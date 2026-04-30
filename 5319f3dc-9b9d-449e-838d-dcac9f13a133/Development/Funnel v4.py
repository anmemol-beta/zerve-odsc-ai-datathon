# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false


# Funnel v4 — 15-category Time-Aware classifier with post-upgrade lifecycle.
#
# Inherits `events` from "Example Dataset" (slim 3-col load).
#
# Differences vs the team's "Funnel Stages" block:
#   v3 (Funnel Stages) splits users into 6 strict-nested stages (signed_up …
#   upgraded), with at_risk as a lateral state. Cumulative reach drops
#   monotonically: 100 → 36.1 → 16.3 → 16.3 → 8.8 → 1.8.
#
#   v4 (this block) keeps the 15-stage view we landed on after the
#   AtRisk-by-prior-stage and post-upgrade lifecycle analysis:
#     0.NoEvent
#     1.New, 2.Exploring, 3.Created, 4.UsedAI,
#     5.WroteCode, 6.Integrated, 7.Engaged
#     8.Upgraded                 (active paying customer)
#     9.AtRisk@{UsedAI, WroteCode, Integrated, Engaged, Upgraded}
#     9.Churned@Upgraded
#
#   Plus 7 metadata columns (orthogonal to stages — used by the prediction
#   model and the LLM strategist):
#     onboarding_completed, used_promo, agent_first, reactivated,
#     exception_rate, is_power_engaged, purpose
#
# Outputs (used downstream by Build Features v3 and the LLM Segment Strategy
# generator):
#   user_features_v4   per-user dataframe with stage label + 7 meta cols
#   stage_distribution_v4   counts/share per final_stage (for the funnel UI)

from datetime import timedelta

NEW_EVENTS_V4 = {"new_user_created", "sign_up"}
EXPLORE_EVENTS_V4 = {
    "$pageview", "$autocapture",
    "submit_onboarding_form", "skip_onboarding_form",
    "notebook_onboarding_tour_started", "notebook_onboarding_tour_step",
    "notebook_onboarding_tour_finished",
    "fullscreen_open", "fullscreen_close",
    "notebook_view_canvas_toggle",
}
CREATED_EVENTS_V4 = {"block_create", "files_upload",
                     "agent_tool_call_create_block_tool"}
AI_EVENTS_V4 = {"$ai_generation", "agent_message", "agent_new_chat",
                "agent_start_from_prompt", "agent_worker_created"}
CODE_EVENTS_V4 = {"run_block", "run_all_blocks"}
INTEG_EVENTS_V4 = {
    "source_control_connect_to_canvas", "source_control_commit",
    "source_control_pull",
    "notebook_deployment_deployed",
    "notebook_deployment_preview_created",
    "notebook_deployment_updated",
}
ENGAGEMENT_EVENTS_V4 = AI_EVENTS_V4 | CODE_EVENTS_V4 | INTEG_EVENTS_V4
UPGRADE_EVENT_V4 = "subscription_upgraded"
DOWNGRADE_EVENTS_V4 = {"subscription_downgraded", "downgrade_subscription"}
CANCEL_EVENTS_V4 = {"subscription_cancelled", "cancel_subscription"}
TRIAL_EVENTS_V4 = {
    "promo_code_redeemed", "claim_free_offer_clicked",
    "work_email_bonus_credits_received", "referral_bonus_credits_received",
}
TOUR_FINISHED_V4 = "notebook_onboarding_tour_finished"
EXCEPTION_EVENT_V4 = "$exception"
NOTEBOOK_EVENTS_V4 = {"block_create", "run_block", "files_upload"}

ENGAGED_DAYS_V4 = 3
AT_RISK_DAYS_V4 = 14
AT_RISK_MIN_STAGE_V4 = 4
UPGRADE_INACTIVE_DAYS_V4 = 30
POWER_ENGAGED_DAYS_V4 = 7

STAGE_NAMES_V4 = {
    0: "0.NoEvent",
    1: "1.New", 2: "2.Exploring", 3: "3.Created", 4: "4.UsedAI",
    5: "5.WroteCode", 6: "6.Integrated", 7: "7.Engaged", 8: "8.Upgraded",
}

asof_ts_v4 = events["timestamp"].max()

# Per-user first ts of each stage event set
def _first_ts_v4(evset):
    return events.loc[events["event"].isin(evset)].groupby("person_id")["timestamp"].min()

t1_v4 = _first_ts_v4(NEW_EVENTS_V4)
t2_v4 = _first_ts_v4(EXPLORE_EVENTS_V4)
t3_v4 = _first_ts_v4(CREATED_EVENTS_V4)
t4_v4 = _first_ts_v4(AI_EVENTS_V4)
t5_v4 = _first_ts_v4(CODE_EVENTS_V4)
t6_v4 = _first_ts_v4(INTEG_EVENTS_V4)
t8_v4 = events.loc[events["event"] == UPGRADE_EVENT_V4].groupby("person_id")["timestamp"].min()

# 7.Engaged: first timestamp of the (engaged_days)th distinct engagement day
_eng_v4 = events.loc[events["event"].isin(ENGAGEMENT_EVENTS_V4),
                      ["person_id", "timestamp"]].copy()
_eng_v4["_date"] = _eng_v4["timestamp"].dt.date
_eng_v4 = _eng_v4.sort_values(["person_id", "timestamp"])
_first_per_date_v4 = _eng_v4.drop_duplicates(["person_id", "_date"], keep="first").sort_values(
    ["person_id", "timestamp"]
)
_first_per_date_v4["_day_idx"] = _first_per_date_v4.groupby("person_id").cumcount()
t7_v4 = _first_per_date_v4.loc[
    _first_per_date_v4["_day_idx"] == ENGAGED_DAYS_V4 - 1
].set_index("person_id")["timestamp"]

# Build per-user frame
all_users_v4 = pd.Index(events["person_id"].unique(), name="person_id")
last_ts_v4 = events.groupby("person_id")["timestamp"].max()

user_features_v4 = pd.DataFrame(index=all_users_v4)
user_features_v4["t1"] = t1_v4
user_features_v4["t2"] = t2_v4
user_features_v4["t3"] = t3_v4
user_features_v4["t4"] = t4_v4
user_features_v4["t5"] = t5_v4
user_features_v4["t6"] = t6_v4
user_features_v4["t7"] = t7_v4
user_features_v4["t8"] = t8_v4
user_features_v4["last_ts"] = last_ts_v4
user_features_v4["days_since_last"] = (
    asof_ts_v4 - user_features_v4["last_ts"]
).dt.total_seconds() / 86400

# Highest reached stage (max k where t_k notna)
user_features_v4["highest"] = 0
for _k in range(1, 9):
    user_features_v4.loc[user_features_v4[f"t{_k}"].notna(), "highest"] = _k
user_features_v4["upgraded"] = user_features_v4["t8"].notna()
user_features_v4.loc[user_features_v4["upgraded"], "highest"] = 8

# Post-upgrade events (downgrade / cancel after first upgrade ts)
_upgr_idx_v4 = user_features_v4.index[user_features_v4["upgraded"]]
if len(_upgr_idx_v4) > 0:
    _upg_first_v4 = user_features_v4.loc[_upgr_idx_v4, "t8"]
    _e_upgr_v4 = events.loc[events["person_id"].isin(_upgr_idx_v4)].copy()
    _e_upgr_v4["upg_ts"] = _e_upgr_v4["person_id"].map(_upg_first_v4)
    _e_post_v4 = _e_upgr_v4.loc[_e_upgr_v4["timestamp"] > _e_upgr_v4["upg_ts"]]
    _downgrade_users_v4 = set(
        _e_post_v4.loc[_e_post_v4["event"].isin(DOWNGRADE_EVENTS_V4), "person_id"].unique()
    )
    _cancel_users_v4 = set(
        _e_post_v4.loc[_e_post_v4["event"].isin(CANCEL_EVENTS_V4), "person_id"].unique()
    )
else:
    _downgrade_users_v4, _cancel_users_v4 = set(), set()

user_features_v4["downgraded"] = user_features_v4.index.isin(_downgrade_users_v4)
user_features_v4["cancelled"] = user_features_v4.index.isin(_cancel_users_v4)
user_features_v4["upg_inactive"] = (
    user_features_v4["upgraded"]
    & (user_features_v4["days_since_last"] >= UPGRADE_INACTIVE_DAYS_V4)
)
user_features_v4["churned_upg"] = user_features_v4["upgraded"] & (
    user_features_v4["cancelled"]
    | (user_features_v4["downgraded"] & user_features_v4["upg_inactive"])
)
user_features_v4["atrisk_upg"] = (
    user_features_v4["upgraded"]
    & user_features_v4["upg_inactive"]
    & ~user_features_v4["churned_upg"]
)

# AtRisk for non-upgraders
user_features_v4["at_risk"] = (
    (user_features_v4["highest"] >= AT_RISK_MIN_STAGE_V4)
    & (user_features_v4["highest"] < 8)
    & ~user_features_v4["upgraded"]
    & (user_features_v4["days_since_last"] >= AT_RISK_DAYS_V4)
)

# Compose final_stage label
user_features_v4["final_stage"] = user_features_v4["highest"].map(STAGE_NAMES_V4)
_ar_mask_v4 = user_features_v4["at_risk"]
user_features_v4.loc[_ar_mask_v4, "final_stage"] = (
    "9.AtRisk@" + user_features_v4.loc[_ar_mask_v4, "highest"]
                                .map(STAGE_NAMES_V4).str.split(".", n=1).str[1]
)
user_features_v4.loc[user_features_v4["upgraded"], "final_stage"] = "8.Upgraded"
user_features_v4.loc[user_features_v4["atrisk_upg"], "final_stage"] = "9.AtRisk@Upgraded"
user_features_v4.loc[user_features_v4["churned_upg"], "final_stage"] = "9.Churned@Upgraded"

# 7-column metadata
_tour_finished_v4 = set(
    events.loc[events["event"] == TOUR_FINISHED_V4, "person_id"].unique()
)
user_features_v4["onboarding_completed"] = user_features_v4.index.isin(_tour_finished_v4)

_promo_users_v4 = set(
    events.loc[events["event"].isin(TRIAL_EVENTS_V4), "person_id"].unique()
)
user_features_v4["used_promo"] = user_features_v4.index.isin(_promo_users_v4)

_first_ai_v4 = events.loc[events["event"].isin(AI_EVENTS_V4)].groupby(
    "person_id"
)["timestamp"].min()
_first_nb_v4 = events.loc[events["event"].isin(NOTEBOOK_EVENTS_V4)].groupby(
    "person_id"
)["timestamp"].min()
_FAR_V4 = pd.Timestamp.max.tz_localize("UTC")
_ai_first_aligned_v4 = _first_ai_v4.reindex(user_features_v4.index).fillna(_FAR_V4)
_nb_first_aligned_v4 = _first_nb_v4.reindex(user_features_v4.index).fillna(_FAR_V4)
user_features_v4["agent_first"] = (
    _first_ai_v4.reindex(user_features_v4.index).notna()
    & (_ai_first_aligned_v4 < _nb_first_aligned_v4)
)

# Reactivated: 14d+ gap then ≥5 events after
_es_v4 = events[["person_id", "timestamp"]].sort_values(["person_id", "timestamp"])
_es_v4["prev_ts"] = _es_v4.groupby("person_id")["timestamp"].shift(1)
_es_v4["gap_d"] = (_es_v4["timestamp"] - _es_v4["prev_ts"]).dt.total_seconds() / 86400
_es_v4["had_big_gap"] = (
    _es_v4.groupby("person_id")["gap_d"].cummax() >= 14
).astype(int)
_n_after_v4 = _es_v4.loc[_es_v4["had_big_gap"] == 1].groupby("person_id").size()
_react_users_v4 = set(_n_after_v4[_n_after_v4 >= 5].index)
user_features_v4["reactivated"] = user_features_v4.index.isin(_react_users_v4)

# exception_rate
_n_total_v4 = events.groupby("person_id").size()
_n_exc_v4 = events.loc[events["event"] == EXCEPTION_EVENT_V4].groupby("person_id").size()
user_features_v4["exception_rate"] = (_n_exc_v4 / _n_total_v4).reindex(
    user_features_v4.index, fill_value=0.0
)

# is_power_engaged
_eng_dates_v4 = (
    events.loc[events["event"].isin(ENGAGEMENT_EVENTS_V4)]
    .assign(_date=lambda d: d["timestamp"].dt.date)
    .drop_duplicates(["person_id", "_date"])
    .groupby("person_id").size()
)
user_features_v4["is_power_engaged"] = (
    _eng_dates_v4 >= POWER_ENGAGED_DAYS_V4
).reindex(user_features_v4.index, fill_value=False)

# Stage distribution table — used by the Visualize Funnel v4 block / UI export
stage_distribution_v4 = (
    user_features_v4["final_stage"].value_counts().rename_axis("stage").to_frame("users")
)
stage_distribution_v4["share_pct"] = (
    100.0 * stage_distribution_v4["users"] / len(user_features_v4)
).round(2)

print(f"v4 users classified         : {len(user_features_v4):,}")
print(f"v4 unique stages            : {user_features_v4['final_stage'].nunique()}")
print(f"v4 sanity (sum == users)    : {int(stage_distribution_v4['users'].sum())} == {len(user_features_v4)}")
print()
print("=== Final stage distribution (v4) ===")
print(stage_distribution_v4.to_string())
print()
print("=== Metadata flag prevalence ===")
for _c in ["onboarding_completed", "used_promo", "agent_first",
           "reactivated", "is_power_engaged"]:
    _frac = user_features_v4[_c].mean()
    print(f"  {_c:<22}  {_frac*100:>5.2f}%")
