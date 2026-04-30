// Zerve deployment API client.
// In production the frontend ships inside the same FastAPI container that
// exposes these endpoints (zerve_deploy/main.py mounts web/out at /), so the
// default base is the empty string — every request becomes same-origin and
// CORS never enters the picture.
//
// For local `npm run dev`, set NEXT_PUBLIC_API_URL=https://beta-zerve.hub.zerve.cloud
// (or whatever your dev backend is) so the dev server can talk to a remote API.
const RAW = process.env.NEXT_PUBLIC_API_URL;
export const API_BASE =
  RAW && RAW.length > 0 ? RAW.replace(/\/$/, "") : "";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, `${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, `${path} → ${res.status}`);
  return res.json();
}

export const api = {
  health:        () => get<{ ok: boolean }>("/health"),
  dag:           () => get<Record<string, string[]>>("/dag"),
  metrics:       () => get<Array<Record<string, unknown>>>("/metrics"),
  strategies:    () => get<unknown>("/strategies"),
  strategySegments: () => get<unknown>("/strategies/segments"),
  roiTop10:      () => get<Array<Record<string, unknown>>>("/roi/top10"),
  roiHeatmap:    () => get<Array<Record<string, unknown>>>("/roi/heatmap"),
  insights:      () => get<{ text: string; payload: unknown }>("/insights"),
  validate:      (block: string) => get<unknown>(`/validate/${encodeURIComponent(block)}`),
  predict:       (features: number[][]) =>
    post<{ upgrade_probability: number[] }>("/predict", { features }),
  predictSample: (idx: number) =>
    get<{
      idx: number;
      n_test: number;
      upgrade_probability: number;
      actual_label: number;
      feature_count: number;
    }>(`/predict/sample/${idx}`),
  reload:        () => post<{ ok: boolean }>("/admin/reload"),
  blockVars:     (block: string) =>
    get<Record<string, unknown>>(`/block/${encodeURIComponent(block)}/vars`),
  champion:      () => get<{
    current: string;
    summary: unknown;
    win_counts: unknown;
    per_cohort: unknown;
  }>("/champion"),
  rollingMetrics: () => get<Array<Record<string, unknown>>>("/rolling/metrics"),
  perfDrift:     () => get<{ summary: unknown; alerts: unknown }>("/drift/performance"),
  dataDrift:     () => get<{
    weekly_index: unknown;
    alerts: unknown;
    baseline_id: unknown;
  }>("/drift/data"),
  weeklyInference: () => get<{ summary: unknown; by_stage: unknown }>("/inference/weekly"),
};

export const figureUrl = (block: string, bust?: number | string) =>
  `${API_BASE}/figure/${encodeURIComponent(block)}` +
  (bust !== undefined ? `?t=${bust}` : "");
