#!/usr/bin/env python3
"""Verify the actual reward popup Lua and 4918 presentation bundled in standalone APKs."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

from test_r712_lua import cocos, register


class RewardLuaTest(unittest.TestCase):
    def test_choice_popup_keeps_banner_snapshot_and_retries_errors(self):
        for apk_path, hotfix in ((self.old_apk, False), (self.hotfix_apk, True)):
            with self.subTest(apk=apk_path.name), ZipFile(apk_path) as apk:
                lua = cocos(apk)
                register(lua, apk, "TimedActivity.TimedRecruitChoiceBoxLayer")
                lua.globals().hotfix = hotfix
                lua.execute("""
                    package.loaded["Config.GoodsOutputRelation"] = true
                    local ctrl = require("Common.Ctrl")
                    ctrl.newFrame = node
                    local shown = 0
                    ctrl.showRewardList = function(result)
                        assert(result.BaseGetGameResourceList[1].Hero[1].HeroModelId == 12011004)
                        shown = shown + 1
                    end
                    ui.newEffect = node
                    display = {cx = 0, cy = 0}
                    dump = function() end
                    LoadingWait = {begin = function() end, ends = function() end}
                    local sends, onResponse = 0
                    HttpRequest = function(module, method, data, callback)
                        assert(module == "TimedRecruitInfo" and method == "DrawGoldHero")
                        assert(data[1] == 12011004)
                        if hotfix then
                            assert(#data == 3 and data[2] == 81 and data[3] == "timed_recruit:81:test")
                        else
                            assert(#data == 1)
                        end
                        sends = sends + 1
                        onResponse = callback
                    end
                    local snapshot = {ActivityEnumId = 81, EventInstanceId = "timed_recruit:81:test", DrawGoldHero = 0}
                    local picker = require("TimedActivity.TimedRecruitChoiceBoxLayer").new({data = snapshot})
                    snapshot.ActivityEnumId = 82
                    picker:requestDrawGoldHero(12011004)
                    if hotfix then picker:requestDrawGoldHero(12011004) end
                    assert(sends == 1)
                    onResponse({Status = -2005, Value = {}})
                    assert(picker.removed == nil and snapshot.DrawGoldHero == 0 and shown == 0)
                    picker:requestDrawGoldHero(12011004)
                    assert(sends == 2)
                    onResponse({Status = 0, Value = {BaseGetGameResourceList = {{Hero = {{HeroModelId = 12011004}}}}}})
                    assert(picker.removed == 1 and snapshot.DrawGoldHero == 1 and shown == 1)
                """)

    def test_4918_uses_per_row_count_and_server_claimability(self):
        with ZipFile(self.hotfix_apk) as apk:
            lua = cocos(apk)
            register(lua, apk, "OpenActivity.SuccessTargetLayer")
            lua.execute("""
                SuccessTargetModel = {items = {[19] = {modelID = 4918}}}
                local layer = require("OpenActivity.SuccessTargetLayer")
                local row = {targetID = 19, sequence = 2, completeCondition1 = 7500}
                local target = {SequenceInfo = {["1"] = 4, ["2"] = 3}, ReachedNum = 8900,
                                Claimable = {["1"] = false, ["2"] = false}, DrawNums = {}}
                local count, required = layer:targetProgress(target, row)
                assert(count == 3 and required == 4 and not layer:canClaimTarget(target, 2))
                row.sequence = 1
                assert(layer:targetProgress(target, row) == 4)
                assert(not layer:canClaimTarget(target, 1))
                target.Claimable["1"] = true
                assert(layer:canClaimTarget(target, 1))
                target.DrawNums[1] = 1
                assert(not layer:canClaimTarget(target, 1) and target.ReachedNum == 8900)
            """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("old_apk", type=Path)
    parser.add_argument("hotfix_apk", type=Path)
    args = parser.parse_args()
    RewardLuaTest.old_apk = args.old_apk
    RewardLuaTest.hotfix_apk = args.hotfix_apk
    unittest.main(argv=[__file__], verbosity=2)
