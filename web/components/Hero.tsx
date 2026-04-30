"use client";

import { motion } from "framer-motion";

const headline1 = "User funnel".split("");
const headline2 = "& upgrade".split("");
const headline3 = "predictor".split("");

function Letters({ chars, delay = 0, gradient = false }: { chars: string[]; delay?: number; gradient?: boolean }) {
  return (
    <span className={gradient ? "gradient-text" : "text-slate-100"}>
      {chars.map((c, i) => (
        <motion.span
          key={i}
          initial={{ y: 80, opacity: 0, rotateX: -50 }}
          animate={{ y: 0, opacity: 1, rotateX: 0 }}
          transition={{
            duration: 0.7,
            delay: delay + i * 0.025,
            ease: [0.22, 1, 0.36, 1],
          }}
          style={{ display: "inline-block" }}
        >
          {c === " " ? " " : c}
        </motion.span>
      ))}
    </span>
  );
}

export default function Hero() {
  return (
    <header className="relative pt-20 pb-10">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-[10px] uppercase tracking-[0.4em] text-slate-400 mb-6 font-mono flex items-center gap-3"
      >
        <span className="w-8 h-px bg-gradient-to-r from-transparent to-pink-400" />
        ODSC × Zerve AI Datathon · April 2026
        <span className="w-8 h-px bg-gradient-to-r from-pink-400 to-transparent" />
      </motion.div>

      <h1 className="text-6xl md:text-8xl font-black leading-[0.92] tracking-[-0.04em]">
        <span className="block"><Letters chars={headline1} delay={0.05} gradient /></span>
        <span className="block"><Letters chars={headline2} delay={0.45} /></span>
        <span className="block"><Letters chars={headline3} delay={0.85} /></span>
      </h1>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 1.4 }}
        className="mt-10 flex flex-col md:flex-row md:items-end gap-6 md:gap-12"
      >
        <p className="text-slate-300 max-w-xl text-base leading-relaxed">
          A leakage-safe upgrade-prediction model and a strict-nested 9-stage funnel,
          built end-to-end in <span className="text-slate-100 font-medium">Zerve</span>.
          Score any user, audit the leakage guardrails, retune the funnel rules — every
          prediction is <span className="gradient-text font-semibold">explainable</span>.
        </p>
        <div className="flex items-center gap-2 text-xs font-mono text-slate-500 shrink-0">
          <span>3.5M events</span>
          <span className="text-slate-500">·</span>
          <span>17,541 users</span>
          <span className="text-slate-500">·</span>
          <span>228 days</span>
        </div>
      </motion.div>
    </header>
  );
}
