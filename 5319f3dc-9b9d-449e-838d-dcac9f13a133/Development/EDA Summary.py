# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false


# Inherits the slim `events` frame from "Example Dataset" — already parsed,
# already deduped. This block only prints summary stats and flags leakage.

eda_n_users = events["person_id"].nunique()

print("Top 20 events by frequency:")
print(events["event"].value_counts().head(20).to_string())
print()

upgraded_users = events.loc[events["event"] == "subscription_upgraded", "person_id"].nunique()
print(f"subscription_upgraded distinct users : {upgraded_users:,}")
print(f"base upgrade rate                    : {100 * upgraded_users / eda_n_users:.2f}%  of all users")
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

eda_fig, (eda_ax1, eda_ax2) = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [3, 1]})

top20 = events["event"].value_counts().head(20)
colors = ["#dd8452" if e in LEAK_CANDIDATES else "#4c72b0" for e in top20.index]
eda_ax1.barh(range(len(top20)), top20.values, color=colors)
eda_ax1.set_yticks(range(len(top20)))
eda_ax1.set_yticklabels(top20.index, fontsize=9)
eda_ax1.invert_yaxis()
eda_ax1.set_xlabel("event count")
eda_ax1.set_title(f"Top 20 events  ·  {eda_n_users:,} users  ·  base upgrade rate {100*upgraded_users/eda_n_users:.2f}%")
for eda_i, eda_ev in enumerate(top20.values):
    eda_ax1.text(eda_ev, eda_i, f"  {eda_ev:,}", va="center", fontsize=8)
eda_ax1.legend(handles=[
    plt.Rectangle((0, 0), 1, 1, color="#4c72b0", label="safe to use as feature"),
    plt.Rectangle((0, 0), 1, 1, color="#dd8452", label="leakage — excluded"),
], loc="lower right", fontsize=8)

daily_events = events.groupby(events["timestamp"].dt.date).size()
eda_ax2.fill_between(daily_events.index, daily_events.values, color="#4c72b0", alpha=0.5, linewidth=0)
eda_ax2.plot(daily_events.index, daily_events.values, color="#4c72b0", linewidth=1)
eda_ax2.set_xlabel("date")
eda_ax2.set_ylabel("events / day")
eda_ax2.set_title(f"Daily event volume  ·  {events['timestamp'].min().date()} → {events['timestamp'].max().date()}")
eda_ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
