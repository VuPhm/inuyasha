# Lộ Trình & Backlog Ưu Tiên Khôi Phục Gameplay và Cân Bằng

**Ngày lập kế hoạch:** 22/11/2026 (UTC+7) | **Baseline:** `checkpoint-vn-r7.21` (`2b91941`, APK 840).

> **Trạng thái phụ thuộc R7.21:** Tại thời điểm hoàn tất khảo sát (`00:12` ngày 22/11/2026), nhánh R7.21 (Phó Bản Tổ Đội + lưu trữ Đá `2000`) **đã được nghiệm thu, commit `2b91941` và gắn tag `checkpoint-vn-r7.21` (APK 840)**. Do đó **không có hạng mục nào bị chặn bởi R7.21 đang chạy dở**; ngược lại, hạ tầng `gems` + `gem_model` mà R7.21 vừa bàn giao chính là **điều kiện đầu vào sẵn sàng** cho gói `REC-P1-04` (Khảm & Hợp Đá)!

---

## 1. Phân tách bắt buộc: Khôi phục Logic Gốc vs Tùy chỉnh Cá nhân Offline

| Nhóm | Phạm vi | Quy tắc xử lý |
|---|---|---|
| **Phần I — Khôi phục Logic Gốc (`VN 5.0.4.98`)** | Toàn bộ các mục `P0`, `P1`, `P2` bên dưới (công thức FAP `1:10:10`, PRNG `CreateRandom`, chọn mục tiêu AI, 12 cơ chế buff `FightBuffModel`, tiến hóa MC, Set Trang Bị, `DAMADDR/DAMCUTR` Bảo Vật, Cổ Vũ, Khảm/Hợp Đá, Drop Tinh Anh, Shop Yêu Vương, Phí Reset Ải, 12 ải Mộ Thần Binh cuối, Chuyển Sinh + `UAID`, Ác Mộng, Kho Vàng, Đấu Võ, Bang Hội S1). | **Ưu tiên số 1.** Bám sát 100% bảng VN và `CSCommon/*.lua`. Không tự ý cân bằng lại tướng hay phá vỡ meta gốc. |
| **Phần II — Tùy chỉnh Trải nghiệm Cá nhân Offline** | (1) Nền túi tướng 300 (gốc 100); (2) Nạp offline không cần cổng thanh toán; (3) Event Archive mở song song nhiều sự kiện/banner & reset `00:00 UTC+7` hoặc thủ công; (4) Nút phân giải nhanh Cam trở xuống (R7.20); (5) Chơi Tổ Đội / Bang Hội / Đấu Võ một mình cùng đồng đội NPC & tài khoản S1; (6) Cân nhắc sau cùng về việc bật các tính năng VN tắt (`ifOpen=0` như Luyện Thể, Pet, Chiến Trận) hoặc nguồn cấp Trang Bị Kim. | **Tách riêng hoàn toàn** khỏi các bản vá logic gốc. Chỉ kích hoạt khi có chỉ thị rõ của chủ dự án và không làm hỏng vòng lặp chiến đấu / tiêu hao tài nguyên. |

---

## 2. Backlog Chi Tiết Theo Mức Ưu Tiên (`P0` → `P3`)

### P0 — Tính Đúng Đắn & Đồng Bộ Cốt Lõi (Phải làm ngay, ảnh hưởng toàn game)

#### `REC-P0-01` — Khôi phục Công Thức FAP Chuẩn (`HP + 10*AP + 10*DEF`) & Sửa Mộ Thần Binh / Tổ Đội *(ĐÃ HOÀN TẤT R7.22C)*
- **Mức phục hồi:** **A** (Khôi phục trực tiếp — chứng minh 0.00 sai số trên 216/216 dòng `TeambattleHeroNpc`).
- **Trạng thái hoàn tất (`R7.22C`):** Đã chuyển toàn bộ công thức tính lực chiến đơn vị (`_compute_slot_property`, `_build_enemy_wave`, `_rpc_treasure_loot_fight`, `_build_boss_fight_info`, `_bdd_fap`, `_teambattle_raw_fap`) từ `HP + 5*(AP+DEF)` sang `HP + 10*(AP+DEF)`, cập nhật các assertion cũ tương ứng và nghiệm thu tại `server/test_r722c.py`.

#### `REC-P0-02` — Đồng Bộ Tuyệt Đối Combat Engine Python ↔ Lua (`CreateRandom` PRNG + AI Chọn Mục Tiêu + Khắc Chế Phe) *(ĐÃ HOÀN TẤT R7.22C)*
- **Mức phục hồi:** **A** (`L1-VN-CODE` 100% từ `CSCommon/`).
- **Trạng thái hoàn tất (`R7.22C`):**
  1. Port nguyên bản `CreateRandom` (`2.400` ký tự hex box + xoay/XOR 32-bit unsigned `& 0xFFFFFFFF`) sang `server/combat_sim.py` (`CreateRandom`), thay `random.Random` trong `simulate_fight_info`.
  2. Sửa `_select_targets` trong `combat_sim.py`: `eHPMin` so raw `HP`; `eRPMax/Min` loại `attacker_pos`; `eSingleFront/Back/OneColumn` fallback sang cột gần nhất; `eRandom` pop qua `get_random(1, len(remaining))`.
  3. Truyền `RADAMADDR..RCDAMCUTR` vào `_zero_slot_property`, `_compute_slot_property`, `_hero_fight_obj` (hỗ trợ `attrEffectRange ∈ {3, 4, 5}` và `412..417`) và cộng `countryHurt` trong `_apply_attack`.
- **Kiểm thử & Nghiệm thu (`server/test_r722c.py`):** Khớp 2.500/2.500 số ngẫu nhiên (5 seed × 500 lượt) với thuật toán `Bit.lua`/`Bit32.lua`/`CreateRandom.lua`, khớp kịch bản Midoriko/Miroku từ APK Lua 5.1 oracle, khớp +50% khắc chế phe `万妖之王*A/B/C`.

#### `REC-P0-03` — Sửa Lỗ Hổng Kinh Tế & Sót Chỉ Số Đã Có Config *(ĐÃ HOÀN TẤT R7.22A + R7.22B)*
- **Mức phục hồi:** **A** (100% có sẵn config VN).
- **Bằng chứng:** `EquipGroupActiveRelation.lua`, `TreasureStepAttrRelation.lua`, `BattleResetUseRelation.lua`, `ElitebattleNodeDropRelation.lua`, `server/emulator.py`, `server/r79_event_handlers.py`.
- **Trạng thái hoàn tất:**
  1. **[XONG R7.22A]** Cộng đủ 16 thuộc tính của `EquipGroupActiveRelation` vào `_compute_slot_property`.
  2. **[XONG R7.22A]** Cộng đủ `410 (DAMADDR)` & `411 (DAMCUTR)` từ `TreasureStepAttrRelation` (kèm `HeroStepCheer` & `FashionPrRelation`).
  3. **[XONG R7.22B]** Trích `BattleResetUseRelation.lua` (20 bậc), trừ đúng thẻ `16050013` trước hoặc `50/100/200` KC, trả `-1105` khi thiếu, trần 20 lần/ngày + reset qua ngày trong `_rpc_battle_reset_count`.
  4. **[XONG R7.22B]** Trích `ElitebattleNodeDropRelation.lua` (747 dòng) và roll drop thật theo `dropOdds` trong `_rpc_elite_fight`.
  5. **[XONG R7.22A]** Nối `_record_daily_task_progress(12, ...)` và `(26, 1)` kiểm chứng tại `server/test_r722a.py`.
- **Kiểm thử & Nghiệm thu:** `server/test_r722a.py` + `server/test_r722b.py` PASS 100%.

#### `REC-P0-04` — Kiểm Định Các Popup Modal / `LoadingWait` Có Nguy Cơ Kẹt State *(ĐÃ ĐÓNG TẠI R7.25 — FALSE POSITIVE, KHÔNG CẦN VÁ APK)*
- **Mức phục hồi:** **A** (`L1-VN-CODE` — Đã xác minh an toàn gốc).
- **Bằng chứng ban đầu & Kết quả xác minh lại ở `R7.25`:**
  - **9 file modal nghi vấn `self.onCloseCallback(self)`:** Kiểm tra trực tiếp từng `ctor` xác nhận **8/9 file** (`GrabForOneKeyLayer`, `LevelGiftLayer`, `ContinuousSignLayer`, `FirstRechargeLayer`, `RewardCenterLayer`, `SystemLayer`, `ChallengeListLayer`, `PracticeListLayer`) thực tế có gán `self.onCloseCallback` theo tham số vị trí hoặc `params`; file thứ 9 (`TimedRecruitEquipLayer.lua`) không định nghĩa phương thức `:onCloseCallback()` trên lớp → không thể gây đệ quy vô hạn (khác hẳn `TimedEquipRankLayer` đã vá ở R7.12).
  - **5 file có số lần `LoadingWait:begin > LoadingWait:ends` (`GrabTreasureScene`, `DisassembleNewScene`, `BagScene`, `RechargeScene`, `GuildApplyLayer`):** Đối chiếu `analysis/vn/decompiled_src/Common/LoadingWait.lua#L67-L83` chứng minh `LoadingWait:begin()` luôn gọi `LoadingWait:ends()` ở dòng đầu tiên (cơ chế thay thế singleton, không đếm tham chiếu) và các màn hình gọi `LoadingWait:ends()` trước khi rẽ nhánh `Status == 0`.
- **Kết luận:** Toàn bộ 14 điểm nghi vấn đều là **false positive**; giữ nguyên `poc/build_standalone_apk.py`, không cần vá thêm Lua.

---

### P1 — Gameplay & Meta Cốt Lõi (Phục hồi trọn vẹn bản sắc chiến đấu và tiến trình)

#### `REC-P1-01` — Khôi Phục Đủ 12 Cơ Chế Buff Còn Thiếu Trong `combat_effects.py` & `combat_sim.py` *(ĐÃ HOÀN TẤT 100% Ở R7.23 + R7.24)*
- **Mức phục hồi:** **A (Đã đạt 100% — khớp `CSCommon/FightBuffModel.lua` & `FightAttack.lua` & `Fight.lua`).**
- **Bằng chứng:** `FightBuffModel.lua`, `FightAttack.lua`, `Fight.lua`, `ContinuousAttack.lua`, `BALANCE_RECOVERY_AUDIT.md` Mục 3 & 4.
- **Trạng thái hoàn tất:**
  - **[ĐÃ XONG R7.23 (`TASK-M05`)] Lát 1A — Độc (`hpdot`), Hút máu (`type=7`), Buff Hàng Trước/Sau (`tE=3/4`), Giảm hồi máu (`407`), Tất trúng/Miễn bạo (`type=2, attr=0`), Trừ/Hồi HP (`attr=201`):** `1.647/1.699` tài năng & `125/133` skill (`server/test_r723.py`).
  - **[ĐÃ XONG R7.24 (`TASK-N01`)] Lát 1B — `ContinuousAttack` (`9002/9003/9005`), Lan đánh thường (`9004`), Phản ST (`9006` + `707`), Hồi sinh & Tử vong kích hoạt (`1029/1030/1031/1032/1033`), Bất tử (`14060000`), Khiên (`601` + `c1=7`), Miễn tử (`9007`), `type=0` (`10110600`), Boss enrage (`10090000`):** đạt **`1.699/1.699` (100,0%) `HeroTalRelation` và `133/133` (100,0%) `AttackModel.buffList`** (`server/test_r724.py`).
- **File đã cập nhật:** `server/combat_effects.py`, `server/combat_sim.py`, `server/test_r717.py`, `server/test_r723.py`, `server/test_r724.py`.

#### `REC-P1-02` — Khôi Phục Tiến Hóa Nhân Vật Chính (`AttrtreeHeromodelRelation`) & Cổ Vũ Đồng Đội (`HeroStepCheer` / `HeroRebornCheer`) & Duyên Thời Trang (`FashionPrRelation`) *(ĐÃ HOÀN TẤT R7.22A + R7.22B + R7.27)*
- **Mức phục hồi:** **A** (100% có bảng VN & UI sẵn).
- **Bằng chứng:** `AttrtreeHeromodelRelation.lua`, `LightenStarScene.lua:309-380`, `HeroStepCheer.lua`, `HeroRebornCheer.lua`, `PartnerCheerLayer.lua`, `FashionPrRelation.lua`, `FashionGroupLayer.lua`.
- **Trạng thái hoàn tất:**
  1. **[XONG R7.22B]** Khi `StarId` đạt mốc `1 / 4 / 113 / 348` (hoặc `Step >= 1` → tối thiểu mốc `1`), `_sync_main_hero_model` tự động nâng `HeroModelId` của MC theo giới tính, đồng bộ `slots[0]` & `HeadImageId` và migrate save cũ giữ nguyên `Id`/`Lv`/`Step`.
  2. **[XONG R7.22A + R7.27]** Đã nối `HeroStepCheer[total_step]` (`R7.22A`) và `HeroRebornCheer[total_reborn]` (`R7.27`, Đồng Đội cam trở lên `colorLV >= 5`).
  3. **[XONG R7.22A]** Đã nối `FashionPrRelation` (`431/432/433` theo phạm vi `2/6/7`).
- **Kiểm thử & Nghiệm thu:** `server/test_r722a.py`, `server/test_r722b.py`, và `server/test_r727.py` đã xác nhận Ngộ Đạo qua mốc `0 → 1 → 4 → 113 → 348` cho cả Nam/Nữ, `Step>=1`, migrate save cũ, `HeroStepCheer`, `HeroRebornCheer`, và `FashionPrRelation`.

#### `REC-P1-03` *(ĐÃ XONG R7.22D)* — Khôi Phục Khảm, Tháo, Hợp Linh Thạch / Đá (`Slot.GemCombat`, `GemOneKeyCombat`, `Gem.GemCompose`, `GemOneKeyCompose`)
- **Mức phục hồi:** **A (Đã đạt ở R7.22D — `TASK-M04`).**
- **Bằng chứng:** `GemModel.lua` (90 mẫu), `MyFormationLayer.lua:1656,1689`, `PlayerFormationLayer.lua:2992`, `Gem/GemLevelUpLayer.lua`, `Equipment/EquipmentScene.lua`, `Data/CalcPrefData.lua:1234`, `Config/PlayerLvRelation.lua`.
- **Cơ chế đã khôi phục:**
  1. **[XONG R7.22D]** `Slot.GemCombat [slotId, gemSlotIdx, gemId]` (khảm/thay/chuyển slot/tháo bằng `""`/`EMPTY_ENTITY_ID`, kiểm tra `GemModel.limit == gemSlotIdx` và `PlayerLvRelation.gemSlotMax`), `Slot.GemOneKeyCombat [slotId]` (chọn Đá rảnh cấp cao nhất cho từng ô đã mở).
  2. **[XONG R7.22D]** `Gem.GemCompose` & `Gem.GemOneKeyCompose`: Mode A nâng cấp tại chỗ Đá đang khảm (`GemLevelUpLayer`), Mode B ghép 4 Đá rảnh từ túi (hỗ trợ `syntheticDoubleUse` Đá Song Sinh), `GemOneKeyCompose` ghép hàng loạt Đá rảnh (không đốt Đá Song Sinh) + red-dot `1413`.
  3. **[XONG R7.22D]** `_slot_gem_bonuses` & `_compute_slot_property`: đọc `slot["Gem"]` (chuẩn 6 phần tử dùng `{}` cho ô rỗng), cộng đủ 11 enum `GemModel.attrStr` (`301..306`, `408`, `409`, `431..433`) vào `Slot["Property"]`, `FAP` và `FightInfo`.
- **File liên quan:** `server/emulator.py`, `server/test_r722d.py`.
- **Độ khó / Rủi ro:** Trung bình / Thấp.
- **Phụ thuộc:** Đã thỏa mãn (R7.21 đã hoàn tất `state["gems"]` & `GemInfo`).
- **Kiểm thử & Nghiệm thu:** `server/test_r722d.py` (5/5 test PASS: khảm/chuyển/tháo/`FightInfo`, `GemOneKeyCombat` + giới hạn cấp, ghép túi + Đá Song Sinh + lỗi biên, nâng cấp tại chỗ, `GemOneKeyCompose` + red-dot `1413` + save/reload).

#### `REC-P1-04` — Cân Bằng Lại Đường Cong Quái Chiến Dịch / Tinh Anh *(ĐÃ HOÀN TẤT R7.26)*
- **Mức phục hồi:** **C có căn cứ** (Đường cong quái Chiến dịch/Tinh Anh dựa trên cấu trúc `needLV`, `Ch 11` giữ nguyên bản 15 kịch bản tân thủ).
- **Trạng thái hoàn tất (`R7.26`):** Đã thay thế phần tính quái tuyến tính ở `Ch 12–80` trong `server/emulator.py:_build_enemy_wave` bằng nội suy log-linear (`_CAMPAIGN_FAP_ANCHORS` + `scale_wave_to_target_fap` trong `server/nightmare_handlers.py`), tăng trơn từ `~8k` (`Ch 12`) lên `~275k` (`Ch 80` `1★`, gấp `~3,0×` mức cũ và bản `3★` nối mượt sang Ác Mộng `550k`), loại bỏ nghịch lý boss `q=6` (`Ch 25`, `Ch 46`) yếu hơn chương trước và giữ nguyên 100% `Ch 11` + `test_emulator.py#test_44`.
- **File đã cập nhật:** `server/nightmare_handlers.py`, `server/emulator.py`, `server/test_r726.py`.

#### `REC-P1-05` — Mở Khóa & Nghiệm Thu 12 Ải Cuối Mộ Thần Binh (Tầng 24–27, Ải 40–51) *(ĐÃ HOÀN TẤT 51/51 ẢI Ở R7.24 + R7.27)*
- **Mức phục hồi:** **B** (Tái dựng có căn cứ từ `BddNodeModel`/`BddPointModel`/`BddClearanceModel`).
- **Bằng chứng:** `server/bdd_handlers.py`, `server/test_r724.py`, `server/test_r727.py`, `TeambattleHeroNpc.lua`, phân tích FAP ở `BALANCE_RECOVERY_AUDIT.md#5.1`.
- **Trạng thái hoàn tất (`R7.24` + `R7.27`):** `R7.24` mở Tầng 24–26 (`48/51` ải); sau khi hoàn tất Chuyển Sinh & `11 UAID` ở `R7.27 (TASK-N02B)`, đã mở trọn vẹn `PLAYABLE_FLOORS = range(11, 28)` (**`51 / 51` ải**) và vượt sạch Tầng 27 (`2711–2713`, `<= 3` lượt) trong `server/test_r727.py` mà không chỉnh sửa `BddPointModel`.
- **File liên quan:** `server/bdd_handlers.py`, `server/reborn_handlers.py`, `server/test_r724.py`, `server/test_r727.py`.

---

### P2 — Độ Sâu Gameplay & Vòng Lặp Endgame (Mở rộng trải nghiệm dài hạn)

#### `REC-P2-01` — Khôi Phục Phó Bản Ác Mộng (`Nightmare`, 65 chương / 639 ải) & Hệ Thống Chuyển Sinh (`RebornInfo`/`RebornShop`) + 11 Tuyệt Kỹ `UAID` *(ĐÃ HOÀN TẤT 100% Ở R7.26 + R7.27)*
- **Mức phục hồi:** **A/B** (100% có đủ 13 bảng VN gốc: 6 bảng `Nightmare*` + 7 bảng `Reborn*`).
- **Trạng thái hoàn tất (`R7.26` `TASK-N02A` + `R7.27` `TASK-N02B`):**
  1. **`R7.26` (`TASK-N02A`):** Trích 5 bảng Ác Mộng/Nguyên liệu, cài đặt `RebornGoods (2701)` & `RebornCoin (1128)`, hoàn thiện 12 RPC thật + `DrawRoadBox` trong `server/nightmare_handlers.py` (`test_r726.py`).
  2. **`R7.27` (`TASK-N02B`):** Trích 6 bảng Chuyển Sinh còn lại (`155/276`), hoàn thiện `server/reborn_handlers.py` (5 RPC `RebornInfo` + 3 RPC `RebornShop`), cộng chỉ số `allAttrStr` / ô khảm / `RebornPrtypeRelation` / Đại Sư `RebornLvActiveModel` / `HeroRebornCheer` / 7 buff `talIDStr`, **kích hoạt 11 Tuyệt Kỹ `UAID` (`1003001..1003011`)**, hoàn trả `HeroRebirth`, và mở nốt Tầng 27 Mộ Thần Binh (`51/51`, `test_r727.py`).

#### `REC-P2-02` — Khôi Phục Trùm Tăng Cấp / Thần Khí (`EquipArtifact`, `1408`) + Triệu Hồi Trang Bị Thường (`Callequip`, `3802`) *(ĐÃ HOÀN TẤT R7.28)*
- **Mức phục hồi:** **A/B** (`EquipArtifactRelation` 1.104 dòng có sẵn VN + `EquipArtifactModel` TW; `CallequipConfig` + `CallequipOutoddsBRelation` có sẵn VN).
- **Trạng thái hoàn tất (`R7.28`):**
  1. Đã trích `EquipArtifactRelation.lua` (1.104 mốc) & `CallequipOutoddsBRelation.lua` (36 dòng) → tổng **`157 / 276`** bảng VN.
  2. `_compute_equip_artifact_state()` tính `EquipModel.itemLv + EquipStepRelation.itemLv` cho 4 loại (`Weapon/Helmet/Clothes/Necklace`), cộng thẳng `APADD/HPADD/DEFADD` vào `Slot.Property` & `FightInfo`, phát `Avatar.EquipArtifactInfo` cho `GetInitData` và khi đổi bậc, và nối chuẩn **`SuccessTarget #37..41`**.
  3. Hoàn thiện **`Callequip.GetCallEquipData` & `Callequip.CallEquip`** (`90m`/`4260m` CD miễn phí, `IsFrist=1` lượt KC đầu đảm bảo Cam, pity `CallCount=9` luân phiên Tím ↔ Cam, ưu đãi `4416`, bạo kích `4419`, nối **`SuccessTarget #12`**) — kiểm chứng trong `server/test_r728.py`.

#### `REC-P2-03` — Khôi Phục Kho Vàng (`GGZJ`, 8 RPC) & Đấu Võ Đại Hội (`Gddh` + `GddhShop`, 10 RPC) *(ĐÃ HOÀN TẤT R7.29)*
- **Mức phục hồi:** **B** (Đủ 10 bảng VN: 4 `Ggzj*` + 6 `Gddh*`).
- **Trạng thái hoàn tất (`R7.29`):**
  1. Đã trích đủ **10 bảng VN** (`ggzj_config`, `ggzj_box_reward` 5, `ggzj_reward_view` 6, `ggzj_system_heroes` 900; `gddh_config`, `gddh_attack_reward` 3, `gddh_buynum` 30, `gddh_shop` 16, `gddh_rank_reward` 36, `gddh_guild_reward` 8) → tổng **`167 / 276`** bảng VN.
  2. Hoàn thiện **Kho Vàng (`GGZJ.*` 8/8 RPC)** trong `server/ggzj_handlers.py` (thuê tướng hệ thống + bạn/bang, đội hình 1–7, đánh/bỏ qua 6 tầng giữ HP địch, rương tuần tự `1..5` + rương cuối tầng, nghỉ chiến `23:50–24:00`, nhân VIP `ggzjMutipleR`, phúc lợi `4415`, reset ngày, chấm đỏ `2504`).
  3. Hoàn thiện **Đấu Võ Đại Hội (`Gddh.*` 8/8 + `GddhShop.*` 2/2 RPC)** trong `server/gddh_handlers.py` (lịch T3–T4 / T5–T6 / T7–T2, nghỉ chiến & kết toán `23:00` về `RewardCenter (2400)`, hồi lượt theo giờ, mua lượt bậc thang `GddhBuynumRelation`, trả thù, đấu TK S1 thật + 80 bot, shop 16 món bán mảnh Kikyo/Kanade Hime/Kaguya, tiền `GDDHCoin (1119)` & `RawGold (2112)` nhân `Lv`, phúc lợi `4414`, chấm đỏ `2503`).
  4. Nối chuẩn **`DailyTask #6/#9`** (đạt **22/25** task hoạt động), **`SuccessTarget #13/#30`**, **`ActiverankingModel #7/#9`** (`ggzj_count * 2`, `gddh_fights * 1`), kiểm chứng trong `server/test_r729.py` (6/6 OK).

#### `REC-P2-04` — Khôi Phục BXH (`LeaderBoard`, XONG `R7.25`), Bạn Bè/Thư (`Friend`/`PlayerEmail`, XONG `R7.30`) & Bang Hội Cục Bộ S1 (`Guild`, `GuildBossInfo`, `GuildReward`, XONG `R7.31`) *(ĐÃ HOÀN TẤT 100% Ở R7.25 + R7.30 + R7.31)*
- **Mức phục hồi:** **B** (`10` bảng `Guild*` mở + `4` bảng `ifOpen=0`, `LeaderboardConfig`, `PlayerLvRelation.friendMax`).
- **Trạng thái hoàn tất (`R7.25` + `R7.30` + `R7.31`):**
  1. **`R7.25` (`LeaderBoard`):** Hoàn tất 3/3 RPC (`RankList`, `Praise`, `Formation`) với 3 tab, 50 hạng TK S1 + NPC, thưởng `10.000` Vàng/ngày/tab (`server/test_r725.py`).
  2. **`R7.30` (`REC-P2-04A`: Bạn Bè & Hộp Thư):** Hoàn tất **19 RPC** trong `server/social_handlers.py` (`Friend.*` 5, `FriendMessage.*` 9, `Enemy.*` 3 gồm nâng `GetEnemyList` từ stub → thật, `PlayerEmail.*` 2): kết bạn 2 chiều giữa các TK S1 + 24 NPC bạn bè cục bộ, tặng/nhận Hoạt Lực (`+2` STA/lượt, cap `20`/ngày, nối **`DailyTask #11`** → `23/25`), danh sách đen `Enemy`, hộp thư chiến báo `PVP`/`Gddh`/`BossBattle.FriendHelp`, chấm đỏ `1700/1701/1900..1903`, xem đội hình `SlotFormations` & mời bạn vào `Teambattle` (`server/test_r730.py`, 6/6 OK).
  3. **`R7.31` (`REC-P2-04B`: Bang Hội Cục Bộ S1):** Trích đủ **10 bảng `Guild*` mở** (`177/276`) và hoàn thiện **38 RPC** trong `server/guild_handlers.py` (`Guild.*` 30, `GuildBossInfo.*` 6, `GuildReward.*` 2): registry `s1_guilds.json` dùng chung đa tài khoản S1 + 3 bang NPC hạt giống (*Tây Quốc*, *Hội Trừ Yêu*, *Bạch Linh Sơn*), duyệt đơn/phân quyền/bãi nhiệm/giải tán, xây dựng (`buildNeedGuildLv=3`), quyên góp & tiền **`Contribution (1113)`**, nâng cấp kiến trúc, Shop Bang 22 món, chia sẻ Lính Thuê liên thông `GGZJ.Hire (hire_type=1)`, Boss Bang (cổ vũ +20%, nghỉ chiến `23:30–24:00`), `GuildReward` nhận thưởng công hội cuối mùa `Gddh`, mời đồng bang `Teambattle`, `LeaderBoard.RankList` `GuildName`, piggyback `GuildAvatar`, chấm đỏ `3400/3402/3403` & nối **`DailyTask #10/#15`** đạt **`25/25` (100%) DailyTask hoạt động** (`server/test_r731.py`, 6/6 OK). *(Các phân hệ `ifOpen=0` trong VN như `3401` Thần Thú, `3404` Đấu Giá `Auction`, `3408..3412` Phó Bản Bang giữ nguyên ngoài phạm vi).*

#### `REC-P2-05` — Hoàn Thiện Kết Toán Hạng Sự Kiện (`4410`, `4421`, `4422`, `4430`), Tiện Ích (`R7.25`) & Trích 5 Bảng Kinh Tế Gốc (`LvPlan`/`VipWelfare`/`Bag`) *(ĐÃ HOÀN TẤT 100% Ở R7.25 + R7.32 — HOÀN TẤT TOÀN BỘ BACKLOG P0/P1/P2)*
- **Mức phục hồi:** **A/B** (`5` bảng VN mới + `4` quy tắc kết toán sự kiện).
- **Trạng thái hoàn tất (`R7.25` + `R7.32`):**
  1. **`R7.25` (`TASK-M06`):** Hoàn tất trọn vẹn **4/4 RPC tiện ích & hợp thành** (`Goods.GoodsSell` gồm `GoodsDjqModel`, `Player.AlterPlayerHeadId`, `Player.AlterPlayerName` dùng thẻ `16050002` hoặc `100` KC, `Treasure.TreasureCompose` 5 Bảo vật Tím + `100.000` Vàng → `16050020` kèm hoàn trả EXP nâng cấp, `server/test_r725.py`).
  2. **`R7.32` (`REC-P2-05B`):**
     - Trích đủ **5 bảng VN vốn hardcode** (`LvPlanConfig`, `LvPlanRewardModel`, `VipWelfareModel`, `BagModel`, `BagExpandUseRelation` → tổng **`182 / 276`** bảng VN) và nối đọc động vào `_bag_info`, `_rpc_bag_expand`, `_rpc_lv_plan_info`/`_rpc_lv_plan_receive`, `_vip_welfare_tuples`, đồng bộ ngày qua `self.clock.today_str()` trong `server/emulator.py`.
     - Hoàn thiện kết toán cuối kỳ (`_on_timed_event_ended` trong `server/event_handlers.py` + `server/r79_event_handlers.py`) đẩy thưởng về `RewardCenter (2400)` cho cả 4 sự kiện **`4410` (`timed_xssb`: BXH `XSSB_RANK_REWARDS` + rương mốc tích lũy chưa nhận)**, **`4421` (`timed_recharge_rank`: ngưỡng `NeedMinNum`)**, **`4422` (`timed_consume_rank`: ngưỡng `NeedMinNum` & `manual_reset`)**, và **`4430` (`timed_active_rank`: ngưỡng `LessScore=20`)**, hỗ trợ nhất quán nhiều tài khoản S1 ngay cả khi peer kết toán trước (`include_archived_peers=True`, `server/test_r732.py` 6/6 OK).

---

### P3 — Nội Dung Mở Rộng & Tùy Chọn Ngoài Baseline VN `5.0.4.98`

| Mã | Nội dung | Mức phục hồi | Điều kiện mở / Trạng thái |
|---|---|---|---|
| `REC-P3-01` | ~~**Lãnh Địa (`CrusadeInfo` / Territory)** — 8 RPC (`SuccessTarget #25`)~~ | **Đã đóng (`R7.33` — Dead Legacy Code)** | Đã xác minh toàn bộ 4 bảng `Crusade*` bị xóa khỏi APK VN/EN/TH/ZH, 0 nơi gọi ngoài `Territory/`, và `ModuleSub[4925]` (`SuccessRewardCrusade`) đã chuyển sang `PB Tổ Đội 2319`. |
| `REC-P3-02` | **Banner Phe `84 / 85 / 86` (Thần Tướng I / S / N)** | **B (Client-blocked)** | Config đã trích đủ trong `game_data.json`, nhưng client VN chưa vá bị chặn bởi `btnPic == ""` (`HomeScene.lua:2871`) và `GoodsOutputRelation[16060037..39].pic == ""` (`LimittedTimedRecruitLayer.lua:495`). Chỉ mở nếu vá client APK. |
| `REC-P3-03` | **Các hệ thống tắt mặc định ở VN (`ifOpen=0`): Luyện Thể (`5700`), Thú Cưng (`7400..7600`), Chiến Trận (`8101..8108`), Trận Quyết (`5400`)** | **B/C** | Chỉ làm nếu chủ dự án quyết định mở rộng vượt phạm vi `VN 5.0.4.98` (cần vá `ModuleSubModel` trên client). |
| `REC-P3-04A` | **8/8 Phúc Lợi Đều (`TimedWelfare 4413..4420`) & `RankScene` Tab 3 (`PVPinter`)** *(ĐÃ HOÀN TẤT `R7.33`)* | **A/B (Đã đạt)** | Đã hoàn thiện `4413` (x2 Đấu Trường `PVPCoin`), `4415` (`RefNum=200`), `4418` (`RefNum="3,6,10,15"` bạo kích ghép trang bị), `4419` (`RefNum="3,6,10,15"` bạo kích gọi trang bị), `4420` (x2 `Merit 1124` BDD) + `PVPinter.GetPVPInterTopRank`/`GetSlotFormations` (`server/test_r733.py` `6/6 OK`, tổng `224/224` tests OK). |
| `REC-P3-04B` | **Lễ Hội `6300/6400` (`20` mã `63xx/64xx`) & `Player.GetPlayerInfo` *(ĐÃ XONG `R7.34`)*; Chiến Liên Server đấu/mùa (`PVPinter`, `PVPinterTop`, `GodDomain`, `ShengyuanWars`) & mở khóa UI/đồng bộ APK** | **A/B (Phần thuần VN đã đạt) / Cổng P4** | **`R7.34` đã hoàn tất 100% phần backend sống (`ifOpen=1`) thuần VN**: 20 sự kiện Lễ Hội opt-in ngoài `DEFAULT_CONCURRENT_EVENTS`, cô lập tiến độ/tiêu nạp/nhận thưởng/`RewardCenter` theo `ActivityId`, `PlayerInfo.ActivityPic/ActivityName`, `Player.GetPlayerInfo` (`server/test_r734.py` `6/6 OK`, tổng `230/230` tests OK). Phần Chiến Liên Server đấu/mùa (`PVPinter`, `PVPinterTop`, `GodDomain`, `ShengyuanWars`) & các hệ `ifOpen=0`/client-blocked chuyển sang **P4 (Cổng Phê Duyệt Đa Vùng / APK)**. |
| `REC-P3-05` | **Nguồn cấp & Cường hóa Trang Bị Kim (`colorLV=8`)** | **D** | Thiếu dữ liệu VN gốc (`0/20` nguồn cấp, thiếu `EquipLvUpuseRelation[8]`). Chỉ mở nếu chủ dự án duyệt thiết kế riêng cho bản offline. |
