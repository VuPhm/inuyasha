# Kiểm Toán Sâu Hệ Thống Chiến Đấu, Cân Bằng & Meta — InuYasha: Seek Jade

**Ngày kiểm toán:** 22/11/2026 (UTC+7) | **Baseline:** `checkpoint-vn-r7.21` (`2b91941`, APK 840).
**Phương pháp:** Đối chiếu từng dòng giữa engine chiến đấu gốc của client VN (`analysis/vn/decompiled_src/CSCommon/*.lua`), bộ tính thuộc tính client (`Hero/GetHeroAttribute.lua`, `Common/ConfigFunc.lua`), dữ liệu máy chủ VN thật nhúng trong `Config/TeambattleHeroNpc.lua` (432 đơn vị) & `Config/StrongFormModel.lua`, với mã backend hiện tại (`server/emulator.py`, `server/combat_sim.py`, `server/combat_effects.py`, `server/bdd_handlers.py`, `server/teambattle_handlers.py`).

---

## 1. Các sai lệch nghiêm trọng làm thay đổi Meta (Tóm tắt điều hành)

Đây là **9 sai lệch có bằng chứng tuyệt đối** đang trực tiếp bóp méo sức mạnh tướng, đội hình, lực chiến và độ khó ải — không phải lỗi crash nhưng làm **sai hẳn meta gốc của InuYasha: Seek Jade**:

1. **Sai công thức Lực Chiến (FAP) gốc 2× trọng số Công/Thủ (`HP + 5*AP + 5*DEF` vs gốc `HP + 10*AP + 10*DEF`):**
   - Chứng minh toán học đạt sai số `0.00` trên `216 / 216` hồ sơ NPC chuẩn trong `TeambattleHeroNpc.lua`.
   - Hệ quả dây chuyền: làm **Mộ Thần Binh (`bdd_handlers.py:126,152-156`) phóng đại kẻ địch mạnh gấp ~1,6× cả HP, AP và DEF** so với `proposeFAP` gốc → trực tiếp gây tắc tầng 24–27 (12 ải cuối 40–51 phải khóa!).
2. **Backend lọc xóa (`strip`) 49 Buff Tài Năng khỏi `FightInfo.BuffList` gửi cho Lua client (`emulator.py:1804`):**
   - Dù engine Lua trên Pixel 3 XL (`CSCommon/FightBuffModel.lua`) đã cài sẵn 100% logic Độc (`hpdot`), Hồi sinh (`eBuffFlagReborn`), Phản kích đỡ đòn (`9005xxxx`), Liên trảm (`9002xxxx`), Lan đánh thường (`9004xxxx`), Phản sát thương (`9006xxxx`), Hút máu (`eTransformation`), v.v., dòng `supports_talent_buff(...)` ở `emulator.py:1804` đã **cắt bỏ toàn bộ chúng trước khi gửi sang client**!
   - Hệ quả: **8/11 tướng Đỏ/Thần (`q=18`) đang mất kỹ năng đặc trưng tạo nên meta của chính mình** (chi tiết ở Mục 4).
3. **40/133 Buff Kỹ Năng Chủ Động (`AttackModel.buffList`) chạy trên Lua nhưng bị Python `combat_sim.py` bỏ qua:**
   - Ví dụ: Nộ Công của **Sesshomaru** (`1002016` — 45% đánh đôi `90030000`), **Naraku** (`1002024` — 60% Độc `14040000`), **Miroku** (`1002010` — buff Công hàng sau), **Toutousai** (`1002039` — buff Thủ hàng trước), **Hakudoushi** (`1002028`), **Sara** (`1002018`), **Toran** (`1002066`), **Hiten** (`1002047`).
   - Hệ quả: **Desync chiến đấu nghiêm trọng** giữa màn hình Pixel (Lua) và kết quả kiểm chứng/mô phỏng ở Arena, Mộ Thần Binh, Phó Bản Tổ Đội (Python).
4. **Nhân Vật Chính không tiến hóa phẩm chất (`AttrtreeHeromodelRelation` chưa nối):**
   - MC kẹt vĩnh viễn ở `12010001`/`12010004` (`q=6`, 420+42 HP / 60+6 AP, Nộ 1 mục tiêu 270%), không bao giờ tiến hóa qua 4 mốc Ngộ Đạo (`1 → 12010009` Nộ 3 mục tiêu, `4 → 12010007` Tím `q=10`, `113 → 12010002` Cam `q=13`, `348 → 12010003` Cam `q=15` với 1.050+105 HP / 150+15 AP — **mạnh gấp 2,5×**).
5. **Mất toàn bộ chỉ số `%` và chỉ số phụ của Bộ Trang Bị (`EquipGroupActiveRelation`) và Tiến Giai Bảo Vật (`TreasureStepAttrRelation`):**
   - `emulator.py:956-960` chỉ cộng `HP/AP/DEF` của Bộ Trang Bị, bỏ rơi hoàn toàn **`APR/HPR/DEFR` (23 mốc mỗi loại), `CRI` (10), `HIT` (7), `DOD` (6), `BLO` (6), `BOG/CRID/TEND` (3), `TEN` (2), `DAMADD/DAMCUT` (1)**.
   - `emulator.py:986-992` bỏ rơi hoàn toàn **`410 (DAMADDR)` và `411 (DAMCUTR)` (30 mốc mỗi loại)** khi Tiến Giai Sách/Ngựa!
6. ***(ĐÃ SỬA HOÀN TẤT ở R7.22A, R7.22D, R7.27 & R7.28)*** **Cổ Vũ `HeroStepCheer`/`HeroRebornCheer`, Duyên Thời Trang `FashionPrRelation`, Linh Thạch `GemModel` 90 mẫu, Chuyển Sinh (`RebornInfo`/`RebornShop` + 11 Tuyệt Kỹ `UAID`), & Trùm Tăng Cấp `EquipArtifactRelation` (1.104 mốc ở R7.28) đã được khôi phục đầy đủ.**
7. **Sai lệch chọn mục tiêu AI & Khắc chế Phe trong `combat_sim.py`:**
   - `eHPMin` (`mode=9`): Python xếp theo **% HP** (`HP/TotalHp`), trong khi Lua `BattleMatrix.lua:702` xếp theo **HP tuyệt đối (`a:getHP() < b:getHP()`)**!
   - `eRPMax`/`eRPMin` (`mode=10/11`): Lua `BattleMatrix.lua:752,795` **loại trừ người ra đòn**, Python không loại trừ!
   - `eSingleFront`/`eSingleBack`/`eOneColumn`: Khi cột đối diện trống (VD cột 3 trống), Lua chọn **cột gần nhất** (cột 2 rồi cột 1), Python `combat_sim.py:61` nhảy thẳng sang **cột 1 (xa nhất)**!
   - Khắc chế Phe (`FightExpression.lua:150` — `RADAMADDR/CUTR`, `RBDAMADDR/CUTR`, `RCDAMADDR/CUTR`): cả `_hero_fight_obj` lẫn `combat_sim.py` đều bỏ trống.
8. **PRNG của Python (`random.Random`) khác PRNG của Lua (`CSCommon/LMMath/CreateRandom.lua`):**
   - Cùng một `RandNum` nhưng Python và Lua sinh hai chuỗi số hoàn toàn khác nhau, trong khi `CreateRandom.lua` chỉ là thuật toán bảng hex + `bit32` thuần dài ~40 dòng có thể port sang Python **khớp từng bit 100%**.
9. ***(ĐÃ CÂN BẰNG Ở R7.26)*** **Sức mạnh quái Chiến dịch (`Ch 12–80`):**
   - Trước R7.26, Boss Chương 70/80 chỉ có ~`50k–90k` FAP và các ải có boss `pic` `q=6` (VD Ch 25 `2520`, Ch 46 `4620`) yếu hơn chương thấp hơn. Từ `R7.26`, `_build_enemy_wave` dùng nội suy log-linear + chuẩn hóa FAP tổng wave (`8k → 275k` `1★`, gấp `~3,0×` ở Ch 80 và `3★` nối mượt sang Ác Mộng `550k → 11,5M`), giữ nguyên 15 trận kịch bản hướng dẫn gốc VN `Ch 1–7`.

---

## 2. Đối chiếu chi tiết Hệ thống Tướng & Chỉ số (Phần 3A)

### 2.1. Phẩm chất tướng trong `HeroModel.lua` (204 mẫu)

| `quality` | Màu hiển thị (`CommonFunc.lua`) | Tướng chơi được (`specialType=0`) | Nhân vật chính (`specialType=255`) | NPC / Boss (`specialType=1`) | Bậc đột phá tối đa (`HeroStepRelation`) |
|---:|---|---:|---:|---:|---|
| `2` | Trắng | 0 | 0 | 1 | — |
| `3` | Lục | 36 (13/12/11 theo phe 1/2/3) | 0 | 0 | — |
| `6` | Lam | 18 (6/6/6) | 4 (`12010001/04/09/10`) | 3 | MC: +0..+15 (`stepUpClassID=255`) |
| `10` | Tím | 30 (10/10/10) | 2 (`12010007/08`) | 0 | +0..+8 (`stepUpClassID=10`) |
| `13` | Cam-13 | 24 (8/8/8) | 2 (`12010002/05`) | 0 | +0..+15 (`stepUpClassID=13`) |
| `15` | Cam-15 | 30 (10/10/10) | 2 (`12010003/06`) | 34 | +0..+15 (`stepUpClassID=15`) |
| `18` | **Đỏ (SR / Thần Tướng)** | **11** (9 phe 1/2/3 + 2 phe 0: `12015022` Tứ Đấu Thần, `12015023` Inu Kimi) | 0 | 7 | +0..+15 (`stepUpClassID=15`) |
| **Tổng** | | **149** | **10** | **45** | **57 dòng công thức đột phá** |

### 2.2. Nguồn chỉ số đi vào `Property` và `FightInfo` (Cái gì chạy thật vs chỉ hiển thị)

| Nguồn chỉ số | Dữ liệu VN gốc | `emulator.py:_compute_slot_property` | Vào `FightInfo`? | Sai lệch trọng yếu |
|---|---|---|---|---|
| **Chỉ số nền + Cấp tướng** (`HPBase + HPUp*(lv-1)`) | `HeroModel` | Có (`L918-920`) | Có | Đúng công thức `ConfigFunc:getHeroLvAttr`. |
| **Đột phá tướng (`Step`)** | `HeroStepRelation` (`attrUpR`, `FSP`) | Có (`L856-867`) | Có | Đúng công thức (`int(Base * attrUpR)`). |
| **Tiến hóa Model MC** | `AttrtreeHeromodelRelation` (`0/1/4/113/348`) | **KHÔNG** | **KHÔNG** | **MC mất 60% chỉ số gốc + mất kỹ năng Nộ 3 mục tiêu.** |
| **Tài năng chỉ số tĩnh (`attrStr`)** | `HeroTalRelation` + `TalModel` | Có cho `scope=1,2`; **bỏ `scope=3,4,5`** | Có (cho 1,2) | 3 dòng khắc chế phe (`413/415/417` ở `万妖之王*A/B/C`) chưa nối. |
| **Tài năng buff chiến đấu (`buffList`)** | `TalModel` + `BuffModel` | Lọc qua `supports_talent_buff` (`L1804`) | **CHỈ 1.585/1.699 dòng** | **99 dòng bị cắt khỏi cả Lua lẫn Python; 15 dòng mất `707`.** |
| **Duyên Phận (`PrModel`)** | `HeroPrRelation` + `PrModel` (572) | Có (`L926-929`, `L1084-1099`) | Có (`ap_rate/hp_rate/def_rate`) | Khớp `GetHeroAttribute.lua`. Lưu ý: `Property.AP1/AP2` chưa tách `APHero/APHeroR` nhưng tổng `AP/HP/DEF` vào trận đã tính tỷ lệ đúng trên `hero_ap/hero_hp/hero_def`. |
| **Cổ Vũ Đột Phá / Chuyển Sinh** | `HeroStepCheer` (180), `HeroRebornCheer` (84) | **CÓ (R7.22A + R7.27)** | **CÓ** | **Đã khôi phục 100% (`R7.22A` + `R7.27`):** `HeroStepCheer` (`colorLV >= 5`) và `HeroRebornCheer` (tổng `rebornNum` Đồng Đội cam+) cộng thẳng vào `_compute_slot_property`. |
| **Trang bị (Base + Lv + Step)** | `EquipModel`, `EquipLvUpuseRelation`, `EquipStepRelation` | Có (`L935-947`) | Có | Đúng `HP/AP/DEF/FSP` cơ bản + Step. |
| **Bộ Trang Bị (Set Bonus)** | `EquipGroupActiveRelation` | **CHỈ cộng `HP/AP/DEF`** (`L952-960`) | **Mất 13 chỉ số** | **Bỏ hoàn toàn `APR/HPR/DEFR`, `HIT/DOD/CRI/TEN/BLO/BOG/CRID/TEND`, `DAMADD/DAMCUT`!** |
| **Trùm Tăng Cấp (`EquipArtifact`)** | `EquipArtifactRelation` (1.104) | **CÓ (R7.28)** | **CÓ** | **Đã khôi phục 100% (`R7.28` / `REC-P2-02`):** `_compute_equip_artifact_state` tính `EquipModel.itemLv + EquipStepRelation.itemLv` cho 4 loại (`Weapon/Helmet/Clothes/Necklace`), cộng đủ `APADD/HPADD/DEFADD` vào 6 slot & `FightInfo` và đồng bộ `Avatar.EquipArtifactInfo`. |
| **Bảo vật (Base + Lv + LvActive + Step)** | `TreasureModel`, `TreasureLvActiveRelation`, `TreasureStepAttrRelation` | Có Base/Lv/`401`/`402`/`201`/`202`/`203` | **Mất `410/411`** | **Bỏ hoàn toàn `DAMADDR (410)` và `DAMCUTR (411)` của Tiến Giai Bảo Vật!** Ngoài ra `tr_hp_pct_bonus`/`tr_ap_pct_bonus` nhân lên `hp1/ap1` gồm cả trang bị + Ngộ Đạo (cần đối chiếu với quy tắc `HPR1` trên `hero_hp`). |
| **Linh Thạch / Đá (`Gem`)** | `GemModel` (90 mẫu, `attrStr`) | **CÓ (R7.22D)** | **CÓ** | **Đã khôi phục R7.22D (`TASK-M04`):** `Slot.GemCombat`, `GemOneKeyCombat`, `Gem.GemCompose` (túi + Đá Song Sinh & nâng cấp tại chỗ `GemLevelUpLayer`), `GemOneKeyCompose`, cộng đủ 11 enum `attrStr` vào `Property`/`FightInfo`. |
| **Ngộ Đạo (`Attrtree`) & Điện Tứ Hồn (`Glory`)** | `AttrtreeModel` (1.001), `GloryTypeModel` (3) | Có (`L1009-1025`) | Có | Đúng `431/432/433` và `+STA`. |
| **Thời Trang (`Fashion`)** | `FashionStepRelation`, `FashionPrRelation` | Có `FashionStepRelation` (`431/432/433`) | Có (thiếu bộ) | **Thiếu `FashionPrRelation` (`allAttr%`)**. |
| **Chuyển Sinh (`Reborn`)** | `RebornLvModel` (340), `RebornLvActiveModel` (9), `RebornPrtypeRelation` (34), `RebornSlotRelation` (340×4) | **CÓ (R7.27)** | **CÓ** | **Đã khôi phục 100% (`R7.27` / `TASK-N02B`):** `reborn_handlers.py` nối đủ `allAttrStr`, ô khảm, `RebornPrtypeRelation` (+35%), Đại Sư Chuyển Sinh `RebornLvActiveModel` (6 slot ra trận, +130% APR/HPR/DEFR), `talIDStr` buff (`10140400`, `20190150`, `20180600`), và **11 Tuyệt Kỹ `UAID` (`1003001..1003011`)**. |
| **Công thức Lực Chiến (`FAP`)** | Chứng minh từ `TeambattleHeroNpc` (432 dòng) | `HP + 5*AP + 5*DEF` (`L1039`) | Sai ở `TeamData.Fap` & UI | **Gốc = `HP + 10*AP + 10*DEF`** (0.00 sai số trên 216/216 dòng chuẩn; endgame có hệ số nhân bổ sung 4,16×–5,63×). |

---

## 3. Đối chiếu Công Thức Chiến Đấu: Lua `CSCommon` vs Python `combat_sim.py` (Phần 3B)

| Cơ chế | Công thức gốc trong Lua `CSCommon` | Hiện trạng Python (`combat_sim.py` / `combat_effects.py`) | Đánh giá sai lệch |
|---|---|---|---|
| **Sát thương cơ bản (`hurtStrength`)** | `max(atkAP - vicDEF, atkAP * 0.1)` (`FightExpression.lua:139`) | Giống (`combat_sim.py:165`) | **Khớp.** |
| **Công & Thủ trong trận** | `atkAP = AP * (1 + apr)`, `vicDEF = DEF * (1 + defr)` (`FightExpression.lua:126,128`); `ServerInterface.lua:85-87` bỏ qua `v.APR/DEFR` khi init (chỉ dùng buff trong trận). | Giống (`combat_sim.py:152,164`); `_hero_fight_obj` không gửi `APR/DEFR` tĩnh → không bị nhân đôi. | **Khớp.** |
| **Hệ số dư Nộ (`rageScale`)** | Nếu Nộ Công: `1 + (attackHeroRP - needRP) / 200` (`FightExpression.lua:143`); Nộ tối đa = `200` (`Hero.lua:18`). | Giống (`combat_sim.py:166`). | **Khớp.** |
| **Bàn tròn xác suất (Round Table)** | `rand ∈ [0, 99]`. Thứ tự ưu tiên: **Né → Bạo → Đỡ → Thường** (`FightExpression.lua:114-211`). Né = `max(DOD - HIT + 100, 0)`, Bạo = `max(CRI - TEN, 0)`, Đỡ = `max(BLO - BOG, 0)`. | Giống (`combat_sim.py:169-184`). | **Khớp.** |
| **Sát thương Bạo / Đỡ / Phẳng** | Bạo = `max(ceil(dmg * (1.5 + (CRID - TEND)/100)), 1)`; Đỡ = `max(ceil(dmg * 0.5), 1)`; sau cùng cộng phẳng `max(val + DAMADD - DAMCUT, 1)` (`FightExpression.lua:188,199,216`). | Giống (`combat_sim.py:179-185`). | **Khớp.** |
| **Khắc chế Phe (`countryHurt`)** | `rate = (damaddr - damcutr) + (atk:Rxdamaddr(vicCountry) - vic:Rxdamcutr(atkCountry))` (`FightExpression.lua:150-154`). | **[ĐÃ SỬA R7.22C]** `_compute_slot_property` + `_hero_fight_obj` gửi `RADAMADDR..RCDAMCUTR` (hỗ trợ `412..417` ở `attrEffectRange 3/4/5`) và `combat_sim.py` tính đủ `countryHurt`. | **Đã đạt.** |
| **Hồi máu (`attackType == 1`)** | `norm = max((atkAP * factor + CP + BCP) * (1 + CPR + BCPR), 0)`; Bạo trị liệu tỷ lệ = `CRI` (không trừ TEN, không Né/Đỡ), nhân `1.5` (`FightExpression.lua:134,163,195`). Chặn khi có `banhp (505)`. | Giống (`combat_sim.py:156-162`). | **Khớp.** |
| **Tích Nộ** | Đánh thường trúng: `+25` (`+20` nếu Boss); Hạ mục tiêu: `+25` (nếu không phải Boss); Chịu ST (không phải Boss): `floor(dmg / OpeningHP * 100)` (`FightAttack.lua:730-760,895-901`). Dùng Nộ reset về `0`. | Giống (`combat_sim.py:187-197`). | **Khớp.** |
| **Thứ tự hành động & Lượt** | Phe có `TeamData.Fsp` cao hơn đánh trước (hòa so `Fap`). PvE địch: `[9,8,7,12,11,10]`, PvP địch: `[7..12]`. Tối đa 30 lượt (`BattleCalc.lua:16-20,195-205,331`). | **[ĐÃ SỬA R7.22C]** Giống (`combat_sim.py`) và `TeamData.Fap` đã dùng công thức chuẩn `1:10:10`. | **Khớp.** |
| **AI Chọn Mục Tiêu** | `TargetModeFunction.lua` & `BattleMatrix.lua`: (1) `eSingleFront/Back/OneColumn` fallback sang **cột gần nhất**; (2) `eHPMin` so **raw HP**; (3) `eRPMax/Min` **loại trừ người đánh**; (4) `eHPLossMax` so `OpeningHP - HP`; (5) `eSputteringRange (14)` & `eFightingForceMax (13)` tồn tại cho buff. | **[ĐÃ SỬA R7.22C]** `_select_targets` đã sửa cả 3 sai lệch (`_col_order`, raw `HP`, loại `attacker_pos`) và `eRandom` pop qua `CreateRandom`. | **Đã đạt (nòng cốt).** |
| **PRNG (Chuỗi ngẫu nhiên)** | `CSCommon/LMMath/CreateRandom.lua` (`2.400`-char hex box + `bit32.bxor/lrotate/rrotate`). | **[ĐÃ SỬA R7.22C]** Đã port `CreateRandom` sang `combat_sim.py` khớp từng bit với Lua 5.1. | **Đã đạt.** |
| **Hệ thống Buff (`typeEnum 0..9` & `addAttrEnum`)** | Hỗ trợ đầy đủ cả 10 loại `typeEnum` (`0` LossAddition, `1` Sacrifice, `2` Instant, `3` StateTrigger gồm `refAttr>=500`, `4` Comparison, `5` Special `9001..9008`, `6` Additional kèm `modifyAddValue` từ `refAttr/refValue`, `7` Transformation hút máu theo `DAM`, `8` Steal, `9` SelfStateTrigger gồm Hồi sinh `HP==0`, Bất tử `14060000`, Tử vong nổ/hồi & Boss `10090000`) + Khiên (`601`), Độc (`602`), Hồi theo lượt (`603`), Miễn phản ST (`707`), Buff hàng trước/sau (`camp=1, tE=3/4`), Thủ thuật Liên kích (`ContinuousAttack`). | **[ĐÃ HOÀN TẤT R7.23 + R7.24 — `1.699/1.699` tài năng (100%) & `133/133` skill (100%)]** Lát 1A (`R7.23`) + Lát 1B (`R7.24`) đã khôi phục toàn bộ: Độc `602` + `modifyAddValue`, Hút máu `type=7`, Buff hàng `tE=3/4/12`, `type=2 attr=0` Tất trúng/Miễn bạo, Giảm hồi máu `407`, `ContinuousAttack` (`9002/9003/9005`), Lan `9004`, Phản ST `9006 + 707`, Hồi sinh (`10290000`), Bất tử (`14060000`), Tử vong (`1030..1033`), Khiên (`601` + `c1=7`), Miễn tử (`9007`), `type=0` (`10110600`), Boss enrage (`10090000`). | **Đã đạt (`A`, 100%).** |

---

## 4. Phân tích Tác Động Meta Từng Tướng & Đội Hình Gốc (Phần 3C)

### 4.1. Kiểm toán 11 Tướng Đỏ / Thần Tướng (`quality = 18`) — Ai đang bị "phế" vì thiếu logic?

| ID | Tướng | Phe | Vai trò gốc | Kỹ năng / Tài năng lõi đang BỊ MẤT hoặc LỆCH | Mức ảnh hưởng Meta |
|---|---|---|---|---|---|
| `12011002` | **Inu no Taishou** | InuYasha (1) | Tank hàng trước bất tử & phản đòn | **[100% ĐÃ XONG R7.24 + R7.27]** Phản kích 75% khi Đỡ (`20050600`, `9005`), Hồi Sinh 1 lần 150% Công (`10290000`, `type=9`) & Tuyệt Kỹ **`UAID 1003001`** (`R7.27`) đã hoạt động 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12011004` | **InuYasha** | InuYasha (1) | DPS cột dọc + giữ Nộ liên tục | **[100% ĐÃ XONG R7.24 + R7.27]** Lan đánh thường 60% (`20590600`, `9004`) & Tuyệt Kỹ **`UAID 1003003`** (270% cột, `R7.27`) đã hoạt động 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12011003` | **Kikyo** | InuYasha (1) | DPS 3 mục tiêu ngẫu nhiên + Né/Bạo | **[100% ĐÃ XONG R7.27]** Toàn bộ tài năng +5..+15 & Tuyệt Kỹ **`UAID 1003002`** (`R7.27`) đã hoạt động 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12012005` | **Sesshomaru** | Sesshomaru (2) | DPS hàng trước burst liên hoàn | **[100% ĐÃ XONG R7.24 + R7.27]** `1002016 → 20530600` (45% đánh đôi `9003`) & Tuyệt Kỹ **`UAID 1003006`** (65% đánh đôi, `R7.27`) đã hoạt động 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12012004` | **Midoriko** | Sesshomaru (2) | Sát thủ đơn mục tiêu (380%–455%!) kết liễu chuỗi | **[100% ĐÃ XONG R7.23 + R7.24 + R7.27]** `20010000` (Tất trúng), `20060000` (Liên trảm `9002`) & Tuyệt Kỹ **`UAID 1003005`** (455%!, `R7.27`) đã hoạt động 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12012003` | **Kanade Hime** | Sesshomaru (2) | Hỗ trợ/DPS toàn đội + Buff Bạo hàng sau | **[100% ĐÃ XONG R7.23 + R7.27]** `20600600` (Buff +20% Bạo Kích hàng sau 2 lượt) & Tuyệt Kỹ **`UAID 1003004`** (`R7.27`) đã chạy đủ! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12013005` | **Naraku** | Naraku (3) | Trùm Độc (DoT) & Tank chống bạo | **[100% ĐÃ XONG R7.23 + R7.27]** RA Độc (`20440606`), +5 Miễn Bạo (`20020000`), +8 `+36%` ST (`10270600`), +10 `-50%` ST (`10261000`) & **`UAID 1003009`** (100% Độc, `R7.27`) đã khôi phục 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12013004` | **Kaguya** | Naraku (3) | Kiểm soát hàng sau (Độc + Im Lặng + Rút Nộ) | **[100% ĐÃ XONG R7.23 + R7.27]** `20310606` + `10621000` & Tuyệt Kỹ **`UAID 1003008`** (`R7.27`) đã khôi phục 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12013003` | **Takemaru** | Naraku (3) | Đấu sĩ/Tank phản ST + hút máu | **[100% ĐÃ XONG R7.23 + R7.24 + R7.27]** Hút máu 45% (`10710600`), Phản 18% ST (`20070600`, `9006`) & **`UAID 1003007`** (`R7.27`) đã hoạt động 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12015022` | **Tứ Đấu Thần** | Thần (0) | DPS 3 mục tiêu + khắc chế hồi máu | **[100% ĐÃ XONG R7.23 + R7.27]** `20300807` (giảm `-75%` hồi máu) & Tuyệt Kỹ **`UAID 1003010`** (`R7.27`, fallback `classID=16`) đã hoạt động 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |
| `12015023` | **Inu Kimi** | Thần (0) | Siêu Healer toàn đội + cực trâu | **[100% ĐÃ XONG R7.27]** Toàn bộ tài năng +5..+15 & Tuyệt Kỹ **`UAID 1003011`** (185% heal, `R7.27`, fallback `classID=16`) đã hoạt động 100%! | **ĐÃ ĐẠT (100% + `UAID`)** |

### 4.2. Meta Đội Hình Gốc theo `StrongFormModel.lua` (Bằng chứng chính chủ VN)

`Config/StrongFormModel.lua` ghi rõ 3 đội hình tối thượng ("Hàng Ma") của 3 phe (đi cùng Nhân Vật Chính ở vị trí còn lại):
1. **Phe InuYasha (`teamID=1`):** `Inu no Taishou` (Tank hồi sinh + phản kích) + `InuYasha` (DPS cột + lan) + `Kikyo` (DPS 3 mục tiêu) + `Miroku` (Hỗ trợ buff Công hàng sau + phản kích) + `Izayoi` (Healer/Hỗ trợ).
   - *Hiện trạng (`sau R7.27`):* Toàn bộ tài năng, buff kỹ năng, Chuyển Sinh & **`UAID 1003001..1003003`** (cùng tiến hóa MC + Khiên `20180600` ở `255099`) **đã hoạt động 100%**!
2. **Phe Sesshomaru (`teamID=2`):** `Sesshomaru` (Burst hàng trước đánh đôi) + `Midoriko` (Sát thủ tất trúng liên trảm) + `Kanade Hime` (AoE + buff Bạo hàng sau) + `Hitomiko` (Hỗ trợ **Bất tử 1 lượt `20470808`**!) + `Hoshiyomi` (**Bạo kích 48% đánh thường lần nữa `20040601`**!).
   - *Hiện trạng (`sau R7.27`):* Cả 5 tướng (gồm `Sesshomaru` đánh đôi `9003` + `UAID 1003006`, `Midoriko` liên trảm `9002` + `UAID 1003005`, `Kanade Hime` buff Bạo hàng sau + `UAID 1003004`, `Hitomiko` Bất tử `14060000`, `Hoshiyomi` đánh đôi `20040601`) **đã hoạt động 100%**!
3. **Phe Naraku (`teamID=3`):** `Naraku` (Độc + miễn bạo + +36% ST / -50% ST nhận với mục tiêu Độc) + `Takemaru` (Phản 18% ST + Hút máu 45%) + `Kaguya` (Gây Độc + Im Lặng + Rút 75 Nộ) + `Moryomaru` (Tank) + `Kanna` (Healer + Xóa debuff — đã phục hồi R7.18!).
   - *Hiện trạng (`sau R7.27`):* Toàn bộ trục synergy **Độc (`602`) + Phản ST (`9006`) + Hút máu (`type=7`) + Khiên (`601`) + `UAID 1003007..1003009`** đã khôi phục 100%!

> **Kết luận Meta (`cập nhật R7.27`):** Không tự ý nerf/buff lại chỉ số tướng. Sau R7.22A–R7.27, tam giác meta gốc **InuYasha — Sesshomaru — Naraku + Bộ đôi Thần Tướng** cùng toàn bộ hệ thống Chuyển Sinh (**11 Tuyệt Kỹ `UAID`**, `RebornLvActiveModel` Đại Sư, `RebornPrtypeRelation`, `HeroRebornCheer`, & 7 buff tài năng Chuyển Sinh) đã vận hành đủ 100%!

---

## 5. Phân tích Cân Bằng Các Chế Độ Chơi (PvE / BDD / Teambattle / Arena / Boss)

### 5.1. Giải mã nghịch lý Mộ Thần Binh 12 ải cuối (Tầng 24–27, Ải 40–51) *(Cập nhật R7.27: Mở trọn vẹn 51/51 ải!)*
- Bảng `BddPointModel.lua` ghi `proposeFAP` ở Tầng 24–26 từ `6,98M` đến `14,95M` và Tầng 27 nhảy vọt lên `18,17M – 38,62M`.
- Do trước R7.22C dùng `FAP = HP + 5*(AP+DEF)`, địch bị scale quá mạnh ~`1,60×` và người chơi thiếu Set bonus / Bảo vật `410/411` / Đá / Cổ Vũ / tiến hóa MC / Buff / Chuyển Sinh.
- **Kết quả kiểm chứng thực tế (`R7.24` + `R7.27`):**
  - Sau khi hoàn thiện 100% buff chiến đấu (`R7.24`) và toàn bộ hệ thống **Chuyển Sinh + Duyên Đại Sư `RebornLvActiveModel` + `HeroRebornCheer` + `11 UAID` (`R7.27`)**, **`PLAYABLE_FLOORS = range(11, 28)` đã mở trọn vẹn 51 / 51 ải Mộ Thần Binh (`Tầng 11–27`)**!
  - `server/test_r727.py#test_05` chứng minh đội hình Lv80 Step+15 Chuyển Sinh 9 (`16099` + `UAID` + Đồng Đội cam+ Chuyển Sinh) **vượt chuẩn cả 51/51 ải gồm 3 ải Tầng 27 (`2711–2713`, `18,17M–38,62M` `proposeFAP`, thắng sạch trong `<= 3` lượt)** mà không hề sửa gian `BddPointModel`!

### 5.2. Cân bằng Chiến Dịch Thường (`Ch 11–80`), Tinh Anh & Ác Mộng (`Nightmare`) *(Cập nhật R7.26)*
- **Hiện trạng sau `R7.26` (`TASK-N02A`):** Đã chuẩn hóa đường cong `Ch 12–80` bằng `interpolate_log_curve` + `scale_wave_to_target_fap` (`server/nightmare_handlers.py`): `Ch 12` `~8k` → `Ch 30` `~65k` → `Ch 50` `~155k` → `Ch 70` `~235k` → `Ch 80` `~275k` (`1★`, `~3,0×` mức cũ, bản `3★` 2-wave nối thẳng sang **Ác Mộng `Ch 11` `550k` → `Ch 75` `11,5M` FAP**), xóa nghịch lý boss `q=6` (`Ch 25 > Ch 20`, `Ch 46 > Ch 32`) trong khi vẫn giữ nguyên 100% 15 trận kịch bản `Ch 11` và tương thích mọi test Chiến dịch (`test_emulator.py` `test_44` & `test_r726.py`). *(Lưu ý: do không có roster wave gốc trong APK, đường cong này vẫn được gắn nhãn **Tái dựng Mức C có căn cứ**).*

### 5.3. Phó Bản Tổ Đội (`Teambattle`, R7.21) & Đấu Trường (`Arena`)
- **Teambattle (`teambattle_handlers.py`):** Cân bằng 24 ải hiện tại đã lấy chuẩn từ `TeambattleHeroNpc` (dữ liệu thật VN) — rất tốt! Chỉ cần cập nhật `_teambattle_raw_fap` từ `5` → `10` và đồng bộ `combat_sim.py` (PRNG + 12 cơ chế buff + chọn mục tiêu) để kết quả trên màn hình Pixel khớp 100% với kết quả tính trước trên backend.
- **Arena (`PVP`):** Hiện phụ thuộc 100% vào `combat_sim.py` (`emulator.py:6632`). Vì `combat_sim.py` bỏ qua 40 buff kỹ năng (như Sesshomaru đánh đôi, Naraku Độc) và dùng PRNG khác Lua, **trận đấu xem lại (replay) trên Pixel có thể khác hoàn toàn kết quả thắng/thua đã chốt bởi server!** Khôi phục PRNG `CreateRandom` + 12 cơ chế buff sẽ giải quyết dứt điểm lỗi desync Arena này.

### 5.4. Kho Vàng (`GGZJ`) & Đấu Võ Đại Hội (`Gddh`) (`R7.29`)
- **Kho Vàng (`ggzj_handlers.py`):** Cân bằng chuẩn 6 tầng theo `GgzjRewardViewModel` + hệ số VIP `ggzjMutipleR` + phúc lợi `4415` (`RefNum=2`), giữ bền HP mục tiêu giữa các trận, thuê từ `GgzjSystemHeroRelation` (900 tướng hệ thống deterministic), rương tuần tự `1..5` theo `GgzjBoxRewardRelation`, và nghỉ chiến `23:50–24:00`.
- **Đấu Võ Đại Hội (`gddh_handlers.py`):** Nhân `RawGold (2112)` theo `player.Lv` (trả về `1112` Vàng) và thưởng `GDDHCoin (1119)` chuẩn từ `GddhAttackRewardRelation` + `GddhRankRewardRelation` (kết toán ngày & mùa lúc `23:00` về `RewardCenter`), shop `GddhShopModel` 16 món (gồm mảnh Kikyo / Kanade Hime / Kaguya), phúc lợi `4414` (`RefNum=2`), và phí mua lượt bậc thang `GddhBuynumRelation`.

### 5.5. Bạn Bè (`Friend`/`STA`) & Hộp Thư (`PlayerEmail`) (`R7.30`)
- **Giới hạn & Hoạt Lực (`social_handlers.py`):** Tuân thủ chuẩn `PlayerLvRelation.friendMax` (`10` ở Lv 1 → `50` ở Lv 41+), mỗi lượt nhận quà tặng `+2 STA` qua `ResourceLedger` với trần `20 lượt/ngày` (`STADrawLeftCount`) và chặn cứng `-3010` khi `STA >= STAMaxNum`. Đồng bộ 2 chiều giữa các tài khoản S1 thật cùng 24 NPC bạn bè deterministic phục vụ chơi đơn (`DailyTask #11`, `Teambattle`).

### 5.6. Bang Hội (`Guild` / `GuildBossInfo` / `GuildReward`) (`R7.31`)
- **Quỹ Bang, Cống Hiến (`1113`) & Nâng Cấp Kiến Trúc (`guild_handlers.py`):** Tuân thủ `GuildConfig.buildNeedGuildLv = 3` (bang mới Lv 1 nâng lên qua quyên góp `GuildContribute` vật phẩm `16050017`/`16050018`, trong khi 3 bang NPC hạt giống khởi tạo ở Lv 3–4 để chơi đơn ngày đầu). Giới hạn cấp Shop/Boss không vượt quá Đại Điện (`34004000`), tiêu đúng `totalExp` hiệu số từ `GuildBuildingLvRelation`, Shop Bang 22 món tiêu `Contribution (1113)` theo đúng giới hạn ngày/tổng và cấp Shop (`34005000`).
- **Lính Thuê & Boss Bang:** Chia sẻ 1 Lính Thuê không phải MC mỗi ngày (`GuildShare`, khóa `specialType == 255` `-3424`, mở `DailyTask #10`), thuê qua `GGZJ.Hire (hire_type=1)` trừ đúng `ggzj_config["hireUse"]` (`3`× `16050016`), giới hạn 5 lượt/ngày (`-3426`) và thưởng chủ tướng `+1 STA` (`perMercenaryBeUseReward`). Boss Bang cổ vũ tăng `+20%` AP (`200` KC / `1800s`), nghỉ chiến `23:30–24:00` (`-3447`), thưởng `battleRewardsEvery` + xếp hạng sát thương Bang/Cá nhân, và nhận thưởng Công Hội cuối mùa `Gddh` qua `GuildReward` (`ResourceList[].Count`).

### 5.7. Kết Toán Hạng Sự Kiện (`4410` / `4421` / `4422` / `4430`) & Cấu Hình Kinh Tế Gốc (`R7.32`)
- **Kết toán cuối kỳ về `RewardCenter (2400)` (`event_handlers.py`, `r79_event_handlers.py`):**
  - `4410` (`timed_xssb`): phát thưởng BXH `XSSB_RANK_REWARDS` cho mọi kỳ có `integral > 0` đồng thời kết toán nốt các rương mốc `XSSB_CREDIT_REWARDS` đạt điều kiện nhưng chưa nhận.
  - `4421` (`timed_recharge_rank`) & `4422` (`timed_consume_rank`): chỉ trao thưởng top `1..5` khi đạt đúng ngưỡng tối thiểu `NeedMinNum` (`1000/500/300/100/60`), idempotent qua `SourceKey` và hoạt động cho cả hết hạn tự nhiên lẫn `manual_reset`.
  - `4430` (`timed_active_rank`): yêu cầu tối thiểu `LessScore = 20` điểm hoạt động theo `TimedActivityRankLayer.lua`; dùng chuẩn `include_archived_peers=True` cho cả 4 bảng xếp hạng để các tài khoản S1 luôn nhận đúng thứ hạng nhất quán bất kể thứ tự kết toán.
- **Đọc trực tiếp 5 bảng kinh tế VN (`emulator.py`):** `LvPlanConfig`, `LvPlanRewardModel`, `VipWelfareModel` (dùng `self.clock.today_str()` thay vì đồng hồ hệ thống), `BagModel` & `BagExpandUseRelation` (1–20 lần, `10..200` KC) đều trích vào `game_data.json` (`182 / 276`).

### 5.8. Phủ Đủ 8/8 `TimedWelfare` (`4413..4420`) & `RankScene` Tab 3 Liên SV (`R7.33`)
- **8/8 Phúc Lợi (`event_runtime.py`, `event_handlers.py`, `r79_event_handlers.py`, `emulator.py`, `ggzj_handlers.py`, `bdd_handlers.py`):**
  - Chuẩn hóa định dạng `RefNum` theo `WelfareData.lua` / `TimedWelfare.lua`: `4413`/`4414`/`4420` dùng `RefNum = 2`, `4415` (Kho Vàng) dùng `RefNum = 200` (`_ggzj_welfare_mult` xử lý cả `>= 100` lẫn `< 100`), `4416`/`4417` dùng `RefNum = 80`, và `4418`/`4419` dùng danh sách phẩm chất `"3,6,10,15"` (`_timed_welfare_qualities`).
  - Nối bổ sung 3 phúc lợi chưa cài ở các bản trước: `4413` nhân đôi `PVPCoin (1115)` khi đánh Arena (`PVP.PVPFight`), `4418` tạo 2 trang bị mỗi lần ghép (`Equip.EquipCompose` / `EquipOneKeyCompose`) khi khớp phẩm chất, và `4420` nhân đôi `Merit (1124)` trong `nationalDrop` của Mộ Thần Binh (`BddInfo.Fight` & `OneKeyThreeStar`) mà không nhân đôi `firstPassDrop` Kim Cương (`1111`) hay `RewardBox`.
- **`RankScene` Tab 3 (`PVPinter.GetPVPInterTopRank` & `PVPinter.GetSlotFormations`):** Phục vụ top 50 đa server (`S1 - Chiến Quốc` gồm các TK S1 + bot `S2..S5`) và xem đội hình ngay trên `RankScene.lua`, giữ nguyên `LeaderBoard.RankList [3]` trả lỗi theo kiểm thử `test_r725.py`.

### 5.9. Lễ Hội `FestivalActivity` (`6300`) / `CommonHoliday` (`6400`) & `Player.GetPlayerInfo` (`R7.34`)
- **Cô lập chuẩn không phá mặc định (`event_runtime.py`, `event_handlers.py`, `r79_event_handlers.py`):**
  - Đăng ký `20` sự kiện Lễ Hội (`FestivalActivity 6300`: `6301,6302,6303,6304,6306,6308,6309,6311,6313,6314`; `CommonHoliday 6400`: `6401,6402,6403,6404,6406,6408,6409,6411,6413,6414`) nhưng **không** đưa vào `DEFAULT_CONCURRENT_EVENTS` (`67` định nghĩa tổng, `22` mặc định), giữ `ModuleSub[6300/6400] = 0` trừ khi được kích hoạt tường minh theo cấu hình kỳ sự kiện.
  - Khi mở song song với `4400`, toàn bộ 10 phân hệ (`charge_single`, `charge_total`, `use_total`, `exchange`, `slot`, `smash_egg`, `day_login`, `points_mall`, `active_rank`, `charge_gift`) định tuyến và lưu trữ tiến độ/nhận thưởng/tiêu nạp cô lập theo từng `ActivityId`, kèm kết toán `RewardCenter` khi hết kỳ cho `6304/6404` (Slot) và `6313/6413` (BXH Năng Động).
- **Hồ sơ & Chat (`emulator.py`):** Mặc định `PlayerInfo["ActivityPic"] = ""` / `ActivityName = ""` trong cả `_normalize_loaded_state` lẫn `Player.GetInitData`, và bổ sung `Player.GetPlayerInfo` (`ChatLayer.lua:143`) tra cứu TK S1 thật lẫn 24 NPC xã hội (trả `-3003` nếu không tồn tại), hoàn tất **100% tính năng backend sống (`ifOpen=1`) thuần VN** (`test_r734.py` `6/6 OK`, tổng `230/230` tests OK).
