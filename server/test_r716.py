"""Regression coverage for Tầm Ngọc, VN talent data and campaign initiative."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from combat_sim import simulate_fight_info
from emulator import GameEmulatorState


class R716DeltaTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.now = 1795212300
        self.reload()
        exp = self.profile.game_data["player_lv"]["70"]["EXPTotal"]
        self.profile.state["player"].update(Lv=70, EXP=exp, StarId=160, Vip=3, VIPLv=3,
                                            Diamond=500, Gold=1_000_000, VIT=200, IsNewPlayer=0)
        self.profile.state["explore"].update(MaxNum=41, RemainNum=1, RecoverTime=self.now + 900)
        self.profile.state["explore"].pop("Day", None)
        self.profile.save()

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(self.now)
        self.profile = self.emu.profiles["normal"]

    def rpc(self, module, method, *args):
        return self.emu.handle_rpc({"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(args)})

    def explore(self, method="GetInfo", *args):
        return self.rpc("Explore", method, *args)

    def test_explore_1_of_41_exact_recovery_boundary_and_save_reload(self):
        info = self.explore()
        self.assertEqual((info["Value"]["RemainNum"], info["Value"]["MaxNum"]), (1, 41))
        self.assertEqual(info["Avatar"]["XYCurCount"], 1)
        run = self.explore("Explore")
        self.assertEqual((run["Status"], run["Value"]["RemainNum"], run["Avatar"]["XYCurCount"]), (0, 0, 0))
        after_run = copy.deepcopy(self.profile.state["explore"])
        gold = self.profile.state["player"]["Gold"]
        self.assertEqual(self.explore("Explore")["Status"], -5101)
        self.assertEqual(self.explore("OneKeyExplore")["Status"], -5101)
        self.assertEqual(self.profile.state["explore"], after_run)
        self.assertEqual(self.profile.state["player"]["Gold"], gold)
        self.emu.clock.set_fixed(self.now + 899)
        self.assertEqual(self.explore()["Value"]["RemainNum"], 0)
        self.emu.clock.set_fixed(self.now + 900)
        exact = self.explore()["Value"]
        self.assertEqual((exact["RemainNum"], exact["RecoverTime"]), (1, self.now + 1800))
        self.assertEqual(self.explore()["Value"], exact)
        self.now += 901
        self.reload()
        self.assertEqual(self.explore()["Value"], exact)
        self.assertEqual(self.explore("Explore")["Value"]["DailyNum"], 2)
        self.assertEqual(self.explore("Explore")["Status"], -5101)

    def test_explore_catchup_buy_and_daily_rewards_are_period_scoped(self):
        state = self.profile.state
        self.assertEqual(self.explore("BuyExploreNum")["Status"], -5103)
        self.assertEqual(state["player"]["Diamond"], 500)
        self.assertEqual(self.explore("DrawDailyReward", 50)["Status"], -5104)
        self.assertEqual(self.explore("DrawDailyReward", "50")["Status"], -48)
        state["explore"].update(RemainNum=0, DailyNum=49)
        bought = self.explore("BuyExploreNum")
        self.assertEqual((bought["Status"], bought["Value"]["RemainNum"], bought["Value"]["ResetNum"]), (0, 10, 1))
        self.assertEqual(state["player"]["Diamond"], 450)
        self.assertEqual(state["stats"]["spent_diamonds"], 50)
        used = self.explore("OneKeyExplore")
        self.assertEqual((used["Status"], used["Value"]["RemainNum"], used["Value"]["DailyNum"]), (0, 0, 59))
        first = self.explore("DrawDailyReward", 50)
        self.assertEqual(first["Status"], 0)
        self.assertEqual(self.explore("DrawDailyReward", 50)["Status"], -7003)
        after_chest = state["player"]["Diamond"]
        self.assertEqual(self.explore("BuyExploreNum")["Value"]["ResetNum"], 2)
        self.assertEqual(state["player"]["Diamond"], after_chest - 100)
        self.now = self.emu.clock.next_midnight_ts() + 86400
        self.emu.clock.set_fixed(self.now)
        current = self.explore()["Value"]
        self.assertEqual((current["RemainNum"], current["RecoverTime"]), (41, 0))
        self.assertEqual((current["DailyNum"], current["DrawnNums"], current["ResetNum"]), (0, "", 0))
        self.assertEqual(self.explore("Explore")["Value"]["RecoverTime"], self.now + 900)
        state["explore"]["DailyNum"] = 50
        self.assertEqual(self.explore("DrawDailyReward", 50)["Status"], 0)
        self.reload()
        self.assertEqual(self.explore("DrawDailyReward", 50)["Status"], -7003)

    def test_explore_save_failure_and_vip_locks_do_not_consume(self):
        state = self.profile.state
        self.explore()
        before = copy.deepcopy(state["explore"])
        gold = state["player"]["Gold"]
        with patch.object(self.profile, "save", side_effect=OSError("disk full")), self.assertLogs(level="ERROR"):
            self.assertEqual(self.explore("Explore")["Status"], -7)
        self.assertEqual(state["player"]["Gold"], gold)
        self.assertEqual(state["explore"], before)
        state["player"].update(Vip=0, VIPLv=0)
        self.assertEqual(self.explore("OneKeyExplore")["Status"], -5004)
        state["explore"]["RemainNum"] = 0
        with patch.object(self.profile, "save", side_effect=OSError("disk full")), self.assertLogs(level="ERROR"):
            self.assertEqual(self.explore("BuyExploreNum")["Status"], -7)
        self.assertEqual((state["player"]["Diamond"], state["explore"]["ResetNum"]), (500, 0))
        state["player"]["Diamond"] = 49
        self.assertEqual(self.explore("BuyExploreNum")["Status"], -1105)
        state["explore"]["ResetNum"] = 1
        self.assertEqual(self.explore("BuyExploreNum")["Status"], -5102)

    def test_insight_capacity_and_level_reward_are_capped(self):
        p = self.profile
        p.state["player"].update(StarId=159, Lv=69, Gold=10_000_000)
        p.state["battle"]["StarCount"] = 5000
        p.state["explore"].update(RemainNum=39, MaxNum=40, RecoverTime=self.now + 700)
        self.assertEqual(self.rpc("LightenStar", "LightenStar")["Status"], 0)
        self.assertEqual(self.explore()["Value"]["MaxNum"], 41)
        self.assertEqual(self.explore()["Value"]["RemainNum"], 40)
        p.state["player"]["EXP"] = p.game_data["player_lv"]["70"]["EXPTotal"]
        self.assertEqual(p._sync_level_from_exp(), (69, 70))
        self.assertEqual((self.explore()["Value"]["RemainNum"], self.explore()["Value"]["RecoverTime"]), (41, 0))

    def place(self, model, step, slot_id):
        p = self.profile
        hero = p._build_hero_instance(model, lv=55, step=step)
        p.state["heroes"].append(hero)
        p.state["slots"][slot_id - 1].update(HeroId=hero["Id"], HeroModelId=model)
        p.state["embattle"][f"Formation{slot_id}"] = slot_id
        p._recalc_all_slots_and_fap()
        return hero

    def fight(self, chapter=11, node=1115, stars=1):
        msg = self.rpc("Battle", "GetFightInfo", chapter, node, stars)
        self.assertEqual(msg["Status"], 0)
        return msg["Value"]["FightInfo"]

    def test_talents_add_base_rage_and_flat_bonuses_once_in_fight_info(self):
        p = self.profile
        main = self.place(12010001, 2, 1)
        inu = self.place(12011004, 5, 2)
        before = self.fight()["FightObjs"][0]["Heros"]
        self.assertEqual([before[0]["RP"], before[1]["RP"]], [50, 50])
        self.assertEqual(before[1]["BuffList"], "10350000")
        main["Step"], inu["Step"] = 3, 6
        p._recalc_all_slots_and_fap()
        after = self.fight()["FightObjs"][0]["Heros"]
        self.assertEqual([after[0]["RP"], after[1]["RP"]], [100, 100])
        self.assertEqual(after[1]["RAId"], p.game_data["heroes"]["12011004"]["RAID"])
        self.assertEqual(after[1]["CRI"], p.game_data["heroes"]["12011004"]["CRI"] + 1000)
        self.assertEqual(after[1]["BuffList"], "10350000")

        main["Step"] = 4
        p._recalc_all_slots_and_fap()
        self.assertEqual(self.fight()["FightObjs"][0]["Heros"][1]["HP"], after[1]["HP"] + 500)
        main["Step"] = 8
        p._recalc_all_slots_and_fap()
        p.save()
        # Reload cannot compound the already-derived properties.
        expected = [(x["HP"], x["AP"], x["RP"]) for x in self.fight()["FightObjs"][0]["Heros"][:2]]
        self.reload()
        self.assertEqual([(x["HP"], x["AP"], x["RP"]) for x in self.fight()["FightObjs"][0]["Heros"][:2]], expected)

    def test_crit_rage_passive_and_opening_rage_act_in_combat(self):
        p = self.profile
        unit = self.place(12011004, 6, 1)
        battle = self.fight()
        wave = battle["FightObjs"][0]
        attacker = wave["Heros"][0]
        attacker.update(CRI=10000, FSP=9000, AP=900)
        enemy = {**wave["Heros"][7], "HP": 100000, "TotalHp": 100000, "TEN": 0, "DEF": 0}
        wave["Heros"] = [attacker] + [{}] * 7 + [enemy] + [{}] * 3
        buff_sources = p.game_data["combat_buffs"]
        attacks = p.game_data["attacks"]
        simulate = lambda: simulate_fight_info(battle, attacks, max_rounds=1, buffs_cfg=buff_sources).verify_data["hp"][0]
        with_talent = simulate()
        self.assertEqual(with_talent[0]["RP"], 25)
        attacker["BuffList"] = "10350000,10350000"
        self.assertEqual(simulate(), with_talent)
        attacker["BuffList"] = ""
        self.assertEqual(simulate()[0]["RP"], 0)
        attacker["RP"] = 50
        self.assertGreater(next(x["HP"] for x in simulate() if x["PosId"] == 9), with_talent[1]["HP"])
        self.assertEqual(unit["Step"], 6)

    def test_campaign_sums_initiative_from_emitted_units_without_touching_waves(self):
        p = self.profile
        self.place(12011004, 6, 1)
        for chapter, node, waves in ((11, 1115, 1), (45, 4520, 2), (80, 8020, 2)):
            with self.subTest(chapter=chapter):
                p.state["player"]["Lv"] = p.game_data["chapters"][str(chapter)]["needLV"]
                stages = self.fight(chapter, node, 3)["FightObjs"]
                self.assertEqual(len(stages), waves)
                self.assertEqual(stages[-1]["Heros"][7]["HeroModelId"], int(p.game_data["nodes"][str(node)]["pic"]))
                for wave in stages:
                    for idx, team in enumerate(wave["TeamData"]):
                        self.assertEqual(team["Fsp"], sum(x.get("FSP", 0) for x in wave["Heros"][idx*6:idx*6+6]))
