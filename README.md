# Zerve × ODSC AI Datathon — Subscription Upgrade Prediction

**Frontend**: <https://anmemol-beta.github.io/zerve-odsc-ai-datathon/>
**API**: <https://beta-zerve.hub.zerve.cloud>

A production-style MLOps pipeline built entirely inside the Zerve canvas. **39 blocks · 60 edges**, organized as a parallel-converge DAG that goes from raw events → validated features → an AutoML pool of 5 models → drift detection → a champion picked for serving → a weekly retraining feedback loop → a Next.js frontend that reads canvas variables in real time.

```
┌──────────────────────┐        ┌──────────────────────┐        ┌──────────────────────┐
│  Zerve canvas        │        │  Zerve deployment    │        │  GitHub Pages        │
│  (Beta · 39 blocks)  │  ◄──►  │  zerve_deploy/main.py│  ◄──►  │  Next.js static site │
│                      │        │  beta-zerve.hub...   │        │  /web                │
└──────────────────────┘        └──────────────────────┘        └──────────────────────┘
        ▲                                ▲                                ▲
        │                                │                                │
   data scientist                  zerve.variable(...)             anyone with the URL
```

The frontend never executes ML code. It draws the canvas DAG (using the exact xy from `canvas.yaml`), and on every interaction calls the deployed FastAPI:

- click a block → `GET /figure/{block}` (matplotlib PNG straight from the canvas variable)
- type a row index → `GET /predict/sample/{idx}` (live calibrated XGB ensemble inference)
- pick a segment → `GET /strategies/segments` (K2-Think output from the canvas)
- the final card → `GET /insights` + `/figure/Insights Card`

## Pipeline (39 blocks, parallel-converge DAG)

```
                            ┌─ EDA Summary
                            ├─ Funnel Stages ──── Visualize Funnel
Example Dataset ────────────┤
   │                        ├─ Build Features  ── Train Model (v1) ──────────────┐
   │                        ├─ Funnel v4
   │                        ├─ Validate Funnel v4
   │                        ├─ Validate Features v3                              │
   ├─ Validate Events       └─ Build Features v3 ──┐                             │
   │                                                │                             │
   │     ┌─ Train Model v3   (XGB+RF+HGB calibrated soft-vote ensemble) ─┐       │
   │     ├─ Train MLP v3     (PyTorch tab-MLP, isotonic calibration)     ┤       │
   │     ├─ Train GBM v3     (sklearn GBM, isotonic cv=3)                ┤       │
   │     │                                                                │       │
   │     ▼                                                                ▼       │
   │   Diagnose v3 · SHAP v3 · Compare Models · Per-Segment Performance ──────┐  │
   │                                                                            │  │
   │   Time-Rolling Splits ─► Train Across Time ─► Performance Drift ─► Champion Selector
   │                                                                            │  │
   │   Build Strategies (K2-Think LLM) ──► ROI Ranking · Strategy Heatmap ────┐│  │
   │                                                                          ││  │
   ├─ Weekly Data Slices ──► Data Drift Monitor (PSI + KS) ──────────────────┐│  │
   │            │                                                            ││  │
   │            ▼                                                            ││  │
   │     Weekly Inference ◄── Load Models ◄── Persist Models ◄───────────────┘│  │
   │                                                                           │  │
   └─ Load Events Master ─┐                                                    │  │
                           ├─► Merge Events ─┬─► Build Inference Pool ─────────┤  │
   Load Weekly Drop ─────┘                  └─► Build Training Pool ─► Persist Master
                                                                              │  │
                                                          Visualize Cohort ◄──┤  │
                                                                              ▼  ▼
                                                                        Insights Card
```

Five tiers, each running in parallel within itself and converging at the next:

| Tier | Blocks | What it does |
|---|---|---|
| **Validation** | Validate Events, Validate Funnel v4, Validate Features v3 | great-expectations-style schema/leakage checks |
| **EDA + Funnel** | EDA Summary, Funnel Stages (v1, 6 stages), Funnel v4 (15 stages incl. post-upgrade) | descriptive analysis + lifecycle assignment |
| **Modeling (AutoML pool of 5)** | Train Model v3 (calibrated XGB+RF+HGB ensemble), Train MLP v3 (PyTorch), Train GBM v3 (sklearn GBM), Train Model (v1 LR+LightGBM) | 4 model families, all isotonic-calibrated, evaluated on a forward-looking holdout |
| **Diagnostics + AutoML loop** | Diagnose v3, SHAP v3 (real shap or pure-numpy Štrumbelj-Kononenko fallback), Compare Models, Per-Segment Performance, Time-Rolling Splits, Train Across Time, Performance Drift, Champion Selector | rolling cohorts × all candidates → weighted champion (0.5·latest + 0.3·mean + 0.2·stability) |
| **Strategy + Insights** | Build Strategies (K2-Think LLM strategist), ROI Ranking, Strategy Heatmap, Visualize Cohort, Insights Card | per-segment playbooks with cached fallback |
| **Weekly drift + serve** | Weekly Data Slices, Data Drift Monitor (PSI 0.10/0.25 + KS), Persist Models, Load Models, Weekly Inference | train tier persists champion to `/tmp/zerve-models/v3/`; inference tier loads on demand and scores incoming weekly slices |
| **Weekly data feedback loop** | Load Events Master, Load Weekly Drop, Merge Events, **Build Inference Pool**, **Build Training Pool**, Persist Master | reads accumulated events pool + this week's drop; merges/dedups; explicitly forks into an inference pool (recency-windowed, all users) and a training pool (label-lag cutoff + trainability gates); Persist Master writes back the master and includes a `would_promote_new_model` flag based on the gate result |

Training and serving are **decoupled**: Persist Models writes joblib pickles + `meta.json`, Load Models reads them (with a GitHub-raw fallback so cold containers still work), Weekly Inference does the actual scoring without re-training. Run Persist Models on a weekly cron and Weekly Inference on demand.

The data tier is **append-only**: Load Events Master fetches `data/events_master.parquet` from a durable store (GitHub raw in this demo, S3/GCS in production). Load Weekly Drop pulls one week of new events at a time. Merge Events unions and dedups, then forks into two purpose-specific blocks so the train/infer split is visible on the DAG: **Build Inference Pool** (recency-windowed, includes label-pending users — this is what gets scored this week) and **Build Training Pool** (label-stable subset + min-users / min-positives trainability gates — this is what feeds the next retrain cycle). Persist Master writes back the updated pool with a SHA-256 hash and exposes a `would_promote_new_model` flag based on the trainability gate, so the CI promotion job can skip retraining when the new data is too thin.

## Repo layout

| Path | What it is |
|---|---|
| `5319f3dc-…/canvas.yaml` | Canvas root — globals, requirements, env vars |
| `5319f3dc-…/Development/layer.yaml` | Layer config — 39 blocks + 60 edges |
| `5319f3dc-…/Development/*.py` | One file per block (~5500 lines total) |
| `zerve_deploy/main.py` | FastAPI deployment — paste into Zerve deployment editor |
| `web/` | Next.js 14 frontend (App Router, static export, ReactFlow DAG) |
| `web/lib/canvas.ts` | DAG layout — block positions/edges inlined from `canvas.yaml` |
| `web/lib/api.ts` | Typed client for `beta-zerve.hub.zerve.cloud` |
| `docs/` | Architecture deep-dive, analysis report, business playbook, roadmap |
| `.github/workflows/pages.yml` | Auto-deploys `web/` to GitHub Pages |
| `pyproject.toml` / `uv.lock` / `requirements.txt` | Local dev deps |

## Headline results

- **Dataset**: 3.5M rows · 17,541 users · 2025-09-01 → 2026-04-16
- **Base upgrade rate**: 1.84% (323 users) · class imbalance ~53:1
- **v3 ensemble** (XGB + RF + HGB, isotonic CalibratedClassifierCV, soft voting): **PR-AUC 0.2645 · ROC-AUC 0.812 · Brier 0.0222** · top-5% precision 0.16 (~9× lift)
- **v4 funnel** (15 stages incl. `9.AtRisk@*` and `9.Churned@Upgraded`): captures the 36% post-upgrade churn-within-60-days problem that v1's 6-stage funnel ignored
- **Champion picker**: weighted score over rolling cohorts → ensemble_v3 wins on stability + latest-cohort PR-AUC
- **K2 strategist**: 14 segments × 3 actions × 3 risks, cached JSON fallback for live demo
- **Drift watch**: PSI/KS per (week × feature) vs first-4-weeks baseline; alerts on material (>0.25) and chronic (3-week) drift

## Compute strategy

Most blocks run on Lambda (`compute_environment_type: 1`, 1.5 GB cap). Two blocks need Fargate (`type: 2`, 8 GB):

- **Train Model v3** — XGBoost wheel + 3-model RF/HGB calibration overflows Lambda
- **Persist Models** — pickling the full calibrated bundle

Toggling Fargate in Zerve UI sets:
```yaml
compute_settings:
  compute_environment_type: 2
  ephemeral_storage_gib: 20
  size: small        # 1 cpu / 8 GB
```

## Deploy

### 1. Backend (Zerve deployment)

Open the canvas → Deploy tab → New Deployment → **Custom**:
- DNS Name: `beta-zerve` → `https://beta-zerve.hub.zerve.cloud`
- Run command: `uvicorn main:app --host 0.0.0.0 --port 8080`
- Code: paste `zerve_deploy/main.py`

The deployment lazy-loads canvas variables via `from zerve import variable`, caches them in-process, and exposes them over CORS-open HTTP. After the canvas re-runs:
```bash
curl -X POST https://beta-zerve.hub.zerve.cloud/admin/reload
```
…clears the cache without a container restart.

### 2. Frontend (GitHub Pages)

```bash
git push origin main
```

`pages.yml` builds `web/` with `GITHUB_PAGES=true` and `NEXT_PUBLIC_API_URL=https://beta-zerve.hub.zerve.cloud`, then publishes `web/out/` to Pages. First-time setup: in repo Settings → Pages, set **Source = GitHub Actions**.

### Local frontend dev

```bash
cd web
npm install
NEXT_PUBLIC_API_URL=https://beta-zerve.hub.zerve.cloud npm run dev
# → http://localhost:3000 talking to the live deployment
```

## Canvas requirements

```yaml
requirements:
  - pyarrow            # fast CSV
  - scikit-learn       # calibration, splits, metrics, GBM
  - lightgbm           # v1 baseline
  - xgboost<4          # v3 ensemble (Zerve compatibility band)
  - torch<3            # MLP v3 (sklearn fallback if torch unavailable)
  - streamlit, plotly  # in-canvas visuals
  - optuna             # AutoML hyper-search hook
  - imbalanced-learn   # SMOTE for MLP path
```

`shap` is **not** declared — SHAP v3 ships a pure-numpy Štrumbelj-Kononenko Monte Carlo Shapley estimator that activates if the import fails. `catboost` was replaced by sklearn's GradientBoosting for the same reason.

## Key design choices

- **Real DAG, not a notebook**: 39 blocks with explicit edges; you can see fan-out (parallel model training, train/infer split) and fan-in (Champion Selector, Insights Card) directly in the canvas.
- **Train/serve separation**: Persist Models + Load Models pattern decouples weekly retraining from on-demand inference. Inference works even if training is offline (GitHub-raw fallback).
- **AutoML over time, not just one split**: Time-Rolling Splits + Train Across Time + Performance Drift + Champion Selector picks the model that is **stable across cohorts**, not the one with the best single-split number.
- **Drift-aware**: Data Drift Monitor watches incoming weekly data without labels (PSI + KS), so we know when to re-train before metrics degrade.
- **Honest interpretability**: real SHAP when available, principled sampling-SHAP fallback otherwise — never a fake stand-in.
- **Live demo, not a static export**: every figure in the frontend is fetched from `zerve.variable(block, name)` at request time.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — full block-by-block architecture
- [`docs/analysis_report.md`](docs/analysis_report.md) — EDA + funnel findings
- [`docs/prediction_report.md`](docs/prediction_report.md) — model report
- [`docs/business_playbook.md`](docs/business_playbook.md) — segment-level GTM playbook
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — what shipped vs what's next
