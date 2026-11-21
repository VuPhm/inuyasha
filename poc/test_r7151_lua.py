#!/usr/bin/env python3
"""Verify the changed VN callbacks using Lua from the signed APK."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from test_r712_lua import cocos, lua_source, register


def function_block(apk, module, name, after):
    source = lua_source(apk, module)
    start = source.index(f"function {name}(")
    end = source.index(after, start)
    return source[start:end]


class R7151LuaTest(unittest.TestCase):
    def test_advance_callback_works_with_sparse_slot_list_and_three_steps(self):
        for apk_path, baseline in ((self.baseline, True), (self.apk, False)):
            with self.subTest(apk=apk_path.name), ZipFile(apk_path) as apk:
                lua = cocos(apk)
                lua.globals().baseline = baseline
                lua.execute("EquipmentScene = {}")
                lua.execute(function_block(
                    apk, "Equipment.EquipmentScene", "EquipmentScene:requestEquipExtra",
                    "--- 宝物强化数据请求",
                ))
                lua.execute("""
                    local requests, consumed, changed = 0, 0, 0
                    LoadingWait = {begin=function() end, ends=function() end}
                    NetworkResData = {modifyEquipItem=function(_, info) changed=info.Step end}
                    Equip = {getSlotList=function() return {{dataset={}}} end,
                             newEquipment=function(info) return info end}
                    clone = function(info) return info end
                    local view = {
                        data={Step=0},
                        handleRequest=function(self, info, callback)
                            assert(callback == nil)
                            self.data = info
                        end,
                    }
                    local scene = setmetatable({_subview=view,
                        deleteEquipmentInfoList=function() consumed=consumed+1 end,
                        loadPlayerAttrs=function() end,
                    }, {__index=EquipmentScene})
                    local response
                    HttpRequest = function(module, method, args, done)
                        requests = requests + 1
                        assert(module == "Equip" and method == "EquipStepUp" and args[1] == "target" and args[2] == "material")
                        if not baseline then assert(args[3] == view.data.Step) end
                        response = done
                    end
                    scene:requestEquipExtra(false, "target", {{Id="material"}})
                    scene:requestEquipExtra(false, "target", {{Id="material"}})
                    assert(requests == 1)
                    response({Status=-1118})
                    assert(consumed == 0 and changed == 0)
                    if baseline then
                        scene:requestEquipExtra(false, "target", {{Id="material"}})
                        assert(not pcall(response, {Status=0, Value={EquipInfo={Id="target",Step=1}}}))
                        return
                    end
                    for step=1,3 do
                        scene:requestEquipExtra(false, "target", {{Id="material"}})
                        response({Status=0, Value={EquipInfo={Id="target",Step=step}}})
                        assert(view.data.Step == step and consumed == step and changed == step)
                    end
                """)

    def test_formation_uses_server_stats_and_power_for_display(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            lua.execute("PlayerFormationLayer = {}")
            lua.execute(function_block(
                apk, "Formation.PlayerFormationLayer", "PlayerFormationLayer:refreshSlotAttr",
                "\nend",
            ) + "\nend")
            lua.execute("""
                local stats = {AP=125,DEF=250,HP=360,FAP=2235,FSP=500,
                    AP1=100, APR1=12500, AP2=0, APR2=0, APAdd=0, APHero=0, APHeroR=0,
                    DEF1=200, DEFR1=12500, DEF2=0, DEFR2=0, DEFAdd=0, DEFHero=0, DEFHeroR=0,
                    HP1=300, HPR1=12000, HP2=0, HPR2=0, HPAdd=0, HPHero=0, HPHeroR=0, APToHPHeroR=0}
                local labels = {}
                local scene = {mSelectedIndex=1, mFormationInfo={SlotInfos={{Property=stats}}},
                    slotHaveHero=function() return true end}
                for _, key in ipairs({"FAP", "SlotFAP", "SlotAP", "SlotDEF", "SlotHP"}) do
                    scene["m"..key.."Label"] = {setString=function(_, result) labels[key] = result end}
                end
                PlayerFormationLayer.refreshSlotAttr(scene)
                assert(labels.SlotAP == "125" and labels.SlotDEF == "250" and labels.SlotHP == "360")
                assert(labels.FAP:find("2235", 1, true))
            """)

    def test_red_naohi_preview_includes_already_applied_steps(self):
        for apk_path, baseline in ((self.baseline, True), (self.apk, False)):
            with self.subTest(apk=apk_path.name), ZipFile(apk_path) as apk:
                lua = cocos(apk)
                lua.globals().baseline = baseline
                lua.execute("EquipmentExtraLayer = {}")
                lua.execute(function_block(
                    apk, "Equipment.Module.EquipmentExtraLayer", "EquipmentExtraLayer:convertData",
                    "function EquipmentExtraLayer:createInfoNode",
                ))
                lua.execute("""
                    table.maxn = function(tbl) return #tbl end
                    local steps = {
                        [0]={AP=0,HP=0,DEF=0}, [1]={AP=1400,HP=0,DEF=0}, [2]={AP=2800,HP=0,DEF=0},
                    }
                    EquipStepRelation={items={[13010701]=steps}}
                    local sword={EquipModelId=13010701,AP=419,APUP=42,HP=0,HPUP=0,DEF=0,DEFUP=0,
                        Lv=70,Step=0,getStepRelation=function() return steps end}
                    local current, nextStats = EquipmentExtraLayer.convertData({}, sword)
                    assert(current[1]:find("3359", 1, true) and nextStats[1] == "4759")
                    sword.Step=1
                    current, nextStats = EquipmentExtraLayer.convertData({}, sword)
                    if baseline then
                        assert(current[1]:find("3359", 1, true) and nextStats[1] == "4759")
                    else
                        assert(current[1]:find("4759", 1, true) and nextStats[1] == "6159")
                    end
                """)

    def test_equip_step_count_displays_the_exact_cost(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            lua.execute("Ctrl = {}")
            lua.execute(function_block(apk, "Common.Ctrl", "Ctrl.newCountNode", "\nend") + "\nend")
            layer = lua_source(apk, "Equipment.Module.EquipmentExtraLayer")
            self.assertIn("value= gold_cost,\n            exact= true,", layer)
            self.assertIn('needsEnhancement and string.format("Cần Cường Hóa Lv%d", needLv)', layer)
            lua.execute("""
                local count
                ResourcetypeSub={eGold=2,eDiamond=1}
                display={}
                NumberToBigUnit=function() return "2 M" end
                string.formatNumberThousands=function(value) return tostring(value) end
                Ctrl.getItemImage=function() end
                Ctrl.linearLayout=function() return {} end
                ui={newSprite=function() return {} end,
                    newLabel=function(params)
                        count=params.text
                        return {setString=function(_, value) count=value end}
                    end}
                local cost = Ctrl.newCountNode({type=2, value=2400000, exact=true})
                assert(count=="2400000" and cost:getValue()==2400000)
                cost:setValue(2800000, false)
                assert(count=="2800000" and cost:getValue()==2800000)
                Ctrl.newCountNode({type=2, value=2400000})
                assert(count=="2 M")
            """)

    def test_bdd_settlement_sends_dense_array_and_refreshes_on_rejected_token(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            register(lua, apk, "Adventure.BattleSettleLayer")
            lua.execute("""
                package.loaded["Adventure.NightmareDataCache"] = true
                package.loaded["Adventure.BattleDataCache"] = true
                LoadingWait={begin=function() end, ends=function() end}
                handler=function(self, fn) return function(value) return fn(self, value) end end
                local closed, payload
                local scene = setmetatable({mXZYYData={NodeId=1111,Nandu=3,FightToken="token"},
                    mFightResult={}, onClose=function() closed=true end}, {__index=require("Adventure.BattleSettleLayer")})
                HttpRequest = function(module, method, args, done)
                    assert(module=="BddInfo" and method=="Fight")
                    payload=args
                    done({Status=-39})
                end
                scene:requestXZYY()
                assert(closed and #payload==6 and payload[3]==false and payload[4]=="" and payload[6]=="token")
            """)

    def test_bdd_sweep_passes_three_rows_and_nine_stars_to_popup(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            register(lua, apk, "NewXZYY.XzyyMainScene")
            lua.execute("""
                package.loaded["Config.BddNodeModel"] = true
                package.loaded["Config.BddClearanceModel"] = true
                LoadingWait = {ends=function() end}
                handler = function(self, fn) return function(...) return fn(self, ...) end end
                local popup
                package.loaded["NewXZYY.XzyyOneKeyLayer"] = {
                    new=function(options) popup=options return {} end,
                }
                local sceneNode = {addChild=function() end}
                local director = {getRunningScene=function() return sceneNode end}
                cc.Director={getInstance=function() return director end}
                local scene = setmetatable({mFloor=1}, {__index=require("NewXZYY.XzyyMainScene")})
                scene:responseOneKey({Status=0,Value={
                    Info={StarCount=9,MaxStarCount=54,CanSweep=false,NeedSelectBuff=true},
                    BaseGetGameResourceList={{}, {}, {}}, BoxGetGameResourceList={}, SweepStarCount=9,
                    NodeInfo={{Id=1211}}, Catalogue={}, BuffInfo={}, BuyShopInfo={},
                }})
                assert(scene.mCurrentStar==9 and scene.mMaxStar==54 and scene.mCanSweep==false)
                assert(popup.gainedStars==9 and #popup.baseGetGameResourceList==3 and popup.currentFloor==1)
            """)

    def test_bdd_prepare_shows_the_catalogue_stage_number(self):
        for apk_path, baseline in ((self.baseline, True), (self.apk, False)):
            with self.subTest(apk=apk_path.name), ZipFile(apk_path) as apk:
                lua = cocos(apk)
                source = lua_source(apk, "NewXZYY.XzyyPrepareFightLayer")
                title = next(line.strip()[len("text = "):-1] for line in source.splitlines()
                             if "text = string.format" in line and "BddNodeModel.items[NodeId].name" in line)
                make_title = lua.execute("""
                    return function(NodeId, floorId)
                        local TR = function(value) return value end
                        local BddNodeModel={items={[NodeId]={floorModelID=floorId,name="NPC"}}}
                        return """ + title + "\nend")
                for node, floor, expected in ((1111, 11, 1), (1211, 12, 4), (1613, 16, 18)):
                    number = node % 10 if baseline else expected
                    self.assertIn(f"第{number}关", make_title(node, floor))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    R7151LuaTest.baseline = args.baseline
    R7151LuaTest.apk = args.apk
    unittest.main(argv=[__file__], verbosity=2)
