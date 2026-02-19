
from playwright.sync_api import sync_playwright

TARGET_URL = 'https://backoffice.splash.tech/labels'

def run():
    print("Launching 'HTML Dump Mode'...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL)

        print("\n" + "="*50)
        print("ACTION REQUIRED: Log in & Navigate to the Labels Page.")
        print("Wait until you see the list of labels.")
        input("Press Enter when ready to DUMP HTML...")
        print("="*50 + "\n")

        print("Waiting for ANY table-like element (max 30s)...")
        try:
            # Try waiting for potential table containers
            page.wait_for_selector('mat-row, tr, [role="row"], .ag-row', timeout=30000)
            print("Table elements detected!")
        except:
             print("Timed out waiting for specific table elements.")

        print("Capturing full body HTML...")
        full_html = page.content()
        
        # Save to file
        with open('table_dump.html', 'w', encoding='utf-8') as f:
            f.write(full_html)
            
        print("\nFull HTML saved to 'table_dump.html'.")
        print("Closing browser...")
        browser.close()

if __name__ == "__main__":
    run()
