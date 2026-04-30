"use client";

import { motion } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { STAGE_LABEL } from "@/lib/stage-labels";
import { FALLBACK_TRANSITIONS } from "@/lib/fallbacks";

const CELL = 56;
const PAD = { top: 88, left: 140 };

export default function TransitionHeatmap() {
  const t = FALLBACK_TRANSITIONS;
  const W = PAD.left + t.cols.length * CELL + 16;
  const H = PAD.top + t.rows.length * CELL + 16;
  const highlights = new Set(t.highlight.map((h) => `${h.from}>>${h.to}`));

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <div className={`glass rounded-2xl border p-4 ${ACCENT.cyan.border}`}>
        <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.cyan.text}`}>
          Stage-to-stage transition probabilities
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img">
          {/* col headers */}
          {t.cols.map((c, j) => (
            <g key={`ch-${j}`}>
              <text
                x={PAD.left + j * CELL + CELL / 2}
                y={PAD.top - 16}
                fontSize={9}
                fill="#94a3b8"
                textAnchor="end"
                transform={`rotate(-40 ${PAD.left + j * CELL + CELL / 2} ${PAD.top - 16})`}
                className="font-mono"
              >
                {STAGE_LABEL[c] ?? c}
              </text>
            </g>
          ))}
          {/* row labels */}
          {t.rows.map((r, i) => (
            <text
              key={`rh-${i}`}
              x={PAD.left - 8}
              y={PAD.top + i * CELL + CELL / 2 + 3}
              fontSize={10}
              fill="#94a3b8"
              textAnchor="end"
              className="font-mono"
            >
              {STAGE_LABEL[r] ?? r}
            </text>
          ))}
          {/* cells */}
          {t.matrix.map((row, i) =>
            row.map((p, j) => {
              const key = `${t.rows[i]}>>${t.cols[j]}`;
              const isHi = highlights.has(key);
              const isDiag = i === j;
              const bg = isDiag
                ? `rgba(100,116,139, ${0.15 + p * 0.4})`
                : `rgba(34, 211, 238, ${Math.min(0.85, p * 1.6)})`;
              return (
                <motion.g
                  key={key}
                  initial={{ opacity: 0, scale: 0.6 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.3, delay: (i + j) * 0.015 }}
                >
                  <rect
                    x={PAD.left + j * CELL + 1}
                    y={PAD.top + i * CELL + 1}
                    width={CELL - 2}
                    height={CELL - 2}
                    fill={bg}
                    rx={4}
                    stroke={isHi ? "#3b82f6" : "transparent"}
                    strokeWidth={isHi ? 2 : 0}
                  />
                  {p > 0.02 && (
                    <text
                      x={PAD.left + j * CELL + CELL / 2}
                      y={PAD.top + i * CELL + CELL / 2 + 3}
                      fontSize={10}
                      fill={p > 0.4 ? "#0f172a" : "#e2e8f0"}
                      textAnchor="middle"
                      className="font-mono tabular-nums"
                    >
                      {(p * 100).toFixed(p < 0.1 ? 1 : 0)}
                    </text>
                  )}
                </motion.g>
              );
            }),
          )}
        </svg>
      </div>

      <div className="space-y-3">
        {t.highlight.map((h) => (
          <div
            key={`${h.from}>>${h.to}`}
            className={`glass rounded-xl border p-4 ${ACCENT.pink.border}`}
          >
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-blue-300">
              {STAGE_LABEL[h.from]} → {STAGE_LABEL[h.to]}
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-300">{h.note}</p>
          </div>
        ))}
        <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4 text-[11px] leading-relaxed text-slate-500">
          Cells are row-stochastic — each row sums to ~100%. Diagonals (slate)
          show stay-in-stage probability; off-diagonals (cyan) show advance.
          Pink-bordered cells are the high-leverage transitions.
        </div>
      </div>
    </div>
  );
}
