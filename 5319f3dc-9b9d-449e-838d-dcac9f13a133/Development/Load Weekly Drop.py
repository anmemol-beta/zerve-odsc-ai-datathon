"""Load Weekly Drop — pulls the latest week of incoming events.

Companion to Load Events Master. While the master block reads the
accumulated pool, this block reads ONLY the new ISO-week of events
that the upstream telemetry system dropped this morning. In production
that drop would land at:

    s3://my-bucket/weekly_drops/events_week_<ISO_WEEK>.csv

For the hackathon demo we point at GitHub raw:

    .../data/weekly_drops/events_week_2026-W18.csv

Configurable via env var:
    TARGET_WEEK    e.g. "2026-W18"  (defaults to the latest available
                                     in the WEEK_CATALOG below)

Outputs:
    weekly_drop          pd.DataFrame  — this week's incoming events
    weekly_drop_meta     dict          — week id, source url, row count
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import os
import io
import urllib.request
import urllib.error
import pandas as pd

lwd_REPO_RAW = (
    "https://raw.githubusercontent.com/"
    "anmemol-beta/zerve-odsc-ai-datathon/main"
)
DROP_URL_TEMPLATE = os.environ.get(
    "WEEKLY_DROP_URL_TEMPLATE",
    f"{lwd_REPO_RAW}/data/weekly_drops/events_week_{{week}}.csv",
)

# Catalog of weeks we have demo drops committed for. In production this
# list would be fetched from the data store (e.g. S3 ListObjects).
WEEK_CATALOG = ["2026-W17", "2026-W18"]

TARGET_WEEK = os.environ.get("TARGET_WEEK") or WEEK_CATALOG[-1]
print(f"[drop] target week = {TARGET_WEEK}")


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "zerve-canvas/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


url = DROP_URL_TEMPLATE.format(week=TARGET_WEEK)
weekly_drop = None
status = "unknown"

try:
    print(f"[drop] fetching {url}")
    csv_text = _fetch_text(url)
    weekly_drop = pd.read_csv(io.StringIO(csv_text))
    status = "ok"
    print(f"[drop] OK — {len(weekly_drop):,} rows")
except urllib.error.HTTPError as e:
    if e.code == 404:
        print(f"[drop] no drop for {TARGET_WEEK} (404) — empty drop")
        weekly_drop = pd.DataFrame(columns=["person_id", "timestamp", "event"])
        status = "empty-404"
    else:
        raise
except Exception as e:
    print(f"[drop] fetch failed ({e}) — empty drop")
    weekly_drop = pd.DataFrame(columns=["person_id", "timestamp", "event"])
    status = f"empty-{type(e).__name__}"

# Schema normalization
if len(weekly_drop):
    weekly_drop["timestamp"] = pd.to_datetime(weekly_drop["timestamp"], utc=True)
    weekly_drop["person_id"] = weekly_drop["person_id"].astype(str)
    weekly_drop["event"] = weekly_drop["event"].astype(str)
    weekly_drop = weekly_drop.dropna(
        subset=["person_id", "timestamp", "event"]
    ).reset_index(drop=True)

weekly_drop_meta = {
    "target_week": TARGET_WEEK,
    "url": url,
    "status": status,
    "n_rows": int(len(weekly_drop)),
    "n_users": int(weekly_drop["person_id"].nunique()) if len(weekly_drop) else 0,
}

print()
print("=" * 70)
print(f"WEEKLY DROP {TARGET_WEEK}")
print("=" * 70)
print(f"  status : {weekly_drop_meta['status']}")
print(f"  rows   : {weekly_drop_meta['n_rows']:,}")
print(f"  users  : {weekly_drop_meta['n_users']:,}")
if len(weekly_drop):
    print(f"  range  : {weekly_drop['timestamp'].min()}  →  {weekly_drop['timestamp'].max()}")
