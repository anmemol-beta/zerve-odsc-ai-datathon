import Hero from "@/components/Hero";
import HeroStats from "@/components/HeroStats";
import Section from "@/components/Section";
import HealthBadge from "@/components/HealthBadge";
import DiscoveryCards from "@/components/DiscoveryCards";
import FunnelView from "@/components/FunnelView";
import TransitionHeatmap from "@/components/TransitionHeatmap";
import SignalCombo from "@/components/SignalCombo";
import LeakageAudit from "@/components/LeakageAudit";
import ModelComparison from "@/components/ModelComparison";
import FeatureImportance from "@/components/FeatureImportance";
import TopKSimulator from "@/components/TopKSimulator";
import LivePredict from "@/components/LivePredict";
import PlaybookList from "@/components/PlaybookList";
import InsightsCard from "@/components/InsightsCard";
import VersionBadge from "@/components/VersionBadge";

export default function Page() {
  return (
    <main className="relative mx-auto max-w-[1400px] space-y-16 px-6 pb-24 lg:px-8">
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
        title="Stage-to-stage transitions"
        subtitle="Row-stochastic matrix derived from the user_features_v4 cohort. Pink-bordered cells are the transitions worth investing in — Connected → Engaged is the strongest natural progression."
      >
        <TransitionHeatmap />
      </Section>

      <Section
        kicker="04"
        title="Signal combinations · live recompute"
        subtitle="Three behavioral flags multiply upgrade probability. Toggle them to see how the conditional rate keys into the lookup table the model uses for thin segments."
      >
        <SignalCombo />
      </Section>

      <Section
        kicker="05"
        title="Leakage audit"
        subtitle="Every guardrail green. The mechanical 21-check sweep across cutoffs, blacklists, splits, and calibration — and the obs_days story behind why we dropped 39 features."
      >
        <LeakageAudit />
      </Section>

      <Section
        kicker="06"
        title="Model comparison"
        subtitle="Five models, same test cohort. The calibrated ensemble takes the crown on PR-AUC and Brier. Curves are PR (precision-recall) and reliability (predicted vs observed) overlaid before/after isotonic calibration."
      >
        <ModelComparison />
      </Section>

      <Section
        kicker="06.5"
        title="Feature importance · marketing bridge"
        subtitle="SHAP top-10 for the champion ensemble. Each top-3 feature already has a corresponding playbook action — the bridge from prediction to revenue."
      >
        <FeatureImportance />
      </Section>

      <Section
        kicker="07"
        title="Top-K simulator ★"
        subtitle="Drag the slider — pick what fraction of the user base to target by score. The curve is exact for the synthetic test cohort; the right pane recomputes precision, recall, lift, and net ROI in real time."
      >
        <TopKSimulator />
      </Section>

      <Section
        kicker="08"
        title="Inference · scoring any user"
        subtitle="Pick any test-set row index — the calibrated ensemble produces an upgrade probability, predicted funnel stage, and the three features that drove the score. Same model, same calibration, same probabilities the playbook is sized against."
      >
        <LivePredict />
      </Section>

      <Section
        kicker="09"
        title="Playbook · 7 ranked actions"
        subtitle="ROI-ranked. Top-3 are the must-ship moves; the rest cover retention and B2B. Every row maps back to a SHAP-positive feature, and the target counts come straight from the per-segment performance table."
      >
        <PlaybookList />
      </Section>

      <Section
        kicker="10"
        title="Insights · the fan-in"
        subtitle="The final canvas node — fan-in from diagnostics, SHAP, model comparison, per-segment performance, strategies, and ROI ranking. Headline metrics, funnel widths, and playbook priorities collapsed into a single artifact."
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
