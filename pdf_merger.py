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

    # 결과 폴더가 없으면 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "wb") as output_file:
        writer.write(output_file)
    
    print(f"Merged PDF saved to: {output_path}")

def merge_all_in_folder(folder_path, output_filename):
    """
    특정 폴더 내의 모든 PDF 파일을 이름 순으로 정렬하여 통합합니다.
    """
    pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(".pdf")]
    pdf_files.sort() # 파일명 순으로 정렬 (회차별 정렬 등에 유리)
    
    if not pdf_files:
        print(f"No PDF files found in {folder_path}")
        return

    merge_pdfs(pdf_files, output_filename)

if __name__ == "__main__":
    # 테스트 예시
    # merge_all_in_folder("./downloads/student_name", "./output/student_name_total.pdf")
    pass
