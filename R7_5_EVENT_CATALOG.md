# Danh Mục Khảo Sát Hệ Thống Hoạt Động & Sự Kiện Gốc — InuYasha: Seek Jade (VN `5.0.4.98`)

Tài liệu này mở rộng và cụ thể hóa `EVENT_RECOVERY_CATALOG.md` cho **R7.5**, đối chiếu trực tiếp từ mã nguồn Lua (`analysis/vn/decompiled_src/`), 271 bảng `Config/` VN, tài nguyên ảnh/Spine trong APK/OBB và trạng thái máy chủ giả lập hiện tại.

> **Nguyên tắc phân biệt nguồn dữ liệu:**
> - **Gốc xác minh (Verified Original):** Toàn bộ điều kiện mở, bảng thưởng, chi phí, tài nguyên UI/Spine đều có mặt trực tiếp trong VN `5.0.4.98` Config/APK/OBB.
> - **Mô phỏng có kiểm soát (Server-Modeled):** Giao diện/ID gốc tồn tại nhưng công thức xác suất ẩn, BXH người chơi khác, hoặc pool đối thủ PvP vốn chạy phía server gốc cần tái tạo có ghi nhận rõ ràng.
> - **Thiếu dữ liệu gốc (Missing Server Data / Asset-Blocked):** Client Lua gọi RPC lấy toàn bộ bảng thưởng/cấu hình động từ server hoặc thiếu texture `xshd_*` trong APK/OBB; **không** tự bịa cấu hình rồi gọi là bản gốc.

---

## I. Phân Nhóm & Trạng Thái Khả Thi Tổng Quan

| Nhóm | Mức độ sẵn sàng dữ liệu | Sự kiện tiêu biểu |
| :--- | :--- | :--- |
| **1. Đủ Config + UI + Asset** | **100% Khả thi** | `DailyTaskInfo (3000)`, `Dinner (2706)`, `Xxbz (4600)`, `TimedRecruit (9300 - Banner 81 & 82)`, `Zcsf (2711)`, `Xhzw (2303)`, `BddInfo (2507)`, `StartWork (2718)`, `Daydayfund (2710)`, `GiftLogin / GiftLv / SuccessTarget (4900)` |
| **2. Có Config nhưng cần BXH / Co-op / Mở rộng UI** | **Khả thi có mô phỏng đối thủ** | `OpenContest (7900)`, `Limitthebounty (6900)`, `TimeSpike (6800)`, `Swdiamonds (8200)`, `GGZJ (2504)`, `Teambattle (2319)`, `GuildBoss (3400)` |
| **3. Chỉ có Lua UI — Thiếu bảng Config/tỷ lệ server** | **Thiếu Config gốc / Partial Asset** | `MonthSignInfo (2712)`, `OnlineReward (3700)`, `Earlytask (OpenActivity)`, `TimedCriticalInfo`, `TimedMoneyTree`, `TimedSmashingeggsInfo`, `TimedHopetreeInfo`, `TimedInfo.*` (`ChargeTotal/Single/UseTotal/Exchange`), `TimedXssbInfo (XssbModel thiếu)`, `TimedRecruit 83..86`, `WrestleRace/Gddh (2503)`, `Crusade` |

---

## II. Hồ Sơ Chi Tiết Từng Sự Kiện / Hoạt Động (12 Tiêu Chí Bắt Buộc)

### Nhóm A — Hoạt Động Đã Khôi Phục Chơi Thật Trong R7.5

#### 1. Nhiệm Vụ Ngày (`DailyTaskInfo`) — `ModuleSub = 3000`
1. **ID & tên gốc:** `3000` — `DaliyTask` / VN UI: **NV Ngày** (`Task/DailyTasksLayer.lua`, `Task/TaskRewardPreviewLayer.lua`).
2. **Loại sự kiện:** Hoạt động hằng ngày (`schedule_type = daily`).
3. **Điều kiện xuất hiện:** `ifOpen = 1`, `openLv = 25` (`ModuleSubModel[3000]`). Tự động hiện nút trên HomeScene khi `Lv >= 25`.
4. **Điều kiện tham gia:** `Lv >= 25` (mỗi nhiệm vụ con chỉ hiển thị khi đạt `openLv` của `moduleID` tương ứng + tối đa 2 nhiệm vụ sắp mở tiếp theo).
5. **Thời gian bắt đầu / kết thúc:** `00:00:00` – `23:59:59` hằng ngày (múi giờ `UTC+7` VN).
6. **Cách chơi / nhiệm vụ:** 25 đầu việc trong `DailytaskModel.lua` (`ID 1..34`: Ải Thường 30 lần, Ải Tinh Anh 3 lần, Đoạt Bảo 5 lần, Ngộ Đạo 1 lần, Quyết Đấu 5 lần, Yêu Vương 4 lần, Cường Hóa TB 1 lần, Tăng Lv Tướng 1 lần, Dùng 300 KC, Kho Báu Bí Ẩn 1 lần, v.v.). Có nút `Hoàn Thành` từng việc (`10` KC) và `Hoàn Thành Hết` (`200` KC theo `DailytaskConfig.oneKeyAllDaliyTask`).
7. **Giới hạn lượt tham gia:** 1 lần hoàn thành + nhận điểm cho mỗi đầu việc / ngày; 5 rương mốc điểm / ngày.
8. **Phần thưởng:**
   - Nhận điểm từng nhiệm vụ (`GetCredit`): `outputCredit` (`5..20`) + Vàng `goldFactor * player.Lv` (xác minh `DailytaskModel.lua`).
   - 5 rương mốc (`30, 80, 130, 170, 220` điểm theo `DailytaskRewardModel.lua`): KC (`5..80`), Lệnh Miễn Chiến (`16050011`), Hồn Ngọc (`1117`), Thể/Hoạt Lực (`16040003`/`16050016`/`16050013`), EXP người chơi `DailytaskExpRelation[Lv].baseEXP * playerEXPFactor`, Quỹ/Cống hiến công hội (`DailyTasksLayer.lua:661-683`).
9. **Cơ chế làm mới:** Tự reset `00:00 UTC+7` mỗi ngày; `EventRuntime` tạo `instance_id = daily_task:YYYY-MM-DD` mới và lưu bản ghi cũ vào `archive_history`.
10. **Các RPC cần thiết:** `DailyTaskInfo.GetDaliyTaskInfo` *(lưu ý lỗi chính tả gốc `Daliy` từ client)*, `DailyTaskInfo.GetCredit`, `DailyTaskInfo.DrawReward`, `DailyTaskInfo.OneKeyDone`, `DailyTaskInfo.OneKeyAllDone`.
11. **Tài nguyên có / thiếu:** Có đủ 100% (`DailytaskConfig`, `DailytaskModel`, `DailytaskRewardModel`, `DailytaskExpRelation`, icon UI & RedDot `"3000"`).
12. **Trạng thái thực tế:** **Đã khôi phục hoàn chỉnh (Verified Original)** + gắn hook tự động vào Ải Thường, Tinh Anh, Đoạt Bảo, Ngộ Đạo, Quyết Đấu, Yêu Vương, Tầm Ngọc, Shop, Shop Bí Ẩn, Cường Hóa TB, Tăng Lv Tướng, Tiêu KC và Kho Báu Bí Ẩn.

#### 2. Tiệc Thể Lực / Hoạt Lực Hằng Ngày (`PlayerVIT.ReceiveVIT`) — `ModuleSub = 2706`
1. **ID & tên gốc:** `2706` — `ExtraActivityDinner` / VN UI: **Tiệc Thể Lực** (`ExtraActivity/DinnerLayer.lua`).
2. **Loại sự kiện:** Hoạt động hằng ngày theo 3 khung giờ cố định (`schedule_type = daily` + `time_windows`).
3. **Điều kiện xuất hiện:** `ifOpen = 1`, `openLv = 1` trong `ModuleSubModel[2706]`, tab thuộc `ExtraActivityScene`.
4. **Điều kiện tham gia:** `Lv >= 1` và đang nằm trong 1 trong 3 khung giờ của ngày theo `UTC+7`.
5. **Thời gian bắt đầu / kết thúc:** Từ `VitConfig.lua`:
   - Khung 1: `0.50` – `0.583333` (`12:00 – 14:00`)
   - Khung 2: `0.75` – `0.833333` (`18:00 – 20:00`)
   - Khung 3: `0.875` – `0.958333` (`21:00 – 23:00`; nhãn UI VN hiển thị `21h-22h`)
6. **Cách chơi / nhiệm vụ:** Bấm vào tô mì bốc khói trong giỏ bento để nhận thưởng khi `RedDotInfo["2706"] ~= 0`.
7. **Giới hạn lượt tham gia:** 1 lần / mỗi khung giờ / ngày (`win:0`, `win:1`, `win:2`).
8. **Phần thưởng:** `VitConfig.dinnerSubstance = "1102,0,50||1103,0,20"` (**50 Thể Lực + 20 Hoạt Lực**).
9. **Cơ chế làm mới:** Làm mới theo ngày `daily_dinner:YYYY-MM-DD`; tự khóa ngoài khung giờ.
10. **Các RPC cần thiết:** `PlayerVIT.ReceiveVIT`, đồng bộ `RedDotInfo["2706"]`.
11. **Tài nguyên có / thiếu:** Có đủ 100% (`VitConfig.lua`, `DinnerLayer.lua`, `jchd_19.png`/`jchd_20.png`).
12. **Trạng thái thực tế:** **Đã khôi phục hoàn chỉnh (Verified Original)** điều khiển bởi `EventClock` + `EventRuntime`.

#### 3. Chiêu Mộ Thần Tướng Giới Hạn (`TimedRecruitInfo`) — `ModuleSub = 9300`
1. **ID & tên gốc:** `9300` — `TimedRecruit` / VN UI: **KM Tướng** (`TimedActivity/LimittedTimedRecruitLayer.lua`, `TimedRecruitChoiceBoxLayer.lua`). Banner `81` (Sesshomaru / InuYasha / Naraku) & `82` (Inu no Taishou / Midoriko / Takemaru).
2. **Loại sự kiện:** Sự kiện giới hạn thời gian (`schedule_type = timed`), xoay vòng / chọn thủ công qua **Event Archive**.
3. **Điều kiện xuất hiện:** `ifOpen = 1`, `openLv = 1`, yêu cầu `Avatar.TimedActivityOpenInfo["9300"]` có bản ghi chứa `ActivityId`, `EndDate`, `ExtraInfo = {ActivityEnumId}`.
4. **Điều kiện tham gia:** `Lv >= 1` và banner đang trạng thái `active` trên `EventRuntime`.
5. **Thời gian bắt đầu / kết thúc:** Quản lý bởi `EventArchive` (`rotating` mặc định 3 ngày = `259200s` mỗi kỳ, `scheduled`, hoặc `manual`).
6. **Cách chơi / nhiệm vụ:** Chiêu mộ miễn phí (hồi chiêu `freeRecruitCD = 72000s` = 20h), x1 bằng `280` KC, x10 bằng `2800` KC; tích lũy `+10` điểm/lần rút; bảo hiểm Tướng Cam (`q=15`) mỗi `10` lượt (`outputHighHeroIntervalNum = 9`); mở rương điểm tuần tự `60..600`; mở khóa Chúc Phúc (`firstBless = 320`, `+5`/lượt) khi xong rương `600`; khi kích hoạt UR sẽ mở `TimedRecruitChoiceBoxLayer` cho chọn 1 Thần Tướng `q=18` từ rương (`16060008` cho banner `81`, `16060009` cho banner `82`).
7. **Giới hạn lượt tham gia:** Miễn phí 1 lần mỗi `72000s`; x1/x10 KC không giới hạn theo số dư; 6 rương điểm mỗi kỳ; BXH cần tối thiểu `limitNum = 500` điểm.
8. **Phần thưởng:**
   - Tướng rút trực tiếp & Tướng UR tự chọn (`16060008` / `16060009`).
   - 6 rương mốc điểm (`TimedRecruitCreditrewardRelation.lua`: `60, 200, 300, 400, 500, 600`) tặng mảnh Thần Tướng `16060024`/`16060025`, Hộp Đá Hồn 3, Đá Đột Phá, Vàng.
   - Thưởng BXH khi kết thúc kỳ (`TimedRecruitRankrewardModel.lua`: Top 1, 2–3, 4–20, 21–50) phát qua **Trung Tâm Nhận Thưởng** (`RewardCenter 2400`).
9. **Cơ chế làm mới:** Mỗi kỳ hoặc mỗi lần mở lại qua `EventArchive` sinh `instance_id` riêng (`rot:k` / `manual:seq:ts`), tự động tất toán BXH kỳ cũ một lần duy nhất vào `RewardCenter` và giữ toàn bộ lịch sử trong `archive_history`.
10. **Các RPC cần thiết:** `TimedRecruitInfo.GetTimedRecruitInfo`, `TimedRecruitInfo.Recruit`, `TimedRecruitInfo.DrawCreditReward`, `TimedRecruitInfo.DrawGoldHero`, cùng `Reward.Rewars` & `Reward.DrawGiftBags` để nhận quà xếp hạng.
11. **Tài nguyên có / thiếu:**
    - **Banner `81` & `82`: Đủ 100% Config + UI + `sy_147`/`sy_148` + `xshd_59/60` + `xshd_98..103` + `GoodsOutputRelation 16060008/16060009`.**
    - **Banner `83`:** Thiếu ảnh nền `xshd_114`/`xshd_115`. **Banner `84..86`:** `btnPic=""`, `pic=""` rỗng trong `TimedRecruitModel.lua`.
    - **Phần mô phỏng ghi nhận:** Phân bố tỷ lệ chi tiết giữa Tướng Tím (`q=13`) vs Cam (`q=15`) trong 10% còn lại ngoài `outputLowHeroR=9000`, công thức nổ UR trung gian của server gốc, và danh sách đối thủ BXH tổng hợp (`25` NPC tất định theo `instance_id`).
12. **Trạng thái thực tế:** **Đã khôi phục hoàn chỉnh cho Banner `81` & `82`** (`Verified Original + Controlled Rank/Odds Modeling`); Banner `83..86` được đánh dấu không mở do thiếu asset trong APK/OBB.

#### 4. Kho Báu Bí Ẩn (`Xxbz` / `XxbzInfo`) — `ModuleSub = 4600`
1. **ID & tên gốc:** `4600` — `XXBZ` / VN UI: **Kho Báu Thần Bí** (`Practice/TimedTreasure.lua`, `BattleSettleLayer.lua`, `ComBattle/BattleUILayer.lua`).
2. **Loại sự kiện:** Hoạt động khiêu chiến Boss Sát Thương hằng ngày (`schedule_type = daily` cho lượt đánh + tiến độ tích lũy suốt đời cho rương mốc sát thương).
3. **Điều kiện xuất hiện:** `ifOpen = 1`, `openLv = 28` trong `Tu Luyện` (`PracticeListLayer`).
4. **Điều kiện tham gia:** Boss `1` (KB Vàng - `12010012`) & Boss `2` (KB Đột Phá - `12010011`) mở tại `Lv 28`; Boss `3` (KB Magatama - `12010014`) mở tại `Lv 30` (`XxbzModel.lua`).
5. **Thời gian bắt đầu / kết thúc:** Mở cả ngày (`0..0.999988`), reset lượt mỗi ngày lúc `00:00 UTC+7`.
6. **Cách chơi / nhiệm vụ:** Chọn Boss -> vào chiến đấu Spine 2D thực tế (`BattleType.eXSBZ`, bản đồ `rongyan`) tối đa 30 lượt -> sát thương gây lên Boss được tính liên tục qua HUD (`BattleUILayer:getCoinReward()`) và quyết toán vào máy chủ (`Xxbz.Fight`). Đạt mốc sát thương cao nhất (`30k..12M`) được mở rương thưởng 1 lần (`Xxbz.DrawReward`).
7. **Giới hạn lượt tham gia:** `freeFightNums = 1` lượt miễn phí/ngày cho mỗi Boss (`XxbzConfig.lua`), `needVIT = 0`, `fightCD = 0`. Mua thêm lượt (`XxbzInfo.BuyCount`) giới hạn theo `VipModel[vip].buyXSBZNum` (`VIP 0..5 = 0`, `VIP 6..20 = 1 lượt/ngày`) với giá `20`/`50` KC (`XxbzDelCdRelation.lua`).
8. **Phần thưởng:**
   - Thưởng chiến đấu tức thời theo đúng công thức VN (`baseReward + ceil(hurt * rewardNumR / 1_000_000 + baseNum)`): Vàng (`1112`), Đá Đột Phá (`16050001`), Hồn Tướng (`1116`), cộng thêm `extraOutput = "1605,16050092,2"` (**2 Lệnh Trợ Chiến**).
   - Mốc thưởng sát thương một lần (`XxbzRewardBaseRelation.lua`, 9 mốc/Boss từ `30,000` đến `12,000,000`): **`100` Kim Cương** mỗi mốc.
9. **Cơ chế làm mới:** `RemainCount`, `RemainNum` và `BuyCount` reset `00:00 UTC+7` hằng ngày (`xxbz:YYYY-MM-DD`); `HighestHurt` và `DrawnMaxNum` giữ trọn đời (`xxbz_lifetime`).
10. **Các RPC cần thiết:** `Xxbz.GetInfo`, `Xxbz.GetFightInfo` *(trả `FightInfo` kèm `TreasureId` gốc cho HUD)*, `Xxbz.Fight`, `Xxbz.DrawReward`, `XxbzInfo.BuyCount`.
11. **Tài nguyên có / thiếu:** Có đủ 100% (`XxbzConfig`, `XxbzModel`, `XxbzRewardBaseRelation`, `XxbzRewardConditionRelation`, `XxbzDelCdRelation`, 3 Boss Spine `12010012`/`12010011`/`12010014` có đầy đủ animation/ảnh).
12. **Trạng thái thực tế:** **Đã khôi phục hoàn chỉnh (Verified Original)** + gắn hook tự động vào `DailyTask #30` và `SuccessTarget #26/#33`.

---

### Nhóm B — Sự Kiện Đã Hoạt Động Từ Các Round Trước (Không Tính Vào 3 Sự Kiện Mới R7.5)

- `GiftLogin (Đua Top / Đăng nhập 7 ngày)`, `GiftLv (Quà Cấp Độ)`, `Daydayfund (2710 Quỹ Mỗi Ngày)`, `StartworkReward (2718 Lì Xì Đầu Năm Mon–Thu)`, `VipWelfare (Phúc Lợi VIP)`, `LvPlan (Quỹ Đầu Tư)`, `CardInfo (Thẻ Tháng)`, `ShopGift (Gói VIP 0..20)`, `SuccessTargetInfo (4900 Quà Thành Tích 7 Ngày)`, `BossBattle (2203 Yêu Vương)`, `PVP (2502 Quyết Đấu)`. *(Lưu ý: `StartworkReward` và `RedDot 2718/2710/2203` trong R7.5 cũng đã được chuyển sang dùng `EventClock` thay vì `time.time()` thô).*

---

### Nhóm C — Các Hoạt Động & Sự Kiện Còn Lại (Đã Khảo Sát Đủ 12 Thuộc Tính Để Lên Lộ Trình R7.6+)

| ID / Tên gốc | Loại & Mở khóa (`ModuleSub`) | Lịch / Làm mới | Cách chơi & Thưởng (Verified vs Missing) | RPC cần thiết | Tài nguyên & Trạng thái hiện tại |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`2711` `Zcsf` (Thần Tài / Chiêu Tài)** | Cố định / `Daily` reset lượt (`openLv=21`, `ifOpen=1`) | Làm mới lượt theo ngày (`ZcsfUseRelation`: `10` lần/ngày, 10–100+ KC) | Tiêu KC quay ra Vàng hệ số x (`ZcsfTypeModel`: `addValueR 10000..`, `rawGold`, `upOdds`). | `Zcsf.ZcsfInfo`, `Zcsf.ZC` | **Đủ 100% Config + Lua (`LuckyCatLayer.lua`)**. Chưa có handler R7.5. |
| **`2303` `Xhzw` (Ước / Goddess Kiss)** | Hoạt động ngày (`openLv=30`, `ifOpen=1`) | Reset lượt miễn phí hằng ngày | Tung xúc xắc/quay biểu tượng nhận quà (`XhzwConfig`, `XhzwRewardModel`). | `Xhzw.GetXhzwInfo`, `XhzwTurn`, `XhzwAlterLuck`, `XhzwAlterLuckLock` | **Đủ 100% Config + Lua (`GoddessKissScene.lua`)**. Chưa nối RPC. |
| **`2507` `BddInfo` (Mộ Thần Binh / Bát Đại Địa Ngục)** | PvE leo ải hằng ngày (`openLv=26`, `ifOpen=1`) | Reset lượt/ngày (`BddResetUseRelation`) | Chiến đấu Spine 3 sao leo tầng, nhận buff sao, quét 3 sao, đổi Thần Binh/Nguyên Liệu (`BddNodeModel`, `BddRewardStarsRelation`, `BddBuffShopRelation`). | `BddInfo.Info`, `OneKeyThreeStar`, `Reset`, `GetBuffs`, `RewardBox`, `Ranking` | **Đủ 100% Config (`Bdd*Model`/`Relation`) + Lua (`XzyyMainScene.lua`)**. Cần mô phỏng `Ranking`. |
| **`2712` `MonthSignInfo` (Điểm Danh Tháng)** | Chu kỳ tháng (`openLv=5`, `ifOpen=1`) | Reset theo tháng dương lịch | Điểm danh tuần tự từng ngày 1..30 (`MonthlySignLayer.lua` truyền `{nil}`). | `MonthSignInfo.GetInfo`, `MonthSignInfo.DrawReward` | **Có UI Lua**, **THIẾU Config thưởng tháng gốc** trong `Config/` (server gốc gửi động). Cần dựng hoặc đối chiếu bảng chuẩn trước khi mở. |
| **`3700` `OnlineReward` (Quà Online)** | Chu kỳ phiên/ngày (`openLv=1`, `ifOpen=1`) | Đếm ngược `NeedReachedNum` phút (`CooledTime`) | Đủ phút bấm nhận quà trực tiếp trên HomeScene. | `OnlineReward.OnlineRewardInfo`, `DrawOnlineReward` | **Có UI Lua**, **THIẾU Config mốc phút & phần thưởng gốc** (server gửi động). Đang stub `{}`. |
| **`6900` `Limitthebounty` (Truy Nã / Quà Giới Hạn)** | Kích hoạt theo cấp (`openLv=1`, `ifOpen=1`) | Hết hạn sau `continuedTime` phút (`90000`) kể từ khi kích hoạt `triggerLV` | Đạt `receiveLV` nhận thưởng KC/Vàng/TB (`LimitthebountyModel.lua`, 6 gói). | `Limitthebounty.GetInfo`, `ReceivedReward` | **Đủ 100% Config (`LimitthebountyModel`) + Lua**. Chưa nối RPC. |
| **`6800` `TimeSpike` (Giờ Vàng / Flash Pack)** | Kích hoạt theo cấp + mốc nạp (`openLv=1`, `ifOpen=1`) | Hết hạn sau `continuedTime` (`360..720` phút) | Mở khóa gói khuyến mãi KC khi đạt `triggerLV` & `receiveCondition` (`TimespikeModel.lua`, 8 gói). | `Timespike.GetInfo`, `ReceivedReward` | **Đủ 100% Config (`TimespikeModel`) + Lua**. Phụ thuộc thanh toán/offline recharge. |
| **`7900` `OpenContest` (Đua Top Mở Server)** | Sự kiện 7 ngày mở server (`openLv=1`, `ifOpen=1`) | 7 ngày (`days = 1..7`) | Đạt `personalCondition` (`Lv 25`, `BattleStar 200`, `Ranking`, v.v.) và đua hạng (`OpencontestProject` + `OpencontestRankingrewards`). | `GlobalOpencontestRank.GetActiveRank`, `GetRank`, `DrawReward` | **Đủ 100% Config + Lua (`OpenSeriveCompetitionLayer.lua`)**, BXH cần NPC/multi-account. |
| **`8200` `Swdiamonds` (10 Vạn Kim Cương)** | Chuỗi nhiệm vụ tân thủ | Theo mốc | Hoàn thành mốc nhận KC từ `ShiwanyuanbaoRelation.lua`. | `Swdiamonds.*` | **Có Config `ShiwanyuanbaoRelation.lua`**. Cần rà soát thêm Lua gọi RPC tương ứng. |
| **Chuỗi `TimedActivity` (`4400`/`6300`/`6400`)** | Giới hạn thời gian (`TimedActivityOpenInfo`) | Theo kỳ `TimedActivity` | Cây Tiền (`TimedMoneyTree`), Đập Trứng (`TimedSmashingeggs`), Cây Ước (`TimedPrayTree`), Vòng Quay (`TimedSlot`), Rút Trang Bị (`TimedXssbInfo`), Tích Nạp/Tiêu/Đổi Quà (`TimedInfo.*`, `TimedLimitExchange`). | `TimedMoneyTree.*`, `TimedSmashingeggsInfo.*`, `TimedHopetreeInfo.*`, `TimedInfo.*`, `TimedLimitExchange.*`, `TimedXssbInfo.*` | **Chỉ có UI Lua**, **THIẾU toàn bộ Config thưởng/giá/tỷ lệ server gốc** (bao gồm `XssbModel.lua` & `CriticalTasksTypeRelation.lua` không có trong client VN). |
| **`Earlytask` (`OpenActivityLayer`)** | Tân thủ mở server | Chuỗi ngày | Hoàn thành nhiệm vụ theo ngày nhận quà. | `EarlytaskFinishRecord.GetEarlytaskList` | **THIẾU `EarlytaskModel.lua` & `EarlytaskRewardRelation.lua`** trong VN `Config/`. |

---

## III. Khảo Sát Hoạt Động Cần Người Chơi Khác & Đề Xuất Mô Phỏng (Mục VI)

Dựa trên thực tế kiểm tra mã nguồn VN `Challenge/`, `InstanceZones/`, `GGZJ/`, `Guild/` và thiết kế đa tài khoản (`MULTI_ACCOUNT_ARCHITECTURE.md`):

| Hoạt động | Cơ chế gốc & RPC | Khả năng chơi đơn bằng Đội hình lưu / NPC / Bot | Định hướng xử lý R7.5 & R7.6+ |
| :--- | :--- | :--- | :--- |
| **`TimedRecruit (9300)` BXH** | Cần điểm của nhiều người chơi cạnh tranh Top 1–50 (`RankList`, `TimedRecruitRankrewardModel`) | Tạo 25 NPC tất định theo `instance_id` (`510..1800+` điểm) và ghép chung điểm thực của người chơi | **Đã áp dụng trong R7.5**; về sau ghép thêm điểm các tài khoản khác cùng thế giới từ DB cục bộ. |
| **`PVP (2502)` Đấu Trường** | Đấu với đối thủ theo bậc rank (`PVP.GetPVPInfo`, `PVPFight`) | Dùng bot tất định + tương lai lưu `DefenseFormationSnapshot` của từng `PlayerId` trên cùng điện thoại | **Giữ nguyên logic R6/R7 an toàn trong R7.5**; R7.6+ cho phép chọn chiến đấu với đội hình phòng thủ thật của tài khoản khác. |
| **`Gddh (2503)` Đấu Võ Đại Hội** | Đăng ký theo bảng, khiêu chiến hạng & phục thù (`Gddh.*`, `openLv=35`) | Dùng NPC bot sinh từ HeroModel + đội hình phòng thủ đã lưu của các tài khoản cục bộ | Cần bổ sung vào R7.7 sau khi rà cấu hình mùa giải & phần thưởng. |
| **`PvP Liên Server` (`PVPinterTop`)** | Đánh bậc & Top (`CrossServerBattleScene.lua`, `Pvpinter*Model/Relation` có đủ!) | Bắt buộc dùng pool đối thủ NPC theo tier rank (`PvpinterLvRelation`, `PvpinterTopRewardRelation`) khi offline | Đủ config client; phù hợp mô phỏng bot có kiểm soát ở giai đoạn cuối. |
| **`TeambattleInfo (2319)` PB Tổ Đội** | Lập phòng `GetMyTeamInfo`, mời bạn/AI `InviteFriends`, vào ải tổ đội (`TeambattleNodeModel`, `TeambattleHeroNpc`, `TeambattlePlayerNpc`, `openLv=40`) | Client có sẵn bảng **`TeambattlePlayerNpc.lua`** và **`TeambattleHeroNpc.lua`**! Tức là bản thân game gốc hỗ trợ sẵn đồng đội NPC/AI + có thể chèn đội hình các nhân vật tài khoản khác | Khả năng khôi phục chơi đơn RẤT CAO ở R7.6+/R7.7 mà không cần server mạng thật. |
| **`GGZJ (2504)` Dũng Sĩ / Kho Vàng** | Đoạt ải có bảo vệ/cướp giữa người chơi & NPC (`GGZJ.*`, `GgzjSystemHeroRelation`, `openLv=32`) | Dùng NPC từ `GgzjSystemHeroRelation` kết hợp snapshot người chơi cùng thế giới | Khả thi cao cho R7.6/R7.7. |
| **`GuildBoss / GuildFb (3400)` Công Hội** | Bang chủ/thành viên đánh Boss & phụ bản bang (`GuildBossModel`, `GuildFbNodeModel`, `GuildBossInfo.*`, `openLv=27`) | Khởi tạo Công Hội cục bộ cho phép các tài khoản cùng máy gia nhập chung bang, cùng cộng dồn sát thương lên HP Boss chung | Giải pháp cực tự nhiên cho kiến trúc multi-account 1 điện thoại trong R7.8+. |
| **`BossBattle (2203)` Yêu Vương (`FriendHelp`)** | Toàn server cùng đánh Boss người chơi gặp | Khi chơi đơn cho phép NPC bạn đồng hành đánh phụ lượng sát thương có giới hạn hoặc tài khoản alt cùng điện thoại | Giữ nguyên logic R6 hiện có, mở rộng qua shared-world multi-account sau. |
