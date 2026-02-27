import csv
import time
import re
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
        workflow_mode: 'labels', 'questions', or 'participants'
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
            if workflow_mode == 'participants':
                self.log("STEP 3: Navigate to the 'Participants (Competitors)' page.", "INFO")
            else:
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

                # === PARTICIPANTS MODE ===
                if workflow_mode == 'participants':
                    try:
                        self._process_participants(page, row, search_val, mode, backfill_en)
                    except Exception as e:
                        self.log(f"Error processing participant '{search_val}': {e}", "ERROR")
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                        page.keyboard.press("Escape")
                    continue

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
                            
                            if not target_cell.is_visible():
                                # Fallback: Look in any cell (critical for Questions mode where col-id is usually 'text')
                                target_cell = page.locator('.ag-cell').filter(has_text=search_val).first
                        
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
                        'Amharic': {'code': 'am', 'search_term': 'amharic', 'drawer_label': 'Amharic (am)', 'aliases': ['amharic', 'am']},
                        'Danish': {'code': 'da', 'search_term': 'danish', 'drawer_label': 'Danish (da)', 'aliases': ['danish', 'da']},
                        'Norwegian': {'code': 'no', 'search_term': 'norweg', 'drawer_label': 'Norwegian (no)', 'aliases': ['norwegian', 'no']},
                        'Bulgarian': {'code': 'bg', 'search_term': 'bulgari', 'drawer_label': 'Bulgarian (bg)', 'aliases': ['bulgarian', 'bg']},
                        'Russian': {'code': 'ru', 'search_term': 'russian', 'drawer_label': 'Russian (ru)', 'aliases': ['russian', 'ru']},
                        'Serbian': {'code': 'sr', 'search_term': 'serbian', 'drawer_label': 'Serbian (sr)', 'aliases': ['serbian', 'sr']},
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
                                self._update_entry(page, config, target_val, csv_col, skip_save=True)
                    
                    # --- FINAL SAVE STEP ---
                    # We MUST save the "Update Label" modal if we made changes.
                    # Currently _update_entry mostly handles filling.
                    # Screenshot shows a "Save" button in the dialog.
                    if mode != 'verify':
                        self.log("  [Step] Saving Translation Changes...", "INFO")
                        
                        # --- 1. SAVE LABEL EDITOR (Topmost Dialog) ---
                        # We specifically target the LAST open dialog, which is the Label Editor.
                        page.wait_for_timeout(1000)

                        label_dialog = page.locator('.mat-mdc-dialog-container').filter(has_text=re.compile(r'Update Label', re.I)).last
                        if not label_dialog.is_visible():
                            label_dialog = page.locator('.mat-mdc-dialog-container').last

                        # FORCE DIRTY STATE: Use the LAST visible input to trigger validation
                        try:
                            last_input = label_dialog.locator('input, textarea').last
                            if last_input.is_visible():
                                last_input.click()
                                page.keyboard.type(" ") 
                                page.keyboard.press("Backspace") 
                                page.keyboard.press("Tab")
                                page.wait_for_timeout(500)
                        except:
                            pass

                        label_save = label_dialog.locator('button:has-text("Save")').first

                        if label_save.is_visible():
                            if not label_save.is_enabled():
                                 self.log("  [WARN] Save button is disabled. Trying to click dialog background to force blur...", "WARNING")
                                 label_dialog.locator('.mat-mdc-dialog-surface').click(position={'x': 10, 'y': 10})
                                 page.wait_for_timeout(500)

                            if label_save.is_enabled():
                                self.log("  [Step] Clicking Label Save...", "INFO")
                                label_save.click(force=True)
                                try:
                                    label_dialog.wait_for(state='hidden', timeout=7000)
                                except:
                                    self.log("  [WARN] Label dialog didn't close immediately. Pressing Escape...", "WARNING")
                                    page.keyboard.press("Escape")
                            else:
                                self.log("  [WARN] Save button persistent disabled. Closing.", "WARNING")
                                page.keyboard.press("Escape")
                        else:
                            self.log("  [WARN] Could not find/click Save on Label modal. Trying broad search...", "WARNING")
                            broad_save = page.locator('button:has-text("Save")').last
                            if broad_save.is_visible() and broad_save.is_enabled():
                                broad_save.click(force=True)
                            else:
                                page.keyboard.press("Escape")
                        
                        page.wait_for_timeout(1500) # Settle time

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
                                # FORCE DIRTY STATE on parent:
                                try:
                                    last_input = question_dialog.locator('input, textarea').last
                                    if last_input.is_visible():
                                        last_input.click()
                                        page.keyboard.type(" ") 
                                        page.keyboard.press("Backspace") 
                                        page.keyboard.press("Tab")
                                        page.wait_for_timeout(500)
                                except:
                                    pass

                                question_save = question_dialog.locator('button:has-text("Save")').first
                                if question_save.is_visible() and not question_save.is_enabled():
                                    question_dialog.locator('.mat-mdc-dialog-surface').click(position={'x': 10, 'y': 10})
                                    page.wait_for_timeout(500)

                                if question_save.is_visible() and question_save.is_enabled():
                                    self.log("  [Step] Clicking Question Template Save...", "INFO")
                                    question_save.click(force=True)
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

    def _update_entry(self, page, config, target_val, lang_name, skip_save=False):
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
            input_locator = None

            # Strategy 1: Go up to mat-form-field ancestor (most specific/reliable)
            try:
                mff = lang_row.locator('xpath=./ancestor::mat-form-field[1]')
                if mff.count() == 1 and mff.is_visible():
                    # The value input is the SIBLING mat-form-field, not this one
                    # So go up one more level and find all inputs there
                    parent = mff.locator('xpath=..')
                    inputs = parent.locator('input, textarea').all()
                    visible_inputs = [i for i in inputs if i.is_visible()]
                    if visible_inputs:
                        input_locator = visible_inputs[-1]  # Last input = value field
            except:
                pass

            # Strategy 2: Go up to nearest flex/grid div ancestor (separately, no union)
            if not input_locator or not input_locator.is_visible():
                try:
                    flex_ancestor = lang_row.locator('xpath=./ancestor::div[contains(@class,"flex")][1]')
                    if flex_ancestor.count() == 1 and flex_ancestor.is_visible():
                        inputs = flex_ancestor.locator('input, textarea').all()
                        visible_inputs = [i for i in inputs if i.is_visible()]
                        if visible_inputs:
                            input_locator = visible_inputs[-1]
                except:
                    pass

            # Strategy 3: Page-level filter (scoped to dialog content)
            if not input_locator or not input_locator.is_visible():
                try:
                    dialog_content = page.locator('mat-dialog-content').first
                    row_container = dialog_content.locator('mat-form-field').filter(has=lang_row).first
                    if row_container.is_visible():
                        parent = row_container.locator('xpath=..')
                        inputs = parent.locator('input, textarea').all()
                        visible_inputs = [i for i in inputs if i.is_visible()]
                        if visible_inputs:
                            input_locator = visible_inputs[-1]
                except:
                    pass

            if input_locator and input_locator.is_visible():
                current_val = input_locator.input_value().strip()
                
                # Check if input is disabled or readonly
                is_editable = page.evaluate("(el) => !el.disabled && !el.readOnly", input_locator.element_handle())
                
                if current_val == target_val.strip():
                    self.log(f"  [{lang_name}] Already correct: '{current_val}'", "SUCCESS")
                    return
                
                if not is_editable:
                    self.log(f"  [{lang_name}] Field is READONLY/DISABLED. Skipping update.", "WARNING")
                    return

                # UPDATE EXISTING
                self.log(f"  [{lang_name}] Updating: '{current_val}' -> '{target_val}'", "INFO")
                input_locator.click(force=True)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                input_locator.fill(target_val)
                input_locator.press("Tab")
            else:
                self.log(f"  [{lang_name}] Could not find input for existing row. Trying keyboard fallback...", "WARNING")
                # Use force=True because the mat-select might be 'disabled' but we still want to grab focus near it
                try:
                    lang_row.click(force=True, timeout=2000)
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(200)
                    page.keyboard.type(target_val)
                    page.keyboard.press("Tab")
                except:
                    self.log(f"  [{lang_name}] Fallback failed. Row may be completely non-interactive.", "ERROR")


        else:
            # ADD NEW
            self.log(f"  [{lang_name}] Adding new entry for {config['drawer_label']}...", "INFO")
            
            # 1. Click 'Add Value'
            add_btn = page.locator("[data-test=\"add-value\"], button:has-text(\"Add Value\")").first
            if not add_btn.is_visible():
                 # Try finding by icon
                 add_btn = page.locator("mat-icon:has-text(\"add\")").locator("xpath=..").first
                 
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
                
        # SAVE (Common) - Skip if caller handles saving (e.g. participants mode)
        if skip_save:
            self.log(f"  [{lang_name}] Filled: {target_val} (save deferred)", "INFO")
            return

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

    def _process_participants(self, page, row, search_val, mode, backfill_en):
        """
        Process a single participant (country) entry.
        Handles multiple matching rows (e.g., same country with shirt + flag logos).
        For each match: Click row -> Competitor dialog -> Translate icon -> Update Label -> Save.
        """
        # --- FULL LANGUAGE CONFIG ---
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
            'Amharic': {'code': 'am', 'search_term': 'amharic', 'drawer_label': 'Amharic (am)', 'aliases': ['amharic', 'am']},
            'Danish': {'code': 'da', 'search_term': 'danish', 'drawer_label': 'Danish (da)', 'aliases': ['danish', 'da']},
            'Norwegian': {'code': 'no', 'search_term': 'norweg', 'drawer_label': 'Norwegian (no)', 'aliases': ['norwegian', 'no']},
            'Bulgarian': {'code': 'bg', 'search_term': 'bulgari', 'drawer_label': 'Bulgarian (bg)', 'aliases': ['bulgarian', 'bg']},
            'Russian': {'code': 'ru', 'search_term': 'russian', 'drawer_label': 'Russian (ru)', 'aliases': ['russian', 'ru']},
            'Serbian': {'code': 'sr', 'search_term': 'serbian', 'drawer_label': 'Serbian (sr)', 'aliases': ['serbian', 'sr']},
        }
        if backfill_en:
            lang_config['English'] = {'code': 'en', 'search_term': 'english', 'drawer_label': 'English (en)', 'aliases': ['english', 'en']}

        # Determine which CSV columns match our languages
        header_map = {k.strip().lower(): k for k in row.keys()}
        found_langs = []
        for lang_key, config in lang_config.items():
            for alias in config['aliases']:
                if alias in header_map:
                    found_langs.append((lang_key, header_map[alias]))
                    break

        if not found_langs:
            self.log(f"  [WARN] No matching language columns found in CSV.", "WARNING")
            return

        # --- CLEANUP: Close any open dialogs ---
        if page.locator('.mat-mdc-dialog-container').is_visible():
            self._close_drawer(page)

        # --- SEARCH ---
        search_box = page.locator("input[placeholder='Search']").first
        if not search_box.is_visible():
            self.log("Search box not found! Are you on the Participants page?", "ERROR")
            return

        search_box.click()
        search_box.fill("")
        search_box.press_sequentially(search_val, delay=50)
        page.wait_for_timeout(2000)

        # --- FIND ALL EXACT MATCHES ---
        grid_rows = page.locator('.ag-row')
        total_visible = grid_rows.count()

        if total_visible == 0:
            self.log(f"[SKIP] No rows found for: {search_val}", "WARNING")
            return

        # Count exact name matches (first cell = Name column)
        exact_match_count = 0
        for j in range(total_visible):
            try:
                name_cell = grid_rows.nth(j).locator('.ag-cell').first
                if name_cell.inner_text().strip().lower() == search_val.lower():
                    exact_match_count += 1
            except:
                pass

        if exact_match_count == 0:
            self.log(f"[SKIP] No exact match for '{search_val}' ({total_visible} partial results)", "WARNING")
            return

        self.log(f"Found {exact_match_count} exact match(es) for '{search_val}'", "INFO")

        # --- PROCESS EACH MATCH ---
        processed = 0
        for match_num in range(exact_match_count):
            # Check for stop
            if self.stop_event and self.stop_event.is_set():
                break
            # Check for pause
            if self.pause_event and not self.pause_event.is_set():
                self.log("⏸️ Paused... Waiting to resume.", "WARNING")
                self.pause_event.wait()

            self.log(f"  >> Processing match {match_num + 1}/{exact_match_count}...", "INFO")

            # Re-search if not the first match (DOM may have refreshed after save)
            if match_num > 0:
                page.wait_for_timeout(1000)
                search_box = page.locator("input[placeholder='Search']").first
                search_box.click()
                search_box.fill("")
                search_box.press_sequentially(search_val, delay=50)
                page.wait_for_timeout(2000)

            # Locate the nth exact match
            grid_rows = page.locator('.ag-row')
            target_row = None
            current_match = 0
            for j in range(grid_rows.count()):
                try:
                    name_cell = grid_rows.nth(j).locator('.ag-cell').first
                    if name_cell.inner_text().strip().lower() == search_val.lower():
                        if current_match == match_num:
                            target_row = grid_rows.nth(j)
                            break
                        current_match += 1
                except:
                    pass

            if not target_row:
                self.log(f"  [WARN] Could not locate match {match_num + 1}. Skipping.", "WARNING")
                continue

            try:
                # --- 1. CLICK ROW (Opens Competitor Dialog) ---
                target_row.click()
                page.wait_for_timeout(1500)

                dialog = page.locator('.mat-mdc-dialog-container').last
                if not dialog.is_visible():
                    self.log("  [ERROR] Competitor dialog did not open.", "ERROR")
                    continue

                # --- 2. CLICK TRANSLATE ICON (Next to Name field) ---
                translate_clicked = False

                # Strategy A: data-test attribute for language icon (first = Name, not Short Name)
                try:
                    btn = dialog.locator('mat-icon[data-test="language-icon"]').first
                    if btn.is_visible():
                        btn.click()
                        translate_clicked = True
                except:
                    pass

                # Strategy B: mat-icon with text 'translate' or 'g_translate'
                if not translate_clicked:
                    try:
                        btn = dialog.locator('mat-icon').filter(has_text='translate').first
                        if btn.is_visible():
                            btn.click()
                            translate_clicked = True
                    except:
                        pass

                # Strategy C: Generic icon button in the first form field area
                if not translate_clicked:
                    try:
                        btn = dialog.locator('mat-icon').filter(has_text='g_translate').first
                        if btn.is_visible():
                            btn.click()
                            translate_clicked = True
                    except:
                        pass

                # Strategy D: Any clickable icon near the Name input
                if not translate_clicked:
                    try:
                        name_field = dialog.locator('mat-form-field').first
                        btn = name_field.locator('mat-icon').first
                        if btn.is_visible():
                            btn.click()
                            translate_clicked = True
                    except:
                        pass

                if not translate_clicked:
                    self.log("  [ERROR] Could not find translate icon in Competitor dialog.", "ERROR")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                    continue

                page.wait_for_timeout(1500)

                # --- 3. FILL TRANSLATIONS (Update Label dialog is now open) ---
                for config_key, csv_col in found_langs:
                    config = lang_config[config_key]
                    target_val = row.get(csv_col, '').strip()
                    if not target_val:
                        continue

                    if mode == 'verify':
                        self._verify_entry(page, config['drawer_label'], target_val, csv_col)
                    else:
                        self._update_entry(page, config, target_val, csv_col, skip_save=True)

                # --- 4. SAVE ---
                if mode != 'verify':
                    # 4a. Save Label Editor (topmost dialog)
                    self.log("  [Step] Saving Translation Changes...", "INFO")
                    
                    # Wait for UI to settle after all the filling
                    page.wait_for_timeout(1000)

                    # FIND THE CORRECT DIALOG: Look for the one that says "Update Label"
                    label_dialog = page.locator('.mat-mdc-dialog-container').filter(has_text=re.compile(r'Update Label', re.I)).last
                    
                    if not label_dialog.is_visible():
                        # Fallback to just the last dialog
                        label_dialog = page.locator('.mat-mdc-dialog-container').last
                    
                    # FORCE DIRTY STATE: Use the LAST visible input to trigger validation
                    try:
                        last_input = label_dialog.locator('input, textarea').last
                        if last_input.is_visible():
                            last_input.click()
                            page.keyboard.type(" ") 
                            page.keyboard.press("Backspace") 
                            page.keyboard.press("Tab")
                            page.wait_for_timeout(500)
                    except:
                        pass

                    # Target the Save button STRICTLY inside this dialog
                    label_save = label_dialog.locator('button:has-text("Save")').first

                    if label_save.is_visible():
                        if not label_save.is_enabled():
                             self.log("  [WARN] Save button is disabled. Trying to click dialog background to force blur...", "WARNING")
                             label_dialog.locator('.mat-mdc-dialog-surface').click(position={'x': 10, 'y': 10})
                             page.wait_for_timeout(500)

                        if label_save.is_enabled():
                            self.log("  [Step] Clicking Label Save...", "INFO")
                            label_save.click(force=True)
                            try:
                                # Wait for this specific dialog to disappear
                                label_dialog.wait_for(state='hidden', timeout=7000)
                            except:
                                self.log("  [WARN] Label dialog persistent. Trying Escape.", "WARNING")
                                page.keyboard.press("Escape")
                        else:
                            self.log("  [WARN] Save button persistent disabled. Closing.", "WARNING")
                            page.keyboard.press("Escape")
                    else:
                        self.log("  [ERROR] Label Save button not found within the dialog. Trying broad search...", "ERROR")
                        broad_save = page.locator('button:has-text("Save")').last
                        if broad_save.is_visible() and broad_save.is_enabled():
                            broad_save.click(force=True)
                        else:
                            page.keyboard.press("Escape")

                    page.wait_for_timeout(1500) # Crucial: Let the first save fully process in the backend

                    # 4b. Save Competitor dialog (the parent dialog)
                    comp_dialog = page.locator('.mat-mdc-dialog-container').last
                    
                    if comp_dialog.is_visible():
                        self.log("  [Step] Finalizing Competitor Record...", "INFO")
                        
                        # TRICK: Click the Name field in the parent dialog to "wake up" the competitor save button
                        try:
                            parent_input = comp_dialog.locator('input, textarea').first
                            if parent_input.is_visible():
                                parent_input.click()
                                page.wait_for_timeout(200)
                                page.keyboard.press("Tab")
                        except:
                            pass

                        comp_save = comp_dialog.locator('button:has-text("Save")').first
                        
                        if comp_save.is_visible():
                            if comp_save.is_enabled():
                                comp_save.click(force=True)
                                try:
                                    comp_dialog.wait_for(state='hidden', timeout=6000)
                                    self.log(f"  [SUCCESS] Match {match_num + 1} fully committed.", "SUCCESS")
                                except:
                                    self.log("  [WARN] Competitor dialog persistent. Closing manually.", "WARNING")
                                    page.keyboard.press("Escape")
                            else:
                                self.log("  [INFO] Competitor Save button is DISABLED. The app might have auto-saved or requires no further action. Closing.", "INFO")
                                page.keyboard.press("Escape")
                        else:
                            self.log("  [INFO] Competitor Save button not found. Closing dialog.", "INFO")
                            page.keyboard.press("Escape")

                    page.wait_for_timeout(1000)

                processed += 1

            except Exception as e:
                self.log(f"  [ERROR] Match {match_num + 1} failed: {e}", "ERROR")
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

        self.log(f"Completed '{search_val}': {processed}/{exact_match_count} matches processed", "INFO")
