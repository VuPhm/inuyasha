"""Delta coverage for R7.33 (REC-P3-04A): 8/8 TimedWelfare (4413..4420) & RankScene Tab 3 PVPinter."""

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


class R733WelfareAndCrossServerRankTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 22, 12, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    @staticmethod
    def _prepare_strong_squad(p: Any, target_lv: int = 60, vip_lv: int = 5) -> None:
        p.admin_prepare_account(target_lv=target_lv, vip_lv=vip_lv, source="test_r733")
        p.state["player"].update(Diamond=20_000, Gold=20_000_000, STA=200, HeroEXP=5_000_000)
        res = p._grant_resources_from_tuples(
            [
                (1201, 12011004, 1),
                (1201, 12012005, 1),
                (1201, 12013004, 1),
                (1301, 13010602, 4),
                (1302, 13020602, 4),
                (1303, 13030602, 4),
                (1304, 13040602, 4),
            ],
            source="test_r733",
            tx_prefix="setup",
        )
        heroes = res[0]["Hero"]
        by_type = {t: [e for e in res[0]["Equip"] if int(e["EquipModelId"]) == mid] for t, mid in (
            ("w", 13010602), ("h", 13020602), ("c", 13030602), ("n", 13040602)
        )}
        p.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [p.state["heroes"][0]["Id"], target_lv]})
        for idx, h in enumerate(heroes, start=2):
            p.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
            p.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [h["Id"], target_lv]})
        for slot_idx in range(1, 5):
            p.handle_rpc(
                {
                    "ModuleName": "Slot",
                    "MethodName": "OneKeyEquipCombat",
                    "Data": [
                        slot_idx,
                        by_type["w"][slot_idx - 1]["Id"],
                        by_type["h"][slot_idx - 1]["Id"],
                        by_type["c"][slot_idx - 1]["Id"],
                        by_type["n"][slot_idx - 1]["Id"],
                        "",
                        "",
                    ],
                }
            )
        p._recalc_all_slots_and_fap()
        p.save()

    def test_01_all_eight_timed_welfare_exposed_and_client_refnum_formats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=30, vip_lv=3, source="test_r733")
            welfare_ids = [
                "timed_welfare_jjc",
                "timed_welfare_dwdh",
                "timed_welfare_ycjk",
                "timed_welfare_equip",
                "timed_welfare_hero",
                "timed_welfare_equip_compose_crit",
                "timed_welfare_equip_crit",
                "timed_welfare_bdd",
            ]
            p.event_runtime.configure_archive_mode("concurrent", concurrent_events=welfare_ids)
            init = self._call(emu, "Player", "GetInitData")
            self.assertEqual(init["Status"], 0)
            open_info = init["Avatar"]["TimedActivityOpenInfo"]
            expected = {
                "4413": 2,
                "4414": 2,
                "4415": 200,
                "4416": 80,
                "4417": 80,
                "4418": "3,6,10,15",
                "4419": "3,6,10,15",
                "4420": 2,
            }
            for mod_key, ref_val in expected.items():
                self.assertIn(mod_key, open_info)
                self.assertEqual(open_info[mod_key][0]["ExtraInfo"]["RefNum"], ref_val)
            self.assertEqual(p._ggzj_welfare_mult(), 2)
            self.assertEqual(p._timed_welfare_qualities(4418), {3, 6, 10, 15})
            self.assertEqual(p._timed_welfare_qualities(4419), {3, 6, 10, 15})

    def test_02_welfare_4413_arena_pvpcoin_doubled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_off, tempfile.TemporaryDirectory() as tmp_on:
            emu_off, p_off = self._new_emu(tmp_off)
            emu_on, p_on = self._new_emu(tmp_on)
            self._prepare_strong_squad(p_off, target_lv=55, vip_lv=3)
            self._prepare_strong_squad(p_on, target_lv=55, vip_lv=3)
            p_on.event_runtime.activate_manual_event("timed_welfare_jjc", duration_sec=3600)

            info_off = self._call(emu_off, "PVP", "GetPVPInfo")["Value"]
            info_on = self._call(emu_on, "PVP", "GetPVPInfo")["Value"]
            target_off = max((x for x in info_off["RankList"] if x["IfAllowRank"] == 1), key=lambda x: x["Rank"])
            target_on = max((x for x in info_on["RankList"] if x["IfAllowRank"] == 1), key=lambda x: x["Rank"])
            self.assertEqual(target_off["Rank"], target_on["Rank"])

            before_off = int(p_off.state["player"]["PVPCoin"])
            before_on = int(p_on.state["player"]["PVPCoin"])
            res_off = self._call(emu_off, "PVP", "PVPFight", target_off["PlayerId"], target_off["Rank"])
            res_on = self._call(emu_on, "PVP", "PVPFight", target_on["PlayerId"], target_on["Rank"])
            self.assertEqual(res_off["Status"], 0)
            self.assertEqual(res_on["Status"], 0)
            self.assertEqual(res_off["Value"]["IsWinFight"], 1)
            self.assertEqual(res_on["Value"]["IsWinFight"], 1)

            gain_off = int(p_off.state["player"]["PVPCoin"]) - before_off
            gain_on = int(p_on.state["player"]["PVPCoin"]) - before_on
            self.assertEqual(gain_on, gain_off * 2)

            reloaded_on = GameEmulatorState(data_dir=Path(tmp_on), env="dev", persist=True, trace_path=Path(tmp_on) / "rpc2.log")
            self.assertEqual(int(reloaded_on.profiles["normal"].state["player"]["PVPCoin"]), before_on + gain_on)

    def test_03_welfare_4415_ggzj_200_pct_and_4419_callequip_quality_crit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_off, tempfile.TemporaryDirectory() as tmp_on:
            emu_off, p_off = self._new_emu(tmp_off)
            emu_on, p_on = self._new_emu(tmp_on)
            self._prepare_strong_squad(p_off, target_lv=50, vip_lv=0)
            self._prepare_strong_squad(p_on, target_lv=50, vip_lv=0)
            p_off.event_runtime.configure_archive_mode("scheduled", scheduled_windows={})
            p_on.event_runtime.configure_archive_mode(
                "concurrent",
                concurrent_events=["timed_welfare_ycjk", "timed_welfare_equip_crit"],
            )

            self.assertEqual(p_off._ggzj_welfare_mult(), 1)
            self.assertEqual(p_on._ggzj_welfare_mult(), 2)

            gold_before_off = int(p_off.state["player"]["Gold"])
            gold_before_on = int(p_on.state["player"]["Gold"])
            f_off = self._call(emu_off, "GGZJ", "Fight", True, "", True)
            f_on = self._call(emu_on, "GGZJ", "Fight", True, "", True)
            self.assertEqual((f_off["Status"], f_on["Status"]), (0, 0))
            self.assertEqual(
                int(p_on.state["player"]["Gold"]) - gold_before_on,
                (int(p_off.state["player"]["Gold"]) - gold_before_off) * 2,
            )

            # 4419 with RefNum="3,6,10,15" doubles all 10 pulled Callequip items -> 20 equips
            r_crit = self._call(emu_on, "Callequip", "CallEquip", 10, 3)
            self.assertEqual(r_crit["Status"], 0)
            self.assertEqual(len(r_crit["Value"]["BaseGetGameResourceList"][0]["Equip"]), 20)

            # Non-matching quality set yields no crit doubling (10 equips)
            p_on.event_runtime.registry["timed_welfare_equip_crit"].metadata["extra_info"]["RefNum"] = "99"
            try:
                r_no_crit = self._call(emu_on, "Callequip", "CallEquip", 10, 3)
                self.assertEqual(r_no_crit["Status"], 0)
                self.assertEqual(len(r_no_crit["Value"]["BaseGetGameResourceList"][0]["Equip"]), 10)
            finally:
                p_on.event_runtime.registry["timed_welfare_equip_crit"].metadata["extra_info"]["RefNum"] = "3,6,10,15"

    def test_04_welfare_4418_equip_compose_and_one_key_crit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=30, vip_lv=2, source="test_r733")
            p.state["player"]["Gold"] = 5_000_000
            p.event_runtime.configure_archive_mode("scheduled", scheduled_windows={})

            granted = p._grant_resources_from_tuples(
                [(1304, 13040130, 5), (1301, 13010130, 10)],
                source="test_r733",
                tx_prefix="eq_grant",
            )[0]["Equip"]
            necks = [e["Id"] for e in granted if int(e["EquipModelId"]) == 13040130]
            weps = [e["Id"] for e in granted if int(e["EquipModelId"]) == 13010130]

            # Inactive 4418: 5 white necks -> 1 green neck (13040215)
            c1 = self._call(emu, "Equip", "EquipCompose", necks)
            self.assertEqual(c1["Status"], 0)
            self.assertEqual(len(c1["Value"]["BaseGetGameResourceList"][0]["Equip"]), 1)

            # Activate 4418 (RefNum="3,6,10,15"): both EquipCompose & EquipOneKeyCompose double output
            p.event_runtime.activate_manual_event("timed_welfare_equip_compose_crit", duration_sec=3600)
            c2 = self._call(emu, "Equip", "EquipCompose", weps[:5])
            self.assertEqual(c2["Status"], 0)
            out2 = c2["Value"]["BaseGetGameResourceList"][0]["Equip"]
            self.assertEqual(len(out2), 2)
            self.assertTrue(all(int(eq["EquipModelId"]) == 13010215 for eq in out2))

            c3 = self._call(emu, "Equip", "EquipOneKeyCompose")
            self.assertEqual(c3["Status"], 0)
            out3 = c3["Value"]["BaseGetGameResourceList"][0]["Equip"]
            self.assertEqual(len(out3), 2)
            self.assertTrue(all(int(eq["EquipModelId"]) == 13010215 for eq in out3))

            expected_green_weps = sum(1 for eq in p.state["equips"] if int(eq["EquipModelId"]) == 13010215)
            self.assertGreaterEqual(expected_green_weps, 4)

            reloaded = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True, trace_path=Path(tmp) / "rpc2.log")
            reloaded_green = sum(
                1 for eq in reloaded.profiles["normal"].state["equips"] if int(eq["EquipModelId"]) == 13010215
            )
            self.assertEqual(reloaded_green, expected_green_weps)

    def test_05_welfare_4420_bdd_fight_and_sweep_double_merit_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_off, tempfile.TemporaryDirectory() as tmp_on:
            emu_off, p_off = self._new_emu(tmp_off)
            emu_on, p_on = self._new_emu(tmp_on)
            self._prepare_strong_squad(p_off, target_lv=60, vip_lv=4)
            self._prepare_strong_squad(p_on, target_lv=60, vip_lv=4)
            p_off.event_runtime.configure_archive_mode("scheduled", scheduled_windows={})
            p_on.event_runtime.activate_manual_event("timed_welfare_bdd", duration_sec=3600)

            self._call(emu_off, "BddInfo", "Info")
            self._call(emu_on, "BddInfo", "Info")

            # Node 1111 @ difficulty 3: nationalDrop=1124*30 (doubled under 4420), firstPassDrop=1111*50 (NOT doubled)
            dia_off0, mer_off0 = int(p_off.state["player"]["Diamond"]), int(p_off.state["player"].get("Merit", 0))
            dia_on0, mer_on0 = int(p_on.state["player"]["Diamond"]), int(p_on.state["player"].get("Merit", 0))

            t_off = self._call(emu_off, "BddInfo", "GetFightInfo", 1111, 3)["Value"]["FightToken"]
            t_on = self._call(emu_on, "BddInfo", "GetFightInfo", 1111, 3)["Value"]["FightToken"]
            w_off = self._call(emu_off, "BddInfo", "Fight", 1111, 3, True, "", {}, t_off)["Value"]
            w_on = self._call(emu_on, "BddInfo", "Fight", 1111, 3, True, "", {}, t_on)["Value"]
            self.assertTrue(w_off["IsSuccess"])
            self.assertTrue(w_on["IsSuccess"])

            self.assertEqual(int(p_off.state["player"]["Diamond"]) - dia_off0, 50)
            self.assertEqual(int(p_on.state["player"]["Diamond"]) - dia_on0, 50)
            self.assertEqual(int(p_off.state["player"]["Merit"]) - mer_off0, 30)
            self.assertEqual(int(p_on.state["player"]["Merit"]) - mer_on0, 60)

            # Finish floor 11 on both p_off & p_on, reset, and test OneKeyThreeStar under 4420 (fight Merit 2x, box Merit unchanged)
            for emu_x, prof_x in ((emu_off, p_off), (emu_on, p_on)):
                for node in (1112, 1113):
                    tok = self._call(emu_x, "BddInfo", "GetFightInfo", node, 3)["Value"]["FightToken"]
                    r = self._call(emu_x, "BddInfo", "Fight", node, 3, True, "", {}, tok)["Value"]
                    self.assertTrue(r["IsSuccess"])
                self.assertEqual(self._call(emu_x, "BddInfo", "RewardBox", 11, 9)["Status"], 0)
                offer = self._call(emu_x, "BddInfo", "GetBuffs")["Value"][0]
                self.assertEqual(self._call(emu_x, "BddInfo", "SelectBuff", offer["Id"])["Status"], 0)
                for row in prof_x.game_data["bdd"]["nodes"].values():
                    if int(row["floorModelID"]) in range(12, 28):
                        prof_x.state["bdd"]["stars"][str(row["ID"])] = 1
                self.assertEqual(self._call(emu_x, "BddInfo", "Reset")["Status"], 0)

            mer_off_sweep0 = int(p_off.state["player"]["Merit"])
            mer_on_sweep0 = int(p_on.state["player"]["Merit"])
            sweep_off = self._call(emu_off, "BddInfo", "OneKeyThreeStar")
            sweep_on = self._call(emu_on, "BddInfo", "OneKeyThreeStar")
            self.assertEqual((sweep_off["Status"], sweep_on["Status"]), (0, 0))
            box_merit = sum(rn for rt, _rm, rn in p_on._bdd_box(11, 9) if rt == 1124)
            self.assertEqual(int(p_off.state["player"]["Merit"]) - mer_off_sweep0, 90 + box_merit)
            self.assertEqual(int(p_on.state["player"]["Merit"]) - mer_on_sweep0, 180 + box_merit)

    def test_06_pvpinter_cross_server_leaderboard_and_formations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu = GameEmulatorState(persist=True, data_dir=Path(tmp), env="dev", trace_path=Path(tmp) / "rpc.log")
            emu.ensure_s1_account_slots(2)
            a1 = emu.s1_accounts["acct_1"]
            a2 = emu.s1_accounts["acct_2"]
            self._call(a1, "Player", "NewPlayer", "ChienQuoc1", 0)
            self._call(a2, "Player", "NewPlayer", "ChienQuoc2", 1)
            self._prepare_strong_squad(a1, target_lv=25, vip_lv=2)
            self._prepare_strong_squad(a2, target_lv=79, vip_lv=6)

            a2_pid = str(a2.state["player"]["PlayerId"])
            a2_fap = int(a2.state["player"]["FAP"])

            top_res = self._call(a1, "PVPinter", "GetPVPInterTopRank", 0)
            self.assertEqual(top_res["Status"], 0)
            rows = top_res["Value"]["PVPinterTopRank"]
            self.assertEqual(len(rows), 50)
            self.assertTrue(all(rows[i]["FAP"] >= rows[i + 1]["FAP"] for i in range(len(rows) - 1)))
            for idx, row in enumerate(rows, start=1):
                self.assertEqual(row["Rank"], idx)
                for req in ("Id", "Name", "Lv", "FAP", "HeadImageId", "FashionModelId", "ServerName", "Zone", "GuildName"):
                    self.assertIn(req, row)
                self.assertTrue(len(row["ServerName"]) > 0)
                self.assertEqual(row["Zone"], row["ServerName"])
                self.assertIn(str(row["HeadImageId"]), a1.game_data["heroes"])
                self.assertNotIn("_source", row)

            peer_row = next((r for r in rows if r["Id"] == a2_pid), None)
            self.assertIsNotNone(peer_row)
            self.assertEqual(peer_row["ServerName"], "S1 - Chiến Quốc")
            bot_row = next((r for r in rows if str(r["Id"]).startswith("cs-bot:")), None)
            self.assertIsNotNone(bot_row)
            self.assertIn(bot_row["ServerName"], {"S2 - Tây Quốc", "S3 - Bạch Linh Sơn", "S4 - Minh Đạo", "S5 - Tứ Hồn"})

            # Inspect formation for S1 peer, self, and cross-server bot
            f_peer = self._call(a1, "PVPinter", "GetSlotFormations", a2_pid)
            self.assertEqual(f_peer["Status"], 0)
            self.assertEqual(f_peer["Value"]["Formation"]["PlayerInfo"]["PlayerId"], a2_pid)
            self.assertEqual(f_peer["Value"]["Formation"]["PlayerInfo"]["FAP"], a2_fap)
            self.assertEqual(len(f_peer["Value"]["Formation"]["SlotInfos"]), 6)

            f_self = self._call(a1, "PVPinter", "GetSlotFormations", str(a1.state["player"]["PlayerId"]))
            self.assertEqual(f_self["Status"], 0)
            self.assertEqual(f_self["Value"]["Formation"]["PlayerInfo"]["Name"], "ChienQuoc1")

            f_bot = self._call(a1, "PVPinter", "GetSlotFormations", bot_row["Id"])
            self.assertEqual(f_bot["Status"], 0)
            self.assertEqual(f_bot["Value"]["Formation"]["PlayerInfo"]["PlayerId"], bot_row["Id"])
            self.assertEqual(len(f_bot["Value"]["Formation"]["SlotInfos"]), 6)

            # Invalid target ID rejected & LeaderBoard.RankList [3] still rejected (test_r725 compatibility)
            self.assertNotEqual(self._call(a1, "PVPinter", "GetSlotFormations", "non-existent-id")["Status"], 0)
            self.assertNotEqual(self._call(a1, "LeaderBoard", "RankList", 3)["Status"], 0)


if __name__ == "__main__":
    unittest.main()
