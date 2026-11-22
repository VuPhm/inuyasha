"""Phó Bản Ác Mộng (`Nightmare`, 65 chapters / 639 stages, ModuleSub 7200..7201)."""

from __future__ import annotations

import math
import random
import time
import uuid
from typing import Any

from combat_sim import simulate_fight_info


def interpolate_log_curve(x: float, anchors: list[tuple[float, float]]) -> float:
    """Log-linear interpolation across sorted (x, y) anchor points, clamped at ends."""
    if not anchors:
        return 1.0
    if x <= anchors[0][0]:
        return float(anchors[0][1])
    if x >= anchors[-1][0]:
        return float(anchors[-1][1])
    for i in range(len(anchors) - 1):
        x0, y0 = anchors[i]
        x1, y1 = anchors[i + 1]
        if x0 <= x <= x1:
            t = (x - x0) / max(1e-9, x1 - x0)
            return math.exp(math.log(max(1.0, y0)) * (1.0 - t) + math.log(max(1.0, y1)) * t)
    return float(anchors[-1][1])


def scale_wave_to_target_fap(
    enemies: list[dict[str, Any]],
    target_fap: float,
    boss_weight: float = 1.25,
) -> int:
    """Scale non-empty enemy units' HP/AP/DEF proportionally so wave FAP == target_fap."""
    active = [u for u in enemies if isinstance(u, dict) and u.get("HeroModelId")]
    if not active or target_fap <= 0:
        return 0
    weights: list[float] = []
    for u in active:
        q = max(1.0, float(u.get("quality", 10)))
        w = 1.0 + 0.015 * q
        if u.get("IsBoss"):
            w *= boss_weight
        weights.append(w)
    total_w = sum(weights) or float(len(active))
    for u, w in zip(active, weights):
        unit_fap = max(30.0, target_fap * (w / total_w))
        hp_base = max(1.0, float(u.get("HP", 100)))
        ap_base = max(1.0, float(u.get("AP", 10)))
        def_base = max(1.0, float(u.get("DEF", 5)))
        raw = hp_base + 10.0 * ap_base + 10.0 * def_base
        factor = unit_fap / max(1.0, raw)
        u["HP"] = max(1, int(round(hp_base * factor)))
        u["TotalHp"] = u["HP"]
        u["AP"] = max(1, int(round(ap_base * factor)))
        u["DEF"] = max(1, int(round(def_base * factor)))
    return sum(int(u["HP"] + u["AP"] * 10 + u["DEF"] * 10) for u in active)


_CAMPAIGN_FAP_ANCHORS: list[tuple[float, float]] = [
    (1.0, 8000.0),      # Ch 12
    (4.0, 16000.0),     # Ch 15
    (9.0, 32000.0),     # Ch 20
    (14.0, 48000.0),    # Ch 25 (fixes q=6 < Ch 20 q=18 inversion)
    (19.0, 65000.0),    # Ch 30 (needLV 31; 2 waves clearable by Lv31 Step+3 ~108k)
    (35.0, 135000.0),   # Ch 46 (needLV 47; fixes q=6 < Ch 32 q=15 inversion)
    (39.0, 155000.0),   # Ch 50 (needLV 51; 2 waves clearable by Lv51 Step+5 ~248k)
    (59.0, 235000.0),   # Ch 70 (needLV 71; 2 waves clearable by Lv71 Step+7 ~386k)
    (69.9, 275000.0),   # Ch 80 (needLV 80; ~3.0x pre-R7.26 90k; 3★ 2-wave ~605k -> Nightmare Ch 11 550k)
]

_NIGHTMARE_FAP_ANCHORS: list[tuple[float, float]] = [
    (0.0, 550000.0),     # NCh 11 (needLV 48)
    (9.0, 1100000.0),    # NCh 20 (needLV 52)
    (21.0, 2200000.0),   # NCh 32 (needLV 58)
    (35.0, 4200000.0),   # NCh 46 (needLV 65)
    (49.0, 7200000.0),   # NCh 60 (needLV 72)
    (64.9, 11500000.0),  # NCh 75 (needLV 80)
]


class NightmareHandlersMixin:
    """Offline server emulation for Nightmare chapters, sweeps, boxes, resets, and rankings."""

    def _default_nightmare_state(self) -> dict[str, Any]:
        return {
            "info": {
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
                "1111": self._make_node_state(1111, flag=1),
            },
        }

    def _nightmare_state(self) -> dict[str, Any]:
        nm = self.state.get("nightmare")
        if not isinstance(nm, dict):
            nm = self._default_nightmare_state()
            self.state["nightmare"] = nm
        nm.setdefault("info", {"MaxChapterId": 11, "MaxNodeId": 1111, "StarCount": 0, "HasBoss": "False", "BossId": 0})
        ch_map = nm.setdefault("chapters", {})
        if "11" not in ch_map:
            ch_map["11"] = self._make_chapter_state(11)
        node_map = nm.setdefault("nodes", {})
        if "1111" not in node_map:
            node_map["1111"] = self._make_node_state(1111, flag=1)
        return nm

    def _nightmare_chapter_node_ids(self, ch_id: int) -> list[int]:
        nodes_cfg = self.game_data.get("nightmare_nodes", {})
        return sorted(int(k) for k, v in nodes_cfg.items() if int(v.get("chapterModelID", 0)) == ch_id)

    def _sync_nightmare_node_daily(self, node_st: dict[str, Any]) -> None:
        today = self.clock.today_str()
        last_fight_date = node_st.get("FightDate")
        if not last_fight_date and int(node_st.get("FightTime", 0)) > 0:
            last_fight_date = self.clock.today_str(int(node_st["FightTime"]))
        if last_fight_date and last_fight_date != today:
            node_st["FightCount"] = 0
        node_st["FightDate"] = today
        last_reset_date = node_st.get("ResetFightDate")
        if not last_reset_date and int(node_st.get("ResetFightTime", 0)) > 0:
            last_reset_date = self.clock.today_str(int(node_st["ResetFightTime"]))
        if last_reset_date and last_reset_date != today:
            node_st["ResetFightCount"] = 0

    def _build_nightmare_wave(self, ch_id: int, node_id: int, node_cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        heroes_cfg = self.game_data["heroes"]
        ch_nodes = self._nightmare_chapter_node_ids(ch_id)
        node_pos = (ch_nodes.index(node_id) + 1) if node_id in ch_nodes else max(1, node_id % 10)
        total_nodes = max(1, len(ch_nodes))
        progress = float(ch_id - 11) + float(node_pos - 1) / float(total_nodes)
        target_fap = interpolate_log_curve(progress, _NIGHTMARE_FAP_ANCHORS)
        need_lv = int(self.game_data.get("nightmare_chapters", {}).get(str(ch_id), {}).get("needLV", 48))

        pic = str(node_cfg.get("pic", "0"))
        boss_cfg = heroes_cfg[pic] if pic != "0" and pic in heroes_cfg else heroes_cfg.get("12013005", next(iter(heroes_cfg.values())))
        mob_ids = ["12011022", "12012045", "12013043", "12012031", "12013041"]
        mob_cfgs = [heroes_cfg.get(mid, boss_cfg) for mid in mob_ids]

        enemies: list[dict[str, Any]] = [
            self._hero_fight_obj(mob_cfgs[0], lv=need_lv, is_boss=False, step=5),
            self._hero_fight_obj(boss_cfg, lv=need_lv + 2, is_boss=(pic != "0"), step=6),
            self._hero_fight_obj(mob_cfgs[1], lv=need_lv, is_boss=False, step=5),
            self._hero_fight_obj(mob_cfgs[2], lv=need_lv, is_boss=False, step=4),
            self._hero_fight_obj(mob_cfgs[3], lv=need_lv, is_boss=False, step=4),
            self._hero_fight_obj(mob_cfgs[4], lv=need_lv, is_boss=False, step=4),
        ]
        enemy_fap = scale_wave_to_target_fap(enemies, target_fap, boss_weight=1.35)
        return enemies, enemy_fap

    def _can_enter_nightmare_node(self, ch_id: int, node_id: int, check_vit: bool = True) -> tuple[bool, int]:
        ch_cfg = self.game_data.get("nightmare_chapters", {}).get(str(ch_id))
        node_cfg = self.game_data.get("nightmare_nodes", {}).get(str(node_id))
        if not ch_cfg or not node_cfg or int(node_cfg.get("chapterModelID", 0)) != ch_id:
            return False, -1
        if int(self.state["player"].get("Lv", 1)) < int(ch_cfg.get("needLV", 48)):
            return False, -1
        nm = self._nightmare_state()
        if str(ch_id) not in nm["chapters"]:
            return False, -1
        node_st = nm["nodes"].get(str(node_id))
        if not node_st or int(node_st.get("Flag", 0)) not in (1, 2):
            return False, -1
        self._sync_nightmare_node_daily(node_st)
        max_fights = int(node_cfg.get("fightNumMax", 10))
        if int(node_st.get("FightCount", 0)) >= max_fights:
            return False, -1
        if check_vit:
            vit_cost = int(self.game_data.get("nightmare_config", {}).get("perUseNum", 10))
            if int(self.state["player"].get("VIT", 0)) < vit_cost:
                return False, -1119
        return True, 0

    def _recalc_nightmare_totals(self, ch_id: int) -> dict[str, Any]:
        nm = self._nightmare_state()
        ch_st = nm["chapters"].setdefault(str(ch_id), self._make_chapter_state(ch_id))
        ch_nodes = self._nightmare_chapter_node_ids(ch_id)
        ch_st["StarCount"] = sum(int(nm["nodes"].get(str(nid), {}).get("StarCount", 0)) for nid in ch_nodes)
        nm["info"]["StarCount"] = sum(int(c.get("StarCount", 0)) for c in nm["chapters"].values())
        return ch_st

    def _unlock_next_nightmare_chapter_after(self, ch_id: int) -> dict[str, Any] | None:
        nm = self._nightmare_state()
        nchapters_cfg = self.game_data.get("nightmare_chapters", {})
        sorted_cids = sorted(int(k) for k in nchapters_cfg)
        if ch_id not in sorted_cids:
            return None
        idx = sorted_cids.index(ch_id)
        if idx + 1 >= len(sorted_cids):
            return None
        next_cid = sorted_cids[idx + 1]
        if str(next_cid) in nm["chapters"]:
            return None
        next_ch = self._make_chapter_state(next_cid)
        nm["chapters"][str(next_cid)] = next_ch
        nm["info"]["MaxChapterId"] = max(int(nm["info"].get("MaxChapterId", 11)), next_cid)
        first_nodes = self._nightmare_chapter_node_ids(next_cid)
        if first_nodes:
            fnid = first_nodes[0]
            if str(fnid) not in nm["nodes"]:
                nm["nodes"][str(fnid)] = self._make_node_state(fnid, flag=1)
            nm["info"]["MaxNodeId"] = max(int(nm["info"].get("MaxNodeId", 1111)), fnid)
        return next_ch

    def _execute_nightmare_clear(
        self,
        ch_id: int,
        node_id: int,
        surviving_allies: int,
        won: bool,
        deduct_vit: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
        nm = self._nightmare_state()
        node_cfg = self.game_data.get("nightmare_nodes", {}).get(str(node_id), {"dropGold": 860, "dropHeroExp": 430})
        nm_cfg = self.game_data.get("nightmare_config", {})
        vit_cfg = self.game_data.get("vit_config", {})
        vit_cost = int(nm_cfg.get("perUseNum", 10))
        per_exp_pct = int(vit_cfg.get("perGetEXPR", 20000))

        exp_gain = 0
        if won:
            old_lv = int(self.state["player"].get("Lv", 48))
            exp_gain = int(vit_cost * old_lv * (per_exp_pct / 10000.0))
            if deduct_vit and int(self.state["player"].get("VIT", 0)) >= vit_cost:
                self.ledger.apply_player_delta(
                    self.state["player"], self.profile_name, "VIT", -vit_cost, source=f"nightmare_vit:{node_id}"
                )

        node_st = nm["nodes"].setdefault(str(node_id), self._make_node_state(node_id, flag=1))
        self._sync_nightmare_node_daily(node_st)
        node_st["FightCount"] = int(node_st.get("FightCount", 0)) + 1
        node_st["FightTime"] = self.now_ts()
        node_st["FightDate"] = self.clock.today_str()

        if won:
            stars = max(1, min(6, int(surviving_allies)))
            node_st["StarCount"] = max(int(node_st.get("StarCount", 0)), stars)
            node_st["Flag"] = 2

        ch_nodes = self._nightmare_chapter_node_ids(ch_id)
        ch_st = self._recalc_nightmare_totals(ch_id)
        next_node: dict[str, Any] | None = None
        next_chapter: dict[str, Any] | None = None

        if won and node_id in ch_nodes:
            pos = ch_nodes.index(node_id)
            if pos + 1 < len(ch_nodes):
                next_nid = ch_nodes[pos + 1]
                existing = nm["nodes"].get(str(next_nid))
                if not existing:
                    next_node = self._make_node_state(next_nid, flag=1)
                    nm["nodes"][str(next_nid)] = next_node
                elif int(existing.get("Flag", 0)) == 0:
                    existing["Flag"] = 1
                    next_node = existing
                nm["info"]["MaxNodeId"] = max(int(nm["info"].get("MaxNodeId", 1111)), next_nid)
            else:
                ch_st["IfPass"] = 1
                next_chapter = self._unlock_next_nightmare_chapter_after(ch_id)

        reward_tuples: list[tuple[int, int, int]] = []
        if won:
            gold_gain = int(node_cfg.get("dropGold", 860))
            hero_exp_gain = int(node_cfg.get("dropHeroExp", 430))
            if exp_gain > 0:
                reward_tuples.append((1101, 0, exp_gain))
            if gold_gain > 0:
                reward_tuples.append((1112, 0, gold_gain))
            if hero_exp_gain > 0:
                reward_tuples.append((1117, 0, hero_exp_gain))
            for d in self.game_data.get("nightmare_node_drops", {}).get(str(node_id), []):
                odds = int(d.get("dropOdds", 0))
                if odds <= 0 or random.randint(1, 10000) <= odds:
                    reward_tuples.append((int(d["typeID"]), int(d["modelID"]), int(d["num"])))

        base_res = self._grant_resources_from_tuples(
            reward_tuples,
            source=f"nightmare_victory:{node_id}",
            tx_prefix=f"nightmare:{self.profile_name}:{node_id}:{uuid.uuid4()}",
        )
        old_lv, new_lv = self._sync_level_from_exp()
        if new_lv != old_lv:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True
        return ch_st, node_st, next_node, next_chapter, base_res

    # ------------------------- Nightmare RPC Handlers -------------------------

    def _rpc_nightmare_get_info(self, _data: Any) -> dict[str, Any]:
        nm = self._nightmare_state()
        chapters = sorted(nm["chapters"].values(), key=lambda c: int(c.get("ChapterModelId", 0)))
        return {
            "NightmareInfo": nm["info"],
            "BattleInfo": nm["info"],
            "ChapterList": chapters,
        }

    def _rpc_nightmare_get_node_list(self, data: Any) -> list[dict[str, Any]]:
        ch_id = int(data[0]) if isinstance(data, list) and data else 11
        nm = self._nightmare_state()
        if str(ch_id) not in nm["chapters"]:
            return []
        nodes_cfg = self.game_data.get("nightmare_nodes", {})
        ch_nodes: list[dict[str, Any]] = []
        for nid, st in sorted(nm["nodes"].items(), key=lambda kv: int(kv[0])):
            if int(nodes_cfg.get(nid, {}).get("chapterModelID", 0)) == ch_id and int(st.get("Flag", 0)) in (1, 2):
                self._sync_nightmare_node_daily(st)
                ch_nodes.append(st)
        if not ch_nodes:
            raw_ids = self._nightmare_chapter_node_ids(ch_id)
            if raw_ids:
                first = self._make_node_state(raw_ids[0], flag=1)
                nm["nodes"][str(raw_ids[0])] = first
                ch_nodes = [first]
                self.save()
        return ch_nodes

    def _rpc_nightmare_all_chapter_info(self, data: Any) -> list[dict[str, Any]]:
        raw_ids = data[0] if isinstance(data, list) and data and isinstance(data[0], list) else []
        nm = self._nightmare_state()
        out: list[dict[str, Any]] = []
        for raw_cid in raw_ids:
            try:
                cid = int(raw_cid)
            except (TypeError, ValueError):
                continue
            if str(cid) in nm["chapters"]:
                out.append({"ChapterModelId": cid, "NodeList": self._rpc_nightmare_get_node_list([cid])})
        return out

    def _rpc_nightmare_get_fight_info(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        node_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1111
        allowed, err = self._can_enter_nightmare_node(ch_id, node_id, check_vit=True)
        if not allowed:
            self._last_rpc_context["status"] = err
            return {}
        node_cfg = self.game_data.get("nightmare_nodes", {}).get(str(node_id), {"ID": node_id, "name": "1-1"})
        allies = self._build_ally_fight_objs()
        enemies, enemy_fap = self._build_nightmare_wave(ch_id, node_id, node_cfg)
        fight_obj = {
            "Heros": allies + enemies,
            "TeamData": [
                {"Fsp": sum(int(u.get("FSP", 0)) for u in allies), "Fap": int(self.state["player"].get("FAP", 0))},
                {"Fsp": sum(int(u.get("FSP", 0)) for u in enemies), "Fap": enemy_fap},
            ],
            "Pets": [],
            "RandNum": random.randint(1000, 999999),
            "IsPVP": False,
        }
        self._last_nightmare_fight = {"ch_id": ch_id, "node_id": node_id, "fight_obj": fight_obj}
        return {
            "NodeInfo": node_cfg,
            "FightInfo": {"FightObjs": [fight_obj]},
        }

    def _simulate_nightmare_skip(self, fight_obj: dict[str, Any]) -> tuple[bool, int, dict[str, dict[str, int]]]:
        outcome = simulate_fight_info(
            {"FightObjs": [fight_obj]},
            self.game_data.get("attacks", {}),
            buffs_cfg=self.game_data.get("combat_buffs", {}),
        )
        hp_waves = outcome.verify_data.get("hp", [])
        last_wave = hp_waves[-1] if hp_waves else []
        target_cs_hp = {str(u["PosId"]): {"HP": int(u["HP"])} for u in last_wave if "PosId" in u}
        surviving = outcome.ally_alive if outcome.won else 0
        return bool(outcome.won), max(0, min(6, surviving)), target_cs_hp

    def _rpc_nightmare_fight(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) > 0 else 11
        node_id = int(data[1]) if isinstance(data, list) and len(data) > 1 else 1111
        left_hero = int(data[2]) if isinstance(data, list) and len(data) > 2 else 6
        won = bool(data[3]) if isinstance(data, list) and len(data) > 3 else True
        verify_raw = data[4] if isinstance(data, list) and len(data) > 4 else None
        is_break = bool(data[5]) if isinstance(data, list) and len(data) > 5 else False

        target_cs_hp: dict[str, dict[str, int]] | None = None
        if is_break:
            cached = getattr(self, "_last_nightmare_fight", None)
            if isinstance(cached, dict) and int(cached.get("node_id", 0)) == node_id:
                won, surviving_allies, target_cs_hp = self._simulate_nightmare_skip(cached["fight_obj"])
            else:
                surviving_allies = max(1, min(6, left_hero)) if won else 0
        else:
            if not self._verify_battle_payload(verify_raw, won).get("consistent", True):
                self._last_rpc_context["status"] = -1
                return {}
            surviving_allies = max(1, min(6, left_hero)) if won else 0

        allowed, err = self._can_enter_nightmare_node(ch_id, node_id, check_vit=True)
        if not allowed:
            self._last_rpc_context["status"] = err
            return {}

        ch_st, node_st, next_node, next_chapter, base_res = self._execute_nightmare_clear(
            ch_id=ch_id,
            node_id=node_id,
            surviving_allies=surviving_allies,
            won=won,
        )
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
        if target_cs_hp is not None:
            out["TargetCsHp"] = target_cs_hp
        return out

    def _rpc_nightmare_con_fight(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) > 0 else 11
        node_id = int(data[1]) if isinstance(data, list) and len(data) > 1 else 1111
        req_count = max(1, min(10, int(data[2]) if isinstance(data, list) and len(data) > 2 else 1))

        ch_cfg = self.game_data.get("nightmare_chapters", {}).get(str(ch_id))
        node_cfg = self.game_data.get("nightmare_nodes", {}).get(str(node_id))
        nm = self._nightmare_state()
        node_st = nm["nodes"].get(str(node_id))
        if (
            not ch_cfg
            or not node_cfg
            or int(node_cfg.get("chapterModelID", 0)) != ch_id
            or int(self.state["player"].get("Lv", 1)) < int(ch_cfg.get("needLV", 48))
            or not node_st
            or int(node_st.get("Flag", 0)) != 2
            or int(node_st.get("StarCount", 0)) < 1
        ):
            self._last_rpc_context["status"] = -1
            return {}

        self._sync_nightmare_node_daily(node_st)
        nm_cfg = self.game_data.get("nightmare_config", {})
        vit_cost = max(1, int(nm_cfg.get("perUseNum", 10)))
        avail_vit = int(self.state["player"].get("VIT", 0))
        if avail_vit < vit_cost:
            self._last_rpc_context["status"] = -1119
            return {}

        max_con = max(1, int(node_cfg.get("conFightNumMax", 10)))
        rem_daily = max(0, int(node_cfg.get("fightNumMax", 10)) - int(node_st.get("FightCount", 0)))
        actual_count = min(req_count, max_con, rem_daily, avail_vit // vit_cost)
        if actual_count <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        # NightmareConfig: conFightUseResource = "1605,16050011,2" or conFightUseDiamond = 2 per run
        use_res = self._parse_res_list_safe(str(nm_cfg.get("conFightUseResource", "1605,16050011,2")))
        token_gid = int(use_res[0][1]) if use_res else 16050011
        token_per_run = int(use_res[0][2]) if use_res else 2
        token_need = token_per_run * actual_count
        owned_tokens = sum(int(g.get("Num", 0)) for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == token_gid)
        if owned_tokens >= token_need:
            self._consume_goods(token_gid, token_need)
        else:
            dia_per_run = int(nm_cfg.get("conFightUseDiamond", 2))
            dia_need = dia_per_run * actual_count
            if int(self.state["player"].get("Diamond", 0)) < dia_need:
                self._last_rpc_context["status"] = -1105
                return {}
            if dia_need > 0:
                self.ledger.apply_player_delta(
                    self.state["player"], self.profile_name, "Diamond", -dia_need, source=f"nightmare_confight:{node_id}"
                )

        stars = max(1, int(node_st.get("StarCount", 6)))
        all_bundles: list[dict[str, Any]] = []
        for _ in range(actual_count):
            _, _, _, _, base_res = self._execute_nightmare_clear(
                ch_id=ch_id,
                node_id=node_id,
                surviving_allies=stars,
                won=True,
            )
            if base_res:
                all_bundles.append(base_res[0])

        self.save()
        return {
            "NightmareInfo": nm["info"],
            "BattleInfo": nm["info"],
            "IsTriggerTrader": False,
            "BaseGetGameResourceList": all_bundles,
        }

    def _rpc_nightmare_hi_auto_fight(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) > 0 else 11
        node_id = int(data[1]) if isinstance(data, list) and len(data) > 1 else 1111
        allowed, err = self._can_enter_nightmare_node(ch_id, node_id, check_vit=True)
        if not allowed:
            self._last_rpc_context["status"] = err
            return {}

        node_cfg = self.game_data.get("nightmare_nodes", {}).get(str(node_id), {"ID": node_id, "name": "1-1"})
        allies = self._build_ally_fight_objs()
        enemies, enemy_fap = self._build_nightmare_wave(ch_id, node_id, node_cfg)
        fight_obj = {
            "Heros": allies + enemies,
            "TeamData": [
                {"Fsp": sum(int(u.get("FSP", 0)) for u in allies), "Fap": int(self.state["player"].get("FAP", 0))},
                {"Fsp": sum(int(u.get("FSP", 0)) for u in enemies), "Fap": enemy_fap},
            ],
            "Pets": [],
            "RandNum": random.randint(1000, 999999),
            "IsPVP": False,
        }
        won, surviving_allies, target_cs_hp = self._simulate_nightmare_skip(fight_obj)
        ch_st, node_st, next_node, next_chapter, base_res = self._execute_nightmare_clear(
            ch_id=ch_id,
            node_id=node_id,
            surviving_allies=surviving_allies,
            won=won,
        )
        self.save()
        out: dict[str, Any] = {
            "IsSuccess": "True" if won else "False",
            "CurrentChapter": ch_st,
            "CurrentNode": node_st,
            "NextNode": next_node,
            "TargetCsHp": target_cs_hp,
            "BaseGetGameResourceList": base_res if won else [],
        }
        if next_chapter is not None:
            out["NextChapter"] = next_chapter
        return out

    def _rpc_nightmare_reset_count(self, data: Any) -> dict[str, Any]:
        node_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1111
        nm = self._nightmare_state()
        node_st = nm["nodes"].get(str(node_id))
        if not node_st or int(node_st.get("Flag", 0)) not in (1, 2):
            self._last_rpc_context["status"] = -1
            return {}

        self._sync_nightmare_node_daily(node_st)
        next_reset = int(node_st.get("ResetFightCount", 0)) + 1
        reset_tbl = self.game_data.get("nightmare_reset_use", {})
        reset_cfg = reset_tbl.get(str(next_reset))
        if not reset_cfg:
            self._last_rpc_context["status"] = -1
            return {}

        diamond_cost = int(reset_cfg.get("nodeUseDiamond", 200))
        if int(self.state["player"].get("Diamond", 0)) < diamond_cost:
            self._last_rpc_context["status"] = -1105
            return {}
        if diamond_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -diamond_cost,
                source=f"nightmare_reset:{node_id}",
            )

        node_st["FightCount"] = 0
        node_st["ResetFightCount"] = next_reset
        node_st["ResetFightTime"] = self.now_ts()
        node_st["ResetFightDate"] = self.clock.today_str()
        self.save()
        return dict(node_st)

    def _rpc_nightmare_draw_box(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        box_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 111
        nm = self._nightmare_state()
        ch_st = nm["chapters"].get(str(ch_id))
        ch_model = self.game_data.get("nightmare_chapters", {}).get(str(ch_id), {})
        box_cfg = self.game_data.get("nightmare_chapter_boxes", {}).get(str(box_id))
        if not ch_st or not box_cfg:
            self._last_rpc_context["status"] = -1
            return {}

        matched_suffix = next(
            (s for s in ("A", "B", "C") if int(ch_model.get(f"box{s}ID", 0)) == box_id),
            None,
        )
        if not matched_suffix:
            self._last_rpc_context["status"] = -1
            return {}
        need_star = int(ch_model.get(f"box{matched_suffix}NeedStar", 0))
        if int(ch_st.get("StarCount", 0)) < need_star or ch_st.get(f"IfDrawBox{matched_suffix}") is True:
            self._last_rpc_context["status"] = -1
            return {}
        ch_st[f"IfDrawBox{matched_suffix}"] = True

        tuples = self._parse_res_list_safe(str(box_cfg.get("outputResource", "")))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"nightmare_box:{box_id}",
            tx_prefix=f"nightmare_box:{self.profile_name}:{self.state['player']['PlayerId']}:{box_id}",
        )
        self.save()
        return {"Chapter": ch_st, "BaseGetGameResourceList": base_res}

    def _rpc_nightmare_draw_road_box(self, _data: Any) -> dict[str, Any]:
        """Nightmare chapters do not have road boxes."""
        self._last_rpc_context["status"] = -1
        return {}

    def _rpc_nightmare_one_key_draw_boxs(self, data: Any) -> dict[str, Any]:
        ch_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 11
        raw_boxes = data[1] if isinstance(data, list) and len(data) >= 2 else []
        if isinstance(raw_boxes, dict):
            req_bids = [int(x) for x in (raw_boxes.get("1", []) or [])]
        elif isinstance(raw_boxes, list):
            req_bids = [int(x) for x in raw_boxes]
        else:
            req_bids = []

        nm = self._nightmare_state()
        ch_st = nm["chapters"].get(str(ch_id))
        ch_model = self.game_data.get("nightmare_chapters", {}).get(str(ch_id), {})
        if not ch_st:
            self._last_rpc_context["status"] = -1
            return {}

        tuples: list[tuple[int, int, int]] = []
        boxes_cfg = self.game_data.get("nightmare_chapter_boxes", {})
        for bid in req_bids:
            for suffix in ("A", "B", "C"):
                if int(ch_model.get(f"box{suffix}ID", 0)) == bid and not ch_st.get(f"IfDrawBox{suffix}"):
                    if int(ch_st.get("StarCount", 0)) >= int(ch_model.get(f"box{suffix}NeedStar", 0)):
                        ch_st[f"IfDrawBox{suffix}"] = True
                        bcfg = boxes_cfg.get(str(bid), {})
                        tuples.extend(self._parse_res_list_safe(str(bcfg.get("outputResource", ""))))

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"nightmare_one_key_boxes:{ch_id}",
            tx_prefix=f"nightmare_one_key_boxes:{self.profile_name}:{ch_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"Chapter": ch_st, "BaseGetGameResourceList": base_res}

    @staticmethod
    def _parse_res_list_safe(res_str: str) -> list[tuple[int, int, int]]:
        out: list[tuple[int, int, int]] = []
        for part in str(res_str).split("||"):
            segs = [s.strip() for s in part.split(",")]
            if len(segs) >= 3 and segs[0].isdigit() and segs[1].isdigit() and segs[2].isdigit():
                out.append((int(segs[0]), int(segs[1]), int(segs[2])))
        return out

    def _build_nightmare_rank_entries(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen_pids: set[str] = set()
        profiles: list[tuple[bool, Any]] = [(True, self)] + [
            (False, peer) for peer in self._get_peer_s1_profiles()
        ]
        for is_self, prof in profiles:
            p = prof.state.get("player", {})
            pid = str(p.get("PlayerId", ""))
            if not pid or pid in seen_pids:
                continue
            if not is_self and int(p.get("IsNewPlayer", 0)) != 0:
                continue
            seen_pids.add(pid)
            nm_info = prof.state.get("nightmare", {}).get("info", {})
            star_cnt = int(nm_info.get("StarCount", 0))
            head_id = self._valid_hero_head_id(int(p.get("HeadImageId", 0)), prof.state.get("slots", []))
            candidates.append(
                {
                    "Id": pid,
                    "Name": str(p.get("PlayerName", "Adventurer") or "Adventurer"),
                    "HeadImageId": head_id,
                    "StarCount": star_cnt,
                    "FAP": int(p.get("FAP", 0)),
                    "Zone": "S1 - Chiến Quốc",
                    "PVPInterLv": 0,
                    "_source": ("self",) if is_self else ("peer", pid),
                }
            )

        bot_pairs = [(st, r) for st in (5, 4, 3, 2, 1) for r in (1, 3, 5, 8, 12, 16, 20, 25, 30, 50)]
        for st, r in bot_pairs:
            bot = self._arena_bot_profile(r, st)
            pid = str(bot["PlayerId"])
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            star_cnt = max(30, min(2400, (st - 2) * 520 + max(0, 60 - r) * 6))
            head_id = self._valid_hero_head_id(0, bot["Slots"])
            candidates.append(
                {
                    "Id": pid,
                    "Name": str(bot["Name"]),
                    "HeadImageId": head_id,
                    "StarCount": star_cnt,
                    "FAP": int(bot["FAP"]),
                    "Zone": "S1 - Chiến Quốc",
                    "PVPInterLv": 0,
                    "_source": ("bot", st, r),
                }
            )

        candidates.sort(key=lambda e: (-int(e["StarCount"]), -int(e["FAP"]), e["Id"]))
        ranked = candidates[:50]
        for idx, entry in enumerate(ranked, start=1):
            entry["Rank"] = idx
        return ranked

    def _rpc_nightmare_rank_list(self, _data: Any) -> dict[str, Any]:
        entries = self._build_nightmare_rank_entries()
        public_entries = [{k: v for k, v in e.items() if k not in ("_source", "FAP")} for e in entries]
        return {"RankList": public_entries}

    def _rpc_nightmare_formation(self, data: Any) -> dict[str, Any]:
        try:
            rank = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            rank = 0
        entries = self._build_nightmare_rank_entries()
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
        return {"Formation": formation, "CombatPet": None}
