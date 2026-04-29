"""
Transition Matrix & Drop-off 분석 (미션 2 - Behavioral Modeling 25점)

산출물:
  (A) 사용자별 stage milestone timestamps (t1...t8)
  (B) 인접 전이 행렬: stage_i → stage_j (다음 milestone이 j인 사용자 수)
  (C) Stage k → Outcome 분포 (Progressed / Stuck / AtRisk / Upgraded)
  (D) 단계 간 평균/median 도달 시간
  (E) Top-N 사용자 경로 (가장 흔한 stage sequence)
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from collections import Counter

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

# ──────────────────────────────────────────────────────────────────
# v2 룰 (분석된 결과 그대로 재사용)
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
AT_RISK_DAYS = 14

STAGE_NAMES = {
    1: "1.New", 2: "2.Exploring", 3: "3.Created", 4: "4.UsedAI",
    5: "5.WroteCode", 6: "6.Integrated", 7: "7.Engaged", 8: "8.Upgraded",
}

# ──────────────────────────────────────────────────────────────────
print("[1] Loading...", flush=True)
events = pd.read_csv(CSV, usecols=["person_id", "timestamp", "event"], engine="pyarrow")
events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
DATA_END = events["timestamp"].max()
N_USERS = events["person_id"].nunique()
print(f"    rows={len(events):,}  users={N_USERS:,}  data_end={DATA_END}")

# ──────────────────────────────────────────────────────────────────
# (A) 사용자별 각 단계 첫 도달 timestamp
# ──────────────────────────────────────────────────────────────────
print("\n[2] Computing stage milestones per user...", flush=True)

def first_ts_for(evset):
    return events[events["event"].isin(evset)].groupby("person_id")["timestamp"].min()

t1 = first_ts_for(NEW_EVENTS)
t2 = first_ts_for(EXPLORE_EVENTS)
t3 = first_ts_for(CREATED_EVENTS)
t4 = first_ts_for(AI_EVENTS)
t5 = first_ts_for(CODE_EVENTS)
t6 = first_ts_for(INTEG_EVENTS)
t8 = events[events["event"] == UPGRADE_EVENT].groupby("person_id")["timestamp"].min()

# Stage 7 (Engaged): AI + 3 distinct days. 가장 이른 "AI를 한 3번째 distinct day"의 첫 AI 이벤트.
ai_ev = events[events["event"].isin(AI_EVENTS)][["person_id", "timestamp"]].copy()
ai_ev["date"] = ai_ev["timestamp"].dt.date
ai_ev = ai_ev.sort_values(["person_id", "timestamp"])

def engaged_first_ts(g):
    distinct = []
    for d in g["date"]:
        if not distinct or d != distinct[-1]:
            distinct.append(d)
        if len(distinct) >= 3:
            target = distinct[2]
            return g.loc[g["date"] == target, "timestamp"].iloc[0]
    return None

# 빠르게: 사용자별 distinct dates list, 3번째 date의 첫 ts
ai_dates = ai_ev.groupby("person_id")["date"].agg(lambda s: list(dict.fromkeys(s)))
def get_3rd_date(dates):
    return dates[2] if len(dates) >= 3 else None
ai_third_date = ai_dates.apply(get_3rd_date)
ai_third_date = ai_third_date.dropna()
# 그 3번째 date에 첫 AI 이벤트 시각
ai_ev_indexed = ai_ev.set_index("person_id")
t7_list = []
for pid, d3 in ai_third_date.items():
    rows = ai_ev_indexed.loc[[pid]] if pid in ai_ev_indexed.index else None
    if rows is None: continue
    if isinstance(rows, pd.Series): rows = rows.to_frame().T
    sub = rows[rows["date"] == d3]
    if len(sub):
        t7_list.append((pid, sub["timestamp"].min()))
t7 = pd.Series(dict(t7_list), name="t7")

# Build milestone dataframe
all_users = pd.Index(events["person_id"].unique(), name="person_id")
mile = pd.DataFrame(index=all_users)
mile["t1"] = t1
mile["t2"] = t2
mile["t3"] = t3
mile["t4"] = t4
mile["t5"] = t5
mile["t6"] = t6
mile["t7"] = t7
mile["t8"] = t8

# 도달 사용자 수 출력
print(f"\n    Stage milestone reach (사용자가 그 단계 처음 도달한 시점이 있는가):")
for k in range(1, 9):
    cnt = mile[f"t{k}"].notna().sum()
    print(f"      stage {k} ({STAGE_NAMES[k]:<14}) : {cnt:>6,}  ({cnt/N_USERS*100:>5.2f}%)")

# 마지막 활동 + AtRisk flag
last_ts = events.groupby("person_id")["timestamp"].max()
mile["last_ts"] = last_ts
mile["days_since_last"] = (DATA_END - mile["last_ts"]).dt.total_seconds() / 86400
mile["upgraded"] = mile["t8"].notna()
mile["at_risk"] = (
    (mile[["t4","t5","t6","t7"]].notna().any(axis=1)) &
    (~mile["upgraded"]) &
    (mile["days_since_last"] >= AT_RISK_DAYS)
)

# ──────────────────────────────────────────────────────────────────
# (B) 인접 전이 행렬 — 각 사용자의 milestone 시퀀스에서 (i → next) 카운트
# ──────────────────────────────────────────────────────────────────
print("\n[3] Building transition matrix (adjacent milestones)...", flush=True)

# wide → long
long = mile[[f"t{k}" for k in range(1,9)]].reset_index().melt(
    id_vars="person_id", var_name="stage_col", value_name="ts"
).dropna(subset=["ts"])
long["stage"] = long["stage_col"].str[1:].astype(int)
long = long.sort_values(["person_id", "ts"]).reset_index(drop=True)
long["next_stage"] = long.groupby("person_id")["stage"].shift(-1)

# 마지막 milestone 후의 outcome 결정
# - Upgraded(8 도달)면 "Upgraded"
# - AtRisk면 "AtRisk"
# - 그 외면 "Stuck@K" (현재 K가 highest이고 활동 중)
mile["highest"] = mile[[f"t{k}" for k in range(1,9)]].notna().mul(range(1,9)).max(axis=1).fillna(0).astype(int)

# 인접 전이 카운트
pairs = long.dropna(subset=["next_stage"])
pairs["next_stage"] = pairs["next_stage"].astype(int)
trans_counts = pairs.groupby(["stage", "next_stage"]).size().unstack(fill_value=0)
# 9x9 형태로 보기 쉽게 정리
trans_counts = trans_counts.reindex(index=range(1,9), columns=range(1,9), fill_value=0)
print("\n=== (B) 인접 전이 행렬 (stage_i 다음 milestone이 stage_j인 사용자 수) ===")
print(f"     {'TO →':>10}", end="")
for j in range(1, 9):
    print(f"{j:>7}", end="")
print()
for i in range(1, 9):
    print(f"  FROM {i}  ", end="")
    for j in range(1, 9):
        v = int(trans_counts.loc[i, j]) if j in trans_counts.columns else 0
        print(f"{v:>7,}", end="")
    print(f"   {STAGE_NAMES[i]}")

# 행 정규화 (확률)
print("\n=== (B') 인접 전이 확률 P(next=j | from=i) ===")
print(f"     {'TO →':>10}", end="")
for j in range(1, 9):
    print(f"{j:>7}", end="")
print()
row_sums = trans_counts.sum(axis=1).replace(0, 1)
trans_prob = trans_counts.div(row_sums, axis=0)
for i in range(1, 9):
    print(f"  FROM {i}  ", end="")
    for j in range(1, 9):
        v = trans_prob.loc[i, j] if j in trans_prob.columns else 0.0
        print(f"{v:>6.1%}", end=" ")
    print(f"  {STAGE_NAMES[i]}")

# ──────────────────────────────────────────────────────────────────
# (C) Stage k → Outcome (시점 DATA_END 기준 최종 상태)
# ──────────────────────────────────────────────────────────────────
print("\n=== (C) Stage k 도달자의 최종 상태 분포 (asof = DATA_END) ===")
print(f"  {'reached':<14} {'users':>7}  {'progressed':>11}  {'upgraded':>10}  {'atrisk':>8}  {'stuck':>8}")
for k in range(1, 8):  # 8은 Upgraded이므로 스킵
    reached = mile[f"t{k}"].notna()
    n_reached = int(reached.sum())
    if n_reached == 0:
        continue
    sub = mile[reached].copy()
    # 도달했으면서 더 높은 단계 도달했나?
    progressed = sub[[f"t{j}" for j in range(k+1, 9)]].notna().any(axis=1)
    upgraded = sub["upgraded"]
    atrisk = sub["at_risk"]
    # Stuck = 진행 안 했고 업그레이드 안 했고 AtRisk도 아님 (= 최근 활동 중인데 더 이상 진척 없음)
    stuck = (~progressed) & (~upgraded) & (~atrisk)
    n_prog = int(progressed.sum())
    n_upg = int(upgraded.sum())
    n_ar = int(atrisk.sum())
    n_st = int(stuck.sum())
    print(f"  {STAGE_NAMES[k]:<14} {n_reached:>7,}  "
          f"{n_prog/n_reached:>10.1%}  {n_upg/n_reached:>9.1%}  "
          f"{n_ar/n_reached:>7.1%}  {n_st/n_reached:>7.1%}")

# ──────────────────────────────────────────────────────────────────
# (D) 단계 간 도달 시간 (median, p25/p75)
# ──────────────────────────────────────────────────────────────────
print("\n=== (D) 인접 전이의 시간 분포 (시간 단위, 도달자 한정) ===")
print(f"  {'transition':<22} {'n':>6}  {'p25':>8}  {'median':>8}  {'p75':>8}  {'p90':>8}")
# wide format에서 (t_k -> t_{k+1}) 직접 계산. 단, "다음으로 도달한" 단계 기준이 더 정확.
# 우선은 인접 단계만: (1→2), (2→3), ..., (7→8).
for k in range(1, 8):
    a, b = f"t{k}", f"t{k+1}"
    if a not in mile.columns or b not in mile.columns: continue
    delta = (mile[b] - mile[a]).dt.total_seconds() / 3600
    delta = delta.dropna()
    delta = delta[delta >= 0]   # 음수는 stage 7(engaged)이 stage 4 이전 발생할 수 없도록 필터
    if len(delta) == 0: continue
    name = f"{STAGE_NAMES[k]} → {STAGE_NAMES[k+1]}"
    print(f"  {name:<22} {len(delta):>6,}  "
          f"{delta.quantile(.25):>7.2f}h  {delta.median():>7.2f}h  "
          f"{delta.quantile(.75):>7.2f}h  {delta.quantile(.90):>7.2f}h")

# Engaged → Upgraded 별도 (가장 중요한 비즈니스 전환)
delta_eng_upg = (mile["t8"] - mile["t7"]).dt.total_seconds() / 86400
delta_eng_upg = delta_eng_upg.dropna()
delta_eng_upg = delta_eng_upg[delta_eng_upg >= 0]
if len(delta_eng_upg):
    print(f"\n  Engaged → Upgraded (days): n={len(delta_eng_upg)}, "
          f"median={delta_eng_upg.median():.1f}d, p90={delta_eng_upg.quantile(0.9):.1f}d")

# Upgraded 기준으로 가입(첫 이벤트)부터 결제까지
first_ts = events.groupby("person_id")["timestamp"].min()
delta_signup_upg = (mile["t8"] - first_ts).dt.total_seconds() / 86400
delta_signup_upg = delta_signup_upg.dropna()
print(f"  First event → Upgraded (days): n={len(delta_signup_upg)}, "
      f"median={delta_signup_upg.median():.2f}d, p25={delta_signup_upg.quantile(.25):.3f}d, "
      f"p75={delta_signup_upg.quantile(.75):.1f}d")

# ──────────────────────────────────────────────────────────────────
# (E) Top-N 사용자 경로 (시간순 stage 시퀀스)
# ──────────────────────────────────────────────────────────────────
print("\n=== (E) Top 사용자 경로 (시간순 stage 시퀀스 + 종료 상태) ===")
# 사용자별 stage 시퀀스 (도달한 단계만, 시간순)
user_seq = long.groupby("person_id")["stage"].apply(
    lambda s: tuple(int(x) for x in s.tolist())
)

# 종료 상태 라벨
def end_label(pid):
    if mile.loc[pid, "upgraded"]:
        return "→Upgraded"
    if mile.loc[pid, "at_risk"]:
        return "→AtRisk"
    return "→active"

paths = []
for pid, seq in user_seq.items():
    paths.append(seq + (end_label(pid),))
# 빈 시퀀스 (이벤트만 있고 단계 미도달) 처리
no_event_users = N_USERS - len(user_seq)
print(f"  (참고: 어떤 단계도 도달하지 않은 사용자 = {no_event_users:,})")

path_counter = Counter(paths)
print(f"\n  TOP 20 경로:")
for p, c in path_counter.most_common(20):
    pretty = " → ".join(STAGE_NAMES[s] if isinstance(s, int) else s for s in p)
    print(f"    {c:>6,}  ({c/N_USERS*100:>5.2f}%)  {pretty}")

# Upgraded만 따로
print(f"\n  TOP 10 경로 (Upgraded만):")
upg_paths = [p for p in paths if p[-1] == "→Upgraded"]
for p, c in Counter(upg_paths).most_common(10):
    pretty = " → ".join(STAGE_NAMES[s] if isinstance(s, int) else s for s in p)
    print(f"    {c:>6,}  ({c/len(upg_paths)*100:>5.1f}% of upgraders)  {pretty}")

# ──────────────────────────────────────────────────────────────────
# (F) 핵심 비즈니스 funnel: 누적 reach + drop-off 막대 자료
# ──────────────────────────────────────────────────────────────────
print("\n=== (F) 누적 reach + drop-off (loose: 그 단계 OR 더 위까지 도달) ===")
print(f"  {'stage':<14} {'reach':>7}  {'% total':>8}  {'drop_from_prev':>14}")
prev_n = N_USERS
for k in range(1, 9):
    cur_or_higher = mile[[f"t{j}" for j in range(k, 9)]].notna().any(axis=1).sum()
    pct = cur_or_higher / N_USERS * 100
    drop = (1 - cur_or_higher / prev_n) * 100 if prev_n else 0
    print(f"  {STAGE_NAMES[k]:<14} {int(cur_or_higher):>7,}  {pct:>7.2f}%  {drop:>13.1f}%")
    prev_n = cur_or_higher

# 결과 저장
mile.to_csv("/Users/hunjunsin/Desktop/zerve/funnel_milestones.csv")
trans_counts.to_csv("/Users/hunjunsin/Desktop/zerve/transition_matrix_counts.csv")
trans_prob.to_csv("/Users/hunjunsin/Desktop/zerve/transition_matrix_probs.csv")
print("\nWROTE: funnel_milestones.csv, transition_matrix_counts.csv, transition_matrix_probs.csv")
