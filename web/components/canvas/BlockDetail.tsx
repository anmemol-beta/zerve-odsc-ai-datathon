"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, figureUrl } from "@/lib/api";
import { blockById, KIND_COLORS } from "@/lib/canvas";
import type { RunStatus } from "./BlockNode";

export default function BlockDetail({
  blockId,
  onClose,
  onStatus,
}: {
  blockId: string | null;
  onClose: () => void;
  onStatus: (id: string, s: RunStatus) => void;
}) {
  const block = blockId ? blockById(blockId) : null;
  const [bust, setBust] = useState(0);
  const [pulled, setPulled] = useState(false);

  const lastSig = useRef<string>("");
  useEffect(() => {
    if (!block) return;
    const sig = `${block.id}:${bust}`;
    if (lastSig.current === sig) return;
    lastSig.current = sig;
    setPulled(false);
    onStatus(block.id, "running");
  }, [block, bust, onStatus]);

  const variableQuery = useQuery({
    queryKey: ["block-vars", block?.name, bust],
    queryFn: () => api.blockVars(block!.name),
    enabled: !!block,
  });

  // Status badge: roll up var-fetch + figure-load completion.
  useEffect(() => {
    if (!block || pulled) return;
    if (variableQuery.isError) {
      onStatus(block.id, "error");
      setPulled(true);
      return;
    }
    if (variableQuery.isSuccess && !block.hasFigure) {
      onStatus(block.id, "done");
      setPulled(true);
    }
  }, [block, variableQuery.isSuccess, variableQuery.isError, pulled, onStatus]);

  if (!block) return null;
  const c = KIND_COLORS[block.kind];

  return (
    <div className="absolute right-0 top-0 z-20 flex h-full w-full max-w-[440px] flex-col border-l border-slate-200 bg-slate-50 backdrop-blur-md">
      <header className="flex items-start justify-between gap-3 border-b border-slate-200 p-5">
        <div className="space-y-1.5">
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider"
            style={{ background: c.bg, color: c.ring }}
          >
            {c.label}
          </span>
          <h3 className="text-lg font-semibold tracking-tight text-slate-900">
            {block.name}
          </h3>
          <p className="text-xs leading-relaxed text-slate-400">
            {block.description}
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-900"
        >
          ✕
        </button>
      </header>

      <div className="flex-1 space-y-5 overflow-y-auto p-5">
        {block.hasFigure && (
          <FigurePane
            block={block.name}
            bust={bust}
            onLoad={() => {
              onStatus(block.id, "done");
              setPulled(true);
            }}
            onError={() => {
              onStatus(block.id, "error");
              setPulled(true);
            }}
          />
        )}

        <section>
          <SectionTitle>Live variables · zerve.variable()</SectionTitle>
          {variableQuery.isLoading && <Skeleton />}
          {variableQuery.isError && <ErrorBanner error={variableQuery.error} />}
          {variableQuery.isSuccess &&
            (Object.keys(variableQuery.data).length === 0 ? (
              <p className="text-xs text-slate-500">
                no non-figure variables registered for this block.
              </p>
            ) : (
              <VariablePreview vars={variableQuery.data} />
            ))}
        </section>
      </div>

      <footer className="border-t border-slate-200 p-4">
        <button
          onClick={() => setBust((n) => n + 1)}
          className="w-full rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs font-medium text-cyan-200 transition hover:bg-cyan-50"
        >
          ↻ Re-pull from canvas
        </button>
      </footer>
    </div>
  );
}

function VariablePreview({ vars }: { vars: Record<string, unknown> }) {
  return (
    <div className="space-y-3">
      {Object.entries(vars).map(([slot, value]) => (
        <div
          key={slot}
          className="rounded-md border border-slate-200 bg-slate-50"
        >
          <div className="border-b border-slate-200 px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-400">
            {slot}
          </div>
          <pre className="max-h-[260px] overflow-auto p-3 text-[11px] leading-relaxed text-slate-300">
            {JSON.stringify(value, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

function FigurePane({
  block,
  bust,
  onLoad,
  onError,
}: {
  block: string;
  bust: number;
  onLoad: () => void;
  onError: () => void;
}) {
  return (
    <section>
      <SectionTitle>matplotlib · live from canvas</SectionTitle>
      <div className="overflow-hidden rounded-md border border-slate-200 bg-slate-100">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={figureUrl(block, bust)}
          alt={`${block} figure`}
          className="block w-full"
          onLoad={onLoad}
          onError={onError}
        />
      </div>
    </section>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
      {children}
    </h4>
  );
}

function Skeleton() {
  return (
    <div className="h-24 animate-pulse rounded-md border border-slate-200 bg-slate-50" />
  );
}

function ErrorBanner({ error }: { error: unknown }) {
  return (
    <div className="rounded-md border border-rose-500/40 bg-rose-50 p-3 text-[11px] text-rose-200">
      <strong>fetch failed</strong> — {String(error)}
      <div className="mt-1 text-rose-600/70">
        Block name in BLOCKS map may not match the canvas variable name. Edit
        zerve_deploy/main.py and re-deploy, or click ↻ once the block runs.
      </div>
    </div>
  );
}
