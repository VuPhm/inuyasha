# R7.12.2 — Nghiệm thu hotfix Đột Phá

Baseline `checkpoint-vn-r7.12.1` (`14b86d6`), APK 823. R7.12.1 đã nghiệm thu 70/70 Python và 7/7 Lua. APK R7.12.2 là **standalone 824**, `5.0.4.98-r7.12.2`, package `com.cmn.inuyasha.revival`, SHA-256 `fd88bf2b7a307484f9b4c90e0fe3ed9168de640697b0266f1d211b2042cf9496`. Chứng thư ký trùng APK 823. Bảy tệp backend nhúng khớp mã nguồn. So sánh asset và thư viện giữa hai APK chỉ thấy thay đổi gói backend, tệp phiên bản backend và `HeroUpdateScene.luac`. [Nghiệm thu R7.12.1](R7_12_1_ACCEPTANCE_REPORT.md) · [APK 824](analysis/vn/patched/com.cmn.inuyasha.revival_r7_12_2_824_standalone.apk)

## Nguyên nhân ca người chơi gặp

**Lv35 là cấp của tướng đang được đột phá từ +4 lên +5.** `HeroUpdateScene.lua` so `self.mHero.Lv` với `needLv` của bậc hiện tại. Lịch sử thật trên Pixel có năm lượt `Hero.HeroStepUp` cùng payload, đều `Status=-1`, với chín ID nguyên liệu. Lần thành công ngay trước đó trên cùng tướng khớp dòng 15003 (+3 → +4), và lần thành công sau nhóm lỗi khớp dòng 15004 (+4 → +5). Đối chiếu sổ giao dịch tại chỗ xác nhận Vàng đủ. Số đá khôi phục từ lần cấp gần nhất và các lần đột phá đã trừ nằm dưới ngưỡng 2.200. Nhật ký lịch sử chỉ ghi mã lỗi tổng quát. Nhánh thiếu đá được xác nhận bằng phép tái hiện trên chính backend trích từ APK 823. [Đối chiếu lịch sử trên Pixel](analysis/qa_r7_12_2/owner-diagnosis.log) · [Điều kiện cấp trên client](analysis/vn/decompiled_src/Hero/HeroUpdateScene.lua#L1022)

Handler 823 trừ đá trong save nhưng bỏ sót `Avatar.GoodsInfo`. Client dùng số đá cũ để kiểm tra nút Đột Phá, nên vẫn gửi yêu cầu cho bậc tiếp theo. Backend kiểm tra số dư thực rồi trả **HTTP 200, ServerId 1, Status -1**. `ServerMessage[-1]` hiển thị “Server không tồn tại”. Cùng handler đó bỏ qua kiểm tra và tiêu hao bảo vật. Nó cũng xóa theo ID tướng/trang bị do client gửi mà chưa đối chiếu đủ công thức. [Payload client VN](analysis/vn/decompiled_src/Hero/HeroUpdateScene.lua#L2132) · [Xử lý Avatar](analysis/vn/decompiled_src/Data/NetworkResData.lua#L571)

| Công thức VN | Cấp tướng | Chi phí |
| --- | --- | --- |
| 15001 (+1 → +2) | 10 | 70.000 Vàng, 400 Đá Đột Phá, 2 sách `14010501`. Ca audit R7.12. |
| 15003 (+3 → +4) | 30 | 250.000 Vàng, 1.400 đá, 2 sách `14010502`, 2 ngựa `14020502`, 1 tướng cùng model. |
| 15004 (+4 → +5) | 35 | 550.000 Vàng, 2.200 đá, 4 sách `14010501`, 4 ngựa `14020501`, 1 tướng cùng model. |
| 15005 (+5 → +6) | 40 | 1.000.000 Vàng, 3.200 đá, 4 sách `14010502`, 4 ngựa `14020502`, 1 tướng cùng model. |
| 255004 (nhân vật chính, +4 → +5) | 35 | 400.000 Vàng, 2.500 đá, 400 Tâm Naohi `16050090`, 2 sách `14010501`, 2 ngựa `14020501`. |

`ConfigFunc` chuyển `useNum` thành số tướng cùng model. Client chỉ truyền ID thực thể tướng/bảo vật. Vàng, đá và Tâm Naohi được tính và trừ theo công thức server. Các công thức và chỉ số chiến đấu VN giữ nguyên. [HeroStepRelation VN](analysis/vn/decompiled_src/Config/HeroStepRelation.lua#L225) · [ConfigFunc](analysis/vn/decompiled_src/Common/ConfigFunc.lua#L156)

## Test the Delta

Đã chạy RPC thật qua `POST /client.aspx` trên Pixel 3 XL, với backend trích từ từng APK và thư mục save cách ly. Các ID dưới đây thuộc fixture.

| APK | RPC và payload | Kết quả |
| --- | --- | --- |
| 823 | `Hero.HeroStepUp ["fixture-inuyasha",["duplicate-3","before-book-1","before-book-2","before-horse-1","before-horse-2"]]` | `Status=0`, bậc +4. 3.500 → 2.100 đá trong save, thiếu `Avatar.GoodsInfo`, bốn bảo vật vẫn còn. |
| 823 | `Hero.HeroStepUp ["fixture-inuyasha",["duplicate-4","lv35-book-1","lv35-book-2","lv35-book-3","lv35-book-4","lv35-horse-1","lv35-horse-2","lv35-horse-3","lv35-horse-4"]]` | `Status=-1`, thiếu 100 đá. Save giữ nguyên bậc, Vàng, đá, bảo vật và tướng. |
| 824 | Cùng hai danh sách ID, thêm bậc kỳ vọng `3` hoặc `4`. | +3 → +4 trả `0`, gửi lại 2.100 đá trong Avatar, tiêu đúng bốn bảo vật. Gửi song song cùng payload chỉ một lượt thành công. Bước Lv35 thiếu đá trả `-1802`, tài sản giữ nguyên. |
| 824 | Cấp thêm 100 đá cho fixture, gửi lại payload bậc 4, rồi phát lại sau thành công và sau restart. | Lên +5 đúng một lần. Trừ 550.000 Vàng, 2.200 đá, tám bảo vật và một tướng trùng. Mọi lượt phát lại trả `-39`. Reload giữ đúng kết quả đã lưu. |

[Log RPC đầy đủ](analysis/qa_r7_12_2/android-rpc-delta.log)

- Backend đối chiếu cấp tướng, bậc, loại, model, số lượng, sở hữu và trạng thái nguyên liệu trước khi trừ. Tướng trùng phải rảnh, Lv1, +0. Bảo vật phải rảnh, Lv0, +0. Đá và Tâm Naohi tính trên tất cả stack cùng model như client VN. Lỗi thiếu Vàng, thiếu vật phẩm, cấp tướng, đang trang bị và yêu cầu trùng có mã riêng.
- Kiểm tra và cập nhật chạy dưới khóa profile. Save ghi bằng một lần thay tệp nguyên tử. Regression mô phỏng lỗi ghi save, xác nhận trạng thái và sổ Vàng giữ nguyên, rồi thử lại thành công một lần. Client cập nhật kho từ `Avatar.GoodsInfo` và khóa gửi lại đến khi có kết quả hoặc hoàn tất hiệu ứng.
- APK 824 gửi `[heroId, materialIds, expectedStep]`. Request còn hai tham số được hỗ trợ tại các bước có thể phân biệt bằng lượng nguyên liệu thực thể. Với hai công thức liên tiếp cùng dùng danh sách rỗng, bước sau cần thêm bậc kỳ vọng để tránh coi request lặp là lần đột phá mới.
- **76/76 Python, 8/8 Lua PASS.** Giữ 70 ca Python và bảy ca Lua đã nghiệm thu, thêm sáu ca Python và một ca Lua. [Backend](server/emulator.py#L3355) · [Python regression](server/test_emulator.py#L4063) · [Lua regression](poc/test_r7122_lua.py)

## Nâng cấp Pixel 3 XL

Cài đè **823 → 824** trên Android Owner. Trước khi mở 824, chỉ mục và bốn save S1 trùng từng byte với bản sao trước cài đặt. APK 824 khởi động thành công. RPC đọc trên bản cài xác nhận cả bốn tài khoản giữ nguyên tướng, trang bị, bảo vật, túi, Vàng, Kim Cương, cấp, VIP, lực chiến và các mốc đã nhận. Tài khoản đang chọn giữ nguyên. Giao dịch tiêu hao chỉ chạy trên save QA. Checkpoint R7.12.1 và STABLE R6.2 (`5fed4bb`) giữ nguyên. [Đối chiếu nâng cấp](analysis/qa_r7_12_2/owner-upgrade.log)

## Bàn giao R7.13 và R7.14

- **R7.13 tiếp tục tài nguyên, lực chiến, tiến trình sự kiện và hợp thành đỏ.** RPC `Equip.EquipCompose [[equipId...]]` dùng đường riêng. Save QA xác nhận bốn vật liệu màu 6 trả `-1` ở điều kiện cần năm món. Năm vũ khí màu 6 tạo một vũ khí đỏ `13010701`. Với năm vũ khí màu 7, bảng VN có `colorFinally=0`, nhưng handler vẫn trừ phí và xóa vật liệu trước khi thử cấp fallback vòng cổ `13040215` dưới loại vũ khí `1301`. Kết nối đóng trước khi có Status. Đây là lỗi riêng đã tái hiện, còn thao tác cụ thể của người chơi cần đối chiếu ở R7.13. [Trace QA](analysis/qa_r7_12_2/r713-equip-triage.log) · [EquipColorRelation VN](analysis/vn/decompiled_src/Config/EquipColorRelation.lua)
- **R7.14 ưu tiên 51 ải Mộ Thần Binh.** Bắt đầu bằng mở khóa, danh sách, chiến đấu, thắng/thua, sao và save/reload. Tiếp theo nối buff, thưởng, shop, quét, nhiệm vụ và sự kiện liên quan theo dữ liệu VN. [Lộ trình](PROJECT_ROADMAP.md#iv-lộ-trình-các-round-tiếp-theo-r77)
