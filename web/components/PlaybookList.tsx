"use client";

import { motion } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { FALLBACK_PLAYBOOK } from "@/lib/fallbacks";
import { fmtLift, fmtNum, fmtPct } from "@/lib/format";

export default function PlaybookList() {
  const p = FALLBACK_PLAYBOOK;
  return (
    <div className="space-y-5">
      <Header total={p.total_target} pct={p.total_pct} />
      <div className="space-y-3">
        {p.actions.map((a, i) => (
          <PlaybookRow key={a.rank} action={a} delay={i * 0.05} />
        ))}
      </div>
    </div>
  );
}

function Header({ total, pct }: { total: number; pct: number }) {
  return (
    <div className={`glass rounded-2xl border p-5 ${ACCENT.pink.border}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.pink.text}`}>
            Playbook · 7 ranked actions
          </div>
          <h3 className="mt-1 text-lg font-semibold text-slate-100">
            {fmtNum(total)} users targeted ({fmtPct(pct, 1)} of base)
          </h3>
        </div>
        <p className="max-w-md text-xs leading-relaxed text-slate-400">
          ROI-ranked. Top-3 bands are the must-ship moves; the rest improve
          retention and B2B conversion. Every row maps to a SHAP-positive feature.
        </p>
      </div>
    </div>
  );
}

function PlaybookRow({
  action,
  delay,
}: {
  action: typeof FALLBACK_PLAYBOOK.actions[number];
  delay: number;
}) {
  const c = ACCENT[action.accent];
  const liftBarPct = Math.min(1, action.lift / 20);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.4, delay }}
      className={`glass rounded-xl border p-5 ${c.border} ${
        action.is_top ? c.glow : ""
      }`}
    >
      <div className="flex items-start gap-4">
        <div className="flex flex-col items-center gap-1.5">
          <span className={`font-mono text-[10px] tracking-[0.18em] ${c.text}`}>
            #{action.rank}
          </span>
          <span className="text-3xl">{action.icon}</span>
          {action.is_top && (
            <span className="rounded-full bg-pink-500/20 px-2 py-0.5 text-[8px] uppercase tracking-[0.18em] text-pink-300">
              top
            </span>
          )}
        </div>

        <div className="flex-1">
          <h4 className="text-base font-semibold text-slate-100">{action.title}</h4>
          <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
            {action.message}
          </p>

          <div className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-4">
            <Metric label="Target" value={fmtNum(action.target_users)} accent="slate" />
            <Metric
              label="Expected rate"
              value={fmtPct(action.expected_rate, 1)}
              accent={action.accent}
            />
            <Metric
              label="Lift"
              value={fmtLift(action.lift)}
              accent={action.lift >= 5 ? "emerald" : "slate"}
            />
            <div className="col-span-3 sm:col-span-1">
              <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">
                vs baseline
              </div>
              <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-800">
                <motion.div
                  className={`h-full ${c.bgStrong}`}
                  initial={{ width: 0 }}
                  whileInView={{ width: `${liftBarPct * 100}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.8, delay: delay + 0.2 }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: keyof typeof ACCENT;
}) {
  const c = ACCENT[accent];
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`mt-0.5 text-base font-semibold tabular-nums ${c.text}`}>
        {value}
      </div>
    </div>
  );
}
