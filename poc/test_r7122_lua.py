#!/usr/bin/env python3
"""Exercise the packaged breakthrough request and response callbacks."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from test_r712_lua import cocos, register


class BreakthroughLuaTest(unittest.TestCase):
    def test_rpc_uses_rendered_step_and_holds_selection_until_response(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            for module in ("Config.HeroStepRelation", "Common.CommonFunc"):
                lua.globals().package.loaded[module] = True
            register(lua, apk, "Hero.HeroUpdateScene")
            lua.execute("""
                handler = function(self, fn) return function(event) fn(self, event) end end
                LoadingWait = {begin = function() end, ends = function() end}
                local sends, result, displayed, play = 0
                local deleted = {}
                HttpRequest = function(module, method, data, callback)
                    assert(module == "Hero" and method == "HeroStepUp" and #data == 3)
                    assert(data[1] == "inuyasha" and data[3] == 4)
                    assert(table.concat(data[2], ",") == "same-hero,book,horse")
                    result = callback
                    sends = sends + 1
                end
                NetworkResData = {
                    getFormationInfo = function()
                        return {SlotInfos = {{HeroId = "inuyasha", FAP = 42}}}
                    end,
                    deleteHeroItems = function(self, list) deleted.hero = list[1].Id end,
                    deleteTreasureItems = function(self, list)
                        deleted.book, deleted.horse = list[1].Id, list[2].Id
                    end,
                    modifyHeroItem = function(self, hero) assert(hero.Step == 5) end,
                }
                playEffect = function() end
                ui.newEffect = function(spec) spec.startListener(); play = spec.completeListener end
                GetHeroAttribute = {getHeroTotalInfor = function() return {} end}
                package.loaded["Hero.HeroBreakInforLayer"] = {new = node}
                cc.Director = {getInstance = function() return {getRunningScene = node} end}

                local scene = setmetatable({
                    mHero = {Id = "inuyasha", HeroModelId = 12011004, Lv = 35, Step = 4},
                    mCanBreak = 0,
                    mMaterialHeroEntity = {"same-hero"},
                    mMaterialEquipmentEntity = {},
                    mMaterialTreasureEntity = {"book", "horse"},
                    mBreakthroughNode1 = {getContentSize = function() return {width = 100} end},
                    mBreakThroughBtn = {setTouchEnabled = function() end},
                    createHeroBreakthrough = function(self, step) displayed = step end,
                }, {__index = require("Hero.HeroUpdateScene")})

                scene:requestHeroStepUp("inuyasha")
                scene:requestHeroStepUp("inuyasha")
                assert(sends == 1)
                result({Status = -1802})
                assert(next(deleted) == nil and scene.mHero.Step == 4 and displayed == nil)
                scene:requestHeroStepUp("inuyasha")
                assert(sends == 2)
                result({Status = 0, Value = {Id = "inuyasha", HeroModelId = 12011004, Lv = 35, Step = 5}})
                scene:requestHeroStepUp("inuyasha")
                assert(sends == 2 and scene.mHero.Step == 4)
                assert(deleted.hero == "same-hero" and deleted.book == "book" and deleted.horse == "horse")
                play()
                assert(scene.mHero.Step == 5 and displayed == 5 and not scene.mHeroStepPending)
            """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    BreakthroughLuaTest.apk = parser.parse_args().apk
    unittest.main(argv=[__file__], verbosity=2)
