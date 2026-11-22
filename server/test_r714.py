"""Test the Delta for Insight Pursuit, equipment tiers and Mộ Thần Binh."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from emulator import GameEmulatorState


class R714DeltaTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.reload()
        self.profile.state["player"].update(Lv=28, IsNewPlayer=0)
        self.rpc("Player", "GetInitData")

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "trace.log")
        self.emu.clock.set_fixed(1795176000)
        self.profile = self.emu.profiles["normal"]

    def rpc(self, module, method, *data, profile=None):
        return (profile or self.profile).handle_rpc({"ServerId": 1, "ModuleName": module,
                                                     "MethodName": method, "Data": list(data)})

    def star(self, method="GetLightenStarInfo"):
        return self.rpc("LightenStar", method)

    def bdd(self, method="Info", *data, profile=None):
        return self.rpc("BddInfo", method, *data, profile=profile)

    def test_node_23_reports_unspent_stars_and_deducts_only_on_success(self):
        state = self.profile.state
        state["player"].update(StarId=22, Gold=18000)
        state["battle"]["StarCount"] = 68
        state["explore"].update(MaxNum=27, RemainNum=10)
        snapshot = self.star()["Value"]
        self.assertEqual((snapshot["StarId"], snapshot["StarCount"], snapshot["StarCountTotal"]), (22, 2, 68))
        self.assertEqual(self.star("LightenStar")["Status"], -2213)
        self.assertEqual(state["player"]["Gold"], 18000)
        state["battle"]["StarCount"] = 69
        result = self.star("LightenStar")
        self.assertEqual(result["Status"], 0)
        self.assertEqual((result["Value"]["StarId"], result["Value"]["StarCount"]), (23, 0))
        self.assertEqual(state["battle"]["StarCount"], 69)
        self.assertEqual(state["player"]["Gold"], 15000)
        self.assertEqual((state["explore"]["MaxNum"], state["explore"]["RemainNum"]), (27, 10))
        self.reload()
        self.assertEqual(self.star()["Value"], result["Value"])

    def test_lighten_progress_uses_vn_slots_properties_and_explore_delta(self):
        state = self.profile.state
        guildless_hero = self.profile._build_hero_instance(12011004, lv=28)
        state["heroes"].append(guildless_hero)
        # VN Attrtree node 28 targets formation slot 5 and unlocks slot 6.
        state["slots"][4].update(HeroId=guildless_hero["Id"], HeroModelId=guildless_hero["HeroModelId"])
        state["embattle"]["Formation5"] = 5
        state["player"].update(StarId=27, Gold=100_000)
        state["battle"]["StarCount"] = 90
        state["explore"].update(MaxNum=27, RemainNum=10)
        self.profile._recalc_all_slots_and_fap()
        self.assertNotIn(16, self.star()["Value"]["UnlockedSlotIds"])
        before = state["slots"][4]["Property"]["AP"]
        reply = self.star("LightenStar")
        self.assertIn(16, reply["Value"]["UnlockedSlotIds"])
        self.assertEqual(reply["Avatar"]["SlotInfo"][4]["Property"]["AP"], before + 7)
        node = self.rpc("Battle", "GetFightInfo", 11, 1111, 1)["Value"]["FightInfo"]["FightObjs"][0]
        self.assertEqual(node["Heros"][4]["AP"], before + 7)
        progressed = self.star("LightenStarForOneKey")["Value"]
        self.assertEqual((progressed["StarId"], progressed["StarCount"]), (30, 0))
        self.assertEqual(state["explore"]["MaxNum"], 28)
        self.assertEqual(state["explore"]["RemainNum"], 11)

    def test_lighten_higher_nodes_gold_gate_level_gate_and_last_node(self):
        player = self.profile.state["player"]
        battle = self.profile.state["battle"]
        player.update(StarId=47, Gold=5999)
        battle["StarCount"] = 144
        self.assertEqual(self.star("LightenStar")["Status"], -1118)
        self.assertEqual(player["Gold"], 5999)
        player.update(Gold=6000)
        with patch.dict(self.profile.game_data["attrtree"]["48"], needLV=29):
            self.assertEqual(self.star("LightenStarForOneKey")["Status"], -2212)
        self.assertIn(21, self.star("LightenStar")["Value"]["UnlockedSlotIds"])
        player.update(StarId=999, Gold=307500)
        battle["StarCount"] = 3000  # Synthetic coverage of the terminal rule.
        self.assertEqual(self.star("LightenStar")["Value"]["StarId"], 1000)
        self.assertEqual(self.star("LightenStar")["Status"], -2211)

    def test_lighten_save_failure_rolls_back_both_resources(self):
        self.profile.state["battle"]["StarCount"] = 9
        self.profile.save()
        start = self.profile.state_path.read_bytes()
        gold = self.profile.state["player"]["Gold"]
        with patch.object(self.profile, "save", side_effect=OSError("disk full")):
            with self.assertLogs(level="ERROR"):
                self.assertEqual(self.star("LightenStarForOneKey")["Status"], -7)
        self.assertEqual(self.profile.state_path.read_bytes(), start)
        self.assertEqual(self.star()["Value"]["StarCount"], 9)
        self.assertEqual(self.profile.state["player"]["Gold"], gold)

    def test_equipment_vn_color_boundaries_and_reload(self):
        models = self.profile.game_data["equips"]
        recipes = self.profile.game_data["equip_color"]
        self.assertEqual({int(color): row["colorFinally"] for color, row in recipes.items()},
                         {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 0})
        self.assertEqual(max(model["colorLV"] for model in models.values()), 8)
        self.profile.state["player"]["Gold"] = 40_000_000
        for color in range(1, 9):
            mid = next(int(key) for key, model in models.items() if model["colorLV"] == color and model["typeID"] == 1301)
            inputs = [self.profile._build_equip_instance(mid) for _ in range(5)]
            self.profile.state["equips"].extend(inputs)
            ids = [item["Id"] for item in inputs]
            gold = self.profile.state["player"]["Gold"]
            reply = self.rpc("Equip", "EquipCompose", ids)
            if color <= 6:
                self.assertEqual(reply["Status"], 0)
                out, = reply["Value"]["BaseGetGameResourceList"][0]["Equip"]
                self.assertEqual(models[str(out["EquipModelId"])]["colorLV"], color + 1)
                self.assertEqual(reply["Avatar"]["Gold"], gold - recipes[str(color)]["colorUpUseNum"])
            else:
                self.assertEqual(reply["Status"], -1321)
                self.assertEqual(self.profile.state["player"]["Gold"], gold)
                self.assertTrue(set(ids) <= {item["Id"] for item in self.profile.state["equips"]})
        self.profile.save()
        self.reload()
        self.assertEqual(self.profile.state["player"]["Gold"], gold)

    def test_bdd_catalogue_at_lv_28_and_canonical_gates(self):
        self.profile.state["player"]["Lv"] = 25
        self.assertEqual(self.bdd("Info", 1, 1, 1, 1)["Status"], -1127)
        self.profile.state["player"]["Lv"] = 28
        reply = self.bdd("Info", 1, 1, 1, 1)
        self.assertEqual(reply["Status"], 0)
        value = reply["Value"]
        self.assertEqual(len(value["Catalogue"]), 51)
        self.assertEqual(len(self.profile.game_data["bdd"]["points"]), 153)
        self.assertEqual(value["PlayableCount"], 51)
        self.assertTrue(value["Simulation"])
        self.assertEqual([item["Locked"] for item in value["NodeInfo"]], [False, True, True])
        self.assertEqual(self.bdd("GetFightInfo", 1311, 1)["Status"], -1716)
        self.assertEqual(self.bdd("GetFightInfo", 1112, 1)["Status"], -1716)
        self.assertEqual(self.bdd("GetFightInfo", 1111, 4)["Status"], -1713)
        self.assertEqual(self.bdd("OneKeyThreeStar")["Status"], -1127)

    def prepare_team(self):
        state = self.profile.state
        state["player"]["Lv"] = 60
        for i, mid in enumerate((12011004, 12011005, 12011006, 12011007, 12011012), start=1):
            hero = self.profile._build_hero_instance(mid, lv=65, step=10)
            state["heroes"].append(hero)
            slot = state["slots"][i - 1]
            slot.update(HeroId=hero["Id"], HeroModelId=mid)
            for equip_type, slot_key in self.profile.EQUIP_TYPE_TO_SLOT_KEY.items():
                model = equip_type * 10000 + 801
                equip = self.profile._build_equip_instance(model)
                equip["Lv"] = 150
                state["equips"].append(equip)
                slot[slot_key] = equip
            state["embattle"][f"Formation{i}"] = i
        self.profile._recalc_all_slots_and_fap()
        self.profile.save()

    @patch("bdd_handlers.PLAYABLE_FLOORS", (11, 12))
    def test_bdd_real_loss_sealed_round_and_all_six_wins_with_reload(self):
        weak = self.bdd("GetFightInfo", 1111, 1)["Value"]
        bad = self.bdd("Fight", 1111, 1, True, "", {}, "wrong-token")
        self.assertEqual(bad["Status"], -39)
        lost = self.bdd("Fight", 1111, 1, True, "", {}, weak["FightToken"])
        self.assertFalse(lost["Value"]["IsSuccess"])
        self.assertEqual(self.bdd()["Value"]["Info"]["Feats"], 0)
        self.prepare_team()
        self.emu.ensure_s1_account_slots(2)
        other = self.emu.s1_accounts["acct_2"]
        other.state["player"].update(Lv=28, IsNewPlayer=0)
        for index, node in enumerate((1111, 1112, 1113, 1211, 1212, 1213), start=1):
            fight = self.bdd("GetFightInfo", node, 3)
            self.assertEqual(fight["Status"], 0, fight)
            payload = fight["Value"]
            wave = payload["FightInfo"]["FightObjs"][0]
            target = int(self.profile.game_data["bdd"]["points"][str(node * 100 + 13)]["proposeFAP"])
            self.assertLessEqual(abs(wave["TeamData"][1]["Fap"] - target), 25)
            if index == 1:
                self.assertEqual(self.bdd("Fight", node, 3, True, "", {}, payload["FightToken"], profile=other)["Status"], -39)
                self.reload()
                self.assertEqual(self.bdd("GetFightInfo", node, 3)["Value"], payload)
            won = self.bdd("Fight", node, 3, False, "", {}, payload["FightToken"])
            self.assertTrue(won["Value"]["IsSuccess"], won["Value"])
            self.assertEqual(won["Value"]["StarCount"], 3)
            self.assertEqual(self.bdd("Fight", node, 3, True, "", {}, payload["FightToken"])["Status"], -39)
            if index in (3, 6):
                self.assertEqual(self.bdd("RewardBox", node // 100, 9)["Status"], 0)
                self.assertEqual(self.bdd("RewardBox", node // 100, 9)["Status"], -39)
                if index == 3:
                    options = self.bdd("GetBuffs")["Value"]
                    self.assertEqual({option["NeedStars"] for option in options}, {3, 6, 9})
                    self.assertEqual(self.bdd("SelectBuff", options[0]["Id"])["Status"], 0)
        final = self.bdd()["Value"]["Info"]
        self.assertEqual((final["StarCount"], final["Feats"], final["MaxThreeFloor"]), (18, 430, 12))
        self.assertTrue(final["NeedReset"])
        self.assertEqual(self.bdd("Ranking")["Value"][0]["WeekStarCount"], 18)
        self.assertEqual(self.bdd("Reset")["Avatar"]["Diamond"], self.profile.state["player"]["Diamond"])
        self.assertEqual(self.bdd("OneKeyThreeStar")["Status"], 0)
        self.assertEqual(self.bdd()["Value"]["Info"]["StarCount"], 9)
        self.reload()
        self.assertEqual(self.bdd()["Value"]["Info"]["Feats"], 645)
        self.assertEqual(self.bdd()["Value"]["Info"]["MaxStarCount"], 18)

    def test_bdd_shop_exact_equipment_and_atomic_ledger(self):
        p = self.profile
        p.state["player"]["Merit"] = 1000
        p.state["bdd"] = {"max_stars": 20}
        item = p._build_equip_instance(13010404)
        item["Step"] = 10
        p.state["equips"].append(item)
        too_many = self.bdd("EquipShopExchange", 1, [item["Id"], "extra"])
        self.assertEqual(too_many["Status"], -1317)
        self.assertEqual(p.state["player"]["Merit"], 1000)
        p.save()
        with patch.object(p, "save", side_effect=OSError("disk full")):
            with self.assertLogs(level="ERROR"):
                self.assertEqual(self.bdd("EquipShopExchange", 1, [item["Id"]])["Status"], -7)
        self.assertIn(item, p.state["equips"])
        self.assertEqual(p.state["player"]["Merit"], 1000)
        exchange = self.bdd("EquipShopExchange", 1, [item["Id"]])
        self.assertEqual(exchange["Status"], 0)
        self.assertEqual(exchange["Value"]["Feats"], 700)
        self.assertEqual(self.bdd("EquipShopExchange", 1, [item["Id"]])["Status"], -2104)
        self.assertTrue(any(eq["EquipModelId"] == 13010503 for eq in p.state["equips"]))
        self.assertNotIn(item, p.state["equips"])
        self.reload()
        self.assertEqual(self.bdd("EquipShopInfo")["Value"]["EquipShopInfo"], [{"Id": 1, "Num": 1}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
