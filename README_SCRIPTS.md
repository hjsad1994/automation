# All-Hands.dev Automation Scripts

## 📁 File Structure

```
automation/
├── allhands_auto_register.py    # Script chính đăng ký email mới
├── allhands_recovery.py         # Script recovery cho email lỗi
├── email.txt                    # Input: Danh sách email mới
├── errormail.txt                # Error emails (tự động tạo)
├── api_keys.txt                 # Output: API keys thành công (script chính)
└── api_keys_done.txt            # Output: API keys thành công (recovery)
```

## 🚀 Cách Sử Dụng

### 1. Script Chính (`allhands_auto_register.py`)

**Chức năng:**
- Đọc email từ `email.txt`
- Tự động đăng ký All-Hands.dev
- Lấy API key → Lưu vào `api_keys.txt`
- **NẾU THẤT BẠI**: Lưu email vào `errormail.txt` và TIẾP TỤC email tiếp theo

**Chạy:**
```bash
python allhands_auto_register.py
```

**Format `email.txt`:**
```
email1@gmail.com|password123
email2@gmail.com|password456
email3@gmail.com|password789
```

### 2. Script Recovery (`allhands_recovery.py`)

**Chức năng:**
- Đọc email LỖI từ `errormail.txt`
- Thực hiện FULL login flow lại từ đầu
- Lấy API key → Lưu vào `api_keys_done.txt`
- **GIỮ NGUYÊN** `errormail.txt` (không tự động xóa)

**Chạy:**
```bash
python allhands_recovery.py
```

**Format `errormail.txt`:** (tự động tạo bởi script chính)
```
error_email1@gmail.com|password123
error_email2@gmail.com|password456
```

## 📋 Workflow

```
[email.txt]
    ↓
[allhands_auto_register.py]
    ├─→ Thành công → [api_keys.txt]
    └─→ Thất bại → [errormail.txt]
                         ↓
            [allhands_recovery.py]
                ├─→ Thành công → [api_keys_done.txt]
                └─→ Thất bại → Giữ trong errormail.txt
```

## 🔑 Output Files

### `api_keys.txt` (từ script chính)
```
username1|sk_live_abc123...
username2|sk_live_def456...
```

### `api_keys_done.txt` (từ recovery script)
```
username3|sk_live_ghi789...
username4|sk_live_jkl012...
```

## ⚠️ Lưu Ý

1. **Script chính KHÔNG DỪNG** khi gặp lỗi, nó sẽ:
   - Lưu email lỗi vào `errormail.txt`
   - Tiếp tục xử lý email tiếp theo

2. **Recovery script** giữ nguyên `errormail.txt`:
   - Không tự động xóa email sau khi thành công
   - Bạn cần xóa thủ công sau khi kiểm tra

3. **Để chạy lại email lỗi:**
   ```bash
   python allhands_recovery.py
   ```

4. **Kiểm tra kết quả:**
   - Script chính: `api_keys.txt`
   - Recovery: `api_keys_done.txt`

## 🎯 Example

### Bước 1: Chạy script chính
```bash
$ python allhands_auto_register.py
✓ Đã đọc 10 email từ email.txt
...
✅ Email 1/10: success
✅ Email 2/10: success
⚠ Email 3/10: không lấy được API key → Lưu vào errormail.txt
✅ Email 4/10: success
...
✓ Hoàn thành! 7 thành công, 3 lỗi
```

### Bước 2: Kiểm tra errormail.txt
```bash
$ cat errormail.txt
email3@gmail.com|pass3
email7@gmail.com|pass7
email9@gmail.com|pass9
```

### Bước 3: Chạy recovery
```bash
$ python allhands_recovery.py
✓ Đã đọc 3 email từ errormail.txt
...
✅ RECOVERY THÀNH CÔNG: email3@gmail.com
✅ RECOVERY THÀNH CÔNG: email7@gmail.com
⚠ RECOVERY THẤT BẠI: email9@gmail.com
```

### Bước 4: Kiểm tra kết quả
```bash
$ cat api_keys_done.txt
email3|sk_live_abc...
email7|sk_live_def...

$ cat errormail.txt  # Vẫn còn email9 để retry sau
email3@gmail.com|pass3
email7@gmail.com|pass7
email9@gmail.com|pass9
```

## 🛠️ Troubleshooting

**Q: Script dừng khi gặp CAPTCHA?**
A: Script sẽ đợi bạn giải CAPTCHA thủ công, sau đó tự động tiếp tục.

**Q: Muốn xóa email khỏi errormail.txt sau recovery thành công?**
A: Hiện tại cần xóa thủ công. Bạn có thể edit `errormail.txt` và xóa các dòng đã thành công.

**Q: Làm sao biết email nào đã recovery thành công?**
A: Kiểm tra `api_keys_done.txt`, so sánh username với `errormail.txt`.

---

**Created by:** AI Assistant
**Last Updated:** 2026-01-03
