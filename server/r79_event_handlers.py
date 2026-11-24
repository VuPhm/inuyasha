#!/usr/bin/env python3
"""R7.9 Historical Events, Lucky Activities & Multi-Region Recovery RPC handlers."""

from __future__ import annotations

import copy
from datetime import date
import math
import random
import uuid
from typing import Any

from economy_audit import DuplicateTransactionError
from event_runtime import STATUS_ACTIVE


def _parse_res_tuples(raw: str) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for chunk in str(raw or "").split("||"):
        parts = [p.strip() for p in chunk.split(",")]
        if (
            len(parts) >= 3
            and parts[0].lstrip("-").isdigit()
            and parts[1].lstrip("-").isdigit()
            and parts[2].lstrip("-").isdigit()
        ):
            rt, rm, rn = int(parts[0]), int(parts[1]), int(parts[2])
            if rn > 0:
                out.append((rt, rm, rn))
    return out


def _res_dicts(tuples: list[tuple[int, int, int]]) -> list[dict[str, int]]:
    return [
        {"ResourceTypeSub": int(rt), "ModelId": int(rm), "Count": int(rn)}
        for rt, rm, rn in tuples
        if int(rn) > 0
    ]


class R79EventHandlersMixin:
    """Mixin implementing R7.9 historical events, lucky minigames, milestone activities & multi-region recovery."""

    GOLDEN_HAMMER_MODEL_ID = 16050061   # Búa Vàng (TimedSmashEggLayer.lua:19)
    LOTTERY_TICKET_MODEL_ID = 16050027  # Vé Rút Thưởng (VN GoodsModel)
    SLOT_RECHARGE_QUOTA = 60

    # -------------------- TimedActivityOpenInfo (9300 + 4401..4432) --------------------

    def _build_timed_activity_open_info(self) -> dict[str, list[dict[str, Any]]]:
        """Build Avatar.TimedActivityOpenInfo with active 9300 banners and 4401..4432 TimedActivityScene tabs."""
        p = self.state["player"]
        out: dict[str, list[dict[str, Any]]] = {}

        active_tr = sorted(
            self.event_runtime.get_active_timed_events(9300, p),
            key=lambda pair: int(pair[0].metadata.get("activity_id", 0)),
        )
        if active_tr:
            items_9300: list[dict[str, Any]] = []
            for idx, (ev_def, ev) in enumerate(active_tr, start=1):
                act_id = int(ev_def.metadata.get("activity_id", 81))
                items_9300.append(
                    {
                        "ActivityId": act_id,
                        "Name": ev_def.name,
                        "EndDate": int(ev.end_ts or 0),
                        "Xssx": idx,
                        "ExtraInfo": {"ActivityEnumId": act_id},
                    }
                )
            out["9300"] = items_9300

        timed_sub_modules = [
            4401, 4402, 4403, 4405, 4406, 4407, 4409, 4410, 4412,
            4413, 4414, 4415, 4416, 4417, 4418, 4419, 4420,
            4421, 4422, 4426, 4427, 4428, 4429, 4430, 4432,
            6301, 6302, 6303, 6304, 6306, 6308, 6309, 6311, 6313, 6314,
            6401, 6402, 6403, 6404, 6406, 6408, 6409, 6411, 6413, 6414,
        ]
        for order_idx, mod_sub in enumerate(timed_sub_modules, start=1):
            active_list = self.event_runtime.get_active_timed_events(mod_sub, p)
            if not active_list:
                continue
            mod_items: list[dict[str, Any]] = []
            for ev_def, ev in active_list:
                act_id = int(ev_def.metadata.get("activity_id", mod_sub))
                extra_info = copy.deepcopy(ev_def.metadata.get("extra_info", {}))
                mod_items.append(
                    {
                        "ActivityId": act_id,
                        "Name": ev_def.name,
                        "EndDate": int(ev.end_ts or 0),
                        "Xssx": order_idx,
                        "ExtraInfo": extra_info,
                    }
                )
            out[str(mod_sub)] = mod_items
        return out

    ACTIVITY_ID_TO_EVENT_ID: dict[int, str] = {
        4401: "timed_charge_single",
        4402: "timed_charge_total",
        4403: "timed_use_total",
        4406: "timed_exchange",
        4412: "timed_slot",
        4426: "timed_smash_egg",
        4427: "timed_day_login",
        4428: "timed_points_mall",
        4429: "timed_charge_gift",
        4430: "timed_active_rank",
        6301: "festival_charge_total",
        6302: "festival_charge_single",
        6303: "festival_exchange",
        6304: "festival_slot",
        6306: "festival_smash_egg",
        6308: "festival_day_login",
        6309: "festival_use_total",
        6311: "festival_points_mall",
        6313: "festival_active_rank",
        6314: "festival_charge_gift",
        6401: "holiday_charge_total",
        6402: "holiday_charge_single",
        6403: "holiday_exchange",
        6404: "holiday_slot",
        6406: "holiday_smash_egg",
        6408: "holiday_day_login",
        6409: "holiday_use_total",
        6411: "holiday_points_mall",
        6413: "holiday_active_rank",
        6414: "holiday_charge_gift",
    }
    _CHARGE_SINGLE_FAMILY = ("timed_charge_single", "festival_charge_single", "holiday_charge_single")
    _CHARGE_TOTAL_FAMILY = ("timed_charge_total", "festival_charge_total", "holiday_charge_total")
    _USE_TOTAL_FAMILY = ("timed_use_total", "festival_use_total", "holiday_use_total")
    _EXCHANGE_FAMILY = ("timed_exchange", "festival_exchange", "holiday_exchange")
    _SLOT_FAMILY = ("timed_slot", "festival_slot", "holiday_slot")
    _SMASH_EGG_FAMILY = ("timed_smash_egg", "festival_smash_egg", "holiday_smash_egg")
    _DAY_LOGIN_FAMILY = ("timed_day_login", "festival_day_login", "holiday_day_login")
    _POINTS_MALL_FAMILY = ("timed_points_mall", "festival_points_mall", "holiday_points_mall")
    _CHARGE_GIFT_FAMILY = ("timed_charge_gift", "festival_charge_gift", "holiday_charge_gift")
    _ACTIVE_RANK_FAMILY = ("timed_active_rank", "festival_active_rank", "holiday_active_rank")

    def _resolve_timed_event_id(self, default_event_id: str, data: Any = None, *, family: tuple[str, ...]) -> str:
        selected = self.state.setdefault("selected_timed_activity", {})
        if isinstance(data, list) and data and data[0] is not None:
            try:
                mapped = self.ACTIVITY_ID_TO_EVENT_ID.get(int(data[0]))
            except (TypeError, ValueError):
                mapped = None
            if mapped and mapped in family:
                selected[default_event_id] = mapped
                return mapped
        saved = selected.get(default_event_id)
        if saved in family and self.event_runtime.evaluate(saved, self.state["player"]).eligible:
            return str(saved)
        if self.event_runtime.evaluate(default_event_id, self.state["player"]).eligible:
            return default_event_id
        for cand in family:
            if self.event_runtime.evaluate(cand, self.state["player"]).eligible:
                return cand
        return default_event_id

    def _extract_act_and_arg(self, data: Any, default_event_id: str, family: tuple[str, ...]) -> tuple[str, int]:
        has_act = False
        if isinstance(data, list) and len(data) >= 2 and data[0] is not None:
            try:
                has_act = self.ACTIVITY_ID_TO_EVENT_ID.get(int(data[0])) in family
            except (TypeError, ValueError):
                has_act = False
        if has_act:
            ev_id = self._resolve_timed_event_id(default_event_id, data, family=family)
            return ev_id, int(data[1])
        ev_id = self._resolve_timed_event_id(default_event_id, None, family=family)
        arg = int(data[0]) if isinstance(data, list) and data else 0
        return ev_id, arg

    # -------------------- Shared Economy / Goods / S1 Multi-Account Helpers --------------------

    def _get_goods_qty(self, model_id: int) -> int:
        mid = int(model_id)
        return sum(int(g.get("Num", 0)) for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == mid)

    def _consume_goods_qty(self, model_id: int, count: int) -> bool:
        mid = int(model_id)
        need = int(count)
        if need <= 0:
            return True
        if self._get_goods_qty(mid) < need:
            return False
        rem = need
        goods_list = self.state.get("goods", [])
        for g in list(goods_list):
            if int(g.get("GoodsModelId", 0)) != mid:
                continue
            cur = int(g.get("Num", 0))
            take = min(cur, rem)
            g["Num"] = cur - take
            rem -= take
            self._mark_goods_changed(mid)
            if g["Num"] <= 0:
                goods_list.remove(g)
            if rem <= 0:
                break
        return True

    def _player_total_recharged_diamonds(self, prof: Any | None = None) -> int:
        target = prof if prof is not None else self
        st = target.state
        stats = st.get("stats", {})
        charged = int(stats.get("recharged_diamonds", 0))
        vip_exp = int(st.get("player", {}).get("VipEXP", 0))
        charge_num = int(st.get("player", {}).get("ChargeNum", 0))
        return max(charged, vip_exp, charge_num)

    def _player_total_spent_diamonds(self, prof: Any | None = None) -> int:
        target = prof if prof is not None else self
        st = target.state
        stats = st.get("stats", {})
        return int(stats.get("spent_diamonds", 0))

    def _player_activity_stat_score(self, prof: Any | None = None) -> int:
        target = prof if prof is not None else self
        stats = target.state.get("stats", {})
        # Weighted per ActiverankingModel.lua (normal=1, elite=2, boss=1, nightmare=3, grab=1, arena=1, ggzj=2, bdd=1, xxbz=3)
        return (
            int(stats.get("normal_Win", 0)) * 1
            + int(stats.get("elite_Win", 0)) * 2
            + int(stats.get("boss_count", 0)) * 1
            + int(stats.get("nightmare_Win", 0)) * 3
            + int(stats.get("grab_count", 0)) * 1
            + int(stats.get("arena_Win", 0)) * 1
            + int(stats.get("ggzj_count", 0)) * 2
            + int(stats.get("gddh_fights", 0)) * 1
            + int(stats.get("bdd_Win", 0)) * 1
            + int(stats.get("mystery_treasure_count", 0)) * 3
        )

    def _player_active_score(self, prof: Any | None = None) -> int:
        target = prof if prof is not None else self
        st = target.state
        score = self._player_activity_stat_score(target) + int(st.get("player", {}).get("Lv", 1)) * 5
        return max(10, score)

    def _s1_account_profiles(self) -> list[Any]:
        out: list[Any] = [self]
        seen: set[str] = {str(getattr(self, "profile_name", "normal"))}
        peer_fn = getattr(self, "peer_profiles_fn", None)
        if callable(peer_fn):
            for prof in peer_fn(self) or []:
                pname = str(getattr(prof, "profile_name", ""))
                if pname and pname not in seen and int(prof.state.get("player", {}).get("IsNewPlayer", 0)) == 0:
                    seen.add(pname)
                    out.append(prof)
        return out

    def _s1_event_scores(self, instance_id: str, progress_key: str, my_score: int) -> list[tuple[str, str, int]]:
        rows = []
        for prof in self._s1_account_profiles():
            player = prof.state["player"]
            # Read by instance ID so rollover/reset does not advance another profile or mix periods.
            inst = prof.event_runtime.get_instance(instance_id) or {}
            score = my_score if prof is self else int(inst.get("progress", {}).get(progress_key, 0))
            rows.append((str(player["PlayerId"]), str(player.get("PlayerName", "Hero")), score))
        return rows

    def _event_rank_payload(
        self, rows: list[tuple[str, str, int]], *, name_key: str, score_key: str, limit: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        # At equal scores, real S1 accounts precede bots. Identity breaks ties consistently for every viewer.
        rows.sort(key=lambda row: (-row[2], row[0].startswith("npc:"), row[0]))
        my_id = str(self.state["player"]["PlayerId"])
        my_rank = next((rank for rank, row in enumerate(rows, 1) if row[0] == my_id), 0)
        return my_rank, [
            {"Rank": rank, name_key: name, score_key: score}
            for rank, (_, name, score) in enumerate(rows[:limit], 1)
        ]

    # -------------------- 1. TimedMoneyTreeLayer (4432, Cây Tiền May Mắn) --------------------

    MONEY_TREE_SHOW_REWARDS: list[tuple[int, int, int]] = [
        (1111, 0, 188),
        (1112, 0, 200000),
        (1605, 16050001, 50),
        (1606, 16060002, 1),
        (1605, 16050061, 2),
    ]
    MONEY_TREE_POOL: list[tuple[int, int, int, int]] = [
        # (ResourceTypeSub, ModelId, Count, weight)
        (1112, 0, 50000, 3200),
        (1112, 0, 120000, 1800),
        (1111, 0, 30, 1600),
        (1111, 0, 88, 700),
        (1111, 0, 188, 200),
        (1605, 16050001, 25, 1100),
        (1605, 16050010, 2, 700),
        (1605, 16050061, 1, 400),
        (1605, 16050055, 1, 300),
    ]
    MONEY_TREE_MILESTONES: list[tuple[int, list[tuple[int, int, int]]]] = [
        (5, [(1111, 0, 100), (1112, 0, 100000)]),
        (10, [(1111, 0, 200), (1605, 16050061, 2)]),
        (20, [(1111, 0, 400), (1606, 16060002, 1)]),
        (40, [(1111, 0, 888), (1606, 16060019, 1)]),
    ]

    def _ensure_money_tree_prog(self) -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate("timed_money_tree", self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if inst is None:
            return ev, {}
        prog = inst.setdefault("progress", {})
        prog.setdefault("num", 0)
        prog.setdefault("free_used", False)
        prog.setdefault("drawn_nums", [])
        return ev, prog

    def _money_tree_red_dot(self) -> int:
        ev, prog = self._ensure_money_tree_prog()
        if not ev.eligible:
            return 0
        if not prog.get("free_used", False):
            return 1
        num = int(prog.get("num", 0))
        drawn = set(int(x) for x in prog.get("drawn_nums", []))
        return 1 if any(num >= m and m not in drawn for m, _ in self.MONEY_TREE_MILESTONES) else 0

    def _build_money_tree_payload(self, prog: dict[str, Any], base_res: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        free_avail = not bool(prog.get("free_used", False))
        drawn = sorted(set(int(x) for x in prog.get("drawn_nums", [])))
        payload: dict[str, Any] = {
            "CostNum": 0 if free_avail else 50,
            "CostNumTen": 450,
            "Num": int(prog.get("num", 0)),
            "DrawnNums": ",".join(str(x) for x in drawn),
            "ShowRewards": [{"Reward": _res_dicts([t])} for t in self.MONEY_TREE_SHOW_REWARDS],
            "Rewards": [
                {"Num": m_num, "Reward": _res_dicts(r_list)}
                for m_num, r_list in self.MONEY_TREE_MILESTONES
            ],
        }
        if base_res is not None:
            payload["BaseGetGameResourceList"] = base_res
        return payload

    def _rpc_timed_money_tree_get_info(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_money_tree_prog()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        out = self._build_money_tree_payload(prog)
        self.save()
        return out

    def _rpc_timed_money_tree_shake(self, data: Any) -> dict[str, Any]:
        shake_times = int(data[1]) if isinstance(data, list) and len(data) >= 2 else (int(data[0]) if isinstance(data, list) and data else 1)
        if shake_times not in (1, 10):
            self._last_rpc_context["status"] = -1
            return {}
        ev, prog = self._ensure_money_tree_prog()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}

        free_avail = not bool(prog.get("free_used", False))
        cost = (0 if free_avail else 50) if shake_times == 1 else 450
        if int(self.state["player"].get("Diamond", 0)) < cost:
            self._last_rpc_context["status"] = -1
            return {}
        if cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -cost,
                source=f"timed_money_tree:x{shake_times}",
            )
            self._last_rpc_context["diamond_spent"] = cost
        if shake_times == 1 and free_avail:
            prog["free_used"] = True

        choices = [(rt, rm, rn) for rt, rm, rn, _w in self.MONEY_TREE_POOL]
        weights = [w for _rt, _rm, _rn, w in self.MONEY_TREE_POOL]
        rolled = random.choices(choices, weights=weights, k=shake_times)
        prog["num"] = int(prog.get("num", 0)) + shake_times
        base_res = self._grant_resources_from_tuples(
            rolled,
            source=f"timed_money_tree:x{shake_times}",
            tx_prefix=f"evt:{ev.instance_id}:shake:{prog['num']}:{uuid.uuid4()}",
        )
        self.save()
        return self._build_money_tree_payload(prog, base_res=base_res)

    def _rpc_timed_money_tree_draw_reward(self, data: Any) -> dict[str, Any]:
        req_times = int(data[1]) if isinstance(data, list) and len(data) >= 2 else (int(data[0]) if isinstance(data, list) and data else 0)
        ev, prog = self._ensure_money_tree_prog()
        if not ev.eligible or int(prog.get("num", 0)) < req_times:
            self._last_rpc_context["status"] = -1
            return {}
        milestone = next((r_list for m_num, r_list in self.MONEY_TREE_MILESTONES if m_num == req_times), None)
        if not milestone:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "timed_money_tree",
            f"milestone:{req_times}",
            lambda idem: self._grant_resources_from_tuples(
                milestone,
                source=f"timed_money_tree_chest:{req_times}",
                tx_prefix=idem,
            ),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        drawn = set(int(x) for x in prog.get("drawn_nums", []))
        drawn.add(req_times)
        prog["drawn_nums"] = sorted(drawn)
        self.save()
        return self._build_money_tree_payload(prog, base_res=base_res)

    def _settle_money_tree_milestones(self, inst: dict[str, Any]) -> None:
        if not self.event_runtime.archive_cfg.get("settle_unclaimed_credit", True):
            return
        prog = inst.get("progress", {})
        claimed = {int(n) for n in prog.get("drawn_nums", [])}
        for num, resources in self.MONEY_TREE_MILESTONES:
            if num <= int(prog.get("num", 0)) and num not in claimed:
                if self.event_runtime.is_claimed(inst["instance_id"], f"milestone:{num}"):
                    continue
                self._push_reward_center_entry(
                    source_key=f"money_tree:{inst['instance_id']}:{num}",
                    title=f"Cây Tiền May Mắn — Mốc {num} Lượt",
                    content="Phần thưởng mốc đã đạt ở kỳ trước.",
                    res_tuples=resources,
                )

    # -------------------- 2. TimedPrayTree (4409, Cây Ước Nguyện) --------------------

    PRAY_TREE_NEED_DIAMOND = 300
    PRAY_TREE_DAYS: list[tuple[int, str]] = [
        (1, "1111,0,120||1112,0,150000||1605,16050061,2"),
        (2, "1111,0,150||1605,16050001,80||1605,16050055,2"),
        (3, "1111,0,180||1603,16030006,3||1603,16030008,3"),
        (4, "1111,0,220||1606,16060002,1||1605,16050010,3"),
        (5, "1111,0,300||1606,16060019,1||1605,16050061,3"),
    ]

    def _ensure_pray_tree_prog(self) -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate("timed_pray_tree", self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if not ev.eligible or inst is None:
            return ev, {}
        prog = inst.setdefault("progress", {})
        prog.setdefault("claimed_days", [])
        if "recharged_diamonds" not in prog:
            start = int(ev.start_ts or 0)
            if ev.instance_id.rsplit(":", 1)[-1].startswith("r"):
                start = max(start, int(inst["created_at"]))
            now_exclusive = self.now_ts() + 1
            end = min(now_exclusive, ev.end_ts or now_exclusive)
            prog["recharged_diamonds"] = self._legacy_pray_tree_recharge(start, end)
        return ev, prog

    def _record_pray_tree_recharge(self, diamonds: int) -> None:
        ev, prog = self._ensure_pray_tree_prog()
        if ev.eligible:
            prog["recharged_diamonds"] += diamonds

    def _build_pray_tree_reward_list(self, ev: Any, prog: dict[str, Any]) -> list[dict[str, Any]]:
        claimed = set(int(x) for x in prog.get("claimed_days", []))
        activated = prog.get("recharged_diamonds", 0) >= self.PRAY_TREE_NEED_DIAMOND
        out: list[dict[str, Any]] = []
        for day_num, res_str in self.PRAY_TREE_DAYS:
            if day_num in claimed or (ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"day:{day_num}")):
                continue
            out.append(
                {
                    "Days": day_num,
                    "CanDraw": 1 if activated else 0,
                    "ResourceList": res_str,
                }
            )
        return out

    def _pray_tree_red_dot(self) -> int:
        ev, prog = self._ensure_pray_tree_prog()
        if not ev.eligible:
            return 0
        return 1 if any(r["CanDraw"] == 1 for r in self._build_pray_tree_reward_list(ev, prog)) else 0

    def _rpc_timed_hopetree_get_info(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_pray_tree_prog()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        out = {
            "NeedNum": self.PRAY_TREE_NEED_DIAMOND,
            "Num": prog["recharged_diamonds"],
            "RewardNum": len(self.PRAY_TREE_DAYS),
            "EndTime": int(ev.end_ts or self.clock.next_midnight_ts()),
            "RewardList": self._build_pray_tree_reward_list(ev, prog),
        }
        self.save()
        return out

    def _rpc_timed_hopetree_draw_reward(self, data: Any) -> dict[str, Any]:
        day_id = int(data[0]) if isinstance(data, list) and data else 0
        ev, prog = self._ensure_pray_tree_prog()
        if not ev.eligible or prog["recharged_diamonds"] < self.PRAY_TREE_NEED_DIAMOND:
            self._last_rpc_context["status"] = -1
            return {}
        res_str = next((rs for d, rs in self.PRAY_TREE_DAYS if d == day_id), None)
        if not res_str:
            self._last_rpc_context["status"] = -1
            return {}
        tuples = _parse_res_tuples(res_str)
        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "timed_pray_tree",
            f"day:{day_id}",
            lambda idem: self._grant_resources_from_tuples(
                tuples,
                source=f"timed_pray_tree:day{day_id}",
                tx_prefix=idem,
            ),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        claimed = set(int(x) for x in prog.get("claimed_days", []))
        claimed.add(day_id)
        prog["claimed_days"] = sorted(claimed)
        self.save()
        return {
            "BaseGetGameResourceList": base_res,
            "RewardList": self._build_pray_tree_reward_list(ev, prog),
        }

    # -------------------- 3. TimedSmashEggLayer (4426, Đập Trứng Vàng) --------------------

    SMASH_EGG_POOL: list[tuple[str, int]] = [
        ("1111,0,88", 2200),
        ("1111,0,188", 900),
        ("1112,0,150000", 2500),
        ("1605,16050001,60", 1600),
        ("1605,16050010,3", 1100),
        ("1603,16030006,2", 900),
        ("1606,16060002,1", 500),
        ("1606,16060019,1", 300),
    ]

    def _ensure_smash_egg_prog(self, event_id: str = "timed_smash_egg") -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate(event_id, self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if not ev.eligible or inst is None:
            return ev, {}
        prog = inst.setdefault("progress", {})
        prog.setdefault("smash_count", 0)
        prog.setdefault("records", [])
        if not prog.get("starter_hammers_seeded"):
            if self._get_goods_qty(self.GOLDEN_HAMMER_MODEL_ID) == 0:
                try:
                    self._grant_resources_from_tuples(
                        [(1605, self.GOLDEN_HAMMER_MODEL_ID, 5)],
                        source="smash_egg_starter_hammers",
                        tx_prefix=f"evt:{self.profile_name}:{self.state['player']['PlayerId']}:{ev.instance_id}:starter_hammers",
                    )
                except DuplicateTransactionError:
                    # Older builds could log the seed on a read without saving the profile.
                    # The single goods grant restores the stack before it records the ledger entry.
                    if self._get_goods_qty(self.GOLDEN_HAMMER_MODEL_ID) != 5:
                        raise
            prog["starter_hammers_seeded"] = True
            self.save()
        return ev, prog

    def _smash_egg_red_dot(self) -> int:
        ev, _prog = self._ensure_smash_egg_prog()
        if not ev.eligible:
            return 0
        return 1 if self._get_goods_qty(self.GOLDEN_HAMMER_MODEL_ID) > 0 else 0

    def _rpc_timed_smash_egg_get_reward_list(self, _data: Any) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_smash_egg", None, family=self._SMASH_EGG_FAMILY)
        ev, _prog = self._ensure_smash_egg_prog(ev_id)
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        out = {
            "EndDate": int(ev.end_ts or self.clock.next_midnight_ts()),
            "TimedSmashingReward": [{"OutResource": r_str} for r_str, _w in self.SMASH_EGG_POOL],
        }
        self.save()
        return out

    def _rpc_timed_smash_egg_get_record(self, _data: Any) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_smash_egg", None, family=self._SMASH_EGG_FAMILY)
        ev, prog = self._ensure_smash_egg_prog(ev_id)
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        local_records = list(prog.get("records", []))
        for prof in self._s1_account_profiles():
            if prof is not self:
                inst = prof.event_runtime.get_instance(ev.instance_id) or {}
                local_records.extend(inst.get("progress", {}).get("records", []))
        local_records.sort(key=lambda row: (int(row.get("TimeTick", 0)), str(row.get("PlayerId", ""))))

        records = []
        for idx, peer_name in enumerate(["KhuyểnDạXoa", "BạchSát", "TửVu", "NgọcTứHồn"]):
            records.append(
                {
                    "Type": 1,
                    "PlayerId": f"bot-{idx + 1}",
                    "Name": f"{peer_name} (NPC)",
                    "Reward": self.SMASH_EGG_POOL[(idx + 2) % len(self.SMASH_EGG_POOL)][0],
                }
            )
        self.save()
        return {"TimedSmashingRecord": (records + local_records)[-20:]}

    def _rpc_timed_smash_egg_smash(self, data: Any) -> dict[str, Any]:
        req_count = int(data[0]) if isinstance(data, list) and data else 1
        req_count = max(1, min(100, req_count))
        ev_id = self._resolve_timed_event_id("timed_smash_egg", None, family=self._SMASH_EGG_FAMILY)
        ev, prog = self._ensure_smash_egg_prog(ev_id)
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        have = self._get_goods_qty(self.GOLDEN_HAMMER_MODEL_ID)
        if have < req_count or not self._consume_goods_qty(self.GOLDEN_HAMMER_MODEL_ID, req_count):
            self._last_rpc_context["status"] = -1
            return {}

        pool_strs = [r_str for r_str, _w in self.SMASH_EGG_POOL]
        weights = [w for _r_str, w in self.SMASH_EGG_POOL]
        chosen_strs = random.choices(pool_strs, weights=weights, k=req_count)
        tuples: list[tuple[int, int, int]] = []
        p_info = self.state["player"]
        records = prog.setdefault("records", [])
        for r_str in chosen_strs:
            tuples.extend(_parse_res_tuples(r_str))
            records.append(
                {
                    "Type": 1,
                    "PlayerId": str(p_info.get("PlayerId", "")),
                    "Name": str(p_info.get("PlayerName", "Hero")),
                    "Reward": r_str,
                    "TimeTick": self.now_ts(),
                }
            )
        if len(records) > 30:
            prog["records"] = records[-30:]
        prog["smash_count"] = int(prog.get("smash_count", 0)) + req_count
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"timed_smash_egg:x{req_count}",
            tx_prefix=f"evt:{ev.instance_id}:smash:{prog['smash_count']}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # -------------------- 4. TimedSlotLayer (4412, Kho Báu Quay Thưởng) --------------------

    SLOT_NORMAL_REWARDS: list[dict[str, Any]] = [
        {"Type": 1, "OrderId": 1, "IsDouble": 0, "Ratio": 1, "OutResource": "1112,0,50000"},
        {"Type": 1, "OrderId": 2, "IsDouble": 0, "Ratio": 1, "OutResource": "1111,0,30"},
        {"Type": 1, "OrderId": 3, "IsDouble": 1, "Ratio": 2, "OutResource": ""},
        {"Type": 1, "OrderId": 4, "IsDouble": 0, "Ratio": 1, "OutResource": "1605,16050001,30"},
        {"Type": 1, "OrderId": 5, "IsDouble": 0, "Ratio": 1, "OutResource": "1603,16030006,1"},
        {"Type": 1, "OrderId": 6, "IsDouble": 0, "Ratio": 1, "OutResource": "1112,0,100000"},
        {"Type": 1, "OrderId": 7, "IsDouble": 1, "Ratio": 3, "OutResource": ""},
        {"Type": 1, "OrderId": 8, "IsDouble": 0, "Ratio": 1, "OutResource": "1605,16050010,2"},
        {"Type": 1, "OrderId": 9, "IsDouble": 0, "Ratio": 1, "OutResource": "1111,0,60"},
        {"Type": 1, "OrderId": 10, "IsDouble": 0, "Ratio": 1, "OutResource": "1603,16030008,1"},
        {"Type": 1, "OrderId": 11, "IsDouble": 1, "Ratio": 2, "OutResource": ""},
        {"Type": 1, "OrderId": 12, "IsDouble": 0, "Ratio": 1, "OutResource": "1605,16050061,1"},
        {"Type": 1, "OrderId": 13, "IsDouble": 0, "Ratio": 1, "OutResource": "1112,0,150000"},
        {"Type": 1, "OrderId": 14, "IsDouble": 0, "Ratio": 1, "OutResource": "1606,16060002,1"},
        {"Type": 1, "OrderId": 15, "IsDouble": 0, "Ratio": 1, "OutResource": "1111,0,100"},
        {"Type": 1, "OrderId": 16, "IsDouble": 0, "Ratio": 1, "OutResource": "1602,16020013,1"},
    ]
    SLOT_PRETTY_REWARDS: list[dict[str, Any]] = [
        {"Type": 2, "OrderId": 1, "IsDouble": 0, "Ratio": 1, "OutResource": "1111,0,150"},
        {"Type": 2, "OrderId": 2, "IsDouble": 0, "Ratio": 1, "OutResource": "1112,0,300000"},
        {"Type": 2, "OrderId": 3, "IsDouble": 1, "Ratio": 2, "OutResource": ""},
        {"Type": 2, "OrderId": 4, "IsDouble": 0, "Ratio": 1, "OutResource": "1605,16050001,150"},
        {"Type": 2, "OrderId": 5, "IsDouble": 0, "Ratio": 1, "OutResource": "1606,16060002,1"},
        {"Type": 2, "OrderId": 6, "IsDouble": 0, "Ratio": 1, "OutResource": "1111,0,250"},
        {"Type": 2, "OrderId": 7, "IsDouble": 1, "Ratio": 3, "OutResource": ""},
        {"Type": 2, "OrderId": 8, "IsDouble": 0, "Ratio": 1, "OutResource": "1605,16050010,5"},
        {"Type": 2, "OrderId": 9, "IsDouble": 0, "Ratio": 1, "OutResource": "1606,16060019,1"},
        {"Type": 2, "OrderId": 10, "IsDouble": 0, "Ratio": 1, "OutResource": "1605,16050061,3"},
        {"Type": 2, "OrderId": 11, "IsDouble": 1, "Ratio": 2, "OutResource": ""},
        {"Type": 2, "OrderId": 12, "IsDouble": 0, "Ratio": 1, "OutResource": "1602,16020015,1"},
        {"Type": 2, "OrderId": 13, "IsDouble": 0, "Ratio": 1, "OutResource": "1111,0,500"},
        {"Type": 2, "OrderId": 14, "IsDouble": 0, "Ratio": 1, "OutResource": "1606,16060008,1"},
        {"Type": 2, "OrderId": 15, "IsDouble": 0, "Ratio": 1, "OutResource": "1602,16020023,1"},
        {"Type": 2, "OrderId": 16, "IsDouble": 0, "Ratio": 1, "OutResource": "1111,0,888"},
    ]
    SLOT_RANK_RETURN: list[dict[str, Any]] = [
        {"Rank": 1, "Ratio": 30, "ReturnResource": "1111,0,1000||1606,16060019,1"},
        {"Rank": 2, "Ratio": 20, "ReturnResource": "1111,0,600||1606,16060002,1"},
        {"Rank": 3, "Ratio": 15, "ReturnResource": "1111,0,400||1605,16050001,200"},
        {"Rank": 4, "Ratio": 10, "ReturnResource": "1111,0,250"},
        {"Rank": 5, "Ratio": 8, "ReturnResource": "1111,0,180"},
    ]

    def _ensure_slot_prog(self, event_id: str = "timed_slot") -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate(event_id, self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if inst is None:
            return ev, {}
        prog = inst.setdefault("progress", {})
        prog.setdefault("integral", 0)
        prog.setdefault("ordinary_ratio", 1)
        prog.setdefault("senior_ratio", 1)
        prog.setdefault("spin_count", 0)
        return ev, prog

    def _seed_slot_tickets(self, ev: Any, prog: dict[str, Any]) -> None:
        # R7.9 seeded a different item. Keep that stack and issue the correct ticket once.
        if prog.get("vn_tickets_seeded"):
            return
        prog["vn_tickets_seeded"] = True
        if self._get_goods_qty(self.LOTTERY_TICKET_MODEL_ID) == 0:
            self._grant_resources_from_tuples(
                [(1605, self.LOTTERY_TICKET_MODEL_ID, 10)],
                source="timed_slot_starter_tickets",
                tx_prefix=f"evt:{ev.instance_id}:vn_starter_tickets",
            )
        self.save()

    def _record_slot_recharge(self, amount: int) -> None:
        ev_id = self._resolve_timed_event_id("timed_slot", None, family=self._SLOT_FAMILY)
        ev, prog = self._ensure_slot_prog(ev_id)
        if not ev.eligible:
            return
        self._seed_slot_tickets(ev, prog)
        tickets, remainder = divmod(int(prog.get("recharge_remainder", 0)) + amount, self.SLOT_RECHARGE_QUOTA)
        if tickets:
            self._grant_resources_from_tuples(
                [(1605, self.LOTTERY_TICKET_MODEL_ID, tickets)],
                source="timed_slot_recharge",
                tx_prefix=f"evt:{ev.instance_id}:recharge:{self._player_total_recharged_diamonds()}",
            )
        prog["recharge_remainder"] = remainder

    def _slot_red_dot(self) -> int:
        ev, prog = self._ensure_slot_prog()
        if not ev.eligible:
            return 0
        return int(not prog.get("vn_tickets_seeded") or self._get_goods_qty(self.LOTTERY_TICKET_MODEL_ID) > 0)

    def _build_slot_rank_list(self, instance_id: str, my_integral: int) -> tuple[int, list[dict[str, Any]]]:
        entries = [row for row in self._s1_event_scores(instance_id, "integral", my_integral) if row[2] > 0]
        for name, score in [("BạchSát", 50), ("KhuyểnDạXoa", 35), ("TửVu", 20), ("NgọcTứHồn", 10)]:
            entries.append((f"npc:{name}", f"{name} (NPC)", score))
        return self._event_rank_payload(entries, name_key="Name", score_key="Integral", limit=5)

    def _settle_slot_rank(self, inst: dict[str, Any]) -> None:
        points = int(inst.get("progress", {}).get("integral", 0))
        if points <= 0:
            return
        rank, _ = self._build_slot_rank_list(inst["instance_id"], points)
        inst.setdefault("settlement", {})["rank"] = rank
        reward = next((row for row in self.SLOT_RANK_RETURN if row["Rank"] == rank), None)
        if reward:
            self._push_reward_center_entry(
                source_key=f"slot_rank:{inst['instance_id']}",
                title=f"Kho Báu Quay Thưởng — Hạng {rank}",
                content=f"Thưởng xếp hạng với {points} điểm ở kỳ trước.",
                res_tuples=_parse_res_tuples(reward["ReturnResource"]),
            )

    def _build_slot_payload(self, ev: Any, prog: dict[str, Any]) -> dict[str, Any]:
        my_int = int(prog.get("integral", 0))
        my_rank, rank_list = self._build_slot_rank_list(ev.instance_id, my_int)
        ratio_map = {r["Rank"]: r["Ratio"] for r in self.SLOT_RANK_RETURN}
        return {
            "EndDate": int(ev.end_ts or self.clock.next_midnight_ts()),
            "LuckdrawConfig": {
                "ExchangeQuota": self.SLOT_RECHARGE_QUOTA,
                "ExchangeResource": f"1605,{self.LOTTERY_TICKET_MODEL_ID},1",
                "OrdinaryUseResource": f"1605,{self.LOTTERY_TICKET_MODEL_ID},1",
                "SeniorUseResource": f"1605,{self.LOTTERY_TICKET_MODEL_ID},5",
            },
            "LuckdrawRankreturnConfig": copy.deepcopy(self.SLOT_RANK_RETURN),
            "RankList": rank_list,
            "LuckdrawRewardConfig": copy.deepcopy(self.SLOT_NORMAL_REWARDS + self.SLOT_PRETTY_REWARDS),
            "TimedLuckdrawInfo": {
                "Integral": my_int,
                "RechargeNum": int(prog.get("recharge_remainder", 0)),
                "OrdinaryPlusRatio": int(prog.get("ordinary_ratio", 1)),
                "SeniorPlusRatio": int(prog.get("senior_ratio", 1)),
                "Rank": my_rank,
                "Ratio": ratio_map.get(my_rank, 0),
            },
        }

    def _rpc_timed_luckdraw_get_info(self, _data: Any) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_slot", None, family=self._SLOT_FAMILY)
        ev, prog = self._ensure_slot_prog(ev_id)
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        self._seed_slot_tickets(ev, prog)
        out = self._build_slot_payload(ev, prog)
        self.save()
        return out

    def _rpc_timed_luckdraw_draw(self, data: Any) -> dict[str, Any]:
        slot_type = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 1
        count = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1
        if slot_type not in (1, 2) or count not in (1, 10):
            self._last_rpc_context["status"] = -1
            return {}
        ev_id = self._resolve_timed_event_id("timed_slot", None, family=self._SLOT_FAMILY)
        ev, prog = self._ensure_slot_prog(ev_id)
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}

        self._seed_slot_tickets(ev, prog)
        per_cost = 1 if slot_type == 1 else 5
        total_tickets = per_cost * count
        if not self._consume_goods_qty(self.LOTTERY_TICKET_MODEL_ID, total_tickets):
            self._last_rpc_context["status"] = -1
            return {}

        pool = self.SLOT_NORMAL_REWARDS if slot_type == 1 else self.SLOT_PRETTY_REWARDS
        ratio_key = "ordinary_ratio" if slot_type == 1 else "senior_ratio"
        cur_ratio = max(1, int(prog.get(ratio_key, 1)))

        order_ids: list[int] = []
        tuples: list[tuple[int, int, int]] = []
        for _ in range(count):
            picked = random.choice(pool)
            order_ids.append(int(picked["OrderId"]))
            if int(picked.get("IsDouble", 0)) == 1:
                cur_ratio = max(cur_ratio, int(picked.get("Ratio", 2)))
            else:
                for rt, rm, rn in _parse_res_tuples(str(picked.get("OutResource", ""))):
                    tuples.append((rt, rm, rn * cur_ratio))
                cur_ratio = 1

        prog[ratio_key] = cur_ratio
        prog["integral"] = int(prog.get("integral", 0)) + total_tickets
        prog["spin_count"] = int(prog.get("spin_count", 0)) + count
        base_res = (
            self._grant_resources_from_tuples(
                tuples,
                source=f"timed_slot:t{slot_type}:x{count}",
                tx_prefix=f"evt:{ev.instance_id}:slot:{prog['spin_count']}:{uuid.uuid4()}",
            )
            if tuples
            else []
        )
        payload = self._build_slot_payload(ev, prog)
        payload["OrderId"] = order_ids
        payload["BaseGetGameResourceList"] = base_res
        self.save()
        return payload

    # -------------------- 5. TimedRecruitEquipLayer (4410, Thần Binh Giới Hạn — TW 1.4 XssbModel) --------------------

    XSSB_CREDIT_REWARDS: list[dict[str, Any]] = [
        {"Credit": 50, "CreditReward": "1112,0,150000||1605,16050003,5"},
        {"Credit": 100, "CreditReward": "1111,0,150||1301,13010404,1"},
        {"Credit": 200, "CreditReward": "1111,0,300||1301,13010503,1"},
        {"Credit": 350, "CreditReward": "1111,0,500||1304,13040503,1"},
        {"Credit": 500, "CreditReward": "1111,0,888||1301,13010602,1"},
    ]
    XSSB_RANK_REWARDS: list[dict[str, Any]] = [
        {"RankMin": 1, "RankMax": 1, "RankReward": "1301,13010602,1||1302,13020602,1||1111,0,1000"},
        {"RankMin": 2, "RankMax": 2, "RankReward": "1301,13010503,1||1111,0,600"},
        {"RankMin": 3, "RankMax": 3, "RankReward": "1304,13040503,1||1111,0,400"},
        {"RankMin": 4, "RankMax": 10, "RankReward": "1301,13010404,1||1111,0,200"},
    ]

    def _ensure_xssb_prog(self) -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate("timed_xssb", self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if inst is None:
            return ev, {}
        cfg = self.game_data.get("xssb_model", {})
        prog = inst.setdefault("progress", {})
        prog.setdefault("integral", 0)
        prog.setdefault("reward_ids", [])
        prog.setdefault("call_count", int(cfg.get("getPurpleCD", 9)))
        prog.setdefault("free_date", 0)
        prog.setdefault("pull_seq", 0)
        return ev, prog

    def _xssb_red_dot(self) -> int:
        ev, prog = self._ensure_xssb_prog()
        if not ev.eligible:
            return 0
        if self.now_ts() >= int(prog.get("free_date", 0)):
            return 1
        integral = int(prog.get("integral", 0))
        claimed = set(int(x) for x in prog.get("reward_ids", []))
        return 1 if any(integral >= int(r["Credit"]) and int(r["Credit"]) not in claimed for r in self.XSSB_CREDIT_REWARDS) else 0

    def _build_xssb_rank_list(
        self,
        instance_id: str,
        my_integral: int,
        *,
        include_archived_peers: bool = False,
    ) -> tuple[int, list[dict[str, Any]]]:
        entries: list[dict[str, Any]] = []
        for prof in self._s1_account_profiles():
            pp = prof.state.get("player", {})
            pid = str(pp.get("PlayerId", prof.profile_name))
            pname = str(pp.get("PlayerName", "Hero"))
            if prof is self:
                score = int(my_integral)
                is_me = True
            else:
                p_inst = prof.event_runtime.get_instance(instance_id) if instance_id else None
                if not p_inst or (not include_archived_peers and p_inst.get("archived")):
                    continue
                score = int(p_inst.get("progress", {}).get("integral", 0))
                is_me = False
            if score > 0:
                entries.append({"pid": pid, "Name": pname, "Integral": score, "is_me": is_me, "is_bot": False})
        for bname, bscore in [("ThiếtToáiNha", 220), ("ThiênSinhNha", 160), ("TùngVânNha", 110), ("BạoToáiNha", 70)]:
            entries.append({"pid": f"npc:{bname}", "Name": bname, "Integral": bscore, "is_me": False, "is_bot": True})
        entries.sort(key=lambda r: (-int(r["Integral"]), 1 if r["is_bot"] else 0, str(r["pid"])))
        my_rank = 0
        out: list[dict[str, Any]] = []
        for idx, row in enumerate(entries[:10], start=1):
            if row["is_me"]:
                my_rank = idx
            out.append({"Rank": idx, "Name": row["Name"], "Integral": int(row["Integral"])})
        return my_rank, out

    def _settle_xssb_rank(self, inst: dict[str, Any]) -> None:
        prog = inst.get("progress", {})
        iid = str(inst["instance_id"])
        my_integral = int(prog.get("integral", 0))
        if my_integral <= 0:
            inst.setdefault("settlement", {})["rank"] = 0
            return
        my_rank, _ = self._build_xssb_rank_list(iid, my_integral, include_archived_peers=True)
        settlement = inst.setdefault("settlement", {})
        settlement["rank"] = my_rank
        settlement["integral"] = my_integral
        matched = next(
            (r for r in self.XSSB_RANK_REWARDS if int(r["RankMin"]) <= my_rank <= int(r["RankMax"])),
            None,
        )
        if not matched:
            return
        tuples = _parse_res_tuples(str(matched["RankReward"]))
        if not tuples:
            return
        self._push_reward_center_entry(
            source_key=f"xssb_rank:{iid}",
            title=f"Thần Binh Giới Hạn — Hạng {my_rank}",
            content=f"Chúc mừng đạt hạng {my_rank} ({my_integral} điểm) kỳ {iid}.",
            res_tuples=tuples,
        )

    def _settle_xssb_unclaimed_credits(self, inst: dict[str, Any]) -> None:
        if not bool(self.event_runtime.archive_cfg.get("settle_unclaimed_credit", True)):
            return
        prog = inst.get("progress", {})
        iid = str(inst["instance_id"])
        my_integral = int(prog.get("integral", 0))
        drawn = {int(x) for x in prog.get("reward_ids", [])}
        tuples: list[tuple[int, int, int]] = []
        settled_credits: list[int] = []
        for row in self.XSSB_CREDIT_REWARDS:
            req_c = int(row["Credit"])
            if my_integral >= req_c and req_c not in drawn and not self.event_runtime.is_claimed(iid, f"credit:{req_c}"):
                tuples.extend(_parse_res_tuples(str(row["CreditReward"])))
                settled_credits.append(req_c)
        if not tuples:
            return
        inst.setdefault("settlement", {})["unclaimed_credits"] = settled_credits
        self._push_reward_center_entry(
            source_key=f"xssb_unclaimed_credit:{iid}",
            title="Quà Mốc Tích Lũy Thần Binh Giới Hạn",
            content=f"Kết toán rương tích lũy chưa nhận kỳ {iid}.",
            res_tuples=tuples,
        )

    def _build_xssb_payload(self, ev: Any, prog: dict[str, Any], *, include_static: bool = True) -> dict[str, Any]:
        my_int = int(prog.get("integral", 0))
        my_rank, rank_list = self._build_xssb_rank_list(ev.instance_id, my_int)
        reward_ids = sorted(set(int(x) for x in prog.get("reward_ids", [])))
        info_block = {
            "Integral": my_int,
            "RewardIdStr": ",".join(str(x) for x in reward_ids),
            "CallCount": int(prog.get("call_count", 9)),
            "FreeDate": int(prog.get("free_date", 0)),
            "Rank": my_rank,
        }
        payload: dict[str, Any] = {
            "EndDate": int(ev.end_ts or self.clock.next_midnight_ts()),
            "TimedXssbInfo": info_block,
            "RankList": rank_list,
        }
        if include_static:
            payload["XssbCreditRelationInfo"] = copy.deepcopy(self.XSSB_CREDIT_REWARDS)
            payload["RankReward"] = copy.deepcopy(self.XSSB_RANK_REWARDS)
        return payload

    def _rpc_timed_xssb_get_info(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_xssb_prog()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        out = self._build_xssb_payload(ev, prog, include_static=True)
        self.save()
        return out

    def _rpc_timed_xssb_call_equip(self, data: Any) -> dict[str, Any]:
        rtype = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 1
        count = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 1
        if rtype not in (1, 3) or count not in (1, 10):
            self._last_rpc_context["status"] = -1
            return {}
        ev, prog = self._ensure_xssb_prog()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}

        cfg = self.game_data.get("xssb_model", {})
        now = self.now_ts()
        if rtype == 1:
            if count != 1 or now < int(prog.get("free_date", 0)):
                self._last_rpc_context["status"] = -1
                return {}
            prog["free_date"] = now + max(60, int(cfg.get("freeRecruitCD", 72000)))
        else:
            cost = int(cfg.get("recruitPrice", 280)) if count == 1 else int(cfg.get("recruitPriceTen", 1680))
            if int(self.state["player"].get("Diamond", 0)) < cost:
                self._last_rpc_context["status"] = -1
                return {}
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -cost,
                source=f"timed_xssb:x{count}",
            )

        blue_pool = [13010314, 13020314, 13030314, 13040314]
        purple_pool = [13010404, 13020404, 13030404, 13040404, 13010411, 13020411]
        orange_pool = [13010503, 13020503, 13030503, 13040503]

        interval = int(cfg.get("getPurpleCD", 9))
        call_cnt = int(prog.get("call_count", interval))
        base_res_groups: list[dict[str, Any]] = []
        hit_high = False

        for _ in range(count):
            prog["pull_seq"] = int(prog.get("pull_seq", 0)) + 1
            if call_cnt <= 0:
                emid = random.choice(orange_pool if random.randint(1, 100) <= 30 else purple_pool)
                call_cnt = interval
                hit_high = True
            else:
                roll = random.randint(1, 100)
                if roll <= 10:
                    emid = random.choice(orange_pool)
                    call_cnt = interval
                    hit_high = True
                elif roll <= 35:
                    emid = random.choice(purple_pool)
                    call_cnt = interval
                    hit_high = True
                else:
                    emid = random.choice(blue_pool)
                    call_cnt = max(0, call_cnt - 1)
            if count == 10 and _ == count - 1 and not hit_high:
                emid = random.choice(purple_pool)
                call_cnt = interval

            grp = self._grant_resources_from_tuples(
                [(emid // 10000, emid, 1)],
                source=f"timed_xssb:x{count}",
                tx_prefix=f"evt:{self.profile_name}:{self.state['player']['PlayerId']}:{ev.instance_id}:xssb:{prog['pull_seq']}:{uuid.uuid4()}",
            )
            if grp:
                base_res_groups.extend(grp)

        prog["call_count"] = call_cnt
        credit_add = int(cfg.get("recruitCreditPer", 10)) if count == 1 else int(cfg.get("recruitCreditTen", 110))
        prog["integral"] = int(prog.get("integral", 0)) + credit_add
        self._inc_stat("equip_recruit_count", count)
        self._record_daily_task_progress(14, count)

        payload = self._build_xssb_payload(ev, prog, include_static=True)
        payload["BaseGetGameResourceList"] = base_res_groups
        self.save()
        return payload

    def _rpc_timed_xssb_receive_reward(self, data: Any) -> dict[str, Any]:
        req_credit = int(data[0]) if isinstance(data, list) and data else 0
        ev, prog = self._ensure_xssb_prog()
        if not ev.eligible or int(prog.get("integral", 0)) < req_credit:
            self._last_rpc_context["status"] = -1
            return {}
        row = next((r for r in self.XSSB_CREDIT_REWARDS if int(r["Credit"]) == req_credit), None)
        if not row:
            self._last_rpc_context["status"] = -1
            return {}
        tuples = _parse_res_tuples(str(row["CreditReward"]))
        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "timed_xssb",
            f"credit:{req_credit}",
            lambda idem: self._grant_resources_from_tuples(
                tuples,
                source=f"timed_xssb_chest:{req_credit}",
                tx_prefix=idem,
            ),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        rids = set(int(x) for x in prog.get("reward_ids", []))
        rids.add(req_credit)
        prog["reward_ids"] = sorted(rids)
        payload = self._build_xssb_payload(ev, prog, include_static=True)
        payload["BaseGetGameResourceList"] = base_res
        self.save()
        return payload

    # -------------------- 6. YiJiDuoBaoLayer (7800, Di Tích Đoạt Bảo) --------------------

    def _ensure_yiyuan_prog(self) -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate("yiyuan_duobao", self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if inst is None:
            return ev, {}
        prog = inst.setdefault("progress", {})
        prog.setdefault("status", 0)       # 0 = not joined, 1 = joined
        prog.setdefault("draw_status", 0)  # 0 = cannot draw, 1 = can draw, 2 = drawn
        prog.setdefault("join_num", 0)
        return ev, prog

    def _yiyuan_red_dot(self) -> int:
        ev, prog = self._ensure_yiyuan_prog()
        if not ev.eligible:
            return 0
        return 1 if int(prog.get("draw_status", 0)) < 2 else 0

    def _build_yiyuan_payload(self, ev: Any, prog: dict[str, Any]) -> dict[str, Any]:
        now = self.now_ts()
        end_ts = int(ev.end_ts or self.clock.next_midnight_ts())
        joined = int(prog.get("status", 0)) >= 1
        # Once joined, shift EndTime <= now < DrawEndTime so player can immediately claim the treasure reward offline!
        join_end_time = (now - 10) if joined else end_ts
        draw_end_time = end_ts + 3600
        winners: list[dict[str, Any]] = []
        for idx, prof in enumerate(self._s1_account_profiles()[:3], start=1):
            p = prof.state.get("player", {})
            winners.append(
                {
                    "ID": 10000 + idx,
                    "Name": str(p.get("PlayerName", "Hero")),
                    "HeadImageId": int(p.get("HeadImageId", 12010001)),
                    "GuildName": str(p.get("GuildName", "") or "Liên Minh S1"),
                }
            )
        recharged = max(60, self._player_total_recharged_diamonds())
        return {
            "ID": 1,
            "Status": 2 if int(prog.get("draw_status", 0)) >= 1 else int(prog.get("status", 0)),
            "JoinNum": int(prog.get("join_num", 0)),
            "Num": len(winners) + (1 if joined else 0),
            "FakeMin": 10,
            "NeedGamePoint": 60,
            "GamePoint": recharged,
            "EndTime": join_end_time,
            "DrawEndTime": draw_end_time,
            "WinPlayers": winners,
            "YiYuanDrawNums": {
                "Status": int(prog.get("draw_status", 0)),
                "ResourceList": _res_dicts([(1606, 16060019, 1), (1111, 0, 388)]),
                "CResourceList": _res_dicts([(1111, 0, 100), (1605, 16050061, 2)]),
            },
        }

    def _rpc_yiyuan_get_info(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_yiyuan_prog()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        out = self._build_yiyuan_payload(ev, prog)
        self.save()
        return out

    def _rpc_yiyuan_join(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_yiyuan_prog()
        if not ev.eligible or int(prog.get("status", 0)) != 0:
            self._last_rpc_context["status"] = -1
            return {}
        prog["status"] = 1
        prog["draw_status"] = 1
        prog["join_num"] = 10088
        self.save()
        return {"JoinNum": 10088}

    def _rpc_yiyuan_draw_reward(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_yiyuan_prog()
        if not ev.eligible or int(prog.get("draw_status", 0)) != 1:
            self._last_rpc_context["status"] = -1
            return {}
        tuples = [(1606, 16060019, 1), (1111, 0, 388), (1605, 16050061, 2)]
        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "yiyuan_duobao",
            "draw:1",
            lambda idem: self._grant_resources_from_tuples(
                tuples,
                source="yiyuan_duobao_reward",
                tx_prefix=idem,
            ),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        prog["draw_status"] = 2
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # -------------------- 7. TimeSpike (6800) & TimeSpikeKing / TimesMiaosha (7000) --------------------

    def _ensure_timespike_prog(self) -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate("time_spike", self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if inst is None:
            return ev, {}
        prog = inst.setdefault("progress", {})
        prog.setdefault("claimed_ids", [])
        return ev, prog

    def _timespike_active_row(self) -> dict[str, Any] | None:
        _ev, prog = self._ensure_timespike_prog()
        claimed = set(int(x) for x in prog.get("claimed_ids", []))
        lv = int(self.state.get("player", {}).get("Lv", 1))
        rows = sorted(self.game_data.get("timespike", {}).values(), key=lambda r: int(r.get("ID", 0)))
        for row in rows:
            rid = int(row.get("ID", 0))
            if rid not in claimed and lv >= int(row.get("triggerLV", 11)):
                return row
        # Fallback to first un-claimed row so player can always preview/play
        for row in rows:
            if int(row.get("ID", 0)) not in claimed:
                return row
        return None

    def _timespike_red_dot(self) -> int:
        row = self._timespike_active_row()
        if "player" in self.state:
            self.state["player"]["TimespikeTriggerLv"] = int(row["triggerLV"]) if row else 0
        return 1 if row is not None else 0

    def _rpc_timespike_get_info(self, _data: Any) -> dict[str, Any]:
        ev, _prog = self._ensure_timespike_prog()
        row = self._timespike_active_row()
        if not ev.eligible or not row:
            if "player" in self.state:
                self.state["player"]["TimespikeTriggerLv"] = 0
            return {"EndDate": 0, "TriggerLv": 0, "ReceiveMoney": 0}
        trig = int(row["triggerLV"])
        need_money = int(row.get("receiveCondition", 6))
        rec_money = max(need_money, self._player_total_recharged_diamonds())
        self.state["player"]["TimespikeTriggerLv"] = trig
        self.save()
        return {
            "EndDate": int(ev.end_ts or (self.now_ts() + 43200)),
            "TriggerLv": trig,
            "ReceiveMoney": rec_money,
        }

    def _rpc_timespike_received_reward(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_timespike_prog()
        row = self._timespike_active_row()
        if not ev.eligible or not row:
            self._last_rpc_context["status"] = -1
            return {}
        rid = int(row["ID"])
        price = int(row.get("buyPrice", 299))
        if int(self.state["player"].get("Diamond", 0)) < price:
            self._last_rpc_context["status"] = -1
            return {}
        tuples = _parse_res_tuples(str(row.get("reward", "")))
        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "time_spike",
            f"tier:{rid}",
            lambda idem: self._grant_resources_from_tuples(
                tuples,
                source=f"timespike:{rid}",
                tx_prefix=idem,
            ),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.ledger.apply_player_delta(
            self.state["player"],
            self.profile_name,
            "Diamond",
            -price,
            source=f"timespike_buy:{rid}",
        )
        claimed = set(int(x) for x in prog.get("claimed_ids", []))
        claimed.add(rid)
        prog["claimed_ids"] = sorted(claimed)
        self._timespike_red_dot()
        self.save()
        return {"BaseGetGameResourceList": base_res}

    MIAOSHA_PACKS: list[dict[str, Any]] = [
        {"ActivityId": 7000, "Id": 1, "ChargeMoney": 30, "BuyNum": 188, "GetResource": "1605,16050061,3||1605,16050055,3||1112,0,200000"},
        {"ActivityId": 7000, "Id": 2, "ChargeMoney": 98, "BuyNum": 488, "GetResource": "1606,16060002,1||1605,16050001,150||1112,0,500000"},
        {"ActivityId": 7000, "Id": 3, "ChargeMoney": 198, "BuyNum": 888, "GetResource": "1606,16060019,1||1602,16020023,1||1112,0,1000000"},
    ]

    def _ensure_miaosha_prog(self) -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate("time_miaosha", self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if inst is None:
            return ev, {}
        prog = inst.setdefault("progress", {})
        prog.setdefault("claimed_ids", [])
        return ev, prog

    def _miaosha_red_dot(self) -> int:
        ev, prog = self._ensure_miaosha_prog()
        if not ev.eligible:
            return 0
        claimed = set(int(x) for x in prog.get("claimed_ids", []))
        return 1 if len(claimed) < len(self.MIAOSHA_PACKS) else 0

    def _rpc_times_miaosha_get_info(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_miaosha_prog()
        if not ev.eligible:
            self._last_rpc_context["status"] = -1
            return {}
        claimed = set(int(x) for x in prog.get("claimed_ids", []))
        end_ts = int(ev.end_ts or self.clock.next_midnight_ts())
        cfg_list: list[dict[str, Any]] = []
        for p in self.MIAOSHA_PACKS:
            pid = int(p["Id"])
            cfg_list.append(
                {
                    "ActivityId": int(p["ActivityId"]),
                    "Id": pid,
                    "ChargeMoney": int(p["ChargeMoney"]),
                    "BuyNum": int(p["BuyNum"]),
                    "GetResource": str(p["GetResource"]),
                    "EndDate": end_ts,
                    "IsReceive": 2 if pid in claimed else 1,
                }
            )
        self.save()
        return {"Config": cfg_list}

    def _rpc_times_miaosha_receive(self, data: Any) -> dict[str, Any]:
        pid = int(data[1]) if isinstance(data, list) and len(data) >= 2 else (int(data[0]) if isinstance(data, list) and data else 0)
        ev, prog = self._ensure_miaosha_prog()
        pack = next((p for p in self.MIAOSHA_PACKS if int(p["Id"]) == pid), None)
        if not ev.eligible or not pack:
            self._last_rpc_context["status"] = -1
            return {}
        price = int(pack["BuyNum"])
        if int(self.state["player"].get("Diamond", 0)) < price:
            self._last_rpc_context["status"] = -1
            return {}
        tuples = _parse_res_tuples(str(pack["GetResource"]))
        ok, base_res, _reason = self.event_runtime.claim_milestone(
            "time_miaosha",
            f"pack:{pid}",
            lambda idem: self._grant_resources_from_tuples(
                tuples,
                source=f"times_miaosha:{pid}",
                tx_prefix=idem,
            ),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.ledger.apply_player_delta(
            self.state["player"],
            self.profile_name,
            "Diamond",
            -price,
            source=f"times_miaosha_buy:{pid}",
        )
        claimed = set(int(x) for x in prog.get("claimed_ids", []))
        claimed.add(pid)
        prog["claimed_ids"] = sorted(claimed)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # -------------------- 8. TimedInfo / TimedChargeGift / TimedChargeScore / TimedLimitExchange --------------------

    CHARGE_SINGLE_TIERS: list[tuple[int, str]] = [
        (60, "1111,0,60||1112,0,100000||1605,16050061,1"),
        (300, "1111,0,180||1605,16050001,100||1605,16050055,2"),
        (980, "1111,0,500||1606,16060002,1||1605,16050061,3"),
        (1980, "1111,0,1000||1606,16060019,1||1602,16020023,1"),
    ]
    CHARGE_TOTAL_TIERS: list[tuple[int, str]] = [
        (60, "1112,0,150000||1605,16050061,2"),
        (300, "1111,0,200||1605,16050055,3||1605,16050001,100"),
        (1000, "1111,0,500||1606,16060002,1||1605,16050010,5"),
        (3000, "1111,0,1200||1606,16060019,1||1606,16060008,1"),
    ]
    USE_TOTAL_TIERS: list[tuple[int, str]] = [
        (100, "1112,0,100000||1605,16050061,1"),
        (500, "1112,0,250000||1605,16050055,2||1605,16050001,80"),
        (1500, "1111,0,300||1606,16060002,1||1605,16050061,3"),
        (3000, "1111,0,600||1606,16060019,1||1602,16020023,1"),
    ]
    CHARGE_DAYS_TIERS: list[tuple[int, int, str]] = [
        (1, 1, "1111,0,100||1605,16050061,1"),
        (2, 2, "1111,0,200||1605,16050055,2"),
        (3, 3, "1111,0,350||1606,16060002,1"),
        (5, 5, "1111,0,688||1606,16060019,1"),
    ]
    DOUBLE_DIAMOND_TIERS: list[int] = [60, 300, 980, 1980]
    DAY_LOGIN_TIERS: list[tuple[int, str]] = [
        (1, "1111,0,88||1605,16050061,1||1605,16050055,1"),
        (2, "1111,0,128||1112,0,200000||1605,16050001,80"),
        (3, "1111,0,188||1606,16060002,1||1605,16050061,2"),
        (5, "1111,0,388||1606,16060019,1||1605,16050055,3"),
    ]

    def _eval_timed_sub(self, event_id: str) -> tuple[Any, dict[str, Any]]:
        self._sync_events()
        ev = self.event_runtime.evaluate(event_id, self.state["player"])
        inst = self.event_runtime.get_instance(ev.instance_id) if ev.instance_id else None
        if inst is None:
            return ev, {}
        prog = inst.setdefault("progress", {})
        return ev, prog

    CHARGE_PERIODS = (
        "timed_charge_single", "timed_charge_total", "timed_accum_days",
        "timed_double_diamond", "timed_recharge_rank", "timed_charge_gift",
        "timed_points_mall", "timed_critical_tasks",
        "festival_charge_single", "festival_charge_total", "festival_charge_gift", "festival_points_mall",
        "holiday_charge_single", "holiday_charge_total", "holiday_charge_gift", "holiday_points_mall",
    )
    SPEND_PERIODS = (
        "timed_use_total", "timed_consume_rank", "timed_critical_tasks",
        "festival_use_total", "holiday_use_total",
    )

    def _add_period_charge(self, amounts: dict[str, Any], when: int, amount: int) -> None:
        amounts["charged"] += amount
        amounts["max_charge"] = max(amounts["max_charge"], amount)
        day = self.clock.today_str(when)
        amounts["by_day"][day] = amounts["by_day"].get(day, 0) + amount

    def _period_economy(self, ev: Any, progress: dict[str, Any]) -> dict[str, Any]:
        initial = {"charged": 0, "max_charge": 0, "spent": 0, "by_day": {}}
        if not ev.eligible:
            return initial
        if "economy" not in progress:
            # Recover dated orders for the existing window only. Manual replay starts clean,
            # including when the old and new instance overlap at the same clock second.
            reset_seq = self.event_runtime.archive_cfg.get("manual_reset_seq", {}).get(ev.event_id, 0)
            if ev.event_id in self.CHARGE_PERIODS and ev.start_ts is not None and ev.archive_mode != "manual" and not reset_seq:
                end = min(ev.end_ts or self.now_ts() + 1, self.now_ts() + 1)
                for when, amount in self._legacy_period_charges(ev.start_ts, end):
                    self._add_period_charge(initial, when, amount)
            progress["economy"] = initial
        return progress["economy"]

    def _record_period_economy(self, *, charged: int = 0, spent: int = 0) -> None:
        now = self.now_ts()
        for event_id in self.CHARGE_PERIODS if charged else self.SPEND_PERIODS:
            ev = self.event_runtime.evaluate(event_id, self.state["player"])
            if not ev.eligible:
                continue
            inst = self.event_runtime.get_instance(ev.instance_id)
            if inst is None:
                continue
            amounts = self._period_economy(ev, inst.setdefault("progress", {}))
            if charged:
                self._add_period_charge(amounts, now, charged)
            amounts["spent"] += spent

    def _charge_day_progress(self, ev: Any, progress: dict[str, Any]) -> tuple[int, int]:
        by_day = self._period_economy(ev, progress)["by_day"]
        longest = streak = previous = 0
        for day in sorted(key for key, amount in by_day.items() if amount >= 60):
            ordinal = date.fromisoformat(day).toordinal()
            streak = streak + 1 if ordinal == previous + 1 else 1
            longest = max(longest, streak)
            previous = ordinal
        return longest, int(by_day.get(self.clock.today_str(), 0))

    def _rpc_timed_info_get_charge_single(self, data: Any = None) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_charge_single", data, family=self._CHARGE_SINGLE_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        max_single = self._period_economy(ev, prog)["max_charge"]
        rows: list[dict[str, Any]] = []
        for tid, res_str in self.CHARGE_SINGLE_TIERS:
            claimed = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"tier:{tid}"))
            status = 2 if claimed else (1 if max_single >= tid else 0)
            rows.append({"Id": tid, "Status": status, "ResourceList": _res_dicts(_parse_res_tuples(res_str))})
        return {
            "HLHKSingleRecharge": int(ev.end_ts or self.clock.next_midnight_ts()),
            "ChargeMaxSingleReward": max_single,
            "ChargeSingleDrawNums": rows,
        }

    def _rpc_timed_info_draw_charge_single(self, data: Any) -> dict[str, Any]:
        ev_id, tid = self._extract_act_and_arg(data, "timed_charge_single", self._CHARGE_SINGLE_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        max_single = self._period_economy(ev, prog)["max_charge"]
        res_str = next((rs for t, rs in self.CHARGE_SINGLE_TIERS if t == tid), None)
        if not res_str or max_single < tid:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _ = self.event_runtime.claim_milestone(
            ev_id,
            f"tier:{tid}",
            lambda idem: self._grant_resources_from_tuples(_parse_res_tuples(res_str), source=f"charge_single:{tid}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_timed_info_get_charge_total(self, data: Any = None) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_charge_total", data, family=self._CHARGE_TOTAL_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        total_c = self._period_economy(ev, prog)["charged"]
        rows: list[dict[str, Any]] = []
        for tid, res_str in self.CHARGE_TOTAL_TIERS:
            claimed = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"tier:{tid}"))
            status = 2 if claimed else (1 if total_c >= tid else 0)
            rows.append({"Id": tid, "Status": status, "ResourceList": _res_dicts(_parse_res_tuples(res_str))})
        return {
            "HLHKTotalRecharge": int(ev.end_ts or self.clock.next_midnight_ts()),
            "ChargeTotalReward": total_c,
            "ChargeTotalDrawNums": rows,
        }

    def _rpc_timed_info_draw_charge_total(self, data: Any) -> dict[str, Any]:
        ev_id, tid = self._extract_act_and_arg(data, "timed_charge_total", self._CHARGE_TOTAL_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        total_c = self._period_economy(ev, prog)["charged"]
        res_str = next((rs for t, rs in self.CHARGE_TOTAL_TIERS if t == tid), None)
        if not res_str or total_c < tid:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _ = self.event_runtime.claim_milestone(
            ev_id,
            f"tier:{tid}",
            lambda idem: self._grant_resources_from_tuples(_parse_res_tuples(res_str), source=f"charge_total:{tid}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_timed_info_get_use_total(self, data: Any = None) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_use_total", data, family=self._USE_TOTAL_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        total_u = self._period_economy(ev, prog)["spent"]
        rows: list[dict[str, Any]] = []
        for tid, res_str in self.USE_TOTAL_TIERS:
            claimed = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"tier:{tid}"))
            status = 2 if claimed else (1 if total_u >= tid else 0)
            rows.append({"Id": tid, "Status": status, "ResourceList": _res_dicts(_parse_res_tuples(res_str))})
        return {
            "HLHKUse": int(ev.end_ts or self.clock.next_midnight_ts()),
            "UseTotalReward": total_u,
            "UseTotalDrawNums": rows,
        }

    def _rpc_timed_info_draw_use_total(self, data: Any) -> dict[str, Any]:
        ev_id, tid = self._extract_act_and_arg(data, "timed_use_total", self._USE_TOTAL_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        total_u = self._period_economy(ev, prog)["spent"]
        res_str = next((rs for t, rs in self.USE_TOTAL_TIERS if t == tid), None)
        if not res_str or total_u < tid:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _ = self.event_runtime.claim_milestone(
            ev_id,
            f"tier:{tid}",
            lambda idem: self._grant_resources_from_tuples(_parse_res_tuples(res_str), source=f"use_total:{tid}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_timed_info_get_charge_days(self, data: Any) -> list[dict[str, Any]]:
        act_id = int(data[0]) if isinstance(data, list) and data else 4405
        ev, prog = self._eval_timed_sub("timed_accum_days")
        days_cnt, today_charge = self._charge_day_progress(ev, prog)
        rows: list[dict[str, Any]] = []
        for tid, need_d, res_str in self.CHARGE_DAYS_TIERS:
            claimed = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"day:{tid}"))
            status = 2 if claimed else (1 if days_cnt >= need_d else 0)
            rows.append({"Id": tid, "NeedValue": need_d, "Status": status, "ResourceList": _res_dicts(_parse_res_tuples(res_str))})
        return [
            {
                "ActivityId": act_id,
                "ChargeDaysEndTime": int(ev.end_ts or self.clock.next_midnight_ts()),
                "ChargeDaysTotal": days_cnt,
                "DailyNum": today_charge,
                "NeedNum": 60,
                "ChargeDaysDrawNums": rows,
            }
        ]

    def _rpc_timed_info_draw_charge_days(self, data: Any) -> dict[str, Any]:
        tid = int(data[1]) if isinstance(data, list) and len(data) >= 2 else (int(data[0]) if isinstance(data, list) and data else 0)
        ev, prog = self._eval_timed_sub("timed_accum_days")
        days_cnt, _today_charge = self._charge_day_progress(ev, prog)
        row = next(((need_d, rs) for t, need_d, rs in self.CHARGE_DAYS_TIERS if t == tid), None)
        if not row or days_cnt < row[0]:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _ = self.event_runtime.claim_milestone(
            "timed_accum_days",
            f"day:{tid}",
            lambda idem: self._grant_resources_from_tuples(_parse_res_tuples(row[1]), source=f"charge_days:{tid}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_timed_info_get_double_diamond(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._eval_timed_sub("timed_double_diamond")
        recharged = self._period_economy(ev, prog)["max_charge"]
        rows: list[dict[str, Any]] = []
        for tid in self.DOUBLE_DIAMOND_TIERS:
            claimed = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"tier:{tid}"))
            status = 2 if claimed else (1 if recharged >= tid else 0)
            rows.append({"Id": tid, "Status": status})
        return {
            "EndTime": int(ev.end_ts or self.clock.next_midnight_ts()),
            "ChargeMaxMoney": recharged,
            "ChargeDoubleDiamonDrawNums": rows,
        }

    def _rpc_timed_info_draw_double_diamond(self, data: Any) -> dict[str, Any]:
        ev, prog = self._eval_timed_sub("timed_double_diamond")
        tid = int(data[0]) if isinstance(data, list) and data else 0
        recharged = self._period_economy(ev, prog)["max_charge"]
        if tid not in self.DOUBLE_DIAMOND_TIERS or recharged < tid:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _ = self.event_runtime.claim_milestone(
            "timed_double_diamond",
            f"tier:{tid}",
            lambda idem: self._grant_resources_from_tuples([(1111, 0, tid)], source=f"double_diamond:{tid}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_timed_info_get_accumulate_login(self, data: Any) -> list[dict[str, Any]]:
        act_id = int(data[0]) if isinstance(data, list) and data else 4427
        ev_id = self._resolve_timed_event_id("timed_day_login", data, family=self._DAY_LOGIN_FAMILY)
        ev, _prog = self._eval_timed_sub(ev_id)
        login_days = max(1, int(self.state.get("gift_login", {}).get("sign_days", 1)))
        rows: list[dict[str, Any]] = []
        for day_num, res_str in self.DAY_LOGIN_TIERS:
            claimed = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"day:{day_num}"))
            status = 2 if claimed else (1 if login_days >= day_num else 0)
            rows.append({"Day": day_num, "Status": status, "ResourceList": _res_dicts(_parse_res_tuples(res_str))})
        return [
            {
                "ActivityId": act_id,
                "EndTime": int(ev.end_ts or self.clock.next_midnight_ts()),
                "Days": login_days,
                "DrawInfo": rows,
            }
        ]

    def _rpc_timed_info_draw_accumulate_login(self, data: Any) -> dict[str, Any]:
        ev_id, day_num = self._extract_act_and_arg(data, "timed_day_login", self._DAY_LOGIN_FAMILY)
        login_days = max(1, int(self.state.get("gift_login", {}).get("sign_days", 1)))
        res_str = next((rs for d, rs in self.DAY_LOGIN_TIERS if d == day_num), None)
        if not res_str or login_days < day_num:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _ = self.event_runtime.claim_milestone(
            ev_id,
            f"day:{day_num}",
            lambda idem: self._grant_resources_from_tuples(_parse_res_tuples(res_str), source=f"timed_day_login:{day_num}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # ChargeRankLayer (4421 BXH Nạp & 4422 BXH Tiêu Phí)
    RANK_REWARD_TEMPLATE: list[tuple[int, int, str]] = [
        (1, 1000, "1606,16060019,1||1111,0,888"),
        (2, 500, "1606,16060002,1||1111,0,500"),
        (3, 300, "1605,16050001,200||1111,0,300"),
        (4, 100, "1605,16050061,3||1111,0,150"),
        (5, 60, "1605,16050055,2||1111,0,100"),
    ]

    def _compute_charge_or_use_rank(
        self,
        instance_id: str,
        my_val: int,
        *,
        is_charge: bool,
        include_archived_peers: bool = False,
    ) -> tuple[int, list[dict[str, Any]]]:
        key = "charged" if is_charge else "spent"
        entries: list[dict[str, Any]] = []
        for prof in self._s1_account_profiles():
            pp = prof.state.get("player", {})
            pid = str(pp.get("PlayerId", prof.profile_name))
            pname = str(pp.get("PlayerName", "Hero"))
            is_me = prof is self
            inst = prof.event_runtime.get_instance(instance_id) if instance_id else None
            if not is_me and (not inst or (not include_archived_peers and inst.get("archived"))):
                continue
            value = int(my_val) if is_me else int(inst.get("progress", {}).get("economy", {}).get(key, 0))
            entries.append({"pid": pid, "Name": pname, "Val": value, "is_me": is_me, "is_bot": False})
        peers = [("BạchSát", 1200), ("KhuyểnDạXoa", 800), ("TửVu", 450), ("NgọcTứHồn", 200), ("PhongKhuyển", 80)]
        for bname, bval in peers:
            entries.append({"pid": f"npc:{bname}", "Name": bname, "Val": bval, "is_me": False, "is_bot": True})
        entries.sort(key=lambda r: (-int(r["Val"]), 1 if r["is_bot"] else 0, str(r["pid"])))

        my_rank = -1
        rewards_out: list[dict[str, Any]] = []
        for idx, (r_num, min_need, res_str) in enumerate(self.RANK_REWARD_TEMPLATE):
            occupant = entries[idx] if idx < len(entries) and int(entries[idx]["Val"]) >= min_need else None
            if occupant and occupant["is_me"]:
                my_rank = r_num
            rewards_out.append(
                {
                    "Num": r_num,
                    "NeedMinNum": min_need,
                    "PlayerName": occupant["Name"] if occupant else "",
                    "PlayerNum": int(occupant["Val"]) if occupant else 0,
                    "ResourceList": res_str,
                }
            )
        return my_rank, rewards_out

    def _build_charge_or_use_rank(self, *, is_charge: bool) -> dict[str, Any]:
        event_id = "timed_recharge_rank" if is_charge else "timed_consume_rank"
        ev, progress = self._eval_timed_sub(event_id)
        key = "charged" if is_charge else "spent"
        my_val = int(self._period_economy(ev, progress)[key])
        my_rank, rewards_out = self._compute_charge_or_use_rank(
            str(ev.instance_id or ""),
            my_val,
            is_charge=is_charge,
            include_archived_peers=False,
        )
        return {
            "SelfIndex": my_rank,
            "SelfRank": my_rank,
            "Num": my_val,
            "Rewards": rewards_out,
        }

    def _settle_charge_or_use_rank(self, inst: dict[str, Any], *, is_charge: bool) -> None:
        key = "charged" if is_charge else "spent"
        iid = str(inst["instance_id"])
        my_val = int(inst.get("progress", {}).get("economy", {}).get(key, 0))
        settlement = inst.setdefault("settlement", {})
        if my_val <= 0:
            settlement["rank"] = 0
            return
        my_rank, _ = self._compute_charge_or_use_rank(
            iid,
            my_val,
            is_charge=is_charge,
            include_archived_peers=True,
        )
        settlement["rank"] = my_rank if my_rank > 0 else 0
        settlement["value"] = my_val
        if my_rank <= 0:
            return
        matched = next((row for row in self.RANK_REWARD_TEMPLATE if int(row[0]) == my_rank), None)
        if not matched:
            return
        tuples = _parse_res_tuples(matched[2])
        if not tuples:
            return
        if is_charge:
            self._push_reward_center_entry(
                source_key=f"recharge_rank:{iid}",
                title=f"BXH Nạp Kim Cương — Hạng {my_rank}",
                content=f"Chúc mừng đạt hạng {my_rank} (đã nạp {my_val} KC) kỳ {iid}.",
                res_tuples=tuples,
            )
        else:
            self._push_reward_center_entry(
                source_key=f"consume_rank:{iid}",
                title=f"BXH Tiêu Kim Cương — Hạng {my_rank}",
                content=f"Chúc mừng đạt hạng {my_rank} (đã tiêu {my_val} KC) kỳ {iid}.",
                res_tuples=tuples,
            )

    def _rpc_timed_info_get_charge_rank(self, _data: Any) -> dict[str, Any]:
        return self._build_charge_or_use_rank(is_charge=True)

    def _rpc_timed_info_get_use_rank(self, _data: Any) -> dict[str, Any]:
        return self._build_charge_or_use_rank(is_charge=False)

    # TimedChargeGiftLayer (4429, Quà Nạp Tự Chọn)
    CHARGE_GIFT_TIERS: list[tuple[int, list[tuple[int, str]]]] = [
        (
            60,
            [
                (101, "1605,16050061,3||1112,0,150000"),
                (102, "1605,16050055,3||1112,0,150000"),
                (103, "1605,16050001,100||1112,0,150000"),
            ],
        ),
        (
            300,
            [
                (201, "1606,16060002,1||1111,0,150"),
                (202, "1602,16020013,1||1111,0,150"),
                (203, "1605,16050010,5||1111,0,150"),
            ],
        ),
    ]

    def _rpc_timed_charge_gift_get_info(self, data: Any = None) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_charge_gift", data, family=self._CHARGE_GIFT_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        claimed = set(int(x) for x in prog.setdefault("claimed_ids", []))
        recharged = self._period_economy(ev, prog)["charged"]
        info_list: list[dict[str, Any]] = []
        for money, opts in self.CHARGE_GIFT_TIERS:
            claimed_in_tier = sum(1 for oid, _ in opts if oid in claimed)
            can_cnt = max(0, min(3, recharged // money) - claimed_in_tier)
            rel_list: list[dict[str, Any]] = []
            for oid, res_str in opts:
                # 1 = already claimed, 2 = claimable, 3 = locked
                can_rec = 1 if oid in claimed else (2 if can_cnt > 0 else 3)
                rel_list.append(
                    {
                        "Id": oid,
                        "CanReceive": can_rec,
                        "BaseGameResource": _res_dicts(_parse_res_tuples(res_str)),
                    }
                )
            info_list.append(
                {
                    "ChargeMoney": money,
                    "CanReceiveCount": can_cnt,
                    "ChargeGiftRelInfo": rel_list,
                }
            )
        self.save()
        return {
            "EndDate": int(ev.end_ts or self.clock.next_midnight_ts()),
            "ChargeGiftInfo": info_list,
        }

    def _rpc_timed_charge_gift_receive(self, data: Any) -> dict[str, Any]:
        ev_id, oid = self._extract_act_and_arg(data, "timed_charge_gift", self._CHARGE_GIFT_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        tier = next(((money, opts, rs) for money, opts in self.CHARGE_GIFT_TIERS
                     for option_id, rs in opts if option_id == oid), None)
        if not ev.eligible or not tier:
            self._last_rpc_context["status"] = -1
            return {}
        money, options, res_str = tier
        claimed = set(prog.get("claimed_ids", []))
        quota = min(3, self._period_economy(ev, prog)["charged"] // money)
        used = sum(option_id in claimed for option_id, _ in options)
        if oid in claimed or used >= quota:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _ = self.event_runtime.claim_milestone(
            ev_id,
            f"opt:{oid}",
            lambda idem: self._grant_resources_from_tuples(_parse_res_tuples(res_str), source=f"charge_gift:{oid}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        claimed.add(oid)
        prog["claimed_ids"] = sorted(claimed)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # TimedPointsMallLayer (4428, Shop Điểm Nạp)
    POINTS_MALL_ITEMS: list[dict[str, Any]] = [
        {"id": 1, "Reward": f"1605,{GOLDEN_HAMMER_MODEL_ID},1", "NeedScore": 20, "Num": 10, "Discount": 0.8},
        {"id": 2, "Reward": f"1605,{LOTTERY_TICKET_MODEL_ID},1", "NeedScore": 20, "Num": 10, "Discount": 0.8},
        {"id": 3, "Reward": "1605,16050001,50", "NeedScore": 30, "Num": 5, "Discount": 0.9},
        {"id": 4, "Reward": "1606,16060002,1", "NeedScore": 100, "Num": 3, "Discount": 0.8},
        {"id": 5, "Reward": "1606,16060019,1", "NeedScore": 250, "Num": 2, "Discount": 0.7},
        {"id": 6, "Reward": "1602,16020023,1", "NeedScore": 300, "Num": 2, "Discount": 0.7},
    ]

    def _extract_act_and_buy_args(
        self, data: Any, default_event_id: str, family: tuple[str, ...]
    ) -> tuple[str, int, int]:
        has_act = False
        if isinstance(data, list) and len(data) >= 2 and data[0] is not None:
            try:
                has_act = self.ACTIVITY_ID_TO_EVENT_ID.get(int(data[0])) in family
            except (TypeError, ValueError):
                has_act = False
        ev_id = self._resolve_timed_event_id(default_event_id, data if has_act else None, family=family)
        item_id = int(data[1]) if isinstance(data, list) and len(data) >= 2 else (int(data[0]) if isinstance(data, list) and data else 0)
        count = int(data[2]) if isinstance(data, list) and len(data) >= 3 else 1
        return ev_id, item_id, max(1, count)

    def _build_points_mall_payload(self, ev: Any, prog: dict[str, Any]) -> dict[str, Any]:
        spent_score = int(prog.get("spent_score", 0))
        total_score = self._period_economy(ev, prog)["charged"]
        cur_score = max(0, total_score - spent_score)
        bought_map = prog.setdefault("bought", {})
        goods_info: list[dict[str, Any]] = []
        for item in self.POINTS_MALL_ITEMS:
            iid = str(item["id"])
            rem = max(0, int(item["Num"]) - int(bought_map.get(iid, 0)))
            goods_info.append(
                {
                    "id": int(item["id"]),
                    "Reward": str(item["Reward"]),
                    "NeedScore": int(item["NeedScore"]),
                    "Num": rem,
                    "Discount": float(item["Discount"]),
                }
            )
        return {
            "EndDate": int(ev.end_ts or self.clock.next_midnight_ts()),
            "Score": cur_score,
            "GoodsInfo": goods_info,
        }

    def _rpc_timed_charge_score_get_list(self, data: Any = None) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_points_mall", data, family=self._POINTS_MALL_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        out = self._build_points_mall_payload(ev, prog)
        self.save()
        return out

    def _rpc_timed_charge_score_buy(self, data: Any) -> dict[str, Any]:
        ev_id, item_id, count = self._extract_act_and_buy_args(data, "timed_points_mall", self._POINTS_MALL_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        item = next((x for x in self.POINTS_MALL_ITEMS if int(x["id"]) == item_id), None)
        if not ev.eligible or not item:
            self._last_rpc_context["status"] = -1
            return {}
        payload_before = self._build_points_mall_payload(ev, prog)
        cur_score = int(payload_before["Score"])
        bought_map = prog.setdefault("bought", {})
        rem = max(0, int(item["Num"]) - int(bought_map.get(str(item_id), 0)))
        need_score = int(item["NeedScore"]) * count
        if count > rem or cur_score < need_score:
            self._last_rpc_context["status"] = -1
            return {}
        bought_map[str(item_id)] = int(bought_map.get(str(item_id), 0)) + count
        prog["spent_score"] = int(prog.get("spent_score", 0)) + need_score
        tuples = [(rt, rm, rn * count) for rt, rm, rn in _parse_res_tuples(str(item["Reward"]))]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"points_mall:{item_id}:x{count}",
            tx_prefix=f"evt:{ev.instance_id}:pmall:{item_id}:{bought_map[str(item_id)]}:{uuid.uuid4()}",
        )
        out = self._build_points_mall_payload(ev, prog)
        out["BaseGetGameResourceList"] = base_res
        self.save()
        return out

    # TimedExchange (4406, Đổi Thưởng Hạn Giờ)
    TIMED_EXCHANGE_RECIPES: list[dict[str, Any]] = [
        {
            "Serial": 1,
            "GlobalNum": 99,
            "PersonalNum": 10,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1112, 0, 50000)],
            "Give": [(1605, GOLDEN_HAMMER_MODEL_ID, 1)],
        },
        {
            "Serial": 2,
            "GlobalNum": 99,
            "PersonalNum": 10,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1112, 0, 50000)],
            "Give": [(1605, LOTTERY_TICKET_MODEL_ID, 1)],
        },
        {
            "Serial": 3,
            "GlobalNum": 50,
            "PersonalNum": 5,
            "NeedLv": 5,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 100)],
            "Give": [(1605, 16050001, 100)],
        },
        {
            "Serial": 4,
            "GlobalNum": 20,
            "PersonalNum": 3,
            "NeedLv": 10,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 280)],
            "Give": [(1606, 16060002, 1)],
        },
        {
            "Serial": 5,
            "GlobalNum": 99,
            "PersonalNum": 10,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 800)],
            "Give": [(1606, 16060003, 1)],
        },
        {
            "Serial": 6,
            "GlobalNum": 99,
            "PersonalNum": 10,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 800)],
            "Give": [(1606, 16060004, 1)],
        },
        {
            "Serial": 7,
            "GlobalNum": 99,
            "PersonalNum": 6,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 800)],
            "Give": [(1606, 16060036, 1)],
        },
        {
            "Serial": 8,
            "GlobalNum": 99,
            "PersonalNum": 6,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 1500)],
            "Give": [(1402, 14022001, 1)],
        },
        {
            "Serial": 9,
            "GlobalNum": 99,
            "PersonalNum": 6,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 1500)],
            "Give": [(1402, 14022002, 1)],
        },
        {
            "Serial": 10,
            "GlobalNum": 99,
            "PersonalNum": 6,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 1500)],
            "Give": [(1401, 14012001, 1)],
        },
        {
            "Serial": 11,
            "GlobalNum": 99,
            "PersonalNum": 6,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 1500)],
            "Give": [(1401, 14012002, 1)],
        },
        {
            "Serial": 12,
            "GlobalNum": 999,
            "PersonalNum": 99,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 300)],
            "Give": [(1602, 16020039, 1)],
        },
        {
            "Serial": 13,
            "GlobalNum": 999,
            "PersonalNum": 99,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 500)],
            "Give": [(1602, 16020045, 1)],
        },
        {
            "Serial": 14,
            "GlobalNum": 999,
            "PersonalNum": 99,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 1500)],
            "Give": [(1602, 16020047, 1)],
        },
        {
            "Serial": 15,
            "GlobalNum": 999,
            "PersonalNum": 99,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 4000)],
            "Give": [(1602, 16020049, 1)],
        },
        {
            "Serial": 16,
            "GlobalNum": 999,
            "PersonalNum": 99,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 10000)],
            "Give": [(1602, 16020051, 1)],
        },
        {
            "Serial": 17,
            "GlobalNum": 999,
            "PersonalNum": 99,
            "NeedLv": 1,
            "NeedVIPLv": 0,
            "Need": [(1111, 0, 30000)],
            "Give": [(1602, 16020057, 1)],
        },
    ]

    def _build_timed_exchange_payload(self, ev: Any, prog: dict[str, Any]) -> dict[str, Any]:
        exchanged = prog.setdefault("exchanged", {})
        act_list: list[dict[str, Any]] = []
        for rec in self.TIMED_EXCHANGE_RECIPES:
            ser = int(rec["Serial"])
            used = int(exchanged.get(str(ser), 0))
            act_list.append(
                {
                    "Serial": ser,
                    "GlobalNum": max(0, int(rec["GlobalNum"]) - used),
                    "PersonalNum": max(0, int(rec["PersonalNum"]) - used),
                    "NeedLv": int(rec["NeedLv"]),
                    "NeedVIPLv": int(rec["NeedVIPLv"]),
                    "NeedGameResourceList": _res_dicts(rec["Need"]),
                    "ExchaneGameResourceList": _res_dicts(rec["Give"]),
                }
            )
        return {
            "EndTime": int(ev.end_ts or self.clock.next_midnight_ts()),
            "ActivityList": act_list,
        }

    def _rpc_timed_limit_exchange_get_info(self, data: Any = None) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_exchange", data, family=self._EXCHANGE_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        out = self._build_timed_exchange_payload(ev, prog)
        self.save()
        return out

    def _rpc_timed_limit_exchange_exchange(self, data: Any) -> dict[str, Any]:
        ev_id, serial, count = self._extract_act_and_buy_args(data, "timed_exchange", self._EXCHANGE_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        rec = next((r for r in self.TIMED_EXCHANGE_RECIPES if int(r["Serial"]) == serial), None)
        if not ev.eligible or not rec:
            self._last_rpc_context["status"] = -1
            return {}
        exchanged = prog.setdefault("exchanged", {})
        used = int(exchanged.get(str(serial), 0))
        if used + count > int(rec["PersonalNum"]):
            self._last_rpc_context["status"] = -1
            return {}

        # Verify & deduct costs
        p = self.state["player"]
        for rt, rm, rn in rec["Need"]:
            need_amt = rn * count
            if rt == 1111 and int(p.get("Diamond", 0)) < need_amt:
                self._last_rpc_context["status"] = -1
                return {}
            if rt == 1112 and int(p.get("Gold", 0)) < need_amt:
                self._last_rpc_context["status"] = -1
                return {}
            if rt not in (1111, 1112) and self._get_goods_qty(rm) < need_amt:
                self._last_rpc_context["status"] = -1
                return {}

        for rt, rm, rn in rec["Need"]:
            need_amt = rn * count
            if rt == 1111:
                self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -need_amt, source=f"timed_exchange:{serial}")
            elif rt == 1112:
                self.ledger.apply_player_delta(p, self.profile_name, "Gold", -need_amt, source=f"timed_exchange:{serial}")
            else:
                self._consume_goods_qty(rm, need_amt)

        exchanged[str(serial)] = used + count
        give_tuples = [(rt, rm, rn * count) for rt, rm, rn in rec["Give"]]
        base_res = self._grant_resources_from_tuples(
            give_tuples,
            source=f"timed_exchange:{serial}:x{count}",
            tx_prefix=f"evt:{ev.instance_id}:exch:{serial}:{exchanged[str(serial)]}:{uuid.uuid4()}",
        )
        out = self._build_timed_exchange_payload(ev, prog)
        out["BaseGetGameResourceList"] = base_res
        self.save()
        return out

    # TimedActivityRankLayer (4430, BXH Năng Động — backed by VN ActiverankingModel.lua)
    ACTIVE_RANK_LESS_SCORE = 20
    ACTIVE_RANK_REWARDS: list[str] = [
        "1606,16060019,1||1111,0,500",
        "1606,16060002,1||1111,0,300",
        "1605,16050001,150||1111,0,200",
        "1605,16050061,2||1111,0,100",
        "1605,16050055,2||1112,0,150000",
    ]

    def _compute_active_rank_list(
        self,
        instance_id: str,
        my_score: int,
        *,
        include_archived_peers: bool = False,
    ) -> tuple[int, list[dict[str, Any]]]:
        entries: list[dict[str, Any]] = []
        for prof in self._s1_account_profiles():
            pp = prof.state.get("player", {})
            pid = str(pp.get("PlayerId", prof.profile_name))
            pname = str(pp.get("PlayerName", "Hero"))
            is_me = prof is self
            if is_me:
                sc = int(my_score)
            else:
                p_inst = prof.event_runtime.get_instance(instance_id) if instance_id else None
                if p_inst and p_inst.get("archived"):
                    if not include_archived_peers:
                        continue
                    p_prog = p_inst.get("progress", {})
                    if "score" not in p_prog and self._player_activity_stat_score(prof) <= 0:
                        continue
                    sc = int(p_prog.get("score", 0)) or self._player_active_score(prof)
                else:
                    sc = self._player_active_score(prof)
            if sc >= self.ACTIVE_RANK_LESS_SCORE:
                entries.append({"pid": pid, "Name": pname, "Score": sc, "is_me": is_me, "is_bot": False})
        for bname, bscore in [("KhuyểnDạXoa", 120), ("BạchSát", 95), ("TửVu", 70), ("NgọcTứHồn", 45), ("PhongKhuyển", 30)]:
            entries.append({"pid": f"npc:{bname}", "Name": bname, "Score": bscore, "is_me": False, "is_bot": True})
        entries.sort(key=lambda r: (-int(r["Score"]), 1 if r["is_bot"] else 0, str(r["pid"])))

        my_rank = 0
        rank_list: list[dict[str, Any]] = []
        for idx, r_str in enumerate(self.ACTIVE_RANK_REWARDS, start=1):
            occ = entries[idx - 1] if idx - 1 < len(entries) else None
            if occ and occ["is_me"]:
                my_rank = idx
            rank_list.append(
                {
                    "PlayerName": occ["Name"] if occ else "",
                    "Score": int(occ["Score"]) if occ else 0,
                    "RewardList": r_str,
                }
            )
        return my_rank, rank_list

    def _settle_active_rank(self, inst: dict[str, Any]) -> None:
        prog = inst.setdefault("progress", {})
        iid = str(inst["instance_id"])
        settlement = inst.setdefault("settlement", {})
        if "score" not in prog and self._player_activity_stat_score() <= 0:
            settlement["score"] = 0
            settlement["rank"] = 0
            return
        my_score = max(int(prog.get("score", 0)), self._player_active_score())
        prog["score"] = my_score
        settlement["score"] = my_score
        if my_score < self.ACTIVE_RANK_LESS_SCORE:
            settlement["rank"] = 0
            return
        my_rank, _ = self._compute_active_rank_list(iid, my_score, include_archived_peers=True)
        settlement["rank"] = my_rank
        if 1 <= my_rank <= len(self.ACTIVE_RANK_REWARDS):
            res_str = self.ACTIVE_RANK_REWARDS[my_rank - 1]
            tuples = _parse_res_tuples(res_str)
            if tuples:
                self._push_reward_center_entry(
                    source_key=f"active_rank:{iid}",
                    title=f"BXH Năng Động — Hạng {my_rank}",
                    content=f"Chúc mừng đạt hạng {my_rank} ({my_score} điểm năng động) kỳ {iid}.",
                    res_tuples=tuples,
                )

    def _rpc_timed_score_rank_get_info(self, data: Any = None) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_active_rank", data, family=self._ACTIVE_RANK_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        reward_step = 20
        my_score = self._player_active_score()
        prog["score"] = my_score
        claimed_cnt = int(prog.get("claimed_tickets", 0))
        can_cnt = max(0, (my_score // reward_step) - claimed_cnt)
        my_rank, rank_list = self._compute_active_rank_list(
            str(ev.instance_id or ""),
            my_score,
            include_archived_peers=False,
        )
        self.save()
        return {
            "EndDate": int(ev.end_ts or self.clock.next_midnight_ts()),
            "RewardScore": reward_step,
            "CanRewardCount": can_cnt,
            "LessScore": self.ACTIVE_RANK_LESS_SCORE,
            "Rank": my_rank,
            "Score": my_score,
            "RankList": rank_list,
        }

    def _rpc_timed_score_rank_get_reward(self, data: Any = None) -> dict[str, Any]:
        ev_id = self._resolve_timed_event_id("timed_active_rank", data, family=self._ACTIVE_RANK_FAMILY)
        ev, prog = self._eval_timed_sub(ev_id)
        reward_step = 20
        my_score = self._player_active_score()
        prog["score"] = my_score
        claimed_cnt = int(prog.get("claimed_tickets", 0))
        can_cnt = max(0, (my_score // reward_step) - claimed_cnt)
        if not ev.eligible or can_cnt <= 0:
            self._last_rpc_context["status"] = -1
            return {}
        prog["claimed_tickets"] = claimed_cnt + 1
        tuples = [(1111, 0, 50), (1605, self.GOLDEN_HAMMER_MODEL_ID, 1), (1605, self.LOTTERY_TICKET_MODEL_ID, 1)]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"timed_active_rank_ticket:{prog['claimed_tickets']}",
            tx_prefix=f"evt:{self.profile_name}:{self.state['player']['PlayerId']}:{ev.instance_id}:actrank:{prog['claimed_tickets']}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # -------------------- 9. TimedTaskListLayer (4700, Nhiệm Vụ Bạo Kích — TW 1.4 CriticalTasksTypeRelation) --------------------

    CRITICAL_TASK_SPECS: list[tuple[int, str, int, str]] = [
        (1, "Nạp Kim Cương", 60, "1111,0,100||1605,16050061,2"),
        (2, "Chiến Thắng Quyết Đấu", 1, "1111,0,50||1605,16050055,2"),
        (3, "Chiêu Mộ Tướng", 1, "1111,0,60||1605,16050001,50"),
        (4, "Chiêu Mộ Trang Bị", 1, "1112,0,100000||1605,16050003,3"),
        (5, "Đánh Yêu Vương", 1, "1111,0,60||1603,16030006,1"),
        (6, "Chinh Chiến Ải", 1, "1111,0,50||1112,0,80000"),
        (7, "Khiêu Chiến Mộ Thần Binh", 1, "1111,0,60||1605,16050010,2"),
        (8, "Chiêu Tài Miêu", 1, "1112,0,120000||1605,16050061,1"),
        (9, "Tiêu Phí Kim Cương", 100, "1111,0,88||1605,16050055,2"),
    ]

    def _critical_task_done_num(self, task_type: int, ev: Any, progress: dict[str, Any]) -> int:
        stats = self.state.get("stats", {})
        if task_type == 1:
            return self._period_economy(ev, progress)["charged"]
        if task_type == 2:
            return max(int(stats.get("arena_Win", 0)), 1 if int(self.state["player"].get("Lv", 1)) >= 6 else 0)
        if task_type == 3:
            return max(int(stats.get("total_recruits", 0)), len(self.state.get("heroes", [])))
        if task_type == 4:
            return max(int(stats.get("equip_recruit_count", 0)), len(self.state.get("equips", [])))
        if task_type == 5:
            return int(stats.get("boss_count", 0))
        if task_type == 6:
            return max(int(stats.get("normal_Win", 0)), len(self.state.get("battle", {}).get("completed_nodes", [])))
        if task_type == 7:
            return int(progress.get("bdd_attempts", 0)) if ev.eligible else 0
        if task_type == 8:
            return int(stats.get("zcsf_count", 0))
        if task_type == 9:
            return self._period_economy(ev, progress)["spent"]
        return 0

    def _build_critical_tasks_list(self) -> list[dict[str, Any]]:
        ev, prog = self._eval_timed_sub("timed_critical_tasks")
        ct_cfg = self.game_data.get("critical_tasks_type", {})
        exp_ts = int(ev.end_ts or self.clock.next_midnight_ts())
        out: list[dict[str, Any]] = []
        for t_type, title, need_num, rew_str in self.CRITICAL_TASK_SPECS:
            desc_fmt = str(ct_cfg.get(str(t_type), {}).get("description", f"{title} %s"))
            desc = desc_fmt.replace("%s", str(need_num)) if "%s" in desc_fmt else f"{desc_fmt} ({need_num})"
            done = min(need_num, self._critical_task_done_num(t_type, ev, prog))
            drawn = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"task:{t_type}"))
            out.append(
                {
                    "TaskType": t_type,
                    "Name": title,
                    "TasksDescription": desc,
                    "TasksReward": rew_str,
                    "CompleteComplete": need_num,
                    "DoneNum": done,
                    "IfDraw": drawn,
                    "ExpireTime": exp_ts,
                }
            )
        return out

    def _critical_tasks_red_dot(self) -> int:
        tasks = self._build_critical_tasks_list()
        return 1 if any(int(t["DoneNum"]) >= int(t["CompleteComplete"]) and not bool(t["IfDraw"]) for t in tasks) else 1

    def _rpc_timed_critical_info(self, _data: Any) -> list[dict[str, Any]]:
        out = self._build_critical_tasks_list()
        self.save()
        return out

    def _rpc_timed_critical_reward(self, data: Any) -> dict[str, Any]:
        t_type = int(data[0]) if isinstance(data, list) and data else 0
        spec = next((s for s in self.CRITICAL_TASK_SPECS if s[0] == t_type), None)
        if not spec:
            self._last_rpc_context["status"] = -1
            return {}
        _tt, _title, need_num, rew_str = spec
        ev, prog = self._eval_timed_sub("timed_critical_tasks")
        if self._critical_task_done_num(t_type, ev, prog) < need_num:
            self._last_rpc_context["status"] = -1
            return {}
        ok, base_res, _ = self.event_runtime.claim_milestone(
            "timed_critical_tasks",
            f"task:{t_type}",
            lambda idem: self._grant_resources_from_tuples(_parse_res_tuples(rew_str), source=f"critical_task:{t_type}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {
            "Info": self._build_critical_tasks_list(),
            "BaseGetGameResourceList": base_res,
        }

    # -------------------- 10. OpenSeriveCompetitionLayer (7900, Đua Top Mở Server 7 Ngày) --------------------

    def _opencontest_profile_score_obj(self, prof: Any) -> dict[str, int]:
        p = prof.state.get("player", {})
        stats = prof.state.get("stats", {})
        lv = int(p.get("Lv", 1))
        battle_stars = max(lv * 12, sum(int(v) for v in prof.state.get("battle", {}).get("node_stars", {}).values()) or (lv * 10))
        arena_step = int(prof.state.get("arena", {}).get("step", 2))
        arena_rank = int(prof.state.get("arena", {}).get("rank", 100))
        equip_score = max(lv * 300, len(prof.state.get("equips", [])) * 850)
        xxbz_dmg = max(int(stats.get("mystery_treasure_max_dmg", 0)), lv * 8000)
        bdd_stars = int(prof.state.get("bdd", {}).get("max_stars", 0))
        fap = max(int(p.get("FAP", 5000)), lv * 26000)
        return {
            "Lv": lv,
            "BattleStar": battle_stars,
            "HistoryMaxStep": max(2, arena_step),
            "HistoryMaxRank": max(1, arena_rank),
            "EquipPoint": equip_score,
            "MaximumDamage": xxbz_dmg,
            "MaxStarCount": bdd_stars,
            "PowerSum": fap,
        }

    def _opencontest_day_score_dict(self, day: int, metrics: dict[str, int]) -> dict[str, int]:
        key_map = {
            2: "BattleStar",
            4: "EquipPoint",
            5: "MaximumDamage",
            7: "PowerSum",
        }
        return {
            "Lv": int(metrics["Lv"]),
            "Score": int(metrics.get(key_map.get(day, "PowerSum"), metrics["PowerSum"])),
            "HistoryMaxStep": int(metrics["HistoryMaxStep"]),
            "HistoryMaxRank": int(metrics["HistoryMaxRank"]),
            "MaxStarCount": int(metrics["MaxStarCount"]),
        }

    def _opencontest_personal_reached(self, day: int, score_obj: dict[str, int]) -> bool:
        proj = self.game_data.get("opencontest_project", {}).get(str(day), {})
        cond = int(proj.get("personalCondition", 1))
        if day == 1:
            return int(score_obj["Lv"]) >= min(cond, max(5, int(self.state["player"].get("Lv", 1))))
        if day == 3:
            return int(score_obj["HistoryMaxStep"]) > 2 or (
                int(score_obj["HistoryMaxStep"]) == 2 and int(score_obj["HistoryMaxRank"]) <= cond
            )
        if day == 6:
            return int(score_obj["MaxStarCount"]) >= cond
        return int(score_obj["Score"]) >= cond

    def _opencontest_build_states(self) -> tuple[Any, list[dict[str, Any]]]:
        ev, _prog = self._eval_timed_sub("open_contest")
        my_metrics = self._opencontest_profile_score_obj(self)
        states: list[dict[str, Any]] = []
        for day in range(1, 8):
            s_dict = self._opencontest_day_score_dict(day, my_metrics)
            claimed = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"day:{day}"))
            if claimed:
                st = 2
            elif self._opencontest_personal_reached(day, s_dict):
                st = 1
            else:
                st = 0
            states.append({"State": st, "Score": s_dict})
        return ev, states

    def _opencontest_red_dot(self) -> int:
        _ev, states = self._opencontest_build_states()
        return 1 if any(int(s["State"]) == 1 for s in states) else 0

    def _rpc_opencontest_get_active_rank(self, _data: Any) -> dict[str, Any]:
        ev, states = self._opencontest_build_states()
        self.save()
        return {
            "EndTime": int(ev.end_ts or self.clock.next_midnight_ts()),
            "RankType": 7,  # All 7 days unlocked & inspectable offline
            "OpencontestState": states,
        }

    def _rpc_opencontest_get_rank(self, data: Any) -> dict[str, Any]:
        day = int(data[0]) if isinstance(data, list) and data else 1
        day = max(1, min(7, day))
        candidates: list[dict[str, Any]] = []
        for prof in self._s1_account_profiles():
            p = prof.state.get("player", {})
            m = self._opencontest_profile_score_obj(prof)
            candidates.append(
                {
                    "Id": str(p.get("PlayerId", "")),
                    "Name": str(p.get("PlayerName", "Hero")),
                    "HeadImageId": int(p.get("HeadImageId", 12010001)),
                    "Score": self._opencontest_day_score_dict(day, m),
                }
            )
        bot_Presets = [
            ("bot-1", "SesshomaruS1", 12013003, {"Lv": 28, "BattleStar": 280, "HistoryMaxStep": 3, "HistoryMaxRank": 12, "EquipPoint": 15000, "MaximumDamage": 350000, "MaxStarCount": 66, "PowerSum": 1150000}),
            ("bot-2", "InuYashaS1", 12012004, {"Lv": 22, "BattleStar": 210, "HistoryMaxStep": 2, "HistoryMaxRank": 28, "EquipPoint": 11000, "MaximumDamage": 240000, "MaxStarCount": 48, "PowerSum": 780000}),
            ("bot-3", "KikyoS1", 12012005, {"Lv": 18, "BattleStar": 160, "HistoryMaxStep": 2, "HistoryMaxRank": 45, "EquipPoint": 8500, "MaximumDamage": 150000, "MaxStarCount": 36, "PowerSum": 540000}),
        ]
        for bid, bname, bhead, bm in bot_Presets:
            candidates.append(
                {
                    "Id": bid,
                    "Name": bname,
                    "HeadImageId": bhead,
                    "Score": self._opencontest_day_score_dict(day, bm),
                }
            )

        if day == 1:
            candidates.sort(key=lambda c: -int(c["Score"]["Lv"]))
        elif day == 3:
            candidates.sort(key=lambda c: (-int(c["Score"]["HistoryMaxStep"]), int(c["Score"]["HistoryMaxRank"])))
        elif day == 6:
            candidates.sort(key=lambda c: -int(c["Score"]["MaxStarCount"]))
        else:
            candidates.sort(key=lambda c: -int(c["Score"]["Score"]))

        return {"OpencontestRank": candidates[:3]}

    def _rpc_opencontest_draw_reward(self, data: Any) -> dict[str, Any]:
        day = int(data[0]) if isinstance(data, list) and data else 1
        day = max(1, min(7, day))
        _ev, states = self._opencontest_build_states()
        if int(states[day - 1]["State"]) != 1:
            self._last_rpc_context["status"] = -1
            return {}
        proj = self.game_data.get("opencontest_project", {}).get(str(day), {})
        tuples = _parse_res_tuples(str(proj.get("personalRewards", "1111,0,200")))
        ok, base_res, _ = self.event_runtime.claim_milestone(
            "open_contest",
            f"day:{day}",
            lambda idem: self._grant_resources_from_tuples(tuples, source=f"open_contest:day{day}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # -------------------- 11. EarlytaskFinishRecord (2600, OpenActivityLayer — TW 1.4 EarlytaskModel) --------------------

    def _earlytask_reached_num(self, tid: int) -> int:
        p = self.state["player"]
        stats = self.state.get("stats", {})
        lv = int(p.get("Lv", 1))
        if tid == 2601:
            return max([int(e.get("Lv", 1)) for e in self.state.get("equips", [])] + [lv * 3, 30])
        if tid == 2602:
            return max(60, lv * 10)
        if tid == 2603:
            return max(10, int(stats.get("grab_count", 0)))
        if tid == 2605:
            return max(10, int(stats.get("arena_Win", 0)))
        if tid == 2606:
            return max(5, int(stats.get("boss_count", 0)))
        if tid == 2623:
            return max(1, int(self.state.get("gift_login", {}).get("sign_days", 1)))
        if tid == 2624:
            return max(3, int(stats.get("zcsf_count", 0)))
        return max(1, lv)

    def _rpc_earlytask_get_list(self, _data: Any) -> dict[str, Any]:
        ev, _prog = self._eval_timed_sub("early_task")
        et_models = self.game_data.get("earlytask_model", {})
        et_rewards = self.game_data.get("earlytask_reward", {})
        task_list: list[dict[str, Any]] = []
        for tid_str in sorted(et_models, key=lambda k: int(k)):
            tid = int(tid_str)
            tiers = et_rewards.get(tid_str, {})
            drawn_nums = [
                int(n_str)
                for n_str in sorted(tiers, key=lambda k: int(k))
                if ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"et:{tid}:{n_str}")
            ]
            task_list.append(
                {
                    "EarlyTaskModelId": tid,
                    "ReachedNum": self._earlytask_reached_num(tid),
                    "DrawNumList": drawn_nums,
                }
            )
        self.save()
        return {"EarlytaskList": task_list}

    def _rpc_earlytask_draw_gift(self, data: Any) -> dict[str, Any]:
        tid = int(data[0]) if isinstance(data, list) and len(data) >= 1 else 0
        need_num = int(data[1]) if isinstance(data, list) and len(data) >= 2 else 0
        tier = self.game_data.get("earlytask_reward", {}).get(str(tid), {}).get(str(need_num))
        if not tier or self._earlytask_reached_num(tid) < need_num:
            self._last_rpc_context["status"] = -1
            return {}
        tuples = _parse_res_tuples(str(tier.get("resourceList", "")))
        ok, base_res, _ = self.event_runtime.claim_milestone(
            "early_task",
            f"et:{tid}:{need_num}",
            lambda idem: self._grant_resources_from_tuples(tuples, source=f"early_task:{tid}:{need_num}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # -------------------- 12. ShiWanDiamond (8200, Mười Vạn Kim Cương — VN ShiwanyuanbaoRelation) --------------------

    def _shiwan_login_days(self) -> int:
        gl_days = int(self.state.get("gift_login", {}).get("sign_days", 1))
        lv_days = max(1, int(self.state.get("player", {}).get("Lv", 1)) // 2)
        return max(gl_days, lv_days)

    def _shiwan_red_dot(self) -> int:
        ev, _prog = self._eval_timed_sub("shiwan_diamond")
        days = self._shiwan_login_days()
        tbl = self.game_data.get("shiwanyuanbao", {})
        for d_str in tbl:
            d = int(d_str)
            if days >= d and not (ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"day:{d}")):
                return 1
        return 0

    def _rpc_swdiamonds_get_info(self, _data: Any) -> dict[str, Any]:
        ev, _prog = self._eval_timed_sub("shiwan_diamond")
        days = self._shiwan_login_days()
        tbl = self.game_data.get("shiwanyuanbao", {})
        info_list: list[dict[str, Any]] = []
        for d_str in sorted(tbl, key=lambda k: int(k)):
            d = int(d_str)
            claimed = bool(ev.instance_id and self.event_runtime.is_claimed(ev.instance_id, f"day:{d}"))
            status = 2 if claimed else (1 if days >= d else 0)
            info_list.append({"Days": d, "Status": status})
        self.save()
        return {"LoginDays": days, "SwDiamondInfo": info_list}

    def _rpc_swdiamonds_get_reward(self, data: Any) -> dict[str, Any]:
        req_days = int(data[0]) if isinstance(data, list) and data else 0
        row = self.game_data.get("shiwanyuanbao", {}).get(str(req_days))
        if not row or self._shiwan_login_days() < req_days:
            self._last_rpc_context["status"] = -1
            return {}
        dia = int(row.get("getDimonds", 100))
        vip_exp = int(row.get("getVipExp", 0))
        tuples: list[tuple[int, int, int]] = [(1111, 0, dia)]
        ok, base_res, _ = self.event_runtime.claim_milestone(
            "shiwan_diamond",
            f"day:{req_days}",
            lambda idem: self._grant_resources_from_tuples(tuples, source=f"shiwan_diamond:{req_days}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        if vip_exp > 0:
            p = self.state["player"]
            p["VipExp"] = int(p.get("VipExp", 0)) + vip_exp
            for v_str, v_row in sorted(self.game_data.get("vip_model", {}).items(), key=lambda kv: int(kv[0])):
                if int(p["VipExp"]) >= int(v_row.get("needEXP", 0)):
                    p["Vip"] = max(int(p.get("Vip", 0)), int(v_str))
        self.save()
        return {"BaseGameResource": base_res, "BaseGetGameResourceList": base_res}

    # -------------------- 13. OnlineReward (3700), MonthSignInfo (2712), RandomRedBag (5501), TraderInfo (4300), ActiveGift (2716), ShareInvite (2705) --------------------

    ONLINE_REWARD_TIERS: list[tuple[int, str]] = [
        (1, f"1111,0,30||1605,{GOLDEN_HAMMER_MODEL_ID},1"),
        (5, f"1112,0,50000||1605,{LOTTERY_TICKET_MODEL_ID},1"),
        (10, "1111,0,50||1605,16050001,30"),
        (20, f"1111,0,88||1605,{GOLDEN_HAMMER_MODEL_ID},2"),
        (30, "1111,0,128||1606,16060002,1"),
    ]

    def _ensure_online_reward_prog(self) -> tuple[Any, dict[str, Any]]:
        ev, prog = self._eval_timed_sub("online_reward")
        prog.setdefault("step_idx", 0)
        prog.setdefault("cooled_time", self.now_ts() - 1)  # First tier immediately claimable!
        return ev, prog

    def _build_online_reward_info(self) -> dict[str, Any] | None:
        _ev, prog = self._ensure_online_reward_prog()
        idx = int(prog.get("step_idx", 0))
        if idx >= len(self.ONLINE_REWARD_TIERS):
            return None
        mins, res_str = self.ONLINE_REWARD_TIERS[idx]
        res_list = [
            {"ResourceTypeSub": rt, "ModelId": rm, "Count": rn, "Num": rn}
            for rt, rm, rn in _parse_res_tuples(res_str)
        ]
        return {
            "NeedReachedNum": mins,
            "CooledTime": int(prog.get("cooled_time", self.now_ts())),
            "ResourceList": res_list,
        }

    def _rpc_online_reward_info(self, _data: Any) -> dict[str, Any]:
        info = self._build_online_reward_info()
        self.save()
        return {"OnlineRewardInfo": info} if info else {}

    def _rpc_online_reward_draw(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_online_reward_prog()
        idx = int(prog.get("step_idx", 0))
        if not ev.eligible or idx >= len(self.ONLINE_REWARD_TIERS):
            self._last_rpc_context["status"] = -1
            return {}
        if self.now_ts() < int(prog.get("cooled_time", 0)):
            self._last_rpc_context["status"] = -1
            return {}
        _mins, res_str = self.ONLINE_REWARD_TIERS[idx]
        tuples = _parse_res_tuples(res_str)
        ok, base_res, _ = self.event_runtime.claim_milestone(
            "online_reward",
            f"step:{idx}",
            lambda idem: self._grant_resources_from_tuples(tuples, source=f"online_reward:{idx}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        next_idx = idx + 1
        prog["step_idx"] = next_idx
        if next_idx < len(self.ONLINE_REWARD_TIERS):
            next_mins = self.ONLINE_REWARD_TIERS[next_idx][0]
            prog["cooled_time"] = self.now_ts() + next_mins * 60
        self.save()
        return {
            "OnlineRewardInfo": self._build_online_reward_info(),
            "BaseGetGameResourceList": base_res,
        }

    # MonthSignInfo (2712, Điểm Danh Tháng)
    def _month_sign_state(self) -> dict[str, Any]:
        ym = self.clock.dt().strftime("%Y-%m")
        ms = self.state.setdefault("month_sign", {})
        if ms.get("month_key") != ym:
            ms["month_key"] = ym
            ms["signed_count"] = 0
            ms["last_sign_day"] = ""
        return ms

    def _month_sign_reward_for_day(self, day_idx: int) -> tuple[str, int, int]:
        cycle = [
            (f"1111,0,50", 1, 2),
            ("1112,0,80000", 0, 1),
            (f"1605,{self.GOLDEN_HAMMER_MODEL_ID},1", 0, 1),
            ("1605,16050001,40", 2, 2),
            (f"1605,{self.LOTTERY_TICKET_MODEL_ID},1", 0, 1),
            ("1603,16030006,2", 0, 1),
            ("1606,16060002,1", 3, 2),
        ]
        return cycle[(day_idx - 1) % len(cycle)]

    def _month_sign_red_dot(self) -> int:
        ms = self._month_sign_state()
        today = self.clock.today_str()
        return 1 if ms.get("last_sign_day") != today and int(ms.get("signed_count", 0)) < 30 else 0

    def _rpc_month_sign_get_info(self, _data: Any) -> list[dict[str, Any]]:
        ms = self._month_sign_state()
        signed = int(ms.get("signed_count", 0))
        can_today = ms.get("last_sign_day") != self.clock.today_str()
        out: list[dict[str, Any]] = []
        for d in range(1, 31):
            res_str, need_vip, mult = self._month_sign_reward_for_day(d)
            if d <= signed:
                can_draw = 2
            elif d == signed + 1 and can_today:
                can_draw = 1
            else:
                can_draw = 0
            out.append(
                {
                    "Id": d,
                    "CanDraw": can_draw,
                    "ResourceList": res_str,
                    "NeedVip": need_vip,
                    "Multiple": mult,
                }
            )
        self.save()
        return out

    def _rpc_month_sign_draw_reward(self, _data: Any) -> dict[str, Any]:
        ms = self._month_sign_state()
        today = self.clock.today_str()
        signed = int(ms.get("signed_count", 0))
        if ms.get("last_sign_day") == today or signed >= 30:
            self._last_rpc_context["status"] = -1
            return {}
        day_idx = signed + 1
        res_str, need_vip, mult = self._month_sign_reward_for_day(day_idx)
        p_vip = int(self.state["player"].get("Vip", 0))
        factor = mult if (need_vip > 0 and p_vip >= need_vip and mult > 1) else 1
        tuples = [(rt, rm, rn * factor) for rt, rm, rn in _parse_res_tuples(res_str)]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"month_sign:{ms['month_key']}:d{day_idx}",
            tx_prefix=f"msign:{self.profile_name}:{ms['month_key']}:{day_idx}",
        )
        ms["signed_count"] = day_idx
        ms["last_sign_day"] = today
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # RandomRedBag (5501, Lì Xì Liên Server)
    def _ensure_red_bag_prog(self) -> tuple[Any, dict[str, Any]]:
        ev, prog = self._eval_timed_sub("random_red_bag")
        if "bags" not in prog:
            prog["bags"] = [
                {"PlayerId": "rb-s1-1", "ServerId": "S1", "PlayerName": "SesshomaruS1", "GroupId": 1, "Strong": 1, "TotalFund": 10000, "Num": 88},
                {"PlayerId": "rb-s1-2", "ServerId": "S1", "PlayerName": "InuYashaS1", "GroupId": 2, "Strong": 2, "TotalFund": 5000, "Num": 66},
            ]
        return ev, prog

    def _random_red_bag_red_dot(self) -> int:
        _ev, prog = self._ensure_red_bag_prog()
        return 1 if len(prog.get("bags", [])) > 0 else 0

    def _rpc_random_red_bag_get_info(self, _data: Any) -> dict[str, Any]:
        _ev, prog = self._ensure_red_bag_prog()
        self.save()
        return {"RandomRedBagList": copy.deepcopy(prog.get("bags", []))}

    def _rpc_random_red_bag_receive(self, data: Any) -> dict[str, Any]:
        pid = str(data[0]) if isinstance(data, list) and data else ""
        _ev, prog = self._ensure_red_bag_prog()
        bags = prog.get("bags", [])
        bag = next((b for b in bags if str(b.get("PlayerId")) == pid), bags[0] if bags else None)
        if not bag:
            self._last_rpc_context["status"] = -1
            return {}
        bid = str(bag["PlayerId"])
        dia = int(bag.get("Num", 66))
        ok, base_res, _ = self.event_runtime.claim_milestone(
            "random_red_bag",
            f"bag:{bid}",
            lambda idem: self._grant_resources_from_tuples([(1111, 0, dia)], source=f"random_red_bag:{bid}", tx_prefix=idem),
            player=self.state["player"],
        )
        if not ok:
            self._last_rpc_context["status"] = -1
            return {}
        prog["bags"] = [b for b in bags if str(b.get("PlayerId")) != bid]
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # TraderInfo (4300, Thương Nhân Hạn Giờ — TW 1.4 TraderConfig)
    TRADER_CATALOG: list[tuple[int, int, int, int, int, int]] = [
        # (SellResourceTypeSub, SellGoodsModelId, SellNum, BuyResourceTypeSub, BuyNum, Discount)
        (1605, GOLDEN_HAMMER_MODEL_ID, 2, 1112, 80000, 8000),
        (1605, LOTTERY_TICKET_MODEL_ID, 2, 1112, 80000, 8000),
        (1605, 16050001, 50, 1111, 100, 8000),
        (1605, 16050010, 3, 1111, 90, 9000),
        (1606, 16060002, 1, 1111, 250, 8000),
        (1301, 13010503, 1, 1111, 450, 8000),
    ]

    def _ensure_trader_prog(self) -> tuple[Any, dict[str, Any]]:
        ev, prog = self._eval_timed_sub("limit_trader")
        prog.setdefault("gold_count", 1)
        if "items" not in prog:
            prog["items"] = [
                {
                    "Id": idx,
                    "SellResourceTypeSub": srt,
                    "SellGoodsModelId": smid,
                    "SellNum": snum,
                    "BuyResourceTypeSub": brt,
                    "BuyGoodsModelId": 0,
                    "BuyNum": bnum,
                    "Discount": disc,
                    "IsSell": 0,
                }
                for idx, (srt, smid, snum, brt, bnum, disc) in enumerate(self.TRADER_CATALOG, start=1)
            ]
        return ev, prog

    def _rpc_trader_get_info(self, _data: Any) -> dict[str, Any]:
        ev, prog = self._ensure_trader_prog()
        self.save()
        return {
            "OpenDate": int(ev.end_ts or self.clock.next_midnight_ts()),
            "GoldCount": max(1, int(prog.get("gold_count", 1))),
            "TraderGoodsList": copy.deepcopy(prog["items"]),
        }

    def _rpc_trader_refresh(self, data: Any) -> dict[str, Any]:
        rtype = int(data[0]) if isinstance(data, list) and data else 1
        ev, prog = self._ensure_trader_prog()
        if rtype == 3:
            cost = 20
            if int(self.state["player"].get("Diamond", 0)) < cost:
                self._last_rpc_context["status"] = -1
                return {}
            self.ledger.apply_player_delta(self.state["player"], self.profile_name, "Diamond", -cost, source="trader_refresh")
        for item in prog["items"]:
            item["IsSell"] = 0
        prog["gold_count"] = int(prog.get("gold_count", 1)) + 1
        self.save()
        return self._rpc_trader_get_info([])

    def _rpc_trader_buy_goods(self, data: Any) -> dict[str, Any]:
        gid = int(data[0]) if isinstance(data, list) and data else 0
        ev, prog = self._ensure_trader_prog()
        item = next((x for x in prog.get("items", []) if int(x["Id"]) == gid), None)
        if not ev.eligible or not item or int(item.get("IsSell", 0)) != 0:
            self._last_rpc_context["status"] = -1
            return {}
        disc_step = math.ceil(int(item["Discount"]) / 1000.0)
        price = int(round(int(item["BuyNum"]) * disc_step * 0.1))
        brt = int(item["BuyResourceTypeSub"])
        p = self.state["player"]
        if brt == 1111:
            if int(p.get("Diamond", 0)) < price:
                self._last_rpc_context["status"] = -1
                return {}
            self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -price, source=f"trader_buy:{gid}")
        else:
            if int(p.get("Gold", 0)) < price:
                self._last_rpc_context["status"] = -1
                return {}
            self.ledger.apply_player_delta(p, self.profile_name, "Gold", -price, source=f"trader_buy:{gid}")
        item["IsSell"] = 1
        base_res = self._grant_resources_from_tuples(
            [(int(item["SellResourceTypeSub"]), int(item["SellGoodsModelId"]), int(item["SellNum"]))],
            source=f"trader_buy:{gid}",
            tx_prefix=f"evt:{ev.instance_id}:trader:{gid}:{uuid.uuid4()}",
        )
        self._record_daily_task_progress(26, 1)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # CDKExchangeLayer (2716, Giftcode) & DailyShareLayer (2705)
    GIFTCODE_BUNDLES: dict[str, list[tuple[int, int, int]]] = {
        "INUYASHA": [(1111, 0, 288), (1605, GOLDEN_HAMMER_MODEL_ID, 3), (1605, LOTTERY_TICKET_MODEL_ID, 3)],
        "SEEKJADE": [(1111, 0, 388), (1606, 16060002, 1), (1112, 0, 200000)],
        "REVIVAL": [(1111, 0, 588), (1606, 16060019, 1), (1605, 16050001, 150)],
        "VIP888": [(1111, 0, 888), (1605, GOLDEN_HAMMER_MODEL_ID, 5), (1605, LOTTERY_TICKET_MODEL_ID, 5)],
    }

    def _rpc_active_gift_redeem(self, data: Any) -> dict[str, Any]:
        raw_code = str(data[0]).strip().upper() if isinstance(data, list) and data else ""
        if not raw_code or not raw_code.isalnum():
            self._last_rpc_context["status"] = -1
            return {}
        redeemed = self.state.setdefault("redeemed_cdks", [])
        if raw_code in redeemed:
            self._last_rpc_context["status"] = -1
            return {}
        tuples = self.GIFTCODE_BUNDLES.get(
            raw_code,
            [(1111, 0, 188), (1605, self.GOLDEN_HAMMER_MODEL_ID, 2), (1605, self.LOTTERY_TICKET_MODEL_ID, 2)],
        )
        redeemed.append(raw_code)
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"cdk:{raw_code}",
            tx_prefix=f"cdk:{self.profile_name}:{raw_code}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_share_invite_get_share_reward(self, _data: Any) -> dict[str, Any]:
        cfg = self.game_data.get("share_config", {})
        first_dia = int(cfg.get("firstRewardDiamond", 100) or 100)
        base_gold = int(cfg.get("dailyRewardBaseGold", 50000) or 50000)
        share_st = self.state.setdefault("daily_share", {"first_claimed": False, "last_day": ""})
        today = self.clock.today_str()
        tuples: list[tuple[int, int, int]] = []
        if not share_st.get("first_claimed"):
            share_st["first_claimed"] = True
            tuples.append((1111, 0, first_dia))
        if share_st.get("last_day") != today:
            share_st["last_day"] = today
            tuples.append((1112, 0, base_gold))
        if not tuples:
            tuples.append((1112, 0, 10000))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"daily_share:{today}",
            tx_prefix=f"share:{self.profile_name}:{today}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}
