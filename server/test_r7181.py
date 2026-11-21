"""R7.18.1 — Banner 83 (Thần Tướng D: Inu Kimi & Tứ Đấu Thần) acceptance tests."""

from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from combat_sim import simulate_fight_info
from emulator import GameEmulatorState


class R7181Banner83Test(unittest.TestCase):
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

    def _grant_goods(self, gid: int, num: int) -> str:
        self.profile._grant_resources_from_tuples([(1606 if gid // 10000 == 1606 else 1501, gid, num)], "test", f"g:{gid}:{num}")
        item = next(g for g in self.profile.state["goods"] if int(g["GoodsModelId"]) == gid)
        return item["Id"]

    def test_banner_83_enabled_by_default_and_upgrade_from_832_preserves_81_82(self):
        # 1. Fresh save exposes 81, 82, 83 concurrently
        res = self.call("TimedRecruitInfo", "GetTimedRecruitInfo")
        self.assertEqual(res["Status"], 0)
        self.assertEqual(sorted(res["Value"]["AvailableBanners"]), [81, 82, 83])

        # 2. Simulate upgrading an 832 save (r79_migrated=True, only 81 & 82 in concurrent_events)
        ac = self.profile.state["event_runtime"]["archive_config"]
        ac["concurrent_events"] = [x for x in ac["concurrent_events"] if x != "timed_recruit:83"]
        ac["rotation_pool"] = ["timed_recruit:81", "timed_recruit:82"]
        ac.pop("r7181_migrated", None)
        self.profile.state["selected_banners"]["9300"] = 82
        # Record progress on 81 & 82 before upgrade
        self.assertEqual(self.call("TimedRecruitInfo", "SelectBanner", 81)["Status"], 0)
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 3, 81)["Status"], 0)
        self.assertEqual(self.call("TimedRecruitInfo", "SelectBanner", 82)["Status"], 0)
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 3, 82)["Status"], 0)
        self.profile.save()

        self.reload()
        b81 = self.call("TimedRecruitInfo", "GetTimedRecruitInfo", 81)["Value"]
        b82 = self.call("TimedRecruitInfo", "GetTimedRecruitInfo", 82)["Value"]
        b83 = self.call("TimedRecruitInfo", "SelectBanner", 83)["Value"]
        self.assertEqual(sorted(b83["AvailableBanners"]), [81, 82, 83])
        self.assertEqual(b81["MyCredit"], 10)
        self.assertEqual(b82["MyCredit"], 10)
        self.assertEqual(b83["MyCredit"], 0)
        self.assertEqual(b83["ActivityEnumId"], 83)

        # Verify 81/82 pools & prices are untouched
        tr_cfg = self.profile.game_data["timed_recruit_model"]
        self.assertEqual(int(tr_cfg["81"]["goldHeroModelID"]), 16060008)
        self.assertEqual(int(tr_cfg["82"]["goldHeroModelID"]), 16060009)
        self.assertEqual(int(tr_cfg["83"]["goldHeroModelID"]), 16060034)
        self.assertEqual(int(tr_cfg["81"]["recruitPrice"]), 280)
        self.assertEqual(int(tr_cfg["82"]["recruitPrice"]), 280)

    def test_receive_inu_kimi_and_tu_dau_than_on_same_s1_account(self):
        sel = self.call("TimedRecruitInfo", "SelectBanner", 83)
        self.assertEqual(sel["Status"], 0)

        # 6x 10-pulls = 600 credit -> claim all 6 sequential credit milestones (60..600)
        for _ in range(6):
            r = self.call("TimedRecruitInfo", "Recruit", 30, 83)
            self.assertEqual(r["Status"], 0)
        for req_c in (60, 200, 300, 400, 500, 600):
            c_res = self.call("TimedRecruitInfo", "DrawCreditReward", req_c, 83)
            self.assertEqual(c_res["Status"], 0)

        # Verify 50x 16060033 (Quà Mảnh Thần D) received in bag
        box_33 = next(g for g in self.profile.state["goods"] if int(g["GoodsModelId"]) == 16060033)
        self.assertEqual(int(box_33["Num"]), 50)

        # Trigger pending_gold_hero via bless (force random=0.0) and claim Inu Kimi (12015023)
        with patch.object(random, "random", return_value=0.0):
            r_ur = self.call("TimedRecruitInfo", "Recruit", 3, 83)
            self.assertEqual(r_ur["Status"], 0)
            self.assertEqual(r_ur["Value"]["RecruitInfo"]["DrawGoldHero"], 0)

        iid = r_ur["Value"]["RecruitInfo"]["EventInstanceId"]
        d1 = self.call("TimedRecruitInfo", "DrawGoldHero", 12015023, 83, iid)
        self.assertEqual(d1["Status"], 0)
        self.assertEqual(d1["Value"]["RecruitInfo"]["DrawGoldHero"], 1)

        # Trigger second UR choice and claim Tứ Đấu Thần (12015022) on the same S1 account
        with patch.object(random, "random", return_value=0.0):
            r_ur2 = self.call("TimedRecruitInfo", "Recruit", 3, 83)
            self.assertEqual(r_ur2["Status"], 0)
            self.assertEqual(r_ur2["Value"]["RecruitInfo"]["DrawGoldHero"], 0)

        d2 = self.call("TimedRecruitInfo", "DrawGoldHero", 12015022, 83, iid)
        self.assertEqual(d2["Status"], 0)

        owned_models = {int(h["HeroModelId"]) for h in self.profile.state["heroes"]}
        self.assertIn(12015023, owned_models)
        self.assertIn(12015022, owned_models)
        # Verify neither was converted to SR or altered in quality/race/ID
        for hid in ("12015022", "12015023"):
            cfg = self.profile.game_data["heroes"][hid]
            self.assertEqual(int(cfg["quality"]), 18)
            self.assertEqual(int(cfg["raceID"]), 0)

    def test_compose_150_pieces_and_box_choices(self):
        # Grant 150x 16060033 and 150x 16060033 -> choose 150 of each shard
        b33_id = self._grant_goods(16060033, 300)
        self.assertEqual(self.call("Goods", "GoodsUseForBoxChoice", b33_id, 16060033, 15010094, 150)["Status"], 0)
        b33_id = next(g["Id"] for g in self.profile.state["goods"] if int(g["GoodsModelId"]) == 16060033)
        self.assertEqual(self.call("Goods", "GoodsUseForBoxChoice", b33_id, 16060033, 15010095, 150)["Status"], 0)

        s22 = next(g for g in self.profile.state["goods"] if int(g["GoodsModelId"]) == 15010094)
        s23 = next(g for g in self.profile.state["goods"] if int(g["GoodsModelId"]) == 15010095)
        self.assertEqual(int(s22["Num"]), 150)
        self.assertEqual(int(s23["Num"]), 150)

        # Less than 150 cannot compose
        self.assertEqual(self.call("Goods", "GoodsUse", s22["Id"], 15010094, 149)["Status"], -1)
        # Compose 150 -> Tứ Đấu Thần (12015022) & Inu Kimi (12015023)
        self.assertEqual(self.call("Goods", "GoodsUse", s22["Id"], 15010094, 150)["Status"], 0)
        self.assertEqual(self.call("Goods", "GoodsUse", s23["Id"], 15010095, 150)["Status"], 0)

        # Also test 16060034 box choice for both heroes
        b34_id = self._grant_goods(16060034, 2)
        self.assertEqual(self.call("Goods", "GoodsUseForBoxChoice", b34_id, 16060034, 12015022, 1)["Status"], 0)
        b34_id = next(g["Id"] for g in self.profile.state["goods"] if int(g["GoodsModelId"]) == 16060034)
        self.assertEqual(self.call("Goods", "GoodsUseForBoxChoice", b34_id, 16060034, 12015023, 1)["Status"], 0)

        counts = [int(h["HeroModelId"]) for h in self.profile.state["heroes"]]
        self.assertEqual(counts.count(12015022), 2)
        self.assertEqual(counts.count(12015023), 2)

    def test_bag_full_errors_and_duplicate_requests(self):
        # Fill hero bag to exact capacity
        cap = self.profile._bag_info(5)["Size"]
        deployed = {str(s.get("HeroId")) for s in self.profile.state["slots"]}
        cur_used = sum(str(h["Id"]) not in deployed for h in self.profile.state["heroes"])
        for _ in range(cap - cur_used):
            self.profile.state["heroes"].append(self.profile._build_hero_instance(12011014))

        b34_id = self._grant_goods(16060034, 1)
        s22_id = self._grant_goods(15010094, 150)

        # Bag full rejects 16060034 box choice, 150-piece compose, and banner pull without losing items/diamonds
        diam_before = int(self.profile.state["player"]["Diamond"])
        self.assertEqual(self.call("Goods", "GoodsUseForBoxChoice", b34_id, 16060034, 12015023, 1)["Status"], -2005)
        self.assertEqual(self.call("Goods", "GoodsUse", s22_id, 15010094, 150)["Status"], -2005)
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 3, 83)["Status"], -2005)
        self.assertEqual(int(self.profile.state["player"]["Diamond"]), diam_before)
        self.assertTrue(any(g["Id"] == b34_id and int(g["Num"]) == 1 for g in self.profile.state["goods"]))
        self.assertTrue(any(g["Id"] == s22_id and int(g["Num"]) == 150 for g in self.profile.state["goods"]))

        # Free space and test DrawGoldHero validation & duplicate guards
        self.profile.state["heroes"] = [h for h in self.profile.state["heroes"] if str(h["Id"]) in deployed]
        self.assertEqual(self.call("TimedRecruitInfo", "SelectBanner", 83)["Status"], 0)
        for _ in range(6):
            self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 30, 83)["Status"], 0)
        # Out-of-order credit claim rejected
        self.assertEqual(self.call("TimedRecruitInfo", "DrawCreditReward", 200, 83)["Status"], -1)
        for req_c in (60, 200, 300, 400, 500, 600):
            self.assertEqual(self.call("TimedRecruitInfo", "DrawCreditReward", req_c, 83)["Status"], 0)
        # Duplicate credit claim rejected
        self.assertEqual(self.call("TimedRecruitInfo", "DrawCreditReward", 60, 83)["Status"], -1)

        with patch.object(random, "random", return_value=0.0):
            r_ur = self.call("TimedRecruitInfo", "Recruit", 3, 83)
            self.assertEqual(r_ur["Value"]["RecruitInfo"]["DrawGoldHero"], 0)
        iid = r_ur["Value"]["RecruitInfo"]["EventInstanceId"]

        # Calling Recruit while pending_gold_hero is True must NOT double-charge
        diam_pending = int(self.profile.state["player"]["Diamond"])
        r_dup_pull = self.call("TimedRecruitInfo", "Recruit", 3, 83)
        self.assertEqual(r_dup_pull["Status"], 0)
        self.assertEqual(r_dup_pull["Value"]["BaseGetGameResourceList"], [])
        self.assertEqual(int(self.profile.state["player"]["Diamond"]), diam_pending)

        # Invalid hero model or stale instance_id rejected without clearing pending_gold_hero
        self.assertEqual(self.call("TimedRecruitInfo", "DrawGoldHero", 12011004, 83, iid)["Status"], -3123)
        self.assertEqual(self.call("TimedRecruitInfo", "DrawGoldHero", 12015023, 83, "stale:id")["Status"], -3106)

        # Valid claim succeeds; duplicate claim is rejected
        self.assertEqual(self.call("TimedRecruitInfo", "DrawGoldHero", 12015023, 83, iid)["Status"], 0)
        self.assertEqual(self.call("TimedRecruitInfo", "DrawGoldHero", 12015023, 83, iid)["Status"], -3116)

    def test_hero_progression_bonds_combat_and_save_reload(self):
        p = self.profile
        h_22 = p._build_hero_instance(12015022, lv=40, step=0)
        h_23 = p._build_hero_instance(12015023, lv=40, step=0)
        h_kagome = p._build_hero_instance(12011003, lv=40, step=0)
        p.state["heroes"].extend([h_22, h_23, h_kagome])
        p._grant_resources_from_tuples([(1605, 16050001, 5000)], "test", "step_stones")
        self.assertEqual(self.call("Slot", "HeroCombat", 2, h_22["Id"])["Status"], 0)
        self.assertEqual(self.call("Slot", "HeroCombat", 3, h_23["Id"])["Status"], 0)
        self.assertEqual(self.call("Slot", "HeroCombat", 4, h_kagome["Id"])["Status"], 0)

        # StepUp +1 (no treasures) then +2 (2x 14010501 books) on Tứ Đấu Thần (stepUpClassID=15)
        p._grant_resources_from_tuples([(1401, 14010501, 2)], "test", "step2_book")
        book_ids = [t["Id"] for t in p.state["treasures"] if int(t["TreasureModelId"]) == 14010501][-2:]
        self.assertEqual(self.call("Hero", "HeroStepUp", h_22["Id"], [], 0)["Status"], 0)
        self.assertEqual(self.call("Hero", "HeroStepUp", h_22["Id"], book_ids, 1)["Status"], 0)
        self.assertEqual(int(h_22["Step"]), 2)

        # Verify Linh Vu bonds (555 on Inu Kimi, 559 on Tứ Đấu Thần) are active in Slot Property
        bonds_22 = set(p.state["slots"][1]["Property"]["ActivePrIds"])
        bonds_23 = set(p.state["slots"][2]["Property"]["ActivePrIds"])
        self.assertIn(559, bonds_22)
        self.assertIn(555, bonds_23)

        # Fight in campaign node 1111 using both heroes + simulate_fight_info
        fi = self.call("Battle", "GetFightInfo", 11, 1111, 1)
        self.assertEqual(fi["Status"], 0)
        sim = simulate_fight_info(
            fi["Value"]["FightInfo"],
            p.game_data["attacks"],
            buffs_cfg=p.game_data["combat_buffs"],
        )
        self.assertTrue(sim.won)
        bres = self.call("Battle", "Fight", 11, 1111, 1, sim.verify_data)
        self.assertEqual(bres["Status"], 0)

        # Save & reload preserves heroes, steps, and slots
        self.profile.save()
        self.reload()
        reloaded_models = {int(h["HeroModelId"]): h for h in self.profile.state["heroes"]}
        self.assertIn(12015022, reloaded_models)
        self.assertIn(12015023, reloaded_models)
        self.assertEqual(int(reloaded_models[12015022]["Step"]), 2)

    def test_switch_between_banners_81_82_83_preserves_state(self):
        # Distinct pulls on 81, 82, 83
        self.assertEqual(self.call("TimedRecruitInfo", "SelectBanner", 81)["Status"], 0)
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 3, 81)["Status"], 0)  # +10 credit, pity 8

        self.assertEqual(self.call("TimedRecruitInfo", "SelectBanner", 82)["Status"], 0)
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 30, 82)["Status"], 0)  # +100 credit

        self.assertEqual(self.call("TimedRecruitInfo", "SelectBanner", 83)["Status"], 0)
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 30, 83)["Status"], 0)
        self.assertEqual(self.call("TimedRecruitInfo", "Recruit", 30, 83)["Status"], 0)  # +200 credit
        self.assertEqual(self.call("TimedRecruitInfo", "DrawCreditReward", 60, 83)["Status"], 0)

        # Switch back and forth and verify zero cross-contamination
        s81 = self.call("TimedRecruitInfo", "SelectBanner", 81)["Value"]
        s82 = self.call("TimedRecruitInfo", "SelectBanner", 82)["Value"]
        s83 = self.call("TimedRecruitInfo", "SelectBanner", 83)["Value"]
        self.assertEqual(s81["MyCredit"], 10)
        self.assertEqual(s81["DrawCreditRewards"], "")
        self.assertEqual(s82["MyCredit"], 100)
        self.assertEqual(s82["DrawCreditRewards"], "")
        self.assertEqual(s83["MyCredit"], 200)
        self.assertEqual(s83["DrawCreditRewards"], "60")


if __name__ == "__main__":
    unittest.main()
