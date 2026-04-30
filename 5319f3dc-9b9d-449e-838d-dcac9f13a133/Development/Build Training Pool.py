"""Build Training Pool — purpose-split for the TRAINING branch.

Sits between Merge Events and Persist Master. Takes the *label-stable*
slice from Merge Events (users whose subscription outcome has had at
least LABEL_LAG_DAYS to settle) and shapes it as the TRAINING input.

This block exists for two reasons:

    1. DAG legibility — pairs with Build Inference Pool so the canvas
       visually shows the train/infer fork after Merge Events.

    2. Trainability gates — checks the trainable subset has enough rows
       and enough positives to be worth re-training on. If the gate
       fails (e.g., only 5 positives this week), Persist Master should
       NOT promote a new model — we keep the previous champion.

Inputs (from canvas namespace):
    events_pipeline_trainable  (Merge Events) — label-stable subset
    merge_summary              (Merge Events) — counts + cutoffs

Outputs:
    training_pool          pd.DataFrame  — same as events_pipeline_trainable
                                           after gate checks pass
    training_pool_meta     dict          — gate results + recency stats
    training_gate_passed   bool          — should retraining proceed?
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import os
import pandas as pd

# Production-tunable retraining gates
MIN_TRAINING_USERS = int(os.environ.get("MIN_TRAINING_USERS", "100"))
MIN_TRAINING_POSITIVES = int(os.environ.get("MIN_TRAINING_POSITIVES", "10"))


# ─── 1. count positives in the trainable subset ──────────────────────────
# An "upgraded" user is anyone with a `subscription_upgraded` event.
upgraders = events_pipeline_trainable.loc[
    events_pipeline_trainable["event"] == "subscription_upgraded",
    "person_id",
].unique()
n_users = int(events_pipeline_trainable["person_id"].nunique())
n_positives = int(len(upgraders))


# ─── 2. trainability gate ────────────────────────────────────────────────
gate_users = n_users >= MIN_TRAINING_USERS
gate_positives = n_positives >= MIN_TRAINING_POSITIVES
training_gate_passed = bool(gate_users and gate_positives)


# ─── 3. set up the training pool ─────────────────────────────────────────
training_pool = events_pipeline_trainable.copy()


# ─── 4. meta / summary ───────────────────────────────────────────────────
training_pool_meta = {
    "purpose": "training",
    "label_lag_days": merge_summary["label_lag_days"],
    "n_rows": int(len(training_pool)),
    "n_users": n_users,
    "n_positives": n_positives,
    "positive_rate": round(n_positives / max(n_users, 1), 5),
    "gate_users": {
        "min_required": MIN_TRAINING_USERS,
        "observed": n_users,
        "passed": gate_users,
    },
    "gate_positives": {
        "min_required": MIN_TRAINING_POSITIVES,
        "observed": n_positives,
        "passed": gate_positives,
    },
    "training_gate_passed": training_gate_passed,
    "downstream_action": (
        "promote new model via Persist Master"
        if training_gate_passed
        else "KEEP PREVIOUS CHAMPION — too little label-stable data this run"
    ),
}


# ─── 5. report ───────────────────────────────────────────────────────────
print()
print("=" * 80)
print(f"BUILD TRAINING POOL  (label_lag={merge_summary['label_lag_days']} days)")
print("=" * 80)
print(f"  rows                : {training_pool_meta['n_rows']:>10,}")
print(f"  users (label-stable): {training_pool_meta['n_users']:>10,}")
print(f"  positives (upgraded): {training_pool_meta['n_positives']:>10,}  "
      f"({training_pool_meta['positive_rate']*100:.2f}%)")
print()
print("  Trainability gates:")
print(f"    users ≥ {MIN_TRAINING_USERS:<8}: "
      f"{'PASS' if gate_users else 'FAIL'}  ({n_users:,} observed)")
print(f"    positives ≥ {MIN_TRAINING_POSITIVES:<3}     : "
      f"{'PASS' if gate_positives else 'FAIL'}  ({n_positives:,} observed)")
print()
print(f"  → Decision: {training_pool_meta['downstream_action']}")
