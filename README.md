# Zerve × ODSC AI Datathon

**Frontend**: <https://anmemol-beta.github.io/zerve-odsc-ai-datathon/>
**API**: <https://beta-zerve.hub.zerve.cloud>

A live mirror of the Zerve canvas: every block, every figure, every prediction is fetched in real time from the deployed FastAPI, which itself reads `zerve.variable(block, name)` straight off the running canvas.

```
┌──────────────────────┐        ┌──────────────────────┐        ┌──────────────────────┐
│  Zerve canvas        │        │  Zerve deployment    │        │  GitHub Pages        │
│  (Beta · 22 blocks)  │  ◄──►  │  api.py + zerve.var  │  ◄──►  │  Next.js static site │
│                      │        │  beta-zerve.hub.zerve.cloud │        │  /web                │
└──────────────────────┘        └──────────────────────┘        └──────────────────────┘
        ▲                                ▲                                ▲
        │                                │                                │
   data scientist                  zerve_deploy/main.py            anyone with the URL
```

The frontend never executes ML code. It draws the canvas DAG (with the exact xy coordinates from `canvas.yaml`), and on every interaction it calls the deployed FastAPI:

- click a block → `GET /figure/{block}` (matplotlib PNG straight from the canvas variable)
- type a row index → `GET /predict/sample/{idx}` (live calibrated XGB ensemble inference)
- pick a segment → `GET /strategies/segments` (K2-Think output from the canvas)
- the final card → `GET /insights` + `/figure/Insights Card`

## What lives where

| Path | What it is |
|---|---|
| `5319f3dc-…/canvas.yaml` | Canvas + globals + requirements (Zerve mirror) |
| `5319f3dc-…/Development/layer.yaml` | Blocks + edges for the Development layer |
| `5319f3dc-…/Development/*.py` | Python block source — one file per block (v1, v3, v4 coexist) |
| `zerve_deploy/main.py` | The Zerve FastAPI deployment — paste into the deployment editor |
| `web/` | Next.js 14 frontend (App Router, static export) |
| `web/lib/canvas.ts` | DAG layout — block positions/edges inlined from `canvas.yaml` |
| `web/lib/api.ts` | Typed client for `beta-zerve.hub.zerve.cloud` |
| `web/components/canvas/` | Reactflow DAG renderer + per-block detail pane |
| `.github/workflows/pages.yml` | Auto-deploys `web/` to GitHub Pages on every push |
| `pyproject.toml` / `uv.lock` | Local deps |
| `datas/zerve_events.csv` | Input dataset (gitignored) |

## Deploy

### 1. Backend (Zerve deployment)

Open the canvas → Deploy tab → New Deployment → **Custom**:
- DNS Name: `beta-zerve` (resolves to `https://beta-zerve.hub.zerve.cloud`)
- Run command: `uvicorn main:app --host 0.0.0.0 --port 8080`
- Code: paste the contents of `zerve_deploy/main.py`

The deployment lazy-loads canvas variables via `from zerve import variable`, caches them in-process, and exposes them over CORS-open HTTP. After the canvas re-runs:

```bash
curl -X POST https://beta-zerve.hub.zerve.cloud/admin/reload
```

…clears the cache without a container restart.

### 2. Frontend (GitHub Pages)

```bash
git push origin main
```

The `pages.yml` workflow builds `web/` with `GITHUB_PAGES=true` and `NEXT_PUBLIC_API_URL=https://beta-zerve.hub.zerve.cloud`, then publishes `web/out/` to Pages. First-time setup: in repo Settings → Pages, set **Source = GitHub Actions**.

### Local frontend dev

```bash
cd web
npm install
NEXT_PUBLIC_API_URL=https://beta-zerve.hub.zerve.cloud npm run dev
# → http://localhost:3000 talking to the live deployment
```

Override `NEXT_PUBLIC_API_URL` to point at a different deployment or a local FastAPI for offline work.

## Pipeline overview

Canvas: **Beta** → Layer: **Development**. v3/v4 are the production blocks; v1 is kept for comparison.

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
                          Build Strategies      (K2-Think strategist over 14 segments)
                                          │
                                          ▼
                          ROI Ranking · Strategy Heatmap · Insights Card
```

End-to-end pipeline on the full 3.5M-row dataset: **~3 min** (v3 ensemble training dominates), Lambda-friendly throughout. K2 LLM step is offline + cached, run once and committed as JSON.

## Data loading optimizations

`Example Dataset.py` uses:
- `usecols=["person_id", "timestamp", "event"]` — drops 80 unused columns (2.7GB → 190MB)
- `engine="pyarrow"` — multi-threaded CSV parser (~0.9s vs 30s+ on the c engine)
- `format="ISO8601"` — fast-path timestamp parser
- `dtype={"event": "category"}` — 227 unique events × 3.5M rows compressed via dict encoding

Canvas requires `pyarrow`, `scikit-learn`, `lightgbm`, `xgboost`, `shap`, `streamlit`, `plotly` (declared in `canvas.yaml` → `requirements`).

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
- **Retention crisis**: 36% of paying users go inactive within 60 days
- **Leakage handling** (v3): 25-event blacklist removed from features; per-user cutoff prevents within-user temporal leakage; `_full` time-window features dropped to avoid cutoff-length leak.
- **v3 model**: calibrated XGB + RF + HGB ensemble, isotonic `CalibratedClassifierCV(cv=3)`, soft voting. 169 features × 4 cumulative time windows (1h / 24h / 7d / full-minus-cutoff).
- **v3 metrics**: **PR-AUC 0.2645 · ROC-AUC 0.812 · Brier 0.0222** · top-5% precision 0.16 (~9× lift) · top-5% recall ~14%
- **K2 strategist coverage**: 14 segments × 3 actions × 3 risks
