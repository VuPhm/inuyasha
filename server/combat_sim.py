"""Deterministic turn-based combat simulator matching CSCommon/FightExpression + BattleCalc."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

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
) -> None:
    """Execute single hero turn using CSCommon/FightExpression.lua formulas."""
    atk = units[atk_pos]
    ra_id = int(atk.get("RAId", 0))
    na_id = int(atk.get("NAId", 0))
    ra_skill = attacks_cfg.get(str(ra_id), {})
    na_skill = attacks_cfg.get(str(na_id), {})

    need_rp = int(ra_skill.get("useRP", 100) or 100)
    use_skill = bool(ra_skill) and int(atk["RP"]) >= need_rp
    skill = ra_skill if use_skill else (na_skill or ra_skill)
    atk_rp_snapshot = int(atk["RP"])

    atk_camp = 1 if atk_pos <= 6 else 2
    targets = _select_targets(atk_pos, atk_camp, units, skill, rng)
    factor = float(skill.get("factor", 10000)) / 10000.0
    is_heal = int(skill.get("type", 0)) == 1
    atk_ap = float(atk.get("AP", 0))

    if use_skill:
        atk["RP"] = max(0, int(atk["RP"]) - need_rp)
    else:
        atk["RP"] = int(atk["RP"]) + 25

    for tpos in targets:
        vic = units[tpos]
        if vic["HP"] <= 0:
            continue
        if is_heal:
            base_heal = max(atk_ap * factor + float(atk.get("CP", 0)) + float(vic.get("BCP", 0)), 0.0)
            cri_prob = max(0.0, float(atk.get("CRI", 0)) / 100.0)
            is_crit = rng.uniform(0, 100) < cri_prob
            heal_val = max(1, math.ceil(base_heal * (1.5 if is_crit else 1.0))) if base_heal > 0 else 0
            vic["HP"] = min(int(vic["TotalHp"]), int(vic["HP"]) + heal_val)
            continue

        vic_def = float(vic.get("DEF", 0))
        hurt_strength = max(atk_ap - vic_def, atk_ap * 0.1)
        if use_skill:
            org_hurt = hurt_strength * factor * max(0.1, 1.0 + (atk_rp_snapshot - need_rp) / 200.0)
        else:
            org_hurt = hurt_strength * factor
        damaddr = float(atk.get("DAMADDR", 0)) / 10000.0
        damcutr = float(vic.get("DAMCUTR", 0)) / 10000.0
        normal_hurt = org_hurt * max(0.01, 1.0 + (damaddr - damcutr))

        val_dod = max(float(vic.get("DOD", 0)) / 100.0 - float(atk.get("HIT", 10000)) / 100.0 + 100.0, 0.0)
        val_cri = max(float(atk.get("CRI", 0)) / 100.0 - float(vic.get("TEN", 0)) / 100.0, 0.0)
        val_blo = max(float(vic.get("BLO", 0)) / 100.0 - float(atk.get("BOG", 0)) / 100.0, 0.0)
        roll = rng.uniform(0.0, 100.0)

        if roll < val_dod:
            dmg = 0
        elif roll < val_dod + val_cri:
            crit_rate = 1.5 + (float(atk.get("CRId", 0)) - float(vic.get("TEND", 0))) / 10000.0
            dmg = max(1, math.ceil(normal_hurt * max(1.1, crit_rate)))
        elif roll < val_dod + val_cri + val_blo:
            dmg = max(1, math.ceil(normal_hurt * 0.5))
        else:
            dmg = max(1, math.ceil(normal_hurt))

        if dmg > 0:
            net_dmg = max(1, int(dmg + float(atk.get("DAMADD", 0)) - float(vic.get("DAMCUT", 0))))
            vic["HP"] = max(0, int(vic["HP"]) - net_dmg)


def simulate_fight_info(
    fight_info: dict[str, Any],
    attacks_cfg: dict[str, Any],
    max_rounds: int = 30,
) -> CombatOutcome:
    """
    Evaluate all waves of a FightInfo payload using real combat math.

    Respects IsPVP turn order ([7..12] vs [9,8,7,12,11,10]) and never rigs outcomes.
    """
    fight_objs = fight_info.get("FightObjs", [])
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
            u["RP"] = int(u.get("RP", 50))
            if idx <= 6 and w_idx > 0 and idx in ally_carry_hp:
                u["HP"] = ally_carry_hp[idx]
                u["RP"] = ally_carry_rp.get(idx, u["RP"])
            units[idx] = u

        ally_total_fsp = sum(int(u.get("FSP", 0)) for p, u in units.items() if p <= 6 and u["HP"] > 0)
        enemy_total_fsp = sum(int(u.get("FSP", 0)) for p, u in units.items() if p > 6 and u["HP"] > 0)
        friend_first = ally_total_fsp >= enemy_total_fsp

        for _rnd in range(1, max_rounds + 1):
            total_rounds += 1
            order = []
            f_live = [p for p in PVE_FRIEND_ORDER if p in units and units[p]["HP"] > 0]
            e_live = [p for p in enemy_order if p in units and units[p]["HP"] > 0]
            first_q, second_q = (f_live, e_live) if friend_first else (e_live, f_live)
            max_len = max(len(first_q), len(second_q))
            for i in range(max_len):
                if i < len(first_q):
                    order.append(first_q[i])
                if i < len(second_q):
                    order.append(second_q[i])

            for pos in order:
                if pos not in units or units[pos]["HP"] <= 0:
                    continue
                _apply_attack(pos, units, attacks_cfg, rng)
                allies_up = any(units[p]["HP"] > 0 for p in units if p <= 6)
                enemies_up = any(units[p]["HP"] > 0 for p in units if p > 6)
                if not allies_up or not enemies_up:
                    break

            allies_up = any(units[p]["HP"] > 0 for p in units if p <= 6)
            enemies_up = any(units[p]["HP"] > 0 for p in units if p > 6)
            if not allies_up or not enemies_up:
                break

        wave_hp_list = [
            {"PosId": p, "HeroModelId": int(units[p]["HeroModelId"]), "HP": int(units[p]["HP"])}
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
