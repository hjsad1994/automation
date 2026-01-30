# Draft: GitLab Sign-IN Conversion

## Requirements (confirmed)
- Convert `gitlab_login.py` from SIGNUP to SIGNIN flow
- Keep warmup logic for Cloudflare bypass at `/sign_in`
- Fill signin form instead of signup form (email + password)
- Handle SMS verification after login using existing `wait_for_gitlab_verification_code()`
- Keep all existing OpenHands flow intact
- Same input format: `email|password|refresh_token|client_id`

## Technical Decisions

### Current Flow (SIGNUP):
1. `register_gitlab()` - Fills signup form (first_name, last_name, username, email, password)
2. `verify_gitlab_email()` - Gets 6-digit code from email API, fills verification form
3. `login_openhands_gitlab()` - OAuth login to OpenHands
4. `get_api_key()` - Gets API key

### Target Flow (SIGNIN):
1. Warmup (keep existing Cloudflare bypass at `/sign_in`)
2. SIGNIN GitLab - Enter email + password into login form
3. Handle SMS/2FA verification (code sent via SMS/email)
4. Continue to OpenHands (existing flow)
5. Get API key (existing)

## Research Findings

### GitLab Sign-in Page Elements (from user):
- URL: https://gitlab.com/users/sign_in
- Email/username field: `#user_login`
- Password field: `#user_password`
- Submit button: `button[type='submit']` or `[data-testid='sign-in-button']`

### SMS Verification Elements (from user):
- Code input field: `#verification_code`
- Submit: `button[type='submit']`

### Existing Helper Functions to Keep:
- `wait_for_gitlab_verification_code()` - Already exists in email_api_helper.py
- `wait_for_openhands_link()` - Keep for OpenHands email verification
- `human_like_type()` - Keep for realistic typing
- `random_delay()` - Keep for timing
- `setup_ixbrowser_driver()` - Keep unchanged
- `close_ixbrowser_profile()` - Keep unchanged
- `read_emails()` - Keep unchanged
- `login_openhands_gitlab()` - Keep unchanged (handles OAuth flow)
- `get_api_key()` - Keep unchanged
- `save_api_key()` - Keep unchanged
- `log_error()` - Keep unchanged

### Functions to Modify:
- `register_gitlab()` → Replace with `signin_gitlab()`
- `verify_gitlab_email()` → Repurpose for SMS verification (maybe rename)
- `main()` → Call signin instead of register

## Scope Boundaries
- INCLUDE:
  - New `signin_gitlab()` function
  - Handle 2FA/SMS verification after signin
  - Update `main()` to use signin
  - Update docstrings and comments
  
- EXCLUDE:
  - Modifying OpenHands login flow (keep as-is)
  - Modifying API key retrieval (keep as-is)
  - Changing input file format
  - Modifying ixBrowser integration

## Open Questions
1. ✅ User confirmed elements for sign-in form
2. ✅ User confirmed SMS verification uses same code extraction logic
3. What happens if there's no 2FA? (Account not enrolled) - Handle gracefully
4. Should we keep `register_gitlab()` as a fallback? - Likely NO, replace entirely
