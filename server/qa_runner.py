#!/usr/bin/env python3
"""
Fast QA Engine for InuYasha: Seek Jade Revival.

Drives progression, combat, upgrades, unlocks, and regression checks directly
against verified backend RPCs & Lua combat formulas without client rendering or
manual ADB clicks, while NEVER touching NORMAL_PROFILE saves in server/saves/.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
STABLE_SAVES_DIR = (SERVER_DIR / "saves").resolve()
QA_RUNS_DIR = SERVER_DIR / "qa_runs"
GAME_DATA_PATH = SERVER_DIR / "game_data.json"

sys.path.insert(0, str(SERVER_DIR))
from emulator import EMPTY_ENTITY_ID, GameEmulatorState  # noqa: E402

PVE_FRIEND_ORDER = [1, 2, 3, 4, 5, 6]
PVE_ENEMY_ORDER = [9, 8, 7, 12, 11, 10]
DEFAULT_STAR_TARGET = 1  # 1★ Easy default; configurable up to 3★ Hard


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


class SafetyViolationError(RuntimeError):
    """Raised if QA attempts to touch STABLE saves/port 8080."""


def _is_unsafe_stable_url(url: str) -> bool:
    parsed = urllib.request.urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return port == 8080


class QABackendClient:
    """Unified RPC + Admin transport over isolated local GameEmulatorState or DEV HTTP."""

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        url: str | None = None,
        admin_token: str | None = None,
        profile: str = "normal",
        server_id: int = 1,
        new_player: bool = True,
        persist: bool = True,
    ) -> None:
        self.profile = profile
        self.server_id = server_id
        self.url = url.rstrip("/") if url else None
        self.admin_token = admin_token
        self.emu: GameEmulatorState | None = None

        if self.url:
            if _is_unsafe_stable_url(self.url):
                raise SafetyViolationError(
                    f"Refusing to run QA against STABLE URL {self.url}; use DEV (8082) or isolated in-process dir."
                )
        else:
            if data_dir is not None:
                resolved = Path(data_dir).resolve()
                if resolved == STABLE_SAVES_DIR:
                    raise SafetyViolationError(
                        f"Refusing to run QA inside STABLE saves dir {resolved}."
                    )
            self.emu = GameEmulatorState(
                persist=persist,
                new_player=new_player,
                default_profile=profile,
                env="dev",
                data_dir=data_dir,
                trace_path=(Path(data_dir) / "qa_rpc_trace.log") if (persist and data_dir) else None,
            )

    @property
    def game_data(self) -> dict[str, Any]:
        if self.emu is not None:
            return self.emu.game_data
        return json.loads(GAME_DATA_PATH.read_text(encoding="utf-8"))

    def rpc(self, module: str, method: str, data: list[Any] | None = None) -> dict[str, Any]:
        req = {
            "ModuleName": module,
            "MethodName": method,
            "Data": data or [],
            "ServerId": self.server_id,
            "TimeTick": int(time.time()),
        }
        if self.emu is not None:
            return self.emu.handle_rpc(req)
        raw = json.dumps(req).encode("utf-8")
        http_req = urllib.request.Request(
            f"{self.url}/client.aspx",
            data=raw,
            headers={"Content-Type": "application/json", "X-Plain-Json": "1"},
            method="POST",
        )
        with urllib.request.urlopen(http_req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def state_summary(self) -> dict[str, Any]:
        if self.emu is not None:
            return self.emu.get_profile_by_name(self.profile).admin_state_summary()
        return self._http_admin("GET", f"/admin/state?profile={self.profile}")

    def state_snapshot(self) -> dict[str, Any]:
        if self.emu is not None:
            return self.emu.get_profile_by_name(self.profile).state
        init_res = self.rpc("Player", "GetInitData", [])
        val = init_res["Value"]
        chapters_raw = self.rpc("Battle", "AllChapterInfo", [])["Value"]
        chapters_list = chapters_raw if isinstance(chapters_raw, list) else chapters_raw.get("ChapterList", [])
        return {
            "player": val["PlayerInfo"],
            "heroes": val["HeroInfo"],
            "slots": val["SlotInfo"],
            "equips": val["EquipInfo"],
            "treasures": val["TreasureInfo"],
            "goods": val["GoodsPropsInfo"],
            "chapters": {str(c["ChapterModelId"]): c for c in chapters_list},
            "battle": {
                "MaxChapterId": max([int(c["ChapterModelId"]) for c in chapters_list] or [11]),
                "MaxNodeId": int(self.state_summary()["battle"]["MaxNodeId"]),
                "StarCount": sum(int(c.get("StarCount", 0)) for c in chapters_list),
            },
        }

    def admin_prepare(self, target_lv: int, vip_lv: int | None = None, source: str = "qa_prepare") -> dict[str, Any]:
        if self.emu is not None:
            return self.emu.get_profile_by_name(self.profile).admin_prepare_account(
                target_lv=target_lv, vip_lv=vip_lv, actor="qa_runner", source=source
            )
        return self._http_admin(
            "POST",
            "/admin/prepare",
            {"profile": self.profile, "target_lv": target_lv, "vip_lv": vip_lv, "actor": "qa_runner", "source": source},
        )

    def admin_grant(
        self,
        *,
        resources: list[dict[str, Any]] | None = None,
        items: list[dict[str, Any]] | None = None,
        heroes: list[dict[str, Any]] | None = None,
        equips: list[dict[str, Any]] | None = None,
        source: str = "qa_grant",
    ) -> dict[str, Any]:
        if self.emu is not None:
            return self.emu.get_profile_by_name(self.profile).admin_grant(
                resources=resources,
                items=items,
                heroes=heroes,
                equips=equips,
                actor="qa_runner",
                source=source,
            )
        return self._http_admin(
            "POST",
            "/admin/grant",
            {
                "profile": self.profile,
                "resources": resources,
                "items": items,
                "heroes": heroes,
                "equips": equips,
                "actor": "qa_runner",
                "source": source,
            },
        )

    def _http_admin(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.admin_token:
            raise RuntimeError("admin_token is required for HTTP /admin/* operations")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"X-Admin-Token": self.admin_token, "X-Plain-Json": "1"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            raise RuntimeError(f"Admin {method} {path} failed ({err.code}): {err.read().decode('utf-8')}") from err


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
    Evaluate all waves of a Battle.GetFightInfo payload using real combat math.

    Never rigs outcomes: weak teams genuinely lose when enemy HP outlasts or defeats allies.
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
            e_live = [p for p in PVE_ENEMY_ORDER if p in units and units[p]["HP"] > 0]
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


def apply_preset(client: QABackendClient, preset: str, target_lv: int | None = None) -> dict[str, Any]:
    """Prepare isolated test profile using only valid heroes, equips, and rules in game_data."""
    key = preset.upper()
    client.rpc("Player", "Login", [])
    if key == "STARTER":
        client.rpc("Player", "NewPlayer", ["QAStarter", 1])
        return {"preset": "STARTER", "summary": client.state_summary()}

    if key == "FAILURE":
        client.rpc("Player", "NewPlayer", ["QAFail", 1])
        return {"preset": "FAILURE", "summary": client.state_summary()}

    if key == "PROGRESSION":
        lv = target_lv or 12
        client.admin_prepare(target_lv=lv, vip_lv=0, source="qa_preset_progression")
        client.admin_grant(
            resources=[
                {"type": "Gold", "amount": 150000},
                {"type": "HeroEXP", "amount": 25000},
            ],
            items=[{"id": 16030006, "num": 6}, {"id": 16050001, "num": 80}],
            heroes=[
                {"model_id": 12011005, "lv": lv, "step": 1, "deploy": True, "slot_id": 2},
                {"model_id": 12011006, "lv": lv, "step": 1, "deploy": True, "slot_id": 3},
                {"model_id": 12011007, "lv": lv, "step": 1, "deploy": True, "slot_id": 4},
            ],
            equips=[
                {"model_id": 13010404, "lv": lv, "slot_id": 1},
                {"model_id": 13020404, "lv": lv, "slot_id": 1},
                {"model_id": 13030404, "lv": lv, "slot_id": 2},
                {"model_id": 13040404, "lv": lv, "slot_id": 2},
            ],
            source="qa_preset_progression",
        )
        return {"preset": "PROGRESSION", "summary": client.state_summary()}

    if key == "STRONG":
        lv = target_lv or 18
        client.admin_prepare(target_lv=lv, vip_lv=None, source="qa_preset_strong")
        # Simulated VIP 5 via authentic recharge tiers
        client.rpc("PlayerCharge", "ConfirmOrder", [60])
        client.rpc("PlayerCharge", "ConfirmOrder", [300])
        client.rpc("PlayerCharge", "ConfirmOrder", [3280])
        client.admin_grant(
            resources=[
                {"type": "Gold", "amount": 500000},
                {"type": "HeroEXP", "amount": 80000},
            ],
            items=[{"id": 16030006, "num": 15}, {"id": 16050001, "num": 250}],
            heroes=[
                {"model_id": 12011004, "lv": lv, "step": 2, "deploy": True, "slot_id": 2},
                {"model_id": 12012005, "lv": lv, "step": 2, "deploy": True, "slot_id": 3},
                {"model_id": 12011005, "lv": lv, "step": 2, "deploy": True, "slot_id": 4},
                {"model_id": 12011007, "lv": lv, "step": 2, "deploy": True, "slot_id": 5},
            ],
            equips=[
                {"model_id": 13010602, "lv": min(lv * 2, 36), "slot_id": 1},
                {"model_id": 13020602, "lv": min(lv * 2, 36), "slot_id": 1},
                {"model_id": 13030602, "lv": min(lv * 2, 36), "slot_id": 2},
                {"model_id": 13040602, "lv": min(lv * 2, 36), "slot_id": 2},
                {"model_id": 13010503, "lv": min(lv * 2, 36), "slot_id": 3},
                {"model_id": 13020503, "lv": min(lv * 2, 36), "slot_id": 3},
            ],
            source="qa_preset_strong",
        )
        return {"preset": "STRONG", "summary": client.state_summary()}

    raise ValueError(f"Unknown preset: {preset}")


def _maintain_progression(client: QABackendClient) -> list[str]:
    """Use ONLY earned in-game resources to recruit/deploy/upgrade/explore within rules."""
    actions: list[str] = []
    snap = client.state_snapshot()
    p = snap["player"]

    # 1. Starter onboarding steps & legit summons when team has < 4 heroes
    steps_claimed = False
    for step_id in (100, 102, 106, 110):
        res = client.rpc("Player", "GetStepCountReward", [step_id])
        if res.get("Status") == 0 and res.get("Value"):
            steps_claimed = True
    if steps_claimed:
        actions.append("claimed_step_rewards")
    if len(snap["heroes"]) == 1:
        r = client.rpc("HeroRecruit", "Recruit", [3, 1])
        if r.get("Status") == 0 and r.get("Value", {}).get("BaseGetGameResourceList"):
            actions.append("destiny_recruit_free")
    # Spend earned Diamonds on additional Destiny Recruit if squad still < 4 heroes
    while len(snap["heroes"]) < 4 and int(snap["player"].get("Diamond", 0)) >= 280:
        r = client.rpc("HeroRecruit", "Recruit", [3, 0])
        if r.get("Status") == 0 and r.get("Value", {}).get("BaseGetGameResourceList"):
            actions.append("destiny_recruit_diamond")
            snap = client.state_snapshot()
        else:
            break

    # 2. Deploy idle heroes into open slots (up to unlocked slots)
    snap = client.state_snapshot()
    deployed_ids = {s["HeroId"] for s in snap["slots"] if int(s.get("HeroModelId", 0)) > 0}
    idle = [h for h in snap["heroes"] if h["Id"] not in deployed_ids]
    max_slots = min(6, 2 if int(snap["player"]["Lv"]) < 5 else 4 if int(snap["player"]["Lv"]) < 10 else 6)
    for slot in snap["slots"][:max_slots]:
        if int(slot.get("HeroModelId", 0)) == 0 and idle:
            h = idle.pop(0)
            res = client.rpc("Slot", "HeroCombat", [slot["SlotId"], h["Id"]])
            if res.get("Status") == 0:
                actions.append(f"deploy:{h['HeroModelId']}->slot{slot['SlotId']}")

    # 3. Level up & Step up deployed heroes using earned Gold/HeroEXP/Pills
    snap = client.state_snapshot()
    for slot in snap["slots"]:
        hid = slot.get("HeroId")
        if int(slot.get("HeroModelId", 0)) > 0 and hid:
            up = client.rpc("Hero", "HeroLvUp", [hid, 5])
            if up.get("Status") == 0:
                actions.append(f"hero_lvup:{slot['SlotId']}")
            su = client.rpc("Hero", "HeroStepUp", [hid, []])
            if su.get("Status") == 0:
                actions.append(f"hero_stepup:{slot['SlotId']}")

    # 4. Equip best free equips onto Slot 1..4
    def _slot_eq_id(val: Any) -> str:
        if isinstance(val, dict):
            return str(val.get("Id") or EMPTY_ENTITY_ID)
        return str(val or EMPTY_ENTITY_ID)

    snap = client.state_snapshot()
    assigned_eq = set()
    for s in snap["slots"]:
        for k in ("Weapon", "Helmet", "Clothes", "Necklace"):
            eid = _slot_eq_id(s.get(k))
            if eid != EMPTY_ENTITY_ID:
                assigned_eq.add(eid)
    type_buckets = {1301: "Weapon", 1302: "Helmet", 1303: "Clothes", 1304: "Necklace"}
    free_eqs = [e for e in snap["equips"] if e["Id"] not in assigned_eq]
    for s in snap["slots"]:
        if int(s.get("HeroModelId", 0)) <= 0 or not free_eqs:
            continue
        chosen = {
            "Weapon": _slot_eq_id(s.get("Weapon")),
            "Helmet": _slot_eq_id(s.get("Helmet")),
            "Clothes": _slot_eq_id(s.get("Clothes")),
            "Necklace": _slot_eq_id(s.get("Necklace")),
        }
        changed = False
        for prefix, skey in type_buckets.items():
            if chosen[skey] == EMPTY_ENTITY_ID:
                cand = next((e for e in free_eqs if int(e["EquipModelId"]) // 10000 == prefix), None)
                if cand:
                    chosen[skey] = cand["Id"]
                    free_eqs.remove(cand)
                    changed = True
        if changed:
            res = client.rpc(
                "Slot",
                "OneKeyEquipCombat",
                [s["SlotId"], chosen["Weapon"], chosen["Helmet"], chosen["Clothes"], chosen["Necklace"], EMPTY_ENTITY_ID, EMPTY_ENTITY_ID],
            )
            if res.get("Status") == 0:
                actions.append(f"equip_slot:{s['SlotId']}")

    # 4b. Enhance equipped gear with earned Gold via OneKeyEquipLvUp
    snap = client.state_snapshot()
    if int(snap["player"].get("Gold", 0)) >= 500:
        eq_up_ids: list[str] = []
        for s in snap["slots"]:
            for k in ("Weapon", "Helmet", "Clothes", "Necklace"):
                eid = _slot_eq_id(s.get(k))
                if eid != EMPTY_ENTITY_ID:
                    eq_up_ids.append(eid)
        if eq_up_ids and client.rpc("Equip", "OneKeyEquipLvUp", [eq_up_ids[:4]]).get("Status") == 0:
            actions.append("equip_lvup")

    # 5. Claim eligible RoadBox / ChapterBox rewards & Explore if unlocked
    snap = client.state_snapshot()
    gd = client.game_data
    for ch_id_str, ch_st in snap["chapters"].items():
        ch_model = gd["chapters"].get(ch_id_str, {})
        for suffix in ("A", "B", "C"):
            if int(ch_st.get(f"CanDrawRoadBox{suffix}", 0)) == 1:
                bid = int(ch_model.get(f"roadBox{suffix}ID", 0))
                if bid and client.rpc("Battle", "DrawRoadBox", [int(ch_id_str), bid]).get("Status") == 0:
                    actions.append(f"roadbox:{ch_id_str}:{suffix}")
            need_star = int(ch_model.get(f"box{suffix}StarCount", 999))
            bid = int(ch_model.get(f"box{suffix}ID", 0))
            if (
                bid > 0
                and not ch_st.get(f"IfDrawBox{suffix}", False)
                and int(ch_st.get("StarCount", 0)) >= need_star
            ):
                if client.rpc("Battle", "DrawBox", [int(ch_id_str), bid]).get("Status") == 0:
                    actions.append(f"chapterbox:{ch_id_str}:{suffix}")

    if int(snap["player"]["Lv"]) >= 7:
        exp_info = client.rpc("Explore", "GetInfo", [])["Value"]
        if int(exp_info.get("RemainNum", 0)) > 0:
            ex = client.rpc("Explore", "OneKeyExplore", [])
            if ex.get("Status") == 0:
                actions.append("one_key_explore")

    # 6. LightenStar progression if Lv >= 8 and player has spare Gold/Stars
    if int(snap["player"]["Lv"]) >= 8:
        for _ in range(3):
            ls = client.rpc("LightenStar", "LightenStar", [])
            if ls.get("Status") == 0:
                actions.append("lighten_star")
            else:
                break
    return actions


def run_progression_qa(
    client: QABackendClient,
    *,
    preset: str = "STARTER",
    target_lv: int | None = None,
    target_node: int | None = None,
    max_stages: int = 30,
    star_lv: int = DEFAULT_STAR_TARGET,
    auto_use_vit_pill: bool = True,
) -> dict[str, Any]:
    """Run Fast QA progression loop using authentic RPCs & real FightInfo combat."""
    t0 = time.perf_counter()
    gd = client.game_data
    attacks_cfg = gd["attacks"]
    all_nodes_sorted = sorted(int(nid) for nid in gd["nodes"].keys())
    preset_info = apply_preset(client, preset, target_lv=target_lv if preset.upper() in ("PROGRESSION", "STRONG") else None)

    stage_logs: list[dict[str, Any]] = []
    stop_reason = "max_stages_reached"
    failure_detail: dict[str, Any] | None = None

    for step in range(max_stages):
        snap = client.state_snapshot()
        cur_lv = int(snap["player"]["Lv"])
        max_node = int(snap["battle"]["MaxNodeId"])

        if target_lv is not None and preset.upper() == "STARTER" and cur_lv >= target_lv and step > 0:
            stop_reason = f"reached_target_lv_{target_lv}"
            break
        if target_node is not None and max_node >= target_node and step > 0:
            stop_reason = f"reached_target_node_{target_node}"
            break

        prep_actions = _maintain_progression(client) if preset.upper() != "FAILURE" else []
        snap = client.state_snapshot()
        next_node_id = target_node if (preset.upper() == "FAILURE" and target_node) else int(snap["battle"]["MaxNodeId"])
        if str(next_node_id) not in gd["nodes"]:
            stop_reason = f"unknown_node_{next_node_id}"
            break
        ch_id = int(gd["nodes"][str(next_node_id)]["chapterModelID"])

        vit_needed = int(gd["nodes"][str(next_node_id)].get("fightVIT", 6))
        if int(snap["player"]["VIT"]) < vit_needed and auto_use_vit_pill:
            pill = next((g for g in snap["goods"] if int(g.get("GoodsModelId", 0)) == 16030006 and int(g.get("Num", 0)) > 0), None)
            if pill:
                client.rpc("Goods", "GoodsUse", [pill["Id"], 16030006, 1])
                prep_actions.append("use_vit_pill")

        snap_pre = client.state_snapshot()
        if int(snap_pre["player"]["VIT"]) < vit_needed:
            stop_reason = "stamina_exhausted"
            failure_detail = {"node_id": next_node_id, "vit": snap_pre["player"]["VIT"], "need_vit": vit_needed}
            break

        fi_res = client.rpc("Battle", "GetFightInfo", [ch_id, next_node_id, star_lv])
        if fi_res.get("Status") != 0:
            stop_reason = "get_fight_info_error"
            failure_detail = {"node_id": next_node_id, "response": fi_res}
            break

        combat = simulate_fight_info(fi_res["Value"]["FightInfo"], attacks_cfg)
        b_res = client.rpc(
            "Battle",
            "Fight",
            [ch_id, next_node_id, star_lv, combat.won, json.dumps(combat.verify_data)],
        )
        post_summary = client.state_summary()

        stage_logs.append(
            {
                "step": step + 1,
                "node_id": next_node_id,
                "chapter_id": ch_id,
                "star_target": star_lv,
                "won": combat.won,
                "waves": combat.waves,
                "rounds": combat.total_rounds,
                "ally_alive": combat.ally_alive,
                "ally_hp_pct": combat.ally_hp_pct,
                "lv_after": post_summary["player"]["Lv"],
                "fap_after": post_summary["player"]["FAP"],
                "max_node_after": post_summary["battle"]["MaxNodeId"],
                "actions": prep_actions,
                "rpc_status": b_res.get("Status"),
            }
        )

        if b_res.get("Status") != 0:
            stop_reason = "battle_fight_rpc_error"
            failure_detail = {"node_id": next_node_id, "status": b_res.get("Status")}
            break
        if not combat.won:
            stop_reason = "battle_defeat"
            failure_detail = {
                "node_id": next_node_id,
                "chapter_id": ch_id,
                "ally_fap": snap_pre["player"]["FAP"],
                "rounds": combat.total_rounds,
                "enemy_alive": combat.enemy_alive,
            }
            break

        # Advance to next node only if we are replaying a lower node
        cur_max = post_summary["battle"]["MaxNodeId"]
        if cur_max == next_node_id:
            idx = all_nodes_sorted.index(next_node_id)
            if idx + 1 >= len(all_nodes_sorted):
                stop_reason = "all_nodes_cleared"
                break

    elapsed_s = round(time.perf_counter() - t0, 4)
    final_summary = client.state_summary()
    return {
        "preset": preset_info["preset"],
        "stop_reason": stop_reason,
        "failure_detail": failure_detail,
        "stages_attempted": len(stage_logs),
        "stages_won": sum(1 for s in stage_logs if s["won"]),
        "elapsed_sec": elapsed_s,
        "final_summary": final_summary,
        "stage_logs": stage_logs,
    }


def run_benchmark_suite(out_dir: Path | None = None) -> dict[str, Any]:
    """Run standardized Fast QA suite: 10-stage benchmark, R3/R4 regression, FAILURE, and VIP/Elite."""
    run_id = time.strftime("%Y%m%d_%H%M%S")
    base_dir = out_dir or (QA_RUNS_DIR / f"bench_{run_id}")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. 10-Stage Benchmark (from Lv 1 Starter)
    c10 = QABackendClient(data_dir=base_dir / "ten_stages", persist=True, new_player=True)
    res_10 = run_progression_qa(c10, preset="STARTER", max_stages=10, star_lv=2)

    # 2. R3/R4 Full Regression + Subsystems (Lv 1 -> Ch 16/17 + Shop + TreasureLoot + Elite + Charge/VIP)
    c_reg = QABackendClient(data_dir=base_dir / "regression_r4", persist=True, new_player=True)
    res_reg = run_progression_qa(c_reg, preset="STARTER", max_stages=25, target_node=1419, star_lv=2)

    # Exercise R4 subsystems + VIP/Charge/LvPlan/VipWelfare on regression profile
    sub_checks: dict[str, Any] = {}
    shop_buy = c_reg.rpc("ShopGoods", "BuyGoods", [1, 1])
    sub_checks["shop_buy_status"] = shop_buy.get("Status")
    c_reg.admin_grant(
        resources=[{"type": "Gold", "amount": 50000}],
        items=[{"id": 15040101, "num": 1}, {"id": 15040102, "num": 1}, {"id": 15040103, "num": 1}],
        source="qa_treasure_check",
    )
    t_list = c_reg.rpc("TreasureLoot", "TreasureDebrisTargetList", [0, 15040103])
    sub_checks["treasure_targets"] = len(t_list.get("Value", {}).get("TreasureLootTeamInfo", []))
    comp = c_reg.rpc("TreasureDebris", "TreasureDebrisCompose", [14020501])
    sub_checks["treasure_compose_ok"] = comp.get("Status") == 0 and bool(comp.get("Value", {}).get("BaseGetGameResourceList"))

    # VIP 2 + Simulated Recharge + LvPlan + VipWelfare + EliteBattle (Lv 18 check)
    c_reg.admin_prepare(target_lv=18, source="qa_elite_gate")
    chg1 = c_reg.rpc("PlayerCharge", "ConfirmOrder", [60])
    chg2 = c_reg.rpc("PlayerCharge", "ConfirmOrder", [300])
    box = c_reg.rpc("PlayerCharge", "DrawChargeBox", [300])
    lvp = c_reg.rpc("LvPlan", "ReceiveLvPlan", [10])
    vw = c_reg.rpc("VipWelfare", "DrawVipWelfare", [])
    efi = c_reg.rpc("EliteBattle", "GetFightInfo", [11])
    el_combat = simulate_fight_info(efi["Value"]["FightInfo"], c_reg.game_data["attacks"])
    ef = c_reg.rpc("EliteBattle", "Fight", [11, el_combat.won, json.dumps(el_combat.verify_data)])
    sub_checks["simulated_charge_vip"] = chg2["Value"].get("Vip")
    sub_checks["first_charge_box_ok"] = box.get("Status") == 0
    sub_checks["lv_plan_claim_ok"] = lvp.get("Status") == 0
    sub_checks["vip_welfare_ok"] = vw.get("Status") == 0
    sub_checks["elite_battle_won"] = el_combat.won and ef.get("Status") == 0

    # 3. Realistic FAILURE preset check (weak Lv 1 hero vs 3★ Hard Ch 16 boss 1620 -> genuine defeat!)
    c_fail = QABackendClient(data_dir=base_dir / "failure_case", persist=True, new_player=True)
    res_fail = run_progression_qa(c_fail, preset="FAILURE", target_node=1620, max_stages=1, star_lv=3)

    report = {
        "run_id": run_id,
        "isolated_dir": str(base_dir),
        "ten_stage_benchmark": {
            "stages_won": res_10["stages_won"],
            "elapsed_sec": res_10["elapsed_sec"],
            "final_lv": res_10["final_summary"]["player"]["Lv"],
            "final_node": res_10["final_summary"]["battle"]["MaxNodeId"],
        },
        "r3_r4_regression": {
            "stages_won": res_reg["stages_won"],
            "stop_reason": res_reg["stop_reason"],
            "elapsed_sec": res_reg["elapsed_sec"],
            "final_lv": res_reg["final_summary"]["player"]["Lv"],
            "final_stars": res_reg["final_summary"]["battle"]["StarCount"],
            "sub_checks": sub_checks,
        },
        "failure_preset_check": {
            "stop_reason": res_fail["stop_reason"],
            "stages_won": res_fail["stages_won"],
            "failure_detail": res_fail["failure_detail"],
            "elapsed_sec": res_fail["elapsed_sec"],
        },
    }
    report_path = base_dir / "qa_benchmark_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="InuYasha: Seek Jade Fast QA Engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bench = sub.add_parser("benchmark", help="Run 10-stage, R3/R4 regression, VIP/Elite, and FAILURE benchmarks")
    p_bench.add_argument("--out-dir", type=Path, default=None, help="Isolated output directory under server/qa_runs/")

    p_run = sub.add_parser("run", help="Run isolated progression QA for a preset")
    p_run.add_argument("--preset", choices=["STARTER", "PROGRESSION", "STRONG", "FAILURE"], default="STARTER")
    p_run.add_argument("--target-lv", type=int, default=None)
    p_run.add_argument("--target-node", type=int, default=None)
    p_run.add_argument("--max-stages", type=int, default=20)
    p_run.add_argument("--star-lv", type=int, choices=[1, 2, 3], default=2)
    p_run.add_argument("--url", default=None, help="Optional DEV emulator URL (refuses port 8080)")
    p_run.add_argument("--admin-token", default=None, help="Admin token if --url is used")
    p_run.add_argument("--out-dir", type=Path, default=None)

    args = parser.parse_args()
    if args.cmd == "benchmark":
        rep = run_benchmark_suite(out_dir=args.out_dir)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0

    out_dir = args.out_dir or (QA_RUNS_DIR / f"run_{args.preset.lower()}_{time.strftime('%Y%m%d_%H%M%S')}")
    client = QABackendClient(
        data_dir=None if args.url else out_dir,
        url=args.url,
        admin_token=args.admin_token,
        persist=args.url is None,
        new_player=args.url is None,
    )
    res = run_progression_qa(
        client,
        preset=args.preset,
        target_lv=args.target_lv,
        target_node=args.target_node,
        max_stages=args.max_stages,
        star_lv=args.star_lv,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "qa_run_report.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: v for k, v in res.items() if k != "stage_logs"}
    summary["report_path"] = str(out_dir / "qa_run_report.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
