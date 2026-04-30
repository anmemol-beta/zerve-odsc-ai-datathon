# Video Assets — DaVinci 임포트 가이드

3분 영상 14컷에 1:1로 매칭되는 시각자료. 모든 PNG는 **1920×1080 · BG #0a0e1a · 다크 테마** 통일.

## 컷 ↔ 자료 매핑

| 시간 | 길이 | 보이스오버 핵심 | 화면 자료 |
|---|---|---|---|
| **0:00** | 5s | "350만 이벤트, 1만 7천 사용자..." | `cut_0_00_title.png` (타이틀 카드) |
| **0:05** | 18s | "절반이 14분 내 이탈..." | `cut_0_05_discovery1.png` (3-card: 14min / first week / first hour) |
| **0:23** | 18s | "두 강한 시그널..." | `cut_0_23_lift_table.png` (top-6 lift bar) |
| **0:41** | 12s | "15단계 퍼널..." | `cut_0_41_funnel_15stage.png` (15-stage 분포 horizontal bar) |
| **0:53** | 16s | "결제자 1 in 3 위험" | `cut_0_53_post_upgrade_donut.png` (donut + 3 stat cards) |
| **1:09** | 14s | "Integrated→Engaged 51%..." | `cut_1_09_transitions.png` (8×8 heatmap, 핵심 셀 핑크 박스) |
| **1:23** | 14s | "55× spread..." | `cut_1_23_flag_combos.png` (8-bar combo, 111/000 강조) |
| **1:37** | 14s | "5 candidates head-to-head" | `cut_1_37_models.png` (6-row model bar + 11× 강조) |
| **1:51** | 12s | "top 5%로 절반 포착" | `cut_1_51_topk.png` (catch curve + 5% 강조 점) |
| **2:03** | 14s | "SHAP → 마케팅 액션" | `cut_2_03_shap_action.png` (SHAP top-8 + 액션 매핑 우측 패널) |
| **2:17** | 16s | "3 production guardrails" | `cut_2_17_guardrails.png` (3-panel: audit / drift / calibration) |
| **2:33** | 14s | "7 campaigns ranked" | `cut_2_33_playbook.png` (7-row lift bar) |
| **2:47** | 12s | "K2-Think live demo" | **screen recording** (아래 참조) |
| **2:59** | 3s | "Thanks" | `cut_2_59_end.png` (URL 끝카드) |

---

## 2:47 K2 demo — 스크린 녹화 가이드

PNG 없음. **라이브 사이트 12초 녹화**:

1. Chrome 1920×1080, 시크릿 모드
2. URL: `https://anmemol-beta.github.io/zerve-odsc-ai-datathon/`
3. 시퀀스 (12초 안에):
   - 0–3s: 페이지 상단 hero 살짝 보이고
   - 3–6s: K2 Strategy Gallery 섹션으로 스크롤
   - 6–10s: segment 카드 1개 클릭, 3 actions 펼쳐짐
   - 10–12s: action 카드의 "expected lift" / "ROI" 숫자 zoom
4. 마우스 커서 표시 (DaVinci Magnify로 강조)

대안: 사이트가 다운이면 `web/`을 로컬에서 `npm run dev`로 띄우고 같은 흐름.

---

## DaVinci 임포트 워크플로

1. **Project setup**: 1920×1080 · 30fps · YRGB color science
2. **트랙 구성**:
   - V1: 이 PNG들 (각 컷 길이만큼 stretch)
   - V2: zoom-in detail (필요 시)
   - V3: 텍스트 오버레이 (필요 시)
   - A1: 보이스오버 (이미 녹음)
   - A2: 옵션 ambient
3. **PNG 임포트**: Media Pool에 `video_assets/` 통째 드래그 → 파일명 시간순 정렬돼 있음
4. **타임라인**:
   - 보이스오버 단일 트랙으로 펼치고
   - 각 PNG를 해당 시간대에 cut-in (페이드인 0.2s 권장, fade-out 0s)
5. **컷 #2:47만 비디오 클립**: K2 demo 스크린 녹화 mp4를 그 위치에 인서트
6. **글자 강조 (옵션)**: 보이스가 "16배"라고 말하는 순간에 화면의 "16×" 숫자에 짧은 zoom (1.05× scale, 0.5s) 또는 short flash overlay

---

## 시각자료 색상 가이드

| 색 | 의미 | 사용 컷 |
|---|---|---|
| 핑크 `#ec4899` | 발견 / 비즈니스 / 핵심 | 0:00, 0:23, 1:23, 2:03, 2:33 |
| 시안 `#22d3ee` | 데이터 / 시스템 / EDA | 0:05, 0:41, 1:09, 2:17, 2:59 |
| 바이올렛 `#a78bfa` | 모델 / ML | 0:00, 1:37, 2:03 |
| 앰버 `#fbbf24` | 위험 / 라이프사이클 위험 | 0:53 (at-risk wedge) |
| 에메랄드 `#34d399` | 성공 / 활성 / 통과 | 0:00 (10.6×), 0:53 (active), 2:17 (audit) |
| 로즈 `#fb7185` | 이탈 / 부정 | 0:53 (churned wedge), 1:37 (majority baseline) |

영상 전체에서 일관된 색이 같은 의미를 갖도록 — 화면 상태가 바뀌어도 청자가 색만 봐도 직관 유지.

---

## 다시 만들 때

데이터가 갱신되면:

```bash
cd docs/video_assets
python3 generate_assets.py
```

13개 PNG 모두 다시 생성. 필요 패키지: `pandas`, `matplotlib`, `numpy`. 5초 이내 완료.

소스 데이터:
- `event_lift_table.csv` → 0:23
- `funnel_v4_milestones.csv` → 0:41, 0:53
- `transition_v4_counts.csv` → 1:09
- `mission1_v3_predictions.csv` → 1:51
- `mission1_v2_xgb_importance.csv` → 2:03
- 나머지는 분석 리포트 숫자 하드코딩
