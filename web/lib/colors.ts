// Accent tokens — keep every component's color choices anchored here so
// the palette stays coherent across the 11 sections.
// Source of truth: docs/frontend_ui_spec.md §4.

export const ACCENT = {
  pink:    {
    text: "text-pink-300",
    textStrong: "text-pink-200",
    bg: "bg-pink-500/10",
    bgStrong: "bg-pink-500/20",
    border: "border-pink-400/40",
    glow: "shadow-[0_0_30px_rgba(236,72,153,0.25)]",
    raw: "#ec4899",
  },
  violet:  {
    text: "text-violet-300",
    textStrong: "text-violet-200",
    bg: "bg-violet-500/10",
    bgStrong: "bg-violet-500/20",
    border: "border-violet-400/40",
    glow: "shadow-[0_0_30px_rgba(139,92,246,0.25)]",
    raw: "#8b5cf6",
  },
  cyan:    {
    text: "text-cyan-300",
    textStrong: "text-cyan-200",
    bg: "bg-cyan-500/10",
    bgStrong: "bg-cyan-500/20",
    border: "border-cyan-400/40",
    glow: "shadow-[0_0_30px_rgba(34,211,238,0.25)]",
    raw: "#22d3ee",
  },
  amber:   {
    text: "text-amber-300",
    textStrong: "text-amber-200",
    bg: "bg-amber-500/10",
    bgStrong: "bg-amber-500/20",
    border: "border-amber-400/40",
    glow: "shadow-[0_0_30px_rgba(251,191,36,0.25)]",
    raw: "#fbbf24",
  },
  emerald: {
    text: "text-emerald-300",
    textStrong: "text-emerald-200",
    bg: "bg-emerald-500/10",
    bgStrong: "bg-emerald-500/20",
    border: "border-emerald-400/40",
    glow: "shadow-[0_0_30px_rgba(16,185,129,0.25)]",
    raw: "#10b981",
  },
  rose:    {
    text: "text-rose-300",
    textStrong: "text-rose-200",
    bg: "bg-rose-500/10",
    bgStrong: "bg-rose-500/20",
    border: "border-rose-400/40",
    glow: "shadow-[0_0_30px_rgba(244,63,94,0.25)]",
    raw: "#f43f5e",
  },
  slate:   {
    text: "text-slate-300",
    textStrong: "text-slate-200",
    bg: "bg-slate-500/10",
    bgStrong: "bg-slate-500/20",
    border: "border-slate-600",
    glow: "shadow-[0_0_30px_rgba(100,116,139,0.20)]",
    raw: "#64748b",
  },
} as const;

export type AccentKey = keyof typeof ACCENT;
