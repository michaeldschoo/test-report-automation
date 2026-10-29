# PROJECT MEMORY — 조사/검증 기록 로그

> 세션이 바뀌어도 유지되어야 하는 **실측 사실과 조사 근거**를 날짜별로 기록합니다.
> 규칙·요약은 [`AGENTS.md`](../AGENTS.md) 참조. 새 기록은 **최신 날짜를 맨 위**에 추가하세요.

---

## 2026-10-29 (5차) — LLM 실제 생성 실행 (45문항) + 연동 튜닝

### API 키 검증 결과
| Provider | 모델 | 결과 |
|---|---|---|
| Gemini | `gemini-2.0-flash` / `2.5-flash` / `2.5-pro` | ❌ 404 — "no longer available to new users" |
| Gemini | `gemini-flash-latest`, `gemini-3.8-flash` | ⚠️ 503 high demand (간헐적) |
| Gemini | **`gemini-3.5-flash`** | ✅ 200 (기본값으로 채택) |
| Gemini | `gemini-flash-lite-latest` | ✅ 200 (대안) |
| OpenAI | `gpt-4o-mini` | ❌ 429 `insufficient_quota` (크레딧 소진) |

- 인증은 기존 `?key=` 쿼리 파라미터로 정상 동작 (헤더 `x-goog-api-key` 도 동일).
- `responseMimeType: application/json` + `maxOutputTokens: 8192` 필요 (3.x 는 thinking 토큰 소모).

### 실행 결과 (mode=passage, 지문 10개 × 5문항)
```
[INFO] Pool loaded: 144 total questions (Math: 30, Reading: 101, Thinking: 13)
       LLM 생성 문항 포함: 45개 (generated_db.json)
생성: 9섹션 / 45문항, 검증 탈락 0건
문서 재생성: 21명 × 3세트 / 1,260문항 / 중복 0
```

### 실행 중 발견·수정한 3가지
1. **생성 문항의 topic 공간 불일치** — 생성 문항 topic 은 `Inference`/`Author's Purpose` 인데
   리포트 약점 토픽은 `Linked Extracts`/`Poetry` 등 → 선택에서 항상 밀림.
   → 생성기 적재 시 `topic = section["type"]`, `skill = 세부 유형` 으로 분리 (PDF 표시는 `skill`).
2. **한 지문에 문항 몰림** — 30문항 세트에서 Reading 12문항이 지문 1개에 집중.
   → `MAX_PER_PASSAGE = 8` 도입으로 지문당 최대 8문항, 나머지는 다음 지문으로 분산(2지문 구성).
3. **기출 독점** — 기출이 항상 먼저 선택됨 → **기출/LLM 교대 배치(round-robin)** 로 혼합.
   검증: 샘플 세트 Reading 12문항 중 6문항이 LLM 생성분.

### 남은 작업
- 생성 문항 사람 검수 → `verified: true` 승격
- `--mode new` (새 지문 생성) 시도
- OpenAI 크레딧 충전 후 provider 교차 검증

---

## 2026-10-29 (4차) — LLM 기반 문제 생성 파이프라인 구축

### 요구사항
- 기출 시험지 데이터를 **학습/참조**해서 새 문제를 생성하는 단계가 필요 (사용자 요청 2번).
- 생성 결과는 품질 게이트를 통과해야만 문제집에 투입.

### 설계 결정
- **런타임 생성 금지**: 생성기(문제집 조립)는 LLM을 호출하지 않는다.
  LLM 호출은 **오프라인 배치**로 분리 (`tools/generate_questions_llm.py`).
- 이유: 재현성·비용·검수 가능성. 런타임 LLM 호출은 결과가 매번 달라진다.
- 두 모드: `--mode passage`(기존 긴 지문 재사용 + 새 문항) / `--mode new`(새 지문 + 다문항)

### 구현
| 파일 | 내용 |
|---|---|
| `tools/generate_questions_llm.py` (신규) | exemplar 로드 → 프롬프트 → Gemini/OpenAI 호출 → JSON 파싱 → 구조 검증 → `generated_db.json` |
| `generate_personalized_practice_sets.py` | `load_pool()` 이 `generated_db.json` 도 로드 (`structure_ok`/`verified` 섹션만) |

### 검증 게이트 (탈락 시 `generated_review.json`)
stem 15자↑ / 선택지 4~5개 / 중복 선택지 금지 / 정답이 선택지 범위 내 / 해설 10자↑ / 기존·신규 stem 중복 금지

### 지원 모드
- `--dry-run`: API 호출 없이 프롬프트 미리보기 (키 불필요)
- `--mock`: 결정적 샘플로 파이프라인 전체 동작 검증 (임시 경로 출력)
- 실제 생성: `.env` 의 `GEMINI_API_KEY`(또는 `GOOGLE_API_KEY`) / `OPENAI_API_KEY`

### 실측 검증
```
--dry-run  → 프롬프트 생성 정상 (Lasseter 지문 + 스타일 참조 3문항 포함)
--mock     → 2섹션 / 8문항 생성, 탈락 0건
연동 테스트 → PRACTICE_GENERATED_DB 로 mock 주입 시 Pool 99 → 107 (mock 8문항 포함)
실제 풀     → generated_db 없을 때 99문항 유지 (기존 동작 불변)
문서 재생성 → 21명 × 3세트 / 1,260문항 / 중복 0
```

### 부수 버그 수정
- `load_pool()` 의 중복 키가 `stem[:80]` 절단이라, 앞 80자가 같은 서로 다른 문항이 병합되던 문제
  → `_stem_key()` 도입(공백/대소문자 정규화 + 전체 stem + topic)

### 남은 작업
- 실제 LLM 생성 실행 (API 키 필요)
- 생성 문항 사람 검수 후 `verified: true` 승격 기준 마련
- 기출 잔여 편(ENG 약 40편 + MATH/TS) 배치 추출

---

## 2026-10-29 (3차) — 기출 시험지 OCR 추출 파이프라인 구축

### 배경
- J: 드라이브 시험지 PDF 167개가 있으나 기존 DB화는 실패(130편 중 문항 있는 편 2개).
- 텍스트 추출 테스트 결과 **모든 시험지가 스캔 PDF(텍스트 레이어 0)** → OCR 필수.

### 핵심 발견 (실험으로 확정)
| 실험 | 결과 |
|---|---|
| pypdf 로 `STT26 ENG.pdf` 추출 | 0 chars (스캔본) |
| tesseract `psm 3` | 보기 라벨 유실 (`A ____ despite...` → `despite...`) |
| tesseract **`psm 4`** | `A ...` / `Cc ...` / `D___ ...` 형태로 안정 추출 ✅ |
| 정답지와 원본 이미지 diff | 모든 줄이 달라 사용 불가 |
| **잉크 밀도 비율(ANS/paper)** | 정답 보기 1.17~1.22 vs 오답 0.99~1.05 → **정답 판정 가능** ✅ |
| 검증 | STT26 정답 대조: 판정 7건 중 **오류 0건** |

### 구현
- `tools/extract_exam_papers.py`
  - poppler(300dpi, grayscale) + tesseract `--psm 4`
  - `Questions N to M.` 마커 기반 섹션 분할, 마커~첫 문항 사이 = 지문
  - 보기 라벨 변형 처리(`Cc`, `D___`, `A __`, 라벨 유실), stem 줄바꿈 판정(줄 간격 <30px)
  - 정답 판정: `ANSWER_MIN_RATIO=1.08`, `ANSWER_MIN_MARGIN=0.05`
  - 출력: `data/questions/exam_papers_raw.json`, 미판정 문항은 `exam_papers_review.json`
- `tools/build_reading_db_from_papers.py`
  - 긴 지문(≥300자) + 정답 문항 ≥3 + stem 미절단 조건으로 채택
  - 기존 DB 보존 병합 (지문/문항 중복 제거)

### 실측 결과
```
배치(ENG 7편): 문항 92개 추출 / 정답 판정 54개
DB 병합: reading_complete_db.json  1섹션/8문항 → 10섹션/42문항
생성기: Pool 99문항 (Math 30, Reading 56, Thinking 13)
30문항 세트 배분: Reading 9~12 (학생별 상이, 8가지 조합), 긴 지문 2개 포함
검증: 21명×3세트 errors 0 / 중복 0
```

### 남은 한계
- cloze 표(2열) 형식 섹션은 파싱 불가 → 자동 제외 (문항 손실)
- 정답 미판정 38건 → `exam_papers_review.json` 검수 필요
- ENG 7편만 처리 (잔여 약 40편 + MATH/TS 미처리)
- LLM 기반 신규 문제 생성은 미구현

---

## 2026-10-29 (2차) — 문제 선별 정책 재설계 + 지식 베이스 도입

### 사용자 요구사항 (신규 확정)
1. Reading은 **긴 지문**만 사용
2. 지문 1개에 **여러 문항**을 묶는 조합 선호
3. 맞춤 문제집은 **모든 과목 포함**
4. 문항 수는 학생별 **과목 성적에 따라 유동 조정**
5. J: 시험지 PDF는 학생 답안지가 아니라 **빈 시험지(원본 데이터)** → `Student Name` 공란이 정상

### 구현 내용 (`tools/generate_personalized_practice_sets.py`)
| 항목 | 내용 |
|---|---|
| `is_usable_question()` | 더미(`A|B|C|D`)·플레이스홀더 stem·정답 범위 오류 문항 배제 |
| `normalize_subject()` | `Selective Trial Test Reading Skills` → `Reading` 등 표준화 |
| `subject_accuracy(report)` | 리포트 과목별 정답률(0~1) 추출 |
| `allocate_counts(count, report, stock)` | 약점 가중치(`1 + (1-정답률)×2`) + 최소 2문항 보장 + 재고 한도 |
| `group_reading_by_passage()` | Reading을 지문 단위로 그룹화 |
| `select_questions(..., report)` | 긴 지문 그룹 우선 → 그룹 내 다문항 연속 배정, 과목별 유동 배분 |
| 기타 | `generated_at` 동적화, `questions.json`에서 `_id` 제거, 매니페스트에 `subject_counts` 추가, 동일 stem 중복 제거 |

### 검증 결과
| 항목 | 결과 |
|---|---|
| 21명 × 3세트 전수 검사 | errors **0** |
| 세트 크기 | 10 / 20 / 30 정확 |
| 과목 누락 | 0건 (모든 세트에 3과목 포함) |
| Reading 지문 수 | 세트당 **1개 긴 지문** (Lasseter, 4,419자) |
| Reading 문항 | 10문항 세트 3~4개 / 20문항 6~8개 / 30문항 8개 |
| 배분 변화 | 10문항 세트 3가지, 20문항 5가지, 30문항 3가지 조합 |
| 중복 | `check_duplicates.py` → 1,260문항 **중복 0** |
| PDF 실측 | 30문항 세트: Reading 8 + Math 12 + Thinking 10 |

### 발견/수정한 버그
- 문제은행에 **동일 stem이 서로 다른 `_id`** 로 존재(사고력 기본 템플릿 3개가 pool.json과 중복) → 세트 내 중복 88건 발생 → stem 정규화 기준 dedupe로 해결

### 남은 한계
- 긴 지문 Reading 재고 **1세트 8문항** → Reading이 모든 학생 8문항으로 포화, 내용도 동일
- 개선하려면 긴 지문 세트를 3~4개 이상으로 확충해야 함 (시험지 DB화 품질 개선 필요)

### 지식 베이스 도입
- `AGENTS.md` (규칙·요약) / `docs/PROJECT_MEMORY.md` (상세 로그) 신규 생성
- 목적: 모델/세션 교체 시 조사 결과 유실 방지

---

## 2026-10-29 (1차) — "Reading 문제가 생성되지 않음" 원인 분석

### 신고 증상
1. (전일) Reading 긴 지문은 PDF에 나오는데 **문제(문항)가 보이지 않음**.
2. Google AI Studio에서 수정 시도 후 오히려 **Reading 문항이 아예 생성되지 않음**.

### 조사 방법
- 산출물 PDF 텍스트 추출(`pypdf`)으로 과목별 문항 수 실측
- 생성기 `load_pool()`, `select_questions()`, `make_pdf()` 실행 추적
- `data/questions/*.json` 전수 스키마 검사
- `git log -S` 로 placeholder stem 문자열 계보 추적
- J: 드라이브 시험지 PDF 텍스트 추출 품질 확인

### 원인 체인 (확정)

| # | 원인 | 근거 |
|---|---|---|
| 1 | **Reading 소스 DB에 문항이 0개** | `reading_nsw.json`(questions 키 없음), `reading_nsw_db.json`(0문항), `nsw_reading_parsed.json`(0문항), `full_nsw_db.json`(130편 중 문항 있는 편 2개, 총 7문항) |
| 2 | `tools/parse_reading_complete.py`가 **파싱 결과를 버림** | 파싱한 `questions` 변수를 사용하지 않고 `"questions": []`로 저장 (스크립트 실행 시 DB 문항 전멸) |
| 3 | 문항이 없으니 생성기가 **플레이스홀더 stem + 더미 선택지**를 사용 | 산출물 `questions.json`에 `stem="Read Extract A: Lasseter's Lost Reef carefully. - Q1"`, `options="A|B|C|D"` → PDF에 지문만 보이고 문제 내용 없음 |
| 4 | Old 산출물은 Reading 0문항 | Selective_R26 PDF 실측: `[Reading=0, [Math=10, [Thinking=10` (10문항 세트가 20문항이 됨) |
| 5 | OC 산출물은 30문항 고정 + placeholder | OC_R11 실측: `[Reading=10` 이지만 전부 placeholder stem |

### 조치 및 검증 결과
- `is_usable_question()` 게이트 추가: 더미 선택지(`A|B|C|D`), 빈 stem, 플레이스홀더 stem, 정답 범위 오류 문항 배제
- `reading_complete_db.json`에 정식 8문항(실제 stem/선택지 A~E/정답/해설, 지문 4,419자) 확보
- 산출물 재생성 후 실측:

| 검증 항목 | 결과 |
|---|---|
| pool 로드 | 65문항 (Math 30, Reading 22, Thinking 13) |
| 세트 크기 | 21명 × (10/20/30) 전원 정확 |
| Reading 배분 | 10문항 세트 4개 / 20문항 7개 / 30문항 10개 |
| Reading 0인 학생 | 0명 |
| 더미/플레이스홀더 선택 | 0건 |
| 세트 내 중복 | 0건 (`check_duplicates.py`: 21명/63세트/1,550문항) |
| 컴파일 | `tools/*.py` + `run_pipeline.py` 오류 0 |
| PDF 렌더 | student/teacher PDF 정상 생성 |

### 남은 구조적 문제
- 긴 지문 Reading 재고가 **1세트(8문항)** 뿐 → 30문항 세트에서 Reading은 10이 아닌 8 수준이 한계
- 세트 간 문항 중첩: 같은 학생의 10문항 세트가 30문항 세트의 부분집합(overlap 10/10)
- 리포트 주제 ↔ 문제은행 주제 매칭률 **17/40 (42.5%)** → `angle`, `perimeter`, `estimation`, `anagram`, `synonym`, `flaws in reasoning` 등 미매칭
- 학생 간 30문항 세트 평균 Jaccard 유사도 **0.58** (최대 0.94)

---

## 2026-10-29 — "시험지 PDF 학습 → 신규 문제 생성" 가능성 검토

### 사용자 질문
"J: 드라이브 TEST 폴더의 과목별 시험지 PDF를 DB화했는데, 이걸로 학습해서 새 문제를 생성하는 방식인가?"

### 답: **아니다. 현재는 검색·조립 방식이다.**
- 생성기는 **고정 문제은행에서 약점 주제로 골라 PDF를 조립**할 뿐, 학습/생성 모델이 없다.
- `pool.json`의 Math 30문항과 Thinking 13문항은 `tools/expand_math.py`, `tools/expand_thinking.py`에 **수작업으로 작성된 템플릿**이다.
- Reading 8문항은 `reading_complete_db.json`에 **수작업 정리된 문항**이다.
- 저장소에 LLM/생성 모델 연동 코드는 존재하지 않는다.

### DB화 실패 원인
- **정규식 파서**: `tools/build_full_db.py`의 패턴이 지문을 문항 본문으로 삼킴, 선택지는 text 안에 줄바꿈으로 섞임, 정답(`ANS` 파일) 파싱 없음 → 130편 중 2편만 성공
- **OCR 파서**: `stt26_eng_ocr.txt` 실측 결과 문항 stem은 정상 추출되나 **선택지 라벨(A/B/C/D)이 뭉개짐**
  - Q1: 선택지 라벨 없이 4줄 + 잡음(`a polite expression of praise.`, `00OU >}`)
  - Q4: `A ____ despite harsh financial times` 형태(가변적)
  - 결론: OCR만으로는 선택지·정답 자동 복원 불가 → 어제의 placeholder/dummy 사고로 이어짐

### 학습 데이터 확충을 위한 전제 조건 (권장 순서)
1. **추출기 재작성** (전체 작업의 약 80%)
   - 텍스트 레이어가 있는 PDF는 `pypdf` 우선 (실측: 결과지 PDF는 텍스트 완벽 추출), OCR은 폴백
   - 추출 스키마: `{source, test, round, subject, passage_id, passage, question_no, stem, options[4-5], answer, topic, difficulty}`
   - 정답은 `... ANS.pdf`에서 별도 추출해 병합
   - 검증 게이트: 옵션 4~5개 / 정답 A~E 범위 / stem 중복 0 / 지문-문항 연결 / 지문 길이 ≥ 300자
2. **스타일 프로파일링**: 토픽별 문항 유형·선택지 길이·정답 위치·난이도·지문 길이 분포화
3. **생성 단계(배치, 오프라인)**: LLM 또는 템플릿 슬롯 변형으로 신규 문항 생성 → 자동 검증 → 사람 검수 → `generated_db.json`에 `verified` 플래그와 함께 저장
4. **생성기 연동**: `load_pool()`이 `verified: true`인 생성 문항까지 읽도록 확장

### 환경 메모
- Poppler 설치 확인: `F:\poppler-26.09.0\Library\bin`
- Tesseract(`pytesseract`, `lang='eng'`, 300dpi) 사용
- J: TEST 폴더 PDF 167개 (ENG 52개, `ANS` 쌍 존재)

---

## 참고: 자주 쓰는 검증 명령

```powershell
# 문제은행 로드 상태 및 과목별/지문별 통계
python -c "import sys; sys.path.insert(0,'tools'); import generate_personalized_practice_sets as g; g.load_pool()"

# 산출물 세트 내 중복 검사
python tools/check_duplicates.py

# PDF에 과목별 문항이 실제로 들어갔는지 확인
python -c "from pypdf import PdfReader; import glob; [print(f, (t:=''.join(p.extract_text() or '' for p in PdfReader(f).pages)).count('[Reading'), t.count('[Mathematical'), t.count('[Thinking')) for f in glob.glob('output/*/personalised_practice_*/*/student_practice.pdf')[:5]]"
```
