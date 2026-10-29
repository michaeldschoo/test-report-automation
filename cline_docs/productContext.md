# Product Context — 왜 이 시스템이 필요한가

---

## 1. 사용자와 역할

| 사용자 | 목적 | 시스템과의 접점 |
|---|---|---|
| **원장/운영자** | 회차별 전 학생 성적 자동 정리, 학부모 상담 자료 | `main.py` 실행 → 병합 PDF, Progress Report |
| **교사** | 학생별 약점 파악 + 맞춤 문제집 배포 | `teacher_answer_key.pdf` (해설 포함), `questions.json` |
| **학생/학부모** | 취약 과목 집중 연습 | `student_practice.pdf` (정답 없는 학생용) |

---

## 2. 실제 운영 흐름 (회차 주간)

```
[월] 새 회차 시험 종료
  ↓
[화] python main.py               → 과목별 결과 PDF 다운로드 + 학생별 병합
  ↓
[수] python run_pipeline.py --test-type Selective --round 26
                                   → 정오답 파싱, 토픽별 약점 추출, Progress Report PDF
  ↓
[목] python tools/generate_personalized_practice_sets.py --test-type Selective --round 26
                                   → 학생 17명 × 3세트 = 51세트 PDF/JSON 생성
  ↓
[금] 교사가 PDF 검토 → 학생 배포
```

**중요**: 2단계와 3단계 사이에 사람이 개입할 필요가 없어야 한다.
현재 3단계는 `output/parsed_reports_v2.json` 이 있어야만 동작한다.

---

## 3. 문제집이 가져야 할 교수학적 성질

| 성질 | 이유 | 구현 상태 |
|---|---|---|
| **긴 지문 + 다문항** | 실제 Selective/OC 시험은 지문 1개에 6~10문항. 단문 1문항은 실전 대비 효과 없음 | ✅ `LONG_PASSAGE_MIN=300`, 지문 그룹 단위 선택 |
| **과목 누락 없음** | 학부모가 "우리 아이 문제집에 Reading 이 없다"고 항의하는 상황 방지 | ✅ `MIN_PER_SUBJECT=2` |
| **약점 가중 배분** | 성적이 좋은 과목에 시간을 쓰는 것은 비효율 | ✅ `allocate_counts()` |
| **정답/해설 제공** | 교사가 채점·설명해야 함 | ✅ teacher_answer_key.pdf |
| **세트 내 중복 없음** | 같은 문제 반복은 학습 효과 0 | ✅ stem 정규화 중복 제거, 1,260문항 중복 0 |
| **난이도 3단계** | 10문항(기본) → 20문항(약점) → 30문항(모의) | ✅ |

---

## 4. 사용자 경험상의 제약

- **PDF 는 반드시 인쇄 가능한 A4** 여야 한다 (학부모가 집에서 출력).
- 학생용에는 **정답·해설이 절대 노출되면 안 된다** (`answer_key=False` 경로).
- Reading 지문은 **읽기 좋은 박스 레이아웃**(회색 배경, 테두리)으로 표시한다.
- 파일명/폴더명은 `personalised_practice_<학생명>/<세트명>/` 규칙을 유지한다.

---

## 5. 품질 사고 이력 (반복 금지)

| 사고 | 원인 | 예방책 |
|---|---|---|
| "Reading 문제가 PDF에 안 보임" | 소스 DB 에 문항 0개 → 생성기가 지문만 렌더링 + 플레이스홀더 stem(`Read Extract ... carefully. - Q1`) + 더미 선택지(`A|B|C|D`) | `is_usable_question()` 게이트, 소스 DB 문항 수 경고 |
| "AI Studio 수정 후 더 망가짐" | `parse_reading_complete.py` 가 파싱 결과를 버리고 `questions: []` 로 덮어씀 | DB 덮어쓰기 금지 규칙, 병합 방식 사용 |
| 학생 이름이 전부 Anonymous | `run_pipeline.py` 의 하드코딩 회귀 | ❌ **미수정** (progress.md 참조) |

---

## 6. 비기능 요구사항

- **재현성**: 같은 입력이면 같은 출력. 실행마다 변하는 hash(`_id`)를 산출물에 저장하지 않는다.
- **투명성**: 생성 시 세트별 과목 배분을 콘솔에 출력하고 매니페스트에 `subject_counts` 로 남긴다.
- **확장성**: 새 시험지/회차가 추가되어도 코드 수정 없이 데이터만으로 동작해야 한다.
