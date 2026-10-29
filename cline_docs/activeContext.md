# Active Context — 현재 진행 상황 (2026-10-29 기준)

> **새 세션은 이 문서부터 읽고 작업을 이어가세요.**

---

## 1. 지금 상태 한 줄

🔴 **최우선: 저작권 사고 수습 중** — 기출 지문 원문이 학생용 PDF에 들어갔습니다.
코드로 차단(`original: true` 만 사용)했고, **재생성 및 배포물 회수**가 필요합니다.
그 다음 작업은 **(A) 새 지문 창작 생성 → (B) MATH/TS 추출 → (C) 미수정 버그**.

### ⚠️ 저작권 사고 요약 (2026-10-29)
- 원인: 대량 추출한 기출 지문(329섹션)을 그대로 학생용 문제집에 사용
- 차단: `original: false` 플래그 + 생성기 자동 제외 (`[COPYRIGHT]` 로그)
- 영향: Reading 긴 지문 재고가 **0** 이 됨 → `--mode new` 로 **새 지문 창작** 필요
- 필수 후속: ① 생성기 재실행 ② 새 지문 생성 ③ 배포본 회수

---

## 2. 이번 세션에서 한 일 (2026-10-29)

| # | 작업 | 결과 |
|---|---|---|
| 1 | "Reading 문제가 PDF에 안 보임" 원인 분석 | 소스 DB 문항 0 + 플레이스홀더/더미 문항이 원인임을 확정 |
| 2 | 문제 선별 로직 재설계 | 긴 지문(≥300자) 그룹 단위 선택 + 학생 성취도 기반 유동 배분 |
| 3 | 품질 게이트 추가 | `is_usable_question()`, stem 정규화 중복 제거 |
| 4 | **시험지 OCR 추출기 신규 작성** | `tools/extract_exam_papers.py` (psm4 + 굵은글씨 정답 판정) |
| 5 | **추출 → DB 병합 스크립트** | `tools/build_reading_db_from_papers.py` |
| 6 | 실제 기출 7편 추출 | 긴 지문 섹션 9개 / 문항 34개를 DB에 병합 (Reading 8 → 42문항) |
| 7 | 산출물 재생성 | 21명 × 3세트, 1,260문항, **중복 0** |
| 8 | 지식 베이스 도입 | `AGENTS.md`, `docs/PROJECT_MEMORY.md`, `cline_docs/` |
| 9 | **LLM 문제 생성 파이프라인 신규 작성** | `tools/generate_questions_llm.py` + 생성기 연동 (`generated_db.json`) |
| 10 | **LLM 실제 생성 실행** | 9섹션 / **45문항 생성** (탈락 0건) → Reading 56 → **101문항** |
| 11 | **연도별 기출 아카이브 확인** | OC/STT 2022~2025 **ENG 314편** 발견 (J: 드라이브) |
| 12 | **대량 배치 추출** | `--workers 8 --append --skip-existing` 병렬 파이프라인 추가 후 실행 |

---

## 3. 최근 변경 파일

### 신규
- `tools/extract_exam_papers.py` — 시험지 PDF → 문항 JSON (OCR)
- `tools/build_reading_db_from_papers.py` — 추출 JSON → `reading_complete_db.json`
- `cline_docs/*.md` — Memory Bank (이 문서 포함)
- `AGENTS.md`, `docs/PROJECT_MEMORY.md` — 에이전트용 기억 문서

### 수정
- `tools/generate_personalized_practice_sets.py`
  - `LONG_PASSAGE_MIN=300`, `MIN_PER_SUBJECT=2` 상수 추가
  - `is_usable_question()`, `normalize_subject()`, `subject_accuracy()`, `allocate_counts()`, `group_reading_by_passage()` 추가
  - `select_questions(areas, count, pool, report=None)` — 지문 그룹 선택 + 유동 배분
  - `load_pool()` — 플레이스홀더 필터, Reading 재고/긴 지문 수 경고
  - `questions.json` 에서 `_id` 제거, `generated_at` 동적화, `subject_counts` 기록

### 데이터
- `data/questions/reading_complete_db.json` — 1섹션/8문항 → **10섹션/42문항**
- `data/questions/exam_papers_raw.json` — 추출 원본 (7편)
- `data/questions/exam_papers_review.json` — 정답 미판정 문항(검수 대상)

---

## 4. 현재 실측 수치 (다음 세션에서 재검증할 것)

```
[INFO] Pool loaded: 1119 total questions (Math: 30, Reading: 1076, Thinking: 13)
       LLM 생성 문항 포함: 45개 (generated_db.json)
       Reading: 343 passages / long passages(>=300 chars): 329 passages, 1062 questions

Selective R26 30문항 세트 배분 예시 (학생별로 다름)
  Aanya Surve    정답률 0.47/0.17/-     → 배분 9/12/9
  Deeksha        (가장 약함)             → 12/9/9   (Reading 12 = 긴 지문 3개)
  Aaron He       0.61/0.69/0.62          → 10/10/10

검증: 21명 × 3세트 errors 0 / check_duplicates 1,260문항 중복 0
기출 추출: 333편 / 5,793문항 (정답 3,593, 62.0%) / 긴 지문 정답 3,465
```

### LLM 모델 현황 (2026-10-29 실측)
| Provider | 상태 |
|---|---|
| Gemini `gemini-3.5-flash` | ✅ 정상 (기본값) |
| Gemini `gemini-2.0-flash` / `2.5-flash` / `2.5-pro` | ❌ 404 — **신규 사용자 제공 중단** |
| Gemini `gemini-flash-latest`, `gemini-3.8-flash` | ⚠️ 503 (수요 폭주) → 재시도 로직으로 대응 |
| OpenAI `gpt-4o-mini` | ❌ 429 `insufficient_quota` (크레딧 소진) |

---

## 5. 다음 단계 (우선순위 순)

### ⓐ 시험지 배치 확장 (사용자 준비 중)
- 사용자가 **추가 시험지 보관 위치**를 알려줄 예정.
- 실행: `python tools/extract_exam_papers.py --roots "<새경로>" --subjects ENG MATH TS`
- 그 후 `python tools/build_reading_db_from_papers.py` → 생성기 재실행.
- 현재 ENG 7편만 처리됨. 남은 ENG 약 40편 + MATH/TS 미처리.

### ⓑ LLM 문제 생성 — **1차 실행 완료** (45문항)
- `tools/generate_questions_llm.py` 로 **9섹션 / 45문항** 실제 생성 (탈락 0건)
- 기본 모델: `gemini-3.5-flash` (2.0/2.5 계열은 신규 사용자 제공 중단 → 404)
- 산출물: `data/questions/generated_db.json` (`structure_ok=true`, `verified=false`)
- 다음: 생성 문항 **사람 검수** 후 `verified: true` 승격, 필요 시 `--mode new`로 새 지문 생성

### ⓒ 미수정 버그 (progress.md 참조)
- `run_pipeline.py` 학생 이름/ID 유실 (Anonymous 회귀) — **파이프라인 재실행 전 필수 수정**
- `tools/parse_reading_complete.py` 의 `questions: []` 덮어쓰기 위험

---

## 6. 작업 시 주의사항

1. **문제은행을 바꾼 뒤 반드시 생성기를 재실행**한다. `output/` 은 파생물이다.
2. OCR 배치는 편당 30~40초. `--limit` 으로 나눠 실행하고 로그를 파일로 남긴다.
3. 시험지 PDF 는 스캔본이라 OCR 품질 이슈가 있다. **cloze 표 형식 섹션**은 현재 파싱 불가(자동 제외됨).
4. 정답 판정이 안 된 문항은 `exam_papers_review.json` 에 쌓인다 → 사람이 검수하거나 제외.
5. 검증 없이 커밋하지 않는다: `check_duplicates.py` + PDF 텍스트 카운트 필수.
