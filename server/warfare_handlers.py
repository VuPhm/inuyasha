"""R8.6: Hệ Thống Kết Giới & Linh Châu (Warfare 8101-8108)."""

from __future__ import annotations

import random
import re
import uuid
from collections import Counter
from typing import Any

from r79_event_handlers import _parse_res_tuples

EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"
_WARFARE_EXP_SPIRIT_TYPE = 16


def _wf_reject(store: Any, status: int = -1) -> dict[str, Any]:
    store._last_rpc_context["status"] = status
    return {}


class WarfareHandlersMixin:
    """Mixin implementing Hero Warfare domains and Warfarespirit beads (8101-8108)."""

    # ------------------------------------------------------------------
    # State Normalization & Stat Contribution Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_slot_warfarespirit(
        slot: dict[str, Any],
        spirits_by_id: dict[str, dict[str, Any]] | None = None,
        seen_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Ensure slot['Warfarespirit'] has 6 elements using {} for empty sockets."""
        raw = slot.get("Warfarespirit")
        if not isinstance(raw, list):
            raw = []
        norm: list[dict[str, Any]] = []
        for idx in range(6):
            entry = raw[idx] if idx < len(raw) else None
            if not isinstance(entry, dict):
                norm.append({})
                continue
            sid = str(entry.get("Id") or "")
            if not sid or sid == EMPTY_ENTITY_ID:
                norm.append({})
                continue
            if spirits_by_id is not None and sid not in spirits_by_id:
                norm.append({})
                continue
            if seen_ids is not None:
                if sid in seen_ids:
                    norm.append({})
                    continue
                seen_ids.add(sid)
            mid = int(spirits_by_id[sid]["ModelId"]) if spirits_by_id is not None else int(entry.get("ModelId", 0))
            if mid <= 0:
                norm.append({})
                continue
            norm.append({"Id": sid, "ModelId": mid})
        slot["Warfarespirit"] = norm
        return norm

    def _ensure_warfare_state(self, state: dict[str, Any] | None = None) -> None:
        """Normalize warfare containers, hero Warfare fields, and 6-socket lists."""
        target = state if state is not None else self.state
        spirits = target.setdefault("warfarespirit", [])
        if not isinstance(spirits, list):
            spirits = []
            target["warfarespirit"] = spirits
        cleaned: list[dict[str, Any]] = []
        spirits_by_id: dict[str, dict[str, Any]] = {}
        for item in spirits:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("Id") or "")
            mid = int(item.get("ModelId", 0))
            if not sid or sid == EMPTY_ENTITY_ID or mid <= 0:
                continue
            item["Id"] = sid
            item["ModelId"] = mid
            item["Lv"] = max(0, int(item.get("Lv", 0)))
            item["Exp"] = max(0, int(item.get("Exp", 0)))
            cleaned.append(item)
            spirits_by_id[sid] = item
        target["warfarespirit"] = cleaned

        for hero in target.get("heroes", []):
            hero["WarfareColorLv"] = max(0, int(hero.get("WarfareColorLv", 0)))
            hero["WarfareLv"] = max(0, int(hero.get("WarfareLv", 0)))

        seen_socketed: set[str] = set()
        for slot in target.get("slots", []):
            self._normalize_slot_warfarespirit(
                slot,
                spirits_by_id=spirits_by_id,
                seen_ids=seen_socketed,
            )

    def _warfare_data(self) -> dict[str, Any]:
        return self.game_data.get("warfare", {})

    def _build_warfarespirit_instance(self, model_id: int) -> dict[str, Any]:
        """Instantiate a fresh Lv.0 Warfarespirit bead entity."""
        return {
            "Id": str(uuid.uuid4()),
            "ModelId": int(model_id),
            "Lv": 0,
            "Exp": 0,
        }

    @staticmethod
    def _parse_warfare_attr_str(raw: str) -> Counter[int]:
        """Parse comma or double-pipe separated 'enum|value' attribute pairs."""
        totals: Counter[int] = Counter()
        for chunk in re.split(r"\|\||,", str(raw or "")):
            chunk = chunk.strip()
            if "|" not in chunk:
                continue
            parts = [p.strip() for p in chunk.split("|")]
            if len(parts) >= 2 and parts[0].lstrip("-").isdigit():
                try:
                    totals[int(parts[0])] += int(float(parts[1]))
                except ValueError:
                    continue
        return totals

    def _warfare_lv_row(self, warfare_id: int, color_lv: int, lv: int) -> dict[str, Any] | None:
        grade_map = self._warfare_data().get("warfare_lv", {}).get(str(warfare_id), {})
        return grade_map.get(str(color_lv), {}).get(str(lv))

    def _hero_warfare_rates(self, hero: dict[str, Any]) -> dict[int, int]:
        """Return hero Warfare 901/902/903 rates in VN 100,000 basis."""
        rates = {901: 0, 902: 0, 903: 0}
        if not isinstance(hero, dict):
            return rates
        clv = int(hero.get("WarfareColorLv", 0))
        lv = int(hero.get("WarfareLv", 0))
        if clv <= 0:
            return rates
        hcfg = self.game_data.get("heroes", {}).get(str(hero.get("HeroModelId", 0)), {})
        wid = int(hcfg.get("warfareID", 0))
        if wid <= 0:
            return rates
        row = self._warfare_lv_row(wid, clv, lv)
        if not row:
            return rates
        parsed = self._parse_warfare_attr_str(str(row.get("warfareAttr", "")))
        for k in (901, 902, 903):
            rates[k] = int(parsed.get(k, 0))
        return rates

    def _slot_warfarespirit_bonuses(self, slot: dict[str, Any], hero: dict[str, Any] | None = None) -> Counter[int]:
        """Sum active Warfarespirit bead stats for unlocked sockets in slot['Warfarespirit']."""
        totals: Counter[int] = Counter()
        if not hasattr(self, "state") or not isinstance(self.state, dict):
            return totals
        unlocked = 6
        if isinstance(hero, dict):
            clv = int(hero.get("WarfareColorLv", 0))
            lv = int(hero.get("WarfareLv", 0))
            hcfg = self.game_data.get("heroes", {}).get(str(hero.get("HeroModelId", 0)), {})
            wid = int(hcfg.get("warfareID", 0))
            if wid <= 0 or clv <= 0:
                return totals
            lv_row = self._warfare_lv_row(wid, clv, lv) or {}
            unlocked = max(0, int(lv_row.get("warfareCardNum", clv - 1)))
        if unlocked <= 0:
            return totals
        models = self.game_data.get("warfarespirit_model", {})
        spirits_by_id = {
            str(s.get("Id")): s
            for s in self.state.get("warfarespirit", [])
            if isinstance(s, dict) and s.get("Id")
        }
        for idx, entry in enumerate(slot.get("Warfarespirit") or []):
            if idx >= unlocked:
                break
            if not isinstance(entry, dict):
                continue
            sid = str(entry.get("Id") or "")
            if not sid or sid == EMPTY_ENTITY_ID:
                continue
            spirit = spirits_by_id.get(sid)
            if not spirit:
                continue
            mid = int(spirit.get("ModelId", 0))
            cfg = models.get(str(mid))
            if not cfg or int(cfg.get("typeID", 0)) == _WARFARE_EXP_SPIRIT_TYPE:
                continue
            slv = max(0, int(spirit.get("Lv", 0)))
            init_attrs = self._parse_warfare_attr_str(str(cfg.get("initialAttr", "")))
            add_attrs = self._parse_warfare_attr_str(str(cfg.get("addAttr", "")))
            for attr_id in set(init_attrs.keys()) | set(add_attrs.keys()):
                totals[attr_id] += int(init_attrs[attr_id]) + slv * int(add_attrs[attr_id])
        return totals

    def _socketed_warfarespirit_ids(self) -> set[str]:
        return {
            str(entry["Id"])
            for slot in self.state.get("slots", [])
            for entry in (slot.get("Warfarespirit") or [])
            if isinstance(entry, dict) and entry.get("Id") and entry.get("Id") != EMPTY_ENTITY_ID
        }

    def _consume_warfare_cost(self, cost_str: str, source: str) -> bool:
        """Atomically validate and deduct Gold + Goods required by WarfareLvRelation.LVUpUse."""
        gold_need = 0
        bag_needs: Counter[int] = Counter()
        for rtype, rmodel, rnum in _parse_res_tuples(cost_str):
            if rnum <= 0:
                continue
            if rtype == 1112:
                gold_need += rnum
            elif rmodel > 0:
                bag_needs[rmodel] += rnum
            else:
                return False

        if int(self.state["player"].get("Gold", 0)) < gold_need:
            return False

        goods_list = self.state.get("goods", [])
        for mid, req in bag_needs.items():
            have = sum(int(g.get("Num", 0)) for g in goods_list if int(g.get("GoodsModelId", 0)) == mid)
            if have < req:
                return False

        if gold_need > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Gold",
                -gold_need,
                source=source,
            )

        for mid, req in bag_needs.items():
            remaining = req
            for g in goods_list:
                if int(g.get("GoodsModelId", 0)) != mid or remaining <= 0:
                    continue
                avail = int(g.get("Num", 0))
                take = min(avail, remaining)
                g["Num"] = avail - take
                remaining -= take
            self._mark_goods_changed(mid)
        if bag_needs:
            self.state["goods"] = [g for g in goods_list if int(g.get("Num", 0)) > 0]
        return True

    def _find_warfare_hero(self, hero_id: str) -> tuple[dict[str, Any] | None, int]:
        hero = next((h for h in self.state.get("heroes", []) if str(h.get("Id")) == str(hero_id)), None)
        if not hero:
            return None, 0
        hcfg = self.game_data.get("heroes", {}).get(str(hero.get("HeroModelId", 0)), {})
        return hero, int(hcfg.get("warfareID", 0))

    # ------------------------------------------------------------------
    # Warfare Upgrade RPCs
    # ------------------------------------------------------------------

    def _rpc_warfare_open(self, data: Any) -> dict[str, Any]:
        self._ensure_warfare_state()
        if not isinstance(data, list) or not data:
            return _wf_reject(self)
        hero, wid = self._find_warfare_hero(str(data[0]))
        if not hero or wid <= 0 or int(hero.get("WarfareColorLv", 0)) != 0:
            return _wf_reject(self)
        row = self._warfare_lv_row(wid, 1, 0)
        if not row or not self._consume_warfare_cost(str(row.get("LVUpUse", "")), source=f"warfare_open:{wid}"):
            return _wf_reject(self)
        hero["WarfareColorLv"] = 1
        hero["WarfareLv"] = 0
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"Hero": dict(hero)}

    def _rpc_warfare_lv_up(self, data: Any) -> dict[str, Any]:
        self._ensure_warfare_state()
        if not isinstance(data, list) or not data:
            return _wf_reject(self)
        hero, wid = self._find_warfare_hero(str(data[0]))
        if not hero or wid <= 0:
            return _wf_reject(self)
        clv = int(hero.get("WarfareColorLv", 0))
        lv = int(hero.get("WarfareLv", 0))
        if clv <= 0:
            return _wf_reject(self)
        next_row = self._warfare_lv_row(wid, clv, lv + 1)
        if not next_row or not self._consume_warfare_cost(str(next_row.get("LVUpUse", "")), source=f"warfare_lvup:{wid}:{clv}:{lv+1}"):
            return _wf_reject(self)
        hero["WarfareLv"] = lv + 1
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"Hero": dict(hero)}

    def _rpc_warfare_color_lv_up(self, data: Any) -> dict[str, Any]:
        self._ensure_warfare_state()
        if not isinstance(data, list) or not data:
            return _wf_reject(self)
        hero, wid = self._find_warfare_hero(str(data[0]))
        if not hero or wid <= 0:
            return _wf_reject(self)
        clv = int(hero.get("WarfareColorLv", 0))
        lv = int(hero.get("WarfareLv", 0))
        if clv <= 0:
            return _wf_reject(self)
        grade_map = self._warfare_data().get("warfare_lv", {}).get(str(wid), {})
        cur_grade = grade_map.get(str(clv), {})
        if not cur_grade:
            return _wf_reject(self)
        max_lv = max(int(k) for k in cur_grade)
        if lv < max_lv:
            return _wf_reject(self)
        next_row = grade_map.get(str(clv + 1), {}).get("0")
        if not next_row or not self._consume_warfare_cost(str(next_row.get("LVUpUse", "")), source=f"warfare_colorup:{wid}:{clv+1}"):
            return _wf_reject(self)
        hero["WarfareColorLv"] = clv + 1
        hero["WarfareLv"] = 0
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"Hero": dict(hero)}

    # ------------------------------------------------------------------
    # Warfarespirit Socket & Bead Progression RPCs
    # ------------------------------------------------------------------

    def _rpc_warfarespirit_slot_combat(self, data: Any) -> dict[str, Any]:
        self._ensure_warfare_state()
        if not isinstance(data, list) or len(data) < 3:
            return _wf_reject(self)
        hero_id = str(data[0])
        try:
            socket_idx = int(data[1])
        except (TypeError, ValueError):
            return _wf_reject(self)
        spirit_id = str(data[2])
        if socket_idx < 1 or socket_idx > 6:
            return _wf_reject(self)

        target_slot = next((s for s in self.state.get("slots", []) if str(s.get("HeroId")) == hero_id), None)
        hero, wid = self._find_warfare_hero(hero_id)
        if not target_slot or not hero or wid <= 0:
            return _wf_reject(self)
        clv = int(hero.get("WarfareColorLv", 0))
        lv = int(hero.get("WarfareLv", 0))
        if clv <= 0:
            return _wf_reject(self)
        lv_row = self._warfare_lv_row(wid, clv, lv) or {}
        unlocked = int(lv_row.get("warfareCardNum", max(0, clv - 1)))
        if socket_idx > unlocked:
            return _wf_reject(self)

        spirit = next((s for s in self.state.get("warfarespirit", []) if s["Id"] == spirit_id), None)
        if not spirit:
            return _wf_reject(self)
        models = self.game_data.get("warfarespirit_model", {})
        new_cfg = models.get(str(spirit["ModelId"]))
        if not new_cfg or int(new_cfg.get("typeID", 0)) == _WARFARE_EXP_SPIRIT_TYPE:
            return _wf_reject(self)
        new_type = int(new_cfg.get("typeID", 0))

        # HeroUpdateScene.lua forbids duplicate Warfarespirit typeIDs on the same Hero
        sockets = target_slot["Warfarespirit"]
        for i, entry in enumerate(sockets):
            if i == socket_idx - 1:
                continue
            eid = str(entry.get("Id") or "")
            if not eid or eid == EMPTY_ENTITY_ID:
                continue
            emid = int(entry.get("ModelId", 0))
            if int(models.get(str(emid), {}).get("typeID", 0)) == new_type:
                return _wf_reject(self)

        # Clear spirit from any previous socket first (replace/move support)
        for other in self.state.get("slots", []):
            other_sockets = other.get("Warfarespirit") or []
            for idx, entry in enumerate(other_sockets):
                if isinstance(entry, dict) and entry.get("Id") == spirit_id:
                    other_sockets[idx] = {}

        sockets[socket_idx - 1] = {"Id": spirit["Id"], "ModelId": int(spirit["ModelId"])}
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotInfo": self.state["slots"]}

    def _rpc_warfarespirit_slot_uncombat(self, data: Any) -> dict[str, Any]:
        self._ensure_warfare_state()
        if not isinstance(data, list) or len(data) < 2:
            return _wf_reject(self)
        hero_id = str(data[0])
        try:
            socket_idx = int(data[1])
        except (TypeError, ValueError):
            return _wf_reject(self)
        spirit_id = str(data[2]) if len(data) >= 3 and data[2] else ""
        if socket_idx < 1 or socket_idx > 6:
            return _wf_reject(self)

        target_slot = next((s for s in self.state.get("slots", []) if str(s.get("HeroId")) == hero_id), None)
        if not target_slot:
            return _wf_reject(self)
        cur = target_slot["Warfarespirit"][socket_idx - 1]
        cur_id = str(cur.get("Id") or "") if isinstance(cur, dict) else ""
        if not cur_id or cur_id == EMPTY_ENTITY_ID:
            return _wf_reject(self)
        if spirit_id and cur_id != spirit_id:
            return _wf_reject(self)

        target_slot["Warfarespirit"][socket_idx - 1] = {}
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotInfo": self.state["slots"]}

    def _rpc_warfarespirit_lv_up(self, data: Any) -> dict[str, Any]:
        self._ensure_warfare_state()
        if not isinstance(data, list) or len(data) < 2:
            return _wf_reject(self)
        target_id = str(data[0])
        raw_fodders = data[1] if isinstance(data[1], list) else []
        if not target_id or not raw_fodders:
            return _wf_reject(self)
        fodder_ids = [str(x) for x in raw_fodders if str(x)]
        if len(fodder_ids) != len(raw_fodders) or len(set(fodder_ids)) != len(fodder_ids):
            return _wf_reject(self)
        if target_id in fodder_ids:
            return _wf_reject(self)

        spirits = self.state.get("warfarespirit", [])
        by_id = {s["Id"]: s for s in spirits}
        target = by_id.get(target_id)
        if not target:
            return _wf_reject(self)
        models = self.game_data.get("warfarespirit_model", {})
        t_cfg = models.get(str(target["ModelId"]))
        if not t_cfg or int(t_cfg.get("typeID", 0)) == _WARFARE_EXP_SPIRIT_TYPE:
            return _wf_reject(self)

        lv_tbl = self.game_data.get("warfarespirit_lv", {}).get(str(t_cfg.get("colorLV", 1)), {})
        if not lv_tbl:
            return _wf_reject(self)
        max_lv = max(int(k) for k in lv_tbl)
        cur_lv = int(target.get("Lv", 0))
        if cur_lv >= max_lv:
            return _wf_reject(self)

        socketed = self._socketed_warfarespirit_ids()
        gained_exp = 0
        for fid in fodder_ids:
            fodder = by_id.get(fid)
            if not fodder or fid in socketed:
                return _wf_reject(self)
            f_cfg = models.get(str(fodder["ModelId"]), {})
            gained_exp += max(int(fodder.get("Exp", 0)), int(f_cfg.get("EXP", 0)))

        if gained_exp <= 0:
            return _wf_reject(self)

        max_exp = int(lv_tbl[str(max_lv)].get("EXPTotal", 0))
        new_exp = min(max_exp, int(target.get("Exp", 0)) + gained_exp)
        new_lv = max(
            (int(k) for k, row in lv_tbl.items() if new_exp >= int(row.get("EXPTotal", 0))),
            default=cur_lv,
        )
        new_lv = min(max_lv, max(cur_lv, new_lv))

        fodder_set = set(fodder_ids)
        self.state["warfarespirit"] = [s for s in spirits if s["Id"] not in fodder_set]
        target["Exp"] = new_exp
        target["Lv"] = new_lv

        if target_id in socketed:
            self._recalc_all_slots_and_fap()
            self._last_rpc_context["slots_changed"] = True
        self.save()
        return dict(target)

    def _rpc_warfarespirit_sell(self, data: Any) -> dict[str, Any]:
        self._ensure_warfare_state()
        if not isinstance(data, list) or not data:
            return _wf_reject(self)
        raw_ids = data[0] if isinstance(data[0], list) else data
        spirit_ids = [str(x) for x in raw_ids if str(x)]
        if not spirit_ids or len(set(spirit_ids)) != len(spirit_ids):
            return _wf_reject(self)

        spirits = self.state.get("warfarespirit", [])
        by_id = {s["Id"]: s for s in spirits}
        socketed = self._socketed_warfarespirit_ids()
        models = self.game_data.get("warfarespirit_model", {})
        reward_tuples: list[tuple[int, int, int]] = []
        for sid in spirit_ids:
            sp = by_id.get(sid)
            if not sp or sid in socketed:
                return _wf_reject(self)
            cfg = models.get(str(sp["ModelId"]), {})
            reward_tuples.extend(_parse_res_tuples(str(cfg.get("price", "1112,0,1000"))))

        sold_set = set(spirit_ids)
        self.state["warfarespirit"] = [s for s in spirits if s["Id"] not in sold_set]
        base_res = self._grant_resources_from_tuples(
            reward_tuples,
            source="warfarespirit_sell",
            tx_prefix=f"wf_sell:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_warfarespirit_decompose(self, data: Any) -> dict[str, Any]:
        """Decompose eWarfareArms (1615) crests into Warfarespirit beads via WarfarecrestRefRelation."""
        self._ensure_warfare_state()
        if not isinstance(data, list) or len(data) < 2:
            return _wf_reject(self)
        id_list, cnt_list = data[0], data[1]
        if not isinstance(id_list, list) or not isinstance(cnt_list, list):
            return _wf_reject(self)
        if not id_list or len(id_list) != len(cnt_list):
            return _wf_reject(self)

        req_by_id: Counter[str] = Counter()
        for raw_id, raw_cnt in zip(id_list, cnt_list):
            eid = str(raw_id)
            try:
                cnt = int(raw_cnt)
            except (TypeError, ValueError):
                return _wf_reject(self)
            if not eid or cnt <= 0:
                return _wf_reject(self)
            req_by_id[eid] += cnt

        goods_by_id = {g["Id"]: g for g in self.state.get("goods", [])}
        ref_map = self._warfare_data().get("warfare_ref", {})
        for eid, cnt in req_by_id.items():
            item = goods_by_id.get(eid)
            if not item or int(item.get("Num", 0)) < cnt:
                return _wf_reject(self)
            gid = int(item.get("GoodsModelId", 0))
            if gid // 10000 != 1615 or not ref_map.get(str(gid)):
                return _wf_reject(self)

        reward_tuples: list[tuple[int, int, int]] = []
        changed_gids: set[int] = set()
        for eid, cnt in req_by_id.items():
            item = goods_by_id[eid]
            gid = int(item["GoodsModelId"])
            item["Num"] = int(item["Num"]) - cnt
            changed_gids.add(gid)
            pool = ref_map[str(gid)]
            min_w = min(int(r.get("oddsMin", 1)) for r in pool)
            max_w = max(int(r.get("oddsMax", 10000)) for r in pool)
            for _ in range(cnt):
                roll = random.randint(min_w, max_w)
                chosen = next(
                    (r for r in pool if int(r.get("oddsMin", 0)) <= roll <= int(r.get("oddsMax", 0))),
                    pool[-1],
                )
                reward_tuples.extend(_parse_res_tuples(str(chosen.get("refResource", ""))))

        self.state["goods"] = [g for g in self.state.get("goods", []) if int(g.get("Num", 0)) > 0]
        for gid in changed_gids:
            self._mark_goods_changed(gid)

        base_res = self._grant_resources_from_tuples(
            reward_tuples,
            source="warfare_decompose",
            tx_prefix=f"wf_dec:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_warfarespirit_add_test(self, data: Any) -> dict[str, Any]:
        """Debug-only helper matching WarfareLevelLayer.lua:553."""
        if getattr(self, "profile_name", "normal") != "debug":
            return _wf_reject(self)
        if not isinstance(data, list) or len(data) < 2:
            return _wf_reject(self)
        try:
            model_id = int(data[0])
            count = int(data[1])
        except (TypeError, ValueError):
            return _wf_reject(self)
        if count <= 0 or count > 50 or str(model_id) not in self.game_data.get("warfarespirit_model", {}):
            return _wf_reject(self)
        base_res = self._grant_resources_from_tuples(
            [(2502, model_id, count)],
            source=f"warfarespirit_add_test:{model_id}",
            tx_prefix=f"wf_test:{self.profile_name}:{model_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}
