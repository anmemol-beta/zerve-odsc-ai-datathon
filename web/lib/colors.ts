// Accent tokens — Zerve-aligned light theme.
// Cards live on white, so accent text needs to be 600-700 for contrast and
// accent fills are 50-100 tints. Borders are 200 (subtle) so the layout reads
// like the Zerve landing page rather than our previous neon glow.

export const ACCENT = {
  pink:    {
    text: "text-pink-600",
    textStrong: "text-pink-700",
    bg: "bg-pink-50",
    bgStrong: "bg-pink-100",
    border: "border-pink-200",
    glow: "shadow-[0_4px_16px_rgba(236,72,153,0.10)]",
    raw: "#ec4899",
  },
  violet:  {
    text: "text-violet-600",
    textStrong: "text-violet-700",
    bg: "bg-violet-50",
    bgStrong: "bg-violet-100",
    border: "border-violet-200",
    glow: "shadow-[0_4px_16px_rgba(139,92,246,0.10)]",
    raw: "#8b5cf6",
  },
  cyan:    {
    text: "text-cyan-700",
    textStrong: "text-cyan-800",
    bg: "bg-cyan-50",
    bgStrong: "bg-cyan-100",
    border: "border-cyan-200",
    glow: "shadow-[0_4px_16px_rgba(6,182,212,0.10)]",
    raw: "#0e7490",
  },
  amber:   {
    text: "text-amber-700",
    textStrong: "text-amber-800",
    bg: "bg-amber-50",
    bgStrong: "bg-amber-100",
    border: "border-amber-200",
    glow: "shadow-[0_4px_16px_rgba(217,119,6,0.10)]",
    raw: "#d97706",
  },
  emerald: {
    text: "text-emerald-700",
    textStrong: "text-emerald-800",
    bg: "bg-emerald-50",
    bgStrong: "bg-emerald-100",
    border: "border-emerald-200",
    glow: "shadow-[0_4px_16px_rgba(16,185,129,0.10)]",
    raw: "#10b981",
  },
  rose:    {
    text: "text-rose-600",
    textStrong: "text-rose-700",
    bg: "bg-rose-50",
    bgStrong: "bg-rose-100",
    border: "border-rose-200",
    glow: "shadow-[0_4px_16px_rgba(244,63,94,0.10)]",
    raw: "#f43f5e",
  },
  slate:   {
    text: "text-slate-600",
    textStrong: "text-slate-800",
    bg: "bg-slate-50",
    bgStrong: "bg-slate-100",
    border: "border-slate-200",
    glow: "shadow-[0_4px_16px_rgba(15,23,42,0.06)]",
    raw: "#475569",
  },
} as const;

export type AccentKey = keyof typeof ACCENT;
