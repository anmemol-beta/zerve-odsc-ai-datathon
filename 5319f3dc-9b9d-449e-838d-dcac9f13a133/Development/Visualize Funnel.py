# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false


# Inherits `events`, `user_features`, `funnel_reach` from upstream blocks.
# Two-panel chart: left = strict-nested funnel + at_risk, right = top-15 events.

import matplotlib.pyplot as plt

chain = ["1_signed_up", "2_active", "3_created_content", "4_used_ai", "5_engaged", "6_upgraded"]
labels = [s.split("_", 1)[1].replace("_", " ") for s in chain]
counts = [int(funnel_reach[s]) for s in chain]
at_risk_count = int(funnel_reach["5b_at_risk"])
total = counts[0]

vf_fig, (vf_ax1, vf_ax2) = plt.subplots(1, 2, figsize=(15, 6))

vf_ax1.barh(range(len(counts)), counts, color="#4c72b0")
vf_ax1.set_yticks(range(len(counts)))
vf_ax1.set_yticklabels(labels)
vf_ax1.invert_yaxis()
vf_ax1.set_xlabel("users (cumulative reach, strict-nested)")
vf_ax1.set_title("User funnel — each higher stage requires all lower")
for i, vc in enumerate(counts):
    pct = 100 * vc / total if total else 0.0
    vf_ax1.text(vc, i, f"  {vc:,}  ({pct:.1f}%)", va="center", fontsize=9)
# Annotate at_risk as a lateral note on the engaged row (index 4)
vf_ax1.text(counts[4] * 0.55, 4.4, f"at_risk: {at_risk_count:,} (engaged → inactive)",
         color="#c44e52", fontsize=8, style="italic")

top = events["event"].value_counts().head(15)
vf_ax2.barh(range(len(top)), top.values, color="#dd8452")
vf_ax2.set_yticks(range(len(top)))
vf_ax2.set_yticklabels(top.index, fontsize=9)
vf_ax2.invert_yaxis()
vf_ax2.set_xlabel("event count")
vf_ax2.set_title("Top 15 events by frequency")
for i, vt in enumerate(top.values):
    vf_ax2.text(vt, i, f"  {vt:,}", va="center", fontsize=8)

plt.tight_layout()
plt.show()
