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
  // bottom hits viewport top. We map that to opacity / Y / scale so the
  // previous section visibly drops away and shrinks while the next one rises in.
  // The narrow [0.42, 0.58] plateau means only one section is fully visible
  // at a time — the transition between them is sharp.
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const opacity = useTransform(
    scrollYProgress,
    [0, 0.42, 0.58, 1],
    [0, 1, 1, 0],
  );
  const y = useTransform(
    scrollYProgress,
    [0, 0.42, 0.58, 1],
    [80, 0, 0, -80],
  );
  const scale = useTransform(
    scrollYProgress,
    [0, 0.42, 0.58, 1],
    [0.92, 1, 1, 0.92],
  );

  return (
    <motion.section ref={ref} style={{ opacity, y, scale }}>
      <div className="flex items-baseline gap-3 mb-1.5">
        <span className="font-mono text-[10px] text-blue-400 tracking-[0.3em]">// {kicker}</span>
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
