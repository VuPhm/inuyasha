#!/usr/bin/env python3
"""Verify R7.36 patched Lua scripts & server_bundle inside the signed APK 855."""

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


class R736LuaTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r7_36_855_standalone.apk")

    def test_store_and_purchase_patches_present(self) -> None:
        ss = read_apk_lua(self.apk, "assets/src/Store/StoreScene.luac")
        gpl = read_apk_lua(self.apk, "assets/src/Store/GoodsPurchaseLayer.luac")
        self.assertIn('text = "Reset Shop"', ss)
        self.assertIn('text = "Max"', gpl)

    def test_gem_compose_unequip_and_lv15_guard(self) -> None:
        ec = read_apk_lua(self.apk, "assets/src/Equipment/EquipmentComposeLayer.luac")
        mf = read_apk_lua(self.apk, "assets/src/Formation/MyFormationLayer.luac")
        gl = read_apk_lua(self.apk, "assets/src/Gem/GemLevelUpLayer.luac")
        self.assertIn("modelId = cardInfor.EquipModelId or cardInfor.TreasureModelId or cardInfor.ModelId,", ec)
        self.assertIn("local nextModel = self.mTempTable[self.mCellList[index[1]].ModelId + 1]", ec)
        self.assertIn('text = "Tháo"', mf)
        self.assertIn("self:GemCombatRequest(EMPTY_ENTITY_ID)", mf)
        self.assertIn("GemModel.items[self.mGemData.ModelId + 1]", gl)

    def test_daily_shop_reset_buttons_in_mystery_pvp_and_guild(self) -> None:
        ms = read_apk_lua(self.apk, "assets/src/Store/MysticalStoreScene.luac")
        ar = read_apk_lua(self.apk, "assets/src/Challenge/ArenaExchangeLayer.luac")
        gs = read_apk_lua(self.apk, "assets/src/Guild/GuildShopLayer.luac")
        self.assertIn('HttpRequest("MysteryShop", "ResetDaily"', ms)
        self.assertIn('HttpRequest("PVPShop", "ResetDaily"', ar)
        self.assertIn('HttpRequest("Guild", "ResetGuildShopDaily"', gs)

    def test_server_bundle_and_version_updated(self) -> None:
        with ZipFile(self.apk) as zf:
            ver = zf.read("assets/inubackend/version.txt").decode("utf-8").strip()
            self.assertEqual(ver, "5.0.4.98-r7.36-standalone-855")
            with ZipFile(io.BytesIO(zf.read("assets/inubackend/server_bundle.zip"))) as bz:
                emu_src = bz.read("emulator.py").decode("utf-8")
                guild_src = bz.read("guild_handlers.py").decode("utf-8")
                self.assertIn("vip_slot_relation", emu_src)
                self.assertIn("_rpc_mystery_shop_reset_daily", emu_src)
                self.assertIn("_rpc_pvp_shop_reset_daily", emu_src)
                self.assertIn("_rpc_guild_shop_reset_daily", guild_src)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R736LuaTest.apk))
    args, rest = p.parse_known_args()
    R736LuaTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
