# GitLab Sign-IN Conversion

## TL;DR

> **Quick Summary**: Convert `gitlab_login.py` from SIGNUP (registration) flow to SIGNIN (login) flow for existing GitLab accounts, keeping all downstream OpenHands integration intact.
> 
> **Deliverables**:
> - New `signin_gitlab()` function replacing `register_gitlab()`
> - Adapted verification handling for post-signin 2FA
> - Updated `main()` function calling signin
> - Updated docstrings/comments reflecting signin flow
> 
> **Estimated Effort**: Medium (2-3 hours)
> **Parallel Execution**: NO - sequential (each task modifies same file)
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5

---

## Context

### Original Request
User wants to modify `gitlab_login.py` to perform SIGNIN (login to existing GitLab accounts) instead of SIGNUP (registration of new accounts).

### Interview Summary
**Key Discussions**:
- Replace `register_gitlab()` entirely with `signin_gitlab()` (not add alongside)
- SMS/2FA verification delivered via EMAIL - existing `wait_for_gitlab_verification_code()` works as-is
- No 2FA required → proceed directly to OpenHands
- 2FA timeout → warn, wait 60s for manual input, continue anyway
- Keep same TURBO_MODE timing behavior

**Research Findings**:
- GitLab signin form elements: `#user_login` (email), `#user_password` (password), `button[type='submit']`
- Verification code input: `#verification_code`
- Current `register_gitlab()` spans lines 257-560 (~300 lines)
- Current `verify_gitlab_email()` spans lines 568-751 (~180 lines)
- Existing helper `wait_for_gitlab_verification_code()` in `email_api_helper.py` extracts 6-digit codes

### Gap Analysis
**Identified Gaps** (addressed in plan):
- URL constant `GITLAB_SIGNUP_URL` should be replaced/removed (line 77)
- Helper functions `generate_username_from_email()` and `generate_name_from_email()` become unused - keep for now, don't delete
- `verify_gitlab_email()` has signup-specific logic that needs simplification for signin flow
- Cloudflare handling logic in `register_gitlab()` should be preserved in new `signin_gitlab()`

---

## Work Objectives

### Core Objective
Transform `gitlab_login.py` from a GitLab account registration script to a GitLab account login script, maintaining the same downstream OpenHands OAuth and API key retrieval flow.

### Concrete Deliverables
- `signin_gitlab(driver, email, password)` function at ~line 257
- Simplified verification handling for 2FA after signin
- Updated `main()` calling signin flow
- Updated script docstring (lines 1-18)
- Removed/updated URL constant `GITLAB_SIGNUP_URL`

### Definition of Done
- [ ] Script successfully logs into an existing GitLab account
- [ ] 2FA verification (if prompted) handled via email API
- [ ] OpenHands OAuth login works after GitLab signin
- [ ] API key retrieval works as before
- [ ] No Python syntax errors
- [ ] Script runs without import errors

### Must Have
- Cloudflare bypass warmup logic preserved
- Human-like typing behavior (using existing `human_like_type()`)
- Same input file format (`email|password|refresh_token|client_id`)
- Same output file format (`username|api_key`)
- Error logging to `errormail.txt`

### Must NOT Have (Guardrails)
- DO NOT modify `login_openhands_gitlab()` function (lines 754-1400)
- DO NOT modify `get_api_key()` function (lines 1403-1498)
- DO NOT modify `save_api_key()` function (lines 1501-1528)
- DO NOT modify `log_error()` function (lines 1531-1538)
- DO NOT modify `setup_ixbrowser_driver()` function (lines 152-194)
- DO NOT modify `close_ixbrowser_profile()` function (lines 197-220)
- DO NOT modify `read_emails()` function (lines 223-254)
- DO NOT modify `email_api_helper.py` at all
- DO NOT delete `generate_username_from_email()` or `generate_name_from_email()` (may be used elsewhere)
- DO NOT add new dependencies/imports
- DO NOT change timing constants behavior

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (no pytest/test files in project)
- **User wants tests**: Manual verification
- **Framework**: None

### Manual Verification Procedures

Each TODO includes commands the agent can run to verify:

1. **Syntax check**: `python -m py_compile gitlab_login.py`
2. **Import check**: `python -c "import gitlab_login"`
3. **Function existence**: `python -c "from gitlab_login import signin_gitlab; print('OK')"`
4. **Dry-run**: Run script with a test account (requires actual credentials)

---

## Execution Strategy

### Sequential Execution (No Parallelization)

All tasks modify the same file (`gitlab_login.py`) and depend on previous changes:

```
Task 1: Update docstring and constants
    ↓
Task 2: Create signin_gitlab() function
    ↓
Task 3: Simplify verify_gitlab_email() for signin
    ↓
Task 4: Update main() function
    ↓
Task 5: Final verification and cleanup
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3, 4 | None |
| 2 | 1 | 3, 4 | None |
| 3 | 2 | 4 | None |
| 4 | 3 | 5 | None |
| 5 | 4 | None | None (final) |

---

## TODOs

- [ ] 1. Update docstring and URL constants

  **What to do**:
  - Update the script docstring (lines 1-18) to reflect SIGNIN workflow instead of SIGNUP
  - Replace `GITLAB_SIGNUP_URL` constant (line 77) with `GITLAB_SIGNIN_URL = "https://gitlab.com/users/sign_in"`
  - Update any comments that reference "đăng ký" (registration) to "đăng nhập" (login)

  **Must NOT do**:
  - Don't change any other constants (OPENHANDS URLs, file paths, timing settings)
  - Don't modify import statements

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple text changes, no complex logic
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**:
    - `git-master`: Not needed for editing

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (first task)
  - **Blocks**: Tasks 2, 3, 4
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `gitlab_login.py:1-18` - Current docstring describing SIGNUP workflow
  - `gitlab_login.py:77` - `GITLAB_SIGNUP_URL` constant to replace

  **WHY Each Reference Matters**:
  - Lines 1-18: Vietnamese docstring explains the workflow - needs updating to reflect signin instead of signup
  - Line 77: URL constant used by register_gitlab() - change name and value for signin

  **Acceptance Criteria**:

  ```bash
  # Agent runs syntax check:
  python -m py_compile E:\autoo\automation\gitlab_login.py
  # Assert: Exit code 0 (no syntax errors)
  
  # Agent verifies constant exists:
  python -c "from gitlab_login import GITLAB_SIGNIN_URL; print(GITLAB_SIGNIN_URL)"
  # Assert: Output is "https://gitlab.com/users/sign_in"
  ```

  **Evidence to Capture:**
  - [ ] Python syntax check passes
  - [ ] GITLAB_SIGNIN_URL constant accessible and correct

  **Commit**: NO (groups with Task 5)

---

- [ ] 2. Create signin_gitlab() function

  **What to do**:
  - Replace `register_gitlab()` function (lines 257-560) with new `signin_gitlab(driver, email, password)` function
  - Preserve Cloudflare warmup logic from register_gitlab() (lines 265-303)
  - After warmup, STAY on /sign_in page (don't open new tab)
  - Wait for signin form to load: `WebDriverWait` for `#user_login` field
  - Fill email into `#user_login` field using `human_like_type()`
  - Fill password into `#user_password` field using `human_like_type()`
  - Click submit button using selector: `button[type='submit']` or `[data-testid='sign-in-button']`
  - Wait for redirect (check for verification page or successful login)
  - Return True on success, False on failure

  **Must NOT do**:
  - Don't open a new tab after warmup (signin is on same page)
  - Don't fill first_name, last_name, username fields (signin doesn't have these)
  - Don't handle CAPTCHA (signin typically doesn't show CAPTCHA like signup)
  - Don't use `GITLAB_SIGNUP_URL` - use `GITLAB_SIGNIN_URL`

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Selenium automation with form filling, web element interactions
  - **Skills**: None required (standard Selenium patterns)
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not using Playwright, using Selenium
    - `dev-browser`: This is Selenium-based, not MCP browser

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Task 1)
  - **Blocks**: Tasks 3, 4
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `gitlab_login.py:257-303` - Cloudflare warmup logic to PRESERVE
  - `gitlab_login.py:113-118` - `human_like_type()` function for realistic typing
  - `gitlab_login.py:105-110` - `random_delay()` function for timing

  **API/Type References**:
  - `gitlab_login.py:29-36` - Selenium imports (By, WebDriverWait, EC, TimeoutException)

  **External References**:
  - GitLab signin page: `https://gitlab.com/users/sign_in`
  - Signin form elements: `#user_login`, `#user_password`, `button[type='submit']`

  **WHY Each Reference Matters**:
  - Lines 257-303: Cloudflare bypass logic is CRITICAL - must be preserved exactly
  - Lines 113-118: Human-like typing prevents bot detection
  - Lines 105-110: Random delays add realism

  **Acceptance Criteria**:

  ```bash
  # Agent runs syntax check:
  python -m py_compile E:\autoo\automation\gitlab_login.py
  # Assert: Exit code 0
  
  # Agent verifies function exists with correct signature:
  python -c "from gitlab_login import signin_gitlab; import inspect; sig = inspect.signature(signin_gitlab); print(list(sig.parameters.keys()))"
  # Assert: Output contains ['driver', 'email', 'password']
  
  # Agent verifies register_gitlab is removed:
  python -c "from gitlab_login import register_gitlab" 2>&1 || echo "REMOVED"
  # Assert: Output contains "REMOVED" or ImportError
  ```

  **Evidence to Capture:**
  - [ ] Python syntax check passes
  - [ ] `signin_gitlab` function exists with correct parameters
  - [ ] `register_gitlab` function no longer exists

  **Commit**: NO (groups with Task 5)

---

- [ ] 3. Simplify verify_gitlab_email() for signin 2FA

  **What to do**:
  - Modify `verify_gitlab_email()` function (lines 568-751) to handle signin 2FA verification
  - Keep the core logic: get code from email API → fill `#verification_code` → submit
  - Simplify: Remove signup-specific redirect handling (lines 604-644)
  - Update function docstring to reflect signin 2FA (not email verification)
  - Handle case where no verification is required (return True immediately)
  - Keep timeout behavior: if code not found in 120s, wait 60s for manual input, return True

  **Must NOT do**:
  - Don't change the function signature (driver, email, refresh_token, client_id)
  - Don't modify the email API helper call (`wait_for_gitlab_verification_code`)
  - Don't remove the manual fallback (60s wait for user to enter code)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Selenium automation with form filling
  - **Skills**: None required
  - **Skills Evaluated but Omitted**:
    - Same as Task 2

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Task 2)
  - **Blocks**: Task 4
  - **Blocked By**: Task 2

  **References**:

  **Pattern References**:
  - `gitlab_login.py:568-751` - Current verify_gitlab_email() function
  - `gitlab_login.py:678-700` - Core verification logic to KEEP: fill code, click verify
  - `email_api_helper.py:238-273` - `wait_for_gitlab_verification_code()` API helper

  **WHY Each Reference Matters**:
  - Lines 568-751: Full function context
  - Lines 678-700: Core logic that works for both signup and signin verification
  - email_api_helper.py: Don't modify this - just call it

  **Acceptance Criteria**:

  ```bash
  # Agent runs syntax check:
  python -m py_compile E:\autoo\automation\gitlab_login.py
  # Assert: Exit code 0
  
  # Agent verifies function exists:
  python -c "from gitlab_login import verify_gitlab_email; import inspect; sig = inspect.signature(verify_gitlab_email); print(list(sig.parameters.keys()))"
  # Assert: Output contains ['driver', 'email', 'refresh_token', 'client_id']
  ```

  **Evidence to Capture:**
  - [ ] Python syntax check passes
  - [ ] `verify_gitlab_email` function signature unchanged

  **Commit**: NO (groups with Task 5)

---

- [ ] 4. Update main() function

  **What to do**:
  - Update `main()` function (lines 1541-1690) to call `signin_gitlab()` instead of `register_gitlab()`
  - Update step comments/prints from "Register GitLab" to "Sign-in GitLab"
  - Update the banner print (line 1547) from "GITLAB SIGNUP" to "GITLAB SIGNIN"
  - Keep the rest of the flow: signin → verify (if needed) → open new tab → OpenHands OAuth → get API key
  - Update error messages to say "signin" instead of "signup"

  **Must NOT do**:
  - Don't change the OpenHands login flow (lines 1616-1621)
  - Don't change the API key retrieval (lines 1623-1631)
  - Don't change the cleanup/finally logic (lines 1643-1662)
  - Don't change the email reading logic

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple function call replacement and string updates
  - **Skills**: None required
  - **Skills Evaluated but Omitted**:
    - None needed for this task

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Task 3)
  - **Blocks**: Task 5
  - **Blocked By**: Task 3

  **References**:

  **Pattern References**:
  - `gitlab_login.py:1541-1690` - Full main() function
  - `gitlab_login.py:1583` - Call to `register_gitlab()` - change to `signin_gitlab()`
  - `gitlab_login.py:1589-1593` - Call to `verify_gitlab_email()` - keep as-is
  - `gitlab_login.py:1547` - Banner print to update

  **WHY Each Reference Matters**:
  - Line 1583: Main call site to change
  - Lines 1589-1593: verify_gitlab_email call - keep unchanged
  - Line 1547: User-facing output needs updating

  **Acceptance Criteria**:

  ```bash
  # Agent runs syntax check:
  python -m py_compile E:\autoo\automation\gitlab_login.py
  # Assert: Exit code 0
  
  # Agent verifies main references signin_gitlab:
  python -c "import ast; tree = ast.parse(open('E:/autoo/automation/gitlab_login.py').read()); funcs = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and hasattr(node.func, 'id')]; print('signin_gitlab' in funcs)"
  # Assert: Output is "True"
  
  # Agent verifies register_gitlab not called:
  python -c "import ast; tree = ast.parse(open('E:/autoo/automation/gitlab_login.py').read()); funcs = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and hasattr(node.func, 'id')]; print('register_gitlab' in funcs)"
  # Assert: Output is "False"
  ```

  **Evidence to Capture:**
  - [ ] Python syntax check passes
  - [ ] `signin_gitlab` is called in main()
  - [ ] `register_gitlab` is NOT called anywhere

  **Commit**: NO (groups with Task 5)

---

- [ ] 5. Final verification and commit

  **What to do**:
  - Run complete syntax and import verification
  - Verify all functions exist with correct signatures
  - Verify no references to `register_gitlab` remain (except maybe commented code)
  - Create a single atomic commit with all changes
  - Commit message: `refactor(gitlab): convert signup flow to signin flow`

  **Must NOT do**:
  - Don't push to remote (user didn't request)
  - Don't modify any other files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Verification and git commit
  - **Skills**: [`git-master`]
    - `git-master`: For atomic commit creation
  - **Skills Evaluated but Omitted**:
    - None

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (final task)
  - **Blocks**: None
  - **Blocked By**: Task 4

  **References**:

  **Pattern References**:
  - `gitlab_login.py` - Entire modified file
  - `AGENTS.md` - Git workflow conventions

  **WHY Each Reference Matters**:
  - Full file verification ensures no broken references
  - AGENTS.md has commit conventions

  **Acceptance Criteria**:

  ```bash
  # Agent runs full import test:
  python -c "import gitlab_login; print('Imports OK')"
  # Assert: Output is "Imports OK"
  
  # Agent verifies all key functions exist:
  python -c "from gitlab_login import signin_gitlab, verify_gitlab_email, login_openhands_gitlab, get_api_key, main; print('All functions exist')"
  # Assert: Output is "All functions exist"
  
  # Agent verifies no register_gitlab function:
  python -c "from gitlab_login import register_gitlab" 2>&1 || echo "Correctly removed"
  # Assert: Contains "Correctly removed" or ImportError
  
  # Agent creates commit:
  git add gitlab_login.py && git commit -m "refactor(gitlab): convert signup flow to signin flow"
  # Assert: Commit succeeds
  
  # Agent verifies commit:
  git log -1 --oneline
  # Assert: Shows the new commit
  ```

  **Evidence to Capture:**
  - [ ] Full import succeeds
  - [ ] All key functions exist
  - [ ] `register_gitlab` correctly removed
  - [ ] Git commit created

  **Commit**: YES
  - Message: `refactor(gitlab): convert signup flow to signin flow`
  - Files: `gitlab_login.py`
  - Pre-commit: `python -c "import gitlab_login"`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 5 | `refactor(gitlab): convert signup flow to signin flow` | gitlab_login.py | `python -c "import gitlab_login"` |

---

## Success Criteria

### Verification Commands
```bash
# Syntax check
python -m py_compile E:\autoo\automation\gitlab_login.py
# Expected: Exit code 0

# Import check
python -c "import gitlab_login"
# Expected: No errors

# Function check
python -c "from gitlab_login import signin_gitlab, verify_gitlab_email, login_openhands_gitlab, get_api_key"
# Expected: No errors

# Constant check
python -c "from gitlab_login import GITLAB_SIGNIN_URL; print(GITLAB_SIGNIN_URL)"
# Expected: https://gitlab.com/users/sign_in
```

### Final Checklist
- [ ] `signin_gitlab()` function exists and replaces `register_gitlab()`
- [ ] `verify_gitlab_email()` simplified for signin 2FA
- [ ] `main()` calls `signin_gitlab()` instead of `register_gitlab()`
- [ ] Docstring updated to reflect signin workflow
- [ ] `GITLAB_SIGNIN_URL` constant defined correctly
- [ ] No Python syntax errors
- [ ] All imports work
- [ ] Single atomic commit created
