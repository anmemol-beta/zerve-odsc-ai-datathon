"""ROI Ranking — flatten K2-Think actions and rank by expected ROI.

Reads `strategies` (from Build Strategies). Each segment yields up to 3
actions; with 14 segments that's up to 42 candidate actions. This block
produces:

    1. all-actions table sorted by `estimated_roi_multiple`
    2. top-10 actions chart
    3. per-channel ROI distribution (boxplot)
    4. per-segment best ROI (bar chart)

Outputs:
    actions_long             pd.DataFrame  — one row per action (n × 3)
    roi_top10                pd.DataFrame  — top-10 by ROI
    roi_per_channel          pd.DataFrame  — channel summary stats
    roi_per_segment          pd.DataFrame  — best ROI per segment
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ─── 1. flatten ───────────────────────────────────────────────────────────
roi_rows = []
for seg in strategies["segments"]:
    if not seg.get("strategy") or not seg["strategy"].get("actions"):
        continue
    label = seg["label"]
    seg_id = seg["segment_id"]
    seg_size = seg["stats"]["size"]
    pos_rate = seg["stats"]["observed_rate"]
    for a in seg["strategy"]["actions"]:
        roi_rows.append({
            "segment_id": seg_id,
            "segment_label": label,
            "segment_size": seg_size,
            "segment_observed_rate": pos_rate,
            "rank": int(a.get("rank", 0)),
            "title": a.get("title", ""),
            "channel": a.get("channel", ""),
            "expected_uplift_pp": float(a.get("expected_uplift_pp", 0)),
            "cost_per_user_usd": float(a.get("estimated_cost_per_user_usd", 0)),
            "roi_multiple": float(a.get("estimated_roi_multiple", 0)),
            "rationale": a.get("rationale", ""),
            "playbook_alignment": a.get("playbook_alignment", ""),
        })

actions_long = pd.DataFrame(roi_rows)
print(f"[ROI] flattened {len(actions_long)} actions across "
      f"{actions_long['segment_id'].nunique()} segments")

if len(actions_long) == 0:
    print("[ROI] no actions found in strategies — skipping rest of block")
    roi_top10 = roi_per_channel = roi_per_segment = pd.DataFrame()
else:
    # ─── 2. top-10 ────────────────────────────────────────────────────────
    roi_top10 = (
        actions_long
        .sort_values("roi_multiple", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    # ─── 3. per-channel summary ───────────────────────────────────────────
    roi_per_channel = (
        actions_long.groupby("channel")
        .agg(n_actions=("roi_multiple", "size"),
             roi_median=("roi_multiple", "median"),
             roi_mean=("roi_multiple", "mean"),
             roi_max=("roi_multiple", "max"),
             cost_median=("cost_per_user_usd", "median"))
        .sort_values("roi_median", ascending=False)
        .reset_index()
    )

    # ─── 4. per-segment best action ───────────────────────────────────────
    roi_per_segment = (
        actions_long.sort_values("roi_multiple", ascending=False)
        .groupby("segment_id", as_index=False)
        .head(1)
        .sort_values("roi_multiple", ascending=False)
        .reset_index(drop=True)
    )

    # ─── reports ──────────────────────────────────────────────────────────
    print()
    print("=" * 100)
    print("TOP-10 ACTIONS BY EXPECTED ROI")
    print("=" * 100)
    for _, r in roi_top10.iterrows():
        print(f"  {r['roi_multiple']:>5.1f}x  "
              f"[{r['channel']:<18}] "
              f"{r['segment_label']:<28} "
              f"{r['title'][:50]}")

    print()
    print("CHANNEL ROI SUMMARY:")
    print(roi_per_channel.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # ─── plots ────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # [L] top-10
    ax = axes[0]
    top = roi_top10.iloc[::-1]
    labels = [f"{r['segment_id']}\n{r['title'][:30]}" for _, r in top.iterrows()]
    ax.barh(labels, top["roi_multiple"], color="#ec4899")
    ax.set_xlabel("estimated ROI multiple")
    ax.set_title("Top-10 K2 actions by expected ROI")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(alpha=0.3, axis="x")

    # [M] per-channel boxplot
    ax = axes[1]
    channels = roi_per_channel["channel"].tolist()
    box_data = [actions_long[actions_long["channel"] == ch]["roi_multiple"].values
                for ch in channels]
    bp = ax.boxplot(box_data, labels=channels, vert=True, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("#06b6d4")
        patch.set_alpha(0.6)
    ax.set_ylabel("ROI multiple")
    ax.set_title("ROI distribution by channel")
    ax.tick_params(axis="x", rotation=30, labelsize=9)
    ax.grid(alpha=0.3, axis="y")

    # [R] per-segment best
    ax = axes[2]
    seg_view = roi_per_segment.iloc[::-1]
    ax.barh(seg_view["segment_label"], seg_view["roi_multiple"], color="#10b981")
    ax.set_xlabel("best action ROI")
    ax.set_title("Best ROI per segment")
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(alpha=0.3, axis="x")

    plt.suptitle("K2 Strategist — ROI ranking dashboard", fontsize=13, y=1.02)
    plt.tight_layout()
    plt.show()
