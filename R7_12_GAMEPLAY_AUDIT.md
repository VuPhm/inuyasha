# R7.12 — Báo cáo kiểm kê gameplay, popup và kinh tế

Ngày rà soát 20/11/2026 (UTC+7). Baseline `checkpoint-vn-r7.11`, APK Android standalone 810. Phạm vi này là kiểm kê và đề xuất. Hai tài liệu R7.12 là thay đổi duy nhất của đợt audit. [Kiểm kê sự kiện chi tiết](R7_12_EVENT_INVENTORY.md)

## Kết quả ảnh hưởng trực tiếp

1. **P0 — Mở Túi Đá 2 có thể mất túi.** Nhận `16020039` từ Giờ Vàng Mua Sắm rồi mở qua `Goods.GoodsUse`. Số túi trong bộ nhớ giảm từ 3 xuống 2 và backend báo lỗi kiểu linh thạch `2000`. Sau một lượt chiêu mộ thành công và tải lại file save tạm, kho chỉ còn 2 túi. [Nguồn cấp VN](analysis/vn/decompiled_src/Config/TimespikeModel.lua#L77) · [tiêu túi và cấp quà](server/emulator.py#L3747) · [kiểm tra model](server/emulator.py#L629)
2. **P1 — Nút X Quà xếp hạng bị kẹt.** Chuỗi callback đóng tự gọi lại trên chính object của popup. Đã đối chiếu Lua giải mã từ APK 810 với bản phân tích và xác nhận nguyên nhân từ mã. Đợt audit giữ nguyên hồ sơ chính, nên chưa bấm lại nút trên Pixel. [TimedEquipRankLayer](analysis/vn/decompiled_src/TimedActivity/TimedEquipRankLayer.lua#L8) · [ModalColorLayer](analysis/vn/decompiled_src/Common/ModalColorLayer.lua#L44)
3. **P1 — Có thao tác tiêu tài nguyên nhưng không cho tác dụng được báo trên UI.** Tăng bậc thời trang trừ vàng và vải, lưu Step, nhưng FAP và FightInfo không tăng. Ưu đãi 4417 báo 224 KC cho lượt Linh Hồn giá gốc 280, trong khi handler từ chối 224 và vẫn trừ đủ 280. Cả hai đã tái hiện trong bộ nhớ. [Fashion.StepUp](server/emulator.py#L6298) · [client RecruitScene](analysis/vn/decompiled_src/Store/RecruitScene.lua#L1175) · [phí backend](server/emulator.py#L2323)
4. **P1 — Đột phá chưa tiêu đủ nguyên liệu.** Với công thức `15001`, InuYasha lên bậc 2, trừ 70.000 vàng và 400 đá, nhưng giữ cả hai bảo vật `14010501` đã gửi đúng theo hợp đồng client. [Công thức](analysis/vn/decompiled_src/Config/HeroStepRelation.lua#L225) · [payload client](analysis/vn/decompiled_src/Hero/HeroUpdateScene.lua#L2171) · [handler](server/emulator.py#L3343)
5. **Ba SR vắng ở 81/82 đã có đường nhận.** Kikyo, Kanade Hime và Kaguya đều nhận được qua 150 mảnh. Cả ba cũng chọn được từ Quà Thần Tướng C do sự kiện 6800 cấp. Hai đường được thực thi qua RPC thật trên hồ sơ thử nghiệm. [Bảng và đường nhận](#chín-tướng-đỏ-sr)

## 1. Baseline và bảo toàn dữ liệu

| Hạng mục | Kết quả đọc-only |
| --- | --- |
| Git | `master` tại `c387cb1`; tag R7.11 tại `dbb2cda5dabecf5669b049adb97080ea56790784`. Bản chênh giữa tag và HEAD trước audit chỉ là báo cáo R7.11. Hai mục untracked có trước audit là `.vscode/` và tài liệu bàn giao R7.9. |
| APK 810 | `com.cmn.inuyasha.revival`, `5.0.4.98-r7.11`, `armeabi`. Chữ ký xác minh thành công. Cả 7 file backend nhúng khớp tag byte-for-byte. SHA-256 của APK Mac và `base.apk` trên Pixel đều là `48c268ac80f4253e66c35f97bb7099cf4c567cfc88f0ecd5ba29a2bd7120e702`. |
| Pixel Owner, S1 | Chỉ mục có đúng 4 mục, slot và định danh tài khoản khớp sao lưu 790. Cả bốn profile JSON đọc được, từng PlayerId khớp. TK1, TK3, TK4 khớp byte với sao lưu 790. TK2 đã có tiến trình hiện tại Lv21, 206 tướng, mốc ải 1716. Sao lưu 790 của TK2 là dữ liệu trước nâng cấp. |
| STABLE | Pointer tiếp tục trỏ `checkpoint-vn-r6.2` (`5fed4bb`). Năm file STABLE và năm file DEV trên Mac khớp manifest trước R7.10. Hai APK 780/790 cũng khớp. Bản sao lưu 790 qua kiểm SHA-256. Audit không chạy RPC chơi hoặc cài APK trên Owner. |

Các tái hiện backend dùng save trong bộ nhớ và đồng hồ cố định khi cần. Bài kiểm tra ghi và tải lại Túi Đá dùng thư mục tạm riêng. Đọc bốn file Android qua ADB và đối chiếu trong bộ nhớ. Suite 61/61 là kết quả nghiệm thu R7.11. Audit này chỉ thực hiện delta. [APK](analysis/vn/patched/com.cmn.inuyasha.revival_r7_11_standalone.apk) · [Nghiệm thu R7.11](R7_11_ACCEPTANCE_REPORT.md)

## 2. Popup Quà xếp hạng

### Chuỗi lỗi đã xác nhận từ APK

`TimedRecruitEquipLayer` mở `TimedEquipRankLayer` khi đã nhận thông tin hạng. Popup truyền một wrapper `onCloseCallback` gọi `self.onCloseCallback(self)` nếu trường này có giá trị. Lớp nền chuyển chính wrapper này thành `returnAction` của nút X, đồng thời lưu chính nó vào `self.onCloseCallback`. Constructor của lớp con chỉ ghi `mParams` và tạo danh sách. Cơ chế `class().new` dùng chung instance native qua các constructor. Bấm X vì vậy đi theo vòng `clickAction → returnAction → self.onCloseCallback → cùng wrapper`, và không đến `removeFromParent`. Lua đóng gói của bốn lớp liên quan khớp bản phân tích. Nút X có ảnh mặc định `c_15.png`, còn tọa độ (500, 430) được đặt cạnh khung scale9 482×428. Giữ vị trí và z-order cho lần sửa callback đầu tiên. [Điểm mở popup](analysis/vn/decompiled_src/TimedActivity/TimedRecruitEquipLayer.lua#L185) · [lớp popup](analysis/vn/decompiled_src/TimedActivity/TimedEquipRankLayer.lua#L8) · [bridge native](analysis/vn/decompiled_src/cocos/cocos2d/extern.lua#L30) · [lớp modal](analysis/vn/decompiled_src/Common/ModalColorLayer.lua#L56) · [nút X](analysis/vn/decompiled_src/Common/CommonBgLayer.lua#L301) · [kích thước](analysis/vn/decompiled_src/Common/Ui.lua#L219)

| Popup dùng chung | Đối chiếu |
| --- | --- |
| `MessageBoxLayer` trong Slot, Cầu Nguyện, quà nhận XSSB | Chuyển `params.returnAction` vào lớp nền. Caller hiện hành để trống trường này, nên chạy nhánh mặc định remove. |
| `TaskRewardPreviewLayer` rương điểm XSSB | Có X, dùng đường mặc định. Nút nhận có callback riêng; nên test cả khi không đủ điểm và khi đã nhận. |
| `ArenaRankLayer`, `ArenaExchangeLayer`, `DailyTasksLayer`, `RewardCenterLayer`, `FirstRechargeLayer`, `EmailListLayer`, `HeroPrDetailsLayer`, `SystemLayer` | Có wrapper cùng mẫu, nhưng constructor con gán lại trường từ callback caller. Đây là nhóm regression của lớp dùng chung, chưa có bằng chứng tái hiện cùng lỗi ở các màn này. |
| Kết quả triệu hồi x1/x10 XSSB | Dùng overlay riêng. Có listener nền tương tự nhưng nhánh đó phụ thuộc `mIsCloseOnTouch`, khác nút X của Quà xếp hạng. Cần smoke nút đóng overlay riêng. |

Nguồn [MessageBoxLayer](analysis/vn/decompiled_src/Common/MessageBoxLayer.lua#L36) · [TaskRewardPreviewLayer](analysis/vn/decompiled_src/Task/TaskRewardPreviewLayer.lua#L8) · [ArenaRankLayer](analysis/vn/decompiled_src/Challenge/ArenaRankLayer.lua#L16) · [RewardCenterLayer](analysis/vn/decompiled_src/Home/RewardCenterLayer.lua#L12) · [hai overlay XSSB](analysis/vn/decompiled_src/TimedActivity/TimedRecruitEquipLayer.lua#L582)

**Sửa nhỏ nhất đề xuất.** Bỏ wrapper `onCloseCallback` riêng ở `TimedEquipRankLayer`, để lớp nền đóng mặc định. Caller duy nhất chỉ truyền `myIntegral`, `myRank` và `rankList`. Áp patch có kiểm tra đoạn Lua đích vào builder standalone, đồng thời giữ nguyên config, server, vị trí X, màu nền và animation. [Caller](analysis/vn/decompiled_src/TimedActivity/TimedRecruitEquipLayer.lua#L185) · [Builder](poc/build_standalone_apk.py#L1045)

**Regression đề xuất.** Test Lua harness với fake CommonBgLayer và nút X, nạp constructor/callback từ Lua đóng gói; trước vá bắt lỗi gọi lặp, sau vá assert chỉ gọi remove một lần và đúng node. Đối chiếu default dismiss và một caller có callback tùy chỉnh ở modal dùng chung. Smoke Pixel trên hồ sơ thử nghiệm theo chuỗi mở tab, mở Quà xếp hạng có hàng và khi không có hạng cá nhân, cuộn, chạm X, mở lại ba lần, rồi mở/đóng rương điểm và overlay kết quả x1/x10. Xác nhận scene Giờ Vàng nhận thao tác sau đóng và log không có lỗi stack. Các test này là phạm vi đề xuất, chưa thêm vào suite.

## 3. Phát triển lực chiến và tác dụng trong chiến đấu

`_compute_slot_property` tạo AP/HP/DEF, FAP và các thuộc tính theo slot. `_build_ally_fight_objs` dùng Property đưa vào FightInfo. Một nhánh có field trong client hoặc xuất hiện trong profile vẫn cần đi qua hai bước này để có tác dụng. Kiểm chứng đối chứng trên tướng ra trận: tăng cấp một lần đưa `HP/AP/DEF/FAP` từ `672/150/32/6415` lên `739/164/35/6567`. [Tính slot](server/emulator.py#L854) · [đội hình trong FightInfo](server/emulator.py#L2872) · [mô phỏng chiến đấu](server/combat_sim.py#L98)

| Hệ thống | Mức | Nguồn, phần đã có và phần còn thiếu |
| --- | --- | --- |
| Tướng, EXP, tăng cấp | Đủ cho lõi | HeroModel 204, HeroLvRelation 600. HeroLvUp trừ Đá Hồn (`HeroEXP`) và vàng, làm thay đổi FightInfo. Cấp nhân vật chính dựa EXP người chơi. |
| Chiêu mộ, sức chứa túi và rương banner | Đủ cho lõi | Chiêu mộ thường, banner 81/82 và rương cấp tướng kiểm sức chứa trước khi trừ phí hoặc mở hộp. Sức chứa nền của save cũ là 200, mỗi lần nới thêm 5 ô. Quyền chọn tướng khi đổi kỳ đã có test 56 và nghiệm thu R7.10. Audit dùng đường chiêu mộ và rương để xác minh nguồn SR. [Nới túi](server/emulator.py#L2210) · [banner](server/event_handlers.py#L680) · [R7.10](R7_10_ACCEPTANCE_REPORT.md) |
| Đột phá tướng | Một phần | HeroStepRelation 57, HeroStepUp và _get_step_attr tăng HP/AP/DEF. Bước cơ bản có regression trước đó. Ở bậc dùng bảo vật, client gửi ID thực thể; backend bỏ qua kiểm tra sở hữu bảo vật và chỉ xóa ID trong kho tướng/trang bị. Đã thử công thức `15001` với đủ bảo vật và xác nhận hai bảo vật vẫn còn. |
| Đội hình và sắp trận | Một phần | Slot.HeroCombat, SlotFormation.Change, gắn đồ và sáu vị trí đi vào FightInfo. MateInfo trả rỗng, thiếu Slot.MateinfoCombat. Cần test dời vị trí, điều kiện trùng entity và slot mở theo cấp ở cả UI và backend. |
| Kỹ năng/thứ tự đánh | Một phần | AttackModel 441, NAID/RAID, RP, chọn đích, tỷ lệ, bạo/né/chặn, heal và AP/DEF được dùng. Python combat hỗ trợ tập con của Lua CSCommon. Payload hiện `BuffList=[]` và nhiều trường CP/DAM/bonus bằng 0. Chưa thấy đường tăng cấp kỹ năng tướng độc lập; cần tách nộ thường khỏi UAID và hiệu ứng chuyển sinh/chiến trận trước khi tuyên bố đủ. |
| Duyên phận | Một phần | HeroPrRelation 123 nhóm, PrModel 572 quan hệ. Client mô tả/kiểm thành viên và đồ; backend APHero/HPHero/DEFHero cùng tỷ lệ bằng 0 và thiếu trợ chiến. Set trang bị được tính độc lập, không đại diện cho duyên. |
| Trang bị | Một phần | 140 mẫu, gắn 4 ô, ghép/nâng Lv, cộng chỉ số cơ bản và bonus set. Equip.EquipRefine là phân giải, EquipRebirth là hoàn tác. Tiến giai/thần khí có EquipStepRelation 112, EquipArtifactRelation 1104 nhưng thiếu đường RPC tương ứng và Property không cộng Step/Extra. Triệu hồi thường 3802 chưa nối; XSSB là nguồn riêng. |
| Bảo vật | Đủ cho lõi | 46 bảo vật/228 mảnh. Tầm Bảo, hợp, gắn Sách/Ngựa, lên Lv/Step, trùng sinh đã có. Property dùng AP/HP theo cấp, Step và một số bonus hoạt hóa. Chỉ số mở rộng vẫn giới hạn theo mapping, cần test riêng với tài nguyên cụ thể. |
| Trùng sinh hoàn phí | Đủ cho lõi | Hero/Equip/Treasure.Rebirth đã reset và hoàn trả tài nguyên theo quan hệ R7.6. |
| Chuyển sinh tăng tiến | Chỉ UI | `RebornInfo` là hệ khác với `*.Rebirth`: RebornLvModel 340, RebornGoodsModel 28, cần Activate/Reborn/Compose và shop. Hợp đồng RPC chưa có; RebornStep trong FightInfo chưa chứng minh tăng lực. |
| Linh thạch | Chỉ UI | GemModel VN có 90 mẫu kiểu 2000; client có GemCompose và Slot.GemCombat/GemOneKeyCombat. Backend chưa trích GemModel, chưa có các handler và từ chối output gem. Vật phẩm gem không đi vào battle. |
| Ngộ Đạo/Điện Tứ Hồn | Đủ cho lõi | Attrtree 1001, Glory 3 nhánh/201 cấp. Có thêm HP/AP/DEF và STA. Ngộ Đạo phân slot bằng logic hiện có, cần so gate/slot gốc nếu mở cấp cao. |
| Thời trang | Một phần | 8 mẫu, mặc/đổi/nâng/phân giải lưu được. `heroAttrStrR` chưa được tiêu thụ khi tính Property/FightInfo. Probe riêng với `19010001`, Step 0→1 trừ 600.000 vàng và 60 `16070004`, bộ 739/164/35/6567 giữ nguyên. |
| Luyện thể, Trận quyết, Chiến trận/Chiến linh | Chỉ UI | Có config/Lua, Luyện thể và Chiến trận tắt theo config VN. Thiếu Lianti/Zhenjue/Warfare/Warfarespirit và các kết nối tăng chỉ số. |
| Yêu Linh, pet và Viễn chinh | Chỉ UI / thiếu tài nguyên | VN có UI/tham chiếu. NewWraithModel thiếu trong bản VN, bản TW có donor; Pet có 111 mẫu, config VN tắt. Thiếu handler và `Pets=[]` trong FightInfo. |

Nguồn [HeroLvUp/StepUp](server/emulator.py#L3287) · [Property](server/emulator.py#L877) · [kỹ năng/buff](server/emulator.py#L1642) · [duyên client](analysis/vn/decompiled_src/Hero/GetHeroAttribute.lua#L70) · [linh thạch client](analysis/vn/decompiled_src/Formation/MyFormationLayer.lua#L1656) · [chuyển sinh client](analysis/vn/decompiled_src/Hero/Rebirth/RebirthLayer.lua#L878) · [thời trang](server/emulator.py#L6298)

## 4. Nguồn nhận, tiêu hao và tài nguyên mắc kẹt

Đối chiếu các bảng được runtime dùng, các handler cấp/trừ, và các cạnh lồng rương trong 245 nhóm `goods_output`. `goods_model` có 1.043 mẫu. Các kết luận không tìm thấy nguồn dưới đây giới hạn ở đường chơi hiện hành đã truy vết; cấu hình chỉ mô tả thưởng, drop trong mode chưa phục hồi, và lệnh quản trị không được tính là nguồn đang chơi được.

| Nhóm | Nguồn hoạt động | Tiêu hao hoặc điểm nghẽn |
| --- | --- | --- |
| KC, vàng | Nạp offline, rương, thành tích, nhiệm vụ; vàng từ ải, Chiêu Tài, shop và quà | Gacha, nới túi, shop, vé bảo hộ/refresh, nâng cấp. 4417 lệch giá. 4401–4407 lấy tổng cũ để mở mốc mới. |
| Đá Hồn `1117`, Mảnh Hồn `1116`, Đá Đột Phá `16050001` | Ải, phân giải, nhiệm vụ, shop/bảng quà | Lần lượt dùng lên cấp, shop Thần Bí, đột phá. `HeroRefine` phân giải tướng rảnh và trả tài nguyên. [Tên theo enum VN](analysis/vn/decompiled_src/Config/Enums.lua#L399) |
| EXP `1101` / EXP VIP `1104` | EXP từ ải và nhiệm vụ. EXP VIP đi theo xác nhận đơn nạp offline | EXP mở cấp/gate; EXP VIP quyết định tầng và quà VIP. Grant tổng quát hỗ trợ EXP; EXP VIP đi qua tuyến nạp riêng. |
| Thể lực / hoạt lực | Hồi theo giờ, Ăn Tối, đan `16030006/08`, shop | Thường/Tinh Anh, Arena/Tầm Bảo theo nhánh. Một số nhiệm vụ cũ tham chiếu hoạt động chưa nối. |
| Điểm Arena `1115` | Đánh và kết quả Arena S1/bot | PVPShop có 40 món; mua trừ điểm thật. |
| Điểm Yêu Vương `1120` | Đánh Yêu Vương và tích điểm | Có LuckbossValueShopModel 35 dòng. Hai RPC ExchangeInfo/Exchange là stub; gọi thử trả `Status=0, Value={}` ở Exchange, thiếu giao dịch tiêu điểm. |
| Vé Rút Thưởng `16050027`, Búa Vàng `16050061` | Vé từ khởi tạo kỳ, nạp đổi theo 60, shop/đổi, quà Năng động; búa từ preset/quà mốc/shop | Slot trừ vé, Trứng trừ búa. `16050055` là Khăn Lau; còn trong nhiều bảng quà mô phỏng. Không tính stack cũ này thành vé quay. |
| Linh thạch kiểu `2000` và túi `16020037–51, 16020055–57` | Có 18 hộp với output gem trong dữ liệu, gồm `16020039` thực cấp ở 6800 | Backend không nhận GemModel và không nối khảm/hợp. Mở 16020039 trừ túi trước khi validate; đã tái hiện chính đường nhận/mở. `16020038` có tên “Tạm chưa dùng” trong VN. |
| Mảnh Sứ Giả Noel `16070004` | Phân giải bản trùng `19010001` ra 200 mảnh theo config và handler; `16060027` có output chọn một mảnh | Trả 60 mảnh và 600.000 vàng để Step 0→1 của 19010001. Step tăng nhưng tổ hợp chiến đấu giữ nguyên. [Phân giải](analysis/vn/decompiled_src/Config/FashionModel.lua#L48) · [rương](analysis/vn/decompiled_src/Config/GoodsOutputRelation.lua#L10381) |
| Tâm Naohi `16050090` | Có trong bảng quà Tầm Bảo, GiftBox và Đấu Võ. Đấu Võ chưa nối | Dùng cho đột phá bậc cao của nhân vật chính. Chưa kiểm định lượng có thể kiếm theo cấp trên APK. [Quà Tầm Bảo](analysis/vn/decompiled_src/Config/ExploreRewardNumsRelation.lua#L11) · [chi phí](analysis/vn/decompiled_src/Config/HeroStepRelation.lua#L362) |
| Linh lực chuyển sinh `1128`, vật liệu `27010101` | RebornGoodsModel có Trúc Xanh → linh lực, shop/đổi tồn tại trong client. Chưa có đường nhận-chuyển này ở runtime chuẩn | RebornInfo/RebornShop chưa triển khai. Không suy ra đủ vật liệu khi bật menu. |
| Điểm/đồ Thần Vực `1127` | Goddomain có quà và shop config, thiếu mode tạo điểm trong standalone | Shop Thần Vực có mảnh SR theo config, chưa thể mua qua R7.11. |
| Rương Tứ Đấu Thần/Inu Kimi `16010023/16010024` | GoodsOutput có tướng, chưa tìm thấy grant live cho hai hộp cố định. Đường banner D `83` còn được khai báo ngoài cấu hình mặc định | Mở theo GoodsUse nếu đã có hợp lệ; chưa coi là nguồn mặc định hoặc tự cấp. |
| Rương phe `16060037–42` | Hộp tướng/mảnh I/S/N tồn tại; `16060037–39` thuộc banner 84–86 chưa bật, `16060040–42` có quan hệ output | GoodsUseForBoxChoice đọc lựa chọn nếu đã sở hữu. Không dùng quan hệ output làm bằng chứng một nguồn cấp. |

**Lỗi chính sách theo kỳ đã tái hiện.** Sau một đơn nạp 300 KC, `TimedInfo.GetChargeDaysInfo` trả 5 ngày. Qua 00:00 UTC+7, ID của 4402 đổi nhưng mốc 60 và 300 vẫn sẵn sàng nhận bởi dữ liệu tổng suốt đời. Rút ngắn kỳ xuống 8/12 giờ không sửa được sự khác nhau giữa tiến trình theo kỳ và tiến trình suốt đời. [Getter nạp/tiêu](server/r79_event_handlers.py#L125) · [tính số ngày](server/r79_event_handlers.py#L1392) · [mốc tích lũy](server/r79_event_handlers.py#L1326)

Nguồn [dispatcher và stub Boss](server/emulator.py#L1814) · [grant resources](server/emulator.py#L1330) · [dữ liệu 1043 mẫu](server/game_data.json) · [LuckbossValueShopModel](analysis/vn/decompiled_src/Config/LuckbossValueShopModel.lua) · [GoddomainShopModel](analysis/vn/decompiled_src/Config/GoddomainShopModel.lua) · [RebornGoodsModel](analysis/vn/decompiled_src/Config/RebornGoodsModel.lua)

## Chín tướng đỏ SR

Phạm vi chín SR thuộc ba phe chơi được trong bản VN được xác định bằng `quality=18`, `specialType=0`, `raceID ∈ {1,2,3}`. HeroModel có 18 hàng quality 18, gồm 7 bản ghi specialType 1 và 2 tướng raceID 0 là Tứ Đấu Thần `12015022`, Inu Kimi `12015023`. Bảng dưới dùng tên VN và ID gốc. [HeroModel](analysis/vn/decompiled_src/Config/HeroModel.lua) · [quy tắc màu và ảnh](analysis/vn/decompiled_src/Common/CommonFunc.lua#L705)

| ID | Tên VN | Mảnh | Nguồn active đã truy vết | Đường cấu hình chưa mở |
| --- | --- | --- | --- | --- |
| 12011002 | Inu no Taishou | 15010001 | Banner 82/Quà B 16060009, gói 6800 cấp 41; rương mảnh B | 84, rương phe I 16060037/40 |
| 12011003 | Kikyo | 15010002 | Quà C 16060032 từ 6800 cấp 44; 16060005 chọn 150 mảnh | 84, phe I, Đấu Võ/Thần Vực bán mảnh trên config |
| 12011004 | InuYasha | 15010003 | Banner 81/Quà A 16060008, gói 6800 cấp 33; rương mảnh A | 84, phe I 16060037/40 |
| 12012003 | Kanade Hime | 15010009 | Quà C 16060032 từ 6800 cấp 44; 16060005 chọn 150 mảnh | 85, phe S, Đấu Võ/Thần Vực; có thêm output ở Quà Nữ Tướng 16020036, chưa xác nhận nguồn cấp hộp |
| 12012004 | Midoriko | 15010010 | Banner 82/Quà B 16060009, gói 6800 cấp 41; rương mảnh B | 85, phe S 16060038/41 |
| 12012005 | Sesshomaru | 15010011 | Banner 81/Quà A 16060008, gói 6800 cấp 33; rương mảnh A | 85, phe S 16060038/41 |
| 12013003 | Takemaru | 15010017 | Banner 82/Quà B 16060009, gói 6800 cấp 41; rương mảnh B | 86, phe N 16060039/42 |
| 12013004 | Kaguya | 15010018 | Quà C 16060032 từ 6800 cấp 44; 16060005 chọn 150 mảnh | 86, phe N, Đấu Võ/Thần Vực bán mảnh trên config |
| 12013005 | Naraku | 15010019 | Banner 81/Quà A 16060008, gói 6800 cấp 33; rương mảnh A | 86, phe N 16060039/42 |

- **Banner.** Gacha HeroRecruit bỏ qua quality ≥18 khi chọn tướng trực tiếp. Banner 81/82 có lần chọn Thần Tướng; cấu hình mốc chứa các hộp mảnh A/B `16060024/25`. Pool banner 83 VN là hai tướng phe 0, hộp D `16060034`. Ba banner 84–86 mới là các hộp phe I/S/N. [HeroRecruit](server/emulator.py#L2252) · [TimedRecruitModel](analysis/vn/decompiled_src/Config/TimedRecruitModel.lua) · [Reward mốc](analysis/vn/decompiled_src/Config/TimedRecruitCreditrewardRelation.lua)
- **Ba tướng ngoài 81/82.** Test ba hồ sơ tạm riêng, nạp offline qua GenerateOrderID/ConfirmOrder, thực hiện 15 lượt Linh Hồn x10 mỗi hồ sơ, nhận đúng 150 hộp `16060005`. Mở hộp theo từng mảnh `15010002`, `15010009`, `15010018`, rồi dùng `Goods.GoodsUse` ghép đúng tướng. Cấu hình Linh Hồn x1 cũng cho một hộp. Quà Thành Tích dùng cùng hộp ở một số mốc; không cần dựa vào các mốc đó để chứng minh đường ghép. [HeroRecruitModel](analysis/vn/decompiled_src/Config/HeroRecruitModel.lua#L35) · [GoodsModel và 150 mảnh](analysis/vn/decompiled_src/Config/GoodsModel.lua#L45) · [output của hộp C](analysis/vn/decompiled_src/Config/GoodsOutputRelation.lua#L6766) · [mốc Thành Tích](analysis/vn/decompiled_src/Config/SuccessTargetRewardRelation.lua#L91)
- **Rương tướng trực tiếp.** Hồ sơ tạm Lv44 nạp offline rồi gọi `Timespike.ReceivedReward` qua các tier tới mốc 8. Tier cấp 44 cấp `16060032`, mỗi bản sao fixture mở qua `GoodsUseForBoxChoice` chọn và nhận đúng một trong ba tướng. Đây là xác nhận nguồn và cấp thưởng qua backend. Toàn vòng UI mốc 44 chưa được smoke. [TimespikeModel](analysis/vn/decompiled_src/Config/TimespikeModel.lua#L77) · [handler gói](server/r79_event_handlers.py#L1126) · [output C](analysis/vn/decompiled_src/Config/GoodsOutputRelation.lua#L14421)
- **Cửa hàng và đường đặc biệt.** Quét shop runtime thường, VIP, Thần Bí và Arena không cho thấy bán trực tiếp chín tướng qua các pool đã nối. GddhShop và GoddomainShop có dòng bán mảnh của cả ba tướng ngoài 81/82 nhưng hai shop chưa có tuyến chơi. `16060035` chứa mảnh cả chín, có trong quà/xếp hạng/đấu giá cũ; đó là đường cấu hình chưa chứng minh active. Kết luận về ba tướng là **thiếu ở banner mặc định, có cách nhận**. [GddhShop](analysis/vn/decompiled_src/Config/GddhShopModel.lua#L89) · [GoddomainShop](analysis/vn/decompiled_src/Config/GoddomainShopModel.lua#L14) · [đấu giá](analysis/vn/decompiled_src/Config/AuctionShop.lua#L175)

## 5. Đối chiếu vùng

| Vùng/tập dữ liệu | Kết quả đối chiếu |
| --- | --- |
| VN 5.0.4.98 | Nguồn chuẩn cho hero, vật phẩm, enum, UI và đóng gói. Trong thư mục phân tích có 276 config Lua, gồm 5 donor đã chèn. APK thực có khung XSSB, icon sy_154 và Spine hai tướng D. |
| EN 5.1.1 | Cùng chín ID và cùng art key cho ba SR đang xét. Ví dụ banner 83 trỏ hộp 16060009 trong EN; hai hero phe 0 không có trong HeroModel EN đã giải mã. Không dùng bảng banner EN cho VN. |
| ZH 5.0.0 | Cùng ID chín SR và mapping hộp banner đối với các hàng 81–86 đã so. Tên ZH hỗ trợ nhận diện; khác bundle tài nguyên/phân phối server. |
| TH 5.1.3.6 | Cùng ID chín SR và mapping hộp 81–86 đã so; có hai hero phe 0. Các nhóm hệ sâu mới hơn cần kiểm riêng từng schema; đồng ID chưa chứng minh cùng điều kiện hoặc cân bằng. |
| TW 1.4 | 15 config phục hồi trong thư mục donor. APK 810 thực chỉ đóng gói 5 bảng VN-adapted XssbModel, CriticalTasksTypeRelation, EarlytaskModel, EarlytaskRewardRelation, TraderConfig. Trong đó module BDD đã đổi ID TW 2506 → VN 2507. NewWraithModel và các bảng khác còn là tham chiếu, chưa đưa vào game. |

Các so sánh trên đọc bản giải mã có sẵn. Khi xét donor mới, kiểm package/version, key schema, tài nguyên thực trong APK, ID hero/đồ/enum và hợp đồng RPC. Xác minh bằng payload nhỏ trên save tạm trước khi nối. Không suy ra tỷ lệ gacha server từ file xem trước hoặc từ locale khác. [Nguồn và phiên bản](SOURCE_INVENTORY.md) · [mapping TW R7.9](R7_9_ACCEPTANCE_REPORT.md) · [builder đóng gói](poc/build_standalone_apk.py#L1049)

## 6. Phạm vi đề xuất R7.12–R7.14

| Round | Ưu tiên và phạm vi | Tiêu chí Test the Delta |
| --- | --- | --- |
| R7.12 | **P0/P1**. Bản vá nhỏ cho nút X Quà xếp hạng. Hạng mục riêng để kiểm và từ chối cấp thưởng không hợp lệ trước khi trừ túi, ưu tiên `16020039`; có thông báo rõ và giữ entitlement nếu gem chưa được hỗ trợ. | Popup red/green theo harness, smoke các modal XSSB nêu trên. Test nhận 16020039 qua 6800, mở thất bại giữ số lượng, reload và mở lại, kiểm một hộp thường/rương chọn hợp lệ. So signer/package và save trước/sau bản cập nhật. |
| R7.13 | **P1/P2**. Chia thay đổi theo nhóm. Khớp nguyên liệu đột phá, mức giảm 4417 và chỉ số thời trang với config VN. Sửa phạm vi tiến trình/claim nạp-tiêu và đồng nhất kỳ XSSB S1. Chốt điều kiện kết toán XSSB/BXH nạp-tiêu. | Đột phá tiêu đúng bảo vật rảnh theo model và từ chối nguyên liệu thiếu/sai trước khi trừ vàng/đá. Giá hiển thị bằng phí thực khi active, phí bình thường ngoài kỳ. Step thời trang tăng đúng chỉ số chiến đấu. Hai TK ở hai kỳ không trộn điểm. Qua mốc 8/12/24 giờ, đối chiếu claim với chính sách đã chốt. |
| R7.14 | **P2/P3**. Ưu tiên một nhánh nội dung đầy đủ có tác động thực. Mộ Thần Binh là ứng viên do có 51 ải VN và nằm trên nhiều nhiệm vụ. Đổi BossCoin và linh thạch/khảm làm từng lát có vòng nhận → tiêu → chỉ số. Bang Hội/Co-op chỉ mở khi đủ luồng local S1 và phần thưởng. Donor hay banner 83–86 cần quyết định riêng. | Khóa đúng cấp, chơi và nhận/thua, cập nhật task, shop/khảm chỉ ra được là thay đổi kho và FightInfo, lưu và reload. Hai TK S1 giữ tài sản riêng. Một smoke offline và nâng cấp đè cho bản phát hành mới. |

Các round giữ package và khóa ký hiện tại, loopback Android, save theo profile S1 và UTC+7. Cập nhật báo cáo và tạo checkpoint sau khi từng round đạt kiểm thử delta và nghiệm thu. Báo cáo này giữ nguyên pool SR, tỷ lệ, giá gốc và mặc định reset. [Roadmap hiện tại](PROJECT_ROADMAP.md)
