#!/usr/bin/env python3
"""
InuYasha: Seek Jade (com.heitao.inuyasha.guge v5.1.1) Local Server Emulator.

Round R2:
  - Separates NORMAL_PROFILE (ServerId=1, authentic Lv1/VIP0/new-player tutorial & progression)
    from DEBUG_PROFILE (ServerId=2, preserves R1 Lv10/VIP5 quick-test save).
  - Restores forced tutorial (GuideRelation[1] steps 1..38) and level-triggered guides,
    persisting ExtensionString.GuideInfo + Player.AlterPlayerStepCount + Player.GetStepCountReward.
  - Implements tutorial-required RPCs: HeroRecruit.Recruit, Slot.HeroCombat,
    Slot.OneKeyEquipCombat, SlotFormation.GetFormation/Change, Equip.EquipCompose,
    Equip.EquipOneKeyCompose, Equip.OneKeyEquipLvUp, Equip.EquipLvUpForCount,
    Battle.DrawRoadBox, Battle.DrawBox.
  - Drives progression, drops, EXP, and stats from extracted EN 5.1.1 Config tables
    and records all currency/resource mutations via ResourceLedger.
"""

from __future__ import annotations

import argparse
import copy
import http.server
import json
import mimetypes
import os
import random
import re
import socketserver
import time
import urllib.parse
import uuid
import zipfile
import zlib
from pathlib import Path
from typing import Any

from economy_audit import ResourceLedger

ROOT_DIR = Path(__file__).resolve().parent.parent
SERVER_DIR = Path(__file__).resolve().parent
POC_DIR = ROOT_DIR / "poc" / "web_poc"
GAME_DATA_PATH = SERVER_DIR / "game_data.json"
LEGACY_SAVE_STATE_PATH = SERVER_DIR / "save_state.json"
SAVES_DIR = SERVER_DIR / "saves"
NORMAL_STATE_PATH = SAVES_DIR / "normal_profile.json"
DEBUG_STATE_PATH = SAVES_DIR / "debug_profile.json"
AUDIT_LOG_PATH = SAVES_DIR / "audit_ledger.jsonl"
RPC_TRACE_PATH = SERVER_DIR / "rpc_trace.log"

EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"

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
    """Lazy read-only lookup across EN 5.1.1 APK (assets/) and OBB."""

    def __init__(self, apk_path: Path, obb_path: Path) -> None:
        self._apk = zipfile.ZipFile(apk_path, "r") if apk_path.exists() else None
        self._obb = zipfile.ZipFile(obb_path, "r") if obb_path.exists() else None
        self._apk_names = set(self._apk.namelist()) if self._apk else set()
        self._obb_names = set(self._obb.namelist()) if self._obb else set()

    def read(self, rel_path: str) -> bytes | None:
        clean = rel_path.lstrip("/")
        if clean in self._obb_names and self._obb:
            return self._obb.read(clean)
        apk_key = f"assets/{clean}"
        if apk_key in self._apk_names and self._apk:
            return self._apk.read(apk_key)
        if clean in self._apk_names and self._apk:
            return self._apk.read(clean)
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
    ) -> None:
        self.profile_name = profile_name  # "normal" or "debug"
        self.game_data = game_data
        self.ledger = ledger
        self.state_path = state_path
        self.persist = persist
        self.legacy_seed_path = legacy_seed_path
        self.state = self._load_or_init(reset=reset)

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
                self.state_path.parent.mkdir(parents=True, exist_ok=True)
                self.state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
        if self.profile_name == "debug":
            state = self._create_debug_default_state()
        else:
            next_pid = "200001"
            if reset and prev_player_id and prev_player_id.isdigit():
                next_pid = str(max(200001, int(prev_player_id) + 1))
            state = self._create_normal_default_state(player_id=next_pid)
        if self.persist and self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def _normalize_loaded_state(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure loaded states have required fields without altering saved progress."""
        data.setdefault("equips", [])
        data.setdefault("goods", [])
        data.setdefault("claimed_step_rewards", [])
        data.setdefault("recruit_state", {"MidAlreadyUseResource": False, "HigAlreadyUseResource": False, "OutZiCount": 5})
        for h in data.get("heroes", []):
            h.setdefault("WarfareColorLv", 0)
            h.setdefault("WarfareLv", 0)
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

    def reset_state(self) -> dict[str, Any]:
        """Reset normal profile with a fresh PlayerId so Android LocalData guide cache starts clean."""
        prev_id = str(self.state.get("player", {}).get("PlayerId", "200001"))
        try:
            next_num = max(200001, int(prev_id) + 1)
        except ValueError:
            next_num = 200001
        self.state = self._create_normal_default_state(player_id=str(next_num))
        self.save()
        return self.state

    def save(self) -> None:
        if self.persist and self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def _compute_slot_property(self, slot: dict[str, Any], heroes_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
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

        hp1 = hero_hp + eq_hp + set_hp
        ap1 = hero_ap + eq_ap + set_ap
        def1 = hero_def + eq_def + set_def
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

    def _recalc_all_slots_and_fap(self) -> None:
        heroes_by_id = {h["Id"]: h for h in self.state["heroes"]}
        total_fap = 0
        for slot in self.state["slots"]:
            slot["Property"] = self._compute_slot_property(slot, heroes_by_id)
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

        return {
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
                "LastLoginTime": now,
                "StepCountList": {},
            },
            "heroes": [main_hero],
            "slots": slots,
            "embattle": {f"Formation{i}": i for i in range(1, 7)},
            "equips": [],
            "goods": init_goods,
            "claimed_step_rewards": [],
            "recruit_state": {
                "MidAlreadyUseResource": False,
                "HigAlreadyUseResource": False,
                "OutZiCount": 5,
            },
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
        }

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

        return {
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
                "Gold": 50000,
                "Diamond": 8888,
                "VIT": 120,
                "VITMaxNum": 200,
                "STA": 40,
                "STAMaxNum": 40,
                "HeroCoin": 1200,
                "HeroEXP": 15000,
                "FAP": 18500,
                "StarId": 0,
                "HeadImageId": 12011004,
                "AppErrorLevel": 0,
                "IsNewPlayer": 0,
                "LastLoginTime": int(time.time()),
                "StepCountList": {"1": 999},
            },
            "heroes": hero_instances,
            "slots": slot_infos,
            "embattle": {"Formation1": 1, "Formation2": 2, "Formation3": 3, "Formation4": 4, "Formation5": 0, "Formation6": 0},
            "equips": [],
            "goods": [],
            "claimed_step_rewards": [],
            "recruit_state": {"MidAlreadyUseResource": False, "HigAlreadyUseResource": False, "OutZiCount": 5},
            "battle": {
                "MaxChapterId": 11,
                "MaxNodeId": ch11_nodes[0]["ID"] if ch11_nodes else 1111,
                "StarCount": 0,
                "HasBoss": "False",
                "BossId": 0,
            },
            "chapters": {"11": self._make_chapter_state(11)},
            "nodes": node_states,
        }

    @staticmethod
    def _make_chapter_state(ch_id: int) -> dict[str, Any]:
        return {
            "ChapterModelId": ch_id,
            "StarCount": 0,
            "IfPass": 0,
            "IfDrawBoxA": 0,
            "IfDrawBoxB": 0,
            "IfDrawBoxC": 0,
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

    def _grant_resources_from_tuples(
        self,
        res_tuples: list[tuple[int, int, int]],
        source: str,
        tx_prefix: str,
    ) -> list[dict[str, Any]]:
        """Apply a list of (typeID, modelID, num) drops and build BaseGetGameResourceList payload."""
        player_attrs: list[dict[str, Any]] = []
        new_heroes: list[dict[str, Any]] = []
        new_equips: list[dict[str, Any]] = []
        new_goods: list[dict[str, Any]] = []

        attr_map = {
            1101: "EXP",
            1102: "VIT",
            1103: "STA",
            1111: "Diamond",
            1112: "Gold",
            1116: "HeroCoin",
            1117: "HeroEXP",
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
            else:
                existing = next((g for g in self.state["goods"] if g["GoodsModelId"] == rmodel), None)
                if existing:
                    existing["Num"] += rnum
                    goods_obj = dict(existing)
                else:
                    goods_obj = {
                        "Id": str(uuid.uuid4()),
                        "GoodsModelId": rmodel,
                        "Num": rnum,
                        "Crdate": int(time.time()),
                        "LastTime": 0,
                        "BeginTime": 0,
                        "EndTime": 0,
                    }
                    self.state["goods"].append(goods_obj)
                new_goods.append(goods_obj)
                self.ledger.record_grant_event(
                    account_id=str(self.state["player"]["PlayerId"]),
                    profile=self.profile_name,
                    resource_type=f"Goods:{rmodel}",
                    amount=rnum,
                    balance_after=goods_obj["Num"],
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
        if new_goods:
            bundle["Goods"] = new_goods
        return [bundle] if bundle else []

    def _sync_level_from_exp(self) -> tuple[int, int]:
        """Recompute player Lv from PlayerLvRelation EXPTotal and sync MainHero Lv."""
        old_lv = int(self.state["player"]["Lv"])
        exp = int(self.state["player"]["EXP"])
        max_lv = int(self.game_data["player_config"].get("maxPlayerLV", 70))
        new_lv = old_lv
        for lv_str, row in self.game_data.get("player_lv", {}).items():
            lv_val = int(lv_str)
            if lv_val <= max_lv and exp >= int(row.get("EXPTotal", 0)) and lv_val > new_lv:
                new_lv = lv_val

        if new_lv != old_lv:
            self.state["player"]["Lv"] = new_lv
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
        override_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if override_stats:
            hp = int(override_stats["HP"] * hp_mult)
            ap = int(override_stats["AP"] * ap_mult)
            defense = int(override_stats["DEF"])
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
            hp = int((cfg["HPBase"] + cfg["HPUp"] * (lv - 1)) * hp_mult)
            ap = int((cfg["APBase"] + cfg["APUp"] * (lv - 1)) * ap_mult)
            defense = int(cfg["DEFBase"] + cfg["DEFUp"] * (lv - 1))
            rp = int(cfg.get("RP", 50))
            fsp = int(cfg.get("FSP", 500))
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
            "Step": 0 if self.profile_name == "normal" else 1,
            "RebornStep": 0,
            "LargePic": cfg["largePic"],
            "SmallPic": cfg["smallPic"],
            "SkillSound": cfg.get("skillSound", "0"),
        }

    def handle_rpc(self, req: dict[str, Any]) -> dict[str, Any]:
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
            "Battle.GetFightInfo": self._rpc_get_fight_info,
            "Battle.Fight": self._rpc_battle_fight,
            "Battle.DrawRoadBox": self._rpc_draw_road_box,
            "Battle.DrawBox": self._rpc_draw_box,
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

        if self.persist:
            with open(RPC_TRACE_PATH, "a", encoding="utf-8") as tf:
                tf.write(
                    f"{time.strftime('%H:%M:%S')} [{self.profile_name}] RPC {key} "
                    f"handled={handled} status={status} data={json.dumps(data, ensure_ascii=False)}\n"
                )

        if key in {"Player.Login", "Player.Login_ForTest", "Player.NewPlayer"}:
            avatar: dict[str, Any] = {}
        elif key == "Player.GetInitData":
            avatar = {"TimedActivityOpenInfo": {}}
        else:
            avatar = {k: v for k, v in self.state["player"].items() if k != "Lv"}
            if self._last_rpc_context.get("lv_changed"):
                avatar["Lv"] = self.state["player"]["Lv"]
            if self._last_rpc_context.get("slots_changed"):
                avatar["SlotInfo"] = self.state["slots"]
            avatar["TimedActivityOpenInfo"] = {}

        return {
            "Status": status,
            "TimeTick": int(time.time()),
            "Avatar": avatar,
            "Value": value,
        }

    def _rpc_login(self, _data: Any) -> dict[str, Any]:
        self.state["player"]["LastLoginTime"] = int(time.time())
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
        return {
            "PlayerInfo": self.state["player"],
            "HeroInfo": self.state["heroes"],
            "EquipInfo": self.state.get("equips", []),
            "TreasureInfo": [],
            "SlotInfo": self.state["slots"],
            "MateInfo": [],
            "SlotFormationInfo": self.state["embattle"],
            "GoodsHeroDebrisInfo": [],
            "GoodsEquipDebrisInfo": [],
            "GoodsPropsInfo": self.state.get("goods", []),
            "TreasureDebrisInfo": [],
            "BagInfo": [{"BagModelId": bid, "Size": 200, "ExpandNum": 0} for bid in range(1, 10)],
            "SkillList": [],
            "ModulesInfo": modules,
            "StarSignInfo": [],
            "XYCurCount": 0,
            "FashionInfo": [],
            "GemInfo": [],
            "PetInfo": [],
        }

    def _rpc_sync_avatar(self, _data: Any) -> dict[str, Any]:
        return dict(self.state["player"])

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

        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotInfo": self.state["slots"]}

    def _rpc_slot_formations(self, _data: Any) -> dict[str, Any]:
        return {"SlotInfo": self.state["slots"], "SlotFormationInfo": self.state["embattle"]}

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

    def _rpc_get_fight_info(self, data: Any) -> dict[str, Any]:
        node_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1111
        node_cfg = self.game_data["nodes"].get(str(node_id), {"ID": node_id, "name": "1-1"})
        heroes_cfg = self.game_data["heroes"]

        heros_arr: list[dict[str, Any]] = [{} for _ in range(12)]

        if self.profile_name == "debug":
            # Keep R1 debug behavior for quick-testing in DEBUG_PROFILE
            for idx, inst in enumerate(self.state["heroes"][:6]):
                cfg = heroes_cfg[str(inst["HeroModelId"])]
                heros_arr[idx] = self._hero_fight_obj(cfg, lv=max(20, inst["Lv"]), is_boss=False, hp_mult=2.5, ap_mult=2.5)
            boss_id = "12011022" if str(node_id).endswith("5") else "12013005"
            heros_arr[7] = self._hero_fight_obj(heroes_cfg[boss_id], lv=1, is_boss=True, hp_mult=0.35, ap_mult=1.15)
            heros_arr[6] = self._hero_fight_obj(heroes_cfg["12011022"], lv=1, is_boss=False, hp_mult=0.25)
            heros_arr[8] = self._hero_fight_obj(heroes_cfg["12010053"], lv=1, is_boss=False, hp_mult=0.25)
            enemy_fap = 9500
        else:
            # Authentic NORMAL_PROFILE allies from deployed slots + embattle
            slots_by_id = {int(s["SlotId"]): s for s in self.state["slots"]}
            emb = self.state.get("embattle", {})
            placed = False
            for f_idx in range(1, 7):
                slot_id = int(emb.get(f"Formation{f_idx}", f_idx))
                slot = slots_by_id.get(slot_id)
                if slot and slot.get("HeroId") and slot["HeroId"] != EMPTY_ENTITY_ID:
                    cfg = heroes_cfg[str(slot["HeroModelId"])]
                    heros_arr[f_idx - 1] = self._hero_fight_obj(cfg, is_boss=False, override_stats=slot["Property"])
                    placed = True
            if not placed and self.state["heroes"]:
                inst = self.state["heroes"][0]
                cfg = heroes_cfg[str(inst["HeroModelId"])]
                heros_arr[0] = self._hero_fight_obj(cfg, lv=inst["Lv"], is_boss=False)

            # Enemies: use BattleNodeModel.pic boss if specified, plus Chapter 1/2 low-tier mobs
            pic = str(node_cfg.get("pic", "0"))
            ch_id = int(node_cfg.get("chapterModelID", 11))
            mob_lv = max(1, (ch_id - 11) * 3 + (node_id % 10))
            if pic != "0" and pic in heroes_cfg:
                heros_arr[7] = self._hero_fight_obj(heroes_cfg[pic], lv=mob_lv, is_boss=True)
            else:
                heros_arr[7] = self._hero_fight_obj(heroes_cfg["12013043"], lv=mob_lv, is_boss=False)
            heros_arr[6] = self._hero_fight_obj(heroes_cfg["12012045"], lv=1, is_boss=False)
            heros_arr[8] = self._hero_fight_obj(heroes_cfg["12012045"], lv=1, is_boss=False)
            enemy_fap = sum(
                int(h["HP"] + h["AP"] * 5 + h["DEF"] * 5) for h in heros_arr[6:12] if h
            )

        return {
            "NodeInfo": node_cfg,
            "FightInfo": {
                "FightObjs": [
                    {
                        "Heros": heros_arr,
                        "TeamData": [
                            {"Fsp": 2000, "Fap": self.state["player"]["FAP"]},
                            {"Fsp": 1200, "Fap": enemy_fap},
                        ],
                        "Pets": [],
                        "RandNum": 4242,
                        "IsPVP": False,
                    }
                ]
            },
        }

    def _rpc_battle_fight(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) > 0 else 11
        node_id = int(data[1]) if isinstance(data, list) and len(data) > 1 else 1111
        star_lv = int(data[2]) if isinstance(data, list) and len(data) > 2 else 3
        won = bool(data[3]) if isinstance(data, list) and len(data) > 3 else True

        node_cfg = self.game_data["nodes"].get(str(node_id), {"dropGold": 50, "dropHeroExp": 25})
        vit_cfg = self.game_data.get("vit_config", {})
        vit_cost = int(vit_cfg.get("perUseNum", 5))
        per_exp_pct = int(vit_cfg.get("perGetEXPR", 20000))

        gold_gain = int(node_cfg.get("dropGold", 50)) if won else 0
        hero_exp_gain = int(node_cfg.get("dropHeroExp", 25)) if won else 0

        if self.profile_name == "normal" and won:
            old_lv = int(self.state["player"]["Lv"])
            exp_gain = int(vit_cost * old_lv * (per_exp_pct / 10000.0))
            if int(self.state["player"]["VIT"]) >= vit_cost:
                self.ledger.apply_player_delta(
                    self.state["player"], self.profile_name, "VIT", -vit_cost, source=f"battle_vit:{node_id}"
                )
        else:
            exp_gain = 30 if won else 0

        node_st = self.state["nodes"].setdefault(str(node_id), self._make_node_state(node_id, flag=1))
        was_first_clear = won and int(node_st.get("StarCount", 0)) == 0
        node_st["FightCount"] += 1
        node_st["FightTime"] = int(time.time())
        if won:
            prev_star = int(node_st["StarCount"])
            node_st["StarCount"] = max(prev_star, min(3, star_lv))
            node_st["Flag"] = 2  # NODE_PASSED
            self.state["battle"]["StarCount"] += max(0, node_st["StarCount"] - prev_star)

        ch_st = self.state["chapters"].setdefault(str(ch_id), self._make_chapter_state(ch_id))
        ch_nodes = sorted(
            [int(k) for k, v in self.game_data["nodes"].items() if v.get("chapterModelID") == ch_id]
        )
        ch_st["StarCount"] = sum(self.state["nodes"].get(str(nid), {}).get("StarCount", 0) for nid in ch_nodes)

        # Unlock road box if its needNodeModelID is cleared
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

        # Build reward tuples
        reward_tuples: list[tuple[int, int, int]] = []
        if won:
            reward_tuples.append((1101, 0, exp_gain))
            reward_tuples.append((1112, 0, gold_gain))
            reward_tuples.append((1117, 0, hero_exp_gain))
            if self.profile_name == "normal":
                for d in self.game_data.get("node_drops", {}).get(str(node_id), []):
                    odds = int(d.get("dropOdds", 0))
                    # dropOdds==0 in BattleNodeDropRelation represents guaranteed first-clear/scripted tutorial drop
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

        self.save()
        out: dict[str, Any] = {
            "IsSuccess": "True" if won else "False",
            "CurrentChapter": ch_st,
            "CurrentNode": node_st,
            "NextNode": next_node,
            "BaseGetGameResourceList": base_res if won else [],
        }
        if next_chapter is not None:
            out["NextChapter"] = next_chapter
        return out

    def _rpc_draw_road_box(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        box_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 111
        ch_st = self.state["chapters"].get(str(ch_id))
        ch_model = self.game_data["chapters"].get(str(ch_id), {})
        box_cfg = self.game_data.get("road_boxes", {}).get(str(box_id))
        if not ch_st or not box_cfg:
            self._last_rpc_context["status"] = -1
            return {}

        for suffix in ("A", "B", "C"):
            if int(ch_model.get(f"roadBox{suffix}ID", 0)) == box_id:
                ch_st[f"CanDrawRoadBox{suffix}"] = 2

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

        for suffix in ("A", "B", "C"):
            if int(ch_model.get(f"box{suffix}ID", 0)) == box_id:
                ch_st[f"IfDrawBox{suffix}"] = 1

        tuples = _parse_resource_str(box_cfg.get("outputResource", ""))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"chapter_box:{box_id}",
            tx_prefix=f"chapter_box:{self.profile_name}:{self.state['player']['PlayerId']}:{box_id}",
        )
        self.save()
        return {"Chapter": ch_st, "BaseGetGameResourceList": base_res}


class GameEmulatorState:
    """Multi-profile coordinator hosting NORMAL_PROFILE (ServerId=1) and DEBUG_PROFILE (ServerId=2)."""

    def __init__(
        self,
        persist: bool = True,
        new_player: bool = False,
        default_profile: str = "normal",
        normal_path: Path = NORMAL_STATE_PATH,
        debug_path: Path = DEBUG_STATE_PATH,
        audit_path: Path = AUDIT_LOG_PATH,
    ) -> None:
        self.persist = persist
        self.default_profile = default_profile
        self.game_data = json.loads(GAME_DATA_PATH.read_text(encoding="utf-8"))
        self.ledger = ResourceLedger(
            audit_log_path=audit_path if persist else None,
            vip_model=self.game_data.get("vip_model", {}),
        )
        self.profiles: dict[str, ProfileStore] = {
            "normal": ProfileStore(
                "normal",
                self.game_data,
                self.ledger,
                state_path=normal_path,
                persist=persist,
                reset=new_player,
            ),
            "debug": ProfileStore(
                "debug",
                self.game_data,
                self.ledger,
                state_path=debug_path,
                persist=persist,
                reset=False,
                legacy_seed_path=LEGACY_SAVE_STATE_PATH,
            ),
        }

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

    def log_message(self, fmt: str, *args: Any) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(fmt, *args)

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

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

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

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
            if self.server.emu.persist:
                with open(RPC_TRACE_PATH, "a", encoding="utf-8") as tf:
                    tf.write(f"{time.strftime('%H:%M:%S')} STEP_GET {self.path}\n")
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

        if path in ("/api/report.ashx", "/api/stepnew.ashx"):
            if self.server.emu.persist:
                with open(RPC_TRACE_PATH, "a", encoding="utf-8") as tf:
                    tf.write(f"{time.strftime('%H:%M:%S')} STEP_POST {path} body={body[:300]!r}\n")
            self._send_json(200, {"Code": 0, "Message": "OK"})
            return

        if path == "/API/ServerList_CheckResource.ashx":
            if self.server.emu.persist:
                with open(RPC_TRACE_PATH, "a", encoding="utf-8") as tf:
                    tf.write(f"{time.strftime('%H:%M:%S')} CHECK_RES body={body[:200]!r}\n")
            self._send_client_json(200, {"Code": 0, "Data": {}})
            return

        if path == "/API/ServerList_Client.ashx":
            if self.server.emu.persist:
                with open(RPC_TRACE_PATH, "a", encoding="utf-8") as tf:
                    tf.write(f"{time.strftime('%H:%M:%S')} SERVERLIST body={body[:300]!r}\n")
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
    ) -> None:
        self.emu = GameEmulatorState(
            persist=persist,
            new_player=new_player,
            default_profile=default_profile,
        )
        self.assets = AssetArchive(EN_APK_PATH, EN_OBB_PATH)
        self.quiet = quiet
        super().__init__(server_address, EmulatorHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="InuYasha: Seek Jade Local Server Emulator")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (use 0.0.0.0 for LAN/Pixel 3 XL)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument("--profile", choices=["normal", "debug"], default="normal", help="Default server profile")
    parser.add_argument(
        "--new-player",
        "--reset-normal",
        action="store_true",
        dest="reset_normal",
        help="Reset NORMAL_PROFILE to fresh IsNewPlayer=1 state (never alters DEBUG_PROFILE)",
    )
    args = parser.parse_args()

    srv = ThreadingEmulatorServer(
        (args.host, args.port),
        new_player=args.reset_normal,
        default_profile=args.profile,
    )
    print(
        f"InuYasha: Seek Jade Emulator listening on http://{args.host}:{args.port}/poc/ "
        f"(default={args.profile}, normal_pid={srv.emu.profiles['normal'].state['player']['PlayerId']}, "
        f"debug_pid={srv.emu.profiles['debug'].state['player']['PlayerId']})"
    )
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down emulator...")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
