"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { DailyPoint, DailyTimeline } from "@/lib/types";

// ─── Stage definitions
const STAGE_COLOR = {
  cum_active:    "#3b82f6",
  cum_created:   "#06b6d4",
  cum_ai:        "#10b981",
  cum_engaged:   "#84cc16",
  cum_at_risk:   "#f59e0b",
  cum_upgraded:  "#ec4899",
} as const;

const STAGE_LABEL: Record<keyof typeof STAGE_COLOR, string> = {
  cum_active:    "Active",
  cum_created:   "Created",
  cum_ai:        "Used AI",
  cum_engaged:   "Engaged",
  cum_at_risk:   "At Risk",
  cum_upgraded:  "Upgraded",
};

type StageKey = keyof typeof STAGE_COLOR;
const STAGES: StageKey[] = ["cum_active", "cum_created", "cum_ai", "cum_engaged", "cum_at_risk", "cum_upgraded"];

// ─── Helpers
function lerp(a: number, b: number, t: number): number { return a + (b - a) * t; }

function fmtDate(iso: string): { full: string; weekday: string; ymd: string } {
  const d = new Date(iso + "T00:00:00Z");
  return {
    full: d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" }),
    weekday: d.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" }),
    ymd: iso,
  };
}

function fmtNum(n: number): string {
  return Math.round(n).toLocaleString();
}

function weekKey(iso: string): string {
  // Monday-based week start (matches pandas to_period("W"))
  const d = new Date(iso + "T00:00:00Z");
  const day = d.getUTCDay();          // 0=Sun, 1=Mon, ...
  const diff = (day === 0 ? -6 : 1 - day);
  d.setUTCDate(d.getUTCDate() + diff);
  return d.toISOString().slice(0, 10);
}

// Interpolate a numeric field between two daily points
function interp(prev: DailyPoint | undefined, cur: DailyPoint, frac: number, key: keyof DailyPoint): number {
  if (!prev) return Number(cur[key]) || 0;
  return lerp(Number(prev[key]) || 0, Number(cur[key]) || 0, frac);
}

// ─── Component
export default function TimeTravel({ data }: { data: DailyTimeline }) {
  const days = data.days;
  const N = days.length;

  // Continuous time, in days from start. 0 .. N-1.
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(8);  // days/sec — fast enough to feel cinematic
  const rafRef = useRef<number | null>(null);
  const lastTRef = useRef<number>(0);
  const speedRef = useRef(speed);
  const playingRef = useRef(playing);
  speedRef.current = speed;
  playingRef.current = playing;

  // rAF loop drives continuous t; we hold the live value in a ref + state
  // (state for rendering, ref for the loop's own bookkeeping)
  const tRef = useRef(t);
  tRef.current = t;

  useEffect(() => {
    let lastNow = performance.now();
    const tick = (now: number) => {
      const dt = (now - lastNow) / 1000;
      lastNow = now;
      if (playingRef.current) {
        let nt = tRef.current + dt * speedRef.current;
        if (nt >= N - 1) nt = 0;
        tRef.current = nt;
        setT(nt);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [N]);

  // Current interpolated values
  const i0 = Math.min(N - 1, Math.floor(t));
  const i1 = Math.min(N - 1, i0 + 1);
  const frac = t - i0;
  const cur = days[i0];
  const next = days[i1];

  const v = (k: keyof DailyPoint): number => interp(cur, next, frac, k);

  const totalUsers = days[N - 1]?.cum_n ?? 1;
  const ymd = cur?.day ?? "";
  const date = useMemo(() => fmtDate(ymd), [ymd]);

  // Top events for current week
  const wk = weekKey(ymd);
  const topEvents = data.top_per_week[wk] ?? data.top_per_week[Object.keys(data.top_per_week)[0]] ?? [];

  // ── Chart geometry for trend lines
  const chartW = 1000;
  const chartH = 220;
  const padL = 50, padR = 16, padT = 14, padB = 26;
  const innerW = chartW - padL - padR;
  const innerH = chartH - padT - padB;
  const xFor = (i: number) => padL + (i / (N - 1)) * innerW;

  const series: { key: keyof DailyPoint; color: string; label: string; max: number }[] = useMemo(() => {
    const computeMax = (k: keyof DailyPoint) => Math.max(1, ...days.map((d) => Number(d[k]) || 0));
    return [
      { key: "cum_n",        color: "#94a3b8", label: "users",       max: computeMax("cum_n") },
      { key: "cum_engaged",  color: "#84cc16", label: "engaged",     max: computeMax("cum_n") },  // share scale w/ users
      { key: "cum_upgraded", color: "#ec4899", label: "upgraded",    max: computeMax("cum_n") },
      { key: "cum_at_risk",  color: "#f59e0b", label: "at-risk",     max: computeMax("cum_n") },
    ];
  }, [days]);

  // Pre-compute paths for each series (once)
  const seriesPaths = useMemo(() => {
    return series.map((s) => {
      let d = "";
      for (let i = 0; i < N; i++) {
        const y = padT + innerH - ((Number(days[i][s.key]) || 0) / s.max) * innerH;
        d += `${i === 0 ? "M" : "L"} ${xFor(i)} ${y} `;
      }
      return d;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, series, N]);

  // Daily new-users sparkline
  const newMax = Math.max(1, ...days.map((d) => d.new_n));
  const eventsMax = Math.max(1, ...days.map((d) => d.events));

  // ── Pulse on day with upgrade events
  const upgradePulse = cur && cur.upgrade_events > 0 ? Math.min(1, cur.upgrade_events / 5) : 0;

  // Click on chart to scrub
  const onScrub = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const xPx = ((e.clientX - rect.left) / rect.width) * chartW;
    const i = ((xPx - padL) / innerW) * (N - 1);
    const clamped = Math.max(0, Math.min(N - 1, i));
    setPlaying(false);
    tRef.current = clamped;
    setT(clamped);
  };

  // Numbers to display (interpolated)
  const cum_n = v("cum_n");
  const cum_engaged = v("cum_engaged");
  const cum_upgraded = v("cum_upgraded");
  const cum_at_risk = v("cum_at_risk");
  const cum_events = v("cum_events");
  const events_today = v("events");
  const upgrades_today = v("upgrade_events");

  return (
    <div className="space-y-4 select-none">
      {/* ── Top control bar ─────────────────────────────────────────── */}
      <div className="glass rounded-2xl p-4 flex flex-col gap-2">
        <div className="flex items-center gap-3 flex-wrap">
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
            <option value={2}>2 d/s</option>
            <option value={4}>4 d/s</option>
            <option value={8}>8 d/s</option>
            <option value={16}>16 d/s</option>
            <option value={32}>32 d/s</option>
          </select>
          <div className="text-[10px] uppercase tracking-[0.22em] font-mono text-slate-500">
            day {Math.round(t) + 1} / {N}
          </div>
          <div className="flex-1 relative">
            <input
              type="range"
              min={0}
              max={N - 1}
              step={0.01}
              value={t}
              onChange={(e) => { setPlaying(false); const nt = parseFloat(e.target.value); tRef.current = nt; setT(nt); }}
              className="w-full"
            />
          </div>
        </div>
        <div className="h-1.5 mt-1 rounded-full bg-slate-800/60 overflow-hidden">
          <div
            style={{ width: `${(t / (N - 1)) * 100}%` }}
            className="h-full bg-gradient-to-r from-pink-500 via-violet-500 to-cyan-500 transition-none"
          />
        </div>
        <div className="flex justify-between text-[10px] font-mono text-slate-500">
          <span>{days[0] ? fmtDate(days[0].day).full : ""}</span>
          <span className="text-pink-300">{date.full}</span>
          <span>{days[N - 1] ? fmtDate(days[N - 1].day).full : ""}</span>
        </div>
      </div>

      {/* ── Hero row: huge date + cumulative numbers ────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-4">
        <div className="glass rounded-2xl p-5 relative overflow-hidden">
          <div
            className="absolute -inset-1 pointer-events-none transition-opacity duration-300"
            style={{
              background: `radial-gradient(420px circle at 30% 30%, rgba(236,72,153,${0.12 + upgradePulse * 0.25}), transparent 65%)`,
            }}
          />
          <div className="relative">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono">snapshot date</div>
            <div className="mt-2 text-4xl md:text-5xl font-black tracking-[-0.04em] text-slate-50 tabular-nums leading-tight">
              {date.full}
            </div>
            <div className="text-xs text-slate-400 font-mono mt-1">
              {date.weekday} · day {Math.round(t) + 1} of {N}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Mini label="events today" value={events_today} accent="text-cyan-200" />
              <Mini label="upgrades today" value={upgrades_today} accent={upgrades_today > 0 ? "text-pink-300" : "text-slate-400"} pulse={upgrades_today > 0} />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="users"     value={cum_n}        accent="text-slate-50"   pct={cum_n / totalUsers} />
          <Stat label="engaged"   value={cum_engaged}  accent="text-emerald-200" pct={cum_engaged / totalUsers} />
          <Stat label="upgraded"  value={cum_upgraded} accent="text-pink-200"   pct={cum_upgraded / totalUsers} pulse={upgrades_today > 0} />
          <Stat label="at-risk"   value={cum_at_risk}  accent="text-amber-200"  pct={cum_at_risk / totalUsers} warn />
        </div>
      </div>

      {/* ── Funnel: animated donut + bars side-by-side ───────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4">
        <div className="glass rounded-2xl p-5 flex flex-col">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-2">
            current-stage breakdown · pie · {date.full}
          </div>
          <Donut valueFn={v} totalUsers={totalUsers} cumN={cum_n} />
        </div>

        <div className="glass rounded-2xl p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono">
              cumulative reach bars
            </div>
            <div className="text-[10px] font-mono text-slate-500 tabular-nums">
              <span className="text-cyan-300">{fmtNum(cum_events)}</span> events · <span className="text-slate-300">{fmtNum(cum_n)}</span> users
            </div>
          </div>
          <div className="space-y-1.5">
            {STAGES.map((s) => {
              const value = v(s);
              const pct = (value / totalUsers) * 100;
              return (
                <div key={s} className="flex items-center gap-3">
                  <div className="w-20 text-xs text-slate-400 font-mono">{STAGE_LABEL[s]}</div>
                  <div className="flex-1 h-6 bg-slate-800/60 rounded-full overflow-hidden relative">
                    <div
                      style={{
                        width: `${Math.min(100, pct)}%`,
                        backgroundColor: STAGE_COLOR[s],
                        boxShadow: `0 0 12px ${STAGE_COLOR[s]}88, inset 0 0 6px rgba(255,255,255,0.12)`,
                      }}
                      className="h-full rounded-full transition-none"
                    />
                    <div
                      className="absolute inset-y-0 w-12 opacity-50 pointer-events-none"
                      style={{
                        left: `${Math.min(100, pct) - 6}%`,
                        background: `linear-gradient(90deg, transparent, ${STAGE_COLOR[s]}cc, transparent)`,
                        filter: "blur(6px)",
                        transition: "left 0.05s linear",
                      }}
                    />
                  </div>
                  <div className="w-20 text-right text-xs font-mono tabular-nums text-slate-200">
                    {fmtNum(value)}
                  </div>
                  <div className="w-14 text-right text-[11px] font-mono tabular-nums text-slate-500">
                    {pct.toFixed(1)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Per-frame analytics: deltas + windowed metrics ─────────── */}
      <FrameAnalytics days={days} idx={Math.round(t)} cur={cur} v={v} totalUsers={totalUsers} />

      {/* ── Cumulative trend chart (multi-line with playhead) ─────── */}
      <div className="glass rounded-2xl p-5">
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono">
            cumulative growth — playhead reveals as time advances
          </div>
          <div className="flex items-center gap-3 text-[10px] font-mono text-slate-500">
            {series.map((s) => (
              <span key={s.key} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ background: s.color, boxShadow: `0 0 6px ${s.color}` }} />
                {s.label}
              </span>
            ))}
          </div>
        </div>

        <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full h-[220px] cursor-pointer" onMouseDown={onScrub}>
          {/* grid */}
          {[0.25, 0.5, 0.75, 1].map((g) => (
            <line key={g}
              x1={padL} x2={chartW - padR}
              y1={padT + innerH * (1 - g)} y2={padT + innerH * (1 - g)}
              stroke="#334155" strokeWidth={0.5} strokeDasharray="2 4" opacity={0.5}
            />
          ))}

          {/* full faint background lines for context */}
          {seriesPaths.map((p, i) => (
            <path key={`bg-${series[i].key}`} d={p} fill="none" stroke={series[i].color} strokeWidth={1.2} opacity={0.18} />
          ))}

          {/* clipped foreground lines (only up to current time) */}
          <defs>
            <clipPath id="reveal">
              <rect x={padL} y={padT} width={(t / (N - 1)) * innerW} height={innerH} />
            </clipPath>
            {/* Glow filter for upgrade pulses */}
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          {seriesPaths.map((p, i) => (
            <path key={`fg-${series[i].key}`}
              d={p}
              fill="none"
              stroke={series[i].color}
              strokeWidth={series[i].key === "cum_upgraded" ? 2.4 : 1.8}
              clipPath="url(#reveal)"
              filter={series[i].key === "cum_upgraded" ? "url(#glow)" : undefined}
            />
          ))}

          {/* playhead */}
          <line
            x1={xFor(t)} x2={xFor(t)}
            y1={padT} y2={padT + innerH}
            stroke="#f1f5f9" strokeWidth={1.2} strokeDasharray="3 3" opacity={0.55}
          />

          {/* dots at current value for each series */}
          {series.map((s) => {
            const yVal = v(s.key);
            const y = padT + innerH - (yVal / s.max) * innerH;
            return (
              <g key={`dot-${s.key}`}>
                <circle cx={xFor(t)} cy={y} r={s.key === "cum_upgraded" ? 7 : 4.5} fill="none" stroke={s.color} strokeWidth={1.6} opacity={0.7} />
                <circle cx={xFor(t)} cy={y} r={s.key === "cum_upgraded" ? 4 : 2.5} fill={s.color} />
              </g>
            );
          })}

          {/* y axis ticks */}
          {[0, 0.5, 1].map((g) => (
            <text key={g} x={padL - 6} y={padT + innerH * (1 - g) + 3}
              fontSize={9} fill="#64748b" textAnchor="end" fontFamily="monospace"
            >
              {fmtNum(g * (series[0]?.max ?? 1))}
            </text>
          ))}
        </svg>
      </div>

      {/* ── Two-up: daily-events sparkline + top events ticker ─────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass rounded-2xl p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-2">
            daily activity volume — events / day · scrub the chart above
          </div>
          <svg viewBox={`0 0 ${chartW} 80`} className="w-full h-[80px]">
            {days.map((d, i) => {
              const x = padL + (i / (N - 1)) * (chartW - padL - padR);
              const h = (d.events / eventsMax) * 60;
              const y = 70 - h;
              const isPast = i <= t;
              return (
                <line key={i} x1={x} x2={x} y1={y} y2={70}
                  stroke={isPast ? "#06b6d4" : "#334155"}
                  strokeWidth={Math.max(1, (chartW - padL - padR) / N - 0.2)}
                  opacity={isPast ? 0.85 : 0.35}
                />
              );
            })}
            {/* upgrade markers */}
            {days.map((d, i) => {
              if (!d.upgrade_events) return null;
              const x = padL + (i / (N - 1)) * (chartW - padL - padR);
              const r = Math.min(5, 1 + d.upgrade_events * 0.5);
              const isPast = i <= t;
              return (
                <circle key={`u-${i}`} cx={x} cy={10} r={r}
                  fill="#ec4899" opacity={isPast ? 0.9 : 0.3}
                  filter={isPast ? "url(#glow)" : undefined}
                />
              );
            })}
            <text x={padL} y={78} fontSize={9} fill="#64748b" fontFamily="monospace">events/day (cyan)</text>
            <text x={chartW - padR} y={78} fontSize={9} fill="#ec4899" fontFamily="monospace" textAnchor="end">upgrade events (pink dots)</text>
          </svg>
          <div className="mt-2 text-[11px] font-mono text-slate-400 tabular-nums">
            today: <span className="text-cyan-300">{fmtNum(events_today)}</span> events ·{" "}
            <span className="text-slate-300">{fmtNum(v("new_n"))}</span> new users
            {upgrades_today > 0 && (
              <span className="ml-2 text-pink-300 animate-pulse">+ {fmtNum(upgrades_today)} upgrade{Math.round(upgrades_today) !== 1 ? "s" : ""} 🎉</span>
            )}
          </div>
        </div>

        <div className="glass rounded-2xl p-5">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-2">
            top events — week of {fmtDate(wk).full}
          </div>
          <div className="space-y-1">
            {topEvents.slice(0, 8).map((e, i) => {
              const max = topEvents[0]?.count ?? 1;
              const w = (e.count / max) * 100;
              return (
                <div key={e.event + i} className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] font-mono text-slate-300 truncate">{e.event}</div>
                    <div className="h-1 bg-slate-800/60 rounded-full overflow-hidden mt-0.5">
                      <div
                        style={{
                          width: `${w}%`,
                          background: `linear-gradient(90deg, #06b6d4, #8b5cf6)`,
                        }}
                        className="h-full rounded-full transition-all duration-500"
                      />
                    </div>
                  </div>
                  <div className="text-[10px] font-mono text-slate-400 tabular-nums w-14 text-right">
                    {fmtNum(e.count)}
                  </div>
                </div>
              );
            })}
            {topEvents.length === 0 && <div className="text-xs text-slate-500">no events</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components

function Stat({ label, value, accent, pct, warn, pulse }: {
  label: string; value: number; accent: string; pct: number; warn?: boolean; pulse?: boolean;
}) {
  return (
    <div className="relative rounded-2xl overflow-hidden p-px">
      <div className={`absolute inset-0 bg-gradient-to-br ${warn ? "from-amber-500/40 via-amber-500/10 to-amber-500/5" : "from-violet-500/30 via-violet-500/5 to-cyan-500/15"} opacity-70`} />
      <div className="relative rounded-[15px] bg-ink-900/85 backdrop-blur-md p-3 overflow-hidden">
        {pulse && (
          <div className="absolute inset-0 pointer-events-none animate-pulse"
            style={{ background: "radial-gradient(160px circle at 70% 0%, rgba(236,72,153,0.30), transparent 70%)" }}
          />
        )}
        <div className="relative">
          <div className="text-[9px] uppercase tracking-[0.22em] text-slate-400 font-mono">{label}</div>
          <div className={`mt-1 text-3xl font-black tracking-[-0.04em] tabular-nums ${warn ? "text-amber-300" : accent}`}>
            {fmtNum(value)}
          </div>
          <div className="text-[10px] text-slate-500 font-mono tabular-nums">
            {(pct * 100).toFixed(1)}% of final
          </div>
        </div>
      </div>
    </div>
  );
}

function Mini({ label, value, accent, pulse }: { label: string; value: number; accent: string; pulse?: boolean }) {
  return (
    <div className="rounded-md bg-ink-950/60 border border-slate-800/50 px-2.5 py-1.5">
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500 font-mono">{label}</div>
      <div className={`text-base font-black tabular-nums ${accent} ${pulse ? "animate-pulse" : ""}`}>
        {fmtNum(value)}
      </div>
    </div>
  );
}

// ── Pie chart: mutually exclusive "current stage" slices that sum to 100%.
//   The strict-nested funnel can't itself pie-chart (every upgraded user is
//   also engaged/active/etc), so we derive exclusive segments by subtracting
//   each stage from the next: a user counted in "Active only" reached active
//   but did NOT reach created, etc. This sums to cum_n ⇒ valid pie.
function Donut({
  valueFn,
  totalUsers,
  cumN,
}: {
  valueFn: (k: any) => number;
  totalUsers: number;
  cumN: number;
}) {
  const size = 260;
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = 110;
  const rInner = 64;

  // Mutually exclusive slices (current-state breakdown)
  const cum_active   = valueFn("cum_active");
  const cum_created  = valueFn("cum_created");
  const cum_ai       = valueFn("cum_ai");
  const cum_engaged  = valueFn("cum_engaged");
  const cum_at_risk  = valueFn("cum_at_risk");
  const cum_upgraded = valueFn("cum_upgraded");

  const slicesRaw: { label: string; value: number; color: string }[] = [
    { label: "signed up only",  value: Math.max(0, cumN          - cum_active),                           color: "#475569" },
    { label: "active only",     value: Math.max(0, cum_active    - cum_created),                          color: STAGE_COLOR.cum_active },
    { label: "created only",    value: Math.max(0, cum_created   - cum_ai),                               color: STAGE_COLOR.cum_created },
    { label: "used AI only",    value: Math.max(0, cum_ai        - cum_engaged),                          color: STAGE_COLOR.cum_ai },
    { label: "engaged",         value: Math.max(0, cum_engaged   - cum_upgraded - cum_at_risk),           color: STAGE_COLOR.cum_engaged },
    { label: "at risk",         value: cum_at_risk,                                                       color: STAGE_COLOR.cum_at_risk },
    { label: "upgraded",        value: cum_upgraded,                                                      color: STAGE_COLOR.cum_upgraded },
  ];

  const total = slicesRaw.reduce((s, x) => s + x.value, 0) || 1;

  // Build arc paths
  const arcSlice = (startFrac: number, endFrac: number): string => {
    const TWO_PI = Math.PI * 2;
    const a0 = startFrac * TWO_PI - Math.PI / 2;
    const a1 = endFrac   * TWO_PI - Math.PI / 2;
    const lg = endFrac - startFrac > 0.5 ? 1 : 0;
    const xo0 = cx + rOuter * Math.cos(a0), yo0 = cy + rOuter * Math.sin(a0);
    const xo1 = cx + rOuter * Math.cos(a1), yo1 = cy + rOuter * Math.sin(a1);
    const xi0 = cx + rInner * Math.cos(a0), yi0 = cy + rInner * Math.sin(a0);
    const xi1 = cx + rInner * Math.cos(a1), yi1 = cy + rInner * Math.sin(a1);
    return `M ${xo0} ${yo0} A ${rOuter} ${rOuter} 0 ${lg} 1 ${xo1} ${yo1} L ${xi1} ${yi1} A ${rInner} ${rInner} 0 ${lg} 0 ${xi0} ${yi0} Z`;
  };

  let cursor = 0;
  const slices = slicesRaw.map((s) => {
    const frac = s.value / total;
    const start = cursor;
    cursor += frac;
    return { ...s, frac, start, end: cursor };
  });

  return (
    <div className="relative flex flex-col items-center" style={{ minHeight: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <filter id="pieGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="1.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        {/* Track ring (covers gaps if total < cumN slightly) */}
        <circle cx={cx} cy={cy} r={(rOuter + rInner) / 2} fill="none" stroke="#1e293b" strokeWidth={rOuter - rInner} opacity={0.4} />
        {slices.map((s, i) => (
          s.frac > 0 ? (
            <path
              key={s.label + i}
              d={arcSlice(s.start, s.end)}
              fill={s.color}
              stroke="#020617"
              strokeWidth={1.2}
              opacity={0.92}
              filter="url(#pieGlow)"
            />
          ) : null
        ))}

        {/* Inner labels: total in center */}
        <text x={cx} y={cy - 8} textAnchor="middle" fill="#f1f5f9" fontSize={28} fontWeight={900} fontFamily="ui-sans-serif">
          {fmtNum(cumN)}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" fill="#94a3b8" fontSize={9} fontFamily="monospace" letterSpacing={2}>
          USERS · BY CURRENT STAGE
        </text>
      </svg>

      {/* Slice legend with %s, sorted by value desc */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] font-mono mt-2 w-full">
        {slices
          .map((s) => ({ ...s, pct: (s.value / total) * 100 }))
          .sort((a, b) => b.value - a.value)
          .map((s, i) => (
            <div key={s.label + i} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: s.color, boxShadow: `0 0 6px ${s.color}` }} />
              <span className="text-slate-400 truncate flex-1">{s.label}</span>
              <span className="text-slate-200 tabular-nums">{s.pct.toFixed(1)}%</span>
            </div>
          ))}
      </div>
    </div>
  );
}

// ── Per-frame analytics: today vs yesterday deltas + 7d/30d rolling
function FrameAnalytics({
  days,
  idx,
  cur,
  v,
  totalUsers,
}: {
  days: DailyPoint[];
  idx: number;
  cur: DailyPoint | undefined;
  v: (k: keyof DailyPoint) => number;
  totalUsers: number;
}) {
  if (!cur) return null;

  const sumWindow = (back: number, key: keyof DailyPoint): number => {
    const start = Math.max(0, idx - back + 1);
    let s = 0;
    for (let i = start; i <= idx; i++) s += Number(days[i][key]) || 0;
    return s;
  };

  const yesterday = idx > 0 ? days[idx - 1] : undefined;
  const lastWeek = idx >= 7 ? days[idx - 7] : undefined;

  const newToday = v("new_n");
  const newYday = yesterday?.new_n ?? 0;
  const dNewVsYday = newToday - newYday;

  const eventsToday = v("events");
  const eventsYday = yesterday?.events ?? 0;
  const dEventsVsYday = eventsToday - eventsYday;

  // 7-day window aggregates
  const w7_events = sumWindow(7, "events");
  const w7_new = sumWindow(7, "new_n");
  const w7_upgrades = sumWindow(7, "upgrade_events");
  // 30-day window
  const w30_events = sumWindow(30, "events");
  const w30_new = sumWindow(30, "new_n");
  const w30_upgrades = sumWindow(30, "upgrade_events");

  // Funnel conversion ratios at this point
  const cum_n = v("cum_n");
  const cum_active = v("cum_active");
  const cum_engaged = v("cum_engaged");
  const cum_upgraded = v("cum_upgraded");
  const cum_at_risk = v("cum_at_risk");

  const conv_active = cum_n > 0 ? (cum_active / cum_n) * 100 : 0;
  const conv_engaged_of_active = cum_active > 0 ? (cum_engaged / cum_active) * 100 : 0;
  const conv_upgraded_of_engaged = cum_engaged > 0 ? (cum_upgraded / cum_engaged) * 100 : 0;
  const conv_upgraded_overall = cum_n > 0 ? (cum_upgraded / cum_n) * 100 : 0;
  const at_risk_of_engaged = cum_engaged > 0 ? (cum_at_risk / cum_engaged) * 100 : 0;

  // 7-day-back rolling deltas (growth velocity)
  const dCumNVs7d = lastWeek ? cum_n - lastWeek.cum_n : 0;
  const dEngagedVs7d = lastWeek ? cum_engaged - lastWeek.cum_engaged : 0;
  const dUpgradedVs7d = lastWeek ? cum_upgraded - lastWeek.cum_upgraded : 0;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* TODAY vs YESTERDAY */}
      <div className="glass rounded-2xl p-5">
        <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-3">
          today · vs yesterday
        </div>
        <div className="space-y-2">
          <DeltaRow label="new users"   today={newToday}    delta={dNewVsYday}  goodIfPositive />
          <DeltaRow label="events"      today={eventsToday} delta={dEventsVsYday} goodIfPositive />
          <DeltaRow label="upgrades"    today={v("upgrade_events")} delta={v("upgrade_events") - (yesterday?.upgrade_events ?? 0)} goodIfPositive />
        </div>
      </div>

      {/* 7-DAY ROLLING WINDOW */}
      <div className="glass rounded-2xl p-5">
        <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-3">
          last 7 days · rolling window
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Stat7 label="new users"  value={w7_new} />
          <Stat7 label="events"     value={w7_events} />
          <Stat7 label="upgrades"   value={w7_upgrades} accent="text-pink-200" />
        </div>
        <div className="mt-3 pt-3 border-t border-slate-800/60 space-y-1.5">
          <DeltaRow label="users grew by" today={dCumNVs7d}        delta={0} hideDelta accent="text-emerald-200" />
          <DeltaRow label="engaged grew"  today={dEngagedVs7d}     delta={0} hideDelta accent="text-emerald-200" />
          <DeltaRow label="upgraded grew" today={dUpgradedVs7d}    delta={0} hideDelta accent="text-pink-300" />
        </div>
      </div>

      {/* 30-DAY ROLLING WINDOW */}
      <div className="glass rounded-2xl p-5">
        <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-3">
          last 30 days · rolling window
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Stat7 label="new users"  value={w30_new} />
          <Stat7 label="events"     value={w30_events} />
          <Stat7 label="upgrades"   value={w30_upgrades} accent="text-pink-200" />
        </div>
        <div className="mt-3 pt-3 border-t border-slate-800/60">
          <div className="text-[10px] font-mono text-slate-500 mb-1">monthly upgrade rate</div>
          <div className="text-2xl font-black tabular-nums text-pink-200">
            {w30_new > 0 ? ((w30_upgrades / w30_new) * 100).toFixed(2) : "0.00"}%
          </div>
          <div className="text-[10px] font-mono text-slate-500 mt-0.5">of users joining in last 30 days who upgraded same window</div>
        </div>
      </div>

      {/* CONVERSION RATES — full width */}
      <div className="glass rounded-2xl p-5 lg:col-span-3">
        <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono mb-3">
          stage-to-stage conversion · cumulative as of {cur.day}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <Conversion label="signed_up → active"        rate={conv_active}                  baseline={36.1} />
          <Conversion label="active → engaged"          rate={conv_engaged_of_active}        baseline={24.4} />
          <Conversion label="engaged → upgraded"        rate={conv_upgraded_of_engaged}      baseline={50.5} pink />
          <Conversion label="signed_up → upgraded"      rate={conv_upgraded_overall}         baseline={1.84} pink />
          <Conversion label="engaged → at_risk"         rate={at_risk_of_engaged}            baseline={78}    warn />
        </div>
      </div>
    </div>
  );
}

function DeltaRow({ label, today, delta, goodIfPositive, accent, hideDelta }: {
  label: string; today: number; delta: number; goodIfPositive?: boolean; accent?: string; hideDelta?: boolean;
}) {
  const upGood = goodIfPositive ? delta >= 0 : delta <= 0;
  const arrow = delta > 0 ? "↑" : delta < 0 ? "↓" : "·";
  const color = hideDelta ? "" : upGood ? "text-emerald-300" : "text-rose-300";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 text-xs text-slate-400 font-mono">{label}</div>
      <div className={`text-lg font-black tabular-nums ${accent ?? "text-slate-100"}`}>
        {fmtNum(today)}
      </div>
      {!hideDelta && (
        <div className={`text-[11px] font-mono tabular-nums w-16 text-right ${color}`}>
          {arrow} {fmtNum(Math.abs(delta))}
        </div>
      )}
    </div>
  );
}

function Stat7({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="space-y-0.5">
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500 font-mono">{label}</div>
      <div className={`text-xl font-black tabular-nums ${accent ?? "text-slate-100"}`}>{fmtNum(value)}</div>
    </div>
  );
}

function Conversion({ label, rate, baseline, pink, warn }: { label: string; rate: number; baseline: number; pink?: boolean; warn?: boolean }) {
  const color = warn ? "text-amber-300" : pink ? "text-pink-300" : "text-emerald-200";
  const ringColor = warn ? "#f59e0b" : pink ? "#ec4899" : "#10b981";
  const cmp = rate - baseline;
  const cmpColor = cmp > 0 ? (warn ? "text-rose-300" : "text-emerald-300") : cmp < 0 ? (warn ? "text-emerald-300" : "text-rose-300") : "text-slate-500";
  return (
    <div className="rounded-xl bg-ink-950/50 border border-slate-800/50 p-3 relative overflow-hidden">
      <div
        className="absolute inset-0 opacity-25 pointer-events-none"
        style={{ background: `radial-gradient(180px circle at 80% 0%, ${ringColor}55, transparent 70%)` }}
      />
      <div className="relative">
        <div className="text-[9px] uppercase tracking-[0.16em] text-slate-500 font-mono leading-tight">{label}</div>
        <div className={`text-2xl font-black tabular-nums ${color} mt-1`}>{rate.toFixed(2)}%</div>
        <div className={`text-[10px] font-mono mt-0.5 ${cmpColor}`}>
          {cmp >= 0 ? "+" : ""}{cmp.toFixed(2)}pp vs final
        </div>
      </div>
    </div>
  );
}
