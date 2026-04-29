"""
업그레이드 후 이탈/다운그레이드 사용자 분석.

확인 항목:
  (A) downgrade/cancel 이벤트가 발생한 사용자 — 명시적 이탈
  (B) 업그레이드 후 비활성화 — 행동상 이탈 (Upgraded → AtRisk 후보)
  (C) 업그레이드 직후 vs 한참 후 이탈 분포
  (D) v4 funnel에 'Churned@Upgraded' 단계 신설할 가치 있는가?
"""
from __future__ import annotations
import pandas as pd
import numpy as np

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

print("[1] Loading...", flush=True)
events = pd.read_csv(CSV, usecols=["person_id", "timestamp", "event"], engine="pyarrow")
events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
DATA_END = events["timestamp"].max()

# 업그레이드 사용자
upgraders = set(events.loc[events["event"] == "subscription_upgraded", "person_id"].unique())
print(f"    upgraders: {len(upgraders):,}")

# 이탈 관련 이벤트
CHURN_EVENTS = [
    "subscription_downgraded",
    "downgrade_subscription",
    "subscription_cancelled",
    "cancel_subscription",
    "open_cancel_plan_modal",
]
print(f"\n=== (A) 이탈 관련 이벤트 빈도 (전체) ===")
for ev in CHURN_EVENTS:
    n_total = (events["event"] == ev).sum()
    n_users = events.loc[events["event"] == ev, "person_id"].nunique()
    print(f"  {ev:<30}  total={n_total:>5,}  unique_users={n_users:>4,}")

# 업그레이더 중 이탈 관련 이벤트 발생자
print(f"\n=== (B) 업그레이더 중 이탈 이벤트 발생자 ===")
upgr_events = events.loc[events["person_id"].isin(upgraders)]
for ev in CHURN_EVENTS:
    n = upgr_events.loc[upgr_events["event"] == ev, "person_id"].nunique()
    print(f"  {ev:<30}  {n:>4,} / 323 ({n/323*100:.1f}% of upgraders)")

# 다운그레이드/취소 이벤트가 *업그레이드 이후*에 발생했는지 확인
print(f"\n=== (C) 업그레이드 후 vs 전 다운그레이드/취소 시점 ===")
upg_first_ts = events.loc[events["event"] == "subscription_upgraded"].groupby(
    "person_id")["timestamp"].min()

for ev in ["subscription_downgraded", "downgrade_subscription",
           "subscription_cancelled", "cancel_subscription"]:
    sub = events.loc[(events["event"] == ev) & events["person_id"].isin(upgraders)]
    if len(sub) == 0:
        print(f"  {ev}: 0 events from upgraders")
        continue
    sub = sub.copy()
    sub["upg_ts"] = sub["person_id"].map(upg_first_ts)
    after = (sub["timestamp"] > sub["upg_ts"]).sum()
    before = (sub["timestamp"] <= sub["upg_ts"]).sum()
    n_users_after = sub.loc[sub["timestamp"] > sub["upg_ts"], "person_id"].nunique()
    print(f"  {ev:<30}  after_upg={after:>4} ({n_users_after:>3} users), "
          f"before/at_upg={before:>4}")

# 업그레이드 직후 시간(첫 이탈 이벤트까지 며칠?)
print(f"\n=== (D) 업그레이드 → 다운그레이드/취소까지 시간 분포 ===")
for ev in ["subscription_downgraded", "subscription_cancelled"]:
    sub = events.loc[(events["event"] == ev) & events["person_id"].isin(upgraders)].copy()
    if len(sub) == 0: continue
    sub["upg_ts"] = sub["person_id"].map(upg_first_ts)
    sub = sub[sub["timestamp"] > sub["upg_ts"]]
    sub["delta_days"] = (sub["timestamp"] - sub["upg_ts"]).dt.total_seconds() / 86400
    # 사용자별 첫 이탈 시점
    first_churn = sub.groupby("person_id")["delta_days"].min()
    if len(first_churn) == 0: continue
    print(f"  {ev}: n={len(first_churn)}, "
          f"median={first_churn.median():.1f}d, "
          f"p25={first_churn.quantile(.25):.1f}d, "
          f"p75={first_churn.quantile(.75):.1f}d, "
          f"max={first_churn.max():.1f}d")

# 행동상 이탈: 업그레이더 중 마지막 활동이 14일+ / 30일+ 전인 사람
print(f"\n=== (E) 업그레이더의 행동상 이탈 (asof=DATA_END) ===")
upgr_last = events.loc[events["person_id"].isin(upgraders)].groupby(
    "person_id")["timestamp"].max()
upgr_inactive_days = (DATA_END - upgr_last).dt.total_seconds() / 86400
print(f"  업그레이더 inactive 일수 분포:")
print(f"    median: {upgr_inactive_days.median():.1f}d")
print(f"    p25:    {upgr_inactive_days.quantile(.25):.2f}d")
print(f"    p75:    {upgr_inactive_days.quantile(.75):.2f}d")
print(f"    p90:    {upgr_inactive_days.quantile(.90):.1f}d")
print(f"    max:    {upgr_inactive_days.max():.1f}d")
for thr in [7, 14, 30, 60, 90, 180]:
    n = (upgr_inactive_days >= thr).sum()
    print(f"    >= {thr:>3}d 무활동: {n:>3} / 323  ({n/323*100:.1f}%)")

# (F) 명시적 이탈 vs 행동상 이탈 — 같은 사람들?
print(f"\n=== (F) 명시적 churn 이벤트 + 행동상 inactive 합쳐서 보기 ===")
explicit_churners = set()
for ev in ["subscription_downgraded", "subscription_cancelled",
           "downgrade_subscription", "cancel_subscription"]:
    sub = events.loc[(events["event"] == ev) & events["person_id"].isin(upgraders)]
    if len(sub) == 0: continue
    sub_after = sub.copy()
    sub_after["upg_ts"] = sub_after["person_id"].map(upg_first_ts)
    sub_after = sub_after[sub_after["timestamp"] > sub_after["upg_ts"]]
    explicit_churners.update(sub_after["person_id"].unique())
print(f"  명시적 churn 이벤트 발생 (업그레이드 이후): {len(explicit_churners)}명")

behavioral_churners_30 = set(upgr_inactive_days[upgr_inactive_days >= 30].index)
behavioral_churners_60 = set(upgr_inactive_days[upgr_inactive_days >= 60].index)
print(f"  행동상 이탈 (30일+ 무활동): {len(behavioral_churners_30)}명")
print(f"  행동상 이탈 (60일+ 무활동): {len(behavioral_churners_60)}명")
print(f"  명시적 + 행동상(30d) 합집합: {len(explicit_churners | behavioral_churners_30)}명")
print(f"  명시적 ∩ 행동상(30d): {len(explicit_churners & behavioral_churners_30)}명  "
      f"(명시적이면서 비활성)")
print(f"  명시적인데 활성: {len(explicit_churners - behavioral_churners_30)}명  "
      f"(다운그레이드했지만 계속 사용)")

# (G) renew_plan 이벤트 — 업그레이드 갱신 = 활성 결제 유지
renews = events.loc[events["event"] == "renew_plan", "person_id"].unique()
print(f"\n=== (G) renew_plan 이벤트 (정상 갱신자) ===")
print(f"  renew_plan 발생자: {len(renews)}명 (업그레이더 중 {len(set(renews) & upgraders)}명)")

# (H) 결론 — Churned@Upgraded 단계 필요한가?
print(f"\n" + "="*72)
print(f"=== (H) v4 'Churned@Upgraded' 단계 필요성 검토 ===")
print(f"="*72)
print(f"  명시적 churn (downgrade/cancel): {len(explicit_churners):>4}명")
print(f"  행동상 inactive 30d+:           {len(behavioral_churners_30):>4}명")
print(f"  행동상 inactive 60d+:           {len(behavioral_churners_60):>4}명")
print(f"  결합 (둘 중 하나):                {len(explicit_churners | behavioral_churners_60):>4}명")
print(f"")
if len(explicit_churners | behavioral_churners_60) >= 30:
    print(f"  ✓ 의미있는 population 존재 → v4에서 별도 단계 신설 권장")
else:
    print(f"  → population 작아 별도 단계는 과도. AtRisk@Upgraded 정도면 충분")
