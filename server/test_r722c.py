"""R7.22C (TASK-M03) tests: Standard FAP 1:10:10, CreateRandom PRNG, Target AI, and Faction Counter."""

from __future__ import annotations

from functools import lru_cache
import unittest

from combat_sim import CreateRandom, _select_targets, simulate_fight_info
from emulator import GameEmulatorState


@lru_cache(maxsize=1)
def _game_data():
    return GameEmulatorState(persist=False).game_data


class _LuaBit32Oracle:
    """Literal 32-bit bit-array implementation mirroring CSCommon/LMMath/Bit.lua + Bit32.lua + CreateRandom.lua."""

    def __init__(self, random_key: int) -> None:
        self.box = CreateRandom.MBOX
        rk = self._bxor(random_key, self._lrotate(random_key, 23), self._rrotate(random_key, 5))
        self.m_var = rk % (1000 - 1)
        self.random_key = rk

    @staticmethod
    def _int_to_bits(n: int) -> list[int]:
        n = n % 0x100000000
        return [(n >> i) & 1 for i in range(31, -1, -1)]

    @staticmethod
    def _bits_to_int(bits: list[int]) -> int:
        val = 0
        for idx, b in enumerate(bits):
            if b:
                val += 1 << (31 - idx)
        return val

    @classmethod
    def _bxor(cls, *nums: int) -> int:
        acc = cls._int_to_bits(nums[0])
        for n in nums[1:]:
            b2 = cls._int_to_bits(n)
            acc = [1 if a != b else 0 for a, b in zip(acc, b2)]
        return cls._bits_to_int(acc)

    @classmethod
    def _lrotate(cls, num: int, disp: int) -> int:
        bits = cls._int_to_bits(num)
        d = disp % 32
        for _ in range(d):
            bits.append(bits.pop(0))
        return cls._bits_to_int(bits)

    @classmethod
    def _rrotate(cls, num: int, disp: int) -> int:
        return cls._lrotate(num, 32 - (disp % 32))

    def get_random(self, mn: int, mx: int) -> int:
        rk = self.random_key
        start_pos = (rk % (len(self.box) - 7)) + 1
        char8 = self.box[start_pos - 1 : start_pos - 1 + 8]
        int4 = int(char8, 16)
        self.m_var += 1
        if self.m_var >= 10_000_000_000:
            self.m_var = 0
        result = (int4 % (mx - mn + 1)) + mn
        rk = self._bxor(rk, int4, self.m_var, result)
        rk = self._bxor(rk, self._lrotate(rk, self.m_var % 7 + 16), self._rrotate(rk, self.m_var % 3 + 2))
        hex_str = f"{rk:08x}"
        self.box = self.box[: start_pos - 1] + hex_str + self.box[start_pos - 1 + len(hex_str) :]
        self.random_key = int(hex_str, 16)
        return result


def _lua_scenario_unit(model: int, rp: int, buffs: str = "") -> dict:
    row = _game_data()["heroes"][str(model)]
    return {
        "HP": 100_000,
        "TotalHp": 100_000,
        "AP": 900,
        "DEF": 0,
        "RP": rp,
        "HIT": 10000,
        "DOD": 0,
        "CRI": 10000,
        "TEN": 0,
        "BLO": 0,
        "BOG": 0,
        "CRId": 0,
        "TEND": 0,
        "NAId": row["NAID"],
        "RAId": row["RAID"],
        "HeroModelId": model,
        "Quality": row["quality"],
        "RaceId": row["raceID"],
        "BuffList": buffs,
        "FSP": 500,
        "CP": 0,
        "BCP": 0,
        "CPR": 0,
        "BCPR": 0,
        "DAMADD": 0,
        "DAMCUT": 0,
        "DAMADDR": 0,
        "DAMCUTR": 0,
        "RADAMADDR": 0,
        "RADAMCUTR": 0,
        "RBDAMADDR": 0,
        "RBDAMCUTR": 0,
        "RCDAMADDR": 0,
        "RCDAMCUTR": 0,
    }


class R722CCombatAndFapTest(unittest.TestCase):
    def test_create_random_matches_lua_bit32_and_apk_oracles(self):
        for seed in (1, 3, 42, 77817, 123456789):
            with self.subTest(seed=seed):
                py_rng = CreateRandom(seed)
                lua_rng = _LuaBit32Oracle(seed)
                py_seq = [py_rng.get_random(0, 9999) for _ in range(500)]
                lua_seq = [lua_rng.get_random(0, 9999) for _ in range(500)]
                self.assertEqual(py_seq, lua_seq)

        gd = _game_data()

        # Real VN APK Lua 5.1 oracle (poc/test_r716_lua.py:137-140):
        # Midoriko (12012004, 68% silence) leaves Kagome unsilenced at seed=1, silences at seed=3
        def midoriko_run(seed: int) -> dict[int, dict]:
            heros = [{} for _ in range(12)]
            heros[0] = _lua_scenario_unit(12012004, 100)
            heros[8] = _lua_scenario_unit(12011005, 100)
            out = simulate_fight_info(
                {
                    "FightObjs": [
                        {
                            "Heros": heros,
                            "TeamData": [{"Fsp": 9000, "Fap": 10000}, {"Fsp": 1, "Fap": 1000}],
                            "Pets": [],
                            "RandNum": seed,
                            "IsPVP": False,
                        }
                    ]
                },
                gd["attacks"],
                max_rounds=1,
                buffs_cfg=gd["combat_buffs"],
            )
            return {row["PosId"]: row for row in out.verify_data["hp"][0]}

        res1 = midoriko_run(1)
        res3 = midoriko_run(3)
        self.assertEqual(res1[9]["RP"], 0)
        self.assertGreaterEqual(res3[9]["RP"], 125)

        # Real VN APK Lua 5.1 oracle (poc/test_r717_lua.py:31-36): Miroku stuns at seed=3
        heros_stun = [{} for _ in range(12)]
        heros_stun[0] = _lua_scenario_unit(12011006, 100, buffs="20210401")
        heros_stun[8] = _lua_scenario_unit(12011005, 100)
        out_stun = simulate_fight_info(
            {
                "FightObjs": [
                    {
                        "Heros": heros_stun,
                        "TeamData": [{"Fsp": 9000, "Fap": 10000}, {"Fsp": 1, "Fap": 1000}],
                        "Pets": [],
                        "RandNum": 3,
                        "IsPVP": False,
                    }
                ]
            },
            gd["attacks"],
            max_rounds=1,
            buffs_cfg=gd["combat_buffs"],
        )
        hp_stun = {row["PosId"]: row for row in out_stun.verify_data["hp"][0]}
        self.assertEqual(hp_stun[1]["HP"], 100_000)

    def test_standard_fap_matches_teambattle_tier1_vn_data_and_all_calculators(self):
        gd = _game_data()
        p = GameEmulatorState(persist=False).profiles["normal"]

        # Verify against all 216 tier-1 TeambattleHeroNpc rows (HPAdd=APAdd=DEFAdd=DAMADDR=0)
        tier1 = [
            r
            for r in gd["teambattle_hero_npcs"]
            if int(r["HPAdd"]) == 0 and int(r["APAdd"]) == 0 and int(r["DEFAdd"]) == 0 and int(r["DAMADDR"]) == 0
        ]
        self.assertEqual(len(tier1), 216)
        for row in tier1:
            expected_fap = int(row["HP"]) + 10 * (int(row["AP"]) + int(row["DEF"]))
            self.assertEqual(int(row["FAP"]), expected_fap)

        # Verify emulator Slot["Property"], _bdd_fap, and _teambattle_raw_fap use 1:10:10
        prop = p.state["slots"][0]["Property"]
        self.assertEqual(prop["FAP"], prop["HP"] + 10 * prop["AP"] + 10 * prop["DEF"])
        sample = [{"HP": 1000, "AP": 120, "DEF": 30}]
        self.assertEqual(p._bdd_fap(sample), 1000 + 10 * (120 + 30))
        self.assertEqual(p._teambattle_raw_fap(sample), 1000 + 10 * (120 + 30))

    def test_target_selection_matches_target_mode_function_and_battle_matrix(self):
        # 1. Nearest column fallback for eSingleFront (1), eSingleBack (2), and eOneColumn (5)
        # Attacker at col 2 (pos=3); enemy col 2 (9, 12) empty; col 1 (8, 11) & col 0 (7, 10) alive
        units_col = {
            3: {"HP": 100, "TotalHp": 100, "RP": 50},
            7: {"HP": 100, "TotalHp": 100, "RP": 50},
            8: {"HP": 100, "TotalHp": 100, "RP": 50},
            10: {"HP": 100, "TotalHp": 100, "RP": 50},
            11: {"HP": 100, "TotalHp": 100, "RP": 50},
        }
        rng = CreateRandom(42)
        self.assertEqual(_select_targets(3, 1, units_col, {"targetCampEnum": 2, "targetEnum": 1, "targetNum": 1}, rng), [8])
        self.assertEqual(_select_targets(3, 1, units_col, {"targetCampEnum": 2, "targetEnum": 2, "targetNum": 1}, rng), [11])
        self.assertEqual(_select_targets(3, 1, units_col, {"targetCampEnum": 2, "targetEnum": 5, "targetNum": 2}, rng), [8, 11])

        # Center col 1 (pos=2) empty on enemy side; col 0 (7) & col 2 (9) tie at dist 1 -> smaller col 0 wins
        units_tie = {
            2: {"HP": 100, "TotalHp": 100, "RP": 50},
            7: {"HP": 100, "TotalHp": 100, "RP": 50},
            9: {"HP": 100, "TotalHp": 100, "RP": 50},
        }
        self.assertEqual(_select_targets(2, 1, units_tie, {"targetCampEnum": 2, "targetEnum": 1, "targetNum": 1}, rng), [7])

        # 2. eHPMin (9) uses raw HP ascending, NOT HP / TotalHp ratio
        units_hp = {
            1: {"HP": 1000, "TotalHp": 1000, "RP": 50},
            7: {"HP": 600, "TotalHp": 2000, "RP": 50},  # 30% ratio, 600 raw HP
            8: {"HP": 400, "TotalHp": 500, "RP": 50},   # 80% ratio, 400 raw HP
        }
        self.assertEqual(_select_targets(1, 1, units_hp, {"targetCampEnum": 2, "targetEnum": 9, "targetNum": 1}, rng), [8])

        # 3. eRPMax (10) & eRPMin (11) exclude attacker_pos on same-camp skills
        units_rp = {
            1: {"HP": 1000, "TotalHp": 1000, "RP": 150},
            2: {"HP": 1000, "TotalHp": 1000, "RP": 80},
            3: {"HP": 1000, "TotalHp": 1000, "RP": 20},
        }
        self.assertEqual(_select_targets(1, 1, units_rp, {"targetCampEnum": 1, "targetEnum": 10, "targetNum": 1}, rng), [2])
        self.assertEqual(_select_targets(3, 1, units_rp, {"targetCampEnum": 1, "targetEnum": 11, "targetNum": 1}, rng), [2])

    def test_faction_counter_attributes_and_country_hurt_formula(self):
        gd = _game_data()
        p = GameEmulatorState(persist=False).profiles["normal"]

        # Bosses 12015019 (A->B), 12015020 (B->A), 12015021 (C->C) emit their RXDAMCUTR = -5000 at step=4
        for hid, field in (("12015020", "RADAMCUTR"), ("12015019", "RBDAMCUTR"), ("12015021", "RCDAMCUTR")):
            obj = p._hero_fight_obj(gd["heroes"][hid], lv=50, step=4)
            self.assertEqual(obj[field], -5000)

        # In combat: Race 1 attacker deals +50% damage to 12015020 (RADAMCUTR=-5000), while Race 2 deals 1.0x
        def hit_dmg(atk_race: int, vic_model: str, atk_radamaddr: int = 0) -> int:
            atk = {
                "HP": 100_000, "TotalHp": 100_000, "AP": 1000, "DEF": 0, "RP": 0,
                "HIT": 10000, "DOD": 0, "CRI": 0, "TEN": 0, "BLO": 0, "BOG": 0, "CRId": 0, "TEND": 0,
                "NAId": 1001008, "RAId": 1002008, "HeroModelId": 12011004, "RaceId": atk_race,
                "FSP": 9000, "BuffList": "", "RADAMADDR": atk_radamaddr,
            }
            vic = p._hero_fight_obj(gd["heroes"][vic_model], lv=10, step=4)
            vic.update(HP=100_000, TotalHp=100_000, DEF=0, DOD=0, BLO=0, TEN=0, FSP=1, NAId=0, RAId=0, BuffList="")
            heros = [atk] + [{}] * 7 + [vic] + [{}] * 3
            out = simulate_fight_info(
                {
                    "FightObjs": [
                        {
                            "Heros": heros,
                            "TeamData": [{"Fsp": 9000, "Fap": 10000}, {"Fsp": 1, "Fap": 1000}],
                            "Pets": [],
                            "RandNum": 7,
                            "IsPVP": False,
                        }
                    ]
                },
                gd["attacks"],
                max_rounds=1,
                buffs_cfg={},
            )
            hp_map = {r["PosId"]: r for r in out.verify_data["hp"][0]}
            return 100_000 - hp_map[9]["HP"]

        base_vs_b = hit_dmg(2, "12015020")
        boosted_a_vs_b = hit_dmg(1, "12015020")
        self.assertEqual(boosted_a_vs_b, int(base_vs_b * 1.5))

        base_vs_a = hit_dmg(1, "12015019")
        boosted_b_vs_a = hit_dmg(2, "12015019")
        self.assertEqual(boosted_b_vs_a, int(base_vs_a * 1.5))

        base_vs_c = hit_dmg(1, "12015021")
        boosted_c_vs_c = hit_dmg(3, "12015021")
        self.assertEqual(boosted_c_vs_c, int(base_vs_c * 1.5))

        # Check RADAMADDR also boosts damage against Race 1 defender (NA 1001008 factor=7500 -> base 750 vs 975)
        def vs_race1(radamaddr: int) -> int:
            atk_obj = {
                "HP": 100_000, "TotalHp": 100_000, "AP": 1000, "DEF": 0, "RP": 0,
                "HIT": 10000, "DOD": 0, "CRI": 0, "TEN": 0, "BLO": 0, "BOG": 0, "CRId": 0, "TEND": 0,
                "NAId": 1001008, "RAId": 1002008, "HeroModelId": 12011004, "RaceId": 2,
                "FSP": 9000, "BuffList": "", "RADAMADDR": radamaddr,
            }
            vic_r1 = _lua_scenario_unit(12011004, 0)
            vic_r1.update(HP=100_000, TotalHp=100_000, DEF=0, DOD=0, BLO=0, TEN=0, FSP=1, NAId=0, RAId=0, RaceId=1)
            out_radd = simulate_fight_info(
                {
                    "FightObjs": [
                        {
                            "Heros": [atk_obj] + [{}] * 7 + [vic_r1] + [{}] * 3,
                            "TeamData": [{"Fsp": 9000, "Fap": 10000}, {"Fsp": 1, "Fap": 1000}],
                            "Pets": [],
                            "RandNum": 7,
                            "IsPVP": False,
                        }
                    ]
                },
                gd["attacks"],
                max_rounds=1,
                buffs_cfg={},
            )
            hp_radd = {r["PosId"]: r for r in out_radd.verify_data["hp"][0]}
            return 100_000 - hp_radd[9]["HP"]

        self.assertEqual(vs_race1(0), 750)
        self.assertEqual(vs_race1(3000), 975)


if __name__ == "__main__":
    unittest.main()
