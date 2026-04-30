

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
# Plain dict so the value survives Zerve's cross-block serialization unchanged.
# (When this was a pd.Series Zerve sometimes restored it with a RangeIndex,
# breaking string-key access in downstream blocks.)
funnel_reach = {
    "1_signed_up":       int(len(user_features)),
    "2_active":          int(is_active.sum()),
    "3_created_content": int(is_created.sum()),
    "4_used_ai":         int(is_ai.sum()),
    "5_engaged":         int(is_engaged.sum()),
    "5b_at_risk":        int(is_at_risk.sum()),
    "6_upgraded":        int(user_features["upgraded"].sum()),
}
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

# ── Visualization on the canvas node: pie of mutually-exclusive current
# stages + horizontal bar of strict-nested cumulative reach.
import matplotlib.pyplot as plt

stage_color = {
    "1_signed_up":       "#475569",
    "2_active":          "#3b82f6",
    "3_created_content": "#06b6d4",
    "4_used_ai":         "#10b981",
    "5_engaged":         "#84cc16",
    "5b_at_risk":        "#f59e0b",
    "6_upgraded":        "#ec4899",
}
nice = {
    "1_signed_up":       "signed up only",
    "2_active":          "active only",
    "3_created_content": "created only",
    "4_used_ai":         "used AI only",
    "5_engaged":         "engaged",
    "5b_at_risk":        "at risk",
    "6_upgraded":        "upgraded",
}

# Order from "stuck" to "deepest" so the pie reads clockwise from churn → conversion.
pie_order = ["1_signed_up", "2_active", "3_created_content", "4_used_ai", "5_engaged", "5b_at_risk", "6_upgraded"]
pie_labels = [nice[s] for s in pie_order]
pie_values = [int(counts[s]) for s in pie_order]
pie_colors = [stage_color[s] for s in pie_order]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={"width_ratios": [1, 1.2]})

# Donut pie (mutually exclusive — sums to 100%)
wedges, _, autotexts = ax1.pie(
    pie_values,
    labels=None,
    colors=pie_colors,
    startangle=90,
    counterclock=False,
    autopct=lambda p: f"{p:.1f}%" if p > 2.0 else "",
    pctdistance=0.78,
    wedgeprops={"width": 0.42, "edgecolor": "#020617", "linewidth": 1.2},
    textprops={"color": "white", "fontsize": 9, "fontweight": "bold"},
)
ax1.text(0, 0.06, f"{total:,}", ha="center", va="center", fontsize=22, fontweight="bold")
ax1.text(0, -0.10, "USERS", ha="center", va="center", fontsize=9, color="#94a3b8")
ax1.set_title("Current stage breakdown — mutually exclusive (sums to 100%)")
ax1.legend(wedges, [f"{l}  ({c:,})" for l, c in zip(pie_labels, pie_values)],
           loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9, frameon=False)

# Strict-nested funnel (cumulative reach)
funnel_order = ["1_signed_up", "2_active", "3_created_content", "4_used_ai", "5_engaged", "6_upgraded"]
funnel_labels = [s.split("_", 1)[1].replace("_", " ") for s in funnel_order]
funnel_counts = [int(funnel_reach[s]) for s in funnel_order]
funnel_colors = [stage_color[s] for s in funnel_order]
ax2.barh(range(len(funnel_counts)), funnel_counts, color=funnel_colors, edgecolor="#020617")
ax2.set_yticks(range(len(funnel_counts)))
ax2.set_yticklabels(funnel_labels)
ax2.invert_yaxis()
ax2.set_xlabel("users (cumulative reach, strict-nested)")
ax2.set_title("Strict-nested funnel — every higher stage requires all lower")
for i, v in enumerate(funnel_counts):
    pct = 100 * v / total if total else 0.0
    ax2.text(v, i, f"  {v:,}  ({pct:.1f}%)", va="center", fontsize=9)

plt.tight_layout()
plt.show()
