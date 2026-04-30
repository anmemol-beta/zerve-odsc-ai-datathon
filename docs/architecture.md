# Zerve Insight Platform — Architecture
## ML 예측 + Funnel + Kimi K2 Reasoning → Interactive Marketing Strategy Platform

> 작성일: 2026-04-29
> 목표: 제품/마케팅 팀이 *모델 + 현재 funnel 상태*를 보고, *어떤 segment에 어떤 캠페인을 해야 ROI 최대인지*를 LLM 추론으로 즉시 받는 인터랙티브 플랫폼.

---

## 0. 한 장 요약

```
┌──────────────────────────────────────────────────────────────────┐
│                     User (PM / Marketing Lead)                    │
│                              ↕ Web UI                             │
├──────────────────────────────────────────────────────────────────┤
│                  Next.js Frontend (web/)                          │
│  Hero KPI · Funnel Explorer · Manifold3D · UserLookup            │
│  + NEW: Segment Strategy · LLM Chat · Action Cards · ROI Calc    │
├──────────────────────────────────────────────────────────────────┤
│                     FastAPI (server.py)                           │
│                    REST + SSE for LLM stream                      │
├──────────┬─────────────────────┬──────────────────────────────────┤
│ ML Engine│   LLM Reasoning     │      Static Data Serving          │
│          │     (Kimi K2)       │                                   │
│ • v3 ens │ • Strategy prompts  │  • funnel_grid.json               │
│ • v4 fnnl│ • Playbook RAG      │  • manifold.json                  │
│ • SHAP   │ • JSON schema       │  • users.json (search)            │
└──────────┴─────────────────────┴──────────────────────────────────┘
              ↕                              ↕
┌──────────────────────────────────────────────────────────────────┐
│  Data Foundation (parquet/csv)                                    │
│  • feature_matrix.parquet  • funnel_v4_assignment.csv             │
│  • mission1_v3_predictions.csv  • business_playbook.md (RAG)      │
│  • zerve_events.csv (raw)                                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. 핵심 사용자 시나리오

### Persona A: 마케팅 리드
> "이번 주 캠페인 예산 5천만원. 어디 써야 가장 결제 많이 나올까?"

→ 들어와서: Hero KPI (현재 funnel 상태) → Action Cards (top 3 추천 캠페인) → 각 카드 클릭 → LLM이 *대상 세그먼트 명단 + 메시지 카피 + 예상 ROI* 보여줌.

### Persona B: 프로덕트 매니저
> "AtRisk@Engaged segment를 분석하고 싶다. 왜 떠났을까?"

→ Funnel Explorer → AtRisk@Engaged 클릭 → segment profile + 행동 패턴 → "LLM에게 물어보기" → Kimi K2가 SHAP feature + 행동 데이터 + playbook 기반 *가설 + 실험 제안*.

### Persona C: 세일즈
> "이 사용자(person_id) 영업 전화 가치 있나?"

→ UserLookup → person_id 입력 → 예측 점수 + funnel stage + 행동 history + LLM 추천 메시지 + sales talking points.

---

## 2. 아키텍처 5계층

### 📦 Layer 1 — Data Foundation (정적 산출물)

| 파일 | 내용 | 갱신 주기 |
|---|---|---|
| `feature_matrix.parquet` | 17,541 × 217 user features | 일/주 |
| `funnel_v4_assignment.csv` | per-user 15-stage label | 일/주 |
| `mission1_v3_predictions.csv` | per-user calibrated upgrade probability | 일/주 |
| `transition_v4_counts.csv` | 단계 간 transition matrix | 일/주 |
| `business_playbook.md` | LLM RAG context | 분기 |
| (raw) `zerve_events.csv` | source of truth | 일 |

**저장**: 로컬 + S3 (혹은 Zerve 자체 데이터셋)

### 🧠 Layer 2 — ML / Analytics Engine

| 모듈 | 역할 | 코드 |
|---|---|---|
| `funnel_v4.py::classify_users_v4` | (events, asof_ts) → 사용자별 stage 라벨 | 기존 |
| `mission1_v3 ensemble` | (X) → calibrated probability + ranking | 기존 |
| **NEW** `segment_analyzer.py` | (filter) → segment profile dict (size, stage_dist, top features, ROI estimate) | 신규 |
| **NEW** `shap_explainer.py` | (user_id) → top-5 contributing features per user | 신규 |

### 🤖 Layer 3 — LLM Reasoning (Kimi K2)

```
┌─────────────────────────────────────────┐
│   Kimi K2 (Moonshot reasoning LLM)      │
│   OpenAI-compatible API                 │
└─────────────────────────────────────────┘
            ↑                    ↑
            │                    │
┌──────────────────┐  ┌──────────────────┐
│  Prompt Builder  │  │  Response Parser │
│  • System role   │  │  • JSON schema   │
│  • Playbook RAG  │  │  • Validation    │
│  • Data injection│  │  • Fallback      │
└──────────────────┘  └──────────────────┘
            ↑
┌──────────────────────────────────────────┐
│  3가지 프롬프트 템플릿                       │
│                                          │
│  1. SegmentStrategy: segment 통계 +      │
│     playbook → 캠페인 추천 (top 3)         │
│  2. UserAction: 단일 user feature/score+ │
│     → 1:1 액션 + sales talking points    │
│  3. WhatIf: "X 시나리오 가정 시 ROI?"      │
└──────────────────────────────────────────┘
```

#### Prompt 1: Segment Strategy

```
[system]
You are a senior growth strategist for Zerve, an AI notebook product.
You receive segment data + business playbook (RAG context) + funnel state,
and recommend 3 prioritized marketing actions in JSON.

Return ONLY valid JSON matching schema:
{
  "segment_name": str,
  "size": int,
  "expected_conversion_lift": float,
  "actions": [
    {
      "rank": int,
      "title": str,
      "channel": "email" | "in_app" | "sales_call" | "ad",
      "message_copy": str,           # 한국어 if user_locale="ko"
      "target_filter": str,          # SQL-like filter
      "expected_uplift_pct": float,
      "estimated_cost_per_user": float,
      "estimated_roi": float,
      "rationale": str               # why this action, citing playbook
    },
    ... 2 more
  ],
  "risks": [str, str, str]           # what could go wrong
}

[user]
SEGMENT: {segment_name}
SIZE: {n_users}
CURRENT_CONVERSION: {observed_rate:.2%}
TOP_FEATURES (model importance): {top10_features}
FUNNEL_STAGE_DIST: {stage_dist}
DEMOGRAPHICS: {demo_summary}
META_FLAGS: {meta_flags}

PLAYBOOK CONTEXT (relevant excerpts):
{retrieved_playbook_chunks}

QUESTION: 이 segment에 어떤 캠페인을 해야 ROI 최대일까? Top 3 액션을 위 schema로.
```

#### Prompt 2: User Action

```
[system]
... given user features + score → 1:1 action + sales talking points

[user]
USER_ID: {anon_user_id}
PREDICTION_SCORE: {score:.3f}  (top {percentile:.1f}%)
FUNNEL_STAGE: {stage}
KEY_FEATURES_PRESENT: {top_features_active}
ACTIVITY_TIMELINE: {first_event} → {last_event}, {n_events} actions
SHAP_TOP5: {shap_explanation}
META: {agent_first, used_promo, onboarding_completed, ...}

QUESTION: 이 사용자에게 지금 무엇을 해야 하나?
출력: {channel, message, talking_points, expected_outcome, why}
```

#### Prompt 3: What-If

```
"AtRisk@Engaged 6,222명 중 2,000명에게 30% 할인 보낼 경우 expected lift?"
→ LLM이 historical conversion rate + 알려진 promo effect로 추정
```

#### RAG strategy (간단)

- `business_playbook.md` 를 ~12개 chunk로 나누고 (action별, segment별)
- 사용자 질의에서 segment 매칭 → 관련 chunk만 prompt에 주입
- vector DB 안 써도 됨 (작아서 keyword 매칭으로 충분)

#### LLM 호출 비용 관리

- **Pre-compute** (배치): 주요 segment 13개 (15 stages 중 의미 있는 것) × 1번 = 일 1회
- **On-demand** (실시간): UserLookup, 챗봇 — 캐시 적극 활용 (LRU 1000건)
- **Caching key**: hash(prompt + data version)
- 예상 비용: pre-compute 13건/일 × $0.05 = $0.65/일, on-demand 100건/일 × $0.03 = $3/일

### 🔌 Layer 4 — API (FastAPI)

기존 `server.py` (25 lines) 확장:

```python
# 정적 데이터 (이미 web/public/data로 export됨)
GET  /api/funnel/snapshot          # 전체 KPI + 단계 분포
GET  /api/funnel/transitions       # 8x8 transition matrix
GET  /api/funnel/sankey            # sankey 데이터

# 사용자/세그먼트
GET  /api/users/{user_id}          # 단일 사용자 풀 프로파일
GET  /api/users/search?q=...       # ID prefix 검색
POST /api/segments/analyze         # body: {filter} → segment summary

# ML
GET  /api/predict/{user_id}        # 단일 예측 + SHAP top-5
POST /api/predict/batch            # body: {user_ids[]} → predictions

# LLM (NEW)
POST /api/llm/segment-strategy     # body: {segment_filter} → 캠페인 3개
POST /api/llm/user-action          # body: {user_id} → 1:1 액션
POST /api/llm/whatif               # body: {scenario_text}
POST /api/llm/chat                 # body: {messages, context} → SSE stream

# Health/admin
GET  /api/health
POST /api/admin/refresh-cache
```

응답 형식: 모두 JSON. LLM 스트리밍은 SSE (Server-Sent Events).

### 🎨 Layer 5 — Frontend (Next.js + react-three-fiber)

**기존 컴포넌트** (팀원 작업):
- `Hero` — 메인 KPI 대시보드 (WebGL 셰이더 배경)
- `HeadlineCards` — 핵심 숫자 카드
- `FunnelExplorer` — 단계별 인터랙티브
- `Manifold3D` — 3D PCA 시각화
- `UserLookup` — 사용자 ID 검색

**신규 컴포넌트** (이번 작업):
| 컴포넌트 | 역할 |
|---|---|
| `ActionCards` | LLM이 추천한 top 3 캠페인 카드 (priority ordered) |
| `SegmentStrategy` | segment 클릭 시 LLM 전략 패널 (상세) |
| `LLMChat` | 자유로운 질의 응답 (sidebar drawer) |
| `ROICalculator` | "X명에게 캠페인하면 expected ROI" 계산기 |
| `RecommendationBadge` | UserLookup 안에 표시되는 1:1 추천 |

### 🚀 Layer 6 — Deployment

```
                 ┌──────────────────┐
   User browser  │ Vercel (frontend)│
                 └─────────┬────────┘
                           │ HTTPS
                 ┌─────────▼────────┐
                 │ FastAPI (Render  │
                 │  / Railway / AWS │
                 │  Lambda+API GW)  │
                 └─────────┬────────┘
                  ┌────────┴────────┐
                  │                 │
        ┌─────────▼──────┐  ┌──────▼───────┐
        │ S3 / static    │  │ Kimi K2 API  │
        │ data files     │  │ (Moonshot)   │
        └────────────────┘  └──────────────┘
```

배포 옵션:
- **A. Static + Serverless**: web → Vercel, server → AWS Lambda + API Gateway. 가장 저비용.
- **B. Full SaaS**: Render/Railway에 FastAPI + Next.js 모두. 단순.
- **C. Zerve native**: Zerve canvas에서 직접 export → "Zerve App" 형태로. 채점 보너스 +α.

---

## 3. Data Contract (JSON schema)

### Segment 응답
```json
{
  "segment_id": "atrisk_engaged",
  "label": "9.AtRisk@Engaged",
  "size": 457,
  "current_conversion": 0.0,
  "demographics": {
    "purpose": {"Personal Projects": 0.62, "Company Work": 0.21, ...},
    "device_type": {"Desktop": 0.74, "Mobile": 0.18, ...}
  },
  "top_features": [
    {"name": "n_agent_tool_24h", "median": 12, "vs_baseline": "5x"},
    ...
  ],
  "median_inactive_days": 58,
  "actions_recommended_by_llm": [...]
}
```

### User 응답
```json
{
  "user_id": "abc-123",
  "stage": "9.AtRisk@Upgraded",
  "score": 0.47,
  "score_percentile": 96.2,
  "shap_top5": [
    {"feature": "did_hit_credit_limit_7d", "shap": +0.23},
    {"feature": "n_agent_tool_24h", "shap": +0.18},
    ...
  ],
  "timeline": [...],   # 최근 20개 이벤트
  "recommendation": {
    "channel": "email",
    "message": "Pro 플랜으로 돌아오세요...",
    "talking_points": ["..."]
  }
}
```

---

## 4. 핵심 설계 결정 사항 (의견 필요)

| # | 결정 사항 | 옵션 | 권장 |
|---|---|---|---|
| **A** | LLM 응답 — 실시간 vs 배치 | (1) 모든 호출 실시간 (느림, 비쌈) <br> (2) Top segment pre-compute + on-demand | **(2)** 권장 — 메인 UX는 즉시, 깊은 질의는 stream |
| **B** | Kimi K2 vs OpenAI | (1) Kimi K2 (사용자 지정) <br> (2) GPT-4o backup | **(1)** + (2) fallback (장애 대비) |
| **C** | RAG 방식 | (1) Vector DB (Pinecone) <br> (2) Static keyword RAG | **(2)** — 작은 playbook이라 충분 |
| **D** | 사용자 인증 | (1) 없음 (public demo) <br> (2) 간단 토큰 | **(1)** 해커톤 demo용. production은 (2) |
| **E** | UI 언어 | (1) 한국어 only <br> (2) 영어 only <br> (3) 토글 | **(2)** 영어 권장 (해커톤 채점관 미국 ODSC) — 단, LLM은 한/영 모두 지원하도록 |
| **F** | 배포 타겟 | (1) Vercel + Lambda <br> (2) Render <br> (3) Zerve native | **(3) Zerve native가 채점 가산점**. 구현 복잡 |
| **G** | LLM 캐싱 | (1) 없음 <br> (2) Redis <br> (3) 파일 기반 | **(3)** — 해커톤은 파일이 단순 |
| **H** | LLM 출력 검증 | (1) 텍스트 그대로 <br> (2) JSON schema 검증 | **(2)** 권장 — 프론트엔드 안정성 |

---

## 5. 구현 단계 (마감 4/30 10AM 고려, 약 14시간 남음)

### Phase 1 — 핵심 (3시간) ✅ 마감 안에 가능
- [x] 데이터 파일 export (팀원 `export-data.py`로 이미 됨)
- [ ] Kimi K2 API 키 셋업 + 단순 호출 테스트
- [ ] `llm_client.py` — Kimi K2 wrapper + retry + 캐시
- [ ] Prompt template 1 (Segment Strategy) 만들고 13개 segment 배치 호출
- [ ] 결과 → `web/public/data/strategies.json`
- [ ] FastAPI에 `/api/llm/segment-strategy` 엔드포인트 (정적 lookup)

### Phase 2 — 프론트 통합 (3시간)
- [ ] `ActionCards` 컴포넌트 — strategies.json 읽어서 top 3 카드
- [ ] `SegmentStrategy` 컴포넌트 — segment 클릭 시 상세 패널
- [ ] FunnelExplorer 안에 LLM 추천 텍스트 inline 추가

### Phase 3 — UserLookup 강화 (2시간)
- [ ] Prompt template 2 (User Action) 작성
- [ ] Top 5% (372명) pre-compute + JSON 저장
- [ ] UserLookup에 추천 카드 표시

### Phase 4 — 폴리싱 (2시간)
- [ ] ROI Calculator 컴포넌트
- [ ] LLM Chat (간단 sidebar) — 옵션
- [ ] Hero에 "AI Strategist" 메시징 추가

### Phase 5 — 영상 + 리포트 (4시간) ★ 채점에 직결
- [ ] 3분 영상 녹화 (시나리오: PM이 들어와서 → segment 클릭 → 캠페인 받음)
- [ ] Zerve report 작성 (agent 사용)
- [ ] README 업데이트

### Phase 6 — 배포 (1시간)
- [ ] Vercel 배포
- [ ] FastAPI Render 배포
- [ ] 도메인 + DNS

---

## 6. 채점 매핑

| Rubric | 점수 | 우리 플랫폼 어디서?  |
|---|---:|---|
| Predictive Model Quality | 25 | v3 ensemble (PR-AUC 0.27, calibrated). Hero KPI에 노출 |
| Handling of Leakage | 15 | 25개 블랙리스트 + cutoff. README + report에 명시 |
| Funnel Design | 25 | v4 15-category. FunnelExplorer 컴포넌트 |
| Transition Logic | 25 | transition matrix + Sankey. FunnelExplorer 안 |
| Data Understanding | 15 | EDA report + manifold3D + funnel_grid |
| **Insights & Business** | **5** | **★ LLM Strategist + ActionCards + Playbook (이 플랫폼의 차별화)** |
| Communication | 5 | Frontend UX + 영상 + report |
| (보너스) Deployment | +α | 인터랙티브 plat 자체 = 보너스 만점 |

---

## 7. 위험 요소

| 위험 | 영향 | 대응 |
|---|---|---|
| Kimi K2 응답 형식 unstable | 프론트 깨짐 | JSON schema 검증 + GPT-4 fallback |
| Pre-compute 시간 부족 | 일부 segment 빈 화면 | 빈 segment는 generic playbook 액션 표시 |
| 프론트 통합 시간 부족 | 데모 못 보여줌 | 최소: ActionCards 1개 컴포넌트만 |
| 배포 실패 | 채점 0 | 로컬 데모 영상 백업 |
| 데이터 신선도 | 모델/현실 격차 | 보고서에 limitation 명시 |

---

## 8. 다음 액션 (이 문서 confirm 후)

1. **API key 확보**: Kimi K2 (Moonshot AI) 계정 + API key
2. **`llm_client.py` 작성**: 단순 wrapper + 첫 호출 성공
3. **Segment 13개 정의**: stages × meta combo
4. **Prompt 1 (SegmentStrategy) 작성**: 한 segment에 대해 manual 호출 검증
5. **Batch 실행 + JSON 저장**
6. **Frontend 컴포넌트 1개 (ActionCards)** 구현 시작

---

## Appendix A. Kimi K2 API 호출 예제 (참고용 — OpenAI compatible)

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MOONSHOT_API_KEY"],
    base_url="https://api.moonshot.cn/v1",
)

resp = client.chat.completions.create(
    model="kimi-k2",  # 또는 moonshot-v1-128k
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
    temperature=0.3,
    response_format={"type": "json_object"},
)
data = json.loads(resp.choices[0].message.content)
```

---

## Appendix B. 사용자 흐름 시나리오 (Demo)

```
1. PM 접속 → Hero (현재 KPI: 17,541 users / 1.84% conversion / 35% AtRisk)
2. ActionCards 본다 → "이번 주 Top 3 캠페인" 카드
   ★ 1순위: Credit 한도자 즉시 결제 유도 (649명, expected +13%p)
   ★ 2순위: AtRisk@Upgraded re-engagement (74명, 17.6% 회복)
   ★ 3순위: Power Engaged sales touch (154명, 26%)
3. 1순위 카드 클릭 → SegmentStrategy 패널 슬라이드
   - "Credit 한도 도달자" 명단 다운로드
   - LLM이 작성한 메시지 카피 (한/영)
   - 예상 ROI 차트
4. "이 segment에 추가 질문" → LLM Chat 열림
   - "이 segment의 평균 lifetime은?" → 답변 stream
5. UserLookup → person_id 1개 검색
   - 사용자 프로파일 + 예측 점수 + funnel 단계
   - LLM 추천: "이 사용자에게는 ____ 캠페인이 좋습니다 (rationale: ...)"
6. PM 결정 → 캠페인 실행 (외부 도구로)
```
