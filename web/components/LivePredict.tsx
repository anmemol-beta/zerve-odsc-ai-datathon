"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";

type Result = Awaited<ReturnType<typeof api.predictSample>>;

export default function LivePredict() {
  const [idx, setIdx] = useState(42);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(targetIdx: number) {
    setLoading(true);
    setError(null);
    try {
      const r = await api.predictSample(targetIdx);
      setResult(r);
    } catch (e) {
      setError(String(e));
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
            Hit the v3 ensemble in real time
          </h3>
          <p className="text-xs leading-relaxed text-slate-400">
            Each click goes to the deployed FastAPI on{" "}
            <code className="rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-cyan-300">
              churn-api.zerve.app
            </code>
            , which calls{" "}
            <code className="rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-pink-300">
              zerve.variable(&quot;Train Model v3&quot;, ...)
            </code>{" "}
            on the live canvas — same calibrated XGB ensemble you see in the DAG above.
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

        {error && (
          <div className="rounded-md border border-rose-500/40 bg-rose-500/10 p-3 text-[11px] text-rose-200">
            <strong>fetch failed</strong> — {error}
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
            click a row to run live inference
          </motion.div>
        )}

        {!loading && result && (
          <motion.div
            key={result.idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-5"
          >
            <ProbabilityGauge value={result.upgrade_probability} />
            <div className="grid grid-cols-3 gap-3 text-center">
              <Stat label="row idx" value={result.idx.toString()} />
              <Stat
                label="actual label"
                value={result.actual_label === 1 ? "upgraded" : "no upgrade"}
                accent={result.actual_label === 1 ? "text-pink-300" : "text-slate-300"}
              />
              <Stat label="features" value={result.feature_count.toString()} />
            </div>
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
        className="relative h-[160px] w-[160px] flex-shrink-0 rounded-full"
        style={{
          background: `conic-gradient(#ec4899 ${deg}deg, rgba(15,23,42,0.8) ${deg}deg)`,
        }}
      >
        <div className="absolute inset-3 flex items-center justify-center rounded-full bg-slate-950 text-center">
          <div>
            <div className="text-3xl font-bold tabular-nums text-pink-300">
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
        <p className="mt-1 max-w-xs text-xs leading-relaxed text-slate-400">
          isotonic calibration over a 3-fold soft-vote of XGBoost, RandomForest,
          and HistGB. Probability is the mean of{" "}
          <code className="rounded bg-slate-900 px-1 py-0.5 text-[10px] text-cyan-300">
            predict_proba
          </code>{" "}
          across folds.
        </p>
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
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">
        {label}
      </div>
      <div className={`mt-0.5 text-sm font-medium ${accent}`}>{value}</div>
    </div>
  );
}
