# InuYasha: Seek Jade (VN 5.0.4.98) — Event Archive & R7.5+ Activity Recovery Catalog

**Status:** Planning & Dependency Inventory completed in R7.4 (Implementation queued for R7.5+)  
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
   - Currently `emulator.py` returns `"TimedActivityOpenInfo": {}` in `Player.GetInitData` and `Avatar` updates ([emulator.py](file:///Users/vup/Documents/agy/inuyasha/server/emulator.py#L1775-L1787)).
   - Populate `TimedActivityOpenInfo` dynamically from an explicit `event_archive` registry in state + `extract_game_data.py` extracted tables.
2. **Dual Scheduling Modes (Single-Player Friendly):**
   - **Auto-Rotation Schedule:** Deterministic weekly/multi-day cycle indexed by player start date or local clock so events rotate naturally without external servers.
   - **Manual Event Archive Activation:** Admin/local toggle allowing the player to activate/pin specific classic events (e.g., UR `TimedRecruit` Banner #1..#6, `TimedMoneyTree`, `TimedSmashEgg`, `TimedChargeTotal`) for solo completion.
3. **Config Extraction Delta for `extract_game_data.py`:**
   - Expand extraction to cover: `TimedRecruitCreditrewardRelation`, `TimedRecruitRankrewardModel`, `TimedRecruitRatioOddsRelation`, `TimedRecruitBlessoddsModel`, `LimitthebountyModel`, `ActiverankingModel`, `TeambattleNodeModel`, `TeambattleShopModel`, `GuildBossModel`, `GuildFbNodeModel`, `GuildShopModel`, `GddhShopModel`, `GoddomainShopModel`, `RebornLvActiveModel`, and `DailyTask` / `MonthSign` tables.
4. **Synthetic Peers & Economy Guardrails:**
   - Use deterministic simulated bots for `GlobalOpencontestRank` / `TimedRecruit` rankings while keeping player rewards routed strictly through `ResourceLedger` (`idempotency_key` per event cycle/milestone).
