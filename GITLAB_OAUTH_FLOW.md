# GitLab OAuth Flow cho OpenHands

## Flow hoàn chỉnh khi login OpenHands qua GitLab:

### 1. User click "Log in with GitLab" trên OpenHands
```
URL: https://app.all-hands.dev/login
Button: <button type="button">
          <span>Log in with GitLab</span>
        </button>
```

### 2. Redirect sang GitLab OAuth Authorization
```
URL: https://gitlab.com/oauth/authorize?
     scope=openid+email+profile+read_user+api+write_repository
     &client_id=171bb1eafc9acabde6dd584c45dc7f21d5c1601e6470bf6c4a2486e312460836
     &redirect_uri=https://auth.app.all-hands.dev/realms/allhands/broker/gitlab/endpoint
     &response_type=code
     &state=...

Trang này có nút: <button>
                    <span class="gl-button-text">
                      Authorize OpenHands
                    </span>
                  </button>
```

**QUAN TRỌNG**: Phải click nút "Authorize OpenHands" để approve!

### 3. GitLab check điều kiện:
- ✅ User đã login GitLab?
- ✅ Email đã verify?
- ✅ User có authorize app chưa?

### 4. Nếu CHƯA authorize → Hiện trang OAuth consent
```
Trang: /oauth/authorize
Nội dung:
- "OpenHands is requesting access to your account"
- Permissions: openid, email, profile, read_user, api, write_repository
- Button: "Authorize OpenHands" ← CẦN CLICK!
```

### 5. Sau khi click Authorize → Redirect về OpenHands
```
URL: https://auth.app.all-hands.dev/realms/allhands/broker/gitlab/endpoint?code=...
     ↓
     Redirect tiếp:
     ↓
URL: https://app.all-hands.dev/oauth/keycloak/callback?code=...
     ↓
     Redirect cuối:
     ↓
URL: https://app.all-hands.dev/ (Dashboard)
```

## Các case có thể xảy ra:

### Case 1: GitLab chưa login
→ Hiện trang login GitLab
→ Sau khi login → Redirect lại về /oauth/authorize

### Case 2: GitLab đã login NHƯNG email chưa verify
→ GitLab từ chối
→ Error: "Email not verified"

### Case 3: GitLab đã login + verify NHƯNG chưa authorize app
→ Hiện trang /oauth/authorize
→ User phải click "Authorize OpenHands"

### Case 4: GitLab đã login + verify + đã authorize trước đó
→ Tự động approve (không cần click)
→ Redirect thẳng về OpenHands

## Script logic:

```python
# 1. Click "Log in with GitLab" từ OpenHands
gitlab_button.click()
time.sleep(2)

# 2. Check xem có ở trang /oauth/authorize không
if "/oauth/authorize" in driver.current_url:
    # Tìm và click nút "Authorize OpenHands"
    authorize_button = find_element("//button//span[contains(text(), 'Authorize OpenHands')]")
    authorize_button.click()
    print("✓ Đã click Authorize")
    
    # Đợi redirect về OpenHands
    time.sleep(3)

# 3. Check xem đã về OpenHands dashboard chưa
if "app.all-hands.dev" in driver.current_url and "login" not in driver.current_url:
    print("✓ Login thành công!")
```

## Selectors cho nút Authorize:

```python
# Priority order:
1. "//button//span[contains(text(), 'Authorize OpenHands')]"  # Chính xác nhất
2. "//button[contains(., 'Authorize')]"                        # Backup
3. "//input[@type='submit' and @value='Authorize']"           # Nếu là input
4. "button.btn-success"                                        # CSS fallback
```

## Timeline:

```
T+0s:  Click "Log in with GitLab"
T+2s:  Check URL → /oauth/authorize?
T+2s:  Tìm nút "Authorize OpenHands"
T+3s:  Click Authorize
T+6s:  Redirect về OpenHands
T+6s:  Check login success
```

## Error handling:

- Nếu KHÔNG tìm thấy nút Authorize → Có thể đã authorize trước đó
- Nếu timeout redirect → Retry click GitLab button
- Nếu vẫn ở /login sau 3 lần retry → Báo lỗi
