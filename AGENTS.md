# AGENTS.md — 프로젝트 컨텍스트 & 작업 규칙

> 이 파일은 **AI 에이전트(Cline, Claude, Copilot 등)가 세션 시작 시 반드시 읽는 프로젝트 기억 파일**입니다.
> 모델이 바뀌거나 세션이 끊겨도 이전에 조사·검증한 사실을 잃지 않도록 유지합니다.
> 상세 조사 근거는 [`docs/PROJECT_MEMORY.md`](docs/PROJECT_MEMORY.md) 참조.

---

## 1. 프로젝트 정체성

EduKingdom College(시드니)의 **시험 결과 리포트 자동화 + 학생별 맞춤 문제집 생성** 시스템.

| 구성 | 역할 |
|---|---|
| `main.py` | EduKingdom 사이트 로그인 → 과목별 결과 PDF 다운로드 → 학생별 병합 |
| `run_pipeline.py` | 병합 PDF 파싱 → Progress Report PDF/JSON 생성 (`output/parsed_reports_v2.json`) |
| `tools/generate_personalized_practice_sets.py` | 학생 약점 기반 맞춤 문제집(10/20/30문항) 생성 |

### 실행 순서 (프로젝트 루트 기준)
```powershell
python main.py                                                   # 1) 결과 PDF 다운로드/병합
python run_pipeline.py --test-type Selective --round 26          # 2) 파싱 + Progress Report
python tools/generate_personalized_practice_sets.py --test-type Selective --round 26   # 3) 맞춤 문제집
```

---

## 2. ⚠️ 절대 잊지 말아야 할 사용자 요구사항

1. **Reading 문제는 반드시 "긴 지문(long passage)"을 사용한다.** 단문 1~2문장짜리 지문은 부적합.
2. **지문 1개에 문항 1개보다, 긴 지문 1개에 여러 문항(4~8개)을 묶은 조합을 선호한다.**
   - 표준 형태: `Extract A + Extract B`(Linked Extracts) + 8문항, 또는 긴 단일 지문 + 4~6문항.
3. **맞춤 문제집은 모든 과목(Reading / Mathematical Reasoning / Thinking)을 포함**해야 한다.
4. **문항 수는 학생별 Progress Report의 과목별 회차 성적에 따라 유동적으로 조정**한다.
   - 약한 과목에 더 많은 문항, 강한 과목은 최소 보장. 고정 비율(4/4/2 등) 금지.
5. J: 드라이브의 시험지 PDF는 **학생이 푼 답안지가 아니라 빈 시험지(문제 원본)** 이다.
   - 따라서 상단 `Student Name`이 공란인 것이 정상이며, 버그로 오해하지 않는다.
   - 이 PDF들은 **문제 생성/참고용 학습 데이터**로 보관된 것이다.

---

## 3. 데이터 인벤토리 (2026-10-29 실측)

| 파일 | 내용 | 상태 |
|---|---|---|
| `data/questions/pool.json` | math 30 / reading 23(유효 22) / thinking 13 | ✅ 사용 중 (수작업 작성 문항) |
| `data/questions/reading_complete_db.json` | 1 section, **8문항**, 지문 4,419자 (Lasseter + Oak Island) | ✅ 사용 중 (유일한 긴 지문+다문항 세트) |
| `data/questions/full_nsw_db.json` | 130편 파싱 결과 → **문항 있는 편 2개, 총 7문항** | ❌ 사실상 실패 (미사용) |
| `data/questions/reading_nsw_db.json` | 1 section, **문항 0** (지문만) | ❌ 미사용 |
| `data/questions/reading_nsw.json` | 2 section, questions 키 없음 (지문만) | ❌ 미사용 |
| `tools/nsw_reading_parsed.json` | 1 section, **문항 0** (지문만) | ❌ 미사용 |
| `output/parsed_reports_v2.json` | Selective R26 17명, OC R11 4명 | ✅ 파이프라인 입력 |

- **생성기가 실제로 읽는 것은 `pool.json` + `reading_complete_db.json` 두 개뿐**이다.
- Reading 긴 지문 재고는 현재 **1세트 8문항**뿐 → 30문항 세트에서 Reading 최대 8문항.

### J: 드라이브 시험지 (학습 데이터 원본)
- `J:\My Drive\EKC  OFFICE\STT - NEW\STT2027\TEST\` → PDF **167개** (ENG 52개, `STT<회차>\STT<회차> ENG.pdf` + `... ENG ANS.pdf` 쌍)
- `J:\My Drive\EKC  OFFICE\OC - NEW\OC 2027\TEST\` → 동일 구조
- 정답지는 `ANS` 접미사 파일에 존재 → 문항 DB화 시 **정답 키 소스**로 사용할 것.

---

## 4. 환경 / 의존성

- Python 3.12, `reportlab`, `pypdf`, `pdf2image`, `pytesseract`, `playwright`
- **Poppler 설치됨**: `F:\poppler-26.09.0\Library\bin` (하드코딩 위치 — 이동 시 `tools/ocr_engine.py`, `tools/ocr_pdf.py` 수정)
- Tesseract OCR 사용 (`lang='eng'`, 300dpi)
- `.gitignore`: `output/`의 PDF/PNG은 추적 안 함, `.json`/`.py`만 추적. `downloads/` 추적 안 함.

---

## 5. 알려진 버그 / 함정 (재발 주의)

| 심각도 | 위치 | 증상 |
|---|---|---|
| 🔴 Critical | `run_pipeline.py` `parse_pdf()` | `final_student_name = "Anonymous"` 하드코딩 → **모든 학생이 Anonymous**, `student_id`도 `None`으로 유실. PDF 원문에는 `Student Name: ... Student ID: ...`가 정상 존재. |
| 🔴 Critical | `run_pipeline.py` `parse_page()` | `ocr_pdf_to_text` import만 하고 미호출 → OCR 폴백 미동작 (dead code) |
| 🔴 Critical | `tools/parse_reading_complete.py` | 파싱한 questions를 버리고 `"questions": []`로 저장 → **이 스크립트를 실행하면 reading_complete_db.json의 문항이 전멸** |
| 🟠 Major | `output/` 산출물 | 구버전 코드로 생성된 stale 산출물이 섞여 있음. 코드 변경 후 반드시 재생성 |
| 🟠 Major | `generate_personalized_practice_sets.py` | `questions.json`에 `_id`(python `hash()`, 실행마다 변동) 유출 → 재현성 없음 |
| 🟠 Major | 동일 | 세트 간 문항 중첩(10 ⊂ 20 ⊂ 30) |
| 🟡 Minor | `README.md` | "문제 은행: Math 15, Reading 10, Thinking 3" — 실제와 불일치(30/22/13) |

### 과거 사고 이력
- **2026-10-29**: "Reading 문제가 PDF에 보이지 않음" 신고.
  - 원인: Reading 소스 DB에 **문항이 0개**였고, 생성기가 지문만 렌더링 + 플레이스홀더 stem(`Read Extract ... carefully. - Q1`) + 더미 선택지(`A|B|C|D`)를 사용.
  - 조치: `is_usable_question()` 게이트 추가(더미/플레이스홀더/정답오류 배제), `reading_complete_db.json`에 정식 8문항 확보, 산출물 재생성.

---

## 6. 코드 작업 규칙

1. **한국어 주석/독스트링** 유지 (기존 코드 스타일).
2. 문제 문항 형식은 반드시 아래 스키마 유지:
   `{subject, topic, difficulty, stem, passage, options("A|B|C" 형태의 파이프 구분), answer(A~E), explanation}`
3. **더미/플레이스홀더 문항을 절대 생성하지 말 것.** 선택지는 실제 4~5개, 정답은 선택지 범위 내.
4. 생성 로직 변경 시 **반드시 실측 검증**:
   ```powershell
   python -c "import sys; sys.path.insert(0,'tools'); import generate_personalized_practice_sets as g; pool=g.load_pool(); print(len(pool))"
   python tools/check_duplicates.py     # 세트 내 중복 0 확인
   ```
   PDF 검증은 `pypdf`로 텍스트 추출 후 과목별 문항 수 카운트.
5. 데이터를 덮어쓰는 스크립트(`build_*`, `parse_*`, `save_reading_db.py`)는 **백업/병합 없이 원본 DB를 비우지 않도록** 주의.
6. 임시 검증 스크립트는 저장소에 남기지 말고 `%TEMP%` 사용.

---

## 7. 문제 선별 정책 (2026-10-29 구현 완료)

### Reading — 긴 지문 + 다문항
- `LONG_PASSAGE_MIN = 300` 자 이상 지문만 Reading 후보로 사용 (`select_questions()`)
- 지문 **그룹 단위**로 선택 → 한 지문에 3~8문항이 함께 출제됨
- 약점 주제를 포함한 지문 그룹 → 긴 지문 → 문항 많은 지문 순으로 우선순위

### 과목별 유동 배분
- `allocate_counts(count, report, stock)` — 학생 Progress Report의 **과목별 정답률**로 가중치 계산
  - 가중치 = `1.0 + (1 - 정답률) × 2.0` (약한 과목일수록 큼)
  - `MIN_PER_SUBJECT = 2` — 모든 과목 최소 보장
  - 과목별 **가용 재고(stock)** 를 넘지 않음 → 재고가 부족한 과목은 다른 과목으로 자동 재분배
- 실측(Selective R26, 30문항): (8,12,10) / (8,11,11) / (8,10,12) 등 학생별로 달라짐

### 현재 한계 (반드시 인지)
- **긴 지문 Reading 재고가 1세트 8문항뿐** → Reading은 모든 학생이 최대 8문항으로 포화
  → 진짜 Reading 유동 배분을 위해선 긴 지문 세트를 최소 3~4개(24~32문항)로 늘려야 함
- 8문항이 모두 같은 지문이므로 Reading 내용은 학생 간 동일

### 중복 방지
- `select_questions()`에서 **동일 stem(정규화) 기준으로 풀 중복 제거**
- `main()`의 사고력 기본 템플릿도 기존 stem과 겹치면 추가하지 않음
- `questions.json`에는 `_id`를 저장하지 않음(실행마다 변하는 hash 유출 방지)
- 검증: `python tools/check_duplicates.py` → 21명/63세트/1,260문항 **중복 0**

---

## 8. 세션 종료 시 규칙

새로 발견한 사실/버그/결정이 있으면 **`docs/PROJECT_MEMORY.md`에 날짜와 근거를 추가**한다.
이 파일(AGENTS.md)은 규칙·요약만 유지하고, 상세 로그는 memory 문서로 분리한다.
