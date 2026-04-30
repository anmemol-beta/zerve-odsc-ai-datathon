"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { CohortEvolution, CohortPoint } from "@/lib/types";

const STAGE_COLOR = {
  active:   "#3b82f6",
  created:  "#06b6d4",
  ai:       "#10b981",
  engaged:  "#84cc16",
  at_risk:  "#f59e0b",
  upgraded: "#ec4899",
} as const;

const STAGE_LABEL: Record<keyof typeof STAGE_COLOR, string> = {
  active:   "Active",
  created:  "Created",
  ai:       "Used AI",
  engaged:  "Engaged",
  at_risk:  "At Risk",
  upgraded: "Upgraded",
};

type Stage = keyof typeof STAGE_COLOR;
const STAGES: Stage[] = ["active", "created", "ai", "engaged", "at_risk", "upgraded"];

function fmtWeek(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit", timeZone: "UTC" });
}

function pct(p: number): string {
  return `${p.toFixed(1)}%`;
}

export default function CohortTimeline({ data }: { data: CohortEvolution }) {
  const cohorts = data.cohorts;
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1); // 0.5x / 1x / 2x
  const timer = useRef<number | null>(null);

  // Clamp idx if data length shrinks
  useEffect(() => {
    if (idx >= cohorts.length) setIdx(0);
  }, [cohorts.length, idx]);

  // Auto-advance
  useEffect(() => {
    if (!playing) return;
    const ms = 1300 / speed;
    timer.current = window.setInterval(() => {
      setIdx((i) => (i + 1) % cohorts.length);
    }, ms);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [playing, speed, cohorts.length]);

  const cur = cohorts[idx] ?? cohorts[0];

  // Pre-compute extents for line chart
  const { maxUpgrade, maxAtRisk, maxN } = useMemo(() => {
    let mU = 0, mR = 0, mN = 0;
    for (const c of cohorts) {
      if (c.upgraded_pct > mU) mU = c.upgraded_pct;
      if (c.at_risk_pct  > mR) mR = c.at_risk_pct;
      if (c.n > mN) mN = c.n;
    }
    return { maxUpgrade: Math.max(mU, 1), maxAtRisk: Math.max(mR, 1), maxN: Math.max(mN, 1) };
  }, [cohorts]);

  const chartW = 800;
  const chartH = 140;
  const padL = 36, padR = 14, padT = 10, padB = 22;
  const innerW = chartW - padL - padR;
  const innerH = chartH - padT - padB;
  const xFor = (i: number) => padL + (cohorts.length <= 1 ? 0 : (i / (cohorts.length - 1)) * innerW);
  const yForUpgrade = (p: number) => padT + innerH - (p / maxUpgrade) * innerH;
  const yForAtRisk  = (p: number) => padT + innerH - (p / maxAtRisk)  * innerH;
  const yForN       = (n: number) => padT + innerH - (n / maxN)       * innerH;

  const upgradePath = cohorts.map((c, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yForUpgrade(c.upgraded_pct)}`).join(" ");
  const atRiskPath  = cohorts.map((c, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yForAtRisk(c.at_risk_pct)}`).join(" ");
  const cumPath     = cohorts.map((c, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yForUpgrade(c.cum_upgrade_rate)}`).join(" ");

  return (
    <div className="space-y-5">
      {/* Cohort headline + stage composition */}
      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-5">
        <div className="glass rounded-2xl p-5 flex flex-col justify-between min-h-[200px]">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono">
            cohort signed up week
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={cur?.week}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
              className="space-y-1"
            >
              <div className="text-3xl font-black tabular-nums text-slate-50">
                {cur ? fmtWeek(cur.week) : "—"}
              </div>
              <div className="text-sm text-slate-400">
                <span className="font-mono text-slate-200">{cur?.n.toLocaleString() ?? 0}</span> users joined
              </div>
              <div className="text-xs text-slate-500 mt-2">
                Cumulative through this week:{" "}
                <span className="text-pink-300 font-mono">{cur?.cum_upgrade_rate.toFixed(2)}%</span> upgrade rate
                {" "}({cur?.cum_upgraded.toLocaleString() ?? 0} of {cur?.cum_n.toLocaleString() ?? 0})
              </div>
            </motion.div>
          </AnimatePresence>

          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={() => setPlaying((p) => !p)}
              className="text-xs font-mono px-3 py-1.5 rounded-md bg-pink-500/20 hover:bg-pink-500/30 border border-pink-500/40 text-pink-200 transition"
            >
              {playing ? "❚❚ pause" : "▶ play"}
            </button>
            <select
              value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
              className="text-xs font-mono px-2 py-1.5 rounded-md bg-ink-900/80 border border-slate-700 text-slate-300"
            >
              <option value={0.5}>0.5×</option>
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={4}>4×</option>
            </select>
          </div>
        </div>

        <div className="glass rounded-2xl p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-3">
            stage reach for this cohort (% of joiners)
          </div>
          <div className="space-y-2">
            {STAGES.map((s) => {
              const value = (cur?.[`${s}_pct` as keyof CohortPoint] as number) ?? 0;
              return (
                <div key={s} className="flex items-center gap-3">
                  <div className="w-20 text-xs text-slate-400 font-mono">{STAGE_LABEL[s]}</div>
                  <div className="flex-1 h-5 bg-slate-800/60 rounded-full overflow-hidden">
                    <motion.div
                      animate={{ width: `${Math.min(100, value)}%` }}
                      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                      style={{ backgroundColor: STAGE_COLOR[s], boxShadow: `0 0 10px ${STAGE_COLOR[s]}88` }}
                      className="h-full rounded-full"
                    />
                  </div>
                  <div className="w-14 text-right text-xs font-mono tabular-nums text-slate-200">
                    {pct(value)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Trend line chart with playhead */}
      <div className="glass rounded-2xl p-5">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono">
            cohort upgrade % · at-risk % · cumulative upgrade rate
          </div>
          <div className="flex items-center gap-3 text-[10px] font-mono text-slate-500">
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-pink-500" />upgraded</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400" />at risk</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-slate-400" />cumulative upgrade</span>
          </div>
        </div>

        <svg
          viewBox={`0 0 ${chartW} ${chartH}`}
          className="w-full h-[140px] cursor-pointer"
          onMouseDown={(e) => {
            const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
            const xPx = ((e.clientX - rect.left) / rect.width) * chartW;
            const i = Math.round(((xPx - padL) / innerW) * (cohorts.length - 1));
            const clamped = Math.max(0, Math.min(cohorts.length - 1, i));
            setPlaying(false);
            setIdx(clamped);
          }}
        >
          {/* Y grid */}
          {[0.25, 0.5, 0.75, 1].map((g) => (
            <line key={g}
              x1={padL} x2={chartW - padR}
              y1={padT + innerH * (1 - g)} y2={padT + innerH * (1 - g)}
              stroke="#334155" strokeWidth={0.5} strokeDasharray="2 4" opacity={0.5}
            />
          ))}

          {/* Cumulative upgrade rate (dim slate, baseline reference) */}
          <path d={cumPath} fill="none" stroke="#94a3b8" strokeWidth={1.4} opacity={0.8} />

          {/* Per-cohort upgrade % (pink) */}
          <path d={upgradePath} fill="none" stroke="#ec4899" strokeWidth={2.0} />

          {/* Per-cohort at_risk % (amber) */}
          <path d={atRiskPath} fill="none" stroke="#f59e0b" strokeWidth={1.6} opacity={0.8} />

          {/* Cohort dots, scaled by cohort size */}
          {cohorts.map((c, i) => (
            <circle key={c.week}
              cx={xFor(i)} cy={yForUpgrade(c.upgraded_pct)}
              r={Math.max(1.5, 4 * (c.n / maxN))}
              fill="#ec4899" opacity={i === idx ? 1 : 0.6}
            />
          ))}

          {/* Playhead */}
          {cur && (
            <g>
              <line
                x1={xFor(idx)} x2={xFor(idx)}
                y1={padT} y2={padT + innerH}
                stroke="#f1f5f9" strokeWidth={1.2} strokeDasharray="3 3" opacity={0.6}
              />
              <circle cx={xFor(idx)} cy={yForUpgrade(cur.upgraded_pct)} r={6} fill="none" stroke="#f1f5f9" strokeWidth={1.5} />
            </g>
          )}

          {/* Y-axis tick labels (upgrade % scale) */}
          {[0, 0.5, 1].map((g) => (
            <text key={g}
              x={padL - 4}
              y={padT + innerH * (1 - g) + 3}
              fontSize={9} fill="#64748b" textAnchor="end" fontFamily="monospace"
            >
              {(g * maxUpgrade).toFixed(1)}%
            </text>
          ))}

          {/* X-axis: first/last cohort labels */}
          <text x={padL} y={chartH - 4} fontSize={9} fill="#64748b" fontFamily="monospace">
            {fmtWeek(cohorts[0]?.week ?? "2025-01-01")}
          </text>
          <text x={chartW - padR} y={chartH - 4} fontSize={9} fill="#64748b" fontFamily="monospace" textAnchor="end">
            {fmtWeek(cohorts[cohorts.length - 1]?.week ?? "2025-01-01")}
          </text>
        </svg>

        <div className="text-[11px] text-slate-500 mt-2 leading-snug">
          <strong className="text-slate-300">Decision lens:</strong>{" "}
          if the per-cohort <span className="text-pink-300">pink</span> line bends UP relative to the{" "}
          <span className="text-slate-300">grey cumulative</span> line, recent cohorts are upgrading at a higher rate than the all-time baseline —
          i.e. the funnel is genuinely improving, not just accumulating eligible users.
          The <span className="text-amber-300">amber</span> line is at-risk %; spikes precede churn waves.
          Click anywhere on the chart to scrub; the bars above re-render the funnel for that week.
        </div>
      </div>
    </div>
  );
}
