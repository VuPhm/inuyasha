# R3_REPORT.md — InuYasha: Seek Jade Revival (Round R3)

Báo cáo tổng kết Round R3 (**VN-First Recovery, Gameplay Fidelity & Progression Restoration**) trên client Việt Nam `com.cmn.inuyasha` (v5.0.4.98) chạy với Python server emulator tại `/Users/vup/Documents/agy/inuyasha` trên **Google Pixel 3 XL (Android 12, Wireless ADB)**.

---

## 1. Quyết định nền tảng & Đánh giá VN vs EN (`Phase A`)

Kết luận chính thức: **`SWITCH VN`** (chuyển sang `com.cmn.inuyasha` 5.0.4.98 làm client mặc định cho emulator), đã trình bày chi tiết kèm bằng chứng trong [VN_MIGRATION_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/VN_MIGRATION_REPORT.md).

- **Checkpoint EN bất biến**: `checkpoint-en-r2` (commit `fed435c`) và thư mục `server/backups/en_r2_stable_checkpoint/` được giữ nguyên vẹn; `originals/` giữ quyền read-only (`chmod 444`).
- **Bản VN mặc định trong R3**:
  - APK gốc tách từ `originals/vn/com.cmn.inuyasha_5.0.4.98.xapk` (`210,162,212` bytes, SHA256 `0fa2d057367c8139ebb58891223d157aa3ddda9638bdccbde48175b2324ac68c`), giải mã `1,148` file `.luac` vào `analysis/vn/decompiled_src/`.
  - Bản patch Android 12 [com.cmn.inuyasha_revival.apk](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/patched/com.cmn.inuyasha_revival.apk) (SHA256 `4872d45e985ca4e9df2ee95c083014eba8b3dded4edca36494df8a42fdb89672`) dựng từ [patch_vn_apk.py](file:///Users/vup/Documents/agy/inuyasha/poc/patch_vn_apk.py) xử lý `assets/libs.apk` `Stub!`, trỏ domain về LAN emulator và vá guard tutorial `GuideMng`/`HomeScene`.
  - [extract_game_data.py](file:///Users/vup/Documents/agy/inuyasha/server/extract_game_data.py) đọc `Config` VN mặc định (hỗ trợ `--client vn|en`), xuất `server/game_data.json` gồm `204` tướng, `441` đòn đánh/kỹ năng, `70` chương thường (`689` ải), `65` chương Ác Mộng (`639` ải), `34` bản ghi guide NPC hợp lệ, `1,001` mốc `AttrtreeModel`, `14` slot `AttrtreeSlotRelation`, cùng các bảng `Explore*` và `BattleConfig`.
  - `AssetArchive` trong [emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py) đọc asset từ APK/OBB VN trước rồi fallback sang EN.

---

## 2. Phục hồi Hệ thống Chiến đấu (`Phase B`)

### 2.1 Kiến trúc client-server gốc xác minh từ Lua

Client APK chứa trọn bộ engine tính toán chiến đấu xác định (`deterministic`) dùng chung giữa client và server cũ trong `analysis/vn/decompiled_src/CSCommon/`:

1. [ServerInterface.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/CSCommon/ServerInterface.lua): `ConvertDataToBattleData` và `CheckBattleResult(string_server, string_client)` chạy lại mô phỏng bằng cùng `FightInfo.FightObjs` (`Heros` 12 vị trí `[1..6]` đồng minh + `[7..12]` địch, `TeamData`, `Pets`, `RandNum`, `IsPVP`).
2. [BattleCalc.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/CSCommon/BattleCalc.lua): Thứ tự ra đòn PVE của ta `mPVEHeroAttackFriendsOrder = {1,2,3,4,5,6}`, địch `{9,8,7,12,11,10}`; xử lý tốc độ (`Fsp` trong `TeamData` quyết định đội đi trước), tối đa 30 lượt/wave (`Lượt X/30`), điều kiện thắng/thua khi toàn bộ `Heros` một bên có `HP <= 0`.
3. [FightExpression.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/CSCommon/FightExpression.lua):
   - **Bàn tròn 100 điểm** (`Rand ∈ [0, 99]`): Né (`DOD - HIT + 100 >= 0`), Bạo (`CRI - TEN`), Đỡ (`BLO - BOG`), còn lại là đánh thường.
   - **Tấn công & Phòng thủ thực tế**: `attackAP = AP * (apr + 1)`, `victimDEF = DEF * (defr + 1)`, `hurtStrength = max(attackAP - victimDEF, attackAP * 0.1)`.
   - **Kỹ năng Nộ (thang `0..200`)**: `valueOfOrgHurt = hurtStrength * attackFactor * (1 + (attackHeroRP - skillNeedRP) / 200)` khi dùng kỹ năng Nộ; đánh thường dùng `hurtStrength * attackFactor`.
   - **Sát thương chuẩn, Đỡ, Bạo kích**:
     - `NormalHurt = valueOfOrgHurt * max(1 + (damaddr - damcutr) + countryHurt, 0.01)`
     - Đỡ: `max(ceil(NormalHurt * 0.5), 1)`
     - Bạo kích: `max(ceil(NormalHurt * (1.5 + (CRID - TEND) / 100)), 1)`
     - Sát thương cuối: `-max(valueRet + (damadd - damcut), 1)` (hồi máu `attackType == 1` tính theo `attackAP * attackFactor`).
4. [BattleVerify.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/ComBattle/BattleVerify.lua): Kết thúc trận client đóng gói `verifyData` (`version`, `hp` cuối từng wave theo `PosId`) gửi kèm lên `Battle.Fight`.

### 2.2 Những gì còn thiếu trong client & Cách xử lý trong Emulator

- **Dữ liệu đội hình quái theo ải (`BattleNodeGuidenpcRelation.lua`)**: Khảo sát cho thấy bảng này có `3,816` entry nhưng chỉ `34` dòng có `heroModelID != 0` — chuyên dùng cho các trận hướng dẫn kịch bản (`1111`, `1211`, `1216`, `1311`... qua `BattleGuider.lua`). Danh sách đội hình quái chuẩn của `689` ải thường nằm ở DB server cũ (không kèm trong APK/OBB).
- **Cách dựng trận đấu trong `emulator.py`**:
  - `_hero_fight_obj` lấy đúng chỉ số Slot đã tính (`Slot["Property"]` gồm Lv, Step, `RebornStep`, trang bị, bộ trang bị và sao Ngộ Đạo `AttrtreeModel`), **không buff ảo hay giảm sức mạnh quái ở `NORMAL_PROFILE`** (chỉ giữ nhánh riêng `self.profile_name == "debug"` cho `DEBUG_PROFILE`).
  - `_build_enemy_wave` & `_rpc_get_fight_info` sinh đúng `fightRound` số wave (`FightObjs` dài bằng `max(1, fightRound)`, ví dụ `2-7` Sesshomaru có 2 wave), đặt boss `node_cfg["pic"]` tại wave cuối, đặt lính phụ từ `HeroModel` cùng cấp tiến độ `base_lv` (`Ch 11: max(1, (node_idx+1)//2)`; `Ch 12+: (ch_id-11)*4 + node_idx`) và nhân `hp_mult/ap_mult/def_mult = diff_mult`.
  - `_verify_battle_payload` kiểm tra tính nhất quán `verifyData["hp"]` cuối trận (`ally_alive` vs `enemy_alive` khớp `won`) khi client gửi payload.

---

## 3. Phục hồi Hệ thống Chấm sao, Rương & Ngộ Đạo (`Phase C`)

### 3.1 Vì sao thắng ải Chương 1–3 chỉ ra 1 sao?

Kiểm tra `Config/BattleNodeModel.lua` (`689` ải thường) và `Adventure/BattleDropLayer.lua` chứng minh đây **không phải bug UI**, mà là thiết kế gốc:
- Chương `11..19` (Chương 1–9): mọi ải đều có `starCount = 1` (chỉ có 1 cấp độ `Dễ` = `1★`).
- Chương `20..22`: có `starCount = 2` (`Dễ 1★`, `Thường 2★`).
- Chương `23+`: có đủ `starCount = 3` (`Dễ 1★`, `Thường 2★`, `Khó 3★`).
- Riêng phó bản Ác Mộng (`NightmareNodeModel`, `639` ải) chấm `1..6★` theo `leftHero` (`BattleWinHintLayer`).

### 3.2 Quy tắc độ khó, nhận thưởng & sửa lỗi client/server

- **Scale quái theo độ khó**: `_difficulty_multiplier` trả về `1.0` cho `1★` (`Dễ`), `commonNPCAttrR / 10000` cho `2★` (`Thường`, ví dụ `1.3224x` tại `2311`), và `hardNPCAttrR / 10000` cho `3★` (`Khó`, ví dụ `1.6684x` tại `2311`).
- **Mở tuần tự & giữ sao cao nhất**: `_execute_battle_clear` khóa sao thắng tối đa theo mốc `min(max_node_star, prev_star + 1)` và cập nhật `node_st["StarCount"] = max(prev_star, earned_star)`; tính lại `Chapter.StarCount` và `BattleInfo.StarCount`.
- **Sửa bug rương chương `IfDrawBoxA/B/C`**: Trước R3, `_make_chapter_state` khởi tạo `IfDrawBoxA/B/C = 0`. Trong Lua (`BattleLayer.lua`), `0 == false` và `not 0` đều **sai**, khiến client hiểu nhầm trạng thái rương sao. Đã đổi sang Python `bool` (`False`/`True`, kèm migrate ở `_normalize_loaded_state`) và kiểm tra điều kiện `StarCount >= boxNeedStar` + chống nhận trùng trong `Battle.DrawBox` và `Battle.OneKeyDrawBoxs`.
- **Quét ải (`ConFight` / `ResetCount`) & Ngộ Đạo (`LightenStar`)**:
  - `Battle.ConFight` chạy lặp nhiều lượt qua `_execute_battle_clear` (kiểm tra đã có `StarCount >= starLv` và đủ `VIT`), hỗ trợ cả tiêu vật phẩm `BattleConfig.conFightUseResource = "1605,16050011,1"`.
  - `LightenStar.*` (`GetLightenStarInfo`, `LightenStar`, `LightenStarForOneKey`) kiểm tra đủ `StarCount` và `Gold` theo `AttrtreeModel` (`1,001` mốc), tăng `StarId` và cộng dồn chỉ số `431 AP` / `432 HP` / `433 DEF` vào tất cả Slot (`_get_slot_star_bonuses`).

---

## 4. Onboarding tới Lv 10+ & Cân bằng Kinh tế (`Phase D & E`)

### 4.1 Luồng mở khóa & Guide theo `GuideRelation.lua` + `FunctionOpenModel.lua`

| Cấp độ | Hướng dẫn / Mở khóa gốc | ID Config | Hành vi đã xác minh trên VN Client + Emulator |
| :--- | :--- | :--- | :--- |
| **Lv 1–2** | Tân thủ đầu game: Tạo nhân vật -> CG -> `BattleScript0000` -> `1-1` -> Triệu hồi (`HeroRecruit.Recruit`) -> Đội hình (`Slot.HeroCombat`) -> Trang bị -> `1-2..1-5` | `GuideRelation[1]` | Chạy liền mạch trên tài khoản sạch `200010`; `IsNewPlayer=1` ban đầu và lưu `StepCountList` qua `Player.AlterPlayerStepCount` để không lặp tutorial khi restart. |
| **Lv 5** | Điểm danh tháng & Quà cấp | `FunctionOpenModel[5]` (`2712`), `ModuleSub[2800]` | Mở icon tương ứng; `GuideRelation[951..965]` kích hoạt thoại cốt truyện khi qua ải (`1111`..`1311`, `1314`...). |
| **Lv 7** | **Tăng cấp Tướng (`Tăng Lv`)** | `GuideRelation[17]`, `FunctionOpen[7]` (`1101`) | Kích hoạt bàn tay chỉ dẫn -> `Hero.HeroLvUp` nâng `Ayame` lên Lv 11 (`HeroLvRelation` + giới hạn `max(playerLv*2, 10)`, tiêu `HeroEXP` & `Gold`). |
| **Lv 8** | **Đột phá Tướng (`Đột Phá`)** | `GuideRelation[2]`, `FunctionOpen[8]` (`1102`) | Kích hoạt bàn tay chỉ dẫn -> `Hero.HeroStepUp` (`HeroStepRelation`, tiêu Đá Đột Phá `16050001` + `Gold`, mở thiên phú +1). Sửa `Slot["FAP"]` giúp `HeroBreakInforLayer` chạy sạch. |
| **Lv 9** | **Tầm Ngọc (`Explore`)** | `GuideRelation[3]`, `FunctionOpen[9]` (`5200`) | Mở `Tầm Ngọc` (`Explore.GetInfo`, `Explore.Explore` tiêu lượt & hồi theo `ExploreConfig`: `fightNumStart=15`, `fightNumMax=25`, `critNum=+5`/Lv up). |
| **Lv 10** | Nhiệm vụ giờ | `ModuleSub[4700]` | Đạt **Lv 10** tự nhiên qua ải `3-4` (`CHÚC MỪNG TĂNG LV Lv.9 -> Lv.10`), tích hợp đầy đủ phần thưởng `PlayerLvRelation` (`rewardDiamond`, `rewardSTA`, `rewardResource`). |
| **Lv 11–20** | Tuần lễ vàng (`11`), Auto Qua Ải (`12`), Tầm Bảo (`14`), **Ngộ Đạo (`16`, `2302`)**, Tinh Anh / Yêu Vương (`18`), Quét 10 lần (`20`, `2204`) | `FunctionOpenModel` & `ModuleSubModel` | Sẵn sàng backend RPC (`LightenStar.*`, `Battle.ConFight`) khi người chơi cày tiếp từ Lv 10 lên Lv 12–20. |

### 4.2 Phân loại mức độ phục hồi dữ liệu & Logic

| Hệ thống | Nguồn | Trạng thái | Ghi chú kiểm chứng |
| :--- | :--- | :--- | :--- |
| Nhân vật, kỹ năng, trưởng thành (`HeroModel`, `HeroLvRelation`, `HeroStepRelation`, `AttackModel`) | VN APK `Config/*.lua` | **`VERIFIED ORIGINAL`** | Trích xuất trực tiếp `204` tướng, `441` skill, `600` mốc Lv, `57` mốc Step. |
| Cấp độ, Thể lực, Kinh nghiệm, Hộp sao/đường (`PlayerConfig`, `PlayerLvRelation`, `VitConfig`, `BattleNodeModel`, `BattleRoad/ChapterBoxRelation`) | VN APK `Config/*.lua` | **`VERIFIED ORIGINAL`** | Áp dụng `maxPlayerLV=80`, `perUseNum=5`, `perGetEXPR=20000`, `initResource` chuẩn. |
| Công thức tính sát thương / Né / Bạo / Đỡ / Nộ | `CSCommon/FightExpression.lua` | **`VERIFIED ORIGINAL`** | Khớp logic chạy trong Spine2D engine của client VN. |
| Danh sách RPC, schema `Player`/`Hero`/`Slot`/`Battle`/`Explore`/`LightenStar` | `NetworkResData.lua`, `ServerInterface.lua`, `XunYuScene.lua`, `LightenStarScene.lua` | **`VERIFIED ORIGINAL`** + **`RECONSTRUCTED`** | Client cung cấp đủ chữ ký RPC; backend tái tạo phản hồi và tính toán lưu state (`server/saves/*.json` + `economy_audit.py`). |
| Đội hình quái chi tiết cho `689` ải thường & tỷ lệ drop chi tiết theo server | Không có trong client (`BattleNodeGuidenpcRelation` chỉ có `34` trận script) | **`MISSING`** -> **`APPROXIMATED`** | Dùng `pic` boss gốc + mob chuẩn theo `base_lv`, scale chính xác theo `commonNPCAttrR` / `hardNPCAttrR` và số lượt `fightRound`; tách hoàn toàn khỏi `DEBUG_PROFILE`. |
| Các tính năng phụ unlock cao hơn (`Tầm Bảo`, `Ải Tinh Anh`, `Yêu Vương`, `Công Hội`, `Shop Bí Ẩn`, Chat TCP 8081) | Mở khóa từ Lv 14–40 | **`MISSING`** (ngoài phạm vi R3) | Đang giữ stub an toàn ở danh sách RPC tối thiểu để không lỗi `HomeScene`. |

---

## 5. Tổng hợp RPC trong `server/emulator.py`

- **Đã phục hồi & hoạt động**:
  - `Player`: `Player.Login`, `Player.Login_ForTest`, `Player.NewPlayer`, `Player.GetInitData`, `Player.SyncAvatarInfo`, `Player.AvatarInfo`, `Player.AlterPlayerStepCount`, `Player.GetStepCountReward`
  - `Hero` & `HeroRecruit`: `HeroRecruit.RecruitInfo`, `HeroRecruit.Recruit`, `Hero.HeroLvUp`, `Hero.HeroStepUp`
  - `Slot` & `Equip`: `Slot.HeroCombat`, `Slot.OneKeyEquipCombat`, `Slot.SlotFormations`, `SlotFormation.GetFormation`, `SlotFormation.Change`, `Equip.EquipCompose`, `Equip.EquipOneKeyCompose`, `Equip.OneKeyEquipLvUp`, `Equip.EquipLvUpForCount`
  - `Battle`: `Battle.GetBattleInfo`, `Battle.GetNodeList`, `Battle.GetFightInfo`, `Battle.Fight`, `Battle.ConFight`, `Battle.ResetCount`, `Battle.DrawRoadBox`, `Battle.DrawBox`, `Battle.OneKeyDrawBoxs`
  - `Explore` & `LightenStar`: `Explore.GetInfo`, `Explore.Explore`, `Explore.OneKeyExplore`, `Explore.BuyExploreNum`, `Explore.DrawDailyReward`, `LightenStar.GetLightenStarInfo`, `LightenStar.LightenStar`, `LightenStar.LightenStarForOneKey`
- **Stub tối thiểu cho `HomeScene` (chưa phục hồi logic đầy đủ)**:
  - `Notice.GetNoticeList`, `Enemy.GetEnemyList`, `TraderInfo.GetInfo`, `OnlineReward.OnlineRewardInfo`, `YiYuan.GetInfo`, `TeambattleInfo.GetInviteInfo`, `GiftLogin.SignInfo`, `Reward.Rewars`

---

## 6. Kết quả kiểm thử (Automated + Live Pixel 3 XL)

1. **Kiểm thử tự động**:
   - `python3 /Users/vup/Documents/agy/inuyasha/server/test_emulator.py`: **8/8 tests PASSED (`OK`)**, bao gồm `test_06_vn_config_extraction_and_combat_scaling`, `test_07_star_rating_replay_con_fight_and_draw_box` (kiểm chứng `1★`, `2★`, `3★`, replay tăng sao và chặn nhảy cóc, `Battle.ConFight`, `Battle.DrawBox`), và `test_08_hero_lv_up_step_up_explore_and_lighten_star_to_lv10` (kiểm chứng `HeroLvUp`, `HeroStepUp` + đồng bộ `Slot["FAP"]`, `Explore`, `LightenStar`, và progression hữu cơ lên `Lv >= 10`).
   - `node --check /Users/vup/Documents/agy/inuyasha/poc/web_poc/app.js`: exit code `0`.
2. **Kiểm thử trực tiếp trên Google Pixel 3 XL (`com.cmn.inuyasha`, `PlayerId "200010"`, nhân vật `"OlinaHugh"`)**:
   - Chạy liền mạch từ tạo nhân vật `VIP 0`, prologue `Omukade`, qua `1-1..1-5` -> chiêu mộ `Ayame` (`5★`) -> lắp đội hình -> thắng sát nút `2-2` (`Suzaku`, sau khi ghi nhận thất bại `THẤT BẠI` thực tế khi thử đi ải yếu) -> hoàn thành **Chương 1 (`5/5 ★ HOÀN MỸ`)** & **Chương 2 (`7/7 ★ HOÀN MỸ`)** bằng `DrawRoadBox`, `DrawBox`, `OneKeyDrawBoxs`.
   - Kích hoạt và hoàn tất đủ hướng dẫn `Lv 7 Hero.HeroLvUp` (`Ayame` -> Lv 11), `Lv 8 Hero.HeroStepUp` (`OlinaHugh +0 -> +1`, và sau khi bổ sung `Slot["FAP"]` tiếp tục đột phá `Ayame +0 -> +1` với animation `HeroBreakInforLayer` không còn `LUA ERROR`), `Lv 9 Explore.Explore` (`Tầm Ngọc`), trang bị & cường hóa bộ 4 món `Lv 20` (`OneKeyEquipCombat` + `OneKeyEquipLvUp`).
   - Đánh `2-7` (`fightRound = 2`) mở Chương 3, đánh `3-1..3-4` đạt **Lv 10** (`CHÚC MỪNG TĂNG LV Lv.9 -> Lv.10`, `7/535 EXP`, `FAP 7160`, `16 ★`, `Gold 50,495`, `Diamond 115`).
   - Force-stop `com.cmn.inuyasha` (`am force-stop`) và mở lại: vào thẳng `HomeScene` Lv 10 đúng trạng thái đã lưu, không lặp tutorial.
   - `server/saves/debug_profile.json` được khôi phục nguyên trạng `100001 InuYasha Lv 10 VIP 5`.

---

## 7. Checkpoint & Hướng dẫn chạy / Rollback

- **Khởi chạy server VN mặc định (`NORMAL_PROFILE` Lv 10 / `DEBUG_PROFILE` tách biệt theo server login)**:
  ```bash
  python3 /Users/vup/Documents/agy/inuyasha/server/emulator.py --host 0.0.0.0 --port 8080 --profile normal
  ```
- **Checkpoint R3 ổn định**: Thư mục `server/backups/vn_r3_stable_checkpoint/` + git tag `checkpoint-vn-r3`.
- **Quay lui về EN R2 nếu cần**: `git checkout checkpoint-en-r2` hoặc khôi phục từ `server/backups/en_r2_stable_checkpoint/`.
