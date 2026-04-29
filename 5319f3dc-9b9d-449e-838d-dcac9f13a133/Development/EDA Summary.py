

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
