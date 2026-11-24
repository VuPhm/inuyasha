#!/usr/bin/env python3
"""Verify R8.2 Hybrid Standalone APK (com.cmn.inuyasha.revival) packaging, embedded backend & Lua UI."""

from __future__ import annotations

import argparse
import io
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


class R82HybridApkTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r8_3_862_hybrid.apk")

    def test_01_packaging_signature_and_embedded_hybrid_backend(self) -> None:
        self.assertTrue(self.apk.is_file(), f"Missing built APK: {self.apk}")
        with ZipFile(self.apk) as zf:
            names = set(zf.namelist())
            self.assertIn("lib/armeabi/libinubackend.so", names)
            self.assertIn("assets/inubackend/server_bundle.zip", names)
            self.assertIn("assets/inubackend/stdlib.zip", names)
            self.assertIn("assets/src/System/HybridSyncLayer.luac", names)

            bundle_bytes = zf.read("assets/inubackend/server_bundle.zip")
            with ZipFile(io.BytesIO(bundle_bytes)) as bzf:
                bnames = set(bzf.namelist())
                self.assertIn("hybrid_sync.py", bnames)
                self.assertIn("sync_ca_bundle.pem", bnames)
                self.assertIn("emulator.py", bnames)
                hs_src = bzf.read("hybrid_sync.py").decode("utf-8")
                self.assertIn("https://inuyasha-sync-hub.vuphamletruong.workers.dev", hs_src)
                compile(hs_src, "hybrid_sync.py", "exec")
                ca_pem = bzf.read("sync_ca_bundle.pem").decode("utf-8")
                self.assertIn("BEGIN CERTIFICATE", ca_pem)

        if SDK_AAPT2.is_file():
            badging = subprocess.check_output(
                [str(SDK_AAPT2), "dump", "badging", str(self.apk)],
                text=True,
                errors="replace",
            )
            self.assertIn("name='com.cmn.inuyasha.revival'", badging)
            self.assertIn("versionCode='862'", badging)
            self.assertIn("versionName='5.0.4.98-r8.3-hybrid'", badging)
            self.assertIn("application-label:'InuYasha Hybrid'", badging)

        verify_res = subprocess.run(
            [str(APKSIGNER), "verify", str(self.apk)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(verify_res.returncode, 0, verify_res.stderr)

    def test_02_hybrid_sync_lua_ui_and_gameplay_patches(self) -> None:
        hs_lua = read_apk_lua(self.apk, "assets/src/System/HybridSyncLayer.luac")
        for needle in (
            "127.0.0.1:18082",
            "/hybrid/status",
            "/hybrid/test",
            "/hybrid/register",
            "/hybrid/login",
            "/hybrid/sync",
            "/hybrid/pull_save",
            "/hybrid/logout",
            "Xung Đột Dữ Liệu",
            "Tải Cloud",
            "Đẩy Máy Lên",
        ):
            self.assertIn(needle, hs_lua)

        sg = read_apk_lua(self.apk, "assets/src/Login/StartGameScene.luac")
        self.assertIn('require("System.HybridSyncLayer").new()', sg)
        self.assertIn("Đồng Bộ Cloud", sg)

        asw = read_apk_lua(self.apk, "assets/src/System/AccountSwitchLayer.luac")
        self.assertIn('require("System.HybridSyncLayer").new()', asw)
        self.assertIn("Đồng Bộ Cloud", asw)
        self.assertIn("Xác nhận chuyển sang tài khoản", asw)
        self.assertIn('action = "delete"', asw)
        self.assertIn("Xóa TK", asw)
        self.assertNotIn("Reset TK", asw)
        self.assertIn("self:addChild(box, 200)", asw)

        # Item 1: System menu button + z-order / parent=self toast fix
        sys_lua = read_apk_lua(self.apk, "assets/src/System/SystemLayer.luac")
        self.assertIn('require("System.HybridSyncLayer").new(), 50', sys_lua)
        self.assertIn("Đồng Bộ Cloud", sys_lua)
        self.assertIn("ui.showFlashView({parent = self,", hs_lua)
        self.assertIn("self:addChild(box, 200)", hs_lua)
        self.assertIn("205)", sg)

        # Item 4: Treasure continuous hunt & multi-compose
        td_lua = read_apk_lua(self.apk, "assets/src/Grab/TreasureDebrisLayer.luac")
        self.assertIn("Tầm Bảo +1", td_lua)
        self.assertIn("H.Thành Tất", td_lua)
        self.assertIn("Tầm Bảo Tiếp", td_lua)

        # Item 5: Friend Sparring in ContactLayer & FriendScene
        cl_lua = read_apk_lua(self.apk, "assets/src/Friend/ContactLayer.luac")
        self.assertIn('"FriendFight"', cl_lua)
        self.assertIn("Giao Hữu (Đấu)", cl_lua)
        fs_lua = read_apk_lua(self.apk, "assets/src/Friend/FriendScene.luac")
        self.assertIn('"FriendFight"', fs_lua)
        self.assertIn('"Đấu"', fs_lua)

        # Retained shared gameplay patches through R7.39 & R7.40
        pf = read_apk_lua(self.apk, "assets/src/Formation/PlayerFormationLayer.luac")
        self.assertIn("ModuleSub.eLianti", pf)
        csb = read_apk_lua(self.apk, "assets/src/Challenge/CrossServerBattleScene.luac")
        self.assertIn("eMostKing   = 8", csb)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R82HybridApkTest.apk))
    args, rest = p.parse_known_args()
    R82HybridApkTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
