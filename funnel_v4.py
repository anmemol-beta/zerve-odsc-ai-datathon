"""
Funnel v4 — 15 stages + 7 metadata features
============================================

v3 → v4 변경점:
  ✅ 8.Upgraded → 3 sub-states:
       - 8.Upgraded            (active 또는 downgrade-but-active)
       - 9.AtRisk@Upgraded     (paying이지만 30+ days 무활동)
       - 9.Churned@Upgraded    (downgrade+inactive 또는 명시적 cancel)
  ✅ 메타 컬럼 7개 추가 (모델 feature, funnel 단계와 직교):
       - onboarding_completed   (tour 완주 여부)
       - used_promo             (promo/trial path 경험)
       - agent_first            (AI를 notebook보다 먼저 사용)
       - reactivated            (14d+ gap 후 5+ events)
       - exception_rate         ($exception / total events)
       - is_power_engaged       (engagement days 7+)
       - purpose                (Personal/Company/Education, optional)

전체 단계 (15 categories):
  0.NoEvent
  1.New, 2.Exploring, 3.Created, 4.UsedAI, 5.WroteCode, 6.Integrated, 7.Engaged
  8.Upgraded                      (active paying customer)
  9.AtRisk@UsedAI, @WroteCode, @Integrated, @Engaged
  9.AtRisk@Upgraded               (NEW: paying but inactive)
  9.Churned@Upgraded              (NEW: explicit churn)

Edge cases:
  - asof_ts < first_event              → "0.NoEvent"
  - 재활성화 자동 처리                    → AtRisk 해제 (asof 시점 재계산)
  - downgrade했지만 활성              → 8.Upgraded (일종의 "smaller plan")
  - 모든 timestamp UTC, distinct_days = UTC date
  - cancel는 downgrade보다 우선 적용 (둘 다 있으면 Churned)
"""
from __future__ import annotations
import pandas as pd
import numpy as np

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

# ─────────────────────────────────────────────────────────────
# Stage event sets (v3와 동일)
# ─────────────────────────────────────────────────────────────
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
                "source_control_pull",
                "notebook_deployment_deployed",
                "notebook_deployment_preview_created",
                "notebook_deployment_updated"}
ENGAGEMENT_EVENTS = AI_EVENTS | CODE_EVENTS | INTEG_EVENTS
UPGRADE_EVENT = "subscription_upgraded"

# ─────────────────────────────────────────────────────────────
# v4 새 이벤트 set
# ─────────────────────────────────────────────────────────────
DOWNGRADE_EVENTS = {"subscription_downgraded", "downgrade_subscription"}
CANCEL_EVENTS = {"subscription_cancelled", "cancel_subscription"}
TRIAL_EVENTS = {
    "promo_code_redeemed",
    "claim_free_offer_clicked",
    "work_email_bonus_credits_received",
    "referral_bonus_credits_received",
}
TOUR_FINISHED_EVENT = "notebook_onboarding_tour_finished"
EXCEPTION_EVENT = "$exception"
NOTEBOOK_EVENTS = {"block_create", "run_block", "files_upload"}

# 임계값
ENGAGED_DAYS = 3
AT_RISK_DAYS = 14
AT_RISK_MIN_STAGE = 4
UPGRADE_INACTIVE_DAYS = 30
POWER_ENGAGED_DAYS = 7
REACT_GAP_DAYS = 14
REACT_MIN_EVENTS_AFTER = 5

STAGE_NAMES = {
    0: "0.NoEvent",
    1: "1.New", 2: "2.Exploring", 3: "3.Created", 4: "4.UsedAI",
    5: "5.WroteCode", 6: "6.Integrated", 7: "7.Engaged", 8: "8.Upgraded",
}

V4_STAGE_ORDER = [
    "0.NoEvent",
    "1.New", "2.Exploring", "3.Created", "4.UsedAI",
    "5.WroteCode", "6.Integrated", "7.Engaged",
    "8.Upgraded",
    "9.AtRisk@UsedAI", "9.AtRisk@WroteCode",
    "9.AtRisk@Integrated", "9.AtRisk@Engaged",
    "9.AtRisk@Upgraded", "9.Churned@Upgraded",
]


def classify_users_v4(
    events: pd.DataFrame,
    asof_ts: pd.Timestamp,
    at_risk_days: int = AT_RISK_DAYS,
    at_risk_min_stage: int = AT_RISK_MIN_STAGE,
    engaged_days: int = ENGAGED_DAYS,
    upgrade_inactive_days: int = UPGRADE_INACTIVE_DAYS,
) -> pd.DataFrame:
    """v4 사용자 분류 + 메타 컬럼 산출.

    Returns DataFrame indexed by person_id with columns:
      Stage classification:
        highest, days_since_last, upgraded, downgraded, cancelled,
        atrisk_upg, churned_upg, at_risk, final_stage
      Metadata:
        onboarding_completed, used_promo, agent_first, reactivated,
        exception_rate, is_power_engaged, purpose
    """
    e = events.loc[events["timestamp"] <= asof_ts]
    if len(e) == 0:
        return pd.DataFrame()
    e = e.copy()
    e["date"] = e["timestamp"].dt.date

    def first_ts(evset):
        return e.loc[e["event"].isin(evset)].groupby("person_id")["timestamp"].min()

    # Stage milestones
    t1 = first_ts(NEW_EVENTS); t2 = first_ts(EXPLORE_EVENTS)
    t3 = first_ts(CREATED_EVENTS); t4 = first_ts(AI_EVENTS)
    t5 = first_ts(CODE_EVENTS); t6 = first_ts(INTEG_EVENTS)
    t8 = e.loc[e["event"] == UPGRADE_EVENT].groupby("person_id")["timestamp"].min()

    # Stage 7 — Engaged
    eng = e.loc[e["event"].isin(ENGAGEMENT_EVENTS), ["person_id", "timestamp", "date"]].copy()
    eng = eng.sort_values(["person_id", "timestamp"])
    first_per_date = eng.drop_duplicates(["person_id", "date"], keep="first").sort_values(
        ["person_id", "timestamp"]
    )
    first_per_date["day_idx"] = first_per_date.groupby("person_id").cumcount()
    t7 = first_per_date.loc[
        first_per_date["day_idx"] == engaged_days - 1
    ].set_index("person_id")["timestamp"]

    all_users = pd.Index(e["person_id"].unique(), name="person_id")
    last_ts = e.groupby("person_id")["timestamp"].max()

    df = pd.DataFrame(index=all_users)
    df["t1"] = t1; df["t2"] = t2; df["t3"] = t3; df["t4"] = t4
    df["t5"] = t5; df["t6"] = t6; df["t7"] = t7; df["t8"] = t8
    df["last_ts"] = last_ts
    df["days_since_last"] = (asof_ts - df["last_ts"]).dt.total_seconds() / 86400

    # Highest stage
    df["highest"] = 0
    for k in range(1, 9):
        df.loc[df[f"t{k}"].notna(), "highest"] = k
    df["upgraded"] = df["t8"].notna()

    # ─── v4: post-upgrade events ───
    if df["upgraded"].any():
        upgr_idx = df.index[df["upgraded"]]
        upg_first = df.loc[upgr_idx, "t8"]
        e_upgr = e.loc[e["person_id"].isin(upgr_idx)].copy()
        e_upgr["upg_ts"] = e_upgr["person_id"].map(upg_first)
        e_post = e_upgr.loc[e_upgr["timestamp"] > e_upgr["upg_ts"]]
        downgrade_users = set(
            e_post.loc[e_post["event"].isin(DOWNGRADE_EVENTS), "person_id"].unique()
        )
        cancel_users = set(
            e_post.loc[e_post["event"].isin(CANCEL_EVENTS), "person_id"].unique()
        )
    else:
        downgrade_users, cancel_users = set(), set()

    df["downgraded"] = df.index.isin(downgrade_users)
    df["cancelled"] = df.index.isin(cancel_users)

    # AtRisk@Upgraded vs Churned@Upgraded
    df["upg_inactive"] = df["upgraded"] & (df["days_since_last"] >= upgrade_inactive_days)
    df["churned_upg"] = df["upgraded"] & (
        df["cancelled"] | (df["downgraded"] & df["upg_inactive"])
    )
    df["atrisk_upg"] = (
        df["upgraded"] & df["upg_inactive"] & ~df["churned_upg"]
    )

    # AtRisk (non-upgrade)
    df["at_risk"] = (
        (df["highest"] >= at_risk_min_stage) &
        (df["highest"] < 8) &
        (~df["upgraded"]) &
        (df["days_since_last"] >= at_risk_days)
    )

    # Final stage label (vectorized)
    df["final_stage"] = df["highest"].map(STAGE_NAMES)
    # AtRisk for non-upgraders
    ar_mask = df["at_risk"]
    df.loc[ar_mask, "final_stage"] = (
        "9.AtRisk@" + df.loc[ar_mask, "highest"].map(STAGE_NAMES).str.split(".", n=1).str[1]
    )
    # Upgraded subdivisions
    df.loc[df["upgraded"], "final_stage"] = "8.Upgraded"
    df.loc[df["atrisk_upg"], "final_stage"] = "9.AtRisk@Upgraded"
    df.loc[df["churned_upg"], "final_stage"] = "9.Churned@Upgraded"

    # ─── v4 METADATA ───
    tour_finished = set(e.loc[e["event"] == TOUR_FINISHED_EVENT, "person_id"].unique())
    df["onboarding_completed"] = df.index.isin(tour_finished)

    promo_users = set(e.loc[e["event"].isin(TRIAL_EVENTS), "person_id"].unique())
    df["used_promo"] = df.index.isin(promo_users)

    # agent_first
    first_ai = e.loc[e["event"].isin(AI_EVENTS)].groupby("person_id")["timestamp"].min()
    first_nb = e.loc[e["event"].isin(NOTEBOOK_EVENTS)].groupby("person_id")["timestamp"].min()
    af = pd.Series(False, index=df.index)
    # AI exists and (NB doesn't OR AI < NB)
    has_ai = first_ai.reindex(df.index).notna()
    has_nb = first_nb.reindex(df.index).notna()
    ai_before_nb = (
        first_ai.reindex(df.index).fillna(pd.Timestamp.max.tz_localize("UTC"))
        < first_nb.reindex(df.index).fillna(pd.Timestamp.max.tz_localize("UTC"))
    )
    df["agent_first"] = has_ai & (ai_before_nb | ~has_nb)

    # reactivated
    e_sorted = e[["person_id", "timestamp"]].sort_values(["person_id", "timestamp"])
    e_sorted["prev_ts"] = e_sorted.groupby("person_id")["timestamp"].shift(1)
    e_sorted["gap"] = (e_sorted["timestamp"] - e_sorted["prev_ts"]).dt.total_seconds() / 86400
    e_sorted["had_big_gap"] = (
        e_sorted.groupby("person_id")["gap"].cummax() >= REACT_GAP_DAYS
    ).astype(int)
    n_after = e_sorted.loc[e_sorted["had_big_gap"] == 1].groupby("person_id").size()
    react_users = set(n_after[n_after >= REACT_MIN_EVENTS_AFTER].index)
    df["reactivated"] = df.index.isin(react_users)

    # exception_rate
    n_total = e.groupby("person_id").size()
    n_exc = e.loc[e["event"] == EXCEPTION_EVENT].groupby("person_id").size()
    df["exception_rate"] = (n_exc / n_total).reindex(df.index, fill_value=0.0)

    # is_power_engaged
    eng_days = eng.drop_duplicates(["person_id", "date"]).groupby("person_id").size()
    df["is_power_engaged"] = (eng_days >= POWER_ENGAGED_DAYS).reindex(df.index, fill_value=False)

    # purpose (events에 컬럼이 있을 때만)
    if "person_properties.purpose" in events.columns:
        purpose = (
            events.loc[events["timestamp"] <= asof_ts]
            .dropna(subset=["person_properties.purpose"])
            .groupby("person_id")["person_properties.purpose"]
            .agg(lambda s: s.mode().iloc[0] if len(s.mode()) else None)
        )
        df["purpose"] = purpose.reindex(df.index)
    else:
        df["purpose"] = None

    return df


# ──────────────────────────────────────────────────────────────────
# Demo / Validation
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[1] Loading with person_properties.purpose...", flush=True)
    events = pd.read_csv(
        CSV,
        usecols=["person_id", "timestamp", "event", "person_properties.purpose"],
        engine="pyarrow",
    )
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
    events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
    DATA_END = events["timestamp"].max()
    N = events["person_id"].nunique()
    print(f"    rows={len(events):,}  users={N:,}  data_end={DATA_END}")

    print("\n[2] Classifying with v4...", flush=True)
    res = classify_users_v4(events, DATA_END)
    print(f"    classified: {len(res):,}")

    # ────────────── (A) v4 분포 ──────────────
    counts = res["final_stage"].value_counts()
    print(f"\n=== (A) v4 STAGE DISTRIBUTION (asof=DATA_END) ===")
    print(f"  {'stage':<24}{'users':>8}  {'% of all':>10}")
    no_event = N - len(res)
    if no_event > 0:
        print(f"  {'(no event in window)':<24}{no_event:>8,}  {no_event/N*100:>9.2f}%")
    total_chk = no_event
    for s in V4_STAGE_ORDER:
        c = int(counts.get(s, 0))
        total_chk += c
        if c > 0:
            print(f"  {s:<24}{c:>8,}  {c/N*100:>9.2f}%")
    print(f"  {'TOTAL':<24}{total_chk:>8,}  (sanity: must equal {N:,})")

    # ────────────── (B) v3 vs v4 8.Upgraded 비교 ──────────────
    print(f"\n=== (B) v3 vs v4 — 8.Upgraded 분해 ===")
    n_upg = int(res["upgraded"].sum())
    n_8 = int((res["final_stage"] == "8.Upgraded").sum())
    n_ar_upg = int((res["final_stage"] == "9.AtRisk@Upgraded").sum())
    n_ch_upg = int((res["final_stage"] == "9.Churned@Upgraded").sum())
    print(f"  v3:")
    print(f"    8.Upgraded (모두):           {n_upg}")
    print(f"  v4:")
    print(f"    8.Upgraded (active):         {n_8:>3}  ({n_8/n_upg*100:.1f}%)")
    print(f"    9.AtRisk@Upgraded:           {n_ar_upg:>3}  ({n_ar_upg/n_upg*100:.1f}%)")
    print(f"    9.Churned@Upgraded:          {n_ch_upg:>3}  ({n_ch_upg/n_upg*100:.1f}%)")
    print(f"    sanity: {n_8 + n_ar_upg + n_ch_upg} = {n_upg}")

    # ────────────── (C) 메타데이터 분포 ──────────────
    print(f"\n=== (C) 메타데이터 분포 ===")
    for col in ["onboarding_completed", "used_promo", "agent_first",
                "reactivated", "is_power_engaged"]:
        n_true = int(res[col].sum())
        print(f"  {col:<25} True={n_true:>6,}  ({n_true/len(res)*100:>5.2f}%)")

    print(f"  exception_rate            median={res['exception_rate'].median():.3f}  "
          f"p90={res['exception_rate'].quantile(.9):.3f}")
    print(f"  purpose dist:")
    for p, c in res["purpose"].value_counts(dropna=False).items():
        print(f"    {str(p):<25}  {c:>6,}  ({c/len(res)*100:.2f}%)")

    # ────────────── (D) 메타 × 단계 cross-tab — 업그레이드율 ──────────────
    print(f"\n=== (D) 메타 컬럼별 업그레이드율 (전체 사용자 대비) ===")
    upgraded_mask = res["final_stage"].isin(["8.Upgraded", "9.AtRisk@Upgraded", "9.Churned@Upgraded"])
    print(f"  {'meta_value':<35} {'users':>7}  {'upgraded':>9}  {'rate':>8}")
    for col in ["onboarding_completed", "used_promo", "agent_first",
                "reactivated", "is_power_engaged"]:
        for v in [True, False]:
            mask = res[col] == v
            n = int(mask.sum())
            n_upg = int((mask & upgraded_mask).sum())
            rate = n_upg / n * 100 if n else 0
            print(f"  {col}={str(v):<22} {n:>7,}  {n_upg:>8,}  {rate:>7.2f}%")

    # ────────────── (E) 메타 조합 — Top conversion 그룹 ──────────────
    print(f"\n=== (E) 메타 조합별 업그레이드율 (Top combos) ===")
    res["combo"] = (
        "tour=" + res["onboarding_completed"].astype(str) +
        " | promo=" + res["used_promo"].astype(str) +
        " | af=" + res["agent_first"].astype(str)
    )
    combo_stats = res.groupby("combo").agg(
        users=("final_stage", "size"),
        upgraded=("final_stage", lambda s: s.isin(["8.Upgraded", "9.AtRisk@Upgraded", "9.Churned@Upgraded"]).sum()),
    )
    combo_stats["rate"] = combo_stats["upgraded"] / combo_stats["users"] * 100
    combo_stats = combo_stats.sort_values("rate", ascending=False)
    print(f"  {'combo':<55} {'users':>7}  {'upg':>5}  {'rate':>7}")
    for combo, row in combo_stats.iterrows():
        print(f"  {combo:<55} {int(row['users']):>7,}  {int(row['upgraded']):>4}  "
              f"{row['rate']:>6.2f}%")

    # 결과 저장
    res.to_csv("/Users/hunjunsin/Desktop/zerve/funnel_v4_assignment.csv")
    print(f"\nWROTE: funnel_v4_assignment.csv")
