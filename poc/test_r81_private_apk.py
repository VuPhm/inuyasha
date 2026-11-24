#!/usr/bin/env python3
"""Verify R8.1 Online Private Server APK (com.cmn.inuyasha.private) packaging & Lua patches."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import unittest
from zipfile import ZipFile

from patch_vn_apk import APKSIGNER, XXTEA_KEY, XXTEA_SIGN, xxtea_decrypt

SDK_AAPT2 = Path("/Users/vup/Library/Android/sdk/build-tools/36.0.0/aapt2")


def read_apk_lua(apk: Path, asset_path: str) -> str:
    with ZipFile(apk) as zf:
        raw = zf.read(asset_path)
    if raw.startswith(XXTEA_SIGN):
        raw = xxtea_decrypt(raw[len(XXTEA_SIGN) :], XXTEA_KEY)
    return raw.decode("utf-8", errors="replace")


class R81PrivateApkTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.private_r8_1_860.apk")

    def test_01_packaging_manifest_and_no_embedded_backend(self) -> None:
        self.assertTrue(self.apk.is_file(), f"Missing built APK: {self.apk}")
        with ZipFile(self.apk) as zf:
            names = set(zf.namelist())
            self.assertFalse(any(n.startswith("assets/inubackend/") for n in names))
            self.assertNotIn("lib/armeabi/libinubackend.so", names)

        if SDK_AAPT2.is_file():
            badging = subprocess.check_output(
                [str(SDK_AAPT2), "dump", "badging", str(self.apk)],
                text=True,
                errors="replace",
            )
            self.assertIn("name='com.cmn.inuyasha.private'", badging)
            self.assertIn("versionCode='860'", badging)
            self.assertIn("versionName='5.0.4.98-r8.1-private'", badging)

        verify_res = subprocess.run(
            [str(APKSIGNER), "verify", str(self.apk)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(verify_res.returncode, 0, verify_res.stderr)

    def test_02_private_login_account_and_gameplay_lua(self) -> None:
        gl = read_apk_lua(self.apk, "assets/src/Login/GameLoginScene.luac")
        for needle in (
            "PrivateServerAuth.txt",
            "/auth/login",
            "/auth/register",
            "/auth/info",
            "192.168.100.173:8080",
        ):
            self.assertIn(needle, gl)
        self.assertNotIn("127.0.0.1:18082", gl)

        sg = read_apk_lua(self.apk, "assets/src/Login/StartGameScene.luac")
        self.assertIn("PrivateServerAuth.txt", sg)
        self.assertIn("Đổi Tài Khoản", sg)
        self.assertNotIn("127.0.0.1:18082", sg)

        asw = read_apk_lua(self.apk, "assets/src/System/AccountSwitchLayer.luac")
        self.assertIn("/auth/change_password", asw)
        self.assertIn("Đăng Xuất / Đổi Tài Khoản", asw)
        self.assertNotIn("127.0.0.1:18082", asw)

        rc = read_apk_lua(self.apk, "assets/src/Store/RechargeScene.luac")
        self.assertIn("(Private)?", rc)
        self.assertNotIn("(Offline)?", rc)
        self.assertIn("Nạp bị giới hạn hoặc tắt trên server", rc)

        # Retained shared gameplay patches through R7.39 & R7.40
        pf = read_apk_lua(self.apk, "assets/src/Formation/PlayerFormationLayer.luac")
        self.assertIn("ModuleSub.eLianti", pf)
        csb = read_apk_lua(self.apk, "assets/src/Challenge/CrossServerBattleScene.luac")
        self.assertIn("eMostKing   = 8", csb)
        self.assertIn("local limitTimes = (rawLimit > 0) and rawLimit or (vipLv + 3)", csb)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R81PrivateApkTest.apk))
    args, rest = p.parse_known_args()
    R81PrivateApkTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
