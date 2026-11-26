"""Elite Battle, SuccessTarget, Glory, Lianti, Gift Bags, Admin Helpers, LeaderBoard & PVPinter Rank handlers."""

from __future__ import annotations

from collections import Counter
import copy
import json
import math
import random
import time
from typing import Any
import uuid

from combat_sim import simulate_fight_info
from emulator_common import DEFAULT_PLAYER_STATS, EMPTY_ENTITY_ID, _parse_resource_str


class ProgressionHandlersMixin:
    """Mixin hosting Elite, SuccessTarget, Glory, Lianti, Gift, Admin, LeaderBoard & Cross-Server Rank handlers."""

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

    def _lianti_lv_exp(self, lv: int) -> int:
        return int(self.game_data.get("lianti_lv", {}).get(str(int(lv)), {}).get("lvExp", 0))

    def _lianti_max_lv(self) -> int:
        cached = getattr(self, "_cached_lianti_max_lv", None)
        if cached is not None:
            return cached
        tbl = self.game_data.get("lianti_lv", {})
        if not tbl:
            self._cached_lianti_max_lv = 81
            return 81
        max_tbl = max((int(k) for k in tbl if str(k).isdigit()), default=81)
        highest_upgradable = max((int(k) for k, v in tbl.items() if str(k).isdigit() and int(v.get("lvExp", 0)) > 0), default=-1)
        val = min(max_tbl, highest_upgradable + 1) if highest_upgradable >= 0 else 0
        self._cached_lianti_max_lv = val
        return val

    def _ensure_hero_lianti_fields(self, hero: dict[str, Any]) -> None:
        max_lv = self._lianti_max_lv()
        lv = max(0, min(max_lv, int(hero.get("LiantiLv", 0))))
        hero["LiantiLv"] = lv
        lv_exp = self._lianti_lv_exp(lv)
        if lv_exp <= 0:
            hero["LianTiNodeId"] = 5
            hero["LvUpExp"] = 100
            hero["LianTiNodeExp"] = 100
        else:
            hero["LianTiNodeId"] = max(1, min(5, int(hero.get("LianTiNodeId", 1))))
            hero["LvUpExp"] = lv_exp
            hero["LianTiNodeExp"] = max(0, min(lv_exp - 1, int(hero.get("LianTiNodeExp", 0))))
        inv = hero.get("LiantiInvested")
        if not isinstance(inv, dict):
            inv = {}
        inv.setdefault("gold", 0)
        if not isinstance(inv.get("stones"), dict):
            inv["stones"] = {}
        hero["LiantiInvested"] = inv

    def _lianti_hero_bonuses(self, hero: dict[str, Any] | None) -> dict[str, int]:
        if not hero:
            return {"HPADD": 0, "APADD": 0, "DEFADD": 0, "DAMADD": 0, "DAMCUT": 0}
        row = self.game_data.get("lianti_lv", {}).get(str(int(hero.get("LiantiLv", 0))), {})
        return {
            "HPADD": int(row.get("HPADD", 0)),
            "APADD": int(row.get("APADD", 0)),
            "DEFADD": int(row.get("DEFADD", 0)),
            "DAMADD": int(row.get("DAMADD", 0)),
            "DAMCUT": int(row.get("DAMCUT", 0)),
        }

    def _compute_lianti_dashi_step(self, heroes_by_id: dict[str, dict[str, Any]] | None = None) -> int:
        if not isinstance(getattr(self, "state", None), dict):
            return 0
        hmap = heroes_by_id if heroes_by_id is not None else {h["Id"]: h for h in self.state.get("heroes", [])}
        deployed: list[dict[str, Any]] = []
        for slot in self.state.get("slots", [])[:6]:
            hid = slot.get("HeroId")
            if hid and hid != EMPTY_ENTITY_ID and hid in hmap:
                deployed.append(hmap[hid])
        if len(deployed) < 6:
            return 0
        min_lv = min(int(h.get("LiantiLv", 0)) for h in deployed)
        best = 0
        for row in self.game_data.get("lianti_dashi", {}).values():
            step_num = int(row.get("liantiDashiStep", 0))
            need_lv = int(row.get("needLiantiLv", 999))
            if min_lv >= need_lv and step_num > best:
                best = step_num
        return best

    def _lianti_dashi_bonuses(self, heroes_by_id: dict[str, dict[str, Any]] | None = None) -> tuple[int, int, int]:
        step = self._compute_lianti_dashi_step(heroes_by_id)
        if step <= 0:
            return (0, 0, 0)
        row = self.game_data.get("lianti_dashi", {}).get(str(step), {})
        return (step, int(row.get("DAMADDR", 0)), int(row.get("DAMCUTR", 0)))

    @staticmethod
    def _lianti_stone_gold_cost(stone_row: dict[str, Any]) -> int:
        reqs = _parse_resource_str(str(stone_row.get("useConsume", "1112,0,1000")))
        return sum(qty for rtype, _mid, qty in reqs if rtype == 1112)

    def _apply_lianti_exp(self, hero: dict[str, Any], gain: int) -> None:
        max_lv = self._lianti_max_lv()
        self._ensure_hero_lianti_fields(hero)
        if self._lianti_lv_exp(hero["LiantiLv"]) <= 0 or gain <= 0:
            return
        hero["LianTiNodeExp"] = int(hero["LianTiNodeExp"]) + int(gain)
        while int(hero["LianTiNodeExp"]) >= int(hero["LvUpExp"]) and int(hero["LiantiLv"]) < max_lv:
            cur_lv_exp = self._lianti_lv_exp(hero["LiantiLv"])
            if cur_lv_exp <= 0:
                break
            hero["LianTiNodeExp"] = int(hero["LianTiNodeExp"]) - cur_lv_exp
            hero["LianTiNodeId"] = int(hero["LianTiNodeId"]) + 1
            if hero["LianTiNodeId"] > 5:
                hero["LiantiLv"] = int(hero["LiantiLv"]) + 1
                next_lv_exp = self._lianti_lv_exp(hero["LiantiLv"])
                if next_lv_exp <= 0 or hero["LiantiLv"] >= max_lv:
                    hero["LianTiNodeId"] = 5
                    hero["LvUpExp"] = 100
                    hero["LianTiNodeExp"] = 100
                    break
                hero["LianTiNodeId"] = 1
                hero["LvUpExp"] = next_lv_exp

    def _build_lianti_info(self, hero: dict[str, Any]) -> dict[str, Any]:
        return {
            "HeroId": hero["Id"],
            "LiantiLv": int(hero["LiantiLv"]),
            "LvUpExp": int(hero["LvUpExp"]),
            "LianTiNodeExp": int(hero["LianTiNodeExp"]),
            "LianTiNodeId": int(hero["LianTiNodeId"]),
        }

    def _consume_goods_multi(self, goods_model_id: int, count: int) -> bool:
        rem = int(count)
        if rem <= 0:
            return True
        avail = sum(
            int(g.get("Num", 0))
            for g in self.state.get("goods", [])
            if int(g.get("GoodsModelId", 0)) == goods_model_id
        )
        if avail < rem:
            return False
        for g in list(self.state.get("goods", [])):
            if int(g.get("GoodsModelId", 0)) != goods_model_id:
                continue
            cur = int(g.get("Num", 0))
            if cur <= 0:
                continue
            take = min(cur, rem)
            g["Num"] = cur - take
            rem -= take
            if g["Num"] <= 0:
                self.state["goods"].remove(g)
            if rem <= 0:
                break
        self._mark_goods_changed(goods_model_id)
        return True

    def _lianti_commit(
        self, hero: dict[str, Any], stones_used: Counter[int], gold_spent: int, source: str
    ) -> dict[str, Any]:
        player = self.state["player"]
        for gid, qty in stones_used.items():
            if qty > 0:
                self._consume_goods_multi(gid, qty)
                stones_inv = hero["LiantiInvested"].setdefault("stones", {})
                stones_inv[str(gid)] = int(stones_inv.get(str(gid), 0)) + int(qty)
        if gold_spent > 0:
            self.ledger.apply_player_delta(
                player,
                self.profile_name,
                "Gold",
                -gold_spent,
                source=source,
            )
            hero["LiantiInvested"]["gold"] = int(hero["LiantiInvested"].get("gold", 0)) + int(gold_spent)
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"LiantiInfo": self._build_lianti_info(hero)}

    def _lianti_validate_hero_and_open(self, hero_id: str) -> dict[str, Any] | None:
        open_lv = int(self.game_data.get("module_subs", {}).get("5700", {}).get("openLv", 34))
        if int(self.state["player"].get("Lv", 1)) < open_lv:
            self._last_rpc_context["status"] = -1
            return None
        hero = next((h for h in self.state.get("heroes", []) if str(h.get("Id")) == hero_id), None)
        if not hero:
            self._last_rpc_context["status"] = -1
            return None
        self._ensure_hero_lianti_fields(hero)
        if self._lianti_lv_exp(hero["LiantiLv"]) <= 0:
            self._last_rpc_context["status"] = -1
            return None
        return hero

    def _rpc_lianti_upgrade(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        hero = self._lianti_validate_hero_and_open(str(data[0]))
        if not hero:
            return {}
        try:
            gid = int(data[1])
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        stone_row = self.game_data.get("lianti_stone_exp", {}).get(str(gid))
        if not stone_row:
            self._last_rpc_context["status"] = -1
            return {}
        gold_cost = self._lianti_stone_gold_cost(stone_row)
        avail = sum(
            int(g.get("Num", 0)) for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == gid
        )
        if avail < 1 or int(self.state["player"].get("Gold", 0)) < gold_cost:
            self._last_rpc_context["status"] = -1
            return {}
        gain = random.randint(int(stone_row.get("expMin", 5)), int(stone_row.get("expMax", 15)))
        self._apply_lianti_exp(hero, gain)
        return self._lianti_commit(hero, Counter({gid: 1}), gold_cost, source=f"lianti:{gid}")

    def _rpc_lianti_one_key(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 3 or not isinstance(data[2], list):
            self._last_rpc_context["status"] = -1
            return {}
        hero = self._lianti_validate_hero_and_open(str(data[0]))
        if not hero:
            return {}
        try:
            gid = int(data[1])
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        stone_row = self.game_data.get("lianti_stone_exp", {}).get(str(gid))
        if not stone_row or not data[2]:
            self._last_rpc_context["status"] = -1
            return {}
        exp_min = int(stone_row.get("expMin", 5))
        exp_max = int(stone_row.get("expMax", 15))
        gold_cost = self._lianti_stone_gold_cost(stone_row)
        avail = sum(
            int(g.get("Num", 0)) for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == gid
        )
        rem_gold = int(self.state["player"].get("Gold", 0))
        used = 0
        total_gold = 0
        for raw_exp in data[2]:
            if self._lianti_lv_exp(hero["LiantiLv"]) <= 0 or avail < 1 or rem_gold < gold_cost:
                break
            try:
                gain = max(exp_min, min(exp_max, int(raw_exp)))
            except (TypeError, ValueError):
                gain = exp_min
            avail -= 1
            rem_gold -= gold_cost
            used += 1
            total_gold += gold_cost
            self._apply_lianti_exp(hero, gain)
        if used <= 0:
            self._last_rpc_context["status"] = -1
            return {}
        return self._lianti_commit(hero, Counter({gid: used}), total_gold, source=f"lianti_one_key:{gid}x{used}")

    def _rpc_lianti_one_key_five_lv(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            self._last_rpc_context["status"] = -1
            return {}
        hero = self._lianti_validate_hero_and_open(str(data[0]))
        if not hero:
            return {}
        target_lv = min(self._lianti_max_lv(), int(hero["LiantiLv"]) + 5)
        stone_rows = sorted(
            self.game_data.get("lianti_stone_exp", {}).values(),
            key=lambda r: int(r.get("expMax", 0)),
            reverse=True,
        )
        qty_by_gid: dict[int, int] = {}
        for g in self.state.get("goods", []):
            mid = int(g.get("GoodsModelId", 0))
            if str(mid) in self.game_data.get("lianti_stone_exp", {}):
                qty_by_gid[mid] = qty_by_gid.get(mid, 0) + int(g.get("Num", 0))
        rem_gold = int(self.state["player"].get("Gold", 0))
        stones_used: Counter[int] = Counter()
        total_gold = 0
        while int(hero["LiantiLv"]) < target_lv and self._lianti_lv_exp(hero["LiantiLv"]) > 0:
            picked = None
            for row in stone_rows:
                gid = int(row["goodsModelId"])
                gcost = self._lianti_stone_gold_cost(row)
                if qty_by_gid.get(gid, 0) >= 1 and rem_gold >= gcost:
                    picked = (row, gid, gcost)
                    break
            if not picked:
                break
            row, gid, gcost = picked
            qty_by_gid[gid] -= 1
            rem_gold -= gcost
            stones_used[gid] += 1
            total_gold += gcost
            gain = random.randint(int(row.get("expMin", 5)), int(row.get("expMax", 15)))
            self._apply_lianti_exp(hero, gain)
        if not stones_used:
            self._last_rpc_context["status"] = -1
            return {}
        return self._lianti_commit(hero, stones_used, total_gold, source=f"lianti_five:{hero['HeroModelId']}")

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
        profiles: list[tuple[bool, Any]] = [(True, self)] + [
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

        profiles: list[tuple[bool, Any]] = [(True, self)] + [
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
            pvp_inter = prof.state.get("pvpinter", {})
            pi_lv = max(1, min(8, int(pvp_inter.get("lv", 1) or int(p.get("PVPInterLv", 1) or 1))))
            pi_rate = int(pvp_inter.get("rate", int(p.get("Lv", 1)) * 10))
            pi_tot = int(pvp_inter.get("total_fights", 0))
            pi_wins = int(pvp_inter.get("win_count", 0))
            pi_wr = int(round(100 * pi_wins / pi_tot)) if pi_tot > 0 else 100
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
                    "PVPInterLv": pi_lv,
                    "Rate": pi_rate,
                    "WinRate": pi_wr,
                }
            )

        for st in self._LEADERBOARD_BOT_STEPS:
            for r in self._LEADERBOARD_BOT_RANKS:
                bot = self._arena_bot_profile(r, st)
                bot_id = f"cs-bot:{st}:{r}"
                srv_name = self._CROSS_SERVER_NAMES[(st + r) % len(self._CROSS_SERVER_NAMES)]
                bot_dan = min(8, max(1, st + (3 if r <= 3 else (2 if r <= 12 else 1))))
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
                        "PVPInterLv": bot_dan,
                        "Rate": max(100, bot_dan * 120 + max(0, 60 - r)),
                        "WinRate": max(55, min(95, 92 - r // 2)),
                    }
                )

        candidates.sort(key=lambda e: (-int(e["FAP"]), -int(e["Lv"]), str(e["Id"])))
        ranked = candidates[:rank_num]
        for idx, entry in enumerate(ranked, start=1):
            entry["Rank"] = idx
        return ranked

    def _rpc_pvpinter_top_rank(self, data: Any) -> dict[str, Any]:
        """Return cross-server Top-50 ranking for RankScene Tab 3 & CrossServerRankLayer."""
        page = int(data[0]) if isinstance(data, list) and data and data[0] is not None else 0
        if page > 0:
            return {"TotalPage": 0, "PVPinterTopRank": []}
        return {"TotalPage": 0, "PVPinterTopRank": self._build_cross_server_rank_entries()}

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
