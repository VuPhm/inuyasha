#!/usr/bin/env python3
"""Exercise the standalone APK's Lua callbacks with mocked Cocos nodes."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from lupa.lua54 import LuaRuntime

from patch_vn_apk import XXTEA_SIGN, xxtea_decrypt


COCOS = """
local noop = function() end
function node()
    return {
        addChild = noop, registerScriptHandler = noop, setBounceEnabled = noop,
        setDirection = noop, setContentSize = noop, setAnchorPoint = noop,
        setPosition = noop, setItemsMargin = noop, setScaleX = noop,
        setSwallowTouches = noop, setColor = noop,
        getEventDispatcher = function() return {addEventListenerWithSceneGraphPriority = noop} end,
        removeFromParent = function(self) self.removed = (self.removed or 0) + 1 end,
    }
end
function class(name, create)
    local cls = {}
    cls.new = function(...)
        local instance = create(...)
        setmetatable(instance, {__index = cls})
        if cls.ctor then cls.ctor(instance, ...) end
        return instance
    end
    return cls
end
CCLayerExtend = {extend = function(n) return n end}
function TR(text) return text end
cc = {
    p = function(x,y) return {x = x, y = y} end,
    c4b = noop,
    EventListenerTouchOneByOne = {create = node},
    Handler = {},
}
ccui = {ListView = {create = node}, ScrollViewDir = {vertical = 1}}
ui = {
    newScene = node,
    getImageSize = function() return {width = 482, height = 428} end,
    newLabel = node,
    newButton = function(spec) return spec end,
}
Adapter = {MinScale = 1}
ColorList = {}
package.loaded["Common.Ctrl"] = {newNode = node}
for _, name in ipairs({"EquipModel", "TreasureDebrisModel", "GoodsModel", "HeroModel", "TreasureModel"}) do
    package.loaded["Config." .. name] = true
end
package.loaded["Language"] = true
package.loaded["Common.CommonBgLayer"] = {
    new = function(params)
        local layer = node()
        layer.mBgSize = {width = 482, height = 428}
        layer.mBgSprite = node()
        layer.getBackgroundSprite = function(self) return self.mBgSprite end
        params.closeBtnImage = params.closeBtnImage or "c_15.png"
        bindCloseButton(layer, params)
        return layer
    end
}
"""


def lua_source(apk, module):
    raw = apk.read(f"assets/src/{module.replace('.', '/')}.luac")
    if not raw.startswith(XXTEA_SIGN):
        raise ValueError(f"{module} has no MQKK header")
    return xxtea_decrypt(raw[len(XXTEA_SIGN):]).decode("utf-8")


def register(lua, apk, *modules):
    for module in modules:
        lua.globals().package.preload[module] = lua.eval("function()\n" + lua_source(apk, module) + "\nend")


def cocos(apk):
    lua = LuaRuntime()
    lua.execute(COCOS)
    source = lua_source(apk, "Common.CommonBgLayer")
    start = source.index('    if params.closeBtnImage and params.closeBtnImage ~= "" then')
    finish = source.index("    -- Title", start)
    lua.globals().bindCloseButton = lua.eval(
        "function(self, params)\n"
        "local function getBgTitleInfo() return {closeRate = 1} end\n"
        "local function getColseBtnPos() return params.closeBtnPos end\n"
        + source[start:finish] + "\nend"
    )
    register(lua, apk, "Common.ModalColorLayer", "Common.MessageBoxLayer", "Task.TaskRewardPreviewLayer")
    return lua


class R712LuaTest(unittest.TestCase):
    def test_rank_popup_red_on_810_green_on_820(self):
        for apk_path, fixed in ((self.old_apk, False), (self.new_apk, True)):
            with self.subTest(apk=apk_path.name), ZipFile(apk_path) as apk:
                lua = cocos(apk)
                register(lua, apk, "TimedActivity.TimedEquipRankLayer")
                for rank in (0, 1, 2):
                    ok, removed = lua.eval("""
                        function(rank)
                            local popup = require("TimedActivity.TimedEquipRankLayer").new({
                                myRank = rank, myIntegral = 0, rankList = {},
                            })
                            debug.sethook(function() error("close callback did not terminate") end, "", 1000)
                            local ok = pcall(popup.mCloseButton.clickAction)
                            debug.sethook()
                            return ok, popup.removed or 0
                        end
                    """)(rank)
                    self.assertEqual((ok, removed), (fixed, int(fixed)))

    def test_common_popups_default_custom_and_reward_preview(self):
        with ZipFile(self.new_apk) as apk:
            lua = cocos(apk)
            lua.execute("""
                local Message = require("Common.MessageBoxLayer")
                local message = Message.new({})
                message.mCloseButton.clickAction()
                assert(message.removed == 1)

                local calls = 0
                local custom = Message.new({returnAction = function(target)
                    calls = calls + 1
                    target:removeFromParent()
                end})
                custom.mCloseButton.clickAction()
                assert(custom.removed == 1 and calls == 1)

                local Preview = require("Task.TaskRewardPreviewLayer")
                Preview.createUI = function() end
                for status = 0, 2 do
                    local preview = Preview.new({status = status, callback = function() error("claimed") end})
                    preview.mCloseButton.clickAction()
                    assert(preview.removed == 1)
                end
            """)

    def test_breakthrough_route_preserves_material_target_and_hero(self):
        with ZipFile(self.new_apk) as apk:
            lua = cocos(apk)
            for name in ("Config.HeroModel", "Config.HeroStepRelation", "Common.CommonFunc",
                         "Config.TreasureDebrisModel", "Config.TreasureModel"):
                lua.globals().package.loaded[name] = True
            register(lua, apk, "Grab.GrabTreasureScene", "Hero.HeroUpdateScene")
            lua.execute("""
                GuideMng = {getOtherGuideId = function() end}
                ModuleSub = {eChallengeGrab = 2501}
                ResourcetypeSub = {eBook = 1401, eHorse = 1402}
                local latest = {Id = "kept", Step = 2}
                local open = false
                local notice, scene
                NetworkResData = {
                    modulePlayerIsOpen = function(self, id)
                        assert(id == 2501)
                        return open, {openMessage = "Lv14"}
                    end,
                    getHero = function(self, id)
                        assert(id == "kept")
                        return latest
                    end,
                }
                ui.showFlashView = function(spec) notice = spec.text end
                game = {replaceScene = function(next) scene = next end}
                local heroScene = require("Hero.HeroUpdateScene")
                heroScene.ctor = function(self, tab, hero, onClose)
                    self.tab, self.hero, self.callback = tab, hero, onClose
                end
                local callback = function() end
                local screen = heroScene.new(2, {Id = "kept", Step = 1}, callback)
                screen.mHero, screen.returnCallback = screen.hero, callback
                screen:openBreakthroughTreasure(1401, 14010501)
                assert(scene == nil and notice == "Lv14")
                open = true
                for _, case in ipairs({{1401, 14010501, 2, 15032101}, {1402, 14020501, 1, 15040101}}) do
                    screen:openBreakthroughTreasure(case[1], case[2])
                    assert(scene.mPargrams.selectType == case[3] and scene.mPargrams.treasureId == case[2])
                    TreasureModel = {items = {[case[2]] = {ID = case[2], typeID = case[1], debrisModelIds = {case[4]}}}}
                    local rows = scene:manageData({}, case[1])
                    assert(rows[1][1].TreasureDebrisModelId == case[4])
                    scene.bgLayer.mCloseButton.clickAction()
                    assert(scene.tab == 2 and scene.hero == latest and scene.callback == callback)
                end
            """)

    def test_pray_tree_reopens_with_fresh_server_data(self):
        for apk_path, expected_requests in ((self.old_apk, 0), (self.new_apk, 2)):
            with self.subTest(apk=apk_path.name), ZipFile(apk_path) as apk:
                lua = cocos(apk)
                register(lua, apk, "TimedActivity.TimedPrayTree")
                requests = lua.execute("""
                package.loaded["Common.PlayerCacheData"] = {
                    get = function()
                        return {NeedNum = 300, Num = 0, RewardNum = 5, EndTime = 3600, RewardList = {}}
                    end,
                }
                local tree = require("TimedActivity.TimedPrayTree")
                tree.createUi = function() end
                tree.refreshUi = function() end
                tree.createListView = function() end
                local requests = 0
                tree.requestTreeData = function() requests = requests + 1 end
                tree.new({size = {}})
                tree.new({size = {}})
                return requests
                """)
                self.assertEqual(requests, expected_requests)

    def test_pray_tree_distinguishes_locked_eligible_and_claimed(self):
        with ZipFile(self.new_apk) as apk:
            lua = cocos(apk)
            register(lua, apk, "TimedActivity.TimedPrayTree")
            lua.execute("""
                local tree = require("TimedActivity.TimedPrayTree")
                local text, shown
                local view = {
                    mCurrentDiamond = 180, mNeedDiamond = 300,
                    mRechargeButton = {setVisible = function(_, value) shown = value end},
                    mTishi = {setString = function(_, value) text = value end},
                }
                tree.refreshEligibility(view, {1})
                assert(shown and text:find("300", 1, true))
                view.mCurrentDiamond = 300
                tree.refreshEligibility(view, {1})
                assert(not shown and text:find("đã kích hoạt", 1, true))
                tree.refreshEligibility(view, {})
                assert(not shown and text:find("Đã nhận đủ", 1, true))
            """)
            for module in ("Network.ServerMessage", "Config.BagModel", "Bag.BagExpandTipLayer",
                           "Grab.TreasureDebrisLayer"):
                register(lua, apk, module)
            lua.execute("""
                assert(require("Network.ServerMessage")[-2009]:find("Vật phẩm vẫn còn", 1, true))
                require("Config.BagModel")
                assert(BagModel.items[5].initSize == 300 and BagModel.items[5].perExpandSize == 5)
            """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("old_apk", type=Path)
    parser.add_argument("new_apk", type=Path)
    args = parser.parse_args()
    R712LuaTest.old_apk = args.old_apk
    R712LuaTest.new_apk = args.new_apk
    unittest.main(argv=[__file__], verbosity=2)
