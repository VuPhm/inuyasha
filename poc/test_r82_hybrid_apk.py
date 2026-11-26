#!/usr/bin/env python3
"""Verify R8.2 Hybrid Standalone APK (com.cmn.inuyasha.revival) packaging, embedded backend & Lua UI."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from zipfile import ZipFile

from build_standalone_apk import _validate_lua_source_quotes
from patch_vn_apk import APKSIGNER, XXTEA_KEY, XXTEA_SIGN, xxtea_decrypt

SDK_AAPT2 = Path("/Users/vup/Library/Android/sdk/build-tools/36.0.0/aapt2")


def read_apk_lua(apk: Path, asset_path: str) -> str:
    with ZipFile(apk) as zf:
        raw = zf.read(asset_path)
    if raw.startswith(XXTEA_SIGN):
        raw = xxtea_decrypt(raw[len(XXTEA_SIGN) :], XXTEA_KEY)
    return raw.decode("utf-8", errors="replace")


class R82HybridApkTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r8_16_875_hybrid.apk")

    def test_01_packaging_signature_and_embedded_hybrid_backend(self) -> None:
        self.assertTrue(self.apk.is_file(), f"Missing built APK: {self.apk}")
        smali_txt = Path("android/smali/com/cmn/inuyasha/standalone/LocalBackendManager.smali").read_text(encoding="utf-8")
        self.assertIn("isLoopbackHealthyDirect", smali_txt)
        self.assertIn("Looper;->getMainLooper", smali_txt)
        self.assertIn("INUYASHA_APK_VERSION_CODE", smali_txt)
        self.assertIn("INUYASHA_CLIENT_OTA_DIR", smali_txt)
        with ZipFile(self.apk) as zf:
            names = set(zf.namelist())
            self.assertIn("lib/armeabi/libinubackend.so", names)
            self.assertIn("assets/inubackend/server_bundle.zip", names)
            self.assertIn("assets/inubackend/stdlib.zip", names)
            self.assertIn("assets/src/System/HybridSyncLayer.luac", names)
            self.assertIn("assets/src/System/OtaUpdateLayer.luac", names)

            bundle_bytes = zf.read("assets/inubackend/server_bundle.zip")
            with ZipFile(io.BytesIO(bundle_bytes)) as bzf:
                bnames = set(bzf.namelist())
                for req_py in (
                    "hybrid_sync.py",
                    "ota_updater.py",
                    "emulator.py",
                    "emulator_common.py",
                    "pvp_boss_handlers.py",
                    "treasure_rebirth_handlers.py",
                    "progression_handlers.py",
                ):
                    self.assertIn(req_py, bnames)
                self.assertIn("sync_ca_bundle.pem", bnames)
                trunc_marker = "truncated for " + "diff preview"
                for bname in sorted(bnames):
                    if bname.endswith(".py"):
                        py_raw = bzf.read(bname)
                        self.assertLess(len(py_raw), 450 * 1024, f"{bname} exceeds 450 KiB")
                        py_src = py_raw.decode("utf-8")
                        self.assertNotIn(trunc_marker, py_src, f"Corrupted file in bundle: {bname}")
                        compile(py_src, bname, "exec")
                hs_src = bzf.read("hybrid_sync.py").decode("utf-8")
                self.assertIn("https://inuyasha-sync-hub.vuphamletruong.workers.dev", hs_src)
                ca_pem = bzf.read("sync_ca_bundle.pem").decode("utf-8")
                self.assertIn("BEGIN CERTIFICATE", ca_pem)

        if SDK_AAPT2.is_file():
            badging = subprocess.check_output(
                [str(SDK_AAPT2), "dump", "badging", str(self.apk)],
                text=True,
                errors="replace",
            )
            self.assertIn("name='com.cmn.inuyasha.revival'", badging)
            self.assertIn("versionCode='875'", badging)
            self.assertIn("versionName='5.0.4.98-r8.16-hybrid'", badging)
            self.assertIn("application-label:'InuYasha Hybrid'", badging)
            self.assertIn("targetSdkVersion:'30'", badging)

        verify_res = subprocess.run(
            [str(APKSIGNER), "verify", str(self.apk)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(verify_res.returncode, 0, verify_res.stderr)

    def test_02_hybrid_sync_lua_ui_and_gameplay_patches(self) -> None:
        hs_lua = read_apk_lua(self.apk, "assets/src/System/HybridSyncLayer.luac")
        _validate_lua_source_quotes(hs_lua, "HybridSyncLayer.luac")
        self.assertNotIn("\u00b7", hs_lua)
        self.assertNotIn("{6c0101}", hs_lua)
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
            "Hồ sơ liên kết",
            "reloadGameScene(lr.bound_user_id)",
            "lr.switched_account",
        ):
            self.assertIn(needle, hs_lua)

        sg = read_apk_lua(self.apk, "assets/src/Login/StartGameScene.luac")
        self.assertIn('require("System.HybridSyncLayer").new()', sg)
        self.assertIn("Đồng Bộ Cloud", sg)
        self.assertIn("mLocalRetryCount", sg)
        self.assertIn('require("System.OtaUpdateLayer").new', sg)
        self.assertIn("Cập Nhật", sg)
        self.assertIn("/ota/check", sg)

        ota_lua = read_apk_lua(self.apk, "assets/src/System/OtaUpdateLayer.luac")
        _validate_lua_source_quotes(ota_lua, "OtaUpdateLayer.luac")
        for needle in ("/ota/check", "/ota/apply", "/ota/status", "/ota/restart", "Cập Nhật Ngay", "Tải APK Ngay", "IPlatform:getInstance():openUrl"):
            self.assertIn(needle, ota_lua)

        main_lua = read_apk_lua(self.apk, "assets/src/main.luac")
        _validate_lua_source_quotes(main_lua, "main.luac")
        self.assertIn('wp .. "Download/"', main_lua)
        self.assertIn('dlRoot .. "src/"', main_lua)
        self.assertIn('fu:setSearchPaths(nextPaths)', main_lua)

        asw = read_apk_lua(self.apk, "assets/src/System/AccountSwitchLayer.luac")
        _validate_lua_source_quotes(asw, "AccountSwitchLayer.luac")
        self.assertIn('require("System.HybridSyncLayer").new()', asw)
        self.assertIn("Đồng Bộ Cloud", asw)
        self.assertIn("Thử Lại", asw)
        self.assertIn("Xác nhận chuyển sang tài khoản", asw)
        self.assertIn('action = "delete"', asw)
        self.assertIn("Xóa TK", asw)
        self.assertNotIn("Reset TK", asw)
        self.assertIn("self:addChild(box, 200)", asw)

        # Item 1: System menu button + z-order / parent=self toast fix
        sys_lua = read_apk_lua(self.apk, "assets/src/System/SystemLayer.luac")
        self.assertIn('require("System.HybridSyncLayer").new(), 50', sys_lua)
        self.assertIn("Đồng Bộ Cloud", sys_lua)
        self.assertIn("Thử Lại", hs_lua)
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

        # Native speed/auto button in PVE; x1/x2 fallback toggle only when native button is hidden
        bui = read_apk_lua(self.apk, "assets/src/ComBattle/BattleUILayer.luac")
        _validate_lua_source_quotes(bui, "BattleUILayer.luac")
        for needle in ("if not hasHostedBtn then", "btnSpeedToggle", "BattleData.game.userSpeed", "Tốc: x2", "Tốc: x1"):
            self.assertIn(needle, bui)
        bdata = read_apk_lua(self.apk, "assets/src/ComBattle/BattleData.luac")
        _validate_lua_source_quotes(bdata, "BattleData.luac")
        self.assertIn("BattleData.game.userSpeed", bdata)
        self.assertIn("not _tuoguanDisp", bdata)

    def test_03_extracted_server_bundle_boots_and_serves_health_and_hybrid_status(self) -> None:
        self.assertTrue(self.apk.is_file(), f"Missing built APK: {self.apk}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            srv_dir = tdp / "server"
            sav_dir = tdp / "saves"
            srv_dir.mkdir(parents=True)
            sav_dir.mkdir(parents=True)
            with ZipFile(self.apk) as zf:
                bundle_bytes = zf.read("assets/inubackend/server_bundle.zip")
            with ZipFile(io.BytesIO(bundle_bytes)) as bzf:
                bzf.extractall(srv_dir)

            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(srv_dir / "emulator.py"),
                    "--env",
                    "dev",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--data-dir",
                    str(sav_dir),
                    "--trace-path",
                    str(sav_dir / "rpc_trace.log"),
                ],
                cwd=str(srv_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                health = None
                for _ in range(150):
                    if proc.poll() is not None:
                        out, _ = proc.communicate(timeout=2)
                        self.fail(f"Extracted backend exited early (rc={proc.returncode}): {out}")
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as r:
                            if r.status == 200:
                                health = json.loads(r.read().decode())
                                break
                    except (OSError, urllib.error.URLError, json.JSONDecodeError):
                        time.sleep(0.05)
                self.assertIsNotNone(health, "Extracted server_bundle backend failed to respond on /health")
                self.assertTrue(health.get("ok"), f"Unexpected /health payload: {health}")

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/hybrid/status", timeout=2) as r:
                    self.assertEqual(r.status, 200)
                    st = json.loads(r.read().decode())
                self.assertTrue(st["ok"])

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/ota/status", timeout=2) as r:
                    self.assertEqual(r.status, 200)
                    ota_st = json.loads(r.read().decode())
                self.assertTrue(ota_st["ok"])
                self.assertEqual(ota_st["update_kind"], "none")
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
                if proc.stdout is not None:
                    proc.stdout.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R82HybridApkTest.apk))
    args, rest = p.parse_known_args()
    R82HybridApkTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
