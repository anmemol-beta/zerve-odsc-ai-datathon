"use client";

import type { Headline } from "@/lib/types";

const fmt = (n: number) => n.toLocaleString();

export default function HeadlineCards({ data }: { data: Headline }) {
  const cards = [
    {
      label: "users",
      value: fmt(data.n_users),
      sub: `${fmt(data.n_events)} events · ${data.n_event_types} types`,
      accent: "from-violet-500/20 to-cyan-500/20",
    },
    {
      label: "reached engaged",
      value: fmt(data.n_engaged),
      sub: `${((data.n_engaged / data.n_users) * 100).toFixed(1)}% of all users`,
      accent: "from-emerald-500/25 to-emerald-500/10",
    },
    {
      label: "upgraded",
      value: fmt(data.n_upgraded),
      sub: `${(data.base_upgrade_rate * 100).toFixed(2)}% base rate · ~53:1 imbalance`,
      accent: "from-pink-500/25 to-pink-500/10",
    },
    {
      label: "at risk",
      value: fmt(data.n_at_risk),
      sub: `${((data.n_at_risk / data.n_engaged) * 100).toFixed(0)}% of engaged · idle 14d+`,
      accent: "from-amber-500/25 to-amber-500/10",
      warn: true,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div
          key={c.label}
          className={`glass rounded-2xl p-5 relative overflow-hidden`}
        >
          <div className={`absolute inset-0 bg-gradient-to-br ${c.accent} opacity-50 pointer-events-none`} />
          <div className="relative">
            <div className="text-xs uppercase tracking-wider text-slate-400">{c.label}</div>
            <div className={`mt-1 text-3xl font-bold ${c.warn ? "text-amber-300" : "text-slate-50"}`}>
              {c.value}
            </div>
            <div className="mt-1 text-xs text-slate-400">{c.sub}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
