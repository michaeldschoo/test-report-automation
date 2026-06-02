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

# Environment variables and settings
LOGIN_URL = "https://edukingdomcollege.com/login/"
DEFAULT_USERNAME = "23017-113"
USERNAME = os.getenv("BRANCH_USERNAME") or DEFAULT_USERNAME
PASSWORD = os.getenv("BRANCH_PASSWORD") or os.getenv("PASSWORD")

def print_log(msg):
    print(f"\n{msg}", flush=True)

async def login(page):
    """Common login process function"""
    print_log(f"[LOGIN] ID: {USERNAME}")
    if not PASSWORD:
        print_log("  ! Error: PASSWORD not found.")
        return False

    try:
        await page.goto(LOGIN_URL, wait_until="load", timeout=90000)
        await page.get_by_role("textbox", name="Username or Email").fill(USERNAME)
        await page.get_by_role("textbox", name="Password").fill(PASSWORD)
        await page.get_by_role("button", name="Log In").click()
        
        try:
            await page.wait_for_function("() => !window.location.href.includes('/login/')", timeout=30000)
            await page.wait_for_load_state("load", timeout=30000)
        except: pass
            
        if "login" in page.url.lower():
            print_log("  ! Login failed: Still on login page.")
            return False

        print_log(f"  > Login successful. (URL: {page.url})")
        return True
    except Exception as e:
        print_log(f"  ! Login Error: {e}")
        return False

async def download_and_extract(page, link, base_download_path, subject, val):
    """Downloads ZIP, extracts PDFs, and organizes by student name"""
    try:
        await link.scroll_into_view_if_needed()
        print(f"    - [{subject}] Opening details...", flush=True)
        await link.click()
        await page.wait_for_load_state("load", timeout=60000)
        await asyncio.sleep(5) 
        
        zip_btn = page.locator("button, a, input").filter(has_text=re.compile("Generate All PDFs|ZIP|Download All", re.I)).first
        if await zip_btn.count() == 0:
            print_log(f"      ! Error: ZIP button not found on {page.url}")
            await page.screenshot(path=f"error_{subject}.png")
            return False

        print(f"    - [{subject}] Downloading ZIP...", flush=True)
        async with page.expect_download(timeout=600000) as download_info:
            await zip_btn.click()
            last_p = ""
            while not download_info.is_done():
                try:
                    p_text = await page.get_by_text("Progress:", exact=False).first.inner_text(timeout=500)
                    if p_text != last_p:
                        print(f"      > {p_text.strip()}", flush=True)
                        last_p = p_text
                except: pass
                await asyncio.sleep(1)

        download = await download_info.value
        zip_path = os.path.join(base_download_path, f"{subject}.zip")
        await download.save_as(zip_path)

        zip_temp = os.path.join(base_download_path, f"temp_{subject}")
        if os.path.exists(zip_temp): shutil.rmtree(zip_temp)
        os.makedirs(zip_temp, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(zip_temp)

        pdf_files = [f for f in os.listdir(zip_temp) if f.endswith(".pdf")]
        for f in pdf_files:
            s_name = f
            for sep in ["_Year", "_Selective", "_Trial", "_Report", "_Term", "_Student", f"_{val}", ".pdf"]:
                if sep in s_name: s_name = s_name.split(sep)[0]
            s_name = s_name.strip().replace(" ", "-")
            s_dir = os.path.join(base_download_path, s_name)
            os.makedirs(s_dir, exist_ok=True)
            dest = os.path.join(s_dir, f"{subject}.pdf")
            if os.path.exists(dest): os.remove(dest)
            shutil.move(os.path.join(zip_temp, f), dest)
        
        os.remove(zip_path)
        shutil.rmtree(zip_temp)
        print(f"    - [{subject}] Completed.", flush=True)
        return True
    except Exception as e:
        print_log(f"    ! Error in [{subject}]: {e}")
        return False

def is_on_page(current, target):
    return current.split('?')[0].rstrip('/') == target.rstrip('/')

async def process_selective_test(page, test_round):
    list_url = "https://edukingdomcollege.com/online-selective-test-report-list/"
    base_path = f"./downloads/Selective_R{test_round}"
    output_path = f"./output/Selective_R{test_round}"
    os.makedirs(base_path, exist_ok=True)

    print_log(f"[STEP] Navigating to Selective list...")
    await page.goto(list_url, wait_until="load")
    
    # Wait for Table content
    print_log("  > Waiting for data to load (8s)...")
    await asyncio.sleep(8)
    
    # SCAN PAGE CONTENT (For Debugging)
    print_log("--- PAGE CONTENT SCAN ---")
    all_text = await page.evaluate("() => document.body.innerText")
    lines = [l.strip() for l in all_text.split('\n') if l.strip()]
    for i, line in enumerate(lines[:20]):
        print(f"  [{i}] {line[:100]}", flush=True)
    print_log("--------------------------")

    # Find ANY row that contains the round number '57'
    # Try multiple ways to locate
    rows = page.locator("tr").filter(has_text=str(test_round))
    count = await rows.count()
    print_log(f"  > Found {count} rows containing '{test_round}'")

    if count == 0:
        print_log("  ! No exact row match. Trying global search for links...")
        # Fallback: search for any link that contains 'test-report' and the round number in its text
        links = page.locator("a").filter(has_text=str(test_round))
        link_count = await links.count()
        print_log(f"  > Found {link_count} potential links matching '{test_round}'")
        
        if link_count > 0:
            for i in range(link_count):
                link = links.nth(i)
                text = await link.inner_text()
                subj = "Reading" if "Reading" in text else "Math" if "Math" in text else f"Subject_{i}"
                await download_and_extract(page, link, base_path, subj, test_round)
        return

    for i in range(count):
        if not is_on_page(page.url, list_url):
            await page.goto(list_url, wait_until="load")
            await asyncio.sleep(3)
            
        row = rows.nth(i)
        text = await row.inner_text()
        print_log(f"  > Processing {i+1}/{count}: {text.strip()[:60]}...")
        
        subj = "Other"
        if any(k in text.lower() for k in ["reading", "power", "english"]): subj = "Reading"
        elif any(k in text.lower() for k in ["math", "reasoning"]): subj = "Math"
        elif any(k in text.lower() for k in ["ts", "thinking"]): subj = "Thinking-Skills"
        elif any(k in text.lower() for k in ["writing", "wrt"]): subj = "Writing"
        
        link = row.locator("a").filter(has_text=re.compile("Report|View|Click|Download", re.I)).first
        if not await link.is_visible(): link = row.locator("a").first
        
        if await link.is_visible():
            await download_and_extract(page, link, base_path, subj, test_round)

    print_log(f"[FINISH] Merging results...")
    merge_all_students(base_path, output_path, f"R{test_round}")

async def process_term_test(page, term_num):
    list_url = "https://edukingdomcollege.com/offline-test-report-list/"
    years = [f"Year {i}" for i in range(1, 7)]
    
    for yr in years:
        print_log(f"{yr} - Term {term_num} Discovery")
        if not is_on_page(page.url, list_url): await page.goto(list_url, wait_until="load")
        await asyncio.sleep(4)

        matching_rows = page.locator("tr").filter(has_text=yr).filter(has_text=str(term_num))
        count = await matching_rows.count()
        print_log(f"  > Found {count} rows for {yr}")

        if count == 0:
            continue

        yr_path = os.path.join("./downloads", f"TermTest_T{term_num}", yr.replace(' ', ''))
        yr_out = os.path.join("./output", f"TermTest_T{term_num}", yr.replace(' ', ''))
        os.makedirs(yr_path, exist_ok=True)

        for i in range(count):
            if not is_on_page(page.url, list_url): await page.goto(list_url, wait_until="load")
            row = matching_rows.nth(i)
            try:
                text = await row.inner_text(timeout=5000)
                subj = "Other"
                if any(k in text.lower() for k in ["reading", "power", "english"]): subj = "English"
                elif any(k in text.lower() for k in ["math", "reasoning", "mathematics"]): subj = "Math"
                elif any(k in text.lower() for k in ["ga", "general", "thinking"]): subj = "Thinking"
                elif any(k in text.lower() for k in ["writing", "wrt"]): subj = "Writing"
                
                link = row.locator("a").filter(has_text=re.compile("Report|View|Click|Download", re.I)).first
                if await link.is_visible():
                    await download_and_extract(page, link, yr_path, subj, term_num)
            except: continue

        merge_all_students(yr_path, yr_out, f"T{term_num}")

def merge_all_students(base_path, output_path, suffix):
    if not os.path.exists(base_path): return
    os.makedirs(output_path, exist_ok=True)
    dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and not d.startswith("temp_")]
    for sid in dirs:
        folder = os.path.join(base_path, sid)
        if any(f.endswith(".pdf") for f in os.listdir(folder)):
            out = os.path.join(output_path, f"Total_Report_{sid}_{suffix}.pdf")
            try: merge_all_in_folder(folder, out)
            except: pass

async def main():
    while True:
        await asyncio.sleep(0.5)
        print_log("="*50 + "\n   EduKingdom Automation v2.2 - Main Menu\n" + "="*50)
        print_log(" 1. Online Selective Test Report\n 2. Term Test Report (Year 1-6)\n 3. Exit")
        choice = input("\nSelect Option: ").strip()
        
        if choice == '3': break
        if choice not in ['1', '2']: continue

        val = input(f"Enter {'Round' if choice=='1' else 'Term'} Number: ").strip()
        if not val: continue
        mode = "selective" if choice == '1' else "term"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            page.on("dialog", lambda d: asyncio.create_task(d.accept()))

            try:
                if await login(page):
                    if mode == "selective": await process_selective_test(page, val)
                    else: await process_term_test(page, val)
                    print_log(f"[DONE] {mode.capitalize()} Test {val} completed.")
                else: print_log("[STOP] Login failed.")
            except Exception as e:
                print_log(f"[ERROR] {e}")
                traceback.print_exc()

            print_log("Process complete. Press Enter to return to menu...")
            await asyncio.get_event_loop().run_in_executor(None, input, "")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
