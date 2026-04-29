

# Trains TWO models on the leakage-safe (X_train, y_train) snapshot:
#   - Logistic regression (interpretable baseline, calibrated probabilities)
#   - LightGBM           (non-linear, top performance, SHAP-friendly)
#
# Both evaluated on (X_test, y_test) — a forward-looking snapshot one month
# later than train, so there is NO label-window overlap.
#
# Class imbalance ~53:1, so we report PR-AUC + Recall@K (the metrics that
# matter when prevalence is low). ROC-AUC is reported but secondary.
#
# Exports for downstream blocks (UI / Streamlit / Visualize Model):
#   lr_model, lgbm_model, model_metrics, shap_values, shap_explainer,
#   feature_importance, feature_cols, base_rate

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np
import lightgbm as lgb
import shap
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, average_precision_score, precision_score,
    recall_score, f1_score, log_loss,
)

feature_cols = list(X_train.columns)
base_rate = float(y_test.mean())

# ── Logistic regression — standardized features for stable coefficients
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train.values.astype(float))
X_test_s  = scaler.transform(X_test.values.astype(float))

lr_model = LogisticRegression(
    class_weight="balanced",
    max_iter=2000,
    solver="lbfgs",
)
lr_model.fit(X_train_s, y_train.values)
lr_proba = lr_model.predict_proba(X_test_s)[:, 1]

# ── LightGBM — handles missing/zero, no scaling needed
lgbm_model = lgb.LGBMClassifier(
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    max_depth=-1,
    min_child_samples=20,
    class_weight="balanced",
    random_state=42,
    verbose=-1,
)
lgbm_model.fit(X_train.values, y_train.values, feature_name=feature_cols)
lgbm_proba = lgbm_model.predict_proba(X_test.values)[:, 1]


def recall_at_k(y_true, y_score, k_pct):
    """Fraction of positives captured if we act on top-k% of predictions."""
    n = len(y_true)
    k = max(1, int(np.ceil(n * k_pct / 100)))
    top_idx = np.argsort(-y_score)[:k]
    return float(y_true.iloc[top_idx].sum()) / max(1, int(y_true.sum()))


def precision_at_k(y_true, y_score, k_pct):
    n = len(y_true)
    k = max(1, int(np.ceil(n * k_pct / 100)))
    top_idx = np.argsort(-y_score)[:k]
    return float(y_true.iloc[top_idx].sum()) / k


def evaluate(name, y_true, y_score):
    return {
        "model": name,
        "roc_auc": roc_auc_score(y_true, y_score),
        "pr_auc":  average_precision_score(y_true, y_score),
        "log_loss": log_loss(y_true, y_score, labels=[0, 1]),
        "recall@5%":  recall_at_k(y_true, y_score, 5),
        "recall@10%": recall_at_k(y_true, y_score, 10),
        "precision@5%":  precision_at_k(y_true, y_score, 5),
        "precision@10%": precision_at_k(y_true, y_score, 10),
    }


model_metrics = pd.DataFrame([
    evaluate("logistic_reg", y_test, lr_proba),
    evaluate("lightgbm",     y_test, lgbm_proba),
])

print(f"test base rate          : {100*base_rate:.2f}%  (positives = {int(y_test.sum())} / {len(y_test):,})")
print(f"random recall@5%        : ~5%  (uniform sampling baseline)")
print(f"random recall@10%       : ~10%")
print()
print("=== Model metrics on TEST snapshot (forward-looking) ===")
print(model_metrics.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
print()

# Pick the better model (by PR-AUC) for downstream UI / SHAP.
better = model_metrics.iloc[model_metrics["pr_auc"].argmax()]["model"]
print(f"=> chosen for UI / explanations : {better}")
chosen_model = lgbm_model if better == "lightgbm" else lr_model
chosen_proba = lgbm_proba if better == "lightgbm" else lr_proba
chosen_X_test = X_test if better == "lightgbm" else pd.DataFrame(X_test_s, index=X_test.index, columns=feature_cols)

# ── Feature importance: LR (standardized coefs) + LGBM (gain).
lr_importance = pd.Series(
    np.abs(lr_model.coef_[0]),
    index=feature_cols,
    name="lr_abs_std_coef",
).sort_values(ascending=False)

lgbm_importance = pd.Series(
    lgbm_model.booster_.feature_importance(importance_type="gain"),
    index=feature_cols,
    name="lgbm_gain",
).sort_values(ascending=False)

feature_importance = pd.concat([lr_importance, lgbm_importance], axis=1).fillna(0)

print()
print("=== Top 15 features (LightGBM gain) ===")
print(lgbm_importance.head(15).to_string())
print()
print("=== Top 15 features (Logistic |std coef|) ===")
print(lr_importance.head(15).to_string())

# ── SHAP values — only for the LGBM model (tree explainer is fast).
# Compute on test set to keep size sane.
shap_explainer = shap.TreeExplainer(lgbm_model)
shap_raw = shap_explainer.shap_values(X_test.values)
# In newer SHAP versions, binary classifiers may return one array (class 1) or list of two arrays.
if isinstance(shap_raw, list):
    shap_values = shap_raw[1]
else:
    shap_values = shap_raw if shap_raw.ndim == 2 else shap_raw[..., 1]

print()
print(f"shap_values shape: {shap_values.shape}")
