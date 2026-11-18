# INUYASHA REVIVAL — R6.2 ACCEPTANCE & PROMOTION READINESS REPORT

**Target Ref:** `checkpoint-vn-r6.2`  
**STABLE Baseline (unchanged):** `checkpoint-vn-r5.2` on port `8080` (`PID 9709`, `server/saves/`: `OlinaHugh` Lv 16, `InuYasha` Lv 10)  
**DEV Target:** working tree / `checkpoint-vn-r6.2` on port `8082` (`server/dev_saves/`: `OlinaHugh` Lv 20 VIP 3, `InuYasha` Lv 10 VIP 5)  
**APK Modification:** None (`com.cmn.inuyasha` v5.0.4.98 untouched — server-side fixes only)

---

## 1. Phase A — BossBattle Hotfix

### Root Cause
Killing `LuckBoss` tier `12010052` returned `DropResource = {"TypeId": 1503, "ModelId": 15030101, "Num": 1}`. Across VN (`5.0.4.98`), EN (`5.1.1`), TH (`5.1.3.6`), and ZH (`5.0.0`) client tables, `TreasureDebrisModel.items[15030101]` does **not** exist (`1503` book debris start at `15032101` — *Sách Kaede1*, `treasureModelID=14010501`, icon `sp_32101.png` verified in VN OBB). In `CommonFunc.lua:1058`, `GetResourceQuality` indexed nil `debris`, crashing the client on victory (`BattleWinHintLayer.lua:514-516`). Existing DEV save `server/dev_saves/normal_profile.json` also carried `15030101` in `treasure_debris`.

### Server Fix (`server/emulator.py`)
- Replaced `15030101` with `15032101` in `ProfileStore.BOSS_DROP_POOL`:
  - `(1602, 16020020)` (*Đá Trang Bị Lam*), `(1602, 16020021)` (*Đá Trang Bị Tím*), `(1503, 15032101)` (*Sách Kaede1* -> *Sách Kaede* `14010501`), `(1504, 15040101)` (*Ngựa Xương1* -> *Ngựa Xương* `14020501`).
  - Kept the 4-entry pool rotation (`tier_idx % 4`), drop rates, counts, and resource quantities unchanged.
- Added resource validation helpers on `ProfileStore`: `_is_valid_resource()`, `_validate_resource_tuples()`, `validate_base_resource_list()`, `_boss_drop_for_model()`, `_sanitize_boss_drop()`.
- Enforced validation in `_grant_resources_from_tuples(..., validate_resources=True)`, `_sync_boss_battle_state()`, `_maybe_trigger_luckboss()`, `_rpc_boss_fight()`, `_rpc_boss_draw_box()`, and `_rpc_boss_one_key_draw_box()` so invalid IDs fail before mutating state or entering RPC payloads.
- Added `_sanitize_legacy_debris_and_boss_drops()` in `_normalize_loaded_state()` to migrate legacy `15030101 -> 15032101` cleanly (merging quantities without duplicates) in both `treasure_debris` and active `boss_battle.bosses[*].DropResource`.

---

## 2. Phase B — VIT & STA Recovery Stabilization

### Root Cause
Client `NetworkResData.lua:305-324` evaluates `VIT < VitConfig.items[1].maxNum` (`200`) every 0.5s and triggers `Player.AvatarInfo` whenever `VITNextRecoverTime <= mTimeTick`. Legacy R2 `debug_profile.json` carried `"VITMaxNum": 120`. `_sync_player_recover_times()` previously trusted `p.get("VITMaxNum", 200)` (`120`), so when `120 <= VIT < 200`, `VIT < 120` evaluated false and reset `VITNextRecoverTime = now`, triggering a continuous 0.5s `Player.AvatarInfo` polling loop (`rpc_trace.log:746-3734`). Furthermore, `_rpc_sync_avatar()` copied `self.state["player"]` before `handle_rpc()` called `_sync_player_recover_times()`, and the `STAMaxNum` fallback was `40` instead of `sta_config.maxNum` (`20`).

### Server Fix (`server/emulator.py`)
- Added `_canonical_recover_limits()` reading `vit_config` (`maxNum=200`, `recoverCD=360`) and `sta_config` (`maxNum=20`, `recoverCD=900`).
- Updated `_sync_player_recover_times()`:
  - Normalizes `VITMaxNum = max(cfg_vit_max, saved_vit_max)` (`120 -> 200`, preserving any valid higher VIP/custom cap like `250`).
  - Normalizes `STAMaxNum = max(cfg_sta_max, saved_sta_max)` (`<20 -> 20`, preserving `debug` `40`).
  - Keeps `VITNextRecoverTime` strictly in `(now, now + 360]` when `VIT < VITMaxNum` and sets `now` when `>= VITMaxNum` (symmetric for `STA` with `recoverCD=900`), leaving `VIT`/`STA` recovery formulas and over-cap values untouched.
- Updated `_rpc_sync_avatar()` to invoke `_sync_player_recover_times()` before returning `Value` and persist if recovery fields were repaired.

---

## 3. Verification Summary

### Automated Unit & Regression Tests (`server/test_emulator.py`)
- Ran `python3 -m unittest discover -s server -p 'test_*.py' -v`: **26/26 OK** (`Ran 26 tests in 5.519s`), including new tests:
  - `test_25_boss_battle_drop_pool_validation_kill_and_legacy_migration`: verifies entire `BOSS_DROP_POOL`, all boss models `12010050..12010055`, all 35 `luckboss_value_shop` rows, rejection of invalid resource tuples/payloads, full Boss `12010052` lifecycle (spawn -> normal attack leaving Boss alive -> All-Out kill -> `15032101` drop -> `GetBossList` close -> save/reload), and legacy `15030101` save/boss migration & merge.
  - `test_26_vit_and_sta_limit_normalization_and_no_polling_loop`: verifies `VitConfig=200` / `StaConfig=20`, `120 -> 200` upgrade, zero polling loop across repeated `Player.AvatarInfo` calls (`VITNextRecoverTime > now` in both `Value` and `Avatar`), VIT boundaries (`80, 199, 200, 235`, VIP `250`), and STA boundaries (`10->20`, `20`, `debug` `35/40`, `OlinaHugh` `143/20`).

### Live HTTP Verification on DEV (`http://127.0.0.1:8082`)
- **OlinaHugh (`ServerId=1`):** `Player.GetInitData` confirmed `PlayerName="OlinaHugh"`, `Lv=20`, `Vip=3`, `Gold=1552861`, `Diamond=4695`, `VIT=80/200`, `STA=143/20`, legacy `15030101` auto-migrated to `15032101`, active boss `12010051` (`DropResource=16020021`), 3x `Player.AvatarInfo` confirmed `VITNextRecoverTime > now` and `STANextRecoverTime <= now` (zero polling).
- **InuYasha (`ServerId=2`):** 3x `Player.AvatarInfo` confirmed `VITMaxNum` upgraded `120 -> 200`, `STAMaxNum=40` preserved, `VITNextRecoverTime > now`.
- **Full BossBattle HTTP lifecycle on DEV (`ServerId=2`, backed up & cleanly restored afterward):**
  - Spawned `12010052` (`DropResource={'TypeId': 1503, 'ModelId': 15032101, 'Num': 1}`) -> Normal attack (`HurtValue=78106`, `SingleJiFen=640`, `TreasureDebrisModelId=15032101` granted) -> Spawned 2nd `12010052` + All-Out Attack (`mode=1`, `HurtValue=78106`, `15032101` granted) -> `BossBattle.GetBossList` + `BoxList` -> Restarted DEV daemon -> Confirmed reloaded `Player.GetInitData` & `BossBattle.GetBossList` persisted `JiFen=1280`, `debris=[(15032101, 2)]`, `VITMaxNum=200`.
- `python3 server/env_ctl.py smoke --url http://127.0.0.1:8082`: **`ok: true`**.

---

## 4. Phase D Architecture Deliverable

- Created `MULTI_ACCOUNT_ARCHITECTURE.md` covering R7 planning across Account & Session (`PlayerId` decoupled from `ServerId=1`, QA isolation on `ServerId=2`/QA accounts, `mqkk` + recovery code reinstall restoration), Player Data separation, Shared World (`LuckBoss`, asynchronous `PVP` ladder snapshots, events, friends), Thread-safe Concurrency (`ResourceLedger` locking, per-account + world lock order, duplicate tx/kill protection), Portable Server readiness (macOS path/process audit, env-var/external `DATA_DIR` + `ASSETS_DIR`, `/health`, backup/restore, Linux Docker readiness, Admin API loopback isolation), and `OlinaHugh` zero-loss save migration.

---

## 5. STABLE Promotion Readiness & Exact Next Commands

- **Status:** STABLE (`:8080`, `checkpoint-vn-r5.2`, `OlinaHugh` Lv 16) was **not modified or restarted**.
- **Recommendation:** `checkpoint-vn-r6.2` fixes both R6.1 blockers with zero client changes and is **ready to stage and promote to STABLE upon explicit user confirmation**. (Keep a Pixel smoke run on `12010052` kill reward & idle `rpc_trace.log` as final on-device sign-off either on DEV before promote or immediately after promote.)
- **Manual promotion commands (only run after user approval):**
  ```bash
  python3 server/env_ctl.py backup --env stable --label pre_r62_promote
  python3 server/env_ctl.py release-stage --ref checkpoint-vn-r6.2
  python3 server/env_ctl.py promote --ref checkpoint-vn-r6.2 --confirm
  python3 server/env_ctl.py smoke --url http://127.0.0.1:8080
  ```
