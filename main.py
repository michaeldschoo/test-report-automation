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
            # Use regex to split student name from the file name more accurately
            # It splits at the first occurrence of common keywords or the specific round/term number
            patterns = ["_Year", "_Selective", "_Trial", "_Report", "_Term", "_Student", rf"_{val}\b", r"\.pdf"]
            combined_pattern = "|".join(patterns)
            split_match = re.search(combined_pattern, s_name)
            if split_match:
                s_name = s_name[:split_match.start()]
            
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
    
    # Clean start: remove existing downloads for this round to avoid mixing old/new files
    if os.path.exists(base_path):
        print_log(f"  > Cleaning existing download folder: {base_path}")
        shutil.rmtree(base_path)
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
    # Use regex for exact round number match to avoid matching 15, 25, 35 when searching for 5
    rows = page.locator("tr").filter(has_text=re.compile(rf"\b{test_round}\b"))
    count = await rows.count()
    print_log(f"  > Found {count} rows containing '{test_round}'")

    if count == 0:
        print_log("  ! No exact row match. Trying global search for links...")
        # Fallback: search for any link that contains 'test-report' and the round number in its text
        links = page.locator("a").filter(has_text=re.compile(rf"\b{test_round}\b"))
        link_count = await links.count()
        print_log(f"  > Found {link_count} potential links matching '{test_round}'")
        
        if link_count > 0:
            for i in range(link_count):
                link = links.nth(i)
                text = await link.inner_text()
                subj = "Reading" if "Reading" in text else "Math" if "Math" in text else f"Subject_{i}"
                await download_and_extract(page, link, base_path, subj, test_round)
        return

    processed_subjects = {}

    for i in range(count):
        if not is_on_page(page.url, list_url):
            await page.goto(list_url, wait_until="load")
            await asyncio.sleep(5) # Increased wait to ensure list is stable
            # Re-locate rows after navigation to avoid stale element reference
            rows = page.locator("tr").filter(has_text=re.compile(rf"\b{test_round}\b"))
            
        row = rows.nth(i)
        
        # Extract Subject from 'Test Subject' column (direct reference)
        tds = row.locator("td")
        td_count = await tds.count()
        subj_base = "Other"
        
        # Scan all columns to find the one that looks like a subject name
        # We ignore buttons (View, Report) and generic numbers
        for j in range(td_count):
            cell_text = (await tds.nth(j).inner_text()).strip()
            if not cell_text: continue
            if any(btn in cell_text for btn in ["View", "Report", "Click", "Download"]): continue
            if cell_text.isdigit(): continue
            # If it contains subject keywords, this is likely our subject column
            if any(k in cell_text.lower() for k in ["math", "reasoning", "reading", "thinking", "skills", "writing", "general", "ability"]):
                subj_base = cell_text
                break
        
        # Fallback if no keywords matched
        if subj_base == "Other" and td_count >= 2:
            subj_base = (await tds.nth(1).inner_text()).strip() or "Other"
        
        # Clean up the subject name for filename safety
        subj_base = subj_base.replace(" ", "-").replace("/", "-")
        
        text = await row.inner_text()
        print_log(f"  > Processing {i+1}/{count}: {subj_base} ({text.strip()[:40]}...)")
        
        # Tracking subjects to handle duplicates correctly
        processed_subjects[subj_base] = processed_subjects.get(subj_base, 0) + 1
        subj = subj_base if processed_subjects[subj_base] == 1 else f"{subj_base}_{processed_subjects[subj_base]}"
        
        link = row.locator("a").filter(has_text=re.compile("Report|View|Click|Download", re.I)).first
        if not await link.is_visible(): link = row.locator("a").first
        
        if await link.is_visible():
            success = await download_and_extract(page, link, base_path, subj, test_round)
            if not success:
                print_log(f"      ! Failed to download {subj}")

    print_log(f"[FINISH] Merging results...")
    merge_all_students(base_path, output_path, f"R{test_round}", is_selective=True)

async def process_term_test(page, term_num):
    list_url = "https://edukingdomcollege.com/offline-test-report-list/"
    years = [f"Year {i}" for i in range(1, 7)]
    
    base_path = f"./downloads/TermTest_T{term_num}"
    if os.path.exists(base_path):
        print_log(f"  > Cleaning existing download folder: {base_path}")
        shutil.rmtree(base_path)
    
    for yr in years:
        print_log(f"{yr} - Term {term_num} Discovery")
        if not is_on_page(page.url, list_url): await page.goto(list_url, wait_until="load")
        await asyncio.sleep(4)

        # Use regex for exact term match to avoid matching 'Year 5' when term_num is 5
        matching_rows = page.locator("tr").filter(has_text=yr).filter(has_text=re.compile(rf"Term\s*{term_num}\b", re.I))
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

        merge_all_students(yr_path, yr_out, f"T{term_num}", is_selective=False, year_str=yr, term_num=term_num)

def merge_all_students(base_path, output_path, suffix, is_selective=False, year_str="", term_num=""):
    if not os.path.exists(base_path): return
    os.makedirs(output_path, exist_ok=True)
    dirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d)) and not d.startswith("temp_")]
    for sid in dirs:
        folder = os.path.join(base_path, sid)
        if any(f.endswith(".pdf") for f in os.listdir(folder)):
            if is_selective:
                round_num = suffix[1:] if suffix.startswith("R") else suffix
                # 성을 제외하고 이름만 추출 (예: 'Adrio-Maheswaran' -> 'Adrio')
                first_name = sid.split('-')[0]
                out = os.path.join(output_path, f"STT{round_num} {first_name}.pdf")
                
                # 동명이인이 있을 경우 파일 덮어쓰기 방지
                counter = 1
                while os.path.exists(out):
                    out = os.path.join(output_path, f"STT{round_num} {first_name}_{counter}.pdf")
                    counter += 1
                # Reading Skills -> 1, Mathematical Reasoning -> 2, Thinking Skills -> 3, others -> 4
                def sort_by_subject(file_path):
                    filename = os.path.basename(file_path).lower()
                    if "reading" in filename:
                        return (1, filename)
                    elif "math" in filename or "reasoning" in filename:
                        return (2, filename)
                    elif "thinking" in filename or "general" in filename or "ability" in filename:
                        return (3, filename)
                    return (4, filename)
                
                try: merge_all_in_folder(folder, out, sort_key=sort_by_subject)
                except Exception as e:
                    print(f"Error merging selective for {sid}: {e}")
            else:
                first_name = sid.split('-')[0]
                y_num = year_str.replace("Year ", "") if year_str.startswith("Year ") else year_str
                year_format = f"Y{y_num}" if y_num else ""
                term_format = f"T{term_num}" if term_num else ""
                
                out_filename = f"{first_name} {year_format} {term_format}".strip() + ".pdf"
                out = os.path.join(output_path, out_filename)
                
                counter = 1
                while os.path.exists(out):
                    out_filename = f"{first_name}_{counter} {year_format} {term_format}".strip() + ".pdf"
                    out = os.path.join(output_path, out_filename)
                    counter += 1

                try: merge_all_in_folder(folder, out)
                except Exception as e:
                    print(f"Error merging term for {sid}: {e}")

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
