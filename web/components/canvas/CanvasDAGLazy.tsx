"use client";

import dynamic from "next/dynamic";

const CanvasDAG = dynamic(() => import("./CanvasDAG"), {
  ssr: false,
  loading: () => (
    <div className="h-[760px] animate-pulse rounded-2xl border border-slate-700/80 bg-slate-900/60" />
  ),
});

export default function CanvasDAGLazy() {
  return <CanvasDAG />;
}
