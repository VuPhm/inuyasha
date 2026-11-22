"""R7.22A (TASK-M01) tests: EquipGroup 13 attrs, TreasureStep 410/411, HeroStepCheer, FashionPrRelation, DailyTask #12/#26."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from emulator import GameEmulatorState


class R722AStatsAndDailyTaskTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.now = 1795262400  # 2026-11-21 12:00:00 UTC
        self.reload()
        self.p.state["player"].update(Lv=100, Vip=9, VIPLv=9, IsNewPlayer=0, VIT=500, Diamond=50000, Gold=5000000)

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(self.now)
        self.p = self.emu.profiles["normal"]

    def rpc(self, module, method, *args):
        return self.emu.handle_rpc({"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(args)})

    def test_equip_group_all_stats_and_fight_info(self):
        slot = self.p.state["slots"][0]
        self.p._recalc_all_slots_and_fap()
        base_prop = dict(slot["Property"])
        hero = next(h for h in self.p.state["heroes"] if h["Id"] == slot["HeroId"])
        hero_ap, hero_hp, hero_def = hero["AP"], hero["HP"], hero["DEF"]

        # Equip 4-piece group 5 (13010705..13040705): has APR/HPR/DEFR=800, BLO=2000, TEND=3000 at 4pc
        # plus flat HP/AP/DEF at 2pc & 3pc.
        for key, mid in zip(("Weapon", "Helmet", "Clothes", "Necklace"), (13010705, 13020705, 13030705, 13040705)):
            eq = self.p._build_equip_instance(mid)
            self.p.state["equips"].append(eq)
            slot[key] = eq
        self.p._recalc_all_slots_and_fap()
        prop = slot["Property"]

        tiers = self.p.game_data["equip_group"]["5"]
        exp_apr = sum(int(t.get("APR", 0)) for req, t in tiers.items() if 4 >= int(req))
        exp_hpr = sum(int(t.get("HPR", 0)) for req, t in tiers.items() if 4 >= int(req))
        exp_defr = sum(int(t.get("DEFR", 0)) for req, t in tiers.items() if 4 >= int(req))
        exp_blo = sum(int(t.get("BLO", 0)) for req, t in tiers.items() if 4 >= int(req))
        exp_tend = sum(int(t.get("TEND", 0)) for req, t in tiers.items() if 4 >= int(req))

        self.assertGreater(exp_apr, 0)
        self.assertEqual(prop["APR1"], base_prop["APR1"] + exp_apr)
        self.assertEqual(prop["HPR1"], base_prop["HPR1"] + exp_hpr)
        self.assertEqual(prop["DEFR1"], base_prop["DEFR1"] + exp_defr)
        self.assertEqual(prop["BLO"], base_prop["BLO"] + exp_blo)
        self.assertEqual(prop["TEND"], base_prop["TEND"] + exp_tend)
        self.assertEqual(prop["AP"], hero_ap * prop["APR1"] // 10000 + prop["AP2"])

        allies = self.p._build_ally_fight_objs()
        self.assertEqual(allies[0]["BLO"], prop["BLO"])
        self.assertEqual(allies[0]["TEND"], prop["TEND"])
        self.assertEqual(allies[0]["AP"], prop["AP"])

        # Also verify CRI/HIT/DOD/TEN/BOG/CRId/DAMADD/DAMCUT propagation using a synthetic equip_group entry
        # or any existing group that grants CRI/DAMADD/etc.
        gid_cri = next(
            gid for gid, ts in self.p.game_data["equip_group"].items()
            if any(t.get("CRI", 0) or t.get("DAMADD", 0) or t.get("HIT", 0) or t.get("CRID", 0) for t in ts.values())
        )
        eqs_cri = [e["ID"] for e in self.p.game_data["equips"].values() if e.get("equipGroupID") == int(gid_cri)]
        for key, mid in zip(("Weapon", "Helmet", "Clothes", "Necklace"), eqs_cri[:4]):
            eq = self.p._build_equip_instance(mid)
            self.p.state["equips"].append(eq)
            slot[key] = eq
        self.p._recalc_all_slots_and_fap()
        prop2 = slot["Property"]
        t4 = self.p.game_data["equip_group"][gid_cri]
        for cfg_k, prop_k in (
            ("HIT", "HIT"), ("DOD", "DOD"), ("CRI", "CRI"), ("TEN", "TEN"),
            ("BOG", "BOG"), ("CRID", "CRId"), ("DAMADD", "DAMADD"), ("DAMCUT", "DAMCUT"),
        ):
            expected_delta = sum(int(t.get(cfg_k, 0)) for req, t in t4.items() if len(eqs_cri[:4]) >= int(req))
            self.assertEqual(prop2[prop_k], base_prop[prop_k] + expected_delta, f"Mismatch for {cfg_k}")

    def test_treasure_step_410_411_damaddr_damcutr(self):
        slot = self.p.state["slots"][0]
        self.p._recalc_all_slots_and_fap()
        base_damaddr = slot["Property"]["DAMADDR"]
        base_damcutr = slot["Property"]["DAMCUTR"]

        self.p._grant_resources_from_tuples([(1401, 14011615, 1), (1402, 14021615, 1)], "test", "tr_step_test")
        book, horse = self.p.state["treasures"][-2], self.p.state["treasures"][-1]
        book["Step"] = 2
        horse["Step"] = 2
        slot["Book"] = book
        slot["Horse"] = horse
        self.p._recalc_all_slots_and_fap()

        prop = slot["Property"]
        self.assertGreater(prop["DAMADDR"], base_damaddr)
        self.assertGreater(prop["DAMCUTR"], base_damcutr)
        allies = self.p._build_ally_fight_objs()
        self.assertEqual(allies[0]["DAMADDR"], prop["DAMADDR"])
        self.assertEqual(allies[0]["DAMCUTR"], prop["DAMCUTR"])

    def test_hero_step_cheer_orange_partner_only(self):
        # Unlock first mate slot
        need_star = int(self.p.game_data["attrtree_slots"]["21"]["needAttrTreeID"])
        self.p.state["player"]["StarId"] = max(need_star, 1)
        self.p._recalc_all_slots_and_fap()
        base_hp = self.p.state["slots"][0]["Property"]["HP"]
        base_ap = self.p.state["slots"][0]["Property"]["AP"]
        base_def = self.p.state["slots"][0]["Property"]["DEF"]

        # Find a low-quality (<13) hero and an orange+ (>=13) hero
        low_q_id = next(int(k) for k, v in self.p.game_data["heroes"].items() if int(v.get("quality", 0)) < 13)
        high_q_id = next(int(k) for k, v in self.p.game_data["heroes"].items() if int(v.get("quality", 0)) >= 13)

        low_hero = self.p._build_hero_instance(low_q_id, lv=10, step=5)
        high_hero = self.p._build_hero_instance(high_q_id, lv=10, step=5)
        self.p.state["heroes"].extend([low_hero, high_hero])

        # Deploy low quality hero -> should NOT activate HeroStepCheer
        res_low = self.rpc("Slot", "MateinfoCombat", 1, low_hero["Id"])
        self.assertEqual(res_low["Status"], 0)
        self.assertEqual(self.p.state["slots"][0]["Property"]["HP"], base_hp)

        # Deploy orange+ hero with Step=5 -> activates HeroStepCheer[5]
        res_high = self.rpc("Slot", "MateinfoCombat", 1, high_hero["Id"])
        self.assertEqual(res_high["Status"], 0)
        cheer5 = self.p.game_data["hero_step_cheer"]["5"]
        self.assertEqual(self.p.state["slots"][0]["Property"]["HP"], base_hp + int(cheer5["HPADD"]))
        self.assertEqual(self.p.state["slots"][0]["Property"]["AP"], base_ap + int(cheer5["APADD"]))
        self.assertEqual(self.p.state["slots"][0]["Property"]["DEF"], base_def + int(cheer5["DEFADD"]))

        # Persist across reload
        self.p.save()
        self.reload()
        self.assertEqual(self.p.state["slots"][0]["Property"]["HP"], base_hp + int(cheer5["HPADD"]))

    def test_fashion_pr_relation_rows_and_formation_swap(self):
        # Put a second hero in slot 4 (back row)
        h4 = self.p._build_hero_instance(12011002, lv=10, step=0)
        self.p.state["heroes"].append(h4)
        self.p.state["slots"][3].update(HeroId=h4["Id"], HeroModelId=12011002)
        self.p._recalc_all_slots_and_fap()

        s1_hp_before = self.p.state["slots"][0]["Property"]["HP"]
        s1_ap_before = self.p.state["slots"][0]["Property"]["AP"]
        s4_hp_before = self.p.state["slots"][3]["Property"]["HP"]
        s4_ap_before = self.p.state["slots"][3]["Property"]["AP"]

        # Own 1/2 of FashionPr #1 -> no Pr bonus yet (only FashionStepRelation if any)
        self.p._grant_resources_from_tuples([(1901, 19010001, 1)], "test", "fash_1")
        self.p._recalc_all_slots_and_fap()
        s1_hp_one = self.p.state["slots"][0]["Property"]["HP"]
        s1_ap_one = self.p.state["slots"][0]["Property"]["AP"]
        s4_hp_one = self.p.state["slots"][3]["Property"]["HP"]
        s4_ap_one = self.p.state["slots"][3]["Property"]["AP"]

        # Own 2/2 of FashionPr #1 (19010001, 19010002): "6||432|2000,7||431|300"
        self.p._grant_resources_from_tuples([(1901, 19010002, 1)], "test", "fash_2")
        self.p._recalc_all_slots_and_fap()
        # Account for FashionStepRelation delta from 19010002 (target 2 all allies)
        f2_step0 = self.p.game_data["fashion_step"].get("19010002", {}).get("0", {})
        f2_all_ap = 0
        f2_all_hp = 0
        for part in str(f2_step0.get("heroAttrStrR", "")).split("||"):
            segs = [x.strip() for x in part.split(",") if x.strip()]
            if len(segs) == 3 and int(segs[0]) == 2:
                if int(segs[1]) == 431:
                    f2_all_ap += int(segs[2])
                elif int(segs[1]) == 432:
                    f2_all_hp += int(segs[2])

        self.assertEqual(self.p.state["slots"][0]["Property"]["HP"], s1_hp_one + f2_all_hp + 2000)
        self.assertEqual(self.p.state["slots"][0]["Property"]["AP"], s1_ap_one + f2_all_ap)
        self.assertEqual(self.p.state["slots"][3]["Property"]["HP"], s4_hp_one + f2_all_hp)
        self.assertEqual(self.p.state["slots"][3]["Property"]["AP"], s4_ap_one + f2_all_ap + 300)

        # Swap Formation1 and Formation4 -> slot 4 becomes front row (+2000 HP), slot 1 becomes back row (+300 AP)
        res = self.rpc("SlotFormation", "Change", 4, 2, 3, 1, 5, 6)
        self.assertEqual(res["Status"], 0)
        self.assertEqual(self.p.state["slots"][0]["Property"]["HP"], s1_hp_one + f2_all_hp)
        self.assertEqual(self.p.state["slots"][0]["Property"]["AP"], s1_ap_one + f2_all_ap + 300)
        self.assertEqual(self.p.state["slots"][3]["Property"]["HP"], s4_hp_one + f2_all_hp + 2000)
        self.assertEqual(self.p.state["slots"][3]["Property"]["AP"], s4_ap_one + f2_all_ap)

        self.reload()
        self.assertEqual(self.p.state["slots"][0]["Property"]["AP"], s1_ap_one + f2_all_ap + 300)

    def test_daily_task_12_glory_and_26_trader(self):
        # Task #12: Glory.GloryLvUp & GloryLvUpForOneKey
        self.p._grant_resources_from_tuples([(1604, 16040001, 4)], "test", "glory_dip")
        res1 = self.rpc("Glory", "GloryLvUp", 1, 16040001, "")
        self.assertEqual(res1["Status"], 0)
        info1 = self.rpc("DailyTaskInfo", "GetDaliyTaskInfo")
        t12 = next(t for t in info1["Value"]["TasksInfo"] if t["Id"] == 12)
        self.assertEqual(t12["Num"], 1)

        res_ok = self.rpc("Glory", "GloryLvUpForOneKey", 1)
        self.assertEqual(res_ok["Status"], 0)
        info2 = self.rpc("DailyTaskInfo", "GetDaliyTaskInfo")
        t12_2 = next(t for t in info2["Value"]["TasksInfo"] if t["Id"] == 12)
        self.assertEqual(t12_2["Num"], 1)
        self.assertTrue(t12_2["CanDrawCredit"])

        claim12 = self.rpc("DailyTaskInfo", "GetCredit", 12)
        self.assertEqual(claim12["Status"], 0)

        # Task #26: TraderInfo.BuyGoods
        tr_info = self.rpc("TraderInfo", "GetInfo")
        self.assertEqual(tr_info["Status"], 0)
        first_id = tr_info["Value"]["TraderGoodsList"][0]["Id"]
        buy_res = self.rpc("TraderInfo", "BuyGoods", first_id)
        self.assertEqual(buy_res["Status"], 0)
        info3 = self.rpc("DailyTaskInfo", "GetDaliyTaskInfo")
        t26 = next(t for t in info3["Value"]["TasksInfo"] if t["Id"] == 26)
        self.assertEqual(t26["Num"], 1)
        claim26 = self.rpc("DailyTaskInfo", "GetCredit", 26)
        self.assertEqual(claim26["Status"], 0)


if __name__ == "__main__":
    unittest.main()
