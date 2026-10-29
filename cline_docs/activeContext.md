# Active Context — 현재 진행 상황 (2026-10-29 기준)

> **새 세션은 이 문서부터 읽고 작업을 이어가세요.**

---

## 1. 지금 상태 한 줄

Reading 문제 생성 문제를 **해결 완료**했고, 기출 시험지 OCR 추출 파이프라인을 **신규 구축**했다.
다음 작업은 **(A) 더 많은 시험지 배치 처리 → (B) LLM 기반 신규 문제 생성 파이프라인**.

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
[INFO] Pool loaded: 99 total questions (Math: 30, Reading: 56, Thinking: 13)

Selective R26 30문항 세트 배분 예시 (학생별로 다름)
  Aanya Surve    정답률 0.47/0.17/-     → 배분 9/12/9   (Reading 지문 2개)
  Aaron He       0.61/0.69/0.62          → 10/10/10
  Asees Kaur     0.37/0.69/0.40          → 11/8/11

검증: 21명 × 3세트 errors 0 / check_duplicates 1,260문항 중복 0
```

---

## 5. 다음 단계 (우선순위 순)

### ⓐ 시험지 배치 확장 (사용자 준비 중)
- 사용자가 **추가 시험지 보관 위치**를 알려줄 예정.
- 실행: `python tools/extract_exam_papers.py --roots "<새경로>" --subjects ENG MATH TS`
- 그 후 `python tools/build_reading_db_from_papers.py` → 생성기 재실행.
- 현재 ENG 7편만 처리됨. 남은 ENG 약 40편 + MATH/TS 미처리.

### ⓑ LLM 기반 신규 문제 생성 파이프라인 (구현 완료 · API 키 대기)
- `tools/generate_questions_llm.py` 신규 작성 완료.
- 두 가지 모드: `--mode passage`(기존 지문 재사용 + 새 문항) / `--mode new`(새 지문+문항)
- 생성 결과는 **구조 검증 게이트** 통과분만 저장: `data/questions/generated_db.json`
  - 검증: stem 15자↑ / 선택지 4~5개 / 중복 선택지 없음 / 정답 범위 / 해설 10자↑ / stem 중복 0
  - `structure_ok=true, verified=false` 로 저장 → 검수 후 `verified=true` 로 바꾸면 우선 사용
- 생성기는 `structure_ok` 또는 `verified` 인 섹션만 읽는다 (`PRACTICE_GENERATED_DB` 로 경로 override 가능)
- **아직 실제 생성 전**: `.env` 에 `GEMINI_API_KEY` (또는 `OPENAI_API_KEY`) 필요
- 키 없이 확인하는 방법: `--dry-run`(프롬프트만) / `--mock`(파이프라인 동작 검증)

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
