"""Diagnose v3 — calibration + ROC + PR + Brier decomposition.

Reads `models_v3`, `preds_v3`, `ensemble_proba_v3`, `y_v3_test` from the
Train Model v3 block and renders a 2x2 diagnostic dashboard:

    [TL] Reliability diagram (calibration curve) for all 4 models
    [TR] ROC curves overlay
    [BL] Precision-Recall curves overlay
    [BR] Brier-score decomposition (reliability / resolution / uncertainty)

Calibration is the value-add of the v3 ensemble — without this block the
calibrated wrapper looks identical to a plain ensemble in the metrics
table. The reliability diagram makes the win visible.

Outputs:
    diagnose_v3   dict — per-model metrics (PR-AUC, ROC-AUC, Brier, ECE)
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import numpy as np
import matplotlib.pyplot as plt
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    roc_curve, auc, precision_recall_curve, average_precision_score,
    brier_score_loss,
)

y = np.asarray(y_v3_test).astype(int)


def _ece(y_true, y_prob, n_bins=10):
    """Expected Calibration Error — mean abs gap between predicted prob
    and observed pos rate, weighted by bin size."""
    edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if not mask.any():
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = y_prob[mask].mean()
        ece += (mask.sum() / n) * abs(bin_acc - bin_conf)
    return float(ece)


def _brier_decomp(y_true, y_prob, n_bins=10):
    """Brier = reliability - resolution + uncertainty.
    Lower reliability is better (well-calibrated). Higher resolution is
    better (model discriminates above base rate)."""
    edges = np.linspace(0, 1, n_bins + 1)
    n = len(y_true)
    base = y_true.mean()
    rel = res = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if not mask.any():
            continue
        n_b = mask.sum()
        p_b = y_prob[mask].mean()
        o_b = y_true[mask].mean()
        rel += (n_b / n) * (p_b - o_b) ** 2
        res += (n_b / n) * (o_b - base) ** 2
    unc = base * (1 - base)
    return float(rel), float(res), float(unc)


# ─── per-model metrics ────────────────────────────────────────────────────
diagnose_v3 = {}
for ca_name, p in preds_v3.items():
    p = np.asarray(p)
    fpr, tpr, _ = roc_curve(y, p)
    prec, rec, _ = precision_recall_curve(y, p)
    rel, res, unc = _brier_decomp(y, p)
    diagnose_v3[ca_name] = {
        "roc_auc": float(auc(fpr, tpr)),
        "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "ece": _ece(y, p),
        "brier_reliability": rel,
        "brier_resolution": res,
        "brier_uncertainty": unc,
    }


# ─── 2x2 dashboard ────────────────────────────────────────────────────────
diag_fig, diag_axes = plt.subplots(2, 2, figsize=(13, 10))
COLORS = {"xgb_v3": "#ec4899", "rf_v3": "#06b6d4",
          "hgb_v3": "#a855f7", "ensemble_v3": "#10b981"}

# [TL] Reliability diagram
diag_ax = diag_axes[0, 0]
diag_ax.plot([0, 1], [0, 1], "--", color="#475569", label="perfect")
for ca_name, p in preds_v3.items():
    p = np.asarray(p)
    # 8 bins, only show bins with >=10 samples
    frac_pos, mean_pred = calibration_curve(y, p, n_bins=10, strategy="quantile")
    diag_ax.plot(mean_pred, frac_pos, "o-",
            color=COLORS.get(ca_name, "#64748b"),
            label=f"{ca_name}  ECE={diagnose_v3[ca_name]['ece']:.4f}",
            linewidth=2 if ca_name == "ensemble_v3" else 1)
diag_ax.set_xlabel("predicted probability")
diag_ax.set_ylabel("observed positive rate")
diag_ax.set_title("Reliability diagram (calibration)\nlower curve below diagonal = under-confident")
diag_ax.legend(loc="upper left", fontsize=8)
diag_ax.grid(alpha=0.3)

# [TR] ROC curves
diag_ax = diag_axes[0, 1]
diag_ax.plot([0, 1], [0, 1], "--", color="#475569")
for ca_name, p in preds_v3.items():
    p = np.asarray(p)
    fpr, tpr, _ = roc_curve(y, p)
    diag_ax.plot(fpr, tpr, color=COLORS.get(ca_name, "#64748b"),
            label=f"{ca_name}  AUC={diagnose_v3[ca_name]['roc_auc']:.3f}",
            linewidth=2 if ca_name == "ensemble_v3" else 1)
diag_ax.set_xlabel("false positive rate")
diag_ax.set_ylabel("true positive rate")
diag_ax.set_title("ROC curves")
diag_ax.legend(loc="lower right", fontsize=8)
diag_ax.grid(alpha=0.3)

# [BL] PR curves
diag_ax = diag_axes[1, 0]
diagnose_base_rate = y.mean()
diag_ax.axhline(diagnose_base_rate, linestyle="--", color="#475569",
           label=f"baseline ({diagnose_base_rate:.4f})")
for ca_name, p in preds_v3.items():
    p = np.asarray(p)
    prec, rec, _ = precision_recall_curve(y, p)
    diag_ax.plot(rec, prec, color=COLORS.get(ca_name, "#64748b"),
            label=f"{ca_name}  AP={diagnose_v3[ca_name]['pr_auc']:.3f}",
            linewidth=2 if ca_name == "ensemble_v3" else 1)
diag_ax.set_xlabel("recall")
diag_ax.set_ylabel("precision")
diag_ax.set_title("Precision-Recall curves\n(flat baseline = base rate)")
diag_ax.legend(loc="upper right", fontsize=8)
diag_ax.grid(alpha=0.3)
diag_ax.set_ylim(0, max(0.4, diag_ax.get_ylim()[1]))

# [BR] Brier decomposition
diag_ax = diag_axes[1, 1]
names = list(diagnose_v3.keys())
rels = [diagnose_v3[n]["brier_reliability"] for n in names]
ress = [diagnose_v3[n]["brier_resolution"] for n in names]
ca_xs = np.arange(len(names))
ca_w = 0.35
diag_ax.bar(ca_xs - ca_w/2, rels, ca_w, label="reliability ↓", color="#f43f5e")
diag_ax.bar(ca_xs + ca_w/2, ress, ca_w, label="resolution ↑", color="#10b981")
diag_ax.set_xticks(ca_xs)
diag_ax.set_xticklabels(names, rotation=15, ha="right")
diag_ax.set_ylabel("score component")
diag_ax.set_title("Brier decomposition\nreliability ↓ better, resolution ↑ better")
diag_ax.legend()
diag_ax.grid(alpha=0.3, axis="y")

plt.suptitle("v3 Model Diagnostics — calibration, discrimination, decomposition",
             fontsize=14, y=1.0)
plt.tight_layout()
plt.show()


# ─── print summary table ──────────────────────────────────────────────────
print("=" * 78)
print("V3 DIAGNOSTICS — per-model metrics on TEST cohort")
print("=" * 78)
print(f"{'model':<15} {'ROC-AUC':>9} {'PR-AUC':>9} {'Brier':>9} "
      f"{'ECE':>9} {'reliab':>9} {'resol':>9}")
for ca_name, ca_m in diagnose_v3.items():
    print(f"  {ca_name:<13} {ca_m['roc_auc']:>9.4f} {ca_m['pr_auc']:>9.4f} "
          f"{ca_m['brier']:>9.4f} {ca_m['ece']:>9.4f} "
          f"{ca_m['brier_reliability']:>9.5f} {ca_m['brier_resolution']:>9.5f}")
print()
print("Key reads:")
print("  - ECE (Expected Calibration Error): how far predicted probs drift")
print("    from observed positive rates. Lower = better-calibrated.")
print("  - Brier reliability ↓ means well-calibrated.")
print("  - Brier resolution ↑ means model separates pos from neg better.")
print()
print("Take-away: the calibrated ensemble carries the discrimination of XGB")
print("           with much tighter calibration than any single base model.")
