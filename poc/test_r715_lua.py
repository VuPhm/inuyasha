#!/usr/bin/env python3
"""Exercise gold enhancement and the BDD shop indicator in signed APKs."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from test_r712_lua import cocos, register


class R715LuaTest(unittest.TestCase):
    def test_gold_level_cost_is_unavailable_without_a_vn_row(self):
        for apk_path, baseline in ((self.baseline, True), (self.apk, False)):
            with self.subTest(apk=apk_path.name), ZipFile(apk_path) as apk:
                lua = cocos(apk)
                register(lua, apk, "Equipment.EquipmentCommon", "Equipment.Module.EquipmentEnhanceLayer")
                lua.globals().baseline = baseline
                lua.execute("""
                    Fightattr = setmetatable({}, {__index = function(_, name) return name end})
                    package.loaded["Config.QualityModel"] = true
                    package.loaded["Config.EquipLvUpuseRelation"] = true
                    QualityModel = {items={[30]={colorLV=7}, [40]={colorLV=8}}}
                    EquipLvUpuseRelation = {items={[7]={[0]={lvUpUseNum=4200}, [1]={lvUpUseNum=5200}}}}
                    local equipment = require("Equipment.EquipmentCommon")
                    assert(equipment.getEnhanceCost({quality=30,Lv=0}, 2) == 9400)
                    local gold = {quality=40,Lv=80}
                    if baseline then
                        assert(not pcall(equipment.getEnhanceCost, gold))
                        return
                    end
                    assert(equipment.getEnhanceCost(gold) == nil)
                    local shown
                    local dummy = {setContentSize=function() end, align=function() end, addChild=function() end}
                    cc.size = function(w, h) return {width=w,height=h} end
                    display = {CENTER_TOP=0, CENTER=1}
                    ui.newScale9Sprite = function() return dummy end
                    ui.newButton = function() error("Unavailable equipment must not have purchase buttons") end
                    ui.newLabel = function(spec) shown = spec.text return dummy end
                    package.loaded["Common.Ctrl"].newNode = function() return dummy end
                    local layer = require("Equipment.Module.EquipmentEnhanceLayer")
                    assert(layer.createActionNode({size={width=550}}, gold) == dummy)
                    assert(shown:find("chưa có giá cường hóa", 1, true))
                """)

    def test_shop_indicator_uses_record_stars_and_clears_when_sold_out(self):
        with ZipFile(self.apk) as apk:
            lua = cocos(apk)
            register(lua, apk, "NewXZYY.XzyyMainScene")
            lua.execute("""
                package.loaded["Config.BddNodeModel"] = true
                package.loaded["Config.BddClearanceModel"] = true
                BddWraithShopRelation = {items={{ID=9, tabOrder=3, needNum=10,
                    needStarNum=10, perMaxNum=0, totalMaxNum=1}}}
                local shown
                local scene = setmetatable({mFeats=20, mMaxStar=54, mCurrentStar=0, mShopInfor={},
                    mRed={setVisible=function(_, state) shown=state end}}, {__index=require("NewXZYY.XzyyMainScene")})
                scene:refreshRed()
                assert(shown == true)
                scene:refreshRed(nil, 1500, {{ShopId=9, TodayBuyCount=1, TotalBuyCount=1}})
                assert(shown == false)
            """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    R715LuaTest.baseline = args.baseline
    R715LuaTest.apk = args.apk
    unittest.main(argv=[__file__], verbosity=2)
