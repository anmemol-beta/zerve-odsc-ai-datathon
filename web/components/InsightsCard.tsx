"use client";

import { useQuery } from "@tanstack/react-query";
import { api, figureUrl } from "@/lib/api";

export default function InsightsCard() {
  const insights = useQuery({
    queryKey: ["insights"],
    queryFn: api.insights,
  });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]">
      <div className="glass overflow-hidden rounded-2xl">
        <div className="border-b border-slate-800 bg-slate-950/50 px-5 py-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-pink-400">
            // insights card · live
          </span>
        </div>
        <div className="bg-slate-100">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={figureUrl("Insights Card")}
            alt="insights card figure"
            className="block w-full"
          />
        </div>
      </div>

      <div className="glass space-y-3 rounded-2xl p-6">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          insights_card_text
        </span>
        {insights.isLoading && (
          <div className="space-y-2">
            <div className="h-3 animate-pulse rounded bg-slate-800" />
            <div className="h-3 w-5/6 animate-pulse rounded bg-slate-800" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-slate-800" />
          </div>
        )}
        {insights.isError && (
          <div className="text-xs text-rose-300">
            could not load /insights — {String(insights.error)}
          </div>
        )}
        {insights.isSuccess && (
          <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-slate-300">
            {insights.data.text}
          </pre>
        )}
      </div>
    </div>
  );
}
