"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { FALLBACK_EDA } from "@/lib/fallbacks";
import { fmtLift, fmtPct } from "@/lib/format";

export default function DiscoveryCards() {
  const eda = FALLBACK_EDA;

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {/* Card 1 — lifetime velocity (unchanged) */}
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5 }}
        className={`glass rounded-2xl border p-6 ${ACCENT.cyan.border}`}
      >
        <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.cyan.text}`}>
          Velocity
        </div>
        <div className={`mt-3 text-5xl font-black tabular-nums ${ACCENT.cyan.textStrong}`}>
          {eda.median_lifetime_minutes}
          <span className="ml-1 text-xl text-slate-500">min</span>
        </div>
        <div className="mt-2 text-sm text-slate-300">
          Median time from signup to upgrade
        </div>
        <div className="mt-4 flex flex-col gap-2 text-xs text-slate-400">
          <div className="flex justify-between">
            <span>Same-day upgrade</span>
            <span className={`tabular-nums ${ACCENT.cyan.text}`}>
              {fmtPct(eda.pct_upgrade_same_day, 1)}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Within 7 days</span>
            <span className={`tabular-nums ${ACCENT.cyan.text}`}>
              {fmtPct(eda.pct_upgrade_within_7d, 1)}
            </span>
          </div>
        </div>
        <div className="mt-4 text-xs leading-relaxed text-slate-500">
          Most paying users decide within minutes — the activation window is short, so trigger-based prompts beat slow drip campaigns.
        </div>
      </motion.div>

      {/* Card 2 — top-event lift carousel (one event at a time) */}
      <TriggerEventCarousel />
    </div>
  );
}

function TriggerEventCarousel() {
  const events = FALLBACK_EDA.top_signals;
  const [idx, setIdx] = useState(0);
  const [dir, setDir] = useState<1 | -1>(1);
  const total = events.length;
  const cur = events[idx];

  const go = (delta: number) => {
    setDir(delta > 0 ? 1 : -1);
    setIdx((p) => (p + delta + total) % total);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.5, delay: 0.1 }}
      className={`glass rounded-2xl border p-6 ${ACCENT.violet.border} md:col-span-2`}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.violet.text}`}>
            Top trigger events
          </div>
          <div className="mt-1 text-sm text-slate-300">
            Reach among upgraders vs non-upgraders
          </div>
        </div>
        <div className="text-[10px] tabular-nums text-slate-500">
          {idx + 1} / {total}
        </div>
      </div>

      {/* card carousel — one event at a time, slide in from the side */}
      <div className="relative mt-5 h-[200px] overflow-hidden">
        <AnimatePresence initial={false} custom={dir} mode="wait">
          <motion.div
            key={cur.event}
            custom={dir}
            initial={{ opacity: 0, x: dir === 1 ? 80 : -80 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: dir === 1 ? -80 : 80 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="absolute inset-0 flex flex-col justify-center gap-4 rounded-xl border border-slate-700/60 bg-slate-900/40 px-6 py-5"
          >
            <div className="flex items-baseline justify-between gap-3">
              <h4 className="text-2xl font-bold tracking-tight text-slate-50">
                {cur.label}
              </h4>
              <span className={`text-3xl font-black tabular-nums ${ACCENT.violet.textStrong}`}>
                {fmtLift(cur.lift)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <ReachStat
                label="Upgrader reach"
                pct={cur.upgrader_reach}
                accent="violet"
                strong
              />
              <ReachStat
                label="Non-upgrader reach"
                pct={cur.non_upgrader_reach}
                accent="slate"
              />
            </div>
            <BarOverlay
              upgrader={cur.upgrader_reach}
              non={cur.non_upgrader_reach}
            />
          </motion.div>
        </AnimatePresence>
      </div>

      {/* nav row — prev / dots / next */}
      <div className="mt-4 flex items-center justify-between">
        <NavBtn label="‹ Prev" onClick={() => go(-1)} />
        <div className="flex items-center gap-1.5">
          {events.map((e, i) => (
            <button
              key={e.event}
              aria-label={`event ${i + 1}`}
              onClick={() => {
                setDir(i > idx ? 1 : -1);
                setIdx(i);
              }}
              className={`h-1.5 rounded-full transition-all ${
                i === idx ? "w-6 bg-blue-400" : "w-1.5 bg-slate-600 hover:bg-slate-500"
              }`}
            />
          ))}
        </div>
        <NavBtn label="Next ›" onClick={() => go(1)} />
      </div>

      <p className="mt-4 text-xs leading-relaxed text-slate-500">
        The credit-limit moment is the strongest signal we have — every Pro pitch should ride this one event.
      </p>
    </motion.div>
  );
}

function NavBtn({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-md border border-slate-700 bg-slate-900/40 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:border-blue-400/60 hover:bg-blue-500/10 hover:text-blue-100"
    >
      {label}
    </button>
  );
}

function ReachStat({
  label,
  pct,
  accent,
  strong = false,
}: {
  label: string;
  pct: number;
  accent: keyof typeof ACCENT;
  strong?: boolean;
}) {
  const c = ACCENT[accent];
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">
        {label}
      </div>
      <div
        className={`mt-1 tabular-nums font-bold ${strong ? c.textStrong : c.text} ${
          strong ? "text-2xl" : "text-xl"
        }`}
      >
        {fmtPct(pct, 1)}
      </div>
    </div>
  );
}

// Side-by-side proportional bars showing upgrader vs non-upgrader reach,
// scaled to whichever is larger so both bars are always readable.
function BarOverlay({ upgrader, non }: { upgrader: number; non: number }) {
  const max = Math.max(upgrader, non, 0.05);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="w-3 text-[9px] text-slate-500">U</span>
        <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-800/60">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${(upgrader / max) * 100}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-blue-500"
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-3 text-[9px] text-slate-500">N</span>
        <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-800/60">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${(non / max) * 100}%` }}
            transition={{ duration: 0.5, ease: "easeOut", delay: 0.05 }}
            className="h-full rounded-full bg-slate-500/70"
          />
        </div>
      </div>
    </div>
  );
}
