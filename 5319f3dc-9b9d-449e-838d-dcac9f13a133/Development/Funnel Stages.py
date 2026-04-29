

# Strict-nested funnel — every higher stage requires all lower stages to be
# satisfied as well. This guarantees monotone-decreasing reach (the property
# the kickoff guide §6 example assumes) and gives meaningful "conversion from
# prior" numbers.
#
# Rules (all observable from event log; no subjective calls):
#   1_signed_up        : everyone with ≥1 event
#   2_active           : 1_signed_up AND (n_signins ≥ 2 OR n_distinct_days ≥ 2)
#   3_created_content  : 2_active AND user produced content
#   4_used_ai          : 3_created_content AND user invoked AI
#   5_engaged          : 4_used_ai AND n_distinct_days ≥ 3
#   5b_at_risk         : 5_engaged AND no activity in last 14 days (NOT upgraded)
#   6_upgraded         : has subscription_upgraded event (terminal)
#
# `now_ts` = latest timestamp in the dataset. Used for at_risk recency.

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
SIGNIN_EVENT  = "sign_in"
AT_RISK_DAYS  = 14

now_ts = events["timestamp"].max()

flags = pd.DataFrame({
    "person_id":  events["person_id"],
    "is_signin":  events["event"].eq(SIGNIN_EVENT),
    "is_created": events["event"].isin(CREATED_EVENTS),
    "is_ai":      events["event"].isin(AI_EVENTS),
    "is_upgrade": events["event"].eq(UPGRADE_EVENT),
    "date":       events["timestamp"].dt.date,
    "ts":         events["timestamp"],
})

user_features = flags.groupby("person_id", sort=False).agg(
    n_signins       = ("is_signin",  "sum"),
    n_created       = ("is_created", "sum"),
    n_ai            = ("is_ai",      "sum"),
    upgraded        = ("is_upgrade", "any"),
    n_distinct_days = ("date",       "nunique"),
    last_event_ts   = ("ts",         "max"),
    first_event_ts  = ("ts",         "min"),
)

user_features["days_since_last_event"] = (now_ts - user_features["last_event_ts"]).dt.total_seconds() / 86400
user_features["account_age_days"] = (user_features["last_event_ts"] - user_features["first_event_ts"]).dt.total_seconds() / 86400

# Strict-nested stage assignment. Each rule depends on the previous mask.
is_active   = (user_features["n_signins"] >= 2) | (user_features["n_distinct_days"] >= 2)
is_created  = is_active  & (user_features["n_created"] > 0)
is_ai       = is_created & (user_features["n_ai"] > 0)
is_engaged  = is_ai      & (user_features["n_distinct_days"] >= 3)
is_at_risk  = is_engaged & (user_features["days_since_last_event"] > AT_RISK_DAYS) & (~user_features["upgraded"])

stage = pd.Series("1_signed_up", index=user_features.index)
stage[is_active]  = "2_active"
stage[is_created] = "3_created_content"
stage[is_ai]      = "4_used_ai"
stage[is_engaged] = "5_engaged"
stage[is_at_risk] = "5b_at_risk"
stage[user_features["upgraded"]] = "6_upgraded"
user_features["stage"] = stage

stage_order = [
    "1_signed_up",
    "2_active",
    "3_created_content",
    "4_used_ai",
    "5_engaged",
    "5b_at_risk",
    "6_upgraded",
]

# Cumulative reach — monotone decreasing by construction since each mask is
# AND of the previous. at_risk is broken out as a side-pocket of engaged.
# Exported as `funnel_reach` so the visualization block reuses it.
funnel_reach = pd.Series({
    "1_signed_up":       len(user_features),
    "2_active":          int(is_active.sum()),
    "3_created_content": int(is_created.sum()),
    "4_used_ai":         int(is_ai.sum()),
    "5_engaged":         int(is_engaged.sum()),
    "5b_at_risk":        int(is_at_risk.sum()),
    "6_upgraded":        int(user_features["upgraded"].sum()),
})
reach = funnel_reach  # alias kept for downstream readability
total = int(funnel_reach["1_signed_up"])

print(f"reference 'now'         : {now_ts}")
print(f"at-risk inactivity gate : >{AT_RISK_DAYS} days since last event")
print()
print("Funnel — cumulative reach (each higher stage AND of all lower)")
print(f"{'stage':<22}{'users':>8}  {'% of total':>11}  {'conv from prior':>17}")
prior_chain = ["1_signed_up", "2_active", "3_created_content", "4_used_ai", "5_engaged", "6_upgraded"]
prev = total
for s in prior_chain:
    c = int(reach[s])
    pct = 100 * c / total if total else 0.0
    conv = 100 * c / prev if prev else 0.0
    print(f"{s:<22}{c:>8,}  {pct:>10.2f}%  {conv:>16.2f}%")
    prev = c
print(f"{'5b_at_risk (lateral)':<22}{int(reach['5b_at_risk']):>8,}  {100*reach['5b_at_risk']/total:>10.2f}%  (subset of 5_engaged who went inactive)")

print()
print("Current-stage distribution (each user's terminal stage):")
counts = user_features["stage"].value_counts().reindex(stage_order, fill_value=0).astype(int)
for s in stage_order:
    c = int(counts[s])
    pct = 100 * c / total if total else 0.0
    print(f"  {s:<22}{c:>8,}  ({pct:>5.2f}%)")
