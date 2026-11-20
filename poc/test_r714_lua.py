#!/usr/bin/env python3
"""Exercise the bundled R7.14 Mộ Thần Binh callbacks."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from test_r712_lua import cocos, register, lua_source


class R714LuaTest(unittest.TestCase):
    def test_catalogue_reads_success_and_handles_missing_baseline_response(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            register(lua, apk, "NewXZYY.XzyyMainScene")
            lua.execute("""
                package.loaded["Config.BddNodeModel"] = true
                package.loaded["Config.BddClearanceModel"] = true
                LoadingWait = {ends = function() end}
                local label, redraw
                local scene = setmetatable({
                    refreshRed = function() end,
                    refeshData = function() redraw = true end,
                    mSimulationLabel = {setString = function(_, text) label = text end},
                }, {__index = require("NewXZYY.XzyyMainScene")})
                scene:responseInitData({Status = 0, Value = {}})
                assert(not redraw)
                scene:responseInitData({Status = 0, Value = {
                    Info = {StarCount=0, MaxStarCount=0, FAP=7800, ResetCount=0,
                            NeedReset=false, NeedSelectBuff=false, NeedDrawReward=false,
                            BeforeFloorStarCount=0, CanUseStarCount=0, Feats=0},
                    Simulation = true,
                    PlayableCount = 6,
                    NodeInfo = {{Id=1111, Locked=false}},
                    Catalogue = {{Id=1111, Locked=false}, {Id=1311, Locked=true}},
                    BuffInfo = {}, BuyShopInfo = {},
                }})
                assert(redraw and scene.mFloorInfor[1].Id == 1111)
                assert(scene.mCatalogue[2].Locked and label:find("6/51", 1, true))
            """)

    def test_fight_token_flows_from_preview_to_settlement(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            register(lua, apk, "NewXZYY.XzyyPrepareFightLayer", "Adventure.BattleSettleLayer")
            lua.execute("""
                package.loaded["Config.BddNodeModel"] = true
                package.loaded["Config.BddPointModel"] = true
                package.loaded["Adventure.NightmareDataCache"] = true
                LoadingWait = {begin = function() end, ends = function() end}
                BattleType = {eXZYY = 10}
                handler = function(self, fn) return function(value) return fn(self, value) end end
                getBattleDisplayInfo = function() return {} end
                local cached, battle, callback, count
                count = 0
                BattleDataCache = {setXZYYData = function(_, info) cached = info end}
                package.loaded["Adventure.BattleDataCache"] = BattleDataCache
                package.loaded["ComBattle.BattleEntry"] = {
                    startBattle = function(_, params) battle = params.data end,
                }
                HttpRequest = function(module, method, args, cb)
                    assert(module == "BddInfo")
                    count = count + 1
                    if method == "GetFightInfo" then
                        assert(args[1] == 1111 and args[2] == 3)
                        callback = cb
                    else
                        assert(method == "Fight" and args[1] == 1111 and args[2] == 3)
                        assert(#args == 6 and args[6] == "qa-token")
                    end
                end
                local preview = setmetatable({}, {__index = require("NewXZYY.XzyyPrepareFightLayer")})
                preview:requestFight(1111, 3, false)
                preview:requestFight(1111, 3, false)
                assert(count == 1)
                local fightInfo = {FightObjs={{RandNum=1}}}
                callback({Status=0, Value={FightInfo=fightInfo, FightToken="qa-token"}})
                assert(battle == fightInfo and cached.FightToken == "qa-token")
                local settlement = setmetatable({
                    mXZYYData = cached,
                    mFightResult = {result=true, data="verify"},
                }, {__index=require("Adventure.BattleSettleLayer")})
                settlement:requestXZYY()
                assert(count == 2)
            """)

    def test_packaged_insight_and_exchange_lua_load(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            for module in ("Practice.LightenStarScene", "NewXZYY.XzyyStoreScene"):
                lua.compile(lua_source(apk, module), name=module)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    R714LuaTest.apk = parser.parse_args().apk
    unittest.main(argv=[__file__], verbosity=2)
