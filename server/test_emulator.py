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
from emulator import GameEmulatorState, ThreadingEmulatorServer


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
        prof.handle_rpc({"ModuleName": "Explore", "MethodName": "OneKeyExplore", "Data": []})
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

        # Grant diamonds via step reward 1602 (200) + paid Recruit type 2 (80)
        prof.handle_rpc({"ModuleName": "Player", "MethodName": "GetStepCountReward", "Data": [1602]})
        r_paid = prof.handle_rpc({"ModuleName": "HeroRecruit", "MethodName": "Recruit", "Data": [2, 0]})
        self.assertEqual(r_paid["Status"], 0)
        self.assertEqual(prof.state["player"]["Diamond"], 120)

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

        # Explore: BuyExploreNum (-20 Diamond, +5 RemainNum) & DrawDailyReward (50/75/100) threshold + idempotency
        exp_buy = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "BuyExploreNum", "Data": []})
        self.assertEqual(exp_buy["Status"], 0)
        self.assertEqual(exp_buy["Value"]["ResetNum"], 1)
        self.assertEqual(prof.state["player"]["Diamond"], 100)

        early_daily = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "DrawDailyReward", "Data": [50]})
        self.assertEqual(early_daily["Status"], -1)
        while prof.state["explore"]["DailyNum"] < 50:
            if prof.state["explore"]["RemainNum"] <= 0:
                prof.state["explore"]["RemainNum"] = 10
            prof.handle_rpc({"ModuleName": "Explore", "MethodName": "OneKeyExplore", "Data": []})
        ok_daily = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "DrawDailyReward", "Data": [50]})
        self.assertEqual(ok_daily["Status"], 0)
        dup_daily = prof.handle_rpc({"ModuleName": "Explore", "MethodName": "DrawDailyReward", "Data": [50]})
        self.assertEqual(dup_daily["Status"], -1)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
