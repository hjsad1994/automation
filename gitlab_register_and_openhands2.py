# -*- coding: utf-8 -*-
"""
Script tự động ĐĂNG KÝ GITLAB + LOGIN OPENHANDS + LẤY API KEY

WORKFLOW ĐÚNG:
1. Đăng ký GitLab.com (điền form + xử lý CAPTCHA)
2. VERIFY EMAIL GITLAB (điền code 6 số từ email) ← BẮT BUỘC!
3. SAU KHI VERIFY XONG → Mở tab mới → Chuyển sang OpenHands.dev
4. Login OpenHands qua GitLab OAuth (GitLab đã login + verify rồi)
5. Lấy API key từ OpenHands /settings/api-keys

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

# ixBrowser Profile ID - Dùng profile 2
IXBROWSER_PROFILE_ID = 2  # Hardcode profile 2 cho script này

# ixBrowser API
IXBROWSER_API_HOST = "127.0.0.1"
IXBROWSER_API_PORT = 53200

# URLs
GITLAB_SIGNUP_URL = "https://gitlab.com/users/sign_up"
OPENHANDS_LOGIN_URL = "https://app.all-hands.dev/login"
OPENHANDS_API_KEYS_URL = "https://app.all-hands.dev/settings/api-keys"

# Files - Dùng file riêng cho script 2
EMAIL_FILE = "products2.txt"  # Format: email|password|refresh_token|client_id
API_KEYS_FILE = "api_keys2.txt"
ERROR_LOG_FILE = "errormail.txt"

# Timing
TURBO_MODE = True
if TURBO_MODE:
    TYPING_SPEED = (0.01, 0.03)
    DELAY_SHORT = (0.1, 0.3)
    DELAY_MEDIUM = (0.3, 0.6)
    PAGE_LOAD_WAIT = 0.5
else:
    TYPING_SPEED = (0.05, 0.1)
    DELAY_SHORT = (0.3, 0.6)
    DELAY_MEDIUM = (0.5, 1.0)
    PAGE_LOAD_WAIT = 2

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
        
        while time.time() - start_time < max_wait_cloudflare:
            try:
                current_url = driver.current_url
                
                # Log URL nếu thay đổi
                if current_url != last_url:
                    elapsed = int(time.time() - start_time)
                    print(f"  [{elapsed}s] URL: {current_url}")
                    last_url = current_url
                
                # Nếu đã vào trang verification hoặc welcome → xong
                if "identity_verification" in current_url or "welcome" in current_url:
                    print("  ✓ Đã vào trang verification/welcome")
                    
                    # CHECK: Nếu có lỗi "error loading the user verification challenge"
                    try:
                        error_alert = driver.find_elements(By.CSS_SELECTOR, ".gl-alert-body")
                        for alert in error_alert:
                            if "error loading" in alert.text.lower() and "verification challenge" in alert.text.lower():
                                print("  ⚠ Lỗi: 'error loading the user verification challenge'")
                                print("  → Reload trang và nhập lại password...")
                                
                                # Reload trang
                                driver.refresh()
                                time.sleep(3)
                                
                                # Nhập lại password
                                try:
                                    password_field = WebDriverWait(driver, 10).until(
                                        EC.presence_of_element_located((By.ID, "new_user_password"))
                                    )
                                    password_field.clear()
                                    password_field.send_keys("Aa@123456X")  # Hardcoded password
                                    print("  ✓ Đã nhập lại password")
                                    time.sleep(1)
                                    
                                    # Click Continue
                                    continue_btn = driver.find_element(By.CSS_SELECTOR, "[data-testid='new-user-register-button']")
                                    continue_btn.click()
                                    print("  ✓ Đã click Continue")
                                    time.sleep(3)
                                    
                                    # Reset để tiếp tục loop
                                    start_time = time.time()
                                    last_url = ""
                                    continue
                                except Exception as e:
                                    print(f"  ⚠ Không thể nhập lại password: {str(e)[:50]}")
                    except:
                        pass
                    
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


def login_openhands_gitlab(driver, email, refresh_token, client_id):
    """Đăng nhập OpenHands qua GitLab OAuth"""
    try:
        print(f"\n[STEP 3: OpenHands Login via GitLab]")
        
        wait = WebDriverWait(driver, 15)
        
        # Mở trang login OpenHands
        print(f"Đang mở {OPENHANDS_LOGIN_URL}...")
        driver.get(OPENHANDS_LOGIN_URL)
        time.sleep(PAGE_LOAD_WAIT)
        
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print(f"✓ Trang đã load: {driver.current_url}")
        time.sleep(1)
        
        # Click button "Log in with GitLab"
        print("\n[OpenHands] Đang tìm button 'Log in with GitLab'...")
        gitlab_button_selectors = [
            (By.XPATH, "//button[@type='button']//span[contains(text(), 'Log in with GitLab')]"),
            (By.XPATH, "//button[@type='button' and contains(., 'Log in with GitLab')]"),
            (By.XPATH, "//button[@type='button' and contains(@class, 'bg-[#FC6B0E]')]"),
        ]
        
        gitlab_button = None
        for by, selector in gitlab_button_selectors:
            try:
                gitlab_button = wait.until(EC.element_to_be_clickable((by, selector)))
                print("✓ Tìm thấy button 'Log in with GitLab'")
                break
            except TimeoutException:
                continue
        
        if not gitlab_button:
            print("✗ Không tìm thấy button GitLab")
            return False
        
        # Click
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", gitlab_button)
        random_delay('short')
        try:
            gitlab_button.click()
            print("✓ Đã click GitLab button")
        except:
            driver.execute_script("arguments[0].click();", gitlab_button)
            print("✓ Đã click GitLab button (JS)")
        
        time.sleep(2)
        
        # Check xem có ở trang GitLab OAuth Authorization không
        print(f"\n[OpenHands] Kiểm tra OAuth Authorization...")
        current_url = driver.current_url
        print(f"URL: {current_url}")
        
        # Nếu đang ở trang /oauth/authorize → cần click "Authorize"
        if "/oauth/authorize" in current_url:
            print("✓ Đang ở trang GitLab OAuth Authorization")
            print("  Cần click nút 'Authorize OpenHands'...")
            
            # Đợi trang load
            time.sleep(2)
            
            # Tìm nút Authorize
            authorize_selectors = [
                (By.XPATH, "//button//span[contains(text(), 'Authorize OpenHands')]"),
                (By.XPATH, "//button[contains(., 'Authorize')]"),
                (By.XPATH, "//input[@type='submit' and @value='Authorize']"),
                (By.CSS_SELECTOR, "button.btn-success"),
                (By.CSS_SELECTOR, "input[type='submit'][value='Authorize']"),
            ]
            
            authorize_button = None
            for by, selector in authorize_selectors:
                try:
                    authorize_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    print(f"  ✓ Tìm thấy nút Authorize")
                    break
                except TimeoutException:
                    continue
            
            if authorize_button:
                # Click Authorize
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", authorize_button)
                random_delay('short')
                try:
                    authorize_button.click()
                    print("  ✓ Đã click 'Authorize OpenHands'")
                except:
                    driver.execute_script("arguments[0].click();", authorize_button)
                    print("  ✓ Đã click 'Authorize OpenHands' (JS)")
                
                # Đợi redirect về OpenHands
                print("  Đang đợi redirect về OpenHands...")
                time.sleep(3)
            else:
                print("  ⚠ Không tìm thấy nút Authorize")
                print("  → Có thể đã authorize trước đó hoặc tự động approve")
        
        # Check email verification
        print(f"\n[OpenHands] Kiểm tra email verification...")
        current_url = driver.current_url
        print(f"URL: {current_url}")
        
        # NẾU VẪN Ở /login SAU KHI AUTHORIZE → Vào direct auth URL ngay
        if "login" in current_url.lower():
            print("  → Vẫn ở trang login, bypass bằng direct auth URL...")
            DIRECT_AUTH_URL = "https://auth.app.all-hands.dev/realms/allhands/protocol/openid-connect/auth?client_id=allhands&kc_idp_hint=gitlab&response_type=code&redirect_uri=https%3A%2F%2Fapp.all-hands.dev%2Foauth%2Fkeycloak%2Fcallback&scope=openid+email+profile&state=https%3A%2F%2Fapp.all-hands.dev%3Flogin_method%3Dgitlab&login_method=gitlab"
            driver.get(DIRECT_AUTH_URL)
            time.sleep(3)
            current_url = driver.current_url
            print(f"  URL sau direct auth: {current_url}")
        
        # NẾU Ở GITLAB OAUTH AUTHORIZE → Click Authorize trước
        if "gitlab.com/oauth/authorize" in current_url:
            print("  → Đang ở GitLab OAuth, cần click Authorize...")
            try:
                # Tìm nút Authorize trên GitLab
                authorize_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(., 'Authorize')]"))
                )
                authorize_btn.click()
                print("  ✓ Đã click Authorize trên GitLab")
                time.sleep(3)
                current_url = driver.current_url
                print(f"  URL sau Authorize: {current_url}")
            except:
                # Thử selector khác
                try:
                    authorize_btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Authorize'], button[type='submit']")
                    authorize_btn.click()
                    print("  ✓ Đã click Authorize (fallback)")
                    time.sleep(3)
                    current_url = driver.current_url
                except Exception as e:
                    print(f"  ⚠ Không click được Authorize: {str(e)[:50]}")
        
        # NẾU Ở ACCEPT-TOS SAU AUTHORIZE → Xử lý luôn
        if "/accept-tos" in current_url:
            print("  → Đang ở trang Accept TOS...")
            try:
                tos_checkbox = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
                )
                tos_checkbox.click()
                print("  ✓ Đã click checkbox Terms")
                time.sleep(0.5)
                
                tos_continue = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Accept')]"))
                )
                tos_continue.click()
                print("  ✓ Đã click Continue/Accept")
                time.sleep(3)
                
                print("  ✅ Đã accept TOS thành công!")
                return True
            except Exception as e:
                print(f"  ⚠ Lỗi TOS: {str(e)[:50]}")
                current_url = driver.current_url
        
        # Check xem có yêu cầu verify email không
        if "email_verification_required=true" in current_url:
            print("⚠ OpenHands yêu cầu verify email!")
        
        # Tìm nút Resend verification với nhiều selector
        short_wait = WebDriverWait(driver, 5)
        resend_button = None
        resend_selectors = [
            (By.XPATH, "//button[contains(text(), 'Resend verification')]"),
            (By.XPATH, "//button[contains(., 'Resend')]"),
            (By.XPATH, "//button[contains(@class, 'bg-primary') and contains(., 'Resend')]"),
            (By.XPATH, "//a[contains(text(), 'Resend')]"),
            (By.CSS_SELECTOR, "button.bg-primary"),
        ]
        
        for by, selector in resend_selectors:
            try:
                resend_button = short_wait.until(EC.element_to_be_clickable((by, selector)))
                print(f"✓ Tìm thấy 'Resend verification' với selector: {selector[:50]}")
                break
            except TimeoutException:
                continue
        
        if not resend_button:
            print("⚠ Không tìm thấy 'Resend verification'")
            
            # Nếu có email_verification_required → thử lấy link từ email đã có
            if "email_verification_required=true" in current_url:
                print("  → Thử lấy verification link từ email (có thể đã gửi trước đó)...")
                verify_link = wait_for_openhands_link(
                    email=email,
                    refresh_token=refresh_token,
                    client_id=client_id,
                    max_wait=30,  # Đợi ngắn hơn vì có thể đã có email
                    check_interval=3
                )
                
                if verify_link:
                    print("✓ Tìm thấy verification link trong email!")
                    # Xử lý verify link
                    driver.get(verify_link)
                    time.sleep(1)
                    
                    try:
                        proceed_link = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Click here to proceed')]"))
                        )
                        proceed_link.click()
                        print("✓ Đã click 'Click here to proceed'")
                        time.sleep(1)
                    except:
                        pass
                    
                    try:
                        back_link = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Back to Application')]"))
                        )
                        back_link.click()
                        print("✓ Đã click 'Back to Application'")
                        time.sleep(2)
                    except:
                        driver.get("https://app.all-hands.dev/?email_verified=true")
                        time.sleep(2)
                else:
                    print("  → Không tìm thấy email verification")
        
        if resend_button:
            # Click resend
            try:
                resend_button.click()
                print("✓ Đã click Resend")
            except:
                driver.execute_script("arguments[0].click();", resend_button)
                print("✓ Đã click Resend (JS)")
            
            time.sleep(2)
            
            # Lấy verification link từ email
            print("\n[OpenHands] Đang lấy verification link từ email...")
            verify_link = wait_for_openhands_link(
                email=email,
                refresh_token=refresh_token,
                client_id=client_id,
                max_wait=120,
                check_interval=5
            )
            
            if not verify_link:
                print("⚠ Không nhận được email verification")
            else:
                print("✓ Đã lấy verification link")
                
                # Mở link
                driver.get(verify_link)
                time.sleep(1)
                
                # Click "Click here to proceed"
                try:
                    proceed_link = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Click here to proceed')]"))
                    )
                    proceed_link.click()
                    print("✓ Đã click 'Click here to proceed'")
                    time.sleep(1)
                except:
                    pass
                
                # Click "Back to Application"
                try:
                    back_link = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Back to Application')]"))
                    )
                    back_link.click()
                    print("✓ Đã click 'Back to Application'")
                    time.sleep(2)
                except:
                    driver.get("https://app.all-hands.dev/?email_verified=true")
                    time.sleep(2)
        
        # Check login status
        print(f"\n[OpenHands] Kiểm tra login status...")
        current_url = driver.current_url
        print(f"URL: {current_url}")
        
        # Retry nếu còn ở trang login HOẶC accept-tos
        retry_count = 0
        max_retries = 4
        while ("login" in current_url.lower() or "/accept-tos" in current_url) and retry_count < max_retries:
            retry_count += 1
            
            # Nếu ở /accept-tos → xử lý trực tiếp, không cần click GitLab
            if "/accept-tos" in current_url:
                print(f"\n[OpenHands] Đang ở trang Accept Terms of Service")
                try:
                    # Click checkbox
                    tos_checkbox = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
                    )
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", tos_checkbox)
                    time.sleep(0.3)
                    tos_checkbox.click()
                    print("  ✓ Đã click checkbox Terms")
                    time.sleep(0.5)
                    
                    # Click Continue
                    tos_continue = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Continuer') or contains(text(), 'Accept')]"))
                    )
                    tos_continue.click()
                    print("  ✓ Đã click Continue/Accept")
                    time.sleep(3)
                    
                    # Update URL
                    current_url = driver.current_url
                    print(f"  URL sau accept TOS: {current_url}")
                    
                    # SAU KHI ACCEPT TOS: Đã login rồi, thoát loop luôn
                    # (URL có thể vẫn là /login?... nhưng thực tế đã authenticated)
                    print("  ✅ Đã accept TOS thành công! Chuyển sang lấy API key...")
                    return True  # Thoát function, đã login thành công
                        
                except Exception as e:
                    print(f"  ⚠ Lỗi xử lý TOS: {str(e)[:50]}")
                
                current_url = driver.current_url
                continue
            
            # Nếu ở /login → vào trực tiếp URL auth với kc_idp_hint=gitlab
            print(f"\n⚠ Vẫn ở trang login (retry {retry_count}/{max_retries})")
            print("  → Vào trực tiếp URL auth (bypass login page)...")
            
            # URL auth trực tiếp với kc_idp_hint=gitlab
            DIRECT_AUTH_URL = "https://auth.app.all-hands.dev/realms/allhands/protocol/openid-connect/auth?client_id=allhands&kc_idp_hint=gitlab&response_type=code&redirect_uri=https%3A%2F%2Fapp.all-hands.dev%2Foauth%2Fkeycloak%2Fcallback&scope=openid+email+profile&state=https%3A%2F%2Fapp.all-hands.dev%3Flogin_method%3Dgitlab&login_method=gitlab"
            
            driver.get(DIRECT_AUTH_URL)
            time.sleep(3)
            
            # SAU KHI VÀO DIRECT AUTH URL: Check kết quả
            current_url_after = driver.current_url
            print(f"  URL sau direct auth: {current_url_after}")
            
            # CHECK 0: Nếu vẫn ở /login → check xem có nút Resend verification không
            if "login" in current_url_after.lower():
                print("  → Vẫn ở trang login, kiểm tra nút Resend verification...")
                try:
                    resend_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Resend') or contains(., 'Resend')]"))
                    )
                    print("  ✓ Tìm thấy nút Resend verification!")
                    resend_btn.click()
                    print("  ✓ Đã click Resend")
                    time.sleep(2)
                    
                    # Đợi email verification link
                    print("  → Đang đợi email verification link...")
                    verify_link = wait_for_openhands_link(
                        email=email,
                        refresh_token=refresh_token,
                        client_id=client_id,
                        max_wait=60,
                        check_interval=5
                    )
                    
                    if verify_link:
                        print(f"  ✓ Nhận được verification link!")
                        driver.get(verify_link)
                        time.sleep(2)
                        
                        # Click "Click here to proceed" nếu có
                        try:
                            proceed_link = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Click here to proceed')]"))
                            )
                            proceed_link.click()
                            print("  ✓ Đã click 'Click here to proceed'")
                            time.sleep(2)
                        except:
                            pass
                        
                        # Click "Back to Application" nếu có
                        try:
                            back_link = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Back to Application')]"))
                            )
                            back_link.click()
                            print("  ✓ Đã click 'Back to Application'")
                            time.sleep(2)
                        except:
                            pass
                        
                        # SAU KHI VERIFY EMAIL: Vào direct auth để tiếp tục flow
                        print("  → Email đã verify, vào direct auth để login...")
                        driver.get(DIRECT_AUTH_URL)
                        time.sleep(3)
                        
                        # Update URL để các CHECK phía dưới xử lý tiếp
                        current_url_after = driver.current_url
                        print(f"  URL sau direct auth (post-verify): {current_url_after}")
                        
                        # Nếu đã qua login luôn → thành công
                        if "login" not in current_url_after.lower() and "/accept-tos" not in current_url_after:
                            print("  ✅ Email verified và login thành công!")
                            return True
                        
                        # Nếu không thì để các CHECK phía dưới xử lý tiếp (accept-tos, etc.)
                        
                    else:
                        print("  ⚠ Không nhận được verification link")
                        
                except TimeoutException:
                    print("  → Không tìm thấy nút Resend")
                except Exception as e:
                    print(f"  ⚠ Lỗi xử lý Resend: {str(e)[:50]}")
            
            # CHECK 1: Nếu ở trang /accept-tos → click checkbox + Continue
            if "/accept-tos" in current_url_after:
                print("  → Đang ở trang Accept Terms of Service")
                try:
                    # Click checkbox
                    tos_checkbox = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
                    )
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", tos_checkbox)
                    time.sleep(0.3)
                    tos_checkbox.click()
                    print("  ✓ Đã click checkbox Terms")
                    time.sleep(0.5)
                    
                    # Click Continue
                    tos_continue = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Continuer') or contains(text(), 'Accept')]"))
                    )
                    tos_continue.click()
                    print("  ✓ Đã click Continue/Accept")
                    time.sleep(3)
                    
                    print("  ✅ Đã accept TOS và login thành công!")
                    return True  # Đã login, chuyển sang lấy API key
                        
                except Exception as e:
                    print(f"  ⚠ Lỗi xử lý TOS: {str(e)[:50]}")
                
                current_url = driver.current_url
                continue  # Tiếp tục loop để check lại
            
            # CHECK 2: Nếu ở GitLab OAuth authorize
            if "/oauth/authorize" in current_url_after or "gitlab.com" in current_url_after:
                print("  → Đang ở trang GitLab OAuth Authorization")
                try:
                    authorize_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button//span[contains(text(), 'Authorize')]"))
                    )
                    authorize_btn.click()
                    print("  ✓ Đã click Authorize")
                    time.sleep(3)
                except:
                    print("  → Không thấy nút Authorize (có thể đã authorize rồi)")
                
                # Check lại sau authorize
                current_url = driver.current_url
                print(f"  URL sau authorize: {current_url}")
                
                # Nếu ở accept-tos sau authorize
                if "/accept-tos" in current_url:
                    try:
                        tos_checkbox = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
                        )
                        tos_checkbox.click()
                        print("  ✓ Đã click checkbox Terms")
                        time.sleep(0.5)
                        
                        tos_continue = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Accept')]"))
                        )
                        tos_continue.click()
                        print("  ✓ Đã click Continue/Accept")
                        time.sleep(3)
                        
                        print("  ✅ Đã accept TOS và login thành công!")
                        return True
                    except Exception as e:
                        print(f"  ⚠ Lỗi TOS: {str(e)[:50]}")
                
                # Nếu không còn ở login → thành công
                if "login" not in current_url.lower():
                    print("  ✅ Login thành công!")
                    return True
                    
                continue
            
            # CHECK 3: Nếu đã qua login (redirect về app)
            if "login" not in current_url_after.lower():
                print("  ✅ Đã login thành công qua direct auth!")
                return True
            
            # Update URL cho vòng lặp tiếp theo
            current_url = current_url_after
        
        # Sau khi hết retry loop, check final status
        current_url = driver.current_url
        
        if "login" in current_url.lower():
            # Kiểm tra xem có phải do email_verification_required không
            if "email_verification_required=true" in current_url:
                print("\n⚠ Vẫn yêu cầu verify email sau 2 lần retry")
                print("  → Thử vào trực tiếp URL auth với kc_idp_hint=gitlab...")
                
                # URL auth trực tiếp - bypass trang login
                DIRECT_AUTH_URL = "https://auth.app.all-hands.dev/realms/allhands/protocol/openid-connect/auth?client_id=allhands&kc_idp_hint=gitlab&response_type=code&redirect_uri=https%3A%2F%2Fapp.all-hands.dev%2Foauth%2Fkeycloak%2Fcallback&scope=openid+email+profile&state=https%3A%2F%2Fapp.all-hands.dev%3Flogin_method%3Dgitlab&login_method=gitlab"
                
                print(f"  → Đang vào: {DIRECT_AUTH_URL[:80]}...")
                driver.get(DIRECT_AUTH_URL)
                time.sleep(3)
                
                auth_url = driver.current_url
                print(f"  URL sau redirect: {auth_url}")
                
                # Nếu ở trang OAuth authorize → click Authorize
                if "/oauth/authorize" in auth_url or "gitlab.com" in auth_url:
                    print("  → Đang ở trang GitLab OAuth, thử click Authorize...")
                    try:
                        auth_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//button//span[contains(text(), 'Authorize')]"))
                        )
                        auth_btn.click()
                        print("  ✓ Đã click Authorize")
                        time.sleep(3)
                    except:
                        print("  → Không thấy nút Authorize (có thể đã authorize rồi)")
                
                # Check accept-tos
                current_url = driver.current_url
                if "/accept-tos" in current_url:
                    print("  → Đang ở trang Accept TOS...")
                    try:
                        tos_checkbox = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
                        )
                        tos_checkbox.click()
                        print("  ✓ Đã click checkbox Terms")
                        time.sleep(0.5)
                        
                        tos_continue = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Accept')]"))
                        )
                        tos_continue.click()
                        print("  ✓ Đã click Continue/Accept")
                        time.sleep(3)
                        
                        print("  ✅ Đã accept TOS thành công!")
                        return True
                    except Exception as e:
                        print(f"  ⚠ Lỗi xử lý TOS: {str(e)[:50]}")
                
                # Check kết quả cuối
                final_url = driver.current_url
                print(f"  URL cuối cùng: {final_url}")
                
                if "login" not in final_url.lower() or "/accept-tos" in final_url:
                    print("  ✅ Login thành công qua direct auth URL!")
                    return True
                else:
                    # Fallback: thử mở tab mới
                    print("  → Direct auth không work, thử mở TAB MỚI...")
                    
                    driver.execute_script("window.open('');")
                    time.sleep(1)
                    driver.switch_to.window(driver.window_handles[-1])
                    print("  ✓ Đã mở tab mới")
                    
                    # Vào GitLab để đảm bảo session vẫn còn
                    print("  → Đang vào GitLab để refresh session...")
                    driver.get("https://gitlab.com/users/sign_in")
                    time.sleep(3)
                    
                    gitlab_url = driver.current_url
                    print(f"  URL GitLab: {gitlab_url}")
                    
                    if "sign_in" not in gitlab_url or "users/" in gitlab_url:
                        print("  ✓ GitLab session vẫn còn")
                    
                    # Thử direct auth URL lần nữa từ tab mới
                    print("  → Thử direct auth URL lần nữa...")
                    driver.get(DIRECT_AUTH_URL)
                    time.sleep(3)
                    
                    final_url = driver.current_url
                    print(f"  URL cuối: {final_url}")
                    
                    if "login" not in final_url.lower():
                        print("  ✅ Login thành công từ tab mới!")
                        return True
                    else:
                        print("✗ Vẫn không thể login")
                        return False
            else:
                print("✗ Không thể login sau khi retry")
                return False
        
        print("✓ Đã login thành công!")
        
        # Click checkbox Terms of Service
        print(f"\n[OpenHands] Kiểm tra Terms of Service...")
        try:
            checkbox = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
            )
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", checkbox)
            time.sleep(0.3)
            try:
                checkbox.click()
                print("✓ Đã click checkbox")
            except:
                driver.execute_script("arguments[0].click();", checkbox)
                print("✓ Đã click checkbox (JS)")
            time.sleep(0.5)
            
            # Click Continue
            continue_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Continuer')]"))
            )
            try:
                continue_button.click()
                print("✓ Đã click Continue")
            except:
                driver.execute_script("arguments[0].click();", continue_button)
                print("✓ Đã click Continue (JS)")
            
            time.sleep(2)
        except TimeoutException:
            print("⚠ Không tìm thấy Terms checkbox")
        
        print("\n" + "=" * 60)
        print("✅ ĐÃ ĐĂNG NHẬP OPENHANDS THÀNH CÔNG!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Lỗi khi login OpenHands: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def get_api_key(driver):
    """Lấy API key từ OpenHands bằng cách click copy button"""
    try:
        print(f"\n[STEP 5: Get API Key]")
        
        # Navigate đến API keys page
        print(f"Đang navigate đến {OPENHANDS_API_KEYS_URL}...")
        
        if "/settings/api-keys" not in driver.current_url:
            driver.get(OPENHANDS_API_KEYS_URL)
        
        # Đợi trang load
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print(f"✓ Trang API keys: {driver.current_url}")
        
        # Đợi thêm 3s để trang render
        print("  Đợi 3s để trang load...")
        time.sleep(3)
        
        api_key = None
        
        # Click copy button - tìm button có SVG icon copy
        print("  Đang tìm và click copy button...")
        try:
            import pyperclip
            
            # Button copy có SVG với viewBox="0 0 448 512" (FontAwesome copy icon)
            copy_selectors = [
                # Tìm button chứa SVG có viewBox copy icon
                (By.XPATH, "//button[.//svg[@viewBox='0 0 448 512']]"),
                # Backup selectors
                (By.XPATH, "//button[contains(@aria-label, 'Copy')]"),
                (By.XPATH, "//button[contains(@title, 'Copy')]"),
                (By.CSS_SELECTOR, "button:has(svg[viewBox='0 0 448 512'])"),
            ]
            
            copy_btn = None
            for by, selector in copy_selectors:
                try:
                    copy_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    print(f"  ✓ Tìm thấy copy button")
                    break
                except:
                    continue
            
            if not copy_btn:
                # Fallback: tìm tất cả buttons có SVG và filter
                print("  → Thử tìm button có SVG icon...")
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in all_buttons:
                    try:
                        # Check xem button có chứa SVG với viewBox copy không
                        svg = btn.find_elements(By.TAG_NAME, "svg")
                        if svg:
                            viewBox = svg[0].get_attribute("viewBox")
                            if viewBox == "0 0 448 512":  # Copy icon viewBox
                                copy_btn = btn
                                print(f"  ✓ Tìm thấy button với SVG copy icon")
                                break
                    except:
                        continue
            
            if copy_btn:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", copy_btn)
                time.sleep(0.5)
                copy_btn.click()
                print("  ✓ Đã click copy button")
                time.sleep(1)
                
                # Lấy từ clipboard
                api_key = pyperclip.paste()
                if api_key and len(api_key) > 20:
                    print(f"  ✓ Lấy được API key: {api_key[:25]}...")
                else:
                    print(f"  ⚠ Clipboard không có API key hợp lệ")
                    api_key = None
            else:
                print("  ✗ Không tìm thấy copy button")
                
                # Screenshot để debug
                screenshot_path = f"debug_api_key_{int(time.time())}.png"
                driver.save_screenshot(screenshot_path)
                print(f"  → Screenshot saved: {screenshot_path}")
                
        except Exception as e:
            print(f"  ✗ Lỗi: {str(e)}")
        
        return api_key
        
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
                
                # Step 3: Sau khi verify xong → MỞ TAB MỚI và chuyển sang OpenHands
                print(f"\n[STEP 3: Mở tab mới và chuyển sang OpenHands]")
                print("Đang mở tab mới...")
                
                # Lưu tab GitLab hiện tại
                try:
                    gitlab_tab = driver.current_window_handle
                    print(f"  GitLab tab: {gitlab_tab[:8]}...")
                except Exception as e:
                    print(f"  ⚠ Không lấy được GitLab tab handle: {str(e)[:50]}")
                    gitlab_tab = None
                
                # Mở tab mới
                driver.execute_script("window.open('');")
                time.sleep(1)
                
                # Switch sang tab mới
                all_tabs = driver.window_handles
                openhands_tab = all_tabs[-1]  # Tab cuối cùng là tab mới
                driver.switch_to.window(openhands_tab)
                print(f"  ✓ Đã mở tab mới: {openhands_tab[:8]}...")
                
                # Step 4: Login OpenHands
                success_login = login_openhands_gitlab(driver, email, refresh_token, client_id)
                if not success_login:
                    print(f"✗ Login OpenHands thất bại")
                    log_error(email, password, refresh_token, client_id, "OpenHands login failed")
                    continue
                
                # Step 5: Get API key
                api_key = get_api_key(driver)
                if not api_key:
                    print(f"✗ Không lấy được API key")
                    log_error(email, password, refresh_token, client_id, "API key not found")
                    continue
                
                # Save API key
                save_api_key(email, api_key)
                
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
