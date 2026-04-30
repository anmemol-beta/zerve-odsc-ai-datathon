"use client";

import { motion } from "framer-motion";
import { useRef, useState, MouseEvent } from "react";
import AnimatedNumber from "./AnimatedNumber";
import type { Headline } from "@/lib/types";

const fmt = (n: number) => Math.round(n).toLocaleString();

type Card = {
  label: string;
  value: number;
  sub: string;
  accent: string;
  glow: string;
  text: string;
  warn?: boolean;
};

function TiltCard({ card, index }: { card: Card; index: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number }>({ x: 50, y: 50 });
  const [active, setActive] = useState(false);

  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    setPos({
      x: ((e.clientX - rect.left) / rect.width) * 100,
      y: ((e.clientY - rect.top) / rect.height) * 100,
    });
  };
  const onLeave = () => {
    setPos({ x: 50, y: 50 });
    setActive(false);
  };
  const onEnter = () => setActive(true);

  // Rotate offsets ±5deg, scaled by mouse position
  const rotX = ((pos.y - 50) / 50) * -5;
  const rotY = ((pos.x - 50) / 50) * 7;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      onMouseMove={onMove}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      style={{
        transform: `perspective(900px) rotateX(${rotX}deg) rotateY(${rotY}deg)`,
        transition: "transform 0.18s cubic-bezier(.2,.9,.4,1)",
      }}
      className="group relative rounded-2xl p-px overflow-hidden"
    >
      <div className={`absolute inset-0 bg-gradient-to-br ${card.accent} opacity-70 group-hover:opacity-100 transition-opacity duration-500`} />

      <div className="relative rounded-[15px] bg-ink-900/85 backdrop-blur-md p-5 overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none transition-opacity duration-500"
          style={{
            opacity: active ? 1 : 0,
            background: `radial-gradient(240px circle at ${pos.x}% ${pos.y}%, ${card.glow}, transparent 60%)`,
          }}
        />

        <div className="relative">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400 font-mono">
            {card.label}
          </div>
          <div className={`mt-2 text-5xl md:text-6xl font-black tracking-[-0.04em] tabular-nums ${card.warn ? "text-amber-300" : card.text}`}>
            <AnimatedNumber value={card.value} duration={1400 + index * 100} />
          </div>
          <div className="mt-2 text-[11px] text-slate-400 leading-snug">{card.sub}</div>
        </div>
      </div>
    </motion.div>
  );
}

export default function HeadlineCards({ data }: { data: Headline }) {
  const cards: Card[] = [
    {
      label: "users",
      value: data.n_users,
      sub: `${fmt(data.n_events)} events · ${data.n_event_types} types`,
      accent: "from-violet-500/40 via-violet-500/10 to-cyan-500/30",
      glow: "rgba(139,92,246,0.32)",
      text: "text-slate-50",
    },
    {
      label: "reached engaged",
      value: data.n_engaged,
      sub: `${((data.n_engaged / data.n_users) * 100).toFixed(1)}% of all users`,
      accent: "from-emerald-500/40 via-emerald-500/10 to-emerald-500/5",
      glow: "rgba(16,185,129,0.30)",
      text: "text-emerald-100",
    },
    {
      label: "upgraded",
      value: data.n_upgraded,
      sub: `${(data.base_upgrade_rate * 100).toFixed(2)}% base · ~53:1 imbalance`,
      accent: "from-pink-500/50 via-pink-500/15 to-pink-500/5",
      glow: "rgba(236,72,153,0.40)",
      text: "text-pink-200",
    },
    {
      label: "at risk",
      value: data.n_at_risk,
      sub: `${((data.n_at_risk / data.n_engaged) * 100).toFixed(0)}% of engaged · idle 14d+`,
      accent: "from-amber-500/50 via-amber-500/15 to-amber-500/5",
      glow: "rgba(245,158,11,0.40)",
      text: "text-amber-200",
      warn: true,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c, i) => (
        <TiltCard key={c.label} card={c} index={i} />
      ))}
    </div>
  );
}
