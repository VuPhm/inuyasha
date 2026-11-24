"""Delta coverage for R7.32 (REC-P2-05): Kết toán BXH cuối kỳ sự kiện (4410/4421/4422/4430) & 5 bảng cấu hình VN."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import GameEmulatorState  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R732EventSettlementAndConfigTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
        base_ts = ts if ts is not None else _ts_vn(2026, 11, 17, 12, 0)
        emu.clock.set_fixed(base_ts)
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(prof: any, mod: str, fn: str, *args: object) -> dict:
        return prof.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    @staticmethod
    def _recharge(prof: any, product_id: str | int) -> None:
        order = prof.handle_rpc({"ServerId": 1, "ModuleName": "PlayerCharge", "MethodName": "GenerateOrderID", "Data": [product_id]})["Value"]
        res = prof.handle_rpc({"ServerId": 1, "ModuleName": "PlayerCharge", "MethodName": "ConfirmOrder", "Data": [product_id, order]})
        assert res["Status"] == 0, res

    @staticmethod
    def _count_goods(prof: any, model_id: int) -> int:
        return sum(int(g.get("Num", 0)) for g in prof.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == model_id)

    def test_01_extracted_lv_plan_vip_welfare_and_bag_configs(self) -> None:
        gd = json.loads((ROOT / "server" / "game_data.json").read_text(encoding="utf-8"))
        self.assertEqual(gd["lv_plan_config"], {"needVIPLV": 2})
        self.assertEqual(len(gd["lv_plan_rewards"]), 10)
        self.assertEqual(len(gd["vip_welfare"]), 21)
        self.assertEqual(len(gd["bag_model"]), 9)
        self.assertEqual(len(gd["bag_expand_use"]), 20)

        with tempfile.TemporaryDirectory() as tmp:
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu, p = self._new_emu(tmp, ts=base_ts)
            p.admin_prepare_account(target_lv=15, vip_lv=1, source="test_r732")
            p.state["player"]["Diamond"] = 5000

            # LvPlan blocked when Vip < needVIPLV (2)
            lp_low = self._call(p, "LvPlan", "GetLvPlanInfo")
            self.assertEqual(lp_low["Value"]["CanRewardLvList"], [])
            self.assertEqual(self._call(p, "LvPlan", "ReceiveLvPlan", 10)["Status"], -1)

            # Raise Vip=2: ReceiveLvPlan(10) spends 100 KC and grants +200 KC (net +100 KC)
            p.state["player"]["Vip"] = 2
            lp_ok = self._call(p, "LvPlan", "GetLvPlanInfo")
            self.assertEqual(lp_ok["Value"]["CanRewardLvList"], [10, 15])
            dia_before = int(p.state["player"]["Diamond"])
            r10 = self._call(p, "LvPlan", "ReceiveLvPlan", 10)
            self.assertEqual(r10["Status"], 0)
            self.assertEqual(r10["Avatar"]["Diamond"], dia_before + 100)

            # VipWelfare uses self.clock.today_str() -> rolls over next day
            vw1 = self._call(p, "VipWelfare", "GetVipWelfare")
            self.assertTrue(vw1["Value"]["CanDraw"])
            self.assertEqual(self._call(p, "VipWelfare", "DrawVipWelfare")["Status"], 0)
            self.assertFalse(self._call(p, "VipWelfare", "GetVipWelfare")["Value"]["CanDraw"])
            self.assertEqual(self._call(p, "VipWelfare", "DrawVipWelfare")["Status"], -1)

            emu.clock.set_fixed(base_ts + 86400)
            self.assertTrue(self._call(p, "VipWelfare", "GetVipWelfare")["Value"]["CanDraw"])
            self.assertEqual(self._call(p, "VipWelfare", "DrawVipWelfare")["Status"], 0)

            # BagExpand preserves offline base size (300 hero / 200 other), uses 10/20/... KC & caps at 20
            self.assertEqual(p._bag_info(5)["Size"], 300)
            self.assertEqual(p._bag_info(4)["Size"], 200)
            d_before = int(p.state["player"]["Diamond"])
            b1 = self._call(p, "Bag", "BagExpand", 5)
            self.assertEqual(b1["Status"], 0)
            self.assertEqual(b1["Value"]["Size"], 305)
            self.assertEqual(b1["Avatar"]["Diamond"], d_before - 10)
            b2 = self._call(p, "Bag", "BagExpand", 5)
            self.assertEqual(b2["Value"]["Size"], 310)
            self.assertEqual(b2["Avatar"]["Diamond"], d_before - 30)
            for _ in range(18):
                self.assertEqual(self._call(p, "Bag", "BagExpand", 5)["Status"], 0)
            self.assertEqual(p._bag_info(5)["Size"], 400)
            self.assertEqual(self._call(p, "Bag", "BagExpand", 5)["Status"], -1)

    def test_02_xssb_4410_rank_and_unclaimed_credits_settlement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu, p = self._new_emu(tmp, ts=base_ts)
            p.admin_prepare_account(target_lv=35, vip_lv=4, source="test_r732")
            p.state["player"]["Diamond"] = 20_000
            p.save()

            # Reach 230 integral (> 220 top bot -> Rank 1) and claim only chest 50
            xs0 = self._call(p, "TimedXssbInfo", "CallEquip", 3, 10)
            self.assertEqual(xs0["Status"], 0)
            xs1 = self._call(p, "TimedXssbInfo", "CallEquip", 3, 10)
            self.assertEqual(xs1["Status"], 0)
            xs_f = self._call(p, "TimedXssbInfo", "CallEquip", 1, 1)
            self.assertEqual(xs_f["Status"], 0)
            self.assertEqual(xs_f["Value"]["TimedXssbInfo"]["Integral"], 230)
            self.assertEqual(xs_f["Value"]["TimedXssbInfo"]["Rank"], 1)
            self.assertEqual(self._call(p, "TimedXssbInfo", "ReceiveReward", 50)["Status"], 0)

            ev = p.event_runtime.evaluate("timed_xssb", p.state["player"])
            iid = ev.instance_id
            end_ts = int(ev.end_ts)

            # Advance past period end -> RewardCenter receives both Rank 1 + unclaimed 100 & 200 chests
            emu.clock.set_fixed(end_ts + 10)
            rew = self._call(p, "Reward", "Rewars")
            self.assertEqual(rew["Status"], 0)
            self.assertEqual(rew["Avatar"]["RedDotInfo"]["2400"], 1)
            by_title = {r["Title"]: r for r in rew["Value"]}
            self.assertIn("Thần Binh Giới Hạn — Hạng 1", by_title)
            self.assertIn("Quà Mốc Tích Lũy Thần Binh Giới Hạn", by_title)

            # Repeat sync does not duplicate RewardCenter entries
            self.assertEqual(len(self._call(p, "Reward", "Rewars")["Value"]), len(rew["Value"]))

            # Rank 1 reward gives 1000 KC; unclaimed 100 + 200 gives 150 + 300 = 450 KC -> total +1450 KC
            dia_before = int(p.state["player"]["Diamond"])
            ids = [by_title["Thần Binh Giới Hạn — Hạng 1"]["Id"], by_title["Quà Mốc Tích Lũy Thần Binh Giới Hạn"]["Id"]]
            drawn = self._call(p, "Reward", "DrawGiftBags", ids)
            self.assertEqual(drawn["Status"], 0)
            self.assertEqual(drawn["Avatar"]["Diamond"], dia_before + 1450)
            self.assertIn(13010602, [e["EquipModelId"] for e in p.state["equips"]])
            self.assertIn(13020602, [e["EquipModelId"] for e in p.state["equips"]])
            self.assertIn(13010404, [e["EquipModelId"] for e in p.state["equips"]])
            self.assertIn(13010503, [e["EquipModelId"] for e in p.state["equips"]])

            # New period with 0 integral produces no xssb RewardCenter entry when it ends
            ev2 = p.event_runtime.evaluate("timed_xssb", p.state["player"])
            self.assertNotEqual(ev2.instance_id, iid)
            emu.clock.set_fixed(int(ev2.end_ts) + 10)
            rew2 = self._call(p, "Reward", "Rewars")["Value"]
            self.assertFalse(any("Thần Binh Giới Hạn" in r["Title"] for r in rew2))

    def test_03_recharge_rank_4421_settlement_and_threshold_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu, p = self._new_emu(tmp, ts=base_ts)
            p.admin_prepare_account(target_lv=30, vip_lv=2, source="test_r732")
            self._recharge(p, "com.cmn.inuyasha.gem1980")

            info = self._call(p, "TimedInfo", "GetChargeRankInfo")
            self.assertEqual(info["Status"], 0)
            self.assertEqual(info["Value"]["Num"], 1980)
            self.assertEqual(info["Value"]["SelfRank"], 1)

            ev = p.event_runtime.evaluate("timed_recharge_rank", p.state["player"])
            emu.clock.set_fixed(int(ev.end_ts) + 10)

            rew = self._call(p, "Reward", "Rewars")
            entry = next((r for r in rew["Value"] if "BXH Nạp Kim Cương — Hạng 1" in r["Title"]), None)
            self.assertIsNotNone(entry)
            dia_before = int(p.state["player"]["Diamond"])
            box_before = self._count_goods(p, 16060019)
            self.assertEqual(self._call(p, "Reward", "DrawGiftBags", [entry["Id"]])["Status"], 0)
            self.assertEqual(int(p.state["player"]["Diamond"]), dia_before + 888)
            self.assertEqual(self._count_goods(p, 16060019), box_before + 1)

        # Below NeedMinNum (< 60) yields no recharge rank settlement
        with tempfile.TemporaryDirectory() as tmp2:
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu2, p2 = self._new_emu(tmp2, ts=base_ts)
            p2.admin_prepare_account(target_lv=30, vip_lv=2, source="test_r732")
            p2._record_period_economy(charged=50)
            ev2 = p2.event_runtime.evaluate("timed_recharge_rank", p2.state["player"])
            emu2.clock.set_fixed(int(ev2.end_ts) + 10)
            rew2 = self._call(p2, "Reward", "Rewars")["Value"]
            self.assertFalse(any("BXH Nạp Kim Cương" in r["Title"] for r in rew2))

    def test_04_consume_rank_4422_settlement_and_manual_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu, p = self._new_emu(tmp, ts=base_ts)
            p.admin_prepare_account(target_lv=30, vip_lv=2, source="test_r732")
            p._record_period_economy(spent=600)

            info = self._call(p, "TimedInfo", "GetUseDiamondRankInfo")
            self.assertEqual(info["Status"], 0)
            self.assertEqual(info["Value"]["Num"], 600)
            self.assertEqual(info["Value"]["SelfRank"], 3)

            old_iid = p.event_runtime.evaluate("timed_consume_rank", p.state["player"]).instance_id
            p.event_runtime.manual_reset_event(
                "timed_consume_rank",
                confirm=True,
                on_ended=p._on_timed_event_ended,
                player=p.state["player"],
            )
            hist = p.event_runtime.rt["archive_history"]
            snap = next(s for s in hist if s["instance_id"] == old_iid)
            self.assertEqual(snap["settlement"]["rank"], 3)

            rew = self._call(p, "Reward", "Rewars")
            entry = next((r for r in rew["Value"] if "BXH Tiêu Kim Cương — Hạng 3" in r["Title"]), None)
            self.assertIsNotNone(entry)
            dia_before = int(p.state["player"]["Diamond"])
            stone_before = self._count_goods(p, 16050001)
            self.assertEqual(self._call(p, "Reward", "DrawGiftBags", [entry["Id"]])["Status"], 0)
            self.assertEqual(int(p.state["player"]["Diamond"]), dia_before + 300)
            self.assertEqual(self._count_goods(p, 16050001), stone_before + 200)

            new_info = self._call(p, "TimedInfo", "GetUseDiamondRankInfo")
            self.assertEqual(new_info["Value"]["Num"], 0)

    def test_05_active_rank_4430_settlement_and_less_score_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu, p = self._new_emu(tmp, ts=base_ts)
            p.admin_prepare_account(target_lv=40, vip_lv=3, source="test_r732")
            sr = self._call(p, "TimedScoreRank", "GetInfo")
            self.assertEqual(sr["Status"], 0)
            self.assertGreaterEqual(sr["Value"]["Score"], 200)
            self.assertEqual(sr["Value"]["Rank"], 1)

            ev = p.event_runtime.evaluate("timed_active_rank", p.state["player"])
            emu.clock.set_fixed(int(ev.end_ts) + 10)
            rew = self._call(p, "Reward", "Rewars")
            entry = next((r for r in rew["Value"] if "BXH Năng Động — Hạng 1" in r["Title"]), None)
            self.assertIsNotNone(entry)
            dia_before = int(p.state["player"]["Diamond"])
            box_before = self._count_goods(p, 16060019)
            self.assertEqual(self._call(p, "Reward", "DrawGiftBags", [entry["Id"]])["Status"], 0)
            self.assertEqual(int(p.state["player"]["Diamond"]), dia_before + 500)
            self.assertEqual(self._count_goods(p, 16060019), box_before + 1)

        # Score below LessScore (20) -> no active rank settlement
        with tempfile.TemporaryDirectory() as tmp2:
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu2, p2 = self._new_emu(tmp2, ts=base_ts)
            p2.state["player"].update(Lv=2, IsNewPlayer=0)
            self.assertLess(p2._player_active_score(), 20)
            sr2 = self._call(p2, "TimedScoreRank", "GetInfo")
            self.assertEqual(sr2["Value"]["Rank"], 0)
            ev2 = p2.event_runtime.evaluate("timed_active_rank", p2.state["player"])
            emu2.clock.set_fixed(int(ev2.end_ts) + 10)
            rew2 = self._call(p2, "Reward", "Rewars")["Value"]
            self.assertFalse(any("BXH Năng Động" in r["Title"] for r in rew2))

    def test_06_multi_account_s1_peer_ranking_consistency_after_expiry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu.clock.set_fixed(base_ts)
            emu.ensure_s1_account_slots(2)
            a1, a2 = emu.s1_accounts["acct_1"], emu.s1_accounts["acct_2"]
            for idx, acct in enumerate((a1, a2), start=1):
                acct.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": [f"CaoThu{idx}", idx % 2]})
                acct.admin_prepare_account(target_lv=35, vip_lv=4, source="test_r732")
                acct.state["player"]["Diamond"] = 20_000
                acct.save()

            # XSSB: a1 pulls 330 pts (Rank 1), a2 pulls 230 pts (> bots 220 -> Rank 2)
            for _ in range(3):
                self.assertEqual(self._call(a1, "TimedXssbInfo", "CallEquip", 3, 10)["Status"], 0)
            for _ in range(2):
                self.assertEqual(self._call(a2, "TimedXssbInfo", "CallEquip", 3, 10)["Status"], 0)
            self.assertEqual(self._call(a2, "TimedXssbInfo", "CallEquip", 1, 1)["Status"], 0)

            # Recharge: a1 recharges 1980 (Rank 1), a2 recharges 1260 (1200+60 > bot 1200 -> Rank 2)
            self._recharge(a1, "com.cmn.inuyasha.gem1980")
            self._recharge(a2, "com.cmn.inuyasha.gem900")
            self._recharge(a2, "com.cmn.inuyasha.gem300")
            self._recharge(a2, "com.cmn.inuyasha.gem60")

            # Active rank: a1 earns 215 pts (Lv35*5 + 20*2), a2 earns 195 pts (Lv35*5 + 10*2) > bots 120
            a1.state["stats"]["elite_Win"] = 20
            a2.state["stats"]["elite_Win"] = 10
            self.assertEqual(self._call(a1, "TimedScoreRank", "GetInfo")["Value"]["Rank"], 1)
            self.assertEqual(self._call(a2, "TimedScoreRank", "GetInfo")["Value"]["Rank"], 2)

            end_ts = int(a1.event_runtime.evaluate("timed_xssb", a1.state["player"]).end_ts)
            emu.clock.set_fixed(end_ts + 10)

            # Settle a1 first (archiving a1's Day-1 instance), then settle a2 -> a2 must receive Rank 2 (not Rank 1!)
            r1 = self._call(a1, "Reward", "Rewars")["Value"]
            r2 = self._call(a2, "Reward", "Rewars")["Value"]
            titles1 = {row["Title"]: row for row in r1}
            titles2 = {row["Title"]: row for row in r2}
            self.assertIn("Thần Binh Giới Hạn — Hạng 1", titles1)
            self.assertIn("BXH Nạp Kim Cương — Hạng 1", titles1)
            self.assertIn("BXH Tiêu Kim Cương — Hạng 1", titles1)
            self.assertIn("BXH Năng Động — Hạng 1", titles1)
            self.assertIn("Thần Binh Giới Hạn — Hạng 2", titles2)
            self.assertIn("BXH Nạp Kim Cương — Hạng 2", titles2)
            self.assertIn("BXH Tiêu Kim Cương — Hạng 2", titles2)
            self.assertIn("BXH Năng Động — Hạng 2", titles2)
            self.assertNotIn("Thần Binh Giới Hạn — Hạng 1", titles2)
            self.assertNotIn("BXH Nạp Kim Cương — Hạng 1", titles2)
            self.assertNotIn("BXH Tiêu Kim Cương — Hạng 1", titles2)
            self.assertNotIn("BXH Năng Động — Hạng 1", titles2)

            # Claim a2's Rank 2 rewards & verify persistence after reload
            draw2 = self._call(
                a2,
                "Reward",
                "DrawGiftBags",
                [
                    titles2["Thần Binh Giới Hạn — Hạng 2"]["Id"],
                    titles2["BXH Nạp Kim Cương — Hạng 2"]["Id"],
                    titles2["BXH Tiêu Kim Cương — Hạng 2"]["Id"],
                    titles2["BXH Năng Động — Hạng 2"]["Id"],
                ],
            )
            self.assertEqual(draw2["Status"], 0)
            expected_dia = int(a2.state["player"]["Diamond"])

            reloaded = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc2.log")
            reloaded.clock.set_fixed(end_ts + 10)
            ra2 = reloaded.s1_accounts["acct_2"]
            self.assertEqual(int(ra2.state["player"]["Diamond"]), expected_dia)
            rem2 = self._call(ra2, "Reward", "Rewars")["Value"]
            self.assertFalse(any("Hạng 2" in row["Title"] for row in rem2))


if __name__ == "__main__":
    unittest.main()
