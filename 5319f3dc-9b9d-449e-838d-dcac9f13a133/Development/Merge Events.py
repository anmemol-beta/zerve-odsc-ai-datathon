"""Merge Events — joins master + this week's drop, applies label-lag cutoff.

This is the heart of the production data pipeline tier. It:

  1. Concatenates `events_master` + `weekly_drop`
  2. Drops exact duplicates (idempotent re-runs of the same drop)
  3. Applies a *label-lag cutoff*: users whose latest activity is within
     LABEL_LAG_DAYS of "now" are dropped from the trainable subset, because
     their `subscription_upgraded` outcome is still uncertain. Industry
     standard is 30-60 days for monthly subscription products; we default
     to 60 to be conservative.

Why split trainable vs full:
    - `events_pipeline_full`        → for inference (we score everyone)
    - `events_pipeline_trainable`   → for retraining (label-stable subset)

This block is pure data — it does not retrain. The retraining cron would
trigger Build Features v3 → Train Model v3 → Persist Models on the
`events_pipeline_trainable` view (a config switch in production, kept
out of this demo to avoid double-execution costs).

Inputs:
    events_master      (Load Events Master)
    weekly_drop        (Load Weekly Drop)

Outputs:
    events_pipeline           pd.DataFrame  — full union (for inference)
    events_pipeline_trainable pd.DataFrame  — label-stable subset (for retraining)
    merge_summary             dict          — counts before/after dedup, lag cutoff
"""
import os
import pandas as pd

LABEL_LAG_DAYS = int(os.environ.get("LABEL_LAG_DAYS", "60"))


# ─── 1. union ────────────────────────────────────────────────────────────
n_master = len(events_master)
n_drop = len(weekly_drop)

if n_drop > 0:
    events_pipeline = pd.concat([events_master, weekly_drop], ignore_index=True)
else:
    events_pipeline = events_master.copy()

n_unioned = len(events_pipeline)


# ─── 2. dedup (idempotent re-runs) ───────────────────────────────────────
events_pipeline = events_pipeline.drop_duplicates(
    subset=["person_id", "timestamp", "event"]
).reset_index(drop=True)
n_after_dedup = len(events_pipeline)


# ─── 3. label-lag cutoff ─────────────────────────────────────────────────
# A user's `subscription_upgraded` event can lag their other events by up
# to LABEL_LAG_DAYS. If their latest activity is within that window, we
# don't yet know whether they will upgrade — so they should NOT be in the
# training pool, only the inference pool.
data_now = events_pipeline["timestamp"].max()
cutoff = data_now - pd.Timedelta(days=LABEL_LAG_DAYS)
last_activity = events_pipeline.groupby("person_id")["timestamp"].max()
trainable_users = last_activity[last_activity <= cutoff].index
events_pipeline_trainable = events_pipeline[
    events_pipeline["person_id"].isin(trainable_users)
].reset_index(drop=True)


# ─── 4. report ───────────────────────────────────────────────────────────
merge_summary = {
    "label_lag_days": LABEL_LAG_DAYS,
    "data_now": str(data_now),
    "label_cutoff": str(cutoff),
    "n_master_in": int(n_master),
    "n_drop_in": int(n_drop),
    "n_unioned": int(n_unioned),
    "n_after_dedup": int(n_after_dedup),
    "n_full_users": int(events_pipeline["person_id"].nunique()),
    "n_trainable_rows": int(len(events_pipeline_trainable)),
    "n_trainable_users": int(events_pipeline_trainable["person_id"].nunique()),
    "n_held_out_users": int(
        events_pipeline["person_id"].nunique()
        - events_pipeline_trainable["person_id"].nunique()
    ),
}

print()
print("=" * 80)
print(f"MERGE EVENTS  (label_lag={LABEL_LAG_DAYS} days)")
print("=" * 80)
print(f"  master in            : {merge_summary['n_master_in']:>10,} rows")
print(f"  weekly drop in       : {merge_summary['n_drop_in']:>10,} rows")
print(f"  unioned              : {merge_summary['n_unioned']:>10,} rows")
print(f"  after dedup          : {merge_summary['n_after_dedup']:>10,} rows  "
      f"(dropped {merge_summary['n_unioned']-merge_summary['n_after_dedup']:,} dup)")
print(f"  data_now             : {merge_summary['data_now']}")
print(f"  label cutoff         : {merge_summary['label_cutoff']}")
print(f"  full pool users      : {merge_summary['n_full_users']:>10,}")
print(f"  trainable users      : {merge_summary['n_trainable_users']:>10,}  "
      f"(label-stable, ≥ {LABEL_LAG_DAYS}d settled)")
print(f"  held-out users       : {merge_summary['n_held_out_users']:>10,}  "
      f"(too recent to label)")
