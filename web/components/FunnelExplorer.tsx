"use client";

import { useMemo, useState } from "react";
import { sankey, sankeyLinkHorizontal } from "d3-sankey";
import type { FunnelGrid } from "@/lib/types";

const STAGE_NAMES = ["signed up", "active", "created", "used AI", "engaged", "upgraded"];
const STAGE_COLORS = ["#475569", "#3b82f6", "#06b6d4", "#10b981", "#84cc16", "#ec4899"];

type SankeyNode = { name: string; kind: "stage" | "drop"; idx?: number };
type SankeyLink = { source: number; target: number; value: number };

export default function FunnelExplorer({ grid }: { grid: FunnelGrid }) {
  const [signin, setSignin] = useState(2);
  const [days, setDays]     = useState(3);
  const [ai, setAi]         = useState(1);

  const reach = useMemo(() => {
    const found = grid.grid.find((g) => g.s === signin && g.d === days && g.a === ai);
    return found?.r ?? grid.grid[0].r;
  }, [grid, signin, days, ai]);

  const total = reach[0];
  const dropped = reach.slice(0, -1).map((v, i) => v - reach[i + 1]);

  // Build sankey input
  const { sankeyNodes, sankeyLinks } = useMemo(() => {
    const nodes: SankeyNode[] = [
      ...STAGE_NAMES.map((n, i) => ({ name: n, kind: "stage" as const, idx: i })),
      ...STAGE_NAMES.slice(0, -1).map((n) => ({ name: `dropped@${n}`, kind: "drop" as const })),
    ];
    const links: SankeyLink[] = [];
    for (let i = 0; i < STAGE_NAMES.length - 1; i++) {
      const passThrough = reach[i + 1];
      const dropAtI = dropped[i];
      if (passThrough > 0) links.push({ source: i, target: i + 1, value: passThrough });
      if (dropAtI > 0) links.push({ source: i, target: STAGE_NAMES.length + i, value: dropAtI });
    }
    return { sankeyNodes: nodes, sankeyLinks: links };
  }, [reach, dropped]);

  const W = 1100, H = 460;

  const layout = useMemo(() => {
    const sk = (sankey() as any)
      .nodeWidth(18)
      .nodePadding(14)
      .extent([
        [10, 30],
        [W - 200, H - 30],
      ]);
    const graph = sk({
      nodes: sankeyNodes.map((d) => ({ ...d })),
      links: sankeyLinks.map((d) => ({ ...d })),
    });
    return graph as { nodes: any[]; links: any[] };
  }, [sankeyNodes, sankeyLinks]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SliderCard
          label="active threshold"
          desc="`n_signins ≥ ?`  (or distinct_days ≥ 2)"
          min={grid.signin_values[0]}
          max={grid.signin_values[grid.signin_values.length - 1]}
          step={1}
          value={signin}
          onChange={setSignin}
        />
        <SliderCard
          label="engaged days threshold"
          desc="`n_distinct_days ≥ ?`"
          min={grid.days_values[0]}
          max={grid.days_values[grid.days_values.length - 1]}
          step={1}
          value={days}
          onChange={setDays}
        />
        <DiscreteCard
          label="used_ai threshold"
          desc="`n_ai ≥ ?`"
          values={grid.ai_values}
          value={ai}
          onChange={setAi}
        />
      </div>

      <div className="glass rounded-2xl p-4">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" style={{ maxHeight: 460 }}>
          <defs>
            {layout.links.map((l: any, i: number) => {
              const sIdx = l.source.index ?? 0;
              const tIsDrop = l.target.kind === "drop";
              const startColor = STAGE_COLORS[sIdx] ?? "#475569";
              const endColor = tIsDrop ? "#7f1d1d" : STAGE_COLORS[l.target.index ?? 0] ?? "#475569";
              return (
                <linearGradient key={`g-${i}`} id={`g-${i}`} gradientUnits="userSpaceOnUse" x1={l.source.x1} x2={l.target.x0}>
                  <stop offset="0%"  stopColor={startColor} stopOpacity={0.7} />
                  <stop offset="100%" stopColor={endColor}   stopOpacity={tIsDrop ? 0.5 : 0.7} />
                </linearGradient>
              );
            })}
          </defs>

          {layout.links.map((l: any, i: number) => (
            <path
              key={i}
              d={(sankeyLinkHorizontal() as any)(l) ?? ""}
              fill="none"
              stroke={`url(#g-${i})`}
              strokeWidth={Math.max(1.2, l.width ?? 1)}
              className="transition-all"
            />
          ))}

          {layout.nodes.map((n: any, i: number) => {
            const isStage = n.kind === "stage";
            const fill = isStage ? STAGE_COLORS[n.idx ?? 0] : "#7f1d1d";
            const value = n.value ?? 0;
            return (
              <g key={i}>
                <rect
                  x={n.x0}
                  y={n.y0}
                  width={(n.x1 ?? 0) - (n.x0 ?? 0)}
                  height={Math.max(2, (n.y1 ?? 0) - (n.y0 ?? 0))}
                  fill={fill}
                  rx={3}
                />
                <text
                  x={(n.x1 ?? 0) + 8}
                  y={((n.y0 ?? 0) + (n.y1 ?? 0)) / 2}
                  dominantBaseline="middle"
                  className="font-mono"
                  fontSize={11}
                  fill={isStage ? "#e2e8f0" : "#fca5a5"}
                >
                  {n.name}
                  <tspan fill="#64748b" dx={6}>
                    {value.toLocaleString()}
                  </tspan>
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="glass rounded-2xl p-4 overflow-hidden">
        <table className="w-full text-xs font-mono">
          <thead className="text-slate-500 uppercase text-[10px] tracking-wider">
            <tr>
              <th className="text-left pb-2 pl-2">stage</th>
              <th className="text-right pb-2">users</th>
              <th className="text-right pb-2">% of total</th>
              <th className="text-right pb-2 pr-2">conv from prior</th>
            </tr>
          </thead>
          <tbody>
            {STAGE_NAMES.map((s, i) => {
              const v = reach[i];
              const pct = (100 * v) / total;
              const conv = i === 0 ? null : (100 * v) / reach[i - 1];
              return (
                <tr key={s} className="border-t border-slate-800/60">
                  <td className="py-2 pl-2 text-slate-200 flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: STAGE_COLORS[i], boxShadow: `0 0 6px ${STAGE_COLORS[i]}` }}
                    />
                    {s}
                  </td>
                  <td className="text-right text-slate-200">{v.toLocaleString()}</td>
                  <td className="text-right text-slate-400">{pct.toFixed(2)}%</td>
                  <td className="text-right pr-2 text-slate-400">{conv === null ? "—" : `${conv.toFixed(1)}%`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SliderCard({
  label, desc, min, max, step, value, onChange,
}: {
  label: string; desc: string; min: number; max: number; step: number;
  value: number; onChange: (v: number) => void;
}) {
  return (
    <div className="glass rounded-2xl p-4">
      <div className="flex justify-between items-baseline">
        <div className="text-xs uppercase tracking-wider text-slate-400">{label}</div>
        <div className="text-2xl font-bold text-slate-100 font-mono">{value}</div>
      </div>
      <div className="text-[10px] text-slate-500 mt-1 font-mono">{desc}</div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        className="w-full mt-3"
      />
    </div>
  );
}

function DiscreteCard({
  label, desc, values, value, onChange,
}: {
  label: string; desc: string; values: number[];
  value: number; onChange: (v: number) => void;
}) {
  return (
    <div className="glass rounded-2xl p-4">
      <div className="flex justify-between items-baseline">
        <div className="text-xs uppercase tracking-wider text-slate-400">{label}</div>
        <div className="text-2xl font-bold text-slate-100 font-mono">{value}</div>
      </div>
      <div className="text-[10px] text-slate-500 mt-1 font-mono">{desc}</div>
      <div className="grid grid-cols-7 gap-1 mt-3">
        {values.map((v) => (
          <button
            key={v}
            onClick={() => onChange(v)}
            className={`text-[11px] font-mono py-1 rounded transition ${
              v === value
                ? "bg-pink-500/30 text-pink-200 border border-pink-500/60"
                : "bg-slate-800/60 text-slate-400 hover:bg-slate-700"
            }`}
          >
            {v}
          </button>
        ))}
      </div>
    </div>
  );
}
