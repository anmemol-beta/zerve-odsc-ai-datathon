"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ACCENT } from "@/lib/colors";
import { FALLBACK_COMBOS } from "@/lib/fallbacks";
import { fmtNum, fmtPct } from "@/lib/format";

type Flag = {
  key: "is_power_engaged" | "agent_first" | "onboarding_completed";
  label: string;
  detail: string;
};

const FLAGS: Flag[] = [
  { key: "is_power_engaged",     label: "Power-engaged",        detail: "≥7 active days in last 14" },
  { key: "agent_first",          label: "Agent-first usage",    detail: "first session used the AI agent" },
  { key: "onboarding_completed", label: "Onboarding complete",  detail: "finished the product tour" },
];

export default function SignalCombo() {
  const [flags, setFlags] = useState({
    is_power_engaged: true,
    agent_first: true,
    onboarding_completed: true,
  });

  const key = `${flags.is_power_engaged ? 1 : 0}${flags.agent_first ? 1 : 0}${flags.onboarding_completed ? 1 : 0}`;
  const cell = FALLBACK_COMBOS[key];

  // baseline = "000" (none of the flags) for comparison
  const baseline = FALLBACK_COMBOS["000"];
  const lift = cell.rate / baseline.rate;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
      {/* LEFT — flag toggles */}
      <div className={`glass rounded-2xl border p-6 ${ACCENT.violet.border}`}>
        <div className={`font-mono text-[10px] uppercase tracking-[0.3em] ${ACCENT.violet.text}`}>
          Toggle the flags
        </div>
        <h3 className="mt-2 text-base font-semibold text-slate-900">
          Live conditional rate
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-slate-400">
          The combo of three behavioral flags multiplies upgrade probability.
          Each toggle re-keys the lookup table behind the model.
        </p>

        <div className="mt-5 space-y-3">
          {FLAGS.map((f) => (
            <FlagSwitch
              key={f.key}
              flag={f}
              on={flags[f.key]}
              onChange={(v) => setFlags({ ...flags, [f.key]: v })}
            />
          ))}
        </div>

        <div className="mt-5 rounded-md border border-slate-200 bg-slate-50 p-3 font-mono text-[10px] text-slate-400">
          combo key →{" "}
          <span className="text-pink-600">{key}</span>
          <span className="ml-3 text-slate-500">
            (power · agent · onboarding)
          </span>
        </div>
      </div>

      {/* RIGHT — live result panel */}
      <motion.div
        key={key}
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.25 }}
        className={`glass rounded-2xl border p-6 ${ACCENT.pink.border} ${
          lift > 5 ? ACCENT.pink.glow : ""
        }`}
      >
        <div className="grid grid-cols-3 gap-4">
          <Stat label="Users" value={fmtNum(cell.users)} accent="cyan" />
          <Stat label="Upgraders" value={fmtNum(cell.upgraders)} accent="violet" />
          <Stat
            label="Upgrade rate"
            value={fmtPct(cell.rate, 2)}
            accent="pink"
            big
          />
        </div>

        <div className="mt-6">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-slate-500">
            <span>vs all-flags-off baseline ({fmtPct(baseline.rate, 2)})</span>
            <span className={`font-mono ${lift > 5 ? "text-pink-600" : "text-slate-400"}`}>
              {lift.toFixed(1)}× lift
            </span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <motion.div
              key={key}
              className="h-full bg-gradient-to-r from-violet-500 to-pink-500"
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(100, (lift / 60) * 100)}%` }}
              transition={{ duration: 0.6 }}
            />
          </div>
        </div>

        <p className="mt-5 text-xs leading-relaxed text-slate-400">
          {key === "111" && (
            <>
              All three flags = {fmtPct(cell.rate, 1)} upgrade rate, ~6× the average.
              This is the segment the playbook's #1 action targets.
            </>
          )}
          {key === "000" && (
            <>The cold cohort — no flags fired. Rate {fmtPct(cell.rate, 2)}, well below the {fmtPct(0.0184, 2)} site-wide average.</>
          )}
          {key !== "111" && key !== "000" && (
            <>
              {cell.users.toLocaleString()} users in this combo · {lift.toFixed(1)}×
              the all-off baseline. Toggle more flags on to see the multiplier compound.
            </>
          )}
        </p>
      </motion.div>
    </div>
  );
}

function FlagSwitch({
  flag,
  on,
  onChange,
}: {
  flag: Flag;
  on: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!on)}
      className={`group flex w-full items-center justify-between rounded-lg border px-4 py-3 text-left transition ${
        on
          ? "border-pink-200 bg-pink-50"
          : "border-slate-200 bg-slate-50 hover:border-slate-200"
      }`}
    >
      <div>
        <div className={`text-sm font-medium ${on ? "text-pink-100" : "text-slate-300"}`}>
          {flag.label}
        </div>
        <div className="text-[10px] text-slate-500">{flag.detail}</div>
      </div>
      <div
        className={`relative h-5 w-9 rounded-full transition ${
          on ? "bg-pink-500" : "bg-slate-200"
        }`}
      >
        <motion.div
          className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow"
          animate={{ x: on ? 18 : 2 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      </div>
    </button>
  );
}

function Stat({
  label,
  value,
  accent,
  big = false,
}: {
  label: string;
  value: string;
  accent: keyof typeof ACCENT;
  big?: boolean;
}) {
  const c = ACCENT[accent];
  return (
    <div>
      <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div
        className={`tabular-nums font-bold ${c.textStrong} ${
          big ? "text-3xl mt-1" : "text-xl mt-0.5"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
