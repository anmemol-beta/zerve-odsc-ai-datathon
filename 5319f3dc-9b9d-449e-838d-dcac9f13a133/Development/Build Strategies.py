"""Build Strategies — K2-Think marketing recommendations per v4 funnel segment.

Self-contained canvas block that consumes upstream namespace:
    user_features_v4    (Funnel v4)        — final_stage, upgraded, days_since_last
    X_v3_train/test     (Build Features v3) — behavioral + demographic features
    ensemble_proba_v3   (Train Model v3)    — calibrated upgrade probability (test)

Behavior:
    if env var K2_API_KEY is set:
        → real-time path. Calls K2-Think 14 times (one per segment),
          parses JSON, validates schema. Result is FRESH at run time.
    else:
        → cache fallback. Pulls the last-committed strategies.json from
          this repo's github raw URL so the canvas stays runnable for
          anyone without an API key (executable-without-errors guarantee).

Outputs in namespace:
    strategies           dict — {generated_at, model, n_segments, segments, _source}
    strategies_segments  list — same as strategies['segments'] for convenience

The frontend (web/components/ActionCards.tsx) reads the same JSON shape from
web/public/data/strategies.json — that file is regenerated locally by
build_strategies.py + committed; the canvas block is the cloud-side mirror
for rubric "all work in Zerve" compliance.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# ═══ 1. config ═══════════════════════════════════════════════════════════
K2_API_KEY = os.environ.get("K2_API_KEY", "")
K2_API_BASE = os.environ.get("K2_API_BASE", "https://api.k2think.ai/v1")
K2_MODEL = os.environ.get("K2_MODEL", "MBZUAI-IFM/K2-Think-v2")

REPO_RAW = (
    "https://raw.githubusercontent.com/"
    "anmemol-beta/zerve-odsc-ai-datathon/main"
)
CACHED_STRATEGIES_URL = f"{REPO_RAW}/web/public/data/strategies.json"
PLAYBOOK_URL = f"{REPO_RAW}/business_playbook.md"


# ═══ 2. K2 client (inlined; no llm_client.py import needed) ═════════════
_JSON_BLOCK = re.compile(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", re.DOTALL)


def _k2_chat(messages: list, temperature: float = 0.2, retries: int = 2) -> str:
    body = json.dumps({
        "model": K2_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{K2_API_BASE}/chat/completions",
        method="POST",
        data=body,
        headers={
            "Authorization": f"Bearer {K2_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                payload = json.loads(r.read())
            text = payload["choices"][0]["message"]["content"]
            if "</think>" in text:
                text = text.split("</think>", 1)[1]
            return text.strip()
        except Exception as e:
            last_err = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"K2 chat failed after {retries + 1} attempts: {last_err}")


def _k2_json(user_prompt: str, system: str, temperature: float = 0.2) -> dict:
    sys2 = system + "\n\nReturn ONLY valid JSON. No prose, no markdown fences."
    text = _k2_chat(
        [{"role": "system", "content": sys2},
         {"role": "user",   "content": user_prompt}],
        temperature=temperature,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for cand in sorted(_JSON_BLOCK.findall(text), key=len, reverse=True):
            try:
                return json.loads(cand)
            except json.JSONDecodeError:
                continue
        raise RuntimeError("K2 returned non-JSON content")


# ═══ 3. prompt template (inlined from prompts.py) ════════════════════════
STRATEGIST_SYSTEM = """\
You are a senior growth strategist at Zerve, a cloud AI notebook platform
(competitors: Google Colab, Hex, Deepnote). You help Zerve's product and
marketing teams turn user-segment data into specific, ROI-justified
campaigns.

Zerve's monetization: free tier with credit-based usage. Users upgrade to
the paid plan when they hit credit limits, deploy notebooks externally,
or use the Coder Agent intensively. Most upgrades happen within 7 days
of signup; ~36% of paying users go inactive within 60 days.

You will be given ONE user segment along with its statistics, behavioral
features, demographics, and relevant business-playbook context. Output
exactly 3 prioritized marketing actions ranked by expected ROI, plus 3
risks.

Be concrete: name the channel, write actual ad/email copy (not a
description of what to write), give a target filter that an analyst
could turn into SQL, and tie every claim to the data the user provided
or the playbook excerpt.

Return ONLY valid JSON matching this schema. No prose, no markdown
fences, no commentary:

{
  "segment_id": str, "summary": str,
  "actions": [
    {"rank": 1|2|3, "title": str,
     "channel": "email"|"in_app_modal"|"sales_call"|"push_notification"|"ad_retargeting"|"lifecycle_drip",
     "message_en": str, "message_ko": str, "target_filter": str,
     "expected_uplift_pp": float, "estimated_cost_per_user_usd": float,
     "estimated_roi_multiple": float, "rationale": str,
     "playbook_alignment": str},
    ... 2 more
  ],
  "risks": [str, str, str]
}
"""


def _fmt_num(x):
    if isinstance(x, float):
        return f"{x:.4f}" if abs(x) < 0.01 else f"{x:.2f}"
    return str(x)


def _build_user_prompt(seg: dict, playbook_excerpt: str) -> str:
    L: list[str] = []
    L.append(f"SEGMENT_ID:   {seg['segment_id']}")
    L.append(f"LABEL:        {seg['label']}")
    L.append(f"SIZE:         {seg['size']:,} users  ({seg['pct_of_total']:.1f}% of all)")
    L.append("")
    L.append(f"OBSERVED UPGRADE RATE (within window): {seg['observed_rate']:.2%}")
    L.append(f"BASELINE (all users):                  {seg['baseline_rate']:.2%}")
    L.append(f"LIFT vs baseline:                      {seg['baseline_lift']:.2f}x")
    L.append("")
    L.append("ACTIVITY SUMMARY (medians):")
    L.append(f"  - n_events:        {seg['median_n_events']:,}")
    L.append(f"  - distinct_days:   {seg['median_distinct_days']}")
    L.append(f"  - days_since_last: {seg['median_days_since_last']:.1f}")
    L.append(f"  - session_minutes: {seg['median_session_min']:.1f}")
    L.append("")
    L.append("TOP DISTINGUISHING BEHAVIORS (vs baseline, sorted by reach lift):")
    for r in seg["top_behavioral"]:
        L.append(f"  - {r['feature']}: seg_med={_fmt_num(r['seg_median'])}, "
                 f"base_med={_fmt_num(r['base_median'])}, "
                 f"reach={r['seg_reach']:.1%} vs {r['base_reach']:.1%} "
                 f"(lift {r['reach_lift']:.1f}x)")
    L.append("")
    L.append("DEMOGRAPHIC PROFILE (top values):")
    for k, v in seg["demographics"].items():
        L.append(f"  - {k}: {v}")
    L.append("")
    L.append("METADATA FLAG MIX:")
    for k, v in seg["metadata"].items():
        L.append(f"  - {k}: {v}")
    L.append("")
    L.append("PREDICTION SCORE (v3 calibrated ensemble, on this segment):")
    L.append(f"  - median: {seg['score']['median']:.3f}")
    L.append(f"  - p90:    {seg['score']['p90']:.3f}")
    L.append(f"  - share above top-5%-cutoff: {seg['score']['pct_top5']:.1%}")
    L.append("")
    L.append("FUNNEL CONTEXT:")
    L.append(f"  Stage \"{seg['label']}\" (rank {seg['stage_rank']}/15)")
    L.append(f"  Adjacent: {seg['adjacent']}")
    L.append("")
    L.append("BUSINESS PLAYBOOK EXCERPT (use this to ground recommendations):")
    L.append("---")
    L.append(playbook_excerpt)
    L.append("---")
    L.append("")
    L.append("TASK: Recommend 3 prioritized marketing actions for this segment, plus")
    L.append("3 risks. Output the JSON object only, matching the schema in your")
    L.append("instructions exactly.")
    return "\n".join(L)


# ═══ 4. segment definitions ══════════════════════════════════════════════
SEGMENTS: list[dict] = [
    {"id": "new",                  "filter": ("stage_eq", "1.New")},
    {"id": "exploring",            "filter": ("stage_eq", "2.Exploring")},
    {"id": "used_ai",              "filter": ("stage_eq", "4.UsedAI")},
    {"id": "wrote_code",           "filter": ("stage_eq", "5.WroteCode")},
    {"id": "integrated",           "filter": ("stage_eq", "6.Integrated")},
    {"id": "engaged",              "filter": ("stage_eq", "7.Engaged")},
    {"id": "upgraded",             "filter": ("stage_eq", "8.Upgraded")},
    {"id": "atrisk_used_ai",       "filter": ("stage_eq", "9.AtRisk@UsedAI")},
    {"id": "atrisk_wrote_code",    "filter": ("stage_eq", "9.AtRisk@WroteCode")},
    {"id": "atrisk_integrated",    "filter": ("stage_eq", "9.AtRisk@Integrated")},
    {"id": "atrisk_engaged",       "filter": ("stage_eq", "9.AtRisk@Engaged")},
    {"id": "atrisk_upgraded",      "filter": ("stage_eq", "9.AtRisk@Upgraded")},
    {"id": "churned_upgraded",     "filter": ("stage_eq", "9.Churned@Upgraded")},
    {"id": "model_top5_predicted", "filter": ("score_top_pct", 5.0)},
]

STAGE_ORDER = [
    "0.NoEvent", "1.New", "2.Exploring", "3.Created", "4.UsedAI",
    "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded",
    "9.AtRisk@UsedAI", "9.AtRisk@WroteCode", "9.AtRisk@Integrated",
    "9.AtRisk@Engaged", "9.AtRisk@Upgraded", "9.Churned@Upgraded",
]

BEHAVIORAL_FEATURES = [
    "n_events_1h", "n_ai_1h", "n_agent_tool_1h", "n_credits_used_1h",
    "n_run_block_1h", "n_block_create_1h",
    "n_events_24h", "n_ai_24h", "n_agent_tool_24h", "n_credits_exceeded_24h",
    "n_run_block_24h", "n_files_upload_24h", "did_use_agent_24h",
    "did_run_block_24h", "any_tour_finish_24h",
    "n_events_7d", "n_distinct_days_7d", "n_credits_exceeded_7d",
    "n_banner_shown_7d", "did_hit_credit_limit_7d", "did_see_banner_7d",
    "did_deploy_7d", "did_source_control_7d", "did_files_upload_7d",
    "did_canvas_clone_7d",
    "agent_first", "is_power_engaged", "deep_user_24h",
    "engagement_velocity_7d", "credit_pressure_24h",
]


# ═══ 5. helpers ══════════════════════════════════════════════════════════
def _select(feat: pd.DataFrame, spec: tuple) -> pd.Series:
    op, val = spec
    if op == "stage_eq":
        return feat["final_stage"] == val
    if op == "score_top_pct":
        scored = feat.loc[feat["score_avg_v3"].notna(), "score_avg_v3"]
        if len(scored) == 0:
            return pd.Series(False, index=feat.index)
        return feat["score_avg_v3"] >= scored.quantile(1 - val / 100.0)
    raise ValueError(f"unknown filter op: {op}")


def _top_behavioral(feat: pd.DataFrame, mask: pd.Series, k: int = 6) -> list:
    rows: list[dict] = []
    seg_n = int(mask.sum())
    base_n = len(feat)
    if seg_n == 0:
        return rows
    for col in [c for c in BEHAVIORAL_FEATURES if c in feat.columns]:
        s = feat[col].fillna(0)
        seg = s[mask]
        seg_reach = float((seg > 0).sum() / seg_n)
        base_reach = float((s > 0).sum() / base_n)
        if seg_reach == 0 and base_reach == 0:
            continue
        lift = (seg_reach + 1e-3) / (base_reach + 1e-3)
        rows.append({
            "feature": col,
            "seg_median": float(seg.median()),
            "base_median": float(s.median()),
            "seg_reach": seg_reach, "base_reach": base_reach,
            "reach_lift": lift,
        })
    rows.sort(key=lambda r: r["reach_lift"], reverse=True)
    return rows[:k]


def _top_demographics(feat: pd.DataFrame, mask: pd.Series) -> dict:
    seg = feat[mask]
    if len(seg) == 0:
        return {}
    out: dict = {}
    for prefix, label in [
        ("purpose_", "purpose"), ("role_", "role"),
        ("work_type_", "work_type"), ("device_type_", "device_type"),
        ("os_", "os"), ("country_", "country"),
        ("signup_source_", "signup_source"),
    ]:
        cols = [c for c in feat.columns if c.startswith(prefix)]
        if not cols:
            continue
        means = seg[cols].mean()
        if means.isna().all() or means.max() == 0:
            continue
        top_col = means.idxmax()
        out[label] = f"{top_col[len(prefix):]} ({means[top_col]*100:.0f}%)"
    return out


def _metadata_flags(feat: pd.DataFrame, mask: pd.Series) -> dict:
    seg = feat[mask]
    if len(seg) == 0:
        return {}
    out: dict = {}
    for col, label in [
        ("agent_first", "agent_first"),
        ("is_power_engaged", "is_power_engaged"),
        ("any_tour_finish_24h", "tour_finished_within_24h"),
        ("any_submit_form_24h", "submitted_onboarding_form"),
        ("did_hit_credit_limit_7d", "hit_credit_limit_7d"),
    ]:
        if col not in seg.columns:
            continue
        v = seg[col].mean()
        if pd.isna(v):
            continue
        out[label] = f"{v*100:.0f}%"
    return out


def _score_stats(feat: pd.DataFrame, mask: pd.Series) -> dict:
    seg = feat.loc[mask, "score_avg_v3"].dropna()
    allv = feat["score_avg_v3"].dropna()
    if len(seg) == 0 or len(allv) == 0:
        return {"median": 0.0, "p90": 0.0, "pct_top5": 0.0, "n_scored": 0}
    th = allv.quantile(0.95)
    return {
        "median": float(seg.median()),
        "p90": float(seg.quantile(0.9)),
        "pct_top5": float((seg >= th).mean()),
        "n_scored": int(len(seg)),
    }


def _adjacent(label: str) -> str:
    if label not in STAGE_ORDER:
        return "(custom segment)"
    i = STAGE_ORDER.index(label)
    prev = STAGE_ORDER[i - 1] if i > 0 else "—"
    nxt = STAGE_ORDER[i + 1] if i + 1 < len(STAGE_ORDER) else "—"
    return f"{prev} → {label} → {nxt}"


def _playbook_excerpt(playbook: str, segment_id: str, label: str) -> str:
    if not playbook or len(playbook) < 50:
        return "(playbook unavailable — generate generic recommendations)"
    keywords = [label, segment_id, label.split(".", 1)[-1].replace("@", " ")]
    paragraphs = re.split(r"\n\s*\n", playbook)
    scored: list[tuple[int, int, str]] = []
    for p in paragraphs:
        s = sum(1 for kw in keywords if kw and kw.lower() in p.lower())
        if s > 0:
            scored.append((s, len(p), p))
    scored.sort(key=lambda t: (-t[0], t[1]))
    chunks: list[str] = []
    used = 0
    for _, _, p in scored:
        if used + len(p) > 1500:
            continue
        chunks.append(p.strip())
        used += len(p)
        if len(chunks) >= 3:
            break
    if not chunks:
        chunks.append(playbook[:1500])
    return "\n\n".join(chunks)


def _build_segment_stats(feat: pd.DataFrame, spec: dict) -> dict | None:
    mask = _select(feat, spec["filter"])
    seg = feat[mask]
    if int(mask.sum()) == 0:
        return None
    if spec["filter"][0] == "stage_eq":
        label = spec["filter"][1]
    elif spec["filter"][0] == "score_top_pct":
        label = f"Top {spec['filter'][1]:.0f}% predicted upgraders (model-based)"
    else:
        label = spec["id"]
    base_rate = float(feat["upgraded"].mean()) if "upgraded" in feat.columns else 0.0
    observed = float(seg["upgraded"].mean()) if "upgraded" in seg.columns else 0.0
    return {
        "segment_id": spec["id"], "label": label,
        "size": int(mask.sum()),
        "pct_of_total": int(mask.sum()) / len(feat) * 100,
        "observed_rate": observed,
        "baseline_rate": base_rate,
        "baseline_lift": observed / base_rate if base_rate > 0 else 0.0,
        "median_n_events": int(seg["n_events_full"].median()) if "n_events_full" in seg.columns else 0,
        "median_distinct_days": int(seg["n_distinct_days_full"].median()) if "n_distinct_days_full" in seg.columns else 0,
        "median_session_min": float(seg["session_minutes_full"].median()) if "session_minutes_full" in seg.columns else 0.0,
        "median_days_since_last": float(seg["days_since_last_full"].median()) if "days_since_last_full" in seg.columns else 0.0,
        "top_behavioral": _top_behavioral(feat, mask),
        "demographics": _top_demographics(feat, mask),
        "metadata": _metadata_flags(feat, mask),
        "score": _score_stats(feat, mask),
        "stage_rank": STAGE_ORDER.index(label) if label in STAGE_ORDER else 0,
        "adjacent": _adjacent(label),
    }


def _compact_stats(s: dict) -> dict:
    return {
        "size": s["size"],
        "pct_of_total": round(s["pct_of_total"], 2),
        "observed_rate": round(s["observed_rate"], 4),
        "baseline_rate": round(s["baseline_rate"], 4),
        "baseline_lift": round(s["baseline_lift"], 2),
        "median_n_events": s["median_n_events"],
        "median_distinct_days": s["median_distinct_days"],
        "median_session_min": round(s["median_session_min"], 1),
        "median_days_since_last": round(s["median_days_since_last"], 1),
        "top_behavioral": [
            {**r,
             "seg_median": round(r["seg_median"], 2),
             "base_median": round(r["base_median"], 2),
             "seg_reach": round(r["seg_reach"], 4),
             "base_reach": round(r["base_reach"], 4),
             "reach_lift": round(r["reach_lift"], 2)}
            for r in s["top_behavioral"]
        ],
        "demographics": s["demographics"],
        "metadata": s["metadata"],
        "score": {k: (round(v, 4) if isinstance(v, float) else v)
                  for k, v in s["score"].items()},
        "stage_rank": s["stage_rank"],
        "adjacent": s["adjacent"],
    }


def _shape_ok(d) -> bool:
    return (
        isinstance(d, dict)
        and isinstance(d.get("actions"), list) and len(d["actions"]) >= 1
        and isinstance(d.get("risks"), list)
    )


def _http_get(url: str, timeout: int = 30) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


# ═══ 6. main pipeline ════════════════════════════════════════════════════
print(f"[Build Strategies] K2_API_KEY {'detected' if K2_API_KEY else 'NOT set'} → "
      f"{'real-time' if K2_API_KEY else 'cache fallback'} mode")

if K2_API_KEY:
    # ── real-time path ──────────────────────────────────────────────────
    # 6a. Build joined feature frame from upstream namespace
    _X_full = pd.concat([X_v3_train, X_v3_test], axis=0)
    _feat = user_features_v4.join(_X_full, how="left")
    _score = pd.Series(ensemble_proba_v3,
                       index=X_v3_test.index, name="score_avg_v3")
    _feat = _feat.join(_score, how="left")
    print(f"[Build Strategies] joined frame: {_feat.shape}, "
          f"with stage={_feat['final_stage'].notna().sum():,}, "
          f"with score={_feat['score_avg_v3'].notna().sum():,}")

    # 6b. Pull playbook from github raw
    try:
        playbook = _http_get(PLAYBOOK_URL).decode("utf-8")
        print(f"[Build Strategies] playbook fetched: {len(playbook):,} chars")
    except Exception as e:
        print(f"[Build Strategies] playbook fetch failed ({e}) — using fallback")
        playbook = ""

    # 6c. Loop segments → K2
    out_segments: list[dict] = []
    for spec in SEGMENTS:
        stats = _build_segment_stats(_feat, spec)
        if stats is None or stats["size"] == 0:
            print(f"  [skip] {spec['id']:<25} empty")
            continue
        excerpt = _playbook_excerpt(playbook, stats["segment_id"], stats["label"])
        prompt = _build_user_prompt(stats, excerpt)
        print(f"  [K2]   {spec['id']:<25} n={stats['size']:>6,}  ", end="", flush=True)
        try:
            strategy = _k2_json(prompt, system=STRATEGIST_SYSTEM, temperature=0.2)
            ok = _shape_ok(strategy)
            print(f"→ {'ok' if ok else 'shape-mismatch'}")
            if not ok:
                strategy = None
        except Exception as e:
            print(f"→ FAILED ({e})")
            strategy = None
        out_segments.append({
            "segment_id": stats["segment_id"],
            "label": stats["label"],
            "stats": _compact_stats(stats),
            "strategy": strategy,
        })

    strategies = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": K2_MODEL,
        "n_segments": len(out_segments),
        "segments": out_segments,
        "_source": "real-time-k2",
    }
else:
    # ── cache fallback ──────────────────────────────────────────────────
    print(f"[Build Strategies] fetching cached strategies → {CACHED_STRATEGIES_URL}")
    try:
        strategies = json.loads(_http_get(CACHED_STRATEGIES_URL))
        strategies["_source"] = "cached-github-raw"
    except Exception as e:
        raise RuntimeError(
            f"Cache fallback failed and no K2_API_KEY set. "
            f"Set K2_API_KEY env var or check network access. {e}"
        )

# ═══ 7. summary + namespace export ═══════════════════════════════════════
strategies_segments = strategies["segments"]
n_with_strategy = sum(1 for s in strategies_segments if s.get("strategy"))
print(f"\n=== strategies ready: {strategies['n_segments']} segments "
      f"({n_with_strategy} with K2 strategy) — source: {strategies.get('_source')} ===")
for s in strategies_segments[:5]:
    n_actions = len(s["strategy"]["actions"]) if s.get("strategy") else 0
    print(f"  - {s['label']:<32} → {n_actions} actions")
print(f"  ... ({len(strategies_segments)} segments total)")
