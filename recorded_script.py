import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://edukingdomcollege.com/login/")
    page.get_by_role("textbox", name="Username or Email").click()
    page.get_by_role("textbox", name="Username or Email").fill("23017-113")
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill("!Grace0608!")
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
