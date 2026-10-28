#!/usr/bin/env python3
"""NSW 기출 Reading DB 통합 빌더"""
import json
import re
from pathlib import Path

# 파싱된 기출 데이터 로드
DB_PATH = Path("data/questions/reading_nsw_db.json")
PARSED_DATA = Path("tools/nsw_reading_parsed.json")

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def build_db():
    print("Reading 기출 DB 구축 시작...")
    
    db = []
    
    # 1. 기존 파싱된 샘플 데이터 로드
    if PARSED_DATA.exists():
        with open(PARSED_DATA, "r", encoding="utf-8") as f:
            parsed_data = json.load(f)
            
        for section in parsed_data.get("sections", []):
            def get_val(key):
                val = section.get(key, "")
                return clean_text(val) if isinstance(val, str) else ""
                
            entry = {
                "type": section.get("type"),
                "title": section.get("title"),
                "source": "NSW Selective Sample Test",
                "passage_a": clean_text(section.get("extract_a", {}).get("text", "") if isinstance(section.get("extract_a"), dict) else ""),
                "passage_b": get_val("extract_b"),
                "text": get_val("text"),
                "questions": section.get("questions", [])
            }
            db.append(entry)
        
    # 2. DB 저장
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Reading DB 생성 완료: {DB_PATH}")
    print(f"   총 {len(db)}개 섹션 포함")

if __name__ == "__main__":
    build_db()

