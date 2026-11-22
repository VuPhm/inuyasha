# Gói Bàn Giao Triển Khai Cho Model Tầm Trung (`Medium-Model Handoff`)

**Baseline:** `checkpoint-vn-r7.21` (`2b91941`, APK 840) | **Ngày lập:** 22/11/2026 (UTC+7).
**Mục tiêu:** Chia nhỏ backlog thành các gói độc lập, rõ ràng đến từng file, dòng code, công thức và tiêu chí nghiệm thu để **model tầm trung** thực thi an toàn mà không phải tự reverse engineering lại từ đầu; chỉ giữ các nhiệm vụ đòi hỏi suy luận engine sâu cho **Neon**.

---

## 1. Phân loại độ phức tạp & Phân bổ Model

| Hạng mục | Nhiệm vụ cụ thể | Loại công việc | Khuyến nghị Model |
|---|---|---|---|
| **Gói 1 — `TASK-M01` *(ĐÃ XONG R7.22A)*** | Khôi phục chỉ số bị sót (`EquipGroup` 13 thuộc tính + `TreasureStep` `410/411` + `HeroStepCheer` + `FashionPrRelation`) & `DailyTask #12/#26` | **Cơ học / Coding thông thường** (rủi ro thấp) | **Trung bình** *(Đã xong)* |
| **Gói 2 — `TASK-M02` *(ĐÃ XONG R7.22B)*** | Khôi phục Tiến hóa Nhân Vật Chính (`AttrtreeHeromodelRelation`), Drop Tinh Anh (`ElitebattleNodeDropRelation`), Phí Reset Ải (`BattleResetUseRelation`), và kiểm chứng `BossBattle` / `LuckbossValueShopModel` | **Coding thông thường** (rủi ro thấp–trung bình) | **Trung bình** *(Đã xong)* |
| **Gói 3 — `TASK-M03` *(ĐÃ XONG R7.22C)*** | Khôi phục công thức FAP chuẩn (`HP + 10*AP + 10*DEF`) + Port PRNG `CreateRandom` + Sửa chọn mục tiêu AI (`eHPMin`, `eRPMax/Min`, fallback cột gần nhất) + Khắc chế phe (`countryHurt`) | **Coding thông thường có đối chứng Lua** (rủi ro trung bình) | **Trung bình** *(Đã xong)* |
| **Gói 4 — `TASK-M04` *(ĐÃ XONG R7.22D)*** | Khôi phục Khảm, Tháo & Hợp Linh Thạch / Đá (`Slot.GemCombat`, `GemOneKeyCombat`, `Gem.GemCompose`, `GemOneKeyCompose` + cộng chỉ số Đá vào `Property`) | **Coding thông thường** (rủi ro thấp–trung bình) | **Trung bình** *(Đã xong)* |
| **Gói 5 — `TASK-M05` *(ĐÃ XONG R7.23)*** | Khôi phục Buff Chiến Đấu Lát 1A (Độc `602` + `modifyAddValue`, điều kiện `refAttr=602`, Hút máu `type=7`, Buff hàng trước/sau `tE=3/4`, Giảm hồi máu `407`, `type=2 attr=0` Tất trúng/Miễn bạo, `attr=201` trừ/hồi HP) | **Coding chuẩn có đối chiếu Lua** | **Trung bình** *(Đã xong)* |
| **Gói 6 — `TASK-N01` *(ĐÃ XONG R7.24)*** | Khôi phục Buff Chiến Đấu Lát 1B (`ContinuousAttack` `9002/9003/9005`, `9004`, `9006 + 707`, Hồi sinh/Tử vong `type=9`, Bất tử `14060000`, Khiên `601`, `9007`, `type=0`, Boss `10090000`) + Mở BDD Tầng 24–26 (`48/51` ải) | **Suy luận phức tạp / Đồng bộ State Engine** | **Mạnh (Neon)** *(Đã xong)* |
| **Gói 7 — `TASK-M06` *(ĐÃ XONG R7.25)*** | Khôi phục Bảng Xếp Hạng Chung (`LeaderBoard`), `Goods.GoodsSell`, `Player.AlterPlayerName/HeadId`, `Treasure.TreasureCompose` + Kiểm chứng đóng 9 modal nghi vấn & 5 file `LoadingWait` (false positive) | **Cơ học / Coding thông thường** | **Trung bình** *(Đã xong)* |
| **Gói 8A — `TASK-N02A` *(ĐÃ XONG R7.26)*** | Phó Bản Ác Mộng (`Nightmare` 65 chương / 639 ải, 12 RPC thật), Nền `RebornGoods (2701)` / `RebornCoin (1128)`, & Cân bằng Wave Chiến dịch `Ch 12–80` | **Thiết kế hệ thống lớn & Cân bằng** | **Mạnh (Neon)** *(Đã xong)* |
| **Gói 8B — `TASK-N02B` *(ĐÃ XONG R7.27)*** | Chuyển Sinh (`RebornInfo` 5 RPC + `RebornShop` 3 RPC + `HeroRebornCheer` + `RebornLvActiveModel` + `11 Tuyệt Kỹ UAID`) & Mở 3 ải Tầng 27 BDD (`51/51`) | **Thiết kế hệ thống lớn & Cân bằng** | **Mạnh (Neon)** *(Đã xong)* |
| **Gói 9 — `REC-P2-02` *(ĐÃ XONG R7.28)*** | Trùm Tăng Cấp / Thần Khí (`EquipArtifactRelation` 1.104 mốc + `SuccessTarget #37..41`) & Triệu Hồi Trang Bị Thường (`Callequip` 2 RPC + `4416`/`4419` + `SuccessTarget #12`) | **Coding chuẩn có đối chiếu Lua** | **Đã xong (`R7.28`)** |
| **Gói 10 — `REC-P2-03` *(ĐÃ XONG R7.29)*** | Kho Vàng (`GGZJ.*` 8 RPC, 4 bảng VN) & Đấu Võ Đại Hội (`Gddh.*` 8 + `GddhShop.*` 2 RPC, 6 bảng VN) + `GDDHCoin (1119)` / `RawGold (2112)` + `RewardCenter` + `4414`/`4415` + `DailyTask #6/#9` + `SuccessTarget #13/#30` + `ActiverankingModel #7/#9` | **Coding chuẩn có đối chiếu Lua** | **Đã xong (`R7.29`)** |
| **Gói 11 — `REC-P2-04A` *(ĐÃ XONG R7.30)*** | Bạn Bè (`Friend.*` 5, `FriendMessage.*` 9, `Enemy.*` 3) & Hộp Thư (`PlayerEmail.*` 2) — 2 chiều S1 + 24 NPC, STA hằng ngày, `DailyTask #11` (`23/25`), chiến báo `PVP`/`Gddh`/`BossBattle`, `Teambattle` & chấm đỏ `1700/1701/1900..1903` | **Coding chuẩn có đối chiếu Lua** | **Đã xong (`R7.30`)** |

---

## 2. Chi Tiết Các Gói Nhiệm Vụ Bàn Giao

---

### `TASK-M01` *(ĐÃ TRIỂN KHAI Ở R7.22A)* — Khôi Phục Chỉ Số Bộ Trang Bị, Tiến Giai Bảo Vật, Cổ Vũ, Duyên Thời Trang & DailyTask `#12/#26`

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.22A** (`server/test_r722a.py`).
- **Mục tiêu:** Cộng đầy đủ toàn bộ chỉ số gốc VN vốn đang bị bỏ sót trong `_compute_slot_property` và nối 2 hook nhiệm vụ ngày (`#12`, `#26`).
- **Mức ưu tiên:** `P0` / `P1`.
- **Các file đã đối chiếu & sử dụng:**
  - `server/extract_game_data.py`, `server/game_data.json`
  - `server/emulator.py` (`_fashion_pr_bonuses`, `_hero_step_cheer_bonuses`, `_compute_slot_property`, `_rpc_change_formation`, `_rpc_glory_lv_up`, `_rpc_glory_lv_up_one_key`)
  - `server/r79_event_handlers.py` (`_rpc_trader_buy_goods`)
  - `analysis/vn/decompiled_src/Config/HeroStepCheer.lua`, `FashionPrRelation.lua`, `QualityModel.lua`, `Formation/PartnerCheerLayer.lua` (`L45-L200`)
- **Bằng chứng & Logic VN gốc đã xác minh & triển khai:**
  1. `EquipGroupActiveRelation` (`game_data["equip_group"]`): đã nối đủ toàn bộ **16 trường**: `HP, AP, DEF`, `APR, HPR, DEFR` (vào `ap_rate/hp_rate/def_rate`), `HIT, DOD, CRI, TEN, BLO, BOG, CRID` (map vào `CRId`), `TEND`, `DAMADD, DAMCUT`, `RP, FSP`.
  2. `TreasureStepAttrRelation` (`game_data["treasure_step_attr"]`): đã bổ sung **`410` → `DAMADDR`** và **`411` → `DAMCUTR`** vào `Property` và `FightInfo`.
  3. `HeroStepCheer.lua` (180 mốc): xác minh từ `PartnerCheerLayer.lua:50-62` — cộng `Step` của các **Đồng Đội (`_mate_slot_info`) phẩm chất Cam trở lên (`colorLV >= 5`, tức `quality >= 13`)**, tra `hero_step_cheer[str(min(total_step, 180))]` cộng `APADD/HPADD/DEFADD` cho toàn bộ 6 slot.
  4. `FashionPrRelation.lua` (4 bộ): xác minh `allAttr` là **chỉ số cộng thẳng** (`431 APADD`, `432 HPADD`, `433 DEFADD`) theo phạm vi vị trí (`2` = toàn đội, `6` = hàng trước `Formation1..3`, `7` = hàng sau `Formation4..6`), đồng thời kích hoạt `_recalc_all_slots_and_fap()` khi đổi đội hình (`SlotFormation.Change`).
  5. `DailyTask`: đã nối `_record_daily_task_progress(12, ...)` trong `Glory.GloryLvUp` / `GloryLvUpForOneKey` (`server/emulator.py:8051,8077`) và `_record_daily_task_progress(26, 1)` trong `TraderInfo.BuyGoods` (`server/r79_event_handlers.py:2592`), kiểm chứng trong `server/test_r722a.py`.
- **Unit/Integration test (`server/test_r722a.py`):** 5 bài test cho Bộ Trang Bị 16 chỉ số, Tiến Giai Bảo Vật `410/411`, Cổ Vũ Đồng Đội cam+, Duyên Bộ Thời Trang + hoán đổi đội hình, và DailyTask `#12`/`#26`.
- **Mức model khuyến nghị:** **Trung bình**.

---

### `TASK-M02` *(ĐÃ TRIỂN KHAI Ở R7.22B)* — Khôi Phục Tiến Hóa Nhân Vật Chính, Drop Tinh Anh, Phí Reset Ải & Kiểm Chứng Shop Điểm Yêu Vương

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.22B** (`server/test_r722b.py`).
- **Mục tiêu:** Đóng 3 lỗ hổng tiến trình & kinh tế có 100% bảng VN gốc và xác minh cấu trúc thật của `BossBattle` (`LuckbossValueShopModel` vs tab `ExchangeInfo`).
- **Mức ưu tiên:** `P0` / `P1`.
- **Các file đã đối chiếu & cập nhật:**
  - `server/extract_game_data.py`, `server/game_data.json`
  - `server/emulator.py` (`_sync_main_hero_model`, `_recalc_all_slots_and_fap`, `_normalize_loaded_state`, `import_save_bundle`, `_rpc_elite_fight`, `_rpc_battle_reset_count`)
  - `server/test_emulator.py` (`test_14` EliteBattle 50 KC + `test_27` ResetCount `-1105` / `50` KC), `server/test_r722b.py`
- **Bằng chứng & Logic VN gốc đã xác minh & triển khai:**
  1. **Tiến hóa MC:** Đã trích `AttrtreeHeromodelRelation.lua` (5 mốc `0, 1, 4, 113, 348`). Thêm `_sync_main_hero_model()` chọn `boyHeroModelID`/`girlHeroModelID` theo `StarId` (hoặc tối thiểu mốc `1` khi `Step >= 1`), cập nhật `hero["HeroModelId"]`, `slots[0]["HeroModelId"]`, `player["HeadImageId"]` giữ nguyên `Id`/`Lv`/`Step`, gọi trong `_recalc_all_slots_and_fap()`, `_normalize_loaded_state()` và `import_save_bundle()`.
  2. **Drop Tinh Anh:** Đã trích `ElitebattleNodeDropRelation.lua` (747 dòng nhóm theo `nodeModelID` cho 36 ải). Trong `_rpc_elite_fight` roll từng dòng drop theo `dropOdds` (`10000` hoặc `1..10000`) và phát cùng phần thưởng qua `_grant_resources_from_tuples`.
  3. **Phí Reset Ải (`Battle.ResetCount`):** Đã trích `BattleResetUseRelation.lua` (20 bậc). Kiểm tra rollover theo ngày (`clock.today_str`), chặn quá 20 lần/ngày (`-1`), hỗ trợ `consume_type` (`2`=thẻ `16050013`, `3`=KC `50/100/200`, `0`=tự động ưu tiên thẻ rồi mới tới KC), trả `-1105` khi thiếu mà không làm biến đổi state, và trả đầy đủ dict node như `BattleDropLayer.lua` mong đợi.
  4. **Kiểm chứng `BossBattle` (`LuckbossValueShopModel`):** Kiểm tra `BossRewardPreviewLayer.lua:60-64,488-518` xác nhận 35 dòng `LuckbossValueShopModel` là **35 rương điểm** của `BossBattle.BoxList`/`DrawBox`/`OneKeyDrawBox` (đã hoạt động 100%). Tab 2 (`ExchangeInfo`/`Exchange` dùng `LuckbossValueExchangeModel`) đã bị chính client VN chú thích tắt và không có config trong VN hay các APK donor → giữ `ExchangeInfo -> []` làm no-op an toàn.
- **Unit/Integration test (`server/test_r722b.py`):** 5 bài test cho Tiến hóa MC Nam/Nữ + `Step>=1` + migrate save cũ + an toàn slot 1 không phải MC; Drop Tinh Anh; ResetCount (thẻ/KC leo thang/rollover/cap 20); `BossBattle` 35 mốc + no-op `ExchangeInfo`.
- **Mức model khuyến nghị:** **Trung bình**.

---

### `TASK-M03` *(ĐÃ TRIỂN KHAI Ở R7.22C)* — Khôi Phục FAP Chuẩn (`1:10:10`), PRNG `CreateRandom`, Chọn Mục Tiêu AI & Khắc Chế Phe

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.22C** (`server/test_r722c.py`).
- **Mức ưu tiên:** `P0`.
- **Các file đã đối chiếu & cập nhật:**
  - `server/combat_sim.py` (`CreateRandom`, `_col_order`, `_select_targets`, `_apply_attack`, `simulate_fight_info`)
  - `server/emulator.py` (`_zero_slot_property`, `_compute_slot_property`, `_recalc_all_slots_and_fap`, `_hero_fight_obj`, `_build_enemy_wave`, `_rpc_treasure_loot_fight`, `_build_boss_fight_info`)
  - `server/bdd_handlers.py` (`_bdd_fap`), `server/teambattle_handlers.py` (`_teambattle_raw_fap`)
  - `server/test_emulator.py`, `server/test_r713.py`, `server/test_r715.py`, `server/test_r7151.py`, `server/test_r717.py`, `server/test_r722c.py`
- **Bằng chứng & Logic VN gốc đã xác minh & triển khai:**
  1. **FAP chuẩn (`HP + 10*(AP + DEF)`):** Đã đổi toàn bộ 6 hàm tính FAP đơn vị sang hệ số `10` và kiểm chứng khớp `0` sai số trên cả 216/216 NPC bậc 1 của `TeambattleHeroNpc.lua`.
  2. **PRNG `CreateRandom`:** Port nguyên bản `2.400`-char `MBOX` + `_lrotate32/_rrotate32` + `& 0xFFFFFFFF` vào `combat_sim.CreateRandom`, cung cấp `get_random(min, max)` và `randrange(stop)` tương thích cả `combat_effects.py` và mock test. Khớp `2.500/2.500` lượt (5 seed × 500 lượt) và kịch bản APK Lua 5.1 oracle (`Midoriko seed=1/3`, `Miroku seed=3`).
  3. **Chọn mục tiêu AI:** `_select_targets` dùng `_col_order` (`[c, c-1, c+1, c-2, c+2]`) cho `eSingleFront/Back/OneColumn`, `eHPMin` so raw `HP`, `eRPMax/Min` loại `attacker_pos`, `eRandom` pop qua `CreateRandom.get_random(1, len(remaining))`.
  4. **Khắc chế phe (`countryHurt`):** Hỗ trợ `attrEffectRange ∈ {3, 4, 5}` + `412..417` (`RADAMADDR..RCDAMCUTR`) trong `Property`, `_hero_fight_obj`, và `combat_sim._apply_attack` (`+50%` ST lên `万妖之王*A/B/C`).
- **Mức model khuyến nghị:** **Trung bình**.

---

### `TASK-M04` *(ĐÃ TRIỂN KHAI Ở R7.22D)* — Khôi Phục Khảm, Tháo & Hợp Linh Thạch / Đá (`Slot.GemCombat` + `Gem.GemCompose`)

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.22D** (`server/test_r722d.py`).
- **Mục tiêu:** Khôi phục đầy đủ khảm/chuyển/tháo/tự khảm Đá (`Slot.GemCombat`, `Slot.GemOneKeyCombat`), ghép Đá (`Gem.GemCompose`, `Gem.GemOneKeyCompose`) và cộng chỉ số Đá từ `GemModel.attrStr` vào `Slot.Property` & `FightInfo`.
- **Mức ưu tiên:** `P1`.
- **Các file đã đối chiếu & cập nhật:**
  - `server/emulator.py` (`_gem_slot_max`, `_normalize_slot_gems`, `_slot_gem_bonuses`, `_compute_slot_property`, `_normalize_loaded_state`, `_compute_red_dot_info`, `_rpc_slot_gem_combat`, `_rpc_slot_gem_one_key_combat`, `_parse_gem_compose_recipe`, `_compose_gems`, `_rpc_gem_compose`, `_rpc_gem_one_key_compose`)
  - `server/test_r722d.py`
  - Client nguồn: `Formation/MyFormationLayer.lua`, `Formation/PlayerFormationLayer.lua`, `Gem/GemLevelUpLayer.lua`, `Gem/GemSelectLayer.lua`, `Equipment/EquipmentScene.lua`, `Equipment/EquipmentComposeLayer.lua`, `Data/CalcPrefData.lua`, `Data/NetworkResData.lua`, `Config/PlayerLvRelation.lua`, `Config/GemModel.lua`
- **Bằng chứng & Logic VN gốc đã xác minh & triển khai:**
  1. **Chuẩn hóa `slot["Gem"]` (6 phần tử):** Mỗi ô rỗng dùng `{}` thay vì `EMPTY_ENTITY_ID` để khớp `CalcPrefData.lua:1234` (`table.nums(cur) <= 0`), tự chuẩn hóa save cũ trong `_normalize_loaded_state` và giữ đồng bộ với `state["gems"]`.
  2. **`Slot.GemCombat` & `Slot.GemOneKeyCombat`:** Kiểm tra mở khóa ô Đá theo `PlayerLvRelation.gemSlotMax` (Lv1..6 → 1..6 ô, thiếu cấp trả `-1127`), kiểm tra `GemModel.limit == gemSlotIdx`, hỗ trợ tháo (`""` / `EMPTY_ENTITY_ID`), chuyển Đá từ slot tướng khác (`GemSelectLayer`), và `GemOneKeyCombat` chọn Đá rảnh cấp cao nhất.
  3. **`Gem.GemCompose` & `Gem.GemOneKeyCompose`:** Hỗ trợ cả **Mode A** (`GemLevelUpLayer`: nâng cấp tại chỗ 1 viên đang khảm + 3 Đá rảnh, cập nhật `slot["Gem"]` + `_recalc_all_slots_and_fap` + `Avatar.SlotInfo`, không phát trùng `BaseGetGameResourceList`) lẫn **Mode B** (`EquipmentComposeLayer`: ghép 4 Đá rảnh, tự dùng `Đá Song Sinh` `syntheticDoubleUse` nếu có để nhận 2 viên kèm `Avatar.GoodsInfo`), và `Gem.GemOneKeyCompose` ghép hàng loạt Đá rảnh (không tự đốt `Đá Song Sinh`). Bật red-dot `1413` (`eGemCompose`) khi Lv >= 40 và có >= 4 Đá rảnh cùng mẫu `< Lv15`.
  4. **Cộng chỉ số Đá:** `_slot_gem_bonuses` đọc đủ 11 enum xuất hiện trong 90 mẫu `GemModel` (`301..306`, `408`, `409`, `431..433`), cộng thẳng vào `_compute_slot_property` → `Slot["Property"]`, `FAP` và `FightInfo`.
- **Unit/Integration test (`server/test_r722d.py`):** 5 bài test (khảm/chuyển/tháo/kiểm tra `limit` & cấp mở ô/`FightInfo`, `GemOneKeyCombat`, ghép túi + Đá Song Sinh + kiểm lỗi, nâng cấp tại chỗ Đá đang khảm, `GemOneKeyCompose` + red-dot `1413` + lưu/tải lại).
- **Mức model khuyến nghị:** **Trung bình**.

---

### `TASK-M05` *(ĐÃ TRIỂN KHAI Ở R7.23)* — Khôi Phục Buff Chiến Đấu Lát 1A (Độc `hpdot`, Hút Máu, Buff Hàng, Giảm Hồi Máu, Tất Trúng/Miễn Bạo)

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.23** (`server/test_r723.py`).
- **Mức ưu tiên:** `P1`.
- **Các file đã đối chiếu & cập nhật:**
  - `server/combat_effects.py`, `server/combat_sim.py`, `server/test_r723.py`
  - Client nguồn: `CSCommon/FightBuffModel.lua`, `CSCommon/FightAttack.lua`, `CSCommon/Fight.lua`, `CSCommon/Hero.lua`, `CSCommon/BattleMatrix.lua`, `CSCommon/TargetModeFunction.lua`
- **Bằng chứng & Logic gốc VN đã triển khai:**
  1. `type=6` có `refAttr != 0` (`ORIG_REF_ATTR {201, 202, 203}`): tính `modify_value = ceil(orig_attr * refValue / 10000)` → `override_add_value = modify_value * 100` (Naraku/Kaguya Độc `2031/2044`, Miroku RA `20480400 → 12440000` gắn đúng `c1=4`).
  2. Độc `HPDOT (602)` (`14040000`): trừ HP qua `_change_hp` khi đơn vị trúng Độc ra đòn (`c1=1, c2=5`), cộng dồn `overlayNum=-1`, hết hạn theo lượt người gắn và xóa sạch bằng `CLEAR_DEBUFFS (499)`.
  3. `type=3` kiểm `refAttr >= 500` (`refAttr=602`) & giữ thứ tự sau-calc (`type=3` trước `type=6` khớp `FightAttack.lua:857 vs 871`) → mở khóa Naraku `+8/+10` (`1027xxxx/10261000`), Kaguya `+10` (`1062xxxx`), hồi Nộ hạ gục `10280000`.
  4. `type=7 (eTransformation)` hút máu theo `CurTotalDamValue` (`DAM` trong `combat_sim.py`, `refAttr=400`) cho bản thân (`camp=3`) hoặc đồng đội mất máu nhiều nhất (`camp=1, tE=12`), tôn trọng `LOCK_HEALING (505)`.
  5. `_select_ally_recipients` cho `camp == 1, tE ∈ {3, 4, 12}` (Kanade Hime `+8`, Miroku, Toutousai, Hakudoushi, Sara, Toran, `10660400/1067xxxx`).
  6. `type=2, addAttr=0` ở `phase=1` (`20010000`, `20020000`): gắn con `12101000`/`12221000` với `before_action=True, turns=1`.
  7. Giảm hồi máu `407 BCPR` (`12420800`, `12430750`, `12430806`) giữ nguyên `c1=4` trung thực theo `FightAttack.lua:429`.
  8. `addAttr=201` (`type=2, at ∈ {2, 4}`: `1901xxxx`, `10540300`, `10660400`, `1069xxxx`, `10340101/51`).
- **Kết quả phủ định lượng sau R7.23:** `HeroTalRelation` đạt **`1.647/1.699` (96,9%) đầy đủ** (chỉ còn `15` một phần + `37` Lát 1B), `AttackModel` đạt **`125/133` (94,0%)**, `server/test_r723.py` 5/5 PASS.
- **Mức model khuyến nghị:** **Trung bình**.

---

### `TASK-N01` *(ĐÃ TRIỂN KHAI Ở R7.24)* — Buff Chiến Đấu Lát 1B (100% VN) & Mở BDD Tầng 24–26 (`48/51` Ải)

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.24** (`server/test_r724.py`).
- **Mức ưu tiên:** `P1`.
- **Các file đã cập nhật:** `server/combat_effects.py`, `server/combat_sim.py`, `server/bdd_handlers.py`, `server/test_r714.py`, `server/test_r717.py`, `server/test_r718.py`, `server/test_r723.py`, `server/test_r724.py`.
- **Kết quả triển khai:**
  1. Khôi phục 100% buff chiến đấu Lát 1B khớp `Fight.lua`/`FightAttack.lua`/`FightBuffModel.lua`/`ContinuousAttack.lua`: `ContinuousAttack` (`9002` Liên trảm, `9003` Đánh đôi, `9005` Phản kích đỡ với `dont_add_rp=True` và `exclude_types=0..9`), Lan đánh thường `9004` (`_ROW_NEIGHBORS`), Phản ST `9006` + Miễn `707`, Hồi sinh & Tử vong kích hoạt (`1029/1030/1031/1032/1033`), Bất tử 1 lượt `14060000`, Khiên `601` + `c1=7`, Miễn tử `9007`, `type=0` (`10110600`), và Boss enrage `10090000`.
  2. Đạt **`1.699 / 1.699` (100,0%) `HeroTalRelation`** và **`133 / 133` (100,0%) `AttackModel.buffList`**.
  3. Mở `PLAYABLE_FLOORS = range(11, 27)` (**`48 / 51` ải**, +9 ải mới Tầng 24–26) và giữ Tầng 27 (`2711–2713`, `18,17M–38,62M` `proposeFAP`) chuyển sang phụ thuộc **`TASK-N02`** (`RebornInfo` + `UAID` + `EquipArtifact`), kèm bằng chứng đối chứng `TeambattleHeroNpc.lua`.

---

### `TASK-M06` *(ĐÃ TRIỂN KHAI Ở R7.25)* — Khôi Phục `LeaderBoard`, `Goods.GoodsSell`, `PlayerProfile`, `Treasure.TreasureCompose` & Đóng Audit Modal/`LoadingWait`

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.25** (`server/test_r725.py`, 5/5 PASS).
- **Mức ưu tiên:** `P0` (`REC-P0-04`) / `P2` (`REC-P2-04`, `REC-P2-05`).
- **Các file đã đối chiếu & cập nhật:**
  - `server/extract_game_data.py`, `server/game_data.json` (trích thêm 3 bảng VN: `LeaderboardConfig.lua`, `TreasureColorModel.lua`, `GoodsDjqModel.lua` → tổng `144 / 276` bảng VN).
  - `server/emulator.py` (+7 RPC thật: `LeaderBoard.RankList`, `LeaderBoard.Praise`, `LeaderBoard.Formation`, `Goods.GoodsSell`, `Player.AlterPlayerHeadId`, `Player.AlterPlayerName`, `Treasure.TreasureCompose`, dùng chung `_treasure_exp_refund_tuples` & `_build_bot_formation_view`; hỗ trợ `goods_djq_model` `1611` trong `_is_valid_resource`).
  - `server/test_r725.py`.
- **Kết quả kiểm chứng Modal & `LoadingWait` (`REC-P0-04`):**
  1. **8/9 modal** (`GrabForOneKeyLayer`, `LevelGiftLayer`, `ContinuousSignLayer`, `FirstRechargeLayer`, `RewardCenterLayer`, `SystemLayer`, `ChallengeListLayer`, `PracticeListLayer`) thực tế ĐÃ gán `self.onCloseCallback` trong `ctor(...)`; modal thứ 9 (`TimedRecruitEquipLayer.lua`) không hề định nghĩa phương thức `:onCloseCallback()` trên lớp → không có vòng đệ quy như `TimedEquipRankLayer`.
  2. **5 file `LoadingWait:begin > ends`** (`GrabTreasureScene`, `DisassembleNewScene`, `BagScene`, `RechargeScene`, `GuildApplyLayer`) không có nguy cơ treo vì `Common/LoadingWait.lua#L67-L83` gọi `LoadingWait:ends()` ngay đầu `LoadingWait:begin()` (thay thế singleton, không đếm tham chiếu). Không cần vá APK.

---

### `TASK-N02A` *(ĐÃ TRIỂN KHAI Ở R7.26)* — Phó Bản Ác Mộng (`Nightmare`), Nền `RebornGoods`/`RebornCoin` & Cân Bằng Wave Chiến Dịch `Ch 12–80`

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.26** (`server/test_r726.py`, 5/5 PASS; toàn bộ `test_emulator.py` `76/76` PASS).
- **Mức ưu tiên:** `P1` (`REC-P1-04`) / `P2` (`REC-P2-01` phần 1).
- **Các file đã cập nhật:**
  - `server/extract_game_data.py`, `server/game_data.json` (+5 bảng VN: `NightmareConfig.lua`, `NightmareChapterBoxRelation.lua` 192 rương, `NightmareNodeDropModel.lua` 899 dòng, `NightmareResetUseRelation.lua` 3 bậc, `RebornGoodsModel.lua` 28 vật liệu → tổng `149 / 276` bảng VN).
  - `server/nightmare_handlers.py` (mới), `server/economy_audit.py` (`RebornCoin`), `server/emulator.py` (+13 route: 12 RPC thật `Nightmare.GetNightmareInfo/GetNodeList/AllChapterInfo/GetFightInfo/Fight/ConFight/HiAutoFight/ResetCount/DrawBox/OneKeyDrawBoxs/RankList/Formation` + `DrawRoadBox` chặn an toàn `-1`; nền tài nguyên `RebornGoods 2701` / `RebornCoin 1128` trong `GetInitData`/`Avatar`/`BaseGetGameResourceList`; hàm chuẩn hóa log-linear `_build_enemy_wave` `Ch 12–80`), `server/test_r726.py`.
- **Ghi chú:** Toàn bộ chuỗi `TASK-N02` (`TASK-N02A` + `TASK-N02B`) đã hoàn tất ở R7.26–R7.27.

---

### `TASK-N02B` *(ĐÃ TRIỂN KHAI Ở R7.27)* — Hệ Thống Chuyển Sinh (`RebornInfo` + `RebornShop`), `11 Tuyệt Kỹ UAID` & Mở BDD Tầng 27 (`51/51`)

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.27** (`server/test_r727.py`, 5/5 PASS).
- **Mức ưu tiên:** `P1` (`REC-P1-05`) / `P2` (`REC-P2-01` phần 2).
- **Các file đã cập nhật:**
  - `server/extract_game_data.py`, `server/game_data.json` (+6 bảng VN: `RebornConfig.lua`, `RebornLvActiveModel.lua` 9 bậc, `RebornPrtypeRelation.lua` 34 bậc, `RebornShopOddsRelation.lua` 61 dòng, `RebornSlotRelation.lua` 340×4 ô, `HeroRebornCheer.lua` 84 cấp → tổng `155 / 276` bảng VN).
  - `server/reborn_handlers.py` (mới): `RebornHandlersMixin` cài đủ 5 RPC `RebornInfo` (`Activate`, `Reborn`, `ComposeAndActivateForOneKey` hợp thành đệ quy `RebornGoodsModel.compoundUse`, `RebornGoodsCompose`, `RebornGoodsRefine` → `1128 RebornCoin`) + 3 RPC `RebornShop` (`GetInfo`, `RefreshtGoodsList` 3 chế độ, `RebornShopBuyGoods`), khởi tạo `RebornId`/`RebornStepInfo` (fallback `classID=16` cho `12015022`/`12015023`), cộng Duyên `RebornPrtypeRelation`, Đại Sư Chuyển Sinh `RebornLvActiveModel` (+130% khi đủ 6 slot), `HeroRebornCheer`, 7 buff `talIDStr`, **mở khóa 11 Tuyệt Kỹ `UAID` (`1003001..1003011`)**, `RebornnComposeStatus`, và hoàn trả ở `HeroRebirth`.
  - `server/emulator.py` (+8 route → `290` handler = `286` thật + `4` stub), `server/bdd_handlers.py` (`PLAYABLE_FLOORS = range(11, 28)` → `51 / 51` ải), `server/test_r714.py`, `server/test_r718.py`, `server/test_r724.py`, `server/test_r727.py`.

---

### `REC-P2-02` *(ĐÃ TRIỂN KHAI Ở R7.28)* — Trùm Tăng Cấp / Thần Khí (`EquipArtifact`, `1408`) & Triệu Hồi Trang Bị Thường (`Callequip`, `3802`)

- **Trạng thái:** **Đã triển khai & kiểm thử ở R7.28** (`server/test_r728.py`, 5/5 PASS).
- **Mức ưu tiên:** `P2`.
- **Các file đã cập nhật:**
  - `server/extract_game_data.py`, `server/game_data.json` (+2 bảng VN: `EquipArtifactRelation.lua` 1.104 dòng, `CallequipOutoddsBRelation.lua` 36 dòng → tổng `157 / 276` bảng VN).
  - `server/event_runtime.py` (thêm `timed_welfare_equip_crit` `4419` vào `timed_scene_specs`).
  - `server/emulator.py`: `_equip_item_lv`, `_compute_equip_artifact_state` (cộng `APADD/HPADD/DEFADD` vào `_compute_slot_property` & đồng bộ `Avatar.EquipArtifactInfo` cho `GetInitData`/thay đổi bậc), nối `SuccessTarget #37..41` & `#12`, thêm 2 RPC `Callequip.GetCallEquipData` & `Callequip.CallEquip` (miễn phí `90m`/`4260m`, lượt KC đầu Cam, pity luân phiên Tím↔Cam, ưu đãi `4416` & bạo kích `4419`; +2 route → `292` handler = `288` thật + `4` stub).
  - `server/test_r715.py`, `server/test_r7151.py` (cập nhật delta `EquipArtifact` hợp lệ), `server/test_r728.py`.

---

### Gói 10 — `REC-P2-03`: Kho Vàng (`GGZJ`) & Đấu Võ Đại Hội (`Gddh`/`GddhShop`) *(ĐÃ HOÀN TẤT R7.29)*
- **Đã triển khai & kiểm chứng xong (`test_r729.py` 6/6 OK, tổng `199/199` tests OK):**
  - `server/extract_game_data.py` & `server/game_data.json`: trích đủ 10 bảng VN (`4` `Ggzj*` + `6` `Gddh*` → `167 / 276` bảng VN).
  - `server/ggzj_handlers.py` (`GgzjHandlersMixin`): 8 RPC `GGZJ.*`, nghỉ chiến `23:50–24:00`, nhân VIP `ggzjMutipleR`, rương tuần tự `1..5`, phúc lợi `4415`, reset ngày, chấm đỏ `2504`.
  - `server/gddh_handlers.py` (`GddhHandlersMixin`): 8 RPC `Gddh.*` + 2 RPC `GddhShop.*`, lịch T3–T4 / T5–T6 / T7–T2, nghỉ chiến & kết toán `23:00` về `RewardCenter (2400)`, hồi lượt theo giờ, TK S1 peer + 80 bot, shop 16 món, phúc lợi `4414`, chấm đỏ `2503`.
  - `server/emulator.py`, `server/economy_audit.py`, `server/event_runtime.py`, `server/event_handlers.py`, `server/r79_event_handlers.py`: đăng ký 18 route (`310` handler), tiền `GDDHCoin (1119)` & `RawGold (2112)`, sự kiện `4414`/`4415`, `_sync_gddh_settlement`, `DailyTask #6/#9`, `SuccessTarget #13/#30`, `ActiverankingModel #7/#9`.
  - `server/test_r729.py` (6 test cases).

---

### Gói 11 — `REC-P2-04A`: Bạn Bè (`Friend`/`FriendMessage`/`Enemy`) & Hộp Thư (`PlayerEmail`) *(ĐÃ HOÀN TẤT R7.30)*
- **Đã triển khai & kiểm chứng xong (`test_r730.py` 6/6 OK, tổng `205/205` tests OK):**
  - `server/social_handlers.py` (`SocialHandlersMixin`): đủ **19 RPC** (`Friend.*` 5, `FriendMessage.*` 9, `Enemy.*` 3 gồm nâng `GetEnemyList` từ stub → thật, `PlayerEmail.*` 2), đồng bộ 2 chiều TK S1 + 24 NPC bạn bè cục bộ, tự động duyệt NPC & gửi quà STA theo ngày (`+2` STA/lượt, cap `20`/ngày, tôn trọng `STAMaxNum` `-3010`), nối `DailyTask #11` (`23/25`), mã lỗi chuẩn `ServerMessage.lua` (`-2703`, `-2706`, `-3001..-3019`), chấm đỏ `1700/1701/1900..1903`.
  - `server/emulator.py`, `server/event_handlers.py`, `server/gddh_handlers.py`, `server/teambattle_handlers.py`: đăng ký 18 route mới + nâng `Enemy.GetEnemyList` (`328` handler = `325` thật + `3` stub), `_sync_social_daily` trong `_sync_events`, `Slot.SlotFormations` cho NPC bạn bè, chiến báo `PVP.PVPFight` / `Gddh.RankWrestleRace` / `BossBattle.FriendHelp` vào `PlayerEmail`, và mời bạn thật/NPC vào `Teambattle`.
  - `server/test_r730.py` (6 test cases).

---

## 3. Trạng Thái Bàn Giao & Prompt `TASK-M01` *(Đã Hoàn Thành Ở R7.22A)*

Gói đầu tiên **`TASK-M01` (`R7.22A`)** đã được triển khai & nghiệm thu xong (`server/test_r722a.py`). Gói kế tiếp sẵn sàng triển khai cho model tầm trung là **`TASK-M02`** (mục 2 phía trên). Prompt `TASK-M01` ban đầu được giữ lại dưới đây để lưu vết:

```markdown
# R7.22A (`TASK-M01` — ĐÃ HOÀN THÀNH) — Khôi phục Chỉ Số Bộ Trang Bị, Bảo Vật, Cổ Vũ, Duyên Thời Trang & DailyTask #12/#26

## Bối cảnh & Ràng buộc
- Workspace: `/Users/vup/Documents/agy/inuyasha` (baseline `checkpoint-vn-r7.21`).
- CHỈ sửa backend Python và dữ liệu trích xuất (`server/extract_game_data.py`, `server/game_data.json`, `server/emulator.py`, `server/r79_event_handlers.py`, và thêm test mới `server/test_r722a.py`).
- KHÔNG sửa `server/combat_sim.py`, `server/combat_effects.py`, `server/bdd_handlers.py`, `server/teambattle_handlers.py`, `poc/build_standalone_apk.py`, KHÔNG đổi công thức FAP (`HP + 5*AP + 5*DEF`), KHÔNG build/cài APK, KHÔNG chạm vào `server/saves/` hoặc thiết bị Pixel 3 XL.
- Đọc trước báo cáo phân tích tại `docs/deep_gameplay_audit/MEDIUM_MODEL_HANDOFF.md` mục `TASK-M01`.

## Các hạng mục bắt buộc triển khai
1. **Trích xuất thêm 2 bảng VN gốc trong `server/extract_game_data.py` và chạy lại để cập nhật `server/game_data.json`:**
   - `HeroStepCheer.lua` → `hero_step_cheer`
   - `FashionPrRelation.lua` → `fashion_pr`
2. **Sửa `ProfileStore._compute_slot_property` trong `server/emulator.py`:**
   - **Bộ Trang Bị (`equip_group`):** Hiện tại chỉ cộng `HP/AP/DEF`. Bổ sung cộng đầy đủ 13 trường còn thiếu từ `EquipGroupActiveRelation.lua`: `APR`, `HPR`, `DEFR` (cộng vào `ap_rate`/`hp_rate`/`def_rate`), `HIT`, `DOD`, `CRI`, `TEN`, `BLO`, `BOG`, `CRID` (map vào `CRId`), `TEND`, `DAMADD`, `DAMCUT`.
   - **Tiến Giai Bảo Vật (`treasure_step_attr`):** Hiện tại chỉ cộng enum `201/202/203`. Bổ sung cộng `410` (`DAMADDR`) và `411` (`DAMCUTR`) vào `Property` để đi thẳng vào `FightInfo`.
   - **Cổ Vũ Đột Phá (`hero_step_cheer`):** Đọc `analysis/vn/decompiled_src/Formation/PartnerCheerLayer.lua` (`L45-L180`) để xác minh chính xác cách tính `totalStep` (6 slot ra trận hay gồm cả Đồng Đội), tra mốc `hero_step_cheer` tương ứng và cộng `APADD`, `HPADD`, `DEFADD` vào các slot.
   - **Duyên Bộ Thời Trang (`fashion_pr`):** Đọc `analysis/vn/decompiled_src/Config/FashionPrRelation.lua` và `Formation/FashionGroupLayer.lua` để kiểm tra đúng đơn vị của `allAttr`, khi sở hữu đủ mọi `FashionModelId` trong `memberS` thì cộng phần trăm tương ứng vào `ap_rate`/`hp_rate`/`def_rate` của mọi slot.
3. **Nối 2 hook DailyTask bị sót:**
   - Gọi `self._record_daily_task_progress(12, count)` khi `Glory.GloryLvUp` / `Glory.GloryLvUpForOneKey` thành công (`server/emulator.py`).
   - Gọi `self._record_daily_task_progress(26, 1)` khi `TraderInfo.BuyGoods` thành công (`server/r79_event_handlers.py`).

## Kiểm thử & Tiêu chí nghiệm thu
- Viết `server/test_r722a.py` kiểm thử độc lập cả 5 hạng mục (mặc bộ trang bị tăng đủ secondary stats + `%` và vào `FightInfo`; nâng bậc bảo vật tăng `DAMADDR`/`DAMCUTR` vào `FightInfo`; tăng tổng Step đội kích hoạt `HeroStepCheer`; sở hữu đủ bộ thời trang kích hoạt `FashionPrRelation`; `Glory` và `TraderInfo` tăng tiến độ `DailyTask #12` & `#26` và nhận thưởng được; save/reload bảo toàn 100%).
- Chạy `python3 server/extract_game_data.py` và chạy toàn bộ bộ test Python (`test_emulator.py`, `test_r7151.py`..`test_r721.py`, `test_r722a.py`), bảo đảm 100% PASS.
- Báo cáo ngắn gọn các file đã sửa, số lượng test PASS và mọi assertion cũ bị ảnh hưởng (nếu có) kèm giải thích toán học.
```
