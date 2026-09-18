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

## 5. 시험 결과 주간 처리
J: 드라이브에 시험 결과 PDF가 준비된 후 프로젝트 루트에서 전체 파이프라인을 실행합니다.

```powershell
# 결과 PDF 파싱, 질문 은행 갱신, 학생별 PDF 보고서 생성
python run_pipeline.py

# 특정 시험 유형만 처리
python run_pipeline.py --test-type OC
python run_pipeline.py --test-type Selective

# JSON은 기존 파일을 사용하고 보고서 PDF만 다시 생성
python run_pipeline.py --no-parse --no-bank

# 파싱과 JSON 갱신만 수행하고 PDF는 생성하지 않음
python run_pipeline.py --no-reports
```

파싱 결과와 질문 은행 JSON은 `output/`에 저장됩니다. `run_pipeline.py`는 프로젝트 루트에 있으므로 `output/output/`이 아니라 올바른 `output/` 경로를 사용합니다.

---
**주의사항**: 실행 중 PDF 파일이 다른 프로그램(Adobe Reader 등)에서 열려 있으면 병합 과정에서 오류가 발생할 수 있습니다. 결과 파일을 확인하기 전에는 이전 결과 파일을 닫아주세요.
