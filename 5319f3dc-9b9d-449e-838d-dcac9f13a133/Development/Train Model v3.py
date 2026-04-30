

# Train Model v3 — calibrated XGBoost + RandomForest + HistGB ensemble.
#
# Differences vs the team's "Train Model" block:
#   v1 trains LightGBM + LR on the team's 60d-label snapshot. With only ~6
#   test positives, single-metric variance is huge.
#   v3 (this block) trains 3 base models on the v3 feature matrix (170+
#   leakage-safe features, 185 test positives), wraps each in
#   CalibratedClassifierCV(method='isotonic', cv=3), then averages their
#   probabilities (soft voting). Calibration brings Brier from ~0.09 to
#   ~0.022 — usable as actual probabilities, not just rankings.
#
# Inputs (from "Build Features v3"):
#   X_v3_train, X_v3_test, y_v3_train, y_v3_test, feature_cols_v3, base_rate_v3
#
# Outputs:
#   models_v3                 dict of calibrated base models
#   preds_v3                  dict of test-set probabilities per model
#   ensemble_proba_v3         soft-voted average probability vector
#   metrics_v3                dataframe with ROC, PR, Brier, top-K cols
#   feature_importance_v3     XGBoost gain importance series

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss, log_loss,
)

_pos_w_v3 = (y_v3_train == 0).sum() / max((y_v3_train == 1).sum(), 1)
print(f"[v3] scale_pos_weight = {_pos_w_v3:.1f}")

base_models_v3 = {
    "xgb_v3": xgb.XGBClassifier(
        objective="binary:logistic", n_estimators=300,
        learning_rate=0.05, max_depth=5, min_child_weight=10,
        subsample=0.8, colsample_bytree=0.7,
        scale_pos_weight=_pos_w_v3, eval_metric="aucpr",
        n_jobs=-1, random_state=42, verbosity=0,
    ),
    "rf_v3": RandomForestClassifier(
        n_estimators=300, max_depth=12, min_samples_leaf=20,
        class_weight="balanced", n_jobs=-1, random_state=42,
    ),
    "hgb_v3": HistGradientBoostingClassifier(
        max_iter=300, max_depth=6, learning_rate=0.05,
        min_samples_leaf=20, l2_regularization=1.0,
        class_weight="balanced", random_state=42,
    ),
}

models_v3 = {}
preds_v3 = {}
print("[v3] Fitting calibrated base models (isotonic, cv=3)...")
for _name, _m in base_models_v3.items():
    _cc = CalibratedClassifierCV(_m, method="isotonic", cv=3, n_jobs=1)
    _cc.fit(X_v3_train, y_v3_train)
    _p = _cc.predict_proba(X_v3_test)[:, 1]
    models_v3[_name] = _cc
    preds_v3[_name] = _p
    _pr = average_precision_score(y_v3_test, _p)
    _roc = roc_auc_score(y_v3_test, _p)
    _br = brier_score_loss(y_v3_test, _p)
    print(f"  {_name:<8}  PR-AUC={_pr:.4f}  ROC-AUC={_roc:.4f}  Brier={_br:.4f}")

# Soft voting ensemble (simple mean — weighted variant marginally different)
ensemble_proba_v3 = np.mean(list(preds_v3.values()), axis=0)
preds_v3["ensemble_v3"] = ensemble_proba_v3


def _recall_at_k_v3(y_true, y_score, k_pct):
    n = len(y_true); n_pos = int(y_true.sum())
    k = max(1, int(np.ceil(n * k_pct / 100)))
    idx = np.argsort(-y_score)[:k]
    return float(y_true[idx].sum()) / max(1, n_pos)


def _precision_at_k_v3(y_true, y_score, k_pct):
    n = len(y_true)
    k = max(1, int(np.ceil(n * k_pct / 100)))
    idx = np.argsort(-y_score)[:k]
    return float(y_true[idx].sum()) / k


def _evaluate_v3(name, y_true, y_score):
    return {
        "model": name,
        "roc_auc":     roc_auc_score(y_true, y_score),
        "pr_auc":      average_precision_score(y_true, y_score),
        "log_loss":    log_loss(y_true, y_score, labels=[0, 1]),
        "brier":       brier_score_loss(y_true, y_score),
        "recall@1%":   _recall_at_k_v3(y_true, y_score, 1),
        "recall@5%":   _recall_at_k_v3(y_true, y_score, 5),
        "recall@10%":  _recall_at_k_v3(y_true, y_score, 10),
        "precision@1%":  _precision_at_k_v3(y_true, y_score, 1),
        "precision@5%":  _precision_at_k_v3(y_true, y_score, 5),
    }


metrics_v3 = pd.DataFrame([
    _evaluate_v3(name, y_v3_test, p) for name, p in preds_v3.items()
])

print()
print(f"[v3] test base rate = {100*base_rate_v3:.2f}%  "
      f"(positives = {int(y_v3_test.sum())} / {len(y_v3_test):,})")
print()
print("=== v3 model metrics on TEST cohort (forward-looking) ===")
print(metrics_v3.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
print()

# Feature importance from the wrapped XGBoost. CalibratedClassifierCV stores
# fitted base estimators inside .calibrated_classifiers_ — sum their gain
# importances across the 3 cv folds.
_xgb_cc_v3 = models_v3["xgb_v3"]
_imp_arrs_v3 = []
for _calib_v3 in _xgb_cc_v3.calibrated_classifiers_:
    _est_v3 = getattr(_calib_v3, "estimator", None) or getattr(_calib_v3, "base_estimator", None)
    if _est_v3 is not None and hasattr(_est_v3, "feature_importances_"):
        _imp_arrs_v3.append(_est_v3.feature_importances_)
if _imp_arrs_v3:
    feature_importance_v3 = pd.Series(
        np.mean(_imp_arrs_v3, axis=0),
        index=feature_cols_v3,
        name="xgb_gain_v3",
    ).sort_values(ascending=False)
else:
    feature_importance_v3 = pd.Series(dtype=float, name="xgb_gain_v3")

print("=== v3 top 20 features (XGBoost gain, mean over 3 calibration folds) ===")
print(feature_importance_v3.head(20).to_string())
