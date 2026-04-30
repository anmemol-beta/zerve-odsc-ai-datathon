"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { FALLBACK_AUDIT } from "@/lib/fallbacks";

export default function LeakageAudit() {
  const a = FALLBACK_AUDIT;
  const [openCat, setOpenCat] = useState<string | null>(a.categories[0]?.id ?? null);

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
      {/* LEFT — score + obs_days story */}
      <div className="space-y-4">
        <div className={`glass rounded-2xl border p-6 ${ACCENT.emerald.border} ${ACCENT.emerald.glow}`}>
          <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.emerald.text}`}>
            Leakage audit
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className={`text-6xl font-black tabular-nums ${ACCENT.emerald.textStrong}`}>
              {a.passed}
            </span>
            <span className="text-2xl text-slate-500">/</span>
            <span className="text-2xl tabular-nums text-slate-400">{a.total}</span>
          </div>
          <div className="mt-1 text-xs uppercase tracking-[0.18em] text-slate-400">
            checks passed
          </div>
          <p className="mt-4 text-xs leading-relaxed text-slate-400">
            Every guardrail green. The model never sees a feature derived from
            anything inside the 30-day label window — verified mechanically across
            169 features and 25 blacklisted event tokens.
          </p>
        </div>

        <ObsDaysStory story={a.obs_days_story} />
      </div>

      {/* RIGHT — categories accordion */}
      <div className="glass rounded-2xl p-2">
        {a.categories.map((cat, i) => {
          const open = openCat === cat.id;
          const passed = cat.checks.filter((c) => c.pass).length;
          return (
            <motion.div
              key={cat.id}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.35, delay: i * 0.04 }}
              className="border-b border-slate-800/60 last:border-b-0"
            >
              <button
                onClick={() => setOpenCat(open ? null : cat.id)}
                className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-slate-800/30"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[10px] tracking-[0.18em] text-emerald-400">
                    {cat.id}
                  </span>
                  <span className="text-sm font-medium text-slate-200">{cat.title}</span>
                </div>
                <div className="flex items-center gap-2 text-[10px] tabular-nums text-emerald-300">
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5">
                    {passed}/{cat.checks.length}
                  </span>
                  <span className={`transition-transform ${open ? "rotate-90" : ""}`}>›</span>
                </div>
              </button>
              <AnimatePresence>
                {open && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25, ease: "easeOut" }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-2 px-4 pb-4">
                      {cat.checks.map((c, j) => (
                        <div
                          key={j}
                          className="flex items-start gap-3 rounded-md border border-slate-800/60 bg-slate-950/60 p-3"
                        >
                          <span
                            className={`mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full ${
                              c.pass ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"
                            }`}
                          >
                            {c.pass ? "✓" : "✗"}
                          </span>
                          <div className="flex-1">
                            <div className="text-xs text-slate-200">{c.name}</div>
                            <div className="mt-1 font-mono text-[10px] leading-relaxed text-slate-500">
                              {c.detail}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

function ObsDaysStory({
  story,
}: {
  story: { roc_alone: number; n_features_dropped: number; pr_auc_before: number; pr_auc_after: number };
}) {
  return (
    <div className={`glass rounded-2xl border p-6 ${ACCENT.amber.border}`}>
      <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.amber.text}`}>
        ⚠ The obs_days story
      </div>
      <h4 className="mt-2 text-base font-semibold text-slate-100">
        ROC 0.939 from one feature alone — that's the smell
      </h4>
      <div className="mt-4 grid grid-cols-3 gap-3 text-center">
        <Tile label="ROC alone" value={story.roc_alone.toFixed(3)} accent="amber" />
        <Tile
          label="Before"
          value={story.pr_auc_before.toFixed(3)}
          detail="PR-AUC w/ leak"
          accent="rose"
        />
        <Tile
          label="After"
          value={story.pr_auc_after.toFixed(3)}
          detail={`–${story.n_features_dropped} features`}
          accent="emerald"
        />
      </div>
      <p className="mt-4 text-xs leading-relaxed text-slate-400">
        We caught a feature whose <em>length</em> depended on the cutoff date — a
        textbook target leak. Dropping it (and {story.n_features_dropped - 1} other
        cutoff-correlated features) cost us 10pp PR-AUC, but the remaining
        {" "}{story.pr_auc_after.toFixed(3)} is honest. Better an honest 0.265 than a
        fantasy 0.37.
      </p>
    </div>
  );
}

function Tile({
  label,
  value,
  detail,
  accent,
}: {
  label: string;
  value: string;
  detail?: string;
  accent: "amber" | "rose" | "emerald";
}) {
  const c = ACCENT[accent];
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${c.text}`}>{value}</div>
      {detail && <div className="mt-0.5 text-[9px] text-slate-500">{detail}</div>}
    </div>
  );
}
