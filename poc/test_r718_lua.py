#!/usr/bin/env python3
"""Test stock combat and the final BDD chest in the signed APK."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

import test_r717_lua
from test_r712_lua import cocos, register


class R718LuaTest(unittest.TestCase):
    def combat(self, script):
        check = test_r717_lua.R717LuaTest()
        check.apk = self.apk
        check.check(script)

    def test_kanna_removes_the_stat_debuff_and_leaves_control(self):
        self.combat("""
            local c=scenario(12013006,100,"",3,{ally=12011004,allyBuffs="12130400,14010000",defer=true})
            assert(buff(c,2,12130400)==1 and buff(c,2,14010000)==1)
            c:fightATimes({autoPlay=true})
            assert(buff(c,2,12130400)==0 and buff(c,2,14010000)==1)
        """)

    def test_manten_pays_ten_percent_max_hp_once_for_rage_skill(self):
        self.combat("""
            local c=scenario(12012014,100,"",3,{hp=40000,crit=0})
            assert(c.mHeros[1]:getHP()==30000 and c.mHeros[1]:getRP()==0)
            local low=scenario(12012014,100,"",3,{hp=5,crit=0})
            assert(low.mHeros[1]:getHP()==1)
            local normal=scenario(12012014,50,"",3,{hp=40000,crit=0})
            assert(normal.mHeros[1]:getHP()==40000)
            local bonus=c.mHeros[9]:getHP()
            BuffModel.items[10720400].addValue=0
            local noBonus=scenario(12012014,100,"",3,{hp=40000,crit=0})
            assert(noBonus.mHeros[9]:getHP()>bonus)
        """)

    def test_lowest_rage_talent_skips_caster_and_adds_twenty_five_to_one_ally(self):
        self.combat("""
            local hit, miss = false, false
            for seed=1,40 do
                local c=scenario(12011020,0,"10530600",seed,{ally=12011004,allyRP=90,
                    secondAlly=12012004,secondAllyRP=80})
                assert(c.mHeros[1]:getRP()==25 and c.mHeros[2]:getRP()==90)
                local rp=c.mHeros[3]:getRP()
                assert(rp==80 or rp==105)
                hit=hit or rp==105
                miss=miss or rp==80
            end
            assert(hit and miss)
            local solo=scenario(12011020,0,"10530600",3)
            assert(solo.mHeros[1]:getRP()==25)
        """)

    def test_final_floor_box_and_reset_label_work_without_next_node(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            register(lua, apk, "NewXZYY.XzyyMainScene")
            lua.execute("""
                package.loaded["Config.BddNodeModel"]=true
                package.loaded["Config.BddClearanceModel"]=true
                package.loaded["Config.BddRewardStarsRelation"]=true
                package.loaded["Config.VipModel"]=true
                package.loaded["Config.BddResetUseRelation"]=true
                BddRewardStarsRelation={items={{floorModelID=23,stars=9,reward="1124,0,325"}}}
                VipModel={items={[0]={resetBDDNum=1}}}
                BddResetUseRelation={items={{useDiamond=0}}}
                TR=function(value) return value end
                ModuleSub={ePracticeOneKeyBDD=2508}
                NetworkResData={modulePlayerIsOpen=function() return true,{openLv=45} end,
                    getPlayerInfo=function() return {Lv=80,Vip=0} end}
                LoadingWait={begin=function() end,ends=function() end}
                local node={setString=function() end,setPosition=function() end,setPositionY=function() end,
                    addChild=function() end,loadTextures=function() end,
                    getContentSize=function() return {width=100,height=100} end}
                cc.Sprite={create=function() return node end}
                cc.p=function() return {} end
                cc.size=function() return {} end
                ui.newButton=function() return node end
                local labels={}
                ui.newLabel=function(options) labels[#labels+1]=options.text return node end
                local box, request, refreshed
                package.loaded["Common.MessageBoxLayer"]={new=function(options) box=options return {} end}
                HttpRequest=function(module,method,args,done)
                    assert(module=="BddInfo" and method=="RewardBox")
                    request=args
                    done({Status=0})
                end
                local scene=setmetatable({mFTPText=node,mHighStar=node,mCurrentStarLable=node,mThreeButton=node,
                    Bgsprite=node,mBgSize={width=100,height=100},addChild=function() end,
                    refreshRed=function() end,requestInitData=function() refreshed=true end},
                    {__index=require("NewXZYY.XzyyMainScene")})
                local data={Status=0,Value={Info={FAP=123,StarCount=117,MaxStarCount=117,ResetCount=0,
                    NeedDrawReward=true,NeedReset=false,CanSweep=false,RewardFloor=23,
                    ClearedCount=39,BeforeFloorStarCount=9},BuffInfo={},BuyShopInfo={},NodeInfo={}}}
                scene:responseInitData(data)
                box.middleBtnCallback({removeFromParent=function() end})
                assert(request[1]==23 and request[2]==9 and refreshed)
                data.Value.Info.NeedDrawReward=false
                data.Value.Info.NeedReset=true
                data.Value.Info.RewardFloor=0
                scene:responseInitData(data)
                assert(string.find(table.concat(labels," "), "39",1,true))
            """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    R718LuaTest.apk = parser.parse_args().apk
    unittest.main(argv=[__file__], verbosity=2)
