#!/usr/bin/env python3
"""Event & Activity RPC handlers (R7.5) wired into ProfileStore via EventHandlersMixin."""

from __future__ import annotations

import copy
import json
import math
import random
import uuid
from typing import Any

from combat_sim import simulate_fight_info
from event_runtime import STATUS_ACTIVE, STATUS_ENDED


def _parse_res_tuples(raw: str) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for chunk in str(raw or "").split("||"):
        parts = [p.strip() for p in chunk.split(",")]
        if len(parts) >= 3 and parts[0].lstrip("-").isdigit() and parts[1].lstrip("-").isdigit() and parts[2].lstrip("-").isdigit():
            rt, rm, rn = int(parts[0]), int(parts[1]), int(parts[2])
            if rn > 0:
                out.append((rt, rm, rn))
    return out


class EventHandlersMixin:
    """Mixin adding R7.5 restored activities and Event Archive integration to ProfileStore."""

    # -------------------- Shared Sync, Archive & RewardCenter (2400) --------------------

    def _sync_events(self) -> None:
        """Advance/archive ended timed events and settle end-of-period rewards once."""
        self.event_runtime.check_and_finalize_ended_timed(on_ended=self._on_timed_event_ended)

    def _on_timed_event_ended(self, inst: dict[str, Any]) -> None:
        event_id = str(inst.get("event_id", ""))
        if event_id.startswith("timed_recruit:"):
            self._settle_timed_recruit_rank(inst)

    def _active_reward_center_entries(self) -> list[dict[str, Any]]:
        now = self.now_ts()
        items = self.state.setdefault("rewards_center", [])
        return [
            row
            for row in items
            if not row.get("Claimed", False) and (int(row.get("ExpireTime", 0)) == 0 or int(row.get("ExpireTime", 0)) > now)
        ]

    def _push_reward_center_entry(
        self,
        *,
        source_key: str,
        title: str,
        content: str,
        res_tuples: list[tuple[int, int, int]],
        expire_sec: int = 7 * 86400,
    ) -> dict[str, Any] | None:
        if not res_tuples:
            return None
        items = self.state.setdefault("rewards_center", [])
        existing = next((r for r in items if r.get("SourceKey") == source_key), None)
        if existing is not None:
            return existing
        now = self.now_ts()
        entry = {
            "Id": str(uuid.uuid4()),
            "SourceKey": source_key,
            "Title": title,
            "Content": content,
            "SendTime": now,
            "ExpireTime": now + max(60, int(expire_sec)),
            "ResourceList": [
                {"ResourceTypeSub": int(rt), "ModelId": int(rm), "Count": int(rn)}
                for rt, rm, rn in res_tuples
                if int(rn) > 0
            ],
            "Claimed": False,
        }
        items.append(entry)
        return entry

    def _rpc_reward_rewars(self, _data: Any) -> list[dict[str, Any]]:
        self._sync_events()
        out: list[dict[str, Any]] = []
        for row in self._active_reward_center_entries():
            out.append(
                {
                    "Id": row["Id"],
                    "Title": row["Title"],
                    "Content": row["Content"],
                    "SendTime": int(row["SendTime"]),
                    "ExpireTime": int(row["ExpireTime"]),
                    "ResourceList": copy.deepcopy(row["ResourceList"]),
                }
            )
        return out

    def _rpc_reward_draw_gift_bags(self, data: Any) -> dict[str, Any]:
        self._sync_events()
        raw_ids = data[0] if isinstance(data, list) and data else []
        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids] if raw_ids else []
        req_ids = {str(x) for x in raw_ids if x}
        if not req_ids:
            self._last_rpc_context["status"] = -1
            return {}

        now = self.now_ts()
        items = self.state.setdefault("rewards_center", [])
        to_claim = [
            row
            for row in items
            if str(row.get("Id")) in req_ids
            and not row.get("Claimed", False)
            and (int(row.get("ExpireTime", 0)) == 0 or int(row.get("ExpireTime", 0)) > now)
        ]
        if not to_claim:
            self._last_rpc_context["status"] = -1
            return {}

        tuples: list[tuple[int, int, int]] = []
        for row in to_claim:
            row["Claimed"] = True
            row["ClaimedAt"] = now
            for r in row.get("ResourceList", []):
                tuples.append((int(r["ResourceTypeSub"]), int(r["ModelId"]), int(r["Count"])))

        old_lv = int(self.state["player"]["Lv"])
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="reward_center",
            tx_prefix=f"rc:{self.profile_name}:{'_'.join(sorted(req_ids))}",
        )
        old_lv2, new_lv2 = self._sync_level_from_exp()
        if new_lv2 != old_lv2 or new_lv2 != old_lv:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True
            self._recalc_all_slots_and_fap()
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _build_timed_activity_open_info(self) -> dict[str, list[dict[str, Any]]]:
        """Build Avatar.TimedActivityOpenInfo strictly from active EventRuntime timed events."""
        p = self.state["player"]
        active_tr = self.event_runtime.get_active_timed_events(9300, p)
        if not active_tr:
            return {}
        ev_def, ev = active_tr[0]
        act_id = int(ev_def.metadata.get("activity_id", 81))
        return {
            "9300": [
                {
                    "ActivityId": act_id,
                    "Name": ev_def.name,
                    "EndDate": int(ev.end_at_ts() if hasattr(ev, "end_at_ts") else (ev.end_ts or 0)),
                    "Xssx": 1,
                    "ExtraInfo": {"ActivityEnumId": act_id},
                }
            ]
        }

    # -------------------- Activity 1a: PlayerVIT Dinner Windows (2706) --------------------

    def _dinner_red_dot(self) -> int:
        ev = self.event_runtime.evaluate("daily_dinner", self.state["player"])
        if not ev.eligible or ev.active_window_idx is None or not ev.instance_id:
            return 0
        if self.event_runtime.is_claimed(ev.instance_id, f"win:{ev.active_window_idx}"):
            return 0
        return 1

    def _rpc_player_vit_receive_vit(self, _data: Any) -> dict[str, Any]:
        ev = self.event_runtime.evaluate("daily_dinner", self.state["player"])
        if not ev.eligible or ev.active_window_idx is None:
            self._last_rpc_context["status"] = -1
            return {}

        vit_cfg = self.game_data.get("vit_config", {})
        tuples = _parse_res_tuples(str(vit_cfg.get("dinnerSubstance", "1102,0,50||1103,0,20")))
        if not tuples:
            tuples = [(1102, 0, 50), (1103, 0, 20)]

        mkey = f"win:{ev.active_window_idx}"
        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "daily_dinner",
            mkey,
            lambda idem: self._grant_resources_from_tuples(
                tuples,
                source=f"daily_dinner:{ev.active_window_idx}",
                tx_prefix=idem,
            ),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # -------------------- Activity 1b: DailyTaskInfo (3000) --------------------

    def _ensure_daily_task_progress(self) -> tuple[Any, dict[str, Any]]:
        ev = self.event_runtime.evaluate("daily_task", self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        assert inst is not None
        prog = inst.setdefault("progress", {})
        prog.setdefault("tasks", {})
        prog.setdefault("total_credit", 0)
        return ev, prog

    def _daily_task_open_lv(self, module_id: int) -> int:
        ms = self.game_data.get("module_subs", {}).get(str(module_id), {})
        return int(ms.get("openLv", 1) or 1)

    def _record_daily_task_progress(self, task_id: int, delta: int = 1) -> None:
        if delta <= 0:
            return
        row = self.game_data.get("dailytask_model", {}).get(str(task_id))
        if not row:
            return
        player_lv = int(self.state.get("player", {}).get("Lv", 1))
        need_mod_lv = self._daily_task_open_lv(int(row.get("moduleID", 2201)))
        if player_lv < need_mod_lv:
            return
        ev, prog = self._ensure_daily_task_progress()
        if ev.status != STATUS_ACTIVE:
            return
        tasks = prog["tasks"]
        t_entry = tasks.setdefault(str(task_id), {"num": 0, "credit_claimed": False})
        loop_num = max(1, int(row.get("loopNum", 1)))
        t_entry["num"] = min(loop_num, int(t_entry.get("num", 0)) + int(delta))

    def _daily_task_red_dot(self) -> int:
        if int(self.state.get("player", {}).get("Lv", 1)) < self._daily_task_open_lv(3000):
            return 0
        payload = self._build_daily_task_payload()
        has_task = any(bool(t.get("CanDrawCredit")) for t in payload.get("TasksInfo", []))
        has_chest = any(int(r.get("Status", 0)) == 1 for r in payload.get("RewardInfo", []))
        return 1 if (has_task or has_chest) else 0

    def _build_daily_task_payload(self) -> dict[str, Any]:
        ev, prog = self._ensure_daily_task_progress()
        tasks_cfg = self.game_data.get("dailytask_model", {})
        rewards_cfg = self.game_data.get("dailytask_reward", {})
        tasks_map = prog["tasks"]
        total_credit = int(prog.get("total_credit", 0))

        tasks_out: list[dict[str, Any]] = []
        for tid_str in sorted(tasks_cfg, key=lambda k: int(k)):
            row = tasks_cfg[tid_str]
            tid = int(row["ID"])
            loop_num = max(1, int(row.get("loopNum", 1)))
            st = tasks_map.get(tid_str, {})
            num = min(loop_num, int(st.get("num", 0)))
            claimed = bool(st.get("credit_claimed", False))
            completed = num >= loop_num
            tasks_out.append(
                {
                    "Id": tid,
                    "Num": num,
                    "Status": 1 if completed else 0,
                    "CanDrawCredit": bool(completed and not claimed),
                }
            )

        reward_out: list[dict[str, Any]] = []
        for cid_str in sorted(rewards_cfg, key=lambda k: int(k)):
            need_c = int(rewards_cfg[cid_str]["needCredit"])
            already = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"chest:{need_c}"))
            if already:
                status = 2
            elif total_credit >= need_c:
                status = 1
            else:
                status = 0
            reward_out.append({"NeedCredit": need_c, "Status": status})

        return {
            "TasksInfo": tasks_out,
            "TotalCredit": total_credit,
            "RewardInfo": reward_out,
        }

    def _rpc_daily_task_get_info(self, _data: Any) -> dict[str, Any]:
        ev = self.event_runtime.evaluate("daily_task", self.state["player"])
        if not ev.unlocked:
            self._last_rpc_context["status"] = -1
            return {}
        out = self._build_daily_task_payload()
        self.save()
        return out

    def _rpc_daily_task_get_credit(self, data: Any) -> dict[str, Any]:
        tid = int(data[0]) if isinstance(data, list) and data else 0
        row = self.game_data.get("dailytask_model", {}).get(str(tid))
        ev, prog = self._ensure_daily_task_progress()
        if not row or not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}

        loop_num = max(1, int(row.get("loopNum", 1)))
        t_entry = prog["tasks"].setdefault(str(tid), {"num": 0, "credit_claimed": False})
        if int(t_entry.get("num", 0)) < loop_num or t_entry.get("credit_claimed", False):
            self._last_rpc_context["status"] = -1
            return {}

        gold_gain = max(0, int(row.get("goldFactor", 0))) * int(self.state["player"].get("Lv", 1))
        tuples = [(1112, 0, gold_gain)] if gold_gain > 0 else []

        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "daily_task",
            f"task:{tid}",
            lambda idem: self._grant_resources_from_tuples(tuples, source=f"daily_task:{tid}", tx_prefix=idem) if tuples else [],
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}

        t_entry["credit_claimed"] = True
        prog["total_credit"] = int(prog.get("total_credit", 0)) + int(row.get("outputCredit", 0))
        self.save()
        payload = self._build_daily_task_payload()
        if base_res:
            payload["BaseGetGameResourceList"] = base_res
        return payload

    def _rpc_daily_task_draw_reward(self, data: Any) -> dict[str, Any]:
        need_credit = int(data[0]) if isinstance(data, list) and data else 0
        chest_row = self.game_data.get("dailytask_reward", {}).get(str(need_credit))
        ev, prog = self._ensure_daily_task_progress()
        if not chest_row or not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        if int(prog.get("total_credit", 0)) < need_credit:
            self._last_rpc_context["status"] = -1
            return {}

        p = self.state["player"]
        cur_lv = int(p.get("Lv", 1))
        if cur_lv < int(chest_row.get("needLV", 1)):
            self._last_rpc_context["status"] = -1
            return {}

        exp_tbl = self.game_data.get("dailytask_exp", {})
        exp_row = exp_tbl.get(str(cur_lv))
        if not exp_row and exp_tbl:
            exp_row = exp_tbl[str(max(int(k) for k in exp_tbl))]
        base_exp = int((exp_row or {}).get("baseEXP", 0))
        exp_gain = base_exp * int(chest_row.get("playerEXPFactor", 0))
        gold_gain = int(chest_row.get("goldFactor", 0)) * cur_lv

        tuples = _parse_res_tuples(str(chest_row.get("resourceList", "")))
        if exp_gain > 0:
            tuples.append((1101, 0, exp_gain))
        if gold_gain > 0:
            tuples.append((1112, 0, gold_gain))

        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "daily_task",
            f"chest:{need_credit}",
            lambda idem: self._grant_resources_from_tuples(
                tuples,
                source=f"daily_task_chest:{need_credit}",
                tx_prefix=idem,
            ),
            player=p,
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}

        old_lv, new_lv = self._sync_level_from_exp()
        if new_lv != old_lv:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True
            self._recalc_all_slots_and_fap()
        self.save()
        payload = self._build_daily_task_payload()
        payload["BaseGetGameResourceList"] = base_res
        return payload

    def _rpc_daily_task_one_key_done(self, data: Any) -> dict[str, Any]:
        tid = int(data[0]) if isinstance(data, list) and data else 0
        row = self.game_data.get("dailytask_model", {}).get(str(tid))
        ev, prog = self._ensure_daily_task_progress()
        if not row or not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        if int(self.state["player"].get("Lv", 1)) < self._daily_task_open_lv(int(row.get("moduleID", 2201))):
            self._last_rpc_context["status"] = -1
            return {}

        loop_num = max(1, int(row.get("loopNum", 1)))
        t_entry = prog["tasks"].setdefault(str(tid), {"num": 0, "credit_claimed": False})
        if int(t_entry.get("num", 0)) >= loop_num:
            self._last_rpc_context["status"] = -1
            return {}

        cost_tuples = _parse_res_tuples(str(row.get("oneKeySingleTask", "1111,0,10")))
        dia_cost = sum(rn for rt, _rm, rn in cost_tuples if rt == 1111)
        if int(self.state["player"].get("Diamond", 0)) < dia_cost:
            self._last_rpc_context["status"] = -1
            return {}
        if dia_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -dia_cost,
                source=f"daily_task_one_key:{tid}",
            )
        t_entry["num"] = loop_num
        self.save()
        return self._build_daily_task_payload()

    def _rpc_daily_task_one_key_all_done(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_daily_task_progress()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        player_lv = int(self.state["player"].get("Lv", 1))
        tasks_cfg = self.game_data.get("dailytask_model", {})

        pending: list[dict[str, Any]] = []
        for tid_str, row in tasks_cfg.items():
            if player_lv < self._daily_task_open_lv(int(row.get("moduleID", 2201))):
                continue
            loop_num = max(1, int(row.get("loopNum", 1)))
            t_entry = prog["tasks"].get(tid_str, {})
            if int(t_entry.get("num", 0)) < loop_num:
                pending.append(row)
        if not pending:
            self._last_rpc_context["status"] = -1
            return {}

        dt_cfg = self.game_data.get("dailytask_config", {})
        cost_tuples = _parse_res_tuples(str(dt_cfg.get("oneKeyAllDaliyTask", "1111,0,200")))
        dia_cost = sum(rn for rt, _rm, rn in cost_tuples if rt == 1111)
        if int(self.state["player"].get("Diamond", 0)) < dia_cost:
            self._last_rpc_context["status"] = -1
            return {}
        if dia_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -dia_cost,
                source="daily_task_one_key_all",
            )
        for row in pending:
            tid_str = str(row["ID"])
            t_entry = prog["tasks"].setdefault(tid_str, {"num": 0, "credit_claimed": False})
            t_entry["num"] = max(1, int(row.get("loopNum", 1)))
        self.save()
        return self._build_daily_task_payload()

    # -------------------- Activity 2: TimedRecruitInfo (9300, Banners 81 & 82) --------------------

    def _timed_recruit_active(self) -> tuple[Any, Any] | tuple[None, None]:
        self._sync_events()
        active = self.event_runtime.get_active_timed_events(9300, self.state["player"])
        if not active:
            return None, None
        return active[0]

    def _ensure_timed_recruit_prog(self, act_id: int, instance_id: str) -> dict[str, Any]:
        inst = self.event_runtime.get_instance(instance_id)
        assert inst is not None
        prog = inst.setdefault("progress", {})
        cfg = self.game_data.get("timed_recruit_model", {}).get(str(act_id), {})
        prog.setdefault("activity_enum_id", int(act_id))
        prog.setdefault("my_credit", 0)
        prog.setdefault("pull_count", 0)
        prog.setdefault("out_zi_count", int(cfg.get("outputHighHeroIntervalNum", 9)))
        prog.setdefault("cooled_time", 0)
        prog.setdefault("bless_num", 0)
        prog.setdefault("bless_r", float(cfg.get("firstBlessR", 0.7)))
        prog.setdefault("bless_unlocked", False)
        prog.setdefault("pending_gold_hero", False)
        prog.setdefault("draw_credit_rewards", [])
        prog.setdefault("ur_grant_seq", 0)
        prog.setdefault("history", [])
        return prog

    def _timed_recruit_synthetic_peers(self, act_id: int, instance_id: str) -> list[dict[str, Any]]:
        """Deterministic synthetic NPC leaderboard peers per event instance (modeled)."""
        rng = random.Random(f"tr_peers:{instance_id}:{act_id}")
        npc_names = [
            "PhongKhuyển", "BạchSát", "TửVu", "HắcCửu", "KhuyểnDạXoa",
            "NgọcTứHồn", "MinhĐạoTàn", "ThiếtToáiNha", "ThiênSinhNha", "BấtYêuVương",
            "XíchNguyệt", "ĐoạnKiếm", "LôiThú", "DạMaLâm", "BăngTinh",
            "ThanhLongẨn", "PhongHuyệt", "TửTâm", "NgânLang", "HồngLiên",
            "TuyếtNữ", "ThầnLạc", "CànThú", "HoàngTuyền", "KỳLânẨn",
        ]
        # Clean stepped distribution from ~1800 down to 510 so Rank 1 is competitively reachable
        base_scores = sorted([510 + idx * 52 + rng.randint(0, 20) for idx in range(len(npc_names))], reverse=True)
        return [
            {"PlayerName": name, "Credit": score, "is_player": False}
            for name, score in zip(npc_names, base_scores)
        ]

    def _timed_recruit_rank_and_list(self, act_id: int, instance_id: str, my_credit: int) -> tuple[int, list[dict[str, Any]]]:
        cfg = self.game_data.get("timed_recruit_model", {}).get(str(act_id), {})
        limit_num = int(cfg.get("limitNum", 500))
        player_name = str(self.state["player"].get("PlayerName", "Hero"))
        entries = self._timed_recruit_synthetic_peers(act_id, instance_id)
        if my_credit >= limit_num:
            entries.append({"PlayerName": player_name, "Credit": int(my_credit), "is_player": True})
        entries.sort(key=lambda r: (-int(r["Credit"]), 0 if r["is_player"] else 1, r["PlayerName"]))

        rank_list: list[dict[str, Any]] = []
        my_rank = 0
        for idx, row in enumerate(entries[:50], start=1):
            if row["is_player"]:
                my_rank = idx
            rank_list.append({"Rank": idx, "PlayerName": row["PlayerName"], "Credit": int(row["Credit"])})
        return my_rank, rank_list

    def _settle_timed_recruit_rank(self, inst: dict[str, Any]) -> None:
        prog = inst.get("progress", {})
        act_id = int(prog.get("activity_enum_id") or str(inst.get("event_id", "0")).split(":")[-1] or 81)
        my_credit = int(prog.get("my_credit", 0))
        iid = str(inst["instance_id"])
        my_rank, _ = self._timed_recruit_rank_and_list(act_id, iid, my_credit)
        if my_rank <= 0:
            return
        rank_rows = self.game_data.get("timed_recruit_rank", {}).get(str(act_id), [])
        matched = next(
            (r for r in rank_rows if int(r.get("rankMin", 999)) <= my_rank <= int(r.get("rankMax", 0))),
            None,
        )
        if not matched:
            return
        tuples = _parse_res_tuples(str(matched.get("resourceList", "")))
        if not tuples:
            return
        self._push_reward_center_entry(
            source_key=f"tr_rank:{iid}",
            title=f"Xếp Hạng Chiêu Mộ Thần Tướng (#{my_rank})",
            content=f"Chúc mừng đạt hạng {my_rank} ({my_credit} điểm) kỳ {iid}!",
            res_tuples=tuples,
        )

    def _timed_recruit_red_dot(self) -> int:
        ev_def, ev = self._timed_recruit_active()
        if not ev_def or not ev or not ev.instance_id:
            return 0
        act_id = int(ev_def.metadata.get("activity_id", 81))
        prog = self._ensure_timed_recruit_prog(act_id, ev.instance_id)
        now = self.now_ts()
        if now >= int(prog.get("cooled_time", 0)):
            return 1
        if prog.get("pending_gold_hero"):
            return 1
        claimed = set(int(x) for x in prog.get("draw_credit_rewards", []))
        thresholds = sorted(
            int(r["needCredit"])
            for r in self.game_data.get("timed_recruit_credit", {}).values()
            if int(r.get("activityEnumID", 0)) == act_id
        )
        next_t = next((t for t in thresholds if t not in claimed), None)
        if next_t is not None and int(prog.get("my_credit", 0)) >= next_t:
            return 1
        return 0

    def _build_timed_recruit_snapshot(self, ev_def: Any, ev: Any) -> dict[str, Any]:
        act_id = int(ev_def.metadata.get("activity_id", 81))
        prog = self._ensure_timed_recruit_prog(act_id, ev.instance_id)
        my_credit = int(prog.get("my_credit", 0))
        my_rank, rank_list = self._timed_recruit_rank_and_list(act_id, ev.instance_id, my_credit)
        draw_credits = sorted(int(x) for x in prog.get("draw_credit_rewards", []))
        return {
            "ActivityEnumId": act_id,
            "MyRank": my_rank,
            "MyCredit": my_credit,
            "OutputHighHeroIntervalNum": int(prog.get("out_zi_count", 9)),
            "RankList": rank_list,
            "DrawStatus": 1 if draw_credits else 0,
            "DrawCreditRewards": ",".join(str(x) for x in draw_credits),
            "EndTime": int(ev.end_ts or 0),
            "CooledTime": int(prog.get("cooled_time", 0)),
            "BlessNum": int(prog.get("bless_num", 0)),
            "BlessR": float(prog.get("bless_r", 0.7)),
            "DrawGoldHero": 0 if prog.get("pending_gold_hero") else 1,
        }

    def _rpc_timed_recruit_get_info(self, _data: Any) -> dict[str, Any]:
        ev_def, ev = self._timed_recruit_active()
        if not ev_def or not ev or not ev.eligible or not ev.instance_id:
            self._last_rpc_context["status"] = -1
            return {}
        snap = self._build_timed_recruit_snapshot(ev_def, ev)
        self.save()
        return snap

    def _pick_timed_recruit_non_ur_hero(self, low_r: int, *, force_orange: bool = False) -> int:
        heroes_cfg = self.game_data.get("heroes", {})
        rec3_all = self.game_data.get("hero_recruit", {}).get("3", {}).get("outShowAll", "")
        pool_ids = [int(x) for x in str(rec3_all).split(",") if x.strip().isdigit()]
        if not pool_ids:
            pool_ids = [int(k) for k, h in heroes_cfg.items() if int(h.get("quality", 0)) in (10, 13, 15)]
        by_q: dict[int, list[int]] = {10: [], 13: [], 15: []}
        for hid in pool_ids:
            q = int(heroes_cfg.get(str(hid), {}).get("quality", 0))
            if q in by_q:
                by_q[q].append(hid)
        if not by_q[15]:
            by_q[15] = [int(k) for k, h in heroes_cfg.items() if int(h.get("quality", 0)) == 15][:10]
        if not by_q[13]:
            by_q[13] = [int(k) for k, h in heroes_cfg.items() if int(h.get("quality", 0)) == 13][:10]
        if not by_q[10]:
            by_q[10] = [int(k) for k, h in heroes_cfg.items() if int(h.get("quality", 0)) == 10][:10]

        if force_orange:
            return random.choice(by_q[15])
        roll = random.randint(1, 10000)
        if roll <= max(1, min(9500, low_r)):
            return random.choice(by_q[10])
        # Remaining split ~75% Purple (q=13), ~25% Orange (q=15) [server-modeled]
        return random.choice(by_q[13] if random.randint(1, 100) <= 75 else by_q[15])

    def _rpc_timed_recruit_pull(self, data: Any) -> dict[str, Any]:
        rtype = int(data[0]) if isinstance(data, list) and data else 1
        if rtype not in (1, 3, 30):
            self._last_rpc_context["status"] = -1
            return {}
        ev_def, ev = self._timed_recruit_active()
        if not ev_def or not ev or not ev.eligible or not ev.instance_id:
            self._last_rpc_context["status"] = -1
            return {}

        act_id = int(ev_def.metadata.get("activity_id", 81))
        cfg = self.game_data.get("timed_recruit_model", {}).get(str(act_id), {})
        prog = self._ensure_timed_recruit_prog(act_id, ev.instance_id)
        now = self.now_ts()

        if prog.get("pending_gold_hero"):
            # Do not double-charge while UR Choice Box is waiting to be picked
            snap = self._build_timed_recruit_snapshot(ev_def, ev)
            return {"RecruitInfo": snap, "BaseGetGameResourceList": []}

        count = 10 if rtype == 30 else 1
        if rtype == 1:
            if now < int(prog.get("cooled_time", 0)):
                self._last_rpc_context["status"] = -1
                return {}
        else:
            unit_price = int(cfg.get("recruitPrice", 280))
            total_cost = unit_price * count
            if int(self.state["player"].get("Diamond", 0)) < total_cost:
                self._last_rpc_context["status"] = -1
                return {}
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -total_cost,
                source=f"timed_recruit:{act_id}:x{count}",
            )

        if rtype == 1:
            prog["cooled_time"] = now + max(60, int(cfg.get("freeRecruitCD", 72000)))

        heroes_cfg = self.game_data.get("heroes", {})
        low_r = int(cfg.get("outputLowHeroR", 9000))
        interval = int(cfg.get("outputHighHeroIntervalNum", 9))
        out_zi = int(prog.get("out_zi_count", interval))
        bless_row = self.game_data.get("timed_recruit_bless", {}).get(str(act_id), {})
        per_bless = int(bless_row.get("blessNum", 5))
        max_bless = int(cfg.get("receiveBlessNum", 500))

        triggered_ur = False
        chosen_hids: list[int] = []
        hit_orange = False

        for _idx in range(count):
            prog["pull_count"] = int(prog.get("pull_count", 0)) + 1
            if prog.get("bless_unlocked"):
                prog["bless_num"] = int(prog.get("bless_num", 0)) + per_bless
                eff_bless = int(int(prog["bless_num"]) * float(prog.get("bless_r", 0.7)))
                odds_prob = min(0.25, float(prog["bless_num"]) * float(cfg.get("blessOddsR", 0.00014)))
                if not triggered_ur and (eff_bless >= max_bless or random.random() < odds_prob):
                    triggered_ur = True
                    prog["pending_gold_hero"] = True
                    prog["bless_num"] = 0
                    if count == 1:
                        break
                    continue

            force_o = out_zi <= 0
            hid = self._pick_timed_recruit_non_ur_hero(low_r, force_orange=force_o)
            hq = int(heroes_cfg.get(str(hid), {}).get("quality", 10))
            if hq >= 15:
                hit_orange = True
                out_zi = interval
            else:
                out_zi = max(0, out_zi - 1)
            chosen_hids.append(hid)

        if count == 10 and not hit_orange and chosen_hids:
            chosen_hids[-1] = self._pick_timed_recruit_non_ur_hero(low_r, force_orange=True)
            out_zi = interval

        prog["out_zi_count"] = out_zi
        credit_gain = int(cfg.get("perRecruitGetCredit", 10)) * count
        prog["my_credit"] = int(prog.get("my_credit", 0)) + credit_gain
        hist = prog.setdefault("history", [])
        hist.append({"ts": now, "rtype": rtype, "heroes": chosen_hids, "triggered_ur": triggered_ur})
        if len(hist) > 100:
            prog["history"] = hist[-100:]

        tuples = [(1201, hid, 1) for hid in chosen_hids]
        base_res = (
            self._grant_resources_from_tuples(
                tuples,
                source=f"timed_recruit:{act_id}",
                tx_prefix=f"evt:{ev.instance_id}:pull:{prog['pull_count']}:{uuid.uuid4()}",
            )
            if tuples
            else []
        )
        self._inc_stat("total_recruits", len(chosen_hids))
        snap = self._build_timed_recruit_snapshot(ev_def, ev)
        self.save()
        return {"RecruitInfo": snap, "BaseGetGameResourceList": base_res}

    def _rpc_timed_recruit_draw_credit(self, data: Any) -> dict[str, Any]:
        req_credit = int(data[0]) if isinstance(data, list) and data else 0
        ev_def, ev = self._timed_recruit_active()
        if not ev_def or not ev or not ev.eligible or not ev.instance_id:
            self._last_rpc_context["status"] = -1
            return {}

        act_id = int(ev_def.metadata.get("activity_id", 81))
        cfg = self.game_data.get("timed_recruit_model", {}).get(str(act_id), {})
        prog = self._ensure_timed_recruit_prog(act_id, ev.instance_id)
        rows = sorted(
            [r for r in self.game_data.get("timed_recruit_credit", {}).values() if int(r.get("activityEnumID", 0)) == act_id],
            key=lambda r: int(r["needCredit"]),
        )
        row = next((r for r in rows if int(r["needCredit"]) == req_credit), None)
        if not row or int(prog.get("my_credit", 0)) < req_credit:
            self._last_rpc_context["status"] = -1
            return {}

        # Enforce sequential chest progression as rendered in LimittedTimedRecruitLayer.lua:689
        claimed = [int(x) for x in prog.get("draw_credit_rewards", [])]
        expected_next = next((int(r["needCredit"]) for r in rows if int(r["needCredit"]) not in claimed), None)
        if expected_next != req_credit:
            self._last_rpc_context["status"] = -1
            return {}

        tuples = _parse_res_tuples(str(row.get("creditReward", "")))
        ok, base_res, _reason = self.event_runtime.claim_milestone(
            ev_def.event_id,
            f"credit:{req_credit}",
            lambda idem: self._grant_resources_from_tuples(
                tuples,
                source=f"timed_recruit_credit:{act_id}:{req_credit}",
                tx_prefix=idem,
            ),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}

        claimed.append(req_credit)
        prog["draw_credit_rewards"] = sorted(claimed)
        if len(claimed) >= len(rows) and not prog.get("bless_unlocked"):
            prog["bless_unlocked"] = True
            prog["bless_num"] = int(cfg.get("firstBless", 320))
            prog["bless_r"] = float(cfg.get("firstBlessR", 0.7))
        self.save()
        return {
            "BaseGetGameResourceList": base_res,
            "BlessNum": int(prog.get("bless_num", 0)),
            "BlessR": float(prog.get("bless_r", 0.7)),
            "DrawCreditRewards": ",".join(str(x) for x in prog["draw_credit_rewards"]),
        }

    def _rpc_timed_recruit_draw_gold_hero(self, data: Any) -> dict[str, Any]:
        hero_model_id = int(data[0]) if isinstance(data, list) and data else 0
        ev_def, ev = self._timed_recruit_active()
        if not ev_def or not ev or not ev.eligible or not ev.instance_id:
            self._last_rpc_context["status"] = -1
            return {}

        act_id = int(ev_def.metadata.get("activity_id", 81))
        cfg = self.game_data.get("timed_recruit_model", {}).get(str(act_id), {})
        prog = self._ensure_timed_recruit_prog(act_id, ev.instance_id)
        if not prog.get("pending_gold_hero"):
            self._last_rpc_context["status"] = -1
            return {}

        box_code = str(int(cfg.get("goldHeroModelID", 16060008)))
        valid_hids = {
            int(v.get("outputModelID", 0))
            for v in self.game_data.get("goods_output", {}).get(box_code, {}).values()
        }
        if hero_model_id not in valid_hids:
            self._last_rpc_context["status"] = -1
            return {}

        seq = int(prog.get("ur_grant_seq", 0)) + 1
        prog["ur_grant_seq"] = seq
        base_res = self._grant_resources_from_tuples(
            [(1201, hero_model_id, 1)],
            source=f"timed_recruit_ur:{act_id}:{hero_model_id}",
            tx_prefix=f"evt:{ev.instance_id}:ur:{seq}",
        )
        prog["pending_gold_hero"] = False
        self._inc_stat("total_recruits", 1)
        snap = self._build_timed_recruit_snapshot(ev_def, ev)
        self.save()
        return {"BaseGetGameResourceList": base_res, "RecruitInfo": snap}

    # -------------------- Activity 3: Xxbz / XxbzInfo (4600, Kho Báu Bí Ẩn) --------------------

    def _ensure_xxbz_progress(self) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        ev = self.event_runtime.evaluate("xxbz", self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        assert inst is not None
        prog = inst.setdefault("progress", {})
        free_cnt = int(self.game_data.get("xxbz_config", {}).get("freeFightNums", 1))
        counts = prog.setdefault("remain_counts", {})
        for tid_str in ("1", "2", "3"):
            counts.setdefault(tid_str, free_cnt)
        prog.setdefault("buy_count", 0)
        prog.setdefault("cooled_time", 0)
        life = self.state.setdefault("xxbz_lifetime", {})
        for tid_str in ("1", "2", "3"):
            t_life = life.setdefault(tid_str, {"HighestHurt": 0, "DrawnMaxNum": 0, "drawn_tiers": []})
            t_life.setdefault("drawn_tiers", [])
        return ev, prog, life

    def _xxbz_red_dot(self) -> int:
        lv = int(self.state.get("player", {}).get("Lv", 1))
        if lv < self._daily_task_open_lv(4600):
            return 0
        _ev, prog, life = self._ensure_xxbz_progress()
        models = self.game_data.get("xxbz_model", {})
        for tid_str, row in models.items():
            if lv < int(row.get("needLv", 28)):
                continue
            if int(prog["remain_counts"].get(tid_str, 0)) > 0:
                return 1
            t_life = life.get(tid_str, {})
            hi = int(t_life.get("HighestHurt", 0))
            drawn_max = int(t_life.get("DrawnMaxNum", 0))
            for b in self.game_data.get("xxbz_reward_base", []):
                if int(b.get("treasureID", 0)) == int(tid_str):
                    nl = int(b.get("needLower", 0))
                    if nl > drawn_max and hi >= nl:
                        return 1
        return 0

    def _build_xxbz_payload(self) -> dict[str, Any]:
        _ev, prog, life = self._ensure_xxbz_progress()
        models = self.game_data.get("xxbz_model", {})
        xxbz_list: list[dict[str, Any]] = []
        total_rem = 0
        for tid_str in sorted(models, key=lambda k: int(k)):
            rem = max(0, int(prog["remain_counts"].get(tid_str, 0)))
            total_rem += rem
            t_life = life.get(tid_str, {})
            xxbz_list.append(
                {
                    "TreasureId": int(tid_str),
                    "RemainCount": rem,
                    "HighestHurt": int(t_life.get("HighestHurt", 0)),
                    "DrawnMaxNum": int(t_life.get("DrawnMaxNum", 0)),
                }
            )
        return {
            "XxbzList": xxbz_list,
            "CooledTime": int(prog.get("cooled_time", self.now_ts())),
            "XxbzInfo": {"BuyCount": int(prog.get("buy_count", 0))},
            "RemainNum": total_rem,
        }

    def _build_xxbz_fight_info(self, treasure_id: int) -> dict[str, Any]:
        model = self.game_data.get("xxbz_model", {}).get(str(treasure_id), {})
        boss_hid = str(model.get("PIC", "12010012"))
        boss_lv = int(model.get("needLv", 28))
        boss_cfg = self.game_data["heroes"].get(boss_hid, next(iter(self.game_data["heroes"].values())))
        boss_unit = self._hero_fight_obj(
            boss_cfg,
            lv=boss_lv,
            is_boss=True,
            hp_mult=1000.0,
            ap_mult=0.8 + treasure_id * 0.15,
            def_mult=0.75 + treasure_id * 0.1,
        )
        boss_unit["TotalHp"] = 25_000_000
        boss_unit["HP"] = 25_000_000
        allies = self._build_ally_fight_objs()
        enemies: list[dict[str, Any]] = [{}, boss_unit, {}, {}, {}, {}]
        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        return {
            "TreasureId": int(treasure_id),
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": ally_fsp, "Fap": int(self.state["player"].get("FAP", 0))},
                        {"Fsp": int(boss_unit.get("FSP", 400)), "Fap": 100_000 * treasure_id},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1, 999999),
                    "IsPVP": False,
                }
            ],
        }

    def _calc_xxbz_damage_reward(self, treasure_id: int, hurt: int) -> int:
        """Exact VN damage -> reward formula verified against BattleUILayer.lua:361-389."""
        hurt = max(0, int(hurt))
        base_reward = 0
        for row in self.game_data.get("xxbz_reward_base", []):
            if int(row.get("treasureID", 0)) == treasure_id and hurt >= int(row.get("needLower", 0)):
                base_reward = int(row.get("rewardNum", 0))

        fix = 0
        base = 0
        for row in self.game_data.get("xxbz_reward_cond", []):
            if int(row.get("treasureID", 0)) == treasure_id and int(row.get("conditionLower", 0)) <= hurt:
                fix = int(row.get("rewardNumR", 0))
                base = int(row.get("baseNum", 0))
        c_value = math.ceil(hurt * fix / 1_000_000.0 + base)
        return max(1, int(c_value + base_reward))

    def _rpc_xxbz_get_info(self, _data: Any) -> dict[str, Any]:
        ev = self.event_runtime.evaluate("xxbz", self.state["player"])
        if not ev.unlocked:
            self._last_rpc_context["status"] = -1
            return {}
        out = self._build_xxbz_payload()
        self.save()
        return out

    def _rpc_xxbz_get_fight_info(self, data: Any) -> dict[str, Any]:
        treasure_id = int(data[0]) if isinstance(data, list) and data else 1
        model = self.game_data.get("xxbz_model", {}).get(str(treasure_id))
        ev, prog, _life = self._ensure_xxbz_progress()
        if not model or not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        if int(self.state["player"].get("Lv", 1)) < int(model.get("needLv", 28)):
            self._last_rpc_context["status"] = -1
            return {}
        if int(prog["remain_counts"].get(str(treasure_id), 0)) <= 0:
            self._last_rpc_context["status"] = -1
            return {}
        need_vit = int(self.game_data.get("xxbz_config", {}).get("needVIT", 0))
        if need_vit > 0 and int(self.state["player"].get("VIT", 0)) < need_vit:
            self._last_rpc_context["status"] = -1
            return {}

        fight_info = self._build_xxbz_fight_info(treasure_id)
        prog["pending_fight"] = {"treasure_id": treasure_id, "fight_info": fight_info}
        self.save()
        return {"FightInfo": fight_info}

    def _rpc_xxbz_fight(self, data: Any) -> dict[str, Any]:
        treasure_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 1
        verify_raw = data[2] if isinstance(data, list) and len(data) >= 3 else None
        client_dmg = int(data[3]) if isinstance(data, list) and len(data) >= 4 and str(data[3]).isdigit() else 0

        model = self.game_data.get("xxbz_model", {}).get(str(treasure_id))
        ev, prog, life = self._ensure_xxbz_progress()
        if not model or not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        if int(self.state["player"].get("Lv", 1)) < int(model.get("needLv", 28)):
            self._last_rpc_context["status"] = -1
            return {}
        rem = int(prog["remain_counts"].get(str(treasure_id), 0))
        if rem <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        need_vit = int(self.game_data.get("xxbz_config", {}).get("needVIT", 0))
        if need_vit > 0:
            if int(self.state["player"].get("VIT", 0)) < need_vit:
                self._last_rpc_context["status"] = -1
                return {}
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "VIT",
                -need_vit,
                source=f"xxbz_vit:{treasure_id}",
            )

        prog["remain_counts"][str(treasure_id)] = rem - 1
        prog["cooled_time"] = self.now_ts() + max(0, int(self.game_data.get("xxbz_config", {}).get("fightCD", 0)))

        pending = prog.pop("pending_fight", None)
        if isinstance(pending, dict) and int(pending.get("treasure_id", 0)) == treasure_id:
            fight_info = pending["fight_info"]
        else:
            fight_info = self._build_xxbz_fight_info(treasure_id)
        boss_max_hp = int(fight_info["FightObjs"][0]["Heros"][7].get("TotalHp", 25_000_000))

        # Verify damage from client combat payload when supplied; otherwise simulate server-side
        verified_hurt: int | None = None
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
                            rem_hp = max(0, min(boss_max_hp, int(unit_hp.get("HP", boss_max_hp))))
                            verified_hurt = max(0, boss_max_hp - rem_hp)
                            break

        if verified_hurt is None:
            outcome = simulate_fight_info(fight_info, self.game_data["attacks"])
            last_wave = outcome.verify_data.get("hp", [[]])[-1]
            rem_hp = next((int(u["HP"]) for u in last_wave if int(u.get("PosId", 0)) == 8), boss_max_hp)
            verified_hurt = max(1000, boss_max_hp - rem_hp)
        if client_dmg > 0 and verified_hurt == 0:
            verified_hurt = min(boss_max_hp, client_dmg)

        hurt = max(1, int(verified_hurt))
        reward_amt = self._calc_xxbz_damage_reward(treasure_id, hurt)
        tuples: list[tuple[int, int, int]] = [
            (int(model.get("rewardTypeID", 1112)), int(model.get("rewardModelID", 0)), reward_amt)
        ]
        for rt, rm, rn in _parse_res_tuples(str(model.get("extraOutput", ""))):
            tuples.append((rt, rm, rn))

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"xxbz_fight:{treasure_id}",
            tx_prefix=f"evt:{ev.instance_id}:fight:{treasure_id}:{uuid.uuid4()}",
        )
        t_life = life[str(treasure_id)]
        t_life["HighestHurt"] = max(int(t_life.get("HighestHurt", 0)), hurt)
        self._inc_stat("mystery_treasure_count", 1)
        stats = self.state.setdefault("stats", {})
        stats["mystery_treasure_max_dmg"] = max(int(stats.get("mystery_treasure_max_dmg", 0)), int(t_life["HighestHurt"]))
        self._record_daily_task_progress(30, 1)

        payload = self._build_xxbz_payload()
        payload["BaseGetGameResourceList"] = base_res
        self.save()
        return payload

    def _rpc_xxbz_draw_reward(self, data: Any) -> dict[str, Any]:
        treasure_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 1
        req_hurt = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 0

        ev, _prog, life = self._ensure_xxbz_progress()
        if not ev.unlocked:
            self._last_rpc_context["status"] = -1
            return {}
        t_life = life.get(str(treasure_id))
        if not t_life:
            self._last_rpc_context["status"] = -1
            return {}

        row = next(
            (
                b
                for b in self.game_data.get("xxbz_reward_base", [])
                if int(b.get("treasureID", 0)) == treasure_id and int(b.get("needLower", 0)) == req_hurt
            ),
            None,
        )
        if not row or int(t_life.get("HighestHurt", 0)) < req_hurt:
            self._last_rpc_context["status"] = -1
            return {}
        drawn_tiers = [int(x) for x in t_life.get("drawn_tiers", [])]
        if req_hurt <= int(t_life.get("DrawnMaxNum", 0)) or req_hurt in drawn_tiers:
            self._last_rpc_context["status"] = -1
            return {}

        dia_amt = int(row.get("onceRewardNum", 100))
        base_res = self._grant_resources_from_tuples(
            [(1111, 0, dia_amt)],
            source=f"xxbz_milestone:{treasure_id}:{req_hurt}",
            tx_prefix=f"xxbz_life:{self.profile_name}:{treasure_id}:{req_hurt}",
        )
        t_life["DrawnMaxNum"] = max(int(t_life.get("DrawnMaxNum", 0)), req_hurt)
        drawn_tiers.append(req_hurt)
        t_life["drawn_tiers"] = sorted(drawn_tiers)

        payload = self._build_xxbz_payload()
        payload["BaseGetGameResourceList"] = base_res
        self.save()
        return payload

    def _rpc_xxbz_buy_count(self, data: Any) -> dict[str, Any]:
        treasure_id = int(data[0]) if isinstance(data, list) and data else 1
        if str(treasure_id) not in self.game_data.get("xxbz_model", {}):
            self._last_rpc_context["status"] = -1
            return {}
        ev, prog, _life = self._ensure_xxbz_progress()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}

        vip_lv = int(self.state["player"].get("Vip", 0))
        can_buy = int(self.game_data.get("vip_model", {}).get(str(vip_lv), {}).get("buyXSBZNum", 0))
        cur_buys = int(prog.get("buy_count", 0))
        if cur_buys >= can_buy:
            self._last_rpc_context["status"] = -1
            return {}

        del_tbl = self.game_data.get("xxbz_del_cd", {})
        step_key = str(min(cur_buys + 1, max((int(k) for k in del_tbl), default=1)))
        dia_cost = int(del_tbl.get(step_key, {}).get("useDiamond", 20))
        if int(self.state["player"].get("Diamond", 0)) < dia_cost:
            self._last_rpc_context["status"] = -1
            return {}

        self.ledger.apply_player_delta(
            self.state["player"],
            self.profile_name,
            "Diamond",
            -dia_cost,
            source=f"xxbz_buy_count:{treasure_id}",
        )
        prog["buy_count"] = cur_buys + 1
        prog["remain_counts"][str(treasure_id)] = int(prog["remain_counts"].get(str(treasure_id), 0)) + 1
        payload = self._build_xxbz_payload()
        self.save()
        return payload
