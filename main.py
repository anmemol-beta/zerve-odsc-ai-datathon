"""
Zerve Custom Deployment entry.

The deployment container is sealed: only this file is mounted at /app/main.py;
the project's File System assets (app.zip, CSVs) are NOT visible at runtime.
So we fetch the prebuilt static bundle from GitHub on boot, extract it into
/tmp, and serve it via FastAPI's StaticFiles mount.

POST /admin/refresh re-pulls the zip without a container restart, so a
fresh `./build-archive.sh && curl -X POST .../admin/refresh` cycle gives
zero-downtime deploys after the initial Zerve setup.
"""
import hashlib
import io
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

ZIP_URL = "https://raw.githubusercontent.com/anmemol-beta/zerve-odsc-ai-datathon/main/app.zip"
EXTRACT_DIR = Path("/tmp/zerve-app")
STATIC = EXTRACT_DIR / "web" / "out"

current_sha: str = ""


def fetch_and_extract() -> tuple[int, str]:
    global current_sha
    # Bust the Fastly POP cache that fronts raw.githubusercontent.com — without
    # this, /admin/refresh keeps returning the previous build for ~5 minutes
    # after each push (different egress regions hit different cached objects).
    url = f"{ZIP_URL}?t={int(time.time())}"
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

    if EXTRACT_DIR.exists():
        shutil.rmtree(EXTRACT_DIR)
    EXTRACT_DIR.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        z.extractall(EXTRACT_DIR)
    current_sha = sha
    return len(payload), sha


print(f"[boot] downloading {ZIP_URL}")
size, sha = fetch_and_extract()
print(f"[boot] got {size} bytes (sha {sha}), extracted to {EXTRACT_DIR}")
assert STATIC.exists(), f"static dir missing after extract: {STATIC}"

app = FastAPI(title="Zerve Funnel & Upgrade Predictor")


@app.get("/admin/version")
def version():
    return {"sha": current_sha, "static": str(STATIC)}


@app.post("/admin/refresh")
def refresh():
    size, sha = fetch_and_extract()
    print(f"[refresh] got {size} bytes (sha {sha})")
    return {"ok": True, "bytes": size, "sha": sha}


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
