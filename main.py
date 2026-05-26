import asyncio
import os
import re
import sys
import zipfile
import shutil
import traceback
from playwright.async_api import async_playwright
from pdf_merger import merge_pdfs, merge_all_in_folder
from dotenv import load_dotenv

load_dotenv()

# 환경 변수 및 설정
LOGIN_URL = "https://edukingdomcollege.com/login/"
USERNAME = "23017-113"
PASSWORD = os.getenv("PASSWORD")

async def run_automation(test_round):
    if not test_round:
        test_round = input("다운로드할 [회차] 정보를 입력하세요 (예: 1): ")
    
    try:
        async with async_playwright() as p:
            # 브라우저 실행
            print("브라우저를 실행합니다...")
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            # 모든 팝업 자동 승인
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

            print(f"[{LOGIN_URL}] 접속 시도 중...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

            # 1. 로그인 프로세스
            print("로그인 단계 진입...")
            try:
                # 아이디 입력창이 나타날 때까지 대기
                print("  > 아이디 입력창 대기 중...")
                user_input = await page.wait_for_selector('input[name="username"]', timeout=15000)
                if user_input:
                    await user_input.fill(USERNAME)
                    print(f"  > 아이디({USERNAME}) 입력 완료.")
                    
                    # 비밀번호 및 로그인 버튼
                    await page.fill('input[type="password"]', PASSWORD)
                    await page.click('button[type="submit"], input[type="submit"], .btn-login')
                    print("  > 로그인 버튼 클릭 완료.")
                    
                    # 로그인 후 대기
                    await page.wait_for_load_state("networkidle")
                    print("  > 로그인 완료 및 페이지 로드됨.")
                else:
                    raise Exception("아이디 입력창을 찾을 수 없습니다.")
            except Exception as login_err:
                print(f"  ! 자동 로그인 실패: {login_err}")
                print("  ! 수동으로 로그인을 완료한 후, 목록 페이지에서 'Resume'을 눌러주세요.")
                await page.pause()

            # 2. 목록 페이지 URL 확인
            print("과목 목록 페이지 확인 중...")
            list_url = None
            try:
                # 메뉴 버튼의 주소 추출
                menu_link = page.get_by_text("Online Selective Test Report", exact=False)
                list_url = await menu_link.first.get_attribute("href")
                if list_url and not list_url.startswith("http"):
                    list_url = f"https://edukingdomcollege.com{list_url}"
                
                print(f"  > 목록 주소 감지: {list_url}")
                await page.goto(list_url, wait_until="networkidle")
            except:
                print("  ! 목록 주소 자동 감지 실패. 수동으로 목록 페이지를 열고 'Resume'을 눌러주세요.")
                await page.pause()
                list_url = page.url

            # 3. 과목 처리 루프
            subjects = ["Reading", "Math", "Thinking Skills", "Writing"]
            base_download_path = f"./downloads/round_{test_round}"
            output_path = f"./output/round_{test_round}"
            os.makedirs(base_download_path, exist_ok=True)
            os.makedirs(output_path, exist_ok=True)

            for subject in subjects:
                print(f"\n" + "="*30)
                print(f"[{subject}] 작업 시작")
                print("="*30)
                
                if page.url != list_url:
                    await page.goto(list_url, wait_until="networkidle")

                try:
                    # 과목 링크 클릭
                    pattern = f"Selective Trial Test Power {subject} Test {test_round}"
                    print(f"  > '{pattern}' 진입 중...")
                    sub_link = page.get_by_text(pattern, exact=False).first
                    await sub_link.wait_for(state="visible", timeout=10000)
                    await sub_link.click()
                    await page.wait_for_load_state("networkidle")

                    # 4. ZIP 다운로드
                    zip_btn = page.get_by_text("Generate All PDFs (ZIP)", exact=False).first
                    await zip_btn.scroll_into_view_if_needed()
                    
                    print("  > ZIP 생성 및 진행 상황 모니터링...")
                    async with page.expect_download(timeout=300000) as download_info:
                        await zip_btn.click(force=True)
                        
                        # Progress 감지 루프
                        last_prog = ""
                        for _ in range(120):
                            try:
                                prog_text = await page.get_by_text("Progress:", exact=False).first.inner_text()
                                if prog_text != last_prog:
                                    print(f"    - {prog_text.strip()}")
                                    last_prog = prog_text
                            except: pass
                            await asyncio.sleep(1)
                            if download_info.is_done(): break

                    download = await download_info.value
                    zip_path = os.path.join(base_download_path, f"{subject}.zip")
                    await download.save_as(zip_path)
                    print(f"  > [성공] {subject}.zip 저장 완료.")

                    # 5. 압축 해제 및 분류
                    zip_temp = os.path.join(base_download_path, f"temp_{subject}")
                    os.makedirs(zip_temp, exist_ok=True)
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        z.extractall(zip_temp)
                    
                    pdf_files = [f for f in os.listdir(zip_temp) if f.endswith(".pdf")]
                    for f in pdf_files:
                        m = re.search(r'(\d{4,})', f)
                        sid = m.group(1) if m else os.path.splitext(f)[0]
                        sdir = os.path.join(base_download_path, sid)
                        os.makedirs(sdir, exist_ok=True)
                        shutil.move(os.path.join(zip_temp, f), os.path.join(sdir, f"{subject}_{test_round}.pdf"))
                    print(f"  > {len(pdf_files)}개 파일 처리 성공.")

                except Exception as e:
                    print(f"  ! [{subject}] 오류: {e}")
                    continue

            # 6. 병합
            print("\n최종 PDF 병합 프로세스 시작...")
            # ... (병합 로직 생략 없이 그대로 유지) ...
            student_dirs = [d for d in os.listdir(base_download_path) if os.path.isdir(os.path.join(base_download_path, d)) and not d.startswith("temp_")]
            merged_count = 0
            for sid in student_dirs:
                folder = os.path.join(base_download_path, sid)
                if any(f.endswith(".pdf") for f in os.listdir(folder)):
                    out_file = os.path.join(output_path, f"Report_{sid}_Round_{test_round}.pdf")
                    merge_all_in_folder(folder, out_file)
                    merged_count += 1
            print(f"\n[최종 완료] 총 {merged_count}명의 리포트 생성.")
            await browser.close()

    except Exception as global_err:
        print("\n" + "!"*50)
        print("치명적 오류 발생 (프로그램 중단):")
        traceback.print_exc()
        print("!"*50)

if __name__ == "__main__":
    round_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_automation(round_arg))
