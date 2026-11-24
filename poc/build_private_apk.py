#!/usr/bin/env python3
"""
Build the online-multiplayer Android Private Server APK for InuYasha: Seek Jade (R8.1).

Features:
  - Application ID: com.cmn.inuyasha.private (coexists side-by-side with com.cmn.inuyasha.revival).
  - Omits embedded Python runtime / LocalBackendService; connects over HTTP/HTTPS to a remote private_server.py.
  - Shares all R7.6..R7.40 VN Lua gameplay patches, merged OBB resources, TW-adapted configs, and Banner 83/84-86 assets.
  - Injects Private Server Login/Register/Change-Password UI backed by PrivateServerAuth.txt (not cleared by game.lua).
  - Signs with the release keystore outside the repository (~/.inuyasha_release/inuyasha_revival_release.jks).
"""

from __future__ import annotations

import argparse
import re
import shutil
import urllib.parse
from pathlib import Path

from build_standalone_apk import (
    ROOT_DIR,
    SRC_DECOMPILED,
    apply_shared_gameplay_patches,
    build_and_sign_work,
    disable_legacy_permissions_array,
    unpack_libs_apk,
    write_luac_text,
)
from patch_vn_apk import (
    VN_LOCAL_ONCREATE_SMALI,
    VN_LOCAL_ONDESTROY_SMALI,
    patch_luac_text,
    replace_cstr_padded,
)

PRIVATE_WORK = ROOT_DIR / "analysis" / "vn" / "apktool_private"

VN_PRIVATE_MQLOGIN_SMALI = """.method public MQLogin()V
    .locals 0

    .prologue
    return-void
.end method"""

PRIVATE_GAME_LOGIN_SCENE_LUA_TMPL = """--[[
    Login.GameLoginScene.lua — Private Server Online Login / Register (R8.1)
-- ]]

require("Common.LoadingWait")
require("Network.HttpClient")

local DEFAULT_SERVER_URL = "__DEFAULT_SERVER_URL__"
local AUTH_STORAGE_FILE = "PrivateServerAuth.txt"

local GameLoginScene = class("GameLoginScene", function()
    return ui.newScene()
end)

local function trimStr(s)
    return (tostring(s or ""):gsub("^%s+", ""):gsub("%s+$", ""))
end

local function normalizeServerUrl(raw)
    local s = trimStr(raw)
    if s == "" then
        return ""
    end
    if not string.match(s, "^https?://") then
        s = "http://" .. s
    end
    s = string.gsub(s, "/+$", "")
    return s
end

local function readAuthCache()
    local d = LocalData:readFileData(AUTH_STORAGE_FILE, {})
    if type(d) ~= "table" then
        return {}
    end
    return d
end

local function saveAuthCache(tbl)
    LocalData:saveDataToFile(AUTH_STORAGE_FILE, tbl or {})
end

function GameLoginScene:ctor()
    NetworkResData:clearPlayerCacheInfo()

    local bgLayer = require("Common.StartPageBgLayer").new()
    self:addChild(bgLayer)

    local cache = readAuthCache()
    local initUrl = (cache.server_url and cache.server_url ~= "") and cache.server_url or DEFAULT_SERVER_URL
    local initUser = cache.username or ""
    local initPass = cache.password or ""

    local panelBg = ccui.Scale9Sprite:create("c_36.png")
    panelBg:setContentSize(cc.size(760, 405))
    panelBg:setPosition(Adapter.AutoPos(568, 225))
    panelBg:setScale(Adapter.MinScale)
    panelBg:setOpacity(225)
    self:addChild(panelBg)

    local titleLbl = ui.newLabel({
        text = "INUYASHA PRIVATE SERVER (R8.1)",
        size = 24,
        color = ColorList.ccYellow or ColorList.ccWhite,
        needShadow = true,
        shadowColor = ColorList.ccBlack,
        align = ui.TEXT_ALIGN_CENTER,
    })
    titleLbl:setPosition(Adapter.AutoPos(568, 398))
    titleLbl:setScale(Adapter.MinScale)
    self:addChild(titleLbl)

    local lblSrv = ui.newLabel({
        text = "Server:",
        size = 23,
        color = ColorList.ccWhite,
        needShadow = true,
        shadowColor = ColorList.ccBlack,
    })
    lblSrv:setPosition(Adapter.AutoPos(290, 342))
    lblSrv:setScale(Adapter.MinScale)
    self:addChild(lblSrv)

    self.mServerEditBox = ui.newEditBox({
        image = "c_84.png",
        size = cc.size(470, 48),
        fontColor = ColorList.ccBlack,
    })
    self.mServerEditBox:setPosition(Adapter.AutoPos(610, 342))
    self.mServerEditBox:setScale(Adapter.MinScale)
    self.mServerEditBox:setPlaceHolder("http://IP:8080 hoặc https://...")
    self.mServerEditBox:setText(initUrl)
    self:addChild(self.mServerEditBox)

    local lblUser = ui.newLabel({
        text = "Tài khoản:",
        size = 23,
        color = ColorList.ccWhite,
        needShadow = true,
        shadowColor = ColorList.ccBlack,
    })
    lblUser:setPosition(Adapter.AutoPos(290, 276))
    lblUser:setScale(Adapter.MinScale)
    self:addChild(lblUser)

    self.mUserEditBox = ui.newEditBox({
        image = "c_84.png",
        size = cc.size(470, 48),
        fontColor = ColorList.ccBlack,
    })
    self.mUserEditBox:setPosition(Adapter.AutoPos(610, 276))
    self.mUserEditBox:setScale(Adapter.MinScale)
    self.mUserEditBox:setPlaceHolder("3–24 ký tự (chữ, số, _ . -)")
    self.mUserEditBox:setText(initUser)
    self:addChild(self.mUserEditBox)

    local lblPass = ui.newLabel({
        text = "Mật khẩu:",
        size = 23,
        color = ColorList.ccWhite,
        needShadow = true,
        shadowColor = ColorList.ccBlack,
    })
    lblPass:setPosition(Adapter.AutoPos(290, 210))
    lblPass:setScale(Adapter.MinScale)
    self:addChild(lblPass)

    self.mPassEditBox = ui.newEditBox({
        image = "c_84.png",
        size = cc.size(470, 48),
        fontColor = ColorList.ccBlack,
    })
    self.mPassEditBox:setPosition(Adapter.AutoPos(610, 210))
    self.mPassEditBox:setScale(Adapter.MinScale)
    self.mPassEditBox:setInputFlag(0)
    self.mPassEditBox:setPlaceHolder("4–64 ký tự")
    self.mPassEditBox:setText(initPass)
    self:addChild(self.mPassEditBox)

    self.mStatusLabel = ui.newLabel({
        text = "Nhập địa chỉ server, tài khoản và mật khẩu để đăng nhập",
        size = 19,
        color = ColorList.ccWhite,
        needShadow = true,
        shadowColor = ColorList.ccBlack,
        align = ui.TEXT_ALIGNMENT_CENTER or ui.TEXT_ALIGN_CENTER,
    })
    self.mStatusLabel:setPosition(Adapter.AutoPos(568, 152))
    self.mStatusLabel:setScale(Adapter.MinScale)
    self:addChild(self.mStatusLabel)

    local btnTest = ui.newButton({
        normalImage = "c_7.png",
        text = "Test Kết Nối",
        fontSize = 20,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = Adapter.AutoPos(325, 84),
        clickAction = function()
            self:testConnection()
        end,
    })
    btnTest:setScale(Adapter.MinScale * 0.92)
    self:addChild(btnTest)

    local btnRegister = ui.newButton({
        normalImage = "c_7.png",
        text = "Đăng Ký",
        fontSize = 22,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = Adapter.AutoPos(568, 84),
        clickAction = function()
            self:submitAuth("register")
        end,
    })
    btnRegister:setScale(Adapter.MinScale * 0.92)
    self:addChild(btnRegister)

    local btnLogin = ui.newButton({
        normalImage = "c_77.png",
        text = "Đăng Nhập",
        fontSize = 22,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = Adapter.AutoPos(811, 84),
        clickAction = function()
            self:submitAuth("login")
        end,
    })
    btnLogin:setScale(Adapter.MinScale * 0.92)
    self:addChild(btnLogin)
end

function GameLoginScene:onEnterTransitionFinish()
end

function GameLoginScene:_httpJson(method, url, payloadTable, cb)
    local xhr = cc.XMLHttpRequest:new()
    xhr:setUnzip(false)
    xhr.responseType = cc.XMLHTTPREQUEST_RESPONSE_STRING
    xhr:open(method, url)
    xhr:registerScriptHandler(function(event)
        if tolua.isnull(self) then
            return
        end
        LoadingWait:ends()
        local data = nil
        if event == "SUCCESS" and xhr.response and xhr.response ~= "" then
            local okDec, decoded = pcall(cjson.decode, xhr.response)
            if okDec and type(decoded) == "table" then
                data = decoded
            end
        end
        if cb then
            cb(xhr.status, data)
        end
    end)
    if method == "POST" and payloadTable then
        xhr:send(cjson.encode(payloadTable))
    else
        xhr:send()
    end
end

function GameLoginScene:testConnection()
    local baseUrl = normalizeServerUrl(self.mServerEditBox and self.mServerEditBox:getText() or "")
    if baseUrl == "" then
        ui.showFlashView({parent = self, text = "Vui lòng nhập địa chỉ server"})
        return
    end
    LoadingWait:begin(self)
    self:_httpJson("GET", baseUrl .. "/auth/info", nil, function(status, res)
        if status == 200 and res and res.ok then
            local msg = string.format(
                "Kết nối OK: %s (%d TK · %s)",
                tostring(res.server_name or "Private"),
                tonumber(res.registered_accounts) or 0,
                tostring(res.version or "R8.1")
            )
            if self.mStatusLabel then
                self.mStatusLabel:setString(msg)
            end
            ui.showFlashView({parent = self, text = msg})
        else
            local err = string.format("Không kết nối được server (HTTP %s)", tostring(status))
            if self.mStatusLabel then
                self.mStatusLabel:setString(err)
            end
            ui.showFlashView({parent = self, text = err})
        end
    end)
end

function GameLoginScene:submitAuth(action)
    local baseUrl = normalizeServerUrl(self.mServerEditBox and self.mServerEditBox:getText() or "")
    local username = trimStr(self.mUserEditBox and self.mUserEditBox:getText() or "")
    local password = self.mPassEditBox and self.mPassEditBox:getText() or ""
    if baseUrl == "" then
        ui.showFlashView({parent = self, text = "Vui lòng nhập địa chỉ server"})
        return
    end
    if username == "" or password == "" then
        ui.showFlashView({parent = self, text = "Vui lòng nhập tài khoản và mật khẩu"})
        return
    end

    LoadingWait:begin(self)
    local endpoint = (action == "register") and "/auth/register" or "/auth/login"
    self:_httpJson("POST", baseUrl .. endpoint, {username = username, password = password}, function(status, res)
        if status == 200 and res and res.ok and res.AuthToken then
            saveAuthCache({
                server_url = baseUrl,
                username = username,
                password = password,
                user_id = tostring(res.UserID or ""),
                auth_token = tostring(res.AuthToken or ""),
            })
            LocalData:saveManageCenter(baseUrl .. "/API/ServerList_Client.ashx")
            local loginPayload = cjson.encode({
                uid = tostring(res.UserID),
                auth_token = tostring(res.AuthToken),
                username = tostring(res.Username or username),
            })
            game.replaceRootScene(require("Login.StartGameScene").new(loginPayload, true), "CCtransitionCrossFade", 0)
        else
            local msg = (res and res.error) or string.format("Lỗi xác thực (HTTP %s)", tostring(status))
            if self.mStatusLabel then
                self.mStatusLabel:setString(tostring(msg))
            end
            ui.showFlashView({parent = self, text = tostring(msg)})
        end
    end)
end

return GameLoginScene
"""

PRIVATE_ACCOUNT_SWITCH_LAYER_LUA_TMPL = """--[[
    System.AccountSwitchLayer.lua — Private Server Account & Password Modal (R8.1)
-- ]]

local AUTH_STORAGE_FILE = "PrivateServerAuth.txt"
local DEFAULT_SERVER_URL = "__DEFAULT_SERVER_URL__"

local AccountSwitchLayer = class("AccountSwitchLayer", function()
    local self
    self = require("Common.ModalColorLayer").new({
        color4B = cc.c4b(0, 0, 0, 150),
        title = "Tài Khoản Private",
        bgImage = "c_43.png",
        closeBtnImage = "c_15.png",
        onCloseCallback = function()
            self:removeFromParent()
        end,
    })
    return self
end)

local function normalizeServerUrl(raw)
    local s = (tostring(raw or ""):gsub("^%s+", ""):gsub("%s+$", ""))
    if s == "" then
        return DEFAULT_SERVER_URL
    end
    if not string.match(s, "^https?://") then
        s = "http://" .. s
    end
    return string.gsub(s, "/+$", "")
end

function AccountSwitchLayer:ctor()
    local w, h = self.mBgSize.width, self.mBgSize.height
    local cache = LocalData:readFileData(AUTH_STORAGE_FILE, {})
    if type(cache) ~= "table" then
        cache = {}
    end
    local srvUrl = normalizeServerUrl(cache.server_url or DEFAULT_SERVER_URL)
    local username = tostring(cache.username or "")
    local srvInfo = NetworkResData:getServerInfo(true) or {}
    local srvName = tostring(srvInfo.ServerName or "S1 InuYasha Private")

    local infoLbl = ui.newLabel({
        text = string.format("Tài khoản: {6c0101}%s\\nServer: %s (%s)", username ~= "" and username or "(Chưa rõ)", srvName, srvUrl),
        size = 20,
        color = ColorList.ccBlack,
        dimensions = cc.size(w * 0.86, 0),
        align = ui.TEXT_ALIGNMENT_CENTER or ui.TEXT_ALIGN_CENTER,
    })
    infoLbl:setPosition(cc.p(w * 0.5, h * 0.74))
    self.mBgSprite:addChild(infoLbl)

    local lblOld = ui.newLabel({
        text = "MK cũ:",
        size = 20,
        color = ColorList.ccBlack,
    })
    lblOld:setPosition(cc.p(w * 0.22, h * 0.54))
    self.mBgSprite:addChild(lblOld)

    local oldPassBox = ui.newEditBox({
        image = "c_71.png",
        size = cc.size(300, 44),
        fontColor = ColorList.ccBlack,
    })
    oldPassBox:setPosition(cc.p(w * 0.60, h * 0.54))
    oldPassBox:setInputFlag(0)
    oldPassBox:setPlaceHolder("Nhập mật khẩu hiện tại")
    self.mBgSprite:addChild(oldPassBox)

    local lblNew = ui.newLabel({
        text = "MK mới:",
        size = 20,
        color = ColorList.ccBlack,
    })
    lblNew:setPosition(cc.p(w * 0.22, h * 0.40))
    self.mBgSprite:addChild(lblNew)

    local newPassBox = ui.newEditBox({
        image = "c_71.png",
        size = cc.size(300, 44),
        fontColor = ColorList.ccBlack,
    })
    newPassBox:setPosition(cc.p(w * 0.60, h * 0.40))
    newPassBox:setInputFlag(0)
    newPassBox:setPlaceHolder("Mật khẩu mới (4–64 ký tự)")
    self.mBgSprite:addChild(newPassBox)

    local btnChangePwd = ui.newButton({
        normalImage = "c_7.png",
        text = "Đổi Mật Khẩu",
        fontSize = 20,
        scale = 0.88,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = cc.p(w * 0.30, h * 0.19),
        clickAction = function()
            local oldP = oldPassBox:getText() or ""
            local newP = newPassBox:getText() or ""
            if username == "" or oldP == "" or newP == "" then
                ui.showFlashView({parent = self, text = "Vui lòng nhập đủ mật khẩu cũ và mới"})
                return
            end
            local xhr = cc.XMLHttpRequest:new()
            xhr:setUnzip(false)
            xhr.responseType = cc.XMLHTTPREQUEST_RESPONSE_STRING
            xhr:open("POST", srvUrl .. "/auth/change_password")
            xhr:registerScriptHandler(function(event)
                if tolua.isnull(self) then
                    return
                end
                local res = nil
                if event == "SUCCESS" and xhr.response and xhr.response ~= "" then
                    local okDec, dec = pcall(cjson.decode, xhr.response)
                    if okDec and type(dec) == "table" then
                        res = dec
                    end
                end
                if xhr.status == 200 and res and res.ok then
                    cache.password = newP
                    cache.auth_token = tostring(res.AuthToken or "")
                    LocalData:saveDataToFile(AUTH_STORAGE_FILE, cache)
                    ui.showFlashView({text = "Đã đổi mật khẩu! Hãy đăng nhập lại."})
                    require("Chat.ChatMng")
                    ChatMng:logout()
                    NetworkResData:clearPlayerCacheInfo()
                    game.replaceRootScene(require("Login.GameLoginScene").new(), "CCtransitionCrossFade", 0)
                else
                    local msg = (res and res.error) or string.format("Đổi mật khẩu thất bại (HTTP %s)", tostring(xhr.status))
                    ui.showFlashView({parent = self, text = tostring(msg)})
                end
            end)
            xhr:send(cjson.encode({username = username, old_password = oldP, new_password = newP}))
        end,
    })
    self.mBgSprite:addChild(btnChangePwd)

    local btnLogout = ui.newButton({
        normalImage = "c_77.png",
        text = "Đăng Xuất / Đổi Tài Khoản",
        fontSize = 18,
        scale = 0.88,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = cc.p(w * 0.70, h * 0.19),
        clickAction = function()
            require("Chat.ChatMng")
            ChatMng:logout()
            NetworkResData:clearPlayerCacheInfo()
            game.replaceRootScene(require("Login.GameLoginScene").new(), "CCtransitionCrossFade", 0)
        end,
    })
    self.mBgSprite:addChild(btnLogout)
end

return AccountSwitchLayer
"""


def _safe_cstr_host_port(server_url: str) -> str:
    parsed = urllib.parse.urlparse(server_url)
    host_port = parsed.netloc or "127.0.0.1:8080"
    # Native C string buffer limit matches original "loginsvr.ynqyc.moqikaka.com" (27 chars)
    if len(host_port) > len("loginsvr.ynqyc.moqikaka.com"):
        return "127.0.0.1:8080"
    return host_port


def patch_private_workspace(
    package_id: str,
    version_code: int,
    version_name: str,
    app_label: str,
    server_url: str,
) -> None:
    clean_url = server_url.strip().rstrip("/")
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"http://{clean_url}"

    if PRIVATE_WORK.exists():
        shutil.rmtree(PRIVATE_WORK)
    shutil.copytree(SRC_DECOMPILED, PRIVATE_WORK)

    # 1. AndroidManifest.xml (coexists cleanly with com.cmn.inuyasha.revival; NO LocalBackendService)
    manifest_path = PRIVATE_WORK / "AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = manifest.replace('package="com.cmn.inuyasha"', f'package="{package_id}"', 1)
    manifest = manifest.replace(
        'android:authorities="com.facebook.app.FacebookContentProvider0"',
        f'android:authorities="{package_id}.FacebookContentProvider0"',
        1,
    )
    for remote_svc in ("com.moqikaka.sdk.MQCrashService", "com.moqikaka.sdk.MQRebootService"):
        manifest = manifest.replace(
            f'<service android:enabled="true" android:exported="false" android:name="{remote_svc}" android:process=":remote"/>',
            f'<service android:enabled="false" android:exported="false" android:name="{remote_svc}"/>',
        )
    for bad_perm in (
        "android.permission.READ_PHONE_STATE",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.SYSTEM_ALERT_WINDOW",
        "android.permission.WRITE_SETTINGS",
        "android.permission.GET_TASKS",
    ):
        manifest = re.sub(rf'\s*<uses-permission(?:-sdk-m)? android:name="{re.escape(bad_perm)}"/>', "", manifest)

    manifest = manifest.replace(
        "<application ",
        '<application android:usesCleartextTraffic="true" android:extractNativeLibs="true" ',
        1,
    )
    manifest = manifest.replace(
        "</application>",
        '    <uses-library android:name="org.apache.http.legacy" android:required="false"/>\n    </application>',
        1,
    )
    manifest_path.write_text(manifest, encoding="utf-8")

    # App label & apktool.yml version metadata
    strings_xml = PRIVATE_WORK / "res" / "values" / "strings.xml"
    if strings_xml.exists():
        s_txt = strings_xml.read_text(encoding="utf-8")
        s_txt = re.sub(
            r'<string name="app_name">.*?</string>',
            f'<string name="app_name">{app_label}</string>',
            s_txt,
            count=1,
        )
        strings_xml.write_text(s_txt, encoding="utf-8")

    yml_path = PRIVATE_WORK / "apktool.yml"
    yml_txt = yml_path.read_text(encoding="utf-8")
    yml_txt = re.sub(r"versionCode:\s*\d+", f"versionCode: {version_code}", yml_txt, count=1)
    yml_txt = re.sub(r"versionName:\s*[^\n]+", f"versionName: {version_name}", yml_txt, count=1)
    yml_path.write_text(yml_txt, encoding="utf-8")

    # 2. Unpack libs.apk & disable obsolete runtime permission prompt
    unpack_libs_apk(PRIVATE_WORK)
    disable_legacy_permissions_array(PRIVATE_WORK)

    # 3. Native C string fallback + Smali SDK stubs (MQLogin is pure no-op)
    cstr_host_port = _safe_cstr_host_port(clean_url)
    so_path = PRIVATE_WORK / "lib" / "armeabi" / "libcocos2dlua.so"
    blob = bytearray(so_path.read_bytes())
    replace_cstr_padded(blob, b"Debug=0", b"Debug=1")
    replace_cstr_padded(
        blob,
        b"ManageCenter=http://loginsvr.ynqyc.moqikaka.com/API/ServerList_Client.ashx",
        f"ManageCenter=http://{cstr_host_port}/API/ServerList_Client.ashx".encode("ascii"),
    )
    replace_cstr_padded(
        blob,
        b"ReleaseDomain=http://loginsvr.ynqyc.moqikaka.com/",
        f"ReleaseDomain=http://{cstr_host_port}/".encode("ascii"),
    )
    so_path.write_bytes(bytes(blob))

    entity_path = PRIVATE_WORK / "smali" / "com" / "moqikaka" / "sdk" / "Entity.smali"
    entity_src = entity_path.read_text(encoding="utf-8")
    for pat, repl, label in [
        (r"\.method public MQLogin\(\)V.*?\.end method", VN_PRIVATE_MQLOGIN_SMALI, "MQLogin"),
        (r"\.method public onCreate\(Landroid/os/Bundle;\)V.*?\.end method", VN_LOCAL_ONCREATE_SMALI, "onCreate"),
        (r"\.method public onDestroy\(\)V.*?\.end method", VN_LOCAL_ONDESTROY_SMALI, "onDestroy"),
    ]:
        entity_src, n = re.subn(pat, repl, entity_src, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"Failed to patch {label} in Entity.smali")
    entity_path.write_text(entity_src, encoding="utf-8")

    utils_path = PRIVATE_WORK / "smali" / "com" / "moqikaka" / "sdk" / "MQUtils.smali"
    utils_path.write_text(
        utils_path.read_text(encoding="utf-8").replace("http://crashnew.moqikaka.com", clean_url),
        encoding="utf-8",
    )

    # 4. Shared R7.6..R7.40 VN Lua gameplay patches, OBB assets, banner assets
    apply_shared_gameplay_patches(PRIVATE_WORK)

    # 5. Private-server-specific Lua auth UI & server URL resolution
    write_luac_text(
        PRIVATE_WORK / "assets" / "src" / "Login" / "GameLoginScene.luac",
        PRIVATE_GAME_LOGIN_SCENE_LUA_TMPL.replace("__DEFAULT_SERVER_URL__", clean_url),
    )

    patch_luac_text(
        PRIVATE_WORK / "assets" / "src" / "Login" / "StartGameScene.luac",
        [
            (
                '    btnEnterGame:setScale(Adapter.MinScale)\n'
                '    self:addChild(btnEnterGame) ',
                '    btnEnterGame:setScale(Adapter.MinScale)\n'
                '    self:addChild(btnEnterGame)\n'
                '    local btnSwitchAcct = ui.newButton({\n'
                '        normalImage = "c_7.png",\n'
                '        position = Adapter.AutoPos(960, 100),\n'
                '        text = "Đổi Tài Khoản",\n'
                '        fontSize = 20,\n'
                '        textColor = ColorList.ccWhite,\n'
                '        outlineColor = ColorList.ccOutline,\n'
                '        clickAction = function()\n'
                '            NetworkResData:clearPlayerCacheInfo()\n'
                '            game.replaceRootScene(require("Login.GameLoginScene").new(), "CCtransitionCrossFade", 0)\n'
                '        end\n'
                '    })\n'
                '    btnSwitchAcct:setScale(Adapter.MinScale * 0.9)\n'
                '    self:addChild(btnSwitchAcct)',
            ),
            (
                'function StartGameScene:getManageCenterAddress()\n'
                '    local ret = LocalData:getManageCenter()\n'
                '    if not ret then\n'
                '        ret = IPlatform:getInstance():getConfigItem("ManageCenter")\n'
                '    end\n'
                '    print("StartGameScene ManageCenter:", ret)\n'
                '    return ret\n'
                'end',
                'function StartGameScene:getManageCenterAddress()\n'
                '    local authCfg = LocalData:readFileData("PrivateServerAuth.txt", {})\n'
                '    if type(authCfg) == "table" and authCfg.server_url and authCfg.server_url ~= "" then\n'
                '        local clean = string.gsub(tostring(authCfg.server_url), "/+$", "")\n'
                '        return clean .. "/API/ServerList_Client.ashx"\n'
                '    end\n'
                '    local ret = LocalData:getManageCenter()\n'
                '    if not ret or ret == "" then\n'
                f'        ret = "{clean_url}/API/ServerList_Client.ashx"\n'
                '    end\n'
                '    print("StartGameScene ManageCenter:", ret)\n'
                '    return ret\n'
                'end',
            ),
            (
                '    local userID, loginInfoStr = ""\n'
                '    local userInfo = NetworkResData:getUserLoginInfo()\n'
                '    if userInfo then\n'
                '        userID = NetworkResData:getUserLoginInfo().UserID\n'
                '    end\n'
                '    local loginInfo = self.mLoginInfo and type(self.mLoginInfo) == "table" and json.encode(self.mLoginInfo) or self.mLoginInfo\n'
                '    loginInfoStr = self.mIsThridChannel and loginInfo or json.encode({sessionId = self.mLoginInfo})',
                '    local userID, loginInfoStr = "", ""\n'
                '    local userInfo = NetworkResData:getUserLoginInfo()\n'
                '    if userInfo then\n'
                '        userID = userInfo.UserID or ""\n'
                '    end\n'
                '    local loginInfo = self.mLoginInfo and type(self.mLoginInfo) == "table" and json.encode(self.mLoginInfo) or self.mLoginInfo\n'
                '    loginInfoStr = self.mIsThridChannel and loginInfo or json.encode({sessionId = self.mLoginInfo})\n'
                '    if (not userID or userID == "") and type(loginInfo) == "string" and string.sub(loginInfo, 1, 1) == "{" then\n'
                '        local okDec, parsed = pcall(cjson.decode, loginInfo)\n'
                '        if okDec and type(parsed) == "table" and parsed.uid then\n'
                '            userID = tostring(parsed.uid)\n'
                '            loginInfoStr = tostring(parsed.auth_token or loginInfoStr or "")\n'
                '        end\n'
                '    end',
            ),
        ],
    )

    patch_luac_text(
        PRIVATE_WORK / "assets" / "src" / "System" / "SystemLayer.luac",
        [('    canLogout = canLogout:len() == 0 and "true" or canLogout', '    canLogout = "true"')],
    )
    write_luac_text(
        PRIVATE_WORK / "assets" / "src" / "System" / "AccountSwitchLayer.luac",
        PRIVATE_ACCOUNT_SWITCH_LAYER_LUA_TMPL.replace("__DEFAULT_SERVER_URL__", clean_url),
    )

    # Clarify Private wording & surface server recharge limits in RechargeScene / MonthCardLayer
    patch_luac_text(
        PRIVATE_WORK / "assets" / "src" / "Store" / "RechargeScene.luac",
        [
            ("Thẻ Tháng (Offline)?", "Thẻ Tháng (Private)?"),
            ("Kim Cương (Offline)?", "Kim Cương (Private)?"),
            (
                '                        self:requestGetChargeList(true)\n'
                '                    end\n'
                '                end)',
                '                        self:requestGetChargeList(true)\n'
                '                    else\n'
                '                        ui.showFlashView({parent = self, text = "Nạp bị giới hạn hoặc tắt trên server"})\n'
                '                    end\n'
                '                end)',
            ),
            (
                '                                self:requestGetChargeList(true)\n'
                '                            end\n'
                '                        end)',
                '                                self:requestGetChargeList(true)\n'
                '                            else\n'
                '                                ui.showFlashView({parent = self, text = "Nạp bị giới hạn hoặc tắt trên server"})\n'
                '                            end\n'
                '                        end)',
            ),
        ],
    )
    patch_luac_text(
        PRIVATE_WORK / "assets" / "src" / "ExtraActivity" / "MonthCardLayer.luac",
        [
            ("(Offline)?", "(Private)?"),
            (
                '                    if actOk then\n'
                '                        self:onPurchaseFinish("ok", id)\n'
                '                        if self.params.parent and self.params.parent.mBkgLayer and self.params.parent.mBkgLayer.refreshPlayerAttrs then\n'
                '                            self.params.parent.mBkgLayer:refreshPlayerAttrs()\n'
                '                        end\n'
                '                    end',
                '                    if actOk then\n'
                '                        self:onPurchaseFinish("ok", id)\n'
                '                        if self.params.parent and self.params.parent.mBkgLayer and self.params.parent.mBkgLayer.refreshPlayerAttrs then\n'
                '                            self.params.parent.mBkgLayer:refreshPlayerAttrs()\n'
                '                        end\n'
                '                    else\n'
                '                        ui.showFlashView({text = "Kích hoạt Thẻ Tháng bị tắt trên server"})\n'
                '                    end',
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Online Private Server Android APK (R8.1)")
    parser.add_argument("--package-id", default="com.cmn.inuyasha.private", help="Android Application ID")
    parser.add_argument("--version-code", type=int, default=860, help="Android versionCode")
    parser.add_argument("--version-name", default="5.0.4.98-r8.1-private", help="Android versionName")
    parser.add_argument("--app-label", default="InuYasha Private", help="Launcher display name")
    parser.add_argument("--server-url", default="http://192.168.100.173:8080", help="Default private server URL")
    parser.add_argument("--out", default="com.cmn.inuyasha.private_r8_1_860.apk", help="Output APK filename")
    args = parser.parse_args()

    patch_private_workspace(
        package_id=args.package_id,
        version_code=args.version_code,
        version_name=args.version_name,
        app_label=args.app_label,
        server_url=args.server_url,
    )
    out = build_and_sign_work(PRIVATE_WORK, args.out)
    print(f"Private APK ready: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
