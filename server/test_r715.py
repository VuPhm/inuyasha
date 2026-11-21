"""Test the Delta for VN equipment progression and 18 playable BDD nodes."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bdd_handlers import bdd_recommended_fap
from emulator import EMPTY_ENTITY_ID, GameEmulatorState


class R715DeltaTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.now = 1795176000
        self.reload()
        self.profile.state["player"].update(Lv=80, IsNewPlayer=0)
        self.profile.save()

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(self.now)
        self.profile = self.emu.profiles["normal"]

    def rpc(self, module, method, *data):
        return self.emu.handle_rpc({"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(data)})

    def bdd(self, method="Info", *data):
        return self.rpc("BddInfo", method, *data)

    def equip(self, method, *data):
        return self.rpc("Equip", method, *data)

    def grant_fixture(self, *models):
        p = self.profile
        first = len(p.state["equips"])
        resources = [(p.game_data["equips"][str(model)]["typeID"], model, 1) for model in models]
        p._grant_resources_from_tuples(resources, "test_fixture", "equip_samples")
        return p.state["equips"][first:]

    def wear_weapon(self, equip_id, slot=1):
        return self.rpc("Slot", "OneKeyEquipCombat", slot, equip_id, "", "", "", "", "")

    def test_gold_models_fit_their_slots_and_feed_fight_info(self):
        p = self.profile
        gold = [row for row in p.game_data["equips"].values() if row["colorLV"] == 8]
        self.assertEqual(len(gold), 20)
        items = self.grant_fixture(*(row["ID"] for row in gold))
        for model, equip in zip(gold, items):
            with self.subTest(model=model["ID"]):
                slots = [""] * 6
                slots[model["typeID"] - 1301] = equip["Id"]
                result = self.rpc("Slot", "OneKeyEquipCombat", 1, *slots)
                self.assertEqual(result["Status"], 0)
                slot = result["Value"]["SlotInfo"][0]
                self.assertEqual(slot[p.EQUIP_TYPE_TO_SLOT_KEY[model["typeID"]]]["Id"], equip["Id"])
                self.assertEqual(self.equip("EquipLvUpForCount", equip["Id"], 3)["Status"], -1331)
                self.assertEqual(self.equip("OneKeyEquipLvUp", [equip["Id"]])["Status"], -1331)
                self.assertEqual(equip["Lv"], 0)
        fight = self.bdd("GetFightInfo", 1111, 1)["Value"]["FightInfo"]["FightObjs"][0]["Heros"][0]
        prop = p.state["slots"][0]["Property"]
        self.assertEqual(tuple(fight[key] for key in ("HP", "AP", "DEF")), tuple(prop[key] for key in ("HP", "AP", "DEF")))
        self.reload()
        self.assertEqual(len([e for e in self.profile.state["equips"] if str(e["EquipModelId"]) in
                              {str(row["ID"]) for row in gold}]), 20)

    def test_gold_advance_and_rebirth_use_vn_requirements_and_restore_costs(self):
        p = self.profile
        target, ingredient, wrong_color, wrong_type = self.grant_fixture(13010801, 13010802, 13010705, 13020802)
        player = p.state["player"]
        recipe = p.game_data["equip_steps"]["13010801"]["0"]
        price, need_level = recipe["stepUpUseNum"], recipe["needLV"]
        # Existing-sample levels are seeded because the VN level-up price table stops at red.
        target["Lv"] = need_level - 1
        self.wear_weapon(target["Id"])
        player.update(Gold=price - 1, Diamond=0)
        step = lambda material: self.equip("EquipStepUp", target["Id"], material)["Status"]
        self.assertEqual(step(ingredient["Id"]), -1314)
        target["Lv"] += 1
        self.wear_weapon(ingredient["Id"], slot=2)
        self.assertEqual(step(ingredient["Id"]), -1304)
        self.wear_weapon(EMPTY_ENTITY_ID, slot=2)
        self.assertEqual(step(wrong_color["Id"]), -1315)
        self.assertEqual(step(wrong_type["Id"]), -1326)
        self.assertEqual(step("missing"), -1315)
        ingredient["Step"] = 1
        self.assertEqual(step(ingredient["Id"]), -1324)
        ingredient["Step"] = 0
        self.assertEqual(step(ingredient["Id"]), -1118)
        self.assertEqual(player["Gold"], price - 1)
        self.assertIn(ingredient, p.state["equips"])
        player["Gold"] = price
        self.wear_weapon(target["Id"])
        before_ap = p.state["slots"][0]["Property"]["AP"]
        prior_fap = player["FAP"]
        p.save()
        with patch.object(p, "save", side_effect=OSError("disk full")), self.assertLogs(level="ERROR"):
            self.assertEqual(step(ingredient["Id"]), -7)
        self.assertEqual(p.state["player"]["Gold"], price)
        self.assertIn(ingredient, p.state["equips"])
        self.assertEqual(step(ingredient["Id"]), 0)
        self.assertEqual(step(ingredient["Id"]), -1315)
        prop = p.state["slots"][0]["Property"]
        gain = p.game_data["equip_steps"]["13010801"]["1"]["AP"]
        self.assertEqual(prop["AP"], before_ap + gain)
        self.assertEqual(p.state["player"]["FAP"], prior_fap + gain * 5)
        fight = self.bdd("GetFightInfo", 1111, 1)["Value"]["FightInfo"]["FightObjs"][0]["Heros"][0]
        self.assertEqual(fight["AP"], prop["AP"])
        self.assertEqual(self.equip("EquipRebirth", [target["Id"]])["Status"], -1304)
        self.wear_weapon(EMPTY_ENTITY_ID)
        self.reload()
        p = self.profile
        self.assertEqual(p.state["player"]["Gold"], 0)
        self.assertEqual(self.equip("EquipRebirth", [target["Id"]])["Status"], -1105)
        fee = p.game_data["equip_rebirth"]["40"]["1"]["useDiamond"]
        p.state["player"]["Diamond"] = fee
        result = self.equip("EquipRebirth", [target["Id"]])
        self.assertEqual(result["Status"], 0)
        self.assertEqual((result["Value"]["EquipInfo"]["Step"], result["Value"]["EquipInfo"]["Lv"]), (0, 0))
        self.assertEqual(p.state["player"]["Gold"], price)
        self.assertEqual(p.state["player"]["Diamond"], 0)
        self.assertEqual(sum(item["EquipModelId"] == 13010802 for item in p.state["equips"]), 1)
        self.assertEqual(self.equip("EquipRebirth", [target["Id"]])["Status"], -1308)

    def test_vn_lead_red_exchange_can_use_real_step_ten(self):
        p = self.profile
        target, *materials = self.grant_fixture(13010602, *([13010617] * 10))
        p.state["player"].update(Gold=100_000_000, Merit=7500)
        self.assertEqual(self.bdd("EquipShopExchange", 9, [target["Id"]])["Status"], -1317)
        recipes = p.game_data["equip_steps"]["13010602"]
        for step, material in enumerate(materials):
            target_lv = recipes[str(step)]["needLV"]
            self.assertEqual(self.equip("EquipLvUpForCount", target["Id"], target_lv - target["Lv"])["Status"], 0)
            self.assertEqual(target["Lv"], target_lv)
            self.assertEqual(self.equip("EquipStepUp", target["Id"], material["Id"])["Status"], 0)
        self.assertEqual(target["Step"], 10)
        self.assertEqual(self.equip("EquipStepUp", target["Id"], materials[0]["Id"])["Status"], -1313)
        result = self.bdd("EquipShopExchange", 9, [target["Id"]])
        self.assertEqual(result["Status"], 0)
        self.assertEqual(p.state["player"]["Merit"], 0)
        self.assertEqual(sum(e["EquipModelId"] == 13010701 for e in p.state["equips"]), 1)
        self.assertEqual(self.bdd("EquipShopExchange", 9, [target["Id"]])["Status"], -2104)

    def test_vn_fap_progression_matches_all_54_fights(self):
        cfg = self.profile.game_data["bdd"]
        nodes = [row for row in cfg["nodes"].values() if 11 <= row["floorModelID"] <= 16]
        self.assertEqual(len(nodes), 18)
        prior = [0, 0, 0]
        for row in nodes:
            faps = []
            for difficulty in (1, 2, 3):
                node = row["ID"]
                wave = self.profile._bdd_encounter(node, difficulty, "ab124709")["FightObjs"][0]
                target = bdd_recommended_fap(cfg["points"][str(node * 100 + 10 + difficulty)]["proposeFAP"])
                self.assertEqual(str(wave["Heros"][7]["HeroModelId"]), row["pic"])
                self.assertLessEqual(abs(wave["TeamData"][1]["Fap"] - target), 25)
                self.assertGreater(target, prior[difficulty - 1])
                faps.append(target)
            self.assertLess(faps[0], faps[1])
            self.assertLess(faps[1], faps[2])
            prior = faps
        self.assertEqual(prior, [540000, 640000, 770000])

    def make_playable_team(self):
        p = self.profile
        p.state["player"]["StarId"] = 28
        for slot, mid in enumerate((12011004, 12011005, 12011006, 12011007, 12011012, 12011008), 1):
            hero = p._build_hero_instance(mid, lv=80, step=10)
            p.state["heroes"].append(hero)
            tiles = p.state["slots"][slot - 1]
            tiles.update(HeroId=hero["Id"], HeroModelId=mid)
            for kind, key in p.EQUIP_TYPE_TO_SLOT_KEY.items():
                item = p._build_equip_instance(kind * 10000 + 705)
                item.update(Lv=160, Step=10)
                p.state["equips"].append(item)
                tiles[key] = item
            p.state["embattle"][f"Formation{slot}"] = slot
        p._recalc_all_slots_and_fap()
        p.save()

    @patch("bdd_handlers.PLAYABLE_FLOORS", range(11, 17))
    def test_18_stage_run_rewards_buffs_shop_reset_and_achievements(self):
        p = self.profile
        p.state["success_target"]["start_ts"] = self.now - 6 * 86400
        p.state["chapters"]["11"]["StarCount"] = 99
        targets = lambda: next(row for row in self.rpc("SuccessTargetInfo", "GetInfo")["Value"]["TargetList"]
                               if row["TargetId"] == 18)
        self.assertEqual(targets()["ReachedNum"], 0)
        self.assertEqual(p._opencontest_profile_score_obj(p)["MaxStarCount"], 0)
        self.assertEqual(self.bdd()["Value"]["PlayableCount"], 18)
        self.assertEqual(self.bdd("BuyShop", 9)["Status"], -1602)
        self.make_playable_team()
        for floor in range(11, 17):
            for suffix in (11, 12, 13):
                node = floor * 100 + suffix
                reply = self.bdd("GetFightInfo", node, 3)
                self.assertEqual(reply["Status"], 0, (node, reply["Status"]))
                payload = reply["Value"]
                if node == 1312:
                    self.reload()
                    self.assertEqual(self.bdd("GetFightInfo", node, 3)["Value"], payload)
                win = self.bdd("Fight", node, 3, False, "", {}, payload["FightToken"])
                self.assertTrue(win["Value"]["IsSuccess"], (node, win["Value"]))
                self.assertEqual(self.bdd("Fight", node, 3, True, "", {}, payload["FightToken"])["Status"], -39)
            self.assertEqual(self.bdd("RewardBox", floor, 9)["Status"], 0)
            self.assertEqual(self.bdd("RewardBox", floor, 9)["Status"], -39)
            if floor < 16:
                offers = self.bdd("GetBuffs")["Value"]
                self.assertEqual([item["NeedStars"] for item in offers], [3, 6, 9])
                info = self.bdd("Info")["Value"]["Info"]
                result = self.bdd("SelectBuff", offers[0]["Id"])["Value"]
                self.assertEqual(result["Info"]["CanUseStarCount"], info["CanUseStarCount"] - 3)
                self.assertEqual(self.bdd("SelectBuff", offers[0]["Id"])["Status"], -39)
        result = self.bdd()["Value"]["Info"]
        self.assertEqual((result["StarCount"], result["MaxThreeFloor"]), (54, 16))
        self.assertTrue(result["NeedReset"])
        self.assertEqual(self.bdd("GetFightInfo", 1711, 1)["Status"], -1716)
        self.assertEqual(self.bdd("Ranking")["Value"][0]["WeekStarCount"], 54)
        self.assertEqual(targets()["ReachedNum"], 54)
        self.assertTrue(targets()["Claimable"]["3"])
        self.assertEqual(self.rpc("SuccessTargetInfo", "DrawReward", 18, 3)["Status"], 0)
        self.assertNotEqual(self.rpc("SuccessTargetInfo", "DrawReward", 18, 3)["Status"], 0)
        self.assertEqual(self.bdd("BuyShop", 21)["Status"], -1732)
        self.assertEqual(self.bdd("Reset")["Status"], 0)
        self.assertEqual(self.bdd("BuyShop", 9)["Status"], 0)
        self.assertEqual(self.bdd("BuyShop", 9)["Status"], -2104)
        self.assertEqual(self.bdd("OneKeyThreeStar")["Status"], 0)
        self.reload()
        info = self.bdd()["Value"]["Info"]
        self.assertEqual((info["StarCount"], info["MaxStarCount"]), (9, 54))
        self.assertTrue(info["NeedSelectBuff"])

    def test_827_floor_12_buff_is_recovered_once_and_attempts_follow_period(self):
        p = self.profile
        p.state["bdd"] = {"stars": {str(node): 1 for node in (1111, 1112, 1113, 1211, 1212, 1213)},
                          "max_stars": 6, "used_buff_stars": 3, "buffs": {"401": 500}}
        p.state["stats"]["bdd_Win"] = 99
        p.event_runtime.configure_archive_mode("concurrent", events=["timed_critical_tasks"])
        p.save()
        def critical():
            rows = self.rpc("TimedCriticalInfo", "Info")["Value"]
            return next(row for row in rows if row["TaskType"] == 7)["DoneNum"]

        def daily():
            rows = self.rpc("DailyTaskInfo", "GetDaliyTaskInfo")["Value"]["TasksInfo"]
            return next(row for row in rows if row["Id"] == 21)["Num"]

        self.assertEqual(critical(), 0)
        self.assertEqual(daily(), 0)
        self.assertTrue(self.bdd()["Value"]["Info"]["NeedSelectBuff"])
        self.assertEqual(self.bdd("GetFightInfo", 1311, 1)["Status"], -1716)
        offers = self.bdd("GetBuffs")["Value"]
        self.assertEqual(self.bdd("SelectBuff", offers[1]["Id"])["Status"], -1732)
        self.assertEqual(self.bdd("SelectBuff", offers[0]["Id"])["Status"], 0)
        self.reload()
        self.assertFalse(self.bdd()["Value"]["Info"]["NeedSelectBuff"])
        self.assertEqual(self.bdd("SelectBuff", offers[0]["Id"])["Status"], -39)
        pending = self.bdd("GetFightInfo", 1311, 1)["Value"]
        self.assertEqual(daily(), 0)
        loss = self.bdd("Fight", 1311, 1, True, "", {}, pending["FightToken"])
        self.assertFalse(loss["Value"]["IsSuccess"])
        self.assertEqual(daily(), 1)
        self.assertEqual(critical(), 1)
        self.assertEqual(self.rpc("TimedCriticalInfo", "Reward", 7)["Status"], 0)
        self.assertNotEqual(self.rpc("TimedCriticalInfo", "Reward", 7)["Status"], 0)
        self.now += 86400
        self.reload()
        self.assertEqual(critical(), 0)
        self.assertEqual(daily(), 0)
