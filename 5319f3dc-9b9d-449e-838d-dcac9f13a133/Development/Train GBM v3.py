"""Train GBM v3 — bias-diverse gradient-boosting candidate (sklearn primary).

Sits in the AutoML pool as 'another GBM, different tree splitting' so the
champion picker sees more than just XGBoost-flavored models. Two paths,
decided at import time:

  Path A — sklearn GradientBoostingClassifier (PRIMARY in Zerve)
        Classic CART-tree GBM, isotonic CalibratedClassifierCV(cv=3).
        Pure sklearn, zero extra dependencies, always installs cleanly.

  Path B — catboost (kept available for richer environments)
        If `catboost` happens to be importable, the block uses it instead
        for its symmetric/oblivious trees + ordered boosting (a more
        meaningfully different bias than path A). In Zerve catboost is
        not in `requirements`, so this path normally won't trigger.

Both paths wrap with isotonic CalibratedClassifierCV(cv=3) so head-to-head
metric comparison with the v3 ensemble stays apples-to-apples.

Outputs are interchangeable:
    gbm_v3                  calibrated classifier wrapper
    gbm_proba_v3            np.ndarray  — test set positive-class probabilities
    gbm_metrics_v3          dict
    gbm_backend             str  — "sklearn_gbm" | "catboost"

The historical name 'CatBoost' is retained as a comment because earlier
canvas runs used real catboost; the block intent (bias-diverse GBM) is
unchanged.
"""
import warnings
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)

# Try catboost first only as an opportunistic upgrade; sklearn is the default.
try:
    from catboost import CatBoostClassifier  # type: ignore
    CATBOOST_OK = True
except Exception as e:
    print(f"[GBM v3] catboost not available ({e}) — using sklearn GradientBoosting")
    CATBOOST_OK = False

from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
)

X_train_arr = X_v3_train.fillna(0).values
y_train_arr = np.asarray(y_v3_train).astype(int)
X_test_arr = X_v3_test.fillna(0).values
y_test_arr = np.asarray(y_v3_test).astype(int)


# ═══ Path A — catboost (only if importable; not in Zerve requirements) ═══
if CATBOOST_OK:
    print("[GBM v3] backend=catboost  (oblivious trees + ordered boosting)")
    gbm_base = CatBoostClassifier(
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
    gbm_backend = "catboost"


# ═══ Path B — sklearn GradientBoosting (PRIMARY) ═════════════════════════
else:
    print("[GBM v3] backend=sklearn_gbm  "
          "(GradientBoostingClassifier — classic CART-tree GBM)")
    from sklearn.ensemble import GradientBoostingClassifier
    gbm_base = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.85,
        random_state=42,
    )
    gbm_backend = "sklearn_gbm"


# ─── shared: calibrate, fit, predict ──────────────────────────────────────
print(f"[GBM v3] calibrating with isotonic CV=3...")
gbm_v3 = CalibratedClassifierCV(gbm_base, method="isotonic", cv=3)
gbm_v3.fit(X_train_arr, y_train_arr)

gbm_proba_v3 = gbm_v3.predict_proba(X_test_arr)[:, 1]

gbm_metrics_v3 = {
    "model": "gbm_v3",
    "backend": gbm_backend,
    "pr_auc":  float(average_precision_score(y_test_arr, gbm_proba_v3)),
    "roc_auc": float(roc_auc_score(y_test_arr, gbm_proba_v3)),
    "brier":   float(brier_score_loss(y_test_arr, gbm_proba_v3)),
    "n_test_pos": int(y_test_arr.sum()),
}

# ─── feature importance (works for both backends) ─────────────────────────
fold0 = gbm_v3.calibrated_classifiers_[0].estimator
if hasattr(fold0, "feature_importances_"):
    importances = fold0.feature_importances_
elif hasattr(fold0, "get_feature_importance"):
    importances = fold0.get_feature_importance()
else:
    importances = np.zeros(X_train_arr.shape[1])

fi_pairs = list(zip(feature_cols_v3, importances))
fi_pairs.sort(key=lambda kv: -kv[1])
gbm_feature_importance_v3 = fi_pairs[:20]

print()
print("=" * 60)
print(f"GBM V3 — backend = {gbm_backend}")
print("=" * 60)
print(f"  PR-AUC  : {gbm_metrics_v3['pr_auc']:.4f}")
print(f"  ROC-AUC : {gbm_metrics_v3['roc_auc']:.4f}")
print(f"  Brier   : {gbm_metrics_v3['brier']:.4f}")
print(f"  test +  : {gbm_metrics_v3['n_test_pos']}")
print()
print("top 20 features (gain importance, fold 0):")
max_imp = gbm_feature_importance_v3[0][1] or 1
for feat, imp in gbm_feature_importance_v3:
    bar = "█" * int(imp / max_imp * 30)
    print(f"  {feat:<35} {imp:>8.3f}  {bar}")
