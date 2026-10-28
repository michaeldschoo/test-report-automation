from run_pipeline import parse_pdf
from pathlib import Path

pdf_path = r'J:\My Drive\EKC  OFFICE\STT - NEW\STT2027\TEST\STT26\STT26 ENG.pdf'
print(f"테스트 시작: {pdf_path}")
try:
    result = parse_pdf(pdf_path)
    print(f"학생 이름: {result.get('student_name')}")
    print(f"과목 수: {len(result.get('subjects', []))}")
except Exception as e:
    print(f"테스트 실패: {e}")
