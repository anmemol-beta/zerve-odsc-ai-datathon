"""Persist Models — checkpoint trained artifacts for the inference tier.

End of the TRAIN tier. Saves every candidate model (the v3 ensemble + its
3 base models, the GBM/sklearn-GBM stand-in, and the MLP) to a known path,
plus a `meta.json` recording the champion pick + key metrics + training
timestamp.

The Inference tier (Load Models + Weekly Inference) reads from this path
on demand. That is what lets training run on a weekly cron while user-
facing inference stays sub-second.

Persistence target:
    /tmp/zerve-models/v3/
        ensemble_v3.joblib       — calibrated XGB+RF+HGB voting wrapper
        models_v3.joblib         — full dict including all 3 base models
        gbm_v3.joblib            — sklearn GradientBoosting (or catboost) wrapper
        mlp_v3_state.joblib      — MLP + scaler + isotonic (sklearn path) OR
                                   torch state-dict bundle (torch path)
        meta.json                — champion + metrics + trained_at + features

Inputs (from canvas namespace):
    models_v3, ensemble_proba_v3   (Train Model v3)
    gbm_v3, gbm_metrics_v3, gbm_backend  (Train GBM v3)
    mlp_v3, mlp_metrics_v3         (Train MLP v3)
    feature_cols_v3                (Build Features v3)
    current_champion, champion_summary  (Champion Selector)

Outputs:
    artifacts_path     str   — directory we wrote to
    artifacts_meta     dict  — same content as meta.json
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

ARTIFACTS = Path("/tmp/zerve-models/v3")
ARTIFACTS.mkdir(parents=True, exist_ok=True)

# ─── 1. save sklearn-style models with joblib ────────────────────────────
saved = []
errors = []


def _save_safe(obj, name: str):
    try:
        joblib.dump(obj, ARTIFACTS / name, compress=3)
        saved.append(name)
        size_kb = (ARTIFACTS / name).stat().st_size / 1024
        print(f"  ✓ saved {name:<32} {size_kb:>8.1f} KB")
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"  ✗ {name} skipped ({e})")


print(f"[persist] writing artifacts to {ARTIFACTS}")
_save_safe(models_v3,  "models_v3.joblib")           # all base models
_save_safe(gbm_v3,     "gbm_v3.joblib")              # GBM wrapper
# MLP — try joblib first; if that fails (e.g., torch wrapper not picklable),
# fall back to saving torch state dict + scaler + isotonic params separately.
try:
    joblib.dump(mlp_v3, ARTIFACTS / "mlp_v3.joblib", compress=3)
    saved.append("mlp_v3.joblib")
    print(f"  ✓ saved mlp_v3.joblib (joblib)")
except Exception as joblib_err:
    print(f"  joblib(mlp_v3) failed ({joblib_err}); trying torch state-dict bundle")
    try:
        import torch
        bundle = {
            "state_dict": mlp_v3.model.state_dict(),
            "scaler_mean": mlp_v3.scaler.mean_,
            "scaler_scale": mlp_v3.scaler.scale_,
            "iso_X": mlp_v3.iso.X_thresholds_,
            "iso_y": mlp_v3.iso.y_thresholds_,
            "n_features": len(feature_cols_v3),
        }
        torch.save(bundle, ARTIFACTS / "mlp_v3_torch.pt")
        saved.append("mlp_v3_torch.pt")
        print(f"  ✓ saved mlp_v3_torch.pt (torch state_dict bundle)")
    except Exception as torch_err:
        errors.append(f"mlp_v3: joblib failed ({joblib_err}); torch failed ({torch_err})")
        print(f"  ✗ mlp_v3 skipped both paths")


# ─── 2. write metadata ───────────────────────────────────────────────────
def _serialize_metrics(d):
    return {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
            for k, v in d.items() if not callable(v)}


metrics_v3_dict = (
    metrics_v3.set_index("model").to_dict(orient="index")
    if hasattr(metrics_v3, "set_index") else dict(metrics_v3)
)

artifacts_meta = {
    "trained_at": datetime.now(timezone.utc).isoformat(),
    "feature_cols": list(feature_cols_v3),
    "n_features": len(feature_cols_v3),
    "current_champion": current_champion,
    "champion_summary": {
        k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
        for k, v in champion_summary.items() if not isinstance(v, dict)
    },
    "v3_metrics": metrics_v3_dict,
    "gbm_metrics": _serialize_metrics(gbm_metrics_v3),
    "mlp_metrics": _serialize_metrics(mlp_metrics_v3),
    "saved_files": saved,
    "errors": errors,
    "artifacts_path": str(ARTIFACTS),
}

(ARTIFACTS / "meta.json").write_text(
    json.dumps(artifacts_meta, indent=2, default=str)
)
print(f"  ✓ saved meta.json")
print()
print(f"[persist] {len(saved)} files written; {len(errors)} errors")
print(f"          champion = {current_champion}")
print(f"          trained_at = {artifacts_meta['trained_at']}")

artifacts_path = str(ARTIFACTS)

# ─── 3. summary report ───────────────────────────────────────────────────
print()
print("=" * 70)
print("ARTIFACTS REGISTRY")
print("=" * 70)
total_kb = sum((ARTIFACTS / f).stat().st_size for f in os.listdir(ARTIFACTS)) / 1024
print(f"  total size : {total_kb:.1f} KB across {len(os.listdir(ARTIFACTS))} files")
print(f"  path       : {ARTIFACTS}")
print()
for f in sorted(os.listdir(ARTIFACTS)):
    fp = ARTIFACTS / f
    print(f"  {f:<32} {fp.stat().st_size / 1024:>8.1f} KB")
print()
print("Note: in serverless runtimes /tmp is ephemeral. To persist across runs,")
print("schedule this block to commit /tmp/zerve-models to a known artifact bucket")
print("(or to git via a separate Action) on a weekly cron.")
