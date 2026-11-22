"""Deterministic turn-based combat simulator matching CSCommon/FightExpression + BattleCalc."""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any

from combat_effects import (
    BattleEffects,
    ContinuousAttack,
    IMMUNE_THORN,
    LOCK_HEALING,
    MAX_RAGE,
    PARALYSIS,
    SILENCE,
    STUN,
)

PVE_FRIEND_ORDER = [1, 2, 3, 4, 5, 6]
PVE_ENEMY_ORDER = [9, 8, 7, 12, 11, 10]
PVP_ENEMY_ORDER = [7, 8, 9, 10, 11, 12]

_RACE_ADD_FIELD = {1: "RADAMADDR", 2: "RBDAMADDR", 3: "RCDAMADDR"}
_RACE_CUT_FIELD = {1: "RADAMCUTR", 2: "RBDAMCUTR", 3: "RCDAMCUTR"}


def _lrotate32(n: int, disp: int) -> int:
    n &= 0xFFFFFFFF
    d = disp % 32
    return ((n << d) | (n >> (32 - d))) & 0xFFFFFFFF if d else n


def _rrotate32(n: int, disp: int) -> int:
    n &= 0xFFFFFFFF
    d = disp % 32
    return ((n >> d) | (n << (32 - d))) & 0xFFFFFFFF if d else n


class CreateRandom:
    """Bit-for-bit port of VN CSCommon/LMMath/CreateRandom.lua."""

    MBOX = (
        "4f4a4d677d13cc2eb2a3bc0e43ff92274a4595736fb803bb3f729a4452e2f0638da5bc601a4e7e458ac2edbf5252e176b037a72d42c8cc07b8a34066"
        "fd8cce9a66396a700f193620595954b77c67ceeb886813ae27717739e2692b25b066366600f649c2cadc4243a30a4dde351ad4165c9d48856110096a"
        "ddf62301e04e50272a10f3af481fe1de03ab846c3e913e1b71b241b985c3d61e8a469d47a2f7ba78fb9745f4e708d957e94af466adede85d29a6b370"
        "7b028530eb9cc9fab91f4adff8f2c4c82b8b465a7cea3fdaf463a527361a821557f621eaf152d883d6ee57b93e20b32770b576d8d8191eb08afabaec"
        "921982d290142d12247a9d55129677d040ccb19538ec2bbc31cadb53c885a63fe3957686c4e2ee61e6c86a104217e359c2f91085beb4337770763441"
        "a93987da9f6c033063d14dcaccb2b35c1a0641910f8a776d6101e5ba65171c95bcba4b7426511c2961b817af6abfd65f91989a0b5f0ae861683033dc"
        "c7ca42da8c6e1d11d4d127619b63377f60f4a073657759ff1ff8526b04dd8a1b8422a9a97e47fafee2eb4f3907614cbc4150c50715ddf66be1936df7"
        "60d156e543960a9116dde88a04ab397e73e71b9e45e89f98babe39d0b5fba8c69de75ff9091a4945f954e3a9a177d48f3fb2266b04b792a9a6042849"
        "59be782a588e410859f1906e1bc9855f03e70a79bc8bf26fd5b3f8af2eb672b6d684601b383f3f8f940f936b69a1b837abec4e9ab24bad9ae3a5b260"
        "f24cc9f97a944a9b9eec42dc8326d5fe8826b2c0c0163d5092593c558c9ddde8814101f2ea92922d57a3e8446c3caeb54e6908744794414b54f84f8e"
        "1485bf374d7b37296c495840aea2732fee60087b06eafcc5ac731cbbaad5e934bf5c234f89f0d886bdfac30fb08ccd7ba436a75e5edecf7e86be7e7c"
        "b484fe1219a154f2ffe0392442668e859af308ca69b2a69fcc5f6a795b86b13f06489ab0d03495ea8f36c1fcc25e54b456e87ad172308946495db62a"
        "4be648f6f76fb4ca133ac5ed90efcb8dd786a6ab7c584d1a20f02eabe8356c8bb60f88ced2cb66f286d1558044d850be049f3225969931cb8a5d7444"
        "b088002ecdf2f67c571998cba6d2896969df3b98620db068964fb36f5edf20eff1e697ec99e38297f2461eb429cf53ff5535b8705456deaa96e96914"
        "589eb9d7e9d87d756b5580615f40eb07f5505ba3620f75e0000d2f5dd891252a8f970d68a6f393576496906dd6f327c93451a8343df0196e84316693"
        "63cb95bc0d2a946fbe5da5855b8d59b5e33cfcc192b1dc5c1f7b4139376c7183779786126fe0adb8266676e91fb4fc8ec087ede7799dacb3fe020e1d"
        "a9afe5261b498870bfec6939883a84c6d676a28ec1cd0da169a5245c14017f4d2a518bc2435cf6aa4d603b818a1ac20a6a2849292ad9c258281cd97b"
        "b779f86f1cb520f76ad89c6617d583443db61492904b065cf20ed9efe6b75e71aa62dc5ac15d3954f1f7a7f9426be93d676ef481d322e8980e4c21ac"
        "07c09c1a86953651c4dfc86058e39b5d1f67b56daa0211071fff16318154f09d2c0d74df07f04c0fef1025348915f01b3bb8f02a8d0bc183f4ee29ac"
        "81cb4a91d1bd9b2281fd68622d4da0394bc2592145aae7fba2886962a1d26d3d16090e5c0379966e886cc8fbe01e6b800b1cca3376471e1b7ca0065d"
    )

    def __init__(self, random_key: int) -> None:
        self.m_box = self.MBOX
        rk = int(random_key) & 0xFFFFFFFF
        rk = (rk ^ _lrotate32(rk, 23) ^ _rrotate32(rk, 5)) & 0xFFFFFFFF
        self.m_var = rk % 999
        self.m_random_key = rk

    def get_random(self, min_val: int, max_val: int) -> int:
        rand_key = self.m_random_key
        start_pos = rand_key % (len(self.m_box) - 7)
        char8 = self.m_box[start_pos : start_pos + 8]
        int4 = int(char8, 16)
        var = self.m_var + 1
        if var >= 10_000_000_000:
            var = 0
        result = (int4 % (max_val - min_val + 1)) + min_val
        rk = (rand_key ^ int4 ^ (var & 0xFFFFFFFF) ^ (result & 0xFFFFFFFF)) & 0xFFFFFFFF
        rk = (rk ^ _lrotate32(rk, var % 7 + 16) ^ _rrotate32(rk, var % 3 + 2)) & 0xFFFFFFFF
        hex8 = f"{rk:08x}"
        self.m_box = self.m_box[:start_pos] + hex8 + self.m_box[start_pos + len(hex8) :]
        self.m_random_key = rk
        self.m_var = var
        return result

    def randrange(self, stop: int) -> int:
        return self.get_random(0, stop - 1)


def _col_order(col: int) -> list[int]:
    """Column fallback order matching TargetModeFunction.lua: nearest column, smaller index on tie."""
    order = [col]
    for dist in (1, 2):
        if col - dist >= 0:
            order.append(col - dist)
        if col + dist <= 2:
            order.append(col + dist)
    return order


@dataclass
class CombatOutcome:
    """Result of evaluating FightInfo with CSCommon/FightExpression + BattleCalc rules."""

    won: bool
    waves: int
    total_rounds: int
    ally_alive: int
    enemy_alive: int
    ally_hp_pct: float
    verify_data: dict[str, Any]


def _select_targets(
    attacker_pos: int,
    attacker_camp: int,
    units: dict[int, dict[str, Any]],
    skill: dict[str, Any],
    rng: Any,
) -> list[int]:
    """Select target PosIds matching CSCommon/TargetModeFunction.lua & BattleMatrix.lua."""
    target_camp = int(skill.get("targetCampEnum", 2))
    if target_camp == 3:  # eSelf
        return [attacker_pos] if attacker_pos in units and units[attacker_pos]["HP"] > 0 else []
    # targetCampEnum: 1=same camp, 2/0=opposing camp
    want_ally = (attacker_camp == 1) if target_camp == 1 else (attacker_camp == 2)
    pool = sorted(
        pos
        for pos, u in units.items()
        if u["HP"] > 0 and ((pos <= 6) == want_ally)
    )
    if not pool:
        return []

    mode = int(skill.get("targetEnum", 1))
    target_num = max(1, int(skill.get("targetNum", 1)))
    front_positions = (1, 2, 3) if want_ally else (7, 8, 9)
    back_positions = (4, 5, 6) if want_ally else (10, 11, 12)
    front_alive = [p for p in front_positions if p in pool]
    back_alive = [p for p in back_positions if p in pool]

    if mode in (0, 1, 15):  # eSingleFront / eDesignatedHero
        cols = _col_order((attacker_pos - 1) % 3)
        pref = [front_positions[c] for c in cols] + [back_positions[c] for c in cols]
        first = next((p for p in pref if p in pool), pool[0])
        return [first]
    if mode == 2:  # eSingleBack
        cols = _col_order((attacker_pos - 1) % 3)
        pref = [back_positions[c] for c in cols] + [front_positions[c] for c in cols]
        first = next((p for p in pref if p in pool), pool[0])
        return [first]
    if mode == 3:  # eRowFront
        return front_alive or back_alive
    if mode == 4:  # eRowBack
        return back_alive or front_alive
    if mode == 5:  # eOneColumn
        for c in _col_order((attacker_pos - 1) % 3):
            hits = [p for p in (front_positions[c], back_positions[c]) if p in pool]
            if hits:
                return hits
        return []
    if mode == 6:  # eAll
        return pool
    if mode == 7:  # eRandom
        if target_num >= len(pool):
            return list(pool)
        remaining = list(pool)
        chosen: list[int] = []
        for _ in range(target_num):
            idx = (rng.get_random(1, len(remaining)) - 1) if hasattr(rng, "get_random") else rng.randrange(len(remaining))
            chosen.append(remaining.pop(idx))
        return chosen
    if mode == 8:  # eHPMax
        return sorted(pool, key=lambda p: units[p]["HP"], reverse=True)[:target_num]
    if mode == 9:  # eHPMin (BattleMatrix:getHPMinAliveHeros uses raw HP)
        return sorted(pool, key=lambda p: units[p]["HP"])[:target_num]
    if mode == 10:  # eRPMax (BattleMatrix:getRPMaxAliveHeros excludes attacker)
        candidates = [p for p in pool if p != attacker_pos]
        return sorted(candidates, key=lambda p: units[p]["RP"], reverse=True)[:target_num]
    if mode == 11:  # eRPMin (BattleMatrix:getRPMinAliveHeros excludes attacker)
        candidates = [p for p in pool if p != attacker_pos]
        return sorted(candidates, key=lambda p: units[p]["RP"])[:target_num]
    if mode == 12:  # eHPLossMax
        return sorted(pool, key=lambda p: units[p]["TotalHp"] - units[p]["HP"], reverse=True)[:target_num]
    return pool[:target_num]


_ROW_NEIGHBORS = {
    1: (2,), 2: (3, 1), 3: (2,),
    4: (5,), 5: (6, 4), 6: (5,),
    7: (8,), 8: (7, 9), 9: (8,),
    10: (11,), 11: (10, 12), 12: (11,),
}


def _apply_attack(
    atk_pos: int,
    units: dict[int, dict[str, Any]],
    attacks_cfg: dict[str, Any],
    rng: Any,
    effects: BattleEffects,
    *,
    continuous: ContinuousAttack | None = None,
) -> None:
    """Execute single hero turn using CSCommon/FightExpression.lua formulas."""
    atk = units[atk_pos]
    atk["DAM"] = 0
    exclude = continuous.exclude_types if continuous else frozenset()
    if continuous is not None:
        use_skill = continuous.is_skill
        skill = attacks_cfg.get(str(continuous.attack_id), {})
        if not skill:
            return
    else:
        ra_id = int(atk.get("RAId", 0))
        na_id = int(atk.get("NAId", 0))
        ra_skill = attacks_cfg.get(str(ra_id), {})
        na_skill = attacks_cfg.get(str(na_id), {})

        if effects.has(atk_pos, STUN):
            return
        need_rp = int(ra_skill.get("useRP", 100))
        use_skill = bool(ra_skill) and int(atk["RP"]) >= need_rp and not effects.has(atk_pos, SILENCE)
        if not use_skill and effects.has(atk_pos, PARALYSIS):
            return
        skill = ra_skill if use_skill else na_skill
        if not skill:
            return
    need_rp = int(skill.get("useRP", 100))
    atk_rp_snapshot = int(atk["RP"])

    atk_camp = 1 if atk_pos <= 6 else 2
    if continuous is not None and continuous.targets:
        targets = [p for p in continuous.targets if p in units]
    else:
        targets = _select_targets(atk_pos, atk_camp, units, skill, rng)
    factor = float(skill.get("factor", 10000)) / 10000.0
    is_heal = int(skill.get("type", 0)) == 1
    active_attack = (1, 3 if use_skill else 2)
    active_defense = (8,) if is_heal else (4, 6 if use_skill else 5)
    action_mods = defaultdict(Counter)
    effects.apply(atk_pos, atk_pos, None, targets, active_attack, (1,), action_mods, exclude_types=exclude)

    if use_skill:
        atk["RP"] = 0

    after_action: set[int] = set()
    attack_rage = 0
    for tpos in targets:
        vic = units[tpos]
        if vic["HP"] <= 0:
            continue
        hit_mods = defaultdict(Counter)
        effects.apply(atk_pos, atk_pos, tpos, [tpos], active_attack, (1,), hit_mods, compared=True, exclude_types=exclude)
        effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, (1,), hit_mods, exclude_types=exclude)
        effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, (1,), hit_mods, compared=True, exclude_types=exclude)

        def stat(pos, field, default=0):
            return units[pos].get(field, default) + action_mods[pos][field] + hit_mods[pos][field]

        atk_ap = stat(atk_pos, "AP") * (1 + stat(atk_pos, "APR") / 10000)
        roll = rng.randrange(100)
        phases = {5}
        if is_heal:
            heal = atk_ap * factor + stat(atk_pos, "CP") + stat(tpos, "BCP")
            base_heal = max(0, heal * (1 + (stat(atk_pos, "CPR") + stat(tpos, "BCPR")) / 10000))
            if roll < stat(atk_pos, "CRI") / 100:
                phases.add(2)
                base_heal = max(1, base_heal * 1.5)
            if not effects.has(tpos, LOCK_HEALING):
                vic["HP"] = min(vic["TotalHp"], vic["HP"] + math.ceil(base_heal))
        else:
            vic_def = stat(tpos, "DEF") * (1 + stat(tpos, "DEFR") / 10000)
            hurt_strength = max(atk_ap - vic_def, atk_ap * 0.1)
            rage_scale = 1 + (atk_rp_snapshot - need_rp) / 200 if use_skill else 1
            atk_race = int(atk.get("RaceId", 0))
            vic_race = int(vic.get("RaceId", 0))
            country_add = stat(atk_pos, _RACE_ADD_FIELD[vic_race]) if vic_race in _RACE_ADD_FIELD else 0
            country_cut = stat(tpos, _RACE_CUT_FIELD[atk_race]) if atk_race in _RACE_CUT_FIELD else 0
            rate = (stat(atk_pos, "DAMADDR") - stat(tpos, "DAMCUTR") + country_add - country_cut) / 10000
            dmg = hurt_strength * factor * rage_scale * max(0.01, 1 + rate)
            dodge = max((stat(tpos, "DOD") - stat(atk_pos, "HIT", 10000)) / 100 + 100, 0)
            crit = max((stat(atk_pos, "CRI") - stat(tpos, "TEN")) / 100, 0)
            block = max((stat(tpos, "BLO") - stat(atk_pos, "BOG")) / 100, 0)
            if roll < dodge:
                after_action.add(3)
                effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, (3,), hit_mods, exclude_types=exclude)
                effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, (3,), hit_mods, compared=True, exclude_types=exclude)
                effects.apply(atk_pos, atk_pos, tpos, [tpos], active_attack, (3,), hit_mods, compared=True, exclude_types=exclude)
                effects.apply(atk_pos, atk_pos, tpos, [tpos], active_attack, (3,), hit_mods, target_only=True, exclude_types=exclude)
                continue
            if roll < dodge + crit:
                phases.add(2)
                dmg = max(1, math.ceil(dmg * (1.5 + (stat(atk_pos, "CRId") - stat(tpos, "TEND")) / 10000)))
            elif roll < dodge + crit + block:
                phases.add(4)
                dmg = max(1, math.ceil(dmg * 0.5))
            else:
                dmg = math.ceil(dmg)
            dmg_raw = max(1, dmg + stat(atk_pos, "DAMADD") - stat(tpos, "DAMCUT"))
            if continuous is not None and continuous.scale is not None:
                dmg_raw = max(0, -math.ceil(-dmg_raw * continuous.scale))
            if vic["HP"] - dmg_raw <= 0 and effects.try_immune_die(tpos):
                dmg_raw = 0
            display_dmg = dmg_raw
            absorbed = effects.use_shield(tpos, dmg_raw) if dmg_raw > 0 else 0
            actual_loss = min(vic["HP"], max(0, dmg_raw - absorbed))
            vic["HP"] -= actual_loss
            atk["DAM"] += actual_loss
            reflect_rate = effects.reflect.get(tpos)
            if reflect_rate and actual_loss > 0 and not effects.has(atk_pos, IMMUNE_THORN):
                reflect_delta = math.floor((-actual_loss) * reflect_rate)
                atk["HP"] = max(0, atk["HP"] + reflect_delta)
            if actual_loss > 0 and not vic.get("IsBoss"):
                effects.rage(tpos, actual_loss * 100 // vic["OpeningHP"])
            if vic["HP"] == 0 and not atk.get("IsBoss"):
                attack_rage += 25
            sput_factor = effects.sputtering.get(atk_pos)
            if sput_factor and not use_skill and display_dmg > 0:
                splash_delta = math.floor(sput_factor * (-display_dmg))
                if splash_delta < 0:
                    for npos in _ROW_NEIGHBORS.get(tpos, ()):
                        if npos in units and units[npos]["HP"] > 0:
                            units[npos]["HP"] = max(0, units[npos]["HP"] + splash_delta)
        effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, phases, hit_mods, exclude_types=exclude)
        effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, phases, hit_mods, compared=True, exclude_types=exclude)
        effects.apply(atk_pos, atk_pos, tpos, [tpos], active_attack, phases, hit_mods, compared=True, exclude_types=exclude)
        effects.apply(atk_pos, atk_pos, tpos, [tpos], active_attack, phases, hit_mods, target_only=True, exclude_types=exclude)
        after_action.update(phases)

    if not use_skill and 5 in after_action and not (continuous is not None and continuous.dont_add_rp):
        attack_rage += 20 if atk.get("IsBoss") else 25
    effects.rage(atk_pos, attack_rage)
    effects.apply(atk_pos, atk_pos, None, targets, active_attack, after_action, action_mods, target_only=False, exclude_types=exclude)


def simulate_fight_info(
    fight_info: dict[str, Any],
    attacks_cfg: dict[str, Any],
    max_rounds: int = 30,
    *,
    buffs_cfg: dict[str, Any] | None = None,
) -> CombatOutcome:
    """
    Evaluate all waves of a FightInfo payload using real combat math.

    Respects IsPVP turn order ([7..12] vs [9,8,7,12,11,10]) and never rigs outcomes.
    """
    fight_objs = fight_info.get("FightObjs", [])
    buffs_cfg = buffs_cfg or {}
    waves_hp: list[list[dict[str, int]]] = []
    ally_carry_hp: dict[int, int] = {}
    ally_carry_rp: dict[int, int] = {}
    total_rounds = 0
    won_all = True
    last_units: dict[int, dict[str, Any]] = {}

    for w_idx, wave in enumerate(fight_objs):
        seed = int(wave.get("RandNum", w_idx + 1))
        rng = CreateRandom(seed)
        heros_arr = wave.get("Heros", [])
        is_pvp = bool(wave.get("IsPVP", False))
        enemy_order = PVP_ENEMY_ORDER if is_pvp else PVE_ENEMY_ORDER

        units: dict[int, dict[str, Any]] = {}
        for idx, obj in enumerate(heros_arr, start=1):
            if not isinstance(obj, dict) or not obj.get("HeroModelId"):
                continue
            u = dict(obj)
            u["HP"] = int(u.get("HP", 0))
            u["TotalHp"] = int(u.get("TotalHp", max(1, u["HP"])))
            u["RP"] = min(MAX_RAGE, int(u.get("RP", 50)))
            if idx <= 6 and w_idx > 0 and idx in ally_carry_hp:
                u["HP"] = ally_carry_hp[idx]
                u["RP"] = ally_carry_rp.get(idx, u["RP"])
            u["OpeningHP"] = max(1, u["HP"])
            u["OriginalAP"] = int(u.get("AP", 0))
            u["OriginalDEF"] = int(u.get("DEF", 0))
            u["DAM"] = 0
            units[idx] = u

        ally_total_fsp = sum(int(u.get("FSP", 0)) for p, u in units.items() if p <= 6 and u["HP"] > 0)
        enemy_total_fsp = sum(int(u.get("FSP", 0)) for p, u in units.items() if p > 6 and u["HP"] > 0)
        teams = wave.get("TeamData") or [{}, {}]
        first_side = int((teams[0].get("Fsp", ally_total_fsp), teams[0].get("Fap", 0))
                         < (teams[1].get("Fsp", enemy_total_fsp), teams[1].get("Fap", 0)))
        effects = BattleEffects(units, attacks_cfg, buffs_cfg, rng)
        first_turn = True

        for _rnd in range(1, max_rounds + 1):
            total_rounds += 1
            order = [deque(p for p in side if p in units) for side in (PVE_FRIEND_ORDER, enemy_order)]
            side = first_side
            while order[0] or order[1]:
                if not order[side]:
                    side ^= 1
                pos = order[side].popleft()
                effects.tick(pos, before=True)
                if units[pos]["HP"] <= 0:
                    # An already defeated caster's effects still age when its slot comes up.
                    effects.tick(pos, before=False)
                    continue
                if first_turn:
                    effects.start(pos)
                    first_turn = False
                _apply_attack(pos, units, attacks_cfg, rng, effects)
                effects.tick(pos, before=False)
                effects.clear_dead()
                while effects.continuous_attacks:
                    allies_up = any(units[p]["HP"] > 0 for p in units if p <= 6)
                    enemies_up = any(units[p]["HP"] > 0 for p in units if p > 6)
                    if not allies_up or not enemies_up:
                        effects.continuous_attacks.clear()
                        break
                    ca = effects.continuous_attacks.popleft()
                    if units[ca.attacker]["HP"] <= 0:
                        continue
                    _apply_attack(ca.attacker, units, attacks_cfg, rng, effects, continuous=ca)
                    effects.clear_dead()
                side ^= 1
                allies_up = any(units[p]["HP"] > 0 for p in units if p <= 6)
                enemies_up = any(units[p]["HP"] > 0 for p in units if p > 6)
                if not allies_up or not enemies_up:
                    break

            allies_up = any(units[p]["HP"] > 0 for p in units if p <= 6)
            enemies_up = any(units[p]["HP"] > 0 for p in units if p > 6)
            if not allies_up or not enemies_up:
                break

        wave_hp_list = [
            {"PosId": p, "HeroModelId": int(units[p]["HeroModelId"]), "HP": int(units[p]["HP"]),
             "RP": int(units[p]["RP"])}
            for p in sorted(units)
        ]
        waves_hp.append(wave_hp_list)
        last_units = units

        for p in range(1, 7):
            if p in units:
                ally_carry_hp[p] = int(units[p]["HP"])
                ally_carry_rp[p] = int(units[p]["RP"])

        allies_up = any(units[p]["HP"] > 0 for p in units if p <= 6)
        enemies_up = any(units[p]["HP"] > 0 for p in units if p > 6)
        if enemies_up or not allies_up:
            won_all = False
            break

    ally_alive = sum(1 for p, u in last_units.items() if p <= 6 and u["HP"] > 0)
    enemy_alive = sum(1 for p, u in last_units.items() if p > 6 and u["HP"] > 0)
    ally_cur_hp = sum(u["HP"] for p, u in last_units.items() if p <= 6)
    ally_max_hp = sum(max(1, u["TotalHp"]) for p, u in last_units.items() if p <= 6)
    hp_pct = round(100.0 * ally_cur_hp / max(1, ally_max_hp), 2)

    return CombatOutcome(
        won=won_all,
        waves=len(waves_hp),
        total_rounds=total_rounds,
        ally_alive=ally_alive,
        enemy_alive=enemy_alive,
        ally_hp_pct=hp_pct,
        verify_data={"version": "201608081200", "hp": waves_hp},
    )
