#!/usr/bin/env python3
"""Tests for TASK-N02A (R7.26): Nightmare Mode (639 stages), RebornGoods/RebornCoin foundation, & Campaign Ch 12-80 Wave Balance."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from combat_sim import simulate_fight_info
from emulator import EventClock, GAME_DATA_PATH, GameEmulatorState, ProfileStore, ResourceLedger


class R726NightmareAndBalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.game_data = json.loads(GAME_DATA_PATH.read_text(encoding="utf-8"))

    def _new_store(self, tmpdir: str, lv: int = 48, vit: int = 500) -> ProfileStore:
        store = ProfileStore(
            "normal",
            self.game_data,
            ResourceLedger(audit_log_path=Path(tmpdir) / "audit_ledger.jsonl", vip_model=self.game_data.get("vip_model", {})),
            state_path=Path(tmpdir) / "normal_profile.json",
            persist=True,
            reset=True,
            clock=EventClock(),
        )
        r = store.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["NightmareTester", 0]})
        self.assertEqual(r["Status"], 0)
        store.admin_prepare_account(target_lv=lv, vip_lv=5, source="test_r726")
        store._grant_resources_from_tuples(
            [(1102, 0, max(0, vit - int(store.state["player"]["VIT"]))), (1111, 0, 5000)],
            source="test_r726_setup",
            tx_prefix="test_r726_setup",
        )
        store.save()
        return store

    def _equip_strong_team(self, store: ProfileStore, lv: int = 80, step: int = 8) -> None:
        granted = store._grant_resources_from_tuples(
            [
                (1201, 12011004, 1), (1201, 12012005, 1), (1201, 12011002, 1),
                (1201, 12011003, 1), (1201, 12011005, 1),
                (1301, 13010602, 6), (1302, 13020602, 6), (1303, 13030602, 6), (1304, 13040602, 6),
                (1401, 14011615, 6), (1402, 14021615, 6),
                (1117, 0, 50000000), (1112, 0, 50000000),
            ],
            source="test_nm_team",
            tx_prefix=f"test_nm_team:{lv}:{step}",
        )
        for idx, h in enumerate(granted[0]["Hero"], start=2):
            store.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
            h["Lv"] = lv
            h["Step"] = step
        store.state["heroes"][0]["Lv"] = lv
        store.state["heroes"][0]["Step"] = step
        store.state["player"]["StarId"] = 120
        for s_id in range(1, 7):
            store.handle_rpc({"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [s_id]})
        books = granted[0]["Treasure"][:6]
        horses = granted[0]["Treasure"][6:12]
        for idx, sl in enumerate(store.state["slots"][:6]):
            books[idx]["Lv"] = 30
            horses[idx]["Lv"] = 30
            sl["Book"] = books[idx]
            sl["Horse"] = horses[idx]
            for ek in ("Weapon", "Helmet", "Clothes", "Necklace"):
                if isinstance(sl.get(ek), dict):
                    sl[ek]["Lv"] = lv
        store._recalc_all_slots_and_fap()
        store.save()

    def test_01_extracted_nightmare_configs_and_reborn_foundation(self) -> None:
        """Nightmare configs, RebornGoods (2701), and RebornCoin (1128) must extract, grant, piggyback, and persist."""
        self.assertEqual(len(self.game_data.get("nightmare_chapters", {})), 65)
        self.assertEqual(len(self.game_data.get("nightmare_nodes", {})), 639)
        self.assertEqual(len(self.game_data.get("nightmare_chapter_boxes", {})), 192)
        self.assertEqual(len(self.game_data.get("nightmare_node_drops", {})), 639)
        self.assertEqual(sum(len(v) for v in self.game_data["nightmare_node_drops"].values()), 899)
        self.assertEqual(len(self.game_data.get("nightmare_reset_use", {})), 3)
        self.assertEqual(len(self.game_data.get("reborn_goods", {})), 28)
        self.assertEqual(int(self.game_data["nightmare_config"]["perUseNum"]), 10)

        with tempfile.TemporaryDirectory() as td:
            store = self._new_store(td, lv=50)
            base_res = store._grant_resources_from_tuples(
                [(2701, 27010101, 4), (1128, 0, 150)],
                source="test_reborn_res",
                tx_prefix="test_reborn_res",
            )
            store.validate_base_resource_list(base_res, context="test_r726")
            self.assertEqual(int(store.state["player"]["RebornCoin"]), 150)
            self.assertEqual(int(store.state["reborn_goods"][0]["Num"]), 4)
            store.save()

            init = store.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": []})
            self.assertEqual(init["Status"], 0)
            self.assertEqual(int(init["Value"]["PlayerInfo"]["RebornCoin"]), 150)
            self.assertEqual(len(init["Value"]["RebornGoodsList"]), 1)
            self.assertEqual(int(init["Value"]["RebornGoodsList"][0]["ModelId"]), 27010101)
            self.assertEqual(int(init["Value"]["RebornGoodsList"][0]["Num"]), 4)

    def test_02_nightmare_progression_drops_boxes_and_skip(self) -> None:
        """Nightmare must gate needLV=48, drop RebornGoods (2701), unlock Ch12, claim boxes, and support isBreak skip."""
        with tempfile.TemporaryDirectory() as td:
            # 1. Lv 47 is blocked from Nightmare Ch 11 (needLV=48)
            low_lv = self._new_store(td, lv=47)
            self.assertNotEqual(low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "GetFightInfo", "Data": [11, 1111, 1]})["Status"], 0)

            # 2. Lv 48 with insufficient VIT (<10) returns -1119
            low_lv.admin_prepare_account(target_lv=48, source="test_nm_lv48")
            low_lv.state["player"]["VIT"] = 5
            low_lv.save()
            self.assertEqual(low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "GetFightInfo", "Data": [11, 1111, 1]})["Status"], -1119)

            # 3. Restore VIT & equip strong 6-hero Lv80 Step=8 team so isBreak skip wins cleanly
            low_lv.state["player"]["VIT"] = 500
            low_lv.admin_prepare_account(target_lv=80, vip_lv=8, source="test_nm_lv80")
            self._equip_strong_team(low_lv, lv=80, step=8)

            info = low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "GetNightmareInfo", "Data": [1, 1]})
            self.assertEqual(info["Status"], 0)
            self.assertEqual(info["Value"]["NightmareInfo"]["MaxChapterId"], 11)
            self.assertEqual(len(info["Value"]["ChapterList"]), 1)

            nodes = low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "GetNodeList", "Data": [11]})
            self.assertEqual(nodes["Status"], 0)
            self.assertEqual([n["NodeModelId"] for n in nodes["Value"]], [1111])

            # Fight Ch 11 nodes 1111..1115 (using isBreak=True skip on 1111, manual 6★ win on 1112..1115)
            fi_1111 = low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "GetFightInfo", "Data": [11, 1111, 1]})
            self.assertEqual(fi_1111["Status"], 0)
            res_1111 = low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "Fight", "Data": [11, 1111, 0, False, "", True]})
            self.assertEqual(res_1111["Status"], 0)
            self.assertEqual(res_1111["Value"]["IsSuccess"], "True")
            self.assertIn("TargetCsHp", res_1111["Value"])
            self.assertIn("RebornGoodsList", res_1111["Avatar"])

            # Ensure 1111 has 6★ too if skip lost any ally, then clear 1112..1115 to reach 30/30★
            for nid in (1112, 1113, 1114, 1115):
                r_n = low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "Fight", "Data": [11, nid, 6, True, "", False]})
                self.assertEqual(r_n["Status"], 0)
                if nid == 1115:
                    self.assertIn("NextChapter", r_n["Value"])
                    self.assertEqual(int(r_n["Value"]["NextChapter"]["ChapterModelId"]), 12)
                    self.assertEqual(int(r_n["Value"]["CurrentChapter"]["IfPass"]), 1)

            # Check Nightmare Ch11 drops accumulated RebornGoods (2701xxxx) + 16050065
            rb_models = {int(rg["ModelId"]): int(rg["Num"]) for rg in low_lv.state["reborn_goods"]}
            self.assertIn(27010101, rb_models)
            self.assertTrue(any(int(g["GoodsModelId"]) == 16050065 and int(g["Num"]) >= 10 for g in low_lv.state["goods"]))

            # AllChapterInfo returns Ch 11 & unlocked Ch 12
            aci = low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "AllChapterInfo", "Data": [[11, 12]]})
            self.assertEqual(aci["Status"], 0)
            self.assertEqual(len(aci["Value"]), 2)

            # Claim box 111 if 30★ reached
            if int(low_lv.state["nightmare"]["chapters"]["11"]["StarCount"]) >= 30:
                rc_before = int(low_lv.state["player"]["RebornCoin"])
                box_res = low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "DrawBox", "Data": [11, 111]})
                self.assertEqual(box_res["Status"], 0)
                self.assertEqual(int(low_lv.state["player"]["RebornCoin"]), rc_before + 150)
                # Duplicate claim rejected
                self.assertNotEqual(low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "DrawBox", "Data": [11, 111]})["Status"], 0)

            # DrawRoadBox unsupported in Nightmare -> -1
            self.assertNotEqual(low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "DrawRoadBox", "Data": [11, 111]})["Status"], 0)

            # OneKeyDrawBoxs with flat list syntax (DrawBoxRewardLayer.lua:226)
            low_lv.state["nightmare"]["chapters"]["12"]["StarCount"] = 60
            ok_box = low_lv.handle_rpc({"ModuleName": "Nightmare", "MethodName": "OneKeyDrawBoxs", "Data": [12, [121, 122]]})
            self.assertEqual(ok_box["Status"], 0)
            self.assertTrue(ok_box["Value"]["Chapter"]["IfDrawBoxA"])
            self.assertTrue(ok_box["Value"]["Chapter"]["IfDrawBoxB"])

    def test_03_nightmare_confight_hiautofight_and_reset_count(self) -> None:
        """Nightmare.ConFight, HiAutoFight, and ResetCount (200/300/500 Diamond) must enforce daily caps & costs."""
        with tempfile.TemporaryDirectory() as td:
            store = self._new_store(td, lv=60, vit=1000)
            # First clear 1111 manually
            res = store.handle_rpc({"ModuleName": "Nightmare", "MethodName": "Fight", "Data": [11, 1111, 6, True, "", False]})
            self.assertEqual(res["Status"], 0)

            # ConFight 3x using Diamond fallback (2 Diamond/run -> 6 Diamond, 30 VIT)
            dia_before = int(store.state["player"]["Diamond"])
            vit_before = int(store.state["player"]["VIT"])
            cf = store.handle_rpc({"ModuleName": "Nightmare", "MethodName": "ConFight", "Data": [11, 1111, 3]})
            self.assertEqual(cf["Status"], 0)
            self.assertEqual(int(store.state["player"]["Diamond"]), dia_before - 6)
            self.assertEqual(int(store.state["player"]["VIT"]), vit_before - 30)
            self.assertEqual(len(cf["Value"]["BaseGetGameResourceList"]), 3)

            # ConFight 2x using 16050011 sweep tokens (2 tokens/run -> 4 tokens, 0 Diamond)
            store._grant_resources_from_tuples([(1605, 16050011, 10)], source="tokens", tx_prefix="tokens")
            dia_tok = int(store.state["player"]["Diamond"])
            cf2 = store.handle_rpc({"ModuleName": "Nightmare", "MethodName": "ConFight", "Data": [11, 1111, 2]})
            self.assertEqual(cf2["Status"], 0)
            self.assertEqual(int(store.state["player"]["Diamond"]), dia_tok)
            rem_tok = next(g for g in store.state["goods"] if int(g["GoodsModelId"]) == 16050011)["Num"]
            self.assertEqual(int(rem_tok), 6)

            # ResetCount: 3 resets/day costing 200, 300, 500 Diamond; 4th rejected
            for cost in (200, 300, 500):
                d0 = int(store.state["player"]["Diamond"])
                rr = store.handle_rpc({"ModuleName": "Nightmare", "MethodName": "ResetCount", "Data": [11, 1111, 3]})
                self.assertEqual(rr["Status"], 0)
                self.assertEqual(int(rr["Value"]["FightCount"]), 0)
                self.assertEqual(int(store.state["player"]["Diamond"]), d0 - cost)
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Nightmare", "MethodName": "ResetCount", "Data": [11, 1111, 3]})["Status"], 0)

            # Advance 1 day -> ResetCount resets cleanly
            store.clock.mode = "offset"
            store.clock.offset_sec += 86400
            d1 = int(store.state["player"]["Diamond"])
            rr_next = store.handle_rpc({"ModuleName": "Nightmare", "MethodName": "ResetCount", "Data": [11, 1111, 3]})
            self.assertEqual(rr_next["Status"], 0)
            self.assertEqual(int(store.state["player"]["Diamond"]), d1 - 200)

            # HiAutoFight with strong team on 1112 runs real combat_sim cleanly
            store.admin_prepare_account(target_lv=80, vip_lv=8, source="hi_auto")
            self._equip_strong_team(store, lv=80, step=8)
            ha = store.handle_rpc({"ModuleName": "Nightmare", "MethodName": "HiAutoFight", "Data": [11, 1112, 1]})
            self.assertEqual(ha["Status"], 0)
            self.assertEqual(ha["Value"]["IsSuccess"], "True")

    def test_04_nightmare_rank_list_and_formation_with_s1_peers(self) -> None:
        """Nightmare.RankList and Formation must rank S1 peers + NPCs by StarCount and resolve peer & bot formations."""
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, data_dir=Path(td))
            emu.ensure_s1_account_slots(2)
            a1 = emu.s1_accounts["acct_1"]
            a2 = emu.s1_accounts["acct_2"]
            a1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["NmOne", 0]})
            a2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["NmStarQueen", 1]})
            a1.admin_prepare_account(target_lv=50, source="nm_rank")
            a2.admin_prepare_account(target_lv=65, source="nm_rank")
            a2._nightmare_state()["info"]["StarCount"] = 1850
            a2.save()

            rl = a1.handle_rpc({"ModuleName": "Nightmare", "MethodName": "RankList", "Data": []})
            self.assertEqual(rl["Status"], 0)
            entries = rl["Value"]["RankList"]
            self.assertEqual(len(entries), 50)
            self.assertTrue(all(entries[i]["StarCount"] >= entries[i + 1]["StarCount"] for i in range(len(entries) - 1)))

            a2_pid = str(a2.state["player"]["PlayerId"])
            peer_row = next((e for e in entries if e["Id"] == a2_pid), None)
            self.assertIsNotNone(peer_row)
            self.assertEqual(peer_row["StarCount"], 1850)

            fmt = a1.handle_rpc({"ModuleName": "Nightmare", "MethodName": "Formation", "Data": [peer_row["Rank"]]})
            self.assertEqual(fmt["Status"], 0)
            self.assertEqual(fmt["Value"]["Formation"]["PlayerInfo"]["PlayerId"], a2_pid)
            self.assertEqual(len(fmt["Value"]["Formation"]["SlotInfos"]), 6)

    def test_05_campaign_wave_balance_ch12_to_ch80_and_inversion_fix(self) -> None:
        """Campaign Ch 12-80 must scale monotonically (~8k -> ~275k FAP 1★), fixing Ch 25/46 q=6 inversion."""
        with tempfile.TemporaryDirectory() as td:
            store = self._new_store(td, lv=80, vit=1000)

            sample_chapters = (12, 15, 20, 25, 32, 46, 60, 70, 80)
            prev_fap = 0
            faps: dict[int, int] = {}
            for cid in sample_chapters:
                ch_nodes = sorted(
                    [n for n in self.game_data["nodes"].values() if int(n["chapterModelID"]) == cid],
                    key=lambda x: int(x["ID"]),
                )
                last = ch_nodes[-1]
                _, fap_1 = store._build_enemy_wave(int(last["ID"]), last, 1, 1, 1)
                faps[cid] = fap_1
                self.assertGreater(fap_1, prev_fap, f"Expected Ch {cid} ({fap_1}) > previous ({prev_fap})")
                prev_fap = fap_1

            # Specifically verify Ch 25 (q=6 pic) > Ch 20 (q=18 pic) and Ch 46 (q=6) > Ch 32 (q=15)
            self.assertGreater(faps[25], faps[20])
            self.assertGreater(faps[46], faps[32])
            # Ch 80 final stage 1★ FAP sits around ~250k - 310k (~3x pre-R7.26 90k; 2-wave 3★ hands off smoothly into Nightmare 550k)
            self.assertGreaterEqual(faps[80], 250000)
            self.assertLessEqual(faps[80], 310000)

            # Star 1★ < 2★ < 3★ scaling at Ch 23 node 2311
            n2311 = self.game_data["nodes"]["2311"]
            fap_stars = [store._build_enemy_wave(2311, n2311, 1, 1, s)[1] for s in (1, 2, 3)]
            self.assertLess(fap_stars[0], fap_stars[1])
            self.assertLess(fap_stars[1], fap_stars[2])

            # Ch 80 final stage beats a weak solo Lv48/unupgraded team and loses to an upgraded Lv80 Step=8 team
            n8020 = self.game_data["nodes"]["8020"]
            e80, fap80 = store._build_enemy_wave(8020, n8020, 1, 1, 1)
            weak_allies = store._build_ally_fight_objs()
            weak_outcome = simulate_fight_info(
                {"FightObjs": [{"Heros": weak_allies + e80, "TeamData": [{"Fsp": 1000, "Fap": 10000}, {"Fsp": 1000, "Fap": fap80}], "IsPVP": False, "RandNum": 7}]},
                self.game_data["attacks"],
                buffs_cfg=self.game_data["combat_buffs"],
            )
            self.assertFalse(weak_outcome.won)

            self._equip_strong_team(store, lv=80, step=8)
            strong_allies = store._build_ally_fight_objs()
            strong_outcome = simulate_fight_info(
                {"FightObjs": [{"Heros": strong_allies + e80, "TeamData": [{"Fsp": 5000, "Fap": int(store.state["player"]["FAP"])}, {"Fsp": 1000, "Fap": fap80}], "IsPVP": False, "RandNum": 7}]},
                self.game_data["attacks"],
                buffs_cfg=self.game_data["combat_buffs"],
            )
            self.assertTrue(strong_outcome.won)


if __name__ == "__main__":
    unittest.main()
