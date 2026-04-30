"""
FastAPI wrapper for the Next.js static export.

Zerve Hosted Apps deploys Python archives, so we wrap the static `web/out/`
into a 5-line FastAPI app. Run locally with:

    uv run uvicorn server:app --reload --port 8000

For Zerve deploy, archive { server.py, web/out/, requirements.txt } and upload.
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "web" / "out"

app = FastAPI(title="Zerve Funnel & Upgrade Predictor")

if not STATIC.exists():
    raise RuntimeError(
        f"Static build missing at {STATIC}. Run `cd web && npm run build` first."
    )

app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
