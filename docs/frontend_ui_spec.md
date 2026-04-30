# Frontend Rebuild Spec — engineering handoff

> **Audience**: 동료 개발자가 `web/`를 발표용으로 재구성할 때 그대로 보고 빌드할 수 있도록.
> **Goal**: 기존 4-section 사이트(`Hero / CanvasDAG / LivePredict / StrategyGallery / InsightsCard`)를 **11-section 발표용 사이트**로 확장.
> **Stack 그대로**: Next.js 14 App Router · Tailwind · ReactFlow · @tanstack/react-query · framer-motion · TypeScript strict.

---

## 0. 현재 상태 (재사용/수정/신규 구분)

### 재사용 (변경 최소화)

| 파일 | 상태 | 변경 |
|---|---|---|
| `web/lib/api.ts` | OK | 신규 엔드포인트 5개 추가 |
| `web/lib/canvas.ts` | OK | 그대로 |
| `web/components/Providers.tsx` | OK | 그대로 |
| `web/components/Hero.tsx` | 수정 | stat 카드 4개 갱신 (3.5M / 17,541 / 323 / 10.6×) |
| `web/components/HealthBadge.tsx` | OK | 그대로 |
| `web/components/Section.tsx` | OK | 그대로, prop 추가 가능 |
| `web/components/AnimatedNumber.tsx` | OK | 그대로 |
| `web/components/ShaderBackground*.tsx` | OK | 그대로 |
| `web/components/canvas/CanvasDAG.tsx` | OK | 위치만 하단으로 이동 |
| `web/components/InsightsCard.tsx` | OK | finale로 이동, 링크 한 줄 추가 |
| `web/components/LivePredict.tsx` | 보강 | stage + SHAP top-3 표시 |
| `web/components/StrategyGallery.tsx` | OK | 카피 버튼 추가 |
| `web/components/VersionBadge.tsx` | OK | 그대로 |

### 신규 컴포넌트 (이번 PR에서 만들 것)

```
web/components/
├── DiscoveryCards.tsx          # §01
├── FunnelView.tsx              # §02 (sankey + donut + insight)
├── TransitionHeatmap.tsx       # §03
├── SignalCombo.tsx             # §04 (3-flag toggle)
├── LeakageAudit.tsx            # §05
├── ModelComparison.tsx         # §06 (table + curves)
├── TopKSimulator.tsx           # §07 (★ 핵심 인터랙션)
├── PlaybookList.tsx            # §09
└── shared/
    ├── StatCard.tsx
    ├── LiftBar.tsx
    └── SectionHeader.tsx
```

### 신규 API 엔드포인트 (백엔드 추가 필요)

`zerve_deploy/main.py`에 5개 추가. inline fallback도 같이.

```python
@app.get("/api/hero-stats")        # §Hero
@app.get("/api/eda-lifts")         # §01
@app.get("/api/funnel-stages")     # §02 — 기존 /metrics 확장 또는 신규
@app.get("/api/post-upgrade")      # §02 도넛
@app.get("/api/transitions")       # §03
@app.get("/api/predictions/test")  # §07 — score array (~7.5K floats)
@app.get("/api/playbook")          # §09
```

---

## 1. 페이지 구조 (`web/app/page.tsx`)

```tsx
import Hero from "@/components/Hero";
import Section from "@/components/Section";
import HealthBadge from "@/components/HealthBadge";
import VersionBadge from "@/components/VersionBadge";
import ShaderBackgroundLazy from "@/components/ShaderBackgroundLazy";

import DiscoveryCards from "@/components/DiscoveryCards";
import FunnelView from "@/components/FunnelView";
import TransitionHeatmap from "@/components/TransitionHeatmap";
import SignalCombo from "@/components/SignalCombo";
import LeakageAudit from "@/components/LeakageAudit";
import ModelComparison from "@/components/ModelComparison";
import TopKSimulator from "@/components/TopKSimulator";
import LivePredict from "@/components/LivePredict";
import PlaybookList from "@/components/PlaybookList";
import StrategyGallery from "@/components/StrategyGallery";
import CanvasDAGLazy from "@/components/canvas/CanvasDAGLazy";
import InsightsCard from "@/components/InsightsCard";

export default function Page() {
  return (
    <main className="relative mx-auto max-w-[1400px] space-y-16 px-6 pb-24 lg:px-8">
      <ShaderBackgroundLazy />
      <Hero />

      <div className="-mt-4 flex justify-end"><HealthBadge /></div>

      <Section kicker="01" title="What we found"
               subtitle="3.5M events 안에 숨어 있던 사용자 행동의 세 가지 진실.">
        <DiscoveryCards />
      </Section>

      <Section kicker="02" title="The 15-stage funnel"
               subtitle="모든 사용자가 정확히 한 단계에 배치되고, 결제 후 라이프사이클까지 추적.">
        <FunnelView />
      </Section>

      <Section kicker="03" title="How users move"
               subtitle="단계 간 전이 확률 — 비즈니스 ROI가 가장 높은 구간을 한눈에.">
        <TransitionHeatmap />
      </Section>

      <Section kicker="04" title="Three behavioral flags"
               subtitle="조합을 직접 토글해서 결제율이 어떻게 변하는지 확인.">
        <SignalCombo />
      </Section>

      <Section kicker="05" title="Why our numbers are honest"
               subtitle="21개 leakage 검증 모두 통과. 가장 어려웠던 케이스를 공개.">
        <LeakageAudit />
      </Section>

      <Section kicker="06" title="Model head-to-head"
               subtitle="단순 다수부터 calibrated ensemble까지 — 정직한 비교.">
        <ModelComparison />
      </Section>

      <Section kicker="07" title="Campaign ROI calculator"
               subtitle="타겟 비율을 슬라이더로 움직이면 결제자 포착 수가 즉시 갱신.">
        <TopKSimulator />
      </Section>

      <Section kicker="08" title="Score any user"
               subtitle="row index 입력 → 예측 확률 + 단계 + top-3 contributing features.">
        <LivePredict />
      </Section>

      <Section kicker="09" title="Seven actions, ranked"
               subtitle="발견을 즉시 실행 가능한 캠페인으로.">
        <PlaybookList />
      </Section>

      <Section kicker="10" title="AI strategist (K2-Think)"
               subtitle="14 segments × 3 actions — 채널, 메시지, ROI까지 자동 생성.">
        <StrategyGallery />
      </Section>

      <Section kicker="11" title="One canvas, 39 blocks"
               subtitle="전부 한 Zerve 캔버스 안. 클릭하면 라이브 결과를 가져옵니다.">
        <CanvasDAGLazy />
      </Section>

      <Section kicker="END" title="The summary card"
               subtitle="Diagnose · SHAP · Compare · ROI · K2 — 모든 게 fan-in.">
        <InsightsCard />
      </Section>

      <VersionBadge />
    </main>
  );
}
```

---

## 2. 섹션별 상세 사양

각 섹션마다 **Props · 데이터 계약(API 응답 타입) · 인터랙션 · 인라인 폴백 · 완료 기준** 4종 세트로 정리.

---

### §HERO — `Hero.tsx` 보강

**현재**: 헤드라인 + 단순 메타 한 줄(3.5M events / 17,541 users / 228 days)

**변경**: 4개 stat 카드를 `<AnimatedNumber>` 기반으로 교체.

```tsx
type HeroStats = {
  events_total: number;          // 3_509_628
  users_total: number;           // 17_541
  upgraders_total: number;       // 323
  base_rate: number;             // 0.01841
  random_pr_auc: number;         // 0.0184
  ensemble_pr_auc: number;       // 0.2645
  // 파생: lift = ensemble_pr_auc / random_pr_auc → 10.6
};
```

API: `GET /api/hero-stats`

UI:
```
┌──────┬────────┬──────────┬────────────┐
│ 3.5M │ 17,541 │   323    │   10.6×    │
│events│ users  │upgraders │ vs random  │
└──────┴────────┴──────────┴────────────┘
```

Punchline 한 줄 추가: `결제자 절반을 상위 5%에게만 보내서 잡습니다.`

**완료 기준**:
- [ ] 4 카드 모두 `<AnimatedNumber from={0} to={...} duration={1500} />`
- [ ] `useQuery<HeroStats>(['hero-stats'], api.heroStats)` (fallback inline)
- [ ] 모바일 2×2 grid

---

### §01 DISCOVERY — `DiscoveryCards.tsx` (신규)

**목적**: EDA 핵심 3가지를 카드로. 영상 0:05–0:23.

```tsx
type EdaLifts = {
  median_lifetime_minutes: number;       // 14
  pct_upgrade_same_day: number;          // 0.613
  pct_upgrade_within_7d: number;         // 0.759
  top_signals: Array<{
    event: string;                       // "credits_exceeded"
    label_ko: string;                    // "크레딧 한도 도달"
    upgrader_reach: number;              // 0.499
    non_upgrader_reach: number;          // 0.040
    lift: number;                        // 12.4
  }>;
};
```

API: `GET /api/eda-lifts`

레이아웃: 3-col grid (lg), 1-col (sm).

```tsx
<div className="grid gap-6 lg:grid-cols-3">
  <DiscoveryCard
    icon="⏱"
    title="Median lifetime"
    big="14 min"
    sub="절반이 가입 후 14분 내 이탈"
    detail="모델은 첫 1시간 / 1일 시그널만 봐야 함"
    accent="cyan"
  />
  <DiscoveryCard
    icon="💸"
    title="Upgrade timing"
    big="61%"
    sub="가입 당일 결제 / 7일 내 76%"
    detail="long history는 무의미"
    accent="violet"
  />
  <DiscoveryCard
    icon="🎯"
    title="Strongest signal"
    big="22×"
    sub="banner_shown lift"
    detail="hover로 추가 신호 5개 reveal"
    accent="pink"
    onHover={() => setRevealed(true)}
  />
</div>
```

`DiscoveryCard` 호버 시 `top_signals` 배열의 5개를 추가로 펼쳐서 mini-list.

**인라인 폴백**:
```ts
const FALLBACK_EDA: EdaLifts = {
  median_lifetime_minutes: 14,
  pct_upgrade_same_day: 0.613,
  pct_upgrade_within_7d: 0.759,
  top_signals: [
    { event: "credits_exceeded", label_ko: "크레딧 한도 도달", upgrader_reach: 0.499, non_upgrader_reach: 0.040, lift: 12.4 },
    { event: "ai_credit_banner_shown", label_ko: "한도 임박 배너 노출", upgrader_reach: 0.399, non_upgrader_reach: 0.018, lift: 22.0 },
    { event: "agent_tool_call_analyze_attachment_tool", label_ko: "분석 도구 사용", upgrader_reach: 0.415, non_upgrader_reach: 0.035, lift: 11.9 },
    { event: "notebook_deployment_deployed", label_ko: "배포 실행", upgrader_reach: 0.230, non_upgrader_reach: 0.018, lift: 12.5 },
    { event: "source_control_commit", label_ko: "Git 커밋", upgrader_reach: 0.090, non_upgrader_reach: 0.006, lift: 14.1 },
    { event: "canvas_clone", label_ko: "캔버스 복제", upgrader_reach: 0.074, non_upgrader_reach: 0.005, lift: 14.0 },
  ],
};
```

**완료 기준**:
- [ ] 카드 3개 hover 시 `top_signals` 5개 reveal (framer-motion fade-in)
- [ ] 한국어 라벨 우선, 영어 event 이름은 sub-text
- [ ] 모바일 1-col stack, hover → tap reveal

---

### §02 FUNNEL — `FunnelView.tsx` (신규)

**목적**: 15단계 분포 + post-upgrade lifecycle. 영상 0:41 + 0:53.

```tsx
type FunnelStages = {
  stages: Array<{
    id: string;             // "8.Upgraded"
    label_ko: string;       // "결제 활동중"
    users: number;          // 221
    pct: number;            // 0.0126
    is_terminal: boolean;
  }>;
  upgrade_outcomes: {
    active: number;         // 221
    at_risk: number;        // 74
    churned: number;        // 28
  };
};
```

API: `GET /api/funnel-stages` + `GET /api/post-upgrade`

**라이브러리**: 차트는 `recharts` 안 쓰고 직접. 이유:
- sankey는 `d3-sankey` (이미 `package.json`에 있음 — 첫 PR에서 선언만)
- 도넛은 SVG 직접 그리기 (60줄)

레이아웃:
```
┌──────────────────────────────────────────────────────────┐
│  [ 15-stage funnel sankey · full width ]                 │
├──────────────────────────────────────────────────────────┤
│  [ 도넛 (1/3) ]   [ insight 카드 (2/3) ]                │
└──────────────────────────────────────────────────────────┘
```

**라벨 매핑** (필수, `lib/stage-labels.ts`로 분리):
```ts
export const STAGE_LABEL_KO: Record<string, string> = {
  "0.NoEvent":            "이벤트 없음",
  "1.New":                "가입",
  "2.Exploring":          "탐색",
  "3.Created":            "첫 생성",
  "4.UsedAI":             "AI 사용",
  "5.WroteCode":          "코드 작성",
  "6.Integrated":         "외부 도구 연결",
  "7.Engaged":            "꾸준한 활동",
  "8.Upgraded":           "결제 활동중",
  "9.AtRisk@UsedAI":      "위험 (AI 사용 단계)",
  "9.AtRisk@WroteCode":   "위험 (코드 단계)",
  "9.AtRisk@Integrated":  "위험 (연결 단계)",
  "9.AtRisk@Engaged":     "위험 (꾸준한 활동 단계)",
  "9.AtRisk@Upgraded":    "결제 후 위험",
  "9.Churned@Upgraded":   "결제 후 이탈",
};
```

**인터랙션**:
- 단계 클릭 → 우측에 그 단계 상세 (n / 결제율 / median time-in-stage)
- 도넛 mount 시 toast: `"가장 중요한 발견 — 결제자 셋 중 한 명이 위험 상태"` 3초 표시 후 fade-out

**완료 기준**:
- [ ] sankey가 좌→우 정렬되고 노드 hover 시 라벨 + 사용자 수
- [ ] 도넛에 active 68% (emerald) / at-risk 23% (amber) / churned 9% (rose)
- [ ] 첫 마운트 시 toast 자동 등장
- [ ] 모바일에서 sankey가 가로 스크롤로 잘리지 않게 — viewBox 활용

---

### §03 TRANSITIONS — `TransitionHeatmap.tsx` (신규)

**목적**: 8×8 transition matrix.

```tsx
type Transitions = {
  rows: string[];                         // ["1.New", ..., "8.Upgraded"]
  cols: string[];
  matrix: number[][];                     // matrix[from][to] = probability
  highlight_cells: Array<{
    from: string;
    to: string;
    note_ko: string;                      // "결제로 이어지는 비율 13% = 평균의 7배"
  }>;
};
```

API: `GET /api/transitions`

**구현**: CSS grid (라이브러리 X). 8 col × 8 row, 각 셀 `flex items-center justify-center`.

색상: `bg-cyan-500/{Math.round(prob*100)}` 같은 동적 클래스는 Tailwind에서 안 됨 → inline `style={{ background: \`rgba(34,211,238,${prob})\` }}`

**핵심 강조**:
- `Integrated → Engaged 51.2%`: cyan glow border
- `Engaged → Upgraded 12.8%`: pink glow border + ★

호버 → 사이드 패널에 `note_ko` + n + median time.

**완료 기준**:
- [ ] 셀 색 강도 = 확률 (0~1 → opacity)
- [ ] 강조 셀 2개 항상 visible glow
- [ ] 모바일에서 가로 스크롤 wrapper

---

### §04 SIGNAL COMBO — `SignalCombo.tsx` (신규)

**목적**: 3-flag 토글 → 결제율 인터랙티브.

```tsx
type ComboLookup = Record<string, {       // key = "111" | "110" | ... | "000"
  users: number;
  upgraders: number;
  rate: number;
}>;

const FALLBACK_COMBOS: ComboLookup = {
  "111": { users: 1204, upgraders: 139, rate: 0.1154 },  // 모두 ON
  "110": { users:  450, upgraders:  18, rate: 0.0400 },
  "101": { users:  680, upgraders:  19, rate: 0.0279 },
  "100": { users: 1850, upgraders:  35, rate: 0.0189 },
  "011": { users:  720, upgraders:  22, rate: 0.0306 },
  "010": { users:  890, upgraders:  16, rate: 0.0180 },
  "001": { users: 2423, upgraders:  54, rate: 0.0223 },
  "000": { users: 9324, upgraders:  20, rate: 0.0021 },  // 모두 OFF
};
```

값은 `feature_matrix.parquet`에서 한 번 계산해서 inline (외부 fetch 불필요).

UI:
```tsx
<div className="grid gap-8 lg:grid-cols-[2fr_3fr]">
  <div className="space-y-3">
    <Toggle label="꾸준한 사용자 (7일+ 활동)" value={a} onChange={setA} />
    <Toggle label="AI를 먼저 써본 사용자"     value={b} onChange={setB} />
    <Toggle label="온보딩 완주자"             value={c} onChange={setC} />
  </div>
  <ComboResult key={`${a}${b}${c}`} {...lookup[key]} />
</div>
```

`ComboResult`는 큰 숫자 3개 (사용자 수 / 결제율 / lift vs base 1.84%).

**Edge case**: 모두 OFF → 모두 ON 토글 시 "55× spread" 토스트 한 번 띄움.

**완료 기준**:
- [ ] 8 case 모두 즉시 (<50ms)
- [ ] base 1.84% 대비 lift 자동 계산
- [ ] 0.21% / 11.5% 양 극단에서 toast

---

### §05 LEAKAGE — `LeakageAudit.tsx` (신규)

**목적**: leakage_audit.py 결과 시각화 + obs_days 일화.

```tsx
type AuditResult = {
  total: number;          // 21
  passed: number;         // 21
  categories: Array<{
    id: "A" | "B" | "D" | "E" | "F" | "H" | "K" | "L" | "M";
    title_ko: string;
    checks: Array<{ name: string; pass: boolean; detail: string }>;
  }>;
  obs_days_story: {
    roc_alone: number;       // 0.939
    n_features_dropped: number; // 39
    pr_auc_before: number;   // 0.37
    pr_auc_after: number;    // 0.265
  };
};
```

데이터: 정적 inline (audit는 매번 재현되는 결정적 결과).

레이아웃:
```
┌────────────────────────────────────────────────────┐
│  [ ✓ 21/21 emerald counter big ]                   │
├────────────────────────────────────────────────────┤
│  [ accordion 9 categories ]                        │
│    > A. 사용자별 시간 cutoff (3 ✓)                 │
│    > B. Leak event 블랙리스트 (5 ✓)                │
│    > F. Cutoff-길이 leak 발견·제거 (2 ✓) ⚠ 별표    │
│    ...                                             │
├────────────────────────────────────────────────────┤
│  [ obs_days story 카드 — amber ]                   │
│    "관찰 기간 길이"만으로 ROC 0.939                 │
│    → 39 features 추가 제거                         │
│    → PR-AUC 0.37 → 0.265 (정직성 비용 -28%)        │
└────────────────────────────────────────────────────┘
```

**Bonus 버튼**: `[Download leakage_audit.py]` → `/leakage_audit.py` raw (`public/`에 복사).

**완료 기준**:
- [ ] 21/21 카운터 mount 시 count-up
- [ ] accordion 클릭 시 framer-motion height transition
- [ ] obs_days 카드 항상 펼쳐진 상태 (강조)

---

### §06 MODEL COMPARISON — `ModelComparison.tsx` (신규)

**목적**: 5개 모델 head-to-head + PR curve overlay.

```tsx
type ModelMetrics = {
  rows: Array<{
    name: string;                   // "Calibrated ensemble"
    label_short: string;            // "Ensemble"
    pr_auc: number;
    roc_auc: number;
    brier: number | null;           // majority는 null
    top5_precision: number;
    top5_recall: number;
    lift_vs_random: number;
    is_champion: boolean;
  }>;
  pr_curves: Record<string, { recall: number[]; precision: number[] }>;
  calibration: {
    uncalibrated: { mean_pred: number[]; frac_positive: number[] };
    calibrated:   { mean_pred: number[]; frac_positive: number[] };
  };
};
```

API: `GET /api/model-comparison` (백엔드에서 캔버스 `metrics_v3` + `Compare Models` 합쳐 반환)

레이아웃:
```
┌──────────────────────────────┬────────────────────┐
│  [ comparison table ]         │  [ PR curve plot ] │
│  6 rows · clickable           │  hovered = bold    │
│  champion row glows           │  random = dashed   │
│                                │                    │
│                                ├────────────────────┤
│                                │  [ calibration ]   │
│                                │  reliability diag  │
└──────────────────────────────┴────────────────────┘
```

**라이브러리**: SVG 직접. 곡선 1개당 ~50점 polyline.

**완료 기준**:
- [ ] 표 row hover → 해당 PR curve가 굵어지고 나머지 fade
- [ ] champion row violet glow + ★
- [ ] calibration plot에 y=x 대각선 + uncalibrated 곡선(앰버 점선) + ours(에메랄드 실선)

---

### §07 TOP-K SIMULATOR — `TopKSimulator.tsx` (★ 핵심)

**목적**: 슬라이더로 캠페인 ROI 즉시 계산. **이 섹션이 사이트 차별점**.

```tsx
type TestPredictions = {
  scores: number[];          // length 7437, sorted desc
  labels: number[];          // 0/1, aligned with scores (sorted desc by score)
  base_rate: number;         // 0.0249
};
```

API: `GET /api/predictions/test` (응답 ~50KB JSON. 30분 캐시)

UI:
```tsx
<div className="space-y-6">
  <Slider
    min={0.005} max={1} step={0.005}
    value={k}
    onChange={setK}
    marks={[0.01, 0.05, 0.1, 0.2, 0.5, 1]}
  />

  <div className="grid grid-cols-3 gap-4">
    <Stat label="타겟 인원"    value={Math.ceil(n * k)} />
    <Stat label="결제자 포착"  value={caught(k)} />
    <Stat label="적중률"       value={precision(k)} fmt="%" />
  </div>

  <div className="grid grid-cols-2 gap-4">
    <Card title="모델 사용 시"  caught={caught(k)}      revenue={ltv * caught(k) - cost * n * k} />
    <Card title="무작위 비교"   caught={Math.ceil(n*k*r)} revenue={...} />
  </div>

  <CostInputs ltv={ltv} setLtv={setLtv} cost={cost} setCost={setCost} />
</div>
```

**계산 함수** (client-side):
```ts
function caught(k: number, scores: number[], labels: number[]) {
  const cut = Math.ceil(scores.length * k);
  return labels.slice(0, cut).reduce((a, b) => a + b, 0);
}
function precision(k: number, ...) { return caught(k, ...) / Math.ceil(scores.length * k); }
```

scores는 이미 desc sorted라 slice만 하면 됨 → `<10ms` 응답.

**비용 인풋 기본값**: LTV $200, 메일 $0.10/통.

**완료 기준**:
- [ ] 슬라이더 0.5%~100% (로그 스케일)
- [ ] 모든 계산 client (네트워크 X)
- [ ] LTV / 비용 인풋 직접 수정
- [ ] 모델 vs 무작위 좌우 카드 동시 갱신

---

### §08 LIVE PREDICT — `LivePredict.tsx` (보강)

**현재**: row index → 확률.

**추가**:
1. 그 사용자의 funnel stage 표시
2. Top-3 contributing features (SHAP 또는 logit coef)
3. "결제자 한 명 보기" / "비결제자 한 명 보기" 단축 버튼

```tsx
// 응답 타입 확장 — 백엔드 /predict/sample/{idx}에 추가 필드 필요:
type PredictSample = {
  idx: number;
  n_test: number;
  upgrade_probability: number;
  actual_label: number;
  feature_count: number;
  // NEW:
  user_stage: string;                     // "4.UsedAI"
  user_stage_label_ko: string;            // "AI 사용"
  top_features: Array<{
    name: string;                         // "n_credits_used_1h"
    name_ko: string;                      // "첫 1시간 크레딧 사용"
    contribution: number;                 // signed
  }>;
};
```

**완료 기준**:
- [ ] stage 뱃지 (`8.Upgraded` 핑크 / `9.AtRisk@*` 앰버 등)
- [ ] top-3 features bar chart (signed: positive=violet, negative=rose)
- [ ] "결제자 보기" 버튼 → 미리 정해둔 idx 5개 중 random
- [ ] 키보드 ↑↓ 화살표로 idx 증감

---

### §09 PLAYBOOK — `PlaybookList.tsx` (신규)

**목적**: 7-action 정렬된 list.

```tsx
type Playbook = {
  actions: Array<{
    rank: number;
    title_ko: string;
    target_users: number;
    expected_rate: number;
    lift: number;
    icon: string;             // emoji
    message_ko: string;
    is_top: boolean;
  }>;
  total_target: number;       // 1300
  total_pct: number;          // 0.074
};
```

API: `GET /api/playbook` (백엔드는 `business_playbook.md` 파싱 또는 hardcode).

UI: 행 list, 각 행에 `<LiftBar lift={...} max={20} />` 가로 막대.

상위 3개는 violet glow + 메시지 카피 직접 노출.

**완료 기준**:
- [ ] 7행 정렬 (rank asc)
- [ ] LiftBar 색은 violet→pink 그라디언트
- [ ] Top-3에만 메시지 카피 표시, 나머지는 클릭 시 펼침

---

### §10 STRATEGY GALLERY — 보강

**현재**: 14 segments × 3 actions 카드.

**추가**:
1. 카드 메시지에 `[Copy]` 버튼 (clipboard API)
2. (P2) §02 sankey 클릭과 segment-pick 연동 — `segmentSelectedAtom` (jotai) 또는 query param

**완료 기준**:
- [ ] copy 버튼 클릭 시 toast 1초
- [ ] (P2) URL hash로 segment 선택 상태 sync

---

### §11 CANVAS DAG — 위치만 변경

**변경**: `<CanvasDAGLazy />`를 page.tsx 하단으로 이동.

**보강 (P2)**: `BlockDetail.tsx`에 "이 블록 결과는 §N 섹션에서 보임" 링크.

```ts
const BLOCK_TO_SECTION: Record<string, { id: string; label: string }> = {
  "Funnel v4":          { id: "02", label: "the funnel" },
  "Train Model v3":     { id: "06", label: "model comparison" },
  "Build Strategies":   { id: "10", label: "AI strategist" },
  "Insights Card":      { id: "END", label: "summary" },
  // ...
};
```

---

### §END INSIGHTS CARD — 보강

링크 한 줄 추가 + finale tone:

```tsx
<footer className="mt-8 flex flex-col items-center gap-3 border-t border-slate-800/60 pt-10 text-center font-mono text-xs text-slate-500">
  <div>
    <a href="https://github.com/anmemol-beta/zerve-odsc-ai-datathon">github</a>
    {" · "}
    <a href="https://anmemol-beta.github.io/zerve-odsc-ai-datathon/">live demo</a>
    {" · "}
    <a href="/video">3-min video</a>
  </div>
  <div>Zerve canvas · 39 blocks · 62 edges · beta-zerve.hub.zerve.cloud</div>
</footer>
```

---

## 3. API 계약 (백엔드 신규 엔드포인트)

`zerve_deploy/main.py`에 추가:

```python
from fastapi import HTTPException
import json

# 모든 신규 엔드포인트는 이 패턴:
# 1) 캔버스 변수 우선 (zerve.variable)
# 2) 실패 시 _FALLBACK_* 상수
# 3) 응답에 source: "live" | "fallback" 메타 포함

@app.get("/api/hero-stats")
def hero_stats():
    try:
        return {
            "events_total": _var("Example Dataset", "events_count"),
            "users_total": _var("Example Dataset", "users_count"),
            "upgraders_total": _var("Example Dataset", "upgraders_count"),
            "base_rate": _var("Build Features v3", "base_rate_v3"),
            "random_pr_auc": _var("Build Features v3", "base_rate_v3"),
            "ensemble_pr_auc": 0.2645,   # from Train Model v3
            "source": "live",
        }
    except Exception:
        return {**_FALLBACK_HERO, "source": "fallback"}

@app.get("/api/eda-lifts")
def eda_lifts():
    # event_lift_table.csv를 inline으로 반환
    ...

@app.get("/api/funnel-stages")
def funnel_stages():
    # stage_distribution_v4 + STAGE_LABEL_KO 조인
    ...

@app.get("/api/post-upgrade")
def post_upgrade():
    # user_features_v4에서 active/at_risk/churned 카운트
    ...

@app.get("/api/transitions")
def transitions():
    # transition_v4_counts.csv → 정규화된 확률
    ...

@app.get("/api/predictions/test")
def predictions_test():
    # score desc sort + label aligned
    ...

@app.get("/api/playbook")
def playbook():
    # business_playbook.md를 파싱해서 7-action 반환
    ...
```

캐시: `@lru_cache` 또는 module-level dict + `/admin/reload`로 invalidate.

응답 모두 JSON, 200 OK, `source` 필드 필수.

---

## 4. 공유 유틸 / 컴포넌트

```
web/lib/
├── api.ts                  # 기존 + 신규 엔드포인트 메서드 7개
├── canvas.ts               # 기존
├── stage-labels.ts         # NEW — STAGE_LABEL_KO map
├── format.ts               # NEW — pct(), num(), lift() formatters
├── fallbacks.ts            # NEW — 모든 inline 폴백 데이터 모음
└── colors.ts               # NEW — accent token 정의
```

```ts
// lib/format.ts
export const fmtPct = (n: number, digits = 1) =>
  `${(n * 100).toFixed(digits)}%`;
export const fmtNum = (n: number) =>
  n.toLocaleString("ko-KR");
export const fmtLift = (n: number) =>
  n >= 10 ? `${Math.round(n)}×` : `${n.toFixed(1)}×`;
```

```ts
// lib/colors.ts
export const ACCENT = {
  pink:    { text: "text-pink-300",    bg: "bg-pink-500/10",    border: "border-pink-400/40" },
  violet:  { text: "text-violet-300",  bg: "bg-violet-500/10",  border: "border-violet-400/40" },
  cyan:    { text: "text-cyan-300",    bg: "bg-cyan-500/10",    border: "border-cyan-400/40" },
  amber:   { text: "text-amber-300",   bg: "bg-amber-500/10",   border: "border-amber-400/40" },
  emerald: { text: "text-emerald-300", bg: "bg-emerald-500/10", border: "border-emerald-400/40" },
  rose:    { text: "text-rose-300",    bg: "bg-rose-500/10",    border: "border-rose-400/40" },
} as const;
```

```tsx
// components/shared/StatCard.tsx
type Props = {
  big: string;
  label: string;
  detail?: string;
  accent?: keyof typeof ACCENT;
};
export default function StatCard({ big, label, detail, accent = "pink" }: Props) {
  const c = ACCENT[accent];
  return (
    <div className={`glass rounded-xl p-5 border ${c.border}`}>
      <div className={`text-3xl font-bold ${c.text}`}>{big}</div>
      <div className="mt-1 text-xs uppercase tracking-wider text-slate-400">{label}</div>
      {detail && <div className="mt-2 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}
```

```tsx
// components/shared/LiftBar.tsx
export default function LiftBar({ lift, max }: { lift: number; max: number }) {
  const pct = Math.min(lift / max, 1);
  return (
    <div className="h-2 w-full rounded-full bg-slate-800">
      <div
        className="h-full rounded-full bg-gradient-to-r from-violet-500 to-pink-500"
        style={{ width: `${pct * 100}%` }}
      />
    </div>
  );
}
```

---

## 5. 카피 톤 가이드 (필수)

| ❌ 쓰지 말 것 | ✅ 쓸 것 |
|---|---|
| Train Model v3 | calibrated ensemble · 캘리브레이션 앙상블 |
| Funnel v4 | 15-stage funnel · 15단계 퍼널 |
| Build Features v3 | feature pipeline · 피처 파이프라인 |
| Validate Features v3 | feature audit · 피처 자동 감사 |
| 8.Upgraded | 결제 활동중 · active paying user |
| 9.AtRisk@Upgraded | 결제 후 위험 · at-risk after upgrade |
| 9.Churned@Upgraded | 결제 후 이탈 · churned after upgrade |
| n_credits_used_1h | 첫 1시간 크레딧 사용 |
| agent_first | AI 먼저 사용 |
| is_power_engaged | 꾸준한 사용자 (7일+) |
| PR-AUC 0.265 | 무작위 대비 10.6배 정확 |
| Brier 0.022 | 확률 정확도 4배 개선 |

원칙: **약어/내부 코드명을 쓰지 말고, 그것이 의미하는 *행동* 또는 *비교 배수*로 번역.**

`stage-labels.ts` + `format.ts`에 매핑 박아두고 모든 컴포넌트에서 그것만 import.

---

## 6. 모바일 반응형 체크리스트

| 섹션 | 데스크탑 | 모바일 (sm) | 핸들링 |
|---|---|---|---|
| Hero | 4-stat row | 2×2 grid | `grid-cols-2 lg:grid-cols-4` |
| 01 | 3-col | 1-col | `lg:grid-cols-3` |
| 02 | sankey + 도넛 옆 | sankey 위 도넛 아래 | `flex-col lg:flex-row` |
| 03 | 8×8 heatmap | 가로 스크롤 | `overflow-x-auto` |
| 04 | 토글 좌 결과 우 | toggle 위 결과 아래 | `lg:grid-cols-[2fr_3fr]` |
| 05 | accordion + 카드 옆 | stack | `lg:grid-cols-2` |
| 06 | 표 + curve 옆 | 표 위 curve 아래 | `lg:grid-cols-2` |
| 07 | 슬라이더 + 카드 옆 | stack | 동일 |
| 08 | input 좌 result 우 | stack | 기존 그대로 |
| 09 | 7-row list | 동일, 메시지 collapsed | `lg:` 분기 |
| 10 | 14-card grid | 가로 스크롤 carousel | `overflow-x-auto snap-x` |
| 11 | full DAG | 전체 + ReactFlow built-in pan/zoom | 기존 그대로 |

iPhone 14 (390×844)에서 모든 섹션이 위→아래 스크롤로 자연스럽게 흐르는지 확인.

---

## 7. 구현 순서 (8시간 기준)

| 시간 | 작업 |
|---|---|
| **0:00–0:30** | `stage-labels.ts`, `format.ts`, `colors.ts`, `fallbacks.ts` + `StatCard`/`LiftBar`/`SectionHeader` |
| **0:30–1:30** | Hero 4 stat 카드 갱신 + DiscoveryCards (§01) |
| **1:30–3:00** | FunnelView (§02 sankey + 도넛) — 가장 복잡 |
| **3:00–4:00** | LeakageAudit (§05) + PlaybookList (§09) — 정적 위주 |
| **4:00–5:30** | ModelComparison (§06) + TransitionHeatmap (§03) |
| **5:30–7:00** | TopKSimulator (§07) ★ |
| **7:00–7:30** | SignalCombo (§04) |
| **7:30–8:00** | LivePredict 보강 (§08) + page.tsx 재배치 + 모바일 검증 |

P0(§Hero, §01, §02, §05, §06, §09)만 5h 안에 끝나면 발표 임팩트 80% 확보.

---

## 8. 백엔드 작업 (병렬)

`zerve_deploy/main.py`에 5개 엔드포인트 + 인라인 폴백.

| 엔드포인트 | 데이터 출처 | 폴백 |
|---|---|---|
| `/api/hero-stats` | 캔버스 + 하드코드 | 인라인 |
| `/api/eda-lifts` | `event_lift_table.csv` | 인라인 (top 6) |
| `/api/funnel-stages` | `Funnel v4`.`stage_distribution_v4` | 인라인 |
| `/api/post-upgrade` | `Funnel v4`.`user_features_v4` | 인라인 (221/74/28) |
| `/api/transitions` | `transition_v4_counts.csv` | 인라인 (8×8) |
| `/api/predictions/test` | `Train Model v3`.`ensemble_proba_v3` + `y_v3_test` | 30KB 인라인 |
| `/api/playbook` | `business_playbook.md` parsed | 인라인 (7 actions) |

모든 응답에 `source: "live" | "fallback"` 메타 → 프론트에서 versionBadge에 표시.

캐시: `@functools.lru_cache(maxsize=1)` + `/admin/reload`로 invalidate.

---

## 9. 완료 기준 (PR 리뷰용)

### 기능
- [ ] 11개 섹션 모두 데스크탑 / iPhone 14 / iPad 정상
- [ ] Hero 4 stat이 hero-stats endpoint live fetch
- [ ] §07 슬라이더가 client-only로 50ms 안에 갱신
- [ ] §05 accordion이 9 카테고리 모두 펼침/접힘
- [ ] §02 sankey + 도넛이 모바일 1-col에서 안 깨짐
- [ ] §08에 stage 뱃지 + top-3 SHAP bar
- [ ] §11 canvas 클릭 → 해당 섹션 anchor scroll

### 품질
- [ ] TypeScript strict, no `any`
- [ ] 모든 fetch에 `useQuery` + retry 1 + 5분 staleTime
- [ ] API 다운 시 inline 폴백 동작 (Network 탭에서 확인)
- [ ] 모바일에서 가로 스크롤 의도된 곳 외 0
- [ ] Lighthouse a11y > 90, performance > 80

### 카피
- [ ] `web/`에서 `v3`/`v4`/`Build Features v3` grep 결과 0건 (캔버스 블록 이름 외)
- [ ] 모든 stage 라벨이 한국어
- [ ] 모든 모델/feature 이름이 행동/배수로 번역됨

### 빌드
- [ ] `npm run build` 통과
- [ ] `npm run lint` 통과
- [ ] GitHub Pages export 동작

---

## 10. 의존성 추가

```bash
cd web && npm i d3-sankey @types/d3-sankey jotai
```

`d3-sankey`는 §02 sankey, `jotai`는 segment-pick state sync(P2).

기존 의존성 그대로 활용:
- `framer-motion` — 모든 애니메이션
- `@tanstack/react-query` — fetch 전부
- `reactflow` — §11
- `tailwindcss` — 스타일
- 차트 라이브러리는 추가 X (recharts/chart.js 안 씀, SVG 직접)

---

## 11. 참고 (이미 존재)

| 자원 | 위치 |
|---|---|
| 영상 storyboard | `docs/video_storyboard.html` |
| Leakage audit 결과 | `/Users/hunjunsin/Desktop/zerve/leakage_audit.py` (실행하면 21/21) |
| 분석 리포트 | `docs/analysis_report.md` |
| 모델 리포트 | `docs/prediction_report.md` |
| 비즈니스 playbook | `docs/business_playbook.md` |
| 캔버스 정의 | `5319f3dc-9b9d-449e-838d-dcac9f13a133/canvas.yaml` + `Development/layer.yaml` |
| 기존 프론트 진입점 | `web/app/page.tsx` |

---

## 12. 질문 생기면

- 데이터 계약 모호 → `docs/prediction_report.md` + `docs/analysis_report.md`에 모든 숫자 출처
- 캔버스 변수 이름 모호 → `5319f3dc.../Development/{블록 이름}.py` 끝부분 (output 변수)
- 카피 톤 결정 못함 → §5 표 보고 행동/배수로 번역
- API down 시 폴백 데이터 출처 → `lib/fallbacks.ts`에 모음
- 색상 결정 못함 → §0 원칙 7번 + `lib/colors.ts`
