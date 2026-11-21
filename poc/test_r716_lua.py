#!/usr/bin/env python3
"""Exercise the patched Tầm Ngọc scene and original VN combat from signed APKs."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from lupa.lua51 import LuaRuntime

from test_r712_lua import cocos, lua_source
from test_r7151_lua import function_block


class R716LuaTest(unittest.TestCase):
    def test_timer_uses_acknowledged_count_and_retries_without_spamming(self):
        module = "Practice.XunYuScene"
        with ZipFile(self.baseline) as baseline:
            lua = cocos(baseline)
            lua.execute("XunYuScene = {}")
            lua.execute(function_block(baseline, module, "XunYuScene:onTimer", "\nend") + "\nend")
            lua.execute("""
                local scene = {model={xun_num=0,xun_max=41,restore_time=0.1,restore_interval=900},
                    handler={xun_num=function() end,restore_time=function() end}}
                XunYuScene.onTimer(scene, 0.2)
                assert(scene.model.xun_num == 1)
            """)
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            lua.execute("XunYuScene = {}; unpack = table.unpack")
            for name in ("onTimer", "requestSync", "handleSync", "newRequest"):
                lua.execute(function_block(apk, module, "XunYuScene:" + name, "\nend") + "\nend")
            lua.execute("""
                local requests, displayed, callback = 0, nil, nil
                HttpRequest=function(module, method, data, done)
                    assert(module=="Explore" and method=="GetInfo" and data==nil)
                    requests=requests+1
                    callback=done
                end
                NetworkResData={getCurrentTime=function() return 100 end}
                ExploreRewardNumsRelation={items={}}
                string.split=function() return {} end
                local scene=setmetatable({model={xun_num=0,xun_max=41,restore_time=0.1},
                    handler={restore_time=function() end}}, {__index=XunYuScene})
                scene.handler.xun_num=function() displayed=scene.model.xun_num end
                scene:onTimer(0.2)
                scene:onTimer(1)
                assert(requests==1 and scene.model.xun_num==0 and not displayed)
                callback(nil)
                assert(not scene.model.request_running and scene.model.restore_time==5)
                scene:onTimer(4)
                assert(requests==1)
                scene:onTimer(1)
                assert(requests==2)
                callback({Status=0,Value={RemainNum=1,MaxNum=41,RecoverTime=1000,DailyNum=2,DrawnNums=""}})
                assert(displayed==1 and scene.model.xun_day_num==2 and scene.model.restore_time==900)
            """)

    def combat(self, apk):
        lua = LuaRuntime(unpack_returned_tuples=True)

        def packaged_source(module):
            try:
                return lua_source(apk, module)
            except KeyError:
                return None

        lua.globals().packaged_source = packaged_source
        lua.execute("""
            table.insert(package.loaders, 1, function(name)
                local source = packaged_source(name)
                if source then return assert(loadstring(source, name)) end
            end)
            require("CSCommon.ServerInterface")
            function scenario(attacker, rp, buffs, seed)
                local function unit(model, initialRP)
                    local row = HeroModel.items[model]
                    return {HP=100000,TotalHp=100000,AP=900,DEF=0,RP=initialRP,
                        HIT=10000,DOD=0,CRI=10000,TEN=0,BLO=0,BOG=0,CRId=0,TEND=0,
                        NAId=row.NAID,RAId=row.RAID,HeroModelId=model,Quality=row.quality,RaceId=row.raceID,
                        DAM=0,CP=0,BCP=0,CPR=0,BCPR=0,DAMADD=0,DAMCUT=0,DAMADDR=0,DAMCUTR=0,BuffList=""}
                end
                local heroes={}
                for i=1,12 do heroes[i]={} end
                heroes[1],heroes[9]=unit(attacker,rp),unit(12011005,100)
                heroes[1].BuffList=buffs
                local wave=ConvertDataToBattleData({FightObjs={{Heros=heroes,
                    TeamData={{Fsp=9000,Fap=10000},{Fsp=1,Fap=1000}},Pets={},RandNum=seed,IsPVP=false}}})[1]
                local calc=newObject(require("CSCommon.BattleCalc"))
                assert(calc:init(wave.heros,wave.teamData,wave.petData,4,wave.randNums,wave.isPvP))
                calc:fightATimes({autoPlay=true})
                return calc
            end
        """)
        return lua

    def test_vn_combat_opens_with_rage_and_applies_crit_passive_once(self):
        with ZipFile(self.apk) as apk:
            self.combat(apk).execute("""
                local function firstAttack(rp,buffs)
                    local calc=scenario(12011004,rp,buffs,77817)
                    return calc.mHeros[1]:getRP(), calc.mHeros[9]:getHP()
                end
                local rp,hp=firstAttack(100,"10350000")
                local duplicate,duplicateHP=firstAttack(100,"10350000,10350000")
                local noTalent,sameHP=firstAttack(100,"")
                local highRP,highDamageHP=firstAttack(150,"10350000")
                local basicRP,basicHP=firstAttack(50,"10350000")
                assert(rp==25 and duplicate==25 and duplicateHP==hp)
                assert(noTalent==0 and sameHP==hp)
                assert(highRP==25 and highDamageHP<hp and hp<basicHP)
                assert(basicRP==100)
            """)

    def test_stock_vn_midoriko_silence_blocks_rage_but_allows_normal_attack(self):
        with ZipFile(self.apk) as apk:
            self.combat(apk).execute("""
                local function enemyAction(seed)
                    local calc=scenario(12012004,100,"",seed)
                    local before=calc.mHeros[9]:getRP()
                    assert(before>=100)
                    calc:fightATimes({autoPlay=true})
                    return before,calc.mHeros[9]:getRP(),calc.mHeros[1]:getHP()
                end
                local clearBefore,clearAfter,rageHP=enemyAction(1)
                local silentBefore,silentAfter,normalHP=enemyAction(3)
                assert(clearBefore==silentBefore and clearAfter==0)
                assert(silentAfter==silentBefore+25 and normalHP<100000 and normalHP>rageHP)
            """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    R716LuaTest.baseline = args.baseline
    R716LuaTest.apk = args.apk
    unittest.main(argv=[__file__], verbosity=2)
