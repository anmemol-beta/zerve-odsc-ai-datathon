"use client";

import { ACCENT, type AccentKey } from "@/lib/colors";

export default function StatCard({
  big,
  label,
  detail,
  accent = "pink",
  glow = false,
}: {
  big: React.ReactNode;
  label: string;
  detail?: string;
  accent?: AccentKey;
  glow?: boolean;
}) {
  const c = ACCENT[accent];
  return (
    <div
      className={`glass rounded-xl border p-5 ${c.border} ${glow ? c.glow : ""}`}
    >
      <div className={`text-3xl font-bold tabular-nums ${c.text}`}>{big}</div>
      <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-slate-400">
        {label}
      </div>
      {detail && <div className="mt-2 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}
