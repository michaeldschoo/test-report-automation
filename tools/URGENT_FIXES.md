# 긴급 개선 사항 요약

## 🔴 발견된 문제점

### 1. 문제 중복 발생 ❌
**원인**: 
- 문제 은행이 작음 (Math 15개, Reading 10개, Thinking 3개 = 총 28개)
- 30문항 세트 생성 시 부족한 문제를 반복 재사용
- 중복 체크 로직 부재 (라인 84-85)

**현재 코드 문제**:
```python
# tools/generate_personalized_practice_sets.py, 라인 84-85
while len(selected) < count:
    selected.append(dict(pool[index % len(pool)]))  # ❌ 무조건 추가!
    index += 1
```

### 2. Reading 지문 너무 짧음 ❌
**원인**: NSW 실제 시험은 300-600단어 긴 지문, 현재는 2-3문장
**예외**: Cloze Exercise는 "쓸만함" ✅

### 3. Math/Thinking Skills (확인 필요)
- 다이어그램 부재
- 문제 유형 다양성

---

## ⚡ 즉시 수정 사항 (Phase 1)

### 수정 1: 중복 방지 로직 추가
**파일**: `tools/generate_personalized_practice_sets.py`
**함수**: `select_questions()` (라인 73-86)

**수정 내용**:
```python
def select_questions(areas, count, pool):
    """중복 방지 + 부족 시 경고"""
    selected = []
    # 각 문제에 고유 ID 부여
    for q in pool:
        q["_id"] = hash(q.get("stem", "") + str(q.get("topic", "")))
    used_ids = set()
    
    # 1단계: 학생 약점 매칭
    for area in sorted(areas, key=lambda x: (-x["error_rate"], -x["wrong"])):
        wanted = area["topic"].lower()
        wanted_subject = area["subject"].lower()
        for q in pool:
            if q["_id"] in used_ids:
                continue  # 이미 사용한 문제 건너뛰기
            topic = q["topic"].lower()
            subject = q["subject"].lower()
            if wanted_subject == subject and (wanted == topic or wanted in topic or topic in wanted):
                selected.append(q)
                used_ids.add(q["_id"])
                if len(selected) >= count:
                    return selected[:count]
    
    # 2단계: 남은 문제로 채우기
    for q in pool:
        if len(selected) >= count:
            break
        if q["_id"] not in used_ids:
            selected.append(q)
            used_ids.add(q["_id"])
    
    # 3단계: 여전히 부족하면 경고
    if len(selected) < count:
        print(f"⚠️  Warning: Pool has only {len(pool)} unique questions, but {count} requested.")
        print(f"    Generated {len(selected)} unique questions.")
    
    return selected
```

### 수정 2: Reading 임시 조치

**옵션 A (추천)**: Cloze Exercise만 유지
```python
def load_pool():
    # ... MATH_POOL 로드 ...
    
    # Reading: Cloze만 필터링
    reading_all = pools.get("READING_POOL", [])
    reading = [dict(q, subject="Reading", verified=False) 
               for q in reading_all 
               if "Cloze" in q.get("topic", "")]
    
    print(f"ℹ️  Loaded {len(reading)} Cloze Exercise questions (other Reading types temporarily disabled).")
    return math + reading
```

**옵션 B**: Reading 완전 제거
```python
def load_pool():
    # ... MATH_POOL 로드 ...
    print("ℹ️  Reading questions disabled pending quality improvements.")
    return math  # Reading 없음
```

### 수정 3: 세트 크기 조정 (선택사항)
```python
# 라인 16-18
SET_COUNTS = {
    "10_questions_basic_review_set": 10,
    "15_questions_subject_weakness_focus_set": 15,  # 20→15
    "25_questions_mock_practice_set": 25  # 30→25
}
```

---

## 📋 작업 체크리스트

### 즉시 (오늘)
- [ ] `select_questions()` 함수 수정 (중복 방지)
- [ ] Reading 임시 조치 (Cloze만 또는 제거)
- [ ] README 업데이트 (제한사항 명시)
- [ ] 테스트: OC R11, Selective R26 재생성
- [ ] 중복 확인
- [ ] Git commit

### 1주일 내
- [ ] 현재 MATH_POOL 15개 분석
- [ ] 현재 생성된 샘플 품질 검토
- [ ] 기출문제와 비교
- [ ] 누락 유형 리스트 작성
- [ ] 문제 은행 확장 계획 수립

### 2-4주 (Phase 2)
- [ ] Math 문제 15→40개 확장
- [ ] Thinking Skills 3→20개 확장
- [ ] Cloze 추가 (현재 몇 개인지 확인 후)
- [ ] 테스트 및 피드백

### 중기 (1-2개월, Phase 3)
- [ ] Reading 근본 해결
  - 기출문제 DB 구축, 또는
  - LLM 긴 지문 생성
- [ ] Math/Thinking 다이어그램 개선

---

## 💬 의사결정 필요

**즉시 결정** (오늘):
1. 중복 방지 로직 적용? (추천: Yes)
2. Reading 임시 조치 방향?
   - A: Cloze만 (추천)
   - B: 완전 제거
   - C: 그대로 (경고만)
3. 세트 크기 조정? (30→25 또는 유지)

**1주 내**:
4. 문제 은행 확장 작업 진행? (Math/Thinking)

**2-4주**:
5. Reading 근본 해결 방향?
   - 기출문제 사용 승인 가능?
   - LLM API 예산?
   - 또는 제외 유지?

---

## 📊 예상 효과

**Before** (현재):
- 문제 은행: 28개
- 중복: 발생 (30개 세트에 28개 pool)
- Reading 품질: ❌

**After** (수정 후):
- 문제 은행: 28개 (동일, 단 중복 없음)
- 중복: 0%
- Reading 품질: ✅ (Cloze만) 또는 제거

**Phase 2 후** (1개월):
- 문제 은행: 60개+
- 중복: 0%
- Reading: ✅ (기출 또는 LLM)
- Math/Thinking: ✅ (다양한 유형)

---

## 🚀 즉시 시작 (승인 시)

1. 중복 방지 로직 구현 (2시간)
2. Reading 임시 조치 (1시간)
3. 테스트 및 재생성 (30분)
4. Git commit (10분)

**Total**: ~3.5시간

승인하시면 바로 시작합니다!
