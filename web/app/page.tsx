import dynamic from "next/dynamic";
import fs from "node:fs/promises";
import path from "node:path";
import HeadlineCards from "@/components/HeadlineCards";
import UserLookup from "@/components/UserLookup";
import FunnelExplorer from "@/components/FunnelExplorer";
import type { Headline, Manifold, UserRow, FunnelGrid } from "@/lib/types";

// 3D canvas needs window — load client-side only.
const Manifold3D = dynamic(() => import("@/components/Manifold3D"), { ssr: false });

async function loadJSON<T>(name: string): Promise<T> {
  const p = path.join(process.cwd(), "public", "data", `${name}.json`);
  return JSON.parse(await fs.readFile(p, "utf-8")) as T;
}

export default async function Page() {
  const [headline, manifold, users, funnelGrid] = await Promise.all([
    loadJSON<Headline>("headline"),
    loadJSON<Manifold>("manifold"),
    loadJSON<UserRow[]>("users"),
    loadJSON<FunnelGrid>("funnel_grid"),
  ]);

  return (
    <main className="max-w-[1400px] mx-auto px-6 py-10 space-y-12">
      {/* Hero */}
      <header>
        <div className="text-xs uppercase tracking-[0.25em] text-slate-400 mb-3">
          ODSC × Zerve AI Datathon · April 2026
        </div>
        <h1 className="text-5xl md:text-6xl font-extrabold leading-[1.05] tracking-tight">
          <span className="gradient-text">User funnel</span>
          <span className="text-slate-200"> & upgrade predictor</span>
        </h1>
        <p className="mt-4 text-slate-400 max-w-2xl text-sm leading-relaxed">
          A leakage-safe upgrade-prediction model and a strict-nested 6-stage funnel,
          built end-to-end in Zerve. Drag the 3D manifold, score any user, retune the
          funnel rules — every prediction is explainable.
        </p>
      </header>

      <HeadlineCards data={headline} />

      <Section
        kicker="03"
        title="User behavior manifold"
        subtitle="3D PCA of every user's first-window behavior. Color = funnel stage. Size = predicted upgrade probability. Drag to rotate, scroll to zoom — pink upgraders cluster in one corner of feature space."
      >
        <Manifold3D manifold={manifold} />
      </Section>

      <Section
        kicker="04"
        title="Per-user prediction & explanation"
        subtitle="Pick a user → upgrade likelihood + the SHAP factors that pushed it up or down. Pink bars push the score up; cyan push it down. The center line is the model's expected prediction."
      >
        <UserLookup users={users} />
      </Section>

      <Section
        kicker="05"
        title="Funnel flow & live thresholds"
        subtitle="Sankey shows actual user flow between funnel stages. Sliders recompute the funnel live — moving them proves the strict-nested rule system stays monotone (no stage explodes when you retune)."
      >
        <FunnelExplorer grid={funnelGrid} />
      </Section>

      <footer className="text-center text-xs text-slate-600 pt-8 pb-4 border-t border-slate-800/60">
        3.5M events · 17,541 users · 2025-09-01 → 2026-04-16 · Built in Zerve, deployed as a single static archive.
      </footer>
    </main>
  );
}

function Section({
  kicker, title, subtitle, children,
}: {
  kicker: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-baseline gap-3 mb-1.5">
        <span className="font-mono text-xs text-pink-400 tracking-widest">// {kicker}</span>
      </div>
      <h2 className="text-2xl md:text-3xl font-bold text-slate-100">{title}</h2>
      <p className="text-sm text-slate-400 mt-2 max-w-3xl leading-relaxed mb-6">{subtitle}</p>
      {children}
    </section>
  );
}
