"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { FALLBACK_TEST_PREDS } from "@/lib/fallbacks";
import { fmtNum, fmtPct, fmtUSD } from "@/lib/format";

const COST_PER_TOUCH = 1.20;       // $ — assumed marketing cost per user touched
const VALUE_PER_UPGRADE = 240;     // $ — assumed first-year revenue per upgrade

export default function TopKSimulator() {
  const { scores, labels, base_rate } = FALLBACK_TEST_PREDS;
  const N = scores.length;
  const totalPositives = labels.reduce((a, b) => a + b, 0);

  const [k, setK] = useState(5);  // top-k% slider, default 5%

  // Sort indices by score desc once.
  const order = useMemo(() => {
    return Array.from({ length: N }, (_, i) => i).sort((a, b) => scores[b] - scores[a]);
  }, [N, scores]);

  // For each k%, compute precision / recall.
  const topK = Math.max(1, Math.round((k / 100) * N));
  const headHits = useMemo(() => {
    let hits = 0;
    for (let i = 0; i < topK; i++) hits += labels[order[i]];
    return hits;
  }, [topK, order, labels]);

  const precision = headHits / topK;
  const recall = headHits / Math.max(1, totalPositives);
  const lift = precision / base_rate;

  const cost = topK * COST_PER_TOUCH;
  const revenue = headHits * VALUE_PER_UPGRADE;
  const roi = (revenue - cost) / Math.max(1, cost);
  const netGain = revenue - cost;

  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
      {/* LEFT — slider + curve */}
      <div className={`glass rounded-2xl border p-6 ${ACCENT.pink.border} ${ACCENT.pink.glow}`}>
        <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.pink.text}`}>
          Top-K simulator ★
        </div>
        <h3 className="mt-2 text-lg font-semibold text-slate-100">
          If we target top {k.toFixed(1)}% by score…
        </h3>

        <div className="mt-5">
          <input
            type="range"
            min={0.5}
            max={50}
            step={0.5}
            value={k}
            onChange={(e) => setK(Number(e.target.value))}
            className="w-full accent-blue-400"
            aria-label="Top-K percent"
          />
          <div className="mt-1 flex justify-between text-[10px] font-mono text-slate-500">
            <span>0.5%</span>
            <span>10%</span>
            <span>25%</span>
            <span>50%</span>
          </div>
        </div>

        <PrecisionRecallCurve
          order={order}
          labels={labels}
          base_rate={base_rate}
          k={k}
          totalPositives={totalPositives}
        />
      </div>

      {/* RIGHT — KPI panel */}
      <div className="space-y-3">
        <KPI
          label="Users touched"
          value={fmtNum(topK)}
          detail={`top ${k.toFixed(1)}% of ${fmtNum(N)}`}
          accent="cyan"
        />
        <KPI
          label="Upgrades captured"
          value={fmtNum(headHits)}
          detail={`recall ${fmtPct(recall, 0)} of ${totalPositives} positives`}
          accent="violet"
        />
        <KPI
          label="Precision"
          value={fmtPct(precision, 1)}
          detail={`${lift.toFixed(1)}× over ${fmtPct(base_rate, 2)} baseline`}
          accent="pink"
          glow
        />
        <KPI
          label="Net gain"
          value={fmtUSD(netGain)}
          detail={`revenue ${fmtUSD(revenue)} – cost ${fmtUSD(cost)} · ROI ${roi.toFixed(1)}×`}
          accent={netGain > 0 ? "emerald" : "rose"}
        />

        <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-[11px] leading-relaxed text-slate-500">
          <strong className="text-slate-300">Assumptions:</strong>{" "}
          {fmtUSD(COST_PER_TOUCH)} per user touched (modal+email blend),{" "}
          {fmtUSD(VALUE_PER_UPGRADE)} first-year revenue per upgrade. Tune in code; the
          curve is exact for the synthetic test cohort.
        </div>
      </div>
    </div>
  );
}

const W = 460;
const H = 220;
const PAD = { top: 14, right: 14, bottom: 28, left: 36 };

function PrecisionRecallCurve({
  order,
  labels,
  base_rate,
  k,
  totalPositives,
}: {
  order: number[];
  labels: number[];
  base_rate: number;
  k: number;
  totalPositives: number;
}) {
  // Sample 60 points along k=0..50% for the curve.
  const points = useMemo(() => {
    const N = order.length;
    const out: { k: number; precision: number; lift: number }[] = [];
    let hits = 0;
    let nextSampleAt = 0;
    const samples = new Set(
      Array.from({ length: 60 }, (_, j) =>
        Math.max(1, Math.round((j / 60) * N * 0.5)),
      ),
    );
    for (let i = 0; i < N; i++) {
      hits += labels[order[i]];
      if (samples.has(i + 1)) {
        const topK = i + 1;
        out.push({
          k: (topK / N) * 100,
          precision: hits / topK,
          lift: hits / topK / base_rate,
        });
      }
      nextSampleAt = i;
    }
    void totalPositives;
    void nextSampleAt;
    return out;
  }, [order, labels, base_rate, totalPositives]);

  const x = (kPct: number) => PAD.left + (kPct / 50) * (W - PAD.left - PAD.right);
  const y = (p: number) => H - PAD.bottom - (p / 0.5) * (H - PAD.top - PAD.bottom);

  const path = points
    .map((d, i) => `${i === 0 ? "M" : "L"} ${x(d.k)} ${y(d.precision)}`)
    .join(" ");

  // Baseline horizontal line + current marker.
  const currentIdx = points.findIndex((d) => d.k >= k);
  const current = currentIdx === -1 ? points[points.length - 1] : points[currentIdx];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-5 w-full">
      <line x1={PAD.left} x2={W - PAD.right} y1={H - PAD.bottom} y2={H - PAD.bottom} stroke="#334155" />
      <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={H - PAD.bottom} stroke="#334155" />

      {/* baseline */}
      <line
        x1={PAD.left}
        x2={W - PAD.right}
        y1={y(base_rate)}
        y2={y(base_rate)}
        stroke="#475569"
        strokeDasharray="3 3"
      />
      <text x={W - PAD.right} y={y(base_rate) - 4} fontSize={9} fill="#64748b" textAnchor="end">
        baseline {fmtPct(base_rate, 2)}
      </text>

      <motion.path
        d={path}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={2}
        initial={{ pathLength: 0 }}
        whileInView={{ pathLength: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.9, ease: "easeOut" }}
      />

      {/* current marker */}
      <line
        x1={x(current.k)}
        x2={x(current.k)}
        y1={PAD.top}
        y2={H - PAD.bottom}
        stroke="#3b82f6"
        strokeOpacity={0.4}
      />
      <circle cx={x(current.k)} cy={y(current.precision)} r={5} fill="#3b82f6" />

      {/* axis labels */}
      <text x={W / 2} y={H - 6} fontSize={10} fill="#64748b" textAnchor="middle">
        top-k % of users →
      </text>
      <text x={-H / 2} y={12} fontSize={10} fill="#64748b" textAnchor="middle" transform="rotate(-90)">
        precision →
      </text>
      {[0, 10, 25, 50].map((t) => (
        <text key={t} x={x(t)} y={H - PAD.bottom + 14} fontSize={9} fill="#94a3b8" textAnchor="middle">
          {t}%
        </text>
      ))}
      {[0, 0.1, 0.25, 0.5].map((t) => (
        <text key={t} x={PAD.left - 6} y={y(t) + 3} fontSize={9} fill="#94a3b8" textAnchor="end">
          {fmtPct(t, 0)}
        </text>
      ))}
    </svg>
  );
}

function KPI({
  label,
  value,
  detail,
  accent,
  glow = false,
}: {
  label: string;
  value: string;
  detail: string;
  accent: keyof typeof ACCENT;
  glow?: boolean;
}) {
  const c = ACCENT[accent];
  return (
    <div className={`glass rounded-xl border p-4 ${c.border} ${glow ? c.glow : ""}`}>
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold tabular-nums ${c.textStrong}`}>{value}</div>
      <div className="mt-1 text-[10px] text-slate-500">{detail}</div>
    </div>
  );
}
