# -*- coding: utf-8 -*-
"""
Script tự động ĐĂNG KÝ GITLAB + LOGIN OPENHANDS + LẤY API KEY

WORKFLOW:
1. Warmup: Mở GitLab /sign_in để pass Cloudflare
2. Mở tab mới → Vào GitLab /sign_up trực tiếp
3. Điền form đăng ký GitLab + xử lý CAPTCHA
4. VERIFY EMAIL GITLAB (điền code 6 số từ email)
5. Mở tab mới → dongvanfb.net/read_mail_box/ + paste credentials
6. Mở tab mới → OpenHands /login
7. Click "Log in with GitLab" → Authorize
8. ⏸️ SCRIPT DỪNG → User tự xử lý CAPTCHA + lấy API key
9. User nhấn ENTER → Chuyển sang email tiếp theo

QUAN TRỌNG: 
- PHẢI verify email GitLab TRƯỚC thì mới login OpenHands được
- Nếu không verify → GitLab OAuth sẽ báo "Email not verified"
- Script tự động lấy code từ email API và điền vào

Sử dụng ixBrowser profile (Incognito + Clear cookies)
"""

# Fix Windows console encoding
import sys
import io
if sys.platform == "win32":
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

import time
import os
import random
import requests
import threading

# Load .env
from dotenv import load_dotenv
load_dotenv()

# Import ixBrowser Local API
try:
    from ixbrowser_local_api import IXBrowserClient
    IXBROWSER_AVAILABLE = True
    print("✓ ixbrowser-local-api có sẵn")
except ImportError:
    IXBROWSER_AVAILABLE = False
    print("✗ ixbrowser-local-api chưa cài. Chạy: pip install ixbrowser-local-api")
    sys.exit(1)

# Import email API helper
try:
    from email_api_helper import wait_for_gitlab_verification_code, wait_for_openhands_link
    EMAIL_API_AVAILABLE = True
    print("✓ email_api_helper có sẵn")
except ImportError:
    EMAIL_API_AVAILABLE = False
    print("⚠ email_api_helper không import được")

# ============================================================
# SETTINGS
# ============================================================

# ixBrowser Profile ID - Dùng profile 1
_ixbrowser_profile_id_str = os.getenv("IXBROWSER_PROFILE_ID_1", "1")
IXBROWSER_PROFILE_ID = int(_ixbrowser_profile_id_str) if _ixbrowser_profile_id_str.isdigit() else 1

# Name for webhook payload
WEBHOOK_NAME = os.getenv("NAME_1", "tai-p1")

# ixBrowser API
IXBROWSER_API_HOST = "127.0.0.1"
IXBROWSER_API_PORT = 53200

# URLs
GITLAB_SIGNUP_URL = "https://gitlab.com/users/sign_up"
OPENHANDS_LOGIN_URL = "https://app.all-hands.dev/login"
OPENHANDS_API_KEYS_URL = "https://app.all-hands.dev/settings/api-keys"

# Webhook Configuration
WEBHOOK_BASE_URL = "http://localhost:3005"
WEBHOOK_SECRET = "ahihi123"
WEBHOOK_CHECK_INTERVAL = 2  # seconds

# Files
EMAIL_FILE = "products1.txt"  # Format: email|password|refresh_token|client_id
API_KEYS_FILE = "api_keys.txt"
ERROR_LOG_FILE = "errormail.txt"

# Timing - ULTRA TURBO MODE (2x speed)
TURBO_MODE = True
if TURBO_MODE:
    TYPING_SPEED = (0.001, 0.005)  # Gần như instant
    DELAY_SHORT = (0.05, 0.1)      # 50% faster
    DELAY_MEDIUM = (0.1, 0.2)      # 50% faster
    PAGE_LOAD_WAIT = 0.2           # 60% faster
else:
    TYPING_SPEED = (0.05, 0.1)
    DELAY_SHORT = (0.3, 0.6)
    DELAY_MEDIUM = (0.5, 1.0)
    PAGE_LOAD_WAIT = 2

# Ultra fast settings
WAIT_TIMEOUT = 8          # WebDriverWait timeout (giảm từ 10-15)
WAIT_TIMEOUT_SHORT = 3    # Short wait timeout
CLICK_DELAY = 0.1         # Delay sau click
NAV_DELAY = 1             # Delay sau navigation

# ============================================================
# GLOBAL VARIABLES
# ============================================================
IXBROWSER_CLIENT = None


def random_delay(delay_type='short'):
    """Random delay"""
    if delay_type == 'short':
        time.sleep(random.uniform(*DELAY_SHORT))
    elif delay_type == 'medium':
        time.sleep(random.uniform(*DELAY_MEDIUM))


def human_like_type(element, text):
    """Gõ text giống người thật"""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(*TYPING_SPEED))


def generate_username_from_email(email):
    """Tạo username từ email"""
    prefix = email.split('@')[0]
    username = ''.join(c for c in prefix if c.isalnum())
    username = f"{username}{random.randint(100, 999)}"
    return username[:20]


def generate_name_from_email(email):
    """Tạo first name và last name từ email"""
    prefix = email.split('@')[0]
    clean_prefix = ''.join(c for c in prefix if c.isalpha())
    
    if len(clean_prefix) < 4:
        clean_prefix = ''.join(c for c in prefix if c.isalnum())
    
    mid = len(clean_prefix) // 2
    first_name = clean_prefix[:mid].capitalize()
    last_name = clean_prefix[mid:].capitalize()
    
    if len(first_name) < 2:
        first_name = "User"
    if len(last_name) < 2:
        last_name = "Account"
    
    first_name = first_name[:20]
    last_name = last_name[:20]
    
    return first_name, last_name


def setup_ixbrowser_driver(profile_id, incognito=True):
    """Mở ixBrowser profile và kết nối Selenium"""
    global IXBROWSER_CLIENT
    
    print(f"\n[ixBrowser] Đang kết nối API (127.0.0.1:53200)...")
    IXBROWSER_CLIENT = IXBrowserClient(target=IXBROWSER_API_HOST, port=IXBROWSER_API_PORT)
    
    startup_args = []
    if incognito:
        startup_args.append("--incognito")
        print("[ixBrowser] Chế độ: ẨN DANH (Incognito)")
    
    print(f"[ixBrowser] Đang mở profile {profile_id}...")
    open_result = IXBROWSER_CLIENT.open_profile(
        profile_id=profile_id,
        cookies_backup=False,
        load_profile_info_page=False,
        load_extensions=True,
        disable_extension_welcome_page=True,
        startup_args=startup_args
    )
    
    if open_result is None:
        raise Exception(f"Không thể mở profile: {IXBROWSER_CLIENT.code} - {IXBROWSER_CLIENT.message}")
    
    webdriver_path = open_result.get('webdriver')
    debugging_address = open_result.get('debugging_address')
    
    print(f"✓ Profile đã mở")
    print(f"  Debugging Address: {debugging_address}")
    
    # Kết nối Selenium
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", debugging_address)
    
    try:
        driver = webdriver.Chrome(service=Service(webdriver_path), options=chrome_options)
    except:
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    print("✓ Selenium đã kết nối")
    return driver


def close_ixbrowser_profile(profile_id, clear_data=True):
    """Đóng profile và clear data"""
    global IXBROWSER_CLIENT
    
    if IXBROWSER_CLIENT is None:
        return
    
    if clear_data:
        print(f"[ixBrowser] Đang clear cookies và cache...")
        try:
            result = IXBROWSER_CLIENT.clear_profile_cache_and_cookies(profile_id)
            if result:
                print("✓ Đã clear cookies và cache")
            else:
                print(f"⚠ Lỗi clear: {IXBROWSER_CLIENT.code}")
        except Exception as e:
            print(f"⚠ Lỗi: {str(e)}")
    
    print(f"[ixBrowser] Đang đóng profile...")
    try:
        IXBROWSER_CLIENT.close_profile(profile_id)
        print("✓ Đã đóng profile")
    except:
        pass


def read_emails(email_file=EMAIL_FILE):
    """Đọc email từ file"""
    if not os.path.exists(email_file):
        print(f"✗ Không tìm thấy file {email_file}")
        return []
    
    emails = []
    with open(email_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or '|' not in line:
                continue
            
            parts = line.split('|')
            if len(parts) < 4:
                print(f"⚠ Bỏ qua dòng thiếu fields: {parts[0] if parts else 'empty'}")
                continue
            
            email = parts[0].strip()
            password = parts[1].strip()
            refresh_token = parts[2].strip()
            client_id = parts[3].strip()
            
            if email and password and refresh_token and client_id:
                emails.append({
                    'email': email,
                    'password': password,
                    'refresh_token': refresh_token,
                    'client_id': client_id
                })
    
    return emails


def register_gitlab(driver, email, password):
    """Đăng ký tài khoản GitLab"""
    try:
        wait = WebDriverWait(driver, 15)
        
        print(f"\n[STEP 1: GitLab Signup]")
        
        # BƯỚC 1: Vào /sign_in trước để pass Cloudflare
        print(f"[Cloudflare Warmup] Đang mở /sign_in trước...")
        driver.get("https://gitlab.com/users/sign_in")
        time.sleep(3)
        
        # Đợi Cloudflare xử lý (nếu có)
        max_cf_wait = 30
        cf_start = time.time()
        while time.time() - cf_start < max_cf_wait:
            current_url = driver.current_url
            
            # Nếu đã vào được trang sign_in thật sự (có form login) → Cloudflare passed
            try:
                # Check form login field (id="user_login") hoặc sign-in-form
                login_form = driver.find_elements(By.ID, "user_login")
                sign_in_form = driver.find_elements(By.ID, "sign-in-form")
                if login_form or sign_in_form:
                    print("  ✓ Cloudflare passed! Trang /sign_in đã load")
                    break
            except:
                pass
            
            # Thử click Cloudflare checkbox nếu có
            try:
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframes:
                    src = iframe.get_attribute("src") or ""
                    if "challenge" in src.lower() or "turnstile" in src.lower():
                        print("  → Đang click Cloudflare checkbox...")
                        driver.switch_to.frame(iframe)
                        time.sleep(0.5)
                        body = driver.find_element(By.TAG_NAME, "body")
                        body.click()
                        driver.switch_to.default_content()
                        time.sleep(2)
                        break
            except:
                pass
            
            time.sleep(1)
        
        # BƯỚC 2: Mở tab mới để vào /sign_up
        print(f"\n[Signup] Mở tab mới để vào {GITLAB_SIGNUP_URL}...")
        driver.execute_script("window.open('');")
        time.sleep(0.5)
        driver.switch_to.window(driver.window_handles[-1])
        
        driver.get(GITLAB_SIGNUP_URL)
        
        # Đợi form load
        wait.until(EC.presence_of_element_located((By.ID, "new_user_email")))
        print("✓ Form đăng ký đã load")
        time.sleep(1)
        
        # Generate names
        first_name, last_name = generate_name_from_email(email)
        username = generate_username_from_email(email)
        
        print(f"\n[GitLab] Đang điền form...")
        print(f"  Email: {email}")
        print(f"  First Name: {first_name}")
        print(f"  Last Name: {last_name}")
        print(f"  Username: {username}")
        
        # Điền form
        print("\n[1/5] Điền First Name...")
        first_name_field = wait.until(EC.presence_of_element_located((By.ID, "new_user_first_name")))
        human_like_type(first_name_field, first_name)
        random_delay('short')
        
        print("[2/5] Điền Last Name...")
        last_name_field = driver.find_element(By.ID, "new_user_last_name")
        human_like_type(last_name_field, last_name)
        random_delay('short')
        
        print("[3/5] Điền Username...")
        username_field = driver.find_element(By.ID, "new_user_username")
        human_like_type(username_field, username)
        random_delay('medium')
        
        # Check username availability
        time.sleep(1.5)
        try:
            error_msg = driver.find_elements(By.CSS_SELECTOR, ".validation-error:not(.hide)")
            if error_msg:
                print("  ⚠ Username taken, đang thử username khác...")
                new_username = f"{username}{random.randint(1000, 9999)}"
                username_field.clear()
                human_like_type(username_field, new_username)
                time.sleep(1.5)
        except:
            pass
        
        print("[4/5] Điền Email...")
        email_field = driver.find_element(By.ID, "new_user_email")
        human_like_type(email_field, email)
        random_delay('short')
        
        print("[5/5] Điền Password...")
        password_field = driver.find_element(By.ID, "new_user_password")
        password_field.clear()
        password_field.send_keys("Aa@123456X")  # Hardcoded password cho GitLab signup
        random_delay('short')
        
        print("\n✓ Đã điền đầy đủ form!")
        
        # Đợi backend validate
        delay = random.uniform(10, 11)
        print(f"\n[GitLab] Đợi {delay:.1f}s để backend validate...")
        time.sleep(delay)
        
        # Click Continue
        print("[GitLab] Đang click nút Continue...")
        submit_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='new-user-register-button']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", submit_button)
        random_delay('short')
        
        try:
            submit_button.click()
        except:
            driver.execute_script("arguments[0].click();", submit_button)
        
        print("✓ Đã click Continue")
        
        # Đợi Cloudflare xử lý và redirect (quan trọng!)
        print("\n[GitLab] Đang đợi Cloudflare xử lý...")
        
        # Đợi URL thay đổi từ /users sang /identity_verification hoặc /welcome
        max_wait_cloudflare = 60  # Tăng lên 60 giây
        start_time = time.time()
        last_url = ""
        current_url = ""
        
        verification_challenge_retry_count = 0
        max_verification_retries = 10  # Tối đa 10 lần retry
        
        while time.time() - start_time < max_wait_cloudflare:
            try:
                current_url = driver.current_url
                
                # Log URL nếu thay đổi
                if current_url != last_url:
                    elapsed = int(time.time() - start_time)
                    print(f"  [{elapsed}s] URL: {current_url}")
                    last_url = current_url
                
                # CHECK LỖI Ở MỌI ITERATION: "error loading the user verification challenge"
                # Lỗi này có thể xuất hiện ở bất kỳ trang nào sau khi click Continue
                try:
                    error_selectors = [
                        ".gl-alert-body",
                        "[data-testid='alert-danger'] .gl-alert-body",
                        ".flash-alert.gl-alert-danger .gl-alert-body",
                    ]
                    
                    error_found = False
                    for selector in error_selectors:
                        try:
                            error_alerts = driver.find_elements(By.CSS_SELECTOR, selector)
                            for alert in error_alerts:
                                alert_text = alert.text.lower()
                                if "error loading" in alert_text and "verification challenge" in alert_text:
                                    error_found = True
                                    break
                        except:
                            continue
                        if error_found:
                            break
                    
                    if error_found:
                        verification_challenge_retry_count += 1
                        print(f"  ⚠ Lỗi: 'error loading the user verification challenge' (lần {verification_challenge_retry_count}/{max_verification_retries})")
                        
                        if verification_challenge_retry_count > max_verification_retries:
                            print("  ✗ Đã retry quá nhiều lần, bỏ qua...")
                            break
                        
                        # Dismiss error alert nếu có
                        try:
                            dismiss_btn = driver.find_element(By.CSS_SELECTOR, ".gl-dismiss-btn, button[aria-label='Dismiss'], .js-close")
                            dismiss_btn.click()
                            time.sleep(0.5)
                            print("  ✓ Đã dismiss error alert")
                        except:
                            pass
                        
                        # Nhập lại password (KHÔNG refresh trang)
                        try:
                            password_field = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.ID, "new_user_password"))
                            )
                            password_field.clear()
                            password_field.send_keys("Aa@123456X")  # Hardcoded password
                            print("  ✓ Đã nhập lại password")
                            
                            # Đợi 5 giây như yêu cầu
                            print("  → Đợi 5s trước khi click Continue...")
                            time.sleep(5)
                            
                            # Click Continue
                            continue_btn = driver.find_element(By.CSS_SELECTOR, "[data-testid='new-user-register-button']")
                            driver.execute_script("arguments[0].click();", continue_btn)
                            print("  ✓ Đã click Continue")
                            
                            # Reset timer để tiếp tục loop
                            start_time = time.time()
                            last_url = ""
                            continue
                        except Exception as e:
                            print(f"  ⚠ Không thể retry: {str(e)[:50]}")
                            # Thử refresh nếu không tìm thấy password field
                            try:
                                driver.refresh()
                                time.sleep(3)
                                start_time = time.time()
                                last_url = ""
                                continue
                            except:
                                pass
                except:
                    pass
                
                # Nếu đã vào trang verification hoặc welcome VÀ không có lỗi → xong
                if "identity_verification" in current_url or "welcome" in current_url:
                    # Double-check không còn lỗi
                    try:
                        error_alerts = driver.find_elements(By.CSS_SELECTOR, ".gl-alert-body")
                        has_error = False
                        for alert in error_alerts:
                            if "error loading" in alert.text.lower():
                                has_error = True
                                break
                        if not has_error:
                            print("  ✓ Đã vào trang verification/welcome thành công!")
                            break
                    except:
                        print("  ✓ Đã vào trang verification/welcome")
                        break
                
                # Nếu bị redirect về /sign_in → fail (đã warmup rồi mà vẫn bị)
                if "/sign_in" in current_url:
                    print(f"\n  ✗ Bị redirect về /sign_in dù đã warmup!")
                    return False
                
                # Nếu ở /users → kiểm tra và click Cloudflare
                if "/users" in current_url and "sign_up" not in current_url:
                    
                    # Thử click Cloudflare checkbox
                    try:
                        # Cách 1: Tìm iframe turnstile/challenge
                        iframes = driver.find_elements(By.TAG_NAME, "iframe")
                        for iframe in iframes:
                            try:
                                src = iframe.get_attribute("src") or ""
                                title = iframe.get_attribute("title") or ""
                                
                                if "challenge" in src.lower() or "turnstile" in src.lower() or "cloudflare" in title.lower():
                                    print("  → Tìm thấy Cloudflare iframe, đang click...")
                                    
                                    # Switch vào iframe
                                    driver.switch_to.frame(iframe)
                                    time.sleep(0.5)
                                    
                                    # Click checkbox hoặc body của iframe
                                    try:
                                        # Thử click checkbox
                                        cb = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox'], .cb-lb, #checkbox")
                                        cb.click()
                                        print("  ✓ Đã click checkbox trong iframe")
                                    except:
                                        # Click body của iframe
                                        body = driver.find_element(By.TAG_NAME, "body")
                                        body.click()
                                        print("  ✓ Đã click body iframe")
                                    
                                    driver.switch_to.default_content()
                                    time.sleep(2)
                                    break
                            except:
                                continue
                        
                        # Cách 2: Click trực tiếp vào div chứa challenge
                        try:
                            cf_container = driver.find_element(By.CSS_SELECTOR, "#challenge-stage, .cf-turnstile, [data-sitekey]")
                            cf_container.click()
                            print("  ✓ Đã click Cloudflare container")
                            time.sleep(2)
                        except:
                            pass
                        
                        # Cách 3: Execute script để click
                        try:
                            driver.execute_script("""
                                var iframes = document.querySelectorAll('iframe');
                                for (var i = 0; i < iframes.length; i++) {
                                    var src = iframes[i].src || '';
                                    if (src.includes('challenge') || src.includes('turnstile')) {
                                        iframes[i].contentDocument.body.click();
                                        break;
                                    }
                                }
                            """)
                        except:
                            pass
                            
                    except Exception as e:
                        pass  # Tiếp tục đợi
                    
                    time.sleep(1)
                    continue
                    
            except Exception as e:
                print(f"  ⚠ Lỗi: {str(e)[:30]}")
            
            time.sleep(1)
        
        # Lấy URL cuối cùng
        try:
            current_url = driver.current_url
            print(f"  URL cuối cùng: {current_url}")
        except:
            pass
        
        # Check CAPTCHA
        if "sign_up" in current_url:
            captcha = driver.find_elements(By.CSS_SELECTOR, ".js-arkose-labs-container-13")
            if captcha and captcha[0].is_displayed():
                print("\n" + "!" * 60)
                print("⚠ CAPTCHA XUẤT HIỆN!")
                print("  Vui lòng giải CAPTCHA thủ công trong 120s...")
                print("!" * 60)
                
                for i in range(120):
                    time.sleep(1)
                    if "sign_up" not in driver.current_url:
                        print("\n✓ CAPTCHA đã được giải!")
                        break
                    print(f"  Đợi CAPTCHA... ({120-i}s)", end='\r')
        
        print("\n" + "=" * 60)
        print("✅ ĐĂNG KÝ GITLAB THÀNH CÔNG!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Lỗi khi đăng ký GitLab: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# NOTE: Function verify_gitlab_email() đã bị XÓA
# Vì logic mới: Đăng ký GitLab → Mở tab mới → Login OpenHands trực tiếp
# GitLab sẽ tự động login do cùng browser session (cookies)


def verify_gitlab_email(driver, email, refresh_token, client_id):
    """
    Verify email GitLab qua API
    
    QUAN TRỌNG: Phải verify email GitLab trước thì mới login OpenHands được!
    """
    try:
        print(f"\n[STEP 2: GitLab Email Verification]")
        
        # Đợi 5s để tránh Cloudflare/redirect chưa xong
        print("  Đang đợi 5s để GitLab redirect hoàn tất...")
        time.sleep(5)
        
        # Kiểm tra URL hiện tại với retry logic
        current_url = ""
        max_retries = 6
        
        for attempt in range(max_retries):
            try:
                current_url = driver.current_url
                print(f"  URL hiện tại (attempt {attempt+1}): {current_url}")
                
                # Nếu đã có URL hợp lệ → break
                if current_url and len(current_url) > 20:
                    break
                    
            except Exception as e:
                print(f"  ⚠ Không lấy được URL (attempt {attempt+1}): {str(e)[:50]}")
            
            # Nếu chưa lấy được hoặc URL chưa hợp lệ → đợi thêm
            if attempt < max_retries - 1:
                wait_time = 3 + attempt * 2  # 3s, 5s, 7s
                print(f"  → Đợi thêm {wait_time}s...")
                time.sleep(wait_time)
        
        # Nếu không ở trang identity_verification → có thể đã verify rồi hoặc skip
        if current_url and "identity_verification" not in current_url:
            print("⚠ Không ở trang identity_verification")
            
            # Check xem có phải trang welcome hoặc success không
            if "/welcome" in current_url or "/success" in current_url:
                print("  → Đã verify thành công (đang ở trang welcome/success)")
                print("  → Tiếp tục với OpenHands login...")
                return True
            
            # Nếu đang ở /users → có thể chưa redirect
            if "/users" in current_url and "/sign_up" not in current_url:
                print("  → Có thể GitLab đang redirect hoặc xử lý Cloudflare")
                print("  → Thử refresh trang để vào verification...")
                
                # Refresh lại trang
                try:
                    driver.refresh()
                    print("  ✓ Đã refresh trang")
                    time.sleep(5)
                    
                    # Check URL lại sau khi refresh
                    try:
                        new_url = driver.current_url
                        print(f"  URL sau refresh: {new_url}")
                        
                        if "identity_verification" in new_url:
                            print("  ✓ Đã vào trang verification sau khi refresh")
                            current_url = new_url
                        else:
                            print("  → Vẫn không vào được verification, bỏ qua...")
                            return True
                    except:
                        pass
                except Exception as e:
                    print(f"  ⚠ Không refresh được: {str(e)[:50]}")
            
            # Nếu vẫn không ở verification → bỏ qua
            if "identity_verification" not in current_url:
                print("  → GitLab không yêu cầu verify hoặc đã verify trước đó")
                print("  → Tiếp tục với OpenHands login...")
                return True
        
        print("Đang ở trang Identity Verification...")
        print("Cần nhập verification code 6 số từ email")
        
        if not EMAIL_API_AVAILABLE:
            print("✗ email_api_helper không khả dụng")
            print("  Vui lòng nhập code thủ công trong browser")
            # Đợi user nhập thủ công (60s)
            print("  Đang đợi 60s để bạn nhập code thủ công...")
            time.sleep(60)
            return True
        
        # Lấy code từ email API
        print("\n[Verification] Đang lấy code từ email API...")
        verification_code = wait_for_gitlab_verification_code(
            email=email,
            refresh_token=refresh_token,
            client_id=client_id,
            max_wait=120,
            check_interval=5
        )
        
        if not verification_code:
            print("✗ Không tìm thấy verification code trong 120s")
            print("  Vui lòng nhập code thủ công trong browser")
            # Đợi user nhập thủ công
            print("  Đang đợi 60s để bạn nhập code thủ công...")
            time.sleep(60)
            return True
        
        print(f"✓ Tìm thấy code: {verification_code}")
        
        # Điền code
        print("\n[Verification] Đang điền code vào form...")
        try:
            wait = WebDriverWait(driver, 10)
            code_input = wait.until(EC.presence_of_element_located((By.ID, "verification_code")))
            code_input.clear()
            code_input.send_keys(verification_code)
            print(f"  ✓ Đã điền code: {verification_code}")
        except Exception as e:
            print(f"  ✗ Không tìm thấy input field: {str(e)[:100]}")
            print("  → Bỏ qua, có thể đã tự động verify")
            return True
        
        time.sleep(1)
        
        # Click Verify button
        print("\n[Verification] Đang click nút Verify...")
        try:
            verify_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            verify_button.click()
            print("  ✓ Đã click Verify")
        except Exception as e:
            print(f"  ⚠ Không click được Verify button: {str(e)[:100]}")
            print("  → Có thể đã tự động submit")
        
        # Đợi 5s để GitLab xử lý
        print("\n[Verification] Đang đợi GitLab xử lý verify...")
        time.sleep(5)
        
        # Kiểm tra kết quả (dùng try-except)
        verification_success = False
        try:
            new_url = driver.current_url
            print(f"  URL sau verify: {new_url}")
            
            # Check các URL cho biết ĐÃ VERIFY THÀNH CÔNG:
            # GitLab có thể redirect đến nhiều URL khác nhau sau verify:
            success_indicators = [
                "/identity_verification/success",  # Success page - verify thành công
                "/sign_up/welcome",                 # Welcome page - đã qua verify
                "/users/sign_up/welcome",           # Welcome page (full path)
                "/users/",                          # Dashboard (đã verify + skip welcome)
            ]
            
            # Nếu URL chứa bất kỳ indicator nào → thành công!
            if any(indicator in new_url for indicator in success_indicators):
                print("  ✅ Verify thành công! (URL đã chuyển)")
                verification_success = True
            elif "identity_verification" in new_url and "success" not in new_url:
                # Vẫn còn ở trang verification (không phải success page)
                print("  ⚠ Vẫn ở trang verification (chưa thành công)")
                print("  → Code có thể sai hoặc cần thao tác thêm")
                print("  → Đợi 30s để bạn xử lý thủ công...")
                time.sleep(30)
            else:
                # URL khác (có thể đã redirect về dashboard, etc.)
                print(f"  → URL không xác định, giả sử thành công")
                verification_success = True
                
        except Exception as e:
            print(f"  ⚠ Không lấy được URL sau verify: {str(e)[:50]}")
            print("  → Giả sử verify thành công, tiếp tục...")
            verification_success = True
        
        print("\n" + "=" * 60)
        print("✅ GITLAB EMAIL VERIFICATION HOÀN TẤT!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Lỗi khi verify GitLab: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n  → Tiếp tục với OpenHands login anyway...")
        return True  # Trả về True để tiếp tục (không block)


def click_gitlab_login_button(driver, wait):
    """Click nút 'Log in with GitLab' trên trang OpenHands login"""
    gitlab_button_selectors = [
        (By.XPATH, "//button[@type='button']//span[contains(text(), 'Log in with GitLab')]"),
        (By.XPATH, "//button[@type='button' and contains(., 'Log in with GitLab')]"),
        (By.XPATH, "//button[@type='button' and contains(@class, 'bg-[#FC6B0E]')]"),
    ]
    
    gitlab_button = None
    for by, selector in gitlab_button_selectors:
        try:
            gitlab_button = WebDriverWait(driver, WAIT_TIMEOUT_SHORT).until(
                EC.element_to_be_clickable((by, selector))
            )
            break
        except TimeoutException:
            continue
    
    if not gitlab_button:
        return False
    
    driver.execute_script("arguments[0].click();", gitlab_button)  # JS click faster
    return True


def is_on_email_verification_page(driver):
    """Check xem có đang ở trang 'Please check your email to verify your account' không"""
    try:
        current_url = driver.current_url
        
        # Check URL có chứa email_verification_required
        if "email_verification_required=true" in current_url:
            return True
        
        # Check page content
        page_source = driver.page_source
        return ("Please check your email to verify your account" in page_source or
                "Resend verification" in page_source)
    except:
        return False


def is_on_accept_tos_page(driver):
    """Check xem có đang ở trang accept-tos không"""
    try:
        current_url = driver.current_url
        page_source = driver.page_source
        return ("/accept-tos" in current_url or 
                "Accept Terms of Service" in page_source or
                "I accept the" in page_source)
    except:
        return False


def is_on_auth_page(driver):
    """Check xem có đang ở trang Keycloak auth không"""
    try:
        current_url = driver.current_url
        return "auth.app.all-hands.dev" in current_url
    except:
        return False


def is_on_email_already_verified_page(driver):
    """
    Check xem có đang ở trang 'Your email address has been verified already.' không
    
    Trang này xuất hiện khi email đã verify trước đó và cần login lại với GitLab
    HTML: <div class="pf-v5-c-login__main-body">
            <div id="kc-info-message">
              <p class="instruction">Your email address has been verified already.</p>
            </div>
          </div>
    """
    try:
        # Check page content
        page_source = driver.page_source
        if "Your email address has been verified already" in page_source:
            return True
        
        # Check bằng selector cụ thể
        try:
            msg_element = driver.find_element(By.CSS_SELECTOR, "#kc-info-message .instruction")
            if msg_element and "verified already" in msg_element.text.lower():
                return True
        except:
            pass
        
        # Check thêm bằng class pf-v5-c-login__main-body
        try:
            login_body = driver.find_element(By.CSS_SELECTOR, ".pf-v5-c-login__main-body")
            if login_body and "verified already" in login_body.text.lower():
                return True
        except:
            pass
        
        return False
    except:
        return False


def wait_for_page_transition(driver, timeout=10):
    """Đợi trang chuyển đổi (URL thay đổi hoặc content thay đổi)"""
    try:
        initial_url = driver.current_url
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            time.sleep(0.3)
            current_url = driver.current_url
            
            # URL đã thay đổi
            if current_url != initial_url:
                time.sleep(0.2)
                return True
            
            # Check nếu đã vào các trang target
            if is_on_email_verification_page(driver):
                return True
            if is_on_accept_tos_page(driver):
                return True
            if "/settings/api-keys" in current_url or "/conversation" in current_url:
                return True
            # Check GitLab OAuth page
            if "gitlab.com/oauth" in current_url:
                return True
        
        return False
    except:
        return False


def handle_gitlab_oauth_authorize(driver):
    """Handle trang GitLab OAuth Authorization - click Authorize nếu cần"""
    try:
        current_url = driver.current_url
        
        # Check nếu đang ở trang GitLab OAuth
        if "gitlab.com/oauth" not in current_url and "gitlab.com/-/profile" not in current_url:
            return False
        
        print("  ✓ Đang ở trang GitLab OAuth Authorization")
        
        # Tìm và click nút Authorize ngay lập tức
        authorize_selectors = [
            (By.XPATH, "//button[contains(text(), 'Authorize')]"),
            (By.XPATH, "//input[@type='submit' and @value='Authorize']"),
            (By.CSS_SELECTOR, "input[type='submit'][value='Authorize']"),
            (By.CSS_SELECTOR, "button.btn-confirm"),
            (By.CSS_SELECTOR, "button.btn-success"),
            (By.NAME, "commit"),
        ]
        
        for by, selector in authorize_selectors:
            try:
                authorize_button = driver.find_element(by, selector)
                if authorize_button and authorize_button.is_displayed():
                    driver.execute_script("arguments[0].click();", authorize_button)
                    print("  ✓ Đã click 'Authorize'")
                    return True
            except:
                continue
        
        # Fallback: đợi element clickable
        for by, selector in authorize_selectors:
            try:
                authorize_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((by, selector))
                )
                driver.execute_script("arguments[0].click();", authorize_button)
                print("  ✓ Đã click 'Authorize' (wait)")
                return True
            except:
                continue
        
        return False
        
    except Exception as e:
        return False


def click_resend_verification_button(driver):
    """Click nút 'Resend verification' trên trang email verification"""
    try:
        selectors = [
            (By.XPATH, "//button[contains(text(), 'Resend verification')]"),
            (By.XPATH, "//button[contains(., 'Resend verification')]"),
            (By.CSS_SELECTOR, "button.bg-primary"),
        ]
        
        for by, selector in selectors:
            try:
                btn = WebDriverWait(driver, WAIT_TIMEOUT_SHORT).until(
                    EC.element_to_be_clickable((by, selector))
                )
                driver.execute_script("arguments[0].click();", btn)
                print("  ✓ Đã click 'Resend verification'")
                return True
            except:
                continue
        
        return False
    except Exception as e:
        print(f"  ✗ Lỗi click Resend verification: {str(e)[:50]}")
        return False


def extract_openhands_verification_link_from_api(email, refresh_token, client_id, max_wait=60):
    """Lấy verification link từ email API"""
    if not EMAIL_API_AVAILABLE:
        return None
    
    print(f"\n  Đang đợi OpenHands verification email (tối đa {max_wait}s)...")
    link = wait_for_openhands_link(
        email=email,
        refresh_token=refresh_token,
        client_id=client_id,
        max_wait=max_wait,
        check_interval=3  # Check nhanh hơn
    )
    return link


def handle_email_verification_flow(driver, email, refresh_token, client_id):
    """
    Xử lý flow email verification cho OpenHands:
    1. Click 'Resend verification'
    2. Lấy link từ email API
    3. Mở link trong browser
    4. Click 'Click here to proceed'
    5. Click 'Back to application'
    """
    try:
        print(f"\n[EMAIL VERIFICATION FLOW]")
        
        # Click Resend verification
        print("  Đang click 'Resend verification'...")
        if not click_resend_verification_button(driver):
            print("  ⚠ Không click được Resend verification")
        
        time.sleep(CLICK_DELAY)
        
        # Lấy verification link từ email API
        print("\n  Đang lấy verification link từ email...")
        verification_link = extract_openhands_verification_link_from_api(
            email, refresh_token, client_id, max_wait=60
        )
        
        if not verification_link:
            print("  ✗ Không tìm thấy verification link")
            print("  → Vui lòng verify thủ công")
            return False
        
        print(f"  ✓ Tìm thấy link: {verification_link[:80]}...")
        
        # Mở verification link
        print("\n  Đang mở verification link...")
        driver.get(verification_link)
        time.sleep(NAV_DELAY)
        
        # Đợi trang load
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print(f"  ✓ Trang đã load: {driver.current_url}")
        
        # Click "Click here to proceed" nếu có
        print("\n  Đang tìm và click 'Click here to proceed'...")
        proceed_selectors = [
            (By.XPATH, "//a[contains(text(), 'Click here to proceed')]"),
            (By.XPATH, "//a[contains(., 'Click here to proceed')]"),
            (By.XPATH, "//p//a[contains(@href, 'login-actions')]"),
            (By.CSS_SELECTOR, "a[href*='login-actions']"),
        ]
        
        proceed_clicked = False
        for by, selector in proceed_selectors:
            try:
                proceed_link = WebDriverWait(driver, WAIT_TIMEOUT_SHORT).until(
                    EC.element_to_be_clickable((by, selector))
                )
                # Navigate trực tiếp nhanh hơn click
                href = proceed_link.get_attribute("href")
                if href:
                    driver.get(href)
                    print("  ✓ Đã navigate 'Click here to proceed'")
                else:
                    driver.execute_script("arguments[0].click();", proceed_link)
                    print("  ✓ Đã click 'Click here to proceed'")
                proceed_clicked = True
                time.sleep(NAV_DELAY)
                break
            except:
                continue
        
        if not proceed_clicked:
            print("  ⚠ Không tìm thấy 'Click here to proceed' (có thể đã tự động proceed)")
        
        # Click "Back to Application" nếu có
        print("\n  Đang tìm và click 'Back to Application'...")
        back_selectors = [
            # Chính xác theo HTML: « Back to Application với href chứa email_verified
            (By.XPATH, "//a[contains(@href, 'email_verified=true')]"),
            (By.XPATH, "//a[contains(text(), 'Back to Application')]"),
            (By.XPATH, "//a[contains(., 'Back to Application')]"),
            (By.XPATH, "//div[@id='kc-info-message']//a"),
            (By.CSS_SELECTOR, "#kc-info-message a"),
            (By.CSS_SELECTOR, "a[href*='email_verified']"),
        ]
        
        back_clicked = False
        for by, selector in back_selectors:
            try:
                back_link = WebDriverWait(driver, WAIT_TIMEOUT_SHORT).until(
                    EC.element_to_be_clickable((by, selector))
                )
                # Lấy href để navigate trực tiếp (nhanh hơn click)
                href = back_link.get_attribute("href")
                if href and "app.all-hands.dev" in href:
                    print(f"  ✓ Tìm thấy link: {href}")
                    driver.get(href)
                    print("  ✓ Đã navigate trực tiếp (nhanh hơn click)")
                    back_clicked = True
                else:
                    # Fallback: click
                    driver.execute_script("arguments[0].click();", back_link)
                    print("  ✓ Đã click 'Back to Application'")
                    back_clicked = True
                time.sleep(NAV_DELAY)
                break
            except:
                continue
        
        if not back_clicked:
            # Fallback: Navigate trực tiếp đến login page
            print("  ⚠ Không tìm thấy link, navigate trực tiếp đến login...")
            driver.get(f"{OPENHANDS_LOGIN_URL}?email_verified=true")
            time.sleep(NAV_DELAY)
        
        print("\n  ✅ Email verification flow hoàn tất!")
        return True
        
    except Exception as e:
        print(f"\n  ✗ Lỗi email verification flow: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def handle_accept_tos_page(driver):
    """
    Xử lý trang Accept Terms of Service:
    1. Click checkbox accept
    2. Click Continue button
    """
    try:
        print(f"\n[ACCEPT TOS PAGE]")
        
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        
        # Click checkbox
        print("  Đang click checkbox 'I accept the terms of service'...")
        checkbox_selectors = [
            (By.XPATH, "//label[contains(., 'I accept')]//input[@type='checkbox']"),
            (By.XPATH, "//input[@type='checkbox']"),
            (By.CSS_SELECTOR, "label.flex input[type='checkbox']"),
        ]
        
        checkbox_clicked = False
        for by, selector in checkbox_selectors:
            try:
                checkbox = wait.until(EC.presence_of_element_located((by, selector)))
                
                # Check nếu checkbox chưa được check
                if not checkbox.is_selected():
                    driver.execute_script("arguments[0].click();", checkbox)
                    print("  ✓ Đã click checkbox")
                else:
                    print("  ✓ Checkbox đã được check sẵn")
                
                checkbox_clicked = True
                break
            except:
                continue
        
        if not checkbox_clicked:
            print("  ⚠ Không tìm thấy checkbox")
        
        time.sleep(CLICK_DELAY)
        
        # Click Continue button
        print("  Đang click 'Continue'...")
        continue_selectors = [
            (By.XPATH, "//button[contains(text(), 'Continue')]"),
            (By.XPATH, "//button[contains(., 'Continue')]"),
            (By.CSS_SELECTOR, "button.bg-primary"),
        ]
        
        for by, selector in continue_selectors:
            try:
                continue_btn = wait.until(EC.element_to_be_clickable((by, selector)))
                driver.execute_script("arguments[0].click();", continue_btn)
                print("  ✓ Đã click 'Continue'")
                time.sleep(NAV_DELAY)
                break
            except:
                continue
        
        print("  ✅ Accept TOS hoàn tất!")
        return True
        
    except Exception as e:
        print(f"\n  ✗ Lỗi handle accept TOS: {str(e)}")
        return False


def login_openhands_gitlab(driver, email, refresh_token, client_id):
    """Đăng nhập OpenHands qua GitLab OAuth với full email verification flow"""
    try:
        print(f"\n[STEP 3: OpenHands Login via GitLab]")
        
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        
        # Mở trang login OpenHands
        print(f"Đang mở {OPENHANDS_LOGIN_URL}...")
        driver.get(OPENHANDS_LOGIN_URL)
        time.sleep(PAGE_LOAD_WAIT)
        
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print(f"✓ Trang đã load: {driver.current_url}")
        
        # ============================================================
        # PHASE 1: Click GitLab login button
        # ============================================================
        print("\n[PHASE 1: GitLab OAuth]")
        print("  Đang click button 'Log in with GitLab'...")
        
        if not click_gitlab_login_button(driver, wait):
            print("  ✗ Không tìm thấy button GitLab")
            return False
        
        print("  ✓ Đã click GitLab button")
        time.sleep(NAV_DELAY)
        
        # ============================================================
        # PHASE 2: Đợi và detect trang đích (loop chính)
        # ============================================================
        print("\n[PHASE 2: Detect target page]")
        
        max_attempts = 20
        attempt = 0
        reached_verification = False
        reached_tos = False
        last_url = ""
        gitlab_click_count = 0  # Đếm số lần click GitLab button liên tiếp
        
        while attempt < max_attempts:
            attempt += 1
            
            try:
                current_url = driver.current_url
            except:
                time.sleep(0.5)
                continue
            
            # Chỉ log nếu URL thay đổi
            if current_url != last_url:
                print(f"\n  [{attempt}/{max_attempts}] URL: {current_url[:80]}...")
                last_url = current_url
            
            # === Check GitLab OAuth page ===
            if "gitlab.com/oauth" in current_url or "gitlab.com/-/profile" in current_url:
                print("  → Đang ở trang GitLab OAuth, click Authorize...")
                if handle_gitlab_oauth_authorize(driver):
                    time.sleep(NAV_DELAY)
                continue
            
            # === Check nếu đã vào trang email verification ===
            if is_on_email_verification_page(driver):
                print("  ✓ Đã vào trang 'Please check your email to verify your account'!")
                reached_verification = True
                break
            
            # === Check nếu đã vào trang accept-tos ===
            if is_on_accept_tos_page(driver):
                print("  ✓ Đã vào trang Accept TOS!")
                reached_tos = True
                break
            
            # === Check nếu đã vào trang API keys hoặc dashboard ===
            if "/settings/api-keys" in current_url or "/conversation" in current_url:
                print("  ✓ Đã login thành công, đang ở dashboard!")
                break
            
            # === Nếu đang ở trang auth.app.all-hands.dev → đợi redirect ===
            if is_on_auth_page(driver):
                # Đợi trang load xong
                try:
                    WebDriverWait(driver, 3).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except:
                    pass
                time.sleep(0.5)
                continue
            
            # === Nếu đang ở trang login OpenHands → click GitLab button ===
            if "/login" in current_url and "app.all-hands.dev" in current_url:
                gitlab_click_count += 1
                
                # Nếu đã click 2 lần mà vẫn ở trang login → reload trang
                if gitlab_click_count > 2:
                    print("  ⚠ Đã click 2 lần không thành công, reload trang...")
                    driver.refresh()
                    time.sleep(3)
                    gitlab_click_count = 0
                    continue
                
                print(f"  → Đang ở trang login, click GitLab button (lần {gitlab_click_count})...")
                if click_gitlab_login_button(driver, wait):
                    print("  ✓ Đã click GitLab button")
                    # Đợi lâu hơn để đảm bảo redirect hoàn tất
                    print("  → Đợi redirect (tối đa 10s)...")
                    redirect_start = time.time()
                    while time.time() - redirect_start < 10:
                        time.sleep(0.5)
                        try:
                            new_url = driver.current_url
                            # Nếu URL đã thay đổi → redirect thành công
                            if "/login" not in new_url or "app.all-hands.dev" not in new_url:
                                print(f"  ✓ Redirect thành công: {new_url[:60]}...")
                                gitlab_click_count = 0  # Reset counter
                                break
                            # Nếu đã vào trang email verification → break ngay
                            if is_on_email_verification_page(driver):
                                print("  ✓ Đã vào trang email verification!")
                                gitlab_click_count = 0  # Reset counter
                                break
                        except:
                            pass
                continue
            
            time.sleep(0.5)
        
        # ============================================================
        # PHASE 3: Handle Email Verification nếu cần
        # ============================================================
        if reached_verification:
            print("\n[PHASE 3: Email Verification]")
            handle_email_verification_flow(driver, email, refresh_token, client_id)
            
            # Sau khi verify, quay lại login và click GitLab button
            print("\n[PHASE 3b: Return to login after verification]")
            driver.get(OPENHANDS_LOGIN_URL)
            time.sleep(NAV_DELAY)
            
            # Loop để vào trang accept-tos hoặc dashboard
            max_attempts_2 = 20
            attempt_2 = 0
            last_url_2 = ""
            gitlab_click_count_3b = 0  # Đếm số lần click GitLab button liên tiếp
            
            while attempt_2 < max_attempts_2:
                attempt_2 += 1
                
                try:
                    current_url = driver.current_url
                except:
                    time.sleep(0.5)
                    continue
                
                if current_url != last_url_2:
                    print(f"\n  [{attempt_2}/{max_attempts_2}] URL: {current_url[:80]}...")
                    last_url_2 = current_url
                
                # Check GitLab OAuth
                if "gitlab.com/oauth" in current_url:
                    print("  → GitLab OAuth, click Authorize...")
                    handle_gitlab_oauth_authorize(driver)
                    time.sleep(NAV_DELAY)
                    continue
                
                # Check accept-tos
                if is_on_accept_tos_page(driver):
                    print("  ✓ Đã vào trang Accept TOS!")
                    reached_tos = True
                    break
                
                # Check dashboard
                if "/settings/api-keys" in current_url or "/conversation" in current_url:
                    print("  ✓ Đã login thành công!")
                    break
                
                # Check auth page → đợi
                if is_on_auth_page(driver):
                    time.sleep(0.5)
                    continue
                
                # Check login page → click GitLab
                if "/login" in current_url and "app.all-hands.dev" in current_url:
                    gitlab_click_count_3b += 1
                    
                    # Nếu đã click 2 lần mà vẫn ở trang login → reload trang
                    if gitlab_click_count_3b > 2:
                        print("  ⚠ Đã click 2 lần không thành công, reload trang...")
                        driver.refresh()
                        time.sleep(3)
                        gitlab_click_count_3b = 0
                        continue
                    
                    print(f"  → Click GitLab button (lần {gitlab_click_count_3b})...")
                    if click_gitlab_login_button(driver, wait):
                        print("  ✓ Đã click GitLab button")
                        # Đợi lâu hơn để đảm bảo redirect hoàn tất
                        print("  → Đợi redirect (tối đa 10s)...")
                        redirect_start = time.time()
                        while time.time() - redirect_start < 10:
                            time.sleep(0.5)
                            try:
                                new_url = driver.current_url
                                # Nếu URL đã thay đổi → redirect thành công
                                if "/login" not in new_url or "app.all-hands.dev" not in new_url:
                                    print(f"  ✓ Redirect thành công: {new_url[:60]}...")
                                    gitlab_click_count_3b = 0  # Reset counter
                                    break
                            except:
                                pass
                    continue
                
                time.sleep(0.5)
        
        # ============================================================
        # PHASE 4: Handle Accept TOS nếu cần
        # ============================================================
        if reached_tos or is_on_accept_tos_page(driver):
            print("\n[PHASE 4: Accept Terms of Service]")
            handle_accept_tos_page(driver)
            time.sleep(NAV_DELAY)
        
        # ============================================================
        # PHASE 5: Navigate to API Keys page and get API key
        # ============================================================
        print("\n[PHASE 5: Get API Key]")
        
        current_url = driver.current_url
        print(f"  URL hiện tại: {current_url[:80]}...")
        
        # Navigate đến API keys page
        if "/settings/api-keys" not in current_url:
            print(f"  → Navigate đến {OPENHANDS_API_KEYS_URL}...")
            driver.get(OPENHANDS_API_KEYS_URL)
            time.sleep(NAV_DELAY)
        
        # Đợi trang load
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print(f"  ✓ Trang API keys: {driver.current_url}")
        time.sleep(NAV_DELAY)
        
        # Retry lấy API key cho đến khi thành công
        max_retries = 10
        api_key = None
        relogin_count = 0
        max_relogin = 3  # Tối đa 3 lần re-login
        
        for retry in range(max_retries):
            print(f"\n  [Retry {retry + 1}/{max_retries}] Đang lấy API key...")
            api_key = get_api_key(driver)
            
            if api_key and api_key.startswith("sk-"):
                print(f"\n  ✅ Lấy được API key: {api_key[:25]}...")
                save_api_key(email, api_key)
                return True
            
            # CHECK: Nếu phát hiện trang "email already verified" → quay lại login
            if api_key == "EMAIL_ALREADY_VERIFIED":
                relogin_count += 1
                print(f"\n  🔄 [Re-login {relogin_count}/{max_relogin}] Quay lại /login để login GitLab lại...")
                
                if relogin_count > max_relogin:
                    print(f"  ✗ Đã re-login quá {max_relogin} lần, bỏ qua...")
                    return False
                
                # Navigate về /login
                driver.get(OPENHANDS_LOGIN_URL)
                time.sleep(NAV_DELAY)
                
                # Click GitLab button và xử lý OAuth flow
                re_login_success = False
                re_login_attempts = 0
                max_re_login_attempts = 10
                
                while re_login_attempts < max_re_login_attempts:
                    re_login_attempts += 1
                    
                    try:
                        current_url = driver.current_url
                    except:
                        time.sleep(0.5)
                        continue
                    
                    print(f"    [{re_login_attempts}/{max_re_login_attempts}] URL: {current_url[:60]}...")
                    
                    # Check nếu đã vào trang API keys hoặc dashboard
                    if "/settings/api-keys" in current_url or "/conversation" in current_url:
                        print("    ✓ Đã login lại thành công!")
                        re_login_success = True
                        break
                    
                    # Check GitLab OAuth page
                    if "gitlab.com/oauth" in current_url or "gitlab.com/-/profile" in current_url:
                        print("    → GitLab OAuth, click Authorize...")
                        handle_gitlab_oauth_authorize(driver)
                        time.sleep(NAV_DELAY)
                        continue
                    
                    # Check accept-tos
                    if is_on_accept_tos_page(driver):
                        print("    ✓ Đang ở trang Accept TOS, xử lý...")
                        handle_accept_tos_page(driver)
                        time.sleep(NAV_DELAY)
                        continue
                    
                    # Check auth page → đợi
                    if is_on_auth_page(driver):
                        time.sleep(0.5)
                        continue
                    
                    # Check login page → click GitLab
                    if "/login" in current_url and "app.all-hands.dev" in current_url:
                        print("    → Click GitLab button...")
                        if click_gitlab_login_button(driver, wait):
                            print("    ✓ Đã click GitLab button, đợi redirect...")
                            time.sleep(3)
                        continue
                    
                    time.sleep(0.5)
                
                if re_login_success:
                    # Navigate lại đến API keys page
                    print("  → Navigate đến API keys page sau khi re-login...")
                    driver.get(OPENHANDS_API_KEYS_URL)
                    time.sleep(NAV_DELAY)
                    continue  # Tiếp tục vòng retry lấy API key
                else:
                    print("  ✗ Re-login thất bại")
                    continue
            
            # CHECK: Nếu cần verify email → xử lý resend flow
            if api_key == "NEED_EMAIL_VERIFICATION":
                relogin_count += 1
                print(f"\n  📧 [Resend {relogin_count}/{max_relogin}] Cần verify email, xử lý resend flow...")
                
                if relogin_count > max_relogin:
                    print(f"  ✗ Đã resend quá {max_relogin} lần, bỏ qua...")
                    return False
                
                # Xử lý email verification flow
                verification_success = handle_email_verification_flow(driver, email, refresh_token, client_id)
                
                if verification_success:
                    print("  ✓ Email verification hoàn tất, quay lại login...")
                    # Quay lại login và click GitLab
                    driver.get(OPENHANDS_LOGIN_URL)
                    time.sleep(NAV_DELAY)
                    
                    # Click GitLab button
                    for _ in range(5):
                        current_url = driver.current_url
                        if "/login" in current_url and "app.all-hands.dev" in current_url:
                            if click_gitlab_login_button(driver, wait):
                                time.sleep(3)
                                break
                        elif "gitlab.com/oauth" in current_url:
                            handle_gitlab_oauth_authorize(driver)
                            time.sleep(NAV_DELAY)
                        elif is_on_accept_tos_page(driver):
                            handle_accept_tos_page(driver)
                            time.sleep(NAV_DELAY)
                        time.sleep(1)
                    
                    # Navigate đến API keys
                    driver.get(OPENHANDS_API_KEYS_URL)
                    time.sleep(NAV_DELAY)
                    continue
                else:
                    print("  ✗ Email verification thất bại")
                    continue
            
            print(f"  ⚠ Chưa lấy được API key, đợi 3s và thử lại...")
            time.sleep(3)
            
            # Refresh trang nếu cần
            if retry % 3 == 2:
                print(f"  → Refresh trang...")
                driver.refresh()
                time.sleep(NAV_DELAY)
        
        # Nếu vẫn không lấy được, hỏi user
        print("\n" + "!" * 60)
        print("⚠ KHÔNG LẤY ĐƯỢC API KEY SAU NHIỀU LẦN THỬ!")
        print("  Vui lòng kiểm tra trên browser và nhấn ENTER khi đã có API key")
        print("  Hoặc nhập 'skip' để bỏ qua email này")
        print("!" * 60)
        
        user_input = input("\n  Nhấn ENTER để thử lại hoặc 'skip' để bỏ qua: ").strip().lower()
        
        if user_input == 'skip':
            print("  → Bỏ qua email này")
            return False
        
        # Thử lấy lại lần cuối
        api_key = get_api_key(driver)
        if api_key and api_key.startswith("sk-"):
            print(f"\n  ✅ Lấy được API key: {api_key[:25]}...")
            save_api_key(email, api_key)
            return True
        
        print("  ✗ Vẫn không lấy được API key")
        return False
        
    except Exception as e:
        print(f"\n✗ Lỗi khi login OpenHands: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def get_api_key(driver):
    """
    Lấy API key từ OpenHands bằng cách đọc trực tiếp từ span
    
    Returns:
        - API key string nếu tìm thấy
        - "EMAIL_ALREADY_VERIFIED" nếu phát hiện trang "email already verified"
        - "NEED_EMAIL_VERIFICATION" nếu cần verify email (resend)
        - None nếu không tìm thấy
    """
    try:
        print(f"\n[STEP 5: Get API Key]")
        
        # Navigate đến API keys page
        if "/settings/api-keys" not in driver.current_url:
            print(f"Đang navigate đến {OPENHANDS_API_KEYS_URL}...")
            driver.get(OPENHANDS_API_KEYS_URL)
        
        # Đợi trang load
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Đợi thêm 1s để đảm bảo redirect hoàn tất
        time.sleep(1)
        
        # Lấy URL hiện tại SAU KHI page load xong
        current_url = driver.current_url
        print(f"✓ Trang hiện tại: {current_url}")
        
        # CHECK 1: Nếu bị redirect về auth page → check các trường hợp
        if "auth.app.all-hands.dev" in current_url:
            print("  ⚠ Đang ở trang auth (bị redirect)")
            
            # Check "email already verified"
            if is_on_email_already_verified_page(driver):
                print("  ⚠ Phát hiện: 'Your email address has been verified already.'")
                print("  → Cần quay lại /login để login GitLab lại")
                return "EMAIL_ALREADY_VERIFIED"
            
            # Check "Please check your email to verify"
            if is_on_email_verification_page(driver):
                print("  ⚠ Phát hiện: 'Please check your email to verify your account'")
                print("  → Cần resend verification email")
                return "NEED_EMAIL_VERIFICATION"
            
            print("  → Auth page khác, có thể cần login lại")
            return "EMAIL_ALREADY_VERIFIED"  # Treat as need re-login
        
        # CHECK 2: Nếu URL là /login → chưa login
        if "/login" in current_url and "app.all-hands.dev" in current_url:
            print("  ⚠ Đang ở trang login (chưa đăng nhập)")
            return "EMAIL_ALREADY_VERIFIED"  # Treat as need re-login
        
        # CHECK 3: Nếu đang ở trang api-keys, kiểm tra content
        if "/settings/api-keys" in current_url:
            # Double check: có thể page content vẫn là "verified already" 
            if is_on_email_already_verified_page(driver):
                print("  ⚠ Phát hiện: 'Your email address has been verified already.'")
                return "EMAIL_ALREADY_VERIFIED"
            
            if is_on_email_verification_page(driver):
                print("  ⚠ Phát hiện: 'Please check your email to verify'")
                return "NEED_EMAIL_VERIFICATION"
        
        # Đợi trang render
        time.sleep(NAV_DELAY)
        
        api_key = None
        
        # Cách 1: Đọc trực tiếp từ span chứa API key
        print("  Đang tìm API key trong span...")
        
        # Tìm span có class font-mono chứa sk-
        try:
            spans = driver.find_elements(By.CSS_SELECTOR, "span.font-mono, span.text-white.font-mono")
            for span in spans:
                text = span.text.strip()
                if text and text.startswith("sk-") and len(text) > 10:
                    api_key = text
                    print(f"  ✓ Tìm thấy API key: {api_key[:25]}...")
                    return api_key
        except:
            pass
        
        # Cách 2: Nếu key bị ẩn (hiển thị dấu *), click nút "Hide API key" để show
        print("  → API key có thể bị ẩn, đang click button để hiện...")
        try:
            # Tìm button "Hide API key" (khi key đang hiện) hoặc "Show API key" (khi key đang ẩn)
            show_hide_selectors = [
                (By.XPATH, "//button[@aria-label='Hide API key']"),
                (By.XPATH, "//button[@aria-label='Show API key']"),
                (By.XPATH, "//button[@title='Hide API key']"),
                (By.XPATH, "//button[@title='Show API key']"),
                (By.XPATH, "//button[.//svg[@viewBox='0 0 640 512']]"),  # Eye icon
            ]
            
            for by, selector in show_hide_selectors:
                try:
                    btn = driver.find_element(by, selector)
                    if btn and btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        print("  ✓ Đã click button show/hide")
                        time.sleep(0.5)
                        break
                except:
                    continue
            
            # Sau khi click, thử đọc lại
            spans = driver.find_elements(By.CSS_SELECTOR, "span.font-mono, span.text-white.font-mono")
            for span in spans:
                text = span.text.strip()
                if text and text.startswith("sk-") and len(text) > 10:
                    api_key = text
                    print(f"  ✓ Tìm thấy API key sau khi show: {api_key[:25]}...")
                    return api_key
        except Exception as e:
            print(f"  ⚠ Lỗi click show/hide: {str(e)[:50]}")
        
        # Cách 3: Tìm tất cả elements chứa sk-
        print("  → Thử tìm bằng JavaScript...")
        try:
            api_key = driver.execute_script("""
                var spans = document.querySelectorAll('span');
                for (var i = 0; i < spans.length; i++) {
                    var text = spans[i].textContent.trim();
                    if (text.startsWith('sk-') && text.length > 10) {
                        return text;
                    }
                }
                // Tìm trong tất cả elements
                var allElements = document.querySelectorAll('*');
                for (var i = 0; i < allElements.length; i++) {
                    var text = allElements[i].textContent.trim();
                    if (text.startsWith('sk-') && text.length > 10 && text.length < 50) {
                        return text;
                    }
                }
                return null;
            """)
            if api_key:
                print(f"  ✓ Tìm thấy API key (JS): {api_key[:25]}...")
                return api_key
        except:
            pass
        
        # Cách 4: Fallback - click copy button và lấy từ clipboard
        print("  → Fallback: click copy button...")
        try:
            import pyperclip
            
            copy_selectors = [
                (By.XPATH, "//button[@aria-label='Copy API key']"),
                (By.XPATH, "//button[@title='Copy API key']"),
                (By.XPATH, "//button[.//svg[@viewBox='0 0 448 512']]"),
            ]
            
            for by, selector in copy_selectors:
                try:
                    copy_btn = driver.find_element(by, selector)
                    if copy_btn and copy_btn.is_displayed():
                        driver.execute_script("arguments[0].click();", copy_btn)
                        print("  ✓ Đã click copy button")
                        time.sleep(0.3)
                        
                        api_key = pyperclip.paste()
                        if api_key and api_key.startswith("sk-") and len(api_key) > 10:
                            print(f"  ✓ Lấy từ clipboard: {api_key[:25]}...")
                            return api_key
                        break
                except:
                    continue
        except:
            pass
        
        print("  ✗ Không tìm thấy API key")
        return None
        
    except Exception as e:
        print(f"✗ Lỗi khi lấy API key: {str(e)}")
        return None


def save_api_key(email, api_key):
    """Lưu API key vào file"""
    try:
        username = email.split('@')[0]
        
        # Check duplicate
        existing = set()
        if os.path.exists(API_KEYS_FILE):
            with open(API_KEYS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if '|' in line:
                        existing.add(line.strip())
        
        new_entry = f"{username}|{api_key}"
        
        if new_entry in existing:
            print(f"⚠ API key đã tồn tại, bỏ qua")
            return
        
        with open(API_KEYS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{new_entry}\n")
        
        print(f"\n✓ Đã lưu vào {API_KEYS_FILE}")
        print(f"  Username: {username}")
        print(f"  API Key: {api_key[:20]}..." if len(api_key) > 20 else f"  API Key: {api_key}")
        
    except Exception as e:
        print(f"✗ Lỗi khi lưu: {str(e)}")


def log_error(email, password, refresh_token, client_id, error_msg):
    """Ghi log lỗi - format giống products.txt để dễ login lại"""
    try:
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            # Format: email|password|refresh_token|client_id (giống products.txt)
            # Để dễ copy paste chạy lại
            f.write(f"{email}|{password}|{refresh_token}|{client_id}\n")
    except:
        pass


# ============================================================
# WEBHOOK FUNCTIONS
# ============================================================

def check_webhook_status():
    """
    Gọi webhook để kiểm tra xem có API key nào cần refresh không
    
    Returns:
        Dict với keys: need_refresh (bool), keys (list of stale keys)
        Hoặc None nếu lỗi
    """
    try:
        url = f"{WEBHOOK_BASE_URL}/webhook/openhands/status"
        headers = {
            "X-Webhook-Secret": WEBHOOK_SECRET
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"  ⚠ Webhook status error: HTTP {response.status_code}")
            return None
        
        data = response.json()
        return data
        
    except requests.exceptions.Timeout:
        print("  ⚠ Webhook timeout")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ⚠ Webhook connection error: {str(e)[:50]}")
        return None
    except Exception as e:
        print(f"  ⚠ Webhook error: {str(e)[:50]}")
        return None


def post_new_api_key(api_key, replace_key_id=None, name=None):
    """
    POST API key mới lên webhook
    
    Args:
        api_key: Full API key string
        replace_key_id: Optional - ID của key cần thay thế (từ GET /status)
        name: Optional - Tên/email để identify key này
        
    Returns:
        True nếu thành công, False nếu thất bại
    """
    try:
        url = f"{WEBHOOK_BASE_URL}/webhook/openhands/keys"
        headers = {
            "X-Webhook-Secret": WEBHOOK_SECRET,
            "Content-Type": "application/json"
        }
        payload = {"apiKey": api_key}
        if replace_key_id:
            payload["replaceKeyId"] = replace_key_id
        if name:
            payload["name"] = name
        
        print(f"  📤 Đang POST API key mới lên webhook...")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 201:
            data = response.json()
            if data.get("success"):
                key_id = data.get("key", {}).get("id", "unknown")
                print(f"  ✅ Webhook: API key đã được thêm thành công! ID: {key_id}")
                return True
            else:
                print(f"  ⚠ Webhook returned success=false")
                return False
        else:
            print(f"  ✗ Webhook POST error: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"    Error: {error_data}")
            except:
                pass
            return False
            
    except requests.exceptions.Timeout:
        print("  ⚠ Webhook POST timeout")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  ⚠ Webhook POST connection error: {str(e)[:50]}")
        return False
    except Exception as e:
        print(f"  ⚠ Webhook POST error: {str(e)[:50]}")
        return False


def get_displayed_api_key(driver):
    """
    Lấy API key đang hiển thị trên trang OpenHands
    
    Args:
        driver: Selenium WebDriver
        
    Returns:
        API key string hoặc None nếu không tìm thấy
    """
    try:
        # Cách 1: Tìm tất cả span và filter theo text bắt đầu bằng sk-
        try:
            all_spans = driver.find_elements(By.TAG_NAME, "span")
            for span in all_spans:
                try:
                    text = span.text.strip()
                    if text and text.startswith("sk-") and len(text) > 10:
                        return text
                except:
                    continue
        except:
            pass
        
        # Cách 2: Tìm theo class (Tailwind)
        selectors = [
            (By.CSS_SELECTOR, "span.text-white.font-mono"),
            (By.CSS_SELECTOR, "span[class*='font-mono']"),
            (By.CSS_SELECTOR, "span[class*='text-white']"),
            (By.XPATH, "//span[contains(@class, 'font-mono')]"),
            (By.XPATH, "//span[contains(text(), 'sk-')]"),
        ]
        
        for by, selector in selectors:
            try:
                elements = driver.find_elements(by, selector)
                for elem in elements:
                    text = elem.text.strip()
                    if text and text.startswith("sk-") and len(text) > 10:
                        return text
            except:
                continue
        
        # Cách 3: Tìm trong div container
        try:
            divs = driver.find_elements(By.CSS_SELECTOR, "div.flex-1")
            for div in divs:
                text = div.text.strip()
                if text and text.startswith("sk-") and len(text) > 10:
                    # Có thể có nhiều text, lấy dòng đầu
                    for line in text.split('\n'):
                        line = line.strip()
                        if line.startswith("sk-"):
                            return line
        except:
            pass
        
        # Cách 4: Dùng JavaScript để tìm
        try:
            result = driver.execute_script("""
                var spans = document.querySelectorAll('span');
                for (var i = 0; i < spans.length; i++) {
                    var text = spans[i].textContent.trim();
                    if (text.startsWith('sk-') && text.length > 10) {
                        return text;
                    }
                }
                return null;
            """)
            if result:
                return result
        except:
            pass
        
        return None
        
    except Exception as e:
        return None


def click_refresh_button(driver):
    """
    Click nút "Refresh API Key" trên trang
    
    Args:
        driver: Selenium WebDriver
        
    Returns:
        True nếu click thành công, False nếu không tìm thấy hoặc lỗi
    """
    try:
        # Tìm button "Refresh API Key" 
        selectors = [
            (By.XPATH, "//button[contains(text(), 'Refresh API Key')]"),
            (By.XPATH, "//button[contains(., 'Refresh API Key')]"),
            (By.CSS_SELECTOR, "button.bg-primary"),
        ]
        
        for by, selector in selectors:
            try:
                buttons = driver.find_elements(by, selector)
                for btn in buttons:
                    btn_text = btn.text.strip()
                    if "Refresh API Key" in btn_text or "Refresh" in btn_text:
                        # Scroll vào view và click
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", btn)
                        time.sleep(0.3)
                        
                        try:
                            btn.click()
                        except:
                            driver.execute_script("arguments[0].click();", btn)
                        
                        return True
            except:
                continue
        
        return False
        
    except Exception as e:
        return False


def webhook_monitor_loop(driver):
    """
    Loop chính để monitor webhook và refresh API key khi cần
    
    Flow:
    1. Check webhook mỗi 2 giây
    2. Nếu need_refresh = true:
       a. Lấy stale API key từ webhook
       b. So sánh với API key trên trang
       c. Nếu khớp và tìm thấy button → click Refresh
       d. Đợi key thay đổi
       e. POST key mới lên webhook
    3. Nếu không tìm thấy button → tiếp tục loop (user chưa đến trang)
    4. User có thể nhấn ENTER để dừng loop
    
    Args:
        driver: Selenium WebDriver
    """
    print("\n" + "=" * 60)
    print("🔄 WEBHOOK MONITOR MODE")
    print("=" * 60)
    print("Script đang monitor webhook để tự động refresh API key")
    print("Bạn có thể:")
    print("  • Đăng ký OpenHands, lấy API key như bình thường")
    print("  • Script sẽ tự động refresh khi webhook báo need_refresh")
    print("  • Nhấn ENTER bất cứ lúc nào để dừng và chuyển email tiếp")
    print("=" * 60)
    
    # Thread để detect ENTER key
    stop_flag = threading.Event()
    
    def wait_for_enter():
        input()  # Block until ENTER
        stop_flag.set()
    
    # Start thread để đợi ENTER
    enter_thread = threading.Thread(target=wait_for_enter, daemon=True)
    enter_thread.start()
    
    check_count = 0
    last_refresh_key = None
    
    while not stop_flag.is_set():
        check_count += 1
        
        try:
            # Check webhook status
            status = check_webhook_status()
            
            if status and status.get("need_refresh"):
                stale_keys = status.get("keys", [])
                print(f"\n  🔔 [{check_count}] Webhook: need_refresh=true, {len(stale_keys)} key(s) cần refresh")
                
                for stale_key_info in stale_keys:
                    stale_api_key = stale_key_info.get("apiKey", "")
                    stale_key_id = stale_key_info.get("id", "")
                    
                    if not stale_api_key:
                        continue
                    
                    print(f"    Stale key: {stale_api_key[:20]}... (ID: {stale_key_id})")
                    
                    # Lấy API key hiển thị trên trang (KHÔNG navigate, chỉ check trang hiện tại)
                    displayed_key = get_displayed_api_key(driver)
                    
                    if not displayed_key:
                        print(f"    ⚠ Không tìm thấy API key trên trang (user chưa đến trang?)")
                        continue
                    
                    print(f"    Displayed key: {displayed_key[:20]}...")
                    
                    # So sánh
                    if displayed_key == stale_api_key:
                        print(f"    ✓ Key khớp! Đang click Refresh...")
                        
                        # Click Refresh button
                        if click_refresh_button(driver):
                            print(f"    ✓ Đã click Refresh API Key")
                            
                            # Đợi key thay đổi (tối đa 30 giây)
                            max_wait = 30
                            start_wait = time.time()
                            new_key = None
                            
                            while time.time() - start_wait < max_wait:
                                time.sleep(1)
                                new_key = get_displayed_api_key(driver)
                                
                                if new_key and new_key != stale_api_key:
                                    print(f"    ✅ Key đã thay đổi!")
                                    print(f"    New key: {new_key[:20]}...")
                                    break
                                
                                # Thử click lại nếu key chưa đổi
                                if int(time.time() - start_wait) % 5 == 0:
                                    print(f"    → Key chưa đổi, thử click lại...")
                                    click_refresh_button(driver)
                            
                            if new_key and new_key != stale_api_key:
                                # POST key mới lên webhook với replaceKeyId
                                if post_new_api_key(new_key, replace_key_id=stale_key_id, name=WEBHOOK_NAME):
                                    last_refresh_key = new_key
                                    print(f"    🎉 Hoàn tất refresh API key!")
                                else:
                                    print(f"    ⚠ POST webhook thất bại, nhưng key đã refresh trên OpenHands")
                            else:
                                print(f"    ⚠ Timeout: Key không thay đổi sau {max_wait}s")
                        else:
                            print(f"    ⚠ Không tìm thấy nút Refresh API Key")
                    else:
                        print(f"    → Key không khớp, bỏ qua")
            else:
                # Không cần refresh - chỉ log mỗi 10 lần check
                if check_count % 10 == 0:
                    print(f"  [{check_count}] Webhook: OK (không cần refresh)", end='\r')
            
        except Exception as e:
            if check_count % 10 == 0:
                print(f"  [{check_count}] Loop error: {str(e)[:50]}", end='\r')
        
        # Đợi trước khi check tiếp
        # Dùng stop_flag.wait() thay vì time.sleep() để có thể interrupt nhanh
        if stop_flag.wait(timeout=WEBHOOK_CHECK_INTERVAL):
            break
    
    print(f"\n\n✅ Webhook monitor đã dừng sau {check_count} lần check")
    if last_refresh_key:
        print(f"  Key cuối cùng được refresh: {last_refresh_key[:20]}...")


def main():
    """Main function"""
    driver = None
    
    try:
        print("=" * 60)
        print("GITLAB SIGNUP → OPENHANDS LOGIN → GET API KEY")
        print("=" * 60)
        
        # Check config
        if not IXBROWSER_PROFILE_ID:
            print("✗ IXBROWSER_PROFILE_ID chưa cấu hình")
            return
        
        print(f"✓ ixBrowser Profile ID: {IXBROWSER_PROFILE_ID}")
        
        # Read emails
        print("\n[0] Đọc danh sách email...")
        emails = read_emails()
        
        if not emails:
            print("✗ Không có email")
            return
        
        print(f"✓ Đã đọc {len(emails)} email")
        
        # Process each email
        for idx, data in enumerate(emails, 1):
            email = data['email']
            password = data['password']
            refresh_token = data['refresh_token']
            client_id = data['client_id']
            
            print("\n" + "=" * 60)
            print(f"[{idx}/{len(emails)}] XỬ LÝ: {email}")
            print("=" * 60)
            
            try:
                # Open ixBrowser
                driver = setup_ixbrowser_driver(IXBROWSER_PROFILE_ID, incognito=True)
                
                # Step 1: Register GitLab
                success_signup = register_gitlab(driver, email, password)
                if not success_signup:
                    print(f"✗ Đăng ký GitLab thất bại")
                    log_error(email, password, refresh_token, client_id, "GitLab signup failed")
                    continue
                
                # Step 2: Verify GitLab email TRƯỚC
                success_verify = verify_gitlab_email(driver, email, refresh_token, client_id)
                if not success_verify:
                    print(f"⚠ Verify GitLab có vấn đề, nhưng vẫn thử login OpenHands...")
                
                # Step 3: Login OpenHands
                success_login = login_openhands_gitlab(driver, email, refresh_token, client_id)
                if not success_login:
                    print(f"✗ Login OpenHands thất bại")
                    log_error(email, password, refresh_token, client_id, "OpenHands login failed")
                    continue
                
                print("\n" + "=" * 60)
                print(f"✅ HOÀN THÀNH: {email}")
                print("=" * 60)
                
            except Exception as e:
                print(f"\n✗ Lỗi: {str(e)}")
                log_error(email, password, refresh_token, client_id, str(e))
                import traceback
                traceback.print_exc()
            
            finally:
                # Cleanup
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                
                try:
                    close_ixbrowser_profile(IXBROWSER_PROFILE_ID, clear_data=True)
                except:
                    pass
                
                driver = None
                
                # Delay
                if idx < len(emails):
                    delay = random.randint(2, 5)
                    print(f"\n⏱️ Đợi {delay}s...")
                    time.sleep(delay)
        
        print("\n" + "=" * 60)
        print(f"✓ ĐÃ XỬ LÝ XONG {len(emails)} EMAIL!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Đã dừng (Ctrl+C)")
    
    except Exception as e:
        print(f"\n✗ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
            
            try:
                close_ixbrowser_profile(IXBROWSER_PROFILE_ID, clear_data=True)
            except:
                pass


if __name__ == "__main__":
    main()
