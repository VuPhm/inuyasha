"""Deterministic turn-based combat simulator matching CSCommon/FightExpression + BattleCalc."""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any

from combat_effects import BattleEffects, LOCK_HEALING, MAX_RAGE, PARALYSIS, SILENCE, STUN

PVE_FRIEND_ORDER = [1, 2, 3, 4, 5, 6]
PVE_ENEMY_ORDER = [9, 8, 7, 12, 11, 10]
PVP_ENEMY_ORDER = [7, 8, 9, 10, 11, 12]


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
    rng: random.Random,
) -> list[int]:
    """Select target PosIds matching CSCommon/FightEnum.lua FightEnum_Target."""
    target_camp = int(skill.get("targetCampEnum", 2))
    if target_camp == 3:  # eSelf
        return [attacker_pos] if attacker_pos in units and units[attacker_pos]["HP"] > 0 else []
    # targetCampEnum: 1=same camp, 2/0=opposing camp
    want_ally = (attacker_camp == 1) if target_camp == 1 else (attacker_camp == 2)
    pool = [
        pos
        for pos, u in units.items()
        if u["HP"] > 0 and ((pos <= 6) == want_ally)
    ]
    if not pool:
        return []

    mode = int(skill.get("targetEnum", 1))
    target_num = max(1, int(skill.get("targetNum", 1)))
    front_positions = (1, 2, 3) if want_ally else (7, 8, 9)
    back_positions = (4, 5, 6) if want_ally else (10, 11, 12)
    front_alive = [p for p in front_positions if p in pool]
    back_alive = [p for p in back_positions if p in pool]

    if mode in (0, 1, 15):  # eSingleFront / eDesignatedHero
        col = (attacker_pos - 1) % 3
        pref = [front_positions[col], *front_positions, *back_positions]
        first = next((p for p in pref if p in pool), pool[0])
        return [first]
    if mode == 2:  # eSingleBack
        col = (attacker_pos - 1) % 3
        pref = [back_positions[col], *back_positions, *front_positions]
        first = next((p for p in pref if p in pool), pool[0])
        return [first]
    if mode == 3:  # eRowFront
        return front_alive or back_alive
    if mode == 4:  # eRowBack
        return back_alive or front_alive
    if mode == 5:  # eOneColumn
        col = (attacker_pos - 1) % 3
        col_pair = [front_positions[col], back_positions[col]]
        hits = [p for p in col_pair if p in pool]
        if not hits:
            alt = next((p for p in (*front_positions, *back_positions) if p in pool), None)
            if alt is not None:
                c = (alt - 1) % 3
                hits = [p for p in (front_positions[c], back_positions[c]) if p in pool]
        return hits
    if mode == 6:  # eAll
        return sorted(pool)
    if mode == 7:  # eRandom
        k = min(len(pool), target_num)
        return rng.sample(pool, k)
    if mode == 8:  # eHPMax
        return sorted(pool, key=lambda p: units[p]["HP"], reverse=True)[:target_num]
    if mode == 9:  # eHPMin
        return sorted(pool, key=lambda p: units[p]["HP"] / max(1, units[p]["TotalHp"]))[:target_num]
    if mode == 10:  # eRPMax
        return sorted(pool, key=lambda p: units[p]["RP"], reverse=True)[:target_num]
    if mode == 11:  # eRPMin
        return sorted(pool, key=lambda p: units[p]["RP"])[:target_num]
    if mode == 12:  # eHPLossMax
        return sorted(pool, key=lambda p: units[p]["TotalHp"] - units[p]["HP"], reverse=True)[:target_num]
    return pool[:target_num]


def _apply_attack(
    atk_pos: int,
    units: dict[int, dict[str, Any]],
    attacks_cfg: dict[str, Any],
    rng: random.Random,
    effects: BattleEffects,
) -> None:
    """Execute single hero turn using CSCommon/FightExpression.lua formulas."""
    atk = units[atk_pos]
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
    atk_rp_snapshot = int(atk["RP"])

    atk_camp = 1 if atk_pos <= 6 else 2
    targets = _select_targets(atk_pos, atk_camp, units, skill, rng)
    factor = float(skill.get("factor", 10000)) / 10000.0
    is_heal = int(skill.get("type", 0)) == 1
    active_attack = (1, 3 if use_skill else 2)
    active_defense = (8,) if is_heal else (4, 6 if use_skill else 5)
    action_mods = defaultdict(Counter)
    effects.apply(atk_pos, atk_pos, None, targets, active_attack, (1,), action_mods)

    if use_skill:
        atk["RP"] = 0

    after_action: set[int] = set()
    attack_rage = 0
    for tpos in targets:
        vic = units[tpos]
        if vic["HP"] <= 0:
            continue
        hit_mods = defaultdict(Counter)
        effects.apply(atk_pos, atk_pos, tpos, [tpos], active_attack, (1,), hit_mods, compared=True)
        effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, (1,), hit_mods)
        effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, (1,), hit_mods, compared=True)

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
            rate = (stat(atk_pos, "DAMADDR") - stat(tpos, "DAMCUTR")) / 10000
            dmg = hurt_strength * factor * rage_scale * max(0.01, 1 + rate)
            dodge = max((stat(tpos, "DOD") - stat(atk_pos, "HIT", 10000)) / 100 + 100, 0)
            crit = max((stat(atk_pos, "CRI") - stat(tpos, "TEN")) / 100, 0)
            block = max((stat(tpos, "BLO") - stat(atk_pos, "BOG")) / 100, 0)
            if roll < dodge:
                after_action.add(3)
                effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, (3,), hit_mods)
                effects.apply(atk_pos, atk_pos, tpos, [tpos], active_attack, (3,), hit_mods, target_only=True)
                continue
            if roll < dodge + crit:
                phases.add(2)
                dmg = max(1, math.ceil(dmg * (1.5 + (stat(atk_pos, "CRId") - stat(tpos, "TEND")) / 10000)))
            elif roll < dodge + crit + block:
                phases.add(4)
                dmg = max(1, math.ceil(dmg * 0.5))
            else:
                dmg = math.ceil(dmg)
            damage = min(vic["HP"], max(1, dmg + stat(atk_pos, "DAMADD") - stat(tpos, "DAMCUT")))
            vic["HP"] -= damage
            if not vic.get("IsBoss"):
                effects.rage(tpos, damage * 100 // vic["OpeningHP"])
            if vic["HP"] == 0 and not atk.get("IsBoss"):
                attack_rage += 25
        effects.apply(tpos, atk_pos, atk_pos, [atk_pos], active_defense, phases, hit_mods)
        effects.apply(atk_pos, atk_pos, tpos, [tpos], active_attack, phases, hit_mods, target_only=True)
        after_action.update(phases)

    if not use_skill and 5 in after_action:
        attack_rage += 20 if atk.get("IsBoss") else 25
    effects.rage(atk_pos, attack_rage)
    effects.apply(atk_pos, atk_pos, None, targets, active_attack, after_action, action_mods, target_only=False)


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
        rng = random.Random(seed)
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
