"""R7.20 — Hero Conversion QoL (Orange & below batch refine) & Tầm Ngọc (Explore) regression tests."""

from pathlib import Path
import tempfile
import unittest

from emulator import GameEmulatorState


class R720ConversionAndExploreTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(1795180000)
        self.profile = self.emu.profiles["normal"]
        self.profile.state["player"].update(
            Lv=80, Vip=11, VIPLv=11, VipLv=11, IsNewPlayer=0, Diamond=500_000, Gold=1_000_000, HeroCoin=0
        )
        self.profile.save()

    def call(self, module, method, *args, server_id=1):
        return self.emu.handle_rpc(
            {"ServerId": server_id, "ModuleName": module, "MethodName": method, "Data": list(args)}
        )

    def test_batch_refine_350_plus_heroes_including_orange_protects_ur_and_deployed(self):
        # Grant 360 fodder heroes (Green 12011039, Blue 12011033, Purple 12011023, Orange 12011009/12012010)
        # Plus protected heroes: UR 12015022 (q=18), UR 12015023 (q=18), and a mate-slot Orange hero
        fodder_models = [12011039, 12011033, 12011023, 12011009, 12012010]
        fodder_ids = []
        for idx in range(360):
            h = self.profile._build_hero_instance(fodder_models[idx % len(fodder_models)])
            self.profile.state["heroes"].append(h)
            fodder_ids.append(h["Id"])

        ur1 = self.profile._build_hero_instance(12015022)
        ur2 = self.profile._build_hero_instance(12015023)
        mate_orange = self.profile._build_hero_instance(12011009)
        self.profile.state["heroes"].extend([ur1, ur2, mate_orange])

        req_star = int(self.profile.game_data["attrtree_slots"]["21"]["needAttrTreeID"])
        self.profile.state["player"]["StarId"] = req_star
        self.assertEqual(self.call("Slot", "MateinfoCombat", 1, mate_orange["Id"])["Status"], 0)

        deployed_id = next(iter(self.profile._deployed_hero_ids()))
        # Send batch refine including fodder + mate + deployed (server must protect deployed & mate)
        res = self.call("Hero", "HeroRefine", fodder_ids + [mate_orange["Id"], deployed_id])
        self.assertEqual(res["Status"], 0)

        # Aggregated PlayerAttr in BaseGetGameResourceList (no 720-entry explosion)
        attrs = res["Value"]["BaseGetGameResourceList"][0]["PlayerAttr"]
        self.assertLessEqual(len(attrs), 4)
        self.assertGreater(int(self.profile.state["player"]["HeroCoin"]), 0)

        # All 360 fodder removed; UR, main, deployed, and mate heroes remain intact
        remaining_ids = {h["Id"] for h in self.profile.state["heroes"]}
        for fid in fodder_ids:
            self.assertNotIn(fid, remaining_ids)
        self.assertIn(ur1["Id"], remaining_ids)
        self.assertIn(ur2["Id"], remaining_ids)
        self.assertIn(mate_orange["Id"], remaining_ids)
        self.assertIn(deployed_id, remaining_ids)

        # Empty / invalid refine returns -1 without losing any remaining hero
        before_cnt = len(self.profile.state["heroes"])
        self.assertEqual(self.call("Hero", "HeroRefine", [])["Status"], -1)
        self.assertEqual(len(self.profile.state["heroes"]), before_cnt)

    def test_explore_one_key_and_consecutive_runs(self):
        info = self.call("Explore", "GetInfo")
        self.assertEqual(info["Status"], 0)
        rem0 = info["Value"]["RemainNum"]
        self.assertGreater(rem0, 0)

        # Consecutive OneKeyExplore calls until exhausted
        total_daily = 0
        while rem0 > 0:
            res = self.call("Explore", "OneKeyExplore")
            self.assertEqual(res["Status"], 0)
            self.assertLess(res["Value"]["RemainNum"], rem0)
            rem0 = res["Value"]["RemainNum"]
            total_daily = res["Value"]["DailyNum"]
            self.assertTrue(res["Value"]["BaseGetGameResourceList"])

        self.assertGreater(total_daily, 0)
        # When RemainNum == 0, OneKeyExplore returns -5101 cleanly
        self.assertEqual(self.call("Explore", "OneKeyExplore")["Status"], -5101)


if __name__ == "__main__":
    unittest.main()
