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
    XXTEA_KEY,
    XXTEA_SIGN,
    ZIPALIGN,
    patch_luac_text,
    replace_cstr_padded,
    xxtea_decrypt,
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
        curLbl:setPosition(cc.p(w * 0.5, h * 0.82))
        self.mContentNode:addChild(curLbl)

        local accounts = res.Accounts or {}
        local positions = (#accounts <= 4) and {
            cc.p(w * 0.28, h * 0.66),
            cc.p(w * 0.72, h * 0.66),
            cc.p(w * 0.28, h * 0.50),
            cc.p(w * 0.72, h * 0.50),
        } or {
            cc.p(w * 0.28, h * 0.69),
            cc.p(w * 0.72, h * 0.69),
            cc.p(w * 0.28, h * 0.56),
            cc.p(w * 0.72, h * 0.56),
            cc.p(w * 0.28, h * 0.43),
            cc.p(w * 0.72, h * 0.43),
        }
        local slotScale = (#accounts <= 4) and 0.92 or 0.80
        for idx = 1, math.min(#accounts, 6) do
            local acc = accounts[idx]
            local isCur = acc.active
            local btnText = acc.display or ("TK " .. tostring(idx))
            local accBtn = ui.newButton({
                normalImage = isCur and "c_77.png" or "c_7.png",
                text = btnText,
                fontSize = 18,
                scale = slotScale,
                color = ColorList.ccWhite,
                outlineColor = ColorList.ccOutline,
                outlineSize = 2,
                position = positions[idx],
                clickAction = function()
                    if isCur then
                        ui.showFlashView({parent = self, text = "Bạn đang dùng tài khoản này rồi!"})
                        return
                    end
                    local box = require("Common.MessageBoxLayer").new({
                        bgImage = "c_43.png",
                        closeBtnImage = "c_15.png",
                        title = TR("Đổi Tài Khoản"),
                        content = string.format("Xác nhận chuyển sang tài khoản %s?", tostring(btnText)),
                        leftBtnTitle = TR("确定"),
                        rightBtnTitle = TR("取消"),
                        leftBtnCallback = function(dlg)
                            dlg:removeFromParent()
                            requestLocalAccountApi("POST", {action = "switch", account_id = acc.account_id}, function(swRes)
                                if swRes and swRes.ok then
                                    local targetUid = (swRes.SwitchedAccount and swRes.SwitchedAccount.user_id) or acc.user_id
                                    self:enterAccount(targetUid)
                                else
                                    ui.showFlashView({parent = self, text = "Chuyển tài khoản thất bại"})
                                end
                            end)
                        end,
                        rightBtnCallback = function(dlg)
                            dlg:removeFromParent()
                        end,
                    })
                    self:addChild(box, 200)
                end,
            })
            self.mContentNode:addChild(accBtn)
        end

        local btnCloudSync = ui.newButton({
            normalImage = "c_77.png",
            text = "Đồng Bộ Cloud (BXH / Bạn Bè / PvP)",
            fontSize = 18,
            scale = 0.88,
            color = ColorList.ccWhite,
            outlineColor = ColorList.ccOutline,
            outlineSize = 2,
            position = cc.p(w * 0.5, h * 0.31),
            clickAction = function()
                self:addChild(require("System.HybridSyncLayer").new(), 150)
            end,
        })
        self.mContentNode:addChild(btnCloudSync)

        local btnNewAcc = ui.newButton({
            normalImage = "c_7.png",
            text = "+ Tạo TK",
            fontSize = 18,
            scale = 0.78,
            color = ColorList.ccWhite,
            outlineColor = ColorList.ccOutline,
            outlineSize = 2,
            position = cc.p(w * 0.16, h * 0.17),
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

        local btnDeleteAcc = ui.newButton({
            normalImage = "c_7.png",
            text = "Xóa TK",
            fontSize = 18,
            scale = 0.78,
            color = ColorList.ccWhite,
            outlineColor = ColorList.ccOutline,
            outlineSize = 2,
            position = cc.p(w * 0.39, h * 0.17),
            clickAction = function()
                local box = require("Common.MessageBoxLayer").new({
                    bgImage = "c_43.png",
                    closeBtnImage = "c_15.png",
                    title = TR("Xóa Tài Khoản"),
                    content = string.format("Xác nhận XÓA VĨNH VIỄN tài khoản đang chọn (%s)? (Hệ thống tự tạo bản sao lưu dự phòng trước khi xóa)", tostring(res.ActiveDisplay or res.ActiveAccountId)),
                    leftBtnTitle = TR("确定"),
                    rightBtnTitle = TR("取消"),
                    leftBtnCallback = function(dlg)
                        dlg:removeFromParent()
                        requestLocalAccountApi("POST", {action = "delete", account_id = res.ActiveAccountId}, function(dlRes)
                            if dlRes and dlRes.ok then
                                ui.showFlashView({parent = display.getRunningScene(), text = "Đã xóa tài khoản!"})
                                self:enterAccount(dlRes.ActiveUserId or "100001")
                            else
                                ui.showFlashView({parent = self, text = tostring((dlRes and dlRes.error) or "Không thể xóa tài khoản")})
                            end
                        end)
                    end,
                    rightBtnCallback = function(dlg)
                        dlg:removeFromParent()
                    end,
                })
                self:addChild(box, 200)
            end,
        })
        self.mContentNode:addChild(btnDeleteAcc)

        local btnExport = ui.newButton({
            normalImage = "c_7.png",
            text = "Sao Lưu",
            fontSize = 18,
            scale = 0.78,
            color = ColorList.ccWhite,
            outlineColor = ColorList.ccOutline,
            outlineSize = 2,
            position = cc.p(w * 0.62, h * 0.17),
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
                        self:addChild(box, 200)
                    else
                        ui.showFlashView({parent = self, text = "Sao lưu thất bại"})
                    end
                end)
            end,
        })
        self.mContentNode:addChild(btnExport)

        local btnImport = ui.newButton({
            normalImage = "c_7.png",
            text = "Khôi Phục",
            fontSize = 18,
            scale = 0.78,
            color = ColorList.ccWhite,
            outlineColor = ColorList.ccOutline,
            outlineSize = 2,
            position = cc.p(w * 0.84, h * 0.17),
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
                                ui.showFlashView({parent = display.getRunningScene(), text = "Đã khôi phục dữ liệu thành công!"})
                                self:enterAccount(imRes.ActiveUserId or "100001")
                            else
                                ui.showFlashView({parent = self, text = "Không tìm thấy bản sao lưu hợp lệ"})
                            end
                        end)
                    end,
                    rightBtnCallback = function(dlg)
                        dlg:removeFromParent()
                    end,
                })
                self:addChild(box, 200)
            end,
        })
        self.mContentNode:addChild(btnImport)
    end)
end

return AccountSwitchLayer
"""

HYBRID_SYNC_LAYER_LUA = """--[[
    System.HybridSyncLayer.lua — Local-First Cloud Sync UI (R8.2)
    Connects to local embedded backend (127.0.0.1:18082/hybrid/*),
    which syncs securely with Cloudflare Workers + D1 Sync Hub.
-- ]]

local HybridSyncLayer = class("HybridSyncLayer", function()
    local self
    self = require("Common.ModalColorLayer").new({
        color4B = cc.c4b(0, 0, 0, 160),
        title = TR("Đồng Bộ Cloud (Hybrid)"),
        bgImage = "c_43.png",
        closeBtnImage = "c_15.png",
        onCloseCallback = function()
            self:removeFromParent()
        end
    })
    return self
end)

local function requestHybridApi(method, path, payloadTable, cb)
    local xhr = cc.XMLHttpRequest:new()
    xhr:setUnzip(false)
    xhr.responseType = cc.XMLHTTPREQUEST_RESPONSE_STRING
    xhr:open(method, "http://127.0.0.1:18082" .. path)
    xhr:registerScriptHandler(function(event)
        local data = nil
        if event == "SUCCESS" and xhr.response and xhr.response ~= "" then
            local okDec, dec = pcall(cjson.decode, xhr.response)
            if okDec and type(dec) == "table" then
                data = dec
            end
        end
        if cb then
            cb(data, xhr.status)
        end
    end)
    if method == "POST" then
        xhr:send(cjson.encode(payloadTable or {}))
    else
        xhr:send()
    end
end

local function reloadGameScene()
    NetworkResData:clearPlayerCacheInfo()
    local loginJson = cjson.encode({
        uid = "100001",
        platformId = "1001",
        token = "local-revival",
    })
    game.replaceRootScene(require("Login.StartGameScene").new(loginJson, true), "CCtransitionCrossFade", 0)
end

local function formatAgo(ts)
    ts = tonumber(ts) or 0
    if ts <= 0 then
        return "Chưa đồng bộ"
    end
    local diff = os.time() - ts
    if diff < 0 then
        diff = 0
    end
    if diff < 60 then
        return string.format("%d giây trước", diff)
    elseif diff < 3600 then
        return string.format("%d phút trước", math.floor(diff / 60))
    elseif diff < 86400 then
        return string.format("%d giờ trước", math.floor(diff / 3600))
    else
        return string.format("%d ngày trước", math.floor(diff / 86400))
    end
end

function HybridSyncLayer:ctor()
    self.mContentNode = cc.Node:create()
    self.mBgSprite:addChild(self.mContentNode)
    self:refreshView()
end

function HybridSyncLayer:showConflictDialog(serverSum, localSum)
    local sLv = tonumber((serverSum and serverSum.lv) or 1) or 1
    local sFap = tonumber((serverSum and serverSum.fap) or 0) or 0
    local lLv = tonumber((localSum and localSum.lv) or 1) or 1
    local lFap = tonumber((localSum and localSum.fap) or 0) or 0
    local msg = string.format(
        "Phát hiện xung đột 2 thiết bị!\\n- Máy này: Lv.%d (Lực chiến %d)\\n- Cloud: Lv.%d (Lực chiến %d)\\n\\nBấm 'Tải Cloud' để lấy bản Cloud (tự backup bản máy), hoặc 'Đẩy Máy Lên' để ghi đè Cloud.",
        lLv, lFap, sLv, sFap
    )
    local box = require("Common.MessageBoxLayer").new({
        bgImage = "c_43.png",
        closeBtnImage = "c_15.png",
        title = TR("Xung Đột Dữ Liệu"),
        content = msg,
        leftBtnTitle = TR("Tải Cloud"),
        rightBtnTitle = TR("Đẩy Máy Lên"),
        leftBtnCallback = function(dlg)
            dlg:removeFromParent()
            requestHybridApi("POST", "/hybrid/pull_save", {}, function(pr)
                if pr and pr.ok then
                    ui.showFlashView({parent = display.getRunningScene(), text = "Đã tải bản Cloud về máy! Đang tải lại game..."})
                    reloadGameScene()
                else
                    ui.showFlashView({parent = self, text = tostring((pr and pr.error) or "Tải bản Cloud thất bại")})
                end
            end)
        end,
        rightBtnCallback = function(dlg)
            dlg:removeFromParent()
            requestHybridApi("POST", "/hybrid/sync", {force_push = true, ignore_cooldown = true}, function(sr)
                if sr and sr.ok then
                    ui.showFlashView({parent = self, text = string.format("Đã đẩy bản máy lên Cloud (Rev #%d)!", tonumber(sr.sync_rev) or 0)})
                    if not tolua.isnull(self) then
                        self:refreshView()
                    end
                else
                    ui.showFlashView({parent = self, text = tostring((sr and sr.error) or "Đẩy bản máy lên thất bại")})
                end
            end)
        end,
    })
    self:addChild(box, 200)
end

function HybridSyncLayer:refreshView()
    self.mContentNode:removeAllChildren()
    local w, h = self.mBgSize.width, self.mBgSize.height

    local loadingLbl = ui.newLabel({
        text = "Đang kiểm tra trạng thái Đồng Bộ Cloud...",
        size = 22,
        color = ColorList.ccBlack,
        align = cc.TEXT_ALIGNMENT_CENTER,
    })
    loadingLbl:setPosition(cc.p(w * 0.5, h * 0.52))
    self.mContentNode:addChild(loadingLbl)

    requestHybridApi("GET", "/hybrid/status", nil, function(st)
        if tolua.isnull(self) or tolua.isnull(self.mContentNode) then
            return
        end
        self.mContentNode:removeAllChildren()
        if not st or not st.ok then
            local errLbl = ui.newLabel({
                text = "Không kết nối được dịch vụ nền cục bộ",
                size = 21,
                color = ColorList.ccBlack,
            })
            errLbl:setPosition(cc.p(w * 0.5, h * 0.52))
            self.mContentNode:addChild(errLbl)
            return
        end

        if st.enabled then
            self:renderConnectedView(st)
        else
            self:renderAuthView(st)
        end
    end)
end

function HybridSyncLayer:renderAuthView(st)
    local w, h = self.mBgSize.width, self.mBgSize.height

    local noteLbl = ui.newLabel({
        text = "Chơi offline bình thường khi mất mạng · Bang Hội lưu riêng trên máy",
        size = 17,
        color = ColorList.ccBlack,
        align = cc.TEXT_ALIGNMENT_CENTER,
    })
    noteLbl:setPosition(cc.p(w * 0.5, h * 0.82))
    self.mContentNode:addChild(noteLbl)

    local function addField(labelText, yRatio, initText, placeholder, isPwd)
        local lbl = ui.newLabel({
            text = labelText,
            size = 19,
            color = ColorList.ccBlack,
        })
        lbl:setPosition(cc.p(w * 0.19, h * yRatio))
        self.mContentNode:addChild(lbl)

        local box = ui.newEditBox({
            image = "c_71.png",
            size = cc.size(340, 40),
            fontColor = ColorList.ccBlack,
        })
        box:setPosition(cc.p(w * 0.59, h * yRatio))
        if isPwd then
            box:setInputFlag(0)
        end
        box:setPlaceHolder(placeholder)
        box:setText(tostring(initText or ""))
        self.mContentNode:addChild(box)
        return box
    end

    local urlBox = addField("Sync URL:", 0.70, st.server_url or "", "https://...workers.dev", false)
    local userBox = addField("Tài khoản:", 0.57, st.username or "", "3-24 ký tự (chữ, số, _ . -)", false)
    local passBox = addField("Mật khẩu:", 0.44, "", "4-64 ký tự", true)
    local inviteBox = addField("Mã mời:", 0.31, "", "Chỉ cần nhập khi Đăng Ký", false)

    local btnTest = ui.newButton({
        normalImage = "c_7.png",
        text = "Test Mạng",
        fontSize = 18,
        scale = 0.82,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = cc.p(w * 0.21, h * 0.16),
        clickAction = function()
            local u = urlBox:getText() or ""
            ui.showFlashView({parent = self, text = "Đang kiểm tra kết nối Cloudflare..."})
            requestHybridApi("POST", "/hybrid/test", {server_url = u}, function(tr)
                if tolua.isnull(self) then
                    return
                end
                if tr and tr.ok then
                    local cnt = tonumber((tr.info and tr.info.account_count) or 0) or 0
                    ui.showFlashView({parent = self, text = string.format("Kết nối OK (%sms · %d người chơi)", tostring(tr.latency_ms or 0), cnt)})
                else
                    ui.showFlashView({parent = self, text = tostring((tr and tr.error) or "Không kết nối được Sync Hub")})
                end
            end)
        end,
    })
    self.mContentNode:addChild(btnTest)

    local btnReg = ui.newButton({
        normalImage = "c_7.png",
        text = "Đăng Ký",
        fontSize = 19,
        scale = 0.85,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = cc.p(w * 0.50, h * 0.16),
        clickAction = function()
            local u = urlBox:getText() or ""
            local uname = userBox:getText() or ""
            local pwd = passBox:getText() or ""
            local inv = inviteBox:getText() or ""
            if uname == "" or pwd == "" then
                ui.showFlashView({parent = self, text = "Vui lòng nhập Tài khoản, Mật khẩu và Mã mời"})
                return
            end
            ui.showFlashView({parent = self, text = "Đang đăng ký & đồng bộ..."})
            requestHybridApi("POST", "/hybrid/register", {
                server_url = u,
                username = uname,
                password = pwd,
                invite_code = inv,
            }, function(rr)
                if tolua.isnull(self) then
                    return
                end
                if rr and rr.ok then
                    ui.showFlashView({parent = self, text = "Đăng ký & đồng bộ thành công!"})
                    self:refreshView()
                else
                    ui.showFlashView({parent = self, text = tostring((rr and rr.error) or "Đăng ký thất bại")})
                end
            end)
        end,
    })
    self.mContentNode:addChild(btnReg)

    local btnLogin = ui.newButton({
        normalImage = "c_77.png",
        text = "Đăng Nhập",
        fontSize = 19,
        scale = 0.85,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = cc.p(w * 0.79, h * 0.16),
        clickAction = function()
            local u = urlBox:getText() or ""
            local uname = userBox:getText() or ""
            local pwd = passBox:getText() or ""
            if uname == "" or pwd == "" then
                ui.showFlashView({parent = self, text = "Vui lòng nhập Tài khoản và Mật khẩu"})
                return
            end
            ui.showFlashView({parent = self, text = "Đang đăng nhập Cloud..."})
            requestHybridApi("POST", "/hybrid/login", {
                server_url = u,
                username = uname,
                password = pwd,
            }, function(lr)
                if tolua.isnull(self) then
                    return
                end
                if lr and lr.ok then
                    if lr.auto_pulled then
                        ui.showFlashView({parent = display.getRunningScene(), text = "Đã khôi phục dữ liệu Cloud về máy mới!"})
                        reloadGameScene()
                    elseif lr.needs_choice then
                        self:showConflictDialog(lr.cloud_summary, st.local_summary)
                        self:refreshView()
                    else
                        ui.showFlashView({parent = self, text = "Đăng nhập thành công! Đang đồng bộ..."})
                        requestHybridApi("POST", "/hybrid/sync", {ignore_cooldown = true}, function()
                            if not tolua.isnull(self) then
                                self:refreshView()
                            end
                        end)
                    end
                else
                    ui.showFlashView({parent = self, text = tostring((lr and lr.error) or "Đăng nhập thất bại")})
                end
            end)
        end,
    })
    self.mContentNode:addChild(btnLogin)
end

function HybridSyncLayer:renderConnectedView(st)
    local w, h = self.mBgSize.width, self.mBgSize.height
    local errLine = ""
    if st.last_error and st.last_error ~= "" then
        errLine = "\\nLưu ý: {6c0101}" .. tostring(st.last_error)
    end
    local infoText = string.format(
        "Tài khoản Cloud: {6c0101}%s\\nPhiên bản lưu: Rev #%d  ·  Bạn bè đã đồng bộ: %d\\nĐồng bộ gần nhất: %s  ·  Hàng chờ: %d\\nTự động đồng bộ: 30 phút / vào BXH-PvP-Bạn bè (giãn 3 phút)%s",
        tostring(st.username or ""),
        tonumber(st.sync_rev) or 0,
        tonumber(st.peer_count) or 0,
        formatAgo(st.last_sync_at),
        tonumber(st.pending_events) or 0,
        errLine
    )
    local infoLbl = ui.newLabel({
        text = infoText,
        size = 19,
        color = ColorList.ccBlack,
        dimensions = cc.size(w * 0.88, 0),
        align = cc.TEXT_ALIGNMENT_CENTER,
    })
    infoLbl:setPosition(cc.p(w * 0.5, h * 0.62))
    self.mContentNode:addChild(infoLbl)

    local btnSync = ui.newButton({
        normalImage = "c_77.png",
        text = "Đồng Bộ Ngay",
        fontSize = 20,
        scale = 0.90,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = cc.p(w * 0.23, h * 0.22),
        clickAction = function()
            ui.showFlashView({parent = self, text = "Đang đồng bộ với Cloudflare..."})
            requestHybridApi("POST", "/hybrid/sync", {force_push = false}, function(sr)
                if tolua.isnull(self) then
                    return
                end
                if sr and sr.ok then
                    ui.showFlashView({
                        parent = self,
                        text = string.format(
                            "Đồng bộ OK! Rev #%d · %d bạn bè · +%d thư mới",
                            tonumber(sr.sync_rev) or 0,
                            tonumber(sr.peer_count) or 0,
                            tonumber(sr.inbox_applied) or 0
                        )
                    })
                    self:refreshView()
                elseif sr and sr.conflict then
                    self:showConflictDialog(sr.server_summary, sr.local_summary)
                else
                    ui.showFlashView({parent = self, text = tostring((sr and sr.error) or "Đồng bộ thất bại")})
                    self:refreshView()
                end
            end)
        end,
    })
    self.mContentNode:addChild(btnSync)

    local btnPull = ui.newButton({
        normalImage = "c_7.png",
        text = "Tải Bản Cloud",
        fontSize = 19,
        scale = 0.85,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = cc.p(w * 0.54, h * 0.22),
        clickAction = function()
            local box = require("Common.MessageBoxLayer").new({
                bgImage = "c_43.png",
                closeBtnImage = "c_15.png",
                title = TR("Tải Bản Lưu Cloud"),
                content = "Tải bản lưu từ Cloud về máy này? (Hệ thống tự tạo bản backup cục bộ và giữ nguyên Bang Hội hiện tại)",
                leftBtnTitle = TR("确定"),
                rightBtnTitle = TR("取消"),
                leftBtnCallback = function(dlg)
                    dlg:removeFromParent()
                    requestHybridApi("POST", "/hybrid/pull_save", {}, function(pr)
                        if pr and pr.ok then
                            ui.showFlashView({parent = display.getRunningScene(), text = "Đã tải bản Cloud! Đang tải lại game..."})
                            reloadGameScene()
                        else
                            ui.showFlashView({parent = self, text = tostring((pr and pr.error) or "Không có bản lưu trên Cloud")})
                        end
                    end)
                end,
                rightBtnCallback = function(dlg)
                    dlg:removeFromParent()
                end,
            })
            self:addChild(box, 200)
        end,
    })
    self.mContentNode:addChild(btnPull)

    local btnLogout = ui.newButton({
        normalImage = "c_7.png",
        text = "Ngắt Cloud",
        fontSize = 18,
        scale = 0.82,
        color = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        outlineSize = 2,
        position = cc.p(w * 0.82, h * 0.22),
        clickAction = function()
            requestHybridApi("POST", "/hybrid/logout", {}, function()
                if not tolua.isnull(self) then
                    ui.showFlashView({parent = self, text = "Đã ngắt Đồng Bộ Cloud (dữ liệu offline vẫn giữ nguyên)"})
                    self:refreshView()
                end
            end)
        end,
    })
    self.mContentNode:addChild(btnLogout)
end

return HybridSyncLayer
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
        "teambattle_handlers.py",
        "nightmare_handlers.py",
        "reborn_handlers.py",
        "ggzj_handlers.py",
        "gddh_handlers.py",
        "social_handlers.py",
        "guild_handlers.py",
        "pvpinter_handlers.py",
        "pet_handlers.py",
        "pet_data.json",
        "warfare_handlers.py",
        "warfare_data.json",
        "private_auth.py",
        "hybrid_sync.py",
        "sync_ca_bundle.pem",
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


def disable_legacy_permissions_array(work_dir: Path) -> None:
    """Empty out MQActivity.mPermissons so Android never prompts for obsolete permissions."""
    mq_act_path = work_dir / "smali" / "com" / "moqikaka" / "sdk" / "MQActivity.smali"
    mq_act_src = mq_act_path.read_text(encoding="utf-8")
    mq_act_src, n_perm = re.subn(
        r"const/4 v0, 0x2\s+new-array v0, v0, \[Ljava/lang/String;.*?iput-object v0, p0, Lcom/moqikaka/sdk/MQActivity;->mPermissons:\[Ljava/lang/String;",
        "const/4 v0, 0x0\n\n    new-array v0, v0, [Ljava/lang/String;\n\n    iput-object v0, p0, Lcom/moqikaka/sdk/MQActivity;->mPermissons:[Ljava/lang/String;",
        mq_act_src,
        count=1,
        flags=re.S,
    )
    if n_perm != 1:
        raise RuntimeError("Failed to patch mPermissons in MQActivity.smali")
    mq_act_path.write_text(mq_act_src, encoding="utf-8")


def unpack_libs_apk(work_dir: Path) -> None:
    """Move assets/libs.apk dex classes into smali_classes2 and stub MQApplication.loadDex."""
    libs_apk = work_dir / "assets" / "libs.apk"
    if not libs_apk.exists():
        return
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
        classes2_dir = work_dir / "smali_classes2"
        if classes2_dir.exists():
            shutil.rmtree(classes2_dir)
        shutil.copytree(dec_dir / "smali", classes2_dir)
    libs_apk.unlink(missing_ok=True)
    mq_app_path = work_dir / "smali" / "com" / "moqikaka" / "sdk" / "MQApplication.smali"
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
    disable_legacy_permissions_array(work_dir)
    mq_act_path = work_dir / "smali" / "com" / "moqikaka" / "sdk" / "MQActivity.smali"
    mq_act_src = mq_act_path.read_text(encoding="utf-8")

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
    unpack_libs_apk(STANDALONE_WORK)

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
    patch_modern_android_sdk(STANDALONE_WORK)

    # 5. Apply shared gameplay patches (R7.6..R7.40 + OBB + B83..86), then standalone-only UI & Python runtime
    apply_shared_gameplay_patches(STANDALONE_WORK)

    patch_luac_text(
        STANDALONE_WORK / "assets" / "src" / "System" / "SystemLayer.luac",
        [
            (
                '    canLogout = canLogout:len() == 0 and "true" or canLogout',
                '    canLogout = "true"',
            ),
            (
                '        {\n'
                '            normalImage = "xt_15.png",\n'
                '            title = TR("邮件"),\n'
                '            muduleId = ModuleSub.eEmail,\n'
                '            clickAction = function(parameters)\n'
                '                print("按下邮件按钮")\n'
                '                local isOpen, retInfo = NetworkResData:modulePlayerIsOpen(ModuleSub.eEmail)\n'
                '                if not isOpen then\n'
                '                    ui.showFlashView({parent = self, text = retInfo.openMessage,})\n'
                '                    return\n'
                '                end\n'
                '                local email = require("Email.EmailHelper").new()\n'
                '                local tempLayer\n'
                '                tempLayer = email:showEmail({parent = self, onCloseCallback = function()\n'
                '                    tempLayer:removeFromParent()\n'
                '                    self:refreshRedDot()\n'
                '                end})\n'
                '            end,\n'
                '        },\n'
                '        \n'
                '    }',
                '        {\n'
                '            normalImage = "xt_15.png",\n'
                '            title = TR("邮件"),\n'
                '            muduleId = ModuleSub.eEmail,\n'
                '            clickAction = function(parameters)\n'
                '                print("按下邮件按钮")\n'
                '                local isOpen, retInfo = NetworkResData:modulePlayerIsOpen(ModuleSub.eEmail)\n'
                '                if not isOpen then\n'
                '                    ui.showFlashView({parent = self, text = retInfo.openMessage,})\n'
                '                    return\n'
                '                end\n'
                '                local email = require("Email.EmailHelper").new()\n'
                '                local tempLayer\n'
                '                tempLayer = email:showEmail({parent = self, onCloseCallback = function()\n'
                '                    tempLayer:removeFromParent()\n'
                '                    self:refreshRedDot()\n'
                '                end})\n'
                '            end,\n'
                '        },\n'
                '        {\n'
                '            normalImage = "xt_13.png",\n'
                '            title = "Đồng Bộ Cloud",\n'
                '            clickAction = function()\n'
                '                self:addChild(require("System.HybridSyncLayer").new(), 50)\n'
                '            end,\n'
                '        },\n'
                '        \n'
                '    }',
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
                '            self:addChild(require("System.AccountSwitchLayer").new(), 200)\n'
                '        end\n'
                '    })\n'
                '    btnAcctMgr:setScale(Adapter.MinScale * 0.9)\n'
                '    self:addChild(btnAcctMgr)\n'
                '    local btnCloudSync = ui.newButton({\n'
                '        normalImage = "c_77.png",\n'
                '        position = Adapter.AutoPos(960, 172),\n'
                '        text = "Đồng Bộ Cloud",\n'
                '        fontSize = 20,\n'
                '        textColor = ColorList.ccWhite,\n'
                '        outlineColor = ColorList.ccOutline,\n'
                '        clickAction = function()\n'
                '            self:addChild(require("System.HybridSyncLayer").new(), 205)\n'
                '        end\n'
                '    })\n'
                '    btnCloudSync:setScale(Adapter.MinScale * 0.9)\n'
                '    self:addChild(btnCloudSync)',
            ),
        ],
    )
    write_luac_text(
        STANDALONE_WORK / "assets" / "src" / "System" / "AccountSwitchLayer.luac",
        ACCOUNT_SWITCH_LAYER_LUA,
    )
    write_luac_text(
        STANDALONE_WORK / "assets" / "src" / "System" / "HybridSyncLayer.luac",
        HYBRID_SYNC_LAYER_LUA,
    )

    # 7. Bundle embedded 32-bit CPython 3.11 + server_bundle.zip + stdlib.zip
    bundle_embedded_python(STANDALONE_WORK, f"{version_name}-{version_code}")


def apply_shared_gameplay_patches(work_dir: Path) -> None:
    """Apply all shared R7.6..R7.40 VN Lua gameplay patches, configs, OBB merge, and banner assets."""
    patch_luac_text(
        work_dir / "assets" / "src" / "Home" / "HomeScene.luac",
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
        work_dir / "assets" / "src" / "Guide" / "GuideMng.luac",
        [
            (
                "        if heroCount > 2 then\n            newEventId = 107\n        elseif heroCount > 1 then\n            newEventId = 1051\n        else\n            newEventId = 104\n        end",
                "        if heroCount > 1 then\n            newEventId = 107\n        else\n            newEventId = 1051\n        end",
            ),
        ],
    )
    patch_luac_text(
        work_dir / "assets" / "src" / "Store" / "RechargeScene.luac",
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
                '        local iconSprite = cc.Sprite:create(data.icon)\n'
                '        iconSprite:setPosition(cc.p(67, 68))\n'
                '        cellBkg:addChild(iconSprite)\n'
                '        -- dump(info,"infooooooo")\n'
                '        --local _,str2 = self:isFormatPrice(info.ChargePoint)\n'
                '        -- print("jkjkjkkkkkkkkk===  ",str2)\n'
                '        local priceLabel = ui.newLabel({\n'
                '            text = string.format(TR("仅售:%s"), tostring(info.ChargePoint)),',
                '        local isInstant = info.Instant or info.ProductId == "com.cmn.inuyasha.gem1000000"\n'
                '        local iconSprite = cc.Sprite:create(isInstant and "sc_9.png" or data.icon)\n'
                '        iconSprite:setPosition(cc.p(67, 68))\n'
                '        cellBkg:addChild(iconSprite)\n'
                '        local priceLabel = ui.newLabel({\n'
                '            text = isInstant and "Nạp 1 chạm (Miễn phí)" or string.format(TR("仅售:%s"), tostring(info.ChargePoint)),',
            ),
            (
                '        local rechargeButton = ui.newButton({\n'
                '            normalImage = btnImage,\n'
                '            position = cc.p(382, 53),\n'
                '            text = TR("购买"),',
                '        local rechargeButton = ui.newButton({\n'
                '            normalImage = btnImage,\n'
                '            position = cc.p(382, 53),\n'
                '            text = isInstant and "Nạp 1M" or TR("购买"),',
            ),
            (
                '        else\n'
                '            lableValue:setString(string.format(TR("%d"), info.GamePoint))\n'
                '            lableValue:setPosition(cc.p(261,105))\n'
                '            cellBkg:addChild(lableValue)\n'
                '        end',
                '        elseif isInstant then\n'
                '            lableValue:setString("1.000.000 KC")\n'
                '            lableValue:setPosition(cc.p(245,105))\n'
                '            cellBkg:addChild(lableValue)\n'
                '        else\n'
                '            lableValue:setString(string.format(TR("%d"), info.GamePoint))\n'
                '            lableValue:setPosition(cc.p(261,105))\n'
                '            cellBkg:addChild(lableValue)\n'
                '        end',
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
                '            if not isMothCard and (productInfo.Instant or productInfo.ProductId == "com.cmn.inuyasha.gem1000000") then\n'
                '                LoadingWait:begin(self)\n'
                '                HttpRequest("PlayerCharge", "ConfirmOrder", {productInfo.ProductId, orderId}, function(res)\n'
                '                    LoadingWait:ends()\n'
                '                    if res.Status == 0 then\n'
                '                        if self.mBkgLayer and self.mBkgLayer.refreshPlayerAttrs then\n'
                '                            self.mBkgLayer:refreshPlayerAttrs()\n'
                '                        end\n'
                '                        self.mPlayerVipLv = NetworkResData:getPlayerInfo().Vip\n'
                '                        ui.showFlashView({parent = self, text = "Đã nạp +1.000.000 KC!"})\n'
                '                        self.mChargeTotalInfo = nil\n'
                '                        self.mChargeSingleInfo = nil\n'
                '                        self.mChargeDaysInfo = nil\n'
                '                        self:requestGetChargeList(true)\n'
                '                    end\n'
                '                end)\n'
                '                return\n'
                '            end\n'
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
        work_dir / "assets" / "src" / "ExtraActivity" / "MonthCardLayer.luac",
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
        work_dir / "assets" / "src" / "TimedActivity" / "LimittedTimedRecruitLayer.luac",
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
                '        local bCount = #self.mBannerList\n'
                '        local tabScale = bCount > 3 and 0.65 or 0.85\n'
                '        local stepX = bCount > 3 and 142 or 160\n'
                '        local startX = bCount > 3 and 115 or 135\n'
                '        local bannerNames = {\n'
                '            [81] = "Sessho (81)",\n'
                '            [82] = "Taishou (82)",\n'
                '            [83] = "Tứ Đấu (83)",\n'
                '            [84] = "Phe I (84)",\n'
                '            [85] = "Phe S (85)",\n'
                '            [86] = "Phe N (86)",\n'
                '        }\n'
                '        for bIdx, bItem in ipairs(self.mBannerList) do\n'
                '            local bId = bItem.ActivityId\n'
                '            local isCur = (bId == self.mActivityInfo.enumId)\n'
                '            local shortName = bannerNames[bId] or ("Banner " .. tostring(bId))\n'
                '            local tabBtn = ui.newButton({\n'
                '                normalImage = isCur and "c_77.png" or "c_7.png",\n'
                '                text = shortName,\n'
                '                scale = tabScale,\n'
                '                position = cc.p(startX + (bIdx - 1) * stepX, self.mBgSize.height - 102),\n'
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

    # 6. Shared ChatMng safe guard (disabled TCP loop until realtime chat server lands)
    patch_luac_text(
        work_dir / "assets" / "src" / "Chat" / "ChatMng.luac",
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
        work_dir / "assets" / "src" / "TimedActivity" / "TimedSlotLayer.luac",
        [("local pos = slot:get_cur_pos(cursors[i])", "local pos = slot:get_cur_pos(i)")],
    )

    patch_r712_lua(work_dir / "assets" / "src")
    patch_reward_claim_lua(work_dir / "assets" / "src")
    patch_mystery_shop_lua(work_dir / "assets" / "src")
    patch_r714_lua(work_dir / "assets" / "src")
    patch_r715_lua(work_dir / "assets" / "src")
    patch_r7151_lua(work_dir / "assets" / "src")
    patch_r716_explore_lua(work_dir / "assets" / "src")
    patch_r721_teambattle_lua(work_dir / "assets" / "src")
    patch_r735_shop_lua(work_dir / "assets" / "src")
    patch_r736_mate_gem_shop_lua(work_dir / "assets" / "src")
    patch_r737_mount_and_p4_lua(work_dir / "assets" / "src")
    patch_r739_lianti_lua(work_dir / "assets" / "src")
    patch_r740_pvpinter_lua(work_dir / "assets" / "src")
    patch_r85_pet_lua(work_dir / "assets" / "src")
    patch_r86_warfare_lua(work_dir / "assets" / "src")
    patch_luac_text(work_dir / "assets" / "src" / "Equipment" / "EquipmentComposeLayer.luac", [
        (
            '        if colorLV < 8 then    --排除最高等级的装备',
            '        local recipe = EquipColorRelation.items[colorLV]\n'
            '        if recipe and recipe.colorFinally > colorLV then',
        ),
    ])
    patch_luac_text(work_dir / "assets" / "src" / "Store" / "RecruitScene.luac", [
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
            work_dir / "assets" / "src" / "Config" / f"{cfg_name}.luac",
            cfg_src.read_text(encoding="utf-8"),
        )

    # 8. Merge OBB res/* directly into assets/res/* for 1-file installation
    merged_n = merge_obb_into_assets(work_dir)
    print(f"Merged {merged_n} OBB resource files directly into APK assets/res/")

    # 9. Bundle Banner 83 / Tứ Đấu Thần / Inu Kimi assets missing from VN APK/OBB
    b83_dir = ROOT_DIR / "android" / "assets_b83"
    if b83_dir.exists():
        b83_n = 0
        for src_file in sorted(b83_dir.rglob("*")):
            if src_file.is_file():
                rel = src_file.relative_to(b83_dir)
                dst_file = work_dir / "assets" / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                b83_n += 1
        print(f"Bundled {b83_n} Banner 83 assets from {b83_dir}")

    # 9b. Bundle Banner 84/85/86 (Faction UR Banners) assets missing from VN APK/OBB
    b84_dir = ROOT_DIR / "android" / "assets_b84_86"
    if b84_dir.exists():
        b84_n = 0
        for src_file in sorted(b84_dir.rglob("*")):
            if src_file.is_file():
                rel = src_file.relative_to(b84_dir)
                dst_file = work_dir / "assets" / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                b84_n += 1
        print(f"Bundled {b84_n} Banner 84-86 assets from {b84_dir}")


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

function HeroUpdateScene:createHeroBreakthrough(step)
    local heroCfg = self.mHero and HeroModel.items[self.mHero.HeroModelId]
    if heroCfg and heroCfg.specialType == 255 then
        local pInfo = NetworkResData:getPlayerInfo()
        if pInfo and pInfo.Lv and self.mHero.Lv ~= pInfo.Lv then
            self.mHero.Lv = pInfo.Lv
            NetworkResData:modifyMainHeroLv(pInfo.Lv)
        end
    end''',
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


def patch_r721_teambattle_lua(src: Path) -> None:
    """Fix R7.21 Teambattle scene error-status checks and immediate InviteAll refresh."""
    patch_luac_text(src / "InstanceZones" / "InstanceNewMainScene.luac", [
        (
            "        if event.Value and event.Value.TeamsInfo then",
            "        if event and event.Status == 0 and event.Value and event.Value.TeamsInfo then",
        ),
        (
            "        if event.Value and event.Value then",
            "        if event and event.Status == 0 and event.Value and event.Value.TeamId then",
        ),
    ])
    patch_luac_text(src / "InstanceZones" / "TeamWaitScene.luac", [
        (
            "                       if self.mSelectType == 2 then\n"
            "                           if not self.mScheduleHandle then",
            "                       if self.mSelectType == 1 then\n"
            "                           self:requestTeamInfor()\n"
            "                       elseif self.mSelectType == 2 then\n"
            "                           if not self.mScheduleHandle then",
        ),
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


def patch_r735_shop_lua(src: Path) -> None:
    """R7.35 QoL: daily Shop Reset button + 1-tap Max & accurate DynamicPrice in GoodsPurchaseLayer."""
    patch_luac_text(src / "Store" / "StoreScene.luac", [
        (
            "    self.mParentLayer:addChild(self.mButtonRecharge)",
            "    self.mParentLayer:addChild(self.mButtonRecharge)\n\n"
            "    self.mButtonResetShop = ui.newButton({\n"
            '        normalImage = "c_7.png",\n'
            '        text = "Reset Shop",\n'
            "        fontSize = 24,\n"
            "        position = cc.p(706, 680),\n"
            "        textColor = ColorList.ccWhite,\n"
            "        outlineColor = ColorList.ccOutline,\n"
            "        clickAction = function()\n"
            "            self:requestResetDailyShop()\n"
            "        end,\n"
            "    })\n"
            "    self.mParentLayer:addChild(self.mButtonResetShop)",
        ),
        (
            "    if  self.mCurrentPage == PageType.props then\n"
            "        self:requestPropsList()",
            "    if self.mButtonResetShop then\n"
            "        self.mButtonResetShop:setVisible(self.mCurrentPage == PageType.props)\n"
            "    end\n"
            "    if  self.mCurrentPage == PageType.props then\n"
            "        self:requestPropsList()",
        ),
        (
            """function StoreScene:updatePropsList(props)
    for _, v in pairs(self.mPropsList) do
        if v.GoodsModelId == props.GoodsModelId then
            v.Num = props.Num
            v.CurrPrice = props.CurrPrice
            break
        end
    end
end""",
            """function StoreScene:updatePropsList(props)
    for _, v in pairs(self.mPropsList) do
        if v.GoodsModelId == props.GoodsModelId then
            v.Num = props.Num
            v.MaxNum = props.MaxNum
            v.CurrPrice = props.CurrPrice
            v.DynamicPrice = props.DynamicPrice
            break
        end
    end
end""",
        ),
        (
            """function StoreScene:responsePropsList(response)
    LoadingWait:ends()
     if response.Status == 0 then
         self.mPropsList = clone(response.Value)
         self:refreshListView()
     end
 end""",
            """function StoreScene:responsePropsList(response)
    LoadingWait:ends()
     if response.Status == 0 then
         self.mPropsList = clone(response.Value)
         self:refreshListView()
     end
 end

function StoreScene:requestResetDailyShop()
    LoadingWait:begin(self)
    HttpRequest("ShopGoods", "ResetDaily", {}, handler(self, self.responseResetDailyShop))
end

function StoreScene:responseResetDailyShop(response)
    LoadingWait:ends()
    if response and response.Status == 0 then
        self.mPropsList = clone(response.Value or {})
        self:refreshListView()
        self.mBkgLayer:refreshPlayerAttrs()
        ui.showFlashView({parent = self, image = nil, text = "Đã reset shop hằng ngày!"})
    end
end""",
        ),
        (
            "     local res = self:isResourceEnough(self.mSelGoodsData.SellTypeId, self.mSelGoodsData.CurrPrice, count)",
            "     local totalCost = self.mSelGoodsData.CurrPrice * count\n"
            "     if self.mSelGoodsData.DynamicPrice and #self.mSelGoodsData.DynamicPrice > 0 then\n"
            "         local dyn = self.mSelGoodsData.DynamicPrice\n"
            "         local startIdx = 1\n"
            "         for idx = 1, #dyn do\n"
            "             if dyn[idx].NewPrice == self.mSelGoodsData.CurrPrice then\n"
            "                 startIdx = idx\n"
            "                 break\n"
            "             end\n"
            "         end\n"
            "         local sumCost = 0\n"
            "         local maxIdx = #dyn\n"
            "         for k = 1, count do\n"
            "             local item = dyn[(k - 1) + startIdx] or dyn[maxIdx]\n"
            "             sumCost = sumCost + ((item and item.NewPrice) or self.mSelGoodsData.CurrPrice)\n"
            "         end\n"
            "         totalCost = sumCost\n"
            "     end\n"
            "     local res = self:isResourceEnough(self.mSelGoodsData.SellTypeId, totalCost, 1)",
        ),
    ])

    patch_luac_text(src / "Store" / "GoodsPurchaseLayer.luac", [
        (
            "    self.mParentLayer:addChild(btnCancel)\nend",
            "    self.mParentLayer:addChild(btnCancel)\n\n"
            "    local btnMax = ui.newButton({\n"
            '        normalImage = "c_8.png",\n'
            '        text = "Max",\n'
            "        fontSize = 20,\n"
            "        fontName = _FONT_DEFAULT,\n"
            "        position = cc.p(self.width * 0.812, self.height * 0.33),\n"
            "        textColor = ColorList.ccWhite,\n"
            "        size = cc.size(82, 40),\n"
            "        clickAction = function()\n"
            "            local maxByLimit = 99\n"
            "            if self.mCurGoods.MaxNum < 0 then\n"
            "                if self.mCurGoods.GoodsModelId == 16030003 then\n"
            "                    maxByLimit = 200\n"
            "                end\n"
            "            else\n"
            "                maxByLimit = math.max(1, self.mCurGoods.MaxNum - self.mCurGoods.Num)\n"
            "            end\n"
            "            local player = NetworkResData:getPlayerInfo()\n"
            "            local balance = maxByLimit\n"
            "            local hasCap = false\n"
            "            if player then\n"
            "                if self.mCurGoods.SellTypeId == ResourcetypeSub.eDiamond then\n"
            "                    balance = tonumber(player.Diamond) or 0\n"
            "                    hasCap = true\n"
            "                elseif self.mCurGoods.SellTypeId == ResourcetypeSub.eGold then\n"
            "                    balance = tonumber(player.Gold) or 0\n"
            "                    hasCap = true\n"
            "                end\n"
            "            end\n"
            "            local best = 1\n"
            "            if not hasCap then\n"
            "                best = maxByLimit\n"
            "            else\n"
            "                for n = maxByLimit, 1, -1 do\n"
            "                    if self:computeTotalCost(n) <= balance then\n"
            "                        best = n\n"
            "                        break\n"
            "                    end\n"
            "                end\n"
            "            end\n"
            "            self.mPurchaseCount = best\n"
            "            self:refreshPurchaseDisplay()\n"
            "        end,\n"
            "    })\n"
            "    self.mParentLayer:addChild(btnMax)\n"
            "end",
        ),
        (
            """    local value = 0
    if self.mCurGoods.DynamicPrice then
        local function getPriceIndex()
            for i = 1, table.maxn(self.mCurGoods.DynamicPrice) do 
                if self.mCurGoods.DynamicPrice[i].NewPrice == self.mCurGoods.CurrPrice then 
                    return i
                end
            end
            return 1
        end
        local max = table.maxn(self.mCurGoods.DynamicPrice)
        local index = getPriceIndex()
        for k = 1, self.mPurchaseCount do
            local curIndex = (k - 1) + index
            local item = self.mCurGoods.DynamicPrice[curIndex] or self.mCurGoods.DynamicPrice[max]
            if item then 
                value = value + item.NewPrice
            end
        end
    else
        value = self.mPurchaseCount * self.mCurGoods.CurrPrice
    end
    self.mLableTotalValue:setString(string.format("%d", value))
end""",
            """    self:refreshPurchaseDisplay()
end

function GoodsPurchaseLayer:computeTotalCost(count)
    local cnt = count or self.mPurchaseCount or 1
    local value = 0
    if self.mCurGoods.DynamicPrice and #self.mCurGoods.DynamicPrice > 0 then
        local function getPriceIndex()
            for i = 1, table.maxn(self.mCurGoods.DynamicPrice) do
                if self.mCurGoods.DynamicPrice[i].NewPrice == self.mCurGoods.CurrPrice then
                    return i
                end
            end
            return 1
        end
        local max = table.maxn(self.mCurGoods.DynamicPrice)
        local index = getPriceIndex()
        for k = 1, cnt do
            local curIndex = (k - 1) + index
            local item = self.mCurGoods.DynamicPrice[curIndex] or self.mCurGoods.DynamicPrice[max]
            if item then
                value = value + item.NewPrice
            end
        end
    else
        value = cnt * self.mCurGoods.CurrPrice
    end
    return value
end

function GoodsPurchaseLayer:refreshPurchaseDisplay()
    self.mLableViewGoodsNum:setString(string.format("%d", self.mPurchaseCount))
    self.mLableTotalValue:setString(string.format("%d", self:computeTotalCost(self.mPurchaseCount)))
end""",
        ),
    ])


def patch_r736_mate_gem_shop_lua(src: Path) -> None:
    """R7.36 QoL/Fixes: Gem Compose UI, Gem Unequip, LV15 guard, and proactive Reset buttons on daily shops."""
    patch_luac_text(src / "Equipment" / "EquipmentComposeLayer.luac", [
        (
            "            modelId = cardInfor.EquipModelId or cardInfor.TreasureModelId,",
            "            modelId = cardInfor.EquipModelId or cardInfor.TreasureModelId or cardInfor.ModelId,",
        ),
        (
            """        local material = splitStrBySep(self.mTempTable[self.mCellList[index[1]].ModelId + 1].syntheticDoubleUse, ",")
        local haveGood = NetworkResData:getGoodsCountByModelId(tonumber(material[2]))
        if haveGood > 0 then
            self.mBtnStone:setCardData({resourceTypeSub = tonumber(material[1]),modelId = tonumber(material[2]),num = haveGood,cardShowAttrs = {CardShowAttr.eBorder,CardShowAttr.eLevel},isTouch = true})
        else
            self.mBtnStone:setEmpty({CardShowAttr.eBorder}, "c_1.png", "c_99.png")
        end""",
            """        local nextModel = self.mTempTable[self.mCellList[index[1]].ModelId + 1]
        local material = nextModel and nextModel.syntheticDoubleUse and splitStrBySep(nextModel.syntheticDoubleUse, ",") or {}
        local dblType = tonumber(material[1])
        local dblModel = tonumber(material[2])
        local haveGood = dblModel and NetworkResData:getGoodsCountByModelId(dblModel) or 0
        if dblType and dblModel and haveGood > 0 then
            self.mBtnStone:setCardData({resourceTypeSub = dblType,modelId = dblModel,num = haveGood,cardShowAttrs = {CardShowAttr.eBorder,CardShowAttr.eLevel},isTouch = true})
        else
            self.mBtnStone:setEmpty({CardShowAttr.eBorder}, "c_1.png", "c_99.png")
        end""",
        ),
    ])

    patch_luac_text(src / "Formation" / "MyFormationLayer.luac", [
        (
            """        normalImage = "c_7.png",
        text = TR("升级"),
        operateBtnTag = OperateBtnTag.eGemUpdate,
        position = cc.p(parentSize.width / 2 - 125,35),""",
            """        normalImage = "c_7.png",
        text = TR("升级"),
        operateBtnTag = OperateBtnTag.eGemUpdate,
        position = cc.p(parentSize.width / 2 - 145,35),""",
        ),
        (
            """        normalImage = "c_7.png",
        text = TR("更换"),
        operateBtnTag = OperateBtnTag.eGemReplace,
        position = cc.p(parentSize.width / 2 + 125,35),""",
            """        normalImage = "c_7.png",
        text = "Tháo",
        position = cc.p(parentSize.width / 2,35),
        clickAction = function()
            self:removeModalLayer()
            local tempSlot = self.mFormationInfo.SlotInfos[self.mSelectedIndex]
            local tempGem = tempSlot and tempSlot.Gem and tempSlot.Gem[self.mSelGemIndex]
            if not tempGem or not IdIsValid(tempGem.Id) then
                ui.showFlashView({parent = self, text = "Ô linh thạch đang trống!"})
                return
            end
            self:GemCombatRequest(EMPTY_ENTITY_ID)
        end
    })
    table.insert(optBtnInfo, {
        normalImage = "c_7.png",
        text = TR("更换"),
        operateBtnTag = OperateBtnTag.eGemReplace,
        position = cc.p(parentSize.width / 2 + 145,35),""",
        ),
    ])

    patch_luac_text(src / "Gem" / "GemLevelUpLayer.luac", [
        (
            """function GemLevelUpLayer:requestLevelUp()
    if #self.mCellList < 3 then""",
            """function GemLevelUpLayer:requestLevelUp()
    if not self.mGemData or not GemModel.items[self.mGemData.ModelId + 1] then
        ui.showFlashView({parent = self, text = "Linh thạch đã đạt cấp tối đa!"})
        return
    end
    if #self.mCellList < 3 then""",
        ),
    ])

    patch_luac_text(src / "Store" / "MysticalStoreScene.luac", [
        (
            "    self.mParentLayer:addChild(buttonRefersh)\n    self.mBtnRefresh = buttonRefersh",
            "    self.mParentLayer:addChild(buttonRefersh)\n    self.mBtnRefresh = buttonRefersh\n\n"
            "    local buttonResetDaily = ui.newButton({\n"
            '        normalImage = "c_7.png",\n'
            "        position = cc.p(810, 45),\n"
            '        text = "Reset Ngày",\n'
            "        fontSize = 22,\n"
            "        textColor = ColorList.ccWhite,\n"
            "        outlineColor = ColorList.ccOutline,\n"
            "        clickAction = function()\n"
            "            self:requestResetDailyMysteryShop()\n"
            "        end,\n"
            "    })\n"
            "    self.mParentLayer:addChild(buttonResetDaily)\n"
            "    self.mBtnResetDaily = buttonResetDaily",
        ),
        (
            "function MysticalStoreScene:requestRefreshtGoodsList()",
            """function MysticalStoreScene:requestResetDailyMysteryShop()
    local isSenior = (self.mCurrStoreType == StoreType.eSenior) and 1 or 0
    LoadingWait:begin(self)
    HttpRequest("MysteryShop", "ResetDaily", {isSenior}, function(response)
        LoadingWait:ends()
        if response and response.Status == 0 then
            if isSenior == 1 then
                self.mStoreInfo.seniorStore = response.Value
                self.mStoreInfo.normalStore = nil
            else
                self.mStoreInfo.normalStore = response.Value
                self.mStoreInfo.seniorStore = nil
            end
            self:updateLayer()
            self:refreshListView(true)
            ui.showFlashView({parent = self, text = "Đã reset Shop Thần Bí!"})
        end
    end)
end

function MysticalStoreScene:requestRefreshtGoodsList()""",
        ),
    ])

    patch_luac_text(src / "Challenge" / "ArenaExchangeLayer.luac", [
        (
            "    self.mBgSprite:addChild(self.mCurrPVPCoin)",
            "    self.mBgSprite:addChild(self.mCurrPVPCoin)\n\n"
            "    local btnResetPvpShop = ui.newButton({\n"
            '        normalImage = "c_7.png",\n'
            "        position = cc.p(self.mBgSize.width * 0.78, self.mBgSize.height - 100),\n"
            '        text = "Reset Ngày",\n'
            "        fontSize = 22,\n"
            "        textColor = ColorList.ccWhite,\n"
            "        outlineColor = ColorList.ccOutline,\n"
            "        clickAction = function()\n"
            "            self:PVPShopResetDailyRequest()\n"
            "        end,\n"
            "    })\n"
            "    self.mBgSprite:addChild(btnResetPvpShop)",
        ),
        (
            "function ArenaExchangeLayer:PVPShopBuyRequest(shopId, num)",
            """function ArenaExchangeLayer:PVPShopResetDailyRequest()
    LoadingWait:begin(self)
    HttpRequest("PVPShop", "ResetDaily", {}, function(retVal)
        LoadingWait:ends()
        if retVal and retVal.Status == 0 then
            for _, item in pairs(self.mNoneRankShopInfo or {}) do
                item.BuyNum = 0
            end
            for _, item in pairs(self.mRankShopInfo or {}) do
                item.BuyNum = 0
            end
            local activeList = self.mCurrPageType == ArenaExchangePageType.eNoneRank and self.mNoneRankShopInfo or self.mRankShopInfo
            for idx = 1, #(activeList or {}) do
                self:refreshListItem(idx)
            end
            ui.showFlashView({parent = self, text = "Đã reset Shop Đấu Trường!"})
        end
    end)
end

function ArenaExchangeLayer:PVPShopBuyRequest(shopId, num)""",
        ),
    ])

    patch_luac_text(src / "Guild" / "GuildShopLayer.luac", [
        (
            "                    bgSprite:addChild(shopLvLabel)",
            "                    bgSprite:addChild(shopLvLabel)\n"
            "                    local btnResetGuildShop = ui.newButton({\n"
            '                        normalImage = "c_7.png",\n'
            "                        position = cc.p(bgSize.width * 0.80, bgSize.height * 0.95),\n"
            '                        text = "Reset Ngày",\n'
            "                        fontSize = 22,\n"
            "                        textColor = ColorList.ccWhite,\n"
            "                        outlineColor = ColorList.ccOutline,\n"
            "                        clickAction = function()\n"
            "                            LoadingWait:begin(self)\n"
            '                            HttpRequest("Guild", "ResetGuildShopDaily", {}, function(res)\n'
            "                                LoadingWait:ends()\n"
            "                                if res and res.Status == 0 and not tolua.isnull(self) then\n"
            "                                    local p = self:getParent()\n"
            "                                    self:removeFromParent()\n"
            "                                    if p and not tolua.isnull(p) then\n"
            '                                        p:addChild(require("Guild.GuildShopLayer").new({}))\n'
            '                                        ui.showFlashView({parent = p, text = "Đã reset Shop Công Hội!"})\n'
            "                                    end\n"
            "                                end\n"
            "                            end)\n"
            "                        end,\n"
            "                    })\n"
            "                    bgSprite:addChild(btnResetGuildShop)",
        ),
    ])


def patch_r737_mount_and_p4_lua(src: Path) -> None:
    """R7.37: Canonical Red Book/Mount PrModel bonds (573..594) + Banner 84/85/86 UI assets."""
    r737_pr_entries = """        [572] = {
            ID = 572,
            name = "Thức Hồn",
            intro = "Cùng  ra trận,HP+18%",
            member = "14011618",
            typeID = 1401,
            APR = 0,
            HPR = 1800,
            DEFR = 0
        },
        [573] = {
            ID = 573,
            name = "Quyển Kami",
            intro = "Cùng Quyển Kami ra trận,HP+20%",
            member = "14012001",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [574] = {
            ID = 574,
            name = "Quyển Tứ Hồn",
            intro = "Cùng Quyển Tứ Hồn ra trận,HP+20%",
            member = "14012002",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [575] = {
            ID = 575,
            name = "Quyển Kami",
            intro = "Cùng Quyển Kami ra trận,HP+20%",
            member = "14012001",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [576] = {
            ID = 576,
            name = "Quyển Tứ Hồn",
            intro = "Cùng Quyển Tứ Hồn ra trận,HP+20%",
            member = "14012002",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [577] = {
            ID = 577,
            name = "Quyển Kami",
            intro = "Cùng Quyển Kami ra trận,HP+20%",
            member = "14012001",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [578] = {
            ID = 578,
            name = "Quyển Tứ Hồn",
            intro = "Cùng Quyển Tứ Hồn ra trận,HP+20%",
            member = "14012002",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [579] = {
            ID = 579,
            name = "Quyển Kami",
            intro = "Cùng Quyển Kami ra trận,HP+20%",
            member = "14012001",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [580] = {
            ID = 580,
            name = "Quyển Tứ Hồn",
            intro = "Cùng Quyển Tứ Hồn ra trận,HP+20%",
            member = "14012002",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [581] = {
            ID = 581,
            name = "Quyển Kami",
            intro = "Cùng Quyển Kami ra trận,HP+20%",
            member = "14012001",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [582] = {
            ID = 582,
            name = "Quyển Tứ Hồn",
            intro = "Cùng Quyển Tứ Hồn ra trận,HP+20%",
            member = "14012002",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [583] = {
            ID = 583,
            name = "Quyển Kami",
            intro = "Cùng Quyển Kami ra trận,HP+20%",
            member = "14012001",
            typeID = 1401,
            APR = 0,
            HPR = 2000,
            DEFR = 0
        },
        [584] = {
            ID = 584,
            name = "Rồng Kami",
            intro = "Cùng Rồng Kami ra trận,Công+20%",
            member = "14022001",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [585] = {
            ID = 585,
            name = "Phượng Hoàng Kami",
            intro = "Cùng Phượng Hoàng Kami ra trận,Công+20%",
            member = "14022002",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [586] = {
            ID = 586,
            name = "Rồng Kami",
            intro = "Cùng Rồng Kami ra trận,Công+20%",
            member = "14022001",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [587] = {
            ID = 587,
            name = "Phượng Hoàng Kami",
            intro = "Cùng Phượng Hoàng Kami ra trận,Công+20%",
            member = "14022002",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [588] = {
            ID = 588,
            name = "Rồng Kami",
            intro = "Cùng Rồng Kami ra trận,Công+20%",
            member = "14022001",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [589] = {
            ID = 589,
            name = "Phượng Hoàng Kami",
            intro = "Cùng Phượng Hoàng Kami ra trận,Công+20%",
            member = "14022002",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [590] = {
            ID = 590,
            name = "Rồng Kami",
            intro = "Cùng Rồng Kami ra trận,Công+20%",
            member = "14022001",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [591] = {
            ID = 591,
            name = "Phượng Hoàng Kami",
            intro = "Cùng Phượng Hoàng Kami ra trận,Công+20%",
            member = "14022002",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [592] = {
            ID = 592,
            name = "Rồng Kami",
            intro = "Cùng Rồng Kami ra trận,Công+20%",
            member = "14022001",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [593] = {
            ID = 593,
            name = "Rồng Kami",
            intro = "Cùng Rồng Kami ra trận,Công+20%",
            member = "14022001",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        },
        [594] = {
            ID = 594,
            name = "Phượng Hoàng Kami",
            intro = "Cùng Phượng Hoàng Kami ra trận,Công+20%",
            member = "14022002",
            typeID = 1402,
            APR = 2000,
            HPR = 0,
            DEFR = 0
        }"""

    patch_luac_text(src / "Config" / "PrModel.luac", [
        ("items_count = 572,", "items_count = 594,"),
        (
            """        [572] = {
            ID = 572,
            name = "Thức Hồn",
            intro = "Cùng  ra trận,HP+18%",
            member = "14011618",
            typeID = 1401,
            APR = 0,
            HPR = 1800,
            DEFR = 0
        }""",
            r737_pr_entries,
        ),
    ])

    hpr_map = [
        (12011002, 4, 560, 573, 584),
        (12011003, 4, 561, 574, 585),
        (12011004, 4, 562, 575, 586),
        (12012003, 4, 564, 576, 587),
        (12012004, 4, 563, 577, 588),
        (12012005, 4, 565, 578, 589),
        (12013003, 4, 566, 579, 590),
        (12013004, 4, 567, 580, 591),
        (12013005, 4, 568, 581, 592),
        (12015022, 6, 572, 582, 593),
        (12015023, 6, 570, 583, 594),
    ]
    hpr_patches = []
    for hid, last_order, last_pr, pr_book, pr_horse in hpr_map:
        old_tail = (
            f"            [{last_order}] = {{\n"
            f"                heroModelID = {hid},\n"
            f"                order = {last_order},\n"
            f"                PRModelId = {last_pr}\n"
            f"            }}\n"
            f"        }}"
        )
        new_tail = (
            f"            [{last_order}] = {{\n"
            f"                heroModelID = {hid},\n"
            f"                order = {last_order},\n"
            f"                PRModelId = {last_pr}\n"
            f"            }},\n"
            f"            [7] = {{\n"
            f"                heroModelID = {hid},\n"
            f"                order = 7,\n"
            f"                PRModelId = {pr_book}\n"
            f"            }},\n"
            f"            [8] = {{\n"
            f"                heroModelID = {hid},\n"
            f"                order = 8,\n"
            f"                PRModelId = {pr_horse}\n"
            f"            }}\n"
            f"        }}"
        )
        hpr_patches.append((old_tail, new_tail))
    patch_luac_text(src / "Config" / "HeroPrRelation.luac", hpr_patches)

    patch_luac_text(src / "Config" / "TreasureModel.luac", [
        (
            """            debrisModelIds = {
                15034501,
                15034502,
                15034503,
                15034504,
                15034505,
                15034506
            },
            prHeroModelIds = {}""",
            """            debrisModelIds = {
                15034501,
                15034502,
                15034503,
                15034504,
                15034505,
                15034506
            },
            prHeroModelIds = {
                12011002,
                12011004,
                12012004,
                12013003,
                12013005,
                12015023
            }""",
        ),
        (
            """            debrisModelIds = {
                15034601,
                15034602,
                15034603,
                15034604,
                15034605,
                15034606
            },
            prHeroModelIds = {}""",
            """            debrisModelIds = {
                15034601,
                15034602,
                15034603,
                15034604,
                15034605,
                15034606
            },
            prHeroModelIds = {
                12011003,
                12012003,
                12012005,
                12013004,
                12015022
            }""",
        ),
        (
            """            debrisModelIds = {
                15044701,
                15044702,
                15044703,
                15044704,
                15044705,
                15044706
            },
            prHeroModelIds = {}""",
            """            debrisModelIds = {
                15044701,
                15044702,
                15044703,
                15044704,
                15044705,
                15044706
            },
            prHeroModelIds = {
                12011002,
                12011004,
                12012004,
                12013003,
                12013005,
                12015022
            }""",
        ),
        (
            """            debrisModelIds = {
                15044801,
                15044802,
                15044803,
                15044804,
                15044805,
                15044806
            },
            prHeroModelIds = {}""",
            """            debrisModelIds = {
                15044801,
                15044802,
                15044803,
                15044804,
                15044805,
                15044806
            },
            prHeroModelIds = {
                12011003,
                12012003,
                12012005,
                12013004,
                12015023
            }""",
        ),
    ])

    patch_luac_text(src / "Config" / "TimedRecruitModel.luac", [
        (
            "            goldHeroModelID = 16060037,\n"
            "            receiveBlessNum = 500,\n"
            "            blessNumMax = 500,\n"
            "            startBlessLimit = 600,\n"
            "            firstBless = 320,\n"
            "            firstBlessR = 0.7,\n"
            "            blessOddsR = 0.00014,\n"
            "            limitNum = 500,\n"
            '            btnPic = ""',
            "            goldHeroModelID = 16060037,\n"
            "            receiveBlessNum = 500,\n"
            "            blessNumMax = 500,\n"
            "            startBlessLimit = 600,\n"
            "            firstBless = 320,\n"
            "            firstBlessR = 0.7,\n"
            "            blessOddsR = 0.00014,\n"
            "            limitNum = 500,\n"
            '            btnPic = "sy_157"',
        ),
        (
            "            goldHeroModelID = 16060038,\n"
            "            receiveBlessNum = 500,\n"
            "            blessNumMax = 500,\n"
            "            startBlessLimit = 600,\n"
            "            firstBless = 320,\n"
            "            firstBlessR = 0.7,\n"
            "            blessOddsR = 0.00014,\n"
            "            limitNum = 500,\n"
            '            btnPic = ""',
            "            goldHeroModelID = 16060038,\n"
            "            receiveBlessNum = 500,\n"
            "            blessNumMax = 500,\n"
            "            startBlessLimit = 600,\n"
            "            firstBless = 320,\n"
            "            firstBlessR = 0.7,\n"
            "            blessOddsR = 0.00014,\n"
            "            limitNum = 500,\n"
            '            btnPic = "sy_158"',
        ),
        (
            "            goldHeroModelID = 16060039,\n"
            "            receiveBlessNum = 500,\n"
            "            blessNumMax = 500,\n"
            "            startBlessLimit = 600,\n"
            "            firstBless = 320,\n"
            "            firstBlessR = 0.7,\n"
            "            blessOddsR = 0.00014,\n"
            "            limitNum = 500,\n"
            '            btnPic = ""',
            "            goldHeroModelID = 16060039,\n"
            "            receiveBlessNum = 500,\n"
            "            blessNumMax = 500,\n"
            "            startBlessLimit = 600,\n"
            "            firstBless = 320,\n"
            "            firstBlessR = 0.7,\n"
            "            blessOddsR = 0.00014,\n"
            "            limitNum = 500,\n"
            '            btnPic = "sy_159"',
        ),
    ])

    gor_pics = [
        (16060037, 1, 12011002, "xshd_101"),
        (16060037, 2, 12011003, "xshd_117"),
        (16060037, 3, 12011004, "xshd_100"),
        (16060038, 1, 12012003, "xshd_118"),
        (16060038, 2, 12012004, "xshd_103"),
        (16060038, 3, 12012005, "xshd_98"),
        (16060039, 1, 12013003, "xshd_102"),
        (16060039, 2, 12013004, "xshd_119"),
        (16060039, 3, 12013005, "xshd_99"),
    ]
    gor_patches = []
    for box_id, row_id, hid, pic in gor_pics:
        old_row = (
            f"                goodsOutputOddsCode = {box_id},\n"
            f"                ID = {row_id},\n"
            f"                outputTypeID = 1201,\n"
            f"                outputModelID = {hid},\n"
            f"                outputNum = 1,\n"
            f"                oddsMin = 0,\n"
            f"                oddsMax = 0,\n"
            f'                pic = "",'
        )
        new_row = old_row.replace('pic = "",', f'pic = "{pic}",')
        gor_patches.append((old_row, new_row))
    patch_luac_text(src / "Config" / "GoodsOutputRelation.luac", gor_patches)


def patch_r739_lianti_lua(src: Path) -> None:
    """R7.39: Enable Lianti (5700), expose Lianti stones in ShopGoodsModel, and fix client Lua bugs."""
    patch_luac_text(src / "Config" / "ModuleSubModel.luac", [
        (
            """        [5700] = {
            Id = 5700,
            alias = "Lianti",
            moduleId = 57,
            moduleAlias = "Lianti",
            name = "炼体",
            isClient = 1,
            ifOpen = 0,""",
            """        [5700] = {
            Id = 5700,
            alias = "Lianti",
            moduleId = 57,
            moduleAlias = "Lianti",
            name = "炼体",
            isClient = 1,
            ifOpen = 1,""",
        ),
    ])

    patch_luac_text(src / "Config" / "ShopGoodsModel.luac", [
        ("items_count = 6,", "items_count = 10,"),
        (
            """        [6] = {
            ID = 6,
            serverGroupID = 0,
            goodsModelID = 16050002,
            sellTypeID = 1111,
            initPrice = 100,
            currPrice = 100,
            ifVipLimitBuy = false,
            ifOnceUse = false,
            ifDynamicPrice = false,
            needLV = 1
        }""",
            """        [6] = {
            ID = 6,
            serverGroupID = 0,
            goodsModelID = 16050002,
            sellTypeID = 1111,
            initPrice = 100,
            currPrice = 100,
            ifVipLimitBuy = false,
            ifOnceUse = false,
            ifDynamicPrice = false,
            needLV = 1
        },
        [7] = {
            ID = 7,
            serverGroupID = 0,
            goodsModelID = 16050035,
            sellTypeID = 1111,
            initPrice = 10,
            currPrice = 10,
            ifVipLimitBuy = false,
            ifOnceUse = false,
            ifDynamicPrice = false,
            needLV = 34
        },
        [8] = {
            ID = 8,
            serverGroupID = 0,
            goodsModelID = 16050036,
            sellTypeID = 1111,
            initPrice = 25,
            currPrice = 25,
            ifVipLimitBuy = false,
            ifOnceUse = false,
            ifDynamicPrice = false,
            needLV = 34
        },
        [9] = {
            ID = 9,
            serverGroupID = 0,
            goodsModelID = 16050037,
            sellTypeID = 1111,
            initPrice = 60,
            currPrice = 60,
            ifVipLimitBuy = false,
            ifOnceUse = false,
            ifDynamicPrice = false,
            needLV = 34
        },
        [10] = {
            ID = 10,
            serverGroupID = 0,
            goodsModelID = 16050038,
            sellTypeID = 1111,
            initPrice = 200,
            currPrice = 200,
            ifVipLimitBuy = false,
            ifOnceUse = false,
            ifDynamicPrice = false,
            needLV = 34
        }""",
        ),
    ])

    patch_luac_text(src / "Formation" / "PlayerFormationLayer.luac", [
        (
            """    --if NetworkResData:modulePlayerIsOpen(ModuleSub.eLianti) and self.mIsMyself then
    --    --炼体
    --    table.insert(tabList, {text = TR("炼体"), tag = ModuleSub.eLianti, x = self.mSoltCellSize.width * 0.77, y = self.mSoltCellSize.height})
    --end""",
            """    if NetworkResData:modulePlayerIsOpen(ModuleSub.eLianti) and NetworkResData:moduleIsOpenInServer(ModuleSub.eLianti) and self.mIsMyself then
        --炼体
        table.insert(tabList, {text = TR("炼体"), tag = ModuleSub.eLianti, x = self.mSoltCellSize.width * 0.77, y = self.mSoltCellSize.height})
    end""",
        ),
        (
            """    local refrehFunc = function(noAction, isNewNode)
        local currentLv = currentHero.LiantiLv
        local currentLayer = currentHero.LianTiNodeId    --（正在点星的节点）

        --提示语
        --local gailv = currentHero.LvUpExp > 0 and (currentHero.LianTiNodeExp / currentHero.LvUpExp  * 100) or 0
        --local tempGaiLv = { oddsMin = 0, des = TR("极低概率") }
        --for i,v in pairs(LiantiOddsDesRelation.items) do
        --    if gailv > v.oddsMin and tempGaiLv.oddsMin < v.oddsMin then
        --        tempGaiLv = v
        --    end
        --end
        tishiLabel:setString(TR("灵力每日 {6cff00}24:00 {ffffff}清零"))
        --5个属性进度条
        for i,v in pairs(progressBarList) do
            local curV = 0
            local maxV = 0
            if i < currentHero.LianTiNodeId then
                curV = v:getMaxValue()
                maxV = v:getMaxValue()
            elseif i > currentHero.LianTiNodeId then
                curV = 0
                maxV = 100
            else
                curV = currentHero.LianTiNodeExp
                maxV = currentHero.LvUpExp

                --正在燃烧的动画
                local createFire = function()
                    self.mFireeffect = ui.newEffect({
                        parent = v,
                        effectName = "effect_ui_lianti",
                        animation = aimationlist[i],
                        position = cc.p(30, 30),
                        scale = 0.8,
                        loop = true,
                        startListener = function()
                        end,
                        completeListener = function()
                        end
                    })
                    self.mFireeffect:setLocalZOrder(-1)
                end
                if not self.mFireeffect then
                    createFire()
                else
                    if isNewNode then
                        self.mFireeffect:removeFromParent()
                        self.mFireeffect = nil
                        createFire()
                    end
                end
            end
            v:setMaxValue(maxV)
            v:setCurrValue(curV,noAction)
        end
        --属性lable
        currentAttr:setString(LiantiModel.items[currentLayer].fightattrName..": {fbfe00}+".. LiantiLvRelation.items[currentLv][attrList[currentLayer]])

        local nextString
        if not LiantiLvRelation.items[currentLv + 1] then
            nextString = TR("炼体等级已满！")
        else
            nextString = LiantiModel.items[currentLayer].fightattrName..": {fbfe00}+".. LiantiLvRelation.items[currentLv + 1][attrList[currentLayer]]
        end
        nextAttr:setString(nextString)
        --当前等级
        currentLvLabel:setString("Lv: "..tostring(currentLv))
        nextLvLabel:setString("Lv: "..tostring(currentLv + 1))
        --刷新金币钻石
        self:refreshPlayerAttrs()


    end""",
            """    local function isLiantiMaxLv(lv)
        local curRow = LiantiLvRelation.items[lv]
        return (not LiantiLvRelation.items[lv + 1]) or (curRow and curRow.lvExp == 0)
    end

    local refrehFunc = function(noAction, isNewNode)
        local currentLv = currentHero.LiantiLv or 0
        local currentLayer = currentHero.LianTiNodeId or 1
        local curExp = currentHero.LianTiNodeExp or 0
        local maxExp = (currentHero.LvUpExp and currentHero.LvUpExp > 0) and currentHero.LvUpExp or 100
        local isMaxLv = isLiantiMaxLv(currentLv)

        tishiLabel:setString(TR("灵力每日 {6cff00}24:00 {ffffff}清零"))
        for i,v in ipairs(progressBarList) do
            local curV = 0
            local maxV = 0
            if isMaxLv then
                curV = 100
                maxV = 100
            elseif i < currentLayer then
                curV = v:getMaxValue()
                maxV = v:getMaxValue()
            elseif i > currentLayer then
                curV = 0
                maxV = 100
            else
                curV = curExp
                maxV = maxExp

                local createFire = function()
                    self.mFireeffect = ui.newEffect({
                        parent = v,
                        effectName = "effect_ui_lianti",
                        animation = aimationlist[i],
                        position = cc.p(30, 30),
                        scale = 0.8,
                        loop = true,
                        startListener = function()
                        end,
                        completeListener = function()
                        end
                    })
                    self.mFireeffect:setLocalZOrder(-1)
                end
                if not self.mFireeffect then
                    createFire()
                else
                    if isNewNode then
                        self.mFireeffect:removeFromParent()
                        self.mFireeffect = nil
                        createFire()
                    end
                end
            end
            v:setMaxValue(maxV)
            v:setCurrValue(curV,noAction)
        end
        local curAttrRow = LiantiLvRelation.items[currentLv] or LiantiLvRelation.items[0]
        local curAttrVal = (curAttrRow and curAttrRow[attrList[currentLayer]]) or 0
        currentAttr:setString(LiantiModel.items[currentLayer].fightattrName..": {fbfe00}+".. curAttrVal)

        local nextString
        if isMaxLv then
            nextString = TR("炼体等级已满！")
            nextLvLabel:setString("MAX")
        else
            nextString = LiantiModel.items[currentLayer].fightattrName..": {fbfe00}+".. LiantiLvRelation.items[currentLv + 1][attrList[currentLayer]]
            nextLvLabel:setString("Lv: "..tostring(currentLv + 1))
        end
        nextAttr:setString(nextString)
        currentLvLabel:setString("Lv: "..tostring(currentLv))
        self:refreshPlayerAttrs()
    end""",
        ),
        (
            """    --经验增加的飘窗
    local piaochuang = function(par, position, value)
        if value == 0 then
            return
        end""",
            """    --经验增加的飘窗
    local piaochuang = function(par, position, value)
        if not value or value <= 0 then
            return
        end""",
        ),
        (
            """                if currentHero.LianTiNodeId == heroValue.LianTiNodeId then
                    piaochuang(card,cc.p(50,70), heroValue.LianTiNodeExp - currentHero.LianTiNodeExp)
                    refreshDataAndUi()""",
            """                if currentHero.LiantiLv == heroValue.LiantiLv and currentHero.LianTiNodeId == heroValue.LianTiNodeId then
                    piaochuang(card,cc.p(50,70), heroValue.LianTiNodeExp - currentHero.LianTiNodeExp)
                    refreshDataAndUi()""",
        ),
        (
            """                if NetworkResData:getPlayerAttr(tonumber(xiaohaoTemple[1])) < tonumber(xiaohaoTemple[3]) then
                    showGoldNotEnough()
                    return
                end
                LoadingWait:begin(self)
                HttpRequest("Lianti","Lianti", {tempSlot, v.goodsModelId}, responseFunc)
            end
        end,
        onLongClickCallBack = function ( ... )
            local exp = math.random(v.expMin, v.expMax)""",
            """                if isLiantiMaxLv(currentHero.LiantiLv or 0) then
                    ui.showFlashView({parent = self, text = TR("炼体等级已满！")})
                    return
                end
                if NetworkResData:getPlayerAttr(tonumber(xiaohaoTemple[1])) < tonumber(xiaohaoTemple[3]) then
                    showGoldNotEnough()
                    return
                end
                LoadingWait:begin(self)
                HttpRequest("Lianti","Lianti", {tempSlot, v.goodsModelId}, responseFunc)
            end
        end,
        onLongClickCallBack = function ( ... )
            if isLiantiMaxLv(currentHero.LiantiLv or 0) or (currentHero.LvUpExp or 0) <= 0 then
                card:stopTimer()
                return
            end
            local exp = math.random(v.expMin, v.expMax)""",
        ),
        (
            """        clickAction = function()
            LoadingWait:begin(self)
            HttpRequest("Lianti","OneKeyFiveLvLianti", {tempSlot},function(event)""",
            """        clickAction = function()
            if isLiantiMaxLv(currentHero.LiantiLv or 0) then
                ui.showFlashView({parent = self, text = TR("炼体等级已满！")})
                return
            end
            LoadingWait:begin(self)
            HttpRequest("Lianti","OneKeyFiveLvLianti", {tempSlot},function(event)""",
        ),
    ])

    patch_luac_text(src / "Hero" / "LianHunDaShiLayer.luac", [
        (
            """    -- 
    --讨论 0 级的情况 
    if self.mRecentLevel == 0 then
            self:setRecentlevelUI(self.mRecentLevel,nil,nil)
            for k,v in pairs(mLianhudashi) do
                if self.mRecentLevel + 1 == v.liantiDashiStep then
                    self:setnextLevelUI(mLianhudashi[self.mRecentLevel + 1].needLiantiLv,mLianhudashi[self.mRecentLevel + 1].DAMADDR,mLianhudashi[self.mRecentLevel + 1].DAMCUTR)
                end
                break
            end
    else
        for k,v in pairs(mLianhudashi) do
            if self.mRecentLevel == v.liantiDashiStep and self.mRecentLevel < #mLianhudashi + 1 then
                    self:setRecentlevelUI(self.mRecentLevel,v.DAMADDR,v.DAMCUTR)
                if self.mRecentLevel  < #mLianhudashi then
                    self:setnextLevelUI(mLianhudashi[self.mRecentLevel + 1].needLiantiLv,mLianhudashi[self.mRecentLevel + 1].DAMADDR,mLianhudashi[self.mRecentLevel + 1].DAMCUTR)
                elseif  self.mRecentLevel == #mLianhudashi then
                     local title6= ui.newLabel{
                        text = TR("已达到最高等级"),
                        size = 28,
                        color = ColorList.ccBlack,
                        needShadow = true,
                        shadowColor = ColorList.ccWhite,
                    }
                    title6:setPosition(250, 180)
                    self.mBgSprite:addChild(title6)
                end
                break
            end
        end

    end""",
            """    if self.mRecentLevel == 0 then
        self:setRecentlevelUI(self.mRecentLevel,nil,nil)
        for _,v in ipairs(mLianhudashi) do
            if self.mRecentLevel + 1 == v.liantiDashiStep then
                self:setnextLevelUI(v.needLiantiLv,v.DAMADDR,v.DAMCUTR)
                break
            end
        end
    else
        for _,v in ipairs(mLianhudashi) do
            if self.mRecentLevel == v.liantiDashiStep then
                self:setRecentlevelUI(self.mRecentLevel,v.DAMADDR,v.DAMCUTR)
                if self.mRecentLevel < #mLianhudashi then
                    local nextRow = mLianhudashi[self.mRecentLevel + 1]
                    self:setnextLevelUI(nextRow.needLiantiLv,nextRow.DAMADDR,nextRow.DAMCUTR)
                else
                    local title6= ui.newLabel{
                        text = TR("已达到最高等级"),
                        size = 28,
                        color = ColorList.ccBlack,
                        needShadow = true,
                        shadowColor = ColorList.ccWhite,
                    }
                    title6:setPosition(250, 180)
                    self.mBgSprite:addChild(title6)
                end
                break
            end
        end
    end""",
        ),
        (
            """    for i,v in pairs(heroList) do
        --下面对于字符字符数大于5的字符串修改字体大小
        local fontsize = nil
        local strCnt = string.asciilen(HeroModel.items[v.HeroModelId].name)""",
            """    for i,v in pairs(heroList) do
        local hero = v and v.HeroId and NetworkResData:getHero(v.HeroId)
        if v and v.HeroModelId and HeroModel.items[v.HeroModelId] and hero then
        --下面对于字符字符数大于5的字符串修改字体大小
        local fontsize = nil
        local strCnt = string.asciilen(HeroModel.items[v.HeroModelId].name)""",
        ),
        (
            """        local hero = NetworkResData:getHero(v.HeroId)
        for k,v in pairs(mLianhudashi) do
            if self.mRecentLevel == 0 then
                 --创建进度条
                local progressBar = require("Common.ProgressBar").new({
                    barImage    = "sy_50.png",
                    bgImage     = "zdjs_11.png",
                    currValue   = hero.LiantiLv,
                    maxValue    = mLianhudashi[self.mRecentLevel + 1].needLiantiLv,
                    barType     = ProgressBarType.eHorizontal,
                    needLabel   = true,
                    font = _FONT_TITLE,
                    color = ColorList.ccWhite,
                    needOutline = true,
                    needShadow = true,
                    size = 24,
                })
                progressBar:setScaleX(0.7)
                progressBar:setPosition(progressBarPosList[i])
                self.mBgSprite:addChild(progressBar)
                break
            elseif self.mRecentLevel == v.liantiDashiStep then
                --创建进度条
                local progressBar = require("Common.ProgressBar").new({
                    barImage    = "sy_50.png",
                    bgImage     = "zdjs_11.png",
                    currValue   = hero.LiantiLv,
                    maxValue    = mLianhudashi[self.mRecentLevel + 1].needLiantiLv,
                    barType     = ProgressBarType.eHorizontal,
                    needLabel   = true,
                    font = _FONT_TITLE,
                    color = ColorList.ccWhite,
                    needOutline = true,
                    needShadow = true,
                    size = 24,
                })
                progressBar:setScaleX(0.7)
                progressBar:setPosition(progressBarPosList[i])
                self.mBgSprite:addChild(progressBar)
                break
            --讨论满级的情况
            elseif self.mRecentLevel == #mLianhudashi then
                local maxLevelLabel= ui.newLabel{
                    text =TR("已达到最高等级"),
                    size = 24,
                    --needShadow = true,
                    color = ColorList.ccWhite,
                }
                maxLevelLabel:setPosition(progressBarPosList[i])
                self.mBgSprite:addChild(maxLevelLabel)
                break
            end   
            
        end
    end""",
            """        if self.mRecentLevel >= #mLianhudashi or not mLianhudashi[self.mRecentLevel + 1] then
            local maxLevelLabel = ui.newLabel{
                text = TR("已达到最高等级"),
                size = 24,
                color = ColorList.ccWhite,
            }
            maxLevelLabel:setPosition(progressBarPosList[i])
            self.mBgSprite:addChild(maxLevelLabel)
        else
            local progressBar = require("Common.ProgressBar").new({
                barImage    = "sy_50.png",
                bgImage     = "zdjs_11.png",
                currValue   = hero.LiantiLv or 0,
                maxValue    = mLianhudashi[self.mRecentLevel + 1].needLiantiLv,
                barType     = ProgressBarType.eHorizontal,
                needLabel   = true,
                font = _FONT_TITLE,
                color = ColorList.ccWhite,
                needOutline = true,
                needShadow = true,
                size = 24,
            })
            progressBar:setScaleX(0.7)
            progressBar:setPosition(progressBarPosList[i])
            self.mBgSprite:addChild(progressBar)
        end
        end
    end""",
        ),
        (
            """function LianHunDaShiLayer:getRecentliantiLevel()
    local heroList = NetworkResData:getFormationInfo().SlotInfos
    for k,v in pairs(mLianhudashi) do
        local cnt = 0
        local maxLevelCnt = 0
        for m,n in pairs(heroList) do
            local hero = NetworkResData:getHero(n.HeroId)
            if hero and self:getMinLianLv() < v.needLiantiLv then
                    return k - 1
            --讨论满级的情况
            elseif hero and hero.LiantiLv == mLianhudashi[#mLianhudashi].needLiantiLv then
                    maxLevelCnt = maxLevelCnt + 1
            end
        end
        --讨论0级的情况
        --不满足6人上阵返回0级
        if #heroList < 6 then
            return 0
        --讨论满级
        elseif maxLevelCnt == #heroList then
            return #mLianhudashi
        end
        

    end
end

function LianHunDaShiLayer:getMinLianLv()
    local heroList = NetworkResData:getFormationInfo().SlotInfos
    local minLianTi =  NetworkResData:getHero(heroList[1].HeroId)
    local minLianLv = minLianTi.LiantiLv
    for m,n in pairs(heroList) do
        local hero = NetworkResData:getHero(n.HeroId)
        if not hero then
            minLianLv = 0
        end
        if hero.LiantiLv < minLianLv then
            minLianLv = hero.LiantiLv
        end
    end
    return minLianLv
end""",
            """function LianHunDaShiLayer:getRecentliantiLevel()
    local heroList = NetworkResData:getFormationInfo().SlotInfos or {}
    local deployedCnt = 0
    for _, n in pairs(heroList) do
        if n and n.HeroId and NetworkResData:getHero(n.HeroId) then
            deployedCnt = deployedCnt + 1
        end
    end
    if deployedCnt < 6 then
        return 0
    end
    local minLv = self:getMinLianLv()
    local step = 0
    for _, v in ipairs(mLianhudashi) do
        if minLv >= v.needLiantiLv then
            step = v.liantiDashiStep
        end
    end
    return step
end

function LianHunDaShiLayer:getMinLianLv()
    local heroList = NetworkResData:getFormationInfo().SlotInfos or {}
    local minLianLv = nil
    for _, n in pairs(heroList) do
        local hero = n and n.HeroId and NetworkResData:getHero(n.HeroId)
        if not hero then
            return 0
        end
        local lv = hero.LiantiLv or 0
        if not minLianLv or lv < minLianLv then
            minLianLv = lv
        end
    end
    return minLianLv or 0
end""",
        ),
    ])



def patch_r740_pvpinter_lua(src: Path) -> None:
    """R7.40: Unlock PVPinter (6100) + WhosTheGod (6200) and fix 7 Challenge Lua compatibility bugs."""
    patch_luac_text(src / "Challenge" / "ChallengeListLayer.luac", [
        (
            """    --[[local isOpen = NetworkResData:moduleIsOpenInServer(ModuleSub.ePVPInter)
    if isOpen then
       table.insert(self.mListItemInfo,{
            -- 跨服战
            normalImage = "tz_7.png",
            title = TR("跨服战"),
            intro = TR("参加跨服排位赛获得积分兑换奖品"),
            moduleId = ModuleSub.ePVPInter,""",
            """    local isOpen = NetworkResData:moduleIsOpenInServer(ModuleSub.ePVPInter)
    if isOpen then
       table.insert(self.mListItemInfo,{
            -- 跨服战
            normalImage = "tz_7.png",
            title = TR("跨服战"),
            intro = TR("参加跨服排位赛获得积分兑换奖品"),
            muduleId = ModuleSub.ePVPInter,""",
        ),
        (
            """        })
    end
    --]]""",
            """        })
    end""",
        ),
    ])

    patch_luac_text(src / "Challenge" / "CrossServerBattleScene.luac", [
        (
            """local DanType = {
    eBronze     = 21,    -- 青铜
    eSliver     = 22,    -- 白银
    eGold       = 23,    -- 黄金
    ePt         = 24,    -- 铂金
    eDiamond    = 25,    -- 钻石
    eMaster     = 26,    -- 大师
    eKing       = 27,    -- 王者
    eMostKing   = 100,    -- 最强王者
}""",
            """local DanType = {
    eBronze     = 1,    -- 半妖
    eSliver     = 2,    -- 顽妖
    eGold       = 3,    -- 强妖
    ePt         = 4,    -- 妖将
    eDiamond    = 5,    -- 妖王
    eMaster     = 6,    -- 大妖
    eKing       = 7,    -- 修影
    eMostKing   = 8,    -- 天照
}""",
        ),
        (
            """-- 根据段位和图片类型获取文件名
function CrossServerBattleScene:getFileNameByDanType( type , dan)
    if type == DanImgType.eBox then
        return PvpinterLvRelation.items[dan].rankHeadFrame
    elseif type == DanImgType.eMark then
        return string.format("kfpw_%d.png",dan == 100 and 8 or dan - 20 )
    elseif type == DanImgType.eTitle then
        --return string.format("kfpw_%d.png",dan == 100 and 31 or dan + 3)
    end
    return ""
end

-- 积分转换为胜点
function CrossServerBattleScene:rateConvertToVictor( rate,lv )
    -- body
    local needRating = PvpinterLvRelation.items[lv].needRating
    local k = PvpinterConfig.items[1].exchangeRate

    return math.floor(0.5 + (rate - needRating) / k)
end""",
            """-- 根据段位和图片类型获取文件名
function CrossServerBattleScene:getFileNameByDanType( type , dan)
    local d = math.max(1, math.min(8, tonumber(dan) or 1))
    if type == DanImgType.eBox then
        return (PvpinterLvRelation.items[d] or PvpinterLvRelation.items[1]).rankHeadFrame
    elseif type == DanImgType.eMark then
        return string.format("kfpw_%d.png", d)
    elseif type == DanImgType.eTitle then
    end
    return ""
end

-- 积分转换为胜点
function CrossServerBattleScene:rateConvertToVictor( rate,lv )
    local curLv = math.max(1, tonumber(lv) or 1)
    local prevNeed = (curLv > 1 and PvpinterLvRelation.items[curLv - 1]) and PvpinterLvRelation.items[curLv - 1].needRating or 0
    local k = math.max(1, tonumber(PvpinterConfig.items[1].exchangeRate) or 1)
    return math.max(0, math.floor(0.5 + ((tonumber(rate) or 0) - prevNeed) / k))
end""",
        ),
        (
            """    -- 段位
    local dan = PVPinterInfo and PVPinterInfo.Lv or DanType.eKing

    if dan == 0 or dan == DanType.eBronze then
        LVCHA = PvpinterLvRelation.items[dan].needRating
    elseif dan < DanType.eMaster then
        LVCHA = PvpinterLvRelation.items[dan].needRating - PvpinterLvRelation.items[dan - 1].needRating
    else
        LVCHA = PvpinterLvRelation.items[dan].needRating
    end""",
            """    -- 段位
    local dan = math.max(1, math.min(8, (PVPinterInfo and tonumber(PVPinterInfo.Lv) and PVPinterInfo.Lv > 0) and PVPinterInfo.Lv or DanType.eBronze))

    if dan <= DanType.eBronze then
        LVCHA = PvpinterLvRelation.items[1].needRating
    elseif dan < DanType.eMaster then
        LVCHA = PvpinterLvRelation.items[dan].needRating - PvpinterLvRelation.items[dan - 1].needRating
    else
        LVCHA = PvpinterLvRelation.items[dan].needRating
    end""",
        ),
        (
            "        for i,v in ipairs(AnalysisStrResList(PvpinterLvRelation.items[PVPinterInfo.Lv].rankRewards)) do",
            "        local curLvRow = PvpinterLvRelation.items[PVPinterInfo.Lv] or PvpinterLvRelation.items[1]\n"
            '        local curRewStr = (curLvRow.lvUpRewardsFirst and curLvRow.lvUpRewardsFirst ~= "" and curLvRow.lvUpRewardsFirst) or curLvRow.victoryRewards\n'
            "        for i,v in ipairs(AnalysisStrResList(curRewStr)) do",
        ),
        (
            '            text = formatTime(data.Crdate - NetworkResData:getCurrentTime())..TR("前"),',
            '            text = formatTime(math.max(0, NetworkResData:getCurrentTime() - (data.Crdate or 0)))..TR("前"),',
        ),
        (
            "    local upgradeData = PvpinterLvRelation.items[PVPinterInfo.Lv + 1]",
            "    local upgradeData = PvpinterLvRelation.items[PVPinterInfo.Lv + 1] or PvpinterLvRelation.items[PVPinterInfo.Lv]",
        ),
        (
            "    if val.PVPinterFightLog then\n        table.insert(selfData.mBattleRecordList,1,val.PVPinterFightLog)",
            "    if val.PVPinterFightLog then\n        selfData.mBattleRecordList = selfData.mBattleRecordList or {}\n        table.insert(selfData.mBattleRecordList,1,val.PVPinterFightLog)",
        ),
        (
            """                if selfData.mIsSucess == 2 then
                    battleStatus.win = 2
                    battleStatus.lose = selfData.mTotalUpGrade - 2
                elseif selfData.mIsSucess == 1 then
                    battleStatus.lose = 2
                    battleStatus.win = selfData.mTotalUpGrade - 2
                end""",
            """                if selfData.mIsSucess == 2 then
                    battleStatus.win = 2
                    battleStatus.lose = math.max(0, selfData.mTotalUpGrade - 2)
                elseif selfData.mIsSucess == 1 then
                    battleStatus.lose = 2
                    battleStatus.win = math.max(0, selfData.mTotalUpGrade - 2)
                end""",
        ),
        (
            "    local limitTimes = VipModel.items[NetworkResData:getPlayerInfo().Vip].buyKuafuNum",
            """    local vipLv = tonumber(NetworkResData:getPlayerInfo().Vip or 0) or 0
    local rawLimit = tonumber(VipModel.items[vipLv] and VipModel.items[vipLv].buyKuafuNum or 0) or 0
    local limitTimes = (rawLimit > 0) and rawLimit or (vipLv + 3)""",
        ),
    ])

    patch_luac_text(src / "Challenge" / "CrossServerRankLayer.luac", [
        (
            """            -- 段位框
            tempSprite = ui.newSprite(string.format("kfpw_%02d.png",tempData.PVPInterLv - 12))
            tempSprite:setPosition(cc.p(tempCard:getContentSize().width / 2,tempCard:getContentSize().height / 2 + 10))
            tempCard:addChild(tempSprite)

            -- 段位
            tempLabel = ui.newLabel({
                text = PvpinterLvRelation.items[tempData.PVPInterLv].name,
                font = _FONT_PANGWA,
                color = ColorList.ccGold,
                size = 24,
                needOutLine = true,
            })""",
            """            local lvRow = PvpinterLvRelation.items[tempData.PVPInterLv or 1] or PvpinterLvRelation.items[1]
            -- 段位框
            tempSprite = ui.newSprite(lvRow.rankHeadFrame)
            tempSprite:setPosition(cc.p(tempCard:getContentSize().width / 2,tempCard:getContentSize().height / 2 + 10))
            tempCard:addChild(tempSprite)

            -- 段位
            tempLabel = ui.newLabel({
                text = lvRow.name,
                font = _FONT_PANGWA,
                color = ColorList.ccGold,
                size = 24,
                needOutLine = true,
            })""",
        ),
        (
            "            totalPage = retVal.Value.TotalPage or 1",
            "            totalPage = retVal.Value.TotalPage or 0",
        ),
        (
            """            local tempLayer = require("Formation.PlayerFormationLayer").new({
                isMyself = false,                           -- 是不是玩家自己
                formationInfo = retVal.Value,               -- 阵容信息
                battleSkills = retVal.Value.SkillInfos,     -- 上阵的主角技能
                combatPet = retVal.Value.CombatPet,
                playerLv = playerLv,                        -- 玩家等级
            })""",
            """            local fInfo = retVal.Value.Formation or retVal.Value
            local tempLayer = require("Formation.PlayerFormationLayer").new({
                isMyself = false,
                formationInfo = fInfo,
                battleSkills = fInfo.SkillInfos,
                combatPet = fInfo.CombatPet,
                playerLv = (fInfo.PlayerInfo and fInfo.PlayerInfo.Lv) or playerLv,
            })""",
        ),
    ])

    patch_luac_text(src / "Challenge" / "CrossServerRewardLayer.luac", [
        (
            "    self.mLevel = pargrams and pargrams.level or 21     --由于表结构问题，定死21为青铜等级",
            "    self.mLevel = (pargrams and pargrams.level and PvpinterLvRelation.items[pargrams.level]) and pargrams.level or 1",
        ),
        (
            """    local bgImage = {
        [21] = {bg = "kfpw_28.png", hero = "kfpw_1.png"},
        [22] = {bg = "kfpw_29.png", hero = "kfpw_2.png"},
        [23] = {bg = "kfpw_30.png", hero = "kfpw_3.png"},
        [24] = {bg = "kfpw_31.png", hero = "kfpw_4.png"},
        [25] = {bg = "kfpw_32.png", hero = "kfpw_5.png"},
        [26] = {bg = "kfpw_33.png", hero = "kfpw_6.png"},
        [27] = {bg = "kfpw_34.png", hero = "kfpw_7.png"},
        [100] = {bg = "kfpw_35.png", hero = "kfpw_8.png"},
    }""",
            """    local bgImage = {
        [1] = {bg = "kfpw_28.png", hero = "kfpw_1.png"},
        [2] = {bg = "kfpw_29.png", hero = "kfpw_2.png"},
        [3] = {bg = "kfpw_30.png", hero = "kfpw_3.png"},
        [4] = {bg = "kfpw_31.png", hero = "kfpw_4.png"},
        [5] = {bg = "kfpw_32.png", hero = "kfpw_5.png"},
        [6] = {bg = "kfpw_33.png", hero = "kfpw_6.png"},
        [7] = {bg = "kfpw_34.png", hero = "kfpw_7.png"},
        [8] = {bg = "kfpw_35.png", hero = "kfpw_8.png"},
    }""",
        ),
        (
            '        local tempGood = splitStrBySep(v.rankRewards,"||")',
            '        local rewStr = (v.lvUpRewardsFirst and v.lvUpRewardsFirst ~= "" and v.lvUpRewardsFirst) or v.victoryRewards\n'
            '        local tempGood = splitStrBySep(rewStr,"||")',
        ),
    ])

    patch_luac_text(src / "Challenge" / "CrossServerBlanceLayer.luac", [
        (
            """    self.mLevel = pragrams and pragrams.level or 21
    self.mUp = pragrams.isUp
    self.mLevelImage = {
        [21] = "kfpw_1.png",
        [22] = "kfpw_2.png",
        [23] = "kfpw_3.png",
        [24] = "kfpw_4.png",
        [25] = "kfpw_5.png",
        [26] = "kfpw_6.png",
        [27] = "kfpw_7.png",
        [100] = "kfpw_8.png",
    }""",
            """    self.mLevel = (pragrams and pragrams.level and PvpinterLvRelation.items[pragrams.level]) and pragrams.level or 1
    self.mUp = pragrams.isUp
    self.mLevelImage = {
        [1] = "kfpw_1.png",
        [2] = "kfpw_2.png",
        [3] = "kfpw_3.png",
        [4] = "kfpw_4.png",
        [5] = "kfpw_5.png",
        [6] = "kfpw_6.png",
        [7] = "kfpw_7.png",
        [8] = "kfpw_8.png",
    }""",
        ),
        (
            "    local levelSprite = cc.Sprite:create(self.mLevelImage[self.mLevel])",
            '    local levelSprite = cc.Sprite:create(self.mLevelImage[self.mLevel] or "kfpw_1.png")',
        ),
    ])

    patch_luac_text(src / "Challenge" / "CrossServerShopLayer.luac", [
        (
            "    self.mLevel = pargrams and pargrams.level or 21     --由于表结构问题，定死21为青铜等级",
            "    self.mLevel = (pargrams and pargrams.level and PvpinterLvRelation.items[pargrams.level]) and pargrams.level or 1",
        ),
        (
            """        local goods = goodTemple[tonumber(tempData[2])]

        --头像
        local card = createCardNode({resourceTypeSub = tonumber(tempData[1]), modelId = tonumber(tempData[2]), cardShowAttrs = {CardShowAttr.eBorder}, isTouch = true})
        bgSprite:addChild(card)
        card:setPosition(cc.p(60,65))

        --名字
        local namelabel = ui.newLabel({
            text = goods.name,
            font = _FONT_PANGWA,
            size = 24,
            needOutLine = true
        })
        namelabel:setPosition(cc.p(120, 95))
        namelabel:setColor(GetColorByQuality(goods.quality, 1))""",
            """        local resType = tonumber(tempData[1])
        local resModel = tonumber(tempData[2]) or 0
        local resNum = tonumber(tempData[3]) or 1
        local goods = (resModel > 0) and goodTemple[resModel] or nil
        local itemName = (goods and goods.name) or (resType == 1128 and "Đá Cảm Ngộ") or (ResourcetypeSubName and ResourcetypeSubName[resType]) or ""
        local itemQuality = (goods and goods.quality) or 15
        local lvInfo = PvpinterLvRelation.items[self.mLevel] or PvpinterLvRelation.items[1]
        local saleRate = (v.isSale == 1 and lvInfo and tonumber(lvInfo.sale)) or 1
        local actualCost = math.max(1, math.floor((tonumber(useData[3]) or 0) * saleRate))

        --头像
        local card = createCardNode({resourceTypeSub = resType, modelId = resModel, num = resNum, cardShowAttrs = {CardShowAttr.eBorder, CardShowAttr.eNum}, isTouch = true})
        bgSprite:addChild(card)
        card:setPosition(cc.p(60,65))

        --名字
        local namelabel = ui.newLabel({
            text = itemName,
            font = _FONT_PANGWA,
            size = 24,
            needOutLine = true
        })
        namelabel:setPosition(cc.p(120, 95))
        namelabel:setColor(GetColorByQuality(itemQuality, 1))""",
        ),
        (
            '        local needlabel = ui.newLabel({\n            text = string.format(TR("{000000}消耗:{db_50062.png} {750721}X%s"), useData[3]),',
            '        local needlabel = ui.newLabel({\n            text = string.format(TR("{000000}消耗:{db_50062.png} {750721}X%d"), actualCost),',
        ),
        (
            "                            if self.mMedal < tonumber(useData[3]) then",
            "                            if self.mMedal < actualCost then",
        ),
        (
            "        if (self.mMedal < tonumber(useData[3])) or (self.mLevel < v.needPVPInteLv) or isFull then",
            "        if (self.mMedal < actualCost) or (self.mLevel < v.needPVPInteLv) or isFull then",
        ),
    ])

    patch_luac_text(src / "Challenge" / "CSBSecondScene.luac", [
        (
            """    local function createCheckOrGuessButton( data,parent,stage,position )
        local clickCallback = nil
        local textStr = TR("查看")
        local isVisible = true
        if self.mCurBattleStage == stage then
            if not isGuessSomeStage(self.mCurStageType) then
                textStr = TR("竞猜")
                clickCallback = function ( ... )
                    self:createGuessLayer(data)
                end
            else
                isVisible = false
            end
        else
            clickCallback = function ( ... )
                self:createBattleRecordLayer(data,false)
            end
        end

        if isVisible then
            local guessButton = ui.newButton({
                normalImage = "c_8.png",
                text = textStr,
                scale = 0.8,
                position = position,--cc.p(cellSize.width * 0.5,cellSize.height * 0.15),
                clickAction = clickCallback,
            })
            parent:addChild(guessButton)
        end
    end""",
            """    local function createCheckOrGuessButton( data,parent,stage,position )
        local canGuess = (stage >= StageType.eStage_2) and (not isGuessSomeStage(stage))
        local watchPos = canGuess and cc.p(position.x - 52, position.y) or position
        local watchButton = ui.newButton({
            normalImage = "c_8.png",
            text = TR("查看"),
            scale = 0.78,
            position = watchPos,
            clickAction = function()
                self:createBattleRecordLayer(data, false)
            end,
        })
        parent:addChild(watchButton)
        if canGuess then
            local guessButton = ui.newButton({
                normalImage = "c_7.png",
                text = TR("竞猜"),
                scale = 0.78,
                position = cc.p(position.x + 52, position.y),
                clickAction = function()
                    self:createGuessLayer(data)
                end,
            })
            parent:addChild(guessButton)
        end
    end""",
        ),
        (
            "                    winSprite:setPosition(cc.p(i == 1 and 80 or -80,250))",
            "                    winSprite:setPosition(cc.p(k == 1 and 80 or -80,250))",
        ),
        (
            "        local worshipUse = AnalysisStrResList(PvpinterTopConfig.items[1].worshipUse)",
            '        local worshipUseStr = (PvpinterTopConfig and PvpinterTopConfig.items and PvpinterTopConfig.items[1] and PvpinterTopConfig.items[1].worshipUse) or "1111,0,50"\n'
            "        local worshipUse = AnalysisStrResList(worshipUseStr)",
        ),
        (
            """function CSBSecondScene:requestGuessBattle( type,guid )
    LoadingWait:begin(self)
    HttpRequest("PVPinterTop", "Bet", {type,guid}, function( retVal )
        LoadingWait:ends()
        if retVal and retVal.Status == 0 then
            ui.showFlashView({parent = self,text = TR("下注成功")})
            -- 下注成功后,更新下我的竞猜信息
            table.insert(selfData.guessInfo,retVal.Value.PVPinterTopBetInfo or {})""",
            """function CSBSecondScene:requestGuessBattle( type,guid )
    LoadingWait:begin(self)
    HttpRequest("PVPinterTop", "Bet", {type,guid,self.mCurStageType,self.mCurGroupType}, function( retVal )
        LoadingWait:ends()
        if retVal and retVal.Status == 0 then
            ui.showFlashView({parent = self,text = TR("下注成功")})
            selfData.guessInfo = selfData.guessInfo or {}
            table.insert(selfData.guessInfo,retVal.Value.PVPinterTopBetInfo or {})""",
        ),
        (
            """            selfData.selfBattleReport = retVal.Value.BattleReport
            self:createBattleRecordLayer(selfData.selfBattleReport,true)""",
            """            selfData.selfBattleRecord = retVal.Value.BattleReport or {}
            self:createBattleRecordLayer(selfData.selfBattleRecord,true)""",
        ),
        (
            """            if retVal.Value.FightInfo.ClientRes then
                self:startBattle(retVal.Value.FightInfo.ClientRes,data)
            end""",
            """            local res = retVal.Value.FightInfo and (retVal.Value.FightInfo.ClientRes or retVal.Value.FightInfo)
            if res then
                self:startBattle(res,data)
            end""",
        ),
    ])

    patch_luac_text(src / "Grab" / "TreasureDebrisLayer.luac", [
        (
            """                            --拥有数量
                            local haveCount = ui.newLabel({
                                text = string.format(TR("当前拥有数量:%s"), newTreasureDebris[i].Num),
                                size = 26,
                                needShadow = true
                            })
                            haveCount:setPosition(cc.p(mBgSize.width / 2 , mBgSize.height * 0.16 ))
                            haveCount:setColor(ColorList.ccGreen)
                            BgSprite:addChild(haveCount)
                        end,
                    })""",
            """                            --拥有数量
                            local haveCount = ui.newLabel({
                                text = string.format(TR("当前拥有数量:%s"), newTreasureDebris[i].Num),
                                size = 24,
                                needShadow = true
                            })
                            haveCount:setPosition(cc.p(mBgSize.width * 0.34, mBgSize.height * 0.16))
                            haveCount:setColor(ColorList.ccGreen)
                            BgSprite:addChild(haveCount)

                            local btnHuntMore = ui.newButton({
                                normalImage = "c_7.png",
                                text = "Tầm Bảo Tiếp",
                                fontSize = 18,
                                scale = 0.72,
                                color = ColorList.ccWhite,
                                outlineColor = ColorList.ccOutline,
                                outlineSize = 2,
                                position = cc.p(mBgSize.width * 0.76, mBgSize.height * 0.16),
                                clickAction = function()
                                    if target and not tolua.isnull(target) then
                                        target:removeFromParent()
                                    end
                                    local grabScene = self:getParent():getParent():getParent():getParent()
                                    local onClose = grabScene.mPargrams and grabScene.mPargrams.onCloseCallback
                                    local callFunc = function()
                                        local ttype = TreasureModel.items[treasureModel.ID].typeID
                                        local selectType = (tonumber(ttype) == ResourcetypeSub.eBook) and 2 or 1
                                        game.replaceScene(require("Grab.GrabTreasureScene").new({treasureId = treasureModel.ID, selectType = selectType, onCloseCallback = onClose}), "CCtransitionCrossFade", 0.0)
                                    end
                                    game.replaceScene(require("Grab.GrabListScene").new(treasureModel.ID, debrisID, grabScene:getTime(), callFunc), "CCtransitionCrossFade", 0)
                                end,
                            })
                            BgSprite:addChild(btnHuntMore)
                        end,
                    })""",
        ),
        (
            """    --合成按钮
    self.mComposeBtn = ui.newButton({
        normalImage   = "c_7.png",
        text = TR("合成"),
        fontSize = 30,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            self:requestCompose(treasure.ID)
        end,
        position = cc.p(self.bgSize.width * 0.8, self.bgSize.height * 0.17),
    })
    node:addChild(self.mComposeBtn)


    --一键抢夺按钮
    local oneKeyButton = ui.newButton({
        normalImage   = "db_10.png",
        text = TR("一键寻宝"),
        fontSize = 22,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            require("Config.StaConfig")
             local isOpen, retInfo = NetworkResData:modulePlayerIsOpen(ModuleSub.eOneKeyChallengeGrab)
             if not isOpen then
                 ui.showFlashView({parent = cc.Director:getInstance():getRunningScene(), text = retInfo.openMessage})
                 return
             end
             if StaConfig.items[1].perUseNum > NetworkResData:getPlayerInfo().STA then
                 showStaOrVitNotEnough(ResourcetypeSub.eSTA)
                 return
             end
             --背包是否已满的判断
             if checkBagSpace() == false then
                 return
             end

            self:requestForOneKey(treasure.ID)
        end,
        position = cc.p(self.bgSize.width * 0.805, self.bgSize.height * 0.64),
    })
    node:addChild(oneKeyButton)""",
            """    local maxComposeCount = 0
    local curDebrisList = self.mTreasureList[index + 1] or {}
    if #curDebrisList == #treasure.debrisModelIds and #curDebrisList > 0 then
        maxComposeCount = 9999
        for _, dv in pairs(curDebrisList) do
            local n = tonumber(dv.Num) or 0
            if n < maxComposeCount then
                maxComposeCount = n
            end
        end
    end

    local function canLaunchOneKeyHunt()
        require("Config.StaConfig")
        local isOpen, retInfo = NetworkResData:modulePlayerIsOpen(ModuleSub.eOneKeyChallengeGrab)
        if not isOpen then
            ui.showFlashView({parent = cc.Director:getInstance():getRunningScene(), text = retInfo.openMessage})
            return false
        end
        if StaConfig.items[1].perUseNum > NetworkResData:getPlayerInfo().STA then
            showStaOrVitNotEnough(ResourcetypeSub.eSTA)
            return false
        end
        if checkBagSpace() == false then
            return false
        end
        return true
    end

    --Tầm bảo tiếp ngay cả khi đã đủ mảnh
    local btnHuntNext = ui.newButton({
        normalImage = "c_7.png",
        text = "Tầm Bảo +1",
        fontSize = 18,
        scale = 0.72,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            if canLaunchOneKeyHunt() then
                self:requestForOneKey(treasure.ID, 1)
            end
        end,
        position = cc.p(self.bgSize.width * 0.60, self.bgSize.height * 0.16),
    })
    node:addChild(btnHuntNext)

    --合成按钮
    self.mComposeBtn = ui.newButton({
        normalImage   = "c_7.png",
        text = TR("合成"),
        fontSize = 24,
        scale = 0.76,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            self:requestCompose(treasure.ID)
        end,
        position = cc.p(self.bgSize.width * 0.77, self.bgSize.height * 0.16),
    })
    node:addChild(self.mComposeBtn)

    --Hợp thành nhiều bảo vật 1 lần
    local btnComposeAll = ui.newButton({
        normalImage = "c_77.png",
        text = (maxComposeCount > 1) and string.format("H.Thành x%d", maxComposeCount) or "H.Thành Tất",
        fontSize = 18,
        scale = 0.72,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            self:requestCompose(treasure.ID, 0)
        end,
        position = cc.p(self.bgSize.width * 0.94, self.bgSize.height * 0.16),
    })
    node:addChild(btnComposeAll)

    --一键抢夺按钮
    local oneKeyButton = ui.newButton({
        normalImage   = "db_10.png",
        text = TR("一键寻宝"),
        fontSize = 22,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            if canLaunchOneKeyHunt() then
                self:requestForOneKey(treasure.ID, self.canCompose and 1 or nil)
            end
        end,
        position = cc.p(self.bgSize.width * 0.805, self.bgSize.height * 0.64),
    })
    node:addChild(oneKeyButton)""",
        ),
        (
            """function TreasureDebrisLayer:requestCompose(treasureModelId)""",
            """function TreasureDebrisLayer:requestCompose(treasureModelId, composeCount)""",
        ),
        (
            """    if self.canCompose then
        LoadingWait:begin(cc.Director:getInstance():getRunningScene())
        HttpRequest("TreasureDebris","TreasureDebrisCompose", {treasureModelId}, handler(self, self.responseCompose))
    else""",
            """    if self.canCompose then
        LoadingWait:begin(cc.Director:getInstance():getRunningScene())
        local reqArgs = (composeCount ~= nil) and {treasureModelId, composeCount} or {treasureModelId}
        HttpRequest("TreasureDebris","TreasureDebrisCompose", reqArgs, handler(self, self.responseCompose))
    else""",
        ),
        (
            """            ui.showFlashView({parent = cc.Director:getInstance():getRunningScene(), text = TR("宝物合成成功！")})""",
            """            local compN = tonumber(event.Value and event.Value.ComposedCount) or 1
            local compMsg = (compN > 1) and string.format("Đã hợp thành %d bảo vật!", compN) or TR("宝物合成成功！")
            ui.showFlashView({parent = cc.Director:getInstance():getRunningScene(), text = compMsg})""",
        ),
        (
            """function TreasureDebrisLayer:requestForOneKey(treasureModelId)
    LoadingWait:begin(cc.Director:getInstance():getRunningScene())
    HttpRequest("TreasureLoot","TreasureLootForOneKey", {treasureModelId}, handler(self, self.responseForKey))
end""",
            """function TreasureDebrisLayer:requestForOneKey(treasureModelId, allowContinue)
    LoadingWait:begin(cc.Director:getInstance():getRunningScene())
    local reqArgs = allowContinue and {treasureModelId, 1} or {treasureModelId}
    HttpRequest("TreasureLoot","TreasureLootForOneKey", reqArgs, handler(self, self.responseForKey))
end""",
        ),
    ])

    FRIEND_DUEL_HELPER_LUA = """local function startFriendDuelFight(loadingParent, friend)
    local targetId = friend and friend.PlayerId
    local targetName = (friend and friend.Name) or "Bạn bè"
    local targetFap = tonumber(friend and friend.FAP) or 0
    if not targetId or targetId == "" then
        return
    end
    LoadingWait:begin(loadingParent or cc.Director:getInstance():getRunningScene())
    HttpRequest("Friend", "FriendFight", {targetId}, function(retVal)
        LoadingWait:ends()
        if not retVal or retVal.Status ~= 0 or not retVal.Value or not retVal.Value.FightInfo then
            ui.showFlashView({parent = cc.Director:getInstance():getRunningScene(), text = "Không thể giao hữu lúc này"})
            return
        end
        local fightVal = retVal.Value
        local isWin = (tonumber(fightVal.IsWinFight) or 0) ~= 0
        local displayInfo = getBattleDisplayInfo(BattleType.eArena)
        require("ComBattle.BattleEntry"):startBattle({
            data = fightVal.FightInfo,
            skip = displayInfo.skip,
            tuoguan = displayInfo.tuoguan,
            skill = displayInfo.skill,
            mapId = ConfigFunc:getBattleNodeBgList(),
            callback = function()
                local returnToFriends = function(dlg)
                    if dlg and not tolua.isnull(dlg) then
                        dlg:removeFromParent()
                    end
                    game.replaceScene(require("Friend.FriendScene").new(), "CCtransitionCrossFade", 0.0)
                end
                local verdict = isWin and "CHIẾN THẮNG" or "THẤT BẠI"
                local box = require("Common.MessageBoxLayer").new({
                    bgImage = "c_43.png",
                    closeBtnImage = "c_15.png",
                    title = TR("Kết Quả Giao Hữu"),
                    content = string.format(
                        "Trận giao hữu với %s (Lực chiến %d):\\n\\nKết quả: %s!\\n(Không tốn Hoạt Lực · Tự gửi chiến báo khi Đồng bộ)",
                        tostring(fightVal.TargetName or targetName),
                        tonumber(fightVal.TargetFAP) or targetFap,
                        verdict
                    ),
                    leftBtnTitle = TR("Quay Lại"),
                    leftBtnCallback = returnToFriends,
                    returnAction = returnToFriends,
                })
                cc.Director:getInstance():getRunningScene():addChild(box, 256)
            end,
        })
    end)
end
"""

    patch_luac_text(src / "Friend" / "ContactLayer.luac", [
        (
            'local ContactLayer = class("ContactLayer", function()',
            FRIEND_DUEL_HELPER_LUA + '\nlocal ContactLayer = class("ContactLayer", function()',
        ),
        (
            """    --- 留言
    self.mBtnConsort = ui.newButton({
        normalImage = "c_7.png",
        position = cc.p(self.mParentSize.width / 2, self.mParentSize.height * 0.6),
        text = TR("留言"),
        fontSize = 24,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            self.mBtnConsort:setVisible(false)
            self.mBtnDelete:setVisible(false)
            self.mBtnView:setVisible(false)
            self.mBtnCancel:setVisible(true)
            self.mBtnSend:setVisible(true)
            self.mEditBox:setVisible(true)
            self.mTitleLabel:setString(TR("内容:"))
        end
    })
    self.mParentLayer:addChild(self.mBtnConsort)

    --- 查看阵容
    self.mBtnView = ui.newButton({
        normalImage = "c_7.png",
        position = cc.p(self.mParentSize.width / 2, self.mParentSize.height * 0.45),
        text = TR("查看阵容"),
        fontSize = 24,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            self:requestFomationInfo()
        end
    })
    self.mParentLayer:addChild(self.mBtnView)

    --- 删除
    self.mBtnDelete = ui.newButton({
        normalImage = "c_7.png",
        position = cc.p(self.mParentSize.width / 2, self.mParentSize.height * 0.3),
        text = TR("删除"),
        fontSize = 24,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            self.mDeleteFriendCallback()
            self:removeFromParent()
        end
    })
    self.mParentLayer:addChild(self.mBtnDelete)""",
            """    --- Giao Hữu (Đấu PvP 0 STA)
    self.mBtnFight = ui.newButton({
        normalImage = "c_77.png",
        position = cc.p(self.mParentSize.width / 2, self.mParentSize.height * 0.63),
        text = "Giao Hữu (Đấu)",
        fontSize = 22,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            startFriendDuelFight(self, self.mFriend)
        end
    })
    self.mParentLayer:addChild(self.mBtnFight)

    --- 留言
    self.mBtnConsort = ui.newButton({
        normalImage = "c_7.png",
        position = cc.p(self.mParentSize.width / 2, self.mParentSize.height * 0.49),
        text = TR("留言"),
        fontSize = 22,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            if self.mBtnFight then
                self.mBtnFight:setVisible(false)
            end
            self.mBtnConsort:setVisible(false)
            self.mBtnDelete:setVisible(false)
            self.mBtnView:setVisible(false)
            self.mBtnCancel:setVisible(true)
            self.mBtnSend:setVisible(true)
            self.mEditBox:setVisible(true)
            self.mTitleLabel:setString(TR("内容:"))
        end
    })
    self.mParentLayer:addChild(self.mBtnConsort)

    --- 查看阵容
    self.mBtnView = ui.newButton({
        normalImage = "c_7.png",
        position = cc.p(self.mParentSize.width / 2, self.mParentSize.height * 0.35),
        text = TR("查看阵容"),
        fontSize = 22,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            self:requestFomationInfo()
        end
    })
    self.mParentLayer:addChild(self.mBtnView)

    --- 删除
    self.mBtnDelete = ui.newButton({
        normalImage = "c_7.png",
        position = cc.p(self.mParentSize.width / 2, self.mParentSize.height * 0.21),
        text = TR("删除"),
        fontSize = 22,
        textColor = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            self.mDeleteFriendCallback()
            self:removeFromParent()
        end
    })
    self.mParentLayer:addChild(self.mBtnDelete)""",
        ),
        (
            """        clickAction = function()
            self.mBtnView:setVisible(true)
            self.mBtnConsort:setVisible(true)
            self.mBtnDelete:setVisible(true)
            self.mBtnCancel:setVisible(false)""",
            """        clickAction = function()
            if self.mBtnFight then
                self.mBtnFight:setVisible(true)
            end
            self.mBtnView:setVisible(true)
            self.mBtnConsort:setVisible(true)
            self.mBtnDelete:setVisible(true)
            self.mBtnCancel:setVisible(false)""",
        ),
    ])

    patch_luac_text(src / "Friend" / "FriendScene.luac", [
        (
            'local FriendScene = class("FriendScene", function()',
            FRIEND_DUEL_HELPER_LUA + '\nlocal FriendScene = class("FriendScene", function()',
        ),
        (
            """    --- 交流
    local btnContact = ui.newButton({
        normalImage = "c_8.png",
        position    = cc.p(215, 27),
        text        = TR("交流"),
        size        = cc.size(120,54),
        fontSize    = 18,
        clickAction = function()
            self:addChild(require("Friend.ContactLayer").new(self, friend, function()
                -- 请求删除
                self:requestRemoveFriend(friend.PlayerId, function()
                    for i, v in ipairs(self.mFriendList) do
                        if v == data then
                            table.remove(self.mFriendList, i)
                            break
                        end
                    end
                    self:refreshView()
                    -- 删除后回调
                    sliderview:reloadData()
                end)
            end))
        end
    })
    lvItem:addChild(btnContact)

    local btnImage = "c_8.png"
    local btnText = ""
    if friend.CanSendSTA == false then
        btnImage = "c_8.png"
        btnText = TR("已赠送")
    end
    --- 赠送耐力
    local btnSendSTA
    btnSendSTA = ui.newButton({
        normalImage = btnImage,
        position    = cc.p(95, 27),""",
            """    --- 交流
    local btnContact = ui.newButton({
        normalImage = "c_8.png",
        position    = cc.p(150, 27),
        text        = TR("交流"),
        scale       = 0.80,
        fontSize    = 18,
        clickAction = function()
            self:addChild(require("Friend.ContactLayer").new(self, friend, function()
                -- 请求删除
                self:requestRemoveFriend(friend.PlayerId, function()
                    for i, v in ipairs(self.mFriendList) do
                        if v == data then
                            table.remove(self.mFriendList, i)
                            break
                        end
                    end
                    self:refreshView()
                    -- 删除后回调
                    sliderview:reloadData()
                end)
            end))
        end
    })
    lvItem:addChild(btnContact)

    --- Đấu giao hữu 1 chạm
    local btnDuel = ui.newButton({
        normalImage = "c_77.png",
        position    = cc.p(244, 27),
        text        = "Đấu",
        scale       = 0.78,
        fontSize    = 18,
        textColor   = ColorList.ccWhite,
        outlineColor = ColorList.ccOutline,
        clickAction = function()
            startFriendDuelFight(self, friend)
        end
    })
    lvItem:addChild(btnDuel)

    local btnImage = "c_8.png"
    local btnText = ""
    if friend.CanSendSTA == false then
        btnImage = "c_8.png"
        btnText = TR("已赠送")
    end
    --- 赠送耐力
    local btnSendSTA
    btnSendSTA = ui.newButton({
        normalImage = btnImage,
        scale       = 0.80,
        position    = cc.p(58, 27),""",
        ),
    ])


def patch_r85_pet_lua(src: Path) -> None:
    """R8.5: Enable Pet/PetOut/PetCompare (1414, 7400..7406, 7500, 7600) and localize 27 Pet names to VN."""
    module_specs = [
        (1414, "PetCompare", 14, "Equip", "宠物合成"),
        (7400, "Pet", 74, "Pet", "宠物系统"),
        (7401, "PetInherit", 74, "Pet", "宠物-传承"),
        (7402, "PetStudySkill", 74, "Pet", "宠物-学习兽决"),
        (7403, "PetLvUp", 74, "Pet", "宠物-升级"),
        (7404, "PetRebirth", 74, "Pet", "宠物-重生"),
        (7405, "PetRefine", 74, "Pet", "宠物-分解"),
        (7406, "PetActiveTal", 74, "Pet", "宠物-激活天赋"),
        (7500, "PetOut", 75, "PetOut", "宠物之源"),
        (7600, "PetColorLv", 76, "PetColorLv", "宠物目录"),
    ]
    module_replacements: list[tuple[str, str]] = []
    for mid, alias, mod_id, mod_alias, zh_name in module_specs:
        old_blk = (
            f"        [{mid}] = {{\n"
            f"            Id = {mid},\n"
            f'            alias = "{alias}",\n'
            f"            moduleId = {mod_id},\n"
            f'            moduleAlias = "{mod_alias}",\n'
            f'            name = "{zh_name}",\n'
            f"            isClient = 1,\n"
            f"            ifOpen = 0,"
        )
        new_blk = (
            f"        [{mid}] = {{\n"
            f"            Id = {mid},\n"
            f'            alias = "{alias}",\n'
            f"            moduleId = {mod_id},\n"
            f'            moduleAlias = "{mod_alias}",\n'
            f'            name = "{zh_name}",\n'
            f"            isClient = 1,\n"
            f"            ifOpen = 1,"
        )
        module_replacements.append((old_blk, new_blk))
    patch_luac_text(src / "Config" / "ModuleSubModel.luac", module_replacements)

    pet_name_map = [
        ("萌萌小紅龍", "Tiểu Long Đỏ"),
        ("調皮狸貓", "Lửng Hachi Tinh Nghịch"),
        ("可愛小烏龜", "Rùa Con Dễ Thương"),
        ("飛艇八衛門", "Hachi Phi Thuyền"),
        ("勤懇死魂蟲", "Tử Hồn Trùng Chăm Chỉ"),
        ("呆萌三眼牛", "Ngưu Ba Mắt Ngây Ngô"),
        ("忠誠阿牟", "A-Un Trung Thành"),
        ("豬九戒", "Trư Cửu Giới"),
        ("龍骨精", "Long Cốt Tinh"),
        ("俏皮狐妖", "Hồ Yêu Shippo Tinh Quái"),
        ("逃跑冥加", "Myoga Đào Tẩu"),
        ("可愛生薑", "Shoga Đáng Yêu"),
        ("呆萌雲母", "Kirara Đáng Yêu"),
        ("狂暴死魂蟲", "Tử Hồn Trùng Cuồng Bạo"),
        ("狸貓石球", "Hachi Cầu Đá"),
        ("玄武神龜", "Huyền Vũ Thần Quy"),
        ("鎧甲八位門", "Hachi Giáp Sắt"),
        ("吐火神龍", "Thần Long Phun Lửa"),
        ("飛天神豬", "Thần Trư Phi Thiên"),
        ("戰鬥阿牟", "A-Un Chiến Đấu"),
        ("憤怒冥加", "Myoga Phẫn Nộ"),
        ("暴走生薑", "Shoga Bạo Tẩu"),
        ("生氣狐妖", "Hồ Yêu Shippo Nổi Giận"),
        ("金剛牛魔王", "Kim Cang Ngưu Ma Vương"),
        ("神翼龍骨精", "Thần Dực Long Cốt Tinh"),
        ("妖化雲母", "Kirara Yêu Hóa"),
        ("經驗寶寶", "Bé Kinh Nghiệm"),
    ]
    pet_model_path = src / "Config" / "PetModel.luac"
    raw_pm = pet_model_path.read_bytes()
    pm_payload = raw_pm[len(XXTEA_SIGN) :] if raw_pm.startswith(XXTEA_SIGN) else raw_pm
    pm_text = xxtea_decrypt(pm_payload, XXTEA_KEY).decode("utf-8")
    for zh, vn in pet_name_map:
        old_token = f'            name = "{zh}",'
        new_token = f'            name = "{vn}",'
        if old_token not in pm_text:
            raise AssertionError(f"Expected pet name token not found in PetModel.luac: {old_token}")
        pm_text = pm_text.replace(old_token, new_token)
    write_luac_text(pet_model_path, pm_text)


def patch_r86_warfare_lua(src: Path) -> None:
    """R8.6: Enable Warfare/Warfarespirit modules (8101..8108), localize names to VN, and unlock UI tabs."""
    module_specs = [
        (8101, "Warfare", "战阵"),
        (8102, "WarfareColorUp", "战阵进阶"),
        (8103, "WarfareSpirit", "战灵"),
        (8104, "WarfarespiritLvUp", "战灵升级"),
        (8105, "WarfarespiritCombat", "战灵上下阵"),
        (8106, "WarfareLvUp", "战阵升级"),
        (8107, "WarfareOpen", "战阵开启"),
        (8108, "WarfarespiritSell", "战灵售卖"),
    ]
    module_replacements: list[tuple[str, str]] = []
    for mid, alias, zh_name in module_specs:
        old_blk = (
            f"        [{mid}] = {{\n"
            f"            Id = {mid},\n"
            f'            alias = "{alias}",\n'
            f"            moduleId = 81,\n"
            f'            moduleAlias = "Warfare",\n'
            f'            name = "{zh_name}",\n'
            f"            isClient = 1,\n"
            f"            ifOpen = 0,"
        )
        new_blk = old_blk.replace("ifOpen = 0,", "ifOpen = 1,")
        module_replacements.append((old_blk, new_blk))
    patch_luac_text(src / "Config" / "ModuleSubModel.luac", module_replacements)

    warfare_name_map = [
        ("萬靈結界", "Kết Giới Vạn Linh"),
        ("雷霆結界", "Kết Giới Lôi Đình"),
        ("降妖結界", "Kết Giới Hàng Yêu"),
        ("風靈結界", "Kết Giới Phong Linh"),
        ("獸靈結界", "Kết Giới Thú Linh"),
        ("妖刀結界", "Kết Giới Yêu Đao"),
        ("暗影結界", "Kết Giới Ám Ảnh"),
        ("水靈結界", "Kết Giới Thủy Linh"),
        ("土靈結界", "Kết Giới Thổ Linh"),
        ("妖神結界", "Kết Giới Yêu Thần"),
        ("冰封結界", "Kết Giới Băng Phong"),
        ("妖魂結界", "Kết Giới Yêu Hồn"),
        ("妖火結界", "Kết Giới Yêu Hỏa"),
        ("巫女結界", "Kết Giới Vu Nữ"),
        ("魔神結界", "Kết Giới Ma Thần"),
    ]
    wf_model_path = src / "Config" / "WarfareModel.luac"
    raw_wm = wf_model_path.read_bytes()
    wm_text = xxtea_decrypt(raw_wm[len(XXTEA_SIGN) :] if raw_wm.startswith(XXTEA_SIGN) else raw_wm, XXTEA_KEY).decode("utf-8")
    for zh, vn in warfare_name_map:
        old_tok = f'            name = "{zh}",'
        new_tok = f'            name = "{vn}",'
        if old_tok not in wm_text:
            raise AssertionError(f"Expected warfare name token not found in WarfareModel.luac: {old_tok}")
        wm_text = wm_text.replace(old_tok, new_tok)
    old_des = '            des = "啟動結界獲得結界技，並獲得結界之力",'
    new_des = '            des = "Kích hoạt Kết Giới để nhận kỹ năng Kết Giới và sức mạnh Kết Giới",'
    if old_des not in wm_text:
        raise AssertionError("Expected warfare description token not found in WarfareModel.luac")
    wm_text = wm_text.replace(old_des, new_des)
    write_luac_text(wf_model_path, wm_text)

    exp_spirit_map = [
        ("低級經驗靈珠", "Linh Châu Kinh Nghiệm Sơ"),
        ("中級經驗靈珠", "Linh Châu Kinh Nghiệm Trung"),
        ("高級經驗靈珠", "Linh Châu Kinh Nghiệm Cao"),
    ]
    spirit_prefix_map = [
        ("命中靈珠", "Linh Châu Chính Xác "),
        ("閃避靈珠", "Linh Châu Né Tránh "),
        ("暴擊靈珠", "Linh Châu Bạo Kích "),
        ("抗暴靈珠", "Linh Châu Kháng Bạo "),
        ("格擋靈珠", "Linh Châu Đỡ Đòn "),
        ("破擊靈珠", "Linh Châu Phá Kích "),
        ("必殺靈珠", "Linh Châu Tất Sát "),
        ("守護靈珠", "Linh Châu Thủ Hộ "),
        ("傷害靈珠", "Linh Châu Sát Thương "),
        ("免傷靈珠", "Linh Châu Miễn Thương "),
        ("攻擊靈珠", "Linh Châu Công "),
        ("血量靈珠", "Linh Châu HP "),
        ("防禦靈珠", "Linh Châu Thủ "),
        ("治療靈珠", "Linh Châu Trị Liệu "),
        ("癒合靈珠", "Linh Châu Hồi Phục "),
    ]
    wsm_path = src / "Config" / "WarfarespiritModel.luac"
    raw_wsm = wsm_path.read_bytes()
    wsm_text = xxtea_decrypt(raw_wsm[len(XXTEA_SIGN) :] if raw_wsm.startswith(XXTEA_SIGN) else raw_wsm, XXTEA_KEY).decode("utf-8")
    for zh, vn in exp_spirit_map:
        old_tok = f'            name = "{zh}",'
        new_tok = f'            name = "{vn}",'
        if old_tok not in wsm_text:
            raise AssertionError(f"Expected spirit EXP token not found: {old_tok}")
        wsm_text = wsm_text.replace(old_tok, new_tok)
    for zh_pref, vn_pref in spirit_prefix_map:
        old_tok = f'            name = "{zh_pref}'
        new_tok = f'            name = "{vn_pref}'
        if old_tok not in wsm_text:
            raise AssertionError(f"Expected spirit prefix token not found: {old_tok}")
        wsm_text = wsm_text.replace(old_tok, new_tok)
    write_luac_text(wsm_path, wsm_text)

    patch_luac_text(src / "Hero" / "HeroUpdateScene.luac", [
        (
            """        tabList = {
            { x = 50, y = 0, text = TR("升级")},
            { x = 200, y = 0, text = TR("突破")},
            --{ x = 350, y = 0, text = TR("转生")},
            --{ x = 500, y = 0, text = TR("结界")},
        },""",
            """        tabList = {
            { x = 50, y = 0, text = TR("升级")},
            { x = 200, y = 0, text = TR("突破")},
            --{ x = 350, y = 0, text = TR("转生")},
            { x = 350, y = 0, tag = HeroEnhance.eWarfare, text = TR("结界")},
        },""",
        ),
        (
            """    -- 小伙伴不能转生
    local mateInfor = NetworkResData:getFormationInfo(false).MateInfos or {}
    for i, v in pairs(mateInfor) do
        if v.HeroId == self.mHero.Id then
            self.mTabLayer:setTabVisibled(HeroEnhance.eRebirth, false)
            break
        end
    end
    
    --[[
    local isOpen = NetworkResData:moduleIsOpenInServer(ModuleSub.eWarfare)
    if not isOpen then
        self.mTabLayer:setTabVisibled(HeroEnhance.eWarfare,false)
    end
    -- 战阵是否开启
    local isOpen, retInfo = NetworkResData:modulePlayerIsOpen(ModuleSub.eWarfare)
    if not isOpen then
        self.mTabLayer:setTabVisibled(HeroEnhance.eWarfare,false)
    end

    -- 是否主角,是否品质>15
    local mainHeroInfo = NetworkResData:getMainSlotInfo()
    if mainHeroInfo.HeroId ~= self.mHero.Id and self.mHeroTable.quality < 15 then
        self.mTabLayer:setTabVisibled(HeroEnhance.eWarfare,false)
    end

    -- 未上阵不显示
    if not self.mCurSlotId then
        self.mTabLayer:setTabVisibled(HeroEnhance.eWarfare,false)
    end
    --]]""",
            """    -- 小伙伴不能转生
    local mateInfor = NetworkResData:getFormationInfo(false).MateInfos or {}
    for i, v in pairs(mateInfor) do
        if v.HeroId == self.mHero.Id then
            self.mTabLayer:setTabVisibled(HeroEnhance.eRebirth, false)
            break
        end
    end
    --]]
    local isOpen = NetworkResData:moduleIsOpenInServer(ModuleSub.eWarfare)
    if not isOpen then
        self.mTabLayer:setTabVisibled(HeroEnhance.eWarfare, false)
    end
    -- 战阵是否开启
    local isOpenPlayer, retInfo = NetworkResData:modulePlayerIsOpen(ModuleSub.eWarfare)
    if not isOpenPlayer then
        self.mTabLayer:setTabVisibled(HeroEnhance.eWarfare, false)
    end

    -- 是否主角,是否品质>=15且配置了结界ID
    local mainHeroInfo = NetworkResData:getMainSlotInfo()
    if (mainHeroInfo.HeroId ~= self.mHero.Id and self.mHeroTable.quality < 15) or not self.mHeroTable.warfareID or self.mHeroTable.warfareID == 0 then
        self.mTabLayer:setTabVisibled(HeroEnhance.eWarfare, false)
    end

    -- 未上阵不显示
    if not self.mCurSlotId then
        self.mTabLayer:setTabVisibled(HeroEnhance.eWarfare, false)
    end""",
        ),
    ])

    patch_luac_text(src / "Disassemble" / "DisassembleNewScene.luac", [
        (
            """                self.mTypeTabLayer:setTabVisibled(3,false)
                self.mTypeTabLayer:setTabVisibled(4,false)
                self.mTypeTabLayer:setTabVisibled(5,true)""",
            """                self.mTypeTabLayer:setTabVisibled(3,false)
                self.mTypeTabLayer:setTabVisibled(4,false)
                self.mTypeTabLayer:setTabVisibled(5, NetworkResData:modulePlayerIsOpen(ModuleSub.eWarfare) and true or false)""",
        ),
        (
            """        tabList = {
            { x = 0, y = 370, text = TR("人\\n物")},
            { x = 0, y = 240, text = TR("宝\\n物")},
            { x = 0, y = 110, text = TR("装\\n备")},
            --{ x = 0, y = 10, text = TR("宠\\n物")},
            --{ x = 0, y = 10, text = TR("结\\n界")},
        },""",
            """        tabList = {
            { x = 0, y = 370, text = TR("人\\n物")},
            { x = 0, y = 240, text = TR("宝\\n物")},
            { x = 0, y = 110, text = TR("装\\n备")},
            { x = 0, y = 10, text = TR("宠\\n物")},
            { x = 0, y = 110, text = TR("结\\n界")},
        },""",
        ),
        (
            """        if  pargrams and pargrams.funcTionType == 2 then
            self.mTypeTabLayer:setTabVisibled(5, false)
        end""",
            """        if (pargrams and pargrams.funcTionType == 2) or not NetworkResData:modulePlayerIsOpen(ModuleSub.eWarfare) then
            self.mTypeTabLayer:setTabVisibled(5, false)
        end""",
        ),
    ])

    patch_luac_text(src / "Bag" / "BagExWarfareArms.luac", [
        (
            "    name           = BagModel.items[BagType.eWarfareArms].name,\n    bagType        = BagType.eWarfareArms,",
            '    name           = "Kết Giới",\n    bagType        = nil,',
        ),
    ])
    patch_luac_text(src / "Bag" / "BagExWarfareSpirit.luac", [
        (
            "    name           = BagModel.items[BagType.eWarfareSpirit].name,\n    bagType        = BagType.eWarfareSpirit,",
            '    name           = "Linh Châu",\n    bagType        = nil,',
        ),
    ])
    patch_luac_text(src / "Bag" / "BagScene.luac", [
        (
            """    -- 判断宝石功能是否开启
    if NetworkResData:modulePlayerIsOpen(ModuleSub.eGem) then
        BagTabInfo[BagSceneTab.eGem] = BagTabInfo[BagSceneTab.eGem] or require("Bag.BagExGem")
        BagSceneTab.eGem = 5
    end""",
            """    -- 判断宝石功能是否开启
    if NetworkResData:modulePlayerIsOpen(ModuleSub.eGem) then
        BagTabInfo[BagSceneTab.eGem] = BagTabInfo[BagSceneTab.eGem] or require("Bag.BagExGem")
        BagSceneTab.eGem = 5
    end
    if NetworkResData:modulePlayerIsOpen(ModuleSub.eWarfare) then
        BagTabInfo[BagSceneTab.eGem] = BagTabInfo[BagSceneTab.eGem] or require("Bag.BagExGem")
        BagTabInfo[BagSceneTab.eWarfareSpirit] = BagTabInfo[BagSceneTab.eWarfareSpirit] or require("Bag.BagExWarfareSpirit")
        BagTabInfo[BagSceneTab.eWarfareArms] = BagTabInfo[BagSceneTab.eWarfareArms] or require("Bag.BagExWarfareArms")
    end""",
        ),
    ])


def _safe_device_id_smali(method_name: str) -> str:
    """Return a non-privileged Build.MANUFACTURER-Build.MODEL getter for MQUtils."""
    return (
        f".method public {method_name}()Ljava/lang/String;\n"
        "    .locals 2\n"
        "\n"
        "    new-instance v0, Ljava/lang/StringBuilder;\n"
        "\n"
        "    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V\n"
        "\n"
        "    sget-object v1, Landroid/os/Build;->MANUFACTURER:Ljava/lang/String;\n"
        "\n"
        "    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n"
        "\n"
        "    move-result-object v0\n"
        "\n"
        '    const-string v1, "-"\n'
        "\n"
        "    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n"
        "\n"
        "    move-result-object v0\n"
        "\n"
        "    sget-object v1, Landroid/os/Build;->MODEL:Ljava/lang/String;\n"
        "\n"
        "    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;\n"
        "\n"
        "    move-result-object v0\n"
        "\n"
        "    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;\n"
        "\n"
        "    move-result-object v0\n"
        "\n"
        "    return-object v0\n"
        ".end method"
    )


def patch_modern_android_sdk(work_dir: Path, min_sdk: int = 21, target_sdk: int = 30) -> None:
    """R8.7: Harden manifest, sdkInfo, and legacy device ID calls for modern Android."""
    manifest_path = work_dir / "AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")

    # 1. Deduplicate <uses-permission .../> lines preserving order
    seen_perms: set[str] = set()
    perm_re = re.compile(r'^(\s*<uses-permission\b[^>]*android:name="([^"]+)"[^>]*/>\s*)$')
    dedup_lines: list[str] = []
    for line in manifest.splitlines(keepends=True):
        pm = perm_re.match(line.rstrip("\r\n"))
        if pm:
            pname = pm.group(2)
            if pname in seen_perms:
                continue
            seen_perms.add(pname)
        dedup_lines.append(line)
    manifest = "".join(dedup_lines)

    # 2. Ensure requestLegacyExternalStorage="true" on <application>
    if "android:requestLegacyExternalStorage=" not in manifest:
        manifest, n_app = re.subn(
            r"<application\s+",
            '<application android:requestLegacyExternalStorage="true" ',
            manifest,
            count=1,
        )
        if n_app != 1:
            raise RuntimeError("Failed to find <application> tag in AndroidManifest.xml")

    # 3. Ensure MQActivity has android:exported="true" and every <intent-filter> component declares android:exported
    manifest, n_main = re.subn(
        r'(<activity\b(?![^>]*\bandroid:exported=)[^>]*android:name="com\.moqikaka\.sdk\.MQActivity")',
        r'\1 android:exported="true"',
        manifest,
        count=1,
    )
    if n_main == 0 and 'android:name="com.moqikaka.sdk.MQActivity"' not in manifest:
        raise RuntimeError("MQActivity not found in AndroidManifest.xml")

    def _add_exported_default(match: re.Match[str]) -> str:
        tag, attrs, body = match.group(1), match.group(2), match.group(3)
        if "<intent-filter" not in body or "android:exported=" in attrs:
            return match.group(0)
        return f"<{tag} android:exported=\"false\"{attrs}>{body}</{tag}>"

    manifest = re.sub(
        r"<(activity|service|receiver|provider)\b([^>]*)>(.*?)</\1>",
        _add_exported_default,
        manifest,
        flags=re.S,
    )
    manifest_path.write_text(manifest, encoding="utf-8")

    # 4. Set minSdkVersion and targetSdkVersion in apktool.yml
    yml_path = work_dir / "apktool.yml"
    yml_txt = yml_path.read_text(encoding="utf-8")
    yml_txt, n_sdk = re.subn(
        r"sdkInfo:\s*\n(?:\s+(?:minSdkVersion|targetSdkVersion):\s*\d+\s*\n)+",
        f"sdkInfo:\n  minSdkVersion: {min_sdk}\n  targetSdkVersion: {target_sdk}\n",
        yml_txt,
        count=1,
    )
    if n_sdk != 1:
        raise RuntimeError("Failed to update sdkInfo in apktool.yml")
    yml_path.write_text(yml_txt, encoding="utf-8")

    # 5. Neutralize TelephonyManager.getDeviceId() + WifiInfo + /sdcard/.moqikaka calls in MQUtils.smali
    mq_path = work_dir / "smali" / "com" / "moqikaka" / "sdk" / "MQUtils.smali"
    mq_src = mq_path.read_text(encoding="utf-8")
    for method_name in ("getDeviceUUid", "getDeviceIMEI2"):
        mq_src, n_rep = re.subn(
            rf"\.method public {re.escape(method_name)}\(\)Ljava/lang/String;.*?\.end method",
            _safe_device_id_smali(method_name),
            mq_src,
            count=1,
            flags=re.S,
        )
        if n_rep != 1:
            raise RuntimeError(f"Failed to patch {method_name} in MQUtils.smali")
    mq_path.write_text(mq_src, encoding="utf-8")


def build_and_sign_work(work_dir: Path, out_name: str) -> Path:
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

    subprocess.run(["java", "-jar", str(APKTOOL_JAR), "b", str(work_dir), "-o", str(unsigned_apk)], check=True)
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


def build_and_sign_release(out_name: str) -> Path:
    return build_and_sign_work(STANDALONE_WORK, out_name)


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
