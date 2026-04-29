"""
v3 funnel 재분석 + 약점 진단.

분석 항목:
  (A) v3 transition matrix (Engaged 새 정의 반영)
  (B) Stage k → outcome (AtRisk 4분할 반영)
  (C) AtRisk subgroup별 행동/회복 특성
  (D) Stage 3 Created transit 문제 확인
  (E) AtRisk → 재활성화 분석 (AtRisk@X 별 복귀율, 업그레이드율)
  (F) 단계별 update 횟수/시간 분포 — 사용자 깊이 진단
  (G) 잠재적 v4 개선점 도출
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from collections import Counter

import sys
sys.path.insert(0, "/Users/hunjunsin/Desktop/zerve")
from funnel_v3 import (
    classify_users, NEW_EVENTS, EXPLORE_EVENTS, CREATED_EVENTS,
    AI_EVENTS, CODE_EVENTS, INTEG_EVENTS, ENGAGEMENT_EVENTS,
    UPGRADE_EVENT, ENGAGED_DAYS, AT_RISK_DAYS, STAGE_NAMES,
)

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

print("[1] Loading...", flush=True)
events = pd.read_csv(CSV, usecols=["person_id", "timestamp", "event"], engine="pyarrow")
events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
DATA_END = events["timestamp"].max()
N_USERS = events["person_id"].nunique()
print(f"    rows={len(events):,}  users={N_USERS:,}")

# v3 분류 (default)
print("\n[2] Running v3 classification @ DATA_END...", flush=True)
v3 = classify_users(events, DATA_END)
print(f"    classified: {len(v3):,}")

# ──────────────────────────────────────────────────────────────────
# (A) v3 transition matrix — Engaged 새 정의로 milestone 재계산
# ──────────────────────────────────────────────────────────────────
print("\n=== (A) v3 transition matrix ===", flush=True)

def first_ts(evset):
    return events.loc[events["event"].isin(evset)].groupby("person_id")["timestamp"].min()

t1 = first_ts(NEW_EVENTS)
t2 = first_ts(EXPLORE_EVENTS)
t3 = first_ts(CREATED_EVENTS)
t4 = first_ts(AI_EVENTS)
t5 = first_ts(CODE_EVENTS)
t6 = first_ts(INTEG_EVENTS)
t8 = events.loc[events["event"] == UPGRADE_EVENT].groupby("person_id")["timestamp"].min()

# Stage 7 (v3): 사용자 첫 3rd-distinct-day의 첫 engagement event ts
# (engagement = AI ∪ Code ∪ Integ)
eng = events.loc[events["event"].isin(ENGAGEMENT_EVENTS), ["person_id", "timestamp"]].copy()
eng["date"] = eng["timestamp"].dt.date
eng = eng.sort_values(["person_id", "timestamp"])
first_per_date = eng.drop_duplicates(["person_id", "date"], keep="first").sort_values(
    ["person_id", "timestamp"]
)
first_per_date["day_idx"] = first_per_date.groupby("person_id").cumcount()
t7 = first_per_date.loc[first_per_date["day_idx"] == 2].set_index("person_id")["timestamp"]

all_users = pd.Index(events["person_id"].unique(), name="person_id")
mile = pd.DataFrame(index=all_users)
mile["t1"] = t1; mile["t2"] = t2; mile["t3"] = t3; mile["t4"] = t4
mile["t5"] = t5; mile["t6"] = t6; mile["t7"] = t7; mile["t8"] = t8

# 인접 전이 카운트
long = mile[[f"t{k}" for k in range(1,9)]].reset_index().melt(
    id_vars="person_id", var_name="stage_col", value_name="ts"
).dropna(subset=["ts"])
long["stage"] = long["stage_col"].str[1:].astype(int)
long = long.sort_values(["person_id", "ts"]).reset_index(drop=True)
long["next_stage"] = long.groupby("person_id")["stage"].shift(-1)
pairs = long.dropna(subset=["next_stage"]).copy()
pairs["next_stage"] = pairs["next_stage"].astype(int)

trans = pairs.groupby(["stage", "next_stage"]).size().unstack(fill_value=0)
trans = trans.reindex(index=range(1,9), columns=range(1,9), fill_value=0)

print(f"\n  v3 transition counts (FROM → TO):")
print(f"     {'TO →':>10}", end="")
for j in range(1, 9): print(f"{j:>7}", end="")
print()
for i in range(1, 9):
    print(f"  FROM {i}  ", end="")
    for j in range(1, 9):
        v = int(trans.loc[i, j]) if j in trans.columns else 0
        print(f"{v:>7,}", end="")
    print(f"   {STAGE_NAMES[i]}")

print(f"\n  v3 transition probs P(next | from):")
print(f"     {'TO →':>10}", end="")
for j in range(1, 9): print(f"{j:>7}", end="")
print()
row_sums = trans.sum(axis=1).replace(0, 1)
trans_p = trans.div(row_sums, axis=0)
for i in range(1, 9):
    print(f"  FROM {i}  ", end="")
    for j in range(1, 9):
        v = trans_p.loc[i, j] if j in trans_p.columns else 0.0
        print(f"{v:>6.1%}", end=" ")
    print(f"  {STAGE_NAMES[i]}")

# ──────────────────────────────────────────────────────────────────
# (B) Stage k → v3 outcome distribution (AtRisk 4분할)
# ──────────────────────────────────────────────────────────────────
print("\n=== (B) Stage k 도달자의 v3 최종 상태 ===", flush=True)
# v3 결과를 조인
mile["upgraded"] = mile["t8"].notna()
last_ts = events.groupby("person_id")["timestamp"].max()
mile["last_ts"] = last_ts
mile["days_since_last"] = (DATA_END - mile["last_ts"]).dt.total_seconds() / 86400

# v3 final_stage join
mile = mile.join(v3[["final_stage"]])

print(f"  {'reached':<14} {'users':>7}  {'progressed':>11}  {'upgraded':>9}  "
      f"{'AR@Used':>8}  {'AR@Code':>8}  {'AR@Int':>7}  {'AR@Eng':>7}  {'active':>7}")
for k in range(1, 8):
    reached = mile[f"t{k}"].notna()
    n_reached = int(reached.sum())
    if n_reached == 0: continue
    sub = mile[reached]
    progressed = sub[[f"t{j}" for j in range(k+1, 9)]].notna().any(axis=1)
    upgraded = sub["upgraded"]
    ar_used = sub["final_stage"] == "9.AtRisk@UsedAI"
    ar_code = sub["final_stage"] == "9.AtRisk@WroteCode"
    ar_int  = sub["final_stage"] == "9.AtRisk@Integrated"
    ar_eng  = sub["final_stage"] == "9.AtRisk@Engaged"
    active  = (~progressed) & (~upgraded) & (~ar_used) & (~ar_code) & (~ar_int) & (~ar_eng)
    print(f"  {STAGE_NAMES[k]:<14} {n_reached:>7,}  "
          f"{progressed.sum()/n_reached:>10.1%}  "
          f"{upgraded.sum()/n_reached:>8.1%}  "
          f"{ar_used.sum()/n_reached:>7.1%}  "
          f"{ar_code.sum()/n_reached:>7.1%}  "
          f"{ar_int.sum()/n_reached:>6.1%}  "
          f"{ar_eng.sum()/n_reached:>6.1%}  "
          f"{active.sum()/n_reached:>6.1%}")

# ──────────────────────────────────────────────────────────────────
# (C) AtRisk subgroup 행동 특성
# ──────────────────────────────────────────────────────────────────
print("\n=== (C) AtRisk subgroup별 행동 프로파일 ===", flush=True)
# 사용자별 이벤트 수, distinct days
user_events_n = events.groupby("person_id").size()
user_days = events.assign(date=events["timestamp"].dt.date).groupby("person_id")["date"].nunique()

prof = mile.copy()
prof["n_events"] = user_events_n
prof["distinct_days"] = user_days
# 활동 기간 (lifetime)
first_t = events.groupby("person_id")["timestamp"].min()
prof["lifetime_days"] = (prof["last_ts"] - first_t).dt.total_seconds() / 86400

print(f"\n  {'subgroup':<24} {'users':>6}  {'median_events':>14}  "
      f"{'median_days':>12}  {'median_lifetime':>16}  {'median_inactive':>16}")
for sg in ["9.AtRisk@UsedAI", "9.AtRisk@WroteCode",
           "9.AtRisk@Integrated", "9.AtRisk@Engaged",
           "7.Engaged", "8.Upgraded"]:
    mask = prof["final_stage"] == sg
    n = int(mask.sum())
    if n == 0: continue
    sub = prof[mask]
    print(f"  {sg:<24} {n:>6,}  "
          f"{int(sub['n_events'].median()):>13,}  "
          f"{int(sub['distinct_days'].median()):>11,}  "
          f"{sub['lifetime_days'].median():>15.2f}d  "
          f"{sub['days_since_last'].median():>15.2f}d")

# ──────────────────────────────────────────────────────────────────
# (D) Stage 3 Created transit 문제 진단
# ──────────────────────────────────────────────────────────────────
print("\n=== (D) Stage 3 (Created) 문제 진단 ===", flush=True)
print(f"  highest = 3 (현재 분류): {(prof['final_stage'] == '3.Created').sum()}명")
# 'Stage 3 도달했지만 Stage 4 (UsedAI) 도달 못 한' 사용자 — 즉 Created만 한 사용자
created_only = mile["t3"].notna() & mile["t4"].isna() & mile["t5"].isna() & mile["t6"].isna() & ~mile["upgraded"]
print(f"  Created 도달 + UsedAI/Code/Integ 미도달: {int(created_only.sum())}명")
# Stage 3 이후 시간 분포
print(f"  Stage 3 도달자 중 그 다음 milestone까지 median: {(mile.loc[mile['t3'].notna(), ['t4','t5','t6','t7','t8']].min(axis=1) - mile.loc[mile['t3'].notna(), 't3']).dt.total_seconds().median()/3600:.2f}h")

# Stage 3 vs Stage 4 도달 시간 비교 — 누가 더 먼저?
both34 = mile[mile["t3"].notna() & mile["t4"].notna()]
ai_first = (both34["t4"] < both34["t3"]).sum()
created_first = (both34["t3"] < both34["t4"]).sum()
same = (both34["t3"] == both34["t4"]).sum()
print(f"  Stage 3+4 모두 도달한 사용자 {len(both34):,}명 중:")
print(f"    AI를 먼저 도달:        {ai_first:>5,}  ({ai_first/len(both34)*100:.1f}%)")
print(f"    Created를 먼저 도달:   {created_first:>5,}  ({created_first/len(both34)*100:.1f}%)")
print(f"    동시:                  {same:>5,}  ({same/len(both34)*100:.1f}%)")

# ──────────────────────────────────────────────────────────────────
# (E) AtRisk → 재활성화 분석 (snapshot 기반)
# ──────────────────────────────────────────────────────────────────
print("\n=== (E) AtRisk 사용자의 재활성화 율 (60일 전 → 지금) ===", flush=True)
prev_60 = classify_users(events, DATA_END - pd.Timedelta(days=60))
# 60일 전 AtRisk@X 였던 사용자가 DATA_END에 어떤 상태?
common = prev_60.index.intersection(v3.index)

print(f"  {'prev_state':<24} {'count':>6}  {'now_active':>11}  {'now_upg':>9}  {'still_AR':>9}")
for ar in ["9.AtRisk@UsedAI", "9.AtRisk@WroteCode",
           "9.AtRisk@Integrated", "9.AtRisk@Engaged"]:
    mask = prev_60.loc[common, "final_stage"] == ar
    n = int(mask.sum())
    if n == 0: continue
    pids = common[mask]
    cur = v3.loc[pids, "final_stage"]
    n_active = int(((~cur.str.startswith("9.AtRisk")) & (cur != "8.Upgraded")).sum())
    n_upg    = int((cur == "8.Upgraded").sum())
    n_ar     = int(cur.str.startswith("9.AtRisk").sum())
    print(f"  {ar:<24} {n:>6,}  "
          f"{n_active/n:>10.1%}  {n_upg/n:>8.1%}  {n_ar/n:>8.1%}")

# ──────────────────────────────────────────────────────────────────
# (F) 단계별 사용자 활동 깊이
# ──────────────────────────────────────────────────────────────────
print("\n=== (F) 단계별 활동 깊이 (events per user, AI 사용량) ===", flush=True)
# 사용자별 AI 이벤트 카운트
ai_per_user = events.loc[events["event"].isin(AI_EVENTS)].groupby("person_id").size()
code_per_user = events.loc[events["event"].isin(CODE_EVENTS)].groupby("person_id").size()
prof["n_ai"] = ai_per_user.reindex(prof.index, fill_value=0)
prof["n_code"] = code_per_user.reindex(prof.index, fill_value=0)

print(f"\n  {'stage':<24} {'n':>6}  {'med_events':>11}  {'med_AI':>8}  {'med_code':>9}")
for s in ["1.New", "2.Exploring", "4.UsedAI", "5.WroteCode", "6.Integrated",
          "7.Engaged", "8.Upgraded",
          "9.AtRisk@UsedAI", "9.AtRisk@WroteCode",
          "9.AtRisk@Integrated", "9.AtRisk@Engaged"]:
    mask = prof["final_stage"] == s
    n = int(mask.sum())
    if n == 0: continue
    sub = prof[mask]
    print(f"  {s:<24} {n:>6,}  "
          f"{int(sub['n_events'].median()):>10,}  "
          f"{int(sub['n_ai'].median()):>7,}  "
          f"{int(sub['n_code'].median()):>8,}")

# ──────────────────────────────────────────────────────────────────
# (G) v4 잠재 개선점 도출
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("=== (G) v3 진단 결과 — 잠재 v4 개선점 ===")
print("="*72)
issues = []

# 1) Stage 3 transit 여부
n_stage3 = (prof["final_stage"] == "3.Created").sum()
total_reach3 = mile["t3"].notna().sum()
issues.append((f"Stage 3 (Created) transit 문제: highest=3 사용자 {n_stage3}명 / 도달자 {total_reach3}명",
               n_stage3 / total_reach3 < 0.01))

# 2) AtRisk@Integrated 작은 population
n_ar_int = (prof["final_stage"] == "9.AtRisk@Integrated").sum()
issues.append((f"AtRisk@Integrated population 작음: {n_ar_int}명 (전체의 {n_ar_int/N_USERS*100:.2f}%)",
               n_ar_int < N_USERS * 0.02))

# 3) Stuck 사용자 (active이지만 진척 없음) — Exploring stuck 가장 큼
exploring_stuck = (prof["final_stage"] == "2.Exploring").sum()
issues.append((f"Exploring stuck 사용자 거대: {exploring_stuck:,}명 ({exploring_stuck/N_USERS*100:.1f}%)  "
               f"→ 이건 stage 자체의 문제라기보다 product onboarding 문제",
               True))

# 4) Engaged v3 효과 미미
issues.append((f"Engaged v3 reach 증가 미미 (754 → 781, +27)  "
               f"→ Code/Integration 단독으로는 3+ days 활동 사용자 거의 없음",
               True))

# 5) NoEvent 74 처리
issues.append((f"NoEvent 74명 — timestamp는 있지만 NaN event/None 사용자 (data quality 이슈)",
               True))

for i, (desc, flagged) in enumerate(issues, 1):
    mark = "⚠️" if flagged else "ℹ️"
    print(f"  {mark} {i}. {desc}")

print("\n  v4 권장 개선 후보:")
print("     a) Stage 3 정의 약간 좁히기 (block_create + files_upload만, agent_tool은 4로):")
print("        → AI 사용 전에 직접 콘텐츠 생성한 사용자만 잡아 transit 문제 완화")
print("     b) AtRisk 시간 윈도우를 stage별로 차등 (예: Engaged 출신 30일, UsedAI 출신 14일)")
print("        → Engaged였던 사람은 더 오래 inactive해야 진짜 떠난 것으로 봄")
print("     c) 'Stuck@Exploring' 별도 세분화 (no_progress인지 progressed인지 구분):")
print("        → 46% 거대 양동이를 분리. 47%는 product team 액션 타깃")
print("     d) 'Reactivated' state 신설: AtRisk였다가 다시 활동 시작한 사용자 마킹")
print("        → 마케팅/CS 팀이 우선 케어할 segment")

print("\nWROTE: review output above + console log")
