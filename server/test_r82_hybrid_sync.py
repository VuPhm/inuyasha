#!/usr/bin/env python3
"""End-to-end unit tests for Hybrid Local-First Cloud Sync (R8.2)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import uuid

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from emulator import GameEmulatorState, ThreadingEmulatorServer  # noqa: E402
from hybrid_sync import DEFAULT_SYNC_POLICY, HybridSyncManager  # noqa: E402


class _MockCloudflareSyncHub:
    """In-memory faithful mirror of deploy/cloudflare_sync/src/worker.js for offline Python tests."""

    def __init__(self, invite_code: str = "INU-TEST") -> None:
        self.invite_code = invite_code
        self.accounts: dict[str, dict] = {}
        self.by_uname: dict[str, str] = {}
        self.by_pid: dict[str, str] = {}
        self.tokens: dict[str, tuple[str, str]] = {}  # token -> (account_id, device_id)
        self.saves: dict[str, dict] = {}
        self.inbox: list[dict] = []
        self.next_inbox_id = 1
        self.sync_calls = 0

    def opener(self, method: str, url: str, headers: dict, data_bytes: bytes | None, _timeout: float):
        assert headers.get("User-Agent") == "InuYashaHybridSync/1.0"
        path = "/" + url.split("://", 1)[1].split("/", 1)[1]
        body = json.loads(data_bytes.decode("utf-8")) if data_bytes else {}
        auth_hdr = headers.get("Authorization", "")
        token = auth_hdr[7:].strip() if auth_hdr.startswith("Bearer ") else ""
        now = int(time.time())

        if method == "GET" and path in ("/health", "/auth/info"):
            return 200, {
                "ok": True,
                "mode": "hybrid_sync_hub",
                "invite_required": bool(self.invite_code),
                "guilds_synced": False,
                "account_count": len(self.accounts),
                "sync_policy": dict(DEFAULT_SYNC_POLICY),
                "server_time": now,
            }

        if method == "POST" and path == "/auth/register":
            if self.invite_code and body.get("invite_code") != self.invite_code:
                return 403, {"ok": False, "error": "Mã mời không đúng"}
            uname = str(body.get("username", "")).strip()
            ulow = uname.lower()
            if ulow in self.by_uname:
                return 409, {"ok": False, "error": "Tên tài khoản đã tồn tại"}
            aid = f"acct_{uuid.uuid4().hex[:12]}"
            pid = str(uuid.uuid4())
            tok = secrets.token_hex(24)
            self.accounts[aid] = {"account_id": aid, "username": uname, "password": body.get("password"), "player_id": pid}
            self.by_uname[ulow] = aid
            self.by_pid[pid] = aid
            self.tokens[tok] = (aid, str(body.get("device_id", "dev")))
            self.saves[aid] = {
                "account_id": aid,
                "player_id": pid,
                "sync_rev": 0,
                "device_id": str(body.get("device_id", "dev")),
                "save_hash": "",
                "save_gzip_b64": "",
                "snapshot": {},
                "name": uname,
                "lv": 1,
                "fap": 0,
                "arena_score": 1000,
                "updated_at": now,
            }
            return 201, {
                "ok": True,
                "account_id": aid,
                "player_id": pid,
                "username": uname,
                "token": tok,
                "sync_rev": 0,
                "has_cloud_save": False,
                "sync_policy": dict(DEFAULT_SYNC_POLICY),
            }

        if method == "POST" and path == "/auth/login":
            ulow = str(body.get("username", "")).strip().lower()
            aid = self.by_uname.get(ulow)
            if not aid or self.accounts[aid]["password"] != body.get("password"):
                return 401, {"ok": False, "error": "Sai tài khoản hoặc mật khẩu"}
            tok = secrets.token_hex(24)
            self.tokens[tok] = (aid, str(body.get("device_id", "dev")))
            sv = self.saves[aid]
            return 200, {
                "ok": True,
                "account_id": aid,
                "player_id": self.accounts[aid]["player_id"],
                "username": self.accounts[aid]["username"],
                "token": tok,
                "sync_rev": sv["sync_rev"],
                "has_cloud_save": sv["sync_rev"] > 0 and bool(sv["save_hash"]),
                "cloud_summary": {"lv": sv["lv"], "fap": sv["fap"], "updated_at": sv["updated_at"]},
                "sync_policy": dict(DEFAULT_SYNC_POLICY),
            }

        if token not in self.tokens:
            return 401, {"ok": False, "error": "Invalid token"}
        aid, _ = self.tokens[token]
        acct = self.accounts[aid]
        my_pid = acct["player_id"]

        if method == "GET" and path == "/sync/pull_save":
            sv = self.saves[aid]
            if sv["sync_rev"] == 0 or not sv["save_gzip_b64"]:
                return 404, {"ok": False, "error": "Chưa có bản lưu trên Cloud"}
            return 200, {
                "ok": True,
                "account_id": aid,
                "player_id": my_pid,
                "sync_rev": sv["sync_rev"],
                "device_id": sv["device_id"],
                "save_hash": sv["save_hash"],
                "save_gzip_b64": sv["save_gzip_b64"],
                "summary": {"name": sv["name"], "lv": sv["lv"], "fap": sv["fap"], "arena_score": sv["arena_score"]},
                "updated_at": sv["updated_at"],
            }

        if method == "POST" and path == "/sync":
            self.sync_calls += 1
            sv = self.saves[aid]
            base_rev = int(body.get("base_rev", 0))
            force_push = bool(body.get("force_push", False))
            save_hash = str(body.get("save_hash", ""))
            save_gz = str(body.get("save_gzip_b64", ""))
            save_changed = bool(save_gz and save_hash) and save_hash != sv["save_hash"]

            if save_changed and not force_push and sv["sync_rev"] > 0 and base_rev < sv["sync_rev"]:
                return 409, {
                    "ok": False,
                    "error": "conflict",
                    "message": "Conflict detected",
                    "server_summary": {
                        "sync_rev": sv["sync_rev"],
                        "device_id": sv["device_id"],
                        "save_hash": sv["save_hash"],
                        "name": sv["name"],
                        "lv": sv["lv"],
                        "fap": sv["fap"],
                        "arena_score": sv["arena_score"],
                        "updated_at": sv["updated_at"],
                    },
                }

            if save_changed:
                snap = body.get("snapshot") or {}
                sv["sync_rev"] += 1
                sv["device_id"] = str(body.get("device_id", ""))
                sv["save_hash"] = save_hash
                sv["save_gzip_b64"] = save_gz
                sv["snapshot"] = snap
                sv["name"] = str(snap.get("name") or acct["username"])
                sv["lv"] = int(snap.get("lv") or 1)
                sv["fap"] = int(snap.get("fap") or 0)
                sv["arena_score"] = int(snap.get("arena_score") or 1000)
                sv["updated_at"] = now

            for ev in body.get("outgoing_events") or []:
                to_pid = str(ev.get("to_player_id") or "")
                if to_pid in self.by_pid and to_pid != my_pid:
                    self.inbox.append(
                        {
                            "id": self.next_inbox_id,
                            "to_player_id": to_pid,
                            "from_player_id": my_pid,
                            "event_type": ev["event_type"],
                            "payload": ev.get("payload") or {},
                            "created_at": now,
                            "consumed": False,
                        }
                    )
                    self.next_inbox_id += 1

            ack_ids = set(body.get("ack_inbox_ids") or [])
            for item in self.inbox:
                if item["to_player_id"] == my_pid and item["id"] in ack_ids:
                    item["consumed"] = True

            since_ts = int(body.get("peers_since_ts", 0))
            updated_peers = []
            all_peer_ids = []
            for other_aid, osv in self.saves.items():
                if other_aid == aid or osv["sync_rev"] == 0:
                    continue
                all_peer_ids.append(osv["player_id"])
                if osv["updated_at"] > since_ts:
                    updated_peers.append(
                        {
                            "player_id": osv["player_id"],
                            "name": osv["name"],
                            "lv": osv["lv"],
                            "fap": osv["fap"],
                            "arena_score": osv["arena_score"],
                            "updated_at": osv["updated_at"],
                            "snapshot": osv["snapshot"],
                        }
                    )

            inbox_events = [
                {
                    "id": item["id"],
                    "from_player_id": item["from_player_id"],
                    "event_type": item["event_type"],
                    "payload": item["payload"],
                    "created_at": item["created_at"],
                }
                for item in self.inbox
                if item["to_player_id"] == my_pid and not item["consumed"]
            ]

            return 200, {
                "ok": True,
                "pushed": save_changed,
                "sync_rev": sv["sync_rev"],
                "server_time": now,
                "updated_peers": updated_peers,
                "all_peer_ids": all_peer_ids,
                "inbox_events": inbox_events,
            }

        return 404, {"ok": False, "error": "Not found"}


def _prepare_player(emu: GameEmulatorState, name: str, lv: int, fap_boost_gold: int = 0) -> None:
    store = emu.s1_accounts["acct_1"]
    store.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": [name, 1]})
    p = store.state["player"]
    p["Lv"] = lv
    p["STA"] = 40
    p["Gold"] = int(p.get("Gold", 0)) + fap_boost_gold
    if store.state.get("heroes"):
        store.state["heroes"][0]["Lv"] = lv
    if store.state.get("slots"):
        store.state["slots"][0]["Lv"] = lv
    store._recalc_all_slots_and_fap()
    store.save()


class HybridSyncE2ETests(unittest.TestCase):
    def _make_device(self, tmpdir: Path, name: str, hub: _MockCloudflareSyncHub) -> GameEmulatorState:
        d = tmpdir / name
        d.mkdir(parents=True, exist_ok=True)
        emu = GameEmulatorState(persist=True, data_dir=d)
        emu.hybrid_sync = HybridSyncManager(
            d,
            emu,
            persist=True,
            default_url="https://mock.sync.workers.dev",
            http_opener=hub.opener,
        )
        return emu

    def test_01_two_offline_devices_sync_leaderboard_friends_and_pvp(self) -> None:
        hub = _MockCloudflareSyncHub(invite_code="INU-999")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            alice = self._make_device(root, "device_alice", hub)
            bob = self._make_device(root, "device_bob", hub)

            _prepare_player(alice, "InuAlice", lv=48)
            _prepare_player(bob, "SesshoBob", lv=42)

            # Wrong invite rejected
            bad = alice.hybrid_sync.register("alice", "pw123", invite_code="BAD")
            self.assertFalse(bad["ok"])

            # Register both with valid invite code
            r_a = alice.hybrid_sync.register("alice", "pw123", invite_code="INU-999")
            r_b = bob.hybrid_sync.register("bob", "pw123", invite_code="INU-999")
            self.assertTrue(r_a["ok"])
            self.assertTrue(r_b["ok"])

            alice_pid = alice.s1_accounts["acct_1"].state["player"]["PlayerId"]
            bob_pid = bob.s1_accounts["acct_1"].state["player"]["PlayerId"]
            self.assertEqual(alice_pid, r_a["player_id"])
            self.assertEqual(bob_pid, r_b["player_id"])
            self.assertNotEqual(alice_pid, bob_pid)

            # Sync Alice so Alice pulls Bob's snapshot too
            sa = alice.hybrid_sync.sync_now(ignore_cooldown=True)
            self.assertTrue(sa["ok"])
            self.assertEqual(sa["peer_count"], 1)

            # 1. LeaderBoard shows Bob on Alice's offline device!
            lb = alice.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "LeaderBoard", "MethodName": "RankList", "Data": [2]}
            )
            names = [e["Name"] for e in lb["Value"]["RankList"]]
            self.assertIn("InuAlice", names)
            self.assertIn("SesshoBob", names)

            # 2. Formation inspection works offline for remote peer Bob!
            form_resp = alice.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "Slot", "MethodName": "SlotFormations", "Data": [bob_pid]}
            )
            self.assertEqual(form_resp["Status"], 0)
            self.assertIn("SlotInfos", form_resp["Value"])
            self.assertIn("SlotFormationInfo", form_resp["Value"])
            self.assertGreaterEqual(len(form_resp["Value"]["SlotInfos"]), 1)

            # 3. Friends flow across sync: Bob applies -> Alice accepts -> Alice sends STA & msg -> Bob receives!
            apply_res = bob.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "FriendMessage", "MethodName": "FriendApply", "Data": [alice_pid, "Kết bạn nha Alice!"]}
            )
            self.assertEqual(apply_res["Status"], 0)
            bob.hybrid_sync.sync_now(ignore_cooldown=True)
            alice.hybrid_sync.sync_now(ignore_cooldown=True)

            msgs = alice.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "FriendMessage", "MethodName": "GetFriendMessageByPage", "Data": [0, 10]}
            )
            self.assertTrue(any(m.get("SendPlayerId") == bob_pid and m.get("Type") == 1 for m in msgs["Value"]))

            acc_res = alice.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "Friend", "MethodName": "FriendApplyResponse", "Data": [bob_pid, True]}
            )
            self.assertEqual(acc_res["Status"], 0)

            sta_res = alice.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "FriendMessage", "MethodName": "SendFriendSTA", "Data": [bob_pid]}
            )
            self.assertEqual(sta_res["Status"], 0)

            msg_res = alice.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "FriendMessage", "MethodName": "SendFriendMessage", "Data": [bob_pid, "Chào Bob!"]}
            )
            self.assertEqual(msg_res["Status"], 0)

            alice.hybrid_sync.sync_now(ignore_cooldown=True)
            bob.hybrid_sync.sync_now(ignore_cooldown=True)

            # Verify Bob now has Alice as friend, STA gift in inbox, and message from Alice
            bob_social = bob.s1_accounts["acct_1"].state["social"]
            self.assertIn(alice_pid, bob_social["friends"])
            self.assertTrue(any(x.get("PlayerId") == alice_pid for x in bob_social["sta_inbox"]))
            self.assertTrue(any(m.get("Content") == "Chào Bob!" for m in bob_social["friend_messages"]))

            # 4. Offline Arena PvP fight against Bob's real synced team!
            bob_rank = bob.hybrid_sync.status()  # ensure no error
            self.assertTrue(bob_rank["ok"])
            bob_proxy = alice.s1_accounts["acct_1"]._find_peer_by_player_id(bob_pid)
            self.assertIsNotNone(bob_proxy)
            target_rank = int(bob_proxy.state["pvp"]["rank"])
            # Make sure Alice strongly out-stats Bob for deterministic win
            alice.s1_accounts["acct_1"].state["slots"][0]["Lv"] = 70
            alice.s1_accounts["acct_1"]._recalc_all_slots_and_fap()
            pvp_res = alice.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "PVP", "MethodName": "PVPFight", "Data": [bob_pid, target_rank]}
            )
            self.assertEqual(pvp_res["Status"], 0)
            self.assertEqual(pvp_res["Value"]["IsWinFight"], 1)
            self.assertGreater(int(alice.s1_accounts["acct_1"].state["pvp"].get("arena_score", 1000)), 1000)

            # Sync pvp_challenge_log to Bob's battle email inbox
            alice.hybrid_sync.sync_now(ignore_cooldown=True)
            bob.hybrid_sync.sync_now(ignore_cooldown=True)
            bob_emails = bob.s1_accounts["acct_1"].state["social"].get("emails", [])
            self.assertTrue(any("Đấu Trường Cloud" in str(e.get("Subject", "")) for e in bob_emails))

    def test_02_multidevice_conflict_and_guild_preservation_on_pull(self) -> None:
        hub = _MockCloudflareSyncHub(invite_code="INU-999")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            phone1 = self._make_device(root, "phone1", hub)
            phone2 = self._make_device(root, "phone2", hub)

            _prepare_player(phone1, "DualHero", lv=25)
            self.assertTrue(phone1.hybrid_sync.register("dual", "pw123", invite_code="INU-999")["ok"])

            # Phone2 already has a local character AND a local Guild
            _prepare_player(phone2, "LocalBeforePull", lv=12)
            phone2.s1_accounts["acct_1"].state["player"]["GuildId"] = "local-guild-uuid-123"
            phone2.s1_accounts["acct_1"].state["player"]["GuildName"] = "Bang Cục Bộ"
            phone2.s1_accounts["acct_1"].save()

            login2 = phone2.hybrid_sync.login("dual", "pw123")
            self.assertTrue(login2["ok"])
            self.assertTrue(login2["needs_choice"])

            # Phone2 tries normal sync -> 409 Conflict!
            c_res = phone2.hybrid_sync.sync_now(ignore_cooldown=True)
            self.assertFalse(c_res["ok"])
            self.assertTrue(c_res.get("conflict"))
            self.assertEqual(c_res["server_summary"]["lv"], 25)

            # Pull Cloud Save -> restores Lv.25 DualHero, creates .bak, AND preserves local Guild!
            pull_res = phone2.hybrid_sync.pull_cloud_save()
            self.assertTrue(pull_res["ok"])
            p2 = phone2.s1_accounts["acct_1"].state["player"]
            self.assertEqual(p2["Lv"], 25)
            self.assertEqual(p2["PlayerName"], "DualHero")
            self.assertEqual(p2["GuildId"], "local-guild-uuid-123")
            self.assertEqual(p2["GuildName"], "Bang Cục Bộ")
            bak = phone2.s1_accounts["acct_1"].state_path.with_name(
                f"{phone2.s1_accounts['acct_1'].state_path.name}.pre_cloud_pull.bak"
            )
            self.assertTrue(bak.exists())

    def test_03_smart_zone_trigger_throttling_prevents_spam(self) -> None:
        hub = _MockCloudflareSyncHub(invite_code="INU-999")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dev = self._make_device(root, "dev_throttle", hub)
            _prepare_player(dev, "ThrottleHero", lv=20)
            self.assertTrue(dev.hybrid_sync.register("throt", "pw123", invite_code="INU-999")["ok"])
            calls_after_reg = hub.sync_calls

            # Simulate user entering LeaderBoard / PVP / Friend 10 times immediately after sync -> 0 extra calls!
            for _ in range(10):
                fired = dev.hybrid_sync.maybe_trigger_async_sync("LeaderBoard", "RankList")
                self.assertFalse(fired)
            self.assertEqual(hub.sync_calls, calls_after_reg)

            # Manual sync within 15s cooldown -> throttled
            m_res = dev.hybrid_sync.sync_now(ignore_cooldown=False, reason="manual")
            # Force _last_manual_mono set first
            dev.hybrid_sync._last_manual_mono = time.monotonic()
            m_res2 = dev.hybrid_sync.sync_now(ignore_cooldown=False, reason="manual")
            self.assertFalse(m_res2["ok"])
            self.assertTrue(m_res2.get("throttled"))

            # Simulate zone cooldown elapsed -> fires once, then immediately blocks spam again!
            dev.hybrid_sync._last_attempt_mono = time.monotonic() - 200
            dev.hybrid_sync._last_zone_trigger_mono = time.monotonic() - 200
            self.assertTrue(dev.hybrid_sync.maybe_trigger_async_sync("PVP", "GetInfo"))
            self.assertFalse(dev.hybrid_sync.maybe_trigger_async_sync("PVP", "GetInfo"))
            time.sleep(0.2)
            self.assertGreaterEqual(hub.sync_calls, calls_after_reg + 1)

    def test_04_http_hybrid_endpoints(self) -> None:
        hub = _MockCloudflareSyncHub(invite_code="INU-999")
        with tempfile.TemporaryDirectory() as td:
            srv = ThreadingEmulatorServer(("127.0.0.1", 0), persist=True, quiet=True, data_dir=Path(td))
            srv.emu.hybrid_sync = HybridSyncManager(
                Path(td),
                srv.emu,
                persist=True,
                default_url="https://mock.sync.workers.dev",
                http_opener=hub.opener,
            )
            port = srv.server_address[1]
            import threading

            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/hybrid/status", timeout=5) as r:
                    st = json.loads(r.read().decode())
                self.assertTrue(st["ok"])
                self.assertFalse(st["enabled"])

                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/hybrid/test",
                    data=json.dumps({"server_url": "https://mock.sync.workers.dev"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    res = json.loads(r.read().decode())
                self.assertTrue(res["ok"])
                self.assertTrue(res["info"]["invite_required"])
            finally:
                srv.shutdown()
                srv.server_close()

    def test_05_android_fuse_chmod_eperm_does_not_abort_startup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            def _raise_eperm(_path, _mode):
                raise PermissionError(1, "Operation not permitted")

            with patch.object(os, "chmod", side_effect=_raise_eperm):
                srv = ThreadingEmulatorServer(
                    ("127.0.0.1", 0),
                    persist=True,
                    quiet=True,
                    env="dev",
                    data_dir=Path(td),
                )
            port = srv.server_address[1]
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                    self.assertEqual(r.status, 200)
                    health = json.loads(r.read().decode())
                self.assertTrue(health.get("ok"))

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/hybrid/status", timeout=5) as r:
                    self.assertEqual(r.status, 200)
                    st = json.loads(r.read().decode())
                self.assertTrue(st["ok"])
            finally:
                srv.shutdown()
                srv.server_close()

    def test_06_client_aspx_accepts_raw_crlf_in_apperror_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            srv = ThreadingEmulatorServer(
                ("127.0.0.1", 0),
                persist=True,
                quiet=True,
                env="dev",
                data_dir=Path(td),
            )
            port = srv.server_address[1]
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                raw_json = (
                    '{"ModuleName":"Player","MethodName":"Login","ServerId":1,'
                    '"Data":["samsung","SM-A515F",123456,"abc","{}","100001"],'
                    '"ExtensionString":{"APPError":["line1base64chunk\r\nline2base64chunk"],"GuideInfo":[]}}'
                ).encode("utf-8")
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/client.aspx",
                    data=raw_json,
                    headers={"Content-Type": "application/json", "X-Plain-Json": "1"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    self.assertEqual(r.status, 200)
                    resp = json.loads(r.read().decode("utf-8"))
                self.assertEqual(resp.get("Status"), 0)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_07_logout_switch_to_tk1_relogin_reattaches_tk2_without_corrupting_tk1(self) -> None:
        hub = _MockCloudflareSyncHub(invite_code="INU-999")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            emu = self._make_device(root, "multi_slot_relogin", hub)
            emu.ensure_s1_account_slots(3)

            s1 = emu.s1_accounts["acct_1"]
            s1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["JesizLyly", 1]})
            s1.state["player"]["Lv"] = 2
            s1.state["player"]["PlayerId"] = "200001"
            s1.save()

            s2 = emu.s1_accounts["acct_2"]
            s2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["vũ khoai to", 1]})
            s2.state["player"]["Lv"] = 29
            s2.state["player"]["FAP"] = 114460
            s2.save()

            # Register Cloud Sync while TK2 is active
            emu.switch_s1_account("acct_2")
            reg = emu.hybrid_sync.register("kkk", "pw123", invite_code="INU-999")
            self.assertTrue(reg["ok"])
            cloud_pid = emu.hybrid_sync.cfg["player_id"]
            self.assertEqual(emu.hybrid_sync.cfg["local_account_id"], "acct_2")
            self.assertEqual(s2.state["player"]["PlayerId"], cloud_pid)
            self.assertEqual(s1.state["player"]["PlayerId"], "200001")

            # Logout Cloud -> switch to TK1 -> log back into kkk
            self.assertTrue(emu.hybrid_sync.logout()["ok"])
            emu.switch_s1_account("acct_1")
            relog = emu.hybrid_sync.login("kkk", "pw123")
            self.assertTrue(relog["ok"])
            self.assertTrue(relog["switched_account"])
            self.assertEqual(relog["bound_account_id"], "acct_2")
            self.assertEqual(relog["bound_user_id"], "100002")
            self.assertEqual(emu.active_account_id, "acct_2")
            self.assertEqual(emu.hybrid_sync.cfg["local_account_id"], "acct_2")
            self.assertEqual(s1.state["player"]["PlayerId"], "200001")
            self.assertEqual(s2.state["player"]["PlayerId"], cloud_pid)

            # Verify switching TK1 <-> TK2 resolves each profile cleanly
            emu.switch_s1_account("acct_1")
            av1 = emu.handle_rpc({
                "ModuleName": "Player",
                "MethodName": "AvatarInfo",
                "ServerId": 1,
                "PlayerId": "200001",
                "Data": [],
            })
            self.assertEqual(av1["Value"]["PlayerName"], "JesizLyly")

            emu.switch_s1_account("acct_2")
            av2 = emu.handle_rpc({
                "ModuleName": "Player",
                "MethodName": "AvatarInfo",
                "ServerId": 1,
                "PlayerId": cloud_pid,
                "Data": [],
            })
            self.assertEqual(av2["Value"]["PlayerName"], "vũ khoai to")
            self.assertEqual(int(av2["Value"]["Lv"]), 29)

    def test_08_startup_deduplicates_corrupted_duplicate_player_id_preserving_higher_lv_slot(self) -> None:
        dup_pid = "54879eb4-d4a5-48ec-9971-bbf26d5ef61a"
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            emu0 = GameEmulatorState(persist=True, data_dir=d)
            emu0.ensure_s1_account_slots(3)

            s1 = emu0.s1_accounts["acct_1"]
            s1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["JesizLyly", 1]})
            s1.state["player"]["Lv"] = 2
            s1.state["player"]["FAP"] = 500
            s1.state["player"]["PlayerId"] = dup_pid
            s1.save()

            s2 = emu0.s1_accounts["acct_2"]
            s2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["vũ khoai to", 1]})
            s2.state["player"]["Lv"] = 29
            s2.state["player"]["FAP"] = 114460
            s2.state["player"]["PlayerId"] = dup_pid
            s2.save()
            emu0.switch_s1_account("acct_1")

            # Restart emulator cleanly -> must auto-heal duplicate PlayerId and keep higher-Lv acct_2 intact
            emu1 = GameEmulatorState(persist=True, data_dir=d)
            pid1 = emu1.s1_accounts["acct_1"].state["player"]["PlayerId"]
            pid2 = emu1.s1_accounts["acct_2"].state["player"]["PlayerId"]
            self.assertEqual(pid2, dup_pid)
            self.assertNotEqual(pid1, dup_pid)
            self.assertEqual(pid1, "200001")

            # Switch to acct_2 and verify login + RPC hit vũ khoai to
            emu1.switch_s1_account("acct_2")
            emu1.handle_rpc({
                "ModuleName": "Player",
                "MethodName": "Login",
                "ServerId": 1,
                "Data": ["samsung", "SM-A515F", 123, "t", "{}", "100002"],
            })
            av2 = emu1.handle_rpc({
                "ModuleName": "Player",
                "MethodName": "AvatarInfo",
                "ServerId": 1,
                "PlayerId": pid2,
                "Data": [],
            })
            self.assertEqual(av2["Value"]["PlayerName"], "vũ khoai to")
            self.assertEqual(int(av2["Value"]["Lv"]), 29)

    def test_09_server_py_files_below_ide_diff_limit_and_fresh_bundle_boots(self) -> None:
        import importlib.util
        import socket
        import subprocess
        import urllib.error
        import zipfile

        max_bytes = 450 * 1024
        for py_path in sorted(SERVER_DIR.glob("*.py")):
            raw = py_path.read_bytes()
            self.assertLess(
                len(raw),
                max_bytes,
                f"{py_path.name} is {len(raw)} bytes (>= {max_bytes}); keep under IDE 512 KiB cutoff",
            )
            txt = raw.decode("utf-8")
            trunc_marker = "truncated for " + "diff preview"
            self.assertNotIn(trunc_marker, txt, f"Corrupted marker in {py_path.name}")
            compile(txt, str(py_path), "exec")

        build_script = SERVER_DIR.parent / "poc" / "build_standalone_apk.py"
        poc_dir = str(build_script.parent)
        added_poc = poc_dir not in sys.path
        if added_poc:
            sys.path.insert(0, poc_dir)
        try:
            spec = importlib.util.spec_from_file_location("build_standalone_apk", build_script)
            assert spec is not None and spec.loader is not None
            build_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(build_mod)
        finally:
            if added_poc and poc_dir in sys.path:
                sys.path.remove(poc_dir)

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            bundle_zip = tdp / "server_bundle.zip"
            srv_dir = tdp / "srv"
            sav_dir = tdp / "saves"
            srv_dir.mkdir(parents=True)
            sav_dir.mkdir(parents=True)

            build_mod.build_server_bundle_zip(bundle_zip, server_dir=SERVER_DIR)
            with zipfile.ZipFile(bundle_zip, "r") as zf:
                names = set(zf.namelist())
                for req_name in (
                    "emulator.py",
                    "emulator_common.py",
                    "pvp_boss_handlers.py",
                    "treasure_rebirth_handlers.py",
                    "progression_handlers.py",
                ):
                    self.assertIn(req_name, names)
                zf.extractall(srv_dir)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]

            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(srv_dir / "emulator.py"),
                    "--env",
                    "dev",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--data-dir",
                    str(sav_dir),
                    "--trace-path",
                    str(sav_dir / "rpc_trace.log"),
                ],
                cwd=str(srv_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                health = None
                for _ in range(150):
                    if proc.poll() is not None:
                        out, _ = proc.communicate(timeout=2)
                        self.fail(f"Bundled server exited early (rc={proc.returncode}): {out}")
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as r:
                            if r.status == 200:
                                health = json.loads(r.read().decode("utf-8"))
                                break
                    except (OSError, urllib.error.URLError, ValueError):
                        time.sleep(0.05)
                self.assertIsNotNone(health, "Bundled backend failed to respond on /health")
                self.assertTrue(health.get("ok"))

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/hybrid/status", timeout=2) as r:
                    self.assertEqual(r.status, 200)
                    st = json.loads(r.read().decode("utf-8"))
                self.assertTrue(st.get("ok"))
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
                if proc.stdout is not None:
                    proc.stdout.close()

    def test_10_endgame_snapshot_compaction_under_28kb_preserves_peer_formation(self) -> None:
        from hybrid_sync import ReadOnlyPeerProxy, build_public_snapshot

        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, data_dir=Path(td))
            _prepare_player(emu, "EndgameCap", lv=80)
            store = emu.s1_accounts["acct_1"]

            # Populate 6 heavy endgame slots so raw _own_slot_formations_view exceeds 36 KB
            base_slot = dict(store.state["slots"][0])
            heavy_props = {f"PadZero{i}": 0 for i in range(60)}
            heavy_props.update({"HP": 500000, "AP": 85000, "DEF": 32000, "SPD": 450, "FSP": 900, "FAP": 450000})
            heavy_eq = {f"ExtraStat{i}": i * 10 for i in range(25)}
            heavy_eq.update({"Id": str(uuid.uuid4()), "ModelId": 13010001, "Lv": 160, "Step": 12, "Quality": 18})
            heavy_slots = []
            for idx in range(1, 7):
                sl = dict(base_slot)
                sl["SlotId"] = idx
                sl["HeroId"] = store.state["heroes"][0]["Id"]
                sl["HeroModelId"] = 12011002 + idx
                sl["Lv"] = 80
                sl["Step"] = 10
                sl["FAP"] = 450000
                sl["Property"] = dict(heavy_props)
                for k in ("Weapon", "Helmet", "Clothes", "Necklace", "Book", "Badge", "Pet"):
                    eq = dict(heavy_eq)
                    eq["Id"] = str(uuid.uuid4())
                    sl[k] = eq
                sl["Gem"] = [{"Slot": g, "ModelId": 14010001 + g, "Extra": "x" * 60} for g in range(6)]
                sl["Warfarespirit"] = [{"Pos": w, "ModelId": 81010001 + w, "Extra": "y" * 60} for w in range(4)]
                heavy_slots.append(sl)
            store.state["slots"] = heavy_slots

            raw_sf_bytes = len(
                json.dumps(store._own_slot_formations_view(), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            )
            self.assertGreater(raw_sf_bytes, 36 * 1024)

            snap = build_public_snapshot(store)
            snap_bytes = len(json.dumps(snap, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
            self.assertLessEqual(snap_bytes, 28 * 1024, f"Compacted snapshot too large: {snap_bytes} bytes")

            pid = str(store.state["player"]["PlayerId"])
            proxy = ReadOnlyPeerProxy({"player_id": pid, "name": "EndgameCap", "lv": 80, "fap": 999999, "snapshot": snap})
            sf_view = proxy._own_slot_formations_view()
            self.assertEqual(len(sf_view.get("SlotInfos", [])), 6)
            self.assertEqual(len(sf_view.get("SlotInfo", [])), 6)
            self.assertIsInstance(proxy._build_ally_fight_objs(), list)

    def test_11_android_dns_errno7_uses_cache_and_doh_fallback(self) -> None:
        import io
        import socket
        from unittest import mock
        import urllib.error
        from hybrid_sync import HybridSyncManager

        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=False, data_dir=Path(td))
            mgr = HybridSyncManager(Path(td), emu, persist=False)

            doh_payload = json.dumps({
                "Status": 0,
                "Answer": [{"name": "inuyasha-sync-hub.vuphamletruong.workers.dev", "type": 1, "TTL": 300, "data": "104.21.70.143"}],
            }).encode("utf-8")

            class _FakeResp:
                def __init__(self, status: int, body: bytes) -> None:
                    self.status = status
                    self._bio = io.BytesIO(body)

                def read(self) -> bytes:
                    return self._bio.read()

                def __enter__(self) -> "_FakeResp":
                    return self

                def __exit__(self, *_args: object) -> None:
                    return None

            gai_err = urllib.error.URLError(socket.gaierror(7, "No address associated with hostname"))
            seen_urls: list[str] = []

            def fake_urlopen(req: Any, **_kwargs: Any) -> _FakeResp:
                u = req.full_url if hasattr(req, "full_url") else str(req)
                seen_urls.append(u)
                if u.startswith("https://1.1.1.1/dns-query"):
                    return _FakeResp(200, doh_payload)
                raise gai_err

            via_ip_calls: list[tuple[str, str, str]] = []

            def fake_via_ip(method: str, url: str, target_ip: str, _headers: dict[str, str], _data: bytes | None, _timeout: float) -> tuple[int, dict[str, Any]]:
                via_ip_calls.append((method, url, target_ip))
                return 200, {"ok": True, "service": "inuyasha-sync-hub"}

            with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), mock.patch.object(
                mgr, "_http_json_via_ip", side_effect=fake_via_ip
            ):
                # 1. Cold cache + Errno 7 -> DoH resolves 104.21.70.143 -> _http_json_via_ip succeeds
                code, body = mgr._http_json("GET", "https://inuyasha-sync-hub.vuphamletruong.workers.dev/health")
                self.assertEqual(code, 200)
                self.assertTrue(body.get("ok"))
                self.assertEqual(via_ip_calls[-1][2], "104.21.70.143")
                self.assertTrue(any(u.startswith("https://1.1.1.1/dns-query") for u in seen_urls))

                # 2. Warm cache + Errno 7 -> uses cached IP directly without another DoH query
                seen_urls.clear()
                code2, body2 = mgr._http_json("GET", "https://inuyasha-sync-hub.vuphamletruong.workers.dev/health")
                self.assertEqual(code2, 200)
                self.assertTrue(body2.get("ok"))
                self.assertFalse(any("dns-query" in u for u in seen_urls))

            # 3. Truly offline (urlopen + DoH + direct IP all fail) -> clean Vietnamese error, no raw Errno 7
            mgr._resolved_ip_cache.clear()
            with mock.patch("urllib.request.urlopen", side_effect=gai_err):
                code3, body3 = mgr._http_json("GET", "https://inuyasha-sync-hub.vuphamletruong.workers.dev/health")
                self.assertEqual(code3, 0)
                self.assertFalse(body3.get("ok"))
                err_msg = str(body3.get("error") or "")
                self.assertIn("Không kết nối được Sync Hub:", err_msg)
                self.assertNotIn("Errno 7", err_msg)
                self.assertNotIn("urlopen error", err_msg)


if __name__ == "__main__":
    unittest.main()
