# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-25T03:25:00+07:00  
**Commit:** 20e8f84  
**Branch:** main

## OVERVIEW

All-Hands.dev automation using Selenium + Python 3.13. Automates account registration via Bitbucket OAuth, retrieves API keys. Uses local proxy server for authenticated proxy support and dongvanfb.net API for email verification.

## STRUCTURE

```
automation/
├── allhands_auto_register.py   # Main entry (2627 LOC) - monolithic
├── email_api_helper.py         # Email API functions (import only)
├── proxy_server.py             # Standalone proxy server
├── fetch_mail_*.py             # Utility scripts
├── products.txt                # INPUT: email|pass|refresh|client_id
├── api_keys.txt                # OUTPUT: username|sk_live_...
├── errormail.txt               # FAILURES: append-only log
├── .beads/                     # Task tracking (bd CLI)
└── .venv/                      # Python 3.13 venv
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Registration flow | `allhands_auto_register.py:1100-1800` | Direct Bitbucket auth URL |
| Proxy setup | `allhands_auto_register.py:40-216` | Local forwarding proxy |
| Email verification | `email_api_helper.py` | `wait_for_bitbucket_code()`, `wait_for_openhands_link()` |
| WebDriver init | `allhands_auto_register.py:749-834` | undetected-chromedriver preferred |
| Task management | `.beads/` | Use `bd` CLI |
| Credentials | `.env` | MongoDB URI only |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `main()` | func | allhands_auto_register.py | Entry point, batch processor |
| `start_local_proxy_server()` | func | allhands_auto_register.py:163 | Spawns proxy thread |
| `setup_driver()` | func | allhands_auto_register.py:749 | Chrome + proxy config |
| `register_account()` | func | allhands_auto_register.py:1100+ | Full registration flow |
| `wait_for_bitbucket_code()` | func | email_api_helper.py | SMS code via API |
| `wait_for_openhands_link()` | func | email_api_helper.py | Email link via API |
| `ProxyServer` | class | proxy_server.py | HTTP/HTTPS forwarding |

## CONVENTIONS

### Input Format (MANDATORY)
```
email|password|refresh_token|client_id
```
All 4 fields required. Old 2-field format NOT supported.

### Global Flags
```python
TURBO_MODE = True        # Timing delays
USE_PROXY = True         # Enable proxy.txt
ENABLE_WARMUP = False    # Pre-navigation
```

### Proxy Architecture
```
Chrome → 127.0.0.1:18888 → Authenticated Upstream → Internet
         [no auth]          [auth auto-added]
```

### Error Philosophy
- Failed email → `errormail.txt` → continue processing
- CAPTCHA → manual solve (300s timeout) → continue
- Only stops: empty input, Ctrl+C, driver init failure

## ANTI-PATTERNS (THIS PROJECT)

### NEVER DO
- Use `get_sms_from_api()` - DEPRECATED, returns status=False
- Use old 2-field email format - NOT SUPPORTED
- Use selenium-wire for proxy - Python 3.13 blinker conflicts
- Use undetected-chromedriver + proxy - SSL certificate issues
- Duplicate to api_keys.txt manually - auto-deduped
- Delete tests to make build pass
- Stop session before `git push` succeeds
- Say "ready to push when you are" - YOU push

### USE INSTEAD
- `wait_for_bitbucket_code()` from email_api_helper.py
- `wait_for_openhands_link()` from email_api_helper.py
- Standard Selenium with local proxy server

### DISABLED CODE (intentional)
```python
# Line 1033-1051: undetected-chromedriver + proxy (SSL issues)
# Line 1070-1080: Proxy verification (already working)
# Line 1004-1006: Original IP check (not needed)
```

## COMMANDS

```bash
# Run main script
python3 allhands_auto_register.py

# Task management (Beads)
bd ready --json              # Available tasks
bd list --json               # All tasks
bd update <id> --status in_progress
bd close <id> --reason "..."
bd sync                      # MANDATORY before session end

# Session completion (MANDATORY)
git pull --rebase && bd sync && git push
git status  # Must show "up to date with origin"
```

## TASK MANAGEMENT (Beads)

Priority levels: P0 (critical) → P3 (low)

### Current Open Tasks
- **P0 auto-bk3**: Security - move credentials to .env, add .gitignore
- **P1 auto-iue**: Custom exception classes
- **P1 auto-dbx**: Parallel email processing
- **P1 auto-1tc**: Docker support
- **P2 auto-46i**: Structured logging
- **P2 auto-msy**: Unit tests

## SESSION COMPLETION (MANDATORY)

Work is NOT complete until `git push` succeeds.

1. File issues for remaining work (`bd create`)
2. Update issue status (`bd close` / `bd update`)
3. Push to remote:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```

**NEVER** stop before pushing - leaves work stranded locally.

## NOTES

### Performance (Email API vs Selenium)
| Operation | Selenium | API | Savings |
|-----------|----------|-----|---------|
| Open Gmail | 5-8s | 0s | 5-8s |
| Find email | 2-4s | 0.5s | 1.5-3.5s |
| **Total** | 12-20s | 0.5s | **11.5-19.5s/email** |

### Common Issues
- Port 18888 in use → change LOCAL_PORT
- Proxy offline → curl test detects before browser init
- CAPTCHA → manual solve, script waits 300s

### Missing Infrastructure
- No CI/CD (.github/workflows)
- No tests (pytest not configured)
- No Docker (task auto-1tc pending)
- No linters/formatters
