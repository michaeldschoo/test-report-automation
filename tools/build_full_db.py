import json
import re
from pathlib import Path
from pypdf import PdfReader

# 데이터 저장 경로
POOL_DIR = Path("data/questions")
POOL_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = POOL_DIR / "full_nsw_db.json"

def parse_question_paper(pdf_path):
    """시험지 PDF에서 지문과 문제를 파싱"""
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except:
        return None

    # 과목 및 회차 인식 (파일명 기반이 더 정확할 수 있음)
    fname = Path(pdf_path).name
    subj_match = re.search(r'(ENG|MATH|TS)', fname, re.IGNORECASE)
    round_match = re.search(r'(\d+)', fname)
    
    subject = subj_match.group(1).upper() if subj_match else "UNKNOWN"
    round_no = round_match.group(1) if round_match else "0"

    # 지문 파싱 (Extract 패턴)
    extracts = re.findall(r'(Extract [A-D]:.*?)(?=\nExtract [A-D]:|\nQuestions|\Z)', text, re.DOTALL)
    
    # 질문 파싱 (번호 패턴)
    questions = re.findall(r'(\d+)\.\s+(.*?)(?=\n\d+\.|\Z)', text, re.DOTALL)
    
    return {
        "file": fname,
        "subject": subject,
        "round": round_no,
        "extracts": [e.strip() for e in extracts],
        "questions": [{"qn": q[0], "text": q[1].strip()} for q in questions]
    }

def build_all():
    # TEST 폴더 내 모든 PDF 순회
    test_folders = [
        Path(r"J:\My Drive\EKC  OFFICE\STT - NEW\STT2027\TEST"),
        Path(r"J:\My Drive\EKC  OFFICE\OC - NEW\OC 2027\TEST")
    ]
    
    db = []
    for folder in test_folders:
        for pdf in folder.rglob("*.pdf"):
            if "ANS" not in pdf.name: # 정답지 제외
                print(f"파싱 중: {pdf.name}")
                data = parse_question_paper(pdf)
                if data:
                    db.append(data)
    
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"✅ 총 {len(db)}개 시험지 파싱 완료 -> {DB_PATH}")

if __name__ == "__main__":
    build_all()
