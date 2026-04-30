"use client";

import { useMemo, useState } from "react";
import type {
  StrategiesIndex,
  StrategySegmentEntry,
  StrategyAction,
  StrategyChannel,
} from "@/lib/types";

const CHANNEL_META: Record<StrategyChannel, { label: string; color: string }> = {
  email:              { label: "email",              color: "#06b6d4" },
  in_app_modal:       { label: "in-app modal",       color: "#ec4899" },
  sales_call:         { label: "sales call",         color: "#f43f5e" },
  push_notification:  { label: "push notification",  color: "#a855f7" },
  ad_retargeting:     { label: "ad retargeting",     color: "#f59e0b" },
  lifecycle_drip:     { label: "lifecycle drip",     color: "#10b981" },
};

function fmtUsd(x: number) {
  return x < 1 ? `$${x.toFixed(2)}` : `$${x.toFixed(2)}`;
}

function fmtPct(x: number, digits = 1) {
  return `${(x * 100).toFixed(digits)}%`;
}

export default function ActionCards({ data }: { data: StrategiesIndex }) {
  const segments = data.segments;
  const [pickedId, setPickedId] = useState<string>(segments[0]?.segment_id ?? "");
  const [lang, setLang] = useState<"en" | "ko">("en");

  const picked = useMemo(
    () => segments.find((s) => s.segment_id === pickedId) ?? segments[0],
    [segments, pickedId]
  );

  if (!picked) {
    return <div className="text-slate-500 text-sm">no strategies loaded</div>;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
      <SegmentList
        segments={segments}
        pickedId={picked.segment_id}
        onPick={setPickedId}
      />
      <div className="glass rounded-2xl p-6 min-h-[720px]">
        <SegmentHeader seg={picked} />
        <Summary text={picked.strategy.summary} />
        <div className="flex items-center justify-between mt-6 mb-3">
          <div className="text-xs uppercase tracking-wider text-slate-400">
            recommended actions{" "}
            <span className="text-slate-600 font-normal">
              (K2-Think, ranked by ROI)
            </span>
          </div>
          <LangToggle lang={lang} onChange={setLang} />
        </div>
        <div className="space-y-3">
          {picked.strategy.actions.map((a) => (
            <ActionCard key={a.rank} action={a} lang={lang} />
          ))}
        </div>
        <div className="mt-6 text-xs uppercase tracking-wider text-slate-400 mb-2">
          risks{" "}
          <span className="text-slate-600 font-normal normal-case">
            (what could go wrong)
          </span>
        </div>
        <ul className="space-y-1.5">
          {picked.strategy.risks.map((r, i) => (
            <li
              key={i}
              className="text-[12px] text-slate-400 leading-relaxed flex gap-2"
            >
              <span className="text-amber-400 shrink-0">⚠</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
        <div className="mt-6 pt-4 border-t border-slate-800/60 text-[10px] text-slate-500">
          generated {new Date(data.generated_at).toLocaleString()} · model{" "}
          <span className="font-mono">{data.model}</span>
        </div>
      </div>
    </div>
  );
}

function SegmentList({
  segments,
  pickedId,
  onPick,
}: {
  segments: StrategySegmentEntry[];
  pickedId: string;
  onPick: (id: string) => void;
}) {
  return (
    <div className="glass rounded-2xl p-4 max-h-[720px] overflow-hidden flex flex-col">
      <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">
        segment
      </div>
      <div className="text-[10px] text-slate-500 mb-2">
        {segments.length} segments · sorted by funnel stage
      </div>
      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        {segments.map((s) => {
          const active = s.segment_id === pickedId;
          const lift = s.stats.baseline_lift;
          const isAtRisk = s.label.startsWith("9.");
          const isUpgraded = s.label.includes("Upgraded") && !isAtRisk;
          const dotColor = isUpgraded
            ? "#ec4899"
            : isAtRisk
            ? "#f59e0b"
            : "#3b82f6";
          return (
            <button
              key={s.segment_id}
              onClick={() => onPick(s.segment_id)}
              className={`w-full text-left px-2.5 py-2 rounded text-[11px] transition ${
                active
                  ? "bg-pink-500/20 border border-pink-500/40"
                  : "hover:bg-slate-700/40 border border-transparent"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: dotColor }}
                />
                <span className="truncate text-slate-200 font-medium">
                  {s.label}
                </span>
              </div>
              <div className="text-slate-500 mt-1 flex justify-between font-mono">
                <span>{s.stats.size.toLocaleString()} u</span>
                <span
                  className={
                    lift >= 1.5
                      ? "text-pink-400"
                      : lift >= 0.5
                      ? "text-slate-400"
                      : "text-slate-600"
                  }
                >
                  {lift.toFixed(2)}× lift
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SegmentHeader({ seg }: { seg: StrategySegmentEntry }) {
  const s = seg.stats;
  return (
    <div className="grid grid-cols-4 gap-4 mb-5">
      <Metric
        label="segment"
        value={seg.label}
        color="#e2e8f0"
        small
      />
      <Metric
        label="size"
        value={`${s.size.toLocaleString()}`}
        sub={`${s.pct_of_total.toFixed(1)}% of all`}
        color="#06b6d4"
      />
      <Metric
        label="observed upgrade"
        value={fmtPct(s.observed_rate, 2)}
        sub={`baseline ${fmtPct(s.baseline_rate, 2)}`}
        color={s.baseline_lift >= 1.0 ? "#ec4899" : "#475569"}
        glow={s.baseline_lift >= 1.5}
      />
      <Metric
        label="model score (median)"
        value={s.score.median.toFixed(3)}
        sub={`p90 ${s.score.p90.toFixed(3)}`}
        color="#a855f7"
      />
    </div>
  );
}

function Summary({ text }: { text: string }) {
  return (
    <div className="text-[13px] text-slate-300 leading-relaxed border-l-2 border-pink-500/40 pl-3">
      {text}
    </div>
  );
}

function LangToggle({
  lang,
  onChange,
}: {
  lang: "en" | "ko";
  onChange: (l: "en" | "ko") => void;
}) {
  return (
    <div className="flex text-[10px] font-mono rounded-md overflow-hidden border border-slate-700">
      {(["en", "ko"] as const).map((l) => (
        <button
          key={l}
          onClick={() => onChange(l)}
          className={`px-2 py-1 transition ${
            lang === l
              ? "bg-pink-500/20 text-pink-300"
              : "bg-slate-900/60 text-slate-500 hover:text-slate-300"
          }`}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

function ActionCard({
  action,
  lang,
}: {
  action: StrategyAction;
  lang: "en" | "ko";
}) {
  const meta = CHANNEL_META[action.channel];
  const message = lang === "en" ? action.message_en : action.message_ko;
  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/40 p-4 hover:border-slate-700 transition">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="shrink-0 w-7 h-7 rounded-md flex items-center justify-center text-[11px] font-bold"
            style={{
              background: `${meta.color}22`,
              color: meta.color,
              border: `1px solid ${meta.color}55`,
            }}
          >
            #{action.rank}
          </span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-100 truncate">
              {action.title}
            </div>
            <div className="text-[10px] uppercase tracking-wider mt-0.5">
              <span style={{ color: meta.color }}>{meta.label}</span>
            </div>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            ROI
          </div>
          <div
            className="text-base font-bold"
            style={{
              color:
                action.estimated_roi_multiple >= 5
                  ? "#ec4899"
                  : action.estimated_roi_multiple >= 1
                  ? "#a855f7"
                  : "#475569",
            }}
          >
            {action.estimated_roi_multiple.toFixed(1)}×
          </div>
        </div>
      </div>

      <div className="mt-2 rounded-md bg-slate-950/60 border border-slate-800/60 p-3 text-[12px] text-slate-200 leading-relaxed">
        {message}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-3 text-[11px]">
        <Stat
          label="expected uplift"
          value={`+${action.expected_uplift_pp.toFixed(2)} pp`}
          color="#10b981"
        />
        <Stat
          label="cost / user"
          value={fmtUsd(action.estimated_cost_per_user_usd)}
          color="#06b6d4"
        />
        <Stat
          label="ROI multiple"
          value={`${action.estimated_roi_multiple.toFixed(1)}×`}
          color="#ec4899"
        />
      </div>

      <details className="mt-3 group">
        <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-slate-500 hover:text-slate-300 select-none">
          target filter · rationale · playbook ↓
        </summary>
        <div className="mt-2 space-y-2">
          <Block label="target filter (SQL-ish)">
            <code className="block font-mono text-[11px] text-cyan-300 whitespace-pre-wrap break-words">
              {action.target_filter}
            </code>
          </Block>
          <Block label="rationale">
            <div className="text-[12px] text-slate-300 leading-relaxed">
              {action.rationale}
            </div>
          </Block>
          <Block label="playbook alignment">
            <div className="text-[12px] text-slate-300 leading-relaxed">
              {action.playbook_alignment}
            </div>
          </Block>
        </div>
      </details>
    </div>
  );
}

function Block({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">
        {label}
      </div>
      <div className="rounded-md bg-slate-950/60 border border-slate-800/60 p-2.5">
        {children}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500">
        {label}
      </div>
      <div className="font-mono font-semibold mt-0.5" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  sub,
  color,
  glow,
  small,
}: {
  label: string;
  value: string;
  sub?: string;
  color: string;
  glow?: boolean;
  small?: boolean;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500">
        {label}
      </div>
      <div
        className={`mt-1 font-bold ${small ? "text-base" : "text-2xl"}`}
        style={{
          color,
          textShadow: glow ? `0 0 24px ${color}55` : "none",
        }}
      >
        {value}
      </div>
      {sub && (
        <div className="text-[10px] text-slate-500 mt-0.5 font-mono">{sub}</div>
      )}
    </div>
  );
}
