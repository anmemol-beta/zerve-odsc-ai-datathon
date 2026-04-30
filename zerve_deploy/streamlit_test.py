"""
Streamlit diagnostic — paste this into the deployment editor (deploy type:
Streamlit, run command auto-fills `streamlit run main.py --server.port 8080`).

Goal: prove or disprove whether `zerve.variable()` from a Streamlit deploy
can read variables from the canvas (Beta). We saw cross-container isolation
when running as FastAPI; this checks if Streamlit deploys are wired
differently.

Three tiers tested:
  1. Bare import — does the `zerve` package even exist here?
  2. Variable probe — try reading from 8 representative blocks.
  3. Live use — if reads work, run a real prediction + render a real figure.
"""
import streamlit as st

st.set_page_config(page_title="Zerve canvas access probe", layout="wide")
st.title("Zerve canvas access probe")
st.caption("Streamlit deploy → can it read canvas Beta variables?")

# ─── tier 1 — import ────────────────────────────────────────────────────
st.header("1. Module import")
try:
    from zerve import variable  # type: ignore
    st.success("`from zerve import variable` — OK")
except Exception as e:
    st.error(f"import failed: {e!r}")
    st.stop()

# ─── tier 2 — probe ─────────────────────────────────────────────────────
st.header("2. Variable probes")
PROBES = [
    ("Example Dataset",     "events"),
    ("EDA Summary",         "top_events"),
    ("Funnel Stages",       "user_features"),
    ("Build Features v3",   "X_v3_test"),
    ("Train Model v3",      "models_v3"),
    ("Train Model v3",      "metrics_v3"),
    ("Build Strategies",    "strategies_segments"),
    ("Insights Card",       "insights_card_text"),
    ("Visualize Funnel",    "fig"),
    ("Champion Selector",   "current_champion"),
]

results = []
for block, var in PROBES:
    try:
        v = variable(block, var)
        results.append((block, var, "OK", type(v).__name__, ""))
    except Exception as e:
        results.append((block, var, "ERR", "—", str(e)[:140]))

import pandas as pd
df = pd.DataFrame(results, columns=["block", "var", "status", "type", "error"])
st.dataframe(df, use_container_width=True)

n_ok = sum(1 for r in results if r[2] == "OK")
if n_ok == 0:
    st.error(
        "**Same isolation as FastAPI.** Every probe failed — "
        "Streamlit deploy also can't reach canvas variables. "
        "Conclusion: cross-container isolation is universal on Zerve, "
        "not a per-host quirk. Move to Plan B (artifact dump → GitHub fetch)."
    )
    st.stop()
else:
    st.success(f"**Streamlit deploy CAN read canvas variables** "
               f"({n_ok}/{len(PROBES)} probes worked).")

# ─── tier 3 — live demo ─────────────────────────────────────────────────
st.header("3. Live use")

col1, col2 = st.columns(2)

with col1:
    st.subheader("metrics_v3 table")
    try:
        m = variable("Train Model v3", "metrics_v3")
        st.dataframe(m, use_container_width=True)
    except Exception as e:
        st.warning(f"metrics not available: {e}")

with col2:
    st.subheader("Live predict — row 0 of X_v3_test")
    try:
        import numpy as np
        Xt = variable("Build Features v3", "X_v3_test")
        models = variable("Train Model v3", "models_v3")
        row = Xt.iloc[[0]] if hasattr(Xt, "iloc") else Xt[:1]
        proba = float(np.mean([m.predict_proba(row)[:, 1] for m in models.values()]))
        st.metric("upgrade probability", f"{proba * 100:.2f}%")
    except Exception as e:
        st.warning(f"predict failed: {e}")

st.subheader("Visualize Funnel — live figure")
try:
    fig = variable("Visualize Funnel", "fig")
    st.pyplot(fig)
except Exception as e:
    st.warning(f"figure not available: {e}")

st.divider()
st.caption(
    "If sections 3 succeeded, Streamlit deploy has full canvas access. "
    "Next: decide whether to migrate the Next.js demo to Streamlit, or "
    "keep Next.js + add an internal API bridge running inside this Streamlit "
    "process (e.g., FastAPI mounted as a sub-app)."
)
