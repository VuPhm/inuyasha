#!/usr/bin/env python3
"""Run the APK's real Mystery Shop clock and refresh callbacks."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from test_r712_lua import cocos, register


class MysteryShopLuaTest(unittest.TestCase):
    def test_expired_callback_on_824_and_single_poll_at_825_boundary(self):
        for apk_path, fixed in ((self.old_apk, False), (self.new_apk, True)):
            with self.subTest(apk=apk_path.name), ZipFile(apk_path) as apk:
                lua = cocos(apk)
                register(lua, apk, "Store.MysticalStoreScene")
                lua.globals().fixed = fixed
                lua.execute("""
                    local tick, response, method
                    local calls, now, display = 0, 999, nil
                    local scheduler = {
                        scheduleScriptFunc = function(self, callback, interval)
                            assert(interval == 1)
                            tick = callback
                            return 123
                        end,
                        unscheduleScriptEntry = function(self, id) assert(id == 123); tick = nil end,
                    }
                    cc.Director = {getInstance = function()
                        return {getScheduler = function() return scheduler end}
                    end}
                    package.loaded["Config.MysteryshopConfig"] = true
                    package.loaded["Config.TreasureDebrisModel"] = true
                    package.loaded["Common.TabView"] = {}
                    NetworkResData = {
                        getCurrentTime = function() return now end,
                        getGoodsCountByModelId = function() return 1 end,
                    }
                    formatTimeEx = function(seconds) return seconds end
                    LoadingWait = {begin = function() end, ends = function() end}
                    HttpRequest = function(module, name, data, callback)
                        assert(module == "MysteryShop")
                        method, response = name, callback
                        calls = calls + 1
                    end
                    local scene = setmetatable({
                        mCurrStoreType = 1,
                        mStoreInfo = {normalRefreshUse = {useResource = {{modelId = 16050010}}}},
                        mRefershTimeLabel = {setString = function(self, value) display = value end},
                        refreshListView = function() end,
                        updateLayer = function() end,
                        executeGuide = function() end,
                        useDiamondHint = function() end,
                        getRefreshType = function() return 3 end,
                    }, {__index = require("Store.MysticalStoreScene")})
                    scene:onEnterTransitionFinish()
                    assert(calls == 1 and method == "GetInfo")
                    if not fixed then
                        response({Status = 0, Value = {FreeCount = 1}})
                        tick()
                        tick()
                        assert(calls == 3 and display == nil)
                        return
                    end
                    response({Status = 0, Value = {LastFreshDate = 1000, FreeCount = 1}})
                    tick()
                    assert(calls == 1 and display == 1)
                    now = 1000
                    tick()
                    tick()
                    assert(calls == 2 and display == 0 and method == "GetInfo")
                    response({Status = 0, Value = {LastFreshDate = 8200, FreeCount = 2}})
                    tick()
                    assert(calls == 2 and display == 7200)

                    scene:requestRefreshtGoodsList()
                    assert(method == "RefreshtGoodsList")
                    response({Status = 0, Value = {LastFreshDate = 8200, FreeCount = 2}})
                    tick()
                    assert(calls == 3 and display == 7200)
                    scene.mCurrStoreType = 2
                    scene:requestSeniorGetInfo()
                    response({Status = 0, Value = {LastFreshDate = 1200, FreeCount = 2}})
                    now = 1200
                    tick()
                    tick()
                    assert(calls == 5 and method == "SeniorGetInfo")
                    scene:onExit()
                    assert(tick == nil)
                """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("old_apk", type=Path)
    parser.add_argument("new_apk", type=Path)
    args = parser.parse_args()
    MysteryShopLuaTest.old_apk = args.old_apk
    MysteryShopLuaTest.new_apk = args.new_apk
    unittest.main(argv=[__file__], verbosity=2)
