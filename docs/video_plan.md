# 3-min submission video plan

Built around the typical Zerve × ODSC datathon rubric (technical depth, business
insight, platform usage, AI agent integration, MLOps, visualization, innovation).
Total 180 seconds, screen-recording first, voice-over from a separate mic.

## Tooling

| Layer | Tool | Notes |
|---|---|---|
| Screen capture | macOS `Cmd+Shift+5` (or OBS) | 1080p / 60 fps. Hide dock + hide menu bar (System Settings → Control Center → Auto-hide). Use **a fresh Chrome window** with no extensions visible. |
| Voice | Mac built-in mic OR a USB mic into QuickTime "New Audio Recording" | Record once, drop into Resolve as a separate track. Don't rely on phone audio. |
| Cursor highlight | macOS Universal Control disabled, optional **Mousecape** for big cursor, or DaVinci Resolve "Magnify" effect on key clicks | Helps reviewers see where you click |
| Edit | DaVinci Resolve | Cuts only — no fancy transitions. Add subtitle track for technical terms |

Record each shot **twice as long as you need** so you have padding to cut on beats. Aim to record at the actual presentation tempo (don't rush the canvas tour).

## Hard constraints from the brief

- All work in Zerve canvas (✅ 39 blocks)
- Mission 1: subscription-upgrade prediction (✅ v3 ensemble)
- Funnel definition + business interpretation (✅ Funnel v4 = 15 stages, AtRisk + Churned)
- AI agent integration (✅ K2-Think strategist as a canvas block)
- Reproducibility (✅ canvas.yaml + GitHub repo public)

## 3-minute structure (180s budget)

| t | duration | shot | what to say (compressed) |
|---|---|---|---|
| 0:00 | 8s | **Title card**: project name, team, mission tag | "Zerve × ODSC Datathon. Mission 1: predict which Zerve users upgrade — built end-to-end as a 39-block production MLOps canvas." |
| 0:08 | 22s | **Canvas DAG zoomed out** in Zerve UI, slow pan from left to right | "Everything you'll see lives inside one Zerve canvas. 39 blocks, 60 edges, organized as a parallel-converge DAG: validation, EDA, AutoML pool of 5 models, drift detection, K2 LLM strategist, train/serve separation, and a weekly retraining feedback loop." |
| 0:30 | 25s | **Funnel v4 block output** + click into block to show 15-stage list | "The funnel is the foundation. v1 had 6 stages; v4 has 15 — including five AtRisk variants and a Churned-from-Upgraded stage. This catches the 36% of paying users who go inactive within 60 days, which the simpler funnel hides." |
| 0:55 | 25s | **AutoML pool**: hover over Train Model v3 → Train MLP v3 → Train GBM v3, click Compare Models output table | "Five candidate models — calibrated XGB+RF+HGB ensemble, sklearn GBM, PyTorch MLP, plus a v1 baseline. All isotonic-calibrated for apples-to-apples PR-AUC. The ensemble wins at 0.265 PR-AUC, ROC-AUC 0.81 — about 9× lift on the top-5%." |
| 1:20 | 20s | **Champion Selector + Performance Drift dashboard** | "We don't pick a champion on one split. Time-Rolling Splits gives us four monthly cohorts, Train Across Time evaluates every model on every cohort, and Champion Selector picks the model that's stable, not the model that got lucky on March." |
| 1:40 | 20s | **Data Drift Monitor heatmap** + **Weekly Inference plot** | "Without labels, we still watch incoming weekly data with PSI and KS divergence per feature. Material drift triggers a re-train alert. Inference is decoupled from training — Persist Models writes to /tmp, Load Models reads on demand, with a GitHub-raw fallback so it works on cold containers." |
| 2:00 | 20s | **Pipeline tier zoom**: Load Master + Load Weekly Drop → Merge → Build Inference / Build Training fork → Persist Master | "And the loop closes. Every Monday a new weekly events drop lands. Merge unions it into the master pool, then forks into an inference pool and a training pool — different filters because different purposes. Persist Master writes back with a SHA-256 and a `would_promote` flag for the CI promotion job." |
| 2:20 | 20s | **Frontend live demo**: open the GitHub Pages site, click a block, type a row index, see live prediction | "The frontend is a Next.js static site on GitHub Pages. It never runs ML — every figure, every prediction is fetched live from the Zerve deployment, which reads canvas variables directly. So when the canvas re-runs, the site updates with one curl command." |
| 2:40 | 15s | **K2 strategy card**: pick a segment, show the 3 actions + ROI ranking | "AI agent integration: K2-Think reads each of 14 funnel segments and writes 3 ranked actions with channel, copy, expected uplift, and ROI — graded against our business playbook. 42 strategies generated, cached as JSON for the demo, regenerated live with an API key." |
| 2:55 | 5s | **End card** with repo + frontend URLs | "Repo and live demo links below. Thanks." |

Pacing tip: every "tier" gets 20–25 seconds. Don't try to read every block name — the visual tells the story. Voice-over only narrates what's special about each tier.

## Rubric coverage map (so judges check every box)

| Rubric category (typical) | Where in the video | What we show |
|---|---|---|
| **Mission completeness** | 0:30, 0:55, 1:20, 1:40 | Funnel v4, model metrics, drift, champion |
| **Technical depth** | 0:55–1:40 | 5-model AutoML, calibration, rolling cohorts |
| **All work in Zerve** | 0:08–0:30 panning shot | Canvas DAG visible end-to-end |
| **AI / agent integration** | 2:40 | K2-Think strategist segment card |
| **Visualization & UX** | 2:20 | Live frontend, ReactFlow DAG, click-through |
| **MLOps / production** | 1:40, 2:00 | Drift, train/serve split, feedback loop, gates |
| **Business impact** | 0:30, 2:40 | Funnel + segments + ROI ranking |
| **Innovation** | 1:20, 2:00 | Stability-weighted champion, train/infer fork, label-lag gate |
| **Reproducibility** | 2:55 | Repo URL + canvas.yaml mention |

## Concrete shot list (record these in this order)

1. **Title card** (5s) — make in Resolve, full-screen text with project name + your name
2. **Canvas zoomed out** — Zerve UI, ~80% zoom so all 39 blocks fit. Mouse drags slowly across. Record 20s.
3. **Funnel v4 block** — click into the block, scroll the printed stage table. Record 30s.
4. **Train Model v3 metrics output** — show PR-AUC table. 15s.
5. **Compare Models block** — printed comparison table. 15s.
6. **Champion Selector** — printed champion summary + win counts. 15s.
7. **Performance Drift block** — the line plot dashboard. 15s.
8. **Data Drift Monitor** — heatmap + alerts list. 20s.
9. **Weekly Inference dashboard** — predicted vs actual + week × stage heatmap. 20s.
10. **Pipeline tier zoom** — Load Master + Load Drop + Merge + Build Inference + Build Training + Persist Master, screen-record the panning. 20s.
11. **Frontend hero** — open GitHub Pages site. 10s.
12. **Frontend canvas DAG view** — click a block, show the figure pane. 15s.
13. **Live predict** — type row index, see prediction. 15s.
14. **K2 strategy card** — segment picker → 3-action card. 20s.
15. **Insights Card** — final summary block output. 10s.
16. **End card** — repo URL + frontend URL + thanks. 5s.

Record all of those before opening DaVinci. Total raw footage: ~4 minutes — gives you 30%+ trimming room to land on 180 seconds.

## DaVinci Resolve workflow (45 min edit)

1. **Project setup**: 1080p 60 fps, Davinci YRGB color science.
2. **Track layout**:
   - V1: shots in order
   - V2: zoomed-in detail crops or overlays (e.g., highlight a number on screen)
   - V3: text overlays for technical terms (PR-AUC, PSI, etc.)
   - A1: voice-over (single take, edit out breaths)
   - A2: optional bed (low subtle ambient — not music with vocals)
3. **First pass**: razor-cut every shot to the duration in the table. Don't bother with transitions — straight cuts.
4. **Voice sync**: record voice-over once start to finish reading the script, then nudge each shot to land on its phrase.
5. **Highlights**: in Color page, slightly desaturate Zerve UI gray (sometimes too cool) — push +5 saturation, -3 lift, no other grading needed.
6. **Subtitles**: drop technical term labels (PR-AUC 0.265, 14 segments, etc.) on V3 for 3-second pops.
7. **Levels**: voice -14 LUFS, ambient -28 LUFS. Use Fairlight loudness meter.
8. **Export**: H.264, 1080p60, ~12 Mbps, MP4. File should be under ~250 MB.

## Common mistakes to avoid

- **Don't mouse around aimlessly.** Plan the cursor path in each shot.
- **Don't read the canvas block names.** Voice-over describes the tier, not every block.
- **Don't show the IDE / VS Code.** The submission story is the canvas + frontend, not the source.
- **Don't show your real K2 API key.** If you do a live K2 generate on camera, blur the URL bar / settings page.
- **Don't fake the metrics.** Use the actual canvas output. Judges WILL re-run blocks.
- **Don't leave dead frames at the end.** Cut the moment your last word ends.

## What to put in the submission description (alongside the video)

- **Project link**: https://github.com/anmemol-beta/zerve-odsc-ai-datathon
- **Live demo**: https://anmemol-beta.github.io/zerve-odsc-ai-datathon/
- **Canvas API**: https://beta-zerve.hub.zerve.cloud
- One sentence: "39-block Zerve canvas predicting Zerve subscription upgrades — calibrated AutoML pool of 5, K2-Think LLM strategist, drift-monitored weekly inference, full retrain feedback loop."

Keep that line tight; the judges read 100+ submissions.
