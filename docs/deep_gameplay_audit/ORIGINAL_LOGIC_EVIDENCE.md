# Hồ Sơ Bằng Chứng Logic Gốc & Độ Tin Cậy — InuYasha: Seek Jade

**Ngày lập hồ sơ:** 22/11/2026 (UTC+7) | **Baseline:** `checkpoint-vn-r7.21` (`2b91941`, APK 840).
**Nguyên tắc phân tách:** Tách bạch tuyệt đối giữa **(I) Sự thật đã xác minh trực tiếp từ mã/dữ liệu VN gốc**, **(II) Dữ liệu suy luận có kiểm chứng toán học**, và **(III) Giả thuyết / Phần chưa đủ bằng chứng** (không bao giờ đánh đồng lời kể cộng đồng hay dữ liệu vùng khác với bằng chứng gốc VN).

---

## 1. Thang phân loại độ tin cậy nguồn

| Cấp độ | Ký hiệu | Định nghĩa |
|---|---|---|
| **Cấp 1 — Tuyệt đối** | `L1-VN-CODE` | Đọc trực tiếp từ mã Lua giải mã của chính client `com.cmn.inuyasha` (`VN 5.0.4.98`) trong `analysis/vn/decompiled_src/`. |
| **Cấp 2 — Xác thực toán học** | `L2-VN-DATA-MATH` | Chứng minh bằng phương trình khớp `0.00` sai số từ bảng dữ liệu máy chủ thật được nhúng trong config VN (như `TeambattleHeroNpc.lua`). |
| **Cấp 3 — Tham chiếu đa vùng** | `L3-CROSS-REGION` | Tìm thấy trong bản `EN 5.1.1`, `ZH 5.0.0`, `TH 5.1.3.6` hoặc `TW 1.4` và đã kiểm tra tính tương thích schema/ID với VN. |
| **Cấp 4 — Chưa đủ bằng chứng** | `L4-SERVER-ONLY` | Logic nằm hoàn toàn trên máy chủ thương mại cũ, không hiện diện trong bất kỳ APK nào hiện có; mọi giải pháp đều phải gắn nhãn *Tái dựng / Mô phỏng*. |

---

## 2. Danh mục bằng chứng cốt lõi đã xác minh (`L1` & `L2`)

### 2.1. Công thức Chiến Đấu & PRNG (`CSCommon/*.lua`) — `L1-VN-CODE`

| Hạng mục | Tệp & Dòng nguồn gốc VN | Logic gốc xác minh được | Sai lệch ở Backend hiện tại (`server/`) |
|---|---|---|---|
| **Sát thương & Bàn tròn** | `analysis/vn/decompiled_src/CSCommon/FightExpression.lua#L114-L219` | `hurtStrength = max(atkAP - vicDEF, atkAP*0.1)`; `rageScale = 1 + (RP - needRP)/200`; `rate = (damaddr - damcutr) + countryHurt`; ưu tiên Né → Bạo → Đỡ → Thường; cuối cùng cộng `damadd - damcut` (`min 1`). | **[ĐÃ SỬA R7.22C]** `combat_sim.py` đã cộng đầy đủ `countryHurt` (`RADAMADDR/CUTR..RCDAMCUTR`). |
| **Khởi tạo Combat & `APR/DEFR`** | `analysis/vn/decompiled_src/CSCommon/ServerInterface.lua#L57-L124` | `v.APR/HPR/DEFR` bị comment (`L85-87`) vì chỉ số tĩnh đã cộng vào `AP/HP/DEF` trước trận; đọc `RADAMADDR..RCDAMCUTR` (`L99-106`); truyền `talBuffList = v.BuffList` (`L108`). | **[ĐÃ ĐẠT R7.24]** `_hero_fight_obj` gửi đủ `RADAMADDR..RCDAMCUTR` (`R7.22C`) và giữ nguyên toàn bộ `1.699/1.699` (100%) dòng tài năng VN qua `supports_talent_buff` (`R7.24`). |
| **PRNG Chiến đấu** | `analysis/vn/decompiled_src/CSCommon/LMMath/CreateRandom.lua#L16-L122` | Thuật toán thuần Lua dùng chuỗi `mBox` (`2.400` ký tự hex) + `bit32.bxor / lrotate / rrotate`, sinh số nguyên trong `[min, max]`. Không phụ thuộc OS/C-rand. | **[ĐÃ SỬA R7.22C]** Đã port `CreateRandom` sang `combat_sim.py` (`test_r722c.py` khớp 2.500/2.500 lần rút & oracle APK). |
| **Chọn mục tiêu AI** | `analysis/vn/decompiled_src/CSCommon/TargetModeFunction.lua#L150-L457` và `CSCommon/BattleMatrix.lua#L642-L858` | (1) `eSingleFront/Back/OneColumn`: cột đối diện trống → chọn **cột khoảng cách gần nhất**, hòa chọn chỉ số nhỏ; (2) `eHPMin` (`L702`): `a:getHP() < b:getHP()` (HP tuyệt đối); (3) `eRPMax/Min` (`L752,L795`): loại `attackHeroSlotID`; (4) `eHPLossMax` (`L844`): `getHP(true) - getHP()`. | **[ĐÃ SỬA R7.22C]** `combat_sim.py:_select_targets` đã đồng bộ cả 3 chế độ và `eRandom` pop qua `CreateRandom`. |
| **10 loại Buff & 8 Special Buff** | `analysis/vn/decompiled_src/CSCommon/FightBuffModel.lua#L44-L1263`, `#L1954-L2377` và `CSCommon/FightAttack.lua#L339-L387,627-728` | Triển khai đủ: `eLossAddition(0)`, `eSacrificeAddition(1)`, `eInstantaneousChange(2)`, `eStateTrigger(3, kể cả refAttr>=500)`, `eComparisonAttribute(4)`, `eSpecial(5: 9001 kháng khống chế, 9002 liên trảm, 9003 đánh đôi, 9004 lan đánh thường, 9005 phản kích đỡ, 9006 phản ST, 9007 miễn tử, 9008 tăng theo đồng đội chết)`, `eAdditional(6, kèm modifyAddValue từ refAttr)`, `eTransformation(7, hút máu theo DAM)`, `eSteal(8)`, `eSelfStateTrigger(9, hồi sinh HP==0 & tử vong nổ/hồi)`, Khiên `601`, Độc `602`, Hồi liên tục `603`, Miễn phản ST `707`. Lưu ý Lua quirk: `12420800/12430750/12430806` (`407 BCPR`) & `12440000` (`202 AP`) có `triggerCondition1=4`, trong khi `FightAttack.lua:429` lọc `c1=4` khi `attackType==1` heal. | **[ĐÃ HOÀN TẤT R7.23 + R7.24 (`1.699/1.699` tài năng = 100%, `133/133` skill = 100%)]** Đã khôi phục đủ Lát 1A (`R7.23`) & Lát 1B (`R7.24`: `ContinuousAttack`, `9004`, `9006+707`, `1029..1033`, `14060000`, `601`, `9007`, `type=0`, `10090000`) trong `combat_effects.py` & `combat_sim.py` (`test_r723.py`, `test_r724.py`). |

### 2.2. Công thức Lực Chiến (`FAP`) — `L2-VN-DATA-MATH`

| Nguồn bằng chứng | Dữ liệu kiểm chứng | Kết quả xác minh |
|---|---|---|
| `analysis/vn/decompiled_src/Config/TeambattleHeroNpc.lua` (432 đơn vị) & `TeambattlePlayerNpc.lua` (72 đội) | Toàn bộ 216/216 đơn vị bậc đầu (`pid 1001..1036`, nơi `HPAdd=APAdd=DEFAdd=0`, `CRID=TEND=DAMADD=DAMCUT=DAMADDR=DAMCUTR=0`, gồm cả 12 đơn vị chỉ số phụ = 0 và 204 đơn vị có `DOD/CRI/TEN/BLO/BOG` từ 300–1000) | **`FAP = HP + 10 * AP + 10 * DEF` khớp chính xác `0.00` sai số trên cả 216/216 dòng!** (Ví dụ `hid=12012029`: `11559 + 10*1409 + 10*734 = 32989 == FAP`; `hid=12013015`: `44267 + 10*13175 + 10*2811 = 204127 == FAP`). |
| Cùng file trên, 216 đơn vị bậc cao (`pid 1037..1072`, Lv65–83) | `DAMADD/DAMCUT ~ 40k–90k`, `DAMADDR/DAMCUTR ~ 6600–8600`, `CRID/TEND ~ 4800–8000` | `FAP / (HP + 10*AP + 10*DEF)` đạt hằng số **4,16× – 5,63×** theo 6 template slot, chứng tỏ server gốc nhân thêm hệ số lực chiến cho nhóm chỉ số endgame/Reborn/Tài năng, **nhưng công thức chính xác của hệ số thứ cấp này là `L4-SERVER-ONLY`** (không nằm trong Lua client). |
| `server/emulator.py`, `server/bdd_handlers.py`, `server/teambattle_handlers.py` | Mã backend sau `R7.22C` | **[ĐÃ SỬA R7.22C]** Toàn bộ 6 chỗ tính FAP đơn vị đã dùng chuẩn `HP + 10 * AP + 10 * DEF`. |

### 2.3. Hệ thống Tiến Hóa, Trang Bị, Bảo Vật, Đá, Cổ Vũ, Chuyển Sinh — `L1-VN-CODE`

| Hạng mục | Tệp & Dòng nguồn gốc VN | Bằng chứng cụ thể |
|---|---|---|
| **Tiến hóa Nhân Vật Chính** | `Config/AttrtreeHeromodelRelation.lua#L1-L36`, `Practice/LightenStarScene.lua#L11,309-380`, `Config/HeroModel.lua` (`12010001..12010010`) | Star `0 → 12010001/04` (`q=6`, RA `1002165` 1 mục tiêu 270%), Star `1 → 12010009/10` (`q=6`, RA `1002173` **3 ngẫu nhiên 130%** — khớp mô tả talent +1 `10320000`!), Star `4 → 12010007/08` (`q=10`), Star `113 → 12010002/05` (`q=13`), Star `348 → 12010003/06` (`q=15`). TW `HerostepHeromodelRelation.lua` xác nhận thêm `[step=1] → 12010009/10` (`L3-CROSS-REGION`). |
| **Bộ Trang Bị thiếu 13 thuộc tính** | `Config/EquipGroupActiveRelation.lua` (trích vào `game_data.json["equip_group"]`) | Có 16 trường khác 0: `AP(13), DEF(13), HP(13), APR(23), HPR(23), DEFR(23), CRI(10), HIT(7), DOD(6), BLO(6), BOG(3), CRID(3), TEND(3), TEN(2), DAMADD(1), DAMCUT(1)`. `emulator.py:956-960` chỉ đọc 3 trường đầu. |
| **Tiến Giai Bảo Vật thiếu `410/411`** | `Config/TreasureStepAttrRelation.lua` (`game_data.json["treasure_step_attr"]`) | `totalAtrrStr` chứa đúng 4 enum: `201 (30)`, `202 (30)`, `410 DAMADDR (30)`, `411 DAMCUTR (30)`. `emulator.py:986-992` chỉ xử lý `201/202/203`. |
| **Cổ Vũ Đột Phá / Chuyển Sinh** | `Config/HeroStepCheer.lua` (180 cấp), `Config/HeroRebornCheer.lua` (84 cấp), `Formation/PartnerCheerLayer.lua#L45-L64` | **[ĐÃ NỐI R7.22A + R7.27]** `PartnerCheerLayer` cộng tổng `data.Step` và `RebornLvModel[data.RebornId].rebornNum` của Đồng Đội cam+ (`colorLV >= 5`) → `_hero_step_cheer_bonuses` (`R7.22A`) + `_hero_reborn_cheer_bonuses` (`R7.27`) cộng đủ `APADD/HPADD/DEFADD`. |
| **Linh Thạch / Đá (`Gem`)** | `Config/GemModel.lua` (90 mẫu), `Formation/MyFormationLayer.lua#L1656,1689`, `Gem/GemLevelUpLayer.lua`, `Equipment/EquipmentScene.lua` | **[ĐÃ NỐI R7.22D]** `Slot.GemCombat [slotId, gemSlotIdx, gemEntityId]`, `Slot.GemOneKeyCombat [slotId]`, `Gem.GemCompose` (túi + `syntheticDoubleUse` và nâng cấp tại chỗ từ `GemLevelUpLayer`), `Gem.GemOneKeyCompose` và 11 enum `attrStr` vào `_compute_slot_property` (`test_r722d.py`). |
| **Chuyển Sinh (`RebornCoin/Goods`) & 11 Tuyệt Kỹ `UAID`** | `Data/NetworkResData.lua#L487,711-712,1082-1083,5786-5957`, `Hero/Rebirth/*.lua`, `Config/Reborn*.lua` (7 bảng), `HeroModel.UAID` (`1003001..1003011`) | **[ĐÃ HOÀN TẤT R7.26 + R7.27]** `R7.26` nối nền `1128 RebornCoin` & `2701 RebornGoods`; `R7.27 (TASK-N02B)` trích đủ 6 bảng Chuyển Sinh còn lại (`155/276`), triển khai 8/8 RPC (`RebornInfo` 5 + `RebornShop` 3) trong `reborn_handlers.py`, cộng `allAttrStr` + ô khảm + `RebornPrtypeRelation` + Đại Sư `RebornLvActiveModel` + 7 buff `talIDStr` + mở khóa **11/11 `UAID`** + hoàn trả `HeroRebirth` (`test_r727.py`). |
| **Trùm Tăng Cấp (`EquipArtifact`) & `Callequip`** | `Equipment/NewArtifactLayer.lua`, `ArtifactBoxLayer.lua`, `Data/CalcPrefData.lua#L835-L910`, `Data/NetworkResData.lua#L686-689,5158-5187`, `Store/RecruitScene.lua#L698-L765,1260-1380`, `Config/EquipArtifactRelation.lua`, `CallequipConfig.lua`, `CallequipOutoddsBRelation.lua` | **[ĐÃ HOÀN TẤT R7.28 (`REC-P2-02`)]** Trích `EquipArtifactRelation` (1.104 mốc) & `CallequipOutoddsBRelation` (36 dòng) → `157/276`; nối `_compute_equip_artifact_state` (`itemLv` = `EquipModel.itemLv + EquipStepRelation.itemLv`) vào `Property`, `Avatar.EquipArtifactInfo`, và `SuccessTarget #37..41`; hoàn thiện `Callequip.GetCallEquipData` / `CallEquip` + `SuccessTarget #12` + `4416`/`4419` (`test_r728.py`). |
| **Kho Vàng (`GGZJ`) & Đấu Võ Đại Hội (`Gddh`/`GddhShop`)** | `GGZJ/GGZJHomeScene.lua`, `GGZJHeroHireLayer.lua`, `GGZJWinHintLayer.lua`, `Challenge/WrestleRaceScene.lua`, `WrestleExchangeLayer.lua`, `WrestleRevengeLayer.lua`, `WrestleRewardLayer.lua`, `ChallengeListLayer.lua`, `Fight/FightBalanceLayer.lua`, 4 bảng `Config/Ggzj*.lua`, 6 bảng `Config/Gddh*.lua` | **[ĐÃ HOÀN TẤT R7.29 (`REC-P2-03`)]** Trích đủ 10 bảng VN (`167/276`); hoàn thiện `GGZJ.*` (8 RPC, `ggzj_handlers.py`) & `Gddh.*`/`GddhShop.*` (10 RPC, `gddh_handlers.py`); hỗ trợ `GDDHCoin (1119)`, `RawGold (2112)` nhân `Lv`, phúc lợi `4414`/`4415`, kết toán `23:00` về `RewardCenter (2400)`, nối `DailyTask #6/#9`, `SuccessTarget #13/#30`, `ActiverankingModel #7/#9` (`test_r729.py`). |
| **Bạn Bè (`Friend`/`FriendMessage`/`Enemy`) & Hộp Thư (`PlayerEmail`)** | `Friend/FriendScene.lua`, `ContactLayer.lua`, `FriendMsgLayer.lua`, `Email/EmailListLayer.lua`, `EmailHelper.lua`, `ReplyEmailLayer.lua`, `Chat/ChatLayer.lua#L1460-L1596`, `Config/PlayerLvRelation.lua` (`friendMax`), `Network/ServerMessage.lua#L350-L396` (`-2701..-2707`, `-3001..-3019`) | **[ĐÃ HOÀN TẤT R7.30 (`REC-P2-04A`)]** Hoàn thiện 19 RPC trong `social_handlers.py` (2 chiều S1 + 24 NPC bạn bè, `STAData.PlayerName`, `+2` STA tối đa `20`/ngày, chặn `STA >= STAMaxNum` `-3010`, nối `DailyTask #11`, `Slot.SlotFormations`, chiến báo `PVP`/`Gddh`/`BossBattle.FriendHelp`, `Teambattle` mời bạn, chấm đỏ `1700/1701/1900..1903`, `test_r730.py`). |
| **Drop Tinh Anh & Phí Reset Ải** | `Config/ElitebattleNodeDropRelation.lua` (747 dòng), `Config/BattleResetUseRelation.lua` (20 bậc: `1605,16050013,1` hoặc `50/100/200` KC) | Cả hai bảng gốc VN tồn tại 100%, đã trích & nối trong `R7.22B` (`test_r722b.py`). |
| **Rương Điểm & Shop Yêu Vương** | `Config/LuckbossValueShopModel.lua` (35 mốc rương điểm), `Adventure/BossRewardPreviewLayer.lua#L60-L64,L488-L518` | Cải chính R7.22B: `LuckbossValueShopModel` là 35 rương điểm (`BoxList`/`DrawBox`/`OneKeyDrawBox` đã chạy); tab 2 `ExchangeInfo`/`Exchange` (`LuckbossValueExchangeModel`) bị tắt trong client VN. |
| **Đội hình Meta chính chủ VN** | `Config/StrongFormModel.lua` | Ghi rõ 9 đội hình tiêu chuẩn (3 bậc Sơ Nhập / Tiến Nhập / Hàng Ma × 3 phe). |

---

## 3. Phân tách rõ: Đã Xác Minh vs Giả Thuyết / `L4-SERVER-ONLY`

| Vấn đề | Phân loại | Ghi chú kỹ thuật bắt buộc tuân thủ |
|---|---|---|
| Công thức sát thương, bàn tròn xác suất, tích Nộ, chọn mục tiêu, 10 loại Buff, PRNG `CreateRandom` | **Đã xác minh 100% (`L1-VN-CODE`)** | Sao chép đúng 100% từ `CSCommon/*.lua`, không tự sáng tác. |
| Hệ số FAP gốc `HP + 10*AP + 10*DEF` | **Đã xác minh 100% (`L2-VN-DATA-MATH`)** | Khớp `0.00` lỗi trên 216/216 NPC bậc chuẩn. |
| Hệ số nhân FAP bậc endgame (`4,16×–5,63×` trên `pid 1037..1072`) | **Giả thuyết / `L4-SERVER-ONLY`** | Không có mã tính FAP trong Lua client. Nên áp dụng `HP + 10*AP + 10*DEF` trước (có kiểm chứng tuyệt đối), chỉ cân nhắc cộng điểm thứ cấp sau nếu cần hiển thị tương đương endgame. |
| Đội hình quái từng wave của 689 ải Chiến dịch, Tinh Anh, 639 ải Ác Mộng, 51 ải Mộ Thần Binh | **`L4-SERVER-ONLY`** | Không tồn tại trong 5 APK (`VN/EN/ZH/TH/TW`). Chiến dịch chỉ có 15 trận kịch bản hướng dẫn gốc; Mộ Thần Binh có `pic` thủ lĩnh + `proposeFAP` + điều kiện thắng. Phải dùng tái dựng có căn cứ (**B/C**) và ghi chú rõ là mô phỏng. |
| Tỉ lệ xác suất quay ra từng tướng lẻ trong `HeroRecruit` / `TimedRecruit` | **`L4-SERVER-ONLY`** | Client chỉ chứa danh sách pool `outShowAll` và bảng `Blessodds`/`RatioOdds`. Giữ nguyên tỷ lệ mô phỏng hợp lý đã nghiệm thu, không suy diễn từ vùng khác. |
| Nguồn cấp món Trang Bị Kim (`colorLV=8`) đầu tiên & bảng giá Cường Hóa Kim trong VN | **Chưa đủ bằng chứng (`L4-SERVER-ONLY`)** | Quét 276 bảng VN: 0 nguồn cấp. Rương Kim `16020069/71/72` của EN/ZH không tồn tại trong `GoodsModel.lua` VN. TW `EquipColorLeadRelation` chỉ cho nâng Đỏ→Kim khi đã có sẵn Kim. Giữ trạng thái chờ quyết định riêng của chủ dự án. |
| 9 file modal có mẫu `self.onCloseCallback(self)` (ngoài `TimedEquipRankLayer`) & 5 file `LoadingWait:begin > ends` | **Đã kiểm chứng tại `R7.25` — False Positive (`L1-VN-CODE`)** | Kiểm tra `ctor` 8/9 modal có gán `self.onCloseCallback`; `TimedRecruitEquipLayer` không định nghĩa method `:onCloseCallback()` (không đệ quy); `Common/LoadingWait.lua#L67-L83` gọi `LoadingWait:ends()` đầu `begin()` (singleton) nên không thể treo đếm tham chiếu. Không cần vá APK. |
| Chi tiết payload RPC cho `CrusadeInfo` (Lãnh Địa) | **Chưa đủ bằng chứng chi tiết (`L1` chưa đọc hết)** | UI có 10 file trong `Territory/`, chưa thấy bảng config `Crusade*` ở `Config/`; cần 1 phiên đọc sâu `Territory/*.lua` trước khi lập trình. |

---

## 4. Quy tắc chống trộn vùng (Cross-Region Provenance Policy)

1. **Tuyệt đối lấy `VN 5.0.4.98` làm chuẩn duy nhất** cho mọi ID tướng, vật phẩm, kỹ năng, buff, duyên phận, bảng thưởng và độ khó.
2. **Không bao giờ** sao chép `GoodsOutputRelation`, `TimedRecruitModel`, hoặc tỉ lệ rơi từ `EN 5.1.1` / `ZH 5.0.0` / `TH 5.1.3.6` vào VN mà không chứng minh ID tồn tại trong `GoodsModel.lua` VN.
3. **Donor hợp lệ duy nhất khi thiếu bảng gốc ở VN:** chỉ dùng khi client VN đã có sẵn UI + gọi trực tiếp tên bảng đó (như `EquipArtifactModel` từ TW 1.4 vì `Artifact/ArtifactScene.lua:8` gọi trực tiếp `require("Config.EquipArtifactModel")` cùng với `EquipArtifactRelation.lua` của VN!). Mọi donor như vậy đều phải ghi rõ xuất xứ.
