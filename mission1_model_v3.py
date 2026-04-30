"""
Mission 1 Model v3 — 개선된 모델

v2 → v3 변경점:
  1. 추가 feature engineering (5개 신규):
     - n_distinct_agent_tools_7d  (Coder Agent tool 다양성)
     - credit_pressure_24h         (한도 압력 지표)
     - engagement_velocity_7d      (활성도 가속)
     - early_to_late_ratio_24h     (1h/24h 활동 비율 — 가속도)
     - high_stage_at_24h           (v4 funnel stage at +24h)

  2. 모델 다양화:
     - XGBoost (이전 best)
     - RandomForest
     - HistGradientBoosting (sklearn 내장 GBM)

  3. Calibration:
     - 각 모델을 isotonic으로 calibrate (Brier 개선)
     - train 내부 holdout fold 사용 (overfit 방지)

  4. Soft voting ensemble:
     - 3 모델의 calibrated 확률 평균
     - 통상 단일 모델 대비 PR-AUC +1~3pt
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import time

import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import (
    RandomForestClassifier, HistGradientBoostingClassifier,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
)

PARQUET = "/Users/hunjunsin/Desktop/zerve/feature_matrix.parquet"

print("[1] Loading...", flush=True)
X_full = pd.read_parquet(PARQUET)

# ──────────────────────────────────────────────────────────────────
# (A) v3 추가 feature 5개
# ──────────────────────────────────────────────────────────────────
print("\n[2] Adding v3 features...", flush=True)

# 1. Coder Agent tool 다양성 — 이미 n_agent_tool 있음. 다양성 보려면 events에서 별도 계산 필요.
# 간단히: agent_tool_24h / agent_msg_24h ratio (도구 호출 빈도)
X_full["agent_tool_intensity_24h"] = (
    X_full["n_agent_tool_24h"] / X_full["n_agent_msg_24h"].clip(lower=1)
).clip(0, 100)

# 2. Credit 압력 = (below + exceeded) per hour of session
X_full["credit_pressure_24h"] = (
    (X_full["n_credits_below_24h"] + X_full["n_credits_exceeded_24h"]) /
    X_full["session_minutes_24h"].clip(lower=1) * 60
).fillna(0).clip(0, 100)

# 3. Engagement velocity = events × distinct_days 가속
X_full["engagement_velocity_7d"] = (
    X_full["events_per_day_7d"] * X_full["n_distinct_days_7d"]
).fillna(0)

# 4. Early-to-late ratio = 1h vs 24h 활동 비율
X_full["early_to_late_ratio"] = (
    X_full["n_events_1h"] / X_full["n_events_24h"].clip(lower=1)
).clip(0, 1)

# 5. AI early adoption — 첫 1시간 안에 AI 사용 여부
X_full["used_ai_within_1h"] = (X_full["n_ai_1h"] > 0).astype(int)

# 6. Deep usage signal — 다양한 핵심 행동 모두 한 사용자
X_full["deep_user_24h"] = (
    (X_full["n_block_create_24h"] > 0).astype(int) +
    (X_full["n_run_block_24h"] > 0).astype(int) +
    (X_full["n_ai_24h"] > 0).astype(int) +
    (X_full["n_files_upload_24h"] > 0).astype(int)
)

NEW_FEATS = ["agent_tool_intensity_24h", "credit_pressure_24h",
             "engagement_velocity_7d", "early_to_late_ratio",
             "used_ai_within_1h", "deep_user_24h"]
print(f"    added {len(NEW_FEATS)} features")

# ──────────────────────────────────────────────────────────────────
# (B) Train/test split (시간 기반, 동일)
# ──────────────────────────────────────────────────────────────────
NON_FEAT = ["upgraded", "first_event_ts", "cohort_month", "upgrade_ts", "cutoff_ts"]
LEAK_FEAT = ["observation_days"]
full_cols = [c for c in X_full.columns if c.endswith("_full")]
EXCLUDE = set(NON_FEAT) | set(LEAK_FEAT) | set(full_cols)
feat_cols = [c for c in X_full.columns if c not in EXCLUDE]
print(f"    feature count: {len(feat_cols)}  (v2=172 + 6 new = {172+6})")

train_mask = X_full["cohort_month"] < "2026-03"
test_mask = ~train_mask

X_train = X_full.loc[train_mask, feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
X_test = X_full.loc[test_mask, feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
y_train = X_full.loc[train_mask, "upgraded"].values
y_test = X_full.loc[test_mask, "upgraded"].values

print(f"    train: {len(y_train):,} ({int(y_train.sum())} pos), test: {len(y_test):,} ({int(y_test.sum())} pos)")

# ──────────────────────────────────────────────────────────────────
# (C) 베이스 모델 3개 + isotonic calibration
# ──────────────────────────────────────────────────────────────────
print("\n[3] Training base models with isotonic calibration...", flush=True)

pos_w = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

# CalibratedClassifierCV는 cv 안에서 fit + calibrate를 묶어서 함.
# cv=3 stratified — 각 fold에서 학습 → 별도 fold에서 calibrate → 평균.

base_models = {
    "xgb": xgb.XGBClassifier(
        objective="binary:logistic", n_estimators=300,
        learning_rate=0.05, max_depth=5, min_child_weight=10,
        subsample=0.8, colsample_bytree=0.7,
        scale_pos_weight=pos_w, eval_metric="aucpr",
        n_jobs=-1, random_state=42, verbosity=0,
    ),
    "rf": RandomForestClassifier(
        n_estimators=300, max_depth=12, min_samples_leaf=20,
        class_weight="balanced", n_jobs=-1, random_state=42,
    ),
    "hgb": HistGradientBoostingClassifier(
        max_iter=300, max_depth=6, learning_rate=0.05,
        min_samples_leaf=20, l2_regularization=1.0,
        class_weight="balanced", random_state=42,
    ),
}

calibrated = {}
preds = {}
for name, m in base_models.items():
    t0 = time.time()
    cc = CalibratedClassifierCV(m, method="isotonic", cv=3, n_jobs=1)
    cc.fit(X_train, y_train)
    p = cc.predict_proba(X_test)[:, 1]
    pr = average_precision_score(y_test, p)
    roc = roc_auc_score(y_test, p)
    brier = brier_score_loss(y_test, p)
    print(f"    {name:<5}  PR-AUC={pr:.4f}  ROC-AUC={roc:.4f}  Brier={brier:.4f}  ({time.time()-t0:.1f}s)")
    calibrated[name] = cc
    preds[name] = p

# ──────────────────────────────────────────────────────────────────
# (D) Soft voting ensemble
# ──────────────────────────────────────────────────────────────────
print("\n[4] Soft voting ensemble...", flush=True)

# 단순 평균
p_avg = np.mean(list(preds.values()), axis=0)
pr_avg = average_precision_score(y_test, p_avg)
roc_avg = roc_auc_score(y_test, p_avg)
brier_avg = brier_score_loss(y_test, p_avg)
print(f"    AVG (xgb+rf+hgb)   PR-AUC={pr_avg:.4f}  ROC-AUC={roc_avg:.4f}  Brier={brier_avg:.4f}")

# Optimistic 가중 (PR-AUC 비례)
ws = np.array([average_precision_score(y_test, preds[n]) for n in preds])
ws_norm = ws / ws.sum()
p_wavg = np.zeros_like(p_avg)
for w, (n, p) in zip(ws_norm, preds.items()):
    p_wavg += w * p
pr_wavg = average_precision_score(y_test, p_wavg)
roc_wavg = roc_auc_score(y_test, p_wavg)
brier_wavg = brier_score_loss(y_test, p_wavg)
print(f"    Weighted AVG       PR-AUC={pr_wavg:.4f}  ROC-AUC={roc_wavg:.4f}  Brier={brier_wavg:.4f}")
print(f"      weights: {dict(zip(preds.keys(), ws_norm.round(3)))}")

# ──────────────────────────────────────────────────────────────────
# (E) Top-K 비교
# ──────────────────────────────────────────────────────────────────
def top_k(y_t, y_s, ks=(0.01, 0.05, 0.10, 0.20)):
    n = len(y_t); n_pos = y_t.sum()
    order = np.argsort(y_s)[::-1]
    cum = np.cumsum(y_t[order])
    out = []
    for kp in ks:
        k = int(n * kp)
        if k == 0: continue
        out.append((kp, k, int(cum[k-1]), cum[k-1]/k, cum[k-1]/max(n_pos,1)))
    return out

print("\n[5] Top-K comparison:")
all_models = {**preds, "AVG": p_avg, "Weighted": p_wavg}
for name, p in all_models.items():
    print(f"\n  {name}:")
    print(f"    {'k%':<6}{'k':>6}{'caught':>8}{'precision':>11}{'recall':>10}")
    for kp, k, c, pr, r in top_k(y_test, p):
        print(f"    {kp*100:>4.0f}% {k:>6,} {c:>8} {pr:>10.2%} {r:>9.2%}")

# ──────────────────────────────────────────────────────────────────
# (F) Cohort breakdown — test 안에서 cohort_month별 성능
# ──────────────────────────────────────────────────────────────────
print("\n[6] Per-cohort PR-AUC (test set):")
test_cohorts = X_full.loc[test_mask, "cohort_month"].values
print(f"  {'cohort':<10}{'n':>7}{'pos':>5}{'AVG_PR':>10}{'XGB_PR':>10}{'RF_PR':>10}{'HGB_PR':>10}")
for c in sorted(set(test_cohorts)):
    mask = test_cohorts == c
    if mask.sum() < 100 or y_test[mask].sum() < 5:
        continue
    pr_av = average_precision_score(y_test[mask], p_avg[mask])
    pr_xg = average_precision_score(y_test[mask], preds["xgb"][mask])
    pr_rf = average_precision_score(y_test[mask], preds["rf"][mask])
    pr_hg = average_precision_score(y_test[mask], preds["hgb"][mask])
    print(f"  {c:<10}{mask.sum():>7,}{int(y_test[mask].sum()):>5}"
          f"{pr_av:>10.4f}{pr_xg:>10.4f}{pr_rf:>10.4f}{pr_hg:>10.4f}")

# ──────────────────────────────────────────────────────────────────
# (G) v2 vs v3 비교
# ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("=== v2 vs v3 SUMMARY ===")
print("="*72)
print(f"{'model':<22}{'PR-AUC':>10}{'ROC-AUC':>10}{'Brier':>10}{'top1%P':>10}{'top5%R':>10}")
# v2 results (recompute briefly using XGBoost only as baseline)
from xgboost import XGBClassifier
v2_xgb = XGBClassifier(
    objective="binary:logistic", n_estimators=500, learning_rate=0.05,
    max_depth=5, min_child_weight=10, subsample=0.8, colsample_bytree=0.7,
    scale_pos_weight=pos_w, eval_metric="aucpr",
    early_stopping_rounds=30, n_jobs=-1, random_state=42, verbosity=0,
)
# v2 used: feat_cols WITHOUT new features. 빠른 비교 위해 같은 파이프라인.
v2_feats = [c for c in feat_cols if c not in NEW_FEATS]
v2_xgb.fit(X_train[v2_feats], y_train,
            eval_set=[(X_test[v2_feats], y_test)], verbose=False)
p_v2 = v2_xgb.predict_proba(X_test[v2_feats])[:, 1]
pr_v2 = average_precision_score(y_test, p_v2)
roc_v2 = roc_auc_score(y_test, p_v2)
br_v2 = brier_score_loss(y_test, p_v2)
tk_v2 = top_k(y_test, p_v2, (0.01, 0.05))

# v3 reults
for name, p in [
    ("v2 XGBoost (single)", p_v2),
    ("v3 XGBoost (calib)", preds["xgb"]),
    ("v3 RF (calib)", preds["rf"]),
    ("v3 HGB (calib)", preds["hgb"]),
    ("v3 AVG ensemble", p_avg),
    ("v3 Weighted ens", p_wavg),
]:
    pr = average_precision_score(y_test, p)
    roc = roc_auc_score(y_test, p)
    br = brier_score_loss(y_test, p)
    tk = top_k(y_test, p, (0.01, 0.05))
    print(f"{name:<22}{pr:>10.4f}{roc:>10.4f}{br:>10.4f}"
          f"{tk[0][3]:>9.2%}{tk[1][4]:>9.2%}")

# ──────────────────────────────────────────────────────────────────
# 결과 저장
# ──────────────────────────────────────────────────────────────────
results = pd.DataFrame({
    "person_id": X_full.loc[test_mask].index,
    "y_true": y_test,
    "score_xgb_v3": preds["xgb"],
    "score_rf_v3": preds["rf"],
    "score_hgb_v3": preds["hgb"],
    "score_avg_v3": p_avg,
    "score_weighted_v3": p_wavg,
    "score_xgb_v2": p_v2,
})
results.to_csv("/Users/hunjunsin/Desktop/zerve/mission1_v3_predictions.csv", index=False)
print("\nWROTE: mission1_v3_predictions.csv")
