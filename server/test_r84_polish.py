#!/usr/bin/env python3
"""Delta coverage for R8.4: Money Tree dead-item cleanup, Main Fashion lifecycle/combat/1607 compose, TimedExchange expansion."""

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


class R84PolishTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 25, 12, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    @staticmethod
    def _goods_qty(prof: Any, mid: int) -> int:
        return sum(int(g.get("Num", 0)) for g in prof.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == mid)

    def test_01_lucky_money_tree_and_dead_items_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=30, vip_lv=5)
            prof.state["player"]["Diamond"] = 50_000

            dead_ids = {16050030, 16050034, 16050055}
            tier_constants = [
                prof.MONEY_TREE_SHOW_REWARDS,
                prof.MONEY_TREE_POOL,
                prof.MONEY_TREE_MILESTONES,
                prof.PRAY_TREE_DAYS,
                prof.MIAOSHA_PACKS,
                prof.CHARGE_SINGLE_TIERS,
                prof.CHARGE_TOTAL_TIERS,
                prof.USE_TOTAL_TIERS,
                prof.CHARGE_DAYS_TIERS,
                prof.DAY_LOGIN_TIERS,
                prof.RANK_REWARD_TEMPLATE,
                prof.CHARGE_GIFT_TIERS,
                prof.ACTIVE_RANK_REWARDS,
                prof.CRITICAL_TASK_SPECS,
            ]
            for const in tier_constants:
                text = repr(const)
                for did in dead_ids:
                    self.assertNotIn(str(did), text, msg=f"Dead item {did} still in {text[:120]}")

            pool_ids = {int(row[1]) for row in prof.MONEY_TREE_POOL}
            self.assertIn(16050065, pool_ids)
            self.assertIn(16050038, pool_ids)

            info = self._call(prof, "TimedMoneyTree", "GetInfo")["Value"]
            show_ids = {int(r["ModelId"]) for s in info["ShowRewards"] for r in s["Reward"]}
            reward_ids = {int(r["ModelId"]) for m in info["Rewards"] for r in m["Reward"]}
            self.assertTrue(dead_ids.isdisjoint(show_ids | reward_ids))
            self.assertIn(16050065, show_ids)
            self.assertIn(16050065, reward_ids)

            gold_before = int(prof.state["player"]["Gold"])
            stones_before = self._goods_qty(prof, 16050001)
            reborn_before = self._goods_qty(prof, 16050065)

            self.assertEqual(self._call(prof, "TimedMoneyTree", "ShakeTree", 10)["Status"], 0)
            self.assertEqual(self._call(prof, "TimedMoneyTree", "ShakeTree", 10)["Status"], 0)

            draw5 = self._call(prof, "TimedMoneyTree", "DrawReward", 5)
            self.assertEqual(draw5["Status"], 0)
            self.assertGreaterEqual(int(prof.state["player"]["Gold"]) - gold_before, 1_000_000)
            self.assertGreaterEqual(self._goods_qty(prof, 16050001) - stones_before, 1000)

            draw20 = self._call(prof, "TimedMoneyTree", "DrawReward", 20)
            self.assertEqual(draw20["Status"], 0)
            self.assertGreaterEqual(self._goods_qty(prof, 16050065) - reborn_before, 80)

    def test_02_timed_exchange_mount_book_fashion_and_daily_shard_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, prof = self._new_emu(tmp, ts=_ts_vn(2026, 11, 25, 12, 0))
            prof.admin_prepare_account(target_lv=30, vip_lv=5)
            prof.state["player"]["Diamond"] = 100_000
            prof.state["player"]["Gold"] = 10_000_000

            info = self._call(prof, "TimedLimitExchange", "GetInfo")["Value"]
            by_serial = {int(row["Serial"]): row for row in info["ActivityList"]}

            expected_gives = {
                4: 16060002,
                5: 16060003,
                6: 16060004,
                7: 16060036,
                8: 14022001,
                9: 14022002,
                10: 14012001,
                11: 14012002,
                19: 16060001,
                20: 16080001,
                21: 16080007,
                22: 16080010,
                23: 16080004,
            }
            for ser, model_id in expected_gives.items():
                self.assertIn(ser, by_serial)
                self.assertEqual(int(by_serial[ser]["ExchaneGameResourceList"][0]["ModelId"]), model_id)

            # Exchange Serial 19 (Purple Mount box 16060001) using 3-arg client convention
            ex19 = self._call(prof, "TimedLimitExchange", "Exchange", 4406, 19, 1)
            self.assertEqual(ex19["Status"], 0)
            self.assertEqual(self._goods_qty(prof, 16060001), 1)

            # Advance across 4 consecutive days and verify Serial 24 & 25 cover all 8 fashion shards
            seen_shards: set[int] = set()
            for day_offset in range(4):
                emu.clock.set_fixed(_ts_vn(2026, 11, 25 + day_offset, 12, 0))
                day_info = self._call(prof, "TimedLimitExchange", "GetInfo")["Value"]
                day_map = {int(row["Serial"]): row for row in day_info["ActivityList"]}
                self.assertIn(24, day_map)
                self.assertIn(25, day_map)
                s24 = int(day_map[24]["ExchaneGameResourceList"][0]["ModelId"])
                s25 = int(day_map[25]["ExchaneGameResourceList"][0]["ModelId"])
                self.assertEqual(int(day_map[24]["ExchaneGameResourceList"][0]["Count"]), 100)
                self.assertEqual(int(day_map[25]["ExchaneGameResourceList"][0]["Count"]), 100)
                seen_shards.update((s24, s25))
                if day_offset == 0:
                    ex24 = self._call(prof, "TimedLimitExchange", "Exchange", 24, 1)
                    self.assertEqual(ex24["Status"], 0)
                    self.assertEqual(self._goods_qty(prof, s24), 100)

            self.assertEqual(seen_shards, set(range(16070004, 16070012)))

            # Verify Points Mall (4428) includes 16080001 & 16080004 and works after recharge (3-arg client call)
            mall = self._call(prof, "TimedChargeScore", "GetRewardList")["Value"]
            mall_by_id = {int(g["id"]): g for g in mall["GoodsInfo"]}
            self.assertEqual(mall_by_id[7]["Reward"], "1608,16080001,1")
            self.assertEqual(mall_by_id[8]["Reward"], "1608,16080004,1")

            order = self._call(prof, "PlayerCharge", "GenerateOrderID", "com.cmn.inuyasha.gem300")["Value"]
            self.assertEqual(self._call(prof, "PlayerCharge", "ConfirmOrder", "com.cmn.inuyasha.gem300", order)["Status"], 0)
            buy7 = self._call(prof, "TimedChargeScore", "BuyGoods", 4428, 7, 1)
            self.assertEqual(buy7["Status"], 0)
            self.assertEqual(self._goods_qty(prof, 16080001), 1)

    def test_03_main_fashion_full_lifecycle_stats_combat_1607_resolve_stepup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=36, vip_lv=6)
            prof.state["player"]["Diamond"] = 100_000
            prof.state["player"]["Gold"] = 5_000_000

            # Capture baseline MC slot & fight metadata
            base_slot0 = dict(prof.state["slots"][0]["Property"])
            base_fap = int(prof.state["player"]["FAP"])
            base_fight = self._call(prof, "Battle", "GetFightInfo", 11, 1111, 1)["Value"]["FightInfo"]
            base_mc = base_fight["FightObjs"][0]["Heros"][0]
            mc_model_id = int(prof.state["slots"][0]["HeroModelId"])
            base_naid = int(base_mc["NAId"])
            base_raid = int(base_mc["RAId"])
            base_large = str(base_mc["LargePic"])
            base_small = str(base_mc["SmallPic"])

            # Exchange 2x 16080004 (Server Fashion box) & choose 19010003 + 19010004
            ex23 = self._call(prof, "TimedLimitExchange", "Exchange", 23, 2)
            self.assertEqual(ex23["Status"], 0)
            box_server = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16080004)

            c1 = self._call(prof, "Goods", "GoodsUseForBoxChoice", box_server["Id"], 16080004, 19010003, 1)
            self.assertEqual(c1["Status"], 0)
            self.assertIn("SlotInfo", c1["Avatar"])
            self.assertGreater(int(c1["Avatar"]["FAP"]), base_fap)

            c2 = self._call(prof, "Goods", "GoodsUseForBoxChoice", box_server["Id"], 16080004, 19010004, 1)
            self.assertEqual(c2["Status"], 0)
            self.assertIn("SlotInfo", c2["Avatar"])

            # Check FashionStep + FashionPrRelation #2 (front row AP+500, all DEF+100) before DressUp
            prop_after_pair = dict(prof.state["slots"][0]["Property"])
            self.assertGreaterEqual(prop_after_pair["AP"] - base_slot0["AP"], 500)
            self.assertGreaterEqual(prop_after_pair["DEF"] - base_slot0["DEF"], 100)
            damaddr_before_wear = int(prop_after_pair["DAMADDR"])
            damcutr_before_wear = int(prop_after_pair["DAMCUTR"])

            # Equip 19010003 (Dũng Khí: attrStr = 410|500,411|500)
            f_courage = next(f for f in prof.state["fashions"] if int(f["FashionModelId"]) == 19010003)
            dress = self._call(prof, "Fashion", "DressUp", f_courage["Id"])
            self.assertEqual(dress["Status"], 0)
            self.assertEqual(dress["Avatar"]["FashionModelId"], 19010003)
            self.assertIn("SlotInfo", dress["Avatar"])
            prop_worn_courage = dress["Avatar"]["SlotInfo"][0]["Property"]
            self.assertEqual(int(prop_worn_courage["DAMADDR"]) - damaddr_before_wear, 500)
            self.assertEqual(int(prop_worn_courage["DAMCUTR"]) - damcutr_before_wear, 500)

            # Verify Battle.GetFightInfo switches MC skills/pics while keeping MC HeroModelId
            fm_courage = prof.game_data["fashion_model"]["19010003"]
            f_courage_fight = self._call(prof, "Battle", "GetFightInfo", 11, 1111, 1)["Value"]["FightInfo"]
            mc_courage = f_courage_fight["FightObjs"][0]["Heros"][0]
            self.assertEqual(int(mc_courage["HeroModelId"]), mc_model_id)
            self.assertEqual(int(mc_courage["NAId"]), int(fm_courage["NAID"]))
            self.assertEqual(int(mc_courage["RAId"]), int(fm_courage["RAID"]))
            self.assertEqual(str(mc_courage["LargePic"]), str(fm_courage["actionPic"]))
            self.assertEqual(str(mc_courage["SmallPic"]), str(fm_courage["headerPic"]))
            self.assertEqual(str(mc_courage["SkillSound"]), str(fm_courage["skillSound"]))
            self.assertEqual(int(mc_courage["DAMADDR"]), int(prop_worn_courage["DAMADDR"]))
            self.assertEqual(int(mc_courage["DAMCUTR"]), int(prop_worn_courage["DAMCUTR"]))

            # Equip 19010005 (Số Đỏ: attrStr = 302|150,303|150 -> DOD +150, CRI +150)
            self.assertEqual(self._call(prof, "TimedLimitExchange", "Exchange", 21, 1)["Status"], 0)
            box_spring = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16080007)
            self.assertEqual(
                self._call(prof, "Goods", "GoodsUseForBoxChoice", box_spring["Id"], 16080007, 19010005, 1)["Status"],
                0,
            )
            prop_before_spring = dict(prof.state["slots"][0]["Property"])
            dod_before = int(prop_before_spring["DOD"])
            cri_before = int(prop_before_spring["CRI"])

            f_spring = next(f for f in prof.state["fashions"] if int(f["FashionModelId"]) == 19010005)
            dress_s = self._call(prof, "Fashion", "DressUp", f_spring["Id"])
            self.assertEqual(dress_s["Status"], 0)
            prop_worn_spring = dress_s["Avatar"]["SlotInfo"][0]["Property"]
            self.assertEqual(int(prop_worn_spring["DOD"]) - dod_before, 150)
            self.assertEqual(int(prop_worn_spring["CRI"]) - cri_before, 150)
            self.assertEqual(int(prop_worn_spring["DAMADDR"]), damaddr_before_wear)
            self.assertEqual(int(prop_worn_spring["DAMCUTR"]), damcutr_before_wear)

            # Unequip via EMPTY_ENTITY_ID -> restores base MC skills & removes worn attrStr
            undress = self._call(prof, "Fashion", "DressUp", EMPTY_ENTITY_ID)
            self.assertEqual(undress["Status"], 0)
            self.assertEqual(undress["Avatar"]["FashionModelId"], 0)
            prop_undressed = undress["Avatar"]["SlotInfo"][0]["Property"]
            self.assertEqual(int(prop_undressed["DOD"]), dod_before)
            self.assertEqual(int(prop_undressed["CRI"]), cri_before)
            f_restored = self._call(prof, "Battle", "GetFightInfo", 11, 1111, 1)["Value"]["FightInfo"]
            mc_restored = f_restored["FightObjs"][0]["Heros"][0]
            self.assertEqual(int(mc_restored["NAId"]), base_naid)
            self.assertEqual(int(mc_restored["RAId"]), base_raid)
            self.assertEqual(str(mc_restored["LargePic"]), base_large)
            self.assertEqual(str(mc_restored["SmallPic"]), base_small)

            # Test 1607 compose ratio: 16070004 needs 200 shards per fashion
            prof._grant_resources_from_tuples([(1607, 16070004, 199)], source="test_1607", tx_prefix="t84:199")
            shard_row = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16070004)
            fail_199 = self._call(prof, "Goods", "GoodsUse", shard_row["Id"], 16070004, 199)
            self.assertEqual(fail_199["Status"], -1)
            self.assertEqual(self._goods_qty(prof, 16070004), 199)

            prof._grant_resources_from_tuples([(1607, 16070004, 251)], source="test_1607", tx_prefix="t84:450")
            shard_row = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16070004)
            ok_450 = self._call(prof, "Goods", "GoodsUse", shard_row["Id"], 16070004, 450)
            self.assertEqual(ok_450["Status"], 0)
            noel_copies = [f for f in prof.state["fashions"] if int(f["FashionModelId"]) == 19010001]
            self.assertEqual(len(noel_copies), 2)
            self.assertEqual(self._goods_qty(prof, 16070004), 50)

            # Test 16070001 (maxNum=60 -> 16060006)
            prof._grant_resources_from_tuples([(1607, 16070001, 59)], source="test_1607", tx_prefix="t84:59")
            g1_row = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16070001)
            self.assertEqual(self._call(prof, "Goods", "GoodsUse", g1_row["Id"], 16070001, 59)["Status"], -1)
            prof._grant_resources_from_tuples([(1607, 16070001, 1)], source="test_1607", tx_prefix="t84:60")
            g1_row = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16070001)
            self.assertEqual(self._call(prof, "Goods", "GoodsUse", g1_row["Id"], 16070001, 60)["Status"], 0)
            self.assertEqual(self._goods_qty(prof, 16070001), 0)
            self.assertEqual(self._goods_qty(prof, 16060006), 1)

            # Resolve duplicate 19010001 -> +200 shards 16070004 (total 250) -> StepUp remaining copy
            res_dup = self._call(prof, "Fashion", "Resolve", noel_copies[1]["Id"])
            self.assertEqual(res_dup["Status"], 0)
            self.assertEqual(self._goods_qty(prof, 16070004), 250)

            gold_before_step = int(prof.state["player"]["Gold"])
            step_res = self._call(prof, "Fashion", "StepUp", noel_copies[0]["Id"])
            self.assertEqual(step_res["Status"], 0)
            self.assertEqual(step_res["Value"]["FashionInfo"]["Step"], 1)
            self.assertEqual(self._goods_qty(prof, 16070004), 190)
            self.assertEqual(gold_before_step - int(prof.state["player"]["Gold"]), 600_000)
            final_slot0 = dict(prof.state["slots"][0]["Property"])

            # Persistence check across reload
            emu2 = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True)
            prof2 = emu2.profiles["normal"]
            self.assertEqual(prof2.state["slots"][0]["Property"], final_slot0)
            self.assertEqual(prof2._get_goods_qty(16070004), 190)
            self.assertTrue(any(int(f["FashionModelId"]) == 19010001 and int(f["Step"]) == 1 for f in prof2.state["fashions"]))


if __name__ == "__main__":
    unittest.main()
