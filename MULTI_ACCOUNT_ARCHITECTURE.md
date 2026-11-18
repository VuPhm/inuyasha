# INUYASHA REVIVAL — R7 MULTI-ACCOUNT & PORTABLE SERVER ARCHITECTURE

**Status:** Survey & Planning Document (R6.2 Deliverable — no runtime rewrite in R6.2)  
**Target Milestone:** Round R7 (~2 concurrent personal players on a single shared world, portable from macOS to Linux VPS / always-on PC / Docker)

---

## Executive Summary

In R6.2, `GameEmulatorState` in `server/emulator.py` routes RPCs solely by `ServerId` (`1 -> "normal"`, `2 -> "debug"`), `/API/ServerList_Client.ashx` and `/sdk/*` return hardcoded `"UserID": "100001"`, and client APK patching (`poc/patch_vn_apk.py`) pins `MQLogin` to `uid="100001"`. That forces two physical devices connecting to Server 1 to collide on `server/saves/normal_profile.json` (`OlinaHugh`, `PlayerId="200010"`).

For R7, the minimal, least-invasive architecture decouples **Account (`AccountId` / `PlayerId`)** from **World (`ServerId`)**:
- Keep **`ServerId = 1`** as the single shared game world where both personal players play together, while isolating **QA/DEBUG (`ServerId = 2` or explicit QA account)** completely.
- Store per-player saves under `<data_dir>/worlds/<world_id>/accounts/<player_id>/profile.json` plus a per-world shared state `<data_dir>/worlds/<world_id>/world_state.json`.
- Protect concurrent two-player requests inside `ThreadingEmulatorServer` with per-account `RLock`, a world lock, and a thread-safe `ResourceLedger` (currently `_applied_keys` in `server/economy_audit.py` has no lock).
- Preserve backward compatibility for `OlinaHugh` (`PlayerId="200010"`, Lv 16 STABLE / Lv 20 DEV) via an automatic one-time migration from legacy `normal_profile.json` + `debug_profile.json`.

---

## Current Architecture Bottlenecks (Observed in R6.2)

| Layer | File / Symbol | Current Limitation |
|---|---|---|
| Account routing | `server/emulator.py` (`GameEmulatorState.get_profile`, lines 5407–5421) | Maps `ServerId=1 -> profiles["normal"]` and `ServerId=2 -> profiles["debug"]`. Ignores `PlayerId`, `UserID`, and `Session` in `/client.aspx` requests. |
| Auth & ServerList | `server/emulator.py` (`/sdk/*` lines 5544–5548; `/API/ServerList_Client.ashx` lines 5634–5676) | Ignores incoming POST credentials; hardcodes `"UserID": "100001"`, `"sessionId": "local-revival-session-0001"`. Uses `ServerID=1` vs `ServerID=2` to pick profile. |
| Client SDK patch | `poc/patch_vn_apk.py` (lines 32–55) | Hooks `MQLogin` to fixed `uid="100001"` instead of `mqkk` email/password UI (`GameLoginScene.lua`) or per-device identity. |
| Client RPC headers | Client `HttpClient.lua` (lines 172–178) & `StartGameScene.lua` | Sends `ServerId`, `Session`, `PlayerId`, `MAC`, `IDFA` on every `/client.aspx` RPC, plus `UserID`/`LoginInfo`/`ServerId` on `Player.Login` (available for server-side resolution, currently unused). |
| Economy Ledger | `server/economy_audit.py` (`ResourceLedger`) | `_applied_keys: set[str]` and JSONL append have no internal lock; all profiles share one `audit_ledger.jsonl` under `SAVES_DIR`. |
| Runtime & Paths | `server/env_ctl.py` & `server/emulator.py` | `env_ctl.py` uses POSIX `pgrep`, binds fixed ports `8080`/`8082`, and runs source/release trees on host; `poc/patch_*.py` hardcode macOS `/Users/vup/Library/...` and default `--server 192.168.1.250:8080`. |

---

## 1. Account & Session

### Design Goals
- Each player gets a distinct `AccountId` / `PlayerId` (e.g., `"200010"` for OlinaHugh, `"200011"` for Player 2).
- `ServerId` identifies the **world** (`1 = Shared World S1`, optional `2 = QA/Sandbox`), **not** the user.
- Both players select **Server 1** and stay completely isolated.
- QA/DEBUG profile (`InuYasha`, `100001`) never shares world state, rankings, or saves with Server 1 players.
- Players can recover their account after reinstalling the APK or switching phones.

### Client Login & Reinstall Recovery Options (Comparison)

The APK already contains `GameLoginScene.lua` supporting both `MQLogin` and `mqkk` (`Channel="mqkk"`, calling `/sdk/login`, `/sdk/Register`, `/sdk/Default`) without modifying core gameplay scripts:

1. **Option A — Built-in `mqkk` Lightweight Account/Passcode (Recommended for R7):**
   - Switch client login channel configuration from hardcoded `uid="100001"` to `mqkk` (or minimal username + PIN/passcode login in `GameLoginScene.lua`).
   - `/sdk/Register` & `/sdk/login` look up `<data_dir>/accounts_index.json` (storing `account_id`, `username`, salted SHA-256/PBKDF2 password hash, `player_id`, `role`, `recovery_code`, `created_at`), issuing a random per-login opaque `session_token` (`secrets.token_urlsafe(24)`).
   - Server sets `"UserID": account_id` and `"sessionId": session_token` in `/sdk/login` and `/API/ServerList_Client.ashx`.
   - **Reinstall recovery:** Player simply logs in with their username/password (or single-use recovery code / admin-reset passcode) on any phone or reinstalled APK and immediately gets their exact `PlayerId` back.

2. **Option B — Pre-issued Per-Player Token + Account-Switch File / QR / Device Binding (Zero-APK-UI fallback):**
   - Generate two static player accounts (`p1`, `p2`) on the server with a bind token or lightweight web bind page (`POST /account/bind`), falling back to `MAC`/`IDFA` (`HttpClient.lua:172-178`) or per-device patched config (`player_token` in APK).
   - **Limitation:** Pure `MAC`/`IDFA` breaks if Android resets `ANDROID_ID`/randomizes MAC on OS upgrade or reinstall; device-bound APK builds require building 2 different APKs unless paired with a login code.

**Recommendation:** Use **Option A (`mqkk` username + password/PIN)** as the primary mechanism, backed by a manual recovery-code / Admin account-rebind fallback so reinstalling on a new phone works without rebuilding APKs.

### Session Isolation & Validation Rules
Every `/client.aspx` request carries `Session`, `PlayerId`, `ServerId`:
1. Look up `session = session_store.get(req.get("Session"))`.
2. Require `session` to be valid and unexpired; reject unknown/expired/forged sessions with an explicit auth error instead of silently defaulting to `normal`.
3. Cross-check `req.get("PlayerId")`: once a session has entered a world (`PlayerId` assigned on `Player.Login` / `Player.NewPlayer`), reject any mismatched `PlayerId` (`HTTP 403` or RPC status error) to guarantee zero cross-account contamination.
4. For `ServerId == 2` (`QA/DEBUG`) or `is_qa=True` accounts:
   - Restrict login to explicit QA accounts (e.g. `account_id="100001"` with QA role flag or non-production `INUYASHA_ALLOW_QA_PROFILE=1`), and route `ServerId=2` to `<data_dir>/worlds/qa_sandbox/` so QA actions (Lv 99 boosts, `/admin/prepare`, debug items) can never leak into `World 1`.
5. Bind `/sdk/*` `ServerList_Client.ashx` responses dynamically using the incoming `UserID`/`sessionId` so Client `StartGameScene` enters Server 1 with the logged-in user's identity rather than `"100001"`.

---

## 2. Player Data

### Per-Account Ownership Boundary

Move single-account state out of `normal_profile.json` into per-account directories under World `S1`:

```
<data_dir>/
  accounts_index.json                     # account credentials, player_id, roles, recovery hashes
  audit_ledger.jsonl                      # append-only ledger (or per-world ledger)
  worlds/
    s1/
      world_state.json                    # shared world: shared bosses, arena ladder, events, friends
      accounts/
        200010/
          profile.json                    # OlinaHugh complete save
        200011/
          profile.json                    # Player 2 complete save
    qa/
      world_state.json
      accounts/
        100001/
          profile.json                    # InuYasha QA/debug save
```

Each `accounts/<player_id>/profile.json` owns 100% independent state:
- **Player identity & stats:** `PlayerId`, `Session`, `PlayerName`, `Gender`, `Lv`, `EXP`, `VIT`, `VITMaxNum`, `VITNextRecoverTime`, `STA`, `STAMaxNum`, `STANextRecoverTime`, `FAP`, `StarId`, `HeadImageId`, `FashionModelId`, `LastLoginTime`, `IsNewPlayer`.
- **Currencies & VIP:** `Gold`, `Diamond`, `HeroCoin`, `HeroEXP`, `PVPCoin`, `BossCoin`, `Vip`, `VIPLv`, `VipEXP`, `ChargeNum`, `month_cards`, `charge_state`.
- **Roster & Equipment:** `heroes`, `slots`, `embattle`, `equips`, `treasures`, `treasure_debris`, `treasure_protect_end`, `fashions`.
- **Inventory & Progression:** `goods`, `battle`, `chapters`, `nodes`, `elite`, `nightmare`, `explore`.
- **Quests, Steps & Daily Activities:** `claimed_step_rewards`, `StepCountList`, `recruit_state`, `shop_bought`, `lv_plan`, `vip_welfare_drawn_date`, `daydayfund`, `startwork`, personal `boss_battle` charges (`attack_num`, `recover_time`, `buy_count`, `drawn_boxes`, `jifen`, `next_boss_count`, `clear_counter`).

### Schema Versioning & Backward Compatibility for `OlinaHugh`
- Add `"schema_version": 2` and `"account_id"` metadata inside `profile.json`, preserving every existing top-level key read by `ProfileStore._normalize_loaded_state()` (`player`, `heroes`, `slots`, `equips`, `goods`, `chapters`, `nodes`, `pvp`, `boss_battle`, etc.).
- Reuse `ProfileStore._normalize_loaded_state()` so `OlinaHugh`'s Lv 16 / Lv 20 VIP 3 save loads without dropping any hero, equip, treasure debris (including `15030101 -> 15032101`), stage stars, daily flags, or VIP progress.

---

## 3. Shared World

All non-real-time social/competitive features on **`ServerId = 1`** read and mutate `<data_dir>/worlds/s1/world_state.json`:

1. **Shared Bosses (`LuckBoss`):**
   - Personal boss attack charges (`attack_num`, `recover_time`, `buy_count`, personal `jifen`) stay inside `accounts/<player_id>/profile.json`.
   - Active spawned boss instances move to `world_state.json["bosses"]` with `OwnerPlayerId`, `OwnerName`, `CurHP`, `TotalHP`, `AwayTime`, `CanHelpTime`, `Helpers: [player_id, ...]`, `ShareState`, and damage log `DamageByPlayer: {player_id: hurt}`.
   - When Player A clicks `BossBattle.FriendHelp` (`CanHelpTime` / open help), `BossBattle.GetBossList` for Player B returns both Player B's own bosses and shared bosses from friends/world players.
   - `BossBattle.JiFenRanking` merges live scores from all active Server 1 accounts (`200010`, `200011`) ahead of or mixed with scaled NPC bots based on `JiFen`.

2. **Arena / Ranking (`PVP`):**
   - Move `rank_table` (`rank -> entity_id`) into `world_state.json["arena_ladder"]`, seeded with the deterministic NPC bots (`1..1500+`), with real players (`200010`, `200011`) occupying live rank slots and mirrored `snapshot` combat teams (`PlayerName`, `Lv`, `FAP`, `slots`, `heroes`, `HeadImageId`) refreshed whenever a player logs in or changes lineup.
   - `PVP.GetPVPTopRankList` and opponent matchmaking read live player snapshots from `world_state.json`, allowing Player 1 and Player 2 to see each other on the ladder and challenge each other's asynchronous defense snapshot (`simulate_fight_info`), swapping ranks atomically under `world_lock`.
   - `PVP.shop_bought_daily`, `shop_bought_total`, `PVPCoin`, and `history` remain per-account (plus a compact match notice appended for the defender).

3. **World Events & Announcements:**
   - Global event windows, double-point schedules (`LuckbossConfig`), welcome/maintenance notices (`Notice.GetNoticeList`), and server-wide milestone flags live in `world_state.json["events"]` so both players experience consistent server time/events.

4. **Friends & Support (Future R7+):**
   - Minimal mutual friend list (`world_state.json["friends"]` mapping `player_id -> set[friend_id]`) powers `FriendHelp` boss visibility, `TreasureLoot` opponent selection (filtering out protected players cleanly), and STA friend gifting without requiring live WebSocket/socket PvP or synchronous co-op.

*(Real-time socket PvP / synchronous co-op ChatServer `ChatServerUrl` on `:8081` stays out of scope for R7.)*

---

## 4. Concurrency & Consistency

Because `ThreadingEmulatorServer` inherits `socketserver.ThreadingMixIn`, simultaneous HTTP requests from Player 1 and Player 2 execute on separate OS threads concurrently:

### Locking Strategy (Deadlock-Free Strict Order)
1. **Acquire order:** Always lock in strict total order:
   1. `account_lock(player_id)` (per-account `threading.RLock`, sorted by `player_id` if ever locking two accounts)
   2. `world_lock(world_id)` (`threading.RLock` for `world_state.json` mutations)
   3. `ledger_lock` (internal `threading.RLock` inside `ResourceLedger`)
2. **Scoped RPC execution:**
   - **Account-only RPCs** (`Battle.*`, `Equip.*`, `Hero.*`, `Shop.*`, `Goods.*`, `Daydayfund.*`): acquire ONLY `account_lock(player_id)`. Player 1 and Player 2 fight stages, upgrade heroes, and buy items completely in parallel without blocking each other.
   - **Shared-world RPCs** (`BossBattle.Fight` on a shared boss, `BossBattle.FriendHelp`, `BossBattle.GetBossList`, `PVP.Fight`, `PVP.GetPVPTopRankList`): acquire `account_lock(caller_id)` then `world_lock` (never lock two `ProfileStore` files simultaneously unless applying a defensive rank swap/inbox event via `world_state.json`).

### Transaction Idempotency & Data Consistency
- **Thread-safe `ResourceLedger` (`server/economy_audit.py`):**
  - Guard `_applied_keys` check + append + JSONL file write inside a `threading.RLock` (`ResourceLedger._lock`), because currently `_applied_keys` is an unsynchronized Python `set` and JSONL writes from two threads could interleave.
  - Enforce account-scoped idempotency keys everywhere: `f"{world_id}:{player_id}:{action}:{tx_id}"`.
- **Client duplicate-request protection:**
  - Support optional client retry keys (or short-TTL deduplication per `(player_id, ModuleName, MethodName, data_hash)` / Boss kill single-winner guard):
  - For shared bosses: perform `if boss["CurHP"] <= 0: return boss_already_defeated` **inside `world_lock`** so two players hitting the last HP at the exact same millisecond cannot both receive kill rewards or double-grant `DropResource`.
- **Atomic Persistence:**
  - Keep existing `tempfile` + `os.replace()` atomic JSON writes per `accounts/<player_id>/profile.json` and `world_state.json` inside their respective locks so a crash or concurrent save by Player 1 can never truncate or overwrite Player 2's file.

---

## 5. Portable Server & Packaging Plan

### macOS / Absolute-Path Dependencies Found in Current Codebase

| Item | Location | Finding | R7 Action |
|---|---|---|---|
| Host process management | `server/env_ctl.py` (line 110, 8080/8082) | Uses POSIX `pgrep -f` and hardcodes ports `8080`/`8082` + local paths. | Keep `env_ctl.py` for local workstation dev only; do NOT rely on `pgrep` inside Docker/systemd. |
| Hardcoded LAN IP & Mac SDK paths | `poc/patch_vn_apk.py`, `poc/patch_*.py` | Hardcodes `/Users/vup/Library/Android/sdk/build-tools/...` and default `--server 192.168.1.250:8080`. | Build-time APK helper only (not imported by `emulator.py`); keep isolated from server runtime. |
| Backend dynamic Host handling | `server/emulator.py` (`ServerList_Client.ashx`, lines 5636–5653) | Dynamically reads HTTP `Host` header (`ServerUrl = f"http://{host}"`). | **Good baseline**, add configurable `--public-url` / `INUYASHA_PUBLIC_BASE_URL` for reverse proxies (Nginx/Caddy/TLS/NAT) where internal `Host` header may differ from external LAN/VPS address. |
| Asset/game_data discovery | `server/emulator.py` (`INUYASHA_ROOT_DIR`, `--data-dir`, lines 173–195) | Already checks `Path.exists()` gracefully for APK/OBB/assets and allows overriding `--data-dir` and `INUYASHA_ADMIN_TOKEN`. | Formalize `INUYASHA_ASSETS_DIR` and `INUYASHA_GAME_DATA_PATH` so `game_data.json` + extracted OBB assets mount cleanly outside code release dirs. |

### Target R7 Packaging & Operations Layout

1. **Configuration via Env Vars / Config File (Zero Hardcoded IPs):**
   - `INUYASHA_HOST` (default `0.0.0.0`), `INUYASHA_PORT` (default `8080`)
   - `INUYASHA_DATA_DIR` (external writable volume for `worlds/`, `accounts_index.json`, `audit_ledger.jsonl`, backups)
   - `INUYASHA_ASSETS_DIR` (read-only OBB/APK asset bundle directory or pre-extracted cache + `game_data.json`)
   - `INUYASHA_PUBLIC_URL` (optional explicit base URL returned in `ServerList_Client.ashx`, falling back to `Host` header when unset)
   - `INUYASHA_ENV` (`prod` | `dev`), `INUYASHA_ALLOW_QA` (`0` on prod by default), `INUYASHA_ENABLE_ADMIN` (`0` or loopback/SSH-tunnel only)
   - `INUYASHA_ADMIN_TOKEN` (required if Admin API enabled; never committed)

2. **Separating Code Release from Runtime Data & Assets:**
   - Code directory (`/app/server`) is immutable / read-only inside container or release tarball.
   - All mutable state (`DATA_DIR` and `TRACE_PATH`) lives outside the code directory on a persistent host directory or Docker named volume (`/data`).
   - Game data + client asset bundles (`ASSETS_DIR`, ~extracted OBB/APK files) mount separately as `/assets:ro` so container image rebuilds remain fast and lightweight.

3. **Health Check, Backup/Restore & Admin API Hardening:**
   - **Health Check:** Extend `/health` with lightweight JSON status (`ok`, `env`, `schema_version`, `world_count`, `active_accounts_count`, `uptime_sec`, `disk_writable` probe without exposing sensitive player tokens or internal filesystem secrets) for Docker `HEALTHCHECK` / systemd watchdog.
   - **Backup / Restore:** Extend `server/env_ctl.py` (or a standalone `server/backup_ctl.py` usable inside Docker) to pause/snapshot `DATA_DIR` (all `accounts/*/profile.json`, `world_state.json`, `accounts_index.json`, `audit_ledger.jsonl`) + `manifest.json` SHA-256 checksums, plus pre-restore verification and daily rotation.
   - **Admin API Network Isolation:** Current `_require_local_admin()` checks `client_ip in ("127.0.0.1", "::1", "::ffff:127.0.0.1")` + `X-Admin-Token`. On Docker/VPS, **do not expose `/admin/*` via public reverse proxy or `0.0.0.0` port mapping**:
     - Bind Admin API either to an isolated loopback port (`127.0.0.1:8090`, only reachable via SSH port-forward `ssh -L 8090:127.0.0.1:8090 vps`) or disable `/admin/*` cleanly in container config unless explicitly bound to `127.0.0.1`.
     - Strip `/admin/*` at Nginx/Caddy (`location ^~ /admin/ { deny all; }`) if placed behind a reverse proxy.

4. **Future Linux Docker Readiness:**
   - Base image: `python:3.11-slim` with non-root user (`uid=1000`), zero native macOS binaries (`sqlite3` if added later is stdlib Python; `requirements.txt` currently uses Python stdlib only!).
   - Mounts: `-v /srv/inuyasha/data:/data -v /srv/inuyasha/assets:/assets:ro`.
   - Restart policy: `--restart unless-stopped`, graceful `SIGTERM` handler finishing in-flight requests and flushing atomic saves before exit.

---

## Save Migration Proposal (`OlinaHugh` -> R7 Multi-Account)

Transitioning cleanly without losing any STABLE (`Lv 16`) or DEV (`Lv 20 VIP 3`) progress:

1. **Snapshot First:** Run `python3 server/env_ctl.py backup --env stable --label pre_r7_migration` and copy `dev_saves/` with SHA-256 verification before touching any file.
2. **Automatic On-Boot Idempotent Migration (`migrate_r6_to_r7(data_dir)`):**
   - Detect legacy layout (`normal_profile.json` or `debug_profile.json` present without `worlds/s1/accounts_index_migrated` marker).
   - **Migrate `OlinaHugh` (`normal_profile.json`):**
     - Read `normal_profile.json`, run R6.2 `_normalize_loaded_state()` (ensures `15030101 -> 15032101`, `VITMaxNum >= 200`, `STAMaxNum >= 20`, valid `DropResource`), extract `PlayerId = "200010"` and `PlayerName = "OlinaHugh"`.
     - Register Player 1 account entry in `accounts_index.json` (`account_id="200010"`, `username="olinahugh"`, `player_id="200010"`, `world_id="s1"`, initial recovery/login secret configurable by operator).
     - Write validated save atomically to `<data_dir>/worlds/s1/accounts/200010/profile.json` (`schema_version=2`).
     - Seed initial World `s1` state (`<data_dir>/worlds/s1/world_state.json`): register OlinaHugh's Arena rank (`pvp.rank`) into `arena_ladder` and promote any still-active `boss_battle.bosses` cleanly to `world_state["bosses"]` with `OwnerPlayerId="200010"`.
   - **Isolate QA Profile (`debug_profile.json`):**
     - Register QA account (`account_id="100001"`, `role="qa"`) in `accounts_index.json` pointing to `worlds/qa/accounts/100001/profile.json`.
     - Move `debug_profile.json` (`InuYasha`, Lv 10 VIP 5) to `<data_dir>/worlds/qa/accounts/100001/profile.json`. Never import QA characters or items into World `s1`.
   - **Preserve Audit History:**
     - Keep `audit_ledger.jsonl` append-only at `<data_dir>/audit_ledger.jsonl` (entries already carry `account_id="200010"` or `"100001"` and `profile="normal"`/`"debug"`). Seed `ResourceLedger._applied_keys` on boot from existing JSONL entries.
   - **Archive Legacy Originals (Never Delete Immediately):**
     - Copy original `normal_profile.json` and `debug_profile.json` into `<data_dir>/legacy_r6_archive/` (or keep read-only `.bak`) until R7 acceptance completes on devices.
3. **Create Player 2 Account:**
   - Player 2 registers cleanly via `/sdk/Register` (or CLI admin seed helper) receiving `PlayerId="200011"` on `ServerId=1`, starting at Lv 1 tutorial onboarding while sharing World `s1` (`arena_ladder`, `world_state.bosses`, events) with `OlinaHugh`.

---

## Recommended R7 Implementation Sequence

1. **Step 1 (Concurrency Foundation):** Add internal `RLock` to `ResourceLedger`, per-account locks + atomic save helper, and `/health` readiness details.
2. **Step 2 (Directory Layout & Migration Tool):** Implement `worlds/s1/accounts/<player_id>/profile.json` loader + automatic tested migration from R6.2 `OlinaHugh` saves + rollback tests.
3. **Step 3 (Account & Session Routing):** Implement `accounts_index.json`, `Session` token validation, `ServerList_Client.ashx` user resolution, QA gating (`ServerId=2`), and recovery flow.
4. **Step 4 (Shared World):** Extract shared `arena_ladder`, shared `LuckBoss` pool (`FriendHelp` + kill lock), and `JiFenRanking` into `world_state.json`.
5. **Step 5 (Portable Packaging & Docker):** Env-var configuration (`INUYASHA_DATA_DIR`, `INUYASHA_ASSETS_DIR`, `INUYASHA_PUBLIC_URL`), Admin API binding separation, backup CLI, and `Dockerfile` + Linux CI/test verification.
