#!/usr/bin/env python3
"""
Build a minimally patched EN 5.1.1 APK pointing to the local Python Server Emulator.
Original XAPK/APK files in `originals/` and `analysis/apktool_en/` remain untouched.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

XXTEA_SIGN = b"MQKK"
XXTEA_KEY = b"cf68b641311b5201"

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DECOMPILED = ROOT_DIR / "analysis" / "apktool_en"
PATCH_WORK = ROOT_DIR / "analysis" / "apktool_patched"
OUT_DIR = ROOT_DIR / "analysis" / "patched"
APKTOOL_JAR = ROOT_DIR / "analysis" / "tools" / "apktool_3.0.3.jar"
SDK_BUILD_TOOLS = Path("/Users/vup/Library/Android/sdk/build-tools/36.0.0")
ZIPALIGN = SDK_BUILD_TOOLS / "zipalign"
APKSIGNER = SDK_BUILD_TOOLS / "apksigner"
KEYSTORE = Path.home() / ".android" / "debug.keystore"

LOCAL_MQLOGIN_SMALI = """.method public MQLogin()V
    .locals 3

    .prologue
    const/4 v1, 0x0

    iput-boolean v1, p0, Lcom/moqikaka/sdk/Entity;->mOptLogin:Z

    new-instance v0, Lcom/moqikaka/sdk/Entity$LoginInfo;

    const/4 v2, 0x0

    invoke-direct {v0, p0, v2}, Lcom/moqikaka/sdk/Entity$LoginInfo;-><init>(Lcom/moqikaka/sdk/Entity;Lcom/moqikaka/sdk/Entity$LoginInfo;)V

    const-string v1, "100001"

    iput-object v1, v0, Lcom/moqikaka/sdk/Entity$LoginInfo;->uid:Ljava/lang/String;

    const-string v1, "1001"

    iput-object v1, v0, Lcom/moqikaka/sdk/Entity$LoginInfo;->platformId:Ljava/lang/String;

    const-string v1, "100001"

    iput-object v1, v0, Lcom/moqikaka/sdk/Entity$LoginInfo;->platformUserId:Ljava/lang/String;

    const-string v1, "local-revival"

    iput-object v1, v0, Lcom/moqikaka/sdk/Entity$LoginInfo;->token:Ljava/lang/String;

    const-string v1, ""

    iput-object v1, v0, Lcom/moqikaka/sdk/Entity$LoginInfo;->custom:Ljava/lang/String;

    iget-object v1, p0, Lcom/moqikaka/sdk/Entity;->mHelper:Lcom/moqikaka/sdk/MQHelper;

    invoke-virtual {v1, v0}, Lcom/moqikaka/sdk/MQHelper;->loginEnd(Ljava/lang/Object;)V

    return-void
.end method"""


def xxtea_decrypt(data: bytes, key: bytes = XXTEA_KEY) -> bytes:
    """Decrypt raw XXTEA payload (without 4-byte sign header)."""
    if len(data) < 4:
        return data
    n = len(data) // 4
    v = list(struct.unpack(f"<{n}I", data))
    k = list(struct.unpack("<4I", key.ljust(16, b"\x00")[:16]))
    delta = 0x9E3779B9
    rounds = 6 + 52 // n
    summ = (rounds * delta) & 0xFFFFFFFF
    y = v[0]
    while summ != 0:
        e = (summ >> 2) & 3
        for p in range(n - 1, 0, -1):
            z = v[p - 1]
            mx = (((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ ((summ ^ y) + (k[(p & 3) ^ e] ^ z))) & 0xFFFFFFFF
            v[p] = (v[p] - mx) & 0xFFFFFFFF
            y = v[p]
        z = v[n - 1]
        mx = (((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ ((summ ^ y) + (k[(0 & 3) ^ e] ^ z))) & 0xFFFFFFFF
        v[0] = (v[0] - mx) & 0xFFFFFFFF
        y = v[0]
        summ = (summ - delta) & 0xFFFFFFFF
    raw = struct.pack(f"<{n}I", *v)
    pad_len = v[-1]
    if 0 < pad_len <= len(raw):
        return raw[:pad_len]
    return raw.rstrip(b"\x00")


def xxtea_encrypt(data: bytes, key: bytes = XXTEA_KEY) -> bytes:
    """Encrypt raw Lua bytes using Cocos2d-x XXTEA format (length trailer)."""
    length = len(data)
    pad = (4 - (length % 4)) % 4
    padded = data + b"\x00" * pad + struct.pack("<I", length)
    n = len(padded) // 4
    v = list(struct.unpack(f"<{n}I", padded))
    k = list(struct.unpack("<4I", key.ljust(16, b"\x00")[:16]))
    delta = 0x9E3779B9
    rounds = 6 + 52 // n
    summ = 0
    z = v[n - 1]
    for _ in range(rounds):
        summ = (summ + delta) & 0xFFFFFFFF
        e = (summ >> 2) & 3
        for p in range(n - 1):
            y = v[p + 1]
            mx = (((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ ((summ ^ y) + (k[(p & 3) ^ e] ^ z))) & 0xFFFFFFFF
            v[p] = (v[p] + mx) & 0xFFFFFFFF
            z = v[p]
        y = v[0]
        mx = (((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ ((summ ^ y) + (k[((n - 1) & 3) ^ e] ^ z))) & 0xFFFFFFFF
        v[n - 1] = (v[n - 1] + mx) & 0xFFFFFFFF
        z = v[n - 1]
    return struct.pack(f"<{n}I", *v)


def patch_luac_text(luac_path: Path, replacements: list[tuple[str, str]]) -> None:
    """Decrypt an MQKK XXTEA .luac script, apply exact string replacements, and re-encrypt."""
    raw = luac_path.read_bytes()
    if not raw.startswith(XXTEA_SIGN):
        raise ValueError(f"Expected MQKK header in {luac_path}")
    text = xxtea_decrypt(raw[len(XXTEA_SIGN) :]).decode("utf-8")
    for old, new in replacements:
        if old not in text:
            raise ValueError(f"Target snippet not found in {luac_path}: {old!r}")
        text = text.replace(old, new, 1)
    luac_path.write_bytes(XXTEA_SIGN + xxtea_encrypt(text.encode("utf-8")))


def replace_cstr_padded(blob: bytearray, old: bytes, new: bytes) -> None:
    if len(new) > len(old):
        raise ValueError(f"Replacement {new!r} is longer than {old!r}")
    idx = blob.find(old)
    if idx == -1:
        raise ValueError(f"Target bytes not found: {old!r}")
    # Ensure exact fixed-length overwrite with NUL padding
    padded = new + b"\x00" * (len(old) - len(new))
    blob[idx : idx + len(old)] = padded


def patch_workspace(server_host_port: str) -> None:
    if PATCH_WORK.exists():
        shutil.rmtree(PATCH_WORK)
    shutil.copytree(SRC_DECOMPILED, PATCH_WORK)

    # 1. AndroidManifest.xml: enable cleartext HTTP on Android 12
    manifest_path = PATCH_WORK / "AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")
    if "android:usesCleartextTraffic" not in manifest:
        manifest = manifest.replace(
            "<application ",
            '<application android:usesCleartextTraffic="true" ',
            1,
        )
        manifest_path.write_text(manifest, encoding="utf-8")

    # 2. libcocos2dlua.so: point ManageCenter & ReleaseDomain to emulator + enable Debug=1
    so_path = PATCH_WORK / "lib" / "armeabi" / "libcocos2dlua.so"
    blob = bytearray(so_path.read_bytes())
    replace_cstr_padded(blob, b"Debug=0", b"Debug=1")
    replace_cstr_padded(
        blob,
        b"ManageCenter=http://loginsvr.enqyc.moqikaka.com/API/ServerList_Client.ashx",
        f"ManageCenter=http://{server_host_port}/API/ServerList_Client.ashx".encode("ascii"),
    )
    replace_cstr_padded(
        blob,
        b"ReleaseDomain=http://loginsvr.enqyc.moqikaka.com/",
        f"ReleaseDomain=http://{server_host_port}/".encode("ascii"),
    )
    so_path.write_bytes(bytes(blob))

    # 3. Entity.smali: bypass external Heitao/Google/FB login and invoke local MQHelper.loginEnd
    entity_path = PATCH_WORK / "smali" / "com" / "moqikaka" / "sdk" / "Entity.smali"
    entity_src = entity_path.read_text(encoding="utf-8")
    new_entity, count = re.subn(
        r"\.method public MQLogin\(\)V.*?\.end method",
        LOCAL_MQLOGIN_SMALI,
        entity_src,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError("Failed to patch MQLogin() in Entity.smali")
    entity_path.write_text(new_entity, encoding="utf-8")

    # 4. MQUtils.smali: redirect crash/step reporting away from dead 118.89.45.225
    utils_path = PATCH_WORK / "smali" / "com" / "moqikaka" / "sdk" / "MQUtils.smali"
    utils_src = utils_path.read_text(encoding="utf-8")
    utils_src = utils_src.replace("http://crashnew.moqikaka.com", f"http://{server_host_port}")
    utils_path.write_text(utils_src, encoding="utf-8")

    # 5. HomeScene.luac & GuideMng.luac: align stale 3-hero rollback guards (> 2 / < 3)
    #    with EN 5.1.1 GuideRelation[1], which summons 1 Destiny Hero and deploys into Slot 2 (= 2 heroes).
    patch_luac_text(
        PATCH_WORK / "assets" / "src" / "Home" / "HomeScene.luac",
        [
            (
                "        if heroCount > 2 then\n            newEventId = 107\n        else\n            newEventId = 103\n        end",
                "        if heroCount > 1 then\n            newEventId = 107\n        else\n            newEventId = 103\n        end",
            ),
            (
                "        if formationHeroCount < 3 then -- 一个学员也没有上阵，则需要回滚\n            newEventId = 107    -- 箭头指向“队伍”按钮",
                "        if formationHeroCount < 2 then -- 少于2人上阵时回滚\n            newEventId = 107    -- 箭头指向“队伍”按钮",
            ),
        ],
    )
    patch_luac_text(
        PATCH_WORK / "assets" / "src" / "Guide" / "GuideMng.luac",
        [
            (
                "        if heroCount > 2 then\n            newEventId = 107\n        elseif heroCount > 1 then\n            newEventId = 1051\n        else\n            newEventId = 104\n        end",
                "        if heroCount > 1 then\n            newEventId = 107\n        else\n            newEventId = 1051\n        end",
            ),
        ],
    )


def build_and_sign() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    unsigned_apk = OUT_DIR / "unsigned.apk"
    aligned_apk = OUT_DIR / "aligned.apk"
    signed_apk = OUT_DIR / "com.heitao.inuyasha.guge_revival.apk"

    for p in (unsigned_apk, aligned_apk, signed_apk):
        if p.exists():
            p.unlink()

    subprocess.run(
        ["java", "-jar", str(APKTOOL_JAR), "b", str(PATCH_WORK), "-o", str(unsigned_apk)],
        check=True,
    )
    subprocess.run(
        [str(ZIPALIGN), "-f", "4", str(unsigned_apk), str(aligned_apk)],
        check=True,
    )
    subprocess.run(
        [
            str(APKSIGNER),
            "sign",
            "--ks",
            str(KEYSTORE),
            "--ks-pass",
            "pass:android",
            "--key-pass",
            "pass:android",
            "--ks-key-alias",
            "androiddebugkey",
            "--out",
            str(signed_apk),
            str(aligned_apk),
        ],
        check=True,
    )
    unsigned_apk.unlink(missing_ok=True)
    aligned_apk.unlink(missing_ok=True)
    return signed_apk


def main() -> None:
    parser = argparse.ArgumentParser(description="Build patched EN 5.1.1 APK for local emulator")
    parser.add_argument("--server", default="192.168.1.250:8080", help="Emulator host:port")
    args = parser.parse_args()

    patch_workspace(args.server)
    out = build_and_sign()
    print(f"Patched & signed APK ready: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
