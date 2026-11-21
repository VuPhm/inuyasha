#!/usr/bin/env python3
"""Replay VN combat effects in the original Lua engine embedded in the signed APK."""

import argparse
from pathlib import Path
import unittest
from zipfile import ZipFile

import test_r716_lua


class R717LuaTest(unittest.TestCase):
    def check(self, script):
        with ZipFile(self.apk) as apk:
            lua = test_r716_lua.R716LuaTest().combat(apk)
            lua.execute("""
                function buff(calc,pos,id)
                    local stacks, time = 0, nil
                    for _, effect in ipairs(calc.mHeros[pos]:getBuffInfo()) do
                        if effect.buffModelInfo.ID == id then
                            stacks, time = stacks+1, effect.buffModelInfo.maxTime
                        end
                    end
                    return stacks, time
                end
            """)
            lua.execute(script)

    def test_talent_stuns_enemy_then_expires_and_immunity_blocks_it(self):
        self.check("""
            local c=scenario(12011006,100,"20210401",3)
            local stacks,duration=buff(c,9,14010000)
            assert(stacks==1 and duration==1)
            local before=c.mHeros[1]:getHP()
            c:fightATimes({autoPlay=true})
            assert(c.mHeros[1]:getHP()==before and buff(c,9,14010000)==0)
            local immune=scenario(12011006,100,"20210401",3,{enemyBuffs="10010000"})
            assert(buff(immune,9,14010000)==0)
            immune:fightATimes({autoPlay=true})
            assert(immune.mHeros[1]:getHP()<before and immune.mHeros[9]:getRP()==0)
        """)

    def test_skill_crit_buff_ticks_on_caster_and_attack_bonus_caps_at_three(self):
        self.check("""
            local c=scenario(12011004,100,"",1)
            local stacks,duration=buff(c,1,12190400)
            assert(stacks==1 and duration==2)
            for step=2,5 do
                c:fightATimes({autoPlay=true})
                local n,t=buff(c,1,12190400)
                if step==2 then assert(n==1 and t==2) end
                if step==3 or step==4 then assert(n==1 and t==1) end
                if step==5 then assert(n==0) end
            end
            local stack=scenario(12011004,0,"20171000,20171000",1,{enemyRP=0})
            for step=1,9 do
                if step>1 then stack:fightATimes({autoPlay=true}) end
                assert(buff(stack,1,14081000)==math.min(3,math.floor((step+1)/2)))
            end
        """)

    def test_stock_rage_debuff_and_immunity_allow_or_block_the_next_rage_skill(self):
        self.check("""
            local cut=scenario(12011005,100,"10450836",3)
            local base=scenario(12011005,100,"",3)
            assert(base.mHeros[9]:getRP()-cut.mHeros[9]:getRP()==25)
            cut:fightATimes({autoPlay=true})
            assert(cut.mHeros[9]:getRP()>0)
            local immune=scenario(12011005,100,"10450836",3,{enemyBuffs="10060000"})
            assert(immune.mHeros[9]:getRP()==base.mHeros[9]:getRP())
            immune:fightATimes({autoPlay=true})
            assert(immune.mHeros[9]:getRP()==0)
        """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    R717LuaTest.apk = parser.parse_args().apk
    unittest.main(argv=[__file__], verbosity=2)
