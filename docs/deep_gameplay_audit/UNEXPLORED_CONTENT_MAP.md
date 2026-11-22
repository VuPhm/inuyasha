# Bản Đồ Nội Dung, Tài Nguyên & Cơ Chế Chưa Khai Phá — InuYasha: Seek Jade

**Ngày khảo cổ:** 22/11/2026 (UTC+7) | **Baseline:** `checkpoint-vn-r7.21` (`2b91941`, APK 840).

---

## 1. Tổng quan khảo cổ cấu hình & giao thức

| Nguồn tài nguyên | Tổng số trong VN `5.0.4.98` | Đã khai thác | Chưa khai thác / Bị bỏ sót |
|---|---:|---:|---:|
| File cấu hình Lua (`analysis/vn/decompiled_src/Config/*.lua`) | **276** | **167** *(+32 sau R7.21)* | **109** |
| Mục tính năng (`ModuleSubModel.lua`) | **350** (293 mở, 57 `ifOpen=0`) | ~168 | ~182 (gồm nhiều hệ lớn đang mở `ifOpen=1`!) |
| RPC Client (`HttpRequest` + `svrMethodData`) | **394** trên **96 module** | **267** thật + **3** stub (`328` trong `emulator.py`) | **124** chưa có handler (~109 tính năng thật) |
| Bản tham chiếu đa vùng | EN `5.1.1` (240), ZH `5.0.0` (276), TH `5.1.3.6` (287), TW `1.4` (15 donor) | 5 bảng TW + 9 asset ZH/TH (Banner 83) | 5 bảng ZH, 27 bảng TH, 10 bảng TW còn lại (cần kiểm tương thích) |

---

## 2. Năm phát hiện khảo cổ giá trị nhất (Ưu tiên khai phá ngay)

### Loại 1: Tính năng có đủ dữ liệu VN gốc + UI client nhưng bị bỏ quên hoàn toàn

| # | Hệ thống | Tài nguyên & UI Client | Cấu hình gốc VN | API / Protocol (RPC) | Trạng thái Backend | Kết quả Gameplay hiện tại |
|---|---|---|---|---|---|---|
| **1** | **Khảm & Hợp Linh Thạch / Đá (`Gem`)** | `Formation/MyFormationLayer.lua`, `Gem/GemLevelUpLayer.lua`, `Gem/GemSelectLayer.lua`, `Equipment/EquipmentScene.lua`, `Equipment/EquipmentComposeLayer.lua` | `GemModel.lua` (90 mẫu, `rtype=2000`, đã trích R7.21) | `Slot.GemCombat`, `Slot.GemOneKeyCombat`, `Gem.GemCompose`, `Gem.GemOneKeyCompose` | **[ĐÃ SỬA R7.22D]** Đã khôi phục **4/4 RPC** (`Slot.GemCombat`, `GemOneKeyCombat`, `Gem.GemCompose` 2 chế độ túi/tại chỗ + `syntheticDoubleUse`, `Gem.GemOneKeyCompose`) và cộng đủ 11 enum `GemModel.attrStr` vào `_compute_slot_property`/`FightInfo`. | Đá từ Phó Bản Tổ Đội & Shop 18 món đã khảm/nâng cấp/cộng lực chiến & chỉ số chiến đấu hoàn chỉnh. |
| **2** | **Tiến hóa Nhân Vật Chính (`AttrtreeHeromodel`)** | `Practice/LightenStarScene.lua:11,309-380` (có sẵn hiệu ứng thăng phẩm Trắng→Lục→Lam→Tím→Cam) | `AttrtreeHeromodelRelation.lua` (5 mốc: Star `0/1/4/113/348`) + `HeroModel` (`12010001..10`) | Piggyback ngay trong `LightenStar` / `SlotInfo` | **[ĐÃ SỬA R7.22B]** `_sync_main_hero_model` đã nối trong `_recalc_all_slots_and_fap` và `_normalize_loaded_state`, hỗ trợ cả `Step >= 1` (`12010009/10`). | Đã mở khóa tiến hóa MC Nam/Nữ đủ 5 mốc `q=6→10→13→15` + Nộ 3 mục tiêu. |
| **3** | **Cổ Vũ Đồng Đội (`PartnerCheer`)** | `Formation/PartnerCheerLayer.lua` (hiển thị tổng Step & Reborn và mốc cộng chỉ số) | `HeroStepCheer.lua` (180 mốc), `HeroRebornCheer.lua` (84 mốc) | Không cần RPC mới — tính trực tiếp vào `Slot.Property`! | **[ĐÃ XONG R7.22A + R7.27]** `HeroStepCheer` (`R7.22A`) và `HeroRebornCheer` (`R7.27`) đã cộng đủ cho Đồng Đội cam+ (`colorLV >= 5`). | Đã mở khóa `+APADD/+HPADD/+DEFADD` theo cả Step lẫn Reborn Đồng Đội. |
| **4** | **Chuyển Sinh (`Reborn`) & Tuyệt Kỹ `UAID`** | `Hero/Rebirth/RebirthLayer.lua`, `RebirthComposeLayer.lua`, `RebirthGoodsConvertLayer.lua`, `RebirthStoreLayer.lua` | `RebornConfig`, `RebornLvModel` (340), `RebornLvActiveModel` (9), `RebornGoodsModel` (28), `RebornPrtypeRelation`, `RebornShopOddsRelation`, `RebornSlotRelation` (7 bảng VN 100%!) | `RebornInfo.Activate`, `Reborn`, `ComposeAndActivateForOneKey`, `RebornGoodsCompose`, `RebornGoodsRefine`; `RebornShop.GetInfo`, `RebornShopBuyGoods`, `RefreshtGoodsList` | **[ĐÃ XONG R7.27]** 8/8 RPC + Duyên `RebornLvActiveModel`/`RebornPrtypeRelation` + 7 buff `talIDStr` + **11/11 `UAID`** (`test_r727.py`). | Mở khóa đủ 11 Tuyệt Kỹ `1003001..1003011` và vòng lặp endgame Lv48+. |
| **5** | **Phó Bản Ác Mộng (`Nightmare`)** | `Adventure/BattleLayer.lua`, `NightmareRankLayer.lua`, `Hero/Rebirth/RebirthComposeLayer.lua` | `NightmareChapterModel` (65), `NightmareNodeModel` (639), `NightmareChapterBoxRelation` (192), `NightmareNodeDropModel` (899), `NightmareConfig`, `NightmareResetUseRelation` | `Nightmare.GetNightmareInfo`, `GetNodeList`, `AllChapterInfo`, `GetFightInfo`, `Fight`, `ConFight`, `HiAutoFight`, `ResetCount`, `DrawBox`, `OneKeyDrawBoxs`, `RankList`, `Formation` | **[ĐÃ XONG R7.26]** 12/12 RPC thật + `DrawRoadBox` `-1` trong `nightmare_handlers.py` + nền `RebornGoods (2701)` / `RebornCoin (1128)`. | Mở đủ 65 chương / 639 ải cung cấp nguyên liệu Chuyển Sinh (`2701xxxx`, `16050065`, `1128`). |

---

### Loại 2: Tính năng đã implement nhưng BỎ SÓT / DÙNG SAI CONFIG VN có sẵn

| # | Hệ thống | Config VN có sẵn | Lỗi trong Backend hiện tại | Tác động gameplay |
|---|---|---|---|---|
| **1** | **Bộ Trang Bị (`EquipGroup`)** | `EquipGroupActiveRelation.lua` (đã trích!) | **[ĐÃ SỬA R7.22A]** Trước R7.22A chỉ đọc `HP/AP/DEF`, bỏ qua 13 trường (`APR, HPR, DEFR, HIT, DOD, CRI, TEN, BLO, BOG, CRID→CRId, TEND, DAMADD, DAMCUT`). | Đã khôi phục đầy đủ cả `APR/HPR/DEFR` và toàn bộ chỉ số phụ set 2/3/4 món. |
| **2** | **Tiến Giai Bảo Vật (`TreasureStep`)** | `TreasureStepAttrRelation.lua` (đã trích!) | **[ĐÃ SỬA R7.22A]** Trước R7.22A chỉ đọc `201/202/203`, bỏ qua `410 (DAMADDR)` và `411 (DAMCUTR)`. | Đã nối `DAMADDR` và `DAMCUTR` từ Bảo Vật vào `Property` và `FightInfo`. |
| **3** | **Drop Phó Bản Tinh Anh (`EliteBattle`)** | `ElitebattleNodeDropRelation.lua` (747 dòng — đã trích ở R7.22B) | **[ĐÃ SỬA R7.22B]** Trước R7.22B `_rpc_elite_fight` chỉ thưởng `(EXP, Gold, HeroEXP)`. | Đã roll đủ phần thưởng Tinh Anh gốc (`dropOdds`), bao gồm 50 KC mốc node 11, Đá đột phá và mảnh tướng. |
| **4** | **Phí Reset Lượt Ải (`Battle.ResetCount`)** | `BattleResetUseRelation.lua` (20 bậc — đã trích ở R7.22B) | **[ĐÃ SỬA R7.22B]** Trước R7.22B reset miễn phí vô hạn. | Đã thu đúng thẻ `16050013` trước hoặc `50/100/200` KC, chặn thiếu tài nguyên (`-1105`) và trần 20 lần/ngày theo chu kỳ ngày. |
| **5** | **Shop Điểm Yêu Vương (`BossBattle`)** | `LuckbossValueShopModel.lua` (35 mốc rương điểm) | **[ĐÃ XÁC MINH R7.22B — KHÔNG PHẢI LỖI]** `LuckbossValueShopModel` là bảng 35 rương điểm cho `BoxList`/`DrawBox`/`OneKeyDrawBox` (đã chạy). Tab 2 `ExchangeInfo`/`Exchange` (`LuckbossValueExchangeModel`) đã bị chính client VN tắt (`BossRewardPreviewLayer.lua:60-64`). | Không ảnh hưởng gameplay VN gốc; `ExchangeInfo -> []` là no-op an toàn. |
| **6** | **Duyên Bộ Thời Trang (`FashionPr`)** | `FashionPrRelation.lua` (đã trích ở R7.22A) | **[ĐÃ SỬA R7.22A]** Trước R7.22A bỏ qua duyên bộ thời trang (`allAttr`: chỉ số cộng thẳng `431/432/433` theo hàng `6` trước / `7` sau / `2` toàn đội). | Đã cộng đúng bonus duyên bộ Thời Trang và cập nhật khi đổi trận `SlotFormation.Change`. |
| **7** | **Nhiệm Vụ Ngày `#12` & `#26`** | `DailytaskModel.lua` (đã trích!) | **[ĐÃ XÁC MINH & PHỦ TEST R7.22A]** `_record_daily_task_progress(12, ...)` (`Glory`, `emulator.py:8051,8077`) và `(26, 1)` (`TraderInfo.BuyGoods`, `r79_event_handlers.py:2592`) đã nối và kiểm chứng trong `test_r722a.py`. | Cả 2 nhiệm vụ ngày hoạt động đúng luồng đến bước nhận điểm thưởng. |
| **8** | **Quỹ Trưởng Thành & Quà VIP Ngày** | `LvPlanConfig`, `LvPlanRewardModel`, `VipWelfareModel` (**chưa trích!**) | Hardcode trong `emulator.py:112-150`. | Tuy giá trị hiện khớp VN, nhưng nên trích tự động để tránh lệch cấu hình. |
| **9** | **Công thức FAP chuẩn** | `TeambattleHeroNpc.lua` (đã trích!) | **[ĐÃ SỬA R7.22C + BDD R7.24 + R7.27]** Đã chuyển toàn bộ bộ tính FAP (`emulator.py`, `bdd_handlers.py`, `teambattle_handlers.py`) từ `HP + 5*(AP+DEF)` sang gốc `HP + 10*(AP+DEF)` (khớp 216/216 NPC bậc chuẩn). | Lực chiến chuẩn hóa toàn game; R7.24 mở Tầng 24–26 và **R7.27 mở nốt Tầng 27 → 51/51 ải Mộ Thần Binh** (`test_r727.py`). |

---

### Loại 3: Các Hệ Thống Lớn Chưa Nối Backend (Bản đồ quan hệ đầy đủ)

| Hệ thống | ModuleSub (`ifOpen` VN) | Số bảng Config VN | Số RPC Client | Gắn với Task / Thành Tích | Đánh giá khả năng chơi Offline S1 |
|---|---|---:|---:|---|---|
| **Trùm Tăng Cấp (`EquipArtifact`)** | `1408` (`ifOpen=1`) | 1 VN (`EquipArtifactRelation`, 1.104 dòng) + 1 TW (`EquipArtifactModel`) | Piggyback `Avatar.EquipArtifactInfo` | `SuccessTarget #37..41` (5 chuỗi!) | **[ĐÃ XONG R7.28]** Đã nối đủ 1.104 mốc `itemLv`, cộng chỉ số & Thành Tích (`test_r728.py`). |
| **Kho Vàng (`GGZJ`)** | `2504/2509/2510` (`ifOpen=1`) | **4 bảng VN** (đủ `GgzjSystemHeroRelation`!) | 8 RPC (`GGZJ.*`) | `DailyTask #9`, `SuccessTarget #13`, `Activeranking #7`, Phúc lợi `4415` | **[ĐÃ HOÀN TẤT R7.29]** — `ggzj_handlers.py` + `test_r729.py`. |
| **Đấu Võ Đại Hội (`Gddh`)** | `2503` (`ifOpen=1`) | **6 bảng VN** (đủ shop bán mảnh SR!) | 10 RPC (`Gddh.*`, `GddhShop.*`) | `DailyTask #6`, `SuccessTarget #30`, `Activeranking #9`, Phúc lợi `4414` | **[ĐÃ HOÀN TẤT R7.29]** — `gddh_handlers.py` + `RewardCenter` + `test_r729.py`. |
| **Bang Hội (`Guild`) + Boss Bang + Phụ Bản Bang** | `3400/3402/3403/3405/3406/3407` mở (`3401/3404/3408..12` tắt) | **14 bảng `Guild*` + 2 bảng `Auction*`** (có `GuildFbNpcRelation`!) | 29 RPC (`Guild`, `GuildBossInfo`, `GuildReward`, `Auction`) | `DailyTask #10/#15` | **Cao (B)** — làm Bang Hội gia đình chia sẻ giữa các TK S1 + Boss Bang hàng ngày + Shop Bang. |
| **Bảng Xếp Hạng Chung (`LeaderBoard`)** | `6701..6704` (`ifOpen=1`) | 1 (`LeaderboardConfig`) | 3 RPC (`LeaderBoard.RankList`, `Praise`, `Formation`) | — | **[ĐÃ XONG R7.25]** Hiển thị 50 hạng TK S1 + NPC, Thích nhận `10.000` Vàng/ngày/tab & xem đội hình (`test_r725.py`). |
| **Triệu Hồi Trang Bị Thường (`Callequip`)** | `3802` (`ifOpen=0`, nhưng gate nút XSSB `4410`!) | 2 (`CallequipConfig`, `CallequipOutoddsBRelation`) | 2 RPC (`Callequip.*`) | `SuccessTarget #12`, Ưu đãi `4416/4419` | **[ĐÃ XONG R7.28]** 2/2 RPC + CD miễn phí + `IsFrist` + pity Tím↔Cam + `4416`/`4419` (`test_r728.py`). |
| **Lãnh Địa (`CrusadeInfo` / Territory)** | `Territory/*` | Chưa thấy file `Crusade*` riêng trong VN Config | 8 RPC (`CrusadeInfo.*`) | `SuccessTarget #25` (`4925`) | **Trung bình (C/D)** — cần đọc kỹ `Territory/*.lua` để trích xuất cấu trúc payload. |
| **Luyện Thể (`Lianti`)** | `5700` (**`ifOpen=0`**) | **4 bảng VN** (`Lianti*`) + 1 TW (`LiantiOddsDesRelation`) | 3 RPC (`Lianti.*`) | `SuccessTarget #42` | **Trung bình (B)** — tắt mặc định ở VN, chỉ mở nếu chủ dự án muốn mở rộng ngoài VN `5.0.4.98`. |
| **Thú Cưng (`Pet` & `PetOut`)** | `7400..7600` (**`ifOpen=0`**) | **12 bảng VN** (`Pet*`, `Petout*`) + engine `CSCommon/Pets.lua` đã có sẵn! | 24 RPC (`Pet.*`, `PetOutInfo.*`, `Slot.PetCombat`) | `Opencontest #6` (`7906`) | **Trung bình (B)** — tắt mặc định ở VN; nếu mở cần bật cờ `ifOpen` trên client. |
| **Chiến Trận / Chiến Linh (`Warfare`)** | `8101..8108` (**`ifOpen=0`**) | **7 bảng VN** (`Warfare*`) | 4+ RPC (`Warfarespirit.*`) | — | **Trung bình (B)** — tắt mặc định ở VN (`openLv=55`). |
| **Trận Quyết (`Zhenjue`)** | `5400..5407` (`ifOpen=1`) | 6 bảng VN + 4 bảng chỉ có ở ZH/TH | Cần đọc UI `Zhenjue` | — | **Thấp–Trung bình (B/C)** — thiếu 4 bảng gốc ở VN. |
| **Thần Vực (`GodDomain`), Liên SV (`PVPinter`, `ShengyuanWars`)** | `6100/6200/8300/9500` | 21 bảng VN (`Pvpinter*`, `Goddomain*`, `Shengyuanwars*`) | 17+ RPC | — | **Thấp (C)** — hệ PvP đa server; chỉ nên xem xét ở P3. |
| **Chức năng phụ: Bán đồ, Đổi tên/Avatar, Hợp Bảo vật Tím, Bạn bè S1, Kẻ thù, Thư** | `1300`, `1000`, `1700`, `1900`, `5300` | `PlayerConfig`, `GoodsModel`, `GoodsDjqModel`, `TreasureColorModel`, `PlayerLvRelation` | `Goods.GoodsSell`, `Player.AlterPlayerName/HeadId`, `Treasure.TreasureCompose` (**XONG R7.25**); `Friend.*`, `FriendMessage.*`, `Enemy.*`, `PlayerEmail.*` (**XONG R7.30**) | `DailyTask #11` (`23/25`) | **[ĐÃ HOÀN TẤT R7.25 + R7.30]** — `social_handlers.py` + `test_r730.py`. |

---

## 3. Khảo cổ Đa Vùng & Kiểm tra Nguồn Trang Bị Kim (`colorLV = 8`)

| Phiên bản tham chiếu | Số Config | Nội dung độc quyền / Khác biệt đã xác minh | Cảnh báo trộn vùng (Nguyên tắc #5) |
|---|---:|---|---|
| **VN `5.0.4.98`** (Chuẩn gốc) | 276 (gồm 5 TW đã chèn) | Nguồn chuẩn duy nhất cho mọi ID, chỉ số, enum, text và cân bằng cốt lõi. | Không tự ý ghi đè bằng bảng vùng khác. |
| **EN `5.1.1`** | 240 | Không có bảng nào thừa so với VN; **NHƯNG `GoodsOutputRelation.lua` có 3 rương Trang Bị Kim (`16020069` vũ khí Kim `13010805`, `16020071` bộ `130x0802`, `16020072` bộ `130x0803`)** — cả 3 ID rương này **KHÔNG tồn tại trong `GoodsModel.lua` VN!** Banner 83 EN trỏ `16060009` (khác VN `16060034`). | **KHÔNG ĐƯỢC dùng `GoodsOutputRelation` hay `TimedRecruitModel` của EN cho VN.** |
| **ZH `5.0.0`** | 276 | Có 5 bảng VN thiếu: `XxbzFightnumBuyRelation`, `ZhenjueConfig`, `ZhenjuePriceRelation`, `ZhenjueRebirthRelation`, `ZhenjueUpmaxLvRelation`. Cũng có rương Kim `16020069/71/72` không tồn tại ở VN. Đã cung cấp 9 asset còn thiếu cho Banner 83 ở R7.18.1. | Có thể tham khảo schema `Zhenjue*` nếu về sau quyết định mở Trận Quyết (phải đối chiếu ID vật phẩm VN). |
| **TH `5.1.3.6`** | 287 | Phiên bản mới hơn: có thêm 27 bảng (Săn Tổ Đội `Teamhunt*`, Chip Thần Vực `GoddomainChip*`, Cây tài năng Pet `PetTalTreeModel`, Đổi tướng `HeroChange*`). | **Tính năng phiên bản sau** — không thuộc `VN 5.0.4.98`, không trộn vào client VN. |
| **TW `1.4`** | 15 (đã trích) | 5 bảng đã được VN-hóa ở R7.9 (`XssbModel`, `CriticalTasksTypeRelation`, `EarlytaskModel`, `EarlytaskRewardRelation`, `TraderConfig`). 10 bảng còn lại gồm `EquipArtifactModel`, `EquipColorLeadRelation` (chuyển Đỏ→Kim cần sẵn món Kim), `HerostepHeromodelRelation` (chỉ có `[step=1] -> 12010009/10`, xác nhận cơ chế đổi model MC!), `NewWraith*` (3 bảng Yêu Linh), `PvpinterTopConfig`, `LiantiOddsDesRelation`. | Chỉ dùng làm tài liệu đối chiếu hoặc donor có kiểm chứng (như `EquipArtifactModel` để mở `1408` khi VN đã có sẵn `EquipArtifactRelation` 1.104 dòng!). |

### Kết luận về dữ liệu không tồn tại trong mọi APK (Server-only gốc)
Quét toàn bộ 5 bản game (`VN`, `EN`, `ZH`, `TH`, `TW`) xác nhận **không có bản client nào chứa**:
1. Đội hình quái chi tiết từng wave đánh thường của 689 ải Chiến dịch / Tinh Anh / 639 ải Ác Mộng / 51 ải Mộ Thần Binh (ngoại trừ 15 `BattleScript` hướng dẫn + `BattleNodeGuidenpcRelation` 34 dòng + `TeambattleHeroNpc` 432 dòng + `GuildFbNpcRelation`).
2. Bảng trọng số xác suất ra từng tướng lẻ của máy chủ Gacha (client chỉ có danh sách hiển thị `outShowAll` và bảng `Blessodds`/`RatioOdds`).
3. Nguồn rơi gameplay của món Trang Bị Kim (`colorLV=8`) đầu tiên và bảng giá Cường Hóa `EquipLvUpuseRelation[8]` trong `VN 5.0.4.98`.
4. Công thức chi tiết trọng số FAP thứ cấp bậc cao (khi `DAMADD/DAMCUT/DAMADDR/DAMCUTR/CRID/TEND > 0`).
