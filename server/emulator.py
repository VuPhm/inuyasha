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
import copy
import hmac
import http.server
import json
import math
import mimetypes
import os
import random
import re
import secrets
import signal
import socketserver
import threading
import time
import urllib.parse
import uuid
import zipfile
import zlib
from pathlib import Path
from typing import Any

from combat_sim import simulate_fight_info
from economy_audit import ResourceLedger

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


class ProfileStore:
    """Single-profile game state & RPC engine backed by extracted EN 5.1.1 config."""

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
    ) -> None:
        self.profile_name = profile_name  # "normal" or "debug"
        self.game_data = game_data
        self.ledger = ledger
        self.state_path = state_path
        self.persist = persist
        self.legacy_seed_path = legacy_seed_path
        self.trace_path = trace_path
        self._lock = threading.RLock()
        self.state = self._load_or_init(reset=reset)

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
            next_pid = "200001"
            if reset and prev_player_id and prev_player_id.isdigit():
                next_pid = str(max(200001, int(prev_player_id) + 1))
            state = self._create_normal_default_state(player_id=next_pid)
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
            "RecoverTime": int(time.time()) + int(ec.get("restoreFightNumDaily", 900)),
        }

    def _normalize_loaded_state(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure loaded states have required fields without altering saved progress."""
        data.setdefault("equips", [])
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
        self._sanitize_legacy_debris_and_boss_drops(data, boss_state)
        p = data.setdefault("player", {})
        p.setdefault("ChargeNum", 0)
        p.setdefault("VipEXP", 0)
        p.setdefault("PVPCoin", 0)
        p.setdefault("BossCoin", int(boss_state.get("jifen", 0)))
        p.setdefault("FashionModelId", 0)
        self._sync_player_recover_times(p)
        for h in data.get("heroes", []):
            h.setdefault("WarfareColorLv", 0)
            h.setdefault("WarfareLv", 0)
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
    _ATTR_RESOURCE_TYPES: frozenset[int] = frozenset({1101, 1102, 1103, 1111, 1112, 1115, 1116, 1117, 1120})

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
        gm = self.game_data.get("goods_model", {}).get(mkey)
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
        """Normalize VITMaxNum/STAMaxNum against canonical config and keep recover timestamps valid."""
        p = player if player is not None else self.state["player"]
        now = int(time.time())
        cfg_vit_max, vit_cd, cfg_sta_max, sta_cd = self._canonical_recover_limits()

        raw_vit_max = p.get("VITMaxNum")
        vit_max = max(cfg_vit_max, int(raw_vit_max)) if isinstance(raw_vit_max, (int, float)) else cfg_vit_max
        p["VITMaxNum"] = vit_max

        raw_sta_max = p.get("STAMaxNum")
        sta_max = max(cfg_sta_max, int(raw_sta_max)) if isinstance(raw_sta_max, (int, float)) else cfg_sta_max
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
        return {
            "Id": inst_id or str(uuid.uuid4()),
            "HeroModelId": int(hero_model_id),
            "Lv": lv,
            "Step": step,
            "RebornStep": 0,
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

    def _compute_slot_property(
        self,
        slot: dict[str, Any],
        heroes_by_id: dict[str, dict[str, Any]],
        include_player_star: bool = True,
    ) -> dict[str, Any]:
        hero_id = slot.get("HeroId", EMPTY_ENTITY_ID)
        hero = heroes_by_id.get(hero_id)
        if not hero:
            return _zero_slot_property()

        cfg = self.game_data["heroes"][str(hero["HeroModelId"])]
        lv = int(hero["Lv"])
        step = int(hero.get("Step", 0))
        step_attr = self._get_step_attr(cfg, step)

        hero_hp = int(cfg["HPBase"] + cfg["HPUp"] * (lv - 1) + step_attr["HP"])
        hero_ap = int(cfg["APBase"] + cfg["APUp"] * (lv - 1) + step_attr["AP"])
        hero_def = int(cfg["DEFBase"] + cfg["DEFUp"] * (lv - 1) + step_attr["DEF"])
        hero["HP"] = hero_hp
        hero["AP"] = hero_ap
        hero["DEF"] = hero_def

        eq_hp, eq_ap, eq_def, eq_fsp = 0, 0, 0, 0
        group_counts: dict[int, int] = {}
        equips_cfg = self.game_data.get("equips", {})
        for key in ("Weapon", "Helmet", "Clothes", "Necklace"):
            eq = slot.get(key)
            if eq and eq.get("EquipModelId"):
                m = equips_cfg.get(str(eq["EquipModelId"]), {})
                elv = int(eq.get("Lv", 0))
                eq_hp += int(m.get("HP", 0) + m.get("HPUP", 0) * elv)
                eq_ap += int(m.get("AP", 0) + m.get("APUP", 0) * elv)
                eq_def += int(m.get("DEF", 0) + m.get("DEFUP", 0) * elv)
                eq_fsp += int(m.get("FSP", 0))
                gid = int(m.get("equipGroupID", 0))
                if gid > 0:
                    group_counts[gid] = group_counts.get(gid, 0) + 1

        set_hp, set_ap, set_def = 0, 0, 0
        equip_groups = self.game_data.get("equip_group", {})
        for gid, cnt in group_counts.items():
            tiers = equip_groups.get(str(gid), {})
            for req_str, bonus in tiers.items():
                if cnt >= int(req_str):
                    set_hp += int(bonus.get("HP", 0))
                    set_ap += int(bonus.get("AP", 0))
                    set_def += int(bonus.get("DEF", 0))

        treasures_cfg = self.game_data.get("treasures", {})
        for tkey in ("Book", "Horse"):
            tr = slot.get(tkey)
            if tr and tr.get("TreasureModelId"):
                tm = treasures_cfg.get(str(tr["TreasureModelId"]), {})
                tlv = int(tr.get("Lv", 0))
                up_r = float(tm.get("upR", 0.25))
                scale = tlv * up_r + 1.0
                eq_hp += int(float(tm.get("HPBase", 0)) * scale)
                eq_ap += int(float(tm.get("APBase", 0)) * scale)

        star_bonus = (
            self._get_slot_star_bonuses(int(slot.get("SlotId", 0)))
            if (include_player_star and hasattr(self, "state"))
            else {"HP": 0, "AP": 0, "DEF": 0}
        )
        hp1 = hero_hp + eq_hp + set_hp + star_bonus["HP"]
        ap1 = hero_ap + eq_ap + set_ap + star_bonus["AP"]
        def1 = hero_def + eq_def + set_def + star_bonus["DEF"]
        fsp = int(cfg.get("FSP", 500)) + step_attr["FSP"] + eq_fsp
        fap = int(hp1 + ap1 * 5 + def1 * 5)

        return {
            "HP": hp1,
            "AP": ap1,
            "DEF": def1,
            "SPD": fsp,
            "FSP": fsp,
            "FAP": fap,
            "AP1": ap1,
            "APR1": 10000,
            "AP2": 0,
            "APR2": 0,
            "APAdd": 0,
            "APHero": 0,
            "APHeroR": 0,
            "DEF1": def1,
            "DEFR1": 10000,
            "DEF2": 0,
            "DEFR2": 0,
            "DEFAdd": 0,
            "DEFHero": 0,
            "DEFHeroR": 0,
            "HP1": hp1,
            "HPR1": 10000,
            "HP2": 0,
            "HPR2": 0,
            "HPAdd": 0,
            "HPHero": 0,
            "HPHeroR": 0,
            "APToHPHeroR": 0,
            "RP": int(cfg.get("RP", 50)),
            "HIT": int(cfg.get("HIT", 10000)),
            "DOD": int(cfg.get("DOD", 0)),
            "CRI": int(cfg.get("CRI", 0)),
            "TEN": int(cfg.get("TEN", 0)),
            "BLO": int(cfg.get("BLO", 0)),
            "BOG": int(cfg.get("BOG", 0)),
            "CRId": int(cfg.get("CRID", 0)),
            "TEND": int(cfg.get("TEND", 0)),
        }

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

    @staticmethod
    def _parse_attr_pairs(attr_str: str) -> list[tuple[int, int, int]]:
        out: list[tuple[int, int, int]] = []
        for part in (attr_str or "").split("||"):
            segs = [s.strip() for s in part.split(",") if s.strip()]
            if len(segs) >= 2:
                out.append((int(segs[0]), 0, int(float(segs[1]))))
        return out

    def _recalc_all_slots_and_fap(self) -> None:
        heroes_by_id = {h["Id"]: h for h in self.state["heroes"]}
        total_fap = 0
        for slot in self.state["slots"]:
            slot["Property"] = self._compute_slot_property(slot, heroes_by_id)
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
                    "Gem": [],
                }
            else:
                s = {
                    "SlotId": idx,
                    "HeroId": EMPTY_ENTITY_ID,
                    "HeroModelId": 0,
                    "Gem": [],
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
                "OutZiCount": 5,
            },
            "explore": self._default_explore_state(),
            "shop_bought": {},
            "lv_plan": {"open": False, "rewarded": []},
            "vip_welfare_drawn_date": "",
            "charge_state": {"first_bought": [], "drawn_boxes": [], "orders": {}},
            "month_cards": {},
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
            slot = {"SlotId": idx, "HeroId": inst_id, "HeroModelId": int(hid), "Gem": []}
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
        new_fashions: list[dict[str, Any]] = []

        attr_map = {
            1101: "EXP",
            1102: "VIT",
            1103: "STA",
            1111: "Diamond",
            1112: "Gold",
            1115: "PVPCoin",
            1116: "HeroCoin",
            1117: "HeroEXP",
            1120: "BossCoin",
        }

        for idx, (rtype, rmodel, rnum) in enumerate(res_tuples):
            if rnum <= 0:
                continue
            if rtype in attr_map:
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
                    eq_inst = {
                        "Id": str(uuid.uuid4()),
                        "EquipModelId": rmodel,
                        "Lv": 0,
                        "Gold": 0,
                        "ExtraCount": 0,
                        "APExtra": 0,
                        "HPExtra": 0,
                        "DEFExtra": 0,
                        "DAMADDExtra": 0,
                        "DAMCUTExtra": 0,
                    }
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
        if new_fashions:
            bundle["Fashion"] = new_fashions
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
            exp_st = self.state.setdefault("explore", self._default_explore_state())
            exp_st["RemainNum"] = min(
                int(exp_st.get("MaxNum", 25)) + 50,
                int(exp_st.get("RemainNum", 0)) + crit_num * (new_lv - old_lv),
            )
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
            if self.profile_name == "normal" and self.state["slots"]:
                main_hid = self.state["slots"][0].get("HeroId")
                for h in self.state["heroes"]:
                    if h["Id"] == main_hid:
                        h["Lv"] = new_lv
                        break
                self._recalc_all_slots_and_fap()
        return old_lv, new_lv

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
        override_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
            hp = max(1, int((cfg["HPBase"] + cfg["HPUp"] * (lv - 1) + step_attr["HP"]) * hp_mult))
            ap = max(1, int((cfg["APBase"] + cfg["APUp"] * (lv - 1) + step_attr["AP"]) * ap_mult))
            defense = max(0, int((cfg["DEFBase"] + cfg["DEFUp"] * (lv - 1) + step_attr["DEF"]) * def_mult))
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
            "RAId": cfg.get("RAID", 1002008),
            "HeroModelId": cfg["ID"],
            "Name": cfg["name"],
            "Quality": cfg.get("quality", 15),
            "RaceId": cfg.get("raceID", 1),
            "FSP": fsp,
            "DAM": 0,
            "CP": 0,
            "BCP": 0,
            "CPR": 0,
            "BCPR": 0,
            "DAMADD": 0,
            "DAMCUT": 0,
            "DAMADDR": 0,
            "DAMCUTR": 0,
            "BuffList": [],
            "IsBoss": is_boss,
            "BodyTypeR": 12500 if is_boss else 10000,
            "Step": step if self.profile_name == "normal" else max(1, step),
            "RebornStep": reborn_step,
            "LargePic": cfg["largePic"],
            "SmallPic": cfg["smallPic"],
            "SkillSound": cfg.get("skillSound", "0"),
        }

    def handle_rpc(self, req: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            return self._handle_rpc_locked(req)

    def _handle_rpc_locked(self, req: dict[str, Any]) -> dict[str, Any]:
        module = req.get("ModuleName", "")
        method = req.get("MethodName", "")
        data = req.get("Data") or []
        key = f"{module}.{method}"

        # Persist piggybacked ExtensionString.GuideInfo from client HttpClient.lua
        ext = req.get("ExtensionString") or {}
        if isinstance(ext, dict) and ext.get("GuideInfo"):
            steps = self.state["player"].setdefault("StepCountList", {})
            changed = False
            for g in ext["GuideInfo"]:
                if isinstance(g, dict) and "GuideId" in g and "Ordinal" in g:
                    gid_str = str(g["GuideId"])
                    ordinal = int(g["Ordinal"])
                    if ordinal > int(steps.get(gid_str, 0)):
                        steps[gid_str] = ordinal
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
            "HeroRecruit.RecruitInfo": self._rpc_recruit_info,
            "HeroRecruit.Recruit": self._rpc_recruit,
            "Hero.HeroLvUp": self._rpc_hero_lv_up,
            "Hero.HeroStepUp": self._rpc_hero_step_up,
            "Slot.HeroCombat": self._rpc_slot_hero_combat,
            "Slot.OneKeyEquipCombat": self._rpc_slot_one_key_equip_combat,
            "Slot.SlotFormations": self._rpc_slot_formations,
            "SlotFormation.GetFormation": self._rpc_get_formation,
            "SlotFormation.Change": self._rpc_change_formation,
            "Equip.EquipCompose": self._rpc_equip_compose,
            "Equip.EquipOneKeyCompose": self._rpc_equip_one_key_compose,
            "Equip.OneKeyEquipLvUp": self._rpc_one_key_equip_lv_up,
            "Equip.EquipLvUpForCount": self._rpc_equip_lv_up_for_count,
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
            "Explore.GetInfo": self._rpc_explore_get_info,
            "Explore.Explore": self._rpc_explore_run,
            "Explore.OneKeyExplore": self._rpc_explore_one_key,
            "Explore.BuyExploreNum": self._rpc_explore_buy,
            "Explore.DrawDailyReward": self._rpc_explore_draw_daily,
            "LightenStar.GetLightenStarInfo": self._rpc_lighten_star_info,
            "LightenStar.LightenStar": self._rpc_lighten_star_up,
            "LightenStar.LightenStarForOneKey": self._rpc_lighten_star_one_key,
            "ShopGoods.ShopGoodsList": self._rpc_shop_goods_list,
            "ShopGoods.GetShopGoodsInfo": self._rpc_get_shop_goods_info,
            "ShopGoods.BuyGoods": self._rpc_shop_buy_goods,
            "Goods.GoodsUse": self._rpc_goods_use,
            "TreasureLootProtect.GetTreasureLootProtectInfo": self._rpc_treasure_protect_info,
            "TreasureLootProtect.TreasureLootProtect": self._rpc_treasure_protect_buy,
            "TreasureLoot.TreasureDebrisTargetList": self._rpc_treasure_target_list,
            "TreasureLoot.TreasureLoot": self._rpc_treasure_loot,
            "TreasureLoot.TreasureLootForCount": self._rpc_treasure_loot_count,
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
            "PVPShop.PVPShopBuy": self._rpc_pvp_shop_buy,
            "Daydayfund.GetInfo": self._rpc_daydayfund_get_info,
            "Daydayfund.Invest": self._rpc_daydayfund_invest,
            "Daydayfund.Harvest": self._rpc_daydayfund_harvest,
            "StartWorkReward.GetStartworkRewardInfo": self._rpc_startwork_get_info,
            "StartWorkReward.GetStartworkReward": self._rpc_startwork_get_reward,
            "Fashion.DressUp": self._rpc_fashion_dress_up,
            "Fashion.StepUp": self._rpc_fashion_step_up,
            "Fashion.Resolve": self._rpc_fashion_resolve,
            "MonthSignInfo.GetInfo": lambda _d: [],
            "Notice.GetNoticeList": lambda _d: [],
            "Enemy.GetEnemyList": lambda _d: [],
            "TraderInfo.GetInfo": lambda _d: {"TraderInfo": None},
            "OnlineReward.OnlineRewardInfo": lambda _d: {},
            "YiYuan.GetInfo": lambda _d: {},
            "TeambattleInfo.GetInviteInfo": lambda _d: {},
            "GiftLogin.SignInfo": lambda _d: {},
            "Reward.Rewars": lambda _d: [],
        }
        fn = handlers.get(key)
        handled = fn is not None
        value = fn(data) if fn else {}
        status = int(self._last_rpc_context.get("status", 0))
        self._sync_player_recover_times()

        if self.persist and self.trace_path:
            with open(self.trace_path, "a", encoding="utf-8") as tf:
                tf.write(
                    f"{time.strftime('%H:%M:%S')} [{self.profile_name}] RPC {key} "
                    f"handled={handled} status={status} data={json.dumps(data, ensure_ascii=False)}\n"
                )

        if key in {"Player.Login", "Player.Login_ForTest", "Player.NewPlayer"}:
            avatar: dict[str, Any] = {}
        elif key == "Player.GetInitData":
            avatar = {"TimedActivityOpenInfo": {}, "RedDotInfo": self._compute_red_dot_info()}
        else:
            avatar = {k: v for k, v in self.state["player"].items() if k != "Lv"}
            if self._last_rpc_context.get("lv_changed"):
                avatar["Lv"] = self.state["player"]["Lv"]
                avatar["XYCurCount"] = int(self.state.get("explore", {}).get("RemainNum", 15))
            if self._last_rpc_context.get("slots_changed"):
                avatar["SlotInfo"] = self.state["slots"]
            if self._last_rpc_context.get("goods_changed") is not None:
                avatar["GoodsInfo"] = self._last_rpc_context["goods_changed"]
            if self._last_rpc_context.get("treasure_debris_changed") is not None:
                avatar["TreasureDebrisInfo"] = self._last_rpc_context["treasure_debris_changed"]
            avatar["TimedActivityOpenInfo"] = {}
            avatar["RedDotInfo"] = self._compute_red_dot_info()

        return {
            "Status": status,
            "TimeTick": int(time.time()),
            "Avatar": avatar,
            "Value": value,
        }

    def _rpc_login(self, _data: Any) -> dict[str, Any]:
        self.state["player"]["LastLoginTime"] = int(time.time())
        self._sync_player_recover_times()
        self.save()
        return dict(self.state["player"])

    def _rpc_new_player(self, data: Any) -> dict[str, Any]:
        player_name = str(data[0])[:24] if isinstance(data, list) and len(data) >= 1 else "Adventurer"
        gender = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1
        main_model_id = 12010001 if gender == 0 else 12010004

        self.state["player"]["PlayerName"] = player_name
        self.state["player"]["Gender"] = gender
        self.state["player"]["HeadImageId"] = main_model_id
        self.state["player"]["IsNewPlayer"] = 0

        if self.profile_name == "normal":
            main_hero = self._build_hero_instance(main_model_id, lv=1, step=0)
            self.state["heroes"] = [main_hero]
            self.state["slots"][0]["HeroId"] = main_hero["Id"]
            self.state["slots"][0]["HeroModelId"] = main_model_id
            self._recalc_all_slots_and_fap()

        self.save()
        return {"PlayerId": self.state["player"]["PlayerId"]}

    def _rpc_get_init_data(self, _data: Any) -> dict[str, Any]:
        self._sync_player_recover_times()
        module_subs = self.game_data.get("module_subs", {})
        if module_subs:
            open_submodules = sorted(
                int(mid) for mid, item in module_subs.items() if int(item.get("ifOpen", 0)) == 1
            )
        else:
            open_submodules = [1000, 1100, 1200, 1300, 1400, 2200, 2201, 3800, 3801]
        modules = [
            {"SubModuleId": mid, "OrderNum": idx, "IfOpen": 1}
            for idx, mid in enumerate(open_submodules, start=1)
        ]
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
            "MateInfo": [],
            "SlotFormationInfo": self.state["embattle"],
            "GoodsHeroDebrisInfo": hero_debris,
            "GoodsEquipDebrisInfo": equip_debris,
            "GoodsPropsInfo": props_goods,
            "TreasureDebrisInfo": self.state.get("treasure_debris", []),
            "BagInfo": [{"BagModelId": bid, "Size": 200, "ExpandNum": 0} for bid in range(1, 10)],
            "SkillList": [],
            "ModulesInfo": modules,
            "StarSignInfo": [],
            "XYCurCount": int(self.state.get("explore", {}).get("RemainNum", 15)),
            "FashionInfo": self.state.get("fashions", []),
            "GemInfo": [],
            "PetInfo": [],
            "WarfarespiritInfo": [],
            "RebornGoodsList": [],
            "RebornnComposeStatus": [],
            "RedDotInfo": self._compute_red_dot_info(),
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
        after = (
            p.get("VITMaxNum"),
            p.get("VITNextRecoverTime"),
            p.get("STAMaxNum"),
            p.get("STANextRecoverTime"),
        )
        if after != before:
            self.save()
        return dict(p)

    def _rpc_alter_step_count(self, data: Any) -> dict[str, Any]:
        if isinstance(data, list) and len(data) >= 2:
            steps = self.state["player"].setdefault("StepCountList", {})
            steps[str(data[0])] = int(data[1])
            self.save()
        return {}

    def _rpc_get_step_count_reward(self, data: Any) -> dict[str, Any]:
        event_id = int(data[0]) if isinstance(data, list) and data else 0
        claimed = self.state.setdefault("claimed_step_rewards", [])
        if event_id in claimed:
            self._last_rpc_context["status"] = -1136  # Already claimed per CommonFunc.lua:2899
            return {}

        reward_map: dict[int, list[tuple[int, int, int]]] = {
            76001: [(1304, 13040130, 5)],  # 5 white necklaces if not dropped in 1-3
            1641: [(1301, 13010130, 1)],
            1602: [(1111, 0, 200)],
            1761: [(1504, 15040101, 1), (1504, 15040102, 1)],  # Lv 14 Grab guide starter mount fragments
            1881: [(1503, 15032101, 1), (1503, 15032102, 1)],  # Backup Grab guide book fragments
        }
        tuples = reward_map.get(event_id, [])
        claimed.append(event_id)
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"step_reward:{event_id}",
            tx_prefix=f"step_reward:{self.profile_name}:{self.state['player']['PlayerId']}:{event_id}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_recruit_info(self, _data: Any) -> dict[str, Any]:
        now = int(time.time())
        rs = self.state.setdefault(
            "recruit_state",
            {"MidAlreadyUseResource": False, "HigAlreadyUseResource": False, "OutZiCount": 5},
        )
        return {
            "OutZiCount": int(rs.get("OutZiCount", 5)),
            "CooledInfo": [
                {"Type": 2, "CooledTime": int(rs.get("GoodReadyAt", now))},
                {"Type": 3, "CooledTime": int(rs.get("ExcellentReadyAt", now))},
            ],
            "MidAlreadyUseResource": bool(rs.get("MidAlreadyUseResource", False)),
            "HigAlreadyUseResource": bool(rs.get("HigAlreadyUseResource", False)),
        }

    def _rpc_recruit(self, data: Any) -> dict[str, Any]:
        rtype = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 2
        is_free = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1
        now = int(time.time())
        rs = self.state.setdefault(
            "recruit_state",
            {"MidAlreadyUseResource": False, "HigAlreadyUseResource": False, "OutZiCount": 5},
        )
        rec_cfg = self.game_data.get("hero_recruit", {}).get(str(rtype), {})
        pool_str = rec_cfg.get("outShowMain") or rec_cfg.get("outShowAll") or "12011014"
        pool = [int(x) for x in pool_str.split(",") if x.strip().isdigit()]

        # Spend cost if not free
        if rtype == 1:
            talisman = next((g for g in self.state.get("goods", []) if g["GoodsModelId"] == 16050003), None)
            if not talisman or talisman["Num"] < 1:
                self._last_rpc_context["status"] = -1
                return {}
            talisman["Num"] -= 1
        elif is_free == 0:
            cost = 280 if rtype == 3 else (2680 if rtype == 30 else 80)
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -cost,
                source=f"recruit:{rtype}",
            )

        count = 10 if rtype in (10, 30) else 1
        tuples: list[tuple[int, int, int]] = []
        for idx in range(count):
            if rtype == 2 and not rs.get("MidAlreadyUseResource", False):
                chosen_hid = 12011014  # Ayame (4*/5* starter summon from Destiny Recruit pool)
            else:
                chosen_hid = pool[idx % len(pool)] if pool else 12011014
            tuples.append((1201, chosen_hid, 1))

        gold_gain = int(rec_cfg.get("goldCoin", 0) or (1000 if rtype == 2 else 0))
        if gold_gain > 0:
            tuples.append((1112, 0, gold_gain))

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"recruit:{rtype}",
            tx_prefix=f"recruit:{self.profile_name}:{now}:{uuid.uuid4()}",
        )

        cd_min = int(rec_cfg.get("freeTimeCD", 1380))
        next_tick = now + max(0, cd_min) * 60
        if rtype == 2:
            rs["MidAlreadyUseResource"] = True
            rs["GoodReadyAt"] = next_tick
        elif rtype == 3:
            rs["HigAlreadyUseResource"] = True
            rs["ExcellentReadyAt"] = next_tick
            rs["OutZiCount"] = max(0, int(rs.get("OutZiCount", 5)) - 1)

        self.save()
        return {
            "CooledTick": next_tick,
            "MidAlreadyUseResource": bool(rs.get("MidAlreadyUseResource", False)),
            "HigAlreadyUseResource": bool(rs.get("HigAlreadyUseResource", False)),
            "OutZiCount": int(rs.get("OutZiCount", 5)),
            "BaseGetGameResourceList": base_res,
        }

    def _rpc_slot_hero_combat(self, data: Any) -> dict[str, Any]:
        slot_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 1
        hero_id = str(data[1]) if isinstance(data, list) and len(data) >= 2 else EMPTY_ENTITY_ID
        target_slot = next((s for s in self.state["slots"] if int(s["SlotId"]) == slot_id), None)
        if not target_slot:
            self._last_rpc_context["status"] = -1
            return {}

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
                    if other.get(skey, {}).get("Id") == eid:
                        other.pop(skey, None)
                target_slot[skey] = {
                    "Id": eq["Id"],
                    "EquipModelId": eq["EquipModelId"],
                    "Lv": eq["Lv"],
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

    def _enrich_slot_for_view(self, slot: dict[str, Any], heroes_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
        enriched = copy.deepcopy(slot)
        hero = heroes_by_id.get(str(slot.get("HeroId", "")))
        if hero:
            enriched["Hero"] = dict(hero)
        return enriched

    def _rpc_slot_formations(self, data: Any) -> dict[str, Any]:
        target_id = str(data[0]) if isinstance(data, list) and data and data[0] else str(self.state["player"]["PlayerId"])
        if target_id == str(self.state["player"]["PlayerId"]):
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
                "MateInfos": [],
                "SlotFormationInfo": self.state["embattle"],
                "SkillInfos": [],
                "CombatPet": None,
            }
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
        self.save()
        return {"SlotFormationInfo": self.state["embattle"]}

    def _compose_equips(self, equip_ids: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
        equips_by_id = {e["Id"]: e for e in self.state.get("equips", [])}
        mats = [equips_by_id[eid] for eid in equip_ids if eid in equips_by_id]
        if len(mats) < 5:
            return [], []
        mats = mats[:5]
        equips_cfg = self.game_data.get("equips", {})
        first_cfg = equips_cfg.get(str(mats[0]["EquipModelId"]), {})
        color_lv = int(first_cfg.get("colorLV", 1))
        type_id = int(first_cfg.get("typeID", 1304))

        ec_cfg = self.game_data.get("equip_color", {}).get(str(color_lv), {})
        next_color = int(ec_cfg.get("colorFinally", color_lv + 1))
        gold_cost = int(ec_cfg.get("colorUpUseNum", 1000))
        if gold_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Gold",
                -gold_cost,
                source=f"equip_compose:color_{color_lv}",
            )

        # Pick deterministic Set Out / matching type next-color equip (e.g. 5x 13040130 -> 13040215 Set Out Necklace)
        candidates = sorted(
            [
                int(eid)
                for eid, item in equips_cfg.items()
                if int(item.get("colorLV", 0)) == next_color and int(item.get("typeID", 0)) == type_id
            ]
        )
        out_model_id = candidates[0] if candidates else 13040215
        consumed_ids = [m["Id"] for m in mats]
        self.state["equips"] = [e for e in self.state["equips"] if e["Id"] not in set(consumed_ids)]
        base_res = self._grant_resources_from_tuples(
            [(type_id, out_model_id, 1)],
            source=f"equip_compose:{out_model_id}",
            tx_prefix=f"equip_compose:{self.profile_name}:{uuid.uuid4()}",
        )
        return consumed_ids, base_res

    def _rpc_equip_compose(self, data: Any) -> dict[str, Any]:
        equip_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        consumed, base_res = self._compose_equips([str(x) for x in equip_ids])
        if not consumed:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"ConsumeList": consumed, "BaseGetGameResourceList": base_res}

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
            if eq["Id"] in equipped_ids:
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
        self.save()
        return {"ConsumeList": consumed_all, "BaseGetGameResourceList": res_all}

    def _level_up_equip(self, eq: dict[str, Any], target_max_lv: int) -> bool:
        equips_cfg = self.game_data.get("equips", {})
        lv_up_tbl = self.game_data.get("equip_lv_up", {})
        clv = str(equips_cfg.get(str(eq["EquipModelId"]), {}).get("colorLV", 1))
        costs = lv_up_tbl.get(clv, {})
        cur_lv = int(eq.get("Lv", 0))
        if cur_lv >= target_max_lv:
            return False
        cost = int(costs.get(str(cur_lv), {}).get("lvUpUseNum", 0))
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
        return True

    def _sync_slot_equips(self) -> None:
        equips_by_id = {e["Id"]: e for e in self.state.get("equips", [])}
        for slot in self.state["slots"]:
            for key in ("Weapon", "Helmet", "Clothes", "Necklace"):
                if slot.get(key, {}).get("Id") in equips_by_id:
                    slot[key]["Lv"] = equips_by_id[slot[key]["Id"]]["Lv"]
        self._recalc_all_slots_and_fap()

    def _rpc_one_key_equip_lv_up(self, data: Any) -> dict[str, Any]:
        equip_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        equips_by_id = {e["Id"]: e for e in self.state.get("equips", [])}
        max_eq_lv = int(self.state["player"]["Lv"]) * 2
        updated: list[dict[str, Any]] = []
        for eid in equip_ids:
            eq = equips_by_id.get(str(eid))
            if not eq:
                continue
            upgraded = False
            while self._level_up_equip(eq, max_eq_lv):
                upgraded = True
            if upgraded or eq["Id"] in equips_by_id:
                updated.append(eq)
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
        node_idx = node_id % 10
        if ch_id == 11:
            base_lv = max(1, (node_idx + 1) // 2)
        else:
            base_lv = max(1, (ch_id - 11) * 4 + node_idx)

        pic = str(node_cfg.get("pic", "0"))
        is_final_wave = wave_idx == total_waves
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
        if ch_id >= 12 or node_idx >= 4:
            enemies[4] = self._hero_fight_obj(mob_cfg, lv=mob_lv, is_boss=False, hp_mult=diff_mult, ap_mult=diff_mult, def_mult=diff_mult)
        enemy_fap = sum(int(h["HP"] + h["AP"] * 5 + h["DEF"] * 5) for h in enemies if h)
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
            )
        return allies

    def _rpc_get_fight_info(self, data: Any) -> dict[str, Any]:
        node_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1111
        star_lv = int(data[2]) if isinstance(data, list) and len(data) >= 3 else 1
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
                        {"Fsp": 2000, "Fap": self.state["player"]["FAP"]},
                        {"Fsp": 1200, "Fap": enemy_fap},
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

        if self.profile_name == "normal" and won:
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
                next_ch_id = ch_id + 1
                if str(next_ch_id) in self.game_data["chapters"] and str(next_ch_id) not in self.state["chapters"]:
                    next_chapter = self._make_chapter_state(next_ch_id)
                    self.state["chapters"][str(next_ch_id)] = next_chapter
                    next_ch_nodes = sorted(
                        [int(k) for k, v in self.game_data["nodes"].items() if v.get("chapterModelID") == next_ch_id]
                    )
                    if next_ch_nodes:
                        self.state["nodes"][str(next_ch_nodes[0])] = self._make_node_state(next_ch_nodes[0], flag=1)
                        self.state["battle"]["MaxNodeId"] = max(self.state["battle"]["MaxNodeId"], next_ch_nodes[0])
                    self.state["battle"]["MaxChapterId"] = max(self.state["battle"]["MaxChapterId"], next_ch_id)

        reward_tuples: list[tuple[int, int, int]] = []
        if won:
            reward_tuples.append((1101, 0, exp_gain))
            reward_tuples.append((1112, 0, gold_gain))
            reward_tuples.append((1117, 0, hero_exp_gain))
            if self.profile_name == "normal":
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
        max_by_vit = available_vit // max(1, vit_cost) if self.profile_name == "normal" else count
        rem_count = max(0, int(node_cfg.get("fightNumMax", 10)) - int(node_st.get("FightCount", 0)))
        actual_count = min(count, max_by_vit, rem_count)
        if actual_count <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        token_gid = 16050011
        token_item = next((g for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == token_gid), None)
        owned_tokens = int(token_item.get("Num", 0)) if token_item else 0
        if consume_type == 3 and owned_tokens < actual_count and self.profile_name == "normal":
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
        node_st = self.state["nodes"].get(str(node_id))
        if not node_st:
            self._last_rpc_context["status"] = -1
            return {}
        node_st["FightCount"] = 0
        node_st["ResetFightCount"] = int(node_st.get("ResetFightCount", 0)) + 1
        node_st["ResetFightTime"] = int(time.time())
        self.save()
        return {"FightCount": 0, "ResetFightCount": node_st["ResetFightCount"]}

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
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return hero

    def _rpc_hero_step_up(self, data: Any) -> dict[str, Any]:
        hero_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        mat_ids = set(str(x) for x in (data[1] if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list) else []))
        hero = next((h for h in self.state["heroes"] if h["Id"] == hero_id), None)
        if not hero:
            self._last_rpc_context["status"] = -1
            return {}

        cfg = self.game_data["heroes"].get(str(hero["HeroModelId"]), {})
        step_cls = int(cfg.get("stepUpClassID", 0))
        cur_step = int(hero.get("Step", 0))
        step_row = self.game_data.get("hero_step", {}).get(str(step_cls * 1000 + cur_step))
        if not step_row or int(hero["Lv"]) < int(step_row.get("needLv", 1)):
            self._last_rpc_context["status"] = -1
            return {}

        reqs = _parse_resource_str(str(step_row.get("upUse", "")))
        for rtype, rmodel, rnum in reqs:
            if rtype == 1112 and int(self.state["player"]["Gold"]) < rnum:
                self._last_rpc_context["status"] = -1
                return {}
            elif rtype in (1401, 1402):
                continue  # Checked against submitted material entities if equips/treasures
            elif rtype >= 1500:
                g = next((x for x in self.state["goods"] if int(x["GoodsModelId"]) == rmodel), None)
                if not g or int(g["Num"]) < rnum:
                    self._last_rpc_context["status"] = -1
                    return {}

        for rtype, rmodel, rnum in reqs:
            if rtype == 1112 and rnum > 0:
                self.ledger.apply_player_delta(
                    self.state["player"], self.profile_name, "Gold", -rnum, source=f"hero_step_up:{hero['HeroModelId']}"
                )
            elif rtype >= 1500 and rnum > 0:
                for g in self.state["goods"]:
                    if int(g["GoodsModelId"]) == rmodel:
                        g["Num"] = max(0, int(g["Num"]) - rnum)
                        break

        if mat_ids:
            self.state["heroes"] = [h for h in self.state["heroes"] if h["Id"] not in mat_ids]
            self.state["equips"] = [e for e in self.state["equips"] if e["Id"] not in mat_ids]

        hero["Step"] = cur_step + 1
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return hero

    def _explore_payload(self) -> dict[str, Any]:
        exp_st = self.state.setdefault("explore", self._default_explore_state())
        return {
            "RecoverTime": int(exp_st.get("RecoverTime", int(time.time()) + 900)),
            "ResetNum": int(exp_st.get("ResetNum", 0)),
            "MaxResetNum": int(exp_st.get("MaxResetNum", 5)),
            "RemainNum": int(exp_st.get("RemainNum", 15)),
            "MaxNum": int(exp_st.get("MaxNum", 25)),
            "DailyNum": int(exp_st.get("DailyNum", 0)),
            "DrawnNums": str(exp_st.get("DrawnNums", "")),
        }

    def _rpc_explore_get_info(self, _data: Any) -> dict[str, Any]:
        return self._explore_payload()

    def _do_explore_once(self) -> tuple[int, int, list[tuple[int, int, int]]]:
        exp_st = self.state.setdefault("explore", self._default_explore_state())
        exp_st["RemainNum"] = int(exp_st.get("RemainNum", 0)) - 1
        exp_st["DailyNum"] = int(exp_st.get("DailyNum", 0)) + 1
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
        exp_st = self.state.setdefault("explore", self._default_explore_state())
        if int(exp_st.get("RemainNum", 0)) <= 0:
            self._last_rpc_context["status"] = -1
            return {}
        reward_id, drop_text_id, tuples = self._do_explore_once()
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="explore",
            tx_prefix=f"explore:{self.profile_name}:{uuid.uuid4()}",
        )
        old_lv, new_lv = self._sync_level_from_exp()
        if new_lv != old_lv:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True
        self.save()
        out = self._explore_payload()
        out.update({"RewardModelId": reward_id, "DropTextId": drop_text_id, "BaseGetGameResourceList": base_res})
        return out

    def _rpc_explore_one_key(self, _data: Any) -> dict[str, Any]:
        exp_st = self.state.setdefault("explore", self._default_explore_state())
        rem = int(exp_st.get("RemainNum", 0))
        if rem <= 0:
            self._last_rpc_context["status"] = -1
            return {}
        count = min(rem, 10)
        totals: dict[tuple[int, int], int] = {}
        last_rid = 1
        last_did = 3
        for _ in range(count):
            last_rid, last_did, ts = self._do_explore_once()
            for rtype, rmodel, rnum in ts:
                totals[(rtype, rmodel)] = totals.get((rtype, rmodel), 0) + rnum
        merged = [(k[0], k[1], v) for k, v in totals.items() if v > 0]
        base_res = self._grant_resources_from_tuples(
            merged,
            source="explore_one_key",
            tx_prefix=f"explore1k:{self.profile_name}:{uuid.uuid4()}",
        )
        old_lv, new_lv = self._sync_level_from_exp()
        if new_lv != old_lv:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True
        self.save()
        out = self._explore_payload()
        out.update({"RewardModelId": last_rid, "DropTextId": last_did, "BaseGetGameResourceList": base_res})
        return out

    def _rpc_explore_buy(self, _data: Any) -> dict[str, Any]:
        exp_st = self.state.setdefault("explore", self._default_explore_state())
        if int(exp_st.get("ResetNum", 0)) >= int(exp_st.get("MaxResetNum", 5)) or int(self.state["player"]["Diamond"]) < 20:
            self._last_rpc_context["status"] = -1
            return {}
        self.ledger.apply_player_delta(self.state["player"], self.profile_name, "Diamond", -20, source="explore_buy")
        exp_st["ResetNum"] = int(exp_st.get("ResetNum", 0)) + 1
        exp_st["RemainNum"] = int(exp_st.get("RemainNum", 0)) + 5
        self.save()
        return self._explore_payload()

    def _rpc_explore_draw_daily(self, data: Any) -> dict[str, Any]:
        num = int(data[0]) if isinstance(data, list) and data else 50
        exp_st = self.state.setdefault("explore", self._default_explore_state())
        drawn = [x for x in str(exp_st.get("DrawnNums", "")).split(",") if x]
        row = self.game_data.get("explore_reward_nums", {}).get(str(num))
        if not row or int(exp_st.get("DailyNum", 0)) < num or str(num) in drawn:
            self._last_rpc_context["status"] = -1
            return {}
        drawn.append(str(num))
        exp_st["DrawnNums"] = ",".join(drawn)
        base_res = self._grant_resources_from_tuples(
            _parse_resource_str(str(row.get("rewards", ""))),
            source=f"explore_daily:{num}",
            tx_prefix=f"explore_daily:{self.profile_name}:{self.state['player']['PlayerId']}:{num}",
        )
        self.save()
        out = self._explore_payload()
        out["BaseGetGameResourceList"] = base_res
        return out

    def _lighten_star_payload(self) -> dict[str, Any]:
        add_info: list[dict[str, Any]] = []
        for slot_id in range(1, 7):
            bonuses = self._get_slot_star_bonuses(slot_id)
            if bonuses["AP"] > 0:
                add_info.append({"SlotId": slot_id, "FightAttr": 431, "AddValue": bonuses["AP"]})
            if bonuses["HP"] > 0:
                add_info.append({"SlotId": slot_id, "FightAttr": 432, "AddValue": bonuses["HP"]})
            if bonuses["DEF"] > 0:
                add_info.append({"SlotId": slot_id, "FightAttr": 433, "AddValue": bonuses["DEF"]})
        return {
            "StarId": int(self.state["player"].get("StarId", 0)),
            "StarCount": int(self.state["battle"].get("StarCount", 0)),
            "AddValueInfo": add_info,
        }

    def _rpc_lighten_star_info(self, _data: Any) -> dict[str, Any]:
        return self._lighten_star_payload()

    def _step_lighten_star_once(self) -> bool:
        cur_id = int(self.state["player"].get("StarId", 0))
        tree = self.game_data.get("attrtree", {})
        nxt = tree.get(str(cur_id + 1))
        if not nxt:
            return False
        need_lv = int(nxt.get("needLV", 1))
        need_star = int(nxt.get("needStar", 3))
        need_gold = int(nxt.get("needGold", 1500))
        used_stars = sum(int(tree.get(str(i), {}).get("needStar", 0)) for i in range(1, cur_id + 1))
        avail_stars = int(self.state["battle"].get("StarCount", 0)) - used_stars
        if int(self.state["player"]["Lv"]) < need_lv or avail_stars < need_star or int(self.state["player"]["Gold"]) < need_gold:
            return False
        self.ledger.apply_player_delta(self.state["player"], self.profile_name, "Gold", -need_gold, source=f"lighten_star:{cur_id + 1}")
        self.state["player"]["StarId"] = cur_id + 1
        xunyu_add = int(nxt.get("xunyuAddNum", 0))
        if xunyu_add > 0:
            exp_st = self.state.setdefault("explore", self._default_explore_state())
            exp_st["MaxNum"] = int(exp_st.get("MaxNum", 25)) + xunyu_add
            exp_st["RemainNum"] = int(exp_st.get("RemainNum", 0)) + xunyu_add
        return True

    def _rpc_lighten_star_up(self, _data: Any) -> dict[str, Any]:
        if not self._step_lighten_star_once():
            self._last_rpc_context["status"] = -1
            return {}
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return self._lighten_star_payload()

    def _rpc_lighten_star_one_key(self, _data: Any) -> dict[str, Any]:
        progressed = 0
        while progressed < 50 and self._step_lighten_star_once():
            progressed += 1
        if progressed == 0:
            self._last_rpc_context["status"] = -1
            return {}
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return self._lighten_star_payload()

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

        bought = int(self.state.setdefault("shop_bought", {}).get(str(goods_model_id), 0))
        curr_price = self._shop_goods_price_for_step(goods_model_id, bought + 1, init_price) if if_dyn else init_price

        if not if_vip_limit:
            max_num = -1
        else:
            vip_lv = str(int(self.state["player"].get("Vip", 0)))
            vip_tbl = self.game_data.get("vip_buy_limit", {}).get(vip_lv, {})
            max_num = int(vip_tbl.get(str(goods_model_id), {}).get("buyMaxNum", 6))

        return {
            "GoodsModelId": goods_model_id,
            "SellTypeId": sell_type_id,
            "CurrPrice": curr_price,
            "Num": bought,
            "MaxNum": max_num,
        }

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

    def _rpc_shop_buy_goods(self, data: Any) -> dict[str, Any]:
        gid = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 16030006
        count = max(1, int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1)
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
        self.state.setdefault("shop_bought", {})[str(gid)] = info["Num"] + count
        self._grant_resources_from_tuples(
            [(gid // 10000, gid, count)],
            source=f"shop_buy:{gid}",
            tx_prefix=f"shop_buy:{self.profile_name}:{gid}:{uuid.uuid4()}",
        )
        self._mark_goods_changed(gid)
        self.save()
        return self._build_shop_goods_entry(gid)

    def _rpc_goods_use(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        entity_id = str(data[0])
        gid = int(data[1])
        count = max(1, int(data[2]) if len(data) >= 3 else 1)

        item = next(
            (g for g in self.state.get("goods", []) if g["Id"] == entity_id or int(g["GoodsModelId"]) == gid),
            None,
        )
        if not item or int(item.get("Num", 0)) < count:
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
            for _ in range(count):
                max_roll = max((int(r.get("oddsMax", 0)) for r in pool_rows), default=0)
                if max_roll > 0:
                    roll = random.randint(1, max_roll)
                    chosen = next(
                        (r for r in pool_rows if int(r.get("oddsMin", 0)) <= roll <= int(r.get("oddsMax", 0))),
                        pool_rows[0],
                    )
                else:
                    chosen = random.choice(pool_rows)
                tuples.append(
                    (
                        int(chosen.get("outputTypeID", 0)),
                        int(chosen.get("outputModelID", 0)),
                        max(1, int(chosen.get("outputNum", 1))),
                    )
                )
        elif out_type > 0 and out_num > 0:
            tuples.append((out_type, out_model, out_num * count))

        item["Num"] = int(item["Num"]) - consume
        if item["Num"] <= 0:
            self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != item["Id"]]

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"goods_use:{gid}",
            tx_prefix=f"goods_use:{self.profile_name}:{gid}:{uuid.uuid4()}",
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
        enemy_fap = sum(int(h["HP"] + h["AP"] * 5 + h["DEF"] * 5) for h in enemies if h)

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
            base_res = self._grant_resources_from_tuples(
                [(1101, 0, exp_gain), (1112, 0, gold_gain), (1117, 0, hero_exp_gain)],
                source=f"elite_victory:{elite_id}",
                tx_prefix=f"elite:{self.profile_name}:{elite_id}:{uuid.uuid4()}",
            )
            old_lv2, new_lv2 = self._sync_level_from_exp()
            if new_lv2 != old_lv2:
                self._last_rpc_context["lv_changed"] = True
                self._last_rpc_context["slots_changed"] = True

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
    def _rpc_lv_plan_info(self, _data: Any) -> dict[str, Any]:
        lp = self.state.setdefault("lv_plan", {"open": False, "rewarded": []})
        rewarded = [int(x) for x in lp.get("rewarded", [])]
        player_lv = int(self.state["player"].get("Lv", 1))
        player_vip = int(self.state["player"].get("Vip", 0))
        can_list: list[int] = []
        if player_vip >= LV_PLAN_NEED_VIP:
            for tier_lv in sorted(LV_PLAN_REWARDS):
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
        reward_diamond = LV_PLAN_REWARDS.get(tier_lv)
        p = self.state["player"]
        lp = self.state.setdefault("lv_plan", {"open": False, "rewarded": []})
        rewarded = [int(x) for x in lp.get("rewarded", [])]
        if (
            reward_diamond is None
            or int(p.get("Vip", 0)) < LV_PLAN_NEED_VIP
            or int(p.get("Lv", 1)) < tier_lv
            or tier_lv in rewarded
            or int(p.get("Diamond", 0)) < LV_PLAN_NEED_DIAMOND
        ):
            self._last_rpc_context["status"] = -1
            return {}
        self.ledger.apply_player_delta(
            p,
            self.profile_name,
            "Diamond",
            -LV_PLAN_NEED_DIAMOND,
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
        raw = VIP_WELFARE_REWARDS.get(vip, VIP_WELFARE_REWARDS[0])
        return _parse_resource_str(raw)

    def _rpc_vip_welfare_info(self, _data: Any) -> dict[str, Any]:
        today = time.strftime("%Y-%m-%d")
        can_draw = self.state.get("vip_welfare_drawn_date", "") != today
        res_list = [
            {"ResourceTypeSub": rtype, "ModelId": rmodel, "Count": rnum}
            for rtype, rmodel, rnum in self._vip_welfare_tuples()
        ]
        return {"CanDraw": can_draw, "ResourceList": res_list}

    def _rpc_vip_welfare_draw(self, _data: Any) -> dict[str, Any]:
        today = time.strftime("%Y-%m-%d")
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

    def _rpc_player_charge_generate_order(self, data: Any) -> str:
        pid = str(data[0]) if isinstance(data, list) and data else CHARGE_TIERS[0]["ProductId"]
        order_id = f"ORD-{uuid.uuid4().hex[:16]}"
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}})
        cs.setdefault("orders", {})[order_id] = {"ProductId": pid, "ts": int(time.time())}
        self.save()
        return order_id

    def _apply_simulated_charge(
        self,
        tier: dict[str, Any],
        actor: str = "player",
        source: str = "simulated_charge",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        p = self.state["player"]
        cs = self.state.setdefault("charge_state", {"first_bought": [], "drawn_boxes": [], "orders": {}})
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
        if is_first:
            bought.append(pid)
        self.save()
        return {
            "ProductId": pid,
            "DiamondAdded": total_diamonds,
            "VipEXPAdded": base_diamonds,
            "Vip": int(p.get("Vip", 0)),
            "Diamond": int(p.get("Diamond", 0)),
            "ChargeNum": int(p["ChargeNum"]),
        }

    def _rpc_player_charge_confirm_order(self, data: Any) -> dict[str, Any]:
        arg = data[0] if isinstance(data, list) and data else CHARGE_TIERS[0]["ChargePoint"]
        tier = next(
            (
                t
                for t in CHARGE_TIERS
                if str(t["ProductId"]) == str(arg) or str(t["ChargePoint"]) == str(arg)
            ),
            None,
        )
        if tier is None:
            try:
                pts = int(arg)
                tier = {
                    "ProductId": f"com.cmn.inuyasha.custom{pts}",
                    "ChargePoint": pts,
                    "GamePoint": pts,
                    "GiveGamePoint": 0,
                    "Ratio": 1,
                }
            except (TypeError, ValueError):
                self._last_rpc_context["status"] = -1
                return {}
        return self._apply_simulated_charge(tier, actor="player", source="simulated_charge_rpc")

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
        cfg = CARD_MODEL_CFG.get(cid, CARD_MODEL_CFG[1])
        return {"ProductId": cfg["ProductId"], "OrderId": f"CARDORD-{uuid.uuid4().hex[:14]}"}

    def _rpc_card_activity(self, data: Any) -> list[dict[str, Any]]:
        cid = int(data[0]) if isinstance(data, list) and data else 1
        cfg = CARD_MODEL_CFG.get(cid)
        if not cfg:
            self._last_rpc_context["status"] = -1
            return []
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
            idempotency_key=f"cardact:{self.profile_name}:{p['PlayerId']}:{cid}:{uuid.uuid4()}",
        )
        p["ChargeNum"] = int(p.get("ChargeNum", 0)) + int(cfg["price"])
        self.save()
        return self._card_list_payload()

    def _rpc_card_draw_daily(self, data: Any) -> dict[str, Any]:
        cid = int(data[0]) if isinstance(data, list) and data else 1
        cfg = CARD_MODEL_CFG.get(cid)
        now = int(time.time())
        today = time.strftime("%Y-%m-%d")
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
        """Compute module red-dot flags (including StartWork 2718 on Mon-Thu until claimed)."""
        lv = int(self.state.get("player", {}).get("Lv", 1))
        now = int(time.time())
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
        today = time.strftime("%Y-%m-%d")
        is_workday_window = time.localtime().tm_wday in (0, 1, 2, 3)
        claimed_days = self.state.get("startwork", {}).get("claimed_days", [])
        can_startwork = is_workday_window and (today not in claimed_days)
        return {
            "2203": 1 if (lv >= 18 and alive_boss) else 0,
            "2205": 1 if (lv >= 18 and claimable_box) else 0,
            "2710": 1 if can_fund else 0,
            "2718": 1 if can_startwork else 0,
        }

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
                        {"Fsp": enemy_fsp, "Fap": int(boss_unit["TotalHp"] + boss_unit["AP"] * 5)},
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
            outcome = simulate_fight_info(fight_info, self.game_data["attacks"])
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
                    bot = self._arena_bot_profile(r, st)
                    return {
                        "PlayerInfo": {
                            "PlayerId": bot["PlayerId"],
                            "Name": bot["Name"],
                            "Lv": bot["Lv"],
                            "StarId": 0,
                            "FashionModelId": 0,
                            "FAP": bot["FAP"],
                        },
                        "SlotInfo": bot["Slots"],
                        "SlotInfos": bot["Slots"],
                        "MateInfos": [],
                        "SlotFormationInfo": bot["Embattle"],
                        "SkillInfos": [],
                        "CombatPet": None,
                    }
        return None

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
        ranks = self._candidate_arena_ranks(player_rank, refresh_seed)
        out: list[dict[str, Any]] = []
        for r in ranks:
            if r == player_rank:
                out.append(self._self_arena_entry(r))
            else:
                bot = self._arena_bot_profile(r, step)
                allow = 1 if (r < player_rank and (r >= 4 or player_rank <= 20)) else 0
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
        today = time.strftime("%Y-%m-%d")
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
        bot = self._arena_bot_profile(target_rank, step)
        if bot["PlayerId"] != target_id:
            # Resolve matching bot rank if client sent slightly stale rank
            for probe in self._candidate_arena_ranks(int(pvp.get("rank", 1500)), int(pvp.get("refresh_seed", 1))):
                cand = self._arena_bot_profile(probe, step)
                if cand["PlayerId"] == target_id:
                    bot = cand
                    target_rank = probe
                    break

        allies = self._build_ally_fight_objs()
        enemies = self._arena_bot_fight_objs(bot)
        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        enemy_fsp = sum(int(u.get("FSP", 0)) for u in enemies if u)
        fight_info = {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": ally_fsp, "Fap": int(p.get("FAP", 0))},
                        {"Fsp": enemy_fsp, "Fap": int(bot["FAP"])},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1, 999999),
                    "IsPVP": True,
                }
            ]
        }

        self.ledger.apply_player_delta(p, self.profile_name, "STA", -sta_cost, source=f"pvp_sta:{target_rank}")
        outcome = simulate_fight_info(fight_info, self.game_data["attacks"])
        is_win = 1 if outcome.won else 0

        old_rank = int(pvp.get("rank", 1500))
        old_max_rank = int(pvp.get("history_max_rank", old_rank))
        new_rank = min(old_rank, target_rank) if is_win else old_rank
        pvp["rank"] = new_rank

        breakthrough_diamond = 0
        if is_win and new_rank < old_max_rank:
            breakthrough_diamond = self._calc_upgrade_rank_diamonds(old_max_rank, step, new_rank)
            pvp["history_max_rank"] = new_rank
        if step > int(pvp.get("history_max_step", 1)):
            pvp["history_max_step"] = step

        per_exp_pct = int(self.game_data.get("sta_config", {}).get("perGetEXPR", 20000))
        exp_gain = int(sta_cost * lv * (per_exp_pct / 10000.0))
        pvp_coin_gain = (40 + max(0, (1600 - target_rank) // 100)) if is_win else 15
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
                "TargetPlayerId": bot["PlayerId"],
                "TargetName": bot["Name"],
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

        today = time.strftime("%Y-%m-%d")
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
        today = time.strftime("%Y-%m-%d")
        claimed = sw.setdefault("claimed_days", [])
        if today in claimed:
            self._last_rpc_context["status"] = -1
            return {}
        wday = time.localtime().tm_wday + 1  # 1=Mon .. 4=Thu
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
        self.ledger = ResourceLedger(
            audit_log_path=resolved_audit if persist else None,
            vip_model=self.game_data.get("vip_model", {}),
        )
        self.profiles: dict[str, ProfileStore] = {
            "normal": ProfileStore(
                "normal",
                self.game_data,
                self.ledger,
                state_path=resolved_normal,
                persist=persist,
                reset=new_player,
                trace_path=self.trace_path if persist else None,
            ),
            "debug": ProfileStore(
                "debug",
                self.game_data,
                self.ledger,
                state_path=resolved_debug,
                persist=persist,
                reset=False,
                legacy_seed_path=LEGACY_SAVE_STATE_PATH if self.env == "stable" else None,
                trace_path=self.trace_path if persist else None,
            ),
        }

    def get_profile_by_name(self, name: str) -> ProfileStore:
        if name not in self.profiles:
            raise ValueError(f"Unknown profile: {name}")
        return self.profiles[name]

    @property
    def state(self) -> dict[str, Any]:
        """Expose active default profile state for backward-compatible callers/tests."""
        return self.profiles[self.default_profile].state

    def get_profile(self, server_id: Any = None) -> ProfileStore:
        if server_id is not None:
            try:
                sid = int(server_id)
                if sid == 2:
                    return self.profiles["debug"]
                if sid == 1:
                    return self.profiles["normal"]
            except (TypeError, ValueError):
                pass
        return self.profiles[self.default_profile]

    def handle_rpc(self, req: dict[str, Any]) -> dict[str, Any]:
        profile = self.get_profile(req.get("ServerId"))
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
                self._send_json(404, {"error": f"Unknown admin endpoint: {path}"})
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._send_json(400, {"error": str(exc)})
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
            self._send_client_json(
                200,
                {
                    "Code": 0,
                    "Data": {
                        "Server": [
                            {
                                "ServerID": 1,
                                "ServerName": "S1 Normal Revival (Lv1)",
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
                            "UserID": "100001",
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
