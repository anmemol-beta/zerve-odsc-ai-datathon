"use client";

import { motion } from "framer-motion";

export default function Section({
  kicker,
  title,
  subtitle,
  children,
}: {
  kicker: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-120px" }}
      transition={{ duration: 0.6, ease: "easeOut" }}
    >
      <div className="flex items-baseline gap-3 mb-1.5">
        <span className="font-mono text-[10px] text-pink-400 tracking-[0.3em]">// {kicker}</span>
      </div>
      <h2 className="text-3xl md:text-4xl font-bold text-slate-100 tracking-tight">
        {title}
      </h2>
      <p className="text-sm text-slate-400 mt-2.5 max-w-3xl leading-relaxed mb-7">
        {subtitle}
      </p>
      {children}
    </motion.section>
  );
}
