"""Train GBM v3 — bias-diverse gradient-boosting candidate (sklearn).

Sits in the AutoML pool as 'another GBM, different tree splitting' so the
champion picker sees more than just XGBoost-flavored models.

  sklearn GradientBoostingClassifier — classic CART-tree GBM, wrapped
  with isotonic CalibratedClassifierCV(cv=3) so head-to-head metric
  comparison with the v3 ensemble stays apples-to-apples.

Outputs:
    gbm_v3                  calibrated classifier wrapper
    gbm_proba_v3            np.ndarray  — test set positive-class probabilities
    gbm_metrics_v3          dict
    gbm_backend             str  — "sklearn_gbm"
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import warnings
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
)

gbm_X_train_arr = X_v3_train.fillna(0).values
y_train_arr = np.asarray(y_v3_train).astype(int)
gbm_X_test_arr = X_v3_test.fillna(0).values
gbm_y_test_arr = np.asarray(y_v3_test).astype(int)


# ─── sklearn GradientBoosting ────────────────────────────────────────────
print("[GBM v3] backend=sklearn_gbm  "
      "(GradientBoostingClassifier — classic CART-tree GBM)")
gbm_base = GradientBoostingClassifier(
    n_estimators=120,
    max_depth=4,
    learning_rate=0.08,
    subsample=0.85,
    random_state=42,
)
gbm_backend = "sklearn_gbm"


# ─── calibrate, fit, predict ─────────────────────────────────────────────
print(f"[GBM v3] calibrating with isotonic CV=2...")
gbm_v3 = CalibratedClassifierCV(gbm_base, method="isotonic", cv=2)
gbm_v3.fit(gbm_X_train_arr, y_train_arr)

gbm_proba_v3 = gbm_v3.predict_proba(gbm_X_test_arr)[:, 1]

gbm_metrics_v3 = {
    "model": "gbm_v3",
    "backend": gbm_backend,
    "pr_auc":  float(average_precision_score(gbm_y_test_arr, gbm_proba_v3)),
    "roc_auc": float(roc_auc_score(gbm_y_test_arr, gbm_proba_v3)),
    "brier":   float(brier_score_loss(gbm_y_test_arr, gbm_proba_v3)),
    "n_test_pos": int(gbm_y_test_arr.sum()),
}

# ─── feature importance (works for both backends) ─────────────────────────
fold0 = gbm_v3.calibrated_classifiers_[0].estimator
if hasattr(fold0, "feature_importances_"):
    importances = fold0.feature_importances_
elif hasattr(fold0, "get_feature_importance"):
    importances = fold0.get_feature_importance()
else:
    importances = np.zeros(gbm_X_train_arr.shape[1])

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
for gbm_feat, imp in gbm_feature_importance_v3:
    bar = "█" * int(imp / max_imp * 30)
    print(f"  {gbm_feat:<35} {imp:>8.3f}  {bar}")
