# R2_REPORT.md — InuYasha: Seek Jade Revival (Round R2 Handoff)

## 1. Phân tích nguyên nhân mất Tutorial (P1)

Kiểm tra trực tiếp `GuideMng.lua`, `HomeScene.lua`, `RoleCreateScene.lua`, `Network/HttpClient.lua`, `Data/NetworkResData.lua` và các bảng `Config/GuideRelation.lua`, `Config/GuideEventModel.lua` cho thấy Tutorial ở R1 không chạy do 5 nguyên nhân kết hợp:

1. **Điều kiện kích hoạt ban đầu (`Player.Login` & `IsNewPlayer`)**:
   - `RoleCreateScene` chỉ chạy khi `Player.Login` trả về `IsNewPlayer == 1`. R1 mặc định `IsNewPlayer = 0` nên bỏ qua tạo nhân vật và phần mở đầu (`BattleScript0000`, `CgScene`).
2. **Cách client lưu & đồng bộ Guide Step**:
   - Client lưu song song ở **local** (`LocalData:saveGuideData(playerId, guideId, ordinal)` theo `PlayerId` trên máy Android) và đồng bộ về **server** qua hai đường:
     - Gọi RPC ngay `Player.AlterPlayerStepCount(guideId, ordinal)` với `guideId == 999999` (`statisticsGuideId`) hoặc special guide.
     - Kẹp vào trường `ExtensionString.GuideInfo` (`AddCommitGuideData` trong `Network/HttpClient.lua`) trên mọi HTTP request kế tiếp, lưu vào `PlayerInfo.StepCountList` trả về ở `Player.Login` / `Player.GetInitData`.
   - `GuideMng:initGuidMng()` lấy `math.max(localOrdinal, serverOrdinal)`. Do R1 đặt `StepCountList = {"1": 999}`, client xem như toàn bộ chuỗi hướng dẫn chính `GuideRelation[1]` (72 entry / 38 bước thực tế) đã hoàn tất.
3. **Ngưỡng cắt cứng theo cấp độ (`Lv >= 7`)**:
   - Trong `GuideMng.lua` (dòng `161–164`), khi `PlayerInfo.Lv >= 7`, `getGuideOrdinal(1)` tự ghi đè ordinal thành `919` và trả `nil`, còn `enterGamePage()` / `haveGuide()` kết thúc guide chính và bỏ qua các level guide thấp hơn (ví dụ `17` mở ở Lv 7, `2` ở Lv 8, `3` ở Lv 9). R1 khởi tạo `Lv = 10`, nên toàn bộ guide tân thủ bị tắt ngay lập tức.
4. **Thiếu các RPC phụ trợ của chuỗi hướng dẫn**:
   - Server R1 chưa có `HeroRecruit.Recruit`, `Slot.HeroCombat`, `Battle.DrawRoadBox`, `Battle.DrawBox`, `Player.GetStepCountReward`, `Equip.EquipCompose`, `Equip.EquipOneKeyCompose`, `Slot.OneKeyEquipCombat`, `Equip.OneKeyEquipLvUp`, `Equip.EquipLvUpForCount`, `SlotFormation.GetFormation`, `SlotFormation.Change`, chưa xử lý `ExtensionString.GuideInfo`, và `Battle.GetNodeList` trả về cả node chưa mở (`Flag=0`) làm `BattleLayer` trỏ sai con trỏ ải hiện tại (`mBattleNodeList[#mBattleNodeList]`).
5. **Lỗi ngưỡng cũ (`> 2` / `< 3`) còn sót trong EN 5.1.1 client**:
   - `Config/GuideRelation.lua` trong EN 5.1.1 (và ZH 5.0.0) đã rút gọn còn **1 lần chiêu mộ** (`1051` Destiny Summoning) và **1 lần ra trận** vào Slot 2 (`1071`), tổng team là **2 tướng** (Main Hero + Ayame).
   - Tuy nhiên `HomeScene.lua` (`3461`, `3471`) và `GuideMng.lua` (`316`) vẫn giữ guard cũ `heroCount > 2` và `formationHeroCount < 3` (từ phiên bản trước khi còn Dream Summoning `104/105` + Slot 3 `1091`), khiến vừa đóng màn Team sau bước `110`, `HomeScene:correctGuideEventId()` tự cuộn ngược tutorial từ `111` về `107`.

---

## 2. Các Guide Step đã phục hồi & xác minh trên Pixel 3 XL

Đã khôi phục chuỗi hướng dẫn gốc `GuideRelation[1]` trên `NORMAL_PROFILE` (Server 1: `S1 Normal Revival (Lv1)`):

- **Tạo nhân vật & Mở đầu**: `RoleCreateScene` (`Player.NewPlayer`) -> `CgScene` phần 1 -> `BattleScript0000` (Mistress Centipede, Kagome, InuYasha, Grandma Kaede, NPC/MC) -> `CgScene` phần 2 -> `Guide/Talk/102`.
- **Chiến đấu & Triệu hồi tân thủ**:
  - `10211 -> 10212 -> 10213`: Vào Adventure -> ải `1-1` (`BattleScript1111`, rơi `Set Out · Dagger` `13010215`, lên Lv 2 `5/20`).
  - `103 -> 1051 -> 1052 -> 106`: Vào Summon -> Destiny Summoning (`HeroRecruit.Recruit([2, 1])` nhận `Ayame` `12011014` + 1000 Gold) -> Đóng kết quả & rời Summon.
  - `107 -> 1071 -> 109 -> 110`: Vào Team -> chọn Slot 2 -> `In formation` (`Slot.HeroCombat` đưa Ayame vào Slot 2) -> Đóng Team.
- **Màn 1-2, Rương đường đi & Boss 1-5**:
  - `111 -> 116 -> 117 -> 118`: Đánh `1-2` thật với Spine2D (thắng bằng chỉ số gốc: Slot 1 HP 448, Slot 2 HP 626) -> Victory Lv 3 (`5/30`) -> Confirm bảng lên cấp `UpgradeLayer`.
  - `1181 -> 1182`: Mở Road Box `111` (`Battle.DrawRoadBox([11, 111])`: nhận `Bronze Helmet` `13020215`, 100 HeroExp, 20 Diamond).
  - `119 -> 7600`: Đánh `1-3` (`BattleScript1113`, lên Lv 4 `5/40`, rơi 5x `Wooden Bead Necklace` `13040130`).
  - `7608..7612`: Đánh `1-4` thật (thắng ở HP 484 / 628, lên Lv 5 mở `Check in Monthly`) -> đánh `1-5` Boss (`Yura`, thắng lên Lv 6 `0/120`, nhận Jaken fragments & Breakthrough Stones) -> Perfect Clearance Chapter 1 -> mở khóa Chapter 2 (`Battle.GetNodeList([12])`).
- **Sang Chapter 2 & Chống lặp khi tắt/mở lại**:
  - Đã kiểm thử tắt hoàn toàn app (`am force-stop`) tại `2-1`, mở lại app vào Server 1: game vào thẳng Chapter 2 (`2-1`), không lặp lại tạo nhân vật/CG/Chapter 1.
  - Hoàn thành `2-1` (`1211`) và `2-2` (`1212`, HP còn lại 332 / 340) -> đạt **Lv 7**, tutorial chính kết thúc (`StepCountList["1"] = 919`) và kích hoạt tự nhiên popup mở khóa tính năng **Character Upgrading** (`FunctionOpenModel[7]` / Guide `17`).
- *Ghi chú bước ghép trang bị `7601..7607`*: Đã cài đặt đầy đủ RPC (`EquipCompose`, `EquipOneKeyCompose`, `OneKeyEquipCombat`, `OneKeyEquipLvUp`) và kiểm thử qua `test_emulator.py`. Trên client thật do `Avatar.RedDotInfo` chưa tổng hợp cờ đỏ `ModuleSub.eEquip`, `BattleLayer:correctGuideEventId()` tự chuyển mượt từ `7600` sang `7608` mà không bị kẹt.

---

## 3. Khảo sát dữ liệu cân bằng gốc từ Client EN 5.1.1 (P3)

| Hệ thống | File / RPC nguồn | Giá trị tìm được từ EN 5.1.1 | Độ tin cậy | Trạng thái Emulator | Chênh lệch | Cần phục hồi? |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- |
| **Tài nguyên tân thủ** | `Config/PlayerConfig.lua` | `initLv=1`, `initVip=0`, `initGold=100000`, `initDiamond=0`, `initHeroEXP=5000`, `initVIT=200`, `initSTA=20`, `initResource="1605,16050001,100\|\|1605,16050003,1"`, `maxPlayerLV=70` | Cao (A) | `NORMAL_PROFILE` khớp 100%; `DEBUG_PROFILE` giữ Lv 10, VIP 5, 8888 Diamond | Không (chủ đích tách 2 profile) | Đã phục hồi cho NORMAL |
| **Bảng Level / EXP nhân vật** | `Config/PlayerLvRelation.lua`, `VitConfig.lua` | `EXPTotal`: Lv1=0, Lv2=5, Lv3=25, Lv4=55, Lv5=95, Lv6=150, Lv7=270, Lv8=410, Lv9=570, Lv10=1175; Lv70=13,547,870. Công thức ải: `perUseNum=5`, `perGetEXPR=20000` -> `+10 * old_lv` EXP/trận | Cao (A) | Đã áp dụng chính xác ở `NORMAL_PROFILE`; `DEBUG` giữ +30 EXP | Không | Đã phục hồi |
| **Hero Base & Growth** | `Config/HeroModel.lua` (`202` tướng) | Male/Female MC (`12010001`/`12010004`): q=6, `HP=420`, `AP=60`, `DEF=20`, `RP=50`, `FSP=500`; InuYasha (`12011004`): q=18, `HP=896`, `AP=200`, `DEF=42`; Ayame (`12011014`): q=13, `HP=672`, `AP=150`, `DEF=32` | Cao (A) | Đọc trực tiếp từ `game_data.json` cho `_build_hero_instance` & `_compute_slot_property` | Không | Đã phục hồi |
| **Đột phá tướng (Step)** | `Config/HeroStepRelation.lua` (`42` mốc), `PlayerConfig` | `step=0` ở `classID=10` tăng 0, gold 20k + 50 stone; `classID=13` gold 30k + 100 stone; `attrUpR` tăng +0.5/step | Cao (A) | Đã trích xuất vào `game_data.json` | Chưa cài RPC `Hero.HeroStepUp` cho R2 (mở ở Lv 8) | Chuyển R3 |
| **Quái & Độ khó ải** | `Config/BattleNodeModel.lua` (`689` node), `BattleNodeGuidenpcRelation.lua` | Chương 11 (`1111..1115`): `dropGold` 30–55, `dropHeroExp` 15–30, `commonNPCAttrR` 11748–14656; Chương 12 (`1211..1217`): `dropGold` 35–70, `dropHeroExp` 20–35 | Cao (A) | Dùng nguyên công thức/node config gốc từ client | Không | Đã phục hồi |
| **Sát thương & Nộ khí** | `CSCommon/FightExpression.lua` (`139–147`), `AttackModel.lua` (`439` skill) | Thang Nộ `0..200`, tiêu hao skill = `100` (`Hero_MAX_RP_VALUE=200`). `hurtStrength = max(attackAP - victimDEF, 0.1 * attackAP)`; hệ số nộ skill `* (1 + (RP - needRP)/200)` | Cao (A/B) | Combat client chạy trực tiếp Lua engine gốc | Không | Đã phục hồi |
| **Rơi đồ & Rương ải** | `Config/BattleNodeDropRelation.lua` (`3,871`), `BattleRoadBoxRelation.lua` (`207`), `BattleChapterBoxRelation.lua` (`207`) | `1111`: `13010215` (`dropOdds=0`); RoadBox `111`: `20 Diamond + 13020215 + 100 HeroExp`; `1113`: 5x `13040130`; `1115`: Jaken fragment `15010025` + `16050001` | Cao (A) | Đã cài đặt (`dropOdds=0` first-clear + roll `1..10000`) | Không | Đã phục hồi |
| **Cường hóa & Ghép đồ** | `Config/EquipColorRelation.lua`, `EquipLvUpuseRelation.lua`, `EquipGroupActiveRelation.lua` | Ghép trắng -> lục (`colorLV=1`): tốn `1000` Gold + 5 đồ; LvUp trắng Lv0..9: `15..85` Gold; Lục Lv0..9: `30..165` Gold; Set 2 món `equipGroupID=22`: `+100 HP, +20 AP, +10 DEF` | Cao (A) | Đã trích xuất và triển khai vào `EquipCompose`, `EquipOneKeyCompose`, `OneKeyEquipLvUp`, `EquipLvUpForCount`, `_compute_slot_property` | Không | Đã phục hồi |
| **Gacha / Triệu hồi** | `Config/HeroRecruitModel.lua`, `CallequipOutoddsBRelation.lua` (`36` dòng) | Type 1 (Dream): dùng `16050003`; Type 2 (Destiny): 80 KC / CD 1380m (`outShowMain` 22 tướng); Type 3 (Spiritual): 280 KC / CD 2820m, tặng `16060005`. Gear: `200`/`1800` | Cao (A) | R2 cố định lần Destiny đầu ra `Ayame` (`12011014`) đúng luồng tutorial | Đầy đủ xác suất Banner/Pity chưa cần cho R2 | Giữ đơn giản, mở rộng R3 |
| **Mở khóa Module** | `Config/FunctionOpenModel.lua` (`25` mục), `Config/ModuleSubModel.lua` (`323` mục) | Lv5 Check-in (`2712`), Lv7 Hero Upgrade (`1101`), Lv8 Breakthrough (`1102`), Lv9 Seek Jade (`5200`), Lv12 Auto-push (`2206`), Lv14 Win Treasure (`2501`), Lv18 Elite (`2202`), Lv20 Duel (`2502`), Lv27 Guild (`3400`), Lv30 Gear Upgrade (`1403`) | Cao (A) | Server trả `ModulesInfo` mở cờ server; client tự khóa theo `openLv` | Không | Đã phục hồi |
| **VIP Model** | `Config/VipModel.lua` (`21` bậc `0..20`) | `VIP 0 = 0`, `VIP 1 = 60`, `VIP 2 = 360`, `VIP 3 = 860`, `VIP 4 = 1860`, `VIP 5 = 3360`, ..., `VIP 9 = 14860` | Cao (A) | `ResourceLedger.derive_vip_level()` tính VIP chặt từ `VipEXP` | `DEBUG` giữ cứng VIP 5 | Đã có nền tảng trong ledger |

---

## 4. Tách biệt hai hồ sơ & Giá trị Debug thay thế (P2)

- **`NORMAL_PROFILE` (`ServerId = 1` — `S1 Normal Revival (Lv1)`)**:
  - Lưu độc lập tại `server/saves/normal_profile.json` (tách biệt hoàn toàn `PlayerId` bắt đầu từ `"200001"`, tự tăng khi `--reset-normal` để tránh đụng cache `LocalData` trên Android).
  - Sau kiểm thử thực tế trên Pixel 3 XL (`DylanBes`, `PlayerId = "200002"`): đạt `Lv 7`, `Vip = 0`, `Gold = 101380`, `Diamond = 20`, `FAP = 3153`, `StepCountList["1"] = 919`.
- **`DEBUG_PROFILE` (`ServerId = 2` — `S2 Debug R1 (Lv10/VIP5)`)**:
  - Lưu độc lập tại `server/saves/debug_profile.json` (seed từ `server/save_state.json`, không sửa bản R1 gốc và giữ backup tại `server/backups/save_state_r1_20261118_022004.json`).
  - Giữ các giá trị debug phục vụ test nhanh: `PlayerId = "100001"`, `PlayerName = "InuYasha"`, `Lv = 10`, `Vip = 5`, `Gold = 50105`, `Diamond = 8888`, `FAP = 18500`, 4 tướng sẵn có, `StepCountList = {"1": 999}`.
- **Giới hạn giá trị suy luận / tạm thay thế trong R2**:
  - `Player.GetStepCountReward` sử dụng `reward_map` tối thiểu (`76001`, `1641`, `1602`) vì phần thưởng step đầy đủ nằm phía server gốc (`UNKNOWN`).
  - Lần quay `HeroRecruit.Recruit([2, 1])` đầu tiên cố định `12011014` (`Ayame`, nằm trong `HeroRecruitModel[2].outShowMain`) để khớp kỳ vọng tutorial.

---

## 5. Kết quả Regression & Kiểm thử (P0 & P5)

1. **Automated Unit & Protocol Tests (`python3 server/test_emulator.py`)** sau lần sửa cuối:
   - `test_01_server_list`: OK (trả đủ S1 Normal & S2 Debug).
   - `test_02_normal_profile_onboarding_and_tutorial_flow`: OK (Login Lv1/VIP0 -> NewPlayer -> GetInitData -> `ExtensionString.GuideInfo` -> 1-1 lên Lv2 -> Recruit Ayame & HeroCombat -> 1-2 lên Lv3 & RoadBox -> 1-3 rơi 5 dây chuyền -> EquipOneKeyCompose -> OneKeyEquipCombat -> OneKeyEquipLvUp -> SlotFormation).
   - `test_03_debug_profile_regression_and_isolation`: OK (kiểm tra S2 Debug tách biệt hoàn toàn với S1 Normal).
   - `test_04_economy_audit_ledger`: OK (chặn `HP`/`AP`/`DEF`/`DAM`/`DAMADD`, chặn âm tiền, chặn trùng `idempotency_key`, tính VIP từ `VipEXP`, ghi JSONL).
   - `test_05_real_apk_obb_assets_served`: OK.
   - Tổng kết: **5/5 tests PASSED** (`0.651s`).
2. **Web PoC syntax check**: `node --check poc/web_poc/app.js` exit code `0`.
3. **On-device Pixel 3 XL (`com.heitao.inuyasha.guge`)**:
   - Đã chạy thông suốt toàn bộ `NORMAL_PROFILE` từ tạo nhân vật (`DylanBes`), qua `1-1` -> `Summon Ayame` -> `Team Slot 2` -> `1-2` -> `Road Box` -> `1-3` -> `1-4` -> `1-5 Boss` -> mở Chương 2 -> tắt/mở lại không lặp tutorial -> `2-1` -> `2-2` -> đạt `Lv 7` & popup mở khóa nâng cấp tướng (`FunctionOpenModel[7]`).
   - Đã chuyển sang `S2 Debug R1 (Lv10/VIP5)` trực tiếp trên giao diện chọn server và xác minh hoạt động độc lập, không ảnh hưởng `normal_profile.json`.

---

## 6. Cập nhật APK & Server

- **`poc/patch_android_apk.py`**:
  - Bổ sung giải mã/mã hóa XXTEA chuẩn Cocos2d-x (`MQKK`, key `cf68b641311b5201`) để vá đúng 3 hằng số guard lỗi thời trong `Home/HomeScene.luac` (`heroCount > 2` -> `> 1`, `formationHeroCount < 3` -> `< 2`) và `Guide/GuideMng.luac` (`heroCount > 2` -> `> 1`), giữ nguyên hoàn toàn `GuideRelation.lua` gốc. Đã build & ký lại `analysis/patched/com.heitao.inuyasha.guge_revival.apk`.
  - Bản gốc trong `originals/` giữ nguyên quyền `chmod 444`.
- **`server/extract_game_data.py` & `server/game_data.json`**:
  - Bổ sung trích xuất toàn bộ bảng cân bằng & config (`player_config`, `vit_config`, `sta_config`, `hero_config`, `callequip_config`, `player_lv`, `hero_lv`, `hero_step`, `equip_color`, `equip_lv_up`, `equip_group`, `node_drops`, `road_boxes`, `chapter_boxes`, `module_subs`, `hero_recruit`, `vip_model`, `attrtree_slots`).
- **`server/emulator.py`**:
  - Tách `ProfileStore` + `GameEmulatorState` cho `normal` (`ServerId=1`) và `debug` (`ServerId=2`), hỗ trợ `ExtensionString.GuideInfo`, công thức EXP/Level/Drop/Equip/Formation/RoadBox, và sửa `Equip.EquipLvUpForCount` trả về `LvUpList`.
- **`server/economy_audit.py`**:
  - Thiết lập nền tảng sổ cái giao dịch tài nguyên (`ResourceTransaction`, `ResourceLedger`).

---

## 7. Cơ chế tự xây lại & Thiết kế nền tảng Admin

### Cơ chế phải tự dựng lại phía server
- Hệ thống lưu/tải đa hồ sơ và persistence (`ProfileStore`, tách `PlayerId` + save file).
- Logic tiến trình chiến dịch, mở khóa node/chapter, mở rương (`RoadBox` / `ChapterBox`), gộp đồ (`EquipCompose`), nâng cấp trang bị (`OneKeyEquipLvUp` / `EquipLvUpForCount`), xếp đội hình (`Slot.HeroCombat` / `SlotFormation`), tính lực chiến `Property` & `FAP`.
- Logic đối chiếu rớt đồ (`BattleNodeDropRelation`), EXP/Level-up theo `VitConfig` & `PlayerLvRelation`.

### Nền tảng thiết kế Admin & Ledger (`server/economy_audit.py`)
- **Mô hình giao dịch (`ResourceTransaction`)**: gồm `tx_id` (UUID), `account_id`, `profile`, `resource_type` (`Gold`, `Diamond`, `HeroEXP`, `HeroCoin`, `VIT`, `STA`, `VipEXP`, `EXP`, hoặc grant item/hero/equip), `amount`, `balance_after`, `source` (lý do bắt buộc), `idempotency_key` (chống áp dụng trùng `DuplicateTransactionError`), `timestamp_unix` / `timestamp_iso`, `actor`, `metadata`.
- **Audit Log**: ghi nối tiếp JSONL bất biến (`server/saves/economy_audit.jsonl`).
- **Ràng buộc chống phá vỡ cân bằng**: cấm tuyệt đối chỉnh sửa trực tiếp các khóa chỉ số chiến đấu (`DISALLOWED_BALANCE_KEYS = {"HP", "AP", "DEF", "DAM", "DAMADD", "DAMADDR", "DAMCUT", "DAMCUTR"}`); cấp VIP bắt buộc dẫn xuất từ `VipEXP` theo bảng `VipModel` (`derive_vip_level`); cấm âm số dư.
- **Triển khai sau này**: công cụ quản trị chỉ binding `127.0.0.1` / LAN nội bộ có token xác thực, tuyệt đối không mở public và không gắn cổng thanh toán thật.

---

## 8. Đề xuất Scope Round R3

1. Bổ sung `Avatar.RedDotInfo` để bật hoàn chỉnh hướng dẫn ghép & mặc trang bị (`7601..7607`) nếu muốn trải nghiệm Forge ngay trong Chapter 1.
2. Triển khai các tính năng mở ở Lv 7–15: `Hero.HeroLvUp` (`1101`), `Hero.HeroStepUp` (`1102`), `Jade / Seek the Jade` (`5200`), `Daily Check-in` (`2712`), `Chapter.DrawBox` (`Star Box` kiểm thử thực tế trên máy).
3. Triển khai giao thức Gacha chuẩn theo bảng tỷ lệ / Pity (khi mở rộng sang `HeroRecruit` nâng cao), chuẩn bị đánh giá tích hợp đa ngôn ngữ/nền tảng (bao gồm tài nguyên bản Việt Nam nếu được chọn).
