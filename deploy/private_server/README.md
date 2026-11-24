# Hướng dẫn chạy InuYasha Private Server (Bước 1 — R8.1)

APK client đi kèm (`com.cmn.inuyasha.private`) cài song song được với bản offline (`com.cmn.inuyasha.revival`), hỗ trợ nhập tự do địa chỉ Server ngay trên màn hình Đăng nhập.

---

## 1. Chạy ngay trên mạng Wi-Fi / LAN (Mac hoặc Linux)

```bash
./deploy/private_server/run_private_server.sh
```

Màn hình khởi động sẽ tự in ra địa chỉ LAN (ví dụ `http://192.168.100.173:8080`). Các máy cùng mạng Wi-Fi chỉ cần mở APK Private, dán địa chỉ đó vào ô **Địa chỉ Server**, bấm **Đăng Ký** rồi vào chơi chung.

---

## 2. Cho bạn bè từ xa vào chơi (Cloudflare Tunnel — không cần mở port modem)

```bash
./deploy/private_server/run_private_server.sh --tunnel
```

Cloudflared sẽ in ra URL dạng `https://xxxx-xxxx.trycloudflare.com`. Gửi URL này cho bạn bè dán vào ô **Địa chỉ Server** trên APK (`HTTPS` được hỗ trợ trực tiếp).

---

## 3. Deploy lên VPS Linux bằng Docker Compose

```bash
cd deploy/private_server
docker compose up -d --build
```

Dữ liệu người chơi nằm bền vững tại `deploy/private_server/private_data/`.

---

## 4. Tùy chỉnh cấu hình & nạp thẻ (`private_server_config.json`)

File cấu hình nằm tại `<data-dir>/private_server_config.json`:

| Khóa | Mặc định | Ý nghĩa |
|---|---|---|
| `server_name` | `"S1 InuYasha Private"` | Tên server hiển thị khi chọn server |
| `notice` | `"Chào mừng..."` | Thông báo bật lên khi kết nối server |
| `allow_registration` | `true` | Cho phép người chơi tự đăng ký |
| `max_accounts` | `100` | Số tài khoản tối đa |
| `allow_free_recharge` | `true` | Cho phép nạp miễn phí & Thẻ Tháng |
| `allow_instant_1m_recharge` | `true` | Bật/tắt gói nạp nhanh **1.000.000 KC** |
| `max_free_recharge_per_day` | `0` | Giới hạn số lần nạp miễn phí/ngày (`0` = không giới hạn) |
| `public_base_url` | `""` | Ép URL public cố định (nếu sau reverse proxy riêng) |

---

## 5. Lệnh GM Admin (chỉ gọi từ localhost / bên trong container)

Lấy token tại `<data-dir>/.admin_token` (nếu dùng Docker, chạy qua `docker compose exec inuyasha-private ...`):

```bash
TOKEN=$(cat server/private_saves/.admin_token)

# Xem danh sách tài khoản
curl -s -H "X-Admin-Token: $TOKEN" http://127.0.0.1:8080/admin/accounts | python3 -m json.tool

# Import save từ bản offline vào tài khoản private "ten_user"
curl -s -X POST -H "X-Admin-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"action":"import_offline_save","username":"ten_user","bundle_path":"/duong/dan/inuyasha_save_backup_latest.json"}' \
  http://127.0.0.1:8080/admin/account_action

# Khóa / mở khóa tài khoản hoặc đặt lại mật khẩu
curl -s -X POST -H "X-Admin-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"action":"ban","username":"ten_user"}' http://127.0.0.1:8080/admin/account_action

curl -s -X POST -H "X-Admin-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"action":"reset_password","username":"ten_user","new_password":"matkhaumoi"}' \
  http://127.0.0.1:8080/admin/account_action

# Gửi quà / Kim Cương / VIP cho tài khoản cụ thể
curl -s -X POST -H "X-Admin-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"profile":"ten_user","resources":[{"type":"Diamond","amount":50000}]}' \
  http://127.0.0.1:8080/admin/grant
```
