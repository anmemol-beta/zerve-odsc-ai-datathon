# Zerve × ODSC AI Datathon

**Live demo**: <https://beta-zerve.hub.zerve.cloud>

Canvas: **Beta** → Layer: **Development**. Two parallel pipelines after EDA.

```
Example Dataset    (slim load — 3 cols, pyarrow, ISO8601, category dtype)
   └─► EDA Summary
         ├─► Funnel Stages       ─► Visualize Funnel
         │     (strict-nested 6-stage funnel + at_risk lateral state)
         └─► Build Features      ─► Train Model    ─► Visualize Model
               (per-user pivot,         (LR + LGBM + SHAP,
                leakage-safe X/y)        PR-AUC, recall@K)
```

End-to-end pipeline on the full 3.5M-row dataset: **~30s** (Build Features + Train Model dominate), Lambda-friendly throughout.

## Local execution (mirrors Zerve)

`run_local.py` reads `<canvas_uuid>/canvas.yaml`, sorts blocks topologically by their edges, and runs each Python block in a shared namespace — exactly like Zerve does on the cloud, including the canvas's `python_global_imports` (`import pandas as pd`).

### Setup

```bash
# 1. dataset (NOT committed; ~861 MB)
mkdir -p datas
cp /path/to/zerve_events.csv datas/zerve_events.csv

# 2. python env via uv
uv sync

# 3. macOS only — LightGBM needs OpenMP
brew install libomp
```

### Run

```bash
uv run run_local.py                          # full pipeline (opens Quartz window for plots)
uv run run_local.py --list                   # show topo execution order
uv run run_local.py --until "EDA Summary"    # stop after a given block
uv run run_local.py --save-figures           # write each plt.show() to figures/figure_NN.png (no GUI)
```

The runner `chdir`s into `datas/` before exec so block code can keep using `pd.read_csv("zerve_events.csv")` unchanged — same path as in Zerve. macOS auto-injects `DYLD_FALLBACK_LIBRARY_PATH` for `libomp`.

### Web app (Next.js)

```bash
./build-archive.sh                # export JSON + build Next.js + commit/push app.zip
( cd web && npm run dev )         # local hot-reload at :3000
uv run uvicorn server:app --port 8000   # serve the production /web/out build
```

Four-section dashboard: headline metrics (animated counters) → 3D PCA user manifold (PC1/PC2/PC3 axes, react-three-fiber) → user lookup with SHAP waterfall → funnel sankey + live threshold sliders backed by a 980-cell prebaked grid.

## Deploy (Zerve Custom Deployment)

The canvas pipeline runs once at *build time* on the local machine; the deployed container only serves the prebuilt static bundle, so the runtime is a 25-line FastAPI wrapper.

```
[local]  ./build-archive.sh
           ├─ export-data.py             → web/public/data/*.json
           ├─ next build                 → web/out/  (data baked in)
           ├─ zip                        → app.zip   (committed to git)
           └─ git push

[zerve]  main.py boots in container
           ├─ fetch app.zip from raw.githubusercontent.com
           ├─ unzip → /tmp/zerve-app
           └─ FastAPI StaticFiles mount /  →  https://beta-zerve.hub.zerve.cloud
```

After a rebuild, hot-reload the deployment without a UI restart:

```bash
curl -X POST https://beta-zerve.hub.zerve.cloud/admin/refresh
curl     https://beta-zerve.hub.zerve.cloud/admin/version
```

Zerve UI Restart is only needed when `main.py` itself changes — which is rare.

## Data loading optimizations

`Example Dataset.py` uses:
- `usecols=["person_id", "timestamp", "event"]` — drops 80 unused columns (2.7GB → 190MB)
- `engine="pyarrow"` — multi-threaded CSV parser (~0.9s vs 30s+ on the c engine)
- `format="ISO8601"` — fast-path timestamp parser
- `dtype={"event": "category"}` — 227 unique events × 3.5M rows compressed via dict encoding

Canvas requires `pyarrow`, `scikit-learn`, `lightgbm`, `shap`, `streamlit`, `plotly` (declared in `canvas.yaml` → `requirements`).

## What lives where

| Path | What it is |
|---|---|
| `5319f3dc-…/canvas.yaml` | Canvas + globals + requirements (Zerve mirror) |
| `5319f3dc-…/Development/layer.yaml` | Blocks + edges for the Development layer |
| `5319f3dc-…/Development/*.py` | Python block source — one file per block |
| `run_local.py` | Local runner — re-execs the canvas off the YAML |
| `export-data.py` | Re-runs the pipeline and dumps JSON into `web/public/data/` |
| `web/` | Next.js 14 frontend (App Router, static export) |
| `server.py` | Local FastAPI wrapper that mounts `web/out/` |
| `main.py` | Zerve deployment entry — fetches `app.zip` from GitHub, mounts static |
| `app.zip` | Build artifact: `server.py + requirements.txt + web/out/` |
| `build-archive.sh` | Build → zip → commit → push, all in one |
| `pyproject.toml` / `uv.lock` | Local deps |
| `datas/zerve_events.csv` | Input dataset (gitignored) |
| `figures/` | `--save-figures` output (gitignored) |

Editing block files locally and pushing keeps Zerve in sync — Zerve re-imports from the repo. Adding a block requires editing **both** `canvas.yaml` (the layer's mirrored block list) and `<layer>/layer.yaml`, plus the source file.

## Compute strategy

All blocks run on Lambda (`compute_environment_type: 1`) thanks to slim loading. Fargate is reserved for blocks that genuinely need >1.5 GB RAM — currently none. Toggling a block to Fargate in Zerve UI sets:

```yaml
compute_settings:
  compute_environment_type: 2
  ephemeral_storage_gib: 20
  size: small        # 1 cpu / 8 GB
```

## Known findings (from current pipeline)

- **3.5M rows / 17,541 users / 2025-09-01 → 2026-04-16**
- **Base upgrade rate**: 323 users (**1.84%**), class imbalance ~53:1
- **Time-to-upgrade**: 70.9% within 3 days, median 3 hours — most upgrades are intent-driven, not earned through engagement
- **Funnel** (strict-nested cumulative reach): 100% → 36.1% (active) → 16.3% (created) → 16.3% (used AI) → 8.8% (engaged) → 1.8% (upgraded)
- **Retention crisis**: 1,053 users at-risk (engaged → 14d idle) vs 286 currently engaged. **78% of engagement is being lost.**
- **Leakage events** (excluded from features): `subscription_upgraded`, `clicked_upgrade`, `upgrade_subscription`, `promo_code_redeemed`, `redeem upgrade offer`, `watermark_remove_upgrade_clicked`, `agent_resume_plan_button_clicked`, `seats_exceeded_share_resource_warning_clicked_upgrade`
- **Model performance** on 8,088 candidates / 31 positives (3-day obs, 60-day label): LightGBM ROC-AUC 0.70, top-decile recall 33% (3× base rate)
- **Top features**: activity intensity (`n_events_obs`), activity hour (`activity_hour_*`), AI usage (`n_ai_obs`), credit pressure (`n_credits_below_obs`)
