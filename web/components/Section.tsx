"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

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
  const ref = useRef<HTMLElement>(null);
  // Scroll progress: 0 when section's top hits viewport bottom, 1 when its
  // bottom hits viewport top. We map that to opacity + Y offset so the section
  // fades and lifts in as it enters, then fades and lifts out as it leaves.
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const opacity = useTransform(
    scrollYProgress,
    [0, 0.18, 0.82, 1],
    [0, 1, 1, 0],
  );
  const y = useTransform(
    scrollYProgress,
    [0, 0.18, 0.82, 1],
    [40, 0, 0, -40],
  );

  return (
    <motion.section ref={ref} style={{ opacity, y }}>
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
