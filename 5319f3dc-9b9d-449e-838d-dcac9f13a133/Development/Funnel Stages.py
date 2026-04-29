

# Inherits `events`. Builds per-user features in one vectorized groupby pass,
# then assigns each user to exactly one funnel stage (highest reached).

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

# Stage assignment: apply rules from lowest to highest priority — later
# assignments override earlier, so each user lands in their highest stage.
stage = pd.Series("1_signed_up", index=user_features.index)
stage[user_features["n_signins"] >= 2] = "2_active"
stage[user_features["n_created"] > 0] = "3_created_content"
stage[user_features["n_ai"] > 0] = "4_used_ai"
stage[(user_features["n_distinct_days"] >= 3) & (user_features["n_ai"] > 0)] = "5_engaged"
stage[user_features["upgraded"]] = "6_upgraded"
user_features["stage"] = stage

stage_order = [
    "1_signed_up",
    "2_active",
    "3_created_content",
    "4_used_ai",
    "5_engaged",
    "6_upgraded",
]

# Cumulative reach: users who satisfy this stage's criteria regardless of any
# higher stage. This is the standard funnel view — gives monotone-decreasing
# counts that "conversion from prior" is meaningful for.
reach = pd.Series({
    "1_signed_up":       len(user_features),
    "2_active":          int((user_features["n_signins"] >= 2).sum()),
    "3_created_content": int((user_features["n_created"] > 0).sum()),
    "4_used_ai":         int((user_features["n_ai"] > 0).sum()),
    "5_engaged":         int(((user_features["n_distinct_days"] >= 3) & (user_features["n_ai"] > 0)).sum()),
    "6_upgraded":        int(user_features["upgraded"].sum()),
})
total = int(reach["1_signed_up"])

print("Funnel — cumulative reach (users who satisfy this stage)")
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
