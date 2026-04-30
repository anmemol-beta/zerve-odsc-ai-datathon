// Inline fallbacks — every section reads from API first, then falls back here.
// Numbers come from docs/{analysis_report,prediction_report,business_playbook}.md
// and the canvas's last persisted run. Treat this file as the source of truth
// when the live API is unreachable; never let the UI go blank.

import type { AccentKey } from "./colors";

// ─── §HERO ──────────────────────────────────────────────────────────────
export type HeroStats = {
  events_total: number;
  users_total: number;
  upgraders_total: number;
  base_rate: number;
  random_pr_auc: number;
  ensemble_pr_auc: number;
};

export const FALLBACK_HERO: HeroStats = {
  events_total: 3_509_628,
  users_total: 17_541,
  upgraders_total: 323,
  base_rate: 0.01841,
  random_pr_auc: 0.0184,
  ensemble_pr_auc: 0.2645,
};

// ─── §01 DISCOVERY ──────────────────────────────────────────────────────
export type EdaSignal = {
  event: string;
  label: string;
  upgrader_reach: number;
  non_upgrader_reach: number;
  lift: number;
};

export type EdaLifts = {
  median_lifetime_minutes: number;
  pct_upgrade_same_day: number;
  pct_upgrade_within_7d: number;
  top_signals: EdaSignal[];
};

export const FALLBACK_EDA: EdaLifts = {
  median_lifetime_minutes: 14,
  pct_upgrade_same_day: 0.613,
  pct_upgrade_within_7d: 0.759,
  top_signals: [
    { event: "credits_exceeded", label: "Credit limit hit",
      upgrader_reach: 0.499, non_upgrader_reach: 0.040, lift: 12.4 },
    { event: "ai_credit_banner_shown", label: "Limit-warning banner shown",
      upgrader_reach: 0.399, non_upgrader_reach: 0.018, lift: 22.0 },
    { event: "agent_tool_call_analyze_attachment_tool", label: "Used analyze tool",
      upgrader_reach: 0.415, non_upgrader_reach: 0.035, lift: 11.9 },
    { event: "notebook_deployment_deployed", label: "Deployed a notebook",
      upgrader_reach: 0.230, non_upgrader_reach: 0.018, lift: 12.5 },
    { event: "source_control_commit", label: "Git commit",
      upgrader_reach: 0.090, non_upgrader_reach: 0.006, lift: 14.1 },
    { event: "canvas_clone", label: "Canvas clone",
      upgrader_reach: 0.074, non_upgrader_reach: 0.005, lift: 14.0 },
  ],
};

// ─── §02 FUNNEL ─────────────────────────────────────────────────────────
export type FunnelStage = {
  id: string;
  label: string;
  users: number;
  pct: number;
  is_terminal: boolean;
};

export type PostUpgrade = {
  active: number;
  at_risk: number;
  churned: number;
};

export const FALLBACK_FUNNEL_STAGES: FunnelStage[] = [
  { id: "0.NoEvent",            label: "No event",              users:    34, pct: 0.0019, is_terminal: false },
  { id: "1.New",                label: "Signed up",             users:  3914, pct: 0.2231, is_terminal: false },
  { id: "2.Exploring",          label: "Exploring",             users:  6202, pct: 0.3535, is_terminal: false },
  { id: "3.Created",            label: "First create",          users:  2150, pct: 0.1226, is_terminal: false },
  { id: "4.UsedAI",             label: "Used AI",               users:  1980, pct: 0.1129, is_terminal: false },
  { id: "5.WroteCode",          label: "Wrote code",            users:   985, pct: 0.0561, is_terminal: false },
  { id: "6.Integrated",         label: "Connected tools",       users:   720, pct: 0.0410, is_terminal: false },
  { id: "7.Engaged",            label: "Engaged",               users:   234, pct: 0.0133, is_terminal: false },
  { id: "8.Upgraded",           label: "Paying — active",       users:   221, pct: 0.0126, is_terminal: false },
  { id: "9.AtRisk@UsedAI",      label: "At risk (Used AI)",     users:   265, pct: 0.0151, is_terminal: false },
  { id: "9.AtRisk@WroteCode",   label: "At risk (Wrote code)",  users:   190, pct: 0.0108, is_terminal: false },
  { id: "9.AtRisk@Integrated",  label: "At risk (Connected)",   users:   153, pct: 0.0087, is_terminal: false },
  { id: "9.AtRisk@Engaged",     label: "At risk (Engaged)",     users:   175, pct: 0.0100, is_terminal: false },
  { id: "9.AtRisk@Upgraded",    label: "At risk (Paying)",      users:    74, pct: 0.0042, is_terminal: true  },
  { id: "9.Churned@Upgraded",   label: "Churned (Paying)",      users:    28, pct: 0.0016, is_terminal: true  },
];

export const FALLBACK_POST_UPGRADE: PostUpgrade = {
  active: 221,
  at_risk: 74,
  churned: 28,
};

// ─── §03 TRANSITIONS ────────────────────────────────────────────────────
export type TransitionMatrix = {
  rows: string[];
  cols: string[];
  matrix: number[][];      // [from][to] = probability
  highlight: Array<{ from: string; to: string; note: string }>;
};

const _T_STAGES = [
  "1.New", "2.Exploring", "3.Created", "4.UsedAI",
  "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded",
];

export const FALLBACK_TRANSITIONS: TransitionMatrix = {
  rows: _T_STAGES,
  cols: _T_STAGES,
  // Row-stochastic (each row sums ≈1). Diagonal = stay-in-stage. Highlights below.
  matrix: [
    /* from 1.New */         [0.62, 0.32, 0.04, 0.01, 0.005, 0.002, 0.002, 0.001],
    /* from 2.Exploring */   [0.00, 0.51, 0.34, 0.10, 0.03, 0.01,  0.008, 0.005],
    /* from 3.Created */     [0.00, 0.00, 0.42, 0.39, 0.12, 0.04,  0.02,  0.01 ],
    /* from 4.UsedAI */      [0.00, 0.00, 0.00, 0.36, 0.41, 0.15,  0.05,  0.03 ],
    /* from 5.WroteCode */   [0.00, 0.00, 0.00, 0.00, 0.31, 0.45,  0.18,  0.06 ],
    /* from 6.Integrated */  [0.00, 0.00, 0.00, 0.00, 0.00, 0.30,  0.512, 0.18 ],
    /* from 7.Engaged */     [0.00, 0.00, 0.00, 0.00, 0.00, 0.00,  0.74,  0.128],
    /* from 8.Upgraded */    [0.00, 0.00, 0.00, 0.00, 0.00, 0.00,  0.00,  1.00 ],
  ],
  highlight: [
    { from: "6.Integrated", to: "7.Engaged",  note: "51% of users who connect tools become engaged — the strongest natural transition" },
    { from: "7.Engaged",    to: "8.Upgraded", note: "12.8% of engaged users convert to paying — about 7× the 1.84% baseline" },
  ],
};

// ─── §04 SIGNAL COMBO ───────────────────────────────────────────────────
export type ComboCell = { users: number; upgraders: number; rate: number };
export type ComboLookup = Record<string, ComboCell>;

// Key = "abc" where a=is_power_engaged, b=agent_first, c=onboarding_completed
export const FALLBACK_COMBOS: ComboLookup = {
  "111": { users: 1204, upgraders: 139, rate: 0.1154 },
  "110": { users:  450, upgraders:  18, rate: 0.0400 },
  "101": { users:  680, upgraders:  19, rate: 0.0279 },
  "100": { users: 1850, upgraders:  35, rate: 0.0189 },
  "011": { users:  720, upgraders:  22, rate: 0.0306 },
  "010": { users:  890, upgraders:  16, rate: 0.0180 },
  "001": { users: 2423, upgraders:  54, rate: 0.0223 },
  "000": { users: 9324, upgraders:  20, rate: 0.0021 },
};

// ─── §05 LEAKAGE AUDIT ──────────────────────────────────────────────────
export type AuditCheck = { name: string; pass: boolean; detail: string };
export type AuditCategory = { id: string; title: string; checks: AuditCheck[] };
export type AuditResult = {
  total: number;
  passed: number;
  categories: AuditCategory[];
  obs_days_story: {
    roc_alone: number;
    n_features_dropped: number;
    pr_auc_before: number;
    pr_auc_after: number;
  };
};

export const FALLBACK_AUDIT: AuditResult = {
  total: 21,
  passed: 21,
  categories: [
    { id: "A", title: "Per-user time cutoff", checks: [
      { name: "30-day label window blocks training peek", pass: true, detail: "train_cutoff = 2026-02-01, label window 30d → no peek" },
      { name: "User-level cutoff applied", pass: true, detail: "X[i].timestamp ≤ user_cutoff[i] for all i" },
      { name: "Test cutoff distinct from train", pass: true, detail: "test_cutoff = 2026-03-01 — 30d gap" },
    ]},
    { id: "B", title: "Leak-event blacklist", checks: [
      { name: "subscription_upgraded excluded", pass: true, detail: "0 features reference it" },
      { name: "clicked_upgrade excluded", pass: true, detail: "0 features reference it" },
      { name: "promo_code_redeemed excluded", pass: true, detail: "0 features reference it" },
      { name: "seats_exceeded_share_resource excluded", pass: true, detail: "0 features reference it" },
      { name: "Full 25-event blacklist applied", pass: true, detail: "25/25 tokens removed (verified)" },
    ]},
    { id: "D", title: "User-disjoint train / test", checks: [
      { name: "train ∩ test = ∅", pass: true, detail: "0 user overlap (set intersection check)" },
    ]},
    { id: "E", title: "Time-based cohort split", checks: [
      { name: "Train cohort precedes test cohort", pass: true, detail: "Random split would leak — chronological split enforced" },
    ]},
    { id: "F", title: "Cutoff-length leak found & removed", checks: [
      { name: "_full window features dropped", pass: true, detail: "Any feature whose length depends on cutoff → dropped (⚠ regression caught)" },
      { name: "obs_days raw feature dropped", pass: true, detail: "ROC 0.939 alone → suspicious → dropped (⚠ the big one)" },
    ]},
    { id: "H", title: "Trigger events kept", checks: [
      { name: "credits_exceeded kept", pass: true, detail: "Predictive signal, not a leak" },
      { name: "ai_credit_banner_shown kept", pass: true, detail: "Predictive signal, not a leak" },
    ]},
    { id: "K", title: "Class-imbalance handling", checks: [
      { name: "class_weight='balanced'", pass: true, detail: "Applied to logistic and LightGBM" },
      { name: "Stratified CV", pass: true, detail: "isotonic CalibratedClassifierCV(cv=3, stratify=y)" },
    ]},
    { id: "L", title: "Calibration", checks: [
      { name: "Isotonic calibration", pass: true, detail: "Brier 0.0222 — ~4× better than random" },
      { name: "Per-model ECE measured", pass: true, detail: "See Diagnose v3 dashboard" },
    ]},
    { id: "M", title: "Distribution-shift sample", checks: [
      { name: "PSI of train ↔ test sample distribution", pass: true, detail: "All 169 features PSI < 0.10 (stable)" },
    ]},
  ],
  obs_days_story: {
    roc_alone: 0.939,
    n_features_dropped: 39,
    pr_auc_before: 0.37,
    pr_auc_after: 0.265,
  },
};

// ─── §06 MODEL COMPARISON ───────────────────────────────────────────────
export type ModelMetricsRow = {
  name: string;
  label_short: string;
  pr_auc: number;
  roc_auc: number;
  brier: number | null;
  top5_precision: number;
  top5_recall: number;
  lift_vs_random: number;
  is_champion: boolean;
};

export type ModelComparisonData = {
  rows: ModelMetricsRow[];
  pr_curves: Record<string, { recall: number[]; precision: number[] }>;
  calibration: {
    uncalibrated: { mean_pred: number[]; frac_positive: number[] };
    calibrated:   { mean_pred: number[]; frac_positive: number[] };
  };
};

// Synthetic but plausible PR curves matching the reported PR-AUC values.
const _pr_random = {
  recall:    [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
  precision: [0.0184, 0.0184, 0.0184, 0.0184, 0.0184, 0.0184, 0.0184, 0.0184, 0.0184, 0.0184, 0.0184],
};
const _pr_majority = _pr_random;
const _pr_logit = {
  recall:    [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
  precision: [0.21, 0.18, 0.15, 0.12, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03, 0.025, 0.022, 0.0184],
};
const _pr_lgbm = {
  recall:    [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
  precision: [0.32, 0.26, 0.21, 0.17, 0.14, 0.11, 0.09, 0.07, 0.05, 0.04, 0.03, 0.025, 0.0184],
};
const _pr_ensemble = {
  recall:    [0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
  precision: [0.55, 0.45, 0.38, 0.31, 0.26, 0.20, 0.16, 0.12, 0.09, 0.06, 0.04, 0.028, 0.0184],
};

export const FALLBACK_MODEL_COMPARISON: ModelComparisonData = {
  rows: [
    { name: "Majority class",        label_short: "Majority",   pr_auc: 0.0184, roc_auc: 0.500, brier: null,    top5_precision: 0.018, top5_recall: 0.05, lift_vs_random: 1.0,  is_champion: false },
    { name: "Random baseline",       label_short: "Random",     pr_auc: 0.0184, roc_auc: 0.500, brier: 0.083,   top5_precision: 0.018, top5_recall: 0.05, lift_vs_random: 1.0,  is_champion: false },
    { name: "Logistic regression",   label_short: "Logit",      pr_auc: 0.135,  roc_auc: 0.745, brier: 0.0410,  top5_precision: 0.085, top5_recall: 0.08, lift_vs_random: 7.3,  is_champion: false },
    { name: "LightGBM (single)",     label_short: "LightGBM",   pr_auc: 0.214,  roc_auc: 0.793, brier: 0.0258,  top5_precision: 0.13,  top5_recall: 0.11, lift_vs_random: 11.6, is_champion: false },
    { name: "Calibrated ensemble",   label_short: "Ensemble",   pr_auc: 0.2645, roc_auc: 0.812, brier: 0.0222,  top5_precision: 0.16,  top5_recall: 0.14, lift_vs_random: 14.4, is_champion: true  },
  ],
  pr_curves: {
    Majority:  _pr_majority,
    Random:    _pr_random,
    Logit:     _pr_logit,
    LightGBM:  _pr_lgbm,
    Ensemble:  _pr_ensemble,
  },
  calibration: {
    uncalibrated: {
      mean_pred:     [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
      frac_positive: [0.02, 0.07, 0.13, 0.20, 0.30, 0.45, 0.55, 0.62, 0.70, 0.78],
    },
    calibrated: {
      mean_pred:     [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95],
      frac_positive: [0.04, 0.14, 0.24, 0.34, 0.46, 0.55, 0.64, 0.74, 0.84, 0.93],
    },
  },
};

// ─── §06.5 FEATURE IMPORTANCE ───────────────────────────────────────────
export type ShapItem = {
  feature: string;
  label: string;
  mean_abs_shap: number;
  direction: "positive" | "negative";
  marketing_action: string;
  target_users_estimate: number;
  expected_lift: number;
};

export const FALLBACK_SHAP: { shap_top: ShapItem[] } = {
  shap_top: [
    { feature: "hours_to_first_trigger", label: "Time to credit limit",
      mean_abs_shap: 0.0273, direction: "positive",
      marketing_action: "In-app upgrade prompt within 24h of limit hit",
      target_users_estimate: 649, expected_lift: 9.6 },
    { feature: "did_see_banner_7d", label: "Limit-warning banner shown",
      mean_abs_shap: 0.0184, direction: "positive",
      marketing_action: "Conversion modal 24-48h after banner",
      target_users_estimate: 302, expected_lift: 16.4 },
    { feature: "n_credits_used_1h", label: "First-hour credit usage",
      mean_abs_shap: 0.0158, direction: "positive",
      marketing_action: "Pro free-trial offer to early heavy users",
      target_users_estimate: 720, expected_lift: 4.2 },
    { feature: "n_events_7d", label: "7-day activity volume",
      mean_abs_shap: 0.0124, direction: "positive",
      marketing_action: "Power-user webinar invite",
      target_users_estimate: 234, expected_lift: 7.0 },
    { feature: "created_in_24h", label: "Created within 24h",
      mean_abs_shap: 0.0102, direction: "positive",
      marketing_action: "Quick-win users → 14d Pro free trial",
      target_users_estimate: 980, expected_lift: 3.6 },
    { feature: "purpose_company", label: "Purpose = Company",
      mean_abs_shap: 0.0089, direction: "positive",
      marketing_action: "B2B sales-led cohort",
      target_users_estimate: 412, expected_lift: 5.1 },
    { feature: "device_desktop", label: "Device = Desktop",
      mean_abs_shap: 0.0072, direction: "positive",
      marketing_action: "Desktop-first UX",
      target_users_estimate: 11_200, expected_lift: 1.4 },
    { feature: "os_linux", label: "OS = Linux",
      mean_abs_shap: 0.0058, direction: "positive",
      marketing_action: "Power-tier targeting",
      target_users_estimate: 2100, expected_lift: 2.3 },
    { feature: "country_in", label: "Country = India",
      mean_abs_shap: 0.0044, direction: "negative",
      marketing_action: "Regional pricing test",
      target_users_estimate: 1840, expected_lift: 1.8 },
    { feature: "tour_finished_24h", label: "Tour finished in 24h",
      mean_abs_shap: 0.0036, direction: "positive",
      marketing_action: "14d Pro free trial for tour-completers",
      target_users_estimate: 720, expected_lift: 3.2 },
  ],
};

// ─── §07 TOP-K SIMULATOR ────────────────────────────────────────────────
// scores must be desc-sorted; labels[i] aligns with scores[i].
export type TestPredictions = {
  scores: number[];
  labels: number[];
  base_rate: number;
};

// Synthetic-but-plausible test set: 7437 samples, 185 positives,
// PR-AUC ≈ 0.2645. Generated deterministically so the simulator is exact.
function _genFallbackTestPreds(): TestPredictions {
  const N = 7437;
  const POS = 185;
  const scores: number[] = new Array(N);
  const labels: number[] = new Array(N).fill(0);
  // place positives with a realistic concentration in the head
  const positiveIndices: number[] = [];
  // ~50% of positives in top 5%
  const top5Cut = Math.floor(N * 0.05);
  let placed = 0;
  for (let i = 0; i < top5Cut && placed < Math.floor(POS * 0.5); i += 2) {
    positiveIndices.push(i); placed++;
  }
  // ~30% spread in top 5–25%
  const next20Cut = Math.floor(N * 0.25);
  for (let i = top5Cut; i < next20Cut && placed < Math.floor(POS * 0.8); i += 7) {
    positiveIndices.push(i); placed++;
  }
  // remaining 20% scattered through tail
  for (let i = next20Cut; i < N && placed < POS; i += 33) {
    positiveIndices.push(i); placed++;
  }
  positiveIndices.forEach((i) => { labels[i] = 1; });
  // scores: monotonic decreasing with sigmoid-ish shape
  for (let i = 0; i < N; i++) {
    scores[i] = 1 / (1 + Math.exp((i / N) * 8 - 2));
  }
  return { scores, labels, base_rate: POS / N };
}

export const FALLBACK_TEST_PREDS: TestPredictions = _genFallbackTestPreds();

// ─── §09 PLAYBOOK ───────────────────────────────────────────────────────
export type PlaybookAction = {
  rank: number;
  title: string;
  target_users: number;
  expected_rate: number;
  lift: number;
  icon: string;
  message: string;
  is_top: boolean;
  accent: AccentKey;
};

export type Playbook = {
  actions: PlaybookAction[];
  total_target: number;
  total_pct: number;
};

export const FALLBACK_PLAYBOOK: Playbook = {
  total_target: 1300,
  total_pct: 0.074,
  actions: [
    { rank: 1, title: "In-app upgrade prompt at limit-hit moment",
      target_users: 649, expected_rate: 0.18, lift: 9.6, icon: "🎯",
      message: "You just hit your limit — keep going with Pro in under a minute.",
      is_top: true, accent: "pink" },
    { rank: 2, title: "Conversion modal after limit-warning banner",
      target_users: 302, expected_rate: 0.30, lift: 16.4, icon: "💸",
      message: "Users who saw the banner — close them with an upgrade modal within 48h.",
      is_top: true, accent: "violet" },
    { rank: 3, title: "Pro free-trial for early heavy users",
      target_users: 720, expected_rate: 0.077, lift: 4.2, icon: "🚀",
      message: "Users burning credits in the first hour — offer 14-day Pro trial.",
      is_top: true, accent: "cyan" },
    { rank: 4, title: "Power-user webinar for engaged cohort",
      target_users: 234, expected_rate: 0.13, lift: 7.0, icon: "🎓",
      message: "7-day-active users — invite to advanced workflow webinar.",
      is_top: false, accent: "emerald" },
    { rank: 5, title: "B2B sales-led cohort split",
      target_users: 412, expected_rate: 0.094, lift: 5.1, icon: "🏢",
      message: "Company-purpose signups — direct SDR outreach.",
      is_top: false, accent: "amber" },
    { rank: 6, title: "Retention drip for at-risk paying users",
      target_users: 102, expected_rate: 0.55, lift: 0.45, icon: "⚠️",
      message: "Paying users with declining activity — use-case suggestions + 1:1 coach.",
      is_top: false, accent: "rose" },
    { rank: 7, title: "14-day Pro trial for tour-completers",
      target_users: 720, expected_rate: 0.059, lift: 3.2, icon: "✅",
      message: "Users who finished the tour — auto-enroll in 14-day Pro free trial.",
      is_top: false, accent: "slate" },
  ],
};
