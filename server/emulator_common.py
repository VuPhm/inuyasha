"""Shared helpers and constants extracted from emulator.py for Mixin reuse."""

from __future__ import annotations

from typing import Any
import uuid


EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"


DEFAULT_PLAYER_STATS: dict[str, int] = {
    "total_recruits": 0,
    "dream_recruits": 0,
    "destiny_recruits": 0,
    "soul_recruits": 0,
    "explore_count": 0,
    "pvp_fights": 0,
    "pvp_wins": 0,
    "boss_fights": 0,
    "mystery_refresh": 0,
    "treasure_loot_wins": 0,
    "equip_lvup_count": 0,
    "equip_compose_count": 0,
    "callequip_count": 0,
    "vit_pills_used": 0,
    "sta_pills_used": 0,
    "daydayfund_count": 0,
    "lighten_star_count": 0,
    "zcsf_count": 0,
    "xhzw_turn_count": 0,
    "treasure_lvup_count": 0,
    "treasure_step_up_count": 0,
    "rebirth_count": 0,
    "ggzj_count": 0,
    "ggzj_wins": 0,
    "gddh_fights": 0,
    "gddh_wins": 0,
    "friend_sta_sent": 0,
    "guild_build_count": 0,
    "guild_share_count": 0,
    "guild_boss_fights": 0,
    "recharged_diamonds": 0,
    "spent_diamonds": 0,
}


def _det_uuid(seed: str) -> str:
    """Return a deterministic 36-char GUID passing client IdIsValid() checks."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"inuyasha.revival.{seed}"))


def _zero_slot_property() -> dict[str, Any]:
    return {
        "HP": 0,
        "AP": 0,
        "DEF": 0,
        "SPD": 0,
        "FSP": 0,
        "FAP": 0,
        "AP1": 0,
        "APR1": 10000,
        "AP2": 0,
        "APR2": 0,
        "APAdd": 0,
        "APHero": 0,
        "APHeroR": 0,
        "DEF1": 0,
        "DEFR1": 10000,
        "DEF2": 0,
        "DEFR2": 0,
        "DEFAdd": 0,
        "DEFHero": 0,
        "DEFHeroR": 0,
        "HP1": 0,
        "HPR1": 10000,
        "HP2": 0,
        "HPR2": 0,
        "HPAdd": 0,
        "HPHero": 0,
        "HPHeroR": 0,
        "APToHPHeroR": 0,
        "RP": 0,
        "HIT": 10000,
        "DOD": 0,
        "CRI": 0,
        "TEN": 0,
        "BLO": 0,
        "BOG": 0,
        "CRId": 0,
        "TEND": 0,
        "RADAMADDR": 0,
        "RADAMCUTR": 0,
        "RBDAMADDR": 0,
        "RBDAMCUTR": 0,
        "RCDAMADDR": 0,
        "RCDAMCUTR": 0,
    }


def _parse_resource_str(res_str: str) -> list[tuple[int, int, int]]:
    """Parse 'type,modelId,num||...' strings from Config tables."""
    out: list[tuple[int, int, int]] = []
    for part in (res_str or "").split("||"):
        part = part.strip()
        if not part:
            continue
        segs = [s.strip() for s in part.split(",")]
        if len(segs) >= 3:
            out.append((int(segs[0]), int(segs[1]), int(segs[2])))
    return out
