"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { FALLBACK_STRATEGIES_SEGMENTS } from "@/lib/fallbacks";

type StrategyAction = {
  rank?: number;
  title?: string;
  channel?: string;
  message_en?: string;
  target_filter?: string;
  expected_uplift_pp?: number;
  estimated_roi_multiple?: number;
  rationale?: string;
};

type SegmentEntry = {
  segment_id: string;
  label?: string;
  stats?: {
    size?: number;
    pct_of_total?: number;
    observed_rate?: number;
    baseline_lift?: number;
  };
  strategy?: {
    summary?: string;
    actions?: StrategyAction[];
    risks?: string[];
  };
};

const CHANNEL_COLOR: Record<string, string> = {
  email:             "text-cyan-300 border-cyan-400/40 bg-cyan-500/15",
  in_app_modal:      "text-pink-300 border-pink-400/40 bg-pink-500/15",
  sales_call:        "text-amber-300 border-amber-400/40 bg-amber-500/15",
  push_notification: "text-violet-300 border-violet-400/40 bg-violet-500/15",
  ad_retargeting:    "text-emerald-300 border-emerald-400/40 bg-emerald-500/15",
  lifecycle_drip:    "text-blue-300 border-blue-400/40 bg-blue-500/15",
};

export default function StrategyGallery() {
  const segments = useQuery({
    queryKey: ["strategy-segments"],
    queryFn: api.strategySegments,
    retry: 1,
  });

  // Fall back to the inline canon if the API isn't reachable.
  const live = (segments.data as SegmentEntry[] | undefined) ?? [];
  const list: SegmentEntry[] =
    live.length > 0 ? live : (FALLBACK_STRATEGIES_SEGMENTS as SegmentEntry[]);
  const usingFallback = live.length === 0;

  const [selected, setSelected] = useState<string | null>(null);

  const current = useMemo(
    () => list.find((s) => s.segment_id === selected) ?? list[0],
    [list, selected],
  );

  if (segments.isLoading)
    return <div className="glass h-[420px] animate-pulse rounded-2xl" />;

  return (
    <div className="space-y-3">
      {usingFallback && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/15 px-3 py-2 text-[11px] text-amber-200">
          live <code className="rounded bg-slate-900 px-1 py-0.5">/strategies/segments</code> unavailable — showing the offline cohort baked into the bundle.
        </div>
      )}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr]">
        <SegmentList
          segments={list}
          selected={current?.segment_id ?? null}
          onSelect={setSelected}
        />
        <AnimatePresence mode="wait">
          <motion.div
            key={current?.segment_id ?? "empty"}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }}
            transition={{ duration: 0.25 }}
          >
            {current && <SegmentDetail segment={current} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function SegmentList({
  segments,
  selected,
  onSelect,
}: {
  segments: SegmentEntry[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="glass max-h-[520px] overflow-y-auto rounded-2xl p-3">
      <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        14 v4 segments
      </div>
      <div className="space-y-1">
        {segments.map((s) => {
          const isSel = s.segment_id === selected;
          const lift = s.stats?.baseline_lift ?? 0;
          return (
            <button
              key={s.segment_id}
              onClick={() => onSelect(s.segment_id)}
              className={`flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-xs transition ${
                isSel
                  ? "bg-pink-500/15 text-pink-100 ring-1 ring-pink-400/40"
                  : "text-slate-300 hover:bg-slate-900"
              }`}
            >
              <span className="truncate">{s.label ?? s.segment_id}</span>
              <span
                className={`flex-shrink-0 rounded-full px-1.5 py-0.5 text-[9px] tabular-nums ${
                  lift > 1 ? "bg-emerald-500/15 text-emerald-300" : "bg-slate-800 text-slate-400"
                }`}
              >
                {lift.toFixed(1)}×
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SegmentDetail({ segment }: { segment: SegmentEntry }) {
  const stats = segment.stats;
  const actions = segment.strategy?.actions ?? [];
  const risks = segment.strategy?.risks ?? [];

  return (
    <div className="glass space-y-5 rounded-2xl p-6">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            segment
          </div>
          <h3 className="text-lg font-semibold tracking-tight text-slate-100">
            {segment.label ?? segment.segment_id}
          </h3>
        </div>
        <div className="grid grid-cols-3 gap-3 text-right text-xs">
          {stats?.size !== undefined && (
            <Stat label="users" value={stats.size.toLocaleString()} />
          )}
          {stats?.observed_rate !== undefined && (
            <Stat
              label="upgrade rate"
              value={`${(stats.observed_rate * 100).toFixed(2)}%`}
            />
          )}
          {stats?.baseline_lift !== undefined && (
            <Stat
              label="lift"
              value={`${stats.baseline_lift.toFixed(1)}×`}
              accent="text-emerald-300"
            />
          )}
        </div>
      </header>

      {segment.strategy?.summary && (
        <p className="text-sm leading-relaxed text-slate-300">
          {segment.strategy.summary}
        </p>
      )}

      <div className="space-y-3">
        <SectionTitle>3 ranked actions · K2-Think</SectionTitle>
        {actions.map((a, i) => (
          <ActionCard key={i} action={a} />
        ))}
      </div>

      {risks.length > 0 && (
        <div>
          <SectionTitle>risks</SectionTitle>
          <ul className="space-y-1.5 text-xs text-slate-400">
            {risks.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-amber-300">·</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ActionCard({ action }: { action: StrategyAction }) {
  const channelClass = action.channel
    ? CHANNEL_COLOR[action.channel] ?? "text-slate-300 border-slate-700 bg-slate-900"
    : "text-slate-300 border-slate-700 bg-slate-900";
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-pink-300">
              #{action.rank ?? "?"}
            </span>
            <span className="font-medium text-slate-100">{action.title ?? "—"}</span>
          </div>
          {action.message_en && (
            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              {action.message_en}
            </p>
          )}
          {action.target_filter && (
            <code className="mt-2 inline-block rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-cyan-300">
              {action.target_filter}
            </code>
          )}
        </div>
        <div className="flex flex-col items-end gap-1">
          {action.channel && (
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${channelClass}`}
            >
              {action.channel}
            </span>
          )}
          {action.estimated_roi_multiple !== undefined && (
            <span className="text-xs tabular-nums text-emerald-300">
              {action.estimated_roi_multiple.toFixed(1)}× ROI
            </span>
          )}
          {action.expected_uplift_pp !== undefined && (
            <span className="text-[10px] tabular-nums text-slate-400">
              +{action.expected_uplift_pp.toFixed(2)}pp
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = "text-slate-100",
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">
        {label}
      </div>
      <div className={`text-sm font-medium tabular-nums ${accent}`}>{value}</div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
      {children}
    </h4>
  );
}
