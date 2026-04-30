"""
모델 weight → 비즈니스 액션 변환

분석 항목:
  (A) 모델 importance × 실제 conversion lift 매트릭스
  (B) 사용자 segment별 (v4 stage × 메타) 결제율 grid
  (C) 각 핵심 feature의 marginal effect — "이 feature 1↑ 하면 결제확률 얼마?"
  (D) Top 5% 예측 사용자의 페르소나 분석
  (E) 비즈니스 액션 ROI 추정
"""
from __future__ import annotations
import pandas as pd
import numpy as np

PARQUET = "/Users/hunjunsin/Desktop/zerve/feature_matrix.parquet"
PRED_V3 = "/Users/hunjunsin/Desktop/zerve/mission1_v3_predictions.csv"
V4_LABEL = "/Users/hunjunsin/Desktop/zerve/funnel_v4_assignment.csv"

print("[1] Loading data...", flush=True)
X = pd.read_parquet(PARQUET)
preds = pd.read_csv(PRED_V3).set_index("person_id")
v4 = pd.read_csv(V4_LABEL, index_col=0)

# Train + test 모두 사용 (insight 산출은 전체 사용자 대상)
n_total = len(X)
upg = X["upgraded"].astype(bool)
print(f"    total users: {n_total:,}, upgraders: {upg.sum()}, base rate {upg.mean()*100:.2f}%")

# ──────────────────────────────────────────────────────────────────
# (A) Top feature × business action mapping
# ──────────────────────────────────────────────────────────────────
print("\n=== (A) Top feature 별 결제율 비교 ===")
print("    (실제 모델이 학습한 패턴이 비즈니스에 어떻게 매핑되는가)")
print()

# 각 핵심 feature를 binary로 보고 / 상위 분위로 보고 결제율 계산
def analyze_binary(col, threshold=0):
    has = X[col] > threshold
    rate_has = X.loc[has, "upgraded"].mean()
    rate_not = X.loc[~has, "upgraded"].mean()
    return has.sum(), rate_has, rate_not, rate_has / max(rate_not, 1e-6)

print(f"  {'feature':<35}{'has':>7}{'rate_has':>11}{'rate_not':>10}{'lift':>8}")
print(f"  {'-'*70}")
analyses = [
    # Credit limit triggers
    ("did_hit_credit_limit_7d",     "Credit 한도 도달 (7d)"),
    ("did_see_banner_7d",            "AI credit 배너 노출 (7d)"),
    ("did_hit_credit_limit_24h",    "Credit 한도 도달 (24h)"),
    # AI/Agent
    ("did_use_agent_24h",            "Coder Agent 사용 (24h)"),
    ("used_ai_within_1h",            "1시간 안에 AI 사용"),
    ("agent_first",                  "AI를 notebook보다 먼저"),
    # Onboarding
    ("any_tour_finish_24h",          "Tour 완주 (24h)"),
    ("any_submit_form_24h",          "Onboarding form 제출 (24h)"),
    # Source control / deployment
    ("did_source_control_7d",        "Source control 사용"),
    ("did_deploy_7d",                "Deployment 수행"),
    # Run / Create
    ("did_run_block_24h",            "Block 실행 (24h)"),
    ("did_files_upload_7d",          "Files upload"),
    ("did_canvas_clone_7d",          "Canvas clone"),
    # Engagement deep
    ("is_power_engaged",             "Power Engaged (7+ days)"),
    # Demographic
    ("purpose_Personal Projects",     "Personal Projects (purpose)"),
    ("purpose_Company Work",          "Company Work (purpose)"),
    ("purpose_Education",             "Education (purpose)"),
    ("device_type_Desktop",           "Desktop"),
    ("device_type_Mobile",            "Mobile"),
    ("os_Linux",                      "OS Linux"),
]

for col, label in analyses:
    if col not in X.columns:
        continue
    has, rate_has, rate_not, lift = analyze_binary(col)
    print(f"  {label:<35}{has:>7,}{rate_has*100:>10.2f}%{rate_not*100:>9.2f}%{lift:>7.1f}x")

# ──────────────────────────────────────────────────────────────────
# (B) v4 stage × 메타 grid — 가장 결제율 높은 segment
# ──────────────────────────────────────────────────────────────────
print("\n=== (B) Stage × 메타 매트릭스 (top 결제율 segment) ===")
df = X.copy()
# v4에서 stage + used_promo + 메타 가져옴 (used_promo는 leakage라 X엔 없음)
v4_cols = v4[["final_stage", "used_promo", "onboarding_completed"]].copy()
v4_cols["used_promo"] = v4_cols["used_promo"].astype(bool)
v4_cols["onboarding_completed"] = v4_cols["onboarding_completed"].astype(bool)
df = df.join(v4_cols)

# meta combination
df["combo"] = (
    "promo:" + df["used_promo"].astype(int).astype(str) +
    " tour:" + df["onboarding_completed"].astype(int).astype(str) +
    " af:" + df["agent_first"].astype(int).astype(str)
)

# 큰 segment만 (n>=100)
seg = df.groupby(["final_stage", "combo"]).agg(
    users=("upgraded", "size"),
    upg=("upgraded", "sum"),
).reset_index()
seg["rate"] = seg["upg"] / seg["users"] * 100
seg = seg[seg["users"] >= 50].sort_values("rate", ascending=False)
print("  (segment 크기 >= 50명만)")
print(f"  {'stage':<22}{'combo':<28}{'users':>7}{'upg':>5}{'rate':>8}")
for _, r in seg.head(15).iterrows():
    print(f"  {r['final_stage']:<22}{r['combo']:<28}{int(r['users']):>7,}"
          f"{int(r['upg']):>5}{r['rate']:>7.2f}%")

# ──────────────────────────────────────────────────────────────────
# (C) Marginal effect — 각 핵심 feature의 dose-response curve
# ──────────────────────────────────────────────────────────────────
print("\n=== (C) Dose-response — 핵심 numerical feature의 결제율 곡선 ===")

def dose_response(col, bins=(0, 1, 5, 20, 100, np.inf)):
    """count feature를 bin으로 나누고 각 bin의 결제율"""
    if col not in X.columns: return
    series = X[col]
    cuts = pd.cut(series, bins=bins, include_lowest=True, right=False)
    grp = X.groupby(cuts, observed=True)["upgraded"].agg(["size", "sum", "mean"])
    grp.columns = ["users", "upg", "rate"]
    grp["rate_pct"] = grp["rate"] * 100
    return grp

for col, label in [
    ("n_agent_tool_24h",      "Coder Agent tool calls (24h)"),
    ("n_credits_used_1h",     "Credits used (1h)"),
    ("n_credits_exceeded_7d", "Credits exceeded count (7d)"),
    ("n_distinct_days_7d",    "Distinct active days (7d)"),
    ("n_pageview_24h",        "Pageviews (24h)"),
    ("n_run_block_24h",       "Block runs (24h)"),
]:
    grp = dose_response(col)
    if grp is None: continue
    print(f"\n  {label}:")
    print(f"    {'bin':<14}{'users':>7}{'upg':>5}{'rate':>9}")
    for idx, row in grp.iterrows():
        print(f"    {str(idx):<14}{int(row['users']):>7,}{int(row['upg']):>4}"
              f"{row['rate_pct']:>8.2f}%")

# ──────────────────────────────────────────────────────────────────
# (D) Top 5% 예측 사용자의 페르소나
# ──────────────────────────────────────────────────────────────────
print("\n=== (D) v3 모델 Top 5% 예측 사용자의 페르소나 ===")
test_idx = preds.index
# Test set만
df_test = X.loc[X.index.isin(test_idx)].copy()
df_test["score"] = preds.loc[df_test.index, "score_avg_v3"].values
df_test["pred_top5"] = df_test["score"] >= df_test["score"].quantile(0.95)

print(f"\n  Top 5% (score 상위 {df_test['pred_top5'].sum()}명) vs 나머지 ({(~df_test['pred_top5']).sum()}명) 페르소나:")
print(f"  {'feature':<35}{'top5%':>10}{'rest':>10}{'diff':>8}")
print(f"  {'-'*65}")
profile_feats = [
    "did_hit_credit_limit_7d", "did_see_banner_7d",
    "used_ai_within_1h", "agent_first",
    "any_tour_finish_24h", "did_source_control_7d", "did_deploy_7d",
    "did_canvas_clone_7d", "did_files_upload_7d",
    "device_type_Desktop", "device_type_Mobile",
    "purpose_Personal Projects", "purpose_Company Work", "purpose_Education",
    "os_Linux", "country_India",
    "n_agent_tool_24h", "n_credits_used_1h", "n_distinct_days_7d",
    "n_run_block_24h", "n_pageview_24h", "session_minutes_24h",
]
for f in profile_feats:
    if f not in df_test.columns: continue
    a = df_test.loc[df_test["pred_top5"], f].mean()
    b = df_test.loc[~df_test["pred_top5"], f].mean()
    diff = a - b
    print(f"  {f:<35}{a:>10.3f}{b:>10.3f}{diff:>+7.2f}")

# Top 5% 안에서 실제 업그레이더 vs not
top5_real = df_test.loc[df_test["pred_top5"] & df_test["upgraded"].astype(bool)]
top5_fake = df_test.loc[df_test["pred_top5"] & ~df_test["upgraded"].astype(bool)]
print(f"\n  Top 5% 안에서 actual upgrader (TP={len(top5_real)}) vs false positive (FP={len(top5_fake)}):")
print(f"  {'feature':<35}{'actual_upg':>12}{'false_pos':>12}{'diff':>8}")
for f in ["did_hit_credit_limit_7d", "did_see_banner_7d",
          "any_tour_finish_24h", "n_distinct_days_7d", "n_agent_tool_24h",
          "did_deploy_7d", "device_type_Desktop"]:
    if f not in df_test.columns: continue
    a = top5_real[f].mean(); b = top5_fake[f].mean()
    print(f"  {f:<35}{a:>12.3f}{b:>12.3f}{a-b:>+7.2f}")

# ──────────────────────────────────────────────────────────────────
# (E) 비즈니스 액션별 ROI 추정
# ──────────────────────────────────────────────────────────────────
print("\n=== (E) 액션 ROI 추정 (전체 사용자 대비) ===")
print()
print(f"  현재 baseline conversion: {upg.mean()*100:.2f}% ({int(upg.sum())} / {n_total:,})")
print()

actions = [
    {
        "name": "A1. Credit 한도 도달 사용자에게 즉시 결제 유도",
        "target_col": "did_hit_credit_limit_7d",
        "rationale": "한도 도달 시 결제율 12.4x. 즉시 30% 할인 코드 제공",
    },
    {
        "name": "A2. Tour 완주자에게 결제 prompt",
        "target_col": "any_tour_finish_24h",
        "rationale": "Tour 완주자 결제율 10x. Pro 플랜 free trial 14일 제안",
    },
    {
        "name": "A3. Deployment 사용자에게 Pro 추천",
        "target_col": "did_deploy_7d",
        "rationale": "Deployment 사용자 결제율 22% (12x). Sales contact 우선",
    },
    {
        "name": "A4. Source control 연결자에게 Team plan 제안",
        "target_col": "did_source_control_7d",
        "rationale": "진지한 사용자 신호. Team/Org 플랜 cross-sell 적합",
    },
    {
        "name": "A5. Power Engaged 사용자 (7+ days) sales touch",
        "target_col": "is_power_engaged",
        "rationale": "결제율 26% (16x). Manual sales contact ROI 가장 높음",
    },
    {
        "name": "A6. AI를 1h 안에 쓴 사용자 retention 강화",
        "target_col": "used_ai_within_1h",
        "rationale": "Agent_first의 결제율은 13x. 첫날 retention 캠페인",
    },
]

print(f"  {'action':<55}{'targets':>8}{'rate':>8}{'lift':>7}")
print(f"  {'-'*80}")
for a in actions:
    if a["target_col"] not in X.columns: continue
    mask = X[a["target_col"]] > 0
    n_targets = int(mask.sum())
    rate = X.loc[mask, "upgraded"].mean() * 100
    lift = rate / (upg.mean() * 100)
    print(f"  {a['name']:<55}{n_targets:>8,}{rate:>7.2f}%{lift:>6.1f}x")
    print(f"     → {a['rationale']}")

# 결과 저장
with open("/Users/hunjunsin/Desktop/zerve/business_insights_data.txt", "w") as f:
    f.write("Business insights raw data\n")
    f.write("="*60 + "\n")
    f.write(f"Total users: {n_total:,}\n")
    f.write(f"Upgraders: {int(upg.sum())} ({upg.mean()*100:.2f}%)\n")

print("\n  → 자세한 액션 매트릭스는 business_playbook.md 참조")
