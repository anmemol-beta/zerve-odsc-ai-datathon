"""Load Models — head of the INFERENCE tier.

Reads the artifact bundle Persist Models wrote. Tries local /tmp first;
if that's empty (serverless cold start, scheduled training hasn't run
yet), falls back to fetching the last-committed artifacts from this
repo's GitHub raw URL — same cache-first / network-fallback pattern
the Build Strategies block uses.

Outputs:
    loaded_models       dict — {model_name: object_with_predict_proba}
    loaded_meta         dict — meta.json contents
    model_age_hours     float — how stale is the champion?
    inference_ready     bool  — True only when champion model loaded OK
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import joblib

ARTIFACTS = Path("/tmp/zerve-models/v3")
GITHUB_RAW = (
    "https://raw.githubusercontent.com/"
    "anmemol-beta/zerve-odsc-ai-datathon/main/models/v3"
)


def _http_get(url: str, timeout: int = 30) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def _try_local_or_remote(name: str) -> Path | None:
    local = ARTIFACTS / name
    if local.exists():
        return local
    try:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        data = _http_get(f"{GITHUB_RAW}/{name}")
        local.write_bytes(data)
        print(f"  ↓ fetched {name} from github raw ({len(data)/1024:.1f} KB)")
        return local
    except Exception as e:
        print(f"  ✗ {name} not in /tmp and github fetch failed: {e}")
        return None


# ─── 1. read meta ───────────────────────────────────────────────────────
print(f"[load] checking {ARTIFACTS}")
meta_path = _try_local_or_remote("meta.json")
if meta_path is None:
    print("[load] no meta.json — Persist Models has never run AND github raw "
          "doesn't have models/v3/meta.json")
    print("[load] inference will fall back to whatever is already in namespace")
    loaded_models = {}
    loaded_meta = {"current_champion": None, "trained_at": None}
    model_age_hours = float("inf")
    inference_ready = False
else:
    loaded_meta = json.loads(meta_path.read_text())
    print(f"[load] meta.json: champion={loaded_meta.get('current_champion')}, "
          f"trained_at={loaded_meta.get('trained_at')}")

    trained = loaded_meta.get("trained_at")
    if trained:
        try:
            ts = datetime.fromisoformat(trained.replace("Z", "+00:00"))
            model_age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        except Exception:
            model_age_hours = float("nan")
    else:
        model_age_hours = float("nan")

    # ─── 2. load model artifacts ────────────────────────────────────────
    loaded_models = {}
    for name in ["models_v3.joblib", "gbm_v3.joblib", "mlp_v3.joblib"]:
        path = _try_local_or_remote(name)
        if path is None:
            continue
        try:
            obj = joblib.load(path)
            key = name.replace(".joblib", "")
            loaded_models[key] = obj
            print(f"  ✓ loaded {name}")
        except Exception as e:
            print(f"  ✗ {name} failed to unpickle: {e}")

    # try torch state-dict bundle as MLP fallback
    if "mlp_v3" not in loaded_models:
        torch_bundle_path = _try_local_or_remote("mlp_v3_torch.pt")
        if torch_bundle_path is not None:
            try:
                import torch
                bundle = torch.load(torch_bundle_path, map_location="cpu", weights_only=False)
                print(f"  ✓ loaded mlp_v3_torch.pt (state-dict bundle, "
                      f"n_features={bundle.get('n_features')})")
                loaded_models["mlp_v3_state"] = bundle
            except Exception as e:
                print(f"  ✗ torch state-dict bundle failed to load: {e}")

    inference_ready = "models_v3" in loaded_models or "gbm_v3" in loaded_models

# ─── 3. report ──────────────────────────────────────────────────────────
print()
print("=" * 60)
print("INFERENCE TIER — LOAD MODELS")
print("=" * 60)
print(f"  champion         : {loaded_meta.get('current_champion', '(unknown)')}")
print(f"  trained_at       : {loaded_meta.get('trained_at', '(unknown)')}")
print(f"  age (hours)      : {model_age_hours:.1f}" if model_age_hours == model_age_hours else "  age (hours)      : ?")
print(f"  loaded models    : {list(loaded_models.keys())}")
print(f"  inference_ready  : {inference_ready}")
print()
if model_age_hours == model_age_hours and model_age_hours > 168:
    print(f"⚠ models are >{int(model_age_hours/24)} days old — recommend retrain")
elif not inference_ready:
    print("⚠ no usable models loaded — schedule Persist Models or commit "
          "models/v3/ to repo")
else:
    print("✓ ready for inference")
