"""Delta coverage for R7.38: Top 1-tap 1M KC recharge tier & high-tier Gem bags in TimedExchange."""

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


class R738OneTapRechargeAndGemBagsTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 24, 13, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    def test_01_top_one_tap_1m_diamond_tier_order_and_vip_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            clist = self._call(p, "PlayerCharge", "GetChargeList")
            self.assertEqual(clist["Status"], 0)
            tiers = clist["Value"]
            self.assertGreaterEqual(len(tiers), 9)
            top = tiers[0]
            self.assertEqual(top["ProductId"], "com.cmn.inuyasha.gem1000000")
            self.assertEqual(int(top["GamePoint"]), 1_000_000)
            self.assertEqual(int(top["GiveGamePoint"]), 0)
            self.assertEqual(int(top["Ratio"]), 1)
            self.assertTrue(bool(top["Instant"]))
            self.assertEqual([t["ProductId"] for t in tiers[1:]], [
                "com.cmn.inuyasha.gem60",
                "com.cmn.inuyasha.gem180",
                "com.cmn.inuyasha.gem300",
                "com.cmn.inuyasha.gem680",
                "com.cmn.inuyasha.gem900",
                "com.cmn.inuyasha.gem1980",
                "com.cmn.inuyasha.gem3280",
                "com.cmn.inuyasha.gem6480",
            ])

            # Empty GenerateOrderID still defaults to gem60 (not 1M tier)
            def_ord = self._call(p, "PlayerCharge", "GenerateOrderID")
            self.assertEqual(def_ord["Status"], 0)
            self.assertEqual(
                p.state["charge_state"]["orders"][def_ord["Value"]]["ProductId"],
                "com.cmn.inuyasha.gem60",
            )

            dia0 = int(p.state["player"]["Diamond"])
            ord1 = self._call(p, "PlayerCharge", "GenerateOrderID", "com.cmn.inuyasha.gem1000000")
            self.assertEqual(ord1["Status"], 0)
            conf1 = self._call(p, "PlayerCharge", "ConfirmOrder", "com.cmn.inuyasha.gem1000000", ord1["Value"])
            self.assertEqual(conf1["Status"], 0)
            self.assertEqual(int(conf1["Value"]["DiamondAdded"]), 1_000_000)
            self.assertEqual(int(conf1["Value"]["VipEXPAdded"]), 1_000_000)
            self.assertEqual(int(p.state["player"]["Diamond"]), dia0 + 1_000_000)
            self.assertEqual(int(p.state["player"]["Vip"]), 20)

            # Replay same order_id rejected with -1136
            replay = self._call(p, "PlayerCharge", "ConfirmOrder", "com.cmn.inuyasha.gem1000000", ord1["Value"])
            self.assertEqual(replay["Status"], -1136)

            # Second fresh 1-tap order grants another exact +1,000,000 Diamond
            ord2 = self._call(p, "PlayerCharge", "GenerateOrderID", "com.cmn.inuyasha.gem1000000")
            self.assertEqual(ord2["Status"], 0)
            conf2 = self._call(p, "PlayerCharge", "ConfirmOrder", "com.cmn.inuyasha.gem1000000", ord2["Value"])
            self.assertEqual(conf2["Status"], 0)
            self.assertEqual(int(p.state["player"]["Diamond"]), dia0 + 2_000_000)

    def test_02_timed_exchange_gem_bags_grant_lv6_lv10_lv15_gems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=50, vip_lv=10, source="test_r738")
            p.state["player"]["Diamond"] = 100_000

            info = self._call(p, "TimedLimitExchange", "GetInfo")
            self.assertEqual(info["Status"], 0)
            serials = [int(row["Serial"]) for row in info["Value"]["ActivityList"]]
            self.assertEqual(serials, list(range(1, 31)))

            cases = [
                (13, 500, 16020045, 6),
                (15, 4000, 16020049, 10),
                (17, 30000, 16020057, 15),
            ]
            for ser, cost, bag_mid, expected_lv in cases:
                before_dia = int(p.state["player"]["Diamond"])
                ex = self._call(p, "TimedLimitExchange", "Exchange", 4406, ser, 1)
                self.assertEqual(ex["Status"], 0)
                self.assertEqual(int(p.state["player"]["Diamond"]), before_dia - cost)

                bag_row = next(g for g in p.state["goods"] if int(g["GoodsModelId"]) == bag_mid)
                use = self._call(p, "Goods", "GoodsUse", bag_row["Id"], bag_mid, 1)
                self.assertEqual(use["Status"], 0)
                gems_out = use["Value"]["BaseGetGameResourceList"][0]["Gem"]
                self.assertEqual(len(gems_out), 1)
                self.assertEqual(int(gems_out[0]["ModelId"]) % 100, expected_lv)


if __name__ == "__main__":
    unittest.main()
