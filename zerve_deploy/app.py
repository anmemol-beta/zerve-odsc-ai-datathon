"""
Zerve Dash deployment — paste into a Dash deploy slot.

Why Dash and not the FastAPI in main.py?
  Zerve's deployment matrix has two privilege tiers:
    - API Service (FastAPI/Flask) — isolated from canvas, `zerve.variable()`
      returns nothing.
    - Web Application (Streamlit/Gradio/Dash) — can read canvas variables.
  We want both: live canvas reads AND our Next.js bundle served same-origin.
  Dash gives us that — its `app.server` is a plain Flask app, so we drop our
  routes onto it with @server.route(...), serve the Next.js bundle via
  send_from_directory, and read canvas vars freely with `zerve.variable()`.

Run command:  gunicorn -w 1 -b 0.0.0.0:8080 app:server

Single worker on purpose:
  - matplotlib's pyplot is process-global; multi-worker risks cross-talk
  - simplest cache semantics if we ever add one back

What changed vs main.py (FastAPI):
  - Routes ported 1:1 (same paths, same response shapes — frontend untouched)
  - In-process `_cache` removed: every request re-resolves zerve.variable(),
    so the page picks up canvas re-runs automatically.
  - Empty Dash layout — we only use Dash to get the canvas-accessible Flask app.
"""
import hashlib
import io
import json
import shutil
import tarfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dash import Dash, html
from flask import Response, jsonify, request, send_from_directory, abort
from zerve import variable

# ─── frontend bundle source ─────────────────────────────────────────────
DIST_URL = (
    "https://github.com/anmemol-beta/zerve-odsc-ai-datathon"
    "/releases/download/web-dist/web-dist.tar.gz"
)
WEB_DIR = Path("/tmp/zerve-web-out")
DIST_DIR = WEB_DIR / "dist"
_dist_sha = ""


def fetch_and_extract() -> tuple[int, str]:
    global _dist_sha
    url = f"{DIST_URL}?t={int(time.time())}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "zerve-dash-deploy",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = resp.read()
    sha = hashlib.sha256(payload).hexdigest()[:12]
    if WEB_DIR.exists():
        shutil.rmtree(WEB_DIR)
    WEB_DIR.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tf:
        tf.extractall(WEB_DIR)
    _dist_sha = sha
    return len(payload), sha


def ensure_placeholder() -> None:
    """LB pings GET / every 10s — placeholder index keeps the container in
    rotation if the boot fetch fails."""
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    idx = WEB_DIR / "index.html"
    if not idx.exists():
        idx.write_text(
            "<!doctype html><html><body style='font-family:sans-serif;padding:40px;"
            "background:#020617;color:#e2e8f0'><h2>Frontend bundle not yet fetched.</h2>"
            "<p>POST <code>/admin/refresh</code> to pull the latest from GitHub Releases.</p>"
            "</body></html>"
        )


ensure_placeholder()
try:
    _size, _sha = fetch_and_extract()
    print(f"[boot] frontend bundle: {_size} bytes (sha {_sha})")
except Exception as _e:  # noqa: BLE001 — boot resilience
    print(f"[boot] WARNING: failed to fetch frontend bundle: {_e}")


# ─── Dash app (we use it for the Flask server only — UI is empty) ───────
# `url_base_pathname="/_dash/"` is a hack: it shoves Dash's own routes
# (/_dash-layout, /_dash-dependencies, /_dash-update-component) under
# /_dash/* so they don't collide with our /api/* and the Next.js bundle
# at /. The Dash UI itself is unused, but if we ever want a debug panel
# we can hit /_dash/.
dash_app = Dash(
    __name__,
    url_base_pathname="/_dash/",
    suppress_callback_exceptions=True,
)
dash_app.layout = html.Div("Dash internal — see / for the Next.js frontend.")
server = dash_app.server  # Flask app — gunicorn entry point


# ─── canvas block → variable map ─────────────────────────────────────────
BLOCKS: dict[str, dict[str, str]] = {
    "Example Dataset":         {"events": "events"},
    "EDA Summary":             {"top_events": "top_events", "figure": "fig"},
    "Funnel Stages":           {"user_features": "user_features", "figure": "fig"},
    "Visualize Funnel":        {"figure": "fig"},
    "Build Features":          {"X_train": "X_train", "y_train": "y_train"},
    "Train Model":             {"model": "model"},
    "Visualize Model":         {"figure": "fig"},
    "Funnel v4":               {"user_features_v4": "user_features_v4"},
    "Build Features v3":       {"X_test": "X_v3_test", "y_test": "y_v3_test"},
    "Train Model v3":          {"models": "models_v3", "preds": "preds_v3",
                                "metrics": "metrics_v3"},
    "Validate Events":         {"validation": "events_validation"},
    "Validate Funnel v4":      {"validation": "funnel_v4_validation"},
    "Validate Features v3":    {"validation": "features_v3_validation"},
    "Visualize Cohort":        {"figure": "fig"},
    "Build Strategies":        {"strategies": "strategies",
                                "segments": "strategies_segments"},
    "Diagnose v3":             {"diagnose": "diagnose_v3", "figure": "fig"},
    "SHAP v3":                 {"figure": "fig"},
    "Compare Models":          {"comparison": "model_comparison",
                                "chosen": "chosen_model", "figure": "fig"},
    "Per-Segment Performance": {"segments": "segment_performance_v3", "figure": "fig"},
    "ROI Ranking":             {"actions": "actions_long",
                                "top10": "roi_top10",
                                "per_channel": "roi_per_channel",
                                "per_segment": "roi_per_segment",
                                "figure": "fig"},
    "Strategy Heatmap":        {"data": "strategy_heatmap_data", "figure": "fig"},
    "Insights Card":           {"text": "insights_card_text",
                                "payload": "insights_payload",
                                "figure": "fig"},
    "Train MLP v3":             {"model": "mlp_v3",
                                 "proba": "mlp_proba_v3",
                                 "metrics": "mlp_metrics_v3"},
    "Train GBM v3":             {"model": "gbm_v3",
                                 "proba": "gbm_proba_v3",
                                 "metrics": "gbm_metrics_v3",
                                 "backend": "gbm_backend"},
    "Weekly Data Slices":       {"slices": "weekly_slices",
                                 "summary": "weekly_summary",
                                 "baseline_id": "weekly_baseline_id"},
    "Data Drift Monitor":       {"per_feature": "drift_per_week_per_feature",
                                 "weekly_index": "weekly_drift_index",
                                 "alerts": "drift_alerts",
                                 "figure": "fig"},
    "Load Events Master":       {"events": "events_master",
                                 "meta": "master_meta",
                                 "source": "master_source"},
    "Load Weekly Drop":         {"events": "weekly_drop",
                                 "meta": "weekly_drop_meta",
                                 "status": "status"},
    "Merge Events":             {"events": "events_pipeline",
                                 "data_now": "data_now"},
    "Persist Master":           {"meta": "persist_master_meta", "sha": "sha"},
    "Build Inference Pool":     {"pool": "inference_pool",
                                 "meta": "inference_pool_meta"},
    "Build Training Pool":      {"pool": "training_pool",
                                 "meta": "training_pool_meta",
                                 "gate_passed": "training_gate_passed"},
}


def get(block: str, slot: str) -> Any:
    """Live canvas variable read — no caching, every call re-resolves so
    the page reflects whatever the canvas ran most recently."""
    if block not in BLOCKS:
        abort(404, description=f"unknown block: {block}")
    if slot not in BLOCKS[block]:
        abort(404, description=f"block {block!r} has no slot {slot!r}")
    var_name = BLOCKS[block][slot]
    return variable(block, var_name)


# ─── offline fallback ────────────────────────────────────────────────────
def fallback_json(name: str) -> Any:
    p = DIST_DIR / "api" / name
    if not p.exists():
        abort(
            503,
            description=(
                f"canvas unreachable and offline bundle missing dist/api/{name} "
                "(run `python export_artifacts.py` locally and push to populate)"
            ),
        )
    return json.loads(p.read_text())


def fallback_figure(block: str) -> bytes | None:
    p = DIST_DIR / "figures" / f"{block}.png"
    return p.read_bytes() if p.exists() else None


def try_canvas_then_disk(canvas_fn, disk_name: str) -> Any:
    try:
        return canvas_fn()
    except Exception:
        return fallback_json(disk_name)


def fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def jsonify_value(obj: Any, depth: int = 0) -> Any:
    """Best-effort serializer (capped depth + size) so giant frames or model
    objects don't blow up the response body."""
    if depth > 4:
        return f"<truncated:{type(obj).__name__}>"
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "columns") and hasattr(obj, "to_dict"):
        head = obj.head(50) if hasattr(obj, "head") else obj
        return {
            "_type": "DataFrame",
            "shape": list(getattr(obj, "shape", (0, 0))),
            "columns": list(getattr(obj, "columns", [])),
            "head": head.to_dict(orient="records"),
        }
    if hasattr(obj, "to_dict") and hasattr(obj, "index") and not hasattr(obj, "columns"):
        d = obj.head(50).to_dict() if hasattr(obj, "head") else obj.to_dict()
        return {"_type": "Series",
                "head": {str(k): jsonify_value(v, depth + 1) for k, v in d.items()}}
    if hasattr(obj, "tolist") and hasattr(obj, "shape"):
        if obj.size > 200:
            return {"_type": "ndarray", "shape": list(obj.shape),
                    "head": np.asarray(obj).flatten()[:50].tolist()}
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): jsonify_value(v, depth + 1) for k, v in list(obj.items())[:200]}
    if isinstance(obj, (list, tuple)):
        return [jsonify_value(v, depth + 1) for v in obj[:200]]
    return f"<{type(obj).__name__}>"


# ─── basic ──────────────────────────────────────────────────────────────
@server.route("/health")
def health():
    return jsonify(ok=True)


@server.route("/api/info")
def api_info():
    api_files = (
        sorted(p.name for p in (DIST_DIR / "api").glob("*.json"))
        if (DIST_DIR / "api").exists() else []
    )
    fig_files = (
        sorted(p.name for p in (DIST_DIR / "figures").glob("*.png"))
        if (DIST_DIR / "figures").exists() else []
    )
    return jsonify(
        ok=True,
        service="zerve-dash-funnel-api",
        deploy_type="dash",
        blocks=len(BLOCKS),
        dist_sha=_dist_sha,
        frontend_present=(WEB_DIR / "index.html").exists(),
        offline_bundle={"api_responses": len(api_files), "figures": len(fig_files)},
    )


@server.route("/dag")
def dag():
    return jsonify({block: list(slots.keys()) for block, slots in BLOCKS.items()})


@server.route("/admin/refresh", methods=["POST"])
def admin_refresh():
    """Re-pull the frontend bundle from GitHub Releases without a restart."""
    try:
        size, sha = fetch_and_extract()
    except Exception as e:  # noqa: BLE001 — surface to caller
        return jsonify(ok=False, error=str(e)), 502
    return jsonify(ok=True, bytes=size, sha=sha)


# ─── canvas reads ───────────────────────────────────────────────────────
@server.route("/block/<block>/vars")
def block_vars(block):
    if block not in BLOCKS:
        abort(404, description=f"unknown block: {block}")
    out: dict[str, Any] = {}
    for slot, var_name in BLOCKS[block].items():
        if slot == "figure":
            continue
        try:
            out[slot] = jsonify_value(get(block, slot))
        except Exception as e:  # noqa: BLE001 — boundary, return error per-slot
            out[slot] = {"_error": str(e), "_var": var_name}
    return jsonify(out)


@server.route("/figure/<block>")
def figure(block):
    try:
        fig = get(block, "figure")
        return Response(fig_to_png(fig), mimetype="image/png")
    except Exception:
        png = fallback_figure(block)
        if png is None:
            abort(404, description=f"no live or cached figure for {block}")
        return Response(png, mimetype="image/png")


@server.route("/predict/sample/<int:idx>")
def predict_sample(idx):
    """Live: re-runs the v3 ensemble on the idx-th test row.
    Falls back to dist/api/predict_samples.json if canvas is unreachable
    OR if xgboost is missing in the deploy environment."""
    try:
        X_test = get("Build Features v3", "X_test")
        y_test = get("Build Features v3", "y_test")
        if idx < 0 or idx >= len(X_test):
            abort(404, description=f"idx out of range [0, {len(X_test)})")
        row = X_test.iloc[[idx]] if hasattr(X_test, "iloc") else X_test[idx:idx + 1]
        models = get("Train Model v3", "models")
        probas = np.mean(
            [m.predict_proba(row)[:, 1] for m in models.values()],
            axis=0,
        )
        label = int(y_test.iloc[idx]) if hasattr(y_test, "iloc") else int(y_test[idx])
        return jsonify(
            idx=idx,
            n_test=int(len(X_test)),
            upgrade_probability=float(probas[0]),
            actual_label=label,
            feature_count=int(row.shape[1]),
            source="live",
        )
    except Exception:
        samples = fallback_json("predict_samples.json")
        if idx < 0 or idx >= len(samples):
            abort(404, description=f"idx out of range [0, {len(samples)})")
        out = dict(samples[idx])
        out["source"] = "offline"
        return jsonify(out)


@server.route("/predict", methods=["POST"])
def predict():
    body = request.get_json(silent=True) or {}
    features = body.get("features")
    if not features:
        return jsonify(error="missing 'features' in body"), 400
    models = get("Train Model v3", "models")
    X = np.array(features)
    probas = np.mean(
        [m.predict_proba(X)[:, 1] for m in models.values()],
        axis=0,
    )
    return jsonify(upgrade_probability=probas.tolist())


@server.route("/metrics")
def metrics():
    try:
        df = get("Train Model v3", "metrics")
        return jsonify(df.to_dict(orient="records"))
    except Exception:
        m = fallback_json("metrics.json")
        return jsonify(m["head"] if isinstance(m, dict) and "head" in m else m)


def _df_records(maybe_df: Any) -> Any:
    if hasattr(maybe_df, "to_dict") and hasattr(maybe_df, "columns"):
        return maybe_df.to_dict(orient="records")
    if isinstance(maybe_df, dict) and "head" in maybe_df:
        return maybe_df["head"]
    return maybe_df


@server.route("/strategies")
def strategies():
    return jsonify(try_canvas_then_disk(
        lambda: get("Build Strategies", "strategies"),
        "strategies.json",
    ))


@server.route("/strategies/segments")
def strategy_segments():
    return jsonify(try_canvas_then_disk(
        lambda: get("Build Strategies", "segments"),
        "strategies_segments.json",
    ))


@server.route("/roi/top10")
def roi_top10():
    try:
        return jsonify(get("ROI Ranking", "top10").to_dict(orient="records"))
    except Exception:
        return jsonify(_df_records(fallback_json("roi_top10.json")))


@server.route("/roi/heatmap")
def roi_heatmap():
    try:
        return jsonify(get("Strategy Heatmap", "data").to_dict(orient="records"))
    except Exception:
        return jsonify(_df_records(fallback_json("roi_heatmap.json")))


@server.route("/insights")
def insights():
    try:
        return jsonify(
            text=get("Insights Card", "text"),
            payload=get("Insights Card", "payload"),
            source="live",
        )
    except Exception:
        return jsonify(
            text=fallback_json("insights_text.json"),
            payload=fallback_json("insights_payload.json"),
            source="offline",
        )


@server.route("/drift/data")
def data_drift():
    return jsonify(
        weekly_index=jsonify_value(get("Data Drift Monitor", "weekly_index")),
        alerts=jsonify_value(get("Data Drift Monitor", "alerts")),
        baseline_id=jsonify_value(get("Weekly Data Slices", "baseline_id")),
    )


@server.route("/pipeline/status")
def pipeline_status():
    out = {}
    for slot, fn in [
        ("master_meta", lambda: jsonify_value(get("Load Events Master", "meta"))),
        ("weekly_drop_meta", lambda: jsonify_value(get("Load Weekly Drop", "meta"))),
        ("persist_master", lambda: jsonify_value(get("Persist Master", "meta"))),
        ("inference_pool", lambda: jsonify_value(get("Build Inference Pool", "meta"))),
        ("training_pool", lambda: jsonify_value(get("Build Training Pool", "meta"))),
        ("training_gate_passed", lambda: jsonify_value(get("Build Training Pool", "gate_passed"))),
    ]:
        try:
            out[slot] = fn()
        except Exception as e:  # noqa: BLE001 — boundary
            out[slot] = {"_error": str(e)}
    return jsonify(out)


@server.route("/validate/<block>")
def validate(block):
    return jsonify(jsonify_value(get(block, "validation")))


# ─── static frontend (registered last — every explicit route above wins) ─
# These two routes together replicate FastAPI's `app.mount("/")`.
# Any URL the explicit /api/* routes don't claim falls through to here:
#   /                     → index.html
#   /_next/static/...     → bundled JS/CSS chunks
#   /favicon.ico, /*.png  → public assets
#   /dist/api/*.json      → offline fallback files (if frontend wants them direct)
@server.route("/", defaults={"path": ""})
@server.route("/<path:path>")
def static_files(path):
    target = WEB_DIR / (path or "index.html")
    if target.is_dir():
        target = target / "index.html"
    if not target.exists():
        # SPA fallback — Next.js export uses /404.html, others fall back to /
        candidate = WEB_DIR / "index.html"
        if candidate.exists():
            return send_from_directory(str(WEB_DIR), "index.html")
        abort(404)
    return send_from_directory(str(WEB_DIR), str(target.relative_to(WEB_DIR)))


# ─── entry point ────────────────────────────────────────────────────────
# Two ways to run this on Zerve:
#   gunicorn -w 1 -b 0.0.0.0:8080 app:server   ← preferred (gunicorn imports
#                                                 `server` directly, this
#                                                 block doesn't execute)
#   python app.py                              ← fallback for envs without
#                                                 gunicorn — falls through here
#
# `dash_app.run_server` was renamed to `dash_app.run` in Dash 2.16+.
# Try the new name first, fall back to the old one.
if __name__ == "__main__":
    runner = getattr(dash_app, "run", None) or getattr(dash_app, "run_server")
    runner(host="0.0.0.0", port=8080, debug=False)
