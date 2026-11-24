#!/usr/bin/env python3
"""Verify R8.6 Warfare & Warfarespirit Lua patches and server_bundle packaging."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from build_standalone_apk import build_server_bundle_zip, patch_r86_warfare_lua
from patch_vn_apk import XXTEA_KEY, XXTEA_SIGN, xxtea_decrypt

VN_LUAC_SRC = Path(__file__).resolve().parent.parent / "analysis" / "vn" / "apktool" / "assets" / "src"


def read_luac_utf8(path: Path) -> str:
    raw = path.read_bytes()
    assert raw.startswith(XXTEA_SIGN), f"Missing XXTEA header: {path}"
    return xxtea_decrypt(raw[len(XXTEA_SIGN) :], XXTEA_KEY).decode("utf-8")


class R86WarfareLuaTest(unittest.TestCase):
    def test_01_patch_r86_warfare_lua_enables_modules_localizes_and_unlocks_ui(self) -> None:
        rel_files = (
            "Config/ModuleSubModel.luac",
            "Config/WarfareModel.luac",
            "Config/WarfarespiritModel.luac",
            "Hero/HeroUpdateScene.luac",
            "Disassemble/DisassembleNewScene.luac",
            "Bag/BagExWarfareArms.luac",
            "Bag/BagExWarfareSpirit.luac",
            "Bag/BagScene.luac",
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            for rel in rel_files:
                src_p = VN_LUAC_SRC / rel
                self.assertTrue(src_p.exists(), f"Missing baseline luac: {src_p}")
                dst_p = src / rel
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_p, dst_p)

            patch_r86_warfare_lua(src)

            ms = read_luac_utf8(src / "Config/ModuleSubModel.luac")
            for mid in range(8101, 8109):
                idx = ms.index(f"[{mid}] = {{")
                block = ms[idx : idx + 280]
                self.assertIn("ifOpen = 1,", block, f"ModuleSub {mid} was not enabled")

            wm = read_luac_utf8(src / "Config/WarfareModel.luac")
            for vn_name in (
                "Kết Giới Vạn Linh",
                "Kết Giới Lôi Đình",
                "Kết Giới Hàng Yêu",
                "Kết Giới Yêu Đao",
                "Kết Giới Vu Nữ",
                "Kết Giới Ma Thần",
            ):
                self.assertIn(f'name = "{vn_name}"', wm)
            self.assertNotIn("萬靈結界", wm)

            wsm = read_luac_utf8(src / "Config/WarfarespiritModel.luac")
            for vn_name in (
                "Linh Châu Kinh Nghiệm Sơ",
                "Linh Châu Kinh Nghiệm Trung",
                "Linh Châu Kinh Nghiệm Cao",
                "Linh Châu Chính Xác Ⅰ",
                "Linh Châu Công Ⅶ",
                "Linh Châu Hồi Phục Ⅶ",
            ):
                self.assertIn(f'name = "{vn_name}"', wsm)
            self.assertNotIn("命中靈珠", wsm)
            self.assertNotIn("經驗靈珠", wsm)

            hus = read_luac_utf8(src / "Hero/HeroUpdateScene.luac")
            self.assertIn('{ x = 350, y = 0, tag = HeroEnhance.eWarfare, text = TR("结界")},', hus)
            self.assertIn("not self.mHeroTable.warfareID or self.mHeroTable.warfareID == 0", hus)

            dns = read_luac_utf8(src / "Disassemble/DisassembleNewScene.luac")
            self.assertIn("self.mTypeTabLayer:setTabVisibled(5, NetworkResData:modulePlayerIsOpen(ModuleSub.eWarfare)", dns)
            self.assertIn('{ x = 0, y = 110, text = TR("结\\n界")},', dns)

            ba = read_luac_utf8(src / "Bag/BagExWarfareArms.luac")
            bs = read_luac_utf8(src / "Bag/BagExWarfareSpirit.luac")
            bag = read_luac_utf8(src / "Bag/BagScene.luac")
            self.assertIn('name           = "Kết Giới",', ba)
            self.assertIn("bagType        = nil,", ba)
            self.assertIn('name           = "Linh Châu",', bs)
            self.assertIn("bagType        = nil,", bs)
            self.assertIn("BagTabInfo[BagSceneTab.eWarfareSpirit]", bag)
            self.assertIn("BagTabInfo[BagSceneTab.eWarfareArms]", bag)

    def test_02_server_bundle_includes_warfare_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "server_bundle.zip"
            build_server_bundle_zip(zpath)
            with ZipFile(zpath) as zf:
                names = set(zf.namelist())
                self.assertIn("warfare_handlers.py", names)
                self.assertIn("warfare_data.json", names)
                self.assertIn("Warfare.OpenWarfare", zf.read("emulator.py").decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
