# R7.12 — Sửa gameplay và cải thiện thao tác

APK Android standalone `com.cmn.inuyasha.revival`, `5.0.4.98-r7.12`, `versionCode=820`, ARM 32-bit. SHA-256 `94fe47d458b29ef47d1572288064c82854b2423c67f07576f3a7ab654d2024b4`. Chứng thư ký khớp APK 810 và cả bảy file backend đóng gói khớp source. [APK 820](analysis/vn/patched/com.cmn.inuyasha.revival_r7_12_standalone.apk) · [Kiểm kê gameplay](R7_12_GAMEPLAY_AUDIT.md) · [Kiểm kê sự kiện](R7_12_EVENT_INVENTORY.md)

## Thay đổi và kiểm thử delta

| Luồng | Kết quả |
| --- | --- |
| Túi Đá 2 `16020039` | Mở túi kiểm toàn bộ đầu ra và sức chứa trước khi trừ vật phẩm. Khi có đầu ra chưa hỗ trợ, client hiện “Phần thưởng này chưa được hỗ trợ. Vật phẩm vẫn còn trong túi.” Save thử nghiệm nhận ba túi từ sự kiện 6800. Mở một hoặc ba túi đều từ chối, vẫn còn ba sau một lượt chiêu mộ khác và tải lại. Kiểm tra đầu ra cũng áp dụng cho rương chọn. |
| Quà xếp hạng Thần Binh | Bỏ callback tự gọi lại của riêng `TimedEquipRankLayer`. Test Lua sử dụng luồng gắn nút X của APK và chạy thất bại trên 810, đóng đúng một lần trên 820. Cùng bộ test kiểm MessageBox đóng mặc định và callback riêng, rương mốc ở ba trạng thái. |
| Kho tướng | Nền 300. Người chơi đã nới giữ nguyên số lần, mỗi lần +5 với phí 10–200 KC cho 20 lần. Đã kiểm 299→300, từ chối chiêu mộ/rương/Trung Tâm Thưởng khi đủ 300, giữ quyền nhận quà và lấy được sau nới. Đã kiểm mức 400 và từ chối lần 21 trước khi trừ phí. Tính sức chứa từ số lần nới nên lặp tải cho cùng kết quả, không ghi lại cơ sở vào save. |
| Đột Phá → Tầm Bảo | Giữ gate Tầm Bảo Lv14. Truyền đúng Sách/Ngựa và ID bảo vật, cả khi chưa có mảnh. Quay lại đúng tab Đột Phá, cùng tướng và callback ban đầu. Tầm Bảo Ngay có RPC cho đúng bảo vật, dùng lượt săn NPC và hao hoạt lực theo luật có sẵn. Gate VN là Lv45 hoặc VIP7 từ Lv14. Kiểm đúng mảnh, dừng khi hết hoạt lực hoặc đã đủ mảnh, ghép được đúng bảo vật sau khi tìm. |
| Cây Ước Nguyện 4409 | Mốc 300 KC tính từ giao dịch nạp xác nhận trong kỳ, gồm thẻ tháng theo đường nạp hiện có. Đơn 810 có thời điểm hoàn tất trong kỳ được đọc lại. Tiêu KC, tổng trọn đời, bonus và VIP không mở điều kiện. Kiểm 180→240→300, chống tính hai lần, nhận quà một lần, giữ kết quả qua reload và kỳ sau về 0. Client đọc lại khi mở tab và hiển thị ba trạng thái thiếu nạp, đã kích hoạt, đã nhận đủ. Bảng quà và chu kỳ hiện hành giữ nguyên. |

## Giới hạn kho và SVIP

Client hiển thị `BagInfo.Size` bằng số nguyên. `BagModel[5]` trong nguồn VN có 100 ô khởi tạo, còn standalone 810 trả 200 và client dùng giá trị server. Bảng mở rộng có 20 hàng với 5 ô mỗi lần, nên trần từ 300 lên 400. Chỉ kho tướng đổi. Tướng đang trong đội hình vẫn được loại khỏi số ô sử dụng theo hành vi cũ. Giữ điều kiện phân giải Lv24. SVIP 10 là VIP nội bộ 20 với mốc 399.860 VIP EXP, không có hệ số túi. [Model VN](analysis/vn/decompiled_src/Config/BagModel.lua) · [Bảng nới](analysis/vn/decompiled_src/Config/BagExpandUseRelation.lua) · [VIP VN](analysis/vn/decompiled_src/Config/VipModel.lua#L488)

## Nghiệm thu Pixel 3 XL

- **Nâng cấp đè 810 → 820 trên Owner.** Sau khi cài và trước lần mở game đầu tiên, chỉ mục S1 và cả bốn save giống từng byte với bản sao lưu. Khi mở game, backend loopback đọc đúng bốn định danh, toàn bộ bản ghi tướng lần lượt giữ nguyên 195, 266, 1 và 63. Các túi trả về 300, 400, 300 và 300. TK2 giữ 20 lần nới. Tài khoản đang chọn không đổi. [Thư mục sao lưu trước nâng cấp](server/backups/pre_r7_12_pixel_810_final)
- **Quà xếp hạng.** Mở và đóng bằng X ba lần. Nền Thần Binh nhận chạm tiếp và mở/đóng rương mốc 50 khi có 0 điểm. [Popup mở](analysis/qa_r7_12/rank_open.png) · [Sau khi đóng](analysis/qa_r7_12/rank_closed.png)
- **Cây Ước Nguyện.** APK 810 hiện 303.040 KC trọn đời và nút Nạp Ngay dù đã nhận hết quà. APK 820 đọc 295.700 KC nạp trong kỳ trên cùng TK, giữ các mốc đã nhận và hiện “Đã nhận đủ quà Cây Ước trong kỳ này”. Thử nạp và nhận mới bằng save thử nghiệm. [810](analysis/qa_r7_12/pray_tree_810.png) · [820](analysis/qa_r7_12/pray_tree_820.png)
- **Tầm Bảo.** Lối tắt từ Đột Phá mở đúng tab Sách và chọn Sách Kaede. Người chơi xác nhận Tầm Bảo Ngay hoạt động, nhật ký thiết bị có lượt trả về thành công. Đường quay lại đúng tướng và bậc được kiểm bằng test Lua. [Đột Phá trước khi mở](analysis/qa_r7_12/breakthrough_before.png) · [Đúng bảo vật](analysis/qa_r7_12/treasure_target.png)

STABLE vẫn ở `checkpoint-vn-r6.2`. Các save STABLE/DEV trên Mac và các checkpoint cũ đã được đối chiếu với manifest gốc. Giữ package, khóa ký, vị trí save, pool tướng, tỷ lệ quay và cân bằng lực chiến. Smoke trên thiết bị dùng kết nối ADB và xác nhận backend loopback. Các bài thử thao tác tiêu tài nguyên được thực hiện trên save thử nghiệm, ngoài lượt Tầm Bảo Ngay do người chơi trực tiếp xác nhận.

## Chạy lại kiểm thử

```sh
python3 server/test_emulator.py -v
PYTHONPATH=/path/to/lupa python3 poc/test_r712_lua.py \
  analysis/vn/patched/com.cmn.inuyasha.revival_r7_11_standalone.apk \
  analysis/vn/patched/com.cmn.inuyasha.revival_r7_12_standalone.apk
```

**65/65 Python và 5/5 Lua PASS.** Bộ test Lua tải mã giải từ APK và mô phỏng đối tượng Cocos để chạy trực tiếp callback. Đã tải lại hai lần bản sao tách riêng của bốn hồ sơ Owner 810, kiểm cùng định danh, cấp VIP, số lần nới và toàn bộ bản ghi tướng. Các thao tác có thể hao tài nguyên chạy trên hồ sơ thử nghiệm.
