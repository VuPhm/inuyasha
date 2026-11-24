"""Delta coverage for R7.36: VIP Mate slots 9-12, cascading Gem compose & unequip, proactive daily shop resets."""

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


class R736MateGemAndDailyShopResetTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 24, 12, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    def test_01_vip_mate_slots_9_to_12_unlock_combat_bonds_and_cheer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=50, vip_lv=0, source="test_r736")
            p.state["player"]["StarId"] = 348  # Star slots 1-8 open; VIP slots 9-12 still locked at VIP 0
            p.state["player"]["Vip"] = 0

            # Pick 4 distinct orange heroes not currently deployed
            deployed_mids = {int(s["HeroModelId"]) for s in p.state["slots"] if s.get("HeroModelId")}
            extra_heroes = []
            for hmid in (12011002, 12011003, 12011004, 12011005, 12011006, 12011007):
                if hmid in deployed_mids:
                    continue
                res = p._grant_resources_from_tuples([(1201, hmid, 1)], source="test_r736", tx_prefix=f"r736:h:{hmid}")
                extra_heroes.append(res[0]["Hero"][0])
                if len(extra_heroes) == 4:
                    break
            self.assertEqual(len(extra_heroes), 4)

            # Slot 9 requires VIP 1 -> rejected with -1127 at VIP 0
            r_locked = self._call(p, "Slot", "MateinfoCombat", 9, extra_heroes[0]["Id"])
            self.assertEqual(r_locked["Status"], -1127)

            # VIP threshold check: 9->VIP1, 10->VIP5, 11->VIP12, 12->VIP14
            for slot_id, req_vip, hero in zip((9, 10, 11, 12), (1, 5, 12, 14), extra_heroes):
                p.state["player"]["Vip"] = req_vip - 1
                self.assertEqual(self._call(p, "Slot", "MateinfoCombat", slot_id, hero["Id"])["Status"], -1127)
                p.state["player"]["Vip"] = req_vip
                ok = self._call(p, "Slot", "MateinfoCombat", slot_id, hero["Id"])
                self.assertEqual(ok["Status"], 0)
                self.assertEqual(ok["Value"]["MateInfo"][0]["SlotId"], slot_id)
                self.assertEqual(ok["Value"]["MateInfo"][0]["HeroId"], hero["Id"])

            mate_ids = {int(m["SlotId"]) for m in p._mate_slot_info()}
            self.assertEqual(mate_ids, {9, 10, 11, 12})

            # Persistence across reload preserves MateInfos 9-12
            reloaded = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True, trace_path=Path(tmp) / "rpc2.log")
            reloaded.clock.set_fixed(_ts_vn(2026, 11, 24, 12, 0))
            rp = reloaded.profiles["normal"]
            self.assertEqual({int(m["SlotId"]) for m in rp._mate_slot_info()}, {9, 10, 11, 12})

            # Removing mate from slot 12 clears it cleanly
            rem = self._call(rp, "Slot", "MateinfoCombat", 12, EMPTY_ENTITY_ID)
            self.assertEqual(rem["Status"], 0)
            self.assertEqual({int(m["SlotId"]) for m in rp._mate_slot_info()}, {9, 10, 11})

    def test_02_gem_one_key_compose_cascades_and_socket_unequip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=50, vip_lv=3, source="test_r736")
            p.state["player"]["Gold"] = 5_000_000
            p.state["gems"] = []
            for s in p.state["slots"]:
                s["Gem"] = [{}, {}, {}, {}, {}, {}]

            # Grant 16x LV1 gems (20001001): 16x LV1 -> 4x LV2 -> 1x LV3 (20001003)
            p._grant_resources_from_tuples([(2000, 20001001, 16)], source="test_r736", tx_prefix="r736:gem16")
            initial_ids = {g["Id"] for g in p.state["gems"]}
            self.assertEqual(len(initial_ids), 16)

            comp = self._call(p, "Gem", "GemOneKeyCompose")
            self.assertEqual(comp["Status"], 0)
            self.assertEqual(set(comp["Value"]["ConsumeList"]), initial_ids)
            created = comp["Value"]["BaseGetGameResourceList"][0]["Gem"]
            self.assertEqual(len(created), 1)
            self.assertEqual(int(created[0]["ModelId"]), 20001003)
            self.assertEqual(len(p.state["gems"]), 1)
            lv3_id = p.state["gems"][0]["Id"]

            # Socket LV3 gem into slot 1 socket 1 -> FAP increases -> unequip via EMPTY_ENTITY_ID -> FAP returns
            fap_base = int(p.state["player"]["FAP"])
            sock = self._call(p, "Slot", "GemCombat", 1, 1, lv3_id)
            self.assertEqual(sock["Status"], 0)
            self.assertGreater(int(p.state["player"]["FAP"]), fap_base)

            unequip = self._call(p, "Slot", "GemCombat", 1, 1, EMPTY_ENTITY_ID)
            self.assertEqual(unequip["Status"], 0)
            self.assertEqual(unequip["Value"]["SlotInfo"][0]["Gem"][0], {})
            self.assertEqual(int(p.state["player"]["FAP"]), fap_base)

            # Max LV15 gem compose is cleanly rejected (-1321)
            p._grant_resources_from_tuples([(2000, 20001015, 4)], source="test_r736", tx_prefix="r736:gem15")
            lv15_ids = [g["Id"] for g in p.state["gems"] if int(g["ModelId"]) == 20001015]
            self.assertEqual(self._call(p, "Gem", "GemCompose", lv15_ids)["Status"], -1321)

    def test_03_proactive_daily_shop_resets_mystery_pvp_and_guild(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=40, vip_lv=3, source="test_r736")
            p.state["player"]["Diamond"] = 50_000
            p.state["player"]["HeroCoin"] = 50_000
            p.state["player"]["Gold"] = 5_000_000
            p.state["player"]["PVPCoin"] = 50_000
            p.state["player"]["Contribution"] = 50_000

            # 1. MysteryShop: buy first item + burn free refresh -> ResetDaily restores GoldCount=0 & IsSell=0
            ms0 = self._call(p, "MysteryShop", "GetInfo")["Value"]
            first_id = ms0["MysteryShopGoodsList"][0]["Id"]
            self.assertEqual(self._call(p, "MysteryShop", "MysteryShopBuyGoods", first_id)["Status"], 0)
            self.assertEqual(self._call(p, "MysteryShop", "RefreshtGoodsList", 3)["Status"], 0)
            ms_reset = self._call(p, "MysteryShop", "ResetDaily", 0)
            self.assertEqual(ms_reset["Status"], 0)
            self.assertEqual(ms_reset["Value"]["GoldCount"], 0)
            self.assertGreater(ms_reset["Value"]["FreeCount"], 0)
            self.assertTrue(all(int(x["IsSell"]) == 0 for x in ms_reset["Value"]["MysteryShopGoodsList"]))

            # 2. PVPShop: buy daily item (#2 VIT pill perMax=1) and total item (#11 one-time if available or find one)
            pvp_shop_cfg = p.game_data["pvp_shop"]
            daily_sid = next(int(k) for k, v in pvp_shop_cfg.items() if int(v.get("perMaxNum", 0)) > 0)
            daily_per = int(pvp_shop_cfg[str(daily_sid)]["perMaxNum"])
            self.assertEqual(self._call(p, "PVPShop", "PVPShopBuy", daily_sid, daily_per)["Status"], 0)
            self.assertEqual(self._call(p, "PVPShop", "PVPShopBuy", daily_sid, 1)["Status"], -1)
            total_sid = next(
                (int(k) for k, v in pvp_shop_cfg.items() if int(v.get("totalMaxNum", 0)) > 0 and int(v.get("needRank", 0)) == 0),
                None,
            )
            if total_sid is not None:
                p.state["player"]["Lv"] = 80
                self._call(p, "PVPShop", "PVPShopBuy", total_sid, 1)

            pvp_reset = self._call(p, "PVPShop", "ResetDaily")
            self.assertEqual(pvp_reset["Status"], 0)
            by_sid = {int(r["ShopId"]): r for r in pvp_reset["Value"]["PVPShopList"]}
            self.assertEqual(by_sid[daily_sid]["BuyNum"], 0)
            if total_sid is not None:
                self.assertEqual(by_sid[total_sid]["BuyTotalNum"], 1)
            self.assertEqual(self._call(p, "PVPShop", "PVPShopBuy", daily_sid, 1)["Status"], 0)

            # 3. GuildShop: create guild, buy daily item to cap, ResetGuildShopDaily clears BuyNum while preserving shop_total
            self.assertEqual(self._call(p, "Guild", "CreateGuild", "Konoha", 1)["Status"], 0)
            gs_cfg = p.game_data["guild_shop"]
            g_daily_sid = next(int(k) for k, v in gs_cfg.items() if int(v.get("perMaxNum", 0)) > 0 and int(v.get("needBuildingLV", 1)) == 1)
            g_per = int(gs_cfg[str(g_daily_sid)]["perMaxNum"])
            self.assertEqual(self._call(p, "Guild", "GuildShopBuy", g_daily_sid, g_per)["Status"], 0)
            self.assertEqual(self._call(p, "Guild", "GuildShopBuy", g_daily_sid, 1)["Status"], -3420)
            g_reset = self._call(p, "Guild", "ResetGuildShopDaily")
            self.assertEqual(g_reset["Status"], 0)
            g_by_sid = {int(r["Id"]): r for r in g_reset["Value"]["GuildShopInfo"]}
            self.assertEqual(g_by_sid[g_daily_sid]["BuyNum"], 0)
            self.assertEqual(self._call(p, "Guild", "GuildShopBuy", g_daily_sid, 1)["Status"], 0)


if __name__ == "__main__":
    unittest.main()
