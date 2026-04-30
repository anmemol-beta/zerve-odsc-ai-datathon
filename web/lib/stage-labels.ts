// 15-stage funnel ID → human-readable English label.
// Used everywhere a stage is rendered (FunnelView, TransitionHeatmap, LivePredict).
// Source of truth: docs/frontend_ui_spec.md §02 (English-only build).

export const STAGE_LABEL: Record<string, string> = {
  "0.NoEvent":            "No event",
  "1.New":                "Signed up",
  "2.Exploring":          "Exploring",
  "3.Created":            "First create",
  "4.UsedAI":             "Used AI",
  "5.WroteCode":          "Wrote code",
  "6.Integrated":         "Connected tools",
  "7.Engaged":            "Engaged",
  "8.Upgraded":           "Paying — active",
  "9.AtRisk@UsedAI":      "At risk (Used AI)",
  "9.AtRisk@WroteCode":   "At risk (Wrote code)",
  "9.AtRisk@Integrated":  "At risk (Connected)",
  "9.AtRisk@Engaged":     "At risk (Engaged)",
  "9.AtRisk@Upgraded":    "At risk (Paying)",
  "9.Churned@Upgraded":   "Churned (Paying)",
};

// Stage palette — pick a foreground/background per phase of the funnel.
// Used by FunnelView, TransitionHeatmap, LivePredict stage badges.
export const STAGE_COLOR: Record<string, { fg: string; bg: string; ring: string }> = {
  "0.NoEvent":            { fg: "text-slate-400",   bg: "bg-slate-700/30",    ring: "border-slate-600" },
  "1.New":                { fg: "text-indigo-300",  bg: "bg-indigo-500/15",   ring: "border-indigo-400/40" },
  "2.Exploring":          { fg: "text-sky-300",     bg: "bg-sky-500/15",      ring: "border-sky-400/40" },
  "3.Created":            { fg: "text-cyan-300",    bg: "bg-cyan-500/15",     ring: "border-cyan-400/40" },
  "4.UsedAI":             { fg: "text-teal-300",    bg: "bg-teal-500/15",     ring: "border-teal-400/40" },
  "5.WroteCode":          { fg: "text-emerald-300", bg: "bg-emerald-500/15",  ring: "border-emerald-400/40" },
  "6.Integrated":         { fg: "text-lime-300",    bg: "bg-lime-500/15",     ring: "border-lime-400/40" },
  "7.Engaged":            { fg: "text-violet-300",  bg: "bg-violet-500/15",   ring: "border-violet-400/40" },
  "8.Upgraded":           { fg: "text-pink-300",    bg: "bg-pink-500/15",     ring: "border-pink-400/40" },
  "9.AtRisk@UsedAI":      { fg: "text-amber-300",   bg: "bg-amber-500/15",    ring: "border-amber-400/40" },
  "9.AtRisk@WroteCode":   { fg: "text-amber-300",   bg: "bg-amber-500/15",    ring: "border-amber-400/40" },
  "9.AtRisk@Integrated":  { fg: "text-amber-300",   bg: "bg-amber-500/15",    ring: "border-amber-400/40" },
  "9.AtRisk@Engaged":     { fg: "text-amber-300",   bg: "bg-amber-500/15",    ring: "border-amber-400/40" },
  "9.AtRisk@Upgraded":    { fg: "text-orange-300",  bg: "bg-orange-500/15",   ring: "border-orange-400/40" },
  "9.Churned@Upgraded":   { fg: "text-rose-300",    bg: "bg-rose-500/15",     ring: "border-rose-400/40" },
};

export const STAGE_ORDER = [
  "0.NoEvent", "1.New", "2.Exploring", "3.Created", "4.UsedAI",
  "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded",
  "9.AtRisk@UsedAI", "9.AtRisk@WroteCode", "9.AtRisk@Integrated",
  "9.AtRisk@Engaged", "9.AtRisk@Upgraded", "9.Churned@Upgraded",
];
