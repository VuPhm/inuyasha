"""R7.19 — Banner Recruitment, Reward Delivery & Hero Capacity regression tests."""

from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from emulator import GameEmulatorState


class R719RecruitRewardCapacityTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.reload()
        p = self.profile.state["player"]
        p.update(Lv=80, Vip=11, VIPLv=11, VipLv=11, IsNewPlayer=0, Diamond=500_000, Gold=50_000_000)
        self.profile.save()

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(1795176000)
        self.profile = self.emu.profiles["normal"]

    def call(self, module, method, *args, server_id=1):
        return self.emu.handle_rpc(
            {"ServerId": server_id, "ModuleName": module, "MethodName": method, "Data": list(args)}
        )

    def test_recruit_free_diamond_and_10x_deliver_heroes_and_deduct_cost(self):
        before_heroes = len(self.profile.state["heroes"])
        before_dia = int(self.profile.state["player"]["Diamond"])

        # Free pull on Banner 83
        r_free = self.call("TimedRecruitInfo", "Recruit", 1, 83)
        self.assertEqual(r_free["Status"], 0)
        self.assertEqual(len(r_free["Value"]["BaseGetGameResourceList"][0]["Hero"]), 1)
        self.assertEqual(len(self.profile.state["heroes"]), before_heroes + 1)
        self.assertEqual(int(self.profile.state["player"]["Diamond"]), before_dia)
        self.assertEqual(r_free["Value"]["RecruitInfo"]["MyCredit"], 10)

        # Free pull on cooldown must fail without granting heroes
        r_cd = self.call("TimedRecruitInfo", "Recruit", 1, 83)
        self.assertNotEqual(r_cd["Status"], 0)
        self.assertEqual(len(self.profile.state["heroes"]), before_heroes + 1)

        # Single diamond pull (280 KC)
        r_one = self.call("TimedRecruitInfo", "Recruit", 3, 83)
        self.assertEqual(r_one["Status"], 0)
        self.assertEqual(len(r_one["Value"]["BaseGetGameResourceList"][0]["Hero"]), 1)
        self.assertEqual(int(self.profile.state["player"]["Diamond"]), before_dia - 280)
        self.assertEqual(r_one["Value"]["RecruitInfo"]["MyCredit"], 20)

        # 10x diamond pull (2800 KC)
        r_ten = self.call("TimedRecruitInfo", "Recruit", 30, 83)
        self.assertEqual(r_ten["Status"], 0)
        self.assertEqual(len(r_ten["Value"]["BaseGetGameResourceList"][0]["Hero"]), 10)
        self.assertEqual(int(self.profile.state["player"]["Diamond"]), before_dia - 3080)
        self.assertEqual(r_ten["Value"]["RecruitInfo"]["MyCredit"], 120)
        self.assertEqual(len(self.profile.state["heroes"]), before_heroes + 12)

    def test_10x_bless_ur_and_milestone_chests_work_even_when_hero_bag_full(self):
        # Reach 600 credit and claim all 6 chests to unlock Bless
        for _ in range(6):
            self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 30, 83)["Status"], 0)
        for req_c in (60, 200, 300, 400, 500):
            res = self.call("TimedRecruitInfo", "DrawCreditReward", req_c, 83)
            self.assertEqual(res["Status"], 0)

        # Fill hero bag to 300/300 (excluding deployed + mate heroes)
        deployed = self.profile._deployed_hero_ids()
        unbattle = sum(1 for h in self.profile.state["heroes"] if h["Id"] not in deployed)
        self.profile.state["heroes"].extend(
            self.profile._build_hero_instance(12011014) for _ in range(300 - unbattle)
        )

        # Claiming 600-credit milestone chest still succeeds when hero bag is full
        res_600 = self.call("TimedRecruitInfo", "DrawCreditReward", 600, 83)
        self.assertEqual(res_600["Status"], 0)
        box_33 = next(g for g in self.profile.state["goods"] if int(g["GoodsModelId"]) == 16060033)
        self.assertEqual(int(box_33["Num"]), 50)
        # Duplicate claim rejected
        self.assertNotEqual(self.call("TimedRecruitInfo", "DrawCreditReward", 600, 83)["Status"], 0)

        # Recruiting when hero bag is full returns -2005 without deducting diamonds
        dia_before = int(self.profile.state["player"]["Diamond"])
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 30, 83)["Status"], -2005)
        self.assertEqual(self.call("HeroRecruit", "Recruit", 30, 0)["Status"], -2005)
        self.assertEqual(int(self.profile.state["player"]["Diamond"]), dia_before)

        # Expand bag twice (+10 slots = 310, cost 10+20 = 30 KC)
        self.assertEqual(self.call("Bag", "BagExpand", 5)["Value"]["Size"], 305)
        self.assertEqual(self.call("Bag", "BagExpand", 5)["Value"]["Size"], 310)
        self.assertEqual(int(self.profile.state["player"]["Diamond"]), dia_before - 30)

        # Now 10x pull triggering Bless UR grants 9 heroes + sets DrawGoldHero=0
        with patch.object(random, "random", return_value=0.0):
            r_ur10 = self.call("TimedRecruitInfo", "Recruit", 30, 83)
        self.assertEqual(r_ur10["Status"], 0)
        self.assertEqual(len(r_ur10["Value"]["BaseGetGameResourceList"][0]["Hero"]), 9)
        self.assertEqual(r_ur10["Value"]["RecruitInfo"]["DrawGoldHero"], 0)

        # Bag now has 309/310 (1 slot left) -> DrawGoldHero succeeds!
        iid = r_ur10["Value"]["RecruitInfo"]["EventInstanceId"]
        d_ur = self.call("TimedRecruitInfo", "DrawGoldHero", 12015022, 83, iid)
        self.assertEqual(d_ur["Status"], 0)
        self.assertEqual(d_ur["Value"]["RecruitInfo"]["DrawGoldHero"], 1)
        self.assertTrue(any(int(h["HeroModelId"]) == 12015022 for h in self.profile.state["heroes"]))

    def test_mate_slots_excluded_from_hero_bag_capacity_like_client(self):
        # Unlock mate slot 1 via StarId and equip a hero to mate slot 1
        req_star = int(self.profile.game_data["attrtree_slots"]["21"]["needAttrTreeID"])
        self.profile.state["player"]["StarId"] = req_star
        mate_hero = self.profile._build_hero_instance(12011004)
        self.profile.state["heroes"].append(mate_hero)
        self.assertEqual(self.call("Slot", "MateinfoCombat", 1, mate_hero["Id"])["Status"], 0)
        self.assertIn(mate_hero["Id"], self.profile._deployed_hero_ids())

        # Fill unbattle heroes to exactly 299 -> 1 slot left -> 1x pull succeeds
        deployed = self.profile._deployed_hero_ids()
        unbattle = sum(1 for h in self.profile.state["heroes"] if h["Id"] not in deployed)
        self.profile.state["heroes"].extend(
            self.profile._build_hero_instance(12011014) for _ in range(299 - unbattle)
        )
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 3, 83)["Status"], 0)
        # Now 300/300 -> next pull fails with -2005
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 3, 83)["Status"], -2005)

    def test_four_s1_accounts_isolation_after_reload(self):
        # Switch through acct_1..acct_4 and verify independent hero bags & banner states
        self.emu.handle_rpc({"ServerId": 1, "ModuleName": "Account", "MethodName": "List", "Data": []})
        for aid in ("acct_2", "acct_3", "acct_4"):
            sw = self.emu.handle_rpc({"ServerId": 1, "ModuleName": "Account", "MethodName": "Switch", "Data": [aid]})
            self.assertEqual(sw["Status"], 0)
            info = self.call("TimedRecruitInfo", "GetTimedRecruitInfo", 83)
            self.assertEqual(info["Status"], 0)
            self.assertEqual(info["Value"]["MyCredit"], 0)
        self.emu.handle_rpc({"ServerId": 1, "ModuleName": "Account", "MethodName": "Switch", "Data": ["acct_1"]})
        self.reload()
        self.assertEqual(sorted(self.emu.s1_accounts.keys()), ["acct_1", "acct_2", "acct_3", "acct_4"])


if __name__ == "__main__":
    unittest.main()
