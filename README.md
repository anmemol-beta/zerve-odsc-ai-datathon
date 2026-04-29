# Zerve × ODSC AI Datathon

Canvas: **Beta** → Layer: **Development**.

```
markdown_block
   └─► Example Dataset    (loads zerve_events.csv)
         └─► Describe Dataset
               └─► EDA Summary       (event counts, time range, leakage watch)
                     └─► Funnel Stages      (per-user features + 6 funnel stages)
                           └─► Visualize Funnel
```

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
uv run run_local.py --layer Development      # explicit layer (only one for now)
```

The runner `chdir`s into `datas/` before exec so block code can keep using `pd.read_csv("zerve_events.csv")` unchanged — same path as in Zerve.

## What lives where

| Path | What it is |
|---|---|
| `5319f3dc-…/canvas.yaml` | Canvas + globals (Zerve mirror) |
| `5319f3dc-…/Development/layer.yaml` | Blocks + edges for the Development layer |
| `5319f3dc-…/Development/*.py` | Python block source — one file per block |
| `5319f3dc-…/Development/*.md` | Markdown block source |
| `run_local.py` | Local runner — re-execs the canvas off the YAML |
| `pyproject.toml` / `uv.lock` | Local deps (pandas, matplotlib, pyarrow, pyyaml) |
| `datas/zerve_events.csv` | Input dataset (gitignored) |
| `figures/` | `--save-figures` output (gitignored) |

Editing block files locally and pushing keeps Zerve in sync — Zerve re-imports from the repo. Adding a block requires editing **both** `canvas.yaml` (the layer's mirrored block list) and `<layer>/layer.yaml`, plus the source file.
