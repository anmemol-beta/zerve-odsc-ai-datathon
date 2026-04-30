"use client";

import { motion } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { FALLBACK_SHAP } from "@/lib/fallbacks";
import { fmtLift, fmtNum } from "@/lib/format";

export default function FeatureImportance() {
  const items = FALLBACK_SHAP.shap_top;
  const maxShap = Math.max(...items.map((s) => s.mean_abs_shap));

  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
      <div className={`glass rounded-2xl border p-5 ${ACCENT.amber.border}`}>
        <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.amber.text}`}>
          SHAP top-10 · feature importance
        </div>
        <div className="mt-4 space-y-2.5">
          {items.map((s, i) => (
            <ShapRow
              key={s.feature}
              item={s}
              max={maxShap}
              delay={i * 0.05}
            />
          ))}
        </div>
      </div>

      {/* RIGHT — marketing bridge */}
      <div className={`glass rounded-2xl border p-6 ${ACCENT.violet.border}`}>
        <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.violet.text}`}>
          Feature → marketing bridge
        </div>
        <h3 className="mt-2 text-base font-semibold text-slate-100">
          Every signal maps to an action
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-slate-400">
          The top-3 SHAP features each have a corresponding playbook action, with
          target audience size and expected lift estimated from the test cohort.
        </p>

        <div className="mt-4 space-y-3">
          {items.slice(0, 3).map((s, i) => (
            <motion.div
              key={s.feature}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.35, delay: 0.1 + i * 0.08 }}
              className="rounded-lg border border-slate-800 bg-slate-950/50 p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-[10px] tracking-[0.18em] text-amber-400">
                  #{i + 1} · {s.label}
                </span>
                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[9px] tabular-nums text-emerald-300">
                  {fmtLift(s.expected_lift)}
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-300">
                {s.marketing_action}
              </p>
              <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-500">
                <span>
                  target ≈{" "}
                  <span className="text-slate-300 tabular-nums">
                    {fmtNum(s.target_users_estimate)}
                  </span>{" "}
                  users
                </span>
                <span>·</span>
                <span>SHAP {s.mean_abs_shap.toFixed(4)}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ShapRow({
  item,
  max,
  delay,
}: {
  item: typeof FALLBACK_SHAP.shap_top[number];
  max: number;
  delay: number;
}) {
  const pct = item.mean_abs_shap / max;
  const positive = item.direction === "positive";
  return (
    <div className="flex items-center gap-3">
      <div className="w-44 truncate text-xs text-slate-200">{item.label}</div>
      <div className="relative flex-1">
        <div className="h-3 overflow-hidden rounded-full bg-slate-800/60">
          <motion.div
            className={`h-full rounded-full ${
              positive
                ? "bg-gradient-to-r from-amber-500 to-pink-500"
                : "bg-gradient-to-r from-cyan-500 to-violet-500"
            }`}
            initial={{ width: 0 }}
            whileInView={{ width: `${pct * 100}%` }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay }}
          />
        </div>
      </div>
      <div className="w-20 text-right font-mono text-[10px] tabular-nums text-slate-400">
        {item.mean_abs_shap.toFixed(4)}
      </div>
      <div
        className={`w-10 text-right text-[10px] uppercase tracking-[0.12em] ${
          positive ? "text-pink-300" : "text-cyan-300"
        }`}
      >
        {positive ? "+" : "–"}
      </div>
    </div>
  );
}
