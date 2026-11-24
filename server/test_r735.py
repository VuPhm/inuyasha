"""Delta coverage for R7.35: Daily Shop Reset & Soul Box (16030003) 200x cap + DynamicPrice."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
import sys
import tempfile
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import GameEmulatorState, SOUL_BOX_GOODS_ID, SOUL_BOX_SHOP_MAX_NUM  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R735ShopResetAndSoulBoxTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 23, 14, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    def test_01_soul_box_limit_200_at_vip0_while_other_items_keep_vn_vip_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["ShopTester", 0]})
            res = self._call(p, "ShopGoods", "ShopGoodsList")
            self.assertEqual(res["Status"], 0)
            by_id = {int(row["GoodsModelId"]): row for row in res["Value"]}

            # 16030003 raised to 200 even at VIP 0, with DynamicPrice [5, 10, 15, 20]
            box = by_id[SOUL_BOX_GOODS_ID]
            self.assertEqual(box["MaxNum"], SOUL_BOX_SHOP_MAX_NUM)
            self.assertEqual(box["Num"], 0)
            self.assertEqual(box["CurrPrice"], 5)
            self.assertEqual([d["NewPrice"] for d in box["DynamicPrice"]], [5, 10, 15, 20])

            # Other VN shop items preserve exact VIP 0 VipBuyLimitModel caps
            self.assertEqual(by_id[16030006]["MaxNum"], 6)
            self.assertEqual(by_id[16030008]["MaxNum"], 6)
            self.assertEqual(by_id[16040005]["MaxNum"], 4)
            self.assertEqual(by_id[16050016]["MaxNum"], -1)
            self.assertNotIn("DynamicPrice", by_id[16040005])

    def test_02_bulk_buy_200_soul_boxes_dynamic_cost_and_use_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=30, vip_lv=3, source="test_r735")
            p.state["player"]["Diamond"] = 5_000
            exp_before = int(p.state["player"]["HeroEXP"])

            # 200 boxes: 5 + 10 + 15 + 197 * 20 = 3970 Diamonds
            buy = self._call(p, "ShopGoods", "BuyGoods", SOUL_BOX_GOODS_ID, 200)
            self.assertEqual(buy["Status"], 0)
            self.assertEqual(int(p.state["player"]["Diamond"]), 5_000 - 3_970)
            self.assertEqual(buy["Value"]["Num"], 200)
            self.assertEqual(buy["Value"]["MaxNum"], 200)
            self.assertEqual(buy["Value"]["CurrPrice"], 20)
            self.assertEqual([d["NewPrice"] for d in buy["Value"]["DynamicPrice"]], [20])

            # Buying 1 more before reset is rejected
            over = self._call(p, "ShopGoods", "BuyGoods", SOUL_BOX_GOODS_ID, 1)
            self.assertEqual(over["Status"], -1)

            # Single stack of 200 granted and usable in one shot -> +600,000 HeroEXP
            stacks = [g for g in p.state["goods"] if int(g["GoodsModelId"]) == SOUL_BOX_GOODS_ID]
            self.assertEqual(len(stacks), 1)
            self.assertEqual(int(stacks[0]["Num"]), 200)
            used = self._call(p, "Goods", "GoodsUse", stacks[0]["Id"], SOUL_BOX_GOODS_ID, 200)
            self.assertEqual(used["Status"], 0)
            self.assertEqual(int(p.state["player"]["HeroEXP"]), exp_before + 200 * 3000)

    def test_03_reset_daily_resets_shop_preserves_vip_gift_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=30, vip_lv=3, source="test_r735")
            p.state["player"]["Diamond"] = 10_000

            # Buy VIP gift 1 and 200 soul boxes
            vip_gifts = self._call(p, "ShopGift", "ShopGiftList")["Value"]
            first_gift_id = int(vip_gifts[0]["GoodsModelId"])
            self.assertEqual(self._call(p, "ShopGift", "BuyGift", first_gift_id, 1)["Status"], 0)
            self.assertEqual(self._call(p, "ShopGoods", "BuyGoods", SOUL_BOX_GOODS_ID, 200)["Status"], 0)

            # Free ShopGoods.ResetDaily resets daily shop counts & dynamic price back to step 1
            reset_res = self._call(p, "ShopGoods", "ResetDaily")
            self.assertEqual(reset_res["Status"], 0)
            by_id = {int(r["GoodsModelId"]): r for r in reset_res["Value"]}
            self.assertEqual(by_id[SOUL_BOX_GOODS_ID]["Num"], 0)
            self.assertEqual(by_id[SOUL_BOX_GOODS_ID]["CurrPrice"], 5)
            self.assertEqual([d["NewPrice"] for d in by_id[SOUL_BOX_GOODS_ID]["DynamicPrice"]], [5, 10, 15, 20])
            self.assertEqual(p.state["shop_daily_reset_count"], 1)

            # VIP gift stays bought; can buy another 200 soul boxes immediately
            gifts_after = {int(g["GoodsModelId"]): int(g["Num"]) for g in self._call(p, "ShopGift", "ShopGiftList")["Value"]}
            self.assertEqual(gifts_after[first_gift_id], 1)
            self.assertEqual(self._call(p, "ShopGoods", "BuyGoods", SOUL_BOX_GOODS_ID, 200)["Status"], 0)

            # Save/reload preserves reset count and bought count on same day
            reloaded = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True, trace_path=Path(tmp) / "rpc2.log")
            reloaded.clock.set_fixed(_ts_vn(2026, 11, 23, 20, 0))
            rp = reloaded.profiles["normal"]
            info = self._call(rp, "ShopGoods", "GetShopGoodsInfo", SOUL_BOX_GOODS_ID)["Value"][0]
            self.assertEqual(info["Num"], 200)
            self.assertEqual(rp.state["shop_daily_reset_count"], 1)

    def test_04_automatic_utc7_daily_rollover_resets_shop_bought(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp, ts=_ts_vn(2026, 11, 23, 23, 59))
            p.admin_prepare_account(target_lv=30, vip_lv=3, source="test_r735")
            p.state["player"]["Diamond"] = 5_000
            self.assertEqual(self._call(p, "ShopGoods", "BuyGoods", SOUL_BOX_GOODS_ID, 10)["Status"], 0)
            before = self._call(p, "ShopGoods", "GetShopGoodsInfo", SOUL_BOX_GOODS_ID)["Value"][0]
            self.assertEqual(before["Num"], 10)

            # Cross UTC+7 midnight -> shop_bought auto-resets
            emu.clock.set_fixed(_ts_vn(2026, 11, 24, 0, 1))
            after = self._call(p, "ShopGoods", "GetShopGoodsInfo", SOUL_BOX_GOODS_ID)["Value"][0]
            self.assertEqual(after["Num"], 0)
            self.assertEqual(after["CurrPrice"], 5)
            self.assertEqual([d["NewPrice"] for d in after["DynamicPrice"]], [5, 10, 15, 20])


if __name__ == "__main__":
    unittest.main()
