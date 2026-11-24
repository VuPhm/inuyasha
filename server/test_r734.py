"""Delta coverage for R7.34 (REC-P3-04B): FestivalActivity (6300), CommonHoliday (6400) & Player.GetPlayerInfo."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
import sys
import tempfile
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import GameEmulatorState  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R734HolidayAndPlayerInfoTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 22, 12, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    @staticmethod
    def _recharge(prof: Any, product_id: str | int) -> None:
        order = prof.handle_rpc({"ServerId": 1, "ModuleName": "PlayerCharge", "MethodName": "GenerateOrderID", "Data": [product_id]})["Value"]
        res = prof.handle_rpc({"ServerId": 1, "ModuleName": "PlayerCharge", "MethodName": "ConfirmOrder", "Data": [product_id, order]})
        assert res["Status"] == 0, res

    def test_01_festival_6300_and_holiday_6400_home_gating_and_player_activity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=30, vip_lv=3, source="test_r734")

            init_off = self._call(emu, "Player", "GetInitData")
            self.assertEqual(init_off["Status"], 0)
            p_info = init_off["Value"]["PlayerInfo"]
            self.assertEqual(p_info["ActivityPic"], "")
            self.assertEqual(p_info["ActivityName"], "")
            mods_off = {int(m["SubModuleId"]): int(m["IfOpen"]) for m in init_off["Value"]["ModulesInfo"]}
            self.assertEqual(mods_off[6300], 0)
            self.assertEqual(mods_off[6400], 0)

            all_20 = [
                "festival_charge_total", "festival_charge_single", "festival_exchange", "festival_slot",
                "festival_smash_egg", "festival_day_login", "festival_use_total", "festival_points_mall",
                "festival_active_rank", "festival_charge_gift",
                "holiday_charge_total", "holiday_charge_single", "holiday_exchange", "holiday_slot",
                "holiday_smash_egg", "holiday_day_login", "holiday_use_total", "holiday_points_mall",
                "holiday_active_rank", "holiday_charge_gift",
            ]
            p.event_runtime.configure_archive_mode("concurrent", concurrent_events=all_20)
            init_on = self._call(emu, "Player", "GetInitData")
            self.assertEqual(init_on["Status"], 0)
            mods_on = {int(m["SubModuleId"]): int(m["IfOpen"]) for m in init_on["Value"]["ModulesInfo"]}
            self.assertEqual(mods_on[6300], 1)
            self.assertEqual(mods_on[6400], 1)
            open_info = init_on["Avatar"]["TimedActivityOpenInfo"]
            for key in (
                "6301", "6302", "6303", "6304", "6306", "6308", "6309", "6311", "6313", "6314",
                "6401", "6402", "6403", "6404", "6406", "6408", "6409", "6411", "6413", "6414",
            ):
                self.assertIn(key, open_info)
                self.assertEqual(int(open_info[key][0]["ActivityId"]), int(key))

    def test_02_festival_and_holiday_charge_single_total_points_mall_isolated_by_activity_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=30, vip_lv=3, source="test_r734")
            p.event_runtime.configure_archive_mode(
                "concurrent",
                concurrent_events=[
                    "timed_charge_single", "festival_charge_single", "holiday_charge_single",
                    "timed_charge_total", "festival_charge_total",
                    "timed_points_mall", "festival_points_mall",
                ],
            )
            self._recharge(p, "com.cmn.inuyasha.gem300")

            # ChargeSingle: claiming 6302 does NOT affect 4401 or 6402
            self.assertEqual(self._call(p, "TimedInfo", "DrawSingleChargeReward", 6302, 60)["Status"], 0)
            cs_6302 = {r["Id"]: r["Status"] for r in self._call(p, "TimedInfo", "GetChargeSingleInfo", 6302)["Value"]["ChargeSingleDrawNums"]}
            cs_4401 = {r["Id"]: r["Status"] for r in self._call(p, "TimedInfo", "GetChargeSingleInfo", 4401)["Value"]["ChargeSingleDrawNums"]}
            cs_6402 = {r["Id"]: r["Status"] for r in self._call(p, "TimedInfo", "GetChargeSingleInfo", 6402)["Value"]["ChargeSingleDrawNums"]}
            self.assertEqual(cs_6302[60], 2)
            self.assertEqual(cs_4401[60], 1)
            self.assertEqual(cs_6402[60], 1)

            # ChargeTotal: claiming 6301 leaves 4402 claimable
            self.assertEqual(self._call(p, "TimedInfo", "DrawChargeTotalReward", 6301, 300)["Status"], 0)
            ct_6301 = {r["Id"]: r["Status"] for r in self._call(p, "TimedInfo", "GetChargeTotalInfo", 6301)["Value"]["ChargeTotalDrawNums"]}
            ct_4402 = {r["Id"]: r["Status"] for r in self._call(p, "TimedInfo", "GetChargeTotalInfo", 4402)["Value"]["ChargeTotalDrawNums"]}
            self.assertEqual(ct_6301[300], 2)
            self.assertEqual(ct_4402[300], 1)

            # PointsMall: buying item 1 (20 pts) in 6311 leaves 4428 score untouched
            pm_6311_b = self._call(p, "TimedChargeScore", "BuyGoods", 6311, 1, 1)
            self.assertEqual(pm_6311_b["Status"], 0)
            self.assertEqual(pm_6311_b["Value"]["Score"], 280)
            pm_4428 = self._call(p, "TimedChargeScore", "GetRewardList", 4428)["Value"]
            self.assertEqual(pm_4428["Score"], 300)

    def test_03_festival_exchange_day_login_charge_gift_and_use_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=30, vip_lv=3, source="test_r734")
            p.state["player"]["Gold"] = 1_000_000
            p.state["player"]["Diamond"] = 5_000
            p.event_runtime.configure_archive_mode(
                "concurrent",
                concurrent_events=[
                    "festival_exchange", "holiday_exchange",
                    "timed_day_login", "festival_day_login",
                    "timed_charge_gift", "festival_charge_gift",
                    "festival_use_total",
                ],
            )
            self._recharge(p, "com.cmn.inuyasha.gem300")

            # Exchange 6303 vs 6403
            ex_6303 = self._call(p, "TimedLimitExchange", "Exchange", 6303, 1, 1)
            self.assertEqual(ex_6303["Status"], 0)
            info_6403 = self._call(p, "TimedLimitExchange", "GetInfo", 6403)["Value"]
            self.assertEqual(next(r["PersonalNum"] for r in info_6403["ActivityList"] if r["Serial"] == 1), 10)

            # DayLogin: client selects 6308 via GetAcumulateDaysRewardInfo [6308] then calls Draw [day=1]
            dl_6308 = self._call(p, "TimedInfo", "GetAcumulateDaysRewardInfo", 6308)
            self.assertEqual(dl_6308["Status"], 0)
            self.assertEqual(self._call(p, "TimedInfo", "DrawAcumulateDaysReward", 1)["Status"], 0)
            dl_6308_after = {r["Day"]: r["Status"] for r in self._call(p, "TimedInfo", "GetAcumulateDaysRewardInfo", 6308)["Value"][0]["DrawInfo"]}
            dl_4427_after = {r["Day"]: r["Status"] for r in self._call(p, "TimedInfo", "GetAcumulateDaysRewardInfo", 4427)["Value"][0]["DrawInfo"]}
            self.assertEqual(dl_6308_after[1], 2)
            self.assertEqual(dl_4427_after[1], 1)

            # ChargeGift: client selects 6314 via GetChargeGiftInfo [6314] then calls ReceiveChargeGift [101]
            self.assertEqual(self._call(p, "TimedChargeGift", "GetChargeGiftInfo", 6314)["Status"], 0)
            self.assertEqual(self._call(p, "TimedChargeGift", "ReceiveChargeGift", 101)["Status"], 0)
            cg_6314 = self._call(p, "TimedChargeGift", "GetChargeGiftInfo", 6314)["Value"]["ChargeGiftInfo"][0]["ChargeGiftRelInfo"]
            cg_4429 = self._call(p, "TimedChargeGift", "GetChargeGiftInfo", 4429)["Value"]["ChargeGiftInfo"][0]["ChargeGiftRelInfo"]
            self.assertEqual(cg_6314[0]["CanReceive"], 1)
            self.assertEqual(cg_4429[0]["CanReceive"], 2)

            # UseTotal 6309 tracks spent diamonds & claims when 4403 is off
            self.assertEqual(self._call(p, "HeroRecruit", "Recruit", 2, 0)["Status"], 0)
            p.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["FestivalHero", 3]})
            ut_info = self._call(p, "TimedInfo", "GetUseTotalInfo")["Value"]
            self.assertGreaterEqual(ut_info["UseTotalReward"], 100)
            self.assertEqual(self._call(p, "TimedInfo", "DrawUseTotalReward", 100)["Status"], 0)

    def test_04_festival_slot_6304_smash_egg_6306_and_active_rank_6313_settlement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=35, vip_lv=3, source="test_r734")
            p.event_runtime.configure_archive_mode(
                "concurrent",
                concurrent_events=["festival_slot", "festival_smash_egg", "festival_active_rank"],
            )

            slot_info = self._call(p, "TimedLuckdrawInfo", "GetInfo")
            self.assertEqual(slot_info["Status"], 0)
            self.assertEqual(self._call(p, "TimedLuckdrawInfo", "Luckdraw", 1, 1)["Status"], 0)

            egg_info = self._call(p, "TimedSmashingeggsInfo", "GetRewardList")
            self.assertEqual(egg_info["Status"], 0)
            smash_res = self._call(p, "TimedSmashingeggsInfo", "SmashingEggs", 1)
            self.assertEqual(smash_res["Status"], 0)

            p.state["stats"]["elite_Win"] = 20
            sr = self._call(p, "TimedScoreRank", "GetInfo", 6313)
            self.assertEqual(sr["Status"], 0)
            self.assertEqual(sr["Value"]["Rank"], 1)

            # Advance clock past festival_slot & festival_active_rank end_ts -> both settle to RewardCenter
            end_ts = max(
                int(p.event_runtime.evaluate("festival_slot", p.state["player"]).end_ts),
                int(p.event_runtime.evaluate("festival_active_rank", p.state["player"]).end_ts),
            )
            emu.clock.set_fixed(end_ts + 10)
            rc = self._call(p, "Reward", "Rewars")
            self.assertEqual(rc["Status"], 0)
            titles = [row["Title"] for row in rc["Value"]]
            self.assertTrue(any(t.startswith("Kho Báu Quay Thưởng — Hạng ") for t in titles), titles)
            self.assertIn("BXH Năng Động — Hạng 1", titles)

    def test_05_player_get_player_info_s1_peer_npc_and_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True, trace_path=Path(tmp) / "rpc.log")
            emu.ensure_s1_account_slots(2)
            a1, a2 = emu.s1_accounts["acct_1"], emu.s1_accounts["acct_2"]
            self._call(a1, "Player", "NewPlayer", "MinhVuong", 0)
            self._call(a2, "Player", "NewPlayer", "SatSinhHoan", 1)
            a1.admin_prepare_account(target_lv=25, vip_lv=2, source="test_r734")
            a2.admin_prepare_account(target_lv=40, vip_lv=5, source="test_r734")

            # Lookup S1 peer (case-insensitive)
            peer_res = self._call(a1, "Player", "GetPlayerInfo", "satsinhhoan")
            self.assertEqual(peer_res["Status"], 0)
            pv = peer_res["Value"]
            self.assertEqual(pv["PlayerId"], a2.state["player"]["PlayerId"])
            self.assertEqual(pv["PlayerName"], "SatSinhHoan")
            self.assertEqual(pv["LV"], 40)
            self.assertEqual(pv["Vip"], 5)
            self.assertGreater(pv["Quality"], 0)
            self.assertEqual(pv["PVPInterLv"], 0)

            # Lookup social NPC
            npc_res = self._call(a1, "Player", "GetPlayerInfo", "Khuyển Dạ Xoa")
            self.assertEqual(npc_res["Status"], 0)
            self.assertEqual(npc_res["Value"]["PlayerName"], "Khuyển Dạ Xoa")
            self.assertGreater(npc_res["Value"]["FAP"], 0)

            # Missing player -> -3003
            miss = self._call(a1, "Player", "GetPlayerInfo", "NoSuchNinja999")
            self.assertEqual(miss["Status"], -3003)

    def test_06_persistence_across_reload_for_holiday_progress_and_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=30, vip_lv=3, source="test_r734")
            p.event_runtime.configure_archive_mode(
                "concurrent",
                concurrent_events=["festival_charge_single", "holiday_charge_total"],
            )
            self._recharge(p, "com.cmn.inuyasha.gem300")
            self.assertEqual(self._call(p, "TimedInfo", "DrawSingleChargeReward", 6302, 60)["Status"], 0)
            self.assertEqual(self._call(p, "TimedInfo", "DrawChargeTotalReward", 6401, 300)["Status"], 0)
            expected_dia = int(p.state["player"]["Diamond"])

            reloaded = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True, trace_path=Path(tmp) / "rpc2.log")
            reloaded.clock.set_fixed(_ts_vn(2026, 11, 22, 12, 0))
            rp = reloaded.profiles["normal"]
            self.assertEqual(int(rp.state["player"]["Diamond"]), expected_dia)
            cs = {r["Id"]: r["Status"] for r in self._call(rp, "TimedInfo", "GetChargeSingleInfo", 6302)["Value"]["ChargeSingleDrawNums"]}
            ct = {r["Id"]: r["Status"] for r in self._call(rp, "TimedInfo", "GetChargeTotalInfo", 6401)["Value"]["ChargeTotalDrawNums"]}
            self.assertEqual(cs[60], 2)
            self.assertEqual(ct[300], 2)


if __name__ == "__main__":
    unittest.main()
