// Formatting helpers — kept tiny so every component imports the same one.
// Source of truth: docs/frontend_ui_spec.md §4.

export const fmtPct = (n: number, digits = 1): string =>
  `${(n * 100).toFixed(digits)}%`;

export const fmtPpt = (n: number, digits = 1): string =>
  `${n >= 0 ? "+" : ""}${(n * 100).toFixed(digits)}pp`;

export const fmtNum = (n: number): string =>
  n.toLocaleString("en-US");

export const fmtCompact = (n: number): string => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
};

export const fmtLift = (n: number): string =>
  n >= 10 ? `${Math.round(n)}×` : `${n.toFixed(1)}×`;

export const fmtUSD = (n: number): string => {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
};

export const fmtMinutes = (n: number): string => {
  if (n < 1) return `${Math.round(n * 60)}s`;
  if (n < 60) return `${Math.round(n)} min`;
  if (n < 60 * 24) return `${(n / 60).toFixed(1)} h`;
  return `${(n / (60 * 24)).toFixed(1)} d`;
};
