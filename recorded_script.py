import os
from dotenv import load_dotenv
from playwright.sync_api import Playwright, sync_playwright

load_dotenv()
USERNAME = os.getenv("BRANCH_USERNAME")
PASSWORD = os.getenv("BRANCH_PASSWORD") or os.getenv("PASSWORD")


def run(playwright: Playwright) -> None:
    if not USERNAME or not PASSWORD:
        raise RuntimeError("BRANCH_USERNAME and BRANCH_PASSWORD must be set in .env")

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://edukingdomcollege.com/login/")
    page.get_by_role("textbox", name="Username or Email").click()
    page.get_by_role("textbox", name="Username or Email").fill(USERNAME)
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill(PASSWORD)
    page.get_by_role("button", name="Log In").click()
    page.get_by_role("link", name="Online Selective Test Report").click()
    page.locator("tr:nth-child(50) > td:nth-child(2) > a").click()
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button", name="Generate All PDFs (ZIP)").click()
    page.goto("https://edukingdomcollege.com/online-selective-test-report-list/")
    page.locator("tr:nth-child(102) > td:nth-child(2) > a").click()
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button", name="Generate All PDFs (ZIP)").click()
    page.goto("https://edukingdomcollege.com/online-selective-test-report-list/")
    page.locator("tr:nth-child(155) > td:nth-child(2) > a").click()
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button", name="Generate All PDFs (ZIP)").click()
    page.goto("https://edukingdomcollege.com/branches-2/")

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
