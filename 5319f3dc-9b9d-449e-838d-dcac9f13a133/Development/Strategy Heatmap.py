"""Strategy Heatmap — 14 segments × 6 channels grid of best ROI per cell.

Reads `strategies` (or `actions_long` if ROI Ranking ran first). Renders
a heatmap that lets a marketing lead see at a glance which channel works
where: e.g., is `in_app_modal` a good fit for `9.AtRisk@*` segments? Are
sales calls reserved for late-funnel cohorts only?

Outputs:
    strategy_heatmap_data    pd.DataFrame   — segments × channels with max ROI
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

CHANNELS = ["email", "in_app_modal", "sales_call",
            "push_notification", "ad_retargeting", "lifecycle_drip"]

# build flat table (avoid depending on ROI Ranking having run)
rows = []
for seg in strategies["segments"]:
    if not seg.get("strategy") or not seg["strategy"].get("actions"):
        continue
    for a in seg["strategy"]["actions"]:
        rows.append({
            "segment": seg["label"],
            "segment_rank": seg["stats"].get("stage_rank", 99),
            "channel": a.get("channel", ""),
            "roi_multiple": float(a.get("estimated_roi_multiple", 0)),
            "expected_uplift_pp": float(a.get("expected_uplift_pp", 0)),
        })
df = pd.DataFrame(rows)
print(f"[heatmap] {len(df)} actions over "
      f"{df['segment'].nunique()} segments × {df['channel'].nunique()} channels")

# pivot: segment × channel, value = MAX roi (best action of that kind)
strategy_heatmap_data = (
    df.pivot_table(index="segment", columns="channel",
                   values="roi_multiple", aggfunc="max")
    .reindex(columns=CHANNELS)
)

# order rows by funnel rank
seg_rank = (df.drop_duplicates("segment").set_index("segment")["segment_rank"])
strategy_heatmap_data = strategy_heatmap_data.reindex(
    seg_rank.sort_values().index
)

print()
print("=" * 90)
print("STRATEGY ROI HEATMAP  (max ROI multiple per segment × channel)")
print("=" * 90)
print(strategy_heatmap_data.fillna(0).round(1).to_string())


# ─── plot ─────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 8))

# [L] ROI heatmap
ax = axes[0]
data = strategy_heatmap_data.fillna(0).values
im = ax.imshow(data, aspect="auto", cmap="RdPu",
               vmin=0, vmax=max(data.max(), 1))
ax.set_xticks(range(len(CHANNELS)))
ax.set_xticklabels(CHANNELS, rotation=30, ha="right")
ax.set_yticks(range(len(strategy_heatmap_data.index)))
ax.set_yticklabels(strategy_heatmap_data.index, fontsize=9)
for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        v = data[i, j]
        if v > 0:
            ax.text(j, i, f"{v:.0f}",
                    ha="center", va="center", fontsize=8,
                    color="white" if v > data.max() * 0.6 else "#1e293b")
ax.set_title("ROI heatmap\n(blank = K2 didn't recommend that channel for this segment)")
plt.colorbar(im, ax=ax, label="ROI multiple")

# [R] action count per cell
ax = axes[1]
count_data = (
    df.pivot_table(index="segment", columns="channel",
                   values="roi_multiple", aggfunc="count")
    .reindex(columns=CHANNELS)
    .reindex(seg_rank.sort_values().index)
    .fillna(0)
)
data2 = count_data.values
im2 = ax.imshow(data2, aspect="auto", cmap="Blues", vmin=0, vmax=max(data2.max(), 1))
ax.set_xticks(range(len(CHANNELS)))
ax.set_xticklabels(CHANNELS, rotation=30, ha="right")
ax.set_yticks(range(len(count_data.index)))
ax.set_yticklabels(count_data.index, fontsize=9)
for i in range(data2.shape[0]):
    for j in range(data2.shape[1]):
        v = int(data2[i, j])
        if v > 0:
            ax.text(j, i, str(v), ha="center", va="center", fontsize=9,
                    color="white" if v >= 2 else "#1e293b")
ax.set_title("Action count per (segment, channel)\n(how often K2 picked each channel)")
plt.colorbar(im2, ax=ax, label="number of actions")

plt.suptitle("K2 strategy distribution across 14 segments × 6 channels",
             fontsize=13, y=1.02)
plt.tight_layout()
plt.show()
