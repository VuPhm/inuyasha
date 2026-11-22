"""Supported VN combat buffs and their wave-local state."""

from __future__ import annotations

import math
import operator
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

MAX_RAGE = 200
STUN, SILENCE, PARALYSIS, LOCK_RAGE, LOCK_HEALING = range(501, 506)
CONTROL = frozenset(range(501, 506))
CONTROL_IMMUNITY = {attr - 200: attr for attr in range(701, 706)}
IMMUNE_RAGE_LOSS = 706
IMMUNE_THORN = 707
IMMUNITIES = frozenset((*CONTROL_IMMUNITY.values(), IMMUNE_RAGE_LOSS, IMMUNE_THORN))
CLEAR_DEBUFFS = 499
SHIELD = 601
HPDOT = 602
ORIG_REF_ATTR = {201: "TotalHp", 202: "OriginalAP", 203: "OriginalDEF"}
STATS = {
    202: "AP", 203: "DEF", 301: "HIT", 302: "DOD", 303: "CRI", 304: "TEN",
    305: "BLO", 306: "BOG", 307: "CRId", 308: "TEND", 401: "APR", 403: "DEFR",
    404: "CP", 405: "BCP", 406: "CPR", 407: "BCPR",
    408: "DAMADD", 409: "DAMCUT", 410: "DAMADDR", 411: "DAMCUTR",
}
PERCENT_RATES = frozenset((401, 403, 406, 407, 410, 411))
REF_COMPARE = {1: operator.ge, 2: operator.gt, 3: operator.eq, 4: operator.lt, 5: operator.le}


def _is_special_range(row: dict[str, Any], lo: int, hi: int) -> bool:
    return row["typeEnum"] == 5 and lo <= row["addValue"] <= hi


def _is_static_special(row: dict[str, Any]) -> bool:
    return (
        _is_special_range(row, 90040000, 90049999)
        or _is_special_range(row, 90060000, 90069999)
        or _is_special_range(row, 90070000, 90079999)
    )


def _is_active_special(row: dict[str, Any]) -> bool:
    return (
        _is_special_range(row, 90020000, 90029999)
        or _is_special_range(row, 90030000, 90039999)
        or _is_special_range(row, 90050000, 90059999)
    )


def _is_death_trigger(row: dict[str, Any]) -> bool:
    return (
        row["typeEnum"] == 9
        and row["triggerCondition2"] == 5
        and row["refAttr"] == 201
        and row["refCondition"] in (3, 5)
        and row["refValue"] == 0
    )


def _is_reborn_effect(row: dict[str, Any]) -> bool:
    return _is_death_trigger(row) and row["targetCampEnum"] == 3 and row["addAttrEnum"] == 201


def _resistance(row: dict[str, Any]) -> bool:
    return (row["typeEnum"] == 5 and 90010000 <= row["addValue"] <= 90019999
            and row["targetCampEnum"] == 3 and row["maxTime"] == -1)


def _supports_effect(row: dict[str, Any], buffs: dict[str, Any], *, attached: bool) -> bool:
    kind, attr, phase = row["typeEnum"], row["addAttrEnum"], row["triggerCondition2"]
    camp, c1 = row["targetCampEnum"], row["triggerCondition1"]
    if row["maxNum"] == 0 or row["maxTime"] == 0:
        return False
    if not attached and _resistance(row):
        return True
    if not attached and c1 == 7 and kind == 6:
        child = buffs.get(str(row["addValue"]))
        return (
            child is not None
            and camp == 3
            and row["refAttr"] in ORIG_REF_ATTR
            and row["refValue"] > 0
            and _supports_effect(child, buffs, attached=True)
            and child["addAttrEnum"] == SHIELD
            and child["addType"] == 1
        )
    if c1 not in (1, 2, 3, 4, 5, 6, 8):
        return False
    if not attached and _is_static_special(row):
        return True
    if not attached and _is_active_special(row):
        if _is_special_range(row, 90020000, 90029999):
            return camp == 3 and c1 in (1, 2, 3) and phase == 5
        if _is_special_range(row, 90030000, 90039999):
            return camp == 3 and c1 in (1, 2, 3) and phase in (2, 5)
        return camp == 3 and c1 in (4, 5, 6) and phase == 4
    lowest_rage_ally = kind == 2 and attr == 205 and row["targetEnum"] == 11 and row["targetNum"] == 1
    most_injured_ally = kind in (2, 7, 9) and attr == 201 and row["targetEnum"] == 12
    row_ally = (kind == 6 or kind == 2) and row["targetEnum"] in (3, 4)
    death_ally = not attached and _is_death_trigger(row) and row["targetEnum"] == 6
    if camp not in (0, 3):
        if camp == 2:
            if not (death_ally and row["targetEnum"] == 6):
                return False
        elif camp != 1 or (row["targetEnum"] != 6 and not lowest_rage_ally and not most_injured_ally and not row_ally):
            return False
    if attr == CLEAR_DEBUFFS:
        return not attached and kind == 2 and camp == 0 and phase == 5
    if kind == 1:
        return (not attached and attr == 410 and phase == 1 and camp == 3
                and row["refAttr"] == 201 and row["refValue"] > 0 and row["addType"] == 1)
    if kind == 0:
        return (not attached and phase == 1 and camp == 3
                and row["refAttr"] == 201 and row["refValue"] > 0
                and attr in STATS and row["addType"] in (1, 2))
    if attr in IMMUNITIES:
        return kind == 2 and camp == 3 and row["addType"] == 1 and row["addValue"] > 0
    if attr in CONTROL:
        return (attached and kind == 2 and camp == 3 and row["addType"] == 1
                and row["addValue"] > 0 and row["triggerOdds"] == 10000)
    if attr == SHIELD:
        return attached and kind == 2 and camp == 3 and row["addType"] == 1
    if attr == HPDOT:
        return attached and kind == 2 and camp == 3 and phase == 5 and row["addType"] == 1
    if _is_reborn_effect(row):
        return row["addType"] in (1, 2, 4)
    if attached and (camp != 3 or kind != 2):
        return False
    if not attached and (kind == 6 or (kind == 2 and attr == 0)):
        child = buffs.get(str(row["addValue"]))
        if child is None or not _supports_effect(child, buffs, attached=True):
            return False
        if kind == 2:
            return phase in (1, 2, 3, 4, 5) and row["refAttr"] == 0
        if row["refAttr"] == 0:
            return phase in (2, 3, 4, 5)
        return phase in (2, 3, 4, 5) and row["refAttr"] in ORIG_REF_ATTR and row["refValue"] > 0 and child["addType"] == 1
    if kind == 2 and row["refAttr"] != 0:
        return False
    if kind == 7:
        return (not attached and attr == 201 and phase == 5 and row["refAttr"] == 400
                and row["refValue"] > 0 and (camp == 3 or (camp == 1 and row["targetEnum"] == 12)))
    if kind == 3:
        if attached or row["refCondition"] not in REF_COMPARE:
            return False
        if phase == 1:
            if camp != 3 or row["refAttr"] not in (201, HPDOT):
                return False
        elif not (phase == 5 and attr == 205 and row["addType"] == 1
                  and ((camp == 0 and row["refAttr"] == HPDOT) or (camp == 3 and row["refAttr"] == 201))):
            return False
    if kind == 4 and (attached or phase != 1 or row["refAttr"] != 201
                      or camp != 3 or row["refCondition"] not in REF_COMPARE):
        return False
    if kind == 9:
        if _is_death_trigger(row):
            if attached or camp not in (1, 2):
                return False
            return (attr == 201 and row["addType"] in (1, 2, 4)) or (attr == 205 and row["addType"] == 1)
        if attached or phase != 1 or row["refAttr"] not in (201, 205) or camp != 3 or row["refCondition"] not in REF_COMPARE:
            return False
    if kind not in (0, 2, 3, 4, 9):
        return False
    if attr == 201:
        return ((not attached and kind == 2 and phase in (2, 5) and row["addType"] in (2, 4)
                 and (camp in (0, 3) or (camp == 1 and row["targetEnum"] == 12)))
                or (_is_death_trigger(row) and row["addType"] in (1, 2, 4)))
    if attr == 205:
        return kind in (2, 3, 9) and phase in (2, 3, 4, 5) and row["addType"] == 1
    return attr in STATS and phase == 1 and row["addType"] in (1, 2)


def supports_talent_buff(row: dict[str, Any], buffs: dict[str, Any]) -> bool:
    """Select whole effects that both the VN client and simulator can evaluate."""
    return _supports_effect(row, buffs, attached=False)


def buff_ids(value: Any) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip())) if isinstance(value, str) else []


@dataclass
class ContinuousAttack:
    attacker: int
    targets: list[int] | None = None
    is_skill: bool = False
    attack_id: int = 0
    scale: float | None = None
    exclude_types: frozenset[int] = frozenset()
    dont_add_rp: bool = False


@dataclass
class Effect:
    row: dict[str, Any]
    trigger: int
    source: int | None = None
    turns: int = -1
    uses: int = -1
    before_action: bool = False
    override_add_value: int | None = None
    shield_absorbed: int = 0


class BattleEffects:
    def __init__(self, units, attacks, buffs, rng):
        self.units = units
        self.buffs = buffs
        self.rng = rng
        self.active: dict[int, list[Effect]] = {pos: [] for pos in units}
        self.continuous_attacks: deque[ContinuousAttack] = deque()
        self.sputtering: dict[int, float] = {}
        self.reflect: dict[int, float] = {}
        self.immune_die: dict[int, int] = {}
        for pos, unit in units.items():
            for attack, trigger in (("NAId", 2), ("RAId", 3)):
                skill = attacks.get(str(unit.get(attack)), {})
                for bid in buff_ids(skill.get("buffList")):
                    self._load(pos, bid, trigger)
            for bid in buff_ids(unit.get("BuffList")):
                self._load(pos, bid)

    def _orig_ref_value(self, pos: int, row: dict[str, Any]) -> int:
        u = self.units[pos]
        ref_attr = row["refAttr"]
        orig_key = ORIG_REF_ATTR[ref_attr]
        fallback_key = "AP" if ref_attr == 202 else ("DEF" if ref_attr == 203 else "TotalHp")
        orig_val = u.get(orig_key, u.get(fallback_key, 0))
        return math.ceil(orig_val * row["refValue"] / 10000)

    def _load(self, pos, buff_id, trigger=None):
        row = self.buffs.get(buff_id)
        if not row or not supports_talent_buff(row, self.buffs):
            return
        if _is_special_range(row, 90040000, 90049999):
            self.sputtering[pos] = row["refValue"] / 10000.0
            return
        if _is_special_range(row, 90060000, 90069999):
            self.reflect[pos] = row["refValue"] / 10000.0
            return
        if _is_special_range(row, 90070000, 90079999):
            self.immune_die[pos] = row["triggerOdds"]
            return
        if row["triggerCondition1"] == 7 and row["typeEnum"] == 6:
            child = self.buffs[str(row["addValue"])]
            modify_val = self._orig_ref_value(pos, row)
            self._add(
                pos,
                child,
                child["triggerCondition1"],
                source=None,
                added_this_turn=False,
                before_calc=False,
                override_add_value=modify_val * 100,
            )
            return
        self._add(pos, row, trigger if trigger is not None else row["triggerCondition1"])

    def clear_dead(self) -> None:
        for pos, unit in self.units.items():
            if unit["HP"] <= 0:
                self.active[pos].clear()
                self.sputtering.pop(pos, None)
                self.reflect.pop(pos, None)
                self.immune_die.pop(pos, None)

    def try_immune_die(self, pos: int) -> bool:
        odds = self.immune_die.get(pos)
        if odds is None:
            return False
        if odds >= 10000 or self.rng.randrange(10000) < odds:
            self.immune_die.pop(pos, None)
            return True
        return False

    def use_shield(self, pos: int, damage: int) -> int:
        if damage <= 0:
            return 0
        remaining = damage
        absorbed = 0
        depleted: list[Effect] = []
        states = self.active[pos]
        for eff in states:
            if eff.row["addAttrEnum"] != SHIELD:
                continue
            eff_add = eff.override_add_value if eff.override_add_value is not None else eff.row["addValue"]
            capacity = math.floor(eff_add / 100 + 0.5)
            avail = max(0, capacity - eff.shield_absorbed)
            used = min(remaining, avail)
            if used > 0:
                eff.shield_absorbed += used
                absorbed += used
                remaining -= used
            if eff.shield_absorbed >= capacity:
                depleted.append(eff)
            if remaining == 0:
                break
        if depleted:
            states[:] = [eff for eff in states if eff not in depleted]
        return absorbed

    def _add(
        self,
        pos,
        row,
        trigger,
        source=None,
        *,
        added_this_turn=False,
        before_calc=False,
        override_add_value=None,
    ):
        states = self.active[pos]
        limit = row["overlayNum"]
        matches = [effect for effect in states if effect.row["ID"] == row["ID"]]
        if limit >= 0:
            for effect in matches[:max(0, len(matches) - max(1, limit) + 1)]:
                states.remove(effect)
        turns = row["maxTime"]
        # VN increments new after-calculation children by one before the casting turn ticks (FightBuffModel.lua:2275).
        if turns > 0 and added_this_turn and not before_calc:
            turns += 1
        before_action = bool(before_calc) if added_this_turn else False
        states.append(Effect(row, trigger, source, turns, row["maxNum"], before_action, override_add_value))

    def has(self, pos, attr):
        return any(effect.row["addAttrEnum"] == attr and effect.uses != 0 for effect in self.active[pos])

    def _change_hp(self, pos: int, delta: int, *, allow_reborn: bool = False) -> None:
        u = self.units[pos]
        if delta == 0:
            return
        if u["HP"] <= 0 and not (allow_reborn and delta > 0):
            return
        if delta > 0:
            if self.has(pos, LOCK_HEALING):
                return
            u["HP"] = min(u["TotalHp"], u["HP"] + delta)
        else:
            u["HP"] = max(0, u["HP"] + delta)

    def _select_camp_recipients(self, owner: int, row: dict[str, Any], *, same_side: bool) -> list[int]:
        pool = sorted(p for p in self.units if (((p <= 6) == (owner <= 6)) == same_side) and self.units[p]["HP"] > 0)
        if not pool:
            return []
        te = row["targetEnum"]
        tnum = max(1, int(row.get("targetNum", 1)))
        if not same_side:
            return pool
        if te == 3:
            front = (1, 2, 3) if owner <= 6 else (7, 8, 9)
            back = (4, 5, 6) if owner <= 6 else (10, 11, 12)
            return [p for p in front if p in pool] or [p for p in back if p in pool]
        if te == 4:
            front = (1, 2, 3) if owner <= 6 else (7, 8, 9)
            back = (4, 5, 6) if owner <= 6 else (10, 11, 12)
            return [p for p in back if p in pool] or [p for p in front if p in pool]
        if te == 11:
            return sorted((p for p in pool if p != owner), key=lambda p: (self.units[p]["RP"], p))[:tnum]
        if te == 12:
            return sorted(pool, key=lambda p: (-(self.units[p]["TotalHp"] - self.units[p]["HP"]), p))[:tnum]
        return pool

    def tick(self, pos, *, before):
        for target, effects in self.active.items():
            if self.units[target]["HP"] <= 0:
                effects.clear()
                continue
            for effect in effects:
                if effect.source == pos and effect.before_action == before and effect.turns > 0:
                    effect.turns -= 1
            effects[:] = [effect for effect in effects if effect.turns != 0 and effect.uses != 0]

    def start(self, first_attacker):
        # FightBuffModel.rewriteWhoAddBuffInBuffInfo attaches initial timers to the first acting hero.
        for effects in self.active.values():
            for effect in effects:
                if effect.turns > 0 and effect.source is None:
                    effect.source = first_attacker
                    effect.before_action = True

    def rage(self, pos, delta, *, from_buff=False):
        if (delta > 0 and self.has(pos, LOCK_RAGE)
                or delta < 0 and from_buff and self.has(pos, IMMUNE_RAGE_LOSS)):
            return
        u = self.units[pos]
        u["RP"] = max(0, min(MAX_RAGE, int(u["RP"]) + delta))

    def _apply_child(self, row, target, attacker, *, before_calc=False, modify_value=None):
        attr = row["addAttrEnum"]
        override_add = int(modify_value) * 100 if (modify_value is not None and row["addType"] == 1) else None
        eff_add = override_add if override_add is not None else row["addValue"]
        if attr in CONTROL:
            if self.has(target, CONTROL_IMMUNITY[attr]):
                return
        elif attr == 205 and eff_add < 0 and self.has(target, IMMUNE_RAGE_LOSS):
            return
        if attr in CONTROL_IMMUNITY.values():
            self.active[target][:] = [effect for effect in self.active[target]
                                     if effect.row["addAttrEnum"] != attr - 200]
        self._add(
            target,
            row,
            row["triggerCondition1"],
            attacker,
            added_this_turn=True,
            before_calc=before_calc,
            override_add_value=override_add,
        )

    def apply(
        self,
        owner,
        attacker,
        opposite,
        targets,
        triggers,
        phases,
        modifiers,
        *,
        target_only=None,
        compared=False,
        exclude_types=frozenset(),
    ):
        for effect in tuple(self.active[owner]):
            row = effect.row
            camp, kind, attr = row["targetCampEnum"], row["typeEnum"], row["addAttrEnum"]
            if (effect.uses == 0 or kind in exclude_types or effect.trigger not in triggers
                    or row["triggerCondition2"] not in phases
                    or attr in CONTROL or attr in IMMUNITIES or attr == SHIELD or _resistance(row)):
                continue
            if self.units[owner]["HP"] <= 0 and not _is_death_trigger(row):
                continue
            if target_only is not None and target_only != (camp == 0):
                continue
            if (kind in (3, 4)) != compared:
                continue
            reborn = _is_reborn_effect(row)
            if camp == 3:
                recipients = [owner] if (self.units[owner]["HP"] > 0 or reborn) else []
            elif camp == 0:
                recipients = [p for p in targets if self.units[p]["HP"] > 0]
            else:
                recipients = self._select_camp_recipients(owner, row, same_side=(camp == 1))
            if not recipients:
                continue
            if kind in (3, 4, 9):
                if opposite is None and kind in (3, 4):
                    continue
                if kind == 3 and row["refAttr"] >= 500:
                    val = 1 if self.has(opposite, row["refAttr"]) else 0
                    threshold = 1 if (row["refValue"] // 10000) != 0 else 0
                    if not REF_COMPARE[row["refCondition"]](val, threshold):
                        continue
                elif kind == 9 and row["refAttr"] == 205:
                    cur_rp = self.units[owner]["RP"]
                    threshold = math.ceil(row["refValue"] / 10000)
                    if not REF_COMPARE[row["refCondition"]](cur_rp, threshold):
                        continue
                else:
                    test = self.units[opposite if kind == 3 else owner]
                    if kind == 9 and row["refValue"] == 0:
                        threshold = 0
                    else:
                        threshold = (self.units[opposite]["HP"] if kind == 4
                                     else math.ceil(test["OpeningHP"] * row["refValue"] / 10000))
                    if not REF_COMPARE[row["refCondition"]](test["HP"], threshold):
                        continue
            add_times = 1
            if kind == 5:
                if self.units[owner]["HP"] <= 0:
                    continue
                if row["triggerOdds"] < 10000 and self.rng.randrange(10000) >= row["triggerOdds"]:
                    continue
                scale = (row["refValue"] / 10000.0) if row["refValue"] != 0 else None
                na_id = int(self.units[owner].get("NAId", 0))
                if _is_special_range(row, 90020000, 90029999):
                    if not any(self.units[t]["HP"] <= 0 for t in targets):
                        continue
                    self.continuous_attacks.append(ContinuousAttack(
                        attacker=owner, targets=None, is_skill=False, attack_id=na_id,
                        scale=scale, exclude_types=frozenset(), dont_add_rp=False,
                    ))
                elif _is_special_range(row, 90030000, 90039999):
                    self.continuous_attacks.append(ContinuousAttack(
                        attacker=owner, targets=None, is_skill=False, attack_id=na_id,
                        scale=scale, exclude_types=frozenset({5}), dont_add_rp=False,
                    ))
                elif _is_special_range(row, 90050000, 90059999):
                    if attacker is None:
                        continue
                    self.continuous_attacks.append(ContinuousAttack(
                        attacker=owner, targets=[attacker], is_skill=False, attack_id=na_id,
                        scale=scale, exclude_types=frozenset(range(10)), dont_add_rp=True,
                    ))
                if effect.uses > 0:
                    effect.uses -= 1
                continue
            if kind == 0:
                orig_hp = max(self.units[owner]["TotalHp"], self.units[owner]["OpeningHP"])
                step_hp = math.ceil(orig_hp * row["refValue"] / 10000)
                add_times = (orig_hp - self.units[owner]["HP"]) // step_hp if step_hp > 0 else 0
                if add_times <= 0:
                    continue
            if kind == 6 or attr == 0:
                child = self.buffs[str(row["addValue"])]
                modify_val = None
                if kind == 6 and row["refAttr"] in ORIG_REF_ATTR and row["refValue"] != 0:
                    modify_val = self._orig_ref_value(owner, row)
                before_calc = 1 in phases
                for target in recipients:
                    resistance = next((e.row["refValue"] for e in reversed(self.active[target])
                                       if _resistance(e.row)), 0)
                    odds = row["triggerOdds"] - (resistance if child["addAttrEnum"] in (STUN, SILENCE, PARALYSIS) else 0)
                    if odds >= 10000 or self.rng.randrange(10000) < odds:
                        self._apply_child(child, target, attacker, before_calc=before_calc, modify_value=modify_val)
            elif kind == 7:
                if row["triggerOdds"] < 10000 and self.rng.randrange(10000) >= row["triggerOdds"]:
                    continue
                heal = math.ceil(self.units[owner].get("DAM", 0) * row["refValue"] / 10000)
                for target in recipients:
                    self._change_hp(target, heal)
            elif row["triggerOdds"] >= 10000 or self.rng.randrange(10000) < row["triggerOdds"]:
                eff_add = effect.override_add_value if effect.override_add_value is not None else row["addValue"]
                for target in recipients:
                    if attr == CLEAR_DEBUFFS:
                        self.active[target][:] = [active for active in self.active[target] if not active.row["isDebuff"]]
                        continue
                    if attr == HPDOT:
                        dmg = math.floor(eff_add / 100 + 0.5)
                        self._change_hp(target, -dmg)
                        continue
                    if attr == 201:
                        if row["addType"] == 2:
                            delta = math.floor(self.units[target]["TotalHp"] * eff_add / 10000 + 0.5)
                        elif row["addType"] == 4:
                            delta = math.floor(self.units[owner]["AP"] * eff_add / 10000 + 0.5)
                        else:
                            delta = math.floor(eff_add / 100 + 0.5)
                        self._change_hp(target, delta, allow_reborn=reborn)
                        continue
                    if attr == 205:
                        self.rage(target, math.floor(eff_add / 100 + 0.5), from_buff=True)
                        continue
                    if kind == 1:
                        unit = self.units[owner]
                        cost = math.ceil(max(unit["HP"], unit["TotalHp"]) * row["refValue"] / 10000)
                        unit["HP"] = max(1, unit["HP"] - cost)
                    stat = STATS[attr]
                    value = (self.units[target].get(stat, 0) * eff_add / 10000
                             if row["addType"] == 2 else eff_add / 100)
                    if attr in PERCENT_RATES:
                        value *= 10000
                    elif attr in range(301, 309):
                        value = math.floor(value + 0.5) * 100
                    else:
                        value = math.floor(value + 0.5)
                    modifiers[target][stat] += value * add_times
            else:
                continue
            if effect.uses > 0:
                effect.uses -= 1
