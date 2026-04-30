"""Weekly Data Slices — turn raw events into per-week behavioral snapshots.

This block sits at the head of the data-drift / weekly-inference branch.
Every Monday (or whenever new data arrives), this block re-slices the
event log by ISO week and produces a tidy per-(week, user) feature
snapshot that the downstream Data Drift Monitor and Weekly Inference
blocks both consume.

Inputs:
    events  (Example Dataset)  — raw event log

Outputs:
    weekly_slices       dict[str, pd.DataFrame]   week_id → features
    weekly_summary      pd.DataFrame              one row per week:
                                                  n_users, n_events,
                                                  n_upgrades, n_active,
                                                  agent_share, ai_share, ...
    weekly_baseline_id  str                       which week_id is the baseline
                                                  (first 4 weeks pooled)

Why per-(week, user) and not just per-week aggregate:
    Data drift is best detected at the feature distribution level. A weekly
    aggregate hides per-user shape (e.g., median session_min could stay
    flat even if the variance explodes). Per-(week, user) lets the drift
    block use PSI / KS / JS divergence on each feature.
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import numpy as np
import pandas as pd

# ─── 1. attach ISO week to every event ───────────────────────────────────
ev = events.copy()
ev["iso_week"] = ev["timestamp"].dt.to_period("W-MON")  # weeks anchored Mon→Sun
weeks = sorted(ev["iso_week"].unique())
print(f"[weekly] event log spans {len(weeks)} ISO weeks "
      f"({weeks[0]} → {weeks[-1]})")


# ─── 2. lightweight per-(week, user) feature snapshot ────────────────────
# These are the features the drift monitor cares about — pick stable,
# behaviorally meaningful signals, not all 169 v3 features (that would
# be expensive). The drift signal in these correlates with the rest.
KEY_EVENT_GROUPS = {
    "n_events":           lambda mask: mask,                # raw count
    "n_ai_events":        lambda mask: mask & ev["event"].str.contains("ai_|llm_|agent_", case=False, na=False),
    "n_credit_events":    lambda mask: mask & ev["event"].str.contains("credit", case=False, na=False),
    "n_run_events":       lambda mask: mask & ev["event"].str.contains("run_|exec_", case=False, na=False),
    "n_block_events":     lambda mask: mask & ev["event"].str.contains("block_", case=False, na=False),
    "n_exception_events": lambda mask: mask & (ev["event"] == "$exception"),
    "n_deploy_events":    lambda mask: mask & ev["event"].str.contains("deploy", case=False, na=False),
}

weekly_slices = {}
print("[weekly] building per-week per-user feature snapshots...")
for w in weeks:
    in_week = (ev["iso_week"] == w)
    if in_week.sum() == 0:
        continue
    week_ev = ev[in_week]
    users_in_week = week_ev["person_id"].unique()
    snap = pd.DataFrame(index=pd.Index(users_in_week, name="person_id"))

    # raw n_events
    snap["n_events"] = week_ev.groupby("person_id", observed=True).size()
    # event-group counts
    for fname, predicate in KEY_EVENT_GROUPS.items():
        if fname == "n_events":
            continue
        sub = ev[predicate(in_week)]
        if len(sub):
            snap[fname] = sub.groupby("person_id", observed=True).size().reindex(snap.index, fill_value=0)
        else:
            snap[fname] = 0

    # active hours diversity
    week_ev_hours = week_ev.assign(hour=week_ev["timestamp"].dt.hour)
    snap["distinct_hours"] = (
        week_ev_hours.groupby("person_id", observed=True)["hour"].nunique()
        .reindex(snap.index, fill_value=0)
    )
    # session minutes proxy (last - first event in the week, in min)
    spans = (
        week_ev.groupby("person_id", observed=True)["timestamp"].agg(["min", "max"])
    )
    snap["session_min_proxy"] = (
        (spans["max"] - spans["min"]).dt.total_seconds() / 60.0
    ).reindex(snap.index, fill_value=0.0)
    # had_upgrade in this week
    snap["had_upgrade"] = (
        week_ev[week_ev["event"] == "subscription_upgraded"]
        .groupby("person_id", observed=True).size()
        .reindex(snap.index, fill_value=0)
        > 0
    ).astype(int)

    snap = snap.fillna(0).astype({"n_events": "int32"})
    weekly_slices[str(w)] = snap

print(f"[weekly] built {len(weekly_slices)} weekly slices")
sample_w = list(weekly_slices.keys())[len(weekly_slices) // 2]
print(f"        sample slice {sample_w!r}: shape={weekly_slices[sample_w].shape}")


# ─── 3. weekly summary dataframe ─────────────────────────────────────────
summary_rows = []
for w_id, snap in weekly_slices.items():
    summary_rows.append({
        "week": w_id,
        "n_users": len(snap),
        "n_events": int(snap["n_events"].sum()),
        "n_upgrades": int(snap["had_upgrade"].sum()),
        "median_n_events": float(snap["n_events"].median()),
        "p90_n_events": float(snap["n_events"].quantile(0.9)),
        "agent_share": float((snap["n_ai_events"] > 0).mean()),
        "credit_share": float((snap["n_credit_events"] > 0).mean()),
        "exception_share": float((snap["n_exception_events"] > 0).mean()),
        "median_session_min": float(snap["session_min_proxy"].median()),
    })
weekly_summary = pd.DataFrame(summary_rows).sort_values("week").reset_index(drop=True)


# ─── 4. baseline (first 4 weeks pooled) for drift comparison ─────────────
# Drift is measured against this distribution. Configurable downstream.
BASELINE_N_WEEKS = 4
baseline_weeks = weekly_summary["week"].head(BASELINE_N_WEEKS).tolist()
weekly_baseline_id = f"baseline:{baseline_weeks[0]}..{baseline_weeks[-1]}"
print(f"[weekly] baseline = first {BASELINE_N_WEEKS} weeks pooled "
      f"({weekly_baseline_id})")


# ─── 5. report ───────────────────────────────────────────────────────────
print()
print("=" * 90)
print("WEEKLY DATA SLICES SUMMARY")
print("=" * 90)
print(weekly_summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print()
print(f"weekly_slices       : dict of {len(weekly_slices)} DataFrames")
print(f"weekly_summary      : ({len(weekly_summary)}, {len(weekly_summary.columns)})")
print(f"weekly_baseline_id  : {weekly_baseline_id}")
