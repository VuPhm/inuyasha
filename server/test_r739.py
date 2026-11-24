"""Delta coverage for R7.39: P4-A4 Luyện Thể (Lianti, ModuleSub 5700) + LiantiDashi + Shop + Rebirth."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
import sys
import tempfile
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import EMPTY_ENTITY_ID, GameEmulatorState  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R739LiantiTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 24, 15, 30))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    @staticmethod
    def _goods_qty(prof: Any, mid: int) -> int:
        return sum(int(g.get("Num", 0)) for g in prof.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == mid)

    def test_01_init_data_module_5700_and_hero_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=40, vip_lv=5, source="test_r739")
            init = self._call(p, "Player", "GetInitData")
            self.assertEqual(init["Status"], 0)
            mods = {int(m["SubModuleId"]): int(m["IfOpen"]) for m in init["Value"]["ModulesInfo"]}
            self.assertEqual(mods.get(5700), 1)
            self.assertEqual(int(init["Avatar"]["LiantiDashiStep"]), 0)
            for hero in init["Value"]["HeroInfo"]:
                self.assertEqual(int(hero["LiantiLv"]), 0)
                self.assertEqual(int(hero["LianTiNodeId"]), 1)
                self.assertEqual(int(hero["LianTiNodeExp"]), 0)
                self.assertEqual(int(hero["LvUpExp"]), 130)

    def test_02_level_gate_inline_shop_and_timed_exchange_serial_18(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            hero1 = p.state["heroes"][0]
            p._grant_resources_from_tuples([(1605, 16050035, 5), (1112, 0, 50_000)], source="seed", tx_prefix="seed_r739_02")
            gated = self._call(p, "Lianti", "Lianti", hero1["Id"], 16050035)
            self.assertEqual(gated["Status"], -1)

            p.admin_prepare_account(target_lv=40, vip_lv=5, source="test_r739")
            p.state["player"]["Diamond"] = 50_000

            for gid, expected_price in ((16050035, 10), (16050036, 25), (16050037, 60), (16050038, 200)):
                info = self._call(p, "ShopGoods", "GetShopGoodsInfo", gid)
                self.assertEqual(info["Status"], 0)
                entry = info["Value"][0]
                self.assertEqual(int(entry["GoodsModelId"]), gid)
                self.assertEqual(int(entry["SellTypeId"]), 1111)
                self.assertEqual(int(entry["CurrPrice"]), expected_price)
                self.assertEqual(int(entry["MaxNum"]), -1)

            before_dia = int(p.state["player"]["Diamond"])
            buy = self._call(p, "ShopGoods", "BuyGoods", 16050038, 3)
            self.assertEqual(buy["Status"], 0)
            self.assertEqual(int(p.state["player"]["Diamond"]), before_dia - 600)
            self.assertEqual(self._goods_qty(p, 16050038), 3)

            ex_info = self._call(p, "TimedLimitExchange", "GetInfo")
            self.assertEqual(ex_info["Status"], 0)
            self.assertEqual([int(r["Serial"]) for r in ex_info["Value"]["ActivityList"]], list(range(1, 31)))

            ex = self._call(p, "TimedLimitExchange", "Exchange", 4406, 18, 1)
            self.assertEqual(ex["Status"], 0)
            self.assertEqual(int(p.state["player"]["Diamond"]), before_dia - 2600)
            self.assertEqual(self._goods_qty(p, 16050038), 53)

    def test_03_single_one_key_stat_bonus_and_dashi_piggyback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=50, vip_lv=10, source="test_r739")
            seeded = p._grant_resources_from_tuples(
                [(1201, m, 1) for m in (12011002, 12011003, 12011004, 12012003, 12012004)]
                + [(1605, 16050035, 10), (1605, 16050038, 500), (1112, 0, 10_000_000)],
                source="seed_team",
                tx_prefix="seed_r739_03",
            )
            p._recalc_all_slots_and_fap()
            init = self._call(p, "Player", "GetInitData")
            self.assertEqual(int(init["Avatar"]["LiantiDashiStep"]), 0)

            extra_heroes = seeded[0]["Hero"]
            for idx, h in enumerate(extra_heroes, start=2):
                res = self._call(p, "Slot", "HeroCombat", idx, h["Id"])
                self.assertEqual(res["Status"], 0)

            main_hero = p.state["heroes"][0]
            slot1_before = dict(p.state["slots"][0]["Property"])
            fap_before = int(p.state["player"]["FAP"])
            gold_before = int(p.state["player"]["Gold"])

            # Single upgrade with 16050035 (cost 1000 Gold, +5..15 exp)
            up1 = self._call(p, "Lianti", "Lianti", main_hero["Id"], 16050035)
            self.assertEqual(up1["Status"], 0)
            li1 = up1["Value"]["LiantiInfo"]
            self.assertGreaterEqual(int(li1["LianTiNodeExp"]), 5)
            self.assertLessEqual(int(li1["LianTiNodeExp"]), 15)
            self.assertEqual(self._goods_qty(p, 16050035), 9)
            self.assertEqual(int(p.state["player"]["Gold"]), gold_before - 1000)

            # Long-press batch OneKeyLianti with 16050038 (+300 x 4 = +1200 exp -> wraps to >= Lv 1)
            stones38_before = self._goods_qty(p, 16050038)
            ok = self._call(p, "Lianti", "OneKeyLianti", main_hero["Id"], 16050038, [300, 300, 300, 300], "ignored")
            self.assertEqual(ok["Status"], 0)
            self.assertEqual(self._goods_qty(p, 16050038), stones38_before - 4)
            new_lv = int(ok["Value"]["LiantiInfo"]["LiantiLv"])
            self.assertGreaterEqual(new_lv, 1)

            lv_row = p.game_data["lianti_lv"][str(new_lv)]
            slot1_after = p.state["slots"][0]["Property"]
            self.assertGreater(int(p.state["player"]["FAP"]), fap_before)
            self.assertGreater(int(slot1_after["HP"]), int(slot1_before["HP"]))
            self.assertGreater(int(slot1_after["AP"]), int(slot1_before["AP"]))
            self.assertGreater(int(slot1_after["DEF"]), int(slot1_before["DEF"]))
            self.assertEqual(int(slot1_after["DAMADD"]), int(slot1_before["DAMADD"]) + int(lv_row["DAMADD"]))
            self.assertEqual(int(slot1_after["DAMCUT"]), int(slot1_before["DAMCUT"]) + int(lv_row["DAMCUT"]))

            # Upgrade all 6 deployed heroes to LiantiLv >= 5 -> triggers LiantiDashiStep = 1 (+100 DAMADDR/DAMCUTR)
            damaddr_before_dashi = int(p.state["slots"][0]["Property"]["DAMADDR"])
            deployed_ids = [s["HeroId"] for s in p.state["slots"][:6]]
            last_res = None
            for hid in deployed_ids:
                h_obj = next(h for h in p.state["heroes"] if h["Id"] == hid)
                while int(h_obj["LiantiLv"]) < 5:
                    last_res = self._call(p, "Lianti", "OneKeyFiveLvLianti", hid)
                    self.assertEqual(last_res["Status"], 0)

            self.assertIsNotNone(last_res)
            self.assertEqual(int(last_res["Avatar"]["LiantiDashiStep"]), 1)
            self.assertEqual(int(p.state["slots"][0]["Property"]["DAMADDR"]), damaddr_before_dashi + 100)
            self.assertEqual(int(p.state["slots"][0]["Property"]["DAMCUTR"]), damaddr_before_dashi + 100)

            # Removing Slot 6 hero drops LiantiDashiStep to 0 and piggybacks 0
            rem = self._call(p, "Slot", "HeroCombat", 6, EMPTY_ENTITY_ID)
            self.assertEqual(rem["Status"], 0)
            self.assertEqual(int(rem["Avatar"]["LiantiDashiStep"]), 0)
            self.assertEqual(int(p.state["slots"][0]["Property"]["DAMADDR"]), damaddr_before_dashi)

            # Re-deploying restores step 1
            readd = self._call(p, "Slot", "HeroCombat", 6, deployed_ids[5])
            self.assertEqual(readd["Status"], 0)
            self.assertEqual(int(readd["Avatar"]["LiantiDashiStep"]), 1)

    def test_04_max_lv_81_cap_and_hero_rebirth_refund(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=50, vip_lv=10, source="test_r739")
            seeded = p._grant_resources_from_tuples(
                [(1201, 12011002, 1), (1605, 16050038, 15_000), (1112, 0, 100_000_000)],
                source="seed_max",
                tx_prefix="seed_r739_04",
            )
            side_id = seeded[0]["Hero"][0]["Id"]
            side = next(h for h in p.state["heroes"] if h["Id"] == side_id)
            stones_start = self._goods_qty(p, 16050038)
            gold_start = int(p.state["player"]["Gold"])

            guard = 0
            while int(side["LiantiLv"]) < 81 and guard < 25:
                res = self._call(p, "Lianti", "OneKeyFiveLvLianti", side["Id"])
                self.assertEqual(res["Status"], 0)
                guard += 1

            self.assertEqual(int(side["LiantiLv"]), 81)
            self.assertEqual(int(side["LianTiNodeId"]), 5)
            self.assertEqual(int(side["LvUpExp"]), 100)
            self.assertEqual(int(side["LianTiNodeExp"]), 100)

            for fn, extra in (("Lianti", [16050038]), ("OneKeyLianti", [16050038, [300], "x"]), ("OneKeyFiveLvLianti", [])):
                cap_res = self._call(p, "Lianti", fn, side["Id"], *extra)
                self.assertEqual(cap_res["Status"], -1)

            stones_spent = stones_start - self._goods_qty(p, 16050038)
            gold_spent = gold_start - int(p.state["player"]["Gold"])
            self.assertGreater(stones_spent, 0)
            self.assertEqual(gold_spent, stones_spent * 4000)

            rb = self._call(p, "Hero", "HeroRebirth", side["Id"])
            self.assertEqual(rb["Status"], 0)
            self.assertEqual(int(side["LiantiLv"]), 0)
            self.assertEqual(int(side["LianTiNodeId"]), 1)
            self.assertEqual(int(side["LianTiNodeExp"]), 0)
            self.assertEqual(int(side["LvUpExp"]), 130)
            self.assertEqual(self._goods_qty(p, 16050038), stones_start)
            self.assertEqual(int(p.state["player"]["Gold"]), gold_start)


if __name__ == "__main__":
    unittest.main()
