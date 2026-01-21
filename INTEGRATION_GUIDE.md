# Hướng Dẫn Tích Hợp Email API vào Scripts

## Tổng Quan

Thay vì sử dụng Selenium để mở Gmail và tìm email, bạn có thể sử dụng `email_api_helper.py` để lấy email qua API.

## Setup

### 1. Format Email Credentials

Mỗi email cần có 3 thông tin:

```
email|password|refresh_token|client_id
```

**Ví dụ trong `email.txt`:**
```
skyebettencourteaw1086@hotmail.com|wxunKeiaw0A@|M.C521_BAY.0.U.-CtPw...(token dài)|9e5f94bc-e8a4-4e73-b8be-63364c29d753
```

### 2. Import Helper Functions

Trong script chính, thêm import:

```python
from email_api_helper import (
    wait_for_bitbucket_code,
    wait_for_openhands_link
)
```

## Sử Dụng trong Main Script (`allhands_auto_register.py`)

### Thay thế phần mở Gmail

**Phần cũ (dùng Selenium):**
```python
# Bước 2.6: Mở Gmail trong tab mới
print("\n[Post-Login 2.6/11] Đang mở Gmail...")
driver.execute_script("window.open('https://mail.google.com/', '_blank');")
# ... 300+ dòng code mở Gmail, tìm email, click link
```

**Phần mới (dùng API):**
```python
# Bước 2.6: Lấy email verification qua API
print("\n[Post-Login 2.6/11] Đang đợi email verification...")

# Đợi email OpenHands
verify_link = wait_for_openhands_link(
    email=email,
    refresh_token=refresh_token,
    client_id=client_id,
    max_wait=120,        # Đợi tối đa 120s
    check_interval=5     # Check mỗi 5s
)

if not verify_link:
    print("✗ Không nhận được email verification")
    return False

print(f"✓ Đã lấy verification link qua API")

# Mở link verification trong browser hiện tại
driver.get(verify_link)
print("✓ Đã mở verification link")
time.sleep(2)

# Tiếp tục với các bước tiếp theo...
```

## Chi Tiết Thay Đổi

### 1. Đọc email credentials từ file

**Cũ:**
```python
def read_all_emails(email_file=EMAIL_FILE):
    for line in lines:
        if '|' in line:
            email, password = line.split('|', 1)
            emails.append((email.strip(), password.strip()))
```

**Mới:**
```python
def read_all_emails(email_file=EMAIL_FILE):
    for line in lines:
        if '|' in line:
            parts = line.split('|')
            if len(parts) >= 4:
                email = parts[0].strip()
                password = parts[1].strip()
                refresh_token = parts[2].strip()
                client_id = parts[3].strip()
                emails.append((email, password, refresh_token, client_id))
            else:
                # Backward compatibility: nếu không có token
                email, password = parts[0].strip(), parts[1].strip()
                emails.append((email, password, None, None))
```

### 2. Xử lý Bitbucket Code (nếu cần)

Nếu script cần nhập code verification cho Bitbucket:

```python
# Đợi Bitbucket verification code
code = wait_for_bitbucket_code(
    email=email,
    refresh_token=refresh_token,
    client_id=client_id,
    max_wait=120
)

if code:
    print(f"✓ Đã nhận code: {code}")

    # Tìm input field và điền code
    code_field = driver.find_element(By.ID, "verification-code")
    code_field.send_keys(code)

    # Click submit
    submit_button = driver.find_element(By.ID, "submit-code")
    submit_button.click()
else:
    print("✗ Không nhận được code")
    return False
```

### 3. Loại bỏ Gmail Selenium Code

Xóa các dòng sau trong `handle_post_login_steps()`:

- **Lines 1512-1676**: Mở Gmail và handle popup
- **Lines 1682-1846**: Tìm email "Verify email"
- **Lines 1973-2018**: Cleanup Gmail tabs

## Ví Dụ Hoàn Chỉnh

```python
def handle_post_login_steps(driver, email, password, refresh_token, client_id):
    """
    Xử lý các bước sau khi đăng nhập Google thành công
    Sử dụng API để lấy email thay vì mở Gmail
    """
    try:
        print("\n=== BẮT ĐẦU CÁC BƯỚC SAU ĐĂNG NHẬP ===")
        wait = WebDriverWait(driver, 20)

        # Bước 1: Click "Create your account" (giữ nguyên)
        print("\n[Post-Login 1/6] Đang tìm nút 'Create your account'...")
        # ... code hiện tại ...

        # Bước 2: Click "Grant access" (giữ nguyên)
        print("\n[Post-Login 2/6] Đang tìm nút 'Grant access'...")
        # ... code hiện tại ...

        # Bước 2.5: Click "Resend verification" (giữ nguyên)
        print("\n[Post-Login 2.5/6] Đang tìm nút 'Resend verification'...")
        # ... code hiện tại ...

        # Bước 2.6: LẤY EMAIL QUA API (THAY THẾ MỞ GMAIL)
        print("\n[Post-Login 2.6/6] Đang đợi email verification qua API...")

        # Import function
        from email_api_helper import wait_for_openhands_link

        # Đợi email
        verify_link = wait_for_openhands_link(
            email=email,
            refresh_token=refresh_token,
            client_id=client_id,
            max_wait=120,
            check_interval=5
        )

        if not verify_link:
            print("✗ Không nhận được email verification sau 120s")
            return False

        print("✓ Đã lấy verification link qua API")

        # Mở link verification
        print("\n[Post-Login 2.7/6] Đang mở verification link...")
        driver.get(verify_link)
        time.sleep(2)

        # Bước 2.8: Click "Click here to proceed" (GIỮ NGUYÊN)
        print("\n[Post-Login 2.8/6] Đang tìm 'Click here to proceed'...")
        # ... code hiện tại từ dòng 1890-1923 ...

        # Bước 2.9: Click "Back to Application" (GIỮ NGUYÊN)
        print("\n[Post-Login 2.9/6] Đang tìm 'Back to Application'...")
        # ... code hiện tại từ dòng 1925-1971 ...

        # Bước 2.10: Click Bitbucket lại (GIỮ NGUYÊN)
        print("\n[Post-Login 2.10/6] Đang click Bitbucket lại...")
        # ... code hiện tại từ dòng 2020-2077 ...

        # Bước 3: Checkbox điều khoản (GIỮ NGUYÊN)
        print("\n[Post-Login 3/6] Đang tìm checkbox...")
        # ... code hiện tại từ dòng 2079-2138 ...

        # Bước 4: Click "Continuer" (GIỮ NGUYÊN)
        print("\n[Post-Login 4/6] Đang tìm 'Continuer'...")
        # ... code hiện tại từ dòng 2140-2202 ...

        # Bước 5: Lấy API key (GIỮ NGUYÊN)
        print("\n[Post-Login 5/6] Đang lấy API key...")
        # ... code hiện tại từ dòng 2204-2365 ...

        return True

    except Exception as e:
        print(f"\n✗ Lỗi: {str(e)}")
        return False
```

## Main Loop Update

```python
def main():
    # Đọc emails với format mới
    emails = read_all_emails()  # Returns: [(email, password, token, client_id), ...]

    for idx, email_data in enumerate(emails, 1):
        # Unpack
        if len(email_data) == 4:
            email, password, refresh_token, client_id = email_data
        else:
            email, password = email_data[:2]
            refresh_token, client_id = None, None
            print(f"⚠ Email {email} không có API credentials, bỏ qua")
            continue

        # Sử dụng trong post-login
        post_login_success = handle_post_login_steps(
            driver, email, password, refresh_token, client_id
        )
```

## Lợi Ích

### So với Selenium Gmail:

✅ **Nhanh hơn**: API response < 1s vs Selenium mở tab + load Gmail ~10s
✅ **Ổn định hơn**: Không bị ảnh hưởng bởi Gmail UI changes
✅ **Ít lỗi hơn**: Không bị "window already closed", "stale element"
✅ **Đơn giản hơn**: ~300 dòng code Gmail → ~10 dòng API call

### Performance Comparison:

| Bước | Selenium | API | Tiết kiệm |
|------|----------|-----|-----------|
| Mở Gmail tab | 5-8s | 0s | 5-8s |
| Handle popup | 3-5s | 0s | 3-5s |
| Tìm email | 2-4s | 0.5s | 1.5-3.5s |
| Click link | 2-3s | 0s (get URL) | 2-3s |
| **TOTAL** | **12-20s** | **0.5s** | **11.5-19.5s mỗi email!** |

## Testing

Test riêng API helper:
```bash
python3 email_api_helper.py
```

Expected output:
```
✓ Nhận được 5 emails:
✓ Tìm thấy Bitbucket verification code: SRBJMK
✓ Tìm thấy OpenHands verification link: https://...
```

## Troubleshooting

**Q: API trả về status=false?**
A: Check credentials (refresh_token, client_id) có đúng không

**Q: Không tìm thấy email sau 120s?**
A: Có thể email chưa gửi, tăng `max_wait` hoặc check mailbox manually

**Q: Link verification không đúng format?**
A: Check regex pattern trong `extract_openhands_verification_link()`

## Next Steps

1. ✅ Test API helper standalone
2. ⬜ Update `read_all_emails()` function
3. ⬜ Replace Gmail Selenium code với API calls
4. ⬜ Test full flow với 1 email
5. ⬜ Deploy to production

---

**Created:** 2026-01-13
**Version:** 1.0
