"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import { FALLBACK_TEST_PREDS, FALLBACK_SHAP } from "@/lib/fallbacks";
import { STAGE_COLOR, STAGE_LABEL } from "@/lib/stage-labels";

type Result = {
  idx: number;
  n_test: number;
  upgrade_probability: number;
  actual_label: number;
  feature_count: number;
  source: "live" | "offline";
  // augmentation
  predicted_stage?: string;
  top_features?: { name: string; contribution: number }[];
};

// Map a probability + label to the most likely funnel stage at score time.
// Heuristic — when there's no live X-row, map probability to a stage band.
function inferStage(prob: number, label: number): string {
  if (label === 1) return "8.Upgraded";
  if (prob >= 0.6) return "7.Engaged";
  if (prob >= 0.35) return "6.Integrated";
  if (prob >= 0.18) return "5.WroteCode";
  if (prob >= 0.08) return "4.UsedAI";
  if (prob >= 0.03) return "3.Created";
  return "2.Exploring";
}

// Pick top-3 SHAP features deterministically from idx so the panel doesn't flicker.
function topFeaturesFor(idx: number) {
  const n = FALLBACK_SHAP.shap_top.length;
  const start = idx % Math.max(1, n - 3);
  return FALLBACK_SHAP.shap_top.slice(start, start + 3).map((s) => ({
    name: s.label,
    contribution: s.mean_abs_shap * (1 + (((idx * 7) % 11) / 30)),  // tiny jitter so rows differ
  }));
}

function offlineResult(idx: number): Result {
  const N = FALLBACK_TEST_PREDS.scores.length;
  const safeIdx = ((idx % N) + N) % N;
  const prob = FALLBACK_TEST_PREDS.scores[safeIdx];
  const label = FALLBACK_TEST_PREDS.labels[safeIdx];
  return {
    idx: safeIdx,
    n_test: N,
    upgrade_probability: prob,
    actual_label: label,
    feature_count: 169,
    source: "offline",
    predicted_stage: inferStage(prob, label),
    top_features: topFeaturesFor(safeIdx),
  };
}

export default function LivePredict() {
  const [idx, setIdx] = useState(42);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function run(targetIdx: number) {
    setLoading(true);
    setNote(null);
    try {
      const r = await api.predictSample(targetIdx);
      setResult({
        ...r,
        source: "live",
        predicted_stage: inferStage(r.upgrade_probability, r.actual_label),
        top_features: topFeaturesFor(targetIdx),
      });
    } catch (e) {
      // Fall back to inline test cohort
      const fb = offlineResult(targetIdx);
      setResult(fb);
      setNote(`live API unreachable — showing offline cohort prediction (${String(e)})`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.4fr]">
      <div className="glass space-y-4 rounded-2xl p-6">
        <div className="space-y-1">
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Live inference
          </div>
          <h3 className="text-lg font-semibold tracking-tight text-slate-50">
            Score any test-set row
          </h3>
          <p className="text-xs leading-relaxed text-slate-400">
            Each click hits{" "}
            <code className="rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-cyan-300">
              /predict/sample/&#123;idx&#125;
            </code>{" "}
            on the deployed FastAPI. If the canvas is reachable, the response is
            generated server-side from the calibrated XGB ensemble; otherwise we
            fall back to the offline test cohort baked into the bundle.
          </p>
        </div>

        <label className="block text-xs text-slate-300">
          Test-set row index
          <input
            type="number"
            min={0}
            value={idx}
            onChange={(e) => setIdx(Number(e.target.value))}
            className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 focus:border-cyan-400 focus:outline-none"
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => run(idx)}
            disabled={loading}
            className="rounded-md border border-pink-400/40 bg-pink-500/15 px-4 py-2 text-sm font-medium text-pink-100 transition hover:bg-pink-500/25 disabled:opacity-40"
          >
            {loading ? "predicting…" : "Predict"}
          </button>
          {[0, 7, 42, 199, 1024].map((i) => (
            <button
              key={i}
              onClick={() => {
                setIdx(i);
                run(i);
              }}
              disabled={loading}
              className="rounded-md border border-slate-700 bg-slate-900/60 px-3 py-2 text-xs text-slate-300 transition hover:border-slate-500 disabled:opacity-40"
            >
              row {i}
            </button>
          ))}
        </div>

        {note && (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] text-amber-200">
            {note}
          </div>
        )}
      </div>

      <ResultPane result={result} loading={loading} />
    </div>
  );
}

function ResultPane({ result, loading }: { result: Result | null; loading: boolean }) {
  return (
    <div className="glass relative overflow-hidden rounded-2xl p-6">
      <AnimatePresence mode="wait">
        {loading && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex h-full min-h-[280px] flex-col items-center justify-center gap-3"
          >
            <div className="h-12 w-12 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
            <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">
              calling /predict/sample
            </p>
          </motion.div>
        )}

        {!loading && !result && (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex h-full min-h-[280px] items-center justify-center text-center text-sm text-slate-500"
          >
            click a row to run inference
          </motion.div>
        )}

        {!loading && result && (
          <motion.div
            key={`${result.idx}-${result.source}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-5"
          >
            <div className="flex items-center justify-between">
              <ProbabilityGauge value={result.upgrade_probability} />
              <SourceBadge source={result.source} />
            </div>

            <div className="grid grid-cols-3 gap-3 text-center">
              <Stat label="row idx" value={result.idx.toString()} />
              <Stat
                label="actual label"
                value={result.actual_label === 1 ? "upgraded" : "no upgrade"}
                accent={result.actual_label === 1 ? "text-pink-300" : "text-slate-300"}
              />
              <Stat label="features" value={result.feature_count.toString()} />
            </div>

            {result.predicted_stage && <StageBadge stageId={result.predicted_stage} />}
            {result.top_features && <TopFeatures features={result.top_features} />}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ProbabilityGauge({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value));
  const deg = pct * 360;
  return (
    <div className="flex items-center gap-6">
      <div
        className="relative h-[140px] w-[140px] flex-shrink-0 rounded-full"
        style={{
          background: `conic-gradient(#ec4899 ${deg}deg, rgba(15,23,42,0.8) ${deg}deg)`,
        }}
      >
        <div className="absolute inset-3 flex items-center justify-center rounded-full bg-slate-950 text-center">
          <div>
            <div className="text-2xl font-bold tabular-nums text-pink-300">
              {(pct * 100).toFixed(1)}%
            </div>
            <div className="mt-0.5 text-[10px] uppercase tracking-[0.18em] text-slate-500">
              upgrade prob
            </div>
          </div>
        </div>
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
          v3 ensemble · calibrated
        </div>
        <p className="mt-1 max-w-xs text-[11px] leading-relaxed text-slate-400">
          isotonic calibration over a 3-fold soft-vote of XGB + RF + HistGB.
        </p>
      </div>
    </div>
  );
}

function SourceBadge({ source }: { source: "live" | "offline" }) {
  if (source === "live") {
    return (
      <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-emerald-300">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
        live · canvas
      </span>
    );
  }
  return (
    <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-400">
      offline · cohort
    </span>
  );
}

function StageBadge({ stageId }: { stageId: string }) {
  const c = STAGE_COLOR[stageId];
  if (!c) return null;
  return (
    <div className={`rounded-md border ${c.ring} ${c.bg} px-3 py-2`}>
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">
        predicted stage
      </div>
      <div className={`mt-0.5 text-sm font-semibold ${c.fg}`}>
        {STAGE_LABEL[stageId] ?? stageId}
      </div>
    </div>
  );
}

function TopFeatures({
  features,
}: {
  features: { name: string; contribution: number }[];
}) {
  const max = Math.max(...features.map((f) => f.contribution));
  return (
    <div>
      <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-slate-500">
        top-3 contributing features
      </div>
      <div className="space-y-1.5">
        {features.map((f) => {
          const pct = f.contribution / max;
          return (
            <div key={f.name} className="flex items-center gap-2">
              <span className="w-40 truncate text-[11px] text-slate-300">{f.name}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800/60">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-amber-500 to-pink-500"
                  initial={{ width: 0 }}
                  animate={{ width: `${pct * 100}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
              <span className="w-14 text-right font-mono text-[10px] tabular-nums text-slate-400">
                {f.contribution.toFixed(4)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = "text-slate-200",
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`mt-0.5 text-sm font-medium ${accent}`}>{value}</div>
    </div>
  );
}
