

# Inherits `df` from upstream "Example Dataset" block.
# Builds a slim, type-cast `events` frame for downstream blocks.

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)

events = (
    df[["person_id", "timestamp", "event"]]
    .dropna(subset=["person_id", "timestamp", "event"])
    .reset_index(drop=True)
)

n_rows = len(events)
n_users = events["person_id"].nunique()
n_event_types = events["event"].nunique()

print(f"rows                 : {n_rows:,}")
print(f"unique users         : {n_users:,}")
print(f"distinct event types : {n_event_types}")
print(f"time range           : {events['timestamp'].min()}  ->  {events['timestamp'].max()}")
print()

print("Top 20 events by frequency:")
print(events["event"].value_counts().head(20).to_string())
print()

# Target: subscription_upgraded
upgraded_users = set(events.loc[events["event"] == "subscription_upgraded", "person_id"].unique())
print(f"subscription_upgraded distinct users : {len(upgraded_users):,}")
print(f"base upgrade rate                    : {100 * len(upgraded_users) / n_users:.2f}%  of all users")
print()

# Leakage watch — events that fire right around the upgrade. Do NOT use as features.
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
print("Likely leakage events (exclude from features for upgrade prediction):")
print(leak.to_string() if len(leak) else "  (none observed)")
