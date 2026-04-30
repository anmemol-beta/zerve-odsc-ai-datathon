# Zerve × ODSC AI Datathon

**Live demo**: <https://beta-zerve.hub.zerve.cloud>

Canvas: **Beta** → Layer: **Development**. Pipeline iterated v1 → v4; v3/v4 are the production blocks.

```
Example Dataset    (slim load — 3 cols, pyarrow, ISO8601, category dtype)
   ├─► EDA Summary
   ├─► Funnel Stages       ─► Visualize Funnel       (v1 — 6 stages, kept for reference)
   ├─► Funnel v4           ─► user_features_v4       (15 stages, post-upgrade lifecycle,
   │                                                  + 7 metadata flags)
   └─► Build Features v3   ─► Train Model v3         (calibrated XGB + RF + HGB ensemble,
         (per-user cutoff,        isotonic CalibratedClassifierCV(cv=3), soft voting,
          4 cumulative                time-based cohort split,
          windows, 25-event           PR-AUC 0.2645 / ROC-AUC 0.812 / Brier 0.0222)
          leakage blacklist)              │
                                          ▼
                          build_strategies.py
                            (K2-Think strategist over 14 segments)
                                          │
                                          ▼
                          web/public/data/strategies.json
                            → ActionCards.tsx (Section 07 in the live demo)
```

End-to-end pipeline on the full 3.5M-row dataset: **~3 min** (v3 ensemble training dominates), Lambda-friendly throughout. K2 LLM step is offline + cached, run once and committed as JSON.

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

Seven-section dashboard:

1. **Headline metrics** — animated counters (3.5M events, 17,541 users, 323 upgraders)
2. **User behavior manifold** — 3D PCA (react-three-fiber), color = funnel stage, size = predicted prob
3. **Per-user prediction & explanation** — pick a user → upgrade likelihood + SHAP waterfall
4. **Funnel flow & live thresholds** — sankey + sliders that recompute the funnel against a 980-cell prebaked grid
5. **Time-travel mode** — daily replay (Sept 2025 → Apr 2026) with funnel composition + growth curves
6. **K2 strategist** — pick a v4 funnel segment → K2-Think returns 3 ranked marketing actions (channel, EN/KO copy, target filter, expected ROI) plus 3 risks, all grounded in that segment's behavior + a Zerve playbook excerpt

`web/public/data/strategies.json` is the offline-baked LLM artifact (14 segments × 3 actions × 3 risks, ~99 KB). Re-generate with `uv run build_strategies.py` — uses the K2-Think v2 endpoint and a sha256-keyed file cache so repeated runs cost nothing.

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

Canvas requires `pyarrow`, `scikit-learn`, `lightgbm`, `xgboost`, `shap`, `streamlit`, `plotly` (declared in `canvas.yaml` → `requirements`). The K2 strategist (`llm_client.py`, `build_strategies.py`, `prompts.py`) lives outside the canvas — it consumes the v3/v4 outputs and writes a single JSON file the frontend reads.

## What lives where

| Path | What it is |
|---|---|
| `5319f3dc-…/canvas.yaml` | Canvas + globals + requirements (Zerve mirror) |
| `5319f3dc-…/Development/layer.yaml` | Blocks + edges for the Development layer |
| `5319f3dc-…/Development/*.py` | Python block source — one file per block (v1, v3, v4 coexist) |
| `run_local.py` | Local runner — re-execs the canvas off the YAML |
| `export-data.py` | Re-runs the pipeline and dumps JSON into `web/public/data/` |
| `llm_client.py` | K2-Think wrapper — `ask` / `ask_json` / `stream` + sha256 file cache |
| `prompts.py` | Strategist system prompt + segment → user-prompt formatter |
| `build_strategies.py` | Builds 14 segments × {stats, top behaviors, demographics, score} → K2 → `strategies.json` |
| `web/components/ActionCards.tsx` | Section 07 — segment list + 3 ranked action cards + risks (renders `strategies.json`) |
| `ROADMAP.md` | Vision · rubric mapping · P0/P1/P2 · risks · open decisions |
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

## Known findings (current pipeline — v4 funnel + v3 model)

- **3.5M rows / 17,541 users / 2025-09-01 → 2026-04-16**
- **Base upgrade rate**: 323 users (**1.84%**), class imbalance ~53:1
- **Time-to-upgrade**: 70.9% within 3 days, median 3 hours — most upgrades are intent-driven, not earned through engagement
- **v4 funnel** (15 stages, post-upgrade lifecycle): `0.NoEvent → 1.New → 2.Exploring → 3.Created → 4.UsedAI → 5.WroteCode → 6.Integrated → 7.Engaged → 8.Upgraded`, plus `9.AtRisk@{UsedAI,WroteCode,Integrated,Engaged,Upgraded}` and `9.Churned@Upgraded`. Each user gets exactly one stage at the per-user cutoff.
- **v4 metadata flags** (7): `onboarding_completed`, `used_promo`, `agent_first`, `reactivated`, `exception_rate`, `is_power_engaged`, `purpose`
- **Retention crisis**: 36% of paying users go inactive within 60 days (`9.AtRisk@Upgraded` + `9.Churned@Upgraded`); engagement-stage at-risk pool is much larger than the active-engaged pool
- **Leakage handling** (v3): 25-event blacklist removed from features (`subscription_upgraded`, `clicked_upgrade`, `promo_code_redeemed`, `seats_exceeded_share_resource_warning_clicked_upgrade`, …); per-user cutoff prevents within-user temporal leakage; `_full` time-window features dropped to avoid cutoff-length leak. Trigger events kept as predictors: `credits_exceeded`, `credits_below_*`, `ai_credit_banner_shown`.
- **v3 model**: calibrated XGB + RF + HGB ensemble, isotonic `CalibratedClassifierCV(cv=3)`, soft voting over the 3 calibrated probabilities. 169 features over 4 cumulative time windows (1h / 24h / 7d / full-minus-cutoff).
- **v3 split**: time-based cohort — train = 2025-09 → 2026-02, test = 2026-03 → 2026-04 (185 test positives, ~30× more statistical power than the original 80/20 random split)
- **v3 metrics**: **PR-AUC 0.2645 · ROC-AUC 0.812 · Brier 0.0222** · top-5% precision 0.16 (~9× lift) · top-5% recall ~14%
- **Top features** (v3 importance): activity intensity (`n_events_24h`, `n_events_7d`), session minutes (`session_min_24h`), credit pressure (`n_credits_below_7d`), AI agent usage (`n_agent_tool_24h`), recency (`days_since_last`)
- **K2 strategist coverage**: 14 segments (13 v4 stages + Top-5% predicted upgraders) × 3 actions × 3 risks → `strategies.json` (~99 KB), reused by Section 07 of the live demo
