"use client";

const SHA = process.env.NEXT_PUBLIC_BUILD_SHA ?? "dev";
const TIME = process.env.NEXT_PUBLIC_BUILD_TIME ?? "";
const TIME_SHORT = TIME ? TIME.replace("T", " ").slice(0, 16) + "Z" : "";

export default function VersionBadge() {
  return (
    <div className="fixed bottom-3 right-3 z-50 pointer-events-auto group">
      <a
        href={`https://github.com/anmemol-beta/zerve-odsc-ai-datathon/commit/${SHA}`}
        target="_blank"
        rel="noopener noreferrer"
        className="font-mono text-[10px] tracking-wider text-slate-500 hover:text-pink-600 transition-colors px-2 py-1 rounded-md bg-ink-900/70 backdrop-blur-md border border-slate-200/60"
      >
        <span className="text-slate-600">build</span>{" "}
        <span className="text-slate-300">{SHA}</span>
        <span className="hidden group-hover:inline text-slate-500"> · {TIME_SHORT}</span>
      </a>
    </div>
  );
}
