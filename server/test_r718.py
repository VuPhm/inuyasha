"""Delta for the new BDD floors, saved runs and stock combat mechanisms."""

from collections import Counter, defaultdict
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from bdd_handlers import bdd_recommended_fap
from combat_effects import BattleEffects, supports_talent_buff
from combat_sim import simulate_fight_info
from emulator import GameEmulatorState
from test_r717 import game, unit, wave


class R718BddTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.reload()
        self.profile.state["player"].update(Lv=80, Vip=9, VIPLv=9, IsNewPlayer=0)

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(1795176000)
        self.profile = self.emu.profiles["normal"]

    def call(self, module, method, *args):
        return self.emu.handle_rpc({"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(args)})

    def bdd(self, method="Info", *args):
        return self.call("BddInfo", method, *args)

    def equip_test_team(self):
        p = self.profile
        p.state["player"]["StarId"] = 160
        for index, model in enumerate((12011002, 12011004, 12012004, 12012005, 12013003, 12013005), 1):
            hero = p._build_hero_instance(model, lv=80, step=15)
            p.state["heroes"].append(hero)
            slot = p.state["slots"][index - 1]
            slot.update(HeroId=hero["Id"], HeroModelId=model)
            for equip_type, key in p.EQUIP_TYPE_TO_SLOT_KEY.items():
                item = p._build_equip_instance(equip_type * 10000 + 701)
                item.update(Lv=160, Step=10)
                p.state["equips"].append(item)
                slot[key] = item
            for kind, key, model_id in ((1401, "Book", 14011615), (1402, "Horse", 14021615)):
                p._grant_resources_from_tuples([(kind, model_id, 1)], "fixture", f"treasure:{index}:{kind}")
                item = p.state["treasures"][-1]
                item.update(Lv=100, Step=10)
                slot[key] = item
        p._recalc_all_slots_and_fap()
        p.save()

    def test_original_832_terminal_save_offers_buff_once_without_reawarding_floor_16(self):
        state = self.profile.state
        keys = [str(100 * f + n) for f in range(11, 17) for n in (11, 12, 13)]
        state["bdd"] = {"stars": dict.fromkeys(keys, 3), "best": dict.fromkeys(keys, 3), "max_stars": 54,
                        "last_buff_floor": 15, "three_star_floors": list(range(11, 17))}
        state["player"]["Merit"] = 1234
        self.profile.save()
        self.reload()
        value = self.bdd()["Value"]
        self.assertEqual((value["PlayableCount"], value["Info"]["ClearedCount"]), (51, 18))
        self.assertTrue(value["Info"]["NeedSelectBuff"])
        self.assertFalse(value["Info"]["NeedReset"])
        self.assertEqual(value["Info"]["BeforeFloorStarCount"], 9)
        self.assertEqual(self.bdd("RewardBox", 16, 9)["Status"], -39)
        self.assertEqual(self.bdd("GetFightInfo", 1711, 1)["Status"], -1716)
        offer = self.bdd("GetBuffs")["Value"][0]
        self.assertEqual(self.bdd("SelectBuff", offer["Id"])["Status"], 0)
        self.reload()
        info = self.bdd()["Value"]["Info"]
        self.assertFalse(info["NeedSelectBuff"])
        self.assertEqual((info["StarCount"], info["Feats"], info["CanUseStarCount"]), (54, 1234, 51))
        self.assertEqual(self.bdd("SelectBuff", offer["Id"])["Status"], -39)
        self.assertEqual(self.bdd("GetFightInfo", 1711, 1)["Status"], 0)
        self.assertEqual(self.bdd("GetFightInfo", 2411, 1)["Status"], -1716)

    def test_new_npc_samples_retain_all_63_vn_difficulty_rows_and_rewards(self):
        cfg = self.profile.game_data["bdd"]
        nodes = [row for row in cfg["nodes"].values() if 17 <= row["floorModelID"] <= 23]
        self.assertEqual(len(nodes), 21)
        for row in nodes:
            node = row["ID"]
            figures = []
            for mode in (1, 2, 3):
                fight = self.profile._bdd_encounter(node, mode, "ab124709")["FightObjs"][0]
                point = cfg["points"][str(node * 100 + 10 + mode)]
                figures.append(bdd_recommended_fap(point["proposeFAP"]))
                self.assertLessEqual(abs(fight["TeamData"][1]["Fap"] - figures[-1]), 25)
                self.assertEqual(fight["Heros"][7]["HeroModelId"], int(row["pic"]))
                self.assertEqual(point["nationalDrop"], f"1124,0,{10 * mode}")
                self.assertEqual(bool(point["firstPassDrop"]), mode == 3)
            self.assertLess(figures[0], figures[1])
            self.assertLess(figures[1], figures[2])

    @patch("bdd_handlers.PLAYABLE_FLOORS", range(11, 24))
    def test_39_stages_have_a_playable_route_and_preserve_shop_quests_and_sweep(self):
        self.equip_test_team()
        cfg = self.profile.game_data["bdd"]
        rng = random.Random(718)
        tokens = patch("bdd_handlers.uuid", SimpleNamespace(uuid4=lambda: uuid.UUID(int=rng.getrandbits(128))))
        tokens.start()
        self.addCleanup(tokens.stop)
        self.assertEqual(self.bdd("BuyShop", 25)["Status"], -1602)
        for floor in range(11, 24):
            difficulty = 3 if floor <= 19 else 1
            for number in (11, 12, 13):
                node = floor * 100 + number
                before = self.profile.state["player"].get("Merit", 0)
                for _ in range(4):
                    pending = self.bdd("GetFightInfo", node, difficulty)["Value"]
                    if node == 1711:
                        self.reload()
                        self.assertEqual(self.bdd("GetFightInfo", node, difficulty)["Value"], pending)
                    token = pending["FightToken"]
                    result = self.bdd("Fight", node, difficulty, True, "", {}, token)["Value"]
                    self.assertEqual(self.bdd("Fight", node, difficulty, True, "", {}, token)["Status"], -39)
                    if result["IsSuccess"]:
                        break
                    self.assertEqual(self.profile.state["player"].get("Merit", 0), before)
                self.assertTrue(result["IsSuccess"], (node, result))
                self.assertEqual(result["StarCount"], difficulty)
            info = self.bdd()["Value"]["Info"]
            self.assertEqual(info["RewardFloor"], floor)
            self.assertFalse(info["NeedReset"])
            self.assertEqual(self.bdd("RewardBox", floor, difficulty * 3)["Status"], 0)
            self.assertEqual(self.bdd("RewardBox", floor, difficulty * 3)["Status"], -39)
            if floor < 23:
                info = self.bdd()["Value"]["Info"]
                offers = [offer for offer in self.bdd("GetBuffs")["Value"]
                          if offer["NeedStars"] <= info["CanUseStarCount"]]
                def benefit(offer):
                    row = cfg["buffs"][str(offer["Id"])]
                    return row["fightattrID"] in (401, 402, 410, 411), row["addValue"]
                selected = max(offers, key=benefit)
                self.assertEqual(self.bdd("SelectBuff", selected["Id"])["Status"], 0)
        self.reload()
        info = self.bdd()["Value"]["Info"]
        self.assertEqual((info["ClearedCount"], info["StarCount"], info["MaxStarCount"]), (39, 93, 93))
        self.assertTrue(info["NeedReset"])
        self.assertEqual(self.bdd("Ranking")["Value"][0]["WeekStarCount"], 93)
        self.assertEqual(self.bdd("BuyShop", 25)["Status"], 0)
        self.assertEqual(self.bdd("BuyShop", 25)["Status"], -2104)
        tasks = self.call("DailyTaskInfo", "GetDaliyTaskInfo")["Value"]["TasksInfo"]
        self.assertEqual(next(row["Num"] for row in tasks if row["Id"] == 21), 1)
        self.assertEqual(self.bdd("Reset")["Status"], 0)
        result = self.bdd("OneKeyThreeStar")["Value"]
        self.assertEqual((result["SweepStarCount"], result["Info"]["ClearedCount"]), (9, 3))
        self.assertEqual(result["Info"]["MaxStarCount"], 93)
        self.assertTrue(result["Info"]["NeedSelectBuff"])
        self.assertEqual(self.bdd("OneKeyThreeStar")["Status"], -1716)


class R718CombatTest(unittest.TestCase):
    def test_manten_pays_hp_once_and_boosts_rage_damage(self):
        cfg = game()
        enemy = unit(12011005)
        enemy.update(NAId=0, RAId=0)
        fighter = unit(12012014, rp=100)

        def simulate(attacker, buffs):
            outcome = simulate_fight_info({"FightObjs": [wave(attacker, enemy)]}, cfg["attacks"],
                                          max_rounds=1, buffs_cfg=buffs)
            return {row["PosId"]: row for row in outcome.verify_data["hp"][0]}

        result = simulate(fighter, cfg["combat_buffs"])
        baseline = simulate(fighter, {})
        self.assertEqual(result[1]["HP"], 90000)
        self.assertLess(result[9]["HP"], baseline[9]["HP"])
        self.assertEqual(simulate(dict(fighter, HP=5), cfg["combat_buffs"])[1]["HP"], 1)
        self.assertEqual(simulate(dict(fighter, RP=50), cfg["combat_buffs"])[1]["HP"], 100000)

    def test_cleanse_clears_only_vn_debuff_flags(self):
        attacks, buffs = game()["attacks"], game()["combat_buffs"]
        units = {1: unit(12013006), 2: unit(12011004), 9: unit(12012014)}
        effects = BattleEffects(units, attacks, buffs, random.Random(4))
        for bid in ("12130400", "14010000"):
            row = buffs[bid]
            effects._add(2, row, row["triggerCondition1"], 9)
        effects.apply(1, 1, 2, [2], (3,), (5,), defaultdict(Counter), target_only=True)
        self.assertEqual({e.row["ID"] for e in effects.active[2]}, {20390600, 14010000})

    def test_rage_talent_targets_living_lowest_ally_and_uses_stock_odds(self):
        attacks, buffs = game()["attacks"], game()["combat_buffs"]
        sources = (12011020, 12013018)
        for model in sources:
            units = {1: unit(model, buffs="10530600"), 2: unit(12011004, rp=90),
                     3: unit(12012004, rp=80), 4: unit(12012005, hp=0), 9: unit(12012014)}
            effects = BattleEffects(units, attacks, buffs, SimpleNamespace(randrange=lambda _: 4500))
            self.assertTrue(supports_talent_buff(buffs["10530600"], buffs))
            effects.apply(1, 1, None, [9], (2,), (5,), defaultdict(Counter), target_only=False)
            self.assertEqual(units[3]["RP"], 80)
            effects.rng = SimpleNamespace(randrange=lambda _: 4499)
            effects.apply(1, 1, None, [9], (2,), (5,), defaultdict(Counter), target_only=False)
            self.assertEqual([units[i]["RP"] for i in (1, 2, 3, 4)], [0, 90, 105, 0])
