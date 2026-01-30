# -*- coding: utf-8 -*-
"""
Script tự động đăng ký GitLab.com
Sử dụng ixBrowser profile với chế độ ẩn danh (Incognito)
Tự động clear cookies và data khi đóng browser
"""

# Fix Windows console encoding for Vietnamese characters
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

# Import email API helper để lấy verification code
try:
    from email_api_helper import wait_for_gitlab_verification_code, get_emails_from_api
    EMAIL_API_AVAILABLE = True
    print("✓ email_api_helper có sẵn")
except ImportError:
    EMAIL_API_AVAILABLE = False
    print("⚠ email_api_helper không import được")

# ============================================================
# SETTINGS
# ============================================================
# ixBrowser Profile ID
_ixbrowser_profile_id_str = os.getenv("IXBROWSER_PROFILE_ID", "")
IXBROWSER_PROFILE_ID = int(_ixbrowser_profile_id_str) if _ixbrowser_profile_id_str.isdigit() else None

# ixBrowser API
IXBROWSER_API_HOST = "127.0.0.1"
IXBROWSER_API_PORT = 53200

# URLs
GITLAB_SIGNUP_URL = "https://gitlab.com/users/sign_up"

# Files
EMAIL_FILE = "products.txt"  # Format: email|password|refresh_token|client_id

# Timing
TURBO_MODE = True
if TURBO_MODE:
    TYPING_SPEED = (0.01, 0.03)
    DELAY_SHORT = (0.1, 0.3)
    DELAY_MEDIUM = (0.3, 0.6)
else:
    TYPING_SPEED = (0.05, 0.1)
    DELAY_SHORT = (0.3, 0.6)
    DELAY_MEDIUM = (0.5, 1.0)

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
    """Tạo username từ email (loại bỏ ký tự đặc biệt)"""
    # Lấy phần trước @
    prefix = email.split('@')[0]
    # Chỉ giữ chữ cái và số
    username = ''.join(c for c in prefix if c.isalnum())
    # Thêm số random để tránh trùng
    username = f"{username}{random.randint(100, 999)}"
    return username[:20]  # GitLab username max 255, nhưng giữ ngắn


def generate_name_from_email(email):
    """
    Tạo first name và last name từ email
    Đơn giản: tách phần trước @ làm đôi
    
    VD: coltonbrickerbps0673@hotmail.com
    -> First: Coltonbri
    -> Last: Ckerbps
    """
    # Lấy phần trước @
    prefix = email.split('@')[0]
    
    # Chỉ giữ chữ cái (bỏ số và ký tự đặc biệt)
    clean_prefix = ''.join(c for c in prefix if c.isalpha())
    
    # Nếu quá ngắn, dùng prefix gốc
    if len(clean_prefix) < 4:
        clean_prefix = ''.join(c for c in prefix if c.isalnum())
    
    # Chia đôi
    mid = len(clean_prefix) // 2
    first_name = clean_prefix[:mid].capitalize()
    last_name = clean_prefix[mid:].capitalize()
    
    # Đảm bảo có ít nhất 2 ký tự
    if len(first_name) < 2:
        first_name = "User"
    if len(last_name) < 2:
        last_name = "Account"
    
    # Giới hạn độ dài (GitLab max 127)
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
    driver = webdriver.Chrome(service=Service(webdriver_path), options=chrome_options)
    
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
    """
    Đọc email từ file
    Format: email|password|refresh_token|client_id
    
    refresh_token và client_id cần thiết để gọi API lấy verification email
    """
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


def register_gitlab(driver, email, password, first_name=None, last_name=None):
    """
    Đăng ký tài khoản GitLab
    
    Returns: True nếu thành công điền form, False nếu lỗi
    """
    try:
        wait = WebDriverWait(driver, 15)
        
        # Mở trang đăng ký
        print(f"\n[GitLab] Đang mở trang đăng ký...")
        driver.get(GITLAB_SIGNUP_URL)
        
        # Đợi form load
        wait.until(EC.presence_of_element_located((By.ID, "new_user_email")))
        print("✓ Form đăng ký đã load")
        time.sleep(1)
        
        # Generate names nếu chưa có
        if not first_name or not last_name:
            first_name, last_name = generate_name_from_email(email)
        
        # Generate username
        username = generate_username_from_email(email)
        
        print(f"\n[GitLab] Đang điền form...")
        print(f"  Email: {email}")
        print(f"  First Name: {first_name}")
        print(f"  Last Name: {last_name}")
        print(f"  Username: {username}")
        
        # 1. Điền First Name
        print("\n[1/5] Điền First Name...")
        first_name_field = wait.until(
            EC.presence_of_element_located((By.ID, "new_user_first_name"))
        )
        first_name_field.clear()
        human_like_type(first_name_field, first_name)
        random_delay('short')
        
        # 2. Điền Last Name
        print("[2/5] Điền Last Name...")
        last_name_field = driver.find_element(By.ID, "new_user_last_name")
        last_name_field.clear()
        human_like_type(last_name_field, last_name)
        random_delay('short')
        
        # 3. Điền Username
        print("[3/5] Điền Username...")
        username_field = driver.find_element(By.ID, "new_user_username")
        username_field.clear()
        human_like_type(username_field, username)
        random_delay('medium')  # Đợi validation
        
        # Check username availability
        try:
            time.sleep(1.5)  # Đợi AJAX check
            success_msg = driver.find_elements(By.CSS_SELECTOR, ".validation-success:not(.hide)")
            if success_msg:
                print("  ✓ Username available")
            else:
                error_msg = driver.find_elements(By.CSS_SELECTOR, ".validation-error:not(.hide)")
                if error_msg:
                    print("  ⚠ Username taken, đang thử username khác...")
                    # Thử username mới
                    new_username = f"{username}{random.randint(1000, 9999)}"
                    username_field.clear()
                    human_like_type(username_field, new_username)
                    time.sleep(1.5)
        except:
            pass
        
        # 4. Điền Email
        print("[4/5] Điền Email...")
        email_field = driver.find_element(By.ID, "new_user_email")
        email_field.clear()
        human_like_type(email_field, email)
        random_delay('short')
        
        # 5. Điền Password
        print("[5/5] Điền Password...")
        password_field = driver.find_element(By.ID, "new_user_password")
        password_field.clear()
        human_like_type(password_field, password)
        random_delay('short')
        
        print("\n✓ Đã điền đầy đủ form!")
        
        # Đợi backend validate (password không trùng username, etc.)
        delay_before_submit = random.uniform(5, 7)
        print(f"\n[GitLab] Đợi {delay_before_submit:.1f}s để backend validate...")
        time.sleep(delay_before_submit)
        
        # Click nút Continue
        print("[GitLab] Đang click nút Continue...")
        submit_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='new-user-register-button']"))
        )
        
        # Scroll vào view
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", submit_button)
        random_delay('short')
        
        # Click
        try:
            submit_button.click()
        except:
            driver.execute_script("arguments[0].click();", submit_button)
        
        print("✓ Đã click Continue")
        
        # Đợi và check kết quả
        print("\n[GitLab] Đang đợi phản hồi...")
        time.sleep(3)
        
        current_url = driver.current_url
        print(f"  URL hiện tại: {current_url}")
        
        # Nếu đã chuyển sang /users -> thành công, lấy verification link
        if "/users" in current_url and "sign_up" not in current_url:
            print("\n" + "=" * 60)
            print("✓ ĐĂNG KÝ THÀNH CÔNG!")
            print("  URL: " + current_url)
            print("=" * 60)
            
            # Trả về True để tiếp tục lấy verification
            return True
        
        # Check nếu có CAPTCHA hoặc lỗi
        if "sign_up" in current_url:
            print("⚠ Vẫn ở trang sign_up - có thể cần giải CAPTCHA hoặc có lỗi")
            
            # Check CAPTCHA
            captcha = driver.find_elements(By.CSS_SELECTOR, ".js-arkose-labs-container-13")
            if captcha and captcha[0].is_displayed():
                print("\n" + "!" * 50)
                print("⚠ CAPTCHA XUẤT HIỆN!")
                print("  Vui lòng giải CAPTCHA thủ công...")
                print("!" * 50)
                
                # Đợi user giải CAPTCHA (tối đa 120s)
                for i in range(120):
                    time.sleep(1)
                    if "sign_up" not in driver.current_url:
                        print("✓ CAPTCHA đã được giải!")
                        break
                    print(f"  Đợi CAPTCHA... ({120-i}s)", end='\r')
            
            return True
        
        print("✓ Đăng ký thành công! (đã chuyển trang)")
        return True
        
    except Exception as e:
        print(f"\n✗ Lỗi khi đăng ký: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def handle_verification_and_welcome(driver, email, refresh_token, client_id):
    """
    Xử lý trang verification và welcome form
    
    Returns: True nếu thành công
    """
    try:
        # Kiểm tra xem có ở trang identity_verification không
        time.sleep(2)
        current_url = driver.current_url
        
        if "identity_verification" in current_url:
            print("\n[GitLab] Đang ở trang Identity Verification...")
            print("  Cần nhập verification code 6 số từ email")
            
            # Lấy verification CODE từ email qua API
            if not EMAIL_API_AVAILABLE:
                print("⚠ email_api_helper không khả dụng")
                print("  Vui lòng nhập verification code thủ công")
                return False
            
            print("\n[GitLab Verification] Đang lấy verification code từ email...")
            verification_code = wait_for_gitlab_verification_code(
                email=email,
                refresh_token=refresh_token,
                client_id=client_id,
                max_wait=120,
                check_interval=5
            )
            
            if not verification_code:
                print("✗ Không tìm thấy verification code trong email")
                print("  Vui lòng kiểm tra email và nhập code thủ công")
                return False
            
            print(f"\n✓ Tìm thấy verification code: {verification_code}")
            
            # Điền code vào input field
            print("\n[GitLab] Đang điền verification code...")
            wait = WebDriverWait(driver, 10)
            code_input = wait.until(
                EC.presence_of_element_located((By.ID, "verification_code"))
            )
            code_input.clear()
            code_input.send_keys(verification_code)
            print(f"  ✓ Đã điền code: {verification_code}")
            
            # Đợi một chút
            time.sleep(1)
            
            # Click nút "Verify email address"
            print("\n[GitLab] Đang click nút Verify...")
            verify_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            verify_button.click()
            print("  ✓ Đã click Verify")
            
            # Đợi kết quả (5s như yêu cầu)
            time.sleep(5)
            new_url = driver.current_url
            print(f"  URL sau khi verify: {new_url}")
            
            if "identity_verification" in new_url:
                print("⚠ Vẫn ở trang verification, có thể code sai hoặc cần thao tác thêm...")
                return False
            
            print("\n" + "=" * 60)
            print("✅ EMAIL ĐÃ ĐƯỢC XÁC THỰC THÀNH CÔNG!")
            print("=" * 60)
            
            # Cập nhật current_url sau verify
            current_url = new_url
        
        # Kiểm tra xem có ở trang Welcome không
        if "sign_up/welcome" in current_url:
            print("\n[GitLab Welcome] Đang điền form Welcome...")
            
            wait = WebDriverWait(driver, 10)
            
            # 1. Select Role = "Software Developer" (value="0")
            print("  [1/5] Chọn Role: Software Developer...")
            role_select = wait.until(
                EC.presence_of_element_located((By.ID, "user_onboarding_status_role"))
            )
            role_select.send_keys("Software Developer")
            time.sleep(0.5)
            
            # 2. Select Registration Objective = "I want to use GitLab CI..." (value="4")
            print("  [2/5] Chọn Registration Objective: GitLab CI...")
            objective_select = driver.find_element(By.ID, "user_onboarding_status_registration_objective")
            objective_select.send_keys("I want to use GitLab CI with my existing repository")
            time.sleep(0.5)
            
            # 3. Radio: What would you like to do? = "Create a new project" (value="false")
            print("  [3/5] Chọn: Create a new project...")
            create_project_radio = driver.find_element(By.ID, "user_onboarding_status_joining_project_false")
            driver.execute_script("arguments[0].click();", create_project_radio)
            time.sleep(0.5)
            
            # 4. Radio: Who will be using GitLab? = "Just me" (value="false")
            print("  [4/5] Chọn: Just me...")
            just_me_radio = driver.find_element(By.ID, "user_onboarding_status_setup_for_company_false")
            driver.execute_script("arguments[0].click();", just_me_radio)
            time.sleep(0.5)
            
            # 5. Click Continue button
            print("  [5/5] Click Continue...")
            continue_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='get-started-button']"))
            )
            continue_button.click()
            print("  ✓ Đã click Continue")
            
            # Đợi chuyển trang
            time.sleep(3)
            next_url = driver.current_url
            print(f"\n  URL tiếp theo: {next_url}")
            
            # Kiểm tra xem có trang tạo project không
            if "projects/new" in next_url or "new_project" in next_url:
                print("\n[GitLab] Đang ở trang Create Project...")
                print("  Click nút Create Project...")
                
                try:
                    create_project_button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='submit-button']"))
                    )
                    create_project_button.click()
                    print("  ✓ Đã click Create Project")
                    
                    time.sleep(3)
                    final_url = driver.current_url
                    print(f"\n  URL cuối cùng: {final_url}")
                except Exception as e:
                    print(f"  ⚠ Không tìm thấy nút Create Project: {str(e)}")
            
            print("\n" + "=" * 60)
            print("✅ ĐÃ HOÀN THÀNH ĐĂNG KÝ GITLAB!")
            print("=" * 60)
            return True
        
        print(f"  URL hiện tại: {current_url}")
        return True
        
    except Exception as e:
        print(f"\n✗ Lỗi khi xử lý verification/welcome: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Hàm chính"""
    driver = None
    
    try:
        print("=" * 60)
        print("GitLab Auto Registration")
        print("Sử dụng ixBrowser (Incognito) + Clear Data")
        print("=" * 60)
        
        # Check config
        if not IXBROWSER_PROFILE_ID:
            print("✗ IXBROWSER_PROFILE_ID chưa được cấu hình trong .env")
            return
        
        print(f"✓ ixBrowser Profile ID: {IXBROWSER_PROFILE_ID}")
        
        # Đọc emails
        print("\n[1] Đọc danh sách email...")
        emails = read_emails()
        
        if not emails:
            print("✗ Không có email nào để xử lý")
            return
        
        print(f"✓ Đã đọc {len(emails)} email")
        
        # Xử lý từng email
        for idx, data in enumerate(emails, 1):
            email = data['email']
            password = data['password']
            refresh_token = data['refresh_token']
            client_id = data['client_id']
            
            print("\n" + "=" * 60)
            print(f"[{idx}/{len(emails)}] Đang xử lý: {email}")
            print("=" * 60)
            
            try:
                # Mở ixBrowser
                driver = setup_ixbrowser_driver(IXBROWSER_PROFILE_ID, incognito=True)
                
                # Đăng ký GitLab
                success = register_gitlab(driver, email, password)
                
                if success:
                    print(f"\n✓ Đăng ký form thành công: {email}")
                    
                    # Xử lý verification và welcome
                    verification_success = handle_verification_and_welcome(
                        driver, email, refresh_token, client_id
                    )
                    
                    if verification_success:
                        print(f"\n✅ Hoàn thành toàn bộ cho: {email}")
                    else:
                        print(f"\n⚠ Verification chưa hoàn tất cho: {email}")
                else:
                    print(f"\n✗ Thất bại email: {email}")
                
                # Đợi user xem kết quả
                print("\n" + "-" * 40)
                print("Nhấn Enter để tiếp tục với email tiếp theo...")
                print("-" * 40)
                
                try:
                    input()
                except EOFError:
                    time.sleep(5)
                
            except Exception as e:
                print(f"\n✗ Lỗi: {str(e)}")
                import traceback
                traceback.print_exc()
            
            finally:
                # Đóng browser và clear data
                if driver:
                    try:
                        close_ixbrowser_profile(IXBROWSER_PROFILE_ID, clear_data=True)
                    except:
                        pass
                    driver = None
                
                # Delay giữa các email
                if idx < len(emails):
                    delay = random.randint(2, 5)
                    print(f"\n⏱️ Đợi {delay}s trước email tiếp theo...")
                    time.sleep(delay)
        
        print("\n" + "=" * 60)
        print(f"✓ Đã xử lý xong {len(emails)} email!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nĐã dừng bởi user (Ctrl+C)")
    
    except Exception as e:
        print(f"\n✗ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if driver:
            try:
                close_ixbrowser_profile(IXBROWSER_PROFILE_ID, clear_data=True)
            except:
                pass


if __name__ == "__main__":
    main()
