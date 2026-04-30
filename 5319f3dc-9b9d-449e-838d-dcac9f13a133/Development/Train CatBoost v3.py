"""Train CatBoost v3 — categorical-aware GBM (with sklearn fallback).

Two execution paths, decided at import time:

  Path A — `catboost` available
        Real CatBoostClassifier (auto class weights, depth=6, lr=0.05,
        iterations=500, early_stopping=30). Symmetric/oblivious trees +
        ordered boosting give a meaningfully different bias than XGBoost
        or LightGBM, which is the whole point of having it in the pool.

  Path B — `catboost` not installable in Zerve runtime
        Sklearn `GradientBoostingClassifier` standing in. Same family
        (gradient boosting), different tree splitting heuristic (CART
        instead of oblivious), so it still adds bias diversity to the
        pool versus XGB/RF/HGB. Honest about being a stand-in.

Both paths wrap with isotonic CalibratedClassifierCV(cv=3) for fair
comparison with the v3 ensemble.

Outputs are interchangeable:
    catboost_v3             calibrated classifier wrapper
    catboost_proba_v3       np.ndarray  — test set positive-class probabilities
    catboost_metrics_v3     dict
    catboost_backend        str  — "catboost" | "sklearn_gbm"
"""
from __future__ import annotations

import warnings
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)

# Decide path at import time
try:
    from catboost import CatBoostClassifier  # type: ignore
    CATBOOST_OK = True
except Exception as e:
    print(f"[CatBoost v3] catboost import failed ({e}) — "
          "falling back to sklearn GradientBoostingClassifier")
    CATBOOST_OK = False

from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
)

X_train_arr = X_v3_train.fillna(0).values
y_train_arr = np.asarray(y_v3_train).astype(int)
X_test_arr = X_v3_test.fillna(0).values
y_test_arr = np.asarray(y_v3_test).astype(int)


# ═══ Path A — real CatBoost ══════════════════════════════════════════════
if CATBOOST_OK:
    print("[CatBoost v3] backend=catboost  (oblivious trees + ordered boosting)")
    base = CatBoostClassifier(
        iterations=500,
        depth=6,
        learning_rate=0.05,
        auto_class_weights="Balanced",
        early_stopping_rounds=30,
        eval_metric="AUC",
        random_seed=42,
        verbose=0,
        allow_writing_files=False,
    )
    catboost_backend = "catboost"


# ═══ Path B — sklearn GradientBoosting fallback ══════════════════════════
else:
    print("[CatBoost v3] backend=sklearn_gbm  "
          "(GradientBoostingClassifier as bias-diverse stand-in)")
    from sklearn.ensemble import GradientBoostingClassifier
    base = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.85,
        random_state=42,
    )
    catboost_backend = "sklearn_gbm"


# ─── shared: calibrate, fit, predict ──────────────────────────────────────
print(f"[CatBoost v3] calibrating with isotonic CV=3...")
catboost_v3 = CalibratedClassifierCV(base, method="isotonic", cv=3)
catboost_v3.fit(X_train_arr, y_train_arr)

catboost_proba_v3 = catboost_v3.predict_proba(X_test_arr)[:, 1]

catboost_metrics_v3 = {
    "model": "catboost_v3",
    "backend": catboost_backend,
    "pr_auc":  float(average_precision_score(y_test_arr, catboost_proba_v3)),
    "roc_auc": float(roc_auc_score(y_test_arr, catboost_proba_v3)),
    "brier":   float(brier_score_loss(y_test_arr, catboost_proba_v3)),
    "n_test_pos": int(y_test_arr.sum()),
}

# ─── feature importance (works for both backends) ─────────────────────────
fold0 = catboost_v3.calibrated_classifiers_[0].estimator
if hasattr(fold0, "feature_importances_"):
    importances = fold0.feature_importances_
elif hasattr(fold0, "get_feature_importance"):
    importances = fold0.get_feature_importance()
else:
    importances = np.zeros(X_train_arr.shape[1])

fi_pairs = list(zip(feature_cols_v3, importances))
fi_pairs.sort(key=lambda kv: -kv[1])
catboost_feature_importance_v3 = fi_pairs[:20]

print()
print("=" * 60)
print(f"CATBOOST V3 — backend = {catboost_backend}")
print("=" * 60)
print(f"  PR-AUC  : {catboost_metrics_v3['pr_auc']:.4f}")
print(f"  ROC-AUC : {catboost_metrics_v3['roc_auc']:.4f}")
print(f"  Brier   : {catboost_metrics_v3['brier']:.4f}")
print(f"  test +  : {catboost_metrics_v3['n_test_pos']}")
print()
print("top 20 features (gain importance, fold 0):")
max_imp = catboost_feature_importance_v3[0][1] or 1
for feat, imp in catboost_feature_importance_v3:
    bar = "█" * int(imp / max_imp * 30)
    print(f"  {feat:<35} {imp:>8.3f}  {bar}")
