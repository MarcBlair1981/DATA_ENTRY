
import csv
import time
from playwright.sync_api import sync_playwright

CSV_FILE = 'data.csv'
TARGET_URL = 'https://backoffice.splash.tech/labels'

# Mapping CSV columns to language search terms for the dropdown
LANG_MAP = {
    'Thai': 'thai',
    'Vietnamese': 'viet'
}

def run():
    with sync_playwright() as p:
        # slow_mo=1000 means 1 second pause between actions
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        context = browser.new_context()
        page = context.new_page()

        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, timeout=60000)

        print("\n" + "="*50)
        print("ACTION REQUIRED: Please log in manually.")
        print("1. Log in.")
        print("2. Switch to 'Silverspin' client.")
        print("3. Navigate to 'Labels'.")
        print("3. Navigate to 'Labels'.")
        print("Script will start automatically in 40 seconds...")
        page.wait_for_timeout(40000)

        print("="*50 + "\n")

        # Read CSV with robust encoding handling
        rows = []
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        for enc in encodings:
            try:
                with open(CSV_FILE, mode='r', encoding=enc) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                print(f"Successfully loaded {len(rows)} rows with encoding: {enc}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error reading file with {enc}: {e}")
        
        if not rows:
            print("CRITICAL ERROR: Could not read CSV. aborting.")
            browser.close()
            return

        # Process from Top-Down (Standard)
        print("Processing rows in Standard order (Top-Down)...")
        # rows.reverse() # Removed per user request

        for row in rows:
            english_text = row.get('English', '').strip()
            if not english_text:
                continue

            print(f"\nProcessing: '{english_text}'")
            
            # --- STEP 1: SEARCH ---
            try:
                # Find search box
                search_box = page.locator("input[placeholder='Search']").first
                search_box.click()
                search_box.fill("") # Clear
                # Type slowly to trigger AG Grid QuickFilter
                search_box.press_sequentially(english_text, delay=100)
                page.wait_for_timeout(2000) # Wait for grid filter to apply
                
                # --- AG GRID INTERACTION LOGIC ---
                
                # Verify filtering worked: Check if we can find the text in the visible grid
                # logic: The first row's 'en' cell should now contain our text (or there are 0 rows)
                
                rows = page.locator('.ag-row')
                if rows.count() == 0:
                     print(f"  [SKIP] No rows found after search for: {english_text}")
                     continue

                # Find the specific row (double check)
                target_en_cell = page.locator('.ag-cell[col-id="en"]').filter(has_text=english_text).first
                
                if not target_en_cell.is_visible():
                     # Fallback: maybe it's exact match?
                     target_en_cell = page.locator('.ag-cell[col-id="en"]').get_by_text(english_text, exact=True).first

                if not target_en_cell.is_visible():
                     print(f"  [SKIP] Text '{english_text}' not found in visible rows after search.")
                     continue

                # Get the parent row
                target_row = page.locator('.ag-row').filter(has=target_en_cell).first
                print("  Row found. Clicking to open drawer...")
                
                # Click the row (or the cell) to open the side drawer/modal
                # We click the 'key' cell or just the row to be safe
                target_row.click()
                page.wait_for_timeout(1000) # Wait for drawer to animate open

                # 2. Iterate through languages
                valid_langs = ['Thai', 'Vietnamese']
                # Mapping user friendly name to AG Grid ID and Dropdown search term
                # Format: Name: (col_id, dropdown_search_term)
                lang_config = {
                    'Thai': ('th', 'thai'),
                    'Vietnamese': ('vi', 'viet')
                }
                
                # 2. Iterate through languages
                valid_langs = ['Thai', 'Vietnamese']
                
                # Config: CSV Header -> (AG Grid ID, Dropdown Search Term, Display Text in Drawer)
                lang_config = {
                    'Thai': ('th', 'thai', 'Thai (th)'),
                    'Vietnamese': ('vi', 'viet', 'Vietnamese (vi)')
                }
                
                for csv_col in valid_langs:
                    content_to_add = row.get(csv_col, '').strip()
                    if not content_to_add:
                        continue
                    
                    ag_col_id, dropdown_term, display_text = lang_config.get(csv_col, (None, None, None))
                    
                    print(f"  Processing {csv_col}...")
                    
                    # --- DRAWER LOGIC ---
                    
                    # Check if the language row ALREADY exists in the drawer
                    # We look for the text "Thai (th)" inside a wrapper that also has a "Value" value or input
                    # Using a broad filter first
                    existing_label = page.get_by_text(display_text, exact=True)
                    
                    if existing_label.count() > 0 and existing_label.first.is_visible():
                        print(f"    [Strategy C] Found existing row for '{display_text}'. Updating...")
                        try:
                            # Strategy: Locate the Input relative to the Label
                            # 1. Find the common ancestor row (usually has multiple mat-form-fields)
                            # We can try to traverse up to a container 'row' (div)
                            # Or we can use layout Selector: Input to the right of Label
                            
                            # Let's try to click the wrapper of the text to reset, then TAB to input?
                            # Or better: locate the input in the same hierarchy
                            # The structure is likely: Row > [Field(Language), Field(Value)]
                            
                            # Using XPath to find the input in the same "row-like" container
                            # "Find an input that is near this text"
                            # We can find the 'mat-select' containing the text, then find the 'mat-input' or 'textarea' following it
                            
                            target_input = page.locator(f"//mat-select[.//span[contains(text(), '{display_text}')]]/ancestor::div[contains(@class, 'row') or contains(@class, 'flex')]//following-sibling::mat-form-field//input | //mat-select[.//span[contains(text(), '{display_text}')]]/ancestor::div[contains(@class, 'row') or contains(@class, 'flex')]//following-sibling::mat-form-field//textarea").first

                            if not target_input.is_visible():
                                 # Fallback: simple right-of logic
                                 target_input = page.locator(f"textarea:right-of(:text('{display_text}')), input:right-of(:text('{display_text}'))").first

                            if target_input.is_visible():
                                target_input.click()
                                target_input.fill(content_to_add)
                                print(f"    [UPDATED-EXISTING] {csv_col}")
                            else:
                                print(f"    [ERROR] Found label '{display_text}' but could not find its input.")
                                
                        except Exception as e:
                            print(f"    [ERROR] Updating existing row failed: {e}")

                    else:
                        # --- STRATEGY B: Add Value (New) ---
                        print(f"    [Strategy B] '{display_text}' not found. Attempting 'Add Value'...")
                        
                        try:
                            # Check if "Add Value" exists
                            add_btn = page.locator("[data-test=\"add-value\"]").first
                            
                            if not add_btn.is_visible():
                                 print(f"    [SKIP] 'Add Value' button not found. Cannot add {csv_col}.")
                                 continue
    
                            add_btn.click()
                            page.wait_for_timeout(500)
    
                            # Logic to select language and fill
                            # 1. Open the LAST dropdown (the new one)
                            dropdowns = page.locator("mat-select").all()
                            if not dropdowns:
                                 print("    [ERROR] No dropdowns found after adding value.")
                                 continue
                            
                            # The new row is at the bottom
                            dropdowns[-1].click()
                            
                            # 2. Search language
                            # Wait for search box in dropdown panel
                            lang_search = page.locator("[data-test=\"language-search\"]")
                            lang_search.wait_for(state='visible', timeout=2000)
                            lang_search.fill(dropdown_term)
                            page.wait_for_timeout(500)
                            
                            # 3. Select Option
                            option = page.locator("[data-test=\"language-option\"]").first
                            if option.is_visible():
                                option.click()
                                page.wait_for_timeout(200) # Wait for panel close
                            else:
                                print(f"    [ERROR] Language option '{dropdown_term}' not found.")
                                page.keyboard.press('Escape')
                                continue
    
                            # 4. Fill Input
                            # Use TAB strategy as it was successful/requested
                            print("    [Drawer] Language selected. Tabbing to value input...")
                            page.keyboard.press('Tab')
                            page.wait_for_timeout(200)
    
                            # Check focus
                            focused_tag = page.evaluate("document.activeElement.tagName")
                            if focused_tag in ['INPUT', 'TEXTAREA']:
                                page.keyboard.type(content_to_add)
                                print(f"    [FILLED-NEW] {csv_col}")
                            else:
                                # Fallback locator
                                print("    [DEBUG] Tab failed. Trying explicit last-input locator...")
                                inputs = page.locator("textarea, input[data-test='value-input']").all()
                                visible_inputs = [i for i in inputs if i.is_visible()]
                                if visible_inputs:
                                    visible_inputs[-1].fill(content_to_add)
                                    print(f"    [FILLED-NEW-CLICK] {csv_col}")
                                else:
                                    print("    [ERROR] No value input found.")
    
                        except Exception as e:
                            print(f"    [ERROR] Add Value failed for {csv_col}: {e}")

                # Save the drawer/modal after processing all languages for this row
                save_btn = page.locator("[data-test=\"create-label-save\"]").first
                if save_btn.is_visible():
                    save_btn.click()
                    print("    [CLICKED SAVE]")
                    page.wait_for_timeout(1000)
                else:
                    print("    [PRESSING ENTER TO SAVE]")
                    page.keyboard.press('Enter')
                    page.wait_for_timeout(1000)

            except Exception as e:
                print(f"  [ERROR] Search/Row error: {e}")
                continue

            except Exception as e:
                print(f"  [ERROR] Search/Row error: {e}")
                continue
            
            # Wait a bit before next row
            page.wait_for_timeout(500)

        print("\nProcessing Complete!")
        browser.close()

if __name__ == "__main__":
    run()
