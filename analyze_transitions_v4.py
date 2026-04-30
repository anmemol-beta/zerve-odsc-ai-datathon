"""
v4 Transition Matrix — 8.Upgraded 분해 반영 (Active / AtRisk / Churned)

핵심 변경점:
  v3: Upgraded는 final state. Upgrade 후 행동 무시.
  v4: Upgrade 후 lifecycle 추적
       8.Upgraded → 9.AtRisk@Upgraded → 9.Churned@Upgraded

산출물:
  (A) Stage milestone 타임스탬프 (1~8)
  (B) Adjacent transition matrix (v4 final state까지 포함)
  (C) Stage k → v4 outcome 분포 (15-category)
  (D) Post-upgrade lifecycle 분석:
       - Upgrade → Downgrade event까지 median days
       - Upgrade → Inactive(30d+) 진입까지 median days
       - Upgrade → Cancel까지 median days
  (E) v4 final state 도달 시간 분포
  (F) 재활성화 패턴: 어느 AtRisk@X에서 어느 active stage로 돌아갔나
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from collections import Counter
import sys

sys.path.insert(0, "/Users/hunjunsin/Desktop/zerve")
from funnel_v4 import (
    classify_users_v4, NEW_EVENTS, EXPLORE_EVENTS, CREATED_EVENTS,
    AI_EVENTS, CODE_EVENTS, INTEG_EVENTS, ENGAGEMENT_EVENTS, UPGRADE_EVENT,
    DOWNGRADE_EVENTS, CANCEL_EVENTS, ENGAGED_DAYS,
    AT_RISK_DAYS, UPGRADE_INACTIVE_DAYS, STAGE_NAMES,
)

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

print("[1] Loading...", flush=True)
events = pd.read_csv(
    CSV,
    usecols=["person_id", "timestamp", "event", "person_properties.purpose"],
    engine="pyarrow",
)
events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
DATA_END = events["timestamp"].max()
N = events["person_id"].nunique()
print(f"    rows={len(events):,}  users={N:,}")

# v4 분류
print("\n[2] Classifying with v4...", flush=True)
v4 = classify_users_v4(events, DATA_END)

# ──────────────────────────────────────────────────────────────────
# (A) Milestone 타임스탬프
# ──────────────────────────────────────────────────────────────────
print("\n[3] Computing milestones (stages 1-8 + post-upgrade events)...", flush=True)

def first_ts(evset):
    return events.loc[events["event"].isin(evset)].groupby("person_id")["timestamp"].min()

t1 = first_ts(NEW_EVENTS); t2 = first_ts(EXPLORE_EVENTS)
t3 = first_ts(CREATED_EVENTS); t4 = first_ts(AI_EVENTS)
t5 = first_ts(CODE_EVENTS); t6 = first_ts(INTEG_EVENTS)
t8 = events.loc[events["event"] == UPGRADE_EVENT].groupby("person_id")["timestamp"].min()

# Engaged
eng = events.loc[events["event"].isin(ENGAGEMENT_EVENTS), ["person_id", "timestamp"]].copy()
eng["date"] = eng["timestamp"].dt.date
eng = eng.sort_values(["person_id", "timestamp"])
fpd = eng.drop_duplicates(["person_id", "date"], keep="first").sort_values(
    ["person_id", "timestamp"]
)
fpd["day_idx"] = fpd.groupby("person_id").cumcount()
t7 = fpd.loc[fpd["day_idx"] == 2].set_index("person_id")["timestamp"]

# Post-upgrade events
upgr = set(events.loc[events["event"] == UPGRADE_EVENT, "person_id"].unique())
upg_first_ts = t8

# 첫 다운그레이드 (업그레이드 이후만)
dg = events.loc[events["event"].isin(DOWNGRADE_EVENTS) & events["person_id"].isin(upgr)].copy()
dg["upg_ts"] = dg["person_id"].map(upg_first_ts)
dg = dg.loc[dg["timestamp"] > dg["upg_ts"]]
t_dg = dg.groupby("person_id")["timestamp"].min()

# 첫 cancel
cn = events.loc[events["event"].isin(CANCEL_EVENTS) & events["person_id"].isin(upgr)].copy()
cn["upg_ts"] = cn["person_id"].map(upg_first_ts)
cn = cn.loc[cn["timestamp"] > cn["upg_ts"]]
t_cn = cn.groupby("person_id")["timestamp"].min()

all_users = pd.Index(events["person_id"].unique(), name="person_id")
mile = pd.DataFrame(index=all_users)
mile["t1"] = t1; mile["t2"] = t2; mile["t3"] = t3; mile["t4"] = t4
mile["t5"] = t5; mile["t6"] = t6; mile["t7"] = t7; mile["t8"] = t8
mile["t_dg"] = t_dg
mile["t_cn"] = t_cn

# 추가: 마지막 활동 + AtRisk 진입 시점 (= last_ts + threshold)
last_ts = events.groupby("person_id")["timestamp"].max()
mile["last_ts"] = last_ts
mile["upgraded"] = mile["t8"].notna()

# AtRisk@Upgraded 진입 = upgrade 후 inactive 30일 진입 시점
# = max(t8 + 30d, last_ts + 30d) — 결제 후 30일간 활동 없으면 진입
# 단순화: last_ts + 30 (단, 결제자만)
mile["t_atrisk_upg"] = mile["last_ts"] + pd.Timedelta(days=UPGRADE_INACTIVE_DAYS)
mile.loc[~mile["upgraded"], "t_atrisk_upg"] = pd.NaT
# 단, AtRisk@Upgraded가 실제 발효되려면 DATA_END > t_atrisk_upg 이어야 함
mile.loc[mile["t_atrisk_upg"] > DATA_END, "t_atrisk_upg"] = pd.NaT

# Churned@Upgraded 진입 = downgrade + inactive 둘 다 발생한 시점, 또는 cancel
# 단순화: cancel 시점 OR (downgrade 시점 if inactive 발생도 했음)
def churned_ts(row):
    if pd.notna(row["t_cn"]):
        return row["t_cn"]
    # downgrade가 있고 + AtRisk 진입한 경우
    if pd.notna(row["t_dg"]) and pd.notna(row["t_atrisk_upg"]):
        return max(row["t_dg"], row["t_atrisk_upg"])
    return pd.NaT
mile["t_churned_upg"] = mile.apply(churned_ts, axis=1)

# v4 final state
mile = mile.join(v4[["final_stage"]])

# ──────────────────────────────────────────────────────────────────
# (B) Stage k → v4 outcome 분포
# ──────────────────────────────────────────────────────────────────
print("\n=== (B) Stage k 도달자의 v4 최종 상태 분포 ===")
v4_outcomes = ["8.Upgraded", "9.AtRisk@Upgraded", "9.Churned@Upgraded",
               "9.AtRisk@UsedAI", "9.AtRisk@WroteCode",
               "9.AtRisk@Integrated", "9.AtRisk@Engaged", "active"]

print(f"  {'reached':<14} {'users':>7}  ", end="")
for o in ["8.Upg", "AR@Upg", "Ch@Upg", "AR@UsAI", "AR@Code", "AR@Int", "AR@Eng", "active"]:
    print(f"{o:>9}", end="")
print()
for k in range(1, 8):
    reached = mile[f"t{k}"].notna()
    n_reached = int(reached.sum())
    if n_reached == 0: continue
    sub = mile[reached]
    counts = sub["final_stage"].value_counts()
    upg_a = int(counts.get("8.Upgraded", 0))
    upg_ar = int(counts.get("9.AtRisk@Upgraded", 0))
    upg_ch = int(counts.get("9.Churned@Upgraded", 0))
    ar_used = int(counts.get("9.AtRisk@UsedAI", 0))
    ar_code = int(counts.get("9.AtRisk@WroteCode", 0))
    ar_int = int(counts.get("9.AtRisk@Integrated", 0))
    ar_eng = int(counts.get("9.AtRisk@Engaged", 0))
    active = n_reached - upg_a - upg_ar - upg_ch - ar_used - ar_code - ar_int - ar_eng
    print(f"  {STAGE_NAMES[k]:<14} {n_reached:>7,}  ", end="")
    for v in [upg_a, upg_ar, upg_ch, ar_used, ar_code, ar_int, ar_eng, active]:
        pct = v / n_reached * 100
        print(f"{pct:>7.1f}%", end=" ")
    print()

# ──────────────────────────────────────────────────────────────────
# (C) Post-upgrade lifecycle 시간 분석
# ──────────────────────────────────────────────────────────────────
print("\n=== (C) Post-upgrade lifecycle 시간 분포 ===")

# Upgrade → Downgrade
delta_dg = (mile["t_dg"] - mile["t8"]).dt.total_seconds() / 86400
delta_dg = delta_dg.dropna()
print(f"  Upgrade → first Downgrade event:")
print(f"    n={len(delta_dg)}, median={delta_dg.median():.2f}d, "
      f"p25={delta_dg.quantile(.25):.2f}d, p75={delta_dg.quantile(.75):.2f}d, "
      f"max={delta_dg.max():.1f}d")

# Upgrade → Cancel
delta_cn = (mile["t_cn"] - mile["t8"]).dt.total_seconds() / 86400
delta_cn = delta_cn.dropna()
print(f"  Upgrade → first Cancel event:")
print(f"    n={len(delta_cn)}, median={delta_cn.median():.2f}d, "
      f"p75={delta_cn.quantile(.75) if len(delta_cn) else 0:.2f}d, "
      f"max={delta_cn.max() if len(delta_cn) else 0:.1f}d")

# Upgrade → AtRisk@Upgraded 진입
delta_ar = (mile["t_atrisk_upg"] - mile["t8"]).dt.total_seconds() / 86400
delta_ar = delta_ar.dropna()
delta_ar = delta_ar[delta_ar > 0]
print(f"  Upgrade → AtRisk@Upgraded entry (≈last_event + 30d):")
print(f"    n={len(delta_ar)}, median={delta_ar.median():.2f}d, "
      f"p25={delta_ar.quantile(.25):.2f}d, p75={delta_ar.quantile(.75):.2f}d")

# ──────────────────────────────────────────────────────────────────
# (D) Adjacent transition matrix — v4 final state를 sink로 추가
# ──────────────────────────────────────────────────────────────────
print("\n=== (D) Adjacent transition matrix (stage k → 다음 milestone) ===")
long = mile[[f"t{k}" for k in range(1,9)]].reset_index().melt(
    id_vars="person_id", var_name="col", value_name="ts"
).dropna(subset=["ts"])
long["stage"] = long["col"].str[1:].astype(int)
long = long.sort_values(["person_id", "ts"]).reset_index(drop=True)
long["next_stage"] = long.groupby("person_id")["stage"].shift(-1)

pairs = long.dropna(subset=["next_stage"]).copy()
pairs["next_stage"] = pairs["next_stage"].astype(int)
trans = pairs.groupby(["stage", "next_stage"]).size().unstack(fill_value=0)
trans = trans.reindex(index=range(1,9), columns=range(1,9), fill_value=0)

print(f"\n  v4 transition counts FROM → TO:")
print(f"     {'TO →':>10}", end="")
for j in range(1, 9): print(f"{j:>7}", end="")
print()
for i in range(1, 9):
    print(f"  FROM {i}  ", end="")
    for j in range(1, 9):
        v = int(trans.loc[i, j]) if j in trans.columns else 0
        print(f"{v:>7,}", end="")
    print(f"   {STAGE_NAMES[i]}")

# 종료 상태 (8 도달 후 어디로 갔나?)
print(f"\n  업그레이더 323명의 v4 종료 상태:")
print(f"    8.Upgraded (active):     {int((mile['final_stage'] == '8.Upgraded').sum())}")
print(f"    9.AtRisk@Upgraded:        {int((mile['final_stage'] == '9.AtRisk@Upgraded').sum())}")
print(f"    9.Churned@Upgraded:      {int((mile['final_stage'] == '9.Churned@Upgraded').sum())}")

# ──────────────────────────────────────────────────────────────────
# (E) Top user paths (v4 final state)
# ──────────────────────────────────────────────────────────────────
print("\n=== (E) Top 사용자 경로 (시간순 stage + v4 종료 상태) ===")
user_seq = long.groupby("person_id")["stage"].apply(
    lambda s: tuple(int(x) for x in s.tolist())
)

paths = []
for pid, seq in user_seq.items():
    end = mile.loc[pid, "final_stage"]
    if pd.isna(end): end = "→active"
    elif end.startswith("9."): end = f"→{end[2:]}"
    elif end.startswith("8."): end = "→Upgraded@Active"
    else: end = "→active"
    paths.append(seq + (end,))
no_event = N - len(user_seq)
print(f"  (어떤 단계도 도달 못한 사용자: {no_event:,})")

cnt = Counter(paths)
print(f"\n  TOP 15 경로 (전체):")
for p, c in cnt.most_common(15):
    pretty = " → ".join(STAGE_NAMES[s] if isinstance(s, int) else s for s in p)
    print(f"    {c:>6,}  ({c/N*100:>5.2f}%)  {pretty}")

# 업그레이드 후 lifecycle paths 분리
print(f"\n  업그레이더의 Top 10 경로 (v4 종료 상태로):")
upg_paths = [p for p in paths if any("Upgraded" in str(x) or "Churned" in str(x) for x in p)]
for p, c in Counter(upg_paths).most_common(10):
    pretty = " → ".join(STAGE_NAMES[s] if isinstance(s, int) else s for s in p)
    print(f"    {c:>4}  {pretty}")

# AtRisk@Upgraded와 Churned@Upgraded 사용자들의 prior journey
print(f"\n  AtRisk@Upgraded → 어떤 prior path?")
ar_upg_paths = [p for p in paths if "AtRisk@Upgraded" in str(p[-1])]
for p, c in Counter(ar_upg_paths).most_common(5):
    pretty = " → ".join(STAGE_NAMES[s] if isinstance(s, int) else s for s in p)
    print(f"    {c:>3}  {pretty}")

print(f"\n  Churned@Upgraded → 어떤 prior path?")
ch_upg_paths = [p for p in paths if "Churned@Upgraded" in str(p[-1])]
for p, c in Counter(ch_upg_paths).most_common(5):
    pretty = " → ".join(STAGE_NAMES[s] if isinstance(s, int) else s for s in p)
    print(f"    {c:>3}  {pretty}")

# ──────────────────────────────────────────────────────────────────
# (F) Loose cumulative reach + drop-off (v4)
# ──────────────────────────────────────────────────────────────────
print("\n=== (F) v4 누적 reach + drop-off ===")
reach = pd.Series(dtype=int)
for k in range(1, 9):
    reach[STAGE_NAMES[k]] = mile[[f"t{j}" for j in range(k, 9)]].notna().any(axis=1).sum()
# Active Upgraded만
reach["8.Upgraded (active only)"] = (mile["final_stage"] == "8.Upgraded").sum()
reach["9.AtRisk@Upgraded"] = (mile["final_stage"] == "9.AtRisk@Upgraded").sum()
reach["9.Churned@Upgraded"] = (mile["final_stage"] == "9.Churned@Upgraded").sum()

print(f"  {'stage':<28} {'reach':>7}  {'% total':>8}")
prev_n = N
for s, r in reach.items():
    r = int(r)
    pct = r / N * 100
    drop = (1 - r/prev_n) * 100 if prev_n else 0
    print(f"  {s:<28} {r:>7,}  {pct:>7.2f}%  drop_from_prev={drop:>5.1f}%")
    prev_n = r

# ──────────────────────────────────────────────────────────────────
# (G) Cohort: AtRisk@Engaged → Upgrade로 회복? + AtRisk@Upgraded → Churned로?
# ──────────────────────────────────────────────────────────────────
print("\n=== (G) AtRisk transitions over time (60일 전 → 지금) ===")
prev = classify_users_v4(events, DATA_END - pd.Timedelta(days=60))
common = prev.index.intersection(v4.index)

# 60일 전 8.Upgraded → 지금?
prev_upg = prev.loc[common, "final_stage"] == "8.Upgraded"
cur_states = v4.loc[common[prev_upg], "final_stage"].value_counts()
print(f"  60일 전 8.Upgraded → 60일 후:")
total_pu = int(prev_upg.sum())
for s, c in cur_states.items():
    print(f"    {s:<24} {c:>4}  ({c/total_pu*100:>5.1f}%)")

# 60일 전 AtRisk@X → 회복 여부
print(f"\n  60일 전 AtRisk@X → 60일 후 active 회복 비율:")
for ar in ["9.AtRisk@UsedAI", "9.AtRisk@WroteCode", "9.AtRisk@Integrated",
           "9.AtRisk@Engaged", "9.AtRisk@Upgraded"]:
    mask = prev.loc[common, "final_stage"] == ar
    n = int(mask.sum())
    if n == 0: continue
    cur = v4.loc[common[mask], "final_stage"]
    n_back = (~cur.str.startswith("9.")).sum()
    n_upg = (cur == "8.Upgraded").sum()
    n_churned = (cur == "9.Churned@Upgraded").sum()
    print(f"    {ar:<24} n={n:>4}  back_to_active={n_back/n*100:>5.1f}%  "
          f"became_8.Upgraded={n_upg/n*100:.1f}%  →Churned={n_churned/n*100:.1f}%")

# 결과 저장
mile.to_csv("/Users/hunjunsin/Desktop/zerve/funnel_v4_milestones.csv")
trans.to_csv("/Users/hunjunsin/Desktop/zerve/transition_v4_counts.csv")
print(f"\nWROTE: funnel_v4_milestones.csv, transition_v4_counts.csv")
