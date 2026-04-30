"use client";

import { motion } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { FALLBACK_EDA } from "@/lib/fallbacks";
import { fmtLift, fmtPct } from "@/lib/format";
import LiftBar from "@/components/shared/LiftBar";

export default function DiscoveryCards() {
  const eda = FALLBACK_EDA;
  const maxLift = Math.max(...eda.top_signals.map((s) => s.lift));

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {/* Card 1 — lifetime velocity */}
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
            <span className={`tabular-nums ${ACCENT.cyan.text}`}>{fmtPct(eda.pct_upgrade_same_day, 1)}</span>
          </div>
          <div className="flex justify-between">
            <span>Within 7 days</span>
            <span className={`tabular-nums ${ACCENT.cyan.text}`}>{fmtPct(eda.pct_upgrade_within_7d, 1)}</span>
          </div>
        </div>
        <div className="mt-4 text-xs leading-relaxed text-slate-500">
          Most paying users decide within minutes — the activation window is short, so trigger-based prompts beat slow drip campaigns.
        </div>
      </motion.div>

      {/* Card 2 — top-event lift */}
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className={`glass rounded-2xl border p-6 ${ACCENT.violet.border} md:col-span-2`}
      >
        <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.violet.text}`}>
          Top trigger events
        </div>
        <div className="mt-2 text-sm text-slate-300">
          Reach among upgraders vs non-upgraders, with raw lift
        </div>
        <div className="mt-5 flex flex-col gap-3">
          {eda.top_signals.map((s) => (
            <div key={s.event} className="flex items-center gap-4">
              <div className="w-44 shrink-0 truncate text-sm text-slate-200">{s.label}</div>
              <div className="flex-1">
                <LiftBar lift={s.lift} max={maxLift} />
                <div className="mt-1 flex justify-between text-[10px] text-slate-500">
                  <span>upgrader {fmtPct(s.upgrader_reach, 1)}</span>
                  <span>non {fmtPct(s.non_upgrader_reach, 1)}</span>
                </div>
              </div>
              <div className={`w-14 shrink-0 text-right font-mono text-sm font-semibold tabular-nums ${ACCENT.violet.text}`}>
                {fmtLift(s.lift)}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 text-xs leading-relaxed text-slate-500">
          The credit-limit moment is the strongest signal we have — every Pro pitch should ride this one event.
        </div>
      </motion.div>
    </div>
  );
}
