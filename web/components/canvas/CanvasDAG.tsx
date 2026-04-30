"use client";

import { useCallback, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type Edge,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";

import {
  CANVAS_BLOCKS,
  CANVAS_EDGES,
  KIND_COLORS,
  type CanvasBlock,
} from "@/lib/canvas";
import BlockNode, { type BlockNodeData, type RunStatus } from "./BlockNode";
import BlockDetail from "./BlockDetail";

// Re-layout: keep horizontal columns (so the shape echoes the real Zerve canvas)
// but evenly-space within each column to remove the original vertical overlap.
const COL_X = [0, 350, 700, 1050, 1400, 1750, 2100, 2450, 2800];
const ROW_GAP = 170;

function layoutPositions(blocks: CanvasBlock[]) {
  const colMap = new Map<number, number>([
    [0, 0], [850, 1], [1700, 2], [2500, 3], [3400, 4],
    [5100, 5], [6800, 6], [8500, 7], [10200, 8],
  ]);
  const groups: Record<number, CanvasBlock[]> = {};
  for (const b of blocks) {
    const c = colMap.get(b.x) ?? 0;
    (groups[c] ??= []).push(b);
  }
  const out = new Map<string, { x: number; y: number }>();
  for (const c of Object.keys(groups).map(Number)) {
    groups[c]
      .sort((a, b) => a.y - b.y)
      .forEach((b, i) => out.set(b.id, { x: COL_X[c], y: i * ROW_GAP }));
  }
  return out;
}

const nodeTypes = { block: BlockNode };

export default function CanvasDAG() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statuses, setStatuses] = useState<Record<string, RunStatus>>({});

  const positions = useMemo(() => layoutPositions(CANVAS_BLOCKS), []);

  const setStatus = useCallback((id: string, s: RunStatus) => {
    setStatuses((prev) => ({ ...prev, [id]: s }));
  }, []);

  const onClick = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const nodes: Node<BlockNodeData>[] = useMemo(
    () =>
      CANVAS_BLOCKS.map((b) => {
        const p = positions.get(b.id)!;
        return {
          id: b.id,
          type: "block",
          position: p,
          data: {
            ...b,
            status: statuses[b.id] ?? "idle",
            selected: selectedId === b.id,
            onClick,
          },
        };
      }),
    [positions, statuses, selectedId, onClick],
  );

  const edges: Edge[] = useMemo(
    () =>
      CANVAS_EDGES.map((e) => {
        const target = CANVAS_BLOCKS.find((b) => b.id === e.target);
        const ring = target ? KIND_COLORS[target.kind].ring : "#64748b";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          animated: statuses[e.target] === "running",
          style: { stroke: ring, strokeWidth: 1.5, opacity: 0.5 },
        };
      }),
    [statuses],
  );

  return (
    <div className="relative h-[760px] w-full overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-900/60">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={28}
          size={1}
          color="#1e293b"
        />
        <Controls
          showInteractive={false}
          className="!bg-slate-900/60 !border-slate-700"
        />
        <MiniMap
          nodeColor={(n) =>
            KIND_COLORS[(n.data as BlockNodeData).kind].ring
          }
          maskColor="rgba(2,6,23,0.7)"
          className="!bg-slate-900/60 !border-slate-700"
          pannable
          zoomable
        />
      </ReactFlow>

      <BlockDetail
        blockId={selectedId}
        onClose={() => setSelectedId(null)}
        onStatus={setStatus}
      />

      <Legend />
    </div>
  );
}

function Legend() {
  const kinds = Object.entries(KIND_COLORS);
  return (
    <div className="absolute left-4 top-4 z-10 flex flex-wrap gap-2 rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 backdrop-blur">
      {kinds.map(([k, c]) => (
        <span
          key={k}
          className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-300"
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: c.ring }}
          />
          {c.label}
        </span>
      ))}
    </div>
  );
}
