"""Delta coverage for VN combat effects, action order and battle isolation."""

import copy
from collections import Counter, defaultdict
from functools import lru_cache
import random
import unittest
from unittest.mock import patch

from combat_effects import BattleEffects, IMMUNE_RAGE_LOSS, SILENCE, supports_talent_buff
from combat_sim import simulate_fight_info
from emulator import GameEmulatorState


@lru_cache(maxsize=1)
def game():
    return GameEmulatorState(persist=False).game_data


def unit(model, hp=100_000, ap=100, rp=0, buffs=""):
    row = game()["heroes"][str(model)]
    return {"HeroModelId": model, "HP": hp, "TotalHp": hp, "AP": ap, "DEF": 0, "RP": rp,
            "NAId": row["NAID"], "RAId": row["RAID"], "BuffList": buffs, "HIT": 10000, "FSP": 500}


def wave(ally, enemy, seed=4, *, npc_first=False):
    return {"Heros": [ally] + [{}] * 7 + [enemy] + [{}] * 3,
            "TeamData": [dict(Fsp=500, Fap=10), dict(Fsp=500, Fap=11 if npc_first else 9)],
            "RandNum": seed, "Pets": [], "IsPVP": False}


class R717DeltaTest(unittest.TestCase):
    def simulate(self, attacker, enemy, **kwargs):
        npc_first = kwargs.pop("npc_first", False)
        data = {"FightObjs": [wave(attacker, enemy, seed=kwargs.pop("seed", 4), npc_first=npc_first)]}
        result = simulate_fight_info(data, game()["attacks"], buffs_cfg=game()["combat_buffs"], **kwargs)
        return result, {row["PosId"]: row for row in result.verify_data["hp"][0]}

    def effects(self, ally, enemy):
        for row in ally, enemy:
            row["OpeningHP"] = row["HP"]
        return BattleEffects({1: ally, 9: enemy}, game()["attacks"], game()["combat_buffs"], random.Random(4))

    def test_npc_silence_falls_back_to_normal_and_immunity_keeps_rage_skill(self):
        # Seed 4 makes Midoriko's actual 68% silence land after her opening skill.
        midoriko = unit(12012004, rp=100)
        kagome = unit(12011005, rp=100)
        _, silenced = self.simulate(midoriko, kagome, max_rounds=1)
        self.assertGreaterEqual(silenced[9]["RP"], 125)
        kagome["BuffList"] = "10020000"
        _, immune = self.simulate(midoriko, kagome, max_rounds=1)
        self.assertEqual(immune[9]["RP"], 0)
        self.assertLess(immune[1]["HP"], silenced[1]["HP"])
        _, enemy_cast = self.simulate(unit(12011005, rp=100), midoriko, max_rounds=1, npc_first=True)
        self.assertGreaterEqual(enemy_cast[1]["RP"], 125)

    def test_stun_skips_actions_and_overlapping_silence_expires_on_caster_turns(self):
        m = unit(12011006, rp=100, buffs="20210401")
        enemy = unit(12011005, rp=100)
        _, stunned = self.simulate(m, enemy, seed=3, max_rounds=1)
        self.assertEqual(stunned[1]["HP"], 100000)
        self.assertGreaterEqual(stunned[9]["RP"], 100)
        enemy["BuffList"] = "10010000"
        _, immune = self.simulate(m, enemy, seed=3, max_rounds=1)
        self.assertLess(immune[1]["HP"], 100000)
        self.assertEqual(immune[9]["RP"], 0)

        effects = self.effects(unit(12012004), unit(12011005))
        with patch.object(effects.rng, "randrange", return_value=0):
            effects.apply(1, 1, 9, [9], (3,), (5,), defaultdict(Counter))
            effects.tick(1, before=False)
            effects.tick(9, before=False)
            self.assertTrue(effects.has(9, SILENCE))
            effects.apply(1, 1, 9, [9], (3,), (5,), defaultdict(Counter))
            effects.tick(1, before=False)
            self.assertEqual([e.turns for e in effects.active[9] if e.row["ID"] == 14120000], [1, 2])
        effects.tick(1, before=False)
        self.assertTrue(effects.has(9, SILENCE))
        effects.tick(1, before=False)
        self.assertFalse(effects.has(9, SILENCE))

    def test_timed_stat_and_configured_stack_cap(self):
        effects = self.effects(unit(12011004, buffs="20171000,20171000"), unit(12011005))
        modifiers = defaultdict(Counter)
        for _ in range(5):
            effects.apply(1, 1, None, [9], (1, 2), (5,), modifiers)
            effects.tick(1, before=False)
        effects.apply(1, 1, None, [9], (1, 2), (1,), modifiers)
        self.assertEqual(modifiers[1]["APR"], 3000)  # 10% × three, from 14081000.
        effects.apply(1, 1, None, [9], (1, 3), (5,), defaultdict(Counter))
        effects.tick(1, before=False)
        for expected in (4000, 4000, 0):
            active = defaultdict(Counter)
            effects.apply(1, 1, None, [9], (1, 2), (1,), active)
            self.assertEqual(active[1]["CRI"], expected)  # 12190400 lasts two caster turns.
            effects.tick(1, before=False)

    def test_hp_comparison_and_one_use_damage_buff_change_real_damage(self):
        enemy = unit(12011005, hp=5000)
        enemy.update(NAId=0, RAId=0)
        sango = unit(12011007, hp=6000)
        _, baseline = self.simulate(sango, enemy, max_rounds=1)
        sango["BuffList"] = "10180400"
        _, boosted = self.simulate(sango, enemy, max_rounds=1)
        self.assertLess(boosted[9]["HP"], baseline[9]["HP"])
        sango["HP"] = 4000
        _, below = self.simulate(sango, enemy, max_rounds=1)
        self.assertEqual(below[9]["HP"], baseline[9]["HP"])

        sango["BuffList"] = "10130600"
        _, one_use = self.simulate(sango, enemy, max_rounds=2)
        sango["BuffList"] = ""
        _, two_normal = self.simulate(sango, enemy, max_rounds=2)
        self.assertEqual(two_normal[9]["HP"] - one_use[9]["HP"], 53)  # +75% of the 70-point first hit.

    def test_rage_cut_defensive_trigger_immunity_and_real_rage_cost(self):
        # Miroku's talent reduces the attacker's Nộ only after the incoming blow.
        cut = "10400830"
        attacker = unit(12011005, rp=75)
        defender = unit(12011006, buffs=cut)
        effects = self.effects(attacker, defender)
        with patch.object(effects.rng, "randrange", return_value=0):
            effects.apply(9, 1, 1, [1], (4, 5), (5,), defaultdict(Counter))
        self.assertEqual(attacker["RP"], 50)
        attacker["BuffList"] = "10060000"
        effects = self.effects(attacker, defender)
        self.assertTrue(effects.has(1, IMMUNE_RAGE_LOSS))
        with patch.object(effects.rng, "randrange", return_value=0):
            effects.apply(9, 1, 1, [1], (4, 5), (5,), defaultdict(Counter))
        self.assertEqual(attacker["RP"], 50)
        effects.rage(1, -50)
        self.assertEqual(attacker["RP"], 0)

    def test_control_resistance_subtracts_vn_basis_points(self):
        ally, enemy = unit(12012004), unit(12011005, buffs="20190150")
        effects = self.effects(ally, enemy)
        with patch.object(effects.rng, "randrange", return_value=6500):
            effects.apply(1, 1, 9, [9], (3,), (5,), defaultdict(Counter))
            self.assertFalse(effects.has(9, SILENCE))  # 6800 minus 600 basis points.
        with patch.object(effects.rng, "randrange", return_value=6199):
            effects.apply(1, 1, 9, [9], (3,), (5,), defaultdict(Counter))
            self.assertTrue(effects.has(9, SILENCE))

    def test_multiphase_cleanup_win_loss_and_npc_priority(self):
        solo = unit(12011006, hp=500, ap=10000, rp=100, buffs="20210401")
        enemy = unit(12011005, hp=500, ap=10000, rp=100)
        win, _ = self.simulate(solo, enemy, max_rounds=1)
        lose, _ = self.simulate(solo, enemy, max_rounds=1, npc_first=True)
        self.assertTrue(win.won)
        self.assertFalse(lose.won)
        packet = {"FightObjs": [wave(solo, enemy), wave(solo, enemy)]}
        copy_before = copy.deepcopy(packet)
        result = simulate_fight_info(packet, game()["attacks"], buffs_cfg=game()["combat_buffs"])
        self.assertTrue(result.won)
        self.assertEqual(result.waves, 2)
        self.assertEqual(packet, copy_before)

    def test_fightinfo_emits_confirmed_talents_and_miroku_counter(self):
        p = GameEmulatorState(persist=False).profiles["normal"]
        m = p._hero_fight_obj(game()["heroes"]["12011006"], step=8)
        self.assertIn("20210401", m["BuffList"].split(","))
        self.assertIn("20050600", m["BuffList"].split(","))
        self.assertTrue(supports_talent_buff(game()["combat_buffs"]["20050600"], game()["combat_buffs"]))
