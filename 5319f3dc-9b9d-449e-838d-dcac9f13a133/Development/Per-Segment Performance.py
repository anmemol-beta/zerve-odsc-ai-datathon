"""Per-Segment Performance — model × funnel cross-section.

The single hardest question for any upgrade-prediction model:
*"Does the model add lift in every segment, or only in segments where
the answer is already obvious?"*

Joins each test user's v3 prediction with their v4 funnel stage, then
computes per-segment PR-AUC, top-5% precision, and lift over base rate.
A model that's only good on a few easy segments is useless for the
strategist downstream — every K2-generated action is segment-targeted.

Inputs (from canvas namespace):
    user_features_v4     (Funnel v4)        — final_stage column
    X_v3_test            (Build Features v3)
    y_v3_test            (Build Features v3)
    ensemble_proba_v3    (Train Model v3)

Outputs:
    segment_performance_v3   pd.DataFrame  — one row per stage
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score

# ─── 1. assemble per-test-user dataframe ──────────────────────────────────
test_df = pd.DataFrame({
    "person_id": X_v3_test.index,
    "y": np.asarray(y_v3_test).astype(int),
    "score": np.asarray(ensemble_proba_v3),
}).set_index("person_id")

stages = user_features_v4[["final_stage"]]
joined = test_df.join(stages, how="left")
joined["final_stage"] = joined["final_stage"].fillna("0.NoEvent")

print(f"[per-seg] joined: {len(joined):,} test users with stage labels")
print(f"[per-seg] base test positive rate: {joined['y'].mean()*100:.2f}%")


# ─── 2. per-stage metrics ─────────────────────────────────────────────────
def _seg_metrics(g: pd.DataFrame) -> pd.Series:
    n = len(g)
    pos = int(g["y"].sum())
    if pos == 0 or n - pos == 0:
        return pd.Series({
            "n_users": n, "n_pos": pos,
            "pos_rate": pos / max(n, 1),
            "pr_auc": np.nan,
            "score_median": float(g["score"].median()),
            "score_p90": float(g["score"].quantile(0.9)),
            "top5_precision": np.nan,
            "lift_over_base": np.nan,
        })
    pr = average_precision_score(g["y"], g["score"])
    # top-5% precision within this segment
    k = max(int(np.ceil(n * 0.05)), 1)
    top_k_idx = g["score"].nlargest(k).index
    top5_prec = g.loc[top_k_idx, "y"].mean()
    base = g["y"].mean()
    lift = top5_prec / base if base > 0 else np.nan
    return pd.Series({
        "n_users": n,
        "n_pos": pos,
        "pos_rate": base,
        "pr_auc": float(pr),
        "score_median": float(g["score"].median()),
        "score_p90": float(g["score"].quantile(0.9)),
        "top5_precision": float(top5_prec),
        "lift_over_base": float(lift),
    })


segment_performance_v3 = (
    joined.groupby("final_stage", sort=True)
          .apply(_seg_metrics)
          .reset_index()
          .sort_values("n_users", ascending=False)
          .reset_index(drop=True)
)

# Order stages by funnel rank for the chart
STAGE_ORDER = [
    "0.NoEvent", "1.New", "2.Exploring", "3.Created", "4.UsedAI",
    "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded",
    "9.AtRisk@UsedAI", "9.AtRisk@WroteCode", "9.AtRisk@Integrated",
    "9.AtRisk@Engaged", "9.AtRisk@Upgraded", "9.Churned@Upgraded",
]
order_map = {s: i for i, s in enumerate(STAGE_ORDER)}
segment_performance_v3["_order"] = segment_performance_v3["final_stage"].map(
    lambda s: order_map.get(s, 99)
)
segment_performance_v3 = (
    segment_performance_v3.sort_values("_order")
    .drop(columns=["_order"]).reset_index(drop=True)
)

print()
print("=" * 100)
print("PER-SEGMENT MODEL PERFORMANCE (v3 ensemble on TEST cohort)")
print("=" * 100)
print(segment_performance_v3.to_string(
    index=False, float_format=lambda x: "—" if pd.isna(x) else f"{x:.4f}"
))

# ─── 3. plots ─────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 1, figsize=(13, 8))

stages = segment_performance_v3["final_stage"].tolist()

# [Top] Segment size + pos count
ax = axes[0]
ax.bar(stages, segment_performance_v3["n_users"], color="#06b6d4",
       label="users in segment")
ax2 = ax.twinx()
ax2.plot(stages, segment_performance_v3["n_pos"], color="#ec4899",
         marker="o", linewidth=2, label="positives")
ax.set_ylabel("users", color="#06b6d4")
ax2.set_ylabel("positives (upgrades)", color="#ec4899")
ax.set_title("Segment size and positive count")
ax.set_xticks(range(len(stages)))
ax.set_xticklabels(stages, rotation=30, ha="right", fontsize=8)
ax.grid(alpha=0.3, axis="y")

# [Bottom] PR-AUC + lift
ax = axes[1]
pr_vals = segment_performance_v3["pr_auc"].fillna(0)
lift_vals = segment_performance_v3["lift_over_base"].fillna(0)
xs = np.arange(len(stages))
ax.bar(xs - 0.2, pr_vals, 0.4, color="#a855f7", label="PR-AUC")
ax2 = ax.twinx()
ax2.bar(xs + 0.2, lift_vals, 0.4, color="#10b981", label="top-5% lift", alpha=0.85)
ax.set_ylabel("PR-AUC", color="#a855f7")
ax2.set_ylabel("top-5% lift over segment base rate", color="#10b981")
ax.set_title("Where does the v3 model add lift? "
             "(missing bars = no positives in test segment)")
ax.set_xticks(xs)
ax.set_xticklabels(stages, rotation=30, ha="right", fontsize=8)
ax.grid(alpha=0.3, axis="y")

plt.tight_layout()
plt.show()
