#!/usr/bin/env python3
"""Verify R8.7 Android Modern SDK hardening (minSdk=21, targetSdk=30, manifest exported/dedup, MQUtils)."""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from build_standalone_apk import patch_modern_android_sdk

VN_APKTOOL = Path(__file__).resolve().parent.parent / "analysis" / "vn" / "apktool"


class R87ModernSdkTest(unittest.TestCase):
    def test_01_patch_modern_android_sdk_manifest_yml_and_smali(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            work.mkdir(parents=True)
            shutil.copy2(VN_APKTOOL / "AndroidManifest.xml", work / "AndroidManifest.xml")
            shutil.copy2(VN_APKTOOL / "apktool.yml", work / "apktool.yml")
            mq_dst = work / "smali" / "com" / "moqikaka" / "sdk" / "MQUtils.smali"
            mq_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(VN_APKTOOL / "smali" / "com" / "moqikaka" / "sdk" / "MQUtils.smali", mq_dst)

            patch_modern_android_sdk(work)

            yml_txt = (work / "apktool.yml").read_text(encoding="utf-8")
            self.assertIn("  minSdkVersion: 21\n", yml_txt)
            self.assertIn("  targetSdkVersion: 30\n", yml_txt)

            mf_txt = (work / "AndroidManifest.xml").read_text(encoding="utf-8")
            self.assertIn('android:requestLegacyExternalStorage="true"', mf_txt)
            self.assertRegex(
                mf_txt,
                r'<activity\b[^>]*android:name="com\.moqikaka\.sdk\.MQActivity"[^>]*android:exported="true"'
                r'|<activity\b[^>]*android:exported="true"[^>]*android:name="com\.moqikaka\.sdk\.MQActivity"',
            )

            perms = re.findall(r'<uses-permission\b[^>]*android:name="([^"]+)"', mf_txt)
            self.assertEqual(len(perms), len(set(perms)), "Duplicate <uses-permission> entries remain")

            for m in re.finditer(r"<(activity|service|receiver|provider)\b([^>]*)>(.*?)</\1>", mf_txt, re.S):
                if "<intent-filter" in m.group(3):
                    self.assertIn("android:exported=", m.group(2), f"Missing android:exported on <{m.group(1)} {m.group(2)}>")

            mq_txt = mq_dst.read_text(encoding="utf-8")
            self.assertNotIn("TelephonyManager;->getDeviceId", mq_txt)
            self.assertIn(".method public getDeviceUUid()Ljava/lang/String;", mq_txt)
            self.assertIn(".method public getDeviceIMEI2()Ljava/lang/String;", mq_txt)
            self.assertIn("Landroid/os/Build;->MANUFACTURER:Ljava/lang/String;", mq_txt)


if __name__ == "__main__":
    unittest.main()
