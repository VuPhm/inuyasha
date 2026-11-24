#!/usr/bin/env python3
"""Unit and persistence tests for R8.6 Warfare & Warfarespirit (8101-8108)."""

from __future__ import annotations

import random
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT_DIR / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from emulator import GameEmulatorState, _parse_resource_str  # noqa: E402

VN_TZ = timezone(timedelta(hours=7))


def _ts_vn(y: int, m: int, d: int, hh: int = 12, mm: int = 0) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=VN_TZ).timestamp())


class R86WarfareTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None):
        emu = GameEmulatorState(
            data_dir=Path(tmpdir),
            env="dev",
            persist=True,
            trace_path=Path(tmpdir) / "rpc.log",
        )
        if ts is not None:
            emu.clock.set_fixed(ts)
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(prof, method: str, sub: str, *args):
        return prof.handle_rpc({"ServerId": 1, "ModuleName": method, "MethodName": sub, "Data": list(args)})

    def _grant(self, prof, res_tuples, source: str = "test_r86"):
        out = prof._grant_resources_from_tuples(
            res_tuples,
            source=source,
            tx_prefix=f"{source}:{id(res_tuples)}:{random.randint(1, 999999)}",
        )
        prof.save()
        return out

    def _goods_qty(self, prof, mid: int) -> int:
        return sum(int(g.get("Num", 0)) for g in prof.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == mid)

    def test_01_data_configs_modules_and_init_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, prof = self._new_emu(tmp)
            gd = emu.game_data
            for mid in range(8101, 8109):
                self.assertEqual(int(gd["module_subs"][str(mid)]["ifOpen"]), 1)
            self.assertEqual(len(gd["warfare_model"]), 15)
            self.assertEqual(len(gd["warfarespirit_model"]), 108)
            self.assertEqual(len(gd["warfare"]["warfare_lv"]), 15)
            self.assertEqual(sum(len(v) for v in gd["warfare"]["warfare_ref"].values()), 1575)

            prof.admin_prepare_account(target_lv=55, vip_lv=5)
            init_res = self._call(prof, "Player", "GetInitData")
            self.assertEqual(init_res["Status"], 0)
            init = init_res["Value"]
            self.assertEqual(init["WarfarespiritInfo"], [])
            open_mods = {int(m["SubModuleId"]) for m in init["ModulesInfo"] if int(m.get("IfOpen", 0)) == 1}
            for mid in range(8101, 8109):
                self.assertIn(mid, open_mods)
            self.assertEqual(len(init["SlotInfo"][0]["Warfarespirit"]), 6)
            self.assertEqual(init["HeroInfo"][0]["WarfareColorLv"], 0)
            self.assertEqual(init["HeroInfo"][0]["WarfareLv"], 0)

    def test_02_warfare_open_lvup_colorup_and_slot_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=60, vip_lv=5)
            self._grant(prof, [(1201, 12011002, 1)])
            hero = next(h for h in prof.state["heroes"] if int(h["HeroModelId"]) == 12011002)
            hero_id = hero["Id"]
            self.assertEqual(self._call(prof, "Slot", "HeroCombat", 2, hero_id)["Status"], 0)

            wf_tbl = emu.game_data["warfare"]["warfare_lv"]["25010001"]
            cost_tuples: list[tuple[int, int, int]] = []
            for clv in range(1, 8):
                for lv_i in range(10):
                    cost_tuples.extend(_parse_resource_str(str(wf_tbl[str(clv)][str(lv_i)]["LVUpUse"])))
            self._grant(prof, cost_tuples)

            self.assertEqual(self._call(prof, "Warfare", "LvUp", hero_id)["Status"], -1)
            self.assertEqual(self._call(prof, "Warfare", "ColorLvUp", hero_id)["Status"], -1)

            gold_before = int(prof.state["player"]["Gold"])
            opened = self._call(prof, "Warfare", "OpenWarfare", hero_id)
            self.assertEqual(opened["Status"], 0)
            self.assertEqual(opened["Value"]["Hero"]["WarfareColorLv"], 1)
            self.assertEqual(opened["Value"]["Hero"]["WarfareLv"], 0)
            self.assertEqual(int(prof.state["player"]["Gold"]), gold_before - 400_000)

            slot_idx2 = lambda: next(s for s in prof.state["slots"] if s["HeroId"] == hero_id)
            fap0 = int(slot_idx2()["Property"]["FAP"])

            for step in range(9):
                res = self._call(prof, "Warfare", "LvUp", hero_id)
                self.assertEqual(res["Status"], 0)
                self.assertEqual(res["Value"]["Hero"]["WarfareLv"], step + 1)

            self.assertEqual(self._call(prof, "Warfare", "LvUp", hero_id)["Status"], -1)
            prop_c1_lv9 = slot_idx2()["Property"]
            self.assertGreater(int(prop_c1_lv9["FAP"]), fap0)
            self.assertEqual(int(prop_c1_lv9["APHeroR"]), 300)
            self.assertEqual(int(prop_c1_lv9["HPHeroR"]), 450)
            self.assertEqual(int(prop_c1_lv9["DEFHeroR"]), 450)

            c2 = self._call(prof, "Warfare", "ColorLvUp", hero_id)
            self.assertEqual(c2["Status"], 0)
            self.assertEqual(c2["Value"]["Hero"]["WarfareColorLv"], 2)
            self.assertEqual(c2["Value"]["Hero"]["WarfareLv"], 0)
            self.assertGreater(int(slot_idx2()["Property"]["FAP"]), int(prop_c1_lv9["FAP"]))

            for target_clv in range(3, 8):
                for _ in range(9):
                    self.assertEqual(self._call(prof, "Warfare", "LvUp", hero_id)["Status"], 0)
                up = self._call(prof, "Warfare", "ColorLvUp", hero_id)
                self.assertEqual(up["Status"], 0)
                self.assertEqual(up["Value"]["Hero"]["WarfareColorLv"], target_clv)

            self.assertEqual(self._call(prof, "Warfare", "ColorLvUp", hero_id)["Status"], -1)

    def test_03_warfarespirit_decompose_chests_and_sell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=55, vip_lv=5)
            self._grant(prof, [(1615, 16150001, 6), (1615, 16150016, 4), (1606, 16061111, 2), (1602, 16021112, 2)])

            ch_bag = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16061111)
            r_bag = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16021112)
            u_choice = self._call(prof, "Goods", "GoodsUseForBoxChoice", ch_bag["Id"], 16061111, 16150002, 2)
            self.assertEqual(u_choice["Status"], 0)
            self.assertGreaterEqual(self._goods_qty(prof, 16150002), 2)
            u_rand = self._call(prof, "Goods", "GoodsUse", r_bag["Id"], 16021112, 2)
            self.assertEqual(u_rand["Status"], 0)

            c1 = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16150001)
            c2 = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16150016)
            dec = self._call(prof, "Warfarespirit", "DecomposeWarfarcerest", [c1["Id"], c2["Id"]], [6, 4])
            self.assertEqual(dec["Status"], 0)
            self.assertEqual(self._goods_qty(prof, 16150001), 0)
            self.assertEqual(self._goods_qty(prof, 16150016), 0)
            spirits_out = dec["Value"]["BaseGetGameResourceList"][0]["WarfarespiritInfo"]
            self.assertEqual(len(spirits_out), 10)
            self.assertEqual(len(prof.state["warfarespirit"]), 10)

            sell_id = spirits_out[0]["Id"]
            gold_before = int(prof.state["player"]["Gold"])
            sold = self._call(prof, "Warfarespirit", "SpiritSell", [sell_id])
            self.assertEqual(sold["Status"], 0)
            self.assertGreater(int(prof.state["player"]["Gold"]), gold_before)
            self.assertFalse(any(s["Id"] == sell_id for s in prof.state["warfarespirit"]))

    def test_04_warfarespirit_socket_duplicate_type_and_lvup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=60, vip_lv=5)
            self._grant(prof, [(1201, 12011002, 1), (1112, 0, 50_000_000), (1615, 16150001, 60), (1615, 16150016, 60)])
            hero = next(h for h in prof.state["heroes"] if int(h["HeroModelId"]) == 12011002)
            hero_id = hero["Id"]
            self.assertEqual(self._call(prof, "Slot", "HeroCombat", 2, hero_id)["Status"], 0)

            self.assertEqual(self._call(prof, "Warfare", "OpenWarfare", hero_id)["Status"], 0)
            for _ in range(9):
                self.assertEqual(self._call(prof, "Warfare", "LvUp", hero_id)["Status"], 0)
            self.assertEqual(self._call(prof, "Warfare", "ColorLvUp", hero_id)["Status"], 0)
            for _ in range(9):
                self.assertEqual(self._call(prof, "Warfare", "LvUp", hero_id)["Status"], 0)
            self.assertEqual(self._call(prof, "Warfare", "ColorLvUp", hero_id)["Status"], 0)

            self._grant(prof, [(2502, 25020901, 1), (2502, 25020902, 1), (2502, 25021101, 1), (2502, 25020002, 2)])
            sp_ap1, sp_ap2, sp_hp1, exp1, exp2 = prof.state["warfarespirit"]

            self.assertEqual(self._call(prof, "WarfarespiritSlot", "SpiritSlotCombat", hero_id, 1, exp1["Id"])["Status"], -1)
            self.assertEqual(self._call(prof, "WarfarespiritSlot", "SpiritSlotCombat", hero_id, 3, sp_ap1["Id"])["Status"], -1)

            slot_view = lambda: next(s for s in prof.state["slots"] if s["HeroId"] == hero_id)
            fap_base = int(slot_view()["Property"]["FAP"])
            ap_base = int(slot_view()["Property"]["AP"])
            ap2_base = int(slot_view()["Property"]["AP2"])
            self.assertEqual(self._call(prof, "WarfarespiritSlot", "SpiritSlotCombat", hero_id, 1, sp_ap1["Id"])["Status"], 0)
            self.assertGreater(int(slot_view()["Property"]["AP"]), ap_base)
            self.assertGreater(int(slot_view()["Property"]["AP2"]), ap2_base)
            self.assertGreater(int(slot_view()["Property"]["FAP"]), fap_base)
            self.assertEqual(self._call(prof, "WarfarespiritSlot", "SpiritSlotCombat", hero_id, 2, sp_ap2["Id"])["Status"], -1)
            self.assertEqual(self._call(prof, "Warfarespirit", "SpiritSell", [sp_ap1["Id"]])["Status"], -1)

            self.assertEqual(self._call(prof, "WarfarespiritSlot", "SpiritSlotCombat", hero_id, 1, sp_ap2["Id"])["Status"], 0)
            self.assertEqual(self._call(prof, "WarfarespiritSlot", "SpiritSlotCombat", hero_id, 2, sp_hp1["Id"])["Status"], 0)

            fap_pre_up = int(slot_view()["Property"]["FAP"])
            lv_up = self._call(prof, "Warfarespirit", "SpiritLvUp", sp_ap2["Id"], [exp1["Id"], exp2["Id"], sp_ap1["Id"]])
            self.assertEqual(lv_up["Status"], 0)
            self.assertEqual(lv_up["Value"]["Id"], sp_ap2["Id"])
            self.assertGreater(int(lv_up["Value"]["Lv"]), 0)
            self.assertGreater(int(lv_up["Value"]["Exp"]), 0)
            self.assertGreater(int(slot_view()["Property"]["FAP"]), fap_pre_up)
            self.assertEqual(len(prof.state["warfarespirit"]), 2)

            fap_pre_un = int(slot_view()["Property"]["FAP"])
            self.assertEqual(self._call(prof, "WarfarespiritSlot", "SpiritSlotUnCombat", hero_id, 2, sp_hp1["Id"])["Status"], 0)
            self.assertEqual(slot_view()["Warfarespirit"][1], {})
            self.assertLess(int(slot_view()["Property"]["FAP"]), fap_pre_un)

    def test_05_nightmare_drops_timed_exchange_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, prof = self._new_emu(tmp, ts=_ts_vn(2026, 11, 1, 12, 0))
            prof.admin_prepare_account(target_lv=60, vip_lv=5)
            prof.state["player"]["Diamond"] = 50_000
            self._grant(prof, [(1102, 0, 500), (1112, 0, 5_000_000), (1615, 16150001, 5)])

            nm = prof._nightmare_state()
            nm["nodes"]["1115"] = prof._make_node_state(1115, flag=1)
            f_res = self._call(prof, "Nightmare", "Fight", 11, 1115, 3, True)
            self.assertEqual(f_res["Status"], 0)
            self.assertGreaterEqual(self._goods_qty(prof, 16061111), 1)

            seen_s29: set[int] = set()
            for day_off in range(7):
                emu.clock.set_fixed(_ts_vn(2026, 11, 1 + day_off, 12, 0))
                info = self._call(prof, "TimedLimitExchange", "GetInfo")["Value"]
                by_ser = {int(r["Serial"]): r for r in info["ActivityList"]}
                self.assertEqual(sorted(by_ser.keys()), list(range(1, 31)))
                seen_s29.add(int(by_ser[29]["ExchaneGameResourceList"][0]["ModelId"]))
            self.assertEqual(seen_s29, {16061111, 16061112, 16061106, 16061107, 16061108, 16061109, 16061110})

            self.assertEqual(self._call(prof, "TimedLimitExchange", "Exchange", 29, 1)["Status"], 0)
            self.assertEqual(self._call(prof, "TimedLimitExchange", "Exchange", 30, 1)["Status"], 0)
            self.assertGreaterEqual(self._goods_qty(prof, 16050086), 5)

            self._grant(prof, [(1201, 12011002, 1), (1615, 16150001, 50), (1615, 16150016, 10), (2502, 25021101, 1)])
            hero = next(h for h in prof.state["heroes"] if int(h["HeroModelId"]) == 12011002)
            hid = hero["Id"]
            self.assertEqual(self._call(prof, "Slot", "HeroCombat", 2, hid)["Status"], 0)
            self.assertEqual(self._call(prof, "Warfare", "OpenWarfare", hid)["Status"], 0)
            for _ in range(9):
                self.assertEqual(self._call(prof, "Warfare", "LvUp", hid)["Status"], 0)
            self.assertEqual(self._call(prof, "Warfare", "ColorLvUp", hid)["Status"], 0)
            sp_id = next(s["Id"] for s in prof.state["warfarespirit"] if int(s["ModelId"]) == 25021101)
            self.assertEqual(self._call(prof, "WarfarespiritSlot", "SpiritSlotCombat", hid, 1, sp_id)["Status"], 0)

            emu2 = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True, trace_path=Path(tmp) / "rpc.log")
            prof2 = emu2.profiles["normal"]
            h2 = next(h for h in prof2.state["heroes"] if h["Id"] == hid)
            self.assertEqual(int(h2["WarfareColorLv"]), 2)
            s2 = next(s for s in prof2.state["slots"] if s["HeroId"] == hid)
            self.assertEqual(s2["Warfarespirit"][0]["Id"], sp_id)


if __name__ == "__main__":
    unittest.main()
