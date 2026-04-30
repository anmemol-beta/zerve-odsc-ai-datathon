"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import {
  sankey,
  sankeyLinkHorizontal,
  type SankeyGraph,
  type SankeyLink,
  type SankeyNode,
} from "d3-sankey";
import { ACCENT } from "@/lib/colors";
import { STAGE_COLOR, STAGE_LABEL } from "@/lib/stage-labels";
import { fmtNum, fmtPct } from "@/lib/format";
import {
  FALLBACK_FUNNEL_STAGES,
  FALLBACK_POST_UPGRADE,
  type FunnelStage,
} from "@/lib/fallbacks";

const MAIN_ORDER = [
  "1.New", "2.Exploring", "3.Created", "4.UsedAI",
  "5.WroteCode", "6.Integrated", "7.Engaged", "8.Upgraded",
];

const AT_RISK_BY_STAGE: Record<string, string> = {
  "4.UsedAI":      "9.AtRisk@UsedAI",
  "5.WroteCode":   "9.AtRisk@WroteCode",
  "6.Integrated":  "9.AtRisk@Integrated",
  "7.Engaged":     "9.AtRisk@Engaged",
};

type N = { id: string; label: string; reach: number };
type L = { source: number; target: number; value: number; kind: "advance" | "stall" | "drop" };

// Build cohort sankey: every user is a unit of flow that enters at "1.New",
// optionally stalls into AtRisk@X, and the rest advances to the next stage.
function buildSankey(stages: FunnelStage[]): { nodes: N[]; links: L[] } {
  const byId = new Map(stages.map((s) => [s.id, s]));

  // "Reach" of each main stage = users currently there or further along.
  // Working backward: reached Upgraded = 221+74+28 = 323; each prior stage
  // adds the residents at that stage and the AtRisk@<that stage> group.
  const upgraders =
    (byId.get("8.Upgraded")?.users ?? 0) +
    (byId.get("9.AtRisk@Upgraded")?.users ?? 0) +
    (byId.get("9.Churned@Upgraded")?.users ?? 0);

  const reach = new Map<string, number>();
  reach.set("8.Upgraded", upgraders);

  for (let i = MAIN_ORDER.length - 2; i >= 0; i--) {
    const id = MAIN_ORDER[i];
    const next = MAIN_ORDER[i + 1];
    const stalledNextId = AT_RISK_BY_STAGE[next];
    const residents = byId.get(id)?.users ?? 0;
    const stalledNext = stalledNextId ? byId.get(stalledNextId)?.users ?? 0 : 0;
    reach.set(id, residents + (reach.get(next) ?? 0) + stalledNext);
  }

  const nodes: N[] = MAIN_ORDER.map((id) => ({
    id,
    label: STAGE_LABEL[id] ?? id,
    reach: reach.get(id) ?? 0,
  }));
  // Append AtRisk sinks so stalls have a target.
  const stallSinks: Record<string, number> = {};
  Object.entries(AT_RISK_BY_STAGE).forEach(([_main, atRiskId]) => {
    const sinkIdx = nodes.length;
    stallSinks[atRiskId] = sinkIdx;
    nodes.push({
      id: atRiskId,
      label: STAGE_LABEL[atRiskId] ?? atRiskId,
      reach: byId.get(atRiskId)?.users ?? 0,
    });
  });
  // Drop-off sink — everyone who never made it past stage i.
  const dropIdx = nodes.length;
  nodes.push({ id: "_drop", label: "Stayed put", reach: 0 });

  const links: L[] = [];
  for (let i = 0; i < MAIN_ORDER.length - 1; i++) {
    const fromId = MAIN_ORDER[i];
    const toId = MAIN_ORDER[i + 1];
    const fromIdx = i;
    const toIdx = i + 1;
    const fromReach = reach.get(fromId) ?? 0;
    const toReach = reach.get(toId) ?? 0;
    const stalledNext = AT_RISK_BY_STAGE[toId]
      ? byId.get(AT_RISK_BY_STAGE[toId])?.users ?? 0
      : 0;
    const stayed = byId.get(fromId)?.users ?? 0;

    if (toReach > 0) {
      links.push({ source: fromIdx, target: toIdx, value: toReach, kind: "advance" });
    }
    if (stalledNext > 0) {
      links.push({
        source: fromIdx,
        target: stallSinks[AT_RISK_BY_STAGE[toId]],
        value: stalledNext,
        kind: "stall",
      });
    }
    if (stayed > 0) {
      // "Stayed put at this stage" → drop sink (only show first-time per node).
      links.push({ source: fromIdx, target: dropIdx, value: stayed, kind: "drop" });
    }
    // ensure flow conservation: fromReach == toReach + stalledNext + stayed
    void fromReach;
  }

  return { nodes, links };
}

const W = 920;
const H = 360;

export default function FunnelView() {
  const { nodes, links, layout } = useMemo(() => {
    const g = buildSankey(FALLBACK_FUNNEL_STAGES);
    const sk = sankey<N, L>()
      .nodeWidth(14)
      .nodePadding(14)
      .extent([
        [16, 16],
        [W - 16, H - 16],
      ]);
    const graph = sk({
      nodes: g.nodes.map((n) => ({ ...n })),
      links: g.links.map((l) => ({ ...l })),
    } as unknown as SankeyGraph<N, L>);
    return { nodes: g.nodes, links: g.links, layout: graph };
  }, []);

  const linkPath = sankeyLinkHorizontal<N, L>();

  const linkColor = (kind: L["kind"]) => {
    if (kind === "advance") return "url(#advance-grad)";
    if (kind === "stall")   return "rgba(245, 158, 11, 0.45)"; // amber
    return "rgba(100, 116, 139, 0.25)";                         // slate (drop)
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      {/* Sankey */}
      <div className={`glass rounded-2xl border p-4 ${ACCENT.violet.border}`}>
        <div className="mb-3 flex items-center justify-between">
          <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.violet.text}`}>
            Funnel · strict-nested cohorts
          </div>
          <div className="flex items-center gap-3 text-[10px] text-slate-400">
            <Legend swatch="bg-gradient-to-r from-violet-500 to-pink-500" label="advance" />
            <Legend swatch="bg-amber-50" label="stall" />
            <Legend swatch="bg-slate-500/40" label="stayed" />
          </div>
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Funnel sankey">
          <defs>
            <linearGradient id="advance-grad" x1="0" x2="1" y1="0" y2="0">
              <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.55" />
              <stop offset="100%" stopColor="#ec4899" stopOpacity="0.55" />
            </linearGradient>
          </defs>

          {/* links */}
          <g fill="none">
            {layout.links.map((d, i) => {
              const path = linkPath(d as SankeyLink<N, L>) ?? "";
              const ld = links[i];
              return (
                <motion.path
                  key={i}
                  d={path}
                  stroke={linkColor(ld.kind)}
                  strokeWidth={Math.max(1, d.width ?? 0)}
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: 0.04 * i }}
                />
              );
            })}
          </g>

          {/* nodes */}
          <g>
            {layout.nodes.map((d, i) => {
              const n = d as SankeyNode<N, L>;
              const isMain = MAIN_ORDER.includes(n.id);
              const isDrop = n.id === "_drop";
              const c = STAGE_COLOR[n.id];
              const fill = isMain
                ? "#8b5cf6"
                : n.id.startsWith("9.AtRisk")
                ? "#f59e0b"
                : "#475569";
              if (isDrop) return null;
              return (
                <g key={i}>
                  <rect
                    x={n.x0 ?? 0}
                    y={n.y0 ?? 0}
                    width={(n.x1 ?? 0) - (n.x0 ?? 0)}
                    height={Math.max(1, (n.y1 ?? 0) - (n.y0 ?? 0))}
                    fill={fill}
                    rx={3}
                  />
                  <text
                    x={(n.x0 ?? 0) < W / 2 ? (n.x1 ?? 0) + 6 : (n.x0 ?? 0) - 6}
                    y={((n.y0 ?? 0) + (n.y1 ?? 0)) / 2}
                    dy="0.35em"
                    textAnchor={(n.x0 ?? 0) < W / 2 ? "start" : "end"}
                    fontSize={10}
                    fill={c?.fg.includes("text-") ? "#cbd5e1" : "#cbd5e1"}
                    className="font-mono"
                  >
                    {nodes[i]?.label}
                  </text>
                  <text
                    x={(n.x0 ?? 0) < W / 2 ? (n.x1 ?? 0) + 6 : (n.x0 ?? 0) - 6}
                    y={((n.y0 ?? 0) + (n.y1 ?? 0)) / 2 + 12}
                    textAnchor={(n.x0 ?? 0) < W / 2 ? "start" : "end"}
                    fontSize={9}
                    fill="#64748b"
                    className="tabular-nums"
                  >
                    {fmtNum(nodes[i]?.reach ?? 0)}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
        <div className="mt-3 text-xs leading-relaxed text-slate-500">
          17,541 users enter at <span className="text-slate-300">Signed up</span>; 323
          (1.84%) make it to <span className="text-pink-600">Paying</span>. The amber
          ribbons mark cohorts that reach a stage and stall — those are the ones the
          model will single out.
        </div>
      </div>

      {/* Post-upgrade donut */}
      <PostUpgradeDonut />
    </div>
  );
}

function Legend({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-1.5 w-4 rounded-full ${swatch}`} />
      <span>{label}</span>
    </span>
  );
}

function PostUpgradeDonut() {
  const p = FALLBACK_POST_UPGRADE;
  const total = p.active + p.at_risk + p.churned;
  const segs = [
    { key: "active",  value: p.active,  color: "#22d3ee", label: "Active",   accent: ACCENT.cyan },
    { key: "at_risk", value: p.at_risk, color: "#f59e0b", label: "At risk",  accent: ACCENT.amber },
    { key: "churned", value: p.churned, color: "#f43f5e", label: "Churned",  accent: ACCENT.rose },
  ];
  const SIZE = 180;
  const R = 72;
  const STROKE = 22;
  const C = 2 * Math.PI * R;
  let acc = 0;

  return (
    <div className={`glass rounded-2xl border p-5 ${ACCENT.cyan.border}`}>
      <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.cyan.text}`}>
        Post-upgrade fate
      </div>
      <div className="mt-1 text-xs text-slate-400">
        Of the {total} paying users — what happened next
      </div>
      <div className="mt-4 flex items-center justify-center">
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
          <g transform={`translate(${SIZE / 2} ${SIZE / 2}) rotate(-90)`}>
            <circle r={R} fill="none" stroke="rgba(241, 245, 249, 0.6)" strokeWidth={STROKE} />
            {segs.map((s) => {
              const frac = s.value / total;
              const dash = `${frac * C} ${C}`;
              const offset = -acc * C;
              acc += frac;
              return (
                <motion.circle
                  key={s.key}
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={STROKE}
                  strokeDasharray={dash}
                  strokeDashoffset={offset}
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.7 }}
                />
              );
            })}
          </g>
          <text
            x={SIZE / 2}
            y={SIZE / 2 - 4}
            textAnchor="middle"
            fontSize={28}
            fill="#0f172a"
            className="font-bold tabular-nums"
          >
            {total}
          </text>
          <text
            x={SIZE / 2}
            y={SIZE / 2 + 16}
            textAnchor="middle"
            fontSize={10}
            fill="#64748b"
            className="font-mono uppercase tracking-[0.2em]"
          >
            paying users
          </text>
        </svg>
      </div>
      <div className="mt-4 flex flex-col gap-2">
        {segs.map((s) => (
          <div key={s.key} className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              <span className="text-slate-300">{s.label}</span>
            </span>
            <span className="tabular-nums text-slate-400">
              {s.value} · {fmtPct(s.value / total, 1)}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 text-xs leading-relaxed text-slate-500">
        Even after upgrading, ~32% drift toward at-risk or churned — the retention drip
        in the playbook targets this slice.
      </div>
    </div>
  );
}
