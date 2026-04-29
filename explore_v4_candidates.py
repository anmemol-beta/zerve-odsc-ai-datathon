"""
v4 분류 후보 탐색 — 깊이 있는 segmentation 발굴.

검토 후보 (가설):
  H1. 8.Upgraded 세분화 (Active / Downgraded / Churned)        [기확인]
  H2. Reactivated state (AtRisk → 다시 활성화)
  H3. Onboarding completion (tour 완료 vs skip vs incomplete)
  H4. Promo/Trial 경로 사용자 (promo_code_redeemed 등)
  H5. Frustrated sub-state (높은 $exception 비율)
  H6. Power Engaged vs Casual Engaged (활동 강도 차이)
  H7. Agent-first vs Notebook-first 사용자 (제품 표면 차이)
  H8. Personal vs Company purpose 별 funnel 차이
  H9. Deployment 성공/실패 분리
  H10. Bot/Outlier 사용자 (이벤트 수 비정상)

각 후보에 대해:
  - 모집단 크기
  - 행동 구분점
  - 업그레이드율 차이
  - 채택 여부 권장
"""
from __future__ import annotations
import pandas as pd
import numpy as np

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

print("[1] Loading slim + person_properties...", flush=True)
# 이번엔 person_properties 컬럼도 로드 (segmentation용)
events = pd.read_csv(
    CSV,
    usecols=["person_id", "timestamp", "event",
             "person_properties.purpose", "person_properties.role",
             "person_properties.work_type", "person_properties.source"],
    engine="pyarrow",
)
events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
DATA_END = events["timestamp"].max()
N_USERS = events["person_id"].nunique()
print(f"    rows={len(events):,}  users={N_USERS:,}")

upgraders = set(events.loc[events["event"] == "subscription_upgraded", "person_id"].unique())

# ──────────────────────────────────────────────────────────────────
# H1. 8.Upgraded 세분화 (이미 분석됨)
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H1. 8.Upgraded 세분화 (재확인)")
print("="*72)
upg_first = events.loc[events["event"] == "subscription_upgraded"].groupby("person_id")["timestamp"].min()
upgr_last = events.loc[events["person_id"].isin(upgraders)].groupby("person_id")["timestamp"].max()
inactive_days = (DATA_END - upgr_last).dt.total_seconds() / 86400

# 다운그레이드 / cancel 발생자 (업그레이드 이후만)
def post_upg_event_users(ev_name):
    sub = events.loc[(events["event"] == ev_name) & events["person_id"].isin(upgraders)].copy()
    if len(sub) == 0: return set()
    sub["upg_ts"] = sub["person_id"].map(upg_first)
    return set(sub.loc[sub["timestamp"] > sub["upg_ts"], "person_id"].unique())

downgrade_users = post_upg_event_users("subscription_downgraded") | post_upg_event_users("downgrade_subscription")
cancel_users = post_upg_event_users("subscription_cancelled") | post_upg_event_users("cancel_subscription")
inactive_30 = set(inactive_days[inactive_days >= 30].index)
inactive_60 = set(inactive_days[inactive_days >= 60].index)

active = upgraders - downgrade_users - cancel_users - inactive_30
churned = (downgrade_users & inactive_30) | cancel_users
downgraded_active = downgrade_users - inactive_30 - cancel_users
inactive_only = inactive_30 - downgrade_users - cancel_users

print(f"  업그레이더: {len(upgraders)}명")
print(f"    8.Upgraded@Active:        {len(active)}명  (no downgrade, active 30d)")
print(f"    8.Upgraded@Downgraded:    {len(downgraded_active)}명  (downgrade했지만 활성)")
print(f"    8.Upgraded@Inactive:      {len(inactive_only)}명  (30d+ 무활동)")
print(f"    9.Churned@Upgraded:       {len(churned)}명  (downgrade+inactive 또는 cancel)")
print(f"    합계: {len(active) + len(downgraded_active) + len(inactive_only) + len(churned)}")
print(f"  채택: ✅ 4분할 (또는 단순화 3분할)")

# ──────────────────────────────────────────────────────────────────
# H2. Reactivated state
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H2. Reactivated — AtRisk 였다가 다시 활성화")
print("="*72)
# 사용자별 timestamp 시퀀스에서 14일 이상 gap이 있고, 그 이후에도 이벤트가 있는 사용자
events_sorted = events[["person_id", "timestamp"]].sort_values(["person_id", "timestamp"])
events_sorted["prev_ts"] = events_sorted.groupby("person_id")["timestamp"].shift(1)
events_sorted["gap_days"] = (events_sorted["timestamp"] - events_sorted["prev_ts"]).dt.total_seconds() / 86400

# 사용자별 최대 gap
max_gap = events_sorted.groupby("person_id")["gap_days"].max()
# 14일 이상 gap이 있는 사용자
gap_users = max_gap[max_gap >= 14].index
print(f"  14일 이상 활동 gap 있는 사용자: {len(gap_users):,}")
print(f"  30일 이상 활동 gap 있는 사용자: {(max_gap >= 30).sum():,}")

# 그 중 gap 이후에도 의미있는 활동(예: 5+ events)이 있는 사용자
def gap_then_active(g):
    """returns True if there's a 14+ day gap and >= 5 events after it"""
    ts = g["timestamp"].sort_values()
    gaps = ts.diff().dt.total_seconds() / 86400
    big_gap_idx = gaps[gaps >= 14].index
    if len(big_gap_idx) == 0:
        return False
    last_big_gap_pos = ts.index.get_loc(big_gap_idx[-1])
    n_after = len(ts) - last_big_gap_pos
    return n_after >= 5

# 빠른 버전: 사용자별 (마지막 gap 이후 이벤트 수)
gap_user_set = set(gap_users)
events_gap = events_sorted[events_sorted["person_id"].isin(gap_user_set)].copy()
events_gap["after_gap"] = (events_gap.groupby("person_id")["gap_days"].cummax() >= 14).astype(int)
n_after_gap = events_gap[events_gap["after_gap"] == 1].groupby("person_id").size()
reactivated = set(n_after_gap[n_after_gap >= 5].index)
print(f"  Reactivated (gap≥14d 후 5+ events): {len(reactivated):,}명  ({len(reactivated)/N_USERS*100:.2f}%)")
# 그 중 업그레이드한 사람
reac_upg = reactivated & upgraders
print(f"    중 업그레이더: {len(reac_upg)}명")
print(f"  채택: 🟡 의미는 있지만 단계 추가는 과도. AtRisk@X 의 'reactivated_at' 메타데이터로 충분")

# ──────────────────────────────────────────────────────────────────
# H3. Onboarding completion
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H3. Onboarding completion (tour 완주 / skip / incomplete)")
print("="*72)
tour_started = set(events.loc[events["event"] == "notebook_onboarding_tour_started", "person_id"].unique())
tour_finished = set(events.loc[events["event"] == "notebook_onboarding_tour_finished", "person_id"].unique())
form_submitted = set(events.loc[events["event"] == "submit_onboarding_form", "person_id"].unique())
form_skipped = set(events.loc[events["event"] == "skip_onboarding_form", "person_id"].unique())

print(f"  notebook_onboarding_tour_started:   {len(tour_started):,}명")
print(f"  notebook_onboarding_tour_finished:  {len(tour_finished):,}명  (완주율 {len(tour_finished)/len(tour_started)*100:.1f}%)")
print(f"  submit_onboarding_form:             {len(form_submitted):,}명")
print(f"  skip_onboarding_form:               {len(form_skipped):,}명")
# 업그레이드율 차이
print(f"\n  업그레이드율 비교:")
for label, group in [
    ("tour_finished", tour_finished),
    ("tour_started_only (no finish)", tour_started - tour_finished),
    ("form_submitted", form_submitted),
    ("form_skipped", form_skipped),
]:
    n = len(group)
    if n == 0: continue
    upg = len(group & upgraders)
    print(f"    {label:<35} {n:>6,}  upg={upg:>3} ({upg/n*100:.2f}%)")
print(f"  채택: 🟢 'OnboardingCompleted' 정보를 메타로 추가. 별도 stage는 과도")

# ──────────────────────────────────────────────────────────────────
# H4. Promo / Trial 사용자
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H4. Promo / Trial / Free offer 사용자")
print("="*72)
promo_users = set(events.loc[events["event"] == "promo_code_redeemed", "person_id"].unique())
free_offer_users = set(events.loc[events["event"] == "claim_free_offer_clicked", "person_id"].unique())
work_email_bonus = set(events.loc[events["event"] == "work_email_bonus_credits_received", "person_id"].unique())
referral_bonus = set(events.loc[events["event"] == "referral_bonus_credits_received", "person_id"].unique())

print(f"  promo_code_redeemed:                  {len(promo_users):,}명")
print(f"  claim_free_offer_clicked:             {len(free_offer_users):,}명")
print(f"  work_email_bonus_credits_received:    {len(work_email_bonus):,}명")
print(f"  referral_bonus_credits_received:      {len(referral_bonus):,}명")

trial_path = promo_users | free_offer_users | work_email_bonus | referral_bonus
print(f"\n  Trial path 합집합: {len(trial_path):,}명")
print(f"  업그레이드율 비교:")
for label, group in [
    ("promo_redeemed", promo_users),
    ("free_offer_clicked", free_offer_users),
    ("work_email_bonus", work_email_bonus),
    ("referral_bonus", referral_bonus),
    ("any_trial_path", trial_path),
    ("no_trial_path", set(events["person_id"].unique()) - trial_path),
]:
    n = len(group)
    if n == 0: continue
    upg = len(group & upgraders)
    print(f"    {label:<25} {n:>6,}  upg={upg:>3} ({upg/n*100:.2f}%)")
print(f"  채택: 🟡 모집단 크지만 'trial_path' 메타데이터로 충분 (단계로 격상은 과도)")

# ──────────────────────────────────────────────────────────────────
# H5. Frustrated — 높은 에러 비율
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H5. Frustrated state ($exception 다발 사용자)")
print("="*72)
n_exception = events.loc[events["event"] == "$exception"].groupby("person_id").size()
n_total = events.groupby("person_id").size()
exc_ratio = (n_exception / n_total).fillna(0)

print(f"  $exception 발생자: {len(n_exception):,}명")
print(f"  exception/total 비율 분포:")
print(f"    median: {exc_ratio.median():.3f}")
print(f"    p75:    {exc_ratio.quantile(.75):.3f}")
print(f"    p90:    {exc_ratio.quantile(.90):.3f}")

# Frustrated = exception 비율 25%+ AND 활동 있음
frustrated = set(exc_ratio[exc_ratio >= 0.25].index) & set(n_total[n_total >= 10].index)
print(f"  Frustrated (exception >= 25% & total >= 10): {len(frustrated):,}명")
print(f"  업그레이드율 비교:")
for label, group in [
    ("frustrated", frustrated),
    ("not_frustrated", set(events["person_id"].unique()) - frustrated),
]:
    n = len(group); upg = len(group & upgraders)
    print(f"    {label:<20} {n:>6,}  upg={upg:>3} ({upg/n*100:.2f}%)")
print(f"  채택: ❌ population 작고 단계 추가는 노이즈. 단, 모델 feature로는 가치 있음")

# ──────────────────────────────────────────────────────────────────
# H6. Power Engaged vs Casual Engaged
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H6. Power Engaged vs Casual Engaged")
print("="*72)
# Engaged v3 = (AI/Code/Integ) AND distinct_days >= 3
# Power = distinct_days >= 7 OR n_events >= 1000

events_dated = events.copy()
events_dated["date"] = events_dated["timestamp"].dt.date
engagement_set = {"$ai_generation", "agent_message", "agent_new_chat",
                   "agent_start_from_prompt", "agent_worker_created",
                   "run_block", "run_all_blocks",
                   "source_control_connect_to_canvas", "source_control_commit",
                   "source_control_pull",
                   "notebook_deployment_deployed",
                   "notebook_deployment_preview_created",
                   "notebook_deployment_updated"}
eng_dates = events_dated.loc[events_dated["event"].isin(engagement_set)].groupby(
    "person_id")["date"].nunique()
engaged_users = set(eng_dates[eng_dates >= 3].index)
power_engaged = set(eng_dates[eng_dates >= 7].index)
casual_engaged = engaged_users - power_engaged

print(f"  Engaged 전체: {len(engaged_users):,}명")
print(f"    Power Engaged (7+ engagement days): {len(power_engaged):,}명")
print(f"    Casual Engaged (3-6 days):         {len(casual_engaged):,}명")
print(f"  업그레이드율:")
for label, group in [("power_engaged", power_engaged), ("casual_engaged", casual_engaged)]:
    n = len(group); upg = len(group & upgraders)
    print(f"    {label:<20} {n:>6,}  upg={upg:>3} ({upg/n*100:.2f}%)")
print(f"  채택: 🟡 의미 있지만 단계 수 늘리는 비용. 메타데이터 필드로 분리 권장")

# ──────────────────────────────────────────────────────────────────
# H7. Agent-first vs Notebook-first
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H7. Agent-first vs Notebook-first user")
print("="*72)
ai_set = {"$ai_generation", "agent_message", "agent_new_chat",
          "agent_start_from_prompt", "agent_worker_created"}
notebook_set = {"block_create", "run_block", "files_upload"}

# 첫 AI ts vs 첫 notebook ts (단순 비교)
first_ai = events.loc[events["event"].isin(ai_set)].groupby("person_id")["timestamp"].min()
first_notebook = events.loc[events["event"].isin(notebook_set)].groupby("person_id")["timestamp"].min()

both = first_ai.index.intersection(first_notebook.index)
ai_first = (first_ai.loc[both] < first_notebook.loc[both]).sum()
notebook_first = (first_notebook.loc[both] < first_ai.loc[both]).sum()

print(f"  AI와 Notebook 모두 사용한 사용자: {len(both):,}")
print(f"    AI 먼저 사용:        {ai_first:,}  ({ai_first/len(both)*100:.1f}%)")
print(f"    Notebook 먼저 사용:  {notebook_first:,}  ({notebook_first/len(both)*100:.1f}%)")
ai_only = first_ai.index.difference(first_notebook.index)
notebook_only = first_notebook.index.difference(first_ai.index)
print(f"  AI만 사용 (Notebook 미사용): {len(ai_only):,}")
print(f"  Notebook만 사용 (AI 미사용): {len(notebook_only):,}")
print(f"  업그레이드율:")
for label, group in [("ai_first", set(both[(first_ai.loc[both] < first_notebook.loc[both])])),
                     ("notebook_first", set(both[(first_notebook.loc[both] < first_ai.loc[both])])),
                     ("ai_only", set(ai_only)), ("notebook_only", set(notebook_only))]:
    n = len(group); upg = len(group & upgraders)
    print(f"    {label:<20} {n:>6,}  upg={upg:>3} ({upg/max(n,1)*100:.2f}%)")
print(f"  채택: 🟡 segmentation으로 의미 있지만 funnel 단계는 아님 (perpendicular dimension)")

# ──────────────────────────────────────────────────────────────────
# H8. Personal vs Company purpose
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H8. Personal vs Company purpose 별 funnel 차이")
print("="*72)
# 사용자별 purpose (가장 많이 등장한 값)
purpose = events.dropna(subset=["person_properties.purpose"]).groupby(
    "person_id")["person_properties.purpose"].agg(lambda s: s.mode().iloc[0] if len(s.mode()) else None)
print(f"  purpose 정보 있는 사용자: {len(purpose):,}/{N_USERS:,}")
print(f"  업그레이드율 by purpose:")
for p in ["Personal Projects", "Company Work", "Education"]:
    grp = set(purpose[purpose == p].index)
    n = len(grp); upg = len(grp & upgraders)
    print(f"    {p:<25} {n:>6,}  upg={upg:>3} ({upg/max(n,1)*100:.2f}%)")
no_purpose = set(events["person_id"].unique()) - set(purpose.index)
upg_no = len(no_purpose & upgraders)
print(f"    {'(no purpose)':<25} {len(no_purpose):>6,}  upg={upg_no:>3} ({upg_no/max(len(no_purpose),1)*100:.2f}%)")
print(f"  채택: ❌ funnel 단계가 아닌 cohort/dimension. 단, 모델 feature로 사용")

# ──────────────────────────────────────────────────────────────────
# H9. Deployment 성공/실패 분리
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H9. Deployment 성공 vs 크레딧 부족 실패")
print("="*72)
deploy_success = set(events.loc[events["event"] == "notebook_deployment_deployed", "person_id"].unique())
deploy_credits_exceeded = set(events.loc[events["event"] == "notebook_deployment_credits_exceeded", "person_id"].unique())
deploy_undeployed = set(events.loc[events["event"] == "notebook_deployment_undeployed", "person_id"].unique())

print(f"  deployment_deployed:           {len(deploy_success):,}명")
print(f"  deployment_credits_exceeded:   {len(deploy_credits_exceeded):,}명")
print(f"  deployment_undeployed:         {len(deploy_undeployed):,}명")
print(f"  업그레이드율:")
for label, group in [
    ("deployed_success", deploy_success),
    ("credits_exceeded", deploy_credits_exceeded),
    ("undeployed", deploy_undeployed),
]:
    n = len(group); upg = len(group & upgraders)
    print(f"    {label:<25} {n:>6,}  upg={upg:>3} ({upg/max(n,1)*100:.2f}%)")
print(f"  채택: ❌ Stage 6 안에 이미 deployment 포함. 추가 분리 불필요")

# ──────────────────────────────────────────────────────────────────
# H10. Bot/Outlier 사용자
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("H10. Bot/Outlier 의심 사용자")
print("="*72)
n_per_user = events.groupby("person_id").size()
n_per_user_sorted = n_per_user.sort_values(ascending=False)
print(f"  이벤트 수 분포:")
print(f"    p99: {int(n_per_user.quantile(.99)):,}")
print(f"    p99.5: {int(n_per_user.quantile(.995)):,}")
print(f"    max: {int(n_per_user.max()):,}")
print(f"  Top 10 heavy users:")
for pid, n in n_per_user_sorted.head(10).items():
    is_upg = "✓UPG" if pid in upgraders else "    "
    print(f"    {pid}  {n:>7,} events  {is_upg}")

# 5만+ 이벤트 사용자
heavy = set(n_per_user[n_per_user >= 50000].index)
print(f"\n  50,000+ events 사용자: {len(heavy):,}명")
print(f"    그 중 업그레이더: {len(heavy & upgraders)}명")
print(f"  → 정상 업그레이더의 heavy 사용 패턴이지 bot 아님")
print(f"  채택: ❌ 자연스러운 power user. bot 단계 불필요")

# ──────────────────────────────────────────────────────────────────
# 종합: v4에 채택할 것
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("=== v4 채택 권장 ===")
print("="*72)
recommendations = [
    ("H1. 8.Upgraded 4분할", "✅ MUST", "Active/Downgraded/Inactive/Churned. Time-Aware 핵심 보강"),
    ("H2. Reactivated", "🟡 OPTIONAL", "단계가 아닌 메타데이터 (reactivation_count)"),
    ("H3. Onboarding completion", "🟢 ADD", "메타 컬럼 'onboarding_completed' (model feature 활용)"),
    ("H4. Promo/Trial path", "🟢 ADD", "메타 컬럼 'used_promo' (모델 feature)"),
    ("H5. Frustrated", "❌ SKIP", "stage 아님. exception_rate를 모델 feature로"),
    ("H6. Power vs Casual Engaged", "🟡 OPTIONAL", "stage 분할 가능하지만 비용/이득 미미"),
    ("H7. Agent-first vs Notebook-first", "🟢 ADD", "메타 컬럼 (모델 feature). funnel과 직교"),
    ("H8. Personal vs Company", "❌ SKIP", "cohort dimension. funnel과 직교"),
    ("H9. Deployment 성공/실패", "❌ SKIP", "Stage 6에 흡수됨"),
    ("H10. Bot/Outlier", "❌ SKIP", "정상 power user"),
]
for h, decision, note in recommendations:
    print(f"  {decision:<14} {h:<35}  {note}")

print("\n  → v4 funnel 최종 단계 수: 13단계 (NoEvent + 1~7 + 8.Upg@{Active,Downgraded,Inactive} + 9.Churned@Upgraded + 9.AtRisk@{UsedAI,Code,Int,Eng})")
print("  → 메타 컬럼 추가: onboarding_completed, used_promo, agent_first")
