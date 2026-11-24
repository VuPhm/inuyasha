"""Delta coverage for R7.40: P4-A2 Chiến Liên Server (PVPinter 6100 + WhosTheGod 6200)."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
import sys
import tempfile
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from combat_sim import simulate_fight_info  # noqa: E402
from emulator import GameEmulatorState  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R740PVPinterTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 24, 16, 10))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    @staticmethod
    def _goods_qty(prof: Any, mid: int) -> int:
        return sum(int(g.get("Num", 0)) for g in prof.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == mid)

    def _seed_strong_team(self, prof: Any) -> None:
        prof.admin_prepare_account(target_lv=55, vip_lv=6, source="test_r740")
        prof.state["player"].update(Diamond=50_000, Gold=5_000_000, STA=100, HeroEXP=5_000_000)
        seeded = prof._grant_resources_from_tuples(
            [(1201, m, 1) for m in (12011002, 12011003, 12011004, 12012003, 12012004)]
            + [
                (1301, 13010602, 6),
                (1302, 13020602, 6),
                (1303, 13030602, 6),
                (1304, 13040602, 6),
            ],
            source="seed_pvpinter",
            tx_prefix="seed_r740",
        )
        heroes = seeded[0]["Hero"]
        by_type = {
            t: [e for e in seeded[0]["Equip"] if int(e["EquipModelId"]) == mid]
            for t, mid in (("w", 13010602), ("h", 13020602), ("c", 13030602), ("n", 13040602))
        }
        self._call(prof, "Hero", "HeroLvUp", prof.state["heroes"][0]["Id"], 55)
        for idx, h in enumerate(heroes, start=2):
            self._call(prof, "Slot", "HeroCombat", idx, h["Id"])
            self._call(prof, "Hero", "HeroLvUp", h["Id"], 55)
        for slot_idx in range(1, 7):
            self._call(
                prof,
                "Slot",
                "OneKeyEquipCombat",
                slot_idx,
                by_type["w"][slot_idx - 1]["Id"],
                by_type["h"][slot_idx - 1]["Id"],
                by_type["c"][slot_idx - 1]["Id"],
                by_type["n"][slot_idx - 1]["Id"],
                "",
                "",
            )
        prof._recalc_all_slots_and_fap()

    def test_01_level_gate_and_open_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            # Lv < 42 gated
            for mod, fn, args in (
                ("PVPinter", "GetPVPInterInfo", []),
                ("PVPinter", "GetPVPinterFightLog", []),
                ("PVPinter", "FightForMatch", []),
                ("PVPinter", "BuyFightCount", [1]),
            ):
                res = self._call(p, mod, fn, *args)
                self.assertEqual(res["Status"], -1)
            self.assertEqual(int(p.state["player"]["PVPInterLv"]), 0)

            self._seed_strong_team(p)
            info = self._call(p, "PVPinter", "GetPVPInterInfo")
            self.assertEqual(info["Status"], 0)
            val = info["Value"]
            self.assertTrue(val["IsOpen"])
            self.assertEqual(int(val["PVPinterInfo"]["Lv"]), 1)
            self.assertEqual(int(val["PVPinterInfo"]["FightCount"]), 10)
            self.assertEqual(int(val["PVPinterInfo"]["Rate"]), 0)
            self.assertGreater(int(val["PVPinterSeasonInfo"]["EndDate"]), int(val["PVPinterSeasonInfo"]["BeginDate"]))
            self.assertEqual(int(p.state["player"]["PVPInterLv"]), 1)

    def test_02_match_win_box_promotion_series_and_uping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            self._seed_strong_team(p)
            # Ensure player FAP beats tier-1 0.72x bots cleanly
            self.assertEqual(self._call(p, "PVPinter", "GetPVPInterInfo")["Status"], 0)

            for m_idx in range(1, 4):
                sta0 = int(p.state["player"]["STA"])
                m0 = self._goods_qty(p, 16050062)
                gold0 = int(p.state["player"]["Gold"])
                res = self._call(p, "PVPinter", "FightForMatch")
                self.assertEqual(res["Status"], 0)
                rv = res["Value"]
                self.assertEqual(int(rv["IsWinFight"]), 1)
                self.assertEqual(int(p.state["player"]["STA"]), sta0 - 2)
                self.assertEqual(int(rv["PVPinterInfo"]["FightCount"]), 10 - m_idx)
                self.assertTrue(rv["TargetInfo"]["Zone"].startswith("S"))
                if m_idx == 2:
                    # 20 victory + 200 daily 2-win box medals, +50k Gold
                    self.assertEqual(self._goods_qty(p, 16050062), m0 + 220)
                    self.assertEqual(int(p.state["player"]["Gold"]), gold0 + 50_000)
                else:
                    self.assertEqual(self._goods_qty(p, 16050062), m0 + 20)
                if m_idx < 3:
                    self.assertEqual(int(rv["PVPinterInfo"]["Rate"]), 40 * m_idx)
                    self.assertIsNone(rv["PVPinterUpingInfo"])
                else:
                    self.assertEqual(int(rv["PVPinterInfo"]["Rate"]), 100)
                    self.assertEqual(len(rv["PVPinterUpingInfo"]), 3)

            # Match blocked during promotion series
            self.assertEqual(self._call(p, "PVPinter", "FightForMatch")["Status"], -1)

            logs = self._call(p, "PVPinter", "GetPVPinterFightLog")
            self.assertEqual(logs["Status"], 0)
            self.assertEqual(len(logs["Value"]["PVPinterFightLog"]), 3)

            uping_targets = self._call(p, "PVPinter", "GetPVPInterInfo")["Value"]["PVPinterUpingInfo"]
            m_before_up1 = self._goods_qty(p, 16050062)
            dia_before_up1 = int(p.state["player"]["Diamond"])
            up1 = self._call(p, "PVPinter", "FightForUping", uping_targets[0]["TargetId"])
            self.assertEqual(up1["Status"], 0)
            self.assertEqual(int(up1["Value"]["IsWinFight"]), 1)
            self.assertEqual(int(up1["Value"]["IsSucess"]), 0)
            self.assertEqual(int(up1["Value"]["PVPinterInfo"]["Lv"]), 1)
            # 4th win of the day grants 20 victory + 300 daily 4-win box medals
            self.assertEqual(self._goods_qty(p, 16050062), m_before_up1 + 20 + 300)

            up2 = self._call(p, "PVPinter", "FightForUping", uping_targets[1]["TargetId"])
            self.assertEqual(up2["Status"], 0)
            self.assertEqual(int(up2["Value"]["IsWinFight"]), 1)
            self.assertEqual(int(up2["Value"]["IsSucess"]), 2)
            self.assertEqual(int(up2["Value"]["PVPinterInfo"]["Lv"]), 2)
            self.assertEqual(int(p.state["player"]["PVPInterLv"]), 2)
            self.assertIsNone(up2["Value"]["PVPinterUpingInfo"])
            # 20 match + 300 4-win box + 590 first Lv2 promo, +50 KC +100k Gold
            self.assertEqual(self._goods_qty(p, 16050062), m_before_up1 + 20 + 20 + 300 + 590)
            self.assertEqual(int(p.state["player"]["Diamond"]), dia_before_up1 + 50)

    def test_03_buy_fight_count_and_pvpinter_shop_discount(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            self._seed_strong_team(p)
            p._grant_resources_from_tuples([(1605, 16050062, 1000)], source="seed_medals", tx_prefix="seed_medals")

            # Progressive Diamond costs: 10 + 10 + 15 = 35
            dia0 = int(p.state["player"]["Diamond"])
            b1 = self._call(p, "PVPinter", "BuyFightCount", 3)
            self.assertEqual(b1["Status"], 0)
            self.assertEqual(int(b1["Value"]["PVPinterInfo"]["FightCount"]), 13)
            self.assertEqual(int(b1["Value"]["PVPinterInfo"]["BuyCount"]), 3)
            self.assertEqual(int(p.state["player"]["Diamond"]), dia0 - 35)

            # VIP 6 buyKuafuNum cap check
            vip_limit = int(p.game_data["vip_model"]["6"]["buyKuafuNum"])
            too_many = self._call(p, "PVPinter", "BuyFightCount", vip_limit + 1)
            self.assertEqual(too_many["Status"], -1)

            # Lv 1 shop: cannot buy ID 2 (needs Lv 2); ID 1 costs full 125 medals -> +100 RebornCoin
            self.assertEqual(self._call(p, "PVPinterShopinfo", "BuyShop", 2, 1)["Status"], -1)
            rc0 = int(p.state["player"]["RebornCoin"])
            m0 = self._goods_qty(p, 16050062)
            sb1 = self._call(p, "PVPinterShopinfo", "BuyShop", 1, 1)
            self.assertEqual(sb1["Status"], 0)
            self.assertEqual(int(p.state["player"]["RebornCoin"]), rc0 + 100)
            self.assertEqual(self._goods_qty(p, 16050062), m0 - 125)

            # Promote to Lv 2 -> 0.95x sale discount (int(125*0.95)=118, int(350*0.95)=332)
            p._ensure_pvpinter_state()["lv"] = 2
            m1 = self._goods_qty(p, 16050062)
            sb2 = self._call(p, "PVPinterShopinfo", "BuyShop", 1, 1)
            self.assertEqual(sb2["Status"], 0)
            self.assertEqual(int(p.state["player"]["RebornCoin"]), rc0 + 200)
            self.assertEqual(self._goods_qty(p, 16050062), m1 - 118)

            sb3 = self._call(p, "PVPinterShopinfo", "BuyShop", 2, 1)
            self.assertEqual(sb3["Status"], 0)
            self.assertEqual(self._goods_qty(p, 15010003), 1)
            self.assertEqual(self._goods_qty(p, 16050062), m1 - 118 - 332)

            sinfo = self._call(p, "PVPinterShopinfo", "ShopInfo")
            self.assertEqual(sinfo["Status"], 0)
            self.assertEqual(
                {int(x["ShopId"]): int(x["TotalBuyCount"]) for x in sinfo["Value"]["BuyShopInfo"]},
                {1: 2, 2: 1},
            )

    def test_04_rank_and_whos_the_god_tournament_bet_and_worship(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            self._seed_strong_team(p)
            p.state["player"]["Gold"] = 2_000_000
            p.state["player"]["Diamond"] = 5_000

            r0 = self._call(p, "PVPinter", "GetPVPInterTopRank", 0)
            self.assertEqual(r0["Status"], 0)
            self.assertEqual(int(r0["Value"]["TotalPage"]), 0)
            self.assertEqual(len(r0["Value"]["PVPinterTopRank"]), 50)
            for row in r0["Value"]["PVPinterTopRank"]:
                self.assertIn(int(row["PVPInterLv"]), range(1, 9))
                self.assertGreater(int(row["Rate"]), 0)
                self.assertIn("WinRate", row)
            self.assertEqual(self._call(p, "PVPinter", "GetPVPInterTopRank", 1)["Value"]["PVPinterTopRank"], [])

            op = self._call(p, "PVPinterTop", "Open")
            self.assertEqual(op["Status"], 0)
            self.assertEqual(int(op["Value"]["IsOpen"]), 1)
            self.assertEqual(int(op["Value"]["LastPvpinterTop"]), 1)

            for stage, expected_n in ((32, 16), (16, 8), (8, 4), (4, 2), (2, 1), (1, 1)):
                rep = self._call(p, "PVPinterTop", "GetBattleReport", 1, stage)
                self.assertEqual(rep["Status"], 0)
                self.assertEqual(int(rep["Value"]["Strong"]), stage)
                self.assertEqual(len(rep["Value"]["BattleReport"]), expected_n)

            # Replay check + simulation on Stage 2 Final
            final_match = self._call(p, "PVPinterTop", "GetBattleReport", 1, 2)["Value"]["BattleReport"][0]
            first_rep_id = str(final_match["BattleReportId"]).split(",")[0]
            bc = self._call(p, "PVPinterTop", "GetBattleContent", 1, 2, first_rep_id)
            self.assertEqual(bc["Status"], 0)
            fight_payload = bc["Value"]["FightInfo"]["ClientRes"]
            sim = simulate_fight_info(fight_payload, p.game_data["attacks"], buffs_cfg=p.game_data["combat_buffs"])
            self.assertGreaterEqual(int(sim.total_rounds), 1)

            own = self._call(p, "PVPinterTop", "GetOwnBattleReport")
            self.assertEqual(own["Status"], 0)
            self.assertGreaterEqual(len(own["Value"]["BattleReport"]), 1)

            # Determine true winner of Stage 2 match via IsWin bit-packing and place BetType=3 (500k -> 1000k Gold)
            is_win_mask = int(final_match["IsWin"]) >> 16
            atk_won = sum(1 for b in range(3) if (is_win_mask >> b) & 1) >= 2
            winner_id = final_match["AttackerId"] if atk_won else final_match["DefenderId"]

            gold0 = int(p.state["player"]["Gold"])
            bet = self._call(p, "PVPinterTop", "Bet", 3, winner_id, 2, 1)
            self.assertEqual(bet["Status"], 0)
            self.assertEqual(int(bet["Value"]["PVPinterTopBetInfo"]["IsWin"]), 1)
            self.assertEqual(int(p.state["player"]["Gold"]), gold0 - 500_000)

            # Duplicate bet in same stage rejected
            self.assertEqual(self._call(p, "PVPinterTop", "Bet", 1, winner_id, 2, 1)["Status"], -1)
            own_info = self._call(p, "PVPinterTop", "GetOwnInfo")
            self.assertEqual(len(own_info["Value"]["PVPinterTopBetInfo"]), 1)

            # Claim bet reward + block double-claim
            rew = self._call(p, "PVPinterTop", "BetReward")
            self.assertEqual(rew["Status"], 0)
            self.assertEqual(int(p.state["player"]["Gold"]), gold0 + 500_000)
            self.assertEqual(self._call(p, "PVPinterTop", "BetReward")["Status"], -1)

            # Worship group 1: -50 KC cost + rewards (1x 16050072, 100x 16050065, +100 KC -> net +50 KC)
            dia0 = int(p.state["player"]["Diamond"])
            w1 = self._call(p, "PvpinterTopWorshipInfo", "Worship", 1)
            self.assertEqual(w1["Status"], 0)
            self.assertEqual(int(p.state["player"]["Diamond"]), dia0 + 50)
            self.assertEqual(self._goods_qty(p, 16050072), 1)
            self.assertEqual(self._goods_qty(p, 16050065), 100)

            # Same group twice in 1 day rejected; group 2 allowed
            self.assertEqual(self._call(p, "PvpinterTopWorshipInfo", "Worship", 1)["Status"], -1)
            self.assertEqual(self._call(p, "PvpinterTopWorshipInfo", "Worship", 2)["Status"], 0)


if __name__ == "__main__":
    unittest.main()
