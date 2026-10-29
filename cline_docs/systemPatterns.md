# System Patterns — 아키텍처와 설계 결정

---

## 1. 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│ 1) 수집 (main.py)                                                │
│    EduKingdom 사이트 로그인(Playwright)                          │
│    → 과목별 결과 PDF 다운로드(downloads/)                        │
│    → 학생별 병합 → output/<TestType>_R<회차>/<학생>.pdf          │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2) 분석 (run_pipeline.py)                                       │
│    병합 PDF → pypdf 텍스트 추출 → 문항별 정오답/토픽 파싱        │
│    → output/parsed_reports_v2.json (누적 병합)                  │
│    → output/question_bank_by_type.json                          │
│    → Progress Report PDF                                        │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3) 생성 (tools/generate_personalized_practice_sets.py)          │
│    parsed_reports_v2.json + 문제은행(pool.json, reading_complete_db.json) │
│    → 학생별 약점 분석 → 과목별 유동 배분 → 지문 그룹 선택        │
│    → student_practice.pdf / teacher_answer_key.pdf / questions.json │
└─────────────────────────────────────────────────────────────────┘

    ┌── 문제은행 확장 (오프라인, 신규) ─────────────────────────┐
    │ J: 시험지 PDF → OCR(psm4) → 문항/보기 파싱                │
    │   → 정답지(ANS) 굵은글씨 판정 → exam_papers_raw.json      │
    │   → build_reading_db_from_papers.py → reading_complete_db.json │
    └───────────────────────────────────────────────────────────┘
```

---

## 2. 모듈 책임

| 모듈 | 책임 | 하지 않는 것 |
|---|---|---|
| `main.py` | 사이트 로그인·다운로드·병합 | PDF 파싱 |
| `run_pipeline.py` | 결과 PDF 파싱, 리포트 생성 | 문제 생성 |
| `generate_personalized_practice_sets.py` | 문제 선택·배분·PDF 조립 | 데이터 생성/수집 |
| `tools/extract_exam_papers.py` | 시험지 PDF → 구조화 문항(JSON) | DB 병합 결정 |
| `tools/build_reading_db_from_papers.py` | 추출 결과 → 생성기용 DB 병합 | PDF 렌더링 |
| `tools/check_duplicates.py` | 산출물 세트 내 stem 중복 검사 | 수정 |

---

## 3. 핵심 설계 결정 (Decision Log)

### D1. 문제은행은 "정적 JSON" 이다 (현재)
- 생성기는 `pool.json` + `reading_complete_db.json` 만 읽는다.
- **LLM 생성이나 학습 모델은 없다** → 검색(retrieval) + 조립(assembly) 방식.
- 이유: 재현성·검수 가능성. LLM 생성은 별도 배치 단계로 분리하는 것이 목표(미구현).

### D2. Reading 은 지문 그룹 단위로 선택한다
- `group_reading_by_passage()` 로 지문별 문항을 묶고, `LONG_PASSAGE_MIN = 300` 자 이상만 후보.
- 한 지문에서 3~8문항을 연속 배정 → "긴 지문 + 다문항" 요구사항 충족.
- 정렬 우선순위: ① 약점 주제 포함 지문 ② 지문 길이 ③ 문항 수.

### D3. 문항 수는 학생 성취도로 유동 배분한다
```
가중치 = 1.0 + (1 - 과목정답률) × 2.0        (1.0 ~ 3.0, 약할수록 큼)
1) 과목별 최소 2문항 보장 (MIN_PER_SUBJECT)
2) 남은 문항을 가중치 비례 분배 (최대잔여법)
3) 과목 재고(stock) 초과 불가 → 부족분은 다른 과목으로 자동 재분배
```
- 실측: 30문항 세트에서 (9,12,9) ~ (12,9,9) 등 학생별 8가지 조합.

### D4. 문제 품질 게이트 (`is_usable_question`)
배제 조건: 선택지 2개 미만 / `options == "A|B|C|D"` / 빈 stem / 플레이스홀더 stem(`^Read Extract .+ carefully\. - Q\d+$`) / 정답이 선택지 범위 밖.

### D5. 중복 방지는 stem 정규화 기준
- `re.sub(r'\s+', ' ', stem).lower()` 로 비교.
- 과거 `_id`(python `hash()`) 기준 중복 검사는 **실패 사례**가 있었다(동일 stem, 다른 `_id` → 88건 중복). 현재는 stem 기준.

### D6. 시험지 OCR 파이프라인 (신규)
- 시험지·정답지 모두 **텍스트 레이어 0인 스캔 PDF** → OCR 필수.
- `psm 3` 은 보기 라벨을 잃는다 → **`psm 4`** 사용 (`A ...`, `Cc ...`, `D___ ...`).
- 정답 판정: 정답지에서 정답 보기가 **굵게(bold)** 표시됨 → 두 PDF 의 동일 좌표에서
  `잉크밀도(ANS) / 잉크밀도(paper)` 비율 계산 → 최대값이 `≥1.08` 이고 2위와 `≥0.05` 차이면 채택.
  실측 정확도: 판정된 정답 중 오류 0건 (STT26 8문항 중 7개 판정, 7개 모두 정답).
- 섹션 구분: `Questions N to M.` 마커 기준. 마커~첫 문항 사이가 지문.

### D7. 산출물 재현성
- `questions.json` 에 `_id`(실행마다 변하는 hash) 저장 금지.
- `generated_at` 은 코드에 하드코딩하지 않고 실행 시각 기록.

---

## 4. 데이터 스키마

### 문제 문항 (생성기 입력)
```json
{
  "subject": "Reading | Mathematical Reasoning | Thinking Skills",
  "topic": "Linked Extracts | Mass | ...",
  "difficulty": "Medium | Hard",
  "stem": "문제 본문",
  "passage": "지문 (Reading 은 300자 이상)",
  "options": "보기1|보기2|보기3|보기4",   // 파이프 구분
  "answer": "A",
  "explanation": "해설"
}
```

### reading_complete_db.json (섹션 단위)
```json
[{ "type": "Linked Extracts", "title": "STT13 ENG — Questions 1-4",
   "source": "STT13 ENG.pdf", "passage": "...",
   "questions": [{ "stem": "...", "options": "a|b|c|d", "answer": "B",
                   "explanation": "...", "topic": "Linked Extracts", "difficulty": "Hard" }] }]
```

### exam_papers_raw.json (추출 원본)
```json
[{ "paper_id": "STT13 ENG", "file": "STT13 ENG.pdf", "ans_file": "STT13 ENG ANS.pdf",
   "subject": "ENG",
   "sections": [{ "type": "Linked Extracts", "title": "Questions 1-4", "passage": "...",
                  "long_passage": true,
                  "questions": [{ "no": 1, "stem": "...", "options": ["...","...","...","..."],
                                  "answer": "B", "answer_confidence": 0.12 }] }] }]
```

---

## 5. 실행 순서 규칙

1. **데이터 → 코드 → 산출물** 순서. 문제은행을 바꾼 뒤에는 반드시 생성기를 재실행한다.
2. `output/` 산출물은 **언제나 파생물**이다. 코드 변경 후 재생성하지 않으면 stale 이 된다.
3. DB를 덮어쓰는 스크립트는 **병합 우선**. 빈 결과로 기존 DB를 지우면 안 된다.
