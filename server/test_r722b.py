"""R7.22B (TASK-M02) tests: MC evolution, EliteBattle drops, Battle.ResetCount cost, and BossBattle shop audit."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from emulator import GameEmulatorState


class R722BProgressionAndEconomyTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.now = 1795262400  # 2026-11-21 12:00:00 UTC
        self.reload()

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(self.now)
        self.p = self.emu.profiles["normal"]

    def rpc(self, module, method, *args):
        return self.emu.handle_rpc({"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(args)})

    def _goods_count(self, model_id: int) -> int:
        return sum(int(g.get("Num", 0)) for g in self.p.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == model_id)

    def test_main_hero_evolution_male_female_and_step_one(self):
        for gender, expected in (
            (0, [(0, 12010001), (1, 12010009), (4, 12010007), (113, 12010002), (348, 12010003)]),
            (1, [(0, 12010004), (1, 12010010), (4, 12010008), (113, 12010005), (348, 12010006)]),
        ):
            with self.subTest(gender=gender):
                td = tempfile.TemporaryDirectory()
                self.addCleanup(td.cleanup)
                emu = GameEmulatorState(data_dir=Path(td.name), env="dev", trace_path=Path(td.name) / "rpc.log")
                emu.clock.set_fixed(self.now)
                prof = emu.profiles["normal"]
                prof.handle_rpc({"ServerId": 1, "ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["MC", gender]})

                hero = prof.state["heroes"][0]
                hero_id = hero["Id"]
                self.assertEqual(hero["HeroModelId"], expected[0][1])

                prof.state["player"].update(Lv=100, Gold=50_000_000)
                prof.state["battle"]["StarCount"] = 5000

                for tier_id, model_id in expected[1:]:
                    # Advance just below or up to tier_id via LightenStar / LightenStarForOneKey
                    while int(prof.state["player"]["StarId"]) < tier_id:
                        rem = tier_id - int(prof.state["player"]["StarId"])
                        method = "LightenStarForOneKey" if rem >= 2 else "LightenStar"
                        # If rem < 50, OneKey advances at most to available stars; cap at exact tier_id on last hops
                        if method == "LightenStarForOneKey" and rem < 50:
                            last_res = None
                            while int(prof.state["player"]["StarId"]) < tier_id:
                                last_res = prof.handle_rpc({"ServerId": 1, "ModuleName": "LightenStar", "MethodName": "LightenStar", "Data": []})
                                self.assertEqual(last_res["Status"], 0)
                            res = last_res
                        else:
                            res = prof.handle_rpc({"ServerId": 1, "ModuleName": "LightenStar", "MethodName": method, "Data": []})
                            self.assertEqual(res["Status"], 0)

                    self.assertEqual(prof.state["player"]["StarId"], tier_id)
                    self.assertEqual(prof.state["heroes"][0]["Id"], hero_id)
                    self.assertEqual(prof.state["heroes"][0]["HeroModelId"], model_id)
                    self.assertEqual(prof.state["slots"][0]["HeroModelId"], model_id)
                    self.assertEqual(prof.state["player"]["HeadImageId"], model_id)
                    self.assertEqual(res["Avatar"]["SlotInfo"][0]["HeroModelId"], model_id)

                # Verify FightInfo carries evolved HeroModelId and quality-15 stats
                fi = prof.handle_rpc({"ServerId": 1, "ModuleName": "Battle", "MethodName": "GetFightInfo", "Data": [11, 1111, 1]})
                self.assertEqual(fi["Status"], 0)
                self.assertEqual(fi["Value"]["FightInfo"]["FightObjs"][0]["Heros"][0]["HeroModelId"], expected[-1][1])

        # Also check Step >= 1 at StarId == 0 evolves 12010001 -> 12010009 via Hero.HeroStepUp
        self.rpc("Player", "NewPlayer", "Stepper", 0)
        mc = self.p.state["heroes"][0]
        mc["Lv"] = 15
        self.p.state["player"].update(Lv=20, Gold=500000, StarId=0)
        self.p._grant_resources_from_tuples([(1605, 16050001, 100)], "test", "step_stone")
        res = self.rpc("Hero", "HeroStepUp", mc["Id"], [], 0)
        self.assertEqual(res["Status"], 0)
        self.assertEqual(mc["Step"], 1)
        self.assertEqual(mc["HeroModelId"], 12010009)
        self.assertEqual(self.p.state["slots"][0]["HeroModelId"], 12010009)
        self.assertEqual(res["Avatar"]["SlotInfo"][0]["HeroModelId"], 12010009)

    def test_main_hero_legacy_migration_on_load_and_non_mc_safety(self):
        self.rpc("Player", "NewPlayer", "LegacyMC", 0)
        mc = self.p.state["heroes"][0]
        self.p.state["player"]["Lv"] = 42
        mc["Lv"] = 42
        mc["Step"] = 5
        hero_id = mc["Id"]
        # Simulate pre-R7.22B legacy save where StarId=113 but HeroModelId stayed at 12010001
        self.p.state["player"]["StarId"] = 113
        mc["HeroModelId"] = 12010001
        self.p.state["slots"][0]["HeroModelId"] = 12010001
        self.p.state["player"]["HeadImageId"] = 12010001
        self.p.save()

        self.reload()
        loaded_mc = self.p.state["heroes"][0]
        self.assertEqual(loaded_mc["Id"], hero_id)
        self.assertEqual(loaded_mc["Lv"], 42)
        self.assertEqual(loaded_mc["Step"], 5)
        self.assertEqual(loaded_mc["HeroModelId"], 12010002)
        self.assertEqual(self.p.state["slots"][0]["HeroModelId"], 12010002)
        self.assertEqual(self.p.state["player"]["HeadImageId"], 12010002)
        self.assertEqual(self.p.state["player"]["FAP"], self.p.state["slots"][0]["Property"]["FAP"])

        # Non-MC hero placed in Slot 1 must NEVER be rewritten by AttrtreeHeromodelRelation
        inuyasha = self.p._build_hero_instance(12011004, lv=10, step=0)
        self.p.state["heroes"].append(inuyasha)
        self.p.state["slots"][0].update(HeroId=inuyasha["Id"], HeroModelId=12011004)
        self.p._recalc_all_slots_and_fap()
        self.assertEqual(self.p.state["slots"][0]["HeroModelId"], 12011004)
        self.assertEqual(inuyasha["HeroModelId"], 12011004)

    def test_elite_battle_drops_guaranteed_and_probabilistic(self):
        self.rpc("Player", "NewPlayer", "EliteTester", 0)
        self.p.state["player"].update(Lv=40, IsNewPlayer=0, VIT=200, Diamond=0)
        self.p.state["nodes"]["1217"] = self.p._make_node_state(1217, flag=2)

        # Case 1: only 10000 odds succeed (randint returns 9999 > 5000)
        with patch("emulator.random.randint", return_value=9999):
            stone_before = self._goods_count(16050001)
            soul_before = self._goods_count(16050011)
            frag_before = self._goods_count(15010064)
            res = self.rpc("EliteBattle", "Fight", 11, True, "", False)
        self.assertEqual(res["Status"], 0)
        self.assertEqual(self.p.state["player"]["Diamond"], 50)
        self.assertEqual(self._goods_count(16050001), stone_before + 10)
        self.assertEqual(self._goods_count(16050011), soul_before + 2)
        self.assertEqual(self._goods_count(15010064), frag_before)

        # Case 2: all odds succeed (randint returns 1 <= 5000)
        with patch("emulator.random.randint", return_value=1):
            frag_64_before = self._goods_count(15010064)
            frag_49_before = self._goods_count(15010049)
            glory_19_before = self._goods_count(16040019)
            glory_16_before = self._goods_count(16040016)
            res2 = self.rpc("EliteBattle", "Fight", 11, True, "", False)
        self.assertEqual(res2["Status"], 0)
        self.assertEqual(self.p.state["player"]["Diamond"], 100)
        self.assertEqual(self._goods_count(15010064), frag_64_before + 2)
        self.assertEqual(self._goods_count(15010049), frag_49_before + 3)
        self.assertEqual(self._goods_count(16040019), glory_19_before + 3)
        self.assertEqual(self._goods_count(16040016), glory_16_before + 1)

        # First-clear reward still works independently
        first = self.rpc("EliteBattle", "DrawFirstReward", 11)
        self.assertEqual(first["Status"], 0)
        self.assertEqual(self.p.state["player"]["Diamond"], 200)

    def test_battle_reset_count_uses_token_then_escalating_diamond_and_rollover(self):
        self.rpc("Player", "NewPlayer", "ResetTester", 0)
        node_st = self.p.state["nodes"]["1111"]
        node_st["FightCount"] = int(self.p.game_data["nodes"]["1111"]["fightNumMax"])

        # No tokens and Diamond=0 -> -1105 without mutating FightCount
        self.p.state["player"]["Diamond"] = 0
        fail_res = self.rpc("Battle", "ResetCount", 11, 1111)
        self.assertEqual(fail_res["Status"], -1105)
        self.assertGreater(node_st["FightCount"], 0)
        self.assertEqual(node_st["ResetFightCount"], 0)

        # Grant two 16050013 tokens across two stacks (1 + 1) and 50 Diamond
        self.p._grant_resources_from_tuples([(1605, 16050013, 1)], "test", "tok1")
        self.p._grant_resources_from_tuples([(1605, 16050013, 1)], "test", "tok2")
        self.p.state["player"]["Diamond"] = 50

        # Auto mode prefers token over Diamond (#1)
        res1 = self.rpc("Battle", "ResetCount", 11, 1111)
        self.assertEqual(res1["Status"], 0)
        self.assertEqual(self._goods_count(16050013), 1)
        self.assertEqual(self.p.state["player"]["Diamond"], 50)
        self.assertEqual(res1["Value"]["NodeModelId"], 1111)
        self.assertEqual(res1["Value"]["FightCount"], 0)
        self.assertEqual(res1["Value"]["ResetFightCount"], 1)
        self.assertEqual(res1["Value"]["ResetFightTime"], self.now)

        # Explicit token mode consumes remaining token (#2), then rejects when out of tokens
        node_st["FightCount"] = 5
        res2 = self.rpc("Battle", "ResetCount", 11, 1111, 2)
        self.assertEqual(res2["Status"], 0)
        self.assertEqual(self._goods_count(16050013), 0)
        self.assertEqual(res2["Value"]["ResetFightCount"], 2)

        fail_tok = self.rpc("Battle", "ResetCount", 11, 1111, 2)
        self.assertEqual(fail_tok["Status"], -1105)

        # Next reset is #3 -> costs 200 Diamond per BattleResetUseRelation[3]
        self.p.state["player"]["Diamond"] = 199
        fail_dia = self.rpc("Battle", "ResetCount", 11, 1111, 3)
        self.assertEqual(fail_dia["Status"], -1105)
        self.assertEqual(self.p.state["player"]["Diamond"], 199)

        self.p.state["player"]["Diamond"] = 200
        res3 = self.rpc("Battle", "ResetCount", 11, 1111)
        self.assertEqual(res3["Status"], 0)
        self.assertEqual(self.p.state["player"]["Diamond"], 0)
        self.assertEqual(res3["Value"]["ResetFightCount"], 3)

        # Persist across reload, verify cap=20, then roll over next day to cost 50 KC again
        self.reload()
        self.assertEqual(self.p.state["nodes"]["1111"]["ResetFightCount"], 3)
        self.p.state["nodes"]["1111"]["ResetFightCount"] = 20
        cap_res = self.rpc("Battle", "ResetCount", 11, 1111)
        self.assertEqual(cap_res["Status"], -1)

        self.now += 86400
        self.emu.clock.set_fixed(self.now)
        self.p.state["player"]["Diamond"] = 60
        day2_res = self.rpc("Battle", "ResetCount", 11, 1111)
        self.assertEqual(day2_res["Status"], 0)
        self.assertEqual(day2_res["Value"]["ResetFightCount"], 1)
        self.assertEqual(self.p.state["player"]["Diamond"], 10)

    def test_boss_battle_luckboss_value_shop_boxes_and_disabled_exchange_stub(self):
        self.rpc("Player", "NewPlayer", "BossBoxer", 0)
        self.p.state["player"]["BossCoin"] = 350
        self.p.state["boss_battle"]["jifen"] = 350

        boxes = self.rpc("BossBattle", "BoxList")
        self.assertEqual(boxes["Status"], 0)
        self.assertEqual(len(boxes["Value"]), len(self.p.game_data["luckboss_value_shop"]))
        self.assertEqual(len(boxes["Value"]), 35)

        draw1 = self.rpc("BossBattle", "DrawBox", 100)
        self.assertEqual(draw1["Status"], 0)
        draw_dup = self.rpc("BossBattle", "DrawBox", 100)
        self.assertEqual(draw_dup["Status"], -1)

        onekey = self.rpc("BossBattle", "OneKeyDrawBox")
        self.assertEqual(onekey["Status"], 0)
        boxes2 = self.rpc("BossBattle", "BoxList")["Value"]
        drawn_vals = [b["NeedValue"] for b in boxes2 if b["IsDraw"] == "True"]
        self.assertEqual(drawn_vals, [100, 200, 300])

        # Page 2 (ExchangeInfo / Exchange) is commented out in VN BossRewardPreviewLayer.lua
        ex_info = self.rpc("BossBattle", "ExchangeInfo")
        self.assertEqual(ex_info["Status"], 0)
        self.assertEqual(ex_info["Value"], [])


if __name__ == "__main__":
    unittest.main()
