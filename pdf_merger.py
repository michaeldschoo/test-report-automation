import os
from PyPDF2 import PdfWriter, PdfReader

def merge_pdfs(input_files, output_path):
    """
    여러 PDF 파일을 하나로 통합합니다.
    :param input_files: 통합할 PDF 파일 경로 리스트
    :param output_path: 저장될 통합 PDF 파일 경로
    """
    writer = PdfWriter()

    for pdf in input_files:
        if os.path.exists(pdf):
            try:
                reader = PdfReader(pdf)
                for page in reader.pages:
                    writer.add_page(page)
            except Exception as e:
                print(f"Error reading {pdf}: {e}")
        else:
            print(f"File not found: {pdf}")

    with open(output_path, "wb") as output_file:
        writer.write(output_file)
    
    print(f"Merged PDF saved to: {output_path}")

if __name__ == "__main__":
    # 간단한 테스트 코드
    test_files = [] # 여기에 테스트용 파일 경로 추가 가능
    if test_files:
        merge_pdfs(test_files, "merged_test.pdf")
