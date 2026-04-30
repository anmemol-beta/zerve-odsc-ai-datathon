"use client";

import { useMemo, useState, useEffect } from "react";
import type { UserRow } from "@/lib/types";
import { STAGE_COLORS, STAGE_LABELS } from "@/lib/types";

export default function UserLookup({ users }: { users: UserRow[] }) {
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<UserRow | null>(users[0] ?? null);
  const [filterUpgrader, setFilterUpgrader] = useState(false);

  const filtered = useMemo(() => {
    let pool = users;
    if (filterUpgrader) pool = pool.filter((u) => u.stage === "6_upgraded");
    if (query.length > 0) {
      const q = query.toLowerCase();
      pool = pool.filter((u) => u.id.toLowerCase().includes(q));
    }
    return pool.slice(0, 80);
  }, [users, query, filterUpgrader]);

  // Derived metrics
  const maxAbsShap = useMemo(
    () => (picked ? Math.max(...picked.shap.map((s) => Math.abs(s.shap))) : 1),
    [picked]
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4">
      <div className="glass rounded-2xl p-4 max-h-[640px] overflow-hidden flex flex-col">
        <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">find a user</div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="search person_id…"
          className="w-full bg-slate-900/80 border border-slate-700 rounded-md px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-pink-500"
        />
        <label className="flex items-center gap-2 text-[11px] text-slate-400 mt-2">
          <input
            type="checkbox"
            checked={filterUpgrader}
            onChange={(e) => setFilterUpgrader(e.target.checked)}
            className="accent-pink-500"
          />
          upgraders only
        </label>
        <div className="text-[11px] text-slate-500 mt-1 mb-2">
          showing {filtered.length} of {users.length}
        </div>
        <div className="flex-1 overflow-y-auto space-y-1 pr-1">
          {filtered.map((u) => {
            const active = picked?.id === u.id;
            return (
              <button
                key={u.id}
                onClick={() => setPicked(u)}
                className={`w-full text-left px-2 py-1.5 rounded text-[11px] font-mono transition ${
                  active ? "bg-pink-500/20 border border-pink-500/40" : "hover:bg-slate-700/40 border border-transparent"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: STAGE_COLORS[u.stage] }}
                  />
                  <span className="truncate text-slate-300">{u.id.slice(0, 14)}…</span>
                </div>
                <div className="text-slate-500 mt-0.5 flex justify-between">
                  <span>{STAGE_LABELS[u.stage]}</span>
                  <span>{(u.prob * 100).toFixed(1)}%</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="glass rounded-2xl p-6 min-h-[640px]">
        {picked ? (
          <>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <Metric
                label="funnel stage"
                value={STAGE_LABELS[picked.stage]}
                color={STAGE_COLORS[picked.stage]}
              />
              <Metric
                label="upgrade likelihood"
                value={`${(picked.prob * 100).toFixed(1)}%`}
                color={picked.prob > 0.05 ? "#ec4899" : picked.prob > 0.01 ? "#8b5cf6" : "#475569"}
                glow
              />
              <Metric
                label="signals captured"
                value={`${picked.shap.length}`}
                color="#06b6d4"
              />
            </div>

            <div className="text-xs uppercase tracking-wider text-slate-400 mb-3">
              top SHAP contributions <span className="text-slate-600 font-normal">(why this prediction)</span>
            </div>
            <div className="space-y-2.5">
              {picked.shap.map((s) => {
                const pct = (Math.abs(s.shap) / maxAbsShap) * 50; // half-width bar
                const positive = s.shap > 0;
                return (
                  <div key={s.feature} className="font-mono text-[11px]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-slate-300">
                        {s.feature}
                        <span className="text-slate-600 ml-2">= {s.value}</span>
                      </span>
                      <span className={positive ? "text-pink-400" : "text-cyan-400"}>
                        {positive ? "+" : ""}
                        {s.shap.toFixed(3)}
                      </span>
                    </div>
                    <div className="relative h-2 bg-slate-800/80 rounded-full">
                      <div className="absolute top-0 bottom-0 left-1/2 w-px bg-slate-600" />
                      <div
                        className="absolute top-0 bottom-0 rounded-full transition-all"
                        style={{
                          left: positive ? "50%" : `${50 - pct}%`,
                          width: `${pct}%`,
                          background: positive
                            ? "linear-gradient(90deg, #ec4899, #f43f5e)"
                            : "linear-gradient(90deg, #06b6d4, #0891b2)",
                          boxShadow: `0 0 10px ${positive ? "rgba(236,72,153,0.5)" : "rgba(6,182,212,0.5)"}`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-6 text-[10px] text-slate-500 leading-relaxed">
              SHAP value = log-odds delta this feature contributed to the prediction.
              Pink → pushes upgrade probability up. Cyan → pushes it down. Center line is the model's expected prediction.
            </div>
          </>
        ) : (
          <div className="text-slate-500 text-sm">pick a user from the list →</div>
        )}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  color,
  glow,
}: {
  label: string;
  value: string;
  color: string;
  glow?: boolean;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div
        className="mt-1 text-2xl font-bold"
        style={{ color, textShadow: glow ? `0 0 24px ${color}55` : "none" }}
      >
        {value}
      </div>
    </div>
  );
}
