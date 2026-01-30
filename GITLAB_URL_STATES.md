# GitLab Registration Flow - URL States

## URL sau khi đăng ký thành công:

1. **`https://gitlab.com/users/sign_up`** → Trang đăng ký ban đầu
2. **`https://gitlab.com/users`** → Sau khi submit form (nếu không cần verify)

## URL verification flow:

1. **`https://gitlab.com/users/sign_up/identity_verification`** 
   - Trang yêu cầu nhập verification code
   - Input field: `verification_code`
   - Button: `<button type="submit">Verify email address</button>`

2. **`https://gitlab.com/users/identity_verification/success`** ← THÀNH CÔNG!
   - Trang báo verify thành công
   - Script cần detect URL này và chuyển sang OpenHands
   
3. **`https://gitlab.com/users/sign_up/welcome`** ← THÀNH CÔNG!
   - Trang welcome form (Role, Objective, etc.)
   - Cũng là dấu hiệu đã verify thành công
   - Script có thể bỏ qua trang này và chuyển thẳng OpenHands

## Logic check URL:

```python
# Verify THÀNH CÔNG nếu URL chứa:
success_indicators = [
    "/identity_verification/success",  # Success page
    "/sign_up/welcome",                 # Welcome page
    "/users/sign_up/welcome",           # Welcome page (full)
    "/users/",                          # Dashboard (rare)
]

# Verify THẤT BẠI nếu:
if "identity_verification" in url and "success" not in url:
    # Vẫn còn ở trang nhập code
    # → Code sai hoặc chưa submit
```

## Flow của script:

1. Đăng ký GitLab → URL: `/users`
2. Detect cần verify → URL: `/identity_verification`
3. Lấy code từ email API → Điền vào form
4. Click Verify → GitLab redirect
5. Check URL:
   - Nếu `/success` hoặc `/welcome` → ✅ Thành công
   - Nếu vẫn `/identity_verification` (không có success) → ❌ Thất bại
6. Mở tab mới → OpenHands login
