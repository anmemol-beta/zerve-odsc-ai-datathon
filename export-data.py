"""
Re-run the canvas pipeline, then dump every artifact the Next.js app needs
into web/public/data/*.json. All interactivity in the frontend is then
client-side — no backend call required, which means the deploy is just a
static archive.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
CANVAS = REPO / "5319f3dc-9b9d-449e-838d-dcac9f13a133" / "Development"
DATAS = REPO / "datas"
OUT = REPO / "web" / "public" / "data"

# ── 1. Run the pipeline (Example Dataset → ... → Train Model) into a shared ns
sys.path.insert(0, str(REPO))
if DATAS.exists():
    os.chdir(DATAS)

if sys.platform == "darwin":
    libomp = Path("/opt/homebrew/opt/libomp/lib")
    if libomp.exists():
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
            str(libomp) + ":" + os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        )

ns: dict = {}
exec("import pandas as pd", ns)
for name in ["Example Dataset", "EDA Summary", "Funnel Stages",
             "Build Features", "Train Model"]:
    src = (CANVAS / f"{name}.py").read_text()
    print(f"-- exec: {name}")
    exec(compile(src, name, "exec"), ns)

os.chdir(REPO)
OUT.mkdir(parents=True, exist_ok=True)

events         = ns["events"]
user_features  = ns["user_features"]
funnel_reach   = ns["funnel_reach"]
X_full         = ns["X_full"]
lgbm_model     = ns["lgbm_model"]
shap_explainer = ns["shap_explainer"]
feature_cols   = ns["feature_cols"]
is_active      = ns["is_active"]
is_created     = ns["is_created"]
is_ai          = ns["is_ai"]
is_engaged     = ns["is_engaged"]
is_at_risk     = ns["is_at_risk"]


def dump(name: str, obj):
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(obj, separators=(",", ":")))
    print(f"-- wrote {p.relative_to(REPO)}  ({p.stat().st_size:,} bytes)")


# ── 2. Headline metrics
n_users = int(len(user_features))
stage = user_features["stage"]
n_engaged = int((stage.isin(["5_engaged", "5b_at_risk", "6_upgraded"])).sum())
n_upgrade = int((stage == "6_upgraded").sum())
n_at_risk = int((stage == "5b_at_risk").sum())
ts_min = events["timestamp"].min().isoformat()
ts_max = events["timestamp"].max().isoformat()

dump("headline", {
    "n_users": n_users,
    "n_events": int(len(events)),
    "n_engaged": n_engaged,
    "n_upgraded": n_upgrade,
    "n_at_risk": n_at_risk,
    "n_event_types": int(events["event"].nunique()),
    "time_min": ts_min,
    "time_max": ts_max,
    "base_upgrade_rate": float(n_upgrade / n_users),
})


# ── 3. Top events
top_events = events["event"].value_counts().head(20).reset_index()
top_events.columns = ["event", "count"]
dump("top_events", top_events.to_dict(orient="records"))


# ── 4. Funnel reach (canonical) + current stage counts
dump("funnel_reach", {k: int(v) for k, v in funnel_reach.items()})
dump("stage_distribution", stage.value_counts().to_dict())


# ── 5. 3D PCA manifold for the candidate set (sampled)
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

Xv = X_full.values
pca = PCA(n_components=3, random_state=42)
coords = pca.fit_transform(StandardScaler().fit_transform(Xv))
proba = lgbm_model.predict_proba(Xv)[:, 1]

manifold_df = pd.DataFrame({
    "id": X_full.index,
    "x": coords[:, 0],
    "y": coords[:, 1],
    "z": coords[:, 2],
    "prob": proba,
})
manifold_df["stage"] = manifold_df["id"].map(user_features["stage"]).fillna("1_signed_up")

# Stratified sample so rare stages stay visible.
sample_target = 4000
parts = []
for s in manifold_df["stage"].unique():
    sub = manifold_df[manifold_df["stage"] == s]
    share = max(1, int(round(sample_target * len(sub) / len(manifold_df))))
    parts.append(sub.sample(min(len(sub), share), random_state=42))
manifold_sample = pd.concat(parts, ignore_index=True)

dump("manifold", {
    "explained_variance": [float(v) for v in pca.explained_variance_ratio_],
    "points": [
        {
            "id": str(r.id),
            "x": round(float(r.x), 3),
            "y": round(float(r.y), 3),
            "z": round(float(r.z), 3),
            "prob": round(float(r.prob), 4),
            "stage": str(r.stage),
        } for r in manifold_sample.itertuples()
    ],
})


# ── 6. Per-user lookup table — features + SHAP top contributions
print("-- computing SHAP for full candidate set (~30s)")
shap_raw = shap_explainer.shap_values(Xv)
if isinstance(shap_raw, list):
    shap_values = shap_raw[1]
elif shap_raw.ndim == 3:
    shap_values = shap_raw[..., 1]
else:
    shap_values = shap_raw

users_records = []
for i, pid in enumerate(X_full.index):
    row_shap = shap_values[i]
    abs_shap = np.abs(row_shap)
    top_idx = np.argsort(-abs_shap)[:8]
    users_records.append({
        "id": str(pid),
        "stage": str(user_features.loc[pid, "stage"]) if pid in user_features.index else "1_signed_up",
        "prob": round(float(proba[i]), 4),
        "shap": [
            {
                "feature": feature_cols[j],
                "value": round(float(X_full.values[i, j]), 3),
                "shap": round(float(row_shap[j]), 4),
            }
            for j in top_idx
        ],
    })

# Single big payload — gzipped over the wire it's manageable.
dump("users", users_records)


# ── 7. Funnel grid — precompute every (signin, days, ai) combo so the slider
#    interaction is purely client-side (no backend call).
CREATED_EVENTS = {"agent_tool_call_create_block_tool", "run_block", "new_canvas_created"}
AI_EVENTS = {"$ai_generation", "agent_new_chat", "agent_worker_created"}

flags = pd.DataFrame({
    "person_id":  events["person_id"],
    "is_signin":  events["event"].eq("sign_in"),
    "is_created": events["event"].isin(CREATED_EVENTS),
    "is_ai":      events["event"].isin(AI_EVENTS),
    "is_upgrade": events["event"].eq("subscription_upgraded"),
    "date":       events["timestamp"].dt.date,
})
uf = flags.groupby("person_id", sort=False, observed=True).agg(
    n_signins      =("is_signin",  "sum"),
    n_created      =("is_created", "sum"),
    n_ai           =("is_ai",      "sum"),
    upgraded       =("is_upgrade", "any"),
    n_distinct_days=("date",       "nunique"),
)
total = int(len(uf))

SIGNIN_VALUES = list(range(1, 11))      # 1..10
DAYS_VALUES   = list(range(1, 15))      # 1..14
AI_VALUES     = [1, 2, 3, 5, 10, 20, 50]

grid = []
for signin in SIGNIN_VALUES:
    for days in DAYS_VALUES:
        for ai in AI_VALUES:
            is_active   = (uf["n_signins"] >= signin) | (uf["n_distinct_days"] >= 2)
            is_created  = is_active  & (uf["n_created"] > 0)
            is_ai_used  = is_created & (uf["n_ai"] >= ai)
            is_engaged  = is_ai_used & (uf["n_distinct_days"] >= days)
            is_upgraded = uf["upgraded"]
            grid.append({
                "s": signin, "d": days, "a": ai,
                "r": [
                    total,
                    int(is_active.sum()),
                    int(is_created.sum()),
                    int(is_ai_used.sum()),
                    int(is_engaged.sum()),
                    int(is_upgraded.sum()),
                ],
            })

dump("funnel_grid", {
    "signin_values": SIGNIN_VALUES,
    "days_values":   DAYS_VALUES,
    "ai_values":     AI_VALUES,
    "total":         total,
    "grid":          grid,
})


# ── 8. Sankey edges for default thresholds (signin=2, days=3, ai=1)
default = next(g for g in grid if g["s"] == 2 and g["d"] == 3 and g["a"] == 1)
reach = default["r"]
stages_l = ["signed_up", "active", "created", "used_ai", "engaged", "upgraded"]
sankey_links = []
for i in range(len(stages_l) - 1):
    sankey_links.append({"source": i,           "target": i + 1,                       "value": int(reach[i + 1])})
    sankey_links.append({"source": i,           "target": len(stages_l) + i,           "value": int(reach[i] - reach[i + 1])})
sankey_nodes = [{"name": s, "kind": "stage"} for s in stages_l] + \
               [{"name": f"dropped@{stages_l[i]}", "kind": "drop"} for i in range(len(stages_l) - 1)]

dump("sankey_default", {
    "nodes": sankey_nodes,
    "links": sankey_links,
})

# ── 9. Cohort evolution timeline — for each weekly signup cohort, the share
#       that reached each funnel stage. Lets the dashboard animate how recent
#       cohorts compare to older ones (decision question: are conversions
#       improving over time, or is the upgrade spike just from accumulated
#       eligibility?).
user_first_ts = events.groupby("person_id", sort=False, observed=True)["timestamp"].min()
weeks = user_first_ts.dt.to_period("W").dt.start_time.rename("cohort_week")
cohort_df = pd.DataFrame({
    "cohort":    weeks.reindex(user_features.index).values,
    "active":    is_active.values,
    "created":   is_created.values,
    "ai":        is_ai.values,
    "engaged":   is_engaged.values,
    "at_risk":   is_at_risk.values,
    "upgraded":  user_features["upgraded"].values,
})

cohort_groups = cohort_df.groupby("cohort", observed=True)
cohort_evolution = []
running = {"n": 0, "active": 0, "created": 0, "ai": 0, "engaged": 0, "at_risk": 0, "upgraded": 0}
for week, group in cohort_groups:
    if pd.isna(week):
        continue
    running["n"]        += int(len(group))
    running["active"]   += int(group["active"].sum())
    running["created"]  += int(group["created"].sum())
    running["ai"]       += int(group["ai"].sum())
    running["engaged"]  += int(group["engaged"].sum())
    running["at_risk"]  += int(group["at_risk"].sum())
    running["upgraded"] += int(group["upgraded"].sum())
    cohort_evolution.append({
        "week": pd.Timestamp(week).strftime("%Y-%m-%d"),
        "n":            int(len(group)),
        # Per-cohort stage reach %
        "active_pct":   round(float(group["active"].mean())   * 100, 2),
        "created_pct":  round(float(group["created"].mean())  * 100, 2),
        "ai_pct":       round(float(group["ai"].mean())       * 100, 2),
        "engaged_pct":  round(float(group["engaged"].mean())  * 100, 2),
        "at_risk_pct":  round(float(group["at_risk"].mean())  * 100, 2),
        "upgraded_pct": round(float(group["upgraded"].mean()) * 100, 2),
        # Cumulative through this week (as-of snapshot)
        "cum_n":         running["n"],
        "cum_active":    running["active"],
        "cum_created":   running["created"],
        "cum_ai":        running["ai"],
        "cum_engaged":   running["engaged"],
        "cum_at_risk":   running["at_risk"],
        "cum_upgraded":  running["upgraded"],
        "cum_upgrade_rate": round(100 * running["upgraded"] / max(1, running["n"]), 2),
    })

# Sort chronologically (groupby on Timestamp index already sorts but be explicit)
cohort_evolution.sort(key=lambda x: x["week"])

dump("cohort_evolution", {
    "cohorts": cohort_evolution,
    "total_users":    int(running["n"]),
    "total_upgraded": int(running["upgraded"]),
})


print("-- done")
