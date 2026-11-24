"""Kho Vàng (GGZJ / 勇闯金库, ModuleSub 2504/2509/2510) handlers."""

from __future__ import annotations

import copy
import random
import uuid
import zlib
from typing import Any

from combat_sim import simulate_fight_info
from nightmare_handlers import scale_wave_to_target_fap
from r79_event_handlers import _parse_res_tuples

EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"

_GGZJ_ENEMY_NAMES: tuple[str, ...] = (
    "Sát Sinh Hoàn",
    "Khuyển Dạ Xoa",
    "Nại Lạc",
    "Kikyo",
    "Thần Lạc",
    "Thiết Toái Nha",
    "Phong Chi Thủ",
    "Thất Nhân Đội",
    "Bạch Linh Sơn",
    "Tây Quốc Vương",
    "Ngân Lang",
    "Xích Nguyệt",
    "Minh Đạo Tàn",
    "Kim Ngân Hầu",
    "Thiên Cổ Khôi",
)

_GGZJ_ENEMY_POOLS: tuple[int, ...] = (
    12011004,
    12011005,
    12011006,
    12011007,
    12011008,
    12011009,
    12011011,
    12011012,
    12011013,
    12011018,
    12011019,
    12011022,
    12012005,
    12013003,
    12013004,
)


def _det_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"inuyasha.revival.{seed}"))


class GgzjHandlersMixin:
    """Offline server emulation for Kho Vàng (`GGZJ`, 8 RPCs)."""

    def _ggzj_is_truce(self) -> bool:
        dt = self.clock.dt()
        return dt.hour == 23 and dt.minute >= 50

    def _ggzj_default_formation(self) -> list[int]:
        emb = self.state.get("embattle", {})
        used: set[int] = set()
        front: list[int] = []
        for idx in range(1, 7):
            val = int(emb.get(f"Formation{idx}", idx) or idx)
            if 1 <= val <= 6 and val not in used:
                front.append(val)
                used.add(val)
        for cand in range(1, 7):
            if len(front) >= 6:
                break
            if cand not in used:
                front.append(cand)
                used.add(cand)
        return front[:6] + [7]

    def _ggzj_state(self) -> dict[str, Any]:
        today = self.clock.today_str()
        ggzj = self.state.setdefault("ggzj", {})
        if not isinstance(ggzj, dict) or ggzj.get("day") != today:
            p = self.state["player"]
            ggzj = {
                "day": today,
                "base_fap": max(10_000, int(p.get("FAP", 10_000))),
                "node_id": 1,
                "fight_count": 0,
                "box_process": 0,
                "clearance_drawn": False,
                "share_type": 0,
                "share_id": EMPTY_ENTITY_ID,
                "hero_model_id": 0,
                "hero_lv": 0,
                "formation": self._ggzj_default_formation(),
                "refresh_seed": 0,
                "pending_fight": None,
            }
            self.state["ggzj"] = ggzj
        ggzj.setdefault("node_id", 1)
        ggzj.setdefault("fight_count", 0)
        ggzj.setdefault("box_process", 0)
        ggzj.setdefault("clearance_drawn", False)
        ggzj.setdefault("share_type", 0)
        ggzj.setdefault("share_id", EMPTY_ENTITY_ID)
        ggzj.setdefault("hero_model_id", 0)
        ggzj.setdefault("hero_lv", 0)
        if not isinstance(ggzj.get("formation"), list) or len(ggzj["formation"]) != 7:
            ggzj["formation"] = self._ggzj_default_formation()
        ggzj.setdefault("refresh_seed", 0)
        return ggzj

    def _ggzj_welfare_mult(self) -> int:
        val = self._timed_welfare_mult(4415, default=1)
        return max(1, val // 100) if val >= 100 else max(1, val)

    def _ggzj_build_target(self, ggzj: dict[str, Any], node_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        p_lv = int(self.state["player"].get("Lv", 32))
        if node_id <= 0:
            return (
                {
                    "NodeId": 0,
                    "Lv": p_lv,
                    "Name": "",
                    "ServerName": "S1",
                    "FAP": 0,
                    "HeroModelId": 12011004,
                    "FashionModelId": 0,
                    "PVPInterLv": 0,
                    "SlotFormationInfo": [],
                },
                [{} for _ in range(6)],
            )

        cfg = self.game_data.get("ggzj_config", {})
        node_total = max(1, int(cfg.get("nodeTotal", 15)))
        refresh_seed = int(ggzj.get("refresh_seed", 0))
        seed_int = zlib.crc32(f"{ggzj.get('day', '')}:{node_id}:{refresh_seed}".encode("utf-8"))
        rng = random.Random(seed_int)

        heroes_cfg = self.game_data.get("heroes", {})
        pool = [hm for hm in _GGZJ_ENEMY_POOLS if str(hm) in heroes_cfg]
        if not pool:
            pool = [int(k) for k in list(heroes_cfg.keys())[:15]]
        rng.shuffle(pool)

        unit_count = min(6, 3 + (node_id - 1) // 4, len(pool))
        chosen = pool[:unit_count]
        enemy_lv = max(25, min(80, p_lv - 3 + (node_id // 3)))
        step_up = max(0, min(8, (node_id - 1) // 2))

        base_fap = max(10_000, int(ggzj.get("base_fap", 10_000)))
        ratio = 0.55 + (node_id - 1) * (0.57 / max(1, node_total - 1))
        if refresh_seed > 0:
            ratio *= 0.90
        target_fap = max(3000.0, float(base_fap) * ratio)

        enemies: list[dict[str, Any]] = [{} for _ in range(6)]
        raw_slot_meta: list[tuple[int, dict[str, Any]]] = []
        for idx, hm in enumerate(chosen, start=1):
            h_cfg = heroes_cfg[str(hm)]
            unit = self._hero_fight_obj(h_cfg, lv=enemy_lv, is_boss=False, step=step_up)
            enemies[idx - 1] = unit
            raw_slot_meta.append((idx, unit))

        actual_fap = scale_wave_to_target_fap(enemies, target_fap)
        slot_formation_info: list[dict[str, Any]] = []
        for pos, unit in raw_slot_meta:
            unit_fap = int(unit["HP"] + unit["AP"] * 10 + unit["DEF"] * 10)
            slot_formation_info.append(
                {
                    "Formation": pos,
                    "HeroModelId": int(unit["HeroModelId"]),
                    "Step": step_up,
                    "Lv": enemy_lv,
                    "FAP": unit_fap,
                }
            )

        lead_hm = int(chosen[0])
        target_name = _GGZJ_ENEMY_NAMES[(seed_int + node_id) % len(_GGZJ_ENEMY_NAMES)]
        target_dict = {
            "NodeId": node_id,
            "Lv": enemy_lv,
            "Name": target_name if refresh_seed == 0 else f"{target_name}·{refresh_seed}",
            "ServerName": "S1",
            "FAP": actual_fap,
            "HeroModelId": lead_hm,
            "FashionModelId": 0,
            "PVPInterLv": 0,
            "SlotFormationInfo": slot_formation_info,
        }
        return target_dict, enemies

    def _ggzj_build_ally_fight_objs(self, ggzj: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        heroes_cfg = self.game_data["heroes"]
        heroes_by_id = {h["Id"]: h for h in self.state.get("heroes", [])}
        slots_by_id = {int(s["SlotId"]): s for s in self.state.get("slots", [])}
        formation = [int(x) for x in ggzj.get("formation", self._ggzj_default_formation())]
        allies: list[dict[str, Any]] = [{} for _ in range(6)]
        share_fap = 0

        for pos_idx in range(6):
            slot_idx = formation[pos_idx]
            if 1 <= slot_idx <= 6:
                slot = slots_by_id.get(slot_idx)
                if slot and slot.get("HeroId") and slot["HeroId"] != EMPTY_ENTITY_ID:
                    cfg = heroes_cfg.get(str(slot["HeroModelId"]))
                    if cfg:
                        inst = heroes_by_id.get(slot["HeroId"], {})
                        allies[pos_idx] = self._hero_fight_obj(
                            cfg,
                            is_boss=False,
                            step=int(inst.get("Step", 0)),
                            reborn_step=int(inst.get("RebornStep", 0)),
                            reborn_id=int(inst.get("RebornId", 0)),
                            override_stats=slot["Property"],
                        )
            elif slot_idx == 7 and int(ggzj.get("share_type", 0)) == 2:
                merc_hm = int(ggzj.get("hero_model_id", 0))
                merc_lv = int(ggzj.get("hero_lv", 0))
                row = self.game_data.get("ggzj_system_heroes", {}).get(str(merc_lv), {}).get(str(merc_hm))
                cfg = heroes_cfg.get(str(merc_hm))
                if row and cfg:
                    override = dict(row)
                    override["CRId"] = int(row.get("CRID", 0))
                    allies[pos_idx] = self._hero_fight_obj(
                        cfg,
                        lv=merc_lv,
                        is_boss=False,
                        step=int(row.get("step", 0)),
                        override_stats=override,
                    )
                    share_fap = int(row.get("FAP", 0))
            elif slot_idx == 7 and int(ggzj.get("share_type", 0)) == 1 and hasattr(self, "_guild_get_shared_hero"):
                merc = ggzj.get("share_snapshot") or self._guild_get_shared_hero(
                    str(ggzj.get("share_id", "")),
                    int(ggzj.get("hero_model_id", 0)),
                )
                if isinstance(merc, dict):
                    merc_hm = int(merc.get("HeroModelId", ggzj.get("hero_model_id", 0)))
                    cfg = heroes_cfg.get(str(merc_hm))
                    if cfg:
                        override = merc.get("Property")
                        if not isinstance(override, dict) or not override:
                            override = {
                                "HP": int(merc.get("HP", 8000)),
                                "AP": int(merc.get("AP", 1200)),
                                "DEF": int(merc.get("DEF", 600)),
                                "FSP": int(merc.get("FSP", 100)),
                            }
                        allies[pos_idx] = self._hero_fight_obj(
                            cfg,
                            lv=int(merc.get("Lv", 32)),
                            is_boss=False,
                            step=int(merc.get("Step", 0)),
                            reborn_step=int(merc.get("RebornStep", 0)),
                            reborn_id=int(merc.get("RebornId", 0)),
                            override_stats=override,
                        )
                        share_fap = int(merc.get("FAP", 0))
        return allies, share_fap

    def _ggzj_red_dot(self) -> int:
        lv = int(self.state.get("player", {}).get("Lv", 1))
        if lv < 32 or self._ggzj_is_truce():
            return 0
        ggzj = self._ggzj_state()
        node_id = int(ggzj.get("node_id", 1))
        cfg = self.game_data.get("ggzj_config", {})
        max_try = int(cfg.get("perNodeDareNumMax", 3))
        if node_id > 0 and int(ggzj.get("fight_count", 0)) < max_try:
            return 1
        node_total = int(cfg.get("nodeTotal", 15))
        cleared = node_total if node_id == 0 else max(0, node_id - 1)
        box_proc = int(ggzj.get("box_process", 0))
        for k in self.game_data.get("ggzj_box_reward", {}):
            bm = int(k)
            if box_proc < bm <= cleared:
                return 1
        return 0

    def _ggzj_info_payload(self, ggzj: dict[str, Any]) -> dict[str, Any]:
        node_id = int(ggzj.get("node_id", 1))
        target_dict, _ = self._ggzj_build_target(ggzj, node_id)
        formation = [int(x) for x in ggzj.get("formation", self._ggzj_default_formation())]
        out: dict[str, Any] = {
            "NodeId": node_id,
            "FightCount": int(ggzj.get("fight_count", 0)),
            "BoxProcess": int(ggzj.get("box_process", 0)),
            "IsReceiveClearanceRewards": bool(ggzj.get("clearance_drawn", False)),
            "ShareType": int(ggzj.get("share_type", 0)),
            "ShareId": str(ggzj.get("share_id", EMPTY_ENTITY_ID)),
            "HeroModelId": int(ggzj.get("hero_model_id", 0)),
            "HeroLv": int(ggzj.get("hero_lv", 0)),
            "Target": [target_dict],
        }
        for i in range(1, 8):
            out[f"Formation{i}"] = formation[i - 1]
        return out

    # -------------------- 8 GGZJ RPCs --------------------

    def _rpc_ggzj_get_info(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < 32:
            self._last_rpc_context["status"] = -1
            return {}
        ggzj = self._ggzj_state()
        out = self._ggzj_info_payload(ggzj)
        self.save()
        return out

    def _rpc_ggzj_formation_change(self, data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < 32:
            self._last_rpc_context["status"] = -1
            return {}
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], list):
            raw = data[0]
        else:
            raw = data
        if not isinstance(raw, list) or len(raw) != 7:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            arr = [int(x) for x in raw]
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        if sorted(arr) != [1, 2, 3, 4, 5, 6, 7] or arr[6] == 1:
            self._last_rpc_context["status"] = -1
            return {}
        ggzj = self._ggzj_state()
        ggzj["formation"] = arr
        self.save()
        return {}

    def _rpc_ggzj_hire(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        if int(p.get("Lv", 1)) < 32 or self._ggzj_is_truce() or not isinstance(data, list) or len(data) < 3:
            self._last_rpc_context["status"] = -1
            return {}
        ggzj = self._ggzj_state()
        if int(ggzj.get("share_type", 0)) != 0:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            hire_type = int(data[0])
            hero_model_id = int(data[2])
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}

        if hire_type == 1:
            if not hasattr(self, "_guild_get_shared_hero") or str(p.get("GuildId", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
                self._last_rpc_context["status"] = -3425
                return {}
            merc = self._guild_get_shared_hero(str(data[1]), hero_model_id)
            if not merc:
                self._last_rpc_context["status"] = -1
                return {}
            if int(merc.get("HireCount", 0)) >= 5:
                self._last_rpc_context["status"] = -3426
                return {}
            cfg = self.game_data.get("ggzj_config", {})
            lv_diff_max = int(cfg.get("hireLVDiffMax", 5))
            if int(merc.get("Lv", 1)) > int(p.get("Lv", 1)) + lv_diff_max:
                self._last_rpc_context["status"] = -1
                return {}
            reqs = _parse_res_tuples(str(cfg.get("hireUse", "1605,16050016,2")))
            for rt, rm, rn in reqs:
                if rt == 1112:
                    if int(p.get("Gold", 0)) < rn:
                        self._last_rpc_context["status"] = -1
                        return {}
                else:
                    have = sum(int(g.get("Num", 0)) for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == rm)
                    if have < rn:
                        self._last_rpc_context["status"] = -1
                        return {}
            ok, err = self._guild_record_merc_hired(str(merc["PlayerId"]), hero_model_id)
            if not ok:
                self._last_rpc_context["status"] = err
                return {}
            for rt, rm, rn in reqs:
                if rt == 1112:
                    self.ledger.apply_player_delta(p, self.profile_name, "Gold", -rn, source="ggzj_hire_guild")
                else:
                    self._consume_goods(rm, rn)
            ggzj["share_type"] = 1
            ggzj["share_id"] = str(merc["ShareId"])
            ggzj["hero_model_id"] = hero_model_id
            ggzj["hero_lv"] = int(merc.get("Lv", 32))
            ggzj["share_snapshot"] = copy.deepcopy(merc)
            self.save()
            return {
                "ShareType": 1,
                "ShareId": str(merc["ShareId"]),
                "HeroModelId": hero_model_id,
                "HeroLv": int(ggzj["hero_lv"]),
            }

        if hire_type != 2:
            self._last_rpc_context["status"] = -1
            return {}

        sys_tbl = self.game_data.get("ggzj_system_heroes", {})
        lv_key = str(min(max(1, int(p.get("Lv", 32))), max((int(k) for k in sys_tbl), default=100)))
        row = sys_tbl.get(lv_key, {}).get(str(hero_model_id))
        if not row:
            self._last_rpc_context["status"] = -1
            return {}

        cfg = self.game_data.get("ggzj_config", {})
        reqs = _parse_res_tuples(str(cfg.get("highHireUse", "1605,16050016,8")))
        for _, rm, rn in reqs:
            if not self._consume_goods(rm, rn):
                self._last_rpc_context["status"] = -1
                return {}

        ggzj["share_type"] = 2
        ggzj["share_id"] = EMPTY_ENTITY_ID
        ggzj["hero_model_id"] = hero_model_id
        ggzj["hero_lv"] = int(lv_key)
        ggzj.pop("share_snapshot", None)
        self.save()
        return {
            "ShareType": 2,
            "ShareId": EMPTY_ENTITY_ID,
            "HeroModelId": hero_model_id,
            "HeroLv": int(lv_key),
        }

    def _rpc_ggzj_refresh_npc(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        lv = int(p.get("Lv", 1))
        vip = int(p.get("Vip", 0))
        gate = self.game_data.get("module_subs", {}).get("2509", {})
        open_lv = int(gate.get("openLv", 35))
        adv_vip = int(gate.get("advancedOpenVIPLv", 4))
        vip_need_lv = int(gate.get("VIPNeedLv", 32))
        if lv < open_lv and not (vip >= adv_vip and lv >= vip_need_lv):
            self._last_rpc_context["status"] = -1
            return {}
        if self._ggzj_is_truce():
            self._last_rpc_context["status"] = -1
            return {}
        ggzj = self._ggzj_state()
        node_id = int(ggzj.get("node_id", 1))
        if node_id <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        cost = int(self.game_data.get("ggzj_config", {}).get("refreshUseDiamond", 20))
        if int(p.get("Diamond", 0)) < cost:
            self._last_rpc_context["status"] = -1105
            return {}
        if cost > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -cost, source=f"ggzj_refresh:{node_id}")
        ggzj["refresh_seed"] = int(ggzj.get("refresh_seed", 0)) + 1
        ggzj["pending_fight"] = None
        target_dict, _ = self._ggzj_build_target(ggzj, node_id)
        self.save()
        return {"Target": [target_dict]}

    def _build_ggzj_fight_obj(self, ggzj: dict[str, Any], node_id: int) -> dict[str, Any]:
        allies, share_fap = self._ggzj_build_ally_fight_objs(ggzj)
        target_dict, enemies = self._ggzj_build_target(ggzj, node_id)
        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        enemy_fsp = sum(int(u.get("FSP", 0)) for u in enemies if u)
        return {
            "Heros": allies + enemies,
            "TeamData": [
                {"Fsp": ally_fsp, "Fap": int(self.state["player"].get("FAP", 0)) + share_fap},
                {"Fsp": enemy_fsp, "Fap": int(target_dict.get("FAP", 0))},
            ],
            "Pets": [],
            "RandNum": random.randint(1000, 999999),
            "IsPVP": True,
        }

    def _rpc_ggzj_get_fight_before_info(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        cfg = self.game_data.get("ggzj_config", {})
        sta_cost = int(cfg.get("fightSTASuccessful", 2))
        max_try = int(cfg.get("perNodeDareNumMax", 3))
        if int(p.get("Lv", 1)) < 32 or self._ggzj_is_truce() or int(p.get("STA", 0)) < sta_cost:
            self._last_rpc_context["status"] = -1
            return {}
        ggzj = self._ggzj_state()
        node_id = int(ggzj.get("node_id", 1))
        if node_id <= 0 or int(ggzj.get("fight_count", 0)) >= max_try:
            self._last_rpc_context["status"] = -1
            return {}

        fight_obj = self._build_ggzj_fight_obj(ggzj, node_id)
        ggzj["pending_fight"] = {"node_id": node_id, "fight_obj": copy.deepcopy(fight_obj)}
        self.save()
        return {"FightInfo": {"FightObjs": [fight_obj]}}

    def _rpc_ggzj_fight(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        cfg = self.game_data.get("ggzj_config", {})
        sta_cost = int(cfg.get("fightSTASuccessful", 2))
        max_try = int(cfg.get("perNodeDareNumMax", 3))
        node_total = int(cfg.get("nodeTotal", 15))
        if int(p.get("Lv", 1)) < 32 or self._ggzj_is_truce():
            self._last_rpc_context["status"] = -1
            return {}
        ggzj = self._ggzj_state()
        node_id = int(ggzj.get("node_id", 1))
        if node_id <= 0 or int(ggzj.get("fight_count", 0)) >= max_try:
            self._last_rpc_context["status"] = -1
            return {}

        req_won = bool(data[0]) if isinstance(data, list) and len(data) > 0 else True
        verify_raw = data[1] if isinstance(data, list) and len(data) > 1 else None
        is_skip = bool(data[2]) if isinstance(data, list) and len(data) > 2 else False

        target_cs_hp: dict[str, dict[str, int]] | None = None
        if is_skip:
            pending = ggzj.get("pending_fight")
            if isinstance(pending, dict) and int(pending.get("node_id", 0)) == node_id and pending.get("fight_obj"):
                fight_obj = pending["fight_obj"]
            else:
                fight_obj = self._build_ggzj_fight_obj(ggzj, node_id)
            outcome = simulate_fight_info(
                {"FightObjs": [fight_obj]},
                self.game_data.get("attacks", {}),
                buffs_cfg=self.game_data.get("combat_buffs", {}),
            )
            hp_waves = outcome.verify_data.get("hp", [])
            last_wave = hp_waves[-1] if hp_waves else []
            target_cs_hp = {str(u["PosId"]): {"HP": int(u["HP"])} for u in last_wave if "PosId" in u}
            won = bool(outcome.won)
        else:
            if not self._verify_battle_payload(verify_raw, req_won).get("consistent", True):
                self._last_rpc_context["status"] = -1
                return {}
            won = req_won

        if won and int(p.get("STA", 0)) < sta_cost:
            self._last_rpc_context["status"] = -1
            return {}

        self._inc_stat("ggzj_count", 1)
        self._record_daily_task_progress(9, 1)

        base_res: list[dict[str, Any]] = []
        if won:
            if sta_cost > 0:
                self.ledger.apply_player_delta(p, self.profile_name, "STA", -sta_cost, source=f"ggzj_sta:{node_id}")
            self._inc_stat("ggzj_wins", 1)
            lv = max(1, int(p.get("Lv", 32)))
            vip = int(p.get("Vip", 0))
            vip_mult = int(self.game_data.get("vip_model", {}).get(str(vip), {}).get("ggzjMutipleR", 100))
            welfare_mult = self._ggzj_welfare_mult()
            base_gold = (220 + node_id * 55) * lv * welfare_mult
            stage_gold = max(1, int(base_gold * vip_mult // 100))
            tuples: list[tuple[int, int, int]] = [(1112, 0, stage_gold)]

            if node_id % 3 == 0:
                rv_tbl = self.game_data.get("ggzj_reward_view", {})
                rv_keys = sorted(rv_tbl.keys(), key=int)
                if rv_keys:
                    rv_row = rv_tbl[rv_keys[(node_id // 3 - 1) % len(rv_keys)]]
                    rv_rt = int(rv_row.get("typeID", 0))
                    rv_rm = int(rv_row.get("modelID", 0))
                    rv_num = int(rv_row.get("num", 1))
                    if rv_rt > 0 and rv_num > 0:
                        tuples.append((rv_rt, rv_rm, rv_num))

            base_res = self._grant_resources_from_tuples(
                tuples,
                source=f"ggzj_fight:{node_id}",
                tx_prefix=f"ggzj:{self.profile_name}:{ggzj.get('day', '')}:{node_id}:{uuid.uuid4()}",
            )
            ggzj["node_id"] = node_id + 1 if node_id < node_total else 0
            ggzj["fight_count"] = 0
            ggzj["refresh_seed"] = 0
        else:
            ggzj["fight_count"] = int(ggzj.get("fight_count", 0)) + 1

        ggzj["pending_fight"] = None
        self.save()
        out: dict[str, Any] = {
            "IsSuccess": "True" if won else "False",
            "BaseGetGameResourceList": base_res,
            "FightCount": int(ggzj["fight_count"]),
            "NodeId": int(ggzj["node_id"]),
        }
        if target_cs_hp is not None:
            out["TargetCsHp"] = target_cs_hp
        return out

    def _rpc_ggzj_receive_box_rewards(self, data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < 32 or self._ggzj_is_truce():
            self._last_rpc_context["status"] = -1
            return {}
        try:
            box_node_id = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}

        box_row = self.game_data.get("ggzj_box_reward", {}).get(str(box_node_id))
        if not box_row:
            self._last_rpc_context["status"] = -1
            return {}

        ggzj = self._ggzj_state()
        node_total = int(self.game_data.get("ggzj_config", {}).get("nodeTotal", 15))
        cur_node = int(ggzj.get("node_id", 1))
        cleared = node_total if cur_node == 0 else max(0, cur_node - 1)
        box_proc = int(ggzj.get("box_process", 0))
        next_box = next((b for b in sorted(int(k) for k in self.game_data.get("ggzj_box_reward", {})) if b > box_proc), 0)
        if box_node_id != next_box or cleared < box_node_id:
            self._last_rpc_context["status"] = -1
            return {}

        welfare_mult = self._ggzj_welfare_mult()
        raw_tuples = _parse_res_tuples(str(box_row.get("reward", "")))
        tuples: list[tuple[int, int, int]] = [
            (rt, rm, rn * welfare_mult if rt in (1112, 2112) else rn)
            for rt, rm, rn in raw_tuples
        ]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"ggzj_box:{box_node_id}",
            tx_prefix=f"ggzjbox:{self.profile_name}:{ggzj.get('day', '')}:{box_node_id}",
        )
        ggzj["box_process"] = box_node_id
        self.save()
        return {"BoxProcess": box_node_id, "BaseGetGameResourceList": base_res}

    def _rpc_ggzj_receive_clearance_rewards(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < 32 or self._ggzj_is_truce():
            self._last_rpc_context["status"] = -1
            return {}
        ggzj = self._ggzj_state()
        if int(ggzj.get("node_id", 1)) != 0 or bool(ggzj.get("clearance_drawn", False)):
            self._last_rpc_context["status"] = -1
            return {}
        welfare_mult = self._ggzj_welfare_mult()
        tuples = [
            (2112, 0, 1500 * welfare_mult),
            (1111, 0, 50),
            (1604, 16040004, 1),
        ]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="ggzj_clearance",
            tx_prefix=f"ggzjclear:{self.profile_name}:{ggzj.get('day', '')}",
        )
        ggzj["clearance_drawn"] = True
        self.save()
        return {"BaseGetGameResourceList": base_res}
