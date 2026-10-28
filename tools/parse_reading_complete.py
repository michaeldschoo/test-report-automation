"""
완전한 Reading 문제 파싱기
- 긴 지문(Extract) 추출
- 해당 지문에 대한 모든 문제(Questions 1-8) 추출
- 선택지 A/B/C/D 추출
- NSW 기출 및 TEST 폴더의 모든 영어 시험지 처리
"""

import re
import json
from pathlib import Path
from ocr_engine import ocr_pdf_to_text

def parse_reading_paper(text):
    """OCR 텍스트에서 Reading 지문과 문제를 완전히 파싱"""
    sections = []
    
    # 먼저 전체 문제 섹션을 찾아서 분리
    questions_start = re.search(r'^\d+\.\s+', text, re.MULTILINE)
    if questions_start:
        extracts_text = text[:questions_start.start()]
        questions_text = text[questions_start.start():]
    else:
        extracts_text = text
        questions_text = ""
    
    # 1. Extract (지문) 추출
    extract_pattern = r'Extract\s+([A-D])\s*[:：]?\s*([^\n]+)(.*?)(?=Extract\s+[A-D]|$)'
    extracts = re.findall(extract_pattern, extracts_text, re.DOTALL | re.IGNORECASE)
    
    for letter, title, extract_body in extracts:
        extract_clean = extract_body.strip()
        if len(extract_clean) < 100:  # 너무 짧은 건 무시
            continue
        
        full_title = f"Extract {letter}: {title.strip()}"
        
        # 2. 해당 Extract에 대한 Questions 찾기
        # 패턴: "Questions 1 to 8" 또는 "Questions 1-8"
        question_section_pattern = rf'Questions?\s+(\d+)\s*(?:to|fo)\s*(\d+).*?(?=Questions?|\Z)'
        
        # questions_text에서 문제 섹션 찾기
        q_match = re.search(question_section_pattern, questions_text, re.DOTALL | re.IGNORECASE)
        
        questions = []
        if q_match:
            start_q = int(q_match.group(1))
            end_q = int(q_match.group(2))
            q_block = q_match.group(0)
            
            # 3. 각 문제 파싱
            # 패턴: "1. 질문내용" 또는 "1 질문내용"
            for q_num in range(start_q, end_q + 1):
                q_pattern = rf'{q_num}[\.\)]\s*(.*?)(?={q_num+1}[\.\)]|\Z)'
                q_text_match = re.search(q_pattern, q_block, re.DOTALL)
                
                if q_text_match:
                    q_full = q_text_match.group(1).strip()
                    
                    # 선택지 추출 (A) B) C) D) 패턴)
                    options_pattern = r'([A-D])[\)\.]\s*([^\n]+)'
                    options = re.findall(options_pattern, q_full)
                    
                    # stem(질문 본문)은 선택지 앞까지
                    stem = re.split(r'[A-D][\)\.]', q_full)[0].strip()
                    
                    if options and len(options) >= 4:
                        questions.append({
                            "number": q_num,
                            "stem": stem,
                            "options": {opt[0]: opt[1].strip() for opt in options},
                            "answer": None  # 정답은 ANS 파일에서 추출
                        })
        
        # Extract만 일단 저장 (문제는 나중에 매칭)
        sections.append({
            "type": "Linked Extracts",
            "title": full_title,
            "passage": extract_clean,
            "questions": []  # 일단 빈 배열
        })
    
    return sections

def main():
    """모든 Reading 시험지를 파싱하여 완전한 DB 구축"""
    all_readings = []
    
    # 1. 기존 OCR 텍스트 파싱
    stt26_path = Path("stt26_eng_ocr.txt")
    if stt26_path.exists():
        text = stt26_path.read_text(encoding='utf-8')
        sections = parse_reading_paper(text)
        all_readings.extend(sections)
        print(f"✓ STT26: {len(sections)} sections parsed")
    
    # 2. TEST 폴더의 모든 영어 시험지 파싱
    test_folders = [
        Path(r"J:\My Drive\EKC  OFFICE\STT - NEW\STT2027\TEST"),
        Path(r"J:\My Drive\EKC  OFFICE\OC - NEW\OC 2027\TEST")
    ]
    
    for folder in test_folders:
        if not folder.exists():
            continue
        
        for pdf_file in folder.rglob("*ENG*.pdf"):
            print(f"Processing: {pdf_file.name}")
            try:
                ocr_text = ocr_pdf_to_text(str(pdf_file))
                sections = parse_reading_paper(ocr_text)
                all_readings.extend(sections)
                print(f"  ✓ {len(sections)} sections")
            except Exception as e:
                print(f"  ✗ Error: {e}")
    
    # 3. 완전한 DB 저장
    output_path = Path("data/questions/reading_complete_db.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(all_readings, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"✅ Complete Reading DB saved: {output_path}")
    print(f"   Total sections: {len(all_readings)}")
    print(f"   Total questions: {sum(len(s['questions']) for s in all_readings)}")
    
    # 샘플 출력
    if all_readings:
        sample = all_readings[0]
        print(f"\n📖 Sample section:")
        print(f"   Type: {sample['type']}")
        print(f"   Passage length: {len(sample['passage'])} chars")
        print(f"   Questions: {len(sample['questions'])}")

if __name__ == "__main__":
    main()
