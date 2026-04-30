"""
Zerve Deployment FastAPI — paste this into the deployment editor's main.py.

Run command:  uvicorn main:app --host 0.0.0.0 --port 8080

Serves two things from one container:

  1. The Zerve canvas output API — `zerve.variable(block, var)` resolved
     under /health, /dag, /predict, /figure/{block}, /strategies, etc.
  2. The Next.js static frontend — fetched on boot from a GitHub Release
     (tag = `web-dist`, asset = `web-dist.tar.gz`, auto-built by
     .github/workflows/pages.yml on every push), extracted to /tmp/zerve-web-out,
     and mounted at /. Same-origin → no CORS issues.

`POST /admin/refresh` re-pulls the bundle without a container restart.
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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from zerve import variable

# ─── frontend bundle source ─────────────────────────────────────────────
DIST_URL = (
    "https://github.com/anmemol-beta/zerve-odsc-ai-datathon"
    "/releases/download/web-dist/web-dist.tar.gz"
)
WEB_DIR = Path("/tmp/zerve-web-out")
_dist_sha = ""


def fetch_and_extract() -> tuple[int, str]:
    global _dist_sha
    # Cache-bust the CDN that fronts release downloads.
    url = f"{DIST_URL}?t={int(time.time())}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "zerve-deploy",
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
    """Make sure WEB_DIR has at least an index.html so StaticFiles can mount
    cleanly even if the boot fetch fails. The Zerve LB pings GET / every 10s,
    and a 200 there is what keeps the container in the healthy rotation."""
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    idx = WEB_DIR / "index.html"
    if not idx.exists():
        idx.write_text(
            "<!doctype html><html><body style='font-family:sans-serif;padding:40px;"
            "background:#020617;color:#e2e8f0'><h2>Frontend bundle not yet fetched.</h2>"
            "<p>POST <code>/admin/refresh</code> to pull the latest from GitHub Releases.</p>"
            "</body></html>"
        )


# Try to bring the frontend up at boot — but don't crash the API if it fails.
ensure_placeholder()
try:
    _size, _sha = fetch_and_extract()
    print(f"[boot] frontend bundle: {_size} bytes (sha {_sha})")
except Exception as _e:  # noqa: BLE001 — boot resilience
    print(f"[boot] WARNING: failed to fetch frontend bundle: {_e}")


app = FastAPI(title="Zerve Funnel & Upgrade API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── canvas block → variable map ─────────────────────────────────────────
# Adjust the right-hand var names if your canvas exports them differently.
# The "figure" slot is treated specially: it is fetched via /figure/{block}
# and returns a PNG. Every other slot is JSON-serialized through
# /block/{block}/vars (and a few topic-specific shortcuts below).
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
    # ── AutoML / time-rolling / inference tier ──────────────────────────
    "Train MLP v3":             {"model": "mlp_v3",
                                 "proba": "mlp_proba_v3",
                                 "metrics": "mlp_metrics_v3"},
    "Train GBM v3":             {"model": "gbm_v3",
                                 "proba": "gbm_proba_v3",
                                 "metrics": "gbm_metrics_v3",
                                 "backend": "gbm_backend"},
    "Time-Rolling Splits":      {"splits": "rolling_splits",
                                 "user_signup_month": "user_signup_month"},
    "Train Across Time":        {"rolling_metrics": "rolling_metrics_v3"},
    "Performance Drift":        {"summary": "drift_summary",
                                 "alerts": "drift_alerts",
                                 "figure": "fig"},
    "Champion Selector":        {"per_cohort": "champion_per_cohort",
                                 "win_counts": "win_counts",
                                 "current_champion": "current_champion",
                                 "summary": "champion_summary",
                                 "figure": "fig"},
    "Weekly Data Slices":       {"slices": "weekly_slices",
                                 "summary": "weekly_summary",
                                 "baseline_id": "weekly_baseline_id"},
    "Data Drift Monitor":       {"per_feature": "drift_per_week_per_feature",
                                 "weekly_index": "weekly_drift_index",
                                 "alerts": "drift_alerts",
                                 "figure": "fig"},
    "Persist Models":           {"saved": "saved", "path": "artifacts_path"},
    "Load Models":              {"models": "loaded_models",
                                 "meta": "loaded_meta",
                                 "model_age_hours": "model_age_hours",
                                 "inference_ready": "inference_ready"},
    "Weekly Inference":         {"predictions": "weekly_predictions",
                                 "summary": "weekly_pred_summary",
                                 "by_stage": "weekly_pred_by_stage",
                                 "figure": "fig"},
}


# ─── lazy variable cache (so /admin/reload can bust without restart) ─────
_cache: dict[tuple[str, str], Any] = {}


def get(block: str, slot: str) -> Any:
    if block not in BLOCKS:
        raise HTTPException(404, f"unknown block: {block}")
    if slot not in BLOCKS[block]:
        raise HTTPException(404, f"block {block!r} has no slot {slot!r}")
    var_name = BLOCKS[block][slot]
    key = (block, var_name)
    if key not in _cache:
        _cache[key] = variable(block, var_name)
    return _cache[key]


# ─── offline fallback ────────────────────────────────────────────────────
# When `zerve.variable()` can't reach the canvas (cross-container isolation),
# many endpoints fall back to pre-baked JSON / PNG that `export_artifacts.py`
# wrote to dist/ before the GH Action packed it into web-dist.tar.gz.
DIST_DIR = WEB_DIR / "dist"


def fallback_json(name: str) -> Any:
    p = DIST_DIR / "api" / name
    if not p.exists():
        raise HTTPException(
            503,
            f"canvas unreachable and offline bundle missing dist/api/{name} "
            f"(run `python export_artifacts.py` locally and push to populate)",
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


def jsonify(obj: Any, depth: int = 0) -> Any:
    """Best-effort serializer for arbitrary canvas variables.
    Keeps depth bounded so giant frames / model objects don't OOM the response."""
    if depth > 4:
        return f"<truncated:{type(obj).__name__}>"
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    # pandas DataFrame → records (cap rows)
    if hasattr(obj, "columns") and hasattr(obj, "to_dict"):
        head = obj.head(50) if hasattr(obj, "head") else obj
        return {
            "_type": "DataFrame",
            "shape": list(getattr(obj, "shape", (0, 0))),
            "columns": list(getattr(obj, "columns", [])),
            "head": head.to_dict(orient="records"),
        }
    # pandas Series → dict (cap)
    if hasattr(obj, "to_dict") and hasattr(obj, "index") and not hasattr(obj, "columns"):
        d = obj.head(50).to_dict() if hasattr(obj, "head") else obj.to_dict()
        return {"_type": "Series", "head": {str(k): jsonify(v, depth + 1) for k, v in d.items()}}
    # numpy
    if hasattr(obj, "tolist") and hasattr(obj, "shape"):
        if obj.size > 200:
            return {"_type": "ndarray", "shape": list(obj.shape),
                    "head": np.asarray(obj).flatten()[:50].tolist()}
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): jsonify(v, depth + 1) for k, v in list(obj.items())[:200]}
    if isinstance(obj, (list, tuple)):
        return [jsonify(v, depth + 1) for v in obj[:200]]
    # scikit-learn / xgboost models, etc.
    return f"<{type(obj).__name__}>"


# ─── basic ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/info")
def api_info():
    api_files = sorted(p.name for p in (DIST_DIR / "api").glob("*.json")) if (DIST_DIR / "api").exists() else []
    fig_files = sorted(p.name for p in (DIST_DIR / "figures").glob("*.png")) if (DIST_DIR / "figures").exists() else []
    return {
        "ok": True,
        "service": "zerve-funnel-api",
        "blocks": len(BLOCKS),
        "dist_sha": _dist_sha,
        "frontend_present": (WEB_DIR / "index.html").exists(),
        "offline_bundle": {
            "api_responses": len(api_files),
            "figures": len(fig_files),
        },
    }


@app.get("/dag")
def dag():
    """Block list + their slot keys. Frontend uses this to draw the canvas."""
    return {
        block: list(slots.keys())
        for block, slots in BLOCKS.items()
    }


@app.post("/admin/reload")
def admin_reload():
    """Clear the in-process cache of zerve.variable() values. Use after the
    canvas re-runs a block so the next API call sees fresh outputs."""
    _cache.clear()
    return {"ok": True, "cleared": True}


@app.post("/admin/refresh")
def admin_refresh():
    """Re-pull the frontend bundle from GitHub Releases without a restart.
    StaticFiles re-reads the filesystem on every request, so the new files
    are served immediately."""
    try:
        size, sha = fetch_and_extract()
    except Exception as e:  # noqa: BLE001 — surface to caller
        raise HTTPException(502, f"refresh failed: {e}")
    return {"ok": True, "bytes": size, "sha": sha}


# ─── generic per-block introspection ────────────────────────────────────
@app.get("/block/{block}/vars")
def block_vars(block: str):
    """Resolve every non-figure slot of a block to a JSON-friendly preview.
    Errors per-slot don't fail the whole response."""
    if block not in BLOCKS:
        raise HTTPException(404, f"unknown block: {block}")
    out: dict[str, Any] = {}
    for slot, var_name in BLOCKS[block].items():
        if slot == "figure":
            continue
        try:
            v = get(block, slot)
            out[slot] = jsonify(v)
        except Exception as e:  # noqa: BLE001 — boundary, return error per-slot
            out[slot] = {"_error": str(e), "_var": var_name}
    return out


# ─── figures ────────────────────────────────────────────────────────────
@app.get("/figure/{block}")
def figure(block: str):
    try:
        fig = get(block, "figure")
        return Response(fig_to_png(fig), media_type="image/png")
    except Exception:
        png = fallback_figure(block)
        if png is None:
            raise HTTPException(404, f"no live or cached figure for {block}")
        return Response(png, media_type="image/png")


# ─── prediction ─────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    features: list[list[float]]


@app.post("/predict")
def predict(req: PredictRequest):
    """Calibrated v3 ensemble — averages predict_proba across the 3 folds."""
    models = get("Train Model v3", "models")
    X = np.array(req.features)
    probas = np.mean(
        [m.predict_proba(X)[:, 1] for m in models.values()],
        axis=0,
    )
    return {"upgrade_probability": probas.tolist()}


@app.get("/predict/sample/{idx}")
def predict_sample(idx: int):
    """Predict on the idx-th test-set row. Tries the live canvas first;
    falls back to dist/api/predict_samples.json that export_artifacts.py
    pre-baked from the same model."""
    try:
        X_test = get("Build Features v3", "X_test")
        y_test = get("Build Features v3", "y_test")
        if idx < 0 or idx >= len(X_test):
            raise HTTPException(404, f"idx out of range [0, {len(X_test)})")
        row = X_test.iloc[[idx]] if hasattr(X_test, "iloc") else X_test[idx:idx + 1]
        models = get("Train Model v3", "models")
        probas = np.mean(
            [m.predict_proba(row)[:, 1] for m in models.values()],
            axis=0,
        )
        label = int(y_test.iloc[idx]) if hasattr(y_test, "iloc") else int(y_test[idx])
        return {
            "idx": idx,
            "n_test": int(len(X_test)),
            "upgrade_probability": float(probas[0]),
            "actual_label": label,
            "feature_count": int(row.shape[1]),
        }
    except HTTPException:
        raise
    except Exception:
        samples = fallback_json("predict_samples.json")
        if idx < 0 or idx >= len(samples):
            raise HTTPException(404, f"idx out of range [0, {len(samples)})")
        return samples[idx]


@app.get("/metrics")
def metrics():
    try:
        df = get("Train Model v3", "metrics")
        return df.to_dict(orient="records")
    except Exception:
        m = fallback_json("metrics.json")
        # JSON-baked DataFrame snapshot uses {"_type":"DataFrame","head":[…]}
        return m["head"] if isinstance(m, dict) and "head" in m else m


# ─── strategies / insights ──────────────────────────────────────────────
def _df_records(maybe_df: Any) -> Any:
    if hasattr(maybe_df, "to_dict") and hasattr(maybe_df, "columns"):
        return maybe_df.to_dict(orient="records")
    if isinstance(maybe_df, dict) and "head" in maybe_df:
        return maybe_df["head"]
    return maybe_df


@app.get("/strategies")
def strategies():
    return try_canvas_then_disk(
        lambda: get("Build Strategies", "strategies"),
        "strategies.json",
    )


@app.get("/strategies/segments")
def strategy_segments():
    return try_canvas_then_disk(
        lambda: get("Build Strategies", "segments"),
        "strategies_segments.json",
    )


@app.get("/roi/top10")
def roi_top10():
    try:
        return get("ROI Ranking", "top10").to_dict(orient="records")
    except Exception:
        return _df_records(fallback_json("roi_top10.json"))


@app.get("/roi/heatmap")
def roi_heatmap():
    try:
        return get("Strategy Heatmap", "data").to_dict(orient="records")
    except Exception:
        return _df_records(fallback_json("roi_heatmap.json"))


@app.get("/insights")
def insights():
    try:
        return {
            "text": get("Insights Card", "text"),
            "payload": get("Insights Card", "payload"),
        }
    except Exception:
        return {
            "text": fallback_json("insights_text.json"),
            "payload": fallback_json("insights_payload.json"),
        }


# ─── AutoML / champion / drift shortcuts ────────────────────────────────
@app.get("/champion")
def champion():
    """Currently-selected production model + win counts + per-cohort table."""
    return {
        "current": get("Champion Selector", "current_champion"),
        "summary": jsonify(get("Champion Selector", "summary")),
        "win_counts": jsonify(get("Champion Selector", "win_counts")),
        "per_cohort": jsonify(get("Champion Selector", "per_cohort")),
    }


@app.get("/rolling/metrics")
def rolling_metrics():
    df = get("Train Across Time", "rolling_metrics")
    return df.to_dict(orient="records")


@app.get("/drift/performance")
def perf_drift():
    return {
        "summary": jsonify(get("Performance Drift", "summary")),
        "alerts": jsonify(get("Performance Drift", "alerts")),
    }


@app.get("/drift/data")
def data_drift():
    return {
        "weekly_index": jsonify(get("Data Drift Monitor", "weekly_index")),
        "alerts": jsonify(get("Data Drift Monitor", "alerts")),
        "baseline_id": jsonify(get("Weekly Data Slices", "baseline_id")),
    }


@app.get("/inference/weekly")
def weekly_inference():
    return {
        "summary": jsonify(get("Weekly Inference", "summary")),
        "by_stage": jsonify(get("Weekly Inference", "by_stage")),
    }


# ─── validations (for the "is this canvas healthy?" badges) ─────────────
@app.get("/validate/{block}")
def validate(block: str):
    return get(block, "validation")


# ─── static frontend ────────────────────────────────────────────────────
# MOUNTED LAST so every explicit route above takes precedence. StaticFiles
# matches whatever the explicit routes don't claim — index.html for /,
# _next/* for the JS chunks, etc.
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="frontend")
