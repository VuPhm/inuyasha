# R7.11 — Cộng đồng S1 offline và Event Archive

APK `com.cmn.inuyasha.revival`, `5.0.4.98-r7.11`, `versionCode=810`, 224.157.937 byte. SHA-256 `48c268ac80f4253e66c35f97bb7099cf4c567cfc88f0ecd5ba29a2bd7120e702`. [Tệp APK](analysis/vn/patched/com.cmn.inuyasha.revival_r7_11_standalone.apk)

## Delta được nghiệm thu

| Luồng | Kết quả |
| --- | --- |
| Slot và Thần Tướng cùng S1 | **PASS tự động và smoke Slot trên Pixel.** Thành tích đọc từ hồ sơ S1 trong đúng kỳ. Hai người xem cùng thứ tự khi hòa điểm. Trên Pixel, cả hai TK khách đọc cùng bảng Slot và thấy hạng riêng. UI hiển thị DeltaPeer và các NPC. Chuyển TK2 → TK3 → TK2 được xác nhận qua UI và backend. [BXH](analysis/qa_r7_11/slot_shared_before.png) · [Chuyển TK](analysis/qa_r7_11/s1_switch.png) |
| Bản ghi Đập Trứng | **PASS tự động.** Tài khoản khác xuất hiện với kết quả đập đã lưu trong đúng kỳ. Tên NPC được ghi rõ. |
| `00:00 UTC+7`, Trung Tâm Thưởng và reload | **PASS tự động.** Slot chốt hạng, Cây Tiền gửi các mốc đã đạt còn chưa lấy, trạng thái và hộp thư được lưu ngay cả khi RPC đầu kỳ mới chỉ đọc. Phần thưởng có khóa theo tài khoản và kỳ. |
| Event Archive và banner `81/82` | **PASS tự động.** Reset có xác nhận boolean, sinh ID mới ở chế độ theo lịch hoặc luân phiên. Chính sách chuyển pity được áp dụng cho cùng banner cả lúc đổi kỳ tự động. Điểm và rương bắt đầu kỳ mới độc lập. |
| Cài mới | **PASS tự động và kiểm tra artifact.** APK chứa backend nhúng ARM 32-bit, đủ config donor R7.9 và không có snapshot tài khoản Mac. TK2 mẫu Lv20/VIP3 được tạo từ dữ liệu game; TK1 và TK3 bắt đầu mới. |
| Cài đè trên Pixel 3 XL | **PASS.** `790 → 800 → 810` trên cùng package, cùng SHA-256 của chứng thư ký. So SHA-256 ngay sau cài 810, trước khi mở hồ sơ chính, cả bốn file S1 và `accounts_index.json` đều khớp bản sao lưu 790. APK 801 của R7.10 đã được xác minh artifact và suite. Phiên cài 801 qua ADB streaming bị treo và được dừng trước khi nâng cấp 810 qua push install. |
| Standalone và kết nối | **PASS loopback trên Pixel.** Backend nhúng chạy với chế độ máy bay bật. Wi-Fi phục vụ ADB không dây. **BLOCKED cho bằng chứng tắt hẳn Wi-Fi.** Đã khởi chạy kịch bản tắt Wi-Fi và tự phục hồi. Pixel đã lên mạng lại, nhưng Android ngắt ADB và chưa truy xuất được ảnh hoặc nhật ký của lượt quay đó. |

**Full suite: 61/61 PASS** (`python3 server/test_emulator.py -v`, 38,0 giây). Kiểm thử thủ công giới hạn ở các màn thay đổi, tài khoản khách và khởi động lại sau cập nhật. Pixel đọc lại đúng 11 lượt Cây Tiền, mốc 10 đã nhận và rương banner 81 mốc 60 từ save R7.10. Hồ sơ STABLE và DEV trên Mac, APK 780/790 và các tag trước R7.10 đã được so với baseline.

## Luật và nguồn

Slot và Cây Tiền dùng bảng thưởng mô phỏng cục bộ, với ID vật phẩm đã đối chiếu VN. Thứ tự điểm Slot và Thần Tướng dùng hồ sơ thật trên thiết bị và điểm NPC ổn định. Reset do quản trị viên xác nhận kết toán theo ảnh chụp BXH tại thời điểm reset của profile được chọn. Cấu hình reset, kỳ riêng, pity và gửi mốc chưa nhận đi qua Event Archive hiện có.

Đã kiểm tra `period_overrides` với Cây Tiền `28800` giây và Slot `43200` giây trên save thử nghiệm. Chu kỳ tương ứng là 00:00/08:00/16:00 và 00:00/12:00 theo UTC+7. Banner vẫn theo kỳ ngày. APK 810 giữ mặc định 24 giờ. API quản trị Event Archive đặt chu kỳ cho từng sự kiện timed trong chế độ concurrent. Ăn Tối, Điểm Danh và Đoạt Bảo dùng lịch riêng.

Đoạt Bảo giữ preset nhận nhanh R7.9. Bang Hội, PB Tổ Đội và Mộ Thần Binh vẫn nằm trong backlog. APK chạy trên thiết bị Android hỗ trợ ứng dụng ARM 32-bit như Pixel 3 XL. Bản này chỉ được nghiệm thu trên thiết bị đã nêu.
