"""
Mission 1 — Feature Engineering (leakage-safe, time-windowed)

산출물:
  feature_matrix.parquet  — per-user feature row + label + cohort 정보
  feature_columns.txt     — 컬럼 카탈로그 (debug)

설계 원칙:
  1. 사용자별 cutoff 적용 (upgrader: upgrade_ts - 1us, others: data_end + 1us)
  2. 4개 누적 윈도우: 1h / 24h / 7d / full(pre-cutoff)
  3. leakage 후보 이벤트 25개 명시 제외 (단, credit_exceeded/credits_below/banner_shown은 trigger로 보존)
  4. 시간 기반 cohort 분할용 컬럼 보존 (first_event_ts, first_event_month)
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import time

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

# ──────────────────────────────────────────────────────────────────
# 이벤트 set 정의 (v4와 동일 + 추가)
# ──────────────────────────────────────────────────────────────────
NEW_EVENTS = {"new_user_created", "sign_up"}
EXPLORE_EVENTS = {
    "$pageview", "$autocapture",
    "submit_onboarding_form", "skip_onboarding_form",
    "notebook_onboarding_tour_started", "notebook_onboarding_tour_step",
    "notebook_onboarding_tour_finished",
    "fullscreen_open", "fullscreen_close",
    "notebook_view_canvas_toggle",
}
CREATED_EVENTS = {"block_create", "files_upload", "agent_tool_call_create_block_tool"}
AI_EVENTS = {"$ai_generation", "agent_message", "agent_new_chat",
             "agent_start_from_prompt", "agent_worker_created"}
CODE_EVENTS = {"run_block", "run_all_blocks"}
INTEG_EVENTS = {"source_control_connect_to_canvas", "source_control_commit",
                "source_control_pull"}
DEPLOY_EVENTS = {"notebook_deployment_deployed",
                 "notebook_deployment_preview_created",
                 "notebook_deployment_updated",
                 "notebook_deployment_undeployed",
                 "notebook_deployment_reset",
                 "notebook_deployment_credits_exceeded",
                 "notebook_deployment_usage_tracked",
                 "notebook_deployment_automatic_preview_started",
                 "notebook_deployment_preview_updated"}

UPGRADE_EVENT = "subscription_upgraded"
TOUR_FINISHED = "notebook_onboarding_tour_finished"
EXCEPTION_EVENT = "$exception"

# leakage 후보 (모델 input 절대 금지)
LEAK_EVENTS = {
    "subscription_upgraded",  # target 자체
    "upgrade_subscription", "clicked_upgrade",
    "billing_info",
    "addon_credits_purchased",
    "add_credits", "clicked_add_credits",
    "agent_add_credits_button_clicked",
    "agent_add_on_credits_popup_opened",
    "claim_free_offer_clicked", "promo_code_redeemed",
    "team_plan_modal", "agent_resume_plan_button_clicked",
    "watermark_remove_upgrade_clicked",
    "seats_exceeded_share_resource_warning_clicked_upgrade",
    "subscription_downgraded", "downgrade_subscription",
    "subscription_cancelled", "cancel_subscription",
    "open_cancel_plan_modal",
    "renew_plan",
    "ai_credit_banner_clicked",  # 클릭은 결제 의도 → leakage
    "work_email_bonus_credits_received",
    "referral_bonus_credits_received",
    "referral_credits_awarded", "commercial_credits_received",
    "referral_upgrade_bonus_awarded", "deployment_credit_limit_modal",
    "agent_cancel_plan_button_clicked",
}

# trigger signals (clean — 결제 trigger지만 결제 자체 아님)
TRIGGER_EVENTS = {"credits_exceeded", "credits_below_1", "credits_below_2",
                   "credits_below_3", "credits_below_4",
                   "ai_credit_banner_shown"}

# Coder Agent tool calls
AGENT_TOOL_PREFIX = "agent_tool_call_"

print("[1] Loading events with extended columns...", flush=True)
t0 = time.time()
events = pd.read_csv(
    CSV,
    usecols=["person_id", "timestamp", "event",
             "person_properties.purpose", "person_properties.role",
             "person_properties.work_type", "person_properties.source",
             "properties.$device_type", "properties.$os",
             "properties.$geoip_country_name"],
    engine="pyarrow",
)
events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
DATA_END = events["timestamp"].max()
N_USERS = events["person_id"].nunique()
print(f"    rows={len(events):,}  users={N_USERS:,}  load={time.time()-t0:.1f}s")

# ──────────────────────────────────────────────────────────────────
# 사용자별 first_event, upgrade_ts, cutoff_ts 계산
# ──────────────────────────────────────────────────────────────────
print("\n[2] Computing per-user cutoffs...", flush=True)
t0 = time.time()
user_first = events.groupby("person_id")["timestamp"].min()
user_last = events.groupby("person_id")["timestamp"].max()

upgrade_ts = events.loc[events["event"] == UPGRADE_EVENT].groupby("person_id")["timestamp"].min()
print(f"    upgraders: {len(upgrade_ts):,}")

# cutoff: upgrader = upgrade_ts - 1us, others = DATA_END + 1us
ONE_US = pd.Timedelta(microseconds=1)
cutoff = pd.Series(DATA_END + ONE_US, index=user_first.index)
cutoff.update(upgrade_ts - ONE_US)

# y label
y = pd.Series(0, index=user_first.index, name="upgraded")
y.update(pd.Series(1, index=upgrade_ts.index))
print(f"    label dist: positive={int(y.sum())}, negative={int((y==0).sum())}, "
      f"rate={y.mean()*100:.2f}%")

# events에 first_event_ts, cutoff_ts 매핑
events["first_event_ts"] = events["person_id"].map(user_first)
events["cutoff_ts"] = events["person_id"].map(cutoff)
events["sec_since_first"] = (events["timestamp"] - events["first_event_ts"]).dt.total_seconds()

# leakage events 통째로 제외
events_clean = events.loc[~events["event"].isin(LEAK_EVENTS)].copy()
# pre-cutoff만
events_clean = events_clean.loc[events_clean["timestamp"] <= events_clean["cutoff_ts"]]
print(f"    events after leak removal + cutoff: {len(events_clean):,} "
      f"(from {len(events):,})")
print(f"    cutoff prep: {time.time()-t0:.1f}s")

# ──────────────────────────────────────────────────────────────────
# Boolean flag 컬럼 (벡터화 위해 미리 계산)
# ──────────────────────────────────────────────────────────────────
print("\n[3] Adding boolean flags...", flush=True)
ev = events_clean["event"]
events_clean["is_pageview"] = ev.eq("$pageview")
events_clean["is_autocapture"] = ev.eq("$autocapture")
events_clean["is_exception"] = ev.eq(EXCEPTION_EVENT)
events_clean["is_explore"] = ev.isin(EXPLORE_EVENTS)
events_clean["is_create"] = ev.isin(CREATED_EVENTS)
events_clean["is_ai"] = ev.isin(AI_EVENTS)
events_clean["is_code"] = ev.isin(CODE_EVENTS)
events_clean["is_integ_sc"] = ev.isin(INTEG_EVENTS)
events_clean["is_deploy"] = ev.isin(DEPLOY_EVENTS)
events_clean["is_block_create"] = ev.eq("block_create")
events_clean["is_run_block"] = ev.eq("run_block")
events_clean["is_run_all"] = ev.eq("run_all_blocks")
events_clean["is_files_upload"] = ev.eq("files_upload")
events_clean["is_canvas_clone"] = ev.eq("canvas_clone")
events_clean["is_agent_msg"] = ev.eq("agent_message")
events_clean["is_agent_new"] = ev.eq("agent_new_chat")
events_clean["is_agent_tool"] = ev.str.startswith(AGENT_TOOL_PREFIX, na=False)
events_clean["is_credits_used"] = ev.eq("credits_used")
events_clean["is_credits_exceeded"] = ev.eq("credits_exceeded")
events_clean["is_credits_below"] = ev.isin({"credits_below_1", "credits_below_2",
                                               "credits_below_3", "credits_below_4"})
events_clean["is_banner_shown"] = ev.eq("ai_credit_banner_shown")
events_clean["is_trigger"] = ev.isin(TRIGGER_EVENTS)
events_clean["is_tour_finished"] = ev.eq(TOUR_FINISHED)
events_clean["is_submit_form"] = ev.eq("submit_onboarding_form")
events_clean["date"] = events_clean["timestamp"].dt.date

# ──────────────────────────────────────────────────────────────────
# 윈도우별 feature 계산
# ──────────────────────────────────────────────────────────────────
print("\n[4] Computing features per window...", flush=True)

WINDOWS = {
    "1h":   3600,
    "24h":  86400,
    "7d":   7 * 86400,
    "full": float("inf"),
}

def compute_window_features(ev_sub: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """벡터화 윈도우 feature 집계."""
    if len(ev_sub) == 0:
        return pd.DataFrame()
    grp = ev_sub.groupby("person_id", sort=False)
    feats = grp.agg(
        n_events=("event", "size"),
        n_distinct_event_types=("event", "nunique"),
        n_distinct_days=("date", "nunique"),
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
        n_credits_exceeded=("is_credits_exceeded", "sum"),
        n_credits_below=("is_credits_below", "sum"),
        n_banner_shown=("is_banner_shown", "sum"),
        n_trigger=("is_trigger", "sum"),
        first_ts=("timestamp", "min"),
        last_ts=("timestamp", "max"),
        any_tour_finish=("is_tour_finished", "max"),
        any_submit_form=("is_submit_form", "max"),
    )
    # 파생
    feats["session_minutes"] = (feats["last_ts"] - feats["first_ts"]).dt.total_seconds() / 60
    feats["mean_event_interval_sec"] = (
        (feats["last_ts"] - feats["first_ts"]).dt.total_seconds() /
        feats["n_events"].clip(lower=1)
    )
    feats["exception_rate"] = feats["n_exception"] / feats["n_events"].clip(lower=1)
    feats["events_per_day"] = feats["n_events"] / feats["n_distinct_days"].clip(lower=1)
    # binary
    feats["did_run_block"] = (feats["n_run_block"] > 0).astype(int)
    feats["did_use_agent"] = (feats["n_agent_msg"] > 0).astype(int)
    feats["did_deploy"] = (feats["n_deploy"] > 0).astype(int)
    feats["did_files_upload"] = (feats["n_files_upload"] > 0).astype(int)
    feats["did_source_control"] = (feats["n_integ_sc"] > 0).astype(int)
    feats["did_hit_credit_limit"] = (feats["n_credits_exceeded"] > 0).astype(int)
    feats["did_see_banner"] = (feats["n_banner_shown"] > 0).astype(int)
    feats["did_canvas_clone"] = (feats["n_canvas_clone"] > 0).astype(int)
    # drop ts (모델에 직접 안 씀)
    feats = feats.drop(columns=["first_ts", "last_ts"])
    # bool → int
    for c in ["any_tour_finish", "any_submit_form"]:
        feats[c] = feats[c].astype(int)
    feats.columns = [f"{c}_{suffix}" for c in feats.columns]
    return feats

all_feats = []
for win_name, win_sec in WINDOWS.items():
    t1 = time.time()
    if win_sec == float("inf"):
        sub = events_clean
    else:
        sub = events_clean.loc[events_clean["sec_since_first"] <= win_sec]
    f = compute_window_features(sub, suffix=win_name)
    all_feats.append(f)
    print(f"    window={win_name:<5} rows={len(sub):>10,} → {len(f.columns)} cols "
          f"({time.time()-t1:.1f}s)")

X = pd.concat(all_feats, axis=1).fillna(0)

# ──────────────────────────────────────────────────────────────────
# Time-to-* features (전체 history 기준, pre-cutoff)
# ──────────────────────────────────────────────────────────────────
print("\n[5] Time-to-X features (in pre-cutoff history)...", flush=True)
def first_event_offset(evset, name):
    sub = events_clean.loc[events_clean["event"].isin(evset)]
    first = sub.groupby("person_id")["timestamp"].min()
    offset = (first - user_first).dt.total_seconds() / 3600
    return offset.rename(f"hours_to_first_{name}")

X = X.join(first_event_offset(AI_EVENTS, "ai"))
X = X.join(first_event_offset({"block_create"}, "block_create"))
X = X.join(first_event_offset({"run_block"}, "run_block"))
X = X.join(first_event_offset(DEPLOY_EVENTS, "deploy"))
X = X.join(first_event_offset(INTEG_EVENTS, "source_control"))
X = X.join(first_event_offset(TRIGGER_EVENTS, "trigger"))

# ──────────────────────────────────────────────────────────────────
# v4 메타 컬럼 (pre-cutoff 기준)
# ──────────────────────────────────────────────────────────────────
print("\n[6] v4 metadata (pre-cutoff)...", flush=True)
# agent_first
first_ai = events_clean.loc[events_clean["is_ai"]].groupby("person_id")["timestamp"].min()
NB_SET = {"block_create", "run_block", "files_upload"}
first_nb = events_clean.loc[events_clean["event"].isin(NB_SET)].groupby("person_id")["timestamp"].min()
ai_idx = first_ai.reindex(X.index)
nb_idx = first_nb.reindex(X.index)
agent_first = ai_idx.notna() & (nb_idx.isna() | (ai_idx < nb_idx))
X["agent_first"] = agent_first.astype(int)

# is_power_engaged (pre-cutoff)
ENG = AI_EVENTS | CODE_EVENTS | INTEG_EVENTS | DEPLOY_EVENTS
eng_dates = events_clean.loc[events_clean["event"].isin(ENG)].drop_duplicates(
    ["person_id", "date"]
).groupby("person_id").size()
X["is_power_engaged"] = (eng_dates >= 7).reindex(X.index, fill_value=False).astype(int)

# observation_days (모델에 cutoff window 길이 알려주기)
X["observation_days"] = (cutoff - user_first).dt.total_seconds() / 86400
X["observation_days"] = X["observation_days"].clip(lower=0)

# ──────────────────────────────────────────────────────────────────
# 정적 (signup) 속성
# ──────────────────────────────────────────────────────────────────
print("\n[7] Static signup attributes...", flush=True)
def mode_per_user(col):
    sub = events.dropna(subset=[col])[["person_id", col]]
    return sub.groupby("person_id")[col].agg(
        lambda s: s.mode().iloc[0] if len(s.mode()) else None
    )

for col, name in [
    ("person_properties.purpose", "purpose"),
    ("person_properties.role", "role"),
    ("person_properties.work_type", "work_type"),
    ("person_properties.source", "signup_source"),
    ("properties.$device_type", "device_type"),
    ("properties.$os", "os"),
    ("properties.$geoip_country_name", "country"),
]:
    s = mode_per_user(col).reindex(X.index)
    if name == "country":
        # top-10 + Other
        top10 = s.value_counts().head(10).index
        s = s.where(s.isin(top10), "Other").fillna("Unknown")
    elif name == "os":
        s = s.fillna("Unknown")
    elif name == "device_type":
        s = s.fillna("Unknown")
    X[f"raw_{name}"] = s

# one-hot encode
for col in ["purpose", "role", "work_type", "signup_source",
            "device_type", "os", "country"]:
    raw = X[f"raw_{col}"].fillna("(missing)")
    dummies = pd.get_dummies(raw, prefix=col, dummy_na=False).astype(int)
    X = pd.concat([X, dummies], axis=1)
    X = X.drop(columns=[f"raw_{col}"])

# ──────────────────────────────────────────────────────────────────
# Cohort + label 추가 + 저장
# ──────────────────────────────────────────────────────────────────
X["first_event_ts"] = user_first.reindex(X.index)
X["cohort_month"] = X["first_event_ts"].dt.to_period("M").astype(str)
X["upgraded"] = y.reindex(X.index, fill_value=0).astype(int)
X["upgrade_ts"] = upgrade_ts.reindex(X.index)
X["cutoff_ts"] = cutoff.reindex(X.index)

print(f"\n    feature matrix shape: {X.shape}")
print(f"    label rate: {X['upgraded'].mean()*100:.2f}%")

# 저장
X.to_parquet("/Users/hunjunsin/Desktop/zerve/feature_matrix.parquet")
with open("/Users/hunjunsin/Desktop/zerve/feature_columns.txt", "w") as f:
    for c in X.columns:
        f.write(f"{c}  ({X[c].dtype})\n")

print(f"\nWROTE: feature_matrix.parquet ({X.shape[0]:,} × {X.shape[1]})")
print(f"WROTE: feature_columns.txt")
print(f"\nCohort distribution:")
print(X.groupby("cohort_month").agg(
    users=("upgraded", "size"),
    upgraders=("upgraded", "sum"),
).to_string())
