#!/usr/bin/env python3
"""Verify R7.21 patched Lua scripts inside the signed APK (error guards & InviteAll refresh)."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from patch_vn_apk import XXTEA_KEY, XXTEA_SIGN, xxtea_decrypt


def read_apk_lua(apk: Path, asset_path: str) -> str:
    with ZipFile(apk) as zf:
        raw = zf.read(asset_path)
    if raw.startswith(XXTEA_SIGN):
        raw = xxtea_decrypt(raw[len(XXTEA_SIGN):], XXTEA_KEY)
    return raw.decode("utf-8", errors="replace")


class R721LuaTest(unittest.TestCase):
    apk = Path("analysis/vn/patched/com.cmn.inuyasha.revival_r7_21_standalone.apk")

    def test_instance_new_main_scene_checks_status_before_entering_wait_scene(self):
        src = read_apk_lua(self.apk, "assets/src/InstanceZones/InstanceNewMainScene.luac")
        self.assertIn(
            "if event and event.Status == 0 and event.Value and event.Value.TeamsInfo then",
            src,
        )
        self.assertIn(
            "if event and event.Status == 0 and event.Value and event.Value.TeamId then",
            src,
        )

    def test_team_wait_scene_refreshes_immediately_on_invite_all(self):
        src = read_apk_lua(self.apk, "assets/src/InstanceZones/TeamWaitScene.luac")
        self.assertIn("if self.mSelectType == 1 then", src)
        self.assertIn("self:requestTeamInfor()", src)

    def test_server_bundle_includes_teambattle_handlers(self):
        with ZipFile(self.apk) as zf:
            names = set(zf.namelist())
            self.assertIn("assets/inubackend/server_bundle.zip", names)
            import io

            with ZipFile(io.BytesIO(zf.read("assets/inubackend/server_bundle.zip"))) as bz:
                self.assertIn("teambattle_handlers.py", bz.namelist())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apk", default=str(R721LuaTest.apk))
    args, rest = p.parse_known_args()
    R721LuaTest.apk = Path(args.apk)
    unittest.main(argv=[__file__] + rest)
