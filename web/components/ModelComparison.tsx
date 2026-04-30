"use client";

import { motion } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { FALLBACK_MODEL_COMPARISON } from "@/lib/fallbacks";
import { fmtLift, fmtPct } from "@/lib/format";

const MODEL_COLOR: Record<string, string> = {
  Majority: "#64748b",
  Random:   "#94a3b8",
  Logit:    "#22d3ee",
  LightGBM: "#8b5cf6",
  Ensemble: "#ec4899",
};

export default function ModelComparison() {
  const data = FALLBACK_MODEL_COMPARISON;
  return (
    <div className="space-y-6">
      <ModelTable rows={data.rows} />
      <div className="grid gap-6 lg:grid-cols-2">
        <PRCurves curves={data.pr_curves} />
        <CalibrationPlot calibration={data.calibration} />
      </div>
    </div>
  );
}

function ModelTable({ rows }: { rows: typeof FALLBACK_MODEL_COMPARISON.rows }) {
  return (
    <div className={`glass overflow-hidden rounded-2xl border ${ACCENT.violet.border}`}>
      <table className="w-full text-sm">
        <thead className="bg-slate-900/60 text-[10px] uppercase tracking-[0.18em] text-slate-400">
          <tr>
            <th className="px-4 py-3 text-left">Model</th>
            <th className="px-3 py-3 text-right">PR-AUC</th>
            <th className="px-3 py-3 text-right">ROC-AUC</th>
            <th className="px-3 py-3 text-right">Brier</th>
            <th className="px-3 py-3 text-right">Top-5% prec.</th>
            <th className="px-3 py-3 text-right">Lift vs random</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <motion.tr
              key={r.name}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.06 }}
              className={`border-t border-slate-700/50 ${
                r.is_champion ? "bg-pink-500/15" : ""
              }`}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2.5">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: MODEL_COLOR[r.label_short] ?? "#64748b" }}
                  />
                  <span
                    className={
                      r.is_champion ? "font-semibold text-pink-200" : "text-slate-200"
                    }
                  >
                    {r.name}
                  </span>
                  {r.is_champion && (
                    <span className="rounded-full bg-pink-500/15 px-2 py-0.5 text-[9px] uppercase tracking-[0.18em] text-pink-300">
                      champion
                    </span>
                  )}
                </div>
              </td>
              <td className="px-3 py-3 text-right font-mono tabular-nums text-slate-200">
                {r.pr_auc.toFixed(3)}
              </td>
              <td className="px-3 py-3 text-right font-mono tabular-nums text-slate-300">
                {r.roc_auc.toFixed(3)}
              </td>
              <td className="px-3 py-3 text-right font-mono tabular-nums text-slate-400">
                {r.brier !== null ? r.brier.toFixed(4) : "—"}
              </td>
              <td className="px-3 py-3 text-right font-mono tabular-nums text-slate-300">
                {fmtPct(r.top5_precision, 1)}
              </td>
              <td
                className={`px-3 py-3 text-right font-mono tabular-nums ${
                  r.is_champion ? "text-pink-300" : "text-slate-300"
                }`}
              >
                {fmtLift(r.lift_vs_random)}
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const PR_W = 460;
const PR_H = 280;
const PAD = { top: 14, right: 14, bottom: 30, left: 36 };

function PRCurves({
  curves,
}: {
  curves: typeof FALLBACK_MODEL_COMPARISON.pr_curves;
}) {
  const x = (v: number) => PAD.left + v * (PR_W - PAD.left - PAD.right);
  const y = (v: number) => PR_H - PAD.bottom - v * (PR_H - PAD.top - PAD.bottom);

  return (
    <div className={`glass rounded-2xl border p-5 ${ACCENT.cyan.border}`}>
      <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.cyan.text}`}>
        Precision-Recall curves
      </div>
      <svg viewBox={`0 0 ${PR_W} ${PR_H}`} className="mt-3 w-full">
        {/* axes */}
        <line x1={PAD.left} x2={PR_W - PAD.right} y1={PR_H - PAD.bottom} y2={PR_H - PAD.bottom} stroke="#334155" />
        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PR_H - PAD.bottom} stroke="#334155" />
        {/* grid */}
        {[0.2, 0.4, 0.6, 0.8].map((g) => (
          <line
            key={g}
            x1={PAD.left}
            x2={PR_W - PAD.right}
            y1={y(g)}
            y2={y(g)}
            stroke="#1e293b"
            strokeDasharray="2 3"
          />
        ))}
        {/* baseline (random) */}
        <line
          x1={PAD.left}
          x2={PR_W - PAD.right}
          y1={y(0.0184)}
          y2={y(0.0184)}
          stroke="#475569"
          strokeDasharray="3 3"
          strokeWidth={1}
        />
        <text x={PR_W - PAD.right - 4} y={y(0.0184) - 4} fontSize={9} fill="#64748b" textAnchor="end">
          random 0.018
        </text>

        {/* curves */}
        {Object.entries(curves).map(([name, c], i) => {
          if (name === "Majority" || name === "Random") return null;
          const path = c.recall
            .map((r, j) => `${j === 0 ? "M" : "L"} ${x(r)} ${y(c.precision[j])}`)
            .join(" ");
          return (
            <motion.path
              key={name}
              d={path}
              fill="none"
              stroke={MODEL_COLOR[name] ?? "#64748b"}
              strokeWidth={name === "Ensemble" ? 2.5 : 1.6}
              initial={{ pathLength: 0 }}
              whileInView={{ pathLength: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 1.2, delay: i * 0.15, ease: "easeOut" }}
            />
          );
        })}

        {/* axis labels */}
        <text x={PR_W / 2} y={PR_H - 8} fontSize={10} fill="#64748b" textAnchor="middle">
          recall →
        </text>
        <text
          x={-PR_H / 2}
          y={12}
          fontSize={10}
          fill="#64748b"
          textAnchor="middle"
          transform="rotate(-90)"
        >
          precision →
        </text>
        {[0, 0.5, 1].map((t) => (
          <text key={`xt${t}`} x={x(t)} y={PR_H - PAD.bottom + 14} fontSize={9} fill="#94a3b8" textAnchor="middle">
            {t.toFixed(1)}
          </text>
        ))}
        {[0.0184, 0.2, 0.4, 0.6].map((t) => (
          <text key={`yt${t}`} x={PAD.left - 6} y={y(t) + 3} fontSize={9} fill="#94a3b8" textAnchor="end">
            {t === 0.0184 ? "0.02" : t.toFixed(1)}
          </text>
        ))}
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-400">
        {(["Logit", "LightGBM", "Ensemble"] as const).map((n) => (
          <span key={n} className="flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded" style={{ background: MODEL_COLOR[n] }} />
            {n}
          </span>
        ))}
      </div>
    </div>
  );
}

const CAL_W = 460;
const CAL_H = 280;

function CalibrationPlot({
  calibration,
}: {
  calibration: typeof FALLBACK_MODEL_COMPARISON.calibration;
}) {
  const x = (v: number) => PAD.left + v * (CAL_W - PAD.left - PAD.right);
  const y = (v: number) => CAL_H - PAD.bottom - v * (CAL_H - PAD.top - PAD.bottom);

  const renderLine = (
    points: { mean_pred: number[]; frac_positive: number[] },
    color: string,
  ) => {
    return points.mean_pred
      .map((p, i) => `${i === 0 ? "M" : "L"} ${x(p)} ${y(points.frac_positive[i])}`)
      .join(" ");
  };

  return (
    <div className={`glass rounded-2xl border p-5 ${ACCENT.amber.border}`}>
      <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.amber.text}`}>
        Calibration · isotonic effect
      </div>
      <svg viewBox={`0 0 ${CAL_W} ${CAL_H}`} className="mt-3 w-full">
        {/* axes */}
        <line x1={PAD.left} x2={CAL_W - PAD.right} y1={CAL_H - PAD.bottom} y2={CAL_H - PAD.bottom} stroke="#334155" />
        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={CAL_H - PAD.bottom} stroke="#334155" />
        {/* perfect-cal diagonal */}
        <line
          x1={x(0)}
          x2={x(1)}
          y1={y(0)}
          y2={y(1)}
          stroke="#475569"
          strokeDasharray="3 3"
        />
        <text x={x(1) - 6} y={y(1) + 12} fontSize={9} fill="#64748b" textAnchor="end">
          perfect
        </text>

        <motion.path
          d={renderLine(calibration.uncalibrated, "#f43f5e")}
          fill="none"
          stroke="#f43f5e"
          strokeWidth={1.8}
          initial={{ pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
        <motion.path
          d={renderLine(calibration.calibrated, "#10b981")}
          fill="none"
          stroke="#10b981"
          strokeWidth={2.4}
          initial={{ pathLength: 0 }}
          whileInView={{ pathLength: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 1, delay: 0.3, ease: "easeOut" }}
        />
        {/* ticks */}
        {[0, 0.5, 1].map((t) => (
          <g key={t}>
            <text x={x(t)} y={CAL_H - PAD.bottom + 14} fontSize={9} fill="#94a3b8" textAnchor="middle">
              {t}
            </text>
            <text x={PAD.left - 6} y={y(t) + 3} fontSize={9} fill="#94a3b8" textAnchor="end">
              {t}
            </text>
          </g>
        ))}
        <text x={CAL_W / 2} y={CAL_H - 8} fontSize={10} fill="#64748b" textAnchor="middle">
          predicted prob →
        </text>
        <text
          x={-CAL_H / 2}
          y={12}
          fontSize={10}
          fill="#64748b"
          textAnchor="middle"
          transform="rotate(-90)"
        >
          observed rate →
        </text>
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-400">
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-3 rounded bg-rose-500/150" />
          uncalibrated
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-3 rounded bg-emerald-500/150" />
          calibrated (isotonic)
        </span>
      </div>
    </div>
  );
}
