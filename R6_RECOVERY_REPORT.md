# INUYASHA REVIVAL — ROUND R6 RECOVERY REPORT
**Client:** VN `com.cmn.inuyasha` (`v5.0.4.98`)  
**Baseline:** `checkpoint-vn-r5.2` (`81a6e17`) -> `checkpoint-vn-r6`  
**Development & QA Server:** DEV `http://127.0.0.1:8082` (`PID 7615`, isolated `server/dev_saves/`)  
**Production / User Server:** STABLE `http://127.0.0.1:8080` (`PID 6251`, `OlinaHugh` Lv 16, **100% untouched & uninterrupted**)

---

## 1. Báo cáo Phase B — BossBattle (Ma Vương / Yêu Vương, Lv 18)

### Dữ liệu VN đã trích xuất (`server/extract_game_data.py` -> `server/game_data.json`)
- `luckboss_config` (`LuckbossConfig.lua`): `alloutAttackUseR=30000` (x3 lượt), `alloutAttackAttrUpR=30000` (x3 AP + đầy nộ `RP=100`), `attackNumRecoverTime=1800`, `buyAttackNumBaseUseNum=10`, khung giờ x2 tích điểm `18:00–20:00` (`0.75–0.833333`).
- `luckboss_trigger` (`LuckbossTriggerRelation.lua`) & `luckboss_value_shop` (`LuckbossValueShopModel.lua` — 35 mốc thưởng từ `100` đến `3500` điểm).

### Cơ chế hoạt động đã phục hồi (`server/emulator.py`)
- **Điều kiện xuất hiện (`_maybe_trigger_luckboss`):** Chỉ kích hoạt khi `player.Lv >= 18` sau khi thắng ải thường (`Battle.Fight`, `Battle.ConFight`) hoặc ải Tinh Anh (`EliteBattle.Fight`), giữ tối đa 3 Boss sống cùng lúc và không làm ảnh hưởng người chơi dưới Lv 18 (bảo toàn bất biến `test_14` ở Lv < 18). Trả về trường `"BossId"` để `BattleSettleLayer` mở popup `BossAppearLayer`.
- **Quái Boss & Chỉ số:** Sinh Boss từ `HeroModel` (`12010050..12010055`) theo cấp người chơi và bậc Boss (`CurHP`/`TotalHP` ~40k–120k+, gắn `DropResource` đá trang bị `16020020/21` hoặc mảnh bảo vật `15030101`/`15040101`, `AwayTime = now + 7200s`).
- **Chiến đấu & Sát thương thực (`BossBattle.GetFightInfo`, `BossBattle.Fight`):**
  - Chế độ thường (`IsFullFight=0`): tốn `1 AttackNum` + `5 VIT`.
  - Chế độ Toàn Lực / All-Out Attack (`IsFullFight=1`): tốn `3 AttackNum` + `15 VIT`, nhân `3x AP` và khởi đầu `100 RP`.
  - Tính sát thương thực tế trên `CurHP` tại vị trí Boss (`PosId=8`) thông qua `verify_data["hp"]` hoặc mô phỏng xác định `combat_sim.simulate_fight_info`, cập nhật `HurtValue`, `SingleJiFen` (nhân đôi trong khung giờ `18:00–20:00`), cập nhật `BossCoin`, cấp `EXP`/`Gold`/`HeroEXP` và thưởng tiêu diệt (`DropResource`) khi `CurHP == 0` (`BossExist = False`).
- **Mốc thưởng & Hồi lượt (`BoxList`, `DrawBox`, `OneKeyDrawBox`, `BuyCount`, `_sync_boss_battle_state`):**
  - Hồi `1 AttackNum` mỗi `1800s` tối đa theo `VipModel.attackLuckBossMaxNum`.
  - Mua lượt bằng Kim Cương giới hạn theo `VipModel.allowBuyLuckBossFightNum` với giá gốc VN `sum(ceil(i/2) * 10)`.
  - Đổi 35 mốc rương tích điểm `100..3500` theo `LuckbossValueShopModel`; `Goods.GoodsUse` đã nối với `GoodsOutputRelation` (245 nhóm) để mở đá trang bị (`16020019/20/21`) từ mốc thưởng Boss.
- **Tính năng cộng đồng mô phỏng tối thiểu:** `BossBattle.FriendHelp` cập nhật cooldown `CanHelpTime = now + 60`; `BossBattle.JiFenRanking` ghép người chơi vào bảng xếp hạng với 9 bot có `PlayerId` UUID 36 ký tự xem được đội hình qua `Slot.SlotFormations`.

---

## 2. Báo cáo Phase C — Arena / Quyết Đấu (Bot Solo Mode, Lv 20)

### Dữ liệu VN đã trích xuất
- `pvp_shop` (`PvpShopModel.lua` — 40 vật phẩm shop Đấu Trường, kiểm tra `needStep`, `needRank`, `perMaxNum`, `totalMaxNum`, `needPVPCoin`).
- `pvp_first_reward` (`PvpRankFirstRewardRelation.lua` — 4.500 mốc thưởng kim cương đột phá hạng theo bậc `1..5`).
- `pvp_rank_reward` (`PvpRankRewardRelation_1..5.lua` — 10.000 mốc thưởng `PVPCoin` & `rawGold` theo bậc `1..5` và hạng `1..2000`).

### Cơ chế Arena PvP đấu Bot đã phục hồi
- **Bậc đấu trường & Thang bot thực tế (`_arena_bot_profile`):** Chia bậc theo `Lv` (`<=30` bậc 1, `<=40` bậc 2, `<=50` bậc 3, `<=60` bậc 4, `61+` bậc 5). Bot sử dụng `PlayerId`, `HeroId`, `EquipId` dạng GUID 36 ký tự (`_det_uuid`) để vượt qua `IdIsValid()` của client (ngăn client tự gán `IsWinFight = 1` ở `ArenaHomeScene.lua:1540`). Đội hình bot ghép từ `HeroModel` + `EquipModel` thực qua `_compute_slot_property(..., include_player_star=False)`: hạng `1..20` dùng đội 6 tướng bậc cao trang bị Cam/Đỏ; hạng `1350..1500` dùng đội 3–4 tướng Lục/Lam.
- **Xem đội hình đối thủ (`Slot.SlotFormations`):** Nâng cấp handler trả về đủ `{PlayerInfo, SlotInfos, MateInfos, SlotFormationInfo, SkillInfos, CombatPet}` (giữ `SlotInfo` tương thích ngược) và đính `"Hero"` vào từng slot cho cả người chơi lẫn mọi bot trong Arena / JiFenRanking.
- **Chiến đấu theo công thức gốc (`PVP.PVPFight` & `combat_sim.simulate_fight_info`):**
  - Tốn `2 STA` theo `StaConfig`, khóa nếu `Lv < 20`.
  - Dùng `IsPVP = True` với đúng thứ tự lượt đối thủ PvP `[7, 8, 9, 10, 11, 12]` (`BattleProcess.lua`).
  - **Không tự mặc định thắng:** thử thách bot Hạng 1 với đội Lv 20 thua thật (`IsWinFight = 0`, giữ nguyên hạng, nhận an ủi `15 PVPCoin` + `500 Gold`); thắng các bot vừa sức (`IsWinFight = 1`, hoán đổi hạng, tính chênh lệch Kim Cương vượt mốc kỷ lục từ `PvpRankFirstRewardRelation`, lật 3 thẻ `ChoiceGetGameResource`, thưởng `PVPCoin`).
- **Làm mới, Top 20 & Shop (`PVP.Refresh`, `PVP.GetPVPTopRankList`, `PVPShop.PVPShopBuy`):**
  - Cooldown làm mới `5s`, cập nhật tập đối thủ phía trên.
  - `GetPVPTopRankList` trả về 5 phần tử ứng 5 bậc PvP, mỗi bậc 20 cao thủ đầu bảng.
  - `PVPShopBuy` kiểm tra đủ bước/hạng/giới hạn ngày/tổng và trừ `PVPCoin` qua `ResourceLedger` (đã thêm `PVPCoin`, `BossCoin` vào `economy_audit.py`).
- **Hoàn thành Guide Lv 20:** `Player.AlterPlayerStepCount` `[6, 206]` lưu bền vững qua save/reload.

---

## 3. Báo cáo Phase D — Các tính năng phụ (Lv 18–20)

| Tính năng | Trạng thái | Chi tiết triển khai |
|---|---|---|
| **Ải Tinh Anh + Guide 8 (Lv 18)** | Hoàn tất | `EliteBattle.Fight` giữ nguyên logic cũ và gắn thêm trigger `BossId` chỉ khi `Lv >= 18`; `AlterPlayerStepCount [8, 215]` hoạt động bình thường. |
| **BattleForTen (Lv 20)** | Hoàn tất | `Battle.ConFight` hỗ trợ đầy đủ `consumeType` (`2`: Bùa Liên Chiến `16050011`, `3`: Kim Cương bù thiếu) tương thích ngược với test cũ và có thể trigger `BossId` ở `Lv >= 18`. |
| **Daydayfund (Lv 19)** | Hoàn tất | `Daydayfund.GetInfo`, `Invest` (đầu tư `100` Gold, quay hệ số `30*Lv .. 60*Lv`), `Harvest` (nhận Gold nhân theo `DaydayfundVipRelation`, thưởng thêm `50` Kim Cương khi hệ số tận cùng là `8`). |
| **StartWorkReward** | Backend xong + Guard | `StartWorkReward.GetStartworkRewardInfo` & `GetStartworkReward` hoạt động theo đúng schema `StartworkRewardLayer.lua`, đồng thời **giữ `RedDotInfo["2718"] = 0`** để `HomeScene.lua:146` không tự bật popup văng lỗi Lua gốc của client (`StartworkRewardLayer.lua:90`, `StartworkRewardTipLayer.lua:15`). |
| **Fashion (`5600..5603`, Lv 20)** | Hoàn tất nhẹ | `GetInitData.FashionInfo` nối save; `_grant_resources_from_tuples` hỗ trợ `typeID=1901`; khôi phục `Fashion.DressUp`, `Fashion.StepUp`, `Fashion.Resolve` theo `FashionModel` & `FashionStepRelation`. |
| **InitData Debris Split & Chest** | Hoàn tất | Tách `GoodsHeroDebrisInfo` (`1501`) & `GoodsEquipDebrisInfo` (`1502`) khỏi `GoodsPropsInfo`; `Goods.GoodsUse` hỗ trợ mở rương xác suất theo `GoodsOutputRelation`. |

---

## 4. Danh sách RPC mới / cập nhật trong Round R6

### BossBattle (`10` RPC chính + `2` stub)
- `BossBattle.GetBossList`
- `BossBattle.GetBossInfo`
- `BossBattle.GetFightInfo`
- `BossBattle.Fight`
- `BossBattle.BoxList`
- `BossBattle.DrawBox`
- `BossBattle.OneKeyDrawBox`
- `BossBattle.BuyCount`
- `BossBattle.FriendHelp`
- `BossBattle.JiFenRanking`
- `BossBattle.ExchangeInfo` (stub tối thiểu `[]`), `BossBattle.Exchange` (stub tối thiểu `{}`)

### Arena (`4` PVP + `1` PVPShop + nâng cấp `Slot`)
- `PVP.GetPVPInfo`
- `PVP.Refresh`
- `PVP.PVPFight`
- `PVP.GetPVPTopRankList`
- `PVPShop.PVPShopBuy`
- `Slot.SlotFormations` (nâng cấp trả `{PlayerInfo, SlotInfos, MateInfos, SlotFormationInfo, SkillInfos, CombatPet}` cho bản thân và bot)

### Phase D (`8` RPC mới + cập nhật `Battle` / `EliteBattle` / `Goods` / `InitData`)
- `Daydayfund.GetInfo`, `Daydayfund.Invest`, `Daydayfund.Harvest`
- `StartWorkReward.GetStartworkRewardInfo`, `StartWorkReward.GetStartworkReward`
- `Fashion.DressUp`, `Fashion.StepUp`, `Fashion.Resolve`
- Cập nhật `Battle.Fight`, `Battle.ConFight`, `EliteBattle.Fight` (`BossId` ở Lv >= 18), `Goods.GoodsUse` (`GoodsOutputRelation`), `Player.GetInitData` & `Avatar.RedDotInfo`.

---

## 5. Kết quả Fast QA & Kiểm thử tự động

### A. Bộ Unit & Regression Tests (`server/test_emulator.py`)
- **23 / 23 tests PASS (`OK`)**:
  - `test_01..test_19`: toàn bộ hồi quy R1–R5.2 giữ nguyên xanh.
  - `test_20`: BossBattle spawn gate (`< 18` không spawn, `>= 18` spawn), thường & All-Out Attack (`100 RP`), trừ HP thực, kill drop, `BoxList`/`DrawBox`, `BuyCount`, `JiFenRanking`, save/reload.
  - `test_21`: Arena gate (`< 20` từ chối), bot 36-char GUID, `Slot.SlotFormations`, `Refresh` & cooldown, **thua thực khi đánh Rank 1**, **thắng & leo hạng `< 1000` nhận Kim Cương đột phá**, `GetPVPTopRankList`, `PVPShopBuy`, Guide 6 (`Player.AlterPlayerStepCount [6, 206]`), save/reload.
  - `test_22`: Phase D (`GoodsHeroDebrisInfo` split, `Goods.GoodsUse` đá trang bị xanh `16020020`, `Daydayfund` invest/harvest, `StartWorkReward` với guard `RedDotInfo["2718"]=0`, `Fashion` DressUp/StepUp/Resolve, `Battle.ConFight`).
  - `test_23`: Preset Fast QA `QA_LV18`, `QA_LV20`, và thứ tự đánh `PVP_ENEMY_ORDER`.

### B. Fast QA Presets & Benchmark (`server/qa_runner.py`)
- `QA_LV18` (`server/qa_runs/qa_lv18/qa_run_report.json`): thắng 5/5 ải kiểm thử (`Lv 18 -> Lv 20`, `FAP 58,378`, `StarCount 5`).
- `QA_LV20` (`server/qa_runs/qa_lv20/qa_run_report.json`): thắng 5/5 ải kiểm thử (`Lv 20 -> Lv 22`, `FAP 60,219`, `StarCount 5`).
- `benchmark`: 10-stage (`10/10` won, `Lv 12`, `final_node 1216`), R3/R4 regression (`25/25` won, `Lv 19`, `EliteBattle` PASS), `FAILURE` preset thua xác thực sau 2 round (`battle_defeat`).

### C. Live HTTP QA trên DEV (`http://127.0.0.1:8082`, `server/qa_runs/dev_r6_http_qa_report.json`)
- Profile clone từ STABLE (`OlinaHugh` Lv 16) khóa chặt Arena (`Status=-1`) và không spawn Boss khi đánh Tinh Anh ở Lv 16.
- Nâng `QA_LV18`: đánh ải spawn Boss `f6ea1489-bd93-43e2-8b79-cd095255453b`, tiêu diệt gây `73,067` sát thương nhận `607` JiFen, nhận rương `OneKeyDrawBox`, mua lượt `BuyCount=1`, `JiFenRanking` trả 10 hạng.
- Nâng `QA_LV20`: xem đội hình bot Rank 1 (`FAP=193,631`), đánh Rank 1 thua (`IsWinFight=0`), thắng bot hợp lệ nhảy lên hạng `1205`, mua `PVPShopBuy`, `Daydayfund` quay hệ số `1169` thu hoạch thành công, `Battle.ConFight` 3 lượt, và **khởi động lại DEV daemon (`env_ctl.py daemon restart --env dev`) xác nhận hạng `1205` & `BuyCount` bảo toàn qua reload**.

### D. Kiểm tra Schema Save & Smoke DEV/STABLE
- Đọc thử bản sao save STABLE `OlinaHugh` Lv 16 qua `GameEmulatorState`: không mất bất kỳ trường nào (`PlayerName`, `Lv=16`, `Gold=173795`, `Diamond=655`, `StarCount=51`), tự khởi tạo sạch các khóa mới (`boss_battle`, `pvp`, `daydayfund`, `startwork`, `fashions`, `player.PVPCoin`, `player.BossCoin`, `player.FashionModelId`).
- `env_ctl.py smoke` trả `ok: true` trên cả DEV (`:8082`) và STABLE (`:8080`).

---

## 6. Lỗi còn lại & Hạn chế đã ghi nhận

1. **Pixel UI Verification chưa chạy trực tiếp trong R6:** Thiết bị Pixel 3 XL (`192.168.1.89:40197`, `pid 3438`) đang chạy APK trỏ `STABLE :8080`. Tuân thủ nghiêm nguyên tắc *"Không làm gián đoạn STABLE hoặc thay APK đang cài nếu không cần thiết"* và *"Không tự động đưa thay đổi lên STABLE"*, chưa chuyển Pixel sang DEV hay deploy R6 lên `:8080`.
2. **Bug Lua có sẵn trong client VN gốc (`StartworkReward`):**
   - `ExtraActivity/StartworkRewardLayer.lua:90` viết nhầm `#self.self.mCurRewardInfo` (gây crash nếu listView load khi có dữ liệu).
   - `ExtraActivity/StartworkRewardTipLayer.lua:15` gọi đúp `layer:removeFromParent()()`.
   - Server đã chủ động giữ `RedDotInfo["2718"] = 0` để người chơi không gặp crash khi vào `HomeScene`.
3. **Lệch nhỏ ở popup client gốc `BossAppearLayer.lua`:**
   - `BossAppearLayer.lua:479` hiển thị giá ước tính mua lượt dùng `ceil(i/10)*10` trong khi `MonsterLayer.lua:133` và `LuckbossConfig.desc` dùng `ceil(i/2)*10` (server áp dụng `ceil(i/2)*10` chuẩn config).
   - `BossAppearLayer.lua:568` khi gửi dữ liệu Boss sang màn kết toán quên gán khóa chữ thường `playerId` nên nút mời hỗ trợ ngay tại màn thắng không hiện khi đi từ popup BossAppear (nhưng nút hỗ trợ trong `MonsterLayer` hoạt động bình thường).
4. **Tính năng ngoài phạm vi / backlog tối thiểu:**
   - `BossBattle.ExchangeInfo` / `Exchange` chưa có bảng Shop tích điểm đổi đồ rời ngoài 35 mốc `LuckbossValueShopModel`; để stub an toàn.
   - Đua top liên server, nhận thưởng thư cuối ngày Arena lúc 22:00 thực tế theo cron chưa bật (đã trả `CurrentReward` + `RewardTimeStart/End` chuẩn UI).

---

## 7. Khả năng triển khai lên STABLE & Đề xuất ưu tiên R7

### Khả năng triển khai lên STABLE (`:8080`)
- **Sẵn sàng triển khai an toàn khi người dùng cho phép:**
  - Schema save tương thích ngược 100% với `server/saves/normal_profile.json` (`OlinaHugh` Lv 16) và `debug_profile.json`.
  - Mọi RPC mới đều mang tính bổ sung; 19 regression tests trước đây và 4 bộ test R6 mới đều xanh hoàn toàn (`23/23 OK`).
  - Lộ trình triển khai đề xuất khi người dùng xác nhận: backup STABLE (`env_ctl.py backup --tag pre-r6`), restart STABLE trên code mới (`env_ctl.py daemon restart --env stable`), kiểm tra smoke `:8080`, rồi kiểm tra UI Boss / Arena trực tiếp trên Pixel.

### Đề xuất ưu tiên Round R7
1. **Pixel UI Verification cho R6** (ngay sau khi được phép đưa R6 lên STABLE): mở màn `MonsterLayer` (BossBattle), `ArenaHomeScene` (Guide 6 + 1 trận Arena + `PVPShop`), `CoinFundLayer` (Lv 19), và `FashionLayer`.
2. **Nội dung Lv 20–30 (Progressive Content):**
   - **Thần Binh / Luyện Tháp / Khiêu Chiến (`Tower` / `BattleNormal` Lv 22–25)** hoặc **Đoạt Bảo mở rộng & Kết Duyên / Tẩy Luyện Trang Bị**.
   - **Sửa có chọn lọc client Lua bugs (nếu build bản vá Lua nhẹ):** `StartworkRewardLayer.lua:90`, `StartworkRewardTipLayer.lua:15`, `BossAppearLayer.lua:479/568`.
   - **Đội hình Chiến Trận / Warfarespirit / Pet** nếu mở ở mốc Lv 25–30.
