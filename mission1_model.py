"""
Mission 1 — Baseline Models (Logistic + XGBoost)

Time-based split:
  train: cohort 2025-09 ~ 2026-02
  test:  cohort 2026-03 ~ 2026-04

Models:
  1. Logistic Regression (interpretable, baseline)
  2. XGBoost (강력)
  3. Naive baseline: 랜덤 점수 / 단일 feature

Metrics:
  - PR-AUC (정직한 imbalanced 지표)
  - ROC-AUC
  - Top-K precision/recall (k=1%, 5%, 10%)
  - Calibration (Brier score)
  - Feature importance (top 30)
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import time

import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
    precision_recall_curve, roc_curve, log_loss,
)

PARQUET = "/Users/hunjunsin/Desktop/zerve/feature_matrix.parquet"

print("[1] Loading feature matrix...", flush=True)
X_full = pd.read_parquet(PARQUET)
print(f"    shape: {X_full.shape}")

# ───── 분할 ─────
TRAIN_END = "2026-03"   # 2026-03 cohort부터 test
train_mask = X_full["cohort_month"] < TRAIN_END
test_mask = ~train_mask

print(f"\n[2] Time-based cohort split @ {TRAIN_END}:")
print(f"    train: {train_mask.sum():,} users, "
      f"upgraders={int(X_full.loc[train_mask, 'upgraded'].sum())}, "
      f"rate={X_full.loc[train_mask, 'upgraded'].mean()*100:.2f}%")
print(f"    test:  {test_mask.sum():,} users, "
      f"upgraders={int(X_full.loc[test_mask, 'upgraded'].sum())}, "
      f"rate={X_full.loc[test_mask, 'upgraded'].mean()*100:.2f}%")

# 모델에 안 들어갈 컬럼
NON_FEAT = ["upgraded", "first_event_ts", "cohort_month", "upgrade_ts", "cutoff_ts"]
feat_cols = [c for c in X_full.columns if c not in NON_FEAT]
print(f"    feature count: {len(feat_cols)}")

X_train = X_full.loc[train_mask, feat_cols].copy()
X_test = X_full.loc[test_mask, feat_cols].copy()
y_train = X_full.loc[train_mask, "upgraded"].values
y_test = X_full.loc[test_mask, "upgraded"].values

# 결측/inf 처리
X_train = X_train.replace([np.inf, -np.inf], np.nan).fillna(0.0)
X_test = X_test.replace([np.inf, -np.inf], np.nan).fillna(0.0)

# ────────────────────────────────────────────────
# 0) Naive baseline: 단일 feature (n_credits_exceeded_full)
# ────────────────────────────────────────────────
print("\n[3] Baseline 0: 단일 feature 'n_credits_exceeded_full'")
naive_score = X_test["n_credits_exceeded_full"].values
nv_pr = average_precision_score(y_test, naive_score)
nv_roc = roc_auc_score(y_test, naive_score) if len(set(y_test)) > 1 else 0.5
print(f"    PR-AUC : {nv_pr:.4f}  (baseline rate {y_test.mean():.4f})")
print(f"    ROC-AUC: {nv_roc:.4f}")

# ────────────────────────────────────────────────
# 1) Logistic Regression
# ────────────────────────────────────────────────
print("\n[4] Model 1: Logistic Regression...", flush=True)
t0 = time.time()
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

logit = LogisticRegression(
    max_iter=2000,
    class_weight="balanced",  # imbalance 대응
    C=0.5,
    solver="liblinear",
    random_state=42,
)
logit.fit(X_train_s, y_train)
y_logit = logit.predict_proba(X_test_s)[:, 1]

logit_pr = average_precision_score(y_test, y_logit)
logit_roc = roc_auc_score(y_test, y_logit)
logit_brier = brier_score_loss(y_test, y_logit)
print(f"    PR-AUC : {logit_pr:.4f}  (vs baseline {y_test.mean():.4f})")
print(f"    ROC-AUC: {logit_roc:.4f}")
print(f"    Brier  : {logit_brier:.4f}")
print(f"    fit+predict: {time.time()-t0:.1f}s")

# ────────────────────────────────────────────────
# 2) XGBoost
# ────────────────────────────────────────────────
print("\n[5] Model 2: XGBoost...", flush=True)
t0 = time.time()
pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
print(f"    scale_pos_weight: {pos_weight:.1f}")

xgb_model = xgb.XGBClassifier(
    objective="binary:logistic",
    eval_metric=["aucpr", "auc"],
    n_estimators=500,
    learning_rate=0.05,
    max_depth=5,
    subsample=0.8,
    colsample_bytree=0.7,
    min_child_weight=10,
    scale_pos_weight=pos_weight,
    early_stopping_rounds=30,
    n_jobs=-1,
    random_state=42,
    verbosity=0,
)
xgb_model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False,
)
y_xgb = xgb_model.predict_proba(X_test)[:, 1]

xgb_pr = average_precision_score(y_test, y_xgb)
xgb_roc = roc_auc_score(y_test, y_xgb)
xgb_brier = brier_score_loss(y_test, y_xgb)
print(f"    PR-AUC : {xgb_pr:.4f}")
print(f"    ROC-AUC: {xgb_roc:.4f}")
print(f"    Brier  : {xgb_brier:.4f}")
print(f"    best iter: {xgb_model.best_iteration}, fit: {time.time()-t0:.1f}s")

# ────────────────────────────────────────────────
# Top-K precision/recall
# ────────────────────────────────────────────────
def top_k_metrics(y_true, y_score, k_pcts=(0.01, 0.05, 0.10, 0.20)):
    n = len(y_true)
    n_pos = y_true.sum()
    out = []
    order = np.argsort(y_score)[::-1]
    sorted_y = y_true[order]
    cum = np.cumsum(sorted_y)
    for kp in k_pcts:
        k = int(n * kp)
        if k == 0: continue
        prec = cum[k - 1] / k
        recall = cum[k - 1] / max(n_pos, 1)
        out.append((kp, k, int(cum[k - 1]), prec, recall))
    return out

print("\n[6] Top-K analysis (test set):")
for name, y_score in [("Naive", naive_score), ("Logistic", y_logit), ("XGBoost", y_xgb)]:
    print(f"  {name}:")
    print(f"    {'k%':<6}{'k':>6}{'caught':>8}{'precision':>11}{'recall':>10}")
    for kp, k, c, p, r in top_k_metrics(y_test, y_score):
        print(f"    {kp*100:>4.0f}% {k:>6,} {c:>8} {p:>10.2%} {r:>9.2%}")

# ────────────────────────────────────────────────
# Feature importance (XGBoost)
# ────────────────────────────────────────────────
print("\n[7] XGBoost feature importance — top 30:")
imp = pd.DataFrame({
    "feature": feat_cols,
    "gain": xgb_model.feature_importances_,
}).sort_values("gain", ascending=False).head(30)
for _, row in imp.iterrows():
    print(f"    {row['gain']:>8.4f}  {row['feature']}")

# Logistic 계수 — top positive / top negative
print("\n[8] Logistic top coefficients (sign-aware):")
coef = pd.DataFrame({
    "feature": feat_cols,
    "coef": logit.coef_[0],
}).sort_values("coef", ascending=False)
print(f"    Top 15 POSITIVE (업그레이드 ↑):")
for _, row in coef.head(15).iterrows():
    print(f"      {row['coef']:>+7.3f}  {row['feature']}")
print(f"    Top 15 NEGATIVE (업그레이드 ↓):")
for _, row in coef.tail(15).iloc[::-1].iterrows():
    print(f"      {row['coef']:>+7.3f}  {row['feature']}")

# ────────────────────────────────────────────────
# 결과 저장
# ────────────────────────────────────────────────
results = pd.DataFrame({
    "person_id": X_full.loc[test_mask].index,
    "cohort_month": X_full.loc[test_mask, "cohort_month"].values,
    "y_true": y_test,
    "score_naive": naive_score,
    "score_logit": y_logit,
    "score_xgb": y_xgb,
})
results.to_csv("/Users/hunjunsin/Desktop/zerve/mission1_test_predictions.csv", index=False)
imp.to_csv("/Users/hunjunsin/Desktop/zerve/mission1_xgb_importance.csv", index=False)
coef.to_csv("/Users/hunjunsin/Desktop/zerve/mission1_logit_coef.csv", index=False)

print("\n" + "="*60)
print("=== SUMMARY ===")
print("="*60)
print(f"  Test set: {len(y_test):,} users, {int(y_test.sum())} upgraders, "
      f"base rate {y_test.mean()*100:.2f}%")
print(f"  {'model':<12}{'PR-AUC':>10}{'ROC-AUC':>10}{'lift@5%':>10}")
for name, y_score, pr, roc in [
    ("Naive",    naive_score, nv_pr,    nv_roc),
    ("Logistic", y_logit,     logit_pr, logit_roc),
    ("XGBoost",  y_xgb,       xgb_pr,   xgb_roc),
]:
    tk = top_k_metrics(y_test, y_score, (0.05,))[0]
    lift = tk[3] / y_test.mean() if y_test.mean() > 0 else 0
    print(f"  {name:<12}{pr:>10.4f}{roc:>10.4f}{lift:>9.2f}x")
print(f"\nWROTE: mission1_test_predictions.csv, mission1_xgb_importance.csv, mission1_logit_coef.csv")
