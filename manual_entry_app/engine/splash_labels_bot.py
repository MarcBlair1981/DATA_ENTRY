import csv
import time
from playwright.sync_api import sync_playwright

class SplashLabelBot:
    def __init__(self, log_callback=None, status_callback=None, pause_event=None, stop_event=None):
        self.log = log_callback if log_callback else print
        self.update_status = status_callback if status_callback else lambda *args: None
        self.pause_event = pause_event
        self.stop_event = stop_event

    def run(self, csv_file_path, mode='import', backfill_en=False, workflow_mode='labels'):
        """
        mode: 'import' or 'verify'
        backfill_en: True/False
        workflow_mode: 'labels' or 'questions'
        """
        # Load CSV
        rows = self._load_csv(csv_file_path)
        if not rows:
            return

        total_rows = len(rows)
        self.log(f"Loaded {total_rows} rows. Starting {mode} mode...", "INFO")
        self.update_status("RUNNING", f"Starting {mode}...", 0, total_rows)

        with sync_playwright() as p:
            # Launch Browser
            browser = p.chromium.launch(headless=False, slow_mo=500)
            context = browser.new_context()
            page = context.new_page()

            TARGET_URL = 'https://backoffice.splash.tech/labels' # Configurable later
            
            self.log(f"Navigating to {TARGET_URL}...", "INFO")
            page.goto(TARGET_URL, timeout=60000)

            self.log("Waiting for user to Log In...", "WARNING")
            self.log("STEP 1: Log In.", "INFO")
            self.log("STEP 2: Select the CLIENT you want to update.", "INFO")
            self.log("STEP 3: Navigate to the 'Labels' page.", "INFO")
            self.log("Waiting 45 seconds for you to get ready...", "WARNING")
            
            # Wait for user setup
            # In a real app we might want a "Start" button in the UI *after* login,
            # but for now we stick to the timer pattern or check for a specific element.
            page.wait_for_timeout(45000) # 45s Wait

            processed_count = 0
            
            for i, row in enumerate(rows):
                # Check for Stop
                if self.stop_event and self.stop_event.is_set():
                    self.log("🛑 Stop requested. Aborting...", "WARNING")
                    break

                # Check for Pause
                if self.pause_event and not self.pause_event.is_set():
                    self.log("⏸️ Paused... Waiting to resume.", "WARNING")
                    self.pause_event.wait() # Block here until set()

                self.update_status("RUNNING", f"Processing {i+1}/{total_rows}", i+1, total_rows)
                
                # SEARCH STRATEGY: KEY is King 👑
                # If we have a 'Key' column, use it. It's unique and strictly formatted.
                # If not, fall back to 'English' text logic.
                
                search_val = None
                search_col = None
                
                # Check for Key
                for k in ['Key', 'key', 'KEY']:
                    if k in row and row[k].strip():
                        search_val = row[k].strip()
                        search_col = 'key' # AG Grid ID for key column is usually 'key' or 'keyName'
                        break
                
                if not search_val:
                    # Fallback to English
                    for col in ['English', 'EN', 'en', 'english']:
                         case_insensitive_key = next((k for k in row.keys() if k.lower() == col.lower()), None)
                         if case_insensitive_key:
                             search_val = row[case_insensitive_key].strip()
                             search_col = 'en'
                             break

                if not search_val:
                    self.log(f"[SKIP] No identifiable search term (Key or English) in row {i+1}", "WARNING")
                    continue
                
                self.log(f"Processing: '{search_val}' (via {search_col})", "INFO")

                try:
                    # --- CLEANUP / SAFETY ---
                    if page.locator('.mat-mdc-dialog-container').is_visible():
                         self.log("Found open dialog from previous step. Closing...", "WARNING")
                         self._close_drawer(page)

                    # --- SEARCH ---
                    search_box = page.locator("input[placeholder='Search']").first
                    if not search_box.is_visible():
                         self.log("Search box not found! Are you on the right page?", "ERROR")
                         continue
                        
                    search_box.click()
                    search_box.fill("")
                    search_box.press_sequentially(search_val, delay=50) 
                    page.wait_for_timeout(1500) 

                    # --- FIND ROW ---
                    # Check for empty grid
                    grid_rows = page.locator('.ag-row')
                    is_new_question = False

                    if grid_rows.count() == 0:
                        if workflow_mode == 'questions' and search_val:
                            # CREATE NEW QUESTION FLOW
                            self.log(f"  [Question Mode] '{search_val}' not found. Creating NEW...", "INFO")
                            
                            create_btn = page.locator('button', has_text='Create New Question Template').first
                            if not create_btn.is_visible():
                                self.log("  [ERROR] 'Create New Question Template' button not found.", "ERROR")
                                continue
                                
                            create_btn.click()
                            page.wait_for_timeout(1000)
                            
                            is_new_question = True
                            
                            # Fill Text (English)
                            # Assuming the first input is 'Text' or finding by label
                            # Screenshot shows 'Text' label
                            text_input = page.locator('mat-form-field').filter(has_text='Text').locator('input, textarea').first
                            if text_input.is_visible():
                                text_input.fill(search_val)
                                page.wait_for_timeout(500)
                            else:
                                self.log("  [ERROR] Could not find 'Text' input for new question.", "ERROR")
                                self._close_drawer(page) # Cancel
                                continue
                                
                            # Click Translate - reusing logic from Update flow?
                            # We can just jump to the "Question Mode" branching logic 
                            # But we are not "clicking a row" here.
                            # So we copy the translate click logic here.
                            
                            self.log("  [Question Mode] Clicking Translate icon...", "INFO")
                            
                            # Use robust data-test locator found in debug
                            try:
                                translate_btn = page.locator('app-input-label[data-test="question-text"] mat-icon[data-test="language-icon"]').last
                                if translate_btn.is_visible():
                                    translate_btn.click()
                                    page.wait_for_timeout(1000)
                                else:
                                    # Fallback to old method just in case
                                    self.log("  [WARN] Primary translate locator not visible. Trying fallback...", "WARNING")
                                    dialog = page.locator('.mat-mdc-dialog-container').last
                                    dialog.locator('mat-icon').filter(has_text='translate').last.click()
                                    page.wait_for_timeout(1000)
                            except Exception as e:
                                self.log(f"  [ERROR] Failed to click Translate button: {e}", "ERROR")
                                self._close_drawer(page)
                                continue
                                
                        else:
                            self.log(f"[SKIP] No rows found for: {search_val}", "WARNING")
                            continue
                    
                    else:
                        # STANDARD UPDATE FLOW (Row Exists)
                        # Verification Strategy dependent on what we searched
                        target_cell = None
                        if search_col == 'key':
                            # Look in Key column (likely col-id="key" or first column)
                            # We try col-id="key" first, then fall back to text match in row
                            target_cell = page.locator('.ag-cell[col-id="key"]').filter(has_text=search_val).first
                            if not target_cell.is_visible():
                                 target_cell = page.locator('.ag-cell').filter(has_text=search_val).first
                        else:
                            # Look in English column
                            target_cell = page.locator('.ag-cell[col-id="en"]').filter(has_text=search_val).first
                            if not target_cell.is_visible():
                                target_cell = page.locator('.ag-cell[col-id="en"]').get_by_text(search_val, exact=True).first
                        
                        if not target_cell or not target_cell.is_visible():
                            self.log(f"[SKIP] Row not visible for: {search_val}", "WARNING")
                            continue

                        # Get Row
                        target_row = page.locator('.ag-row').filter(has=target_cell).first
                        
                        # --- DRAWER INTERACTION ---
                        # Open Drawer
                        target_row.click()
                        page.wait_for_timeout(1000)

                        if workflow_mode == 'questions':
                            self.log("  [Question Mode] Looking for Translate button (Edit Mode)...", "INFO")
                            
                            try:
                                # Use robust data-test locator
                                translate_btn = page.locator('app-input-label[data-test="question-text"] mat-icon[data-test="language-icon"]').last
                                
                                if translate_btn.is_visible():
                                    translate_btn.click()
                                    self.log("  [Question Mode] Clicked Translate. Waiting for Label editor...", "INFO")
                                    page.wait_for_timeout(1000)
                                else:
                                    self.log("  [WARN] Primary translate locator not visible in Edit Mode. Trying fallback...", "WARNING")
                                    # Fallback
                                    dialog = page.locator('.mat-mdc-dialog-container').last
                                    dialog.locator('mat-icon').filter(has_text='translate').last.click()
                                    page.wait_for_timeout(1000)

                            except Exception as e:
                                self.log(f"  [ERROR] Translate button interactions failed: {e}", "ERROR")
                                continue

                    # --- STANDARD LABEL LOGIC (Shared) ---
                    # At this point, we should see the "Update Label" interface
                    if not page.locator('h2', has_text='Update Label').is_visible():
                         # Maybe it's just the header checking?
                         # Just continue and let the field finding logic handle it.
                         pass

                    # Define Languages
                    lang_config = {
                        'Thai': {'code': 'th', 'search_term': 'thai', 'drawer_label': 'Thai (th)', 'aliases': ['thai', 'th']},
                        'Vietnamese': {'code': 'vi', 'search_term': 'viet', 'drawer_label': 'Vietnamese (vi)', 'aliases': ['vietnamese', 'vi', 'vn']},
                        'Spanish': {'code': 'es', 'search_term': 'spanish', 'drawer_label': 'Spanish (es)', 'aliases': ['spanish', 'es', 'esp']},
                        'German': {'code': 'de', 'search_term': 'german', 'drawer_label': 'German (de)', 'aliases': ['german', 'de']},
                        'Japanese': {'code': 'ja', 'search_term': 'japanese', 'drawer_label': 'Japanese (ja)', 'aliases': ['japanese', 'ja', 'jp']},
                        'French': {'code': 'fr', 'search_term': 'french', 'drawer_label': 'French (fr)', 'aliases': ['french', 'fr']},
                        'Hungarian': {'code': 'hu', 'search_term': 'hungarian', 'drawer_label': 'Hungarian (hu)', 'aliases': ['hungarian', 'hu']},
                        'Dutch': {'code': 'nl', 'search_term': 'dutch', 'drawer_label': 'Dutch (nl)', 'aliases': ['dutch', 'nl']},
                        'Italian': {'code': 'it', 'search_term': 'italian', 'drawer_label': 'Italian (it)', 'aliases': ['italian', 'it']},
                        'Portuguese': {'code': 'pt', 'search_term': 'portuguese', 'drawer_label': 'Portuguese (pt)', 'aliases': ['portuguese', 'pt', 'br']},
                    }

                    # Conditionally add English
                    if backfill_en:
                        lang_config['English'] = {'code': 'en', 'search_term': 'english', 'drawer_label': 'English (en)', 'aliases': ['english', 'en']}

                    # Heuristic: Normalize headers to find matches
                    # Create a map of normalized_header -> original_header
                    header_map = {k.strip().lower(): k for k in row.keys()}
                    
                    found_langs = []

                    for lang_key, config in lang_config.items():
                        # Check all aliases (e.g. 'spanish', 'es', 'esp')
                        for alias in config['aliases']:
                            if alias in header_map:
                                found_langs.append((lang_key, header_map[alias]))
                                break # Found a match for this language, stop checking aliases
                    
                    if not found_langs:
                         self.log(f"  [WARN] No matching language columns found. (Available: {list(lang_config.keys())})", "WARNING")
                         # Should we save anyway if we created a new question? 
                         # Yes, otherwise we lose the question.
                         pass
                    
                    else:
                        for config_key, csv_col in found_langs:
                            config = lang_config[config_key]
                            target_val = row.get(csv_col, '').strip()
                            if not target_val:
                                continue

                            if mode == 'verify':
                                self._verify_entry(page, config['drawer_label'], target_val, csv_col)
                            else:
                                self._update_entry(page, config, target_val, csv_col)
                    
                    # --- FINAL SAVE STEP ---
                    # We MUST save the "Update Label" modal if we made changes.
                    # Currently _update_entry mostly handles filling.
                    # Screenshot shows a "Save" button in the dialog.
                    if mode != 'verify':
                        self.log("  [Step] Saving Translation Changes...", "INFO")
                        
                        # --- 1. SAVE LABEL EDITOR (Topmost Dialog) ---
                        # We specifically target the LAST open dialog, which is the Label Editor.
                        top_dialog = page.locator('.mat-mdc-dialog-container').last
                        label_save = top_dialog.locator('button', has_text='Save').first
                        
                        if label_save.is_visible() and label_save.is_enabled():
                            label_save.click()
                            # Critical: Wait for this specific dialog to close to confirm save
                            # This prevents us from interacting with the underlying dialog too early
                            try:
                                top_dialog.wait_for(state='hidden', timeout=3000)
                            except:
                                self.log("  [WARN] Label dialog didn't close immediately. Pressing Escape...", "WARNING")
                                page.keyboard.press("Escape")
                        else:
                            self.log("  [WARN] Could not find/click Save on Label modal. Trying Escape...", "WARNING")
                            page.keyboard.press("Escape")
                        
                        page.wait_for_timeout(500) # Settle time

                        page.wait_for_timeout(500) # Settle time

                        # --- 2. SAVE QUESTION TEMPLATE (Underlying Dialog) ---
                        # In Questions Mode, we have a parent Question Template dialog that must be saved.
                        # This applies to BOTH 'New' and 'Update' flows.
                        if is_new_question or workflow_mode == 'questions':
                            self.log("  [Step] Saving Question Template...", "INFO")
                            
                            # Now the Topmost dialog should be the Question Template
                            question_dialog = page.locator('.mat-mdc-dialog-container').last
                            
                            # Check if the remaining dialog is actually a Question Template
                            # Look for the header text "Question Template"
                            header = question_dialog.locator('h1, h2, h3').filter(has_text='Question Template').first
                            
                            if header.is_visible():
                                question_save = question_dialog.locator('button', has_text='Save').first
                                if question_save.is_visible() and question_save.is_enabled():
                                    question_save.click()
                                    try:
                                        question_dialog.wait_for(state='hidden', timeout=3000)
                                        if is_new_question:
                                            self.log(f"  [SUCCESS] Created New Question: '{search_val}'", "SUCCESS")
                                        else:
                                            self.log(f"  [SUCCESS] Updated Question: '{search_val}'", "SUCCESS")
                                    except:
                                        self.log("  [WARN] Question dialog didn't close.", "WARNING")
                                else:
                                    self.log("  [ERROR] Could not find Save button for Question Template.", "ERROR")
                                    page.keyboard.press("Escape")
                            else:
                                # Not a question template? Maybe Labels mode was active but workflow_mode says questions?
                                # Just log and escape if we are stuck.
                                if is_new_question:
                                     self.log("  [WARN] Expected Question Template but header not found.", "WARNING")
                                page.keyboard.press("Escape")

                except Exception as e:
                    self.log(f"Error processing row: {e}", "ERROR")
                    # Try to recover state
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                    page.keyboard.press("Escape")

            self.log("Task Completed!", "SUCCESS")
            browser.close()

    def _load_csv(self, file_path):
        rows = []
        # Priority: utf-8-sig (Handles BOM) -> utf-8 -> latin-1
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        delimiters = [',', ';', '\t']
        
        for enc in encodings:
            try:
                with open(file_path, mode='r', encoding=enc, newline='') as f:
                    # Read sample for sniffing
                    sample = f.read(1024)
                    f.seek(0)
                    
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=delimiters)
                        reader = csv.DictReader(f, dialect=dialect)
                    except csv.Error:
                        # Sniffer failed, try default comma
                        f.seek(0)
                        reader = csv.DictReader(f)

                    rows = list(reader)
                
                # Log success and headers
                if rows:
                    raw_headers = list(rows[0].keys())
                    
                    # Robust Header Cleaning: Remove BOM and whitespace from ALL keys
                    cleaned_rows = []
                    for r in rows:
                        cleaned_row = {k.replace('\ufeff', '').strip(): v for k, v in r.items()}
                        cleaned_rows.append(cleaned_row)
                    rows = cleaned_rows
                    
                    headers = list(rows[0].keys())
                    self.log(f"CSV Loaded ({enc}). Raw Headers: {raw_headers} -> Cleaned: {headers}", "INFO")
                    
                    # Validation: Check if it looks like we failed to split
                    if len(headers) == 1 and any(d in headers[0] for d in delimiters):
                        self.log(f"WARNING: CSV parsing might have failed (Single column found containing delimiters). Headers: {headers}", "WARNING")
                        continue 
                    
                    return rows
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.log(f"CSV Read Error ({enc}): {e}", "ERROR")
        
        self.log("Failed to read CSV with any encoding.", "ERROR")
        return []

    def _update_entry(self, page, config, target_val, lang_name):
        # 1. Check if language row exists in Drawer
        # Robust check: Look for the text inside the dialog using multiple potential containers
        # The text 'Dutch (nl)' usually appears in a mat-select or mat-form-field
        
        lang_row = None
        
        # Strategy A: Look for mat-select (likely structure)
        candidate = page.locator('mat-select', has_text=config['drawer_label']).first
        if candidate.is_visible():
            lang_row = candidate
        
        # Strategy B: Look for generic row wrapper
        if not lang_row:
             candidate = page.locator('div.flex.flex-row', has_text=config['drawer_label']).first
             if candidate.is_visible():
                 lang_row = candidate

        # Strategy C: Look for any strong text match in the dialog
        # Be careful not to match the 'Add Value' dropdown options if they are somehow visible
        if not lang_row:
             # scoping to dialog content might help
             # Use explicit text= to avoid partial matches on similar languages if possible, 
             # but exact=True is safer.
             candidate = page.locator('mat-dialog-content').get_by_text(config['drawer_label'], exact=True).first
             if candidate.is_visible():
                  lang_row = candidate
        
        if lang_row and lang_row.is_visible():
            # UPDATE EXISTING
            self.log(f"  [{lang_name}] Updating existing entry...", "INFO")
            # Refined Strategy:
            # The previous bot logic for "Update" (if row exists) was:
            # locate language label -> find sibling input?
            # Actually, previous bot mostly relied on "Add" if missing.
            # Let's try to find an input near the label.
            
            # Using the "Edit" button if present? usually inputs are just there.
            # Let's try locating the textarea/input in the same container.
            
            input_locator = lang_row.locator('xpath=..').locator('textarea, input').first
            if not input_locator.is_visible():
                 # Fallback: traverse up and find 'mat-form-field'
                 input_locator = lang_row.locator('xpath=../..').locator('textarea, input').first
            
            if input_locator.is_visible():
                input_locator.fill(target_val)
                # Auto-save triggers on blur or enter? Usually explicit Save button?
                # Previous bot pressed Enter.
                # page.keyboard.press('Enter') # Might submit form?
                # Usually there is a "Save" button at the bottom of drawer?
                pass 
            else:
                 self.log(f"  [{lang_name}] Could not find input for existing row.", "ERROR")
                 return

        else:
            # ADD NEW
            self.log(f"  [{lang_name}] Adding new entry for {config['drawer_label']}...", "INFO")
            
            # 1. Click 'Add Value'
            add_btn = page.locator("[data-test=\"add-value\"]").first
            if not add_btn.is_visible():
                 self.log(f"  [{lang_name}] 'Add Value' button not found. Cannot add new language.", "ERROR")
                 return

            add_btn.click()
            page.wait_for_timeout(500)

            try:
                # 2. Open the LAST dropdown (the new one we just added)
                # The app likely appends a new row at the bottom.
                dropdowns = page.locator("mat-select").all()
                if not dropdowns:
                     self.log(f"  [{lang_name}] Error: No dropdowns found after clicking Add.", "ERROR")
                     return
                
                # Click the last dropdown to open language selection
                dropdowns[-1].click()
                
                # 3. Search for Language
                # Wait for the search box inside the dropdown panel
                lang_search = page.locator("[data-test=\"language-search\"]")
                lang_search.wait_for(state='visible', timeout=2000)
                lang_search.fill(config['search_term']) # e.g. 'thai'
                page.wait_for_timeout(500)
                
                # 4. Select Option
                # Usually the first option is the best match after search
                option = page.locator("[data-test=\"language-option\"]").first
                if option.is_visible():
                    option.click()
                    page.wait_for_timeout(200) # Wait for panel to close
                else:
                    self.log(f"  [{lang_name}] Error: Language option '{config['search_term']}' not found in dropdown.", "ERROR")
                    page.keyboard.press('Escape') # Close dropdown
                    return

                # 5. Fill Input
                # Use Keyboard TAB strategy to move from Dropdown -> Input
                # This was effective in the original script.
                page.keyboard.press('Tab')
                page.wait_for_timeout(200)
                
                # Verify focus is on an input
                focused_tag = page.evaluate("document.activeElement.tagName")
                if focused_tag in ['INPUT', 'TEXTAREA']:
                    # Use sequential press (type) to ensure validation triggers!
                    # This mimics the "typing" fix we discussed.
                    page.keyboard.type(target_val) 
                    
                    # HIT TAB AGAIN to trigger blur/validation for the Save button
                    page.keyboard.press('Tab')
                    self.log(f"  [{lang_name}] Filled new value (via Tab navigation).", "INFO")
                else:
                    # Fallback: Try to find the input explicitly if Tab didn't land us there
                    self.log(f"  [{lang_name}] Tab focus failed (landed on {focused_tag}). Trying explicit locator...", "WARNING")
                    # Look for the last input in the DOM
                    inputs = page.locator("textarea, input[data-test='value-input']").all()
                    visible_inputs = [i for i in inputs if i.is_visible()]
                    if visible_inputs:
                        visible_inputs[-1].fill(target_val)
                        visible_inputs[-1].press("Tab") # Trigger validation
                        self.log(f"  [{lang_name}] Filled new value (via explicit locator).", "INFO")
                    else:
                        self.log(f"  [{lang_name}] Error: Could not find input to fill.", "ERROR")

            except Exception as e:
                self.log(f"  [{lang_name}] Error during Add Value flow: {e}", "ERROR")
                # Try to recover by closing drawer?
                pass
                
        # SAVE (Common)
        # Find global "Save" button in drawer/dialog
        # Use a more specific locator if possible, or fallback to text.
        save_btn = page.locator('button', has_text='Save').last 
        
        if save_btn.is_visible():
            # Attempt to enable it if disabled (Try bluring input)
            if not save_btn.is_enabled():
                page.keyboard.press("Tab")
                page.wait_for_timeout(200)
            
            if save_btn.is_enabled():
                save_btn.click()
                page.wait_for_timeout(500) # Wait for save to process
                self.log(f"  [{lang_name}] Saved: {target_val}", "SUCCESS")
                
                # Wait for interaction to close?
                # Sometimes save doesn't close immediately. 
                # If dialog remains open, it blocks next search.
                # Let's wait for it to disappear?
                try:
                    save_btn.wait_for(state='hidden', timeout=2000)
                except:
                    pass # It's okay if it stays, but we hope it closes.
            else:
                self.log(f"  [{lang_name}] Warning: 'Save' button disabled. Value might be identical or invalid.", "WARNING")
                # CRITICAL: If we don't save, we MUST Close/Cancel to unblock the next row!
                self._close_drawer(page)

    def _close_drawer(self, page):
        """Helper to close any open drawer/dialog to prevent blocking."""
        # Try finding a Cancel button
        cancel_btn = page.locator('button', has_text='Cancel').last
        if cancel_btn.is_visible() and cancel_btn.is_enabled():
            cancel_btn.click()
            page.wait_for_timeout(500)
            return

        # Try Escape key
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        # SENSE CHECKER LOGIC
        lang_row = page.locator('div.flex.flex-row', has_text=drawer_label).first
        
        if not lang_row.is_visible():
            self.log(f"  [MISSING] {lang_name} entry not found in drawer.", "ERROR")
            return

        # Find value... similar to update logic
        # It might be in a readonly view or input
        input_locator = lang_row.locator('xpath=../..').locator('textarea, input').first
        
        current_val = ""
        if input_locator.is_visible():
            current_val = input_locator.input_value()
        else:
            # Maybe just text?
            current_val = lang_row.locator('xpath=..').inner_text()
        
        # Clean up
        current_val = current_val.strip()
        
        if current_val == target_val:
            self.log(f"  [MATCH] {lang_name}: {current_val}", "SUCCESS")
        else:
            self.log(f"  [MISMATCH] {lang_name}. Expected: '{target_val}', Found: '{current_val}'", "ERROR")
