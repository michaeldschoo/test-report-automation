from pdf2image import convert_from_path
import pytesseract

POPPLER_PATH = r'F:\poppler-26.09.0\Library\bin' 

def ocr_pdf_to_text(pdf_path):
    """PDF를 이미지로 변환 후 OCR 수행하여 텍스트 반환"""
    print(f"  [OCR] 텍스트 레이어 없음 - OCR 실행 중: {pdf_path}")
    pages = convert_from_path(pdf_path, 300, poppler_path=POPPLER_PATH)
    full_text = ""
    for i, page in enumerate(pages):
        text = pytesseract.image_to_string(page, lang='eng')
        full_text += f"\n=== Page {i+1} ===\n{text}"
    return full_text
