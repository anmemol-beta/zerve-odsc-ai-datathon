"""Performance Drift — does any candidate hold up over time?

Reads `rolling_metrics_v3` and asks two production-relevant questions:

  1. STABILITY — for each model, how much does its PR-AUC swing across
     monthly cohorts? Tight band = production-safe. Wide band = retrain
     monthly.

  2. DRIFT — is the trend going up, down, or flat over the rolling
     window? Falling = the model is staling; rising = recent users
     resemble training data more.

Outputs:
    drift_summary    pd.DataFrame  — per-model stability + slope + rank
    drift_alerts     list[dict]    — actionable callouts
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Filter out the "test_full" pseudo-cohort — it covers all months and
# would smooth the drift signal we want to see.
df = rolling_metrics_v3[rolling_metrics_v3["cohort"] != "test_full"].copy()

# Order cohorts chronologically by month string (YYYY-MM sorts naturally)
ordered = sorted(df["month"].dropna().unique())
df["cohort_idx"] = df["month"].map({m: i for i, m in enumerate(ordered)})
df = df.dropna(subset=["cohort_idx"]).sort_values(["model", "cohort_idx"])


# ─── 1. per-model stability ───────────────────────────────────────────────
def _summarize(g):
    pr = g["pr_auc"].dropna().values
    if len(pr) < 2:
        return pd.Series({
            "n_cohorts": len(pr),
            "pr_mean": float(np.nanmean(pr)) if len(pr) else float("nan"),
            "pr_std": float("nan"),
            "pr_min": float(np.nanmin(pr)) if len(pr) else float("nan"),
            "pr_max": float(np.nanmax(pr)) if len(pr) else float("nan"),
            "pr_slope": float("nan"),
            "stability_score": float("nan"),
        })
    pr_mean = float(np.mean(pr))
    pr_std = float(np.std(pr))
    pr_min = float(np.min(pr))
    pr_max = float(np.max(pr))
    # OLS slope of PR-AUC vs cohort index
    xs = np.arange(len(pr))
    slope = float(np.polyfit(xs, pr, 1)[0])
    # Stability score — higher is better. Coefficient of variation inverted.
    cv = pr_std / pr_mean if pr_mean > 0 else float("inf")
    stability = 1 / (1 + cv)
    return pd.Series({
        "n_cohorts": len(pr),
        "pr_mean": pr_mean, "pr_std": pr_std,
        "pr_min": pr_min, "pr_max": pr_max,
        "pr_slope": slope, "stability_score": stability,
    })


drift_summary = (
    df.groupby("model").apply(_summarize)
    .sort_values("pr_mean", ascending=False)
    .reset_index()
)

# ─── 2. alerts ────────────────────────────────────────────────────────────
drift_alerts: list[dict] = []
for _, r in drift_summary.iterrows():
    if pd.notna(r["pr_slope"]) and r["pr_slope"] < -0.005:
        drift_alerts.append({
            "model": r["model"],
            "kind": "negative_drift",
            "detail": f"PR-AUC slope {r['pr_slope']:+.4f} per cohort step "
                      "(falling). Consider retrain.",
        })
    if pd.notna(r["pr_std"]) and r["pr_std"] > 0.05:
        drift_alerts.append({
            "model": r["model"],
            "kind": "high_variance",
            "detail": f"PR-AUC std {r['pr_std']:.4f} across cohorts — "
                      "performance is cohort-dependent.",
        })
    if pd.notna(r["pr_max"]) and pd.notna(r["pr_min"]) \
            and r["pr_max"] - r["pr_min"] > 0.1:
        drift_alerts.append({
            "model": r["model"],
            "kind": "wide_range",
            "detail": f"PR-AUC range [{r['pr_min']:.3f}, {r['pr_max']:.3f}] "
                      f"= {r['pr_max'] - r['pr_min']:.3f} swing.",
        })

print("=" * 90)
print("PERFORMANCE DRIFT — model stability across rolling cohorts")
print("=" * 90)
print(drift_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

print()
if drift_alerts:
    print(f"DRIFT ALERTS ({len(drift_alerts)}):")
    for a in drift_alerts:
        print(f"  [{a['kind']:<14}] {a['model']:<14} → {a['detail']}")
else:
    print("No drift alerts — every candidate is stable across the rolling window.")


# ─── 3. plot ──────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# [L] PR-AUC line per model
ax = axes[0]
COLORS = {
    "ensemble_v3": "#10b981",
    "xgb_v3": "#ec4899",
    "rf_v3": "#06b6d4",
    "hgb_v3": "#a855f7",
    "mlp_v3": "#f59e0b",
    "catboost_v3": "#f43f5e",
}
for model, g in df.groupby("model"):
    ax.plot(g["cohort_idx"], g["pr_auc"],
            "o-", color=COLORS.get(model, "#64748b"),
            label=model,
            linewidth=2 if model == "ensemble_v3" else 1)
labels = [df[df["cohort_idx"] == i]["cohort_label"].iloc[0]
          for i in sorted(df["cohort_idx"].unique())]
ax.set_xticks(range(len(labels)))
ax.set_xticklabels(labels, rotation=15, ha="right")
ax.set_ylabel("PR-AUC")
ax.set_title("PR-AUC over rolling cohorts (per model)")
ax.legend(loc="best", fontsize=8)
ax.grid(alpha=0.3)

# [R] Stability score bars
ax = axes[1]
stab = drift_summary.dropna(subset=["stability_score"]).sort_values("stability_score")
ax.barh(stab["model"], stab["stability_score"],
        color=[COLORS.get(m, "#64748b") for m in stab["model"]])
ax.set_xlabel("stability score (1 / (1 + CV))  — higher ↑ more stable")
ax.set_title("Cross-cohort stability ranking")
ax.grid(alpha=0.3, axis="x")

plt.suptitle("AutoML rolling-cohort drift dashboard",
             fontsize=13, y=1.02)
plt.tight_layout()
plt.show()
