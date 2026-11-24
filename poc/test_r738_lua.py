#!/usr/bin/env python3
"""Verify R7.38 1-tap 1M diamond UI & server_bundle inside signed APK 857."""

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


class R738LuaTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r7_38_857_standalone.apk")

    def test_01_recharge_scene_one_tap_1m_kc(self) -> None:
        rs = read_apk_lua(self.apk, "assets/src/Store/RechargeScene.luac")
        self.assertIn("com.cmn.inuyasha.gem1000000", rs)
        self.assertIn('"Nạp 1 chạm (Miễn phí)"', rs)
        self.assertIn('"Nạp 1M"', rs)
        self.assertIn('"1.000.000 KC"', rs)
        self.assertIn('"Đã nạp +1.000.000 KC!"', rs)
        self.assertIn('HttpRequest("PlayerCharge", "ConfirmOrder", {productInfo.ProductId, orderId}', rs)

    def test_02_server_bundle_and_version(self) -> None:
        with ZipFile(self.apk) as zf:
            ver = zf.read("assets/inubackend/version.txt").decode("utf-8").strip()
            self.assertEqual(ver, "5.0.4.98-r7.38-standalone-857")
            with ZipFile(io.BytesIO(zf.read("assets/inubackend/server_bundle.zip"))) as bz:
                emu_src = bz.read("emulator.py").decode("utf-8")
                r79_src = bz.read("r79_event_handlers.py").decode("utf-8")
                self.assertIn("com.cmn.inuyasha.gem1000000", emu_src)
                self.assertIn("16020057", r79_src)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R738LuaTest.apk))
    args, rest = p.parse_known_args()
    R738LuaTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
