# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an All-Hands.dev automation project using Selenium to automate account registration and API key retrieval through Bitbucket OAuth with Google authentication. The project uses `undetected-chromedriver` to bypass bot detection and implements a custom local proxy server for authenticated proxy support.

## Running the Scripts

### Main Registration Script
```bash
python3 allhands_auto_register.py
```

Processes emails from `products.txt` with **REQUIRED format**: `email|password|refresh_token|client_id`. Uses email API (dongvanfb.net) to retrieve verification codes and links. Registers accounts directly via Bitbucket auth URL, retrieves API keys, and saves them to `api_keys.txt`. Failed emails are saved to `errormail.txt` and script continues processing.

**⚠️ Important**: All 4 fields are mandatory. The old `email|password` format is no longer supported.

**New Flow (2026-01)**:
1. Navigate directly to Bitbucket auth URL (bypasses app.all-hands.dev OAuth button)
2. Login with email/password + SMS verification
3. Grant access and resend verification email
4. Verify email via API
5. Open new tab with auth URL to complete login
6. Accept Terms of Service and get API key

### Test Proxy Connection
```bash
python3 test_proxy.py
```

Tests proxy configuration with whoer.net to verify IP masking is working correctly.

## Architecture

### Core Script: `allhands_auto_register.py` (~3000+ lines)

**Key Components:**

1. **Local Proxy Server** (lines 40-162)
   - Custom HTTP/HTTPS proxy implementation using raw sockets
   - Forwards requests to upstream authenticated proxy
   - Automatically adds `Proxy-Authorization` headers
   - Handles CONNECT method for HTTPS tunneling
   - Started in background thread via `start_local_proxy_server()`

2. **Proxy Configuration System**
   - Reads proxies from `proxy.txt` with format: `IP:PORT:USERNAME:PASSWORD`
   - Example: `118.70.171.67:23443:KbdsYf:ffyDYM`
   - Uses HTTP protocol by default
   - Circular rotation through proxy list via global `PROXY_INDEX`
   - Pre-validates proxy IP using curl before browser initialization

3. **WebDriver Setup** (lines 749-834)
   - Priority: `undetected-chromedriver` for stealth
   - Fallback: Standard Selenium WebDriver
   - Chrome connects to local proxy (127.0.0.1:18888) which forwards to authenticated upstream proxy
   - No authentication popups - handled transparently by local proxy server

4. **Registration Flow (Updated 2026-01)**
   - Navigate directly to Bitbucket auth URL (no need to click OAuth button)
   - Login with email/password on Atlassian
   - Handle SMS verification via dongvanfb.net API
   - Create account and grant access
   - Resend verification email
   - Verify email via API (no Selenium/Gmail popup needed)
   - Open new tab with auth URL to complete login
   - Accept Terms of Service
   - Retrieve API key from settings page

### Critical Implementation Patterns

**Email Verification via API** (dongvanfb.net):
- No Selenium/Gmail interaction needed
- Uses `wait_for_bitbucket_code()` and `wait_for_openhands_link()` from `email_api_helper.py`
- Polls API every 5 seconds for verification code and email link
- Timeout: 120 seconds

**Configuration System** (lines 60-80):
```python
TURBO_MODE = True        # Affects all timing delays
USE_PROXY = True         # Enable/disable proxy from proxy.txt
ENABLE_WARMUP = False    # Pre-navigation warmup
```

### Proxy Architecture

```
Chrome → Local Proxy (127.0.0.1:18888) → Authenticated Proxy (upstream) → Internet
         [No auth needed]                  [Auth added automatically]
```

**Why This Approach:**
- selenium-wire has compatibility issues with Python 3.13 (blinker module conflicts)
- Chrome extensions don't reliably handle proxy authentication
- Local forwarding proxy is simple, reliable, and doesn't require extensions

**Proxy Functions:**
- `load_proxies_from_file()` - Reads proxy.txt at startup
- `get_proxy_from_file()` - Returns next proxy with circular rotation, pre-validates with curl
- `start_local_proxy_server()` - Spawns background thread running forwarding proxy
- `verify_proxy_is_working()` - Checks actual IP via ipify.org

## File Format Specifications

**Input Files:**
- `email.txt`: `email@domain.com|password` (one per line)
- `proxy.txt`: `IP:PORT:USERNAME:PASSWORD` (one per line, HTTP protocol assumed)
  - Lines starting with `#` are treated as comments
  - Empty lines are ignored

**Output Files:**
- `api_keys.txt`: `username|sk_live_...` (username = email.split('@')[0])
- `errormail.txt`: Same format as email.txt, auto-appended on failures

## Important Behavioral Rules

1. **Never duplicate to api_keys.txt** - Script automatically handles deduplication
2. **Continue on failure** - Main script continues processing remaining emails when one fails
3. **No auto-cleanup** - `errormail.txt` is append-only, requires manual cleanup
4. **CAPTCHA handling** - Scripts pause for manual solving with 300s timeout via `wait_for_manual_captcha_solve()`

## Modifying Login Flow

When editing login logic:
- New flow (2026-01) uses direct Bitbucket auth URL - no Google login needed
- SMS verification is handled via dongvanfb.net API - no Gmail popup needed
- Email verification is handled via dongvanfb.net API - no Selenium email interaction
- After verification, open new tab with auth URL to complete login

## Dependencies

Critical dependencies (see requirements.txt):
- `selenium` + `webdriver-manager`
- `undetected-chromedriver` (essential for bypassing detection)
- `blinker<1.8` (required for Python 3.13 compatibility)
- `setuptools` (provides pkg_resources for selenium-wire if used)

**selenium-wire status:** Installed but not actively used due to SSL certificate issues. Local proxy server is the preferred solution.

## Error Handling Philosophy

The main script is designed to be resilient:
- Failed email → Save to errormail.txt → Continue processing
- CAPTCHA detected → Wait for manual solving (300s timeout) → Continue
- Element not found → Try multiple selectors → Fallback methods → Continue if possible
- Proxy failure → Verify with IP check → Report but continue

Script will only stop on:
- Empty email.txt
- Keyboard interrupt (Ctrl+C)
- Critical driver initialization failure

## Debugging Proxy Issues

**Symptoms of proxy not working:**
- Browser shows your real IP when checking whoer.net or ipify.org
- verify_proxy_is_working() reports "CẢNH BÁO: Browser đang dùng IP khác"

**Troubleshooting steps:**
1. Check `proxy.txt` format is correct (IP:PORT:USERNAME:PASSWORD)
2. Verify proxy credentials with: `curl -x http://user:pass@host:port https://api.ipify.org`
3. Check local proxy server started: Look for "Local proxy server started: 127.0.0.1:18888"
4. Verify Chrome is using local proxy: Should see "--proxy-server=http://127.0.0.1:18888"
5. Check proxy is actually forwarding: Run `test_proxy.py` to isolate the issue

**Common issues:**
- Port 18888 already in use → Change LOCAL_PORT in start_local_proxy_server()
- Upstream proxy offline → Script will detect via curl test before browser initialization
- Firewall blocking → Check system firewall allows localhost connections on 18888
- them nhung gi da thay doi nay gio
- hay them nhung gi da thay doi