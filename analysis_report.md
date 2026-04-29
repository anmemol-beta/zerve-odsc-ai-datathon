# Zerve Hackathon 데이터 분석 보고서

> 분석 대상: `zerve_events.csv` (861MB, 3,509,628 행) + `Zerve_Hackathon_Kickoff.pdf` (20p)
> 분석 일자: 2026-04-29

---

## 1) 과제 요약 (PDF)

- **미션 1**: 어떤 사용자가 업그레이드할지 예측 (`event = subscription_upgraded`가 양성 라벨)
- **미션 2**: 모든 사용자를 항상 정확히 한 단계에 배치하는 funnel 정의 (9단계 예시 제공: New → Exploring → Created Content → Used AI → Wrote Code → Used Integration → Engaged → Upgraded → At Risk)
- **결정적 경고**: target leakage 주의. `redeem upgrade offer` 같은 이벤트 쓰면 모델은 좋아 보이지만 무용지물. 채점에서 25점(model quality) + 15점(leakage handling) = 40점이 leakage 처리 quality에 직결.
- 채점 100점 / 1등 $5,000 / 마감 4/30 10AM

---

## 2) 데이터 전반

| 항목 | 값 |
|---|---|
| 총 행 | **3,509,628** |
| 고유 사용자 | **17,541** |
| 업그레이드 사용자 | **323명 (1.84%)** ← 매우 imbalanced |
| 시간 범위 | 2025-09-01 ~ 2026-04-16 (약 7.5개월) |
| 고유 이벤트 종류 | **227개** |

**컬럼 구조**: `person_id`, `timestamp`, `event` + `person_properties.*` (가입 시 작성: role/purpose/work_type/source/cloudProvider) + `properties.*` (이벤트별 메타: 디바이스, AI 토큰/모델, credits, button_name, utm, web_vitals 등 80개+)

---

## 3) 사용자 프로필

| 차원 | 분포 |
|---|---|
| **Role** | Student 33% > Data Scientist 18% > Data Analyst 14% > AI Engineer 13% > ML Engineer 7% |
| **Purpose** | Personal Projects 74% / Company Work 18% / Education 7% |
| **Work type** | Data & Analytics 45% > R&D 32% > Business Apps 11% |
| **가입 출처** | Google 35% / LinkedIn 31% / Press·Media 21% |
| **국가 (이벤트 기준)** | Ireland 1위(AWS Dublin 라우팅 영향 의심) / India 2위 / US 3위 |
| **OS** | Linux 70%(노트북 실행 컨테이너 영향 의심) / Windows 20% / Mac 9% |
| **UTM** | Devpost 1위 → 해커톤·대회 트래픽 비중 큼 |

> ⚠️ **주의**: Ireland가 사용자 국가 1위, Linux가 OS 1위인 건 Zerve **백엔드 실행 환경**이 이벤트에 같이 찍힌 결과일 가능성이 높음. 사용자 지역/디바이스 feature로 쓸 땐 device_type/browser 같은 client-side 신호 우선.

---

## 4) 사용 패턴 (Top 이벤트)

```
934,821  credits_used          ← 압도적
549,818  $ai_generation
347,985  $exception            ← 전체의 10% (에러 빈번)
272,411  addon_credits_used
189,498  notebook_deployment_usage_tracked
 92,596  agent_tool_call_get_block_tool
 66,758  agent_tool_call_create_block_tool
 55,106  credits_below_4
 38,706  agent_tool_call_refactor_block_tool
```

- 핵심 기능 = **Coder Agent**. `tool_name = Coder Agent`가 34만건 (다른 tool은 1만건 미만)
- `subscription_type` 컬럼은 4행만 채워져 사실상 사용 불가
- `feature_tag`도 거의 비어있음 (4행)

---

## 5) 사용자 활동 분포 (long-tailed, churn 강함)

| | 이벤트 수 | lifetime |
|---|---|---|
| median | **17 events** | **0.01일 (≈14분)** |
| p75 | 60 | 1일 |
| p90 | 369 | 14일 |
| p95 | 816 | 33일 |
| p99 | 3,361 | 105일 |
| max | 97,938 | 228일 |

→ **절반 이상은 가입 후 14분 내 마지막 활동**. 모델은 짧은 초기 시퀀스만 보고 판단해야 한다.

---

## 6) ⚠️ Leakage 후보 (모델링에서 반드시 제외)

target과 직접/즉시 인접 — 사용 시 채점 감점 직결:

```
subscription_upgraded         ← target
upgrade_subscription           1,318
clicked_upgrade                1,360
billing_info                     242
addon_credits_purchased           74
add_credits / clicked_add_credits  106 / 94
agent_add_credits_button_clicked  395
claim_free_offer_clicked       1,269
promo_code_redeemed            1,718
team_plan_modal                   78
agent_resume_plan_button_clicked   30
watermark_remove_upgrade_clicked    4
subscription_downgraded / cancelled / renew_plan / open_cancel_plan_modal
```

> `open_cancel_plan_modal`이 업그레이더 30%에서 발생 — 이건 명백히 업그레이드 **이후** 이벤트라 super-leak.

---

## 7) ⚡ 강한 예측 신호 (clean — leakage 아닌 것)

업그레이더 reach % vs 비업그레이더 reach % (상위만, lift 순):

| 이벤트 | upgrader | non-upgrader | lift |
|---|---|---|---|
| **credits_exceeded** | 49.9% | 4.0% | **12.4x** |
| **agent_tool_call_analyze_attachment_tool** | 41.5% | 3.5% | 11.9x |
| **ai_credit_banner_shown** | 39.9% | 1.8% | 22x |
| **agent_tool_call_get_scripts_tool** | 25.1% | 2.0% | 12.3x |
| **notebook_deployment_*** (deployed/preview/usage) | 14–23% | 0.5–1.8% | 12–25x |
| **agent_retry_message_button_clicked** | 16.4% | 0.3% | 53x |
| **ai_credit_banner_clicked** | 9.3% | 0.2% | 46x |
| **source_control_commit/pull/connect** | 7–9% | 0.5–0.6% | 14–15x |
| **canvas_clone** | 7.4% | 0.5% | 14x |
| **stop_all_blocks** | 10.5% | 0.8% | 13x |
| **notebook_report_create** | 6.8% | 0.2% | 28x |

**핵심 페르소나**: 업그레이더 = *"실제로 진지하게 일하다 무료 한도에 부딪힌 사용자"*

1. credit 한도 부딪힘 (credits_exceeded, ai_credit_banner_shown)
2. Coder Agent를 깊이 사용 (analyze_attachment, get_scripts, retry)
3. 노트북을 **실제로 배포**까지 함 (deployment 시리즈)
4. **Git/Source control** 연결 → 진지한 사용자
5. canvas clone, report 생성 등 자산화 행동

비업그레이더는 `$pageview/$pageleave/sign_up/skip_onboarding_form`은 비슷하거나 더 많이 함 — *둘러보다 떠나는* 패턴.

---

## 8) ⏱️ Time-to-upgrade (가장 결정적인 패턴)

| | 가입 후 업그레이드까지 |
|---|---|
| **같은 날 업그레이드** | **198/323 = 61.3%** |
| **7일 이내** | **245/323 = 75.9%** |
| median | 3시간 |
| p90 | 25.6일 |

→ **결정적 함의**: 모델은 "최초 1시간/1일 행동 시퀀스" 만으로 예측해야 한다. *random user-level split을 쓰면 시간 leakage가 거의 무조건 발생*. 시간 기준 split (예: 2025-09 ~ 2026-02 train / 2026-03 ~ 2026-04 holdout) 권장.

---

## 9) Funnel 가설 매핑 (PDF 9단계 → 실제 이벤트)

| 단계 | 트리거 이벤트 (후보) |
|---|---|
| 1. New | `new_user_created` / `sign_up` |
| 2. Exploring | `$pageview`, `$autocapture`, `notebook_onboarding_tour_*`, `submit_onboarding_form` |
| 3. Created Content | `block_create`, `run_block`, `files_upload`, canvas 생성 |
| 4. Used AI | `$ai_generation`, `agent_message`, `agent_new_chat`, `agent_start_from_prompt` |
| 5. Wrote Code | `block_create` + `run_block` (실제 실행) |
| 6. Used Integration | `source_control_*`, AWS/cloud 연결 |
| 7. Engaged | 3+일 활성 + 임계 (예: ≥5 `run_block` & ≥1 deployment) |
| 8. Upgraded | `subscription_upgraded` |
| 9. At Risk | 7일 무활동 (lifetime 분포 보면 14일이 더 자연스러울 수도) |

---

## 10) 모델링 권장 사항

1. **Leakage 제거 화이트리스트 방식 권장** — 사용 가능 이벤트만 명시적으로 허용 (위 Top 이벤트 + agent_tool_call_*, run_block, block_create 등).
2. **사용자별 컷오프 시점 적용**: 업그레이더는 *첫 `subscription_upgraded` timestamp 직전*까지의 이벤트만 feature로. (within-user leakage 방지)
3. **시간 split**: 9~2월 train / 3~4월 test
4. **불균형 대응**: 1.84% positive → class weight, focal loss, 또는 stratified sampling
5. **핵심 feature 후보** (clean):
   - 첫 1시간/24시간 내 unique event 종류 수
   - `credits_exceeded` 발생 여부 (강한 trigger 신호)
   - notebook deployment 수행 여부
   - Coder Agent tool 사용 다양성 (`agent_tool_call_*` distinct count)
   - source_control 사용 여부
   - canvas/block 생성 수 (`number_of_blocks`, `number_of_canvases`도 컬럼에 있음)
   - 첫 세션 길이, 이벤트당 평균 간격
   - role/purpose/work_type (가입 직후 알 수 있는 정적 속성)

---

## 산출물

- `eda_summary.json` — 전반 통계
- `event_lift_table.csv` — 모든 이벤트의 upgrader vs non-upgrader lift
- `eda_output.txt`, `compare_output.txt` — 콘솔 로그 백업
- `analyze_eda.py`, `analyze_compare.py` — 재현 가능 스크립트

---

## 다음 단계 제안

1. **leakage-safe feature matrix 생성** — 사용자별 첫 1h/24h 행동 집계
2. **시간 기반 train/test split + baseline 모델** (logistic + gradient boosted)으로 PR-AUC 확인
3. **funnel 단계 라벨링 함수 작성** — 사용자×시점 → 단계 매핑
