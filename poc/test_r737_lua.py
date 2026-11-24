#!/usr/bin/env python3
"""Verify R7.37 patched Lua configs, multi-banner UI, PNG assets, and server_bundle inside signed APK 856."""

import argparse
import io
from pathlib import Path
import re
import unittest
from zipfile import ZipFile

from patch_vn_apk import XXTEA_KEY, XXTEA_SIGN, xxtea_decrypt


def read_apk_lua(apk: Path, asset_path: str) -> str:
    with ZipFile(apk) as zf:
        raw = zf.read(asset_path)
    if raw.startswith(XXTEA_SIGN):
        raw = xxtea_decrypt(raw[len(XXTEA_SIGN) :], XXTEA_KEY)
    return raw.decode("utf-8", errors="replace")


def png_dimensions(raw: bytes) -> tuple[int, int]:
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "Invalid PNG signature"
    w = int.from_bytes(raw[16:20], "big")
    h = int.from_bytes(raw[20:24], "big")
    return w, h


class R737LuaTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r7_37_856_standalone.apk")

    def test_01_pr_model_and_hero_pr_relation_red_treasures(self) -> None:
        pr_lua = read_apk_lua(self.apk, "assets/src/Config/PrModel.luac")
        self.assertIn("items_count = 594,", pr_lua)
        for bid in range(573, 595):
            self.assertIn(f"[{bid}] = {{", pr_lua)
        self.assertIn('member = "14022001"', pr_lua)
        self.assertIn('member = "14022002"', pr_lua)

        hpr_lua = read_apk_lua(self.apk, "assets/src/Config/HeroPrRelation.luac")
        for hid in (
            12011002, 12011003, 12011004,
            12012003, 12012004, 12012005,
            12013003, 12013004, 12013005,
            12015022, 12015023,
        ):
            m = re.search(rf"^\s{{8}}\[{hid}\]\s*=\s*\{{(.*?)^\s{{8}}\}}", hpr_lua, re.M | re.S)
            self.assertIsNotNone(m, msg=f"Missing HeroPrRelation[{hid}]")
            body = m.group(1)
            self.assertIn("[7] = {", body)
            self.assertIn("[8] = {", body)

        tr_lua = read_apk_lua(self.apk, "assets/src/Config/TreasureModel.luac")
        for tid, first_hero in (
            (14012001, 12011002),
            (14012002, 12011003),
            (14022001, 12011002),
            (14022002, 12011003),
        ):
            m = re.search(rf"^\s{{8}}\[{tid}\]\s*=\s*\{{(.*?)^\s{{8}}\}}", tr_lua, re.M | re.S)
            self.assertIsNotNone(m)
            self.assertIn(f"prHeroModelIds = {{\n                {first_hero},", m.group(1))

    def test_02_banner_84_85_86_models_and_tabs(self) -> None:
        trm = read_apk_lua(self.apk, "assets/src/Config/TimedRecruitModel.luac")
        for pic in ("sy_157", "sy_158", "sy_159"):
            self.assertIn(f'btnPic = "{pic}"', trm)

        gor = read_apk_lua(self.apk, "assets/src/Config/GoodsOutputRelation.luac")
        for pic in ("xshd_101", "xshd_117", "xshd_100", "xshd_118", "xshd_103", "xshd_98", "xshd_102", "xshd_119", "xshd_99"):
            self.assertIn(f'pic = "{pic}"', gor)

        ltr = read_apk_lua(self.apk, "assets/src/TimedActivity/LimittedTimedRecruitLayer.luac")
        self.assertIn('[84] = "Phe I (84)"', ltr)
        self.assertIn('[85] = "Phe S (85)"', ltr)
        self.assertIn('[86] = "Phe N (86)"', ltr)
        self.assertIn("local stepX = bCount > 3 and 142 or 160", ltr)

    def test_03_png_assets_and_server_bundle(self) -> None:
        with ZipFile(self.apk) as zf:
            for name in ("sy_157.png", "sy_158.png", "sy_159.png"):
                self.assertEqual(png_dimensions(zf.read(f"assets/res/ui/{name}")), (92, 92))
            for name in ("xshd_117.png", "xshd_118.png", "xshd_119.png"):
                self.assertEqual(png_dimensions(zf.read(f"assets/res/ui/{name}")), (212, 385))

            ver = zf.read("assets/inubackend/version.txt").decode("utf-8").strip()
            self.assertEqual(ver, "5.0.4.98-r7.37-standalone-856")
            with ZipFile(io.BytesIO(zf.read("assets/inubackend/server_bundle.zip"))) as bz:
                gd = bz.read("game_data.json").decode("utf-8")
                self.assertIn('"594"', gd)
                self.assertIn('"sy_159"', gd)
                er = bz.read("event_runtime.py").decode("utf-8")
                self.assertIn('"timed_recruit:86"', er)
                r79 = bz.read("r79_event_handlers.py").decode("utf-8")
                self.assertIn("14022001", r79)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R737LuaTest.apk))
    args, rest = p.parse_known_args()
    R737LuaTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
