# R7.14 — Ngộ Đạo, phẩm trang bị và Mộ Thần Binh

Baseline R7.13, APK standalone 825. Backend 825 và mã nguồn đầu kỳ khớp byte. APK 825 giữ SHA-256 `4ae8768933da2ba494ac33e6d7a5d6c4deb773089167811d18b1cd42a955cc3d`. Bản R7.14 là **APK 827** `5.0.4.98-r7.14`, package `com.cmn.inuyasha.revival`. SHA-256 `12b56e117377452c5ed189a89c4029d5eb80ad5f73d7f333604597c6f5075795`. Chứng thư ký trùng 825. Chín tệp backend nhúng khớp mã nguồn. [APK 827](analysis/vn/patched/com.cmn.inuyasha.revival_r7_14_827_standalone.apk)

## R7.14A — Ngộ Đạo

Truy vấn đọc và đếm log trên Pixel xác nhận hồ sơ ở **Lv28, Ngộ Đạo 22, 68 sao chiến dịch, còn 2 sao, đủ Vàng**. Hàng VN số 23 cần Lv1, 3 sao và 3.000 Vàng. APK 825 trả tổng 68 ở `LightenStar.GetLightenStarInfo [].Value.StarCount`. Client so 68 với giá 3 sao và cho bấm. `LightenStar.LightenStar []` đã trừ 66 sao đã dùng khi kiểm tra nên trả HTTP 200 `Status=-1`. Đây là thiếu một sao ở tài khoản đó và lỗi đồng bộ UI/mã lỗi. Backend đã có handler cho mốc 23. [Tổng hợp hồ sơ tại chỗ](analysis/qa_r7_14/owner-star.log) · [Bảng Attrtree VN](analysis/vn/decompiled_src/Config/AttrtreeModel.lua)

APK 827 gửi sao còn dùng trong `StarCount` và tổng sao chiến dịch trong `StarCountTotal`. RPC một lần và một chạm dùng cùng điều kiện config cho dải nút. Mã `-2213` thiếu sao, `-1118` thiếu Vàng, `-2212` thiếu cấp và `-2211` đạt giới hạn. Ca thử 68 sao giữ nguyên bậc và vàng. Có đủ 69 sao thì lên bậc 23, tiêu đúng 3.000 Vàng và còn 0 sao dùng được. Số sao chiến dịch giữ 69. Lỗi ghi save khôi phục cả Vàng và mốc.

`xunyuAddNum` là giá trị cộng dồn. Bản cũ cộng lại toàn bộ giá trị ở từng nút. Bản mới chỉ cộng phần tăng và giữ số lượt Tầm Ngọc đã lưu trước bản vá. Test mốc 28 xác nhận mở ô đội hình số 6 theo `AttrtreeSlotRelation`, cộng +7 Công ở ô nhận thuộc tính và cùng chỉ số trong `Property` lẫn `FightInfo`. Ca cao bao phủ mở trợ chiến ở 48 và nút cuối 1.000 bằng fixture. [Slot VN](analysis/vn/decompiled_src/Config/AttrtreeSlotRelation.lua) · [Lua hiển thị phần tăng](analysis/vn/decompiled_src/Practice/LightenStarScene.lua#L1399)

## R7.14A — Hợp Thành và trang bị Kim

| Màu đầu vào | Phẩm VN | Số món | Vàng theo công thức | Đầu ra |
| --- | --- | ---: | ---: | --- |
| 1 | Trắng | 5 | 1.000 | Lục |
| 2 | Lục | 5 | 5.000 | Lam |
| 3 | Lam | 5 | 10.000 | Tím |
| 4 | Tím | 5 | 100.000 | Cam |
| 5 | Cam | 5 | 500.000 | Hồng |
| 6 | Hồng | 5 | 5.000.000 | Đỏ |
| 7 | Đỏ | — | 10.000.000 trong dòng VN, giao dịch không thu | `colorFinally=0` |
| 8 | Kim | — | — | Không có dòng hợp thành |

`EquipModel` có 20 trang bị Kim, đều `quality=40`. Đủ 20/20 ảnh trong APK, gồm `assets/res/ui/zb_10801.png` của Naohi-Kiếm Eimaro. Đối chiếu ID mẫu trong `EquipModel`, `GoodsModel` và `EquipStepRelation` tìm thấy model và dòng tiến giai, chưa tìm được công thức năm Đỏ lên Kim. Bảng màu VN dừng ở 8. Handler từ R7.13 giữ đúng các đầu ra đến Đỏ. Regression R7.14 thử từng màu 1–8 và giữ cả năm món lẫn Vàng khi gửi màu Đỏ hoặc Kim. Mã giới hạn là `-1321`. [Công thức màu](analysis/vn/decompiled_src/Config/EquipColorRelation.lua) · [Model Kim](analysis/vn/decompiled_src/Config/EquipModel.lua#L4360)

## R7.14B — Mộ Thần Binh

APK 825 nhận `BddInfo.Info [1,1,1,1]` với `Status=0, Value={}` do thiếu dispatch. APK 827 trả danh mục 51 ải ở 17 tầng, trạng thái khóa và sao đã đạt. Lát chơi dùng dữ liệu từ 153 dòng độ khó VN. Mở tính năng ở Lv26. Màn chính có danh sách cuộn toàn bộ ải và ghi rõ **“Đội NPC mô phỏng (6/51 ải)”**. Sáu ải đầu `1111–1113`, `1211–1213` có thể đánh, thắng/thua và lưu tiến độ. Các ải sau có trạng thái chưa mở mô phỏng. [Audit gốc](R7_14_SOURCE_AUDIT.md)

Nguồn hiện có thiếu đội hình và chỉ số NPC gốc. Lát mô phỏng dùng model thủ lĩnh VN của ải cùng hai model còn lại trong tầng, giữ tỷ lệ HP/Công/Thủ từ model và canh tổng lực chiến theo `proposeFAP` của từng độ khó. Kỹ năng lấy từ model VN. Engine đấu có kết quả thực và kiểm điều kiện sống sót, số lượt hoặc phần trăm HP theo config. Server xác nhận bằng bản trận đã lưu và mã lượt, chặn trả thưởng lại qua reload. [Engine và handler](server/bdd_handlers.py) · [Dữ liệu trích](server/bdd_data.json)

Đã nối 12 phương thức `BddInfo` cho lát sáu ải. Chiến Công, thưởng lần đầu và rương tầng dùng bảng VN. Buff dùng bảng giá sao/xác suất VN. Reset dùng hạn VIP và phí bảng VN. Quét cần điều kiện cấp/VIP cùng thành tích ba sao của tầng. Shop kiểm tra Chiến Công, hạn mua và trang bị rảnh đúng model/bậc. Tiến độ và kho theo từng tài khoản, nhiệm vụ ngày #21 cập nhật khi thắng, BXH đọc sao đã lưu theo tuần.

## Test the Delta

**94/94 Python, 12/12 Lua PASS.** Regression bao phủ L22→23 đủ/thiếu sao, mốc mở slot, bậc cuối, lỗi ghi save, chuỗi hợp thành 1–8 và các luồng đã nghiệm thu R7.13. Kiểm thử Mộ Thần Binh bao phủ thua với đội hình yếu, sáu thắng bằng engine, mã lượt sai, nhận trùng, rương, buff, reset, quét, shop và tách tài khoản. [Python](server/test_r714.py) · [Lua từ APK](poc/test_r714_lua.py) · [RPC 825/826 trên Pixel](analysis/qa_r7_14/android-rpc-delta.log)

Backend 827 trùng từng byte với 826 đã chạy RPC trên Pixel. APK 827 tăng độ đọc của nhãn mô phỏng và nút mở danh sách. Đã chạy lại 12 ca Lua trên APK 827.

## Nâng cấp Pixel 3 XL

Đã cài đè 825 → 826 → 827. Chỉ mục và bốn save S1 trùng từng byte sau mỗi lần cài, trước lần mở đầu. Sau khi mở, RPC chỉ đọc xác nhận Vàng/KC, túi, đội hình, lực chiến, mốc Ngộ Đạo và quyền thưởng của cả bốn TK. TK2 đủ cấp nhận đủ 51 dòng của `BddInfo.Info` trên APK đã cài và RPC Ngộ Đạo trả đúng 2/68 sao. Các thử nghiệm đánh, tiêu Vàng và đổi trang bị chạy trên save cách ly. [Log 825 → 826](analysis/qa_r7_14/owner-upgrade.log) · [Log 826 → 827](analysis/qa_r7_14/owner-upgrade-827.log) · [Màn ải APK 827](analysis/qa_r7_14/pixel-bdd-827.png) · [Danh sách ải APK 827](analysis/qa_r7_14/pixel-catalogue-827.png) · [Cuộn tới ải 51](analysis/qa_r7_14/pixel-catalogue-end-827.png)
