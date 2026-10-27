# NSW Selective High School Reading Test 분석

## 📋 시험 구조 분석 (40분, 30문항)

### Part 1: Linked Extracts (문항 1-8)
- **형식**: 2개의 긴 문학 작품 발췌문 (각 300-500단어)
- **특징**: 
  - 소설, 에세이, 자서전 등 다양한 장르
  - 서사적 묘사가 풍부하고 문학적 표현이 많음
  - 두 발췌문의 공통점/차이점을 비교하는 문제 포함
- **예시**: 
  - Extract A: "Picnic at Hanging Rock" (역사 소설, 1900년대 배경)
  - Extract B: "Gold Coast Theme Park" (현대 에세이, 가족 여행)
- **문제 유형**:
  - 두 발췌문의 공통점 찾기
  - 특정 표현의 의미 추론
  - 등장인물/화자의 태도 파악
  - 암시적 의미 이해

### Part 2: Poetry (문항 9-14)
- **형식**: 1편의 시 (20-40행)
- **특징**:
  - 현대시, 고전시 모두 출제
  - 은유, 직유, 이미지 등 시적 장치 분석
  - 시의 구조와 형식도 문제로 출제
- **예시**:
  - "The Fish" by Marianne Moore (해양 생물과 절벽 묘사)
  - "The Curtain" by Judith Wright (부모와 자녀 관계)
- **문제 유형**:
  - 시적 장치 파악 (은유, 직유 등)
  - 단어/구절의 의미 해석
  - 시의 전체 주제 파악
  - 시의 형식과 내용의 관계

### Part 3: Cloze Exercise (문항 15-20)
- **형식**: 1개의 설명문/논설문 (400-600단어)
- **특징**:
  - 6개 문장이 제거됨 (7개 선택지 중 6개 선택)
  - 논리적 흐름과 문맥 파악 능력 테스트
  - 과학, 환경, 사회 이슈 등 비문학 지문
- **예시**:
  - "Octopus farming" (문어 양식의 윤리적/환경적 문제)
- **문제 유형**:
  - 논리적 연결 파악
  - 전후 문맥 이해
  - 주제 일관성 유지

### Part 4: Thematic Matching (문항 21-30)
- **형식**: 4개의 짧은 발췌문 (각 100-200단어)
- **특징**:
  - 공통 주제로 묶인 4개 지문
  - 10개 질문에 대해 어느 지문이 해당하는지 매칭
  - 빠른 스캐닝과 정확한 이해 필요
- **예시 주제**:
  - Dreams (꿈)
  - Communication (의사소통)
- **문제 유형**:
  - 특정 내용/아이디어가 언급된 지문 찾기
  - 유사한 표현을 다른 방식으로 묻기
  - 암시적 의미 파악

## 🎯 현재 생성기의 문제점

### 1. **지문 길이 부족**
- **현재**: 2-3문장의 짧은 stem
- **실제**: 300-600단어의 긴 문학/비문학 지문
- **영향**: 난이도가 실제 시험보다 훨씬 낮음

### 2. **문학적 깊이 부족**
- **현재**: 단순한 정보 전달 문장
- **실제**: 풍부한 묘사, 은유, 문학적 표현
- **영향**: 학생들이 실제 시험의 복잡한 문장 구조에 대비 불가

### 3. **문제 유형 불일치**
- **현재**: 단순 사실 확인 문제
- **실제**: 추론, 해석, 비교, 암시적 의미 파악 등 고차원 사고
- **영향**: 실제 시험에서 요구하는 사고력 훈련 불가

### 4. **Cloze Exercise 형식**
- **현재**: "Cloze Exercise"라는 이름만 사용
- **실제**: 문장 삽입형 문제 (6 out of 7 선택)
- **영향**: 유일하게 쓸만하다고 평가받은 부분도 형식이 다름

## 💡 개선 방안

### 단기 해결책 (임시)
1. **Cloze Exercise만 유지**
   - 현재 평가: "쓸만함"
   - 이유: 문장 단위 문제라 짧은 지문으로도 가능
   
2. **Reading 문제 제외**
   - Linked Extracts, Poetry, Thematic Matching 제거
   - 이유: 긴 지문 필요, AI 생성 품질 보장 어려움

### 중장기 해결책 (근본적)
1. **실제 기출문제 은행 구축**
   - NSW 기출문제 3세트 분석 및 DB화
   - J 드라이브 경로: `J:\My Drive\EKC  OFFICE\STT - NEW\STT Gov TEST\`
   - 파일들:
     - Sample Test: `Reading-Sample-Test-Questions.pdf`
     - 2023: `SHS-2023-Reading-practice-test-questions.pdf`
     - 2022: `0322_SHSPT_READING_QUESTION_PAPER.pdf`
     - 2021: `Practice test 2021 Reading questions (1).pdf`

2. **지문 재사용 방식**
   - 기출 지문을 그대로 사용
   - 문제만 학생 약점에 맞춰 선택
   - 예: Poetry 약점 → 기출 시 3편 중 1편 제공

3. **혼합 방식**
   - 긴 지문: 기출문제 재사용
   - 짧은 Cloze: AI 생성 유지
   - Mathematical/Thinking Skills: AI 생성 가능 (짧은 문제)

## 📝 필요한 작업

### 1단계: 기출문제 파싱 및 DB 구축
```python
# 필요한 데이터 구조
{
  "question_type": "Linked Extracts",
  "source": "NSW Sample Test",
  "year": 2023,
  "extract_a": {
    "title": "Picnic at Hanging Rock",
    "author": "Joan Lindsay",
    "text": "...",
    "word_count": 450
  },
  "extract_b": {
    "title": "Gold Coast Theme Park",
    "author": "Unknown",
    "text": "...",
    "word_count": 380
  },
  "questions": [
    {
      "qn": 1,
      "stem": "Both extracts mention...",
      "options": ["A...", "B...", "C...", "D..."],
      "answer": "C",
      "skill": "comparison",
      "topic": "narrative"
    }
  ]
}
```

### 2단계: 학생 약점 매칭 로직
```python
# 학생 약점: Poetry 60% 오답률
# → 기출 Poetry 문제 중 1개 선택
# → 전체 지문 + 6문제 제공

# 학생 약점: Linked Extracts 50% 오답률
# → 기출 Linked Extracts 1세트 선택
# → 전체 지문 + 8문제 제공
```

### 3단계: PDF 생성 개선
- 긴 지문 + 여러 문제 = 여러 페이지
- 실제 시험지 형식 재현
- 학생용: 지문 + 문제
- 교사용: 지문 + 문제 + 상세 해설

## 🤔 의사결정 필요 사항

1. **기출문제 저작권 문제**
   - NSW 정부 공개 문제 → 교육 목적 사용 가능할 것으로 판단
   - 하지만 확인 필요

2. **문제 은행 구축 범위**
   - 4개 기출 세트만? (2021-2023 + Sample)
   - 추가 상업 문제집 구매?

3. **맞춤 문제 생성 방식**
   - 완전 자동: 약점 → 기출 문제 매칭
   - 반자동: 교사가 기출 문제 선택, 시스템이 PDF 생성
   - 수동: 기출 문제 은행만 제공, 교사가 직접 선택

## 📌 추천 방향

**단기**: Cloze Exercise만 AI 생성 유지, 나머지 Reading 제외

**중기**: 기출 문제 DB 구축 → 학생 약점 기반 자동 매칭

**장기**: 상업 문제집 추가 구매 → 더 다양한 문제 은행 확보
