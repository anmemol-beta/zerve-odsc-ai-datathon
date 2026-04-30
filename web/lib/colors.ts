// Accent tokens — Zerve dark theme.
// Brand chord: blue (primary) + cyan (accent) + sky/teal (supporting). Pink/
// violet/amber kept as semantic highlights (alerts, segments) but at lower
// saturation than the previous cyberpunk palette. Cards live on slate-800,
// so accent text uses 300 (good contrast) and fills are 500/15 alpha overlays.
// Glow is muted — soft elevation shadow rather than 30px neon halo.

export const ACCENT = {
  // "pink" → primary blue (Zerve brand). Kept under the "pink" key so existing
  // components that hardcode `accent="pink"` automatically pick up the new
  // brand color without touching the call sites.
  pink:    {
    text: "text-blue-300",
    textStrong: "text-blue-200",
    bg: "bg-blue-500/15",
    bgStrong: "bg-blue-500/25",
    border: "border-blue-500/40",
    glow: "shadow-[0_2px_18px_rgba(59,130,246,0.18)]",
    raw: "#3b82f6",
  },
  violet:  {
    text: "text-indigo-300",
    textStrong: "text-indigo-200",
    bg: "bg-indigo-500/15",
    bgStrong: "bg-indigo-500/25",
    border: "border-indigo-500/40",
    glow: "shadow-[0_2px_18px_rgba(99,102,241,0.18)]",
    raw: "#6366f1",
  },
  cyan:    {
    text: "text-cyan-300",
    textStrong: "text-cyan-200",
    bg: "bg-cyan-500/15",
    bgStrong: "bg-cyan-500/25",
    border: "border-cyan-500/40",
    glow: "shadow-[0_2px_18px_rgba(34,211,238,0.18)]",
    raw: "#22d3ee",
  },
  amber:   {
    text: "text-amber-300",
    textStrong: "text-amber-200",
    bg: "bg-amber-500/15",
    bgStrong: "bg-amber-500/25",
    border: "border-amber-500/40",
    glow: "shadow-[0_2px_18px_rgba(245,158,11,0.18)]",
    raw: "#f59e0b",
  },
  emerald: {
    text: "text-emerald-300",
    textStrong: "text-emerald-200",
    bg: "bg-emerald-500/15",
    bgStrong: "bg-emerald-500/25",
    border: "border-emerald-500/40",
    glow: "shadow-[0_2px_18px_rgba(16,185,129,0.18)]",
    raw: "#10b981",
  },
  rose:    {
    text: "text-rose-300",
    textStrong: "text-rose-200",
    bg: "bg-rose-500/15",
    bgStrong: "bg-rose-500/25",
    border: "border-rose-500/40",
    glow: "shadow-[0_2px_18px_rgba(244,63,94,0.18)]",
    raw: "#f43f5e",
  },
  slate:   {
    text: "text-slate-300",
    textStrong: "text-slate-100",
    bg: "bg-slate-700/40",
    bgStrong: "bg-slate-700/60",
    border: "border-slate-600",
    glow: "shadow-[0_2px_12px_rgba(0,0,0,0.30)]",
    raw: "#64748b",
  },
} as const;

export type AccentKey = keyof typeof ACCENT;
