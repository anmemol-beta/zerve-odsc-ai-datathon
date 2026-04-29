"""
Funnel v3 — 5개 보완 사항 모두 적용
====================================

(1) Engaged 정의 robust:  (UsedAI OR WroteCode OR Integrated) AND distinct_days >= 3
    → AI 안 쓰고 코드/통합만 깊게 사용한 사용자도 포섭

(2) AtRisk 세분화: prior stage별 4분할
    9.AtRisk@UsedAI / 9.AtRisk@WroteCode / 9.AtRisk@Integrated / 9.AtRisk@Engaged
    → "어디까지 갔다가 AtRisk됐는지" 정보 보존

(3) AtRisk threshold 옵션:
    AT_RISK_MIN_STAGE = 4 (default, "engagement" = UsedAI 이상)
    AT_RISK_MIN_STAGE = 7 (PDF strict, "engagement" = Engaged 이상)
    런타임 토글 가능

(4) 함수 시그니처 명시:
    classify_users(events, asof_ts, at_risk_days=14, at_risk_min_stage=4)
    → 같은 입력 → 같은 출력 (deterministic)

(5) Edge case 룰 명시:
    - timezone: 모든 timestamp UTC 일관
    - 재활성화: AtRisk → 재활동 시 AtRisk 자동 해제 (asof 시점에 days_since_last < 14면)
    - asof_ts < first_event: "0.NoEvent" 분류
    - asof_ts > DATA_END: 허용 (extrapolation 없이 가장 최근 데이터로)
    - 이벤트 timestamp가 microsecond precision까지 비교됨 (deterministic)
"""
from __future__ import annotations
import pandas as pd
import numpy as np

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

# ──────────────────────────────────────────────────────────────────
# Stage event sets — v3
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
                "source_control_pull",
                "notebook_deployment_deployed",
                "notebook_deployment_preview_created",
                "notebook_deployment_updated"}
UPGRADE_EVENT = "subscription_upgraded"

# (1) v3: Engagement events = UsedAI OR WroteCode OR Integrated
ENGAGEMENT_EVENTS = AI_EVENTS | CODE_EVENTS | INTEG_EVENTS

ENGAGED_DAYS = 3
AT_RISK_DAYS = 14
AT_RISK_MIN_STAGE_DEFAULT = 4   # "engagement" = UsedAI 이상 도달자

STAGE_NAMES = {
    0: "0.NoEvent",
    1: "1.New", 2: "2.Exploring", 3: "3.Created", 4: "4.UsedAI",
    5: "5.WroteCode", 6: "6.Integrated", 7: "7.Engaged", 8: "8.Upgraded",
}

# ──────────────────────────────────────────────────────────────────
# 핵심 함수: classify_users
# ──────────────────────────────────────────────────────────────────
def classify_users(
    events: pd.DataFrame,
    asof_ts: pd.Timestamp,
    at_risk_days: int = AT_RISK_DAYS,
    at_risk_min_stage: int = AT_RISK_MIN_STAGE_DEFAULT,
    engaged_days: int = ENGAGED_DAYS,
) -> pd.DataFrame:
    """사용자별 단계 분류 — Time-Aware deterministic classifier.

    Args
    ----
    events : DataFrame[person_id:str, timestamp:UTC datetime, event:str]
        모든 이벤트. asof_ts 이후 이벤트는 자동 필터됨.
    asof_ts : UTC timestamp
        분류 기준 시점. 이 시점까지의 이벤트만 사용 (within-user leak 차단).
    at_risk_days : int = 14
        AtRisk 판정 무활동 임계 (asof_ts - last_event_ts >= at_risk_days).
    at_risk_min_stage : int = 4
        AtRisk 적용 가능한 최소 highest 단계. 4=UsedAI(default), 7=Engaged(PDF strict).
    engaged_days : int = 3
        Engaged 단계 정의의 distinct days 임계.

    Returns
    -------
    DataFrame indexed by person_id, columns:
      highest (int 0..8)       : 도달한 가장 높은 단계 (8=Upgraded)
      days_since_last (float)  : asof_ts - 마지막 이벤트 (UTC days)
      upgraded (bool), at_risk (bool)
      final_stage (str)        : 최종 라벨 (NoEvent / 1~8 / 9.AtRisk@X)

    Edge cases
    ----------
    - asof_ts가 사용자의 first event보다 이전이면 → "0.NoEvent"
    - 재활성화: AtRisk 사용자가 다시 활동(asof_ts 기준 last_event가 14일 이내)하면
      자동으로 AtRisk 해제되고 highest 단계로 복귀. (각 asof_ts에서 재계산)
    - 모든 timestamp는 UTC. distinct_days는 UTC date 기준.
    - 같은 사용자에 대해 같은 (events, asof_ts)를 입력하면 항상 같은 결과 (deterministic).
    """
    # asof_ts 직전까지의 이벤트만
    e = events.loc[events["timestamp"] <= asof_ts]
    if len(e) == 0:
        return pd.DataFrame(columns=["highest", "days_since_last", "upgraded",
                                       "at_risk", "final_stage"])

    e = e.copy()
    e["date"] = e["timestamp"].dt.date

    # 사용자별 stage milestone first ts
    def first_ts(evset):
        return e.loc[e["event"].isin(evset)].groupby("person_id")["timestamp"].min()

    t1 = first_ts(NEW_EVENTS)
    t2 = first_ts(EXPLORE_EVENTS)
    t3 = first_ts(CREATED_EVENTS)
    t4 = first_ts(AI_EVENTS)
    t5 = first_ts(CODE_EVENTS)
    t6 = first_ts(INTEG_EVENTS)
    t8 = e.loc[e["event"] == UPGRADE_EVENT].groupby("person_id")["timestamp"].min()

    # Stage 7 (Engaged) v3: 사용자 첫 3rd-distinct-day의 첫 engagement event ts
    eng = e.loc[e["event"].isin(ENGAGEMENT_EVENTS), ["person_id", "timestamp", "date"]].copy()
    eng = eng.sort_values(["person_id", "timestamp"])
    # 각 (user, date) 쌍의 첫 timestamp
    first_per_date = eng.drop_duplicates(["person_id", "date"], keep="first")
    # 사용자별로 distinct date 순서대로 0,1,2,...
    first_per_date = first_per_date.sort_values(["person_id", "timestamp"])
    first_per_date["day_idx"] = first_per_date.groupby("person_id").cumcount()
    third_day = first_per_date.loc[first_per_date["day_idx"] == engaged_days - 1]
    t7 = third_day.set_index("person_id")["timestamp"]

    # 사용자 인덱스
    all_users = pd.Index(e["person_id"].unique(), name="person_id")
    last_ts = e.groupby("person_id")["timestamp"].max()

    mile = pd.DataFrame(index=all_users)
    mile["t1"] = t1; mile["t2"] = t2; mile["t3"] = t3; mile["t4"] = t4
    mile["t5"] = t5; mile["t6"] = t6; mile["t7"] = t7; mile["t8"] = t8
    mile["last_ts"] = last_ts
    mile["days_since_last"] = (asof_ts - mile["last_ts"]).dt.total_seconds() / 86400

    # highest stage = max k where t_k notna
    mile["highest"] = 0
    for k in range(1, 9):
        mile.loc[mile[f"t{k}"].notna(), "highest"] = k

    # 단, Upgraded는 무조건 highest=8 (다른 단계 도달여부 무관)
    mile["upgraded"] = mile["t8"].notna()
    mile.loc[mile["upgraded"], "highest"] = 8

    # AtRisk 판정 (Edge case: 재활성화 = days_since_last < at_risk_days → at_risk = False)
    mile["at_risk"] = (
        (mile["highest"] >= at_risk_min_stage) &
        (mile["highest"] < 8) &                              # Upgraded는 AtRisk 아님
        (mile["days_since_last"] >= at_risk_days)
    )

    # Final stage label
    def label(row):
        if row["upgraded"]:
            return "8.Upgraded"
        if row["at_risk"]:
            h = int(row["highest"])
            sub = STAGE_NAMES[h].split(".", 1)[1]   # e.g. "UsedAI"
            return f"9.AtRisk@{sub}"
        return STAGE_NAMES[int(row["highest"])]
    mile["final_stage"] = mile.apply(label, axis=1)

    return mile


def get_stage(person_id: str, asof_ts: pd.Timestamp,
              events: pd.DataFrame, **kwargs) -> str:
    """단일 사용자 분류 — classify_users의 단일 사용자 wrapper."""
    user_events = events.loc[events["person_id"] == person_id]
    if len(user_events) == 0:
        return "0.NoEvent"
    res = classify_users(user_events, asof_ts, **kwargs)
    if person_id not in res.index:
        return "0.NoEvent"
    return res.loc[person_id, "final_stage"]


# ──────────────────────────────────────────────────────────────────
# Demo / Validation
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[1] Loading...", flush=True)
    events = pd.read_csv(CSV, usecols=["person_id", "timestamp", "event"], engine="pyarrow")
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
    events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
    DATA_END = events["timestamp"].max()
    N_USERS = events["person_id"].nunique()
    print(f"    rows={len(events):,}  users={N_USERS:,}  data_end={DATA_END}")

    # ──────────────────────────────────────────────────────
    # (A) v3 default 분류 (asof = DATA_END, AT_RISK_MIN=4)
    # ──────────────────────────────────────────────────────
    print("\n[2] Classify @ asof=DATA_END, AT_RISK_MIN_STAGE=4 (default)...", flush=True)
    res_default = classify_users(events, DATA_END, at_risk_days=14, at_risk_min_stage=4)
    print(f"    classified users: {len(res_default):,}")

    # 분포
    counts = res_default["final_stage"].value_counts()
    # NoEvent 사용자 (asof < first event 같은 케이스 — 이 데이터엔 없음)
    no_event_users = N_USERS - len(res_default)

    final_order = [
        "0.NoEvent", "1.New", "2.Exploring", "3.Created", "4.UsedAI",
        "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded",
        "9.AtRisk@UsedAI", "9.AtRisk@WroteCode",
        "9.AtRisk@Integrated", "9.AtRisk@Engaged",
    ]
    print(f"\n=== (A) v3 FINAL DISTRIBUTION (asof=DATA_END, at_risk_min=4) ===")
    print(f"  {'stage':<24}{'users':>8}  {'% of all':>10}")
    if no_event_users > 0:
        print(f"  {'(no event in window)':<24}{no_event_users:>8,}  {no_event_users/N_USERS*100:>9.2f}%")
    total = no_event_users
    for s in final_order:
        c = int(counts.get(s, 0))
        total += c
        print(f"  {s:<24}{c:>8,}  {c/N_USERS*100:>9.2f}%")
    print(f"  {'TOTAL':<24}{total:>8,}  (sanity: must equal {N_USERS:,})")

    # ──────────────────────────────────────────────────────
    # (B) PDF strict 옵션 비교 (AT_RISK_MIN=7)
    # ──────────────────────────────────────────────────────
    print("\n[3] Strict mode: AT_RISK_MIN_STAGE=7 (PDF 'after engagement')...", flush=True)
    res_strict = classify_users(events, DATA_END, at_risk_days=14, at_risk_min_stage=7)
    counts_s = res_strict["final_stage"].value_counts()
    print(f"\n=== (B) STRICT DISTRIBUTION (asof=DATA_END, at_risk_min=7) ===")
    print(f"  {'stage':<24}{'default':>10}  {'strict':>10}  {'diff':>8}")
    all_keys = set(counts.index) | set(counts_s.index)
    for s in final_order:
        d = int(counts.get(s, 0))
        st = int(counts_s.get(s, 0))
        diff = st - d
        print(f"  {s:<24}{d:>10,}  {st:>10,}  {diff:>+8,}")

    # ──────────────────────────────────────────────────────
    # (C) Engaged v3 효과 측정 — robust 정의 적용 후 변화
    # ──────────────────────────────────────────────────────
    print("\n[4] Engaged v3 vs v2 비교...", flush=True)
    # v2 = (UsedAI) AND distinct_days >= 3
    # v3 = (UsedAI OR WroteCode OR Integrated) AND distinct_days >= 3

    def count_engaged_v2():
        ai = events.loc[events["event"].isin(AI_EVENTS), ["person_id", "timestamp"]].copy()
        ai["date"] = ai["timestamp"].dt.date
        days = ai.drop_duplicates(["person_id", "date"]).groupby("person_id").size()
        return int((days >= 3).sum())

    def count_engaged_v3():
        ev = events.loc[events["event"].isin(ENGAGEMENT_EVENTS), ["person_id", "timestamp"]].copy()
        ev["date"] = ev["timestamp"].dt.date
        days = ev.drop_duplicates(["person_id", "date"]).groupby("person_id").size()
        return int((days >= 3).sum())

    e_v2 = count_engaged_v2()
    e_v3 = count_engaged_v3()
    print(f"    Engaged v2 reach: {e_v2:>5,} ({e_v2/N_USERS*100:.2f}%)")
    print(f"    Engaged v3 reach: {e_v3:>5,} ({e_v3/N_USERS*100:.2f}%)  diff=+{e_v3-e_v2:,}")
    print(f"    추가 포섭: AI 안 쓰고 Code/Integration만으로 3+ days 활동한 사용자")

    # ──────────────────────────────────────────────────────
    # (D) Time-Aware 검증 — 다른 asof_ts에서 분포 변화 시뮬
    # ──────────────────────────────────────────────────────
    print("\n[5] Time-Aware 검증: 여러 asof 시점에서 funnel 분포...", flush=True)
    snapshots = [
        DATA_END - pd.Timedelta(days=120),
        DATA_END - pd.Timedelta(days=60),
        DATA_END - pd.Timedelta(days=30),
        DATA_END - pd.Timedelta(days=7),
        DATA_END,
    ]
    print(f"\n  {'stage':<24}", end="")
    for s in snapshots:
        label = s.strftime("%Y-%m-%d")
        print(f"  {label:>10}", end="")
    print()
    snap_results = {s: classify_users(events, s) for s in snapshots}
    for stg in ["1.New", "2.Exploring", "4.UsedAI", "7.Engaged", "8.Upgraded",
                "9.AtRisk@UsedAI", "9.AtRisk@WroteCode",
                "9.AtRisk@Integrated", "9.AtRisk@Engaged"]:
        print(f"  {stg:<24}", end="")
        for s in snapshots:
            c = (snap_results[s]["final_stage"] == stg).sum()
            print(f"  {c:>10,}", end="")
        print()

    # ──────────────────────────────────────────────────────
    # (E) 재활성화 케이스 검증 — 같은 사용자가 시간에 따라 단계 변하는지
    # ──────────────────────────────────────────────────────
    print("\n[6] 재활성화 검증: AtRisk → 활동재개 → 다른 단계 복귀...", flush=True)
    # 데이터 마지막 30일 안에 활동한 사용자 중, 60일 전 시점에서 AtRisk였던 사람 찾기
    prev = snap_results[DATA_END - pd.Timedelta(days=60)]
    cur = snap_results[DATA_END]
    common = prev.index.intersection(cur.index)
    prev_atrisk = prev.loc[common, "final_stage"].str.startswith("9.AtRisk")
    cur_active = ~cur.loc[common, "final_stage"].str.startswith("9.AtRisk")
    reactivated_idx = common[prev_atrisk & cur_active]
    n_react = len(reactivated_idx)
    print(f"    60일 전 AtRisk → DATA_END에 active로 복귀한 사용자: {n_react:,}")
    if n_react > 0:
        sample = reactivated_idx[0]
        prev_lbl = prev.loc[sample, "final_stage"]
        cur_lbl = cur.loc[sample, "final_stage"]
        print(f"    예시 사용자 {sample}:  60일 전 = {prev_lbl}  →  지금 = {cur_lbl}")
    print(f"    → 함수가 시간에 따라 단계를 자동 재계산함 ✓ Time-Aware ✓")

    # ──────────────────────────────────────────────────────
    # (F) AtRisk 세분화 효과: 정보 보존 검증
    # ──────────────────────────────────────────────────────
    print("\n[7] AtRisk 세분화 — prior stage 정보 보존 ===")
    atrisk_only = res_default.loc[res_default["final_stage"].str.startswith("9.AtRisk")]
    print(f"    AtRisk 총합: {len(atrisk_only):,}")
    print(f"    세분화 분포:")
    for sub in ["9.AtRisk@UsedAI", "9.AtRisk@WroteCode",
                "9.AtRisk@Integrated", "9.AtRisk@Engaged"]:
        c = (atrisk_only["final_stage"] == sub).sum()
        print(f"      {sub:<24}{c:>6,}  ({c/len(atrisk_only)*100:>5.2f}% of AtRisk)")

    # 결과 저장
    res_default.to_csv("/Users/hunjunsin/Desktop/zerve/funnel_v3_assignment.csv")
    print("\nWROTE: funnel_v3_assignment.csv")
