"""Integration and security tests for Small Private Server Core (R8.1)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import ThreadingEmulatorServer  # noqa: E402
from private_auth import PrivateServerConfig  # noqa: E402


class R81PrivateServerTest(unittest.TestCase):
    ADMIN_TOKEN = "test-admin-token-r81"

    def _start_server(
        self,
        tmpdir: str,
        *,
        cfg: PrivateServerConfig | None = None,
    ) -> tuple[ThreadingEmulatorServer, str]:
        srv = ThreadingEmulatorServer(
            ("127.0.0.1", 0),
            persist=True,
            quiet=True,
            env="private",
            data_dir=Path(tmpdir),
            trace_path=Path(tmpdir) / "private_rpc.log",
            admin_token=self.ADMIN_TOKEN,
            private_mode=True,
            private_config=cfg,
        )
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return srv, f"http://127.0.0.1:{srv.server_port}"

    @staticmethod
    def _stop_server(srv: ThreadingEmulatorServer) -> None:
        srv.shutdown()
        srv.server_close()

    @staticmethod
    def _http_json(
        url: str,
        method: str = "GET",
        payload: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(body)
            except ValueError:
                parsed = {"raw": body}
            return exc.code, parsed

    @staticmethod
    def _rpc(
        base_url: str,
        mod: str,
        fn: str,
        data: list | None = None,
        *,
        player_id: str = "",
        session: str = "",
    ) -> dict:
        payload = {
            "ServerId": 1,
            "ModuleName": mod,
            "MethodName": fn,
            "PlayerId": player_id,
            "Session": session,
            "Data": list(data or []),
        }
        req = urllib.request.Request(
            f"{base_url}/client.aspx",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Plain-Json", "1")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _server_list(
        base_url: str,
        user_id: str,
        login_info: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict:
        body = (
            f"gameID=0&PartnerID=1001&GameVersionID=504&EncryptedString=abc"
            f"&RandNum=1&ResourceVersionName=&UserID={user_id}&LoginInfo={login_info}"
        ).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/API/ServerList_Client.ashx", data=body, method="POST")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read()
        return json.loads(zlib.decompress(raw).decode("utf-8"))

    def _enter_player(self, base_url: str, username: str, password: str, *, action: str = "register", role_name: str | None = None) -> tuple[str, str, dict]:
        st, auth = self._http_json(
            f"{base_url}/auth/{action}",
            method="POST",
            payload={"username": username, "password": password},
            headers={"X-Forwarded-For": f"10.0.0.{hash(username) % 200 + 10}"},
        )
        self.assertEqual(st, 200, auth)
        slist = self._server_list(base_url, auth["UserID"], auth["AuthToken"])
        self.assertEqual(slist["Code"], 0)
        ui = slist["Data"]["UserInfo"]
        login_res = self._rpc(
            base_url,
            "Player",
            "Login",
            ["Android", "13", 1, "abc", ui["LoginInfo"], ui["UserID"]],
        )
        self.assertEqual(login_res["Status"], 0, login_res)
        pinfo = login_res["Value"]
        pid = str(pinfo["PlayerId"])
        sess = str(pinfo["Session"])
        if role_name and int(pinfo.get("IsNewPlayer", 1)) == 1:
            np = self._rpc(base_url, "Player", "NewPlayer", [role_name, 1], player_id=pid, session=sess)
            self.assertEqual(np["Status"], 0, np)
        return pid, sess, auth

    def test_01_register_login_password_and_rate_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srv, base = self._start_server(tmp)
            try:
                st, info = self._http_json(f"{base}/auth/info")
                self.assertEqual(st, 200)
                self.assertEqual(info["registered_accounts"], 0)
                self.assertTrue(info["allow_registration"])

                # /account locked out without admin token (401) and rejected locally even with admin token (403)
                st_no_tok, _ = self._http_json(f"{base}/account")
                self.assertEqual(st_no_tok, 401)
                st_with_tok, _ = self._http_json(
                    f"{base}/account", headers={"X-Admin-Token": self.ADMIN_TOKEN}
                )
                self.assertEqual(st_with_tok, 403)

                # Bad username & short password rejected
                st_bad_u, _ = self._http_json(
                    f"{base}/auth/register", "POST", {"username": "a!", "password": "secret"}
                )
                self.assertEqual(st_bad_u, 400)
                st_bad_p, _ = self._http_json(
                    f"{base}/auth/register", "POST", {"username": "valid_user", "password": "12"}
                )
                self.assertEqual(st_bad_p, 400)

                # Register Alice (GM) and Bob
                st_a, res_a = self._http_json(
                    f"{base}/auth/register", "POST", {"username": "Alice", "password": "secret123"}
                )
                self.assertEqual(st_a, 200)
                self.assertEqual(res_a["UserID"], "100001")
                self.assertEqual(res_a["PlayerId"], "200001")
                self.assertEqual(res_a["Role"], "gm")
                self.assertRegex(res_a["AuthToken"], r"^[0-9a-f]{48}$")

                # Case-insensitive duplicate rejected
                st_dup, _ = self._http_json(
                    f"{base}/auth/register", "POST", {"username": "alice", "password": "otherpass"}
                )
                self.assertEqual(st_dup, 409)

                st_b, res_b = self._http_json(
                    f"{base}/auth/register", "POST", {"username": "Bob_02", "password": "bobpass1"}
                )
                self.assertEqual(st_b, 200)
                self.assertEqual(res_b["UserID"], "100002")
                self.assertEqual(res_b["PlayerId"], "200002")
                self.assertEqual(res_b["Role"], "player")

                # Wrong password fails, correct succeeds
                st_wrong, _ = self._http_json(
                    f"{base}/auth/login", "POST", {"username": "Bob_02", "password": "wrong"}
                )
                self.assertEqual(st_wrong, 401)
                st_ok, _ = self._http_json(
                    f"{base}/auth/login", "POST", {"username": "Bob_02", "password": "bobpass1"}
                )
                self.assertEqual(st_ok, 200)

                # Password change invalidates old password
                st_cp, res_cp = self._http_json(
                    f"{base}/auth/change_password",
                    "POST",
                    {"username": "Bob_02", "old_password": "bobpass1", "new_password": "bobpass2"},
                )
                self.assertEqual(st_cp, 200)
                self.assertTrue(res_cp["ok"])
                self.assertEqual(
                    self._http_json(f"{base}/auth/login", "POST", {"username": "Bob_02", "password": "bobpass1"})[0],
                    401,
                )
                self.assertEqual(
                    self._http_json(f"{base}/auth/login", "POST", {"username": "Bob_02", "password": "bobpass2"})[0],
                    200,
                )

                # Rate limiter triggers 429 after 30 calls from one IP within 60s
                statuses = [
                    self._http_json(
                        f"{base}/auth/login",
                        "POST",
                        {"username": "Alice", "password": "wrong"},
                        headers={"X-Forwarded-For": "203.0.113.55"},
                    )[0]
                    for _ in range(31)
                ]
                self.assertEqual(statuses[-1], 429)
            finally:
                self._stop_server(srv)

    def test_02_strict_session_isolation_and_single_device_kick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srv, base = self._start_server(tmp)
            try:
                # Reverse-proxy headers Reflected dynamically in ServerList_Client
                _, reg_a = self._http_json(
                    f"{base}/auth/register", "POST", {"username": "Alice", "password": "pass1234"}
                )
                slist_proxy = self._server_list(
                    base,
                    reg_a["UserID"],
                    reg_a["AuthToken"],
                    headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "play.example.com"},
                )
                self.assertEqual(slist_proxy["Code"], 0)
                self.assertEqual(slist_proxy["Data"]["Server"][0]["ServerUrl"], "https://play.example.com")
                self.assertEqual(slist_proxy["Data"]["Server"][0]["ChatServerUrl"], "play.example.com:8081")

                pid_a, sess_a1, _ = self._enter_player(base, "Alice", "pass1234", action="login", role_name="Alisa")
                pid_b, sess_b1, _ = self._enter_player(base, "Bob", "pass1234", action="register", role_name="Bobby")
                self.assertNotEqual(pid_a, pid_b)
                self.assertNotEqual(sess_a1, sess_b1)

                # Spoofing Bob's Session on Alice's PlayerId & missing session both fail with -1101
                spoof = self._rpc(base, "Player", "GetInitData", [], player_id=pid_a, session=sess_b1)
                self.assertEqual(spoof["Status"], -1101)
                missing = self._rpc(base, "Player", "GetInitData", [], player_id=pid_a, session="")
                self.assertEqual(missing["Status"], -1101)
                valid_a = self._rpc(base, "Player", "GetInitData", [], player_id=pid_a, session=sess_a1)
                self.assertEqual(valid_a["Status"], 0)

                # Single-device kick: second login for Alice invalidates sess_a1
                _, sess_a2, _ = self._enter_player(base, "Alice", "pass1234", action="login")
                self.assertNotEqual(sess_a1, sess_a2)
                self.assertEqual(
                    self._rpc(base, "Player", "GetInitData", [], player_id=pid_a, session=sess_a1)["Status"],
                    -1101,
                )
                self.assertEqual(
                    self._rpc(base, "Player", "GetInitData", [], player_id=pid_a, session=sess_a2)["Status"],
                    0,
                )

                # Admin ban blocks active session (-1102) & login (403); unban restores
                st_ban, _ = self._http_json(
                    f"{base}/admin/account_action",
                    "POST",
                    {"action": "ban", "username": "Bob"},
                    headers={"X-Admin-Token": self.ADMIN_TOKEN},
                )
                self.assertEqual(st_ban, 200)
                self.assertEqual(
                    self._rpc(base, "Player", "GetInitData", [], player_id=pid_b, session=sess_b1)["Status"],
                    -1102,
                )
                self.assertEqual(
                    self._http_json(f"{base}/auth/login", "POST", {"username": "Bob", "password": "pass1234"})[0],
                    403,
                )
                self._http_json(
                    f"{base}/admin/account_action",
                    "POST",
                    {"action": "unban", "username": "Bob"},
                    headers={"X-Admin-Token": self.ADMIN_TOKEN},
                )
                self.assertEqual(
                    self._http_json(f"{base}/auth/login", "POST", {"username": "Bob", "password": "pass1234"})[0],
                    200,
                )
            finally:
                self._stop_server(srv)

    def test_03_multiplayer_shared_world_and_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srv, base = self._start_server(tmp)
            try:
                pid_a, sess_a, _ = self._enter_player(base, "alice", "pass1234", role_name="AliceVN")
                pid_b, sess_b, _ = self._enter_player(base, "bob", "pass1234", role_name="BobVN")

                for uname, lv, vip in (("alice", 78, 5), ("bob", 76, 4)):
                    st_prep, _ = self._http_json(
                        f"{base}/admin/prepare",
                        "POST",
                        {"profile": uname, "target_lv": lv, "vip_lv": vip},
                        headers={"X-Admin-Token": self.ADMIN_TOKEN},
                    )
                    self.assertEqual(st_prep, 200)

                # LeaderBoard RankList(2=Lv) sees both real players
                lb = self._rpc(base, "LeaderBoard", "RankList", [2], player_id=pid_a, session=sess_a)
                self.assertEqual(lb["Status"], 0)
                lb_pids = {str(r.get("Id")) for r in lb["Value"].get("RankList", [])}
                self.assertIn(pid_a, lb_pids)
                self.assertIn(pid_b, lb_pids)

                # Friend request Alice -> Bob, Bob accepts -> both are friends
                ap_fr = self._rpc(
                    base, "FriendMessage", "FriendApply", [pid_b, "Chào bạn!"], player_id=pid_a, session=sess_a
                )
                self.assertEqual(ap_fr["Status"], 0)
                accept = self._rpc(base, "Friend", "FriendApplyResponse", [pid_a, True], player_id=pid_b, session=sess_b)
                self.assertEqual(accept["Status"], 0)
                fl_a = self._rpc(base, "Friend", "GetFriendList", [], player_id=pid_a, session=sess_a)
                self.assertIn(pid_b, {str(f["PlayerId"]) for f in fl_a["Value"]})

                # Guild shared across players in <data_dir>/s1_guilds.json
                st_g, _ = self._http_json(
                    f"{base}/admin/grant",
                    "POST",
                    {"profile": "alice", "resources": [{"type": "Diamond", "amount": 2000}, {"type": "Gold", "amount": 1_000_000}]},
                    headers={"X-Admin-Token": self.ADMIN_TOKEN},
                )
                self.assertEqual(st_g, 200)
                cg = self._rpc(
                    base, "Guild", "CreateGuild", ["PrivateClan", "Chào anh em"], player_id=pid_a, session=sess_a
                )
                self.assertEqual(cg["Status"], 0, cg)
                gid = cg["Value"]["GuildInfo"]["Id"]
                self.assertTrue((Path(tmp) / "s1_guilds.json").exists())
                self.assertEqual(self._rpc(base, "Guild", "AlterAutoApply", [0], player_id=pid_a, session=sess_a)["Status"], 0)
                join_b = self._rpc(base, "Guild", "GuildApply", [gid], player_id=pid_b, session=sess_b)
                self.assertEqual(join_b["Status"], 0)
                self.assertEqual(
                    self._rpc(base, "Guild", "ManageApply", [pid_b, 1], player_id=pid_a, session=sess_a)["Status"], 0
                )
                g_info_b = self._rpc(base, "Guild", "GetGuildInfo", [], player_id=pid_b, session=sess_b)
                self.assertEqual(g_info_b["Status"], 0)
                self.assertEqual(g_info_b["Value"]["GuildInfo"]["Id"], gid)

                # Concurrent requests across Alice & Bob without deadlock
                def _worker(pid: str, sess: str) -> list[int]:
                    out = []
                    for _ in range(10):
                        r1 = self._rpc(base, "LeaderBoard", "RankList", [1], player_id=pid, session=sess)
                        r2 = self._rpc(base, "PVP", "GetPVPInfo", [], player_id=pid, session=sess)
                        r3 = self._rpc(base, "PVPinter", "GetPVPInterTopRank", [0], player_id=pid, session=sess)
                        out.extend([r1["Status"], r2["Status"], r3["Status"]])
                    return out

                with ThreadPoolExecutor(max_workers=2) as pool:
                    f1 = pool.submit(_worker, pid_a, sess_a)
                    f2 = pool.submit(_worker, pid_b, sess_b)
                    self.assertTrue(all(code == 0 for code in f1.result() + f2.result()))
            finally:
                self._stop_server(srv)

    def test_04_recharge_policy_and_offline_save_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srv, base = self._start_server(tmp)
            try:
                pid_a, sess_a, _ = self._enter_player(base, "alice", "pass1234", role_name="AliceSave")
                pid_b, sess_b, _ = self._enter_player(base, "bob", "pass1234", role_name="BobSave")

                # Default: instant 1M KC visible and works
                clist = self._rpc(base, "PlayerCharge", "GetChargeList", [], player_id=pid_a, session=sess_a)
                self.assertIn("com.cmn.inuyasha.gem1000000", [t["ProductId"] for t in clist["Value"]])
                ord1m = self._rpc(
                    base,
                    "PlayerCharge",
                    "GenerateOrderID",
                    ["com.cmn.inuyasha.gem1000000"],
                    player_id=pid_a,
                    session=sess_a,
                )
                self.assertEqual(ord1m["Status"], 0)
                conf1m = self._rpc(
                    base,
                    "PlayerCharge",
                    "ConfirmOrder",
                    ["com.cmn.inuyasha.gem1000000", ord1m["Value"]],
                    player_id=pid_a,
                    session=sess_a,
                )
                self.assertEqual(conf1m["Status"], 0)

                # Daily cap = 2 for Bob
                srv.emu.private_config.max_free_recharge_per_day = 2
                for _ in range(2):
                    oid = self._rpc(base, "PlayerCharge", "GenerateOrderID", ["com.cmn.inuyasha.gem60"], player_id=pid_b, session=sess_b)["Value"]
                    self.assertEqual(
                        self._rpc(base, "PlayerCharge", "ConfirmOrder", ["com.cmn.inuyasha.gem60", oid], player_id=pid_b, session=sess_b)["Status"],
                        0,
                    )
                oid3 = self._rpc(base, "PlayerCharge", "GenerateOrderID", ["com.cmn.inuyasha.gem60"], player_id=pid_b, session=sess_b)["Value"]
                self.assertEqual(
                    self._rpc(base, "PlayerCharge", "ConfirmOrder", ["com.cmn.inuyasha.gem60", oid3], player_id=pid_b, session=sess_b)["Status"],
                    -1,
                )

                # Disable 1M instant tier
                srv.emu.private_config.allow_instant_1m_recharge = False
                clist2 = self._rpc(base, "PlayerCharge", "GetChargeList", [], player_id=pid_a, session=sess_a)
                self.assertNotIn("com.cmn.inuyasha.gem1000000", [t["ProductId"] for t in clist2["Value"]])
                self.assertEqual(
                    self._rpc(base, "PlayerCharge", "GenerateOrderID", ["com.cmn.inuyasha.gem1000000"], player_id=pid_a, session=sess_a)["Status"],
                    -1,
                )

                # Disable all free recharge & month cards
                srv.emu.private_config.allow_free_recharge = False
                self.assertEqual(
                    self._rpc(base, "PlayerCharge", "GenerateOrderID", ["com.cmn.inuyasha.gem60"], player_id=pid_a, session=sess_a)["Status"],
                    -1,
                )
                self.assertEqual(
                    self._rpc(base, "CardInfo", "GenerateOrderID", [1], player_id=pid_a, session=sess_a)["Status"],
                    -1,
                )

                # Import offline standalone save into Alice, keeping Alice's private PlayerId & unique ArenaRank
                bob_store = srv.emu.auth.resolve_store_by_identifier("bob")
                bob_rank = int(bob_store.state["pvp"]["rank"])
                imported_state = copy.deepcopy(bob_store.state)
                imported_state["player"]["PlayerName"] = "ImportedInu"
                imported_state["player"]["Lv"] = 50
                imported_state["player"]["Vip"] = 8
                imported_state["player"]["Diamond"] = 123_456
                imported_state["player"]["PlayerId"] = pid_b  # intentional collision in offline save
                imported_state["pvp"]["rank"] = bob_rank       # intentional collision in offline save
                bundle = {
                    "bundle_format": "inuyasha_seek_jade_standalone_save_v1",
                    "accounts": {"acct_1": {"meta": {"account_id": "acct_1"}, "state": imported_state}},
                }
                st_imp, res_imp = self._http_json(
                    f"{base}/admin/account_action",
                    "POST",
                    {"action": "import_offline_save", "username": "alice", "bundle_data": bundle},
                    headers={"X-Admin-Token": self.ADMIN_TOKEN},
                )
                self.assertEqual(st_imp, 200, res_imp)
                self.assertEqual(res_imp["PlayerId"], pid_a)
                self.assertEqual(res_imp["Lv"], 50)
                self.assertEqual(res_imp["Vip"], 8)
                self.assertNotEqual(res_imp["ArenaRank"], bob_rank)
                init_a = self._rpc(base, "Player", "GetInitData", [], player_id=pid_a, session=sess_a)
                self.assertEqual(init_a["Status"], 0)
                self.assertEqual(init_a["Value"]["PlayerInfo"]["PlayerId"], pid_a)
                self.assertEqual(int(init_a["Value"]["PlayerInfo"]["Diamond"]), 123_456)
            finally:
                self._stop_server(srv)


if __name__ == "__main__":
    unittest.main()
