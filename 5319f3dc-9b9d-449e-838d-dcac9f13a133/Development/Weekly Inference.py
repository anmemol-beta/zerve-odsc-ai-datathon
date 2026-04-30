"""Weekly Inference — score each week's incoming users with the loaded champion.

This is the user-facing read of the trained models. The training tier
(Funnel v4 → Build Features v3 → Train Model v3 → Champion Selector →
Persist Models) runs on a weekly cron. This block runs anytime new
weekly slices land, scores them with the persisted champion, and
produces a per-week prediction table that downstream visualizations and
the live web demo can consume.

Per-(week, segment) is the unit because the K2 strategist works at the
v4-funnel-segment level — a marketing lead wants to know
"this week's at_risk_engaged predicted upgrade rate" not just an overall
mean.

Inputs:
    weekly_slices, weekly_summary  (Weekly Data Slices)
    loaded_models, loaded_meta, inference_ready  (Load Models)
    user_features_v4               (Funnel v4)  — for v4 stage join
    feature_cols_v3                (Build Features v3) — to align cols

Outputs:
    weekly_predictions      pd.DataFrame  — week × user-level scores
    weekly_pred_summary     pd.DataFrame  — week-level aggregate
    weekly_pred_by_stage    pd.DataFrame  — week × v4_stage aggregate
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

if not inference_ready:
    raise RuntimeError(
        "inference_ready=False from Load Models — cannot score weekly slices. "
        "Run Persist Models on the training tier or commit models/v3/ to repo."
    )

champion_name = loaded_meta.get("current_champion") or "ensemble_v3"
print(f"[weekly-infer] champion = {champion_name}")

# Resolve champion model object out of the loaded bundle
def _resolve_champion(name: str):
    if name == "ensemble_v3":
        # ensemble = soft-vote over the 3 base models in models_v3
        return loaded_models.get("models_v3")
    if name in {"xgb_v3", "rf_v3", "hgb_v3"}:
        bundle = loaded_models.get("models_v3", {})
        return bundle.get(name) if isinstance(bundle, dict) else None
    if name == "gbm_v3":
        return loaded_models.get("gbm_v3")
    if name == "mlp_v3":
        return loaded_models.get("mlp_v3")
    return None


champion_obj = _resolve_champion(champion_name)
if champion_obj is None:
    print(f"[weekly-infer] champion {champion_name!r} not loaded — falling back to gbm_v3")
    champion_name = "gbm_v3"
    champion_obj = loaded_models.get("gbm_v3")
if champion_obj is None:
    raise RuntimeError(f"no usable model loaded; bundle keys = {list(loaded_models.keys())}")


def _predict(model, X: np.ndarray) -> np.ndarray:
    """Unified predict_proba wrapper. Handles ensemble dict (mean of base
    proba) AND single calibrated wrappers."""
    if isinstance(model, dict):
        # ensemble = mean of base model probabilities
        probas = []
        for name, m in model.items():
            try:
                p = m.predict_proba(X)[:, 1]
                probas.append(p)
            except Exception as e:
                print(f"  warn: {name} failed during ensemble predict: {e}")
        if not probas:
            raise RuntimeError("all base models in ensemble failed to predict")
        return np.mean(probas, axis=0)
    return model.predict_proba(X)[:, 1]


# ─── 1. score each weekly slice ──────────────────────────────────────────
# The weekly slices have a SMALLER feature set (~10 cols) than v3 (~169).
# We need to project each weekly slice onto the v3 feature space, fill
# missing v3 features with 0, and then score. This is a coarse approximation
# (the model was trained on cumulative-window features, not weekly snapshots)
# but tracking RELATIVE prediction trends across weeks is still meaningful.

WEEKLY_TO_V3_MAP = {
    "n_events":           "n_events_7d",
    "n_ai_events":        "n_ai_7d",
    "n_credit_events":    "n_credits_used_7d",
    "n_run_events":       "n_run_block_7d",
    "n_block_events":     "n_block_create_7d",
    "n_exception_events": "n_exception_7d",
    "n_deploy_events":    None,
    "distinct_hours":     "n_distinct_hours_7d",
    "session_min_proxy":  "session_minutes_7d",
}


def _project_to_v3(snap: pd.DataFrame) -> pd.DataFrame:
    """Build a (n_users, n_v3_features) DataFrame from a weekly snapshot."""
    out = pd.DataFrame(0.0, index=snap.index, columns=feature_cols_v3)
    for w_col, v3_col in WEEKLY_TO_V3_MAP.items():
        if v3_col is None or v3_col not in out.columns or w_col not in snap.columns:
            continue
        out[v3_col] = snap[w_col].astype(float).values
        # also populate the 24h cousin if it exists, with a heuristic discount
        v3_24h = v3_col.replace("_7d", "_24h")
        if v3_24h in out.columns:
            out[v3_24h] = snap[w_col].astype(float).values / 7.0
    return out


print(f"[weekly-infer] scoring {len(weekly_slices)} weeks "
      f"with champion={champion_name}")
weekly_pred_rows = []
for w_id, snap in weekly_slices.items():
    if len(snap) == 0:
        continue
    Xw = _project_to_v3(snap)
    try:
        prob = _predict(champion_obj, Xw.values.astype(np.float32))
    except Exception as e:
        print(f"  warn: predict failed on {w_id}: {e}")
        continue
    df = pd.DataFrame({
        "week": w_id,
        "person_id": snap.index,
        "predicted_upgrade_prob": prob,
        "had_actual_upgrade": snap["had_upgrade"].values,
    })
    weekly_pred_rows.append(df)

weekly_predictions = pd.concat(weekly_pred_rows, axis=0, ignore_index=True)
print(f"[weekly-infer] scored {len(weekly_predictions):,} (week, user) rows")


# ─── 2. weekly aggregate ────────────────────────────────────────────────
weekly_pred_summary = (
    weekly_predictions.groupby("week")
    .agg(
        n_users=("person_id", "nunique"),
        mean_predicted=("predicted_upgrade_prob", "mean"),
        median_predicted=("predicted_upgrade_prob", "median"),
        p90_predicted=("predicted_upgrade_prob", lambda s: float(s.quantile(0.9))),
        share_high_risk=("predicted_upgrade_prob", lambda s: float((s > 0.5).mean())),
        actual_upgrade_rate=("had_actual_upgrade", "mean"),
    )
    .reset_index()
    .sort_values("week")
)


# ─── 3. per-(week, v4 stage) breakdown ──────────────────────────────────
stage_lookup = user_features_v4[["final_stage"]].rename_axis("person_id")
joined = weekly_predictions.merge(
    stage_lookup, left_on="person_id", right_index=True, how="left"
)
joined["final_stage"] = joined["final_stage"].fillna("0.NoEvent")
weekly_pred_by_stage = (
    joined.groupby(["week", "final_stage"])
    .agg(
        n_users=("person_id", "count"),
        mean_predicted=("predicted_upgrade_prob", "mean"),
        share_high_risk=("predicted_upgrade_prob", lambda s: float((s > 0.5).mean())),
    )
    .reset_index()
    .sort_values(["week", "final_stage"])
)

print()
print("=" * 90)
print("WEEKLY PREDICTION SUMMARY")
print("=" * 90)
print(weekly_pred_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


# ─── 4. plots ───────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 1, figsize=(14, 9))

# [Top] mean predicted vs actual upgrade rate over time
ax = axes[0]
xs = range(len(weekly_pred_summary))
ax.plot(xs, weekly_pred_summary["mean_predicted"], "o-",
        color="#ec4899", label="mean predicted prob", linewidth=2)
ax.plot(xs, weekly_pred_summary["actual_upgrade_rate"], "s-",
        color="#10b981", label="actual upgrade rate", linewidth=2)
ax2 = ax.twinx()
ax2.bar(xs, weekly_pred_summary["n_users"], alpha=0.15, color="#06b6d4",
        label="n active users (right axis)")
ax2.set_ylabel("n users", color="#06b6d4")
ax.set_xticks(xs)
ax.set_xticklabels(weekly_pred_summary["week"], rotation=60, ha="right", fontsize=7)
ax.set_ylabel("upgrade probability")
ax.set_title(f"Weekly inference — champion={champion_name}\n"
             "(predicted vs actual upgrade rate per week)")
ax.legend(loc="upper left", fontsize=8)
ax.grid(alpha=0.3)

# [Bottom] heatmap mean predicted by (week × v4 stage)
ax = axes[1]
pivot = weekly_pred_by_stage.pivot_table(
    index="final_stage", columns="week", values="mean_predicted"
)
# Order rows by funnel rank
STAGE_ORDER = [
    "0.NoEvent", "1.New", "2.Exploring", "3.Created", "4.UsedAI",
    "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded",
    "9.AtRisk@UsedAI", "9.AtRisk@WroteCode", "9.AtRisk@Integrated",
    "9.AtRisk@Engaged", "9.AtRisk@Upgraded", "9.Churned@Upgraded",
]
pivot = pivot.reindex([s for s in STAGE_ORDER if s in pivot.index])
im = ax.imshow(pivot.values, aspect="auto", cmap="RdPu",
               vmin=0, vmax=max(pivot.values.max() if pivot.size else 0.5, 0.5))
ax.set_xticks(range(len(pivot.columns)))
ax.set_xticklabels(pivot.columns, rotation=60, ha="right", fontsize=7)
ax.set_yticks(range(len(pivot.index)))
ax.set_yticklabels(pivot.index, fontsize=9)
ax.set_title("mean predicted upgrade prob — (v4 stage × week)")
plt.colorbar(im, ax=ax, label="predicted prob")

plt.suptitle("Weekly inference dashboard", fontsize=13, y=1.0)
plt.tight_layout()
plt.show()
