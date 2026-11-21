#!/usr/bin/env python3
"""Automated end-to-end protocol, dual-profile, tutorial, ledger & asset tests for InuYasha: Seek Jade."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zlib
from pathlib import Path
from unittest.mock import patch

from economy_audit import DuplicateTransactionError, ResourceLedger, ResourceTransactionError
from emulator import GameEmulatorState, ThreadingEmulatorServer
import qa_runner


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

    def test_06_vn_config_extraction_and_combat_scaling(self) -> None:
        gd = self.srv.emu.game_data
        self.assertIn("com.cmn.inuyasha", gd["source"])
        self.assertEqual(gd["counts"]["heroes"], 204)
        self.assertEqual(gd["player_config"]["maxPlayerLV"], 80)
        self.assertEqual(gd["counts"]["hero_step"], 57)
        self.assertEqual(gd["counts"]["attrtree"], 1001)

        # Multi-wave stage 1217 (2-7, fightRound=2) returns 2 waves in FightObjs
        f_1217 = self._rpc("Battle", "GetFightInfo", [12, 1217, 1], server_id=1)
        self.assertEqual(f_1217["Status"], 0)
        self.assertEqual(len(f_1217["Value"]["FightInfo"]["FightObjs"]), 2)

        # Multi-star stage 2311 (starCount=3) scales enemy HP/AP/DEF strictly across 1★, 2★, 3★
        hp_by_star = []
        for star_lv in (1, 2, 3):
            fi = self._rpc("Battle", "GetFightInfo", [23, 2311, star_lv], server_id=1)
            self.assertEqual(fi["Status"], 0)
            enemies = [h for h in fi["Value"]["FightInfo"]["FightObjs"][0]["Heros"][6:] if h]
            self.assertGreaterEqual(len(enemies), 3)
            hp_by_star.append(sum(e["HP"] for e in enemies))
        self.assertLess(hp_by_star[0], hp_by_star[1])
        self.assertLess(hp_by_star[1], hp_by_star[2])

    def test_07_star_rating_replay_con_fight_and_draw_box(self) -> None:
        # Use isolated state in a fresh emulator instance to test Ch 11 & Ch 23 star persistence cleanly
        emu = GameEmulatorState(persist=False)
        prof = emu.profiles["normal"]
        pid = prof.state["player"]["PlayerId"]

        # Ch 11 nodes have starCount=1; winning at star_lv=3 clamps to 1★, IfDrawBoxA is False (bool)
        for nid in (1111, 1112, 1113, 1114):
            res = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, nid, 3, True, "", False]})
            self.assertEqual(res["Status"], 0)
            self.assertEqual(res["Value"]["CurrentNode"]["StarCount"], 1)
            self.assertIs(res["Value"]["CurrentChapter"]["IfDrawBoxA"], False)

        # DrawBox rejects before 5 stars
        fail_box = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawBox", "Data": [11, 111]})
        self.assertEqual(fail_box["Status"], -1)

        # Clear 1115 -> 5 stars total -> Ch 12 unlocked + DrawBox succeeds + ConFight works
        res_1115 = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1115, 1, True, "", False]})
        self.assertEqual(res_1115["Value"]["CurrentChapter"]["StarCount"], 5)
        self.assertIn("NextChapter", res_1115["Value"])

        ok_box = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawBox", "Data": [11, 111]})
        self.assertEqual(ok_box["Status"], 0)
        self.assertIs(ok_box["Value"]["Chapter"]["IfDrawBoxA"], True)
        # Double-claim blocked
        dup_box = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawBox", "Data": [11, 111]})
        self.assertEqual(dup_box["Status"], -1)

        # Contradictory verifyData rejected (won=True while ally HP=0 & enemy HP>0)
        bad_verify = json.dumps({"hp": [[{"PosId": 1, "HP": 0, "RP": 0}, {"PosId": 7, "HP": 100, "RP": 50}]]})
        bad_fight = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1115, 1, True, bad_verify, False]})
        self.assertEqual(bad_fight["Status"], -1)

        # 3-star node (2311, starCount=3): progressive 1★ -> 2★ -> 3★, and 1★ replay preserves 3★
        prof.state["chapters"]["23"] = prof._make_chapter_state(23)
        prof.state["nodes"]["2311"] = prof._make_node_state(2311, flag=1)
        r1 = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [23, 2311, 1, True, "", False]})
        self.assertEqual(r1["Value"]["CurrentNode"]["StarCount"], 1)
        r2 = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [23, 2311, 2, True, "", False]})
        self.assertEqual(r2["Value"]["CurrentNode"]["StarCount"], 2)
        r3 = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [23, 2311, 3, True, "", False]})
        self.assertEqual(r3["Value"]["CurrentNode"]["StarCount"], 3)
        r_replay = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [23, 2311, 1, True, "", False]})
        self.assertEqual(r_replay["Value"]["CurrentNode"]["StarCount"], 3)

        # ConFight 3x returns 3 reward bundles and deducts VIT
        vit_before = prof.state["player"]["VIT"]
        cf = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "ConFight", "Data": [23, 2311, 3, 3, 2]})
        self.assertEqual(cf["Status"], 0)
        self.assertEqual(len(cf["Value"]["BaseGetGameResourceList"]), 3)
        self.assertEqual(prof.state["player"]["VIT"], vit_before - 15)
        self.assertIsNotNone(pid)

    def test_08_hero_lv_up_step_up_explore_and_lighten_star_to_lv10(self) -> None:
        emu = GameEmulatorState(persist=False)
        prof = emu.profiles["normal"]
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["KagomeVN", 1]})

        # Recruit companion Ayame -> HeroLvUp 10x -> HeroStepUp Step 0 -> 1
        rec = prof.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 1]})
        self.assertEqual(rec["Status"], 0)
        ayame = rec["Value"]["BaseGetGameResourceList"][0]["Hero"][0]
        prof.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [2, ayame["Id"]]})

        fap_before = prof.state["player"]["FAP"]
        lv_res = prof.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [ayame["Id"], 10]})
        self.assertEqual(lv_res["Status"], 0)
        self.assertEqual(lv_res["Value"]["Lv"], 10)  # Capped at max(playerLv*2, 10)
        self.assertGreater(prof.state["player"]["FAP"], fap_before)

        # Play Ch 1 (5 stages) and Ch 2 to push Player Lv up + claim Ch 1 & Ch 2 boxes (for 120 pills & stars)
        for nid in (1111, 1112, 1113, 1114, 1115):
            prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, nid, 1, True, "", False]})
        prof.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawBox", "Data": [11, 111]})
        for nid in (1211, 1212, 1213, 1214, 1215, 1216, 1217):
            prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [12, nid, 1, True, "", False]})

        step_res = prof.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroStepUp", "Data": [ayame["Id"], []]})
        self.assertEqual(step_res["Status"], 0)
        self.assertEqual(step_res["Value"]["Step"], 1)
        for s in prof.state["slots"]:
            self.assertEqual(s.get("FAP"), int(s["Property"]["FAP"]))

        # LightenStar spends earned stars + gold and increases slot stats
        ls_info = prof.handle_rpc({"ModuleName": "LightenStar", "MethodName": "GetLightenStarInfo", "Data": []})
        self.assertGreaterEqual(ls_info["Value"]["StarCount"], 12)
        fap_pre_star = prof.state["player"]["FAP"]
        ls_up = prof.handle_rpc({"ModuleName": "LightenStar", "MethodName": "LightenStar", "Data": []})
        self.assertEqual(ls_up["Status"], 0)
        self.assertEqual(ls_up["Value"]["StarId"], 1)
        self.assertGreater(prof.state["player"]["FAP"], fap_pre_star)

        # Explore (Seek Jade) + Ch 3 pushes player to Lv >= 10 organically without hacks
        exp_info = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "GetInfo", "Data": []})
        self.assertGreater(exp_info["Value"]["RemainNum"], 15)
        exp_one = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "Explore", "Data": []})
        self.assertEqual(exp_one["Status"], 0)
        self.assertIn("RewardModelId", exp_one["Value"])

        for nid in (1311, 1312, 1313, 1314, 1315, 1316, 1317, 1318):
            prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [13, nid, 1, True, "", False]})
        prof.state["player"].update(Vip=3, VIPLv=3)
        self.assertEqual(prof.handle_rpc({"ModuleName": "Explore", "MethodName": "OneKeyExplore", "Data": []})["Status"], 0)
        self.assertGreaterEqual(prof.state["player"]["Lv"], 10)

    def test_09_battle_defeat_and_reward_idempotency_guards(self) -> None:
        emu = GameEmulatorState(persist=False)
        prof = emu.profiles["normal"]
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["GuardTester", 0]})
        self.assertEqual(prof.state["heroes"][0]["HeroModelId"], 12010001)  # Male starter

        # Defeat on 1-1: no VIT deducted, no rewards, Flag stays 1, StarCount stays 0, 1112 not unlocked
        p_before = dict(prof.state["player"])
        lose = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, False, "", False]})
        self.assertEqual(lose["Status"], 0)
        self.assertEqual(lose["Value"]["IsSuccess"], "False")
        self.assertEqual(lose["Value"]["CurrentNode"]["Flag"], 1)
        self.assertEqual(lose["Value"]["CurrentNode"]["StarCount"], 0)
        self.assertIsNone(lose["Value"]["NextNode"])
        self.assertEqual(lose["Value"]["BaseGetGameResourceList"], [])
        self.assertEqual(prof.state["player"]["VIT"], p_before["VIT"])
        self.assertEqual(prof.state["player"]["Gold"], p_before["Gold"])
        self.assertEqual(prof.state["player"]["EXP"], p_before["EXP"])
        self.assertNotIn("1112", prof.state["nodes"])

        # Contradictory defeat verifyData (ally alive & enemy dead with won=False) rejected
        bad_lose = json.dumps({"hp": [[{"PosId": 1, "HP": 120, "RP": 50}, {"PosId": 7, "HP": 0, "RP": 0}]]})
        bad_res = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, False, bad_lose, False]})
        self.assertEqual(bad_res["Status"], -1)

        # Tutorial step reward idempotency (-1136 on duplicate claim)
        step_ok = prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1602]})
        self.assertEqual(step_ok["Status"], 0)
        diamond_after = prof.state["player"]["Diamond"]
        self.assertEqual(diamond_after, 200)
        step_dup = prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1602]})
        self.assertEqual(step_dup["Status"], -1136)
        self.assertEqual(prof.state["player"]["Diamond"], diamond_after)

        # DrawRoadBox rejects before unlock, succeeds once, rejects duplicate claim (no duplicate equip!)
        early_rb = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawRoadBox", "Data": [11, 111]})
        self.assertEqual(early_rb["Status"], -1)
        prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, True, "", False]})
        prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1112, 1, True, "", False]})
        equips_before = len(prof.state["equips"])
        ok_rb = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawRoadBox", "Data": [11, 111]})
        self.assertEqual(ok_rb["Status"], 0)
        self.assertEqual(len(prof.state["equips"]), equips_before + 1)
        dup_rb = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawRoadBox", "Data": [11, 111]})
        self.assertEqual(dup_rb["Status"], -1)
        self.assertEqual(len(prof.state["equips"]), equips_before + 1)

        # OneKeyDrawBoxs claims unlocked chapter boxes once; repeating grants nothing extra
        for nid in (1113, 1114, 1115):
            prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, nid, 1, True, "", False]})
        ok_onekey = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "OneKeyDrawBoxs", "Data": [11, {"1": [111]}]})
        self.assertEqual(ok_onekey["Status"], 0)
        self.assertTrue(ok_onekey["Value"]["BaseGetGameResourceList"])
        gold_after_box = prof.state["player"]["Gold"]
        dup_onekey = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "OneKeyDrawBoxs", "Data": [11, {"1": [111]}]})
        self.assertEqual(dup_onekey["Status"], 0)
        self.assertEqual(dup_onekey["Value"]["BaseGetGameResourceList"], [])
        self.assertEqual(prof.state["player"]["Gold"], gold_after_box)

        # ResetCount clears FightCount and increments ResetFightCount
        rc = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "ResetCount", "Data": [11, 1111]})
        self.assertEqual(rc["Status"], 0)
        self.assertEqual(rc["Value"]["FightCount"], 0)
        self.assertEqual(rc["Value"]["ResetFightCount"], 1)

    def test_10_recruit_equip_set_and_explore_subflows(self) -> None:
        emu = GameEmulatorState(persist=False)
        prof = emu.profiles["normal"]
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["EquipExplore", 1]})

        # Recruit type 1 consumes talisman 16050003 (initResource has 1) and rejects when 0 remain
        r_info = prof.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "RecruitInfo", "Data": []})
        self.assertEqual(r_info["Status"], 0)
        r_tal = prof.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [1, 0]})
        self.assertEqual(r_tal["Status"], 0)
        r_tal_empty = prof.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [1, 0]})
        self.assertEqual(r_tal_empty["Status"], -1)

        # Grant diamonds via step reward 1602 (200) + paid Recruit type 2 (64 while 4417 is active)
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1602]})
        r_paid = prof.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 0]})
        self.assertEqual(r_paid["Status"], 0)
        self.assertEqual(prof.state["player"]["Diamond"], 136)  # VN 4417: 200 - ceil(80 * 80%).

        # EquipCompose (explicit 5 white -> 1 green), EquipLvUpForCount, and set bonus verification
        prof._grant_resources_from_tuples(
            [(1304, 13040130, 5), (1301, 13010215, 1), (1302, 13020215, 1), (1303, 13030215, 1)],
            source="test_seed",
            tx_prefix="test10:seed",
        )
        white_ids = [e["Id"] for e in prof.state["equips"] if e["EquipModelId"] == 13040130][:5]
        comp = prof.handle_rpc({"ModuleName": "Equip", "MethodName": "EquipCompose", "Data": [white_ids]})
        self.assertEqual(comp["Status"], 0)
        green_neck = comp["Value"]["BaseGetGameResourceList"][0]["Equip"][0]
        self.assertEqual(green_neck["EquipModelId"], 13040215)

        lv_cnt = prof.handle_rpc({"ModuleName": "Equip", "MethodName": "EquipLvUpForCount", "Data": [green_neck["Id"], 2]})
        self.assertEqual(lv_cnt["Status"], 0)
        self.assertEqual(lv_cnt["Value"]["EquipInfo"]["Lv"], 2)

        # Equip 2 -> 4 pieces of Set Out (equipGroupID > 0) and confirm FAP strictly increases
        w_id = next(e["Id"] for e in prof.state["equips"] if e["EquipModelId"] == 13010215)
        h_id = next(e["Id"] for e in prof.state["equips"] if e["EquipModelId"] == 13020215)
        c_id = next(e["Id"] for e in prof.state["equips"] if e["EquipModelId"] == 13030215)
        prof.handle_rpc({"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [1, w_id, h_id, "", "", "", ""]})
        fap_2pc = prof.state["slots"][0]["FAP"]
        prof.handle_rpc({"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [1, "", "", c_id, green_neck["Id"], "", ""]})
        fap_4pc = prof.state["slots"][0]["FAP"]
        self.assertGreater(fap_4pc, fap_2pc)

        # VN only offers a purchase at zero. The first purchase grants ten turns for 50 diamonds.
        prof.state["player"].update(Vip=3, VIPLv=3)
        prof.state["explore"]["RemainNum"] = 0
        exp_buy = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "BuyExploreNum", "Data": []})
        self.assertEqual(exp_buy["Status"], 0)
        self.assertEqual(exp_buy["Value"]["ResetNum"], 1)
        self.assertEqual(exp_buy["Value"]["RemainNum"], 10)
        self.assertEqual(prof.state["player"]["Diamond"], 86)

        early_daily = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "DrawDailyReward", "Data": [50]})
        self.assertEqual(early_daily["Status"], -5104)
        while prof.state["explore"]["DailyNum"] < 50:
            if prof.state["explore"]["RemainNum"] <= 0:
                prof.state["explore"]["RemainNum"] = 10
            self.assertEqual(prof.handle_rpc({"ModuleName": "Explore", "MethodName": "OneKeyExplore", "Data": []})["Status"], 0)
        ok_daily = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "DrawDailyReward", "Data": [50]})
        self.assertEqual(ok_daily["Status"], 0)
        dup_daily = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "DrawDailyReward", "Data": [50]})
        self.assertEqual(dup_daily["Status"], -7003)

    def test_11_isolated_save_reload_and_r3_trace_replay(self) -> None:
        # Ensure tests NEVER mutate real server/saves/* or server/rpc_trace.log
        server_dir = Path(__file__).resolve().parent
        real_files = [
            server_dir / "saves" / "normal_profile.json",
            server_dir / "saves" / "debug_profile.json",
            server_dir / "saves" / "audit_ledger.jsonl",
            server_dir / "rpc_trace.log",
        ]
        before_stats = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in real_files if p.exists()}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            normal_p = tmp_dir / "normal_profile.json"
            debug_p = tmp_dir / "debug_profile.json"
            audit_p = tmp_dir / "audit_ledger.jsonl"
            trace_p = tmp_dir / "rpc_trace.log"

            emu1 = GameEmulatorState(
                persist=True,
                normal_path=normal_p,
                debug_path=debug_p,
                audit_path=audit_p,
                trace_path=trace_p,
            )
            # Replay core R3 progression flow up to Lv 10+
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Player", "MethodName": "Login", "Data": []})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["OlinaReplay", 1]})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Player", "MethodName": "GetInitData", "Data": [1] * 20})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Player", "MethodName": "AlterPlayerStepCount", "Data": [1, 997]})
            emu1.handle_rpc(
                {
                    "ServerId": 1,
                    "ModuleName": "Battle",
                    "MethodName": "Fight",
                    "Data": [11, 1111, 1, True, "", False],
                    "ExtensionString": {"GuideInfo": [{"GuideId": 951, "Ordinal": 3}]},
                }
            )
            rec = emu1.handle_rpc({"ServerId": 1, "ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 1]})
            ayame_id = rec["Value"]["BaseGetGameResourceList"][0]["Hero"][0]["Id"]
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [2, ayame_id]})
            for nid in (1112, 1113, 1114, 1115):
                emu1.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "Fight", "Data": [11, nid, 1, True, "", False]})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "DrawRoadBox", "Data": [11, 111]})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "DrawBox", "Data": [11, 111]})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Equip", "MethodName": "EquipOneKeyCompose", "Data": []})
            for nid in (1211, 1212, 1213, 1214, 1215, 1216, 1217):
                emu1.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "Fight", "Data": [12, nid, 1, True, "", False]})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "OneKeyDrawBoxs", "Data": [12, {"1": [121, 122], "2": [121, 122]}]})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [ayame_id, 10]})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Hero", "MethodName": "HeroStepUp", "Data": [ayame_id, []]})
            emu1.handle_rpc({"ServerId": 1, "ModuleName": "Explore", "MethodName": "Explore", "Data": []})
            for nid in (1311, 1312, 1313, 1314):
                emu1.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "Fight", "Data": [13, nid, 1, True, "", False]})

            snap = json.loads(json.dumps(emu1.profiles["normal"].state))
            self.assertGreaterEqual(snap["player"]["Lv"], 9)
            self.assertTrue(normal_p.exists())
            self.assertTrue(trace_p.exists())

            # Reload from disk into a fresh GameEmulatorState (simulating server restart)
            emu2 = GameEmulatorState(
                persist=True,
                normal_path=normal_p,
                debug_path=debug_p,
                audit_path=audit_p,
                trace_path=trace_p,
            )
            reloaded_login = emu2.handle_rpc({"ServerId": 1, "ModuleName": "Player", "MethodName": "Login", "Data": []})
            self.assertEqual(reloaded_login["Value"]["IsNewPlayer"], 0)
            self.assertEqual(reloaded_login["Value"]["PlayerName"], "OlinaReplay")
            self.assertEqual(reloaded_login["Value"]["StepCountList"], snap["player"]["StepCountList"])
            self.assertEqual(reloaded_login["Value"]["Gold"], snap["player"]["Gold"])
            self.assertEqual(reloaded_login["Value"]["Diamond"], snap["player"]["Diamond"])

            b_info = emu2.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "GetBattleInfo", "Data": [1, 1]})
            self.assertEqual(b_info["Value"]["BattleInfo"]["StarCount"], snap["battle"]["StarCount"])

            # Already-claimed rewards remain blocked after restart
            self.assertEqual(
                emu2.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "DrawBox", "Data": [11, 111]})["Status"],
                -1,
            )
            self.assertEqual(
                emu2.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "DrawRoadBox", "Data": [11, 111]})["Status"],
                -1,
            )

        # Verify R3 checkpoint backup save loads cleanly without mutation
        r3_backup = server_dir / "backups" / "vn_r3_stable_checkpoint" / "normal_profile.json"
        if r3_backup.exists():
            r3_data = json.loads(r3_backup.read_text(encoding="utf-8"))
            norm = emu1.profiles["normal"]._normalize_loaded_state(r3_data)
            self.assertEqual(norm["player"]["Lv"], 10)
            self.assertEqual(norm["battle"]["MaxChapterId"], 13)

        after_stats = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in real_files if p.exists()}
        self.assertEqual(before_stats, after_stats)

    def test_12_all_chapter_info_shop_goods_and_goods_use(self) -> None:
        emu = GameEmulatorState(persist=False)
        prof = emu.profiles["normal"]
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["ShopTester", 1]})
        for nid in (1111, 1112, 1113, 1114, 1115):
            prof.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, nid, 1, True, "", False]})

        # Battle.AllChapterInfo returns NodeList per requested chapter
        all_ch = prof.handle_rpc({"ModuleName": "Battle", "MethodName": "AllChapterInfo", "Data": [[11, 12]]})
        self.assertEqual(all_ch["Status"], 0)
        self.assertEqual([c["ChapterModelId"] for c in all_ch["Value"]], [11, 12])
        self.assertEqual(len(all_ch["Value"][0]["NodeList"]), 5)
        self.assertEqual([n["NodeModelId"] for n in all_ch["Value"][1]["NodeList"]], [1211])

        # ShopGoods.GetShopGoodsInfo & dynamic pricing BuyGoods (16030006 -> 20, 20, 30)
        info0 = prof.handle_rpc({"ModuleName": "ShopGoods", "MethodName": "GetShopGoodsInfo", "Data": [16030006]})
        self.assertEqual(info0["Status"], 0)
        self.assertEqual(info0["Value"][0]["CurrPrice"], 20)
        self.assertEqual(info0["Value"][0]["Num"], 0)

        prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1602]})  # +200 Diamond
        b1 = prof.handle_rpc({"ModuleName": "ShopGoods", "MethodName": "BuyGoods", "Data": [16030006, 2]})
        self.assertEqual(b1["Status"], 0)
        self.assertEqual(b1["Value"]["Num"], 2)
        self.assertEqual(b1["Value"]["CurrPrice"], 30)
        self.assertEqual(prof.state["player"]["Diamond"], 160)
        self.assertIn("GoodsInfo", b1["Avatar"])

        # Goods.GoodsUse consumes 1x 16030006 and grants +25 VIT
        vit_before = prof.state["player"]["VIT"]
        pill = next(g for g in prof.state["goods"] if g["GoodsModelId"] == 16030006)
        used = prof.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsUse", "Data": [pill["Id"], 16030006, 1]})
        self.assertEqual(used["Status"], 0)
        self.assertEqual(prof.state["player"]["VIT"], vit_before + 25)
        self.assertIn("GoodsInfo", used["Avatar"])

    def test_13_treasure_loot_compose_and_slot_equip(self) -> None:
        emu = GameEmulatorState(persist=False)
        prof = emu.profiles["normal"]
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["GrabTester", 1]})

        # StepCountReward 1761 grants 2 starter mount debris (15040101, 15040102) and blocks duplicate claim
        r1761 = prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1761]})
        self.assertEqual(r1761["Status"], 0)
        debris_ids = sorted(d["TreasureDebrisModelId"] for d in prof.state["treasure_debris"])
        self.assertEqual(debris_ids, [15040101, 15040102])
        self.assertEqual(set(r1761["Avatar"]["TreasureDebrisInfo"].keys()), {"15040101", "15040102"})
        r1761_dup = prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1761]})
        self.assertEqual(r1761_dup["Status"], -1136)

        # TreasureLootProtect info + buy via diamond
        prot0 = prof.handle_rpc({"ModuleName": "TreasureLootProtect", "MethodName": "GetTreasureLootProtectInfo", "Data": []})
        self.assertEqual(prot0["Status"], 0)
        self.assertEqual(prot0["Value"]["EndTime"], 0)
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1602]})  # +200 Diamond
        prot1 = prof.handle_rpc({"ModuleName": "TreasureLootProtect", "MethodName": "TreasureLootProtect", "Data": [2]})
        self.assertEqual(prot1["Status"], 0)
        self.assertGreater(prot1["Value"]["EndTime"], 0)
        self.assertEqual(prof.state["player"]["Diamond"], 180)  # 200 - 20

        # Target list + single loot for missing fragment 15040103
        tlist = prof.handle_rpc({"ModuleName": "TreasureLoot", "MethodName": "TreasureDebrisTargetList", "Data": [14020501, 15040103]})
        self.assertEqual(tlist["Status"], 0)
        targets = tlist["Value"]["TreasureLootTeamInfo"]
        self.assertGreaterEqual(len(targets), 3)

        sta_before = prof.state["player"]["STA"]
        loot = prof.handle_rpc(
            {"ModuleName": "TreasureLoot", "MethodName": "TreasureLoot", "Data": [targets[0]["LootPlayerId"], 14020501, 15040103]}
        )
        self.assertEqual(loot["Status"], 0)
        self.assertEqual(loot["Value"]["IfTargetCanLoot"], 1)
        self.assertEqual(loot["Value"]["IsWinFight"], 1)
        self.assertEqual(loot["Value"]["FightInfo"]["IsWinFight"], 1)
        self.assertEqual(loot["Value"]["IsWinLootSuccess"], 1)
        self.assertEqual(len(loot["Value"]["ChoiceGetGameResource"]), 3)
        self.assertEqual(prof.state["player"]["STA"], sta_before - 2)
        self.assertIn("15040103", loot["Avatar"]["TreasureDebrisInfo"])

        # Compose 14020501 (consumes 3 fragments, returns Treasure instance, idempotent against double compose)
        comp = prof.handle_rpc({"ModuleName": "TreasureDebris", "MethodName": "TreasureDebrisCompose", "Data": [14020501]})
        self.assertEqual(comp["Status"], 0)
        tr_inst = comp["Value"]["BaseGetGameResourceList"][0]["Treasure"][0]
        self.assertEqual(tr_inst["TreasureModelId"], 14020501)
        self.assertEqual(prof.state["treasure_debris"], [])
        comp_dup = prof.handle_rpc({"ModuleName": "TreasureDebris", "MethodName": "TreasureDebrisCompose", "Data": [14020501]})
        self.assertEqual(comp_dup["Value"].get("IsTreasureDebrisNotEnough"), 0)

        # Equip composed Horse on Slot 1 and confirm AP + FAP increase
        fap_before = prof.state["slots"][0]["FAP"]
        ap_before = prof.state["slots"][0]["Property"]["AP"]
        eq_res = prof.handle_rpc(
            {"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [1, "", "", "", "", "", tr_inst["Id"]]}
        )
        self.assertEqual(eq_res["Status"], 0)
        self.assertEqual(prof.state["slots"][0]["Horse"]["TreasureModelId"], 14020501)
        self.assertEqual(prof.state["slots"][0]["Property"]["AP"], ap_before + 20)
        self.assertEqual(prof.state["slots"][0]["FAP"], fap_before + 100)

        # GetInitData persists composed treasure
        init_res = prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [1] * 20})
        self.assertEqual(len(init_res["Value"]["TreasureInfo"]), 1)
        self.assertEqual(init_res["Value"]["TreasureInfo"][0]["Id"], tr_inst["Id"])

    def test_14_elite_battle_and_goods_delta_drop(self) -> None:
        emu = GameEmulatorState(persist=False)
        prof = emu.profiles["normal"]
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["EliteTester", 1]})

        # Stacked Goods grants return delta Num in BaseGetGameResourceList and total stack in Avatar.GoodsInfo
        start_stone = next((g["Num"] for g in prof.state["goods"] if g["GoodsModelId"] == 16050001), 0)
        drop1 = prof._grant_resources_from_tuples([(1605, 16050001, 2)], source="t14:1", tx_prefix="t14:1")
        drop2 = prof._grant_resources_from_tuples([(1605, 16050001, 3)], source="t14:2", tx_prefix="t14:2")
        self.assertEqual(drop1[0]["Goods"][0]["Num"], 2)
        self.assertEqual(drop2[0]["Goods"][0]["Num"], 3)
        bag_stone = next(g for g in prof.state["goods"] if g["GoodsModelId"] == 16050001)
        self.assertEqual(bag_stone["Num"], start_stone + 5)

        # Locked before Ch 2 (1217) is cleared; unlocks once 1217 Flag == 2
        info0 = prof.handle_rpc({"ModuleName": "EliteBattle", "MethodName": "GetBattleInfo", "Data": [1, 1]})
        self.assertEqual(info0["Status"], 0)
        self.assertEqual(info0["Value"]["NodeList"][0]["Flag"], 0)

        prof.state["nodes"]["1217"] = prof._make_node_state(1217, flag=2)
        info1 = prof.handle_rpc({"ModuleName": "EliteBattle", "MethodName": "GetBattleInfo", "Data": [1, 1]})
        self.assertEqual(info1["Value"]["BattleInfo"]["FightCount"], 3)
        self.assertEqual(info1["Value"]["NodeList"][0]["Flag"], 1)
        self.assertEqual(info1["Value"]["NodeList"][0]["CanDraw"], "False")

        # GetFightInfo + Fight deducts 10 VIT, decrements FightCount, omits BossId when no Boss spawned
        finfo = prof.handle_rpc({"ModuleName": "EliteBattle", "MethodName": "GetFightInfo", "Data": [11]})
        self.assertEqual(finfo["Status"], 0)
        self.assertIn("FightObjs", finfo["Value"]["FightInfo"])

        vit_before = prof.state["player"]["VIT"]
        efight = prof.handle_rpc({"ModuleName": "EliteBattle", "MethodName": "Fight", "Data": [11, True, "", False]})
        self.assertEqual(efight["Status"], 0)
        self.assertEqual(efight["Value"]["IsSuccess"], "True")
        self.assertNotIn("BossId", efight["Value"])
        self.assertEqual(efight["Value"]["CurrentNode"]["Flag"], 2)
        self.assertEqual(efight["Value"]["CurrentNode"]["CanDraw"], "True")
        self.assertEqual(prof.state["player"]["VIT"], vit_before - 10)
        self.assertEqual(efight["Value"]["BattleInfo"]["FightCount"], 2)

        # DrawFirstReward grants reward once and blocks duplicate claim
        first = prof.handle_rpc({"ModuleName": "EliteBattle", "MethodName": "DrawFirstReward", "Data": [11]})
        self.assertEqual(first["Status"], 0)
        self.assertEqual(first["Value"]["NodeInfo"]["CanDraw"], "False")
        self.assertEqual(prof.state["player"]["Diamond"], 100)
        first_dup = prof.handle_rpc({"ModuleName": "EliteBattle", "MethodName": "DrawFirstReward", "Data": [11]})
        self.assertEqual(first_dup["Status"], -1)

        # BuyFightCount spends 50 Diamond and increments BuyCount
        buy = prof.handle_rpc({"ModuleName": "EliteBattle", "MethodName": "BuyFightCount", "Data": [3]})
        self.assertEqual(buy["Status"], 0)
        self.assertEqual(buy["Value"]["BattleInfo"]["BuyCount"], 1)
        self.assertEqual(prof.state["player"]["Diamond"], 50)

    def test_15_role_info_recover_times_and_extra_activity_schemas(self) -> None:
        emu = GameEmulatorState(persist=False)
        prof = emu.profiles["normal"]
        login = prof.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": []})
        self.assertEqual(login["Status"], 0)
        self.assertIsInstance(login["Value"].get("VITNextRecoverTime"), int)
        self.assertIsInstance(login["Value"].get("STANextRecoverTime"), int)

        init_res = prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": []})
        pinfo = init_res["Value"]["PlayerInfo"]
        self.assertIsInstance(pinfo.get("VITNextRecoverTime"), int)
        self.assertIsInstance(pinfo.get("STANextRecoverTime"), int)

        # LevelPlanLayer.lua expects CanRewardLvList & RewardLvList tables, never nil
        lvp = prof.handle_rpc({"ModuleName": "LvPlan", "MethodName": "GetLvPlanInfo", "Data": []})
        self.assertEqual(lvp["Status"], 0)
        self.assertIsInstance(lvp["Value"].get("CanRewardLvList"), list)
        self.assertIsInstance(lvp["Value"].get("RewardLvList"), list)

        # VipWelfareLayer.lua expects CanDraw + ResourceList + Ctrl.showRewardList BaseGetGameResourceList
        vw = prof.handle_rpc({"ModuleName": "VipWelfare", "MethodName": "GetVipWelfare", "Data": []})
        self.assertTrue(vw["Value"]["CanDraw"])
        self.assertGreater(len(vw["Value"]["ResourceList"]), 0)
        self.assertIn("ResourceTypeSub", vw["Value"]["ResourceList"][0])

        draw = prof.handle_rpc({"ModuleName": "VipWelfare", "MethodName": "DrawVipWelfare", "Data": []})
        self.assertEqual(draw["Status"], 0)
        self.assertGreater(len(draw["Value"].get("BaseGetGameResourceList", [])), 0)
        vw2 = prof.handle_rpc({"ModuleName": "VipWelfare", "MethodName": "GetVipWelfare", "Data": []})
        self.assertFalse(vw2["Value"]["CanDraw"])
        draw2 = prof.handle_rpc({"ModuleName": "VipWelfare", "MethodName": "DrawVipWelfare", "Data": []})
        self.assertEqual(draw2["Status"], -1)

        # MonthSignInfo returns list (never {}) so table.sort succeeds
        ms = prof.handle_rpc({"ModuleName": "MonthSignInfo", "MethodName": "GetInfo", "Data": []})
        self.assertIsInstance(ms["Value"], list)

    def test_16_simulated_charge_card_and_admin_api_auth_audit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "dev_data"
            srv = ThreadingEmulatorServer(
                ("127.0.0.1", 0),
                persist=True,
                quiet=True,
                env="dev",
                data_dir=data_dir,
                trace_path=Path(td) / "dev_trace.log",
                admin_token="secret-qa-token",
            )
            port = srv.server_address[1]
            base = f"http://127.0.0.1:{port}"
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            try:
                def call_admin(method: str, path: str, body: dict | None = None, token: str | None = None):
                    headers = {"X-Plain-Json": "1"}
                    if token is not None:
                        headers["X-Admin-Token"] = token
                    raw = json.dumps(body).encode("utf-8") if body is not None else None
                    if raw is not None:
                        headers["Content-Type"] = "application/json"
                    req = urllib.request.Request(f"{base}{path}", data=raw, headers=headers, method=method)
                    try:
                        with urllib.request.urlopen(req, timeout=5) as r:
                            return r.status, json.loads(r.read().decode("utf-8"))
                    except urllib.error.HTTPError as e:
                        return e.code, json.loads(e.read().decode("utf-8") or "{}")

                # Unauthenticated / wrong token must return 401
                st, _ = call_admin("GET", "/admin/state?profile=normal")
                self.assertEqual(st, 401)
                st, _ = call_admin("POST", "/admin/vip", {"profile": "normal", "vip_lv": 3}, token="wrong")
                self.assertEqual(st, 401)

                # Invalid resource / hero ID must fail validation cleanly with 400
                st, _ = call_admin(
                    "POST",
                    "/admin/grant",
                    {"profile": "normal", "resources": [{"type": "FakeCurrency", "amount": 100}]},
                    token="secret-qa-token",
                )
                self.assertEqual(st, 400)
                st, _ = call_admin(
                    "POST",
                    "/admin/grant",
                    {"profile": "normal", "heroes": [{"model_id": 99999999, "lv": 1}]},
                    token="secret-qa-token",
                )
                self.assertEqual(st, 400)

                # Prepare Lv 15, grant valid hero/equip, set VIP 3 -> verified via audit log
                st, prep = call_admin(
                    "POST", "/admin/prepare", {"profile": "normal", "target_lv": 15}, token="secret-qa-token"
                )
                self.assertEqual(st, 200)
                self.assertEqual(prep["player"]["Lv"], 15)

                st, vip_res = call_admin(
                    "POST", "/admin/vip", {"profile": "normal", "vip_lv": 3}, token="secret-qa-token"
                )
                self.assertEqual(st, 200)
                self.assertEqual(vip_res["Vip"], 3)
                self.assertEqual(vip_res["VipEXP"], 860)

                st, grant_res = call_admin(
                    "POST",
                    "/admin/grant",
                    {
                        "profile": "normal",
                        "resources": [{"type": "Diamond", "amount": 500}],
                        "heroes": [{"model_id": 12011004, "lv": 15, "step": 1, "deploy": True}],
                        "equips": [{"model_id": 13010404, "lv": 10, "slot_id": 1}],
                    },
                    token="secret-qa-token",
                )
                self.assertEqual(st, 200)
                self.assertGreaterEqual(grant_res["summary"]["counts"]["heroes"], 2)

                st, audit = call_admin("GET", "/admin/audit?limit=50", token="secret-qa-token")
                self.assertEqual(st, 200)
                sources = {tx["source"] for tx in audit["transactions"]}
                self.assertIn("admin_prepare", sources)
                self.assertIn("admin_vip", sources)
                self.assertIn("admin_grant", sources)

                # Simulated store charge + first-charge box + CardInfo monthly card
                prof = srv.emu.profiles["normal"]
                clist = prof.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "GetChargeList", "Data": []})
                self.assertGreaterEqual(len(clist["Value"]), 3)
                ord_res = prof.handle_rpc(
                    {"ModuleName": "PlayerCharge", "MethodName": "GenerateOrderID", "Data": ["com.cmn.inuyasha.gem300"]}
                )
                self.assertTrue(str(ord_res["Value"]).startswith("ORD-"))
                conf = prof.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "ConfirmOrder", "Data": [300]})
                self.assertEqual(conf["Value"]["DiamondAdded"], 600)  # First recharge 2x
                box = prof.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "DrawChargeBox", "Data": [60]})
                self.assertEqual(box["Status"], 0)
                self.assertGreater(len(box["Value"]["BaseGetGameResourceList"]), 0)

                card_act = prof.handle_rpc({"ModuleName": "CardInfo", "MethodName": "Activity", "Data": [1]})
                self.assertEqual(len(card_act["Value"]), 1)
                self.assertTrue(card_act["Value"][0]["CanDrawBuyReward"])
                daily = prof.handle_rpc({"ModuleName": "CardInfo", "MethodName": "DrawDailyReward", "Data": [1]})
                self.assertEqual(daily["Status"], 0)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_17_stable_dev_env_isolation_and_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            stable_dir = Path(td) / "stable"
            dev_dir = Path(td) / "dev"
            stable_trace = Path(td) / "stable.log"
            dev_trace = Path(td) / "dev.log"
            emu_s = GameEmulatorState(persist=True, env="stable", data_dir=stable_dir, trace_path=stable_trace)
            emu_d = GameEmulatorState(persist=True, env="dev", data_dir=dev_dir, trace_path=dev_trace)
            emu_d.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": [], "ServerId": 1})
            self.assertTrue(dev_trace.exists())
            self.assertFalse(stable_trace.exists())
            self.assertEqual(emu_s.profiles["normal"].state["player"]["Lv"], 1)

    def test_18_fast_qa_presets_progression_and_failure_no_rigging(self) -> None:
        # Must refuse STABLE saves or port 8080
        with self.assertRaises(qa_runner.SafetyViolationError):
            qa_runner.QABackendClient(url="http://127.0.0.1:8080")
        with self.assertRaises(qa_runner.SafetyViolationError):
            qa_runner.QABackendClient(data_dir=Path(__file__).resolve().parent / "saves")

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # STARTER organic progression for 5 stages
            c_start = qa_runner.QABackendClient(data_dir=base / "starter", persist=True, new_player=True)
            res_s = qa_runner.run_progression_qa(c_start, preset="STARTER", max_stages=5, star_lv=2)
            self.assertEqual(res_s["stages_won"], 5)
            self.assertGreaterEqual(res_s["final_summary"]["player"]["Lv"], 5)

            # PROGRESSION & STRONG presets apply real heroes/equips/VIP
            c_prog = qa_runner.QABackendClient(data_dir=base / "prog", persist=True, new_player=True)
            res_p = qa_runner.run_progression_qa(c_prog, preset="PROGRESSION", target_lv=12, max_stages=2, star_lv=2)
            self.assertEqual(res_p["stages_won"], 2)
            self.assertGreaterEqual(res_p["final_summary"]["counts"]["deployed_slots"], 4)

            c_str = qa_runner.QABackendClient(data_dir=base / "strong", persist=True, new_player=True)
            res_st = qa_runner.run_progression_qa(c_str, preset="STRONG", target_lv=18, max_stages=2, star_lv=2)
            self.assertEqual(res_st["stages_won"], 2)
            self.assertGreaterEqual(res_st["final_summary"]["player"]["Vip"], 5)

            # FAILURE preset vs hard Ch 16 boss MUST genuinely lose (0 rigged victories)
            c_fail = qa_runner.QABackendClient(data_dir=base / "fail", persist=True, new_player=True)
            res_f = qa_runner.run_progression_qa(c_fail, preset="FAILURE", target_node=1620, max_stages=1, star_lv=3)
            self.assertEqual(res_f["stop_reason"], "battle_defeat")
            self.assertEqual(res_f["stages_won"], 0)
            self.assertEqual(res_f["final_summary"]["battle"]["StarCount"], 0)

    def test_19_concurrent_rpc_and_atomic_save_persistence(self) -> None:
        import env_ctl

        self.assertIn("stable", env_ctl.ENV_DAEMON_CONFIG)
        self.assertEqual(env_ctl.ENV_DAEMON_CONFIG["stable"]["port"], 8080)
        self.assertEqual(env_ctl.ENV_DAEMON_CONFIG["dev"]["port"], 8082)

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "concurrent_saves"
            srv = ThreadingEmulatorServer(
                ("127.0.0.1", 0),
                persist=True,
                quiet=True,
                env="dev",
                data_dir=data_dir,
                trace_path=Path(td) / "trace.log",
                admin_token="conc-token",
            )
            port = srv.server_address[1]
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            errors: list[str] = []

            def worker(idx: int) -> None:
                try:
                    for j in range(6):
                        mod, met = ("Player", "AvatarInfo") if (idx + j) % 2 == 0 else ("Battle", "GetBattleInfo")
                        payload = json.dumps({"ModuleName": mod, "MethodName": met, "Data": [], "ServerId": 1}).encode("utf-8")
                        req = urllib.request.Request(
                            f"http://127.0.0.1:{port}/client.aspx",
                            data=payload,
                            headers={"Content-Type": "application/json", "X-Plain-Json": "1"},
                            method="POST",
                        )
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            body = json.loads(resp.read().decode("utf-8"))
                            if body.get("Status") != 0:
                                errors.append(f"non-zero status: {body}")
                except Exception as exc:
                    errors.append(repr(exc))

            try:
                workers = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
                for w in workers:
                    w.start()
                for w in workers:
                    w.join(timeout=10)
                srv.emu.profiles["normal"].save()
                self.assertEqual(errors, [])
                tmp_files = list(data_dir.glob("*.tmp*"))
                self.assertEqual(tmp_files, [])
                reloaded = json.loads((data_dir / "normal_profile.json").read_text(encoding="utf-8"))
                self.assertEqual(reloaded["player"]["PlayerId"], "200001")
            finally:
                srv.shutdown()
                srv.server_close()

    def test_20_boss_battle_spawn_combat_rewards_boxes_buy_and_reload(self) -> None:
        from combat_sim import simulate_fight_info
        import qa_runner

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            c_qa = qa_runner.QABackendClient(data_dir=data_dir, persist=True, new_player=True)
            emu = c_qa.emu
            assert emu is not None
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": [], "ServerId": 1})
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["BossTester", 1], "ServerId": 1})

            # Below Lv 18: battles and elites must NOT trigger BossBattle
            qa_runner.apply_preset(c_qa, "PROGRESSION", target_lv=17)
            fi17 = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [11, 1111, 1], "ServerId": 1})
            c17 = simulate_fight_info(fi17["Value"]["FightInfo"], emu.game_data["attacks"])
            b17 = emu.handle_rpc(
                {"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, c17.won, json.dumps(c17.verify_data)], "ServerId": 1}
            )
            self.assertNotIn("BossId", b17["Value"])
            bl17 = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetBossList", "Data": [], "ServerId": 1})
            self.assertEqual(bl17["Value"]["BossList"], [])

            # Upgrade to Lv 18 QA preset -> trigger Boss on victory
            qa_runner.apply_preset(c_qa, "QA_LV18")
            fi18 = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [11, 1111, 1], "ServerId": 1})
            c18 = simulate_fight_info(fi18["Value"]["FightInfo"], emu.game_data["attacks"])
            b18 = emu.handle_rpc(
                {"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, c18.won, json.dumps(c18.verify_data)], "ServerId": 1}
            )
            boss_id = b18["Value"].get("BossId")
            self.assertIsInstance(boss_id, str)
            self.assertEqual(len(boss_id), 36)

            bl = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetBossList", "Data": [], "ServerId": 1})
            self.assertEqual(bl["Status"], 0)
            self.assertEqual(len(bl["Value"]["BossList"]), 1)
            self.assertEqual(bl["Avatar"]["RedDotInfo"]["2203"], 1)
            boss_item = bl["Value"]["BossList"][0]
            self.assertEqual(boss_item["CurHP"], boss_item["TotalHP"])

            # BossInfo + FriendHelp
            binfo = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetBossInfo", "Data": [boss_id], "ServerId": 1})
            self.assertEqual(binfo["Status"], 0)
            fhelp = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "FriendHelp", "Data": [boss_id], "ServerId": 1})
            self.assertGreater(fhelp["Value"]["CanHelpTime"], 0)

            # Normal attack + optional All-Out Attack until killed
            vit_before = emu.profiles["normal"].state["player"]["VIT"]
            bfi = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetFightInfo", "Data": [boss_id, 0], "ServerId": 1})
            self.assertEqual(bfi["Status"], 0)
            bc = simulate_fight_info(bfi["Value"]["FightInfo"], emu.game_data["attacks"])
            bf = emu.handle_rpc(
                {"ModuleName": "BossBattle", "MethodName": "Fight", "Data": [boss_id, 0, bc.won, json.dumps(bc.verify_data)], "ServerId": 1}
            )
            self.assertEqual(bf["Status"], 0)
            self.assertGreater(bf["Value"]["HurtValue"], 0)
            self.assertGreater(bf["Value"]["SingleJiFen"], 0)
            self.assertEqual(emu.profiles["normal"].state["player"]["VIT"], vit_before - 5)

            while bf["Value"]["BossExist"]:
                # Use All-Out Attack to verify 3x AP & 100 RP scaling and kill boss
                bfi_all = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetFightInfo", "Data": [boss_id, 1], "ServerId": 1})
                self.assertEqual(bfi_all["Status"], 0)
                first_ally = next(u for u in bfi_all["Value"]["FightInfo"]["FightObjs"][0]["Heros"][:6] if u)
                self.assertEqual(first_ally["RP"], 100)
                bc_all = simulate_fight_info(bfi_all["Value"]["FightInfo"], emu.game_data["attacks"])
                bf = emu.handle_rpc(
                    {"ModuleName": "BossBattle", "MethodName": "Fight", "Data": [boss_id, 1, bc_all.won, json.dumps(bc_all.verify_data)], "ServerId": 1}
                )
                self.assertEqual(bf["Status"], 0)

            self.assertFalse(bf["Value"]["BossExist"])
            total_jifen = emu.profiles["normal"].state["player"]["BossCoin"]
            self.assertGreaterEqual(total_jifen, 100)

            # Box milestone claim + OneKeyDrawBox + BuyCount + Ranking
            boxes = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "BoxList", "Data": [], "ServerId": 1})
            self.assertEqual(len(boxes["Value"]), 35)
            dbox = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "DrawBox", "Data": [100], "ServerId": 1})
            self.assertEqual(dbox["Status"], 0)
            dup_box = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "DrawBox", "Data": [100], "ServerId": 1})
            self.assertNotEqual(dup_box["Status"], 0)

            buy_res = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "BuyCount", "Data": [2], "ServerId": 1})
            self.assertEqual(buy_res["Status"], 0)
            self.assertEqual(buy_res["Value"]["BuyCount"], 2)

            ranks = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "JiFenRanking", "Data": [], "ServerId": 1})
            self.assertEqual(ranks["Status"], 0)
            self.assertGreaterEqual(len(ranks["Value"]), 5)

            # Save / reload verification
            emu2 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            bl2 = emu2.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetBossList", "Data": [], "ServerId": 1})
            self.assertEqual(bl2["Value"]["BattleInfo"]["BuyCount"], 2)
            self.assertEqual(bl2["Value"]["BattleInfo"]["JiFen"], total_jifen)

    def test_21_arena_bots_genuine_win_loss_rank_swap_shop_and_guide6(self) -> None:
        import qa_runner

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            c_qa = qa_runner.QABackendClient(data_dir=data_dir, persist=True, new_player=True)
            emu = c_qa.emu
            assert emu is not None

            # Below Lv 20: Arena fight rejected
            qa_runner.apply_preset(c_qa, "QA_LV18")
            deny = emu.handle_rpc({"ModuleName": "PVP", "MethodName": "PVPFight", "Data": ["x", 1499], "ServerId": 1})
            self.assertNotEqual(deny["Status"], 0)

            # Upgrade to Lv 20 QA preset
            qa_runner.apply_preset(c_qa, "QA_LV20")
            pinfo = emu.handle_rpc({"ModuleName": "PVP", "MethodName": "GetPVPInfo", "Data": [], "ServerId": 1})
            self.assertEqual(pinfo["Status"], 0)
            val = pinfo["Value"]
            self.assertEqual(val["Rank"], 1500)
            self.assertGreater(val["RewardTimeStart"], 0)
            self.assertEqual(len(val["PVPShopInfo"]), 40)

            rank_list = val["RankList"]
            self.assertTrue(any(item["Rank"] == 1 for item in rank_list))
            self.assertTrue(any(item["IfAllowRank"] == 1 for item in rank_list))

            # Inspect bot formation via Slot.SlotFormations
            top_bot = next(item for item in rank_list if item["Rank"] == 1)
            self.assertEqual(len(top_bot["PlayerId"]), 36)
            bot_form = emu.handle_rpc({"ModuleName": "Slot", "MethodName": "SlotFormations", "Data": [top_bot["PlayerId"]], "ServerId": 1})
            self.assertEqual(bot_form["Status"], 0)
            self.assertEqual(bot_form["Value"]["PlayerInfo"]["Name"], top_bot["Name"])
            self.assertTrue(any(s.get("Hero") for s in bot_form["Value"]["SlotInfos"]))

            # Refresh + cooldown check
            ref1 = emu.handle_rpc({"ModuleName": "PVP", "MethodName": "Refresh", "Data": [], "ServerId": 1})
            self.assertEqual(ref1["Status"], 0)
            ref2 = emu.handle_rpc({"ModuleName": "PVP", "MethodName": "Refresh", "Data": [], "ServerId": 1})
            self.assertNotEqual(ref2["Status"], 0)

            # Fight Rank 1 boss-tier bot -> must NOT auto-win!
            lose_res = emu.handle_rpc({"ModuleName": "PVP", "MethodName": "PVPFight", "Data": [top_bot["PlayerId"], 1], "ServerId": 1})
            self.assertEqual(lose_res["Status"], 0)
            self.assertEqual(lose_res["Value"]["IsWinFight"], 0)
            self.assertEqual(lose_res["Value"]["Rank"], 1500)
            self.assertGreaterEqual(lose_res["Value"]["PVPCoin"], 10)
            self.assertTrue(lose_res["Value"]["FightInfo"]["FightObjs"][0]["IsPVP"])

            # Fight beatable Rank 1499 opponent -> genuine win & rank swap
            easy_target = max((item for item in val["RankList"] if item["IfAllowRank"] == 1), key=lambda x: x["Rank"])
            win_res = emu.handle_rpc(
                {"ModuleName": "PVP", "MethodName": "PVPFight", "Data": [easy_target["PlayerId"], easy_target["Rank"]], "ServerId": 1}
            )
            self.assertEqual(win_res["Status"], 0)
            self.assertEqual(win_res["Value"]["IsWinFight"], 1)
            self.assertEqual(win_res["Value"]["Rank"], easy_target["Rank"])
            self.assertEqual(len(win_res["Value"]["ChoiceGetGameResource"]), 3)

            # Top Rank list across steps 1..5
            top_list = emu.handle_rpc({"ModuleName": "PVP", "MethodName": "GetPVPTopRankList", "Data": [], "ServerId": 1})
            self.assertEqual(top_list["Status"], 0)
            self.assertEqual(len(top_list["Value"]["TopRankList"]), 5)

            # Climb across rank tiers into top-1000 to verify breakthrough Diamonds from PvpRankFirstRewardRelation
            diam_before = emu.profiles["normal"].state["player"]["Diamond"]
            cur_list = win_res["Value"]["RankList"]
            for _ in range(3):
                if emu.profiles["normal"].state["pvp"]["rank"] <= 980:
                    break
                climb_target = min((item for item in cur_list if item["IfAllowRank"] == 1), key=lambda x: x["Rank"])
                climb_res = emu.handle_rpc(
                    {"ModuleName": "PVP", "MethodName": "PVPFight", "Data": [climb_target["PlayerId"], climb_target["Rank"]], "ServerId": 1}
                )
                self.assertEqual(climb_res["Status"], 0)
                if climb_res["Value"]["IsWinFight"] == 1:
                    cur_list = climb_res["Value"]["RankList"]
            self.assertLess(emu.profiles["normal"].state["pvp"]["rank"], 1000)
            self.assertGreater(emu.profiles["normal"].state["player"]["Diamond"], diam_before)

            # Verify PVPShopBuy with earned PVPCoin
            shop_buy = emu.handle_rpc({"ModuleName": "PVPShop", "MethodName": "PVPShopBuy", "Data": [1, 1], "ServerId": 1})
            self.assertEqual(shop_buy["Status"], 0)

            # Complete Lv 20 Guide 6 using real RPC Player.AlterPlayerStepCount
            g6 = emu.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerStepCount", "Data": [6, 206], "ServerId": 1})
            self.assertEqual(g6["Status"], 0)

            # Save / reload verification
            emu2 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            pinfo2 = emu2.handle_rpc({"ModuleName": "PVP", "MethodName": "GetPVPInfo", "Data": [], "ServerId": 1})
            self.assertLess(pinfo2["Value"]["Rank"], 1000)
            self.assertEqual(emu2.profiles["normal"].state["player"]["StepCountList"]["6"], 206)
            shop_row_1 = next(x for x in pinfo2["Value"]["PVPShopInfo"] if x["ShopId"] == 1)
            self.assertEqual(shop_row_1["BuyNum"], 1)

    def test_22_phase_d_battle_for_ten_daydayfund_startwork_fashion_and_chest(self) -> None:
        import qa_runner

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            c_qa = qa_runner.QABackendClient(data_dir=data_dir, persist=True, new_player=True)
            emu = c_qa.emu
            assert emu is not None
            qa_runner.apply_preset(c_qa, "QA_LV20")

            # Debris split + chest opening (GoodsOutputRelation) + Battle.ConFight
            c_qa.admin_grant(
                items=[{"id": 15010006, "num": 5}, {"id": 16020020, "num": 1}, {"id": 16070004, "num": 100}],
                source="qa_phase_d",
            )
            init = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertTrue(any(g["GoodsModelId"] == 15010006 for g in init["Value"]["GoodsHeroDebrisInfo"]))
            self.assertFalse(any(g["GoodsModelId"] == 15010006 for g in init["Value"]["GoodsPropsInfo"]))

            stone = next(g for g in init["Value"]["GoodsPropsInfo"] if g["GoodsModelId"] == 16020020)
            used = emu.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsUse", "Data": [stone["Id"], 16020020, 1], "ServerId": 1})
            self.assertEqual(used["Status"], 0)
            self.assertTrue(used["Value"]["BaseGetGameResourceList"])

            # Daydayfund cycle
            df0 = emu.handle_rpc({"ModuleName": "Daydayfund", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertTrue(df0["Value"]["IfDraw"])
            inv = emu.handle_rpc({"ModuleName": "Daydayfund", "MethodName": "Invest", "Data": [], "ServerId": 1})
            self.assertEqual(inv["Status"], 0)
            self.assertFalse(inv["Value"]["IfDraw"])
            self.assertGreaterEqual(inv["Value"]["Multiple"], 30 * 20)
            harv = emu.handle_rpc({"ModuleName": "Daydayfund", "MethodName": "Harvest", "Data": [], "ServerId": 1})
            self.assertEqual(harv["Status"], 0)
            self.assertTrue(harv["Value"]["IfDraw"])
            self.assertTrue(harv["Value"]["BaseGetGameResourceList"])

            # StartWorkReward RPC + RedDotInfo[2718] dynamic Mon-Thu workday behavior
            import time as _time

            sw_info = emu.handle_rpc({"ModuleName": "StartWorkReward", "MethodName": "GetStartworkRewardInfo", "Data": [], "ServerId": 1})
            self.assertEqual(sw_info["Status"], 0)
            self.assertIn("StartWorkReward", sw_info["Value"])
            expected_before = 1 if _time.localtime().tm_wday in (0, 1, 2, 3) else 0
            self.assertEqual(sw_info["Avatar"]["RedDotInfo"]["2718"], expected_before)
            sw_get = emu.handle_rpc({"ModuleName": "StartWorkReward", "MethodName": "GetStartworkReward", "Data": [], "ServerId": 1})
            self.assertEqual(sw_get["Status"], 0)
            self.assertEqual(sw_get["Avatar"]["RedDotInfo"]["2718"], 0)

            # Fashion DressUp / StepUp / Resolve
            prof = emu.profiles["normal"]
            prof._grant_resources_from_tuples([(1901, 19010001, 2)], source="qa_fashion_grant", tx_prefix="qa_fash")
            fashions = prof.state["fashions"]
            self.assertEqual(len(fashions), 2)
            dr = emu.handle_rpc({"ModuleName": "Fashion", "MethodName": "DressUp", "Data": [fashions[0]["Id"]], "ServerId": 1})
            self.assertEqual(dr["Value"]["FashionModelId"], 19010001)
            su = emu.handle_rpc({"ModuleName": "Fashion", "MethodName": "StepUp", "Data": [fashions[0]["Id"]], "ServerId": 1})
            self.assertEqual(su["Status"], 0)
            self.assertEqual(su["Value"]["FashionInfo"]["Step"], 1)
            rs = emu.handle_rpc({"ModuleName": "Fashion", "MethodName": "Resolve", "Data": [fashions[1]["Id"]], "ServerId": 1})
            self.assertEqual(rs["Status"], 0)
            self.assertEqual(len(prof.state["fashions"]), 1)

            # BattleForTen (Battle.ConFight) with sweep token consumption
            emu.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, True, None], "ServerId": 1})
            cf = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "ConFight", "Data": [11, 1111, 1, 3, 2], "ServerId": 1})
            self.assertEqual(cf["Status"], 0)
            self.assertEqual(len(cf["Value"]["BaseGetGameResourceList"]), 3)

    def test_23_fast_qa_presets_lv18_and_lv20_and_pvp_turn_order(self) -> None:
        from combat_sim import PVP_ENEMY_ORDER, PVE_ENEMY_ORDER
        import qa_runner

        self.assertEqual(PVP_ENEMY_ORDER, [7, 8, 9, 10, 11, 12])
        self.assertEqual(PVE_ENEMY_ORDER, [9, 8, 7, 12, 11, 10])
        with tempfile.TemporaryDirectory() as td:
            c18 = qa_runner.QABackendClient(data_dir=Path(td) / "lv18", persist=True, new_player=True)
            res18 = qa_runner.apply_preset(c18, "QA_LV18")
            self.assertEqual(res18["summary"]["player"]["Lv"], 18)

            c20 = qa_runner.QABackendClient(data_dir=Path(td) / "lv20", persist=True, new_player=True)
            res20 = qa_runner.apply_preset(c20, "QA_LV20")
            self.assertEqual(res20["summary"]["player"]["Lv"], 20)

    def test_24_release_isolation_promote_and_rollback(self) -> None:
        import env_ctl

        with tempfile.TemporaryDirectory() as td:
            rel_dir = Path(td) / "releases"
            # Uninitialized stable release must refuse falling back to DEV working tree
            empty_rel = env_ctl.get_active_stable_release(releases_dir=rel_dir)
            self.assertFalse(empty_rel["configured"])
            with self.assertRaises(RuntimeError):
                env_ctl.start_env_daemon("stable", port_override=19999, data_dir=Path(td) / "s", releases_dir=rel_dir)

            # Pin STABLE pointer to checkpoint-vn-r5.2 and stage checkpoint-vn-r6 separately
            ptr52 = env_ctl._set_stable_release_pointer("checkpoint-vn-r5.2", releases_dir=rel_dir)
            self.assertEqual(ptr52["active_release"], "checkpoint-vn-r5.2")
            staged6 = env_ctl.materialize_release("checkpoint-vn-r6", releases_dir=rel_dir)
            self.assertTrue(staged6["ok"])

            active = env_ctl.get_active_stable_release(releases_dir=rel_dir)
            self.assertTrue(active["verified"])
            self.assertTrue(active["isolated_from_dev"])
            self.assertEqual(active["active_release"], "checkpoint-vn-r5.2")
            # Ensure materialized r5.2 snapshot does not carry R6 BossBattle handlers
            r52_src = Path(active["emulator_path"]).read_text(encoding="utf-8")
            self.assertNotIn("BossBattle.GetBossList", r52_src)

            # Promote to r6 -> records previous_release; rollback reverts cleanly
            ptr6 = env_ctl._set_stable_release_pointer("checkpoint-vn-r6", releases_dir=rel_dir)
            self.assertEqual(ptr6["active_release"], "checkpoint-vn-r6")
            self.assertEqual(ptr6["previous_release"], "checkpoint-vn-r5.2")
            ptr_rb = env_ctl._set_stable_release_pointer(ptr6["previous_release"], releases_dir=rel_dir)
            self.assertEqual(ptr_rb["active_release"], "checkpoint-vn-r5.2")

            # Tampering with STABLE release code fails checksum verification
            emu_p = Path(env_ctl.get_active_stable_release(releases_dir=rel_dir)["emulator_path"])
            emu_p.write_text(emu_p.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
            self.assertFalse(env_ctl.get_active_stable_release(releases_dir=rel_dir)["verified"])

    def test_25_boss_battle_drop_pool_validation_kill_and_legacy_migration(self):
        import time
        import uuid
        from combat_sim import simulate_fight_info

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            normal = emu.get_profile_by_name("normal")

            # 1. Verify entire BossBattle DropResource pool and LuckbossValueShop are valid & displayable
            pool_ids = [int(item["ModelId"]) for item in normal.BOSS_DROP_POOL]
            self.assertNotIn(15030101, pool_ids)
            self.assertIn(15032101, pool_ids)
            for item in normal.BOSS_DROP_POOL:
                self.assertTrue(
                    normal._is_valid_resource(int(item["TypeId"]), int(item["ModelId"])),
                    msg=f"Invalid pool entry: {item}",
                )
            for mid in range(12010050, 12010056):
                dr = normal._boss_drop_for_model(mid)
                self.assertTrue(normal._is_valid_resource(dr["TypeId"], dr["ModelId"]))
            for row in normal.game_data["luckboss_value_shop"].values():
                self.assertTrue(normal._is_valid_resource(int(row["typeID"]), int(row["modelID"])))

            # 2. Validation guard rejects invalid resource tuples & payloads before RPC emission
            with self.assertRaises(ValueError):
                normal._grant_resources_from_tuples(
                    [(1503, 15030101, 1)],
                    source="test_invalid",
                    tx_prefix=f"test_invalid:{uuid.uuid4()}",
                )
            with self.assertRaises(ValueError):
                normal.validate_base_resource_list(
                    [{"TreasureDebris": [{"ResourceTypeSub": 1503, "TreasureDebrisModelId": 15030101, "Num": 1}]}],
                    context="test_invalid_payload",
                )

            # 3. Full BossBattle cycle on BossModelId=12010052 (the tier that previously yielded 15030101)
            normal.state["player"]["Lv"] = 20
            normal.state["player"]["VIT"] = 200
            for slot in normal.state["slots"]:
                if slot.get("HeroModelId"):
                    heroes_map = {h["Id"]: h for h in normal.state["heroes"]}
                    heroes_map[slot["HeroId"]]["Lv"] = 35
                    slot["Property"] = normal._compute_slot_property(slot, heroes_map)
            normal._recalc_all_slots_and_fap()

            now = int(time.time())
            bs = normal._sync_boss_battle_state()
            bs["attack_num"] = 20
            boss_cfg = normal.game_data["heroes"]["12010052"]
            boss_id = str(uuid.uuid4())
            probe_boss = {
                "Id": boss_id,
                "PlayerId": str(normal.state["player"]["PlayerId"]),
                "PlayerName": str(normal.state["player"]["PlayerName"]),
                "BossModelId": 12010052,
                "Name": boss_cfg["name"],
                "Lv": 20,
                "CurHP": 1000000,
                "TotalHP": 1000000,
                "AwayTime": now + 7200,
                "CanHelpTime": 0,
                "DropResource": normal._boss_drop_for_model(12010052),
            }
            preview = simulate_fight_info(normal._build_boss_fight_info(probe_boss, False), normal.game_data["attacks"])
            preview_last = preview.verify_data.get("hp", [[]])[-1]
            preview_hp = next((int(u["HP"]) for u in preview_last if int(u.get("PosId", 0)) == 8), 999000)
            boss_hp = max(4000, (1000000 - preview_hp) * 3)
            probe_boss["CurHP"] = boss_hp
            probe_boss["TotalHP"] = boss_hp
            bs["bosses"] = [probe_boss]
            normal.state["battle"]["HasBoss"] = "True"

            bl = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetBossList", "Data": [], "ServerId": 1})
            self.assertEqual(bl["Status"], 0)
            self.assertEqual(len(bl["Value"]["BossList"]), 1)
            self.assertEqual(bl["Value"]["BossList"][0]["DropResource"]["ModelId"], 15032101)

            # Normal attack must leave boss alive (HP > 0)
            fi_norm = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetFightInfo", "Data": [boss_id, 0], "ServerId": 1})
            self.assertEqual(fi_norm["Status"], 0)
            bc_norm = simulate_fight_info(fi_norm["Value"]["FightInfo"], normal.game_data["attacks"])
            atk_norm = emu.handle_rpc(
                {
                    "ModuleName": "BossBattle",
                    "MethodName": "Fight",
                    "Data": [boss_id, 0, bc_norm.won, json.dumps(bc_norm.verify_data)],
                    "ServerId": 1,
                }
            )
            self.assertEqual(atk_norm["Status"], 0)
            self.assertGreater(atk_norm["Value"]["HurtValue"], 0)
            self.assertTrue(atk_norm["Value"]["BossExist"])

            # All-Out attacks until kill reward triggers
            kill_res = atk_norm
            for _ in range(10):
                if not kill_res["Value"]["BossExist"]:
                    break
                fi_full = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetFightInfo", "Data": [boss_id, 1], "ServerId": 1})
                self.assertEqual(fi_full["Status"], 0)
                bc_full = simulate_fight_info(fi_full["Value"]["FightInfo"], normal.game_data["attacks"])
                kill_res = emu.handle_rpc(
                    {
                        "ModuleName": "BossBattle",
                        "MethodName": "Fight",
                        "Data": [boss_id, 1, bc_full.won, json.dumps(bc_full.verify_data)],
                        "ServerId": 1,
                    }
                )
                self.assertEqual(kill_res["Status"], 0)
            self.assertFalse(kill_res["Value"]["BossExist"])
            kill_bundles = kill_res["Value"]["BaseGetGameResourceList"]
            normal.validate_base_resource_list(kill_bundles, context="test_25_kill")
            debris_rewards = kill_bundles[0].get("TreasureDebris", [])
            self.assertEqual([d["TreasureDebrisModelId"] for d in debris_rewards], [15032101])
            debris_delta = kill_res["Avatar"]["TreasureDebrisInfo"].get("15032101", [])
            self.assertEqual(len(debris_delta), 1)
            self.assertEqual(debris_delta[0].get("Num"), 1)

            # Close victory screen & verify GetBossList + save/reload persistence
            bl_after = emu.handle_rpc({"ModuleName": "BossBattle", "MethodName": "GetBossList", "Data": [], "ServerId": 1})
            self.assertEqual(bl_after["Status"], 0)
            self.assertEqual(bl_after["Value"]["BossList"], [])

            emu2 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            normal2 = emu2.get_profile_by_name("normal")
            self.assertEqual(
                sum(d["Num"] for d in normal2.state["treasure_debris"] if d["TreasureDebrisModelId"] == 15032101),
                1,
            )
            init2 = emu2.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertEqual(init2["Status"], 0)
            self.assertEqual(
                [d["TreasureDebrisModelId"] for d in init2["Value"].get("TreasureDebrisInfo", [])],
                [15032101],
            )

            # 4. Legacy save migration: 15030101 in treasure_debris (merged cleanly) and boss DropResource
            normal_path = data_dir / "normal_profile.json"
            raw = json.loads(normal_path.read_text(encoding="utf-8"))
            raw["treasure_debris"].append({"Id": str(uuid.uuid4()), "TreasureDebrisModelId": 15030101, "Num": 2})
            legacy_boss_id = str(uuid.uuid4())
            raw["boss_battle"]["bosses"] = [
                {
                    "Id": legacy_boss_id,
                    "PlayerId": raw["player"]["PlayerId"],
                    "PlayerName": raw["player"]["PlayerName"],
                    "BossModelId": 12010052,
                    "Name": "Legacy Boss",
                    "Lv": 20,
                    "CurHP": 1000,
                    "TotalHP": 1000,
                    "AwayTime": int(time.time()) + 3600,
                    "CanHelpTime": 0,
                    "DropResource": {"TypeId": 1503, "ModelId": 15030101, "Num": 1},
                }
            ]
            normal_path.write_text(json.dumps(raw), encoding="utf-8")

            emu3 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            normal3 = emu3.get_profile_by_name("normal")
            debris_models = [d["TreasureDebrisModelId"] for d in normal3.state["treasure_debris"]]
            self.assertNotIn(15030101, debris_models)
            self.assertEqual(debris_models.count(15032101), 1)
            self.assertEqual(normal3.state["treasure_debris"][0]["Num"], 3)
            self.assertEqual(normal3.state["boss_battle"]["bosses"][0]["DropResource"]["ModelId"], 15032101)

    def test_26_vit_and_sta_limit_normalization_and_no_polling_loop(self):
        import time

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            debug_prof = emu.get_profile_by_name("debug")
            vit_cfg = debug_prof.game_data["vit_config"]
            sta_cfg = debug_prof.game_data["sta_config"]
            self.assertEqual(int(vit_cfg["maxNum"]), 200)
            self.assertEqual(int(sta_cfg["maxNum"]), 20)
            vit_cd = int(vit_cfg["recoverCD"])
            sta_cd = int(sta_cfg["recoverCD"])

            # 1. Legacy debug profile with VITMaxNum=120 & stale VITNextRecoverTime <= now
            p = debug_prof.state["player"]
            now = int(time.time())
            p["VIT"] = 165
            p["VITMaxNum"] = 120
            p["VITNextRecoverTime"] = now - 30
            debug_prof.state = debug_prof._normalize_loaded_state(debug_prof.state)

            self.assertEqual(debug_prof.state["player"]["VITMaxNum"], 200)
            self.assertEqual(debug_prof.state["player"]["VIT"], 165)
            # Client checks VIT < VitConfig.maxNum (200) and VITNextRecoverTime <= mTimeTick; must NOT loop
            for _ in range(3):
                res = emu.handle_rpc({"ModuleName": "Player", "MethodName": "AvatarInfo", "Data": [], "ServerId": 2})
                self.assertEqual(res["Status"], 0)
                val = res["Value"]
                av = res["Avatar"]
                cur_now = int(time.time())
                self.assertEqual(val["VITMaxNum"], 200)
                self.assertEqual(av["VITMaxNum"], 200)
                self.assertGreater(val["VITNextRecoverTime"], cur_now)
                self.assertLessEqual(val["VITNextRecoverTime"], cur_now + vit_cd)
                self.assertEqual(val["VITNextRecoverTime"], av["VITNextRecoverTime"])

            # 2. VIT boundaries: below (80), at limit (200), above limit (235), and VIP/elevated cap (250)
            for vit_val, saved_max, exp_max, expect_future in [
                (80, 120, 200, True),
                (199, 200, 200, True),
                (200, 120, 200, False),
                (235, 200, 200, False),
                (220, 250, 250, True),
                (250, 250, 250, False),
            ]:
                p = debug_prof.state["player"]
                cur_now = int(time.time())
                p["VIT"] = vit_val
                p["VITMaxNum"] = saved_max
                p["VITNextRecoverTime"] = cur_now - 5
                res = emu.handle_rpc({"ModuleName": "Player", "MethodName": "AvatarInfo", "Data": [], "ServerId": 2})
                val = res["Value"]
                self.assertEqual(val["VIT"], vit_val)
                self.assertEqual(val["VITMaxNum"], exp_max)
                if expect_future:
                    self.assertGreater(val["VITNextRecoverTime"], cur_now)
                    self.assertLessEqual(val["VITNextRecoverTime"], cur_now + vit_cd)
                else:
                    self.assertLessEqual(val["VITNextRecoverTime"], int(time.time()))

            # 3. Symmetric STA checks: legacy low cap upgraded to 20, debug cap 40 preserved, OlinaHugh >20 preserved
            for sta_val, saved_sta_max, exp_sta_max, expect_future in [
                (10, 10, 20, True),
                (20, 15, 20, False),
                (35, 40, 40, True),
                (40, 40, 40, False),
                (143, 20, 20, False),
            ]:
                p = debug_prof.state["player"]
                cur_now = int(time.time())
                p["STA"] = sta_val
                p["STAMaxNum"] = saved_sta_max
                p["STANextRecoverTime"] = cur_now - 10
                res = emu.handle_rpc({"ModuleName": "Player", "MethodName": "AvatarInfo", "Data": [], "ServerId": 2})
                val = res["Value"]
                self.assertEqual(val["STA"], sta_val)
                self.assertEqual(val["STAMaxNum"], exp_sta_max)
                if expect_future:
                    self.assertGreater(val["STANextRecoverTime"], cur_now)
                    self.assertLessEqual(val["STANextRecoverTime"], cur_now + sta_cd)
                else:
                    self.assertLessEqual(val["STANextRecoverTime"], int(time.time()))

    def test_27_r7_stage_progression_guards_and_chapter_need_lv(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            normal = emu.get_profile_by_name("normal")
            gd = normal.game_data

            # 1. VIT guard: below vit_cost (5), Battle.GetFightInfo and Battle.Fight reject (-1)
            normal.state["player"]["VIT"] = 4
            fi_low_vit = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [11, 1111, 1], "ServerId": 1})
            self.assertEqual(fi_low_vit["Status"], -1)
            f_low_vit = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, True, "", False], "ServerId": 1})
            self.assertEqual(f_low_vit["Status"], -1)

            # Exactly 5 VIT succeeds and deducts 5 -> 0
            normal.state["player"]["VIT"] = 5
            f_ok = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, True, "", False], "ServerId": 1})
            self.assertEqual(f_ok["Status"], 0)
            self.assertEqual(normal.state["player"]["VIT"], 0)

            # 2. Daily fightNumMax guard & ResetCount recovery
            normal.state["player"]["VIT"] = 200
            max_fights = int(gd["nodes"]["1111"]["fightNumMax"])
            normal.state["nodes"]["1111"]["FightCount"] = max_fights
            fi_cap = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [11, 1111, 1], "ServerId": 1})
            self.assertEqual(fi_cap["Status"], -1)
            f_cap = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1111, 1, True, "", False], "ServerId": 1})
            self.assertEqual(f_cap["Status"], -1)
            rc = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "ResetCount", "Data": [11, 1111], "ServerId": 1})
            self.assertEqual(rc["Status"], 0)
            fi_after_reset = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [11, 1111, 1], "ServerId": 1})
            self.assertEqual(fi_after_reset["Status"], 0)

            # 3. BattleChapterModel.needLV gate (Ch 27 requires Lv 28):
            # Below Lv 28: clearing final node of Ch 26 sets IfPass=1 without unlocking Ch 27, and Ch 27 battles reject
            ch26_nodes = sorted([int(k) for k, v in gd["nodes"].items() if v.get("chapterModelID") == 26])
            ch27_nodes = sorted([int(k) for k, v in gd["nodes"].items() if v.get("chapterModelID") == 27])
            self.assertEqual(int(gd["chapters"]["27"]["needLV"]), 28)
            last_26 = ch26_nodes[-1]
            first_27 = ch27_nodes[0]

            normal.state["player"]["Lv"] = 26
            normal.state["player"]["EXP"] = int(gd["player_lv"]["26"]["EXPTotal"])
            normal.state["chapters"]["26"] = normal._make_chapter_state(26)
            normal.state["nodes"][str(last_26)] = normal._make_node_state(last_26, flag=1)

            early_27 = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [27, first_27, 1], "ServerId": 1})
            self.assertEqual(early_27["Status"], -1)

            clear_26 = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [26, last_26, 1, True, "", False], "ServerId": 1})
            self.assertEqual(clear_26["Status"], 0)
            self.assertEqual(normal.state["chapters"]["26"]["IfPass"], 1)
            self.assertNotIn("27", normal.state["chapters"])
            self.assertNotIn("NextChapter", clear_26["Value"])

            # Leveling up to 28 automatically unlocks Ch 27 and its first node
            normal.state["player"]["EXP"] = int(gd["player_lv"]["28"]["EXPTotal"])
            normal._sync_level_from_exp()
            self.assertEqual(normal.state["player"]["Lv"], 28)
            self.assertIn("27", normal.state["chapters"])
            self.assertIn(str(first_27), normal.state["nodes"])

    def test_28_r7_2_fresh_lv1_tutorial_progression(self):
        """Test A: Fresh Lv 1 VN onboarding from NewPlayer through Guide 1 (Lv 1 -> Lv 7)."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            self.assertEqual(prof.state["player"]["Lv"], 1)
            self.assertEqual(prof.state["player"]["IsNewPlayer"], 1)
            self.assertEqual(prof.state["player"]["StepCountList"], {})

            # 1. Login -> NewPlayer (creates female main hero 12010004) -> duplicate NewPlayer blocked
            login_res = emu.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": ["1", "tok"], "ServerId": 1})
            self.assertEqual(login_res["Status"], 0)
            self.assertEqual(login_res["Value"]["IsNewPlayer"], 1)

            np_res = emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["TanThuR72", 1], "ServerId": 1})
            self.assertEqual(np_res["Status"], 0)
            self.assertEqual(prof.state["player"]["PlayerName"], "TanThuR72")
            self.assertEqual(prof.state["player"]["IsNewPlayer"], 0)
            self.assertEqual(len(prof.state["heroes"]), 1)
            self.assertEqual(prof.state["heroes"][0]["HeroModelId"], 12010004)

            dup_np = emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["Hijack", 0], "ServerId": 1})
            self.assertEqual(dup_np["Status"], -1114)
            self.assertEqual(prof.state["player"]["PlayerName"], "TanThuR72")

            init_res = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertEqual(init_res["Status"], 0)
            self.assertEqual(len(init_res["Value"]["HeroInfo"]), 1)
            self.assertEqual(init_res["Value"]["PlayerInfo"]["Lv"], 1)
            self.assertEqual(init_res["Value"]["PlayerInfo"]["StepCountList"], {})

            # 2. Battle 1111 (1-1) -> exact Lv 2 + starter drops + Guide 1 ordinal 1
            f1 = emu.handle_rpc(
                {
                    "ModuleName": "Battle",
                    "MethodName": "Fight",
                    "Data": [11, 1111, 1, True, "", False],
                    "ExtensionString": {"GuideInfo": [{"GuideId": 1, "Ordinal": 1}]},
                    "ServerId": 1,
                }
            )
            self.assertEqual(f1["Status"], 0)
            self.assertEqual(prof.state["player"]["Lv"], 2)
            self.assertEqual(prof.state["player"]["StepCountList"].get("1"), 1)

            # 3. Free Recruit -> Ayame (12011014) -> HeroCombat slot 2 -> free repeat blocked
            rec = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 1], "ServerId": 1})
            self.assertEqual(rec["Status"], 0)
            ayame = next((h for h in prof.state["heroes"] if h["HeroModelId"] == 12011014), None)
            self.assertIsNotNone(ayame)
            dup_rec = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 1], "ServerId": 1})
            self.assertEqual(dup_rec["Status"], -1)
            comb = emu.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [2, ayame["Id"]], "ServerId": 1})
            self.assertEqual(comb["Status"], 0)

            # 4. Battle 1112 (1-2) -> Lv 3 + RoadBox 111 -> DrawRoadBox -> Battle 1113 (1-3) -> Lv 4 & Forging RedDot
            f2 = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1112, 1, True, "", False], "ServerId": 1})
            self.assertEqual(f2["Status"], 0)
            self.assertEqual(prof.state["player"]["Lv"], 3)
            box = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawRoadBox", "Data": [11, 111], "ServerId": 1})
            self.assertEqual(box["Status"], 0)
            box_dup = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "DrawRoadBox", "Data": [11, 111], "ServerId": 1})
            self.assertEqual(box_dup["Status"], -1)

            f3 = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [11, 1113, 1, True, "", False], "ServerId": 1})
            self.assertEqual(f3["Status"], 0)
            self.assertEqual(prof.state["player"]["Lv"], 4)
            neck_whites = [e for e in prof.state["equips"] if e["EquipModelId"] == 13040130]
            self.assertGreaterEqual(len(neck_whites), 5)
            # RedDot 1400/1405 activates when >= 5 same-color equips can be composed
            self.assertEqual(f3["Avatar"]["RedDotInfo"].get("1400"), 1)
            self.assertEqual(f3["Avatar"]["RedDotInfo"].get("1405"), 1)

            comp = emu.handle_rpc(
                {"ModuleName": "Equip", "MethodName": "EquipCompose", "Data": [[e["Id"] for e in neck_whites[:5]]], "ServerId": 1}
            )
            self.assertEqual(comp["Status"], 0)
            green_neck = next((e for e in prof.state["equips"] if e["EquipModelId"] == 13040215), None)
            self.assertIsNotNone(green_neck)
            self.assertEqual(comp["Avatar"]["RedDotInfo"].get("1400"), 0)

            eq_comb = emu.handle_rpc(
                {"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [1, "", "", "", green_neck["Id"], "", ""], "ServerId": 1}
            )
            self.assertEqual(eq_comb["Status"], 0)
            eq_up = emu.handle_rpc({"ModuleName": "Equip", "MethodName": "OneKeyEquipLvUp", "Data": [[green_neck["Id"]]], "ServerId": 1})
            self.assertEqual(eq_up["Status"], 0)
            self.assertGreater(green_neck["Lv"], 1)

            # 5. Stages 1114 (Lv 5) -> 1115 (Lv 6, unlocks Ch 12) -> 1211 (Lv 6) -> 1212 (Lv 7) + Guide completion (997)
            for nid, exp_lv in [(1114, 5), (1115, 6), (1211, 6), (1212, 7)]:
                cid = 11 if nid < 1200 else 12
                res = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "Fight", "Data": [cid, nid, 1, True, "", False], "ServerId": 1})
                self.assertEqual(res["Status"], 0)
                self.assertEqual(prof.state["player"]["Lv"], exp_lv)
            self.assertIn("12", prof.state["chapters"])

            alt = emu.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerStepCount", "Data": [1, 997], "ServerId": 1})
            self.assertEqual(alt["Status"], 0)
            self.assertEqual(prof.state["player"]["StepCountList"].get("1"), 997)

    def test_29_r7_2_guide_continuity_and_regression_guard(self):
        """Test B: Partial tutorial progress persists across reload; completed guides ignore stale regression."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu1 = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            emu1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["Relay", 0], "ServerId": 1})
            emu1.handle_rpc(
                {
                    "ModuleName": "Battle",
                    "MethodName": "Fight",
                    "Data": [11, 1111, 1, True, "", False],
                    "ExtensionString": {"GuideInfo": [{"GuideId": 1, "Ordinal": 10}]},
                    "ServerId": 1,
                }
            )
            # In-progress backward recovery (e.g. correctMainGuideOrdinal: 10 -> 7) is allowed
            emu1.handle_rpc(
                {
                    "ModuleName": "Player",
                    "MethodName": "AlterPlayerStepCount",
                    "Data": [1, 7],
                    "ServerId": 1,
                }
            )

            # Reload from disk (simulating server restart + relogin)
            emu2 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            init2 = emu2.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertEqual(init2["Value"]["PlayerInfo"]["StepCountList"].get("1"), 7)

            # Complete Guide 1 (997) and Guide 7 (max_ord=8 -> saved as 9); stale rollback (15 or 4) must be ignored
            emu2.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerStepCount", "Data": [1, 997], "ServerId": 1})
            emu2.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerStepCount", "Data": [7, 9], "ServerId": 1})
            emu2.handle_rpc(
                {
                    "ModuleName": "Player",
                    "MethodName": "SyncAvatar",
                    "Data": [],
                    "ExtensionString": {"GuideInfo": [{"GuideId": 1, "Ordinal": 15}, {"GuideId": 7, "Ordinal": 4}]},
                    "ServerId": 1,
                }
            )
            emu3 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            steps3 = emu3.get_profile_by_name("normal").state["player"]["StepCountList"]
            self.assertEqual(steps3.get("1"), 997)
            self.assertEqual(steps3.get("7"), 9)

    def test_30_r7_2_step_rewards_antiduplication_and_early_rpcs(self):
        """Test C: Verified step reward IDs, anti-duplication, non-reward 313, and Shrine/Refine/Gift/MysteryShop."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["RewardTest", 1], "ServerId": 1})

            # Unknown event ID rejected
            bad = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [999999], "ServerId": 1})
            self.assertEqual(bad["Status"], -1)

            # 2071 -> 5x Tamotu (12013054) -> Hero.HeroRefine
            r2071 = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [2071], "ServerId": 1})
            self.assertEqual(r2071["Status"], 0)
            tamotus = [h for h in prof.state["heroes"] if h["HeroModelId"] == 12013054]
            self.assertEqual(len(tamotus), 5)
            # Duplicate claim rejected (-1136) even after restart
            dup2071 = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [2071], "ServerId": 1})
            self.assertEqual(dup2071["Status"], -1136)

            hero_coin_before = prof.state["player"]["HeroCoin"]
            ref_res = emu.handle_rpc(
                {"ModuleName": "Hero", "MethodName": "HeroRefine", "Data": [[h["Id"] for h in tamotus]], "ServerId": 1}
            )
            self.assertEqual(ref_res["Status"], 0)
            self.assertEqual(len([h for h in prof.state["heroes"] if h["HeroModelId"] == 12013054]), 0)
            self.assertGreater(prof.state["player"]["HeroCoin"], hero_coin_before)

            # 2181 -> 3x Meihaku (16040009) -> Glory.GloryLvUp (Shrine Lv 0 -> Lv 1 boosts STAMaxNum & party HP)
            sta_max_before = prof.state["player"]["STAMaxNum"]
            fap_before = prof.state["player"]["FAP"]
            r2181 = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [2181], "ServerId": 1})
            self.assertEqual(r2181["Status"], 0)
            dip = next((g for g in prof.state["goods"] if g["GoodsModelId"] == 16040009), None)
            self.assertIsNotNone(dip)
            self.assertEqual(dip["Num"], 3)

            g_up = emu.handle_rpc({"ModuleName": "Glory", "MethodName": "GloryLvUpForOneKey", "Data": [2], "ServerId": 1})
            self.assertEqual(g_up["Status"], 0)
            self.assertGreaterEqual(prof.state["glory"]["2"]["Lv"], 1)
            self.assertEqual(prof.state["player"]["STAMaxNum"], sta_max_before)  # +1 per 10 total levels
            self.assertGreater(prof.state["player"]["FAP"], fap_before)

            # 274 (1x 16030006 VIT pill) & 313 (non-reward UI pointer -> [] then -1136 on retry)
            r274 = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [274], "ServerId": 1})
            self.assertEqual(r274["Status"], 0)
            pill = next((g for g in prof.state["goods"] if g["GoodsModelId"] == 16030006), None)
            self.assertIsNotNone(pill)
            self.assertEqual(pill["Num"], 1)

            r313 = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [313], "ServerId": 1})
            self.assertEqual(r313["Status"], 0)
            self.assertEqual(r313["Value"]["BaseGetGameResourceList"], [])
            r313_dup = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [313], "ServerId": 1})
            self.assertEqual(r313_dup["Status"], -1136)

            # GiftLogin day 1 claim + anti-dup, and Day 2 denied on Day 1
            login_info = emu.handle_rpc({"ModuleName": "GiftLogin", "MethodName": "SignInfo", "Data": [], "ServerId": 1})
            self.assertEqual(login_info["Status"], 0)
            draw1 = emu.handle_rpc({"ModuleName": "GiftLogin", "MethodName": "DrawGiftBox", "Data": [1], "ServerId": 1})
            self.assertEqual(draw1["Status"], 0)
            draw1_dup = emu.handle_rpc({"ModuleName": "GiftLogin", "MethodName": "DrawGiftBox", "Data": [1], "ServerId": 1})
            self.assertEqual(draw1_dup["Status"], -1)
            draw2_early = emu.handle_rpc({"ModuleName": "GiftLogin", "MethodName": "DrawGiftBox", "Data": [2], "ServerId": 1})
            self.assertEqual(draw2_early["Status"], -1)

            # MysteryShop buy & anti-dup (IsSell 0 -> 1)
            ms_info = emu.handle_rpc({"ModuleName": "MysteryShop", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ms_info["Status"], 0)
            items = ms_info["Value"]["MysteryShopGoodsList"]
            self.assertGreater(len(items), 0)
            buyable = next((it for it in items if int(it["IsSell"]) == 0), None)
            self.assertIsNotNone(buyable)
            prof.state["player"]["Diamond"] = 10000
            prof.state["player"]["Gold"] = 1000000
            prof.state["player"]["HeroCoin"] = 10000
            ms_buy = emu.handle_rpc({"ModuleName": "MysteryShop", "MethodName": "MysteryShopBuyGoods", "Data": [buyable["Id"]], "ServerId": 1})
            self.assertEqual(ms_buy["Status"], 0)
            ms_buy_dup = emu.handle_rpc({"ModuleName": "MysteryShop", "MethodName": "MysteryShopBuyGoods", "Data": [buyable["Id"]], "ServerId": 1})
            self.assertEqual(ms_buy_dup["Status"], -1)

            # Persistence check after restart: 2071 still cannot be re-claimed
            emu_reload = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            dup_after_reload = emu_reload.handle_rpc(
                {"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [2071], "ServerId": 1}
            )
            self.assertEqual(dup_after_reload["Status"], -1136)

    def test_31_r7_2_existing_olinahugh_compatibility(self):
        """Test D: Existing completed profile (OlinaHugh-style) loads cleanly without losing stats or re-triggering guide."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu1 = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu1.get_profile_by_name("normal")
            prof.state["player"]["PlayerName"] = "OlinaHugh"
            prof.state["player"]["IsNewPlayer"] = 0
            prof.state["player"]["Lv"] = 20
            prof.state["player"]["EXP"] = int(prof.game_data["player_lv"]["20"]["EXPTotal"])
            prof.state["player"]["Diamond"] = 4695
            prof.state["player"]["Gold"] = 1552861
            prof.state["player"]["StepCountList"] = {"1": 997}
            prof.state["claimed_step_rewards"] = [1761]
            # Remove newer R7.2 keys to simulate legacy save normalization
            for legacy_key in ("glory", "gift_lv", "gift_login", "mystery_shop"):
                prof.state.pop(legacy_key, None)
            prof.save()

            emu2 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            init = emu2.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertEqual(init["Status"], 0)
            p_info = init["Value"]["PlayerInfo"]
            self.assertEqual(p_info["PlayerName"], "OlinaHugh")
            self.assertEqual(p_info["Lv"], 20)
            self.assertEqual(p_info["Diamond"], 4695)
            self.assertEqual(p_info["Gold"], 1552861)
            self.assertEqual(p_info["StepCountList"], {"1": 997})

            # Previously claimed 1761 cannot be claimed again; stale guide reset to 1 is blocked
            dup1761 = emu2.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1761], "ServerId": 1})
            self.assertEqual(dup1761["Status"], -1136)
            emu2.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerStepCount", "Data": [1, 1], "ServerId": 1})
            self.assertEqual(emu2.get_profile_by_name("normal").state["player"]["StepCountList"]["1"], 997)

            # GiftLv backfills claimable past levels (Lv 5..20) cleanly
            glv = emu2.handle_rpc({"ModuleName": "GiftLv", "MethodName": "LvGiftBags", "Data": [], "ServerId": 1})
            self.assertEqual(glv["Status"], 0)
            self.assertIn(5, glv["Value"]["Bags"])
            draw5 = emu2.handle_rpc({"ModuleName": "GiftLv", "MethodName": "DrawGiftBags", "Data": [5], "ServerId": 1})
            self.assertEqual(draw5["Status"], 0)
            draw5_dup = emu2.handle_rpc({"ModuleName": "GiftLv", "MethodName": "DrawGiftBags", "Data": [5], "ServerId": 1})
            self.assertEqual(draw5_dup["Status"], -1)

    def test_32_r7_4_recruit_tiers_pity_extra_rewards_and_ticket40(self) -> None:
        """R7.4: Quality-tiered Recruit pools, Ayame tutorial, 10x Dream talisman, Soul pity & 16060005, ticket 16050056."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            prof.state["player"]["Diamond"] = 20000

            info0 = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "RecruitInfo", "Data": [], "ServerId": 1})
            self.assertEqual(info0["Status"], 0)
            self.assertEqual(info0["Value"]["OutZiCount"], 9)

            # First Destiny free pull -> Ayame (12011014), cooldown blocks repeat free pull
            d1 = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 1], "ServerId": 1})
            self.assertEqual(d1["Status"], 0)
            self.assertEqual(d1["Value"]["BaseGetGameResourceList"][0]["Hero"][0]["HeroModelId"], 12011014)
            d_dup = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 1], "ServerId": 1})
            self.assertEqual(d_dup["Status"], -1)

            # Dream 10x (rtype=10) MUST spend 10x 16050003 talisman (NOT Diamonds!) and pull from banner 1 pool
            dia_before = prof.state["player"]["Diamond"]
            bad_d10 = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [10, 0], "ServerId": 1})
            self.assertEqual(bad_d10["Status"], -1)
            prof._grant_resources_from_tuples([(1605, 16050003, 12)], source="test32", tx_prefix="t32:tal")
            ok_d10 = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [10, 0], "ServerId": 1})
            self.assertEqual(ok_d10["Status"], 0)
            self.assertEqual(prof.state["player"]["Diamond"], dia_before)
            tal_left = next((g["Num"] for g in prof.state["goods"] if g["GoodsModelId"] == 16050003), 0)
            self.assertEqual(tal_left, 3)  # 1 starter + 12 granted - 10 spent
            d10_heroes = [h["HeroModelId"] for h in ok_d10["Value"]["BaseGetGameResourceList"][0]["Hero"]]
            self.assertEqual(len(d10_heroes), 10)
            self.assertGreater(len(set(d10_heroes)), 1)  # Varied heroes, not a static loop

            # First Soul pull -> guarantees q=15 Orange + extraRewards 16060005 x1
            s1 = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [3, 1], "ServerId": 1})
            self.assertEqual(s1["Status"], 0)
            s1_hero = s1["Value"]["BaseGetGameResourceList"][0]["Hero"][0]
            self.assertEqual(int(prof.game_data["heroes"][str(s1_hero["HeroModelId"])]["quality"]), 15)
            s1_goods = s1["Value"]["BaseGetGameResourceList"][0].get("Goods", [])
            self.assertEqual(s1_goods[0]["GoodsModelId"], 16060005)
            self.assertEqual(s1_goods[0]["Num"], 1)
            self.assertEqual(s1["Value"]["OutZiCount"], 9)

            # Force OutZiCount to 0 -> next single Soul pull guarantees q=15 Orange and resets OutZiCount to 9
            prof.state["recruit_state"]["OutZiCount"] = 0
            pity_pull = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [3, 0], "ServerId": 1})
            self.assertEqual(pity_pull["Status"], 0)
            pity_hid = pity_pull["Value"]["BaseGetGameResourceList"][0]["Hero"][0]["HeroModelId"]
            self.assertEqual(int(prof.game_data["heroes"][str(pity_hid)]["quality"]), 15)
            self.assertEqual(pity_pull["Value"]["OutZiCount"], 9)

            # Soul 10x with ticket 16050056 (rtype=40) via Bag -> 10 heroes (at least 1 q=15) + 10x 16060005
            prof._grant_resources_from_tuples([(1605, 16050056, 1)], source="test32", tx_prefix="t32:tick")
            s40 = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [40, 0], "ServerId": 1})
            self.assertEqual(s40["Status"], 0)
            s40_heroes = [h["HeroModelId"] for h in s40["Value"]["BaseGetGameResourceList"][0]["Hero"]]
            self.assertEqual(len(s40_heroes), 10)
            self.assertTrue(any(int(prof.game_data["heroes"][str(hid)]["quality"]) >= 15 for hid in s40_heroes))
            self.assertFalse(any(int(prof.game_data["heroes"][str(hid)]["quality"]) >= 18 for hid in s40_heroes))
            box_c = next((g["Num"] for g in prof.state["goods"] if g["GoodsModelId"] == 16060005), 0)
            self.assertGreaterEqual(box_c, 12)
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [40, 0], "ServerId": 1})["Status"],
                -1,
            )

            # Persistence across restart
            emu2 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            r_reload = emu2.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "RecruitInfo", "Data": [], "ServerId": 1})
            self.assertTrue(r_reload["Value"]["MidAlreadyUseResource"])
            self.assertTrue(r_reload["Value"]["HigAlreadyUseResource"])
            self.assertGreaterEqual(len(emu2.get_profile_by_name("normal").state["recruit_state"]["history"]), 4)

    def test_33_r7_4_simulated_charge_card_idempotency_and_vip_perks(self) -> None:
        """R7.4: Local Order -> ConfirmOrder/CardInfo idempotency, VIP upgrade, and dynamic VIP perks."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            self.assertEqual(prof.state["player"]["Vip"], 0)

            # Unknown product rejected
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "GenerateOrderID", "Data": ["com.fake.9999"], "ServerId": 1})["Status"],
                -1,
            )
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "ConfirmOrder", "Data": [99999], "ServerId": 1})["Status"],
                -1,
            )

            # GenerateOrderID -> ConfirmOrder with order_id -> grants 2x first-charge + VipEXP + VIP level up
            ord_res = emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "GenerateOrderID", "Data": ["com.cmn.inuyasha.gem680"], "ServerId": 1})
            self.assertEqual(ord_res["Status"], 0)
            oid = ord_res["Value"]
            conf = emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "ConfirmOrder", "Data": ["com.cmn.inuyasha.gem680", oid], "ServerId": 1})
            self.assertEqual(conf["Status"], 0)
            self.assertEqual(conf["Value"]["DiamondAdded"], 1360)
            self.assertEqual(conf["Avatar"]["VipEXP"], 680)
            expected_vip = prof.ledger.derive_vip_level(680)
            self.assertGreater(expected_vip, 0)
            self.assertEqual(conf["Avatar"]["Vip"], expected_vip)
            self.assertEqual(conf["Avatar"]["VIPLv"], expected_vip)

            # Replay same order_id blocked with -1136 without double-grant
            dia_after_first = prof.state["player"]["Diamond"]
            replay = emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "ConfirmOrder", "Data": ["com.cmn.inuyasha.gem680", oid], "ServerId": 1})
            self.assertEqual(replay["Status"], -1136)
            self.assertEqual(prof.state["player"]["Diamond"], dia_after_first)

            # Monthly card GenerateOrderID -> Activity + idempotency + DrawBuyReward & DrawDailyReward
            c_ord = emu.handle_rpc({"ModuleName": "CardInfo", "MethodName": "GenerateOrderID", "Data": [1], "ServerId": 1})
            self.assertEqual(c_ord["Status"], 0)
            c_oid = c_ord["Value"]["OrderId"]
            c_act = emu.handle_rpc({"ModuleName": "CardInfo", "MethodName": "Activity", "Data": [1, c_oid], "ServerId": 1})
            self.assertEqual(c_act["Status"], 0)
            self.assertEqual(prof.state["player"]["VipEXP"], 980)
            c_replay = emu.handle_rpc({"ModuleName": "CardInfo", "MethodName": "Activity", "Data": [1, c_oid], "ServerId": 1})
            self.assertEqual(c_replay["Status"], -1136)
            self.assertEqual(emu.handle_rpc({"ModuleName": "CardInfo", "MethodName": "DrawBuyReward", "Data": [1], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "CardInfo", "MethodName": "DrawBuyReward", "Data": [1], "ServerId": 1})["Status"], -1)
            self.assertEqual(emu.handle_rpc({"ModuleName": "CardInfo", "MethodName": "DrawDailyReward", "Data": [1], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "CardInfo", "MethodName": "DrawDailyReward", "Data": [1], "ServerId": 1})["Status"], -1)

            # Upgraded VIP perks dynamically reflected in MysteryShop, Explore, VipWelfare
            cur_vip = prof.state["player"]["VIPLv"]
            vip_cfg = prof.game_data["vip_model"][str(cur_vip)]
            ms = emu.handle_rpc({"ModuleName": "MysteryShop", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ms["Value"]["RefreshMysteryShopMaxNum"], int(vip_cfg["refreshMysteryShopMaxNum"]))
            exp = emu.handle_rpc({"ModuleName": "Explore", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(exp["Value"]["MaxResetNum"], int(vip_cfg["exploreMaxNum"]))
            vw = emu.handle_rpc({"ModuleName": "VipWelfare", "MethodName": "DrawVipWelfare", "Data": [], "ServerId": 1})
            self.assertEqual(vw["Status"], 0)

    def test_34_r7_4_shop_gift_vip_packs_and_fixed_bundle_1601(self) -> None:
        """R7.4: ShopGift 0..20 VIP packs and Goods.GoodsUse eBoxFixed (1601) granting ALL rows."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            prof.state["player"]["Diamond"] = 5000

            glist = emu.handle_rpc({"ModuleName": "ShopGift", "MethodName": "ShopGiftList", "Data": [], "ServerId": 1})
            self.assertEqual(glist["Status"], 0)
            self.assertEqual(len(glist["Value"]), 21)
            self.assertEqual(glist["Value"][0]["GoodsModelId"], 16010001)
            self.assertEqual(glist["Value"][20]["GoodsModelId"], 16010021)

            # VIP 0 cannot buy VIP 5 pack (16010006)
            too_low = emu.handle_rpc({"ModuleName": "ShopGift", "MethodName": "BuyGift", "Data": [16010006, 1], "ServerId": 1})
            self.assertEqual(too_low["Status"], -1)

            # Buy VIP 0 pack (16010001) -> adds 16010001 to bag -> GoodsUse grants ALL 3 fixed outputs
            buy0 = emu.handle_rpc({"ModuleName": "ShopGift", "MethodName": "BuyGift", "Data": [16010001, 1], "ServerId": 1})
            self.assertEqual(buy0["Status"], 0)
            self.assertEqual(buy0["Value"]["BuyGiftRecord"]["Num"], 1)
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "ShopGift", "MethodName": "BuyGift", "Data": [16010001, 1], "ServerId": 1})["Status"],
                -1,
            )
            box_item = next(g for g in prof.state["goods"] if g["GoodsModelId"] == 16010001)
            gold_before = prof.state["player"]["Gold"]
            use0 = emu.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsUse", "Data": [box_item["Id"], 16010001, 1], "ServerId": 1})
            self.assertEqual(use0["Status"], 0)
            self.assertEqual(prof.state["player"]["Gold"], gold_before + 10000)
            goods_gained = {g["GoodsModelId"]: g["Num"] for g in use0["Value"]["BaseGetGameResourceList"][0].get("Goods", [])}
            self.assertEqual(goods_gained.get(16050010), 5)
            self.assertEqual(goods_gained.get(16030008), 1)

    def test_35_r7_4_success_target_all_rpcs_and_lv11_unlock(self) -> None:
        """R7.4: SuccessTargetInfo GetInfo/DrawReward/DrawTotalReward/GetExchangeInfo/Exchange + 4900 RedDot."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            prof.state["player"]["Lv"] = 11
            prof.state["player"]["Diamond"] = 5000

            init = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertEqual(init["Avatar"]["RedDotInfo"].get("4900"), 1)

            st_info = emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(st_info["Status"], 0)
            v = st_info["Value"]
            self.assertEqual(v["Day"], 1)
            self.assertEqual(len(v["TargetList"]), 42)
            t3 = next(t for t in v["TargetList"] if t["TargetId"] == 3)
            self.assertGreaterEqual(t3["Sequence"], 1)

            # Claim Day 1 Login (tid=3, seq=1) -> blocks duplicate & locked Day 2
            dr_ok = emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "DrawReward", "Data": [3, 1], "ServerId": 1})
            self.assertEqual(dr_ok["Status"], 0)
            self.assertGreaterEqual(len(dr_ok["Value"]["BaseGetGameResourceList"]), 1)
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "DrawReward", "Data": [3, 1], "ServerId": 1})["Status"],
                -3137,
            )
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "DrawReward", "Data": [3, 2], "ServerId": 1})["Status"],
                -6001,
            )

            # ExchangeInfo & Exchange
            ex_info = emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "GetExchangeInfo", "Data": [1], "ServerId": 1})
            self.assertEqual(ex_info["Status"], 0)
            self.assertEqual(len(ex_info["Value"]["ActivityList"]), 7)
            ex_buy = emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "Exchange", "Data": [1, 1], "ServerId": 1})
            self.assertEqual(ex_buy["Status"], 0)

            # The no-argument final claim is available after the seven-day phase.
            prof.state["success_target"]["start_ts"] -= 7 * 86400
            tot = emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "DrawTotalReward", "Data": [], "ServerId": 1})
            self.assertEqual(tot["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "GetInfo", "Data": [], "ServerId": 1})["Value"]["IfDraw"], 1)
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "SuccessTargetInfo", "MethodName": "DrawTotalReward", "Data": [], "ServerId": 1})["Status"],
                -3137,
            )

    def test_36_r7_4_box_choice_including_ur_quality18(self) -> None:
        """R7.4: Goods.GoodsUseForBoxChoice for eBoxChoice (16060008 UR hero) and eFashionChoice (16080001)."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            prof._grant_resources_from_tuples([(1606, 16060008, 1), (1608, 16080001, 1)], source="test36", tx_prefix="t36:seed")

            ur_box = next(g for g in prof.state["goods"] if g["GoodsModelId"] == 16060008)
            f_box = next(g for g in prof.state["goods"] if g["GoodsModelId"] == 16080001)

            # Reject hero not inside 16060008 choice table without consuming box
            bad = emu.handle_rpc(
                {"ModuleName": "Goods", "MethodName": "GoodsUseForBoxChoice", "Data": [ur_box["Id"], 16060008, 12011014, 1], "ServerId": 1}
            )
            self.assertEqual(bad["Status"], -1)
            self.assertTrue(any(g["GoodsModelId"] == 16060008 for g in prof.state["goods"]))

            # Pick quality=18 UR InuYasha (12011004)
            ok = emu.handle_rpc(
                {"ModuleName": "Goods", "MethodName": "GoodsUseForBoxChoice", "Data": [ur_box["Id"], 16060008, 12011004, 1], "ServerId": 1}
            )
            self.assertEqual(ok["Status"], 0)
            gained_h = ok["Value"]["BaseGetGameResourceList"][0]["Hero"][0]
            self.assertEqual(gained_h["HeroModelId"], 12011004)
            self.assertEqual(int(prof.game_data["heroes"]["12011004"]["quality"]), 18)
            self.assertFalse(any(g["GoodsModelId"] == 16060008 for g in prof.state["goods"]))
            self.assertEqual(
                emu.handle_rpc(
                    {"ModuleName": "Goods", "MethodName": "GoodsUseForBoxChoice", "Data": [ur_box["Id"], 16060008, 12011004, 1], "ServerId": 1}
                )["Status"],
                -1,
            )

            # Pick fashion from 16080001
            ok_f = emu.handle_rpc(
                {"ModuleName": "Goods", "MethodName": "GoodsUseForBoxChoice", "Data": [f_box["Id"], 16080001, 19010001, 1], "ServerId": 1}
            )
            self.assertEqual(ok_f["Status"], 0)
            self.assertTrue(any(f["FashionModelId"] == 19010001 for f in prof.state.get("fashions", [])))

    def test_37_r7_4_lvplan_canonical_cost_and_regressions(self) -> None:
        """R7.4: Verify canonical LvPlan 100-Diamond tier fee (per LvPlanRewardModel) + clean LvPlan claim."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            prof.state["player"]["Lv"] = 15
            prof.state["player"]["Diamond"] = 1000
            prof.state["player"]["Vip"] = 2
            prof.state["player"]["VIPLv"] = 2

            self.assertEqual(emu.handle_rpc({"ModuleName": "LvPlan", "MethodName": "OpenLvPlan", "Data": [], "ServerId": 1})["Status"], 0)
            self.assertEqual(prof.state["player"]["Diamond"], 1000)
            # Insufficient 100 Diamond cannot claim tier 10 -> after setting 100 Diamond, net gain = +100 (200 - 100)
            prof.state["player"]["Diamond"] = 50
            self.assertEqual(emu.handle_rpc({"ModuleName": "LvPlan", "MethodName": "ReceiveLvPlan", "Data": [10], "ServerId": 1})["Status"], -1)
            prof.state["player"]["Diamond"] = 100
            r10 = emu.handle_rpc({"ModuleName": "LvPlan", "MethodName": "ReceiveLvPlan", "Data": [10], "ServerId": 1})
            self.assertEqual(r10["Status"], 0)
            self.assertEqual(prof.state["player"]["Diamond"], 200)

    def test_38_r7_5_event_clock_and_archive_modes(self) -> None:
        """R7.5: EventClock (UTC+7/fixed/advance/TimeTick) & EventArchive (scheduled/rotating/manual) + instance isolation."""
        import datetime as _dt

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            # Anchor at 2026-01-01 12:30:00 UTC+7
            vn_tz = _dt.timezone(_dt.timedelta(hours=7))
            ts_day1 = int(_dt.datetime(2026, 1, 1, 12, 30, 0, tzinfo=vn_tz).timestamp())
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            emu.clock.set_fixed(ts_day1)
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=28)

            # TimeTick follows EventClock cleanly
            init_res = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertEqual(init_res["TimeTick"], ts_day1)
            mods = {m["SubModuleId"]: m["IfOpen"] for m in init_res["Value"]["ModulesInfo"]}
            self.assertEqual(mods.get(4400), 1)
            self.assertEqual(mods.get(6300), 0)
            self.assertEqual(mods.get(6400), 0)
            self.assertEqual(init_res["Avatar"]["TimedActivityOpenInfo"]["9300"][0]["ActivityId"], 81)

            # Scheduled mode: upcoming -> active -> ended
            prof.event_runtime.set_scheduled_window("timed_recruit:82", ts_day1 + 1000, ts_day1 + 5000)
            ev_up = prof.event_runtime.evaluate("timed_recruit:82", prof.state["player"])
            self.assertEqual(ev_up.status, "upcoming")
            self.assertNotIn("9300", prof._build_timed_activity_open_info())
            emu.clock.set_fixed(ts_day1 + 1500)
            ev_act = prof.event_runtime.evaluate("timed_recruit:82", prof.state["player"])
            self.assertEqual(ev_act.status, "active")
            self.assertEqual(prof._build_timed_activity_open_info()["9300"][0]["ActivityId"], 82)
            emu.clock.set_fixed(ts_day1 + 6000)
            ev_end = prof.event_runtime.evaluate("timed_recruit:82", prof.state["player"])
            self.assertEqual(ev_end.status, "ended")
            self.assertNotIn("9300", prof._build_timed_activity_open_info())

            # Manual archive: activate 81, earn credit, activate 82, then reactivate 81 -> new instance_id, old history preserved, zero auto-unlocks
            prof.event_runtime.activate_manual_event("timed_recruit:81", duration_sec=3600)
            iid1 = prof.event_runtime.evaluate("timed_recruit:81", prof.state["player"]).instance_id
            emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [1], "ServerId": 1})
            self.assertEqual(prof.event_runtime.get_instance(iid1)["progress"]["my_credit"], 10)

            prof.event_runtime.activate_manual_event("timed_recruit:82", duration_sec=3600)
            self.assertEqual(prof._build_timed_activity_open_info()["9300"][0]["ActivityId"], 82)
            emu.clock.advance(10)
            prof.event_runtime.activate_manual_event("timed_recruit:81", duration_sec=3600)
            iid2 = prof.event_runtime.evaluate("timed_recruit:81", prof.state["player"]).instance_id
            self.assertNotEqual(iid1, iid2)
            self.assertEqual(prof.event_runtime.get_instance(iid2)["progress"].get("my_credit", 0), 0)
            hist_iids = {h["instance_id"]: h for h in prof.state["event_runtime"]["archive_history"]}
            self.assertIn(iid1, hist_iids)
            self.assertEqual(hist_iids[iid1]["progress"]["my_credit"], 10)

            # Rotating mode alternates 81 -> 82 -> 81
            anchor = int(_dt.datetime(2026, 1, 1, 0, 0, 0, tzinfo=vn_tz).timestamp())
            prof.event_runtime.configure_archive_mode("rotating", rotation_anchor_ts=anchor, rotation_duration_sec=259200)
            emu.clock.set_fixed(anchor + 100)
            self.assertEqual(prof._build_timed_activity_open_info()["9300"][0]["ActivityId"], 81)
            emu.clock.set_fixed(anchor + 259200 + 100)
            self.assertEqual(prof._build_timed_activity_open_info()["9300"][0]["ActivityId"], 82)
            emu.clock.set_fixed(anchor + 2 * 259200 + 100)
            self.assertEqual(prof._build_timed_activity_open_info()["9300"][0]["ActivityId"], 83)
            emu.clock.set_fixed(anchor + 3 * 259200 + 100)
            self.assertEqual(prof._build_timed_activity_open_info()["9300"][0]["ActivityId"], 81)

    def test_39_r7_5_daily_dinner_vit_windows(self) -> None:
        """R7.5: PlayerVIT.ReceiveVIT enforces VN time windows (12-14, 18-20, 21-22), anti-duplicate & daily reset."""
        import datetime as _dt

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            vn_tz = _dt.timezone(_dt.timedelta(hours=7))
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            prof._sync_player_recover_times()
            vit0 = int(prof.state["player"]["VIT"])
            sta0 = int(prof.state["player"]["STA"])

            # 10:00 -> outside window
            emu.clock.set_fixed(int(_dt.datetime(2026, 2, 1, 10, 0, 0, tzinfo=vn_tz).timestamp()))
            r_out = emu.handle_rpc({"ModuleName": "PlayerVIT", "MethodName": "ReceiveVIT", "Data": [], "ServerId": 1})
            self.assertEqual(r_out["Status"], -1)
            self.assertEqual(r_out["Avatar"]["RedDotInfo"]["2706"], 0)

            # 12:30 -> noon window active, claim once then block duplicate
            emu.clock.set_fixed(int(_dt.datetime(2026, 2, 1, 12, 30, 0, tzinfo=vn_tz).timestamp()))
            chk = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertEqual(chk["Avatar"]["RedDotInfo"]["2706"], 1)
            r_win0 = emu.handle_rpc({"ModuleName": "PlayerVIT", "MethodName": "ReceiveVIT", "Data": [], "ServerId": 1})
            self.assertEqual(r_win0["Status"], 0)
            self.assertEqual(r_win0["Avatar"]["RedDotInfo"]["2706"], 0)
            self.assertEqual(prof.state["player"]["VIT"], vit0 + 50)
            self.assertEqual(prof.state["player"]["STA"], sta0 + 20)
            self.assertEqual(emu.handle_rpc({"ModuleName": "PlayerVIT", "MethodName": "ReceiveVIT", "Data": [], "ServerId": 1})["Status"], -1)

            # 18:30 -> second window active; 21:15 -> third window active
            emu.clock.set_fixed(int(_dt.datetime(2026, 2, 1, 18, 30, 0, tzinfo=vn_tz).timestamp()))
            self.assertEqual(emu.handle_rpc({"ModuleName": "PlayerVIT", "MethodName": "ReceiveVIT", "Data": [], "ServerId": 1})["Status"], 0)
            emu.clock.set_fixed(int(_dt.datetime(2026, 2, 1, 21, 15, 0, tzinfo=vn_tz).timestamp()))
            self.assertEqual(emu.handle_rpc({"ModuleName": "PlayerVIT", "MethodName": "ReceiveVIT", "Data": [], "ServerId": 1})["Status"], 0)
            self.assertEqual(prof.state["player"]["VIT"], vit0 + 150)

            # Next day 12:30 -> resets cleanly
            emu.clock.set_fixed(int(_dt.datetime(2026, 2, 2, 12, 30, 0, tzinfo=vn_tz).timestamp()))
            self.assertEqual(emu.handle_rpc({"ModuleName": "PlayerVIT", "MethodName": "ReceiveVIT", "Data": [], "ServerId": 1})["Status"], 0)

    def test_40_r7_5_daily_task_full_flow_and_reset(self) -> None:
        """R7.5: DailyTaskInfo progression via real gameplay, GetCredit, DrawReward EXP/level, OneKey, persistence & daily reset."""
        import datetime as _dt

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            vn_tz = _dt.timezone(_dt.timedelta(hours=7))
            ts_d1 = int(_dt.datetime(2026, 3, 10, 14, 0, 0, tzinfo=vn_tz).timestamp())
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            emu.clock.set_fixed(ts_d1)
            prof = emu.get_profile_by_name("normal")

            # Locked below Lv 25
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetDaliyTaskInfo", "Data": [], "ServerId": 1})["Status"],
                -1,
            )

            prof.admin_prepare_account(target_lv=25)
            sample_eq = next(int(k) for k in prof.game_data["equips"])
            prof.admin_grant(
                resources=[
                    {"type": "Diamond", "amount": 5000},
                    {"type": "Gold", "amount": 500000},
                    {"type": "HeroEXP", "amount": 100000},
                    {"type": "VIT", "amount": 100},
                    {"type": "STA", "amount": 50},
                ],
                equips=[{"model_id": sample_eq, "slot_id": 1}],
            )
            prof.state["battle"]["StarCount"] = 50
            prof.state["player"]["StarId"] = 0

            dt_info = emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetDaliyTaskInfo", "Data": [], "ServerId": 1})
            self.assertEqual(dt_info["Status"], 0)
            self.assertEqual(len(dt_info["Value"]["TasksInfo"]), 25)
            self.assertEqual(len(dt_info["Value"]["RewardInfo"]), 5)

            # Perform real actions: LightenStar (#4), EquipLvUpForCount (#27), HeroLvUp (#28), TimedRecruit 10x -> spends >300 Dia (#23)
            self.assertEqual(emu.handle_rpc({"ModuleName": "LightenStar", "MethodName": "LightenStar", "Data": [], "ServerId": 1})["Status"], 0)
            eq_id = prof.state["equips"][0]["Id"]
            self.assertEqual(emu.handle_rpc({"ModuleName": "Equip", "MethodName": "EquipLvUpForCount", "Data": [eq_id, 1], "ServerId": 1})["Status"], 0)
            hid = prof.state["heroes"][0]["Id"]
            prof.state["heroes"][0]["Lv"] = 1
            self.assertEqual(emu.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [hid, 1], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [30], "ServerId": 1})["Status"], 0)

            after_act = emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetDaliyTaskInfo", "Data": [], "ServerId": 1})
            self.assertEqual(after_act["Avatar"]["RedDotInfo"]["3000"], 1)
            by_id = {t["Id"]: t for t in after_act["Value"]["TasksInfo"]}
            for check_tid in (4, 27, 28, 23):
                self.assertEqual(by_id[check_tid]["Status"], 1, f"task {check_tid} should complete")
                self.assertTrue(by_id[check_tid]["CanDrawCredit"])

            # Claim credits -> TotalCredit reaches 40 (5 + 10 + 5 + 20) >= 30 chest!
            gold_before = int(prof.state["player"]["Gold"])
            for tid in (4, 27, 28, 23):
                c_res = emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetCredit", "Data": [tid], "ServerId": 1})
                self.assertEqual(c_res["Status"], 0)
            # Duplicate credit claim rejected
            self.assertEqual(emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetCredit", "Data": [23], "ServerId": 1})["Status"], -1)
            self.assertGreater(int(prof.state["player"]["Gold"]), gold_before)

            cur = emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetDaliyTaskInfo", "Data": [], "ServerId": 1})["Value"]
            self.assertEqual(cur["TotalCredit"], 40)
            chest30 = next(r for r in cur["RewardInfo"] if r["NeedCredit"] == 30)
            self.assertEqual(chest30["Status"], 1)

            # Claim chest 30 -> EXP gain & items & anti-duplicate
            exp_before = int(prof.state["player"]["EXP"])
            dr = emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "DrawReward", "Data": [30], "ServerId": 1})
            self.assertEqual(dr["Status"], 0)
            self.assertGreater(int(prof.state["player"]["EXP"]), exp_before)
            self.assertEqual(
                next(r for r in dr["Value"]["RewardInfo"] if r["NeedCredit"] == 30)["Status"],
                2,
            )
            self.assertEqual(emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "DrawReward", "Data": [30], "ServerId": 1})["Status"], -1)

            # OneKeyDone on Task 24 (cost 10 Dia) -> sets Status=1, CanDrawCredit=True
            dia_pre = int(prof.state["player"]["Diamond"])
            ok1 = emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "OneKeyDone", "Data": [24], "ServerId": 1})
            self.assertEqual(ok1["Status"], 0)
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia_pre - 10)
            self.assertTrue(next(t for t in ok1["Value"]["TasksInfo"] if t["Id"] == 24)["CanDrawCredit"])

            # Persistence across reload
            emu2 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            emu2.clock.set_fixed(ts_d1)
            reloaded = emu2.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetDaliyTaskInfo", "Data": [], "ServerId": 1})["Value"]
            self.assertEqual(reloaded["TotalCredit"], 40)
            self.assertEqual(next(r for r in reloaded["RewardInfo"] if r["NeedCredit"] == 30)["Status"], 2)

            # Advance +1 day -> fresh daily instance (TotalCredit=0, tasks=0), yesterday archived!
            emu2.clock.set_fixed(ts_d1 + 86400)
            next_day = emu2.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetDaliyTaskInfo", "Data": [], "ServerId": 1})["Value"]
            self.assertEqual(next_day["TotalCredit"], 0)
            self.assertEqual(next(r for r in next_day["RewardInfo"] if r["NeedCredit"] == 30)["Status"], 0)
            hist_ids = [h["instance_id"] for h in emu2.get_profile_by_name("normal").state["event_runtime"]["archive_history"]]
            self.assertIn("daily_task:2026-03-10", hist_ids)

    def test_41_r7_5_timed_recruit_full_cycle_bless_rank_and_rotation(self) -> None:
        """R7.5: TimedRecruit 81->82 free CD, 10x Orange pity, 6 credit chests, Bless->UR ChoiceBox, rank settlement->RewardCenter, expiry block."""
        import datetime as _dt

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            vn_tz = _dt.timezone(_dt.timedelta(hours=7))
            anchor = int(_dt.datetime(2026, 4, 1, 0, 0, 0, tzinfo=vn_tz).timestamp())
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            emu.clock.set_fixed(anchor + 100)
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=15)
            prof.event_runtime.configure_archive_mode("rotating", rotation_anchor_ts=anchor, rotation_duration_sec=259200)
            prof.admin_grant(resources=[{"type": "Diamond", "amount": 60000}])

            info0 = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [], "ServerId": 1})
            self.assertEqual(info0["Status"], 0)
            self.assertEqual(info0["Value"]["ActivityEnumId"], 81)
            self.assertEqual(info0["Value"]["MyRank"], 0)
            self.assertEqual(len(info0["Value"]["RankList"]), 25)

            # Free summon once, blocks during 72000s CD
            p_free = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [1], "ServerId": 1})
            self.assertEqual(p_free["Status"], 0)
            self.assertEqual(p_free["Value"]["RecruitInfo"]["MyCredit"], 10)
            self.assertEqual(p_free["Value"]["RecruitInfo"]["CooledTime"], anchor + 100 + 72000)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [1], "ServerId": 1})["Status"], -1)

            # 10x pulls until credit >= 600; verify Orange (q=15) hero included and MyRank updates
            dia0 = int(prof.state["player"]["Diamond"])
            for _ in range(6):
                p10 = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [30], "ServerId": 1})
                self.assertEqual(p10["Status"], 0)
                pulled_hids = [h["HeroModelId"] for h in p10["Value"]["BaseGetGameResourceList"][0]["Hero"]]
                self.assertTrue(any(int(prof.game_data["heroes"][str(hid)]["quality"]) >= 15 for hid in pulled_hids))
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia0 - 6 * 2800)

            snap = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [], "ServerId": 1})["Value"]
            self.assertEqual(snap["MyCredit"], 610)
            self.assertGreater(snap["MyRank"], 0)

            # Sequential credit chests 60 -> 600 unlock Bless
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "DrawCreditReward", "Data": [200], "ServerId": 1})["Status"], -1)
            for thresh in (60, 200, 300, 400, 500, 600):
                cr = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "DrawCreditReward", "Data": [thresh], "ServerId": 1})
                self.assertEqual(cr["Status"], 0)
                self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "DrawCreditReward", "Data": [thresh], "ServerId": 1})["Status"], -1)
            self.assertEqual(cr["Value"]["BlessNum"], 320)

            # Pull until Bless triggers DrawGoldHero == 0 (320 + 79*5 = 715 -> floor(715*0.7) >= 500 deterministic) -> claim Sesshomaru (12012005, quality=18)
            for _ in range(90):
                cur_s = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [], "ServerId": 1})["Value"]
                if cur_s["DrawGoldHero"] == 0:
                    break
                r1 = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [3], "ServerId": 1})
                self.assertEqual(r1["Status"], 0)
                if r1["Value"]["RecruitInfo"]["DrawGoldHero"] == 0:
                    break
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [], "ServerId": 1})["Value"]["DrawGoldHero"], 0)

            # Reject hero outside 16060008 before granting valid UR
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "DrawGoldHero", "Data": [12011002], "ServerId": 1})["Status"], -3123)
            ur_ok = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "DrawGoldHero", "Data": [12012005], "ServerId": 1})
            self.assertEqual(ur_ok["Status"], 0)
            self.assertEqual(ur_ok["Value"]["RecruitInfo"]["DrawGoldHero"], 1)
            self.assertTrue(any(int(h["HeroModelId"]) == 12012005 for h in prof.state["heroes"]))

            # Rotate to Banner 82 -> Period 1 (Banner 81) settles Rank Reward into RewardCenter ONCE!
            emu.clock.set_fixed(anchor + 259200 + 100)
            info_b2 = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [], "ServerId": 1})
            self.assertEqual(info_b2["Status"], 0)
            self.assertEqual(info_b2["Value"]["ActivityEnumId"], 82)
            self.assertEqual(info_b2["Value"]["MyCredit"], 0)
            self.assertEqual(info_b2["Avatar"]["TimedActivityOpenInfo"]["9300"][0]["ActivityId"], 82)
            self.assertEqual(info_b2["Avatar"]["RedDotInfo"]["2400"], 1)

            rc_list = emu.handle_rpc({"ModuleName": "Reward", "MethodName": "Rewars", "Data": [], "ServerId": 1})["Value"]
            self.assertEqual(len(rc_list), 1)
            rc_id = rc_list[0]["Id"]
            rc_claim = emu.handle_rpc({"ModuleName": "Reward", "MethodName": "DrawGiftBags", "Data": [[rc_id]], "ServerId": 1})
            self.assertEqual(rc_claim["Status"], 0)
            self.assertEqual(rc_claim["Avatar"]["RedDotInfo"]["2400"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Reward", "MethodName": "DrawGiftBags", "Data": [[rc_id]], "ServerId": 1})["Status"], -1)

            # Expired scheduled event blocks all actions
            prof.event_runtime.set_scheduled_window("timed_recruit:82", anchor, anchor + 3600)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [], "ServerId": 1})["Status"], -1)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [3], "ServerId": 1})["Status"], -1)

    def test_42_r7_5_xxbz_combat_damage_milestones_buy_and_reset(self) -> None:
        """R7.5: Xxbz 3 bosses, Lv 28/30 gates, TreasureId in FightInfo, damage->Gold formula, 100-Dia milestones, VIP BuyCount & daily reset."""
        import datetime as _dt

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            vn_tz = _dt.timezone(_dt.timedelta(hours=7))
            ts_d1 = int(_dt.datetime(2026, 5, 1, 15, 0, 0, tzinfo=vn_tz).timestamp())
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            emu.clock.set_fixed(ts_d1)
            prof = emu.get_profile_by_name("normal")

            self.assertEqual(emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "GetInfo", "Data": [], "ServerId": 1})["Status"], -1)
            prof.admin_prepare_account(target_lv=28, vip_lv=6)
            prof.admin_grant(resources=[{"type": "Diamond", "amount": 500}, {"type": "Gold", "amount": 10000}])

            # Boss 3 requires Lv 30 -> rejected at Lv 28
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "GetFightInfo", "Data": [3], "ServerId": 1})["Status"], -1)

            x_info = emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "GetInfo", "Data": [], "ServerId": 1})["Value"]
            self.assertEqual(x_info["RemainNum"], 3)
            self.assertEqual([b["TreasureId"] for b in x_info["XxbzList"]], [1, 2, 3])

            fi = emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "GetFightInfo", "Data": [1], "ServerId": 1})
            self.assertEqual(fi["Status"], 0)
            self.assertEqual(fi["Value"]["FightInfo"]["TreasureId"], 1)

            # Submit Fight with verified boss PosId=8 HP loss = 120,000 dmg
            gold0 = int(prof.state["player"]["Gold"])
            verify_payload = json.dumps({"hp": [[{"PosId": 8, "HP": 25_000_000 - 120_000}]]})
            fg = emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "Fight", "Data": [1, 1, verify_payload, 120_000, 0, False], "ServerId": 1})
            self.assertEqual(fg["Status"], 0)
            expected_gold = prof._calc_xxbz_damage_reward(1, 120_000)
            self.assertEqual(int(prof.state["player"]["Gold"]), gold0 + expected_gold)
            self.assertTrue(any(g["GoodsModelId"] == 16050092 and g["Num"] >= 2 for g in prof.state["goods"]))
            b1 = next(b for b in fg["Value"]["XxbzList"] if b["TreasureId"] == 1)
            self.assertEqual(b1["HighestHurt"], 120_000)
            self.assertEqual(b1["RemainCount"], 0)
            # Hooks to DailyTask #30 & SuccessTarget #26/#33
            self.assertEqual(prof.state["stats"]["mystery_treasure_count"], 1)
            self.assertEqual(prof.state["stats"]["mystery_treasure_max_dmg"], 120_000)
            dt_list = emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetDaliyTaskInfo", "Data": [], "ServerId": 1})["Value"]["TasksInfo"]
            self.assertEqual(next(t for t in dt_list if t["Id"] == 30)["Status"], 1)

            # Milestone claims (30k & 60k grant 100 Dia each, 200k rejected) + anti-duplicate
            dia0 = int(prof.state["player"]["Diamond"])
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "DrawReward", "Data": [1, 30000], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "DrawReward", "Data": [1, 60000], "ServerId": 1})["Status"], 0)
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia0 + 200)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "DrawReward", "Data": [1, 60000], "ServerId": 1})["Status"], -1)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "DrawReward", "Data": [1, 200000], "ServerId": 1})["Status"], -1)

            # VIP 6 allows 1 BuyCount (20 Dia), blocks 2nd buy
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "GetFightInfo", "Data": [1], "ServerId": 1})["Status"], -1)
            buy1 = emu.handle_rpc({"ModuleName": "XxbzInfo", "MethodName": "BuyCount", "Data": [1], "ServerId": 1})
            self.assertEqual(buy1["Status"], 0)
            self.assertEqual(buy1["Value"]["XxbzInfo"]["BuyCount"], 1)
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia0 + 180)
            self.assertEqual(emu.handle_rpc({"ModuleName": "XxbzInfo", "MethodName": "BuyCount", "Data": [1], "ServerId": 1})["Status"], -1)

            # Next day resets RemainCount & BuyCount while lifetime HighestHurt/DrawnMaxNum stay!
            emu.clock.set_fixed(ts_d1 + 86400)
            x_next = emu.handle_rpc({"ModuleName": "Xxbz", "MethodName": "GetInfo", "Data": [], "ServerId": 1})["Value"]
            self.assertEqual(x_next["XxbzInfo"]["BuyCount"], 0)
            self.assertEqual(x_next["RemainNum"], 3)
            b1_next = next(b for b in x_next["XxbzList"] if b["TreasureId"] == 1)
            self.assertEqual(b1_next["HighestHurt"], 120_000)
            self.assertEqual(b1_next["DrawnMaxNum"], 60_000)

    def test_43_r7_5_http_admin_clock_and_events_integration(self) -> None:
        """R7.5: Live HTTP /admin/clock and /admin/events endpoints + auth guard + persistence across server restart."""
        import http.client

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "dev_saves"
            srv1 = ThreadingEmulatorServer(
                ("127.0.0.1", 0),
                persist=True,
                quiet=True,
                new_player=True,
                env="dev",
                data_dir=data_dir,
                trace_path=data_dir / "trace.log",
                admin_token="r75_test_tok",
            )
            t1 = threading.Thread(target=srv1.serve_forever, daemon=True)
            t1.start()
            try:
                port = srv1.server_port

                # Unauthorized admin clock POST blocked (401)
                c_unauth = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                c_unauth.request("POST", "/admin/clock", body=b'{"action":"advance","delta_sec":3600}', headers={"Content-Type": "application/json"})
                self.assertEqual(c_unauth.getresponse().status, 401)
                c_unauth.close()

                # Set fixed clock & activate manual event 82
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                hdrs = {"Content-Type": "application/json", "X-Admin-Token": "r75_test_tok"}
                c.request("POST", "/admin/clock", body=json.dumps({"action": "fixed", "fixed_ts": 1770000000}).encode(), headers=hdrs)
                clk_res = json.loads(c.getresponse().read())
                self.assertTrue(clk_res["ok"])
                self.assertEqual(clk_res["clock"]["now"], 1770000000)

                c.request("POST", "/admin/events", body=json.dumps({"action": "activate", "event_id": "timed_recruit:82", "duration_sec": 7200}).encode(), headers=hdrs)
                ev_res = json.loads(c.getresponse().read())
                self.assertEqual(ev_res["archive_config"]["mode"], "manual")
                self.assertEqual(ev_res["events"]["timed_recruit:82"]["status"], "active")
                c.close()
            finally:
                srv1.shutdown()
                srv1.server_close()

            # Restart server -> persisted clock & manual archive intact
            srv2 = ThreadingEmulatorServer(
                ("127.0.0.1", 0),
                persist=True,
                quiet=True,
                new_player=False,
                env="dev",
                data_dir=data_dir,
                trace_path=data_dir / "trace.log",
                admin_token="r75_test_tok",
            )
            t2 = threading.Thread(target=srv2.serve_forever, daemon=True)
            t2.start()
            try:
                c2 = http.client.HTTPConnection("127.0.0.1", srv2.server_port, timeout=5)
                c2.request("GET", "/admin/events", headers={"X-Admin-Token": "r75_test_tok"})
                st_res = json.loads(c2.getresponse().read())
                self.assertEqual(st_res["clock"]["now"], 1770000000)
                self.assertEqual(st_res["events"]["timed_recruit:82"]["status"], "active")
                c2.close()
            finally:
                srv2.shutdown()
                srv2.server_close()

    def test_44_r7_6_far_chapter_combat_and_boss_node_scaling(self) -> None:
        """R7.6: Far chapters 15/30/50/70/80 scaling, X20 >= X19 enemy strength fix, needLV gate & chapter rewards."""
        from combat_sim import simulate_fight_info

        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=Path(td) / "saves")
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=20)
            # Lv 20 player blocked from Ch 30 (needLV=31) and Ch 70 (needLV=71)
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [30, 3011, 1], "ServerId": 1})["Status"],
                -1,
            )
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [70, 7011, 1], "ServerId": 1})["Status"],
                -1,
            )

            # Node X20 mob wave scaling must be >= X19 (previously X20 % 10 == 0 made stage 10 weaker than stage 9!)
            for x19, x20 in ((1519, 1520), (3019, 3020), (5019, 5020), (7019, 7020), (8019, 8020)):
                n19 = prof.game_data["nodes"][str(x19)]
                n20 = prof.game_data["nodes"][str(x20)]
                w19, _ = prof._build_enemy_wave(x19, n19, 1, 1, 1)
                w20, _ = prof._build_enemy_wave(x20, n20, 1, 1, 1)
                self.assertGreaterEqual(w20[0]["HP"], w19[0]["HP"], f"Expected mob HP {x20} >= {x19}")

            # 6-hero level-matched squad across Ch 30/50/70/80 completes final nodes cleanly via simulate_fight_info
            team_hids = [12011002, 12011003, 12011004, 12011005, 12011006]
            for idx, hm in enumerate(team_hids, start=2):
                h = prof._build_hero_instance(hm, lv=15, step=1)
                prof.state["heroes"].append(h)
                prof.state["slots"][idx - 1]["HeroId"] = h["Id"]
                prof.state["slots"][idx - 1]["HeroModelId"] = hm

            for cid, lv, step in ((30, 31, 3), (50, 51, 5), (70, 71, 7), (80, 80, 8)):
                prof.state["player"]["Lv"] = lv
                prof.state["player"]["VIT"] = 200
                prof.state["chapters"][str(cid)] = prof._make_chapter_state(cid)
                nid = cid * 100 + 20
                prof.state["nodes"][str(nid)] = prof._make_node_state(nid, flag=1)
                for h in prof.state["heroes"]:
                    h["Lv"] = lv
                    h["Step"] = step
                prof._recalc_all_slots_and_fap()
                fi_res = emu.handle_rpc({"ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [cid, nid, 1], "ServerId": 1})
                self.assertEqual(fi_res["Status"], 0)
                combat = simulate_fight_info(fi_res["Value"]["FightInfo"], prof.game_data["attacks"])
                self.assertTrue(combat.won, f"Expected Lv {lv} Step+{step} squad to clear Ch {cid} Node {nid}")
                fg_res = emu.handle_rpc(
                    {
                        "ModuleName": "Battle",
                        "MethodName": "Fight",
                        "Data": [cid, nid, 1, True, json.dumps(combat.verify_data), 0],
                        "ServerId": 1,
                    }
                )
                self.assertEqual(fg_res["Status"], 0)
                self.assertTrue(int(fg_res["Value"]["CurrentNode"]["StarCount"]) >= 1)

    def test_45_r7_6_zcsf_lucky_cat_and_xhzw_goddess_kiss(self) -> None:
        """R7.6: Zcsf (2711) & Xhzw (2303) full gameplay, economy ledger, DailyTask #16/#8 & 00:00 UTC+7 reset."""
        import datetime as _dt

        with tempfile.TemporaryDirectory() as td:
            vn_tz = _dt.timezone(_dt.timedelta(hours=7))
            ts_d1 = int(_dt.datetime(2026, 6, 10, 14, 0, 0, tzinfo=vn_tz).timestamp())
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=Path(td) / "saves")
            emu.clock.set_fixed(ts_d1)
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=20, vip_lv=3)
            prof.admin_grant(
                resources=[{"type": "Diamond", "amount": 2000}],
                items=[{"id": 16050012, "num": 2}],
            )

            # Lv 20 blocks Zcsf (openLv=21) & Xhzw (openLv=30)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Zcsf", "MethodName": "ZcsfInfo", "Data": [], "ServerId": 1})["Status"], -1)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "GetXhzwInfo", "Data": [], "ServerId": 1})["Status"], -1)

            # Unlock Zcsf at Lv 21
            prof.admin_prepare_account(target_lv=21, vip_lv=3)
            z_info = emu.handle_rpc({"ModuleName": "Zcsf", "MethodName": "ZcsfInfo", "Data": [], "ServerId": 1})
            self.assertEqual(z_info["Status"], 0)
            self.assertEqual(z_info["Value"]["ZcNum"], 0)
            self.assertEqual(z_info["Value"]["ActiveSF"], 1)
            self.assertEqual(z_info["Avatar"]["RedDotInfo"]["2711"], 1)

            gold0 = int(prof.state["player"]["Gold"])
            dia0 = int(prof.state["player"]["Diamond"])
            zc1 = emu.handle_rpc({"ModuleName": "Zcsf", "MethodName": "ZC", "Data": [1], "ServerId": 1})
            self.assertEqual(zc1["Status"], 0)
            self.assertEqual(zc1["Value"]["GoldInfo"]["Gold"], 1300 * 21)
            self.assertEqual(int(prof.state["player"]["Gold"]), gold0 + 1300 * 21)
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia0 - 10)
            self.assertEqual(zc1["Value"]["ZcsfInfo"]["ZcNum"], 1)

            # VIP 3 limit (ZCSFMaxNum) exhaustion & DailyTask #16 progress
            max_zc = prof._zcsf_max_count()
            for _ in range(max_zc - 1):
                self.assertEqual(emu.handle_rpc({"ModuleName": "Zcsf", "MethodName": "ZC", "Data": [1], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Zcsf", "MethodName": "ZC", "Data": [1], "ServerId": 1})["Status"], -1)

            # Unlock Xhzw at Lv 30 & DailyTask #8 (#16 also verifiable here)
            prof.admin_prepare_account(target_lv=30, vip_lv=3)
            x0 = emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "GetXhzwInfo", "Data": [], "ServerId": 1})
            self.assertEqual(x0["Status"], 0)
            self.assertEqual(len(x0["Value"]["XhzwRewardInfo"]), 10)
            self.assertEqual(x0["Avatar"]["RedDotInfo"]["2303"], 1)

            # Turn -> AlterLuck (type 1 free, type 2 item 16050012, type 3 Dia 20) -> Lock -> claim reward
            for turn_idx in range(5):
                turn_r = emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "XhzwTurn", "Data": [], "ServerId": 1})
                self.assertEqual(turn_r["Status"], 0)
                cur_lip = turn_r["Value"]["LipNum"]
                if cur_lip < 6:
                    alt1 = emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "XhzwAlterLuck", "Data": [1], "ServerId": 1})
                    self.assertEqual(alt1["Status"], 0)
                    self.assertGreaterEqual(alt1["Value"]["LipNum"], min(6, cur_lip + 1))
                lock_r = emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "XhzwAlterLuckLock", "Data": [], "ServerId": 1})
                self.assertEqual(lock_r["Status"], 0)
                self.assertEqual(lock_r["Value"]["LipNum"], 0)
            # 6th turn rejected (maxNum == 5)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "XhzwTurn", "Data": [], "ServerId": 1})["Status"], -1)

            x_after = emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "GetXhzwInfo", "Data": [], "ServerId": 1})["Value"]
            self.assertGreaterEqual(x_after["Integral"], 10)
            claim_x = emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "ReceiveRewardForOneKey", "Data": [], "ServerId": 1})
            self.assertEqual(claim_x["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "ReceiveRewardForOneKey", "Data": [], "ServerId": 1})["Status"], -1)

            dt = emu.handle_rpc({"ModuleName": "DailyTaskInfo", "MethodName": "GetDaliyTaskInfo", "Data": [], "ServerId": 1})["Value"]["TasksInfo"]
            self.assertEqual(next(t for t in dt if t["Id"] == 16)["Status"], 1)
            self.assertEqual(next(t for t in dt if t["Id"] == 8)["Status"], 1)

            # Advance across 00:00 UTC+7 -> both Zcsf & Xhzw reset cleanly
            emu.clock.set_fixed(ts_d1 + 86400)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Zcsf", "MethodName": "ZcsfInfo", "Data": [], "ServerId": 1})["Value"]["ZcNum"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Xhzw", "MethodName": "GetXhzwInfo", "Data": [], "ServerId": 1})["Value"]["TurnCount"], 0)

    def test_46_r7_6_limitthebounty_and_treasure_lv_step_and_rebirth(self) -> None:
        """R7.6: Limitthebounty (6900), Treasure LvUp/StepUp (1402/1404) & Hero/Equip/Treasure Rebirth refunds."""
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=Path(td) / "saves")
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=12)
            # TriggerLv 12 opened, cannot claim until Lv 15
            b0 = emu.handle_rpc({"ModuleName": "Limitthebounty", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(b0["Value"]["TriggerLv"], 12)
            self.assertGreater(b0["Value"]["EndDate"], emu.clock.now())
            self.assertEqual(emu.handle_rpc({"ModuleName": "Limitthebounty", "MethodName": "ReceivedReward", "Data": [], "ServerId": 1})["Status"], -1)

            prof.admin_prepare_account(target_lv=15)
            init_r = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            self.assertEqual(init_r["Value"]["PlayerInfo"]["LimitthebountyTriggerLv"], 12)
            self.assertEqual(init_r["Avatar"]["RedDotInfo"]["6900"], 1)
            dia_before = int(prof.state["player"]["Diamond"])
            b_claim = emu.handle_rpc({"ModuleName": "Limitthebounty", "MethodName": "ReceivedReward", "Data": [], "ServerId": 1})
            self.assertEqual(b_claim["Status"], 0)
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia_before + 288)
            self.assertEqual(prof.state["player"]["LimitthebountyTriggerLv"], 15)

            # Treasure LvUp (1402) & StepUp (1404) + FAP update
            prof.admin_prepare_account(target_lv=35)
            prof.admin_grant(
                resources=[
                    {"type": "Gold", "amount": 500000},
                    {"type": "Diamond", "amount": 2000},
                    {"type": "HeroEXP", "amount": 100000},
                ],
                items=[
                    {"id": 16050001, "num": 500},
                    {"id": 16050020, "num": 5},
                    {"id": 14011615, "num": 1},
                    {"id": 14010803, "num": 12},
                ],
            )
            tr_target = next(t for t in prof.state["treasures"] if int(t["TreasureModelId"]) == 14011615)
            fodders = [t["Id"] for t in prof.state["treasures"] if int(t["TreasureModelId"]) == 14010803]
            # Equip Book first to verify FAP boosts on TreasureLvUp & TreasureStepUp
            self.assertEqual(
                emu.handle_rpc(
                    {"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [1, "", "", "", "", tr_target["Id"], ""], "ServerId": 1}
                )["Status"],
                0,
            )
            fap_base = int(prof.state["player"]["FAP"])
            tlv = emu.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureLvUp", "Data": [tr_target["Id"], fodders], "ServerId": 1})
            self.assertEqual(tlv["Status"], 0)
            self.assertGreaterEqual(tlv["Value"]["Lv"], 5)
            self.assertGreater(int(prof.state["player"]["FAP"]), fap_base)
            fap_after_lv = int(prof.state["player"]["FAP"])

            tstep = emu.handle_rpc(
                {"ModuleName": "Treasure", "MethodName": "TreasureStepUp", "Data": [tr_target["Id"], [], 0], "ServerId": 1}
            )
            self.assertEqual(tstep["Status"], 0)
            self.assertEqual(tstep["Value"]["Step"], 1)
            self.assertGreater(int(prof.state["player"]["FAP"]), fap_after_lv)

            # Deployed hero/equipped treasure cannot be reborn -> unequip Treasure then Rebirth
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureRebirth", "Data": [[tr_target["Id"]]], "ServerId": 1})["Status"],
                -1,
            )
            self.assertEqual(
                emu.handle_rpc(
                    {"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [1, "", "", "", "", "00000000-0000-0000-0000-000000000000", ""], "ServerId": 1}
                )["Status"],
                0,
            )
            stone_before = next(g["Num"] for g in prof.state["goods"] if g["GoodsModelId"] == 16050020)
            tr_rb = emu.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureRebirth", "Data": [[tr_target["Id"]]], "ServerId": 1})
            self.assertEqual(tr_rb["Status"], 0)
            self.assertIsInstance(tr_rb["Value"]["TreasureInfo"], dict)
            self.assertEqual(tr_rb["Value"]["TreasureInfo"]["Lv"], 0)
            self.assertEqual(tr_rb["Value"]["TreasureInfo"]["Step"], 0)
            self.assertEqual(next(g["Num"] for g in prof.state["goods"] if g["GoodsModelId"] == 16050020), stone_before + 3)

            # Hero LvUp + StepUp + HeroRebirth + EquipLvUp + EquipRebirth
            side_hero = prof._build_hero_instance(12011002, lv=1, step=0)
            prof.state["heroes"].append(side_hero)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [side_hero["Id"], 15], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroStepUp", "Data": [side_hero["Id"], []], "ServerId": 1})["Status"], 0)
            self.assertEqual(side_hero["Step"], 1)
            soul_before = int(prof.state["player"]["HeroEXP"])
            hr_rb = emu.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroRebirth", "Data": [[side_hero["Id"]]], "ServerId": 1})
            self.assertEqual(hr_rb["Status"], 0)
            self.assertEqual(hr_rb["Value"]["HeroInfo"]["Lv"], 1)
            self.assertEqual(hr_rb["Value"]["HeroInfo"]["Step"], 0)
            self.assertGreater(int(prof.state["player"]["HeroEXP"]), soul_before)

            prof._grant_resources_from_tuples([(1301, 13010701, 1)], source="test_equip_rebirth", tx_prefix="test_eq_rb")
            target_eq = next(e for e in prof.state["equips"] if int(e["EquipModelId"]) == 13010701)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Equip", "MethodName": "EquipLvUpForCount", "Data": [target_eq["Id"], 5], "ServerId": 1})["Status"], 0)
            invested_g = int(target_eq["Gold"])
            self.assertGreater(invested_g, 0)
            g_before = int(prof.state["player"]["Gold"])
            eq_rb = emu.handle_rpc({"ModuleName": "Equip", "MethodName": "EquipRebirth", "Data": [[target_eq["Id"]]], "ServerId": 1})
            self.assertEqual(eq_rb["Status"], 0)
            self.assertEqual(eq_rb["Value"]["EquipInfo"]["Lv"], 0)
            self.assertEqual(int(prof.state["player"]["Gold"]), g_before + invested_g)

    def test_47_r7_6_concurrent_multibanner_isolation_and_normal_recruit(self) -> None:
        """R7.6: Banners 81 & 82 active simultaneously with strict counter/pool/credit/pity/bless isolation alongside HeroRecruit."""
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=Path(td) / "saves")
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=15)
            prof.admin_grant(resources=[{"type": "Diamond", "amount": 20000}])

            init_r = emu.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": [], "ServerId": 1})
            banners_9300 = [x["ActivityId"] for x in init_r["Avatar"]["TimedActivityOpenInfo"]["9300"]]
            self.assertEqual(banners_9300, [81, 82, 83])

            # Pull & claim credit chest on Banner 81
            info81 = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "SelectBanner", "Data": [81], "ServerId": 1})
            self.assertEqual(info81["Value"]["ActivityEnumId"], 81)
            self.assertEqual(info81["Value"]["AvailableBanners"], [81, 82, 83])
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [30], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "DrawCreditReward", "Data": [60], "ServerId": 1})["Status"], 0)

            # Switch to Banner 82 -> completely fresh counters (0 credit, 0 chest, free pull ready!)
            info82 = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "SelectBanner", "Data": [82], "ServerId": 1})
            self.assertEqual(info82["Value"]["ActivityEnumId"], 82)
            self.assertEqual(info82["Value"]["MyCredit"], 0)
            self.assertEqual(info82["Value"]["DrawCreditRewards"], "")
            self.assertEqual(info82["Value"]["CooledTime"], 0)

            r82_free = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [1], "ServerId": 1})
            self.assertEqual(r82_free["Status"], 0)
            self.assertEqual(r82_free["Value"]["RecruitInfo"]["MyCredit"], 10)

            # Explicit arg keeps Banner 81 accessible & completely isolated
            check81 = emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [81], "ServerId": 1})["Value"]
            self.assertEqual(check81["ActivityEnumId"], 81)
            self.assertEqual(check81["MyCredit"], 100)
            self.assertEqual(check81["DrawCreditRewards"], "60")

            # Normal HeroRecruit remains usable alongside both timed banners
            norm_info = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "RecruitInfo", "Data": [], "ServerId": 1})
            self.assertEqual(norm_info["Status"], 0)
            norm_pull = emu.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 1], "ServerId": 1})
            self.assertEqual(norm_pull["Status"], 0)
            self.assertEqual(
                emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [82], "ServerId": 1})["Value"]["MyCredit"],
                10,
            )

    def test_48_r7_6_daily_utc7_reset_custom_period_and_confirmed_manual_reset(self) -> None:
        """R7.6: Auto 00:00 UTC+7 reset, custom per-banner period, confirmed single-banner manual reset & HTTP persistence."""
        import datetime as _dt
        import http.client

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "dev_saves"
            vn_tz = _dt.timezone(_dt.timedelta(hours=7))
            ts_before_mid = int(_dt.datetime(2026, 7, 1, 23, 59, 50, tzinfo=vn_tz).timestamp())
            srv1 = ThreadingEmulatorServer(
                ("127.0.0.1", 0),
                persist=True,
                quiet=True,
                new_player=True,
                env="dev",
                data_dir=data_dir,
                trace_path=data_dir / "trace.log",
                admin_token="r76_tok",
            )
            t1 = threading.Thread(target=srv1.serve_forever, daemon=True)
            t1.start()
            try:
                port = srv1.server_port
                prof = srv1.emu.get_profile_by_name("normal")
                srv1.emu.clock.set_fixed(ts_before_mid)
                prof.admin_prepare_account(target_lv=15)
                prof.admin_grant(resources=[{"type": "Diamond", "amount": 40000}])

                # Build >=500 credit on 81 (unclaimed chest 600 triggers settlement) and 100 credit on 82
                srv1.emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "SelectBanner", "Data": [81], "ServerId": 1})
                for _ in range(6):
                    srv1.emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [30], "ServerId": 1})
                srv1.emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "SelectBanner", "Data": [82], "ServerId": 1})
                srv1.emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "Recruit", "Data": [30], "ServerId": 1})

                c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                hdrs = {"Content-Type": "application/json", "X-Admin-Token": "r76_tok"}

                # Manual reset without confirm=True MUST be rejected (HTTP 400)
                c.request("POST", "/admin/events", body=json.dumps({"action": "reset", "event_id": "timed_recruit:81"}).encode(), headers=hdrs)
                self.assertEqual(c.getresponse().status, 400)

                # Confirmed manual reset affects ONLY 81, settles 81 once into RewardCenter, leaves 82 (credit=100) + Diamond + Heroes untouched!
                heroes_before = len(prof.state["heroes"])
                dia_before = int(prof.state["player"]["Diamond"])
                c.request(
                    "POST",
                    "/admin/events",
                    body=json.dumps({"action": "reset", "event_id": "timed_recruit:81", "confirm": True}).encode(),
                    headers=hdrs,
                )
                r_man = json.loads(c.getresponse().read())
                self.assertTrue(r_man["ok"])
                c.close()

                self.assertEqual(len(prof.state["heroes"]), heroes_before)
                self.assertEqual(int(prof.state["player"]["Diamond"]), dia_before)
                self.assertEqual(
                    srv1.emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [81], "ServerId": 1})["Value"]["MyCredit"],
                    0,
                )
                self.assertEqual(
                    srv1.emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [82], "ServerId": 1})["Value"]["MyCredit"],
                    100,
                )
                # Settlement pushed Banner 81 Rank + Unclaimed Credit rewards into RewardCenter
                rc = srv1.emu.handle_rpc({"ModuleName": "Reward", "MethodName": "Rewars", "Data": [], "ServerId": 1})["Value"]
                self.assertGreaterEqual(len(rc), 2)

                # Cross 00:00 UTC+7 midnight -> automatic daily cycle resets Banner 82 as well
                srv1.emu.clock.advance(30)
                self.assertEqual(
                    srv1.emu.handle_rpc({"ModuleName": "TimedRecruitInfo", "MethodName": "GetTimedRecruitInfo", "Data": [82], "ServerId": 1})["Value"]["MyCredit"],
                    0,
                )
                # Configure custom 3600s period on Banner 82 + carry_over_pity=True via persisted /admin/events config
                c_cfg = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                c_cfg.request(
                    "POST",
                    "/admin/events",
                    body=json.dumps(
                        {
                            "action": "config",
                            "mode": "concurrent",
                            "period_overrides": {"timed_recruit:82": 3600},
                            "carry_over_pity": True,
                        }
                    ).encode(),
                    headers=hdrs,
                )
                cfg_res = json.loads(c_cfg.getresponse().read())
                self.assertTrue(cfg_res["ok"])
                c_cfg.close()
                ev82 = prof.event_runtime.evaluate("timed_recruit:82", prof.state["player"])
                self.assertEqual(int(ev82.end_ts - ev82.start_ts), 3600)
            finally:
                srv1.shutdown()
                srv1.server_close()

            # Restart server -> archive history & custom period_overrides persist
            srv2 = ThreadingEmulatorServer(
                ("127.0.0.1", 0),
                persist=True,
                quiet=True,
                new_player=False,
                env="dev",
                data_dir=data_dir,
                trace_path=data_dir / "trace.log",
                admin_token="r76_tok",
            )
            t2 = threading.Thread(target=srv2.serve_forever, daemon=True)
            t2.start()
            try:
                p2 = srv2.emu.get_profile_by_name("normal")
                self.assertGreaterEqual(len(p2.state["event_runtime"]["archive_history"]), 2)
                self.assertEqual(p2.event_runtime.archive_cfg["period_overrides"].get("timed_recruit:82"), 3600)
            finally:
                srv2.shutdown()
                srv2.server_close()

    def test_49_r7_7_standalone_seed_and_loopback_account_routing(self) -> None:
        """R7.7: Standalone seed initialization (TK1 fresh Lv1 + TK2 OlinaHugh preset + TK3 fresh) & loopback routing."""
        import os

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            seed_dir = base / "seeds"
            seed_dir.mkdir(parents=True, exist_ok=True)
            data_dir = base / "standalone_saves"
            # Prepare an OlinaHugh-like Lv 20 seed profile
            seed_emu = GameEmulatorState(persist=False, new_player=True, default_profile="normal")
            seed_emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["OlinaHugh", True], "ServerId": 1})
            seed_prof = seed_emu.get_profile(1)
            seed_prof.admin_prepare_account(target_lv=20, vip_lv=3)
            seed_prof.state["player"]["PlayerId"] = "200010"
            (seed_dir / "seed_olinahugh.json").write_text(
                json.dumps(seed_prof.state, ensure_ascii=False),
                encoding="utf-8",
            )

            prev_env = os.environ.get("INUYASHA_SEED_DIR")
            os.environ["INUYASHA_SEED_DIR"] = str(seed_dir)
            try:
                emu = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
                info = emu.list_s1_accounts(ensure_slots=3)
                self.assertEqual(info["ActiveAccountId"], "acct_1")
                self.assertEqual(len(info["Accounts"]), 3)
                a1, a2, a3 = info["Accounts"]
                self.assertEqual(a1["IsNewPlayer"], 1)
                self.assertEqual(a2["PlayerName"], "OlinaHugh")
                self.assertEqual(a2["Lv"], 20)
                self.assertEqual(a2["IsNewPlayer"], 0)
                self.assertEqual(a3["IsNewPlayer"], 1)
                self.assertNotEqual(a1["PlayerId"], a2["PlayerId"])
                self.assertNotEqual(a2["PlayerId"], a3["PlayerId"])
            finally:
                if prev_env is None:
                    os.environ.pop("INUYASHA_SEED_DIR", None)
                else:
                    os.environ["INUYASHA_SEED_DIR"] = prev_env

    def test_50_r7_8_s1_multi_account_arena_defense_and_save_backup_restore(self) -> None:
        """R7.8: S1 multi-account isolation, shared S1 Arena defense fight & rank swap, and save export/import."""
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            emu.ensure_s1_account_slots(3)

            # Account 1: create HeroAlpha and advance to Lv 22
            r_login1 = emu.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": ["A", "1", 1, "x", "{}", "100001"], "ServerId": 1})
            pid1 = r_login1["Value"]["PlayerId"]
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["HeroAlpha", True], "ServerId": 1, "PlayerId": pid1})
            prof1 = emu.get_profile(1, player_id=pid1)
            prof1.admin_prepare_account(target_lv=22, vip_lv=2)
            prof1.state["pvp"]["rank"] = 1480
            prof1.save()

            # Switch to Account 2: create HeroBeta, deploy 2nd hero & equip so its lineup beats HeroAlpha
            sw2 = emu.switch_s1_account("acct_2")
            self.assertEqual(sw2["ActiveAccountId"], "acct_2")
            r_login2 = emu.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": ["A", "1", 1, "x", "{}", "100001"], "ServerId": 1})
            pid2 = r_login2["Value"]["PlayerId"]
            self.assertNotEqual(pid1, pid2)
            self.assertEqual(r_login2["Value"]["IsNewPlayer"], 1)
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["HeroBeta", False], "ServerId": 1, "PlayerId": pid2})
            prof2 = emu.get_profile(1, player_id=pid2)
            prof2.admin_prepare_account(target_lv=25, vip_lv=4)
            prof2.admin_grant(heroes=[{"model_id": 12011004, "count": 1}, {"model_id": 12011005, "count": 1}])
            h2_id = [h["Id"] for h in prof2.state["heroes"] if int(h["HeroModelId"]) == 12011004][0]
            h3_id = [h["Id"] for h in prof2.state["heroes"] if int(h["HeroModelId"]) == 12011005][0]
            emu.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [2, h2_id], "ServerId": 1, "PlayerId": pid2})
            emu.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [3, h3_id], "ServerId": 1, "PlayerId": pid2})
            prof2.state["pvp"]["rank"] = 1500
            prof2.save()

            # Verify Account 1 was NOT overwritten
            self.assertEqual(prof1.state["player"]["PlayerName"], "HeroAlpha")
            self.assertEqual(prof1.state["player"]["Lv"], 22)
            self.assertEqual(prof2.state["player"]["PlayerName"], "HeroBeta")
            self.assertEqual(prof2.state["player"]["Lv"], 25)

            # Account 2 opens Arena -> sees Account 1 ("HeroAlpha") at rank 1480 in RankList
            pvp_info2 = emu.handle_rpc({"ModuleName": "PVP", "MethodName": "GetPVPInfo", "Data": [], "ServerId": 1, "PlayerId": pid2})["Value"]
            rank_list2 = pvp_info2["RankList"]
            peer_rows = [r for r in rank_list2 if r["PlayerId"] == pid1]
            self.assertEqual(len(peer_rows), 1)
            self.assertEqual(peer_rows[0]["Name"], "HeroAlpha")
            self.assertEqual(peer_rows[0]["Rank"], 1480)

            # Account 2 inspects Account 1's defense formation via Slot.SlotFormations
            f_view = emu.handle_rpc({"ModuleName": "Slot", "MethodName": "SlotFormations", "Data": [pid1], "ServerId": 1, "PlayerId": pid2})["Value"]
            self.assertEqual(f_view["PlayerInfo"]["Name"], "HeroAlpha")
            self.assertEqual(f_view["PlayerInfo"]["PlayerId"], pid1)

            # Account 2 challenges Account 1's defense formation in Arena -> wins and swaps rank 1500 <-> 1480
            fight_res = emu.handle_rpc({"ModuleName": "PVP", "MethodName": "PVPFight", "Data": [pid1, 1480], "ServerId": 1, "PlayerId": pid2})["Value"]
            self.assertEqual(fight_res["IsWinFight"], 1)
            self.assertEqual(fight_res["Rank"], 1480)
            self.assertEqual(prof1.state["pvp"]["rank"], 1500)
            self.assertEqual(prof2.state["pvp"]["rank"], 1480)

            # Create Account 4 dynamically & export save bundle
            created = emu.create_s1_account(label="TK 4")
            self.assertEqual(created["ActiveAccountId"], "acct_4")
            exp_res = emu.export_save_bundle()
            self.assertTrue(exp_res["ok"])
            self.assertEqual(exp_res["AccountCount"], 4)
            self.assertTrue(Path(exp_res["BackupPath"]).exists())

            # Mutate Account 1 diamond & import backup -> restores Account 1 & all 4 accounts intact
            orig_dia1 = int(prof1.state["player"]["Diamond"])
            prof1.state["player"]["Diamond"] = 999999
            prof1.save()
            with self.assertRaises(ValueError):
                emu.import_save_bundle(confirm=False)
            imp_res = emu.import_save_bundle(confirm=True)
            self.assertTrue(imp_res["ok"])
            self.assertEqual(imp_res["RestoredCount"], 4)
            self.assertEqual(int(emu.get_profile(1, player_id=pid1).state["player"]["Diamond"]), orig_dia1)
            self.assertTrue(Path(imp_res["SafetyBackupPath"]).exists())

    def test_51_r7_9_money_tree_pray_tree_and_smash_egg(self) -> None:
        """R7.9: TimedMoneyTree (4432), TimedHopetreeInfo (4409) & TimedSmashingeggsInfo (4426)."""
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=Path(td) / "saves")
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=30)
            prof.state["player"]["Diamond"] = 5000
            prof.save()

            # 1. TimedMoneyTree: free shake -> paid 1x -> paid 10x -> milestone chest + duplicate guard
            mt0 = emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(mt0["Status"], 0)
            self.assertEqual(mt0["Value"]["CostNum"], 0)

            s1 = emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "ShakeTree", "Data": [1], "ServerId": 1})
            self.assertEqual(s1["Status"], 0)
            self.assertEqual(s1["Value"]["Num"], 1)
            self.assertEqual(s1["Value"]["CostNum"], 50)
            self.assertEqual(len(s1["Value"]["BaseGetGameResourceList"]), 1)

            s2 = emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "ShakeTree", "Data": [1], "ServerId": 1})
            self.assertEqual(s2["Status"], 0)
            self.assertEqual(s2["Value"]["Num"], 2)

            s10 = emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "ShakeTree", "Data": [10], "ServerId": 1})
            self.assertEqual(s10["Status"], 0)
            self.assertEqual(s10["Value"]["Num"], 12)
            self.assertGreaterEqual(len(s10["Value"]["BaseGetGameResourceList"]), 1)

            dr = emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "DrawReward", "Data": [5], "ServerId": 1})
            self.assertEqual(dr["Status"], 0)
            self.assertTrue(len(dr["Value"]["BaseGetGameResourceList"]) >= 1)
            dr_dup = emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "DrawReward", "Data": [5], "ServerId": 1})
            self.assertNotEqual(dr_dup["Status"], 0)

            # 2. TimedHopetreeInfo: locked before recharge -> unlocked after ConfirmOrder -> claim day 1
            ht0 = emu.handle_rpc({"ModuleName": "TimedHopetreeInfo", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ht0["Status"], 0)
            self.assertEqual(ht0["Value"]["RewardList"][0]["CanDraw"], 0)
            ht_fail = emu.handle_rpc({"ModuleName": "TimedHopetreeInfo", "MethodName": "DrawReward", "Data": [1], "ServerId": 1})
            self.assertNotEqual(ht_fail["Status"], 0)

            ord_id = emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "GenerateOrderID", "Data": ["com.cmn.inuyasha.gem300"], "ServerId": 1})["Value"]
            conf = emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "ConfirmOrder", "Data": ["com.cmn.inuyasha.gem300", ord_id], "ServerId": 1})
            self.assertEqual(conf["Status"], 0)

            ht1 = emu.handle_rpc({"ModuleName": "TimedHopetreeInfo", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ht1["Value"]["RewardList"][0]["CanDraw"], 1)
            ht_ok = emu.handle_rpc({"ModuleName": "TimedHopetreeInfo", "MethodName": "DrawReward", "Data": [1], "ServerId": 1})
            self.assertEqual(ht_ok["Status"], 0)
            self.assertTrue(len(ht_ok["Value"]["BaseGetGameResourceList"]) >= 1)

            # 3. TimedSmashingeggsInfo: GetRewardList -> SmashingEggs 1x & 5x -> GetSmashingRecord
            egg0 = emu.handle_rpc({"ModuleName": "TimedSmashingeggsInfo", "MethodName": "GetRewardList", "Data": [], "ServerId": 1})
            self.assertEqual(egg0["Status"], 0)
            self.assertTrue(len(egg0["Value"]["TimedSmashingReward"]) >= 5)
            sm1 = emu.handle_rpc({"ModuleName": "TimedSmashingeggsInfo", "MethodName": "SmashingEggs", "Data": [1, 1], "ServerId": 1})
            self.assertEqual(sm1["Status"], 0)
            self.assertEqual(len(sm1["Value"]["BaseGetGameResourceList"]), 1)
            sm5 = emu.handle_rpc({"ModuleName": "TimedSmashingeggsInfo", "MethodName": "SmashingEggs", "Data": [2, 5], "ServerId": 1})
            self.assertEqual(sm5["Status"], 0)
            self.assertGreaterEqual(len(sm5["Value"]["BaseGetGameResourceList"]), 1)
            rec = emu.handle_rpc({"ModuleName": "TimedSmashingeggsInfo", "MethodName": "GetSmashingRecord", "Data": [], "ServerId": 1})
            self.assertEqual(rec["Status"], 0)
            self.assertGreaterEqual(len(rec["Value"]["TimedSmashingRecord"]), 2)

    def test_52_r7_9_slot_luckdraw_xssb_divine_equip_and_yiyuan_duobao(self) -> None:
        """R7.9: TimedLuckdrawInfo (4412), TimedXssbInfo (4410, TW 1.4 XssbModel) & YiYuan (7800)."""
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=Path(td) / "saves")
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=30)
            prof.state["player"]["Diamond"] = 5000
            prof.save()

            # 1. TimedLuckdrawInfo (Slot Machine): GetInfo -> Ordinary spin -> Senior spin -> Rank & Integral
            sl0 = emu.handle_rpc({"ModuleName": "TimedLuckdrawInfo", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(sl0["Status"], 0)
            self.assertGreaterEqual(len(sl0["Value"]["RankList"]), 4)
            sp1 = emu.handle_rpc({"ModuleName": "TimedLuckdrawInfo", "MethodName": "Luckdraw", "Data": [1, 1], "ServerId": 1})
            self.assertEqual(sp1["Status"], 0)
            self.assertGreater(sp1["Value"]["TimedLuckdrawInfo"]["Integral"], 0)
            sp2 = emu.handle_rpc({"ModuleName": "TimedLuckdrawInfo", "MethodName": "Luckdraw", "Data": [2, 1], "ServerId": 1})
            self.assertEqual(sp2["Status"], 0)
            self.assertGreater(sp2["Value"]["TimedLuckdrawInfo"]["Integral"], sp1["Value"]["TimedLuckdrawInfo"]["Integral"])
            self.assertEqual(len(sp2["Value"]["RankList"]), 5)

            # 2. TimedXssbInfo (Divine Equip Summon from TW 1.4 XssbModel): GetInfo -> Free 1x -> Paid 10x -> Credit chest
            xs0 = emu.handle_rpc({"ModuleName": "TimedXssbInfo", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(xs0["Status"], 0)
            self.assertIn("TimedXssbInfo", xs0["Value"])
            xs_free = emu.handle_rpc({"ModuleName": "TimedXssbInfo", "MethodName": "CallEquip", "Data": [1, 1], "ServerId": 1})
            self.assertEqual(xs_free["Status"], 0)
            self.assertGreater(xs_free["Value"]["TimedXssbInfo"]["Integral"], 0)
            xs_10 = emu.handle_rpc({"ModuleName": "TimedXssbInfo", "MethodName": "CallEquip", "Data": [3, 10], "ServerId": 1})
            self.assertEqual(xs_10["Status"], 0)
            self.assertGreaterEqual(len(xs_10["Value"]["BaseGetGameResourceList"]), 1)
            self.assertGreaterEqual(xs_10["Value"]["TimedXssbInfo"]["Integral"], 110)
            xs_rew = emu.handle_rpc({"ModuleName": "TimedXssbInfo", "MethodName": "ReceiveReward", "Data": [100], "ServerId": 1})
            self.assertEqual(xs_rew["Status"], 0)

            # 3. YiYuan (Treasure Snatch 7800): GetInfo -> Join -> DrawReward + duplicate guard
            yy0 = emu.handle_rpc({"ModuleName": "YiYuan", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(yy0["Status"], 0)
            yy_join = emu.handle_rpc({"ModuleName": "YiYuan", "MethodName": "Join", "Data": [1], "ServerId": 1})
            self.assertEqual(yy_join["Status"], 0)
            yy_draw = emu.handle_rpc({"ModuleName": "YiYuan", "MethodName": "DrawReward", "Data": [1], "ServerId": 1})
            self.assertEqual(yy_draw["Status"], 0)
            yy_dup = emu.handle_rpc({"ModuleName": "YiYuan", "MethodName": "DrawReward", "Data": [1], "ServerId": 1})
            self.assertNotEqual(yy_dup["Status"], 0)

    def test_53_r7_9_timespike_miaosha_milestone_charge_use_exchange_and_points_mall(self) -> None:
        """R7.9: Timespike (6800), TimesMiaosha (7000), TimedInfo (4401..4407,4421,4422,4427), ChargeGift (4429), PointsMall (4428), Exchange (4406), ScoreRank (4430)."""
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=Path(td) / "saves")
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=30)
            prof.state["player"]["Diamond"] = 20000
            prof.save()

            # Simulate recharge 900 so recharge-gated tiers unlock
            ord_id = emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "GenerateOrderID", "Data": ["com.cmn.inuyasha.gem900"], "ServerId": 1})["Value"]
            emu.handle_rpc({"ModuleName": "PlayerCharge", "MethodName": "ConfirmOrder", "Data": ["com.cmn.inuyasha.gem900", ord_id], "ServerId": 1})

            # Timespike & TimesMiaosha
            ts_info = emu.handle_rpc({"ModuleName": "Timespike", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ts_info["Status"], 0)
            self.assertGreater(ts_info["Value"]["TriggerLv"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "Timespike", "MethodName": "ReceivedReward", "Data": [], "ServerId": 1})["Status"], 0)

            ms_info = emu.handle_rpc({"ModuleName": "TimesMiaosha", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ms_info["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimesMiaosha", "MethodName": "Receive", "Data": [7000, 1], "ServerId": 1})["Status"], 0)

            # TimedInfo: ChargeSingle, ChargeTotal, UseTotal (after spending), ChargeDays, DoubleDiamond, AccumulateDays, ChargeRank, UseRank
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "GetChargeSingleInfo", "Data": [], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "DrawSingleChargeReward", "Data": [60], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "GetChargeTotalInfo", "Data": [], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "DrawChargeTotalReward", "Data": [300], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "GetChargeDaysInfo", "Data": [], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "DrawChargeDaysReward", "Data": [1], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "GetDoubleDiamondInfo", "Data": [], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "DrawDoubleDiamondReward", "Data": [60], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "GetAcumulateDaysRewardInfo", "Data": [], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "DrawAcumulateDaysReward", "Data": [1], "ServerId": 1})["Status"], 0)

            # Spend >= 500 diamonds via PointsMall / Exchange / MoneyTree so UseTotal unlocks
            pm_info = emu.handle_rpc({"ModuleName": "TimedChargeScore", "MethodName": "GetRewardList", "Data": [], "ServerId": 1})
            self.assertEqual(pm_info["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedChargeScore", "MethodName": "BuyGoods", "Data": [1, 1], "ServerId": 1})["Status"], 0)

            ex_info = emu.handle_rpc({"ModuleName": "TimedLimitExchange", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ex_info["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedLimitExchange", "MethodName": "Exchange", "Data": [1, 1], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "ShakeTree", "Data": [10], "ServerId": 1})["Status"], 0)

            ut_info = emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "GetUseTotalInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ut_info["Status"], 0)
            self.assertGreaterEqual(ut_info["Value"]["UseTotalReward"], 500)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "DrawUseTotalReward", "Data": [500], "ServerId": 1})["Status"], 0)

            # ChargeGift, ChargeRank, UseDiamondRank, ScoreRank
            cg_info = emu.handle_rpc({"ModuleName": "TimedChargeGift", "MethodName": "GetChargeGiftInfo", "Data": [], "ServerId": 1})
            self.assertEqual(cg_info["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedChargeGift", "MethodName": "ReceiveChargeGift", "Data": [101], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "GetChargeRankInfo", "Data": [], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedInfo", "MethodName": "GetUseDiamondRankInfo", "Data": [], "ServerId": 1})["Status"], 0)

            sr_info = emu.handle_rpc({"ModuleName": "TimedScoreRank", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(sr_info["Status"], 0)
            self.assertGreater(sr_info["Value"]["Score"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedScoreRank", "MethodName": "GetReward", "Data": [1], "ServerId": 1})["Status"], 0)

    def test_54_r7_9_multi_region_critical_tasks_earlytask_trader_shiwan_online_and_month_sign(self) -> None:
        """R7.9: TW 1.4 recovered configs (CriticalTasks 4700, Earlytask 2600, Trader 4300) + Swdiamonds (8200), OnlineReward (3700), MonthSign (2712), RandomRedBag (5501), ActiveGift (2716)."""
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=Path(td) / "saves")
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=30)
            prof.state["player"]["Diamond"] = 5000
            prof.save()

            # 1. TimedCriticalInfo (4700, TW 1.4 CriticalTasksTypeRelation)
            prof._inc_stat("spent_diamonds", 600)
            prof.save()
            ct_info = emu.handle_rpc({"ModuleName": "TimedCriticalInfo", "MethodName": "Info", "Data": [], "ServerId": 1})
            self.assertEqual(ct_info["Status"], 0)
            self.assertTrue(len(ct_info["Value"]) >= 5)
            claimable_ct = [r for r in ct_info["Value"] if int(r["DoneNum"]) >= int(r["CompleteComplete"]) and not r["IfDraw"]]
            self.assertTrue(len(claimable_ct) >= 1)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TimedCriticalInfo", "MethodName": "Reward", "Data": [claimable_ct[0]["TaskType"]], "ServerId": 1})["Status"], 0)

            # 2. EarlytaskFinishRecord (2600, TW 1.4 EarlytaskModel & EarlytaskRewardRelation)
            et_info = emu.handle_rpc({"ModuleName": "EarlytaskFinishRecord", "MethodName": "GetEarlytaskList", "Data": [], "ServerId": 1})
            self.assertEqual(et_info["Status"], 0)
            self.assertGreaterEqual(len(et_info["Value"]["EarlytaskList"]), 10)
            first_et = next(
                r
                for r in et_info["Value"]["EarlytaskList"]
                if int(r["ReachedNum"]) >= min(int(k) for k in prof.game_data["earlytask_reward"][str(r["EarlyTaskModelId"])])
            )
            first_need = min(int(k) for k in prof.game_data["earlytask_reward"][str(first_et["EarlyTaskModelId"])])
            self.assertEqual(
                emu.handle_rpc(
                    {
                        "ModuleName": "EarlytaskFinishRecord",
                        "MethodName": "DrawEarlytaskGift",
                        "Data": [first_et["EarlyTaskModelId"], first_need],
                        "ServerId": 1,
                    }
                )["Status"],
                0,
            )

            # 3. TraderInfo (4300, TW 1.4 TraderConfig)
            tr_info = emu.handle_rpc({"ModuleName": "TraderInfo", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(tr_info["Status"], 0)
            goods_list = tr_info["Value"]["TraderGoodsList"]
            self.assertTrue(len(goods_list) >= 4)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TraderInfo", "MethodName": "BuyGoods", "Data": [goods_list[0]["Id"]], "ServerId": 1})["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "TraderInfo", "MethodName": "RefreshtGoodsList", "Data": [3], "ServerId": 1})["Status"], 0)

            # 4. Swdiamonds (8200, 100k Diamonds)
            sw_info = emu.handle_rpc({"ModuleName": "Swdiamonds", "MethodName": "GetSwdiamondInfo", "Data": [], "ServerId": 1})
            self.assertEqual(sw_info["Status"], 0)
            dia_before = int(prof.state["player"]["Diamond"])
            self.assertEqual(emu.handle_rpc({"ModuleName": "Swdiamonds", "MethodName": "GetSwdiamondReward", "Data": [1], "ServerId": 1})["Status"], 0)
            self.assertGreater(int(prof.state["player"]["Diamond"]), dia_before)

            # 5. OnlineReward (3700), MonthSignInfo (2712), RandomRedBag (5501), ActiveGift (2716)
            or_info = emu.handle_rpc({"ModuleName": "OnlineReward", "MethodName": "OnlineRewardInfo", "Data": [], "ServerId": 1})
            self.assertEqual(or_info["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "OnlineReward", "MethodName": "DrawOnlineReward", "Data": [1], "ServerId": 1})["Status"], 0)

            ms_info = emu.handle_rpc({"ModuleName": "MonthSignInfo", "MethodName": "GetInfo", "Data": [], "ServerId": 1})
            self.assertEqual(ms_info["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "MonthSignInfo", "MethodName": "DrawReward", "Data": [], "ServerId": 1})["Status"], 0)

            rb_info = emu.handle_rpc({"ModuleName": "RandomRedBag", "MethodName": "GetRandomRedBagInfo", "Data": [], "ServerId": 1})
            self.assertEqual(rb_info["Status"], 0)
            self.assertEqual(emu.handle_rpc({"ModuleName": "RandomRedBag", "MethodName": "ReceiveRandomRedBag", "Data": [1], "ServerId": 1})["Status"], 0)

            ag_ok = emu.handle_rpc({"ModuleName": "ActiveGift", "MethodName": "ActiveGift", "Data": ["INUYASHA2026"], "ServerId": 1})
            self.assertEqual(ag_ok["Status"], 0)
            ag_dup = emu.handle_rpc({"ModuleName": "ActiveGift", "MethodName": "ActiveGift", "Data": ["INUYASHA2026"], "ServerId": 1})
            self.assertNotEqual(ag_dup["Status"], 0)

    def test_55_r7_9_open_contest_s1_multi_account_ranking_and_daily_manual_reset(self) -> None:
        """R7.9: OpenContest (7900) S1 multi-account community leaderboard, 00:00 UTC+7 daily reset, manual reset & persistence."""
        import datetime as _dt

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            vn_tz = _dt.timezone(_dt.timedelta(hours=7))
            ts_day1 = int(_dt.datetime(2026, 5, 1, 10, 0, 0, tzinfo=vn_tz).timestamp())
            emu = GameEmulatorState(persist=True, new_player=True, default_profile="normal", data_dir=data_dir)
            emu.clock.set_fixed(ts_day1)

            # Account 1 & Account 2 in S1
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": ["A", "1", 1, "x", "{}", "100001"], "ServerId": 1})
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["S1Leader", True], "ServerId": 1})
            prof1 = emu.get_profile_by_name("normal")
            prof1.admin_prepare_account(target_lv=30)
            pid1 = prof1.state["player"]["PlayerId"]

            emu.create_s1_account(label="TK 2")
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": ["A", "1", 1, "x", "{}", "100002"], "ServerId": 1})
            emu.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["S1Challenger", False], "ServerId": 1})
            prof2 = emu.get_profile_by_name("acct_2")
            prof2.admin_prepare_account(target_lv=29)
            pid2 = prof2.state["player"]["PlayerId"]

            # OpenContest: GetActiveRank & GetRank includes both S1 accounts + synthetic peers
            oc_act = emu.handle_rpc({"ModuleName": "GlobalOpencontestRank", "MethodName": "GetActiveRank", "Data": [], "ServerId": 1, "PlayerId": pid1})
            self.assertEqual(oc_act["Status"], 0)
            oc_rank = emu.handle_rpc({"ModuleName": "GlobalOpencontestRank", "MethodName": "GetRank", "Data": [1], "ServerId": 1, "PlayerId": pid1})
            self.assertEqual(oc_rank["Status"], 0)
            names = [r["Name"] for r in oc_rank["Value"]["OpencontestRank"]]
            self.assertIn("S1Leader", names)
            self.assertIn("S1Challenger", names)
            self.assertEqual(emu.handle_rpc({"ModuleName": "GlobalOpencontestRank", "MethodName": "DrawReward", "Data": [1], "ServerId": 1, "PlayerId": pid1})["Status"], 0)

            # MoneyTree shake on Day 1 -> 00:00 UTC+7 next day resets free shake
            emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "ShakeTree", "Data": [1], "ServerId": 1, "PlayerId": pid1})
            mt_day1 = emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "GetInfo", "Data": [], "ServerId": 1, "PlayerId": pid1})["Value"]
            self.assertEqual(mt_day1["CostNum"], 50)

            ts_day2 = int(_dt.datetime(2026, 5, 2, 0, 5, 0, tzinfo=vn_tz).timestamp())
            emu.clock.set_fixed(ts_day2)
            mt_day2 = emu.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "GetInfo", "Data": [], "ServerId": 1, "PlayerId": pid1})["Value"]
            self.assertEqual(mt_day2["CostNum"], 0)

            # Persistence across emulator restart
            emu2 = GameEmulatorState(persist=True, new_player=False, default_profile="normal", data_dir=data_dir)
            emu2.clock.set_fixed(ts_day2)
            prof1_reloaded = emu2.get_profile_by_name("normal")
            self.assertEqual(prof1_reloaded.state["player"]["PlayerName"], "S1Leader")


    def test_56_r7_10_hero_bag_and_banner_chest_preserve_entitlements(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            emu = GameEmulatorState(persist=True, new_player=True, data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=25)
            prof.state["player"]["Diamond"] = 5000
            prof.state["heroes"].extend(prof._build_hero_instance(12011014) for _ in range(298))
            prof._grant_resources_from_tuples([(1606, 16060008, 1)], source="test56", tx_prefix="test56")

            def rpc(module, method, *args):
                return prof.handle_rpc({"ModuleName": module, "MethodName": method, "Data": list(args)})

            self.assertEqual(rpc("HeroRecruit", "Recruit", 30, 0)["Status"], -2005)
            self.assertEqual(rpc("TimedRecruitInfo", "Recruit", 30, 81)["Status"], -2005)
            self.assertEqual(prof.state["player"]["Diamond"], 5000)
            self.assertEqual(rpc("Bag", "BagExpand", 5)["Value"], {"BagModelId": 5, "Size": 305, "ExpandNum": 1})
            self.assertEqual(rpc("Bag", "BagExpand", 5)["Value"]["Size"], 310)
            self.assertEqual(prof.state["player"]["Diamond"], 4970)
            self.assertEqual(rpc("TimedRecruitInfo", "Recruit", 30, 81)["Status"], 0)
            chest = rpc("TimedRecruitInfo", "DrawCreditReward", 60, 81)
            self.assertEqual(chest["Status"], 0)
            self.assertEqual(chest["Value"]["DrawCreditRewards"], "60")
            self.assertNotEqual(rpc("TimedRecruitInfo", "DrawCreditReward", 60, 81)["Status"], 0)
            self.assertNotEqual(rpc("TimedRecruitInfo", "DrawCreditReward", 60, 82)["Status"], 0)

            box = next(g for g in prof.state["goods"] if g["GoodsModelId"] == 16060008)
            self.assertNotEqual(rpc("Goods", "GoodsUseForBoxChoice", "stale", 16060008, 12011004)["Status"], 0)
            result = rpc("Goods", "GoodsUseForBoxChoice", box["Id"], 16060008, 12011004)
            self.assertEqual(result["Value"]["BaseGetGameResourceList"][0]["Hero"][0]["HeroModelId"], 12011004)
            self.assertNotEqual(rpc("Goods", "GoodsUseForBoxChoice", box["Id"], 16060008, 12011004)["Status"], 0)

            ev = prof.event_runtime.evaluate("timed_recruit:81", prof.state["player"])
            prof.event_runtime.get_instance(ev.instance_id)["progress"]["pending_gold_hero"] = True
            prof.event_runtime.manual_reset_event("timed_recruit:81", confirm=True, on_ended=prof._on_timed_event_ended)
            self.assertEqual(len([r for r in prof.state["rewards_center"] if r["SourceKey"] == f"tr_pending_ur:{ev.instance_id}"]), 1)
            prof.save()
            reloaded = GameEmulatorState(persist=True, data_dir=data_dir).get_profile_by_name("normal")
            self.assertEqual(reloaded._bag_info(5)["Size"], 310)
            self.assertTrue(any(h["HeroModelId"] == 12011004 for h in reloaded.state["heroes"]))

    def test_57_r7_10_slot_vn_ticket_recharge_and_multiplier(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            emu = GameEmulatorState(persist=True, new_player=True, data_dir=data_dir)
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=30)
            ev, progress = prof._ensure_slot_prog()
            progress["starter_tickets_seeded"] = True
            prof._grant_resources_from_tuples([(1605, 16050055, 3)], source="legacy", tx_prefix="test57")

            def rpc(module, method, *args):
                return prof.handle_rpc({"ModuleName": module, "MethodName": method, "Data": list(args)})

            result = rpc("TimedLuckdrawInfo", "GetInfo")["Value"]
            self.assertEqual(result["LuckdrawConfig"]["OrdinaryUseResource"], "1605,16050027,1")
            self.assertEqual(prof._get_goods_qty(16050055), 3)
            self.assertEqual(prof._get_goods_qty(16050027), 10)
            charge = "com.cmn.inuyasha.gem300"
            order = rpc("PlayerCharge", "GenerateOrderID", charge)["Value"]
            self.assertEqual(rpc("PlayerCharge", "ConfirmOrder", charge, order)["Status"], 0)
            self.assertEqual(prof._get_goods_qty(16050027), 15)
            self.assertNotEqual(rpc("PlayerCharge", "ConfirmOrder", charge, order)["Status"], 0)
            with patch("r79_event_handlers.random.choice", side_effect=[prof.SLOT_NORMAL_REWARDS[i] for i in [2] + [0] * 9]):
                spin = rpc("TimedLuckdrawInfo", "Luckdraw", 1, 10)["Value"]
            self.assertEqual(spin["OrderId"], [3] + [1] * 9)
            self.assertEqual(spin["TimedLuckdrawInfo"]["Integral"], 10)
            self.assertEqual(sum(r["Num"] for r in spin["BaseGetGameResourceList"][0]["PlayerAttr"]), 500000)
            self.assertEqual(prof._get_goods_qty(16050027), 5)
            reloaded = GameEmulatorState(persist=True, data_dir=data_dir).get_profile_by_name("normal")
            self.assertEqual(reloaded._get_goods_qty(16050027), 5)
            self.assertEqual(reloaded.event_runtime.get_instance(ev.instance_id)["progress"]["integral"], 10)


    def test_58_r7_10_same_event_rewards_are_independent_per_s1_account(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            emu = GameEmulatorState(persist=True, new_player=True, data_dir=data_dir)
            emu.create_s1_account()

            def rpc(prof, module, method, *args):
                return emu.handle_rpc({
                    "ModuleName": module, "MethodName": method, "Data": list(args),
                    "ServerId": 1, "PlayerId": prof.state["player"]["PlayerId"],
                })

            for name in ("normal", "acct_2"):
                prof = emu.get_profile_by_name(name)
                prof.admin_prepare_account(target_lv=30)
                prof.state["player"]["Diamond"] = 5000
                self.assertEqual(rpc(prof, "TimedSmashingeggsInfo", "GetRewardList")["Status"], 0)
                hammers = prof._get_goods_qty(16050061)
                with patch("r79_event_handlers.random.choices", return_value=[(1111, 0, 30)] * 10):
                    shake = rpc(prof, "TimedMoneyTree", "ShakeTree", 4432, 10)
                self.assertEqual(shake["Value"]["Num"], 10)
                self.assertEqual(prof.state["stats"]["spent_diamonds"], 450)
                self.assertEqual(prof.state["player"]["Diamond"], 4850)
                self.assertEqual(rpc(prof, "TimedMoneyTree", "DrawReward", 4432, 10)["Status"], 0)
                self.assertEqual(prof.state["player"]["Diamond"], 5050)
                self.assertEqual(prof._get_goods_qty(16050061), hammers + 2)
                self.assertEqual(rpc(prof, "TimedLuckdrawInfo", "GetInfo")["Status"], 0)
                self.assertEqual(prof._get_goods_qty(16050027), 10)

            emu = GameEmulatorState(persist=True, data_dir=data_dir)
            for name in ("normal", "acct_2"):
                prof = emu.get_profile_by_name(name)
                self.assertNotEqual(rpc(prof, "TimedMoneyTree", "DrawReward", 4432, 10)["Status"], 0)
                self.assertEqual(prof.state["player"]["Diamond"], 5050)
                self.assertEqual(prof._get_goods_qty(16050027), 10)


    def test_59_r7_11_shared_s1_rank_reconciles_once_at_midnight(self) -> None:
        from datetime import datetime, timedelta, timezone

        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            emu = GameEmulatorState(persist=True, new_player=True, data_dir=data_dir)
            emu.clock.set_fixed(int(datetime(2026, 11, 20, 23, 59, 30, tzinfo=timezone(timedelta(hours=7))).timestamp()))
            emu.create_s1_account()
            alpha, beta = (emu.get_profile_by_name(name) for name in ("normal", "acct_2"))

            def rpc(prof, module, method, *args):
                return emu.handle_rpc({
                    "ModuleName": module, "MethodName": method, "Data": list(args),
                    "ServerId": 1, "PlayerId": prof.state["player"]["PlayerId"],
                })

            for prof, name in ((alpha, "DeltaAlpha"), (beta, "DeltaBeta")):
                rpc(prof, "Player", "NewPlayer", name, 1)
                prof.admin_prepare_account(target_lv=30)
                prof.state["player"]["Diamond"] = 5000
                with patch("r79_event_handlers.random.choice", return_value=prof.SLOT_NORMAL_REWARDS[0]):
                    self.assertEqual(rpc(prof, "TimedLuckdrawInfo", "Luckdraw", 1, 10)["Status"], 0)

            slot_a = rpc(alpha, "TimedLuckdrawInfo", "GetInfo")["Value"]
            slot_b = rpc(beta, "TimedLuckdrawInfo", "GetInfo")["Value"]
            self.assertEqual(slot_a["RankList"], slot_b["RankList"])
            self.assertNotEqual(slot_a["TimedLuckdrawInfo"]["Rank"], slot_b["TimedLuckdrawInfo"]["Rank"])
            self.assertEqual({r["Name"] for r in slot_a["RankList"][-2:]}, {"DeltaAlpha", "DeltaBeta"})

            self.assertEqual(rpc(beta, "TimedSmashingeggsInfo", "SmashingEggs", 1)["Status"], 0)
            records = rpc(alpha, "TimedSmashingeggsInfo", "GetSmashingRecord")["Value"]["TimedSmashingRecord"]
            self.assertEqual([r["Name"] for r in records if not r["PlayerId"].startswith("bot-")], ["DeltaBeta"])

            self.assertEqual(rpc(alpha, "TimedMoneyTree", "ShakeTree", 4432, 10)["Status"], 0)
            self.assertEqual(rpc(alpha, "TimedMoneyTree", "DrawReward", 4432, 5)["Status"], 0)
            worlds = []
            for prof, credit in ((alpha, 650), (beta, 660)):
                ev = prof.event_runtime.evaluate("timed_recruit:81", prof.state["player"])
                worlds.append(ev.instance_id)
                active = prof._ensure_timed_recruit_prog(81, ev.instance_id)
                active.update({"my_credit": credit, "out_zi_count": 4, "bless_num": 340})
                prof.save()
            self.assertEqual(worlds[0], worlds[1])
            self.assertEqual(
                rpc(alpha, "TimedRecruitInfo", "GetTimedRecruitInfo", 81)["Value"]["RankList"],
                rpc(beta, "TimedRecruitInfo", "GetTimedRecruitInfo", 81)["Value"]["RankList"],
            )
            alpha.event_runtime.configure_archive_mode("concurrent", carry_over_policy={"timed_recruit:81": {"pity": True}})
            emu.clock.advance(60)
            pending = {}
            for prof in (alpha, beta):
                mail = rpc(prof, "Reward", "Rewars")["Value"]
                self.assertEqual(len([r for r in mail if r["Title"].startswith("Kho Báu Quay Thưởng")]), 1)
                self.assertEqual(rpc(prof, "TimedLuckdrawInfo", "GetInfo")["Value"]["TimedLuckdrawInfo"]["Integral"], 0)
                pending[prof.profile_name] = mail
            self.assertEqual([r["Title"] for r in pending["normal"] if "Cây Tiền" in r["Title"]], ["Cây Tiền May Mắn — Mốc 10 Lượt"])
            self.assertEqual(rpc(alpha, "TimedRecruitInfo", "GetTimedRecruitInfo", 81)["Value"]["OutputHighHeroIntervalNum"], 4)
            self.assertEqual(rpc(beta, "TimedRecruitInfo", "GetTimedRecruitInfo", 81)["Value"]["OutputHighHeroIntervalNum"], 9)
            self.assertEqual(rpc(alpha, "TimedRecruitInfo", "GetTimedRecruitInfo", 82)["Value"]["OutputHighHeroIntervalNum"], 9)

            after_midnight = emu.clock.now()
            emu = GameEmulatorState(persist=True, data_dir=data_dir)
            emu.clock.set_fixed(after_midnight)
            for name in ("normal", "acct_2"):
                prof = emu.get_profile_by_name(name)
                self.assertEqual(rpc(prof, "Reward", "Rewars")["Value"], pending[name])
                slot_mail = next(r for r in pending[name] if r["Title"].startswith("Kho Báu Quay Thưởng"))
                self.assertEqual(rpc(prof, "Reward", "DrawGiftBags", [slot_mail["Id"]])["Status"], 0)
                self.assertNotEqual(rpc(prof, "Reward", "DrawGiftBags", [slot_mail["Id"]])["Status"], 0)
                archived = next(r for r in prof.event_runtime.rt["archive_history"] if r["event_id"] == "timed_slot")
                self.assertIn(archived["settlement"]["rank"], (4, 5))

    def test_60_r7_11_scheduled_and_rotating_resets_keep_banner_isolation(self) -> None:
        for mode in ("scheduled", "rotating"):
            with self.subTest(mode=mode):
                emu = GameEmulatorState(persist=False, new_player=True)
                prof = emu.get_profile_by_name("normal")
                prof.admin_prepare_account(target_lv=30)
                rt = prof.event_runtime
                now = emu.clock.now()
                id81, id82 = "timed_recruit:81", "timed_recruit:82"
                if mode == "scheduled":
                    rt.set_scheduled_window(id81, now - 60, now + 600)
                    rt.set_scheduled_window(id82, now - 60, now + 600)
                else:
                    rt.configure_archive_mode("rotating", rotation_pool=[id81, id82], rotation_anchor_ts=now - 60, rotation_duration_sec=600)
                rt.configure_archive_mode(mode, carry_over_policy={id81: {"pity": True}}, settle_unclaimed_credit=False)
                player = prof.state["player"]
                event81 = rt.evaluate(id81, player)
                event82 = rt.evaluate(id82, player)
                old = prof._ensure_timed_recruit_prog(81, event81.instance_id)
                old.update({"my_credit": 100, "out_zi_count": 2, "bless_num": 350, "bless_r": 0.4})
                with self.assertRaises(ValueError):
                    rt.manual_reset_event(id81, confirm="false", player=player)
                self.assertEqual(rt.evaluate(id81, player).instance_id, event81.instance_id)
                rt.manual_reset_event(id81, confirm=True, player=player, on_ended=prof._on_timed_event_ended)
                new81 = rt.evaluate(id81, player)
                self.assertNotEqual(new81.instance_id, event81.instance_id)
                self.assertEqual(rt.evaluate(id82, player).instance_id, event82.instance_id)
                new = prof._ensure_timed_recruit_prog(81, new81.instance_id)
                self.assertEqual((new["my_credit"], new["out_zi_count"], new["bless_num"], new["bless_r"]), (0, 2, 350, 0.4))
                self.assertTrue(rt.get_instance(event81.instance_id)["archived"])
                self.assertFalse(any("tr_unclaimed_credit:" in r["SourceKey"] for r in prof.state.get("rewards_center", [])))

    def test_61_r7_11_fresh_standalone_generates_independent_sample_without_save_seed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with patch.dict("os.environ", {"INUYASHA_SEED_DIR": str(Path(td) / "unbundled")}):
                emu = GameEmulatorState(persist=True, data_dir=Path(td) / "saves")
                a, sample, b = emu.list_s1_accounts()["Accounts"]
                self.assertEqual((a["IsNewPlayer"], b["IsNewPlayer"]), (1, 1))
                self.assertEqual((sample["PlayerName"], sample["Lv"], sample["Vip"]), ("Mẫu S1", 20, 3))
                self.assertEqual(len({a["PlayerId"], sample["PlayerId"], b["PlayerId"]}), 3)


class R712DeltaTest(unittest.TestCase):
    @staticmethod
    def rpc(profile, module, method, *data):
        return profile.handle_rpc({"ModuleName": module, "MethodName": method, "Data": list(data)})

    @staticmethod
    def emulator(root, *, new_player=False):
        return GameEmulatorState(
            env="dev", persist=True, new_player=new_player, data_dir=root, trace_path=root / "trace.log",
        )

    def test_unsupported_bag_output_preserves_item_after_reload(self):
        with tempfile.TemporaryDirectory() as dest:
            emu = self.emulator(Path(dest), new_player=True)
            prof = emu.get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=44)
            order = self.rpc(prof, "PlayerCharge", "GenerateOrderID", 6480)["Value"]
            self.assertEqual(self.rpc(prof, "PlayerCharge", "ConfirmOrder", 6480, order)["Status"], 0)
            for _ in range(8):
                self.assertEqual(self.rpc(prof, "Timespike", "ReceivedReward")["Status"], 0)
            item = next(g for g in prof.state["goods"] if g["GoodsModelId"] == 16020039)
            self.assertEqual(item["Num"], 3)
            out_code = str(prof.game_data["goods_model"]["16020039"]["goodsOutputOddsCode"])
            rows = list(prof.game_data["goods_output"][out_code].values())
            orig_types = [r["outputTypeID"] for r in rows]
            try:
                for row in rows:
                    row["outputTypeID"] = 9999
                for count in (1, 3):
                    rejected = self.rpc(prof, "Goods", "GoodsUse", item["Id"], 16020039, count)
                    self.assertEqual(rejected["Status"], -2009)
                    self.assertNotIn("GoodsInfo", rejected["Avatar"])
                    self.assertEqual(prof._get_goods_qty(16020039), 3)
            finally:
                for row, orig in zip(rows, orig_types):
                    row["outputTypeID"] = orig
            self.assertEqual(self.rpc(prof, "HeroRecruit", "Recruit", 1, 0)["Status"], 0)
            reloaded = self.emulator(Path(dest)).get_profile_by_name("normal")
            self.assertEqual(reloaded._get_goods_qty(16020039), 3)

    def test_hero_bag_boundaries_reward_claim_and_legacy_expansions(self):
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            prof = self.emulator(root, new_player=True).get_profile_by_name("normal")
            prof.admin_prepare_account(target_lv=23)
            prof.state["player"]["Diamond"] = 5000
            prof.state["heroes"].extend(prof._build_hero_instance(12011014) for _ in range(299))
            deployed_ids = {s["HeroId"] for s in prof.state["slots"]}
            self.assertEqual(sum(h["Id"] not in deployed_ids for h in prof.state["heroes"]), 299)
            self.assertEqual(prof._bag_info(5)["Size"], 300)
            self.assertEqual(self.rpc(prof, "HeroRecruit", "Recruit", 1, 0)["Status"], 0)
            gold, diamond = (prof.state["player"][field] for field in ("Gold", "Diamond"))
            self.assertEqual(self.rpc(prof, "HeroRecruit", "Recruit", 1, 0)["Status"], -2005)
            self.assertEqual(prof.state["player"]["Diamond"], diamond)

            prof._grant_resources_from_tuples([(1606, 16060008, 1)], source="test", tx_prefix="test:chest")
            chest = next(g for g in prof.state["goods"] if g["GoodsModelId"] == 16060008)
            self.assertEqual(self.rpc(prof, "Goods", "GoodsUseForBoxChoice", chest["Id"], 16060008, 12011004)["Status"], -2005)
            self.assertEqual(prof._get_goods_qty(16060008), 1)
            prof._push_reward_center_entry(
                source_key="capacity", title="Test", content="Test",
                res_tuples=[(1112, 0, 10), (1201, 12011004, 1)],
            )
            reward = prof.state["rewards_center"][-1]
            self.assertEqual(self.rpc(prof, "Reward", "DrawGiftBags", [reward["Id"]])["Status"], -2005)
            self.assertEqual(prof.state["player"]["Gold"], gold)
            self.assertFalse(reward["Claimed"])

            # R7.11 saves hold only the purchased expansions; reload twice across the new code.
            prof.state["bag_expansions"] = {"5": 2, "4": 1}
            prof.save()
            expected_hero_ids = [h["Id"] for h in prof.state["heroes"]]
            for _ in range(2):
                prof = self.emulator(root).get_profile_by_name("normal")
                self.assertEqual(prof._bag_info(5), {"BagModelId": 5, "Size": 310, "ExpandNum": 2})
                self.assertEqual(prof._bag_info(4)["Size"], 205)
                self.assertEqual([h["Id"] for h in prof.state["heroes"]], expected_hero_ids)
                prof.save()
            self.assertEqual(self.rpc(prof, "Reward", "DrawGiftBags", [reward["Id"]])["Status"], 0)
            self.assertEqual(self.rpc(prof, "Goods", "GoodsUseForBoxChoice", chest["Id"], 16060008, 12011004)["Status"], 0)
            for expansion in range(3, 21):
                result = self.rpc(prof, "Bag", "BagExpand", 5)
                self.assertEqual(result["Value"]["Size"], 300 + expansion * 5)
            balance = prof.state["player"]["Diamond"]
            self.assertNotEqual(self.rpc(prof, "Bag", "BagExpand", 5)["Status"], 0)
            self.assertEqual(prof.state["player"]["Diamond"], balance)
            self.assertEqual(prof._bag_info(5)["Size"], 400)
            self.assertEqual(prof.game_data["module_subs"]["1500"]["openLv"], 24)

    def test_pray_tree_qualifies_by_confirmed_in_period_charge(self):
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            emu = self.emulator(root, new_player=True)
            emu.clock.set_fixed(1795136400 + 3600)
            prof = emu.get_profile_by_name("normal")
            start = emu.clock.midnight_ts(emu.clock.now())
            orders = prof.state["charge_state"]["orders"]
            for key, tier, status, stamp in (
                ("past", 6480, "completed", start - 1),
                ("current", 180, "completed", start + 1),
                ("pending", 6480, "pending", start + 1),
            ):
                orders[key] = {"ProductId": f"com.cmn.inuyasha.gem{tier}", "status": status, "completed_at": stamp}
            prof.state["stats"].update({"recharged_diamonds": 6660, "spent_diamonds": 9000})
            prof.state["player"]["VipEXP"] = 6660
            prof.save()
            emu2 = self.emulator(root)
            emu2.clock.set_fixed(emu.clock.now())
            prof = emu2.get_profile_by_name("normal")

            def info():
                return self.rpc(prof, "TimedHopetreeInfo", "GetInfo")["Value"]

            self.assertEqual(info()["Num"], 180)
            self.assertEqual(info()["RewardList"][0]["CanDraw"], 0)
            self.assertNotEqual(self.rpc(prof, "TimedHopetreeInfo", "DrawReward", 1)["Status"], 0)
            for expected in (240, 300):
                order = self.rpc(prof, "PlayerCharge", "GenerateOrderID", 60)["Value"]
                self.assertEqual(self.rpc(prof, "PlayerCharge", "ConfirmOrder", 60, order)["Status"], 0)
                self.assertNotEqual(self.rpc(prof, "PlayerCharge", "ConfirmOrder", 60, order)["Status"], 0)
                self.assertEqual(info()["Num"], expected)
            self.assertEqual(info()["RewardList"][0]["CanDraw"], 1)
            self.assertEqual(self.rpc(prof, "TimedHopetreeInfo", "DrawReward", 1)["Status"], 0)
            self.assertNotEqual(self.rpc(prof, "TimedHopetreeInfo", "DrawReward", 1)["Status"], 0)
            reloaded = self.emulator(root)
            reloaded.clock.set_fixed(emu2.clock.now())
            prof = reloaded.get_profile_by_name("normal")
            self.assertEqual(info()["Num"], 300)
            self.assertEqual(info()["RewardList"][0]["Days"], 2)
            reloaded.clock.set_fixed(reloaded.clock.next_midnight_ts())
            self.assertEqual(info()["Num"], 0)
            self.assertNotEqual(self.rpc(prof, "TimedHopetreeInfo", "DrawReward", 1)["Status"], 0)
            card = self.rpc(prof, "CardInfo", "GenerateOrderID", 1)["Value"]
            self.assertEqual(self.rpc(prof, "CardInfo", "Activity", 1, card["OrderId"])["Status"], 0)
            self.assertEqual(info()["Num"], 300)
            self.assertEqual(self.rpc(prof, "TimedHopetreeInfo", "DrawReward", 1)["Status"], 0)

    def test_treasure_one_key_obeys_vn_gate_and_only_targets_missing_material(self):
        profile = GameEmulatorState(persist=False, new_player=True).get_profile_by_name("normal")
        profile.admin_prepare_account(target_lv=44)
        profile.state["player"]["STA"] = 20
        def loot(treasure):
            return self.rpc(profile, "TreasureLoot", "TreasureLootForOneKey", treasure)
        self.assertEqual(loot(14010501)["Status"], -5902)
        self.assertEqual(profile.state["player"]["STA"], 20)
        profile.admin_prepare_account(target_lv=14, vip_lv=7)
        profile.state["player"]["STA"] = 20
        received = loot(14010501)
        self.assertEqual(received["Status"], 0)
        value = received["Value"]
        self.assertEqual(value["TotalLootCount"], 3)
        self.assertEqual(set(value["LootInfo"].values()), {15032101, 15032102, 15032103})
        self.assertEqual(len(value["ChoiceGameResource"]), 3)
        self.assertEqual(profile.state["player"]["STA"], 14)
        self.assertEqual(loot(14010501)["Status"], -2010)
        self.assertEqual(self.rpc(profile, "TreasureDebris", "TreasureDebrisCompose", 14010501)["Status"], 0)
        profile.state["player"]["STA"] = 2
        value = loot(14020502)["Value"]
        self.assertEqual(list(value["LootInfo"].values()), [15040201])
        self.assertEqual(loot(14020502)["Status"], -1120)


class R7121RewardTest(unittest.TestCase):
    @staticmethod
    def call(emu, module, method, *data):
        return emu.handle_rpc({"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(data)})

    @staticmethod
    def seed_banner(profile, banner):
        _, event = profile._timed_recruit_active(explicit_act_id=banner)
        prog = profile._ensure_timed_recruit_prog(banner, event.instance_id)
        prog["pending_gold_hero"] = True
        return event.instance_id

    def test_banner_hero_choice_binds_all_six_heroes_to_exact_banner_and_instance(self):
        for banner, heroes in ((81, (12011004, 12012005, 12013005)), (82, (12011002, 12012004, 12013003))):
            for chosen in heroes:
                with self.subTest(banner=banner, chosen=chosen), tempfile.TemporaryDirectory() as dest:
                    root = Path(dest)
                    emu = R712DeltaTest.emulator(root, new_player=True)
                    profile = emu.get_profile_by_name("normal")
                    other = 82 if banner == 81 else 81
                    event_id = self.seed_banner(profile, banner)
                    peer_event_id = self.seed_banner(profile, other)
                    self.call(emu, "TimedRecruitInfo", "SelectBanner", other)
                    snap = self.call(emu, "TimedRecruitInfo", "GetTimedRecruitInfo", banner)["Value"]
                    self.assertEqual((snap["ActivityEnumId"], snap["EventInstanceId"], snap["DrawGoldHero"]), (banner, event_id, 0))
                    rpc = lambda *args: self.call(emu, "TimedRecruitInfo", "DrawGoldHero", *args)
                    num = len(profile.state["heroes"])
                    self.assertEqual(rpc(chosen, other, peer_event_id)["Status"], -3123)
                    self.assertEqual(rpc(chosen, banner, "expired")["Status"], -3106)
                    self.assertEqual(rpc(chosen, 999)["Status"], -3115)
                    self.assertEqual(len(profile.state["heroes"]), num)

                    picked = rpc(chosen, banner, event_id)
                    self.assertEqual(picked["Status"], 0)
                    self.assertEqual([h["HeroModelId"] for b in picked["Value"]["BaseGetGameResourceList"] for h in b["Hero"]], [chosen])
                    self.assertEqual(picked["Value"]["RecruitInfo"]["DrawGoldHero"], 1)
                    self.assertEqual(rpc(chosen, banner, event_id)["Status"], -3116)
                    self.assertEqual(self.call(emu, "TimedRecruitInfo", "GetTimedRecruitInfo", other)["Value"]["DrawGoldHero"], 0)
                    emu = R712DeltaTest.emulator(root)
                    self.assertEqual(rpc(chosen, banner, event_id)["Status"], -3116)
                    self.assertEqual(len(emu.get_profile_by_name("normal").state["heroes"]), num + 1)

    def test_full_bag_preserves_pending_choice_and_can_retry_after_reload(self):
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            emu = R712DeltaTest.emulator(root, new_player=True)
            profile = emu.get_profile_by_name("normal")
            event_id = self.seed_banner(profile, 81)
            profile.state["player"]["Diamond"] = 100
            profile.state["heroes"].extend(profile._build_hero_instance(12011014) for _ in range(300))
            self.call(emu, "Player", "GetInitData")
            profile.save()
            rejected = self.call(emu, "TimedRecruitInfo", "DrawGoldHero", 12011004, 81, event_id)
            self.assertEqual((rejected["Status"], rejected["Value"]), (-2005, {}))
            emu = R712DeltaTest.emulator(root)
            profile = emu.get_profile_by_name("normal")
            prog = profile.event_runtime.get_instance(event_id)["progress"]
            self.assertTrue(prog["pending_gold_hero"])
            self.assertEqual(prog.get("ur_grant_seq", 0), 0)
            self.assertEqual(profile.state["player"]["Diamond"], 100)
            self.assertEqual(self.call(emu, "Bag", "BagExpand", 5)["Status"], 0)
            self.assertEqual(self.call(emu, "TimedRecruitInfo", "DrawGoldHero", 12011004, 81, event_id)["Status"], 0)
            self.assertEqual(sum(h["HeroModelId"] == 12011004 for h in profile.state["heroes"]), 1)

    def test_achievement_4918_counts_distinct_equipped_item_levels_and_prevalidates_grant(self):
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            emu = R712DeltaTest.emulator(root, new_player=True)
            profile = emu.get_profile_by_name("normal")
            info = lambda: next(t for t in self.call(emu, "SuccessTargetInfo", "GetInfo")["Value"]["TargetList"] if t["TargetId"] == 19)
            claim = lambda: self.call(emu, "SuccessTargetInfo", "DrawReward", 19, 5)
            for kind, model, slot in ((1301, 13010716, "Weapon"), (1302, 13020716, "Helmet"),
                                      (1303, 13030716, "Clothes"), (1304, 13040716, "Necklace")):
                [eq] = profile._grant_resources_from_tuples(
                    [(kind, model, 1)], source="r7121-test", tx_prefix=f"r7121:{model}",
                )[0]["Equip"]
                eq.update(Lv=78, Step=0 if kind == 1304 else 1)
                profile.state["slots"][0][slot] = eq
            profile.state["success_target"] = {"start_ts": emu.clock.now() - 8 * 86400}
            target = info()
            self.assertEqual(target["SequenceInfo"]["5"], 3)
            self.assertFalse(target["Claimable"]["5"])
            self.assertEqual((claim()["Status"], info()["DrawNums"]), (-6001, ""))
            profile.state["equips"][-1]["Step"] = 1
            self.assertEqual(info()["SequenceInfo"]["5"], 4)
            self.assertTrue(info()["Claimable"]["5"])

            row = profile.game_data["success_target_reward"]["19"][4]
            reward = row["resourceList"]
            row["resourceList"] += "||9999,99999999,1"
            before = profile.state["player"]["Diamond"]
            self.assertEqual(claim()["Status"], -2009)
            self.assertEqual(profile.state["player"]["Diamond"], before)
            self.assertEqual(info()["DrawNums"], "")
            row["resourceList"] = reward
            self.assertEqual(claim()["Status"], 0)
            self.assertEqual(profile.state["player"]["Diamond"], before + 100)
            emu = R712DeltaTest.emulator(root)
            self.assertEqual(claim()["Status"], -3137)
            self.assertEqual(info()["DrawNums"], "5")
            self.assertFalse(info()["Claimable"]["5"])
            self.assertEqual(emu.get_profile_by_name("normal").state["player"]["Diamond"], before + 100)

    def test_daily_achievement_chest_only_claims_the_requested_day(self):
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            emu = R712DeltaTest.emulator(root, new_player=True)
            profile = emu.get_profile_by_name("normal")
            profile.state["success_target"] = {"start_ts": emu.clock.now() - 86400}
            info = self.call(emu, "SuccessTargetInfo", "GetInfo")["Value"]
            self.assertEqual([day["Day"] for day in info["DrawDay"]], [1, 2])
            self.assertFalse(next(t for t in info["TargetList"] if t["TargetId"] == 3)["Claimable"]["3"])
            total = lambda *args: self.call(emu, "SuccessTargetInfo", "DrawTotalReward", *args)
            self.assertEqual(total(3)["Status"], -6004)
            self.assertEqual(total()["Status"], -6004)
            day1 = total(1)
            self.assertEqual(day1["Status"], 0)
            self.assertEqual(day1["Value"]["DrawnDays"], [1])
            self.assertEqual(day1["Value"]["IfDraw"], 0)
            self.assertEqual([entry["Day"] for entry in day1["Value"]["DrawDay"]], [2])
            emu = R712DeltaTest.emulator(root)
            before = emu.get_profile_by_name("normal").state["player"]["Diamond"]
            self.assertEqual(total(1)["Status"], -3137)
            self.assertEqual(emu.get_profile_by_name("normal").state["player"]["Diamond"], before)
            self.assertEqual(total(2)["Value"]["DrawnDays"], [1, 2])

    def test_older_smash_egg_ledger_seed_without_saved_goods_recovers_on_init(self):
        with tempfile.TemporaryDirectory() as dest:
            root = Path(dest)
            emu = R712DeltaTest.emulator(root, new_player=True)
            profile = emu.get_profile_by_name("normal")
            player_id = profile.state["player"]["PlayerId"]
            event = profile.event_runtime.evaluate("timed_smash_egg", profile.state["player"])
            profile.save()
            key = f"evt:normal:{player_id}:{event.instance_id}:starter_hammers:0:goods:16050061"
            profile.ledger.record_grant_event(
                account_id=player_id, profile="normal", resource_type="Goods:16050061",
                amount=5, balance_after=5, source="smash_egg_starter_hammers", idempotency_key=key,
            )
            for _ in range(2):
                emu = R712DeltaTest.emulator(root)
                init = self.call(emu, "Player", "GetInitData")
                self.assertEqual(init["Status"], 0)
                hammers = [goods["Num"] for goods in init["Value"]["GoodsPropsInfo"] if goods["GoodsModelId"] == 16050061]
                self.assertEqual(hammers, [5])
                profile = emu.get_profile_by_name("normal")
                self.assertEqual(profile._get_goods_qty(16050061), 5)
                self.assertTrue(profile.event_runtime.get_instance(event.instance_id)["progress"]["starter_hammers_seeded"])
            entries = [json.loads(line) for line in (root / "audit_ledger.jsonl").read_text().splitlines()]
            self.assertEqual(sum(row["idempotency_key"] == key for row in entries), 1)


class HeroBreakthroughDeltaTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.profile = R712DeltaTest.emulator(self.root).profiles["normal"]
        self.profile.state["player"].update(Lv=42, Gold=2_000_000)
        self.profile.state["goods"] = []
        R712DeltaTest.rpc(self.profile, "Player", "GetInitData")

    def step_up(self, hero, materials, *expected_step):
        return R712DeltaTest.rpc(self.profile, "Hero", "HeroStepUp", hero["Id"], materials, *expected_step)

    def hero(self, model, lv=1, step=0):
        hero = self.profile._build_hero_instance(model, lv=lv, step=step)
        self.profile.state["heroes"].append(hero)
        return hero

    def treasures(self, model, amount):
        bundles = self.profile._grant_resources_from_tuples(
            [(model // 10000, model, amount)], source="step_fixture",
            tx_prefix=f"step_fixture:{model}",
        )
        return bundles[0]["Treasure"]

    def goods(self, model, *amounts):
        for i, amount in enumerate(amounts):
            self.profile.state["goods"].append(
                {"GoodsModelId": model, "Id": f"goods-{model}-{i}", "Num": amount},
            )

    def inventory(self):
        state = self.profile.state
        return (
            state["player"]["Gold"],
            {item["Id"]: item["Num"] for item in state["goods"]},
            {item["Id"]: item["Step"] for item in state["heroes"]},
            {item["Id"] for item in state["treasures"]},
            {item["Id"] for item in state["equips"]},
        )

    def assert_rejected(self, status, hero, materials, *expected_step):
        before = self.inventory()
        self.assertEqual(self.step_up(hero, materials, *expected_step)["Status"], status)
        self.assertEqual(self.inventory(), before)

    def test_lv35_uses_target_hero_level_and_refreshes_stones_before_next_step(self):
        hero = self.hero(12011004, lv=34, step=3)
        ids_before = [item["Id"] for item in self.treasures(14010502, 2) + self.treasures(14020502, 2)]
        ids_after = [item["Id"] for item in self.treasures(14010501, 4) + self.treasures(14020501, 4)]
        ids_before.insert(0, self.hero(12011004)["Id"])
        ids_after.insert(0, self.hero(12011004)["Id"])
        self.goods(16050001, 3500)
        reply = self.step_up(hero, ids_before, 3)
        self.assertEqual(reply["Status"], 0)
        self.assertEqual([item["Num"] for item in reply["Avatar"]["GoodsInfo"]["16050001"]], [2100])
        self.assert_rejected(-1217, hero, ids_after, 4)  # Player Lv42, target hero Lv34
        hero["Lv"] = 35
        self.assert_rejected(-1802, hero, ids_after, 4)
        stones = next(item for item in self.profile.state["goods"] if item["GoodsModelId"] == 16050001)
        stones["Num"] += 100
        reply = self.step_up(hero, ids_after, 4)
        self.assertEqual(reply["Status"], 0)
        self.assertEqual(reply["Value"]["Step"], 5)
        self.assertEqual(reply["Avatar"]["GoodsInfo"], {"16050001": []})
        self.assertEqual(self.inventory()[0], 1_200_000)
        self.assertFalse(set(ids_before + ids_after) & (set(self.inventory()[2]) | self.inventory()[3]))
        self.assert_rejected(-1217, hero, [], 5)  # Next gate is Lv40

    def test_lv35_rejects_wrong_missing_duplicate_upgraded_or_equipped_entities(self):
        self.goods(16050001, 2200)
        hero = self.hero(12011004, lv=35, step=4)
        duplicate = self.hero(12011004)
        books = self.treasures(14010501, 4)
        horses = self.treasures(14020501, 4)
        wrong_book = self.treasures(14010502, 1)[0]
        wrong_hero = self.hero(12012005)
        ids = [duplicate["Id"]] + [item["Id"] for item in books + horses]
        self.assert_rejected(-1602, hero, ids[:-1], 4)
        self.assert_rejected(-1602, hero, [wrong_hero["Id"], *ids[1:]], 4)
        self.assert_rejected(-1602, hero, [*ids[:-1], wrong_book["Id"]], 4)
        self.assert_rejected(-1602, hero, [*ids[:-1], "missing-id"], 4)
        self.assert_rejected(-1221, hero, [*ids[:-1], ids[-2]], 4)
        self.assert_rejected(-1220, hero, [hero["Id"], *ids[1:]], 4)
        self.profile.state["slots"][1]["HeroId"] = duplicate["Id"]
        self.assert_rejected(-1206, hero, ids, 4)
        self.profile.state["slots"][1]["HeroId"] = hero["Id"]
        duplicate["Lv"] = 2
        self.assert_rejected(-1602, hero, ids, 4)
        duplicate["Lv"] = 1
        self.profile.state["slots"][1]["Book"] = books[0].copy()
        self.assert_rejected(-1405, hero, ids, 4)
        self.profile.state["slots"][1].pop("Book")
        books[0]["Lv"] = 1
        self.assert_rejected(-1602, hero, ids, 4)
        books[0]["Lv"] = 0
        horses[0]["Step"] = 1
        self.assert_rejected(-1602, hero, ids, 4)
        horses[0]["Step"] = 0
        self.profile.state["player"]["Gold"] = 549999
        self.assert_rejected(-1118, hero, ids, 4)
        self.profile.state["player"]["Gold"] += 1
        self.assertEqual(self.step_up(hero, ids, 4)["Status"], 0)
        self.assertEqual(self.inventory()[0], 0)
        self.assertIn(wrong_book["Id"], self.inventory()[3])

    def test_main_hero_lv35_naohi_and_stones_across_multiple_stacks(self):
        hero = next(h for h in self.profile.state["heroes"] if h["HeroModelId"] in (12010001, 12010004))
        hero.update(Lv=35, Step=4)
        treasures = self.treasures(14010501, 2) + self.treasures(14020501, 2)
        self.goods(16050001, 1000, 1550)
        self.goods(16050090, 100, 299)
        materials = [item["Id"] for item in treasures]
        self.assert_rejected(-1802, hero, materials, 4)
        self.profile.state["goods"][-1]["Num"] += 1
        reply = self.step_up(hero, materials, 4)
        self.assertEqual(reply["Status"], 0)
        self.assertEqual(reply["Avatar"]["GoodsInfo"]["16050090"], [])
        self.assertEqual([item["Num"] for item in reply["Avatar"]["GoodsInfo"]["16050001"]], [50])
        self.assertEqual(self.inventory()[0], 1_600_000)
        self.assertFalse(self.inventory()[3])

    def test_early_step_replay_concurrent_and_after_reload(self):
        hero = next(h for h in self.profile.state["heroes"] if h["HeroModelId"] in (12010001, 12010004))
        hero.update(Lv=10, Step=0)
        self.goods(16050001, 600)
        self.profile.save()
        with ThreadPoolExecutor(max_workers=2) as clients:
            replies = list(clients.map(lambda _: self.step_up(hero, {}, 0)["Status"], range(2)))
        self.assertCountEqual(replies, [0, -39])
        self.assertEqual(self.inventory()[0], 1_980_000)
        self.assertEqual(self.profile._get_goods_qty(16050001), 500)
        self.profile = R712DeltaTest.emulator(self.root).profiles["normal"]
        self.assert_rejected(-39, hero, [], 0)
        self.assert_rejected(-47, hero, [])
        self.assertEqual(self.step_up(hero, [], 1)["Status"], 0)
        self.assertEqual(self.profile._get_goods_qty(16050001), 100)
        self.assertEqual(self.inventory()[0], 1_930_000)

    def test_lv35_failed_save_rolls_back_and_retry_commits_once(self):
        hero = self.hero(12011004, lv=35, step=4)
        mats = [item["Id"] for item in self.treasures(14010501, 4) + self.treasures(14020501, 4)]
        mats.insert(0, self.hero(12011004)["Id"])
        self.goods(16050001, 2200)
        self.profile.save()
        saved = self.profile.state_path.read_bytes()
        audit = self.profile.ledger.audit_log_path.read_bytes()
        with patch.object(self.profile, "_write_json_atomic", side_effect=OSError("test storage error")):
            with self.assertLogs(level="ERROR"):
                self.assert_rejected(-7, hero, mats, 4)
        self.assertEqual(self.profile.state_path.read_bytes(), saved)
        self.assertEqual(self.profile.ledger.audit_log_path.read_bytes(), audit)
        self.assertEqual(self.step_up(hero, mats, 4)["Status"], 0)
        committed = self.inventory()
        self.profile = R712DeltaTest.emulator(self.root).profiles["normal"]
        self.assertEqual(self.inventory(), committed)
        self.assert_rejected(-39, hero, mats, 4)
        rows = self.profile.ledger.list_transactions()
        self.assertEqual([row["amount"] for row in rows if row["source"] == "hero_step_up:12011004"], [-550000])

    def test_max_step_or_invalid_payload_leaves_inventory_intact(self):
        hero = self.hero(12011004, lv=75, step=15)
        self.goods(16050001, 10000)
        self.assert_rejected(-1214, hero, [], 15)
        early = self.hero(12011004, lv=1)
        self.assert_rejected(-1602, early, [hero["Id"]], 0)
        self.assert_rejected(-48, early, {"extra": hero["Id"]}, 0)
        self.assert_rejected(-48, early, [], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
