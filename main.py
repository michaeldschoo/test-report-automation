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
        test_round = input("다운로드할 [회차] 정보를 입력하세요 (예: 57): ")
    
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
                # recorded_script 기반 role/name 사용
                print("  > 로그인 필드 대기 중...")
                await page.get_by_role("textbox", name="Username or Email").wait_for(state="visible", timeout=20000)
                await page.get_by_role("textbox", name="Username or Email").fill(USERNAME)
                await page.get_by_role("textbox", name="Password").fill(PASSWORD)
                await page.get_by_role("button", name="Log In").click()
                print("  > 로그인 버튼 클릭 완료.")
                
                # 로그인 후 대기
                await page.wait_for_load_state("networkidle", timeout=30000)
                print("  > 로그인 프로세스 완료.")
            except Exception as login_err:
                print(f"  ! 자동 로그인 실패: {login_err}")
                await page.screenshot(path="debug_error.png")
                print("  ! 오류 화면을 'debug_error.png'로 저장했습니다. 수동으로 로그인을 진행해주세요.")
                await page.pause()

            # 2. 목록 페이지 URL 확인
            print("과목 목록 페이지 확인 중...")
            list_url = "https://edukingdomcollege.com/online-selective-test-report-list/"
            try:
                await page.get_by_role("link", name="Online Selective Test Report").click()
                await page.wait_for_load_state("networkidle")
                list_url = page.url
                print(f"  > 목록 페이지 진입 성공: {list_url}")
            except:
                print(f"  ! 메뉴 클릭 실패, 직접 이동 시도: {list_url}")
                await page.goto(list_url, wait_until="networkidle")

            # 3. 과목 처리 루프
            subject_search_map = {
                "Reading": ["Reading", "Power Reading"],
                "Math": ["Mathematical Reasoning", "Math"],
                "Thinking Skills": ["Thinking Skills", "TS"],
                "Writing": ["Writing", "Wrt"]
            }
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
                    terms = subject_search_map.get(subject, [subject])
                    if isinstance(terms, str): terms = [terms]
                    
                    sub_link = None
                    for term in terms:
                        print(f"  > '{subject}'(검색어: {term}) 링크 찾는 중 (회차: {test_round})...")
                        target_row = page.locator("tr").filter(has_text=str(test_round)).filter(has_text=term).first
                        
                        if await target_row.is_visible(timeout=3000):
                            sub_link = target_row.locator("a").filter(has_text=term).first
                            if not await sub_link.is_visible():
                                sub_link = target_row.locator("a").first
                            break
                    
                    if not sub_link or not await sub_link.is_visible():
                        print(f"    - 1단계 실패, 정규식 기반 검색 시도...")
                        for term in terms:
                            sub_link = page.get_by_role("link", name=re.compile(f"{term}.*{test_round}|{test_round}.*{term}", re.I)).first
                            if await sub_link.is_visible(): break

                    if not sub_link or not await sub_link.is_visible():
                        print(f"  ! '{subject}' 링크를 최종적으로 찾을 수 없습니다. (넘어갑니다)")
                        continue

                    await sub_link.scroll_into_view_if_needed()
                    link_text = (await sub_link.inner_text()).strip()
                    print(f"    - 클릭 시도: '{link_text}'")
                    
                    await sub_link.click()
                    await page.wait_for_load_state("networkidle")

                    # [검증] 실제 해당 과목 페이지에 진입했는지 확인
                    page_content = await page.content()
                    verified = False
                    for term in terms:
                        if term.lower() in page_content.lower():
                            verified = True
                            break
                    
                    if not verified:
                        print(f"  ! [경고] 진입한 페이지에서 '{subject}' 키워드를 찾을 수 없습니다.")
                        header = await page.locator("h1, h2").first.inner_text()
                        print(f"    - 현재 페이지 헤더: {header.strip()}")
                        if "Math" in header and subject != "Math":
                            raise Exception(f"잘못된 페이지(Math)에 진입함. ({subject} 작업을 건너뜁니다)")

                    # 4. ZIP 다운로드
                    print("  > ZIP 다운로드 버튼 대기 중...")
                    zip_btn = page.get_by_role("button", name="Generate All PDFs (ZIP)")
                    await zip_btn.wait_for(state="visible", timeout=20000)
                    
                    print("  > ZIP 생성 시작...")
                    async with page.expect_download(timeout=300000) as download_info:
                        await zip_btn.click()
                        
                        last_prog = ""
                        for _ in range(150):
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
                    if os.path.exists(zip_temp): shutil.rmtree(zip_temp)
                    os.makedirs(zip_temp, exist_ok=True)
                    
                    with zipfile.ZipFile(zip_path, 'r') as z:
                        z.extractall(zip_temp)
                    
                    pdf_files = [f for f in os.listdir(zip_temp) if f.endswith(".pdf")]
                    print(f"    - {subject} 압축 해제됨 ({len(pdf_files)}개 파일)")
                    
                    for f in pdf_files:
                        # [개선] 학생 이름 추출 로직 강화
                        # 예: "Aarav-Nair_Selective-Trial-Test...Reading_57.pdf"
                        student_name = f
                        for sep in ["_Selective", "_Trial", "_Report", f"_{test_round}"]:
                            if sep in student_name:
                                student_name = student_name.split(sep)[0]
                                break
                        
                        student_name = student_name.strip().replace(" ", "-")
                        sdir = os.path.join(base_download_path, student_name)
                        os.makedirs(sdir, exist_ok=True)
                        
                        # [핵심] 파일명을 과목명으로 고정하여 중복 방지 (Reading.pdf 등)
                        dest_name = f"{subject}.pdf"
                        dest_path = os.path.join(sdir, dest_name)
                        
                        # 이미 같은 이름의 파일이 있다면 삭제 후 이동 (확실한 교체)
                        if os.path.exists(dest_path): os.remove(dest_path)
                        shutil.move(os.path.join(zip_temp, f), dest_path)
                    
                    print(f"  > {subject} 과목 분류 완료.")

                except Exception as e:
                    print(f"  ! [{subject}] 오류: {e}")
                    continue

            # 6. 병합
            print("\n최종 PDF 병합 프로세스 시작...")
            student_dirs = [d for d in os.listdir(base_download_path) if os.path.isdir(os.path.join(base_download_path, d)) and not d.startswith("temp_")]
            merged_count = 0
            for sid in student_dirs:
                folder = os.path.join(base_download_path, sid)
                if any(f.endswith(".pdf") for f in os.listdir(folder)):
                    # 파일명 간소화 (PermissionError 및 긴 경로 방지)
                    simple_name = sid.split("_")[0]
                    out_file = os.path.join(output_path, f"Report_{simple_name}_R{test_round}.pdf")
                    
                    try:
                        merge_all_in_folder(folder, out_file)
                        merged_count += 1
                        print(f"  > [성공] 병합 완료: {out_file}")
                    except PermissionError:
                        print(f"  ! [오류] {out_file} 파일이 열려 있습니다. 파일을 닫고 다시 실행하세요.")
                    except Exception as e:
                        print(f"  ! [병합 오류] {sid}: {e}")

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
