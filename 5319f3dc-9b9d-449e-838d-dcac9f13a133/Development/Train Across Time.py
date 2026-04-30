"""Train Across Time — AutoML core.

Runs every trained candidate model against every rolling test cohort.
The output is the metric grid that downstream Performance Drift and
Champion Selector use to detect drift and pick the production model.

We do *not* retrain per cohort here — each model was trained once on
the full X_v3_train. The rolling cohorts are different *test slices*.
That isolates the question:

    "Same model, same training data — does the metric hold up
     when I score next month's signups?"

Inputs (from canvas namespace):
    rolling_splits        (Time-Rolling Splits)
    y_v3_test             (Build Features v3)
    preds_v3              (Train Model v3)        — XGB, RF, HGB, ensemble
    mlp_proba_v3          (Train MLP v3)
    gbm_proba_v3          (Train GBM v3 — sklearn GradientBoosting)

Outputs:
    rolling_metrics_v3    pd.DataFrame  — long table: cohort × model → metrics

NOTE on shape: the entire block body is wrapped in a single function so
that no transient locals (`candidates`, `rows`, `pivot_pr`, `y_full`, ...)
are exposed at module level. Zerve runs all canvas blocks in one shared
global namespace, so module-level names collide across blocks and the
canvas linter flags them as 'defined in multiple places'. Wrapping moves
those names into function scope, leaves only the explicitly-returned
output (`rolling_metrics_v3`) at module level.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
)


def _train_across_time_main(rolling_splits_in, y_v3_test_in,
                             preds_v3_in, mlp_proba_v3_in, gbm_proba_v3_in):
    # ─── 1. assemble candidate predictions ───────────────────────────────
    candidates = {}
    for name, p in preds_v3_in.items():
        candidates[name] = np.asarray(p)
    candidates["mlp_v3"] = np.asarray(mlp_proba_v3_in)
    candidates["gbm_v3"] = np.asarray(gbm_proba_v3_in)

    print(f"[AutoML] {len(candidates)} candidate models × "
          f"{len(rolling_splits_in)} rolling cohorts = "
          f"{len(candidates) * len(rolling_splits_in)} evaluations")

    y_full = np.asarray(y_v3_test_in).astype(int)

    def _safe_metric(fn, y, p):
        if y.sum() == 0 or (y.sum() == len(y)):
            return float("nan")
        try:
            return float(fn(y, p))
        except Exception:
            return float("nan")

    # ─── 2. evaluate every (model, cohort) pair ──────────────────────────
    rows = []
    for cohort in rolling_splits_in:
        mask = cohort["test_mask"]
        y_c = y_full[mask]
        if y_c.sum() == 0:
            continue
        base_rate = y_c.mean()
        n = len(y_c)
        k5 = max(int(np.ceil(n * 0.05)), 1)
        k10 = max(int(np.ceil(n * 0.10)), 1)
        for model_name, p_full in candidates.items():
            p_c = p_full[mask]
            order = np.argsort(-p_c)
            top5_prec = float(y_c[order[:k5]].mean()) if k5 else float("nan")
            top10_prec = float(y_c[order[:k10]].mean()) if k10 else float("nan")
            rows.append({
                "cohort": cohort["name"],
                "cohort_label": cohort["label"],
                "month": cohort["month"],
                "model": model_name,
                "n_test": n,
                "n_pos": int(y_c.sum()),
                "base_rate": float(base_rate),
                "pr_auc": _safe_metric(average_precision_score, y_c, p_c),
                "roc_auc": _safe_metric(roc_auc_score, y_c, p_c),
                "brier": _safe_metric(brier_score_loss, y_c, p_c),
                "top5_precision": top5_prec,
                "top10_precision": top10_prec,
                "top5_lift": top5_prec / base_rate if base_rate > 0 else float("nan"),
            })

    df = pd.DataFrame(rows)

    # ─── 3. pretty-print pivots ──────────────────────────────────────────
    print()
    print("=" * 110)
    print("ROLLING METRICS  (PR-AUC primary metric — handles imbalance correctly)")
    print("=" * 110)

    pivot_pr = df.pivot_table(index="model", columns="cohort_label", values="pr_auc")
    ordered_cohorts = [c["label"] for c in rolling_splits_in
                       if c["label"] in pivot_pr.columns]
    pivot_pr = pivot_pr.reindex(columns=ordered_cohorts)
    print(pivot_pr.round(4).to_string())

    print()
    print("ROC-AUC view:")
    pivot_roc = df.pivot_table(
        index="model", columns="cohort_label", values="roc_auc"
    ).reindex(columns=ordered_cohorts)
    print(pivot_roc.round(4).to_string())

    print()
    print(f"Total rows in rolling_metrics_v3: {len(df)}")
    print("Columns:", list(df.columns))

    return df


rolling_metrics_v3 = _train_across_time_main(
    rolling_splits, y_v3_test, preds_v3, mlp_proba_v3, gbm_proba_v3,
)
