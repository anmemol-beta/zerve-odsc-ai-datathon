"use client";

// Smaller subheader inside a Section — for grouping subblocks.
export default function SectionHeader({
  kicker,
  title,
  subtitle,
}: {
  kicker?: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-4">
      {kicker && (
        <div className="font-mono text-[10px] tracking-[0.3em] text-pink-300">
          {kicker}
        </div>
      )}
      <h3 className="mt-1 text-xl font-semibold tracking-tight text-slate-100">
        {title}
      </h3>
      {subtitle && (
        <p className="mt-1.5 text-xs leading-relaxed text-slate-400">
          {subtitle}
        </p>
      )}
    </div>
  );
}
