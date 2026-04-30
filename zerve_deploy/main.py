"""
Zerve Deployment FastAPI — paste this into the deployment editor's main.py.

Run command:  uvicorn main:app --host 0.0.0.0 --port 8080

Reads canvas block outputs via `zerve.variable(block_name, var_name)` and
exposes them to the standalone Next.js frontend.
"""
import io
from typing import Any

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from zerve import variable

app = FastAPI(title="Zerve Funnel & Upgrade API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── canvas block → variable map ─────────────────────────────────────────
# Adjust the right-hand var names if your canvas exports them differently.
BLOCKS: dict[str, dict[str, str]] = {
    "Example Dataset":         {"events": "events"},
    "EDA Summary":             {"top_events": "top_events"},
    "Funnel Stages":           {"user_features": "user_features"},
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
                                "chosen": "chosen_model"},
    "Per-Segment Performance": {"segments": "segment_performance_v3"},
    "ROI Ranking":             {"actions": "actions_long",
                                "top10": "roi_top10",
                                "per_channel": "roi_per_channel",
                                "per_segment": "roi_per_segment"},
    "Strategy Heatmap":        {"data": "strategy_heatmap_data"},
    "Insights Card":           {"text": "insights_card_text",
                                "payload": "insights_payload",
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


def fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# ─── basic ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/dag")
def dag():
    """Block list + their slot keys. Frontend uses this to draw the canvas."""
    return {
        block: list(slots.keys())
        for block, slots in BLOCKS.items()
    }


@app.post("/admin/reload")
def reload():
    _cache.clear()
    return {"ok": True, "cleared": True}


# ─── figures ────────────────────────────────────────────────────────────
@app.get("/figure/{block}")
def figure(block: str):
    fig = get(block, "figure")
    return Response(fig_to_png(fig), media_type="image/png")


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
    """Predict on the idx-th test-set row — frontend uses this to demo
    end-to-end inference without needing to reconstruct the full feature vector."""
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


@app.get("/metrics")
def metrics():
    df = get("Train Model v3", "metrics")
    return df.to_dict(orient="records")


# ─── strategies / insights ──────────────────────────────────────────────
@app.get("/strategies")
def strategies():
    return get("Build Strategies", "strategies")


@app.get("/strategies/segments")
def strategy_segments():
    return get("Build Strategies", "segments")


@app.get("/roi/top10")
def roi_top10():
    return get("ROI Ranking", "top10").to_dict(orient="records")


@app.get("/roi/heatmap")
def roi_heatmap():
    return get("Strategy Heatmap", "data").to_dict(orient="records")


@app.get("/insights")
def insights():
    return {
        "text": get("Insights Card", "text"),
        "payload": get("Insights Card", "payload"),
    }


# ─── validations (for the "is this canvas healthy?" badges) ─────────────
@app.get("/validate/{block}")
def validate(block: str):
    return get(block, "validation")
