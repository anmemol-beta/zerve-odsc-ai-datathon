"""
Zerve × ODSC Datathon — interactive Streamlit + Plotly 3D dashboard.

Four sections:
  1. Headline metrics
  2. 3D User Manifold      — PCA(feature) projection, colored by funnel stage,
                             sized by upgrade probability. Rotatable.
  3. User Lookup           — pick a user, see stage + upgrade prob + SHAP
                             contributions in a Plotly waterfall.
  4. Funnel Sankey + Explorer — Sankey diagram of stage flow + live thresholds
                                that recompute the funnel.

References variables exported from the Zerve canvas via `from zerve import variable`.
Local dev fallback: re-runs the canvas blocks in a shared namespace.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


# ── Variable resolution ───────────────────────────────────────────────────
def _from_zerve():
    from zerve import variable  # type: ignore[import-not-found]
    return {k: variable(k) for k in [
        "events", "user_features", "X_full", "y_full", "X_test",
        "lgbm_model", "lr_model", "scaler", "shap_explainer", "feature_cols",
    ]}


def _from_local():
    repo_root = Path(__file__).resolve().parent
    canvas = repo_root / "5319f3dc-9b9d-449e-838d-dcac9f13a133" / "Development"
    datas = repo_root / "datas"
    cwd = os.getcwd()
    if datas.exists():
        os.chdir(datas)
    try:
        ns: dict = {}
        exec("import pandas as pd", ns)
        for name in ["Example Dataset", "EDA Summary", "Funnel Stages",
                     "Build Features", "Train Model"]:
            src = (canvas / f"{name}.py").read_text()
            exec(compile(src, name, "exec"), ns)
    finally:
        os.chdir(cwd)
    return ns


@st.cache_resource
def load_state():
    try:
        return _from_zerve()
    except Exception:
        return _from_local()


# ── Style ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Zerve Funnel & Upgrade Predictor",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown("""
<style>
  /* hide streamlit chrome */
  #MainMenu, footer, header {visibility: hidden;}
  /* tighter padding */
  .block-container {padding-top: 1.5rem; padding-bottom: 1rem; max-width: 1500px;}
  /* metric styling */
  div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    padding: 1rem 1.2rem; border-radius: 12px;
    border: 1px solid #334155;
  }
  div[data-testid="stMetricLabel"] {color: #94a3b8 !important; font-size: 0.85rem;}
  div[data-testid="stMetricValue"] {color: #f1f5f9 !important;}
  /* headers */
  h1 {color: #f1f5f9; font-weight: 700; letter-spacing: -0.02em;}
  h2 {color: #e2e8f0; border-left: 4px solid #3b82f6; padding-left: 0.7rem; margin-top: 2rem;}
  /* select boxes */
  .stSelectbox label {color: #cbd5e1 !important;}
  /* body */
  .stApp {background: #020617;}
</style>
""", unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_dark"
STAGE_COLORS = {
    "1_signed_up":       "#64748b",
    "2_active":          "#3b82f6",
    "3_created_content": "#06b6d4",
    "4_used_ai":         "#10b981",
    "5_engaged":         "#84cc16",
    "5b_at_risk":        "#f59e0b",
    "6_upgraded":        "#ec4899",
}

st.title("Zerve User Funnel & Upgrade Predictor")
st.caption("ODSC × Zerve AI Datathon · April 2026  ·  Strict-nested funnel + leakage-safe model + 3D user manifold")

with st.spinner("Loading canvas state…"):
    state = load_state()
events         = state["events"]
user_features  = state["user_features"]
X_full         = state["X_full"]
lgbm_model     = state["lgbm_model"]
shap_explainer = state["shap_explainer"]
feature_cols   = state["feature_cols"]


# ── Section 1: Headline metrics ──────────────────────────────────────────
n_users = len(user_features)
n_upgrade = int((user_features["stage"] == "6_upgraded").sum())
n_engaged = int(((user_features["stage"] == "5_engaged") |
                 (user_features["stage"] == "5b_at_risk") |
                 (user_features["stage"] == "6_upgraded")).sum())
n_at_risk = int((user_features["stage"] == "5b_at_risk").sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("total users", f"{n_users:,}")
c2.metric("reached engaged", f"{n_engaged:,}", f"{100*n_engaged/n_users:.1f}%")
c3.metric("upgraded (paid)", f"{n_upgrade:,}", f"{100*n_upgrade/n_users:.2f}%")
c4.metric("at risk (engaged → idle)", f"{n_at_risk:,}", f"{100*n_at_risk/n_engaged:.0f}% of engaged", delta_color="inverse")


# ── Section 2: 3D user manifold ──────────────────────────────────────────
st.header("User Manifold — 3D PCA of behavior features")
st.caption("Each point is a user. Position = PCA of behavioral features. Color = funnel stage. Size = predicted upgrade probability. Drag to rotate, scroll to zoom.")

@st.cache_data(show_spinner=False)
def build_manifold():
    Xv = X_full.values
    pca = PCA(n_components=3, random_state=42)
    coords = pca.fit_transform(StandardScaler().fit_transform(Xv))
    proba = lgbm_model.predict_proba(Xv)[:, 1]
    df = pd.DataFrame({
        "person_id": X_full.index,
        "x": coords[:, 0], "y": coords[:, 1], "z": coords[:, 2],
        "upgrade_prob": proba,
    })
    df["stage"] = df["person_id"].map(user_features["stage"]).fillna("1_signed_up")
    df["explained_var_pct"] = float(pca.explained_variance_ratio_.sum() * 100)
    return df, pca.explained_variance_ratio_

manifold, evr = build_manifold()
mc1, mc2 = st.columns([3, 1])
with mc2:
    show_stages = st.multiselect(
        "show stages",
        options=list(STAGE_COLORS.keys()),
        default=list(STAGE_COLORS.keys()),
    )
    sample_n = st.slider("sample size (smaller = faster)", 500, min(8000, len(manifold)),
                         min(3000, len(manifold)), step=500)
    boost_size = st.checkbox("emphasize high-prob users", value=True)

view = manifold[manifold["stage"].isin(show_stages)]
if len(view) > sample_n:
    # Stratified by stage so rare classes stay visible
    parts = []
    for s in view["stage"].unique():
        sub = view[view["stage"] == s]
        share = max(1, int(round(sample_n * len(sub) / len(view))))
        parts.append(sub.sample(min(len(sub), share), random_state=42))
    view = pd.concat(parts, ignore_index=True)

# Marker size: emphasize high-prob users when enabled
if boost_size:
    sizes = 4 + 30 * (view["upgrade_prob"] / max(view["upgrade_prob"].max(), 1e-9)) ** 0.7
else:
    sizes = np.full(len(view), 4)

fig3d = go.Figure()
for stage in [s for s in STAGE_COLORS if s in view["stage"].unique()]:
    sub = view[view["stage"] == stage]
    sub_sizes = sizes[view["stage"] == stage] if hasattr(sizes, '__getitem__') else sizes
    fig3d.add_trace(go.Scatter3d(
        x=sub["x"], y=sub["y"], z=sub["z"],
        mode="markers",
        name=stage.replace("_", " "),
        marker=dict(
            size=sub_sizes if hasattr(sub_sizes, '__len__') else 4,
            color=STAGE_COLORS[stage],
            opacity=0.75,
            line=dict(width=0),
        ),
        customdata=np.stack([sub["person_id"], sub["upgrade_prob"]], axis=-1),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            f"stage: {stage}<br>"
            "upgrade prob: %{customdata[1]:.2%}<br>"
            "<extra></extra>"
        ),
    ))
fig3d.update_layout(
    template=PLOTLY_TEMPLATE,
    height=600,
    margin=dict(l=0, r=0, t=10, b=10),
    scene=dict(
        xaxis_title=f"PC1 ({evr[0]*100:.1f}%)",
        yaxis_title=f"PC2 ({evr[1]*100:.1f}%)",
        zaxis_title=f"PC3 ({evr[2]*100:.1f}%)",
        bgcolor="#020617",
    ),
    legend=dict(bgcolor="rgba(15,23,42,0.6)", bordercolor="#334155", borderwidth=1),
)
with mc1:
    st.plotly_chart(fig3d, use_container_width=True)
st.caption(f"PCA explains {sum(evr)*100:.1f}% of variance across PC1+PC2+PC3 (PC1: {evr[0]*100:.1f}%, PC2: {evr[1]*100:.1f}%, PC3: {evr[2]*100:.1f}%).")


# ── Section 3: User Lookup ──────────────────────────────────────────────
st.header("User Lookup — per-user prediction & explanation")
st.caption("Pick a user → upgrade probability + the SHAP factors that pushed it up or down.")

candidates = sorted(X_full.index.tolist())
person_id = st.selectbox("user (person_id)", candidates, index=0)

stage = user_features.loc[person_id, "stage"] if person_id in user_features.index else "—"
x_row = X_full.loc[[person_id]]
prob = float(lgbm_model.predict_proba(x_row.values)[0, 1])

shap_raw = shap_explainer.shap_values(x_row.values)
if isinstance(shap_raw, list):
    shap_row = shap_raw[1][0]
elif shap_raw.ndim == 3:
    shap_row = shap_raw[0, :, 1]
else:
    shap_row = shap_raw[0]

uc1, uc2, uc3 = st.columns(3)
uc1.metric("funnel stage", stage)
uc2.metric("upgrade likelihood", f"{prob:.1%}")
n_active_days = int(x_row["n_distinct_days_obs"].iloc[0]) if "n_distinct_days_obs" in x_row.columns else 0
uc3.metric("active days in obs window", n_active_days)

shap_df = pd.DataFrame({
    "feature": feature_cols,
    "value":   x_row.values[0],
    "shap":    shap_row,
}).assign(abs_shap=lambda d: d["shap"].abs()).sort_values("abs_shap", ascending=False).head(10)
shap_df = shap_df.iloc[::-1]  # Plotly renders bottom-up

fig_shap = go.Figure(go.Bar(
    x=shap_df["shap"], y=[f"{f}  (={v:.2f})" for f, v in zip(shap_df["feature"], shap_df["value"])],
    orientation="h",
    marker=dict(color=["#ec4899" if s > 0 else "#06b6d4" for s in shap_df["shap"]]),
    hovertemplate="%{y}<br>SHAP: %{x:.3f}<extra></extra>",
))
fig_shap.update_layout(
    template=PLOTLY_TEMPLATE,
    height=400,
    title="Top 10 SHAP contributions (→ pushes upgrade prob up, ← down)",
    xaxis_title="SHAP value (log-odds delta)",
    margin=dict(l=10, r=10, t=50, b=10),
    plot_bgcolor="#020617", paper_bgcolor="#020617",
)
fig_shap.add_vline(x=0, line=dict(color="#64748b", width=1, dash="dot"))
st.plotly_chart(fig_shap, use_container_width=True)


# ── Section 4: Funnel Sankey + Explorer ─────────────────────────────────
st.header("Funnel Flow — Sankey + interactive thresholds")
st.caption("Sankey shows current user flow between stages. Sliders recompute the funnel live — moving them proves the rules are robust (still monotone-decreasing).")

CREATED_EVENTS = {"agent_tool_call_create_block_tool", "run_block", "new_canvas_created"}
AI_EVENTS = {"$ai_generation", "agent_new_chat", "agent_worker_created"}

s1, s2, s3 = st.columns(3)
signin_thr = s1.slider("`n_signins ≥ ?` for active",        1, 10, 2)
days_thr   = s2.slider("`n_distinct_days ≥ ?` for engaged", 1, 14, 3)
ai_thr     = s3.slider("`n_ai ≥ ?` for used_ai",            1, 50, 1)

@st.cache_data(show_spinner=False)
def per_user_aggs(_hash):
    flags = pd.DataFrame({
        "person_id":  events["person_id"],
        "is_signin":  events["event"].eq("sign_in"),
        "is_created": events["event"].isin(CREATED_EVENTS),
        "is_ai":      events["event"].isin(AI_EVENTS),
        "is_upgrade": events["event"].eq("subscription_upgraded"),
        "date":       events["timestamp"].dt.date,
    })
    return flags.groupby("person_id", sort=False, observed=True).agg(
        n_signins      =("is_signin",  "sum"),
        n_created      =("is_created", "sum"),
        n_ai           =("is_ai",      "sum"),
        upgraded       =("is_upgrade", "any"),
        n_distinct_days=("date",       "nunique"),
    )

uf = per_user_aggs(id(events))
is_active   = (uf["n_signins"] >= signin_thr) | (uf["n_distinct_days"] >= 2)
is_created  = is_active  & (uf["n_created"] > 0)
is_ai       = is_created & (uf["n_ai"] >= ai_thr)
is_engaged  = is_ai      & (uf["n_distinct_days"] >= days_thr)
is_upgraded = uf["upgraded"]

stages = ["signed_up", "active", "created", "used_ai", "engaged", "upgraded"]
reach = [
    len(uf),
    int(is_active.sum()),
    int(is_created.sum()),
    int(is_ai.sum()),
    int(is_engaged.sum()),
    int(is_upgraded.sum()),
]
dropped = [reach[i] - reach[i+1] for i in range(len(reach)-1)]
total = reach[0]

# Sankey: each stage flows to (next stage, dropped)
sankey_labels = []
for i, s in enumerate(stages):
    sankey_labels.append(f"{s} ({reach[i]:,})")
for i in range(len(stages) - 1):
    sankey_labels.append(f"dropped at {stages[i]} ({dropped[i]:,})")

# build src/dst
src, dst, val, color = [], [], [], []
for i in range(len(stages) - 1):
    src.append(i)
    dst.append(i + 1)
    val.append(reach[i + 1])
    color.append("rgba(59,130,246,0.5)")
    src.append(i)
    dst.append(len(stages) + i)  # dropped
    val.append(dropped[i])
    color.append("rgba(244,63,94,0.35)")

stage_colors_hex = ["#64748b","#3b82f6","#06b6d4","#10b981","#84cc16","#ec4899"]
node_colors = stage_colors_hex + ["#7f1d1d"] * (len(stages) - 1)

fig_sankey = go.Figure(go.Sankey(
    arrangement="snap",
    node=dict(
        pad=24, thickness=22,
        line=dict(color="#020617", width=0.5),
        label=sankey_labels,
        color=node_colors,
    ),
    link=dict(source=src, target=dst, value=val, color=color),
))
fig_sankey.update_layout(
    template=PLOTLY_TEMPLATE, height=500,
    margin=dict(l=10, r=10, t=20, b=10),
    plot_bgcolor="#020617", paper_bgcolor="#020617",
    font=dict(size=11),
)
st.plotly_chart(fig_sankey, use_container_width=True)

st.dataframe(
    pd.DataFrame({
        "stage": stages,
        "users": reach,
        "% of total": [f"{100*r/total:.2f}%" for r in reach],
        "conv from prior": ["—"] + [f"{100*reach[i]/reach[i-1]:.1f}%" for i in range(1, len(reach))],
    }),
    hide_index=True, use_container_width=True,
)
