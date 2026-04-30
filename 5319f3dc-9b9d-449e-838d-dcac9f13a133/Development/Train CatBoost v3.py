"""Train CatBoost v3 — categorical-aware GBM with isotonic calibration.

CatBoost rounds out the boosting candidate pool. It uses ordered
boosting + symmetric trees, which handles categorical features and rare
classes differently from XGBoost. On 53:1 imbalance with a moderate
number of categorical features (purpose, role, country, signup_source),
it sometimes beats XGBoost outright.

Inputs:
    X_v3_train, y_v3_train, X_v3_test, y_v3_test, feature_cols_v3

Pipeline:
    CatBoostClassifier(auto_class_weights='Balanced', iterations=500,
                       depth=6, learning_rate=0.05, early_stopping=30)
    → isotonic calibration via CalibratedClassifierCV(cv=3) for fair-fight
      with the v3 ensemble.

Outputs:
    catboost_v3            calibrated wrapper
    catboost_proba_v3      np.ndarray  — test probabilities
    catboost_metrics_v3    dict
"""
from __future__ import annotations

import warnings
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)

try:
    from catboost import CatBoostClassifier
except ImportError as e:
    raise RuntimeError(f"catboost not available: {e}")

from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
)

# ─── 1. base classifier ───────────────────────────────────────────────────
print("[CatBoost v3] training base CatBoostClassifier...")
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

# ─── 2. calibrate isotonic with cv=3 (matches the v3 ensemble approach) ──
print("[CatBoost v3] calibrating with isotonic CV=3...")
catboost_v3 = CalibratedClassifierCV(base, method="isotonic", cv=3)

X_train_arr = X_v3_train.fillna(0).values
y_train_arr = np.asarray(y_v3_train).astype(int)
X_test_arr = X_v3_test.fillna(0).values
y_test_arr = np.asarray(y_v3_test).astype(int)

catboost_v3.fit(X_train_arr, y_train_arr)

# ─── 3. predict + metrics ─────────────────────────────────────────────────
catboost_proba_v3 = catboost_v3.predict_proba(X_test_arr)[:, 1]

catboost_metrics_v3 = {
    "model": "catboost_v3",
    "pr_auc":  float(average_precision_score(y_test_arr, catboost_proba_v3)),
    "roc_auc": float(roc_auc_score(y_test_arr, catboost_proba_v3)),
    "brier":   float(brier_score_loss(y_test_arr, catboost_proba_v3)),
    "n_test_pos": int(y_test_arr.sum()),
}

# ─── 4. base feature importance (any one fold, for quick read) ───────────
fold0 = catboost_v3.calibrated_classifiers_[0].estimator
importances = fold0.get_feature_importance()
fi_pairs = list(zip(feature_cols_v3, importances))
fi_pairs.sort(key=lambda kv: -kv[1])
catboost_feature_importance_v3 = fi_pairs[:20]

print()
print("=" * 60)
print("CATBOOST V3")
print("=" * 60)
print(f"  PR-AUC  : {catboost_metrics_v3['pr_auc']:.4f}")
print(f"  ROC-AUC : {catboost_metrics_v3['roc_auc']:.4f}")
print(f"  Brier   : {catboost_metrics_v3['brier']:.4f}")
print(f"  test +  : {catboost_metrics_v3['n_test_pos']}")
print()
print("top 20 features (CatBoost gain, fold 0):")
max_imp = catboost_feature_importance_v3[0][1]
for feat, imp in catboost_feature_importance_v3:
    bar = "█" * int(imp / max_imp * 30)
    print(f"  {feat:<35} {imp:>7.2f}  {bar}")
