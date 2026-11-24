#!/usr/bin/env python3
"""End-to-end unit tests for Hybrid Local-First Cloud Sync (R8.2)."""

from __future__ import annotations

import json
from pathlib import Path
import secrets
import sys
import tempfile
import time
import unittest
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


if __name__ == "__main__":
    unittest.main()
