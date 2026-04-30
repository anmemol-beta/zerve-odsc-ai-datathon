import Hero from "@/components/Hero";
import HeroStats from "@/components/HeroStats";
import Section from "@/components/Section";
import HealthBadge from "@/components/HealthBadge";
import DiscoveryCards from "@/components/DiscoveryCards";
import FunnelView from "@/components/FunnelView";
import LivePredict from "@/components/LivePredict";
import StrategyGallery from "@/components/StrategyGallery";
import InsightsCard from "@/components/InsightsCard";
import VersionBadge from "@/components/VersionBadge";
import ShaderBackgroundLazy from "@/components/ShaderBackgroundLazy";
import CanvasDAGLazy from "@/components/canvas/CanvasDAGLazy";

export default function Page() {
  return (
    <main className="relative mx-auto max-w-[1400px] space-y-16 px-6 pb-24 lg:px-8">
      <ShaderBackgroundLazy />
      <Hero />

      <div className="-mt-4 flex justify-end">
        <HealthBadge />
      </div>

      <HeroStats />

      <Section
        kicker="01"
        title="What the data is screaming"
        subtitle="3.5M events, 17,541 users, 323 upgraders. Three patterns leap off the page before any model runs — and every downstream playbook traces back to one of them."
      >
        <DiscoveryCards />
      </Section>

      <Section
        kicker="02"
        title="The 9-stage funnel"
        subtitle="Strict-nested cohorts: every user enters at Signed up, advances if their behavior triggers the next stage, and stalls into At-risk if they go dormant. Width = users; amber ribbons = the at-risk siphon at each stage."
      >
        <FunnelView />
      </Section>

      <Section
        kicker="03"
        title="The canvas, in your browser"
        subtitle="Every block here is a real Zerve canvas node. Coordinates, edges, descriptions all read straight from canvas.yaml. Click a block to pull its live matplotlib figure or variable from the deployed FastAPI — same calibrated XGB ensemble, same cohort tables, same K2 strategies that the data scientist sees inside the canvas."
      >
        <CanvasDAGLazy />
      </Section>

      <Section
        kicker="04"
        title="Live inference · v3 ensemble"
        subtitle={`Pick any test-set row index — the request flies through beta-zerve.hub.zerve.cloud, which calls zerve.variable("Train Model v3", "models") on the canvas and runs predict_proba across all 3 calibration folds. The probability you see is generated server-side, not baked into a static JSON.`}
      >
        <LivePredict />
      </Section>

      <Section
        kicker="05"
        title="K2-Think strategies · per-segment"
        subtitle="14 v4 funnel segments. Each one shipped through the Build Strategies node, which prompts K2-Think with the segment's behavioral profile and a Zerve playbook excerpt. The 3 ranked actions, target filters, expected uplift, and ROI multipliers come back in real time from the deployed canvas."
      >
        <StrategyGallery />
      </Section>

      <Section
        kicker="06"
        title="Insights card · the fan-in"
        subtitle="The final canvas node — fan-in from Diagnose v3, SHAP v3, Compare Models, Per-Segment Performance, Build Strategies, and ROI Ranking. The PNG and the text both come from the same canvas variables, fetched live."
      >
        <InsightsCard />
      </Section>

      <footer className="mt-6 border-t border-slate-800/60 pt-10 text-center font-mono text-[10px] tracking-wider text-slate-600">
        Zerve canvas · 32 blocks · 42 edges · beta-zerve.hub.zerve.cloud
      </footer>
      <VersionBadge />
    </main>
  );
}
