# R7.15 — Mộ Thần Binh và trang bị Kim

Baseline `checkpoint-vn-r7.14` (`8dca0fb`), APK standalone 827. Bản R7.15 là **APK 828**, `5.0.4.98-r7.15`, package `com.cmn.inuyasha.revival`. SHA-256 `1995de0ff2526a2f6e134849199f143f121b81e0ddeef333876e5b5ca838ec93`. Chứng thư ký khớp APK 827. [APK 828](analysis/vn/patched/com.cmn.inuyasha.revival_r7_15_828_standalone.apk)

## Kiểm kê 20 trang bị Kim

| Nhóm | Vũ khí | Mũ | Áo | Phụ kiện | Nguồn cấp Kim xác minh được |
| --- | --- | --- | --- | --- | --- |
| Naohi | `13010801` Naohi-Kiếm Eimaro | `13020801` Naohi-Mũ Ziya | `13030801` Naohi-Áo Waita | `13040801` Naohi-Bùa Tụ Hồn | VN có đủ model và tiến giai. Luồng lên phẩm từ Naohi Đỏ có công thức tham khảo ở TW, cần dữ liệu hoặc payload VN để kích hoạt. |
| Tensho | `13010802` Tensho-Kiếm Ma | `13020802` Tensho-Mũ Ma | `13030802` Tensho-Áo Ma | `13040802` Tensho-Bùa Ma | Có mẫu, hình, bộ và bảng tiến giai VN. Chưa tìm thấy nguồn cấp. |
| Spi | `13010803` Spi-Kiếm Trấn Yêu | `13020803` Spi-Mũ Trấn Yêu | `13030803` Spi-Áo Trấn Yêu | `13040803` Spi-Dây Trấn Yêu | Có mẫu, hình, bộ và bảng tiến giai VN. Chưa tìm thấy nguồn cấp. |
| Crime và Yêu Thần | `13010804` Crime-Giáo Ma | `13020804` Yêu Thần-Mũ Thần | `13030804` Yêu Thần-Áo Thần | `13040804` Crime-Dây Xích Ma | Có mẫu, hình, bộ và bảng tiến giai VN. Chưa tìm thấy nguồn cấp. |
| Món lẻ | `13010805` Kiếm Ma Thần | `13020805` Mũ Vạn Yêu | `13030805` Áo Thiên Tằm | `13040805` Lệnh Diệt Yêu | Có mẫu, hình và bảng tiến giai VN. Chưa tìm thấy nguồn cấp. |

Quét đủ 276 bảng Lua Config VN bằng 20 ID nguyên vẹn cho thấy ID Kim chỉ xuất hiện trong `EquipModel` và `EquipStepRelation`. Đối chiếu riêng đầu ra rương `GoodsOutputRelation`, danh sách triệu hồi `CallequipOutoddsBRelation`, thưởng/đổi sự kiện, cả hai shop và thưởng Mộ Thần Binh. Kiểm tra các pool runtime gồm XSSB và đầu ra Hợp Thành cho thấy **0/20 món Kim có nguồn phát hành gameplay xác minh được**. Các lượt cấp tài nguyên trong ca test dùng fixture của save cách ly. [EquipModel VN](analysis/vn/decompiled_src/Config/EquipModel.lua) · [Cường Hóa VN](analysis/vn/decompiled_src/Config/EquipLvUpuseRelation.lua) · [Triệu hồi VN](analysis/vn/decompiled_src/Config/CallequipOutoddsBRelation.lua) · [Hợp Thành VN](analysis/vn/decompiled_src/Config/EquipColorRelation.lua)

Nguồn đang hoạt động gần nhất là 12 lượt đổi phẩm Naohi ở `BddEquipShopRelation`. Mức cuối, dòng 9–12, đổi Naohi Hồng Tiến Giai 10 và 7.500 Chiến Công để lấy Naohi Đỏ và năm món Hồng theo đúng ô. Bản 828 kiểm được toàn bộ mười lần Tiến Giai và đổi thành công. `EquipColorLeadRelation` thu hồi từ TW 1.4 có bốn dòng Naohi Đỏ Tiến Giai 10 → Naohi Kim, yêu cầu một món Kim cùng ô và 10 triệu Vàng. Lua VN còn tên RPC `EquipColorLeadUp` nhưng thiếu bảng quan hệ. Các đường lên phẩm sớm trong bảng TW có chi phí khác đường đổi shop VN. Dữ liệu đang có cũng chưa xác nhận nguồn món Kim đầu tiên, nên không nhập công thức TW hoặc thêm lượt quay. [Shop VN](analysis/vn/decompiled_src/Config/BddEquipShopRelation.lua) · [Luồng RPC của client VN](analysis/vn/decompiled_src/Equipment/EquipmentScene.lua#L960) · [Bảng tham khảo TW](analysis/tw_1.4_recovered_configs/EquipColorLeadRelation.lua)

## Tiến Giai, Cường Hóa và hoàn tác

- Cấp thử cả 20 model qua bộ cấp tài nguyên, gắn đúng bốn ô, kiểm `Property`, `FightInfo` và tải lại. `Equip.EquipStepUp [equipId,materialId]` áp dụng toàn bộ dòng VN. Dùng đúng màu và loại ô, xác minh nguyên liệu rảnh đang ở bậc 0, cấp cường hóa của món đích và Vàng. Kim có bậc 0–10. Bước đầu của Naohi Kim cần trang bị ở cấp 80, Kim khác cần cấp 70, giá 3.000.000 Vàng. Bậc mới cộng đúng HP/Công/Thủ theo bảng gốc.
- `Equip.EquipRebirth` kiểm tra trạng thái trang bị và giá KC của phẩm/bậc. Với đầu tư đã ghi nhận, giữ món gốc, trả Vàng cường hóa và trả Vàng cùng đúng model nguyên liệu Tiến Giai. Ca lỗi ghi save, thiếu Vàng/KC hoặc gửi lại ID đều giữ tài nguyên. Món Kim có bậc/cấp cũ vẫn giữ giá trị đã lưu.
- APK 827 cho cường hóa Kim miễn phí qua RPC do tra bảng thiếu dòng màu 8. Lua gốc cũng lỗi khi lấy giá. VN, EN, ZH và TH có bảy nhóm giá giống nhau và đều thiếu Kim. APK 828 trả `-1331` và hiển thị lý do trong màn Cường Hóa. Ca Tiến Giai Kim dùng mẫu được chuẩn bị sẵn ở mức cường hóa VN yêu cầu. Với dữ liệu hiện có, người chơi chưa thể hoàn tất vòng nhận và cường hóa Kim từ cấp 0.

## Mộ Thần Binh

- Mở **18/51 ải**, sáu tầng 11–16 và 54 cấu hình độ khó. Danh mục VN vẫn đủ 51 ải. Giải mã lực chiến VN ở cả dạng số và hậu tố `K`. FAP khuyến nghị tăng dần theo ải ở từng độ khó, từ 29.800/34.100/43.700 đến 540.000/640.000/770.000. Cả 54 đội có thủ lĩnh đúng model ở `BddNodeModel` và FAP sai số dưới 25 do làm tròn chỉ số.
- 18 đội được ghi nhãn mô phỏng. Dùng thủ lĩnh của ải và hai model còn lại ở cùng tầng, giữ tỷ lệ chỉ số và kỹ năng VN rồi canh theo lực chiến khuyến nghị. Điều kiện thắng giữ đúng dữ liệu VN, gồm 4 hoặc 6 người sống, tối đa 3 hoặc 4 lượt, và HP còn trên 60% hoặc 70%. Đối chiếu các khóa độ khó mở rộng trong Lua VN chỉ tìm đến `BddPointModel`. Tài nguyên hiện có chứa chân dung và kỹ năng, chưa có đội hình gốc cho từng trận. Các bản ghi gameplay công khai tìm được thiếu payload hoặc chi tiết đủ để thay fixture. [Audit gốc](R7_14_SOURCE_AUDIT.md) · [Điều kiện VN](analysis/vn/decompiled_src/Config/BddClearanceModel.lua) · [Bản ghi gameplay tham khảo](https://www.youtube.com/watch?v=4RqPlgZXvWk)
- Kiểm cả trận thua, 18 trận thắng bằng sáu tướng cấp 80 với trang bị Đỏ, 54 sao, sáu rương tầng, năm lượt chọn buff, cửa hàng, quét, reset, BXH và tải lại. Trên Pixel, lượt đầu đạt 1.515 Chiến Công và chặn kết toán lại bằng mã lượt đã dùng. Hồ sơ 827 đã nhận rương tầng 12 thấy buff chuyển tầng đúng một lần khi lên bản mới.
- Nhiệm vụ ngày #21 và Nhiệm vụ Bạo Kích #7 ghi theo lượt chiến đấu đã kết toán trong kỳ. Mục tiêu #18 và bảng Đua Top ngày 6 dùng kỷ lục sao Mộ Thần Binh đã lưu. Shop dùng ngưỡng kỷ lục theo VN, nên lượt reset không khóa lại các món đã đạt mốc. Các lượt nhận trùng và giao dịch thiếu nguyên liệu được kiểm bằng save thử nghiệm. [Regression Python](server/test_r715.py) · [Data VN](server/bdd_data.json)

## Test the Delta

**100/100 Python và 14/14 Lua PASS.** Đối chứng backend trích từ APK 827 và 828 qua HTTP loopback thật trên Pixel 3 XL, dùng CPython Android và thư mục save tạm riêng. Mỗi kết quả được kiểm trên payload và trạng thái sau reload. Chín tệp backend trong APK 828 khớp mã nguồn. APK 827, bốn save S1 và các checkpoint đã nghiệm thu được giữ nguyên. Pixel chính vẫn cài 827. [Đối chứng Pixel](analysis/qa_r7_15/android-rpc.log) · [Regression Lua](poc/test_r715_lua.py)
