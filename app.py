"""
Zerve × ODSC Datathon — Streamlit deployment.

Single-file dashboard. References variables from the Development-layer canvas
via `from zerve import variable` (events, user_features, X_full, lgbm_model,
shap_explainer, feature_cols). Local fallback re-runs the canvas in a shared
namespace so `streamlit run app.py` works outside Zerve too.

Sections:
  1. Hero + 4 headline metrics
  2. 3D PCA user manifold (Plotly Scatter3d, rotatable)
  3. User Lookup with SHAP waterfall (per-prediction explanation)
  4. Funnel Sankey + live thresholds (proves rule monotonicity)
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


# ── Variable resolution ──────────────────────────────────────────────────
def _from_zerve():
    from zerve import variable  # type: ignore[import-not-found]
    return {k: variable(k) for k in [
        "events", "user_features", "X_full", "y_full", "X_test",
        "lgbm_model", "lr_model", "scaler", "shap_explainer", "feature_cols",
    ]}


def _from_local():
    """Re-run the canvas blocks in a shared namespace. Slow on first launch."""
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


# ── Page config + styling ────────────────────────────────────────────────
st.set_page_config(
    page_title="Zerve Funnel & Upgrade Predictor",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  /* Hide all streamlit chrome */
  #MainMenu, footer, header[data-testid="stHeader"] {display: none !important;}
  [data-testid="stToolbar"] {display: none !important;}
  /* Page background */
  .stApp {
    background: radial-gradient(ellipse at top left, #1e1b4b 0%, #020617 50%);
    background-attachment: fixed;
  }
  /* Tighten container */
  .block-container {padding: 2rem 3rem 1rem 3rem !important; max-width: 1400px;}
  /* Hero gradient text */
  .hero-title {
    background: linear-gradient(120deg, #ec4899 0%, #8b5cf6 35%, #06b6d4 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
    font-size: 3rem; font-weight: 800; letter-spacing: -0.025em; line-height: 1.05;
  }
  .hero-sub {color: #94a3b8; font-size: 0.95rem; line-height: 1.6; max-width: 720px; margin-top: 0.75rem;}
  .kicker {color: #ec4899; font-family: 'JetBrains Mono', ui-monospace, monospace;
           font-size: 0.7rem; letter-spacing: 0.25em; text-transform: uppercase;}
  /* Glass cards on metrics */
  div[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(15,23,42,0.7), rgba(11,17,32,0.85));
    backdrop-filter: blur(12px);
    border: 1px solid rgba(51,65,85,0.5);
    padding: 1.1rem 1.2rem; border-radius: 14px;
  }
  div[data-testid="stMetricLabel"] > div {color: #94a3b8 !important; font-size: 0.7rem !important;
                                          letter-spacing: 0.1em; text-transform: uppercase;}
  div[data-testid="stMetricValue"] {color: #f1f5f9 !important; font-weight: 700;}
  /* Section titles */
  h2 {color: #e2e8f0; font-size: 1.6rem !important; font-weight: 700;
      border-left: 3px solid #ec4899; padding-left: 0.85rem; margin-top: 2.5rem !important;}
  /* Tab contents */
  div[role="tablist"] {gap: 0.4rem;}
  button[role="tab"] {background: rgba(15,23,42,0.6); border-radius: 8px;
                      color: #cbd5e1; padding: 0.5rem 1rem;}
  button[role="tab"][aria-selected="true"] {background: rgba(236,72,153,0.18);
                                              color: #f9a8d4; border: 1px solid #ec4899;}
  /* Sliders accent */
  .stSlider [role="slider"] {background-color: #ec4899 !important;}
  /* Selectbox */
  div[data-baseweb="select"] > div {background: rgba(15,23,42,0.7) !important;
                                     border-color: #334155 !important;}
</style>
""", unsafe_allow_html=True)

PLOTLY_DARK = "plotly_dark"
STAGE_COLORS = {
    "1_signed_up":       "#475569",
    "2_active":          "#3b82f6",
    "3_created_content": "#06b6d4",
    "4_used_ai":         "#10b981",
    "5_engaged":         "#84cc16",
    "5b_at_risk":        "#f59e0b",
    "6_upgraded":        "#ec4899",
}
STAGE_LABELS = {
    "1_signed_up": "signed up", "2_active": "active",
    "3_created_content": "created content", "4_used_ai": "used AI",
    "5_engaged": "engaged", "5b_at_risk": "at risk", "6_upgraded": "upgraded",
}


# ── Hero ─────────────────────────────────────────────────────────────────
st.markdown('<div class="kicker">ODSC × Zerve AI Datathon · April 2026</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">User funnel & upgrade predictor</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub">Strict-nested 6-stage funnel + leakage-safe upgrade model, built end-to-end in Zerve. '
    'Drag the 3D manifold, score any user, retune the funnel rules — every prediction is explainable.</div>',
    unsafe_allow_html=True,
)
st.write("")

# Load state
with st.spinner("Loading model + data…"):
    state = load_state()
events         = state["events"]
user_features  = state["user_features"]
X_full         = state["X_full"]
lgbm_model     = state["lgbm_model"]
shap_explainer = state["shap_explainer"]
feature_cols   = state["feature_cols"]


# ── Headline metrics ─────────────────────────────────────────────────────
n_users   = len(user_features)
n_engaged = int(user_features["stage"].isin(["5_engaged", "5b_at_risk", "6_upgraded"]).sum())
n_upgrade = int((user_features["stage"] == "6_upgraded").sum())
n_at_risk = int((user_features["stage"] == "5b_at_risk").sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("users", f"{n_users:,}", f"{int(len(events)):,} events")
m2.metric("reached engaged", f"{n_engaged:,}", f"{100*n_engaged/n_users:.1f}% of all")
m3.metric("upgraded", f"{n_upgrade:,}", f"{100*n_upgrade/n_users:.2f}% base rate")
m4.metric("at risk", f"{n_at_risk:,}", f"{100*n_at_risk/n_engaged:.0f}% of engaged", delta_color="inverse")


# ── Section: 3D Manifold ────────────────────────────────────────────────
st.markdown('<div class="kicker" style="margin-top:2rem">// 03</div>', unsafe_allow_html=True)
st.markdown("## User behavior manifold")
st.caption("3D PCA of every user's first-window behavior. Color = funnel stage. Size = predicted upgrade probability. Drag to rotate, scroll to zoom.")

@st.cache_data(show_spinner=False)
def build_manifold():
    Xv = X_full.values
    pca = PCA(n_components=3, random_state=42)
    coords = pca.fit_transform(StandardScaler().fit_transform(Xv))
    proba = lgbm_model.predict_proba(Xv)[:, 1]
    df = pd.DataFrame({
        "id": X_full.index,
        "x": coords[:, 0], "y": coords[:, 1], "z": coords[:, 2],
        "prob": proba,
        "stage": [user_features.loc[pid, "stage"] if pid in user_features.index else "1_signed_up"
                  for pid in X_full.index],
    })
    return df, pca.explained_variance_ratio_

manifold, evr = build_manifold()
mc1, mc2 = st.columns([4, 1])

with mc2:
    show_stages = st.multiselect(
        "show stages",
        options=list(STAGE_COLORS),
        default=list(STAGE_COLORS),
        format_func=lambda s: STAGE_LABELS[s],
    )
    sample_n = st.slider("sample size", 500, min(8000, len(manifold)),
                         min(3000, len(manifold)), step=500)
    boost_size = st.checkbox("emphasize high-prob users", value=True)

view = manifold[manifold["stage"].isin(show_stages)]
if len(view) > sample_n:
    parts = []
    for s in view["stage"].unique():
        sub = view[view["stage"] == s]
        share = max(1, int(round(sample_n * len(sub) / len(view))))
        parts.append(sub.sample(min(len(sub), share), random_state=42))
    view = pd.concat(parts, ignore_index=True)

if boost_size:
    p_max = max(view["prob"].max(), 1e-9)
    sizes = 4 + 22 * (view["prob"] / p_max) ** 0.7
else:
    sizes = pd.Series(4, index=view.index)

fig3d = go.Figure()
for stage in [s for s in STAGE_COLORS if s in view["stage"].unique()]:
    sub = view[view["stage"] == stage]
    fig3d.add_trace(go.Scatter3d(
        x=sub["x"], y=sub["y"], z=sub["z"], mode="markers",
        name=STAGE_LABELS[stage],
        marker=dict(
            size=sizes.loc[sub.index].clip(2, 28),
            color=STAGE_COLORS[stage], opacity=0.78,
            line=dict(width=0),
        ),
        customdata=np.stack([sub["id"], sub["prob"]], axis=-1),
        hovertemplate=("<b>%{customdata[0]}</b><br>"
                       f"stage: {STAGE_LABELS[stage]}<br>"
                       "upgrade prob: %{customdata[1]:.2%}<extra></extra>"),
    ))
fig3d.update_layout(
    template=PLOTLY_DARK, height=620,
    margin=dict(l=0, r=0, t=10, b=10),
    scene=dict(
        xaxis_title=f"PC1 ({evr[0]*100:.1f}%)",
        yaxis_title=f"PC2 ({evr[1]*100:.1f}%)",
        zaxis_title=f"PC3 ({evr[2]*100:.1f}%)",
        bgcolor="rgba(0,0,0,0)",
        xaxis=dict(backgroundcolor="rgba(15,23,42,0.3)", gridcolor="#1e293b"),
        yaxis=dict(backgroundcolor="rgba(15,23,42,0.3)", gridcolor="#1e293b"),
        zaxis=dict(backgroundcolor="rgba(15,23,42,0.3)", gridcolor="#1e293b"),
    ),
    paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(bgcolor="rgba(15,23,42,0.7)", bordercolor="#334155", borderwidth=1, font=dict(size=11)),
)
with mc1:
    st.plotly_chart(fig3d, use_container_width=True)


# ── Section: User Lookup ────────────────────────────────────────────────
st.markdown('<div class="kicker" style="margin-top:2rem">// 04</div>', unsafe_allow_html=True)
st.markdown("## Per-user prediction & explanation")
st.caption("Pick a user → upgrade likelihood + the SHAP factors that pushed it up or down. Pink = pushes prob up, cyan = pushes it down.")

candidates = sorted(X_full.index.tolist())
person_id = st.selectbox("user (person_id)", candidates, index=0, label_visibility="collapsed")

stage = user_features.loc[person_id, "stage"] if person_id in user_features.index else "1_signed_up"
x_row = X_full.loc[[person_id]]
prob = float(lgbm_model.predict_proba(x_row.values)[0, 1])

shap_raw = shap_explainer.shap_values(x_row.values)
if isinstance(shap_raw, list):
    shap_row = shap_raw[1][0]
elif shap_raw.ndim == 3:
    shap_row = shap_raw[0, :, 1]
else:
    shap_row = shap_raw[0]

c1, c2, c3 = st.columns(3)
c1.metric("funnel stage", STAGE_LABELS[stage])
c2.metric("upgrade likelihood", f"{prob:.1%}")
n_days = int(x_row["n_distinct_days_obs"].iloc[0]) if "n_distinct_days_obs" in x_row.columns else 0
c3.metric("days active in obs window", n_days)

shap_df = pd.DataFrame({
    "feature": feature_cols,
    "value":   x_row.values[0],
    "shap":    shap_row,
}).assign(abs_shap=lambda d: d["shap"].abs()).sort_values("abs_shap", ascending=False).head(10).iloc[::-1]

fig_shap = go.Figure(go.Bar(
    x=shap_df["shap"],
    y=[f"{f}  =  {v:.2f}" for f, v in zip(shap_df["feature"], shap_df["value"])],
    orientation="h",
    marker=dict(color=["#ec4899" if s > 0 else "#06b6d4" for s in shap_df["shap"]]),
    hovertemplate="%{y}<br>SHAP: %{x:.3f}<extra></extra>",
))
fig_shap.update_layout(
    template=PLOTLY_DARK, height=420,
    title=dict(text="Top 10 SHAP contributions", font=dict(size=13)),
    xaxis_title="SHAP value (log-odds delta)",
    margin=dict(l=10, r=10, t=50, b=10),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
)
fig_shap.add_vline(x=0, line=dict(color="#475569", width=1, dash="dot"))
st.plotly_chart(fig_shap, use_container_width=True)


# ── Section: Funnel Sankey + Explorer ───────────────────────────────────
st.markdown('<div class="kicker" style="margin-top:2rem">// 05</div>', unsafe_allow_html=True)
st.markdown("## Funnel flow & live thresholds")
st.caption("Sankey shows actual user flow between funnel stages. Sliders recompute the funnel live — moving them proves the strict-nested rule system stays monotone (no stage explodes when you retune).")

CREATED_EVENTS = {"agent_tool_call_create_block_tool", "run_block", "new_canvas_created"}
AI_EVENTS = {"$ai_generation", "agent_new_chat", "agent_worker_created"}

sc1, sc2, sc3 = st.columns(3)
signin_thr = sc1.slider("active threshold:  n_signins ≥",        1, 10, 2)
days_thr   = sc2.slider("engaged threshold:  n_distinct_days ≥", 1, 14, 3)
ai_thr     = sc3.slider("used_ai threshold:  n_ai ≥",            1, 50, 1)

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
is_ai_used  = is_created & (uf["n_ai"] >= ai_thr)
is_engaged  = is_ai_used & (uf["n_distinct_days"] >= days_thr)
is_upgraded = uf["upgraded"]

stages = ["signed up", "active", "created", "used AI", "engaged", "upgraded"]
reach = [
    int(len(uf)),
    int(is_active.sum()), int(is_created.sum()), int(is_ai_used.sum()),
    int(is_engaged.sum()), int(is_upgraded.sum()),
]
dropped = [reach[i] - reach[i+1] for i in range(len(reach)-1)]
total = reach[0]

# Sankey: stage chain + dropoffs
labels = stages + [f"dropped @ {s}" for s in stages[:-1]]
sankey_colors = ["#475569", "#3b82f6", "#06b6d4", "#10b981", "#84cc16", "#ec4899"] + ["#7f1d1d"] * 5
src, tgt, val, link_color = [], [], [], []
for i in range(len(stages) - 1):
    if reach[i+1] > 0:
        src.append(i); tgt.append(i+1); val.append(reach[i+1])
        link_color.append("rgba(59,130,246,0.45)")
    if dropped[i] > 0:
        src.append(i); tgt.append(len(stages) + i); val.append(dropped[i])
        link_color.append("rgba(239,68,68,0.30)")

fig_sankey = go.Figure(go.Sankey(
    arrangement="snap",
    node=dict(pad=22, thickness=22, line=dict(color="rgba(0,0,0,0)", width=0),
              label=[f"{labels[i]}  {(reach[i] if i < len(reach) else dropped[i-len(reach)]):,}" for i in range(len(labels))],
              color=sankey_colors),
    link=dict(source=src, target=tgt, value=val, color=link_color),
))
fig_sankey.update_layout(
    template=PLOTLY_DARK, height=480, margin=dict(l=10, r=10, t=10, b=10),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=11),
)
st.plotly_chart(fig_sankey, use_container_width=True)

# Conversion table
table = pd.DataFrame({
    "stage": stages,
    "users": reach,
    "% of total": [f"{100*r/total:.2f}%" for r in reach],
    "conv from prior": ["—"] + [f"{100*reach[i]/reach[i-1]:.1f}%" for i in range(1, len(reach))],
})
st.dataframe(table, hide_index=True, use_container_width=True)

st.markdown(
    '<div style="text-align:center; color:#475569; font-size:0.75rem; margin-top:2rem; '
    'padding-top:1.5rem; border-top:1px solid rgba(51,65,85,0.4)">'
    '3.5M events · 17,541 users · 2025-09-01 → 2026-04-16 · Built end-to-end in Zerve</div>',
    unsafe_allow_html=True,
)
