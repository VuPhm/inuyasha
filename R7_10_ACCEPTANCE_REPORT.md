# R7.10 — Kiểm thử vòng chơi may mắn và nhận thưởng

Baseline `checkpoint-vn-r7.9` (`d24d214`). Bản standalone R7.10 dùng `com.cmn.inuyasha.revival`, `5.0.4.98-r7.10`, `versionCode=801` ([APK](analysis/vn/patched/com.cmn.inuyasha.revival_r7_10_standalone.apk)). APK 800 là bản smoke đầu tiên. Bản 801 bổ sung sửa khóa nhận thưởng S1 và tính đủ phí rung cây vào tích lũy tiêu Kim Cương.

## Test the Delta

| Luồng | Phạm vi và kết quả |
| --- | --- |
| Cây Tiền `4432` | **PASS trên Pixel.** Rung miễn phí, rung 10 lần giá 450 KC, lên 11 lượt, nhận mốc 10. Popup có 200 KC và 2 Búa Vàng. Backend trả `DrawnNums="10"` và số dư tăng đúng 200 KC. `test_58` xác nhận phí tích lũy tính đủ 450 KC, hai TK S1 cùng nhận được mốc, và reload giữ khóa chống nhận lại. |
| Slot `4412` | **PASS trên Pixel.** Rút 10 lần, popup thưởng hiện, vé từ 10 xuống 0, điểm từ 0 lên 10. Sửa chỉ số ô nháy trong Lua. `test_57` xác nhận Vé Rút Thưởng VN `16050027`, hệ số lượt kế, nạp giả lập, số dư vé sau reload và bảo toàn stack Khăn Lau `16050055`. |
| Chiêu mộ thường, banner `81/82`, túi tướng, rương chọn | **PASS rương banner trên Pixel.** Banner 81 hiển thị 10 tướng và 100 điểm, nhận rương 60 và chuyển sang mốc 200. Backend đọc lại `81: 100 điểm, mốc 60 đã nhận` và `82: 0 điểm`. `test_56` kiểm tra giới hạn đợt quay trước khi trừ phí, nới túi 5 ô theo giá VN, từ chối lấy rương hai lần, và quyền chọn UR được gửi vào Trung Tâm Thưởng khi đổi kỳ. Save cũ giữ sức chứa nền 200 ô như R7.9. |
| Cầu Nguyện `4409`, Đập Trứng `4426` | **PASS tự động.** Đối chiếu trường dữ liệu và lời gọi VN. `test_51` kiểm tra khóa trước nạp, mở và nhận thưởng sau nạp, đập trứng và tải bản ghi. |
| Đoạt Bảo `7800`, Thần Binh `4410` | **PASS tự động.** `test_52` kiểm tra tham gia/nhận một lần, lượt miễn phí và có phí Thần Binh, nhận mốc. Đoạt Bảo dùng preset mô phỏng R7.9. Thần Binh dùng cấu hình TW 1.4 ánh xạ VN và bảng thưởng mô phỏng R7.9. |

**Kết quả full suite: 58/58 PASS** (`python3 server/test_emulator.py -v`, 40,4 giây). Smoke dùng user Android khách với save riêng. Chế độ máy bay đang bật và Wi-Fi dùng để điều khiển ADB. Ảnh [Slot](analysis/qa_r7_10/slot_reward.png), [Slot sau khi nhận](analysis/qa_r7_10/slot_after.png), [rung cây trả phí](analysis/qa_r7_10/tree_paid_reward.png), [mốc 10](analysis/qa_r7_10/tree_milestone.png), [rương banner](analysis/qa_r7_10/banner_chest.png). Các bảng xác suất và mốc Cây Tiền, Slot, Đập Trứng thuộc preset phục hồi, chưa có bảng thưởng máy chủ gốc để xác nhận.

Vòng cài đè `790 → 800` trên Pixel 3 XL đã xác minh cùng chữ ký. SHA-256 của bốn profile S1 và `accounts_index.json` khớp bản sao lưu trước nâng cấp. Bản sao lưu riêng có SHA-256 tại `server/backups/pre_r7_10_pixel_790`. Git theo dõi mã và báo cáo, APK và save lưu trong các thư mục bỏ qua của repo.
