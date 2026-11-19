# InuYasha: Seek Jade (VN 5.0.4.98) — Event Archive & R7.5+ Activity Recovery Catalog

**Status:** Hoàn thành R7.9 Historical Events, Lucky Activities & Multi-Region Recovery (`checkpoint-vn-r7.9`, **55/55** unit test PASS, Android Standalone `versionCode=790` nghiệm thu Pixel 3 XL); chi tiết trong [R7_9_ACCEPTANCE_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R7_9_ACCEPTANCE_REPORT.md), [PROJECT_ROADMAP.md](file:///Users/vup/Documents/agy/inuyasha/PROJECT_ROADMAP.md), [R7_5_EVENT_CATALOG.md](file:///Users/vup/Documents/agy/inuyasha/R7_5_EVENT_CATALOG.md) & [R7_6_ACCEPTANCE_REPORT.md](file:///Users/vup/Documents/agy/inuyasha/R7_6_ACCEPTANCE_REPORT.md)  
**Canonical Client:** `com.cmn.inuyasha v5.0.4.98` (VN Lua + Config tables in [analysis/vn/decompiled_src/](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src))  
**Prior Audit Reference:** [R7_3_FULL_RECOVERY_AUDIT.md](file:///Users/vup/Documents/agy/inuyasha/R7_3_FULL_RECOVERY_AUDIT.md)

**Delta R7.10:** Vé Slot VN `16050027`, rút 10 lần và popup thưởng, Cây Tiền và nhận mốc trên Pixel. Quyền chọn UR chưa dùng được gửi vào Trung Tâm Thưởng khi đổi kỳ. Các khóa nhận thưởng và phát vé gắn tài khoản S1. Xem [báo cáo R7.10](R7_10_ACCEPTANCE_REPORT.md) để phân biệt bằng chứng UI, RPC và nguồn của bảng thưởng.

---

## 1. Objective for R7.5+

Enable full solo / local-friend playability across **time-limited events, recurring dailies, guild/team dungeons, and UR Timed Recruit banners** through an offline **Event Archive** scheduler without requiring an external live-ops backend or fake client-side bypasses.

---

## 2. Verified Config & UI Dependency Inventory (VN `5.0.4.98`)

### A. Permanent & Recurring Daily Activities (High Priority Early R7.5)

| System | Lua UI Modules | Config Tables (`items_count`) | Client RPCs (`Module.Method`) | Current R7.4 State |
|---|---|---|---|---|
| **Daily Tasks & Credit** | [DailyTasksLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/Task/DailyTasksLayer.lua), [TimedTask.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/Task/TimedTask.lua) | `DailytaskModel` (25), `DailytaskReward` (5), `DailytaskExp` (100) | `DailyTaskInfo.GetCredit`, `DrawReward`, `OneKeyDone`, `OneKeyAllDone` | **Playable (R7.5+, reset `00:00 UTC+7`)** |
| **Monthly Sign-In** | [MonthlySignLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/ExtraActivity/MonthlySignLayer.lua) | Server-driven 30 ngày | `MonthSignInfo.GetInfo`, `MonthSignInfo.DrawReward` | **Playable (R7.9, reset theo tháng)** |
| **Zcsf (Chiêu Tài)** | [CoinFundLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/ExtraActivity/CoinFundLayer.lua) | `ZcsfTypeRelation` (6), `ZcsfUseRelation` (10) | `Zcsf.ZcsfInfo`, `Zcsf.ZC` | **Playable (R7.6, Lv 21, nối `DailyTask #16`)** |
| **Xhzw (Ước)** | [XhzwLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/Practice/XhzwLayer.lua) | `XhzwConfig` (6), `XhzwLipRelation` (6), `XhzwRewardRelation` (10), `XhzwRewardRefreshPrice` (1) | `Xhzw.GetXhzwInfo`, `XhzwTurn`, `XhzwAlterLuck`, `XhzwAlterLuckLock`, `RefreshXhzwRewardList`, `ReceiveRewardForOneKey` | **Playable (R7.6, Lv 30, nối `DailyTask #8`)** |
| **Lucky Cat / Online** | [LuckyCatLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/ExtraActivity/LuckyCatLayer.lua), `OnlineReward` | Server-driven tiers | `OnlineReward.OnlineRewardInfo`, `DrawOnlineReward` | **Playable (R7.9)** |
| **Cumulative Sign / Earlytask** | [OpenActivityLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/OpenActivity/OpenActivityLayer.lua) | **TW 1.4 `EarlytaskModel` (24), `EarlytaskRewardRelation` (239)** | `EarlytaskFinishRecord.GetEarlytaskList`, `DrawEarlytaskGift` | **Playable (R7.9, Multi-Region)** |

### B. Limited-Time Events (`TimedActivityScene` / `TimedInfo` / Special Banners)

Verified in [TimedActivityScene.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/TimedActivity/TimedActivityScene.lua#L19-L160):

| Event Category | Lua UI Module(s) | Verified Configs (`Config/`) | Verified Client RPCs | Notes |
|---|---|---|---|---|
| **Timed Recruit (UR Tướng Thần)** | `TimedRecruitLayer.lua`, `LimittedTimedRecruitLayer.lua`, `TimedRecruitChoiceBoxLayer.lua` | `TimedRecruitModel` (6), `TimedRecruitCreditrewardRelation` (36), `TimedRecruitRankrewardModel` (6), `TimedRecruitRatioOddsRelation` (11), `TimedRecruitBlessoddsModel` (6) | `TimedRecruitInfo.GetTimedRecruitInfo`, `SelectBanner` (R7.6), `Recruit`, `DrawCreditReward`, `DrawGoldHero` | **Playable (R7.5+) & Multi-Banner đồng thời `81 + 82` (R7.6)** |
| **Limitthebounty (Săn Thưởng)** | `LimitthebountyLayer.lua` | `LimitthebountyModel` (6) | `Limitthebounty.GetInfo`, `ReceivedReward` | **Playable (R7.6, TriggerLv 12/15/20/25/35/45)** |
| **Treasure & Rebirth (Phát triển)** | `EquipmentScene.lua`, `TreasureExtraLayer.lua`, `DisassembleNewScene.lua` | `TreasureLvRelation` (100), `TreasureLvActiveRelation` (106), `TreasureStepRelation` (33), `TreasureStepAttrRelation` (60), `HeroRebirthRelation` (18), `EquipRebirthRelation` (8), `TreasureRebirthRelation` (4), `RebornLvModel` (340) | `Treasure.TreasureLvUp` (1402), `Treasure.TreasureStepUp` (1404), `Hero.HeroRebirth`, `Equip.EquipRebirth`, `Treasure.TreasureRebirth` | **Playable (R7.6)** |
| **Recharge & Spend Milestones** | `TimedChargeSingle.lua`, `TimedChargeTotal.lua`, `TimedUseTotal.lua`, `TimedAccumDays.lua`, `TimedDoubleDiamond.lua`, `TimedChargeGiftLayer.lua` | `TimedActivityModel` / server-driven tiers | `TimedInfo.GetChargeSingleInfo`, `GetChargeTotalInfo`, `DrawChargeTotalReward`, etc. | Hooks cleanly into `PlayerCharge.ConfirmOrder` / `Diamond` spend ledger |
| **Timed Exchange & Points Mall** | `TimedExchange.lua`, `TimedPointsMallLayer.lua` | Config relations + item pools | `TimedInfo.*` | Material/currency swap |
| **Minigames (Slot / MoneyTree / SmashEgg / PrayTree)** | `TimedSlotLayer.lua`, `TimedMoneyTreeLayer.lua`, `TimedSmashEggLayer.lua`, `TimedPrayTree.lua`, `YiJiDuoBaoLayer.lua` | Per-activity reward relations | `TimedLuckdrawInfo.Luckdraw/GetInfo`, `TimedMoneyTree.GetInfo/ShakeTree/DrawReward`, `TimedSmashingeggsInfo.GetRewardList/SmashingEggs/GetSmashingRecord`, `TimedHopetreeInfo.GetInfo/DrawReward`, `TimedCriticalInfo.Info/Reward`, `TimedXssbInfo.GetInfo/CallEquip/ReceiveReward`, `YiYuan.GetInfo/Join/DrawReward` | Suitable for Event Archive rotation |
| **Bounty / Spike / Rank Contests** | `LimitthebountyLayer.lua`, `TimeSpikeLayer.lua`, `ChargeRankLayer.lua`, `TimedActivityRankLayer.lua` | `LimitthebountyModel` (6), `ActiverankingModel` (12) | `Limitthebounty.GetInfo/ReceivedReward`, `Timespike.GetInfo/ReceivedReward`, `TimesMiaosha.GetInfo/Receive`, `GlobalOpencontestRank.GetRank/GetActiveRank/DrawReward` | Requires synthetic offline ranking peers |

### C. Mid/Endgame Cooperative, Guild & Competitive Systems

| System | Verified Configs (`items_count`) | Verified Shops / Dependencies | Notes |
|---|---|---|---|
| **Team Battle (PB Tổ Đội)** | `TeambattleConfig` (1), `TeambattleNodeModel` (24), `TeambattleHeroNpc`, `TeambattlePlayerNpc`, `TeambattleShopModel` (18) | `TeambattleInfo.GetInviteInfo` (currently stub `{}`) | Also feeds `SuccessTargetModel` ID `27` |
| **Guild (Bang Hội)** | `GuildConfig` (1), `GuildBossModel` (3), `GuildFbNodeModel` (10), `GuildShopModel` (22), `GuildDonateRelation`, `GuildBuildingModel`, `GddhShopModel` (16), `GoddomainShopModel` (44) | Full local guild + synthetic members + Raid Boss | Requires synthetic guild state & contributions |
| **Legacy / Comeback Events** | `OlderUserActivity/`, `RebornLvActiveModel` (9), `RebornShopOddsRelation` | `OldPlayer.*`, `OldPlayerNewServer.*` | Optional Archive preset |

---

## 3. Event Archive Architecture Design (For R7.5+)

1. **`TimedActivityOpenInfo` Broadcast Channel:**
   - Implemented in R7.5 (`EventHandlersMixin._build_timed_activity_open_info`): populated dynamically in `Player.GetInitData` and `Avatar` updates from active `EventRuntime` instances; updated in R7.6 to emit ALL simultaneously active banners (`[81, 82]`) under default `mode = "concurrent"`.
2. **Scheduling & Multi-Banner Modes (Single-Player & Archive-First, R7.6 Default):**
   - **Default Daily Reset (`00:00 UTC+7`) + Custom Per-Event Period:** Local `EventClock` resets daily activities and active banners at `00:00 UTC+7` by default (`period_mode = "daily_utc7"`), with per-event `period_overrides` and zero Internet requirement.
   - **Concurrent Multi-Banner & Multi-Event Activation:** `mode = "concurrent"` runs Standard (`HeroRecruit`) + Banner `81` + Banner `82` (plus daily `Zcsf`, `Xhzw`, `Xxbz`, `DailyTask`, `Dinner`) simultaneously with isolated `progress`/`instance_id` per event, paired with the `SelectBanner` APK tab selector on `LimittedTimedRecruitLayer`.
   - **Confirmed Manual Reset & Archive Replay:** `EventRuntime.manual_reset_event(..., confirm=True)` requires explicit confirmation (HTTP `400` without `confirm=True`), resets only the selected event via the 5-step settlement pipeline (archive history -> settle eligible unclaimed credit/rank rewards to `RewardCenter` -> create `rN` instance -> reset counters -> preserve player inventory/history).
3. **Config Extraction Delta for `extract_game_data.py`:**
   - **Completed in R7.5–R7.6:** Extracted `TimedRecruit*`, `Xxbz*`, `Dailytask*`, `Zcsf*`, `Limitthebounty`, `Xhzw*`, `TreasureLv*`/`TreasureStep*`, `*RebirthRelation`, `RebornLvModel`, `TimeSpike`, `ActiveRanking`, `OpenContest*`. Remaining R7.7+ targets: `TeambattleNodeModel`/`ShopModel`, `GGZJ`, `Guild*`, `RebornLvActiveModel`.
4. **Synthetic Peers & Economy Guardrails:**
   - Use deterministic simulated bots for `GlobalOpencontestRank` / `TimedRecruit` rankings while keeping player rewards routed strictly through `ResourceLedger` (`idempotency_key` per event cycle/milestone).
