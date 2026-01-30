"""
Helper module để lấy email/SMS qua API thay vì mở Gmail
API: https://docs.dongvanfb.net/utils/get-messages-mail-with-oauth2
"""

import requests
import time
import re
from typing import Optional, Dict, Tuple, Callable

# API Configuration
API_ENDPOINT = "https://tools.dongvanfb.net/api/get_messages_oauth2"

def get_emails_from_api(email: str, refresh_token: str, client_id: str) -> Dict:
    """
    Gọi API để lấy danh sách emails

    Args:
        email: Email address (e.g., skyebettencourteaw1086@hotmail.com)
        refresh_token: OAuth2 refresh token
        client_id: Client ID

    Returns:
        Dict chứa response từ API
    """
    try:
        payload = {
            "email": email,
            "refresh_token": refresh_token,
            "client_id": client_id
        }

        print(f"📧 Đang gọi API để lấy emails cho: {email}")
        response = requests.post(API_ENDPOINT, json=payload, timeout=30)

        if response.status_code != 200:
            print(f"✗ API error: HTTP {response.status_code}")
            return None

        data = response.json()

        if not data.get("status"):
            print(f"✗ API returned status=false, code: {data.get('code')}")
            return None

        print(f"✓ API response nhận được {len(data.get('messages', []))} emails")
        return data

    except requests.exceptions.Timeout:
        print("✗ API timeout sau 30 giây")
        return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Lỗi kết nối API: {str(e)}")
        return None
    except Exception as e:
        print(f"✗ Lỗi không xác định: {str(e)}")
        return None


def extract_bitbucket_code(messages: list) -> Optional[str]:
    """
    Tìm và extract verification code từ Bitbucket/Atlassian

    Format email:
    - From: noreply+*@id.atlassian.com
    - Subject: "XXXXXX is your verification code"

    Returns:
        Verification code (6 ký tự) hoặc None
    """
    try:
        for msg in messages:
            # Check sender - handle both string and list format
            from_field = msg.get("from", "")
            if isinstance(from_field, list) and from_field:
                from_address = from_field[0].get("address", "") if isinstance(from_field[0], dict) else from_field[0]
            elif isinstance(from_field, str):
                from_address = from_field
            else:
                from_address = ""

            subject = msg.get("subject", "")

            # Kiểm tra xem có phải email từ Atlassian không
            if "id.atlassian.com" in from_address:
                # Extract code từ subject: "SRBJMK is your verification code"
                match = re.search(r'([A-Z0-9]{6})\s+is your verification code', subject)
                if match:
                    code = match.group(1)
                    print(f"✓ Tìm thấy Bitbucket verification code: {code}")
                    return code

                # Fallback: Tìm trong body nếu không có trong subject
                message_body = msg.get("message", "")
                match = re.search(r'verification code is:\s*([A-Z0-9]{6})', message_body)
                if match:
                    code = match.group(1)
                    print(f"✓ Tìm thấy code trong body: {code}")
                    return code

        print("✗ Không tìm thấy Bitbucket verification code")
        return None

    except Exception as e:
        print(f"✗ Lỗi khi extract Bitbucket code: {str(e)}")
        return None


def extract_openhands_verification_link(messages: list) -> Optional[str]:
    """
    Tìm và extract verification link từ OpenHands

    Format email:
    - From: no-reply@openhands.dev
    - Subject: "Verify email"
    - Body chứa: "Link to e-mail address verification"

    Returns:
        Verification link hoặc None
    """
    try:
        for msg in messages:
            # Check sender - handle both string and list format
            from_field = msg.get("from", "")
            if isinstance(from_field, list) and from_field:
                from_address = from_field[0].get("address", "") if isinstance(from_field[0], dict) else from_field[0]
            elif isinstance(from_field, str):
                from_address = from_field
            else:
                from_address = ""

            subject = msg.get("subject", "")

            # Kiểm tra xem có phải email từ OpenHands không
            if "openhands.dev" in from_address and "verify" in subject.lower():
                message_body = msg.get("message", "")

                # Extract link - tìm link chứa "login-actions/action-token"
                # Regex để tìm URL trong HTML
                matches = re.findall(r'https?://[^\s<>"]+login-actions/action-token[^\s<>"]*', message_body)

                if matches:
                    link = matches[0]
                    # Clean up HTML entities nếu có
                    link = link.replace('&amp;', '&')
                    print(f"✓ Tìm thấy OpenHands verification link: {link[:80]}...")
                    return link

                # Fallback: Tìm bất kỳ link nào trong body
                matches = re.findall(r'https?://[^\s<>"]+', message_body)
                for link in matches:
                    if "login-actions" in link or "verify" in link.lower():
                        link = link.replace('&amp;', '&')
                        print(f"✓ Tìm thấy verification link (fallback): {link[:80]}...")
                        return link

        print("✗ Không tìm thấy OpenHands verification link")
        return None

    except Exception as e:
        print(f"✗ Lỗi khi extract OpenHands link: {str(e)}")
        return None


def extract_gitlab_verification_code(messages: list) -> Optional[str]:
    """
    Tìm và extract verification CODE 6 số từ GitLab

    Format email:
    - From: gitlab@mg.gitlab.com hoặc noreply@gitlab.com
    - Body chứa: code trong thẻ <div> với font-weight:700
      VD: <div style="...font-weight:700;...">689923 </div>

    Returns:
        Verification code (6 số) hoặc None
    """
    try:
        for msg in messages:
            # Check sender - handle both string and list format
            from_field = msg.get("from", "")
            if isinstance(from_field, list) and from_field:
                from_address = from_field[0].get("address", "") if isinstance(from_field[0], dict) else from_field[0]
            elif isinstance(from_field, str):
                from_address = from_field
            else:
                from_address = ""

            subject = msg.get("subject", "")
            message_body = msg.get("message", "")

            # Kiểm tra xem có phải email từ GitLab không
            is_gitlab = "gitlab" in from_address.lower() or "gitlab" in subject.lower()
            
            if is_gitlab or "verification" in subject.lower() or "confirm" in subject.lower():
                # Pattern ưu tiên: code trong thẻ div có font-weight:700 (format GitLab)
                # VD: <div style="...font-weight:700;...">689923 </div>
                pattern_div = r'<div[^>]*font-weight:\s*700[^>]*>\s*(\d{6})\s*</div>'
                matches = re.findall(pattern_div, message_body, re.IGNORECASE)
                if matches:
                    code = matches[0]
                    print(f"✓ Tìm thấy GitLab verification code (div pattern): {code}")
                    return code
                
                # Pattern thứ 2: code nằm giữa 2 thẻ > và <
                # VD: >689923<  hoặc >689923 </div>
                pattern_tags = r'>\s*(\d{6})\s*<'
                matches = re.findall(pattern_tags, message_body)
                if matches:
                    # Loại bỏ các code là mã màu (thường xuất hiện sau color: hoặc #)
                    for code in matches:
                        # Kiểm tra xem code có phải mã màu không
                        color_pattern = f'(color[:#]\\s*{code}|#{code})'
                        if not re.search(color_pattern, message_body, re.IGNORECASE):
                            print(f"✓ Tìm thấy GitLab verification code (tag pattern): {code}")
                            return code
                
                # Pattern thứ 3: "enter the following code" hoặc "verification code"
                patterns_text = [
                    r'enter the following code[.\s:]*[^0-9]*?(\d{6})',
                    r'verification code[.\s:]*[^0-9]*?(\d{6})',
                ]
                
                for pattern in patterns_text:
                    matches = re.findall(pattern, message_body, re.IGNORECASE)
                    if matches:
                        code = matches[0]
                        print(f"✓ Tìm thấy GitLab verification code (text pattern): {code}")
                        return code

        print("✗ Không tìm thấy GitLab verification code")
        return None

    except Exception as e:
        print(f"✗ Lỗi khi extract GitLab code: {str(e)}")
        return None


def wait_for_gitlab_verification_code(email: str, refresh_token: str, client_id: str,
                                       max_wait: int = 120, check_interval: int = 5) -> Optional[str]:
    """
    Đợi và lấy GitLab verification CODE (6 số)

    Args:
        email: Email address
        refresh_token: OAuth2 token
        client_id: Client ID
        max_wait: Thời gian đợi tối đa (giây)
        check_interval: Khoảng thời gian giữa các lần check (giây)

    Returns:
        Verification code (6 số) hoặc None nếu timeout
    """
    print(f"\n⏳ Đang đợi GitLab verification code (tối đa {max_wait}s)...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        # Gọi API
        data = get_emails_from_api(email, refresh_token, client_id)

        if data and data.get("messages"):
            # Tìm code
            code = extract_gitlab_verification_code(data["messages"])
            if code:
                return code

        # Đợi trước khi check lại
        elapsed = int(time.time() - start_time)
        remaining = max_wait - elapsed
        print(f"  ⏱️  Chưa thấy code GitLab, đợi {check_interval}s... ({remaining}s còn lại)", end='\r')
        time.sleep(check_interval)

    print(f"\n⚠ Timeout sau {max_wait}s, không nhận được code GitLab")
    return None


def wait_for_bitbucket_code(email: str, refresh_token: str, client_id: str,
                            max_wait: int = 120, check_interval: int = 5,
                            resend_callback: Optional[Callable[[], bool]] = None,
                            resend_after_attempts: int = 5) -> Optional[str]:
    """
    Đợi và lấy Bitbucket verification code

    Args:
        email: Email address
        refresh_token: OAuth2 token
        client_id: Client ID
        max_wait: Thời gian đợi tối đa (giây)
        check_interval: Khoảng thời gian giữa các lần check (giây)
        resend_callback: Callback function để click "Resend email" - returns True nếu thành công
        resend_after_attempts: Số lần check thất bại trước khi gọi resend_callback

    Returns:
        Verification code hoặc None nếu timeout
    """
    print(f"\n⏳ Đang đợi Bitbucket verification code (tối đa {max_wait}s)...")
    start_time = time.time()
    attempts = 0
    resend_triggered = False

    while time.time() - start_time < max_wait:
        attempts += 1
        
        # Gọi API
        data = get_emails_from_api(email, refresh_token, client_id)

        if data and data.get("messages"):
            # Tìm code
            code = extract_bitbucket_code(data["messages"])
            if code:
                return code

        # Check nếu cần gọi resend_callback
        if (resend_callback and 
            not resend_triggered and 
            attempts >= resend_after_attempts):
            print(f"\n🔄 Đã thử {attempts} lần không thành công, đang gọi Resend email...")
            try:
                if resend_callback():
                    print("✓ Đã click Resend email thành công!")
                    resend_triggered = True
                    # Reset timer để có thêm thời gian chờ sau khi resend
                    start_time = time.time()
                    attempts = 0
                else:
                    print("⚠ Resend email callback trả về False")
            except Exception as e:
                print(f"✗ Lỗi khi gọi resend callback: {str(e)}")

        # Đợi trước khi check lại
        elapsed = int(time.time() - start_time)
        remaining = max_wait - elapsed
        print(f"  ⏱️  Chưa thấy code, đợi {check_interval}s nữa... ({remaining}s còn lại)", end='\r')
        time.sleep(check_interval)

    print(f"\n⚠ Timeout sau {max_wait}s, không nhận được code")
    return None


def wait_for_openhands_link(email: str, refresh_token: str, client_id: str,
                            max_wait: int = 120, check_interval: int = 5) -> Optional[str]:
    """
    Đợi và lấy OpenHands verification link

    Args:
        email: Email address
        refresh_token: OAuth2 token
        client_id: Client ID
        max_wait: Thời gian đợi tối đa (giây)
        check_interval: Khoảng thời gian giữa các lần check (giây)

    Returns:
        Verification link hoặc None nếu timeout
    """
    print(f"\n⏳ Đang đợi OpenHands verification email (tối đa {max_wait}s)...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        # Gọi API
        data = get_emails_from_api(email, refresh_token, client_id)

        if data and data.get("messages"):
            # Tìm link
            link = extract_openhands_verification_link(data["messages"])
            if link:
                return link

        # Đợi trước khi check lại
        elapsed = int(time.time() - start_time)
        remaining = max_wait - elapsed
        print(f"  ⏱️  Chưa thấy email, đợi {check_interval}s nữa... ({remaining}s còn lại)", end='\r')
        time.sleep(check_interval)

    print(f"\n⚠ Timeout sau {max_wait}s, không nhận được email")
    return None


# Test function
if __name__ == "__main__":
    print("=== TEST EMAIL API HELPER ===\n")

    # Test credentials
    TEST_EMAIL = "skyebettencourteaw1086@hotmail.com"
    TEST_TOKEN = "M.C521_BAY.0.U.-CtPwMqUZwogq2GKT6AxBVLI52H!tWLjEJFkAn0CfYm!swGHexo86*9aZ9GP0NKl9OVWZ4!c82DtLhALsgw7h2MuxI0dHCvCUGFLin9ZmzIaGI4NdQzsQW3VeoQoZRBR!WP1CjtMTh9*4sBTMH5PNv9N2HfkLh0ZnnHQwSKZOqXauHD8pzWlNm5PuSU*xEyvP588x5IDqulu46EaSdRV*jo1Ygp3HbF!BUaK3D7sWEWmH3*X*OPrkGpTUHow7AComWpkcjGQKOZJiWvhRZ!oY9o3IUEgksqHeatKT5KZpT0Q0FCIWATRFzGc6E!v!S*6RnvdueiY3aFgvN5HbFEZ9NUf1TKsO!n3kMENjChjgQYOuIOCgJVK9FkzOT6Fy11SWHA$$"
    TEST_CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"

    # Test 1: Lấy emails
    print("Test 1: Lấy danh sách emails")
    data = get_emails_from_api(TEST_EMAIL, TEST_TOKEN, TEST_CLIENT_ID)

    if data:
        messages = data.get("messages", [])
        print(f"\n✓ Nhận được {len(messages)} emails:\n")

        for idx, msg in enumerate(messages, 1):
            # Handle "from" field - có thể là list hoặc string
            from_field = msg.get("from", "")
            if isinstance(from_field, list) and from_field:
                from_address = from_field[0].get("address", "Unknown") if isinstance(from_field[0], dict) else from_field[0]
            elif isinstance(from_field, str):
                from_address = from_field
            else:
                from_address = "Unknown"

            subject = msg.get("subject", "")
            date = msg.get("date", "")

            print(f"{idx}. [{date}] From: {from_address}")
            print(f"   Subject: {subject}")
            print()

        # Test 2: Extract Bitbucket code
        print("\nTest 2: Extract Bitbucket code")
        code = extract_bitbucket_code(messages)
        if code:
            print(f"✅ Code: {code}")

        # Test 3: Extract OpenHands link
        print("\nTest 3: Extract OpenHands verification link")
        link = extract_openhands_verification_link(messages)
        if link:
            print(f"✅ Link: {link}")
    else:
        print("✗ Không lấy được emails từ API")
