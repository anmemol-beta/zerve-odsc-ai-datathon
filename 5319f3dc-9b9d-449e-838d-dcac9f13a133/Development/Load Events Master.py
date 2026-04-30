"""Load Events Master — head of the production data pipeline tier.

This block reads the *accumulated* event log from an external store. In a
real production deployment that store would be S3 / GCS / a versioned
data warehouse — anything append-only and durable across canvas runs
(Zerve canvas variables and `/tmp` are not durable enough by themselves).

For the hackathon demo we use **GitHub raw** as the durable store:

    https://raw.githubusercontent.com/<org>/<repo>/main/data/events_master.parquet

The block has a 3-level fallback chain so the rest of the pipeline keeps
working in any environment:

    1. EVENTS_MASTER_URL  env var          → fetch from there
    2. default GitHub raw URL              → fetch from there
    3. fall back to an in-memory snapshot  → derive from the upstream
                                             `events` variable so the
                                             pipeline can still demo
                                             without an external store

Outputs:
    events_master      pd.DataFrame  — accumulated events pool
    master_source      str           — "github-raw" | "env-url" | "fallback-events"
    master_meta        dict          — n_rows, n_users, time range, source url
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import os
import io
import urllib.request
import urllib.error
import pandas as pd

DEFAULT_MASTER_URL = (
    "https://raw.githubusercontent.com/"
    "anmemol-beta/zerve-odsc-ai-datathon/main/data/events_master.parquet"
)
EVENTS_MASTER_URL = os.environ.get("EVENTS_MASTER_URL", DEFAULT_MASTER_URL)
HTTP_TIMEOUT = 30


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "zerve-canvas/1.0"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return r.read()


events_master = None
master_source = "unknown"

try:
    print(f"[master] fetching {EVENTS_MASTER_URL}")
    raw = _fetch(EVENTS_MASTER_URL)
    events_master = pd.read_parquet(io.BytesIO(raw))
    master_source = "env-url" if "EVENTS_MASTER_URL" in os.environ else "github-raw"
    print(f"[master] OK from external store ({len(raw)/1024:.0f} KB)")
except Exception as e:
    print(f"[master] external fetch failed ({e}) — falling back to upstream `events`")
    # Fallback: take the upstream `events` variable (loaded by Example Dataset)
    # and treat it as if it were the master pool. This lets the pipeline
    # demo run end-to-end even without a real external store.
    events_master = events.copy()
    master_source = "fallback-events"

# Schema normalization so downstream blocks don't have to think about dtypes
events_master["timestamp"] = pd.to_datetime(events_master["timestamp"], utc=True)
events_master["person_id"] = events_master["person_id"].astype(str)
events_master["event"] = events_master["event"].astype(str)
events_master = events_master.dropna(subset=["person_id", "timestamp", "event"])
events_master = events_master.reset_index(drop=True)

master_meta = {
    "source": master_source,
    "url": EVENTS_MASTER_URL if master_source != "fallback-events" else None,
    "n_rows": int(len(events_master)),
    "n_users": int(events_master["person_id"].nunique()),
    "time_min": str(events_master["timestamp"].min()),
    "time_max": str(events_master["timestamp"].max()),
}

print()
print("=" * 70)
print("EVENTS MASTER LOADED")
print("=" * 70)
print(f"  source   : {master_meta['source']}")
print(f"  rows     : {master_meta['n_rows']:,}")
print(f"  users    : {master_meta['n_users']:,}")
print(f"  range    : {master_meta['time_min']}  →  {master_meta['time_max']}")
