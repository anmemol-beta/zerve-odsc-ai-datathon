"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, figureUrl } from "@/lib/api";
import { FALLBACK_INSIGHTS_TEXT } from "@/lib/fallbacks";

export default function InsightsCard() {
  const insights = useQuery({
    queryKey: ["insights"],
    queryFn: api.insights,
    retry: 1,
  });
  const [imgFailed, setImgFailed] = useState(false);

  const text =
    (insights.data as { text?: string } | undefined)?.text ?? FALLBACK_INSIGHTS_TEXT;
  const usingFallback = !insights.isSuccess;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]">
      <div className="glass overflow-hidden rounded-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/50 px-5 py-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-pink-400">
            // insights card · live figure
          </span>
          {imgFailed && (
            <span className="text-[10px] text-amber-400">
              figure unavailable — canvas not reachable
            </span>
          )}
        </div>
        <div className={imgFailed ? "p-6" : "bg-slate-100"}>
          {imgFailed ? (
            <FallbackInsightVisual />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={figureUrl("Insights Card")}
              alt="insights card figure"
              className="block w-full"
              onError={() => setImgFailed(true)}
            />
          )}
        </div>
      </div>

      <div className="glass space-y-3 rounded-2xl p-6">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            insights_card_text
          </span>
          {usingFallback && (
            <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2 py-0.5 text-[9px] uppercase tracking-[0.18em] text-slate-400">
              offline
            </span>
          )}
        </div>
        {insights.isLoading && (
          <div className="space-y-2">
            <div className="h-3 animate-pulse rounded bg-slate-800" />
            <div className="h-3 w-5/6 animate-pulse rounded bg-slate-800" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-slate-800" />
          </div>
        )}
        {!insights.isLoading && (
          <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-slate-300">
            {text}
          </pre>
        )}
      </div>
    </div>
  );
}

// Inline-rendered substitute when /figure/Insights Card 404s.
// Mirrors what the matplotlib figure shows: PR-AUC headline + funnel ribbon.
function FallbackInsightVisual() {
  return (
    <div className="space-y-5 rounded-xl bg-slate-950/40 p-5">
      <div>
        <div className="text-[10px] uppercase tracking-[0.3em] text-pink-400">
          v3 ensemble · headline
        </div>
        <div className="mt-2 flex items-baseline gap-3">
          <span className="text-5xl font-black text-pink-300 tabular-nums">0.265</span>
          <span className="text-sm text-slate-400">PR-AUC</span>
          <span className="text-xs text-emerald-300">14.4× lift vs random</span>
        </div>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
          funnel — strict-nested cohorts
        </div>
        <div className="mt-2 flex items-end gap-1">
          {[17541, 13377, 7175, 4760, 2590, 1452, 557, 323].map((n, i) => (
            <div key={i} className="flex-1">
              <div
                className="rounded-t bg-gradient-to-t from-violet-500 to-pink-500"
                style={{ height: `${Math.max(8, (n / 17541) * 80)}px` }}
              />
              <div className="mt-1 truncate text-center text-[8px] text-slate-500 tabular-nums">
                {n.toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
        <div className="rounded border border-emerald-500/40 bg-emerald-500/10 p-2">
          <div className="text-lg font-bold text-emerald-300">21/21</div>
          <div className="text-slate-500">leakage checks</div>
        </div>
        <div className="rounded border border-cyan-500/40 bg-cyan-500/10 p-2">
          <div className="text-lg font-bold text-cyan-300">169</div>
          <div className="text-slate-500">features</div>
        </div>
        <div className="rounded border border-pink-500/40 bg-pink-500/10 p-2">
          <div className="text-lg font-bold text-pink-300">1,300</div>
          <div className="text-slate-500">playbook target</div>
        </div>
      </div>
    </div>
  );
}
