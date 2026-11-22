"""Reborn (Chuyển Sinh) system handlers, stat bonuses, Cheer/Master bonds, and Shop."""

from __future__ import annotations

from collections import Counter
import copy
import random
import uuid
from typing import Any

from r79_event_handlers import _parse_res_tuples

_REBORN_CURRENCY_MAP: dict[int, str] = {
    1111: "Diamond",
    1112: "Gold",
    1115: "PVPCoin",
    1116: "HeroCoin",
    1117: "HeroEXP",
    1120: "BossCoin",
    1124: "Merit",
    1128: "RebornCoin",
}

_REBORN_SHOP_SLOT_COUNT = 8


def _parse_attr_str(attr_str: str) -> Counter[int]:
    """Parse comma-separated `attrId|val` pairs into a Counter."""
    totals: Counter[int] = Counter()
    if not attr_str:
        return totals
    for chunk in str(attr_str).split(","):
        parts = [p.strip() for p in chunk.split("|")]
        if len(parts) == 2 and parts[0].lstrip("-").isdigit():
            totals[int(parts[0])] += int(float(parts[1]))
    return totals


def _default_reborn_step_info(reborn_id: int) -> list[dict[str, int]]:
    """Build initial 4-slot status list for a reborn-eligible hero."""
    if reborn_id <= 0:
        return []
    return [{"Num": i, "Status": 0} for i in range(1, 5)]


class RebornHandlersMixin:
    """Server handlers and stat calculators for Hero Reborn, Materials, UAID, and RebornShop."""

    def _reborn_reject(self, status: int) -> dict[str, Any]:
        self._last_rpc_context["status"] = status
        return {}

    def _hero_reborn_class_id(self, cfg: dict[str, Any]) -> int:
        """Resolve RebornLvModel classID; quality-18 Red UAID heroes fall back to classID 16."""
        rc = int(cfg.get("rebornClassID", 0))
        if rc > 0:
            return rc
        if int(cfg.get("quality", 0)) >= 18 and int(cfg.get("UAID", 0)) > 0:
            return 16
        return 0

    def _ensure_hero_reborn_fields(self, hero: dict[str, Any]) -> None:
        """Initialize or normalize RebornId, RebornStepInfo, and RebornStep on a hero instance."""
        cfg = self.game_data.get("heroes", {}).get(str(hero.get("HeroModelId", 0)), {})
        rc = self._hero_reborn_class_id(cfg)
        rlv = self.game_data.get("reborn_lv", {})
        if rc <= 0:
            hero.setdefault("RebornId", 0)
            hero.setdefault("RebornStepInfo", [])
            hero.setdefault("RebornStep", 0)
            return

        base_id = rc * 1000
        rid = int(hero.get("RebornId", 0))
        if rid <= 0 or str(rid) not in rlv:
            legacy_step = max(0, int(hero.get("RebornStep", 0)))
            cand = base_id + legacy_step * 10
            if str(cand) in rlv:
                rid = cand
            else:
                matching = sorted(int(k) for k, v in rlv.items() if int(v.get("classID", 0)) == rc)
                rid = matching[-1] if (legacy_step > 0 and matching) else base_id
            hero["RebornId"] = rid

        raw_slots = hero.get("RebornStepInfo")
        by_num: dict[int, int] = {}
        if isinstance(raw_slots, list):
            for entry in raw_slots:
                if isinstance(entry, dict) and str(entry.get("Num", "")).isdigit():
                    num = int(entry["Num"])
                    if 1 <= num <= 4:
                        by_num[num] = 1 if int(entry.get("Status", 0)) > 0 else 0
        hero["RebornStepInfo"] = [{"Num": n, "Status": by_num.get(n, 0)} for n in range(1, 5)]
        hero["RebornStep"] = int(rlv.get(str(rid), {}).get("rebornNum", 0))

    def _hero_reborn_flat_and_self_rates(self, hero: dict[str, Any]) -> tuple[Counter[int], int, int, int]:
        """Return (flat_attrs Counter, APR bps, HPR bps, DEFR bps) for a hero's current RebornId & slots."""
        flat: Counter[int] = Counter()
        rid = int(hero.get("RebornId", 0))
        rlv = self.game_data.get("reborn_lv", {})
        row = rlv.get(str(rid))
        if not row:
            return flat, 0, 0, 0

        flat += _parse_attr_str(str(row.get("allAttrStr", "")))
        slot_cfg = self.game_data.get("reborn_slots", {}).get(str(rid), {})
        for entry in hero.get("RebornStepInfo") or []:
            if isinstance(entry, dict) and int(entry.get("Status", 0)) == 1:
                srow = slot_cfg.get(str(entry.get("Num", 0)))
                if srow:
                    flat += _parse_attr_str(str(srow.get("attrStr", "")))

        class_id = int(row.get("classID", 0))
        reborn_num = int(row.get("rebornNum", 0))
        pr_row = self.game_data.get("reborn_prtype", {}).get(str(class_id * 1000 + reborn_num * 10), {})
        apr = int(round(float(pr_row.get("APR", 0)) * 10000))
        hpr = int(round(float(pr_row.get("HPR", 0)) * 10000))
        defr = int(round(float(pr_row.get("DEFR", 0)) * 10000))
        return flat, apr, hpr, defr

    def _team_reborn_master_rates(self, heroes_by_id: dict[str, dict[str, Any]]) -> tuple[int, int, int]:
        """Compute team-wide Reborn Master (APR, HPR, DEFR) bps from min rebornNum across 6 deployed slots."""
        slots = self.state.get("slots", []) if isinstance(getattr(self, "state", None), dict) else []
        if len(slots) < 6:
            return 0, 0, 0
        rlv = self.game_data.get("reborn_lv", {})
        min_reborn: int | None = None
        for slot in slots[:6]:
            hid = slot.get("HeroId")
            hero = heroes_by_id.get(hid) if hid else None
            if not hero:
                return 0, 0, 0
            rid = int(hero.get("RebornId", 0))
            rnum = int(rlv.get(str(rid), {}).get("rebornNum", 0))
            min_reborn = rnum if min_reborn is None else min(min_reborn, rnum)
        if not min_reborn or min_reborn <= 0:
            return 0, 0, 0

        apr, hpr, defr = 0, 0, 0
        active_tbl = self.game_data.get("reborn_lv_active", {})
        for row in active_tbl.values():
            if int(row.get("rebornNum", 999)) <= min_reborn:
                bps = int(round(float(row.get("PRRatio", 0)) * 10000))
                ptype = str(row.get("PRType", ""))
                if ptype == "APR":
                    apr += bps
                elif ptype == "HPR":
                    hpr += bps
                elif ptype == "DEFR":
                    defr += bps
        return apr, hpr, defr

    def _hero_reborn_cheer_bonuses(self, heroes_by_id: dict[str, dict[str, Any]]) -> dict[str, int]:
        """Compute party-wide HeroRebornCheer flat bonuses from orange+ partner (mate) slots."""
        bonuses = {"HP": 0, "AP": 0, "DEF": 0}
        cheer_tbl = self.game_data.get("hero_reborn_cheer", {})
        if not cheer_tbl or not isinstance(getattr(self, "state", None), dict):
            return bonuses
        quality_tbl = self.game_data.get("quality_model", {})
        heroes_cfg = self.game_data.get("heroes", {})
        rlv = self.game_data.get("reborn_lv", {})
        total_reborn = 0
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
                rid = int(hero.get("RebornId", 0))
                total_reborn += int(rlv.get(str(rid), {}).get("rebornNum", 0))
        if total_reborn <= 0:
            return bonuses
        max_tier = max((int(k) for k in cheer_tbl if k.isdigit()), default=0)
        row = cheer_tbl.get(str(min(total_reborn, max_tier)), {})
        bonuses["AP"] = int(row.get("APADD", 0))
        bonuses["HP"] = int(row.get("HPADD", 0))
        bonuses["DEF"] = int(row.get("DEFADD", 0))
        return bonuses

    def _hero_reborn_talent_buffs(self, reborn_id: int) -> list[str]:
        """Return combat buff IDs granted by RebornLvModel[reborn_id].talIDStr."""
        row = self.game_data.get("reborn_lv", {}).get(str(reborn_id))
        if not row:
            return []
        tal_ids = [t.strip() for t in str(row.get("talIDStr", "")).split(",") if t.strip()]
        tals = self.game_data.get("talent_models", {})
        out: list[str] = []
        for tid in tal_ids:
            trow = tals.get(tid)
            if trow and trow.get("buffList"):
                out.extend(b.strip() for b in str(trow["buffList"]).split(",") if b.strip())
        return out

    def _hero_uaid_unlocked(self, cfg: dict[str, Any], reborn_id: int) -> bool:
        """True once the hero has reached or passed an ifUAID==1 milestone in its RebornLvModel class."""
        if int(cfg.get("UAID", 0)) <= 0 or reborn_id <= 0:
            return False
        rlv = self.game_data.get("reborn_lv", {})
        cur = rlv.get(str(reborn_id))
        if not cur:
            return False
        cid = int(cur.get("classID", 0))
        return any(
            int(v.get("classID", 0)) == cid
            and int(k) <= reborn_id
            and int(v.get("ifUAID", 0)) == 1
            for k, v in rlv.items()
        )

    def _reborn_goods_counts(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for rg in self.state.get("reborn_goods", []):
            mid = int(rg.get("ModelId", 0))
            if mid > 0:
                counts[mid] = counts.get(mid, 0) + int(rg.get("Num", 0))
        return counts

    def _set_reborn_goods_counts(self, new_counts: dict[int, int], touched_ids: set[int] | None = None) -> None:
        rb_list = self.state.setdefault("reborn_goods", [])
        existing_by_mid = {int(rg["ModelId"]): rg for rg in rb_list if int(rg.get("ModelId", 0)) > 0}
        updated: list[dict[str, Any]] = []
        all_mids = set(existing_by_mid) | set(new_counts)
        for mid in sorted(all_mids):
            qty = int(new_counts.get(mid, 0))
            old_qty = int(existing_by_mid.get(mid, {}).get("Num", 0))
            if qty > 0:
                entry = existing_by_mid.get(mid) or {"Id": str(uuid.uuid4()), "ModelId": mid, "Num": 0}
                entry["Num"] = qty
                updated.append(entry)
            if touched_ids is not None and qty != old_qty:
                touched_ids.add(mid)
        self.state["reborn_goods"] = updated
        if touched_ids:
            for mid in sorted(touched_ids):
                self._mark_reborn_goods_changed(mid)

    def _can_craft_reborn_good(
        self,
        model_id: int,
        qty: int,
        work_rb: dict[int, int],
        work_other: dict[tuple[int, int], int],
        visiting: set[int] | None = None,
    ) -> bool:
        """Try satisfying `qty` units of `model_id` using bag stock first, then recursive compoundUse."""
        vis = visiting or set()
        if qty <= 0:
            return True
        have = int(work_rb.get(model_id, 0))
        use = min(have, qty)
        if use > 0:
            work_rb[model_id] = have - use
        rem = qty - use
        if rem == 0:
            return True
        if model_id in vis:
            return False
        rg_row = self.game_data.get("reborn_goods", {}).get(str(model_id), {})
        recipe = str(rg_row.get("compoundUse", "")).strip()
        if not recipe:
            return False
        reqs = _parse_res_tuples(recipe)
        if not reqs:
            return False
        next_vis = vis | {model_id}
        for _ in range(rem):
            for rt, rm, rn in reqs:
                if rt == 2701:
                    if not self._can_craft_reborn_good(rm, rn, work_rb, work_other, next_vis):
                        return False
                else:
                    key = (rt, rm)
                    cur_o = int(work_other.get(key, 0))
                    if cur_o < rn:
                        return False
                    work_other[key] = cur_o - rn
        return True

    def _goods_qty(self, goods_model_id: int) -> int:
        return sum(
            int(g.get("Num", 0))
            for g in self.state.get("goods", [])
            if int(g.get("GoodsModelId", 0)) == goods_model_id
        )

    def _check_and_consume_tuples(self, reqs: list[tuple[int, int, int]], source: str) -> int:
        """Verify all resource tuples can be paid and deduct them. Returns 0 on success or error code."""
        player = self.state["player"]
        rb_counts = self._reborn_goods_counts()
        need_rb: Counter[int] = Counter()
        need_goods: Counter[int] = Counter()
        need_curr: Counter[str] = Counter()
        for rt, rm, rn in reqs:
            if rn <= 0:
                continue
            if rt == 2701:
                need_rb[rm] += rn
            elif rt in _REBORN_CURRENCY_MAP:
                need_curr[_REBORN_CURRENCY_MAP[rt]] += rn
            else:
                need_goods[rm] += rn

        for mid, cnt in need_rb.items():
            if rb_counts.get(mid, 0) < cnt:
                return -1126
        for mid, cnt in need_goods.items():
            if self._goods_qty(mid) < cnt:
                return -1126
        for field, cnt in need_curr.items():
            if int(player.get(field, 0)) < cnt:
                return -1105 if field == "Diamond" else -1

        if need_rb:
            touched: set[int] = set()
            for mid, cnt in need_rb.items():
                rb_counts[mid] -= cnt
            self._set_reborn_goods_counts(rb_counts, touched)
        for mid, cnt in need_goods.items():
            self._consume_goods(mid, cnt)
        for field, cnt in need_curr.items():
            self.ledger.apply_player_delta(player, self.profile_name, field, -cnt, source=source)
            if field == "Diamond":
                self._last_rpc_context["diamond_spent"] = int(self._last_rpc_context.get("diamond_spent", 0)) + cnt
        return 0

    def _hero_reborn_refund_tuples(self, hero: dict[str, Any]) -> list[tuple[int, int, int]]:
        """Compute full Reborn resource, stone, gold, and duplicate refunds for HeroRebirth."""
        cfg = self.game_data.get("heroes", {}).get(str(hero.get("HeroModelId", 0)), {})
        rc = self._hero_reborn_class_id(cfg)
        if rc <= 0:
            return []
        base_id = rc * 1000
        cur_id = int(hero.get("RebornId", base_id))
        if cur_id < base_id:
            return []

        rlv = self.game_data.get("reborn_lv", {})
        slots_tbl = self.game_data.get("reborn_slots", {})
        refunds: list[tuple[int, int, int]] = []
        is_mc = int(cfg.get("specialType", 0)) == 255
        for rid in range(base_id, cur_id):
            row = rlv.get(str(rid))
            if not row:
                continue
            for srow in slots_tbl.get(str(rid), {}).values():
                mid = int(srow.get("useModelID", 0))
                if mid > 0:
                    refunds.append((2701, mid, 1))
            refunds.extend(_parse_res_tuples(str(row.get("useStr", ""))))
            dupes = int(row.get("useSameHeroNum", 0))
            if not is_mc and dupes > 0:
                refunds.append((1201, int(hero["HeroModelId"]), dupes))

        cur_slots_cfg = slots_tbl.get(str(cur_id), {})
        for entry in hero.get("RebornStepInfo") or []:
            if isinstance(entry, dict) and int(entry.get("Status", 0)) == 1:
                srow = cur_slots_cfg.get(str(entry.get("Num", 0)))
                mid = int(srow.get("useModelID", 0)) if srow else 0
                if mid > 0:
                    refunds.append((2701, mid, 1))
        return refunds

    def _compute_reborn_compose_status(self) -> list[dict[str, Any]]:
        """Build NetworkResData.RebornnComposeStatus entries for craftable RebornGoods."""
        rb_counts = self._reborn_goods_counts()
        status_list: list[dict[str, Any]] = []
        for mid_str, row in sorted(self.game_data.get("reborn_goods", {}).items(), key=lambda x: int(x[0])):
            if not str(row.get("compoundUse", "")).strip():
                continue
            work_rb = dict(rb_counts)
            # Strip one copy of target from work_rb so we test whether a fresh unit is craftable.
            work_rb[int(mid_str)] = 0
            can_craft = self._can_craft_reborn_good(int(mid_str), 1, work_rb, {})
            status_list.append({"GoodsId": int(mid_str), "Status": can_craft})
        return status_list

    # ------------------------------------------------------------------
    # RebornInfo RPCs (5)
    # ------------------------------------------------------------------
    def _rpc_reborn_activate(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            return self._reborn_reject(-1)
        hero_id = str(data[0])
        try:
            slot_id = int(data[1])
        except (TypeError, ValueError):
            return self._reborn_reject(-1)
        if slot_id not in (1, 2, 3, 4):
            return self._reborn_reject(-1)
        hero = next((h for h in self.state.get("heroes", []) if str(h.get("Id")) == hero_id), None)
        if not hero:
            return self._reborn_reject(-1)
        self._ensure_hero_reborn_fields(hero)
        rid = int(hero.get("RebornId", 0))
        if rid <= 0 or str(rid + 1) not in self.game_data.get("reborn_lv", {}):
            return self._reborn_reject(-1)

        slot_entry = next((s for s in hero["RebornStepInfo"] if int(s["Num"]) == slot_id), None)
        if not slot_entry or int(slot_entry["Status"]) == 1:
            return self._reborn_reject(-1)
        srow = self.game_data.get("reborn_slots", {}).get(str(rid), {}).get(str(slot_id))
        if not srow:
            return self._reborn_reject(-1)
        use_mid = int(srow.get("useModelID", 0))
        err = self._check_and_consume_tuples([(2701, use_mid, 1)], source=f"reborn_activate:{hero['HeroModelId']}")
        if err != 0:
            return self._reborn_reject(err)

        slot_entry["Status"] = 1
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {
            "HeroId": hero["Id"],
            "RebornId": hero["RebornId"],
            "RebornStepInfo": copy.deepcopy(hero["RebornStepInfo"]),
        }

    def _rpc_reborn_one_key_activate(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            return self._reborn_reject(-1)
        hero_id = str(data[0])
        hero = next((h for h in self.state.get("heroes", []) if str(h.get("Id")) == hero_id), None)
        if not hero:
            return self._reborn_reject(-1)
        self._ensure_hero_reborn_fields(hero)
        rid = int(hero.get("RebornId", 0))
        if rid <= 0 or str(rid + 1) not in self.game_data.get("reborn_lv", {}):
            return self._reborn_reject(-1)

        slot_cfg = self.game_data.get("reborn_slots", {}).get(str(rid), {})
        work_rb = self._reborn_goods_counts()
        work_other: dict[tuple[int, int], int] = {}
        activated_nums: list[int] = []
        for entry in hero["RebornStepInfo"]:
            if int(entry["Status"]) == 1:
                continue
            srow = slot_cfg.get(str(entry["Num"]))
            if not srow:
                continue
            mid = int(srow.get("useModelID", 0))
            snap_rb = dict(work_rb)
            snap_other = dict(work_other)
            if self._can_craft_reborn_good(mid, 1, work_rb, work_other):
                activated_nums.append(int(entry["Num"]))
            else:
                work_rb = snap_rb
                work_other = snap_other

        if not activated_nums:
            return self._reborn_reject(-1126)

        touched: set[int] = set()
        self._set_reborn_goods_counts(work_rb, touched)
        for entry in hero["RebornStepInfo"]:
            if int(entry["Num"]) in activated_nums:
                entry["Status"] = 1

        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {
            "HeroId": hero["Id"],
            "RebornId": hero["RebornId"],
            "RebornStepInfo": copy.deepcopy(hero["RebornStepInfo"]),
        }

    def _rpc_reborn_upgrade(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            return self._reborn_reject(-1)
        hero_id = str(data[0])
        dupe_ids_raw = data[1] if len(data) >= 2 and isinstance(data[1], list) else []
        dupe_ids = [str(x) for x in dupe_ids_raw]

        hero = next((h for h in self.state.get("heroes", []) if str(h.get("Id")) == hero_id), None)
        if not hero:
            return self._reborn_reject(-1)
        self._ensure_hero_reborn_fields(hero)
        rid = int(hero.get("RebornId", 0))
        rlv = self.game_data.get("reborn_lv", {})
        cur_row = rlv.get(str(rid))
        next_row = rlv.get(str(rid + 1))
        if not cur_row or not next_row:
            return self._reborn_reject(-1)

        if int(self.state["player"].get("Lv", 1)) < int(cur_row.get("needLv", 0)):
            return self._reborn_reject(-1)
        if any(int(s.get("Status", 0)) != 1 for s in hero["RebornStepInfo"]):
            return self._reborn_reject(-1)

        cfg = self.game_data.get("heroes", {}).get(str(hero["HeroModelId"]), {})
        is_mc = int(cfg.get("specialType", 0)) == 255
        req_dupes = 0 if is_mc else int(cur_row.get("useSameHeroNum", 0))
        deployed = self._deployed_hero_ids()
        if req_dupes > 0:
            if len(dupe_ids) != req_dupes or len(set(dupe_ids)) != req_dupes:
                return self._reborn_reject(-1)
            heroes_map = {str(h["Id"]): h for h in self.state.get("heroes", [])}
            for did in dupe_ids:
                dh = heroes_map.get(did)
                if (
                    not dh
                    or did == hero_id
                    or did in deployed
                    or int(dh.get("HeroModelId", 0)) != int(hero["HeroModelId"])
                    or int(dh.get("Step", 0)) != 0
                ):
                    return self._reborn_reject(-1)
        elif dupe_ids:
            return self._reborn_reject(-1)

        costs = _parse_res_tuples(str(cur_row.get("useStr", "")))
        err = self._check_and_consume_tuples(costs, source=f"reborn_upgrade:{hero['HeroModelId']}")
        if err != 0:
            return self._reborn_reject(err)

        if req_dupes > 0:
            drop_set = set(dupe_ids)
            self.state["heroes"] = [h for h in self.state["heroes"] if str(h.get("Id")) not in drop_set]

        hero["RebornId"] = rid + 1
        hero["RebornStep"] = int(next_row.get("rebornNum", 0))
        hero["RebornStepInfo"] = _default_reborn_step_info(hero["RebornId"])
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {
            "HeroId": hero["Id"],
            "RebornId": hero["RebornId"],
            "RebornStepInfo": copy.deepcopy(hero["RebornStepInfo"]),
        }

    def _rpc_reborn_goods_compose(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            return self._reborn_reject(-1)
        try:
            model_id = int(data[0])
        except (TypeError, ValueError):
            return self._reborn_reject(-1)
        row = self.game_data.get("reborn_goods", {}).get(str(model_id))
        recipe = str(row.get("compoundUse", "")).strip() if row else ""
        if not recipe:
            return self._reborn_reject(-1)
        reqs = _parse_res_tuples(recipe)
        err = self._check_and_consume_tuples(reqs, source=f"reborn_goods_compose:{model_id}")
        if err != 0:
            return self._reborn_reject(err)
        base_res = self._grant_resources_from_tuples(
            [(2701, model_id, 1)],
            source=f"reborn_goods_compose:{model_id}",
            tx_prefix=f"reborn_compose:{self.profile_name}:{model_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_reborn_goods_refine(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            return self._reborn_reject(-1)
        try:
            model_id = int(data[0])
            num = int(data[1])
        except (TypeError, ValueError):
            return self._reborn_reject(-1)
        if num <= 0:
            return self._reborn_reject(-1)
        row = self.game_data.get("reborn_goods", {}).get(str(model_id))
        out_str = str(row.get("output", "")).strip() if row else ""
        if not out_str:
            return self._reborn_reject(-1)
        err = self._check_and_consume_tuples([(2701, model_id, num)], source=f"reborn_goods_refine:{model_id}")
        if err != 0:
            return self._reborn_reject(err)
        grants = [(rt, rm, rn * num) for rt, rm, rn in _parse_res_tuples(out_str) if rn > 0]
        base_res = self._grant_resources_from_tuples(
            grants,
            source=f"reborn_goods_refine:{model_id}",
            tx_prefix=f"reborn_refine:{self.profile_name}:{model_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # ------------------------------------------------------------------
    # RebornShop RPCs (3)
    # ------------------------------------------------------------------
    def _roll_reborn_shop_row(self, pool_num: int, rng: random.Random, used_ids: set[int]) -> dict[str, Any] | None:
        odds_tbl = self.game_data.get("reborn_shop_odds", {})
        candidates = [r for r in odds_tbl.values() if int(r.get("num", -1)) == pool_num]
        if not candidates:
            candidates = list(odds_tbl.values())
        if not candidates:
            return None
        available = [r for r in candidates if int(r.get("ID", 0)) not in used_ids] or candidates
        roll = rng.randint(1, 10000)
        matched = [r for r in available if int(r.get("oddsMin", 0)) <= roll <= int(r.get("oddsMax", 0))]
        if not matched:
            # If unused subset left a gap around `roll`, pick closest or fallback across candidates
            all_matched = [r for r in candidates if int(r.get("oddsMin", 0)) <= roll <= int(r.get("oddsMax", 0))]
            matched = [all_matched[0]] if all_matched else [available[roll % len(available)]]
        return matched[0]

    def _generate_reborn_shop_goods(self, seed_hint: int | None = None) -> list[dict[str, Any]]:
        cfg = self.game_data.get("reborn_config", {})
        total = int(cfg.get("refreshNum", _REBORN_SHOP_SLOT_COUNT)) or _REBORN_SHOP_SLOT_COUNT
        rng = random.Random(seed_hint) if seed_hint is not None else random.Random()
        goods: list[dict[str, Any]] = []
        used_ids: set[int] = set()
        for idx in range(total):
            pool_num = 1 if idx == 0 else 0
            row = self._roll_reborn_shop_row(pool_num, rng, used_ids)
            if not row:
                continue
            used_ids.add(int(row.get("ID", 0)))
            sell = _parse_res_tuples(str(row.get("outStr", "")))
            buy = _parse_res_tuples(str(row.get("useStr", "")))
            if not sell or not buy:
                continue
            s_rt, s_mid, s_num = sell[0]
            b_rt, b_mid, b_num = buy[0]
            goods.append(
                {
                    "Id": str(uuid.uuid4()),
                    "SellResourceTypeSub": s_rt,
                    "SellGoodsModelId": s_mid,
                    "SellNum": s_num,
                    "BuyResourceTypeSub": b_rt,
                    "BuyGoodsModelId": b_mid,
                    "BuyNum": b_num,
                    "IsSell": 0,
                }
            )
        return goods

    def _sync_reborn_shop_state(self) -> tuple[dict[str, Any], int]:
        cfg = self.game_data.get("reborn_config", {})
        free_max = max(1, int(cfg.get("freeRefreshMax", 2)))
        interval = max(60, int(cfg.get("freeRefreshCD", 7200)))
        now = self.now_ts()
        today = self.clock.today_str(now)
        midnight = self.clock.midnight_ts(now)
        cur_period = midnight + (now - midnight) // interval * interval
        next_deadline = cur_period + interval

        rs = self.state.setdefault("reborn_shop", {})
        changed = False
        if "free_period" not in rs:
            rs["free_count"] = int(rs.get("free_count", free_max))
            rs["free_period"] = cur_period
            rs["diamond_count"] = int(rs.get("diamond_count", 0))
            rs["last_day"] = today
            changed = True
        elif cur_period > int(rs["free_period"]):
            elapsed = (cur_period - int(rs["free_period"])) // interval
            rs["free_count"] = min(free_max, int(rs.get("free_count", 0)) + elapsed)
            rs["free_period"] = cur_period
            changed = True

        if today > str(rs.get("last_day", "")):
            rs["last_day"] = today
            rs["diamond_count"] = 0
            changed = True

        if not isinstance(rs.get("goods"), list) or not rs["goods"] or now >= int(rs.get("deadline", 0)):
            rs["goods"] = self._generate_reborn_shop_goods()
            rs["deadline"] = next_deadline
            changed = True

        if changed:
            self.save()
        return rs, free_max

    def _reborn_shop_payload(self, rs: dict[str, Any], free_max: int) -> dict[str, Any]:
        return {
            "FreeCount": int(rs.get("free_count", 0)),
            "DiamondCount": int(rs.get("diamond_count", 0)),
            "FreeRefreshMax": free_max,
            "LastFreshDate": int(rs.get("deadline", 0)),
            "RebornShopGoodsData": copy.deepcopy(rs.get("goods", [])),
        }

    def _rpc_reborn_shop_get_info(self, _data: Any) -> dict[str, Any]:
        rs, free_max = self._sync_reborn_shop_state()
        return self._reborn_shop_payload(rs, free_max)

    def _rpc_reborn_shop_refresh(self, data: Any) -> dict[str, Any]:
        try:
            refresh_type = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            refresh_type = 0
        if refresh_type not in (1, 2, 3):
            return self._reborn_reject(-1)

        rs, free_max = self._sync_reborn_shop_state()
        cfg = self.game_data.get("reborn_config", {})
        if refresh_type == 1:
            if int(rs.get("free_count", 0)) <= 0:
                return self._reborn_reject(-1)
            rs["free_count"] = int(rs["free_count"]) - 1
        elif refresh_type == 2:
            token_reqs = _parse_res_tuples(str(cfg.get("refreshUseResource", "1605,16050010,1")))
            err = self._check_and_consume_tuples(token_reqs, source="reborn_shop_refresh_token")
            if err != 0:
                return self._reborn_reject(err)
        else:
            dia_cost = int(cfg.get("refreshUseDiamond", 20))
            err = self._check_and_consume_tuples([(1111, 0, dia_cost)], source="reborn_shop_refresh_diamond")
            if err != 0:
                return self._reborn_reject(err)
            rs["diamond_count"] = int(rs.get("diamond_count", 0)) + 1

        rs["goods"] = self._generate_reborn_shop_goods()
        self.save()
        return self._reborn_shop_payload(rs, free_max)

    def _rpc_reborn_shop_buy(self, data: Any) -> dict[str, Any]:
        item_id = str(data[0]) if isinstance(data, list) and data else ""
        if not item_id:
            return self._reborn_reject(-1)
        rs, _free_max = self._sync_reborn_shop_state()
        entry = next((g for g in rs.get("goods", []) if str(g.get("Id")) == item_id), None)
        if not entry or int(entry.get("IsSell", 0)) != 0:
            return self._reborn_reject(-1)

        buy_tuple = (
            int(entry["BuyResourceTypeSub"]),
            int(entry["BuyGoodsModelId"]),
            int(entry["BuyNum"]),
        )
        sell_tuple = (
            int(entry["SellResourceTypeSub"]),
            int(entry["SellGoodsModelId"]),
            int(entry["SellNum"]),
        )
        err = self._check_and_consume_tuples([buy_tuple], source=f"reborn_shop_buy:{sell_tuple[1]}")
        if err != 0:
            return self._reborn_reject(err)

        entry["IsSell"] = 1
        base_res = self._grant_resources_from_tuples(
            [sell_tuple],
            source=f"reborn_shop_buy:{sell_tuple[1]}",
            tx_prefix=f"reborn_shop_buy:{self.profile_name}:{item_id}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}
