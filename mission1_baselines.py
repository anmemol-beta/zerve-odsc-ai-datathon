"""
Baseline 비교 — 모델이 단순 baseline들을 정말 이기는가?

Baselines:
  B0. Majority voting       → 항상 0 예측
  B1. Random scoring        → 무작위 점수
  B2. Base rate predictor   → 모두에게 base rate 점수
  B3. 단일 강력 feature      → n_credits_exceeded_7d
  B4. 룰 기반                → did_hit_credit_limit_7d == 1
  B5. v4 funnel stage       → 7.Engaged/6.Integrated/5.WroteCode 인지

Models:
  M1. Logistic v2
  M2. XGBoost v2

비교 지표: Accuracy(threshold 0.5) / PR-AUC / ROC-AUC / Top-K precision&recall
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from sklearn.metrics import (
    average_precision_score, roc_auc_score, accuracy_score,
    precision_score, recall_score, f1_score, confusion_matrix,
)

PARQUET = "/Users/hunjunsin/Desktop/zerve/feature_matrix.parquet"
PRED = "/Users/hunjunsin/Desktop/zerve/mission1_v2_predictions.csv"

X_full = pd.read_parquet(PARQUET)
preds = pd.read_csv(PRED)

# Test set 사용자만
test_mask = X_full["cohort_month"] >= "2026-03"
X_test = X_full.loc[test_mask].copy()
y_test = X_test["upgraded"].values
n = len(y_test)
n_pos = int(y_test.sum())
base_rate = y_test.mean()

print(f"Test set: {n:,} users, {n_pos} upgraders, base rate {base_rate:.4f} ({base_rate*100:.2f}%)\n")

# 점수 매핑 (test set index 매칭)
preds_indexed = preds.set_index("person_id")
y_logit = preds_indexed.loc[X_test.index, "score_logit"].values
y_xgb = preds_indexed.loc[X_test.index, "score_xgb"].values

# v4 funnel stage 라벨
v4_labels = pd.read_csv("/Users/hunjunsin/Desktop/zerve/funnel_v4_assignment.csv",
                         index_col=0)
stage_test = v4_labels.loc[X_test.index, "final_stage"].values

# ────────────────────────────────────────
# 점수 정의
# ────────────────────────────────────────
np.random.seed(42)
y_majority = np.zeros(n)                     # 모두 0 예측 (점수도 0)
y_random   = np.random.rand(n)
y_const    = np.full(n, base_rate)           # base rate score
y_naive    = X_test["n_credits_exceeded_7d"].values
y_rule     = X_test["did_hit_credit_limit_7d"].values

# v4 stage 기반: high stages가 양성 신호
high_stages = {"7.Engaged", "6.Integrated", "5.WroteCode"}
y_funnel = np.array([1 if s in high_stages else 0 for s in stage_test])

# ────────────────────────────────────────
# 평가 함수
# ────────────────────────────────────────
def top_k_metrics(y_t, y_s, k_pcts=(0.01, 0.05, 0.10, 0.20)):
    n = len(y_t); n_pos = y_t.sum()
    order = np.argsort(y_s)[::-1]
    cum = np.cumsum(y_t[order])
    out = {}
    for kp in k_pcts:
        k = int(n * kp)
        if k == 0: continue
        out[kp] = {
            "k": k,
            "caught": int(cum[k-1]),
            "precision": cum[k-1]/k,
            "recall": cum[k-1]/max(n_pos,1),
        }
    return out

def evaluate(name, y_score, threshold=0.5, is_binary_input=False):
    """y_score는 점수(0~1)이며, threshold로 binary 변환."""
    if is_binary_input:
        y_pred = y_score.astype(int)
    else:
        y_pred = (y_score >= threshold).astype(int)

    # 점수가 모두 같으면 PR-AUC = base rate
    pr = average_precision_score(y_test, y_score) if y_score.std() > 0 else base_rate
    try:
        roc = roc_auc_score(y_test, y_score) if y_score.std() > 0 else 0.5
    except ValueError:
        roc = 0.5
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    return {"name": name, "PR-AUC": pr, "ROC-AUC": roc,
            "Acc": acc, "Prec": prec, "Recall": rec, "F1": f1}

# ────────────────────────────────────────
# 평가 실행
# ────────────────────────────────────────
results = []
results.append(evaluate("B0. Majority(=0)",     y_majority, is_binary_input=True))
results.append(evaluate("B1. Random",            y_random))
results.append(evaluate("B2. Const(base_rate)",  y_const))
results.append(evaluate("B3. n_credits_exc_7d",  y_naive))
results.append(evaluate("B4. did_hit_limit_7d",  y_rule, is_binary_input=True))
results.append(evaluate("B5. v4_funnel_high",    y_funnel, is_binary_input=True))
results.append(evaluate("M1. Logistic v2",       y_logit))
results.append(evaluate("M2. XGBoost v2",        y_xgb))

print(f"{'model':<26}{'Acc':>7}{'Prec':>7}{'Rec':>7}{'F1':>7}{'PR-AUC':>9}{'ROC-AUC':>9}")
for r in results:
    print(f"  {r['name']:<24}{r['Acc']:>7.4f}{r['Prec']:>7.3f}{r['Recall']:>7.3f}"
          f"{r['F1']:>7.3f}{r['PR-AUC']:>9.4f}{r['ROC-AUC']:>9.4f}")

# Top-K 비교
print(f"\n{'─'*60}")
print(f"Top-K Precision / Recall:")
print(f"{'─'*60}")
print(f"  {'model':<22}", end="")
for kp in [0.01, 0.05, 0.10, 0.20]:
    print(f"{'top'+str(int(kp*100))+'%':>10}", end="  ")
print()
print(f"  {'':<22}", end="")
for kp in [0.01, 0.05, 0.10, 0.20]:
    print(f"{'P/R':>10}", end="  ")
print()
for name, y_score in [
    ("Majority(=0)", y_majority),
    ("Random", y_random),
    ("n_credits_exc_7d", y_naive),
    ("did_hit_limit_7d", y_rule),
    ("v4_funnel_high", y_funnel),
    ("Logistic v2", y_logit),
    ("XGBoost v2", y_xgb),
]:
    print(f"  {name:<22}", end="")
    if y_score.std() == 0:
        for kp in [0.01, 0.05, 0.10, 0.20]:
            print(f"{'-':>10}", end="  ")
    else:
        tk = top_k_metrics(y_test, y_score)
        for kp in [0.01, 0.05, 0.10, 0.20]:
            if kp not in tk: continue
            t = tk[kp]
            print(f"{t['precision']*100:>4.1f}%/{t['recall']*100:>4.1f}%", end="  ")
    print()

# ────────────────────────────────────────
# Confusion matrix — 모델 vs Majority
# ────────────────────────────────────────
print(f"\n{'─'*60}")
print(f"Confusion Matrices (threshold 0.5):")
print(f"{'─'*60}")
for name, y_score in [("Majority(=0)", (y_majority).astype(int)),
                       ("XGBoost v2 @0.5", (y_xgb >= 0.5).astype(int)),
                       ("XGBoost v2 @0.9", (y_xgb >= 0.9).astype(int)),
                       ("XGBoost v2 @0.99", (y_xgb >= 0.99).astype(int))]:
    cm = confusion_matrix(y_test, y_score, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    print(f"\n  {name}:")
    print(f"    TN={tn:>5}  FP={fp:>5}  → 정상 사용자")
    print(f"    FN={fn:>5}  TP={tp:>5}  → 실제 업그레이더")
    if (tp+fp) > 0 and (tp+fn) > 0:
        print(f"    Precision={tp/(tp+fp):.3f}, Recall={tp/(tp+fn):.3f}, "
              f"Acc={(tp+tn)/(tp+tn+fp+fn):.3f}")

# 비즈니스 시나리오
print(f"\n{'═'*60}")
print(f"비즈니스 시나리오: '상위 K%에 결제 유도 캠페인 보낸다'")
print(f"{'═'*60}")
print(f"  Test 사용자 {n:,}명 중 실제 업그레이더 {n_pos}명")
print(f"  - Majority voting: 캠페인 0건. 업그레이더 0명 잡음. ROI 정의 불가")
print(f"  - Random 5%: 캠페인 {int(n*0.05)}건. 업그레이더 약 {int(n*0.05*base_rate)}명 잡음")
print(f"  - XGBoost top 5%: 캠페인 {int(n*0.05)}건. "
      f"업그레이더 {top_k_metrics(y_test, y_xgb)[0.05]['caught']}명 잡음")
print(f"    → {top_k_metrics(y_test, y_xgb)[0.05]['precision']*100:.1f}% 적중률, "
      f"전체 업그레이더의 {top_k_metrics(y_test, y_xgb)[0.05]['recall']*100:.1f}% 커버")
