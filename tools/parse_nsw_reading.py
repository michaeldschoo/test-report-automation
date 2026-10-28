#!/usr/bin/env python3
"""NSW Selective Reading 기출문제 파싱"""
from pypdf import PdfReader
from pathlib import Path
import json
import re

BASE = Path(r"J:\My Drive\EKC  OFFICE\STT - NEW\STT Additional test papers\STT Sample Tests")
OUTPUT = Path(r"D:\EKCRPA\test-report-automation\tools")

def extract_text_by_page(pdf_path):
    """PDF의 각 페이지 텍스트 추출"""
    reader = PdfReader(pdf_path)
    return [reader.pages[i].extract_text() for i in range(len(reader.pages))]

def parse_linked_extracts(text):
    """Linked Extracts 파싱"""
    extract_a_match = re.search(r'Extract A:(.+?)(?=Extract B:|For questions)', text, re.DOTALL)
    extract_b_match = re.search(r'Extract B:(.+?)(?=For questions)', text, re.DOTALL)
    
    if not extract_a_match or not extract_b_match:
        return None
    
    extract_a = extract_a_match.group(1).strip()
    extract_b = extract_b_match.group(1).strip()
    
    title_a = re.search(r'from (.+?) by (.+?)\n', extract_a)
    
    return {
        "type": "Linked Extracts",
        "extract_a": {"text": extract_a, "title": title_a.group(1) if title_a else "Unknown"},
        "extract_b": {"text": extract_b}
    }

def parse_poetry(text):
    """Poetry 파싱"""
    title_match = re.search(r'Read the poem ["\']?(.+?)["\']? (?:below )?by (.+?) then', text)
    poem_match = re.search(r'then answer the questions\.\n(.+?)(?=For questions|\d+\s+The title)', text, re.DOTALL)
    
    if not poem_match:
        return None
    
    return {
        "type": "Poetry",
        "title": title_match.group(1).strip() if title_match else "The Poem",
        "author": title_match.group(2).strip() if title_match and len(title_match.groups()) > 1 else "Unknown",
        "text": poem_match.group(1).strip()
    }

def parse_cloze(text):
    """Cloze Exercise 파싱"""
    passage_match = re.search(r'Read the text below then answer the questions\.\n(.+?)(?=A\s+Fish farmers|For questions)', text, re.DOTALL)
    if not passage_match:
        return None
    
    passage = passage_match.group(1).strip()
    title_match = re.search(r'^(.+?)\n', passage)
    
    return {
        "type": "Cloze Exercise",
        "title": title_match.group(1).strip() if title_match else "Passage",
        "text": passage
    }

def main():
    print("NSW Selective Reading 기출문제 파싱 시작...")
    
    reading_pdf = BASE / "Reading-Sample-Test-Questions.pdf"
    pages = extract_text_by_page(reading_pdf)
    
    results = {"source": "NSW Selective Sample Test", "sections": []}
    
def parse_questions_from_text(text, start_q, end_q):
    """텍스트에서 질문 및 선택지 파싱"""
    questions = []
    # 각 질문 파싱 (예: '1 Both extracts...'에서 'For questions' 이전까지)
    for q_num in range(start_q, end_q + 1):
        # 질문 내용 파싱
        q_pattern = rf'{q_num}\s+(.+?)(?=\n(?:[A-D]\s+|{q_num+1}\s+|$))'
        q_match = re.search(q_pattern, text, re.DOTALL)
        if not q_match: continue
        
        stem = q_match.group(1).strip()
        
        # 선택지 파싱 (A, B, C, D)
        options = []
        for opt in ['A', 'B', 'C', 'D']:
            opt_pattern = rf'{opt}\s+(.+?)(?=\n(?:[A-D]\s+|{q_num+1}\s+|$))'
            opt_match = re.search(opt_pattern, text, re.DOTALL)
            if opt_match:
                options.append(opt_match.group(1).strip())
        
        questions.append({"qn": q_num, "stem": stem, "options": options})
    return questions

def main():
    print("NSW 기출문제 파싱 및 DB 구축 시작...")
    reading_pdf = BASE / "Reading-Sample-Test-Questions.pdf"
    pages = extract_text_by_page(reading_pdf)
    results = {"source": "NSW Selective Sample Test", "sections": []}
    
    # 1. Linked Extracts (P3-4)
    combined = pages[2] + pages[3]
    linked = parse_linked_extracts(combined)
    if linked:
        linked["questions"] = parse_questions_from_text(combined, 1, 8)
        results["sections"].append(linked)
        print(f"  ✓ Linked Extracts: {len(linked['questions'])} 문항")
    
    # 2. Poetry (P6-7)
    combined = pages[5] + pages[6]
    poetry = parse_poetry(combined)
    if poetry:
        poetry["questions"] = parse_questions_from_text(combined, 9, 14)
        results["sections"].append(poetry)
        print(f"  ✓ Poetry: {len(poetry['questions'])} 문항")
    
    # 3. Cloze (P8-9)
    combined = pages[7] + pages[8]
    cloze = parse_cloze(combined)
    if cloze:
        cloze["questions"] = parse_questions_from_text(combined, 15, 20)
        results["sections"].append(cloze)
        print(f"  ✓ Cloze: {len(cloze['questions'])} 문항")
    
    with open(OUTPUT / "reading_nsw.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n완료: data/questions/reading_nsw.json 생성됨")

