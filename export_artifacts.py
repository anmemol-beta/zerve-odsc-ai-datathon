#!/usr/bin/env python3
"""
Export everything the FastAPI deployment needs into `models/v3/` (joblib bundles,
matching the Load Models block fallback URL) and `dist/` (pre-baked JSON + PNG
that the deployment serves whenever `zerve.variable()` access is blocked).

Runs the canvas Development layer in topo order against the local
`datas/zerve_events.csv`, then snapshots the resulting in-process namespace.

Usage:
    uv run python export_artifacts.py
    uv run python export_artifacts.py --until "Train Model v3"   # partial bundle
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import joblib
import yaml

REPO_ROOT = Path(__file__).resolve().parent
DATAS_DIR = REPO_ROOT / "datas"
MODELS_DIR = REPO_ROOT / "models" / "v3"
DIST_DIR = REPO_ROOT / "dist"
API_DIR = DIST_DIR / "api"
FIG_DIR = DIST_DIR / "figures"

if sys.platform == "darwin":
    libomp = Path("/opt/homebrew/opt/libomp/lib")
    if libomp.exists():
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
            str(libomp) + ":" + os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        )

# Force non-interactive matplotlib so plt.show() in canvas blocks doesn't pop windows.
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.show = lambda *a, **k: None  # type: ignore[assignment]


def _find_canvas() -> Path:
    for p in REPO_ROOT.iterdir():
        if p.is_dir() and (p / "canvas.yaml").exists() and p.name not in {".git", ".venv"}:
            return p
    sys.exit("no canvas.yaml found at repo root")


def _topo(blocks: list[dict], edges: list[dict]) -> list[dict]:
    by_id = {b["id"]: b for b in blocks}
    incoming = {b["id"]: 0 for b in blocks}
    children: dict[str, list[str]] = {b["id"]: [] for b in blocks}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in by_id and t in by_id:
            incoming[t] += 1
            children[s].append(t)
    ready = [bid for bid, n in incoming.items() if n == 0]
    out: list[dict] = []
    while ready:
        ready.sort(key=lambda bid: (by_id[bid].get("y", 0), by_id[bid].get("x", 0)))
        bid = ready.pop(0)
        out.append(by_id[bid])
        for c in children[bid]:
            incoming[c] -= 1
            if incoming[c] == 0:
                ready.append(c)
    if len(out) != len(blocks):
        sys.exit("cycle detected")
    return out


# ─── what to dump ────────────────────────────────────────────────────────
# Maps namespace variable name → output strategy.
JOBLIB_DUMPS = [
    ("models_v3",  MODELS_DIR / "models_v3.joblib"),
    ("gbm_v3",     MODELS_DIR / "gbm_v3.joblib"),
    ("mlp_v3",     MODELS_DIR / "mlp_v3.joblib"),
]

# (variable_name, dist/api/<filename>.json) — variables jsonified via best-effort serializer
JSON_DUMPS: list[tuple[str, str]] = [
    ("metrics_v3",                 "metrics.json"),
    ("strategies",                 "strategies.json"),
    ("strategies_segments",        "strategies_segments.json"),
    ("roi_top10",                  "roi_top10.json"),
    ("roi_per_channel",            "roi_per_channel.json"),
    ("roi_per_segment",            "roi_per_segment.json"),
    ("strategy_heatmap_data",      "roi_heatmap.json"),
    ("insights_card_text",         "insights_text.json"),
    ("insights_payload",           "insights_payload.json"),
    ("model_comparison",           "model_comparison.json"),
    ("chosen_model",               "chosen_model.json"),
    ("segment_performance_v3",     "per_segment_performance.json"),
    ("events_validation",          "events_validation.json"),
    ("funnel_v4_validation",       "funnel_v4_validation.json"),
    ("features_v3_validation",     "features_v3_validation.json"),
    ("current_champion",           "champion_current.json"),
    ("champion_summary",           "champion_summary.json"),
    ("rolling_metrics_v3",         "rolling_metrics.json"),
    ("drift_summary",              "perf_drift_summary.json"),
    ("drift_alerts",               "perf_drift_alerts.json"),
    ("weekly_drift_index",         "data_drift_weekly_index.json"),
    ("weekly_pred_summary",        "weekly_pred_summary.json"),
    ("weekly_pred_by_stage",       "weekly_pred_by_stage.json"),
    ("top_events",                 "top_events.json"),
]

# Per-block figure snapshot. After block N runs, if `fig` is in namespace, save it.
FIG_BLOCKS = [
    "EDA Summary", "Funnel Stages", "Visualize Funnel", "Visualize Cohort",
    "Visualize Model", "Compare Models", "Diagnose v3", "SHAP v3",
    "Per-Segment Performance", "ROI Ranking", "Strategy Heatmap",
    "Performance Drift", "Champion Selector", "Data Drift Monitor",
    "Weekly Inference", "Insights Card",
]


def _jsonify(obj: Any, depth: int = 0) -> Any:
    """Same serializer the deployment uses."""
    if depth > 4:
        return f"<truncated:{type(obj).__name__}>"
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "columns") and hasattr(obj, "to_dict"):
        head = obj.head(500) if hasattr(obj, "head") else obj
        return {
            "_type": "DataFrame",
            "shape": list(getattr(obj, "shape", (0, 0))),
            "columns": list(getattr(obj, "columns", [])),
            "head": head.to_dict(orient="records"),
        }
    if hasattr(obj, "to_dict") and hasattr(obj, "index") and not hasattr(obj, "columns"):
        d = obj.head(500).to_dict() if hasattr(obj, "head") else obj.to_dict()
        return {"_type": "Series", "head": {str(k): _jsonify(v, depth + 1) for k, v in d.items()}}
    if hasattr(obj, "tolist") and hasattr(obj, "shape"):
        if obj.size > 1000:
            import numpy as np
            return {"_type": "ndarray", "shape": list(obj.shape),
                    "head": np.asarray(obj).flatten()[:500].tolist()}
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): _jsonify(v, depth + 1) for k, v in list(obj.items())[:1000]}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v, depth + 1) for v in obj[:1000]]
    return f"<{type(obj).__name__}>"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default=None,
                    help="Stop after this block (skip the AutoML / inference tier if you only need core artifacts).")
    ap.add_argument("--layer", default="Development")
    args = ap.parse_args()

    canvas_dir = _find_canvas()
    canvas = yaml.safe_load((canvas_dir / "canvas.yaml").read_text())
    layer = next(L for L in canvas["layers"] if L["name"] == args.layer)
    ordered = _topo(layer["blocks"], layer.get("edges") or [])

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    API_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # Same dataset cwd shim run_local.py uses.
    if DATAS_DIR.exists():
        os.chdir(DATAS_DIR)

    layer_dir = canvas_dir / args.layer
    namespace: dict = {"__name__": "__main__"}
    prelude = (canvas.get("python_global_imports") or "").strip()
    if prelude:
        exec(compile(prelude, "<global_imports>", "exec"), namespace)

    for b in ordered:
        if b.get("type") != 1:  # skip markdown
            continue
        name = b["name"]
        block_path = layer_dir / f"{name}.py"
        if not block_path.exists():
            print(f"  [skip] {name}: source missing")
            if args.until == name:
                break
            continue
        print(f"\n===== {name} =====", flush=True)
        try:
            exec(compile(block_path.read_text(), str(block_path), "exec"), namespace)
        except Exception as e:
            print(f"  [block failed] {name}: {e}")
            traceback.print_exc()

        # Per-block figure snapshot.
        if name in FIG_BLOCKS and "fig" in namespace:
            fig = namespace.get("fig")
            try:
                safe = name.replace("/", "_")
                out = FIG_DIR / f"{safe}.png"
                fig.savefig(out, dpi=120, bbox_inches="tight")
                print(f"  ✓ saved figure → {out.relative_to(REPO_ROOT)}")
            except Exception as e:
                print(f"  ✗ figure save failed for {name}: {e}")
            namespace["fig"] = None  # don't carry over to next block
        plt.close("all")

        if args.until == name:
            break

    # ── 2. dump joblib models ──────────────────────────────────────────
    print("\n===== joblib dumps =====")
    saved_models = []
    for var, out in JOBLIB_DUMPS:
        if var in namespace and namespace[var] is not None:
            try:
                joblib.dump(namespace[var], out, compress=3)
                kb = out.stat().st_size / 1024
                print(f"  ✓ {out.relative_to(REPO_ROOT)} ({kb:.1f} KB)")
                saved_models.append(out.name)
            except Exception as e:
                print(f"  ✗ {var}: {e}")
        else:
            print(f"  - {var}: not in namespace")

    # ── 3. write meta.json (Load Models block expects this) ───────────
    meta = {
        "current_champion": namespace.get("current_champion") or "ensemble_v3",
        "trained_at": namespace.get("trained_at_iso")
                      or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "saved_models": saved_models,
        "metrics": _jsonify(namespace.get("metrics_v3")),
    }
    (MODELS_DIR / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    print(f"  ✓ {(MODELS_DIR / 'meta.json').relative_to(REPO_ROOT)}")

    # ── 4. dump JSON snapshots for the deployment fallback path ────────
    print("\n===== json dumps (dist/api/) =====")
    for var, fname in JSON_DUMPS:
        path = API_DIR / fname
        if var in namespace and namespace[var] is not None:
            try:
                payload = _jsonify(namespace[var])
                path.write_text(json.dumps(payload, indent=2, default=str))
                kb = path.stat().st_size / 1024
                print(f"  ✓ {path.relative_to(REPO_ROOT)} ({kb:.1f} KB)")
            except Exception as e:
                print(f"  ✗ {var}: {e}")
        else:
            print(f"  - {var}: not in namespace")

    # ── 5. predict_sample fallback — bake N test rows + their proba ────
    if all(k in namespace for k in ("X_v3_test", "y_v3_test", "models_v3")):
        try:
            import numpy as np
            Xt = namespace["X_v3_test"]
            yt = namespace["y_v3_test"]
            models = namespace["models_v3"]
            n = min(2000, len(Xt))
            probas = np.mean(
                [m.predict_proba(Xt.iloc[:n] if hasattr(Xt, "iloc") else Xt[:n])[:, 1]
                 for m in models.values()],
                axis=0,
            )
            preds = [
                {
                    "idx": i,
                    "n_test": int(len(Xt)),
                    "upgrade_probability": float(probas[i]),
                    "actual_label": int(yt.iloc[i] if hasattr(yt, "iloc") else yt[i]),
                    "feature_count": int(Xt.shape[1]),
                }
                for i in range(n)
            ]
            (API_DIR / "predict_samples.json").write_text(json.dumps(preds))
            print(f"  ✓ dist/api/predict_samples.json ({n} rows)")
        except Exception as e:
            print(f"  ✗ predict_samples bake failed: {e}")

    print("\nDone. Commit `models/v3/` and `dist/` to ship the offline fallback bundle.")


if __name__ == "__main__":
    main()
