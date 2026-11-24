#!/usr/bin/env python3
"""
InuYasha: Seek Jade Local Server Emulator (VN-First Revival, Round R3).

Primary Client: com.cmn.inuyasha v5.0.4.98 (VN), with EN 5.1.1 asset fallback.

Features:
  - Separates NORMAL_PROFILE (ServerId=1, Lv1/VIP0 onboarding progression)
    from DEBUG_PROFILE (ServerId=2, R1 quick-test save).
  - Config-driven VN data (204 heroes, maxPlayerLV=80, 689 stages, 1001 Attrtree nodes).
  - Multi-wave Battle.GetFightInfo & star-difficulty scaling (1★ Easy 1.0x,
    2★ Normal commonNPCAttrR%, 3★ Hard hardNPCAttrR%).
  - Highest-star persistence on replay, Battle.ConFight sweeps, chapter star sums,
    Battle.DrawBox / Battle.OneKeyDrawBoxs / Battle.DrawRoadBox.
  - Onboarding & progression RPCs up to >= Lv 10: Hero.HeroLvUp, Hero.HeroStepUp,
    Explore (Seek Jade), LightenStar (Ngộ Đạo / Insight Pursuit), Formation, Equips.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import hmac
import http.server
import json
import logging
import math
import mimetypes
import os
import random
import re
import secrets
import signal
import socketserver
import sys
import threading
import time
import urllib.parse
import uuid
import zipfile
import zlib
from pathlib import Path
from typing import Any, Callable

from bdd_handlers import BddHandlersMixin
from combat_effects import MAX_RAGE, supports_talent_buff
from combat_sim import simulate_fight_info
from economy_audit import ResourceLedger
from event_handlers import EventHandlersMixin
from event_runtime import EventClock, EventRuntime, build_default_event_registry
from gddh_handlers import GddhHandlersMixin
from ggzj_handlers import GgzjHandlersMixin
from guild_handlers import GuildHandlersMixin
from nightmare_handlers import (
    _CAMPAIGN_FAP_ANCHORS,
    NightmareHandlersMixin,
    interpolate_log_curve,
    scale_wave_to_target_fap,
)
from reborn_handlers import RebornHandlersMixin, _default_reborn_step_info
from social_handlers import SocialHandlersMixin
from teambattle_handlers import TeambattleHandlersMixin

SERVER_DIR = Path(__file__).resolve().parent
_default_root = SERVER_DIR.parent
ROOT_DIR = Path(os.environ.get("INUYASHA_ROOT_DIR", str(_default_root))).resolve()


def _load_release_meta() -> dict[str, Any]:
    """Read RELEASE.json beside SERVER_DIR/parent if running from an isolated release bundle."""
    for candidate in (SERVER_DIR.parent / "RELEASE.json", SERVER_DIR / "RELEASE.json"):
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return {
                    "release_tag": data.get("tag"),
                    "commit": data.get("commit"),
                    "source": "isolated_release",
                    "release_dir": str(candidate.parent),
                }
            except Exception:
                pass
    return {
        "release_tag": "working-tree",
        "commit": None,
        "source": "working_tree",
        "release_dir": str(ROOT_DIR),
    }


RELEASE_META = _load_release_meta()


def _det_uuid(seed: str) -> str:
    """Return a deterministic 36-char GUID passing client IdIsValid() checks."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"inuyasha.revival.{seed}"))
POC_DIR = ROOT_DIR / "poc" / "web_poc"
GAME_DATA_PATH = SERVER_DIR / "game_data.json"
LEGACY_SAVE_STATE_PATH = SERVER_DIR / "save_state.json"
SAVES_DIR = SERVER_DIR / "saves"
DEV_SAVES_DIR = SERVER_DIR / "dev_saves"
NORMAL_STATE_PATH = SAVES_DIR / "normal_profile.json"
DEBUG_STATE_PATH = SAVES_DIR / "debug_profile.json"
AUDIT_LOG_PATH = SAVES_DIR / "audit_ledger.jsonl"
RPC_TRACE_PATH = SERVER_DIR / "rpc_trace.log"
DEV_RPC_TRACE_PATH = SERVER_DIR / "dev_rpc_trace.log"

ENV_PRESETS: dict[str, dict[str, Any]] = {
    "stable": {
        "port": 8080,
        "data_dir": SAVES_DIR,
        "trace_path": RPC_TRACE_PATH,
    },
    "dev": {
        "port": 8082,
        "data_dir": DEV_SAVES_DIR,
        "trace_path": DEV_RPC_TRACE_PATH,
    },
}

SOUL_BOX_GOODS_ID = 16030003  # Quà Đá Hồn 3 (+3000 HeroEXP / hộp)
SOUL_BOX_SHOP_MAX_NUM = 200

# Exact VN client Config/LvPlanRewardModel.lua & LvPlanConfig.lua
LV_PLAN_NEED_VIP = 2
LV_PLAN_NEED_DIAMOND = 100
LV_PLAN_REWARDS: dict[int, int] = {
    10: 200,
    15: 300,
    20: 350,
    25: 400,
    30: 450,
    35: 500,
    40: 550,
    45: 600,
    50: 650,
    55: 888,
}

# Exact VN client Config/VipWelfareModel.lua (LV 0..20)
VIP_WELFARE_REWARDS: dict[int, str] = {
    0: "1112,0,10000||1605,16050011,5",
    1: "1112,0,30000||1605,16050011,10||1605,16050013,1",
    2: "1112,0,50000||1605,16050011,15||1605,16050013,1||1117,0,1000",
    3: "1112,0,80000||1605,16050011,20||1605,16050013,1||1117,0,1500||1605,16050012,1",
    4: "1112,0,100000||1605,16050011,25||1605,16050013,1||1117,0,2000||1605,16050012,1||1605,16050010,1",
    5: "1112,0,110000||1605,16050011,25||1605,16050013,1||1117,0,2200||1605,16050012,1||1605,16050010,1",
    6: "1112,0,120000||1605,16050011,30||1605,16050013,2||1117,0,2500||1605,16050012,1||1605,16050010,1",
    7: "1112,0,140000||1605,16050011,30||1605,16050013,2||1117,0,2800||1605,16050012,1||1605,16050010,1",
    8: "1112,0,150000||1605,16050011,35||1605,16050013,2||1117,0,3000||1605,16050012,2||1605,16050010,2",
    9: "1112,0,160000||1605,16050011,35||1605,16050013,2||1117,0,3000||1605,16050012,2||1605,16050010,2",
    10: "1112,0,180000||1605,16050011,40||1605,16050013,2||1117,0,3500||1605,16050012,2||1605,16050010,3",
    11: "1112,0,230000||1605,16050011,45||1605,16050013,2||1117,0,4000||1605,16050012,3||1605,16050010,4",
    12: "1112,0,260000||1605,16050011,50||1605,16050013,2||1117,0,4000||1605,16050012,3||1605,16050010,5",
    13: "1112,0,300000||1605,16050011,55||1605,16050013,2||1117,0,5000||1605,16050012,3||1605,16050010,6",
    14: "1112,0,320000||1605,16050011,55||1605,16050013,2||1117,0,5500||1605,16050012,3||1605,16050010,7",
    15: "1112,0,350000||1605,16050011,60||1605,16050013,3||1117,0,6000||1605,16050012,3||1605,16050010,8",
    16: "1112,0,360000||1605,16050011,60||1605,16050013,3||1117,0,6000||1605,16050012,3||1605,16050010,9",
    17: "1112,0,380000||1605,16050011,60||1605,16050013,3||1117,0,6000||1605,16050012,3||1605,16050010,10",
    18: "1112,0,400000||1605,16050011,65||1605,16050013,3||1117,0,7000||1605,16050012,4||1605,16050010,10",
    19: "1112,0,450000||1605,16050011,70||1605,16050013,3||1117,0,8000||1605,16050012,4||1605,16050010,10",
    20: "1112,0,500000||1605,16050011,75||1605,16050013,3||1117,0,9000||1605,16050012,5||1605,16050010,10",
}

# Exact VN client Config/ChargeConfig.lua & simulated store tiers
CHARGE_BOX_REWARDS: dict[int, str] = {
    60: "1606,16060026,1||1602,16020021,1||1605,16050010,10||1603,16030006,1||1603,16030008,1||1605,16050001,200||1112,0,200000",
    300: "1302,13020413,1||1303,13030413,1||1605,16050010,20||1603,16030006,2||1603,16030008,3||1605,16050001,500||1112,0,300000",
    900: "1606,16060019,1||1605,16050010,30||1603,16030008,10||1605,16050001,1000||1112,0,500000",
}
CHARGE_TIERS: list[dict[str, Any]] = [
    {"ProductId": "com.cmn.inuyasha.gem1000000", "ChargePoint": 1000000, "GamePoint": 1000000, "GiveGamePoint": 0, "Ratio": 1, "Instant": True},
    {"ProductId": "com.cmn.inuyasha.gem60", "ChargePoint": 60, "GamePoint": 60, "GiveGamePoint": 60, "Ratio": 2},
    {"ProductId": "com.cmn.inuyasha.gem180", "ChargePoint": 180, "GamePoint": 180, "GiveGamePoint": 180, "Ratio": 2},
    {"ProductId": "com.cmn.inuyasha.gem300", "ChargePoint": 300, "GamePoint": 300, "GiveGamePoint": 300, "Ratio": 2},
    {"ProductId": "com.cmn.inuyasha.gem680", "ChargePoint": 680, "GamePoint": 680, "GiveGamePoint": 680, "Ratio": 2},
    {"ProductId": "com.cmn.inuyasha.gem900", "ChargePoint": 900, "GamePoint": 900, "GiveGamePoint": 900, "Ratio": 2},
    {"ProductId": "com.cmn.inuyasha.gem1980", "ChargePoint": 1980, "GamePoint": 1980, "GiveGamePoint": 1980, "Ratio": 2},
    {"ProductId": "com.cmn.inuyasha.gem3280", "ChargePoint": 3280, "GamePoint": 3280, "GiveGamePoint": 3280, "Ratio": 2},
    {"ProductId": "com.cmn.inuyasha.gem6480", "ChargePoint": 6480, "GamePoint": 6480, "GiveGamePoint": 6480, "Ratio": 2},
]
CARD_MODEL_CFG: dict[int, dict[str, Any]] = {
    1: {
        "ID": 1,
        "ProductId": "com.cmn.inuyasha.card1",
        "price": 300,
        "continueTime": 30,
        "dailyReward": "1111,0,100",
        "buyReward": "1111,0,268",
    }
}

# Quality-tiered recruit weights per banner (q=6 Green, q=10 Blue, q=13 Purple, q=15 Orange).
# NOTE: Official VN/EN/TH/ZH HeroRecruitModel.lua configs define pools/costs/CDs/extraRewards
# without drop-rate tables; these tier weights are server-modeled & configurable, never flat
# uniform random across all heroes, and UR (q=18) heroes are excluded from normal recruit pools.
RECRUIT_RATE_CONFIG: dict[int, dict[int, int]] = {
    1: {6: 5000, 10: 4200, 13: 800},
    2: {6: 2500, 10: 5500, 13: 2000},
    3: {10: 4500, 13: 4500, 15: 1000},
}

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

EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"

VN_APK_PATH = ROOT_DIR / "analysis" / "vn" / "extracted" / "com.cmn.inuyasha.apk"
VN_OBB_PATH = (
    ROOT_DIR
    / "analysis"
    / "vn"
    / "extracted"
    / "Android"
    / "obb"
    / "com.cmn.inuyasha"
    / "main.98.com.cmn.inuyasha.obb"
)
EN_APK_PATH = ROOT_DIR / "analysis" / "extracted" / "com.heitao.inuyasha.guge_5.1.1" / "com.heitao.inuyasha.guge.apk"
EN_OBB_PATH = (
    ROOT_DIR
    / "analysis"
    / "extracted"
    / "com.heitao.inuyasha.guge_5.1.1"
    / "Android"
    / "obb"
    / "com.heitao.inuyasha.guge"
    / "main.511.com.heitao.inuyasha.guge.obb"
)


class AssetArchive:
    """Lazy read-only lookup across VN (primary) and EN (fallback) APKs and OBBs."""

    def __init__(self, sources: list[tuple[Path, Path]] | Path, obb_path: Path | None = None) -> None:
        if isinstance(sources, Path):
            pairs = [(sources, obb_path)] if obb_path else [(sources, Path())]
        else:
            pairs = sources
        self._layers: list[tuple[zipfile.ZipFile, set[str]]] = []
        for apk_p, obb_p in pairs:
            for p in (obb_p, apk_p):
                if p and str(p) and p.exists():
                    zf = zipfile.ZipFile(p, "r")
                    self._layers.append((zf, set(zf.namelist())))

    def read(self, rel_path: str) -> bytes | None:
        clean = rel_path.lstrip("/")
        for zf, names in self._layers:
            if clean in names:
                return zf.read(clean)
            apk_key = f"assets/{clean}"
            if apk_key in names:
                return zf.read(apk_key)
        return None


def parse_atlas(raw_text: str) -> dict[str, Any]:
    """Parse a Spine/LibGDX .atlas text file into page size and frame regions."""
    lines = [ln.rstrip("\r\n") for ln in raw_text.splitlines()]
    page_name = ""
    page_size = [0, 0]
    regions: dict[str, dict[str, Any]] = {}
    current: str | None = None

    for line in lines:
        if not line.strip():
            continue
        if not line.startswith(" "):
            if not page_name and (line.endswith(".png") or line.endswith(".jpg")):
                page_name = line.strip()
            elif ":" not in line:
                current = line.strip()
                regions[current] = {}
        elif current and ":" in line:
            k, v = line.strip().split(":", 1)
            v = v.strip()
            if k in ("xy", "size", "orig", "offset"):
                regions[current][k] = [int(x.strip()) for x in v.split(",")]
            elif k == "rotate":
                regions[current][k] = v.lower() == "true"
            elif k == "index":
                regions[current][k] = int(v)
        elif not current and line.strip().startswith("size:"):
            page_size = [int(x.strip()) for x in line.split(":", 1)[1].split(",")]

    return {"page": page_name, "size": page_size, "regions": regions}


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


class ProfileStore(
    EventHandlersMixin,
    BddHandlersMixin,
    TeambattleHandlersMixin,
    NightmareHandlersMixin,
    RebornHandlersMixin,
    GgzjHandlersMixin,
    GddhHandlersMixin,
    SocialHandlersMixin,
    GuildHandlersMixin,
):
    """Single-profile game state & RPC engine backed by extracted VN/EN config."""

    DEBUG_STARTER_HERO_IDS = ["12011004", "12011005", "12012005", "12011006"]
    EQUIP_TYPE_TO_SLOT_KEY = {
        1301: "Weapon",
        1302: "Helmet",
        1303: "Clothes",
        1304: "Necklace",
    }

    def __init__(
        self,
        profile_name: str,
        game_data: dict[str, Any],
        ledger: ResourceLedger,
        state_path: Path | None = None,
        persist: bool = True,
        reset: bool = False,
        legacy_seed_path: Path | None = None,
        trace_path: Path | None = RPC_TRACE_PATH,
        clock: EventClock | None = None,
        default_player_id: str | None = None,
        default_arena_rank: int = 1500,
        peer_profiles_fn: Any = None,
        account_manager: Any = None,
    ) -> None:
        self.profile_name = profile_name  # "normal", "s1_acct_N", or "debug"
        self.game_data = game_data
        self.ledger = ledger
        self.state_path = state_path
        self.persist = persist
        self.legacy_seed_path = legacy_seed_path
        self.trace_path = trace_path
        self.clock = clock if clock is not None else EventClock()
        self.default_player_id = default_player_id
        self.default_arena_rank = int(default_arena_rank)
        self.peer_profiles_fn = peer_profiles_fn
        self.account_manager = account_manager
        self._lock = threading.RLock()
        self.state = self._load_or_init(reset=reset)
        self.event_runtime = EventRuntime(
            self.clock,
            build_default_event_registry(self.game_data),
            self.state,
        )
        self._recalc_all_slots_and_fap()
        if self.persist and self.state_path:
            self._write_json_atomic(self.state_path, self.state)

    @property
    def is_debug_profile(self) -> bool:
        return self.profile_name == "debug"

    @property
    def is_normal_gameplay(self) -> bool:
        return self.profile_name != "debug"

    def now_ts(self) -> int:
        return self.clock.now()

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, path)

    def _load_or_init(self, reset: bool = False) -> dict[str, Any]:
        prev_player_id: str | None = None
        if self.persist and self.state_path and self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            prev_player_id = str(data.get("player", {}).get("PlayerId", "")) or None
            if not reset:
                return self._normalize_loaded_state(data)
        if self.profile_name == "debug" and not reset and self.legacy_seed_path and self.legacy_seed_path.exists():
            data = json.loads(self.legacy_seed_path.read_text(encoding="utf-8"))
            data = self._normalize_loaded_state(data)
            if self.persist and self.state_path:
                self._write_json_atomic(self.state_path, data)
            return data
        if self.profile_name == "debug":
            state = self._create_debug_default_state()
        else:
            next_pid = self.default_player_id or "200001"
            if reset and prev_player_id and prev_player_id.isdigit():
                next_pid = str(max(200001, int(prev_player_id) + 1))
            state = self._create_normal_default_state(player_id=next_pid)
            pvp_st = state.setdefault("pvp", {})
            pvp_st["rank"] = int(self.default_arena_rank)
            pvp_st["history_max_rank"] = int(self.default_arena_rank)
        if self.persist and self.state_path:
            self._write_json_atomic(self.state_path, state)
        return state

    def _default_explore_state(self) -> dict[str, Any]:
        ec = self.game_data.get("explore_config", {})
        return {
            "RemainNum": int(ec.get("fightNumStart", 15)),
            "MaxNum": int(ec.get("fightNumMax", 25)),
            "DailyNum": 0,
            "ResetNum": 0,
            "MaxResetNum": 5,
            "DrawnNums": "",
            "RecoverTime": self.now_ts() + int(ec.get("restoreFightNumDaily", 900)),
            "Day": self.clock.today_str(),
        }

    def _normalize_loaded_state(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure loaded states have required fields without altering saved progress."""
        data.setdefault("equips", [])
        data.setdefault("gems", [])
        data.setdefault("treasures", [])
        data.setdefault("treasure_debris", [])
        data.setdefault("treasure_protect_end", 0)
        el_cfg = self.game_data.get("elite_config", {})
        data.setdefault(
            "elite",
            {
                "fight_count": int(el_cfg.get("maxFightNum", 3)),
                "buy_count": 0,
                "consume_buy_count": 0,
                "nodes": {},
            },
        )
        data.setdefault("goods", [])
        data.setdefault("claimed_step_rewards", [])
        data.setdefault("recruit_state", {"MidAlreadyUseResource": False, "HigAlreadyUseResource": False, "OutZiCount": 5})
        data.setdefault("explore", self._default_explore_state())
        data.setdefault("shop_bought", {})
        data.setdefault("shop_bought_date", self.clock.today_str())
        data.setdefault("shop_daily_reset_count", 0)
        data.setdefault("lv_plan", {"open": False, "rewarded": []})
        data.setdefault("vip_welfare_drawn_date", "")
        data.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}})
        data.setdefault("month_cards", {})
        lb_cfg = self.game_data.get("luckboss_config", {})
        rec_cd = int(lb_cfg.get("attackNumRecoverTime", 1800))
        now = int(time.time())
        boss_state = data.setdefault(
            "boss_battle",
            {
                "attack_num": 10,
                "recover_time": now + rec_cd,
                "buy_count": 0,
                "jifen": 0,
                "drawn_boxes": [],
                "clear_counter": 0,
                "next_boss_count": 10,
                "next_boss_model_id": 12010055,
                "bosses": [],
            },
        )
        boss_state.setdefault("attack_num", 10)
        boss_state.setdefault("recover_time", now + rec_cd)
        boss_state.setdefault("buy_count", 0)
        boss_state.setdefault("jifen", 0)
        boss_state.setdefault("drawn_boxes", [])
        boss_state.setdefault("clear_counter", 0)
        boss_state.setdefault("next_boss_count", 10)
        boss_state.setdefault("next_boss_model_id", 12010055)
        boss_state.setdefault("bosses", [])
        pvp_state = data.setdefault(
            "pvp",
            {
                "rank": 1500,
                "history_max_rank": 1500,
                "history_max_step": 1,
                "refresh_date": 0,
                "shop_bought_daily": {},
                "shop_bought_total": {},
                "history": [],
                "refresh_seed": 1,
            },
        )
        pvp_state.setdefault("rank", 1500)
        pvp_state.setdefault("history_max_rank", int(pvp_state["rank"]))
        pvp_state.setdefault("history_max_step", 1)
        pvp_state.setdefault("refresh_date", 0)
        pvp_state.setdefault("shop_bought_daily", {})
        pvp_state.setdefault("shop_bought_total", {})
        pvp_state.setdefault("history", [])
        pvp_state.setdefault("refresh_seed", 1)
        data.setdefault("daydayfund", {"if_draw": True, "cooled_time": 0, "last_multiple": 0, "harvest_list": []})
        data.setdefault("startwork", {"claimed_days": []})
        data.setdefault("fashions", [])
        data.setdefault(
            "glory",
            {
                "1": {"TypeId": 1, "Lv": 0, "EXP": 0},
                "2": {"TypeId": 2, "Lv": 0, "EXP": 0},
                "3": {"TypeId": 3, "Lv": 0, "EXP": 0},
            },
        )
        data.setdefault("gift_lv", {"claimed": []})
        today_str = time.strftime("%Y-%m-%d")
        gl_state = data.setdefault(
            "gift_login",
            {"login_days": 1, "last_login_date": today_str, "claimed": []},
        )
        gl_state.setdefault("login_days", 1)
        gl_state.setdefault("last_login_date", today_str)
        gl_state.setdefault("claimed", [])
        data.setdefault(
            "mystery_shop",
            {"normal": None, "senior": None, "free_date": "", "free_count": 2, "gold_count": 0},
        )
        rs = data.setdefault("recruit_state", {})
        rs.setdefault("MidAlreadyUseResource", False)
        rs.setdefault("HigAlreadyUseResource", False)
        rs.setdefault("OutZiCount", 9)
        rs.setdefault("history", [])
        cs = data.setdefault("charge_state", {})
        cs.setdefault("first_bought", [])
        cs.setdefault("drawn_boxes", [])
        cs.setdefault("orders", {})
        cs.setdefault("card_orders", {})
        data.setdefault("vip_gift_bought", [])
        st = data.setdefault("success_target", {})
        st.setdefault("start_ts", int(time.time()))
        st.setdefault("drawn", {})
        st.setdefault("drawn_days", [])
        st.setdefault("if_draw", 0)
        st.setdefault("exchange_counts", {})
        stats = data.setdefault("stats", {})
        for sk, sv in DEFAULT_PLAYER_STATS.items():
            stats.setdefault(sk, sv)
        self._sanitize_legacy_debris_and_boss_drops(data, boss_state)
        p = data.setdefault("player", {})
        p.setdefault("ChargeNum", 0)
        p.setdefault("VipEXP", 0)
        p.setdefault("PVPCoin", 0)
        p.setdefault("GDDHCoin", 0)
        p.setdefault("BossCoin", int(boss_state.get("jifen", 0)))
        p.setdefault("RebornCoin", 0)
        p.setdefault("Contribution", 0)
        p.setdefault("FashionModelId", 0)
        p.setdefault("GuildId", EMPTY_ENTITY_ID)
        p.setdefault("GuildName", "")
        p.setdefault("PVPInterLv", 0)
        p.setdefault("ActivityPic", "")
        p.setdefault("ActivityName", "")
        data.setdefault("rewards_center", [])
        data.setdefault("xxbz_lifetime", {})
        data.setdefault("reborn_goods", [])
        data.setdefault("reborn_shop", {})
        data.setdefault("equip_artifacts", {})
        data.setdefault("ggzj", {})
        data.setdefault("gddh", {})
        self._ensure_social_container(data)
        self._ensure_player_guild_container(data)
        if not isinstance(data.get("callequip"), dict):
            data["callequip"] = {}
        if not isinstance(data.get("nightmare"), dict):
            data["nightmare"] = self._default_nightmare_state()
        lb_st = data.setdefault("leaderboard", {"praised_date": "", "praised_types": [], "praise_counts": {}, "received_praises": {}})
        lb_st.setdefault("praised_date", "")
        lb_st.setdefault("praised_types", [])
        lb_st.setdefault("praise_counts", {})
        lb_st.setdefault("received_praises", {})
        # Migrate pre-R7.6 single-rotation default saves to R7.6 concurrent multi-banner once
        raw_ac = data.get("event_runtime", {}).get("archive_config", {})
        if isinstance(raw_ac, dict) and not raw_ac.get("r76_migrated"):
            if raw_ac.get("mode") == "rotating":
                raw_ac["mode"] = "concurrent"
            raw_ac["r76_migrated"] = True
        EventRuntime.ensure_state(data)
        self._sync_player_recover_times(p)
        for h in data.get("heroes", []):
            h.setdefault("WarfareColorLv", 0)
            h.setdefault("WarfareLv", 0)
            h.setdefault("LiantiLv", 0)
            h.setdefault("RebornStep", 0)
            h.setdefault("Lv", 1)
            h.setdefault("Step", 0)
            self._ensure_hero_reborn_fields(h)
        data.setdefault("mates", {})
        for eq in data.get("equips", []):
            eq.setdefault("Step", 0)
            eq.setdefault("Lv", 0)
        for tr in data.get("treasures", []):
            tr.setdefault("Step", 0)
            tr.setdefault("Lv", 0)
            tr.setdefault("Exp", 0)
        gems_by_id = {g["Id"]: g for g in data.get("gems", []) if isinstance(g, dict) and g.get("Id")}
        seen_socketed_gems: set[str] = set()
        for slot in data.get("slots", []):
            for skey in ("Weapon", "Helmet", "Clothes", "Necklace"):
                s_eq = slot.get(skey)
                if isinstance(s_eq, dict) and s_eq.get("Id"):
                    s_eq.setdefault("Step", 0)
            self._normalize_slot_gems(slot, gems_by_id=gems_by_id, seen_ids=seen_socketed_gems)
        for ch_st in data.get("chapters", {}).values():
            for suffix in ("A", "B", "C"):
                val = ch_st.get(f"IfDrawBox{suffix}", False)
                ch_st[f"IfDrawBox{suffix}"] = bool(val) if not isinstance(val, str) else val.lower() == "true"
        # Convert legacy list embattle to Formation1..6 dict for SlotFormation.GetFormation
        emb = data.get("embattle")
        if isinstance(emb, list):
            emb_dict = {f"Formation{i}": 0 for i in range(1, 7)}
            for entry in emb:
                f_idx = int(entry.get("FormationIdx", 0))
                s_id = int(entry.get("SlotId", 0))
                if 1 <= f_idx <= 6:
                    emb_dict[f"Formation{f_idx}"] = s_id
            data["embattle"] = emb_dict
        # For debug profile only, ensure cleared nodes with StarCount>0 have Flag=2 so nodeIsPassed works
        if self.profile_name == "debug":
            for n in data.get("nodes", {}).values():
                if n.get("StarCount", 0) > 0 and n.get("Flag", 0) == 0:
                    n["Flag"] = 2
        self._sync_main_hero_model(data)
        return data

    BOSS_DROP_POOL: tuple[dict[str, int], ...] = (
        {"TypeId": 1602, "ModelId": 16020020, "Num": 1},
        {"TypeId": 1602, "ModelId": 16020021, "Num": 1},
        {"TypeId": 1503, "ModelId": 15032101, "Num": 1},
        {"TypeId": 1504, "ModelId": 15040101, "Num": 1},
    )
    LEGACY_RESOURCE_REMAPPING: dict[tuple[int, int], tuple[int, int]] = {
        (1503, 15030101): (1503, 15032101),
    }
    _ATTR_RESOURCE_TYPES: frozenset[int] = frozenset({1101, 1102, 1103, 1111, 1112, 1113, 1115, 1116, 1117, 1119, 1120, 1124, 1128, 2112})

    def _is_valid_resource(self, rtype: int, rmodel: int) -> bool:
        """Check whether (TypeId, ModelId) exists in game_data and can be rendered by client."""
        if rtype in self._ATTR_RESOURCE_TYPES:
            return True
        mkey = str(rmodel)
        if rtype == 1201:
            return mkey in self.game_data.get("heroes", {})
        if rtype in (1301, 1302, 1303, 1304):
            eq = self.game_data.get("equips", {}).get(mkey)
            return bool(eq and int(eq.get("typeID", rtype)) == rtype)
        if rtype in (1401, 1402):
            tr = self.game_data.get("treasures", {}).get(mkey)
            return bool(tr and int(tr.get("typeID", rtype)) == rtype)
        if rtype in (1503, 1504):
            td = self.game_data.get("treasure_debris", {}).get(mkey)
            if not td or int(td.get("typeID", 0)) != rtype:
                return False
            return str(td.get("treasureModelID", 0)) in self.game_data.get("treasures", {})
        if rtype == 1901:
            return mkey in self.game_data.get("fashion_model", {})
        if rtype == 2000:
            return mkey in self.game_data.get("gem_model", {})
        if rtype == 2701:
            return mkey in self.game_data.get("reborn_goods", {})
        gm = self.game_data.get("goods_model", {}).get(mkey) or self.game_data.get("goods_djq_model", {}).get(mkey)
        return bool(gm and int(gm.get("typeID", rtype)) == rtype)

    def _validate_resource_tuples(
        self, res_tuples: list[tuple[int, int, int]], source: str = ""
    ) -> list[tuple[int, int, int]]:
        """Validate every positive-count resource tuple before state mutation or RPC emission."""
        for rtype, rmodel, rnum in res_tuples:
            if int(rnum) <= 0:
                continue
            if not self._is_valid_resource(int(rtype), int(rmodel)):
                raise ValueError(f"Invalid resource tuple ({rtype}, {rmodel}, {rnum}) in {source or 'rpc'}")
        return res_tuples

    def validate_base_resource_list(self, base_res: list[dict[str, Any]], context: str = "rpc") -> None:
        """Verify every item in a BaseGetGameResourceList payload maps to a valid client resource."""
        for bundle in base_res or []:
            if not isinstance(bundle, dict):
                continue
            for item in bundle.get("Hero", []):
                mid = int(item.get("HeroModelId", 0))
                if not self._is_valid_resource(1201, mid):
                    raise ValueError(f"Invalid Hero resource ModelId={mid} in {context}")
            for item in bundle.get("Equip", []):
                mid = int(item.get("EquipModelId", 0))
                eq = self.game_data.get("equips", {}).get(str(mid))
                if not eq or not self._is_valid_resource(int(eq.get("typeID", 0)), mid):
                    raise ValueError(f"Invalid Equip resource ModelId={mid} in {context}")
            for item in bundle.get("Treasure", []):
                mid = int(item.get("TreasureModelId", 0))
                tr = self.game_data.get("treasures", {}).get(str(mid))
                if not tr or not self._is_valid_resource(int(tr.get("typeID", 0)), mid):
                    raise ValueError(f"Invalid Treasure resource ModelId={mid} in {context}")
            for item in bundle.get("TreasureDebris", []):
                rtype = int(item.get("ResourceTypeSub", 0))
                mid = int(item.get("TreasureDebrisModelId", 0))
                if not self._is_valid_resource(rtype, mid):
                    raise ValueError(f"Invalid TreasureDebris resource TypeId={rtype}, ModelId={mid} in {context}")
            for item in bundle.get("Goods", []):
                rtype = int(item.get("ResourceTypeSub", 0))
                mid = int(item.get("GoodsModelId", 0))
                if not self._is_valid_resource(rtype, mid):
                    raise ValueError(f"Invalid Goods resource TypeId={rtype}, ModelId={mid} in {context}")
            for item in bundle.get("Fashion", []):
                mid = int(item.get("FashionModelId", 0))
                if not self._is_valid_resource(1901, mid):
                    raise ValueError(f"Invalid Fashion resource ModelId={mid} in {context}")
            for item in bundle.get("Gem", []):
                mid = int(item.get("ModelId", 0))
                if not self._is_valid_resource(2000, mid):
                    raise ValueError(f"Invalid Gem resource ModelId={mid} in {context}")
            for item in bundle.get("RebornGoods", []):
                mid = int(item.get("ModelId", 0))
                if not self._is_valid_resource(2701, mid):
                    raise ValueError(f"Invalid RebornGoods resource ModelId={mid} in {context}")

    def _boss_drop_for_model(self, model_id: int) -> dict[str, int]:
        """Select a validated DropResource entry for a LuckBoss model ID."""
        tier_idx = max(0, int(model_id) - 12010050)
        drop_res = dict(self.BOSS_DROP_POOL[tier_idx % len(self.BOSS_DROP_POOL)])
        self._validate_resource_tuples(
            [(int(drop_res["TypeId"]), int(drop_res["ModelId"]), int(drop_res["Num"]))],
            source=f"boss_drop_pool:{model_id}",
        )
        return drop_res

    def _sanitize_boss_drop(self, boss: dict[str, Any]) -> dict[str, int]:
        """Normalize or repair an active boss's DropResource so invalid IDs never reach RPCs."""
        dr = boss.get("DropResource")
        if isinstance(dr, dict):
            rtype = int(dr.get("TypeId", 0))
            rmodel = int(dr.get("ModelId", 0))
            rnum = max(1, int(dr.get("Num", 1)))
            mapped = self.LEGACY_RESOURCE_REMAPPING.get((rtype, rmodel))
            if mapped:
                rtype, rmodel = mapped
            if self._is_valid_resource(rtype, rmodel):
                clean = {"TypeId": rtype, "ModelId": rmodel, "Num": rnum}
                boss["DropResource"] = clean
                return clean
        clean = self._boss_drop_for_model(int(boss.get("BossModelId", 12010050)))
        boss["DropResource"] = clean
        return clean

    def _sanitize_legacy_debris_and_boss_drops(self, data: dict[str, Any], boss_state: dict[str, Any]) -> None:
        """Migrate legacy invalid 15030101 book debris saves/drops to valid 15032101."""
        debris_raw = data.get("treasure_debris")
        if isinstance(debris_raw, list):
            merged_by_model: dict[int, dict[str, Any]] = {}
            ordered_models: list[int] = []
            for row in debris_raw:
                if not isinstance(row, dict):
                    continue
                mid = int(row.get("TreasureDebrisModelId", 0))
                remapped = self.LEGACY_RESOURCE_REMAPPING.get((1503, mid))
                if remapped:
                    mid = remapped[1]
                num = int(row.get("Num", 0))
                if mid not in merged_by_model:
                    entry = dict(row)
                    entry["TreasureDebrisModelId"] = mid
                    entry["Num"] = num
                    merged_by_model[mid] = entry
                    ordered_models.append(mid)
                else:
                    merged_by_model[mid]["Num"] = int(merged_by_model[mid].get("Num", 0)) + num
            data["treasure_debris"] = [merged_by_model[m] for m in ordered_models]

        for boss in boss_state.get("bosses", []):
            if isinstance(boss, dict):
                self._sanitize_boss_drop(boss)

    def _canonical_recover_limits(self) -> tuple[int, int, int, int]:
        """Return (vit_max, vit_cd, sta_max, sta_cd) from canonical client/server configs."""
        vit_cfg = self.game_data.get("vit_config", {})
        sta_cfg = self.game_data.get("sta_config", {})
        return (
            int(vit_cfg.get("maxNum", 200)),
            int(vit_cfg.get("recoverCD", 360)),
            int(sta_cfg.get("maxNum", 20)),
            int(sta_cfg.get("recoverCD", 900)),
        )

    def _sync_player_recover_times(self, player: dict[str, Any] | None = None) -> None:
        """Normalize VITMaxNum/STAMaxNum, VIP sync, and recover timestamps."""
        p = player if player is not None else self.state["player"]
        now = self.now_ts()
        vip_exp = int(p.get("VipEXP", 0))
        derived_vip = self.ledger.derive_vip_level(vip_exp) if vip_exp > 0 else 0
        vip_lv = max(int(p.get("Vip", 0)), int(p.get("VIPLv", 0)), derived_vip)
        p["Vip"] = vip_lv
        p["VIPLv"] = vip_lv
        cfg_vit_max, vit_cd, cfg_sta_max, sta_cd = self._canonical_recover_limits()

        raw_vit_max = p.get("VITMaxNum")
        vit_max = max(cfg_vit_max, int(raw_vit_max)) if isinstance(raw_vit_max, (int, float)) else cfg_vit_max
        p["VITMaxNum"] = vit_max

        raw_sta_max = p.get("STAMaxNum")
        extra_sta = self._glory_extra_sta() if hasattr(self, "state") else 0
        sta_max = max(cfg_sta_max + extra_sta, int(raw_sta_max)) if isinstance(raw_sta_max, (int, float)) else (cfg_sta_max + extra_sta)
        p["STAMaxNum"] = sta_max

        if int(p.get("VIT", 0)) < vit_max:
            cur = p.get("VITNextRecoverTime")
            if isinstance(cur, (int, float)) and int(cur) > now:
                p["VITNextRecoverTime"] = min(int(cur), now + vit_cd)
            else:
                p["VITNextRecoverTime"] = now + vit_cd
        else:
            p["VITNextRecoverTime"] = now

        if int(p.get("STA", 0)) < sta_max:
            cur = p.get("STANextRecoverTime")
            if isinstance(cur, (int, float)) and int(cur) > now:
                p["STANextRecoverTime"] = min(int(cur), now + sta_cd)
            else:
                p["STANextRecoverTime"] = now + sta_cd
        else:
            p["STANextRecoverTime"] = now

    def reset_state(self) -> dict[str, Any]:
        """Reset normal profile with a fresh PlayerId so Android LocalData guide cache starts clean."""
        with self._lock:
            prev_id = str(self.state.get("player", {}).get("PlayerId", "200001"))
            try:
                next_num = max(200001, int(prev_id) + 1)
            except ValueError:
                next_num = 200001
            self.state = self._create_normal_default_state(player_id=str(next_num))
            self.save()
            return self.state

    def save(self) -> None:
        with self._lock:
            if self.persist and self.state_path:
                self._write_json_atomic(self.state_path, self.state)

    def _build_hero_instance(
        self, hero_model_id: int, lv: int = 1, step: int = 0, inst_id: str | None = None
    ) -> dict[str, Any]:
        cfg = self.game_data["heroes"][str(hero_model_id)]
        step_attr = self._get_step_attr(cfg, step)
        hp = int(cfg["HPBase"] + cfg["HPUp"] * (lv - 1) + step_attr["HP"])
        ap = int(cfg["APBase"] + cfg["APUp"] * (lv - 1) + step_attr["AP"])
        defense = int(cfg["DEFBase"] + cfg["DEFUp"] * (lv - 1) + step_attr["DEF"])
        rc = self._hero_reborn_class_id(cfg)
        reborn_id = rc * 1000 if rc > 0 else 0
        return {
            "Id": inst_id or str(uuid.uuid4()),
            "HeroModelId": int(hero_model_id),
            "Lv": lv,
            "Step": step,
            "RebornId": reborn_id,
            "RebornStepInfo": _default_reborn_step_info(reborn_id),
            "RebornStep": 0,
            "LiantiLv": 0,
            "WarfareColorLv": 0,
            "WarfareLv": 0,
            "HP": hp,
            "AP": ap,
            "DEF": defense,
        }

    def _get_step_attr(self, hero_cfg: dict[str, Any], step: int) -> dict[str, int]:
        step_cls = int(hero_cfg.get("stepUpClassID", 0))
        rec = self.game_data.get("hero_step", {}).get(str(step_cls * 1000 + step))
        if not rec:
            return {"HP": 0, "AP": 0, "DEF": 0, "FSP": 0}
        mult = float(rec.get("attrUpR", 0))
        return {
            "HP": int(hero_cfg["HPBase"] * mult),
            "AP": int(hero_cfg["APBase"] * mult),
            "DEF": int(hero_cfg["DEFBase"] * mult),
            "FSP": int(rec.get("FSP", 0)),
        }

    def _hero_talent_rows(self, model: int, step: int) -> list[dict[str, Any]]:
        relations = self.game_data.get("hero_talents", {}).get(str(model), {})
        attained = dict.fromkeys(row["TALModelID"] for rank, row in relations.items() if int(rank) <= step)
        talents = self.game_data.get("talent_models", {})
        return [talents[str(talent)] for talent in attained if str(talent) in talents]

    @staticmethod
    def _add_talent_attributes(stats: Counter[int], talents: list[dict[str, Any]], scope: int) -> None:
        for row in talents:
            if row["attrEffectRange"] != scope or not row["attrStr"]:
                continue
            for pair in row["attrStr"].split(","):
                attr, amount = pair.split("|", 1)
                stats[int(attr)] += int(amount)

    def _fashion_collection_stats(self) -> Counter[int]:
        # FashionAttributeLayer sums one copy per owned model, preferring its upgraded copy.
        owned_steps: dict[str, int] = {}
        for item in self.state.get("fashions", []):
            model = str(item["FashionModelId"])
            if not owned_steps.get(model, 0):
                owned_steps[model] = int(item.get("Step", 0))
        result: Counter[int] = Counter()
        table = self.game_data.get("fashion_step", {})
        for model, step in owned_steps.items():
            row = table.get(model, {}).get(str(step), {})
            for target, attr, amount in _parse_resource_str(row.get("heroAttrStrR", "")):
                if target == 2:  # VN labels this scope "all allies".
                    result[attr] += amount
        return result

    def _fashion_pr_bonuses(self, slot_id: int) -> dict[str, int]:
        """Compute flat HP/AP/DEF bonuses from completed FashionPrRelation sets."""
        bonuses = {"HP": 0, "AP": 0, "DEF": 0}
        fashions = self.state.get("fashions", []) if isinstance(getattr(self, "state", None), dict) else []
        if not fashions:
            return bonuses
        owned_models = {int(item["FashionModelId"]) for item in fashions if item.get("FashionModelId")}
        if not owned_models:
            return bonuses
        emb = self.state.get("embattle", {})
        front_slots = {int(emb.get(f"Formation{i}", i)) for i in (1, 2, 3)}
        back_slots = {int(emb.get(f"Formation{i}", i)) for i in (4, 5, 6)}
        enum_map = {431: "AP", 432: "HP", 433: "DEF"}
        for row in self.game_data.get("fashion_pr", {}).values():
            members = [int(x.strip()) for x in str(row.get("memberS", "")).split(",") if x.strip().isdigit()]
            if not members or not all(m in owned_models for m in members):
                continue
            for chunk in str(row.get("allAttr", "")).split(","):
                parts = [p.strip() for p in chunk.split("|")]
                if len(parts) >= 4 and parts[0].isdigit() and parts[2].isdigit():
                    target, attr, val = int(parts[0]), int(parts[2]), int(float(parts[3]))
                    if target == 2 or (target == 6 and slot_id in front_slots) or (target == 7 and slot_id in back_slots):
                        key = enum_map.get(attr)
                        if key:
                            bonuses[key] += val
        return bonuses

    def _hero_step_cheer_bonuses(self, heroes_by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
        """Compute party-wide HeroStepCheer bonuses from orange+ partner (mate) slots."""
        bonuses = {"HP": 0, "AP": 0, "DEF": 0}
        cheer_tbl = self.game_data.get("hero_step_cheer", {})
        if not cheer_tbl or not isinstance(getattr(self, "state", None), dict):
            return bonuses
        quality_tbl = self.game_data.get("quality_model", {})
        heroes_cfg = self.game_data.get("heroes", {})
        total_step = 0
        for mate in self._mate_slot_info():
            hero = heroes_by_id.get(mate["HeroId"])
            if not hero:
                continue
            cfg = heroes_cfg.get(str(hero.get("HeroModelId", 0)), {})
            quality = int(cfg.get("quality", 0))
            if quality_tbl:
                color_lv = int(quality_tbl.get(str(quality), {}).get("colorLV", 0))
                if quality == 18:
                    color_lv = 7
            else:
                color_lv = 5 if quality >= 13 else 0
            if color_lv >= 5:
                total_step += int(hero.get("Step", 0))
        if total_step <= 0:
            return bonuses
        max_step = max((int(k) for k in cheer_tbl if k.isdigit()), default=0)
        row = cheer_tbl.get(str(min(total_step, max_step)), {})
        bonuses["AP"] = int(row.get("APADD", 0))
        bonuses["HP"] = int(row.get("HPADD", 0))
        bonuses["DEF"] = int(row.get("DEFADD", 0))
        return bonuses

    def _equip_item_lv(self, equip: dict[str, Any]) -> int:
        """Return EquipModel.itemLv + EquipStepRelation[Step].itemLv for EquipArtifact."""
        mid = str(equip.get("EquipModelId", 0))
        base_lv = int(self.game_data.get("equips", {}).get(mid, {}).get("itemLv", 0))
        step_lv = int(
            self.game_data.get("equip_steps", {})
            .get(mid, {})
            .get(str(int(equip.get("Step", 0))), {})
            .get("itemLv", 0)
        )
        return base_lv + step_lv

    def _compute_equip_artifact_state(self) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
        """Evaluate highest unlocked EquipArtifactRelation tier per slot type (1..4) and sum stats."""
        artifacts_cfg = self.game_data.get("equip_artifact", {})
        slot_keys = {1: "Weapon", 2: "Helmet", 3: "Clothes", 4: "Necklace"}
        prev_map = (
            self.state.get("equip_artifacts", {})
            if isinstance(getattr(self, "state", None), dict)
            else {}
        )
        slots = self.state.get("slots", []) if isinstance(getattr(self, "state", None), dict) else []
        by_type: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: [], 4: []}
        for row in artifacts_cfg.values():
            aid = int(row.get("artifactModelID", 0))
            if aid in by_type:
                by_type[aid].append(row)

        result: dict[str, dict[str, int]] = {}
        bonuses = {"HP": 0, "AP": 0, "DEF": 0}
        for aid, skey in slot_keys.items():
            pinjis = [
                self._equip_item_lv(slot[skey])
                for slot in slots
                if slot.get("HeroId") not in (None, "", EMPTY_ENTITY_ID)
                and isinstance(slot.get(skey), dict)
                and slot[skey].get("EquipModelId")
            ]
            best_row: dict[str, Any] | None = None
            best_key = (-1, -1)
            for row in by_type[aid]:
                need_lv = int(row.get("needItemLv", 0))
                need_num = int(row.get("needEquipNum", 0))
                if sum(1 for p in pinjis if p >= need_lv) >= need_num:
                    rank_key = (int(row.get("Lv", 0)), need_num)
                    if rank_key > best_key:
                        best_key = rank_key
                        best_row = row
            prev_lv = int((prev_map.get(str(aid)) or {}).get("Lv", 0)) if isinstance(prev_map, dict) else 0
            if best_row:
                result[str(aid)] = {
                    "Id": int(best_row["ID"]),
                    "Lv": int(best_row["Lv"]),
                    "OldLv": prev_lv,
                    "ArtifactModelId": aid,
                }
                bonuses["AP"] += int(best_row.get("APADD", 0))
                bonuses["HP"] += int(best_row.get("HPADD", 0))
                bonuses["DEF"] += int(best_row.get("DEFADD", 0))
            else:
                result[str(aid)] = {"Id": 0, "Lv": 0, "OldLv": prev_lv, "ArtifactModelId": aid}
        return result, bonuses

    def _gem_slot_max(self, player_lv: int | None = None) -> int:
        """Return max unlocked gem slots for player level per PlayerLvRelation.gemSlotMax."""
        if player_lv is None:
            player_lv = int(self.state.get("player", {}).get("Lv", 1))
        lv_row = self.game_data.get("player_lv", {}).get(str(player_lv), {})
        if "gemSlotMax" in lv_row:
            return max(0, min(6, int(lv_row["gemSlotMax"])))
        return max(1, min(6, int(player_lv)))

    @staticmethod
    def _normalize_slot_gems(
        slot: dict[str, Any],
        gems_by_id: dict[str, dict[str, Any]] | None = None,
        seen_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Ensure slot['Gem'] has 6 elements using {} for empty sockets (per CalcPrefData.lua:1234)."""
        raw = slot.get("Gem")
        if not isinstance(raw, list):
            raw = []
        norm: list[dict[str, Any]] = []
        for idx in range(6):
            entry = raw[idx] if idx < len(raw) else None
            if not isinstance(entry, dict):
                norm.append({})
                continue
            gid = str(entry.get("Id") or "")
            if not gid or gid == EMPTY_ENTITY_ID:
                norm.append({})
                continue
            if gems_by_id is not None and gid not in gems_by_id:
                norm.append({})
                continue
            if seen_ids is not None:
                if gid in seen_ids:
                    norm.append({})
                    continue
                seen_ids.add(gid)
            mid = int(gems_by_id[gid]["ModelId"]) if gems_by_id is not None else int(entry.get("ModelId", 0))
            if mid <= 0:
                norm.append({})
                continue
            norm.append({"Id": gid, "ModelId": mid})
        slot["Gem"] = norm
        return norm

    def _slot_gem_bonuses(self, slot: dict[str, Any]) -> dict[int, int]:
        """Sum GemModel.attrStr attributes from all valid socketed gems in slot['Gem']."""
        totals: dict[int, int] = {
            301: 0, 302: 0, 303: 0, 304: 0, 305: 0, 306: 0,
            408: 0, 409: 0, 431: 0, 432: 0, 433: 0,
        }
        gem_models = self.game_data.get("gem_model", {})
        for entry in slot.get("Gem") or []:
            if not isinstance(entry, dict):
                continue
            gid = str(entry.get("Id") or "")
            if not gid or gid == EMPTY_ENTITY_ID:
                continue
            gm = gem_models.get(str(entry.get("ModelId", 0)))
            if not gm:
                continue
            for chunk in str(gm.get("attrStr", "")).split(","):
                parts = [p.strip() for p in chunk.split("|")]
                if len(parts) == 2 and parts[0].isdigit():
                    aid, aval = int(parts[0]), int(float(parts[1]))
                    if aid in totals:
                        totals[aid] += aval
        return totals

    def _compute_slot_property(
        self,
        slot: dict[str, Any],
        heroes_by_id: dict[str, dict[str, Any]],
        include_player_star: bool = True,
        formation_models: set[int] | None = None,
        team_talents: Counter[int] | None = None,
        race_talents: dict[int, Counter[int]] | None = None,
        artifact_bonuses: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        hero_id = slot.get("HeroId", EMPTY_ENTITY_ID)
        hero = heroes_by_id.get(hero_id)
        if not hero:
            return _zero_slot_property()

        cfg = self.game_data["heroes"][str(hero["HeroModelId"])]
        lv = int(hero["Lv"])
        step = int(hero.get("Step", 0))
        step_attr = self._get_step_attr(cfg, step)

        reborn_flat, rb_apr, rb_hpr, rb_defr = self._hero_reborn_flat_and_self_rates(hero)
        dashi_apr, dashi_hpr, dashi_defr = (
            self._team_reborn_master_rates(heroes_by_id)
            if (include_player_star and hasattr(self, "state"))
            else (0, 0, 0)
        )
        hero_hp = int(cfg["HPBase"] + cfg["HPUp"] * (lv - 1) + step_attr["HP"]) + reborn_flat[201]
        hero_ap = int(cfg["APBase"] + cfg["APUp"] * (lv - 1) + step_attr["AP"]) + reborn_flat[202]
        hero_def = int(cfg["DEFBase"] + cfg["DEFUp"] * (lv - 1) + step_attr["DEF"]) + reborn_flat[203]
        hero["HP"] = hero_hp
        hero["AP"] = hero_ap
        hero["DEF"] = hero_def
        talent = Counter(team_talents or {})
        hero_race = int(cfg.get("raceID", 0))
        if race_talents and hero_race in race_talents:
            talent += race_talents[hero_race]
        hero_tals = self._hero_talent_rows(hero["HeroModelId"], step)
        self._add_talent_attributes(talent, hero_tals, scope=1)
        for row in hero_tals:
            if row.get("attrEffectRange") in (3, 4, 5) and row.get("attrStr"):
                for pair in row["attrStr"].split(","):
                    attr_s, amount_s = pair.split("|", 1)
                    attr_id = int(attr_s)
                    if 412 <= attr_id <= 417:
                        talent[attr_id] += int(amount_s)
        bonds = self._active_bonds(slot, int(hero["HeroModelId"]), formation_models) if formation_models is not None else []
        ap_rate = 10000 + talent[401] + sum(bond["APR"] for bond in bonds) + rb_apr + dashi_apr
        hp_rate = 10000 + talent[402] + sum(bond["HPR"] for bond in bonds) + rb_hpr + dashi_hpr
        def_rate = 10000 + talent[403] + sum(bond["DEFR"] for bond in bonds) + rb_defr + dashi_defr

        eq_hp, eq_ap, eq_def, eq_fsp = 0, 0, 0, 0
        group_counts: dict[int, int] = {}
        equips_cfg = self.game_data.get("equips", {})
        step_table = self.game_data["equip_steps"]
        for key in ("Weapon", "Helmet", "Clothes", "Necklace"):
            eq = slot.get(key)
            if eq and eq.get("EquipModelId"):
                m = equips_cfg.get(str(eq["EquipModelId"]), {})
                elv = int(eq.get("Lv", 0))
                eq_hp += int(m.get("HP", 0) + m.get("HPUP", 0) * elv)
                eq_ap += int(m.get("AP", 0) + m.get("APUP", 0) * elv)
                eq_def += int(m.get("DEF", 0) + m.get("DEFUP", 0) * elv)
                stats = step_table.get(str(eq["EquipModelId"]), {}).get(str(eq.get("Step", 0)), {})
                eq_hp += stats.get("HP", 0)
                eq_ap += stats.get("AP", 0)
                eq_def += stats.get("DEF", 0)
                eq_fsp += int(m.get("FSP", 0))
                gid = int(m.get("equipGroupID", 0))
                if gid > 0:
                    group_counts[gid] = group_counts.get(gid, 0) + 1

        set_hp, set_ap, set_def = 0, 0, 0
        set_hit, set_dod, set_cri, set_ten = 0, 0, 0, 0
        set_blo, set_bog, set_crid, set_tend = 0, 0, 0, 0
        set_damadd, set_damcut, set_rp, set_fsp = 0, 0, 0, 0
        equip_groups = self.game_data.get("equip_group", {})
        for gid, cnt in group_counts.items():
            tiers = equip_groups.get(str(gid), {})
            for req_str, bonus in tiers.items():
                if cnt >= int(req_str):
                    set_hp += int(bonus.get("HP", 0))
                    set_ap += int(bonus.get("AP", 0))
                    set_def += int(bonus.get("DEF", 0))
                    ap_rate += int(bonus.get("APR", 0))
                    hp_rate += int(bonus.get("HPR", 0))
                    def_rate += int(bonus.get("DEFR", 0))
                    set_hit += int(bonus.get("HIT", 0))
                    set_dod += int(bonus.get("DOD", 0))
                    set_cri += int(bonus.get("CRI", 0))
                    set_ten += int(bonus.get("TEN", 0))
                    set_blo += int(bonus.get("BLO", 0))
                    set_bog += int(bonus.get("BOG", 0))
                    set_crid += int(bonus.get("CRID", 0))
                    set_tend += int(bonus.get("TEND", 0))
                    set_damadd += int(bonus.get("DAMADD", 0))
                    set_damcut += int(bonus.get("DAMCUT", 0))
                    set_rp += int(bonus.get("RP", 0))
                    set_fsp += int(bonus.get("FSP", 0))

        treasures_cfg = self.game_data.get("treasures", {})
        tr_step_attr_tbl = self.game_data.get("treasure_step_attr", {})
        tr_lv_active_tbl = self.game_data.get("treasure_lv_active", {})
        tr_hp_pct_bonus = 0
        tr_ap_pct_bonus = 0
        tr_damaddr = 0
        tr_damcutr = 0
        for tkey in ("Book", "Horse"):
            tr = slot.get(tkey)
            if tr and tr.get("TreasureModelId"):
                tm = treasures_cfg.get(str(tr["TreasureModelId"]), {})
                tlv = int(tr.get("Lv", 0))
                tstep = int(tr.get("Step", 0))
                up_r = float(tm.get("upR", 0.25))
                scale = tlv * up_r + 1.0
                eq_hp += int(float(tm.get("HPBase", 0)) * scale)
                eq_ap += int(float(tm.get("APBase", 0)) * scale)

                type_id = int(tm.get("typeID", 1401))
                val_lv = int(tm.get("valueLv", 1))
                if tstep > 0:
                    sa_id = str(type_id * 100000 + val_lv * 1000 + tstep)
                    sa_row = tr_step_attr_tbl.get(sa_id, {})
                    for chunk in str(sa_row.get("totalAtrrStr", "")).split(","):
                        parts = [s.strip() for s in chunk.split("|")]
                        if len(parts) == 2 and parts[0].isdigit():
                            aid, aval = int(parts[0]), int(float(parts[1]))
                            if aid == 201:
                                eq_hp += aval
                            elif aid == 202:
                                eq_ap += aval
                            elif aid == 203:
                                eq_def += aval
                            elif aid == 410:
                                tr_damaddr += aval
                            elif aid == 411:
                                tr_damcutr += aval

                act_enum = int(tm.get("activeAttrEnumID", 0))
                if tlv > 0 and act_enum in (401, 402):
                    best_val = 0
                    for row in tr_lv_active_tbl.values():
                        if (
                            int(row.get("typeID", 0)) == type_id
                            and int(row.get("valueLv", 0)) == val_lv
                            and int(row.get("Lv", 9999)) <= tlv
                        ):
                            best_val = max(best_val, int(row.get("totalAttrUpVal", 0)))
                    if act_enum == 402:
                        tr_hp_pct_bonus += best_val
                    elif act_enum == 401:
                        tr_ap_pct_bonus += best_val

        star_bonus = (
            self._get_slot_star_bonuses(int(slot.get("SlotId", 0)))
            if (include_player_star and hasattr(self, "state"))
            else {"HP": 0, "AP": 0, "DEF": 0}
        )
        glory_bonus = (
            self._glory_attr_bonuses()
            if (include_player_star and hasattr(self, "state"))
            else {"HP": 0, "AP": 0, "DEF": 0}
        )
        cheer_bonus = (
            self._hero_step_cheer_bonuses(heroes_by_id)
            if (include_player_star and hasattr(self, "state"))
            else {"HP": 0, "AP": 0, "DEF": 0}
        )
        reborn_cheer = (
            self._hero_reborn_cheer_bonuses(heroes_by_id)
            if (include_player_star and hasattr(self, "state"))
            else {"HP": 0, "AP": 0, "DEF": 0}
        )
        artifact_bonus = (
            artifact_bonuses
            if artifact_bonuses is not None
            else (
                self._compute_equip_artifact_state()[1]
                if (include_player_star and hasattr(self, "state"))
                else {"HP": 0, "AP": 0, "DEF": 0}
            )
        )
        hp1 = hero_hp + eq_hp + set_hp + star_bonus["HP"] + glory_bonus["HP"] + cheer_bonus["HP"] + reborn_cheer["HP"] + artifact_bonus["HP"]
        ap1 = hero_ap + eq_ap + set_ap + star_bonus["AP"] + glory_bonus["AP"] + cheer_bonus["AP"] + reborn_cheer["AP"] + artifact_bonus["AP"]
        if tr_hp_pct_bonus > 0:
            hp1 = int(hp1 * (1.0 + tr_hp_pct_bonus / 10000.0))
        if tr_ap_pct_bonus > 0:
            ap1 = int(ap1 * (1.0 + tr_ap_pct_bonus / 10000.0))
        def1 = hero_def + eq_def + set_def + star_bonus["DEF"] + glory_bonus["DEF"] + cheer_bonus["DEF"] + reborn_cheer["DEF"] + artifact_bonus["DEF"]
        gem_bonus = self._slot_gem_bonuses(slot)
        ap1 += gem_bonus[431]
        hp1 += gem_bonus[432]
        def1 += gem_bonus[433]
        if include_player_star and hasattr(self, "state") and self.state.get("fashions"):
            fashion = self._fashion_collection_stats()
            fashion_pr = self._fashion_pr_bonuses(int(slot.get("SlotId", 0)))
            ap1 += fashion[431] + fashion_pr["AP"]  # APADD
            hp1 += fashion[432] + fashion_pr["HP"]  # HPADD
            def1 += fashion[433] + fashion_pr["DEF"]  # DEFADD
        # The VN Property calculation has separate terms for the hero's rate and other flat stats.
        ap_extra = ap1 - hero_ap + talent[202]
        hp_extra = hp1 - hero_hp + talent[201]
        def_extra = def1 - hero_def + talent[203]
        ap1 = hero_ap * ap_rate // 10000 + ap_extra
        hp1 = hero_hp * hp_rate // 10000 + hp_extra
        def1 = hero_def * def_rate // 10000 + def_extra
        fsp = int(cfg.get("FSP", 500)) + step_attr["FSP"] + eq_fsp + set_fsp
        fap = int(hp1 + ap1 * 10 + def1 * 10)

        return {
            "HP": hp1,
            "AP": ap1,
            "DEF": def1,
            "SPD": fsp,
            "FSP": fsp,
            "FAP": fap,
            "AP1": hero_ap,
            "APR1": ap_rate,
            "AP2": ap_extra,
            "APR2": 0,
            "APAdd": 0,
            "APHero": 0,
            "APHeroR": 0,
            "DEF1": hero_def,
            "DEFR1": def_rate,
            "DEF2": def_extra,
            "DEFR2": 0,
            "DEFAdd": 0,
            "DEFHero": 0,
            "DEFHeroR": 0,
            "HP1": hero_hp,
            "HPR1": hp_rate,
            "HP2": hp_extra,
            "HPR2": 0,
            "HPAdd": 0,
            "HPHero": 0,
            "HPHeroR": 0,
            "APToHPHeroR": 0,
            "RP": min(MAX_RAGE, int(cfg.get("RP", 50)) + talent[205] + set_rp),
            "HIT": int(cfg.get("HIT", 10000)) + talent[301] + set_hit + gem_bonus[301],
            "DOD": int(cfg.get("DOD", 0)) + talent[302] + set_dod + gem_bonus[302],
            "CRI": int(cfg.get("CRI", 0)) + talent[303] + set_cri + gem_bonus[303],
            "TEN": int(cfg.get("TEN", 0)) + talent[304] + set_ten + gem_bonus[304],
            "BLO": int(cfg.get("BLO", 0)) + talent[305] + set_blo + gem_bonus[305],
            "BOG": int(cfg.get("BOG", 0)) + talent[306] + set_bog + gem_bonus[306],
            "CRId": int(cfg.get("CRID", 0)) + talent[307] + set_crid,
            "TEND": int(cfg.get("TEND", 0)) + talent[308] + set_tend,
            "CP": talent[404], "BCP": talent[405], "CPR": talent[406], "BCPR": talent[407],
            "DAMADD": talent[408] + set_damadd + gem_bonus[408], "DAMCUT": talent[409] + set_damcut + gem_bonus[409],
            "DAMADDR": talent[410] + tr_damaddr, "DAMCUTR": talent[411] + tr_damcutr,
            "RADAMADDR": talent[412], "RADAMCUTR": talent[413],
            "RBDAMADDR": talent[414], "RBDAMCUTR": talent[415],
            "RCDAMADDR": talent[416], "RCDAMCUTR": talent[417],
            "ActivePrIds": [bond["ID"] for bond in bonds],
        }

    def _active_bonds(self, slot: dict[str, Any], hero_model: int, formation: set[int]) -> list[dict[str, Any]]:
        equipped = {
            item[model_key]
            for keys, model_key in ((self.EQUIP_TYPE_TO_SLOT_KEY.values(), "EquipModelId"),
                                    (("Book", "Horse"), "TreasureModelId"))
            for key in keys
            if (item := slot.get(key)) and item.get("Id") not in (None, "", EMPTY_ENTITY_ID) and item.get(model_key)
        }
        result = []
        for bond_id in self.game_data.get("hero_bonds", {}).get(str(hero_model), ()):
            bond = self.game_data["bonds"][str(bond_id)]
            candidates = formation if bond["typeID"] == 1201 else equipped
            groups = str(bond["member"]).split(",")
            if all(any(int(model) in candidates for model in group.split("|")) for group in groups):
                result.append(bond)
        return result

    def _mate_slot_unlocked(self, slot_id: int) -> bool:
        if slot_id <= 0:
            return False
        star_row = self.game_data.get("attrtree_slots", {}).get(str(20 + slot_id))
        if star_row is not None:
            return int(self.state["player"].get("StarId", 0)) >= int(star_row.get("needAttrTreeID", 0))
        vip_row = self.game_data.get("vip_slot_relation", {}).get(str(slot_id))
        if vip_row is not None:
            return int(self.state["player"].get("Vip", 0)) >= int(vip_row.get("LV", 0))
        return False

    def _mate_slot_info(self) -> list[dict[str, Any]]:
        heroes = {hero["Id"]: hero["HeroModelId"] for hero in self.state["heroes"]}
        mates = []
        for number, hero_id in self.state.get("mates", {}).items():
            slot_id = int(number)
            if self._mate_slot_unlocked(slot_id) and hero_id in heroes:
                mates.append({"SlotId": slot_id, "HeroId": hero_id, "HeroModelId": heroes[hero_id]})
        return sorted(mates, key=lambda row: row["SlotId"])

    def _deployed_hero_ids(self) -> set[str]:
        return {slot["HeroId"] for slot in (*self.state["slots"], *self._mate_slot_info())
                if slot.get("HeroId") not in (None, "", EMPTY_ENTITY_ID)}

    def _get_slot_star_bonuses(self, slot_id: int) -> dict[str, int]:
        """Compute cumulative AttrtreeModel HP/AP/DEF bonuses for a given battle slot."""
        bonuses = {"HP": 0, "AP": 0, "DEF": 0}
        star_id = int(self.state.get("player", {}).get("StarId", 0)) if isinstance(getattr(self, "state", None), dict) else 0
        if star_id <= 0 or not (1 <= slot_id <= 6):
            return bonuses
        tree = self.game_data.get("attrtree", {})
        enum_map = {431: "AP", 432: "HP", 433: "DEF"}
        for sid in range(1, star_id + 1):
            node = tree.get(str(sid))
            if not node:
                continue
            target_slot = (sid % 6) + 1
            if target_slot != slot_id:
                continue
            for enum_id, _mid, val in self._parse_attr_pairs(str(node.get("addAttrList", ""))):
                key = enum_map.get(enum_id)
                if key:
                    bonuses[key] += val
        return bonuses

    def _glory_extra_sta(self) -> int:
        """Compute bonus max STA from Glory Shrine total levels (+1 per 10 total levels)."""
        glory = self.state.get("glory", {})
        total_lv = sum(int(entry.get("Lv", 0)) for entry in glory.values() if isinstance(entry, dict))
        return total_lv // 10

    def _glory_attr_bonuses(self) -> dict[str, int]:
        """Compute party-wide HP/AP/DEF bonuses from Glory Shrine levels."""
        bonuses = {"HP": 0, "AP": 0, "DEF": 0}
        glory = self.state.get("glory", {})
        glory_type = self.game_data.get("glory_type", {})
        enum_map = {431: "AP", 432: "HP", 433: "DEF"}
        for tid_str, entry in glory.items():
            if not isinstance(entry, dict):
                continue
            lv = int(entry.get("Lv", 0))
            if lv <= 0:
                continue
            cfg = glory_type.get(str(tid_str), {})
            key = enum_map.get(int(cfg.get("addAttrEnumID", 0)))
            if key:
                bonuses[key] += lv * int(cfg.get("addValue", 0))
        return bonuses

    @staticmethod
    def _parse_attr_pairs(attr_str: str) -> list[tuple[int, int, int]]:
        out: list[tuple[int, int, int]] = []
        for part in (attr_str or "").split("||"):
            segs = [s.strip() for s in part.split(",") if s.strip()]
            if len(segs) >= 2:
                out.append((int(segs[0]), 0, int(float(segs[1]))))
        return out

    def _sync_main_hero_model(self, state: dict[str, Any] | None = None) -> bool:
        """Keep the main hero HeroModelId and Lv synchronized with StarId/Step/Gender/PlayerLv."""
        st = state if state is not None else getattr(self, "state", None)
        tbl = self.game_data.get("attrtree_heromodel", {})
        if not isinstance(st, dict) or not tbl or not st.get("slots"):
            return False
        slot1 = next((s for s in st["slots"] if int(s.get("SlotId", 0)) == 1), None)
        if not slot1:
            return False
        hero_id = slot1.get("HeroId")
        hero = next((h for h in st.get("heroes", []) if h.get("Id") == hero_id), None)
        if not hero:
            return False
        boy_models = {int(r["boyHeroModelID"]) for r in tbl.values()}
        girl_models = {int(r["girlHeroModelID"]) for r in tbl.values()}
        mc_models = boy_models | girl_models
        cur_model = int(hero.get("HeroModelId", 0))
        hero_cfg = self.game_data.get("heroes", {}).get(str(cur_model), {})
        if cur_model not in mc_models and int(hero_cfg.get("specialType", 0)) != 255:
            return False

        player = st.get("player", {})
        changed = False
        if self.is_normal_gameplay:
            player_lv = max(1, int(player.get("Lv", 1)))
            if int(hero.get("Lv", 1)) != player_lv:
                hero["Lv"] = player_lv
                changed = True

        if cur_model not in mc_models:
            return changed

        star_id = int(player.get("StarId", 0))
        step = int(hero.get("Step", 0))
        tier_ids = sorted(int(k) for k in tbl if str(k).isdigit())
        matched_tier = max((tid for tid in tier_ids if tid <= star_id), default=0)
        if matched_tier == 0 and step >= 1 and 1 in tier_ids:
            matched_tier = 1
        row = tbl[str(matched_tier)]
        if "Gender" in player:
            gender = int(player["Gender"])
        else:
            gender = 1 if cur_model in girl_models else 0
        target_model = int(row["boyHeroModelID"] if gender == 0 else row["girlHeroModelID"])

        if cur_model == target_model and int(slot1.get("HeroModelId", 0)) == target_model:
            return changed
        hero["HeroModelId"] = target_model
        slot1["HeroModelId"] = target_model
        if int(player.get("HeadImageId", 0)) in mc_models:
            player["HeadImageId"] = target_model
        return True

    def _recalc_all_slots_and_fap(self) -> None:
        self._sync_main_hero_model()
        heroes_by_id = {h["Id"]: h for h in self.state["heroes"]}
        formation = {heroes_by_id[hero_id]["HeroModelId"]
                     for hero_id in self._deployed_hero_ids() if hero_id in heroes_by_id}
        team_talents: Counter[int] = Counter()
        race_talents: dict[int, Counter[int]] = {1: Counter(), 2: Counter(), 3: Counter()}
        for slot in self.state["slots"]:
            hero = heroes_by_id.get(slot.get("HeroId"))
            if hero:
                tals = self._hero_talent_rows(hero["HeroModelId"], hero["Step"])
                self._add_talent_attributes(team_talents, tals, scope=2)
                for row in tals:
                    scope = int(row.get("attrEffectRange", 0))
                    if scope in (3, 4, 5) and row.get("attrStr"):
                        for pair in row["attrStr"].split(","):
                            attr_s, amount_s = pair.split("|", 1)
                            attr_id = int(attr_s)
                            if not (412 <= attr_id <= 417):
                                race_talents[scope - 2][attr_id] += int(amount_s)
        new_artifacts, artifact_bonus = self._compute_equip_artifact_state()
        prev_artifacts = self.state.get("equip_artifacts") or {}
        old_artifact_ids = {k: int((prev_artifacts.get(k) or {}).get("Id", 0)) for k in ("1", "2", "3", "4")}
        new_artifact_ids = {k: int(new_artifacts[k]["Id"]) for k in ("1", "2", "3", "4")}
        self.state["equip_artifacts"] = new_artifacts
        if old_artifact_ids != new_artifact_ids and hasattr(self, "_last_rpc_context"):
            self._last_rpc_context["equip_artifacts_changed"] = copy.deepcopy(new_artifacts)

        total_fap = 0
        for slot in self.state["slots"]:
            slot["Property"] = self._compute_slot_property(
                slot,
                heroes_by_id,
                formation_models=formation,
                team_talents=team_talents,
                race_talents=race_talents,
                artifact_bonuses=artifact_bonus,
            )
            slot["FAP"] = int(slot["Property"]["FAP"])
            if slot.get("HeroId") and slot["HeroId"] != EMPTY_ENTITY_ID:
                total_fap += int(slot["Property"]["FAP"])
        self.state["player"]["FAP"] = total_fap

    def _create_normal_default_state(self, player_id: str = "200001") -> dict[str, Any]:
        pc = self.game_data["player_config"]
        vit_max = int(self.game_data["vit_config"].get("maxNum", 200))
        sta_max = int(self.game_data["sta_config"].get("maxNum", 20))

        # Seed initial Male MC placeholder until RoleCreateScene calls Player.NewPlayer
        init_gender = int(pc.get("initGender", 0))
        main_model_id = 12010001 if init_gender == 0 else 12010004
        main_hero = self._build_hero_instance(
            main_model_id, lv=int(pc.get("initLv", 1)), step=int(pc.get("initStepCount", 0))
        )
        heroes_by_id = {main_hero["Id"]: main_hero}

        slots = []
        for idx in range(1, 7):
            if idx == 1:
                s: dict[str, Any] = {
                    "SlotId": 1,
                    "HeroId": main_hero["Id"],
                    "HeroModelId": main_model_id,
                    "Gem": [{} for _ in range(6)],
                }
            else:
                s = {
                    "SlotId": idx,
                    "HeroId": EMPTY_ENTITY_ID,
                    "HeroModelId": 0,
                    "Gem": [{} for _ in range(6)],
                }
            s["Property"] = self._compute_slot_property(s, heroes_by_id)
            s["FAP"] = int(s["Property"]["FAP"])
            slots.append(s)

        init_goods = []
        now = int(time.time())
        for rtype, rmodel, rnum in _parse_resource_str(pc.get("initResource", "")):
            init_goods.append(
                {
                    "Id": str(uuid.uuid4()),
                    "GoodsModelId": rmodel,
                    "Num": rnum,
                    "Crdate": now,
                    "LastTime": 0,
                    "BeginTime": 0,
                    "EndTime": 0,
                }
            )

        first_node = self._make_node_state(1111, flag=1)
        fap = int(slots[0]["Property"]["FAP"])

        return self._normalize_loaded_state({
            "profile": "normal",
            "player": {
                "PlayerId": player_id,
                "Session": f"normal-session-{player_id}",
                "PlayerName": "Adventurer",
                "Gender": init_gender,
                "Lv": int(pc.get("initLv", 1)),
                "EXP": int(pc.get("initEXP", 0)),
                "Vip": int(pc.get("initVip", 0)),
                "VIPLv": int(pc.get("initVip", 0)),
                "VipEXP": int(pc.get("initVipEXP", 0)),
                "Gold": int(pc.get("initGold", 100000)),
                "Diamond": int(pc.get("initDiamond", 0)),
                "VIT": int(pc.get("initVIT", 200)),
                "VITMaxNum": vit_max,
                "STA": int(pc.get("initSTA", 20)),
                "STAMaxNum": sta_max,
                "HeroCoin": int(pc.get("initHeroCoin", 0)),
                "HeroEXP": int(pc.get("initHeroEXP", 5000)),
                "FAP": fap,
                "StarId": 0,
                "HeadImageId": main_model_id,
                "AppErrorLevel": 0,
                "IsNewPlayer": 1,
                "ChargeNum": 0,
                "VITNextRecoverTime": now,
                "STANextRecoverTime": now,
                "LastLoginTime": now,
                "StepCountList": {},
            },
            "heroes": [main_hero],
            "slots": slots,
            "embattle": {f"Formation{i}": i for i in range(1, 7)},
            "equips": [],
            "treasures": [],
            "treasure_debris": [],
            "treasure_protect_end": 0,
            "elite": {
                "fight_count": int(self.game_data.get("elite_config", {}).get("maxFightNum", 3)),
                "buy_count": 0,
                "consume_buy_count": 0,
                "nodes": {},
            },
            "goods": init_goods,
            "claimed_step_rewards": [],
            "recruit_state": {
                "MidAlreadyUseResource": False,
                "HigAlreadyUseResource": False,
                "OutZiCount": 9,
                "history": [],
            },
            "explore": self._default_explore_state(),
            "shop_bought": {},
            "shop_bought_date": self.clock.today_str(),
            "shop_daily_reset_count": 0,
            "vip_gift_bought": [],
            "lv_plan": {"open": False, "rewarded": []},
            "vip_welfare_drawn_date": "",
            "charge_state": {"first_bought": [], "drawn_boxes": [], "orders": {}, "card_orders": {}},
            "month_cards": {},
            "success_target": {
                "start_ts": now,
                "drawn": {},
                "drawn_days": [],
                "if_draw": 0,
                "exchange_counts": {},
            },
            "stats": dict(DEFAULT_PLAYER_STATS),
            "battle": {
                "MaxChapterId": 11,
                "MaxNodeId": 1111,
                "StarCount": 0,
                "HasBoss": "False",
                "BossId": 0,
            },
            "chapters": {
                "11": self._make_chapter_state(11),
            },
            "nodes": {
                "1111": first_node,
            },
        })

    def _create_debug_default_state(self) -> dict[str, Any]:
        heroes_cfg = self.game_data["heroes"]
        hero_instances = []
        slot_infos = []
        for idx, hid in enumerate(self.DEBUG_STARTER_HERO_IDS, start=1):
            cfg = heroes_cfg[hid]
            inst_id = f"10000000-0000-4000-8000-{idx:012d}"
            lv = 10
            inst = self._build_hero_instance(int(hid), lv=lv, step=1, inst_id=inst_id)
            hero_instances.append(inst)
            heroes_map = {h["Id"]: h for h in hero_instances}
            slot = {"SlotId": idx, "HeroId": inst_id, "HeroModelId": int(hid), "Gem": [{} for _ in range(6)]}
            slot["Property"] = self._compute_slot_property(slot, heroes_map)
            slot_infos.append(slot)

        ch11_nodes = sorted(
            [n for n in self.game_data["nodes"].values() if n.get("chapterModelID") == 11],
            key=lambda x: x["ID"],
        )
        node_states = {}
        for i, n in enumerate(ch11_nodes):
            node_states[str(n["ID"])] = self._make_node_state(n["ID"], flag=1 if i == 0 else 0)

        now = int(time.time())
        return self._normalize_loaded_state({
            "profile": "debug",
            "player": {
                "PlayerId": "100001",
                "Session": "local-revival-session-0001",
                "PlayerName": "InuYasha",
                "Lv": 10,
                "EXP": 120,
                "Vip": 5,
                "VIPLv": 5,
                "VipEXP": 3360,
                "ChargeNum": 3360,
                "Gold": 50000,
                "Diamond": 8888,
                "VIT": 120,
                "VITMaxNum": 200,
                "VITNextRecoverTime": now + 360,
                "STA": 40,
                "STAMaxNum": 40,
                "STANextRecoverTime": now,
                "HeroCoin": 1200,
                "HeroEXP": 15000,
                "FAP": 18500,
                "StarId": 0,
                "HeadImageId": 12011004,
                "AppErrorLevel": 0,
                "IsNewPlayer": 0,
                "LastLoginTime": now,
                "StepCountList": {"1": 999},
            },
            "heroes": hero_instances,
            "slots": slot_infos,
            "embattle": {"Formation1": 1, "Formation2": 2, "Formation3": 3, "Formation4": 4, "Formation5": 0, "Formation6": 0},
            "equips": [],
            "goods": [],
            "claimed_step_rewards": [],
            "recruit_state": {"MidAlreadyUseResource": False, "HigAlreadyUseResource": False, "OutZiCount": 5},
            "explore": self._default_explore_state(),
            "lv_plan": {"open": False, "rewarded": []},
            "vip_welfare_drawn_date": "",
            "charge_state": {"first_bought": [], "drawn_boxes": [], "orders": {}},
            "month_cards": {},
            "battle": {
                "MaxChapterId": 11,
                "MaxNodeId": ch11_nodes[0]["ID"] if ch11_nodes else 1111,
                "StarCount": 0,
                "HasBoss": "False",
                "BossId": 0,
            },
            "chapters": {"11": self._make_chapter_state(11)},
            "nodes": node_states,
        })

    @staticmethod
    def _make_chapter_state(ch_id: int) -> dict[str, Any]:
        return {
            "ChapterModelId": ch_id,
            "StarCount": 0,
            "IfPass": 0,
            "IfDrawBoxA": False,
            "IfDrawBoxB": False,
            "IfDrawBoxC": False,
            "CanDrawRoadBoxA": 0,
            "CanDrawRoadBoxB": 0,
            "CanDrawRoadBoxC": 0,
        }

    @staticmethod
    def _make_node_state(node_id: int, flag: int = 1) -> dict[str, Any]:
        return {
            "NodeModelId": node_id,
            "StarCount": 0,
            "Flag": flag,
            "FightCount": 0,
            "FightTime": 0,
            "ResetFightCount": 0,
            "ResetFightTime": 0,
        }

    def _mark_goods_changed(self, model_id: int) -> None:
        if not hasattr(self, "_last_rpc_context"):
            return
        changed = self._last_rpc_context.setdefault("goods_changed", {})
        if changed is None:
            changed = {}
            self._last_rpc_context["goods_changed"] = changed
        changed[str(model_id)] = [g for g in self.state.get("goods", []) if int(g["GoodsModelId"]) == model_id]

    def _mark_treasure_debris_changed(self, debris_model_id: int) -> None:
        if not hasattr(self, "_last_rpc_context"):
            return
        changed = self._last_rpc_context.setdefault("treasure_debris_changed", {})
        if changed is None:
            changed = {}
            self._last_rpc_context["treasure_debris_changed"] = changed
        changed[str(debris_model_id)] = [
            d for d in self.state.get("treasure_debris", []) if int(d["TreasureDebrisModelId"]) == debris_model_id
        ]

    def _mark_reborn_goods_changed(self, model_id: int) -> None:
        if not hasattr(self, "_last_rpc_context"):
            return
        changed = self._last_rpc_context.setdefault("reborn_goods_changed", {})
        if changed is None:
            changed = {}
            self._last_rpc_context["reborn_goods_changed"] = changed
        changed[str(model_id)] = [
            rg for rg in self.state.get("reborn_goods", []) if int(rg.get("ModelId", 0)) == model_id
        ]

    def _grant_resources_from_tuples(
        self,
        res_tuples: list[tuple[int, int, int]],
        source: str,
        tx_prefix: str,
        validate_resources: bool = True,
    ) -> list[dict[str, Any]]:
        """Apply a list of (typeID, modelID, num) drops and build BaseGetGameResourceList payload."""
        if validate_resources:
            self._validate_resource_tuples(res_tuples, source=source)
        player_attrs: list[dict[str, Any]] = []
        new_heroes: list[dict[str, Any]] = []
        new_equips: list[dict[str, Any]] = []
        new_treasures: list[dict[str, Any]] = []
        new_treasure_debris: list[dict[str, Any]] = []
        new_goods: list[dict[str, Any]] = []
        new_reborn_goods: list[dict[str, Any]] = []
        new_fashions: list[dict[str, Any]] = []
        new_gems: list[dict[str, Any]] = []

        attr_map = {
            1101: "EXP",
            1102: "VIT",
            1103: "STA",
            1111: "Diamond",
            1112: "Gold",
            1113: "Contribution",
            1115: "PVPCoin",
            1116: "HeroCoin",
            1117: "HeroEXP",
            1119: "GDDHCoin",
            1120: "BossCoin",
            1124: "Merit",
            1128: "RebornCoin",
        }

        for idx, (rtype, rmodel, rnum) in enumerate(res_tuples):
            if rnum <= 0:
                continue
            if rtype == 2112:
                gold_amt = int(rnum) * max(1, int(self.state["player"].get("Lv", 1)))
                self.ledger.apply_player_delta(
                    self.state["player"],
                    self.profile_name,
                    "Gold",
                    gold_amt,
                    source=source,
                    idempotency_key=f"{tx_prefix}:{idx}:Gold",
                    allow_duplicate_noop=True,
                )
                player_attrs.append({"ResourceTypeSub": 1112, "Num": gold_amt})
            elif rtype in attr_map:
                field = attr_map[rtype]
                self.ledger.apply_player_delta(
                    self.state["player"],
                    self.profile_name,
                    field,
                    rnum,
                    source=source,
                    idempotency_key=f"{tx_prefix}:{idx}:{field}",
                    allow_duplicate_noop=True,
                )
                player_attrs.append({"ResourceTypeSub": rtype, "Num": rnum})
            elif rtype == 1201:
                for copy_i in range(rnum):
                    hero_inst = self._build_hero_instance(rmodel, lv=1, step=0)
                    self.state["heroes"].append(hero_inst)
                    new_heroes.append(hero_inst)
                    self.ledger.record_grant_event(
                        account_id=str(self.state["player"]["PlayerId"]),
                        profile=self.profile_name,
                        resource_type=f"Hero:{rmodel}",
                        amount=1,
                        balance_after=len(self.state["heroes"]),
                        source=source,
                        idempotency_key=f"{tx_prefix}:{idx}:hero:{copy_i}:{hero_inst['Id']}",
                    )
            elif rtype in (1301, 1302, 1303, 1304):
                for copy_i in range(rnum):
                    eq_inst = self._build_equip_instance(rmodel)
                    self.state["equips"].append(eq_inst)
                    new_equips.append(eq_inst)
                    self.ledger.record_grant_event(
                        account_id=str(self.state["player"]["PlayerId"]),
                        profile=self.profile_name,
                        resource_type=f"Equip:{rmodel}",
                        amount=1,
                        balance_after=len(self.state["equips"]),
                        source=source,
                        idempotency_key=f"{tx_prefix}:{idx}:equip:{copy_i}:{eq_inst['Id']}",
                    )
            elif rtype in (1401, 1402):
                treasures_list = self.state.setdefault("treasures", [])
                for copy_i in range(rnum):
                    tr_inst = {
                        "Id": str(uuid.uuid4()),
                        "TreasureModelId": rmodel,
                        "Lv": 0,
                        "Step": 0,
                        "EXP": 0,
                    }
                    treasures_list.append(tr_inst)
                    new_treasures.append(tr_inst)
                    self.ledger.record_grant_event(
                        account_id=str(self.state["player"]["PlayerId"]),
                        profile=self.profile_name,
                        resource_type=f"Treasure:{rmodel}",
                        amount=1,
                        balance_after=len(treasures_list),
                        source=source,
                        idempotency_key=f"{tx_prefix}:{idx}:treasure:{copy_i}:{tr_inst['Id']}",
                    )
            elif rtype in (1503, 1504):
                debris_list = self.state.setdefault("treasure_debris", [])
                existing_deb = next(
                    (d for d in debris_list if int(d["TreasureDebrisModelId"]) == rmodel),
                    None,
                )
                if existing_deb:
                    existing_deb["Num"] = int(existing_deb["Num"]) + rnum
                    deb_obj = dict(existing_deb)
                else:
                    deb_obj = {
                        "Id": str(uuid.uuid4()),
                        "TreasureDebrisModelId": rmodel,
                        "Num": rnum,
                    }
                    debris_list.append(deb_obj)
                new_treasure_debris.append({**deb_obj, "ResourceTypeSub": rtype, "Num": rnum})
                self._mark_treasure_debris_changed(rmodel)
                self.ledger.record_grant_event(
                    account_id=str(self.state["player"]["PlayerId"]),
                    profile=self.profile_name,
                    resource_type=f"TreasureDebris:{rmodel}",
                    amount=rnum,
                    balance_after=deb_obj["Num"],
                    source=source,
                    idempotency_key=f"{tx_prefix}:{idx}:debris:{rmodel}",
                )
            elif rtype == 1901:
                fashions_list = self.state.setdefault("fashions", [])
                for copy_i in range(rnum):
                    f_inst = {"Id": str(uuid.uuid4()), "FashionModelId": rmodel, "Step": 0}
                    fashions_list.append(f_inst)
                    new_fashions.append({**f_inst, "ResourceTypeSub": rtype})
                    self.ledger.record_grant_event(
                        account_id=str(self.state["player"]["PlayerId"]),
                        profile=self.profile_name,
                        resource_type=f"Fashion:{rmodel}",
                        amount=1,
                        balance_after=len(fashions_list),
                        source=source,
                        idempotency_key=f"{tx_prefix}:{idx}:fashion:{copy_i}:{f_inst['Id']}",
                    )
            elif rtype == 2000:
                gems_list = self.state.setdefault("gems", [])
                for copy_i in range(rnum):
                    gem_inst = {"Id": str(uuid.uuid4()), "ModelId": rmodel}
                    gems_list.append(gem_inst)
                    new_gems.append({**gem_inst, "ResourceTypeSub": rtype, "Num": 1})
                    self.ledger.record_grant_event(
                        account_id=str(self.state["player"]["PlayerId"]),
                        profile=self.profile_name,
                        resource_type=f"Gem:{rmodel}",
                        amount=1,
                        balance_after=len(gems_list),
                        source=source,
                        idempotency_key=f"{tx_prefix}:{idx}:gem:{copy_i}:{gem_inst['Id']}",
                    )
            elif rtype == 2701:
                rb_list = self.state.setdefault("reborn_goods", [])
                existing_rb = next((rg for rg in rb_list if int(rg.get("ModelId", 0)) == rmodel), None)
                if existing_rb:
                    existing_rb["Num"] = int(existing_rb.get("Num", 0)) + rnum
                    stored_rb = existing_rb
                else:
                    stored_rb = {
                        "Id": str(uuid.uuid4()),
                        "ModelId": rmodel,
                        "Num": rnum,
                    }
                    rb_list.append(stored_rb)
                new_reborn_goods.append({**stored_rb, "ResourceTypeSub": 2701, "Num": rnum})
                self._mark_reborn_goods_changed(rmodel)
                self.ledger.record_grant_event(
                    account_id=str(self.state["player"]["PlayerId"]),
                    profile=self.profile_name,
                    resource_type=f"RebornGoods:{rmodel}",
                    amount=rnum,
                    balance_after=stored_rb["Num"],
                    source=source,
                    idempotency_key=f"{tx_prefix}:{idx}:reborn_goods:{rmodel}",
                )
            else:
                existing = next((g for g in self.state["goods"] if g["GoodsModelId"] == rmodel), None)
                if existing:
                    existing["Num"] += rnum
                    stored_obj = existing
                else:
                    stored_obj = {
                        "Id": str(uuid.uuid4()),
                        "GoodsModelId": rmodel,
                        "Num": rnum,
                        "Crdate": int(time.time()),
                        "LastTime": 0,
                        "BeginTime": 0,
                        "EndTime": 0,
                    }
                    self.state["goods"].append(stored_obj)
                new_goods.append({**stored_obj, "ResourceTypeSub": rtype, "Num": rnum})
                self._mark_goods_changed(rmodel)
                self.ledger.record_grant_event(
                    account_id=str(self.state["player"]["PlayerId"]),
                    profile=self.profile_name,
                    resource_type=f"Goods:{rmodel}",
                    amount=rnum,
                    balance_after=stored_obj["Num"],
                    source=source,
                    idempotency_key=f"{tx_prefix}:{idx}:goods:{rmodel}",
                )

        bundle: dict[str, Any] = {}
        if player_attrs:
            bundle["PlayerAttr"] = player_attrs
        if new_heroes:
            bundle["Hero"] = new_heroes
        if new_equips:
            bundle["Equip"] = new_equips
        if new_treasures:
            bundle["Treasure"] = new_treasures
        if new_treasure_debris:
            bundle["TreasureDebris"] = new_treasure_debris
        if new_goods:
            bundle["Goods"] = new_goods
        if new_reborn_goods:
            bundle["RebornGoods"] = new_reborn_goods
        if new_fashions:
            bundle["Fashion"] = new_fashions
            self._recalc_all_slots_and_fap()
            if hasattr(self, "_last_rpc_context"):
                self._last_rpc_context["slots_changed"] = True
        if new_gems:
            bundle["Gem"] = new_gems
        if "boss_battle" in self.state:
            self.state["boss_battle"]["jifen"] = int(self.state["player"].get("BossCoin", self.state["boss_battle"].get("jifen", 0)))
        return [bundle] if bundle else []

    def _sync_level_from_exp(self) -> tuple[int, int]:
        """Recompute player Lv from PlayerLvRelation EXPTotal and sync MainHero Lv."""
        old_lv = int(self.state["player"]["Lv"])
        exp = int(self.state["player"]["EXP"])
        max_lv = int(self.game_data["player_config"].get("maxPlayerLV", 80))
        new_lv = old_lv
        for lv_str, row in self.game_data.get("player_lv", {}).items():
            lv_val = int(lv_str)
            if lv_val <= max_lv and exp >= int(row.get("EXPTotal", 0)) and lv_val > new_lv:
                new_lv = lv_val

        if new_lv > old_lv:
            self.state["player"]["Lv"] = new_lv
            crit_num = int(self.game_data.get("explore_config", {}).get("critNum", 5))
            exp_st = self._explore_snapshot()
            if exp_st["RemainNum"] < exp_st["MaxNum"]:
                exp_st["RemainNum"] = min(exp_st["MaxNum"], exp_st["RemainNum"] + crit_num * (new_lv - old_lv))
            if exp_st["RemainNum"] >= exp_st["MaxNum"]:
                exp_st["RecoverTime"] = 0
            self.state["explore"] = exp_st
            for lv_step in range(old_lv + 1, new_lv + 1):
                lv_row = self.game_data.get("player_lv", {}).get(str(lv_step), {})
                bonus_tuples: list[tuple[int, int, int]] = []
                if int(lv_row.get("rewardDiamond", 0)) > 0:
                    bonus_tuples.append((1111, 0, int(lv_row["rewardDiamond"])))
                if int(lv_row.get("rewardSTA", 0)) > 0:
                    bonus_tuples.append((1103, 0, int(lv_row["rewardSTA"])))
                bonus_tuples.extend(_parse_resource_str(str(lv_row.get("rewardResource", ""))))
                if bonus_tuples:
                    self._grant_resources_from_tuples(
                        bonus_tuples,
                        source=f"level_up:{lv_step}",
                        tx_prefix=f"lvup:{self.profile_name}:{self.state['player']['PlayerId']}:{lv_step}",
                    )
            # MainHero (specialType=255 or Slot 1 hero) tracks player Lv
            if self.is_normal_gameplay and self.state["slots"]:
                main_hid = self.state["slots"][0].get("HeroId")
                for h in self.state["heroes"]:
                    if h["Id"] == main_hid or int(self.game_data["heroes"].get(str(h.get("HeroModelId", 0)), {}).get("specialType", 0)) == 255:
                        h["Lv"] = new_lv
                self._recalc_all_slots_and_fap()
            self._unlock_eligible_next_chapters()
            self._sync_limitthebounty_trigger_lv()
        return old_lv, new_lv

    def _unlock_next_chapter_after(self, ch_id: int) -> dict[str, Any] | None:
        """Unlock chapter ch_id+1 only when BattleChapterModel.needLV is satisfied (VN original rule)."""
        next_ch_id = ch_id + 1
        next_cfg = self.game_data["chapters"].get(str(next_ch_id))
        if not next_cfg or str(next_ch_id) in self.state.get("chapters", {}):
            return None
        need_lv = int(next_cfg.get("needLV", 1))
        if int(self.state["player"].get("Lv", 1)) < need_lv:
            return None
        next_chapter = self._make_chapter_state(next_ch_id)
        self.state["chapters"][str(next_ch_id)] = next_chapter
        next_ch_nodes = sorted(
            [int(k) for k, v in self.game_data["nodes"].items() if v.get("chapterModelID") == next_ch_id]
        )
        if next_ch_nodes:
            self.state["nodes"].setdefault(str(next_ch_nodes[0]), self._make_node_state(next_ch_nodes[0], flag=1))
            self.state["battle"]["MaxNodeId"] = max(self.state["battle"]["MaxNodeId"], next_ch_nodes[0])
        self.state["battle"]["MaxChapterId"] = max(self.state["battle"]["MaxChapterId"], next_ch_id)
        return next_chapter

    def _unlock_eligible_next_chapters(self) -> list[dict[str, Any]]:
        """Unlock any passed chapter's successor once player Lv meets BattleChapterModel.needLV."""
        unlocked: list[dict[str, Any]] = []
        for cid_str, ch_st in sorted(list(self.state.get("chapters", {}).items()), key=lambda kv: int(kv[0])):
            if int(ch_st.get("IfPass", 0)) == 1:
                nxt = self._unlock_next_chapter_after(int(cid_str))
                if nxt is not None:
                    unlocked.append(nxt)
        return unlocked

    def _hero_fight_obj(
        self,
        cfg: dict[str, Any],
        lv: int = 1,
        is_boss: bool = False,
        hp_mult: float = 1.0,
        ap_mult: float = 1.0,
        def_mult: float = 1.0,
        step: int = 0,
        reborn_step: int = 0,
        reborn_id: int = 0,
        override_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        stats = override_stats or {}
        if override_stats:
            hp = int(override_stats["HP"] * hp_mult)
            ap = int(override_stats["AP"] * ap_mult)
            defense = int(override_stats["DEF"] * def_mult)
            rp = int(override_stats.get("RP", cfg.get("RP", 50)))
            fsp = int(override_stats.get("FSP", cfg.get("FSP", 500)))
            hit = int(override_stats.get("HIT", cfg.get("HIT", 10000)))
            dod = int(override_stats.get("DOD", cfg.get("DOD", 0)))
            cri = int(override_stats.get("CRI", cfg.get("CRI", 0)))
            ten = int(override_stats.get("TEN", cfg.get("TEN", 0)))
            blo = int(override_stats.get("BLO", cfg.get("BLO", 0)))
            bog = int(override_stats.get("BOG", cfg.get("BOG", 0)))
            crid = int(override_stats.get("CRId", cfg.get("CRID", 0)))
            tend = int(override_stats.get("TEND", cfg.get("TEND", 0)))
        else:
            step_attr = self._get_step_attr(cfg, step) if step > 0 else {"HP": 0, "AP": 0, "DEF": 0, "FSP": 0}
            rb_flat = (
                self._hero_reborn_flat_and_self_rates({"RebornId": reborn_id, "RebornStepInfo": []})[0]
                if reborn_id > 0
                else Counter()
            )
            hp = max(1, int((cfg["HPBase"] + cfg["HPUp"] * (lv - 1) + step_attr["HP"] + rb_flat[201]) * hp_mult))
            ap = max(1, int((cfg["APBase"] + cfg["APUp"] * (lv - 1) + step_attr["AP"] + rb_flat[202]) * ap_mult))
            defense = max(0, int((cfg["DEFBase"] + cfg["DEFUp"] * (lv - 1) + step_attr["DEF"] + rb_flat[203]) * def_mult))
            rp = int(cfg.get("RP", 50))
            fsp = int(cfg.get("FSP", 500)) + step_attr["FSP"]
            hit = int(cfg.get("HIT", 10000))
            dod = int(cfg.get("DOD", 0))
            cri = int(cfg.get("CRI", 0))
            ten = int(cfg.get("TEN", 0))
            blo = int(cfg.get("BLO", 0))
            bog = int(cfg.get("BOG", 0))
            crid = int(cfg.get("CRID", 0))
            tend = int(cfg.get("TEND", 0))

        buff_cfg = self.game_data.get("combat_buffs", {})
        tal_rows = self._hero_talent_rows(cfg["ID"], step)
        npc_rx: Counter[int] = Counter()
        if not override_stats:
            for row in tal_rows:
                if row.get("attrEffectRange") in (1, 3, 4, 5) and row.get("attrStr"):
                    for pair in row["attrStr"].split(","):
                        attr_s, amount_s = pair.split("|", 1)
                        attr_id = int(attr_s)
                        if 412 <= attr_id <= 417:
                            npc_rx[attr_id] += int(amount_s)
        buff_ids = dict.fromkeys(buff for row in tal_rows
                                 for buff in row["buffList"].split(",") if buff)
        for bid in self._hero_reborn_talent_buffs(reborn_id):
            buff_ids.setdefault(bid, None)
        ra_id = int(cfg["UAID"]) if self._hero_uaid_unlocked(cfg, reborn_id) else int(cfg.get("RAID", 1002008))
        return {
            "HP": hp,
            "TotalHp": hp,
            "AP": ap,
            "DEF": defense,
            "RP": rp,
            "HIT": hit,
            "DOD": dod,
            "CRI": cri,
            "TEN": ten,
            "BLO": blo,
            "BOG": bog,
            "CRId": crid,
            "TEND": tend,
            "NAId": cfg.get("NAID", 1001008),
            "RAId": ra_id,
            "HeroModelId": cfg["ID"],
            "Name": cfg["name"],
            "Quality": cfg.get("quality", 15),
            "RaceId": cfg.get("raceID", 1),
            "FSP": fsp,
            "DAM": 0,
            "CP": stats.get("CP", 0),
            "BCP": stats.get("BCP", 0),
            "CPR": stats.get("CPR", 0),
            "BCPR": stats.get("BCPR", 0),
            "DAMADD": stats.get("DAMADD", 0),
            "DAMCUT": stats.get("DAMCUT", 0),
            "DAMADDR": stats.get("DAMADDR", 0),
            "DAMCUTR": stats.get("DAMCUTR", 0),
            "RADAMADDR": stats.get("RADAMADDR", npc_rx[412]),
            "RADAMCUTR": stats.get("RADAMCUTR", npc_rx[413]),
            "RBDAMADDR": stats.get("RBDAMADDR", npc_rx[414]),
            "RBDAMCUTR": stats.get("RBDAMCUTR", npc_rx[415]),
            "RCDAMADDR": stats.get("RCDAMADDR", npc_rx[416]),
            "RCDAMCUTR": stats.get("RCDAMCUTR", npc_rx[417]),
            "BuffList": ",".join(bid for bid in buff_ids if bid in buff_cfg and supports_talent_buff(buff_cfg[bid], buff_cfg)),
            "IsBoss": is_boss,
            "BodyTypeR": 12500 if is_boss else 10000,
            "Step": step if self.is_normal_gameplay else max(1, step),
            "RebornStep": reborn_step,
            "LargePic": cfg["largePic"],
            "SmallPic": cfg["smallPic"],
            "SkillSound": cfg.get("skillSound", "0"),
        }

    def handle_rpc(self, req: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            return self._handle_rpc_locked(req)

    def _apply_step_count_update(self, guide_id: int, ordinal: int) -> bool:
        """Persist a guide step update while protecting completed guides from stale regression."""
        steps = self.state["player"].setdefault("StepCountList", {})
        gid_str = str(guide_id)
        existing = int(steps.get(gid_str, 0))
        if guide_id == 1 and existing >= 900 and ordinal < 900:
            return False
        guide_cfg = self.game_data.get("guide_relation", {}).get(gid_str, {})
        max_ord = len(guide_cfg) if isinstance(guide_cfg, dict) else 0
        if max_ord > 0 and existing > max_ord and ordinal <= max_ord:
            return False
        if existing == ordinal:
            return False
        steps[gid_str] = ordinal
        return True

    def _handle_rpc_locked(self, req: dict[str, Any]) -> dict[str, Any]:
        module = req.get("ModuleName", "")
        method = req.get("MethodName", "")
        data = req.get("Data") or []
        key = f"{module}.{method}"

        # Persist piggybacked ExtensionString.GuideInfo from client HttpClient.lua
        ext = req.get("ExtensionString") or {}
        if isinstance(ext, dict) and ext.get("GuideInfo"):
            changed = False
            for g in ext["GuideInfo"]:
                if isinstance(g, dict) and "GuideId" in g and "Ordinal" in g:
                    try:
                        gid_int = int(g["GuideId"])
                        ordinal = int(g["Ordinal"])
                    except (TypeError, ValueError):
                        continue
                    if ordinal >= 0 and self._apply_step_count_update(gid_int, ordinal):
                        changed = True
            if changed:
                self.save()

        self._last_rpc_context: dict[str, Any] = {
            "status": 0,
            "lv_changed": False,
            "slots_changed": False,
        }

        handlers = {
            "Player.Login": self._rpc_login,
            "Player.Login_ForTest": self._rpc_login,
            "Player.NewPlayer": self._rpc_new_player,
            "Player.GetInitData": self._rpc_get_init_data,
            "Player.SyncAvatarInfo": self._rpc_sync_avatar,
            "Player.AvatarInfo": self._rpc_sync_avatar,
            "Player.AlterPlayerStepCount": self._rpc_alter_step_count,
            "Player.GetStepCountReward": self._rpc_get_step_count_reward,
            "Player.AlterPlayerHeadId": self._rpc_alter_player_head_id,
            "Player.AlterPlayerName": self._rpc_alter_player_name,
            "Player.GetPlayerInfo": self._rpc_player_get_player_info,
            "Bag.BagExpand": self._rpc_bag_expand,
            "HeroRecruit.RecruitInfo": self._rpc_recruit_info,
            "HeroRecruit.Recruit": self._rpc_recruit,
            "Callequip.GetCallEquipData": self._rpc_callequip_get_data,
            "Callequip.CallEquip": self._rpc_callequip_call,
            "Hero.HeroLvUp": self._rpc_hero_lv_up,
            "Hero.HeroStepUp": self._rpc_hero_step_up,
            "Hero.HeroRefine": self._rpc_hero_refine,
            "Hero.HeroRebirth": self._rpc_hero_rebirth,
            "RebornInfo.Activate": self._rpc_reborn_activate,
            "RebornInfo.Reborn": self._rpc_reborn_upgrade,
            "RebornInfo.ComposeAndActivateForOneKey": self._rpc_reborn_one_key_activate,
            "RebornInfo.RebornGoodsCompose": self._rpc_reborn_goods_compose,
            "RebornInfo.RebornGoodsRefine": self._rpc_reborn_goods_refine,
            "RebornShop.GetInfo": self._rpc_reborn_shop_get_info,
            "RebornShop.RefreshtGoodsList": self._rpc_reborn_shop_refresh,
            "RebornShop.RebornShopBuyGoods": self._rpc_reborn_shop_buy,
            "Slot.HeroCombat": self._rpc_slot_hero_combat,
            "Slot.MateinfoCombat": self._rpc_slot_mate_combat,
            "Slot.OneKeyEquipCombat": self._rpc_slot_one_key_equip_combat,
            "Slot.GemCombat": self._rpc_slot_gem_combat,
            "Slot.GemOneKeyCombat": self._rpc_slot_gem_one_key_combat,
            "Slot.SlotFormations": self._rpc_slot_formations,
            "SlotFormation.GetFormation": self._rpc_get_formation,
            "SlotFormation.Change": self._rpc_change_formation,
            "Equip.EquipCompose": self._rpc_equip_compose,
            "Equip.EquipOneKeyCompose": self._rpc_equip_one_key_compose,
            "Gem.GemCompose": self._rpc_gem_compose,
            "Gem.GemOneKeyCompose": self._rpc_gem_one_key_compose,
            "Equip.OneKeyEquipLvUp": self._rpc_one_key_equip_lv_up,
            "Equip.EquipLvUpForCount": self._rpc_equip_lv_up_for_count,
            "Equip.EquipStepUp": self._rpc_equip_step_up,
            "Equip.EquipRefine": self._rpc_equip_refine,
            "Equip.EquipRebirth": self._rpc_equip_rebirth,
            "Treasure.TreasureRefine": self._rpc_treasure_refine,
            "Treasure.TreasureLvUp": self._rpc_treasure_lv_up,
            "Treasure.TreasureStepUp": self._rpc_treasure_step_up,
            "Treasure.TreasureRebirth": self._rpc_treasure_rebirth,
            "Treasure.TreasureCompose": self._rpc_treasure_compose_color,
            "Battle.GetBattleInfo": self._rpc_get_battle_info,
            "Battle.GetNodeList": self._rpc_get_node_list,
            "Battle.AllChapterInfo": self._rpc_all_chapter_info,
            "Battle.GetFightInfo": self._rpc_get_fight_info,
            "Battle.Fight": self._rpc_battle_fight,
            "Battle.ConFight": self._rpc_battle_con_fight,
            "Battle.ResetCount": self._rpc_battle_reset_count,
            "Battle.DrawRoadBox": self._rpc_draw_road_box,
            "Battle.DrawBox": self._rpc_draw_box,
            "Battle.OneKeyDrawBoxs": self._rpc_one_key_draw_boxs,
            "Nightmare.GetNightmareInfo": self._rpc_nightmare_get_info,
            "Nightmare.GetNodeList": self._rpc_nightmare_get_node_list,
            "Nightmare.AllChapterInfo": self._rpc_nightmare_all_chapter_info,
            "Nightmare.GetFightInfo": self._rpc_nightmare_get_fight_info,
            "Nightmare.Fight": self._rpc_nightmare_fight,
            "Nightmare.ConFight": self._rpc_nightmare_con_fight,
            "Nightmare.HiAutoFight": self._rpc_nightmare_hi_auto_fight,
            "Nightmare.ResetCount": self._rpc_nightmare_reset_count,
            "Nightmare.DrawBox": self._rpc_nightmare_draw_box,
            "Nightmare.DrawRoadBox": self._rpc_nightmare_draw_road_box,
            "Nightmare.OneKeyDrawBoxs": self._rpc_nightmare_one_key_draw_boxs,
            "Nightmare.RankList": self._rpc_nightmare_rank_list,
            "Nightmare.Formation": self._rpc_nightmare_formation,
            "Explore.GetInfo": self._rpc_explore_get_info,
            "Explore.Explore": self._rpc_explore_run,
            "Explore.OneKeyExplore": self._rpc_explore_one_key,
            "Explore.BuyExploreNum": self._rpc_explore_buy,
            "Explore.DrawDailyReward": self._rpc_explore_draw_daily,
            "LightenStar.GetLightenStarInfo": self._rpc_lighten_star_info,
            "BddInfo.Info": self._rpc_bdd_info,
            "BddInfo.GetFightInfo": self._rpc_bdd_get_fight_info,
            "BddInfo.Fight": self._rpc_bdd_fight,
            "BddInfo.RewardBox": self._rpc_bdd_reward_box,
            "BddInfo.GetBuffs": self._rpc_bdd_get_buffs,
            "BddInfo.SelectBuff": self._rpc_bdd_select_buff,
            "BddInfo.Reset": self._rpc_bdd_reset,
            "BddInfo.Ranking": self._rpc_bdd_ranking,
            "BddInfo.OneKeyThreeStar": self._rpc_bdd_sweep,
            "BddInfo.BuyShop": self._rpc_bdd_buy_shop,
            "BddInfo.EquipShopInfo": self._rpc_bdd_equip_shop_info,
            "BddInfo.EquipShopExchange": self._rpc_bdd_equip_shop_exchange,
            "LightenStar.LightenStar": self._rpc_lighten_star_up,
            "LightenStar.LightenStarForOneKey": self._rpc_lighten_star_one_key,
            "ShopGoods.ShopGoodsList": self._rpc_shop_goods_list,
            "ShopGoods.GetShopGoodsInfo": self._rpc_get_shop_goods_info,
            "ShopGoods.BuyGoods": self._rpc_shop_buy_goods,
            "ShopGoods.ResetDaily": self._rpc_shop_reset_daily,
            "ShopGift.ShopGiftList": self._rpc_shop_gift_list,
            "ShopGift.BuyGift": self._rpc_shop_buy_gift,
            "Goods.GoodsUse": self._rpc_goods_use,
            "Goods.GoodsUseForBoxChoice": self._rpc_goods_use_box_choice,
            "Goods.GoodsSell": self._rpc_goods_sell,
            "TreasureLootProtect.GetTreasureLootProtectInfo": self._rpc_treasure_protect_info,
            "TreasureLootProtect.TreasureLootProtect": self._rpc_treasure_protect_buy,
            "TreasureLoot.TreasureDebrisTargetList": self._rpc_treasure_target_list,
            "TreasureLoot.TreasureLoot": self._rpc_treasure_loot,
            "TreasureLoot.TreasureLootForCount": self._rpc_treasure_loot_count,
            "TreasureLoot.TreasureLootForOneKey": self._rpc_treasure_loot_one_key,
            "TreasureDebris.TreasureDebrisCompose": self._rpc_treasure_compose,
            "EliteBattle.GetBattleInfo": self._rpc_elite_get_battle_info,
            "EliteBattle.GetFightInfo": self._rpc_elite_get_fight_info,
            "EliteBattle.Fight": self._rpc_elite_fight,
            "EliteBattle.DrawFirstReward": self._rpc_elite_draw_first_reward,
            "EliteBattle.BuyFightCount": self._rpc_elite_buy_fight_count,
            "LvPlan.GetLvPlanInfo": self._rpc_lv_plan_info,
            "LvPlan.OpenLvPlan": self._rpc_lv_plan_open,
            "LvPlan.ReceiveLvPlan": self._rpc_lv_plan_receive,
            "VipWelfare.GetVipWelfare": self._rpc_vip_welfare_info,
            "VipWelfare.DrawVipWelfare": self._rpc_vip_welfare_draw,
            "PlayerCharge.GetChargeList": self._rpc_player_charge_list,
            "PlayerCharge.ChargeInfo": self._rpc_player_charge_info,
            "PlayerCharge.DrawChargeBox": self._rpc_player_charge_draw_box,
            "PlayerCharge.GenerateOrderID": self._rpc_player_charge_generate_order,
            "PlayerCharge.ConfirmOrder": self._rpc_player_charge_confirm_order,
            "CardInfo.GetInfo": self._rpc_card_info,
            "CardInfo.GenerateOrderID": self._rpc_card_generate_order,
            "CardInfo.Activity": self._rpc_card_activity,
            "CardInfo.DrawDailyReward": self._rpc_card_draw_daily,
            "CardInfo.DrawBuyReward": self._rpc_card_draw_buy,
            "BossBattle.GetBossList": self._rpc_boss_get_boss_list,
            "BossBattle.GetBossInfo": self._rpc_boss_get_boss_info,
            "BossBattle.GetFightInfo": self._rpc_boss_get_fight_info,
            "BossBattle.Fight": self._rpc_boss_fight,
            "BossBattle.BoxList": self._rpc_boss_box_list,
            "BossBattle.DrawBox": self._rpc_boss_draw_box,
            "BossBattle.OneKeyDrawBox": self._rpc_boss_one_key_draw_box,
            "BossBattle.BuyCount": self._rpc_boss_buy_count,
            "BossBattle.FriendHelp": self._rpc_boss_friend_help,
            "BossBattle.JiFenRanking": self._rpc_boss_jifen_ranking,
            "BossBattle.ExchangeInfo": lambda _d: [],
            "BossBattle.Exchange": lambda _d: {},
            "PVP.GetPVPInfo": self._rpc_pvp_get_info,
            "PVP.Refresh": self._rpc_pvp_refresh,
            "PVP.PVPFight": self._rpc_pvp_fight,
            "PVP.GetPVPTopRankList": self._rpc_pvp_top_rank_list,
            "LeaderBoard.RankList": self._rpc_leaderboard_rank_list,
            "LeaderBoard.Praise": self._rpc_leaderboard_praise,
            "LeaderBoard.Formation": self._rpc_leaderboard_formation,
            "PVPinter.GetPVPInterTopRank": self._rpc_pvpinter_top_rank,
            "PVPinter.GetSlotFormations": self._rpc_pvpinter_slot_formations,
            "PVPShop.PVPShopBuy": self._rpc_pvp_shop_buy,
            "PVPShop.ResetDaily": self._rpc_pvp_shop_reset_daily,
            "Daydayfund.GetInfo": self._rpc_daydayfund_get_info,
            "Daydayfund.Invest": self._rpc_daydayfund_invest,
            "Daydayfund.Harvest": self._rpc_daydayfund_harvest,
            "StartWorkReward.GetStartworkRewardInfo": self._rpc_startwork_get_info,
            "StartWorkReward.GetStartworkReward": self._rpc_startwork_get_reward,
            "Fashion.DressUp": self._rpc_fashion_dress_up,
            "Fashion.StepUp": self._rpc_fashion_step_up,
            "Fashion.Resolve": self._rpc_fashion_resolve,
            "MonthSignInfo.GetInfo": self._rpc_month_sign_get_info,
            "MonthSignInfo.DrawReward": self._rpc_month_sign_draw_reward,
            "Notice.GetNoticeList": lambda _d: [],
            "Enemy.GetEnemyList": self._rpc_enemy_get_list,
            "Enemy.AddEnemy": self._rpc_enemy_add,
            "Enemy.DeleteEnemy": self._rpc_enemy_delete,
            "Friend.GetFriendList": self._rpc_friend_get_list,
            "Friend.GetRecommendFriendList": self._rpc_friend_get_recommend,
            "Friend.PlayerSearch": self._rpc_friend_search,
            "Friend.DeleteFriend": self._rpc_friend_delete,
            "Friend.FriendApplyResponse": self._rpc_friend_apply_response,
            "FriendMessage.SendFriendSTA": self._rpc_friend_send_sta,
            "FriendMessage.BatchSendFriendSTA": self._rpc_friend_batch_send_sta,
            "FriendMessage.GetFriendSTAMessages": self._rpc_friend_get_sta_messages,
            "FriendMessage.ReceiveFriendSTA": self._rpc_friend_receive_sta,
            "FriendMessage.BatchReceiveAndSendSTA": self._rpc_friend_batch_receive_and_send_sta,
            "FriendMessage.FriendApply": self._rpc_friend_apply,
            "FriendMessage.BatchFriendApply": self._rpc_friend_batch_apply,
            "FriendMessage.SendFriendMessage": self._rpc_friend_send_message,
            "FriendMessage.GetFriendMessageByPage": self._rpc_friend_get_messages_by_page,
            "PlayerEmail.GetEmailsByPage": self._rpc_email_get_by_page,
            "PlayerEmail.DeleteEmail": self._rpc_email_delete,
            "TraderInfo.GetInfo": self._rpc_trader_get_info,
            "TraderInfo.RefreshtGoodsList": self._rpc_trader_refresh,
            "TraderInfo.BuyGoods": self._rpc_trader_buy_goods,
            "OnlineReward.OnlineRewardInfo": self._rpc_online_reward_info,
            "OnlineReward.DrawOnlineReward": self._rpc_online_reward_draw,
            "YiYuan.GetInfo": self._rpc_yiyuan_get_info,
            "YiYuan.Join": self._rpc_yiyuan_join,
            "YiYuan.DrawReward": self._rpc_yiyuan_draw_reward,
            "TeambattleInfo.GetInviteInfo": self._rpc_teambattle_get_invite_info,
            "TeambattleInfo.UpdateAllInviteFlag": self._rpc_teambattle_update_all_invite_flag,
            "TeambattleInfo.CreatTeams": self._rpc_teambattle_creat_teams,
            "TeambattleInfo.FightForMatch": self._rpc_teambattle_fight_for_match,
            "TeambattleInfo.GetMyTeamInfo": self._rpc_teambattle_get_my_team_info,
            "TeambattleInfo.GetFriendsOrGuildMembers": self._rpc_teambattle_get_friends_or_guild,
            "TeambattleInfo.InviteFriends": self._rpc_teambattle_invite_friends,
            "TeambattleInfo.InviteFriendsForOneKey": self._rpc_teambattle_invite_one_key,
            "TeambattleInfo.InviteAll": self._rpc_teambattle_invite_all,
            "TeambattleInfo.KickOutTeam": self._rpc_teambattle_kick_out_team,
            "TeambattleInfo.DismissTeam": self._rpc_teambattle_dismiss_team,
            "TeambattleInfo.ExitTeam": self._rpc_teambattle_dismiss_team,
            "TeambattleInfo.InterTeam": self._rpc_teambattle_inter_team,
            "TeambattleInfo.Fight": self._rpc_teambattle_fight,
            "TeambattleFightinfo.GetInfo": self._rpc_teambattle_get_info,
            "TeambattleFightinfo.DrawFirstReward": self._rpc_teambattle_draw_first_reward,
            "TeambattleHoldinfo.HeroHold": self._rpc_teambattle_hero_hold,
            "TeambattleHoldinfo.GetHoldInfo": self._rpc_teambattle_get_hold_info,
            "TeambattleHoldinfo.DrawHoldReward": self._rpc_teambattle_draw_hold_reward,
            "TeambattleHoldinfo.QuickDrawHoldReward": self._rpc_teambattle_quick_draw_hold_reward,
            "TeambattleShopinfo.ShopInfo": self._rpc_teambattle_shop_info,
            "TeambattleShopinfo.BuyShop": self._rpc_teambattle_buy_shop,
            "GiftLogin.SignInfo": self._rpc_gift_login_info,
            "GiftLogin.DrawGiftBox": self._rpc_gift_login_draw,
            "GiftLv.LvGiftBags": self._rpc_gift_lv_bags,
            "GiftLv.DrawGiftBags": self._rpc_gift_lv_draw,
            "Glory.GetGloryData": self._rpc_glory_get_data,
            "Glory.GloryLvUp": self._rpc_glory_lv_up,
            "Glory.GloryLvUpForOneKey": self._rpc_glory_lv_up_one_key,
            "MysteryShop.GetInfo": self._rpc_mystery_shop_get_info,
            "MysteryShop.RefreshtGoodsList": self._rpc_mystery_shop_refresh,
            "MysteryShop.MysteryShopBuyGoods": self._rpc_mystery_shop_buy,
            "MysteryShop.SeniorGetInfo": self._rpc_mystery_shop_senior_get_info,
            "MysteryShop.SeniorRefreshtGoodsList": self._rpc_mystery_shop_senior_refresh,
            "MysteryShop.SeniorMysteryShopBuyGoods": self._rpc_mystery_shop_senior_buy,
            "MysteryShop.ResetDaily": self._rpc_mystery_shop_reset_daily,
            "SuccessTargetInfo.GetInfo": self._rpc_success_target_get_info,
            "SuccessTargetInfo.DrawReward": self._rpc_success_target_draw_reward,
            "SuccessTargetInfo.DrawTotalReward": self._rpc_success_target_draw_total_reward,
            "SuccessTargetInfo.GetExchangeInfo": self._rpc_success_target_get_exchange_info,
            "SuccessTargetInfo.Exchange": self._rpc_success_target_exchange,
            "Reward.Rewars": self._rpc_reward_rewars,
            "Reward.DrawGiftBags": self._rpc_reward_draw_gift_bags,
            "PlayerVIT.ReceiveVIT": self._rpc_player_vit_receive_vit,
            "DailyTaskInfo.GetDaliyTaskInfo": self._rpc_daily_task_get_info,
            "DailyTaskInfo.GetCredit": self._rpc_daily_task_get_credit,
            "DailyTaskInfo.DrawReward": self._rpc_daily_task_draw_reward,
            "DailyTaskInfo.OneKeyDone": self._rpc_daily_task_one_key_done,
            "DailyTaskInfo.OneKeyAllDone": self._rpc_daily_task_one_key_all_done,
            "TimedRecruitInfo.GetTimedRecruitInfo": self._rpc_timed_recruit_get_info,
            "TimedRecruitInfo.SelectBanner": self._rpc_timed_recruit_select_banner,
            "TimedRecruitInfo.Recruit": self._rpc_timed_recruit_pull,
            "TimedRecruitInfo.DrawCreditReward": self._rpc_timed_recruit_draw_credit,
            "TimedRecruitInfo.DrawGoldHero": self._rpc_timed_recruit_draw_gold_hero,
            "Xxbz.GetInfo": self._rpc_xxbz_get_info,
            "Xxbz.GetFightInfo": self._rpc_xxbz_get_fight_info,
            "Xxbz.Fight": self._rpc_xxbz_fight,
            "Xxbz.DrawReward": self._rpc_xxbz_draw_reward,
            "XxbzInfo.BuyCount": self._rpc_xxbz_buy_count,
            "Zcsf.ZcsfInfo": self._rpc_zcsf_info,
            "Zcsf.ZC": self._rpc_zcsf_zc,
            "Xhzw.GetXhzwInfo": self._rpc_xhzw_get_info,
            "Xhzw.XhzwTurn": self._rpc_xhzw_turn,
            "Xhzw.XhzwAlterLuck": self._rpc_xhzw_alter_luck,
            "Xhzw.XhzwAlterLuckLock": self._rpc_xhzw_alter_luck_lock,
            "Xhzw.RefreshXhzwRewardList": self._rpc_xhzw_refresh_reward_list,
            "Xhzw.ReceiveRewardForOneKey": self._rpc_xhzw_receive_reward_for_one_key,
            "Limitthebounty.GetInfo": self._rpc_limitthebounty_get_info,
            "Limitthebounty.ReceivedReward": self._rpc_limitthebounty_received_reward,
            "TimedMoneyTree.GetInfo": self._rpc_timed_money_tree_get_info,
            "TimedMoneyTree.ShakeTree": self._rpc_timed_money_tree_shake,
            "TimedMoneyTree.DrawReward": self._rpc_timed_money_tree_draw_reward,
            "TimedHopetreeInfo.GetInfo": self._rpc_timed_hopetree_get_info,
            "TimedHopetreeInfo.DrawReward": self._rpc_timed_hopetree_draw_reward,
            "TimedSmashingeggsInfo.GetRewardList": self._rpc_timed_smash_egg_get_reward_list,
            "TimedSmashingeggsInfo.GetSmashingRecord": self._rpc_timed_smash_egg_get_record,
            "TimedSmashingeggsInfo.SmashingEggs": self._rpc_timed_smash_egg_smash,
            "TimedLuckdrawInfo.GetInfo": self._rpc_timed_luckdraw_get_info,
            "TimedLuckdrawInfo.Luckdraw": self._rpc_timed_luckdraw_draw,
            "TimedXssbInfo.GetInfo": self._rpc_timed_xssb_get_info,
            "TimedXssbInfo.CallEquip": self._rpc_timed_xssb_call_equip,
            "TimedXssbInfo.ReceiveReward": self._rpc_timed_xssb_receive_reward,
            "Timespike.GetInfo": self._rpc_timespike_get_info,
            "Timespike.ReceivedReward": self._rpc_timespike_received_reward,
            "TimesMiaosha.GetInfo": self._rpc_times_miaosha_get_info,
            "TimesMiaosha.Receive": self._rpc_times_miaosha_receive,
            "TimedInfo.GetChargeSingleInfo": self._rpc_timed_info_get_charge_single,
            "TimedInfo.DrawSingleChargeReward": self._rpc_timed_info_draw_charge_single,
            "TimedInfo.GetChargeTotalInfo": self._rpc_timed_info_get_charge_total,
            "TimedInfo.DrawChargeTotalReward": self._rpc_timed_info_draw_charge_total,
            "TimedInfo.GetUseTotalInfo": self._rpc_timed_info_get_use_total,
            "TimedInfo.DrawUseTotalReward": self._rpc_timed_info_draw_use_total,
            "TimedInfo.GetChargeDaysInfo": self._rpc_timed_info_get_charge_days,
            "TimedInfo.DrawChargeDaysReward": self._rpc_timed_info_draw_charge_days,
            "TimedInfo.GetDoubleDiamondInfo": self._rpc_timed_info_get_double_diamond,
            "TimedInfo.DrawDoubleDiamondReward": self._rpc_timed_info_draw_double_diamond,
            "TimedInfo.GetAcumulateDaysRewardInfo": self._rpc_timed_info_get_accumulate_login,
            "TimedInfo.DrawAcumulateDaysReward": self._rpc_timed_info_draw_accumulate_login,
            "TimedInfo.GetChargeRankInfo": self._rpc_timed_info_get_charge_rank,
            "TimedInfo.GetUseDiamondRankInfo": self._rpc_timed_info_get_use_rank,
            "TimedChargeGift.GetChargeGiftInfo": self._rpc_timed_charge_gift_get_info,
            "TimedChargeGift.ReceiveChargeGift": self._rpc_timed_charge_gift_receive,
            "TimedChargeScore.GetRewardList": self._rpc_timed_charge_score_get_list,
            "TimedChargeScore.BuyGoods": self._rpc_timed_charge_score_buy,
            "TimedLimitExchange.GetInfo": self._rpc_timed_limit_exchange_get_info,
            "TimedLimitExchange.Exchange": self._rpc_timed_limit_exchange_exchange,
            "TimedScoreRank.GetInfo": self._rpc_timed_score_rank_get_info,
            "TimedScoreRank.GetReward": self._rpc_timed_score_rank_get_reward,
            "TimedCriticalInfo.Info": self._rpc_timed_critical_info,
            "TimedCriticalInfo.Reward": self._rpc_timed_critical_reward,
            "GlobalOpencontestRank.GetActiveRank": self._rpc_opencontest_get_active_rank,
            "GlobalOpencontestRank.GetRank": self._rpc_opencontest_get_rank,
            "GlobalOpencontestRank.DrawReward": self._rpc_opencontest_draw_reward,
            "EarlytaskFinishRecord.GetEarlytaskList": self._rpc_earlytask_get_list,
            "EarlytaskFinishRecord.DrawEarlytaskGift": self._rpc_earlytask_draw_gift,
            "Swdiamonds.GetSwdiamondInfo": self._rpc_swdiamonds_get_info,
            "Swdiamonds.GetSwdiamondReward": self._rpc_swdiamonds_get_reward,
            "RandomRedBag.GetRandomRedBagInfo": self._rpc_random_red_bag_get_info,
            "RandomRedBag.ReceiveRandomRedBag": self._rpc_random_red_bag_receive,
            "ActiveGift.ActiveGift": self._rpc_active_gift_redeem,
            "ShareInvite.GetShareReward": self._rpc_share_invite_get_share_reward,
            "GGZJ.GetGGZJInfo": self._rpc_ggzj_get_info,
            "GGZJ.FormationChang": self._rpc_ggzj_formation_change,
            "GGZJ.Hire": self._rpc_ggzj_hire,
            "GGZJ.RefreshGGZJNPC": self._rpc_ggzj_refresh_npc,
            "GGZJ.GetFightBeforeInfo": self._rpc_ggzj_get_fight_before_info,
            "GGZJ.Fight": self._rpc_ggzj_fight,
            "GGZJ.ReceiveBoxRewards": self._rpc_ggzj_receive_box_rewards,
            "GGZJ.ReceiveClearanceRewards": self._rpc_ggzj_receive_clearance_rewards,
            "Gddh.SignupInfo": self._rpc_gddh_signup_info,
            "Gddh.ApplyGroup": self._rpc_gddh_apply_group,
            "Gddh.GetWrestleRaceInfo": self._rpc_gddh_get_info,
            "Gddh.RefreshWrestleRaceRankList": self._rpc_gddh_refresh_rank_list,
            "Gddh.RankWrestleRace": self._rpc_gddh_rank_fight,
            "Gddh.BuyRankCount": self._rpc_gddh_buy_rank_count,
            "Gddh.ReceiveReward": self._rpc_gddh_receive_reward,
            "Gddh.GetWrestleRaceReviveList": self._rpc_gddh_get_revive_list,
            "GddhShop.GetWrestleRaceShopInfo": self._rpc_gddh_shop_info,
            "GddhShop.WrestleRaceShopBuy": self._rpc_gddh_shop_buy,
            "Guild.CreateGuild": self._rpc_guild_create,
            "Guild.GetGuildInfo": self._rpc_guild_get_info,
            "Guild.GetApplyGuildInfo": self._rpc_guild_get_apply_info,
            "Guild.GetApplyGuildInfoForNotFull": self._rpc_guild_get_apply_not_full,
            "Guild.GuildQuery": self._rpc_guild_query,
            "Guild.GetGuildRankListForWeek": self._rpc_guild_get_rank_week,
            "Guild.GuildApply": self._rpc_guild_apply,
            "Guild.GuildCancelApply": self._rpc_guild_cancel_apply,
            "Guild.GetApplyList": self._rpc_guild_get_apply_list,
            "Guild.ManageApply": self._rpc_guild_manage_apply,
            "Guild.AlterAutoApply": self._rpc_guild_alter_auto_apply,
            "Guild.AlterFapLimit": self._rpc_guild_alter_fap_limit,
            "Guild.UpdateNotice": self._rpc_guild_update_notice,
            "Guild.UpdateDeclaration": self._rpc_guild_update_declaration,
            "Guild.GetGuildMembers": self._rpc_guild_get_members,
            "Guild.PostChange": self._rpc_guild_post_change,
            "Guild.PostAlter": self._rpc_guild_post_alter,
            "Guild.PostAssignment": self._rpc_guild_post_assignment,
            "Guild.KickOutGuild": self._rpc_guild_kick_out,
            "Guild.ExitGuild": self._rpc_guild_exit,
            "Guild.DismissGuild": self._rpc_guild_dismiss,
            "Guild.GuildImpeach": self._rpc_guild_impeach,
            "Guild.GuildBuild": self._rpc_guild_build,
            "Guild.GetGuildBuildLog": self._rpc_guild_get_build_log,
            "Guild.GuildContribute": self._rpc_guild_contribute,
            "Guild.GuildBuildingLvUp": self._rpc_guild_building_lv_up,
            "Guild.GetGuildShopBuyList": self._rpc_guild_shop_buy_list,
            "Guild.GuildShopBuy": self._rpc_guild_shop_buy,
            "Guild.ResetGuildShopDaily": self._rpc_guild_shop_reset_daily,
            "Guild.GetGuildShare": self._rpc_guild_get_share,
            "Guild.GuildShare": self._rpc_guild_share,
            "GuildBossInfo.GetGuildBoss": self._rpc_guild_boss_get,
            "GuildBossInfo.GetRankList": self._rpc_guild_boss_rank_list,
            "GuildBossInfo.Inspire": self._rpc_guild_boss_inspire,
            "GuildBossInfo.GetFightInfo": self._rpc_guild_boss_get_fight_info,
            "GuildBossInfo.Fight": self._rpc_guild_boss_fight,
            "GuildBossInfo.ResetFightCount": self._rpc_guild_boss_reset_count,
            "GuildReward.Rewars": self._rpc_guild_reward_list,
            "GuildReward.DrawGiftBags": self._rpc_guild_reward_draw,
            "Account.List": self._rpc_account_list,
            "Account.Switch": self._rpc_account_switch,
            "Account.Create": self._rpc_account_create,
            "Account.Export": self._rpc_account_export,
            "Account.Import": self._rpc_account_import,
        }
        fn = handlers.get(key)
        handled = fn is not None
        self._sync_events()
        before_diamond = int(self.state.get("player", {}).get("Diamond", 0))
        with self.ledger.capture_diamond_debits() as diamond_debits:
            value = fn(data) if fn else {}
        status = int(self._last_rpc_context.get("status", 0))
        if status == 0 and not self._last_rpc_context.get("spend_recorded"):
            actual_cost = max(diamond_debits.get(str(self.state["player"]["PlayerId"]), 0),
                              self._last_rpc_context.get("diamond_spent", 0))
            if actual_cost:
                self._record_period_economy(spent=actual_cost)
            dia_spent = self._last_rpc_context.get(
                "diamond_spent", before_diamond - int(self.state.get("player", {}).get("Diamond", 0)),
            )
            if dia_spent > 0 and key not in ("DailyTaskInfo.OneKeyDone", "DailyTaskInfo.OneKeyAllDone"):
                self._inc_stat("spent_diamonds", dia_spent)
                self._record_daily_task_progress(23, dia_spent)
                self.save()
            elif dia_spent > 0 and key in ("DailyTaskInfo.OneKeyDone", "DailyTaskInfo.OneKeyAllDone"):
                self._inc_stat("spent_diamonds", dia_spent)
                self._record_daily_task_progress(23, dia_spent)
                if isinstance(value, dict) and "TasksInfo" in value:
                    value = self._build_daily_task_payload()
                self.save()
            elif actual_cost:
                self.save()
        self._sync_events()
        self._sync_player_recover_times()

        if self.persist and self.trace_path:
            with open(self.trace_path, "a", encoding="utf-8") as tf:
                tf.write(
                    f"{time.strftime('%H:%M:%S')} [{self.profile_name}] RPC {key} "
                    f"handled={handled} status={status} data={json.dumps(data, ensure_ascii=False)}\n"
                )

        timed_open = self._build_timed_activity_open_info()
        if key in {"Player.Login", "Player.Login_ForTest", "Player.NewPlayer"}:
            avatar: dict[str, Any] = {}
        elif key == "Player.GetInitData":
            avatar = {
                "TimedActivityOpenInfo": timed_open,
                "RedDotInfo": self._compute_red_dot_info(),
                "EquipArtifactInfo": copy.deepcopy(self._compute_equip_artifact_state()[0]),
            }
        else:
            avatar = {k: v for k, v in self.state["player"].items() if k != "Lv"}
            if self._last_rpc_context.get("lv_changed"):
                avatar["Lv"] = self.state["player"]["Lv"]
            if self._last_rpc_context.get("lv_changed") or self._last_rpc_context.get("explore_changed"):
                avatar["XYCurCount"] = int(self.state.get("explore", {}).get("RemainNum", 15))
            if self._last_rpc_context.get("slots_changed"):
                avatar["SlotInfo"] = self.state["slots"]
            if self._last_rpc_context.get("goods_changed") is not None:
                avatar["GoodsInfo"] = self._last_rpc_context["goods_changed"]
            if self._last_rpc_context.get("treasure_debris_changed") is not None:
                avatar["TreasureDebrisInfo"] = self._last_rpc_context["treasure_debris_changed"]
            if self._last_rpc_context.get("reborn_goods_changed") is not None:
                avatar["RebornGoodsList"] = self._last_rpc_context["reborn_goods_changed"]
                avatar["RebornnComposeStatus"] = self._compute_reborn_compose_status()
            if self._last_rpc_context.get("equip_artifacts_changed") is not None:
                avatar["EquipArtifactInfo"] = self._last_rpc_context["equip_artifacts_changed"]
            avatar["TimedActivityOpenInfo"] = timed_open
            avatar["RedDotInfo"] = self._compute_red_dot_info()

        resp: dict[str, Any] = {
            "Status": status,
            "TimeTick": self.now_ts(),
            "Avatar": avatar,
            "Value": value,
        }
        if self._last_rpc_context.get("guild_avatar"):
            resp["GuildAvatar"] = self._last_rpc_context["guild_avatar"]
        return resp

    def _rpc_login(self, _data: Any) -> dict[str, Any]:
        self._sync_events()
        self.state["player"]["LastLoginTime"] = self.now_ts()
        today = self.clock.today_str()
        gl = self.state.setdefault(
            "gift_login",
            {"login_days": 1, "last_login_date": today, "claimed": []},
        )
        if gl.get("last_login_date") != today:
            gl["login_days"] = min(7, int(gl.get("login_days", 0)) + 1)
            gl["last_login_date"] = today
        self._sync_player_recover_times()
        self._sync_limitthebounty_trigger_lv()
        self.save()
        return dict(self.state["player"])

    def _rpc_new_player(self, data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("IsNewPlayer", 1)) == 0:
            self._last_rpc_context["status"] = -1114  # Already created per RoleCreateScene.lua:349
            return {"PlayerId": self.state["player"]["PlayerId"]}

        player_name = str(data[0])[:24] if isinstance(data, list) and len(data) >= 1 else "Adventurer"
        gender = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1
        main_model_id = 12010001 if gender == 0 else 12010004

        self.state["player"]["PlayerName"] = player_name
        self.state["player"]["Gender"] = gender
        self.state["player"]["HeadImageId"] = main_model_id
        self.state["player"]["IsNewPlayer"] = 0

        if self.is_normal_gameplay:
            main_hero = self._build_hero_instance(main_model_id, lv=1, step=0)
            self.state["heroes"] = [main_hero]
            self.state["slots"][0]["HeroId"] = main_hero["Id"]
            self.state["slots"][0]["HeroModelId"] = main_model_id
            self._recalc_all_slots_and_fap()
            self.ledger.record_grant_event(
                account_id=str(self.state["player"]["PlayerId"]),
                profile=self.profile_name,
                resource_type=f"Hero:{main_model_id}",
                amount=1,
                balance_after=len(self.state["heroes"]),
                source="new_player_main_hero",
                idempotency_key=f"new_player:{self.profile_name}:{self.state['player']['PlayerId']}:main_hero",
            )

        self.save()
        return {"PlayerId": self.state["player"]["PlayerId"]}

    def _rpc_get_init_data(self, _data: Any) -> dict[str, Any]:
        if self._sync_main_hero_model():
            self._recalc_all_slots_and_fap()
            self.save()
        self._sync_events()
        self._sync_player_recover_times()
        self._sync_limitthebounty_trigger_lv()
        self.state["player"]["OpencontestState"] = 1
        self.state["player"].setdefault("ActivityPic", "")
        self.state["player"].setdefault("ActivityName", "")
        timed_open = self._build_timed_activity_open_info()
        has_44xx = any(4400 <= int(k) < 4500 for k in timed_open if str(k).isdigit())
        has_63xx = any(6300 <= int(k) < 6400 for k in timed_open if str(k).isdigit())
        has_64xx = any(6400 <= int(k) < 6500 for k in timed_open if str(k).isdigit())
        module_subs = self.game_data.get("module_subs", {})
        if module_subs:
            open_submodules = sorted(
                int(mid) for mid, item in module_subs.items() if int(item.get("ifOpen", 0)) == 1
            )
        else:
            open_submodules = [1000, 1100, 1200, 1300, 1400, 2200, 2201, 3800, 3801]
        modules = [
            {
                "SubModuleId": mid,
                "OrderNum": idx,
                "IfOpen": (
                    (1 if has_44xx else 0)
                    if mid == 4400
                    else ((1 if has_63xx else 0) if mid == 6300 else ((1 if has_64xx else 0) if mid == 6400 else 1))
                ),
            }
            for idx, mid in enumerate(open_submodules, start=1)
        ]
        # Event red dots can initialize starter goods. Include those grants in this inventory snapshot.
        red_dots = self._compute_red_dot_info()
        all_goods = self.state.get("goods", [])
        hero_debris = [g for g in all_goods if int(g.get("GoodsModelId", 0)) // 10000 == 1501]
        equip_debris = [g for g in all_goods if int(g.get("GoodsModelId", 0)) // 10000 == 1502]
        props_goods = [g for g in all_goods if int(g.get("GoodsModelId", 0)) // 10000 not in (1501, 1502)]
        return {
            "PlayerInfo": self.state["player"],
            "HeroInfo": self.state["heroes"],
            "EquipInfo": self.state.get("equips", []),
            "TreasureInfo": self.state.get("treasures", []),
            "SlotInfo": self.state["slots"],
            "MateInfo": self._mate_slot_info(),
            "SlotFormationInfo": self.state["embattle"],
            "GoodsHeroDebrisInfo": hero_debris,
            "GoodsEquipDebrisInfo": equip_debris,
            "GoodsPropsInfo": props_goods,
            "TreasureDebrisInfo": self.state.get("treasure_debris", []),
            "BagInfo": [self._bag_info(bid) for bid in range(1, 10)],
            "SkillList": [],
            "ModulesInfo": modules,
            "StarSignInfo": [],
            "XYCurCount": self._explore_snapshot()["RemainNum"],
            "FashionInfo": self.state.get("fashions", []),
            "GemInfo": self.state.get("gems", []),
            "PetInfo": [],
            "WarfarespiritInfo": [],
            "RebornGoodsList": self.state.get("reborn_goods", []),
            "RebornnComposeStatus": self._compute_reborn_compose_status(),
            "OpencontestState": 1,
            "RedDotInfo": red_dots,
        }

    def _rpc_sync_avatar(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        before = (
            p.get("VITMaxNum"),
            p.get("VITNextRecoverTime"),
            p.get("STAMaxNum"),
            p.get("STANextRecoverTime"),
        )
        self._sync_player_recover_times(p)
        old_trig = p.get("LimitthebountyTriggerLv")
        new_trig = self._sync_limitthebounty_trigger_lv()
        after = (
            p.get("VITMaxNum"),
            p.get("VITNextRecoverTime"),
            p.get("STAMaxNum"),
            p.get("STANextRecoverTime"),
        )
        if after != before or new_trig != old_trig:
            self.save()
        return {**p, "XYCurCount": self._explore_snapshot()["RemainNum"]}

    STEP_REWARD_MAP: dict[int, list[tuple[int, int, int]]] = {
        76001: [(1304, 13040130, 5)],   # 5 white necklaces if not dropped in 1-3 (BattleLayer.lua:2812)
        1641: [(1301, 13010130, 1)],    # Starter weapon (CommonFunc.lua:2885, HomeScene.lua:1893)
        1602: [(1111, 0, 200)],         # 200 Diamonds (GuideEventModel[1602])
        1625: [(1605, 16050001, 100)],  # 100 Breakthrough Stones (GuideEventModel[1625])
        1761: [(1504, 15040101, 1), (1504, 15040102, 1)],  # Lv 14 Grab mount debris (14020501)
        1881: [(1503, 15032101, 1), (1503, 15032102, 1)],  # Backup Grab book debris (14010501)
        2071: [(1201, 12013054, 5)],    # Lv 24 Guide 7: 5x Tamotu fodder heroes (DisassembleNewScene.lua:493)
        2181: [(1604, 16040009, 3)],    # Lv 22 Guide 9: 3x eDiploma / Meihaku (ShrineScene.lua:605)
        274: [(1603, 16030006, 1)],     # VIT pill Thuốc Thể Lực 2 (BattleLayer.lua:403)
        293: [(1605, 16050016, 10)],    # Guide 21: 10x Lệnh Lính Thuê (GGZJHeroHireLayer.lua:638)
        313: [],                        # Non-reward UI pointer in Guide 23 (ChallengeListLayer.lua:626)
    }

    def _rpc_alter_step_count(self, data: Any) -> dict[str, Any]:
        if isinstance(data, list) and len(data) >= 2:
            try:
                gid = int(data[0])
                ordinal = int(data[1])
            except (TypeError, ValueError):
                return {}
            if ordinal >= 0 and self._apply_step_count_update(gid, ordinal):
                self.save()
        return {}

    def _rpc_get_step_count_reward(self, data: Any) -> dict[str, Any]:
        event_id = int(data[0]) if isinstance(data, list) and data else 0
        if event_id not in self.STEP_REWARD_MAP:
            self._last_rpc_context["status"] = -1
            return {}
        claimed = self.state.setdefault("claimed_step_rewards", [])
        if event_id in claimed:
            self._last_rpc_context["status"] = -1136  # Already claimed per CommonFunc.lua:2899
            return {}

        tuples = self.STEP_REWARD_MAP[event_id]
        claimed.append(event_id)
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"step_reward:{event_id}",
            tx_prefix=f"step_reward:{self.profile_name}:{self.state['player']['PlayerId']}:{event_id}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_alter_player_head_id(self, data: Any) -> dict[str, Any]:
        """Update player avatar HeadImageId to an owned or deployed HeroModelId."""
        try:
            head_model_id = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            head_model_id = 0
        if head_model_id <= 0 or str(head_model_id) not in self.game_data.get("heroes", {}):
            self._last_rpc_context["status"] = -1
            return {}
        owned_models = {int(h.get("HeroModelId", 0)) for h in self.state.get("heroes", [])}
        owned_models.update(int(s.get("HeroModelId", 0)) for s in self.state.get("slots", []))
        if head_model_id not in owned_models:
            self._last_rpc_context["status"] = -1
            return {}
        self.state["player"]["HeadImageId"] = head_model_id
        self.save()
        return {"HeadImageId": head_model_id}

    def _rpc_alter_player_name(self, data: Any) -> dict[str, Any]:
        """Rename player using Rename Card (consume_type=2) or Diamond (consume_type=3)."""
        if not isinstance(data, list) or not data or data[0] is None:
            self._last_rpc_context["status"] = -1
            return {}
        new_name = str(data[0]).strip()
        try:
            consume_type = int(data[1]) if len(data) >= 2 else 3
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}

        pcfg = self.game_data.get("player_config", {})
        min_len = int(pcfg.get("playerNameMinLength", 2))
        max_len = int(pcfg.get("playerNameMaxLength", 32))
        player = self.state["player"]
        if (
            not new_name
            or len(new_name) < min_len
            or len(new_name) > 14
            or len(new_name.encode("utf-8")) > max_len
            or new_name == str(player.get("PlayerName", ""))
        ):
            self._last_rpc_context["status"] = -1
            return {}

        if consume_type == 2:
            if not self._consume_goods(16050002, 1):
                self._last_rpc_context["status"] = -1
                return {}
        elif consume_type == 3:
            cost = int(pcfg.get("alterNameSpendDiamond", 100))
            if int(player.get("Diamond", 0)) < cost:
                self._last_rpc_context["status"] = -1105
                return {}
            self.ledger.apply_player_delta(
                player,
                self.profile_name,
                "Diamond",
                -cost,
                source="alter_player_name",
            )
            self._last_rpc_context["diamond_spent"] = cost
        else:
            self._last_rpc_context["status"] = -1
            return {}

        player["PlayerName"] = new_name
        self.save()
        return {"PlayerName": new_name}

    def _rpc_player_get_player_info(self, data: Any) -> dict[str, Any]:
        """Lookup active S1 player or social NPC summary by exact name or PlayerId (ChatLayer private chat)."""
        query = str(data[0]).strip() if isinstance(data, list) and data and data[0] is not None else ""
        if not query:
            self._last_rpc_context["status"] = -3003
            return {}

        def _format_summary(
            *,
            pid: str,
            pname: str,
            fap: int,
            lv: int,
            head_id: int,
            fashion_id: int,
            vip: int,
            guild_name: str,
        ) -> dict[str, Any]:
            quality = int(self.game_data.get("heroes", {}).get(str(head_id), {}).get("quality", 13))
            return {
                "PlayerId": pid,
                "PlayerName": pname,
                "FAP": int(fap),
                "LV": int(lv),
                "Lv": int(lv),
                "HeadImageId": int(head_id),
                "FashionModelId": int(fashion_id),
                "Vip": int(vip),
                "Quality": quality,
                "PVPInterLv": 0,
                "GuildName": guild_name,
            }

        q_lower = query.lower()
        for prof in [self] + self._get_peer_s1_profiles():
            pp = prof.state.get("player", {})
            if prof is not self and int(pp.get("IsNewPlayer", 0)) != 0:
                continue
            pid = str(pp.get("PlayerId", ""))
            pname = str(pp.get("PlayerName", "") or "")
            if pid == query or pname.lower() == q_lower:
                head_id = self._valid_hero_head_id(int(pp.get("HeadImageId", 0)), prof.state.get("slots", []))
                return _format_summary(
                    pid=pid,
                    pname=pname,
                    fap=int(pp.get("FAP", 0)),
                    lv=int(pp.get("Lv", 1)),
                    head_id=head_id,
                    fashion_id=int(pp.get("FashionModelId", 0)),
                    vip=int(pp.get("Vip", 0)),
                    guild_name=str(pp.get("GuildName", "") or ""),
                )

        from social_handlers import FRIEND_NPC_COUNT, _FRIEND_NPC_NAMES

        for idx in range(1, FRIEND_NPC_COUNT + 1):
            npc_pid = _det_uuid(f"friend_npc:{idx}")
            npc_name = _FRIEND_NPC_NAMES[(idx - 1) % len(_FRIEND_NPC_NAMES)]
            if npc_pid == query or npc_name.lower() == q_lower:
                npc = self._social_npc_profile(idx)
                return _format_summary(
                    pid=str(npc["PlayerId"]),
                    pname=str(npc["Name"]),
                    fap=int(npc["FAP"]),
                    lv=int(npc["Lv"]),
                    head_id=int(npc["HeadImageId"]),
                    fashion_id=int(npc.get("FashionModelId", 0)),
                    vip=2,
                    guild_name="",
                )

        self._last_rpc_context["status"] = -3003
        return {}

    def _inc_stat(self, key: str, delta: int = 1) -> int:
        stats = self.state.setdefault("stats", dict(DEFAULT_PLAYER_STATS))
        stats[key] = int(stats.get(key, 0)) + int(delta)
        return int(stats[key])

    def _reject_resource_change(self, status: int) -> dict[str, Any]:
        self._last_rpc_context["status"] = status
        return {}

    def _commit_resource_change(self, apply: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Commit the save before publishing ledger entries."""
        before = copy.deepcopy(self.state)
        context = self._last_rpc_context.copy()
        ledger = self.ledger
        staged = ResourceLedger(vip_model=ledger.vip_model)
        self.ledger = staged
        try:
            result = apply()
            self.save()
        except Exception as exc:
            self.state.clear()
            self.state.update(before)
            self._last_rpc_context = context
            if not isinstance(exc, OSError):
                raise
            logging.exception("Could not save resource transaction")
            return self._reject_resource_change(-7)
        finally:
            self.ledger = ledger
        try:
            for entry in staged.list_transactions():
                ledger.record_grant_event(**{key: entry[key] for key in (
                    "account_id", "profile", "resource_type", "amount", "balance_after",
                    "source", "idempotency_key", "actor", "metadata",
                )})
        except OSError:
            logging.exception("Could not audit committed resource transaction")
        return result

    def _consume_goods(self, goods_model_id: int, count: int) -> bool:
        """Atomically verify and deduct count units of goods_model_id from bag."""
        if count <= 0:
            return True
        item = next(
            (g for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == goods_model_id),
            None,
        )
        if not item or int(item.get("Num", 0)) < count:
            return False
        item["Num"] = int(item["Num"]) - count
        if item["Num"] <= 0:
            self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != item["Id"]]
        self._mark_goods_changed(goods_model_id)
        return True

    def _bag_info(self, bag_id: int) -> dict[str, int]:
        # Saves store purchases only. Derive Size for old and new accounts alike.
        bm = self.game_data.get("bag_model", {}).get(str(bag_id), {})
        base = max(300 if bag_id == 5 else 200, int(bm.get("initSize", 0)))
        per_expand = max(1, int(bm.get("perExpandSize", 5)))
        expanded = int(self.state.get("bag_expansions", {}).get(str(bag_id), 0))
        return {"BagModelId": bag_id, "Size": base + per_expand * expanded, "ExpandNum": expanded}

    def _rpc_bag_expand(self, data: Any) -> dict[str, Any]:
        bag_id = int(data[0]) if isinstance(data, list) and data else 0
        if bag_id not in range(1, 9):  # BagModel.items in the VN client
            self._last_rpc_context["status"] = -1
            return {}
        expansion = self._bag_info(bag_id)["ExpandNum"] + 1
        expand_tbl = self.game_data.get("bag_expand_use", {})
        max_expand = max((int(k) for k in expand_tbl), default=20)
        if expansion > max_expand:
            self._last_rpc_context["status"] = -1
            return {}
        cost = int(expand_tbl.get(str(expansion), {}).get("useDiamondNum", 10 * expansion))
        if int(self.state["player"].get("Diamond", 0)) < cost:
            self._last_rpc_context["status"] = -1105
            return {}
        self.ledger.apply_player_delta(self.state["player"], self.profile_name, "Diamond", -cost, source=f"bag_expand:{bag_id}")
        self.state.setdefault("bag_expansions", {})[str(bag_id)] = expansion
        self.save()
        return self._bag_info(bag_id)

    def _check_hero_capacity(self, incoming: int) -> bool:
        if incoming <= 0:
            return True
        deployed = self._deployed_hero_ids()
        used = sum(str(hero["Id"]) not in deployed for hero in self.state["heroes"])
        if used + incoming > self._bag_info(5)["Size"]:
            self._last_rpc_context["status"] = -2005  # VN ServerMessage: hero bag full
            return False
        return True

    def _can_receive_goods_outputs(self, rewards: list[tuple[int, int, int]]) -> bool:
        if any(not self._is_valid_resource(rtype, model) for rtype, model, count in rewards if count > 0):
            self._last_rpc_context["status"] = -2009  # Standalone client: unsupported reward, item kept.
            return False
        return self._check_hero_capacity(sum(count for rtype, _, count in rewards if rtype == 1201))

    def _rpc_recruit_info(self, _data: Any) -> dict[str, Any]:
        now = self.now_ts()
        rs = self.state.setdefault(
            "recruit_state",
            {"MidAlreadyUseResource": False, "HigAlreadyUseResource": False, "OutZiCount": 9, "history": []},
        )
        return {
            "OutZiCount": int(rs.get("OutZiCount", 9)),
            "CooledInfo": [
                {"Type": 2, "CooledTime": int(rs.get("GoodReadyAt", now))},
                {"Type": 3, "CooledTime": int(rs.get("ExcellentReadyAt", now))},
            ],
            "MidAlreadyUseResource": bool(rs.get("MidAlreadyUseResource", False)),
            "HigAlreadyUseResource": bool(rs.get("HigAlreadyUseResource", False)),
        }

    def _pick_recruit_hero(
        self,
        banner_id: int,
        pool_ids: list[int],
        force_quality: int | None = None,
    ) -> int:
        """Select a hero from banner pool using configured quality tier weights (no uniform UR/flat random)."""
        heroes_cfg = self.game_data.get("heroes", {})
        by_quality: dict[int, list[int]] = {}
        for hid in pool_ids:
            h_cfg = heroes_cfg.get(str(hid))
            if not h_cfg:
                continue
            q = int(h_cfg.get("quality", 10))
            if q >= 18:
                continue  # UR heroes are exclusive to TimedRecruit / UR Choice chests
            by_quality.setdefault(q, []).append(hid)
        if not by_quality:
            return 12011014
        if force_quality is not None:
            bucket = by_quality.get(force_quality) or by_quality[max(by_quality)]
            return random.choice(bucket)
        weights_cfg = RECRUIT_RATE_CONFIG.get(banner_id, RECRUIT_RATE_CONFIG[2])
        avail_tiers = sorted(by_quality)
        tier_weights = [max(1, int(weights_cfg.get(q, 100))) for q in avail_tiers]
        chosen_q = random.choices(avail_tiers, weights=tier_weights, k=1)[0]
        return random.choice(by_quality[chosen_q])

    def _rpc_recruit(self, data: Any) -> dict[str, Any]:
        rtype = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 2
        is_free = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1
        if rtype not in (1, 10, 2, 3, 30, 40) or is_free not in (0, 1):
            self._last_rpc_context["status"] = -1
            return {}
        count = 10 if rtype in (10, 30, 40) else 1
        if not self._check_hero_capacity(count):
            return {}

        now = self.now_ts()
        rs = self.state.setdefault(
            "recruit_state",
            {"MidAlreadyUseResource": False, "HigAlreadyUseResource": False, "OutZiCount": 9, "history": []},
        )
        recruit_tbl = self.game_data.get("hero_recruit", {})
        cfg_key = "30" if rtype == 40 and "40" not in recruit_tbl else str(rtype)
        rec_cfg = recruit_tbl.get(cfg_key, {})
        base_banner = 1 if rtype in (1, 10) else (2 if rtype == 2 else 3)
        fallback_all = recruit_tbl.get(str(base_banner), {}).get("outShowAll", "12011014")
        pool_all = [int(x) for x in str(rec_cfg.get("outShowAll") or fallback_all).split(",") if x.strip().isdigit()]
        pool_main = [int(x) for x in str(rec_cfg.get("outShowMain") or "").split(",") if x.strip().isdigit()]

        # Validate & deduct banner resource or free-recruit cooldown
        if rtype in (1, 10):
            reqs = _parse_resource_str(str(rec_cfg.get("recruitUse", f"1605,16050003,{10 if rtype == 10 else 1}")))
            _, rm, rn = reqs[0] if reqs else (1605, 16050003, 10 if rtype == 10 else 1)
            if not self._consume_goods(rm, rn):
                self._last_rpc_context["status"] = -1
                return {}
        elif rtype == 40:
            if not self._consume_goods(16050056, 1):
                self._last_rpc_context["status"] = -1
                return {}
        elif rtype in (2, 3) and is_free == 1:
            if rtype == 2 and rs.get("MidAlreadyUseResource", False) and now < int(rs.get("GoodReadyAt", 0)):
                self._last_rpc_context["status"] = -1
                return {}
            if rtype == 3 and rs.get("HigAlreadyUseResource", False) and now < int(rs.get("ExcellentReadyAt", 0)):
                self._last_rpc_context["status"] = -1
                return {}
        elif rtype in (2, 3, 30) and is_free == 0:
            reqs = _parse_resource_str(str(rec_cfg.get("recruitUse", "")))
            default_cost = 280 if rtype == 3 else (2680 if rtype == 30 else 80)
            cost = int(reqs[0][2]) if reqs and reqs[0][0] == 1111 else default_cost
            welfare = self.event_runtime.get_active_timed_events(4417, self.state["player"])
            if welfare:
                percent = int(welfare[0][0].metadata.get("extra_info", {}).get("RefNum", 100))
                cost = (cost * percent + 99) // 100  # RecruitScene.lua uses math.ceil.
            if int(self.state["player"].get("Diamond", 0)) < cost:
                self._last_rpc_context["status"] = -1105
                return {}
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -cost,
                source=f"recruit:{rtype}",
            )
        else:
            self._last_rpc_context["status"] = -1
            return {}

        heroes_cfg = self.game_data.get("heroes", {})
        chosen_hids: list[int] = []
        out_zi = int(rs.get("OutZiCount", 9))

        if rtype == 2 and not rs.get("MidAlreadyUseResource", False):
            # Canonical Tutorial Guide 1: first Destiny pull always grants Ayame (12011014)
            chosen_hids.append(12011014)
        elif rtype in (1, 10, 2):
            for _ in range(count):
                chosen_hids.append(self._pick_recruit_hero(base_banner, pool_all))
        else:
            # Soul Recruit (3, 30, 40): first pull or OutZiCount <= 0 or >=1 slot in 10x guarantees q=15
            first_soul = rtype == 3 and not rs.get("HigAlreadyUseResource", False)
            hit_q15 = False
            for idx in range(count):
                force_q = 15 if ((idx == 0 and first_soul) or out_zi <= 0) else None
                src_pool = (pool_main or pool_all) if force_q == 15 else pool_all
                hid = self._pick_recruit_hero(3, src_pool, force_quality=force_q)
                hq = int(heroes_cfg.get(str(hid), {}).get("quality", 10))
                if hq >= 15:
                    hit_q15 = True
                    out_zi = 9
                else:
                    out_zi = max(0, out_zi - 1)
                chosen_hids.append(hid)
            if count == 10 and not hit_q15:
                # 10x Soul guarantees at least one q=15 Orange hero
                chosen_hids[-1] = self._pick_recruit_hero(3, pool_main or pool_all, force_quality=15)
                out_zi = 9
            rs["OutZiCount"] = out_zi

        tuples: list[tuple[int, int, int]] = [(1201, hid, 1) for hid in chosen_hids]
        extra_str = str(rec_cfg.get("extraRewards") or ("1606,16060005,10" if rtype in (30, 40) else ""))
        for rt, rm, rn in _parse_resource_str(extra_str):
            if rn > 0:
                tuples.append((rt, rm, rn))
        gold_gain = int(rec_cfg.get("goldCoin", 0) or 0)
        if gold_gain > 0:
            tuples.append((1112, 0, gold_gain))

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"recruit:{rtype}",
            tx_prefix=f"recruit:{self.profile_name}:{now}:{uuid.uuid4()}",
        )

        next_tick = now
        if rtype == 2 and (is_free == 1 or not rs.get("MidAlreadyUseResource", False)):
            cd_min = int(rec_cfg.get("freeTimeCD", 1380))
            next_tick = now + max(0, cd_min) * 60
            rs["MidAlreadyUseResource"] = True
            rs["GoodReadyAt"] = next_tick
        elif rtype == 3 and (is_free == 1 or not rs.get("HigAlreadyUseResource", False)):
            cd_min = int(rec_cfg.get("freeTimeCD", 2820))
            next_tick = now + max(0, cd_min) * 60
            rs["HigAlreadyUseResource"] = True
            rs["ExcellentReadyAt"] = next_tick
        elif rtype == 2:
            next_tick = int(rs.get("GoodReadyAt", now))
        elif rtype == 3:
            next_tick = int(rs.get("ExcellentReadyAt", now))

        hist = rs.setdefault("history", [])
        hist.append({"ts": now, "rtype": rtype, "is_free": is_free, "heroes": chosen_hids})
        if len(hist) > 50:
            rs["history"] = hist[-50:]
        self._inc_stat("total_recruits", len(chosen_hids))
        if rtype in (1, 10):
            self._inc_stat("dream_recruits", len(chosen_hids))
        elif rtype == 2:
            self._inc_stat("destiny_recruits", len(chosen_hids))
        else:
            self._inc_stat("soul_recruits", len(chosen_hids))

        self.save()
        return {
            "CooledTick": next_tick,
            "MidAlreadyUseResource": bool(rs.get("MidAlreadyUseResource", False)),
            "HigAlreadyUseResource": bool(rs.get("HigAlreadyUseResource", False)),
            "OutZiCount": int(rs.get("OutZiCount", 9)),
            "BaseGetGameResourceList": base_res,
        }

    def _callequip_state(self) -> dict[str, Any]:
        """Initialize or return persisted Callequip (3802) pity & cooldown state."""
        cfg = self.game_data.get("callequip_config", {})
        ce = self.state.setdefault("callequip", {})
        now = self.now_ts()
        pity_interval = int(cfg.get("sureOutLvFourInterval", 9))
        init_cd_sec = max(0, int(cfg.get("initFreeTimeCD", 90))) * 60
        ce.setdefault("is_first", 1)
        ce.setdefault("call_count", pity_interval)
        ce.setdefault("color_lv", 4)
        ce.setdefault("last_free_call_time", now + init_cd_sec)
        ce.setdefault("total_calls", 0)
        return ce

    def _callequip_payload(self, ce: dict[str, Any]) -> dict[str, int]:
        return {
            "IsFrist": int(ce.get("is_first", 1)),
            "CallCount": int(ce.get("call_count", 9)),
            "ColorLv": int(ce.get("color_lv", 4)),
            "LastFreeCallTime": int(ce.get("last_free_call_time", self.now_ts())),
        }

    def _roll_callequip_drop(self, min_color: int = 0) -> tuple[int, int, int]:
        odds_tbl = self.game_data.get("callequip_outodds", {})
        rows = [r for r in odds_tbl.values() if int(r.get("colorLV", 0)) >= min_color]
        if not rows:
            rows = list(odds_tbl.values())
        weights = [max(1, int(r.get("odds", 1))) for r in rows]
        picked = random.choices(rows, weights=weights, k=1)[0]
        return int(picked["typeID"]), int(picked["modelID"]), 1

    def _rpc_callequip_get_data(self, _data: Any) -> dict[str, Any]:
        ce = self._callequip_state()
        return self._callequip_payload(ce)

    def _rpc_callequip_call(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            types = int(data[0])
            consume = int(data[1])
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        if types not in (1, 10) or consume not in (1, 3) or (consume == 1 and types != 1):
            self._last_rpc_context["status"] = -1
            return {}

        ce = self._callequip_state()
        cfg = self.game_data.get("callequip_config", {})
        self._sync_events()
        now = self.now_ts()
        if consume == 1:
            if now < int(ce.get("last_free_call_time", 0)):
                self._last_rpc_context["status"] = -1
                return {}
            ce["last_free_call_time"] = now + max(0, int(cfg.get("freeTimeCD", 4260))) * 60
        else:
            price = int(cfg.get("tenTimesPrice", 1800)) if types == 10 else int(cfg.get("perPrice", 200))
            welfare = self.event_runtime.get_active_timed_events(4416, self.state["player"])
            if welfare:
                percent = int(welfare[0][0].metadata.get("extra_info", {}).get("RefNum", 100))
                price = (price * percent + 99) // 100
            if int(self.state["player"].get("Diamond", 0)) < price:
                self._last_rpc_context["status"] = -1105
                return {}
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -price,
                source=f"callequip:{types}",
            )
            self._last_rpc_context["diamond_spent"] = price

        pity_interval = int(cfg.get("sureOutLvFourInterval", 9))
        drops: list[tuple[int, int, int]] = []
        crit_active = bool(self.event_runtime.get_active_timed_events(4419, self.state["player"]))
        crit_qualities = self._timed_welfare_qualities(4419)
        equips_cfg = self.game_data.get("equips", {})
        for _ in range(types):
            if consume == 3 and int(ce.get("is_first", 0)) > 0:
                drop = self._roll_callequip_drop(min_color=5)
                ce["is_first"] = 0
            elif int(ce.get("call_count", 0)) <= 0:
                min_c = int(ce.get("color_lv", 4))
                drop = self._roll_callequip_drop(min_color=min_c)
                ce["call_count"] = pity_interval
                ce["color_lv"] = 5 if min_c == 4 else 4
            else:
                drop = self._roll_callequip_drop(min_color=0)
                ce["call_count"] = max(0, int(ce["call_count"]) - 1)
            drops.append(drop)
            if crit_active:
                eq_quality = int(equips_cfg.get(str(drop[1]), {}).get("quality", 0))
                if crit_qualities and eq_quality in crit_qualities:
                    drops.append(drop)

        ce["total_calls"] = int(ce.get("total_calls", 0)) + types
        self._inc_stat("callequip_count", types)
        base_res = self._grant_resources_from_tuples(
            drops,
            source=f"callequip:{types}:{consume}",
            tx_prefix=f"callequip:{self.profile_name}:{now}:{uuid.uuid4()}",
        )
        self.save()
        return {
            "CallEquipInfo": self._callequip_payload(ce),
            "BaseGetGameResourceList": base_res,
        }

    def _rpc_slot_hero_combat(self, data: Any) -> dict[str, Any]:
        slot_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 1
        hero_id = str(data[1]) if isinstance(data, list) and len(data) >= 2 else EMPTY_ENTITY_ID
        target_slot = next((s for s in self.state["slots"] if int(s["SlotId"]) == slot_id), None)
        if not target_slot:
            self._last_rpc_context["status"] = -1
            return {}
        if hero_id != target_slot["HeroId"] and hero_id in self._deployed_hero_ids():
            return self._reject_resource_change(-1206)

        if hero_id == EMPTY_ENTITY_ID:
            target_slot["HeroId"] = EMPTY_ENTITY_ID
            target_slot["HeroModelId"] = 0
        else:
            hero = next((h for h in self.state["heroes"] if h["Id"] == hero_id), None)
            if not hero:
                self._last_rpc_context["status"] = -1
                return {}
            target_slot["HeroId"] = hero["Id"]
            target_slot["HeroModelId"] = hero["HeroModelId"]

        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotInfo": self.state["slots"]}

    def _rpc_slot_mate_combat(self, data: Any) -> dict[str, Any]:
        if (not isinstance(data, list) or len(data) != 2
                or type(data[0]) is not int or not isinstance(data[1], str)):
            return self._reject_resource_change(-48)
        slot_id, hero_id = data
        if not self._mate_slot_unlocked(slot_id):
            return self._reject_resource_change(-1127)

        mates = self.state["mates"]
        key = str(slot_id)
        selected = {"SlotId": slot_id, "HeroId": EMPTY_ENTITY_ID, "HeroModelId": 0}
        if hero_id not in ("", EMPTY_ENTITY_ID):
            hero = next((hero for hero in self.state["heroes"] if hero["Id"] == hero_id), None)
            if not hero:
                return self._reject_resource_change(-1201)
            if mates.get(key) != hero_id and hero_id in self._deployed_hero_ids():
                return self._reject_resource_change(-1206)
            selected.update(HeroId=hero_id, HeroModelId=hero["HeroModelId"])

        def change_mate():
            if selected["HeroModelId"]:
                mates[key] = hero_id
            else:
                mates.pop(key, None)
            self._recalc_all_slots_and_fap()
            self._last_rpc_context["slots_changed"] = True
            return {"MateInfo": [selected]}

        return self._commit_resource_change(change_mate)

    def _rpc_slot_one_key_equip_combat(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 7:
            self._last_rpc_context["status"] = -1
            return {}
        slot_id = int(data[0])
        target_slot = next((s for s in self.state["slots"] if int(s["SlotId"]) == slot_id), None)
        if not target_slot:
            self._last_rpc_context["status"] = -1
            return {}

        equips_by_id = {e["Id"]: e for e in self.state.get("equips", [])}
        slot_keys = ("Weapon", "Helmet", "Clothes", "Necklace")
        for idx, skey in enumerate(slot_keys, start=1):
            eid = str(data[idx] or "")
            if eid == "":
                continue  # empty string means unchanged per MyFormationLayer.lua:1388
            if eid == EMPTY_ENTITY_ID:
                target_slot.pop(skey, None)
            elif eid in equips_by_id:
                eq = equips_by_id[eid]
                # Unequip from any other slot first
                for other in self.state["slots"]:
                    if (other.get(skey) or {}).get("Id") == eid:
                        other.pop(skey, None)
                target_slot[skey] = {
                    "Id": eq["Id"],
                    "EquipModelId": eq["EquipModelId"],
                    "Lv": eq["Lv"],
                    "Step": int(eq.get("Step", 0)),
                }

        treasures_by_id = {t["Id"]: t for t in self.state.get("treasures", [])}
        treasure_keys = ("Book", "Horse")
        for idx, tkey in enumerate(treasure_keys, start=5):
            tid = str(data[idx] or "")
            if tid == "":
                continue
            if tid == EMPTY_ENTITY_ID:
                target_slot.pop(tkey, None)
            elif tid in treasures_by_id:
                tr = treasures_by_id[tid]
                for other in self.state["slots"]:
                    if other.get(tkey, {}).get("Id") == tid:
                        other.pop(tkey, None)
                target_slot[tkey] = {
                    "Id": tr["Id"],
                    "TreasureModelId": tr["TreasureModelId"],
                    "Lv": int(tr.get("Lv", 0)),
                    "Step": int(tr.get("Step", 0)),
                }

        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotInfo": self.state["slots"]}

    def _rpc_slot_gem_combat(self, data: Any) -> dict[str, Any]:
        """Socket, swap, transfer, or unequip a gem on a formation slot (MyFormationLayer.lua:1689)."""
        if not isinstance(data, list) or len(data) < 3:
            self._last_rpc_context["status"] = -48
            return {}
        try:
            slot_id = int(data[0])
            gem_idx = int(data[1])
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -48
            return {}
        gem_id = str(data[2] or "")

        target_slot = next((s for s in self.state["slots"] if int(s["SlotId"]) == slot_id), None)
        if not target_slot or target_slot.get("HeroId") in (None, "", EMPTY_ENTITY_ID):
            self._last_rpc_context["status"] = -1
            return {}
        if not (1 <= gem_idx <= 6):
            self._last_rpc_context["status"] = -48
            return {}
        if gem_idx > self._gem_slot_max():
            self._last_rpc_context["status"] = -1127
            return {}

        gems_by_id = {g["Id"]: g for g in self.state.get("gems", [])}
        for s in self.state["slots"]:
            self._normalize_slot_gems(s, gems_by_id=gems_by_id)

        if not gem_id or gem_id == EMPTY_ENTITY_ID:
            target_slot["Gem"][gem_idx - 1] = {}
        else:
            gem = gems_by_id.get(gem_id)
            if not gem:
                self._last_rpc_context["status"] = -1301
                return {}
            gm = self.game_data.get("gem_model", {}).get(str(gem.get("ModelId", 0)))
            if not gm:
                self._last_rpc_context["status"] = -1311
                return {}
            if int(gm.get("limit", 0)) != gem_idx:
                self._last_rpc_context["status"] = -48
                return {}
            for other in self.state["slots"]:
                other_gems = other.get("Gem") or []
                for pos, cur in enumerate(other_gems):
                    if isinstance(cur, dict) and cur.get("Id") == gem_id:
                        other_gems[pos] = {}
            target_slot["Gem"][gem_idx - 1] = {"Id": gem["Id"], "ModelId": int(gem["ModelId"])}

        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotInfo": self.state["slots"]}

    def _rpc_slot_gem_one_key_combat(self, data: Any) -> dict[str, Any]:
        """Auto-socket highest-level unbattle gems into unlocked gem sockets (MyFormationLayer.lua:1656)."""
        try:
            slot_id = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -48
            return {}
        target_slot = next((s for s in self.state["slots"] if int(s["SlotId"]) == slot_id), None)
        if not target_slot or target_slot.get("HeroId") in (None, "", EMPTY_ENTITY_ID):
            self._last_rpc_context["status"] = -1
            return {}

        gems_by_id = {g["Id"]: g for g in self.state.get("gems", [])}
        battle_gem_ids: set[str] = set()
        for s in self.state["slots"]:
            for cur in self._normalize_slot_gems(s, gems_by_id=gems_by_id):
                if cur.get("Id"):
                    battle_gem_ids.add(cur["Id"])

        gem_models = self.game_data.get("gem_model", {})
        max_open = self._gem_slot_max()
        for gem_idx in range(1, max_open + 1):
            cur = target_slot["Gem"][gem_idx - 1]
            cur_lv = int(gem_models.get(str(cur.get("ModelId", 0)), {}).get("LV", 0)) if cur.get("Id") else 0
            best_gem: dict[str, Any] | None = None
            best_lv = cur_lv
            for g in self.state.get("gems", []):
                gid = g.get("Id", "")
                if not gid or gid in battle_gem_ids:
                    continue
                gm = gem_models.get(str(g.get("ModelId", 0)))
                if not gm or int(gm.get("limit", 0)) != gem_idx:
                    continue
                glv = int(gm.get("LV", 0))
                if glv > best_lv:
                    best_lv = glv
                    best_gem = g
            if best_gem is not None:
                if cur.get("Id"):
                    battle_gem_ids.discard(cur["Id"])
                target_slot["Gem"][gem_idx - 1] = {"Id": best_gem["Id"], "ModelId": int(best_gem["ModelId"])}
                battle_gem_ids.add(best_gem["Id"])

        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotInfo": self.state["slots"]}

    def _enrich_slot_for_view(self, slot: dict[str, Any], heroes_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
        enriched = copy.deepcopy(slot)
        hero = heroes_by_id.get(str(slot.get("HeroId", "")))
        if hero:
            enriched["Hero"] = dict(hero)
        return enriched

    def _own_slot_formations_view(self) -> dict[str, Any]:
        p = self.state["player"]
        heroes_by_id = {str(h["Id"]): h for h in self.state.get("heroes", [])}
        slot_infos = [self._enrich_slot_for_view(s, heroes_by_id) for s in self.state["slots"]]
        return {
            "PlayerInfo": {
                "PlayerId": p["PlayerId"],
                "Name": p.get("PlayerName", ""),
                "Lv": int(p.get("Lv", 1)),
                "StarId": int(p.get("StarId", 0)),
                "FashionModelId": int(p.get("FashionModelId", 0)),
                "FAP": int(p.get("FAP", 0)),
            },
            "SlotInfo": self.state["slots"],
            "SlotInfos": slot_infos,
            "MateInfos": self._mate_slot_info(),
            "SlotFormationInfo": self.state["embattle"],
            "SkillInfos": [],
            "CombatPet": None,
        }

    def _get_peer_s1_profiles(self) -> list[ProfileStore]:
        if not callable(self.peer_profiles_fn):
            return []
        my_pid = str(self.state.get("player", {}).get("PlayerId", ""))
        out: list[ProfileStore] = []
        for peer in self.peer_profiles_fn(self) or []:
            p_info = peer.state.get("player", {})
            if str(p_info.get("PlayerId", "")) != my_pid and int(p_info.get("IsNewPlayer", 0)) == 0:
                out.append(peer)
        return out

    def _find_peer_by_player_id(self, target_id: str) -> ProfileStore | None:
        tid = str(target_id)
        for peer in self._get_peer_s1_profiles():
            if str(peer.state.get("player", {}).get("PlayerId", "")) == tid:
                return peer
        return None

    def _find_peer_by_arena_rank(self, rank: int) -> ProfileStore | None:
        target_r = int(rank)
        my_r = int(self.state.get("pvp", {}).get("rank", 1500))
        if target_r == my_r:
            return None
        for peer in self._get_peer_s1_profiles():
            peer_r = int(peer.state.get("pvp", {}).get("rank", -1))
            if peer_r == target_r:
                return peer
        return None

    def _rpc_slot_formations(self, data: Any) -> dict[str, Any]:
        target_id = str(data[0]) if isinstance(data, list) and data and data[0] else str(self.state["player"]["PlayerId"])
        if target_id == str(self.state["player"]["PlayerId"]):
            return self._own_slot_formations_view()
        peer = self._find_peer_by_player_id(target_id)
        if peer is not None:
            return peer._own_slot_formations_view()
        bot_view = self._bot_slot_formations(target_id)
        if bot_view is not None:
            return bot_view
        self._last_rpc_context["status"] = -1
        return {}

    def _rpc_get_formation(self, _data: Any) -> dict[str, Any]:
        return {"SlotFormationInfo": self.state["embattle"]}

    def _rpc_change_formation(self, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            for k in range(1, 7):
                fk = f"Formation{k}"
                if fk in data:
                    self.state["embattle"][fk] = int(data[fk])
        elif isinstance(data, list) and len(data) >= 6:
            for k in range(1, 7):
                self.state["embattle"][f"Formation{k}"] = int(data[k - 1])
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotFormationInfo": self.state["embattle"]}

    @staticmethod
    def _build_equip_instance(model: int) -> dict[str, Any]:
        return {
            "Id": str(uuid.uuid4()),
            "EquipModelId": model,
            "Lv": 0,
            "Step": 0,
            "Gold": 0,
            "ExtraCount": 0,
            "APExtra": 0,
            "HPExtra": 0,
            "DEFExtra": 0,
            "DAMADDExtra": 0,
            "DAMCUTExtra": 0,
        }

    def _compose_equips(self, equip_ids: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
        def reject(status: int) -> tuple[list[str], list[dict[str, Any]]]:
            self._last_rpc_context["status"] = status
            return [], []

        if len(equip_ids) != 5:
            return reject(-1317)
        ids = set(equip_ids)
        if len(ids) != 5:
            return reject(-1320)
        equips = self.state["equips"]
        equips_by_id = {item["Id"]: item for item in equips}
        if ids - equips_by_id.keys():
            return reject(-1301)
        equipped = {
            slot.get(key, {}).get("Id")
            for slot in self.state["slots"] for key in self.EQUIP_TYPE_TO_SLOT_KEY.values()
        }
        materials = [equips_by_id[eid] for eid in equip_ids]
        if ids & equipped:
            return reject(-1304)
        if any(int(item.get("Step", 0)) for item in materials):
            return reject(-1323)

        models = self.game_data["equips"]
        recipes = self.game_data["equip_color"]
        configs = [models.get(str(item["EquipModelId"])) for item in materials]
        if not all(configs):
            return reject(-1311)
        color = int(configs[0]["colorLV"])
        if any(int(config["colorLV"]) != color for config in configs):
            return reject(-1325)
        recipe = recipes.get(str(color), {})
        next_color = int(recipe.get("colorFinally", 0))
        if next_color <= color:
            return reject(-1321)
        type_id = int(configs[0]["typeID"])
        output = min(
            (int(mid) for mid, info in models.items()
             if int(info["colorLV"]) == next_color and int(info["typeID"]) == type_id),
            default=0,
        )
        if not output or not self._is_valid_resource(type_id, output):
            return reject(-1331)
        player = self.state["player"]
        gold = int(player["Gold"])
        cost = int(recipe["colorUpUseNum"])
        if gold < cost:
            return reject(-1118)

        out_quality = int(models.get(str(output), {}).get("quality", 0))
        crit_qualities = self._timed_welfare_qualities(4418)
        copies = 2 if (crit_qualities and out_quality in crit_qualities) else 1
        created = [self._build_equip_instance(output) for _ in range(copies)]
        count_before = self.state["stats"]["equip_compose_count"]
        player["Gold"] = gold - cost
        self.state["equips"] = [item for item in equips if item["Id"] not in ids] + created
        self._inc_stat("equip_compose_count")
        try:
            self.save()
        except OSError:
            player["Gold"] = gold
            self.state["equips"] = equips
            self.state["stats"]["equip_compose_count"] = count_before
            logging.exception("Could not save equipment composition")
            return reject(-7)

        # Inventory and Gold commit together. The audit trail follows the committed save.
        try:
            self.ledger.record_grant_event(
                account_id=str(player["PlayerId"]), profile=self.profile_name, resource_type="Gold",
                amount=-cost, balance_after=player["Gold"], source=f"equip_compose:color_{color}",
            )
            self.ledger.record_grant_event(
                account_id=str(player["PlayerId"]), profile=self.profile_name, resource_type=f"Equip:{output}",
                amount=len(created), balance_after=len(self.state["equips"]), source=f"equip_compose:{output}",
            )
        except OSError:
            logging.exception("Could not audit committed equipment composition")
        return equip_ids, [{"Equip": created}]

    def _rpc_equip_compose(self, data: Any) -> dict[str, Any]:
        equip_ids = data[0] if isinstance(data, list) and len(data) == 1 and isinstance(data[0], list) else []
        if not all(isinstance(eid, str) for eid in equip_ids):
            self._last_rpc_context["status"] = -48
            return {}
        consumed, base_res = self._compose_equips(equip_ids)
        return {"ConsumeList": consumed, "BaseGetGameResourceList": base_res} if consumed else {}

    def _rpc_equip_one_key_compose(self, _data: Any) -> dict[str, Any]:
        equips_cfg = self.game_data.get("equips", {})
        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state["slots"]
            for k in ("Weapon", "Helmet", "Clothes", "Necklace")
            if slot.get(k, {}).get("Id")
        }
        buckets: dict[int, list[str]] = {}
        for eq in self.state.get("equips", []):
            if eq["Id"] in equipped_ids or int(eq.get("Step", 0)):
                continue
            clv = int(equips_cfg.get(str(eq["EquipModelId"]), {}).get("colorLV", 0))
            if clv in (1, 2, 3):
                buckets.setdefault(clv, []).append(eq["Id"])
        consumed_all: list[str] = []
        res_all: list[dict[str, Any]] = []
        for clv in sorted(buckets):
            ids = buckets[clv]
            while len(ids) >= 5:
                batch = ids[:5]
                ids = ids[5:]
                consumed, base_res = self._compose_equips(batch)
                consumed_all.extend(consumed)
                res_all.extend(base_res)
                if self._last_rpc_context["status"] == -7:
                    break
            if self._last_rpc_context["status"] == -7:
                break
        if consumed_all:
            self._last_rpc_context["status"] = 0
        return {"ConsumeList": consumed_all, "BaseGetGameResourceList": res_all}

    def _rpc_treasure_compose_color(self, data: Any) -> dict[str, Any]:
        """Combine 5 unequipped, un-stepped purple Treasures + Gold into Essence Stone (16050020)."""
        def reject(status: int) -> dict[str, Any]:
            self._last_rpc_context["status"] = status
            return {}

        treasure_ids = data[0] if isinstance(data, list) and len(data) == 1 and isinstance(data[0], list) else []
        if not all(isinstance(tid, str) for tid in treasure_ids):
            return reject(-48)

        cfg = self.game_data.get("treasure_color", {})
        need_purple = int(cfg.get("needPurple", 5))
        need_gold = int(cfg.get("needGold", 100000))
        out_str = str(cfg.get("outFinally", "1605,16050020,1"))

        if len(treasure_ids) != need_purple:
            return reject(-1317)
        ids = set(treasure_ids)
        if len(ids) != need_purple:
            return reject(-1320)

        treasures = self.state.get("treasures", [])
        tr_by_id = {str(t["Id"]): t for t in treasures}
        if ids - tr_by_id.keys():
            return reject(-1301)

        equipped = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Book", "Horse")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        if ids & equipped:
            return reject(-1304)

        materials = [tr_by_id[tid] for tid in treasure_ids]
        if any(int(t.get("Step", 0)) > 0 for t in materials):
            return reject(-1323)

        tr_models = self.game_data.get("treasures", {})
        quality_tbl = self.game_data.get("quality_model", {})
        refund_tuples: list[tuple[int, int, int]] = []
        for mat in materials:
            mid = int(mat.get("TreasureModelId", 0))
            tm = tr_models.get(str(mid))
            if not tm or mid in (14010803, 14020803) or int(tm.get("maxLV", 0)) <= 0:
                return reject(-1325)
            q_info = quality_tbl.get(str(int(tm.get("quality", 0))), {})
            if int(q_info.get("colorLV", 0)) != 4:
                return reject(-1325)
            refund_tuples.extend(self._treasure_exp_refund_tuples(tm, mat))

        player = self.state["player"]
        if int(player.get("Gold", 0)) < need_gold:
            return reject(-1118)

        out_tuples = _parse_resource_str(out_str) or [(1605, 16050020, 1)]
        grant_tuples = out_tuples + refund_tuples

        if need_gold > 0:
            self.ledger.apply_player_delta(
                player,
                self.profile_name,
                "Gold",
                -need_gold,
                source="treasure_compose",
            )
        self.state["treasures"] = [t for t in treasures if str(t["Id"]) not in ids]
        base_res = self._grant_resources_from_tuples(
            grant_tuples,
            source="treasure_compose",
            tx_prefix=f"treasure_compose:{self.profile_name}:{uuid.uuid4()}",
        )
        for rtype, rmid, _ in out_tuples:
            if int(rtype) == 1605:
                self._mark_goods_changed(int(rmid))
        self.save()
        return {"ConsumeList": treasure_ids, "BaseGetGameResourceList": base_res}

    @staticmethod
    def _parse_gem_compose_recipe(dst_model: dict[str, Any]) -> tuple[int, int, int, int, int]:
        """Parse syntheticUse and syntheticDoubleUse from a target GemModel entry."""
        gold_cost, req_gem_mid, req_gem_count = 0, 0, 0
        for part in str(dst_model.get("syntheticUse", "")).split("||"):
            segs = [s.strip() for s in part.split(",")]
            if len(segs) >= 3 and segs[0].isdigit():
                rtype, rmid, rnum = int(segs[0]), int(segs[1]), int(segs[2])
                if rtype == 1112:
                    gold_cost = rnum
                elif rtype == 2000:
                    req_gem_mid, req_gem_count = rmid, rnum
        dbl_mid, dbl_num = 0, 0
        dbl_raw = [s.strip() for s in str(dst_model.get("syntheticDoubleUse", "")).split(",") if s.strip()]
        if len(dbl_raw) >= 3 and dbl_raw[1].isdigit() and dbl_raw[2].isdigit():
            dbl_mid, dbl_num = int(dbl_raw[1]), int(dbl_raw[2])
        return gold_cost, req_gem_mid, req_gem_count, dbl_mid, dbl_num

    def _compose_gems(self, gem_ids: list[str], allow_double: bool = True) -> dict[str, Any] | None:
        """Merge 4 identical gems into the next level, either upgrading in-place or from bag."""
        def reject(status: int) -> None:
            self._last_rpc_context["status"] = status
            return None

        if len(gem_ids) != 4:
            return reject(-1317)
        ids = set(gem_ids)
        if len(ids) != 4:
            return reject(-1320)

        gems = self.state.get("gems", [])
        gems_by_id = {g["Id"]: g for g in gems}
        if ids - gems_by_id.keys():
            return reject(-1301)

        materials = [gems_by_id[gid] for gid in gem_ids]
        src_mid = int(materials[0].get("ModelId", 0))
        if any(int(item.get("ModelId", 0)) != src_mid for item in materials):
            return reject(-1325)

        gem_models = self.game_data.get("gem_model", {})
        src_model = gem_models.get(str(src_mid))
        if not src_model:
            return reject(-1311)
        dst_mid = src_mid + 1
        dst_model = gem_models.get(str(dst_mid))
        if (
            not dst_model
            or int(dst_model.get("gemType", 0)) != int(src_model.get("gemType", 0))
            or int(dst_model.get("LV", 0)) != int(src_model.get("LV", 0)) + 1
            or not self._is_valid_resource(2000, dst_mid)
        ):
            return reject(-1321)

        gold_cost, req_mid, req_count, dbl_mid, dbl_num = self._parse_gem_compose_recipe(dst_model)
        if req_mid != src_mid or req_count != 4:
            return reject(-1331)

        player = self.state["player"]
        gold_before = int(player["Gold"])
        if gold_before < gold_cost:
            return reject(-1118)

        socketed_map: dict[str, tuple[dict[str, Any], int]] = {}
        for slot in self.state["slots"]:
            for pos_idx, entry in enumerate(self._normalize_slot_gems(slot, gems_by_id=gems_by_id)):
                egid = entry.get("Id")
                if egid:
                    socketed_map[egid] = (slot, pos_idx)
        socketed_in_batch = [gid for gid in gem_ids if gid in socketed_map]
        if len(socketed_in_batch) > 1:
            return reject(-1304)

        gems_snapshot = copy.deepcopy(gems)
        slots_snapshot = copy.deepcopy(self.state["slots"])
        goods_snapshot = copy.deepcopy(self.state.get("goods", []))

        if len(socketed_in_batch) == 1:
            # Mode A: GemLevelUpLayer.lua:252-277 upgrades socketed gem in-place with 3 unbattle mats.
            target_gid = socketed_in_batch[0]
            mat_ids = [gid for gid in gem_ids if gid != target_gid]
            mat_set = set(mat_ids)
            player["Gold"] = gold_before - gold_cost
            self.state["gems"] = [g for g in gems if g["Id"] not in mat_set]
            upgraded = next(g for g in self.state["gems"] if g["Id"] == target_gid)
            upgraded["ModelId"] = dst_mid
            slot_ref, pos_idx = socketed_map[target_gid]
            slot_ref["Gem"][pos_idx] = {"Id": target_gid, "ModelId": dst_mid}
            self._recalc_all_slots_and_fap()
            self._last_rpc_context["slots_changed"] = True
            try:
                self.save()
            except OSError:
                player["Gold"] = gold_before
                self.state["gems"] = gems_snapshot
                self.state["slots"] = slots_snapshot
                self._recalc_all_slots_and_fap()
                logging.exception("Could not save in-place gem upgrade")
                return reject(-7)
            try:
                if gold_cost > 0:
                    self.ledger.record_grant_event(
                        account_id=str(player["PlayerId"]),
                        profile=self.profile_name,
                        resource_type="Gold",
                        amount=-gold_cost,
                        balance_after=player["Gold"],
                        source=f"gem_compose:{dst_mid}",
                    )
                self.ledger.record_grant_event(
                    account_id=str(player["PlayerId"]),
                    profile=self.profile_name,
                    resource_type=f"Gem:{dst_mid}",
                    amount=1,
                    balance_after=len(self.state["gems"]),
                    source=f"gem_compose_upgrade:{dst_mid}",
                )
            except OSError:
                logging.exception("Could not audit committed in-place gem upgrade")
            return {"Gem": dict(upgraded), "ConsumeList": mat_ids}

        # Mode B: EquipmentScene.lua:1185-1238 composes 4 bag gems (with optional syntheticDoubleUse).
        used_double = False
        if allow_double and dbl_mid > 0 and dbl_num > 0:
            used_double = self._consume_goods(dbl_mid, dbl_num)
        output_count = 2 if used_double else 1

        player["Gold"] = gold_before - gold_cost
        created = [{"Id": str(uuid.uuid4()), "ModelId": dst_mid} for _ in range(output_count)]
        self.state["gems"] = [g for g in gems if g["Id"] not in ids] + created
        try:
            self.save()
        except OSError:
            player["Gold"] = gold_before
            self.state["gems"] = gems_snapshot
            if used_double:
                self.state["goods"] = goods_snapshot
                gc = self._last_rpc_context.get("goods_changed")
                if isinstance(gc, dict):
                    gc.pop(str(dbl_mid), None)
            logging.exception("Could not save bag gem composition")
            return reject(-7)
        try:
            if gold_cost > 0:
                self.ledger.record_grant_event(
                    account_id=str(player["PlayerId"]),
                    profile=self.profile_name,
                    resource_type="Gold",
                    amount=-gold_cost,
                    balance_after=player["Gold"],
                    source=f"gem_compose:{dst_mid}",
                )
            if used_double:
                rem_double = sum(
                    int(g.get("Num", 0)) for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == dbl_mid
                )
                self.ledger.record_grant_event(
                    account_id=str(player["PlayerId"]),
                    profile=self.profile_name,
                    resource_type=f"Goods:{dbl_mid}",
                    amount=-dbl_num,
                    balance_after=rem_double,
                    source=f"gem_compose_double:{dst_mid}",
                )
            self.ledger.record_grant_event(
                account_id=str(player["PlayerId"]),
                profile=self.profile_name,
                resource_type=f"Gem:{dst_mid}",
                amount=output_count,
                balance_after=len(self.state["gems"]),
                source=f"gem_compose:{dst_mid}",
            )
        except OSError:
            logging.exception("Could not audit committed bag gem composition")
        return {
            "Gem": dict(created[0]),
            "ConsumeList": list(gem_ids),
            "BaseGetGameResourceList": [
                {"Gem": [{**g, "ResourceTypeSub": 2000, "Num": 1} for g in created]}
            ],
        }

    def _rpc_gem_compose(self, data: Any) -> dict[str, Any]:
        """Compose 4 gems into the next tier (GemLevelUpLayer.lua:266 / EquipmentScene.lua:1210)."""
        gem_ids = data[0] if isinstance(data, list) and len(data) >= 1 and isinstance(data[0], list) else []
        if not all(isinstance(gid, str) for gid in gem_ids):
            self._last_rpc_context["status"] = -48
            return {}
        res = self._compose_gems(gem_ids, allow_double=True)
        return res if res is not None else {}

    def _rpc_gem_one_key_compose(self, _data: Any) -> dict[str, Any]:
        """Batch-compose all unbattle sets of 4 identical gems across cascading tiers without burning double stones."""
        gem_models = self.game_data.get("gem_model", {})
        gems_by_id = {g["Id"]: g for g in self.state.get("gems", []) if g.get("Id")}
        initial_ids = set(gems_by_id)
        battle_gem_ids: set[str] = set()
        for slot in self.state["slots"]:
            for cur in self._normalize_slot_gems(slot, gems_by_id=gems_by_id):
                if cur.get("Id"):
                    battle_gem_ids.add(cur["Id"])

        buckets: dict[int, list[str]] = {}
        for g in self.state.get("gems", []):
            gid = g.get("Id", "")
            if not gid or gid in battle_gem_ids:
                continue
            mid = int(g.get("ModelId", 0))
            gm = gem_models.get(str(mid), {})
            if 1 <= int(gm.get("LV", 0)) < 15:
                buckets.setdefault(mid, []).append(gid)

        consumed_all: list[str] = []
        created_all: list[dict[str, Any]] = []
        while True:
            ready_mids = [
                mid
                for mid, ids in buckets.items()
                if len(ids) >= 4 and 1 <= int(gem_models.get(str(mid), {}).get("LV", 0)) < 15
            ]
            if not ready_mids:
                break
            mid = min(ready_mids, key=lambda m: (int(gem_models.get(str(m), {}).get("LV", 0)), m))
            ids = buckets[mid]
            stopped = False
            while len(ids) >= 4:
                batch = ids[:4]
                res = self._compose_gems(batch, allow_double=False)
                if res is None:
                    stopped = True
                    break
                del ids[:4]
                consumed_all.extend(res.get("ConsumeList", []))
                for bundle in res.get("BaseGetGameResourceList", []):
                    for new_gem in bundle.get("Gem", []):
                        created_all.append(new_gem)
                        new_mid = int(new_gem.get("ModelId", 0))
                        new_lv = int(gem_models.get(str(new_mid), {}).get("LV", 0))
                        new_id = str(new_gem.get("Id") or "")
                        if new_id and 1 <= new_lv < 15:
                            buckets.setdefault(new_mid, []).append(new_id)
                if self._last_rpc_context["status"] in (-7, -1118):
                    stopped = True
                    break
            if stopped:
                break

        remaining_ids = {g.get("Id") for g in self.state.get("gems", []) if g.get("Id")}
        net_consumed = [gid for gid in consumed_all if gid in initial_ids and gid not in remaining_ids]
        net_created = [g for g in created_all if g.get("Id") in remaining_ids]
        if net_consumed:
            self._last_rpc_context["status"] = 0
        base_res = [{"Gem": net_created}] if net_created else []
        return {"ConsumeList": net_consumed, "BaseGetGameResourceList": base_res}

    def _level_up_equip(self, eq: dict[str, Any], target_max_lv: int) -> bool:
        equips_cfg = self.game_data.get("equips", {})
        lv_up_tbl = self.game_data.get("equip_lv_up", {})
        clv = str(equips_cfg.get(str(eq["EquipModelId"]), {}).get("colorLV", 1))
        costs = lv_up_tbl.get(clv, {})
        cur_lv = int(eq.get("Lv", 0))
        row = costs.get(str(cur_lv))
        if cur_lv >= target_max_lv or (clv == "8" and not row):
            return False
        cost = int((row or {}).get("lvUpUseNum", 0))
        if int(self.state["player"]["Gold"]) < cost:
            return False
        if cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Gold",
                -cost,
                source=f"equip_lvup:{eq['EquipModelId']}",
            )
        eq["Lv"] = cur_lv + 1
        eq["Gold"] = int(eq.get("Gold", 0)) + cost
        self._inc_stat("equip_lvup_count", 1)
        self._record_daily_task_progress(27, 1)
        return True

    def _sync_slot_equips(self) -> None:
        equips_by_id = {e["Id"]: e for e in self.state.get("equips", [])}
        for slot in self.state["slots"]:
            for key in ("Weapon", "Helmet", "Clothes", "Necklace"):
                if (slot.get(key) or {}).get("Id") in equips_by_id:
                    eq = equips_by_id[slot[key]["Id"]]
                    slot[key]["Lv"] = eq["Lv"]
                    slot[key]["Step"] = int(eq.get("Step", 0))
        self._recalc_all_slots_and_fap()

    def _rpc_one_key_equip_lv_up(self, data: Any) -> dict[str, Any]:
        equip_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        equips_by_id = {e["Id"]: e for e in self.state.get("equips", [])}
        max_eq_lv = int(self.state["player"]["Lv"]) * 2
        updated: list[dict[str, Any]] = []
        missing_cost = False
        for eid in equip_ids:
            eq = equips_by_id.get(str(eid))
            if not eq:
                continue
            if not self._has_equip_enhancement_cost(eq):
                missing_cost = True
                continue
            while self._level_up_equip(eq, max_eq_lv):
                pass
            updated.append(eq)
        if not updated and missing_cost:
            return self._reject_resource_change(-1331)
        self._sync_slot_equips()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"EquipsInfo": updated}

    def _rpc_equip_lv_up_for_count(self, data: Any) -> dict[str, Any]:
        eid = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        count = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1
        eq = next((e for e in self.state.get("equips", []) if e["Id"] == eid), None)
        if not eq:
            self._last_rpc_context["status"] = -1
            return {}
        if not self._has_equip_enhancement_cost(eq):
            return self._reject_resource_change(-1331)
        max_eq_lv = int(self.state["player"]["Lv"]) * 2
        lv_up_list: list[int] = []
        for _ in range(max(1, count)):
            if not self._level_up_equip(eq, max_eq_lv):
                break
            lv_up_list.append(1)
        self._sync_slot_equips()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"EquipInfo": eq, "LvUpList": lv_up_list}

    def _has_equip_enhancement_cost(self, equip: dict[str, Any]) -> bool:
        color = str(self.game_data["equips"][str(equip["EquipModelId"])]["colorLV"])
        return color != "8" or str(equip["Lv"]) in self.game_data["equip_lv_up"].get(color, {})

    def _equipped_item_ids(self) -> set[str]:
        return {slot[key]["Id"] for slot in self.state["slots"]
                for key in self.EQUIP_TYPE_TO_SLOT_KEY.values() if (slot.get(key) or {}).get("Id")}

    def _rpc_equip_step_up(self, data: Any) -> dict[str, Any]:
        if (not isinstance(data, list) or len(data) not in (2, 3)
                or any(type(eid) is not str for eid in data[:2])):
            return self._reject_resource_change(-1316)
        equip_id, material_id = data[:2]
        if equip_id == material_id:
            return self._reject_resource_change(-1316)
        if self.state["player"]["Lv"] < self.game_data["module_subs"]["1403"]["openLv"]:
            return self._reject_resource_change(-1127)
        inventory = {item["Id"]: item for item in self.state["equips"]}
        equip, material = inventory.get(equip_id), inventory.get(material_id)
        if not equip:
            return self._reject_resource_change(-1301)
        model = str(equip["EquipModelId"])
        step = int(equip["Step"])
        if len(data) == 3:
            if type(data[2]) is not int:
                return self._reject_resource_change(-1316)
            if data[2] != step:
                return self._reject_resource_change(-39)
        steps = self.game_data["equip_steps"].get(model, {})
        row = steps.get(str(step))
        if not row:
            return self._reject_resource_change(-1312)
        if str(step + 1) not in steps:
            return self._reject_resource_change(-1313)
        if not material:
            return self._reject_resource_change(-1315)
        if equip["Lv"] < row["needLV"]:
            return self._reject_resource_change(-1314)
        if material_id in self._equipped_item_ids():
            return self._reject_resource_change(-1304)
        if material.get("Step", 0):
            return self._reject_resource_change(-1324)
        config = self.game_data["equips"]
        target, ingredient = config[model], config[str(material["EquipModelId"])]
        if target["typeID"] != ingredient["typeID"]:
            return self._reject_resource_change(-1326)
        if target["colorLV"] != ingredient["colorLV"]:
            return self._reject_resource_change(-1315)
        cost = row["stepUpUseNum"]
        player = self.state["player"]
        if int(player["Gold"]) < cost:
            return self._reject_resource_change(-1118)

        def advance():
            self.ledger.apply_player_delta(player, self.profile_name, "Gold", -cost, source="equip_step")
            self.state["equips"].remove(material)
            equip["Step"] += 1
            equip.setdefault("StepMaterials", []).append({"ModelId": material["EquipModelId"], "Gold": cost})
            refund = [(1112, 0, int(material.get("Gold", 0)))]
            output = self._grant_resources_from_tuples(
                refund, "equip_step_material", f"equip_step:{self.profile_name}:{material_id}",
            ) if refund[0][2] > 0 else []
            self._sync_slot_equips()
            self._last_rpc_context["slots_changed"] = True
            return {"EquipInfo": copy.deepcopy(equip), "BaseGetGameResourceList": output}

        return self._commit_resource_change(advance)

    def _rpc_get_battle_info(self, _data: Any) -> dict[str, Any]:
        return {
            "BattleInfo": self.state["battle"],
            "ChapterList": list(self.state["chapters"].values()),
        }

    def _rpc_get_node_list(self, data: Any) -> list[dict[str, Any]]:
        ch_id = int(data[0]) if isinstance(data, list) and data else 11
        # Only return unlocked (Flag=1) or passed (Flag=2) nodes per BattleLayer.lua:998 & GuideMng.lua:181
        nodes = [
            st
            for nid, st in sorted(self.state["nodes"].items(), key=lambda kv: int(kv[0]))
            if self.game_data["nodes"].get(nid, {}).get("chapterModelID") == ch_id and int(st.get("Flag", 0)) in (1, 2)
        ]
        if not nodes:
            raw_nodes = sorted(
                [n for n in self.game_data["nodes"].values() if n.get("chapterModelID") == ch_id],
                key=lambda x: x["ID"],
            )
            if raw_nodes:
                first = self._make_node_state(raw_nodes[0]["ID"], flag=1)
                self.state["nodes"][str(raw_nodes[0]["ID"])] = first
                nodes = [first]
                self.save()
        return nodes

    def _rpc_all_chapter_info(self, data: Any) -> list[dict[str, Any]]:
        raw_ids = data[0] if isinstance(data, list) and data and isinstance(data[0], list) else []
        out: list[dict[str, Any]] = []
        for raw_cid in raw_ids:
            cid = int(raw_cid)
            if str(cid) in self.state["chapters"]:
                out.append({"ChapterModelId": cid, "NodeList": self._rpc_get_node_list([cid])})
        return out

    def _difficulty_multiplier(self, node_cfg: dict[str, Any], star_lv: int) -> float:
        """Compute BattleNodeModel enemy stat ratio per selected star tier (1=Easy, 2=Normal, 3=Hard)."""
        max_stars = max(1, int(node_cfg.get("starCount", 1)))
        clamped = max(1, min(star_lv, max_stars))
        if clamped == 2:
            return float(node_cfg.get("commonNPCAttrR", 12500)) / 10000.0
        if clamped >= 3:
            return float(node_cfg.get("hardNPCAttrR", 16000)) / 10000.0
        return 1.0

    def _build_enemy_wave(
        self,
        node_id: int,
        node_cfg: dict[str, Any],
        wave_idx: int,
        total_waves: int,
        star_lv: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Build 6 enemy slots (indices 6..11 in Heros) scaled by stage progression and star_lv."""
        heroes_cfg = self.game_data["heroes"]
        enemies: list[dict[str, Any]] = [{} for _ in range(6)]
        diff_mult = self._difficulty_multiplier(node_cfg, star_lv)

        if self.profile_name == "debug":
            boss_id = "12011022" if str(node_id).endswith("5") else "12013005"
            enemies[1] = self._hero_fight_obj(
                heroes_cfg[boss_id],
                lv=1,
                is_boss=True,
                hp_mult=0.35 * diff_mult,
                ap_mult=1.15 * diff_mult,
                def_mult=diff_mult,
            )
            enemies[0] = self._hero_fight_obj(
                heroes_cfg["12011022"], lv=1, is_boss=False, hp_mult=0.25 * diff_mult, ap_mult=diff_mult, def_mult=diff_mult
            )
            enemies[2] = self._hero_fight_obj(
                heroes_cfg["12010053"], lv=1, is_boss=False, hp_mult=0.25 * diff_mult, ap_mult=diff_mult, def_mult=diff_mult
            )
            return enemies, 9500

        ch_id = int(node_cfg.get("chapterModelID", 11))
        node_pos = 10 if (node_id % 10 == 0 and ch_id > 11) else max(1, node_id % 10)
        pic = str(node_cfg.get("pic", "0"))
        is_final_wave = wave_idx == total_waves

        if ch_id <= 11:
            base_lv = max(1, (node_pos + 1) // 2)
            if is_final_wave and pic != "0" and pic in heroes_cfg:
                enemies[1] = self._hero_fight_obj(
                    heroes_cfg[pic],
                    lv=base_lv,
                    is_boss=True,
                    hp_mult=diff_mult,
                    ap_mult=diff_mult,
                    def_mult=diff_mult,
                )
            else:
                enemies[1] = self._hero_fight_obj(
                    heroes_cfg.get("12013043", next(iter(heroes_cfg.values()))),
                    lv=base_lv,
                    is_boss=False,
                    hp_mult=diff_mult,
                    ap_mult=diff_mult,
                    def_mult=diff_mult,
                )
            mob_lv = max(1, base_lv - 1)
            mob_cfg = heroes_cfg.get("12012045", heroes_cfg["12013043"])
            enemies[0] = self._hero_fight_obj(mob_cfg, lv=mob_lv, is_boss=False, hp_mult=diff_mult, ap_mult=diff_mult, def_mult=diff_mult)
            enemies[2] = self._hero_fight_obj(mob_cfg, lv=mob_lv, is_boss=False, hp_mult=diff_mult, ap_mult=diff_mult, def_mult=diff_mult)
            if node_pos >= 4:
                enemies[4] = self._hero_fight_obj(mob_cfg, lv=mob_lv, is_boss=False, hp_mult=diff_mult, ap_mult=diff_mult, def_mult=diff_mult)
            enemy_fap = sum(int(h["HP"] + h["AP"] * 10 + h["DEF"] * 10) for h in enemies if h)
            return enemies, enemy_fap

        # Calibrated log-linear progression across Ch 12..80 eliminating quality-inversion anomalies
        ch_nodes = [n for n in self.game_data.get("nodes", {}).values() if int(n.get("chapterModelID", 0)) == ch_id]
        ch_node_count = max(1, len(ch_nodes))
        need_lv = max(1, int(self.game_data.get("chapters", {}).get(str(ch_id), {}).get("needLV", ch_id)))
        unit_lv = max(need_lv, min(80, 1 + (ch_id - 11)))
        boss_cfg = heroes_cfg[pic] if (is_final_wave and pic != "0" and pic in heroes_cfg) else heroes_cfg.get("12013043", next(iter(heroes_cfg.values())))
        mob_cfgs = [
            heroes_cfg.get("12012045", boss_cfg),
            heroes_cfg.get("12013043", boss_cfg),
            heroes_cfg.get("12011022", boss_cfg),
            heroes_cfg.get("12012031", boss_cfg),
            heroes_cfg.get("12013041", boss_cfg),
        ]
        step_hint = max(0, min(6, (ch_id - 12) // 10))
        enemies[1] = self._hero_fight_obj(boss_cfg, lv=unit_lv, is_boss=(is_final_wave and pic != "0"), step=step_hint)
        enemies[0] = self._hero_fight_obj(mob_cfgs[0], lv=max(1, unit_lv - 1), is_boss=False, step=step_hint)
        enemies[2] = self._hero_fight_obj(mob_cfgs[1], lv=max(1, unit_lv - 1), is_boss=False, step=step_hint)
        enemies[4] = self._hero_fight_obj(mob_cfgs[2], lv=max(1, unit_lv - 1), is_boss=False, step=step_hint)
        if ch_id >= 20:
            enemies[3] = self._hero_fight_obj(mob_cfgs[3], lv=max(1, unit_lv - 1), is_boss=False, step=step_hint)
        if ch_id >= 35:
            enemies[5] = self._hero_fight_obj(mob_cfgs[4], lv=max(1, unit_lv - 1), is_boss=False, step=step_hint)

        progress = float(ch_id - 11) + float(max(0, node_pos - 1)) / float(ch_node_count)
        wave_scale = 1.0 if is_final_wave else 0.78
        target_fap = interpolate_log_curve(progress, _CAMPAIGN_FAP_ANCHORS) * diff_mult * wave_scale
        enemy_fap = scale_wave_to_target_fap(enemies, target_fap, boss_weight=1.25)
        return enemies, enemy_fap

    def _build_ally_fight_objs(self) -> list[dict[str, Any]]:
        heroes_cfg = self.game_data["heroes"]
        heroes_by_id = {h["Id"]: h for h in self.state["heroes"]}
        allies: list[dict[str, Any]] = [{} for _ in range(6)]
        if self.profile_name == "debug":
            for idx, inst in enumerate(self.state["heroes"][:6]):
                cfg = heroes_cfg[str(inst["HeroModelId"])]
                allies[idx] = self._hero_fight_obj(
                    cfg,
                    lv=max(20, inst["Lv"]),
                    is_boss=False,
                    hp_mult=2.5,
                    ap_mult=2.5,
                    step=int(inst.get("Step", 1)),
                )
            return allies

        slots_by_id = {int(s["SlotId"]): s for s in self.state["slots"]}
        emb = self.state.get("embattle", {})
        placed = False
        for f_idx in range(1, 7):
            slot_id = int(emb.get(f"Formation{f_idx}", f_idx))
            slot = slots_by_id.get(slot_id)
            if slot and slot.get("HeroId") and slot["HeroId"] != EMPTY_ENTITY_ID:
                cfg = heroes_cfg[str(slot["HeroModelId"])]
                inst = heroes_by_id.get(slot["HeroId"], {})
                allies[f_idx - 1] = self._hero_fight_obj(
                    cfg,
                    is_boss=False,
                    step=int(inst.get("Step", 0)),
                    reborn_step=int(inst.get("RebornStep", 0)),
                    reborn_id=int(inst.get("RebornId", 0)),
                    override_stats=slot["Property"],
                )
                placed = True
        if not placed and self.state["heroes"]:
            inst = self.state["heroes"][0]
            cfg = heroes_cfg[str(inst["HeroModelId"])]
            allies[0] = self._hero_fight_obj(
                cfg,
                lv=inst["Lv"],
                is_boss=False,
                step=int(inst.get("Step", 0)),
                reborn_step=int(inst.get("RebornStep", 0)),
                reborn_id=int(inst.get("RebornId", 0)),
            )
        return allies

    def _can_enter_battle_node(self, ch_id: int, node_id: int, check_vit: bool = True) -> tuple[bool, str]:
        """Enforce VN chapter needLV, daily fightNumMax, and VitConfig.perUseNum stamina."""
        ch_cfg = self.game_data["chapters"].get(str(ch_id), {})
        if int(self.state["player"].get("Lv", 1)) < int(ch_cfg.get("needLV", 1)):
            return False, "chapter_level_locked"
        node_cfg = self.game_data["nodes"].get(str(node_id))
        if not node_cfg or int(node_cfg.get("chapterModelID", 0)) != ch_id:
            return False, "invalid_node"
        node_st = self.state.get("nodes", {}).get(str(node_id))
        max_fights = int(node_cfg.get("fightNumMax", 10))
        if node_st and int(node_st.get("FightCount", 0)) >= max_fights:
            return False, "fight_limit_reached"
        if check_vit:
            vit_cost = int(self.game_data.get("vit_config", {}).get("perUseNum", 5))
            if int(self.state["player"].get("VIT", 0)) < vit_cost:
                return False, "insufficient_vit"
        return True, "ok"

    def _rpc_get_fight_info(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        node_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1111
        star_lv = int(data[2]) if isinstance(data, list) and len(data) >= 3 else 1
        allowed, _reason = self._can_enter_battle_node(ch_id, node_id, check_vit=True)
        if not allowed:
            self._last_rpc_context["status"] = -1
            return {}
        node_cfg = self.game_data["nodes"].get(str(node_id), {"ID": node_id, "name": "1-1", "starCount": 1, "fightRound": 1})
        allies = self._build_ally_fight_objs()

        total_waves = max(1, int(node_cfg.get("fightRound", 1)))
        fight_objs: list[dict[str, Any]] = []
        base_seed = random.randint(1000, 999999)
        for w_idx in range(1, total_waves + 1):
            enemies, enemy_fap = self._build_enemy_wave(node_id, node_cfg, w_idx, total_waves, star_lv)
            fight_objs.append(
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": sum(unit.get("FSP", 0) for unit in allies), "Fap": self.state["player"]["FAP"]},
                        {"Fsp": sum(unit.get("FSP", 0) for unit in enemies), "Fap": enemy_fap},
                    ],
                    "Pets": [],
                    "RandNum": base_seed + w_idx,
                    "IsPVP": False,
                }
            )

        return {
            "NodeInfo": node_cfg,
            "FightInfo": {
                "FightObjs": fight_objs,
            },
        }

    @staticmethod
    def _verify_battle_payload(verify_raw: Any, won: bool) -> dict[str, Any]:
        """Inspect BattleVerify payload (Battle.Fight data[4]) for wave/HP consistency."""
        if not verify_raw:
            return {"present": False, "consistent": True}
        try:
            payload = json.loads(verify_raw) if isinstance(verify_raw, str) else verify_raw
            if not isinstance(payload, dict):
                return {"present": True, "consistent": True}
            hp_waves = payload.get("hp")
            consistent = True
            if isinstance(hp_waves, list) and hp_waves:
                last_wave = hp_waves[-1]
                if isinstance(last_wave, list) and last_wave:
                    ally_alive = any(int(u.get("PosId", 0)) <= 6 and int(u.get("HP", 0)) > 0 for u in last_wave)
                    enemy_alive = any(int(u.get("PosId", 0)) > 6 and int(u.get("HP", 0)) > 0 for u in last_wave)
                    if won and enemy_alive and not ally_alive:
                        consistent = False
                    if not won and ally_alive and not enemy_alive:
                        consistent = False
            return {
                "present": True,
                "version": payload.get("version"),
                "waves": len(hp_waves) if isinstance(hp_waves, list) else 0,
                "consistent": consistent,
            }
        except Exception:
            return {"present": True, "consistent": True}

    def _recalc_battle_totals(self, ch_id: int) -> dict[str, Any]:
        ch_st = self.state["chapters"].setdefault(str(ch_id), self._make_chapter_state(ch_id))
        ch_nodes = sorted([int(k) for k, v in self.game_data["nodes"].items() if v.get("chapterModelID") == ch_id])
        ch_st["StarCount"] = sum(int(self.state["nodes"].get(str(nid), {}).get("StarCount", 0)) for nid in ch_nodes)
        self.state["battle"]["StarCount"] = sum(int(c.get("StarCount", 0)) for c in self.state["chapters"].values())
        return ch_st

    def _execute_battle_clear(
        self,
        ch_id: int,
        node_id: int,
        star_lv: int,
        won: bool,
        deduct_vit: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
        node_cfg = self.game_data["nodes"].get(str(node_id), {"dropGold": 50, "dropHeroExp": 25, "starCount": 1})
        max_node_star = max(1, int(node_cfg.get("starCount", 1)))
        vit_cfg = self.game_data.get("vit_config", {})
        vit_cost = int(vit_cfg.get("perUseNum", 5))
        per_exp_pct = int(vit_cfg.get("perGetEXPR", 20000))

        gold_gain = int(node_cfg.get("dropGold", 50)) if won else 0
        hero_exp_gain = int(node_cfg.get("dropHeroExp", 25)) if won else 0

        if self.is_normal_gameplay and won:
            old_lv = int(self.state["player"]["Lv"])
            exp_gain = int(vit_cost * old_lv * (per_exp_pct / 10000.0))
            if deduct_vit and int(self.state["player"]["VIT"]) >= vit_cost:
                self.ledger.apply_player_delta(
                    self.state["player"], self.profile_name, "VIT", -vit_cost, source=f"battle_vit:{node_id}"
                )
        else:
            exp_gain = 30 if won else 0

        node_st = self.state["nodes"].setdefault(str(node_id), self._make_node_state(node_id, flag=1))
        prev_star = int(node_st.get("StarCount", 0))
        was_first_clear = won and prev_star == 0
        node_st["FightCount"] += 1
        node_st["FightTime"] = int(time.time())
        if won:
            allowed_max = min(max_node_star, max(1, min(3, prev_star + 1)))
            earned_star = max(1, min(int(star_lv), max_node_star, allowed_max))
            node_st["StarCount"] = max(prev_star, earned_star)
            node_st["Flag"] = 2

        ch_nodes = sorted([int(k) for k, v in self.game_data["nodes"].items() if v.get("chapterModelID") == ch_id])
        ch_st = self._recalc_battle_totals(ch_id)

        ch_model = self.game_data["chapters"].get(str(ch_id), {})
        for suffix in ("A", "B", "C"):
            box_id = int(ch_model.get(f"roadBox{suffix}ID", 0))
            if box_id > 0 and ch_st.get(f"CanDrawRoadBox{suffix}", 0) == 0:
                box_cfg = self.game_data.get("road_boxes", {}).get(str(box_id), {})
                if int(box_cfg.get("needNodeModelID", 0)) == node_id and won:
                    ch_st[f"CanDrawRoadBox{suffix}"] = 1

        next_node = None
        next_chapter = None
        if won and node_id in ch_nodes:
            pos = ch_nodes.index(node_id)
            if pos + 1 < len(ch_nodes):
                next_nid = ch_nodes[pos + 1]
                next_node = self.state["nodes"].get(str(next_nid))
                if not next_node:
                    next_node = self._make_node_state(next_nid, flag=1)
                    self.state["nodes"][str(next_nid)] = next_node
                elif next_node["StarCount"] == 0 and next_node["Flag"] == 0:
                    next_node["Flag"] = 1
                self.state["battle"]["MaxNodeId"] = max(self.state["battle"]["MaxNodeId"], next_nid)
            else:
                ch_st["IfPass"] = 1
                next_chapter = self._unlock_next_chapter_after(ch_id)

        reward_tuples: list[tuple[int, int, int]] = []
        if won:
            reward_tuples.append((1101, 0, exp_gain))
            reward_tuples.append((1112, 0, gold_gain))
            reward_tuples.append((1117, 0, hero_exp_gain))
            if self.is_normal_gameplay:
                for d in self.game_data.get("node_drops", {}).get(str(node_id), []):
                    odds = int(d.get("dropOdds", 0))
                    if odds == 0 and was_first_clear:
                        reward_tuples.append((int(d["typeID"]), int(d["modelID"]), int(d["num"])))
                    elif odds > 0 and random.randint(1, 10000) <= odds:
                        reward_tuples.append((int(d["typeID"]), int(d["modelID"]), int(d["num"])))

        base_res = self._grant_resources_from_tuples(
            reward_tuples,
            source=f"battle_victory:{node_id}",
            tx_prefix=f"battle:{self.profile_name}:{node_id}:{uuid.uuid4()}",
        )
        self._record_daily_task_progress(1, 1)
        old_lv, new_lv = self._sync_level_from_exp()
        if new_lv != old_lv:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True
        return ch_st, node_st, next_node, next_chapter, base_res

    def _rpc_battle_fight(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) > 0 else 11
        node_id = int(data[1]) if isinstance(data, list) and len(data) > 1 else 1111
        star_lv = int(data[2]) if isinstance(data, list) and len(data) > 2 else 1
        won = bool(data[3]) if isinstance(data, list) and len(data) > 3 else True
        verify_raw = data[4] if isinstance(data, list) and len(data) > 4 else None

        verify_info = self._verify_battle_payload(verify_raw, won)
        if not verify_info.get("consistent", True):
            self._last_rpc_context["status"] = -1
            return {}

        allowed, _reason = self._can_enter_battle_node(ch_id, node_id, check_vit=True)
        if not allowed:
            self._last_rpc_context["status"] = -1
            return {}

        ch_st, node_st, next_node, next_chapter, base_res = self._execute_battle_clear(
            ch_id=ch_id, node_id=node_id, star_lv=star_lv, won=won
        )
        boss_id = self._maybe_trigger_luckboss() if won else None
        self.save()
        out: dict[str, Any] = {
            "IsSuccess": "True" if won else "False",
            "CurrentChapter": ch_st,
            "CurrentNode": node_st,
            "NextNode": next_node,
            "BaseGetGameResourceList": base_res if won else [],
        }
        if boss_id:
            out["BossId"] = boss_id
        if next_chapter is not None:
            out["NextChapter"] = next_chapter
        return out

    def _rpc_battle_con_fight(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) > 0 else 11
        node_id = int(data[1]) if isinstance(data, list) and len(data) > 1 else 1111
        star_lv = int(data[2]) if isinstance(data, list) and len(data) > 2 else 1
        count = max(1, min(10, int(data[3]) if isinstance(data, list) and len(data) > 3 else 1))
        consume_type = int(data[4]) if isinstance(data, list) and len(data) > 4 else 2

        node_cfg = self.game_data["nodes"].get(str(node_id), {"fightNumMax": 10, "starCount": 1})
        node_st = self.state["nodes"].get(str(node_id))
        max_node_star = max(1, int(node_cfg.get("starCount", 1)))
        if not node_st or int(node_st.get("StarCount", 0)) < min(star_lv, max_node_star):
            self._last_rpc_context["status"] = -1
            return {}

        vit_cost = int(self.game_data.get("vit_config", {}).get("perUseNum", 5))
        available_vit = int(self.state["player"]["VIT"])
        max_by_vit = available_vit // max(1, vit_cost) if self.is_normal_gameplay else count
        rem_count = max(0, int(node_cfg.get("fightNumMax", 10)) - int(node_st.get("FightCount", 0)))
        actual_count = min(count, max_by_vit, rem_count)
        if actual_count <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        token_gid = 16050011
        token_item = next((g for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == token_gid), None)
        owned_tokens = int(token_item.get("Num", 0)) if token_item else 0
        if consume_type == 3 and owned_tokens < actual_count and self.is_normal_gameplay:
            per_diamond = int(self.game_data.get("battle_config", {}).get("conFightUseDiamond", 5))
            diamond_need = per_diamond * (actual_count - owned_tokens)
            if int(self.state["player"].get("Diamond", 0)) < diamond_need:
                self._last_rpc_context["status"] = -1
                return {}
            if diamond_need > 0:
                self.ledger.apply_player_delta(
                    self.state["player"], self.profile_name, "Diamond", -diamond_need, source=f"confight:{node_id}"
                )
        use_tokens = min(owned_tokens, actual_count)
        if use_tokens > 0 and token_item is not None:
            token_item["Num"] = int(token_item["Num"]) - use_tokens
            if token_item["Num"] <= 0:
                self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != token_item["Id"]]
            self._mark_goods_changed(token_gid)

        all_bundles: list[dict[str, Any]] = []
        boss_id: str | None = None
        for _ in range(actual_count):
            _, _, _, _, base_res = self._execute_battle_clear(
                ch_id=ch_id, node_id=node_id, star_lv=star_lv, won=True
            )
            if base_res:
                all_bundles.append(base_res[0])
            if not boss_id:
                boss_id = self._maybe_trigger_luckboss()

        self.save()
        out_cf: dict[str, Any] = {
            "BattleInfo": self.state["battle"],
            "IsTriggerTrader": False,
            "BaseGetGameResourceList": all_bundles,
        }
        if boss_id:
            out_cf["BossId"] = boss_id
        return out_cf

    def _rpc_battle_reset_count(self, data: Any) -> dict[str, Any]:
        node_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1111
        consume_type = int(data[2]) if isinstance(data, list) and len(data) >= 3 and data[2] is not None else 0
        node_st = self.state["nodes"].get(str(node_id))
        if not node_st:
            self._last_rpc_context["status"] = -1
            return {}

        today = self.clock.today_str()
        last_reset_date = node_st.get("ResetFightDate")
        if not last_reset_date and int(node_st.get("ResetFightTime", 0)) > 0:
            last_reset_date = self.clock.today_str(int(node_st["ResetFightTime"]))
        cur_reset_count = 0 if (last_reset_date and last_reset_date != today) else int(node_st.get("ResetFightCount", 0))

        next_reset = cur_reset_count + 1
        reset_tbl = self.game_data.get("battle_reset_use", {})
        reset_cfg = reset_tbl.get(str(next_reset))
        if reset_tbl and not reset_cfg:
            self._last_rpc_context["status"] = -1
            return {}
        reset_cfg = reset_cfg or {"nodeUseResource": "1605,16050013,1", "nodeUseDiamond": 50}

        res_tuples = _parse_resource_str(str(reset_cfg.get("nodeUseResource", "")))
        diamond_cost = int(reset_cfg.get("nodeUseDiamond", 50))
        goods = self.state.get("goods", [])
        has_tokens = bool(res_tuples) and all(
            sum(int(g.get("Num", 0)) for g in goods if int(g.get("GoodsModelId", 0)) == model_id) >= need
            for _rt, model_id, need in res_tuples
        )

        use_token = True if consume_type == 2 else (False if consume_type == 3 else has_tokens)
        if use_token:
            if not has_tokens:
                self._last_rpc_context["status"] = -1105
                return {}
            for _rt, model_id, need in res_tuples:
                rem = need
                for g in self.state.get("goods", []):
                    if int(g.get("GoodsModelId", 0)) != model_id or rem <= 0:
                        continue
                    cur = int(g.get("Num", 0))
                    take = min(cur, rem)
                    g["Num"] = cur - take
                    rem -= take
                self.state["goods"] = [g for g in self.state.get("goods", []) if int(g.get("Num", 0)) > 0]
                self._mark_goods_changed(model_id)
        else:
            if int(self.state["player"].get("Diamond", 0)) < diamond_cost:
                self._last_rpc_context["status"] = -1105
                return {}
            if diamond_cost > 0:
                self.ledger.apply_player_delta(
                    self.state["player"],
                    self.profile_name,
                    "Diamond",
                    -diamond_cost,
                    source=f"battle_reset:{node_id}",
                )

        node_st["FightCount"] = 0
        node_st["ResetFightCount"] = next_reset
        node_st["ResetFightTime"] = self.now_ts()
        node_st["ResetFightDate"] = today
        self.save()
        return dict(node_st)

    def _rpc_draw_road_box(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        box_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 111
        ch_st = self.state["chapters"].get(str(ch_id))
        ch_model = self.game_data["chapters"].get(str(ch_id), {})
        box_cfg = self.game_data.get("road_boxes", {}).get(str(box_id))
        if not ch_st or not box_cfg:
            self._last_rpc_context["status"] = -1
            return {}

        matched_suffix = None
        for suffix in ("A", "B", "C"):
            if int(ch_model.get(f"roadBox{suffix}ID", 0)) == box_id:
                matched_suffix = suffix
                break
        if not matched_suffix or ch_st.get(f"CanDrawRoadBox{matched_suffix}", 0) != 1:
            self._last_rpc_context["status"] = -1
            return {}
        ch_st[f"CanDrawRoadBox{matched_suffix}"] = 2

        tuples = _parse_resource_str(box_cfg.get("outputResource", ""))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"road_box:{box_id}",
            tx_prefix=f"road_box:{self.profile_name}:{self.state['player']['PlayerId']}:{box_id}",
        )
        self.save()
        return {"Chapter": ch_st, "BaseGetGameResourceList": base_res}

    def _rpc_draw_box(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        box_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 111
        ch_st = self.state["chapters"].get(str(ch_id))
        ch_model = self.game_data["chapters"].get(str(ch_id), {})
        box_cfg = self.game_data.get("chapter_boxes", {}).get(str(box_id))
        if not ch_st or not box_cfg:
            self._last_rpc_context["status"] = -1
            return {}

        matched_suffix = None
        for suffix in ("A", "B", "C"):
            if int(ch_model.get(f"box{suffix}ID", 0)) == box_id:
                matched_suffix = suffix
                break
        if matched_suffix:
            need_star = int(ch_model.get(f"box{matched_suffix}NeedStar", 0))
            if int(ch_st.get("StarCount", 0)) < need_star or ch_st.get(f"IfDrawBox{matched_suffix}") is True:
                self._last_rpc_context["status"] = -1
                return {}
            ch_st[f"IfDrawBox{matched_suffix}"] = True

        tuples = _parse_resource_str(box_cfg.get("outputResource", ""))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"chapter_box:{box_id}",
            tx_prefix=f"chapter_box:{self.profile_name}:{self.state['player']['PlayerId']}:{box_id}",
        )
        self.save()
        return {"Chapter": ch_st, "BaseGetGameResourceList": base_res}

    def _rpc_one_key_draw_boxs(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        box_map = data[1] if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], dict) else {}
        ch_st = self.state["chapters"].get(str(ch_id))
        ch_model = self.game_data["chapters"].get(str(ch_id), {})
        if not ch_st:
            self._last_rpc_context["status"] = -1
            return {}

        tuples: list[tuple[int, int, int]] = []
        for raw_bid in box_map.get("1", []) or []:
            bid = int(raw_bid)
            for suffix in ("A", "B", "C"):
                if int(ch_model.get(f"box{suffix}ID", 0)) == bid and not ch_st.get(f"IfDrawBox{suffix}"):
                    if int(ch_st.get("StarCount", 0)) >= int(ch_model.get(f"box{suffix}NeedStar", 0)):
                        ch_st[f"IfDrawBox{suffix}"] = True
                        box_cfg = self.game_data.get("chapter_boxes", {}).get(str(bid), {})
                        tuples.extend(_parse_resource_str(box_cfg.get("outputResource", "")))
        for raw_bid in box_map.get("2", []) or []:
            bid = int(raw_bid)
            for suffix in ("A", "B", "C"):
                if int(ch_model.get(f"roadBox{suffix}ID", 0)) == bid and ch_st.get(f"CanDrawRoadBox{suffix}", 0) == 1:
                    ch_st[f"CanDrawRoadBox{suffix}"] = 2
                    box_cfg = self.game_data.get("road_boxes", {}).get(str(bid), {})
                    tuples.extend(_parse_resource_str(box_cfg.get("outputResource", "")))

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"one_key_boxes:{ch_id}",
            tx_prefix=f"one_key_boxes:{self.profile_name}:{ch_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"Chapter": ch_st, "BaseGetGameResourceList": base_res}

    def _rpc_hero_lv_up(self, data: Any) -> dict[str, Any]:
        hero_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        count = max(1, min(50, int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1))
        hero = next((h for h in self.state["heroes"] if h["Id"] == hero_id), None)
        if not hero:
            self._last_rpc_context["status"] = -1
            return {}
        cfg = self.game_data["heroes"].get(str(hero["HeroModelId"]), {})
        val_lv = int(cfg.get("valueLv", 3))
        gold_ratio = int(self.game_data.get("hero_config", {}).get("LVUpUseGoldR", 10000)) / 10000.0
        hero_lv_tbl = self.game_data.get("hero_lv", {})
        max_hero_lv = min(100, max(int(self.state["player"]["Lv"]) * 2, 10))

        leveled = 0
        for _ in range(count):
            cur_lv = int(hero["Lv"])
            if cur_lv >= max_hero_lv:
                break
            cur_row = hero_lv_tbl.get(str(val_lv * 1000 + cur_lv))
            nxt_row = hero_lv_tbl.get(str(val_lv * 1000 + cur_lv + 1))
            if not cur_row or not nxt_row:
                break
            soul_cost = max(0, int(nxt_row.get("EXPTotal", 0)) - int(cur_row.get("EXPTotal", 0)))
            gold_cost = int(soul_cost * gold_ratio)
            if int(self.state["player"]["HeroEXP"]) < soul_cost or int(self.state["player"]["Gold"]) < gold_cost:
                break
            if soul_cost > 0:
                self.ledger.apply_player_delta(
                    self.state["player"],
                    self.profile_name,
                    "HeroEXP",
                    -soul_cost,
                    source=f"hero_lv_up:{hero['HeroModelId']}",
                )
            if gold_cost > 0:
                self.ledger.apply_player_delta(
                    self.state["player"],
                    self.profile_name,
                    "Gold",
                    -gold_cost,
                    source=f"hero_lv_up:{hero['HeroModelId']}",
                )
            hero["Lv"] = cur_lv + 1
            leveled += 1

        if leveled == 0:
            self._last_rpc_context["status"] = -1
            return {}

        self._recalc_all_slots_and_fap()
        self._inc_stat("hero_lvup_count", leveled)
        self._record_daily_task_progress(28, leveled)
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return hero

    def _rpc_hero_step_up(self, data: Any) -> dict[str, Any]:
        def reject(status: int) -> dict[str, Any]:
            self._last_rpc_context["status"] = status
            return {}

        if not isinstance(data, list) or len(data) not in (2, 3):
            return reject(-47)
        hero_id, materials = data[:2]
        if materials == {}:  # Lua can encode an empty table as a JSON object.
            materials = []
        if (not isinstance(hero_id, str) or not isinstance(materials, list)
                or any(not isinstance(entity_id, str) or not entity_id for entity_id in materials)):
            return reject(-48)
        material_ids = set(materials)
        if len(material_ids) != len(materials):
            return reject(-1221)
        if hero_id in material_ids:
            return reject(-1220)

        heroes = {h["Id"]: h for h in self.state["heroes"]}
        hero = heroes.get(hero_id)
        if not hero:
            return reject(-1201)
        hero_model = int(hero["HeroModelId"])
        cfg = self.game_data["heroes"].get(str(hero_model), {})
        cur_step = int(hero["Step"])
        if len(data) == 3:
            if type(data[2]) is not int:
                return reject(-48)
            if data[2] != cur_step:
                return reject(-39)

        steps = self.game_data.get("hero_step", {})
        row_id = int(cfg.get("stepUpClassID", 0)) * 1000 + cur_step
        row = steps.get(str(row_id))
        if not row:
            return reject(-1212)
        if str(row_id + 1) not in steps:
            return reject(-1214)
        if self.is_normal_gameplay and (
            int(cfg.get("specialType", 0)) == 255
            or (self.state.get("slots") and self.state["slots"][0].get("HeroId") == hero_id)
        ):
            hero["Lv"] = max(1, int(self.state["player"].get("Lv", 1)))
        if int(hero["Lv"]) < int(row["needLv"]):
            return reject(-1217)

        gold_cost = 0
        goods_costs: Counter[int] = Counter()
        entity_costs: Counter[tuple[int, int]] = Counter()
        for resource_type, model, count in _parse_resource_str(row["upUse"]):
            if resource_type == 1112:
                gold_cost += count
            elif resource_type in (1401, 1402):
                entity_costs[resource_type, model] += count
            elif resource_type == 1605:
                goods_costs[model] += count
            else:
                return reject(-1212)
        if row["useNum"]:
            entity_costs[1201, hero_model] += int(row["useNum"])

        # Legacy requests are unambiguous unless two consecutive recipes use no entity IDs.
        if len(data) == 2 and not entity_costs and (previous := steps.get(str(row_id - 1))):
            previous_costs = _parse_resource_str(previous["upUse"])
            if not previous["useNum"] and all(kind in (1112, 1605) for kind, _, _ in previous_costs):
                return reject(-47)
        if len(material_ids) != sum(entity_costs.values()):
            return reject(-1602)

        player = self.state["player"]
        if int(player["Gold"]) < gold_cost:
            return reject(-1118)
        # The client totals all stacks for a model. Plan the same deduction before mutating any stack.
        goods_remaining = goods_costs.copy()
        goods_updates: dict[str, int] = {}
        for item in self.state["goods"]:
            model = int(item["GoodsModelId"])
            count = min(goods_remaining[model], int(item["Num"]))
            if count > 0:
                goods_updates[item["Id"]] = int(item["Num"]) - count
                goods_remaining[model] -= count
        if any(goods_remaining.values()):
            return reject(-1802)

        slots = self.state["slots"]
        deployed = self._deployed_hero_ids()
        equipped = {slot.get(key, {}).get("Id") for slot in slots for key in ("Book", "Horse")}
        treasures = {t["Id"]: t for t in self.state["treasures"]}
        submitted: Counter[tuple[int, int]] = Counter()
        for entity_id in materials:
            if material_hero := heroes.get(entity_id):
                if entity_id in deployed:
                    return reject(-1206)
                if int(material_hero["Lv"]) != 1 or int(material_hero["Step"]) != 0:
                    return reject(-1602)
                submitted[1201, int(material_hero["HeroModelId"])] += 1
            elif treasure := treasures.get(entity_id):
                if entity_id in equipped:
                    return reject(-1405)
                if int(treasure["Lv"]) != 0 or int(treasure["Step"]) != 0:
                    return reject(-1602)
                model = int(treasure["TreasureModelId"])
                resource_type = int(self.game_data["treasures"].get(str(model), {}).get("typeID", 0))
                submitted[resource_type, model] += 1
            else:
                return reject(-1602)
        if submitted != entity_costs:
            return reject(-1602)

        # RPCs hold the profile lock. The atomic JSON replace commits all inventory and the step together.
        before = copy.deepcopy({key: self.state[key] for key in ("player", "slots", "heroes", "treasures", "goods")})
        try:
            player["Gold"] = int(player["Gold"]) - gold_cost
            for item in self.state["goods"]:
                if item["Id"] in goods_updates:
                    item["Num"] = goods_updates[item["Id"]]
            self.state["goods"] = [
                item for item in self.state["goods"] if goods_updates.get(item["Id"], 1) > 0
            ]
            self.state["heroes"] = [h for h in self.state["heroes"] if h["Id"] not in material_ids]
            self.state["treasures"] = [t for t in self.state["treasures"] if t["Id"] not in material_ids]
            hero["Step"] = cur_step + 1
            self._recalc_all_slots_and_fap()
            self.save()
        except Exception as exc:
            self.state.update(before)
            if not isinstance(exc, OSError):
                raise
            logging.exception("Could not save hero breakthrough")
            return reject(-7)

        if gold_cost:
            try:
                self.ledger.record_grant_event(
                    account_id=str(player["PlayerId"]), profile=self.profile_name,
                    resource_type="Gold", amount=-gold_cost, balance_after=player["Gold"],
                    source=f"hero_step_up:{hero_model}",
                )
            except OSError:
                logging.exception("Could not audit committed hero breakthrough")
        for model in goods_costs:
            self._mark_goods_changed(model)
        self._last_rpc_context["slots_changed"] = True
        return hero

    def _explore_snapshot(self) -> dict[str, Any]:
        """Evaluate the timer and VN day without consuming or granting anything."""
        state = self._default_explore_state() | self.state["explore"]
        now = self.now_ts()
        today = self.clock.today_str(now)
        day = state.get("Day") or today
        if day < today:
            state.update(Day=today, DailyNum=0, ResetNum=0, DrawnNums="")
        else:
            state["Day"] = day
        cfg = self.game_data["explore_config"]
        row = self.game_data["attrtree"].get(str(self.state["player"].get("StarId", 0)), {})
        cap = int(cfg["fightNumMax"]) + int(row.get("xunyuAddNum", 0))
        remain = max(0, int(state.get("RemainNum", cfg["fightNumStart"])))
        next_time = int(state.get("RecoverTime", 0))
        interval = int(cfg["restoreFightNumDaily"])
        if remain < cap:
            if next_time <= 0 or next_time > now + interval:
                next_time = now + interval
            elif next_time <= now:
                recovered = min(cap - remain, 1 + (now - next_time) // interval)
                remain += recovered
                next_time += recovered * interval
        state.update(RemainNum=remain, MaxNum=cap, RecoverTime=next_time if remain < cap else 0)
        return state

    def _explore_payload(self) -> dict[str, Any]:
        exp_st = self.state["explore"]
        vip_lv = int(self.state.get("player", {}).get("VIPLv", self.state.get("player", {}).get("Vip", 0)))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        return {
            "RecoverTime": exp_st["RecoverTime"],
            "ResetNum": int(exp_st.get("ResetNum", 0)),
            "MaxResetNum": int(vip_cfg.get("exploreMaxNum", 0)),
            "RemainNum": exp_st["RemainNum"],
            "MaxNum": exp_st["MaxNum"],
            "DailyNum": int(exp_st.get("DailyNum", 0)),
            "DrawnNums": str(exp_st.get("DrawnNums", "")),
        }

    def _rpc_explore_get_info(self, _data: Any) -> dict[str, Any]:
        snapshot = self._explore_snapshot()
        self._last_rpc_context["explore_changed"] = True
        if snapshot != self.state["explore"]:
            def sync():
                self.state["explore"] = snapshot
                return self._explore_payload()
            return self._commit_resource_change(sync)
        return self._explore_payload()

    def _do_explore_once(self) -> tuple[int, int, list[tuple[int, int, int]]]:
        exp_st = self.state.setdefault("explore", self._default_explore_state())
        exp_st["RemainNum"] = int(exp_st.get("RemainNum", 0)) - 1
        exp_st["DailyNum"] = int(exp_st.get("DailyNum", 0)) + 1
        self._inc_stat("explore_count", 1)
        self._record_daily_task_progress(17, 1)
        roll = random.randint(1, 10000)
        reward_id = 1
        mult = 1
        for rid, rinfo in self.game_data.get("explore_reward_model", {}).items():
            if int(rinfo.get("oddsMin", 0)) <= roll <= int(rinfo.get("oddsMax", 0)):
                reward_id = int(rid)
                mult = int(rinfo.get("bonusMultiple", 1))
                break

        lv = int(self.state["player"]["Lv"])
        awards_tbl = self.game_data.get("explore_base_awards", {})
        base_row = awards_tbl.get(str(lv)) or awards_tbl.get("1", {"dropGold": 20, "dropExp": 4, "dropHeroExp": 0})
        tuples = [
            (1112, 0, int(base_row.get("dropGold", 20)) * mult),
            (1101, 0, int(base_row.get("dropExp", 4)) * mult),
        ]
        hexp = int(base_row.get("dropHeroExp", 0)) * mult
        if hexp > 0:
            tuples.append((1117, 0, hexp))
        if reward_id == 2:
            tuples.append((1605, 16050001, 2))
        drop_text_id = 3 if reward_id != 2 else 1
        return reward_id, drop_text_id, tuples

    def _rpc_explore_run(self, _data: Any) -> dict[str, Any]:
        return self._run_explore(1, "explore")

    def _rpc_explore_one_key(self, _data: Any) -> dict[str, Any]:
        if self.state["player"]["Vip"] < self.game_data["module_subs"]["5201"]["advancedOpenVIPLv"]:
            return self._reject_resource_change(-5004)
        return self._run_explore(10, "explore_one_key")

    def _run_explore(self, requested: int, source: str) -> dict[str, Any]:
        snapshot = self._explore_snapshot()
        count = min(snapshot["RemainNum"], requested)
        if count <= 0:
            return self._reject_resource_change(-5101)

        def explore():
            self.state["explore"] = snapshot
            totals: dict[tuple[int, int], int] = {}
            for _ in range(count):
                reward, drop, drops = self._do_explore_once()
                for rtype, rmodel, num in drops:
                    totals[(rtype, rmodel)] = totals.get((rtype, rmodel), 0) + num
            if snapshot["RemainNum"] < snapshot["MaxNum"] and not snapshot["RecoverTime"]:
                snapshot["RecoverTime"] = self.now_ts() + int(self.game_data["explore_config"]["restoreFightNumDaily"])
            base_res = self._grant_resources_from_tuples(
                [(rtype, model, num) for (rtype, model), num in totals.items() if num > 0],
                source=source, tx_prefix=f"{source}:{self.profile_name}:{uuid.uuid4()}",
            )
            old_lv, new_lv = self._sync_level_from_exp()
            if old_lv != new_lv:
                self._last_rpc_context.update(lv_changed=True, slots_changed=True)
            self._last_rpc_context["explore_changed"] = True
            return {**self._explore_payload(), "RewardModelId": reward, "DropTextId": drop,
                    "BaseGetGameResourceList": base_res}

        return self._commit_resource_change(explore)

    def _rpc_explore_buy(self, _data: Any) -> dict[str, Any]:
        snapshot = self._explore_snapshot()
        player = self.state["player"]
        max_reset = int(self.game_data["vip_model"][str(player["Vip"])]["exploreMaxNum"])
        if snapshot["RemainNum"] > 0:
            return self._reject_resource_change(-5103)
        if snapshot["ResetNum"] >= max_reset:
            return self._reject_resource_change(-5102)
        offers = self.game_data["explore_reset_use"]
        row = offers[str(min(snapshot["ResetNum"] + 1, len(offers)))]
        cost = row["useDiamond"]
        if player["Diamond"] < cost:
            return self._reject_resource_change(-1105)

        def buy():
            self.state["explore"] = snapshot
            self.ledger.apply_player_delta(player, self.profile_name, "Diamond", -cost, source="explore_buy")
            snapshot["ResetNum"] += 1
            snapshot["RemainNum"] += row["buyNum"]
            self._record_period_economy(spent=cost)
            self._inc_stat("spent_diamonds", cost)
            self._record_daily_task_progress(23, cost)
            self._last_rpc_context.update(explore_changed=True, spend_recorded=True)
            return self._explore_payload()

        return self._commit_resource_change(buy)

    def _rpc_explore_draw_daily(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) != 1 or type(data[0]) is not int:
            return self._reject_resource_change(-48)
        num = data[0]
        snapshot = self._explore_snapshot()
        drawn = [x for x in str(snapshot.get("DrawnNums", "")).split(",") if x]
        row = self.game_data.get("explore_reward_nums", {}).get(str(num))
        if not row:
            return self._reject_resource_change(-48)
        if snapshot["DailyNum"] < num:
            return self._reject_resource_change(-5104)
        if str(num) in drawn:
            return self._reject_resource_change(-7003)
        rewards = _parse_resource_str(str(row["rewards"]))
        if not self._can_receive_goods_outputs(rewards):
            return {}

        def draw():
            self.state["explore"] = snapshot
            snapshot["DrawnNums"] = ",".join((*drawn, str(num)))
            base_res = self._grant_resources_from_tuples(
                rewards, source=f"explore_daily:{num}",
                tx_prefix=f"explore_daily:{self.profile_name}:{self.state['player']['PlayerId']}:{snapshot['Day']}:{num}",
            )
            self._last_rpc_context["explore_changed"] = True
            return {**self._explore_payload(), "BaseGetGameResourceList": base_res}

        return self._commit_resource_change(draw)

    def _available_lighten_stars(self, star_id: int) -> int:
        tree = self.game_data["attrtree"]
        spent = sum(int(tree.get(str(node), {}).get("needStar", 0)) for node in range(1, star_id + 1))
        return max(0, int(self.state["battle"].get("StarCount", 0)) - spent)

    def _lighten_star_payload(self) -> dict[str, Any]:
        add_info = [
            {"SlotId": slot, "FightAttr": attr, "AddValue": bonuses[field]}
            for slot in range(1, 7)
            for bonuses in [self._get_slot_star_bonuses(slot)]
            for attr, field in ((431, "AP"), (432, "HP"), (433, "DEF"))
            if bonuses[field] > 0
        ]
        star_id = int(self.state["player"].get("StarId", 0))
        return {
            "StarId": star_id,
            "StarCount": self._available_lighten_stars(star_id),
            "StarCountTotal": int(self.state["battle"].get("StarCount", 0)),
            "UnlockedSlotIds": sorted(int(row["ID"]) for row in self.game_data["attrtree_slots"].values()
                                      if star_id >= int(row["needAttrTreeID"])),
            "AddValueInfo": add_info,
        }

    def _rpc_lighten_star_info(self, _data: Any) -> dict[str, Any]:
        return self._lighten_star_payload()

    def _advance_lighten_stars(self, limit: int) -> dict[str, Any]:
        player = self.state["player"]
        original = int(player.get("StarId", 0))
        tree = self.game_data["attrtree"]
        available = self._available_lighten_stars(original)
        gold = int(player["Gold"])
        status = 0
        current = original
        for _ in range(limit):
            row = tree.get(str(current + 1))
            if not row:
                status = -2211
                break
            if int(player["Lv"]) < int(row["needLV"]):
                status = -2212
                break
            if available < int(row["needStar"]):
                status = -2213
                break
            if gold < int(row["needGold"]):
                status = -1118
                break
            available -= int(row["needStar"])
            gold -= int(row["needGold"])
            current += 1
        if current == original:
            self._last_rpc_context["status"] = status
            return {}

        before = copy.deepcopy(self.state)
        # VN stores the cumulative exploration bonus, so only grant the change.
        delta = int(tree[str(current)]["xunyuAddNum"]) - int(tree[str(original)]["xunyuAddNum"])
        try:
            if delta > 0:
                explore = self._explore_snapshot()
                explore["MaxNum"] += delta
                explore["RemainNum"] += delta
                self.state["explore"] = explore
            player["StarId"] = current
            player["Gold"] = gold
            self._inc_stat("lighten_star_count", current - original)
            self._record_daily_task_progress(4, current - original)
            self._recalc_all_slots_and_fap()
            self.save()
        except OSError:
            self.state.clear()
            self.state.update(before)
            logging.exception("Could not save Insight Pursuit")
            self._last_rpc_context["status"] = -7
            return {}

        cost = int(before["player"]["Gold"]) - gold
        if cost:
            try:
                self.ledger.record_grant_event(
                    account_id=str(player["PlayerId"]), profile=self.profile_name, resource_type="Gold",
                    amount=-cost, balance_after=gold, source=f"lighten_star:{current}",
                )
            except OSError:
                logging.exception("Could not audit committed Insight Pursuit")
        self._last_rpc_context["slots_changed"] = True
        self._last_rpc_context["explore_changed"] = delta > 0
        return self._lighten_star_payload()

    def _rpc_lighten_star_up(self, _data: Any) -> dict[str, Any]:
        return self._advance_lighten_stars(1)

    def _rpc_lighten_star_one_key(self, _data: Any) -> dict[str, Any]:
        return self._advance_lighten_stars(50)

    def _ensure_shop_bought_daily(self) -> dict[str, int]:
        today = self.clock.today_str()
        if not self.state.get("shop_bought_date"):
            self.state["shop_bought_date"] = today
        elif self.state.get("shop_bought_date") != today:
            self.state["shop_bought"] = {}
            self.state["shop_bought_date"] = today
        return self.state.setdefault("shop_bought", {})

    def _shop_goods_price_for_step(self, goods_model_id: int, step_num: int, fallback: int) -> int:
        price_tbl = self.game_data.get("shop_goods_price", {}).get(str(goods_model_id), {})
        if not price_tbl:
            return fallback
        if str(step_num) in price_tbl:
            return int(price_tbl[str(step_num)].get("newPrice", fallback))
        max_k = max((int(k) for k in price_tbl if k.isdigit()), default=0)
        return int(price_tbl.get(str(max_k), {}).get("newPrice", fallback)) if max_k > 0 else fallback

    def _build_shop_goods_entry(self, goods_model_id: int) -> dict[str, Any]:
        shop_tbl = self.game_data.get("shop_goods", {})
        row = next((r for r in shop_tbl.values() if int(r.get("goodsModelID", 0)) == goods_model_id), None)
        init_price = int(row.get("initPrice", 20)) if row else 20
        sell_type_id = int(row.get("sellTypeID", 1111)) if row else 1111
        if_vip_limit = bool(row.get("ifVipLimitBuy", True)) if row else True
        if_dyn = bool(row.get("ifDynamicPrice", False)) if row else False

        bought = int(self._ensure_shop_bought_daily().get(str(goods_model_id), 0))
        curr_price = self._shop_goods_price_for_step(goods_model_id, bought + 1, init_price) if if_dyn else init_price

        if not if_vip_limit:
            max_num = -1
        else:
            vip_lv = str(int(self.state["player"].get("Vip", 0)))
            vip_tbl = self.game_data.get("vip_buy_limit", {}).get(vip_lv, {})
            max_num = int(vip_tbl.get(str(goods_model_id), {}).get("buyMaxNum", 6))
            if goods_model_id == SOUL_BOX_GOODS_ID and max_num >= 0:
                max_num = max(max_num, SOUL_BOX_SHOP_MAX_NUM)

        entry: dict[str, Any] = {
            "GoodsModelId": goods_model_id,
            "SellTypeId": sell_type_id,
            "CurrPrice": curr_price,
            "Num": bought,
            "MaxNum": max_num,
        }
        if if_dyn:
            price_tbl = self.game_data.get("shop_goods_price", {}).get(str(goods_model_id), {})
            max_step = max((int(k) for k in price_tbl if str(k).isdigit()), default=0)
            start_step = bought + 1
            end_step = max(start_step, max_step)
            entry["DynamicPrice"] = [
                {"NewPrice": self._shop_goods_price_for_step(goods_model_id, step_i, init_price)}
                for step_i in range(start_step, end_step + 1)
            ]
        return entry

    def _rpc_shop_goods_list(self, _data: Any) -> list[dict[str, Any]]:
        shop_tbl = self.game_data.get("shop_goods", {})
        return [
            self._build_shop_goods_entry(int(row["goodsModelID"]))
            for _, row in sorted(shop_tbl.items(), key=lambda kv: int(kv[0]))
            if int(row.get("goodsModelID", 0)) > 0
        ]

    def _rpc_get_shop_goods_info(self, data: Any) -> list[dict[str, Any]]:
        gid = int(data[0]) if isinstance(data, list) and data else 16030006
        return [self._build_shop_goods_entry(gid)]

    def _rpc_shop_reset_daily(self, _data: Any = None) -> list[dict[str, Any]]:
        """Reset daily props shop purchase counts & dynamic pricing without touching VIP gift bags."""
        self.state["shop_bought"] = {}
        self.state["shop_bought_date"] = self.clock.today_str()
        self.state["shop_daily_reset_count"] = int(self.state.get("shop_daily_reset_count", 0)) + 1
        self.save()
        return self._rpc_shop_goods_list(None)

    def _rpc_shop_buy_goods(self, data: Any) -> dict[str, Any]:
        gid = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 16030006
        count = max(1, int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1)
        if not self._is_valid_resource(gid // 10000, gid):
            self._last_rpc_context["status"] = -1
            return {}
        info = self._build_shop_goods_entry(gid)
        if info["MaxNum"] >= 0 and info["Num"] + count > info["MaxNum"]:
            self._last_rpc_context["status"] = -1
            return {}

        shop_tbl = self.game_data.get("shop_goods", {})
        row = next((r for r in shop_tbl.values() if int(r.get("goodsModelID", 0)) == gid), None)
        init_price = int(row.get("initPrice", 20)) if row else 20
        if_dyn = bool(row.get("ifDynamicPrice", False)) if row else False
        total_cost = sum(
            self._shop_goods_price_for_step(gid, info["Num"] + step_i + 1, init_price) if if_dyn else init_price
            for step_i in range(count)
        )
        currency = "Gold" if info["SellTypeId"] == 1112 else "Diamond"
        if int(self.state["player"].get(currency, 0)) < total_cost:
            self._last_rpc_context["status"] = -1
            return {}

        if total_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                currency,
                -total_cost,
                source=f"shop_buy:{gid}x{count}",
            )
        self._ensure_shop_bought_daily()[str(gid)] = info["Num"] + count
        self._grant_resources_from_tuples(
            [(gid // 10000, gid, count)],
            source=f"shop_buy:{gid}",
            tx_prefix=f"shop_buy:{self.profile_name}:{gid}:{uuid.uuid4()}",
        )
        g_cfg = self.game_data.get("goods_model", {}).get(str(gid), {})
        if int(g_cfg.get("typeID", 0)) == 1603:
            if int(g_cfg.get("outputTypeID", 0)) == 1102:
                self._record_daily_task_progress(13, count)
            elif int(g_cfg.get("outputTypeID", 0)) == 1103:
                self._record_daily_task_progress(22, count)
        self._mark_goods_changed(gid)
        self.save()
        return self._build_shop_goods_entry(gid)

    def _build_vip_gift_entry(self, row: dict[str, Any], bought_ids: set[int]) -> dict[str, Any]:
        gid = int(row["goodsModelID"])
        return {
            "GoodsModelId": gid,
            "SellTypeId": int(row.get("sellTypeID", 1111)),
            "InitPrice": int(row.get("initPrice", 0)),
            "CurrPrice": int(row.get("currPrice", 0)),
            "MaxNum": 1,
            "Num": 1 if gid in bought_ids else 0,
            "VipLv": int(row["ID"]),
        }

    def _rpc_shop_gift_list(self, _data: Any) -> list[dict[str, Any]]:
        gift_tbl = self.game_data.get("shop_vip_gift", {})
        bought_ids = {int(x) for x in self.state.get("vip_gift_bought", [])}
        return [
            self._build_vip_gift_entry(row, bought_ids)
            for _, row in sorted(gift_tbl.items(), key=lambda kv: int(kv[0]))
            if int(row.get("goodsModelID", 0)) > 0
        ]

    def _rpc_shop_buy_gift(self, data: Any) -> dict[str, Any]:
        gid = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 0
        buy_count = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1
        gift_tbl = self.game_data.get("shop_vip_gift", {})
        row = next((r for r in gift_tbl.values() if int(r.get("goodsModelID", 0)) == gid), None)
        if not row or buy_count != 1:
            self._last_rpc_context["status"] = -1
            return {}
        req_vip = int(row["ID"])
        cur_vip = int(self.state["player"].get("VIPLv", self.state["player"].get("Vip", 0)))
        bought = self.state.setdefault("vip_gift_bought", [])
        if cur_vip < req_vip or gid in {int(x) for x in bought}:
            self._last_rpc_context["status"] = -1
            return {}
        price = int(row.get("currPrice", 0))
        currency = "Gold" if int(row.get("sellTypeID", 1111)) == 1112 else "Diamond"
        if int(self.state["player"].get(currency, 0)) < price:
            self._last_rpc_context["status"] = -1
            return {}
        if price > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                currency,
                -price,
                source=f"shop_gift:{gid}",
                idempotency_key=f"shopgift_cost:{self.profile_name}:{gid}",
            )
        bought.append(gid)
        base_res = self._grant_resources_from_tuples(
            [(gid // 10000, gid, 1)],
            source=f"shop_gift:{gid}",
            tx_prefix=f"shopgift_item:{self.profile_name}:{gid}",
        )
        bought_ids = {int(x) for x in bought}
        self.save()
        return {
            "BuyGiftRecord": self._build_vip_gift_entry(row, bought_ids),
            "BaseGetGameResourceList": base_res,
        }

    def _rpc_goods_use(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        entity_id = str(data[0])
        gid = int(data[1])
        count = int(data[2]) if len(data) >= 3 else 1
        if count <= 0:
            self._last_rpc_context["status"] = -1
            return {}
        item = next((g for g in self.state.get("goods", []) if g["Id"] == entity_id and int(g["GoodsModelId"]) == gid), None)
        if not item or int(item.get("Num", 0)) < count:
            self._last_rpc_context["status"] = -1
            return {}
        if gid == 16050056:
            if count == 1:
                return self._rpc_recruit([40, 0])
            self._last_rpc_context["status"] = -1
            return {}

        g_cfg = self.game_data.get("goods_model", {}).get(str(gid), {})
        type_id = int(g_cfg.get("typeID", gid // 10000))
        out_type = int(g_cfg.get("outputTypeID", 0))
        out_model = int(g_cfg.get("outputModelID", 0))
        out_num = int(g_cfg.get("outputNum", 0))

        odds_code = int(g_cfg.get("goodsOutputOddsCode", 0))
        consume = count
        tuples: list[tuple[int, int, int]] = []
        if type_id in (1501, 1502):
            req_each = max(1, int(g_cfg.get("maxNum", 1)))
            crafts = count // req_each
            if crafts <= 0 or out_type <= 0 or out_model <= 0:
                self._last_rpc_context["status"] = -1
                return {}
            consume = crafts * req_each
            tuples.append((out_type, out_model, max(1, out_num) * crafts))
        elif odds_code > 0 and str(odds_code) in self.game_data.get("goods_output", {}):
            pool_rows = sorted(
                self.game_data["goods_output"][str(odds_code)].values(),
                key=lambda r: int(r.get("ID", 0)),
            )
            max_roll = max((int(r.get("oddsMax", 0)) for r in pool_rows), default=0)
            if type_id == 1601 or max_roll == 0:
                # eBoxFixed (including all 21 VIP gift bundles 16010001..16010021) grants EVERY row
                for row in pool_rows:
                    tuples.append(
                        (
                            int(row.get("outputTypeID", 0)),
                            int(row.get("outputModelID", 0)),
                            max(1, int(row.get("outputNum", 1))) * count,
                        )
                    )
            else:
                for _ in range(count):
                    roll = random.randint(1, max_roll)
                    chosen = next(
                        (r for r in pool_rows if int(r.get("oddsMin", 0)) <= roll <= int(r.get("oddsMax", 0))),
                        pool_rows[0],
                    )
                    tuples.append(
                        (
                            int(chosen.get("outputTypeID", 0)),
                            int(chosen.get("outputModelID", 0)),
                            max(1, int(chosen.get("outputNum", 1))),
                        )
                    )
        elif out_type > 0 and out_num > 0:
            tuples.append((out_type, out_model, out_num * count))

        if not tuples:
            self._last_rpc_context["status"] = -1
            return {}
        if not self._can_receive_goods_outputs(tuples):
            return {}
        item["Num"] = int(item["Num"]) - consume
        if item["Num"] <= 0:
            self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != item["Id"]]

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"goods_use:{gid}",
            tx_prefix=f"goods_use:{self.profile_name}:{gid}:{uuid.uuid4()}",
        )
        if type_id == 1603:
            if out_type == 1102:
                self._inc_stat("vit_pills_used", consume)
                self._record_daily_task_progress(13, consume)
            elif out_type == 1103:
                self._inc_stat("sta_pills_used", consume)
                self._record_daily_task_progress(22, consume)
        self._mark_goods_changed(gid)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_goods_use_box_choice(self, data: Any) -> dict[str, Any]:
        """Implement Goods.GoodsUseForBoxChoice for eBoxChoice (1606) and eFashionChoice (1608)."""
        if not isinstance(data, list) or len(data) < 3:
            self._last_rpc_context["status"] = -1
            return {}
        entity_id = str(data[0])
        box_gid = int(data[1])
        selected_model_id = int(data[2])
        count = int(data[3]) if len(data) >= 4 else 1
        if count <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        item = next(
            (g for g in self.state.get("goods", []) if g["Id"] == entity_id and int(g["GoodsModelId"]) == box_gid),
            None,
        )
        if not item or int(item.get("Num", 0)) < count:
            self._last_rpc_context["status"] = -1
            return {}

        g_cfg = self.game_data.get("goods_model", {}).get(str(box_gid), {})
        type_id = int(g_cfg.get("typeID", box_gid // 10000))
        odds_code = int(g_cfg.get("goodsOutputOddsCode", 0))
        if type_id not in (1606, 1608) or odds_code <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        pool_rows = self.game_data.get("goods_output", {}).get(str(odds_code), {}).values()
        chosen = next(
            (r for r in pool_rows if int(r.get("outputModelID", 0)) == selected_model_id),
            None,
        )
        if not chosen:
            self._last_rpc_context["status"] = -1
            return {}

        reward = (
            int(chosen.get("outputTypeID", 0)),
            int(chosen.get("outputModelID", 0)),
            max(1, int(chosen.get("outputNum", 1))) * count,
        )
        if not self._can_receive_goods_outputs([reward]):
            return {}

        item["Num"] = int(item["Num"]) - count
        if item["Num"] <= 0:
            self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != item["Id"]]

        base_res = self._grant_resources_from_tuples(
            [reward],
            source=f"box_choice:{box_gid}:{selected_model_id}",
            tx_prefix=f"boxchoice:{self.profile_name}:{box_gid}:{selected_model_id}:{uuid.uuid4()}",
        )
        self._mark_goods_changed(box_gid)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_goods_sell(self, data: Any) -> dict[str, Any]:
        """Sell stackable bag goods or expired vouchers per GoodsModel/GoodsDjqModel."""
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        entity_id = str(data[0])
        try:
            gid = int(data[1])
            count = int(data[2]) if len(data) >= 3 else 1
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        if count <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        item = next(
            (g for g in self.state.get("goods", []) if g.get("Id") == entity_id and int(g.get("GoodsModelId", 0)) == gid),
            None,
        )
        if not item or int(item.get("Num", 0)) < count:
            self._last_rpc_context["status"] = -1
            return {}

        cfg = self.game_data.get("goods_model", {}).get(str(gid)) or self.game_data.get("goods_djq_model", {}).get(str(gid))
        if not cfg:
            self._last_rpc_context["status"] = -1
            return {}
        sell_type = int(cfg.get("sellTypeID", 0))
        sell_num = int(cfg.get("sellNum", 0))
        if sell_type <= 0 or sell_num <= 0 or sell_type not in self._ATTR_RESOURCE_TYPES:
            self._last_rpc_context["status"] = -1
            return {}

        item["Num"] = int(item["Num"]) - count
        if item["Num"] <= 0:
            self.state["goods"] = [g for g in self.state["goods"] if g.get("Id") != item.get("Id")]

        base_res = self._grant_resources_from_tuples(
            [(sell_type, 0, sell_num * count)],
            source=f"goods_sell:{gid}",
            tx_prefix=f"goods_sell:{self.profile_name}:{gid}:{uuid.uuid4()}",
        )
        self._mark_goods_changed(gid)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_treasure_protect_info(self, _data: Any) -> dict[str, Any]:
        return {"EndTime": int(self.state.get("treasure_protect_end", 0))}

    def _rpc_treasure_protect_buy(self, data: Any) -> dict[str, Any]:
        # Type 1 uses protect item (16050004), type 2 uses Diamonds from TreasureLootConfig
        req_type = int(data[0]) if isinstance(data, list) and data else 2
        cfg = self.game_data.get("treasure_loot_config", {})
        per_sec = int(cfg.get("perProtectTime", 7200))
        used = False
        if req_type == 1:
            mat = next((g for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == 16050004 and int(g.get("Num", 0)) >= 1), None)
            if mat:
                mat["Num"] = int(mat["Num"]) - 1
                if mat["Num"] <= 0:
                    self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != mat["Id"]]
                self._mark_goods_changed(16050004)
                used = True
        if not used:
            cost = int(cfg.get("protectUseDiamond", 20))
            if int(self.state["player"].get("Diamond", 0)) < cost:
                self._last_rpc_context["status"] = -1
                return {}
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -cost,
                source="treasure_protect",
            )
        now = int(time.time())
        cur_end = max(now, int(self.state.get("treasure_protect_end", 0)))
        self.state["treasure_protect_end"] = cur_end + per_sec
        self.save()
        return {"EndTime": self.state["treasure_protect_end"]}

    def _build_treasure_robots(self, debris_model_id: int) -> list[dict[str, Any]]:
        cfg = self.game_data.get("treasure_loot_config", {})
        count = max(3, min(6, int(cfg.get("perGetTeamNum", 6))))
        player_lv = max(1, int(self.state["player"].get("Lv", 1)))
        player_fap = max(1200, int(self.state["player"].get("FAP", 1200)))
        roster = [
            ("robot_9001", "Yêu Quái Sói", 12011022, 1),
            ("robot_9002", "Thổ Phỉ Sơn Cốc", 12013005, 1),
            ("robot_9003", "Binh Lính Thành", 12012045, 2),
            ("robot_9004", "Lãng Nhân Chiến Quốc", 12013043, 2),
            ("robot_9005", "Tà Yêu Đêm", 12011032, 3),
            ("robot_9006", "Hắc Yêu Sĩ", 12012029, 3),
        ]
        heroes_cfg = self.game_data.get("heroes", {})
        targets: list[dict[str, Any]] = []
        for idx in range(count):
            rid, rname, hid, pro_enum = roster[idx % len(roster)]
            if str(hid) not in heroes_cfg:
                hid = int(next(iter(heroes_cfg.keys())))
            lv = max(1, player_lv - 2 + (idx % 3))
            fap = max(800, int(player_fap * (0.55 + 0.06 * idx)))
            targets.append(
                {
                    "LootPlayerId": f"{rid}_{debris_model_id}",
                    "Name": rname,
                    "Lv": lv,
                    "FAP": fap,
                    "HeroModelId": hid,
                    "PVPInterLv": 0,
                    "IsRobot": 1,
                    "LootProEnum": pro_enum,
                }
            )
        return targets

    def _rpc_treasure_target_list(self, data: Any) -> dict[str, Any]:
        debris_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 15040103
        return {"TreasureLootTeamInfo": self._build_treasure_robots(debris_id)}

    def _execute_single_treasure_loot(
        self,
        loot_player_id: str,
        treasure_model_id: int,
        debris_model_id: int,
    ) -> dict[str, Any] | None:
        sta_cfg = self.game_data.get("sta_config", {})
        sta_cost = int(sta_cfg.get("perUseNum", 2))
        if int(self.state["player"].get("STA", 0)) < sta_cost:
            self._last_rpc_context["status"] = -1
            return None

        self.ledger.apply_player_delta(
            self.state["player"],
            self.profile_name,
            "STA",
            -sta_cost,
            source=f"treasure_loot:{debris_model_id}",
        )

        targets = self._build_treasure_robots(debris_model_id)
        target = next((t for t in targets if t["LootPlayerId"] == loot_player_id), targets[0])
        if int(target.get("IsRobot", 1)) != 1:
            self.state["treasure_protect_end"] = 0

        player_lv = max(1, int(self.state["player"].get("Lv", 1)))
        player_fap = max(1000, int(self.state["player"].get("FAP", 1000)))
        heroes_cfg = self.game_data["heroes"]
        allies = self._build_ally_fight_objs()
        enemy_lv = max(1, player_lv // 2)
        leader_cfg = heroes_cfg.get(str(target["HeroModelId"]), next(iter(heroes_cfg.values())))
        mob_cfg = heroes_cfg.get("12012045", leader_cfg)
        enemies: list[dict[str, Any]] = [{} for _ in range(6)]
        enemies[1] = self._hero_fight_obj(leader_cfg, lv=enemy_lv, is_boss=False, hp_mult=0.45, ap_mult=0.45, def_mult=0.45)
        enemies[0] = self._hero_fight_obj(mob_cfg, lv=max(1, enemy_lv - 1), is_boss=False, hp_mult=0.4, ap_mult=0.4, def_mult=0.4)
        enemies[2] = self._hero_fight_obj(mob_cfg, lv=max(1, enemy_lv - 1), is_boss=False, hp_mult=0.4, ap_mult=0.4, def_mult=0.4)
        enemy_fap = sum(int(h["HP"] + h["AP"] * 10 + h["DEF"] * 10) for h in enemies if h)

        won = player_fap >= enemy_fap or target.get("IsRobot", 1) == 1
        loot_cfg = self.game_data.get("treasure_loot_config", {})
        deb_cfg = self.game_data.get("treasure_debris", {}).get(str(debris_model_id), {})
        deb_rtype = int(deb_cfg.get("typeID", 1504 if str(debris_model_id).startswith("1504") else 1503))

        has_debris = any(
            int(d.get("TreasureDebrisModelId", 0)) == debris_model_id and int(d.get("Num", 0)) > 0
            for d in self.state.get("treasure_debris", [])
        )
        loot_success = 1 if (won and (not has_debris or random.randint(1, 100) <= 75)) else 0

        gold_gain = int(player_lv * float(loot_cfg.get("perLootGetGoldR", 600000)) / 10000.0) if won else 0
        exp_gain = int(sta_cost * player_lv * (int(sta_cfg.get("perGetEXPR", 20000)) / 10000.0)) if won else 0
        flip_gold = max(300, player_lv * 40) if won else 0

        reward_tuples: list[tuple[int, int, int]] = []
        if won:
            reward_tuples.append((1112, 0, gold_gain + flip_gold))
            reward_tuples.append((1101, 0, exp_gain))
            if loot_success == 1 and debris_model_id > 0:
                reward_tuples.append((deb_rtype, debris_model_id, 1))

        base_res = self._grant_resources_from_tuples(
            reward_tuples,
            source=f"treasure_loot:{debris_model_id}",
            tx_prefix=f"loot:{self.profile_name}:{debris_model_id}:{uuid.uuid4()}",
        )
        if not base_res:
            base_res = [{"PlayerAttr": [{"ResourceTypeSub": 1112, "Num": 0}, {"ResourceTypeSub": 1101, "Num": 0}]}]

        self._record_daily_task_progress(3, 1)
        if loot_success == 1:
            self._inc_stat("treasure_loot_wins", 1)
        old_lv, new_lv = self._sync_level_from_exp()
        if new_lv != old_lv:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True

        choice_cards = [
            {"IsDrop": 1, "ResourceTypeSub": 1112, "ModelId": 0, "Num": flip_gold},
            {"IsDrop": 0, "ResourceTypeSub": 1117, "ModelId": 0, "Num": 40},
            {"IsDrop": 0, "ResourceTypeSub": 1605, "ModelId": 16050001, "Num": 2},
        ]
        fight_info = {
            "IsWinFight": 1 if won else 0,
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": 2000, "Fap": player_fap},
                        {"Fsp": 1100, "Fap": enemy_fap},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1000, 999999),
                    "IsPVP": False,
                }
            ],
        }
        return {
            "IfTargetCanLoot": 1,
            "IsWinFight": 1 if won else 0,
            "IsWinLootSuccess": loot_success,
            "FightInfo": fight_info,
            "BaseGetGameResourceList": base_res,
            "ChoiceGetGameResource": choice_cards,
        }

    def _rpc_treasure_loot(self, data: Any) -> dict[str, Any]:
        loot_player_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else "robot_9001"
        treasure_model_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 14020501
        debris_model_id = int(data[2]) if isinstance(data, list) and len(data) >= 3 else 15040103
        res = self._execute_single_treasure_loot(loot_player_id, treasure_model_id, debris_model_id)
        if res is None:
            return {}
        self.save()
        return res

    def _rpc_treasure_loot_count(self, data: Any) -> dict[str, Any]:
        loot_player_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else "robot_9001"
        treasure_model_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 14020501
        debris_model_id = int(data[2]) if isinstance(data, list) and len(data) >= 3 else 15040103
        req_count = max(1, min(10, int(data[3]) if isinstance(data, list) and len(data) >= 4 else 1))

        choices: list[dict[str, Any]] = []
        base_last: list[dict[str, Any]] = []
        got_loot = 0
        for _ in range(req_count):
            step_res = self._execute_single_treasure_loot(loot_player_id, treasure_model_id, debris_model_id)
            if step_res is None:
                break
            base_last = step_res["BaseGetGameResourceList"]
            drop_card = next((c for c in step_res["ChoiceGetGameResource"] if c.get("IsDrop") == 1), step_res["ChoiceGetGameResource"][0])
            choices.append(drop_card)
            if step_res["IsWinLootSuccess"] == 1:
                got_loot = 1
                break
        if not choices:
            return {}
        self.save()
        return {
            "IsWinLootSuccess": got_loot,
            "BaseGameResource": base_last,
            "ChoiceGameResource": choices,
        }

    def _rpc_treasure_loot_one_key(self, data: Any) -> dict[str, Any]:
        player = self.state["player"]
        gate = self.game_data["module_subs"]["2506"]
        level = int(player["Lv"])
        vip = int(player.get("Vip", 0))
        if level < int(gate["openLv"]) and not (
            vip >= int(gate["advancedOpenVIPLv"]) and level >= int(gate["VIPNeedLv"])
        ):
            self._last_rpc_context["status"] = -5902
            return {}

        treasure_id = int(data[0]) if isinstance(data, list) and data else 0
        treasure = self.game_data["treasures"].get(str(treasure_id), {})
        owned = {
            int(row["TreasureDebrisModelId"])
            for row in self.state["treasure_debris"] if int(row["Num"]) > 0
        }
        missing = [mid for mid in treasure.get("debrisModelIds", []) if mid not in owned]
        if not missing:
            self._last_rpc_context["status"] = -2010
            return {}

        sta_cost = int(self.game_data["sta_config"]["perUseNum"])
        choices = []
        loot_info = {}
        base = []
        debris_id = missing[0]
        for missing_id in missing:
            debris_id = missing_id
            target = self._build_treasure_robots(debris_id)[0]["LootPlayerId"]
            while int(player["STA"]) >= sta_cost:
                result = self._execute_single_treasure_loot(target, treasure_id, debris_id)
                base = result["BaseGetGameResourceList"]
                choices.append(next(card for card in result["ChoiceGetGameResource"] if card["IsDrop"] == 1))
                if result["IsWinLootSuccess"]:
                    loot_info[str(len(choices))] = debris_id
                    break
            if int(player["STA"]) < sta_cost:
                break
        if not choices:
            self._last_rpc_context["status"] = -1120
            return {}
        self.save()
        return {
            "TotalLootCount": len(choices),
            "LootInfo": loot_info,
            "LastTreasureModelId": debris_id,
            "BaseGameResource": base,
            "ChoiceGameResource": choices,
        }

    def _rpc_treasure_compose(self, data: Any) -> dict[str, Any]:
        treasure_model_id = int(data[0]) if isinstance(data, list) and data else 0
        tr_cfg = self.game_data.get("treasures", {}).get(str(treasure_model_id))
        if not tr_cfg:
            self._last_rpc_context["status"] = -1
            return {}
        req_debris = tr_cfg.get("debrisModelIds", [])
        if not isinstance(req_debris, list) or not req_debris:
            self._last_rpc_context["status"] = -1
            return {}

        debris_list = self.state.setdefault("treasure_debris", [])
        by_model = {int(d["TreasureDebrisModelId"]): d for d in debris_list}
        for did in req_debris:
            entry = by_model.get(int(did))
            if not entry or int(entry.get("Num", 0)) < 1:
                return {"IsTreasureDebrisNotEnough": 0}

        for did in req_debris:
            did_int = int(did)
            entry = by_model[did_int]
            entry["Num"] = int(entry["Num"]) - 1
            if entry["Num"] <= 0:
                self.state["treasure_debris"] = [
                    d for d in self.state["treasure_debris"] if int(d["TreasureDebrisModelId"]) != did_int
                ]
            self._mark_treasure_debris_changed(did_int)

        rtype = int(tr_cfg.get("typeID", 1402 if str(treasure_model_id).startswith("1402") else 1401))
        base_res = self._grant_resources_from_tuples(
            [(rtype, treasure_model_id, 1)],
            source=f"treasure_compose:{treasure_model_id}",
            tx_prefix=f"compose:{self.profile_name}:{treasure_model_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _elite_battle_info_payload(self) -> dict[str, Any]:
        el = self.state.setdefault("elite", {"fight_count": 3, "buy_count": 0, "consume_buy_count": 0, "nodes": {}})
        return {
            "BuyCount": int(el.get("buy_count", 0)),
            "FightCount": int(el.get("fight_count", 3)),
            "RefreshCount": 0,
            "ConsumeBuyCount": int(el.get("consume_buy_count", 0)),
            "CanFightTime": 0,
        }

    def _sync_elite_nodes(self) -> list[dict[str, Any]]:
        el = self.state.setdefault("elite", {"fight_count": 3, "buy_count": 0, "consume_buy_count": 0, "nodes": {}})
        saved_nodes = el.setdefault("nodes", {})
        elite_cfg_nodes = self.game_data.get("elite_nodes", {})
        ordered_ids = sorted(elite_cfg_nodes.keys(), key=int)
        out: list[dict[str, Any]] = []
        prev_cleared = True
        for nid_str in ordered_ids:
            nid = int(nid_str)
            cfg = elite_cfg_nodes[nid_str]
            st = saved_nodes.setdefault(
                nid_str,
                {"NodeModelId": nid, "Flag": 0, "PassTime": 0, "CanDraw": "False", "first_claimed": False},
            )
            req_node = int(cfg.get("needBattleNodeModelID", 0))
            req_ok = req_node <= 0 or int(self.state.get("nodes", {}).get(str(req_node), {}).get("Flag", 0)) == 2
            if int(st.get("Flag", 0)) == 0 and prev_cleared and req_ok:
                st["Flag"] = 1
            if int(st.get("Flag", 0)) == 2 and not st.get("first_claimed", False):
                st["CanDraw"] = "True"
            else:
                st["CanDraw"] = "False"
            out.append(
                {
                    "NodeModelId": nid,
                    "Flag": int(st["Flag"]),
                    "PassTime": int(st.get("PassTime", 0)),
                    "CanDraw": st["CanDraw"],
                }
            )
            prev_cleared = int(st["Flag"]) == 2
        return out

    def _rpc_elite_get_battle_info(self, _data: Any) -> dict[str, Any]:
        node_list = self._sync_elite_nodes()
        return {
            "BattleInfo": self._elite_battle_info_payload(),
            "NodeList": node_list,
        }

    def _rpc_elite_get_fight_info(self, data: Any) -> dict[str, Any]:
        elite_id = int(data[0]) if isinstance(data, list) and data else 11
        cfg = self.game_data.get("elite_nodes", {}).get(str(elite_id), {})
        ref_nid = int(cfg.get("needBattleNodeModelID", 1217))
        ref_node_cfg = self.game_data.get("nodes", {}).get(str(ref_nid), {"chapterModelID": 12, "pic": "12012045"})
        allies = self._build_ally_fight_objs()
        enemies, enemy_fap = self._build_enemy_wave(ref_nid, ref_node_cfg, 1, 1, 2)
        return {
            "FightInfo": {
                "FightObjs": [
                    {
                        "Heros": allies + enemies,
                        "TeamData": [
                            {"Fsp": 2000, "Fap": int(self.state["player"].get("FAP", 1000))},
                            {"Fsp": 1300, "Fap": enemy_fap},
                        ],
                        "Pets": [],
                        "RandNum": random.randint(1000, 999999),
                        "IsPVP": False,
                    }
                ]
            }
        }

    def _rpc_elite_fight(self, data: Any) -> dict[str, Any]:
        elite_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        won = bool(data[1]) if isinstance(data, list) and len(data) >= 2 else True
        verify_raw = data[2] if isinstance(data, list) and len(data) >= 3 else None

        if not self._verify_battle_payload(verify_raw, won).get("consistent", True):
            self._last_rpc_context["status"] = -1
            return {}

        el_cfg = self.game_data.get("elite_config", {})
        vit_cost = int(el_cfg.get("fightVITSuccessful", 10))
        el = self.state.setdefault("elite", {"fight_count": 3, "buy_count": 0, "consume_buy_count": 0, "nodes": {}})
        avail = int(el.get("fight_count", 0)) + max(0, int(el.get("buy_count", 0)) - int(el.get("consume_buy_count", 0)))
        if won and (avail <= 0 or int(self.state["player"].get("VIT", 0)) < vit_cost):
            self._last_rpc_context["status"] = -1
            return {}

        node_list = self._sync_elite_nodes()
        node_cfg = self.game_data.get("elite_nodes", {}).get(str(elite_id), {})
        st = el["nodes"].setdefault(
            str(elite_id), {"NodeModelId": elite_id, "Flag": 1, "PassTime": 0, "CanDraw": "False", "first_claimed": False}
        )
        base_res: list[dict[str, Any]] = []
        if won:
            if int(el.get("fight_count", 0)) > 0:
                el["fight_count"] = int(el["fight_count"]) - 1
            else:
                el["consume_buy_count"] = int(el.get("consume_buy_count", 0)) + 1
            self.ledger.apply_player_delta(self.state["player"], self.profile_name, "VIT", -vit_cost, source=f"elite_vit:{elite_id}")
            st["Flag"] = 2
            st["PassTime"] = int(time.time())
            if not st.get("first_claimed", False):
                st["CanDraw"] = "True"

            old_lv = int(self.state["player"]["Lv"])
            per_exp_pct = int(self.game_data.get("vit_config", {}).get("perGetEXPR", 20000))
            exp_gain = int(vit_cost * old_lv * (per_exp_pct / 10000.0))
            gold_gain = int(node_cfg.get("dropGold", 3000))
            hero_exp_gain = int(node_cfg.get("dropHeroExp", 3000))
            reward_tuples: list[tuple[int, int, int]] = [
                (1101, 0, exp_gain),
                (1112, 0, gold_gain),
                (1117, 0, hero_exp_gain),
            ]
            for d in self.game_data.get("elite_node_drops", {}).get(str(elite_id), []):
                odds = int(d.get("dropOdds", 0))
                if odds >= 10000 or (odds > 0 and random.randint(1, 10000) <= odds):
                    reward_tuples.append((int(d["typeID"]), int(d["modelID"]), int(d["num"])))
            base_res = self._grant_resources_from_tuples(
                reward_tuples,
                source=f"elite_victory:{elite_id}",
                tx_prefix=f"elite:{self.profile_name}:{elite_id}:{uuid.uuid4()}",
            )
            old_lv2, new_lv2 = self._sync_level_from_exp()
            if new_lv2 != old_lv2:
                self._last_rpc_context["lv_changed"] = True
                self._last_rpc_context["slots_changed"] = True
            self._record_daily_task_progress(2, 1)

        node_list = self._sync_elite_nodes()
        cur_node = next((n for n in node_list if n["NodeModelId"] == elite_id), {"NodeModelId": elite_id, "Flag": int(st["Flag"]), "PassTime": int(st["PassTime"]), "CanDraw": st["CanDraw"]})
        next_node = next((n for n in node_list if n["NodeModelId"] == elite_id + 1), cur_node)
        boss_id = self._maybe_trigger_luckboss() if won else None
        self.save()
        out: dict[str, Any] = {
            "IsSuccess": "True" if won else "False",
            "BattleInfo": self._elite_battle_info_payload(),
            "CurrentNode": cur_node,
            "NextNode": next_node,
            "BaseGetGameResourceList": base_res if won else [],
        }
        if boss_id:
            out["BossId"] = boss_id
        return out

    def _rpc_elite_draw_first_reward(self, data: Any) -> dict[str, Any]:
        elite_id = int(data[0]) if isinstance(data, list) and data else 11
        self._sync_elite_nodes()
        el = self.state.setdefault("elite", {"fight_count": 3, "buy_count": 0, "consume_buy_count": 0, "nodes": {}})
        st = el.get("nodes", {}).get(str(elite_id))
        if not st or int(st.get("Flag", 0)) != 2 or st.get("first_claimed", False):
            self._last_rpc_context["status"] = -1
            return {}
        cfg = self.game_data.get("elite_nodes", {}).get(str(elite_id), {})
        tuples = _parse_resource_str(str(cfg.get("firstReward", "")))
        st["first_claimed"] = True
        st["CanDraw"] = "False"
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"elite_first:{elite_id}",
            tx_prefix=f"elite_first:{self.profile_name}:{elite_id}",
        )
        self.save()
        return {
            "NodeInfo": {"NodeModelId": elite_id, "Flag": int(st["Flag"]), "PassTime": int(st.get("PassTime", 0)), "CanDraw": "False"},
            "BaseGetGameResourceList": base_res,
        }

    def _rpc_elite_buy_fight_count(self, data: Any) -> dict[str, Any]:
        ctype = int(data[0]) if isinstance(data, list) and data else 3
        el = self.state.setdefault("elite", {"fight_count": 3, "buy_count": 0, "consume_buy_count": 0, "nodes": {}})
        used_prop = False
        if ctype == 2:
            mat = next((g for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == 16050014 and int(g.get("Num", 0)) >= 1), None)
            if mat:
                mat["Num"] = int(mat["Num"]) - 1
                if mat["Num"] <= 0:
                    self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != mat["Id"]]
                self._mark_goods_changed(16050014)
                used_prop = True
        if not used_prop:
            cost = 50
            if int(self.state["player"].get("Diamond", 0)) < cost:
                self._last_rpc_context["status"] = -1
                return {}
            self.ledger.apply_player_delta(self.state["player"], self.profile_name, "Diamond", -cost, source="elite_buy")
        el["buy_count"] = int(el.get("buy_count", 0)) + 1
        self.save()
        return {"BattleInfo": self._elite_battle_info_payload()}


    # ------------------------------------------------------------------
    # ExtraActivity, Charge, CardInfo, and Authenticated Admin Helpers
    # ------------------------------------------------------------------
    def _lv_plan_need_vip(self) -> int:
        return int(self.game_data.get("lv_plan_config", {}).get("needVIPLV", LV_PLAN_NEED_VIP))

    def _lv_plan_tiers(self) -> dict[int, tuple[int, int]]:
        tbl = self.game_data.get("lv_plan_rewards", {})
        if isinstance(tbl, dict) and tbl:
            return {
                int(r["LV"]): (int(r["diamond"]), int(r.get("needDiamond", LV_PLAN_NEED_DIAMOND)))
                for r in tbl.values()
                if "LV" in r and "diamond" in r
            }
        return {lv: (dia, LV_PLAN_NEED_DIAMOND) for lv, dia in LV_PLAN_REWARDS.items()}

    def _rpc_lv_plan_info(self, _data: Any) -> dict[str, Any]:
        lp = self.state.setdefault("lv_plan", {"open": False, "rewarded": []})
        rewarded = [int(x) for x in lp.get("rewarded", [])]
        player_lv = int(self.state["player"].get("Lv", 1))
        player_vip = int(self.state["player"].get("Vip", 0))
        tiers = self._lv_plan_tiers()
        can_list: list[int] = []
        if player_vip >= self._lv_plan_need_vip():
            for tier_lv in sorted(tiers):
                if player_lv >= tier_lv and tier_lv not in rewarded:
                    can_list.append(tier_lv)
        return {
            "CanRewardLvList": can_list,
            "RewardLvList": rewarded,
        }

    def _rpc_lv_plan_open(self, _data: Any) -> dict[str, Any]:
        lp = self.state.setdefault("lv_plan", {"open": False, "rewarded": []})
        lp["open"] = True
        self.save()
        return self._rpc_lv_plan_info([])

    def _rpc_lv_plan_receive(self, data: Any) -> dict[str, Any]:
        tier_lv = int(data[0]) if isinstance(data, list) and data else 0
        tier = self._lv_plan_tiers().get(tier_lv)
        p = self.state["player"]
        lp = self.state.setdefault("lv_plan", {"open": False, "rewarded": []})
        rewarded = [int(x) for x in lp.get("rewarded", [])]
        if (
            tier is None
            or int(p.get("Vip", 0)) < self._lv_plan_need_vip()
            or int(p.get("Lv", 1)) < tier_lv
            or tier_lv in rewarded
            or int(p.get("Diamond", 0)) < tier[1]
        ):
            self._last_rpc_context["status"] = -1
            return {}
        reward_diamond, need_diamond = tier
        self.ledger.apply_player_delta(
            p,
            self.profile_name,
            "Diamond",
            -need_diamond,
            source=f"lv_plan_cost:{tier_lv}",
            idempotency_key=f"lvplan:cost:{self.profile_name}:{p['PlayerId']}:{tier_lv}",
        )
        base_res = self._grant_resources_from_tuples(
            [(1111, 0, reward_diamond)],
            source=f"lv_plan_reward:{tier_lv}",
            tx_prefix=f"lvplan:rew:{self.profile_name}:{p['PlayerId']}:{tier_lv}",
        )
        rewarded.append(tier_lv)
        lp["rewarded"] = sorted(set(rewarded))
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _vip_welfare_tuples(self) -> list[tuple[int, int, int]]:
        vip = max(0, min(20, int(self.state["player"].get("Vip", 0))))
        row = self.game_data.get("vip_welfare", {}).get(str(vip))
        raw = str(row["resourceList"]) if isinstance(row, dict) and row.get("resourceList") else VIP_WELFARE_REWARDS.get(vip, VIP_WELFARE_REWARDS[0])
        return _parse_resource_str(raw)

    def _rpc_vip_welfare_info(self, _data: Any) -> dict[str, Any]:
        today = self.clock.today_str()
        can_draw = self.state.get("vip_welfare_drawn_date", "") != today
        res_list = [
            {"ResourceTypeSub": rtype, "ModelId": rmodel, "Count": rnum}
            for rtype, rmodel, rnum in self._vip_welfare_tuples()
        ]
        return {"CanDraw": can_draw, "ResourceList": res_list}

    def _rpc_vip_welfare_draw(self, _data: Any) -> dict[str, Any]:
        today = self.clock.today_str()
        if self.state.get("vip_welfare_drawn_date", "") == today:
            self._last_rpc_context["status"] = -1
            return {}
        tuples = self._vip_welfare_tuples()
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"vip_welfare:{today}",
            tx_prefix=f"vipwelfare:{self.profile_name}:{self.state['player']['PlayerId']}:{today}",
        )
        self.state["vip_welfare_drawn_date"] = today
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_player_charge_list(self, _data: Any) -> list[dict[str, Any]]:
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}})
        bought = {str(x) for x in cs.get("first_bought", [])}
        out: list[dict[str, Any]] = []
        for tier in CHARGE_TIERS:
            is_first = tier["ProductId"] not in bought
            out.append(
                {
                    "ProductId": tier["ProductId"],
                    "ChargePoint": tier["ChargePoint"],
                    "GamePoint": tier["GamePoint"],
                    "GiveGamePoint": tier["GiveGamePoint"] if is_first else 0,
                    "IsFirst": is_first,
                    "Ratio": tier["Ratio"] if is_first else 1,
                    "Instant": bool(tier.get("Instant", False)),
                }
            )
        return out

    def _rpc_player_charge_info(self, _data: Any) -> dict[str, Any]:
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}})
        return {
            "ChargeNum": int(self.state["player"].get("ChargeNum", 0)),
            "DrawNums": [int(x) for x in cs.get("drawn_boxes", [])],
        }

    def _rpc_player_charge_draw_box(self, data: Any) -> dict[str, Any]:
        num = int(data[0]) if isinstance(data, list) and data else 0
        raw = CHARGE_BOX_REWARDS.get(num)
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}})
        drawn = [int(x) for x in cs.get("drawn_boxes", [])]
        if not raw or int(self.state["player"].get("ChargeNum", 0)) < num or num in drawn:
            self._last_rpc_context["status"] = -1
            return {}
        base_res = self._grant_resources_from_tuples(
            _parse_resource_str(raw),
            source=f"first_charge_box:{num}",
            tx_prefix=f"chargebox:{self.profile_name}:{self.state['player']['PlayerId']}:{num}",
        )
        drawn.append(num)
        cs["drawn_boxes"] = sorted(set(drawn))
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _resolve_charge_tier(self, identifier: Any) -> dict[str, Any] | None:
        key = str(identifier).strip()
        return next(
            (
                t
                for t in CHARGE_TIERS
                if str(t["ProductId"]) == key or str(t["ChargePoint"]) == key
            ),
            None,
        )

    def _rpc_player_charge_generate_order(self, data: Any) -> str:
        arg = data[0] if isinstance(data, list) and data else "com.cmn.inuyasha.gem60"
        tier = self._resolve_charge_tier(arg)
        if not tier:
            self._last_rpc_context["status"] = -1
            return ""
        order_id = f"ORD-{uuid.uuid4().hex[:16]}"
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}, "card_orders": {}})
        cs.setdefault("orders", {})[order_id] = {
            "ProductId": tier["ProductId"],
            "ChargePoint": tier["ChargePoint"],
            "status": "pending",
            "ts": int(time.time()),
        }
        self.save()
        return order_id

    def _legacy_pray_tree_recharge(self, start: int, end: int) -> int:
        """Recover dated R7.11 purchases for the current instance."""
        charge = self.state.get("charge_state", {})

        def completed_in_window(order: dict[str, Any]) -> bool:
            return (
                order.get("status") == "completed"
                and not order.get("pray_tree_tracked")
                and start <= int(order.get("completed_at") or 0) < end
            )

        diamonds = 0
        for order in charge.get("orders", {}).values():
            if completed_in_window(order):
                tier = self._resolve_charge_tier(order.get("ProductId"))
                if tier:
                    diamonds += int(tier["GamePoint"])
        for order in charge.get("card_orders", {}).values():
            if completed_in_window(order):
                card = CARD_MODEL_CFG.get(int(order.get("CardId", 0)))
                if card:
                    diamonds += int(card["price"])
        return diamonds

    def _legacy_period_charges(self, start: int, end: int) -> list[tuple[int, int]]:
        """Recover only timestamped, completed purchases from saves made before R7.13."""
        charges: list[tuple[int, int]] = []
        state = self.state.get("charge_state", {})
        for orders, card in (("orders", False), ("card_orders", True)):
            for order in state.get(orders, {}).values():
                when = int(order.get("completed_at") or 0)
                if not start <= when < end or order.get("status") != "completed" or order.get("period_economy_tracked"):
                    continue
                if card:
                    tier = CARD_MODEL_CFG.get(int(order.get("CardId", 0)))
                    amount = int(tier["price"]) if tier else 0
                else:
                    tier = self._resolve_charge_tier(order.get("ProductId"))
                    amount = int(tier["GamePoint"]) if tier else 0
                if amount:
                    charges.append((when, amount))
        return charges

    def _apply_simulated_charge(
        self,
        tier: dict[str, Any],
        actor: str = "player",
        source: str = "simulated_charge",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        p = self.state["player"]
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}, "card_orders": {}})
        bought = cs.setdefault("first_bought", [])
        pid = tier["ProductId"]
        is_first = pid not in bought
        base_diamonds = int(tier["GamePoint"])
        bonus_diamonds = int(tier["GiveGamePoint"]) if is_first else 0
        total_diamonds = base_diamonds + bonus_diamonds
        tx_key = idempotency_key or f"simcharge:{self.profile_name}:{p['PlayerId']}:{uuid.uuid4()}"
        self.ledger.apply_player_delta(
            p,
            self.profile_name,
            "Diamond",
            total_diamonds,
            source=source,
            idempotency_key=f"{tx_key}:diamond",
            actor=actor,
            metadata={"ProductId": pid, "ChargePoint": tier["ChargePoint"], "is_first": is_first},
        )
        self.ledger.apply_player_delta(
            p,
            self.profile_name,
            "VipEXP",
            base_diamonds,
            source=source,
            idempotency_key=f"{tx_key}:vipexp",
            actor=actor,
            metadata={"ProductId": pid},
        )
        p["ChargeNum"] = int(p.get("ChargeNum", 0)) + base_diamonds
        self._inc_stat("recharged_diamonds", base_diamonds)
        self._record_period_economy(charged=base_diamonds)
        self._record_pray_tree_recharge(base_diamonds)
        self._record_slot_recharge(base_diamonds)
        if is_first:
            bought.append(pid)
        self._sync_player_recover_times(p)
        self.save()
        return {
            "ProductId": pid,
            "DiamondAdded": total_diamonds,
            "VipEXPAdded": base_diamonds,
            "Vip": int(p.get("Vip", 0)),
            "VIPLv": int(p.get("VIPLv", 0)),
            "VipEXP": int(p.get("VipEXP", 0)),
            "Diamond": int(p.get("Diamond", 0)),
            "ChargeNum": int(p["ChargeNum"]),
        }

    def _rpc_player_charge_confirm_order(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            self._last_rpc_context["status"] = -1
            return {}
        tier = self._resolve_charge_tier(data[0])
        if tier is None:
            self._last_rpc_context["status"] = -1
            return {}
        order_id = str(data[1]).strip() if len(data) >= 2 and data[1] is not None else ""
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}, "card_orders": {}})
        tx_key = None
        if order_id:
            ord_entry = cs.setdefault("orders", {}).get(order_id)
            if not isinstance(ord_entry, dict) or ord_entry.get("ProductId") != tier["ProductId"]:
                self._last_rpc_context["status"] = -1
                return {}
            if ord_entry.get("status") == "completed":
                self._last_rpc_context["status"] = -1136
                return {}
            ord_entry["status"] = "completed"
            ord_entry["completed_at"] = int(time.time())
            ord_entry["pray_tree_tracked"] = True
            ord_entry["period_economy_tracked"] = True
            tx_key = f"order:{self.profile_name}:{order_id}"
        return self._apply_simulated_charge(
            tier,
            actor="player",
            source="simulated_charge_rpc",
            idempotency_key=tx_key,
        )

    def _card_list_payload(self) -> list[dict[str, Any]]:
        now = int(time.time())
        today = time.strftime("%Y-%m-%d")
        cards = self.state.setdefault("month_cards", {})
        out: list[dict[str, Any]] = []
        for cid_str, info in sorted(cards.items()):
            exp_ts = int(info.get("ExpireTime", 0))
            if exp_ts <= now:
                continue
            out.append(
                {
                    "CardId": int(cid_str),
                    "ExpireTime": exp_ts,
                    "CanDrawTodayReward": info.get("LastDailyDate", "") != today,
                    "CanDrawBuyReward": not bool(info.get("BuyDrawn", False)),
                }
            )
        return out

    def _rpc_card_info(self, _data: Any) -> list[dict[str, Any]]:
        return self._card_list_payload()

    def _rpc_card_generate_order(self, data: Any) -> dict[str, Any]:
        cid = int(data[0]) if isinstance(data, list) and data else 1
        cfg = CARD_MODEL_CFG.get(cid)
        if not cfg:
            self._last_rpc_context["status"] = -1
            return {}
        order_id = f"CARDORD-{uuid.uuid4().hex[:14]}"
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}, "card_orders": {}})
        cs.setdefault("card_orders", {})[order_id] = {
            "CardId": cid,
            "ProductId": cfg["ProductId"],
            "status": "pending",
            "ts": int(time.time()),
        }
        self.save()
        return {"ProductId": cfg["ProductId"], "OrderId": order_id}

    def _rpc_card_activity(self, data: Any) -> list[dict[str, Any]]:
        cid = int(data[0]) if isinstance(data, list) and data else 1
        cfg = CARD_MODEL_CFG.get(cid)
        if not cfg:
            self._last_rpc_context["status"] = -1
            return []
        order_id = str(data[1]).strip() if isinstance(data, list) and len(data) >= 2 and data[1] is not None else ""
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}, "card_orders": {}})
        tx_key = f"cardact:{self.profile_name}:{self.state['player']['PlayerId']}:{cid}:{uuid.uuid4()}"
        if order_id:
            ord_entry = cs.setdefault("card_orders", {}).get(order_id)
            if not isinstance(ord_entry, dict) or int(ord_entry.get("CardId", 0)) != cid:
                self._last_rpc_context["status"] = -1
                return []
            if ord_entry.get("status") == "completed":
                self._last_rpc_context["status"] = -1136
                return []
            ord_entry["status"] = "completed"
            ord_entry["completed_at"] = int(time.time())
            ord_entry["pray_tree_tracked"] = True
            ord_entry["period_economy_tracked"] = True
            tx_key = f"cardact:{self.profile_name}:{order_id}"
        now = int(time.time())
        cards = self.state.setdefault("month_cards", {})
        cur = cards.get(str(cid), {})
        base_exp = max(now, int(cur.get("ExpireTime", now)))
        cards[str(cid)] = {
            "CardId": cid,
            "ExpireTime": base_exp + int(cfg["continueTime"]) * 86400,
            "LastDailyDate": cur.get("LastDailyDate", ""),
            "BuyDrawn": False,
        }
        p = self.state["player"]
        self.ledger.apply_player_delta(
            p,
            self.profile_name,
            "VipEXP",
            int(cfg["price"]),
            source=f"card_activity:{cid}",
            idempotency_key=tx_key,
        )
        p["ChargeNum"] = int(p.get("ChargeNum", 0)) + int(cfg["price"])
        self._inc_stat("recharged_diamonds", int(cfg["price"]))
        self._record_period_economy(charged=int(cfg["price"]))
        self._record_pray_tree_recharge(int(cfg["price"]))
        self._record_slot_recharge(int(cfg["price"]))
        self._sync_player_recover_times(p)
        self.save()
        return self._card_list_payload()

    def _rpc_card_draw_daily(self, data: Any) -> dict[str, Any]:
        cid = int(data[0]) if isinstance(data, list) and data else 1
        cfg = CARD_MODEL_CFG.get(cid)
        now = self.now_ts()
        today = self.clock.today_str()
        cards = self.state.setdefault("month_cards", {})
        entry = cards.get(str(cid))
        if not cfg or not entry or int(entry.get("ExpireTime", 0)) <= now or entry.get("LastDailyDate") == today:
            self._last_rpc_context["status"] = -1
            return {}
        base_res = self._grant_resources_from_tuples(
            _parse_resource_str(cfg["dailyReward"]),
            source=f"card_daily:{cid}",
            tx_prefix=f"carddaily:{self.profile_name}:{self.state['player']['PlayerId']}:{cid}:{today}",
        )
        entry["LastDailyDate"] = today
        self.save()
        return {"BaseGetGameResourceList": base_res, "CardInfo": self._card_list_payload()}

    def _rpc_card_draw_buy(self, data: Any) -> dict[str, Any]:
        cid = int(data[0]) if isinstance(data, list) and data else 1
        cfg = CARD_MODEL_CFG.get(cid)
        now = int(time.time())
        cards = self.state.setdefault("month_cards", {})
        entry = cards.get(str(cid))
        if not cfg or not entry or int(entry.get("ExpireTime", 0)) <= now or entry.get("BuyDrawn"):
            self._last_rpc_context["status"] = -1
            return {}
        base_res = self._grant_resources_from_tuples(
            _parse_resource_str(cfg["buyReward"]),
            source=f"card_buy:{cid}",
            tx_prefix=f"cardbuy:{self.profile_name}:{self.state['player']['PlayerId']}:{cid}:{uuid.uuid4()}",
        )
        entry["BuyDrawn"] = True
        self.save()
        return {"BaseGetGameResourceList": base_res, "CardInfo": self._card_list_payload()}

    # ------------------------------------------------------------------
    # R6 Systems: RedDot, BossBattle, Arena (PVP/PVPShop), Daydayfund, StartWorkReward, Fashion
    # ------------------------------------------------------------------

    def _compute_red_dot_info(self) -> dict[str, int]:
        """Compute module red-dot flags (including StartWork 2718 and R7.5–R7.9 events)."""
        lv = int(self.state.get("player", {}).get("Lv", 1))
        now = self.now_ts()
        boss_state = self.state.get("boss_battle", {})
        alive_boss = any(
            int(b.get("CurHP", 0)) > 0 and int(b.get("AwayTime", 0)) > now
            for b in boss_state.get("bosses", [])
        )
        jifen = int(boss_state.get("jifen", 0))
        drawn = set(int(x) for x in boss_state.get("drawn_boxes", []))
        claimable_box = any(
            jifen >= int(row.get("needValue", 9999999)) and int(row.get("needValue", 0)) not in drawn
            for row in self.game_data.get("luckboss_value_shop", {}).values()
        )
        df = self.state.get("daydayfund", {})
        can_fund = lv >= 19 and (bool(df.get("if_draw", True)) or now >= int(df.get("cooled_time", 0)))
        today = self.clock.today_str()
        is_workday_window = self.clock.weekday() in (1, 2, 3, 4)
        claimed_days = self.state.get("startwork", {}).get("claimed_days", [])
        can_startwork = is_workday_window and (today not in claimed_days)

        # Equip compose red dot (ModuleSub.eEquip=1400 / eEquipCompare=1405) required by Guide 1 (BattleLayer.lua:2701)
        equips_cfg = self.game_data.get("equips", {})
        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Weapon", "Helmet", "Clothes", "Necklace")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        compose_buckets: dict[int, int] = {}
        for eq in self.state.get("equips", []):
            if eq.get("Id") in equipped_ids:
                continue
            clv = int(equips_cfg.get(str(eq.get("EquipModelId", 0)), {}).get("colorLV", 0))
            if clv in (1, 2, 3):
                compose_buckets[clv] = compose_buckets.get(clv, 0) + 1
        can_compose_equip = any(cnt >= 5 for cnt in compose_buckets.values())
        gem_models = self.game_data.get("gem_model", {})
        gems_by_id = {g["Id"]: g for g in self.state.get("gems", []) if g.get("Id")}
        battle_gem_ids = {
            entry["Id"]
            for slot in self.state.get("slots", [])
            for entry in (slot.get("Gem") or [])
            if isinstance(entry, dict) and entry.get("Id") and entry.get("Id") != EMPTY_ENTITY_ID
        }
        gem_compose_buckets: dict[int, int] = {}
        for g in gems_by_id.values():
            if g["Id"] in battle_gem_ids:
                continue
            mid = int(g.get("ModelId", 0))
            if int(gem_models.get(str(mid), {}).get("LV", 0)) < 15:
                gem_compose_buckets[mid] = gem_compose_buckets.get(mid, 0) + 1
        can_compose_gem = lv >= 40 and any(cnt >= 4 for cnt in gem_compose_buckets.values())
        st_payload = self._build_success_target_info() if lv >= 11 else {}
        has_success_claim = any(
            int(item.get("Sequence", 0)) > len([x for x in str(item.get("DrawNums", "")).split(",") if x.strip()])
            for item in st_payload.get("TargetList", [])
        )
        miaosha_rd = self._miaosha_red_dot()

        return {
            "1400": 1 if can_compose_equip else 0,
            "1405": 1 if can_compose_equip else 0,
            "1413": 1 if can_compose_gem else 0,
            "1700": self._friend_red_dot(),
            "1701": self._friend_sta_red_dot(),
            **self._email_red_dots(),
            "2203": 1 if (lv >= 18 and alive_boss) else 0,
            "2205": 1 if (lv >= 18 and claimable_box) else 0,
            "2303": self._xhzw_red_dot(),
            "2400": 1 if len(self._active_reward_center_entries()) > 0 else 0,
            "2503": self._gddh_red_dot(),
            "2504": self._ggzj_red_dot(),
            "2706": self._dinner_red_dot(),
            "2710": 1 if can_fund else 0,
            "2711": self._zcsf_red_dot(),
            "2712": self._month_sign_red_dot(),
            "2718": 1 if can_startwork else 0,
            "3000": self._daily_task_red_dot(),
            "3400": self._guild_red_dot(),
            "3402": self._guild_reward_red_dot(),
            "3403": self._guild_boss_red_dot(),
            "3700": 1 if self._build_online_reward_info() is not None else 0,
            "4300": 1,
            "4409": self._pray_tree_red_dot(),
            "4410": self._xssb_red_dot(),
            "4412": self._slot_red_dot(),
            "4426": self._smash_egg_red_dot(),
            "4432": self._money_tree_red_dot(),
            "4600": self._xxbz_red_dot(),
            "4700": self._critical_tasks_red_dot(),
            "4900": 1 if has_success_claim else 0,
            "5501": self._random_red_bag_red_dot(),
            "6800": self._timespike_red_dot(),
            "6900": self._bounty_red_dot(),
            "7000": miaosha_rd,
            "7001": miaosha_rd,
            "7002": miaosha_rd,
            "7800": self._yiyuan_red_dot(),
            "7900": self._opencontest_red_dot(),
            "8200": self._shiwan_red_dot(),
            "9300": self._timed_recruit_red_dot(),
        }

    # ------------------------- R7.4: SuccessTargetInfo (4900) -------------------------

    def _success_target_metrics(self, cur_day: int) -> tuple[dict[int, int], list[tuple[dict[str, Any], dict[str, Any]]], list[tuple[dict[str, Any], dict[str, Any]]]]:
        p = self.state["player"]
        stats = self.state.setdefault("stats", dict(DEFAULT_PLAYER_STATS))
        heroes_by_id = {str(h["Id"]): h for h in self.state.get("heroes", [])}
        heroes_cfg = self.game_data.get("heroes", {})
        equips_by_id = {str(e["Id"]): e for e in self.state.get("equips", [])}
        equips_cfg = self.game_data.get("equips", {})
        chapters = self.state.get("chapters", {})

        deployed_heroes: list[tuple[dict[str, Any], dict[str, Any]]] = []
        equipped_equips: list[tuple[dict[str, Any], dict[str, Any]]] = []
        by_eq_slot: dict[str, list[dict[str, Any]]] = {"Weapon": [], "Helmet": [], "Clothes": [], "Necklace": []}

        for slot in self.state.get("slots", []):
            hid = str(slot.get("HeroId", ""))
            if hid in heroes_by_id:
                h = heroes_by_id[hid]
                deployed_heroes.append((h, heroes_cfg.get(str(h.get("HeroModelId", 0)), {})))
            for skey in ("Weapon", "Helmet", "Clothes", "Necklace"):
                s_eq = slot.get(skey)
                if isinstance(s_eq, dict) and s_eq.get("Id") in equips_by_id:
                    eq = equips_by_id[s_eq["Id"]]
                    cfg = equips_cfg.get(str(eq.get("EquipModelId", 0)), {})
                    equipped_equips.append((eq, cfg))
                    by_eq_slot[skey].append(eq)

        cleared_ch = [int(cid) - 10 for cid, ch in chapters.items() if int(ch.get("IfPass", 0)) == 1]
        max_chapter_idx = max(cleared_ch) if cleared_ch else max(0, int(self.state.get("battle", {}).get("MaxChapterId", 11)) - 11)
        elite_cleared = [
            int(nid) - 10
            for nid, st in self.state.get("elite", {}).get("nodes", {}).items()
            if int(st.get("Flag", 0)) >= 2
        ]
        slot_slot_names = {37: "Weapon", 38: "Helmet", 39: "Clothes", 40: "Necklace"}

        scalars: dict[int, int] = {
            1: max_chapter_idx,
            2: int(p.get("Lv", 1)),
            3: max(cur_day, int(self.state.get("gift_login", {}).get("login_days", 1))),
            4: int(stats.get("soul_recruits", 0)),
            5: max((int(eq.get("Lv", 0)) for eq, _ in equipped_equips), default=0),
            6: sum(1 for _, hc in deployed_heroes if int(hc.get("quality", 0)) >= 15),
            9: max(int(stats.get("explore_count", 0)), int(self.state.get("explore", {}).get("DailyNum", 0))),
            10: int(stats.get("treasure_loot_wins", 0)),
            11: int(stats.get("pvp_fights", 0)),
            12: int(stats.get("callequip_count", 0)),
            13: int(stats.get("ggzj_wins", 0)),
            14: max(elite_cleared, default=0),
            15: sum(int(h.get("Lv", 1)) for h, _ in deployed_heroes),
            16: int(stats.get("mystery_refresh", 0)),
            17: int(stats.get("boss_fights", 0)),
            18: int(self.state.get("bdd", {}).get("max_stars", 0)),
            22: int(stats.get("daydayfund_count", 0)),
            23: int(stats.get("sta_pills_used", 0)),
            24: int(stats.get("vit_pills_used", 0)),
            25: int(stats.get("zcsf_count", 0)),
            26: int(stats.get("mystery_treasure_count", 0)),
            27: int(stats.get("teambattle_count", 0)),
            29: sum(1 for _, hc in deployed_heroes if int(hc.get("quality", 0)) >= 15),
            30: int(stats.get("gddh_fights", 0)),
            31: int(p.get("FAP", 0)),
            32: int(stats.get("wish_points", 0)),
            33: int(stats.get("mystery_treasure_max_dmg", 0)),
            34: max(int(stats.get("equip_lvup_count", 0)), sum(int(eq.get("Lv", 0)) for eq, _ in equipped_equips)),
            35: max(int(self.state.get("boss_battle", {}).get("jifen", 0)), int(p.get("BossCoin", 0))),
            36: int(stats.get("jade_search_count", 0)),
        }
        artifacts = self._compute_equip_artifact_state()[0]
        scalars[37] = int(artifacts["1"]["Lv"])
        scalars[38] = int(artifacts["2"]["Lv"])
        scalars[39] = int(artifacts["3"]["Lv"])
        scalars[40] = int(artifacts["4"]["Lv"])
        scalars[41] = max(scalars[37], scalars[38], scalars[39], scalars[40])
        return scalars, equipped_equips, deployed_heroes

    def _evaluate_success_row(
        self,
        tid: int,
        row: dict[str, Any],
        scalars: dict[int, int],
        equipped_equips: list[tuple[dict[str, Any], dict[str, Any]]],
        deployed_heroes: list[tuple[dict[str, Any], dict[str, Any]]],
    ) -> tuple[bool, int]:
        c1 = int(row.get("completeCondition1", 0))
        c2 = int(row.get("completeCondition2", 0))
        if tid == 19:
            equip_steps = self.game_data["equip_steps"]
            qualifying = {
                eq["Id"] for eq, cfg in equipped_equips
                if int(cfg.get("itemLv", 0))
                + equip_steps.get(str(eq["EquipModelId"]), {}).get(str(eq.get("Step", 0)), {}).get("itemLv", 0) >= c1
            }
            count = min(4, len(qualifying))
            return count == 4, count
        if c2 > 0:
            if tid == 5:
                val = sum(1 for eq, _ in equipped_equips if int(eq.get("Lv", 0)) >= c2)
            elif tid == 6:
                val = sum(1 for h, hc in deployed_heroes if int(hc.get("quality", 0)) >= 15 and int(h.get("Step", 0)) >= c2)
            elif tid == 29:
                val = sum(1 for h, hc in deployed_heroes if int(hc.get("quality", 0)) >= 15 and int(h.get("Lv", 0)) >= c2)
            else:
                val = scalars.get(tid, 0)
            return val >= c1, val
        val = scalars.get(tid, 0)
        return val >= c1, val

    def _build_success_target_info(self) -> dict[str, Any]:
        now = self.now_ts()
        st = self.state.setdefault(
            "success_target",
            {"start_ts": now, "drawn": {}, "drawn_days": [], "if_draw": 0, "exchange_counts": {}},
        )
        start_ts = int(st.get("start_ts", now))
        cur_day = max(1, 1 + max(0, now - start_ts) // 86400)
        if_draw = int(st.get("if_draw", 0))
        end_date = start_ts + 7 * 86400

        scalars, equipped_equips, deployed_heroes = self._success_target_metrics(cur_day)
        model_tbl = self.game_data.get("success_target_model", {})
        reward_tbl = self.game_data.get("success_target_reward", {})
        drawn_map = st.get("drawn", {})

        target_list: list[dict[str, Any]] = []
        day_finish: dict[int, int] = {d: 0 for d in range(1, 8)}
        day_total: dict[int, int] = {d: 0 for d in range(1, 8)}

        for tid_str in sorted(model_tbl.keys(), key=lambda x: int(x)):
            tid = int(tid_str)
            rows = sorted(reward_tbl.get(tid_str, []), key=lambda r: int(r.get("sequence", 0)))
            drawn_seqs = [int(x) for x in drawn_map.get(tid_str, [])]
            seq_info: dict[str, int] = {}
            claimable: dict[str, bool] = {}
            completed_count = 0

            for row in rows:
                seq = int(row.get("sequence", 0))
                aday = int(row.get("appearDay", 1))
                done, val = self._evaluate_success_row(tid, row, scalars, equipped_equips, deployed_heroes)
                seq_info[str(seq)] = val
                if 1 <= aday <= 7:
                    day_total[aday] += 1
                    if done or seq in drawn_seqs:
                        day_finish[aday] += 1
                unlocked = (aday <= 7 and aday <= cur_day) or (aday == 8 and (if_draw == 1 or cur_day >= 8))
                claimable[str(seq)] = unlocked and done and seq not in drawn_seqs
                if claimable[str(seq)] or seq in drawn_seqs:
                    completed_count += 1

            target_list.append(
                {
                    "TargetId": tid,
                    "Sequence": completed_count,
                    "ReachedNum": scalars.get(tid, 0),
                    "DrawNums": ",".join(str(x) for x in sorted(set(drawn_seqs))),
                    "SequenceInfo": seq_info,
                    "Claimable": claimable,
                }
            )

        drawn_days = set(int(d) for d in st.get("drawn_days", []))
        draw_day = [
            {
                "Day": d,
                "FinishTargetCount": day_finish[d],
                "TotalTargetCount": max(1, day_total[d]),
            }
            for d in range(1, min(7, cur_day) + 1)
            if d not in drawn_days and day_finish[d] > 0
        ]
        cur_cap_day = min(7, cur_day)
        return {
            "Day": cur_day,
            "EndDate": end_date,
            "IfDraw": int(bool(if_draw) or (cur_day >= 8 and not draw_day)),
            "FinishTargetCount": day_finish.get(cur_cap_day, 0),
            "TotalTargetCount": max(1, day_total.get(cur_cap_day, 1)),
            "DrawDay": draw_day,
            "DrawnDays": sorted(drawn_days),
            "TargetList": target_list,
        }

    def _rpc_success_target_get_info(self, _data: Any) -> dict[str, Any]:
        return self._build_success_target_info()

    def _rpc_success_target_draw_reward(self, data: Any) -> dict[str, Any]:
        try:
            tid, seq = int(data[0]), int(data[1])
        except (TypeError, ValueError, KeyError, IndexError):
            self._last_rpc_context["status"] = -3121
            return {}
        info = self._build_success_target_info()
        rows = self.game_data.get("success_target_reward", {}).get(str(tid), [])
        row = next((r for r in rows if int(r.get("sequence", 0)) == seq), None)
        if not row:
            self._last_rpc_context["status"] = -3121
            return {}
        st = self.state["success_target"]
        if seq in st.get("drawn", {}).get(str(tid), []):
            self._last_rpc_context["status"] = -3137
            return {}
        target = next((t for t in info["TargetList"] if t["TargetId"] == tid), None)
        if not target or not target["Claimable"].get(str(seq)):
            self._last_rpc_context["status"] = -6001
            return {}
        tuples = _parse_resource_str(str(row.get("resourceList", "")))
        if not self._can_receive_goods_outputs(tuples):
            return {}
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"success_target:{tid}:{seq}",
            tx_prefix=f"successtarget:{self.profile_name}:{tid}:{seq}",
        )
        st.setdefault("drawn", {}).setdefault(str(tid), []).append(seq)
        self.save()
        return {"BaseGetGameResourceList": base_res, "FinishTargetCount": info["FinishTargetCount"]}

    def _rpc_success_target_draw_total_reward(self, data: Any) -> dict[str, Any]:
        info = self._build_success_target_info()
        st = self.state["success_target"]
        drawn_days = set(int(d) for d in st.get("drawn_days", []))
        try:
            day = int(data[0]) if data else None
        except (TypeError, ValueError, KeyError, IndexError):
            self._last_rpc_context["status"] = -6004
            return {}
        if day in drawn_days or int(st.get("if_draw", 0)) == 1:
            self._last_rpc_context["status"] = -3137
            return {}
        targets = [entry for entry in info["DrawDay"] if day is None or entry["Day"] == day]
        if day is None and info["Day"] < 8 or day is not None and not targets:
            self._last_rpc_context["status"] = -6004
            return {}
        time_tbl = self.game_data.get("success_time_model", {})
        tuples: list[tuple[int, int, int]] = []
        for d_entry in targets:
            day_number = d_entry["Day"]
            t_cfg = next((v for v in time_tbl.values() if int(v.get("openDay", 0)) == day_number and not v.get("isSuccess")), None)
            if t_cfg:
                res_list = _parse_resource_str(str(t_cfg.get("resourceList", "")))
                if res_list:
                    rt, rm, rn = res_list[0]
                    scaled = math.ceil(int(d_entry["FinishTargetCount"]) / max(1, int(d_entry["TotalTargetCount"])) * rn)
                    tuples.append((rt, rm, scaled))
        if not self._can_receive_goods_outputs(tuples):
            return {}
        claimed_days = {entry["Day"] for entry in targets}
        remaining = [entry for entry in info["DrawDay"] if entry["Day"] not in claimed_days]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="success_target_total",
            tx_prefix=f"successtarget_total:{self.profile_name}:{self.state['player']['PlayerId']}:{day or 'final'}",
        )
        st["drawn_days"] = sorted(drawn_days | claimed_days)
        st["if_draw"] = int(info["Day"] >= 8 and not remaining)
        self.save()
        return {
            "BaseGetGameResourceList": base_res,
            "DrawDay": remaining,
            "DrawnDays": st["drawn_days"],
            "IfDraw": st["if_draw"],
        }

    def _iter_success_purchase_rows(self) -> list[dict[str, Any]]:
        purchase_tbl = self.game_data.get("success_purchase_model", {})
        rows: list[dict[str, Any]] = []
        for val in purchase_tbl.values():
            if not isinstance(val, dict):
                continue
            if "day" in val and "sequence" in val:
                rows.append(val)
            else:
                for sub in val.values():
                    if isinstance(sub, dict) and "day" in sub and "sequence" in sub:
                        rows.append(sub)
        return sorted(rows, key=lambda r: (int(r.get("day", 1)), int(r.get("sequence", 1))))

    def _rpc_success_target_get_exchange_info(self, _data: Any) -> dict[str, Any]:
        now = int(time.time())
        st = self.state.setdefault(
            "success_target",
            {"start_ts": now, "drawn": {}, "drawn_days": [], "if_draw": 0, "exchange_counts": {}},
        )
        end_date = int(st.get("start_ts", now)) + 7 * 86400
        ex_counts = st.get("exchange_counts", {})
        by_day: list[list[dict[str, Any]]] = [[] for _ in range(7)]
        for row in self._iter_success_purchase_rows():
            d = int(row.get("day", 1))
            seq = int(row.get("sequence", 1))
            if 1 <= d <= 7:
                cnt = int(ex_counts.get(f"{d}:{seq}", 0))
                by_day[d - 1].append({"Sequence": seq, "GlobalNum": cnt, "PersonalNum": cnt})
        return {"EndDate": end_date, "ActivityList": by_day}

    def _rpc_success_target_exchange(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        day = int(data[0])
        seq = int(data[1])
        row = next(
            (r for r in self._iter_success_purchase_rows() if int(r.get("day", 0)) == day and int(r.get("sequence", 0)) == seq),
            None,
        )
        if not row:
            self._last_rpc_context["status"] = -1
            return {}
        p = self.state["player"]
        cur_vip = int(p.get("VIPLv", p.get("Vip", 0)))
        if int(p.get("Lv", 1)) < int(row.get("needLv", 1)) or cur_vip < int(row.get("needVipLv", 0)):
            self._last_rpc_context["status"] = -1
            return {}
        st = self.state["success_target"]
        ex_counts = st.setdefault("exchange_counts", {})
        key = f"{day}:{seq}"
        cur_cnt = int(ex_counts.get(key, 0))
        if cur_cnt >= int(row.get("singleMax", 1)) or cur_cnt >= int(row.get("serverMax", 1)):
            self._last_rpc_context["status"] = -1
            return {}
        costs = _parse_resource_str(str(row.get("needresourceList", "")))
        attr_map = {1111: "Diamond", 1112: "Gold", 1115: "PVPCoin", 1116: "HeroCoin", 1120: "BossCoin"}
        for rt, rm, rn in costs:
            if rn <= 0:
                continue
            if rt in attr_map:
                field = attr_map[rt]
                if int(self.state["player"].get(field, 0)) < rn:
                    self._last_rpc_context["status"] = -1105 if rt == 1111 else -1
                    return {}
            elif rt >= 1500:
                g = next((x for x in self.state.get("goods", []) if int(x.get("GoodsModelId", 0)) == rm), None)
                if not g or int(g.get("Num", 0)) < rn:
                    self._last_rpc_context["status"] = -1
                    return {}
        for rt, rm, rn in costs:
            if rn <= 0:
                continue
            if rt in attr_map:
                self.ledger.apply_player_delta(
                    self.state["player"],
                    self.profile_name,
                    attr_map[rt],
                    -rn,
                    source=f"success_exchange:{day}:{seq}",
                )
            elif rt >= 1500:
                self._consume_goods(rm, rn)
        ex_counts[key] = cur_cnt + 1
        base_res = self._grant_resources_from_tuples(
            _parse_resource_str(str(row.get("resourceList", ""))),
            source=f"success_exchange:{day}:{seq}",
            tx_prefix=f"success_ex:{self.profile_name}:{day}:{seq}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _sync_boss_battle_state(self) -> dict[str, Any]:
        """Recover LuckBoss attack charges over time and prune defeated/expired bosses."""
        now = int(time.time())
        lb_cfg = self.game_data.get("luckboss_config", {})
        rec_cd = max(60, int(lb_cfg.get("attackNumRecoverTime", 1800)))
        vip_lv = int(self.state["player"].get("VIPLv", 0))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        max_atk = max(10, int(vip_cfg.get("attackLuckBossMaxNum", 10)))

        bs = self.state["boss_battle"]
        bs["bosses"] = [
            b for b in bs.get("bosses", []) if int(b.get("CurHP", 0)) > 0 and int(b.get("AwayTime", 0)) > now
        ]
        for b in bs["bosses"]:
            self._sanitize_boss_drop(b)
        atk_num = int(bs.get("attack_num", 10))
        rec_time = int(bs.get("recover_time", now + rec_cd))
        if atk_num < max_atk:
            if rec_time <= now:
                gained = 1 + (now - rec_time) // rec_cd
                atk_num = min(max_atk, atk_num + gained)
                bs["attack_num"] = atk_num
                bs["recover_time"] = (now + rec_cd) if atk_num < max_atk else now
            elif rec_time > now + rec_cd:
                bs["recover_time"] = now + rec_cd
        else:
            bs["recover_time"] = now
        bs["jifen"] = int(self.state["player"].get("BossCoin", bs.get("jifen", 0)))
        if "battle" in self.state:
            self.state["battle"]["HasBoss"] = "True" if bs["bosses"] else "False"
        return bs

    def _luckboss_is_double_jifen(self) -> bool:
        """Check LuckbossConfig double-point window (default 18:00-20:00 local time)."""
        lb_cfg = self.game_data.get("luckboss_config", {})
        begin_frac = float(lb_cfg.get("valueDoubleBeginTime1", 0.75))
        end_frac = float(lb_cfg.get("valueDoubleEndTime2", 0.833333333333))
        lt = time.localtime()
        frac = (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec) / 86400.0
        return begin_frac <= frac <= end_frac

    def _boss_info_payload(self, bs: dict[str, Any]) -> dict[str, Any]:
        return {
            "AttackNum": int(bs.get("attack_num", 0)),
            "RecoverTime": int(bs.get("recover_time", int(time.time()) + 1800)),
            "BuyCount": int(bs.get("buy_count", 0)),
            "JiFen": int(bs.get("jifen", 0)),
            "NextBoss": {
                "NCount": int(bs.get("next_boss_count", 10)),
                "BossModelId": int(bs.get("next_boss_model_id", 12010055)),
            },
        }

    def _maybe_trigger_luckboss(self, force: bool = False) -> str | None:
        """Spawn a LuckBoss on Lv>=18 battle victory (strictly inactive below Lv 18)."""
        lv = int(self.state["player"].get("Lv", 1))
        if lv < 18:
            return None
        bs = self._sync_boss_battle_state()
        bs["clear_counter"] = int(bs.get("clear_counter", 0)) + 1
        if len(bs["bosses"]) >= 3 and not force:
            return None

        ncount = int(bs.get("next_boss_count", 10))
        should_spawn = force or bs["clear_counter"] == 1 or ncount <= 1 or random.randint(1, 100) <= 35
        if not should_spawn:
            bs["next_boss_count"] = max(1, ncount - 1)
            return None

        if ncount <= 1 or bs["clear_counter"] % 5 == 0:
            model_id = int(bs.get("next_boss_model_id", 12010055))
            bs["next_boss_count"] = 10
            bs["next_boss_model_id"] = 12010055 if model_id == 12010054 else 12010054
        else:
            bs["next_boss_count"] = max(1, ncount - 1)
            tier_pool = [12010050, 12010051, 12010052] if lv < 25 else [12010051, 12010052, 12010053, 12010054]
            model_id = random.choice(tier_pool)

        tier_idx = max(0, model_id - 12010050)
        boss_lv = max(18, lv + min(3, tier_idx))
        hero_cfg = self.game_data["heroes"].get(str(model_id), self.game_data["heroes"]["12010050"])
        hp_mult = 18.0 + tier_idx * 6.0
        boss_obj = self._hero_fight_obj(
            hero_cfg,
            lv=boss_lv,
            is_boss=True,
            hp_mult=hp_mult,
            ap_mult=1.2 + tier_idx * 0.2,
            def_mult=1.1 + tier_idx * 0.15,
        )
        drop_res = self._boss_drop_for_model(model_id)
        now = int(time.time())
        boss_entry = {
            "Id": str(uuid.uuid4()),
            "PlayerId": str(self.state["player"]["PlayerId"]),
            "PlayerName": str(self.state["player"]["PlayerName"]),
            "BossModelId": model_id,
            "Name": f"Yêu Vương Bậc {tier_idx + 1}",
            "Lv": boss_lv,
            "CurHP": int(boss_obj["TotalHp"]),
            "TotalHP": int(boss_obj["TotalHp"]),
            "AwayTime": now + 7200,
            "CanHelpTime": 0,
            "DropResource": drop_res,
        }
        bs["bosses"].append(boss_entry)
        if "battle" in self.state:
            self.state["battle"]["HasBoss"] = "True"
        return boss_entry["Id"]

    def _build_boss_fight_info(self, boss: dict[str, Any], is_full: bool) -> dict[str, Any]:
        allies = self._build_ally_fight_objs()
        if is_full:
            up_r = float(self.game_data.get("luckboss_config", {}).get("alloutAttackAttrUpR", 30000)) / 10000.0
            for unit in allies:
                if unit:
                    unit["AP"] = max(1, int(unit.get("AP", 1) * up_r))
                    unit["RP"] = 100
        model_id = int(boss.get("BossModelId", 12010050))
        tier_idx = max(0, model_id - 12010050)
        cfg = self.game_data["heroes"].get(str(model_id), self.game_data["heroes"]["12010050"])
        boss_unit = self._hero_fight_obj(
            cfg,
            lv=int(boss.get("Lv", 18)),
            is_boss=True,
            hp_mult=18.0 + tier_idx * 6.0,
            ap_mult=1.2 + tier_idx * 0.2,
            def_mult=1.1 + tier_idx * 0.15,
        )
        boss_unit["TotalHp"] = int(boss["TotalHP"])
        boss_unit["HP"] = int(boss["CurHP"])
        enemies: list[dict[str, Any]] = [{}, boss_unit, {}, {}, {}, {}]
        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        enemy_fsp = int(boss_unit.get("FSP", 500))
        return {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": ally_fsp, "Fap": int(self.state["player"].get("FAP", 0))},
                        {"Fsp": enemy_fsp, "Fap": int(boss_unit["TotalHp"] + boss_unit["AP"] * 10 + boss_unit.get("DEF", 0) * 10)},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1, 999999),
                    "IsPVP": False,
                }
            ]
        }

    def _rpc_boss_get_boss_list(self, _data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        self.save()
        return {"BattleInfo": self._boss_info_payload(bs), "BossList": copy.deepcopy(bs["bosses"])}

    def _rpc_boss_get_boss_info(self, data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        boss_id = str(data[0]) if isinstance(data, list) and data else ""
        boss = next((b for b in bs["bosses"] if str(b["Id"]) == boss_id), None)
        if not boss:
            self._last_rpc_context["status"] = -1
            return {}
        return {"BattleInfo": self._boss_info_payload(bs), "BossInfo": copy.deepcopy(boss)}

    def _rpc_boss_get_fight_info(self, data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        boss_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        is_full = bool(int(data[1])) if isinstance(data, list) and len(data) >= 2 else False
        boss = next((b for b in bs["bosses"] if str(b["Id"]) == boss_id and int(b.get("CurHP", 0)) > 0), None)
        need_atk = 3 if is_full else 1
        need_vit = 15 if is_full else 5
        if not boss or int(bs["attack_num"]) < need_atk or int(self.state["player"].get("VIT", 0)) < need_vit:
            self._last_rpc_context["status"] = -1
            return {}
        fight_info = self._build_boss_fight_info(boss, is_full)
        bs["pending_fight"] = {"boss_id": boss["Id"], "is_full": is_full, "fight_info": fight_info}
        self.save()
        return {"FightInfo": fight_info}

    def _rpc_boss_fight(self, data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        boss_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        is_full = bool(int(data[1])) if isinstance(data, list) and len(data) >= 2 else False
        verify_raw = data[3] if isinstance(data, list) and len(data) >= 4 else None

        boss = next((b for b in bs["bosses"] if str(b["Id"]) == boss_id and int(b.get("CurHP", 0)) > 0), None)
        need_atk = 3 if is_full else 1
        need_vit = 15 if is_full else 5
        if not boss or int(bs["attack_num"]) < need_atk or int(self.state["player"].get("VIT", 0)) < need_vit:
            self._last_rpc_context["status"] = -1
            return {}

        bs["attack_num"] = int(bs["attack_num"]) - need_atk
        self._sync_boss_battle_state()
        self.ledger.apply_player_delta(
            self.state["player"], self.profile_name, "VIT", -need_vit, source=f"boss_vit:{boss_id}"
        )

        old_hp = int(boss["CurHP"])
        sim_boss_hp: int | None = None
        if verify_raw is not None:
            parsed = None
            if isinstance(verify_raw, str) and verify_raw.strip():
                try:
                    parsed = json.loads(verify_raw)
                except ValueError:
                    parsed = None
            elif isinstance(verify_raw, dict):
                parsed = verify_raw
            if isinstance(parsed, dict) and isinstance(parsed.get("hp"), list) and parsed["hp"]:
                last_wave = parsed["hp"][-1]
                if isinstance(last_wave, list):
                    for unit_hp in last_wave:
                        if isinstance(unit_hp, dict) and int(unit_hp.get("PosId", 0)) == 8:
                            sim_boss_hp = int(unit_hp.get("HP", old_hp))
                            break
        if sim_boss_hp is None:
            pending = bs.pop("pending_fight", None)
            if isinstance(pending, dict) and pending.get("boss_id") == boss_id and bool(pending.get("is_full")) == is_full:
                fight_info = pending["fight_info"]
            else:
                fight_info = self._build_boss_fight_info(boss, is_full)
            outcome = simulate_fight_info(fight_info, self.game_data["attacks"], buffs_cfg=self.game_data["combat_buffs"])
            last_wave = outcome.verify_data.get("hp", [[]])[-1]
            sim_boss_hp = next((int(u["HP"]) for u in last_wave if int(u.get("PosId", 0)) == 8), old_hp)
        else:
            bs.pop("pending_fight", None)

        new_hp = max(0, min(old_hp, int(sim_boss_hp)))
        hurt = old_hp - new_hp
        boss["CurHP"] = new_hp
        boss_exist = new_hp > 0
        if not boss_exist:
            bs["bosses"] = [b for b in bs["bosses"] if str(b["Id"]) != boss_id]

        jifen_gain = max(15, hurt // 150) + (120 if not boss_exist else 0)
        if self._luckboss_is_double_jifen():
            jifen_gain *= 2

        old_lv = int(self.state["player"]["Lv"])
        per_exp_pct = int(self.game_data.get("vit_config", {}).get("perGetEXPR", 20000))
        exp_gain = int(need_vit * old_lv * (per_exp_pct / 10000.0))
        tuples: list[tuple[int, int, int]] = [
            (1101, 0, exp_gain),
            (1112, 0, 1200 * need_atk),
            (1117, 0, 600 * need_atk),
            (1120, 0, jifen_gain),
        ]
        if not boss_exist and isinstance(boss.get("DropResource"), dict):
            dr = self._sanitize_boss_drop(boss)
            tuples.append((int(dr["TypeId"]), int(dr["ModelId"]), int(dr.get("Num", 1))))

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"boss_fight:{boss['BossModelId']}",
            tx_prefix=f"boss:{self.profile_name}:{boss_id}:{uuid.uuid4()}",
        )
        self.validate_base_resource_list(base_res, context="BossBattle.Fight")
        old_lv2, new_lv2 = self._sync_level_from_exp()
        if new_lv2 != old_lv2:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True

        self._inc_stat("boss_fights", need_atk)
        self._record_daily_task_progress(7, need_atk)
        self.save()
        return {
            "HurtValue": hurt,
            "SingleJiFen": jifen_gain,
            "BossExist": boss_exist,
            "BaseGetGameResourceList": base_res,
        }

    def _rpc_boss_box_list(self, _data: Any) -> list[dict[str, Any]]:
        bs = self._sync_boss_battle_state()
        drawn = set(int(x) for x in bs.get("drawn_boxes", []))
        rows = sorted(self.game_data.get("luckboss_value_shop", {}).values(), key=lambda r: int(r["needValue"]))
        return [
            {"NeedValue": int(row["needValue"]), "IsDraw": "True" if int(row["needValue"]) in drawn else "False"}
            for row in rows
        ]

    def _rpc_boss_draw_box(self, data: Any) -> dict[str, Any]:
        need_val = int(data[0]) if isinstance(data, list) and data else 0
        bs = self._sync_boss_battle_state()
        drawn = bs.setdefault("drawn_boxes", [])
        row = next(
            (r for r in self.game_data.get("luckboss_value_shop", {}).values() if int(r["needValue"]) == need_val),
            None,
        )
        if not row or need_val in drawn or int(bs.get("jifen", 0)) < need_val:
            self._last_rpc_context["status"] = -1
            return {}
        drawn.append(need_val)
        base_res = self._grant_resources_from_tuples(
            [(int(row["typeID"]), int(row["modelID"]), int(row["num"]))],
            source=f"boss_box:{need_val}",
            tx_prefix=f"boss_box:{self.profile_name}:{need_val}:{uuid.uuid4()}",
        )
        self.validate_base_resource_list(base_res, context="BossBattle.DrawBox")
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_boss_one_key_draw_box(self, _data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        jifen = int(bs.get("jifen", 0))
        drawn = bs.setdefault("drawn_boxes", [])
        rows = sorted(self.game_data.get("luckboss_value_shop", {}).values(), key=lambda r: int(r["needValue"]))
        tuples: list[tuple[int, int, int]] = []
        for row in rows:
            nv = int(row["needValue"])
            if nv <= jifen and nv not in drawn:
                drawn.append(nv)
                tuples.append((int(row["typeID"]), int(row["modelID"]), int(row["num"])))
        if not tuples:
            self._last_rpc_context["status"] = -1
            return {}
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="boss_one_key_box",
            tx_prefix=f"boss_box_all:{self.profile_name}:{uuid.uuid4()}",
        )
        self.validate_base_resource_list(base_res, context="BossBattle.OneKeyDrawBox")
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_boss_buy_count(self, data: Any) -> dict[str, Any]:
        count = max(1, min(20, int(data[0]) if isinstance(data, list) and data else 1))
        bs = self._sync_boss_battle_state()
        vip_lv = int(self.state["player"].get("VIPLv", 0))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        allow_buy = int(vip_cfg.get("allowBuyLuckBossFightNum", 10))
        cur_buy = int(bs.get("buy_count", 0))
        if cur_buy + count > allow_buy:
            self._last_rpc_context["status"] = -1
            return {}
        base_price = int(self.game_data.get("luckboss_config", {}).get("buyAttackNumBaseUseNum", 10))
        cost = sum(math.ceil((cur_buy + step) / 2) * base_price for step in range(1, count + 1))
        if int(self.state["player"].get("Diamond", 0)) < cost:
            self._last_rpc_context["status"] = -1
            return {}
        if cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"], self.profile_name, "Diamond", -cost, source=f"boss_buy_count:{count}"
            )
        bs["buy_count"] = cur_buy + count
        bs["attack_num"] = int(bs.get("attack_num", 0)) + count
        self._sync_boss_battle_state()
        self.save()
        return {"BuyCount": int(bs["buy_count"]), "AttackNum": int(bs["attack_num"])}

    def _rpc_boss_friend_help(self, data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        boss_id = str(data[0]) if isinstance(data, list) and data else ""
        boss = next((b for b in bs["bosses"] if str(b["Id"]) == boss_id), None)
        if not boss:
            self._last_rpc_context["status"] = -1
            return {}
        now = int(time.time())
        boss["CanHelpTime"] = now + 60
        social = self._social_state()
        for fid in social.get("friends", []):
            peer = self._find_peer_by_player_id(str(fid))
            if peer is not None:
                p_info = self.state["player"]
                with peer._lock:
                    peer._push_player_email(
                        1,
                        "Hỗ trợ Yêu Vương",
                        f"{p_info.get('PlayerName', 'Bạn bè')} kêu gọi hỗ trợ đánh Yêu Vương!",
                        send_player_id=str(p_info["PlayerId"]),
                        send_player_name=str(p_info.get("PlayerName", "Bạn bè")),
                        sub_module_id=2203,
                        head_image_id=0,
                        fashion_model_id=0,
                    )
                    peer.save()
        self.save()
        return {"CanHelpTime": int(boss["CanHelpTime"])}

    def _rpc_boss_jifen_ranking(self, _data: Any) -> list[dict[str, Any]]:
        bs = self._sync_boss_battle_state()
        p = self.state["player"]
        rows = [
            {
                "PlayerId": str(p["PlayerId"]),
                "Name": str(p["PlayerName"]),
                "Lv": int(p["Lv"]),
                "FAP": int(p.get("FAP", 0)),
                "JiFen": int(bs.get("jifen", 0)),
                "HeadImageId": int(p.get("HeadImageId", 12011004)),
            }
        ]
        npc_jifens = [3600, 2900, 2350, 1800, 1400, 950, 620, 380, 210]
        step = self._pvp_step_for_lv(int(p.get("Lv", 18)))
        for idx, score in enumerate(npc_jifens, start=1):
            bot = self._arena_bot_profile(idx * 50, step)
            rows.append(
                {
                    "PlayerId": bot["PlayerId"],
                    "Name": bot["Name"],
                    "Lv": bot["Lv"],
                    "FAP": bot["FAP"],
                    "JiFen": score,
                    "HeadImageId": bot["Slots"][0]["HeroModelId"],
                }
            )
        rows.sort(key=lambda r: (-int(r["JiFen"]), -int(r["FAP"])))
        for rank_idx, r in enumerate(rows, start=1):
            r["Id"] = rank_idx
        return rows

    # ------------------------- Arena (PVP & PVPShop) -------------------------

    @staticmethod
    def _pvp_step_for_lv(lv: int) -> int:
        if lv <= 30:
            return 1
        if lv <= 40:
            return 2
        if lv <= 50:
            return 3
        if lv <= 60:
            return 4
        return 5

    @staticmethod
    def _pvp_reward_window() -> tuple[int, int]:
        now_dt = time.localtime()
        midnight = int(time.time()) - (now_dt.tm_hour * 3600 + now_dt.tm_min * 60 + now_dt.tm_sec)
        start = midnight + 22 * 3600
        end = start + 300
        now = int(time.time())
        if now >= start:
            start += 86400
            end += 86400
        return start, end

    def _arena_bot_profile(self, rank: int, step: int) -> dict[str, Any]:
        """Deterministically construct a realistic Arena bot built from real heroes & equips."""
        rank = max(1, min(2000, int(rank)))
        step = max(1, min(5, int(step)))
        names = [
            "PhongKhuyển", "BạchSát", "TửVu", "HắcCửu", "KhuyểnDạXoa",
            "NgọcTứHồn", "PhongChiThủ", "MinhĐạoTàn", "ThiếtToáiNha", "ThiênSinhNha",
            "BấtYêuVương", "LamNgọc", "XíchNguyệt", "ĐoạnKiếm", "LôiThú",
            "HồĐiệpẢo", "VôẢnhNhẫn", "DạMaLâm", "BăngTinh", "ThanhLongẨn",
            "CổTỉnh", "PhongHuyệt", "TửTâm", "NgânLang", "HồngLiên",
            "TuyếtNữ", "ThầnLạc", "CànThú", "HoàngTuyền", "KỳLânẨn",
        ]
        guilds = ["Chiến Quốc", "Tây Quốc", "Hội Trừ Yêu", "Làng Phong", ""]
        base_lv_min = {1: 18, 2: 31, 3: 41, 4: 51, 5: 61}[step]
        base_lv_max = {1: 30, 2: 40, 3: 50, 4: 60, 5: 75}[step]
        # Stronger bots sit at lower numeric rank (rank 1 = strongest, rank 1500+ = entry Lv)
        ratio = max(0.0, min(1.0, (1600 - rank) / 1599.0))
        bot_lv = min(80, max(16, int(round(base_lv_min + (base_lv_max - base_lv_min) * (ratio ** 1.35)))))

        if rank <= 20:
            slot_count = 6
            step_up = 3 + step
            eq_tier = min(7, 5 + (step >= 3))
            hero_pool = [12011004, 12012005, 12011002, 12011003, 12011005, 12011007, 12011008, 12011020]
        elif rank <= 200:
            slot_count = 5
            step_up = 2 + step
            eq_tier = 5
            hero_pool = [12011004, 12011005, 12011006, 12011007, 12011008, 12011011, 12011019, 12011022]
        elif rank <= 900:
            slot_count = 5 if bot_lv >= 22 else 4
            step_up = 1 + step
            eq_tier = 4
            hero_pool = [12011005, 12011006, 12011007, 12011009, 12011012, 12011014, 12011016, 12011018]
        elif rank <= 1350:
            slot_count = 4
            step_up = 1
            eq_tier = 3
            hero_pool = [12011009, 12011012, 12011013, 12011023, 12011024, 12011026, 12011028, 12011030]
        else:
            slot_count = 3 if rank >= 1480 else 4
            step_up = 0 if rank >= 1460 else 1
            eq_tier = 2 if rank >= 1460 else 3
            hero_pool = [12011023, 12011025, 12011027, 12011033, 12011034, 12011035, 12011036, 12011037]

        equip_by_color = {
            1: (13010130, 13020130, 13030130, 13040130),
            2: (13010215, 13020215, 13030215, 13040215),
            3: (13010314, 13020314, 13030314, 13040314),
            4: (13010404, 13020404, 13030404, 13040404),
            5: (13010503, 13020503, 13030503, 13040503),
            6: (13010602, 13020602, 13030602, 13040602),
            7: (13010701, 13020701, 13030701, 13040701),
        }
        eq_set = equip_by_color.get(eq_tier, equip_by_color[3])
        eq_lv = max(1, int(bot_lv * (1.5 if rank <= 200 else 1.0 if rank <= 1350 else 0.5)))

        rng = random.Random(step * 10000 + rank)
        chosen_models = [hero_pool[(rank + i * 3 + rng.randint(0, 2)) % len(hero_pool)] for i in range(slot_count)]
        # Deduplicate while keeping order
        seen_m: set[int] = set()
        unique_models: list[int] = []
        for hm in chosen_models + hero_pool:
            if hm not in seen_m and str(hm) in self.game_data["heroes"]:
                seen_m.add(hm)
                unique_models.append(hm)
            if len(unique_models) >= slot_count:
                break

        bot_player_id = _det_uuid(f"arena_bot:{step}:{rank}")
        slots: list[dict[str, Any]] = []
        heroes_by_id: dict[str, dict[str, Any]] = {}
        embattle: dict[str, int] = {f"Formation{i}": 0 for i in range(1, 7)}
        total_fap = 0
        for s_idx in range(1, 7):
            if s_idx <= len(unique_models):
                hm = unique_models[s_idx - 1]
                h_id = _det_uuid(f"bot_hero:{step}:{rank}:{s_idx}")
                h_inst = self._build_hero_instance(hm, lv=bot_lv, step=step_up, inst_id=h_id)
                heroes_by_id[h_id] = h_inst
                eq_keys = ("Weapon", "Helmet", "Clothes", "Necklace")
                slot: dict[str, Any] = {
                    "SlotId": s_idx,
                    "HeroId": h_id,
                    "HeroModelId": hm,
                    "GemId": EMPTY_ENTITY_ID,
                    "NewWraithId": EMPTY_ENTITY_ID,
                    "StarId": 0,
                    "Book": None,
                    "Horse": None,
                    "Hero": h_inst,
                }
                for ek_idx, ek in enumerate(eq_keys):
                    em_id = eq_set[ek_idx]
                    slot[ek] = {
                        "Id": _det_uuid(f"bot_eq:{step}:{rank}:{s_idx}:{ek}"),
                        "EquipModelId": em_id,
                        "Lv": eq_lv,
                        "Gold": 0,
                        "ExtraCount": 0,
                        "APExtra": 0,
                        "HPExtra": 0,
                        "DEFExtra": 0,
                        "DAMADDExtra": 0,
                        "DAMCUTExtra": 0,
                    }
                prop = self._compute_slot_property(slot, heroes_by_id, include_player_star=False)
                slot["Property"] = prop
                total_fap += int(prop["FAP"])
                embattle[f"Formation{s_idx}"] = s_idx
            else:
                slot = {
                    "SlotId": s_idx,
                    "HeroId": EMPTY_ENTITY_ID,
                    "HeroModelId": 0,
                    "Weapon": None,
                    "Helmet": None,
                    "Clothes": None,
                    "Necklace": None,
                    "Book": None,
                    "Horse": None,
                    "GemId": EMPTY_ENTITY_ID,
                    "NewWraithId": EMPTY_ENTITY_ID,
                    "StarId": 0,
                    "Property": _zero_slot_property(),
                }
            slots.append(slot)

        base_name = names[(rank + step * 7) % len(names)]
        bot_name = base_name if rank <= 30 else f"{base_name}{rank}"
        return {
            "PlayerId": bot_player_id,
            "Lv": bot_lv,
            "Name": bot_name,
            "FAP": total_fap,
            "Rank": rank,
            "Step": step,
            "Guild": guilds[(rank + step) % len(guilds)],
            "FashionModelId": 0,
            "Slots": slots,
            "Embattle": embattle,
            "HeroesById": heroes_by_id,
        }

    def _build_bot_formation_view(self, bot: dict[str, Any]) -> dict[str, Any]:
        return {
            "PlayerInfo": {
                "PlayerId": bot["PlayerId"],
                "Name": bot["Name"],
                "Lv": bot["Lv"],
                "StarId": 0,
                "FashionModelId": int(bot.get("FashionModelId", 0)),
                "FAP": bot["FAP"],
            },
            "SlotInfo": bot["Slots"],
            "SlotInfos": bot["Slots"],
            "MateInfos": [],
            "SlotFormationInfo": bot["Embattle"],
            "SkillInfos": [],
            "CombatPet": None,
        }

    def _bot_slot_formations(self, target_id: str) -> dict[str, Any] | None:
        p = self.state["player"]
        cur_step = self._pvp_step_for_lv(int(p.get("Lv", 20)))
        for st in (cur_step, 1, 2, 3, 4, 5):
            # Probe current rank list candidates & top 50 quickly
            pvp = self.state.get("pvp", {})
            probe_ranks = list(range(1, 31)) + list(range(50, 2001, 50))
            pr = int(pvp.get("rank", 1500))
            probe_ranks.extend(self._candidate_arena_ranks(pr, int(pvp.get("refresh_seed", 1))))
            for r in set(probe_ranks):
                if _det_uuid(f"arena_bot:{st}:{r}") == target_id:
                    return self._build_bot_formation_view(self._arena_bot_profile(r, st))
        return self._gddh_bot_slot_formations(target_id) or self._social_npc_slot_formations(target_id)

    def _arena_bot_fight_objs(self, bot: dict[str, Any]) -> list[dict[str, Any]]:
        enemies: list[dict[str, Any]] = [{} for _ in range(6)]
        slots_by_id = {int(s["SlotId"]): s for s in bot["Slots"]}
        emb = bot["Embattle"]
        heroes_by_id = bot["HeroesById"]
        for f_idx in range(1, 7):
            s_id = int(emb.get(f"Formation{f_idx}", f_idx))
            slot = slots_by_id.get(s_id)
            if slot and slot.get("HeroModelId"):
                hm = int(slot["HeroModelId"])
                cfg = self.game_data["heroes"][str(hm)]
                inst = heroes_by_id.get(str(slot["HeroId"]), {})
                enemies[f_idx - 1] = self._hero_fight_obj(
                    cfg,
                    is_boss=False,
                    step=int(inst.get("Step", 0)),
                    reborn_step=int(inst.get("RebornStep", 0)),
                    reborn_id=int(inst.get("RebornId", 0)),
                    override_stats=slot["Property"],
                )
        return enemies

    def _candidate_arena_ranks(self, player_rank: int, refresh_seed: int) -> list[int]:
        if player_rank <= 1:
            return [1, 2, 3, 4, 5, 6]
        ranks: set[int] = {1, 2, 3, player_rank}
        rng = random.Random(player_rank * 97 + refresh_seed)
        if player_rank <= 15:
            for r in range(1, min(21, player_rank + 4)):
                ranks.add(r)
        else:
            step_spans = [320, 210, 140, 90, 55, 32, 18, 8, 1]
            prev = player_rank
            for idx, delta in enumerate(step_spans):
                jitter = rng.randint(0, max(0, delta // 4)) if idx < len(step_spans) - 1 else 0
                cand = max(4, min(prev - 1, player_rank - delta + jitter))
                ranks.add(cand)
                prev = cand
            ranks.add(min(2000, player_rank + 1))
            ranks.add(min(2000, player_rank + 2))
        return sorted(r for r in ranks if 1 <= r <= 2000)

    def _self_arena_entry(self, rank: int) -> dict[str, Any]:
        p = self.state["player"]
        slot_heroes = [
            {"Id": int(s["SlotId"]), "HeroModelId": int(s["HeroModelId"])}
            for s in self.state["slots"]
            if int(s.get("HeroModelId", 0)) > 0
        ]
        return {
            "PlayerId": str(p["PlayerId"]),
            "Lv": int(p["Lv"]),
            "Name": str(p["PlayerName"]),
            "FAP": int(p.get("FAP", 0)),
            "Rank": rank,
            "Guild": "",
            "FashionModelId": int(p.get("FashionModelId", 0)),
            "IfAllowRank": 0,
            "SlotHeroModelIdList": slot_heroes,
        }

    def _build_arena_rank_list(self, step: int, player_rank: int, refresh_seed: int) -> list[dict[str, Any]]:
        ranks_set = set(self._candidate_arena_ranks(player_rank, refresh_seed))
        for peer in self._get_peer_s1_profiles():
            pr = int(peer.state.get("pvp", {}).get("rank", 1500))
            if 1 <= pr <= 2000:
                ranks_set.add(pr)
        ranks = sorted(ranks_set)
        out: list[dict[str, Any]] = []
        for r in ranks:
            if r == player_rank:
                out.append(self._self_arena_entry(r))
            else:
                allow = 1 if (r < player_rank and (r >= 4 or player_rank <= 20)) else 0
                peer = self._find_peer_by_arena_rank(r)
                if peer is not None:
                    entry = peer._self_arena_entry(r)
                    entry["IfAllowRank"] = allow
                    out.append(entry)
                else:
                    bot = self._arena_bot_profile(r, step)
                    out.append(
                        {
                            "PlayerId": bot["PlayerId"],
                            "Lv": bot["Lv"],
                            "Name": bot["Name"],
                            "FAP": bot["FAP"],
                            "Rank": r,
                            "Guild": bot["Guild"],
                            "FashionModelId": bot["FashionModelId"],
                            "IfAllowRank": allow,
                            "SlotHeroModelIdList": [
                                {"Id": int(s["SlotId"]), "HeroModelId": int(s["HeroModelId"])}
                                for s in bot["Slots"]
                                if int(s.get("HeroModelId", 0)) > 0
                            ],
                        }
                    )
        out.sort(key=lambda item: int(item["Rank"]))
        return out

    def _pvp_current_reward(self, step: int, rank: int) -> list[dict[str, int]]:
        step_tbl = self.game_data.get("pvp_rank_reward", {}).get(str(step), {})
        row = step_tbl.get(str(min(2000, max(1, rank))), {"PVPCoin": 100, "rawGold": 500})
        return [
            {"ResourceTypeSub": 1115, "ModelId": 0, "Num": int(row.get("PVPCoin", 100))},
            {"ResourceTypeSub": 1112, "ModelId": 0, "Num": int(row.get("rawGold", 500))},
        ]

    def _pvp_shop_list_payload(self) -> list[dict[str, Any]]:
        pvp = self.state["pvp"]
        today = self.clock.today_str()
        daily_map = pvp.setdefault("shop_bought_daily", {})
        if daily_map.get("_date") != today:
            daily_map.clear()
            daily_map["_date"] = today
        total_map = pvp.setdefault("shop_bought_total", {})
        items = sorted(self.game_data.get("pvp_shop", {}).values(), key=lambda x: int(x["ID"]))
        out: list[dict[str, Any]] = []
        for row in items:
            sid = int(row["ID"])
            out.append(
                {
                    "ShopId": sid,
                    "TypeId": int(row["typeID"]),
                    "ModelId": int(row["modelID"]),
                    "Num": int(row["num"]),
                    "NeedStep": int(row["needStep"]),
                    "NeedRank": int(row["needRank"]),
                    "NeedPVPCoin": int(row["needPVPCoin"]),
                    "PerMaxNum": int(row["perMaxNum"]),
                    "TotalMaxNum": int(row["totalMaxNum"]),
                    "BuyNum": int(daily_map.get(str(sid), 0)),
                    "BuyTotalNum": int(total_map.get(str(sid), 0)),
                }
            )
        return out

    def _calc_upgrade_rank_diamonds(self, old_rank: int, old_step: int, new_rank: int) -> int:
        if new_rank >= old_rank:
            return 0
        first_tbl = self.game_data.get("pvp_first_reward", {})

        def _reward_at(step: int, rank: int) -> int:
            rec = first_tbl.get(str(step), {}).get(str(rank))
            if not rec and step > 1:
                rec = first_tbl.get(str(step - 1), {}).get("1")
            if not rec:
                return 0
            total = 0
            for rt, _rm, cnt in _parse_resource_str(str(rec.get("firstReward", ""))):
                if rt == 1111:
                    total += cnt
            return total

        return max(0, _reward_at(old_step, new_rank) - _reward_at(old_step, old_rank))

    def _rpc_pvp_get_info(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        pvp = self.state["pvp"]
        step = self._pvp_step_for_lv(int(p.get("Lv", 20)))
        if step > int(pvp.get("history_max_step", 1)):
            pvp["history_max_step"] = step
        rank = int(pvp.get("rank", 1500))
        r_start, r_end = self._pvp_reward_window()
        self.save()
        return {
            "RefreshDate": int(pvp.get("refresh_date", 0)),
            "PVPCoin": int(p.get("PVPCoin", 0)),
            "RewardTimeStart": r_start,
            "RewardTimeEnd": r_end,
            "Rank": rank,
            "HistoryMaxStep": int(pvp.get("history_max_step", step)),
            "HistoryMaxRank": int(pvp.get("history_max_rank", rank)),
            "CurrentReward": self._pvp_current_reward(step, rank),
            "RankList": self._build_arena_rank_list(step, rank, int(pvp.get("refresh_seed", 1))),
            "PVPShopInfo": self._pvp_shop_list_payload(),
        }

    def _rpc_pvp_refresh(self, _data: Any) -> dict[str, Any]:
        pvp = self.state["pvp"]
        now = int(time.time())
        if now < int(pvp.get("refresh_date", 0)):
            self._last_rpc_context["status"] = -1
            return {}
        pvp["refresh_seed"] = int(pvp.get("refresh_seed", 1)) + 1
        pvp["refresh_date"] = now + 5
        step = self._pvp_step_for_lv(int(self.state["player"].get("Lv", 20)))
        rank = int(pvp.get("rank", 1500))
        self.save()
        return {
            "RefreshDate": int(pvp["refresh_date"]),
            "RankList": self._build_arena_rank_list(step, rank, int(pvp["refresh_seed"])),
        }

    def _rpc_pvp_fight(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        pvp = self.state["pvp"]
        lv = int(p.get("Lv", 1))
        if lv < 20 or not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        target_id = str(data[0])
        target_rank = int(data[1])
        sta_cost = int(self.game_data.get("sta_config", {}).get("perUseNum", 2))
        if int(p.get("STA", 0)) < sta_cost:
            self._last_rpc_context["status"] = -1
            return {}

        step = self._pvp_step_for_lv(lv)
        peer = self._find_peer_by_player_id(target_id) or self._find_peer_by_arena_rank(target_rank)
        if peer is not None:
            target_rank = int(peer.state.get("pvp", {}).get("rank", target_rank))
            target_pid = str(peer.state["player"]["PlayerId"])
            target_name = str(peer.state["player"].get("PlayerName", "Peer"))
            target_fap = int(peer.state["player"].get("FAP", 0))
            enemies = peer._build_ally_fight_objs()
        else:
            bot = self._arena_bot_profile(target_rank, step)
            if bot["PlayerId"] != target_id:
                # Resolve matching bot rank if client sent slightly stale rank
                for probe in self._candidate_arena_ranks(int(pvp.get("rank", 1500)), int(pvp.get("refresh_seed", 1))):
                    cand = self._arena_bot_profile(probe, step)
                    if cand["PlayerId"] == target_id:
                        bot = cand
                        target_rank = probe
                        break
            target_pid = str(bot["PlayerId"])
            target_name = str(bot["Name"])
            target_fap = int(bot["FAP"])
            enemies = self._arena_bot_fight_objs(bot)

        allies = self._build_ally_fight_objs()
        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        enemy_fsp = sum(int(u.get("FSP", 0)) for u in enemies if u)
        fight_info = {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": ally_fsp, "Fap": int(p.get("FAP", 0))},
                        {"Fsp": enemy_fsp, "Fap": target_fap},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1, 999999),
                    "IsPVP": True,
                }
            ]
        }

        self.ledger.apply_player_delta(p, self.profile_name, "STA", -sta_cost, source=f"pvp_sta:{target_rank}")
        outcome = simulate_fight_info(fight_info, self.game_data["attacks"], buffs_cfg=self.game_data["combat_buffs"])
        is_win = 1 if outcome.won else 0
        self._inc_stat("pvp_fights", 1)
        self._record_daily_task_progress(5, 1)
        if is_win:
            self._inc_stat("pvp_wins", 1)

        old_rank = int(pvp.get("rank", 1500))
        old_max_rank = int(pvp.get("history_max_rank", old_rank))
        new_rank = min(old_rank, target_rank) if is_win else old_rank
        pvp["rank"] = new_rank
        if is_win and peer is not None and target_rank < old_rank:
            with peer._lock:
                peer_pvp = peer.state.setdefault("pvp", {})
                peer_pvp["rank"] = old_rank
                peer._push_player_email(
                    2,
                    "Chiến báo Đấu Trường",
                    f"{p.get('PlayerName', 'Đối thủ')} đã đánh bại bạn tại Đấu Trường (Hạng {target_rank} → {old_rank}).",
                    send_player_id=str(p["PlayerId"]),
                    send_player_name=str(p.get("PlayerName", "Đối thủ")),
                    sub_module_id=2502,
                    head_image_id=0,
                    fashion_model_id=0,
                )
                peer.save()

        breakthrough_diamond = 0
        if is_win and new_rank < old_max_rank:
            breakthrough_diamond = self._calc_upgrade_rank_diamonds(old_max_rank, step, new_rank)
            pvp["history_max_rank"] = new_rank
        if step > int(pvp.get("history_max_step", 1)):
            pvp["history_max_step"] = step

        per_exp_pct = int(self.game_data.get("sta_config", {}).get("perGetEXPR", 20000))
        exp_gain = int(sta_cost * lv * (per_exp_pct / 10000.0))
        arena_mult = self._timed_welfare_mult(4413, default=1)
        pvp_coin_gain = ((40 + max(0, (1600 - target_rank) // 100)) if is_win else 15) * arena_mult
        gold_gain = (1500 + lv * 50) if is_win else 500
        tuples: list[tuple[int, int, int]] = [
            (1101, 0, exp_gain),
            (1115, 0, pvp_coin_gain),
            (1112, 0, gold_gain),
        ]
        if breakthrough_diamond > 0:
            tuples.append((1111, 0, breakthrough_diamond))

        choice_cards: list[dict[str, Any]] = []
        if is_win:
            tuples.append((1605, 16050001, 5))
            choice_cards = [
                {"ResourceTypeSub": 1605, "ModelId": 16050001, "Num": 5, "IsDrop": 1},
                {"ResourceTypeSub": 1112, "ModelId": 0, "Num": 5000, "IsDrop": 0},
                {"ResourceTypeSub": 1115, "ModelId": 0, "Num": 30, "IsDrop": 0},
            ]

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"pvp_fight:{target_rank}:{'win' if is_win else 'lose'}",
            tx_prefix=f"pvp:{self.profile_name}:{target_rank}:{uuid.uuid4()}",
        )
        old_lv2, new_lv2 = self._sync_level_from_exp()
        if new_lv2 != old_lv2:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True

        history = pvp.setdefault("history", [])
        history.append(
            {
                "Timestamp": int(time.time()),
                "TargetPlayerId": target_pid,
                "TargetName": target_name,
                "TargetRank": target_rank,
                "OldRank": old_rank,
                "NewRank": new_rank,
                "IsWin": is_win,
                "DiamondBonus": breakthrough_diamond,
            }
        )
        if len(history) > 30:
            pvp["history"] = history[-30:]

        self.save()
        return {
            "Rank": new_rank,
            "HistoryMaxRank": int(pvp["history_max_rank"]),
            "HistoryMaxStep": int(pvp["history_max_step"]),
            "PVPCoin": int(p.get("PVPCoin", 0)),
            "IsWinFight": is_win,
            "RankList": self._build_arena_rank_list(step, new_rank, int(pvp.get("refresh_seed", 1))),
            "CurrentReward": self._pvp_current_reward(step, new_rank),
            "BaseGetGameResourceList": base_res,
            "ChoiceGetGameResource": choice_cards,
            "FightInfo": fight_info,
        }

    def _rpc_pvp_top_rank_list(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        pvp = self.state["pvp"]
        my_step = self._pvp_step_for_lv(int(p.get("Lv", 20)))
        my_rank = int(pvp.get("rank", 1500))
        top_steps: list[dict[str, Any]] = []
        for st in range(1, 6):
            rank_entries: list[dict[str, Any]] = []
            for r in range(1, 21):
                if st == my_step and r == my_rank:
                    rank_entries.append(self._self_arena_entry(r))
                else:
                    peer = self._find_peer_by_arena_rank(r) if st == my_step else None
                    if peer is not None:
                        rank_entries.append(peer._self_arena_entry(r))
                    else:
                        bot = self._arena_bot_profile(r, st)
                        rank_entries.append(
                            {
                                "PlayerId": bot["PlayerId"],
                                "Lv": bot["Lv"],
                                "Name": bot["Name"],
                                "FAP": bot["FAP"],
                                "Rank": r,
                                "Guild": bot["Guild"],
                                "FashionModelId": 0,
                                "IfAllowRank": 0,
                                "SlotHeroModelIdList": [
                                    {"Id": int(s["SlotId"]), "HeroModelId": int(s["HeroModelId"])}
                                    for s in bot["Slots"]
                                    if int(s.get("HeroModelId", 0)) > 0
                                ],
                            }
                        )
            top_steps.append({"RankList": rank_entries})
        return {"TopRankList": top_steps}

    def _rpc_account_list(self, _data: Any) -> dict[str, Any]:
        if self.account_manager is None:
            return {"ActiveAccountId": "acct_1", "Accounts": []}
        return self.account_manager.list_s1_accounts(ensure_slots=3)

    def _rpc_account_switch(self, data: Any) -> dict[str, Any]:
        if self.account_manager is None:
            self._last_rpc_context["status"] = -1
            return {}
        target_acct = str(data[0]) if isinstance(data, list) and data else "acct_1"
        return self.account_manager.switch_s1_account(target_acct)

    def _rpc_account_create(self, data: Any) -> dict[str, Any]:
        if self.account_manager is None:
            self._last_rpc_context["status"] = -1
            return {}
        label = str(data[0]) if isinstance(data, list) and data and data[0] else None
        return self.account_manager.create_s1_account(label=label)

    def _rpc_account_export(self, data: Any) -> dict[str, Any]:
        if self.account_manager is None:
            self._last_rpc_context["status"] = -1
            return {}
        dest = str(data[0]) if isinstance(data, list) and data and data[0] else None
        return self.account_manager.export_save_bundle(dest_path=dest)

    def _rpc_account_import(self, data: Any) -> dict[str, Any]:
        if self.account_manager is None:
            self._last_rpc_context["status"] = -1
            return {}
        src = str(data[0]) if isinstance(data, list) and data and data[0] else None
        confirm = bool(data[1]) if isinstance(data, list) and len(data) > 1 else True
        return self.account_manager.import_save_bundle(source_path=src, confirm=confirm)

    def _rpc_pvp_shop_buy(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        shop_id = int(data[0])
        num = max(1, int(data[1]))
        row = self.game_data.get("pvp_shop", {}).get(str(shop_id))
        if not row:
            self._last_rpc_context["status"] = -1
            return {}

        p = self.state["player"]
        pvp = self.state["pvp"]
        step = self._pvp_step_for_lv(int(p.get("Lv", 20)))
        need_step = int(row.get("needStep", 1))
        need_rank = int(row.get("needRank", 0))
        if step < need_step or (step == need_step and need_rank > 0 and int(pvp.get("history_max_rank", 1500)) > need_rank):
            self._last_rpc_context["status"] = -1
            return {}

        today = self.clock.today_str()
        daily_map = pvp.setdefault("shop_bought_daily", {})
        if daily_map.get("_date") != today:
            daily_map.clear()
            daily_map["_date"] = today
        total_map = pvp.setdefault("shop_bought_total", {})
        cur_daily = int(daily_map.get(str(shop_id), 0))
        cur_total = int(total_map.get(str(shop_id), 0))
        per_max = int(row.get("perMaxNum", 0))
        tot_max = int(row.get("totalMaxNum", 0))
        if per_max > 0 and cur_daily + num > per_max:
            self._last_rpc_context["status"] = -1
            return {}
        if tot_max > 0 and cur_total + num > tot_max:
            self._last_rpc_context["status"] = -1
            return {}

        cost = int(row.get("needPVPCoin", 0)) * num
        if int(p.get("PVPCoin", 0)) < cost:
            self._last_rpc_context["status"] = -1
            return {}
        if cost > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "PVPCoin", -cost, source=f"pvp_shop:{shop_id}")
        daily_map[str(shop_id)] = cur_daily + num
        total_map[str(shop_id)] = cur_total + num

        base_res = self._grant_resources_from_tuples(
            [(int(row["typeID"]), int(row["modelID"]), int(row["num"]) * num)],
            source=f"pvp_shop_buy:{shop_id}",
            tx_prefix=f"pvp_shop:{self.profile_name}:{shop_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_pvp_shop_reset_daily(self, _data: Any = None) -> dict[str, Any]:
        """Reset daily Arena shop limits (perMaxNum) while preserving one-time totalMaxNum purchases."""
        pvp = self.state.setdefault("pvp", {})
        pvp["shop_bought_daily"] = {"_date": self.clock.today_str()}
        self.save()
        return {"PVPShopList": self._pvp_shop_list_payload()}

    # ------------------------- Phase D: Daydayfund, StartWorkReward, Fashion -------------------------

    def _rpc_daydayfund_get_info(self, _data: Any) -> dict[str, Any]:
        df = self.state["daydayfund"]
        return {
            "Multiple": int(df.get("last_multiple", 0)),
            "CooledTime": int(df.get("cooled_time", 0)),
            "IfDraw": bool(df.get("if_draw", True)),
            "HarvestList": list(df.get("harvest_list", []))[-10:],
        }

    def _rpc_daydayfund_invest(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        lv = int(p.get("Lv", 1))
        df = self.state["daydayfund"]
        if lv < 19 or not bool(df.get("if_draw", True)):
            self._last_rpc_context["status"] = -1
            return {}
        dm = self.game_data.get("daydayfund_model", {})
        base_fund = int(dm.get("baseFund", 100))
        if int(p.get("Gold", 0)) < base_fund:
            self._last_rpc_context["status"] = -1
            return {}
        self.ledger.apply_player_delta(p, self.profile_name, "Gold", -base_fund, source="daydayfund_invest")
        m_min = int(dm.get("multipleMin", 30)) * lv
        m_max = int(dm.get("multipleMax", 60)) * lv
        mult = random.randint(m_min, max(m_min, m_max))
        df["last_multiple"] = mult
        df["cooled_time"] = 0
        df["if_draw"] = False
        self._inc_stat("daydayfund_count", 1)
        self.save()
        return {
            "Multiple": mult,
            "CooledTime": 0,
            "IfDraw": False,
            "HarvestList": list(df.get("harvest_list", []))[-10:],
        }

    def _rpc_daydayfund_harvest(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        df = self.state["daydayfund"]
        now = int(time.time())
        if bool(df.get("if_draw", True)) or now < int(df.get("cooled_time", 0)):
            self._last_rpc_context["status"] = -1
            return {}
        dm = self.game_data.get("daydayfund_model", {})
        base_fund = int(dm.get("baseFund", 100))
        mult = max(1, int(df.get("last_multiple", 30)))
        vip_lv = int(p.get("VIPLv", 0))
        vip_row = self.game_data.get("daydayfund_vip", {}).get(str(vip_lv), {})
        vip_pct = int(vip_row.get("mutipleR", 100)) / 100.0
        gold_gain = int(base_fund * mult * vip_pct)
        tuples: list[tuple[int, int, int]] = [(1112, 0, gold_gain)]
        if mult % 10 == 8:
            tuples.extend(_parse_resource_str(str(dm.get("specialReward", "1111,0,50"))))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"daydayfund_harvest:{mult}",
            tx_prefix=f"daydayfund:{self.profile_name}:{uuid.uuid4()}",
        )
        h_list = df.setdefault("harvest_list", [])
        h_list.append({"PlayerName": str(p["PlayerName"]), "Multiple": mult})
        if len(h_list) > 20:
            df["harvest_list"] = h_list[-20:]
        df["if_draw"] = True
        df["last_multiple"] = 0
        df["cooled_time"] = 0
        self.save()
        return {
            "Multiple": mult,
            "CooledTime": 0,
            "IfDraw": True,
            "HarvestList": list(df["harvest_list"])[-10:],
            "BaseGetGameResourceList": base_res,
        }

    def _startwork_schedule(self) -> dict[str, dict[str, Any]]:
        return {
            str(d): {
                "Diamond": 50 * d,
                "Multiple": 2 if d == 1 else 1,
                "Resource": [{"ResourceTypeSub": 1112, "ModelId": 0, "Count": 10000 * d}],
            }
            for d in (1, 2, 3, 4)
        }

    def _rpc_startwork_get_info(self, _data: Any) -> dict[str, Any]:
        return {"StartWorkReward": [self._startwork_schedule()]}

    def _rpc_startwork_get_reward(self, _data: Any) -> dict[str, Any]:
        sw = self.state["startwork"]
        today = self.clock.today_str()
        claimed = sw.setdefault("claimed_days", [])
        if today in claimed:
            self._last_rpc_context["status"] = -1
            return {}
        wday = self.clock.weekday()  # 1=Mon .. 7=Sun
        sched = self._startwork_schedule()
        entry = sched.get(str(wday if 1 <= wday <= 4 else 1))
        tuples = [(1111, 0, int(entry["Diamond"]) * int(entry["Multiple"]))]
        for r in entry["Resource"]:
            tuples.append((int(r["ResourceTypeSub"]), int(r["ModelId"]), int(r["Count"])))
        claimed.append(today)
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"startwork:{today}",
            tx_prefix=f"startwork:{self.profile_name}:{today}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_fashion_dress_up(self, data: Any) -> dict[str, Any]:
        entity_id = str(data[0]) if isinstance(data, list) and data else EMPTY_ENTITY_ID
        if entity_id == EMPTY_ENTITY_ID:
            self.state["player"]["FashionModelId"] = 0
            self.save()
            return {"FashionModelId": 0}
        target = next((f for f in self.state.get("fashions", []) if str(f["Id"]) == entity_id), None)
        if not target:
            self._last_rpc_context["status"] = -1
            return {}
        self.state["player"]["FashionModelId"] = int(target["FashionModelId"])
        self.save()
        return {"FashionModelId": int(target["FashionModelId"])}

    def _rpc_fashion_step_up(self, data: Any) -> dict[str, Any]:
        entity_id = str(data[0]) if isinstance(data, list) and data else ""
        target = next((f for f in self.state.get("fashions", []) if str(f["Id"]) == entity_id), None)
        if not target:
            self._last_rpc_context["status"] = -1
            return {}
        mid = str(target["FashionModelId"])
        step = int(target.get("Step", 0))
        step_row = self.game_data.get("fashion_step", {}).get(mid, {}).get(str(step))
        next_row = self.game_data.get("fashion_step", {}).get(mid, {}).get(str(step + 1))
        if not step_row or not next_row or not step_row.get("stepUpUse"):
            self._last_rpc_context["status"] = -1
            return {}
        costs = _parse_resource_str(str(step_row["stepUpUse"]))
        p = self.state["player"]
        for rt, rm, cnt in costs:
            if rt == 1112 and int(p.get("Gold", 0)) < cnt:
                self._last_rpc_context["status"] = -1
                return {}
            elif rt == 1111 and int(p.get("Diamond", 0)) < cnt:
                self._last_rpc_context["status"] = -1
                return {}
            elif rt not in (1111, 1112):
                have = sum(int(g.get("Num", 0)) for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == rm)
                if have < cnt:
                    self._last_rpc_context["status"] = -1
                    return {}
        for rt, rm, cnt in costs:
            if rt == 1112:
                self.ledger.apply_player_delta(p, self.profile_name, "Gold", -cnt, source=f"fashion_step:{mid}")
            elif rt == 1111:
                self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -cnt, source=f"fashion_step:{mid}")
            else:
                need = cnt
                for g in list(self.state["goods"]):
                    if int(g.get("GoodsModelId", 0)) == rm and need > 0:
                        take = min(int(g["Num"]), need)
                        g["Num"] = int(g["Num"]) - take
                        need -= take
                self.state["goods"] = [g for g in self.state["goods"] if int(g.get("Num", 0)) > 0]
                self._mark_goods_changed(rm)
        target["Step"] = step + 1
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"FashionInfo": copy.deepcopy(target)}

    def _rpc_fashion_resolve(self, data: Any) -> dict[str, Any]:
        entity_id = str(data[0]) if isinstance(data, list) and data else ""
        target = next((f for f in self.state.get("fashions", []) if str(f["Id"]) == entity_id), None)
        if not target:
            self._last_rpc_context["status"] = -1
            return {}
        mid = str(target["FashionModelId"])
        same_count = sum(1 for f in self.state.get("fashions", []) if str(f["FashionModelId"]) == mid)
        if same_count < 2 or (int(self.state["player"].get("FashionModelId", 0)) == int(mid) and same_count < 2):
            self._last_rpc_context["status"] = -1
            return {}
        fm = self.game_data.get("fashion_model", {}).get(mid, {})
        tuples = _parse_resource_str(str(fm.get("decompose", "")))
        self.state["fashions"] = [f for f in self.state["fashions"] if str(f["Id"]) != entity_id]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"fashion_resolve:{mid}",
            tx_prefix=f"fashion_resolve:{self.profile_name}:{entity_id}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # ------------------------- R7.2: Refine, MysteryShop, Glory, GiftLv, GiftLogin -------------------------

    def _rpc_hero_refine(self, data: Any) -> dict[str, Any]:
        """Disassemble idle fodder heroes (e.g. Tamotu 12013054 from Guide 7 / 2071)."""
        raw_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        req_ids = [str(x) for x in raw_ids if x]
        if not req_ids:
            self._last_rpc_context["status"] = -1
            return {}
        deployed_ids = self._deployed_hero_ids()
        heroes_by_id = {str(h["Id"]): h for h in self.state.get("heroes", [])}
        heroes_cfg = self.game_data.get("heroes", {})
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hid in req_ids:
            if hid in seen or hid in deployed_ids:
                continue
            h = heroes_by_id.get(hid)
            if not h:
                continue
            cfg = heroes_cfg.get(str(h.get("HeroModelId", 0)), {})
            if int(cfg.get("specialType", 0)) == 255 or not cfg.get("outputResource"):
                continue
            seen.add(hid)
            targets.append(h)
        if not targets:
            self._last_rpc_context["status"] = -1
            return {}

        totals: dict[tuple[int, int], int] = {}
        remove_ids = {h["Id"] for h in targets}
        for h in targets:
            cfg = heroes_cfg.get(str(h["HeroModelId"]), {})
            for rtype, rmodel, rnum in _parse_resource_str(str(cfg.get("outputResource", ""))):
                if rnum > 0:
                    totals[(rtype, rmodel)] = totals.get((rtype, rmodel), 0) + rnum
        tuples: list[tuple[int, int, int]] = [(rt, rm, rn) for (rt, rm), rn in totals.items()]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="hero_refine",
            tx_prefix=f"hero_refine:{self.profile_name}:{uuid.uuid4()}",
        )
        self.state["heroes"] = [h for h in self.state.get("heroes", []) if h["Id"] not in remove_ids]
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_equip_refine(self, data: Any) -> dict[str, Any]:
        """Disassemble unequipped equipment items for their config outputResource/Gold."""
        raw_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        req_ids = [str(x) for x in raw_ids if x]
        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Weapon", "Helmet", "Clothes", "Necklace")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        equips_by_id = {str(e["Id"]): e for e in self.state.get("equips", [])}
        equips_cfg = self.game_data.get("equips", {})
        targets = [equips_by_id[eid] for eid in dict.fromkeys(req_ids) if eid in equips_by_id and eid not in equipped_ids]
        if not targets:
            self._last_rpc_context["status"] = -1
            return {}
        tuples: list[tuple[int, int, int]] = []
        for eq in targets:
            cfg = equips_cfg.get(str(eq.get("EquipModelId", 0)), {})
            tuples.extend(_parse_resource_str(str(cfg.get("outputResource", ""))))
            if int(eq.get("Gold", 0)) > 0:
                tuples.append((1112, 0, int(eq["Gold"])))
        remove_ids = {e["Id"] for e in targets}
        self.state["equips"] = [e for e in self.state.get("equips", []) if e["Id"] not in remove_ids]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="equip_refine",
            tx_prefix=f"equip_refine:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_treasure_refine(self, data: Any) -> dict[str, Any]:
        """Disassemble unequipped treasures for their config outputResource."""
        raw_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        req_ids = [str(x) for x in raw_ids if x]
        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Book", "Horse")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        tr_by_id = {str(t["Id"]): t for t in self.state.get("treasures", [])}
        tr_cfg = self.game_data.get("treasures", {})
        targets = [tr_by_id[tid] for tid in dict.fromkeys(req_ids) if tid in tr_by_id and tid not in equipped_ids]
        if not targets:
            self._last_rpc_context["status"] = -1
            return {}
        tuples: list[tuple[int, int, int]] = []
        for tr in targets:
            cfg = tr_cfg.get(str(tr.get("TreasureModelId", 0)), {})
            tuples.extend(_parse_resource_str(str(cfg.get("outputResource", ""))))
        remove_ids = {t["Id"] for t in targets}
        self.state["treasures"] = [t for t in self.state.get("treasures", []) if t["Id"] not in remove_ids]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="treasure_refine",
            tx_prefix=f"treasure_refine:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # ------------------------- R7.6: Treasure LvUp/StepUp & Hero/Equip/Treasure Rebirth -------------------------

    def _sync_slot_treasures(self) -> None:
        treasures_by_id = {t["Id"]: t for t in self.state.get("treasures", [])}
        for slot in self.state.get("slots", []):
            for tkey in ("Book", "Horse"):
                s_tr = slot.get(tkey)
                if isinstance(s_tr, dict) and s_tr.get("Id") in treasures_by_id:
                    tr = treasures_by_id[s_tr["Id"]]
                    s_tr["Lv"] = int(tr.get("Lv", 0))
                    s_tr["Step"] = int(tr.get("Step", 0))
                    s_tr["EXP"] = int(tr.get("EXP", 0))
        self._recalc_all_slots_and_fap()

    def _treasure_lv_for_exp(self, treasure_model_id: int, exp_total: int, max_lv: int) -> int:
        tm = self.game_data.get("treasures", {}).get(str(treasure_model_id), {})
        exp_r = float(tm.get("expR", 1.0))
        if exp_r <= 0:
            return 0
        lv_tbl = self.game_data.get("treasure_lv", {})
        cur_lv = 0
        for lv in range(1, max(1, max_lv) + 1):
            row = lv_tbl.get(str(lv))
            if not row:
                break
            req_exp = int(round(float(row.get("baseExpTotal", 0)) * exp_r))
            if exp_total >= req_exp:
                cur_lv = lv
            else:
                break
        return cur_lv

    def _rpc_treasure_lv_up(self, data: Any) -> dict[str, Any]:
        """Consume unequipped fodder treasures/EXP items to strengthen target Treasure (ModuleSub 1402)."""
        entity_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        mat_ids = [str(x) for x in (data[1] if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list) else []) if x]
        tr = next((t for t in self.state.get("treasures", []) if str(t.get("Id")) == entity_id), None)
        if not tr or not mat_ids:
            self._last_rpc_context["status"] = -1
            return {}

        treasures_cfg = self.game_data.get("treasures", {})
        tm = treasures_cfg.get(str(tr.get("TreasureModelId", 0)), {})
        max_lv = int(tm.get("maxLV", 100))
        if int(tr.get("Lv", 0)) >= max_lv or float(tm.get("expR", 0)) <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Book", "Horse")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        tr_by_id = {str(t["Id"]): t for t in self.state.get("treasures", [])}
        consumed: list[dict[str, Any]] = []
        gain_exp = 0
        seen: set[str] = set()
        for mid in mat_ids:
            if mid in seen or mid == entity_id or mid in equipped_ids:
                continue
            mat = tr_by_id.get(mid)
            if not mat:
                continue
            mcfg = treasures_cfg.get(str(mat.get("TreasureModelId", 0)), {})
            base_exp = int(mcfg.get("baseExp", 1000))
            gain_exp += max(0, base_exp + int(mat.get("EXP", 0)))
            seen.add(mid)
            consumed.append(mat)
        if not consumed or gain_exp <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        self.state["treasures"] = [t for t in self.state.get("treasures", []) if str(t["Id"]) not in seen]
        new_exp = int(tr.get("EXP", 0)) + gain_exp
        tr["EXP"] = new_exp
        tr["Lv"] = self._treasure_lv_for_exp(int(tr["TreasureModelId"]), new_exp, max_lv)
        self._inc_stat("treasure_lvup_count", 1)
        self._sync_slot_treasures()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {
            "Id": tr["Id"],
            "TreasureModelId": int(tr["TreasureModelId"]),
            "Lv": int(tr["Lv"]),
            "Step": int(tr.get("Step", 0)),
            "EXP": int(tr["EXP"]),
        }

    def _rpc_treasure_step_up(self, data: Any) -> dict[str, Any]:
        """Advance Treasure Step using duplicate card or Substitute Stone (ModuleSub 1404)."""
        entity_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        mat_ids = [str(x) for x in (data[1] if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list) else []) if x]
        # VN Lua TreasureExtraLayer sends data[2]=0 with [] for Substitute Stone, or data[2]=1 with [dupe_id,...] for duplicate cards.
        if_sub = len(mat_ids) == 0

        tr = next((t for t in self.state.get("treasures", []) if str(t.get("Id")) == entity_id), None)
        if not tr:
            self._last_rpc_context["status"] = -1
            return {}
        tm = self.game_data.get("treasures", {}).get(str(tr.get("TreasureModelId", 0)), {})
        cur_step = int(tr.get("Step", 0))
        max_step = int(tm.get("maxStep", 0))
        if max_step <= 0 or cur_step >= max_step:
            self._last_rpc_context["status"] = -1
            return {}

        val_lv = int(tm.get("valueLv", 5))
        step_row = self.game_data.get("treasure_step", {}).get(str(val_lv * 1000 + cur_step))
        if not step_row or int(tr.get("Lv", 0)) < int(step_row.get("needLv", 0)):
            self._last_rpc_context["status"] = -1
            return {}

        extra_reqs = _parse_resource_str(str(step_row.get("upUseExtraStr", "")))
        sub_reqs = _parse_resource_str(str(step_row.get("upUseBaseSubStr", "")))
        need_cards = int(step_row.get("upUseBaseCardNum", 0))

        # Validate costs before mutating state
        cost_tuples: list[tuple[int, int, int]] = list(extra_reqs)
        if if_sub:
            if not bool(tm.get("ifSub", True)):
                self._last_rpc_context["status"] = -1
                return {}
            cost_tuples.extend(sub_reqs)
        for rt, rm, rn in cost_tuples:
            if rt == 1112 and int(self.state["player"].get("Gold", 0)) < rn:
                self._last_rpc_context["status"] = -1
                return {}
            if rt >= 1500:
                g = next((x for x in self.state.get("goods", []) if int(x["GoodsModelId"]) == rm), None)
                if not g or int(g.get("Num", 0)) < rn:
                    self._last_rpc_context["status"] = -1
                    return {}

        dupe_consumed: list[dict[str, Any]] = []
        if not if_sub and need_cards > 0:
            equipped_ids = {
                slot[k]["Id"]
                for slot in self.state.get("slots", [])
                for k in ("Book", "Horse")
                if isinstance(slot.get(k), dict) and slot[k].get("Id")
            }
            tr_by_id = {str(t["Id"]): t for t in self.state.get("treasures", [])}
            for mid in mat_ids:
                if len(dupe_consumed) >= need_cards:
                    break
                if mid == entity_id or mid in equipped_ids or any(c["Id"] == mid for c in dupe_consumed):
                    continue
                cand = tr_by_id.get(mid)
                if cand and int(cand.get("TreasureModelId", 0)) == int(tr["TreasureModelId"]):
                    dupe_consumed.append(cand)
            if len(dupe_consumed) < need_cards:
                self._last_rpc_context["status"] = -1
                return {}

        used_log = tr.setdefault("step_materials_used", [])
        for rt, rm, rn in cost_tuples:
            if rn <= 0:
                continue
            if rt == 1112:
                self.ledger.apply_player_delta(
                    self.state["player"],
                    self.profile_name,
                    "Gold",
                    -rn,
                    source=f"treasure_step_up:{tr['TreasureModelId']}",
                )
                used_log.append([1112, 0, rn])
            elif rt >= 1500:
                for g in self.state.get("goods", []):
                    if int(g["GoodsModelId"]) == rm:
                        g["Num"] = max(0, int(g["Num"]) - rn)
                        self._mark_goods_changed(rm)
                        break
                used_log.append([rt, rm, rn])

        if dupe_consumed:
            rm_ids = {str(c["Id"]) for c in dupe_consumed}
            self.state["treasures"] = [t for t in self.state.get("treasures", []) if str(t["Id"]) not in rm_ids]
            tr_type = int(tm.get("typeID", 1401))
            used_log.append([tr_type, int(tr["TreasureModelId"]), len(dupe_consumed)])

        tr["Step"] = cur_step + 1
        self._inc_stat("treasure_step_up_count", 1)
        self._sync_slot_treasures()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {
            "Id": tr["Id"],
            "TreasureModelId": int(tr["TreasureModelId"]),
            "Lv": int(tr.get("Lv", 0)),
            "Step": int(tr["Step"]),
            "EXP": int(tr.get("EXP", 0)),
        }

    def _rebirth_target_id(self, data: Any) -> str:
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, list) and first:
                return str(first[0])
            return str(first)
        return ""

    def _rpc_hero_rebirth(self, data: Any) -> dict[str, Any]:
        """Reset non-deployed upgraded Hero back to Lv 1 Step 0 and refund HeroEXP, Gold, Stones, and dupes."""
        hero_id = self._rebirth_target_id(data)
        deployed_ids = self._deployed_hero_ids()
        hero = next((h for h in self.state.get("heroes", []) if str(h.get("Id")) == hero_id), None)
        if not hero or hero_id in deployed_ids:
            self._last_rpc_context["status"] = -1
            return {}

        cur_lv = int(hero.get("Lv", 1))
        cur_step = int(hero.get("Step", 0))
        cur_reborn = int(hero.get("RebornStep", 0))
        cfg = self.game_data.get("heroes", {}).get(str(hero["HeroModelId"]), {})
        base_reborn_id = self._hero_reborn_class_id(cfg) * 1000
        has_reborn_progress = (
            int(hero.get("RebornId", base_reborn_id)) > base_reborn_id
            or any(int(s.get("Status", 0)) == 1 for s in (hero.get("RebornStepInfo") or []))
        )
        if cur_lv <= 1 and cur_step <= 0 and cur_reborn <= 0 and not has_reborn_progress and int(hero.get("LiantiLv", 0)) <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        quality = str(int(cfg.get("quality", 15)))
        rb_tbl = self.game_data.get("hero_rebirth", {}).get(quality, {})
        dia_cost = int(rb_tbl.get(str(cur_step), {}).get("useDiamond", 0)) + int(
            rb_tbl.get(str(cur_reborn), {}).get("useDiamond", 0)
        )
        if int(self.state["player"].get("Diamond", 0)) < dia_cost:
            self._last_rpc_context["status"] = -1
            return {}
        if dia_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -dia_cost,
                source=f"hero_rebirth:{hero['HeroModelId']}",
            )

        refund_tuples: list[tuple[int, int, int]] = []
        val_lv = int(cfg.get("valueLv", 3))
        gold_ratio = int(self.game_data.get("hero_config", {}).get("LVUpUseGoldR", 10000)) / 10000.0
        hero_lv_tbl = self.game_data.get("hero_lv", {})
        base_exp = int(hero_lv_tbl.get(str(val_lv * 1000 + 1), {}).get("EXPTotal", 0))
        cur_exp = int(hero_lv_tbl.get(str(val_lv * 1000 + cur_lv), {}).get("EXPTotal", base_exp))
        soul_refund = max(0, cur_exp - base_exp)
        gold_refund = int(soul_refund * gold_ratio)
        if soul_refund > 0:
            refund_tuples.append((1117, 0, soul_refund))
        if gold_refund > 0:
            refund_tuples.append((1112, 0, gold_refund))

        step_cls = int(cfg.get("stepUpClassID", 0))
        hero_step_tbl = self.game_data.get("hero_step", {})
        for s_idx in range(cur_step):
            row = hero_step_tbl.get(str(step_cls * 1000 + s_idx))
            if not row:
                continue
            refund_tuples.extend(_parse_resource_str(str(row.get("upUse", ""))))
            use_dupes = int(row.get("useNum", 0))
            if use_dupes > 0:
                refund_tuples.append((1201, int(hero["HeroModelId"]), use_dupes))
        refund_tuples.extend(self._hero_reborn_refund_tuples(hero))

        hero["Lv"] = 1
        hero["EXP"] = 0
        hero["Step"] = 0
        hero["RebornId"] = base_reborn_id
        hero["RebornStepInfo"] = _default_reborn_step_info(base_reborn_id)
        hero["RebornStep"] = 0
        hero["LiantiLv"] = 0
        hero["HP"] = int(cfg.get("HPBase", hero.get("HP", 100)))
        hero["AP"] = int(cfg.get("APBase", hero.get("AP", 20)))
        hero["DEF"] = int(cfg.get("DEFBase", hero.get("DEF", 10)))

        base_res = (
            self._grant_resources_from_tuples(
                refund_tuples,
                source=f"hero_rebirth:{hero['HeroModelId']}",
                tx_prefix=f"hero_rebirth:{self.profile_name}:{hero_id}:{uuid.uuid4()}",
            )
            if refund_tuples
            else []
        )
        self._inc_stat("rebirth_count", 1)
        self.save()
        return {"HeroInfo": copy.deepcopy(hero), "BaseGetGameResourceList": base_res}

    def _rpc_equip_rebirth(self, data: Any) -> dict[str, Any]:
        """Reset unequipped gear and return its enhancement and recorded step costs."""
        equip_id = self._rebirth_target_id(data)
        eq = next((e for e in self.state.get("equips", []) if str(e.get("Id")) == equip_id), None)
        if not eq:
            return self._reject_resource_change(-1301)
        if equip_id in self._equipped_item_ids():
            return self._reject_resource_change(-1304)

        cur_lv = int(eq.get("Lv", 0))
        cur_step = int(eq.get("Step", 0))
        if cur_lv <= 0 and cur_step <= 0:
            return self._reject_resource_change(-1308)

        cfg = self.game_data.get("equips", {}).get(str(eq["EquipModelId"]), {})
        quality = str(int(cfg.get("quality", 30)))
        rb_tbl = self.game_data.get("equip_rebirth", {}).get(quality, {})
        if str(cur_step) not in rb_tbl:
            return self._reject_resource_change(-1308)
        dia_cost = rb_tbl[str(cur_step)]["useDiamond"]
        player = self.state["player"]
        if int(player.get("Diamond", 0)) < dia_cost:
            return self._reject_resource_change(-1105)

        clv = str(int(cfg.get("colorLV", 1)))
        lv_tbl = self.game_data.get("equip_lv_up", {}).get(clv, {})
        computed_gold = sum(int(lv_tbl.get(str(lv_i), {}).get("lvUpUseNum", 0)) for lv_i in range(cur_lv))
        refund_gold = max(int(eq.get("Gold", 0)), computed_gold)
        materials = eq.get("StepMaterials", [])
        refund_gold += sum(material["Gold"] for material in materials)
        refunds = [(1112, 0, refund_gold)] if refund_gold > 0 else []
        refunds.extend((self.game_data["equips"][str(material["ModelId"])]["typeID"], material["ModelId"], 1)
                       for material in materials)

        def rebirth():
            source = f"equip_rebirth:{eq['EquipModelId']}"
            if dia_cost:
                self.ledger.apply_player_delta(player, self.profile_name, "Diamond", -dia_cost, source=source)
                self._last_rpc_context["diamond_spent"] = dia_cost
            eq.update(Lv=0, Step=0, Gold=0)
            eq.pop("StepMaterials", None)
            output = self._grant_resources_from_tuples(
                refunds, source=source, tx_prefix=f"{source}:{equip_id}:{uuid.uuid4()}",
            ) if refunds else []
            self._inc_stat("rebirth_count", 1)
            return {"EquipInfo": copy.deepcopy(eq), "BaseGetGameResourceList": output}

        return self._commit_resource_change(rebirth)

    def _treasure_exp_refund_tuples(self, tm: dict[str, Any], tr: dict[str, Any]) -> list[tuple[int, int, int]]:
        """Convert accumulated Treasure EXP (or Lv floor if EXP==0) into fodder refund tuples."""
        tr_type = int(tm.get("typeID", 1401))
        cur_exp = int(tr.get("EXP", 0))
        cur_lv = int(tr.get("Lv", 0))
        if cur_exp <= 0 and cur_lv > 0:
            row = self.game_data.get("treasure_lv", {}).get(str(cur_lv), {})
            cur_exp = int(round(float(row.get("baseExpTotal", 0)) * float(tm.get("expR", 0.5))))
        if cur_exp <= 0:
            return []
        refund_tuples: list[tuple[int, int, int]] = []
        gold_fodder = 14021304 if tr_type == 1402 else 14011304
        silver_fodder = 14020803 if tr_type == 1402 else 14010803
        base_fodder = 14020501 if tr_type == 1402 else 14010501
        g_cnt = cur_exp // 40000
        rem = cur_exp % 40000
        s_cnt = rem // 10000
        b_cnt = (rem % 10000 + 999) // 1000
        if g_cnt > 0:
            refund_tuples.append((tr_type, gold_fodder, g_cnt))
        if s_cnt > 0:
            refund_tuples.append((tr_type, silver_fodder, s_cnt))
        if b_cnt > 0:
            refund_tuples.append((tr_type, base_fodder, b_cnt))
        return refund_tuples

    def _rpc_treasure_rebirth(self, data: Any) -> dict[str, Any]:
        """Reset unequipped Treasure back to Lv 0 Step 0 EXP 0 and refund EXP fodders + Step materials."""
        tr_id = self._rebirth_target_id(data)
        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Book", "Horse")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        tr = next((t for t in self.state.get("treasures", []) if str(t.get("Id")) == tr_id), None)
        if not tr or tr_id in equipped_ids:
            self._last_rpc_context["status"] = -1
            return {}

        cur_lv = int(tr.get("Lv", 0))
        cur_step = int(tr.get("Step", 0))
        cur_exp = int(tr.get("EXP", 0))
        if cur_lv <= 0 and cur_step <= 0 and cur_exp <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        tm = self.game_data.get("treasures", {}).get(str(tr["TreasureModelId"]), {})
        quality = str(int(tm.get("quality", 10)))
        rb_tbl = self.game_data.get("treasure_rebirth", {}).get(quality, {})
        dia_cost = int(rb_tbl.get(str(cur_step), {}).get("useDiamond", 0))
        if int(self.state["player"].get("Diamond", 0)) < dia_cost:
            self._last_rpc_context["status"] = -1
            return {}
        if dia_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -dia_cost,
                source=f"treasure_rebirth:{tr['TreasureModelId']}",
            )

        tr_type = int(tm.get("typeID", 1401))
        refund_tuples = self._treasure_exp_refund_tuples(tm, tr) if cur_exp > 0 else []

        used_log = tr.pop("step_materials_used", None)
        if isinstance(used_log, list) and used_log:
            for item in used_log:
                if len(item) >= 3 and int(item[2]) > 0:
                    refund_tuples.append((int(item[0]), int(item[1]), int(item[2])))
        elif cur_step > 0:
            val_lv = int(tm.get("valueLv", 5))
            tr_step_tbl = self.game_data.get("treasure_step", {})
            for s_idx in range(cur_step):
                s_row = tr_step_tbl.get(str(val_lv * 1000 + s_idx))
                if not s_row:
                    continue
                refund_tuples.extend(_parse_resource_str(str(s_row.get("upUseExtraStr", ""))))
                cards_n = int(s_row.get("upUseBaseCardNum", 0))
                if cards_n > 0:
                    refund_tuples.append((tr_type, int(tr["TreasureModelId"]), cards_n))

        tr["Lv"] = 0
        tr["Step"] = 0
        tr["EXP"] = 0
        base_res = (
            self._grant_resources_from_tuples(
                refund_tuples,
                source=f"treasure_rebirth:{tr['TreasureModelId']}",
                tx_prefix=f"treasure_rebirth:{self.profile_name}:{tr_id}:{uuid.uuid4()}",
            )
            if refund_tuples
            else []
        )
        self._inc_stat("rebirth_count", 1)
        self.save()
        return {"TreasureInfo": copy.deepcopy(tr), "BaseGetGameResourceList": base_res}

    def _build_mystery_shop_items(self, shop_type: int) -> list[dict[str, Any]]:
        """Build 8 Mystery Shop entries from MysteryshopFixedRelation + MysteryshopOddsPseudoRelation."""
        lv = int(self.state["player"].get("Lv", 1))
        ms_cfg = self.game_data.get("mystery_shop_config", {})
        target_len = max(1, int(ms_cfg.get("refreshNum", 8)))
        fixed_rows = [
            r
            for r in sorted(self.game_data.get("mystery_shop_fixed", {}).values(), key=lambda x: int(x.get("ID", 0)))
            if int(r.get("shopType", 0)) == shop_type and lv >= int(r.get("needLv", 1))
        ]
        # Prefer the lowest needLv fixed slot first (ID=1: 50x 16050001 for 50 HeroCoin) so Lv24 Guide 7 step 211 succeeds
        odds_rows = list(self.game_data.get("mystery_shop_odds", {}).values())
        chosen_rows: list[dict[str, Any]] = []
        if fixed_rows:
            chosen_rows.append(fixed_rows[0])
        if odds_rows:
            pool = random.sample(odds_rows, min(len(odds_rows), max(0, target_len - len(chosen_rows))))
            chosen_rows.extend(pool)
        out: list[dict[str, Any]] = []
        for row in chosen_rows[:target_len]:
            sell_parts = _parse_resource_str(str(row.get("outResource", "")))
            buy_parts = _parse_resource_str(str(row.get("useResource", "")))
            if not sell_parts or not buy_parts:
                continue
            st, sm, sn = sell_parts[0]
            bt, bm, bn = buy_parts[0]
            if not self._is_valid_resource(st, sm):
                continue
            out.append(
                {
                    "Id": str(uuid.uuid4()),
                    "SellResourceTypeSub": st,
                    "SellGoodsModelId": sm,
                    "SellNum": sn,
                    "BuyResourceTypeSub": bt,
                    "BuyGoodsModelId": bm if bm > 0 and bt >= 1500 else 0,
                    "BuyNum": bn,
                    "IsSell": 0,  # Exchange.Enabled = 0 per MysticalStoreScene.lua:20
                }
            )
        return out

    def _mystery_shop_state(self, senior: bool = False) -> dict[str, Any]:
        vip_lv = int(self.state["player"].get("VIPLv", self.state["player"].get("Vip", 0)))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        free_max = max(1, int(vip_cfg.get("freeRefreshMysteryShopMaxNum", 2)))
        max_refresh = int(vip_cfg.get("refreshMysteryShopMaxNum", 10 + vip_lv * 5))
        ms = self.state.setdefault(
            "mystery_shop",
            {"normal": None, "senior": None, "free_date": "", "free_count": free_max, "gold_count": 0},
        )
        now = self.now_ts()
        today = self.clock.today_str(now)
        config = self.game_data["mystery_shop_config"]
        interval = int(config["freeRefreshCD"])
        # Use VN server-day boundaries. Store the most recent credited period so polling
        # and reopening the shop cannot award the same free refresh twice.
        midnight = self.clock.midnight_ts(now)
        normal_period = midnight + (now - midnight) // interval * interval
        changed = False
        if "free_period" not in ms:
            if not ms.get("free_date"):
                ms["free_count"] = free_max
            ms["free_date"] = today
            ms["free_period"] = normal_period
            changed = True
        elif normal_period > ms["free_period"]:
            elapsed = (normal_period - ms["free_period"]) // interval
            ms["free_count"] = min(free_max, ms["free_count"] + elapsed)
            ms["free_period"] = normal_period
            changed = True
        if today > ms.get("free_date", ""):
            ms["free_date"] = today
            ms["gold_count"] = 0
            changed = True

        normal_deadline = ms["free_period"] + interval
        senior_hours = [int(config[field] * 86400) for field in ("seniorRefreshTimeFirst", "seniorRefreshTimeSecond")]
        senior_deadline = next(
            (midnight + seconds for seconds in sorted(senior_hours) if midnight + seconds > now),
            midnight + 86400 + min(senior_hours),
        )
        deadlines = ms.setdefault("deadlines", {})
        # Attach deadlines to legacy stock before it can be rerolled, preserving sold entries.
        for shop, deadline in (("normal", normal_deadline), ("senior", senior_deadline)):
            if shop not in deadlines:
                deadlines[shop] = deadline
                changed = True
        key = "senior" if senior else "normal"
        if ms.get(key) is None or now >= deadlines[key]:
            ms[key] = self._build_mystery_shop_items(1 if senior else 0)
            deadlines[key] = senior_deadline if senior else normal_deadline
            changed = True
        if changed:
            self.save()
        return {
            "FreeCount": int(ms.get("free_count", free_max)),
            "GoldCount": int(ms.get("gold_count", 0)),
            "RefreshMysteryShopMaxNum": max_refresh,
            "MysteryShopGoodsList": ms[key],
            "LastFreshDate": deadlines[key],
        }

    def _rpc_mystery_shop_get_info(self, _data: Any) -> dict[str, Any]:
        return self._mystery_shop_state(senior=False)

    def _rpc_mystery_shop_senior_get_info(self, _data: Any) -> dict[str, Any]:
        return self._mystery_shop_state(senior=True)

    def _do_mystery_shop_refresh(self, refresh_type: int, senior: bool) -> dict[str, Any]:
        ms_state = self._mystery_shop_state(senior=senior)
        ms = self.state["mystery_shop"]
        ms_cfg = self.game_data.get("mystery_shop_config", {})
        if refresh_type not in (1, 2, 3):
            self._last_rpc_context["status"] = -48
            return {}
        if refresh_type == 1:
            if int(ms.get("free_count", 0)) <= 0:
                self._last_rpc_context["status"] = -2105
                return {}
            ms["free_count"] = int(ms["free_count"]) - 1
        elif refresh_type == 2:
            res_str = str(ms_cfg.get("seniorRefreshUseResource" if senior else "refreshUseResource", "1605,16050010,1"))
            _, model, count = _parse_resource_str(res_str)[0]
            if not self._consume_goods_qty(model, count):
                self._last_rpc_context["status"] = -1802
                return {}
            self._mark_goods_changed(model)
            ms["gold_count"] = int(ms.get("gold_count", 0)) + 1
        else:
            if int(ms.get("gold_count", 0)) >= int(ms_state["RefreshMysteryShopMaxNum"]):
                self._last_rpc_context["status"] = -2107
                return {}
            cost = int(ms_cfg.get("seniorRefreshUseDiamond" if senior else "refreshUseDiamond", 20))
            if int(self.state["player"].get("Diamond", 0)) < cost:
                self._last_rpc_context["status"] = -1105
                return {}
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -cost,
                source=f"mystery_refresh:{'senior' if senior else 'normal'}",
            )
            ms["gold_count"] = int(ms.get("gold_count", 0)) + 1

        ms["senior" if senior else "normal"] = self._build_mystery_shop_items(1 if senior else 0)
        self._inc_stat("mystery_refresh", 1)
        self.save()
        return dict(ms_state, FreeCount=ms["free_count"], GoldCount=ms["gold_count"],
                    MysteryShopGoodsList=ms["senior" if senior else "normal"])

    def _rpc_mystery_shop_refresh(self, data: Any) -> dict[str, Any]:
        rtype = data[0] if isinstance(data, list) and len(data) == 1 and type(data[0]) is int else 0
        return self._do_mystery_shop_refresh(rtype, senior=False)

    def _rpc_mystery_shop_senior_refresh(self, data: Any) -> dict[str, Any]:
        rtype = data[0] if isinstance(data, list) and len(data) == 1 and type(data[0]) is int else 0
        return self._do_mystery_shop_refresh(rtype, senior=True)

    def _do_mystery_shop_buy(self, goods_id: str, senior: bool) -> dict[str, Any]:
        ms_state = self._mystery_shop_state(senior=senior)
        item = next((x for x in ms_state["MysteryShopGoodsList"] if str(x.get("Id")) == goods_id), None)
        if not item or int(item.get("IsSell", 0)) == 1:
            self._last_rpc_context["status"] = -1
            return {}
        bt = int(item["BuyResourceTypeSub"])
        bn = int(item["BuyNum"])
        attr_map = {1111: "Diamond", 1112: "Gold", 1116: "HeroCoin"}
        field = attr_map.get(bt, "HeroCoin")
        if int(self.state["player"].get(field, 0)) < bn:
            self._last_rpc_context["status"] = -1
            return {}
        if bn > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                field,
                -bn,
                source=f"mystery_buy:{item['SellGoodsModelId']}",
                idempotency_key=f"mystery_cost:{self.profile_name}:{goods_id}",
            )
        item["IsSell"] = 1
        base_res = self._grant_resources_from_tuples(
            [(int(item["SellResourceTypeSub"]), int(item["SellGoodsModelId"]), int(item["SellNum"]))],
            source=f"mystery_buy:{item['SellGoodsModelId']}",
            tx_prefix=f"mystery_buy:{self.profile_name}:{goods_id}",
        )
        self._record_daily_task_progress(24, 1)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_mystery_shop_buy(self, data: Any) -> dict[str, Any]:
        gid = str(data[0]) if isinstance(data, list) and data else ""
        return self._do_mystery_shop_buy(gid, senior=False)

    def _rpc_mystery_shop_senior_buy(self, data: Any) -> dict[str, Any]:
        gid = str(data[0]) if isinstance(data, list) and data else ""
        return self._do_mystery_shop_buy(gid, senior=True)

    def _rpc_mystery_shop_reset_daily(self, data: Any = None) -> dict[str, Any]:
        """Reset daily Mystery Shop counters/free refreshes and reroll both normal and senior stock."""
        senior = bool(isinstance(data, list) and data and int(data[0]) == 1)
        vip_lv = int(self.state["player"].get("VIPLv", self.state["player"].get("Vip", 0)))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        free_max = max(1, int(vip_cfg.get("freeRefreshMysteryShopMaxNum", 2)))
        now = self.now_ts()
        today = self.clock.today_str(now)
        config = self.game_data["mystery_shop_config"]
        interval = int(config["freeRefreshCD"])
        midnight = self.clock.midnight_ts(now)
        normal_period = midnight + (now - midnight) // interval * interval
        normal_deadline = normal_period + interval
        senior_hours = [int(config[field] * 86400) for field in ("seniorRefreshTimeFirst", "seniorRefreshTimeSecond")]
        senior_deadline = next(
            (midnight + seconds for seconds in sorted(senior_hours) if midnight + seconds > now),
            midnight + 86400 + min(senior_hours),
        )
        ms = self.state.setdefault("mystery_shop", {})
        ms["free_count"] = free_max
        ms["gold_count"] = 0
        ms["free_date"] = today
        ms["free_period"] = normal_period
        ms["normal"] = self._build_mystery_shop_items(0)
        ms["senior"] = self._build_mystery_shop_items(1)
        ms["deadlines"] = {"normal": normal_deadline, "senior": senior_deadline}
        self.save()
        return self._mystery_shop_state(senior=senior)

    def _glory_payload(self, active_type_id: int | None = None) -> dict[str, Any]:
        glory = self.state.setdefault(
            "glory",
            {
                "1": {"TypeId": 1, "Lv": 0, "EXP": 0},
                "2": {"TypeId": 2, "Lv": 0, "EXP": 0},
                "3": {"TypeId": 3, "Lv": 0, "EXP": 0},
            },
        )
        glory_lv_tbl = self.game_data.get("glory_lv", {})
        glory_list: list[dict[str, Any]] = []
        for tid in (1, 2, 3):
            entry = glory.setdefault(str(tid), {"TypeId": tid, "Lv": 0, "EXP": 0})
            lv = int(entry.get("Lv", 0))
            crit = int(glory_lv_tbl.get(str(lv), {}).get("upOddsMin", 3200))
            glory_list.append({"TypeId": tid, "Lv": lv, "EXP": int(entry.get("EXP", 0)), "CritOdds": crit})
        bonuses = self._glory_attr_bonuses()
        add_attr = [
            {"AddAttrEnumId": 432, "AddAttrNum": bonuses["HP"]},
            {"AddAttrEnumId": 431, "AddAttrNum": bonuses["AP"]},
            {"AddAttrEnumId": 433, "AddAttrNum": bonuses["DEF"]},
        ]
        extra_sta = self._glory_extra_sta()
        if active_type_id is not None:
            active_item = next(g for g in glory_list if g["TypeId"] == active_type_id)
            return {
                **active_item,
                "AddAttrInfo": add_attr,
                "ExtraSTA": extra_sta,
            }
        return {
            "GloryInfo": glory_list,
            "AddAttrInfo": add_attr,
            "ExtraSTA": extra_sta,
        }

    def _apply_glory_diploma(self, type_id: int, goods_item: dict[str, Any]) -> None:
        glory = self.state.setdefault("glory", {})
        entry = glory.setdefault(str(type_id), {"TypeId": type_id, "Lv": 0, "EXP": 0})
        g_cfg = self.game_data.get("goods_model", {}).get(str(goods_item["GoodsModelId"]), {})
        exp_gain = max(1, int(g_cfg.get("outputNum", 10)))
        entry["EXP"] = int(entry.get("EXP", 0)) + exp_gain
        glory_lv_tbl = self.game_data.get("glory_lv", {})
        cur_lv = int(entry.get("Lv", 0))
        while str(cur_lv + 1) in glory_lv_tbl and entry["EXP"] >= int(glory_lv_tbl[str(cur_lv + 1)].get("EXPTotal", 0)):
            cur_lv += 1
        entry["Lv"] = cur_lv
        goods_item["Num"] = int(goods_item["Num"]) - 1
        gid = int(goods_item["GoodsModelId"])
        if goods_item["Num"] <= 0:
            self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != goods_item["Id"]]
        self._mark_goods_changed(gid)

    def _rpc_glory_get_data(self, _data: Any) -> dict[str, Any]:
        return self._glory_payload()

    def _rpc_glory_lv_up(self, data: Any) -> dict[str, Any]:
        type_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 2
        gid = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 0
        entity_id = str(data[2]) if isinstance(data, list) and len(data) >= 3 else ""
        if type_id not in (1, 2, 3):
            self._last_rpc_context["status"] = -1
            return {}
        item = next(
            (
                g
                for g in self.state.get("goods", [])
                if (entity_id and g["Id"] == entity_id or int(g.get("GoodsModelId", 0)) == gid)
                and int(g.get("GoodsModelId", 0)) // 10000 == 1604
                and int(g.get("Num", 0)) >= 1
            ),
            None,
        )
        if not item:
            self._last_rpc_context["status"] = -1
            return {}
        self._apply_glory_diploma(type_id, item)
        self._record_daily_task_progress(12, 1)
        self._sync_player_recover_times()
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return self._glory_payload(active_type_id=type_id)

    def _rpc_glory_lv_up_one_key(self, data: Any) -> dict[str, Any]:
        type_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 2
        if type_id not in (1, 2, 3):
            self._last_rpc_context["status"] = -1
            return {}
        diplomas = [
            g
            for g in list(self.state.get("goods", []))
            if int(g.get("GoodsModelId", 0)) // 10000 == 1604 and int(g.get("Num", 0)) > 0
        ]
        if not diplomas:
            self._last_rpc_context["status"] = -1
            return {}
        used_count = 0
        for item in diplomas:
            while int(item.get("Num", 0)) > 0:
                self._apply_glory_diploma(type_id, item)
                used_count += 1
        if used_count > 0:
            self._record_daily_task_progress(12, used_count)
        self._sync_player_recover_times()
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return self._glory_payload(active_type_id=type_id)

    def _rpc_gift_lv_bags(self, _data: Any) -> dict[str, Any]:
        """Return claimable level gift IDs per LevelGiftLayer.lua:112-119."""
        lv = int(self.state["player"].get("Lv", 1))
        claimed = set(int(x) for x in self.state.setdefault("gift_lv", {"claimed": []}).get("claimed", []))
        gift_tbl = self.game_data.get("gift_lv", {})
        claimable = sorted(int(k) for k in gift_tbl if lv >= int(k) and int(k) not in claimed)
        return {"Bags": claimable}

    def _rpc_gift_lv_draw(self, data: Any) -> dict[str, Any]:
        target_lv = int(data[0]) if isinstance(data, list) and data else 0
        player_lv = int(self.state["player"].get("Lv", 1))
        row = self.game_data.get("gift_lv", {}).get(str(target_lv))
        gl_state = self.state.setdefault("gift_lv", {"claimed": []})
        claimed = gl_state.setdefault("claimed", [])
        if not row or player_lv < target_lv or target_lv in claimed:
            self._last_rpc_context["status"] = -1
            return {}
        claimed.append(target_lv)
        base_res = self._grant_resources_from_tuples(
            _parse_resource_str(str(row.get("resourceList", ""))),
            source=f"gift_lv:{target_lv}",
            tx_prefix=f"gift_lv:{self.profile_name}:{self.state['player']['PlayerId']}:{target_lv}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_gift_login_info(self, _data: Any) -> dict[str, Any]:
        """Return 7-day consecutive login gift state per ContinuousSignLayer.lua:264."""
        today = time.strftime("%Y-%m-%d")
        gl = self.state.setdefault("gift_login", {"login_days": 1, "last_login_date": today, "claimed": []})
        login_days = max(1, min(7, int(gl.get("login_days", 1))))
        claimed = set(int(x) for x in gl.get("claimed", []))
        gift_list = []
        for day_idx in sorted(int(k) for k in self.game_data.get("gift_login", {})):
            status = 2 if day_idx in claimed else (1 if day_idx <= login_days else 0)
            gift_list.append({"Id": day_idx, "Status": status})
        return {"GiftList": gift_list}

    def _rpc_gift_login_draw(self, data: Any) -> dict[str, Any]:
        day_id = int(data[0]) if isinstance(data, list) and data else 0
        today = time.strftime("%Y-%m-%d")
        gl = self.state.setdefault("gift_login", {"login_days": 1, "last_login_date": today, "claimed": []})
        login_days = max(1, min(7, int(gl.get("login_days", 1))))
        claimed = gl.setdefault("claimed", [])
        row = self.game_data.get("gift_login", {}).get(str(day_id))
        if not row or day_id < 1 or day_id > login_days or day_id in claimed:
            self._last_rpc_context["status"] = -1
            return {}
        claimed.append(day_id)
        base_res = self._grant_resources_from_tuples(
            _parse_resource_str(str(row.get("resourceList", ""))),
            source=f"gift_login:{day_id}",
            tx_prefix=f"gift_login:{self.profile_name}:{self.state['player']['PlayerId']}:{day_id}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def admin_state_summary(self) -> dict[str, Any]:
        """Return structured profile summary for admin/QA inspection."""
        with self._lock:
            return self._admin_state_summary_locked()

    def _admin_state_summary_locked(self) -> dict[str, Any]:
        p = self.state["player"]
        b = self.state["battle"]
        deployed = [
            {
                "SlotId": s["SlotId"],
                "HeroId": s["HeroId"],
                "HeroModelId": s["HeroModelId"],
                "FAP": int(s.get("Property", {}).get("FAP", 0)),
            }
            for s in self.state["slots"]
            if int(s.get("HeroModelId", 0)) > 0
        ]
        return {
            "profile": self.profile_name,
            "player": {
                "PlayerId": p["PlayerId"],
                "PlayerName": p.get("PlayerName"),
                "Lv": int(p["Lv"]),
                "EXP": int(p["EXP"]),
                "Vip": int(p.get("Vip", 0)),
                "VipEXP": int(p.get("VipEXP", 0)),
                "Gold": int(p["Gold"]),
                "Diamond": int(p["Diamond"]),
                "VIT": int(p["VIT"]),
                "STA": int(p["STA"]),
                "HeroCoin": int(p["HeroCoin"]),
                "HeroEXP": int(p["HeroEXP"]),
                "FAP": int(p["FAP"]),
                "StarId": int(p.get("StarId", 0)),
                "ChargeNum": int(p.get("ChargeNum", 0)),
                "IsNewPlayer": int(p.get("IsNewPlayer", 0)),
            },
            "battle": {
                "MaxChapterId": int(b.get("MaxChapterId", 11)),
                "MaxNodeId": int(b.get("MaxNodeId", 1111)),
                "StarCount": int(b.get("StarCount", 0)),
            },
            "counts": {
                "heroes": len(self.state.get("heroes", [])),
                "deployed_slots": len(deployed),
                "equips": len(self.state.get("equips", [])),
                "treasures": len(self.state.get("treasures", [])),
                "goods": len(self.state.get("goods", [])),
            },
            "deployed": deployed,
        }

    def admin_set_vip(
        self,
        vip_lv: int | None = None,
        vip_exp: int | None = None,
        actor: str = "admin",
        source: str = "admin_vip",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Set VIP level or VipEXP via ResourceLedger, deriving Vip from game_data['vip_model']."""
        with self._lock:
            return self._admin_set_vip_locked(
                vip_lv=vip_lv,
                vip_exp=vip_exp,
                actor=actor,
                source=source,
                idempotency_key=idempotency_key,
            )

    def _admin_set_vip_locked(
        self,
        vip_lv: int | None = None,
        vip_exp: int | None = None,
        actor: str = "admin",
        source: str = "admin_vip",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        vip_model = self.game_data.get("vip_model", {})
        max_vip = max((int(k) for k in vip_model.keys()), default=20)
        cur_exp = int(self.state["player"].get("VipEXP", 0))
        if vip_lv is not None:
            lv = int(vip_lv)
            if lv < 0 or lv > max_vip or str(lv) not in vip_model:
                raise ValueError(f"Invalid vip_lv={vip_lv}; valid range 0..{max_vip}")
            target_exp = int(vip_model[str(lv)]["expTotal"])
        elif vip_exp is not None:
            target_exp = int(vip_exp)
            if target_exp < 0:
                raise ValueError("vip_exp must be >= 0")
        else:
            raise ValueError("Provide vip_lv or vip_exp")
        delta = target_exp - cur_exp
        if delta != 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "VipEXP",
                delta,
                source=source,
                idempotency_key=idempotency_key,
                actor=actor,
            )
        else:
            derived = int(self.ledger.derive_vip_level(target_exp))
            self.state["player"]["Vip"] = derived
            self.state["player"]["VIPLv"] = derived
        self.save()
        return {
            "Vip": int(self.state["player"]["Vip"]),
            "VipEXP": int(self.state["player"]["VipEXP"]),
        }

    def admin_grant(
        self,
        resources: list[dict[str, Any]] | None = None,
        items: list[dict[str, Any]] | None = None,
        heroes: list[dict[str, Any]] | None = None,
        equips: list[dict[str, Any]] | None = None,
        actor: str = "admin",
        source: str = "admin_grant",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Grant validated resources, items, heroes, or equips with ledger audit trail."""
        with self._lock:
            return self._admin_grant_locked(
                resources=resources,
                items=items,
                heroes=heroes,
                equips=equips,
                actor=actor,
                source=source,
                idempotency_key=idempotency_key,
            )

    def _admin_grant_locked(
        self,
        resources: list[dict[str, Any]] | None = None,
        items: list[dict[str, Any]] | None = None,
        heroes: list[dict[str, Any]] | None = None,
        equips: list[dict[str, Any]] | None = None,
        actor: str = "admin",
        source: str = "admin_grant",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        p = self.state["player"]
        pid = str(p["PlayerId"])
        max_lv = int(self.game_data.get("player_config", {}).get("maxPlayerLV", 80))
        player_lv = int(p.get("Lv", 1))
        granted_resources: list[dict[str, Any]] = []
        item_tuples: list[tuple[int, int, int]] = []
        granted_heroes: list[dict[str, Any]] = []
        granted_equips: list[dict[str, Any]] = []

        for idx, res in enumerate(resources or []):
            rtype = str(res.get("type", ""))
            amount = int(res.get("amount", 0))
            if amount <= 0:
                raise ValueError(f"Resource amount must be > 0 for {rtype}")
            tx_key = f"{idempotency_key}:res:{idx}:{rtype}" if idempotency_key else None
            tx = self.ledger.apply_player_delta(
                p,
                self.profile_name,
                rtype,
                amount,
                source=source,
                idempotency_key=tx_key,
                actor=actor,
            )
            if rtype == "EXP":
                self._sync_level_from_exp()
                player_lv = int(p.get("Lv", 1))
            granted_resources.append({"type": rtype, "amount": amount, "balance": tx.balance_after})

        for entry in items or []:
            mid = int(entry.get("id", 0))
            num = int(entry.get("num", 1))
            if num <= 0:
                raise ValueError(f"Item num must be > 0 for {mid}")
            mid_str = str(mid)
            if mid_str in self.game_data.get("goods_model", {}):
                rtype = int(entry.get("type") or (mid // 10000))
            elif mid_str in self.game_data.get("treasure_debris", {}):
                rtype = int(entry.get("type") or 1504)
            elif mid_str in self.game_data.get("treasures", {}):
                rtype = int(entry.get("type") or (mid // 10000))
            elif mid_str in self.game_data.get("equips", {}):
                rtype = int(entry.get("type") or (mid // 10000))
            else:
                raise ValueError(f"Unknown game item model_id={mid}")
            item_tuples.append((rtype, mid, num))

        if item_tuples:
            self._grant_resources_from_tuples(
                item_tuples,
                source=source,
                tx_prefix=idempotency_key or f"{source}:{self.profile_name}:{pid}:{uuid.uuid4()}",
            )

        for idx, hspec in enumerate(heroes or []):
            hid = int(hspec.get("model_id", 0))
            if str(hid) not in self.game_data.get("heroes", {}):
                raise ValueError(f"Unknown hero model_id={hid}")
            lv = max(1, min(int(hspec.get("lv", 1)), max_lv, player_lv))
            step = max(0, min(int(hspec.get("step", 0)), 15))
            inst = self._build_hero_instance(hid, lv=lv, step=step)
            self.state["heroes"].append(inst)
            self.ledger.record_grant_event(
                account_id=pid,
                profile=self.profile_name,
                resource_type=f"Hero:{hid}",
                amount=1,
                balance_after=len(self.state["heroes"]),
                source=source,
                idempotency_key=f"{idempotency_key}:hero:{idx}:{hid}" if idempotency_key else None,
                actor=actor,
                metadata={"lv": lv, "step": step, "inst_id": inst["Id"]},
            )
            if hspec.get("deploy"):
                slot_idx = hspec.get("slot_id")
                target_slot = None
                if slot_idx is not None:
                    sid = int(slot_idx)
                    if 1 <= sid <= len(self.state["slots"]):
                        target_slot = self.state["slots"][sid - 1]
                else:
                    target_slot = next((s for s in self.state["slots"] if int(s.get("HeroModelId", 0)) == 0), None)
                if target_slot is not None:
                    target_slot["HeroId"] = inst["Id"]
                    target_slot["HeroModelId"] = hid
                    self.state["embattle"][f"Formation{target_slot['SlotId']}"] = target_slot["SlotId"]
            granted_heroes.append({"Id": inst["Id"], "HeroModelId": hid, "Lv": lv, "Step": step})

        for idx, espec in enumerate(equips or []):
            eid = int(espec.get("model_id", 0))
            if str(eid) not in self.game_data.get("equips", {}):
                raise ValueError(f"Unknown equip model_id={eid}")
            lv = max(1, min(int(espec.get("lv", 1)), player_lv * 2, max_lv * 2))
            step = max(0, min(int(espec.get("step", 0)), 10))
            rtype = eid // 10000
            eq_id = str(uuid.uuid4())
            eq_obj = {
                "Id": eq_id,
                "EquipModelId": eid,
                "Lv": lv,
                "Step": step,
                "Gold": 0,
                "Star": 0,
                "Crdate": int(time.time()),
            }
            self.state.setdefault("equips", []).append(eq_obj)
            self.ledger.record_grant_event(
                account_id=pid,
                profile=self.profile_name,
                resource_type=f"Equip:{eid}",
                amount=1,
                balance_after=len(self.state["equips"]),
                source=source,
                idempotency_key=f"{idempotency_key}:equip:{idx}:{eid}" if idempotency_key else None,
                actor=actor,
                metadata={"lv": lv, "step": step, "inst_id": eq_id},
            )
            slot_id = espec.get("slot_id")
            if slot_id is not None:
                sid = int(slot_id)
                slot_key = self.EQUIP_TYPE_TO_SLOT_KEY.get(rtype)
                if 1 <= sid <= len(self.state["slots"]) and slot_key:
                    self.state["slots"][sid - 1][slot_key] = eq_obj
            granted_equips.append({"Id": eq_id, "EquipModelId": eid, "Lv": lv})

        self._recalc_all_slots_and_fap()
        self._sync_player_recover_times()
        self.save()
        return {
            "resources": granted_resources,
            "items_count": len(item_tuples),
            "heroes": granted_heroes,
            "equips": granted_equips,
            "summary": self.admin_state_summary(),
        }

    def admin_prepare_account(
        self,
        target_lv: int = 1,
        vip_lv: int | None = None,
        actor: str = "admin",
        source: str = "admin_prepare",
    ) -> dict[str, Any]:
        """Prepare account at an authentic target player Lv (and optional VIP tier)."""
        with self._lock:
            return self._admin_prepare_account_locked(
                target_lv=target_lv,
                vip_lv=vip_lv,
                actor=actor,
                source=source,
            )

    def _admin_prepare_account_locked(
        self,
        target_lv: int = 1,
        vip_lv: int | None = None,
        actor: str = "admin",
        source: str = "admin_prepare",
    ) -> dict[str, Any]:
        p = self.state["player"]
        max_lv = int(self.game_data.get("player_config", {}).get("maxPlayerLV", 80))
        lv = int(target_lv)
        if lv < 1 or lv > max_lv or str(lv) not in self.game_data.get("player_lv", {}):
            raise ValueError(f"Invalid target_lv={target_lv}; valid 1..{max_lv}")
        target_exp = int(self.game_data["player_lv"][str(lv)]["EXPTotal"])
        cur_exp = int(p.get("EXP", 0))
        if target_exp != cur_exp:
            self.ledger.apply_player_delta(
                p,
                self.profile_name,
                "EXP",
                target_exp - cur_exp,
                source=source,
                actor=actor,
            )
        if lv < int(p.get("Lv", 1)):
            p["Lv"] = lv
            if self.state.get("slots"):
                main_hid = self.state["slots"][0].get("HeroId")
                for h in self.state.get("heroes", []):
                    if h["Id"] == main_hid:
                        h["Lv"] = lv
        else:
            self._sync_level_from_exp()
        p["IsNewPlayer"] = 0
        if vip_lv is not None:
            self.admin_set_vip(vip_lv=vip_lv, actor=actor, source=source)
        self._recalc_all_slots_and_fap()
        self._sync_player_recover_times()
        self.save()
        return self.admin_state_summary()

    # ------------------------- R7.25: LeaderBoard (ModuleSub 6701..6704) -------------------------

    _LEADERBOARD_VALID_TYPES = frozenset({1, 2, 4})

    def _leaderboard_state(self) -> dict[str, Any]:
        lb = self.state.setdefault(
            "leaderboard",
            {"praised_date": "", "praised_types": [], "praise_counts": {}, "received_praises": {}},
        )
        lb.setdefault("praise_counts", {})
        lb.setdefault("received_praises", {})
        today = self.clock.today_str()
        if lb.get("praised_date") != today:
            lb["praised_date"] = today
            lb["praised_types"] = []
        return lb

    def _valid_hero_head_id(self, candidate: int, slots: list[dict[str, Any]]) -> int:
        heroes_cfg = self.game_data.get("heroes", {})
        if candidate > 0 and str(candidate) in heroes_cfg:
            return candidate
        for slot in slots:
            hm = int(slot.get("HeroModelId", 0))
            if hm > 0 and str(hm) in heroes_cfg:
                return hm
        return 12010004

    def _strongest_slot_hero(self, slots: list[dict[str, Any]]) -> tuple[int, int]:
        heroes_cfg = self.game_data.get("heroes", {})
        best_fap = -1
        best_mid = 0
        for slot in slots:
            hm = int(slot.get("HeroModelId", 0))
            if hm <= 0 or str(hm) not in heroes_cfg:
                continue
            slot_fap = int(slot.get("Property", {}).get("FAP", 0))
            if slot_fap > best_fap:
                best_fap = slot_fap
                best_mid = hm
        return best_mid, max(0, best_fap)

    def _build_leaderboard_entries(self, rank_type: int) -> list[dict[str, Any]]:
        lb = self._leaderboard_state()
        lb_cfg = self.game_data.get("leaderboard_config", {})
        rank_num = max(1, int(lb_cfg.get("rankNum", 50)))
        candidates: list[dict[str, Any]] = []

        # 1. Real S1 profiles (self + active peers)
        profiles: list[tuple[bool, ProfileStore]] = [(True, self)] + [
            (False, peer) for peer in self._get_peer_s1_profiles()
        ]
        seen_pids: set[str] = set()
        for is_self, prof in profiles:
            p = prof.state.get("player", {})
            pid = str(p.get("PlayerId", ""))
            if not pid or pid in seen_pids:
                continue
            if not is_self and int(p.get("IsNewPlayer", 0)) != 0:
                continue
            seen_pids.add(pid)
            slots = prof.state.get("slots", [])
            head_id = self._valid_hero_head_id(int(p.get("HeadImageId", 0)), slots)
            lv = int(p.get("Lv", 1))
            fap = int(p.get("FAP", 0))
            if rank_type == 4:
                best_hm, best_fap = self._strongest_slot_hero(slots)
                if best_hm:
                    head_id = best_hm
                    fap = best_fap
            prof_lb = prof.state.setdefault(
                "leaderboard",
                {"praised_date": "", "praised_types": [], "praise_counts": {}, "received_praises": {}},
            )
            praise_num = int(prof_lb.get("received_praises", {}).get(str(rank_type), 0))
            candidates.append(
                {
                    "Id": pid,
                    "Name": str(p.get("PlayerName", "Adventurer") or "Adventurer"),
                    "Lv": lv,
                    "FAP": fap,
                    "HeadImageId": head_id,
                    "FashionModelId": int(p.get("FashionModelId", 0)),
                    "GuildName": str(p.get("GuildName", "") or ""),
                    "ServerName": "S1 - Chiến Quốc",
                    "PraiseNum": praise_num,
                    "_source": ("self",) if is_self else ("peer", pid),
                }
            )

        # 2. Deterministic NPC leaderboard population up to rankNum (50)
        bot_pairs = [(st, r) for st in (5, 4, 3, 2, 1) for r in (1, 3, 5, 8, 12, 16, 20, 25, 30, 50)]
        for st, r in bot_pairs:
            bot = self._arena_bot_profile(r, st)
            pid = str(bot["PlayerId"])
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            slots = bot["Slots"]
            head_id = self._valid_hero_head_id(0, slots)
            fap = int(bot["FAP"])
            if rank_type == 4:
                best_hm, best_fap = self._strongest_slot_hero(slots)
                if best_hm:
                    head_id = best_hm
                    fap = best_fap
            praise_num = int(lb["praise_counts"].get(f"{rank_type}:{pid}", 0))
            candidates.append(
                {
                    "Id": pid,
                    "Name": str(bot["Name"]),
                    "Lv": int(bot["Lv"]),
                    "FAP": fap,
                    "HeadImageId": head_id,
                    "FashionModelId": int(bot.get("FashionModelId", 0)),
                    "GuildName": str(bot.get("Guild", "") or ""),
                    "ServerName": "S1 - Chiến Quốc",
                    "PraiseNum": praise_num,
                    "_source": ("bot", st, r),
                }
            )

        if rank_type == 2:
            candidates.sort(key=lambda e: (-int(e["Lv"]), -int(e["FAP"]), e["Id"]))
        else:
            candidates.sort(key=lambda e: (-int(e["FAP"]), -int(e["Lv"]), e["Id"]))

        ranked = candidates[:rank_num]
        for idx, entry in enumerate(ranked, start=1):
            entry["Rank"] = idx
        return ranked

    def _rpc_leaderboard_rank_list(self, data: Any) -> dict[str, Any]:
        """Return Leaderboard top-50 list for RankType 1 (FAP), 2 (Lv), or 4 (Generals)."""
        try:
            rank_type = int(data[0]) if isinstance(data, list) and data else 1
        except (TypeError, ValueError):
            rank_type = 0
        if rank_type not in self._LEADERBOARD_VALID_TYPES:
            self._last_rpc_context["status"] = -1
            return {}
        lb = self._leaderboard_state()
        entries = self._build_leaderboard_entries(rank_type)
        public_entries = [{k: v for k, v in e.items() if k != "_source"} for e in entries]
        return {
            "RankList": public_entries,
            "IsPraise": rank_type in lb.get("praised_types", []),
        }

    def _rpc_leaderboard_praise(self, data: Any) -> dict[str, Any]:
        """Praise a ranked player once per day per RankType and grant LeaderboardConfig.likeReward."""
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            rank_type = int(data[0])
            rank = int(data[1])
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        if rank_type not in self._LEADERBOARD_VALID_TYPES:
            self._last_rpc_context["status"] = -1
            return {}

        lb = self._leaderboard_state()
        if rank_type in lb.get("praised_types", []):
            self._last_rpc_context["status"] = -1
            return {}

        entries = self._build_leaderboard_entries(rank_type)
        if rank < 1 or rank > len(entries):
            self._last_rpc_context["status"] = -1
            return {}

        target = entries[rank - 1]
        src = target["_source"]
        if src[0] == "self":
            rec = lb.setdefault("received_praises", {})
            rec[str(rank_type)] = int(rec.get(str(rank_type), 0)) + 1
        elif src[0] == "peer":
            peer = self._find_peer_by_player_id(src[1])
            if peer is not None:
                peer_lb = peer.state.setdefault(
                    "leaderboard",
                    {"praised_date": "", "praised_types": [], "praise_counts": {}, "received_praises": {}},
                )
                rec = peer_lb.setdefault("received_praises", {})
                rec[str(rank_type)] = int(rec.get(str(rank_type), 0)) + 1
                peer.save()
            else:
                p_key = f"{rank_type}:{target['Id']}"
                lb["praise_counts"][p_key] = int(lb["praise_counts"].get(p_key, 0)) + 1
        else:
            p_key = f"{rank_type}:{target['Id']}"
            lb["praise_counts"][p_key] = int(lb["praise_counts"].get(p_key, 0)) + 1

        lb.setdefault("praised_types", []).append(rank_type)

        like_reward = str(self.game_data.get("leaderboard_config", {}).get("likeReward", "1112,0,10000"))
        reward_tuples = _parse_resource_str(like_reward) or [(1112, 0, 10000)]
        base_res = self._grant_resources_from_tuples(
            reward_tuples,
            source=f"leaderboard_praise:{rank_type}:{rank}",
            tx_prefix=f"lb_praise:{self.profile_name}:{lb['praised_date']}:{rank_type}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_leaderboard_formation(self, data: Any) -> dict[str, Any]:
        """Return full Formation snapshot for a Leaderboard rank entry."""
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            rank_type = int(data[0])
            rank = int(data[1])
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        if rank_type not in self._LEADERBOARD_VALID_TYPES:
            self._last_rpc_context["status"] = -1
            return {}

        entries = self._build_leaderboard_entries(rank_type)
        if rank < 1 or rank > len(entries):
            self._last_rpc_context["status"] = -1
            return {}

        src = entries[rank - 1]["_source"]
        if src[0] == "self":
            formation = self._own_slot_formations_view()
        elif src[0] == "peer":
            peer = self._find_peer_by_player_id(src[1])
            if peer is None:
                self._last_rpc_context["status"] = -1
                return {}
            formation = peer._own_slot_formations_view()
        else:
            formation = self._build_bot_formation_view(self._arena_bot_profile(src[2], src[1]))
        return {"Formation": formation}

    _LEADERBOARD_BOT_STEPS = (5, 4, 3, 2, 1)
    _LEADERBOARD_BOT_RANKS = (1, 3, 5, 8, 12, 16, 20, 25, 30, 50)
    _CROSS_SERVER_NAMES = ("S2 - Tây Quốc", "S3 - Bạch Linh Sơn", "S4 - Minh Đạo", "S5 - Tứ Hồn")

    def _build_cross_server_rank_entries(self) -> list[dict[str, Any]]:
        lb_cfg = self.game_data.get("leaderboard_config", {})
        rank_num = max(1, int(lb_cfg.get("rankNum", 50)))
        candidates: list[dict[str, Any]] = []

        profiles: list[tuple[bool, ProfileStore]] = [(True, self)] + [
            (False, peer) for peer in self._get_peer_s1_profiles()
        ]
        seen_pids: set[str] = set()
        for is_self, prof in profiles:
            p = prof.state.get("player", {})
            pid = str(p.get("PlayerId", ""))
            if not pid or pid in seen_pids:
                continue
            if not is_self and int(p.get("IsNewPlayer", 0)) != 0:
                continue
            seen_pids.add(pid)
            slots = prof.state.get("slots", [])
            candidates.append(
                {
                    "Id": pid,
                    "Name": str(p.get("PlayerName", "Adventurer") or "Adventurer"),
                    "Lv": int(p.get("Lv", 1)),
                    "FAP": int(p.get("FAP", 0)),
                    "HeadImageId": self._valid_hero_head_id(int(p.get("HeadImageId", 0)), slots),
                    "FashionModelId": int(p.get("FashionModelId", 0)),
                    "GuildName": str(p.get("GuildName", "") or ""),
                    "ServerName": "S1 - Chiến Quốc",
                    "Zone": "S1 - Chiến Quốc",
                    "PraiseNum": 0,
                }
            )

        for st in self._LEADERBOARD_BOT_STEPS:
            for r in self._LEADERBOARD_BOT_RANKS:
                bot = self._arena_bot_profile(r, st)
                bot_id = f"cs-bot:{st}:{r}"
                srv_name = self._CROSS_SERVER_NAMES[(st + r) % len(self._CROSS_SERVER_NAMES)]
                candidates.append(
                    {
                        "Id": bot_id,
                        "Name": str(bot["Name"]),
                        "Lv": int(bot["Lv"]),
                        "FAP": int(bot["FAP"]),
                        "HeadImageId": self._valid_hero_head_id(0, bot["Slots"]),
                        "FashionModelId": int(bot.get("FashionModelId", 0)),
                        "GuildName": str(bot.get("Guild", "") or ""),
                        "ServerName": srv_name,
                        "Zone": srv_name,
                        "PraiseNum": 0,
                    }
                )

        candidates.sort(key=lambda e: (-int(e["FAP"]), -int(e["Lv"]), str(e["Id"])))
        ranked = candidates[:rank_num]
        for idx, entry in enumerate(ranked, start=1):
            entry["Rank"] = idx
        return ranked

    def _rpc_pvpinter_top_rank(self, _data: Any) -> dict[str, Any]:
        """Return cross-server Top-50 ranking for RankScene Tab 3 (eCrossServerRank)."""
        return {"PVPinterTopRank": self._build_cross_server_rank_entries()}

    def _rpc_pvpinter_slot_formations(self, data: Any) -> dict[str, Any]:
        """Return full Formation snapshot for RankScene cross-server tab inspection."""
        target_id = str(data[0]) if isinstance(data, list) and data and data[0] is not None else ""
        if not target_id:
            self._last_rpc_context["status"] = -1
            return {}
        if target_id == str(self.state.get("player", {}).get("PlayerId", "")):
            return {"Formation": self._own_slot_formations_view()}
        for peer in self._get_peer_s1_profiles():
            pp = peer.state.get("player", {})
            if str(pp.get("PlayerId", "")) == target_id and int(pp.get("IsNewPlayer", 0)) == 0:
                return {"Formation": peer._own_slot_formations_view()}
        if target_id.startswith("cs-bot:"):
            parts = target_id.split(":")
            if len(parts) == 3:
                try:
                    st, r = int(parts[1]), int(parts[2])
                except ValueError:
                    st, r = 0, 0
                if st in self._LEADERBOARD_BOT_STEPS and r in self._LEADERBOARD_BOT_RANKS:
                    bot = self._arena_bot_profile(r, st)
                    bot["PlayerId"] = target_id
                    return {"Formation": self._build_bot_formation_view(bot)}
        self._last_rpc_context["status"] = -1
        return {}


class GameEmulatorState:
    """Multi-profile coordinator hosting NORMAL_PROFILE (ServerId=1) and DEBUG_PROFILE (ServerId=2)."""

    def __init__(
        self,
        persist: bool = True,
        new_player: bool = False,
        default_profile: str = "normal",
        normal_path: Path | None = None,
        debug_path: Path | None = None,
        audit_path: Path | None = None,
        trace_path: Path | None = None,
        env: str = "stable",
        data_dir: Path | None = None,
    ) -> None:
        self.persist = persist
        self.default_profile = default_profile
        self.env = env if env in ENV_PRESETS else "stable"
        preset = ENV_PRESETS[self.env]
        resolved_dir = Path(data_dir) if data_dir is not None else Path(preset["data_dir"])
        self.data_dir = resolved_dir
        resolved_normal = Path(normal_path) if normal_path is not None else (resolved_dir / "normal_profile.json")
        resolved_debug = Path(debug_path) if debug_path is not None else (resolved_dir / "debug_profile.json")
        resolved_audit = Path(audit_path) if audit_path is not None else (resolved_dir / "audit_ledger.jsonl")
        self.trace_path = Path(trace_path) if trace_path is not None else Path(preset["trace_path"])
        self.game_data = json.loads(GAME_DATA_PATH.read_text(encoding="utf-8"))
        self.game_data["bdd"] = json.loads((SERVER_DIR / "bdd_data.json").read_text(encoding="utf-8"))
        self.clock_path = resolved_dir / "clock_state.json"
        if persist and self.clock_path.exists():
            try:
                self.clock = EventClock.from_dict(json.loads(self.clock_path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                self.clock = EventClock()
        else:
            self.clock = EventClock()
        self.ledger = ResourceLedger(
            audit_log_path=resolved_audit if persist else None,
            vip_model=self.game_data.get("vip_model", {}),
        )
        self._acct_lock = threading.RLock()
        self.accounts_index_path = resolved_dir / "accounts_index.json"
        self.active_account_id = "acct_1"
        self.s1_meta: dict[str, dict[str, Any]] = {
            "acct_1": {
                "account_id": "acct_1",
                "user_id": "100001",
                "slot": 1,
                "file": resolved_normal.name,
                "label": "TK 1",
                "default_player_id": "200001",
                "default_arena_rank": 1500,
            }
        }
        normal_store = ProfileStore(
            "normal",
            self.game_data,
            self.ledger,
            state_path=resolved_normal,
            persist=persist,
            reset=new_player,
            trace_path=self.trace_path if persist else None,
            clock=self.clock,
            default_player_id="200001",
            default_arena_rank=1500,
            peer_profiles_fn=self.get_s1_peer_profiles,
            account_manager=self,
        )
        debug_store = ProfileStore(
            "debug",
            self.game_data,
            self.ledger,
            state_path=resolved_debug,
            persist=persist,
            reset=False,
            legacy_seed_path=LEGACY_SAVE_STATE_PATH if self.env == "stable" else None,
            trace_path=self.trace_path if persist else None,
            clock=self.clock,
            account_manager=self,
        )
        self.profiles: dict[str, ProfileStore] = {
            "normal": normal_store,
            "debug": debug_store,
        }
        self.s1_accounts: dict[str, ProfileStore] = {
            "acct_1": normal_store,
        }
        self._init_s1_accounts()

    def _init_s1_accounts(self) -> None:
        seed_dir_env = os.environ.get("INUYASHA_SEED_DIR", "").strip()
        if self.persist and seed_dir_env and not self.accounts_index_path.exists():
            seed_dir = Path(seed_dir_env)
            olina_seed = seed_dir / "seed_olinahugh.json"
            acct2_file = self.data_dir / "s1_acct_2.json"
            new_sample = not acct2_file.exists()
            if olina_seed.exists() and new_sample:
                try:
                    raw_seed = json.loads(olina_seed.read_text(encoding="utf-8"))
                    pvp_st = raw_seed.setdefault("pvp", {})
                    if int(pvp_st.get("rank", 1500)) == 1500:
                        pvp_st["rank"] = 1488
                    ProfileStore._write_json_atomic(acct2_file, raw_seed)
                except Exception:
                    pass
            self.ensure_s1_account_slots(3)
            if new_sample and not olina_seed.exists():
                sample = self.s1_accounts["acct_2"]
                sample.state["player"].update({"PlayerName": "Mẫu S1", "StepCountList": {"1": 999}})
                sample.admin_prepare_account(target_lv=20, vip_lv=3, source="standalone_sample")
            return

        if self.persist and self.accounts_index_path.exists():
            try:
                idx_data = json.loads(self.accounts_index_path.read_text(encoding="utf-8"))
                for meta in idx_data.get("accounts", []):
                    aid = str(meta.get("account_id", ""))
                    if not aid or aid == "acct_1":
                        if aid == "acct_1" and meta.get("label"):
                            self.s1_meta["acct_1"]["label"] = str(meta["label"])
                        continue
                    self._materialize_s1_account(meta)
                active_id = str(idx_data.get("active_account_id", "acct_1"))
                if active_id in self.s1_accounts:
                    self.active_account_id = active_id
            except Exception:
                pass

    def _materialize_s1_account(self, meta: dict[str, Any], reset: bool = False) -> ProfileStore:
        aid = str(meta["account_id"])
        slot = int(meta.get("slot", len(self.s1_meta) + 1))
        uid = str(meta.get("user_id", str(100000 + slot)))
        fname = str(meta.get("file", f"s1_{aid}.json"))
        def_pid = str(meta.get("default_player_id", str(200010 + slot)))
        def_rank = int(meta.get("default_arena_rank", max(100, 1500 - (slot - 1) * 12)))
        norm_meta = {
            "account_id": aid,
            "user_id": uid,
            "slot": slot,
            "file": fname,
            "label": str(meta.get("label") or f"TK {slot}"),
            "default_player_id": def_pid,
            "default_arena_rank": def_rank,
        }
        self.s1_meta[aid] = norm_meta
        if aid in self.s1_accounts and not reset:
            return self.s1_accounts[aid]
        store = ProfileStore(
            aid,
            self.game_data,
            self.ledger,
            state_path=self.data_dir / fname,
            persist=self.persist,
            reset=reset,
            trace_path=self.trace_path if self.persist else None,
            clock=self.clock,
            default_player_id=def_pid,
            default_arena_rank=def_rank,
            peer_profiles_fn=self.get_s1_peer_profiles,
            account_manager=self,
        )
        # Ensure distinct player_id & initial arena rank across S1 accounts
        used_pids = {
            str(p.state["player"]["PlayerId"])
            for k, p in self.s1_accounts.items()
            if k != aid
        }
        if str(store.state["player"]["PlayerId"]) in used_pids:
            store.state["player"]["PlayerId"] = def_pid
            store.save()
        used_ranks = {
            int(p.state.get("pvp", {}).get("rank", 1500))
            for k, p in self.s1_accounts.items()
            if k != aid
        }
        cur_rank = int(store.state.get("pvp", {}).get("rank", 1500))
        if cur_rank in used_ranks:
            cand_r = def_rank
            while cand_r in used_ranks and cand_r > 50:
                cand_r -= 7
            store.state.setdefault("pvp", {})["rank"] = cand_r
            store.save()
        self.s1_accounts[aid] = store
        self.profiles[aid] = store
        return store

    def _save_accounts_index(self) -> None:
        if not self.persist:
            return
        ordered = sorted(self.s1_meta.values(), key=lambda m: int(m.get("slot", 1)))
        payload = {
            "schema_version": 1,
            "active_account_id": self.active_account_id,
            "accounts": ordered,
            "updated_at": int(time.time()),
        }
        ProfileStore._write_json_atomic(self.accounts_index_path, payload)

    def ensure_s1_account_slots(self, min_slots: int = 3) -> None:
        with self._acct_lock:
            changed = False
            for slot in range(2, min_slots + 1):
                aid = f"acct_{slot}"
                if aid not in self.s1_accounts:
                    self._materialize_s1_account(
                        {
                            "account_id": aid,
                            "user_id": str(100000 + slot),
                            "slot": slot,
                            "file": f"s1_acct_{slot}.json",
                            "label": f"TK {slot}",
                            "default_player_id": str(200010 + slot),
                            "default_arena_rank": max(100, 1500 - (slot - 1) * 12),
                        }
                    )
                    changed = True
            if changed or (self.persist and not self.accounts_index_path.exists()):
                self._save_accounts_index()

    def get_s1_peer_profiles(self, caller: ProfileStore | None = None) -> list[ProfileStore]:
        with self._acct_lock:
            return [p for p in self.s1_accounts.values() if p is not caller]

    def _summarize_s1_account(self, aid: str) -> dict[str, Any]:
        meta = self.s1_meta[aid]
        store = self.s1_accounts[aid]
        p = store.state.get("player", {})
        is_new = int(p.get("IsNewPlayer", 1))
        pname = str(p.get("PlayerName", "")) if is_new == 0 else ""
        lv = int(p.get("Lv", 1))
        vip = int(p.get("Vip", 0))
        fap = int(p.get("FAP", 0))
        rank = int(store.state.get("pvp", {}).get("rank", 1500))
        slot = int(meta.get("slot", 1))
        if is_new == 0 and pname:
            display = f"TK{slot}: {pname} (Lv.{lv})"
        else:
            display = f"TK{slot}: (Tạo nhân vật mới)"
        return {
            "account_id": aid,
            "user_id": str(meta["user_id"]),
            "slot": slot,
            "label": str(meta.get("label", f"TK {slot}")),
            "display": display,
            "active": aid == self.active_account_id,
            "PlayerId": str(p.get("PlayerId", "")),
            "PlayerName": pname,
            "Lv": lv,
            "Vip": vip,
            "FAP": fap,
            "Diamond": int(p.get("Diamond", 0)),
            "Gold": int(p.get("Gold", 0)),
            "IsNewPlayer": is_new,
            "HeroCount": len(store.state.get("heroes", [])),
            "MaxNodeId": int(store.state.get("battle", {}).get("MaxNodeId", 0)),
            "ArenaRank": rank,
        }

    def list_s1_accounts(self, ensure_slots: int = 3) -> dict[str, Any]:
        with self._acct_lock:
            if ensure_slots > 1:
                self.ensure_s1_account_slots(ensure_slots)
            ordered_ids = [
                m["account_id"]
                for m in sorted(self.s1_meta.values(), key=lambda x: int(x.get("slot", 1)))
                if m["account_id"] in self.s1_accounts
            ]
            summaries = [self._summarize_s1_account(aid) for aid in ordered_ids]
            active_sum = self._summarize_s1_account(self.active_account_id)
            backup_file = self.data_dir / "backups" / "inuyasha_save_backup_latest.json"
            return {
                "ok": True,
                "ActiveAccountId": self.active_account_id,
                "ActiveUserId": active_sum["user_id"],
                "ActiveDisplay": active_sum["display"],
                "Accounts": summaries,
                "BackupAvailable": backup_file.exists(),
                "BackupPath": str(backup_file),
            }

    def switch_s1_account(self, account_id: str) -> dict[str, Any]:
        with self._acct_lock:
            aid = str(account_id).strip()
            # Also allow switching by user_id or slot number
            if aid not in self.s1_accounts:
                for cand_id, meta in self.s1_meta.items():
                    if str(meta.get("user_id")) == aid or f"acct_{aid}" == cand_id:
                        aid = cand_id
                        break
            if aid not in self.s1_accounts:
                m = re.match(r"^acct_(\d+)$", aid)
                if m:
                    slot = int(m.group(1))
                    if 1 <= slot <= 20:
                        self.ensure_s1_account_slots(slot)
            if aid not in self.s1_accounts:
                raise ValueError(f"Unknown S1 account: {account_id}")
            self.active_account_id = aid
            self._save_accounts_index()
            info = self.list_s1_accounts(ensure_slots=max(3, len(self.s1_accounts)))
            info["SwitchedAccount"] = self._summarize_s1_account(aid)
            return info

    def create_s1_account(self, label: str | None = None) -> dict[str, Any]:
        with self._acct_lock:
            max_slot = max((int(m.get("slot", 1)) for m in self.s1_meta.values()), default=1)
            next_slot = max_slot + 1
            aid = f"acct_{next_slot}"
            self._materialize_s1_account(
                {
                    "account_id": aid,
                    "user_id": str(100000 + next_slot),
                    "slot": next_slot,
                    "file": f"s1_acct_{next_slot}.json",
                    "label": label or f"TK {next_slot}",
                    "default_player_id": str(200010 + next_slot),
                    "default_arena_rank": max(100, 1500 - (slot - 1) * 12 if (slot := next_slot) else 1500),
                },
                reset=True,
            )
            self.active_account_id = aid
            self._save_accounts_index()
            info = self.list_s1_accounts(ensure_slots=next_slot)
            info["CreatedAccount"] = self._summarize_s1_account(aid)
            return info

    def reset_s1_account(self, account_id: str | None = None) -> dict[str, Any]:
        """Reset an S1 account (or the active S1 account) cleanly to a fresh new-player state."""
        with self._acct_lock:
            aid = str(account_id or self.active_account_id).strip()
            if aid not in self.s1_accounts:
                for cand_id, meta in self.s1_meta.items():
                    if str(meta.get("user_id")) == aid or f"acct_{aid}" == cand_id:
                        aid = cand_id
                        break
            if aid not in self.s1_accounts:
                raise ValueError(f"Unknown S1 account: {account_id}")
            backups_dir = self.data_dir / "backups"
            backups_dir.mkdir(parents=True, exist_ok=True)
            safety_path = backups_dir / f"pre_reset_{aid}_backup.json"
            self.export_save_bundle(dest_path=safety_path)
            store = self.s1_accounts[aid]
            store.reset_state()
            store.state.setdefault("pvp", {})["rank"] = int(store.default_arena_rank)
            store.state["pvp"]["history_max_rank"] = int(store.default_arena_rank)
            store.save()
            info = self.list_s1_accounts(ensure_slots=max(3, len(self.s1_accounts)))
            info["ResetAccount"] = self._summarize_s1_account(aid)
            info["SafetyBackupPath"] = str(safety_path)
            return info

    def export_save_bundle(self, dest_path: str | Path | None = None) -> dict[str, Any]:
        with self._acct_lock:
            accounts_payload: dict[str, Any] = {}
            for aid, store in self.s1_accounts.items():
                with store._lock:
                    store.save()
                    accounts_payload[aid] = {
                        "meta": copy.deepcopy(self.s1_meta[aid]),
                        "state": copy.deepcopy(store.state),
                    }
            raw_json = json.dumps(accounts_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            checksum = hashlib.sha256(raw_json).hexdigest()
            now_ts = int(time.time())
            bundle = {
                "bundle_format": "inuyasha_seek_jade_standalone_save_v1",
                "exported_at": now_ts,
                "exported_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "active_account_id": self.active_account_id,
                "clock": self.clock.to_dict(),
                "sha256": checksum,
                "accounts": accounts_payload,
            }
            backups_dir = self.data_dir / "backups"
            backups_dir.mkdir(parents=True, exist_ok=True)
            latest_path = backups_dir / "inuyasha_save_backup_latest.json"
            ts_path = backups_dir / f"inuyasha_save_backup_{time.strftime('%Y%m%d_%H%M%S')}.json"
            ProfileStore._write_json_atomic(latest_path, bundle)
            ProfileStore._write_json_atomic(ts_path, bundle)
            written_paths = [str(latest_path), str(ts_path)]
            ext_export = os.environ.get("INUYASHA_PUBLIC_BACKUP_PATH", "").strip()
            for extra in ([dest_path] if dest_path else []) + ([ext_export] if ext_export else []):
                try:
                    ep = Path(extra)
                    ProfileStore._write_json_atomic(ep, bundle)
                    written_paths.append(str(ep))
                except OSError:
                    pass
            return {
                "ok": True,
                "BackupPath": str(latest_path),
                "TimestampedPath": str(ts_path),
                "WrittenPaths": written_paths,
                "AccountCount": len(accounts_payload),
                "SizeBytes": latest_path.stat().st_size if latest_path.exists() else len(raw_json),
                "Sha256": checksum,
                "ExportedAt": now_ts,
            }

    def import_save_bundle(
        self,
        source_path: str | Path | None = None,
        bundle_data: dict[str, Any] | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        if not confirm:
            raise ValueError("Save import requires confirm=True")
        with self._acct_lock:
            if bundle_data is None:
                candidates: list[Path] = []
                if source_path:
                    candidates.append(Path(source_path))
                ext_export = os.environ.get("INUYASHA_PUBLIC_BACKUP_PATH", "").strip()
                if ext_export:
                    candidates.append(Path(ext_export))
                candidates.append(self.data_dir / "backups" / "inuyasha_save_backup_latest.json")
                chosen: Path | None = None
                for c in candidates:
                    if c.exists() and c.is_file():
                        chosen = c
                        break
                if chosen is None:
                    raise ValueError("Không tìm thấy tệp sao lưu để khôi phục")
                bundle_data = json.loads(chosen.read_text(encoding="utf-8"))

            if not isinstance(bundle_data, dict) or bundle_data.get("bundle_format") != "inuyasha_seek_jade_standalone_save_v1":
                raise ValueError("Định dạng tệp sao lưu không hợp lệ")
            accounts_payload = bundle_data.get("accounts")
            if not isinstance(accounts_payload, dict) or "acct_1" not in accounts_payload:
                raise ValueError("Tệp sao lưu thiếu dữ liệu tài khoản S1 (acct_1)")
            expected_sha = str(bundle_data.get("sha256", ""))
            if expected_sha:
                actual_sha = hashlib.sha256(
                    json.dumps(accounts_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest()
                if actual_sha != expected_sha:
                    raise ValueError("Checksum SHA-256 của bản sao lưu không khớp")

            # Safety snapshot before overwriting any save
            backups_dir = self.data_dir / "backups"
            backups_dir.mkdir(parents=True, exist_ok=True)
            safety_path = backups_dir / "pre_import_safety_backup.json"
            self.export_save_bundle(dest_path=safety_path)

            for aid, entry in accounts_payload.items():
                meta = dict(entry.get("meta") or {})
                state_obj = copy.deepcopy(entry.get("state") or {})
                if aid == "acct_1":
                    meta["account_id"] = "acct_1"
                    meta["user_id"] = "100001"
                    meta["slot"] = 1
                    meta["file"] = self.s1_meta["acct_1"]["file"]
                    store = self.s1_accounts["acct_1"]
                    with store._lock:
                        store.state = store._normalize_loaded_state(state_obj)
                        store.event_runtime = EventRuntime(
                            self.clock,
                            build_default_event_registry(self.game_data),
                            store.state,
                        )
                        store._recalc_all_slots_and_fap()
                        store.save()
                    self.s1_meta["acct_1"].update(meta)
                else:
                    meta.setdefault("account_id", aid)
                    fname = str(meta.get("file") or f"s1_{aid}.json")
                    meta["file"] = fname
                    if self.persist:
                        ProfileStore._write_json_atomic(self.data_dir / fname, state_obj)
                    if aid in self.s1_accounts:
                        del self.s1_accounts[aid]
                    self._materialize_s1_account(meta)

            restored_active = str(bundle_data.get("active_account_id", "acct_1"))
            self.active_account_id = restored_active if restored_active in self.s1_accounts else "acct_1"
            self._save_accounts_index()
            res = self.list_s1_accounts(ensure_slots=max(3, len(self.s1_accounts)))
            res["RestoredCount"] = len(accounts_payload)
            res["SafetyBackupPath"] = str(safety_path)
            return res

    def save_clock(self) -> None:
        if self.persist:
            ProfileStore._write_json_atomic(self.clock_path, self.clock.to_dict())

    def get_profile_by_name(self, name: str) -> ProfileStore:
        if name in self.s1_accounts:
            return self.s1_accounts[name]
        if name not in self.profiles:
            raise ValueError(f"Unknown profile: {name}")
        return self.profiles[name]

    @property
    def state(self) -> dict[str, Any]:
        """Expose active default profile state for backward-compatible callers/tests."""
        if self.default_profile == "normal":
            return self.s1_accounts[self.active_account_id].state
        return self.profiles[self.default_profile].state

    def get_profile(
        self,
        server_id: Any = None,
        player_id: str | None = None,
        user_id: str | None = None,
    ) -> ProfileStore:
        if server_id is not None:
            try:
                sid = int(server_id)
                if sid == 2:
                    return self.profiles["debug"]
            except (TypeError, ValueError):
                pass
        if self.default_profile == "debug" and server_id is None:
            return self.profiles["debug"]

        with self._acct_lock:
            if player_id:
                pid_str = str(player_id).strip()
                for store in self.s1_accounts.values():
                    if str(store.state.get("player", {}).get("PlayerId", "")) == pid_str:
                        return store
            if user_id:
                uid_str = str(user_id).strip()
                # If non-default UserID is explicitly sent, resolve its matching S1 account
                if uid_str and uid_str != "100001":
                    for aid, meta in self.s1_meta.items():
                        if str(meta.get("user_id")) == uid_str and aid in self.s1_accounts:
                            return self.s1_accounts[aid]
            return self.s1_accounts.get(self.active_account_id, self.profiles["normal"])

    def handle_rpc(self, req: dict[str, Any]) -> dict[str, Any]:
        req_pid = str(req.get("PlayerId") or "").strip() or None
        req_uid: str | None = None
        if req.get("ModuleName") == "Player" and req.get("MethodName") in ("Login", "Login_ForTest"):
            data = req.get("Data")
            if isinstance(data, list) and len(data) >= 6 and data[5]:
                req_uid = str(data[5]).strip()
                # If an explicit non-100001 user_id logs in, make that account active
                if req_uid != "100001":
                    with self._acct_lock:
                        for aid, meta in self.s1_meta.items():
                            if str(meta.get("user_id")) == req_uid and aid in self.s1_accounts:
                                self.active_account_id = aid
                                self._save_accounts_index()
                                break
        profile = self.get_profile(req.get("ServerId"), player_id=req_pid, user_id=req_uid)
        return profile.handle_rpc(req)


class EmulatorHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler serving game RPCs, extracted assets, and the web PoC."""

    server_version = "SeekJadeRevival/0.2"
    _trace_lock = threading.Lock()

    def log_message(self, fmt: str, *args: Any) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(fmt, *args)

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _send_json(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, "application/json; charset=utf-8", raw)

    def _send_client_json(self, status: int, payload: Any) -> None:
        """Cocos2d-x LuaMinXmlHttpRequest has isNeedUnzip=true and runs ZipUtils::inflateMemory."""
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if self.headers.get("X-Plain-Json") == "1":
            self._send_bytes(status, "application/json; charset=utf-8", raw)
        else:
            self._send_bytes(status, "application/octet-stream", zlib.compress(raw))

    def _append_trace(self, line: str) -> None:
        trace_path = getattr(self.server.emu, "trace_path", None)
        if self.server.emu.persist and trace_path:
            with self._trace_lock:
                Path(trace_path).parent.mkdir(parents=True, exist_ok=True)
                with open(trace_path, "a", encoding="utf-8") as tf:
                    tf.write(f"{line}\n")

    def _require_local_admin(self) -> bool:
        client_ip = str(self.client_address[0] if self.client_address else "")
        if client_ip not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            self._send_json(403, {"error": "Admin API restricted to localhost"})
            return False
        expected = getattr(self.server, "admin_token", "") or ""
        provided = self.headers.get("X-Admin-Token", "")
        if not expected or not hmac.compare_digest(provided, expected):
            self._send_json(401, {"error": "Missing or invalid X-Admin-Token"})
            return False
        return True

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/admin/state":
            if not self._require_local_admin():
                return
            prof_name = (qs.get("profile") or [self.server.emu.default_profile])[0]
            try:
                prof = self.server.emu.get_profile_by_name(prof_name)
                self._send_json(200, {"ok": True, "env": self.server.emu.env, **prof.admin_state_summary()})
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            return
        if path == "/admin/audit":
            if not self._require_local_admin():
                return
            acc = (qs.get("account_id") or [None])[0]
            limit = int((qs.get("limit") or ["100"])[0])
            txs = self.server.emu.ledger.list_transactions(account_id=acc, limit=limit)
            self._send_json(200, {"ok": True, "env": self.server.emu.env, "transactions": txs})
            return
        if path == "/admin/clock":
            if not self._require_local_admin():
                return
            self._send_json(200, {"ok": True, "env": self.server.emu.env, "clock": self.server.emu.clock.to_dict()})
            return
        if path == "/admin/events":
            if not self._require_local_admin():
                return
            prof_name = (qs.get("profile") or [self.server.emu.default_profile])[0]
            try:
                prof = self.server.emu.get_profile_by_name(prof_name)
                with prof._lock:
                    prof._sync_events()
                    info = prof.event_runtime.describe_archive(prof.state["player"])
                    prof.save()
                self._send_json(200, {"ok": True, "env": self.server.emu.env, "profile": prof_name, **info})
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if path in ("/", "/poc", "/poc/"):
            self._serve_poc_file("index.html")
            return
        if path.startswith("/poc/"):
            self._serve_poc_file(path[len("/poc/") :])
            return
        if path.startswith("/assets/"):
            self._serve_game_asset(path[len("/assets/") :])
            return
        if path.startswith("/api/atlas/"):
            name = re.sub(r"[^A-Za-z0-9_.-]", "", path[len("/api/atlas/") :])
            raw = self.server.assets.read(f"res/animation/{name}.atlas")
            if raw is None:
                self._send_json(404, {"error": f"Atlas not found: {name}"})
                return
            self._send_json(200, parse_atlas(raw.decode("utf-8", "replace")))
            return
        if path == "/api/gamedata":
            gd = self.server.emu.game_data
            self._send_json(
                200,
                {
                    "source": gd["source"],
                    "counts": gd["counts"],
                    "heroes": gd["heroes"],
                    "chapters": {"11": gd["chapters"]["11"], "12": gd["chapters"]["12"]},
                    "nodes": {k: v for k, v in gd["nodes"].items() if v.get("chapterModelID") in (11, 12)},
                    "attacks": gd["attacks"],
                },
            )
            return
        if path in ("/api/report.ashx", "/api/stepnew.ashx"):
            self._append_trace(f"{time.strftime('%H:%M:%S')} STEP_GET {self.path}")
            self._send_json(200, {"Code": 0, "Message": "OK"})
            return
        if path.startswith("/sdk/"):
            self._send_json(
                200,
                {"State": 1, "UserID": "100001", "sessionId": "local-revival-session-0001", "Message": "OK"},
            )
            return
        if path == "/account":
            self._send_json(200, self.server.emu.list_s1_accounts(ensure_slots=3))
            return
        if path == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "env": self.server.emu.env,
                    "release": RELEASE_META,
                    "data_dir": str(self.server.emu.data_dir),
                    "game": "InuYasha: Seek Jade",
                    "default_profile": self.server.emu.default_profile,
                    "active_account_id": self.server.emu.active_account_id,
                    "profiles": {
                        name: {
                            "PlayerId": p.state["player"]["PlayerId"],
                            "Lv": p.state["player"]["Lv"],
                            "IsNewPlayer": p.state["player"]["IsNewPlayer"],
                        }
                        for name, p in self.server.emu.profiles.items()
                    },
                },
            )
            return
        self._send_json(404, {"error": "Not found", "path": path})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        path = parsed.path

        if path.startswith("/admin/"):
            if not self._require_local_admin():
                return
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                prof_name = str(payload.get("profile") or self.server.emu.default_profile)
                prof = self.server.emu.get_profile_by_name(prof_name)
                actor = str(payload.get("actor") or "local_admin")
                idem = payload.get("idempotency_key")
                if path == "/admin/grant":
                    res = prof.admin_grant(
                        resources=payload.get("resources"),
                        items=payload.get("items"),
                        heroes=payload.get("heroes"),
                        equips=payload.get("equips"),
                        actor=actor,
                        source=str(payload.get("source") or "admin_grant"),
                        idempotency_key=idem,
                    )
                    self._send_json(200, {"ok": True, "env": self.server.emu.env, **res})
                    return
                if path == "/admin/vip":
                    res = prof.admin_set_vip(
                        vip_lv=payload.get("vip_lv"),
                        vip_exp=payload.get("vip_exp"),
                        actor=actor,
                        source=str(payload.get("source") or "admin_vip"),
                        idempotency_key=idem,
                    )
                    self._send_json(200, {"ok": True, "env": self.server.emu.env, **res})
                    return
                if path == "/admin/prepare":
                    res = prof.admin_prepare_account(
                        target_lv=int(payload.get("target_lv", 1)),
                        vip_lv=payload.get("vip_lv"),
                        actor=actor,
                        source=str(payload.get("source") or "admin_prepare"),
                    )
                    self._send_json(200, {"ok": True, "env": self.server.emu.env, **res})
                    return
                if path == "/admin/clock":
                    action = str(payload.get("action") or "status")
                    clk = self.server.emu.clock
                    if action == "realtime":
                        clk.set_realtime()
                    elif action == "fixed":
                        clk.set_fixed(int(payload.get("fixed_ts", clk.now())))
                    elif action == "offset":
                        clk.set_offset(int(payload.get("offset_sec", 0)))
                    elif action == "advance":
                        clk.advance(int(payload.get("delta_sec", 0)))
                    elif action == "config":
                        clk.apply_config(payload)
                    if "tz_offset_hours" in payload and action != "config":
                        clk.set_tz_offset(int(payload["tz_offset_hours"]))
                    self.server.emu.save_clock()
                    for p_store in self.server.emu.profiles.values():
                        with p_store._lock:
                            p_store._sync_events()
                            p_store._sync_player_recover_times()
                            p_store.save()
                    self._send_json(200, {"ok": True, "env": self.server.emu.env, "clock": clk.to_dict()})
                    return
                if path == "/admin/events":
                    action = str(payload.get("action") or "status")
                    with prof._lock:
                        prof._sync_events()
                        if action in ("mode", "config"):
                            mode = str(
                                payload.get(
                                    "mode",
                                    prof.event_runtime.archive_cfg.get("mode", "concurrent"),
                                )
                            )
                            kwargs: dict[str, Any] = {}
                            for k in (
                                "concurrent_events",
                                "events",
                                "period_mode",
                                "period_sec",
                                "period_anchor_ts",
                                "period_overrides",
                                "carry_over_pity",
                                "carry_over_policy",
                                "settle_unclaimed_credit",
                                "rotation_pool",
                                "rotation_duration_sec",
                                "rotation_anchor_ts",
                                "scheduled_windows",
                                "event_id",
                                "duration_sec",
                            ):
                                if k in payload:
                                    kwargs[k] = payload[k]
                            if "settle_unclaimed_credit" in payload:
                                prof.event_runtime.archive_cfg["settle_unclaimed_credit"] = bool(
                                    payload["settle_unclaimed_credit"]
                                )
                            prof.event_runtime.configure_archive_mode(mode, **kwargs)
                        elif action == "activate":
                            prof.event_runtime.activate_manual_event(
                                str(payload["event_id"]),
                                duration_sec=int(payload["duration_sec"]) if payload.get("duration_sec") is not None else None,
                            )
                        elif action == "schedule":
                            prof.event_runtime.set_scheduled_window(
                                str(payload["event_id"]),
                                int(payload["start_ts"]),
                                int(payload["end_ts"]),
                                enabled=bool(payload.get("enabled", True)),
                            )
                        elif action == "reset":
                            prof.event_runtime.manual_reset_event(
                                str(payload["event_id"]),
                                confirm=payload.get("confirm", False),
                                on_ended=prof._on_timed_event_ended,
                                player=prof.state["player"],
                            )
                        prof._sync_events()
                        info = prof.event_runtime.describe_archive(prof.state["player"])
                        prof.save()
                    self._send_json(200, {"ok": True, "env": self.server.emu.env, "profile": prof_name, **info})
                    return
                self._send_json(404, {"error": f"Unknown admin endpoint: {path}"})
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._send_json(400, {"error": str(exc)})
            return

        if path == "/account":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                action = str(payload.get("action") or "list")
                if action == "list":
                    self._send_json(200, self.server.emu.list_s1_accounts(ensure_slots=int(payload.get("ensure_slots", 3))))
                    return
                if action == "switch":
                    self._send_json(200, self.server.emu.switch_s1_account(str(payload["account_id"])))
                    return
                if action == "create":
                    self._send_json(200, self.server.emu.create_s1_account(label=payload.get("label")))
                    return
                if action == "reset":
                    self._send_json(200, self.server.emu.reset_s1_account(account_id=payload.get("account_id")))
                    return
                if action == "export":
                    self._send_json(200, self.server.emu.export_save_bundle(dest_path=payload.get("dest_path")))
                    return
                if action == "import":
                    self._send_json(
                        200,
                        self.server.emu.import_save_bundle(
                            source_path=payload.get("source_path"),
                            bundle_data=payload.get("bundle_data"),
                            confirm=bool(payload.get("confirm", False)),
                        ),
                    )
                    return
                self._send_json(400, {"ok": False, "error": f"Unknown account action: {action}"})
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
            return

        if path in ("/api/report.ashx", "/api/stepnew.ashx"):
            self._append_trace(f"{time.strftime('%H:%M:%S')} STEP_POST {path} body={body[:300]!r}")
            self._send_json(200, {"Code": 0, "Message": "OK"})
            return

        if path == "/API/ServerList_CheckResource.ashx":
            self._append_trace(f"{time.strftime('%H:%M:%S')} CHECK_RES body={body[:200]!r}")
            self._send_client_json(200, {"Code": 0, "Data": {}})
            return

        if path == "/API/ServerList_Client.ashx":
            self._append_trace(f"{time.strftime('%H:%M:%S')} SERVERLIST body={body[:300]!r}")
            host = self.headers.get("Host") or f"127.0.0.1:{self.server.server_port}"
            host_ip = host.split(":", 1)[0]
            default_sid = 2 if self.server.emu.default_profile == "debug" else 1
            active_sum = self.server.emu._summarize_s1_account(self.server.emu.active_account_id)
            s1_name = f"S1 Normal ({active_sum['display']})"
            self._send_client_json(
                200,
                {
                    "Code": 0,
                    "Data": {
                        "Server": [
                            {
                                "ServerID": 1,
                                "ServerName": s1_name,
                                "ServerState": 1,
                                "ServerHeat": 2 if default_sid == 1 else 1,
                                "ServerUrl": f"http://{host}",
                                "ChatServerUrl": f"{host_ip}:8081",
                                "ChargeServerUrl": f"http://{host}/charge",
                                "OfficialOrTest": 0,
                            },
                            {
                                "ServerID": 2,
                                "ServerName": "S2 Debug R1 (Lv10/VIP5)",
                                "ServerState": 1,
                                "ServerHeat": 3 if default_sid == 2 else 1,
                                "ServerUrl": f"http://{host}",
                                "ChatServerUrl": f"{host_ip}:8081",
                                "ChargeServerUrl": f"http://{host}/charge",
                                "OfficialOrTest": 0,
                            },
                        ],
                        "ServerHistory": [default_sid],
                        "Resource": {},
                        "UserInfo": {
                            "UserID": active_sum["user_id"],
                            "PartnerId": "1001",
                            "LoginInfo": "{}",
                        },
                    },
                },
            )
            return

        if path == "/client.aspx":
            try:
                req = json.loads(body.decode("utf-8")) if body else {}
            except json.JSONDecodeError:
                self._send_client_json(400, {"Status": -32, "Message": "Invalid JSON"})
                return
            resp = self.server.emu.handle_rpc(req)
            self._send_client_json(200, resp)
            return

        self._send_json(404, {"error": "Unsupported POST endpoint", "path": path})

    def _serve_poc_file(self, rel: str) -> None:
        safe = os.path.normpath(rel).lstrip("/")
        target = (POC_DIR / safe).resolve()
        if not str(target).startswith(str(POC_DIR.resolve())) or not target.is_file():
            self._send_bytes(404, "text/plain", b"PoC file not found")
            return
        ctype, _ = mimetypes.guess_type(str(target))
        self._send_bytes(200, ctype or "application/octet-stream", target.read_bytes())

    def _serve_game_asset(self, rel: str) -> None:
        raw = self.server.assets.read(rel)
        if raw is None:
            self._send_bytes(404, "text/plain", f"Asset not found: {rel}".encode("utf-8"))
            return
        ctype, _ = mimetypes.guess_type(rel)
        self._send_bytes(200, ctype or "application/octet-stream", raw)


class ThreadingEmulatorServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        persist: bool = True,
        quiet: bool = False,
        new_player: bool = False,
        default_profile: str = "normal",
        env: str = "stable",
        data_dir: Path | None = None,
        trace_path: Path | None = None,
        admin_token: str | None = None,
    ) -> None:
        self.emu = GameEmulatorState(
            persist=persist,
            new_player=new_player,
            default_profile=default_profile,
            env=env,
            data_dir=data_dir,
            trace_path=trace_path,
        )
        tok = admin_token or os.environ.get("INUYASHA_ADMIN_TOKEN") or secrets.token_urlsafe(24)
        self.admin_token = tok
        if persist:
            tok_file = self.emu.data_dir / ".admin_token"
            self.emu.data_dir.mkdir(parents=True, exist_ok=True)
            tok_file.write_text(tok, encoding="utf-8")
            os.chmod(tok_file, 0o600)
        self.assets = AssetArchive([(VN_APK_PATH, VN_OBB_PATH), (EN_APK_PATH, EN_OBB_PATH)])
        self.quiet = quiet
        super().__init__(server_address, EmulatorHandler)


def main() -> None:
    if __name__ == "__main__" and not os.environ.get("INUYASHA_HOTPATCH_ACTIVE"):
        try:
            idx = sys.argv.index("--data-dir")
            if idx + 1 < len(sys.argv):
                hotpatch_dir = Path(sys.argv[idx + 1]).resolve() / "hotpatch"
                hotpatch_emu = hotpatch_dir / "emulator.py"
                if hotpatch_emu.is_file() and hotpatch_emu.resolve() != Path(__file__).resolve():
                    os.environ["INUYASHA_HOTPATCH_ACTIVE"] = "1"
                    cur_pypath = os.environ.get("PYTHONPATH", "")
                    os.environ["PYTHONPATH"] = f"{hotpatch_dir}:{cur_pypath}" if cur_pypath else str(hotpatch_dir)
                    print(f"[HOTPATCH] Delegating backend startup to {hotpatch_emu}", flush=True)
                    os.execv(sys.executable, [sys.executable, str(hotpatch_emu), *sys.argv[1:]])
        except ValueError:
            pass

    parser = argparse.ArgumentParser(description="InuYasha: Seek Jade Local Server Emulator")
    parser.add_argument("--env", choices=["stable", "dev"], default="stable", help="Server environment preset")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (use 0.0.0.0 for LAN/Pixel 3 XL)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: 8080 stable, 8082 dev)")
    parser.add_argument("--profile", choices=["normal", "debug"], default="normal", help="Default server profile")
    parser.add_argument("--data-dir", type=Path, default=None, help="Override save/ledger directory")
    parser.add_argument("--trace-path", type=Path, default=None, help="Override RPC trace log path")
    parser.add_argument("--admin-token", default=None, help="Local Admin API token (default: INUYASHA_ADMIN_TOKEN or generated)")
    parser.add_argument(
        "--new-player",
        "--reset-normal",
        action="store_true",
        dest="reset_normal",
        help="Reset NORMAL_PROFILE to fresh IsNewPlayer=1 state (never alters DEBUG_PROFILE)",
    )
    args = parser.parse_args()

    port = args.port if args.port is not None else int(ENV_PRESETS[args.env]["port"])
    srv = ThreadingEmulatorServer(
        (args.host, port),
        new_player=args.reset_normal,
        default_profile=args.profile,
        env=args.env,
        data_dir=args.data_dir,
        trace_path=args.trace_path,
        admin_token=args.admin_token,
    )
    print(
        f"InuYasha: Seek Jade [{srv.emu.env.upper()}] listening on http://{args.host}:{port}/poc/ "
        f"(data_dir={srv.emu.data_dir}, default={args.profile}, "
        f"normal_pid={srv.emu.profiles['normal'].state['player']['PlayerId']}, "
        f"debug_pid={srv.emu.profiles['debug'].state['player']['PlayerId']})"
    )

    def _handle_sigterm(_signum: int, _frame: Any) -> None:
        threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down emulator...")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
