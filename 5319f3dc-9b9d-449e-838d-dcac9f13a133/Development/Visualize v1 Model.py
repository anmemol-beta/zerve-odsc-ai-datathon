# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false


# 4-panel diagnostic dashboard for the upgrade-prediction models.
#   Top-left  : ROC curves (LR + LGBM + base-rate baseline)
#   Top-right : Precision-Recall curves
#   Bot-left  : LightGBM feature importance (top 15 by gain)
#   Bot-right : SHAP summary — mean |SHAP| of top features

import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, precision_recall_curve

# Pull both score arrays for plotting (recompute is cheap).
lr_proba_test   = lr_model.predict_proba(scaler.transform(X_test.values.astype(float)))[:, 1]
lgbm_proba_test = lgbm_model.predict_proba(X_test.values)[:, 1]

vm_fig, vm_axes = plt.subplots(2, 2, figsize=(15, 10))

# ROC
for name, scores, color in [("logistic_reg", lr_proba_test, "#4c72b0"),
                            ("lightgbm",     lgbm_proba_test, "#dd8452")]:
    fpr, tpr, _ = roc_curve(y_test, scores)
    auc = np.trapezoid(tpr, fpr)
    vm_axes[0, 0].plot(fpr, tpr, label=f"{name}  AUC={auc:.3f}", color=color, linewidth=1.5)
vm_axes[0, 0].plot([0, 1], [0, 1], color="grey", linestyle=":", linewidth=1)
vm_axes[0, 0].set_xlabel("FPR"); vm_axes[0, 0].set_ylabel("TPR")
vm_axes[0, 0].set_title("ROC")
vm_axes[0, 0].legend(loc="lower right", fontsize=9)
vm_axes[0, 0].grid(True, alpha=0.3)

# PR
for name, scores, color in [("logistic_reg", lr_proba_test, "#4c72b0"),
                            ("lightgbm",     lgbm_proba_test, "#dd8452")]:
    prec, rec, _ = precision_recall_curve(y_test, scores)
    ap = np.trapezoid(prec[::-1], rec[::-1])
    vm_axes[0, 1].plot(rec, prec, label=f"{name}  AP={ap:.3f}", color=color, linewidth=1.5)
vm_axes[0, 1].axhline(base_rate, color="grey", linestyle=":", linewidth=1, label=f"base rate {base_rate:.3f}")
vm_axes[0, 1].set_xlabel("recall"); vm_axes[0, 1].set_ylabel("precision")
vm_axes[0, 1].set_title("Precision-Recall (preferred under imbalance)")
vm_axes[0, 1].legend(loc="upper right", fontsize=9)
vm_axes[0, 1].grid(True, alpha=0.3)

# LGBM feature importance
top_lgbm = lgbm_importance.head(15)
vm_axes[1, 0].barh(range(len(top_lgbm)), top_lgbm.values, color="#dd8452")
vm_axes[1, 0].set_yticks(range(len(top_lgbm)))
vm_axes[1, 0].set_yticklabels(top_lgbm.index, fontsize=8)
vm_axes[1, 0].invert_yaxis()
vm_axes[1, 0].set_xlabel("gain")
vm_axes[1, 0].set_title("LightGBM feature importance (top 15)")

# SHAP mean |value|
mean_abs_shap = pd.Series(np.abs(shap_values).mean(axis=0), index=feature_cols).sort_values(ascending=False).head(15)
vm_axes[1, 1].barh(range(len(mean_abs_shap)), mean_abs_shap.values, color="#55a868")
vm_axes[1, 1].set_yticks(range(len(mean_abs_shap)))
vm_axes[1, 1].set_yticklabels(mean_abs_shap.index, fontsize=8)
vm_axes[1, 1].invert_yaxis()
vm_axes[1, 1].set_xlabel("mean |SHAP|")
vm_axes[1, 1].set_title("SHAP impact (top 15)")

plt.tight_layout()
plt.show()
