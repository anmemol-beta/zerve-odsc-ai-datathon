"""Build Inference Pool — purpose-split for the INFERENCE branch.

Sits between Merge Events and the inference branch. Takes the full merged
events pool (label-stable + label-pending users) and shapes it as the
INFERENCE input — the data the deployed champion will score this week.

Why a separate block from Build Training Pool:
    Train data and inference data come from the SAME source file but have
    DIFFERENT shapes:
      - inference pool: include EVERYONE, regardless of label state.
                        We must score recently-active users so growth/CSM
                        teams have time to act before the upgrade window
                        closes.
      - training pool : include ONLY label-stable users (>=60d settled),
                        because users still inside the label window
                        contribute label noise.
    Splitting visually on the canvas makes the train-vs-infer fork
    legible to anyone reading the DAG.

Inputs (from canvas namespace):
    events_pipeline       (Merge Events) — full union, no label filter
    merge_summary         (Merge Events) — counts + cutoffs

Outputs:
    inference_pool        pd.DataFrame   — events used for THIS week's scoring
    inference_pool_meta   dict           — n_rows, n_users, recency stats
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import os
import pandas as pd

# Optional recency window for inference. We score everyone who has at least
# one event in the last INFERENCE_WINDOW_DAYS. Older users probably don't
# need a fresh score this week. Default 28 days = ~last 4 weeks of activity.
INFERENCE_WINDOW_DAYS = int(os.environ.get("INFERENCE_WINDOW_DAYS", "28"))

# ─── 1. recency filter ───────────────────────────────────────────────────
bip_data_now = events_pipeline["timestamp"].max()
recency_cutoff = bip_data_now - pd.Timedelta(days=INFERENCE_WINDOW_DAYS)
last_seen = events_pipeline.groupby("person_id")["timestamp"].max()
recent_users = last_seen[last_seen >= recency_cutoff].index

inference_pool = events_pipeline[
    events_pipeline["person_id"].isin(recent_users)
].reset_index(drop=True)


# ─── 2. meta / summary ───────────────────────────────────────────────────
inference_pool_meta = {
    "purpose": "inference",
    "inference_window_days": INFERENCE_WINDOW_DAYS,
    "bip_data_now": str(bip_data_now),
    "recency_cutoff": str(recency_cutoff),
    "n_rows": int(len(inference_pool)),
    "n_users": int(inference_pool["person_id"].nunique()),
    "n_users_full_pool": int(events_pipeline["person_id"].nunique()),
    "share_of_full_pool": round(
        inference_pool["person_id"].nunique()
        / max(events_pipeline["person_id"].nunique(), 1),
        4,
    ),
}


# ─── 3. report ───────────────────────────────────────────────────────────
print()
print("=" * 80)
print(f"BUILD INFERENCE POOL  (window={INFERENCE_WINDOW_DAYS} days)")
print("=" * 80)
print(f"  bip_data_now            : {inference_pool_meta['bip_data_now']}")
print(f"  recency cutoff      : {inference_pool_meta['recency_cutoff']}")
print(f"  full pool users     : {inference_pool_meta['n_users_full_pool']:>10,}")
print(f"  inference users     : {inference_pool_meta['n_users']:>10,}  "
      f"({inference_pool_meta['share_of_full_pool']*100:.1f}% of full pool)")
print(f"  inference rows      : {inference_pool_meta['n_rows']:>10,}")
print()
print("  → Weekly Inference branch consumes this pool to score every user")
print("    with the persisted champion model.")
