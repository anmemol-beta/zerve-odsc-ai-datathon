# Zerve Insight Platform — 로드맵 & 진척 현황
> 마감: **2026-04-30 10:00** · 라이브: <https://beta-zerve.hub.zerve.cloud>

이 문서는 *지금 어디까지 와 있고*, *어디로 가고 있고*, *남는 시간에 뭘 더 하면 좋은지* 한 페이지로 보는 단일 진실 문서입니다. 다른 문서들은 깊은 내용이고, 이 문서는 *내비게이션*입니다.

| 문서 | 다루는 것 |
|---|---|
| [`architecture.md`](./architecture.md) | 6-layer 플랫폼 설계 (계획) |
| [`analysis_report.md`](./analysis_report.md) | EDA + funnel v1→v4 + transition 분석 결과 |
| [`prediction_report.md`](./prediction_report.md) | Mission 1 모델 v1→v3 detail + leakage 추적 |
| [`business_playbook.md`](./business_playbook.md) | 모델 weight → 비즈니스 액션 7개 |
| [`README.md`](./README.md) | 캔버스/배포 사용법 |
| **`ROADMAP.md` (이 문서)** | **전체 진척 + 남은 일 + 보완 후보** |

---

## 1. 한 줄 비전

> **사용 데이터 → ML 예측 + 9-stage funnel → K2 Reasoning LLM이 "어떤 segment에 어떤 캠페인을 어떻게 보내야 ROI 최대인지" 추천하는 인터랙티브 플랫폼.**
> 사용자는 PM/마케팅 리드. *모델 결과를 직접 비즈니스 결정으로* 변환하는 게 핵심 차별점.

---

## 2. PDF Rubric vs 우리 진척

| 항목 | 점수 | 진척 | 자체 평가 (예상 점수) |
|---|---:|---|---:|
| Data Understanding & Feature Engineering | 15 | ✅ EDA + 217 feature matrix + window 설계 | 13~15 |
| Handling of Leakage | 15 | ✅ 25-event blacklist + cutoff + 시간 split + observation_days leak 발견·제거 | 13~15 |
| **Predictive Model Quality** | **25** | ✅ v3 ensemble (PR-AUC 0.27, calibrated) — 캔버스 통합 완료 | 22~25 |
| **Funnel Design & Stage Definitions** | **25** | ✅ v4 15-stage + post-upgrade lifecycle (Time-Aware) | 24~25 |
| **Transition Logic & Behavioral Modeling** | **25** | ✅ 8x8 transition matrix + 사용자 경로 + 60일 cohort 분석 | 24~25 |
| Insights, Recommendations & Business Impact | 5 | ✅ playbook + LLM 14-segment strategies | 5 |
| Communication & Presentation | 5 | 🟡 라이브 사이트 ✓, 영상/리포트 ⬜ | 3~5 |
| **합계 (max 100)** | | | **104~115 → "100" cap** |

→ **Rubric 자체는 전 항목 만점 노릴 수 있는 상태.** 남은 손실 위험은 영상/리포트 + 라이브 통합 깔끔도.

---

## 3. 현재까지 완료된 것 (커밋 순)

### 🟢 데이터 사이드 — 분석 / 모델 / LLM

| # | 산출물 | 파일 | 상태 |
|---|---|---|---|
| 1 | EDA + leakage 후보 | `analyze_eda.py`, `analyze_compare.py`, `event_lift_table.csv` | ✅ |
| 2 | v1 funnel | `analyze_funnel.py` (root) | ✅ archive |
| 3 | v2 funnel (Integration 확장) | 동상 | ✅ archive |
| 4 | **v3 funnel (5가지 보완)** | `funnel_v3.py` | ✅ |
| 5 | **v4 funnel (15-stage + post-upgrade lifecycle)** | `funnel_v4.py` + 캔버스 `Funnel v4.py` | ✅ |
| 6 | Transition matrix v4 | `analyze_transitions_v4.py`, `transition_v4_counts.csv` | ✅ |
| 7 | Mission 1 features (217 cols) | `mission1_features.py`, `feature_matrix.parquet` | ✅ |
| 8 | Mission 1 model v2 (leakage 정정) | `mission1_model_v2.py` | ✅ |
| 9 | **Mission 1 model v3 (calibrated ensemble)** | `mission1_model_v3.py` + 캔버스 `Train Model v3.py` | ✅ |
| 10 | Business playbook | `business_playbook.md`, `business_insights.py` | ✅ |
| 11 | **K2-Think LLM client** | `llm_client.py` + `.env`(gitignored) | ✅ |
| 12 | **SegmentStrategy 배치 (14 segments × 3 actions)** | `prompts.py`, `build_strategies.py`, `web/public/data/strategies.json` | ✅ |
| 13 | 캔버스 통합 (Funnel v4 + Build Features v3 + Train Model v3) | `5319f3dc.../Development/*.py` + `canvas.yaml` + `layer.yaml` | ✅ |

### 🟢 프론트 / 배포 (팀원 작업)

| # | 산출물 | 상태 |
|---|---|---|
| 14 | Next.js 14 정적 export, react-three-fiber, d3-sankey | ✅ |
| 15 | Hero, HeadlineCards, FunnelExplorer, Manifold3D, UserLookup | ✅ |
| 16 | CohortTimeline, VersionBadge | ✅ (방금 main에서 받음) |
| 17 | Zerve Custom Deployment (`main.py` + `app.zip` + `/admin/refresh`) | ✅ live |
| 18 | `build-archive.sh` 한 줄 빌드 + push | ✅ |
| 19 | `export-data.py` 캔버스 → JSON 데이터 export | ✅ |

---

## 4. 진행 중 / 남은 일 (마감까지)

### 🟡 진행 중

| 항목 | 상태 | 다음 액션 |
|---|---|---|
| `strategies.json`을 라이브 사이트에 반영 | 데이터 파일은 만들어졌지만 **아직 frontend에서 안 읽음** | (A) 또는 (B) 결정 후 build-archive.sh |

### ⬜ 남은 일 — 우선순위 순

#### P0 (필수 — 채점 직결)

1. **3분 영상** (max 3분, 폰 세로)
   - 시나리오: 라이브 사이트 시연 + segment 클릭 → LLM 추천 노출 → 모델 metric 강조
   - 핵심 메시지 3개: ① v3 ensemble PR-AUC 0.27 (베이스 1.84% 대비 14x), ② v4 funnel 15-stage + post-upgrade lifecycle, ③ K2 LLM이 모델 weight를 직접 액션으로 변환
   - 도구: QuickTime (Mac) 또는 폰 화면 녹화

2. **Zerve Report** (Zerve agent로 작성)
   - PDF 명시: *"approach + results + funnel design and logic (stage/transition rules) + business implications"*
   - 입력: `analysis_report.md` + `prediction_report.md` + `business_playbook.md` + `architecture.md` 통합 요약
   - 30분 작업 예상

3. **프론트엔드 LLM strategies 노출** ★ 차별화 포인트
   - 옵션 A: `ActionCards.tsx` — Hero 섹션 아래 "Top 3 weekly campaigns" 카드 (top-rank 액션 3개)
   - 옵션 B: `SegmentStrategyDrawer.tsx` — FunnelExplorer 단계 클릭 시 슬라이드 인 (해당 segment 14개 중 매칭)
   - 최소: A 1개 컴포넌트 (60-90분)
   - 풀: A + B (2-3시간)

4. **README 갱신** — v3 모델 metric + LLM 통합 + segment strategies 언급
   - 현재 README는 팀원 v1 모델 결과 기준 (PR-AUC 0.067, recall@5% 50% but 6 positives)
   - v3 메인으로 노출하고 v1은 "alternative cohort-based view" 정도로

#### P1 (중요 — 시간 남으면)

5. **`build-archive.sh` + admin/refresh** — 라이브 사이트에 우리 작업 반영
   - 현재 라이브 사이트는 어제 빌드된 app.zip (v3 metric 못 봄)
   - `./build-archive.sh && curl -X POST .../admin/refresh` 한 번이면 zero-downtime 갱신

6. **`export-data.py`에 v3/v4 출력 추가**
   - 현재 export는 팀원 파이프라인의 v1/v2 funnel을 읽음
   - v3 metric + v4 funnel을 추가 export하면 frontend에서 표시 가능

7. **K2 LLM에 한국어 메시지도 검증** (현재 message_ko 필드 들어있음)

#### P2 (보너스 — 채점 +α)

8. **WhatIf Calculator** — 사용자가 "X% off promo to AtRisk@Engaged" 같은 가정 입력 → K2가 expected ROI 추정
9. **UserLookup에 K2-driven 1:1 추천** — 사용자 ID 입력 → 단일 사용자 메시지 카피 + sales talking points
10. **LLM Chat sidebar** — 자유 질의 (SSE stream)

---

## 5. 보완하면 좋은 것 (제출 후 또는 시간 남으면)

### 모델 측면
- **Activity hour features 추가** (`activity_hour_min/mean/max`) — 다른 LLM 평가에서 핵심 신호로 지목된 것. 우리 217 feature에 시간대 신호 없음. PR-AUC +0.5~1pt 가능.
- **Optuna hyperparameter tuning** — 현재 default. 30~60분 작업, +0.01~0.03 PR-AUC.
- **LightGBM 추가 (4번째 base model)** — 현재 XGB+RF+HGB ensemble. marginal 개선.
- **Stacking with logreg meta-learner** — 단순 평균 대신 학습 가능한 가중치.
- **Time-series CV** — 현재 cohort split만. 더 robust하려면 forward-walk cross-validation.

### Funnel 측면
- **Funnel 단계별 demographics breakdown** — 각 stage에 어떤 사용자가 모이는지 (현재는 strategies.json 안에 부분적으로만)
- **Stage 3 (Created) 정의 재검토** — highest=3 사용자가 3명뿐. transit-only stage라 funnel 시각화에서 어색할 수 있음.
- **Stage rank vs time progression** — Stage 4 (UsedAI)가 Stage 3 (Created)보다 시간상 *먼저* 도달. 단계 번호 = 기능 깊이 순서임을 보고서에 더 명확히.

### LLM 측면
- **Cache invalidation 전략** — 현재 prompt 변경 시만 새 호출. 데이터 변경 시 자동 재실행 트리거 필요.
- **GPT-4 fallback** — K2 응답 schema mismatch 시 백업.
- **Prompt 1, 2, 3 각각 성능 평가** — A/B로 prompt 변형 비교.
- **Vector DB RAG** — 현재 keyword RAG. playbook이 커지면 vector 필요.
- **Multi-turn LLM Chat** — 현재 단일 호출만.

### 플랫폼 측면
- **사용자 인증** — 현재 public demo. production은 로그인 필요.
- **모델 retraining 자동화** — 매월 새 cohort로 재학습 → 자동 배포.
- **A/B test 인프라** — 우리가 추천한 캠페인의 실제 lift 측정.
- **Drift monitoring** — 모델 score 분포가 시간에 따라 어떻게 변하는지.
- **Feature store** — 지금은 parquet 파일. production은 BigQuery/Snowflake 등.

### 프론트엔드 측면
- **모바일 최적화** — 현재 데스크탑 우선
- **다국어 (영/한 토글)** — LLM은 둘 다 만들었지만 UI는 영어
- **PDF export** — 한 segment의 strategy를 PDF로 다운로드
- **Slack/email 통합** — 추천 액션을 직접 메시지로 전송

---

## 6. 알려진 위험 (Risk Register)

| 위험 | 영향 | 대응 |
|---|---|---|
| K2 응답 schema 깨짐 (이전 1회 발생, 수정됨) | strategies.json 일부 비어있음 | shape validator + retry 적용 ✅ |
| `lightgbm` 없으면 캔버스 일부 블록 실행 안 됨 | local dev 시 — 클라우드 OK | uv sync + brew libomp 명시 ✅ |
| `app.zip` 갱신 누락 | 라이브 사이트 stale | `./build-archive.sh` 한 번 |
| K2 API 다운 | 빌드 타임 호출 실패 | LLM 캐시 (이미 있는 호출은 OK), 재빌드 시만 영향 |
| 마감 직전 main 충돌 | merge 부담 | 자주 pull, feature branch는 짧게 |
| 영상 시간 초과 | 채점 감점 | 3분 엄수 — 60초 demo + 90초 metric + 30초 결론 |
| 모델 결과 두 종류 (v1 vs v3) 혼동 | 채점관 confused | README + report에서 v3 메인으로 명시 |

---

## 7. 의사결정 대기 항목

| # | 결정 | 옵션 | 권장 |
|---|---|---|---|
| D1 | LLM strategies 노출 형태 | A=ActionCards top3 / B=SegmentStrategyDrawer 14개 / C=둘다 | **A 우선** (시간 부족) |
| D2 | UI 언어 | 영어 only / 한국어 only / 토글 | **영어 only** (ODSC 미국) |
| D3 | 영상 한국어 vs 영어 | KR / EN | **EN** (채점관) |
| D4 | 모델 v1 (팀) vs v3 (우리) main으로 | v1 / v3 / 둘다 | **v3 메인 + v1 부록** |
| D5 | 라이브 사이트 어디까지 갱신 | hot reload만 / app.zip 다시 빌드 / canvas 재실행 | **app.zip 다시 빌드 후 hot reload** |

---

## 8. 시간 예산 (현재 ~9~12시간 남음 가정)

| 작업 | 예상 시간 | 우선순위 |
|---|---:|---|
| ActionCards 컴포넌트 + 빌드 | 1.5h | P0 |
| README 갱신 (v3 메인) | 0.5h | P0 |
| `build-archive.sh` 1회 | 5min | P0 |
| Zerve Report 작성 | 1h | P0 |
| 3분 영상 녹화 + 편집 | 1.5h | P0 |
| (P0 합계) | **4.5h** | |
| `export-data.py` v3/v4 통합 | 1h | P1 |
| SegmentStrategyDrawer | 1.5h | P1 |
| Activity hour features → v3.1 | 1h | P1 |
| (P0 + P1 합계) | **8h** | |
| WhatIf calculator | 2h | P2 |
| UserLookup에 K2 1:1 추천 | 2h | P2 |

→ **P0만 4.5h. 9시간 있으면 P0 + P1 모두 가능.**

---

## 9. Submission Requirements 체크리스트 (PDF에서)

- [x] **Zerve Project link** — 캔버스 v3/v4 블록 통합 완료, runnable
- [x] **Live demo** — https://beta-zerve.hub.zerve.cloud (4-section dashboard live)
- [ ] **3-minute video** — 미작성
- [ ] **Zerve Report** — 미작성 (Zerve agent 사용 권장)
- [x] (Bonus) **Deployment artifact** — 라이브 사이트 = 자체 deployment

---

## 10. 한 눈 요약 — "내일 아침 10시 전까지"

```
✅ 분석 (EDA + funnel v4 + transition + model v3)
✅ K2 LLM client + 14 segment strategies JSON
✅ 캔버스에 우리 작업 통합 (3 신규 블록)
✅ 라이브 사이트 (팀원 작업, 4-section dashboard)

⬜ ActionCards 컴포넌트 → strategies.json 노출 (1.5h, ★ 차별화)
⬜ README v3 메인으로 갱신 (0.5h)
⬜ Zerve Report (1h, agent 사용)
⬜ 3분 영상 (1.5h)
⬜ build-archive.sh 1번 → 라이브 갱신
```

핵심 메시지 한 줄:
> **"우리는 EDA → 9-stage funnel → calibrated ensemble model → K2 LLM 추천을 한 파이프라인에 묶고, 그걸 라이브 인터랙티브 플랫폼으로 노출했다."**

---

*마지막 갱신: 2026-04-30*
*다음 갱신 시점: 영상 녹화 직전 (P0 항목 모두 완료 후)*
