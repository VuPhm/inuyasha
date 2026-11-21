"""Supported VN combat buffs and their wave-local state."""

from __future__ import annotations

import math
import operator
from collections import Counter
from dataclasses import dataclass
from typing import Any

MAX_RAGE = 200
STUN, SILENCE, PARALYSIS, LOCK_RAGE, LOCK_HEALING = range(501, 506)
CONTROL = frozenset(range(501, 506))
CONTROL_IMMUNITY = {attr - 200: attr for attr in range(701, 706)}
IMMUNE_RAGE_LOSS = 706
IMMUNITIES = frozenset((*CONTROL_IMMUNITY.values(), IMMUNE_RAGE_LOSS))
STATS = {
    202: "AP", 203: "DEF", 301: "HIT", 302: "DOD", 303: "CRI", 304: "TEN",
    305: "BLO", 306: "BOG", 307: "CRId", 308: "TEND", 401: "APR", 403: "DEFR",
    404: "CP", 405: "BCP", 406: "CPR", 407: "BCPR",
    408: "DAMADD", 409: "DAMCUT", 410: "DAMADDR", 411: "DAMCUTR",
}
PERCENT_RATES = frozenset((401, 403, 406, 407, 410, 411))
REF_COMPARE = {1: operator.ge, 2: operator.gt, 3: operator.eq, 4: operator.lt, 5: operator.le}


def _resistance(row: dict[str, Any]) -> bool:
    return (row["typeEnum"] == 5 and 90010000 <= row["addValue"] <= 90019999
            and row["targetCampEnum"] == 3 and row["maxTime"] == -1)


def _supports_effect(row: dict[str, Any], buffs: dict[str, Any], *, attached: bool) -> bool:
    kind, attr, phase = row["typeEnum"], row["addAttrEnum"], row["triggerCondition2"]
    camp = row["targetCampEnum"]
    if not attached and _resistance(row):
        return True
    if row["maxNum"] == 0 or row["maxTime"] == 0 or row["triggerCondition1"] not in (1, 2, 3, 4, 5, 6, 8):
        return False
    if camp not in (0, 3) and (camp != 1 or row["targetEnum"] != 6):
        return False
    if attr in IMMUNITIES:
        return kind == 2 and camp == 3 and row["addType"] == 1 and row["addValue"] > 0
    if attr in CONTROL:
        return (attached and kind == 2 and camp == 3 and row["addType"] == 1
                and row["addValue"] > 0 and row["triggerOdds"] == 10000)
    if attached and (camp != 3 or kind != 2):
        return False
    # Only one level of attachment with an unchanged child value.
    if not attached and (kind == 6 or kind == 2 and attr == 0):
        child = buffs.get(str(row["addValue"]))
        return (phase in (2, 3, 4, 5) and row["refAttr"] == 0 and child is not None
                and _supports_effect(child, buffs, attached=True))
    if kind == 2 and row["refAttr"] != 0:
        return False
    if kind in (3, 4, 9) and (attached or phase != 1 or row["refAttr"] != 201
                              or camp != 3 or row["refCondition"] not in REF_COMPARE):
        return False
    if kind not in (2, 3, 4, 9):
        return False
    if attr == 205:
        return kind == 2 and phase in (2, 3, 4, 5) and row["addType"] == 1
    if attr in (405, 407) and row["triggerCondition1"] not in (1, 2, 3, 8):
        return False
    return attr in STATS and phase == 1 and row["addType"] in (1, 2)


def supports_talent_buff(row: dict[str, Any], buffs: dict[str, Any]) -> bool:
    """Select whole effects that both the VN client and simulator can evaluate."""
    return _supports_effect(row, buffs, attached=False)


def buff_ids(value: Any) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip())) if isinstance(value, str) else []


@dataclass
class Effect:
    row: dict[str, Any]
    trigger: int
    source: int | None = None
    turns: int = -1
    uses: int = -1
    before_action: bool = False


class BattleEffects:
    def __init__(self, units, attacks, buffs, rng):
        self.units = units
        self.buffs = buffs
        self.rng = rng
        self.active: dict[int, list[Effect]] = {pos: [] for pos in units}
        for pos, unit in units.items():
            for attack, trigger in (("NAId", 2), ("RAId", 3)):
                skill = attacks.get(str(unit.get(attack)), {})
                for bid in buff_ids(skill.get("buffList")):
                    self._load(pos, bid, trigger)
            for bid in buff_ids(unit.get("BuffList")):
                self._load(pos, bid)

    def _load(self, pos, buff_id, trigger=None):
        row = self.buffs.get(buff_id)
        if row and supports_talent_buff(row, self.buffs):
            self._add(pos, row, trigger if trigger is not None else row["triggerCondition1"])

    def _add(self, pos, row, trigger, source=None, *, added_this_turn=False):
        states = self.active[pos]
        limit = row["overlayNum"]
        matches = [effect for effect in states if effect.row["ID"] == row["ID"]]
        if limit >= 0:
            for effect in matches[:max(0, len(matches) - max(1, limit) + 1)]:
                states.remove(effect)
        turns = row["maxTime"]
        # VN increments new after-calculation children by one before the casting turn ticks.
        if turns > 0 and added_this_turn:
            turns += 1
        states.append(Effect(row, trigger, source, turns, row["maxNum"]))

    def has(self, pos, attr):
        return any(effect.row["addAttrEnum"] == attr and effect.uses != 0 for effect in self.active[pos])

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

    def _apply_child(self, row, target, attacker):
        attr = row["addAttrEnum"]
        if attr in CONTROL:
            if self.has(target, CONTROL_IMMUNITY[attr]):
                return
        elif attr == 205 and row["addValue"] < 0 and self.has(target, IMMUNE_RAGE_LOSS):
            return
        if attr in CONTROL_IMMUNITY.values():
            self.active[target][:] = [effect for effect in self.active[target]
                                     if effect.row["addAttrEnum"] != attr - 200]
        self._add(target, row, row["triggerCondition1"], attacker, added_this_turn=True)

    def apply(self, owner, attacker, opposite, targets, triggers, phases, modifiers, *, target_only=None, compared=False):
        for effect in tuple(self.active[owner]):
            row = effect.row
            camp, kind, attr = row["targetCampEnum"], row["typeEnum"], row["addAttrEnum"]
            if (effect.uses == 0 or effect.trigger not in triggers or row["triggerCondition2"] not in phases
                    or attr in CONTROL or attr in IMMUNITIES or _resistance(row)):
                continue
            if target_only is not None and target_only != (camp == 0):
                continue
            if 1 in phases and (kind in (3, 4)) != compared:
                continue
            if camp == 3:
                recipients = [owner]
            elif camp == 0:
                recipients = targets
            else:
                recipients = [p for p in self.units if (p <= 6) == (owner <= 6)]
            recipients = [p for p in recipients if self.units[p]["HP"] > 0]
            if not recipients:
                continue
            if kind in (3, 4, 9):
                if opposite is None and kind in (3, 4):
                    continue
                test = self.units[opposite if kind == 3 else owner]
                threshold = (self.units[opposite]["HP"] if kind == 4
                             else math.ceil(test["OpeningHP"] * row["refValue"] / 10000))
                if not REF_COMPARE[row["refCondition"]](test["HP"], threshold):
                    continue
            if kind == 6 or attr == 0:
                child = self.buffs[str(row["addValue"])]
                for target in recipients:
                    resistance = next((e.row["refValue"] for e in reversed(self.active[target])
                                       if _resistance(e.row)), 0)
                    odds = row["triggerOdds"] - (resistance if child["addAttrEnum"] in (STUN, SILENCE, PARALYSIS) else 0)
                    if odds >= 10000 or self.rng.randrange(10000) < odds:
                        self._apply_child(child, target, attacker)
            elif row["triggerOdds"] >= 10000 or self.rng.randrange(10000) < row["triggerOdds"]:
                for target in recipients:
                    if attr == 205:
                        self.rage(target, math.floor(row["addValue"] / 100 + 0.5), from_buff=True)
                        continue
                    stat = STATS[attr]
                    value = (self.units[target].get(stat, 0) * row["addValue"] / 10000
                             if row["addType"] == 2 else row["addValue"] / 100)
                    if attr in PERCENT_RATES:
                        value *= 10000
                    elif attr in range(301, 309):
                        value = math.floor(value + 0.5) * 100
                    else:
                        value = math.floor(value + 0.5)
                    modifiers[target][stat] += value
            else:
                continue
            if effect.uses > 0:
                effect.uses -= 1
