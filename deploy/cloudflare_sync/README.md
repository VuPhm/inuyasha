# InuYasha Hybrid Sync Hub (Cloudflare Workers + D1 — 100% Free)

Sync Hub siêu nhẹ cho mô hình **Hybrid Local-First**:
- Game luôn chạy offline trên Python nhúng (`127.0.0.1:18082`).
- Bang Hội giữ cục bộ, **không đồng bộ**.
- Khi có mạng (tự động giãn cách / khi vào khu vực BXH, Bạn Bè, Đấu Trường có cooldown / hoặc bấm nút Sync), game đồng bộ save cá nhân (nén gzip), cập nhật snapshot đội hình bạn bè và hộp thư sự kiện bạn bè qua **1 request `/sync` duy nhất**.
- **An toàn 100% Free:** Dùng Cloudflare Workers + D1 Free Plan (**không gắn thẻ thanh toán**). Nếu vượt hạn mức ngày, Cloudflare tự từ chối request (`429`) cho đến 07:00 sáng hôm sau (00:00 UTC) và **tuyệt đối không phát sinh phí**.

## 1. Chạy bộ test tự động cục bộ (không cần tài khoản Cloudflare)

```bash
node deploy/cloudflare_sync/test_sync_hub.mjs
```

## 2. Triển khai lên Cloudflare (5 phút, miễn phí)

> Yêu cầu: tài khoản Cloudflare miễn phí (không cần thêm thẻ tín dụng).

```bash
cd deploy/cloudflare_sync

# 1) Đăng nhập Cloudflare (mở trình duyệt xác nhận)
npx wrangler login

# 2) Tạo D1 database (ưu tiên khu vực APAC gần Việt Nam)
npx wrangler d1 create inuyasha-sync-db --location apac
# -> Copy giá trị database_id dán vào wrangler.jsonc

# 3) Chạy migration tạo 4 bảng D1
npx wrangler d1 execute inuyasha-sync-db --remote --file=schema.sql

# 4) Đặt mã mời nhóm bạn (bắt buộc nhập đúng mã mời mới đăng ký được)
npx wrangler secret put INVITE_CODE

# (Tùy chọn) Đặt token quản trị để xem/khóa tài khoản qua /admin/*
npx wrangler secret put ADMIN_TOKEN

# 5) Deploy Worker
npx wrangler deploy
```

Sau khi deploy xong, Cloudflare sẽ cấp URL dạng:
`https://inuyasha-sync-hub.<subdomain>.workers.dev`

Kiểm tra nhanh:
```bash
curl https://inuyasha-sync-hub.<subdomain>.workers.dev/health
```

## 3. Danh sách Endpoint

| Method | Path | Mô tả |
| :--- | :--- | :--- |
| `GET` | `/health`, `/auth/info` | Thông tin hub, trạng thái `invite_required`, chính sách cooldown sync |
| `POST` | `/auth/register` | Đăng ký tài khoản (kiểm tra `invite_code` nếu có) |
| `POST` | `/auth/login` | Đăng nhập, trả token phiên + tóm tắt save trên Cloud |
| `POST` | `/auth/change_password` | Đổi mật khẩu (hủy các phiên khác) |
| `POST` | `/sync` | Gộp Push save gzip + gửi `outgoing_events` + Delta Pull `updated_peers` & `inbox_events` (trả `409` nếu xung đột 2 thiết bị) |
| `GET` | `/sync/pull_save` | Tải toàn bộ save nén gzip từ Cloud (dùng khi đổi máy hoặc chọn ghi đè từ Cloud) |
| `GET` | `/admin/accounts` | Danh sách tài khoản (yêu cầu `X-Admin-Token`) |
| `POST` | `/admin/ban` | Khóa / mở khóa tài khoản (yêu cầu `X-Admin-Token`) |
