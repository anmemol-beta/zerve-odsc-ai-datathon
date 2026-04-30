"use client";

import { Handle, Position } from "reactflow";
import { KIND_COLORS, type CanvasBlock } from "@/lib/canvas";

export type RunStatus = "idle" | "running" | "done" | "error";

export type BlockNodeData = CanvasBlock & {
  status: RunStatus;
  selected?: boolean;
  onClick: (id: string) => void;
};

export default function BlockNode({ data }: { data: BlockNodeData }) {
  const c = KIND_COLORS[data.kind];
  const ringColor =
    data.status === "running"
      ? "#22d3ee"
      : data.status === "error"
        ? "#f87171"
        : data.status === "done"
          ? "#4ade80"
          : c.ring;
  return (
    <div
      onClick={() => data.onClick(data.id)}
      className="group relative w-[300px] cursor-pointer rounded-xl border bg-slate-900/60 px-4 py-3 text-left text-slate-100 shadow-[0_8px_30px_rgba(0,0,0,0.5)] backdrop-blur-md transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_12px_40px_rgba(99,102,241,0.25)]"
      style={{
        borderColor: ringColor,
        background: `linear-gradient(155deg, ${c.bg}, rgba(2,6,23,0.92))`,
        boxShadow: data.selected
          ? `0 0 0 2px ${ringColor}, 0 8px 30px rgba(0,0,0,0.5)`
          : undefined,
      }}
    >
      {data.status === "running" && (
        <div
          className="absolute inset-0 -z-10 animate-pulse rounded-xl"
          style={{ boxShadow: `0 0 30px ${ringColor}` }}
        />
      )}

      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-0"
        style={{ background: c.ring }}
      />
      <div className="flex items-center justify-between gap-2">
        <span
          className="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider"
          style={{ background: c.bg, color: c.ring }}
        >
          {c.label}
        </span>
        <StatusBadge status={data.status} />
      </div>
      <div className="mt-2 font-semibold tracking-tight">{data.name}</div>
      <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-slate-400">
        {data.description}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-0"
        style={{ background: c.ring }}
      />
    </div>
  );
}

function StatusBadge({ status }: { status: RunStatus }) {
  const map = {
    idle: { dot: "bg-slate-900/600", text: "idle", color: "text-slate-400" },
    running: { dot: "bg-cyan-400 animate-pulse", text: "running", color: "text-cyan-300" },
    done: { dot: "bg-emerald-400", text: "done", color: "text-emerald-300" },
    error: { dot: "bg-rose-400", text: "error", color: "text-rose-300" },
  } as const;
  const m = map[status];
  return (
    <span className={`flex items-center gap-1.5 text-[10px] ${m.color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} />
      {m.text}
    </span>
  );
}
