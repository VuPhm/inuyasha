# INUYASHA: SEEK JADE — R7.3 FULL GAME RECOVERY AUDIT
**Kiểm kê toàn diện tài nguyên, hệ thống gameplay, kinh tế & kiến trúc khôi phục Full Game**

- **Client chuẩn:** VN `com.cmn.inuyasha v5.0.4.98` (APK `96,806,706` bytes + OBB `113,083,804` bytes, tổng `8,301` file tài nguyên trong kho lưu trữ hợp nhất).
- **Server hiện tại:** DEV `checkpoint-vn-r7.2` (`31d187c`, cổng `8082`) & STABLE `checkpoint-vn-r6.2` (`5fed4bb`, cổng `8080`).
- **Tài khoản gốc được bảo vệ:** `OlinaHugh` (`PlayerId="200010"` trên cả STABLE và DEV).
- **Quy ước kiểm kê:**
  - Phân tách rõ **kết quả kiểm chứng thực tế** (31/31 unit tests trong `server/test_emulator.py` + nghiệm thu giao diện R7.2A trên Pixel 3 XL + nghiệm thu R6.1/R6.2) với **suy luận từ mã nguồn/bảng Config** (`analysis/vn/decompiled_src/`).
  - Không ước lượng phần trăm khôi phục tổng thể khi thiếu mẫu số chuẩn (một số bảng cấu hình hoạt động/tỷ lệ gốc nằm hoàn toàn phía server đã ngừng hoạt động).
  - Không trộn lẫn logic giữa các phiên bản quốc gia khác (`EN 5.1.1`, `TH 5.1.3.6`, `ZH 5.0.0`, `TW 1.4`).

---

## A. Tổng quan khôi phục

### 1. Thống kê tổng hợp tài nguyên & giao thức

| Hạng mục khảo sát | Số liệu đo trực tiếp (VN `5.0.4.98`) | Ghi chú đối chiếu |
| --- | --- | --- |
| **Tài nguyên APK + OBB** | `8,301` file (`499` `.skel`, `499` `.atlas`, `949` `.mp3`, `4,530` `.png`, `167` `.jpg`) | `204/204` tướng trong `HeroModel`, `70/70` nền chương, `689/689` icon ải đều có file ảnh/Spine tương ứng (`0` thiếu) |
| **Bảng cấu hình Lua (`Config/`)** | `271` file | `ModuleSubModel` có `350` mục (`293` `ifOpen=true`, `57` `ifOpen=false`); `FunctionOpenModel` có `23` mốc mở theo cấp (`Lv 5..40`) |
| **Giao thức HTTP RPC (`/client.aspx`)** | `96` module trong quét regex trực tiếp (`382` `Module.Method`) + `34` RPC đã nối qua lời gọi đa dòng/động (`114` module hợp nhất) | `server/emulator.py` hiện cài `118` handler (`108` hàm xử lý thực + `10` lambda stub rỗng) |
| **Bản quốc gia tham chiếu (chỉ đọc)** | `EN 5.1.1` (`363` Config), `ZH 5.0.0` (`405` Config), `TH 5.1.3.6` (`420` Config), `TW 1.4` (OBB `.luac` riêng) | Toàn bộ server chính thức đã chết (`SOURCE_INVENTORY.md`); riêng `ZH 5.0.0` & `TH 5.1.3.6` có thêm file config cho `Zhenjue`, `Pet` cao cấp, `Goddomain` nhưng **không có bảng xác suất gacha `HeroRecruit` ở bất kỳ bản client nào** |

### 2. Bảng phân loại toàn bộ hệ thống theo 6 mức độ

> **Thang phân loại bắt buộc:**
> 1. **Mức 1 — Có tài nguyên và logic hoạt động thực tế**
> 2. **Mức 2 — Có tài nguyên nhưng server chưa xử lý đầy đủ**
> 3. **Mức 3 — Đã mô phỏng một phần**
> 4. **Mức 4 — Chỉ có giao diện hoặc dữ liệu khai báo**
> 5. **Mức 5 — Thiếu tài nguyên hoặc logic**
> 6. **Mức 6 — Chưa đủ bằng chứng để kết luận**

| Nhóm / Hệ thống | Mức | Tài nguyên & Bằng chứng mã nguồn / kiểm thử | Phần còn thiếu & Ảnh hưởng trải nghiệm |
| --- | :---: | --- | --- |
| **Đăng nhập, Tạo nhân vật & Tân thủ (`Player`, `GuideMng`)** | **1** | `GuideRelation` (`73`), `GuideEventModel` (`466`), `GuideDialogModel` (`1015`), `PlayerLvRelation` (`100`). PASS cả `test_28..test_31` và **UI Pixel 3 XL R7.2A** (`TedGill` Lv 1 -> Lv 12, relogin OK) | Còn thiếu `AlterPlayerName`, `AlterPlayerHeadId`, `AddStarCount`, `GetPlayerInfo`. Ảnh hưởng nhẹ (chỉ thiếu đổi tên/avatar sau khi tạo). |
| **Cốt truyện Thường (`Battle.*`)** | **2** | `70` chương (`11..80`), `689` ải (`622` có drop), `207` rương chương & `207` rương đường; `10/11` RPC (`GetSays` thiếu). PASS UI `1-1..2-7` + R6/R7 unit test | `BattleNodeModel.lua` không chứa danh sách đội hình quái từng đợt gốc -> `_build_enemy_wave` dùng mob tổng hợp (`12012045`/`12013043`) + boss `pic`. Các chương `13..80` mới kiểm chứng ở mức dữ liệu/công thức, chưa chơi thử hết trên UI. Ảnh hưởng **trung bình** tới cảm giác chuẩn bản gốc ở giai đoạn giữa/cuối game. |
| **Ải Tinh Anh (`EliteBattle.*`)** | **2** | `36` ải, `747` dòng drop (`ElitebattleNodeDropRelation`); đủ `5/5` RPC; PASS `test_14` | Đội hình quái dùng chung `_build_enemy_wave` tổng hợp thay vì đội hình tinh anh gốc. Chưa test UI hết 36 ải. |
| **Yêu Vương / Boss Thế Giới (`BossBattle.*`)** | **2** | `LuckbossConfig`, `LuckbossValueShopModel` (`35`), `10/12` RPC thật + `2` stub; PASS `test_20`, `test_25` & nghiệm thu R6.2 | `BossBattle.Exchange` & `ExchangeInfo` là lambda stub rỗng `[]`/`{}` -> shop đổi điểm Yêu Vương chưa mua được; `JiFenRanking` & boss chỉ ở phạm vi cá nhân, chưa chia sẻ giữa nhiều tài khoản. |
| **Đội hình & Tướng (`Slot`, `SlotFormation`, `Hero`)** | **2** | `204` tướng (`149` `specialType=0`, `0` thiếu `.skel`), `HeroLvRelation` (`600`), `HeroStepRelation` (`57`). PASS UI R7.2A (`SlotFormation.Change`, `HeroLvUp`, `HeroStepUp`, `HeroRefine`) | Thiếu `Hero.HeroRebirth` (Trùng Sinh tướng hoàn trả tài nguyên) và `Slot.MateinfoCombat` (bỏ/ghép duyên kích ứng). Ảnh hưởng **cao** khi người chơi muốn đổi team giữa chừng. |
| **Chiêu Mộ (`HeroRecruit.*`)** | **3** | `HeroRecruitModel` (`5` loại: `1, 2, 3, 10, 30`). PASS cơ chế trừ vé/KC & CD ở UI R7.2A (`Ayame` `[2,1]`, `Kagome` `[3,1]`/`[3,0]`) | **`_rpc_recruit` đang chọn tuần tự `pool[idx % len(pool)]`** -> quay đơn luôn ra phần tử đầu (`Kagome` ở Linh Hồn), bỏ qua `OutZiCount` pity, thiếu `extraRewards` (`16060005`), sai trừ phí ở `rtype==10`, và `51` tướng `specialType=0` (gồm `11` UR quality `18`) chưa có đường rơi. Ảnh hưởng **rất cao (điểm nghẽn chính)**. |
| **Trang Bị (`Equip.*`)** | **2** | `140` trang bị, `EquipStepRelation` (`112`), `EquipArtifactRelation` (`1104`). PASS UI R7.2A (`EquipCompose`, `OneKeyEquipCombat`, `OneKeyEquipLvUp`, `EquipRefine`) | Thiếu `Equip.EquipRebirth` (trùng sinh trang bị) và `Callequip.*` (Mộ Thần Binh, `ifOpen=false` ở `ModuleSub[3802]`). |
| **Bảo Vật & Tầm Bảo (`Treasure*`, `TreasureLoot*`)** | **2** | `46` bảo vật, `228` mảnh; đủ `TreasureLoot`, `TreasureLootProtect`, `TreasureDebrisCompose`, `TreasureRefine`; PASS `test_13` | Thiếu **`TreasureLvUp`, `TreasureStepUp`, `TreasureCompose`, `TreasureRebirth`**, `TreasureLootForOneKey`. Không nâng cấp/tinh luyện được Sách/Ngựa -> mất nguồn tăng chiến lực quan trọng từ Lv 14-32 (`ModuleSub 1402/1404`). |
| **Ngộ Đạo / Tinh Túc (`LightenStar.*`)** | **1** | `AttrtreeModel` (`1001`), `AttrtreeSlotRelation` (`14`), đủ `3/3` RPC; PASS `test_08` | Hoạt động đầy đủ theo dữ liệu gốc VN. |
| **Tầm Ngọc / Thám Hiểm (`Explore.*`)** | **1** | `100` ô `ExploreBaseAwardsRelation`, đủ `5/5` RPC; PASS `test_08` & **25 lượt UI R7.2A** | Hoạt động đầy đủ theo dữ liệu gốc VN. |
| **Điện Tứ Hồn / Vinh Dự (`Glory.*`)** | **1** | `GloryTypeModel` (`3`), `GloryLvRelation` (`201` cấp), đủ `3/3` RPC; PASS `test_28..30` | Cộng đủ chỉ số HP/AP/DEF và STA. |
| **Thời Trang Chủ Tướng (`Fashion.*`)** | **2** | `FashionModel` (`8`), `FashionStepRelation` (`8`), `3/4` RPC (`DressUp`, `StepUp`, `Resolve`); PASS `test_22` | `ModuleSubModel[1104].ifOpen = false` trong config VN gốc nên nút Thời Trang bị ẩn nếu không bật cấu hình hoặc cấp thời trang khởi điểm. |
| **Đấu Trường / Quyết Đấu (`PVP.*`, `PVPShop.*`)** | **2** | `PvpShopModel` (`40`), `PvpRankRewardRelation`, đủ `5/5` RPC; PASS `test_21`, `test_23` | Đối thủ hoàn toàn là bot giả lập theo hạng (`_arena_bot_profile`), chưa có PvP bất đồng bộ đánh đội hình phòng thủ của tài khoản khác trên `ServerId=1`. |
| **Nạp, Thẻ Tháng & VIP (`PlayerCharge.*`, `CardInfo.*`, `VipWelfare.*`)** | **2** | `VipModel` (`21` cấp), `VipLvIntroRelation` (`21`), `VipSlotRelation` (`4`), `ChargeConfig` (`3`), `CardModel` (`1`), `VipWelfareModel` (`21`), `ShopVipGiftModel` (`21`). Backend `ConfirmOrder`/`CardInfo.Activity` PASS `test_16`, `VipWelfare` PASS UI R7.2A | Bấm **Mua** trên APK gọi `GenerateOrderID` + `com.kull.sdk` (`Entity.smali:502`) nên **không cộng Kim Cương/VIP khi không có thanh toán thật**. Ngoài ra **`ShopGift` (21 gói VIP 0..20 `16010001..21`) chưa xử lý**. Ảnh hưởng **rất cao (điểm nghẽn chính)**. |
| **Cửa hàng Đạo cụ & Shop Thần Bí (`ShopGoods.*`, `MysteryShop.*`)** | **2** | `ShopGoods` đủ `3/3` RPC (PASS UI R7.2A & `test_12`). `MysteryShop` đủ `6/8` RPC (PASS `test_28..30`) | Thiếu `SVipGetInfo` & `SVipMysteryShopBuyGoods` (VIP Shop `ModuleSub[2102]`, `ifOpen=false`); chưa đồng bộ đầy đủ hạn mức VIP từ `VipBuyLimitModel`. |
| **Thương Nhân Thần Bí (`TraderInfo.*`)** | **3** | `TraderRefreshModel` (`6`), `TraderDiscountOddsRelation` (`3`) | `GetInfo` là stub `{"TraderInfo": None}`; thiếu `BuyGoods` & `RefreshtGoodsList`. |
| **Túi Đồ & Rương Chọn (`Goods.*`, `Bag.*`)** | **2** | `GoodsModel` (`1043`), `GoodsOutputRelation` (`245`), `Goods.GoodsUse` đã chạy | Thiếu `GoodsUseForBoxChoice` (rương chọn quà như `16060005` Mảnh Thần Tướng / `16060008` Thần Tướng!), `GoodsSell`, `GetGoods`, `Bag.BagExpand` (`20` mốc). Ảnh hưởng **cao** khi mở quà rương chọn. |
| **Phúc Lợi Cố Định (`GiftLogin`, `GiftLv`, `LvPlan`, `Daydayfund`, `StartWorkReward`)** | **1** | Đều có đủ Config VN & RPC thật; PASS `test_16`, `test_22`, `test_29`, `test_30` & `StartWorkReward` trên UI R7.2A | Ghi chú nhỏ: `LvPlan.ReceiveLvPlan` hiện trừ `100` KC mỗi lần nhận mốc thay vì chỉ trừ 1 lần mở quỹ (cần kiểm lại điều kiện `OpenLvPlan`); `Daydayfund` đọc `VIPLv` thay vì `Vip`. |
| **Quà Thành Tích / 7 Ngày (`SuccessTargetInfo.*`, `EarlytaskFinishRecord.*`)** | **4** | `SuccessTargetModel` (`42`), `SuccessTargetRewardRelation` (`33`), `SuccessTimeModel` (`8`), `5` RPC | **`0/5` RPC xử lý -> CRASH Lua (`SuccessTargetLayer.lua:151`)** khi bấm nút `QUÀ THÀNH TÍCH` mới mở ở **Lv 11** (quan sát trực tiếp trên Pixel 3 XL lúc `01:52:40`). Ảnh hưởng **rất cao** cho trải nghiệm đầu game! |
| **Nhiệm Vụ Ngày (`DailyTaskInfo.*`) & Tiệm Vụ Chính** | **4** | `DailytaskModel` (`25`), `DailytaskRewardModel` (`5`), `DailytaskExpRelation` (`100`) (mở ở Lv 25) | `0/5` RPC xử lý; `MainTaskModel` không có trong VN Config (nhiệm vụ chính theo luồng Chương + `GuideRelation`). Thiếu EXP/KC/Tài nguyên hàng ngày từ Lv 25. |
| **Điểm Danh Tháng (`MonthSignInfo.*`) & Quà Online (`OnlineReward.*`)** | **5** | Lua UI hoàn chỉnh (`MonthlySignLayer.lua`, `HomeScene.lua`); server chỉ có stub `[]`/`{}` | Client VN **không có bảng dữ liệu thưởng** (`configs=[]` trong `MonthlySignLayer.lua`, thiếu `MonthSignModel` / `OnlineRewardModel` vốn nằm trên server). Cần khôi phục bảng thưởng dựa trên `GoodsModel`/`Enums` nếu bật lại. |
| **Ải Ác Mộng (`Nightmare.*`)** | **4** | `65` chương (`11..75`), `639` ải, `899` dòng drop, `192` box chương | `0/6` RPC xử lý -> toàn bộ chế độ cốt truyện bậc cao sau Thường/Tinh Anh chưa chơi được. |
| **Thần Binh Địa Huyệt (`BddInfo.*`), Dũng Sấm Kim Khố (`GGZJ.*`), Đấu Võ (`Gddh.*`), Lĩnh Địa (`CrusadeInfo.*`)** | **4** | Đều có đủ bảng Config phong phú (`BddNodeModel` `51`, `GgzjSystemHeroRelation` `100`, `GddhShopModel` `16`, v.v.) và Lua UI đầy đủ | `0` RPC thực (`BddInfo` 12 RPC, `GGZJ` 8 RPC, `Gddh` 10 RPC, `CrusadeInfo` 8 RPC đều thiếu). Ảnh hưởng **cao** tới nội dung PvE/PvP trung & hậu kỳ (Lv 26-35). |
| **Phó Bản Tổ Đội (`Teambattle*`, `TeamcopyInfo`), Thú Cưng Viễn Chinh (`PetOutInfo`)** | **4** | `TeambattleNodeModel` (`24`), `TeambattleHeroNpc` (`432`), `PetoutNodeModel` (`48`), `PetoutShopRelation` (`1656`) | `0` RPC thực (`GetInviteInfo` stub `{}`). Nếu chơi cá nhân offline cần chế độ bot đồng đội/đánh solo tương thích giao thức. |
| **Hệ thống Bồi dưỡng Sâu (`Pet`, `Zhenjue`, `Gem`, `Lianti`, `Warfare`, `Warfarespirit`, `RebornInfo`)** | **4** | `Pet` (`111`), `Zhenjue` (`30`), `Gem` (`90`), `Lianti` (`5` loại / `101` lv), `Warfare` (`15`), `Warfarespirit` (`108`), `RebornGoods` (`28`) | `0` RPC thực trên toàn bộ 7 hệ thống; `Gem/Pet/NewWraith` thiếu cả `Slot.*Combat`. Ảnh hưởng **cao** đến toàn bộ tăng tiến sức mạnh từ giữa game trở đi. |
| **Yêu Linh (`NewWraith.*`, `Wraithfood`) & Tháp Quái (`MonstertowerInfo`)** | **5** | Có một phần UI Lua (`NewWraith/`, `BattleSettleLayer`) & tham chiếu cũ (`313` trong `HomeScene`) | Thiếu bảng cấu hình chính (`NewWraithModel`, `MonstertowerFloorModel`) trong VN Config (`5.0.4.98`). |
| **Công Hội, Đấu Giá, Bạn Bè, Thư, Đạn Mạc, Lì Xì, Chat** | **4** | Đủ UI + Config (`GuildFbChapter` `10`, `GuildShop` `22`, `AuctionShop` `96`, `ChatMng.lua` giao thức TCP) | `0` RPC xử lý cho `Guild` (17), `GuildBossInfo` (6), `Auction` (4), `Friend` (5), `FriendMessage` (9), `PlayerEmail` (2), `LeaderBoard` (2), `RedBag` (5), `BarragePve` (2); chưa bật Chat TCP `:8081`. `PlayerEmail` & `LeaderBoard` rất hữu ích cả khi chơi cá nhân + multi-account. |
| **Sự kiện Hạn Giờ & Lễ Hội (`Timed*`, `YiYuan`, `Timespike`, `Zcsf`, `OldPlayer*`, `Bữa Tối`, `CDK`, `Share`)** | **5** (một phần **4**) | Có đủ Lua UI trong `TimedActivity/` (`33` file), `ExtraActivity/` (`15`), `OpenActivity/` (`7`). `TimedRecruit` (`6`), `Timespike` (`8`), `Limitthebounty` (`6`), `Zcsf` (`6`) có Config cục bộ | Đa số sự kiện (`Tiền Rơi/MoneyTree`, `Đập Trứng`, `Quay Số`, `Cây Ước`, `Nạp/Tiêu Tích Lũy`, `Đổi Quà Lễ`, `Bữa Tối`, `Giáng Sinh/Tết`) thiếu bảng dữ liệu phần thưởng gốc vì server đẩy qua `TimedActivityOpenInfo.ExtraInfo`. Các hoạt động `Share/WeChat` phụ thuộc SDK mạng xã hội cũ đã đóng. |
| **Kênh thông báo, Quảng cáo, Feedback, Đạn Mạc (`Notice`, `Chat` ngoài)** | **3 / 5** | `Notice.GetNoticeList` trả `[]` (đã test R7.2A); `Barrage`, `Feedback`, `WeChat` phụ thuộc dịch vụ ngoài | Ảnh hưởng **rất thấp**; chỉ cần điền `Notice` nội bộ chào mừng local server là đủ. |

---

## B. Báo cáo chuyên sâu

### 1. Chiêu mộ và nguyên nhân cố định Kagome

Khảo sát trực tiếp `server/emulator.py:1895-1973`, `analysis/vn/decompiled_src/Config/HeroRecruitModel.lua` và `Store/RecruitScene.lua:875-925`:

1. **`HeroRecruit.Recruit` hiện trả về tướng gì?**
   - Theo `server/emulator.py:1940-1945`:
     ```python
     for idx in range(count):
         if rtype == 2 and not rs.get("MidAlreadyUseResource", False):
             chosen_hid = 12011014  # Ayame (4*/5* starter summon from Destiny Recruit pool)
         else:
             chosen_hid = pool[idx % len(pool)] if pool else 12011014
         tuples.append((1201, chosen_hid, 1))
     ```
   - `pool` được lấy từ `rec_cfg.get("outShowMain") or rec_cfg.get("outShowAll")`.
   - Khi quay **1 lần** (`count = 1`, áp dụng cho `rtype = 1, 2, 3`), vòng lặp chỉ chạy `idx = 0`, nên **luôn chọn đúng phần tử đầu tiên `pool[0]`**:
     - `rtype = 1` (Mộng Cảnh): `outShowMain[0] = 12011023` (*Chokyukai*, quality `10`).
     - `rtype = 2` (Túc Mệnh): `outShowMain[0] = 12011014` (*Ayame*, quality `13`).
     - `rtype = 3` (Linh Hồn): `outShowMain[0] = 12011005` (**Kagome**, quality `15`).
   - Khi quay **10 lần** (`rtype = 30`, `count = 10`, đã thấy ở trace `01:27:15`), `idx = 0..9` trả cố định đúng 10 tướng đầu trong `outShowMain`: *Kagome, Miroku, Sango, Kouga, Jaken, ...*

2. **Tướng `12011014` trong báo cáo R7.2 là ai?**
   - Là **Ayame** (`quality = 13`, 5★ cam, thuộc `HeroRecruitModel[2].outShowMain[0]` & `outShowAll[0]`), **không phải Kagome** (`12011005`, `quality = 15`). Người dùng thấy toàn ra *Kagome* khi chơi tự do vì banner cao cấp **Chiêu Mộ Linh Hồn** (`rtype = 3`) có `outShowMain[0] = 12011005` (*Kagome*), như đã tái hiện trực tiếp trong trace R7.2A lúc `01:52:53` (`[3, 1]` miễn phí) và `01:52:56` (`[3, 0]` 280 KC).

3. **Lần chiêu mộ đầu tiên & các lượt tiếp theo:**
   - Lần đầu tiên ở `rtype = 2` (khi `MidAlreadyUseResource == False`) cố định ra `12011014` (*Ayame*) để khớp mạch hướng dẫn tân thủ (đã PASS trên Pixel 3 XL).
   - Hiện tại ở các lượt tiếp theo (`count = 1`), nhân vật **KHÔNG hề thay đổi**: quay `rtype = 3` bao nhiêu lần vẫn ra đúng `Kagome`, quay `rtype = 2` bao nhiêu lần vẫn ra đúng `Ayame`!

4. **Bảng pool, trọng số, phân loại & cơ chế bảo đảm gốc:**
   - `HeroRecruitModel.lua` khai báo đầy đủ 5 banner: `[1]` Mộng Cảnh (`16050003` x1, `outShowAll` 70 tướng bậc 6/10/13, `outShowMain` 30 tướng bậc 10), `[10]` Mộng Cảnh x10 (`16050003` x10), `[2]` Túc Mệnh (`80` KC, CD miễn phí `1380` phút = 23h, `outShowAll` 70 tướng bậc 6/10/13, `outShowMain` 22 tướng bậc 13), `[3]` Linh Hồn (`280` KC, CD miễn phí `2820` phút = 47h, `extraRewards = "1606,16060005,1"`, `outShowAll` 80 tướng bậc 10/13/15, `outShowMain` 28 tướng bậc 15), `[30]` Linh Hồn x10 (`2680` KC, `extraRewards = "1606,16060005,10"`).
   - **Không có bảng trọng số chiêu mộ thường (`HeroRecruit`) trong client Config** ở cả VN `5.0.4.98`, EN `5.1.1`, TH `5.1.3.6` lẫn ZH `5.0.0` — xác suất từng bậc phẩm vốn nằm ở server gốc. Tuy nhiên client có tham chiếu tỷ lệ chuẩn của game ở `TimedRecruitModel.lua` (`outputLowHeroR = 9000` tức ~90% bậc thấp, `outputHighHeroIntervalNum = 9` tức tối đa 10 lần chắc chắn nổ tím/tướng chính) và trường `OutZiCount` trong `RecruitScene.lua:901-922` đếm ngược lượt bảo đảm ra tím/cam (`quality = 15`).
   - **Lỗi bổ sung phát hiện trong `emulator.py`:**
     - `extraRewards` (`16060005` — *Quà Mảnh Thần C (C)*) không được trao khi quay `rtype = 3` / `30`.
     - `rtype = 10` (Mộng Cảnh x10) không đi qua nhánh `if rtype == 1:`, rơi vào `elif is_free == 0` nên trừ sai thành `80` Kim Cương thay vì `10`x Bùa Triệu Hồi `16050003`.
     - `OutZiCount` chỉ trừ `max(0, OutZiCount - 1)` một chiều, không reset chu kỳ sau khi nổ bảo hiểm.

5. **Tướng nào thực sự nhận và sử dụng được?**
   - Trong `204` tướng của `HeroModel.lua`, có `149` tướng chơi được (`specialType == 0`). Trong đó:
     - `98` tướng nằm trong pool `HeroRecruitModel` (phẩm `6, 10, 13, 15`), nhận và đưa vào trận được.
     - `51` tướng `specialType == 0` **không nằm trong `HeroRecruitModel`**: `36` quái/fodder phẩm `3`, `2` phẩm `13`, `2` phẩm `15` (*Goshinki*, *Toran*), và toàn bộ `11` Thần Tướng phẩm `18` (*Inu no Taishou*, *Kikyo*, *InuYasha*, *Kanade Hime*, *Midoriko*, *Sesshomaru*, *Takemaru*, *Kaguya*, *Naraku*, *Tứ Đấu Thần*, *Inu Kimi*) vốn phân phối qua Quà Thần Tướng (`16060008`, `16060009`, `16060034`, `16060037..39`), `TimedRecruit` / `Shop` / ghép mảnh.

6. **Phương án khôi phục chuẩn (tuyệt đối không random đồng đều):**
   - Tách `outShowAll` theo từng bậc `quality`:
     - Banner `1` / `10` (Mộng Cảnh): trọng số giảm mạnh theo phẩm (`6 > 10 >> 13`), không để phẩm `13` ngang tỷ lệ phẩm `6`.
     - Banner `2` (Túc Mệnh): ưu tiên phẩm `6/10` (~88-90%), tỷ lệ vừa cho phẩm `13` (`outShowMain`), giữ lần quay đầu `not MidAlreadyUseResource` = `12011014` (*Ayame*).
     - Banner `3` / `30` (Linh Hồn): dùng `outShowAll` (`80` tướng bậc `10, 13, 15`) kết hợp trọng số theo phẩm + **cơ chế bảo hiểm `OutZiCount`** (mỗi lần không ra `quality = 15` thì giảm `OutZiCount`; khi `OutZiCount == 0` hoặc x10 đảm bảo ít nhất `1` tướng `quality = 15` từ `outShowMain` rồi reset lại `OutZiCount` theo chu kỳ); lần đầu `not HigAlreadyUseResource` có thể đảm bảo `1` tướng `quality = 15` (chọn ngẫu nhiên trong nhóm `outShowMain` hoặc pool khởi đầu thay vì khóa vĩnh viễn mọi lượt về sau).
   - Đồng thời sửa trừ `10x 16050003` cho `rtype = 10` và cấp `extraRewards` (`16060005`), cộng với hỗ trợ `GoodsUseForBoxChoice` để mở được rương chọn mảnh Thần Tướng.

---

### 2. Nạp, VIP và Kim cương

1. **Danh sách gói nạp, Thẻ Tháng & Quà Nạp Đầu:**
   - **8 gói Kim Cương (`emulator.py:150-159`):** `com.cmn.inuyasha.gem60`, `gem180`, `gem300`, `gem680`, `gem900`, `gem1980`, `gem3280`, `gem6480` — ứng với `60..6480` Kim Cương cơ bản + `GiveGamePoint` x2 cho lần mua đầu mỗi mốc (`IsFirst = true`). Lưu ý: `RechargeScene.lua:1242` hiển thị chuỗi `"Chỉ bán: <ChargePoint>"` trực tiếp từ danh sách `PlayerCharge.GetChargeList` do server trả về.
   - **Thẻ Tháng (`CardModel.lua:14-22`):** `ID = 1`, `price = 90000` (hiển thị VNĐ; `CARD_MODEL_CFG` trong emulator dùng `300` VIP EXP/điểm), thời hạn `30` ngày, thưởng ngay `268` KC (`buyReward`), thưởng mỗi ngày `100` KC (`dailyReward`).
   - **3 mốc Quà Nạp Đầu (`ChargeConfig.lua:11-28`):** `60` điểm (`18,000`), `300` điểm (`90,000`), `900` điểm (`270,000`) — mở qua `PlayerCharge.DrawChargeBox`.

2. **VIP EXP, Đặc quyền & Quà VIP:**
   - `VipModel.lua` (`21` bậc `0..20`, từ bậc `11..20` client hiện thành `SVIP 1..10`): `expTotal` tích lũy tăng dần `0, 60, 360, 860, 1860, 3360, 5360, 7860, 10860, 14860, 19860, 27860, 39860, 54860, 74860, 99860, 129860, 169860, 219860, 299860, 399860`.
   - `VipModel` định nghĩa `21` đặc quyền (loại cường hóa bạo kích trang bị, số lần làm mới miễn phí/trả phí Tiệm Thần Bí, mua lượt Tinh Anh/Boss/Chiêu Tài/Tầm Ngọc/Địa Huyệt/Thần Bí Bảo Tàng, hệ số `ggzjMutipleR`, v.v.) + `VipSlotRelation` mở ô đồng hành `9, 10, 11, 12` tại **VIP 1, 5, 12, 14** + `VipBuyLimitModel` quy định hạn mức mua hàng ngày tại Shop.
   - **Quà VIP gồm 2 luồng tách biệt:**
     - `VipWelfare` (`VipWelfare.GetVipWelfare` / `DrawVipWelfare`): quà nhận miễn phí mỗi ngày theo VIP `0..20` — **ĐÃ hoạt động trên APK**.
     - `ShopVipGiftModel` (`21` gói VIP `0..20`: `goodsModelID = 16010001..16010021`, `currPrice` từ `18` KC ở VIP 0 đến `9888` KC ở SVIP 10) gọi `ShopGift.ShopGiftList` và `ShopGift.BuyGift` (`Store/StoreScene.lua:832-855`) — **CHƯA được xử lý trong `emulator.py`**.

3. **Cơ chế tiêu hao Kim Cương & lỗ hổng hiện tại:**
   - Tiêu KC trong `emulator.py` hiện đi qua `ResourceLedger`: `HeroRecruit.Recruit` (`80/280/2680`), `Battle.ConFight` (`5` KC/lượt khi thiếu bùa `16050011`), `Battle.ResetCount`, `Explore` reset (`20`), `ShopGoods.BuyGoods`, `MysteryShop.RefreshtGoodsList`/`MysteryShopBuyGoods`, `LvPlan.ReceiveLvPlan` (lưu ý: `emulator.py:3718-3725` hiện trừ `-100` KC ở mỗi lần nhận mốc thay vì chỉ trừ 1 lần mở Quỹ Trưởng Thành), `BossBattle.BuyCount`, `Fashion.StepUp`.
   - **Tại sao bấm Nạp / Thẻ Tháng trên APK không cộng tài nguyên?**
     - `Store/RechargeScene.lua:1272-1285`: chỉ khi `IPlatform:getConfigItem("Channel") == "MQKK"` client mới gọi thẳng `HttpRequest("PlayerCharge", "ConfirmOrder", {chargePoint})`.
     - Với APK VN hiện tại (`Channel` khác `"MQKK"`), bấm `Mua` gửi `PlayerCharge.GenerateOrderID` (hoặc `CardInfo.GenerateOrderID`), nhận mã `ORD-...` rồi gọi xuống Java `Entity.MQRecharge` -> `com.kull.sdk.ui.dialogs.Dialogs.showPaymentByPackage` (`Entity.smali:502`). Vì SDK CMN cũ không thể mở cổng thanh toán thật, giao dịch kết thúc im lặng và `ConfirmOrder` / `CardInfo.Activity` **không bao giờ được gọi**.
     - Hiện chỉ có RPC ẩn `PlayerCharge.ConfirmOrder` / `CardInfo.Activity` và `/admin/grant`, `/admin/vip` dùng để test HTTP.

4. **Phương án mục tiêu "Bấm gói nạp -> nhận tài nguyên ngay, không cần thanh toán":**
   - Hai cách sạch để nối luồng trên APK mà giữ nguyên kinh tế & `ResourceLedger`:
     - **Phương án 1 (Sạch ở cả APK + Server, ưu tiên):** Patch nhánh `RechargeScene.luac` / `MonthCardLayer.luac` (hoặc đặt `Channel=MQKK` kèm tùy chỉnh UI nạp/thẻ tháng) sao cho bấm **Mua** gói Kim Cương gọi `PlayerCharge.ConfirmOrder {ProductId/ChargePoint}` và bấm **Mua Thẻ Tháng** gọi `CardInfo.Activity {cardId}` kèm hộp thoại xác nhận; toàn bộ cộng KC, thưởng x2 `IsFirst`, `VipEXP`, nâng cấp `Vip` tự động, và mở khóa `ChargeConfig` chạy đúng chuẩn trong `_apply_simulated_charge` & `_rpc_card_activity` qua `ResourceLedger`.
     - **Phương án 2 (Bổ sung thêm ShopGift):** Cài đặt `ShopGift.ShopGiftList` và `ShopGift.BuyGift` dùng `ShopVipGiftModel.lua` + `GoodsOutputRelation.lua` để người chơi mua đủ 21 gói VIP bằng Kim Cương.

---

### 3. Số lượng chương/ải có dữ liệu so với số lượng chơi được

| Chế độ chơi | Dữ liệu có trong VN Config | Trạng thái trên Server Emulator | Thực tế chơi được & Độ chuẩn bản gốc |
| --- | --- | --- | --- |
| **Ải Thường (`Battle`)** | `70` chương (`11..80`, `needLV` `1..80`), `689` ải (`620` có 1 đợt, `69` có 2 đợt; `622` ải có bảng drop), `207` rương chương, `207` rương đường | Đủ `10/11` RPC (`GetSays` thiếu). Mở khóa theo `needLV`, đếm `FightCount`/`StarCount`, thưởng hộp | Về **công thức**: qua được đủ `70` chương (`11..80`). Về **UI thực tế**: đã nghiệm thu `1-1..2-7` (`12` ải). Tuy nhiên quái mỗi đợt dùng công thức tổng hợp (`12012045`/`12013043` + boss `pic`), không phải đội hình quái cố định gốc (không có trong client). |
| **Ải Tinh Anh (`EliteBattle`)** | `36` ải, `747` dòng rơi (`ElitebattleNodeDropRelation`), cấu hình VIP mua lượt | Đủ `5/5` RPC (`test_14` PASS) | Chạy được về giao thức; quái dùng chung `_build_enemy_wave` tổng hợp; chưa nghiệm thu toàn bộ `36` ải trên UI APK. |
| **Yêu Vương (`BossBattle`)** | `LuckbossConfig`, `LuckbossValueShopModel` (`35`) | `10/12` RPC thật (`test_20`, `test_25`, R6.2 PASS) | Săn Boss hoạt động; thiếu shop điểm (`ExchangeInfo`/`Exchange` là stub). |
| **Ác Mộng (`Nightmare`)** | `65` chương (`11..75`), `639` ải, `899` dòng drop, `192` rương chương | `0/6` RPC (`miss`) | **Chưa chơi được** (dù dữ liệu bản đồ/rơi đồ rất đầy đủ). |
| **Thần Binh Địa Huyệt (`BddInfo`)** | `51` ải (`BddNodeModel`), `153` point, shop/buff đủ | `0/12` RPC (`miss`) | **Chưa chơi được**. |
| **PB Tổ Đội (`Teambattle` / `Teamcopy`)** | `24` ải, `432` NPC | `0/20+` RPC (`GetInviteInfo` stub) | **Chưa chơi được** (cần bổ sung bot đồng đội khi chơi offline). |
| **PB Công Hội (`GuildFb`)** | `10` chương, `10` ải, `50` NPC | `0` RPC | **Chưa chơi được** (phụ thuộc thêm hệ thống `Guild`). |
| **Thú Cưng Viễn Chinh (`PetOutInfo`)** | `48` ải, `1656` dòng shop | `0/13` RPC | **Chưa chơi được**. |
| **Tháp Quái (`MonstertowerInfo`)** | Không có bảng tầng (`MonstertowerFloorModel` không tồn tại) | `0/1` RPC | **Chưa chơi được / thiếu dữ liệu**. |

---

### 4. Các sự kiện và hoạt động

- **Hoạt động thường trực đã hoạt động (6 hệ thống):** `GiftLogin` (7 ngày), `GiftLv` (20 mốc Lv 5..100), `VipWelfare` (hàng ngày VIP 0..20), `LvPlan` (Quỹ Trưởng Thành, lưu ý lỗi trừ 100 KC nhiều lần cần chỉnh), `Daydayfund` (Quỹ Mỗi Ngày, mở Lv 19), `StartWorkReward` (Quà Khởi Nghiệp). Tất cả đều có bảng dữ liệu gốc và đã qua test tự động (Riêng `VipWelfare` & `StartWorkReward` đã PASS trên UI APK).
- **Hoạt động mở sớm bị lỗi / chưa hoạt động (3 hệ thống ưu tiên):**
  1. `SuccessTargetInfo` (**Quà Thành Tích / 7 Ngày**, mở ngay **Lv 11**): crash Lua tại `SuccessTargetLayer.lua:151` trên Pixel 3 XL do `GetInfo` trả `{}` thiếu `TargetList`.
  2. `MonthSignInfo` (**Điểm Danh Tháng**, mở **Lv 5**) & `OnlineReward` (**Quà Online**): chỉ có stub `[]`/`{}`; bảng thưởng gốc nằm phía server đã đóng nên muốn bật phải tự thiết kế lại danh sách quà cân bằng theo `GoodsModel`.
  3. `DailyTaskInfo` (**Nhiệm Vụ Ngày**, mở **Lv 25**): đã có đủ `25` nhiệm vụ & `5` mốc rương điểm tích lũy trong Config VN, chỉ thiếu cài đặt `5` RPC + theo dõi bộ đếm hành động hàng ngày.
- **Sự kiện hạn giờ (`TimedActivity` — `33` file Lua):** Hầu hết hoạt động (`TimedMoneyTree`, `TimedSmashingEggs`, `TimedHopeTree`, `TimedLuckDraw`, `TimedChargeTotal/Single/Days`, `TimedUseTotal`, `TimedExchange`, `CommonHoliday`, `FestivalActivity`) đều phụ thuộc server gửi cấu hình động qua `Avatar.TimedActivityOpenInfo` (`Data/NetworkResData.lua:4914-4966`). Một số sự kiện có bảng config gốc cục bộ như `TimedRecruitModel` (6 kỳ Chiêu Mộ Thần Tướng), `TimespikeModel` (8 gói), `LimitthebountyModel` (6 mốc), `ZcsfTypeModel` (Chiêu Tài Miêu 6 mốc) — rất phù hợp để khôi phục trước sau khi sửa kinh tế/gacha.

---

### 5. Khả năng nhiều tài khoản cùng một thế giới (`ServerId = 1`) và PvP bất đồng bộ

Phân tích dựa trên `MULTI_ACCOUNT_ARCHITECTURE.md`, `Login/GameLoginScene.lua`, `Login/StartGameScene.lua`, `System/AccountSwitchLayer.lua`, `analysis/vn/apktool_patched/smali/com/moqikaka/sdk/Entity.smali`, và `server/emulator.py`:

1. **Khả năng tái sử dụng định danh `AccountId / ServerId / PlayerId`:**
   - Kiến trúc VN gốc đã phân tách rành mạch 3 tầng:
     - `AccountId` (`UserID`, lưu bởi `LocalData:saveLoginInfo`, gửi ở `/API/ServerList_Client.ashx` & `Player.Login` arg #6)
     - `ServerId` (ID thế giới, gửi ở `req["ServerId"]`, dùng `ServerId = 1` chung cho mọi tài khoản)
     - `PlayerId` (ID nhân vật duy nhất cho mỗi cặp `(AccountId, ServerId)`, trả từ `Player.Login` và gửi trên mọi `/client.aspx`).
   - Do đó mô hình **nhiều tài khoản cục bộ trên cùng `ServerId = 1` + PvP bất đồng bộ** hoàn toàn khớp nguyên bản giao thức VN, **không cần thay đổi thiết kế protocol**.

2. **Hai điểm đang khóa 1-tài-khoản cần tháo gỡ (chưa sửa trong R7.3):**
   - **Phía APK (`Entity.smali:431-445` & `AccountManage.lua`):** `MQLogin` đang hardcode `uid = "100001"`, `platformId = "1001"`. Muốn chuyển tài khoản A/B/C ngay trên 1 điện thoại qua `Hệ thống -> Đổi Tài Khoản` (`AccountSwitchLayer`), cách tự nhiên nhất của client VN là bật `GameLoginScene:createMqkkUI()` (`Channel=MQKK`) trỏ `AccountManage.lua` về emulator cục bộ (`/sdk/login`, `/sdk/Register` -> trả `UserID` tương ứng từng tài khoản A, B, C) hoặc thêm nút chọn tài khoản local. Client lưu cache hướng dẫn theo `PlayerId` nên khi `Player.Login` trả `PlayerId` khác nhau (`200010` cho `OlinaHugh`, `200011` cho tài khoản B...), tiến trình và `StepCountList` không đè lẫn nhau.
   - **Phía Server (`emulator.py:6009-6055` & `4453-4929`):**
     - `GameEmulatorState` hiện chỉ ánh xạ cứng `ServerId=1 -> normal_profile.json`, `ServerId=2 -> debug_profile.json`, bỏ qua `UserID` / `Session`. Cần chuyển sang cấu trúc `accounts_index.json` + `worlds/1/players/<player_id>/profile.json` + `worlds/1/world_state.json` như đã thiết kế trong `MULTI_ACCOUNT_ARCHITECTURE.md` (giữ nguyên `OlinaHugh` ở `worlds/1/players/200010/profile.json`).
     - `PVP` hiện chỉ dựng bot giả (`_arena_bot_profile`). Để **tài khoản A đấu với đội hình phòng thủ đã lưu của tài khoản B**, server chỉ cần lưu snapshot phòng thủ (`heroes`, `slots`, `embattle`, `FAP`, `Lv`, `HeadImageId`) vào `world_state["player_snapshots"][player_id]` mỗi khi người chơi đổi đội hình/trang bị/đăng nhập, đưa `player_id` vào `world_state["arena_ladder"]` (kèm bot lấp hạng trống), và giữ `PVP.PVPFight` chạy `simulate_fight_info` trên snapshot bất đồng bộ.

---

### 6. Đánh giá khả năng đóng gói bản Android độc lập

Kiểm tra trực tiếp phần cứng Pixel 3 XL, mã nguồn `server/`, `AndroidManifest.xml`, và cấu trúc APK/OBB:

| Tiêu chí kỹ thuật | Kết quả khảo sát thực tế | Đánh giá khả thi |
| --- | --- | --- |
| **Phụ thuộc thư viện ngoài của Server** | `server/emulator.py` (`290,666` bytes), `combat_sim.py` (`10,738` bytes), `economy_audit.py` (`8,269` bytes), `game_data.json` (~`5.5 MB`) đều dùng **100% Python Standard Library**, **0 phụ thuộc `pip` ngoài** | **Rất thuận lợi** — không cần C-extension ngoài nào để chạy logic game + HTTP RPC `/client.aspx`. Riêng `AssetArchive` đọc APK/OBB chỉ phục vụ Web PoC (`/assets/`, `/api/atlas/`), client Android đã tự giải nén OBB nên server trên Android không cần nạp 210 MB APK+OBB. |
| **Phụ thuộc server ngoài** | Mọi lời gọi gameplay, ServerList, Login (`AccountManage`), Nạp (`ConfirmOrder`/`CardInfo`), Chat TCP (`:8081`), Report/Step đều chuyển hướng về địa chỉ nội bộ được | **0 phụ thuộc bắt buộc ra Internet** sau khi chỉnh endpoint về `127.0.0.1:<port>`. Chỉ Google/Facebook/WeChat SDK (`com.kull.sdk`, `Bugly`) là cần vô hiệu hóa hoặc bỏ qua an toàn. |
| **Tài nguyên phần cứng Pixel 3 XL** | CPU `aarch64` (hỗ trợ `arm64-v8a, armeabi-v7a, armeabi`), RAM `3579 MB`, bộ nhớ trong trống `39 GB / 52 GB` (`25%` đã dùng). APK `96.8 MB` + OBB `113.1 MB` (`libcocos2dlua.so` kiến trúc `armeabi`) | **Dư dả**. Emulator Python tải `game_data.json` (`~5.5 MB` trên đĩa, `~25-45 MB` RAM khi chạy cùng vài profile JSON) tiêu tốn CPU gần như `0%` lúc rảnh và chỉ xử lý từng request JSON gọn nhẹ; nằm thoải mái trong `3579 MB` RAM & `39 GB` trống của Pixel 3 XL. |
| **3 phương án chạy trên Android** | 1. **Termux + APK (`127.0.0.1:8080`):** Giữ nguyên Python `server/`, dễ phát triển nhanh và chia sẻ, nhưng người chơi phải bật Termux chạy nền (bị Android Doze/hạn chế chạy nền trên Android 12 nếu không tắt tối ưu pin).<br>2. **Ứng dụng đồng hành Android nhúng Python (Chaquopy / Foreground Service) + APK game trỏ `127.0.0.1`:** Tự động bật local HTTP service không cần Termux, nhưng tăng dung lượng app đồng hành (~30-50 MB runtime Python).<br>3. **Port/nhúng thẳng HTTP server nhẹ (`NanoHTTPD` / Kotlin) hoặc service nội bộ vào cùng 1 APK:** Trải nghiệm 1-chạm hoàn chỉnh nhất để gửi cho bạn bè, nhưng đòi hỏi viết lại phần Python (`emulator.py` + `combat_sim.py` ~6,400 dòng) hoặc nhúng runtime Python (`Chaquopy`, cần chuyển `armeabi` sang hỗ trợ `armeabi-v7a` / chạy tiến trình riêng nếu dùng `arm64`). | **Khả thi cao**. Nên dùng **bộ APK + server Python trên PC/Termux** trong giai đoạn khôi phục tính năng nhanh (R7.4–R7.6), sau khi gameplay ổn định mới đóng gói thành **1-app standalone** (Foreground Service nhúng Python hoặc port Kotlin khi bộ RPC đã chốt). |
| **Giữ nhiều tài khoản & Cập nhật APK không mất save** | Nếu lưu JSON vào thư mục riêng trong sandbox `Android/data/com.cmn.inuyasha/files/`, việc gỡ cài đặt hoặc cài bản APK khác chữ ký sẽ **xóa sạch dữ liệu**. Cần: (1) Dùng **cùng keystore cố định** để update đè trực tiếp không cần gỡ APK; (2) Lưu thư mục `worlds/` + `accounts/` + `audit_ledger.jsonl` ra vùng lưu trữ bên ngoài sandbox hoặc hỗ trợ **Export/Import JSON/ZIP** qua Storage Access Framework (SAF) / `/sdcard/Documents/InuYashaRevival/` | **Giải quyết được triệt để** miễn thiết kế đường dẫn lưu ngoài hoặc Export/Import ngay từ đầu kiến trúc multi-account. |

---

## C. Roadmap khôi phục

Sắp xếp thứ tự ưu tiên theo đủ **5 tiêu chí**: (1) Ảnh hưởng tới khả năng chơi full game, (2) Tính sẵn có của tài nguyên/logic gốc, (3) Chi phí triển khai, (4) Nguy cơ phá vỡ gameplay đã hoạt động, (5) Khả năng kiểm thử và nghiệm thu.

| Giai đoạn đề xuất | Hạng mục trọng tâm | (1) Ảnh hưởng | (2) Tài nguyên/Logic gốc | (3) Chi phí | (4) Rủi ro hồi quy | (5) Kiểm thử & Nghiệm thu |
| --- | --- | :---: | --- | :---: | :---: | --- |
| **Round tiếp theo: R7.4 — Khôi phục Kinh tế, Chiêu mộ, VIP & Lỗi đầu game** *(Đề xuất ưu tiên)* | 1. **Sửa `HeroRecruit.Recruit`**: phân tầng trọng số theo phẩm `outShowAll` + chu kỳ bảo hiểm `OutZiCount` + cấp `extraRewards` (`16060005`) + sửa chi phí `rtype=10` (giữ `12011014` lần đầu Túc Mệnh).<br>2. **Nạp & Thẻ Tháng tức thì ("Bấm là nhận") + `ShopGift` (21 gói VIP `16010001..21`)** + sửa trừ 100 KC nhiều lần ở `LvPlan`.<br>3. **`SuccessTargetInfo` (`4900`, mở Lv 11)** hết crash Lua + **`Goods.GoodsUseForBoxChoice`** mở rương chọn Thần Tướng (`16060005`, `16060008..09`). | Rất cao | Có đủ Config VN + UI client | Thấp–TB | Thấp (không đụng luồng guide R7.2) | Unit test tỷ lệ/bảo hiểm/ledger + UI test trực tiếp trên Pixel 3 XL (`Buy Diamond`, `MonthCard`, `ShopGift`, `Recruit x1/x10`, `SuccessTarget` Lv 11) |
| **R7.5 — Nâng cấp cốt lõi Trung/Hậu kỳ & Tiến trình hàng ngày** | 1. **`Treasure` (`TreasureLvUp`, `TreasureStepUp`, `TreasureCompose`, `TreasureRebirth`)** + **`HeroRebirth` & `EquipRebirth`**.<br>2. **`DailyTaskInfo` (Lv 25)** dựa trên `25` nhiệm vụ & `5` mốc rương gốc.<br>3. **`BossBattle.Exchange`** + **`TraderInfo` (`BuyGoods`, `RefreshtGoodsList`)** + bật `Fashion` (`1104`) & `SVipMysteryShop`. | Rất cao | Đủ 100% Config VN + UI | Trung bình | Thấp–TB | Unit test từng bảng tăng cấp + test tái hiện luồng tăng FAP, trùng sinh, làm nhiệm vụ ngày |
| **R7.6 — Multi-account `ServerId = 1` & PvP Bất đồng bộ (trên nền `OlinaHugh`)** | 1. Triển khai `accounts_index.json` + `worlds/1/players/<pid>/profile.json` + khóa `ResourceLedger`, migrate tự động `OlinaHugh` (`200010`).<br>2. Bật chuyển tài khoản A/B/C trên 1 điện thoại (`Channel=MQKK` hoặc switcher cục bộ).<br>3. `world_state.player_snapshots` cho **`PVP` bất đồng bộ** + chia sẻ `LuckBoss` / `LeaderBoard` / `PlayerEmail`. | Rất cao | Đủ giao thức client VN + đã có thiết kế `MULTI_ACCOUNT_ARCHITECTURE.md` | TB–Cao | TB (đụng cấu trúc save & `Login`) | Backup SHA-256 bắt buộc trước migration + test chuyển A/B/C đấu snapshot phòng thủ của nhau trên Server 1 |
| **R7.7 — Mở rộng Bản đồ & Hệ thống Sức mạnh Hậu kỳ** | 1. Phó bản đơn/tổ đội có bot: **`Nightmare` (65 chương / 639 ải)**, **`BddInfo` (51 ải)**, **`GGZJ`**, **`Gddh`**, **`CrusadeInfo`**, **`PetOutInfo` (48 ải)**, **`Teambattle` (24 ải + bot đồng đội)**.<br>2. Hệ thống nuôi dưỡng: **`Gem` (`90`)**, **`Pet` (`111`)**, **`Lianti`**, **`Zhenjue`**, **`Warfare`/`Warfarespirit` (`15+108`)**, **`RebornInfo`**. | Cao (tới late-game) | Đủ phần lớn Config VN (lưu ý `Zhenjue` một số bảng phụ chỉ có ở `ZH/TH`, `NewWraith`/`Monstertower` thiếu bảng) | Cao | Trung bình | Tách từng cụm module theo cấp mở khóa (`FunctionOpenModel` Lv 26..40+), test tính chỉ số slot & combat từng tính năng |
| **R7.8 — Sự kiện, Xã hội & Đóng gói Android Độc lập** | 1. Sự kiện: `TimedRecruit` (`6` kỳ), `Timespike`, `Limitthebounty`, `Zcsf`, `MonthSignInfo`/`OnlineReward` (khôi phục bảng hợp lý), chọn lọc sự kiện `TimedActivity` theo lịch xoay vòng.<br>2. `Guild` (`17` RPC + `GuildBoss` + `Auction`) & `Friend`/`Chat :8081` nếu cần chơi nhiều người qua mạng.<br>3. Đóng gói **Android Standalone** (Termux script hoặc app Foreground Service nhúng Python `127.0.0.1` + lưu save ngoài sandbox). | Trung bình–Cao | Hỗn hợp (một số bảng nằm ở server cũ) | TB–Cao | Thấp (tầng đóng gói tách biệt) | Kiểm thử dài hạn độ bền save khi nâng cấp APK, đo RAM/pin trên Pixel 3 XL |

### Đề xuất bước tiếp theo

- **Dừng tại đây chờ duyệt lộ trình.**
- **Đề xuất thực hiện ngay ở R7.4 (sau khi được duyệt):**
  1. Khôi phục **Chiêu Mộ (`HeroRecruit.Recruit`)** đúng cơ chế pool theo bậc phẩm + chu kỳ bảo hiểm + `extraRewards` + sửa `rtype=10` (chấm dứt tình trạng quay đơn chỉ ra *Kagome*).
  2. Triển khai **Nạp / Thẻ Tháng tức thì ("Bấm gói nạp -> nhận tài nguyên tương ứng ngay")** + **`ShopGift` (`21` gói VIP)** + sửa bug trừ KC lặp ở `LvPlan`.
  3. Sửa crash Lv 11 **`SuccessTargetInfo`** + bổ sung **`Goods.GoodsUseForBoxChoice`** để mở được các rương Thần Tướng (giải phóng luôn đường nhận tướng `quality = 18` ngoài pool chiêu mộ thường).
  4. Thực hiện nghiệm thu lại cả Unit Test lẫn **giao diện trực tiếp trên Pixel 3 XL (DEV `:8082`)** trước khi quyết định gộp và promote lên STABLE.
