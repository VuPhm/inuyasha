"""Delta coverage for R7.23 (TASK-M05) VN combat buffs Slice 1A."""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from combat_effects import BattleEffects, CLEAR_DEBUFFS, HPDOT, supports_talent_buff  # noqa: E402
from combat_sim import CreateRandom, simulate_fight_info  # noqa: E402
from emulator import GameEmulatorState  # noqa: E402


@lru_cache(maxsize=1)
def game():
    return GameEmulatorState(persist=False).game_data


def unit(model, hp=100_000, ap=1000, def_=0, rp=0, buffs="", na=None, ra=None, hit=10000):
    row = game()["heroes"][str(model)]
    return {
        "HeroModelId": model,
        "HP": hp,
        "TotalHp": hp,
        "OpeningHP": hp,
        "AP": ap,
        "OriginalAP": ap,
        "DEF": def_,
        "OriginalDEF": def_,
        "RP": rp,
        "NAId": row["NAID"] if na is None else na,
        "RAId": row["RAID"] if ra is None else ra,
        "BuffList": buffs,
        "HIT": hit,
        "FSP": 500,
    }


def wave(allies, enemies, seed=4, *, npc_first=False):
    h = [{} for _ in range(12)]
    for pos, u in allies.items():
        h[pos - 1] = u
    for pos, u in enemies.items():
        h[pos - 1] = u
    return {
        "Heros": h,
        "TeamData": [dict(Fsp=500, Fap=10), dict(Fsp=500, Fap=11 if npc_first else 9)],
        "RandNum": seed,
        "Pets": [],
        "IsPVP": False,
    }


class R723CombatSlice1ATest(unittest.TestCase):
    def sim(self, allies, enemies, *, max_rounds=1, seed=4, npc_first=False):
        data = {"FightObjs": [wave(allies, enemies, seed=seed, npc_first=npc_first)]}
        res = simulate_fight_info(data, game()["attacks"], max_rounds=max_rounds, buffs_cfg=game()["combat_buffs"])
        return res, {row["PosId"]: row for row in res.verify_data["hp"][0]}

    def test_naraku_poison_modify_add_value_duration_cleanse_and_state_triggers(self):
        # Naraku (12013005) AP=1000 with RA poison 20440606 + 10270600 (+36% DAMADDR vs HPDOT)
        # Child 14040000 deals ceil(OriginalAP * 0.20) = 200 HP per poisoned unit turn for 2 caster turns.
        naraku = unit(12013005, ap=1000, rp=100, buffs="20440606", na=1001015, ra=1002008)
        enemy = unit(12011005, hp=50_000, ap=100, rp=0, na=1001015, ra=0)
        effects = BattleEffects({1: naraku, 9: enemy}, game()["attacks"], game()["combat_buffs"], CreateRandom(4))

        with patch.object(effects.rng, "randrange", return_value=0):
            # Naraku RA attaches 14040000 with modify_value=200 (override_add_value=20000) and turns=2+1
            effects.apply(1, 1, 9, [9], (3,), (5,), defaultdict(Counter), target_only=True)
        self.assertTrue(effects.has(9, HPDOT))
        poison_eff = next(e for e in effects.active[9] if e.row["addAttrEnum"] == HPDOT)
        self.assertEqual(poison_eff.override_add_value, 20000)
        self.assertEqual(poison_eff.turns, 3)

        # End of Naraku's Turn 1: ticks 3 -> 2
        effects.tick(1, before=False)
        self.assertEqual(poison_eff.turns, 2)

        # Enemy Turn 1: poison ticks (-200 HP); enemy's own tick doesn't decrement Naraku-sourced poison
        effects.apply(9, 9, None, [1], (1, 2), (5,), defaultdict(Counter), target_only=False)
        self.assertEqual(enemy["HP"], 49_800)
        effects.tick(9, before=False)
        self.assertTrue(effects.has(9, HPDOT))

        # Naraku Turn 2 ends (2 -> 1), Enemy Turn 2 takes 2nd poison tick (-200 HP -> 49,600)
        effects.tick(1, before=False)
        self.assertEqual(poison_eff.turns, 1)
        effects.apply(9, 9, None, [1], (1, 2), (5,), defaultdict(Counter), target_only=False)
        self.assertEqual(enemy["HP"], 49_600)

        # Naraku Turn 3 ends (1 -> 0): expires cleanly
        effects.tick(1, before=False)
        self.assertFalse(effects.has(9, HPDOT))

        # Cleanse via CLEAR_DEBUFFS (499) removes poison
        with patch.object(effects.rng, "randrange", return_value=0):
            effects.apply(1, 1, 9, [9], (3,), (5,), defaultdict(Counter), target_only=True)
        self.assertTrue(effects.has(9, HPDOT))
        clean_row = next(r for r in game()["combat_buffs"].values() if r["addAttrEnum"] == CLEAR_DEBUFFS and r["targetCampEnum"] == 0)
        effects._add(1, clean_row, 3)
        effects.apply(1, 1, 9, [9], (3,), (5,), defaultdict(Counter), target_only=True)
        self.assertFalse(effects.has(9, HPDOT))

        # Test 10270600 (+36% DAMADDR when opposite has HPDOT) and 10261000 (+50% DAMCUTR when attacker has HPDOT)
        naraku_t = unit(12013005, ap=1000, buffs="10270600,10261000")
        e_poisoned = unit(12011005, buffs="")
        e_clean = unit(12011005, buffs="")
        fx = BattleEffects({1: naraku_t, 7: e_poisoned, 8: e_clean}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        fx._apply_child(game()["combat_buffs"]["14040000"], 7, 1, before_calc=False, modify_value=200)

        mods_vs_p = defaultdict(Counter)
        fx.apply(1, 1, 7, [7], (1, 2), (1,), mods_vs_p, compared=True)
        self.assertEqual(mods_vs_p[1]["DAMADDR"], 3600)
        mods_vs_c = defaultdict(Counter)
        fx.apply(1, 1, 8, [8], (1, 2), (1,), mods_vs_c, compared=True)
        self.assertEqual(mods_vs_c[1]["DAMADDR"], 0)

        mods_def = defaultdict(Counter)
        fx.apply(1, 7, 7, [7], (4, 5), (1,), mods_def, compared=True)
        self.assertEqual(mods_def[1]["DAMCUTR"], 5000)

    def test_kaguya_poison_rp_drain_ordering_and_immunity(self):
        # FightAttack.lua:857 (type=3 compared after-calc) runs BEFORE 871 (type=6 target-only after-calc)
        # So Kaguya's 10621000 (-75 RP if target has HPDOT) must NOT fire on the hit that first applies poison!
        atk_ra = 1002050  # type=0, factor=10000, buffList=''
        kaguya = unit(12013004, hp=50_000, ap=500, rp=100, buffs="10621000,20441026", na=1001015, ra=atk_ra)
        enemy = unit(12011005, hp=100_000, ap=10, rp=100, na=0, ra=0)

        # Round 1: Kaguya uses RA (1002203 would hit all; our single-target RA hits slot 9):
        # At line 857 enemy is NOT poisoned yet -> 10621000 does NOT drain RP -> enemy ends Round 1 with > 0 RP (actually >= 100)
        _, after_r1 = self.sim({1: kaguya}, {9: enemy}, max_rounds=1)
        self.assertGreaterEqual(after_r1[9]["RP"], 100)

        # Now start with enemy ALREADY poisoned before Kaguya casts RA -> 10621000 drains 75 RP before 20441026 re-applies poison
        kaguya2 = unit(12013004, hp=50_000, ap=500, rp=100, buffs="10621000")
        enemy2 = unit(12011005, hp=100_000, ap=10, rp=100)
        fx = BattleEffects({1: kaguya2, 9: enemy2}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        fx._apply_child(game()["combat_buffs"]["14040000"], 9, 1, before_calc=False, modify_value=100)
        fx.apply(1, 1, 9, [9], (1, 3), (5,), defaultdict(Counter), compared=True)
        self.assertEqual(enemy2["RP"], 25)

        # 10060000 (IMMUNE_RAGE_LOSS 706) blocks 10621000 drain
        enemy_imm = unit(12011005, hp=100_000, ap=10, rp=100, buffs="10060000")
        fx2 = BattleEffects({1: kaguya2, 9: enemy_imm}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        fx2._apply_child(game()["combat_buffs"]["14040000"], 9, 1, before_calc=False, modify_value=100)
        fx2.apply(1, 1, 9, [9], (1, 3), (5,), defaultdict(Counter), compared=True)
        self.assertEqual(enemy_imm["RP"], 100)

    def test_lifesteal_type7_self_and_most_injured_ally(self):
        # Takemaru +8 (10710600): type=7, c1=2 (NA), c2=5, camp=3, ra=400, rv=4500 (45% of DAM)
        atk_na = 1001015  # single-target normal attack (factor=10000 or 9000..11000, buffList='')
        factor = int(game()["attacks"][str(atk_na)]["factor"]) / 10000.0
        takemaru = unit(12013003, hp=5000, ap=1000, def_=0, rp=0, buffs="10710600", na=atk_na, ra=0)
        takemaru["TotalHp"] = 10_000
        enemy = unit(12011005, hp=10_000, ap=0, def_=0, na=0, ra=0)
        enemy["DOD"] = -10000  # force 0 dodge

        # With seed=4 and CRI=0, expected_dmg = ceil(1000 * factor) and heal = ceil(expected_dmg * 0.45)
        expected_dmg = int(-(-1000 * factor // 1))
        expected_heal = int(-(-expected_dmg * 0.45 // 1))
        _, r = self.sim({1: takemaru}, {9: enemy}, max_rounds=1, seed=4)
        self.assertEqual(10_000 - r[9]["HP"], expected_dmg)
        self.assertEqual(r[1]["HP"], 5000 + expected_heal)

        # LOCK_HEALING (505) blocks lifesteal
        fx = BattleEffects({1: takemaru, 9: enemy}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        takemaru["DAM"] = 2000
        takemaru["HP"] = 5000
        lock_heal_row = {
            "ID": 999505,
            "typeEnum": 2,
            "targetCampEnum": 3,
            "triggerCondition2": 1,
            "addAttrEnum": 505,
            "maxTime": -1,
            "maxNum": -1,
            "overlayNum": -1,
            "isDebuff": True,
        }
        fx._add(1, lock_heal_row, 3)
        fx.apply(1, 1, None, [9], (1, 2), (5,), defaultdict(Counter), target_only=False)
        self.assertEqual(takemaru["HP"], 5000)

        # 10670800: camp=1, te=12 (most injured ally including self), rv=4000 (40% DAM)
        healer = unit(12011004, hp=9000, ap=1000, buffs="10670800")
        healer["TotalHp"] = 10_000  # loss = 1000
        ally = unit(12011005, hp=6000, ap=1000)
        ally["TotalHp"] = 10_000  # loss = 4000 (most injured)
        fx2 = BattleEffects({1: healer, 4: ally, 9: enemy}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        healer["DAM"] = 3000
        fx2.apply(1, 1, None, [9], (1, 3), (5,), defaultdict(Counter), target_only=False)
        self.assertEqual(ally["HP"], 6000 + 1200)
        self.assertEqual(healer["HP"], 9000)

    def test_row_buffs_kanade_miroku_and_toutousai(self):
        # Kanade Hime +8 (20600600, te=4 back row -> 12190200 CRI +20%) & Miroku RA (20480400, te=4 -> 12440000 AP +15% OrigAP)
        # & Toutousai RA (20490400, te=3 front row -> 12060400 DEFR +40%)
        front1 = unit(12011004, ap=2000, def_=1000, buffs="20600600,20480400,20490400", na=1001015, ra=1002050)
        front2 = unit(12011005, ap=500, def_=500, na=1001015, ra=0)
        back4 = unit(12011007, ap=500, def_=500, na=1001015, ra=0)
        back5 = unit(12011006, ap=500, def_=500, na=1001015, ra=0)
        enemy = unit(12011005, na=0, ra=0)
        fx = BattleEffects(
            {1: front1, 2: front2, 4: back4, 5: back5, 9: enemy},
            game()["attacks"],
            game()["combat_buffs"],
            CreateRandom(1),
        )
        fx.apply(1, 1, None, [9], (1, 3), (5,), defaultdict(Counter), target_only=False)
        mods_atk = defaultdict(Counter)
        mods_def = defaultdict(Counter)
        for p in (1, 2, 4, 5):
            fx.apply(p, p, None, [9], (1, 2), (1,), mods_atk)
            fx.apply(p, 9, 9, [9], (4, 5), (1,), mods_def)

        # Back row (4, 5) received +2000 CRI (c1=1 attack) and +ceil(2000 * 0.15)=300 AP (12440000 c1=4 defense)
        for p in (4, 5):
            self.assertEqual(mods_atk[p]["CRI"], 2000)
            self.assertEqual(mods_def[p]["AP"], 300)
            self.assertEqual(mods_def[p]["DEFR"], 0)
        # Front row (1, 2) received +4000 DEFR (12060400 c1=4 defense) only
        for p in (1, 2):
            self.assertEqual(mods_def[p]["DEFR"], 4000)
            self.assertEqual(mods_atk[p]["CRI"], 0)
            self.assertEqual(mods_def[p]["AP"], 0)

        # Fallback: when back row is empty, te=4 falls back to front row per TargetModeFunction.lua:382
        fx_front_only = BattleEffects(
            {1: unit(12011004, buffs="20600600", na=1001015, ra=1002050), 9: enemy},
            game()["attacks"],
            game()["combat_buffs"],
            CreateRandom(1),
        )
        fx_front_only.apply(1, 1, None, [9], (1, 3), (5,), defaultdict(Counter), target_only=False)
        mods_fb = defaultdict(Counter)
        fx_front_only.apply(1, 1, None, [9], (1, 2), (1,), mods_fb)
        self.assertEqual(mods_fb[1]["CRI"], 2000)

    def test_sure_hit_crit_immunity_bcpr_direct_hp_and_fightinfo_filtering(self):
        # 20020000 (Naraku +5): when hit by E1, attaches 12221000 (+10000 TEN, turns=1, before_action=True)
        # Protects Naraku against E2 in the same round, and expires when E1's next turn starts!
        naraku = unit(12013005, buffs="20020000")
        e1 = unit(12011005)
        e2 = unit(12011006)
        fx = BattleEffects({1: naraku, 7: e1, 8: e2}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))

        # E1 attacks Naraku (phase 1 BeforeCalculation -> compared=False attaches 12221000)
        fx.apply(1, 7, 7, [7], (4, 5), (1,), defaultdict(Counter), compared=False)
        crit_imm = next(e for e in fx.active[1] if e.row["ID"] == 12221000)
        self.assertTrue(crit_imm.before_action)
        self.assertEqual(crit_imm.turns, 1)
        self.assertEqual(crit_imm.source, 7)

        # E2 attacks Naraku later: 12221000 grants +10000 TEN!
        mods_e2 = defaultdict(Counter)
        fx.apply(1, 8, 8, [8], (4, 5), (1,), mods_e2, compared=False)
        self.assertEqual(mods_e2[1]["TEN"], 10000)

        # Next time E1 acts (tick(7, before=True)): E1's 12221000 expires; E2's copy expires on tick(8, before=True)
        self.assertEqual([e.source for e in fx.active[1] if e.row["ID"] == 12221000], [7, 8])
        fx.tick(7, before=True)
        self.assertEqual([e.source for e in fx.active[1] if e.row["ID"] == 12221000], [8])
        fx.tick(8, before=True)
        self.assertFalse(any(e.row["ID"] == 12221000 for e in fx.active[1]))

        # 20010000 (Midoriko +5): attaches 12101000 (HIT +10000, turns=1, before_action=True)
        midoriko = unit(12012004, buffs="20010000")
        fx_m = BattleEffects({1: midoriko, 7: e1}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        fx_m.apply(1, 1, None, [7], (1, 2), (1,), defaultdict(Counter))
        sure_hit = next(e for e in fx_m.active[1] if e.row["ID"] == 12101000)
        self.assertTrue(sure_hit.before_action)
        self.assertEqual(sure_hit.turns, 1)

        # 20300807 -> 12430750 (c1=4, ae=407 BCPR -75%): attaches cleanly and is skipped by c1=8 heal (per FightAttack.lua:429)
        tdt = unit(12015022, buffs="20300807")
        vic = unit(12011005)
        fx_b = BattleEffects({1: tdt, 9: vic}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        with patch.object(fx_b.rng, "randrange", return_value=0):
            fx_b.apply(1, 1, 9, [9], (1, 3), (5,), defaultdict(Counter), target_only=True)
        self.assertTrue(any(e.row["ID"] == 12430750 for e in fx_b.active[9]))
        heal_mods = defaultdict(Counter)
        fx_b.apply(9, 1, 1, [1], (8,), (1,), heal_mods)  # is_heal passes active_defense=(8,), matching FightAttack.lua:429
        self.assertEqual(heal_mods[9]["BCPR"], 0)
        atk_mods = defaultdict(Counter)
        fx_b.apply(9, 1, 1, [1], (4, 5), (1,), atk_mods)
        self.assertEqual(atk_mods[9]["BCPR"], -7500)

        # Direct HP buffs (addAttr=201): 19010200 (-20% TotalHp), 10690600 (+60% AP), 10660400 (+20% AP to most injured),
        # 10340151 (+5% TotalHp after crit), and kill-rage 10280000 (+25 RP on target HP==0)
        boss = unit(12011004, hp=10_000, ap=500, buffs="19010200,10690600,10660400,10340151,10280000")
        boss["TotalHp"] = 10_000
        boss["HP"] = 8_000
        ally = unit(12011005, hp=4_000)
        ally["TotalHp"] = 10_000
        dead_foe = unit(12011006, hp=0)
        dead_foe["TotalHp"] = 10_000
        live_foe = unit(12011007, hp=10_000)
        fx_hp = BattleEffects(
            {1: boss, 2: ally, 9: live_foe, 10: dead_foe},
            game()["attacks"],
            game()["combat_buffs"],
            CreateRandom(1),
        )
        fx_hp.apply(1, 1, 9, [9], (1, 3), (5,), defaultdict(Counter), target_only=True)
        self.assertEqual(live_foe["HP"], 8_000)  # 19010200: -2000
        fx_hp.apply(1, 1, None, [9], (1, 3), (5,), defaultdict(Counter), target_only=False)
        self.assertEqual(boss["HP"], 8_300)  # 10690600: +60% of 500 AP = +300
        fx_hp.apply(1, 1, None, [9], (1, 2), (5,), defaultdict(Counter), target_only=False)
        self.assertEqual(ally["HP"], 4_100)  # 10660400: +20% of 500 AP = +100
        with patch.object(fx_hp.rng, "randrange", return_value=0):
            fx_hp.apply(1, 9, 9, [9], (4, 5), (2,), defaultdict(Counter))
        self.assertEqual(boss["HP"], 8_800)  # 10340151: +5% of 10000 = +500
        fx_hp.apply(1, 1, 10, [10], (1, 2), (5,), defaultdict(Counter), compared=True)
        self.assertEqual(boss["RP"], 25)  # 10280000 on dead_foe HP==0

        # Verify ProfileStore._hero_fight_obj emits Slice 1A talents & keeps Slice 1B deferred
        p = GameEmulatorState(persist=False).profiles["normal"]
        naraku_obj = p._hero_fight_obj(game()["heroes"]["12013005"], step=10)
        naraku_bl = set(naraku_obj["BuffList"].split(","))
        for bid in ("20020000", "10270600", "10261000"):
            self.assertIn(bid, naraku_bl)
        self.assertTrue(supports_talent_buff(game()["combat_buffs"]["20440606"], game()["combat_buffs"]))
        kaguya_obj = p._hero_fight_obj(game()["heroes"]["12013004"], step=10)
        for bid in ("20310606", "10621000"):
            self.assertIn(bid, kaguya_obj["BuffList"].split(","))
        kanade_obj = p._hero_fight_obj(game()["heroes"]["12012003"], step=10)
        self.assertIn("20600600", kanade_obj["BuffList"].split(","))
        takemaru_obj = p._hero_fight_obj(game()["heroes"]["12013003"], step=10)
        self.assertIn("10710600", takemaru_obj["BuffList"].split(","))
        self.assertIn("20070600", takemaru_obj["BuffList"].split(","))
        # Slice 1B now enabled in R7.24 as well
        for bid in ("20050600", "10290000", "20530600", "20590600", "20070600", "20180600"):
            self.assertTrue(supports_talent_buff(game()["combat_buffs"][bid], game()["combat_buffs"]))


if __name__ == "__main__":
    unittest.main()
