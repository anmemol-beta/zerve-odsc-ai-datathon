

# Inherits `events` from upstream "EDA Summary" block.
# Classifies every user into exactly ONE funnel stage (highest reached).
# Stages follow the kickoff guide adapted to the actual event vocabulary.

CREATED_EVENTS = {
    "agent_tool_call_create_block_tool",
    "run_block",
    "new_canvas_created",
}
AI_EVENTS = {
    "$ai_generation",
    "agent_new_chat",
    "agent_worker_created",
}
UPGRADE_EVENT = "subscription_upgraded"
SIGNIN_EVENT = "sign_in"

flags = pd.DataFrame({
    "person_id":  events["person_id"],
    "is_signin":  events["event"].eq(SIGNIN_EVENT),
    "is_created": events["event"].isin(CREATED_EVENTS),
    "is_ai":      events["event"].isin(AI_EVENTS),
    "is_upgrade": events["event"].eq(UPGRADE_EVENT),
    "date":       events["timestamp"].dt.date,
})

user_features = flags.groupby("person_id", sort=False).agg(
    n_signins       = ("is_signin",  "sum"),
    n_created       = ("is_created", "sum"),
    n_ai            = ("is_ai",      "sum"),
    upgraded        = ("is_upgrade", "any"),
    n_distinct_days = ("date",       "nunique"),
)

def stage(r):
    if r["upgraded"]:
        return "6_upgraded"
    if r["n_distinct_days"] >= 3 and r["n_ai"] > 0:
        return "5_engaged"
    if r["n_ai"] > 0:
        return "4_used_ai"
    if r["n_created"] > 0:
        return "3_created_content"
    if r["n_signins"] >= 2:
        return "2_active"
    return "1_signed_up"

user_features["stage"] = user_features.apply(stage, axis=1)

stage_order = [
    "1_signed_up",
    "2_active",
    "3_created_content",
    "4_used_ai",
    "5_engaged",
    "6_upgraded",
]

# Cumulative reach: users who satisfy this stage's criteria regardless of higher
# stages. This is the standard funnel view (kickoff guide §6) and gives
# monotone-decreasing counts that "conversion from prior" actually applies to.
reach_mask = {
    "1_signed_up":       pd.Series(True, index=user_features.index),
    "2_active":          user_features["n_signins"] >= 2,
    "3_created_content": user_features["n_created"] > 0,
    "4_used_ai":         user_features["n_ai"] > 0,
    "5_engaged":         (user_features["n_distinct_days"] >= 3) & (user_features["n_ai"] > 0),
    "6_upgraded":        user_features["upgraded"],
}
reach = pd.Series({s: int(m.sum()) for s, m in reach_mask.items()})
total = int(reach["1_signed_up"])

print("Funnel — cumulative reach (users who satisfy this stage, regardless of higher stages)")
print(f"{'stage':<22}{'users':>8}  {'% of total':>11}  {'conv from prior':>17}")
prev = total
for s in stage_order:
    c = int(reach[s])
    pct = 100 * c / total if total else 0.0
    conv = 100 * c / prev if prev else 0.0
    print(f"{s:<22}{c:>8,}  {pct:>10.2f}%  {conv:>16.2f}%")
    prev = c

print()
print("Current-stage distribution (each user counted in their highest-reached stage):")
counts = user_features["stage"].value_counts().reindex(stage_order, fill_value=0).astype(int)
for s in stage_order:
    c = int(counts[s])
    pct = 100 * c / total if total else 0.0
    print(f"  {s:<22}{c:>8,}  ({pct:>5.2f}%)")

print()
print(f"total classified users : {total:,}")
print(f"upgraded users         : {int(reach['6_upgraded']):,}  ({100*reach['6_upgraded']/total:.2f}%)")
