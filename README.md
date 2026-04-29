# Zerve × ODSC AI Datathon

Canvas: **Beta** → Layer: **Development**.

```
Example Dataset    (slim load — 3 cols, pyarrow, ISO8601, category dtype)
   └─► EDA Summary       (top events, base upgrade rate, leakage flags)
         └─► Funnel Stages      (per-user features, 6-stage funnel classification)
               └─► Visualize Funnel
```

End-to-end run on the full 3.5M-row dataset: **~1.7s**, **~190MB RAM**. Lambda-friendly.

## Local execution (mirrors Zerve)

`run_local.py` reads `<canvas_uuid>/canvas.yaml`, sorts blocks topologically by their edges, and runs each Python block in a shared namespace — exactly like Zerve does on the cloud, including the canvas's `python_global_imports` (`import pandas as pd`).

### Setup

```bash
# 1. dataset (NOT committed; ~861 MB)
mkdir -p datas
cp /path/to/zerve_events.csv datas/zerve_events.csv

# 2. python env via uv
uv sync
```

### Run

```bash
uv run run_local.py                          # full pipeline (opens Quartz window for plots)
uv run run_local.py --list                   # show topo execution order
uv run run_local.py --until "EDA Summary"    # stop after a given block
uv run run_local.py --save-figures           # write each plt.show() to figures/figure_NN.png (no GUI)
```

The runner `chdir`s into `datas/` before exec so block code can keep using `pd.read_csv("zerve_events.csv")` unchanged — same path as in Zerve.

## Data loading optimizations

`Example Dataset.py` uses:
- `usecols=["person_id", "timestamp", "event"]` — drops 80 unused columns (2.7GB → 190MB)
- `engine="pyarrow"` — multi-threaded CSV parser (~0.9s vs 30s+ on the c engine)
- `format="ISO8601"` — fast-path timestamp parser
- `dtype={"event": "category"}` — 227 unique events × 3.5M rows compressed via dict encoding

Canvas requires `pyarrow` (declared in `canvas.yaml` → `requirements`).

## What lives where

| Path | What it is |
|---|---|
| `5319f3dc-…/canvas.yaml` | Canvas + globals + requirements (Zerve mirror) |
| `5319f3dc-…/Development/layer.yaml` | Blocks + edges for the Development layer |
| `5319f3dc-…/Development/*.py` | Python block source — one file per block |
| `run_local.py` | Local runner — re-execs the canvas off the YAML |
| `pyproject.toml` / `uv.lock` | Local deps (pandas, matplotlib, pyarrow, pyyaml) |
| `datas/zerve_events.csv` | Input dataset (gitignored) |
| `figures/` | `--save-figures` output (gitignored) |

Editing block files locally and pushing keeps Zerve in sync — Zerve re-imports from the repo. Adding a block requires editing **both** `canvas.yaml` (the layer's mirrored block list) and `<layer>/layer.yaml`, plus the source file.

## Known findings (from current pipeline)

- **3.5M rows / 17,541 users / 2025-09-01 → 2026-04-16**
- **Base upgrade rate**: 323 users (**1.84%**)
- **Leakage events** (do NOT use as features): `clicked_upgrade`, `upgrade_subscription`, `promo_code_redeemed`, `redeem upgrade offer`, etc.
- **Funnel cumulative reach**: 100% → 23.9% (active) → 24.9% (created) → 39.9% (used AI) → 10.8% (engaged) → 1.8% (upgraded). Note: `created_content` reach > `active` reach — funnel rule ordering needs review (some users create content without ≥2 sign_ins).
