"""
Zerve Custom Deployment entry.

The deployment container is sealed: only this file is mounted at /app/main.py;
the project's File System assets (app.zip, CSVs) are NOT visible at runtime.
So we fetch the prebuilt static bundle from GitHub on boot, extract it into
/tmp, and serve it via FastAPI's StaticFiles mount.

Update ZIP_URL whenever app.zip changes on GitHub.
"""
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ZIP_URL = "https://raw.githubusercontent.com/anmemol-beta/zerve-odsc-ai-datathon/main/app.zip"
EXTRACT_DIR = Path("/tmp/zerve-app")

print(f"[boot] downloading {ZIP_URL}")
req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "zerve-deploy"})
with urllib.request.urlopen(req, timeout=60) as resp:
    payload = resp.read()
print(f"[boot] got {len(payload)} bytes")

if EXTRACT_DIR.exists():
    shutil.rmtree(EXTRACT_DIR)
EXTRACT_DIR.mkdir(parents=True)

with zipfile.ZipFile(io.BytesIO(payload)) as z:
    z.extractall(EXTRACT_DIR)
print(f"[boot] extracted to {EXTRACT_DIR}")

STATIC = EXTRACT_DIR / "web" / "out"
assert STATIC.exists(), f"static dir missing after extract: {STATIC}"

app = FastAPI(title="Zerve Funnel & Upgrade Predictor")
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
