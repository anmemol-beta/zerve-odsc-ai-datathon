"use client";

export default function LiftBar({
  lift,
  max,
  className = "",
}: {
  lift: number;
  max: number;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(lift / max, 1));
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-slate-900 ${className}`}>
      <div
        className="h-full rounded-full bg-gradient-to-r from-violet-500 to-pink-500"
        style={{ width: `${pct * 100}%` }}
      />
    </div>
  );
}
