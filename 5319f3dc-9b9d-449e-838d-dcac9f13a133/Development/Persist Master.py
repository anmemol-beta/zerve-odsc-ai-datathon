"""Persist Master — writes the updated events pool back to the durable store.

In production this block would push the merged events pool back to the
external store (S3, GCS, a warehouse) so that next week's run starts
from this week's accumulated state. In Zerve we write to `/tmp` for the
within-canvas cache and PRINT the upload command that a real deployment
would execute. The actual upload is mocked because the canvas does not
have credentials to push to GitHub or S3 — that step belongs to a CI
job triggered after the canvas run.

Why split write vs upload:
    The canvas should be able to dry-run the merge without side effects.
    Pushing to durable storage is a *commit* — best done from a CI job
    that has scoped credentials, AFTER the model retrain on the new
    trainable subset has succeeded.

Inputs:
    events_pipeline       (Merge Events)
    merge_summary         (Merge Events)
    master_meta           (Load Events Master)

Outputs:
    persist_master_meta   dict   — local path, sha hash, target upload url
"""
import os
import json
import hashlib
import pathlib
from datetime import datetime, timezone

import pandas as pd

LOCAL_DIR = pathlib.Path("/tmp/zerve-pipeline")
LOCAL_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_PATH = LOCAL_DIR / "events_master.parquet"
META_PATH = LOCAL_DIR / "events_master.meta.json"

# In production this would be e.g. s3://my-bucket/events_master.parquet
# or a Zerve File-Storage URL. For the demo we just *describe* the target.
TARGET_UPLOAD_URL = os.environ.get(
    "EVENTS_MASTER_UPLOAD_TARGET",
    "s3://zerve-demo/events_master.parquet  (mocked — CI job would push)",
)


# ─── 1. write merged pool to local cache ─────────────────────────────────
events_pipeline.to_parquet(LOCAL_PATH, compression="snappy", index=False)
size_kb = LOCAL_PATH.stat().st_size / 1024

# ─── 2. content hash for idempotency / change detection ──────────────────
sha = hashlib.sha256(LOCAL_PATH.read_bytes()).hexdigest()[:12]


# ─── 3. write companion meta.json ────────────────────────────────────────
persist_master_meta = {
    "written_at": datetime.now(timezone.utc).isoformat(),
    "local_path": str(LOCAL_PATH),
    "size_kb": round(size_kb, 1),
    "sha256_12": sha,
    "n_rows": int(len(events_pipeline)),
    "n_users": int(events_pipeline["person_id"].nunique()),
    "label_lag_days": merge_summary["label_lag_days"],
    "trainable_users": merge_summary["n_trainable_users"],
    "upstream_master_source": master_meta["source"],
    "upload_target": TARGET_UPLOAD_URL,
    "upload_status": "MOCKED — would run in CI after successful retrain",
}
META_PATH.write_text(json.dumps(persist_master_meta, indent=2))


# ─── 4. report ───────────────────────────────────────────────────────────
print()
print("=" * 80)
print("PERSIST MASTER")
print("=" * 80)
print(f"  written      : {LOCAL_PATH}  ({size_kb:.1f} KB)")
print(f"  sha          : {sha}")
print(f"  n_rows       : {persist_master_meta['n_rows']:,}")
print(f"  n_users      : {persist_master_meta['n_users']:,}")
print()
print("  → Production CI job would now run:")
print(f"      aws s3 cp {LOCAL_PATH} {TARGET_UPLOAD_URL}")
print(f"      (or: gh workflow run promote-master --ref main)")
print()
print("  Next weekly cron picks up the updated master on the same DAG.")
