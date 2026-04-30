# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false


# Inherits the slim `events` frame from "Example Dataset" — already parsed,
# already deduped. This block only prints summary stats and flags leakage.

n_users = events["person_id"].nunique()

print("Top 20 events by frequency:")
print(events["event"].value_counts().head(20).to_string())
print()

upgraded_users = events.loc[events["event"] == "subscription_upgraded", "person_id"].nunique()
print(f"subscription_upgraded distinct users : {upgraded_users:,}")
print(f"base upgrade rate                    : {100 * upgraded_users / n_users:.2f}%  of all users")
print()

# Events that fire right around the upgrade. Do NOT use as features for the
# upgrade-prediction model — kickoff guide §4 ("WARNING: target leakage").
LEAK_CANDIDATES = [
    "clicked_upgrade",
    "upgrade_subscription",
    "redeem upgrade offer",
    "promo_code_redeemed",
    "watermark_remove_upgrade_clicked",
    "agent_resume_plan_button_clicked",
    "seats_exceeded_share_resource_warning_clicked_upgrade",
]
leak = events.loc[events["event"].isin(LEAK_CANDIDATES), "event"].value_counts()
leak = leak[leak > 0]
print("Likely leakage events (exclude from upgrade-prediction features):")
print(leak.to_string() if len(leak) else "  (none observed)")

# ── Visualization on the canvas node: top-20 events bar chart with daily activity sparkline.
import matplotlib.pyplot as plt

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [3, 1]})

top20 = events["event"].value_counts().head(20)
colors = ["#dd8452" if e in LEAK_CANDIDATES else "#4c72b0" for e in top20.index]
ax1.barh(range(len(top20)), top20.values, color=colors)
ax1.set_yticks(range(len(top20)))
ax1.set_yticklabels(top20.index, fontsize=9)
ax1.invert_yaxis()
ax1.set_xlabel("event count")
ax1.set_title(f"Top 20 events  ·  {n_users:,} users  ·  base upgrade rate {100*upgraded_users/n_users:.2f}%")
for i, v in enumerate(top20.values):
    ax1.text(v, i, f"  {v:,}", va="center", fontsize=8)
ax1.legend(handles=[
    plt.Rectangle((0, 0), 1, 1, color="#4c72b0", label="safe to use as feature"),
    plt.Rectangle((0, 0), 1, 1, color="#dd8452", label="leakage — excluded"),
], loc="lower right", fontsize=8)

daily_events = events.groupby(events["timestamp"].dt.date).size()
ax2.fill_between(daily_events.index, daily_events.values, color="#4c72b0", alpha=0.5, linewidth=0)
ax2.plot(daily_events.index, daily_events.values, color="#4c72b0", linewidth=1)
ax2.set_xlabel("date")
ax2.set_ylabel("events / day")
ax2.set_title(f"Daily event volume  ·  {events['timestamp'].min().date()} → {events['timestamp'].max().date()}")
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
