

# Per-user "activity snapshot" pattern for upgrade prediction.
#
# Why this and not a calendar-date cutoff:
#   With a fixed-date cutoff (e.g. Mar 1), we can only label "users who were
#   already active before Mar 1." But upgrade events spike in Mar/Apr from
#   users who first signed up DURING that window — we'd lose ~90% of positives.
#   Per-user pivots align every user to the same "age" relative to their own
#   start, mirroring a real CS workflow.
#
# Why OBS_DAYS = 3, LABEL_DAYS = 60:
#   The data has a sharp time-to-upgrade distribution — 70.9% of upgraders
#   convert within 3 days, 75.9% within 7 days. Predicting "will user upgrade"
#   over the very early window is mostly trivial (those users came with intent).
#   The interesting and actionable question is: "of users who DIDN'T upgrade
#   in their first 3 days, who will in the next 60?" That's where CS / growth
#   teams can intervene. So OBS=3 (capture early intensity), LABEL=60 (60d is
#   long enough to catch ~78% of remaining upgraders without truncating too
#   many recent users from eligibility).
#
# Design:
#   For each user u with first event at t0(u):
#     observation_end(u) = t0(u) + OBS_DAYS
#     label_end(u)       = t0(u) + OBS_DAYS + LABEL_DAYS
#   Features: aggregations of events in [t0(u), observation_end(u))
#   Label:    did user upgrade in [observation_end(u), label_end(u))?
#
# Eligibility (so every user has a complete label window):
#   label_end(u) <= max(events.timestamp).
#   Users who already upgraded WITHIN the observation window are dropped (their
#   label is trivially yes and their features include the upgrade behavior).
#
# Leakage protection:
#   - Features only use events strictly before observation_end(u).
#   - Blacklisted events (those that fire on/around the upgrade itself) are
#     excluded from feature aggregation.
#
# Train/test = random stratified 80/20 split. Temporal protection is built in
# via the per-user windowing.

from datetime import timedelta
from sklearn.model_selection import train_test_split

OBS_DAYS     = 3
LABEL_DAYS   = 60
RANDOM_STATE = 42

DATA_END = events["timestamp"].max()

LEAKAGE_EVENTS = {
    # Direct upgrade/downgrade
    "subscription_upgraded",
    "subscription_downgraded",
    "subscription_cancelled",
    "upgrade_subscription",
    "downgrade_subscription",
    "cancel_subscription",
    "renew_plan",
    "open_cancel_plan_modal",
    # Click-to-pay intent
    "clicked_upgrade",
    "promo_code_redeemed",
    "redeem upgrade offer",
    "claim_free_offer_clicked",
    "watermark_remove_upgrade_clicked",
    "agent_resume_plan_button_clicked",
    "agent_cancel_plan_button_clicked",
    "seats_exceeded_share_resource_warning_clicked_upgrade",
    "ai_credit_banner_clicked",
    "team_plan_modal",
    "deployment_credit_limit_modal",
    # Wallet operations adjacent to upgrade
    "billing_info",
    "addon_credits_purchased",
    "add_credits",
    "clicked_add_credits",
    "agent_add_credits_button_clicked",
    "agent_add_on_credits_popup_opened",
    # Promotional credit grants (correlate w/ admin upgrade intent)
    "work_email_bonus_credits_received",
    "referral_bonus_credits_received",
    "referral_credits_awarded",
    "referral_upgrade_bonus_awarded",
    "commercial_credits_received",
}

CREATED_EVENTS       = {"agent_tool_call_create_block_tool", "run_block", "new_canvas_created", "block_create", "files_upload"}
AI_EVENTS            = {"$ai_generation", "agent_new_chat", "agent_worker_created", "agent_message"}
TOOL_CALL_PREFIX     = "agent_tool_call_"
CREDITS_BELOW_EVENTS = {"credits_below_1", "credits_below_2", "credits_below_3", "credits_below_4"}
DEPLOY_EVENTS        = {
    "notebook_deployment_deployed",
    "notebook_deployment_preview_created",
    "notebook_deployment_updated",
    "notebook_deployment_undeployed",
    "notebook_deployment_reset",
    "notebook_deployment_credits_exceeded",
    "notebook_deployment_usage_tracked",
    "notebook_deployment_automatic_preview_started",
    "notebook_deployment_preview_updated",
}
INTEG_SC_EVENTS      = {"source_control_connect_to_canvas", "source_control_commit", "source_control_pull"}


# ── Per-user start time
user_first_ts = events.groupby("person_id", sort=False, observed=True)["timestamp"].min()
user_first_ts.name = "first_ts"

# Eligible: users whose label window fits within observed data.
required_total_days = OBS_DAYS + LABEL_DAYS
eligible_users = user_first_ts[user_first_ts <= DATA_END - timedelta(days=required_total_days)].index

# Annotate each event row with the user's start time + relative days.
ev = events.merge(user_first_ts, how="left", left_on="person_id", right_index=True)
ev["days_from_start"] = (ev["timestamp"] - ev["first_ts"]).dt.total_seconds() / 86400

# Observation = events in [0, OBS_DAYS) for eligible users, excluding leakage events.
obs = ev[
    (ev["person_id"].isin(eligible_users)) &
    (ev["days_from_start"] >= 0) &
    (ev["days_from_start"] <  OBS_DAYS) &
    (~ev["event"].isin(LEAKAGE_EVENTS))
].copy()

# Boolean / date helpers (computed once).
obs["_date"]              = obs["timestamp"].dt.date
obs["_is_signin"]         = obs["event"].eq("sign_in")
obs["_is_ai"]             = obs["event"].isin(AI_EVENTS)
obs["_is_created"]        = obs["event"].isin(CREATED_EVENTS)
obs["_is_run_block"]      = obs["event"].eq("run_block")
obs["_is_credits_used"]   = obs["event"].eq("credits_used")
obs["_is_credits_below"]  = obs["event"].isin(CREDITS_BELOW_EVENTS)
obs["_is_credits_excd"]   = obs["event"].eq("credits_exceeded")
obs["_is_exception"]      = obs["event"].eq("$exception")
obs["_is_pageview"]       = obs["event"].eq("$pageview")
obs["_is_addon"]          = obs["event"].eq("addon_credits_used")
obs["_is_tool_call"]      = obs["event"].astype(str).str.startswith(TOOL_CALL_PREFIX)
obs["_is_deploy"]         = obs["event"].isin(DEPLOY_EVENTS)
obs["_is_integ_sc"]       = obs["event"].isin(INTEG_SC_EVENTS)
obs["_is_canvas_clone"]   = obs["event"].eq("canvas_clone")
obs["_is_files_upload"]   = obs["event"].eq("files_upload")
obs["_is_agent_msg"]      = obs["event"].eq("agent_message")
obs["_is_banner_shown"]   = obs["event"].eq("ai_credit_banner_shown")


def _agg(df, suffix):
    if len(df) == 0:
        return pd.DataFrame()
    g = df.groupby("person_id", sort=False, observed=True)
    out = g.agg(
        n_events         =("event",            "size"),
        n_distinct_days  =("_date",            "nunique"),
        n_distinct_evts  =("event",            "nunique"),
        n_signins        =("_is_signin",       "sum"),
        n_ai             =("_is_ai",           "sum"),
        n_created        =("_is_created",      "sum"),
        n_run_block      =("_is_run_block",    "sum"),
        n_credits_used   =("_is_credits_used", "sum"),
        n_credits_below  =("_is_credits_below","sum"),
        n_credits_excd   =("_is_credits_excd", "sum"),
        n_exception      =("_is_exception",    "sum"),
        n_pageview       =("_is_pageview",     "sum"),
        n_addon          =("_is_addon",        "sum"),
        n_tool_call      =("_is_tool_call",    "sum"),
        n_deploy         =("_is_deploy",       "sum"),
        n_integ_sc       =("_is_integ_sc",     "sum"),
        n_canvas_clone   =("_is_canvas_clone", "sum"),
        n_files_upload   =("_is_files_upload", "sum"),
        n_agent_msg      =("_is_agent_msg",    "sum"),
        n_banner_shown   =("_is_banner_shown", "sum"),
        first_ts         =("timestamp",        "min"),
        last_ts          =("timestamp",        "max"),
    )
    # Tempo / quality features
    span_sec = (out["last_ts"] - out["first_ts"]).dt.total_seconds()
    out["session_minutes"]         = span_sec / 60.0
    out["mean_event_interval_sec"] = span_sec / out["n_events"].clip(lower=1)
    out["exception_rate"]          = out["n_exception"] / out["n_events"].clip(lower=1)
    out["events_per_day"]          = out["n_events"] / out["n_distinct_days"].clip(lower=1)
    # Binary engagement flags (mission1 "did_*" semantic)
    out["did_run_block"]      = (out["n_run_block"]    > 0).astype(int)
    out["did_use_agent"]      = (out["n_agent_msg"]    > 0).astype(int)
    out["did_deploy"]         = (out["n_deploy"]       > 0).astype(int)
    out["did_files_upload"]   = (out["n_files_upload"] > 0).astype(int)
    out["did_source_control"] = (out["n_integ_sc"]     > 0).astype(int)
    out["did_hit_credit_lim"] = (out["n_credits_excd"] > 0).astype(int)
    out["did_canvas_clone"]   = (out["n_canvas_clone"] > 0).astype(int)
    out["did_see_banner"]     = (out["n_banner_shown"] > 0).astype(int)
    out = out.drop(columns=["first_ts", "last_ts"])
    return out.add_suffix(f"_{suffix}")


obs_agg = _agg(obs, "obs")

# Day-1 vs full-obs split lets the model see "early intensity" patterns.
obs_day0 = obs[obs["days_from_start"] < 1.0]
day0_agg = _agg(obs_day0, "day0")

# Activity hour (UTC) — pattern of when users come in
hour_summary = obs.groupby("person_id", sort=False, observed=True).agg(
    activity_hour_min =("timestamp", lambda x: x.dt.hour.min()),
    activity_hour_max =("timestamp", lambda x: x.dt.hour.max()),
    activity_hour_mean=("timestamp", lambda x: x.dt.hour.mean()),
)

# Full feature matrix indexed by eligible users.
X_full = (
    obs_agg
    .join(day0_agg,     how="left")
    .join(hour_summary, how="left")
    .reindex(eligible_users, fill_value=0)
    .fillna(0)
)
X_full.index.name = "person_id"

# ── Filter out users who upgraded WITHIN their observation window. Their label
#    is structurally yes but their features are post-decision — both useless
#    and leakage-prone.
upgrade_rows = ev[ev["event"] == "subscription_upgraded"]
upgrade_rows = upgrade_rows[upgrade_rows["person_id"].isin(eligible_users)]
upgraded_in_obs = upgrade_rows[upgrade_rows["days_from_start"] < OBS_DAYS]["person_id"].unique()

# Label: upgraded in [OBS_DAYS, OBS_DAYS + LABEL_DAYS).
label_rows = upgrade_rows[
    (upgrade_rows["days_from_start"] >= OBS_DAYS) &
    (upgrade_rows["days_from_start"] <  OBS_DAYS + LABEL_DAYS)
]
upgraded_in_label = pd.Index(label_rows["person_id"].unique())

X_full = X_full.drop(index=upgraded_in_obs, errors="ignore")
y_full = pd.Series(X_full.index.isin(upgraded_in_label).astype(int), index=X_full.index, name="upgraded")

# ── 80/20 stratified split.
X_train, X_test, y_train, y_test = train_test_split(
    X_full, y_full,
    test_size=0.20,
    random_state=RANDOM_STATE,
    stratify=y_full,
)

feature_cols = list(X_full.columns)

print(f"data span             : {events['timestamp'].min().date()} → {DATA_END.date()}")
print(f"observation window    : first {OBS_DAYS} days from each user's first event")
print(f"label window          : days [{OBS_DAYS}, {OBS_DAYS + LABEL_DAYS}) from first event")
print(f"required to qualify   : first event ≤ {(DATA_END - timedelta(days=required_total_days)).date()}")
print()
print(f"eligible users        : {len(eligible_users):,}")
print(f"dropped (upgraded in obs window) : {len(upgraded_in_obs):,}")
print(f"final candidates      : {len(X_full):,}")
print(f"positives total       : {int(y_full.sum())} ({100 * y_full.mean():.2f}%)")
print()
print(f"train: {X_train.shape}  positives={int(y_train.sum())}  ({100 * y_train.mean():.2f}%)")
print(f"test : {X_test.shape}   positives={int(y_test.sum())}  ({100 * y_test.mean():.2f}%)")
print(f"feature count         : {len(feature_cols)}")
