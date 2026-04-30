"use client";

import { motion } from "framer-motion";
import AnimatedNumber from "./AnimatedNumber";
import { ACCENT, type AccentKey } from "@/lib/colors";
import { FALLBACK_HERO } from "@/lib/fallbacks";
import { fmtCompact, fmtNum, fmtPct } from "@/lib/format";

type Stat = {
  big: number;
  format: (n: number) => string;
  label: string;
  detail: string;
  accent: AccentKey;
  glow?: boolean;
};

export default function HeroStats() {
  const h = FALLBACK_HERO;
  const lift = h.ensemble_pr_auc / h.random_pr_auc;

  const stats: Stat[] = [
    {
      big: h.events_total,
      format: fmtCompact,
      label: "Events ingested",
      detail: `${fmtNum(h.users_total)} users · 228 days`,
      accent: "cyan",
    },
    {
      big: h.upgraders_total,
      format: (n) => fmtNum(Math.round(n)),
      label: "Upgraders",
      detail: `Base rate ${fmtPct(h.base_rate, 2)}`,
      accent: "violet",
    },
    {
      big: h.ensemble_pr_auc,
      format: (n) => n.toFixed(3),
      label: "Ensemble PR-AUC",
      detail: `Random baseline ${h.random_pr_auc.toFixed(3)}`,
      accent: "pink",
      glow: true,
    },
    {
      big: lift,
      format: (n) => `${n.toFixed(1)}×`,
      label: "Lift vs random",
      detail: "Calibrated XGB · isotonic CV",
      accent: "emerald",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {stats.map((s, i) => (
        <motion.div
          key={s.label}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 1.6 + i * 0.08, ease: [0.22, 1, 0.36, 1] }}
        >
          <StatTile {...s} />
        </motion.div>
      ))}
    </div>
  );
}

function StatTile({ big, format, label, detail, accent, glow }: Stat) {
  const c = ACCENT[accent];
  return (
    <div className={`glass rounded-xl border p-5 ${c.border} ${glow ? c.glow : ""}`}>
      <div className={`text-3xl font-bold tabular-nums ${c.text} md:text-4xl`}>
        <AnimatedNumber value={big} format={format} />
      </div>
      <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-slate-400">
        {label}
      </div>
      <div className="mt-2 text-xs text-slate-500">{detail}</div>
    </div>
  );
}
