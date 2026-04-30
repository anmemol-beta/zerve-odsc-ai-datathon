"""Generate web/public/data/strategies.json — per-segment marketing
recommendations from K2-Think.

Pipeline:
  1. Load funnel_v4_assignment.csv, mission1_v3_predictions.csv,
     feature_matrix.parquet, business_playbook.md
  2. Define 14 segments (13 funnel stages with non-trivial size + 1
     model-based "Top 5% predicted upgraders" cross-cut)
  3. For each segment, extract size, observed rate, top behavioral
     features by reach lift, demographics, metadata flags, score stats
  4. Pull a relevant playbook excerpt by keyword match against the
     stage label
  5. Render the user prompt, call K2 (cached), parse JSON
  6. Bundle everything into strategies.json with both the raw stats and
     the LLM strategy so the frontend can render context next to the
     recommendation

Re-running is cheap thanks to llm_client's file cache; only changed
prompts re-hit the API.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import llm_client
from prompts import STRATEGIST_SYSTEM, build_user_prompt


ROOT = Path(__file__).resolve().parent
ANALYSIS_ROOT = ROOT.parent  # /Users/hunjunsin/Desktop/zerve

# data files (live in repo root after merge)
FEATURE_PATH = ROOT / "feature_matrix.parquet"
FUNNEL_PATH = ROOT / "funnel_v4_assignment.csv"
PRED_PATH = ROOT / "mission1_v3_predictions.csv"
PLAYBOOK_PATH = ROOT / "business_playbook.md"

OUT_PATH = ROOT / "web" / "public" / "data" / "strategies.json"


# ─── segment definitions ──────────────────────────────────────────────────
SEGMENTS: list[dict] = [
    # active funnel stages (rank by stage number)
    {"id": "new",            "rank": 1,  "filter": ("stage_eq", "1.New")},
    {"id": "exploring",      "rank": 2,  "filter": ("stage_eq", "2.Exploring")},
    {"id": "used_ai",        "rank": 4,  "filter": ("stage_eq", "4.UsedAI")},
    {"id": "wrote_code",     "rank": 5,  "filter": ("stage_eq", "5.WroteCode")},
    {"id": "integrated",     "rank": 6,  "filter": ("stage_eq", "6.Integrated")},
    {"id": "engaged",        "rank": 7,  "filter": ("stage_eq", "7.Engaged")},
    {"id": "upgraded",       "rank": 8,  "filter": ("stage_eq", "8.Upgraded")},
    # at-risk variants
    {"id": "atrisk_used_ai",    "rank": 9,  "filter": ("stage_eq", "9.AtRisk@UsedAI")},
    {"id": "atrisk_wrote_code", "rank": 10, "filter": ("stage_eq", "9.AtRisk@WroteCode")},
    {"id": "atrisk_integrated", "rank": 11, "filter": ("stage_eq", "9.AtRisk@Integrated")},
    {"id": "atrisk_engaged",    "rank": 12, "filter": ("stage_eq", "9.AtRisk@Engaged")},
    {"id": "atrisk_upgraded",   "rank": 13, "filter": ("stage_eq", "9.AtRisk@Upgraded")},
    {"id": "churned_upgraded",  "rank": 14, "filter": ("stage_eq", "9.Churned@Upgraded")},
    # cross-cut: model-flagged top 5%
    {"id": "model_top5_predicted", "rank": 15, "filter": ("score_top_pct", 5.0)},
]

# stage rank for adjacency hint
STAGE_ORDER = [
    "0.NoEvent", "1.New", "2.Exploring", "3.Created", "4.UsedAI",
    "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded",
    "9.AtRisk@UsedAI", "9.AtRisk@WroteCode", "9.AtRisk@Integrated",
    "9.AtRisk@Engaged", "9.AtRisk@Upgraded", "9.Churned@Upgraded",
]


# ─── helpers ──────────────────────────────────────────────────────────────
def load_data() -> tuple[pd.DataFrame, str]:
    print(f"[load] feature matrix...")
    feat = pd.read_parquet(FEATURE_PATH)
    print(f"       {feat.shape[0]:,} users x {feat.shape[1]} cols")

    print(f"[load] funnel v4 labels...")
    fnl = pd.read_csv(FUNNEL_PATH, index_col=0)

    print(f"[load] v3 predictions...")
    pred = pd.read_csv(PRED_PATH).set_index("person_id")

    # join: bring final_stage + score into feature frame
    feat = feat.join(fnl[["final_stage"]], how="left")
    feat = feat.join(pred[["score_avg_v3"]], how="left")
    # fill missing (users not in test set are train-set; leave score NaN)
    print(f"[load] joined: {feat.shape}, "
          f"with stage={feat['final_stage'].notna().sum():,}, "
          f"with score={feat['score_avg_v3'].notna().sum():,}")

    print(f"[load] business playbook...")
    playbook = PLAYBOOK_PATH.read_text(encoding="utf-8")
    return feat, playbook


def select_segment(feat: pd.DataFrame, spec: tuple) -> pd.Series:
    op, val = spec
    if op == "stage_eq":
        return feat["final_stage"] == val
    if op == "score_top_pct":
        # users with score in top val% (only those that have a score)
        with_score = feat.loc[feat["score_avg_v3"].notna(), "score_avg_v3"]
        if len(with_score) == 0:
            return pd.Series(False, index=feat.index)
        threshold = with_score.quantile(1 - val / 100.0)
        return feat["score_avg_v3"] >= threshold
    raise ValueError(f"unknown filter op: {op}")


# Behavioral features we score for "lift" (leakage-safe windowed signals)
BEHAVIORAL_FEATURES = [
    # 1h
    "n_events_1h", "n_ai_1h", "n_agent_tool_1h", "n_credits_used_1h",
    "n_run_block_1h", "n_block_create_1h",
    # 24h
    "n_events_24h", "n_ai_24h", "n_agent_tool_24h", "n_credits_exceeded_24h",
    "n_run_block_24h", "n_files_upload_24h", "did_use_agent_24h",
    "did_run_block_24h", "any_tour_finish_24h",
    # 7d
    "n_events_7d", "n_distinct_days_7d", "n_credits_exceeded_7d",
    "n_banner_shown_7d", "did_hit_credit_limit_7d", "did_see_banner_7d",
    "did_deploy_7d", "did_source_control_7d", "did_files_upload_7d",
    "did_canvas_clone_7d",
    # synthesized
    "agent_first", "is_power_engaged", "deep_user_24h",
    "engagement_velocity_7d", "credit_pressure_24h",
]
# limit to features that exist and are numeric


def top_behavioral_lifts(feat: pd.DataFrame, mask: pd.Series, k: int = 6) -> list:
    """Return top-k features ranked by reach lift (segment vs baseline).

    For each candidate column we compute:
      seg_reach = fraction of segment users with feature > 0
      base_reach = fraction of all users with feature > 0
    """
    rows = []
    seg_n = int(mask.sum())
    if seg_n == 0:
        return rows
    base_n = len(feat)
    candidates = [c for c in BEHAVIORAL_FEATURES if c in feat.columns]
    for col in candidates:
        s = feat[col].fillna(0)
        seg_vals = s[mask]
        seg_reach = float((seg_vals > 0).sum() / seg_n)
        base_reach = float((s > 0).sum() / base_n)
        if seg_reach == 0 and base_reach == 0:
            continue
        # Laplace smoothing to avoid 0-division and overstating tiny features
        lift = (seg_reach + 1e-3) / (base_reach + 1e-3)
        rows.append({
            "feature": col,
            "seg_median": float(seg_vals.median()),
            "base_median": float(s.median()),
            "seg_reach": seg_reach,
            "base_reach": base_reach,
            "reach_lift": lift,
        })
    rows.sort(key=lambda r: r["reach_lift"], reverse=True)
    return rows[:k]


def top_demographics(feat: pd.DataFrame, mask: pd.Series) -> dict:
    """For each one-hot demographic family, pick the dominant value."""
    seg = feat[mask]
    if len(seg) == 0:
        return {}
    out = {}
    for prefix, label in [
        ("purpose_",       "purpose"),
        ("role_",          "role"),
        ("work_type_",     "work_type"),
        ("device_type_",   "device_type"),
        ("os_",            "os"),
        ("country_",       "country"),
        ("signup_source_", "signup_source"),
    ]:
        cols = [c for c in feat.columns if c.startswith(prefix)]
        if not cols:
            continue
        means = seg[cols].mean()
        if means.isna().all() or means.max() == 0:
            continue
        top_col = means.idxmax()
        top_val = top_col[len(prefix):]
        out[label] = f"{top_val} ({means[top_col]*100:.0f}%)"
    return out


def metadata_flags(feat: pd.DataFrame, mask: pd.Series) -> dict:
    seg = feat[mask]
    if len(seg) == 0:
        return {}
    out = {}
    for col, label in [
        ("agent_first",          "agent_first"),
        ("is_power_engaged",     "is_power_engaged"),
        ("any_tour_finish_24h",  "tour_finished_within_24h"),
        ("any_submit_form_24h",  "submitted_onboarding_form"),
        ("did_hit_credit_limit_7d", "hit_credit_limit_7d"),
    ]:
        if col not in seg.columns:
            continue
        v = seg[col].mean()
        if pd.isna(v):
            continue
        out[label] = f"{v*100:.0f}%"
    return out


def score_stats(feat: pd.DataFrame, mask: pd.Series) -> dict:
    """Score percentile stats. If segment has no scored users, return zeros."""
    seg = feat.loc[mask, "score_avg_v3"].dropna()
    all_scores = feat["score_avg_v3"].dropna()
    if len(seg) == 0 or len(all_scores) == 0:
        return {"median": 0.0, "p90": 0.0, "pct_top5": 0.0, "n_scored": 0}
    top5_threshold = all_scores.quantile(0.95)
    return {
        "median": float(seg.median()),
        "p90": float(seg.quantile(0.9)),
        "pct_top5": float((seg >= top5_threshold).mean()),
        "n_scored": int(len(seg)),
    }


def adjacency_hint(label: str) -> str:
    if label not in STAGE_ORDER:
        return "(custom segment)"
    i = STAGE_ORDER.index(label)
    prev = STAGE_ORDER[i - 1] if i > 0 else "—"
    nxt = STAGE_ORDER[i + 1] if i + 1 < len(STAGE_ORDER) else "—"
    return f"{prev} → {label} → {nxt}"


# Playbook is one big markdown. Pick paragraphs that mention the segment
# label or its short name. Keep at most ~1500 chars to control prompt size.
def playbook_excerpt(playbook: str, segment_id: str, label: str) -> str:
    keywords = [label, segment_id]
    short = label.split(".", 1)[-1].replace("@", " ")
    keywords.append(short)
    keywords += {
        "atrisk_upgraded": ["AtRisk@Upgraded", "post-upgrade"],
        "churned_upgraded": ["Churned", "downgrade"],
        "engaged": ["Engaged", "Power Engaged"],
        "upgraded": ["Upgraded", "retention"],
        "model_top5_predicted": ["Top 5%", "Model"],
    }.get(segment_id, [])

    paragraphs = re.split(r"\n\s*\n", playbook)
    scored = []
    for para in paragraphs:
        score = sum(1 for kw in keywords if kw and kw.lower() in para.lower())
        if score > 0:
            scored.append((score, len(para), para))
    scored.sort(key=lambda t: (-t[0], t[1]))

    chunks: list[str] = []
    used = 0
    for _, _, para in scored:
        if used + len(para) > 1500:
            continue
        chunks.append(para.strip())
        used += len(para)
        if len(chunks) >= 3:
            break
    if not chunks:
        # fall back to the TL;DR section
        m = re.search(r"## TL;DR.*?(?=\n## )", playbook, re.DOTALL)
        if m:
            chunks.append(m.group(0).strip()[:1500])
        else:
            chunks.append(playbook[:1500])
    return "\n\n".join(chunks)


# ─── one segment end-to-end ──────────────────────────────────────────────
def build_segment(feat: pd.DataFrame, playbook: str, spec: dict) -> dict:
    mask = select_segment(feat, spec["filter"])
    seg = feat[mask]
    n = int(mask.sum())
    if n == 0:
        return None  # type: ignore

    # Build label for non-stage segments
    if spec["filter"][0] == "stage_eq":
        label = spec["filter"][1]
    elif spec["filter"][0] == "score_top_pct":
        label = f"Top {spec['filter'][1]:.0f}% predicted upgraders (model-based)"
    else:
        label = spec["id"]

    n_users_total = len(feat)
    upg = seg["upgraded"].astype(bool) if "upgraded" in seg.columns else None
    observed = float(upg.mean()) if upg is not None and len(seg) else 0.0
    base_rate = float(feat["upgraded"].mean()) if "upgraded" in feat.columns else 0.0
    lift = observed / base_rate if base_rate > 0 else 0.0

    # Activity medians
    median_n_events = int(seg["n_events_full"].median()) if "n_events_full" in seg.columns else 0
    median_distinct_days = int(seg["n_distinct_days_full"].median()) if "n_distinct_days_full" in seg.columns else 0
    median_session_min = float(seg["session_minutes_full"].median()) if "session_minutes_full" in seg.columns else 0.0
    median_days_since_last = float(seg["days_since_last_full"].median()) if "days_since_last_full" in seg.columns else 0.0

    stats = {
        "segment_id": spec["id"],
        "label": label,
        "size": n,
        "pct_of_total": n / n_users_total * 100,
        "observed_rate": observed,
        "baseline_rate": base_rate,
        "baseline_lift": lift,
        "median_n_events": median_n_events,
        "median_distinct_days": median_distinct_days,
        "median_session_min": median_session_min,
        "median_days_since_last": median_days_since_last,
        "top_behavioral": top_behavioral_lifts(feat, mask),
        "demographics": top_demographics(feat, mask),
        "metadata": metadata_flags(feat, mask),
        "score": score_stats(feat, mask),
        "stage_rank": STAGE_ORDER.index(label) if label in STAGE_ORDER else 0,
        "adjacent": adjacency_hint(label),
    }
    return stats


def _shape_ok(d) -> bool:
    if not isinstance(d, dict):
        return False
    actions = d.get("actions")
    if not isinstance(actions, list) or len(actions) < 1:
        return False
    if not isinstance(d.get("risks"), list):
        return False
    return True


def call_strategist(stats: dict, playbook: str) -> dict | None:
    excerpt = playbook_excerpt(playbook, stats["segment_id"], stats["label"])
    base_prompt = build_user_prompt(stats, excerpt)

    for attempt in range(2):
        prompt = base_prompt
        if attempt == 1:
            # Cache miss + much stronger schema reminder
            prompt += (
                "\n\nIMPORTANT: The previous reply did not wrap actions in the "
                "outer schema. You MUST return a single JSON object whose top "
                "level has keys segment_id, summary, actions (array of 3), "
                "risks (array of 3). Do not return a single action."
            )
        try:
            result = llm_client.ask_json(
                prompt,
                system=STRATEGIST_SYSTEM,
                temperature=0.2,
                use_cache=(attempt == 0),
            )
        except Exception as e:
            print(f"  [warn] {stats['segment_id']} attempt {attempt+1}: {e}")
            continue
        if _shape_ok(result):
            return result
        print(f"  [warn] {stats['segment_id']} attempt {attempt+1}: shape mismatch, retrying")
    print(f"  [fail] {stats['segment_id']} did not produce valid schema")
    return result if isinstance(result, dict) else None  # type: ignore


# ─── main ─────────────────────────────────────────────────────────────────
def main():
    feat, playbook = load_data()

    # Note: feature_matrix has ALL users; v4 stage join may miss some (users
    # without stage assignment will have final_stage=NaN). We treat NaN as
    # not in any of our 13 stage segments, which matches the 0.NoEvent intent.

    out_segments = []
    for spec in SEGMENTS:
        stats = build_segment(feat, playbook, spec)
        if stats is None or stats["size"] == 0:
            print(f"[skip] {spec['id']:<25} empty segment")
            continue
        print(f"[run]  {spec['id']:<25} n={stats['size']:>6,}  "
              f"observed={stats['observed_rate']:.2%}")

        strategy = call_strategist(stats, playbook)

        # Compact representation: keep the data the frontend needs to render
        # alongside the strategy. Skip raw playbook excerpt (large).
        out_segments.append({
            "segment_id": stats["segment_id"],
            "label": stats["label"],
            "stats": {
                "size": stats["size"],
                "pct_of_total": round(stats["pct_of_total"], 2),
                "observed_rate": round(stats["observed_rate"], 4),
                "baseline_rate": round(stats["baseline_rate"], 4),
                "baseline_lift": round(stats["baseline_lift"], 2),
                "median_n_events": stats["median_n_events"],
                "median_distinct_days": stats["median_distinct_days"],
                "median_session_min": round(stats["median_session_min"], 1),
                "median_days_since_last": round(stats["median_days_since_last"], 1),
                "top_behavioral": [
                    {**r, "seg_median": round(r["seg_median"], 2),
                     "base_median": round(r["base_median"], 2),
                     "seg_reach": round(r["seg_reach"], 4),
                     "base_reach": round(r["base_reach"], 4),
                     "reach_lift": round(r["reach_lift"], 2)}
                    for r in stats["top_behavioral"]
                ],
                "demographics": stats["demographics"],
                "metadata": stats["metadata"],
                "score": {
                    "median": round(stats["score"]["median"], 4),
                    "p90":    round(stats["score"]["p90"], 4),
                    "pct_top5": round(stats["score"]["pct_top5"], 4),
                    "n_scored": stats["score"]["n_scored"],
                },
                "stage_rank": stats["stage_rank"],
                "adjacent": stats["adjacent"],
            },
            "strategy": strategy,
        })

    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": llm_client.MODEL,
        "n_segments": len(out_segments),
        "segments": out_segments,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(bundle, indent=2, ensure_ascii=False))
    print(f"\nWROTE: {OUT_PATH}  ({OUT_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
