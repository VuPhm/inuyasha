# InuYasha: Seek Jade — R7.9 Acceptance Report
**Historical Events, Lucky Activities & Multi-Region Recovery**

- **Build / Version:** `5.0.4.98-r7.9` (`versionCode=790`, `com.cmn.inuyasha.revival`)
- **APK Artifact:** `analysis/vn/patched/com.cmn.inuyasha.revival_r7_9_standalone.apk` (224,166,129 bytes)
- **Preserved R7.8 Beta Artifact:** `analysis/vn/patched/com.cmn.inuyasha.revival_r7_8_beta.apk` (`versionCode=780`, untouched)
- **Unit & Integration Tests:** **55 / 55 PASS** (`python3 server/test_emulator.py -v`, 44.4s)
- **Target Device Verification:** Google Pixel 3 XL (`adb-8A3Y0EDTX-AveQrp._adb-tls-connect._tcp`) upgraded in-place `780 -> 790` with all 4 S1 accounts (`TK1 FoxZora`, `TK2 OlinaHugh`, `TK3`, `TK4 TomNoel`) preserved.

---

## 1. Executive Summary

R7.9 recovers and makes genuinely playable end-to-end **30 historical events, lucky minigames, milestone activities, community/ranking events, and multi-region systems** across both the shared Python emulator (`server/`) and the self-contained Android Standalone APK (`com.cmn.inuyasha.revival`). Every recovered event deducts real costs via `ResourceLedger`, grants real rewards with idempotency / anti-duplicate protection, updates `RedDotInfo` and `DailyTaskInfo`, and supports `00:00 UTC+7` daily resets + confirmed manual resets.

---

## 2. Recovered Event Matrix (VN + Multi-Region)

| Category | Module ID | Lua / Scene | Server RPCs | Config Source | Status |
|---|---|---|---|---|---|
| 1. Cây Tiền May Mắn | `4432` | `TimedMoneyTreeLayer` | `TimedMoneyTree.{GetInfo,ShakeTree,DrawReward}` | VN + Modeled Pool | **Playable** |
| 1. Cây Cầu Nguyện | `4409` | `TimedPrayTree` | `TimedHopetreeInfo.{GetInfo,DrawReward}` | VN | **Playable** |
| 2. Quay Số / Slot | `4412` | `TimedSlotLayer`, `SlotMachine` | `TimedLuckdrawInfo.{GetInfo,Luckdraw}` | VN + Modeled Pool | **Playable** |
| 2. Đoạt Bảo 1 Ngọc | `7800` | `YiJiDuoBaoLayer` | `YiYuan.{GetInfo,Join,DrawReward}` | VN | **Playable** |
| 3. Đập Trứng Vàng | `4426` | `TimedSmashEggLayer` | `TimedSmashingeggsInfo.{GetRewardList,GetSmashingRecord,SmashingEggs}` | VN + Modeled Pool | **Playable** |
| 3. Chiêu Mộ Thần Binh | `4410` | `TimedRecruitEquipLayer` | `TimedXssbInfo.{GetInfo,CallEquip,ReceiveReward}` | **TW 1.4 `XssbModel`** | **Playable** |
| 4. Quà Online | `3700` | `OnlineReward` | `OnlineReward.{OnlineRewardInfo,DrawOnlineReward}` | VN | **Playable** |
| 4. Điểm Danh Tháng | `2712` | `MonthlySignLayer` | `MonthSignInfo.{GetInfo,DrawReward}` | VN | **Playable** |
| 4. Lì Xì Liên Server | `5501` | `RandomRedBagLayer` | `RandomRedBag.{GetRandomRedBagInfo,ReceiveRandomRedBag}` | VN | **Playable** |
| 5. Giờ Vàng Mua Sắm | `6800` | `TimeSpikeLayer` | `Timespike.{GetInfo,ReceivedReward}` | VN `TimespikeModel` | **Playable** |
| 5. Trùm Mua Sắm | `7000` | `TimeSpikeKingLayer` | `TimesMiaosha.{GetInfo,Receive}` | VN | **Playable** |
| 5. 10 Vạn Kim Cương | `8200` | `ShiWanDiamond` | `Swdiamonds.{GetSwdiamondInfo,GetSwdiamondReward}` | VN `ShiwanyuanbaoModel` | **Playable** |
| 5. Nạp Đơn / Nạp Tổng / Tiêu Phí / Ngày Nạp / x2 KC / Tích Lũy Ngày | `4401..4407, 4427` | `TimedChargeSingle..TimedAccumulatedLoginLayer` | `TimedInfo.*` | VN | **Playable** |
| 5. Quà Chọn Nạp | `4429` | `TimedChargeGiftLayer` | `TimedChargeGift.{GetChargeGiftInfo,ReceiveChargeGift}` | VN | **Playable** |
| 5. Nhiệm Vụ Hạn Giờ | `4700` | `TimedTaskListLayer` | `TimedCriticalInfo.{Info,Reward}` | **TW 1.4 `CriticalTasksTypeRelation`** | **Playable** |
| 6. Đổi Thưởng Hạn Giờ | `4406` | `TimedExchange` | `TimedLimitExchange.{GetInfo,Exchange}` | VN | **Playable** |
| 6. Shop Điểm Tích Lũy | `4428` | `TimedPointsMallLayer` | `TimedChargeScore.{GetRewardList,BuyGoods}` | VN | **Playable** |
| 6. Thương Nhân Thần Bí | `4300` | `LimitStoreScene` | `TraderInfo.{GetInfo,RefreshtGoodsList,BuyGoods}` | **TW 1.4 `TraderConfig`** | **Playable** |
| 6. Nhiệm Vụ Tăng Cấp | `2600` | `OpenActivityLayer` | `EarlytaskFinishRecord.{GetEarlytaskList,DrawEarlytaskGift}` | **TW 1.4 `EarlytaskModel` & `EarlytaskRewardRelation`** | **Playable** |
| 6. Giftcode & Chia Sẻ | `2716, 2705` | `CDKExchangeLayer`, `DailyShareLayer` | `ActiveGift.ActiveGift`, `ShareInvite.GetShareReward` | VN | **Playable** |
| 7. Đua Top Mở Server 7 Ngày | `7900` | `OpenSeriveCompetitionLayer` | `GlobalOpencontestRank.{GetActiveRank,GetRank,DrawReward}` | VN `Opencontest*Model` | **Playable (S1 Multi-Account)** |
| 7. BXH Nạp / Tiêu / Năng Động | `4421, 4422, 4430` | `ChargeRankLayer`, `TimedActivityRankLayer` | `TimedInfo.GetChargeRankInfo`, `GetUseDiamondRankInfo`, `TimedScoreRank.*` | VN `ActiverankingModel` | **Playable (S1 Multi-Account)** |
| 8. Chiêu Mộ Thần Tướng | `9300` | `TimedRecruit` (Banners 81 & 82) | `TimedRecruitInfo.*` | VN `TimedRecruit*Model` | **Playable (Concurrent)** |

---

## 3. Multi-Region Recovery (`TW 1.4 -> VN 5.0.4.98`)

- Recovered the `TW 1.4` (`com.infinite.qyc4_1.4`) XXTEA key `b"c0c0s3_InUyASHa_"` and decrypted 15 Config tables into `analysis/tw_1.4_recovered_configs/`.
- Adapted and validated 5 missing VN Config tables against `VN 5.0.4.98` IDs (`moduleID`, `GoodsModel`, `EquipModel`, `HeroModel`), fixing cross-region mismatches:
  - `CriticalTasksTypeRelation` type 7 `moduleID` `2506 -> 2507` (`ePracticeBloodyDemonDomain`).
  - `EarlytaskModel` tasks `2620/2621/2626` mapped to valid VN `2203/2301/1200`.
  - `EarlytaskRewardRelation` task `2623` TW-only Wraith IDs mapped to valid VN chests `16020022, 16020023, 16060002`.
  - Localized strings to Vietnamese and bundled all 5 encrypted `.luac` tables (`XssbModel`, `CriticalTasksTypeRelation`, `EarlytaskModel`, `EarlytaskRewardRelation`, `TraderConfig`) into `assets/src/Config/` in the R7.9 Standalone APK.

---

## 4. `TimedActivityScene` (`4400`) & `HomeScene` Fixes

- Fixed `Player.GetInitData` `ModulesInfo` check in `server/emulator.py` so `SubModuleId=4400` (`eTimedActivity`) reports `IfOpen=1` whenever any `4401..4432` child event is active in `TimedActivityOpenInfo`.
- Set `OpencontestState=1` in `PlayerInfo` and `GetInitData` so `Đua Top SV Mới` (`7900`) appears on `HomeScene`.
- Wired `RedDotInfo` flags for `2712, 3700, 4300, 4409, 4410, 4412, 4426, 4432, 4700, 5501, 6800, 7000, 7001, 7002, 7800, 7900, 8200`.
- Hooked `recharged_diamonds` into simulated recharge (`_apply_simulated_charge`, `_rpc_card_activity`) and `spent_diamonds` centrally into `_handle_rpc_locked`.

---

## 5. Verification Evidence

1. **Automated Unit & Integration Suite:**
   - `python3 server/test_emulator.py -v` -> **55 / 55 PASS** (`OK`, 44.4s), including `test_51`..`test_55` covering all R7.9 RPCs, TW 1.4 recovered configs, S1 multi-account community rankings, `00:00 UTC+7` daily resets, and save persistence.
2. **Pixel 3 XL On-Device Verification (`780 -> 790` In-Place Upgrade):**
   - `adb install -r analysis/vn/patched/com.cmn.inuyasha.revival_r7_9_standalone.apk` -> `Success`, `versionCode=790`, `versionName=5.0.4.98-r7.9`.
   - Verified via `/health` and `/account` on the phone's `127.0.0.1:18082` that all 4 R7.8 saves (`TK1 FoxZora Lv.8`, `TK2 OlinaHugh Lv.20`, `TK3`, `TK4 TomNoel Lv.6`) remained 100% intact.
   - Verified live R7.9 RPCs (`Player.GetInitData`, `TimedMoneyTree.GetInfo`, `TimedXssbInfo.GetInfo`, `TimedCriticalInfo.Info`, `EarlytaskFinishRecord.GetEarlytaskList`, `TraderInfo.GetInfo`, `GlobalOpencontestRank.GetRank`, `TimedSmashingeggsInfo.GetRewardList`, `TimedLuckdrawInfo.GetInfo`) all returned `Status=0` from the embedded Python 3.11 backend (`libinubackend.so`) on Pixel 3 XL.
   - Verified visually on Pixel 3 XL (`HomeScene` & `TimedActivityScene` `GIỜ VÀNG`) that all top-bar event icons and the 19 `TimedActivityScene` tabs render and display claimable rewards.
