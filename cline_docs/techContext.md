# Tech Context — 기술 스택과 환경

---

## 1. 런타임

| 항목 | 값 |
|---|---|
| OS | Windows 10/11 (PowerShell) |
| Python | **3.12.5** (pyenv-win: `C:\Users\mc.WIN10-MODULATOR\.pyenv\pyenv-win\versions\3.12.5`) |
| 프로젝트 루트 | `D:\EKCRPA\test-report-automation` |
| 인코딩 | 모든 JSON/py 는 **UTF-8**. PowerShell 콘솔(cp949)에서 한글이 깨져 보이는 것은 표시 문제일 뿐 파일은 정상 |

---

## 2. 외부 의존성

| 패키지 | 용도 |
|---|---|
| `playwright` (+ chromium) | EduKingdom 사이트 로그인/다운로드 |
| `pypdf` | 결과지 PDF 텍스트 추출, 생성 PDF 검증 |
| `reportlab` | Progress Report / 문제집 PDF 생성 |
| `pdf2image` | PDF → 이미지 변환 (poppler 필요) |
| `pytesseract` | OCR (Tesseract) |
| `numpy` | 정답 판정용 이미지 잉크 밀도 계산 |

설치:
```powershell
pip install -r requirements.txt
playwright install chromium
```

---

## 3. 시스템 도구 (중요)

| 도구 | 경로 / 설정 | 비고 |
|---|---|---|
| **Poppler** | `F:\poppler-26.09.0\Library\bin` | `tools/ocr_engine.py`, `tools/ocr_pdf.py`, `tools/extract_exam_papers.py` 에 하드코딩 (환경변수 `POPPLER_PATH` 로 덮어쓰기 가능) |
| **Tesseract** | 시스템 PATH | `lang='eng'`, 300dpi. **`--psm 4` 필수** (psm 3 은 보기 라벨 유실) |

> ⚠️ Poppler 경로가 바뀌면 위 3개 파일의 `POPPLER_PATH` 상수를 수정해야 한다.

---

## 4. 계정/설정

`.env` (git 추적 제외):
```env
BRANCH_USERNAME=...
BRANCH_PASSWORD=...
GEMINI_API_KEY=...      # LLM 문제 생성용 (또는 GOOGLE_API_KEY)
# OPENAI_API_KEY=...    # OpenAI 사용 시
```

---

## 5. 표준 실행 명령

```powershell
# 1) 결과 PDF 수집·병합
python main.py

# 2) 회차 파싱 + Progress Report
python run_pipeline.py --test-type Selective --round 26
python run_pipeline.py --test-type OC --round 11

# 3) 맞춤 문제집 생성
python tools/generate_personalized_practice_sets.py --test-type Selective --round 26
python tools/generate_personalized_practice_sets.py --test-type OC --round 11

# 4) 검증
python tools/check_duplicates.py
```

### 시험지 DB 확장 (신규 파이프라인)
```powershell
# J: 드라이브 시험지 OCR 추출 (기본: ENG, 전체 루트 2곳)
python tools/extract_exam_papers.py                 # 전체 (오래 걸림: 편당 약 30~40초)
python tools/extract_exam_papers.py --limit 10      # 10편만
python tools/extract_exam_papers.py --match "STT26 ENG" --limit 1
python tools/extract_exam_papers.py --subjects ENG MATH TS

# 추출 결과를 생성기 DB 로 병합
python tools/build_reading_db_from_papers.py --dry-run
python tools/build_reading_db_from_papers.py
```

### LLM 문제 생성 (신규)
```powershell
# 프롬프트만 확인 (API 호출 없음)
python tools/generate_questions_llm.py --dry-run --limit 1 --questions 5

# API 키 없이 파이프라인 동작 검증 (임시 파일로만 출력)
python tools/generate_questions_llm.py --mock --limit 2 `
  --out "$env:TEMP\mock_generated.json" --review "$env:TEMP\mock_review.json"

# 실제 생성 (Gemini)
python tools/generate_questions_llm.py --mode passage --limit 10 --questions 5

# 새 지문 생성 (OpenAI 호환)
python tools/generate_questions_llm.py --mode new --provider openai --model gpt-4o-mini --limit 3

# 생성 후 문제집 재생성
python tools/generate_personalized_practice_sets.py --test-type Selective --round 26
```

---

## 6. 시험지 데이터 위치 (J: 드라이브)

```
J:\My Drive\EKC  OFFICE\STT - NEW\STT2027\TEST\        ← STT 회차 시험지 167 PDF
   STT10\STT10 ENG.pdf  /  STT10 ENG ANS.pdf  /  STT10 MATH.pdf  /  STT10 TS.pdf ...
J:\My Drive\EKC  OFFICE\OC - NEW\OC 2027\TEST\         ← OC 회차 (동일 구조)
```

- 파일명 규칙: `<회차> <과목>.pdf` + `<회차> <과목> ANS.pdf` (정답지)
- **모든 PDF 는 스캔 이미지 (텍스트 레이어 0)** → OCR 필수
- PDF 상단 `Student Name` 공란은 **정상** (학생 답안지가 아니라 빈 시험지)

---

## 7. 저장소 규칙 (.gitignore)

```
downloads/        추적 안 함 (원본 PDF)
output/           추적 안 함. 단 output/*.json, output/*.py, 매니페스트 JSON 은 추적
*.pdf, *.png      추적 안 함
__pycache__/      추적 안 함
```

---

## 8. 알려진 환경 이슈

| 이슈 | 대응 |
|---|---|
| 콘솔에서 한글 mojibake | 표시 문제. `$env:PYTHONIOENCODING='utf-8'` 설정 권장 |
| 긴 OCR 배치 실행 시 터미널 완료 감지 실패 | `*> log.txt` 로 리다이렉트 후 로그 파일 확인 |
| PDF 가 Adobe Reader 에 열려 있으면 병합 실패 | 실행 전 결과 PDF 닫기 |
| `git add` 시 `index.lock` 오류 | `.git/index.lock` 삭제 후 재시도 |
