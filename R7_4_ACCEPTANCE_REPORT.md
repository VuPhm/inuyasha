# InuYasha: Seek Jade (VN 5.0.4.98) — R7.4 Acceptance Report
## Economy, Recruitment, VIP & Progression Blocker Recovery

**Date:** 2026-11-19  
**Branch / Target Checkpoint:** `master` -> `checkpoint-vn-r7.4` (DEV `:8082`)  
**Canonical Client:** `com.cmn.inuyasha v5.0.4.98`  
**Production / STABLE Status:** `checkpoint-vn-r6.2` (`5fed4bb`) on port `8080` (`OlinaHugh` Lv 20) — **untouched and preserved**  

---

## 1. Executive Summary

Round **R7.4** restored playable core economy, recruitment, VIP progression, VIP gift packs, open-server achievements (`Quà Thành Tích`), and UR hero selection chests on **DEV (`:8082`)**, verified with **37/37 automated unit/protocol tests** and **live Pixel 3 XL UI testing** against an isolated R7.4 DEV QA instance (`R74QA`, `PlayerId=200100`).

| Area | Scope | Automated Tests | Live Pixel 3 XL UI |
|---|---|---|---|
| **HeroRecruit (`1, 10, 2, 3, 30, 40`)** | Quality-tiered pools, `12011014` tutorial fix, `OutZiCount`, `16060005` `extraRewards`, `rtype=10` & `40` | PASS (`test_02, 10, 28, 32`) | PASS (`Mộng Cảnh X10`, `Linh Hồn X10`, `Phiếu Rút 10 Lần 40`) |
| **Offline Charge & Month Card** | Native `MessageBoxLayer` confirmation bypassing dead `com.kull.sdk` billing + order-ID replay guard | PASS (`test_16, 33`) | PASS (`300 tặng 300`, `Thẻ Tháng 90.000`, `DrawBuyReward +268`) |
| **VIP Sync, Perks & `ShopGift` (0..20)** | `Vip`/`VIPLv` derivation, `MysteryShop`/`Explore` scaling, all 21 VIP gift packs + `1601` bundle fix | PASS (`test_33, 34`) | PASS (`VIP0 -> VIP1 -> VIP2`, `Quà VIP2` + all 4 bundle items) |
| **`SuccessTargetInfo` (`4900`)** | Fixed Lv 11 `SuccessTargetLayer.luac:151` crash; all 5 RPCs across 42 targets / 327 rewards | PASS (`test_35`) | PASS (`GetInfo`, `DrawReward`, `GetExchangeInfo`, `Exchange`) |
| **`GoodsUseForBoxChoice` (`1606/1608`)** | Selection chest validation including `quality=18` UR heroes + fashion chests | PASS (`test_36`) | PASS (`16060008` -> `InuYasha` UR `12011004`) |
| **`LvPlan` Canonical Audit** | Verified VN `LvPlanRewardModel.lua` + `LevelPlanLayer.lua` (`needDiamond=100` per tier) | PASS (`test_15, 37`) | N/A (logic verified in Lua + tests) |
| **STABLE Isolation & Restore** | STABLE `:8080` untouched; Pixel 3 XL & `dev_saves` restored cleanly post-QA | PASS (`test_17, 24, 31`) | PASS (`OlinaHugh` Lv 20 loads on `:8080`) |

---

## 2. Recruitment Recovery (`HeroRecruit`) — Canonical vs. Server-Modeled Boundary

### A. Cause of Pre-R7.4 Kagome Loop
Previous `_rpc_recruit` selected `pool[idx % len(pool)]` from `outShowMain`. Single pulls (`count=1`, `idx=0`) repeatedly returned `pool[0]` (and Dream `10` charged Diamonds instead of `10x 16050003`).

### B. Canonical vs. Server-Modeled Separation

> [!IMPORTANT]
> Official `HeroRecruitModel.lua` tables across inspected VN (`5.0.4.98`), EN, TH, and ZH client assets define pools (`outShowAll` / `outShowMain`), summon costs (`recruitUse`), cooldowns (`freeTimeCD`), and bonus drops (`extraRewards`), **without any drop-rate probability table**. The emulator does **not** misrepresent modeled tier weights as official drop rates.

| Component | Source | Implementation Detail in [emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py) |
|---|---|---|
| Banner Pools & Hero Qualities | **Canonical (`HeroRecruitModel.lua` / `HeroModel.lua`)** | Dream `1/10`: `outShowAll` (`q=6, 10, 13`), `outShowMain` (`q=10`); Destiny `2`: `outShowAll` (`q=6, 10, 13`), `outShowMain` (`q=13`); Soul `3/30/40`: `outShowAll` (`q=10, 13, 15`), `outShowMain` (`q=15`). All `q=18` UR heroes are excluded from standard banners. |
| First Destiny Pull | **Canonical Tutorial** | `HeroRecruit.Recruit [2, 1]` when `not MidAlreadyUseResource` fixes `12011014` (*Ayame*). |
| Costs, Cooldowns & Extra Drops | **Canonical (`HeroRecruitModel.lua` / `BagScene.lua`)** | `rtype=1/10` consume `1`/`10` `16050003` (*Bùa Triệu Hồi*, no Diamonds); `2` costs `80` Diamond / `1380m` CD; `3` costs `280` Diamond / `2820m` CD + `16060005 x1`; `30` costs `2680` Diamond + `16060005 x10`; `40` consumes `1x 16050056` (*Phiếu Rút 10 Lần* per `BagScene.lua:1615`) + `16060005 x10`. Removed non-canonical `1000` fallback Gold. |
| `OutZiCount` & Guarantees | **Canonical + Restored Cycle** | New profiles initialize `OutZiCount=9` (`9..0` countdown across Soul draws; triggers `q=15` when `<= 0` and resets to `9`); first Soul pull guarantees `q=15`; 10x Soul (`30/40`) guarantees at least 1 `q=15` hero. |
| Quality Tier Weights (`RECRUIT_RATE_CONFIG`) | **Server-Modeled (Configurable)** | `{1: {6: 5000, 10: 4200, 13: 800}, 2: {6: 2500, 10: 5500, 13: 2000}, 3: {10: 4500, 13: 4500, 15: 1000}}` — weighted by quality tier first, then uniform within tier (never flat random across all heroes). |
| Persistence | **Server State** | `MidAlreadyUseResource`, `HigAlreadyUseResource`, `OutZiCount`, `GoodReadyAt`, `ExcellentReadyAt`, and rolling 50-entry `recruit_state.history` persist across server restarts. |

---

## 3. Offline Recharge, Month Card, VIP & `ShopGift`

1. **Client Confirmation Bypass (Dead SDK Replaced):**
   - Updated [poc/patch_vn_apk.py](file:///Users/vup/Documents/agy/inuyasha/poc/patch_vn_apk.py) (`--out` support added) to patch `Store/RechargeScene.luac` and `ExtraActivity/MonthCardLayer.luac`.
   - Clicking any Diamond bundle or Month Card inside original APK UI now displays a native `Common.MessageBoxLayer` confirmation modal (`"Xác nhận nạp X Kim Cương (Offline)?"` / `"Xác nhận kích hoạt Thẻ Tháng (Offline)?"`), then calls `PlayerCharge.GenerateOrderID` -> `PlayerCharge.ConfirmOrder` or `CardInfo.GenerateOrderID` -> `CardInfo.Activity` with `order_id` — zero calls to dead `com.kull.sdk` billing (`Dialogs.showPaymentByPackage`), and zero external payment traffic.
2. **Server Order Validation & `ResourceLedger` Idempotency:**
   - `PlayerCharge.ConfirmOrder` and `CardInfo.Activity` validate strictly against `CHARGE_TIERS` and `CARD_MODEL_CFG` (rejecting unknown products with `Status = -1`).
   - Replaying an already completed `order_id` or `card_order_id` returns `Status = -1136` without granting duplicate Diamonds or `VipEXP`.
   - Every grant records atomic idempotency keys in `audit_ledger.jsonl` via [economy_audit.py](file:///Users/vup/Documents/agy/inuyasha/server/economy_audit.py).
3. **Dynamic VIP Sync & Privileges:**
   - `_sync_player_recover_times` and `apply_player_delta("VipEXP", ...)` keep `Vip == VIPLv` synchronized with `VipModel` (`vip_model` thresholds), while preserving higher explicit pre-seeded test flags (`debug` profile).
   - Verified VIP perks dynamically track the active `VIPLv`: `VipWelfare` tier rewards (`0..20`), `MysteryShop` (`refreshMysteryShopMaxNum` & daily `freeRefreshMysteryShopMaxNum`), `Explore` (`exploreMaxNum` in `vip_model`), `BossBattle` (`attackLuckBossMaxNum`), and `Daydayfund` VIP multiplier.
4. **`ShopGift` (21 VIP Packs `0..20`) & Critical `1601` Fixed Bundle Fix:**
   - Implemented `ShopGift.ShopGiftList` and `ShopGift.BuyGift` backed by `ShopVipGiftModel` (`shop_vip_gift` Extracted in [extract_game_data.py](file:///Users/vup/Documents/agy/inuyasha/server/extract_game_data.py), packs `16010001..16010021` for VIP 0..20), enforcing VIP requirement and one-time lifetime purchase limit.
   - Fixed a critical pre-existing bug in `_rpc_goods_use` ([emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py)): all 32 `typeID == 1601` (`eBoxFixed`, including VIP packs) have `oddsMax=0` and previously picked only one random row via `random.choice`; `typeID == 1601` now grants **all** `GoodsOutputRelation` rows in the bundle.
5. **Canonical `LvPlan` Audit:**
   - Verified `analysis/vn/decompiled_src/Config/LvPlanRewardModel.lua` and `ExtraActivity/LevelPlanLayer.lua`: `needDiamond = 100` on every tier reward is original VN client logic (`LvPlan.OpenLvPlan` unlocks at VIP 2 free, and `ReceiveLvPlan` charges 100 Diamond per claimed milestone). No incorrect override was introduced (`test_37`).

---

## 4. Gameplay Blockers Resolved

### A. `SuccessTargetInfo` (`QUÀ THÀNH TÍCH`, RedDot `"4900"`)
- Extracted `SuccessTargetModel` (42 targets), `SuccessTargetRewardRelation` (327 milestone rows), `SuccessTimeModel` (8 day totals), and `SuccessPurchaseModel` (14 exchange offers across days `1..7`) in [server/game_data.json](file:///Users/vup/Documents/agy/inuyasha/server/game_data.json).
- Implemented all 5 RPCs (`GetInfo`, `DrawReward`, `DrawTotalReward`, `GetExchangeInfo`, `Exchange`) plus live `"4900"` RedDot calculation and real stat hooks across Battles, Explore, Recruits, LightenStar, Equips, MysteryShop, BossBattle, PVP, TreasureLoot, Daydayfund, and VIT/STA pill consumption (`stats` + derived slot/chapter metrics).
- Resolved the Lv 11 Lua crash (`SuccessTargetLayer.luac:151`) where `TargetList` was previously `nil`.

### B. `Goods.GoodsUseForBoxChoice` (`1606` / `1608`)
- Implemented `Goods.GoodsUseForBoxChoice` ([BagScene.lua:2475](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/Bag/BagScene.lua#L2475)) validating `box_gid` (`typeID` `1606` `eBoxChoice` or `1608` `eFashionChoice`) and verifying `selectedModelId` exists in `goods_output[oddsCode]`.
- Verified granting `quality=18` UR heroes (`InuYasha` `12011004`, `Sesshomaru` `12012005`, `Naraku` `12013005`) from `16060008` and fashions (`19010001`) from `16080001`, with `count <= 0` and invalid selection guards (`-1` without consuming the box).

---

## 5. Verification Evidence

### A. Automated Unit & Protocol Tests
Ran `python3 -m unittest discover -s server -p 'test_*.py' -v`: **37/37 PASS** (`Ran 37 tests`, 0 failures, 0 skipped), covering all 31 prior tests + 6 new R7.4 suites (`test_32`..`test_37`).

### B. Live Pixel 3 XL UI Verification (Isolated DEV QA `:8082`, Account `R74QA`, `PlayerId=200100`)
All live UI tests ran against an isolated QA save (`server/qa_runs/r7_4_live_saves/`) using the R7.4 APK pointed at `192.168.1.250:8082`:
- **`QUÀ THÀNH TÍCH` (`SuccessTargetLayer`)**: Opened via Home RedDot icon (`"4900": 1`), displayed `QUÀ SERVER` (`Tiến Độ: 1/19`), claimed Day 1 Login (`SuccessTargetInfo.DrawReward [3, 1]` -> `+600 Dia, +50k Gold, +10x 16050003`), exchanged `250 Dia -> 5 Thuốc Thể Lực 2` (`SuccessTargetInfo.Exchange [1, 1]`).
- **`Summon` (`RecruitScene`)**: Verified Dream X10 (`Recruit [10, 0]`) spent `10x 16050003` (`33 -> 23`, 0 Diamonds spent) and returned 10 mixed heroes; verified Soul modal showed `"RÚT THÊM 9 LẦN NHẬN TƯỚNG CAM"`, Soul X10 (`Recruit [30, 0]`) dropped spotlight Orange `Kanna (Tư Chất 15)` + `10x 16060005`.
- **Offline Recharge & Month Card (`RechargeScene`)**: Tapped `300 tặng 300` -> native `MessageBoxLayer` `"Xác nhận nạp 300 Kim Cương (Offline)?"` -> `GenerateOrderID` + `ConfirmOrder` -> `+600 Dia` (`3670 -> 4270`), `VIP0 -> VIP1`, first-charge `X2` badge cleared; switched to `Thẻ Tháng 90.000` -> confirmed offline -> `CardInfo.Activity` + `DrawBuyReward [1]` -> `+268 Dia` (`4270 -> 4538`), **`VIP1 -> VIP2 (600/860)`**.
- **VIP Shop Packs (`StoreScene -> Quà VIP`)**: Displayed all 21 tiers; purchased `Quà VIP2` (`ShopGift.BuyGift [16010003, 1]` -> automatic `Goods.GoodsUse [..., 16010003, 1]`), granting all 4 items (`Tamu-Mũ Linh`, `100K Gold`, `5x Refresh`, `2x STA Pill 2`), Diamonds `4538 -> 4440`, `Quà VIP3` remained locked grey at `VIP2`.
- **Bag Choice Chest & 10x Ticket (`BagScene`)**: Opened `16060008` (`Quà Thần Tướng A`) -> selected `InuYasha` UR (`12011004`, `quality=18`) -> `GoodsUseForBoxChoice` granted red UR hero (`18 -> 17` bag items); tapped `16050056` (`Phiếu Rút 10 Lần`) -> `HeroRecruit.Recruit [40, 0]` granted `Izayoi (15)` + 9 heroes + `10x 16060005` (`16060005 num=20`).
- **Restart & Persistence**: Restarted QA server and Pixel 3 XL app -> verified `R74QA`, `Lv 20`, `VIP 2`, `4440` Diamonds, `OutZiCount=6`, completed order IDs, `43` heroes (incl. `12011004`), and `55` `audit_ledger.jsonl` entries survived intact.
- **Note on Scope Split:** `16080001` (`eFashionChoice`), replay-attack rejection (`-1136`), and fresh Lv 1 tutorial `Ayame` (`12011014`) regression after R7.4 edits were verified via automated unit tests (`test_28, 32, 33, 36`); fresh Lv 1 Pixel 3 XL UI walkthrough was previously accepted in R7.2A.

### C. Environment Restoration & Environment Checks
- Pixel 3 XL `http_proxy` confirmed `null`; pre-R7.4 APK restored from [com.cmn.inuyasha_revival.apk](file:///Users/vup/Documents/agy/inuyasha/server/backups/pre_r7_4_apk/com.cmn.inuyasha_revival.apk); verified `OlinaHugh` Lv 20 loads on untouched STABLE `:8080`.
- `server/dev_saves/normal_profile.json` SHA256 verified unchanged (`3e071918b9f9adbe148a53816ddfd5ea2dae23ed9458dcae43e28a11af6b7f7f`); DEV daemon restarted on `:8082`.

---

## 6. Modified Files & Artifacts

- [server/extract_game_data.py](file:///Users/vup/Documents/agy/inuyasha/server/extract_game_data.py) & [server/game_data.json](file:///Users/vup/Documents/agy/inuyasha/server/game_data.json)
- [server/emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py)
- [server/test_emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/test_emulator.py) (`test_32`..`test_37`)
- [poc/patch_vn_apk.py](file:///Users/vup/Documents/agy/inuyasha/poc/patch_vn_apk.py) (`--out`, `RechargeScene.luac`, `MonthCardLayer.luac` offline dialogs)
- [EVENT_RECOVERY_CATALOG.md](file:///Users/vup/Documents/agy/inuyasha/EVENT_RECOVERY_CATALOG.md)
- [R7_4_ACCEPTANCE_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R7_4_ACCEPTANCE_REPORT.md)

**Next Step:** Await user review before promoting R7.4 to STABLE or beginning **R7.5** (Daily/Monthly/Activity & Event Archive implementation).
