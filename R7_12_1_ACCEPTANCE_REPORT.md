# R7.12.1 — Hotfix nhận thưởng

Baseline `checkpoint-vn-r7.12` (`46708a4`), APK 820. Bản hotfix cuối là APK standalone **823**, `5.0.4.98-r7.12.1`, package `com.cmn.inuyasha.revival`. SHA-256 `91c76bbf355c43ce4710eca8dee71031000b27db27c5896450c941c437ef6dcd`. Chứng thư ký khớp 820, bảy file backend nhúng khớp source. [APK 823](analysis/vn/patched/com.cmn.inuyasha.revival_r7_12_1_823_standalone.apk)

## Chẩn đoán

`HttpClient.lua` gửi `ServerId` từ server đang đăng nhập và tra `ServerMessage[response.Status]`. `-1` trỏ tới “服务器不存在”, bản VN là “Server không tồn tại”. Các lỗi tái hiện trả **HTTP 200, ServerId 1 và Status -1** từ handler đã dispatch. Log lịch sử Owner ghi nhận các lượt chọn `DrawGoldHero [12011004]` và nhận `DrawReward [3,1]`, `[4,1..6]` thành công. Log đó thiếu lượt bị báo lỗi, nên dữ liệu dưới đây lấy từ tái hiện bằng save thử nghiệm trên backend trích từ APK 820 và 821, chạy trực tiếp trên Pixel. [Log tái hiện trên Pixel](analysis/qa_r7_12_1/android-rpc-delta.log)

| Luồng | APK 820 | Bản sửa từ 821 |
| --- | --- | --- |
| Chọn tướng banner | Popup thật gửi `TimedRecruitInfo.DrawGoldHero [12011004]`. Khi quyền thuộc 81 nhưng banner đang chọn là 82, handler dùng 82 và trả `Status=-1, Value={}`. Banner 81 vẫn còn quyền. Test R7.5 chỉ gửi ID tướng trong ngữ cảnh banner đã khớp. | Popup giữ `ActivityEnumId` và `EventInstanceId` của ảnh chụp lúc mở. Gửi `[12011004,81,"timed_recruit:81:d:2026-11-20"]`. Nhận `Status=0`, `BaseGetGameResourceList` có đúng một InuYasha và `RecruitInfo.DrawGoldHero=1`. Banner 82 giữ nguyên quyền. |
| Thành tích 4918 | `SuccessTargetInfo.GetInfo []` trả 8.900 là điểm tổng hợp giả lập, dùng màu, cấp cường hóa, tinh luyện của bốn món có điểm cao nhất. Lua ghép `8900/4` và bật nút theo điều kiện `>=4`, nhưng `DrawReward [19,4]` so với mốc 12.500 nên trả `-1`. Test R7.4 chỉ nhận mốc đăng nhập. | Mỗi mốc đếm tối đa bốn món phân biệt đang trang bị đạt phẩm cấp VN. Phẩm cấp là `EquipModel.itemLv + EquipStepRelation.itemLv` theo đúng model và bậc. Fixture hiện `4/4` ở mốc 12.500 và `0/4` ở mốc 62.500. `Claimable` là nguồn chung cho nút Nhận, trạng thái mốc và kiểm tra khi bấm. |
| Rương tổng theo ngày | Client gửi `SuccessTargetInfo.DrawTotalReward [ngày]`, handler bỏ tham số, cấp các ngày đang mở, đánh dấu hàng loạt và đặt `IfDraw=1`. Request tiếp theo báo lỗi. | `[ngày]` chỉ nhận ngày đó. Danh sách còn nhận và đã nhận trả về từ server. `[]` là kết toán sau bảy ngày. Dữ liệu đã nhận từ bản cũ được giữ để tránh trả trùng. |

[RPC banner](server/event_handlers.py) · [Backend thành tích](server/emulator.py) · [Gắn bản vá vào APK](poc/build_standalone_apk.py) · [Cách client VN tính phẩm cấp](analysis/vn/decompiled_src/Equipment/NewArtifactLayer.lua#L291)

## Rà soát và bảo toàn quyền nhận

- Nhóm 4900–4935 dùng cùng trạng thái từng mốc từ server cho phép Nhận. Giữ nguyên bảng thưởng và các phép đo của nhóm khác. Những mục phụ thuộc Mộ Thần Binh, tiến giai hoặc tính năng chưa nối thuộc phạm vi kiểm kê riêng. [Kiểm kê R7.12](R7_12_EVENT_INVENTORY.md)
- Đối chiếu rương mốc banner `DrawCreditReward`, rương chọn trong kho `GoodsUseForBoxChoice` và đổi quà `SuccessTargetInfo.Exchange`. Luồng rương mốc và kho dùng tham số khác, còn đổi quà dùng cặp ngày/mốc. Các đường đó được giữ nguyên. Một số guard riêng vẫn dùng mã lỗi tổng quát trong baseline, không áp ánh xạ chung.
- Kiểm tra quyền, danh sách tướng hợp lệ, kỳ và sức chứa trước khi cấp. Sai kỳ `-3106`, banner tắt `-3115`, lựa chọn sai `-3123`, hết quyền `-3116`, đầy túi `-2005`. Thành tích chưa đủ `-6001`, ngày chưa thể nhận `-6004`, đã nhận `-3137`. Xác thực phần thưởng trước khi đánh dấu nhận. Các ca tái hiện từ chối không mất quyền, lượt hoặc vật phẩm.
- Khi kiểm sau cài 821, TK3 còn có một lỗi riêng ở búa khởi tạo Đập Trứng. Sổ giao dịch đã ghi khóa cấp 5 búa, còn profile chưa lưu vật phẩm và cờ tương ứng. Truy vấn `Player.GetInitData` gặp khóa trùng và đóng kết nối. Bản 822 khôi phục đúng stack và ghi save ngay lúc khởi tạo. Bản 823 tạo snapshot túi sau bước khởi tạo để client có đúng 5 búa từ phản hồi đầu tiên. Qua tải lại, số búa và số bản ghi cấp đều giữ nguyên. [Khởi tạo Đập Trứng](server/r79_event_handlers.py) · [Snapshot đăng nhập](server/emulator.py)
- **70/70 Python, 7/7 Lua PASS trên bản cuối.** Bao phủ đủ 6 lựa chọn theo pool 81/82, chọn sai banner/kỳ, túi đầy và thử lại sau nới, mốc 4918 đủ/chưa đủ, đầu ra không hỗ trợ, nhận theo ngày, nhận trùng và reload. Bộ Lua thực thi popup đóng gói để kiểm đường truyền và việc giữ popup khi request thất bại.

## Nghiệm thu nâng cấp Pixel

Đã cài đè 820 → 821 → 822 → 823 trên Android Owner. Sau mỗi lần cài và trước lần khởi động đầu, SHA-256 của chỉ mục cùng bốn save đều khớp bản sao lưu của lần đó. Sau mở 823, backend loopback đọc đủ bốn hồ sơ với 195, 295, 1 và 63 tướng. Toàn bộ tướng, trang bị, bảo vật, Kim Cương, Vàng, VIP, lịch sử nhận thành tích, quyền chọn và điểm banner đang mở đều khớp. So sánh bảo vật áp cùng giá trị mặc định `Exp=0` đã có ở baseline. TK3 trả đúng 5 búa trong dữ liệu đăng nhập và vẫn đúng 5 ở lần đọc lại. [Đối chiếu Owner](analysis/qa_r7_12_1/owner-reload.log)

Các lượt nhận thay đổi kho được thử trên save cách ly. Trên Owner, nghiệm thu bằng truy vấn đọc và kiểm dữ liệu sau nâng cấp. STABLE vẫn ở `checkpoint-vn-r6.2` (`5fed4bb`). Giữ nguyên package, khóa ký, đường dẫn save, pool và tỷ lệ chiêu mộ.

## Kiểm thử có thể chạy lại

```sh
python3 server/test_emulator.py -v
PYTHONPATH=/path/to/lupa python3 poc/test_r7121_lua.py \
  analysis/vn/patched/com.cmn.inuyasha.revival_r7_12_standalone.apk \
  analysis/vn/patched/com.cmn.inuyasha.revival_r7_12_1_823_standalone.apk
```
