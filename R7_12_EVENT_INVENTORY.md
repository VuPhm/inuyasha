# R7.12 — Kiểm kê sự kiện và hoạt động VN

Baseline `checkpoint-vn-r7.11` (`dbb2cda`), APK 810. Phạm vi sửa đề xuất nằm trong [báo cáo chính](R7_12_GAMEPLAY_AUDIT.md).

**Đủ** là có đường chơi và phát thưởng theo luật offline hiện hành. **Một phần** là có handler thật nhưng còn thiếu một đoạn luồng hoặc luật thực thi lệch dữ liệu/giao diện. **Chỉ UI** là có màn hoặc component tái dùng với logic lõi thiếu, stub hoặc chưa kích hoạt. **Chưa** là có khai báo hoặc dấu vết tài nguyên nhưng chưa thấy luồng nghiệp vụ đầy đủ trong bản VN. Hoạt động Đủ vẫn có thể dùng preset mô phỏng.

## Phạm vi quét

- `ModuleSubModel` có 350 mục, 31 thuộc nhóm `44xx` tính cả màn `4400`. Đã rà nhóm này, sáu bản ghi banner `9300`, hai họ lễ hội `6300/6400` và các hoạt động độc lập trong Home, ExtraActivity, OpenActivity, Practice, Challenge. Những ID chỉ làm shortcut, thông báo, mốc hoặc đổi giao diện được gộp với hệ thống chủ. [ModuleSubModel.lua](analysis/vn/decompiled_src/Config/ModuleSubModel.lua) · [HomeScene.lua](analysis/vn/decompiled_src/Home/HomeScene.lua)
- Registry có **41 định nghĩa**, gồm **25 timed**, **14 daily**, **2 permanent**. Profile mặc định phát **19 tab 44xx và 2 banner**. Số định nghĩa và số màn hoạt động hoàn chỉnh là hai phép đếm khác nhau. [event_runtime.py](server/event_runtime.py#L210) · [r79_event_handlers.py](server/r79_event_handlers.py#L48)
- Quét literal RPC đa dòng và bảng `module/method` ngoài Config thu được **108 module, 428 cặp**. Dispatcher có **222 mục, 217 tham chiếu hàm và 5 lambda stub**. Tên động được đối chiếu khi có ở luồng liên quan. Phạm vi quét literal là cận dưới của giao thức client. [emulator.py](server/emulator.py#L1730)

## Giờ Vàng và banner

| ID | Sự kiện | Mức | Chứng cứ hoặc phần thiếu |
| --- | --- | --- | --- |
| 4400 | Giờ Vàng | Đủ | Màn điều phối, hiện khi payload có 44xx, danh sách cuộn theo ID. |
| 4401 | Nạp đơn | Một phần | Có claim. Dùng tổng nạp suốt đời hoặc sàn VIP để tính đơn lớn nhất. |
| 4402 | Nạp tích lũy | Một phần | Có claim và chống trùng cùng kỳ. Tổng suốt đời giữ nguyên khi đổi kỳ; mốc được mở lại từ lần nạp cũ. |
| 4403 | Tiêu tích lũy | Một phần | Có claim. Đọc tổng tiêu suốt đời; một số handler báo phí ròng. |
| 4405 | Ngày nạp liên tục | Một phần | Có claim. Một lần nạp 300 KC trả về 5 ngày đủ điều kiện. |
| 4406 | Đổi thưởng hạn giờ | Đủ | Trừ nguyên liệu, kiểm hạn mức, phát vật phẩm bằng `TimedLimitExchange`, preset mô phỏng, test 53. |
| 4407 | Nạp nhân đôi | Một phần | Mốc thật, có trả KC. Dựa tổng nạp suốt đời. Hiệu ứng tách riêng với bonus lần mua gói đầu. |
| 4409 | Cây Cầu Nguyện | Một phần | Có nhận thưởng. Mốc ngày cùng khả dụng sau ngưỡng nạp theo preset. |
| 4410 | Thần Binh giới hạn | Một phần | GetInfo, CallEquip, ReceiveReward phát trang bị và mốc. Popup xếp hạng bị đệ quy khi đóng. Chưa kết toán thưởng hạng. |
| 4412 | Kho Báu Quay Thưởng | Đủ | Có vé VN 16050027, quay và hệ số, đổi vé qua nạp offline, BXH S1/NPC và thưởng kỳ. Đã quay trên Pixel khi Wi-Fi tắt. |
| 4413 | Phúc lợi Quyết Đấu | Chỉ UI | Có entry `TimedWelfare` bị comment và thiếu payload. Chưa nối hiệu lực. |
| 4414 | Phúc lợi Đấu Võ | Chỉ UI | Cùng wrapper; phụ thuộc Gddh chưa nối. |
| 4415 | Phúc lợi Kim Khố | Chỉ UI | Cùng wrapper; phụ thuộc GGZJ chưa nối. |
| 4416 | Giảm phí triệu hồi trang bị | Một phần | Tab có `RefNum=80`. `Callequip.*` chưa có tuyến trừ phí áp ưu đãi. |
| 4417 | Giảm phí chiêu mộ tướng | Một phần | Tab có `RefNum=80`, client tính giảm. Handler vẫn tính 280 KC cho lượt được hiển thị 224 KC. |
| 4418 | Bạo kích hợp trang bị | Chỉ UI | Wrapper/config có dấu vết; chưa phát tab hoặc nối sản lượng. |
| 4419 | Bạo kích triệu hồi trang bị | Chỉ UI | Wrapper/config có dấu vết; chưa phát tab hoặc nối `Callequip`. |
| 4420 | Bội thưởng Mộ Thần Binh | Chỉ UI | Entry bị comment, phụ thuộc BddInfo. |
| 4421 | BXH nạp KC | Một phần | Có bảng S1/NPC và preview quà, tổng nạp suốt đời, thiếu trả thưởng hạng cuối kỳ. |
| 4422 | BXH tiêu KC | Một phần | Tương tự 4421, dùng số KC tiêu. |
| 4423 | Nạp hoàn KC | Chưa | Có enum RechargeBackDrilling, thiếu instance/payload riêng. |
| 4424 | Vận may giáng xuống | Chưa | Có enum GoodLuckDay, thiếu đường phát thưởng riêng. |
| 4425 | Đổi lễ trong 44xx | Chưa | Có enum FestivalExchange, khác ID 4406 và 6303/6403. |
| 4426 | Đập Trứng Vàng | Đủ | Cấp/trừ Búa Vàng 16050061, trả vật phẩm, bản ghi S1 đúng kỳ và NPC. Pool mô phỏng, test 51 và 59. |
| 4427 | Đăng nhập tích lũy | Một phần | Có claim. Đọc chuỗi `gift_login`, chưa đếm lại theo instance sự kiện. |
| 4428 | Shop điểm nạp | Một phần | Có mua hàng, cấp vé/búa. Điểm dùng tổng nạp và có sàn mô phỏng. |
| 4429 | Quà nạp tự chọn | Một phần | Chọn và nhận thật, điều kiện dùng tổng nạp và có sàn mô phỏng. |
| 4430 | BXH Năng động | Một phần | Bảng S1/NPC và quà điểm. Chưa trả quà hạng; thống kê suốt đời và hòa điểm ưu tiên người đang xem. |
| 4431 | Boss rơi quà đặc biệt | Chưa | Có enum TimedBossDrop, thiếu hook drop theo instance. |
| 4432 | Cây Tiền May Mắn | Đủ | Miễn phí/trả phí, thưởng, nhận mốc, kết toán mốc chưa nhận. UI Pixel và test 58–59. Pool mô phỏng. |
| 4433 | Rơi đồ hạn giờ | Chưa | Có enum TimedHolidayDrop, chưa có tuyến tính drop theo kỳ. |
| 9300/81 | Thần Tướng A | Đủ | Chọn từ 16060008, pity/mốc riêng, kết toán S1. UI mốc 60 đã qua Pixel. |
| 9300/82 | Thần Tướng B | Đủ | Chọn từ 16060009, test 41/47/48/59 và nghiệm thu chuyển tab các round trước. |
| 9300/83 | Thần Tướng D | Một phần | Có config/handler chung, tắt mặc định. VN dùng 16060034 cho Tứ Đấu Thần/Inu Kimi; ảnh sy_154 và Spine hai tướng đều có trong APK. Nhãn “Kikyo” và “thiếu tài nguyên” trong registry chưa phản ánh manifest. |
| 9300/84–86 | Thần Tướng I/S/N | Một phần | Mỗi mẫu cho ba SR cùng phe, `btnPic` trống. Có rương và handler chung, chưa phát mặc định hoặc nghiệm thu từng banner. |

Nguồn [màn 4400](analysis/vn/decompiled_src/TimedActivity/TimedActivityScene.lua#L20) · [WelfareData](analysis/vn/decompiled_src/TimedActivity/WelfareData.lua) · [registry](server/event_runtime.py#L374) · [payload](server/r79_event_handlers.py#L48) · [nghiệm thu R7.10](R7_10_ACCEPTANCE_REPORT.md) · [nghiệm thu R7.11](R7_11_ACCEPTANCE_REPORT.md)

## Họ lễ hội và hoạt động từ Home

| ID | Luồng | Mức | Chứng cứ hoặc phần thiếu |
| --- | --- | --- | --- |
| 6300, 6400 | Lễ Hội và Hoạt Động Chung | Chỉ UI | Hai scene có nguồn. R7.11 không phát nhóm 63xx/64xx, nút gốc bị gate tương ứng. |
| 6301–6306, 6308–6309, 6311, 6313–6314 và 64xx cùng đuôi | Nạp tổng/đơn, đổi, Slot, cây tiền, trứng, đăng nhập, tiêu phí, shop, BXH, quà chọn | Chỉ UI | Có danh mục/component tái dùng. Một số entry, gồm Cây Tiền lễ, nằm trong comment. Thiếu mapping instance và phần thưởng từng module. |
| 6307/6310/6312/6315 và 6407/6410/6412/6415 | Tài Thần, Boss lễ, nạp tích lũy mới, drop theo kỳ | Chưa | Ba mục đầu mỗi họ có đánh dấu placeholder ở config. Drop chưa có đường rơi theo instance. |
| 2600 | Nhiệm vụ Mở Server | Một phần | EarlytaskFinishRecord có claim qua donor TW đã ánh xạ. Permanent; một số chỉ tiêu dựa tính năng phụ chưa nối. |
| 2700, 2707 | HĐ Đặc Sắc, shortcut Chiêu Mộ | Đủ | Menu/đường dẫn, phụ thuộc điều kiện ở hoạt động thành phần. |
| 2702, 3301 | Quà/hoàn nạp | Chỉ UI | GiftBackLayer yêu cầu `TimedInfo.GetTimeLimitInfo` và RPC claim riêng. 3301 có khai báo. |
| 2703 | Quỹ Trưởng Thành | Đủ | LvPlan mở quỹ, tiêu KC và claim, test 37. |
| 2704, 3500 | Quà và shop VIP | Đủ | VipWelfare và ShopGift, test 33–35. |
| 2705, 2717 | Chia sẻ ngày / Facebook | Một phần | `ShareInvite.GetShareReward` trả quà nội bộ; chia sẻ/mời bên ngoài chưa nối. |
| 2706 | Ăn Tối/nhận thể lực | Đủ | PlayerVIT dùng khung VitConfig, nhận một lần mỗi khung. |
| 2708, 2713–2715, 8700–8701, 8800–8802 | Mời bạn, WeChat/Weibo, theo dõi, Lì Xì WeChat | Chỉ UI | Có UI/SDK hoặc enum, thiếu luồng invite/WeChat. 2714–15 tắt; một số nút Home cũ bị comment. |
| 2710 | Quỹ Mỗi Ngày | Đủ | Daydayfund đầu tư và nhận, test 22. |
| 2711 | Chiêu Tài | Đủ | Zcsf có lượt ngày, trả vàng, test 45. |
| 2712 | Điểm Danh Tháng | Đủ | Có guard ngày và tháng, thưởng mô phỏng, test 54. |
| 2716 | Giftcode | Đủ | Mã local và khóa claim theo mã, test 54. |
| 2718 | Quà Khởi Nghiệp | Đủ | Có config, nhận thật, test 22. |
| 2800, 3100, 3600, 3700 | Quà cấp, nạp lần đầu, chuỗi đăng nhập, quà online | Đủ | GiftLv, PlayerCharge.DrawBox, GiftLogin, OnlineReward có grant thực. |
| 2400 | Trung Tâm Thưởng | Đủ | Reward.Rewars/DrawGiftBags trả quà từ nguồn đã nối. |
| 3000 | Nhiệm Vụ Ngày | Một phần | Điểm, claim, one-key và reset chạy; một số task gắn BDD, tổ đội hoặc mode chưa khôi phục. |
| 4300 | Thương Nhân Hạn Giờ | Đủ | TraderInfo xem/làm mới/mua, donor TW đã ánh xạ VN, test 54. |
| 4600–4602 | Kho Bí Ẩn/Huyết Chiến | Đủ | Xxbz có đánh, điểm/lượt ngày, thưởng thiệt hại, lưu highest. 4601 xóa CD tắt trong config VN. |
| 4700 | Nhiệm vụ Hạn Giờ | Một phần | Có quà và hợp đồng TW/VN. BDD không có nguồn tăng tiến độ, nạp/tiêu dùng tổng suốt đời. |
| 4900–4935 | Quà Thành Tích 7 ngày | Một phần | Có nhận mốc, nhưng một số chỉ tiêu như BDD/tiến giai trang bị chưa có đường hoàn thành. |
| 5500, 6705 | Lì xì gửi/nhận, BXH lì xì | Chỉ UI | RedBag và BXH chung chưa nối. |
| 5501 | Lì Xì ngẫu nhiên | Đủ | RandomRedBag hiển thị và cấp theo preset cục bộ, test 54. |
| 5900, 9400 | Giao diện Tết/Giáng Sinh | Chưa | Công tắc giao diện, không có instance phát thưởng riêng. |
| 6600–6602 | Thẻ Tháng | Một phần | CardInfo chạy với model trích được. VN data có 1 CardModel, các ID con chưa chứng minh có gói độc lập. |
| 6800 | Giờ Vàng Mua Sắm | Một phần | Có 8 gói, nguồn rương SR. Fallback bỏ qua cấp khi hết mốc phù hợp, ReceiveMoney có sàn và Túi Đá 2 mốc 44 lỗi khi mở. |
| 6900 | Săn Thưởng | Đủ | Mốc theo cấp, trả quà thật, test 46. |
| 7000–7002 | Trùm Mua Sắm | Một phần | TimesMiaosha có gói và nhận theo preset. 7001–02 điều khiển hiển thị/chấm đỏ. |
| 7100 | Phiếu thay tiền/ưu đãi | Chỉ UI | Home có mục/notice, chưa có đường tiêu phiếu trong checkout local. |
| 7700–7703 | Người cũ quay lại | Chỉ UI | OlderUserActivity và OldPlayer/OldPlayerNewServer, config VN tắt, thiếu handler. |
| 7800 | Đoạt Bảo | Một phần | Tham gia và nhận thật một lần/ngày. Số tham gia 10088, quà cố định và sàn nạp, thiếu vòng quay S1 chung. |
| 7900–7908 | Đua Top SV Mới / ngôi sao | Một phần | Có bảng S1/NPC và claim mốc. Đang chạy ngày, không phải mùa 7 ngày; có chỉ tiêu BDD/Pet chưa chơi được. |
| 8200 | 10 Vạn KC | Đủ | Swdiamonds có mốc nạp và claim theo VN, permanent, test 54. |
| 8400, 8500–8502, 8900 | Đổi phi hành khí, Sát Điện Bảo Tàng, thư VIP | Chưa | Enum/config/UI liên quan. Chưa có vòng nghiệp vụ sống, 8501–02 là trạng thái hiển thị. |

Nguồn [ExtraActivity](analysis/vn/decompiled_src/ExtraActivity) · [OpenActivity](analysis/vn/decompiled_src/OpenActivity) · [Home](analysis/vn/decompiled_src/Home/HomeScene.lua#L2454) · [lễ 6300](analysis/vn/decompiled_src/TimedActivity/FestivalActivityScene.lua#L17) · [lễ 6400](analysis/vn/decompiled_src/TimedActivity/CommonHolidayScene.lua#L17) · [handler](server/r79_event_handlers.py) · [test](server/test_emulator.py)

## Hoạt động combat và cộng đồng

| ID / nhóm | Mức | Chứng cứ hoặc phần thiếu |
| --- | --- | --- |
| 2200–2203 Thường/Tinh Anh | Một phần | Chơi, drop, rương hoạt động; địch theo wave tổng hợp, chưa có đội hình gốc từng ải. |
| 7200–7201 Ác Mộng | Chỉ UI | Có 65 chương/639 ải trong data. Nightmare.* 0/6 literal. |
| 2301–2304, 5200–5201 Tu Hành | Đủ | Điện Tứ Hồn, Ngộ Đạo, Ước, Tầm Ngọc chạy; Xhzw có luật mô phỏng. Shortcut có gate riêng. |
| 2501/2505/2506 Tầm Bảo | Đủ | Loot, mảnh và ghép, bảo hộ, một số shortcut dùng chung handler. |
| 2502 Arena | Đủ | Đánh đội phòng thủ S1 và bot, điểm, hạng và shop. |
| Yêu Vương/BossBattle | Một phần | Đánh, quà cá nhân, lượt. Shop điểm ExchangeInfo/Exchange stub; thiếu boss chung S1. |
| 2503 Đấu Võ, 2504/2509/2510 Kim Khố | Chỉ UI | Gddh/GddhShop và GGZJ chưa có handler sống. |
| 2507–2508 Mộ Thần Binh | Chỉ UI | Có 51 ải VN, BddInfo 0/12 literal gồm đánh, quét, buff, shop, rank. |
| 2319–2322, 4500, 6000–6003 Phó Bản Tổ Đội | Chỉ UI | Có 24 ải, NPC và shop. GetInviteInfo stub, thiếu lập đội, đánh, trấn giữ, thưởng. |
| 3400–3412 Bang Hội, Boss Bang, phụ bản, đấu giá | Chỉ UI | Guild, GuildBossInfo, GuildReward, Auction chưa nối; một số mục VN tắt. |
| Lĩnh Địa | Chỉ UI | CrusadeInfo 0/8 literal, còn UI Territory. |
| 6100, 6200–6202 Liên Server và Quán Quân | Chỉ UI | PVPinter, PVPinterTop, shop/worship chưa có handler. |
| 6701–6704 BXH chung | Chỉ UI | Thiếu LeaderBoard.RankList/Praise. Các bảng sự kiện hoạt động riêng. |
| 7400–7600 Thú cưng/viễn chinh | Chỉ UI | VN tắt; 111 pet, 48 ải PetOut; Pet, PetOut và Slot.PetCombat chưa nối. |
| 8300–8306 Thần Vực | Chỉ UI | Có shop và quà 44 dòng config, thiếu đội/đấu/quà cục bộ. |
| 9500–9507, 9700–9801 chiến liên server/săn tổ đội | Chưa | ID tắt, một phần tài nguyên/donor, thiếu handler có thể chơi. |
| Thư, bạn bè, thông báo, chat | Chỉ UI | PlayerEmail/Friend/FriendMessage thiếu handler, Notice stub, TCP chat đã ngắt trong standalone. |

Nguồn [dispatcher](server/emulator.py#L1758) · [BddInfo client](analysis/vn/decompiled_src/NewXZYY/XzyyMainScene.lua#L751) · [Arena S1](R7_7_R7_8_STANDALONE_BETA_REPORT.md) · [catalog cũ](EVENT_RECOVERY_CATALOG.md)

## Lịch, hiển thị và số lượng đồng thời

| Chế độ | Kết quả |
| --- | --- |
| Concurrent mặc định | 21 instance timed được chọn. Không có giới hạn số tab toàn cục riêng. Registry và allowlist payload giới hạn những gì hiện thực tế. Scene cuộn 19 tab 44xx, 2 banner độc lập. |
| Mốc UTC+7 | 00:00 mặc định. `fixed_sec` đổi các timed trong concurrent, `period_overrides` đổi riêng. Đã thử chu kỳ 28.800 giây ra 00:00/08:00/16:00, 43.200 giây ra 00:00/12:00. APK vẫn mặc định ngày. |
| Daily/permanent | 14 định nghĩa daily; Dinner khung 12–14, 18–20, 21–23; tháng điểm danh có guard riêng. Earlytask và 10 Vạn KC permanent. Engine có nhánh weekly, registry hiện chưa dùng. |
| Scheduled | Cửa sổ đầu/cuối riêng từng event, có thể chồng. Cần guard nếu cấu hình dùng cùng ID instance cho hai event. |
| Rotating | Một timed event hoạt động mỗi lượt. Mặc định pool 81/82, bước 259.200 giây và anchor. Daily/permanent vẫn chạy. |
| Manual | Một timed event active, reset cần xác nhận. Daily tạo ID mới. Thử reset permanent trả cùng ID đã bị đánh dấu archived. |
| Visibility | Config client, ModuleInfo.IfOpen, level/VIP, TimedActivityOpenInfo đều liên quan. Hàm `moduleIsOpenInServer` trả true nếu thiếu mục, nên chỉ bỏ ID khỏi payload không đủ bảo đảm ẩn. Registry timed có Lv1/VIP0; Thần Binh 4410 bấm quay còn qua gate Lv25 của EquipRecruit 3802 ở client. |
| Màn mở qua ranh giới kỳ | `TimedActivityScene:onTimer` chỉ gọi bộ đếm của tab hiện tại. Danh sách tab dựng lúc mở từ `TimedActivityOpenInfo` client đang giữ. Chưa chứng minh UI tự đổi danh sách hoặc banner khi người chơi đứng nguyên màn qua mốc reset. [Timer và dựng danh sách](analysis/vn/decompiled_src/TimedActivity/TimedActivityScene.lua#L458) · [cache](analysis/vn/decompiled_src/Data/NetworkResData.lua#L4968) |
| S1 và kết toán | Lịch và progress theo profile. Slot/banner đối chiếu cùng ID kỳ. XSSB đọc kỳ đang mở của từng peer, có thể trộn kỳ sau manual reset lệch nhau. Rank/mốc chỉ kết toán ở nguồn đã nối. History snapshot giữ 200 mục; bảng instance gốc chưa có pruning. |

Nguồn [EventClock](server/event_runtime.py#L163) · [cấu hình](server/event_runtime.py#L506) · [resolver](server/event_runtime.py#L625) · [manual reset](server/event_runtime.py#L911) · [gate client](analysis/vn/decompiled_src/Data/NetworkResData.lua#L4324) · [render danh sách](analysis/vn/decompiled_src/TimedActivity/TimedActivityScene.lua#L493)
