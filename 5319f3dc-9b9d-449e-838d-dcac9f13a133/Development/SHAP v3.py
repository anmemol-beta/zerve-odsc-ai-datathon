"""SHAP v3 — interpretability for the v3 ensemble (no shap library required).

Two execution paths, picked at runtime:

    Path A — `shap` library available
        Use shap.TreeExplainer over the 3 calibration folds. This is the
        fastest and most exact route, but shap has heavy LLVM/llvmlite
        deps that frequently break on Lambda/Fargate runtimes.

    Path B — `shap` not available  (DEFAULT in Zerve)
        Implement SHAP from scratch using the Štrumbelj & Kononenko (2014)
        Monte Carlo sampling estimator. Pure numpy — no shap, no extra deps.
        Algorithm:
            for each Monte Carlo iteration r in 1..R:
                sample a random permutation π of features
                sample a background instance b
                walk left→right through π, replacing b's features with x's:
                    φ_i  +=  f(x_with_i_revealed) - f(x_without_i_revealed)
            φ_i = mean over R iterations
        Theoretical guarantee: as R→∞, φ converges to true Shapley values.

Either way, outputs are interchangeable:

    shap_values_v3        np.ndarray  (n_explain, n_features)
    shap_summary_v3       pd.DataFrame  — top-20 mean |φ|
    interpret_method      str  — "shap_tree" | "sampling_pure_numpy"

Inputs (canvas namespace):
    models_v3             — dict of CalibratedClassifierCV per base model
    X_v3_test, y_v3_test  — test cohort
    X_v3_train            — used as the "background distribution" for sampling
    feature_cols_v3       — column order
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ─── try real shap, but don't require it ────────────────────────────────
try:
    import shap  # type: ignore
    SHAP_OK = True
except Exception as e:
    print(f"[SHAP v3] shap not importable ({e})")
    print("[SHAP v3] → using pure-numpy sampling estimator instead")
    SHAP_OK = False

ensemble_model = models_v3.get("xgb_v3", None)  # use XGB base for explanations
if ensemble_model is None:
    raise RuntimeError("models_v3['xgb_v3'] missing — Train Model v3 must run first")

X_train_arr = X_v3_train.fillna(0).values
X_test_arr = X_v3_test.fillna(0).values
y_test_arr = np.asarray(y_v3_test).astype(int)

# Sample size for explanations (don't blow compute on 3.5k test rows)
SAMPLE_N = min(200, len(X_test_arr))
rng = np.random.default_rng(42)
sample_idx = rng.choice(len(X_test_arr), size=SAMPLE_N, replace=False)
X_explain = X_test_arr[sample_idx]
y_explain = y_test_arr[sample_idx]


# ═══ Path A: shap library ════════════════════════════════════════════════
if SHAP_OK:
    folds = ensemble_model.calibrated_classifiers_
    print(f"[SHAP v3] using TreeExplainer over {len(folds)} calibration folds")
    shap_per_fold = []
    for fi, fold in enumerate(folds):
        base = fold.estimator
        expl = shap.TreeExplainer(base)
        sv = expl.shap_values(X_explain)
        if isinstance(sv, list):
            sv = sv[1]
        shap_per_fold.append(sv)
        print(f"  fold {fi+1}/{len(folds)} done  shape={sv.shape}")

    shap_values_v3 = np.mean(shap_per_fold, axis=0)
    interpret_method = "shap_tree"


# ═══ Path B: pure-numpy sampling SHAP ═══════════════════════════════════
else:
    BG_SIZE = min(100, len(X_train_arr))
    N_PERM = 20  # Monte Carlo iterations per sample
    print(f"[SHAP v3] sampling SHAP — n_explain={SAMPLE_N}, "
          f"bg={BG_SIZE}, n_perm={N_PERM}, n_feat={X_explain.shape[1]}")

    # Pre-pick background distribution from train pool
    bg_idx = rng.choice(len(X_train_arr), size=BG_SIZE, replace=False)
    X_bg = X_train_arr[bg_idx]

    n_explain, n_feat = X_explain.shape

    def _proba(X):
        """Calibrated wrapper predict_proba on positive class."""
        return ensemble_model.predict_proba(X)[:, 1]

    shap_values_v3 = np.zeros((n_explain, n_feat))
    t0 = time.time()
    for shp_perm_idx in range(N_PERM):
        # one shared permutation per iteration (each explained sample
        # gets the same permutation but a different background sample)
        pi = rng.permutation(n_feat)
        # one background instance per explanation
        bg_per = X_bg[rng.integers(0, BG_SIZE, size=n_explain)]

        # start with the background. Then reveal features in order of pi.
        x_current = bg_per.copy()
        f_prev = _proba(x_current)

        for k in range(n_feat):
            i = pi[k]
            x_next = x_current.copy()
            x_next[:, i] = X_explain[:, i]  # reveal feature i
            f_next = _proba(x_next)
            shap_values_v3[:, i] += (f_next - f_prev)
            x_current = x_next
            f_prev = f_next

        if (shp_perm_idx + 1) % 5 == 0 or shp_perm_idx == 0:
            elapsed = time.time() - t0
            eta = elapsed / (shp_perm_idx + 1) * (N_PERM - shp_perm_idx - 1)
            print(f"  perm {shp_perm_idx+1:>2}/{N_PERM}  elapsed={elapsed:.1f}s  ETA={eta:.1f}s")

    shap_values_v3 /= N_PERM
    interpret_method = "sampling_pure_numpy"
    print(f"[SHAP v3] sampling done in {time.time()-t0:.1f}s")


# ═══ summary table ═══════════════════════════════════════════════════════
mean_abs = np.abs(shap_values_v3).mean(axis=0)
shap_summary_v3 = (
    pd.DataFrame({"feature": feature_cols_v3, "mean_abs_shap": mean_abs})
    .sort_values("mean_abs_shap", ascending=False)
    .reset_index(drop=True)
)

print()
print("=" * 70)
print(f"INTERPRETABILITY v3 — method={interpret_method}")
print("=" * 70)
denom = shap_summary_v3["mean_abs_shap"].max() or 1
for _, row in shap_summary_v3.head(20).iterrows():
    bar = "█" * int(row["mean_abs_shap"] / denom * 30)
    print(f"  {row['feature']:<35} {row['mean_abs_shap']:.4f}  {bar}")


# ═══ plots ═══════════════════════════════════════════════════════════════
shp_fig, shp_axes = plt.subplots(1, 2, figsize=(14, 8))

# [L] top-20 bar
top = shap_summary_v3.head(20).iloc[::-1]
shp_axes[0].barh(top["feature"], top["mean_abs_shap"], color="#ec4899")
shp_axes[0].set_xlabel("mean |SHAP value|")
shp_axes[0].set_title(f"Top-20 features driving v3 ensemble\n({interpret_method})")
shp_axes[0].tick_params(axis="y", labelsize=9)
shp_axes[0].grid(alpha=0.3, axis="x")

# [R] contrasting upgrader vs non-upgrader (works for both paths)
shp_ax = shp_axes[1]
pos_idx = np.where(y_explain == 1)[0]
neg_idx = np.where(y_explain == 0)[0]
if len(pos_idx) and len(neg_idx):
    p_i, n_i = int(pos_idx[0]), int(neg_idx[0])
    p_shap = shap_values_v3[p_i]
    n_shap = shap_values_v3[n_i]
    top10 = np.argsort(-np.abs(p_shap))[:10]
    ys = np.arange(10)
    shp_ax.barh(ys - 0.2, p_shap[top10], 0.4, color="#ec4899", label="example upgrader")
    shp_ax.barh(ys + 0.2, n_shap[top10], 0.4, color="#06b6d4", label="example non-upgrader")
    shp_ax.set_yticks(ys)
    shp_ax.set_yticklabels([feature_cols_v3[i] for i in top10], fontsize=9)
    shp_ax.axvline(0, color="#475569", linewidth=0.8)
    shp_ax.set_xlabel("SHAP value  (push toward upgrade →)")
    shp_ax.set_title("Two contrasting cases (top-10 by |SHAP|)")
    shp_ax.legend(fontsize=9)
    shp_ax.grid(alpha=0.3, axis="x")
    shp_ax.invert_yaxis()
else:
    shp_ax.text(0.5, 0.5, "(not enough positives in sample)", ha="center")

plt.suptitle(f"v3 ensemble interpretability  ({interpret_method})",
             fontsize=14, y=1.0)
plt.tight_layout()
plt.show()

print()
print(f"interpret_method      : {interpret_method}")
print(f"shap_summary_v3       : top-20 features dataframe")
print(f"shap_values_v3        : np.ndarray {shap_values_v3.shape}")
