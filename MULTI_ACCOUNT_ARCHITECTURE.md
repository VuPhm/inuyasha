# INUYASHA REVIVAL — R7 MULTIPLAYER PRIVATE SERVER & PORTABLE ARCHITECTURE

**Status:** Architecture & Survey Specification (Revised before R7.2 / R7.3 implementation)  
**Canonical Client Reference:** VN `com.cmn.inuyasha` (`v5.0.4.98`)  
**Scope:** True multi-player private game server supporting $N$ independent concurrent players sharing **Server 1**, portable across macOS / always-on PC / Linux VPS / Docker (with initial multi-player acceptance validated using 2 simultaneous independent clients on Server 1).

> **Key Clarification (R7.3 Correction):**  
> "2 players" is **only the initial acceptance target** — NOT a 2-account cap and **NOT** one person switching `Server 1 <-> Server 2` on a single device. The server must be a genuine multi-client private game server where independent players connect simultaneously to the **same Server 1 world**, each owning an independent account, session, player profile, roster, and save, while sharing rankings, shared bosses, events, social features, and (optionally) world chat.

---

## 1. Exact Identifier Model (Verified from VN Client Lua Source)

Never conflate these identifiers; each comes directly from VN `5.0.4.98` Lua code:

| Identifier | VN Client Field(s) | Scope & Lifecycle | Source Location |
|---|---|---|---|
| **`AccountId`** | `UserID` (and `LoginInfo.uid`) | Cross-world user account ID returned by `/sdk/login` or `/sdk/Register` (or third-party SDK login), persisted via `LocalData:saveLoginInfo`, passed to `/API/ServerList_Client.ashx` and `Player.Login` arg #6. | `Login/GameLoginScene.lua:493-506`, `Login/StartGameScene.lua:441,663` |
| **`ServerId`** | `ServerID` / `ServerId` | **Game World / Shard ID** (`1` = Shared World S1, optional `2` = isolated QA/Sandbox). Sent on `/client.aspx` (`data.ServerId`) and `ChatMng:login()`. Multiple independent accounts select `ServerId = 1` simultaneously and inhabit the **same world**. | `Login/StartGameScene.lua:651,716`, `Network/HttpClient.lua:172`, `Chat/ChatMng.lua:151,158` |
| **`PlayerId`** | `PlayerId` (`PlayerID`) | **Per-world player entity ID**: uniquely identifies `(AccountId, ServerId)` inside a world (`200010` for OlinaHugh on S1). Returned by `Player.Login` (`response.Value.PlayerId`), cached by client (`LocalData:savePlayerId`), and sent on every `/client.aspx` request (`data.PlayerId`) and `ChatMng:login()` (`Id`). | `Login/StartGameScene.lua:675,718`, `Network/HttpClient.lua:158,174`, `Chat/ChatMng.lua:142,154` |
| **`Character` / `Hero.Id`** | *(No `CharacterId` field exists)* `Hero.Id`, `HeroModelId`, `SlotId` | The VN protocol has **no separate `CharacterId`** on login/RPC envelopes. Calling `Player.NewPlayer({PlayerName, Gender})` initializes the player's avatar metadata (`PlayerName`, `Gender`, `HeadImageId`) and creates their Main Hero instance (`Hero.Id` UUID, `HeroModelId=12010001/12010004`) in `SlotId=1`. | `Login/RoleCreateScene.lua:344,383`, `server/emulator.py` |
| **`SessionId`** | Auth `sessionId` vs RPC `Session` | Two distinct tokens:<br>1. **Account auth token** (`sessionId` / `LoginInfo.token`) issued at SDK/account login.<br>2. **Per-login world session** (`response.Value.Session` from `Player.Login`), attached by client as `data.Session` on every `/client.aspx` call (`HttpClient.lua:159,173`). | `Login/StartGameScene.lua:444`, `Network/HttpClient.lua:159,173,271` |

---

## 2. Current Single-User Bottlenecks Observed in R6.2 / R7.1

| Layer | Observed Behavior in Current Code | Why It Blocks True Multiplayer |
|---|---|---|
| RPC Routing | `GameEmulatorState.get_profile()` (`server/emulator.py:5460`) switches solely on `ServerId` (`1 -> normal`, `2 -> debug`). | Two devices joining `ServerId=1` share `normal_profile.json` (`200010`) and overwrite each other's state. |
| Auth & ServerList | `/sdk/*` & `/API/ServerList_Client.ashx` (`emulator.py:5595,5685`) ignore incoming `UserID`/credentials and return hardcoded `"UserID": "100001"`. | Cannot distinguish real Player A vs Player B at login or issue per-user sessions. |
| Session Validation | `/client.aspx` never checks `Session` or matches `Session` -> `(AccountId, ServerId, PlayerId)`. `-46` / `-1101` / `-1103` error flows are unused. | Spoofed/stale/colliding requests cannot be rejected cleanly or forced to re-login (`-1101`). |
| APK SDK Stub | `poc/patch_vn_apk.py:31-58` hardcodes `MQLogin` to `uid="100001"`. | Every installed APK reports `UserID="100001"` unless using `mqkk` login UI (`GameLoginScene.lua`) or per-account auth. |
| Ledger Thread Safety | `ResourceLedger` (`server/economy_audit.py`) holds `_applied_keys` in an unlocked `set` and shares one `audit_ledger.jsonl` without an internal lock. | Concurrent grants across threads risk race conditions on `_applied_keys` or interleaved JSONL writes. |
| Shared Features | `boss_battle.bosses` and `pvp.rank` live inside each user's individual JSON (`normal_profile.json` / `debug_profile.json`). | Players on S1 only see scripted bots instead of real players' ranks, formations, or shared bosses. |

---

## 3. Target N-Player Private Server Architecture

### 3.1 Storage Layout (`N` Accounts, World-Scoped)

No fixed cap on number of players (scales naturally from 2 test players to $N$ personal/private-server players):

```
<data_dir>/
  accounts/
    accounts_index.json                     # username/email -> AccountId, salted PBKDF2 hash, role ("player"|"qa"), recovery_hash, status
    sessions.json                           # active/revocable world sessions (or in-memory + persistent salt)
  audit_ledger.jsonl                        # locked append-only economy ledger (world_id + player_id scoped keys)
  worlds/
    1/                                      # ServerId = 1 (Shared World for all real players)
      world_state.json                      # Arena ladder, shared LuckBosses, Friend graph, Guilds, Notices, Events
      players/
        200010/
          profile.json                      # OlinaHugh (migrated intact)
        200011/
          profile.json                      # Player 2
        200012/
          profile.json                      # Player 3 ... N
    2/                                      # ServerId = 2 (Isolated QA/Debug World, gated by QA role/env flag)
      world_state.json
      players/
        100001/
          profile.json                      # InuYasha QA/Debug
```

### 3.2 Authentication, Login & Session Lifecycle (`Status` Codes Match VN Client)

Follows `GameLoginScene.lua`, `StartGameScene.lua`, and `HttpClient.lua` natively:

1. **Account Auth (`/sdk/Register`, `/sdk/login`, `/sdk/Default`):**
   - Enable `GameLoginScene:createMqkkUI()` (already built into VN client) or lightweight account binding so any player can register/login from any device without rebuilding per-user APKs.
   - Generate unique `AccountId` (e.g. monotonic counter or UUID/string ID), store salted PBKDF2-HMAC-SHA256 password hash + optional single-use recovery code hash in `accounts_index.json`.
   - Issue opaque SDK `sessionId` (`secrets.token_urlsafe(24)`), return `{"State": 1, "Result": {"UserID": account_id, "sessionId": sdk_token}}`.
   - **Reinstall recovery:** Player installs the APK on a new phone and logs in with their `account` + password/recovery key -> receives the exact same `AccountId` (`UserID`), and `ServerList_Client.ashx` + `Player.Login(ServerId=1)` reconnects them to their existing `PlayerId` (`200010`, etc.).

2. **Server List (`/API/ServerList_Client.ashx`):**
   - Read `UserID` and `LoginInfo` from POST form body (`StartGameScene.lua:451`).
   - Return Server 1 (`S1`) to all accounts; include Server 2 (`QA Sandbox`) **only** for `role="qa"` accounts or when `INUYASHA_EXPOSE_QA_SERVER=1` is enabled.
   - `ServerUrl = f"http://{public_host}"`, `ChatServerUrl = f"{public_host_ip}:8081"` (if chat service is enabled).

3. **World Login (`Player.Login` -> `PlayerId` + `Session`):**
   - Inputs: `ServerId`, plus `[model, version, randNum, encryptedString, loginInfoJson, userID]` (`StartGameScene.lua:663`).
   - Verify account exists (`-1102` if banned/locked) and verify QA access if `ServerId == 2`.
   - Resolve `(AccountId, ServerId) -> PlayerId` from `worlds/<sid>/world_state.json["account_to_player"]` (creating a fresh `Lv 1`, `IsNewPlayer=1` player directory under `worlds/<sid>/players/<new_player_id>/profile.json` if first time on this world, allocating next unused `PlayerId` e.g. `max_id + 1`).
   - Mint a fresh per-login `world_session = secrets.token_urlsafe(32)` stored in `SessionStore`: `{session -> (account_id, server_id, player_id, issued_at, expires_at, generation)}`.
   - **Concurrent login safety (same account on two devices):** Logging into `(AccountId, ServerId)` rotates the active session for that `(AccountId, ServerId)` so the superseded session fails cleanly on its next RPC with **`Status = -1101`** (client displays *"Account logged in elsewhere / expired"* and returns to login screen per `HttpClient.lua:246-256`). Different accounts (`Player 1` and `Player 2`) hold completely separate sessions on `ServerId=1` simultaneously.

4. **Per-RPC Enforcement (`/client.aspx`):**
   - Look up `req["Session"]` -> verify valid & active:
     - Unknown / expired -> return `Status = -1101` (or `-46` if silent refresh applies per `HttpClient.lua:271`).
     - If `req["PlayerId"]` is non-empty and `!= session.player_id`, or `req["ServerId"] != session.server_id` -> **reject immediately (`Status = -1103`, no fallback to any default profile!)**.
   - Route directly to `WorldManager.get_world(session.server_id).get_player(session.player_id)`.

---

## 4. Per-Player State vs Shared World State on `ServerId = 1`

### 4.1 Strictly Private Per-Player Data (`worlds/<sid>/players/<player_id>/profile.json`)
- **Identity & Vitals:** `PlayerId`, `AccountId`, `PlayerName`, `Gender`, `Lv`, `EXP`, `VIT`, `VITMaxNum`, `VITNextRecoverTime`, `STA`, `STAMaxNum`, `STANextRecoverTime`, `FAP`, `StarId`, `HeadImageId`, `FashionModelId`, `IsNewPlayer`.
- **Currencies & VIP:** `Gold`, `Diamond`, `HeroCoin`, `HeroEXP`, `PVPCoin`, `BossCoin`, `Vip`, `VIPLv`, `VipEXP`, `ChargeNum`, `month_cards`, `charge_state`.
- **Inventory & Roster:** `heroes`, `slots`, `embattle`, `equips`, `treasures`, `treasure_debris`, `treasure_protect_end`, `goods`, `fashions`.
- **Progression & Personal Quests/Cooldowns:** `battle`, `chapters`, `nodes`, `elite`, `nightmare`, `explore`, `claimed_step_rewards`, `StepCountList`, `recruit_state`, `shop_bought`, `lv_plan`, `vip_welfare_drawn_date`, `daydayfund`, `startwork`, personal `boss_battle` charges (`attack_num`, `recover_time`, `buy_count`, `drawn_boxes`, `jifen`, `clear_counter`), personal `pvp` coins/shop limits/cooldowns.

### 4.2 Shared World Systems (`worlds/<sid>/world_state.json`, Protocol-Grounded)

Only recover shared mechanisms that have **verified RPC/socket definitions in the VN client**:

1. **Arena & Rankings (`PVP.*`, `Slot.SlotFormations`):**
   - `world_state["arena_ladder"]`: ordered rank slots `1..2000` seeded with deterministic NPC bots, where active real players occupy real ranks and swap ranks atomically under `world_lock` (`PVP.PVPFight`).
   - `world_state["player_snapshots"][player_id]`: combat snapshot (`PlayerName`, `Lv`, `FAP`, `HeadImageId`, `slots`, `heroes`, `embattle`) updated automatically after lineup/hero/equip changes and logins so Opponent Lookup (`Slot.SlotFormations`), `PVP.Refresh`, `PVP.PVPFight`, and `PVP.GetPVPTopRankList` reflect **actual players on Server 1**.
   - Offline defense: fights against another player's rank resolve asynchronously against their `player_snapshots` entry (`simulate_fight_info`), keeping zero risk of blocking their concurrent PVE session.

2. **Shared LuckBoss (`BossBattle.*`):**
   - Triggered bosses move into `world_state["bosses"]` with `OwnerPlayerId`, `OwnerName`, `CurHP`, `TotalHP`, `AwayTime`, `CanHelpTime`, `HelpOpen` (set when owner triggers `BossBattle.FriendHelp`), `DropResource`, and `Contributors: {player_id: damage}`.
   - `BossBattle.GetBossList` returns player's own bosses + world/friend bosses whose help flag is open (`CanHelpTime > 0`).
   - `BossBattle.JiFenRanking` ranks real players on `ServerId = 1` alongside NPC filler entries ordered by `JiFen`.

3. **Treasure Loot Targets (`TreasureLoot.*`):**
   - Candidate pool includes real Server 1 players holding the requested debris (respecting `treasure_protect_end`) plus fallback NPC targets when fewer than 3 live targets hold that fragment.

4. **Social / World Chat (Future / Optional in R7.3b via Original `ChatMng.lua` Protocol):**
   - `ChatMng.lua:140-260` defines a lightweight JSON-over-TCP socket protocol (`ChatServerUrl` e.g. `<host>:8081`):
     - `CMD_TYPE_LOGIN = 1` (verifies `Sign = md5(Id + "-" + Name + "-7DE9DAA1-E87C-FF51-BCE3-15946DBE9462")` + `ServerId`),
     - `CMD_TYPE_SEND_MSG = 3` (`CHANNEL_TYPE_SYSTEM=0`, `WORLD=1`, `UNION=2`, `PRIVATE=3`, `AVATAR=4`), `30s` heartbeat.
   - HTTP gameplay works safely with or without `:8081` active (client disables chat cleanly when TCP is unreachable); adding a small Python async/threaded TCP relay on `:8081` scoped by `ServerId` later follows the exact client protocol without inventing custom endpoints.

5. **Friends / Guilds (`Friend.*`, `Guild.*`, `Notice.*`):**
   - Scoped strictly per `ServerId` in `world_state.json`; real players can add each other, join/form guilds, and see live world notices once implemented.

---

## 5. Concurrency, Thread Safety & Consistency

Under `ThreadingEmulatorServer`, $N$ players send HTTP RPCs simultaneously on separate worker threads:

1. **Global Lock Acquisition Order (Deadlock-Free):**
   1. `accounts_lock` (when mutating `accounts_index.json` or `SessionStore`)
   2. `player_lock(server_id, player_id)` (one `RLock` per player; if ever needing two, acquire in sorted `player_id` order — though async snapshot reads avoid dual player locks!)
   3. `world_lock(server_id)` (`RLock` guarding `world_state.json`)
   4. `ledger_lock` (internal `RLock` inside `ResourceLedger` protecting `_applied_keys` and JSONL writes)
2. **Isolation Guarantees:**
   - Single-player RPCs (`Battle.*`, `Equip.*`, `Hero.*`, `ShopGoods.*`, `Goods.*`) lock ONLY `player_lock` — Player A and Player B run in full parallel without waiting on each other or touching each other's files.
   - Shared-world mutations (e.g., killing a shared `LuckBoss` or swapping `Arena` ranks): `CurHP` decrement (`BossBattle.Fight`) and kill-reward eligibility (`boss_killed_by_this_call = old_hp > 0 and new_hp == 0`) execute **atomically inside `world_lock`**, guaranteeing only the true finisher receives the `DropResource` kill reward even under simultaneous requests.
3. **Atomic Persistence & Ledger:**
   - Every `profile.json`, `world_state.json`, and `accounts_index.json` writes via temp file + `os.replace()` while holding its owning lock.
   - Every `ResourceLedger` idempotency key includes `(server_id, player_id, action, tx_id)`.

---

## 6. Portable Server & Operations (macOS -> Always-On PC / Linux VPS / Docker)

- **macOS dependencies audited:** `server/env_ctl.py` uses `pgrep` and local ports `8080`/`8082`; `poc/patch_*.py` hardcodes `/Users/vup/Library/...` and default `--server 192.168.1.250:8080` (build-time APK script only). `server/emulator.py` itself uses pure Python stdlib and already supports `INUYASHA_ROOT_DIR`, `--data-dir`, `--trace-path`, and `INUYASHA_ADMIN_TOKEN`.
- **R7 target env configuration (zero hardcoded LAN IPs in backend):**
  - `INUYASHA_HOST`, `INUYASHA_PORT`, `INUYASHA_PUBLIC_URL` (for proxies/NAT in `ServerList_Client.ashx`)
  - `INUYASHA_DATA_DIR` (external writable volume `/data`)
  - `INUYASHA_ASSETS_DIR` (external read-only OBB/assets + `game_data.json` volume `/assets:ro`)
  - `INUYASHA_ENV`, `INUYASHA_ALLOW_QA`, `INUYASHA_ADMIN_TOKEN`
- **Security & Ops:**
  - `/health` exposes readiness metrics (`ok`, `env`, `schema_version`, `worlds`, `active_sessions`) without leaking tokens or secrets.
  - `/admin/*` stays restricted to loopback/SSH tunnel (`127.0.0.1` + `X-Admin-Token`) or disabled on public-facing interfaces; never exposed via public reverse proxy.
  - Backup/restore captures `accounts/`, `worlds/`, and `audit_ledger.jsonl` with SHA-256 `MANIFEST.json`.
  - Voice packs (Post-R7): remain cleanly decoupled under `<assets_dir>/voice_packs/{vn,jp}/res/music/*.mp3` with zero backend/save impact.

---

## 7. Preserving Existing Saves (`OlinaHugh` Migration)

1. **Snapshot & Backup First:** Run `python3 server/env_ctl.py backup --tag pre_r7_multi_migration` before migrating any data directory.
2. **Idempotent Migration (`migrate_r6_to_r7(data_dir)`):**
   - Convert legacy `normal_profile.json` (`OlinaHugh`, `PlayerId="200010"`, Lv 16 STABLE / Lv 20 DEV) via R6.2/R7.1 `_normalize_loaded_state()` into `worlds/1/players/200010/profile.json` (`AccountId="acct_200010"` registered in `accounts_index.json`, mapped to `(AccountId, ServerId=1) -> PlayerId="200010"` in `worlds/1/world_state.json`, preserving all heroes, equips, treasures, `15032101`, chapter stars, VIP, Diamond, Gold, and Arena rank).
   - Isolate legacy `debug_profile.json` (`InuYasha`, `PlayerId="100001"`) strictly into `worlds/2/players/100001/profile.json` under QA account `acct_100001` (`role="qa"`). Never import QA data into World 1.
   - Keep `audit_ledger.jsonl` append-only and archive raw legacy files under `<data_dir>/legacy_r6_archive/`.

---

## 8. Mandatory Acceptance Gate for R7.3 (Before Considering Multiplayer Complete)

> **Switching `Server 1 <-> Server 2` on a single device is NOT accepted as multiplayer verification.**

R7.3 must pass both automated concurrent tests and live two-device/two-client verification on **Server 1**:
1. **Two Concurrent Independent Clients (`Session A` for Player 1, `Session B` for Player 2) on `ServerId = 1`:**
   - Simultaneous login with distinct `UserID` -> distinct `PlayerId` + distinct `Session`, both on `ServerId = 1`.
   - Parallel PVE stage clears, shop purchases, hero upgrades, and daemon restart -> zero cross-write, zero lost saves, intact `OlinaHugh` save.
2. **Cross-Session & Idempotency Guards:**
   - Replaying Player A's request with Player B's `Session` or mismatched `PlayerId` is rejected (`-1103` / `-1101`).
   - Same account logging in from a second client invalidates old session (`-1101`) cleanly.
   - Concurrent finishing hits from Player A & Player B on the same shared `LuckBoss` grant kill `DropResource` to **at most one** finisher.
3. **Shared World Verification:**
   - Player A and Player B appear on the same Server 1 Arena ladder (`PVP.GetPVPTopRankList` / `Slot.SlotFormations`), can challenge each other's asynchronous defense team, and see each other in `BossBattle.JiFenRanking` / shared `FriendHelp` bosses.

---

## 9. Phased Execution Plan (Remaining R7 Sequence)

1. **R7.2 (Next Immediate Coding Slice):** Restore remaining VN Tutorial steps & `GetStepCountReward` mappings (`2071`, `2181`, `274`, etc.) using original VN configs (`GuideMng.lua`, `GuideEventModel.lua`, `HomeScene.lua`) and verify a fresh Lv 1 onboarding flow end-to-end.
2. **R7.3 (Private Server Multiplayer Foundation):**
   - `R7.3a`: `ResourceLedger` locking, multi-player world/player directory storage, automatic `OlinaHugh` migration.
   - `R7.3b`: `accounts_index.json`, `Session` issuance/validation (`-1101`/`-1103`), dynamic `ServerList_Client.ashx` & `/sdk/*` auth (`mqkk` / client login), multi-client Server 1 concurrent test suite.
   - `R7.3c`: Shared World (`Arena` real player ladder/snapshots, shared `LuckBoss` help & JiFen ranking, optional `:8081` `ChatMng` relay) + 2-client concurrent live acceptance.
3. **Post-R7:** Vietnamese character voice pack experiments (`res/music/*.mp3` overlay) once R7 multiplayer is stable.
