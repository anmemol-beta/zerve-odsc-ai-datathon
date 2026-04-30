// Canvas DAG mirror — inlined from 5319f3dc-9b9d-449e-838d-dcac9f13a133/canvas.yaml.
// Positions, sizes, descriptions, and edges all come straight from the Zerve project,
// so the frontend renders the exact same graph the user sees inside the canvas.

export type CanvasBlockKind =
  | "ingest"
  | "transform"
  | "model"
  | "viz"
  | "validate"
  | "strategy"
  | "report"
  | "ops";

export type CanvasBlock = {
  id: string;
  name: string;
  description: string;
  x: number;
  y: number;
  width: number;
  height: number;
  kind: CanvasBlockKind;
  hasFigure: boolean;
};

export type CanvasEdge = {
  id: string;
  source: string;
  target: string;
};

export const CANVAS_BLOCKS: CanvasBlock[] = [
  {
    id: "example-dataset",
    name: "Example Dataset",
    description:
      "Slim-loads zerve_events.csv (usecols=person_id, timestamp, event), pyarrow engine, ISO8601 timestamps, categorical event dtype. Produces `events`.",
    x: 0, y: 0, width: 1600, height: 1000,
    kind: "ingest", hasFigure: false,
  },
  {
    id: "validate-events",
    name: "Validate Events",
    description:
      "Schema/null/range/dedup/leakage-event audit on raw events. Halts the pipeline on any hard failure.",
    x: 1700, y: 200, width: 1600, height: 1000,
    kind: "validate", hasFigure: false,
  },
  {
    id: "eda-summary",
    name: "EDA Summary",
    description:
      "Top events, base upgrade rate, and likely-leakage event flags that must be excluded from upgrade-prediction features.",
    x: 0, y: 500, width: 1600, height: 1000,
    kind: "transform", hasFigure: true,
  },
  {
    id: "funnel-stages",
    name: "Funnel Stages",
    description:
      "Builds per-user features and assigns each user to one of six funnel stages. Outputs `user_features`.",
    x: 0, y: 1000, width: 1600, height: 1000,
    kind: "transform", hasFigure: true,
  },
  {
    id: "build-features",
    name: "Build Features",
    description:
      "Leakage-safe per-user X/y for two forward-looking snapshots (train cutoff 2026-02-01, test cutoff 2026-03-01, 30d label window).",
    x: 1700, y: 1000, width: 1600, height: 1000,
    kind: "transform", hasFigure: false,
  },
  {
    id: "visualize-funnel",
    name: "Visualize Funnel",
    description:
      "Renders the funnel descent and the top-15 events as horizontal bar charts using matplotlib.",
    x: 0, y: 1500, width: 1600, height: 1000,
    kind: "viz", hasFigure: true,
  },
  {
    id: "train-model",
    name: "Train Model",
    description:
      "Trains logistic regression + LightGBM. Reports PR-AUC, recall@K, SHAP feature importance.",
    x: 1700, y: 1500, width: 1600, height: 1000,
    kind: "model", hasFigure: false,
  },
  {
    id: "compare-models",
    name: "Compare Models",
    description:
      "Fan-in from Train Model (v1) and v3 — side-by-side metrics table, head-to-head bar chart, statistical-power callout (6 vs 185 test positives).",
    x: 3400, y: 1500, width: 1600, height: 1000,
    kind: "report", hasFigure: true,
  },
  {
    id: "visualize-cohort",
    name: "Visualize Cohort",
    description:
      "Cumulative growth, daily activity sparkline + upgrade markers, weekly cohort upgrade rate vs cumulative baseline, day-of-week × hour heatmap.",
    x: 0, y: 2000, width: 1600, height: 1000,
    kind: "viz", hasFigure: true,
  },
  {
    id: "visualize-model",
    name: "Visualize Model",
    description: "ROC + PR curves, LightGBM feature importance, SHAP impact in a 2×2 dashboard.",
    x: 1700, y: 2000, width: 1600, height: 1000,
    kind: "viz", hasFigure: true,
  },
  {
    id: "funnel-v4",
    name: "Funnel v4",
    description:
      "15-stage Time-Aware funnel classifier with post-upgrade lifecycle (Upgraded / AtRisk@Upgraded / Churned@Upgraded). Outputs `user_features_v4`.",
    x: 0, y: 2500, width: 1600, height: 1000,
    kind: "transform", hasFigure: false,
  },
  {
    id: "build-features-v3",
    name: "Build Features v3",
    description:
      "Per-user feature matrix at 4 cumulative windows (1h/24h/7d/full), leakage-safe per-user cutoff, time-based cohort split.",
    x: 1700, y: 2500, width: 1600, height: 1000,
    kind: "transform", hasFigure: false,
  },
  {
    id: "validate-features-v3",
    name: "Validate Features v3",
    description:
      "User-disjoint check, leakage-feature audit (25-token blacklist), _full window absence, distribution shift sample.",
    x: 3400, y: 2500, width: 1600, height: 1000,
    kind: "validate", hasFigure: false,
  },
  {
    id: "train-model-v3",
    name: "Train Model v3",
    description:
      "Calibrated XGBoost + RandomForest + HistGB ensemble (isotonic, cv=3) with soft voting. Reports PR-AUC, ROC-AUC, Brier, top-K precision/recall.",
    x: 1700, y: 3000, width: 1600, height: 1000,
    kind: "model", hasFigure: false,
  },
  {
    id: "diagnose-v3",
    name: "Diagnose v3",
    description:
      "Calibration reliability diagram, ROC overlay, PR overlay, Brier decomposition (reliability/resolution/uncertainty) + per-model ECE.",
    x: 3400, y: 3000, width: 1600, height: 1000,
    kind: "viz", hasFigure: true,
  },
  {
    id: "build-strategies",
    name: "Build Strategies",
    description:
      "K2-Think marketing strategist over 14 v4 funnel segments. Real-time if K2_API_KEY is set, else fetches the last-committed strategies.json from raw GitHub.",
    x: 850, y: 3500, width: 1600, height: 1000,
    kind: "strategy", hasFigure: false,
  },
  {
    id: "shap-v3",
    name: "SHAP v3",
    description:
      "Tree SHAP on the v3 ensemble — averages SHAP values across the 3 calibration folds, renders top-20 bar + contrasting upgrader/non-upgrader waterfalls.",
    x: 3400, y: 3500, width: 1600, height: 1000,
    kind: "viz", hasFigure: true,
  },
  {
    id: "validate-funnel-v4",
    name: "Validate Funnel v4",
    description:
      "8-check audit on user_features_v4 — exactly-one-stage, closed enum, monotonicity, AtRisk@X rank consistency, label/flag agreement.",
    x: 0, y: 4000, width: 1600, height: 1000,
    kind: "validate", hasFigure: false,
  },
  {
    id: "per-segment-performance",
    name: "Per-Segment Performance",
    description:
      "Joins each test user's v3 prediction with their v4 funnel stage, then computes per-segment PR-AUC, top-5% precision, and lift over base rate.",
    x: 1700, y: 4000, width: 1600, height: 1000,
    kind: "report", hasFigure: true,
  },
  {
    id: "strategy-heatmap",
    name: "Strategy Heatmap",
    description:
      "14 segments × 6 channels heatmap of best ROI per cell, plus action-count heatmap (how often K2 picked each channel).",
    x: 850, y: 4500, width: 1600, height: 1000,
    kind: "viz", hasFigure: true,
  },
  {
    id: "roi-ranking",
    name: "ROI Ranking",
    description:
      "Flattens K2 actions into a long table, ranks by ROI, charts top-10, per-channel boxplot, and best-per-segment.",
    x: 2500, y: 4500, width: 1600, height: 1000,
    kind: "report", hasFigure: true,
  },
  {
    id: "insights-card",
    name: "Insights Card",
    description:
      "Final fan-in from Diagnose v3, SHAP v3, Compare Models, Per-Segment Performance, Build Strategies, ROI Ranking. 1-page text + visual insights card.",
    x: 1700, y: 5000, width: 1600, height: 1000,
    kind: "report", hasFigure: true,
  },
  // ── AutoML / time-rolling / inference tier ─────────────────────────────
  {
    id: "train-mlp-v3",
    name: "Train MLP v3",
    description:
      "PyTorch tabular MLP — deep-learning candidate for the AutoML pool. 3-layer net with BatchNorm/GELU/Dropout, class-weighted BCE, cosine LR, isotonic post-hoc calibration.",
    x: 5100, y: 2500, width: 1600, height: 1000,
    kind: "model", hasFigure: false,
  },
  {
    id: "train-gbm-v3",
    name: "Train GBM v3",
    description:
      "Bias-diverse GBM candidate — sklearn GradientBoosting (CART) wrapped in isotonic CalibratedClassifierCV(cv=3). catboost optional.",
    x: 5100, y: 3000, width: 1600, height: 1000,
    kind: "model", hasFigure: false,
  },
  {
    id: "weekly-data-slices",
    name: "Weekly Data Slices",
    description:
      "ISO-week slicing of `events`. Per-(week, user) feature snapshot. Outputs `weekly_slices`, `weekly_summary`, `weekly_baseline_id`. Head of the data-drift branch.",
    x: 6800, y: 0, width: 1600, height: 1000,
    kind: "transform", hasFigure: false,
  },
  {
    id: "data-drift-monitor",
    name: "Data Drift Monitor",
    description:
      "Data-drift detection without labels. Per-(week, feature) PSI + KS test vs first-4-weeks baseline. Thresholds 0.10 / 0.25. Heatmap + line plot dashboard.",
    x: 6800, y: 500, width: 1600, height: 1000,
    kind: "viz", hasFigure: true,
  },
];

export const CANVAS_EDGES: CanvasEdge[] = [
  ["example-dataset", "eda-summary"],
  ["example-dataset", "validate-events"],
  ["example-dataset", "funnel-v4"],
  ["example-dataset", "build-features-v3"],
  ["example-dataset", "weekly-data-slices"],
  ["eda-summary", "funnel-stages"],
  ["eda-summary", "build-features"],
  ["funnel-stages", "visualize-funnel"],
  ["funnel-stages", "visualize-cohort"],
  ["build-features", "train-model"],
  ["train-model", "visualize-model"],
  ["train-model", "compare-models"],
  ["funnel-v4", "build-strategies"],
  ["funnel-v4", "validate-funnel-v4"],
  ["funnel-v4", "per-segment-performance"],
  ["build-features-v3", "train-model-v3"],
  ["build-features-v3", "validate-features-v3"],
  ["build-features-v3", "train-mlp-v3"],
  ["build-features-v3", "train-gbm-v3"],
  ["train-model-v3", "build-strategies"],
  ["train-model-v3", "diagnose-v3"],
  ["train-model-v3", "shap-v3"],
  ["train-model-v3", "compare-models"],
  ["train-model-v3", "per-segment-performance"],
  ["train-mlp-v3", "compare-models"],
  ["train-gbm-v3", "compare-models"],
  ["weekly-data-slices", "data-drift-monitor"],
  ["data-drift-monitor", "insights-card"],
  ["build-strategies", "roi-ranking"],
  ["build-strategies", "strategy-heatmap"],
  ["build-strategies", "insights-card"],
  ["diagnose-v3", "insights-card"],
  ["shap-v3", "insights-card"],
  ["compare-models", "insights-card"],
  ["per-segment-performance", "insights-card"],
  ["roi-ranking", "insights-card"],
].map(([source, target], i) => ({
  id: `edge-${i}`,
  source: source as string,
  target: target as string,
}));

export const KIND_COLORS: Record<CanvasBlockKind, { bg: string; ring: string; label: string }> = {
  ingest:    { bg: "rgba(99,102,241,0.15)",  ring: "#818cf8", label: "ingest" },
  transform: { bg: "rgba(14,165,233,0.15)",  ring: "#38bdf8", label: "transform" },
  model:     { bg: "rgba(236,72,153,0.18)",  ring: "#f472b6", label: "model" },
  viz:       { bg: "rgba(168,85,247,0.15)",  ring: "#c084fc", label: "viz" },
  validate:  { bg: "rgba(245,158,11,0.15)",  ring: "#fbbf24", label: "validate" },
  strategy:  { bg: "rgba(16,185,129,0.15)",  ring: "#34d399", label: "strategy" },
  report:    { bg: "rgba(244,114,182,0.15)", ring: "#f9a8d4", label: "report" },
  ops:       { bg: "rgba(148,163,184,0.18)", ring: "#94a3b8", label: "ops" },
};

export const blockByName = (name: string) =>
  CANVAS_BLOCKS.find((b) => b.name === name);

export const blockById = (id: string) =>
  CANVAS_BLOCKS.find((b) => b.id === id);

export const CANVAS_EXTENT = {
  minX: Math.min(...CANVAS_BLOCKS.map((b) => b.x)),
  maxX: Math.max(...CANVAS_BLOCKS.map((b) => b.x + b.width)),
  minY: Math.min(...CANVAS_BLOCKS.map((b) => b.y)),
  maxY: Math.max(...CANVAS_BLOCKS.map((b) => b.y + b.height)),
};
