# Project Brief — EduKingdom 리포트 자동화 & 맞춤 문제집 생성

> 이 문서는 프로젝트의 **존재 이유와 목표**를 정의하는 최상위 기준 문서입니다.
> 다른 Memory Bank 문서는 모두 이 문서를 기준으로 파생됩니다.

---

## 1. 한 줄 정의

EduKingdom College(시드니)의 **온라인 시험 결과 PDF를 자동 수집·파싱**하고,
학생별 성적 분석(Progress Report)과 **약점 기반 맞춤 문제집(10/20/30문항)** 을 자동 생성하는 시스템.

---

## 2. 해결하려는 문제

| 현재(수작업) | 목표(자동화) |
|---|---|
| 사이트에서 학생별·과목별 결과 PDF를 사람이 하나씩 다운로드 | `main.py` 가 로그인→다운로드→학생별 병합까지 자동 |
| 성적표를 사람이 읽고 약점을 정리 | `run_pipeline.py` 가 문항 단위 정오답을 파싱해 리포트 생성 |
| 학생마다 문제집을 손으로 편집 | `generate_personalized_practice_sets.py` 가 학생별 3세트 자동 생성 |
| 문제은행이 수작업 30~40문항에 머묾 | J: 드라이브 기출 시험지(167 PDF)를 OCR로 DB화해 재고 확장 |

---

## 3. 핵심 산출물

1. **학생별 통합 결과 PDF** — `output/Selective_R<회차>/`, `output/OC_R<회차>/`
2. **파싱 데이터 / 문제은행** — `output/parsed_reports_v2.json`, `output/question_bank_by_type.json`
3. **Progress Report PDF** — 학생별 과목·토픽 성취도
4. **맞춤 문제집** — 학생 폴더당 3세트
   - `10_questions_basic_review_set`
   - `20_questions_subject_weakness_focus_set`
   - `30_questions_15_to_20_minute_mock_practice_set`
   - 각 세트: `student_practice.pdf`, `teacher_answer_key.pdf`, `questions.json`
5. **회차 매니페스트** — `personalised_practice_manifest_R<회차>.json`

---

## 4. 반드시 지켜야 할 사용자 요구사항 (변경 금지)

1. **Reading 문항은 "긴 지문(long passage)" 기반이어야 한다.** 단문 1~2문장 지문 금지.
2. **지문 1개에 여러 문항(3~8개)을 묶은 조합을 선호**한다. (지문 1개 = 문항 1개 형태 지양)
3. 맞춤 문제집은 **모든 과목(Reading / Mathematical Reasoning / Thinking)을 포함**한다.
4. 문항 수는 학생별 **Progress Report 의 과목별 성취도에 따라 유동적으로** 배분한다.
   - 약한 과목 ↑, 강한 과목은 최소 보장. 고정 비율(4/4/2 등) 금지.
5. J: 드라이브 시험지 PDF는 **학생이 푼 답안지가 아니라 빈 시험지(문제 원본)** 이다.
   - 상단 `Student Name` 공란은 정상이며 버그가 아니다.
   - 이 PDF들은 **문제 생성·참고용 학습 데이터**로 보관된 것이다.

---

## 5. 성공 기준

- 파이프라인 3단계가 사람 손 없이 끝까지 실행된다.
- 모든 학생의 문제집에 3과목이 모두 포함되고, 문항 수가 학생별로 달라진다.
- Reading 은 항상 긴 지문 + 다문항 세트로만 출제된다.
- 세트 내 중복 문항 0, 더미/플레이스홀더 문항 0.
- 새 회차·새 시험지가 추가되어도 데이터만 넣으면 재생성된다.

---

## 6. 현재 범위 밖 (명시적 제외)

- 학생 개인정보의 외부 전송 (모든 처리는 로컬)
- 웹 UI / 대시보드
- 실시간 채점 (결과 PDF는 이미 채점된 산출물)

---

## 7. 문서 지도

| 문서 | 내용 |
|---|---|
| `projectbrief.md` (이 문서) | 목표·요구사항·성공 기준 |
| `productContext.md` | 사용자(원장/교사/학부모)와 사용 흐름 |
| `systemPatterns.md` | 아키텍처·모듈·데이터 흐름·설계 결정 |
| `techContext.md` | 기술 스택·환경·의존성·실행 명령 |
| `activeContext.md` | 지금 진행 중인 작업·최근 변경·다음 단계 |
| `progress.md` | 완료/미완료·알려진 버그·검증 수치 |
