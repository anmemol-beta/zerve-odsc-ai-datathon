import dynamic from "next/dynamic";
import fs from "node:fs/promises";
import path from "node:path";
import Hero from "@/components/Hero";
import HeadlineCards from "@/components/HeadlineCards";
import Section from "@/components/Section";
import UserLookup from "@/components/UserLookup";
import FunnelExplorer from "@/components/FunnelExplorer";
import type { Headline, Manifold, UserRow, FunnelGrid } from "@/lib/types";

const Manifold3D = dynamic(() => import("@/components/Manifold3D"), { ssr: false });
const ShaderBackground = dynamic(() => import("@/components/ShaderBackground"), { ssr: false });

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
    <main className="relative max-w-[1400px] mx-auto px-6 lg:px-8 space-y-16 pb-24">
      <ShaderBackground />
      <Hero />
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

      <footer className="text-center text-xs text-slate-600 pt-10 mt-6 border-t border-slate-800/60">
        Built end-to-end in Zerve · 3.5M events · 17,541 users · 2025-09-01 → 2026-04-16
      </footer>
    </main>
  );
}
