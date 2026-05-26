import asyncio
import os
from playwright.async_api import async_playwright
from pdf_merger import merge_pdfs
from dotenv import load_dotenv

load_dotenv()

# 환경 변수 설정 (실제 값은 .env 파일에 저장)
LOGIN_URL = os.getenv("LOGIN_URL", "https://example.com/login")
USERNAME = os.getenv("BRANCH_USERNAME")
PASSWORD = os.getenv("BRANCH_PASSWORD")

async def run_automation():
    async with async_playwright() as p:
        # 브라우저 실행 (headless=False로 설정하여 동작 확인 가능)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Connecting to {LOGIN_URL}...")
        await page.goto(LOGIN_URL)

        # 1. 로그인 프로세스 (실제 사이트의 선택자에 맞게 수정 필요)
        try:
            await page.fill('input[name="username"]', USERNAME)
            await page.fill('input[name="password"]', PASSWORD)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            print("Login successful.")
        except Exception as e:
            print(f"Login failed: {e}")
            await browser.close()
            return

        # 2. 메뉴 이동 및 학생 리포트 페이지 탐색
        # 예시: await page.click('text="Test Reports"')
        
        # 3. 학생별 리포트 다운로드 로직
        # 리스트를 돌면서 각 PDF를 다운로드 폴더에 저장
        download_path = "./downloads"
        os.makedirs(download_path, exist_ok=True)
        
        # 다운로드 예시 (실제 구현 시 학생별 루프 필요)
        # async with page.expect_download() as download_info:
        #     await page.click('.download-btn')
        # download = await download_info.value
        # await download.save_as(os.path.join(download_path, "report1.pdf"))

        # 4. PDF 통합 (학생별로 수집된 파일들을 통합)
        # output_path = "./output"
        # os.makedirs(output_path, exist_ok=True)
        # merge_pdfs(["./downloads/report1.pdf", "./downloads/report2.pdf"], "./output/student_A_integrated.pdf")

        print("Automation task completed.")
        await browser.close()

if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("Please set BRANCH_USERNAME and BRANCH_PASSWORD in .env file.")
    else:
        asyncio.run(run_automation())
