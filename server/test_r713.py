"""Focused regressions for R7.13 economy changes."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from unittest.mock import patch

import test_emulator

VN_10_AM = 1795143600


class R713DeltaTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.emu = test_emulator.R712DeltaTest.emulator(self.root)
        self.profile = self.emu.profiles["normal"]
        self.emu.clock.set_fixed(VN_10_AM - 1)

    def rpc(self, module, method, *data, profile=None):
        return test_emulator.R712DeltaTest.rpc(profile or self.profile, module, method, *data)

    def shop(self, method="GetInfo", *data, profile=None):
        return self.rpc("MysteryShop", method, *data, profile=profile)

    @staticmethod
    def stock(payload):
        return [item["Id"] for item in payload["MysteryShopGoodsList"]]

    def test_shop_boundary_polling_buy_and_reload(self):
        self.profile.state["player"].update(Lv=28, HeroCoin=2000, Diamond=1000)
        before = self.shop()["Value"]
        self.assertEqual(before["LastFreshDate"], VN_10_AM)
        first = before["MysteryShopGoodsList"][0]
        paid = self.shop("MysteryShopBuyGoods", first["Id"])
        self.assertEqual(paid["Status"], 0)
        self.assertEqual(self.shop("MysteryShopBuyGoods", first["Id"])["Status"], -1)
        after_buy = self.shop()["Value"]
        self.assertEqual(self.stock(after_buy), self.stock(before))
        self.assertEqual(after_buy["MysteryShopGoodsList"][0]["IsSell"], 1)
        self.emu.save_clock()
        self.emu = test_emulator.R712DeltaTest.emulator(self.root)
        self.profile = self.emu.profiles["normal"]
        self.assertEqual(self.shop()["Value"], after_buy)

        self.emu.clock.advance(1)
        with ThreadPoolExecutor(max_workers=4) as workers:
            replies = list(workers.map(lambda _: self.shop()["Value"], range(8)))
        reset = replies[0]
        self.assertTrue(all(item == reset for item in replies))
        self.assertNotEqual(self.stock(before), self.stock(reset))
        self.assertEqual(reset["LastFreshDate"], VN_10_AM + 7200)
        self.assertTrue(all(item["IsSell"] == 0 for item in reset["MysteryShopGoodsList"]))
        self.emu.clock.advance(1)
        self.assertEqual(self.shop()["Value"], reset)

    def test_shop_senior_deadlines_and_paid_and_free_actions(self):
        self.profile.state["player"].update(Lv=35, Diamond=1000)
        self.profile.state["goods"] = [{"Id": "shop-token", "GoodsModelId": 16050010, "Num": 6}]
        normal = self.shop()["Value"]
        senior = self.shop("SeniorGetInfo")["Value"]
        self.assertEqual(senior["LastFreshDate"], VN_10_AM + 7200)
        refresh_free = self.shop("RefreshtGoodsList", 1)["Value"]
        self.assertEqual(refresh_free["FreeCount"], normal["FreeCount"] - 1)
        self.assertEqual(refresh_free["LastFreshDate"], normal["LastFreshDate"])
        self.assertNotEqual(self.stock(normal), self.stock(refresh_free))
        refresh_token = self.shop("SeniorRefreshtGoodsList", 2)
        self.assertEqual(refresh_token["Status"], 0)
        self.assertEqual(self.profile._get_goods_qty(16050010), 1)
        self.assertEqual(refresh_token["Value"]["LastFreshDate"], senior["LastFreshDate"])
        self.assertEqual(self.shop("SeniorRefreshtGoodsList", 2)["Status"], -1802)
        self.assertEqual(self.shop("RefreshtGoodsList", 3)["Avatar"]["Diamond"], 980)
        self.assertEqual(self.shop("SeniorRefreshtGoodsList", 3)["Avatar"]["Diamond"], 880)

        self.emu.clock.set_fixed(senior["LastFreshDate"] - 1)
        refreshed = self.shop("SeniorGetInfo")["Value"]
        self.emu.clock.advance(1)
        noon = self.shop("SeniorGetInfo")["Value"]
        self.assertNotEqual(self.stock(refreshed), self.stock(noon))
        self.assertEqual(noon["LastFreshDate"], senior["LastFreshDate"] + 6 * 3600)
        self.emu.clock.set_fixed(noon["LastFreshDate"])
        evening = self.shop("SeniorGetInfo")["Value"]
        self.assertEqual(evening["LastFreshDate"], noon["LastFreshDate"] + 18 * 3600)
        self.assertEqual(self.shop("SeniorGetInfo")["Value"], evening)

    def test_shop_legacy_and_s1_isolation(self):
        self.emu.ensure_s1_account_slots(2)
        other = self.emu.s1_accounts["acct_2"]
        self.profile.state["player"].update(Lv=35, Diamond=100)
        other.state["player"].update(Lv=35, Diamond=100)
        self.profile.state["mystery_shop"] = {
            "normal": [{"Id": "sold-legacy", "IsSell": 1}], "senior": None,
            "free_date": "2026-11-20", "free_count": 0, "gold_count": 3,
        }
        legacy = self.shop()["Value"]
        self.assertEqual(self.stock(legacy), ["sold-legacy"])
        self.assertEqual(legacy["FreeCount"], 0)
        self.assertEqual(legacy["GoldCount"], 3)
        other_before = self.shop(profile=other)["Value"]
        self.assertEqual(other_before["FreeCount"], 2)
        self.assertEqual(self.shop("RefreshtGoodsList", 1)["Status"], -2105)
        self.assertEqual(self.shop("RefreshtGoodsList", 3)["Avatar"]["Diamond"], 80)
        self.assertEqual(self.shop(profile=other)["Value"], other_before)
        self.assertEqual(other.state["player"]["Diamond"], 100)
        next_day = self.emu.clock.next_midnight_ts()
        self.emu.clock.set_fixed(next_day - 1)
        self.assertEqual(self.shop()["Value"]["GoldCount"], 4)
        self.emu.clock.advance(1)
        self.assertEqual(self.shop()["Value"]["GoldCount"], 0)
        self.assertEqual(self.shop()["Value"]["FreeCount"], 2)


    def test_red_compose_is_atomic_and_preserves_gold_on_rejected_inputs(self):
        self.profile.state["player"]["Gold"] = 20_000_000
        self.rpc("Player", "GetInitData")
        equips = self.profile.state["equips"]
        materials = [self.profile._build_equip_instance(13010602) for _ in range(5)]
        red = [self.profile._build_equip_instance(13010701) for _ in range(5)]
        equips.extend(materials + red)
        ids = [item["Id"] for item in materials]
        compose = lambda ids: self.rpc("Equip", "EquipCompose", ids)
        self.profile.save()
        initial = self.profile.state_path.read_bytes()
        for invalid, status in ((ids[:-1], -1317), (ids[:-1] + ids[:1], -1320),
                                (ids[:-1] + ["missing"], -1301),
                                (ids[:-1] + [red[0]["Id"]], -1325),
                                ([item["Id"] for item in red], -1321)):
            self.assertEqual(compose(invalid)["Status"], status)
            self.assertEqual(self.profile.state["player"]["Gold"], 20_000_000)
            self.assertEqual(self.profile.state_path.read_bytes(), initial)
        self.profile.state["slots"][0]["Weapon"] = materials[0]
        self.assertEqual(compose(ids)["Status"], -1304)
        del self.profile.state["slots"][0]["Weapon"]
        materials[0]["Step"] = 1
        self.assertEqual(compose(ids)["Status"], -1323)
        materials[0]["Step"] = 0
        self.profile.state["player"]["Gold"] = 1
        self.assertEqual(compose(ids)["Status"], -1118)
        self.profile.state["player"]["Gold"] = 20_000_000

        with patch.object(self.profile, "_write_json_atomic", side_effect=OSError("storage")):
            with self.assertLogs(level="ERROR"):
                self.assertEqual(compose(ids)["Status"], -7)
        self.assertEqual(self.profile.state["player"]["Gold"], 20_000_000)
        self.assertEqual(self.profile.state_path.read_bytes(), initial)
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: compose(ids), range(2)))
        self.assertCountEqual([item["Status"] for item in results], [0, -1301])
        successful = next(item["Value"] for item in results if item["Status"] == 0)
        result, = successful["BaseGetGameResourceList"][0]["Equip"]
        self.assertEqual(result["EquipModelId"], 13010701)
        self.assertEqual(successful["ConsumeList"], ids)
        self.profile = test_emulator.R712DeltaTest.emulator(self.root).profiles["normal"]
        self.assertEqual(self.profile.state["player"]["Gold"], 15_000_000)
        self.assertFalse(set(ids) & {item["Id"] for item in self.profile.state["equips"]})
        self.assertIn(result, self.profile.state["equips"])
        self.assertEqual(compose(ids)["Status"], -1301)

    def test_recruit_prices_match_4417_activity_and_expire(self):
        self.profile.state["player"]["Diamond"] = 224
        pull = lambda kind, free=0: self.rpc("HeroRecruit", "Recruit", kind, free)
        result = pull(3)
        self.assertEqual(result["Status"], 0)
        self.assertEqual(result["Avatar"]["TimedActivityOpenInfo"]["4417"][0]["ExtraInfo"]["RefNum"], 80)
        self.assertEqual(result["Avatar"]["Diamond"], 0)
        self.profile.state["player"]["Diamond"] = 2144
        self.assertEqual(pull(30)["Avatar"]["Diamond"], 0)
        welfare = self.profile.event_runtime.evaluate("timed_welfare_hero", self.profile.state["player"])
        self.profile.event_runtime.configure_archive_mode("scheduled", scheduled_windows={
            "timed_welfare_hero": {"start_ts": welfare.start_ts, "end_ts": welfare.end_ts, "enabled": True},
        })
        self.emu.clock.set_fixed(welfare.end_ts)
        self.profile.state["player"]["Diamond"] = 224
        self.assertEqual(pull(3)["Status"], -1105)
        self.assertEqual(self.profile.state["player"]["Diamond"], 224)
        self.profile.state["player"]["Diamond"] = 280
        self.assertEqual(pull(3)["Avatar"]["Diamond"], 0)
        self.assertEqual(pull(2, 1)["Avatar"]["Diamond"], 0)

    def test_wardrobe_step_applies_vn_collection_bonus_to_property_and_fight(self):
        self.profile.state["player"].update(Lv=36, Gold=1_000_000)
        self.profile.state["fashions"] = [
            {"Id": "target-fashion", "FashionModelId": 19010001, "Step": 0},
            {"Id": "duplicate-fashion", "FashionModelId": 19010001, "Step": 0},
        ]
        self.profile.state["goods"] = [{"Id": "cloth", "GoodsModelId": 16070004, "Num": 60}]
        self.profile._recalc_all_slots_and_fap()
        hero_attr = self.profile.state["slots"][0]["Property"].copy()
        reply = self.rpc("Fashion", "StepUp", "target-fashion")
        self.assertEqual(reply["Status"], 0)
        self.assertEqual(reply["Value"]["FashionInfo"]["Step"], 1)
        delta = {"AP": 60, "HP": 400, "DEF": 20, "FAP": 800}
        after = reply["Avatar"]["SlotInfo"][0]["Property"]
        self.assertEqual({key: after[key] - hero_attr[key] for key in delta}, delta)
        self.assertEqual(reply["Avatar"]["GoodsInfo"]["16070004"], [])
        self.assertEqual(reply["Avatar"]["Gold"], 400_000)
        fight = self.rpc("Battle", "GetFightInfo", 11, 1111, 1)
        self.assertEqual(fight["Status"], 0)
        allies = fight["Value"]["FightInfo"]["FightObjs"][0]["Heros"]
        self.assertEqual({key: allies[0][key] for key in ("HP", "AP", "DEF")},
                         {key: after[key] for key in ("HP", "AP", "DEF")})
        self.profile = test_emulator.R712DeltaTest.emulator(self.root).profiles["normal"]
        self.assertEqual(self.profile.state["slots"][0]["Property"], after)
        self.assertEqual(self.rpc("Fashion", "StepUp", "target-fashion")["Status"], -1)

    def charge(self, amount, profile=None):
        order = self.rpc("PlayerCharge", "GenerateOrderID", amount, profile=profile)["Value"]
        reply = self.rpc("PlayerCharge", "ConfirmOrder", amount, order, profile=profile)
        self.assertEqual(reply["Status"], 0)
        return order

    def test_charge_and_spend_only_qualify_in_active_window_after_reload(self):
        self.profile.state["player"].update(Diamond=1000, ChargeNum=15000, VipEXP=15000)
        self.profile.state["stats"].update(recharged_diamonds=15000, spent_diamonds=18000)
        self.emu.ensure_s1_account_slots(2)
        other = self.emu.s1_accounts["acct_2"]
        self.assertEqual(self.rpc("TimedInfo", "GetChargeTotalInfo")["Value"]["ChargeTotalReward"], 0)
        self.assertEqual(self.rpc("TimedInfo", "GetUseTotalInfo")["Value"]["UseTotalReward"], 0)
        self.assertEqual(self.rpc("TimedChargeGift", "ReceiveChargeGift", 101)["Status"], -1)
        self.assertEqual(self.rpc("TimedChargeScore", "BuyGoods", 1, 1)["Status"], -1)
        order = self.charge(60)
        self.assertEqual(self.rpc("PlayerCharge", "ConfirmOrder", 60, order)["Status"], -1136)
        self.assertEqual(self.rpc("TimedInfo", "DrawChargeTotalReward", 60)["Status"], 0)
        self.assertEqual(self.rpc("TimedInfo", "DrawChargeTotalReward", 60)["Status"], -1)
        self.assertEqual(self.rpc("TimedChargeGift", "ReceiveChargeGift", 101)["Status"], 0)
        self.assertEqual(self.rpc("TimedChargeGift", "ReceiveChargeGift", 102)["Status"], -1)
        self.assertEqual(self.rpc("TimedInfo", "GetChargeTotalInfo", profile=other)["Value"]["ChargeTotalReward"], 0)
        self.assertEqual(self.rpc("HeroRecruit", "Recruit", 3, 0)["Status"], 0)
        spent = self.rpc("TimedInfo", "GetUseTotalInfo")["Value"]
        self.assertEqual(spent["UseTotalReward"], 224)
        self.emu.save_clock()
        self.emu = test_emulator.R712DeltaTest.emulator(self.root)
        self.profile = self.emu.profiles["normal"]
        self.assertEqual(self.rpc("TimedInfo", "GetUseTotalInfo")["Value"], spent)
        self.emu.clock.set_fixed(self.emu.clock.next_midnight_ts())
        self.assertEqual(self.rpc("TimedInfo", "GetChargeTotalInfo")["Value"]["ChargeTotalReward"], 0)
        self.assertEqual(self.rpc("TimedInfo", "GetUseTotalInfo")["Value"]["UseTotalReward"], 0)
        self.assertEqual(self.rpc("TimedInfo", "DrawChargeTotalReward", 60)["Status"], -1)
        self.charge(60)
        self.assertEqual(self.rpc("TimedInfo", "DrawChargeTotalReward", 60)["Status"], 0)

    def test_single_orders_days_and_manual_reset_are_separate(self):
        event_ids = ("timed_charge_single", "timed_charge_total", "timed_accum_days", "timed_double_diamond")
        self.profile.event_runtime.configure_archive_mode(
            "concurrent", period_mode="fixed_sec", period_sec=3 * 86400,
            period_anchor_ts=self.emu.clock.midnight_ts(),
            period_overrides={event_id: 3 * 86400 for event_id in event_ids},
        )
        self.charge(300)
        self.charge(300)
        self.assertEqual(self.rpc("TimedInfo", "GetChargeTotalInfo")["Value"]["ChargeTotalReward"], 600)
        self.assertEqual(self.rpc("TimedInfo", "GetChargeSingleInfo")["Value"]["ChargeMaxSingleReward"], 300)
        self.assertEqual(self.rpc("TimedInfo", "GetDoubleDiamondInfo")["Value"]["ChargeMaxMoney"], 300)
        day = self.rpc("TimedInfo", "GetChargeDaysInfo")["Value"][0]
        self.assertEqual((day["ChargeDaysTotal"], day["DailyNum"]), (1, 600))
        self.emu.clock.set_fixed(self.emu.clock.next_midnight_ts())
        self.charge(60)
        day = self.rpc("TimedInfo", "GetChargeDaysInfo")["Value"][0]
        self.assertEqual((day["ChargeDaysTotal"], day["DailyNum"]), (2, 60))
        self.profile.event_runtime.manual_reset_event("timed_charge_total", confirm=True, player=self.profile.state["player"])
        self.assertEqual(self.rpc("TimedInfo", "GetChargeTotalInfo")["Value"]["ChargeTotalReward"], 0)
        self.assertEqual(self.rpc("TimedInfo", "GetChargeSingleInfo")["Value"]["ChargeMaxSingleReward"], 300)


    def test_xssb_rank_excludes_a_peer_from_a_different_instance(self):
        self.emu.ensure_s1_account_slots(2)
        other = self.emu.s1_accounts["acct_2"]
        self.profile.state["player"].update(IsNewPlayer=0, Lv=46)
        other.state["player"].update(IsNewPlayer=0, Lv=46, PlayerName="Peer QA")
        self.assertEqual(self.rpc("TimedXssbInfo", "CallEquip", 1, 1, profile=other)["Status"], 0)
        rank = self.rpc("TimedXssbInfo", "GetInfo")["Value"]["RankList"]
        self.assertIn("Peer QA", [entry["Name"] for entry in rank])
        self.profile.event_runtime.manual_reset_event("timed_xssb", confirm=True, player=self.profile.state["player"])
        new_rank = self.rpc("TimedXssbInfo", "GetInfo")["Value"]["RankList"]
        self.assertNotIn("Peer QA", [entry["Name"] for entry in new_rank])

    def test_in_window_legacy_order_is_recovered_without_carrying_lifetime_spend(self):
        self.profile.state["player"].update(VipEXP=9000, ChargeNum=9000)
        self.profile.state["stats"]["spent_diamonds"] = 5000
        midnight = self.emu.clock.midnight_ts()
        self.profile.state["charge_state"]["orders"] = {
            "expired": {"ProductId": "com.cmn.inuyasha.gem300", "status": "completed", "completed_at": midnight - 1},
            "valid": {"ProductId": "com.cmn.inuyasha.gem60", "status": "completed", "completed_at": midnight},
            "pending": {"ProductId": "com.cmn.inuyasha.gem300", "status": "pending", "completed_at": midnight},
        }
        self.assertEqual(self.rpc("TimedInfo", "GetChargeTotalInfo")["Value"]["ChargeTotalReward"], 60)
        self.assertEqual(self.rpc("TimedInfo", "GetUseTotalInfo")["Value"]["UseTotalReward"], 0)
        self.profile.event_runtime.manual_reset_event("timed_charge_total", confirm=True, player=self.profile.state["player"])
        self.assertEqual(self.rpc("TimedInfo", "GetChargeTotalInfo")["Value"]["ChargeTotalReward"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
