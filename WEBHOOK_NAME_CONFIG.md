# Webhook Name Configuration

## Tổng quan

Tất cả 8 hook script (hook1.py -> hook8.py) load từ **1 file `.env` duy nhất** và lấy NAME tương ứng để gửi lên webhook.

## Cấu trúc

### File `.env` (1 file duy nhất)
```bash
# Webhook Names - Tên để identify API key trên webhook
NAME_1=tai-p1
NAME_2=tai-p2
NAME_3=tai-p3
NAME_4=tai-p4
NAME_5=tai-p5
NAME_6=tai-p6
NAME_7=tai-p7
NAME_8=tai-p8
```

### Hook Scripts
Mỗi script load cùng 1 file `.env` nhưng đọc NAME khác nhau:

| Script | Load từ | Lấy biến | Default |
|--------|---------|----------|---------|
| `gitlab_register_and_openhands-hook1.py` | `.env` | `NAME_1` | `tai-p1` |
| `gitlab_register_and_openhands-hook2.py` | `.env` | `NAME_2` | `tai-p2` |
| `gitlab_register_and_openhands-hook3.py` | `.env` | `NAME_3` | `tai-p3` |
| `gitlab_register_and_openhands-hook4.py` | `.env` | `NAME_4` | `tai-p4` |
| `gitlab_register_and_openhands-hook5.py` | `.env` | `NAME_5` | `tai-p5` |
| `gitlab_register_and_openhands-hook6.py` | `.env` | `NAME_6` | `tai-p6` |
| `gitlab_register_and_openhands-hook7.py` | `.env` | `NAME_7` | `tai-p7` |
| `gitlab_register_and_openhands-hook8.py` | `.env` | `NAME_8` | `tai-p8` |

## Cách sử dụng

### 1. Tạo file `.env` từ template:
```bash
cp env.example .env
```

### 2. Chỉnh sửa file `.env` với NAME của bạn:
```bash
# Webhook Names - Tùy chỉnh tên theo ý bạn
NAME_1=my-server-1
NAME_2=my-server-2
NAME_3=dev-machine
NAME_4=prod-server
# ... etc
```

### 3. Chạy các hook script như bình thường:
```bash
python gitlab_register_and_openhands-hook1.py  # Sẽ dùng NAME_1
python gitlab_register_and_openhands-hook2.py  # Sẽ dùng NAME_2
# ... etc
```

## Webhook Payload

Khi POST lên webhook, payload sẽ có dạng:
```json
{
  "apiKey": "sk-live-...",
  "name": "tai-p1",           // Từ NAME_1 trong .env
  "replaceKeyId": "abc123"    // Optional
}
```

## Lưu ý

- ✅ **CHỈ CẦN 1 FILE `.env`** cho tất cả 8 scripts
- ✅ Mỗi script tự động lấy NAME tương ứng
- ✅ Nếu không có NAME_X trong `.env`, sẽ dùng giá trị default (tai-p1, tai-p2, etc.)
- ✅ Có thể đặt tên bất kỳ (không nhất thiết phải "tai-pX")
