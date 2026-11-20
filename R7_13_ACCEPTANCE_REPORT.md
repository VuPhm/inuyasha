# R7.13 — Economy, Equipment & Event Consistency

Baseline APK standalone 824, đã nghiệm thu R7.12.2. Backend trích từ 824 khớp từng byte với mã nguồn trên worktree đầu kỳ. Worktree có hotfix R7.12.2 nhưng ref Git `checkpoint-vn-r7.12.2` chưa tồn tại. APK 824, bản chụp mã nguồn đầu kỳ và các checkpoint Git hiện có được bảo toàn. [R7.12.2](R7_12_2_ACCEPTANCE_REPORT.md) · [Bản chụp mã nguồn 824](analysis/qa_r7_13/baseline-824)

APK standalone **825**, `5.0.4.98-r7.13`, package `com.cmn.inuyasha.revival`. SHA-256 `4ae8768933da2ba494ac33e6d7a5d6c4deb773089167811d18b1cd42a955cc3d`. Chứng thư khớp APK 824. Bảy tệp backend nhúng khớp nguồn. Ba tệp Lua thay đổi thuộc Shop Thần Bí, hợp thành và giá chiêu mộ. Config VN, dữ liệu tướng và pool/tỷ lệ chiêu mộ giữ nguyên. [APK 825](analysis/vn/patched/com.cmn.inuyasha.revival_r7_13_825_standalone.apk)

## Shop Thần Bí

`MysteryShop` là module 2100 cho tab thường và 2101 cho tab cao cấp. Tab SVIP 2102 theo client dùng mốc 00:00 và ẩn đồng hồ. Module 4300 là Thương Nhân Hạn Giờ. Client `MysticalStoreScene` gửi `GetInfo []` hoặc `SeniorGetInfo []`. Callback mỗi giây đọc `LastFreshDate` và so với `NetworkResData:getCurrentTime()`. `HttpClient` đồng bộ đồng hồ này từ `TimeTick` tính bằng giây Unix. [Các module](analysis/vn/decompiled_src/Config/Enums.lua#L66) · [Callback VN](analysis/vn/decompiled_src/Store/MysticalStoreScene.lua#L90) · [Đồng bộ đồng hồ](analysis/vn/decompiled_src/Data/NetworkResData.lua#L286)

APK 824 trả HTTP 200, `Status=0`, `TimeTick=1795143599` ở 09:59:59 UTC+7 và thiếu `LastFreshDate`. Client thay trường thiếu bằng 0, liên tục đánh giá đã hết hạn, gọi lại thông tin và giữ nhãn mặc định `00:00:00`. Các ID hàng trong RPC giữ nguyên qua ba lần gọi. Lua đóng gói 824 tái hiện hai lượt truy vấn dư trên hai nhịp liên tiếp. [RPC baseline](analysis/qa_r7_13/mystery-824-rpc.log)

APK 825 trả hạn bằng giây Unix và chỉ làm mới hàng khi chạm hạn. Chu kỳ tab thường 7.200 giây lấy từ `freeRefreshCD` VN và dùng các mốc tính từ 00:00 UTC+7. Bảng VN quy định mốc tab cao cấp là 12:00 và 18:00. Mốc hàng và mốc cộng lượt miễn phí lưu theo profile. Đọc lại, mua, khởi động lại và gọi dồn cùng kỳ giữ nguyên ID hàng và trạng thái đã mua. Trên save cũ, lần mở đầu thêm hạn vào danh sách đang có. Client chỉ gửi một request thông tin đang chờ cho mỗi tab. [Config VN](analysis/vn/decompiled_src/Config/MysteryshopConfig.lua) · [RPC mới ở 09:59:59, 10:00:00 và 10:00:01](analysis/qa_r7_13/mystery-825-rpc.log)

`RefreshtGoodsList [1|2|3]` và bản cao cấp là làm mới thủ công. Phí lần lượt là một lượt miễn phí, 1/5 lệnh hoặc 20/100 KC theo tab. Tự làm mới dùng đường đọc thông tin, giữ phí và hạn của các lần làm mới thủ công độc lập. Bộ test bao phủ mốc 10:00, 12:00, 18:00, 00:00, mua trùng, load save cũ và hai TK S1.

## Các hạng mục còn lại

| Hạng mục | Thay đổi và kết quả |
| --- | --- |
| Hợp thành đỏ | `Equip.EquipCompose [[id...]]` kiểm đủ năm thực thể khác nhau, cùng phẩm chất, còn sở hữu, rảnh, chưa tiến giai, tài nguyên đủ và đầu ra hợp lệ. Màu 6 → 7 trừ 5 triệu Vàng và cấp đúng một trang bị đỏ. Màu 7 có `colorFinally=0` nên bị từ chối trước khi trừ. Toàn bộ Vàng, kho và bộ đếm ghi chung một lần. Mô phỏng lỗi lưu xác nhận rollback. Phát lại và reload xác nhận đầu vào chỉ tiêu một lần. |
| Ưu đãi 4417 | Backend dùng `RefNum` của kỳ đang hiển thị và làm tròn lên giống Lua. Trong kỳ, Túc Mệnh 64 KC, Linh Hồn 224 KC, Linh Hồn x10 2.144 KC. Ngoài kỳ về 80, 280 và 2.680 KC. Vé và lượt miễn phí giữ cách xử lý cũ. |
| Thời trang | `heroAttrStrR` nhóm 2 là toàn đội. Chỉ tính một bản mỗi model, ưu tiên bản đã nâng bậc như client. Bậc 0 → 1 của `19010001` cộng **60 Công, 400 HP và 20 Thủ** mỗi tướng ra trận. `Slot.Property`, tổng lực chiến và `Battle.GetFightInfo` dùng cùng chỉ số. Asset, bảng phí và bảng chỉ số VN giữ nguyên. |
| Nạp/tiêu theo kỳ | 4401/4407 dùng đơn nạp lớn nhất, 4402 dùng tổng nạp, 4403 dùng KC thực tế đã trừ, 4405 dùng các ngày VN đủ 60 KC liên tiếp. BXH 4421/4422, quà chọn 4429, shop điểm 4428 và nhiệm vụ nạp/tiêu 4700 lấy số từ kỳ hiện tại. BXH XSSB chỉ đọc điểm S1 từ đúng instance. Đơn hoàn tất có timestamp của save cũ được phục hồi khi thuộc đúng kỳ. Số tiêu suốt đời giữ nguyên trong save và không tự chuyển thành tiến độ kỳ. Kỳ thủ công mới bắt đầu trống, kể cả khi reset trong cùng giây. |

[RPC cách ly trên Pixel](analysis/qa_r7_13/android-rpc-delta.log) · [Công thức trang bị VN](analysis/vn/decompiled_src/Config/EquipColorRelation.lua) · [Phạm vi chỉ số thời trang VN](analysis/vn/decompiled_src/Formation/FashionStepUpLayer.lua#L38)

## Nghiệm thu Pixel 3 XL

**86/86 Python và 9/9 Lua PASS.** Đã chạy RPC thật với backend trích từ APK 825 trên Pixel và save cách ly. APK 825 cài đè từ 824 thành công. Chỉ mục và bốn save trùng từng byte trước lần mở đầu. Truy vấn bốn hồ sơ trên bản cài xác nhận tướng, trang bị, bảo vật, thời trang, túi, Vàng, Kim Cương, VIP, cấp và quyền thưởng giữ nguyên. Lực chiến khớp công thức thời trang VN. Tài khoản đang chọn và STABLE R6.2 giữ nguyên. [Đối chiếu nâng cấp](analysis/qa_r7_13/owner-upgrade.log)

Đã bắt đầu R7.14 bằng đối chiếu nguồn. Bộ config VN có 51 ải và 153 mức khó, còn thiếu nguồn đáng tin cậy cho đội hình và chỉ số NPC trong `FightInfo`. [Audit R7.14](R7_14_SOURCE_AUDIT.md)

## Chạy lại kiểm thử

```sh
PYTHONPATH=server python3 -m unittest -v test_emulator test_r713
PYTHONPATH=/path/to/lupa python3 poc/test_r713_lua.py \
  analysis/vn/patched/com.cmn.inuyasha.revival_r7_12_2_824_standalone.apk \
  analysis/vn/patched/com.cmn.inuyasha.revival_r7_13_825_standalone.apk
```

[Ca hồi quy Python](server/test_r713.py) · [Ca kiểm callback Lua đóng gói](poc/test_r713_lua.py)
