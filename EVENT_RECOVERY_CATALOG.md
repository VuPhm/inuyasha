# InuYasha: Seek Jade (VN 5.0.4.98) — Event Archive & R7.5+ Activity Recovery Catalog

**Status:** Baseline Event Runtime/Archive + 4 playable activities shipped in R7.5 (`checkpoint-vn-r7.5`); updated Multi-Banner & Daily `00:00 UTC+7` Event Archive rules tracked in [PROJECT_ROADMAP.md](file:///Users/vup/Documents/agy/inuyasha/PROJECT_ROADMAP.md) & [R7_5_EVENT_CATALOG.md](file:///Users/vup/Documents/agy/inuyasha/R7_5_EVENT_CATALOG.md)  
**Canonical Client:** `com.cmn.inuyasha v5.0.4.98` (VN Lua + Config tables in [analysis/vn/decompiled_src/](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src))  
**Prior Audit Reference:** [R7_3_FULL_RECOVERY_AUDIT.md](file:///Users/vup/Documents/agy/inuyasha/R7_3_FULL_RECOVERY_AUDIT.md)

---

## 1. Objective for R7.5+

Enable full solo / local-friend playability across **time-limited events, recurring dailies, guild/team dungeons, and UR Timed Recruit banners** through an offline **Event Archive** scheduler without requiring an external live-ops backend or fake client-side bypasses.

---

## 2. Verified Config & UI Dependency Inventory (VN `5.0.4.98`)

### A. Permanent & Recurring Daily Activities (High Priority Early R7.5)

| System | Lua UI Modules | Config Tables (`items_count`) | Client RPCs (`Module.Method`) | Current R7.4 State |
|---|---|---|---|---|
| **Daily Tasks & Credit** | [DailyTasksLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/Task/DailyTasksLayer.lua), [TimedTask.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/Task/TimedTask.lua) | Task / Active point configs | `DailyTaskInfo.GetCredit`, `OneKeyDone`, `OneKeyAllDone` | Not implemented |
| **Monthly Sign-In** | [MonthlySignLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/ExtraActivity/MonthlySignLayer.lua) | Sign-in reward table | `MonthSignInfo.GetInfo` (stub `[]`), `MonthSignInfo.DrawReward` | Stubbed `GetInfo` |
| **Zcsf (Chiêu Tài)** | [CoinFundLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/ExtraActivity/CoinFundLayer.lua) | VIP count + Gold return configs | `Zcsf.ZcsfInfo`, `Zcsf.ZC` | Not implemented |
| **Lucky Cat / Online** | [LuckyCatLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/ExtraActivity/LuckyCatLayer.lua) | Level/VIP tiers | `OnlineReward.OnlineRewardInfo` (stub `{}`) | Stubbed |
| **Cumulative Sign / Activity** | [CumulativeSignLayer.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/OpenActivity/CumulativeSignLayer.lua) | `EarlytaskFinishRecord` | `EarlytaskFinishRecord.GetEarlytaskList`, `DrawEarlytaskGift` | Not implemented |

### B. Limited-Time Events (`TimedActivityScene` / `TimedInfo` / Special Banners)

Verified in [TimedActivityScene.lua](file:///Users/vup/Documents/agy/inuyasha/analysis/vn/decompiled_src/TimedActivity/TimedActivityScene.lua#L19-L160):

| Event Category | Lua UI Module(s) | Verified Configs (`Config/`) | Verified Client RPCs | Notes |
|---|---|---|---|---|
| **Timed Recruit (UR Tướng Thần)** | `TimedRecruitLayer.lua`, `LimittedTimedRecruitLayer.lua`, `TimedRecruitChoiceBoxLayer.lua` | `TimedRecruitModel` (6), `TimedRecruitCreditrewardRelation` (36), `TimedRecruitRankrewardModel` (6), `TimedRecruitRatioOddsRelation` (11), `TimedRecruitBlessoddsModel` (6) | `TimedRecruitInfo.GetTimedRecruitInfo`, `Recruit`, `DrawCreditReward`, `DrawGoldHero` | Primary source of `quality=18` UR heroes alongside `16060008` boxes |
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
   - Implemented in R7.5 (`EventHandlersMixin._build_timed_activity_open_info`): populated dynamically in `Player.GetInitData` and `Avatar` updates from active `EventRuntime` instances; R7.6 expands this to emit multiple concurrent banners cleanly.
2. **Scheduling & Multi-Banner Modes (Single-Player & Archive-First, Updated for R7.6+):**
   - **Default Daily Reset (`00:00 UTC+7`) + Custom Per-Event Period:** Local `EventClock` resets daily activities/banners at `00:00 UTC+7` by default, with per-event cycle overrides and zero Internet requirement.
   - **Concurrent Multi-Banner & Multi-Event Activation:** Allow standard (`HeroRecruit`) + multiple limited banners (e.g., `81`, `82`, future complete banners) and events to run simultaneously with fully isolated pools, costs, counters, credits, pity (`OutZiCount` / Bless), and rewards (using compatible banner selection where legacy Lua UI only displays one same-type slot).
   - **Manual Reset & Archive Replay:** Allow players to manually reopen or reset individual restored events with explicit confirmation, settling eligible rewards, archiving old instances without losing characters/items/history, and never pre-unlocking rewards.
3. **Config Extraction Delta for `extract_game_data.py`:**
   - Expand extraction to cover: `TimedRecruitCreditrewardRelation`, `TimedRecruitRankrewardModel`, `TimedRecruitRatioOddsRelation`, `TimedRecruitBlessoddsModel`, `LimitthebountyModel`, `ActiverankingModel`, `TeambattleNodeModel`, `TeambattleShopModel`, `GuildBossModel`, `GuildFbNodeModel`, `GuildShopModel`, `GddhShopModel`, `GoddomainShopModel`, `RebornLvActiveModel`, and `DailyTask` / `MonthSign` tables.
4. **Synthetic Peers & Economy Guardrails:**
   - Use deterministic simulated bots for `GlobalOpencontestRank` / `TimedRecruit` rankings while keeping player rewards routed strictly through `ResourceLedger` (`idempotency_key` per event cycle/milestone).
