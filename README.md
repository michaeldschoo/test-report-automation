# EduKingdom Report Automation System (ERAS) 사용자 가이드

본 시스템은 EduKingdom College 사이트에서 **Online Selective Test** 및 **Term Test** 리포트를 자동으로 다운로드하고 학생별로 통합 PDF를 생성하는 도구입니다.

## 1. 주요 기능
- **통합 모드 지원**: 실행 시 Selective Test 또는 Term Test 중 선택 가능.
- **Term Test 전 학년 자동화**: Year 1부터 Year 6까지 순차적으로 전체 리포트 처리.
- **스마트 탐색**: 테이블 내에서 지정된 패턴(`Year [학년] Term Test [과목] [Term 번호]`)으로 리포트 자동 검색.
- **자동 병합**: 과목별로 분산된 PDF 파일을 학생별 하나의 통합 리포트로 병합.
- **계층적 저장**: 결과물을 모드/학년/회차별로 자동 분류하여 저장.

## 2. 다른 컴퓨터에서 실행하기 위한 준비 사항

### 필수 소프트웨어
1. **Python 3.8+**: [python.org](https://www.python.org/)에서 설치.
2. **Google Chrome**: 브라우저 설치 권장.

### 환경 설정 절차
복사한 프로젝트 폴더 내에서 터미널(명령 프롬프트)을 열고 다음 명령어를 실행합니다.

```powershell
# 1. 필수 라이브러리 설치
pip install -r requirements.txt

# 2. 브라우저 자동화 도구 설치
playwright install chromium
```

### 계정 설정 (`.env` 파일)
프로젝트 루트 폴더에 `.env` 파일을 생성하고 다음과 같이 입력합니다.
```env
BRANCH_USERNAME=당신의_아이디
BRANCH_PASSWORD=당신의_비밀번호
```

## 3. 실행 방법
터미널에서 다음 명령어를 입력합니다.
```powershell
python main.py
```

1. **메뉴 선택**: `1` (Selective) 또는 `2` (Term Test)를 입력합니다.
2. **번호 입력**: 다운로드할 **회차 번호**(Selective) 또는 **Term 번호**(Term Test)를 입력합니다.
3. **자동 작업**: 브라우저가 열리고 로그인이 진행된 후 다운로드 및 병합이 시작됩니다.

## 4. 결과물 확인
- **다운로드 원본**: `downloads/` 폴더 내에 저장됩니다.
- **최종 통합 리포트**: `output/` 폴더 내에서 학생 이름별로 확인 가능합니다.

## 5. 새 시험 회차 주간 처리

새 회차의 학생별·과목별 결과를 병합한 뒤, 해당 회차만 파싱하고 질문 은행과 Progress report를 갱신합니다. 명령은 프로젝트 루트에서 실행합니다.

### 1단계: 학생별 과목 결과 병합

```powershell
python main.py
```

대화형 메뉴에서 시험 종류와 회차를 입력합니다.

- Selective: `1` 선택 → 새 **Round 번호** 입력
- Term Test: `2` 선택 → 새 **Term 번호** 입력
- OC Trial: `3` 선택 → 새 **Round 번호** 입력

로그인 후 과목별 PDF를 내려받고 학생별 PDF로 병합합니다. Selective/OC 병합 결과는 각각 `output/Selective_R<회차>/`, `output/OC_R<회차>/`에 저장됩니다. 메뉴의 `5`로 종료합니다.

### 2단계: 회차 데이터 파싱 및 Progress report 생성

1단계에서 처리한 시험 종류와 회차에 맞는 명령을 실행합니다.

```powershell
# 예: Selective Round 23
python run_pipeline.py --test-type Selective --round 23

# 예: OC Round 8
python run_pipeline.py --test-type OC --round 8

# 예: Term Test Term 3
python run_pipeline.py --test-type TermTest --round 3
```

`--round`를 함께 지정하면 해당 회차만 파싱·보고서 생성합니다. 파싱 결과는 기존 `output/parsed_reports_v2.json`에 병합되고, `output/question_bank_by_type.json`은 전체 누적 데이터 기준으로 다시 생성됩니다. 매 회차마다 별도의 명령을 실행해 주세요.

### 3단계: 완료 확인

터미널 요약에서 파싱한 PDF 수, 생성 보고서 수, 실패 수를 확인합니다. 출력은 다음 위치에 저장됩니다.

- 파싱 데이터: `output/parsed_reports_v2.json`
- 질문 은행: `output/question_bank_by_type.json`
- Progress reports: Selective `output/Selective_R<회차>/`, OC `output/OC_R<회차 두 자리>/`
- Term Test 보고서: 각 해당 Year 결과 폴더

보고서 생성이 실패하거나 PDF가 누락된 경우, 원본 병합 PDF와 터미널 오류를 확인한 뒤 회차를 다시 처리하세요. `main.py`를 같은 회차에 다시 실행하면 기존 병합 PDF를 보존하기 위해 `_1` 같은 접미사가 붙을 수 있으므로, 재실행 전에는 해당 회차 폴더의 오래된 병합 PDF를 점검하세요. Progress report 파일은 삭제하지 마세요.

참고: `run_pipeline.py`는 프로젝트 루트에 있습니다. 결과 JSON과 질문 은행은 `output/` 바로 아래에 저장됩니다.

---
**주의사항**: 실행 중 PDF 파일이 다른 프로그램(Adobe Reader 등)에서 열려 있으면 병합 과정에서 오류가 발생할 수 있습니다. 결과 파일을 확인하기 전에는 이전 결과 파일을 닫아주세요.
