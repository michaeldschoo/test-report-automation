from pdf2image import convert_from_path
import pytesseract

# 설치하신 poppler의 bin 경로
POPPLER_PATH = r'F:\poppler-26.09.0\Library\bin' 

def extract_text_from_pdf_ocr(pdf_path):
    print(f"이미지 변환 중: {pdf_path}")
    # poppler_path 인자 추가
    pages = convert_from_path(pdf_path, 300, poppler_path=POPPLER_PATH)
    full_text = ""
    for i, page in enumerate(pages):
        print(f"OCR 처리 중: {i+1} 페이지")
        text = pytesseract.image_to_string(page, lang='eng')
        full_text += f"\n=== Page {i+1} ===\n{text}"
    return full_text

pdf_file = r'J:\My Drive\EKC  OFFICE\STT - NEW\STT2027\TEST\STT26\STT26 ENG.pdf'
try:
    text = extract_text_from_pdf_ocr(pdf_file)
    with open("stt26_eng_ocr.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("OCR 완료: stt26_eng_ocr.txt")
except Exception as e:
    print(f"Error: {e}")
