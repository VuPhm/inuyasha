#!/usr/bin/env python3
"""Verify R7.39 Lianti (5700) client Lua patches & server_bundle inside signed APK 858."""

from __future__ import annotations

import argparse
import io
import json
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


class R739LuaTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r7_39_858_standalone.apk")

    def test_01_module_sub_and_shop_goods_models(self) -> None:
        ms = read_apk_lua(self.apk, "assets/src/Config/ModuleSubModel.luac")
        idx = ms.index("[5700] = {")
        block = ms[idx : idx + 280]
        self.assertIn("ifOpen = 1,", block)

        sg = read_apk_lua(self.apk, "assets/src/Config/ShopGoodsModel.luac")
        self.assertIn("items_count = 10,", sg)
        for gid in ("16050035", "16050036", "16050037", "16050038"):
            self.assertIn(f"goodsModelID = {gid}", sg)

    def test_02_player_formation_and_lian_hun_da_shi_guards(self) -> None:
        pf = read_apk_lua(self.apk, "assets/src/Formation/PlayerFormationLayer.luac")
        self.assertIn(
            'if NetworkResData:modulePlayerIsOpen(ModuleSub.eLianti) and NetworkResData:moduleIsOpenInServer(ModuleSub.eLianti) and self.mIsMyself then',
            pf,
        )
        self.assertIn("local function isLiantiMaxLv(lv)", pf)
        self.assertIn("if currentHero.LiantiLv == heroValue.LiantiLv and currentHero.LianTiNodeId == heroValue.LianTiNodeId then", pf)
        self.assertIn("if isLiantiMaxLv(currentHero.LiantiLv or 0) or (currentHero.LvUpExp or 0) <= 0 then", pf)

        lh = read_apk_lua(self.apk, "assets/src/Hero/LianHunDaShiLayer.luac")
        self.assertIn("local hero = v and v.HeroId and NetworkResData:getHero(v.HeroId)", lh)
        self.assertIn("if self.mRecentLevel >= #mLianhudashi or not mLianhudashi[self.mRecentLevel + 1] then", lh)
        self.assertIn("local deployedCnt = 0", lh)
        self.assertIn("local minLianLv = nil", lh)

    def test_03_server_bundle_game_data_and_version(self) -> None:
        with ZipFile(self.apk) as zf:
            ver = zf.read("assets/inubackend/version.txt").decode("utf-8").strip()
            self.assertEqual(ver, "5.0.4.98-r7.39-standalone-858")
            with ZipFile(io.BytesIO(zf.read("assets/inubackend/server_bundle.zip"))) as bz:
                emu_src = bz.read("emulator.py").decode("utf-8")
                r79_src = bz.read("r79_event_handlers.py").decode("utf-8")
                gd = json.loads(bz.read("game_data.json").decode("utf-8"))
                self.assertIn("Lianti.OneKeyFiveLvLianti", emu_src)
                self.assertIn("16050038", r79_src)
                self.assertEqual(int(gd["counts"]["lianti_lv"]), 101)
                self.assertEqual(int(gd["module_subs"]["5700"]["ifOpen"]), 1)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R739LuaTest.apk))
    args, rest = p.parse_known_args()
    R739LuaTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
