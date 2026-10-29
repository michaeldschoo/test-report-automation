# Progress — 완료/미완료 및 알려진 버그

---

## 1. 동작하는 것 (검증 완료)

| 기능 | 검증 방법 | 결과 |
|---|---|---|
| 결과 PDF 다운로드·병합 (`main.py`) | 실제 사이트 로그인 | ✅ 운영 중 |
| 결과지 파싱 (문항별 정오답/토픽) | `parsed_reports_v2.json` 17명+4명 | ✅ 회차 누적 |
| Progress Report PDF 생성 | 산출물 확인 | ✅ |
| 맞춤 문제집 PDF/JSON 생성 | 21명 × 3세트 = 63세트 | ✅ 1,260문항 |
| 긴 지문 + 다문항 Reading | PDF 텍스트 추출 | ✅ 세트당 긴 지문 2개 / Reading 9~12문항 |
| 과목별 유동 배분 | 배분 조합 8가지 | ✅ 학생별 상이 |
| 세트 내 중복 방지 | `check_duplicates.py` | ✅ 중복 0 |
| 더미/플레이스홀더 배제 | `is_usable_question()` | ✅ 0건 |
| 시험지 OCR 추출 | ENG 7편 | ✅ 92문항 / 정답 54 |
| 굵은글씨 정답 판정 | STT26 정답 대조 | ✅ 판정 7건 중 오류 0 |
| 추출→DB 병합 | 9섹션/34문항 추가 | ✅ 기존 8문항 보존 |
| LLM 생성 파이프라인 | `--dry-run` / `--mock` | ✅ 프롬프트·검증·저장·연동 동작 확인 |
| LLM 실제 생성 (Gemini 3.5-flash) | 10개 지문 × 5문항 | ✅ **9섹션 / 45문항, 탈락 0건** |
| 생성 문항 문제집 반영 | PDF 텍스트 검사 | ✅ 샘플 세트 Reading 12문항 중 6문항이 LLM 생성분 |
| 대량 배치 추출 (병렬) | `--workers 8 --append --skip-existing` | ✅ 동작 (4편 33초 ≈ 순차 대비 4배) |
| 연도별 아카이브 인식 | OC/STT 2022~2025 | ✅ ENG 314편 식별, 연도 컨텍스트 ID(`OC2023\|OC01 ENG`)로 충돌 방지 |
| **전체 기출 추출 실행** | ENG 333편, workers=8 | ✅ **5,793문항 / 정답 3,593(62.0%) / 긴 지문 정답 3,465** (총 50분) |
| **DB 병합** | `--min-questions 2` | ✅ 329섹션 / **1,017문항** (10섹션/42문항에서 확장) |
| **문제집 재생성** | 21명 × 3세트 | ✅ 1,260문항, 중복 0, 30문항 세트 Reading 12문항 = 긴 지문 3개 |

---

## 2. 알려진 버그 (미수정 — 우선순위 순)

### 🔴 Critical 0. 저작권 — 기출 지문 원문 사용 (2026-10-29 사고)
- 증상: 학생용 문제집 지문이 **기출 원문 그대로** (예: `STT2023|STT29 ENG` "Making Mascara")
- 원인: 대량 OCR 추출 데이터를 그대로 DB에 넣고 생성기가 사용
- 조치(코드): `original: true` 섹션만 사용하도록 차단, 원문은 `original: false` + `verbatim_source`
- **남은 조치**: 재생성 / 새 지문 창작 / 배포본 회수

### 🔴 Critical 1. `run_pipeline.py` 학생 이름/ID 유실 (회귀)
- 위치: `parse_pdf()` 내부
```python
student_name = detect_student_name(fname)          # 계산만 하고 미사용
m = re.search(r'Student Name:\s*[-~\s]*', ...)     # 결과 미사용 (dead code)
final_student_name = "Anonymous"                   # 하드코딩
student_id = None                                  # 항상 None
```
- 실측: PDF 원문에 `Student Name: Diya Muttena Student ID: 45278` 이 있는데 결과는 `Anonymous / None`
- 영향: 파이프라인 재실행 시 **전 학생이 Anonymous 로 병합** → 문제집 생성 불가
- 수정안:
```python
m = re.search(r'Student Name:\s*(.+?)\s+Student ID:', first_text)
parsed_name = m.group(1).strip() if m else None
m_id = re.search(r'Student ID:\s*([A-Za-z0-9-]+)', first_text)
student_id = m_id.group(1).strip() if m_id else None
final_student_name = parsed_name or student_name or "Anonymous"
```

### 🔴 Critical 2. OCR 폴백 미동작
- 위치: `run_pipeline.py` `parse_page()` — `ocr_pdf_to_text` 를 import 만 하고 호출하지 않음
- `hasattr(page, 'extract_text')` 는 항상 True → OCR 분기 도달 불가 (dead code)

### 🔴 Critical 3. `tools/parse_reading_complete.py` 가 DB를 비움
- 파싱한 `questions` 를 사용하지 않고 `"questions": []` 로 저장
- 이 스크립트를 실행하면 `reading_complete_db.json` 의 42문항이 전멸
- **대응**: 실행 금지. 필요하면 `tools/build_reading_db_from_papers.py` 사용

### 🟠 Major 4. cloze 표 형식 섹션 파싱 불가
- 일부 Reading 섹션은 보기가 2열 표로 배치되어 OCR 이 `ordinary A _ vanished` 처럼 읽는다
- 현재는 stem 이 숫자뿐이라 자동 제외됨 (오염은 없지만 문항 손실)

### 🟠 Major 5. 세트 간 문항 중첩
- 같은 학생의 10문항 세트가 30문항 세트의 부분집합 (선택 순서가 결정적이기 때문)
- 개선안: 세트별 offset/shuffle 또는 상위 세트 배정 문항 제외

### 🟠 Major 6. 개인화 커버리지 42%
- 리포트 토픽 40개 중 17개만 문제은행과 매칭 (`angle`, `perimeter`, `anagram`, `flaws in reasoning` 등 부재)
- 개선안: 토픽 alias 매핑 테이블 추가 또는 문제은행 확장

---

## 3. 남은 작업 (TODO)

- [ ] `run_pipeline.py` 학생 이름/ID 복원 (Critical 1) — **파이프라인 재실행 전 필수**
- [ ] OCR 폴백 실제 연결 또는 dead code 정리 (Critical 2)
- [ ] 잔여 ENG 시험지 약 40편 + MATH/TS 배치 추출
- [ ] 사용자가 제공할 **추가 시험지 경로** 반영
- [x] LLM 파이프라인 실제 생성 실행 → **9섹션 / 45문항 완료**
- [ ] 생성 문항 **사람 검수** → `verified: true` 승격 (샘플링 검수 기준 필요)
- [ ] `--mode new` 로 **새 지문 생성** 시도 (현재는 기존 지문 재사용만)
- [ ] OpenAI 크레딧 충전 후 provider 교차 검증 (현재 `insufficient_quota`)
- [ ] cloze 표 형식 파서 (2열 좌표 기반)
- [ ] 저신뢰 정답 검수 워크플로 (`exam_papers_review.json` 활용)
- [ ] README 의 "문제 은행: Math 15, Reading 10, Thinking 3" 수치 갱신 (실제 30/22/13 + 추출분)

---

## 5. 진행 중인 작업 (2026-10-29 세션 말)

- **연도별 아카이브 대량 추출 ✅ 완료** (OC/STT 2022~2025, ENG 333편)
  - 결과: 5,793문항 / 정답 3,593(62.0%) / 긴 지문 정답 3,465
  - `data/questions/exam_papers_raw.json` (append 방식, `--skip-existing` 로 재개 가능)
- 이후 파이프라인 ✅ 완료:
  ```powershell
  python tools/build_reading_db_from_papers.py --min-questions 2   # 329섹션/1,017문항
  python tools/generate_personalized_practice_sets.py --test-type Selective --round 26
  python tools/generate_personalized_practice_sets.py --test-type OC --round 11
  python tools/check_duplicates.py     # 중복 0
  ```
- 남은 후보 작업:
  - MATH / TS 과목 추출 (`--subjects ENG MATH TS`)
  - `exam_papers_review.json` 1,558건 정답 미판정분 검수
  - `--mode new` 로 새 지문 생성 확대

---

## 6. 검증 체크리스트 (커밋 전 실행)

```powershell
# 1) 문제은행 로드 상태
python -c "import sys; sys.path.insert(0,'tools'); import generate_personalized_practice_sets as g; g.load_pool()"

# 2) 세트 내 중복 0
python tools/check_duplicates.py

# 3) PDF 에 과목별 문항이 실제로 들어갔는지
python -c "from pypdf import PdfReader; import glob; [print(f, (t:=''.join(p.read_text() or '' for p in PdfReader(f).pages)).count('[Reading'), t.count('[Mathematical'), t.count('[Thinking')) for f in glob.glob('output/*/personalised_practice_*/*/student_practice.pdf')[:3]]"

# 4) 스크립트 컴파일
python -m py_compile tools/generate_personalized_practice_sets.py tools/extract_exam_papers.py tools/build_reading_db_from_papers.py
```

최종 통과 기준: ① Pool 로드 정상 ② 중복 0 ③ 세트 크기 10/20/30 정확 ④ 3과목 모두 포함 ⑤ 컴파일 오류 0
