#!/usr/bin/env python3
"""
Build the self-contained Android Standalone APK for InuYasha: Seek Jade (R7.7 -> R7.8).

Features:
  - Application ID: com.cmn.inuyasha.revival (coexists safely with com.cmn.inuyasha STABLE).
  - Embeds 32-bit ARM CPython 3.11 runtime + libinubackend.so PIE launcher in lib/armeabi/.
  - Packages canonical Python backend (emulator.py, event_handlers.py, event_runtime.py,
    combat_sim.py, economy_audit.py, game_data.json) in assets/inubackend/.
  - Merges OBB resources (main.98.com.cmn.inuyasha.obb) directly into assets/res/ for 1-file install.
  - Injects LocalBackendManager & LocalBackendService lifecycle supervisor (auto-start on launch,
    127.0.0.1:18082 loopback-only bind, watchdog auto-restart, save mirror, clean shutdown).
  - Patches VN Lua UI for offline recharge, concurrent multi-banner 81/82 tabs, multi-account S1
    switcher, and save backup export/import.
  - Signs with fixed release keystore outside repository (~/.inuyasha_release/inuyasha_revival_release.jks).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from patch_vn_apk import (
    APKTOOL_JAR,
    APKSIGNER,
    OUT_DIR,
    ROOT_DIR,
    SRC_DECOMPILED,
    VN_LOCAL_MQLOGIN_SMALI,
    VN_LOCAL_ONCREATE_SMALI,
    VN_LOCAL_ONDESTROY_SMALI,
    XXTEA_SIGN,
    ZIPALIGN,
    patch_luac_text,
    replace_cstr_padded,
    xxtea_encrypt,
)

STANDALONE_WORK = ROOT_DIR / "analysis" / "vn" / "apktool_standalone"
VN_OBB_ZIP = (
    ROOT_DIR
    / "analysis"
    / "vn"
    / "extracted"
    / "Android"
    / "obb"
    / "com.cmn.inuyasha"
    / "main.98.com.cmn.inuyasha.obb"
)
BUILD_CACHE_DIR = ROOT_DIR.parent / "inuyasha_build"
CHAQUOPY_ARM_ZIP = BUILD_CACHE_DIR / "deps" / "target-3.11.17-0-armeabi-v7a.zip"
CHAQUOPY_STDLIB_ZIP = BUILD_CACHE_DIR / "deps" / "target-3.11.17-0-stdlib-pyc.zip"
PREBUILT_LAUNCHER = BUILD_CACHE_DIR / "libinubackend.so"
SUPERVISOR_SMALI_DIR = ROOT_DIR / "android" / "smali" / "com" / "cmn" / "inuyasha" / "standalone"

RELEASE_KEYSTORE = Path.home() / ".inuyasha_release" / "inuyasha_revival_release.jks"
RELEASE_KS_ALIAS = "inuyasha_revival"
RELEASE_KS_PASS = "InuYashaRevival2026!"

SKIP_DYNLOAD_PREFIXES = (
    "_codecs_",
    "_ctypes",
    "_xxtestfuzz",
    "xxlimited",
    "audioop",
    "ossaudiodev",
)

ACCOUNT_SWITCH_LAYER_LUA = """--[[
    System.AccountSwitchLayer.lua — Standalone S1 Multi-Account & Save Backup Manager (R7.8)
-- ]]

local AccountSwitchLayer = class("AccountSwitchLayer", function()
    local self
    self = require("Common.ModalColorLayer").new({
        color4B = cc.c4b(0, 0, 0, 150),
        title = TR("Tài Khoản S1 & Sao Lưu"),
        bgImage = "c_43.png",
        closeBtnImage = "c_15.png",
        onCloseCallback = function()
            self:removeFromParent()
        end
    })
    return self
end)

local function requestLocalAccountApi(method, payloadTable, cb)
    local xhr = cc.XMLHttpRequest:new()
    xhr:setUnzip(false)
    xhr.responseType = cc.XMLHTTPREQUEST_RESPONSE_STRING
    xhr:open(method, "http://127.0.0.1:18082/account")
    xhr:registerScriptHandler(function(event)
        local data = nil
        if event == "SUCCESS" and xhr.status == 200 and xhr.response then
            data = cjson.decode(xhr.response)
        end
        if cb then
            cb(data, xhr.status)
        end
    end)
    if method == "POST" and payloadTable then
        xhr:send(cjson.encode(payloadTable))
    else
        xhr:send()
    end
end

function AccountSwitchLayer:ctor()
    self.mContentNode = cc.Node:create()
    self.mBgSprite:addChild(self.mContentNode)
    self:refreshAccountView()
end

function AccountSwitchLayer:enterAccount(userId)
    NetworkResData:clearPlayerCacheInfo()
    local loginJson = cjson.encode({
        uid = tostring(userId or "100001"),
        platformId = "1001",
        token = "local-revival",
    })
    game.replaceRootScene(require("Login.StartGameScene").new(loginJson, true), "CCtransitionCrossFade", 0)
end

function AccountSwitchLayer:refreshAccountView()
    self.mContentNode:removeAllChildren()
    local w, h = self.mBgSize.width, self.mBgSize.height

    local loadingLbl = ui.newLabel({
        text = "Đang tải danh sách tài khoản cục bộ S1...",
        size = 22,
        color = ColorList.ccBlack,
        align = cc.TEXT_ALIGNMENT_CENTER,
    })
    loadingLbl:setPosition(cc.p(w * 0.5, h * 0.52))
    self.mContentNode:addChild(loadingLbl)

    requestLocalAccountApi("GET", nil, function(res)
        if tolua.isnull(self) or tolua.isnull(self.mContentNode) then
            return
        end
        self.mContentNode:removeAllChildren()
        if not res or not res.Accounts then
            local errLbl = ui.newLabel({
                text = "Không thể đọc danh sách tài khoản cục bộ",
                size = 22,
                color = ColorList.ccBlack,
            })
            errLbl:setPosition(cc.p(w * 0.5, h * 0.52))
            self.mContentNode:addChild(errLbl)
            return
        end

        local curLbl = ui.newLabel({
            text = "Đang chọn: {6c0101}" .. tostring(res.ActiveDisplay or res.ActiveAccountId),
            size = 21,
            color = ColorList.ccBlack,
            align = cc.TEXT_ALIGNMENT_CENTER,
        })
        curLbl:setPosition(cc.p(w * 0.5, h * 0.78))
        self.mContentNode:addChild(curLbl)

        local accounts = res.Accounts or {}
        local positions = {
            cc.p(w * 0.28, h * 0.61),
            cc.p(w * 0.72, h * 0.61),
            cc.p(w * 0.28, h * 0.43),
            cc.p(w * 0.72, h * 0.43),
        }
        for idx = 1, math.min(#accounts, 4) do
            local acc = accounts[idx]
            local isCur = acc.active
            local btnText = acc.display or ("TK " .. tostring(idx))
            local accBtn = ui.newButton({
                normalImage = isCur and "c_77.png" or "c_7.png",
                text = btnText,
                fontSize = 18,
                scale = 0.92,
                color = ColorList.ccWhite,
                outlineColor = ColorList.ccOutline,
                outlineSize = 2,
                position = positions[idx],
                clickAction = function()
                    requestLocalAccountApi("POST", {action = "switch", account_id = acc.account_id}, function(swRes)
                        if swRes and swRes.ok then
                            local targetUid = (swRes.SwitchedAccount and swRes.SwitchedAccount.user_id) or acc.user_id
                            self:enterAccount(targetUid)
                        end
                    end)
                end,
            })
            self.mContentNode:addChild(accBtn)
        end

        local btnNewAcc = ui.newButton({
            normalImage = "c_7.png",
            text = "+ Tạo TK Mới",
            fontSize = 19,
            scale = 0.85,
            color = ColorList.ccWhite,
            outlineColor = ColorList.ccOutline,
            outlineSize = 2,
            position = cc.p(w * 0.21, h * 0.20),
            clickAction = function()
                requestLocalAccountApi("POST", {action = "create"}, function(crRes)
                    if crRes and crRes.ok then
                        local newUid = (crRes.CreatedAccount and crRes.CreatedAccount.user_id) or crRes.ActiveUserId
                        self:enterAccount(newUid)
                    end
                end)
            end,
        })
        self.mContentNode:addChild(btnNewAcc)

        local btnExport = ui.newButton({
            normalImage = "c_7.png",
            text = "Sao Lưu Save",
            fontSize = 19,
            scale = 0.85,
            color = ColorList.ccWhite,
            outlineColor = ColorList.ccOutline,
            outlineSize = 2,
            position = cc.p(w * 0.50, h * 0.20),
            clickAction = function()
                requestLocalAccountApi("POST", {action = "export"}, function(exRes)
                    if exRes and exRes.ok then
                        local msg = string.format(
                            "Đã sao lưu %d tài khoản S1!\\nSHA256: %s\\nTệp: saves/backups/inuyasha_save_backup_latest.json",
                            tonumber(exRes.AccountCount) or 1,
                            string.sub(tostring(exRes.Sha256 or ""), 1, 12)
                        )
                        local box = require("Common.MessageBoxLayer").new({
                            bgImage = "c_43.png",
                            closeBtnImage = "c_15.png",
                            title = TR("提示"),
                            content = msg,
                            leftBtnTitle = TR("确定"),
                            leftBtnCallback = function(dlg)
                                dlg:removeFromParent()
                            end,
                        })
                        display.getRunningScene():addChild(box, 1024)
                    else
                        ui.showFlashView({text = "Sao lưu thất bại"})
                    end
                end)
            end,
        })
        self.mContentNode:addChild(btnExport)

        local btnImport = ui.newButton({
            normalImage = "c_7.png",
            text = "Khôi Phục",
            fontSize = 19,
            scale = 0.85,
            color = ColorList.ccWhite,
            outlineColor = ColorList.ccOutline,
            outlineSize = 2,
            position = cc.p(w * 0.79, h * 0.20),
            clickAction = function()
                local box = require("Common.MessageBoxLayer").new({
                    bgImage = "c_43.png",
                    closeBtnImage = "c_15.png",
                    title = TR("提示"),
                    content = "Xác nhận khôi phục toàn bộ tài khoản S1 từ bản sao lưu gần nhất? (Hệ thống sẽ tự tạo bản lưu an toàn trước khi ghi đè)",
                    leftBtnTitle = TR("确定"),
                    rightBtnTitle = TR("取消"),
                    leftBtnCallback = function(dlg)
                        dlg:removeFromParent()
                        requestLocalAccountApi("POST", {action = "import", confirm = true}, function(imRes)
                            if imRes and imRes.ok then
                                ui.showFlashView({text = "Đã khôi phục dữ liệu thành công!"})
                                self:enterAccount(imRes.ActiveUserId or "100001")
                            else
                                ui.showFlashView({text = "Không tìm thấy bản sao lưu hợp lệ"})
                            end
                        end)
                    end,
                    rightBtnCallback = function(dlg)
                        dlg:removeFromParent()
                    end,
                })
                display.getRunningScene():addChild(box, 1024)
            end,
        })
        self.mContentNode:addChild(btnImport)
    end)
end

return AccountSwitchLayer
"""


def write_luac_text(luac_path: Path, lua_source: str) -> None:
    luac_path.write_bytes(XXTEA_SIGN + xxtea_encrypt(lua_source.encode("utf-8")))


def build_server_bundle_zip(dest_zip: Path) -> None:
    server_dir = ROOT_DIR / "server"
    files = [
        "emulator.py",
        "event_handlers.py",
        "r79_event_handlers.py",
        "event_runtime.py",
        "combat_effects.py",
        "combat_sim.py",
        "economy_audit.py",
        "game_data.json",
        "bdd_handlers.py",
        "bdd_data.json",
    ]
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in files:
            src = server_dir / fname
            if not src.exists():
                raise FileNotFoundError(f"Missing server file: {src}")
            zf.write(src, arcname=fname)


def bundle_embedded_python(work_dir: Path, version_tag: str) -> None:
    if not CHAQUOPY_ARM_ZIP.exists() or not CHAQUOPY_STDLIB_ZIP.exists():
        raise FileNotFoundError(f"Missing Chaquopy Python 3.11 artifacts in {BUILD_CACHE_DIR / 'deps'}")
    if not PREBUILT_LAUNCHER.exists():
        raise FileNotFoundError(f"Missing compiled {PREBUILT_LAUNCHER}")

    arm_lib_dir = work_dir / "lib" / "armeabi"
    arm_lib_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PREBUILT_LAUNCHER, arm_lib_dir / "libinubackend.so")

    with zipfile.ZipFile(CHAQUOPY_ARM_ZIP, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if name.startswith("jniLibs/armeabi-v7a/") and name.endswith(".so"):
                base = Path(name).name
                (arm_lib_dir / base).write_bytes(zf.read(name))
            elif name.startswith("lib-dynload/armeabi-v7a/") and name.endswith(".cpython-311.so"):
                mod = Path(name).name[: -len(".cpython-311.so")]
                if any(mod.startswith(pfx) for pfx in SKIP_DYNLOAD_PREFIXES):
                    continue
                (arm_lib_dir / f"libpymod_{mod}.so").write_bytes(zf.read(name))

    backend_assets_dir = work_dir / "assets" / "inubackend"
    backend_assets_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CHAQUOPY_STDLIB_ZIP, backend_assets_dir / "stdlib.zip")
    build_server_bundle_zip(backend_assets_dir / "server_bundle.zip")
    (backend_assets_dir / "version.txt").write_text(f"{version_tag}\n", encoding="utf-8")


def merge_obb_into_assets(work_dir: Path) -> int:
    if not VN_OBB_ZIP.exists():
        raise FileNotFoundError(f"Missing VN OBB file: {VN_OBB_ZIP}")
    assets_dir = work_dir / "assets"
    merged_count = 0
    with zipfile.ZipFile(VN_OBB_ZIP, "r") as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.startswith("res/"):
                continue
            target = assets_dir / info.filename
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(info.filename))
                merged_count += 1
    return merged_count


def inject_lifecycle_supervisor(work_dir: Path) -> None:
    if not SUPERVISOR_SMALI_DIR.exists():
        raise FileNotFoundError(f"Missing supervisor smali dir: {SUPERVISOR_SMALI_DIR}")
    dst_smali_dir = work_dir / "smali_classes2" / "com" / "cmn" / "inuyasha" / "standalone"
    dst_smali_dir.mkdir(parents=True, exist_ok=True)
    for sf in SUPERVISOR_SMALI_DIR.glob("*.smali"):
        shutil.copy2(sf, dst_smali_dir / sf.name)

    # 1. Hook GameApplication.onCreate
    game_app_path = work_dir / "smali" / "com" / "moqikaka" / "sdk" / "GameApplication.smali"
    game_app_src = game_app_path.read_text(encoding="utf-8")
    target_ga = "invoke-super {p0}, Lcom/kull/sdk/ui/AnalyticsApp;->onCreate()V"
    if target_ga not in game_app_src:
        raise RuntimeError("Failed to locate super.onCreate in GameApplication.smali")
    game_app_src = game_app_src.replace(
        target_ga,
        target_ga
        + "\n\n    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->onAppCreate(Landroid/content/Context;)V",
        1,
    )
    game_app_path.write_text(game_app_src, encoding="utf-8")

    # 2. Hook MQActivity lifecycle & disable legacy storage permission array
    mq_act_path = work_dir / "smali" / "com" / "moqikaka" / "sdk" / "MQActivity.smali"
    mq_act_src = mq_act_path.read_text(encoding="utf-8")

    # Empty out mPermissons array so Android never prompts for obsolete permissions
    mq_act_src, n_perm = re.subn(
        r"const/4 v0, 0x2\s+new-array v0, v0, \[Ljava/lang/String;.*?iput-object v0, p0, Lcom/moqikaka/sdk/MQActivity;->mPermissons:\[Ljava/lang/String;",
        "const/4 v0, 0x0\n\n    new-array v0, v0, [Ljava/lang/String;\n\n    iput-object v0, p0, Lcom/moqikaka/sdk/MQActivity;->mPermissons:[Ljava/lang/String;",
        mq_act_src,
        count=1,
        flags=re.S,
    )
    if n_perm != 1:
        raise RuntimeError("Failed to patch mPermissons in MQActivity.smali")

    # Hook MQActivity.onCreate before super.onCreate
    target_oc = "invoke-super {p0, p1}, Lorg/cocos2dx/lib/Cocos2dxActivity;->onCreate(Landroid/os/Bundle;)V"
    if target_oc not in mq_act_src:
        raise RuntimeError("Failed to locate super.onCreate in MQActivity.smali")
    mq_act_src = mq_act_src.replace(
        target_oc,
        "invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->ensureStarted(Landroid/content/Context;)V\n\n    "
        + target_oc,
        1,
    )

    # Hook MQActivity.pause()
    target_pause = "invoke-virtual {v0}, Lorg/cocos2dx/lib/Cocos2dxGLSurfaceView;->onPause()V"
    if target_pause not in mq_act_src:
        raise RuntimeError("Failed to locate onPause in MQActivity.smali")
    mq_act_src = mq_act_src.replace(
        target_pause,
        target_pause
        + "\n\n    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->onActivityPause(Landroid/content/Context;)V",
        1,
    )

    # Hook MQActivity.resume()
    target_resume = "invoke-static {}, Lorg/cocos2dx/lib/Cocos2dxHelper;->onResume()V"
    if target_resume not in mq_act_src:
        raise RuntimeError("Failed to locate onResume in MQActivity.smali")
    mq_act_src = mq_act_src.replace(
        target_resume,
        "invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->onActivityResume(Landroid/content/Context;)V\n\n    "
        + target_resume,
        1,
    )

    # Hook MQActivity.onDestroy()
    target_destroy = "invoke-virtual {v0}, Lcom/moqikaka/sdk/IBase;->onDestroy()V"
    if target_destroy not in mq_act_src:
        raise RuntimeError("Failed to locate IBase.onDestroy in MQActivity.smali")
    mq_act_src = mq_act_src.replace(
        target_destroy,
        target_destroy
        + "\n\n    invoke-static {p0}, Lcom/cmn/inuyasha/standalone/LocalBackendManager;->onActivityDestroy(Landroid/content/Context;)V",
        1,
    )

    mq_act_path.write_text(mq_act_src, encoding="utf-8")


def patch_standalone_workspace(
    package_id: str,
    version_code: int,
    version_name: str,
    app_label: str,
) -> None:
    server_host_port = "127.0.0.1:18082"
    if STANDALONE_WORK.exists():
        shutil.rmtree(STANDALONE_WORK)
    shutil.copytree(SRC_DECOMPILED, STANDALONE_WORK)

    # 1. Manifest & package ID / provider authority / permissions / service
    manifest_path = STANDALONE_WORK / "AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = manifest.replace('package="com.cmn.inuyasha"', f'package="{package_id}"', 1)
    manifest = manifest.replace(
        'android:authorities="com.facebook.app.FacebookContentProvider0"',
        f'android:authorities="{package_id}.FacebookContentProvider0"',
        1,
    )
    # Disable obsolete :remote crash/reboot services so Android does not spawn a redundant :remote process
    for remote_svc in ("com.moqikaka.sdk.MQCrashService", "com.moqikaka.sdk.MQRebootService"):
        manifest = manifest.replace(
            f'<service android:enabled="true" android:exported="false" android:name="{remote_svc}" android:process=":remote"/>',
            f'<service android:enabled="false" android:exported="false" android:name="{remote_svc}"/>',
        )
    # Remove intrusive obsolete permissions
    for bad_perm in (
        "android.permission.READ_PHONE_STATE",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.SYSTEM_ALERT_WINDOW",
        "android.permission.WRITE_SETTINGS",
        "android.permission.GET_TASKS",
    ):
        manifest = re.sub(rf'\s*<uses-permission(?:-sdk-m)? android:name="{re.escape(bad_perm)}"/>', "", manifest)

    if "android.permission.FOREGROUND_SERVICE" not in manifest:
        manifest = manifest.replace(
            '<uses-permission android:name="android.permission.INTERNET"/>',
            '<uses-permission android:name="android.permission.INTERNET"/>\n    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>',
            1,
        )
    manifest = manifest.replace(
        "<application ",
        '<application android:usesCleartextTraffic="true" android:extractNativeLibs="true" ',
        1,
    )
    manifest = manifest.replace(
        "</application>",
        '    <uses-library android:name="org.apache.http.legacy" android:required="false"/>\n'
        '        <service android:enabled="true" android:exported="false" android:name="com.cmn.inuyasha.standalone.LocalBackendService"/>\n'
        "    </application>",
        1,
    )
    manifest_path.write_text(manifest, encoding="utf-8")

    # Update app_name in res/values/strings.xml
    strings_xml = STANDALONE_WORK / "res" / "values" / "strings.xml"
    if strings_xml.exists():
        s_txt = strings_xml.read_text(encoding="utf-8")
        s_txt = re.sub(
            r'<string name="app_name">.*?</string>',
            f'<string name="app_name">{app_label}</string>',
            s_txt,
            count=1,
        )
        strings_xml.write_text(s_txt, encoding="utf-8")

    # Update apktool.yml versionCode, versionName, and doNotCompress
    yml_path = STANDALONE_WORK / "apktool.yml"
    yml_txt = yml_path.read_text(encoding="utf-8")
    yml_txt = re.sub(r"versionCode:\s*\d+", f"versionCode: {version_code}", yml_txt, count=1)
    yml_txt = re.sub(r"versionName:\s*[^\n]+", f"versionName: {version_name}", yml_txt, count=1)
    if "assets/inubackend/stdlib.zip" not in yml_txt:
        yml_txt = yml_txt.replace(
            "doNotCompress:\n",
            "doNotCompress:\n- assets/inubackend/stdlib.zip\n- assets/inubackend/server_bundle.zip\n",
            1,
        )
    yml_path.write_text(yml_txt, encoding="utf-8")

    # 2. Unpack assets/libs.apk into smali_classes2 and stub MQApplication.loadDex
    libs_apk = STANDALONE_WORK / "assets" / "libs.apk"
    if libs_apk.exists():
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tmp_apk = td_path / "wrap.apk"
            orig_apk = ROOT_DIR / "analysis" / "vn" / "extracted" / "com.cmn.inuyasha.apk"
            with zipfile.ZipFile(orig_apk, "r") as zorig, zipfile.ZipFile(libs_apk, "r") as zlibs, zipfile.ZipFile(tmp_apk, "w") as zout:
                zout.writestr("AndroidManifest.xml", zorig.read("AndroidManifest.xml"))
                zout.writestr("resources.arsc", zorig.read("resources.arsc"))
                zout.writestr("classes.dex", zlibs.read("classes.dex"))
            dec_dir = td_path / "dec"
            subprocess.run(["java", "-jar", str(APKTOOL_JAR), "d", "-f", str(tmp_apk), "-o", str(dec_dir)], check=True)
            for rel_stub in [("org", "apache", "http"), ("android", "net", "http"), ("android", "net", "compatibility")]:
                stub_dir = dec_dir / "smali"
                for part in rel_stub:
                    stub_dir = stub_dir / part
                if stub_dir.exists():
                    shutil.rmtree(stub_dir)
            classes2_dir = STANDALONE_WORK / "smali_classes2"
            if classes2_dir.exists():
                shutil.rmtree(classes2_dir)
            shutil.copytree(dec_dir / "smali", classes2_dir)
        libs_apk.unlink(missing_ok=True)
        mq_app_path = STANDALONE_WORK / "smali" / "com" / "moqikaka" / "sdk" / "MQApplication.smali"
        mq_app_src = mq_app_path.read_text(encoding="utf-8")
        mq_app_src, n = re.subn(
            r"\.method public static loadDex\(Landroid/content/Context;\)V.*?\.end method",
            ".method public static loadDex(Landroid/content/Context;)V\n    .locals 0\n\n    return-void\n.end method",
            mq_app_src,
            count=1,
            flags=re.S,
        )
        if n != 1:
            raise RuntimeError("Failed to stub MQApplication.loadDex")
        mq_app_path.write_text(mq_app_src, encoding="utf-8")

    # 3. Inject LocalBackendManager & LocalBackendService smali + lifecycle hooks
    inject_lifecycle_supervisor(STANDALONE_WORK)

    # 4. Patch libcocos2dlua.so, Entity.smali, and MQUtils.smali to 127.0.0.1:18082
    so_path = STANDALONE_WORK / "lib" / "armeabi" / "libcocos2dlua.so"
    blob = bytearray(so_path.read_bytes())
    replace_cstr_padded(blob, b"Debug=0", b"Debug=1")
    replace_cstr_padded(
        blob,
        b"ManageCenter=http://loginsvr.ynqyc.moqikaka.com/API/ServerList_Client.ashx",
        f"ManageCenter=http://{server_host_port}/API/ServerList_Client.ashx".encode("ascii"),
    )
    replace_cstr_padded(
        blob,
        b"ReleaseDomain=http://loginsvr.ynqyc.moqikaka.com/",
        f"ReleaseDomain=http://{server_host_port}/".encode("ascii"),
    )
    so_path.write_bytes(bytes(blob))

    entity_path = STANDALONE_WORK / "smali" / "com" / "moqikaka" / "sdk" / "Entity.smali"
    entity_src = entity_path.read_text(encoding="utf-8")
    for pat, repl, label in [
        (r"\.method public MQLogin\(\)V.*?\.end method", VN_LOCAL_MQLOGIN_SMALI, "MQLogin"),
        (r"\.method public onCreate\(Landroid/os/Bundle;\)V.*?\.end method", VN_LOCAL_ONCREATE_SMALI, "onCreate"),
        (r"\.method public onDestroy\(\)V.*?\.end method", VN_LOCAL_ONDESTROY_SMALI, "onDestroy"),
    ]:
        entity_src, n = re.subn(pat, repl, entity_src, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"Failed to patch {label} in Entity.smali")
    entity_path.write_text(entity_src, encoding="utf-8")

    utils_path = STANDALONE_WORK / "smali" / "com" / "moqikaka" / "sdk" / "MQUtils.smali"
    utils_path.write_text(
        utils_path.read_text(encoding="utf-8").replace("http://crashnew.moqikaka.com", f"http://{server_host_port}"),
        encoding="utf-8",
    )

    # 5. Apply all R7.6 Lua patches + R7.7/R7.8 Standalone Lua patches
    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "Home" / "HomeScene.luac",
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
        STANDALONE_WORK / "assets" / "src" / "Guide" / "GuideMng.luac",
        [
            (
                "        if heroCount > 2 then\n            newEventId = 107\n        elseif heroCount > 1 then\n            newEventId = 1051\n        else\n            newEventId = 104\n        end",
                "        if heroCount > 1 then\n            newEventId = 107\n        else\n            newEventId = 1051\n        end",
            ),
        ],
    )
    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "Store" / "RechargeScene.luac",
        [
            (
                '                    local canPurchase = IPlatform:getInstance():isRechargeSupported()\n'
                '                    if not canPurchase then\n'
                '                        ui.showFlashView({parent = self, text = TR("暂不支持充值")})\n'
                '                        return\n'
                '                    end',
                '                    -- Offline local revival: confirm MonthCard directly without dead billing SDK',
            ),
            (
                '                local channelName = IPlatform:getInstance():getConfigItem("Channel")\n'
                '                if channelName == "MQKK" then\n'
                '                    self:requestTestRecharge(info.ChargePoint)\n'
                '                    return\n'
                '                end\n'
                '                local canPurchase = IPlatform:getInstance():isRechargeSupported()\n'
                '                if not canPurchase then\n'
                '                    ui.showFlashView({parent = self, image = nil, text = TR("暂不支持充值")})\n'
                '                    return\n'
                '                end\n'
                '                IPlatform:getInstance():rechargeBegin()',
                '                -- Offline local revival: confirm diamond package directly via GenerateOrderID',
            ),
            (
                'function RechargeScene:requestGenerateOrderID(moduleName, methodName, productInfo)\n'
                '    LoadingWait:begin(self)\n'
                '    local product = {\n'
                '        productInfo.ProductId or productInfo.monthCardId,\n'
                '        IPlatform:getInstance():getDeviceMAC(),\n'
                '        IPlatform:getInstance():getDeviceUUID(),\n'
                '        IPlatform:getInstance():getDeviceIMEI()\n'
                '    }\n'
                '    HttpRequest(moduleName, methodName, product, function(response)\n'
                '        LoadingWait:ends()\n'
                '        if response.Status == 0 then\n'
                '            local info = {}\n'
                '            local serverInfo = NetworkResData:getServerInfo(true)\n'
                '            local userLoginInfo = NetworkResData:getUserLoginInfo()\n'
                '            local isMothCard = productInfo.ProductId == nil\n\n'
                '            info.MothCard = isMothCard and 1 or 0   -- 是否是月卡\n'
                '            info.ProductName = TR("钻石")                                    --: 购买产品名称(钻宝、晶石)\n'
                '            info.ProductID = productInfo.ProductId or response.Value.ProductId     --: 充值档位ID(string)\n'
                '            info.OrderID = isMothCard and response.Value.OrderId or response.Value --: 订单ID(string)\n'
                '            info.CurNum = self.mPlayerInfo.Diamond or 0 \t\t            --: 当前(钻宝)数目(int)\n'
                '            info.BuyNum = productInfo.GamePoint or 1\t\t            --: 购买(钻宝)数目(int)\n'
                '            info.PresentNum = productInfo.GiveGamePoint or 0\t            --: 赠送(钻宝)数目(int)\n'
                '            info.Price = isMothCard and productInfo.Price or productInfo.ChargePoint or 0\t--: 价格(钻)(int)\n'
                '            info.ServerID = serverInfo.ServerID or 0                  --: 当前服务器ID(int)\n'
                '            info.ServerName = serverInfo.ServerName or ""\t                --: 当前服务器名称(string)\n'
                '            info.PlayerID = self.mPlayerInfo.PlayerId \t            -- 玩家ID(string)\n'
                '            info.PlayerLevel = self.mPlayerInfo.Lv  \t            --: 玩家等级(int)\n'
                '            info.PlayerName = self.mPlayerInfo.PlayerName  \t        --: 玩家名称(string)\n'
                '            info.PlayerVipLevel = self.mPlayerInfo.Vip              --: 玩家VIP等级(int)\n'
                '            info.ExtData = userLoginInfo.ExtraData or ""                 -- 登录服务器时返回的额外信息\n'
                '            info.NotifyUrl = serverInfo.ChargeServerUrl or ""\t\t    -- 充值回调地址\n\n'
                '            local value = json.encode(info)\n'
                '            dump(value)\n'
                '            IPlatform:getInstance():recharge(value, function(result)\n'
                '                local tempInfo = clone(productInfo)\n'
                '                if isMothCard then\n'
                '                    productInfo.ProductId = response.ProductId\n'
                '                end\n'
                '                tempInfo.OrderID = isMothCard and response.Value.OrderId or response.Value\n'
                '                self:onPurchaseFinish(result, tempInfo)\n'
                '            end)\n'
                '        end\n'
                '    end)\n'
                'end',
                'function RechargeScene:requestGenerateOrderID(moduleName, methodName, productInfo)\n'
                '    LoadingWait:begin(self)\n'
                '    local product = {\n'
                '        productInfo.ProductId or productInfo.monthCardId,\n'
                '        IPlatform:getInstance():getDeviceMAC(),\n'
                '        IPlatform:getInstance():getDeviceUUID(),\n'
                '        IPlatform:getInstance():getDeviceIMEI()\n'
                '    }\n'
                '    HttpRequest(moduleName, methodName, product, function(response)\n'
                '        LoadingWait:ends()\n'
                '        if response.Status == 0 then\n'
                '            local isMothCard = productInfo.ProductId == nil\n'
                '            local orderId = isMothCard and response.Value.OrderId or response.Value\n'
                '            local desc = isMothCard and TR("Xác nhận kích hoạt Thẻ Tháng (Offline)?") or string.format(TR("Xác nhận nạp %d Kim Cương (Offline)?"), tonumber(productInfo.GamePoint) or 0)\n'
                '            local box = require("Common.MessageBoxLayer").new({\n'
                '                bgImage = "c_43.png",\n'
                '                closeBtnImage = "c_15.png",\n'
                '                title = TR("提示"),\n'
                '                content = desc,\n'
                '                leftBtnTitle = TR("确定"),\n'
                '                rightBtnTitle = TR("取消"),\n'
                '                leftBtnCallback = function(dlg)\n'
                '                    dlg:removeFromParent()\n'
                '                    LoadingWait:begin(self)\n'
                '                    if isMothCard then\n'
                '                        HttpRequest("CardInfo", "Activity", {productInfo.monthCardId, orderId}, function(res)\n'
                '                            LoadingWait:ends()\n'
                '                            if res.Status == 0 and res.Value then\n'
                '                                self.mMonthCardInfo = {}\n'
                '                                for _, item in pairs(res.Value) do\n'
                '                                    self.mMonthCardInfo[item.CardId] = item\n'
                '                                end\n'
                '                                self.mPlayerVipLv = NetworkResData:getPlayerInfo().Vip\n'
                '                                if self.mBkgLayer and self.mBkgLayer.refreshPlayerAttrs then\n'
                '                                    self.mBkgLayer:refreshPlayerAttrs()\n'
                '                                end\n'
                '                                self.mLeftTabLayer:reloadPage()\n'
                '                                ui.showFlashView({parent = self, text = TR("充值成功")})\n'
                '                            end\n'
                '                        end)\n'
                '                    else\n'
                '                        HttpRequest("PlayerCharge", "ConfirmOrder", {productInfo.ProductId, orderId}, function(res)\n'
                '                            LoadingWait:ends()\n'
                '                            if res.Status == 0 then\n'
                '                                ui.showFlashView({parent = self, text = TR("充值成功")})\n'
                '                                self.mChargeTotalInfo = nil\n'
                '                                self.mChargeSingleInfo = nil\n'
                '                                self.mChargeDaysInfo = nil\n'
                '                                self:requestGetChargeList(true)\n'
                '                            end\n'
                '                        end)\n'
                '                    end\n'
                '                end,\n'
                '                rightBtnCallback = function(dlg)\n'
                '                    dlg:removeFromParent()\n'
                '                end,\n'
                '            })\n'
                '            display.getRunningScene():addChild(box, 256)\n'
                '        end\n'
                '    end)\n'
                'end',
            ),
        ],
    )
    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "ExtraActivity" / "MonthCardLayer.luac",
        [
            (
                'function MonthCardLayer:handleOrderID(ok, content, id)\n'
                '    if not ok then return end\n\n'
                '    local config = self.model[id]\n\n'
                '    local serverInfo    = NetworkResData:getServerInfo(true)\n'
                '    local userLoginInfo = NetworkResData:getUserLoginInfo()\n'
                '    local playerInfo    = NetworkResData:getPlayerInfo()\n\n'
                '    local order = {\n'
                '        ProductName    = config.card_name,\n'
                '        ProductID      = content.ProductId,  -- 使用生成的产品ID\n'
                '        OrderID        = content.OrderId,    -- 使用生成的OrderID\n'
                '        CurNum         = 0,\n'
                '        BuyNum         = 1,\n'
                '        PresentNum     = 300,                   --: 赠送(元宝)数目(int)\n'
                '        Price          = config.active_price,   --: 价格(元)(int)\n'
                '        ServerID       = serverInfo.ServerID,   --: 当前服务器ID(int)\n'
                '        ServerName     = serverInfo.ServerName, --: 当前服务器名称(string)\n'
                '        PlayerID       = playerInfo.PlayerId,   -- 玩家ID(string)\n'
                '        PlayerLevel    = playerInfo.Lv,         --: 玩家等级(int)\n'
                '        PlayerName     = playerInfo.PlayerName, --: 玩家名称(string)\n'
                '        PlayerVipLevel = playerInfo.Vip,        --: 玩家VIP等级(int)\n'
                '        ExtData        = userLoginInfo.ExtraData,   -- 登录服务器时返回的额外信息\n'
                '        NotifyUrl      = serverInfo.ChargeServerUrl,-- 充值回调地址\n'
                '    }\n\n'
                '    config.OrderID = content\n'
                '    IPlatform:getInstance():recharge(json.encode(order), function(result)\n'
                '        self:onPurchaseFinish(result, id)\n'
                '    end)\n'
                'end',
                'function MonthCardLayer:handleOrderID(ok, content, id)\n'
                '    if not ok then return end\n'
                '    local box = require("Common.MessageBoxLayer").new({\n'
                '        bgImage = "c_43.png",\n'
                '        closeBtnImage = "c_15.png",\n'
                '        title = TR("提示"),\n'
                '        content = TR("Xác nhận kích hoạt Thẻ Tháng (Offline)?"),\n'
                '        leftBtnTitle = TR("确定"),\n'
                '        rightBtnTitle = TR("取消"),\n'
                '        leftBtnCallback = function(dlg)\n'
                '            dlg:removeFromParent()\n'
                '            self.params.parent:newRequest({\n'
                '                module = "CardInfo",\n'
                '                method = "Activity",\n'
                '                data = {id, content.OrderId},\n'
                '                callback = function(actOk, actVal)\n'
                '                    if actOk then\n'
                '                        self:onPurchaseFinish("ok", id)\n'
                '                        if self.params.parent and self.params.parent.mBkgLayer and self.params.parent.mBkgLayer.refreshPlayerAttrs then\n'
                '                            self.params.parent.mBkgLayer:refreshPlayerAttrs()\n'
                '                        end\n'
                '                    end\n'
                '                end,\n'
                '            })\n'
                '        end,\n'
                '        rightBtnCallback = function(dlg)\n'
                '            dlg:removeFromParent()\n'
                '        end,\n'
                '    })\n'
                '    display.getRunningScene():addChild(box, 256)\n'
                'end',
            ),
            (
                'function MonthCardLayer:onPurchaseFinish(result, id)\n    IPlatform:getInstance():rechargeEnd()',
                'function MonthCardLayer:onPurchaseFinish(result, id)',
            ),
        ],
    )
    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "TimedActivity" / "LimittedTimedRecruitLayer.luac",
        [
            (
                '    self:loadActivityData()\n\n'
                '    self:createBgUI()\n'
                '    self:initUI()',
                '    self:loadActivityData(params)\n\n'
                '    self:createBgUI()\n'
                '    self:initUI()',
            ),
            (
                'function LimittedTimedRecruitLayer:loadActivityData( ... )\n'
                '     self.activityId = ModuleSub.eTimedRecruit\n\n'
                '    local activityInfo = NetworkResData:getTimedActivityOpenInfo(true, true)\n'
                '    local _,v = next(activityInfo[ModuleSub.eTimedRecruit] or {})',
                'function LimittedTimedRecruitLayer:loadActivityData(params)\n'
                '     self.activityId = ModuleSub.eTimedRecruit\n\n'
                '    local activityInfo = NetworkResData:getTimedActivityOpenInfo(true, true)\n'
                '    local bannerList = activityInfo[ModuleSub.eTimedRecruit] or {}\n'
                '    self.mBannerList = bannerList\n'
                '    local wantId = params and params.selectedActivityId or nil\n'
                '    local v = nil\n'
                '    if wantId then\n'
                '        for _, item in ipairs(bannerList) do\n'
                '            if item.ActivityId == wantId then v = item break end\n'
                '        end\n'
                '    end\n'
                '    if not v then local _, firstItem = next(bannerList); v = firstItem end',
            ),
            (
                '    for k,v in pairs(self.mPlayerAttrNodes) do\n'
                '        if not tolua.isnull(v.sprite) then\n'
                '            v.sprite:setPositionY(self.mBgSize.height - 35)\n'
                '        end\n'
                '    end\n'
                'end',
                '    for k,v in pairs(self.mPlayerAttrNodes) do\n'
                '        if not tolua.isnull(v.sprite) then\n'
                '            v.sprite:setPositionY(self.mBgSize.height - 35)\n'
                '        end\n'
                '    end\n'
                '    if self.mBannerList and #self.mBannerList > 1 then\n'
                '        for bIdx, bItem in ipairs(self.mBannerList) do\n'
                '            local bId = bItem.ActivityId\n'
                '            local isCur = (bId == self.mActivityInfo.enumId)\n'
                '            local shortName = bId == 81 and "Sessho (81)" or (bId == 82 and "InuTaishou (82)" or (bId == 83 and "Thần Tướng D (83)" or ("Banner " .. tostring(bId))))\n'
                '            local tabBtn = ui.newButton({\n'
                '                normalImage = isCur and "c_77.png" or "c_7.png",\n'
                '                text = shortName,\n'
                '                scale = 0.85,\n'
                '                position = cc.p(135 + (bIdx - 1) * 160, self.mBgSize.height - 102),\n'
                '                clickAction = function()\n'
                '                    if isCur then return end\n'
                '                    self:newRequest({\n'
                '                        module = "TimedRecruitInfo",\n'
                '                        method = "SelectBanner",\n'
                '                        data = {bId},\n'
                '                        callback = function(selOk)\n'
                '                            if not selOk then return end\n'
                '                            local parentNode = self:getParent()\n'
                '                            local zOrd = self:getLocalZOrder()\n'
                '                            self:removeFromParent()\n'
                '                            if parentNode then\n'
                '                                local newLayer = require("TimedActivity.LimittedTimedRecruitLayer").new({selectedActivityId = bId})\n'
                '                                parentNode.mModalLayer = newLayer\n'
                '                                parentNode:addChild(newLayer, zOrd)\n'
                '                            end\n'
                '                        end,\n'
                '                    })\n'
                '                end,\n'
                '            })\n'
                '            self.mBgSprite:addChild(tabBtn, 20)\n'
                '        end\n'
                '    end\n'
                'end',
            ),
            (
                'function LimittedTimedRecruitLayer:requestSync()\n'
                '    self:newRequest({\n'
                '        module   = "TimedRecruitInfo",\n'
                '        method   = "GetTimedRecruitInfo",\n'
                '        callback = self.handleSync,',
                'function LimittedTimedRecruitLayer:requestSync()\n'
                '    self:newRequest({\n'
                '        module   = "TimedRecruitInfo",\n'
                '        method   = "GetTimedRecruitInfo",\n'
                '        data     = {self.mActivityInfo and self.mActivityInfo.enumId},\n'
                '        callback = self.handleSync,',
            ),
            (
                '                self:newRequest({\n'
                '                    module   = "TimedRecruitInfo",\n'
                '                    method   = "Recruit",\n'
                '                    data     = {type},\n'
                '                    callback = self.handleRecruit,\n'
                '                    context  = self,\n'
                '                })\n'
                '            end\n'
                '        else\n'
                '            self.lastRequestTimes = times or 1\n'
                '            self:newRequest({\n'
                '                module   = "TimedRecruitInfo",\n'
                '                method   = "Recruit",\n'
                '                data     = {type},',
                '                self:newRequest({\n'
                '                    module   = "TimedRecruitInfo",\n'
                '                    method   = "Recruit",\n'
                '                    data     = {type, self.activityEnumId or (self.mActivityInfo and self.mActivityInfo.enumId)},\n'
                '                    callback = self.handleRecruit,\n'
                '                    context  = self,\n'
                '                })\n'
                '            end\n'
                '        else\n'
                '            self.lastRequestTimes = times or 1\n'
                '            self:newRequest({\n'
                '                module   = "TimedRecruitInfo",\n'
                '                method   = "Recruit",\n'
                '                data     = {type, self.activityEnumId or (self.mActivityInfo and self.mActivityInfo.enumId)},',
            ),
            (
                '    HttpRequest("TimedRecruitInfo", "DrawCreditReward", {credit}, function(result)',
                '    HttpRequest("TimedRecruitInfo", "DrawCreditReward", {credit, self.activityEnumId or (self.mActivityInfo and self.mActivityInfo.enumId)}, function(result)',
            ),
            (
                '    self:newRequest({\n'
                '        module   = "TimedRecruitInfo",\n'
                '        method   = "DrawGoldHero",\n'
                '        data     = {heroID},',
                '    self:newRequest({\n'
                '        module   = "TimedRecruitInfo",\n'
                '        method   = "DrawGoldHero",\n'
                '        data     = {heroID, self.activityEnumId or (self.mActivityInfo and self.mActivityInfo.enumId)},',
            ),
            (
                'function LimittedTimedRecruitLayer:handleRecruit(ok, content, type)\n'
                '    if not ok then return end',
                'function LimittedTimedRecruitLayer:handleRecruit(ok, content, type)\n'
                '    if not ok then\n'
                '        if content == -2005 then\n'
                '            checkBagSpace({checkBag = {BagType.eHero}, parent = self})\n'
                '        end\n'
                '        return\n'
                '    end',
            ),
            (
                '        Ctrl.showRewardList(\n'
                '            content,\n'
                '            function(type)\n'
                '                self:requestRecruit(type)\n'
                '            end,\n'
                '            nil,\n'
                '            self.mBaseData,\n'
                '            self.ActivityEnumId\n'
                '        )',
                '        Ctrl.showRewardList(\n'
                '            content,\n'
                '            function(type)\n'
                '                self:requestRecruit(type)\n'
                '            end,\n'
                '            function()\n'
                '                if self.mBaseData and self.mBaseData.DrawGoldHero == 0 then\n'
                '                    local activityId = self.ActivityEnumId\n'
                '                    local config = TimedRecruitModel.items[activityId]\n'
                '                    local layer = require("TimedActivity.TimedRecruitChoiceBoxLayer").new({\n'
                '                        outid = config.goldHeroModelID,\n'
                '                        recruit = type,\n'
                '                        data = self.mBaseData,\n'
                '                        callBack = function(recruit)\n'
                '                            self:requestRecruit(recruit)\n'
                '                        end,\n'
                '                    })\n'
                '                    display.getRunningScene():addChild(layer)\n'
                '                end\n'
                '            end,\n'
                '            self.mBaseData,\n'
                '            self.ActivityEnumId\n'
                '        )',
            ),
        ],
    )

    # 6. Standalone offline ChatMng, SystemLayer, StartGameScene, and AccountSwitchLayer patches
    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "Chat" / "ChatMng.luac",
        [
            (
                '    if ip and port then\n'
                '        -- 登陆IP\n'
                '        print("chat server:", ip, port)\n'
                '        local result = self.mSocketMng:init(ip, port, "", self.mListener_)',
                '    if false and ip and port then\n'
                '        -- Offline standalone: disable background TCP socket reconnect loop\n'
                '        local result = self.mSocketMng:init(ip, port, "", self.mListener_)',
            ),
            (
                '    local cmd = json.encode({CommandType = ChatMng.CMD_TYPE_SEND_MSG, Command = ctx})\n'
                '    print("send:", cmd)\n'
                '    self.mSocketMng:addMessageToSendQueue(cmd)',
                '    if self.mSocketMng and self.mConnStatus then\n'
                '        local cmd = json.encode({CommandType = ChatMng.CMD_TYPE_SEND_MSG, Command = ctx})\n'
                '        self.mSocketMng:addMessageToSendQueue(cmd)\n'
                '    end',
            ),
            (
                '    local cmd = json.encode({CommandType = ChatMng.CMD_TYPE_UPDATE_PLAYER_INFO, Command = ctx})\n\n'
                '    print(cmd, "updatePlayerInfo")\n'
                '    self.mSocketMng:addMessageToSendQueue(cmd)',
                '    if self.mSocketMng and self.mConnStatus then\n'
                '        local cmd = json.encode({CommandType = ChatMng.CMD_TYPE_UPDATE_PLAYER_INFO, Command = ctx})\n'
                '        self.mSocketMng:addMessageToSendQueue(cmd)\n'
                '    end',
            ),
        ],
    )
    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "System" / "SystemLayer.luac",
        [
            (
                '    canLogout = canLogout:len() == 0 and "true" or canLogout',
                '    canLogout = "true"',
            ),
        ],
    )
    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "Login" / "StartGameScene.luac",
        [
            (
                '    btnEnterGame:setScale(Adapter.MinScale)\n'
                '    self:addChild(btnEnterGame) ',
                '    btnEnterGame:setScale(Adapter.MinScale)\n'
                '    self:addChild(btnEnterGame)\n'
                '    local btnAcctMgr = ui.newButton({\n'
                '        normalImage = "c_7.png",\n'
                '        position = Adapter.AutoPos(960, 100),\n'
                '        text = "TK / Sao Lưu",\n'
                '        fontSize = 20,\n'
                '        textColor = ColorList.ccWhite,\n'
                '        outlineColor = ColorList.ccOutline,\n'
                '        clickAction = function()\n'
                '            self:addChild(require("System.AccountSwitchLayer").new(), 1026)\n'
                '        end\n'
                '    })\n'
                '    btnAcctMgr:setScale(Adapter.MinScale * 0.9)\n'
                '    self:addChild(btnAcctMgr)',
            ),
        ],
    )
    write_luac_text(
        STANDALONE_WORK / "assets" / "src" / "System" / "AccountSwitchLayer.luac",
        ACCOUNT_SWITCH_LAYER_LUA,
    )

    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "TimedActivity" / "TimedSlotLayer.luac",
        [("local pos = slot:get_cur_pos(cursors[i])", "local pos = slot:get_cur_pos(i)")],
    )

    patch_r712_lua(STANDALONE_WORK / "assets" / "src")
    patch_reward_claim_lua(STANDALONE_WORK / "assets" / "src")
    patch_mystery_shop_lua(STANDALONE_WORK / "assets" / "src")
    patch_r714_lua(STANDALONE_WORK / "assets" / "src")
    patch_r715_lua(STANDALONE_WORK / "assets" / "src")
    patch_r7151_lua(STANDALONE_WORK / "assets" / "src")
    patch_r716_explore_lua(STANDALONE_WORK / "assets" / "src")
    patch_luac_text(STANDALONE_WORK / "assets" / "src" / "Equipment" / "EquipmentComposeLayer.luac", [
        (
            '        if colorLV < 8 then    --排除最高等级的装备',
            '        local recipe = EquipColorRelation.items[colorLV]\n'
            '        if recipe and recipe.colorFinally > colorLV then',
        ),
    ])
    patch_luac_text(STANDALONE_WORK / "assets" / "src" / "Store" / "RecruitScene.luac", [
        (
            'local cnt = singleUsed.count * (priceSave and (priceSave / 100) or 1)',
            'local cnt = math.ceil(singleUsed.count * (priceSave or 100) / 100)',
        ),
        (
            'local tenCnt = tenConsume.count * (priceSave and (priceSave / 100) or 1)',
            'local tenCnt = math.ceil(tenConsume.count * (priceSave or 100) / 100)',
        ),
    ])

    # 6b. Bundle VN-adapted TW 1.4 Config/*.lua tables missing from VN 5.0.4.98 APK
    for cfg_name in (
        "XssbModel",
        "CriticalTasksTypeRelation",
        "EarlytaskModel",
        "EarlytaskRewardRelation",
        "TraderConfig",
    ):
        cfg_src = ROOT_DIR / "analysis" / "vn" / "decompiled_src" / "Config" / f"{cfg_name}.lua"
        if not cfg_src.exists():
            raise FileNotFoundError(f"Missing VN-adapted config Lua: {cfg_src}")
        write_luac_text(
            STANDALONE_WORK / "assets" / "src" / "Config" / f"{cfg_name}.luac",
            cfg_src.read_text(encoding="utf-8"),
        )

    # 7. Bundle embedded 32-bit CPython 3.11 + server_bundle.zip + stdlib.zip
    bundle_embedded_python(STANDALONE_WORK, f"{version_name}-{version_code}")

    # 8. Merge OBB res/* directly into assets/res/* for 1-file installation
    merged_n = merge_obb_into_assets(STANDALONE_WORK)
    print(f"Merged {merged_n} OBB resource files directly into APK assets/res/")

    # 9. Bundle Banner 83 / Tứ Đấu Thần / Inu Kimi assets missing from VN APK/OBB
    b83_dir = ROOT_DIR / "android" / "assets_b83"
    if b83_dir.exists():
        b83_n = 0
        for src_file in sorted(b83_dir.rglob("*")):
            if src_file.is_file():
                rel = src_file.relative_to(b83_dir)
                dst_file = STANDALONE_WORK / "assets" / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                b83_n += 1
        print(f"Bundled {b83_n} Banner 83 assets from {b83_dir}")


def patch_r712_lua(src: Path) -> None:
    patch_luac_text(src / "TimedActivity" / "TimedEquipRankLayer.luac", [
        (
            '        onCloseCallback = function(self)\n'
            '            if self.onCloseCallback then\n'
            '                self.onCloseCallback(self)\n'
            '            else\n'
            '                self:removeFromParent()\n'
            '            end\n'
            '        end,\n',
            '',
        ),
    ])
    patch_luac_text(src / "Network" / "ServerMessage.luac", [
        (
            '[-2008] = TR("战灵背包已满"),',
            '[-2008] = TR("战灵背包已满"),\n'
            '\t[-2009] = "Phần thưởng này chưa được hỗ trợ. Vật phẩm vẫn còn trong túi.",\n'
            '\t[-2010] = "Không còn mảnh bảo vật phù hợp để tìm.",',
        ),
    ])
    patch_luac_text(src / "Task" / "TaskRewardPreviewLayer.luac", [
        (
            '            elseif status == 1 then\n'
            '                if checkBagSpace() == true then\n'
            '                    if params.callback then',
            '            elseif status == 1 then\n'
            '                local needBags, seenBags = {}, {}\n'
            '                local function addBag(bid)\n'
            '                    if bid and not seenBags[bid] then\n'
            '                        seenBags[bid] = true\n'
            '                        table.insert(needBags, bid)\n'
            '                    end\n'
            '                end\n'
            '                for _, item in ipairs(params.rewards or {}) do\n'
            '                    local rt = item.resourceTypeSub or item.resourcetypeSub\n'
            '                    if rt == ResourcetypeSub.eHero then\n'
            '                        addBag(BagType.eHero)\n'
            '                    elseif ResourceSubIsEquip(rt) or ResourceSubIsTreasure(rt) then\n'
            '                        addBag(BagType.eEquip)\n'
            '                    elseif rt and math.floor(rt / 100) == 16 then\n'
            '                        addBag(BagType.eProps)\n'
            '                    end\n'
            '                end\n'
            '                if #needBags == 0 or checkBagSpace({checkBag = needBags}) == true then\n'
            '                    if params.callback then',
        ),
    ])
    patch_luac_text(src / "Store" / "RecruitScene.luac", [
        (
            'function RecruitScene:responseRecruit(response)\n'
            '    LoadingWait:ends()\n'
            '    if response and response.Status == 0 then',
            'function RecruitScene:responseRecruit(response)\n'
            '    LoadingWait:ends()\n'
            '    if response and response.Status == -2005 then\n'
            '        checkBagSpace({checkBag = {BagType.eHero}, parent = self})\n'
            '        return\n'
            '    end\n'
            '    if response and response.Status == 0 then',
        ),
    ])
    patch_luac_text(src / "Config" / "BagModel.luac", [
        ('name = "Tướng",\n            initSize = 100,', 'name = "Tướng",\n            initSize = 300,'),
    ])
    patch_luac_text(src / "Bag" / "BagExpandTipLayer.luac", [
        (
            '    local expandNum = bagData.ExpandNum\n'
            '    if expandNum >= table.maxn(BagExpandUseRelation.items)  then\n'
            '        expandNum = (table.maxn(BagExpandUseRelation.items) - 1)\n'
            '    end',
            '    local nextExpansion = BagExpandUseRelation.items[bagData.ExpandNum + 1]',
        ),
        (
            'local expandCharge = BagExpandUseRelation.items[expandNum + 1].useDiamondNum',
            'local expandCharge = nextExpansion and nextExpansion.useDiamondNum or 0',
        ),
        (
            '    text = string.format(TR("你确定要花费',
            '    text = not nextExpansion and "Túi đã đạt sức chứa tối đa." or string.format(TR("你确定要花费',
        ),
        ('if not BagExpandUseRelation.items[expandNum + 1] then', 'if not nextExpansion then'),
        ('if not BagExpandUseRelation.items[expandNum + 1] then', 'if not nextExpansion then'),
    ])
    patch_luac_text(src / "Hero" / "HeroUpdateScene.luac", [
        (
            'function HeroUpdateScene:requestHeroStepUp(heroId)\n',
            'function HeroUpdateScene:requestHeroStepUp(heroId)\n'
            '    if self.mHeroStepPending then return end\n',
        ),
        (
            '    LoadingWait:begin(self)\n'
            '    HttpRequest("Hero","HeroStepUp", {heroId, materialEntity}, handler(self, self.responseHeroStepUp))',
            '    self.mHeroStepPending = true\n'
            '    LoadingWait:begin(self)\n'
            '    HttpRequest("Hero","HeroStepUp", {heroId, materialEntity, self.mHero.Step}, '
            'handler(self, self.responseHeroStepUp))',
        ),
        (
            'function HeroUpdateScene:responseHeroStepUp(event)\n    LoadingWait:ends()',
            'function HeroUpdateScene:responseHeroStepUp(event)\n    LoadingWait:ends()\n'
            '    if not event or event.Status ~= 0 then self.mHeroStepPending = false end',
        ),
        (
            '            self.mHero = event.Value\n'
            '            --刷新界面\n'
            '            self:createHeroBreakthrough(event.Value.Step)',
            '            self.mHero = event.Value\n'
            '            self.mHeroStepPending = false\n'
            '            --刷新界面\n'
            '            self:createHeroBreakthrough(event.Value.Step)',
        ),
        (
            'function HeroUpdateScene:createHeroBreakthrough(step)',
            '''function HeroUpdateScene:openBreakthroughTreasure(resourceType, modelId)
    local isOpen, info = NetworkResData:modulePlayerIsOpen(ModuleSub.eChallengeGrab)
    if not isOpen then
        ui.showFlashView({parent = self, text = info.openMessage})
        return
    end
    local hero = self.mHero
    local returnCallback = self.returnCallback
    game.replaceScene(require("Grab.GrabTreasureScene").new({
        selectType = resourceType == ResourcetypeSub.eBook and 2 or 1,
        treasureId = modelId,
        onCloseCallback = function()
            local currentHero = NetworkResData:getHero(hero.Id) or hero
            game.replaceScene(require("Hero.HeroUpdateScene").new(HeroEnhance.eBreakthrough, currentHero, returnCallback))
        end,
    }), "CCtransitionCrossFade", 0)
end

function HeroUpdateScene:createHeroBreakthrough(step)''',
        ),
        (
            '''                    local call = function()
                        local hero = self.mHero

                        local isOpen, retInfo = NetworkResData:modulePlayerIsOpen(ModuleSub.eChallengeGrab)
                        if not isOpen then
                            ui.showFlashView({parent = self, text = retInfo.openMessage,})
                            return
                        end

                        local returnCallback = self.returnCallback
                        if tonumber(material[1]) == ResourcetypeSub.eBook then
                            game.replaceScene(require("Grab.GrabTreasureScene").new({ selectType = 2, treasureId = tonumber(material[2]), onCloseCallback = function()
                                game.replaceScene(require("Hero.HeroUpdateScene").new(HeroEnhance.eBreakthrough, hero, returnCallback))
                            end}), "CCtransitionCrossFade", 0.0)
                        else
                            game.replaceScene(require("Grab.GrabTreasureScene").new({ selectType = 1, treasureId = tonumber(material[2]), onCloseCallback = function()
                                game.replaceScene(require("Hero.HeroUpdateScene").new(HeroEnhance.eBreakthrough, hero, returnCallback))
                            end}), "CCtransitionCrossFade", 0.0)
                        end

                    end''',
            '''                    local call = function()
                        self:openBreakthroughTreasure(tonumber(material[1]), tonumber(material[2]))
                    end''',
        ),
    ])
    patch_luac_text(src / "Grab" / "GrabTreasureScene.luac", [
        ('local grabCloseCallback = nil\n', ''),
        (
            '    if pargrams and pargrams.onCloseCallback then    -- add by liaoyuangang 解决从队伍页面调用夺宝，合成后关闭夺宝页面不能回到队伍页面的问题。\n'
            '        grabCloseCallback = pargrams.onCloseCallback\n'
            '    end',
            '    self.mPargrams = pargrams',
        ),
        (
            '            if grabCloseCallback then  -- modify by liaoyuangang 解决从队伍页面调用夺宝，合成后关闭夺宝页面不能回到队伍页面的问题。\n'
            '                grabCloseCallback()\n'
            '                grabCloseCallback = nil',
            '            local callback = self.mPargrams and self.mPargrams.onCloseCallback\n'
            '            if callback then\n'
            '                callback()',
        ),
        ('    self.mParentSprite = self.bgLayer:getBackgroundSprite()\n    self.mPargrams = pargrams',
         '    self.mParentSprite = self.bgLayer:getBackgroundSprite()'),
        (
            '    for i, v1 in pairs(allTreasureTable) do\n        if v1.ifBase and v1.typeID == resourceType then',
            '    local targetId = self.mPargrams and self.mPargrams.treasureId\n'
            '    for i, v1 in pairs(allTreasureTable) do\n'
            '        if (v1.ifBase or v1.ID == targetId) and v1.typeID == resourceType then',
        ),
    ])
    patch_luac_text(src / "Grab" / "TreasureDebrisLayer.luac", [
        (
            '                    local callFunc =function()\n                        local type = TreasureModel.items[treasureModel.ID].typeID',
            '                    local grabScene = self:getParent():getParent():getParent():getParent()\n'
            '                    local onClose = grabScene.mPargrams and grabScene.mPargrams.onCloseCallback\n'
            '                    local callFunc =function()\n                        local type = TreasureModel.items[treasureModel.ID].typeID',
        ),
        (
            'treasureId = treasureModel.ID, selectType = selectType}',
            'treasureId = treasureModel.ID, selectType = selectType, onCloseCallback = onClose}',
        ),
    ])
    patch_luac_text(src / "TimedActivity" / "TimedPrayTree.luac", [
        ('local CacheData = require("Common.PlayerCacheData")\n', ''),
        (
            '''    local cache = CacheData:get("TimedPrayTree")

    if not cache  then
        self:requestTreeData()
    else
        self.mNeedDiamond = cache.NeedNum
        self.mCurrentDiamond = cache.Num
        self.mTotalDay = cache.RewardNum
        self:refreshUi(cache.EndTime, cache.NeedNum, cache.Num, self.mTotalDay)
        self:createListView(cache.RewardList)
    end''',
            '    self:requestTreeData()',
        ),
        ('        CacheData:set("TimedPrayTree", event.Value)\n', ''),
        (
            '    self:addChild(rechargeButton, 1)',
            '    self:addChild(rechargeButton, 1)\n'
            '    self.mRechargeButton = rechargeButton\n'
            '    rechargeButton:setVisible(false)',
        ),
        (
            '        text        = string.format(TR("活动期间，累计充满{fbfe00}%d{db_1111.png}{ffffff}可激活许愿树，领取{fbfe00}%d{ffffff}天许愿奖励"),0,0),',
            '        text        = "",',
        ),
        (
            '''function TimedPrayTree:refreshUi(missTime, needDiamond, currentDiamond,day)
    if needDiamond > currentDiamond then
        self.mChargeLabel:setString(string.format("{db_1111.png}%d",currentDiamond))
    else
        self.mChargeLabel:setString(string.format("{db_1111.png}%d",currentDiamond))
    end
    self.mTishi:setString(string.format(TR("活动期间，累计充满{fbfe00}%d{db_1111.png}{ffffff}可激活许愿树，领取{fbfe00}%d{ffffff}天许愿奖励"),needDiamond,day))''',
            '''function TimedPrayTree:refreshEligibility(rewards)
    local canRecharge = #rewards > 0 and self.mCurrentDiamond < self.mNeedDiamond
    self.mRechargeButton:setVisible(canRecharge)
    if #rewards == 0 then
        self.mTishi:setString("Đã nhận đủ quà Cây Ước trong kỳ này.")
    elseif canRecharge then
        self.mTishi:setString(string.format("Nạp đủ {fbfe00}%d{db_1111.png}{ffffff} trong kỳ để kích hoạt Cây Ước.", self.mNeedDiamond))
    else
        self.mTishi:setString("Cây Ước đã kích hoạt. Hãy nhận quà còn lại.")
    end
end

function TimedPrayTree:refreshUi(missTime, needDiamond, currentDiamond, rewards)
    self.mChargeLabel:setString(string.format("{db_1111.png}%d/%d", currentDiamond, needDiamond))
    self:refreshEligibility(rewards)''',
        ),
        (
            'self:refreshUi(self.mEndTime, self.mNeedDiamond, self.mCurrentDiamond, self.mTotalDay)',
            'self:refreshUi(self.mEndTime, self.mNeedDiamond, self.mCurrentDiamond, event.Value.RewardList)',
        ),
        (
            '        self.mListview:removeItem(self.mIndex)',
            '        self.mListview:removeItem(self.mIndex)\n'
            '        self:refreshEligibility(event.Value.RewardList)',
        ),
        (
            '''        local cache ={}
        cache.NeedNum = self.mNeedDiamond
        cache.Num = self.mCurrentDiamond
        cache.RewardNum = self.mTotalDay
        cache.EndTime = self.mEndTime
        cache.RewardList = event.Value.RewardList

        CacheData:set("TimedPrayTree", cache)''',
            '',
        ),
    ])


def patch_r714_lua(src: Path) -> None:
    patch_luac_text(src / "Practice" / "LightenStarScene.luac", [
        (
            '    if starCount < targetStarInfo.needStar then',
            '    if LightenStarInfo.ID == AttrtreeModel.items[#AttrtreeModel.items].ID then\n'
            '        ui.showFlashView({parent = self, text = TR("悟道已完成")})\n'
            '    elseif starCount < targetStarInfo.needStar then',
        ),
        (
            '    elseif LightenStarInfo.ID == AttrtreeModel.items[#AttrtreeModel.items].ID then\n'
            '        --点星已经达到最大\n'
            '        ui.showFlashView({parent = self, text = TR("悟道已完成"),})\n',
            '',
        ),
    ])
    patch_luac_text(src / "NewXZYY" / "XzyyMainScene.luac", [
        (
            '    FTPSprite :setScale(Adapter.MinScale)',
            '''    FTPSprite :setScale(Adapter.MinScale)
    self.mSimulationLabel = ui.newLabel({
        text = "", font = _FONT_DEFAULT, size = 20,
        color = ColorList.ccWhite, needOutLine = true,
    })
    self.mSimulationLabel:setPosition(cc.p(445 * Adapter.AutoScaleX, display.height - 138 * Adapter.AutoScaleY))
    self.mSimulationLabel:setScale(Adapter.MinScale)
    self.mBgLayer:addChild(self.mSimulationLabel)
    local catalogueBtn = ui.newButton({
        normalImage = "c_77.png", text = "Danh sách ải", fontSize = 24,
        clickAction = function() self:showCatalogue() end,
    })
    catalogueBtn:setPosition(cc.p(490 * Adapter.AutoScaleX, 50 * Adapter.AutoScaleY))
    catalogueBtn:setScale(Adapter.MinScale)
    self.mBgLayer:addChild(catalogueBtn)''',
        ),
        (
            'function XzyyMainScene:refeshData(needAction)',
            '''function XzyyMainScene:showCatalogue()
    if not self.mCatalogue then return end
    local layer = require("Common.ModalColorLayer").new({
        bgImage = "c_43.png", title = "Mộ Thần Binh", closeBtnImage = "c_15.png",
    })
    local size = layer.mBgSprite:getContentSize()
    local list = ccui.ListView:create()
    list:setDirection(ccui.ScrollViewDir.vertical)
    list:setTouchEnabled(true)
    list:setContentSize(cc.size(size.width * 0.85, size.height * 0.65))
    list:setPosition(cc.p(size.width * 0.075, size.height * 0.14))
    layer.mBgSprite:addChild(list)
    for _, entry in ipairs(self.mCatalogue) do
        local cell = ccui.Layout:create()
        cell:setContentSize(cc.size(size.width * 0.85, 39))
        local state = "Có thể đánh"
        if entry.StarCount > 0 then
            state = string.format("%d sao", entry.StarCount)
        elseif not entry.Available then
            state = "Chưa mở mô phỏng"
        elseif entry.Locked then
            state = "Đang khóa"
        end
        local name = BddNodeModel.items[entry.Id].name
        local row = ui.newLabel({
            text = string.format("%02d  %s   -   %s", (entry.Floor - 11) * 3 + entry.Id % 10, name, state),
            size = 19, font = _FONT_DEFAULT, color = ColorList.ccWhite, needOutLine = true,
        })
        row:setAnchorPoint(cc.p(0, 0.5))
        row:setPosition(cc.p(8, 19))
        cell:addChild(row)
        list:pushBackCustomItem(cell)
    end
    self:addChild(layer)
end

function XzyyMainScene:refeshData(needAction)''',
        ),
        (
            '        local guan = (self.mFloor - 1) * 3 + self.mNode % 10 - 1',
            '        local guan = self.mClearedCount',
        ),
        (
            '            if v.floorModelID == (self.mFloor + 10 - 1) then',
            '            if v.floorModelID == self.mRewardFloor then',
        ),
        (
            'HttpRequest("BddInfo","RewardBox", {self.mFloor + 10 - 1,tempReward.stars }',
            'HttpRequest("BddInfo","RewardBox", {self.mRewardFloor,tempReward.stars }',
        ),
        *([(
            '        self.mLastFloorStar = event.Value.Info.BeforeFloorStarCount',
            '        local info = event.Value.Info\n'
            '        self.mLastFloorStar = info.BeforeFloorStarCount\n'
            '        self.mRewardFloor = info.RewardFloor\n'
            '        self.mClearedCount = info.ClearedCount',
        )] * 3),
        (
            '                        --请求BUff信息\n'
            '                        if self.mIsNeedBuff == true then\n'
            '                            self:requestSelectBuffList()\n'
            '                        end\n'
            '                        target:removeFromParent()',
            '                        target:removeFromParent()\n'
            '                        self:requestInitData()',
        ),
        (
            '    if event and event.Status == 0 then\n'
            '        --当前星星',
            '    if event and event.Status == 0 and event.Value and event.Value.Info then\n'
            '        self.mCatalogue = event.Value.Catalogue\n'
            '        if self.mSimulationLabel and event.Value.Simulation then\n'
            '            self.mSimulationLabel:setString(string.format("Đội NPC mô phỏng (%d/51 ải)", event.Value.PlayableCount))\n'
            '        end\n'
            '        --当前星星',
        ),
        (
            '                    static = self.mFloorInfor[i].Id  ~= self.mNode,',
            '                    static = self.mFloorInfor[i].Locked or self.mFloorInfor[i].Id ~= self.mNode,',
        ),
        (
            '                        if  self.mFloorInfor[i].Id  ~= self.mNode then',
            '                        if self.mFloorInfor[i].Locked or self.mFloorInfor[i].Id ~= self.mNode then',
        ),
        (
            '                if self.mFloorInfor[i].Id  == self.mNode then',
            '                if not self.mFloorInfor[i].Locked and self.mFloorInfor[i].Id == self.mNode then',
        ),
        (
            '    self.mCanUseStar = canUseStar\n    self:refeshData(true)',
            '    self.mCanUseStar = canUseStar\n    self:requestInitData()',
        ),
        (
            '        local tempLayer = require("NewXZYY.XzyyOneKeyLayer")',
            '        self.mCatalogue = event.Value.Catalogue\n'
            '        self.mHaveBuff = event.Value.BuffInfo\n'
            '        local tempLayer = require("NewXZYY.XzyyOneKeyLayer")',
        ),
        (
            '        if self.mShanhu then',
            '        self.mCatalogue = event.Value.Catalogue\n'
            '        if self.mShanhu then',
        ),
    ])
    patch_luac_text(src / "NewXZYY" / "XzyyPrepareFightLayer.luac", [
        (
            'function XzyyPrepareFightLayer:requestFight(NodeId,difficulty,isPassed)\n',
            'function XzyyPrepareFightLayer:requestFight(NodeId,difficulty,isPassed)\n'
            '    if self.mFightPending then return end\n'
            '    self.mFightPending = true\n',
        ),
        (
            'function XzyyPrepareFightLayer:responseFight(event)\n',
            'function XzyyPrepareFightLayer:responseFight(event)\n'
            '    self.mFightPending = false\n',
        ),
        (
            'BattleDataCache:setXZYYData({NodeId = self.mFightNodeId,Nandu = self.mFightNandu})',
            'BattleDataCache:setXZYYData({NodeId = self.mFightNodeId, Nandu = self.mFightNandu, FightToken = event.Value.FightToken})',
        ),
    ])
    patch_luac_text(src / "Adventure" / "BattleSettleLayer.luac", [
        (
            '{self.mXZYYData.NodeId, self.mXZYYData.Nandu, self.mFightResult.result,self.mFightResult.data, self.mFightResult.optional},',
            '{self.mXZYYData.NodeId, self.mXZYYData.Nandu, self.mFightResult.result, self.mFightResult.data, '
            'self.mFightResult.optional or {}, self.mXZYYData.FightToken},',
        ),
    ])
    patch_luac_text(src / "NewXZYY" / "XzyyStoreScene.luac", [
        (
            '                for j, v2 in pairs(equipment) do\n'
            '                    table.insert(IdList,v2.Id)\n'
            '                end',
            '                local selected = {}\n'
            '                for index = 1, useData[1].count do\n'
            '                    if not equipment[index] then return end\n'
            '                    selected[index] = equipment[index]\n'
            '                    IdList[index] = equipment[index].Id\n'
            '                end',
        ),
        ('NetworkResData:deleteEquipItems(equipment)', 'NetworkResData:deleteEquipItems(selected)'),
    ])


def patch_r715_lua(src: Path) -> None:
    patch_luac_text(src / "Equipment" / "EquipmentCommon.luac", [
        (
            "        local dataset = EquipLvUpuseRelation.items[colorLV]\n",
            "        local dataset = EquipLvUpuseRelation.items[colorLV]\n"
            "        if not dataset or not dataset[level] then return nil end\n",
        ),
    ])
    patch_luac_text(src / "Equipment" / "Module" / "EquipmentEnhanceLayer.luac", [
        (
            "    -- 提示信息\n    local reminderLabel = ui.newLabel({",
            "    local nextCost = Equipment.getEnhanceCost(equipObj)\n"
            "    if nextCost == nil then\n"
            "        local unavailable = ui.newLabel({text = \"Trang bị này chưa có giá cường hóa trong dữ liệu VN.\",\n"
            "            size = 22, color = ColorList.ccWhite, needOutLine = true})\n"
            "        unavailable:align(display.CENTER, nodeSize.width / 2, nodeSize.height / 2)\n"
            "        container:addChild(unavailable)\n"
            "        return container\n"
            "    end\n"
            "    -- 提示信息\n    local reminderLabel = ui.newLabel({",
        ),
        ("value= Equipment.getEnhanceCost(equipObj),", "value= nextCost,"),
    ])
    patch_luac_text(src / "NewXZYY" / "XzyyMainScene.luac", [
        (
            "    for i,v in pairs(BddWraithShopRelation.items) do\n",
            "    self.mIsRed = false\n"
            "    for i,v in pairs(BddWraithShopRelation.items) do\n",
        ),
        ("v.needStarNum <= self.mCurrentStar then", "v.needStarNum <= self.mMaxStar then"),
    ])


def patch_r716_explore_lua(src: Path) -> None:
    patch_luac_text(src / "Practice" / "XunYuScene.luac", [
        (
            '        while restoreTime < 0 do\n'
            '            restoreTime = restoreTime + self.model.restore_interval\n'
            '        end\n'
            '        time = restoreTime',
            '        time = math.max(0, restoreTime)',
        ),
        (
            '        self:requestSync()\n\n        self:executeGuide()',
            '        self:setTimeEvent(true)\n'
            '        self:requestSync()\n\n        self:executeGuide()',
        ),
        (
            '    if CacheData:get("XunYuScene.auto_state") then',
            '    if self.model.player.Vip >= self.model.auto_viplv and CacheData:get("XunYuScene.auto_state") then',
        ),
        (
            '        if self.model.xun_num > 0 then\n            if checkBagSpace() then',
            '        if self.model.request_running or self.model.action_running then return end\n'
            '        if self.model.xun_num == 0 and self.model.restore_time <= 0 then\n'
            '            self:requestSync(true)\n'
            '        elseif self.model.xun_num > 0 then\n            if checkBagSpace() then',
        ),
        (
            '''        local time = self.model.restore_time - delta
        if time < 0 then
            time = self.model.restore_interval
            self.model.xun_num = self.model.xun_num + 1
            self.handler.xun_num()
        end
        self.model.restore_time = time
        self.handler.restore_time()''',
            '''        self.model.restore_time = math.max(0, self.model.restore_time - delta)
        self.handler.restore_time()
        if self.model.restore_time <= 0 then
            self:requestSync(true)
        end''',
        ),
        (
            'function XunYuScene:requestSync()\n    self.model.request_block = true',
            'function XunYuScene:requestSync(silent)\n'
            '    if self.model.request_running then return end\n'
            '    self.model.request_block = not silent',
        ),
        (
            'function XunYuScene:handleSync(ok, content)\n    if not ok then return end\n    self.model.request_block = false',
            'function XunYuScene:handleSync(ok, content)\n'
            '    self.model.request_block = false\n'
            '    if not ok then\n'
            '        self.model.restore_time = 5\n'
            '        return\n'
            '    end',
        ),
        (
            '    self.handler.xun_num()\n    self:setTimeEvent(true)',
            '    self.handler.xun_num()\n    self.handler.restore_time()',
        ),
        (
            '    self.model.restore_time = XunYuRecoverTime - now',
            '    self.model.restore_time = math.max(0, XunYuRecoverTime - now)',
        ),
        (
            '    self.model.restore_time = content["RecoverTime"] - now',
            '    XunYuRecoverTime = content["RecoverTime"]\n'
            '    self.model.restore_time = math.max(0, XunYuRecoverTime - now)\n'
            '    self.handler.restore_time()',
        ),
        (
            '    self.model.restore_time = content["RecoverTime"] - now',
            '    XunYuRecoverTime = content["RecoverTime"]\n'
            '    self.model.restore_time = math.max(0, XunYuRecoverTime - now)\n'
            '    self.handler.restore_time()',
        ),
        (
            'function XunYuScene:requestBuy()\n    self.model.request_block = true',
            'function XunYuScene:requestBuy()\n'
            '    if self.model.request_running then return end\n'
            '    self.model.request_block = true',
        ),
        (
            '    if not ok then return end\n\n    local now = NetworkResData:getCurrentTime()',
            '    if not ok then\n'
            '        if content == -5103 then\n'
            '            self._buyview:removeSelf()\n'
            '            self:requestSync(true)\n'
            '        end\n'
            '        return\n'
            '    end\n\n    local now = NetworkResData:getCurrentTime()',
        ),
        (
            '        self.model.action_running = false\n        return\n    end\n\n    local now =',
            '        self.model.action_running = false\n'
            '        if content == -5101 then self:requestSync(true) end\n'
            '        return\n    end\n\n    local now =',
        ),
        (
            '        else\n            print("[error] no response")\n        end',
            '        else\n'
            '            table.insert(args, false)\n'
            '            config.callback(unpack(args))\n'
            '        end',
        ),
        (
            'function XunYuScene:onExitTransitionStart()\n'
            '    self:setTimeEvent(false)\n'
            'end',
            'function XunYuScene:onExitTransitionStart()\n'
            '    self:setTimeEvent(false)\n'
            '    self.model.action_running = false\n'
            '    self.model.request_running = false\n'
            '    self.model.xun_run = false\n'
            'end',
        ),
        (
            '    else\n'
            '        ShowRewardGoods(resourceList)\n'
            '    end',
            '    else\n'
            '        self.model.action_running = false\n'
            '        ShowRewardGoods(resourceList)\n'
            '    end',
        ),
        (
            '            if self.model.request_running then\n'
            '                self:runXunyuAction(callback)\n'
            '            else\n'
            '                return callback and callback()\n'
            '            end',
            '            if self.model.request_running then\n'
            '                self:runXunyuAction(callback)\n'
            '            else\n'
            '                self.model.action_running = false\n'
            '                return callback and callback()\n'
            '            end',
        ),
    ])
    patch_luac_text(src / "Disassemble" / "DisassembleNewScene.luac", [
        (
            '            if QualityModel.items[heroModelItem.quality].colorLV <=4 then\n'
            '                table.insert(self.mAutoLianHeroList2, v)\n'
            '            end',
            '            if QualityModel.items[heroModelItem.quality].colorLV <= 5 and heroModelItem.quality < 18 and heroModelItem.specialType ~= 255 and not v.IsLock and not v.IfLock then\n'
            '                table.insert(self.mAutoLianHeroList2, v)\n'
            '            end',
        ),
        (
            '            if not self.mAutoLianList or #self.mAutoLianList <= 0 then\n'
            '                ui.showFlashView({parent = cc.Director:getInstance():getRunningScene(), text = TR("没有可一键炼化的材料！")})\n'
            '                return\n'
            '            end\n\n'
            '            -- for i ,v in pairs(self.mSelectList) do\n'
            '            --     table.insert(self.mCellList, v.data)\n'
            '            -- end\n'
            '            -- self.mSelectList = {}\n'
            '            for i ,v in pairs(self.mAutoLianList) do\n'
            '                local temp ={}\n'
            '                temp.index = self.mMoveIndex\n'
            '                temp.data =  v\n'
            '                table.insert(self.mSelectList, temp)\n'
            '            end\n'
            '            self.mIsAutoLianhua = true\n'
            '            self:requestLianhua()',
            '            if not self.mAutoLianList or #self.mAutoLianList <= 0 then\n'
            '                ui.showFlashView({parent = cc.Director:getInstance():getRunningScene(), text = TR("没有可一键炼化的材料！")})\n'
            '                return\n'
            '            end\n'
            '            local function doBatchRefine()\n'
            '                for i ,v in pairs(self.mAutoLianList) do\n'
            '                    local temp ={}\n'
            '                    temp.index = self.mMoveIndex\n'
            '                    temp.data =  v\n'
            '                    table.insert(self.mSelectList, temp)\n'
            '                end\n'
            '                self.mIsAutoLianhua = true\n'
            '                self:requestLianhua()\n'
            '            end\n'
            '            if self.mSelectType == typeTable.eHero then\n'
            '                local orangeCnt = 0\n'
            '                for _, hv in ipairs(self.mAutoLianList) do\n'
            '                    local hm = HeroModel.items[hv.HeroModelId]\n'
            '                    if hm and QualityModel.items[hm.quality].colorLV == 5 then\n'
            '                        orangeCnt = orangeCnt + 1\n'
            '                    end\n'
            '                end\n'
            '                local confirmMsg = string.format("Xác nhận chuyển hóa nhanh %d tướng (trong đó có %d tướng Cam)?\\nKhông bao gồm tướng Đỏ/UR, ra trận, đồng hành hoặc đã bồi dưỡng.", #self.mAutoLianList, orangeCnt)\n'
            '                local confirmBox = require("Common.MessageBoxLayer").new({\n'
            '                    bgImage = "c_43.png",\n'
            '                    closeBtnImage = "c_15.png",\n'
            '                    title = TR("提示"),\n'
            '                    leftBtnTitle = TR("取消"),\n'
            '                    rightBtnTitle = TR("确定"),\n'
            '                    content = confirmMsg,\n'
            '                    rightBtnCallback = function(target)\n'
            '                        target:removeFromParent(true)\n'
            '                        doBatchRefine()\n'
            '                    end,\n'
            '                })\n'
            '                cc.Director:getInstance():getRunningScene():addChild(confirmBox, 256)\n'
            '            else\n'
            '                doBatchRefine()\n'
            '            end',
        ),
        (
            '    local lianhuaLable2 = ui.newLabel({\n'
            '        text = TR("橙色以下") ,',
            '    local lianhuaLable2 = ui.newLabel({\n'
            '        text = "Cam trở xuống" ,',
        ),
        (
            '    if havewaring == true then',
            '    if havewaring == true and not self.mIsAutoLianhua then',
        ),
        (
            'function DisassembleNewScene:responseLianHua(event)\n'
            '    LoadingWait:ends()\n'
            '    if event and event.Status == 0 then',
            'function DisassembleNewScene:responseLianHua(event)\n'
            '    LoadingWait:ends()\n'
            '    if not (event and event.Status == 0) then\n'
            '        if self.mIsAutoLianhua then\n'
            '            self.mSelectList = {}\n'
            '            self.mIsAutoLianhua = false\n'
            '        end\n'
            '        return\n'
            '    end\n'
            '    if event and event.Status == 0 then',
        ),
    ])


def patch_r7151_lua(src: Path) -> None:
    patch_luac_text(src / "Common" / "ConfigFunc.luac", [
        (
            "        if not params.slotId or params.slotId < 1 or params.slotId >= MAX_HERO_SLOT_COUNT  then",
            "        if not params.slotId or (not params.isMateSlot and (params.slotId < 1 or params.slotId >= MAX_HERO_SLOT_COUNT)) then",
        ),
    ])
    patch_luac_text(src / "Formation" / "PlayerFormationLayer.luac", [
        (
            '        self.mSlotAPLabel:setString(string.format("%d", APValue))',
            '        self.mSlotAPLabel:setString(string.format("%d", property.AP or math.floor(APValue)))',
        ),
        (
            '        self.mSlotDEFLabel:setString(string.format("%d", DEFValue))',
            '        self.mSlotDEFLabel:setString(string.format("%d", property.DEF or math.floor(DEFValue)))',
        ),
        (
            '        self.mSlotHPLabel:setString(string.format("%d", HPValue))',
            '        self.mSlotHPLabel:setString(string.format("%d", property.HP or math.floor(HPValue)))',
        ),
    ])
    patch_luac_text(src / "Formation" / "MyFormationLayer.luac", [
        ('ret.AP = ret.AP + property.APHero * (property.APHeroR / 10000)',
         'ret.AP = property.AP or math.floor(ret.AP + property.APHero * (property.APHeroR / 10000))'),
        ('ret.DEF = ret.DEF + property.DEFHero * (property.DEFHeroR / 10000)',
         'ret.DEF = property.DEF or math.floor(ret.DEF + property.DEFHero * (property.DEFHeroR / 10000))'),
        ('ret.HP = ret.HP + ret.AP * (property.APToHPHeroR / 10000)',
         'ret.HP = property.HP or math.floor(ret.HP + ret.AP * (property.APToHPHeroR / 10000))'),
        ('--                ret.FAP = tempSlot.FAP or 0', '                ret.FAP = property.FAP or tempSlot.FAP or 0'),
    ])
    patch_luac_text(src / "Hero" / "GetHeroAttribute.luac", [
        (
            '                totalInfor.FSP  = v.Property.FSP+ dValueInfor.FSP',
            '''                local property = v.Property
                if property.ActivePrIds then
                    totalInfor.AP = property.AP + math.floor((property.AP1 + dValueInfor.AP) * property.APR1 / 10000)
                        - math.floor(property.AP1 * property.APR1 / 10000)
                    totalInfor.HP = property.HP + math.floor((property.HP1 + dValueInfor.HP) * property.HPR1 / 10000)
                        - math.floor(property.HP1 * property.HPR1 / 10000)
                    totalInfor.DEF = property.DEF + math.floor((property.DEF1 + dValueInfor.DEF) * property.DEFR1 / 10000)
                        - math.floor(property.DEF1 * property.DEFR1 / 10000)
                end
                totalInfor.FSP  = v.Property.FSP+ dValueInfor.FSP''',
        ),
    ])
    patch_luac_text(src / "Equipment" / "EquipmentCommon.luac", [
        (
            '            for _, equipItem in ipairs({slotItem.Weapon, slotItem.Helmet, slotItem.Necklace, slotItem.Clothes}) do\n'
            '                if IdIsValid(equipItem.Id) then',
            '            for _, key in ipairs({"Weapon", "Helmet", "Necklace", "Clothes"}) do\n'
            '                local equipItem = slotItem[key]\n'
            '                if equipItem and IdIsValid(equipItem.Id) then',
        ),
        (
            '            for _, treasureItem in ipairs({slotItem.Book, slotItem.Horse}) do\n'
            '                if IdIsValid(treasureItem.Id) then',
            '            for _, key in ipairs({"Book", "Horse"}) do\n'
            '                local treasureItem = slotItem[key]\n'
            '                if treasureItem and IdIsValid(treasureItem.Id) then',
        ),
    ])
    patch_luac_text(src / "Equipment" / "EquipmentScene.luac", [
        (
            '    HttpRequest("Equip", ifLead and "EquipColorLeadUp" or "EquipStepUp", {entityId, materials[1].Id}, function(retVal)',
            '''    local view = self._subview
    local step = view and view.data and view.data.Step
    local payload = {entityId, materials[1].Id}
    if not ifLead then payload[3] = step end
    HttpRequest("Equip", ifLead and "EquipColorLeadUp" or "EquipStepUp", payload, function(retVal)''',
        ),
        (
            '''        local callfunc = function()
            self._jinjieLayer:refreshData()
            self._jinjieLayer.mEntityId = retVal.Value.EquipInfo.Id
            self._jinjieLayer:createEquipment(self._shenqiId,true)
        end

        self._slotlist = Equip.getSlotList()

        local tempObj = {}
        local tempData = self._slotlist[soltId].dataset
        for i ,v in pairs(tempData) do
            if v.Id == retVal.Value.EquipInfo.Id then
                tempObj = v
                break
            end
        end

        self._subview:handleRequest(tempObj,callfunc)''',
            '''        local info = retVal.Value.EquipInfo
        local callfunc
        if soltId and self._jinjieLayer then
            callfunc = function()
                self._jinjieLayer:refreshData()
                self._jinjieLayer.mEntityId = info.Id
                self._jinjieLayer:createEquipment(self._shenqiId, true)
            end
        end

        self._slotlist = Equip.getSlotList()
        if view and self._subview == view then
            view:handleRequest(Equip.newEquipment(clone(info)), callfunc)
        end''',
        ),
    ])
    patch_luac_text(src / "Equipment" / "NewArtifactLayer.luac", [
        (
            '''   local tempObj = {}
   local tempData = self.mSlotlist[soltInfor.slotId].dataset
   for i ,v in pairs(tempData) do
       if v.Id == soltInfor.Id then
           tempObj = v
           break
       end
   end''',
            '''   local tempObj
   if equipmentEnum[index] == ResourcetypeSub.eBook or equipmentEnum[index] == ResourcetypeSub.eHorse then
       tempObj = Equip.newTreasure(clone(NetworkResData:getTreasure(soltInfor.Id)))
   else
       tempObj = Equip.newEquipment(clone(NetworkResData:getEquipment(soltInfor.Id)))
   end
   if not tempObj then return end''',
        ),
    ])
    patch_luac_text(src / "Common" / "Ctrl.luac", [
        ('function Ctrl.newCountNode(params, player)\n',
         'function Ctrl.newCountNode(params, player)\n'
         '    local formatCount = params.exact and string.formatNumberThousands or NumberToBigUnit\n'),
        ('text= NumberToBigUnit(item.value),', 'text= formatCount(item.value),'),
        ('item.label:setString(NumberToBigUnit(to))', 'item.label:setString(formatCount(to))'),
        ('item.label:setString(NumberToBigUnit(tween))', 'item.label:setString(formatCount(tween))'),
        ('item.label:setString(NumberToBigUnit(value))', 'item.label:setString(formatCount(value))'),
    ])
    patch_luac_text(src / "Equipment" / "Module" / "EquipmentExtraLayer.luac", [
        (
            '    local tempString\n    local tempInfor = {',
            '    local tempString\n    local active = tempObj:getStepRelation()[tempObj.Step]\n    local tempInfor = {',
        ),
        ('tostring(tempObj.AP + tempObj.APUP * tempObj.Lv)',
         'tostring(tempObj.AP + tempObj.APUP * tempObj.Lv + active.AP)'),
        ('tostring(tempObj.AP + tempObj.APUP * tempObj.Lv + tempInfor.AP)',
         'tostring(tempObj.AP + tempObj.APUP * tempObj.Lv + active.AP + tempInfor.AP)'),
        ('tostring(tempObj.HP+ tempObj.HPUP * tempObj.Lv)',
         'tostring(tempObj.HP + tempObj.HPUP * tempObj.Lv + active.HP)'),
        ('tostring(tempObj.HP + tempObj.HPUP * tempObj.Lv + tempInfor.HP)',
         'tostring(tempObj.HP + tempObj.HPUP * tempObj.Lv + active.HP + tempInfor.HP)'),
        ('tostring(tempObj.DEF+ tempObj.DEFUP * tempObj.Lv)',
         'tostring(tempObj.DEF + tempObj.DEFUP * tempObj.Lv + active.DEF)'),
        ('tostring(tempObj.DEF + tempObj.DEFUP * tempObj.Lv + tempInfor.DEF)',
         'tostring(tempObj.DEF + tempObj.DEFUP * tempObj.Lv + active.DEF + tempInfor.DEF)'),
        ('    --"本次可激活进阶大师"\n',
         '    local tiers = equipObj:getStepRelation()\n'
         '    local needLv = tiers[equipObj.Step].needLV\n'
         '    local needsEnhancement = tiers[equipObj.Step + 1] and equipObj.Lv < needLv\n'),
        ('text = TR("本次可激活进阶大师"),',
         'text = needsEnhancement and string.format("Cần Cường Hóa Lv%d", needLv) or "Chỉ số của trang bị",'),
        ('            value= gold_cost,\n', '            value= gold_cost,\n            exact= true,\n'),
    ])
    patch_luac_text(src / "NewXZYY" / "XzyyMainScene.luac", [
        ('if self.mMaxThreeFloor < (self.mFloor + 10) then', 'if not self.mCanSweep then'),
        ('if self.mMaxThreeFloor < (self.mFloor + 10) or not isOpen then',
         'if not self.mCanSweep or not isOpen then'),
        ('        self.mMaxThreeFloor = event.Value.Info.MaxThreeFloor\n        --层信息',
         '        self.mCanSweep = event.Value.Info.CanSweep\n        --层信息'),
        ('        self.mMaxThreeFloor = event.Value.Info.MaxThreeFloor\n        --层信息',
         '        self.mCanSweep = event.Value.Info.CanSweep\n        --层信息'),
        ('        self.mMaxThreeFloor = event.Value.Info.MaxThreeFloor\n        --层信息',
         '        self.mCanSweep = event.Value.Info.CanSweep\n        --层信息'),
        ('boxGetGameResourceList = event.Value.BoxGetGameResourceList, callBack',
         'boxGetGameResourceList = event.Value.BoxGetGameResourceList, gainedStars = event.Value.SweepStarCount, callBack'),
    ])
    patch_luac_text(src / "NewXZYY" / "XzyyOneKeyLayer.luac", [
        ('    self.mFloor = pargams.currentFloor', '    self.mFloor = pargams.currentFloor\n'
         '    self.mGainedStars = pargams.gainedStars'),
        ('#self.mRewardList * 3),', 'self.mGainedStars or #self.mRewardList * 3),'),
    ])
    patch_luac_text(src / "NewXZYY" / "XzyyPrepareFightLayer.luac", [
        ('NodeId % 10, BddNodeModel.items[NodeId].name',
         '(BddNodeModel.items[NodeId].floorModelID - 11) * 3 + NodeId % 10, BddNodeModel.items[NodeId].name'),
    ])
    patch_luac_text(src / "Adventure" / "BattleSettleLayer.luac", [
        ('self.mXZYYData.Nandu, self.mFightResult.result, self.mFightResult.data, self.mFightResult.optional or {}',
         'self.mXZYYData.Nandu, self.mFightResult.result == true, self.mFightResult.data or "", self.mFightResult.optional or {}'),
        ('function BattleSettleLayer:responseXZYY(event)\n    LoadingWait:ends()\n    if event.Value and event.Value.IsSuccess == true then',
         '''function BattleSettleLayer:responseXZYY(event)
    LoadingWait:ends()
    if not event or event.Status ~= 0 or not event.Value then
        self:onClose()
        return
    end
    if event.Value.IsSuccess == true then'''),
    ])


def patch_mystery_shop_lua(src: Path) -> None:
    replacements = [
        (
            '                if not storeInfo then\n'
            '                    return\n'
            '                end\n'
            '                local tempTime = storeInfo.LastFreshDate or 0\n'
            '                if tempTime < currTime then  -- 需要重新请求服务器获取商店数据\n'
            '                    return true\n'
            '                end\n'
            '                -- 刷新倒计时时间\n'
            '                if self.mRefershTimeLabel then\n'
            '                    self.mRefershTimeLabel:setString(formatTimeEx(tempTime - currTime))\n'
            '                end',
            '                local deadline = storeInfo and tonumber(storeInfo.LastFreshDate)\n'
            '                if not deadline or not currTime then return end\n'
            '                local remaining = math.max(0, deadline - currTime)\n'
            '                if self.mRefershTimeLabel then\n'
            '                    self.mRefershTimeLabel:setString(formatTimeEx(remaining))\n'
            '                end\n'
            '                return remaining == 0',
        ),
    ]
    for rpc, method, field in (
        ("GetInfo", "requestNormalInfo", "mNormalInfoPending"),
        ("SeniorGetInfo", "requestSeniorGetInfo", "mSeniorInfoPending"),
    ):
        old = (
            f'function MysticalStoreScene:{method}()\n'
            '    LoadingWait:begin(self)\n'
            f'    HttpRequest("MysteryShop", "{rpc}", {{}}, function(response)\n'
        )
        new = (
            f'function MysticalStoreScene:{method}()\n'
            f'    if self.{field} then return end\n'
            f'    self.{field} = true\n'
            '    LoadingWait:begin(self)\n'
            f'    HttpRequest("MysteryShop", "{rpc}", {{}}, function(response)\n'
            f'        self.{field} = false\n'
        )
        replacements.append((old, new))
    replacements.extend([
        (
            '            if self.mStoreInfo.normalStore then\n'
            '                self.mStoreInfo.normalStore.FreeCount = response.Value.FreeCount\n'
            '                self.mStoreInfo.normalStore.GoldCount = response.Value.GoldCount\n'
            '                self.mStoreInfo.normalStore.RefreshMysteryShopMaxNum = response.Value.RefreshMysteryShopMaxNum\n'
            '                self.mStoreInfo.normalStore.MysteryShopGoodsList = response.Value.MysteryShopGoodsList\n'
            '            else\n'
            '                self.mStoreInfo.normalStore = response.Value\n'
            '            end',
            '            self.mStoreInfo.normalStore = response.Value',
        ),
        (
            '            if self.mStoreInfo.seniorStore then\n'
            '                self.mStoreInfo.seniorStore.MysteryShopGoodsList = response.Value and response.Value.MysteryShopGoodsList\n'
            '            else\n'
            '                self.mStoreInfo.seniorStore = response.Value\n'
            '            end',
            '            self.mStoreInfo.seniorStore = response.Value',
        ),
    ])
    patch_luac_text(src / "Store" / "MysticalStoreScene.luac", replacements)


def patch_reward_claim_lua(src: Path) -> None:
    patch_luac_text(src / "TimedActivity" / "TimedRecruitChoiceBoxLayer.luac", [
        (
            '    self.data = params.data\n',
            '    self.data = params.data\n'
            '    self.mBannerId = params.data.ActivityEnumId\n'
            '    self.mEventInstanceId = params.data.EventInstanceId\n',
        ),
        (
            '    LoadingWait:begin(self)\n'
            '    HttpRequest("TimedRecruitInfo", "DrawGoldHero", {heroID}, function(result)\n'
            '        LoadingWait:ends()',
            '    if self.mDrawingHero then return end\n'
            '    self.mDrawingHero = true\n'
            '    LoadingWait:begin(self)\n'
            '    HttpRequest("TimedRecruitInfo", "DrawGoldHero", {heroID, self.mBannerId, self.mEventInstanceId}, function(result)\n'
            '        self.mDrawingHero = false\n'
            '        LoadingWait:ends()',
        ),
    ])
    patch_luac_text(src / "OpenActivity" / "SuccessTargetLayer.luac", [
        (
            'function SuccessTargetLayer:createAwardList(awardInfo,lastListView)',
            '''function SuccessTargetLayer:canClaimTarget(target, sequence)
    return target.Claimable and target.Claimable[tostring(sequence)] == true
        and not target.DrawNums[sequence]
end

function SuccessTargetLayer:targetProgress(target, row)
    local reached = target.SequenceInfo[tostring(row.sequence)] or target.ReachedNum
    local model = SuccessTargetModel.items[row.targetID].modelID
    if model == 4918 then
        return reached, 4
    end
    if model == 4907 and row.completeCondition1 > 6 then
        return math.max(0, reached - 6), row.completeCondition1 - 6
    end
    if model == 4913 or model == 4907 then
        return self:canClaimTarget(target, row.sequence) and 1 or 0, 1
    end
    return reached, row.completeCondition1
end

function SuccessTargetLayer:createAwardList(awardInfo,lastListView)''',
        ),
        (
            '        --创建界面UI的函数\n        local function uiFunc( ... )',
            '        local function drawAble()\n'
            '            return self:canClaimTarget(targetInfo, v.sequence)\n'
            '        end\n\n'
            '        --创建界面UI的函数\n        local function uiFunc( ... )',
        ),
        (
            '''            --一些特殊的奖励需要用到SequenceInfo
            -- 索引为字符串
            if targetInfo.SequenceInfo[tostring(v.sequence)] then
                targetInfo.ReachedNum = targetInfo.SequenceInfo[tostring(v.sequence)]
            end


            --能否领取该奖励
            local function drawAble( ... )
                --  特殊情况
                if targetInfo.SequenceInfo[tostring(v.sequence)] then
                    --装备进阶活动需要特殊处理下
                    if SuccessTargetModel.items[v.targetID].modelID == 4918 then
                        return targetInfo.ReachedNum >= 4
                    else
                        return targetInfo.ReachedNum >= v.completeCondition1
                    end
                else
                    return targetInfo.Sequence >= v.sequence
                end
            end

            --进度的字符串
            --能领取的显示绿色不能的红色
            local c = not drawAble() and "{e71312}" or ColorList.green



            local progressStr = c .. targetInfo.ReachedNum .."/" .. v.completeCondition1

            --精英猛将活动需要特殊处理下
            if SuccessTargetModel.items[v.targetID].modelID == 4913 then
                local count = not drawAble() and 0 or 1
                progressStr = c .. count .."/" .. "1"
            end

            --装备进阶活动需要特殊处理下
            if SuccessTargetModel.items[v.targetID].modelID == 4918 then
                local count = not drawAble() and 0 or 1
                progressStr = c .. targetInfo.ReachedNum .."/" .. "4"
            end


            if SuccessTargetModel.items[v.targetID].modelID == 4907 then
                 --小伙伴
                if v.completeCondition1 > 6 then
                    local reachedNum = targetInfo.ReachedNum - 6
                    reachedNum = reachedNum < 0 and 0 or reachedNum
                    progressStr = c .. reachedNum .."/" .. (v.completeCondition1 - 6)
                else
                    local count = not drawAble() and 0 or 1
                    progressStr = c .. count .."/" .. "1"
                end
            end''',
            '''            local c = drawAble() and ColorList.green or "{e71312}"
            local reached, goal = self:targetProgress(targetInfo, v)
            local progressStr = c .. reached .. "/" .. goal''',
        ),
        (
            '''         --能否领取该奖励
        local function drawAble( ... )
            --  特殊情况
            if targetInfo.SequenceInfo[tostring(v.sequence)] then
                --装备进阶活动需要特殊处理下
                if SuccessTargetModel.items[v.targetID].modelID == 4918 then
                    return targetInfo.SequenceInfo[tostring(v.sequence)] >= 4
                else
                    return targetInfo.SequenceInfo[tostring(v.sequence)] >= v.completeCondition1
                end
            else
                return targetInfo.Sequence >= v.sequence
            end
        end''',
            '',
        ),
        (
            '                            targetInfo.DrawNums[v.sequence] = v.sequence',
            '                            targetInfo.DrawNums[v.sequence] = v.sequence\n'
            '                            targetInfo.Claimable[tostring(v.sequence)] = false',
        ),
        (
            '                            serverInfo.FinishTargetCount = serverInfo.FinishTargetCount + 1',
            '                            serverInfo.FinishTargetCount = response.Value.FinishTargetCount',
        ),
        (
            '''                                local reachNum = serverInfo.TargetList[m].ReachedNum
                                --一些特殊的奖励需要用到SequenceInfo
                                -- 索引为字符串
                                if serverInfo.TargetList[m].SequenceInfo[tostring(y.sequence)] then
                                    reachNum = serverInfo.TargetList[m].SequenceInfo[tostring(y.sequence)]
                                end
                                if SuccessTargetModel.items[m].modelID == 4918 then
                                    if reachNum >= 4 and not serverInfo.TargetList[m].DrawNums[y.sequence] then
                                        return true
                                    end
                                else
                                    if reachNum >= y.completeCondition1 and not serverInfo.TargetList[m].DrawNums[y.sequence] then
                                        return true
                                    end
                                end''',
            '''                                if self:canClaimTarget(serverInfo.TargetList[m], y.sequence) then
                                    return true
                                end''',
        ),
        (
            '''                                        local reachNum = serverInfo.TargetList[tID].ReachedNum
                                        --一些特殊的奖励需要用到SequenceInfo
                                        -- 索引为字符串
                                        if serverInfo.TargetList[tID].SequenceInfo[tostring(n.sequence)] then
                                            reachNum = serverInfo.TargetList[tID].SequenceInfo[tostring(n.sequence)]
                                        end

                                        --装备进阶特殊处理下
                                        if SuccessTargetModel.items[tID].modelID == 4918 then
                                            if reachNum >= 4 and not serverInfo.TargetList[tID].DrawNums[n.sequence] then
                                                return true
                                            end
                                        else
                                            if reachNum >= n.completeCondition1 and not serverInfo.TargetList[tID].DrawNums[n.sequence] then
                                                return true
                                            end
                                        end''',
            '''                                        if self:canClaimTarget(serverInfo.TargetList[tID], n.sequence) then
                                            return true
                                        end''',
        ),
        (
            '''                                for k,v in pairs(serverInfo.DrawDay) do
                                    if v.Day == k then
                                        table.remove(serverInfo.DrawDay,k)
                                        break
                                    end
                                end''',
            '''                                serverInfo.DrawDay = response.Value.DrawDay
                                serverInfo.DrawnDays = response.Value.DrawnDays''',
        ),
        (
            '            if k < serverInfo.Day then\n                --已经领取的添加个标示',
            '            if self:hasDrawnDay(k) then\n                --已经领取的添加个标示',
        ),
        (
            'function SuccessTargetLayer:canDrawReward( day )',
            '''function SuccessTargetLayer:hasDrawnDay(day)
    for _, claimedDay in ipairs(serverInfo.DrawnDays or {}) do
        if claimedDay == day then return true end
    end
    return false
end

function SuccessTargetLayer:canDrawReward( day )''',
        ),
        ('        if not curBt and k == serverInfo.Day then', '        if not curBt and k == math.min(serverInfo.Day, endDay) then'),
    ])


def build_and_sign_release(out_name: str) -> Path:
    if not RELEASE_KEYSTORE.exists():
        raise FileNotFoundError(
            f"Missing release keystore outside repository: {RELEASE_KEYSTORE}"
        )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    unsigned_apk = OUT_DIR / "standalone_unsigned.apk"
    aligned_apk = OUT_DIR / "standalone_aligned.apk"
    signed_apk = OUT_DIR / out_name
    for p in (unsigned_apk, aligned_apk, signed_apk):
        p.unlink(missing_ok=True)

    subprocess.run(["java", "-jar", str(APKTOOL_JAR), "b", str(STANDALONE_WORK), "-o", str(unsigned_apk)], check=True)
    subprocess.run([str(ZIPALIGN), "-f", "4", str(unsigned_apk), str(aligned_apk)], check=True)
    subprocess.run(
        [
            str(APKSIGNER),
            "sign",
            "--ks",
            str(RELEASE_KEYSTORE),
            "--ks-pass",
            f"pass:{RELEASE_KS_PASS}",
            "--key-pass",
            f"pass:{RELEASE_KS_PASS}",
            "--ks-key-alias",
            RELEASE_KS_ALIAS,
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
    parser = argparse.ArgumentParser(description="Build self-contained Android Standalone APK")
    parser.add_argument("--package-id", default="com.cmn.inuyasha.revival", help="Android Application ID")
    parser.add_argument("--version-code", type=int, default=770, help="Android versionCode")
    parser.add_argument("--version-name", default="5.0.4.98-r7.7-standalone", help="Android versionName")
    parser.add_argument("--app-label", default="InuYasha Offline", help="Launcher display name")
    parser.add_argument("--out", default="com.cmn.inuyasha.revival_r7_7_standalone.apk", help="Output APK filename")
    args = parser.parse_args()

    patch_standalone_workspace(
        package_id=args.package_id,
        version_code=args.version_code,
        version_name=args.version_name,
        app_label=args.app_label,
    )
    out = build_and_sign_release(args.out)
    print(f"Standalone APK ready: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
