#!/usr/bin/env python3
"""
Build an isolated test-patched VN 5.0.4.98 (com.cmn.inuyasha) APK pointing to the local emulator.
Does NOT alter EN files, originals/, or EN checkpoint.
"""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DECOMPILED = ROOT_DIR / "analysis" / "vn" / "apktool"
PATCH_WORK = ROOT_DIR / "analysis" / "vn" / "apktool_patched"
OUT_DIR = ROOT_DIR / "analysis" / "vn" / "patched"
APKTOOL_JAR = ROOT_DIR / "analysis" / "tools" / "apktool_3.0.3.jar"
SDK_BUILD_TOOLS = Path("/Users/vup/Library/Android/sdk/build-tools/36.0.0")
ZIPALIGN = SDK_BUILD_TOOLS / "zipalign"
APKSIGNER = SDK_BUILD_TOOLS / "apksigner"
KEYSTORE = Path.home() / ".android" / "debug.keystore"

XXTEA_SIGN = b"MQKK"
XXTEA_KEY = b"cf68b641311b5201"

VN_LOCAL_MQLOGIN_SMALI = """.method public MQLogin()V
    .locals 3

    .prologue
    new-instance v0, Lcom/moqikaka/sdk/Entity$2$1LoginInfo;

    const/4 v2, 0x0

    invoke-direct {v0, v2}, Lcom/moqikaka/sdk/Entity$2$1LoginInfo;-><init>(Lcom/moqikaka/sdk/Entity$2;)V

    const-string v1, "100001"

    iput-object v1, v0, Lcom/moqikaka/sdk/Entity$2$1LoginInfo;->uid:Ljava/lang/String;

    const-string v1, "1001"

    iput-object v1, v0, Lcom/moqikaka/sdk/Entity$2$1LoginInfo;->platformId:Ljava/lang/String;

    const-string v1, "local-revival"

    iput-object v1, v0, Lcom/moqikaka/sdk/Entity$2$1LoginInfo;->token:Ljava/lang/String;

    iget-object v1, p0, Lcom/moqikaka/sdk/Entity;->mHelper:Lcom/moqikaka/sdk/MQHelper;

    invoke-virtual {v1, v0}, Lcom/moqikaka/sdk/MQHelper;->loginEnd(Ljava/lang/Object;)V

    return-void
.end method"""

VN_LOCAL_ONCREATE_SMALI = """.method public onCreate(Landroid/os/Bundle;)V
    .locals 2
    .param p1, "savedInstanceState"    # Landroid/os/Bundle;

    .prologue
    const/4 v1, 0x1

    iget-object v0, p0, Lcom/moqikaka/sdk/Entity;->mHelper:Lcom/moqikaka/sdk/MQHelper;

    invoke-virtual {v0, v1}, Lcom/moqikaka/sdk/MQHelper;->setSdkInited(Z)V

    return-void
.end method"""

VN_LOCAL_ONDESTROY_SMALI = """.method public onDestroy()V
    .locals 0

    .prologue
    return-void
.end method"""


def xxtea_decrypt(data: bytes, key: bytes = XXTEA_KEY) -> bytes:
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
    blob[idx : idx + len(old)] = new + b"\x00" * (len(old) - len(new))


def patch_workspace(server_host_port: str) -> None:
    if PATCH_WORK.exists():
        shutil.rmtree(PATCH_WORK)
    shutil.copytree(SRC_DECOMPILED, PATCH_WORK)

    manifest_path = PATCH_WORK / "AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")
    if "android:usesCleartextTraffic" not in manifest:
        manifest = manifest.replace("<application ", '<application android:usesCleartextTraffic="true" ', 1)
    if "org.apache.http.legacy" not in manifest:
        manifest = manifest.replace(
            "</application>",
            '    <uses-library android:name="org.apache.http.legacy" android:required="false"/>\n    </application>',
            1,
        )
    manifest_path.write_text(manifest, encoding="utf-8")

    # VN assets/libs.apk uses a custom DexClassLoader whose parent excludes org.apache.http.legacy
    # and bundles compile-time Stub! classes. Move its non-stub classes into smali_classes2
    # so Android 12 PathClassLoader loads org.apache.http.legacy.jar cleanly, and stub loadDex().
    libs_apk = PATCH_WORK / "assets" / "libs.apk"
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
            classes2_dir = PATCH_WORK / "smali_classes2"
            if classes2_dir.exists():
                shutil.rmtree(classes2_dir)
            shutil.copytree(dec_dir / "smali", classes2_dir)
        libs_apk.unlink(missing_ok=True)
        mq_app_path = PATCH_WORK / "smali" / "com" / "moqikaka" / "sdk" / "MQApplication.smali"
        mq_app_src = mq_app_path.read_text(encoding="utf-8")
        mq_app_src, n = re.subn(
            r"\.method public static loadDex\(Landroid/content/Context;\)V.*?\.end method",
            ".method public static loadDex(Landroid/content/Context;)V\n    .locals 0\n\n    return-void\n.end method",
            mq_app_src,
            count=1,
            flags=re.S,
        )
        if n != 1:
            raise RuntimeError("Failed to stub MQApplication.loadDex in VN")
        mq_app_path.write_text(mq_app_src, encoding="utf-8")

    so_path = PATCH_WORK / "lib" / "armeabi" / "libcocos2dlua.so"
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

    entity_path = PATCH_WORK / "smali" / "com" / "moqikaka" / "sdk" / "Entity.smali"
    entity_src = entity_path.read_text(encoding="utf-8")
    for pat, repl, label in [
        (r"\.method public MQLogin\(\)V.*?\.end method", VN_LOCAL_MQLOGIN_SMALI, "MQLogin"),
        (r"\.method public onCreate\(Landroid/os/Bundle;\)V.*?\.end method", VN_LOCAL_ONCREATE_SMALI, "onCreate"),
        (r"\.method public onDestroy\(\)V.*?\.end method", VN_LOCAL_ONDESTROY_SMALI, "onDestroy"),
    ]:
        entity_src, n = re.subn(pat, repl, entity_src, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"Failed to patch {label} in VN Entity.smali")
    entity_path.write_text(entity_src, encoding="utf-8")

    utils_path = PATCH_WORK / "smali" / "com" / "moqikaka" / "sdk" / "MQUtils.smali"
    utils_path.write_text(
        utils_path.read_text(encoding="utf-8").replace("http://crashnew.moqikaka.com", f"http://{server_host_port}"),
        encoding="utf-8",
    )

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
    patch_luac_text(
        PATCH_WORK / "assets" / "src" / "Store" / "RechargeScene.luac",
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
        PATCH_WORK / "assets" / "src" / "ExtraActivity" / "MonthCardLayer.luac",
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
        PATCH_WORK / "assets" / "src" / "TimedActivity" / "LimittedTimedRecruitLayer.luac",
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
                '            local shortName = bId == 81 and "Sessho (81)" or (bId == 82 and "InuTaishou (82)" or ("Banner " .. tostring(bId)))\n'
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
        ],
    )


def build_and_sign(out_name: str = "com.cmn.inuyasha_revival.apk") -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    unsigned_apk = OUT_DIR / "unsigned.apk"
    aligned_apk = OUT_DIR / "aligned.apk"
    signed_apk = OUT_DIR / out_name
    for p in (unsigned_apk, aligned_apk, signed_apk):
        p.unlink(missing_ok=True)
    subprocess.run(["java", "-jar", str(APKTOOL_JAR), "b", str(PATCH_WORK), "-o", str(unsigned_apk)], check=True)
    subprocess.run([str(ZIPALIGN), "-f", "4", str(unsigned_apk), str(aligned_apk)], check=True)
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
    parser = argparse.ArgumentParser(description="Build patched VN 5.0.4.98 APK for local emulator test")
    parser.add_argument("--server", default="192.168.1.250:8080", help="Emulator host:port")
    parser.add_argument("--out", default="com.cmn.inuyasha_revival.apk", help="Output APK filename in analysis/vn/patched/")
    args = parser.parse_args()
    patch_workspace(args.server)
    out = build_and_sign(args.out)
    print(f"Patched & signed VN APK ready: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
