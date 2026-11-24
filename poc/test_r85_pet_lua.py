#!/usr/bin/env python3
"""Verify R8.5 Pet/PetOut/PetCompare Lua patches & server_bundle packaging."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from build_standalone_apk import build_server_bundle_zip, patch_r85_pet_lua
from patch_vn_apk import XXTEA_KEY, XXTEA_SIGN, xxtea_decrypt

VN_LUAC_CFG = Path(__file__).resolve().parent.parent / "analysis" / "vn" / "apktool" / "assets" / "src" / "Config"


def read_luac_utf8(path: Path) -> str:
    raw = path.read_bytes()
    assert raw.startswith(XXTEA_SIGN), f"Missing XXTEA header: {path}"
    return xxtea_decrypt(raw[len(XXTEA_SIGN) :], XXTEA_KEY).decode("utf-8")


class R85PetLuaTest(unittest.TestCase):
    def test_01_patch_r85_pet_lua_enables_modules_and_localizes_names(self) -> None:
        self.assertTrue((VN_LUAC_CFG / "ModuleSubModel.luac").exists())
        self.assertTrue((VN_LUAC_CFG / "PetModel.luac").exists())
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            cfg = src / "Config"
            cfg.mkdir(parents=True)
            shutil.copy2(VN_LUAC_CFG / "ModuleSubModel.luac", cfg / "ModuleSubModel.luac")
            shutil.copy2(VN_LUAC_CFG / "PetModel.luac", cfg / "PetModel.luac")

            patch_r85_pet_lua(src)

            ms = read_luac_utf8(cfg / "ModuleSubModel.luac")
            for mid in (1414, 7400, 7401, 7402, 7403, 7404, 7405, 7406, 7500, 7600):
                idx = ms.index(f"[{mid}] = {{")
                block = ms[idx : idx + 280]
                self.assertIn("ifOpen = 1,", block, f"ModuleSub {mid} was not enabled")

            pm = read_luac_utf8(cfg / "PetModel.luac")
            expected_vn_names = [
                "Tiểu Long Đỏ",
                "Lửng Hachi Tinh Nghịch",
                "Rùa Con Dễ Thương",
                "Hachi Phi Thuyền",
                "Tử Hồn Trùng Chăm Chỉ",
                "Ngưu Ba Mắt Ngây Ngô",
                "A-Un Trung Thành",
                "Trư Cửu Giới",
                "Long Cốt Tinh",
                "Hồ Yêu Shippo Tinh Quái",
                "Myoga Đào Tẩu",
                "Shoga Đáng Yêu",
                "Kirara Đáng Yêu",
                "Tử Hồn Trùng Cuồng Bạo",
                "Hachi Cầu Đá",
                "Huyền Vũ Thần Quy",
                "Hachi Giáp Sắt",
                "Thần Long Phun Lửa",
                "Thần Trư Phi Thiên",
                "A-Un Chiến Đấu",
                "Myoga Phẫn Nộ",
                "Shoga Bạo Tẩu",
                "Hồ Yêu Shippo Nổi Giận",
                "Kim Cang Ngưu Ma Vương",
                "Thần Dực Long Cốt Tinh",
                "Kirara Yêu Hóa",
                "Bé Kinh Nghiệm",
            ]
            for vn_name in expected_vn_names:
                self.assertIn(f'name = "{vn_name}",', pm)
            for zh_name in ("萌萌小紅龍", "呆萌雲母", "妖化雲母", "經驗寶寶", "神翼龍骨精"):
                self.assertNotIn(f'name = "{zh_name}",', pm)

    def test_02_server_bundle_includes_pet_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "server_bundle.zip"
            build_server_bundle_zip(zpath)
            with ZipFile(zpath) as zf:
                names = set(zf.namelist())
                self.assertIn("pet_handlers.py", names)
                self.assertIn("pet_data.json", names)
                self.assertIn("PetOutInfo.GetPetOutInfo", zf.read("emulator.py").decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
