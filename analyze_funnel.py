"""
9단계 funnel 룰 후보를 우리 데이터에 맞춰 검증.
검증 항목:
  1. Specific & Observable: 단계마다 어떤 이벤트로 정의?
  2. Deterministic: 같은 입력 → 같은 답
  3. Complete Coverage: 모든 사용자 분류됨?
  4. Time-Aware: At Risk 단계 동작?
  5. Monotonicity: 누적 reach가 단조 감소?

전체 17,541 사용자에 대한 stage 분포와
다음 단계로의 conversion rate를 출력.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import timedelta

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

print("[1] Loading slim CSV...", flush=True)
events = pd.read_csv(
    CSV, usecols=["person_id", "timestamp", "event"], engine="pyarrow"
)
events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
events["event"] = events["event"].astype("category")
events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
events.reset_index(drop=True, inplace=True)
print(f"    rows={len(events):,}  users={events['person_id'].nunique():,}")

DATA_END = events["timestamp"].max()
print(f"    dataset end: {DATA_END}")

# ──────────────────────────────────────────────────────────────────
# 단계별 이벤트 후보 — 우리 EDA 결과 기반
# ──────────────────────────────────────────────────────────────────
NEW_EVENTS = {"new_user_created", "sign_up"}

# Exploring: onboarding 흐름 + 페이지뷰 — '둘러보다'는 신호
EXPLORE_EVENTS = {
    "$pageview", "$autocapture",
    "submit_onboarding_form", "skip_onboarding_form",
    "notebook_onboarding_tour_started",
    "notebook_onboarding_tour_step",
    "notebook_onboarding_tour_finished",
    "fullscreen_open", "fullscreen_close",
    "notebook_view_canvas_toggle",
}

# Created Content: 캔버스/블록/파일을 실제로 생성/업로드
CREATED_EVENTS = {
    "block_create",
    "files_upload",
    "agent_tool_call_create_block_tool",
}

# Used AI: AI 기능 사용 (생성/대화/에이전트)
AI_EVENTS = {
    "$ai_generation",
    "agent_message",
    "agent_new_chat",
    "agent_start_from_prompt",
    "agent_worker_created",
}

# Wrote Their Own Code: 블록 실행
CODE_EVENTS = {
    "run_block",
    "run_all_blocks",
}

# Used Integration v2: source control + deployment (외부 노출/연결)
# v1은 source_control만 → 138명(0.79%). 너무 좁아서 "외부 도구 사용" 본질 못 잡음.
# v2는 notebook_deployment_* 추가 → "본인 작업물을 외부에 노출"도 integration으로 인정.
INTEGRATION_EVENTS = {
    "source_control_connect_to_canvas",
    "source_control_commit",
    "source_control_pull",
    "notebook_deployment_deployed",
    "notebook_deployment_preview_created",
    "notebook_deployment_updated",
}

# Upgraded
UPGRADE_EVENT = "subscription_upgraded"

# Engagement threshold parameters
ENGAGED_DAYS = 3
AT_RISK_DAYS = 14
AT_RISK_DAYS_ALT = 7

# ──────────────────────────────────────────────────────────────────
# 사용자별 feature 집계 — 한번에 vectorized
# ──────────────────────────────────────────────────────────────────
print("\n[2] Building per-user features...", flush=True)
events["date"] = events["timestamp"].dt.date

# 각 이벤트 카테고리에 속하는지 boolean
ev = events["event"]
events["is_new"]      = ev.isin(NEW_EVENTS)
events["is_explore"]  = ev.isin(EXPLORE_EVENTS)
events["is_created"]  = ev.isin(CREATED_EVENTS)
events["is_ai"]       = ev.isin(AI_EVENTS)
events["is_code"]     = ev.isin(CODE_EVENTS)
events["is_integ"]    = ev.isin(INTEGRATION_EVENTS)
events["is_upgrade"]  = ev.eq(UPGRADE_EVENT)

uf = events.groupby("person_id", sort=False).agg(
    n_events       = ("event",      "size"),
    n_new          = ("is_new",     "sum"),
    n_explore      = ("is_explore", "sum"),
    n_created      = ("is_created", "sum"),
    n_ai           = ("is_ai",      "sum"),
    n_code         = ("is_code",    "sum"),
    n_integ        = ("is_integ",   "sum"),
    n_upgrade      = ("is_upgrade", "sum"),
    distinct_days  = ("date",       "nunique"),
    first_ts       = ("timestamp",  "min"),
    last_ts        = ("timestamp",  "max"),
)
uf["days_since_last"] = (DATA_END - uf["last_ts"]).dt.total_seconds() / 86400
n = len(uf)
print(f"    users in feature table: {n:,}")

# ──────────────────────────────────────────────────────────────────
# 단계별 boolean — "이 사용자가 단계 k의 본질 조건을 만족한 적 있다"
# ──────────────────────────────────────────────────────────────────
b = pd.DataFrame(index=uf.index)
b["s1_new"]        = uf["n_new"] > 0
b["s2_explored"]   = uf["n_explore"] > 0
b["s3_created"]    = uf["n_created"] > 0
b["s4_used_ai"]    = uf["n_ai"] > 0
b["s5_wrote_code"] = uf["n_code"] > 0
b["s6_integrated"] = uf["n_integ"] > 0
b["s7_engaged"]    = (uf["n_ai"] > 0) & (uf["distinct_days"] >= ENGAGED_DAYS)
b["s8_upgraded"]   = uf["n_upgrade"] > 0

# ──────────────────────────────────────────────────────────────────
# (A) 각 단계의 "본질 조건" 단독 reach
# ──────────────────────────────────────────────────────────────────
print("\n=== (A) 단계별 단독 reach (본질 조건만) ===")
for c in b.columns:
    cnt = int(b[c].sum())
    print(f"  {c:<18}  {cnt:>6,}  ({cnt/n*100:>5.2f}%)")

# ──────────────────────────────────────────────────────────────────
# (B) Monotonicity 검사: 단계 k+1 ⊆ 단계 k ?
#     깨지면 "단계 k+1인데 단계 k 조건 미충족" 사용자 수 출력
# ──────────────────────────────────────────────────────────────────
print("\n=== (B) Monotonicity (s(k+1) ⊆ s(k))? — 깨지면 leaks > 0 ===")
order = ["s1_new", "s2_explored", "s3_created", "s4_used_ai",
         "s5_wrote_code", "s6_integrated", "s7_engaged", "s8_upgraded"]
for i in range(len(order) - 1):
    a, c = order[i], order[i + 1]
    leaks = int(((~b[a]) & b[c]).sum())
    print(f"  {c:<18} ⊆ {a:<18} ? leaks={leaks}")

# ──────────────────────────────────────────────────────────────────
# (C) 누적 chained reach: "이 단계까지 순차적으로 다 거쳤다"
#     stage_k_reached = s1 AND s2 AND ... AND sk
#     → 단조 감소 보장
# ──────────────────────────────────────────────────────────────────
print("\n=== (C) Chained cumulative reach (모든 이전 단계 다 충족) ===")
cum = pd.DataFrame(index=uf.index)
prev = pd.Series(True, index=uf.index)
labels = ["1.New", "2.Exploring", "3.Created", "4.UsedAI",
          "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded"]
print(f"  {'stage':<16}{'users':>8}  {'% total':>8}  {'conv from prior':>17}")
prev_n = n
for lbl, col in zip(labels, order):
    cur = prev & b[col]
    cum[lbl] = cur
    cnt = int(cur.sum())
    pct = cnt / n * 100
    conv = (cnt / prev_n * 100) if prev_n else 0.0
    print(f"  {lbl:<16}{cnt:>8,}  {pct:>7.2f}%  {conv:>16.2f}%")
    prev = cur
    prev_n = cnt

# ──────────────────────────────────────────────────────────────────
# (D) "약한" 누적 reach: 단계 k 도달 = "그 단계까지의 어느 조건이든 만족"
#     이전 단계 강제 안 함 → reach 큼, 단조성 깨질 수도 있음
# ──────────────────────────────────────────────────────────────────
print("\n=== (D) Loose cumulative reach (이전 단계 강제 X) ===")
# stage_k_or_higher = b[s_k] OR b[s_{k+1}] OR ...
loose = pd.DataFrame(index=uf.index)
for i, lbl in enumerate(labels):
    mask = b[order[i]].copy()
    for j in range(i + 1, len(order)):
        mask = mask | b[order[j]]
    loose[lbl] = mask
    cnt = int(mask.sum())
    print(f"  {lbl:<16}{cnt:>8,}  ({cnt/n*100:>5.2f}%)")

# ──────────────────────────────────────────────────────────────────
# (E) "highest stage reached" — 사용자별 도달한 가장 높은 단계
#     priority order: 8 > 7 > 6 > 5 > 4 > 3 > 2 > 1 > 0(none)
# ──────────────────────────────────────────────────────────────────
print("\n=== (E) Highest stage reached (사용자별 1개만) ===")
highest = pd.Series(0, index=uf.index, name="highest")
for k, col in enumerate(order, start=1):
    highest[b[col]] = k
counts = highest.value_counts().reindex(range(0, 9), fill_value=0)
stage_names = {0: "0.NoEvent", 1: "1.New", 2: "2.Exploring", 3: "3.Created",
               4: "4.UsedAI", 5: "5.WroteCode", 6: "6.Integrated",
               7: "7.Engaged", 8: "8.Upgraded"}
for k in range(0, 9):
    c = int(counts[k])
    print(f"  {stage_names[k]:<16}{c:>8,}  ({c/n*100:>5.2f}%)")

# ──────────────────────────────────────────────────────────────────
# (F) At Risk 단계 — Time-Aware
#     "단계 4(UsedAI) 이상 도달했지만 마지막 활동이 X일 이상 전" + "업그레이드 X"
#     기준일 = DATA_END (실시간 운영 시엔 'asof' 시점)
# ──────────────────────────────────────────────────────────────────
print(f"\n=== (F) At Risk @ asof = DATA_END ===")
for thresh in [7, 14, 30]:
    at_risk = (
        (highest >= 4) &              # 4단계(UsedAI) 이상 도달했어야
        (~b["s8_upgraded"]) &         # 업그레이드 안 함
        (uf["days_since_last"] >= thresh)
    )
    cnt = int(at_risk.sum())
    pop = int((highest >= 4).sum())
    print(f"  AT_RISK_DAYS={thresh:>2}  at_risk={cnt:>5,}  "
          f"({cnt/pop*100:.1f}% of UsedAI+ pop, {cnt/n*100:.1f}% of all)")

# 최종: AT_RISK_DAYS=14 채택
at_risk_mask = (
    (highest >= 4) & (~b["s8_upgraded"]) &
    (uf["days_since_last"] >= AT_RISK_DAYS)
)

# ──────────────────────────────────────────────────────────────────
# (G) 최종 9단계 분류 — 사용자별 1개 라벨 (At Risk 우선 적용)
# ──────────────────────────────────────────────────────────────────
final_stage = highest.map(stage_names).copy()
# At Risk override (단, Upgraded는 At Risk보다 우선 — 이미 결제했으니)
override = at_risk_mask & (~b["s8_upgraded"])
final_stage[override] = "9.AtRisk"

print(f"\n=== (G) FINAL 9-STAGE DISTRIBUTION (asof = DATA_END, at_risk={AT_RISK_DAYS}d) ===")
final_order = ["0.NoEvent", "1.New", "2.Exploring", "3.Created", "4.UsedAI",
               "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded", "9.AtRisk"]
fc = final_stage.value_counts().reindex(final_order, fill_value=0).astype(int)
for s in final_order:
    c = int(fc[s])
    print(f"  {s:<16}{c:>8,}  ({c/n*100:>5.2f}%)")
print(f"  {'TOTAL':<16}{int(fc.sum()):>8,}  (sanity: must equal {n:,})")

# 업그레이드 conversion 단계별 (E의 highest 기반)
print(f"\n=== (H) 단계별 업그레이드 전환율 (highest stage 기준) ===")
for k in range(0, 9):
    sel = (highest == k)
    total = int(sel.sum())
    if total == 0:
        continue
    upg = int((sel & b["s8_upgraded"]).sum())
    print(f"  reached_max={stage_names[k]:<14}  users={total:>6,}  "
          f"upgraders={upg:>4,}  ({upg/total*100:.2f}%)")

# ──────────────────────────────────────────────────────────────────
# (I) 단계별 사용자가 어떻게 다음 단계로 갔나 — 시간순 transition matrix
#     사용자별 시간순 이벤트를 따라가며 단계 라벨 변경 시점을 기록
#     (간단 버전: 도달한 단계들의 sequence만 추출)
# ──────────────────────────────────────────────────────────────────
print(f"\n=== (I) 시간순 단계 진행 시퀀스 ===")
# 각 사용자의 stage milestones (어느 단계에 처음 도달했는지)
stage_first_ts = {col: events.loc[events["event"].isin(_get_set(col)),
                                    ["person_id", "timestamp"]]
                                  .groupby("person_id")["timestamp"].min()
                  for col, _get_set in [
                      ("s1_new",        lambda c=None: NEW_EVENTS),
                      ("s2_explored",   lambda c=None: EXPLORE_EVENTS),
                      ("s3_created",    lambda c=None: CREATED_EVENTS),
                      ("s4_used_ai",    lambda c=None: AI_EVENTS),
                      ("s5_wrote_code", lambda c=None: CODE_EVENTS),
                      ("s6_integrated", lambda c=None: INTEGRATION_EVENTS),
                      ("s8_upgraded",   lambda c=None: {UPGRADE_EVENT}),
                  ]}
# 출력용 — 단계 도달 비율 + 평균 도달까지 시간(가입 후)
print(f"  단계         도달자  median_hours_from_first_event")
for col in ["s1_new", "s2_explored", "s3_created", "s4_used_ai",
            "s5_wrote_code", "s6_integrated", "s8_upgraded"]:
    ts_first = stage_first_ts[col]
    common = ts_first.index.intersection(uf.index)
    delta = (ts_first.loc[common] - uf.loc[common, "first_ts"]).dt.total_seconds() / 3600
    if len(delta):
        print(f"  {col:<16}  {len(delta):>6,}  median={delta.median():.2f}h  p90={delta.quantile(0.9):.2f}h")

# 결과 저장
out = pd.concat([uf, b, highest.rename("highest_stage_num"),
                 final_stage.rename("final_stage")], axis=1)
out.to_csv("/Users/hunjunsin/Desktop/zerve/funnel_user_assignment.csv", index=True)
print(f"\nWROTE /Users/hunjunsin/Desktop/zerve/funnel_user_assignment.csv "
      f"(per-user stage assignment table)")
