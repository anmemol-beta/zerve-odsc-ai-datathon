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

function fmtNum(n: number): string {
  return Math.round(n).toLocaleString();
}

// Animated counter — interpolates the number on prop change
function NumberTicker({ value, accent }: { value: number; accent: string }) {
  const [shown, setShown] = useState(value);
  useEffect(() => {
    const start = shown;
    const t0 = performance.now();
    const dur = 360;
    let raf = 0;
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / dur);
      const eased = 1 - Math.pow(1 - k, 3);
      setShown(start + (value - start) * eased);
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return <span className={`tabular-nums ${accent}`}>{fmtNum(shown)}</span>;
}

export default function CohortTimeline({ data }: { data: CohortEvolution }) {
  const cohorts = data.cohorts;
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (idx >= cohorts.length) setIdx(0);
  }, [cohorts.length, idx]);

  useEffect(() => {
    if (!playing) return;
    const ms = 1300 / speed;
    timer.current = window.setInterval(() => {
      setIdx((i) => {
        const next = i + 1;
        if (next >= cohorts.length) {
          // loop back to start
          return 0;
        }
        return next;
      });
    }, ms);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [playing, speed, cohorts.length]);

  const cur = cohorts[idx] ?? cohorts[0];

  // Trend chart extents
  const { maxUpgrade, maxAtRisk, maxN } = useMemo(() => {
    let mU = 0, mR = 0, mN = 0;
    for (const c of cohorts) {
      if (c.upgraded_pct > mU) mU = c.upgraded_pct;
      if (c.at_risk_pct  > mR) mR = c.at_risk_pct;
      if (c.n > mN) mN = c.n;
    }
    return { maxUpgrade: Math.max(mU, 1), maxAtRisk: Math.max(mR, 1), maxN: Math.max(mN, 1) };
  }, [cohorts]);

  const chartW = 800, chartH = 140;
  const padL = 36, padR = 14, padT = 10, padB = 22;
  const innerW = chartW - padL - padR;
  const innerH = chartH - padT - padB;
  const xFor = (i: number) => padL + (cohorts.length <= 1 ? 0 : (i / (cohorts.length - 1)) * innerW);
  const yForUpgrade = (p: number) => padT + innerH - (p / maxUpgrade) * innerH;
  const yForAtRisk  = (p: number) => padT + innerH - (p / maxAtRisk)  * innerH;

  const upgradePath = cohorts.map((c, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yForUpgrade(c.upgraded_pct)}`).join(" ");
  const atRiskPath  = cohorts.map((c, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yForAtRisk(c.at_risk_pct)}`).join(" ");
  const cumPath     = cohorts.map((c, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yForUpgrade(c.cum_upgrade_rate)}`).join(" ");

  // Reveal-up-to-current overlay path (animated growth)
  const visibleUpgrade = cohorts.slice(0, idx + 1).map((c, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yForUpgrade(c.upgraded_pct)}`).join(" ");

  // Cumulative funnel composition (as-of this week)
  const cumStage = (k: Stage) => (cur as any)[`cum_${k}`] as number;
  const cumPct = (k: Stage) => (cur ? (cumStage(k) / Math.max(1, cur.cum_n)) * 100 : 0);

  // Progress bar fill (0 → 100% over the timeline)
  const progress = cohorts.length <= 1 ? 0 : idx / (cohorts.length - 1);

  return (
    <div className="space-y-5">
      {/* ── Time scrubber + playhead controls (sticky-ish header for the section) */}
      <div className="glass rounded-2xl p-4">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setPlaying((p) => !p)}
              className="text-xs font-mono px-3 py-1.5 rounded-md bg-pink-500/20 hover:bg-pink-500/30 border border-pink-500/40 text-pink-200 transition shrink-0"
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
            <div className="text-[10px] uppercase tracking-[0.22em] font-mono text-slate-500">
              week {idx + 1} / {cohorts.length}
            </div>
          </div>

          {/* Scrubber */}
          <div className="flex-1 relative">
            <input
              type="range"
              min={0}
              max={cohorts.length - 1}
              step={1}
              value={idx}
              onChange={(e) => { setPlaying(false); setIdx(parseInt(e.target.value)); }}
              className="w-full"
            />
            <div className="flex justify-between mt-1 text-[10px] font-mono text-slate-500">
              <span>{fmtWeek(cohorts[0]?.week ?? "")}</span>
              <span className="text-pink-300">{cur ? fmtWeek(cur.week) : ""}</span>
              <span>{fmtWeek(cohorts[cohorts.length - 1]?.week ?? "")}</span>
            </div>
          </div>
        </div>

        {/* Skinny progress fill */}
        <div className="h-1 mt-2 rounded-full bg-slate-800/60 overflow-hidden">
          <motion.div
            animate={{ width: `${progress * 100}%` }}
            transition={{ duration: 0.25, ease: "linear" }}
            className="h-full bg-gradient-to-r from-pink-500 via-violet-500 to-cyan-500"
          />
        </div>
      </div>

      {/* ── Headline cards (cumulative as-of this week) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Cumulative users"  value={cur?.cum_n ?? 0}        accent="text-slate-50"  glow="rgba(139,92,246,0.18)" />
        <StatCard label="Reached engaged"   value={cur?.cum_engaged ?? 0}  accent="text-emerald-200" glow="rgba(16,185,129,0.18)" />
        <StatCard label="Upgraded"          value={cur?.cum_upgraded ?? 0} accent="text-pink-200" glow="rgba(236,72,153,0.22)" />
        <StatCard label="At risk (cum)"     value={cur?.cum_at_risk ?? 0}  accent="text-amber-200" glow="rgba(245,158,11,0.20)" warn />
      </div>

      {/* ── Two-up: cumulative funnel (left) + this-week's cohort breakdown (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass rounded-2xl p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-3">
            cumulative funnel — as of {cur ? fmtWeek(cur.week) : "—"}
          </div>
          <div className="space-y-2">
            {STAGES.map((s) => {
              const v = cumPct(s);
              return (
                <div key={s} className="flex items-center gap-3">
                  <div className="w-20 text-xs text-slate-400 font-mono">{STAGE_LABEL[s]}</div>
                  <div className="flex-1 h-5 bg-slate-800/60 rounded-full overflow-hidden">
                    <motion.div
                      animate={{ width: `${Math.min(100, v)}%` }}
                      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                      style={{ backgroundColor: STAGE_COLOR[s], boxShadow: `0 0 10px ${STAGE_COLOR[s]}88` }}
                      className="h-full rounded-full"
                    />
                  </div>
                  <div className="w-16 text-right text-xs font-mono tabular-nums text-slate-300">
                    {v.toFixed(1)}%
                  </div>
                  <div className="w-14 text-right text-xs font-mono tabular-nums text-slate-500">
                    <NumberTicker value={cumStage(s)} accent="text-slate-500" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="glass rounded-2xl p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-3">
            this week's cohort —{" "}
            <span className="text-pink-300 tabular-nums">
              <NumberTicker value={cur?.n ?? 0} accent="text-pink-300" /> users
            </span>{" "}
            joined
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
                    {value.toFixed(1)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Trend line with playhead */}
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

        <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full h-[140px]">
          {/* grid */}
          {[0.25, 0.5, 0.75, 1].map((g) => (
            <line key={g}
              x1={padL} x2={chartW - padR}
              y1={padT + innerH * (1 - g)} y2={padT + innerH * (1 - g)}
              stroke="#334155" strokeWidth={0.5} strokeDasharray="2 4" opacity={0.5}
            />
          ))}

          {/* faint full-line backgrounds */}
          <path d={cumPath} fill="none" stroke="#94a3b8" strokeWidth={1.4} opacity={0.35} />
          <path d={upgradePath} fill="none" stroke="#ec4899" strokeWidth={1.6} opacity={0.18} />
          <path d={atRiskPath} fill="none" stroke="#f59e0b" strokeWidth={1.4} opacity={0.18} />

          {/* foreground "drawn so far" segment */}
          <path d={visibleUpgrade} fill="none" stroke="#ec4899" strokeWidth={2.2} />

          {/* dots, only up to current */}
          {cohorts.slice(0, idx + 1).map((c, i) => (
            <circle key={c.week}
              cx={xFor(i)} cy={yForUpgrade(c.upgraded_pct)}
              r={Math.max(1.5, 4 * (c.n / maxN))}
              fill="#ec4899" opacity={i === idx ? 1 : 0.55}
            />
          ))}

          {/* playhead */}
          {cur && (
            <g>
              <line x1={xFor(idx)} x2={xFor(idx)} y1={padT} y2={padT + innerH}
                stroke="#f1f5f9" strokeWidth={1.2} strokeDasharray="3 3" opacity={0.6}
              />
              <circle cx={xFor(idx)} cy={yForUpgrade(cur.upgraded_pct)} r={6} fill="none" stroke="#f1f5f9" strokeWidth={1.5} />
            </g>
          )}

          {/* y ticks */}
          {[0, 0.5, 1].map((g) => (
            <text key={g} x={padL - 4} y={padT + innerH * (1 - g) + 3}
              fontSize={9} fill="#64748b" textAnchor="end" fontFamily="monospace"
            >
              {(g * maxUpgrade).toFixed(1)}%
            </text>
          ))}
        </svg>

        <AnimatePresence mode="wait">
          <motion.div
            key={cur?.week}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="text-[11px] text-slate-400 mt-2 leading-snug"
          >
            <strong className="text-slate-200">{cur ? fmtWeek(cur.week) : ""}</strong> ·
            this cohort upgrade <span className="text-pink-300 font-mono">{cur?.upgraded_pct.toFixed(2)}%</span> ·
            cumulative upgrade <span className="text-slate-300 font-mono">{cur?.cum_upgrade_rate.toFixed(2)}%</span> ·
            at-risk <span className="text-amber-300 font-mono">{cur?.at_risk_pct.toFixed(1)}%</span>
            {idx > 0 && cur && cohorts[0] && cur.upgraded_pct > cohorts[0].upgraded_pct && (
              <span className="ml-2 text-emerald-300">↑ vs cohort 1</span>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function StatCard({ label, value, accent, glow, warn }: { label: string; value: number; accent: string; glow: string; warn?: boolean }) {
  return (
    <div className="relative rounded-2xl overflow-hidden p-px">
      <div className="absolute inset-0 bg-gradient-to-br from-violet-500/30 via-violet-500/5 to-cyan-500/15 opacity-70" />
      <div className="relative rounded-[15px] bg-ink-900/85 backdrop-blur-md p-4">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: `radial-gradient(220px circle at 60% 0%, ${glow}, transparent 70%)` }}
        />
        <div className="relative">
          <div className="text-[9px] uppercase tracking-[0.22em] text-slate-400 font-mono">{label}</div>
          <div className={`mt-1.5 text-3xl font-black tracking-[-0.04em] ${warn ? "text-amber-300" : accent}`}>
            <NumberTicker value={value} accent="" />
          </div>
        </div>
      </div>
    </div>
  );
}
