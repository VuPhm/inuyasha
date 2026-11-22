"""Test the Delta for VN bonds, persisted mates, equipment steps and BDD UI data."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from combat_sim import simulate_fight_info
from emulator import EMPTY_ENTITY_ID, GameEmulatorState


class R7151DeltaTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.reload()
        self.profile.state["player"].update(Lv=35, IsNewPlayer=0, Gold=2_000_000, VIT=200)
        self.profile.save()

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "trace.log")
        self.emu.clock.set_fixed(1795176000)
        self.profile = self.emu.profiles["normal"]

    def rpc(self, module, method, *payload):
        return self.emu.handle_rpc({"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(payload)})

    def hero(self, model, lv=25):
        hero = self.profile._build_hero_instance(model, lv=lv)
        self.profile.state["heroes"].append(hero)
        return hero

    def deploy(self, index, hero):
        assert self.rpc("Slot", "HeroCombat", index, hero["Id"])["Status"] == 0
        self.profile.state["embattle"][f"Formation{index}"] = index

    def mate(self, index, hero=None):
        return self.rpc("Slot", "MateinfoCombat", index, hero["Id"] if hero else EMPTY_ENTITY_ID)

    def prop(self, index=1):
        return self.profile.state["slots"][index - 1]["Property"]

    def test_hero_groups_activate_only_with_every_member_in_formation(self):
        inu = self.hero(12011004)
        dad = self.hero(12011002)
        kikyo = self.hero(12011003)
        kaede = self.hero(12011012)
        self.deploy(1, inu)
        prior = self.prop().copy()
        self.assertNotIn(7, prior["ActivePrIds"])
        self.deploy(2, kikyo)
        self.assertNotIn(8, self.prop()["ActivePrIds"])
        self.deploy(3, kaede)
        self.assertEqual(self.prop()["ActivePrIds"], [8])
        self.assertEqual(self.prop()["HPR1"], 12200)
        self.assertEqual(self.prop()["HP"], prior["HP"] + prior["HP1"] * 2200 // 10000)
        self.deploy(4, dad)
        self.assertEqual(self.prop()["ActivePrIds"], [7, 8])
        self.assertEqual(self.prop()["AP"], prior["AP"] + prior["AP1"] * 2200 // 10000)
        self.assertEqual(self.rpc("Slot", "HeroCombat", 5, dad["Id"])["Status"], -1206)
        fight = self.rpc("Battle", "GetFightInfo", 11, 1111, 1)["Value"]["FightInfo"]
        hero_fight = fight["FightObjs"][0]["Heros"][0]
        self.assertEqual([hero_fight[key] for key in ("AP", "HP", "DEF")],
                         [self.prop()[key] for key in ("AP", "HP", "DEF")])
        outcome = simulate_fight_info(fight, self.profile.game_data["attacks"])
        self.assertTrue(outcome.won)
        self.rpc("Slot", "HeroCombat", 3, EMPTY_ENTITY_ID)
        self.assertEqual(self.prop()["ActivePrIds"], [7])
        self.assertEqual(self.prop()["HP"], prior["HP"])

    def test_replace_and_remove_mates_updates_power_once_and_survives_reload(self):
        self.deploy(1, self.hero(12011004))
        mate = self.hero(12011002)
        alternate = self.hero(12011008)
        initial = self.profile.state["player"]["FAP"]
        player = self.profile.state["player"]
        player["StarId"] = 47
        self.assertEqual(self.mate(1, mate)["Status"], -1127)
        player["StarId"] = 48
        result = self.mate(1, mate)
        self.assertEqual(result["Status"], 0)
        self.assertEqual(result["Value"]["MateInfo"], [{"SlotId": 1, "HeroId": mate["Id"], "HeroModelId": 12011002}])
        change = self.prop()["AP1"] * 2200 // 10000
        self.assertIn(7, self.prop()["ActivePrIds"])
        self.assertEqual(result["Avatar"]["FAP"], initial + change * 10 + self.profile._get_slot_star_bonuses(1)["HP"]
                         + 10 * sum(self.profile._get_slot_star_bonuses(1)[key] for key in ("AP", "DEF")))
        self.assertEqual(self.mate(1, mate)["Avatar"]["FAP"], result["Avatar"]["FAP"])
        self.assertEqual(self.rpc("Slot", "HeroCombat", 2, mate["Id"])["Status"], -1206)
        self.assertNotEqual(self.rpc("Hero", "HeroRebirth", [mate["Id"]])["Status"], 0)
        self.assertNotEqual(self.rpc("Hero", "HeroRefine", [mate["Id"]])["Status"], 0)
        with patch.object(self.profile, "save", side_effect=OSError("disk full")), self.assertLogs(level="ERROR"):
            self.assertEqual(self.mate(1, alternate)["Status"], -7)
        self.assertEqual(self.profile.state["mates"], {"1": mate["Id"]})
        self.reload()
        startup = self.rpc("Player", "GetInitData")["Value"]
        self.assertEqual(startup["MateInfo"], result["Value"]["MateInfo"])
        self.assertEqual(startup["PlayerInfo"]["FAP"], result["Avatar"]["FAP"])
        self.assertEqual(self.rpc("Slot", "SlotFormations")["Value"]["MateInfos"], startup["MateInfo"])
        alternate_result = self.mate(1, alternate)
        self.assertEqual(alternate_result["Avatar"]["FAP"], result["Avatar"]["FAP"] - change * 10)
        self.assertEqual(self.mate(1)["Value"]["MateInfo"][0]["HeroModelId"], 0)
        self.reload()
        self.assertEqual(self.rpc("Player", "GetInitData")["Value"]["MateInfo"], [])

    def test_gear_alternative_and_treasure_apply_only_to_the_wearer(self):
        profile = self.profile
        self.deploy(2, self.hero(12011004))
        prior = self.prop().copy()
        prior_ally = self.prop(2).copy()
        sword = profile._build_equip_instance(13010503)
        helmet = profile._build_equip_instance(13020404)
        profile.state["equips"].extend((sword, helmet))
        treasure = {"Id": "qa-horse", "TreasureModelId": 14021014, "Step": 0, "Lv": 0}
        profile.state["treasures"].append(treasure)
        self.assertEqual(self.prop()["ActivePrIds"], [])
        args = [sword["Id"], helmet["Id"], "", "", "", treasure["Id"]]
        equip = self.rpc("Slot", "OneKeyEquipCombat", 1, *args)
        self.assertEqual(equip["Status"], 0)
        after = self.prop()
        self.assertEqual(after["ActivePrIds"], [472, 473, 476])
        self.assertEqual([after[key] for key in ("APR1", "DEFR1", "HPR1")], [12000, 11300, 11700])
        self.assertGreater(after["DEF"], prior["DEF"])
        _, art_bonus = profile._compute_equip_artifact_state()
        expected_ally = prior_ally.copy()
        expected_ally["AP"] += art_bonus["AP"]
        expected_ally["AP2"] += art_bonus["AP"]
        expected_ally["HP"] += art_bonus["HP"]
        expected_ally["HP2"] += art_bonus["HP"]
        expected_ally["DEF"] += art_bonus["DEF"]
        expected_ally["DEF2"] += art_bonus["DEF"]
        expected_ally["FAP"] += art_bonus["HP"] + 10 * (art_bonus["AP"] + art_bonus["DEF"])
        self.assertEqual(self.prop(2), expected_ally)
        unequip = self.rpc("Slot", "OneKeyEquipCombat", 1, *([EMPTY_ENTITY_ID] * 6))
        self.assertEqual(unequip["Status"], 0)
        self.assertEqual(self.prop(), prior)
        self.assertEqual(self.prop(2), prior_ally)

    def test_equipped_gear_advances_three_steps_and_refuses_stale_requests(self):
        profile = self.profile
        profile.state["player"].update(Lv=45, Gold=14_000_000)
        item = profile._build_equip_instance(13010701)
        item["Lv"] = 69
        materials = [profile._build_equip_instance(13010701) for _ in range(4)]
        profile.state["equips"].extend([item, *materials])
        self.rpc("Slot", "OneKeyEquipCombat", 1, item["Id"], "", "", "", "", "")
        self.assertEqual(self.rpc("Equip", "EquipStepUp", item["Id"], materials[0]["Id"], 0)["Status"], -1314)
        self.assertEqual(profile.state["player"]["Gold"], 14_000_000)
        steps = profile.game_data["equip_steps"]["13010701"]
        for index, material in enumerate(materials[:3]):
            required_level = steps[str(index)]["needLV"]
            self.assertEqual(self.rpc("Equip", "EquipLvUpForCount", item["Id"], required_level - item["Lv"])["Status"], 0)
            self.assertEqual(item["Lv"], required_level)
            before_ap = self.prop()["AP"]
            before_art_ap = profile._compute_equip_artifact_state()[1]["AP"]
            gold = profile.state["player"]["Gold"]
            result = self.rpc("Equip", "EquipStepUp", item["Id"], material["Id"], index)
            self.assertEqual(result["Status"], 0)
            self.assertEqual(result["Value"]["EquipInfo"]["Step"], index + 1)
            self.assertEqual(result["Avatar"]["SlotInfo"][0]["Weapon"]["Step"], index + 1)
            step_gain = steps[str(index + 1)]["AP"] - steps[str(index)]["AP"]
            art_ap_gain = profile._compute_equip_artifact_state()[1]["AP"] - before_art_ap
            self.assertEqual(self.prop()["AP"], before_ap + step_gain + art_ap_gain)
            gold -= steps[str(index)]["stepUpUseNum"]
            self.assertEqual(profile.state["player"]["Gold"], gold)
            self.assertEqual(self.rpc("Equip", "EquipStepUp", item["Id"], materials[-1]["Id"], index)["Status"], -39)
            self.assertIn(materials[-1], profile.state["equips"])
            self.assertEqual(profile.state["player"]["Gold"], gold)
        self.reload()
        startup = self.rpc("Player", "GetInitData")["Value"]
        self.assertEqual(startup["SlotInfo"][0]["Weapon"]["Step"], 3)
        self.assertEqual(startup["PlayerInfo"]["Gold"], gold)

    def test_sweep_exact_floor_history_and_one_result_per_node(self):
        p = self.profile
        p.state["player"].update(Lv=28, VIPLv=9)
        p.state["bdd"] = {"max_stars": 54, "three_star_floors": [12], "run": 1}
        info = lambda: self.rpc("BddInfo", "Info", 1, 1, 1, 1)["Value"]["Info"]
        self.assertFalse(info()["CanSweep"])
        self.assertEqual(self.rpc("BddInfo", "OneKeyThreeStar")["Status"], -1717)
        p.state["bdd"]["three_star_floors"].insert(0, 11)
        self.assertTrue(info()["CanSweep"])
        fight = self.rpc("BddInfo", "GetFightInfo", 1111, 1)["Value"]
        result = self.rpc("BddInfo", "OneKeyThreeStar")
        self.assertEqual(result["Status"], 0)
        result = result["Value"]
        self.assertEqual(result["SweepStarCount"], 9)
        self.assertEqual(len(result["BaseGetGameResourceList"]), 3)
        self.assertEqual((result["Info"]["StarCount"], result["Info"]["MaxStarCount"]), (9, 54))
        self.assertFalse(result["Info"]["CanSweep"])
        self.assertEqual(self.rpc("BddInfo", "Fight", 1111, 1, False, "", {}, fight["FightToken"])["Status"], -39)
        self.assertEqual(self.rpc("BddInfo", "OneKeyThreeStar")["Status"], -1716)
        self.reload()
        self.assertEqual((info()["StarCount"], info()["MaxStarCount"]), (9, 54))
        self.assertTrue(info()["NeedSelectBuff"])
