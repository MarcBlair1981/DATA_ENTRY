from playwright.sync_api import sync_playwright
import time
import os

def inspect_modal():
    print("Starting Inspector...")
    print("1. I will launch the browser.")
    print("2. Please LOG IN and navigate to the 'Questions' page.")
    print("3. Click 'Create New Question Template' (or open an existing one).")
    print("4. I will wait up to 5 minutes for you to open the modal.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to base
        try:
            print("Navigating to https://backoffice.splash.tech/questions ...")
            page.goto('https://backoffice.splash.tech/questions', timeout=60000)
        except Exception as e:
            print(f"Navigation warning: {e}")

        print("\nWaiting for you to open the modal (I am watching for '.mat-mdc-dialog-container')...")
        try:
            # Wait for the dialog to appear (5 minutes)
            page.wait_for_selector('.mat-mdc-dialog-container', state='visible', timeout=300000)
            print("Modal detected! Waiting 15 seconds for you to get settled...")
            time.sleep(15)
            
            print("Capturing modal HTML...")
            try:
                # Get the modal content specifically using evaluate
                modal_html = page.locator('.mat-mdc-dialog-container').evaluate('node => node.outerHTML')
                
                with open('modal_fragment.html', 'w', encoding='utf-8') as f:
                    f.write(modal_html)
                
                print("SUCCESS! Saved to modal_fragment.html")
            except Exception as e:
                print(f"Error grabbing specific modal HTML: {e}")

            print("Taking full snapshot just in case...")
            try:
                # Dump full page HTML (for context)
                html_content = page.content()
                with open("modal_debug.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                print("Saved modal_debug.html")
            except:
                pass
            
        except Exception as e:
            print(f"Bored of waiting or error: {e}")

        print("Done! Keeping browser open for 60 seconds so you can see...")
        time.sleep(60)
        print("Closing...")
        browser.close()

if __name__ == "__main__":
    inspect_modal()
