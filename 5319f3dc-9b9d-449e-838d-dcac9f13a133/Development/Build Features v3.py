# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false


# Build Features v3 — leakage-safe per-user feature matrix with cumulative
# time windows and a time-based cohort split.
#
# Differences vs the team's "Build Features" block:
#   v1 ("Build Features") uses OBS=3d / LABEL=60d snapshot per user, drops
#   users who upgraded within their first 3 days (~70% of upgraders), 80/20
#   stratified random split. End result: 31 positives total, 6-7 in test.
#
#   v3 (this block) keeps every upgrader. We apply a per-user cutoff:
#     - upgrader:    cutoff = first subscription_upgraded ts - 1us
#     - non-upgrader: cutoff = data_end + 1us
#   Then aggregate at 4 cumulative windows: 1h, 24h, 7d, full(pre-cutoff).
#   Train/test = time-based cohort split: cohort 2025-09 to 2026-02 => train,
#   2026-03 to 2026-04 => test. ~138 train pos / ~185 test pos (30x more
#   statistical power for evaluation than v1).
#
# We re-load the CSV with extra columns here because "Example Dataset" is a
# 3-column slim load. Adding role/purpose/work_type/source/device/os/country
# brings demographic signals in. ~5s extra wall time.
#
# Outputs (consumed by Train Model v3):
#   X_v3_train, X_v3_test         pandas dataframes (numeric, fillna(0))
#   y_v3_train, y_v3_test         binary labels
#   feature_cols_v3, base_rate_v3, train_index_v3, test_index_v3
#   X_v3_full                     full matrix incl. cohort_month + label

from datetime import timedelta
import numpy as np

V3_CSV_PATH = "zerve_events.csv"

# Event sets (mirror Funnel v4 / mission1_features.py for consistency)
NEW_EVENTS_V3       = {"new_user_created", "sign_up"}
EXPLORE_EVENTS_V3   = {
    "$pageview", "$autocapture",
    "submit_onboarding_form", "skip_onboarding_form",
    "notebook_onboarding_tour_started", "notebook_onboarding_tour_step",
    "notebook_onboarding_tour_finished",
    "fullscreen_open", "fullscreen_close",
    "notebook_view_canvas_toggle",
}
CREATED_EVENTS_V3   = {"block_create", "files_upload", "agent_tool_call_create_block_tool"}
AI_EVENTS_V3        = {"$ai_generation", "agent_message", "agent_new_chat",
                        "agent_start_from_prompt", "agent_worker_created"}
CODE_EVENTS_V3      = {"run_block", "run_all_blocks"}
INTEG_SC_EVENTS_V3  = {"source_control_connect_to_canvas",
                        "source_control_commit", "source_control_pull"}
DEPLOY_EVENTS_V3    = {
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

UPGRADE_EVENT_V3 = "subscription_upgraded"
TOUR_FINISHED_V3 = "notebook_onboarding_tour_finished"
EXCEPTION_EVENT_V3 = "$exception"
AGENT_TOOL_PREFIX_V3 = "agent_tool_call_"

LEAK_EVENTS_V3 = {
    "subscription_upgraded",
    "upgrade_subscription", "clicked_upgrade",
    "billing_info",
    "addon_credits_purchased",
    "add_credits", "clicked_add_credits",
    "agent_add_credits_button_clicked", "agent_add_on_credits_popup_opened",
    "claim_free_offer_clicked", "promo_code_redeemed",
    "team_plan_modal", "agent_resume_plan_button_clicked",
    "watermark_remove_upgrade_clicked",
    "seats_exceeded_share_resource_warning_clicked_upgrade",
    "subscription_downgraded", "downgrade_subscription",
    "subscription_cancelled", "cancel_subscription",
    "open_cancel_plan_modal", "renew_plan",
    "ai_credit_banner_clicked",
    "work_email_bonus_credits_received",
    "referral_bonus_credits_received",
    "referral_credits_awarded", "commercial_credits_received",
    "referral_upgrade_bonus_awarded", "deployment_credit_limit_modal",
    "agent_cancel_plan_button_clicked",
}

# ── Reload events with demographic columns
print("[v3] Reloading events with demographic columns...")
_ev_v3 = pd.read_csv(
    V3_CSV_PATH,
    usecols=["person_id", "timestamp", "event",
             "person_properties.purpose", "person_properties.role",
             "person_properties.work_type", "person_properties.source",
             "properties.$device_type", "properties.$os",
             "properties.$geoip_country_name"],
    engine="pyarrow",
)
_ev_v3["timestamp"] = pd.to_datetime(_ev_v3["timestamp"], utc=True, format="ISO8601")
_ev_v3.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
DATA_END_V3 = _ev_v3["timestamp"].max()
print(f"[v3] events rows={len(_ev_v3):,}  users={_ev_v3['person_id'].nunique():,}")

# ── Per-user cutoff
_user_first_v3 = _ev_v3.groupby("person_id")["timestamp"].min()
_user_last_v3 = _ev_v3.groupby("person_id")["timestamp"].max()
_upg_ts_v3 = _ev_v3.loc[_ev_v3["event"] == UPGRADE_EVENT_V3].groupby("person_id")["timestamp"].min()

_ONE_US_V3 = pd.Timedelta(microseconds=1)
_cutoff_v3 = pd.Series(DATA_END_V3 + _ONE_US_V3, index=_user_first_v3.index)
_cutoff_v3.update(_upg_ts_v3 - _ONE_US_V3)

# y label
y_v3_full_series = pd.Series(0, index=_user_first_v3.index, name="upgraded")
y_v3_full_series.update(pd.Series(1, index=_upg_ts_v3.index))

# Filter to pre-cutoff + drop leakage events
_ev_v3["first_event_ts"] = _ev_v3["person_id"].map(_user_first_v3)
_ev_v3["cutoff_ts"] = _ev_v3["person_id"].map(_cutoff_v3)
_ev_v3["sec_since_first"] = (
    _ev_v3["timestamp"] - _ev_v3["first_event_ts"]
).dt.total_seconds()

_clean_v3 = _ev_v3.loc[~_ev_v3["event"].isin(LEAK_EVENTS_V3)].copy()
_clean_v3 = _clean_v3.loc[_clean_v3["timestamp"] <= _clean_v3["cutoff_ts"]]
print(f"[v3] events after leak removal + cutoff: {len(_clean_v3):,}")

# Boolean flag columns for fast aggregation
_ev_col_v3 = _clean_v3["event"]
_clean_v3["is_pageview"]      = _ev_col_v3.eq("$pageview")
_clean_v3["is_autocapture"]   = _ev_col_v3.eq("$autocapture")
_clean_v3["is_exception"]     = _ev_col_v3.eq(EXCEPTION_EVENT_V3)
_clean_v3["is_explore"]       = _ev_col_v3.isin(EXPLORE_EVENTS_V3)
_clean_v3["is_create"]        = _ev_col_v3.isin(CREATED_EVENTS_V3)
_clean_v3["is_ai"]            = _ev_col_v3.isin(AI_EVENTS_V3)
_clean_v3["is_code"]          = _ev_col_v3.isin(CODE_EVENTS_V3)
_clean_v3["is_integ_sc"]      = _ev_col_v3.isin(INTEG_SC_EVENTS_V3)
_clean_v3["is_deploy"]        = _ev_col_v3.isin(DEPLOY_EVENTS_V3)
_clean_v3["is_block_create"]  = _ev_col_v3.eq("block_create")
_clean_v3["is_run_block"]     = _ev_col_v3.eq("run_block")
_clean_v3["is_run_all"]       = _ev_col_v3.eq("run_all_blocks")
_clean_v3["is_files_upload"]  = _ev_col_v3.eq("files_upload")
_clean_v3["is_canvas_clone"]  = _ev_col_v3.eq("canvas_clone")
_clean_v3["is_agent_msg"]     = _ev_col_v3.eq("agent_message")
_clean_v3["is_agent_new"]     = _ev_col_v3.eq("agent_new_chat")
_clean_v3["is_agent_tool"]    = _ev_col_v3.str.startswith(AGENT_TOOL_PREFIX_V3, na=False)
_clean_v3["is_credits_used"]  = _ev_col_v3.eq("credits_used")
_clean_v3["is_credits_excd"]  = _ev_col_v3.eq("credits_exceeded")
_clean_v3["is_credits_below"] = _ev_col_v3.isin({"credits_below_1", "credits_below_2",
                                                   "credits_below_3", "credits_below_4"})
_clean_v3["is_banner_shown"]  = _ev_col_v3.eq("ai_credit_banner_shown")
_clean_v3["is_tour_finish"]   = _ev_col_v3.eq(TOUR_FINISHED_V3)
_clean_v3["is_submit_form"]   = _ev_col_v3.eq("submit_onboarding_form")
_clean_v3["_date"]            = _clean_v3["timestamp"].dt.date

WINDOWS_V3 = {"1h": 3600, "24h": 86400, "7d": 7 * 86400, "full": float("inf")}


def _agg_window_v3(sub, suffix):
    if len(sub) == 0:
        return pd.DataFrame()
    g = sub.groupby("person_id", sort=False)
    out = g.agg(
        n_events=("event", "size"),
        n_distinct_event_types=("event", "nunique"),
        n_distinct_days=("_date", "nunique"),
        n_pageview=("is_pageview", "sum"),
        n_autocapture=("is_autocapture", "sum"),
        n_exception=("is_exception", "sum"),
        n_explore=("is_explore", "sum"),
        n_create=("is_create", "sum"),
        n_ai=("is_ai", "sum"),
        n_code=("is_code", "sum"),
        n_integ_sc=("is_integ_sc", "sum"),
        n_deploy=("is_deploy", "sum"),
        n_block_create=("is_block_create", "sum"),
        n_run_block=("is_run_block", "sum"),
        n_run_all=("is_run_all", "sum"),
        n_files_upload=("is_files_upload", "sum"),
        n_canvas_clone=("is_canvas_clone", "sum"),
        n_agent_msg=("is_agent_msg", "sum"),
        n_agent_new=("is_agent_new", "sum"),
        n_agent_tool=("is_agent_tool", "sum"),
        n_credits_used=("is_credits_used", "sum"),
        n_credits_exceeded=("is_credits_excd", "sum"),
        n_credits_below=("is_credits_below", "sum"),
        n_banner_shown=("is_banner_shown", "sum"),
        first_ts=("timestamp", "min"),
        last_ts=("timestamp", "max"),
        any_tour_finish=("is_tour_finish", "max"),
        any_submit_form=("is_submit_form", "max"),
    )
    out["session_minutes"] = (out["last_ts"] - out["first_ts"]).dt.total_seconds() / 60
    out["mean_event_interval_sec"] = (
        (out["last_ts"] - out["first_ts"]).dt.total_seconds()
        / out["n_events"].clip(lower=1)
    )
    out["exception_rate"] = out["n_exception"] / out["n_events"].clip(lower=1)
    out["events_per_day"] = out["n_events"] / out["n_distinct_days"].clip(lower=1)
    out["did_run_block"]      = (out["n_run_block"] > 0).astype(int)
    out["did_use_agent"]      = (out["n_agent_msg"] > 0).astype(int)
    out["did_deploy"]         = (out["n_deploy"] > 0).astype(int)
    out["did_files_upload"]   = (out["n_files_upload"] > 0).astype(int)
    out["did_source_control"] = (out["n_integ_sc"] > 0).astype(int)
    out["did_hit_credit_limit"] = (out["n_credits_exceeded"] > 0).astype(int)
    out["did_see_banner"]     = (out["n_banner_shown"] > 0).astype(int)
    out["did_canvas_clone"]   = (out["n_canvas_clone"] > 0).astype(int)
    out = out.drop(columns=["first_ts", "last_ts"])
    out["any_tour_finish"] = out["any_tour_finish"].astype(int)
    out["any_submit_form"] = out["any_submit_form"].astype(int)
    return out.add_suffix(f"_{suffix}")


print("[v3] Aggregating window features...")
_window_blocks_v3 = []
for _name, _sec in WINDOWS_V3.items():
    if _sec == float("inf"):
        _sub_v3 = _clean_v3
    else:
        _sub_v3 = _clean_v3.loc[_clean_v3["sec_since_first"] <= _sec]
    _f_v3 = _agg_window_v3(_sub_v3, _name)
    _window_blocks_v3.append(_f_v3)
    print(f"  window={_name:<5}  rows={len(_sub_v3):>10,}  feats={len(_f_v3.columns)}")

X_v3_full = pd.concat(_window_blocks_v3, axis=1).fillna(0)

# Time-to-X features (in pre-cutoff history)
def _first_offset_v3(evset, name):
    sub = _clean_v3.loc[_clean_v3["event"].isin(evset)]
    first = sub.groupby("person_id")["timestamp"].min()
    delta_h = (first - _user_first_v3).dt.total_seconds() / 3600
    return delta_h.rename(f"hours_to_first_{name}")

X_v3_full = X_v3_full.join(_first_offset_v3(AI_EVENTS_V3, "ai"))
X_v3_full = X_v3_full.join(_first_offset_v3({"block_create"}, "block_create"))
X_v3_full = X_v3_full.join(_first_offset_v3({"run_block"}, "run_block"))
X_v3_full = X_v3_full.join(_first_offset_v3(DEPLOY_EVENTS_V3, "deploy"))
X_v3_full = X_v3_full.join(_first_offset_v3(INTEG_SC_EVENTS_V3, "source_control"))
X_v3_full = X_v3_full.join(
    _first_offset_v3({"credits_exceeded", "credits_below_1", "credits_below_2",
                       "credits_below_3", "credits_below_4",
                       "ai_credit_banner_shown"}, "trigger")
)

# v4 metadata-derived features
_first_ai_v3 = _clean_v3.loc[_clean_v3["is_ai"]].groupby("person_id")["timestamp"].min()
_NB_SET_V3 = {"block_create", "run_block", "files_upload"}
_first_nb_v3 = _clean_v3.loc[_clean_v3["event"].isin(_NB_SET_V3)].groupby("person_id")["timestamp"].min()
_FAR_V3 = pd.Timestamp.max.tz_localize("UTC")
_ai_a_v3 = _first_ai_v3.reindex(X_v3_full.index).fillna(_FAR_V3)
_nb_a_v3 = _first_nb_v3.reindex(X_v3_full.index).fillna(_FAR_V3)
X_v3_full["agent_first"] = (
    _first_ai_v3.reindex(X_v3_full.index).notna() & (_ai_a_v3 < _nb_a_v3)
).astype(int)

_eng_dates_v3 = (
    _clean_v3.loc[_clean_v3["event"].isin(AI_EVENTS_V3 | CODE_EVENTS_V3
                                            | INTEG_SC_EVENTS_V3 | DEPLOY_EVENTS_V3)]
    .drop_duplicates(["person_id", "_date"])
    .groupby("person_id").size()
)
X_v3_full["is_power_engaged"] = (
    _eng_dates_v3 >= 7
).reindex(X_v3_full.index, fill_value=False).astype(int)

# Static signup attributes (one-hot top values)
def _mode_per_user_v3(col):
    sub = _ev_v3.dropna(subset=[col])[["person_id", col]]
    return sub.groupby("person_id")[col].agg(
        lambda s: s.mode().iloc[0] if len(s.mode()) else None
    )

for _col, _name in [
    ("person_properties.purpose",      "purpose"),
    ("person_properties.role",         "role"),
    ("person_properties.work_type",    "work_type"),
    ("person_properties.source",       "signup_source"),
    ("properties.$device_type",        "device_type"),
    ("properties.$os",                 "os"),
    ("properties.$geoip_country_name", "country"),
]:
    _s_v3 = _mode_per_user_v3(_col).reindex(X_v3_full.index)
    if _name == "country":
        _top10 = _s_v3.value_counts().head(10).index
        _s_v3 = _s_v3.where(_s_v3.isin(_top10), "Other").fillna("Unknown")
    elif _name in ("os", "device_type"):
        _s_v3 = _s_v3.fillna("Unknown")
    _dummies_v3 = pd.get_dummies(_s_v3.fillna("(missing)"), prefix=_name, dummy_na=False).astype(int)
    X_v3_full = pd.concat([X_v3_full, _dummies_v3], axis=1)

# Cohort + label
X_v3_full["first_event_ts"] = _user_first_v3.reindex(X_v3_full.index)
X_v3_full["cohort_month"] = X_v3_full["first_event_ts"].dt.tz_convert(None).dt.to_period("M").astype(str)
X_v3_full["upgraded"] = y_v3_full_series.reindex(X_v3_full.index, fill_value=0).astype(int)

# ── Time-based cohort split: Sep–Feb -> train, Mar–Apr -> test
TRAIN_END_V3 = "2026-03"
_train_mask_v3 = X_v3_full["cohort_month"] < TRAIN_END_V3
_test_mask_v3 = ~_train_mask_v3

# Drop leakage / metadata cols from X
_drop_from_x_v3 = ["upgraded", "first_event_ts", "cohort_month"]
# observation_days would be derivable from cutoff length (leak: shorter for upgraders)
_observation_days_v3 = (_cutoff_v3 - _user_first_v3).dt.total_seconds() / 86400
# We do not include it in X_v3.

feature_cols_v3 = [c for c in X_v3_full.columns if c not in _drop_from_x_v3
                    and not c.endswith("_full")]
# Drop _full window columns (cutoff-length dependent — same leak family).

X_v3_train = X_v3_full.loc[_train_mask_v3, feature_cols_v3].replace(
    [np.inf, -np.inf], np.nan
).fillna(0.0)
X_v3_test = X_v3_full.loc[_test_mask_v3, feature_cols_v3].replace(
    [np.inf, -np.inf], np.nan
).fillna(0.0)
y_v3_train = X_v3_full.loc[_train_mask_v3, "upgraded"].values
y_v3_test = X_v3_full.loc[_test_mask_v3, "upgraded"].values
train_index_v3 = X_v3_train.index
test_index_v3 = X_v3_test.index

base_rate_v3 = float(np.mean(y_v3_test))

print(f"[v3] feature matrix         : {X_v3_full.shape[0]:,} users x {len(feature_cols_v3)} feats (after dropping _full)")
print(f"[v3] train: {X_v3_train.shape}  positives={int(y_v3_train.sum())}  ({100*y_v3_train.mean():.2f}%)")
print(f"[v3] test : {X_v3_test.shape}  positives={int(y_v3_test.sum())}  ({100*base_rate_v3:.2f}%)")
print()
print("[v3] cohort distribution:")
print(X_v3_full.groupby("cohort_month").agg(
    users=("upgraded", "size"), upgraders=("upgraded", "sum"),
).to_string())
