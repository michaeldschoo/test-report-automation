import sys
sys.path.append(r'd:\EKCRPA\test-report-automation')

from run_pipeline import parse_pdf
from pathlib import Path

# 정확한 새로 스캔한 PDF 경로
pdf_path = r'J:\My Drive\EKC  OFFICE\STT - NEW\STT2027\TEST\STT27\20261027185708.pdf'
print(f"테스트 시작: {pdf_path}")
try:
    # 텍스트 레이어 있는지 먼저 체크
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    first_text = reader.pages[0].extract_text()
    print(f"텍스트 레이어 글자 수: {len(first_text.strip())}")
    
    result = parse_pdf(pdf_path)
    print(f"학생 이름: {result.get('student_name')}")
    print(f"과목 수: {len(result.get('subjects', []))}")
except Exception as e:
    import traceback
    traceback.print_exc()
