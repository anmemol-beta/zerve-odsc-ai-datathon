export type Stage =
  | "1_signed_up"
  | "2_active"
  | "3_created_content"
  | "4_used_ai"
  | "5_engaged"
  | "5b_at_risk"
  | "6_upgraded";

export const STAGE_COLORS: Record<Stage, string> = {
  "1_signed_up":       "#475569",
  "2_active":          "#3b82f6",
  "3_created_content": "#06b6d4",
  "4_used_ai":         "#10b981",
  "5_engaged":         "#84cc16",
  "5b_at_risk":        "#f59e0b",
  "6_upgraded":        "#ec4899",
};

export const STAGE_LABELS: Record<Stage, string> = {
  "1_signed_up":       "signed up",
  "2_active":          "active",
  "3_created_content": "created content",
  "4_used_ai":         "used AI",
  "5_engaged":         "engaged",
  "5b_at_risk":        "at risk",
  "6_upgraded":        "upgraded",
};

export type Headline = {
  n_users: number;
  n_events: number;
  n_engaged: number;
  n_upgraded: number;
  n_at_risk: number;
  n_event_types: number;
  time_min: string;
  time_max: string;
  base_upgrade_rate: number;
};

export type ManifoldPoint = {
  id: string;
  x: number; y: number; z: number;
  prob: number;
  stage: Stage;
};

export type Manifold = {
  explained_variance: number[];
  points: ManifoldPoint[];
};

export type ShapItem = { feature: string; value: number; shap: number };
export type UserRow  = { id: string; stage: Stage; prob: number; shap: ShapItem[] };

export type FunnelGridEntry = { s: number; d: number; a: number; r: number[] };
export type FunnelGrid = {
  signin_values: number[];
  days_values: number[];
  ai_values: number[];
  total: number;
  grid: FunnelGridEntry[];
};

export type TopEvent = { event: string; count: number };

export type CohortPoint = {
  week: string;
  n: number;
  active_pct: number;
  created_pct: number;
  ai_pct: number;
  engaged_pct: number;
  at_risk_pct: number;
  upgraded_pct: number;
  cum_n: number;
  cum_active: number;
  cum_created: number;
  cum_ai: number;
  cum_engaged: number;
  cum_at_risk: number;
  cum_upgraded: number;
  cum_upgrade_rate: number;
};

export type CohortEvolution = {
  cohorts: CohortPoint[];
  total_users: number;
  total_upgraded: number;
};
