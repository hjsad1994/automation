"""
Script tự động đăng ký All-Hands.dev thông qua Bitbucket OAuth với Google authentication
Sử dụng undetected-chromedriver để bypass automation detection
"""

# Fix Windows console encoding for Vietnamese characters
import sys
import io
if sys.platform == "win32":
    # Set console encoding to UTF-8 on Windows
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
from selenium.webdriver.common.action_chains import ActionChains

# Import email API helper
from email_api_helper import wait_for_openhands_link, wait_for_bitbucket_code

# Import selenium-wire để hỗ trợ proxy authentication
try:
    from seleniumwire import webdriver as wiredriver
    from seleniumwire import undetected_chromedriver as wire_uc
    SELENIUM_WIRE_AVAILABLE = True
    print("✓ selenium-wire có sẵn (hỗ trợ proxy auth)")
except ImportError:
    SELENIUM_WIRE_AVAILABLE = False
    print("⚠ selenium-wire chưa cài. Sẽ dùng local proxy server")

# Import local proxy server module
import threading
import socket

def start_local_proxy_server(upstream_host, upstream_port, username, password, local_port=18888):
    """Khởi động local proxy server để forward với authentication

    Mỗi email sẽ khởi động proxy mới với upstream proxy mới
    """
    global PROXY_THREAD, PROXY_SERVER_RUNNING, PROXY_STOP_FLAG, CURRENT_PROXY_PORT

    import base64

    def handle_client(client_socket, upstream_info):
        try:
            request = client_socket.recv(8192).decode('utf-8', errors='ignore')
            if not request:
                client_socket.close()
                return

            lines = request.split('\r\n')
            if len(lines) == 0:
                client_socket.close()
                return

            first_line = lines[0]
            parts = first_line.split(' ')
            if len(parts) < 2:
                client_socket.close()
                return

            method = parts[0]

            # CONNECT method cho HTTPS
            if method == 'CONNECT':
                try:
                    upstream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    upstream_socket.settimeout(30)
                    upstream_socket.connect((upstream_info['host'], upstream_info['port']))

                    auth_string = base64.b64encode(
                        f"{upstream_info['user']}:{upstream_info['pass']}".encode()
                    ).decode()

                    connect_request = f"{first_line}\r\n"
                    connect_request += f"Proxy-Authorization: Basic {auth_string}\r\n\r\n"

                    upstream_socket.sendall(connect_request.encode())
                    response = upstream_socket.recv(8192)
                    client_socket.sendall(response)

                    if b'200' in response:
                        # Tunnel data
                        import select
                        sockets = [client_socket, upstream_socket]
                        timeout = 300

                        while timeout > 0:
                            readable, _, _ = select.select(sockets, [], [], 1)
                            if not readable:
                                timeout -= 1
                                continue

                            for sock in readable:
                                data = sock.recv(8192)
                                if not data:
                                    client_socket.close()
                                    upstream_socket.close()
                                    return

                                if sock is client_socket:
                                    upstream_socket.sendall(data)
                                else:
                                    client_socket.sendall(data)

                            timeout = 300  # Reset timeout
                except Exception as e:
                    pass
                finally:
                    try:
                        client_socket.close()
                    except:
                        pass
                    try:
                        upstream_socket.close()
                    except:
                        pass
            else:
                client_socket.close()

        except Exception as e:
            try:
                client_socket.close()
            except:
                pass

    def proxy_server_thread():
        # Kill process đang chiếm port (nếu có)
        try:
            import subprocess
            import platform
            system = platform.system()
            if system == "Darwin" or system == "Linux":
                # macOS/Linux: lsof -ti:PORT | xargs kill -9
                subprocess.run(f"lsof -ti:{local_port} | xargs kill -9 2>/dev/null",
                              shell=True, check=False)
            elif system == "Windows":
                # Windows: netstat + taskkill
                subprocess.run(f"for /f \"tokens=5\" %a in ('netstat -aon ^| findstr :{local_port}') do taskkill /F /PID %a",
                              shell=True, check=False)
        except:
            pass

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('127.0.0.1', local_port))
        server_socket.listen(100)
        server_socket.settimeout(1)

        print(f"✓ Local proxy server started: 127.0.0.1:{local_port}")
        print(f"  → Forwarding to {upstream_host}:{upstream_port}")

        upstream_info = {
            'host': upstream_host,
            'port': int(upstream_port),
            'user': username,
            'pass': password
        }

        # Loop với stop flag check
        while not PROXY_STOP_FLAG:
            try:
                client_socket, _ = server_socket.accept()
                threading.Thread(
                    target=handle_client,
                    args=(client_socket, upstream_info),
                    daemon=True
                ).start()
            except socket.timeout:
                continue  # Timeout mỗi 1s để check PROXY_STOP_FLAG
            except:
                break

        # Cleanup khi stop
        print(f"[Proxy] Đang dừng proxy server trên port {local_port}...")
        server_socket.close()
        print(f"✓ Đã dừng proxy server")

    # Khởi động proxy server mới
    print(f"[Proxy] Đang khởi động proxy thread mới trên port {local_port}...")
    PROXY_STOP_FLAG = False  # Reset stop flag
    PROXY_THREAD = threading.Thread(target=proxy_server_thread, daemon=True)
    PROXY_THREAD.start()
    PROXY_SERVER_RUNNING = True
    CURRENT_PROXY_PORT = local_port
    time.sleep(1)  # Đợi proxy server khởi động (giảm từ 2s)
    print(f"✓ Proxy server đã khởi động trên port {local_port}")

    return local_port

def stop_proxy_server():
    """Dừng proxy server và đợi thread kết thúc"""
    global PROXY_THREAD, PROXY_SERVER_RUNNING, PROXY_STOP_FLAG

    if not PROXY_SERVER_RUNNING or not PROXY_THREAD:
        return

    print("[Proxy] Đang dừng proxy server cũ...")
    PROXY_STOP_FLAG = True  # Set flag để proxy thread thoát

    # Đợi thread kết thúc (tối đa 5s)
    if PROXY_THREAD and PROXY_THREAD.is_alive():
        PROXY_THREAD.join(timeout=5)

    PROXY_SERVER_RUNNING = False
    print("✓ Đã dừng proxy server cũ")

import time
import os
import requests
import json
import zipfile
import random

# Import undetected-chromedriver
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
    print("✓ undetected-chromedriver có sẵn")
except ImportError:
    UC_AVAILABLE = False
    print("⚠ undetected-chromedriver chưa cài. Cài đặt: pip install undetected-chromedriver")

# Optional: pyperclip for clipboard access (install with: pip install pyperclip)
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False
    print("⚠ pyperclip not installed. API key will be extracted from page elements.")

# URL target - Direct auth URL (bypasses Bitbucket OAuth button)
TARGET_URL = "https://auth.app.all-hands.dev/realms/allhands/protocol/openid-connect/auth?client_id=allhands&kc_idp_hint=bitbucket&response_type=code&redirect_uri=https%3A%2F%2Fapp.all-hands.dev%2Foauth%2Fkeycloak%2Fcallback&scope=openid+email+profile&state=https%3A%2F%2Fapp.all-hands.dev%3Flogin_method%3Dbitbucket&login_method=bitbucket"
EMAIL_FILE = "products.txt"  # Changed from email.txt to products.txt

# ============================================================
# PROXY SETTINGS - Chỉ dùng API xoay proxy
# ============================================================
USE_PROXY = True  # Bật/tắt sử dụng proxy

# PROXY API ROTATION - Xoay proxy tự động qua API
PROXY_API_URL = "https://proxyxoay.shop/api/get.php"
PROXY_API_KEY = "tcLQfdoXPYtbjMZulCnJSs"
PROXY_API_NETWORK = "random"  # random, viettel, fpt, vnpt, vinaphone, etc.
PROXY_API_LOCATION = "0"      # 0=bất kỳ, hoặc mã tỉnh thành cụ thể

# ============================================================
# WARM-UP SETTINGS - Giảm CAPTCHA bằng cách warm-up account
# ============================================================
ENABLE_WARMUP = False  # TẮT vì không hiệu quả (vẫn bị CAPTCHA)
WARMUP_ACTIONS = [
    "https://www.google.com",  # Visit Google
    "https://www.youtube.com",  # Visit YouTube
    "https://mail.google.com",  # Visit Gmail để login trước
]

# ============================================================
# WINDOW POSITION - Set vị trí và kích thước window
# ============================================================
WINDOW_LEFT_HALF = True  # True = Nửa trái màn hình | False = Full screen

def set_window_position(driver):
    """Set window position và size"""
    try:
        if WINDOW_LEFT_HALF:
            # Lấy kích thước màn hình
            screen_width = driver.execute_script("return window.screen.availWidth")
            screen_height = driver.execute_script("return window.screen.availHeight")

            # Set window ở 1/4 màn hình góc trên phải
            window_width = screen_width // 2
            window_height = screen_height // 2

            driver.set_window_position(screen_width // 2, 0)  # Góc phải trên
            driver.set_window_size(window_width, window_height)
            print(f"✓ Window: 1/4 màn hình góc trên phải ({window_width}x{window_height})")
        else:
            # Full screen
            driver.maximize_window()
            print("✓ Window: Full screen")
    except Exception as e:
        print(f"⚠ Lỗi set window position: {str(e)}")
        # Fallback: maximize
        try:
            driver.maximize_window()
        except:
            pass

# ============================================================
# TURBO MODE - Bật để chạy nhanh hơn, Tắt để giảm CAPTCHA
# ============================================================
TURBO_MODE = True  # True = Nhanh | False = An toàn

# Cấu hình delays dựa trên mode
if TURBO_MODE:
    print("🚀 TURBO MODE: BẬT - Tốc độ TỐI ĐA")
    DELAY_SHORT = (0.01, 0.03)        # Random delay ngắn - cực nhanh
    DELAY_MEDIUM = (0.03, 0.08)       # Random delay trung bình - rất nhanh
    DELAY_LONG = (0.1, 0.2)           # Random delay dài - nhanh
    TYPING_SPEED = (0.001, 0.003)     # Gõ siêu nhanh (gần như instant)
    DELAY_BETWEEN_EMAILS = (1, 2)    # Delay giữa emails: 1-2s (int for randint)
    PAGE_LOAD_WAIT = 0.1              # Đợi load trang - minimal
    CAPTCHA_TIMEOUT = 30              # Timeout CAPTCHA: 30s (giữ nguyên để có thời gian giải)
else:
    print("🐢 TURBO MODE: TẮT - An toàn hơn (ít CAPTCHA)")
    DELAY_SHORT = (0.3, 0.6)
    DELAY_MEDIUM = (0.5, 1.0)
    DELAY_LONG = (1.5, 2.5)
    TYPING_SPEED = (0.05, 0.15)
    DELAY_BETWEEN_EMAILS = (15, 30)
    PAGE_LOAD_WAIT = 2
    CAPTCHA_TIMEOUT = 30  # 30s để giải CAPTCHA

def random_delay(min_sec=None, max_sec=None, delay_type='short'):
    """Random delay với preset dựa trên TURBO_MODE"""
    if min_sec is None or max_sec is None:
        # Dùng preset
        if delay_type == 'short':
            min_sec, max_sec = DELAY_SHORT
        elif delay_type == 'medium':
            min_sec, max_sec = DELAY_MEDIUM
        elif delay_type == 'long':
            min_sec, max_sec = DELAY_LONG

    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

def human_like_type(element, text, typing_delay_range=None):
    """Gõ text với tốc độ dựa trên TURBO_MODE"""
    if typing_delay_range is None:
        typing_delay_range = TYPING_SPEED

    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(*typing_delay_range))

def smooth_scroll(driver, element):
    """Scroll đến element"""
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});",
            element
        )
        random_delay(delay_type='short')
    except:
        pass

def close_extra_windows(driver, keep_window):
    """
    Đóng tất cả windows/popups trừ window cần giữ lại
    Returns: True nếu có đóng window, False nếu không
    """
    try:
        all_handles = driver.window_handles
        if len(all_handles) <= 1:
            return False

        closed_count = 0
        for handle in all_handles:
            if handle != keep_window:
                try:
                    driver.switch_to.window(handle)
                    print(f"  ⚠ Đóng popup thừa: {handle[:8]}...")
                    driver.close()
                    closed_count += 1
                except Exception as e:
                    print(f"  ✗ Không thể đóng window: {str(e)}")

        # Switch về window chính
        driver.switch_to.window(keep_window)

        if closed_count > 0:
            print(f"✓ Đã đóng {closed_count} popup thừa")
            return True
        return False
    except Exception as e:
        print(f"⚠ Lỗi khi đóng extra windows: {str(e)}")
        return False

def wait_for_manual_captcha_solve(driver, timeout=None, auto_click_button=True):
    """
    Detect CAPTCHA và đợi user giải thủ công, sau đó tự động click button tiếp theo

    Args:
        driver: WebDriver instance
        timeout: Thời gian đợi tối đa (seconds)
        auto_click_button: Tự động tìm và click button sau khi giải CAPTCHA

    Returns: True nếu CAPTCHA đã được giải, False nếu timeout hoặc không có CAPTCHA
    """
    if timeout is None:
        timeout = CAPTCHA_TIMEOUT
    print("\n" + "="*60)
    print("🔍 ĐANG KIỂM TRA CAPTCHA...")
    print("="*60)

    # Check xem có CAPTCHA không
    captcha_selectors = [
        "//iframe[contains(@src, 'recaptcha')]",
        "//div[@class='g-recaptcha']",
        "//*[@id='recaptcha-anchor']",
        "//iframe[contains(@title, 'reCAPTCHA')]",
    ]

    has_captcha = False
    for selector in captcha_selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            if elements:
                has_captcha = True
                print("⚠ PHÁT HIỆN CAPTCHA!")
                break
        except:
            continue

    if not has_captcha:
        print("✓ Không có CAPTCHA, tiếp tục...")
        return True

    # Có CAPTCHA - thông báo cho user
    print("\n" + "!"*60)
    print("⚠️  CAPTCHA XUẤT HIỆN - CẦN GIẢI THỦ CÔNG")
    print("!"*60)
    print("\n📋 HƯỚNG DẪN:")
    print("  1. Nhìn vào cửa sổ Chrome")
    print("  2. Click vào ô CAPTCHA")
    print("  3. Giải CAPTCHA (chọn hình, nhập text, ...)")
    print("  4. Script sẽ TỰ ĐỘNG click button tiếp theo")
    print(f"\n⏱️  Thời gian tối đa: {timeout} giây")
    print("\n" + "="*60 + "\n")

    # Đợi CAPTCHA biến mất (nghĩa là user đã giải xong)
    start_time = time.time()
    check_interval = 1  # Check mỗi 1 giây (giảm từ 2s để responsive hơn)

    while time.time() - start_time < timeout:
        try:
            # Check xem CAPTCHA còn không
            captcha_still_exists = False

            # Check 1: iframe recaptcha có visible không
            iframes = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha')]")
            for iframe in iframes:
                try:
                    if iframe.is_displayed():
                        captcha_still_exists = True
                        break
                except:
                    pass

            # Check 2: Checkbox recaptcha chưa được check
            try:
                checkbox = driver.find_element(By.XPATH, "//*[@id='recaptcha-anchor']")
                if checkbox.is_displayed():
                    aria_checked = checkbox.get_attribute("aria-checked")
                    if aria_checked != "true":
                        captcha_still_exists = True
            except:
                pass

            # Check 3: Kiểm tra response token (dấu hiệu CAPTCHA đã giải)
            try:
                response = driver.execute_script(
                    "return document.querySelector('[name=\"g-recaptcha-response\"]')?.value || ''"
                )
                if response and len(response) > 50:  # Token thường rất dài
                    captcha_still_exists = False
                    print(f"\n✓ Detect CAPTCHA token: {response[:50]}...")
            except:
                pass

            if not captcha_still_exists:
                print("\n✅ CAPTCHA ĐÃ ĐƯỢC GIẢI!")
                print("🚀 Đang tự động click button tiếp theo...\n")
                time.sleep(1)

                # Tự động tìm và click button (Create account, Submit, Continue, etc.)
                if auto_click_button:
                    button_clicked = auto_click_submit_button(driver)
                    if button_clicked:
                        print("✓ Đã tự động click button tiếp theo")
                    else:
                        print("⚠ Không tìm thấy button để click, tiếp tục thủ công...")

                return True

            # In progress
            elapsed = int(time.time() - start_time)
            remaining = timeout - elapsed
            print(f"⏳ Đang đợi bạn giải CAPTCHA... ({remaining}s còn lại)", end='\r')
            time.sleep(check_interval)

        except Exception as e:
            # Có thể CAPTCHA đã biến mất (exception do element không tồn tại)
            print(f"\n✓ CAPTCHA có vẻ đã được giải (exception: {str(e)[:50]})")
            return True

    # Timeout
    print(f"\n\n⏱️  TIMEOUT sau {timeout}s!")
    print("⚠️  Có thể CAPTCHA chưa được giải hoặc bạn cần thêm thời gian.")
    print("Script sẽ thử tiếp tục anyway...\n")
    return False

def auto_click_submit_button(driver, wait_time=3):
    """
    Tự động tìm và click button submit/continue/create sau khi giải CAPTCHA

    Returns: True nếu click thành công, False nếu không tìm thấy
    """
    try:
        wait = WebDriverWait(driver, wait_time)

        # Các button có thể xuất hiện sau CAPTCHA
        button_selectors = [
            # Create account button
            (By.ID, "login-submit"),
            (By.XPATH, "//button[@id='login-submit' and @type='submit']"),
            (By.XPATH, "//button[contains(., 'Create your account')]"),
            (By.XPATH, "//button[contains(., 'Tạo tài khoản')]"),
            # Submit buttons
            (By.XPATH, "//button[@type='submit' and not(@disabled)]"),
            (By.XPATH, "//input[@type='submit' and not(@disabled)]"),
            # Continue/Next buttons
            (By.XPATH, "//button[contains(., 'Continue') or contains(., 'Next') or contains(., 'Tiếp tục')]"),
        ]

        for by, selector in button_selectors:
            try:
                button = wait.until(EC.element_to_be_clickable((by, selector)))
                # Scroll vào view
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", button)
                time.sleep(0.3)
                # Click
                try:
                    button.click()
                except:
                    driver.execute_script("arguments[0].click();", button)
                print(f"  ✓ Đã click button: {selector[:60]}...")
                return True
            except:
                continue

        return False

    except Exception as e:
        print(f"  ⚠ Lỗi auto-click: {str(e)}")
        return False

def warmup_browser(driver):
    """Warm-up browser để giảm CAPTCHA - Browse một vài trang trước khi automation"""
    if not ENABLE_WARMUP:
        return

    print("\n" + "="*60)
    print("🔥 WARM-UP BROWSER - Giảm CAPTCHA")
    print("="*60)

    for idx, url in enumerate(WARMUP_ACTIONS, 1):
        try:
            print(f"  [{idx}/{len(WARMUP_ACTIONS)}] Đang truy cập: {url}")
            driver.get(url)

            # Đợi trang load
            time.sleep(random.uniform(2, 4))

            # Scroll một chút để giống người dùng thật
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(random.uniform(1, 2))
                driver.execute_script("window.scrollTo(0, 0);")
            except:
                pass

            print(f"  ✓ Đã warm-up với {url}")
        except Exception as e:
            print(f"  ⚠ Lỗi khi warm-up {url}: {str(e)}")

    print("✓ Hoàn thành warm-up browser!")
    print("="*60 + "\n")

# Global proxy thread state - mỗi email 1 proxy mới
PROXY_THREAD = None
PROXY_SERVER_RUNNING = False
PROXY_STOP_FLAG = False  # Flag để stop proxy thread
CURRENT_PROXY_PORT = None

# REMOVED: File-based proxy logic
# def load_proxies_from_file(file_path="proxy.txt"):
#     """Đọc danh sách proxy từ file proxy.txt"""
#     ...
#
# def get_proxy_from_file():
#     """Lấy proxy tiếp theo từ danh sách (xoay vòng)"""
#     ...

def get_proxy_from_api():
    """
    Lấy proxy mới từ API proxyxoay.shop

    Không cần xoay vòng - mỗi lần gọi API sẽ trả về proxy mới
    Sử dụng HTTP proxy với username/password

    API Response:
    {
        "status": 100,  # 100=success, 101/102=error
        "message": "proxy nay se die sau 1777s",
        "proxyhttp": "IP:PORT:USERNAME:PASSWORD",
        "proxysocks5": "IP:PORT:USERNAME:PASSWORD",
        "Nha Mang": "fpt",
        "Vi Tri": "HaNoi1",
        "Token expiration date": "22:52 19-02-2025"
    }

    Returns:
        dict: Proxy info hoặc None nếu lỗi
    """
    try:
        print("\n[Proxy API] Đang gọi API proxyxoay.shop để lấy proxy mới...")

        # Build API URL với parameters
        params = {
            'key': PROXY_API_KEY,
            'nhamang': PROXY_API_NETWORK,
            'tinhthanh': PROXY_API_LOCATION
        }

        # Gọi API với timeout 15s
        response = requests.get(PROXY_API_URL, params=params, timeout=15)

        # Check HTTP status
        if response.status_code != 200:
            print(f"✗ API HTTP error: {response.status_code}")
            print("  → Không thể lấy proxy từ API")
            return None

        # Parse JSON response
        data = response.json()
        api_status = data.get('status')

        # Check API status code
        if api_status != 100:
            error_msg = data.get('message', 'Unknown error')
            print(f"✗ API error: status={api_status}")
            print(f"  Message: {error_msg}")

            if api_status == 101:
                print("  → Lỗi API key hoặc request không hợp lệ")
            elif api_status == 102:
                print("  → Không có proxy khả dụng")

            return None

        # Extract proxy HTTP (format: IP:PORT:USERNAME:PASSWORD)
        proxy_http = data.get('proxyhttp')
        if not proxy_http:
            print("✗ API không trả về 'proxyhttp' field")
            return None

        # Parse proxy format: IP:PORT:USERNAME:PASSWORD
        parts = proxy_http.split(':')
        if len(parts) != 4:
            print(f"✗ Format proxy không đúng: {proxy_http}")
            print("  Expected: IP:PORT:USERNAME:PASSWORD")
            return None

        proxy_ip = parts[0]
        proxy_port = parts[1]
        proxy_user = parts[2]
        proxy_pass = parts[3]

        # Log thông tin proxy từ API
        print(f"✓ Đã lấy proxy MỚI từ API:")
        print(f"  Proxy Server: {proxy_ip}:{proxy_port}")
        print(f"  Username: {proxy_user}")
        print(f"  Network: {data.get('Nha Mang', 'unknown')}")
        print(f"  Location: {data.get('Vi Tri', 'unknown')}")
        print(f"  Expires: {data.get('Token expiration date', 'unknown')}")
        print(f"  Message: {data.get('message', '')}")

        # Verify IP thực tế bằng curl
        print(f"[Proxy] Đang kiểm tra IP thực tế của proxy...")
        real_proxy_ip = None
        try:
            import subprocess
            result = subprocess.run(
                ['curl', '-x', f'http://{proxy_user}:{proxy_pass}@{proxy_ip}:{proxy_port}',
                 '--connect-timeout', '10', 'https://api.ipify.org'],
                capture_output=True,
                text=True,
                timeout=15
            )
            if result.returncode == 0:
                real_proxy_ip = result.stdout.strip()
                print(f"  ✓ IP thực tế qua proxy: {real_proxy_ip}")
            else:
                print(f"  ⚠ Không thể verify IP proxy (curl failed)")
        except Exception as e:
            print(f"  ⚠ Không thể verify IP proxy: {str(e)}")

        # Return proxy dict
        return {
            "http": proxy_http,  # IP:PORT:USERNAME:PASSWORD
            "socks5": data.get('proxysocks5'),  # Có thể dùng SOCKS5 sau này
            "location": data.get('Vi Tri', 'API-based'),
            "isp": data.get('Nha Mang', 'API proxy'),
            "real_ip": real_proxy_ip  # IP thực tế để verify
        }

    except requests.Timeout:
        print("✗ API timeout sau 15s")
        return None

    except requests.RequestException as e:
        print(f"✗ Lỗi kết nối API: {str(e)}")
        return None

    except json.JSONDecodeError as e:
        print(f"✗ Lỗi parse JSON từ API: {str(e)}")
        return None

    except Exception as e:
        print(f"✗ Lỗi không xác định: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def create_proxy_extension(proxy_host, proxy_port, proxy_user, proxy_pass):
    """Tạo Chrome extension để xử lý proxy authentication"""
    # Dùng Manifest V2 vì V3 không support webRequest blocking cho auth
    manifest_json = """
{
    "version": "1.0.0",
    "manifest_version": 2,
    "name": "Chrome Proxy Auth",
    "permissions": [
        "proxy",
        "tabs",
        "unlimitedStorage",
        "storage",
        "<all_urls>",
        "webRequest",
        "webRequestBlocking"
    ],
    "background": {
        "scripts": ["background.js"]
    },
    "minimum_chrome_version": "22.0.0"
}
"""

    background_js = """
var config = {
    mode: "fixed_servers",
    rules: {
        singleProxy: {
            scheme: "http",
            host: "%s",
            port: parseInt(%s)
        },
        bypassList: ["localhost"]
    }
};

console.log("[PROXY EXT] Starting proxy extension...");
console.log("[PROXY EXT] Proxy server:", "%s:%s");
console.log("[PROXY EXT] Username:", "%s");

chrome.proxy.settings.set({value: config, scope: "regular"}, function() {
    if (chrome.runtime.lastError) {
        console.error("[PROXY EXT] Error setting proxy:", chrome.runtime.lastError);
    } else {
        console.log("[PROXY EXT] ✓ Proxy settings applied successfully");
    }
});

function callbackFn(details) {
    console.log("[PROXY EXT] Auth required for:", details.url);
    console.log("[PROXY EXT] Sending credentials...");
    return {
        authCredentials: {
            username: "%s",
            password: "%s"
        }
    };
}

chrome.webRequest.onAuthRequired.addListener(
    callbackFn,
    {urls: ["<all_urls>"]},
    ['blocking']
);

console.log("[PROXY EXT] ✓ Auth listener registered successfully");
console.log("[PROXY EXT] Extension is ready!");
""" % (proxy_host, proxy_port, proxy_host, proxy_port, proxy_user, proxy_user, proxy_pass)

    # Tạo thư mục tạm cho extension
    import tempfile
    plugin_dir = tempfile.mkdtemp()

    manifest_file = os.path.join(plugin_dir, "manifest.json")
    with open(manifest_file, 'w', encoding='utf-8') as f:
        f.write(manifest_json)

    background_file = os.path.join(plugin_dir, "background.js")
    with open(background_file, 'w', encoding='utf-8') as f:
        f.write(background_js)

    # Trả về thư mục thay vì ZIP file
    print(f"  Extension directory: {plugin_dir}")
    return plugin_dir

def get_original_ip():
    """
    Lấy IP gốc của máy (không qua proxy)
    Returns: IP address string hoặc None nếu lỗi
    """
    try:
        print("[IP Check] Đang lấy IP gốc của máy...")
        import subprocess
        result = subprocess.run(
            ['curl', '--connect-timeout', '5', 'https://api.ipify.org'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            original_ip = result.stdout.strip()
            print(f"[IP Check] ✓ IP gốc: {original_ip}")
            return original_ip
        else:
            print(f"[IP Check] ⚠ Không thể lấy IP gốc (curl failed)")
            return None
    except Exception as e:
        print(f"[IP Check] ⚠ Lỗi khi lấy IP gốc: {str(e)}")
        return None

def verify_proxy_is_working(driver, expected_proxy_ip, original_ip=None):
    """
    Kiểm tra proxy hoạt động ĐÚNG:
    1. IP qua browser PHẢI KHÁC IP gốc (không dùng IP thật)
    2. IP qua browser NÊN MATCH với expected_proxy_ip (nếu có)

    Args:
        driver: WebDriver instance
        expected_proxy_ip: IP dự kiến từ proxy (có thể None)
        original_ip: IP gốc của máy (để so sánh)

    Returns:
        True: Proxy hoạt động đúng (IP đã thay đổi)
        False: Proxy KHÔNG hoạt động (vẫn dùng IP gốc)
        None: Không thể verify
    """
    try:
        print("\n" + "="*60)
        print("🔍 KIỂM TRA PROXY HOẠT ĐỘNG")
        print("="*60)

        print("[Proxy Verify] Đang kiểm tra IP qua browser...")

        # Sử dụng nhiều service để check IP (fallback)
        ip_check_urls = [
            "https://api.ipify.org?format=json",
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
        ]

        actual_ip = None
        for url in ip_check_urls:
            try:
                if "json" in url:
                    driver.get(url)
                    time.sleep(2)
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    data = json.loads(body_text)
                    actual_ip = data.get("ip", "")
                else:
                    driver.get(url)
                    time.sleep(2)
                    actual_ip = driver.find_element(By.TAG_NAME, "body").text.strip()

                if actual_ip:
                    print(f"[Proxy Verify] ✓ IP qua browser: {actual_ip}")
                    break

            except Exception as e:
                print(f"[Proxy Verify] ⚠ Lỗi với {url}: {str(e)[:50]}")
                continue

        if not actual_ip:
            print("[Proxy Verify] ✗ Không thể lấy IP từ browser")
            print("="*60)
            return None

        # CHECK 1: So sánh với IP gốc (QUAN TRỌNG NHẤT)
        if original_ip:
            print(f"\n[CHECK 1] So sánh với IP gốc:")
            print(f"  - IP gốc (máy):     {original_ip}")
            print(f"  - IP qua browser:   {actual_ip}")

            if actual_ip == original_ip:
                print("\n" + "!"*60)
                print("❌ PROXY KHÔNG HOẠT ĐỘNG!")
                print("   Browser đang dùng IP GỐC (không qua proxy)")
                print("!"*60)
                return False
            else:
                print(f"  ✅ IP đã thay đổi (KHÔNG phải IP gốc)")

        # CHECK 2: So sánh với expected proxy IP (nếu có)
        if expected_proxy_ip:
            print(f"\n[CHECK 2] So sánh với IP proxy:")
            print(f"  - IP proxy (dự kiến): {expected_proxy_ip}")
            print(f"  - IP qua browser:     {actual_ip}")

            if actual_ip == expected_proxy_ip:
                print(f"  ✅ IP MATCH với proxy")
            else:
                print(f"  ⚠ IP KHÁC với proxy (có thể do proxy gateway)")
                print(f"     Điều này vẫn OK nếu IP khác IP gốc")

        # KẾT LUẬN
        print("\n" + "="*60)
        if original_ip and actual_ip != original_ip:
            print("✅ PROXY HOẠT ĐỘNG ĐÚNG - IP đã được thay đổi")
            print("="*60 + "\n")
            return True
        elif not original_ip and expected_proxy_ip and actual_ip == expected_proxy_ip:
            print("✅ PROXY HOẠT ĐỘNG - IP match với proxy")
            print("="*60 + "\n")
            return True
        else:
            print("⚠ Không thể xác định chắc chắn")
            print("="*60 + "\n")
            return None

    except Exception as e:
        print(f"\n[Proxy Verify] ✗ Lỗi: {str(e)}")
        print("="*60 + "\n")
        return None

def auto_fill_proxy_auth(driver, username, password, max_wait=10):
    """Tự động điền username/password vào popup proxy authentication"""
    try:
        print(f"[Proxy Auth] Đang tìm popup authentication...")

        # Đợi và kiểm tra popup xuất hiện
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.common.alert import Alert

        for attempt in range(max_wait):
            try:
                # Chrome proxy auth popup là một alert
                alert = driver.switch_to.alert

                # Nếu tìm thấy alert, điền credentials
                print(f"[Proxy Auth] Tìm thấy popup! Đang điền credentials...")

                # Alert text thường là: "Authentication Required"
                # Format để điền: username + TAB + password + ENTER
                import pyperclip
                from selenium.webdriver.common.keys import Keys
                from selenium.webdriver.common.action_chains import ActionChains

                # Gửi username và password
                alert.send_keys(username + Keys.TAB + password)
                alert.accept()

                print(f"[Proxy Auth] ✓ Đã điền credentials thành công!")
                return True

            except:
                # Popup chưa xuất hiện, đợi thêm
                time.sleep(1)
                continue

        print(f"[Proxy Auth] Không tìm thấy popup authentication (có thể không cần)")
        return False

    except Exception as e:
        print(f"[Proxy Auth] Lỗi: {str(e)}")
        return False

def setup_chrome_driver(proxy_info=None):
    """Thiết lập Chrome WebDriver với local proxy server để xử lý authentication"""

    proxy_ip_to_verify = None
    local_proxy_port = None
    original_ip = None

    # Lấy IP gốc TRƯỚC KHI setup proxy (để so sánh sau)
    # DISABLED: Proxy đã hoạt động đúng, không cần verify nữa
    # if proxy_info:
    #     original_ip = get_original_ip()

    if proxy_info:
        proxy_http = proxy_info.get("http")
        if proxy_http:
            parts = proxy_http.split(":")
            if len(parts) == 4:
                proxy_host = parts[0]
                proxy_port = parts[1]
                proxy_user = parts[2]
                proxy_pass = parts[3]
                proxy_ip_to_verify = proxy_info.get("real_ip")

                print(f"[Proxy] Đang khởi động local proxy server...")
                print(f"[Proxy] Upstream: {proxy_host}:{proxy_port}")
                print(f"[Proxy] Username: {proxy_user}")

                # Khởi động local proxy server
                local_proxy_port = start_local_proxy_server(
                    upstream_host=proxy_host,
                    upstream_port=proxy_port,
                    username=proxy_user,
                    password=proxy_pass,
                    local_port=18888
                )

    # Setup Chrome với proxy
    # DISABLED: undetected-chromedriver bị lỗi SSL certificate với proxy
    # if UC_AVAILABLE:
    #     print("Đang sử dụng undetected-chromedriver với local proxy")
    #
    #     options = uc.ChromeOptions()
    #
    #     if local_proxy_port:
    #         # Dùng local proxy (không cần auth vì local)
    #         options.add_argument(f'--proxy-server=http://127.0.0.1:{local_proxy_port}')
    #         print(f"✓ Chrome sẽ dùng local proxy: 127.0.0.1:{local_proxy_port}")
    #
    #     try:
    #         driver = uc.Chrome(options=options, version_main=None)
    #         print("✓ Đã khởi tạo undetected Chrome driver")
    #
    #         return driver
    #     except Exception as e:
    #         print(f"⚠ Lỗi khi khởi tạo undetected driver: {str(e)}")
    #         print("  Fallback sang Selenium thông thường...")

    # Sử dụng Selenium thông thường (không dùng undetected-chromedriver)
    print("Đang sử dụng Selenium Chrome driver")
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    if local_proxy_port:
        chrome_options.add_argument(f'--proxy-server=http://127.0.0.1:{local_proxy_port}')
        print(f"✓ Chrome sẽ dùng local proxy: 127.0.0.1:{local_proxy_port}")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        driver = webdriver.Chrome(options=chrome_options)

    # Verify proxy
    # DISABLED: Proxy đã hoạt động đúng, không cần verify nữa để chạy nhanh hơn
    # if local_proxy_port:
    #     print("[Proxy] Đang đợi proxy khởi tạo (5 giây)...")
    #     time.sleep(5)
    #     verify_result = verify_proxy_is_working(driver, proxy_ip_to_verify, original_ip)
    #     if verify_result == True:
    #         print("[Proxy] ✅ PROXY HOẠT ĐỘNG HOÀN HẢO - IP đã thay đổi!")
    #     elif verify_result == False:
    #         print("\n" + "!"*60)
    #         print("❌ CẢNH BÁO: PROXY KHÔNG HOẠT ĐỘNG!")
    #         print("!"*60 + "\n")

    return driver

def read_all_emails(email_file=EMAIL_FILE):
    """
    Đọc tất cả email credentials từ file
    Format BẮT BUỘC: email|password|refresh_token|client_id
    Ví dụ: user@hotmail.com|pass123|M.C555_BAY...|9e5f94bc-...

    Returns: List of tuples (email, password, refresh_token, client_id)
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
                print(f"   Format yêu cầu: email|password|refresh_token|client_id")
                print(f"   Dòng hiện tại: {line[:100]}...")
                continue

            email = parts[0].strip()
            password = parts[1].strip()
            refresh_token = parts[2].strip()
            client_id = parts[3].strip()

            # Validate các field không được rỗng
            if not email or not password or not refresh_token or not client_id:
                print(f"✗ Dòng {idx}: Bỏ qua - có field rỗng")
                print(f"   Email: {email}")
                continue

            emails.append((email, password, refresh_token, client_id))

        return emails

    except Exception as e:
        print(f"✗ Lỗi khi đọc file {email_file}: {str(e)}")
        return []

def paste_to_dongvanfb(driver, full_line, wait_time=10):
    """
    Mở trang https://dongvanfb.net/read_mail_box và paste data vào textarea

    Args:
        driver: WebDriver instance
        full_line: Toàn bộ dòng từ products.txt (email|password|token|uuid|timestamp)
        wait_time: Timeout để tìm textarea

    Returns:
        True nếu thành công, False nếu thất bại
    """
    try:
        print("\n[DongVanFB] Đang mở trang dongvanfb.net/read_mail_box...")

        # Mở trang dongvanfb
        driver.get("https://dongvanfb.net/read_mail_box")

        # Đợi trang load
        wait = WebDriverWait(driver, wait_time)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(1)
        print("✓ Trang dongvanfb đã load")

        # Tìm textarea với id="list_email"
        print("[DongVanFB] Đang tìm textarea #list_email...")
        textarea_selectors = [
            (By.ID, "list_email"),
            (By.NAME, "list_email"),
            (By.XPATH, "//textarea[@id='list_email']"),
            (By.XPATH, "//textarea[@name='list_email']"),
            (By.CSS_SELECTOR, "textarea#list_email"),
        ]

        textarea = None
        for by, selector in textarea_selectors:
            try:
                textarea = wait.until(EC.presence_of_element_located((by, selector)))
                print("✓ Tìm thấy textarea #list_email")
                break
            except TimeoutException:
                continue

        if not textarea:
            print("✗ Không tìm thấy textarea #list_email")
            return False

        # Scroll đến textarea
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", textarea)
        time.sleep(0.3)

        # Clear và paste data
        print(f"[DongVanFB] Đang paste data: {full_line[:60]}...")
        textarea.clear()
        textarea.send_keys(full_line)
        print("✓ Đã paste data vào textarea")

        # Đợi một chút để đảm bảo data được nhập
        time.sleep(1)

        print("✓ Hoàn thành paste data vào dongvanfb.net")
        return True

    except Exception as e:
        print(f"✗ Lỗi khi paste vào dongvanfb: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# DEPRECATED: Function này dùng API cũ /api/get_code_oauth2 (không hoạt động nữa)
# Thay vào đó dùng wait_for_bitbucket_code() từ email_api_helper.py
# def get_sms_from_api(email, refresh_token, client_id, max_retries=10, retry_delay=5):
#     """
#     [DEPRECATED] Lấy mã SMS từ API dongvanfb
#     API này không còn hoạt động, trả về status=False
#     Dùng wait_for_bitbucket_code() từ email_api_helper.py thay thế
#     """
#     pass

def get_sms_from_dongvanfb(driver, dongvanfb_tab, atlassian_tab, wait_time=30):
    """
    Đọc SMS code từ trang dongvanfb.net/read_mail_box
    - Click nút "Đọc hòm thư" 2 lần, mỗi lần cách nhau 3s
    - Parse email content từ <td class="text-left content_email readmail_content">
    - Tìm pattern "XXXXXX is" để lấy verification code

    Returns: SMS code (string) hoặc None nếu không tìm thấy
    """
    import re

    try:
        print(f"\n📧 Đang chuyển sang tab dongvanfb để đọc SMS...")
        driver.switch_to.window(dongvanfb_tab)
        time.sleep(1)

        # Log current URL để debug
        current_url = driver.current_url
        print(f"URL hiện tại: {current_url}")

        # KHÔNG RELOAD - chỉ tìm và click nút "Đọc hòm thư"
        wait = WebDriverWait(driver, wait_time)

        # Click nút "Đọc hòm thư" lần 1
        print("🔄 Click nút 'Đọc hòm thư' lần 1...")
        button_selectors = [
            # Selector chính xác theo HTML: <button class="btn-buy-home mt-2 btn-checked">
            (By.XPATH, "//button[@class='btn-buy-home mt-2 btn-checked' and contains(text(), 'Đọc hòm thư')]"),
            (By.XPATH, "//div[@class='box-button-item']//button[contains(text(), 'Đọc hòm thư')]"),
            (By.XPATH, "//button[contains(@class, 'btn-buy-home') and contains(@class, 'mt-2') and contains(@class, 'btn-checked')]"),
            (By.XPATH, "//button[contains(@class, 'btn-buy-home') and contains(@class, 'btn-checked') and contains(text(), 'Đọc hòm thư')]"),
            (By.XPATH, "//button[contains(@class, 'btn-buy-home') and contains(text(), 'Đọc hòm thư')]"),
            (By.XPATH, "//button[contains(text(), 'Đọc hòm thư')]"),
        ]

        button_found = False
        for by, selector in button_selectors:
            try:
                button = wait.until(EC.element_to_be_clickable((by, selector)))
                button.click()
                print("✓ Đã click lần 1")
                button_found = True
                break
            except Exception as e:
                continue

        if not button_found:
            print("✗ Không tìm thấy nút 'Đọc hòm thư'")
            print(f"⚠ HTML snapshot: {driver.page_source[:500]}")  # Debug: show first 500 chars
            driver.switch_to.window(atlassian_tab)
            return None

        # Đợi 3 giây
        print("⏳ Đợi 3 giây...")
        time.sleep(3)

        # Click nút "Đọc hòm thư" lần 2
        print("🔄 Click nút 'Đọc hòm thư' lần 2...")
        for by, selector in button_selectors:
            try:
                button = wait.until(EC.element_to_be_clickable((by, selector)))
                button.click()
                print("✓ Đã click lần 2")
                break
            except Exception as e:
                continue

        # Đợi thêm 2 giây cho email load
        print("⏳ Đợi email load...")
        time.sleep(2)

        # Parse email content từ <td class="text-left content_email readmail_content">
        print("🔍 Đang tìm email content...")
        content_selectors = [
            (By.XPATH, "//td[contains(@class, 'content_email') and contains(@class, 'readmail_content')]"),
            (By.CLASS_NAME, "readmail_content"),
            (By.CLASS_NAME, "content_email"),
        ]

        email_content = None
        for by, selector in content_selectors:
            try:
                element = wait.until(EC.presence_of_element_located((by, selector)))
                email_content = element.text
                print(f"✓ Tìm thấy email content: {email_content[:100]}...")
                break
            except Exception as e:
                continue

        if not email_content:
            print("✗ Không tìm thấy email content")
            driver.switch_to.window(atlassian_tab)
            return None

        # Tìm verification code với pattern "XXXXXX is"
        # Pattern: 6 ký tự chữ hoặc số, theo sau bởi " is"
        pattern = r'\b([A-Z0-9]{6})\s+is\b'
        match = re.search(pattern, email_content, re.IGNORECASE)

        if match:
            sms_code = match.group(1).upper()
            print(f"✓ Tìm thấy verification code: {sms_code}")

            # Switch về tab Atlassian
            print(f"🔄 Chuyển về tab Atlassian...")
            driver.switch_to.window(atlassian_tab)
            time.sleep(1)

            return sms_code
        else:
            print("✗ Không tìm thấy verification code trong email")
            print(f"Email content: {email_content}")
            driver.switch_to.window(atlassian_tab)
            return None

    except Exception as e:
        print(f"✗ Lỗi khi đọc SMS từ dongvanfb: {str(e)}")
        # Đảm bảo switch về tab Atlassian
        try:
            driver.switch_to.window(atlassian_tab)
        except:
            pass
        return None

def check_and_restart_driver(driver, proxy_info=None):
    """Kiểm tra driver session và khởi động lại nếu cần"""
    if driver is None:
        print("⚠ Driver là None, đang khởi động driver mới...")
        driver = setup_chrome_driver(proxy_info)
        set_window_position(driver)
        print("✓ Đã khởi động driver mới")
        return driver, True

    try:
        _ = driver.current_url
        return driver, False
    except Exception as e:
        print(f"⚠ Driver session bị mất ({str(e)}), đang đóng Chrome hoàn toàn...")

        try:
            handles = driver.window_handles
            if handles:
                for handle in handles:
                    try:
                        driver.switch_to.window(handle)
                        driver.close()
                    except:
                        pass
        except:
            pass

        time.sleep(0.6)

        try:
            driver.quit()
            print("✓ Đã gọi driver.quit() để đóng Chrome")
        except Exception as e_quit:
            print(f"⚠ Lỗi khi gọi driver.quit(): {str(e_quit)}")
            try:
                import subprocess
                import platform
                system = platform.system()
                if system == "Darwin":  # macOS
                    subprocess.run(["pkill", "-f", "Google Chrome"], check=False)
                    print("✓ Đã thử force kill Chrome process (macOS)")
                elif system == "Windows":  # Windows
                    subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], check=False, 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe", "/T"], check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print("✓ Đã thử force kill Chrome process (Windows)")
                elif system == "Linux":  # Linux
                    subprocess.run(["pkill", "-f", "chrome"], check=False)
                    print("✓ Đã thử force kill Chrome process (Linux)")
            except:
                pass

        print("Đang đợi Chrome đóng hoàn toàn...")
        time.sleep(1.8)

        print("Đang khởi động lại Chrome driver...")
        try:
            driver = setup_chrome_driver(proxy_info)
            set_window_position(driver)
            print("✓ Đã khởi động lại driver thành công")
            return driver, True
        except Exception as e_setup:
            print(f"✗ Lỗi khi khởi động lại driver: {str(e_setup)}")
            time.sleep(1.2)
            try:
                driver = setup_chrome_driver(proxy_info)
                set_window_position(driver)
                print("✓ Đã khởi động lại driver thành công (lần thử thứ 2)")
                return driver, True
            except Exception as e_setup2:
                print(f"✗ Không thể khởi động lại driver sau 2 lần thử: {str(e_setup2)}")
                raise

def click_bitbucket_button(driver, wait_time=3):
    """Tìm và click nút Bitbucket trên trang All-Hands.dev"""
    try:
        wait = WebDriverWait(driver, wait_time)

        # Selector đơn giản ưu tiên cho lần click thứ 2
        selectors = [
            (By.XPATH, "//button[contains(text(), 'Bitbucket')]"),
            (By.XPATH, "//button[@type='button' and contains(., 'Bitbucket')]"),
            (By.XPATH, "//button[text()='Se connecter à Bitbucket']"),
            (By.XPATH, "//button[contains(text(), 'Se connecter à Bitbucket')]"),
            (By.XPATH, "//button[contains(@class, 'p-2') and contains(@class, 'text-sm') and contains(@class, 'rounded-sm')]"),
            (By.CSS_SELECTOR, "button.p-2.text-sm"),
            (By.CSS_SELECTOR, "button.rounded-sm"),
        ]

        button = None
        for by, selector in selectors:
            try:
                button = wait.until(EC.element_to_be_clickable((by, selector)))
                print(f"✓ Tìm thấy nút Bitbucket bằng selector: {selector}")
                break
            except TimeoutException:
                continue

        if not button:
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if "bitbucket" in btn.text.lower():
                        button = btn
                        print("✓ Tìm thấy nút Bitbucket bằng cách tìm tất cả button")
                        break
            except Exception as e:
                print(f"Lỗi khi tìm button: {e}")

        if button:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", button)
            time.sleep(0.3)
            try:
                button.click()
                print("✓ Đã click nút Bitbucket thành công!")
            except Exception:
                driver.execute_script("arguments[0].click();", button)
                print("✓ Đã click nút Bitbucket (bằng JavaScript)")
            return True
        else:
            print("✗ Không tìm thấy nút Bitbucket")
            return False

    except Exception as e:
        print(f"✗ Lỗi khi click nút Bitbucket: {str(e)}")
        return False

def wait_for_atlassian_redirect(driver, timeout=15):
    """Đợi redirect sang trang Atlassian login"""
    try:
        print("Đang đợi redirect sang Atlassian...")

        WebDriverWait(driver, timeout).until(
            lambda d: "atlassian.com" in d.current_url or "id.atlassian" in d.current_url
        )

        current_url = driver.current_url
        print(f"✓ Đã redirect tới: {current_url}")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        time.sleep(2)
        print("✓ Trang Atlassian đã load thành công")
        return True

    except TimeoutException:
        print(f"✗ Timeout khi đợi redirect sang Atlassian. URL hiện tại: {driver.current_url}")
        return False
    except Exception as e:
        print(f"✗ Lỗi khi đợi redirect sang Atlassian: {str(e)}")
        return False

def login_bitbucket(driver, email, password, refresh_token, client_id, wait_time=15):
    """Đăng nhập trực tiếp vào Bitbucket/Atlassian với email và password

    Args:
        driver: WebDriver instance
        email: Email để đăng nhập
        password: Password
        refresh_token: OAuth2 refresh token để lấy SMS qua API
        client_id: Client ID cho API
        wait_time: Timeout
    """
    try:
        wait = WebDriverWait(driver, wait_time)
        atlassian_tab = driver.current_window_handle  # Lưu tab Atlassian

        # Bước 1: Tìm và điền email
        print("\n[Bitbucket Login 1/5] Đang tìm field email...")
        email_selectors = [
            (By.ID, "username-uid1"),
            (By.NAME, "username"),
            (By.XPATH, "//input[@type='email' and @name='username']"),
            (By.XPATH, "//input[@id='username-uid1']"),
            (By.XPATH, "//input[@autocomplete='username']"),
            (By.XPATH, "//input[@placeholder='Nhập email của bạn']"),
        ]

        email_field = None
        for by, selector in email_selectors:
            try:
                email_field = wait.until(EC.presence_of_element_located((by, selector)))
                print(f"✓ Tìm thấy email field")
                break
            except TimeoutException:
                continue

        if not email_field:
            print("✗ Không tìm thấy email field")
            return False

        # Điền email
        print(f"Đang điền email: {email}")
        smooth_scroll(driver, email_field)
        random_delay(delay_type='short')
        human_like_type(email_field, email)

        # Delay 0.3-0.5s sau khi nhập email (TURBO: giảm từ 1-1.5s)
        delay_after_typing = random.uniform(0.3, 0.5) if TURBO_MODE else random.uniform(1, 1.5)
        print(f"⏱️  Đợi {delay_after_typing:.1f}s sau khi nhập email...")
        time.sleep(delay_after_typing)

        # Bước 2: Click nút Continue
        print("\n[Bitbucket Login 2/5] Đang tìm nút 'Continue'...")
        continue_selectors = [
            (By.ID, "login-submit"),
            (By.XPATH, "//button[@id='login-submit']"),
            (By.XPATH, "//button[@type='submit']"),
            (By.XPATH, "//button[contains(text(), 'Continue')]"),
            (By.XPATH, "//span[contains(text(), 'Continue')]/parent::button"),
        ]

        continue_button = None
        for by, selector in continue_selectors:
            try:
                continue_button = wait.until(EC.element_to_be_clickable((by, selector)))
                print("✓ Tìm thấy nút 'Continue'")
                break
            except TimeoutException:
                continue

        if continue_button:
            try:
                continue_button.click()
                print("✓ Đã click nút 'Continue'")
            except:
                driver.execute_script("arguments[0].click();", continue_button)
                print("✓ Đã click nút 'Continue' (JavaScript)")
        else:
            email_field.send_keys(Keys.RETURN)
            print("✓ Đã nhấn Enter trên email field")

        # Đợi trang load sau Continue (TURBO: 0.3s, normal: 1s)
        time.sleep(0.3 if TURBO_MODE else 1)

        # Bước 3: Click nút "Sign up" (nếu có) - Timeout 3s
        print("\n[Bitbucket Login 3/5] Đang tìm nút 'Sign up' (timeout 3s)...")
        signup_selectors = [
            (By.XPATH, "//span[@class='css-178ag6o' and contains(text(), 'Sign up')]"),
            (By.XPATH, "//span[contains(@class, 'css-178ag6o') and contains(text(), 'Sign up')]"),
            (By.XPATH, "//button[.//span[contains(text(), 'Sign up')]]"),
            (By.XPATH, "//button[contains(., 'Sign up')]"),
            (By.XPATH, "//span[contains(text(), 'Sign up')]/ancestor::button"),
        ]

        signup_button = None
        signup_wait = WebDriverWait(driver, 3)  # Chỉ đợi 3 giây
        for by, selector in signup_selectors:
            try:
                signup_button = signup_wait.until(EC.element_to_be_clickable((by, selector)))
                print("✓ Tìm thấy nút 'Sign up'")
                break
            except TimeoutException:
                continue

        if not signup_button:
            print("⚠ Không tìm thấy nút 'Sign up' sau 3s, tiếp tục...")
        else:
            try:
                signup_button.click()
                print("✓ Đã click nút 'Sign up'")
            except:
                driver.execute_script("arguments[0].click();", signup_button)
                print("✓ Đã click nút 'Sign up' (JavaScript)")

            # Đợi trang load sau Sign up (TURBO: 0.3s, normal: 1s)
            time.sleep(0.3 if TURBO_MODE else 1)

        # CAPTCHA Check sau Sign up - Dùng function đã cải tiến
        print("\n[CAPTCHA Check] Đang kiểm tra CAPTCHA sau Sign up...")
        wait_for_manual_captcha_solve(driver, timeout=30, auto_click_button=True)

        # Bước 4: Lấy SMS code từ API messages (thay vì API get_code)
        print("\n[Bitbucket Login 4/5] Đang lấy mã SMS từ API messages...")

        # Callback function để click "Resend email" sau N lần thất bại
        def click_resend_email():
            """Click 'Didn't receive an email? Resend email' button"""
            try:
                resend_selectors = [
                    # Selector chính xác theo HTML: <span class="css-1gd7hga">Didn't receive an email? Resend email</span>
                    (By.XPATH, "//span[contains(@class, 'css-1gd7hga') and contains(text(), 'Resend')]"),
                    (By.XPATH, "//span[contains(text(), \"Didn't receive an email\")]"),
                    (By.XPATH, "//*[contains(text(), \"Didn't receive an email\")]"),
                    (By.XPATH, "//span[contains(text(), 'Resend email')]"),
                    (By.XPATH, "//button[contains(text(), 'Resend email')]"),
                    (By.CSS_SELECTOR, "span.css-1gd7hga"),
                ]
                
                for by, selector in resend_selectors:
                    try:
                        resend_elem = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((by, selector))
                        )
                        try:
                            resend_elem.click()
                        except:
                            driver.execute_script("arguments[0].click();", resend_elem)
                        print("✓ Đã click 'Resend email'")
                        time.sleep(2)  # Đợi email mới được gửi
                        return True
                    except:
                        continue
                
                print("⚠ Không tìm thấy nút 'Resend email'")
                return False
            except Exception as e:
                print(f"✗ Lỗi khi click Resend email: {str(e)}")
                return False

        # Dùng wait_for_bitbucket_code từ email_api_helper với resend callback
        sms_code = wait_for_bitbucket_code(
            email=email,
            refresh_token=refresh_token,
            client_id=client_id,
            max_wait=120,  # Đợi tối đa 120s
            check_interval=5,  # Check mỗi 5s
            resend_callback=click_resend_email,  # Callback để click Resend
            resend_after_attempts=4  # Sau 4 lần check thất bại → click Resend
        )

        # Nếu có SMS code, điền vào 6 ô OTP riêng biệt
        if sms_code and len(sms_code) == 6:
            print(f"\n[Bitbucket Login 5/5] Đang điền mã SMS: {sms_code}")

            # Tìm 6 ô OTP input
            otp_inputs = []
            for i in range(6):
                otp_selectors = [
                    (By.XPATH, f"//input[@data-testid='otp-input-index-{i}']"),
                    (By.XPATH, f"//input[@aria-label='Please enter OTP character {i+1}']"),
                    (By.XPATH, f"(//input[@maxlength='1' and @type='text'])[{i+1}]"),
                ]

                otp_input = None
                for by, selector in otp_selectors:
                    try:
                        otp_input = wait.until(EC.presence_of_element_located((by, selector)))
                        otp_inputs.append(otp_input)
                        print(f"✓ Tìm thấy OTP input {i+1}")
                        break
                    except TimeoutException:
                        continue

                if not otp_input:
                    print(f"✗ Không tìm thấy OTP input {i+1}")
                    break

            # Điền từng ký tự vào từng ô
            if len(otp_inputs) == 6:
                for i, char in enumerate(sms_code):
                    try:
                        otp_inputs[i].clear()
                        otp_inputs[i].send_keys(char)
                        time.sleep(0.2)  # Delay nhỏ giữa các ký tự
                    except Exception as e:
                        print(f"✗ Lỗi khi điền ký tự {i+1}: {str(e)}")

                print("✓ Đã điền tất cả 6 ký tự OTP")

                # Đợi trang load (giảm từ 2s xuống 1s)
                time.sleep(1)

                # Sau OTP: Điền username và password
                print("\n[Bitbucket Login 6/7] Đang điền username và password...")

                # Bước 6.1: Tạo username từ email (chia đôi)
                # VD: mamqotevotf@hotmail.com → "mamqotevotf" → "mamqot evotf"
                email_prefix = email.split('@')[0]  # "mamqotevotf"
                mid_point = len(email_prefix) // 2
                username = email_prefix[:mid_point] + " " + email_prefix[mid_point:]
                print(f"Username được tạo: {username}")

                # Bước 6.2: Tìm và điền username
                username_selectors = [
                    (By.NAME, "displayName"),
                    (By.ID, "displayName"),
                    (By.XPATH, "//input[@name='displayName']"),
                    (By.XPATH, "//input[@placeholder='Enter your name']"),
                    (By.XPATH, "//input[@type='text' and @name='displayName']"),
                ]

                username_field = None
                for by, selector in username_selectors:
                    try:
                        username_field = wait.until(EC.presence_of_element_located((by, selector)))
                        print("✓ Tìm thấy username field")
                        break
                    except TimeoutException:
                        continue

                if username_field:
                    smooth_scroll(driver, username_field)
                    random_delay(delay_type='short')
                    username_field.clear()
                    human_like_type(username_field, username)
                    print(f"✓ Đã điền username: {username}")
                else:
                    print("⚠ Không tìm thấy username field")

                # Bước 6.3: Tìm và điền password
                password_selectors = [
                    (By.NAME, "password"),
                    (By.ID, "password"),
                    (By.XPATH, "//input[@type='password']"),
                    (By.XPATH, "//input[@name='password']"),
                    (By.XPATH, "//input[@autocomplete='new-password']"),
                ]

                password_field = None
                for by, selector in password_selectors:
                    try:
                        password_field = wait.until(EC.presence_of_element_located((by, selector)))
                        print("✓ Tìm thấy password field")
                        break
                    except TimeoutException:
                        continue

                if password_field:
                    smooth_scroll(driver, password_field)
                    random_delay(delay_type='short')
                    password_field.clear()
                    human_like_type(password_field, password)
                    print("✓ Đã điền password")
                else:
                    print("⚠ Không tìm thấy password field")

                # Bước 6.4: Click nút "Continue"
                print("\n[Bitbucket Login 7/7] Đang tìm nút 'Continue'...")
                continue_selectors = [
                    (By.XPATH, "//span[@class='css-178ag6o' and contains(text(), 'Continue')]"),
                    (By.XPATH, "//button[.//span[contains(text(), 'Continue')]]"),
                    (By.XPATH, "//button[contains(text(), 'Continue')]"),
                    (By.XPATH, "//button[@type='submit']"),
                    (By.ID, "login-submit"),
                ]

                continue_button = None
                for by, selector in continue_selectors:
                    try:
                        continue_button = wait.until(EC.element_to_be_clickable((by, selector)))
                        print("✓ Tìm thấy nút 'Continue'")
                        break
                    except TimeoutException:
                        continue

                if continue_button:
                    try:
                        continue_button.click()
                        print("✓ Đã click nút Continue")
                    except:
                        driver.execute_script("arguments[0].click();", continue_button)
                        print("✓ Đã click nút Continue (JavaScript)")
                else:
                    print("⚠ Không tìm thấy nút Continue, thử nhấn Enter")
                    if password_field:
                        password_field.send_keys(Keys.RETURN)

                time.sleep(1)  # Giảm từ 2s xuống 1s
            else:
                print(f"✗ Chỉ tìm thấy {len(otp_inputs)}/6 OTP inputs")
        else:
            print("⚠ Không có mã SMS hoặc mã không đúng 6 ký tự")

        # Hoàn thành
        print("\n✓ Đã hoàn thành đăng nhập Bitbucket!")
        return True

    except Exception as e:
        print(f"\n✗ Lỗi khi đăng nhập Bitbucket: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def handle_post_login_steps(driver, email, password, refresh_token=None, client_id=None):
    """
    Xử lý các bước sau khi đăng nhập Bitbucket thành công

    Luồng mới (2026-01):
    1. Click "Grant access" (nếu có)
    2. Click "Resend verification"
    3. Verify email qua API (lấy verification link)
    4. Mở tab mới và navigate đến URL auth để login
    5. Redirect về app.all-hands.dev (tự động đã login)
    6. Click checkbox Terms of Service
    7. Click "Continuer"
    8. Lấy API key và lưu vào file
    """
    try:
        print("\n=== BẮT ĐẦU CÁC BƯỚC SAU ĐĂNG NHẬP ===")
        wait = WebDriverWait(driver, 10 if TURBO_MODE else 20)  # TURBO: giảm timeout
        allhands_tab = driver.current_window_handle  # Lưu tab All-Hands

        # Bước 1: Click nút "Grant access" (nếu có)
        print("\n[Post-Login 1/6] Đang tìm nút 'Grant access'...")
        grant_access_selectors = [
            (By.XPATH, "//button[@type='submit' and @name='action' and @value='approve']"),
            (By.XPATH, "//button[contains(@class, 'aui-button-primary') and @name='action' and @value='approve']"),
            (By.XPATH, "//button[contains(., 'Grant access')]"),
            (By.XPATH, "//button[@type='submit' and contains(., 'Grant access')]"),
            (By.XPATH, "//button[contains(text(), 'Grant access')]"),
        ]

        grant_button = None
        for by, selector in grant_access_selectors:
            try:
                grant_button = wait.until(EC.element_to_be_clickable((by, selector)))
                print(f"✓ Tìm thấy nút 'Grant access'")
                break
            except TimeoutException:
                continue

        if not grant_button:
            # Fallback
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if "grant access" in btn.text.lower():
                        grant_button = btn
                        print("✓ Tìm thấy nút 'Grant access' (fallback)")
                        break
            except:
                pass

        if grant_button:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", grant_button)
            random_delay(delay_type='short')
            try:
                grant_button.click()
                print("✓ Đã click nút 'Grant access'")
            except:
                driver.execute_script("arguments[0].click();", grant_button)
                print("✓ Đã click nút 'Grant access' (JavaScript)")

            # ĐỢI VÀ CHECK xem đã redirect chưa trước khi tiếp tục
            print("Đang đợi redirect sau khi Grant access...")
            redirect_wait_time = 3 if TURBO_MODE else 5
            for i in range(redirect_wait_time):
                time.sleep(1)
                current_url = driver.current_url
                if "all-hands.dev" in current_url:
                    print(f"✓ Đã bắt đầu redirect sau {i+1}s")
                    break
                print(f"  Đang đợi... ({i+1}s)")
        else:
            print("⚠ Không tìm thấy nút 'Grant access', có thể đã ở bước tiếp theo")

        # Đợi redirect về All-Hands.dev (TURBO: 0.5s, normal: 2s)
        print("\nĐang đợi redirect về All-Hands.dev...")
        time.sleep(0.5 if TURBO_MODE else 2)

        # Bước 1.5: Kiểm tra email verification TRƯỚC
        print("\n[Post-Login 1.5/6] Kiểm tra email verification trước...")
        print("🔍 Check email...")
        verify_link_early = wait_for_openhands_link(
            email=email,
            refresh_token=refresh_token,
            client_id=client_id,
            max_wait=10,  # Đợi ngắn - chỉ 10s
            check_interval=3
        )

        if verify_link_early:
            print("✓ Đã có email verification sẵn! Bỏ qua check Bitbucket & Resend.")
            verify_link = verify_link_early
            skip_resend = True
        else:
            print("⚠ Chưa có email → Kiểm tra Bitbucket lại...")
            verify_link = None
            skip_resend = False

            # Kiểm tra xem có cần chọn Bitbucket lại không
            print("\n[Post-Login 1.6/6] Kiểm tra xem có cần chọn Bitbucket lại không...")
            bitbucket_check_selectors = [
                (By.XPATH, "//button[contains(text(), 'Bitbucket')]"),
                (By.XPATH, "//button[@type='button' and contains(., 'Bitbucket')]"),
                (By.XPATH, "//button[text()='Se connecter à Bitbucket']"),
                (By.XPATH, "//button[contains(text(), 'Se connecter à Bitbucket')]"),
            ]

            bitbucket_button_again = None
            short_wait = WebDriverWait(driver, 5)  # Timeout ngắn, chỉ 5s
            for by, selector in bitbucket_check_selectors:
                try:
                    bitbucket_button_again = short_wait.until(EC.element_to_be_clickable((by, selector)))
                    print("⚠ Phát hiện trang yêu cầu chọn Bitbucket lại!")
                    break
                except TimeoutException:
                    continue

            if bitbucket_button_again:
                # Click Bitbucket lại
                try:
                    bitbucket_button_again.click()
                    print("✓ Đã click Bitbucket lại")
                    time.sleep(2)
                except:
                    driver.execute_script("arguments[0].click();", bitbucket_button_again)
                    print("✓ Đã click Bitbucket lại (JavaScript)")
                    time.sleep(2)
            else:
                print("✓ Không cần login lại, tiếp tục với Resend verification...")

        # Bước 2: Click "Resend verification" nếu cần
        if not skip_resend:
            print("\n[Post-Login 2.5/6] Đang tìm nút 'Resend verification'...")
            resend_selectors = [
                (By.XPATH, "//button[@type='button' and contains(@class, 'bg-primary') and contains(text(), 'Resend verification')]"),
                (By.XPATH, "//button[contains(@class, 'bg-primary') and contains(., 'Resend verification')]"),
                (By.XPATH, "//button[contains(text(), 'Resend verification')]"),
            ]

            resend_button = None
            for by, selector in resend_selectors:
                try:
                    resend_button = wait.until(EC.element_to_be_clickable((by, selector)))
                    print("✓ Tìm thấy nút 'Resend verification'")
                    break
                except TimeoutException:
                    continue

            if resend_button:
                try:
                    resend_button.click()
                    print("✓ Đã click nút 'Resend verification'")
                except:
                    driver.execute_script("arguments[0].click();", resend_button)
                    print("✓ Đã click nút 'Resend verification' (JavaScript)")
                time.sleep(2)  # Giảm từ 3s xuống 2s
            else:
                print("⚠ Không tìm thấy nút 'Resend verification', bỏ qua...")
        else:
            print("\n[Post-Login 2.5/6] ✓ Bỏ qua Resend - đã có email verification sẵn")

        # Bước 3: Verify email qua API (nếu chưa có từ bước 2)
        if not verify_link:
            print("\n[Post-Login 3/6] Đang lấy verification link qua API...")

            # Đợi và lấy verification link từ email
            verify_link = wait_for_openhands_link(
                email=email,
                refresh_token=refresh_token,
                client_id=client_id,
                max_wait=120,
                check_interval=5
            )
        else:
            print("\n[Post-Login 3/6] ✓ Đã có verification link từ check sớm")

        if not verify_link:
            print("✗ Không nhận được email verification sau 120s")
            print("⚠ Thử tiếp tục với các bước tiếp theo...")
        else:
            print(f"✓ Đã lấy verification link qua API")

            # Mở verification link trong browser
            print("🔄 Đang mở verification link...")
            driver.get(verify_link)
            time.sleep(0.5 if TURBO_MODE else 1.5)  # Giảm: mở verification link

            # Click "Click here to proceed" (nếu có)
            print("🔄 Đang tìm link 'Click here to proceed'...")
            try:
                proceed_selectors = [
                    (By.XPATH, "//div[@id='kc-info-message']//a[contains(., 'Click here to proceed')]"),
                    (By.XPATH, "//a[contains(text(), 'Click here to proceed')]"),
                    (By.XPATH, "//a[contains(@href, 'action-token') and contains(., 'Click')]"),
                ]

                proceed_link = None
                for by, sel in proceed_selectors:
                    try:
                        proceed_link = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((by, sel))
                        )
                        print("✓ Tìm thấy link 'Click here to proceed'")
                        break
                    except:
                        continue

                if proceed_link:
                    proceed_link.click()
                    print("✓ Đã click 'Click here to proceed'")
                    time.sleep(0.3 if TURBO_MODE else 1.5)  # TURBO: 0.3s, normal: 1.5s
                else:
                    print("⚠ Không tìm thấy link 'Click here to proceed', bỏ qua...")
            except Exception as e:
                print(f"⚠ Lỗi khi click 'Click here to proceed': {str(e)}")

            # Click "Back to Application"
            print("🔄 Đang tìm link 'Back to Application'...")
            try:
                back_selectors = [
                    (By.XPATH, "//a[contains(@href, 'app.all-hands.dev') and contains(., 'Back to Application')]"),
                    (By.XPATH, "//a[contains(text(), 'Back to Application')]"),
                    (By.XPATH, "//a[contains(@href, 'email_verified=true')]"),
                ]

                back_link = None
                for by, sel in back_selectors:
                    try:
                        back_link = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((by, sel))
                        )
                        print("✓ Tìm thấy link 'Back to Application'")
                        break
                    except:
                        continue

                if back_link:
                    back_link.click()
                    print("✓ Đã click 'Back to Application'")
                    time.sleep(0.5 if TURBO_MODE else 2)  # TURBO: 0.5s, normal: 2s
                else:
                    print("⚠ Không tìm thấy link 'Back to Application', thử navigate trực tiếp...")
                    driver.get("https://app.all-hands.dev/?email_verified=true")
                    time.sleep(0.5 if TURBO_MODE else 2)  # TURBO: 0.5s, normal: 2s
            except Exception as e:
                print(f"⚠ Lỗi khi click 'Back to Application': {str(e)}")

            print("✓ Hoàn thành verify email qua API")

        # Bước 3.5: Mở tab mới và navigate đến URL auth để login
        print("\n[Post-Login 3.5/6] Đang mở tab mới với URL auth để login...")

        # Mở tab mới
        driver.execute_script("window.open('');")

        # Switch sang tab mới
        new_tab = driver.window_handles[-1]
        driver.switch_to.window(new_tab)

        # Navigate đến URL auth
        auth_url = "https://auth.app.all-hands.dev/realms/allhands/protocol/openid-connect/auth?client_id=allhands&kc_idp_hint=bitbucket&response_type=code&redirect_uri=https%3A%2F%2Fapp.all-hands.dev%2Foauth%2Fkeycloak%2Fcallback&scope=openid+email+profile&state=https%3A%2F%2Fapp.all-hands.dev%3Flogin_method%3Dbitbucket&login_method=bitbucket"
        print(f"Đang navigate đến: {auth_url[:80]}...")
        driver.get(auth_url)
        print("✓ Đã mở tab mới và navigate đến URL auth")

        # Đợi redirect về app (tự động login) - TURBO: 0.5s, normal: 2s
        print("Đang đợi redirect về app.all-hands.dev...")
        time.sleep(0.5 if TURBO_MODE else 2)

        try:
            WebDriverWait(driver, 10).until(
                lambda d: "app.all-hands.dev" in d.current_url
            )
            print(f"✓ Đã về trang app: {driver.current_url}")
        except:
            print(f"⚠ Chưa về app. URL hiện tại: {driver.current_url}")

        time.sleep(1.5)  # Giảm từ 2s xuống 1.5s

        # Bước 4: Đợi trang all-hands.dev sẵn sàng và click checkbox chấp nhận điều khoản
        print("\n[Post-Login 4/6] Đang kiểm tra trang All-Hands.dev...")

        # Kiểm tra URL hiện tại
        try:
            current_url = driver.current_url
            if "all-hands.dev" in current_url:
                print(f"✓ Đang ở trang All-Hands.dev: {current_url}")
            else:
                print(f"⚠ URL hiện tại: {current_url}")
            time.sleep(PAGE_LOAD_WAIT)
        except Exception as e:
            print(f"⚠ Lỗi khi check URL: {str(e)}")

        # Đợi thêm để đảm bảo trang load hoàn toàn
        print("Đang đợi trang load hoàn toàn...")
        try:
            WebDriverWait(driver, 6).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            print("✓ Trang đã load hoàn toàn")
        except:
            print("⚠ Timeout đợi trang load, tiếp tục...")

        random_delay(delay_type='short')

        print("Đang tìm checkbox điều khoản sử dụng...")

        # Timeout cho checkbox và continue button
        long_wait = WebDriverWait(driver, 8 if TURBO_MODE else 15)  # TURBO: giảm timeout

        checkbox_selectors = [
            (By.XPATH, "//input[@type='checkbox']"),
            (By.XPATH, "//label[contains(., \"J'accepte les\")]//input[@type='checkbox']"),
            (By.XPATH, "//label[contains(., 'conditions')]//input[@type='checkbox']"),
            (By.CSS_SELECTOR, "label.flex.items-center.gap-2 input[type='checkbox']"),
            (By.CSS_SELECTOR, "input[type='checkbox']"),
        ]

        checkbox = None
        for by, selector in checkbox_selectors:
            try:
                checkbox = long_wait.until(EC.element_to_be_clickable((by, selector)))
                print(f"✓ Tìm thấy checkbox điều khoản")
                break
            except TimeoutException:
                continue

        if checkbox:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", checkbox)
            time.sleep(0.3)
            try:
                checkbox.click()
                print("✓ Đã click checkbox chấp nhận điều khoản")
            except:
                driver.execute_script("arguments[0].click();", checkbox)
                print("✓ Đã click checkbox (JavaScript)")
            time.sleep(0.5)  # Giảm từ 1s xuống 0.5s
        else:
            print("⚠ Không tìm thấy checkbox, có thể không cần thiết")

        # Bước 4: Click nút "Continuer"
        print("\n[Post-Login 5/6] Đang tìm nút 'Continuer'...")
        continue_selectors = [
            # Tìm button có text "Continuer" hoặc "Continue"
            (By.XPATH, "//button[contains(text(), 'Continuer') or contains(text(), 'Continue')]"),
            (By.XPATH, "//button[@type='button' and (contains(., 'Continuer') or contains(., 'Continue'))]"),
            # Tìm button có class bg-primary và w-full
            (By.XPATH, "//button[contains(@class, 'bg-primary') and contains(@class, 'w-full')]"),
            # Tìm button có class font-semibold và w-full
            (By.XPATH, "//button[contains(@class, 'font-semibold') and contains(@class, 'w-full')]"),
            # Tìm button type='button' với class bg-primary
            (By.XPATH, "//button[@type='button' and contains(@class, 'bg-primary')]"),
            # CSS selector
            (By.CSS_SELECTOR, "button.bg-primary.w-full"),
            (By.CSS_SELECTOR, "button[type='button'].bg-primary"),
        ]

        continue_button = None
        for by, selector in continue_selectors:
            try:
                continue_button = long_wait.until(EC.element_to_be_clickable((by, selector)))
                print(f"✓ Tìm thấy nút 'Continuer'")
                break
            except TimeoutException:
                continue

        if not continue_button:
            # Fallback
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if "continuer" in btn.text.lower() or "continue" in btn.text.lower():
                        continue_button = btn
                        print("✓ Tìm thấy nút 'Continuer' (fallback)")
                        break
            except:
                pass

        if continue_button:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", continue_button)
            random_delay(delay_type='short')
            try:
                continue_button.click()
                print("✓ Đã click nút 'Continuer'")
            except:
                driver.execute_script("arguments[0].click();", continue_button)
                print("✓ Đã click nút 'Continuer' (JavaScript)")

            # ĐỢI VÀ VERIFY click đã hoàn thành trước khi tiếp tục
            print("Đang đợi sau khi click Continuer...")
            wait_after_continuer = 1 if TURBO_MODE else 2  # Giảm từ 2/3s xuống 1/2s
            time.sleep(wait_after_continuer)

            # Check xem có popup/window mới không
            try:
                handles = driver.window_handles
                if len(handles) > 1:
                    print(f"⚠ Phát hiện popup mới sau Continuer, đang xử lý...")
                    time.sleep(1)  # Đợi popup load
            except:
                pass
        else:
            print("⚠ Không tìm thấy nút 'Continuer'")

        # Bước 6: Đợi redirect sang /settings/api-keys và copy API key
        api_keys_timeout = 3 if TURBO_MODE else 10
        print(f"\n[Post-Login 6/6] Đang đợi redirect sang trang API keys (timeout {api_keys_timeout}s)...")
        try:
            WebDriverWait(driver, api_keys_timeout).until(
                lambda d: "/settings/api-keys" in d.current_url or "api-keys" in d.current_url
            )
            print(f"✓ Đã redirect sang trang API keys: {driver.current_url}")
            time.sleep(PAGE_LOAD_WAIT)
        except TimeoutException:
            print(f"⚠ Chưa redirect sang API keys. URL hiện tại: {driver.current_url}")
            # Thử navigate trực tiếp
            try:
                driver.get("https://app.all-hands.dev/settings/api-keys")
                print("✓ Đã navigate trực tiếp đến trang API keys")
                time.sleep(PAGE_LOAD_WAIT)
            except:
                print("✗ Không thể navigate đến trang API keys")
                return False

        print("Đang tìm API key trên trang...")
        
        # PHƯƠNG PHÁP 1: Tìm trực tiếp trong input/text fields
        api_key = None
        try:
            print("  [1] Đang tìm trong input fields...")
            api_key_elements = driver.find_elements(By.XPATH, "//input[@type='text' or @type='password' or @readonly]")
            for elem in api_key_elements:
                try:
                    value = elem.get_attribute("value")
                    if value and len(value) > 20:  # API key thường dài > 20 ký tự
                        api_key = value
                        print(f"✓ Đã tìm thấy API key trong input field (length: {len(value)})")
                        break
                except:
                    continue
        except Exception as e:
            print(f"  ⚠ Lỗi khi tìm input fields: {e}")

        # PHƯƠNG PHÁP 2: Tìm trong div/span/code tags
        if not api_key:
            try:
                print("  [2] Đang tìm trong div/span/code tags...")
                text_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'font-mono')] | //code | //span[contains(@class, 'font-mono')]")
                for elem in text_elements:
                    try:
                        text = elem.text.strip()
                        if text and len(text) > 20 and not ' ' in text:  # API key không có khoảng trắng
                            api_key = text
                            print(f"✓ Đã tìm thấy API key trong text element (length: {len(text)})")
                            break
                    except:
                        continue
            except Exception as e:
                print(f"  ⚠ Lỗi khi tìm text elements: {e}")

        # PHƯƠNG PHÁP 3: Click nút copy và lấy từ clipboard
        if not api_key:
            print("  [3] Đang tìm nút copy API key...")
            copy_button_selectors = [
                (By.XPATH, "//button[@aria-label='Copy API key']"),
                (By.XPATH, "//button[@title='Copy API key']"),
                (By.XPATH, "//button[contains(@aria-label, 'Copy')]"),
                (By.XPATH, "//button[contains(@class, 'text-white')]//svg[@viewBox='0 0 448 512']"),
                (By.XPATH, "//button[contains(@class, 'hover:text-gray-300')]"),
            ]

            copy_button = None
            for by, selector in copy_button_selectors:
                try:
                    copy_button = wait.until(EC.element_to_be_clickable((by, selector)))
                    print(f"✓ Tìm thấy nút copy API key")
                    break
                except TimeoutException:
                    continue

            if not copy_button:
                # Fallback: tìm button có icon copy
                try:
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for btn in buttons:
                        try:
                            aria_label = btn.get_attribute("aria-label") or ""
                            title = btn.get_attribute("title") or ""
                            if "copy" in aria_label.lower() or "copy" in title.lower():
                                copy_button = btn
                                print("✓ Tìm thấy nút copy API key (fallback)")
                                break
                        except:
                            continue
                except:
                    pass

            if copy_button:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", copy_button)
                    time.sleep(0.3)
                    copy_button.click()
                    print("✓ Đã click nút copy API key")
                    time.sleep(0.8)

                    # Lấy từ clipboard
                    if PYPERCLIP_AVAILABLE:
                        try:
                            clipboard_content = pyperclip.paste()
                            if clipboard_content and len(clipboard_content) > 20:
                                api_key = clipboard_content
                                print(f"✓ Đã lấy API key từ clipboard (length: {len(clipboard_content)})")
                        except Exception as e:
                            print(f"  ⚠ Không thể lấy từ clipboard: {e}")
                    else:
                        print("  ⚠ pyperclip không có, bỏ qua clipboard")
                except Exception as e:
                    print(f"  ⚠ Lỗi khi click copy button: {e}")
            else:
                print("  ⚠ Không tìm thấy nút copy")

        # PHƯƠNG PHÁP 4: Screenshot để debug
        if not api_key:
            try:
                screenshot_path = f"debug_api_key_{email.split('@')[0]}.png"
                driver.save_screenshot(screenshot_path)
                print(f"  ⚠ Không tìm thấy API key, đã lưu screenshot: {screenshot_path}")
                print(f"  Current URL: {driver.current_url}")
            except:
                pass

        # Lưu API key vào file
        if api_key:
            # Lấy username từ email (phần trước @)
            username = email.split('@')[0]

            # Lưu vào file
            api_keys_file = "api_keys.txt"
            try:
                with open(api_keys_file, 'a', encoding='utf-8') as f:
                    f.write(f"{username}|{api_key}\n")
                print(f"✓ Đã lưu API key vào file {api_keys_file}")
                print(f"  Username: {username}")
                print(f"  API Key: {api_key[:20]}..." if len(api_key) > 20 else f"  API Key: {api_key}")

                # ✅ ĐÃ LẤY ĐƯỢC API KEY - Có thể tiếp tục
                print("\n" + "="*60)
                print("✅ API KEY ĐÃ ĐƯỢC LƯU THÀNH CÔNG!")
                print("="*60)
            except Exception as e:
                print(f"✗ Lỗi khi lưu API key vào file: {e}")
                print("\n" + "!"*60)
                print("⛔ DỪNG SCRIPT - Không thể lưu API key vào file!")
                print("!"*60)
                return False
        else:
            print("✗ Không lấy được API key")
            print("\n" + "!"*60)
            print("⛔ DỪNG SCRIPT - Không thể lấy API key!")
            print("   Vui lòng kiểm tra:")
            print("   - Trang API keys có load đúng không?")
            print("   - API key có hiển thị trên trang không?")
            print("   - Screenshot đã được lưu để debug")
            print("!"*60)
            return False

        print("\n✓ ĐÃ HOÀN THÀNH TẤT CẢ CÁC BƯỚC SAU ĐĂNG NHẬP!")
        return True

    except Exception as e:
        print(f"\n✗ Lỗi trong quá trình xử lý sau đăng nhập: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Hàm chính để chạy automation"""
    driver = None
    current_email_processing = None  # Track email đang xử lý

    try:
        print("=" * 50)
        print("Bắt đầu automation đăng ký All-Hands.dev")
        print("=" * 50)

        # REMOVED: Load proxy từ file
        # if USE_PROXY:
        #     print("\n[Khởi tạo] Đang load danh sách proxy từ file...")
        #     if not load_proxies_from_file(PROXY_FILE):
        #         print("⚠ Không thể load proxy từ file. Tiếp tục không dùng proxy...")
        #     print()

        # Đọc tất cả email từ file
        print("\n[0/5] Đang đọc danh sách email từ file...")
        emails = read_all_emails()

        if not emails:
            print("✗ Không có email nào để xử lý. Dừng script.")
            return

        print(f"✓ Đã đọc {len(emails)} email từ file")
        for idx, (email, _, _, _) in enumerate(emails, 1):
            print(f"  {idx}. {email}")

        # Biến lưu proxy hiện tại
        current_proxy = None

        # Loop qua từng email
        for idx, (email, password, refresh_token, client_id) in enumerate(emails, 1):
            try:
                # LOCK: Set email đang xử lý
                current_email_processing = email
                print("\n" + "=" * 50)
                print(f"🔒 LOCK: Đang xử lý email {idx}/{len(emails)}: {email}")
                print("=" * 50)

                # Lấy proxy mới cho mỗi email
                print("\n[1/7] Đang lấy proxy mới...")
                current_proxy = None

                if USE_PROXY:
                    current_proxy = get_proxy_from_api()
                    if not current_proxy:
                        print("⚠ Không lấy được proxy, tiếp tục không dùng proxy...")
                else:
                    print("ℹ️  Proxy đã TẮT - Chạy với IP thật để giảm CAPTCHA")

                # Thiết lập Chrome driver với proxy mới
                print("\n[2/7] Đang khởi động Chrome WebDriver với proxy...")
                driver = setup_chrome_driver(current_proxy)
                set_window_position(driver)
                print("✓ Chrome WebDriver đã sẵn sàng")

                # WARM-UP browser để giảm CAPTCHA
                warmup_browser(driver)

                # LƯU main window handle
                main_window = driver.current_window_handle
                print(f"🔒 Main window handle: {main_window[:8]}...")

                # Truy cập URL auth trực tiếp (không cần click Bitbucket OAuth)
                print(f"\n[3/6] Đang truy cập URL auth: {TARGET_URL}")
                try:
                    driver.get(TARGET_URL)
                    print("✓ Đã truy cập trang auth, sẽ tự động redirect sang Atlassian/Bitbucket")
                except Exception as e:
                    print(f"⚠ Lỗi khi truy cập URL: {str(e)}")
                    driver, _ = check_and_restart_driver(driver, current_proxy)
                    driver.get(TARGET_URL)
                    print("✓ Đã truy cập URL auth (sau khi khởi động lại)")

                # Đợi trang load + React hydration
                print("\nĐang đợi trang load...")
                try:
                    WebDriverWait(driver, 6).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    time.sleep(1)
                    print("✓ Trang đã load hoàn tất")
                except:
                    time.sleep(1)

                # URL mới đã trỏ trực tiếp sang Bitbucket auth, không cần click nút
                print("\n[3/6] Đang đợi trang Atlassian/Bitbucket login load...")

                # Đợi trang Atlassian/Bitbucket login sẵn sàng
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: "atlassian.com" in d.current_url or "id.atlassian" in d.current_url
                    )
                    print(f"✓ Đã redirect tới Atlassian: {driver.current_url}")
                except TimeoutException:
                    print(f"⚠ Chưa redirect sang Atlassian. URL hiện tại: {driver.current_url}")
                    # Vẫn tiếp tục vì có thể đã ở đúng trang

                time.sleep(2)

                # Đăng nhập Bitbucket với API credentials để lấy SMS
                print("\n[4/6] Đang đăng nhập Bitbucket...")
                login_success = login_bitbucket(driver, email, password, refresh_token, client_id)

                if not login_success:
                    print(f"\n⚠ Đăng nhập Bitbucket không thành công cho email: {email}")
                    continue

                print(f"\n✓ Đăng nhập Bitbucket thành công cho email: {email}!")

                # Các bước sau đăng nhập
                post_login_success = handle_post_login_steps(driver, email, password, refresh_token, client_id)

                # KIỂM TRA: Nếu không lấy được API key → LƯU VÀO ERRORMAIL.TXT VÀ TIẾP TỤC
                if not post_login_success:
                    print("\n" + "!"*60)
                    print("⚠ KHÔNG LẤY ĐƯỢC API KEY")
                    print(f"   Email: {email}")
                    print("!"*60)

                    # Lưu email vào errormail.txt
                    try:
                        with open("errormail.txt", 'a', encoding='utf-8') as f:
                            f.write(f"{email}|{password}\n")
                        print(f"✓ Đã lưu email vào errormail.txt: {email}")
                    except Exception as e:
                        print(f"✗ Lỗi khi lưu vào errormail.txt: {e}")

                    print("▶ Tiếp tục với email tiếp theo...")

                    # Đóng driver trước khi tiếp tục
                    try:
                        driver.quit()
                        print("✓ Đã đóng browser")
                    except:
                        pass

                    # TIẾP TỤC với email tiếp theo
                    continue

                # Đợi trang load
                print("Đang đợi trang load hoàn tất...")
                time.sleep(2)

                print(f"\n{'='*50}")
                print(f"✓ Hoàn thành email {idx}/{len(emails)}: {email}")
                print(f"🔓 UNLOCK: Giải phóng lock cho email {email}")
                print(f"{'='*50}\n")

                # RESET email processing
                current_email_processing = None

                # Đóng Chrome sau khi hoàn thành email (để xoay proxy mới cho email tiếp theo)
                if idx < len(emails):  # Không đóng nếu đây là email cuối cùng
                    # Random delay giữa các email để giảm CAPTCHA
                    delay_between_emails = random.randint(*DELAY_BETWEEN_EMAILS)
                    print(f"\n⏱️  Đợi {delay_between_emails}s trước khi xử lý email tiếp theo...")
                    time.sleep(delay_between_emails)

                    print("Đang đóng Chrome và proxy để chuẩn bị proxy mới cho email tiếp theo...")
                    try:
                        # Đóng Chrome trước
                        driver.quit()
                        print("✓ Đã đóng Chrome")

                        # Dừng proxy server cũ
                        stop_proxy_server()

                        random_delay(delay_type='short')
                    except Exception as e_close:
                        print(f"⚠ Lỗi khi đóng Chrome/proxy: {str(e_close)}")
                        time.sleep(1)

            except Exception as e:
                print(f"\n✗ Lỗi khi xử lý email {email}: {str(e)}")
                import traceback
                traceback.print_exc()

                print(f"\n{'='*50}")
                print(f"⚠ Bỏ qua email {idx}/{len(emails)}: {email} (có lỗi)")
                print(f"{'='*50}\n")
                print("Tiếp tục với email tiếp theo...")

                # Đóng Chrome sau lỗi (để xoay proxy mới cho email tiếp theo)
                if idx < len(emails):  # Không đóng nếu đây là email cuối cùng
                    print("Đang đóng Chrome và proxy sau lỗi...")
                    try:
                        driver.quit()
                        print("✓ Đã đóng Chrome")

                        # Dừng proxy server cũ
                        stop_proxy_server()

                        time.sleep(2)
                    except Exception as e_close:
                        print(f"⚠ Lỗi khi đóng Chrome/proxy: {str(e_close)}")
                        time.sleep(1)

                continue

        print("\n" + "=" * 50)
        print(f"✓ Đã xử lý xong tất cả {len(emails)} email!")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nNgười dùng đã dừng script (Ctrl+C)")
    except Exception as e:
        print(f"\n✗ Lỗi xảy ra: {str(e)}")
        import traceback
        traceback.print_exc()

        if driver:
            try:
                driver.save_screenshot("error_screenshot.png")
                print("✓ Đã lưu screenshot lỗi: error_screenshot.png")
            except:
                pass

    finally:
        # Cleanup proxy server
        try:
            stop_proxy_server()
        except:
            pass

        if driver:
            print("\nĐang đóng browser...")
            driver.quit()
            print("✓ Đã đóng browser")

        print("\n" + "=" * 50)
        print("Hoàn thành!")
        print("=" * 50)

if __name__ == "__main__":
    main()
