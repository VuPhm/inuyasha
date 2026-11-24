#!/usr/bin/env python3
"""Verify R7.35 patched Store Lua scripts & server_bundle inside the signed APK."""

import argparse
import io
from pathlib import Path
import unittest
from zipfile import ZipFile

from patch_vn_apk import XXTEA_KEY, XXTEA_SIGN, xxtea_decrypt


def read_apk_lua(apk: Path, asset_path: str) -> str:
    with ZipFile(apk) as zf:
        raw = zf.read(asset_path)
    if raw.startswith(XXTEA_SIGN):
        raw = xxtea_decrypt(raw[len(XXTEA_SIGN) :], XXTEA_KEY)
    return raw.decode("utf-8", errors="replace")


class R735LuaTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r7_35_854_standalone.apk")

    def test_store_scene_has_reset_shop_button_and_dynamic_cost_check(self) -> None:
        src = read_apk_lua(self.apk, "assets/src/Store/StoreScene.luac")
        self.assertIn("self.mButtonResetShop", src)
        self.assertIn('text = "Reset Shop"', src)
        self.assertIn('HttpRequest("ShopGoods", "ResetDaily", {}', src)
        self.assertIn("v.DynamicPrice = props.DynamicPrice", src)
        self.assertIn("local totalCost = self.mSelGoodsData.CurrPrice * count", src)

    def test_goods_purchase_layer_has_max_button_and_compute_total_cost(self) -> None:
        src = read_apk_lua(self.apk, "assets/src/Store/GoodsPurchaseLayer.luac")
        self.assertIn('text = "Max"', src)
        self.assertIn("GoodsPurchaseLayer:computeTotalCost(count)", src)
        self.assertIn("GoodsPurchaseLayer:refreshPurchaseDisplay()", src)
        self.assertIn("if self.mCurGoods.GoodsModelId == 16030003 then", src)

    def test_server_bundle_and_version_updated(self) -> None:
        with ZipFile(self.apk) as zf:
            ver = zf.read("assets/inubackend/version.txt").decode("utf-8").strip()
            self.assertEqual(ver, "5.0.4.98-r7.35-standalone-854")
            with ZipFile(io.BytesIO(zf.read("assets/inubackend/server_bundle.zip"))) as bz:
                emu_src = bz.read("emulator.py").decode("utf-8")
                self.assertIn("_rpc_shop_reset_daily", emu_src)
                self.assertIn("SOUL_BOX_SHOP_MAX_NUM = 200", emu_src)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R735LuaTest.apk))
    args, rest = p.parse_known_args()
    R735LuaTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
