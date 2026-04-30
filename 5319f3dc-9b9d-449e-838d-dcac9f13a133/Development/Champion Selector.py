"""Champion Selector — pick the production model from rolling evidence.

Naïvely picking the model with the best on the latest cohort is fragile
(one good month doesn't make a champion). Naïvely picking the most
stable is also fragile (a stable mediocre model loses to a slightly
volatile great one). This block picks the production model with a
defensible rule:

    weighted_score(model) =
        0.5 × pr_auc_on_latest_cohort
      + 0.3 × pr_auc_mean_across_cohorts
      + 0.2 × stability_score

Tie-breaks favor recency. The block also reports per-cohort winners and
how often each model wins, so a human can sanity-check the pick.

Inputs:
    rolling_metrics_v3   (Train Across Time)
    drift_summary        (Performance Drift)

Outputs:
    champion_per_cohort      pd.DataFrame
    win_counts               pd.Series
    current_champion         str
    champion_summary         dict
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Drop the synthetic "test_full" cohort
df = rolling_metrics_v3[rolling_metrics_v3["cohort"] != "test_full"].copy()
ordered = sorted(df["month"].dropna().unique())
df["cohort_idx"] = df["month"].map({m: i for i, m in enumerate(ordered)})
df = df.dropna(subset=["cohort_idx", "pr_auc"]).copy()

# ─── 1. winner per cohort ─────────────────────────────────────────────────
champion_per_cohort = (
    df.sort_values("pr_auc", ascending=False)
    .drop_duplicates("cohort")
    .sort_values("cohort_idx")
    [["cohort", "cohort_label", "month", "model", "pr_auc",
      "n_test", "n_pos"]]
    .reset_index(drop=True)
)

# ─── 2. win counts ────────────────────────────────────────────────────────
win_counts = champion_per_cohort["model"].value_counts()

# ─── 3. weighted score (latest 50% + mean 30% + stability 20%) ────────────
latest_idx = int(df["cohort_idx"].max())
latest = df[df["cohort_idx"] == latest_idx]
latest_pr = latest.set_index("model")["pr_auc"]
mean_pr = df.groupby("model")["pr_auc"].mean()
# stability from drift_summary
stab = drift_summary.set_index("model")["stability_score"]
all_models = mean_pr.index.union(latest_pr.index).union(stab.index)


def _norm(s: pd.Series) -> pd.Series:
    """Min-max normalize, NaN-safe. If max==min, all 0.5."""
    s = s.reindex(all_models)
    valid = s.dropna()
    if len(valid) == 0:
        return pd.Series(0.5, index=all_models)
    rng = valid.max() - valid.min()
    if rng == 0:
        return pd.Series(0.5, index=all_models)
    return ((s - valid.min()) / rng).clip(0, 1)


norm_latest = _norm(latest_pr)
norm_mean = _norm(mean_pr)
norm_stab = _norm(stab)

weighted_score = (
    0.5 * norm_latest.fillna(0)
    + 0.3 * norm_mean.fillna(0)
    + 0.2 * norm_stab.fillna(0)
)
weighted_score = weighted_score.sort_values(ascending=False)

current_champion = weighted_score.index[0]
champion_summary = {
    "current_champion": current_champion,
    "weighted_score": float(weighted_score.iloc[0]),
    "latest_cohort": ordered[latest_idx] if ordered else None,
    "latest_pr_auc": float(latest_pr.get(current_champion, float("nan"))),
    "mean_pr_auc": float(mean_pr.get(current_champion, float("nan"))),
    "stability": float(stab.get(current_champion, float("nan"))),
    "wins_count": int(win_counts.get(current_champion, 0)),
    "wins_total_cohorts": int(len(champion_per_cohort)),
    "rule": "0.5 latest + 0.3 cross-cohort mean + 0.2 stability (min-max scaled)",
}

# ─── 4. report ────────────────────────────────────────────────────────────
print("=" * 90)
print("CHAMPION SELECTOR — production model recommendation")
print("=" * 90)
print()
print("Per-cohort winners:")
for _, r in champion_per_cohort.iterrows():
    print(f"  {r['cohort_label']:<18} {r['model']:<14} "
          f"PR-AUC {r['pr_auc']:.4f}  ({r['n_pos']} pos / {r['n_test']:,} users)")

print()
print("Win counts (across rolling cohorts):")
for m, n in win_counts.items():
    pct = n / len(champion_per_cohort) * 100
    bar = "█" * int(n)
    print(f"  {m:<14} {n} wins  ({pct:>4.0f}%)  {bar}")

print()
print("Weighted score (recency + mean + stability):")
for m, s in weighted_score.items():
    print(f"  {m:<14} {s:.4f}")

print()
print("=" * 90)
print(f"PRODUCTION CHAMPION → {current_champion}")
print("=" * 90)
print(f"  weighted score    : {champion_summary['weighted_score']:.4f}")
print(f"  latest cohort     : {champion_summary['latest_cohort']}  "
      f"(PR-AUC {champion_summary['latest_pr_auc']:.4f})")
print(f"  mean PR-AUC       : {champion_summary['mean_pr_auc']:.4f}")
print(f"  stability score   : {champion_summary['stability']:.4f}")
print(f"  cohort wins       : {champion_summary['wins_count']} / "
      f"{champion_summary['wins_total_cohorts']}")
print(f"  selection rule    : {champion_summary['rule']}")


# ─── 5. plot ──────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

COLORS = {
    "ensemble_v3": "#10b981", "xgb_v3": "#ec4899", "rf_v3": "#06b6d4",
    "hgb_v3": "#a855f7", "mlp_v3": "#f59e0b", "gbm_v3": "#f43f5e",
}

# [L] Champion per cohort
ax = axes[0]
labels = champion_per_cohort["cohort_label"].tolist()
prs = champion_per_cohort["pr_auc"].tolist()
colors = [COLORS.get(m, "#64748b") for m in champion_per_cohort["model"]]
bars = ax.bar(labels, prs, color=colors)
for bar, m in zip(bars, champion_per_cohort["model"]):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
            m, ha="center", va="bottom", fontsize=8, color="#1e293b",
            rotation=15)
ax.set_ylabel("winner PR-AUC")
ax.set_title("Per-cohort champion (the model that won that month)")
ax.tick_params(axis="x", rotation=15, labelsize=9)
ax.grid(alpha=0.3, axis="y")

# [R] Weighted score ranking
ax = axes[1]
ws = weighted_score.iloc[::-1]
ax.barh(ws.index, ws.values,
        color=[COLORS.get(m, "#64748b") for m in ws.index])
ax.set_xlabel("weighted score (0.5 latest + 0.3 mean + 0.2 stability)")
ax.set_title(f"Production champion → {current_champion}")
ax.grid(alpha=0.3, axis="x")

plt.suptitle("AutoML champion selection", fontsize=13, y=1.02)
plt.tight_layout()
plt.show()
