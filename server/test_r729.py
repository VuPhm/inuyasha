"""Delta coverage for R7.29 (REC-P2-03): Kho Vàng (GGZJ, 8 RPCs) & Đấu Võ Đại Hội (Gddh + GddhShop, 10 RPCs)."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import EMPTY_ENTITY_ID, GameEmulatorState  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R729GgzjAndGddhTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
        # Default: Tuesday 2026-11-17 12:00:00 UTC+7 (mid-season Tue-Wed)
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 17, 12, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(emu: GameEmulatorState, mod: str, fn: str, *args: object) -> dict:
        return emu.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    def _prepare_strong_squad(self, p: any, target_lv: int = 50, vip_lv: int = 5) -> None:
        p.admin_prepare_account(target_lv=target_lv, vip_lv=vip_lv, source="test_r729")
        p.state["player"].update(Diamond=10_000, Gold=10_000_000, STA=80, HeroEXP=5_000_000)
        res = p._grant_resources_from_tuples(
            [
                (1201, 12011004, 1),
                (1201, 12012005, 1),
                (1201, 12013004, 1),
                (1301, 13010602, 4),
                (1302, 13020602, 4),
                (1605, 16050016, 20),
            ],
            source="test_r729",
            tx_prefix="setup",
        )
        heroes = res[0]["Hero"]
        weapons = [e for e in res[0]["Equip"] if int(e["EquipModelId"]) == 13010602]
        helmets = [e for e in res[0]["Equip"] if int(e["EquipModelId"]) == 13020602]
        p.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [p.state["heroes"][0]["Id"], target_lv]})
        for idx, h in enumerate(heroes, start=2):
            p.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
            p.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [h["Id"], target_lv]})
        for slot_idx in range(1, 5):
            p.handle_rpc(
                {
                    "ModuleName": "Slot",
                    "MethodName": "OneKeyEquipCombat",
                    "Data": [slot_idx, weapons[slot_idx - 1]["Id"], helmets[slot_idx - 1]["Id"], "", "", "", ""],
                }
            )
        p._recalc_all_slots_and_fap()
        p.save()

    def test_01_vn_configs_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, p = self._new_emu(tmp)
            gd = p.game_data
            self.assertEqual(gd["ggzj_config"]["nodeTotal"], 15)
            self.assertEqual(gd["ggzj_config"]["perNodeDareNumMax"], 3)
            self.assertEqual(gd["ggzj_config"]["refreshUseDiamond"], 20)
            self.assertEqual(len(gd["ggzj_box_reward"]), 5)
            self.assertEqual(len(gd["ggzj_reward_view"]), 6)
            self.assertEqual(len(gd["ggzj_system_heroes"]), 100)
            self.assertEqual(sum(len(v) for v in gd["ggzj_system_heroes"].values()), 900)

            self.assertEqual(gd["gddh_config"]["initValue"], 1000)
            self.assertEqual(gd["gddh_config"]["attckNumMax"], 10)
            self.assertEqual(len(gd["gddh_attack_reward"]), 3)
            self.assertEqual(len(gd["gddh_buynum"]), 30)
            self.assertEqual(len(gd["gddh_shop"]), 16)
            self.assertEqual(len(gd["gddh_rank_reward"]["0"]), 18)
            self.assertEqual(len(gd["gddh_rank_reward"]["1"]), 18)
            self.assertEqual(len(gd["gddh_guild_reward"]["0"]), 5)
            self.assertEqual(len(gd["gddh_guild_reward"]["1"]), 3)

    def test_02_ggzj_hire_formation_refresh_fight_and_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.event_runtime.configure_archive_mode("scheduled", scheduled_windows={})
            self._prepare_strong_squad(p, target_lv=50, vip_lv=5)

            # PlayerInfo has GuildId == EMPTY_ENTITY_ID so Hire layer switches to System tab cleanly
            init_val = self._call(emu, "Player", "GetInitData")["Value"]
            self.assertEqual(init_val["PlayerInfo"]["GuildId"], EMPTY_ENTITY_ID)

            info = self._call(emu, "GGZJ", "GetGGZJInfo")
            self.assertEqual(info["Status"], 0)
            v = info["Value"]
            self.assertEqual(v["NodeId"], 1)
            self.assertEqual(v["FightCount"], 0)
            self.assertEqual(v["BoxProcess"], 0)
            self.assertEqual(v["ShareType"], 0)
            self.assertEqual(len(v["Target"]), 1)
            orig_target_fap = v["Target"][0]["FAP"]

            # Hire system mercenary 12013004 (consumes 8x 16050016, emits Avatar.GoodsInfo, rejects 2nd hire)
            hire = self._call(emu, "GGZJ", "Hire", 2, EMPTY_ENTITY_ID, 12013004)
            self.assertEqual(hire["Status"], 0)
            self.assertEqual(hire["Value"]["ShareType"], 2)
            self.assertEqual(hire["Value"]["HeroModelId"], 12013004)
            self.assertEqual(hire["Value"]["HeroLv"], 50)
            self.assertIn("GoodsInfo", hire["Avatar"])
            tok = next(g for g in p.state["goods"] if int(g["GoodsModelId"]) == 16050016)
            self.assertEqual(tok["Num"], 12)
            self.assertNotEqual(self._call(emu, "GGZJ", "Hire", 2, EMPTY_ENTITY_ID, 12013005)["Status"], 0)

            # FormationChang: rejects moving MC (1) to reserve slot 7; allows putting merc (7) at pos 4
            self.assertNotEqual(self._call(emu, "GGZJ", "FormationChang", 7, 2, 3, 4, 5, 6, 1)["Status"], 0)
            chg = self._call(emu, "GGZJ", "FormationChang", 1, 2, 3, 7, 5, 6, 4)
            self.assertEqual(chg["Status"], 0)
            self.assertEqual(self._call(emu, "GGZJ", "GetGGZJInfo")["Value"]["Formation4"], 7)

            # RefreshGGZJNPC spends 20 Diamond and lowers opponent FAP slightly
            dia_before = int(p.state["player"]["Diamond"])
            ref = self._call(emu, "GGZJ", "RefreshGGZJNPC")
            self.assertEqual(ref["Status"], 0)
            self.assertEqual(dia_before - int(p.state["player"]["Diamond"]), 20)
            self.assertLess(ref["Value"]["Target"][0]["FAP"], orig_target_fap)

            # GetFightBeforeInfo includes hired system hero stats at pos 4
            before = self._call(emu, "GGZJ", "GetFightBeforeInfo")
            self.assertEqual(before["Status"], 0)
            heros = before["Value"]["FightInfo"]["FightObjs"][0]["Heros"]
            self.assertEqual(heros[3]["HeroModelId"], 12013004)
            sys_row = p.game_data["ggzj_system_heroes"]["50"]["12013004"]
            self.assertEqual(heros[3]["AP"], sys_row["AP"])

            # Loss consumes 0 STA & increments FightCount
            sta_before = int(p.state["player"]["STA"])
            lose_verify = json.dumps({"hp": [[{"PosId": 1, "HP": 0, "RP": 0}, {"PosId": 7, "HP": 1000, "RP": 50}]]})
            loss1 = self._call(emu, "GGZJ", "Fight", False, lose_verify, False)
            self.assertEqual(loss1["Status"], 0)
            self.assertEqual(loss1["Value"]["IsSuccess"], "False")
            self.assertEqual(loss1["Value"]["FightCount"], 1)
            self.assertEqual(int(p.state["player"]["STA"]), sta_before)

            # Win with is_skip=True returns TargetCsHp, deducts 2 STA, grants VIP 125% Gold, advances to NodeId=2
            gold_before = int(p.state["player"]["Gold"])
            p.state["success_target"] = {"start_ts": emu.clock.now() - 6 * 86400, "drawn": {}, "drawn_days": [], "if_draw": 0, "exchange_counts": {}}
            skip_win = self._call(emu, "GGZJ", "Fight", True, "", True)
            self.assertEqual(skip_win["Status"], 0)
            self.assertEqual(skip_win["Value"]["IsSuccess"], "True")
            self.assertIn("TargetCsHp", skip_win["Value"])
            self.assertEqual(skip_win["Value"]["NodeId"], 2)
            self.assertEqual(int(p.state["player"]["STA"]), sta_before - 2)
            expected_gold_1 = ((220 + 1 * 55) * 50) * 125 // 100
            self.assertEqual(int(p.state["player"]["Gold"]) - gold_before, expected_gold_1)

            # Welfare 4415 doubles GGZJ stage Gold on Node 2
            p.event_runtime.activate_manual_event("timed_welfare_ycjk", duration_sec=3600)
            gold_before_2 = int(p.state["player"]["Gold"])
            w2 = self._call(emu, "GGZJ", "Fight", True, "", True)
            self.assertEqual(w2["Status"], 0)
            expected_gold_2 = ((220 + 2 * 55) * 50 * 2) * 125 // 100
            self.assertEqual(int(p.state["player"]["Gold"]) - gold_before_2, expected_gold_2)

            # Check DailyTask #9, SuccessTarget #13 (2 wins), and Activeranking Score
            dt_list = self._call(emu, "DailyTaskInfo", "GetDaliyTaskInfo")["Value"]["TasksInfo"]
            t9 = next(t for t in dt_list if t["Id"] == 9)
            self.assertEqual(t9["Num"], 1)  # loopNum=1, completed
            self.assertTrue(t9["CanDrawCredit"])
            self.assertEqual(self._call(emu, "DailyTaskInfo", "GetCredit", 9)["Status"], 0)
            st_list = self._call(emu, "SuccessTargetInfo", "GetInfo")["Value"]["TargetList"]
            t13 = next(t for t in st_list if t["TargetId"] == 13)
            self.assertEqual(t13["ReachedNum"], 2)
            act_score = self._call(emu, "TimedScoreRank", "GetInfo")["Value"]["Score"]
            self.assertEqual(act_score, 3 * 2 + 50 * 5)  # ggzj_count=3 * 2pts + Lv50*5

            # Exhausting 3 losses on Node 3 locks further fights
            for idx in range(1, 4):
                r_lose = self._call(emu, "GGZJ", "Fight", False, lose_verify, False)
                self.assertEqual(r_lose["Status"], 0)
                self.assertEqual(r_lose["Value"]["FightCount"], idx)
            self.assertNotEqual(self._call(emu, "GGZJ", "GetFightBeforeInfo")["Status"], 0)
            self.assertNotEqual(self._call(emu, "GGZJ", "Fight", True, "", False)["Status"], 0)

    def test_03_ggzj_boxes_clearance_truce_and_daily_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.event_runtime.configure_archive_mode("scheduled", scheduled_windows={})
            self._prepare_strong_squad(p, target_lv=50, vip_lv=0)

            # Cannot claim Box 3 before clearing node 3
            self.assertNotEqual(self._call(emu, "GGZJ", "ReceiveBoxRewards", 3)["Status"], 0)

            # Clear all 15 nodes
            for n in range(1, 16):
                r = self._call(emu, "GGZJ", "Fight", True, "", False)
                self.assertEqual(r["Status"], 0)
                if n < 15:
                    self.assertEqual(r["Value"]["NodeId"], n + 1)
                else:
                    self.assertEqual(r["Value"]["NodeId"], 0)

            # Box rewards must be claimed in milestone order 3, 6, 9, 12, 15 and expand 2112 (1000 * Lv=50_000 Gold)
            self.assertNotEqual(self._call(emu, "GGZJ", "ReceiveBoxRewards", 6)["Status"], 0)
            for m in (3, 6, 9, 12, 15):
                gold_before = int(p.state["player"]["Gold"])
                dia_before = int(p.state["player"]["Diamond"])
                rb = self._call(emu, "GGZJ", "ReceiveBoxRewards", m)
                self.assertEqual(rb["Status"], 0)
                self.assertEqual(rb["Value"]["BoxProcess"], m)
                self.assertEqual(int(p.state["player"]["Gold"]) - gold_before, 1000 * 50)
                self.assertEqual(int(p.state["player"]["Diamond"]) - dia_before, 20)

            # Clearance chest (once only)
            gold_before = int(p.state["player"]["Gold"])
            rc = self._call(emu, "GGZJ", "ReceiveClearanceRewards")
            self.assertEqual(rc["Status"], 0)
            self.assertEqual(int(p.state["player"]["Gold"]) - gold_before, 1500 * 50)
            self.assertNotEqual(self._call(emu, "GGZJ", "ReceiveClearanceRewards")["Status"], 0)

            # 23:55 UTC+7 truce blocks GetFightBeforeInfo/Hire
            emu.clock.set_fixed(_ts_vn(2026, 11, 17, 23, 55))
            self.assertNotEqual(self._call(emu, "GGZJ", "Hire", 2, EMPTY_ENTITY_ID, 12013004)["Status"], 0)

            # 00:05 next day resets GGZJ daily state cleanly
            emu.clock.set_fixed(_ts_vn(2026, 11, 18, 0, 5))
            next_info = self._call(emu, "GGZJ", "GetGGZJInfo")["Value"]
            self.assertEqual(next_info["NodeId"], 1)
            self.assertEqual(next_info["BoxProcess"], 0)
            self.assertFalse(next_info["IsReceiveClearanceRewards"])
            self.assertEqual(next_info["ShareType"], 0)

    def test_04_gddh_signup_apply_fight_recovery_buy_and_attack_rewards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.event_runtime.configure_archive_mode("scheduled", scheduled_windows={})
            self._prepare_strong_squad(p, target_lv=50, vip_lv=4)

            sig = self._call(emu, "Gddh", "SignupInfo")
            self.assertEqual(sig["Status"], 0)
            self.assertEqual(sig["Value"]["IsJoin"], 0)
            self.assertGreater(emu.clock.now(), sig["Value"]["BeginDate"])

            app = self._call(emu, "Gddh", "ApplyGroup")
            self.assertEqual(app["Status"], 0)
            gid = app["Value"]["GroupId"]
            self.assertIn(gid, (1, 2, 3, 4))

            info = self._call(emu, "Gddh", "GetWrestleRaceInfo")["Value"]
            self.assertEqual(info["IsApply"], 1)
            self.assertEqual(info["IsInTruce"], 0)
            self.assertEqual(info["RankCount"], 10)
            self.assertEqual(info["Integral"], 1000)
            self.assertEqual(info["GroupId"], gid)
            self.assertEqual(len(info["GddhRankTargetList"]), 3)
            self.assertGreater(len(info["GddhRankList"]["One"]), 0)
            self.assertGreater(len(info["GddhRankList"]["GuildInfo"]), 0)

            # Slot.SlotFormations works on Gddh bot!
            bot_pid = info["GddhRankTargetList"][0]["PlayerId"]
            bot_fmt = self._call(emu, "Slot", "SlotFormations", bot_pid)
            self.assertEqual(bot_fmt["Status"], 0)
            self.assertEqual(bot_fmt["Value"]["PlayerInfo"]["PlayerId"], bot_pid)

            # RefreshWrestleRaceRankList enforces 10s CD
            ref1 = self._call(emu, "Gddh", "RefreshWrestleRaceRankList")
            self.assertEqual(ref1["Status"], 0)
            self.assertEqual(ref1["Value"]["LastRefreshTime"] - ref1["TimeTick"], 10)
            self.assertNotEqual(self._call(emu, "Gddh", "RefreshWrestleRaceRankList")["Status"], 0)
            emu.clock.advance(11)
            self.assertEqual(self._call(emu, "Gddh", "RefreshWrestleRaceRankList")["Status"], 0)

            # Activate 4414 Welfare (2x GDDHCoin) & fight a weaker low-integral bot so player wins reliably
            p.event_runtime.activate_manual_event("timed_welfare_dwdh", duration_sec=3600)
            weak_bot = min(info["GddhRankList"]["Four"], key=lambda e: int(e["FAP"]))
            sta_before = int(p.state["player"]["STA"])
            coin_before = int(p.state["player"]["GDDHCoin"])
            fight_res = self._call(emu, "Gddh", "RankWrestleRace", weak_bot["PlayerId"], 0)
            self.assertEqual(fight_res["Status"], 0)
            fv = fight_res["Value"]
            self.assertEqual(fv["IsWinFight"], 1)
            self.assertGreater(fv["AddIntegral"], 0)
            self.assertEqual(fv["Integral"], 1000 + fv["AddIntegral"])
            self.assertEqual(fv["RankCount"], 9)
            self.assertEqual(fv["PerRankCount"], 1)
            self.assertNotIn("IntegralRewardIdList", fv)
            self.assertEqual(int(p.state["player"]["STA"]), sta_before - 2)
            self.assertEqual(int(p.state["player"]["GDDHCoin"]) - coin_before, 4)  # 2 * RefNum=2
            self.assertTrue(any(c.get("IsDrop") == 1 for c in fv["ChoiceGetGameResource"]))

            # DailyTask #6 & SuccessTarget #30 & Activeranking updated
            self.assertEqual(p._success_target_metrics(1)[0][30], 1)
            dt_list = self._call(emu, "DailyTaskInfo", "GetDaliyTaskInfo")["Value"]["TasksInfo"]
            t6 = next(t for t in dt_list if t["Id"] == 6)
            self.assertEqual(t6["Num"], 1)

            # Hourly RankCount recovery (+1 per 3600s back to 10)
            emu.clock.advance(3605)
            rec_info = self._call(emu, "Gddh", "GetWrestleRaceInfo")["Value"]
            self.assertEqual(rec_info["RankCount"], 10)

            # Tiered BuyRankCount pricing: first 10 costs 10 each, 11..20 costs 20 each, 21+ costs 30 each
            dia_before = int(p.state["player"]["Diamond"])
            b1 = self._call(emu, "Gddh", "BuyRankCount", 9)
            self.assertEqual(b1["Status"], 0)
            self.assertEqual(dia_before - int(p.state["player"]["Diamond"]), 90)
            self.assertEqual(b1["Value"]["BuyRankCount"], 9)
            self.assertEqual(b1["Value"]["RankCount"], 19)

            dia_mid = int(p.state["player"]["Diamond"])
            b2 = self._call(emu, "Gddh", "BuyRankCount", 3)  # #10=10, #11=20, #12=20 -> 50
            self.assertEqual(b2["Status"], 0)
            self.assertEqual(dia_mid - int(p.state["player"]["Diamond"]), 50)
            self.assertEqual(b2["Value"]["BuyRankCount"], 12)
            self.assertEqual(b2["Value"]["RankCount"], 22)

            # Fight 4 more times -> 5 total fights -> milestone 5 appears in ReceiveIdList and claim expands 2112
            for _ in range(4):
                self.assertEqual(self._call(emu, "Gddh", "RankWrestleRace", weak_bot["PlayerId"], 0)["Status"], 0)
            pre_claim = self._call(emu, "Gddh", "GetWrestleRaceInfo")["Value"]
            self.assertIn(5, pre_claim["ReceiveIdList"])
            gold_before = int(p.state["player"]["Gold"])
            rec = self._call(emu, "Gddh", "ReceiveReward", "5")
            self.assertEqual(rec["Status"], 0)
            self.assertEqual(int(p.state["player"]["Gold"]) - gold_before, 125 * 50)
            self.assertNotIn(5, self._call(emu, "Gddh", "GetWrestleRaceInfo")["Value"]["ReceiveIdList"])
            self.assertNotEqual(self._call(emu, "Gddh", "ReceiveReward", "5")["Status"], 0)

    def test_05_gddh_revenge_s1_peer_and_shop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu.clock.set_fixed(_ts_vn(2026, 11, 17, 12, 0))
            emu.ensure_s1_account_slots(2)
            acct1 = emu.s1_accounts["acct_1"]
            acct2 = emu.s1_accounts["acct_2"]
            acct1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["VictimOne", 0]})
            acct2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["RaiderTwo", 1]})
            acct1.admin_prepare_account(target_lv=50, vip_lv=3, source="test_rev")
            acct2.admin_prepare_account(target_lv=65, vip_lv=5, source="test_rev")
            res2 = acct2._grant_resources_from_tuples(
                [(1201, 12011004, 1), (1201, 12012005, 1), (1117, 0, 5_000_000), (1112, 0, 5_000_000)],
                source="test_rev",
                tx_prefix="rev2",
            )
            for idx, h in enumerate(res2[0]["Hero"], start=2):
                acct2.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
                acct2.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [h["Id"], 65]})
            acct1.handle_rpc({"ModuleName": "Gddh", "MethodName": "ApplyGroup", "Data": []})
            acct2.handle_rpc({"ModuleName": "Gddh", "MethodName": "ApplyGroup", "Data": []})

            # acct2 defeats acct1 -> acct1's revive list receives acct2!
            pid1 = str(acct1.state["player"]["PlayerId"])
            pid2 = str(acct2.state["player"]["PlayerId"])
            atk = acct2.handle_rpc({"ModuleName": "Gddh", "MethodName": "RankWrestleRace", "Data": [pid1, 0]})
            self.assertEqual(atk["Status"], 0)
            self.assertEqual(atk["Value"]["IsWinFight"], 1)
            rev_list = acct1.handle_rpc({"ModuleName": "Gddh", "MethodName": "GetWrestleRaceReviveList", "Data": []})["Value"]
            self.assertEqual(len(rev_list), 1)
            self.assertEqual(rev_list[0]["RankPlayerId"], pid2)

            # Empower acct1 above acct2 so revenge succeeds and clears acct2 from revive list
            res1 = acct1._grant_resources_from_tuples(
                [(1201, 12013004, 1), (1201, 12013005, 1), (1301, 13010701, 3), (1117, 0, 10_000_000)],
                source="test_rev",
                tx_prefix="rev1",
            )
            for idx, h in enumerate(res1[0]["Hero"], start=2):
                acct1.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
                acct1.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [h["Id"], 75]})
            acct1.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [acct1.state["heroes"][0]["Id"], 75]})
            for s_idx, w in enumerate(res1[0]["Equip"], start=1):
                acct1.handle_rpc({"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [s_idx, w["Id"], "", "", "", "", ""]})

            revenge = acct1.handle_rpc({"ModuleName": "Gddh", "MethodName": "RankWrestleRace", "Data": [pid2, 1]})
            self.assertEqual(revenge["Status"], 0)
            self.assertEqual(revenge["Value"]["IsWinFight"], 1)
            self.assertEqual(revenge["Value"]["GddhReviveList"], [])
            coin_after_rev = int(acct1.state["player"]["GDDHCoin"])
            self.assertGreaterEqual(coin_after_rev, 2)

            # GddhShop: 16 items, rank-gated item #6 rejected unless HistortRank==1, Kikyo shard #7 purchasable
            shop = acct1.handle_rpc({"ModuleName": "GddhShop", "MethodName": "GetWrestleRaceShopInfo", "Data": []})
            self.assertEqual(shop["Status"], 0)
            self.assertEqual(len(shop["Value"]), 16)
            acct1._grant_resources_from_tuples([(1119, 0, 2000)], source="test_shop", tx_prefix="shopcoin")

            # Item 6 needs rank==1 (totalMaxNum=1); reject if history_rank > 1
            acct1.state["gddh"]["history_rank"] = 5
            self.assertNotEqual(acct1.handle_rpc({"ModuleName": "GddhShop", "MethodName": "WrestleRaceShopBuy", "Data": [6, 1]})["Status"], 0)
            acct1.state["gddh"]["history_rank"] = 1
            buy6 = acct1.handle_rpc({"ModuleName": "GddhShop", "MethodName": "WrestleRaceShopBuy", "Data": [6, 1]})
            self.assertEqual(buy6["Status"], 0)
            self.assertEqual(buy6["Avatar"]["GDDHCoin"], coin_after_rev + 400)
            # Lifetime totalMaxNum=1 blocks second purchase
            self.assertNotEqual(acct1.handle_rpc({"ModuleName": "GddhShop", "MethodName": "WrestleRaceShopBuy", "Data": [6, 1]})["Status"], 0)

            # Buy #7 (Kikyo shard 15010002, cost 100 GDDHCoin)
            buy7 = acct1.handle_rpc({"ModuleName": "GddhShop", "MethodName": "WrestleRaceShopBuy", "Data": [7, 2]})
            self.assertEqual(buy7["Status"], 0)
            self.assertEqual(buy7["Avatar"]["GDDHCoin"], coin_after_rev + 200)
            kikyo_shard = next(g for g in acct1.state["goods"] if int(g["GoodsModelId"]) == 15010002)
            self.assertEqual(kikyo_shard["Num"], 2)

    def test_06_gddh_daily_and_season_settlement_to_reward_center(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Start Tuesday 2026-11-17 12:00 UTC+7 (2-day season: Tue-Wed, rewardsType=1)
            emu, p = self._new_emu(tmp, ts=_ts_vn(2026, 11, 17, 12, 0))
            p.admin_prepare_account(target_lv=50, vip_lv=3, source="test_settle")
            self.assertEqual(self._call(emu, "Gddh", "ApplyGroup")["Status"], 0)
            pre_info = self._call(emu, "Gddh", "GetWrestleRaceInfo")["Value"]
            rank_tue = pre_info["Rank"]
            self.assertTrue(1 <= rank_tue <= 21)

            # Advance to Tue 23:05 -> daily gold reward arrives in RewardCenter; IsJoin stays 1 & Integral kept
            emu.clock.set_fixed(_ts_vn(2026, 11, 17, 23, 5))
            rc_tue = self._call(emu, "Reward", "Rewars")["Value"]
            self.assertEqual(len(rc_tue), 1)
            self.assertEqual(rc_tue[0]["ResourceList"][0]["ResourceTypeSub"], 1112)
            still_in = self._call(emu, "Gddh", "GetWrestleRaceInfo")["Value"]
            self.assertEqual(still_in["IsApply"], 1)
            self.assertEqual(still_in["Integral"], 1000)

            # Advance to Wed 23:05 (final day settlement) -> IsInTruce=1 + season reward queued in RewardCenter
            emu.clock.set_fixed(_ts_vn(2026, 11, 18, 23, 5))
            truce_info = self._call(emu, "Gddh", "GetWrestleRaceInfo")["Value"]
            self.assertEqual(truce_info["IsInTruce"], 1)
            rc_wed = self._call(emu, "Reward", "Rewars")["Value"]
            self.assertEqual(len(rc_wed), 2)
            season_entry = next(e for e in rc_wed if "Mùa Giải" in e["Title"])
            res_types = {int(r["ResourceTypeSub"]) for r in season_entry["ResourceList"]}
            self.assertIn(1112, res_types)
            self.assertIn(1119, res_types)

            # Claim both RewardCenter entries & verify Gold + GDDHCoin + idempotency
            gold_before = int(p.state["player"]["Gold"])
            coin_before = int(p.state["player"]["GDDHCoin"])
            claim = self._call(emu, "Reward", "DrawGiftBags", [e["Id"] for e in rc_wed])
            self.assertEqual(claim["Status"], 0)
            self.assertGreater(int(p.state["player"]["Gold"]), gold_before)
            self.assertGreater(int(p.state["player"]["GDDHCoin"]), coin_before)
            self.assertEqual(self._call(emu, "Reward", "Rewars")["Value"], [])

            # Advance to Thu 10:00 (next season W47-S2) -> resets IsJoin=0, season reward NOT duplicated
            emu.clock.set_fixed(_ts_vn(2026, 11, 19, 10, 0))
            self.assertEqual(self._call(emu, "Gddh", "SignupInfo")["Value"]["IsJoin"], 0)
            self.assertEqual(self._call(emu, "Reward", "Rewars")["Value"], [])


if __name__ == "__main__":
    unittest.main()
