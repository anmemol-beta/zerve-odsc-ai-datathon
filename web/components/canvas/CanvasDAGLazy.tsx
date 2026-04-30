"use client";

import dynamic from "next/dynamic";

const CanvasDAG = dynamic(() => import("./CanvasDAG"), {
  ssr: false,
  loading: () => (
    <div className="h-[760px] animate-pulse rounded-2xl border border-slate-200/80 bg-slate-50" />
  ),
});

export default function CanvasDAGLazy() {
  return <CanvasDAG />;
}
