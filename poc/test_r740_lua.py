#!/usr/bin/env python3
"""Verify R7.40 PVPinter (6100) + WhosTheGod (6200) Lua patches & server_bundle inside APK 859."""

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


class R740LuaTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r7_40_859_standalone.apk")

    def test_01_challenge_list_and_pvpinter_scenes(self) -> None:
        cl = read_apk_lua(self.apk, "assets/src/Challenge/ChallengeListLayer.luac")
        self.assertIn("muduleId = ModuleSub.ePVPInter", cl)
        self.assertNotIn("--[[local isOpen = NetworkResData:moduleIsOpenInServer(ModuleSub.ePVPInter)", cl)

        csb = read_apk_lua(self.apk, "assets/src/Challenge/CrossServerBattleScene.luac")
        self.assertIn("eMostKing   = 8", csb)
        self.assertNotIn("eBronze     = 21", csb)
        self.assertIn("for i,v in ipairs(AnalysisStrResList(curRewStr)) do", csb)
        self.assertNotIn("\n        for i,v in ipairs(AnalysisStrResList(PvpinterLvRelation.items[PVPinterInfo.Lv].rankRewards)) do", csb)
        self.assertIn("local limitTimes = (rawLimit > 0) and rawLimit or (vipLv + 3)", csb)

        crank = read_apk_lua(self.apk, "assets/src/Challenge/CrossServerRankLayer.luac")
        self.assertIn("local lvRow = PvpinterLvRelation.items[tempData.PVPInterLv or 1] or PvpinterLvRelation.items[1]", crank)
        self.assertIn("local fInfo = retVal.Value.Formation or retVal.Value", crank)

        crew = read_apk_lua(self.apk, "assets/src/Challenge/CrossServerRewardLayer.luac")
        self.assertIn('[8] = {bg = "kfpw_35.png", hero = "kfpw_8.png"}', crew)
        self.assertNotIn(".rankRewards", crew)

        cbal = read_apk_lua(self.apk, "assets/src/Challenge/CrossServerBlanceLayer.luac")
        self.assertIn('[8] = "kfpw_8.png"', cbal)

        cshop = read_apk_lua(self.apk, "assets/src/Challenge/CrossServerShopLayer.luac")
        self.assertIn('"Đá Cảm Ngộ"', cshop)
        self.assertIn("local actualCost =", cshop)

        csb2 = read_apk_lua(self.apk, "assets/src/Challenge/CSBSecondScene.luac")
        self.assertIn('winSprite:setPosition(cc.p(k == 1 and 80 or -80,250))', csb2)
        self.assertIn("selfData.selfBattleRecord = retVal.Value.BattleReport or {}", csb2)
        self.assertIn("retVal.Value.FightInfo.ClientRes or retVal.Value.FightInfo", csb2)

    def test_02_server_bundle_and_version(self) -> None:
        with ZipFile(self.apk) as zf:
            ver = zf.read("assets/inubackend/version.txt").decode("utf-8").strip()
            self.assertEqual(ver, "5.0.4.98-r7.40-standalone-859")
            with ZipFile(io.BytesIO(zf.read("assets/inubackend/server_bundle.zip"))) as bz:
                pvp_src = bz.read("pvpinter_handlers.py").decode("utf-8")
                emu_src = bz.read("emulator.py").decode("utf-8")
                gd = json.loads(bz.read("game_data.json").decode("utf-8"))
                self.assertIn("class PVPinterHandlersMixin:", pvp_src)
                self.assertIn("PVPinterTop.BetReward", emu_src)
                for key in (
                    "pvpinter_lv",
                    "pvpinter_buynum",
                    "pvpinter_shop",
                    "pvpinter_win_box",
                    "pvpinter_top_gamble",
                    "pvpinter_top_reward",
                    "pvpinter_top_worship",
                ):
                    self.assertGreater(int(gd["counts"][key]), 0)
                self.assertEqual(int(gd["vip_model"]["6"]["buyKuafuNum"]), 9)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R740LuaTest.apk))
    args, rest = p.parse_known_args()
    R740LuaTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
