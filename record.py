import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://backoffice.splash.tech/login")
    page.get_by_role("textbox", name="E-Mail").click()
    page.get_by_role("textbox", name="E-Mail").fill("marc@splash.tech")
    page.get_by_role("textbox", name="E-Mail").press("Tab")
    page.get_by_role("textbox", name="Password").fill("Arsenal1")
    page.get_by_role("button", name="Login").click()
    page.get_by_role("button", name="Open or close menu").click()
    page.get_by_role("link", name="Language Labels").click()
    page.get_by_role("button", name="Client Logo 10 Bet ZA Arrow").click()
    page.get_by_role("menuitem", name="Client logo SilverSpin").click()
    page.get_by_role("gridcell", name="Bet could not be created.").click()
    page.locator("[data-test=\"add-value\"]").click()
    page.locator(".mat-mdc-select-placeholder").click()
    page.locator("[data-test=\"language-search\"]").click()
    page.locator("[data-test=\"language-search\"]").fill("thai")
    page.locator("[data-test=\"language-option\"]").click()
    page.locator("#mat-input-16").click()
    page.locator("#mat-input-16").fill("ไม่สามารถสร้างการเดิมพันได้")
    page.locator("[data-test=\"add-value\"]").click()
    page.locator("#mat-mdc-form-field-label-50").get_by_text("Language").click()
    page.locator("[data-test=\"language-search\"]").click()
    page.locator("[data-test=\"language-search\"]").fill("viet")
    page.locator("[data-test=\"language-option\"]").click()
    page.locator("div").filter(has_text=re.compile(r"^Value$")).nth(4).click()
    page.locator("#mat-input-18").click()
    page.locator("#mat-input-18").fill("Không thể tạo cược.")
    page.locator("[data-test=\"create-label-save\"]").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
