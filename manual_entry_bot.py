import csv
from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        # Launch browser in visible mode
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to https://backoffice.splash.tech/ ...")
        page.goto("https://backoffice.splash.tech/")

        print("\n" + "="*50)
        print("ACTION REQUIRED: Please log in manually in the browser window.")
        print("When you are effectively logged in and on the correct starting page, return here.")
        input("Press Enter to continue teaching the bot...")
        print("="*50 + "\n")

        print("Logged in confirmed!")
        print("Current Page Title:", page.title())
        print("Current URL:", page.url)

        # 4. Open Translation Modal (Robust Selection)
        print(f"{Fore.CYAN}[INFO]   [Question Mode] Clicking Translate icon...{Style.RESET_ALL}")
        
        # The translate button is likely an icon inside the input field
        # We target the specific input for 'question-text' and finding the icon within it
        try:
            # Primary attempt: data-test attribute which we found in debug
            translate_btn = page.locator('app-input-label[data-test="question-text"] mat-icon[data-test="language-icon"]')
            translate_btn.click()
        except:
            # Fallback: look for any translate icon in the dialog
            print(f"{Fore.YELLOW}[WARNING] Primary translate locator failed, trying fallback...{Style.RESET_ALL}")
            page.locator('mat-icon:has-text("translate")').first.click()
            
        # Wait for translation modal
        page.wait_for_selector('app-translation-dialog', timeout=5000)

        # Basic routine to read the CSV (just to show we can)
        print("\nReading data.csv to prepare for entry...")
        with open('data.csv', mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            print("Columns found:", reader.fieldnames)
            
            # Identify the first row to start teaching
            first_row = next(reader, None)
            if first_row:
                print(f"Ready to process first item: {first_row['Key']}")
            else:
                print("CSV appears empty!")

        # Keep browser open for the 'teaching' phase
        print("\nNow, let's identify the fields.")
        print("Please use the browser's 'Inspect' tool or tell me the field selectors.")
        # In a real collaborative session, we'd input selectors here.
        # For now, we pause so the user can see the state.
        input("Press Enter to close the browser session (or Ctrl+C to stop)...")

        browser.close()

if __name__ == "__main__":
    run()
