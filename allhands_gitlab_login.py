"""
Script tự động ĐĂNG NHẬP GITLAB + LOGIN OPENHANDS + LẤY API KEY

WORKFLOW:
1. Mở ixBrowser profile (incognito)
2. Warmup Cloudflare tại GitLab /sign_in
3. ĐĂNG NHẬP GitLab (tài khoản đã có) - nhập email + password
4. VERIFY SMS/EMAIL code (nếu GitLab yêu cầu) - điền code 6 số từ email
5. Chuyển sang OpenHands.dev và login qua GitLab OAuth
6. Lấy API key từ OpenHands /settings/api-keys

QUAN TRỌNG: 
- Script này dùng cho tài khoản GitLab ĐÃ ĐĂNG KÝ SẴN
- GitLab có thể yêu cầu verify code sau khi đăng nhập
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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys

# Import email API helper
from email_api_helper import wait_for_openhands_link, wait_for_gitlab_verification_code

# Import ixBrowser Local API
try:
    from ixbrowser_local_api import IXBrowserClient
    IXBROWSER_AVAILABLE = True
    print("✓ ixbrowser-local-api có sẵn")
except ImportError:
    IXBROWSER_AVAILABLE = False
    print("⚠ ixbrowser-local-api chưa cài. Cài đặt: pip install ixbrowser-local-api")

import time
import os
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

# ixBrowser settings
USE_IXBROWSER = True
_ixbrowser_profile_id_str = os.getenv("IXBROWSER_PROFILE_ID", "")
IXBROWSER_PROFILE_ID = int(_ixbrowser_profile_id_str) if _ixbrowser_profile_id_str.isdigit() else None
IXBROWSER_API_HOST = "127.0.0.1"
IXBROWSER_API_PORT = 53200

# URLs
GITLAB_SIGNIN_URL = "https://gitlab.com/users/sign_in"
ALLHANDS_LOGIN_URL = "https://app.all-hands.dev/login"
ALLHANDS_API_KEYS_URL = "https://app.all-hands.dev/settings/api-keys"

# GitLab default password
GITLAB_DEFAULT_PASSWORD = "Aa@123456X"

# File paths
EMAIL_FILE = "errormail.txt"  # Format: email|password|refresh_token|client_id
API_KEYS_FILE = "api_keys.txt"
ERROR_LOG_FILE = "errormail_failed.txt"

# Timing settings
TURBO_MODE = True

if TURBO_MODE:
    print("🚀 TURBO MODE: BẬT")
    DELAY_SHORT = (0.01, 0.03)
    DELAY_MEDIUM = (0.03, 0.08)
    DELAY_LONG = (0.1, 0.2)
    PAGE_LOAD_WAIT = 0.1
else:
    print("🐢 TURBO MODE: TẮT")
    DELAY_SHORT = (0.3, 0.6)
    DELAY_MEDIUM = (0.5, 1.0)
    DELAY_LONG = (1.5, 2.5)
    PAGE_LOAD_WAIT = 2

# Window position
WINDOW_LEFT_HALF = True

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def random_delay(min_sec=None, max_sec=None, delay_type='short'):
    """Random delay với preset"""
    if min_sec is None or max_sec is None:
        if delay_type == 'short':
            min_sec, max_sec = DELAY_SHORT
        elif delay_type == 'medium':
            min_sec, max_sec = DELAY_MEDIUM
        elif delay_type == 'long':
            min_sec, max_sec = DELAY_LONG
    
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

def set_window_position(driver):
    """Set window position và size"""
    try:
        if WINDOW_LEFT_HALF:
            screen_width = driver.execute_script("return window.screen.availWidth")
            screen_height = driver.execute_script("return window.screen.availHeight")
            window_width = screen_width // 2
            window_height = screen_height // 2
            driver.set_window_position(screen_width // 2, 0)
            driver.set_window_size(window_width, window_height)
            print(f"✓ Window: 1/4 màn hình góc trên phải ({window_width}x{window_height})")
        else:
            driver.maximize_window()
            print("✓ Window: Full screen")
    except Exception as e:
        print(f"⚠ Lỗi set window position: {str(e)}")
        try:
            driver.maximize_window()
        except:
            pass

# ============================================================
# IXBROWSER FUNCTIONS
# ============================================================

IXBROWSER_CLIENT = None

def setup_ixbrowser_driver(profile_id=None, incognito=True):
    """
    Setup WebDriver qua ixBrowser profile
    Proxy và fingerprint đã được cấu hình trong ixBrowser app
    """
    global IXBROWSER_CLIENT
    
    if not IXBROWSER_AVAILABLE:
        raise Exception("ixbrowser-local-api chưa được cài đặt")
    
    if profile_id is None:
        profile_id = IXBROWSER_PROFILE_ID
    
    if not profile_id:
        raise Exception("IXBROWSER_PROFILE_ID chưa được cấu hình trong .env")
    
    print(f"\n[ixBrowser] Đang kết nối đến ixBrowser Local API...")
    print(f"[ixBrowser] Profile ID: {profile_id}")
    print(f"[ixBrowser] Incognito Mode: {'BẬT' if incognito else 'TẮT'}")
    
    # Khởi tạo client
    try:
        IXBROWSER_CLIENT = IXBrowserClient(target=IXBROWSER_API_HOST, port=IXBROWSER_API_PORT)
        print("✓ Đã kết nối đến ixBrowser Local API")
    except Exception as e:
        raise Exception(f"Không thể kết nối đến ixBrowser Local API: {str(e)}")
    
    # Startup arguments
    startup_args = []
    if incognito:
        startup_args.append("--incognito")
        print("[ixBrowser] Đang mở ở chế độ ẨN DANH...")
    
    # Mở profile
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
        error_msg = f"Không thể mở profile. Code: {IXBROWSER_CLIENT.code}, Message: {IXBROWSER_CLIENT.message}"
        raise Exception(error_msg)
    
    # Lấy thông tin kết nối
    webdriver_path = open_result.get('webdriver')
    debugging_address = open_result.get('debugging_address')
    
    if not webdriver_path or not debugging_address:
        raise Exception(f"open_profile() không trả về đủ thông tin")
    
    print(f"✓ Profile đã mở thành công")
    print(f"  Debugging Address: {debugging_address}")
    
    # Kết nối Selenium
    print(f"[ixBrowser] Đang kết nối Selenium...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", debugging_address)
    
    try:
        driver = webdriver.Chrome(service=Service(webdriver_path), options=chrome_options)
        print("✓ Selenium đã kết nối thành công")
    except Exception as e:
        print(f"⚠ Không thể dùng webdriver từ ixBrowser, thử fallback...")
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✓ Selenium đã kết nối bằng ChromeDriverManager")
        except Exception as e2:
            raise Exception(f"Không thể kết nối Selenium: {str(e2)}")
    
    return driver

def close_ixbrowser_profile(profile_id=None, clear_data=True):
    """Đóng ixBrowser profile và clear cookies/cache"""
    global IXBROWSER_CLIENT
    
    if IXBROWSER_CLIENT is None:
        print("⚠ ixBrowser client chưa được khởi tạo")
        return False
    
    if profile_id is None:
        profile_id = IXBROWSER_PROFILE_ID
    
    if not profile_id:
        print("⚠ Không có profile_id để đóng")
        return False
    
    # Clear cookies và cache
    if clear_data:
        print(f"[ixBrowser] Đang clear cookies và cache...")
        try:
            clear_result = IXBROWSER_CLIENT.clear_profile_cache_and_cookies(profile_id)
            if clear_result:
                print("✓ Đã clear cookies và cache")
            else:
                print(f"⚠ Lỗi clear: Code={IXBROWSER_CLIENT.code}")
        except Exception as e:
            print(f"⚠ Lỗi khi clear data: {str(e)}")
    
    # Đóng profile
    print(f"[ixBrowser] Đang đóng profile {profile_id}...")
    try:
        close_result = IXBROWSER_CLIENT.close_profile(profile_id)
        if close_result is None:
            print(f"⚠ Lỗi khi đóng profile: Code={IXBROWSER_CLIENT.code}")
            return False
        
        print("✓ Đã đóng ixBrowser profile")
        return True
    except Exception as e:
        print(f"✗ Exception khi đóng profile: {str(e)}")
        return False

# ============================================================
# EMAIL READING
# ============================================================

def read_all_emails(email_file=EMAIL_FILE):
    """
    Đọc tất cả email từ file
    Format: email|password|refresh_token|client_id
    """
    try:
        if not os.path.exists(email_file):
            print(f"✗ Không tìm thấy file {email_file}")
            return []
        
        with open(email_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        if not lines:
            print(f"✗ File {email_file} rỗng")
            return []
        
        emails = []
        for idx, line in enumerate(lines, 1):
            if '|' not in line:
                print(f"⚠ Dòng {idx}: Bỏ qua - không có dấu |")
                continue
            
            parts = line.split('|')
            if len(parts) < 4:
                print(f"✗ Dòng {idx}: Bỏ qua - thiếu fields (cần 4, có {len(parts)})")
                continue
            
            email = parts[0].strip()
            password = parts[1].strip()
            refresh_token = parts[2].strip()
            client_id = parts[3].strip()
            
            if not email or not password or not refresh_token or not client_id:
                print(f"✗ Dòng {idx}: Bỏ qua - có field rỗng")
                continue
            
            emails.append((email, password, refresh_token, client_id))
        
        return emails
    
    except Exception as e:
        print(f"✗ Lỗi khi đọc file {email_file}: {str(e)}")
        return []

# ============================================================
# GITLAB SIGNIN FUNCTION
# ============================================================

def signin_gitlab(driver, email, password, refresh_token, client_id):
    """
    Đăng nhập vào GitLab với tài khoản đã có
    
    Flow:
    1. Warmup - vào /sign_in để bypass Cloudflare
    2. Điền email + password vào form login
    3. Submit và đợi redirect
    4. Nếu cần SMS/Email verification → lấy code từ email API và điền
    5. Sau khi đăng nhập xong → sẵn sàng cho OpenHands OAuth
    
    Returns:
        bool: True nếu đăng nhập thành công, False nếu thất bại
    """
    try:
        print("\n" + "="*60)
        print("🔐 ĐĂNG NHẬP GITLAB")
        print("="*60)
        
        wait = WebDriverWait(driver, 15)
        
        # ============================================================
        # BƯỚC 1: WARMUP - Bypass Cloudflare
        # ============================================================
        print(f"\n[GitLab 1/4] Warmup - Bypass Cloudflare...")
        print(f"  Đang mở {GITLAB_SIGNIN_URL}...")
        driver.get(GITLAB_SIGNIN_URL)
        time.sleep(3)
        
        # Đợi Cloudflare xử lý
        max_cf_wait = 30
        cf_start = time.time()
        while time.time() - cf_start < max_cf_wait:
            current_url = driver.current_url
            
            # Kiểm tra xem đã load được form login chưa
            try:
                login_field = driver.find_elements(By.ID, "user_login")
                if login_field:
                    print("  ✓ Cloudflare passed! Form login đã load")
                    break
            except:
                pass
            
            # Thử click Cloudflare checkbox nếu có
            try:
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                for iframe in iframes:
                    src = iframe.get_attribute("src") or ""
                    if "challenge" in src.lower() or "turnstile" in src.lower():
                        print("  → Phát hiện Cloudflare challenge, đang click...")
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
        
        # ============================================================
        # BƯỚC 2: ĐIỀN FORM LOGIN
        # ============================================================
        print(f"\n[GitLab 2/4] Điền form đăng nhập...")
        
        # Đợi form load
        try:
            email_field = wait.until(EC.presence_of_element_located((By.ID, "user_login")))
            print("  ✓ Form login đã sẵn sàng")
        except TimeoutException:
            print("  ✗ Không tìm thấy form login sau 15s")
            return False
        
        # Điền email
        print(f"  Đang điền email: {email}")
        email_field.clear()
        for char in email:
            email_field.send_keys(char)
            time.sleep(random.uniform(0.01, 0.03) if TURBO_MODE else random.uniform(0.05, 0.1))
        time.sleep(0.3)
        
        # Điền password
        print(f"  Đang điền password...")
        password_field = driver.find_element(By.ID, "user_password")
        password_field.clear()
        for char in password:
            password_field.send_keys(char)
            time.sleep(random.uniform(0.01, 0.03) if TURBO_MODE else random.uniform(0.05, 0.1))
        time.sleep(0.3)
        
        print("  ✓ Đã điền xong form")
        
        # ============================================================
        # BƯỚC 3: CLICK SIGN IN
        # ============================================================
        print(f"\n[GitLab 3/4] Click nút Sign in...")
        
        # Tìm nút Sign in
        signin_button_selectors = [
            (By.CSS_SELECTOR, "[data-testid='sign-in-button']"),
            (By.XPATH, "//button[@type='submit' and contains(., 'Sign in')]"),
            (By.XPATH, "//button[@type='submit']"),
        ]
        
        signin_button = None
        for by, selector in signin_button_selectors:
            try:
                signin_button = driver.find_element(by, selector)
                if signin_button.is_displayed():
                    break
            except:
                continue
        
        if not signin_button:
            print("  ✗ Không tìm thấy nút Sign in")
            return False
        
        # Click
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", signin_button)
        time.sleep(0.3)
        try:
            signin_button.click()
            print("  ✓ Đã click Sign in")
        except:
            driver.execute_script("arguments[0].click();", signin_button)
            print("  ✓ Đã click Sign in (JS)")
        
        # Đợi redirect
        print("  Đang đợi GitLab xử lý...")
        time.sleep(3)
        
        # ============================================================
        # BƯỚC 4: XỬ LÝ VERIFICATION (NẾU CÓ)
        # ============================================================
        print(f"\n[GitLab 4/4] Kiểm tra verification...")
        current_url = driver.current_url
        print(f"  URL hiện tại: {current_url}")
        
        # Kiểm tra có cần verification không - check cả URL và element trên trang
        needs_verification = False
        
        # Check URL
        if "identity_verification" in current_url or "verification" in current_url.lower():
            needs_verification = True
        
        # Check xem có input verification-code trên trang không
        try:
            code_input_check = driver.find_elements(By.ID, "verification-code")
            if code_input_check:
                needs_verification = True
                print("  → Phát hiện form verification code trên trang!")
        except:
            pass
        
        if needs_verification:
            print("  → GitLab yêu cầu verification code!")
            
            # Lấy code từ email API
            print("  🔍 Đang lấy verification code từ email...")
            verification_code = wait_for_gitlab_verification_code(
                email=email,
                refresh_token=refresh_token,
                client_id=client_id,
                max_wait=120,
                check_interval=5
            )
            
            if not verification_code:
                print("  ⚠ Không tìm thấy code trong 120s")
                print("  → Đợi 60s để bạn nhập code thủ công...")
                time.sleep(60)
            else:
                print(f"  ✓ Tìm thấy code: {verification_code}")
                
                # Điền code
                try:
                    # Selector đúng: #verification-code (có dấu gạch ngang)
                    code_input = wait.until(EC.presence_of_element_located((By.ID, "verification-code")))
                    code_input.clear()
                    code_input.send_keys(verification_code)
                    print(f"  ✓ Đã điền code")
                    time.sleep(0.5)
                    
                    # Click Verify code button
                    verify_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    verify_button.click()
                    print("  ✓ Đã click Verify code")
                    time.sleep(3)
                except Exception as e:
                    print(f"  ⚠ Lỗi điền code: {str(e)[:50]}")
            
            # Check kết quả
            current_url = driver.current_url
            print(f"  URL sau verify: {current_url}")
        
        # Kiểm tra đã đăng nhập thành công chưa
        # Nếu còn ở /sign_in với error → thất bại
        if "/sign_in" in current_url:
            # Check error message
            try:
                error_msgs = driver.find_elements(By.CSS_SELECTOR, ".flash-alert, .alert-danger, [data-testid='alert-danger']")
                for msg in error_msgs:
                    if msg.is_displayed():
                        print(f"  ✗ Lỗi đăng nhập: {msg.text}")
                        return False
            except:
                pass
        
        # Nếu URL không còn /sign_in hoặc có /users hoặc dashboard → thành công
        if "/sign_in" not in current_url or "users" in current_url or "dashboard" in current_url:
            print("\n" + "="*60)
            print("✅ ĐĂNG NHẬP GITLAB THÀNH CÔNG!")
            print("="*60)
            return True
        
        # Nếu vẫn còn ở sign_in nhưng không có error → có thể cần thêm xử lý
        print("  ⚠ Không rõ trạng thái đăng nhập, tiếp tục...")
        return True
        
    except Exception as e:
        print(f"\n✗ Lỗi khi đăng nhập GitLab: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# MAIN LOGIN FUNCTION
# ============================================================

def login_allhands_gitlab(driver, email, password, refresh_token, client_id, max_retries=3):
    """
    Đăng nhập vào All-Hands.dev qua GitLab OAuth
    
    Flow đúng:
    1. Mở trang /login → Click "Log in with GitLab"
    2. Nếu OAuth Authorization → Click Authorize → redirect về /login
    3. Nếu cần verify email → Click Resend → verify → redirect về /login  
    4. Sau khi về /login → Click GitLab lại
    5. Nếu /accept-tos → Click checkbox + Continue
    6. Lấy API key từ /settings/api-keys
    """
    try:
        print("\n" + "="*60)
        print("🔐 ĐĂNG NHẬP ALL-HANDS.DEV QUA GITLAB")
        print("="*60)
        
        wait = WebDriverWait(driver, 10 if TURBO_MODE else 20)
        short_wait = WebDriverWait(driver, 5)
        
        def click_gitlab_button():
            """Helper: Tìm và click button Log in with GitLab"""
            gitlab_selectors = [
                (By.XPATH, "//button[@type='button']//span[contains(text(), 'Log in with GitLab')]"),
                (By.XPATH, "//button[@type='button' and contains(., 'Log in with GitLab')]"),
                (By.XPATH, "//button[contains(@class, 'bg-[#FC6B0E]')]"),
            ]
            for by, selector in gitlab_selectors:
                try:
                    btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, selector)))
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
        
        def handle_accept_tos():
            """Helper: Xử lý trang accept-tos"""
            try:
                checkbox = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='checkbox']"))
                )
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", checkbox)
                time.sleep(0.3)
                try:
                    checkbox.click()
                except:
                    driver.execute_script("arguments[0].click();", checkbox)
                print("  ✓ Đã click checkbox Terms of Service")
                time.sleep(0.5)
                
                # Click Continue
                continue_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Accept')]"))
                )
                try:
                    continue_btn.click()
                except:
                    driver.execute_script("arguments[0].click();", continue_btn)
                print("  ✓ Đã click Continue")
                time.sleep(2)
                return True
            except Exception as e:
                print(f"  ⚠ Lỗi xử lý TOS: {str(e)[:50]}")
                return False
        
        def handle_oauth_authorize():
            """Helper: Xử lý trang GitLab OAuth Authorize"""
            try:
                # Tìm nút Authorize
                auth_selectors = [
                    (By.XPATH, "//button[@type='submit' and contains(., 'Authorize')]"),
                    (By.XPATH, "//input[@type='submit' and @value='Authorize']"),
                    (By.CSS_SELECTOR, "button.btn-success"),
                ]
                for by, selector in auth_selectors:
                    try:
                        auth_btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, selector)))
                        auth_btn.click()
                        print("  ✓ Đã click Authorize")
                        time.sleep(2)
                        return True
                    except:
                        continue
                return False
            except:
                return False
        
        # ============================================================
        # BƯỚC 1: MỞ TRANG LOGIN
        # ============================================================
        print(f"\n[Step 1] Mở trang login...")
        driver.get(ALLHANDS_LOGIN_URL)
        time.sleep(PAGE_LOAD_WAIT)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print(f"✓ Đã mở: {driver.current_url}")
        time.sleep(1)
        
        # ============================================================
        # BƯỚC 2: CLICK GITLAB BUTTON
        # ============================================================
        print(f"\n[Step 2] Click 'Log in with GitLab'...")
        if not click_gitlab_button():
            print("✗ Không tìm thấy button GitLab")
            return False
        print("✓ Đã click GitLab button")
        time.sleep(2)
        
        # ============================================================
        # MAIN LOOP: XỬ LÝ CÁC TRẠNG THÁI
        # ============================================================
        for attempt in range(max_retries + 1):
            current_url = driver.current_url
            print(f"\n[Check] URL: {current_url}")
            
            # CASE 1: Đã vào dashboard/settings → THÀNH CÔNG
            if "/settings" in current_url or ("app.all-hands.dev" in current_url and "/login" not in current_url and "/accept-tos" not in current_url):
                if "oauth" not in current_url and "auth" not in current_url:
                    print("✓ Đã login thành công!")
                    break
            
            # CASE 2: Trang accept-tos → Click checkbox + Continue
            if "/accept-tos" in current_url:
                print("→ Đang ở trang Accept Terms of Service...")
                if handle_accept_tos():
                    print("✓ Đã accept TOS")
                    time.sleep(2)
                    continue
            
            # CASE 3: GitLab OAuth Authorize → Click Authorize
            if "gitlab.com/oauth/authorize" in current_url:
                print("→ Đang ở trang GitLab OAuth Authorization...")
                handle_oauth_authorize()
                time.sleep(2)
                continue
            
            # CASE 3.5: GitLab Sign In page → Đăng nhập GitLab
            if "gitlab.com/users/sign_in" in current_url or "gitlab.com" in current_url and "sign_in" in current_url:
                print("→ Đang ở trang GitLab Sign In, cần đăng nhập...")
                try:
                    # Điền email
                    email_field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "user_login"))
                    )
                    email_field.clear()
                    email_field.send_keys(email)
                    print(f"  ✓ Đã điền email: {email}")
                    time.sleep(0.3)
                    
                    # Điền password - SỬ DỤNG MẬT KHẨU MẶC ĐỊNH
                    password_field = driver.find_element(By.ID, "user_password")
                    password_field.clear()
                    password_field.send_keys(GITLAB_DEFAULT_PASSWORD)
                    print(f"  ✓ Đã điền password: {GITLAB_DEFAULT_PASSWORD}")
                    time.sleep(0.3)
                    
                    # Click Sign in
                    signin_btn = driver.find_element(By.CSS_SELECTOR, "[data-testid='sign-in-button'], button[type='submit']")
                    signin_btn.click()
                    print("  ✓ Đã click Sign in")
                    time.sleep(3)
                except Exception as e:
                    print(f"  ⚠ Lỗi đăng nhập GitLab: {str(e)[:50]}")
                continue
            
            # CASE 3.6: GitLab Verification page (sau khi login) → Click Resend code trước, rồi lấy code mới
            # Check bằng element #verification-code thay vì URL
            try:
                code_input_check = driver.find_elements(By.ID, "verification-code")
                if code_input_check and "gitlab.com" in current_url:
                    print("→ GitLab yêu cầu verification code...")
                    
                    # QUAN TRỌNG: Click "Resend code" trước để có code mới nhất
                    try:
                        resend_code_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Resend code')]"))
                        )
                        resend_code_btn.click()
                        print("  ✓ Đã click 'Resend code'")
                        time.sleep(2)
                    except:
                        print("  ⚠ Không tìm thấy nút 'Resend code', lấy code có sẵn...")
                    
                    # Lấy code MỚI NHẤT từ email
                    print("  🔍 Đang lấy verification code từ email...")
                    verification_code = wait_for_gitlab_verification_code(
                        email=email,
                        refresh_token=refresh_token,
                        client_id=client_id,
                        max_wait=120,
                        check_interval=5
                    )
                    
                    if verification_code:
                        print(f"  ✓ Tìm thấy code: {verification_code}")
                        code_input = driver.find_element(By.ID, "verification-code")
                        code_input.clear()
                        code_input.send_keys(verification_code)
                        time.sleep(0.5)
                        
                        # Click Verify code
                        verify_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                        verify_btn.click()
                        print("  ✓ Đã click Verify code")
                        time.sleep(3)
                    else:
                        print("  ⚠ Không tìm thấy verification code trong email")
                        print("  → Đợi 60s để bạn nhập code thủ công...")
                        time.sleep(60)
                    continue
            except:
                pass
            
            # CASE 4: Trang login với email_verification_required → Verify email
            if "/login" in current_url and "email_verification_required=true" in current_url:
                print("→ Cần verify email...")
                
                # Tìm nút Resend
                try:
                    resend_btn = short_wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Resend verification')]"))
                    )
                    resend_btn.click()
                    print("  ✓ Đã click Resend verification")
                    time.sleep(2)
                    
                    # Lấy verification link từ email
                    print("  🔍 Đang lấy verification link từ email...")
                    verify_link = wait_for_openhands_link(
                        email=email,
                        refresh_token=refresh_token,
                        client_id=client_id,
                        max_wait=120,
                        check_interval=5
                    )
                    
                    if verify_link:
                        print("  ✓ Đã nhận được verification link")
                        driver.get(verify_link)
                        time.sleep(1)
                        
                        # Click "Click here to proceed"
                        try:
                            proceed = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Click here to proceed')]"))
                            )
                            proceed.click()
                            print("  ✓ Đã click 'Click here to proceed'")
                            time.sleep(1)
                        except:
                            pass
                        
                        # Click "Back to Application"  
                        try:
                            back = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Back to Application')]"))
                            )
                            back.click()
                            print("  ✓ Đã click 'Back to Application'")
                            time.sleep(2)
                        except:
                            driver.get(ALLHANDS_LOGIN_URL)
                            time.sleep(2)
                    else:
                        print("  ⚠ Không nhận được verification link")
                except Exception as e:
                    print(f"  ⚠ Lỗi verify email: {str(e)[:50]}")
                
                # Sau khi verify, quay lại trang login và click GitLab
                current_url = driver.current_url
                if "/login" in current_url:
                    print("→ Quay lại trang login, click GitLab...")
                    click_gitlab_button()
                    time.sleep(2)
                continue
            
            # CASE 5: Trang login - CHECK RESEND BUTTON TRƯỚC, rồi mới click GitLab
            if "/login" in current_url:
                # QUAN TRỌNG: Check xem có nút Resend verification không (dù URL không có email_verification_required)
                try:
                    resend_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Resend verification')]"))
                    )
                    print("→ Tìm thấy nút 'Resend verification', cần verify email...")
                    resend_btn.click()
                    print("  ✓ Đã click Resend verification")
                    time.sleep(2)
                    
                    # Lấy verification link từ email
                    print("  🔍 Đang lấy verification link từ email...")
                    verify_link = wait_for_openhands_link(
                        email=email,
                        refresh_token=refresh_token,
                        client_id=client_id,
                        max_wait=120,
                        check_interval=5
                    )
                    
                    if verify_link:
                        print("  ✓ Đã nhận được verification link")
                        driver.get(verify_link)
                        time.sleep(1)
                        
                        # Click "Click here to proceed"
                        try:
                            proceed = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Click here to proceed')]"))
                            )
                            proceed.click()
                            print("  ✓ Đã click 'Click here to proceed'")
                            time.sleep(1)
                        except:
                            pass
                        
                        # Click "Back to Application"
                        try:
                            back = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Back to Application')]"))
                            )
                            back.click()
                            print("  ✓ Đã click 'Back to Application'")
                            time.sleep(2)
                        except:
                            driver.get(ALLHANDS_LOGIN_URL)
                            time.sleep(2)
                        
                        # Sau khi verify xong, click GitLab để login
                        print("→ Email đã verify, click GitLab để login...")
                        click_gitlab_button()
                        time.sleep(2)
                    else:
                        print("  ⚠ Không nhận được verification link")
                    continue
                except TimeoutException:
                    # Không có nút Resend → click GitLab bình thường
                    pass
                except Exception as e:
                    print(f"  ⚠ Lỗi check Resend: {str(e)[:30]}")
                
                # Không có Resend button → click GitLab
                if attempt < max_retries:
                    print(f"→ Vẫn ở trang login (attempt {attempt + 1}/{max_retries + 1}), click GitLab...")
                    if click_gitlab_button():
                        print("  ✓ Đã click GitLab")
                        time.sleep(2)
                    else:
                        print("  ✗ Không tìm thấy button GitLab")
                continue
            
            # CASE 6: URL khác (có thể đang redirect) → đợi
            time.sleep(2)
        
        # ============================================================
        # KIỂM TRA KẾT QUẢ CUỐI CÙNG
        # ============================================================
        current_url = driver.current_url
        print(f"\n[Final] URL: {current_url}")
        
        # Nếu vẫn ở login → thất bại
        if "/login" in current_url:
            print("✗ Không thể đăng nhập sau nhiều lần thử")
            return False
        
        # Nếu ở accept-tos → xử lý lần cuối
        if "/accept-tos" in current_url:
            print("→ Xử lý TOS lần cuối...")
            handle_accept_tos()
            time.sleep(2)
        
        # ============================================================
        # LẤY API KEY
        # ============================================================
        print(f"\n[Step 3] Lấy API key...")
        api_key = get_api_key(driver, email)
        
        if not api_key:
            print("✗ Không lấy được API key")
            return False
        
        # Lưu API key
        save_api_key(email, api_key)
        
        print("\n" + "="*60)
        print("✅ HOÀN THÀNH ĐĂNG NHẬP VÀ LẤY API KEY!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Lỗi khi đăng nhập: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def get_api_key(driver, email):
    """
    Lấy API key từ trang /settings/api-keys
    """
    try:
        wait = WebDriverWait(driver, 10)
        
        # Navigate đến trang API keys
        print("🔄 Đang navigate đến trang API keys...")
        
        # Kiểm tra xem đã ở trang API keys chưa
        if "/settings/api-keys" not in driver.current_url:
            driver.get(ALLHANDS_API_KEYS_URL)
            time.sleep(PAGE_LOAD_WAIT)
        
        # Đợi trang load
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        print(f"✓ Đã vào trang API keys: {driver.current_url}")
        time.sleep(1)
        
        # QUAN TRỌNG: Click "Refresh API Key" trước để tạo/refresh API key mới
        print("🔄 Đang click 'Refresh API Key'...")
        try:
            refresh_btn_selectors = [
                (By.XPATH, "//button[contains(., 'Refresh API Key')]"),
                (By.XPATH, "//button[contains(@class, 'bg-primary') and contains(., 'Refresh')]"),
                (By.XPATH, "//button[contains(text(), 'Refresh')]"),
            ]
            refresh_btn = None
            for by, selector in refresh_btn_selectors:
                try:
                    refresh_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    break
                except:
                    continue
            
            if refresh_btn:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", refresh_btn)
                time.sleep(0.3)
                refresh_btn.click()
                print("✓ Đã click 'Refresh API Key'")
                time.sleep(2)  # Đợi API key mới được generate
            else:
                print("⚠ Không tìm thấy nút 'Refresh API Key'")
        except Exception as e:
            print(f"⚠ Lỗi click Refresh: {str(e)[:50]}")
        
        api_key = None
        
        # Phương pháp 1: Tìm trong input fields
        print("  [1] Đang tìm trong input fields...")
        try:
            api_key_elements = driver.find_elements(By.XPATH, "//input[@type='text' or @type='password' or @readonly]")
            for elem in api_key_elements:
                try:
                    value = elem.get_attribute("value")
                    if value and len(value) > 20:
                        api_key = value
                        print(f"✓ Tìm thấy API key trong input (length: {len(value)})")
                        break
                except:
                    continue
        except Exception as e:
            print(f"  ⚠ Lỗi phương pháp 1: {e}")
        
        # Phương pháp 2: Tìm trong text elements
        if not api_key:
            print("  [2] Đang tìm trong text elements...")
            try:
                text_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'font-mono')] | //code | //span[contains(@class, 'font-mono')]")
                for elem in text_elements:
                    try:
                        text = elem.text.strip()
                        if text and len(text) > 20 and ' ' not in text:
                            api_key = text
                            print(f"✓ Tìm thấy API key trong text (length: {len(text)})")
                            break
                    except:
                        continue
            except Exception as e:
                print(f"  ⚠ Lỗi phương pháp 2: {e}")
        
        # Phương pháp 3: Click copy button và lấy từ clipboard
        if not api_key:
            print("  [3] Đang tìm copy button...")
            try:
                import pyperclip
                copy_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Copy') or contains(@title, 'Copy')]"))
                )
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", copy_button)
                time.sleep(0.3)
                copy_button.click()
                print("✓ Đã click copy button")
                time.sleep(0.8)
                
                clipboard_content = pyperclip.paste()
                if clipboard_content and len(clipboard_content) > 20:
                    api_key = clipboard_content
                    print(f"✓ Lấy được API key từ clipboard (length: {len(clipboard_content)})")
            except:
                print("  ⚠ Không thể dùng phương pháp 3")
        
        # Screenshot nếu không tìm thấy
        if not api_key:
            try:
                screenshot_path = f"debug_api_key_{email.split('@')[0]}.png"
                driver.save_screenshot(screenshot_path)
                print(f"  ⚠ Đã lưu screenshot: {screenshot_path}")
            except:
                pass
        
        return api_key
        
    except Exception as e:
        print(f"✗ Lỗi khi lấy API key: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def save_api_key(email, api_key):
    """Lưu API key vào file"""
    try:
        username = email.split('@')[0]
        
        # Check duplicate
        existing_keys = set()
        if os.path.exists(API_KEYS_FILE):
            with open(API_KEYS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if '|' in line:
                        existing_keys.add(line.strip())
        
        new_entry = f"{username}|{api_key}"
        
        if new_entry in existing_keys:
            print(f"⚠ API key đã tồn tại trong file, bỏ qua...")
            return
        
        # Append to file
        with open(API_KEYS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{new_entry}\n")
        
        print(f"✓ Đã lưu API key vào {API_KEYS_FILE}")
        print(f"  Username: {username}")
        print(f"  API Key: {api_key[:20]}..." if len(api_key) > 20 else f"  API Key: {api_key}")
        
    except Exception as e:
        print(f"✗ Lỗi khi lưu API key: {str(e)}")

def log_error(email, error_msg):
    """Ghi log email failed"""
    try:
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{timestamp}|{email}|{error_msg}\n")
        print(f"✓ Đã ghi log lỗi vào {ERROR_LOG_FILE}")
    except Exception as e:
        print(f"⚠ Không thể ghi log: {str(e)}")

# ============================================================
# MAIN
# ============================================================

def main():
    """Main function"""
    driver = None
    current_email_processing = None
    
    try:
        print("=" * 60)
        print("ĐĂNG NHẬP ALL-HANDS.DEV QUA GITLAB OAUTH")
        print("=" * 60)
        
        # Kiểm tra ixBrowser config
        if USE_IXBROWSER:
            if not IXBROWSER_AVAILABLE:
                print("✗ ixbrowser-local-api chưa được cài đặt!")
                print("  Chạy: pip install ixbrowser-local-api")
                return
            if not IXBROWSER_PROFILE_ID:
                print("✗ IXBROWSER_PROFILE_ID chưa được cấu hình!")
                print("  Thêm vào .env: IXBROWSER_PROFILE_ID=your_profile_id")
                return
            print(f"✓ ixBrowser Profile ID: {IXBROWSER_PROFILE_ID}")
        
        # Đọc emails từ file
        print("\n[0/5] Đang đọc danh sách email...")
        emails = read_all_emails()
        
        if not emails:
            print("✗ Không có email nào để xử lý")
            return
        
        print(f"✓ Đã đọc {len(emails)} email từ file")
        for idx, (email, _, _, _) in enumerate(emails, 1):
            print(f"  {idx}. {email}")
        
        # Loop qua từng email
        for idx, (email, password, refresh_token, client_id) in enumerate(emails, 1):
            try:
                current_email_processing = email
                print("\n" + "=" * 60)
                print(f"📧 XỬ LÝ EMAIL {idx}/{len(emails)}: {email}")
                print("=" * 60)
                
                # Mở ixBrowser profile
                if USE_IXBROWSER:
                    print("\n[1/5] Đang mở ixBrowser profile...")
                    try:
                        driver = setup_ixbrowser_driver(IXBROWSER_PROFILE_ID)
                        set_window_position(driver)
                        print("✓ ixBrowser profile đã sẵn sàng")
                    except Exception as e:
                        print(f"✗ Lỗi khi mở ixBrowser: {str(e)}")
                        log_error(email, f"Lỗi mở ixBrowser: {str(e)}")
                        continue
                
                # BƯỚC MỚI: Đăng nhập GitLab trước
                print("\n[2/5] Đang đăng nhập GitLab...")
                success_gitlab = signin_gitlab(driver, email, password, refresh_token, client_id)
                
                if not success_gitlab:
                    print(f"✗ Đăng nhập GitLab thất bại cho {email}")
                    log_error(email, "Đăng nhập GitLab thất bại")
                    # Cleanup và tiếp tục email tiếp theo
                    try:
                        if driver:
                            driver.quit()
                    except:
                        pass
                    if USE_IXBROWSER:
                        try:
                            close_ixbrowser_profile(IXBROWSER_PROFILE_ID, clear_data=True)
                        except:
                            pass
                    continue
                
                # Đăng nhập OpenHands
                print("\n[3/5] Đang đăng nhập All-Hands.dev...")
                success = login_allhands_gitlab(driver, email, password, refresh_token, client_id)
                
                if not success:
                    print(f"✗ Đăng nhập OpenHands thất bại cho {email}")
                    log_error(email, "Đăng nhập OpenHands thất bại")
                else:
                    print(f"✅ Hoàn thành cho {email}")
                
                # Đóng browser
                print("\n[4/5] Đang đóng browser...")
                try:
                    if driver:
                        driver.quit()
                        print("✓ Đã đóng browser")
                except:
                    pass
                
                # Clear cookies và đóng profile
                if USE_IXBROWSER:
                    print("\n[5/5] Đang clear cookies và đóng profile...")
                    close_ixbrowser_profile(IXBROWSER_PROFILE_ID, clear_data=True)
                    print("✓ Đã clear cookies và đóng profile")
                
                # Delay giữa các email
                if idx < len(emails):
                    delay_sec = random.randint(1, 3)
                    print(f"\n⏱️  Đợi {delay_sec}s trước khi xử lý email tiếp theo...")
                    time.sleep(delay_sec)
                
            except KeyboardInterrupt:
                print("\n\n⚠️ Đã nhận tín hiệu dừng (Ctrl+C)")
                raise
            
            except Exception as e:
                print(f"\n✗ Lỗi khi xử lý {email}: {str(e)}")
                log_error(email, str(e))
                import traceback
                traceback.print_exc()
                
                # Cleanup
                try:
                    if driver:
                        driver.quit()
                except:
                    pass
                
                if USE_IXBROWSER:
                    try:
                        close_ixbrowser_profile(IXBROWSER_PROFILE_ID, clear_data=True)
                    except:
                        pass
                
                # Tiếp tục với email tiếp theo
                continue
        
        print("\n" + "=" * 60)
        print("✅ ĐÃ HOÀN THÀNH TẤT CẢ EMAIL!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Script đã bị dừng bởi người dùng")
        if current_email_processing:
            log_error(current_email_processing, "Script bị dừng bởi người dùng")
    
    except Exception as e:
        print(f"\n✗ Lỗi nghiêm trọng: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Final cleanup
        try:
            if driver:
                driver.quit()
                print("✓ Đã đóng browser cuối cùng")
        except:
            pass
        
        if USE_IXBROWSER:
            try:
                close_ixbrowser_profile(IXBROWSER_PROFILE_ID, clear_data=True)
                print("✓ Đã đóng ixBrowser profile cuối cùng")
            except:
                pass

if __name__ == "__main__":
    main()
