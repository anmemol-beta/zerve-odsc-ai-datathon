"use client";

import { useQuery } from "@tanstack/react-query";
import { api, API_BASE } from "@/lib/api";

export default function HealthBadge() {
  const q = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });
  const ok = q.isSuccess && q.data.ok;
  const dotColor = q.isLoading
    ? "bg-slate-500"
    : ok
      ? "bg-emerald-400"
      : "bg-rose-400";
  const label = q.isLoading ? "pinging…" : ok ? "live" : "offline";
  const host = API_BASE.replace(/^https?:\/\//, "") || "same-origin";
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 font-mono text-[10px] text-slate-300 backdrop-blur">
      <span className={`h-1.5 w-1.5 animate-pulse rounded-full ${dotColor}`} />
      {label}
      <span className="text-slate-600">·</span>
      <span className="text-slate-400">{host}</span>
    </div>
  );
}
