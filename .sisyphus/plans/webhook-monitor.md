# Webhook Monitoring for OpenHands API Key Refresh

## TL;DR

> **Quick Summary**: Add continuous webhook monitoring during OpenHands registration pause to automatically refresh stale API keys when requested by external system.
> 
> **Deliverables**:
> - Webhook configuration constants (URLs, secret)
> - 4 helper functions (GET status, POST key, scrape key, click refresh)
> - Main `webhook_monitor_loop(driver)` function with threading for ENTER detection
> - Replace `input()` at line 875 with webhook monitor loop
> 
> **Estimated Effort**: Short (2-3 hours)
> **Parallel Execution**: NO - sequential (functions build on each other)
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6

---

## Context

### Original Request
Add continuous webhook monitoring during OpenHands registration so that:
1. Script checks webhook every 2 seconds for `need_refresh = true`
2. When stale key found, match with displayed key on page
3. If match AND "Refresh API Key" button visible → click it
4. POST new key to webhook after refresh
5. User can press ENTER anytime to skip and continue to next email

### Interview Summary
**Key Decisions**:
- Use `requests` library (existing pattern in email_api_helper.py)
- Use threading for non-blocking ENTER key detection
- 2-second polling interval for webhook
- No test infrastructure - manual verification only

**User-Provided API Specs**:
- GET `https://api.trollllm.xyz/webhook/openhands/status` → `{need_refresh, keys[]}`
- POST `https://api.trollllm.xyz/webhook/openhands/keys` → `{apiKey: "..."}`
- Header: `X-Webhook-Secret: ahihi123`

**User-Provided HTML Selectors**:
- API key display: `<span class="text-white font-mono">sk-xxx</span>`
- Refresh button: `<button class="bg-primary ...">Refresh API Key</button>`

---

## Work Objectives

### Core Objective
Replace manual `input()` pause at line 875 with an intelligent webhook monitoring loop that automatically refreshes stale API keys upon external request.

### Concrete Deliverables
1. Webhook configuration constants in SETTINGS section
2. `check_webhook_status()` function - returns dict with `need_refresh` and `keys`
3. `post_new_api_key(api_key)` function - POSTs new key, returns success boolean
4. `get_displayed_api_key(driver)` function - scrapes key from OpenHands page
5. `click_refresh_button(driver)` function - clicks refresh, returns success boolean
6. `webhook_monitor_loop(driver)` function - main loop with threading for ENTER
7. Updated line 875 calling `webhook_monitor_loop(driver)` instead of `input()`

### Definition of Done
- [ ] Script runs without import errors
- [ ] Webhook GET returns status correctly (manual curl test)
- [ ] Webhook POST sends new key correctly (manual curl test)
- [ ] ENTER key stops the loop immediately
- [ ] Console output shows clear status messages

### Must Have
- Non-blocking ENTER key detection (threading)
- Error handling for network failures (continue loop, don't crash)
- Clear console output showing what's happening each cycle
- Match API key EXACTLY before clicking refresh
- Wait for key to actually change before POSTing

### Must NOT Have (Guardrails)
- ❌ NO retry logic for failed webhook calls (just skip that cycle)
- ❌ NO modifications to any other functions in the script
- ❌ NO changes to imports beyond adding `requests` and `threading`
- ❌ NO hardcoded secrets in code (use constants section for maintainability)
- ❌ NO infinite loops without escape - ENTER MUST break immediately
- ❌ NO clicking refresh if keys don't match (could refresh wrong account)

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO
- **User wants tests**: Manual-only
- **Framework**: None

### Manual Verification Procedures

Each TODO includes console output verification and manual curl tests.

---

## Execution Strategy

### Sequential Execution (No Parallelization)

```
Task 1: Add imports + constants
    ↓
Task 2: check_webhook_status()
    ↓
Task 3: post_new_api_key()
    ↓
Task 4: get_displayed_api_key()
    ↓
Task 5: click_refresh_button()
    ↓
Task 6: webhook_monitor_loop() + replace input()
```

**Why Sequential**: Each function builds on prior work. Loop function needs all helpers complete.

### Dependency Matrix

| Task | Depends On | Blocks |
|------|------------|--------|
| 1 | None | 2, 3, 4, 5, 6 |
| 2 | 1 | 6 |
| 3 | 1 | 6 |
| 4 | 1 | 6 |
| 5 | 1 | 6 |
| 6 | 2, 3, 4, 5 | None (final) |

---

## TODOs

- [ ] 1. Add imports and webhook configuration constants

  **What to do**:
  - Add `import requests` after line 44 (with other imports)
  - Add `import threading` after requests
  - Add webhook constants after line 89 (after ERROR_LOG_FILE):
    ```python
    # Webhook Configuration
    WEBHOOK_STATUS_URL = "https://api.trollllm.xyz/webhook/openhands/status"
    WEBHOOK_ADD_KEY_URL = "https://api.trollllm.xyz/webhook/openhands/keys"
    WEBHOOK_SECRET = "ahihi123"
    WEBHOOK_CHECK_INTERVAL = 2  # seconds
    ```

  **Must NOT do**:
  - Do NOT modify any existing constants
  - Do NOT add imports inside functions

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple text insertion at known locations
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**:
    - `git-master`: Not needed - no git operations

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Tasks 2, 3, 4, 5, 6
  - **Blocked By**: None (start immediately)

  **References**:
  - `gitlab_register_and_openhands-hook1.py:33-44` - Existing imports section
  - `gitlab_register_and_openhands-hook1.py:86-89` - Existing constants (FILES section, add after)
  - `email_api_helper.py:6` - Pattern for requests import

  **Acceptance Criteria**:
  - [ ] `import requests` added in imports section
  - [ ] `import threading` added in imports section
  - [ ] 4 webhook constants defined after ERROR_LOG_FILE
  - [ ] Run: `python -c "import gitlab_register_and_openhands-hook1"` → no ImportError
  - [ ] Verify manually: Constants visible in file around line 90-95

  **Commit**: NO (group with Task 6)

---

- [ ] 2. Add `check_webhook_status()` function

  **What to do**:
  - Add function after line 109 (after GLOBAL VARIABLES section, before `random_delay`)
  - Function signature: `def check_webhook_status() -> dict | None`
  - Make GET request to WEBHOOK_STATUS_URL
  - Include header `X-Webhook-Secret: WEBHOOK_SECRET`
  - Set timeout=10 seconds
  - Return parsed JSON on success, None on any error
  - Print status messages: "🔍 Checking webhook..." and result

  **Implementation pattern** (from email_api_helper.py):
  ```python
  def check_webhook_status():
      """Check webhook for API keys that need refresh"""
      try:
          headers = {"X-Webhook-Secret": WEBHOOK_SECRET}
          response = requests.get(WEBHOOK_STATUS_URL, headers=headers, timeout=10)
          
          if response.status_code != 200:
              print(f"  ⚠ Webhook error: HTTP {response.status_code}")
              return None
          
          data = response.json()
          if data.get("need_refresh"):
              print(f"  🔄 Webhook: {len(data.get('keys', []))} key(s) need refresh")
          else:
              print(f"  ✓ Webhook: No refresh needed")
          return data
          
      except requests.exceptions.Timeout:
          print("  ⚠ Webhook timeout")
          return None
      except requests.exceptions.RequestException as e:
          print(f"  ⚠ Webhook error: {str(e)}")
          return None
      except Exception as e:
          print(f"  ⚠ Webhook error: {str(e)}")
          return None
  ```

  **Must NOT do**:
  - Do NOT raise exceptions (return None instead)
  - Do NOT add retry logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single function implementation following existing pattern
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Backend code, not UI

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 6
  - **Blocked By**: Task 1

  **References**:
  - `email_api_helper.py:26-57` - Pattern for requests error handling
  - `gitlab_register_and_openhands-hook1.py:104-108` - GLOBAL VARIABLES section (insert after)
  - User request: GET response format `{need_refresh: bool, keys: [{apiKey, ...}]}`

  **Acceptance Criteria**:
  - [ ] Function defined after GLOBAL VARIABLES, before random_delay
  - [ ] Uses WEBHOOK_STATUS_URL and WEBHOOK_SECRET constants
  - [ ] Returns dict on success, None on failure
  - [ ] Handles Timeout, RequestException, generic Exception
  - [ ] Manual test: Add temp code `print(check_webhook_status())` → run → see response
  - [ ] Console shows "🔍" or "🔄" or "✓" status

  **Commit**: NO (group with Task 6)

---

- [ ] 3. Add `post_new_api_key()` function

  **What to do**:
  - Add function immediately after `check_webhook_status()`
  - Function signature: `def post_new_api_key(api_key: str) -> bool`
  - Make POST request to WEBHOOK_ADD_KEY_URL
  - Include headers: `X-Webhook-Secret` and `Content-Type: application/json`
  - Body: `{"apiKey": api_key}`
  - Return True on 201 status, False otherwise
  - Print success/failure message

  **Implementation**:
  ```python
  def post_new_api_key(api_key: str) -> bool:
      """POST new API key to webhook"""
      try:
          headers = {
              "X-Webhook-Secret": WEBHOOK_SECRET,
              "Content-Type": "application/json"
          }
          payload = {"apiKey": api_key}
          
          print(f"  📤 Posting new key to webhook: {api_key[:10]}...")
          response = requests.post(WEBHOOK_ADD_KEY_URL, json=payload, headers=headers, timeout=10)
          
          if response.status_code == 201:
              print(f"  ✓ Webhook accepted new key")
              return True
          else:
              print(f"  ✗ Webhook rejected: HTTP {response.status_code}")
              return False
              
      except Exception as e:
          print(f"  ✗ Failed to post key: {str(e)}")
          return False
  ```

  **Must NOT do**:
  - Do NOT print full API key (only first 10 chars for security)
  - Do NOT retry on failure

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single function, similar pattern to Task 2
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 6
  - **Blocked By**: Task 1

  **References**:
  - `email_api_helper.py:34` - Pattern for requests.post with json param
  - Task 2 output - Follows same error handling pattern
  - User request: POST response expected 201 status

  **Acceptance Criteria**:
  - [ ] Function defined immediately after check_webhook_status()
  - [ ] Uses json= parameter (not data=) for automatic JSON encoding
  - [ ] Returns bool (True/False), never raises
  - [ ] Only prints first 10 chars of API key
  - [ ] Manual test: Call with fake key → see 4xx response (expected)

  **Commit**: NO (group with Task 6)

---

- [ ] 4. Add `get_displayed_api_key()` function

  **What to do**:
  - Add function after `post_new_api_key()`
  - Function signature: `def get_displayed_api_key(driver) -> str | None`
  - Find element: `span.text-white.font-mono` containing "sk-"
  - Return the text content, or None if not found
  - Use try/except to handle element not found gracefully

  **Implementation**:
  ```python
  def get_displayed_api_key(driver) -> str | None:
      """Get the API key currently displayed on OpenHands page"""
      try:
          # Find span with API key - look for text-white font-mono class containing sk-
          spans = driver.find_elements(By.CSS_SELECTOR, "span.text-white.font-mono")
          for span in spans:
              text = span.text.strip()
              if text.startswith("sk-"):
                  return text
          
          # Fallback: Try XPath for any element containing sk-
          elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'sk-')]")
          for el in elements:
              text = el.text.strip()
              if text.startswith("sk-") and len(text) > 10:
                  return text
                  
          return None
      except Exception:
          return None
  ```

  **Must NOT do**:
  - Do NOT use WebDriverWait (page might not have the element yet)
  - Do NOT print errors (silent failure, loop will retry)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple Selenium element lookup
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**:
    - `playwright`: Using existing Selenium driver, not Playwright

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 6
  - **Blocked By**: Task 1

  **References**:
  - `gitlab_register_and_openhands-hook1.py:34` - By import already exists
  - `gitlab_register_and_openhands-hook1.py:887-910` - Existing get_api_key() function pattern
  - User request: HTML `<span class="text-white font-mono">sk-xxx</span>`

  **Acceptance Criteria**:
  - [ ] Function defined after post_new_api_key()
  - [ ] Uses CSS selector as primary, XPath as fallback
  - [ ] Returns string starting with "sk-" or None
  - [ ] Never raises exceptions (returns None on error)
  - [ ] No console output (silent function)

  **Commit**: NO (group with Task 6)

---

- [ ] 5. Add `click_refresh_button()` function

  **What to do**:
  - Add function after `get_displayed_api_key()`
  - Function signature: `def click_refresh_button(driver) -> bool`
  - Find button with text "Refresh API Key" 
  - Click it using JS executor (more reliable)
  - Return True if clicked, False if button not found

  **Implementation**:
  ```python
  def click_refresh_button(driver) -> bool:
      """Click the Refresh API Key button"""
      try:
          # Try multiple selectors
          selectors = [
              (By.XPATH, "//button[contains(text(), 'Refresh API Key')]"),
              (By.XPATH, "//button[contains(., 'Refresh API Key')]"),
              (By.CSS_SELECTOR, "button.bg-primary"),
          ]
          
          for by, selector in selectors:
              try:
                  buttons = driver.find_elements(by, selector)
                  for btn in buttons:
                      if "Refresh" in btn.text or "refresh" in btn.get_attribute("innerHTML").lower():
                          driver.execute_script("arguments[0].click();", btn)
                          print(f"  🔄 Clicked 'Refresh API Key' button")
                          return True
              except:
                  continue
          
          return False
      except Exception:
          return False
  ```

  **Must NOT do**:
  - Do NOT use WebDriverWait (button might not exist)
  - Do NOT click if button text doesn't contain "Refresh"

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple Selenium button click
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 6
  - **Blocked By**: Task 1

  **References**:
  - `gitlab_register_and_openhands-hook1.py:831-853` - Pattern for button finding with multiple selectors
  - `gitlab_register_and_openhands-hook1.py:852` - JS click pattern: `driver.execute_script("arguments[0].click();", btn)`
  - User request: Button `<button class="bg-primary ...">Refresh API Key</button>`

  **Acceptance Criteria**:
  - [ ] Function defined after get_displayed_api_key()
  - [ ] Uses JavaScript click (more reliable than .click())
  - [ ] Returns True only if button found AND clicked
  - [ ] Prints "🔄 Clicked..." only on success
  - [ ] Returns False silently if button not found

  **Commit**: NO (group with Task 6)

---

- [ ] 6. Add `webhook_monitor_loop()` and replace input() call

  **What to do**:
  - Add main loop function after `click_refresh_button()`
  - Function signature: `def webhook_monitor_loop(driver) -> None`
  - Use threading to detect ENTER key press (non-blocking)
  - Main loop every 2 seconds:
    1. Check if ENTER was pressed → break
    2. Call check_webhook_status()
    3. If need_refresh AND has keys:
       - Get displayed key from page
       - For each stale key in webhook response:
         - If displayed key matches stale key:
           - Click refresh button
           - Wait for key to change (poll every 0.5s, max 10s)
           - POST new key to webhook
    4. Sleep WEBHOOK_CHECK_INTERVAL seconds
  - Replace `input()` at line 875 with call to this function

  **Implementation**:
  ```python
  def webhook_monitor_loop(driver) -> None:
      """
      Monitor webhook for API key refresh requests.
      Runs until user presses ENTER.
      """
      import sys
      import select
      
      print("\n" + "=" * 60)
      print("🔄 WEBHOOK MONITORING ACTIVE")
      print("=" * 60)
      print("Monitoring for API key refresh requests...")
      print("Press ENTER at any time to stop and continue to next email")
      print("=" * 60)
      
      # Threading setup for non-blocking input
      stop_flag = threading.Event()
      
      def wait_for_enter():
          try:
              input()
              stop_flag.set()
          except:
              pass
      
      # Start input listener thread
      input_thread = threading.Thread(target=wait_for_enter, daemon=True)
      input_thread.start()
      
      cycle = 0
      while not stop_flag.is_set():
          cycle += 1
          print(f"\n[Cycle {cycle}] Checking webhook...")
          
          # Check webhook
          status = check_webhook_status()
          
          if status and status.get("need_refresh") and status.get("keys"):
              stale_keys = [k.get("apiKey") for k in status["keys"] if k.get("apiKey")]
              
              # Get current displayed key
              displayed_key = get_displayed_api_key(driver)
              
              if displayed_key:
                  print(f"  📋 Page shows key: {displayed_key[:15]}...")
                  
                  # Check if displayed key is in stale list
                  if displayed_key in stale_keys:
                      print(f"  ⚠ This key needs refresh!")
                      
                      # Try to click refresh button
                      if click_refresh_button(driver):
                          # Wait for key to change
                          print(f"  ⏳ Waiting for key to change...")
                          old_key = displayed_key
                          new_key = None
                          
                          for _ in range(20):  # 10 seconds max
                              time.sleep(0.5)
                              new_key = get_displayed_api_key(driver)
                              if new_key and new_key != old_key:
                                  print(f"  ✓ Key changed to: {new_key[:15]}...")
                                  break
                          
                          if new_key and new_key != old_key:
                              # POST new key to webhook
                              post_new_api_key(new_key)
                          else:
                              print(f"  ⚠ Key didn't change after refresh")
                      else:
                          print(f"  ⚠ Refresh button not found (user may not be on API keys page)")
                  else:
                      print(f"  ✓ Displayed key not in stale list")
              else:
                  print(f"  ℹ No API key visible on page (user may not be on API keys page yet)")
          
          # Wait before next cycle (but check stop_flag frequently)
          for _ in range(WEBHOOK_CHECK_INTERVAL * 2):  # Check every 0.5s
              if stop_flag.is_set():
                  break
              time.sleep(0.5)
      
      print("\n✅ User pressed ENTER - stopping webhook monitor")
      print("Continuing to next email...\n")
  ```

  - **Replace line 875**: Change `input()` to `webhook_monitor_loop(driver)`
  - **Update print messages** at lines 865-874 to reflect new behavior

  **Must NOT do**:
  - Do NOT use keyboard interrupt (breaks on Windows)
  - Do NOT block the main thread waiting for input
  - Do NOT crash on any exception (catch and continue)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Complex function with threading, state management, and UI interaction
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**:
    - `playwright`: Using Selenium, not Playwright

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (final task)
  - **Blocks**: None
  - **Blocked By**: Tasks 1, 2, 3, 4, 5

  **References**:
  - `gitlab_register_and_openhands-hook1.py:862-878` - Current input() block to replace
  - `gitlab_register_and_openhands-hook1.py:92-102` - TURBO_MODE timing pattern
  - Tasks 2-5 output - All helper functions this loop calls
  - Python threading docs - `threading.Event()` for stop flag pattern

  **Acceptance Criteria**:
  - [ ] Function defined after click_refresh_button()
  - [ ] Uses threading.Event() for stop flag (not global variable)
  - [ ] Input thread is daemon=True (won't block program exit)
  - [ ] Loop checks stop_flag every 0.5s for responsive ENTER detection
  - [ ] All exceptions caught (never crashes)
  - [ ] Line 875: `input()` replaced with `webhook_monitor_loop(driver)`
  - [ ] Print messages at 865-874 updated to mention webhook monitoring
  
  **Manual Verification**:
  ```bash
  # 1. Run script normally
  python gitlab_register_and_openhands-hook1.py
  
  # 2. When it reaches webhook monitoring:
  #    - See "WEBHOOK MONITORING ACTIVE" message
  #    - See cycle messages every 2 seconds
  #    - Press ENTER → see "User pressed ENTER" → continues
  
  # 3. Test webhook integration (if webhook has stale key):
  #    - Navigate to OpenHands API keys page manually
  #    - If displayed key matches stale key in webhook:
  #      - See "This key needs refresh!"
  #      - See button click
  #      - See new key posted
  ```

  **Commit**: YES
  - Message: `feat(gitlab): add webhook monitoring for API key refresh`
  - Files: `gitlab_register_and_openhands-hook1.py`
  - Pre-commit: `python -c "import gitlab_register_and_openhands-hook1"` (syntax check)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 6 | `feat(gitlab): add webhook monitoring for API key refresh` | gitlab_register_and_openhands-hook1.py | `python -c "import gitlab_register_and_openhands-hook1"` |

**Single commit**: All 6 tasks are one logical feature, commit together after Task 6.

---

## Success Criteria

### Verification Commands
```bash
# Syntax check (no import errors)
python -c "import gitlab_register_and_openhands-hook1"

# Manual webhook test
curl -H "X-Webhook-Secret: ahihi123" https://api.trollllm.xyz/webhook/openhands/status
```

### Final Checklist
- [ ] `requests` and `threading` imported
- [ ] 4 webhook constants defined
- [ ] 5 new functions added (check_webhook, post_key, get_displayed, click_refresh, monitor_loop)
- [ ] `input()` at line 875 replaced with `webhook_monitor_loop(driver)`
- [ ] ENTER key stops the loop immediately
- [ ] Script runs without errors when reaching webhook monitor point
- [ ] Console output shows clear cycle status messages
