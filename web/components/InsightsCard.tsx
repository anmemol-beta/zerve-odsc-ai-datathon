"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { FALLBACK_INSIGHTS_TEXT } from "@/lib/fallbacks";

export default function InsightsCard() {
  const insights = useQuery({
    queryKey: ["insights"],
    queryFn: api.insights,
    retry: 1,
  });

  const text =
    (insights.data as { text?: string } | undefined)?.text ?? FALLBACK_INSIGHTS_TEXT;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]">
      <div className="glass overflow-hidden rounded-2xl">
        <div className="border-b border-slate-700 bg-slate-900/60 px-5 py-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
            // insights · headline
          </span>
        </div>
        <div className="bg-slate-950 p-5">
          <InsightVisual />
        </div>
      </div>

      <div className="glass space-y-3 rounded-2xl p-6">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          insights_text
        </span>
        {insights.isLoading && (
          <div className="space-y-2">
            <div className="h-3 animate-pulse rounded bg-slate-800" />
            <div className="h-3 w-5/6 animate-pulse rounded bg-slate-800" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-slate-800" />
          </div>
        )}
        {!insights.isLoading && (
          <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-slate-500">
            {text}
          </pre>
        )}
      </div>
    </div>
  );
}

// Inline-rendered insight visual — mirrors what the matplotlib figure shows
// (PR-AUC headline + funnel ribbon + summary tiles) so we don't depend on a
// canvas-only PNG that may not be reachable.
function InsightVisual() {
  return (
    <div className="space-y-5">
      <div>
        <div className="text-[10px] uppercase tracking-[0.3em] text-cyan-300">
          ensemble · headline
        </div>
        <div className="mt-2 flex items-baseline gap-3">
          <span className="text-5xl font-black text-slate-100 tabular-nums">0.265</span>
          <span className="text-sm text-slate-500">PR-AUC</span>
          <span className="text-xs font-medium text-emerald-300">14.4× lift vs random</span>
        </div>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
          funnel — strict-nested cohorts
        </div>
        <div className="mt-2 flex items-end gap-1">
          {[
            { label: "New", n: 17467 },
            { label: "Explore", n: 15312 },
            { label: "Created", n: 7131 },
            { label: "AI", n: 7128 },
            { label: "Code", n: 3113 },
            { label: "Connect", n: 1205 },
            { label: "Engage", n: 954 },
            { label: "Pay", n: 323 },
          ].map((s) => (
            <div key={s.label} className="flex-1">
              <div
                className="rounded-t bg-gradient-to-t from-cyan-500 to-blue-600"
                style={{ height: `${Math.max(8, (s.n / 17467) * 80)}px` }}
              />
              <div className="mt-1 truncate text-center text-[8px] text-slate-500 tabular-nums">
                {s.n.toLocaleString()}
              </div>
              <div className="truncate text-center text-[8px] text-slate-400">{s.label}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
        <div className="rounded border border-emerald-400/40 bg-emerald-500/15 p-2">
          <div className="text-lg font-bold text-emerald-300">21/21</div>
          <div className="text-slate-500">leakage checks</div>
        </div>
        <div className="rounded border border-cyan-400/40 bg-cyan-500/15 p-2">
          <div className="text-lg font-bold text-cyan-300">169</div>
          <div className="text-slate-500">features</div>
        </div>
        <div className="rounded border border-blue-400/40 bg-blue-500/15 p-2">
          <div className="text-lg font-bold text-blue-300">1,300</div>
          <div className="text-slate-500">playbook target</div>
        </div>
      </div>
    </div>
  );
}
