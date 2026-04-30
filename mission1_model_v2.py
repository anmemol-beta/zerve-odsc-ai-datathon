"""
Mission 1 Model v2 — observation_days leakage 제거.

문제:
  observation_days = (cutoff - first_event_ts).days
    upgrader:    cutoff = upgrade_ts - 1us  → 짧음
    non-upgrader: cutoff = data_end + 1us  → 김
  → 인공 leakage. 모델 입력에서 제거.

또한 _full 윈도우 feature들은 cutoff 길이에 영향받음 — 일부는 leakage 가능성.
v2에서는 _full feature 통째로 제거하고 _1h/_24h/_7d만 사용 (윈도우 길이 고정).
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
)

PARQUET = "/Users/hunjunsin/Desktop/zerve/feature_matrix.parquet"

print("[1] Loading...", flush=True)
X_full = pd.read_parquet(PARQUET)

NON_FEAT = ["upgraded", "first_event_ts", "cohort_month", "upgrade_ts", "cutoff_ts"]

# v2: leakage 의심 컬럼 제외
LEAK_FEAT = ["observation_days"]
# _full 윈도우 feature는 cutoff 길이에 영향받음. 보수적으로 제외.
full_cols = [c for c in X_full.columns if c.endswith("_full")]
EXCLUDE = set(NON_FEAT) | set(LEAK_FEAT) | set(full_cols)

feat_cols = [c for c in X_full.columns if c not in EXCLUDE]
print(f"    features used: {len(feat_cols)}  (v1=212 → v2 dropped {212 - len(feat_cols)})")
print(f"    excluded _full: {len(full_cols)}")

train_mask = X_full["cohort_month"] < "2026-03"
test_mask = ~train_mask
print(f"    train: {train_mask.sum():,}, test: {test_mask.sum():,}")

X_train = X_full.loc[train_mask, feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
X_test = X_full.loc[test_mask, feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
y_train = X_full.loc[train_mask, "upgraded"].values
y_test = X_full.loc[test_mask, "upgraded"].values

# ────────────────────────────────────────────────
# Logistic
# ────────────────────────────────────────────────
print("\n[2] Logistic...", flush=True)
scaler = StandardScaler()
Xt_s = scaler.fit_transform(X_train)
Xv_s = scaler.transform(X_test)
logit = LogisticRegression(max_iter=2000, class_weight="balanced",
                            C=0.5, solver="liblinear", random_state=42)
logit.fit(Xt_s, y_train)
y_logit = logit.predict_proba(Xv_s)[:, 1]
logit_pr = average_precision_score(y_test, y_logit)
logit_roc = roc_auc_score(y_test, y_logit)
print(f"    PR-AUC: {logit_pr:.4f}   ROC-AUC: {logit_roc:.4f}")

# ────────────────────────────────────────────────
# XGBoost
# ────────────────────────────────────────────────
print("\n[3] XGBoost...", flush=True)
pos_w = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
xgb_model = xgb.XGBClassifier(
    objective="binary:logistic", eval_metric=["aucpr", "auc"],
    n_estimators=500, learning_rate=0.05, max_depth=5,
    subsample=0.8, colsample_bytree=0.7, min_child_weight=10,
    scale_pos_weight=pos_w, early_stopping_rounds=30,
    n_jobs=-1, random_state=42, verbosity=0,
)
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
y_xgb = xgb_model.predict_proba(X_test)[:, 1]
xgb_pr = average_precision_score(y_test, y_xgb)
xgb_roc = roc_auc_score(y_test, y_xgb)
print(f"    PR-AUC: {xgb_pr:.4f}   ROC-AUC: {xgb_roc:.4f}")
print(f"    best iter: {xgb_model.best_iteration}")

# ────────────────────────────────────────────────
# Top-K
# ────────────────────────────────────────────────
def top_k(y_t, y_s, ks=(0.01, 0.05, 0.10, 0.20)):
    n = len(y_t)
    n_pos = y_t.sum()
    order = np.argsort(y_s)[::-1]
    cum = np.cumsum(y_t[order])
    out = []
    for kp in ks:
        k = int(n * kp)
        if k == 0: continue
        out.append((kp, k, int(cum[k-1]), cum[k-1]/k, cum[k-1]/max(n_pos,1)))
    return out

print("\n[4] Top-K analysis (test set):")
for name, ys in [("Naive (n_credits_exceeded_7d)",
                   X_test["n_credits_exceeded_7d"].values),
                  ("Logistic", y_logit), ("XGBoost", y_xgb)]:
    print(f"\n  {name}:")
    print(f"    {'k%':<6}{'k':>6}{'caught':>8}{'precision':>11}{'recall':>10}")
    for kp, k, c, p, r in top_k(y_test, ys):
        print(f"    {kp*100:>4.0f}% {k:>6,} {c:>8} {p:>10.2%} {r:>9.2%}")

# Importance
print("\n[5] XGBoost top 30 features:")
imp = pd.DataFrame({"feature": feat_cols,
                    "gain": xgb_model.feature_importances_}).sort_values(
                    "gain", ascending=False).head(30)
for _, r in imp.iterrows():
    print(f"    {r['gain']:>8.4f}  {r['feature']}")

print("\n[6] Logistic top coefficients:")
coef = pd.DataFrame({"feature": feat_cols,
                     "coef": logit.coef_[0]}).sort_values("coef", ascending=False)
print("  POSITIVE:")
for _, r in coef.head(15).iterrows():
    print(f"    {r['coef']:>+7.3f}  {r['feature']}")
print("  NEGATIVE:")
for _, r in coef.tail(15).iloc[::-1].iterrows():
    print(f"    {r['coef']:>+7.3f}  {r['feature']}")

# ────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────
print("\n" + "="*60)
print(f"=== v2 SUMMARY (observation_days + _full features removed) ===")
print("="*60)
print(f"  Test: {len(y_test):,} users, {int(y_test.sum())} upgraders, "
      f"base {y_test.mean()*100:.2f}%")
print(f"  {'model':<12}{'PR-AUC':>10}{'ROC-AUC':>10}{'top1%':>9}{'top5%':>9}")
for name, ys in [("Logistic", y_logit), ("XGBoost", y_xgb)]:
    pr = average_precision_score(y_test, ys)
    roc = roc_auc_score(y_test, ys)
    tk1 = top_k(y_test, ys, (0.01,))[0]
    tk5 = top_k(y_test, ys, (0.05,))[0]
    print(f"  {name:<12}{pr:>10.4f}{roc:>10.4f}{tk1[3]:>8.2%}{tk5[3]:>8.2%}")

# 결과 저장
imp.to_csv("/Users/hunjunsin/Desktop/zerve/mission1_v2_xgb_importance.csv", index=False)
coef.to_csv("/Users/hunjunsin/Desktop/zerve/mission1_v2_logit_coef.csv", index=False)
results = pd.DataFrame({
    "person_id": X_full.loc[test_mask].index,
    "y_true": y_test,
    "score_logit": y_logit,
    "score_xgb": y_xgb,
})
results.to_csv("/Users/hunjunsin/Desktop/zerve/mission1_v2_predictions.csv", index=False)
print("\nWROTE: mission1_v2_*.csv")
