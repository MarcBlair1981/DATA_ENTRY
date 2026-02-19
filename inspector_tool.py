
from playwright.sync_api import sync_playwright

TARGET_URL = 'https://backoffice.splash.tech/labels'

def run():
    print("Launching 'Inspector Mode'...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL)

        print("\n" + "="*50)
        print("ACTION REQUIRED: Log in & Navigate to the Labels Page.")
        print("Wait until you see the list of labels.")
        input("Press Enter when ready to INSPECT...")
        print("="*50 + "\n")

        print("INSTRUCTION: switch to the browser window NOW.")
        print("Hover your mouse over the English text of the first row.")
        print("I will capture the element in 5 seconds...")
        
        import time
        for i in range(5, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        
        print("CAPTURING NOW!")

        # Evaluate JS to get the element under the mouse
        # This is a powerful trick to "see what the user sees"
        element_info = page.evaluate("""() => {
            const el = document.querySelector(':hover');
            if (!el) return "No element found under mouse.";
            
            // Traverse up to find the row container (tr or mat-row)
            let row = el.closest('tr') || el.closest('mat-row') || el.closest('.row');
            
            return {
                tagName: el.tagName,
                className: el.className,
                innerText: el.innerText,
                outerHTML: el.outerHTML,
                rowHTML: row ? row.outerHTML.substring(0, 300) + "..." : "No row container found"
            };
        }""")

        print("\n" + "-"*20 + " CAPTURED ELEMENT " + "-"*20)
        print(f"Tag: {element_info.get('tagName')}")
        print(f"Class: {element_info.get('className')}")
        print(f"Text: {element_info.get('innerText')}")
        print(f"HTML: {element_info.get('outerHTML')}")
        print("\n" + "-"*20 + " ROW CONTAINER " + "-"*20)
        print(f"Row HTML Start: {element_info.get('rowHTML')}")
        print("-" * 60)
        
        print("\nPlease COPY the output above and paste it to the chat.")
        input("Press Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    run()
