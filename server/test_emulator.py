#!/usr/bin/env python3
"""Automated end-to-end protocol, dual-profile, tutorial, ledger & asset tests for InuYasha: Seek Jade."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
import zlib
from pathlib import Path

from economy_audit import DuplicateTransactionError, ResourceLedger, ResourceTransactionError
from emulator import ThreadingEmulatorServer


class EmulatorProtocolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.srv = ThreadingEmulatorServer(("127.0.0.1", 0), persist=False, quiet=True)
        cls.port = cls.srv.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.srv.shutdown()
        cls.srv.server_close()

    def _post_json(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 200)
            raw = r.read()
            if not raw.lstrip().startswith(b"{"):
                raw = zlib.decompress(raw)
            return json.loads(raw.decode("utf-8"))

    def _post_form(self, path: str, body: str) -> dict:
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 200)
            raw = r.read()
            if not raw.lstrip().startswith(b"{"):
                raw = zlib.decompress(raw)
            return json.loads(raw.decode("utf-8"))

    def _rpc(
        self,
        module: str,
        method: str,
        data=None,
        *,
        server_id: int = 1,
        player_id: str = "200001",
        ext: dict | None = None,
    ) -> dict:
        payload = {
            "PartnerId": "1001",
            "ServerId": server_id,
            "Session": "local-revival-session-0001",
            "PlayerId": player_id,
            "GameVersionId": "505",
            "ModuleName": module,
            "MethodName": method,
            "Data": data if data is not None else [],
        }
        if ext is not None:
            payload["ExtensionString"] = ext
        return self._post_json("/client.aspx", payload)

    def test_01_server_list(self) -> None:
        res = self._post_form("/API/ServerList_Client.ashx", "gameID=0&PartnerID=1001&GameVersionID=505")
        self.assertEqual(res["Code"], 0)
        servers = res["Data"]["Server"]
        self.assertEqual(len(servers), 2)
        self.assertEqual(servers[0]["ServerID"], 1)
        self.assertIn("Normal", servers[0]["ServerName"])
        self.assertEqual(servers[1]["ServerID"], 2)
        self.assertIn("Debug", servers[1]["ServerName"])
        self.assertIn(f"127.0.0.1:{self.port}", servers[0]["ServerUrl"])
        self.assertIn(":", servers[0]["ChatServerUrl"])
        self.assertEqual(res["Data"]["ServerHistory"], [1])
        self.assertEqual(res["Data"]["Resource"], {})

    def test_02_normal_profile_onboarding_and_tutorial_flow(self) -> None:
        # 1. Fresh NORMAL login (ServerId=1)
        login = self._rpc("Player", "Login", ["android", "12", 1234, "hash", "", "100001"], server_id=1)
        self.assertEqual(login["Status"], 0)
        val_login = login["Value"]
        self.assertEqual(val_login["IsNewPlayer"], 1)
        self.assertEqual(val_login["Lv"], 1)
        self.assertEqual(val_login["Vip"], 0)
        self.assertEqual(val_login["Gold"], 100000)
        self.assertEqual(val_login["Diamond"], 0)
        self.assertEqual(val_login["VIT"], 200)
        self.assertEqual(val_login["STA"], 20)
        self.assertEqual(val_login["HeroEXP"], 5000)
        self.assertEqual(val_login["StepCountList"], {})
        pid = val_login["PlayerId"]

        # 2. RoleCreateScene -> Player.NewPlayer (Female MC 12010004)
        created = self._rpc("Player", "NewPlayer", ["KagomeTest", 1], server_id=1, player_id=pid)
        self.assertEqual(created["Status"], 0)
        self.assertEqual(created["Value"]["PlayerId"], pid)

        init_res = self._rpc("Player", "GetInitData", [1] * 20, server_id=1, player_id=pid)
        self.assertEqual(init_res["Status"], 0)
        init_val = init_res["Value"]
        self.assertEqual(init_val["PlayerInfo"]["PlayerName"], "KagomeTest")
        self.assertEqual(init_val["PlayerInfo"]["IsNewPlayer"], 0)
        self.assertEqual(len(init_val["HeroInfo"]), 1)
        self.assertEqual(init_val["HeroInfo"][0]["HeroModelId"], 12010004)
        goods_ids = {g["GoodsModelId"]: g["Num"] for g in init_val["GoodsPropsInfo"]}
        self.assertEqual(goods_ids.get(16050001), 100)
        self.assertEqual(goods_ids.get(16050003), 1)
        self.assertGreater(len(init_val["ModulesInfo"]), 5)

        # 3. Initial Chapter 11 node list only exposes 1111 (Flag=1)
        b_info = self._rpc("Battle", "GetBattleInfo", [1, 1], server_id=1, player_id=pid)
        self.assertNotIn("Lv", b_info["Avatar"])  # Avatar.Lv omitted unless level changes
        nodes = self._rpc("Battle", "GetNodeList", [11], server_id=1, player_id=pid)
        self.assertEqual([n["NodeModelId"] for n in nodes["Value"]], [1111])
        self.assertEqual(nodes["Value"][0]["Flag"], 1)

        # 4. Piggybacked ExtensionString.GuideInfo persists & Battle 1-1 levels Lv 1 -> Lv 2
        settle_1111 = self._rpc(
            "Battle",
            "Fight",
            [11, 1111, 3, True, "", False],
            server_id=1,
            player_id=pid,
            ext={"GuideInfo": [{"GuideId": 1, "Ordinal": 10212}]},
        )
        self.assertEqual(settle_1111["Status"], 0)
        self.assertEqual(settle_1111["Value"]["IsSuccess"], "True")
        self.assertEqual(settle_1111["Value"]["CurrentNode"]["Flag"], 2)
        self.assertEqual(settle_1111["Value"]["NextNode"]["NodeModelId"], 1112)
        self.assertEqual(settle_1111["Value"]["NextNode"]["Flag"], 1)
        self.assertEqual(settle_1111["Avatar"].get("Lv"), 2)
        self.assertEqual(settle_1111["Avatar"]["StepCountList"].get("1"), 10212)

        # 5. Destiny Recruit summons Ayame (12011014) -> deploy in Slot 2
        recruit = self._rpc("HeroRecruit", "Recruit", [2, 1], server_id=1, player_id=pid)
        self.assertEqual(recruit["Status"], 0)
        heroes_gained = recruit["Value"]["BaseGetGameResourceList"][0]["Hero"]
        self.assertEqual(heroes_gained[0]["HeroModelId"], 12011014)
        ayame_id = heroes_gained[0]["Id"]

        combat = self._rpc("Slot", "HeroCombat", [2, ayame_id], server_id=1, player_id=pid)
        self.assertEqual(combat["Status"], 0)
        self.assertEqual(combat["Value"]["SlotInfo"][1]["HeroModelId"], 12011014)

        # 6. Battle 1-2 levels Lv 2 -> Lv 3 and enables CanDrawRoadBoxA, then DrawRoadBox(11, 111)
        settle_1112 = self._rpc("Battle", "Fight", [11, 1112, 3, True, "", False], server_id=1, player_id=pid)
        self.assertEqual(settle_1112["Status"], 0)
        self.assertEqual(settle_1112["Avatar"].get("Lv"), 3)
        self.assertEqual(settle_1112["Value"]["CurrentChapter"]["CanDrawRoadBoxA"], 1)

        road_box = self._rpc("Battle", "DrawRoadBox", [11, 111], server_id=1, player_id=pid)
        self.assertEqual(road_box["Status"], 0)
        self.assertEqual(road_box["Value"]["Chapter"]["CanDrawRoadBoxA"], 2)
        box_equips = road_box["Value"]["BaseGetGameResourceList"][0]["Equip"]
        self.assertEqual(box_equips[0]["EquipModelId"], 13020215)

        # 7. Battle 1-3 drops 5x 13040130 -> Compose 13040215 -> OneKeyEquipCombat -> OneKeyEquipLvUp
        settle_1113 = self._rpc("Battle", "Fight", [11, 1113, 3, True, "", False], server_id=1, player_id=pid)
        self.assertEqual(settle_1113["Status"], 0)
        dropped_equips = settle_1113["Value"]["BaseGetGameResourceList"][0]["Equip"]
        white_necklaces = [e for e in dropped_equips if e["EquipModelId"] == 13040130]
        self.assertEqual(len(white_necklaces), 5)

        compose = self._rpc("Equip", "EquipOneKeyCompose", [], server_id=1, player_id=pid)
        self.assertEqual(compose["Status"], 0)
        self.assertEqual(len(compose["Value"]["ConsumeList"]), 5)
        composed_necklace = compose["Value"]["BaseGetGameResourceList"][0]["Equip"][0]
        self.assertEqual(composed_necklace["EquipModelId"], 13040215)

        dagger_id = settle_1111["Value"]["BaseGetGameResourceList"][0]["Equip"][0]["Id"]
        helmet_id = box_equips[0]["Id"]
        eq_combat = self._rpc(
            "Slot",
            "OneKeyEquipCombat",
            [1, dagger_id, helmet_id, "", composed_necklace["Id"], "", ""],
            server_id=1,
            player_id=pid,
        )
        self.assertEqual(eq_combat["Status"], 0)
        slot1 = eq_combat["Value"]["SlotInfo"][0]
        self.assertEqual(slot1["Weapon"]["EquipModelId"], 13010215)
        self.assertEqual(slot1["Helmet"]["EquipModelId"], 13020215)
        self.assertEqual(slot1["Necklace"]["EquipModelId"], 13040215)

        lv_up = self._rpc(
            "Equip",
            "OneKeyEquipLvUp",
            [[dagger_id, helmet_id, composed_necklace["Id"]]],
            server_id=1,
            player_id=pid,
        )
        self.assertEqual(lv_up["Status"], 0)
        self.assertTrue(all(e["Lv"] > 0 for e in lv_up["Value"]["EquipsInfo"]))

        fmt_get = self._rpc("SlotFormation", "GetFormation", [], server_id=1, player_id=pid)
        self.assertEqual(fmt_get["Status"], 0)
        fmt_chg = self._rpc("SlotFormation", "Change", [2, 1, 0, 0, 0, 0], server_id=1, player_id=pid)
        self.assertEqual(fmt_chg["Value"]["SlotFormationInfo"]["Formation1"], 2)

    def test_03_debug_profile_regression_and_isolation(self) -> None:
        # Verify ServerId=2 keeps R1 quick-test profile (Lv 10, VIP 5, PlayerId 100001)
        login = self._rpc("Player", "Login", ["android", "12", 1234, "hash", "", "100001"], server_id=2, player_id="100001")
        self.assertEqual(login["Status"], 0)
        self.assertEqual(login["Value"]["PlayerId"], "100001")
        self.assertEqual(login["Value"]["IsNewPlayer"], 0)
        self.assertEqual(login["Value"]["Lv"], 10)
        self.assertEqual(login["Value"]["Vip"], 5)

        init_res = self._rpc("Player", "GetInitData", [1] * 20, server_id=2, player_id="100001")
        val = init_res["Value"]
        self.assertEqual(val["PlayerInfo"]["PlayerName"], "InuYasha")
        self.assertEqual(len(val["HeroInfo"]), 4)
        self.assertEqual(val["HeroInfo"][0]["HeroModelId"], 12011004)
        self.assertIn("APR1", val["SlotInfo"][0]["Property"])

        fight_info = self._rpc("Battle", "GetFightInfo", [11, 1111, 1], server_id=2, player_id="100001")
        self.assertEqual(fight_info["Status"], 0)
        heros = fight_info["Value"]["FightInfo"]["FightObjs"][0]["Heros"]
        self.assertEqual(len(heros), 12)
        self.assertEqual(heros[0]["LargePic"], "hero_quanyecha")
        self.assertTrue(heros[7]["IsBoss"])

        gold_before = fight_info["Avatar"]["Gold"]
        settle = self._rpc("Battle", "Fight", [11, 1111, 3, True, "", False], server_id=2, player_id="100001")
        self.assertEqual(settle["Status"], 0)
        self.assertEqual(settle["Value"]["IsSuccess"], "True")
        self.assertGreater(settle["Avatar"]["Gold"], gold_before)

        # Ensure NORMAL profile was NOT mutated by DEBUG profile actions
        normal_sync = self._rpc("Player", "SyncAvatarInfo", [], server_id=1, player_id="200001")
        self.assertEqual(normal_sync["Value"]["PlayerName"], "KagomeTest")
        self.assertEqual(normal_sync["Value"]["Vip"], 0)

    def test_04_economy_audit_ledger(self) -> None:
        vip_model = self.srv.emu.game_data.get("vip_model", {})
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            ledger = ResourceLedger(audit_log_path=audit_path, vip_model=vip_model)
            player = {"PlayerId": "200001", "Gold": 1000, "Diamond": 0, "VipEXP": 0, "Vip": 0, "VIPLv": 0}

            # Disallow combat stat tampering
            for bad_key in ("HP", "AP", "DEF", "DAM", "DAMADD"):
                with self.assertRaises(ResourceTransactionError):
                    ledger.apply_player_delta(player, "normal", bad_key, 100, source="bad_override")

            # Prevent negative overdraft
            with self.assertRaises(ResourceTransactionError):
                ledger.apply_player_delta(player, "normal", "Diamond", -10, source="spend_too_much")

            # Apply validated grant + idempotency dedupe
            tx1 = ledger.apply_player_delta(
                player, "normal", "Diamond", 500, source="admin_compensate", idempotency_key="tx-key-1"
            )
            self.assertIsNotNone(tx1)
            self.assertEqual(player["Diamond"], 500)
            with self.assertRaises(DuplicateTransactionError):
                ledger.apply_player_delta(
                    player, "normal", "Diamond", 500, source="admin_compensate", idempotency_key="tx-key-1"
                )
            self.assertEqual(player["Diamond"], 500)

            # VIP must derive strictly from VipEXP
            ledger.apply_player_delta(
                player, "normal", "VipEXP", 1000, source="charge_sim", idempotency_key="vip-1"
            )
            self.assertEqual(player["Vip"], ledger.derive_vip_level(1000))
            self.assertGreaterEqual(player["Vip"], 1)

            rows = ledger.list_transactions(account_id="200001")
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["tx_id"], tx1.tx_id)

    def test_05_real_apk_obb_assets_served(self) -> None:
        for path in [
            "/assets/res/ui/dl_21.jpg",
            "/assets/res/ui/smap01.jpg",
            "/assets/res/animation/hero_quanyecha.png",
            "/assets/res/music/music_login.mp3",
            "/api/atlas/hero_quanyecha",
            "/api/gamedata",
            "/poc/",
            "/health",
        ]:
            with urllib.request.urlopen(f"{self.base}{path}", timeout=5) as r:
                self.assertEqual(r.status, 200)
                body = r.read()
                self.assertGreater(len(body), 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
