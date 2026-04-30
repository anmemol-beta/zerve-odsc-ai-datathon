"""Data Drift Monitor — does this week's data look like the baseline?

Production ML systems degrade silently when input distribution shifts.
This block surfaces the shift BEFORE any label feedback (label window is
60 days, so we'd otherwise be flying blind for 2 months). It compares
each week's user-feature distribution to a baseline (first 4 weeks
pooled) using two complementary tests:

  PSI  (Population Stability Index)  — banking-industry standard.
        Bin-based KL-style divergence. Threshold rules of thumb:
            < 0.1  : no drift
            0.1-0.25 : moderate drift, monitor
            > 0.25 : material drift, retrain trigger

  KS test (Kolmogorov-Smirnov)  — distribution-free goodness of fit.
        p-value < 0.05 = drifted.

We compute both; PSI is the headline metric (more interpretable),
KS is the second opinion. We also track a global "drift index" per
week = mean PSI across all monitored features.

Inputs:
    weekly_slices, weekly_summary, weekly_baseline_id
    (Weekly Data Slices block)

Outputs:
    drift_per_week_per_feature   pd.DataFrame  long table
    weekly_drift_index           pd.DataFrame  one row per week
    drift_alerts                 list[dict]    actionable callouts
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

# Features to monitor — same as Weekly Data Slices output
MONITORED_FEATURES = [
    "n_events", "n_ai_events", "n_credit_events", "n_run_events",
    "n_block_events", "n_exception_events", "n_deploy_events",
    "distinct_hours", "session_min_proxy",
]

PSI_THRESHOLD_MODERATE = 0.10
PSI_THRESHOLD_MATERIAL = 0.25
KS_PVAL_THRESHOLD = 0.05


# ─── 1. build baseline by pooling first 4 weeks ──────────────────────────
all_weeks = sorted(weekly_slices.keys())
baseline_weeks = all_weeks[:4]
baseline_df = pd.concat(
    [weekly_slices[w][MONITORED_FEATURES] for w in baseline_weeks],
    axis=0, ignore_index=True,
)
print(f"[drift] baseline pooled from {len(baseline_weeks)} weeks → "
      f"{len(baseline_df):,} user-rows")


# ─── 2. PSI helper ───────────────────────────────────────────────────────
def _psi(a: np.ndarray, b: np.ndarray, n_bins: int = 10) -> float:
    """Bin-based PSI. Bins are quantile-based on `a`. Small-count
    smoothing (Laplace 1e-4) prevents log(0)."""
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 50 or len(b) < 30:
        return float("nan")  # insufficient data
    if a.std() == 0 and b.std() == 0:
        return 0.0
    # quantile bins from baseline; clip current data to those edges
    quantiles = np.linspace(0, 1, n_bins + 1)
    edges = np.unique(np.quantile(a, quantiles))
    if len(edges) < 3:
        # constant or near-constant → fall back to two bins by mean
        edges = np.array([-np.inf, float(np.mean(a)), np.inf])
    edges = np.concatenate([[-np.inf], edges[1:-1], [np.inf]])

    a_hist, _ = np.histogram(a, bins=edges)
    b_hist, _ = np.histogram(b, bins=edges)
    a_pct = (a_hist + 1e-4) / (a_hist.sum() + 1e-4 * len(a_hist))
    b_pct = (b_hist + 1e-4) / (b_hist.sum() + 1e-4 * len(b_hist))
    return float(np.sum((b_pct - a_pct) * np.log(b_pct / a_pct)))


def _ks_pvalue(a: np.ndarray, b: np.ndarray) -> float:
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 30 or len(b) < 30:
        return float("nan")
    try:
        return float(stats.ks_2samp(a, b).pvalue)
    except Exception:
        return float("nan")


# ─── 3. compute drift per (week, feature) ────────────────────────────────
rows = []
for w_id in all_weeks:
    snap = weekly_slices[w_id]
    for feat in MONITORED_FEATURES:
        if feat not in snap.columns:
            continue
        baseline_vals = baseline_df[feat].values.astype(float)
        current_vals = snap[feat].values.astype(float)
        psi = _psi(baseline_vals, current_vals)
        ks_p = _ks_pvalue(baseline_vals, current_vals)
        rows.append({
            "week": w_id,
            "feature": feat,
            "n_current": len(current_vals),
            "psi": psi,
            "ks_pvalue": ks_p,
            "drifted_psi": (not np.isnan(psi)) and psi > PSI_THRESHOLD_MODERATE,
            "drifted_material": (not np.isnan(psi)) and psi > PSI_THRESHOLD_MATERIAL,
            "drifted_ks": (not np.isnan(ks_p)) and ks_p < KS_PVAL_THRESHOLD,
        })

drift_per_week_per_feature = pd.DataFrame(rows)
print(f"[drift] computed {len(drift_per_week_per_feature)} (week, feature) "
      f"drift measurements")


# ─── 4. weekly drift index ───────────────────────────────────────────────
weekly_drift_index = (
    drift_per_week_per_feature.groupby("week")
    .agg(
        mean_psi=("psi", "mean"),
        max_psi=("psi", "max"),
        n_drifted_features=("drifted_psi", "sum"),
        n_material_drift=("drifted_material", "sum"),
        n_ks_drift=("drifted_ks", "sum"),
    )
    .reset_index()
    .sort_values("week")
    .reset_index(drop=True)
)
weekly_drift_index["status"] = pd.cut(
    weekly_drift_index["max_psi"],
    bins=[-np.inf, PSI_THRESHOLD_MODERATE, PSI_THRESHOLD_MATERIAL, np.inf],
    labels=["green", "yellow", "red"],
)


# ─── 5. alerts ───────────────────────────────────────────────────────────
drift_alerts = []
for _, r in weekly_drift_index.iterrows():
    if r["status"] == "red":
        drift_alerts.append({
            "week": r["week"],
            "kind": "material_drift",
            "detail": f"max PSI {r['max_psi']:.3f} (>{PSI_THRESHOLD_MATERIAL}), "
                      f"{r['n_material_drift']} features past material threshold. "
                      "Recommend retrain.",
        })
    elif r["status"] == "yellow":
        drift_alerts.append({
            "week": r["week"],
            "kind": "moderate_drift",
            "detail": f"max PSI {r['max_psi']:.3f}, "
                      f"{r['n_drifted_features']} features drifted. Monitor.",
        })

# also: features that drifted in 3+ consecutive weeks
fp = drift_per_week_per_feature.copy()
fp = fp.sort_values(["feature", "week"])
fp["streak"] = (
    fp.groupby("feature")["drifted_psi"]
    .transform(lambda s: s.groupby((~s).cumsum()).cumsum())
)
chronic = fp[fp["streak"] >= 3]
for feat, g in chronic.groupby("feature"):
    drift_alerts.append({
        "week": str(g["week"].iloc[-1]),
        "kind": "chronic_drift",
        "detail": f"feature `{feat}` has drifted PSI > {PSI_THRESHOLD_MODERATE} "
                  f"for {int(g['streak'].max())} consecutive weeks.",
    })

print()
print("=" * 90)
print("DATA DRIFT MONITOR — weekly PSI vs baseline (first 4 weeks pooled)")
print("=" * 90)
print(weekly_drift_index.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print()
if drift_alerts:
    print(f"DRIFT ALERTS ({len(drift_alerts)}):")
    for a in drift_alerts[:15]:
        print(f"  [{a['kind']:<14}] week={a['week']:<14} → {a['detail']}")
    if len(drift_alerts) > 15:
        print(f"  ... and {len(drift_alerts) - 15} more")
else:
    print("No drift alerts — data is stable across the rolling window.")


# ─── 6. plots ────────────────────────────────────────────────────────────
ddm_fig, ddm_axes = plt.subplots(2, 1, figsize=(14, 10))

# [Top] heatmap (feature × week) of PSI
ax = ddm_axes[0]
pivot = drift_per_week_per_feature.pivot_table(
    index="feature", columns="week", values="psi"
).reindex(index=MONITORED_FEATURES, columns=all_weeks)
im = ax.imshow(pivot.values, aspect="auto", cmap="RdPu",
               vmin=0, vmax=max(0.5, np.nanmax(pivot.values) if pivot.notna().any().any() else 0.5))
ax.set_xticks(range(len(all_weeks)))
ax.set_xticklabels(all_weeks, rotation=60, ha="right", fontsize=7)
ax.set_yticks(range(len(MONITORED_FEATURES)))
ax.set_yticklabels(MONITORED_FEATURES, fontsize=9)
ax.set_title("PSI per (feature × week) vs baseline\n"
             "(red = drifted > 0.25, pink = moderate 0.10-0.25, faded = stable)")
plt.colorbar(im, ax=ax, label="PSI")
# annotate cells with PSI value if drifted
for i, feat in enumerate(MONITORED_FEATURES):
    for j, w in enumerate(all_weeks):
        v = pivot.values[i, j] if i < pivot.shape[0] and j < pivot.shape[1] else float("nan")
        if not np.isnan(v) and v > PSI_THRESHOLD_MODERATE:
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    fontsize=7, color="white" if v > 0.3 else "black")

# [Bottom] line plot — overall drift over time
ax = ddm_axes[1]
xs = range(len(weekly_drift_index))
ax.plot(xs, weekly_drift_index["mean_psi"], "o-", color="#06b6d4", label="mean PSI")
ax.plot(xs, weekly_drift_index["max_psi"], "s-", color="#ec4899", label="max PSI")
ax.axhline(PSI_THRESHOLD_MODERATE, linestyle="--", color="#f59e0b", linewidth=1, label="moderate (0.10)")
ax.axhline(PSI_THRESHOLD_MATERIAL, linestyle="--", color="#ef4444", linewidth=1, label="material (0.25)")
ax.set_xticks(xs)
ax.set_xticklabels(weekly_drift_index["week"], rotation=60, ha="right", fontsize=7)
ax.set_ylabel("PSI")
ax.set_title("Weekly drift index over time")
ax.legend(loc="upper left", fontsize=8)
ax.grid(alpha=0.3)

plt.suptitle("Data Drift Monitor — input distribution vs baseline",
             fontsize=13, y=1.0)
plt.tight_layout()
plt.show()
