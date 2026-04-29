

# Inherits `events` and `user_features` from upstream blocks.
# Two-panel chart: left = funnel descent, right = top-15 events.

import matplotlib.pyplot as plt

stage_order = [
    "1_signed_up",
    "2_active",
    "3_created_content",
    "4_used_ai",
    "5_engaged",
    "6_upgraded",
]
reach = pd.Series({
    "1_signed_up":       len(user_features),
    "2_active":          int((user_features["n_signins"] >= 2).sum()),
    "3_created_content": int((user_features["n_created"] > 0).sum()),
    "4_used_ai":         int((user_features["n_ai"] > 0).sum()),
    "5_engaged":         int(((user_features["n_distinct_days"] >= 3) & (user_features["n_ai"] > 0)).sum()),
    "6_upgraded":        int(user_features["upgraded"].sum()),
})
labels = [s.split("_", 1)[1].replace("_", " ") for s in stage_order]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# Left: funnel — cumulative reach
total = reach["1_signed_up"]
bars1 = ax1.barh(range(len(reach)), reach.values, color="#4c72b0")
ax1.set_yticks(range(len(reach)))
ax1.set_yticklabels(labels)
ax1.invert_yaxis()
ax1.set_xlabel("users (cumulative reach)")
ax1.set_title("User funnel — users who reached each stage")
for i, v in enumerate(reach.values):
    pct = 100 * v / total if total else 0.0
    ax1.text(v, i, f"  {v:,}  ({pct:.1f}%)", va="center", fontsize=9)

# Right: top events
top = events["event"].value_counts().head(15)
ax2.barh(range(len(top)), top.values, color="#dd8452")
ax2.set_yticks(range(len(top)))
ax2.set_yticklabels(top.index, fontsize=9)
ax2.invert_yaxis()
ax2.set_xlabel("event count")
ax2.set_title("Top 15 events by frequency")
for i, v in enumerate(top.values):
    ax2.text(v, i, f"  {v:,}", va="center", fontsize=8)

plt.tight_layout()
plt.show()
