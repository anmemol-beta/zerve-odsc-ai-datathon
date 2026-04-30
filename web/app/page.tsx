import dynamic from "next/dynamic";
import fs from "node:fs/promises";
import path from "node:path";
import Hero from "@/components/Hero";
import HeadlineCards from "@/components/HeadlineCards";
import Section from "@/components/Section";
import UserLookup from "@/components/UserLookup";
import FunnelExplorer from "@/components/FunnelExplorer";
import TimeTravel from "@/components/TimeTravel";
import ActionCards from "@/components/ActionCards";
import VersionBadge from "@/components/VersionBadge";
import type {
  Headline,
  Manifold,
  UserRow,
  FunnelGrid,
  DailyTimeline,
  StrategiesIndex,
} from "@/lib/types";

const Manifold3D = dynamic(() => import("@/components/Manifold3D"), { ssr: false });
const ShaderBackground = dynamic(() => import("@/components/ShaderBackground"), { ssr: false });

async function loadJSON<T>(name: string): Promise<T> {
  const p = path.join(process.cwd(), "public", "data", `${name}.json`);
  return JSON.parse(await fs.readFile(p, "utf-8")) as T;
}

export default async function Page() {
  const [headline, manifold, users, funnelGrid, dailyTimeline, strategies] =
    await Promise.all([
      loadJSON<Headline>("headline"),
      loadJSON<Manifold>("manifold"),
      loadJSON<UserRow[]>("users"),
      loadJSON<FunnelGrid>("funnel_grid"),
      loadJSON<DailyTimeline>("daily_timeline"),
      loadJSON<StrategiesIndex>("strategies"),
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

      <Section
        kicker="06"
        title="Time-travel mode"
        subtitle="Press play and the panel rewinds to Sept 1, 2025, then advances through every single day to Apr 16, 2026 at up to 32 days/sec — date label, headline counters, funnel composition, growth curves, daily-event spark, and weekly top-events all animate in lockstep. Pink dots above the spark are upgrade events; a flash on the date card means a user converted today. Scrub the trend chart or drag the slider to jump to any day."
      >
        <TimeTravel data={dailyTimeline} />
      </Section>

      <Section
        kicker="07"
        title="K2 strategist — segment-specific marketing actions"
        subtitle="Pick any funnel segment → K2-Think reads its behavior, demographics, model score, and a Zerve playbook excerpt, then returns 3 ranked actions (channel, copy, target filter, expected ROI) plus 3 risks. Every recommendation is grounded in this segment's data, not generic advice."
      >
        <ActionCards data={strategies} />
      </Section>

      <footer className="text-center text-xs text-slate-600 pt-10 mt-6 border-t border-slate-800/60">
        Built end-to-end in Zerve · 3.5M events · 17,541 users · 2025-09-01 → 2026-04-16
      </footer>
      <VersionBadge />
    </main>
  );
}
