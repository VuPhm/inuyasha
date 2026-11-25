"""Treasure loot/refine/step/compose, Fashion, Refine, Rebirth & MysteryShop handlers extracted from emulator.py."""

from __future__ import annotations

from collections import Counter
import copy
import random
import time
from typing import Any
import uuid

from emulator_common import EMPTY_ENTITY_ID, _parse_resource_str
from reborn_handlers import _default_reborn_step_info


class TreasureRebirthHandlersMixin:
    """Mixin hosting Treasure, Fashion, Refine, Rebirth, and MysteryShop handlers."""

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
        enemy_fap = sum(int(h["HP"] + h["AP"] * 10 + h["DEF"] * 10) for h in enemies if h)

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

        self._record_daily_task_progress(3, 1)
        if loot_success == 1:
            self._inc_stat("treasure_loot_wins", 1)
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

    def _rpc_treasure_loot_one_key(self, data: Any) -> dict[str, Any]:
        player = self.state["player"]
        gate = self.game_data["module_subs"]["2506"]
        level = int(player["Lv"])
        vip = int(player.get("Vip", 0))
        if level < int(gate["openLv"]) and not (
            vip >= int(gate["advancedOpenVIPLv"]) and level >= int(gate["VIPNeedLv"])
        ):
            self._last_rpc_context["status"] = -5902
            return {}

        treasure_id = int(data[0]) if isinstance(data, list) and data else 0
        allow_continue = bool(data[1]) if isinstance(data, list) and len(data) >= 2 and data[1] else False
        treasure = self.game_data["treasures"].get(str(treasure_id), {})
        req_debris = [int(mid) for mid in treasure.get("debrisModelIds", [])]
        owned_counts = {
            int(row["TreasureDebrisModelId"]): int(row.get("Num", 0))
            for row in self.state["treasure_debris"]
            if int(row.get("Num", 0)) > 0
        }
        if allow_continue and req_debris:
            min_owned = min(owned_counts.get(mid, 0) for mid in req_debris)
            target_num = min_owned + 1
            missing = [mid for mid in req_debris if owned_counts.get(mid, 0) < target_num]
        else:
            missing = [mid for mid in req_debris if owned_counts.get(mid, 0) <= 0]
        if not missing:
            self._last_rpc_context["status"] = -2010
            return {}

        sta_cost = int(self.game_data["sta_config"]["perUseNum"])
        choices = []
        loot_info = {}
        base = []
        debris_id = missing[0]
        for missing_id in missing:
            debris_id = missing_id
            target = self._build_treasure_robots(debris_id)[0]["LootPlayerId"]
            while int(player["STA"]) >= sta_cost:
                result = self._execute_single_treasure_loot(target, treasure_id, debris_id)
                base = result["BaseGetGameResourceList"]
                choices.append(next(card for card in result["ChoiceGetGameResource"] if card["IsDrop"] == 1))
                if result["IsWinLootSuccess"]:
                    loot_info[str(len(choices))] = debris_id
                    break
            if int(player["STA"]) < sta_cost:
                break
        if not choices:
            self._last_rpc_context["status"] = -1120
            return {}
        self.save()
        return {
            "TotalLootCount": len(choices),
            "LootInfo": loot_info,
            "LastTreasureModelId": debris_id,
            "BaseGameResource": base,
            "ChoiceGameResource": choices,
        }

    def _rpc_treasure_compose(self, data: Any) -> dict[str, Any]:
        treasure_model_id = int(data[0]) if isinstance(data, list) and data else 0
        req_count = int(data[1]) if isinstance(data, list) and len(data) >= 2 and data[1] is not None else 1
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
        max_sets = min(int(by_model.get(int(did), {}).get("Num", 0)) for did in req_debris)
        if req_count == 0:
            compose_n = min(50, max_sets)
        else:
            compose_n = max(1, min(50, req_count))
        if compose_n < 1 or max_sets < compose_n:
            return {"IsTreasureDebrisNotEnough": 0}

        for did in req_debris:
            did_int = int(did)
            entry = by_model[did_int]
            entry["Num"] = int(entry["Num"]) - compose_n
            if entry["Num"] <= 0:
                self.state["treasure_debris"] = [
                    d for d in self.state["treasure_debris"] if int(d["TreasureDebrisModelId"]) != did_int
                ]
            self._mark_treasure_debris_changed(did_int)

        rtype = int(tr_cfg.get("typeID", 1402 if str(treasure_model_id).startswith("1402") else 1401))
        base_res = self._grant_resources_from_tuples(
            [(rtype, treasure_model_id, compose_n)],
            source=f"treasure_compose:{treasure_model_id}:x{compose_n}",
            tx_prefix=f"compose:{self.profile_name}:{treasure_model_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res, "ComposedCount": compose_n}

    def _rpc_fashion_dress_up(self, data: Any) -> dict[str, Any]:
        entity_id = str(data[0]) if isinstance(data, list) and data else EMPTY_ENTITY_ID
        if entity_id == EMPTY_ENTITY_ID:
            self.state["player"]["FashionModelId"] = 0
            self._recalc_all_slots_and_fap()
            self._last_rpc_context["slots_changed"] = True
            self.save()
            return {"FashionModelId": 0}
        target = next((f for f in self.state.get("fashions", []) if str(f["Id"]) == entity_id), None)
        if not target:
            self._last_rpc_context["status"] = -1
            return {}
        self.state["player"]["FashionModelId"] = int(target["FashionModelId"])
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
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
        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
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

    # ------------------------- R7.2: Refine, MysteryShop, Glory, GiftLv, GiftLogin -------------------------

    def _rpc_hero_refine(self, data: Any) -> dict[str, Any]:
        """Disassemble idle fodder heroes (e.g. Tamotu 12013054 from Guide 7 / 2071)."""
        raw_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        req_ids = [str(x) for x in raw_ids if x]
        if not req_ids:
            self._last_rpc_context["status"] = -1
            return {}
        deployed_ids = self._deployed_hero_ids()
        heroes_by_id = {str(h["Id"]): h for h in self.state.get("heroes", [])}
        heroes_cfg = self.game_data.get("heroes", {})
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hid in req_ids:
            if hid in seen or hid in deployed_ids:
                continue
            h = heroes_by_id.get(hid)
            if not h:
                continue
            cfg = heroes_cfg.get(str(h.get("HeroModelId", 0)), {})
            if int(cfg.get("specialType", 0)) == 255 or not cfg.get("outputResource"):
                continue
            seen.add(hid)
            targets.append(h)
        if not targets:
            self._last_rpc_context["status"] = -1
            return {}

        totals: dict[tuple[int, int], int] = {}
        remove_ids = {h["Id"] for h in targets}
        for h in targets:
            cfg = heroes_cfg.get(str(h["HeroModelId"]), {})
            for rtype, rmodel, rnum in _parse_resource_str(str(cfg.get("outputResource", ""))):
                if rnum > 0:
                    totals[(rtype, rmodel)] = totals.get((rtype, rmodel), 0) + rnum
        tuples: list[tuple[int, int, int]] = [(rt, rm, rn) for (rt, rm), rn in totals.items()]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="hero_refine",
            tx_prefix=f"hero_refine:{self.profile_name}:{uuid.uuid4()}",
        )
        self.state["heroes"] = [h for h in self.state.get("heroes", []) if h["Id"] not in remove_ids]
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_equip_refine(self, data: Any) -> dict[str, Any]:
        """Disassemble unequipped equipment items for their config outputResource/Gold."""
        raw_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        req_ids = [str(x) for x in raw_ids if x]
        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Weapon", "Helmet", "Clothes", "Necklace")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        equips_by_id = {str(e["Id"]): e for e in self.state.get("equips", [])}
        equips_cfg = self.game_data.get("equips", {})
        targets = [equips_by_id[eid] for eid in dict.fromkeys(req_ids) if eid in equips_by_id and eid not in equipped_ids]
        if not targets:
            self._last_rpc_context["status"] = -1
            return {}
        tuples: list[tuple[int, int, int]] = []
        for eq in targets:
            cfg = equips_cfg.get(str(eq.get("EquipModelId", 0)), {})
            tuples.extend(_parse_resource_str(str(cfg.get("outputResource", ""))))
            if int(eq.get("Gold", 0)) > 0:
                tuples.append((1112, 0, int(eq["Gold"])))
        remove_ids = {e["Id"] for e in targets}
        self.state["equips"] = [e for e in self.state.get("equips", []) if e["Id"] not in remove_ids]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="equip_refine",
            tx_prefix=f"equip_refine:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_treasure_refine(self, data: Any) -> dict[str, Any]:
        """Disassemble unequipped treasures for their config outputResource."""
        raw_ids = list(data[0]) if isinstance(data, list) and data and isinstance(data[0], list) else []
        req_ids = [str(x) for x in raw_ids if x]
        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Book", "Horse")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        tr_by_id = {str(t["Id"]): t for t in self.state.get("treasures", [])}
        tr_cfg = self.game_data.get("treasures", {})
        targets = [tr_by_id[tid] for tid in dict.fromkeys(req_ids) if tid in tr_by_id and tid not in equipped_ids]
        if not targets:
            self._last_rpc_context["status"] = -1
            return {}
        tuples: list[tuple[int, int, int]] = []
        for tr in targets:
            cfg = tr_cfg.get(str(tr.get("TreasureModelId", 0)), {})
            tuples.extend(_parse_resource_str(str(cfg.get("outputResource", ""))))
        remove_ids = {t["Id"] for t in targets}
        self.state["treasures"] = [t for t in self.state.get("treasures", []) if t["Id"] not in remove_ids]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="treasure_refine",
            tx_prefix=f"treasure_refine:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # ------------------------- R7.6: Treasure LvUp/StepUp & Hero/Equip/Treasure Rebirth -------------------------

    def _sync_slot_treasures(self) -> None:
        treasures_by_id = {t["Id"]: t for t in self.state.get("treasures", [])}
        for slot in self.state.get("slots", []):
            for tkey in ("Book", "Horse"):
                s_tr = slot.get(tkey)
                if isinstance(s_tr, dict) and s_tr.get("Id") in treasures_by_id:
                    tr = treasures_by_id[s_tr["Id"]]
                    s_tr["Lv"] = int(tr.get("Lv", 0))
                    s_tr["Step"] = int(tr.get("Step", 0))
                    s_tr["EXP"] = int(tr.get("EXP", 0))
        self._recalc_all_slots_and_fap()

    def _treasure_lv_for_exp(self, treasure_model_id: int, exp_total: int, max_lv: int) -> int:
        tm = self.game_data.get("treasures", {}).get(str(treasure_model_id), {})
        exp_r = float(tm.get("expR", 1.0))
        if exp_r <= 0:
            return 0
        lv_tbl = self.game_data.get("treasure_lv", {})
        cur_lv = 0
        for lv in range(1, max(1, max_lv) + 1):
            row = lv_tbl.get(str(lv))
            if not row:
                break
            req_exp = int(round(float(row.get("baseExpTotal", 0)) * exp_r))
            if exp_total >= req_exp:
                cur_lv = lv
            else:
                break
        return cur_lv

    def _rpc_treasure_lv_up(self, data: Any) -> dict[str, Any]:
        """Consume unequipped fodder treasures/EXP items to strengthen target Treasure (ModuleSub 1402)."""
        entity_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        mat_ids = [str(x) for x in (data[1] if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list) else []) if x]
        tr = next((t for t in self.state.get("treasures", []) if str(t.get("Id")) == entity_id), None)
        if not tr or not mat_ids:
            self._last_rpc_context["status"] = -1
            return {}

        treasures_cfg = self.game_data.get("treasures", {})
        tm = treasures_cfg.get(str(tr.get("TreasureModelId", 0)), {})
        max_lv = int(tm.get("maxLV", 100))
        if int(tr.get("Lv", 0)) >= max_lv or float(tm.get("expR", 0)) <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Book", "Horse")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        tr_by_id = {str(t["Id"]): t for t in self.state.get("treasures", [])}
        consumed: list[dict[str, Any]] = []
        gain_exp = 0
        seen: set[str] = set()
        for mid in mat_ids:
            if mid in seen or mid == entity_id or mid in equipped_ids:
                continue
            mat = tr_by_id.get(mid)
            if not mat:
                continue
            mcfg = treasures_cfg.get(str(mat.get("TreasureModelId", 0)), {})
            base_exp = int(mcfg.get("baseExp", 1000))
            gain_exp += max(0, base_exp + int(mat.get("EXP", 0)))
            seen.add(mid)
            consumed.append(mat)
        if not consumed or gain_exp <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        self.state["treasures"] = [t for t in self.state.get("treasures", []) if str(t["Id"]) not in seen]
        new_exp = int(tr.get("EXP", 0)) + gain_exp
        tr["EXP"] = new_exp
        tr["Lv"] = self._treasure_lv_for_exp(int(tr["TreasureModelId"]), new_exp, max_lv)
        self._inc_stat("treasure_lvup_count", 1)
        self._sync_slot_treasures()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {
            "Id": tr["Id"],
            "TreasureModelId": int(tr["TreasureModelId"]),
            "Lv": int(tr["Lv"]),
            "Step": int(tr.get("Step", 0)),
            "EXP": int(tr["EXP"]),
        }

    def _rpc_treasure_step_up(self, data: Any) -> dict[str, Any]:
        """Advance Treasure Step using duplicate card or Substitute Stone (ModuleSub 1404)."""
        entity_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        mat_ids = [str(x) for x in (data[1] if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list) else []) if x]
        # VN Lua TreasureExtraLayer sends data[2]=0 with [] for Substitute Stone, or data[2]=1 with [dupe_id,...] for duplicate cards.
        if_sub = len(mat_ids) == 0

        tr = next((t for t in self.state.get("treasures", []) if str(t.get("Id")) == entity_id), None)
        if not tr:
            self._last_rpc_context["status"] = -1
            return {}
        tm = self.game_data.get("treasures", {}).get(str(tr.get("TreasureModelId", 0)), {})
        cur_step = int(tr.get("Step", 0))
        max_step = int(tm.get("maxStep", 0))
        if max_step <= 0 or cur_step >= max_step:
            self._last_rpc_context["status"] = -1
            return {}

        val_lv = int(tm.get("valueLv", 5))
        step_row = self.game_data.get("treasure_step", {}).get(str(val_lv * 1000 + cur_step))
        if not step_row or int(tr.get("Lv", 0)) < int(step_row.get("needLv", 0)):
            self._last_rpc_context["status"] = -1
            return {}

        extra_reqs = _parse_resource_str(str(step_row.get("upUseExtraStr", "")))
        sub_reqs = _parse_resource_str(str(step_row.get("upUseBaseSubStr", "")))
        need_cards = int(step_row.get("upUseBaseCardNum", 0))

        # Validate costs before mutating state
        cost_tuples: list[tuple[int, int, int]] = list(extra_reqs)
        if if_sub:
            if not bool(tm.get("ifSub", True)):
                self._last_rpc_context["status"] = -1
                return {}
            cost_tuples.extend(sub_reqs)
        for rt, rm, rn in cost_tuples:
            if rt == 1112 and int(self.state["player"].get("Gold", 0)) < rn:
                self._last_rpc_context["status"] = -1
                return {}
            if rt >= 1500:
                g = next((x for x in self.state.get("goods", []) if int(x["GoodsModelId"]) == rm), None)
                if not g or int(g.get("Num", 0)) < rn:
                    self._last_rpc_context["status"] = -1
                    return {}

        dupe_consumed: list[dict[str, Any]] = []
        if not if_sub and need_cards > 0:
            equipped_ids = {
                slot[k]["Id"]
                for slot in self.state.get("slots", [])
                for k in ("Book", "Horse")
                if isinstance(slot.get(k), dict) and slot[k].get("Id")
            }
            tr_by_id = {str(t["Id"]): t for t in self.state.get("treasures", [])}
            for mid in mat_ids:
                if len(dupe_consumed) >= need_cards:
                    break
                if mid == entity_id or mid in equipped_ids or any(c["Id"] == mid for c in dupe_consumed):
                    continue
                cand = tr_by_id.get(mid)
                if cand and int(cand.get("TreasureModelId", 0)) == int(tr["TreasureModelId"]):
                    dupe_consumed.append(cand)
            if len(dupe_consumed) < need_cards:
                self._last_rpc_context["status"] = -1
                return {}

        used_log = tr.setdefault("step_materials_used", [])
        for rt, rm, rn in cost_tuples:
            if rn <= 0:
                continue
            if rt == 1112:
                self.ledger.apply_player_delta(
                    self.state["player"],
                    self.profile_name,
                    "Gold",
                    -rn,
                    source=f"treasure_step_up:{tr['TreasureModelId']}",
                )
                used_log.append([1112, 0, rn])
            elif rt >= 1500:
                for g in self.state.get("goods", []):
                    if int(g["GoodsModelId"]) == rm:
                        g["Num"] = max(0, int(g["Num"]) - rn)
                        self._mark_goods_changed(rm)
                        break
                used_log.append([rt, rm, rn])

        if dupe_consumed:
            rm_ids = {str(c["Id"]) for c in dupe_consumed}
            self.state["treasures"] = [t for t in self.state.get("treasures", []) if str(t["Id"]) not in rm_ids]
            tr_type = int(tm.get("typeID", 1401))
            used_log.append([tr_type, int(tr["TreasureModelId"]), len(dupe_consumed)])

        tr["Step"] = cur_step + 1
        self._inc_stat("treasure_step_up_count", 1)
        self._sync_slot_treasures()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {
            "Id": tr["Id"],
            "TreasureModelId": int(tr["TreasureModelId"]),
            "Lv": int(tr.get("Lv", 0)),
            "Step": int(tr["Step"]),
            "EXP": int(tr.get("EXP", 0)),
        }

    def _rebirth_target_id(self, data: Any) -> str:
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, list) and first:
                return str(first[0])
            return str(first)
        return ""

    def _rpc_hero_rebirth(self, data: Any) -> dict[str, Any]:
        """Reset non-deployed upgraded Hero back to Lv 1 Step 0 and refund HeroEXP, Gold, Stones, and dupes."""
        hero_id = self._rebirth_target_id(data)
        deployed_ids = self._deployed_hero_ids()
        hero = next((h for h in self.state.get("heroes", []) if str(h.get("Id")) == hero_id), None)
        if not hero or hero_id in deployed_ids:
            self._last_rpc_context["status"] = -1
            return {}

        cur_lv = int(hero.get("Lv", 1))
        cur_step = int(hero.get("Step", 0))
        cur_reborn = int(hero.get("RebornStep", 0))
        cfg = self.game_data.get("heroes", {}).get(str(hero["HeroModelId"]), {})
        base_reborn_id = self._hero_reborn_class_id(cfg) * 1000
        has_reborn_progress = (
            int(hero.get("RebornId", base_reborn_id)) > base_reborn_id
            or any(int(s.get("Status", 0)) == 1 for s in (hero.get("RebornStepInfo") or []))
        )
        if (
            cur_lv <= 1
            and cur_step <= 0
            and cur_reborn <= 0
            and not has_reborn_progress
            and int(hero.get("LiantiLv", 0)) <= 0
            and int(hero.get("LianTiNodeId", 1)) <= 1
            and int(hero.get("LianTiNodeExp", 0)) <= 0
        ):
            self._last_rpc_context["status"] = -1
            return {}

        quality = str(int(cfg.get("quality", 15)))
        rb_tbl = self.game_data.get("hero_rebirth", {}).get(quality, {})
        dia_cost = int(rb_tbl.get(str(cur_step), {}).get("useDiamond", 0)) + int(
            rb_tbl.get(str(cur_reborn), {}).get("useDiamond", 0)
        )
        if int(self.state["player"].get("Diamond", 0)) < dia_cost:
            self._last_rpc_context["status"] = -1
            return {}
        if dia_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -dia_cost,
                source=f"hero_rebirth:{hero['HeroModelId']}",
            )

        refund_tuples: list[tuple[int, int, int]] = []
        val_lv = int(cfg.get("valueLv", 3))
        gold_ratio = int(self.game_data.get("hero_config", {}).get("LVUpUseGoldR", 10000)) / 10000.0
        hero_lv_tbl = self.game_data.get("hero_lv", {})
        base_exp = int(hero_lv_tbl.get(str(val_lv * 1000 + 1), {}).get("EXPTotal", 0))
        cur_exp = int(hero_lv_tbl.get(str(val_lv * 1000 + cur_lv), {}).get("EXPTotal", base_exp))
        soul_refund = max(0, cur_exp - base_exp)
        gold_refund = int(soul_refund * gold_ratio)
        if soul_refund > 0:
            refund_tuples.append((1117, 0, soul_refund))
        if gold_refund > 0:
            refund_tuples.append((1112, 0, gold_refund))

        step_cls = int(cfg.get("stepUpClassID", 0))
        hero_step_tbl = self.game_data.get("hero_step", {})
        for s_idx in range(cur_step):
            row = hero_step_tbl.get(str(step_cls * 1000 + s_idx))
            if not row:
                continue
            refund_tuples.extend(_parse_resource_str(str(row.get("upUse", ""))))
            use_dupes = int(row.get("useNum", 0))
            if use_dupes > 0:
                refund_tuples.append((1201, int(hero["HeroModelId"]), use_dupes))
        refund_tuples.extend(self._hero_reborn_refund_tuples(hero))
        lianti_inv = hero.get("LiantiInvested") if isinstance(hero.get("LiantiInvested"), dict) else {}
        inv_gold = int(lianti_inv.get("gold", 0) or 0)
        if inv_gold > 0:
            refund_tuples.append((1112, 0, inv_gold))
        for gid_s, qty in (lianti_inv.get("stones") or {}).items():
            if str(gid_s).isdigit() and int(qty) > 0:
                refund_tuples.append((1605, int(gid_s), int(qty)))

        hero["Lv"] = 1
        hero["EXP"] = 0
        hero["Step"] = 0
        hero["RebornId"] = base_reborn_id
        hero["RebornStepInfo"] = _default_reborn_step_info(base_reborn_id)
        hero["RebornStep"] = 0
        hero["LiantiLv"] = 0
        hero["LianTiNodeId"] = 1
        hero["LianTiNodeExp"] = 0
        hero["LvUpExp"] = self._lianti_lv_exp(0) or 130
        hero["LiantiInvested"] = {"gold": 0, "stones": {}}
        hero["HP"] = int(cfg.get("HPBase", hero.get("HP", 100)))
        hero["AP"] = int(cfg.get("APBase", hero.get("AP", 20)))
        hero["DEF"] = int(cfg.get("DEFBase", hero.get("DEF", 10)))

        base_res = (
            self._grant_resources_from_tuples(
                refund_tuples,
                source=f"hero_rebirth:{hero['HeroModelId']}",
                tx_prefix=f"hero_rebirth:{self.profile_name}:{hero_id}:{uuid.uuid4()}",
            )
            if refund_tuples
            else []
        )
        self._inc_stat("rebirth_count", 1)
        self.save()
        return {"HeroInfo": copy.deepcopy(hero), "BaseGetGameResourceList": base_res}

    def _rpc_equip_rebirth(self, data: Any) -> dict[str, Any]:
        """Reset unequipped gear and return its enhancement and recorded step costs."""
        equip_id = self._rebirth_target_id(data)
        eq = next((e for e in self.state.get("equips", []) if str(e.get("Id")) == equip_id), None)
        if not eq:
            return self._reject_resource_change(-1301)
        if equip_id in self._equipped_item_ids():
            return self._reject_resource_change(-1304)

        cur_lv = int(eq.get("Lv", 0))
        cur_step = int(eq.get("Step", 0))
        if cur_lv <= 0 and cur_step <= 0:
            return self._reject_resource_change(-1308)

        cfg = self.game_data.get("equips", {}).get(str(eq["EquipModelId"]), {})
        quality = str(int(cfg.get("quality", 30)))
        rb_tbl = self.game_data.get("equip_rebirth", {}).get(quality, {})
        if str(cur_step) not in rb_tbl:
            return self._reject_resource_change(-1308)
        dia_cost = rb_tbl[str(cur_step)]["useDiamond"]
        player = self.state["player"]
        if int(player.get("Diamond", 0)) < dia_cost:
            return self._reject_resource_change(-1105)

        clv = str(int(cfg.get("colorLV", 1)))
        lv_tbl = self.game_data.get("equip_lv_up", {}).get(clv, {})
        computed_gold = sum(int(lv_tbl.get(str(lv_i), {}).get("lvUpUseNum", 0)) for lv_i in range(cur_lv))
        refund_gold = max(int(eq.get("Gold", 0)), computed_gold)
        materials = eq.get("StepMaterials", [])
        refund_gold += sum(material["Gold"] for material in materials)
        refunds = [(1112, 0, refund_gold)] if refund_gold > 0 else []
        refunds.extend((self.game_data["equips"][str(material["ModelId"])]["typeID"], material["ModelId"], 1)
                       for material in materials)

        def rebirth():
            source = f"equip_rebirth:{eq['EquipModelId']}"
            if dia_cost:
                self.ledger.apply_player_delta(player, self.profile_name, "Diamond", -dia_cost, source=source)
                self._last_rpc_context["diamond_spent"] = dia_cost
            eq.update(Lv=0, Step=0, Gold=0)
            eq.pop("StepMaterials", None)
            output = self._grant_resources_from_tuples(
                refunds, source=source, tx_prefix=f"{source}:{equip_id}:{uuid.uuid4()}",
            ) if refunds else []
            self._inc_stat("rebirth_count", 1)
            return {"EquipInfo": copy.deepcopy(eq), "BaseGetGameResourceList": output}

        return self._commit_resource_change(rebirth)

    def _treasure_exp_refund_tuples(self, tm: dict[str, Any], tr: dict[str, Any]) -> list[tuple[int, int, int]]:
        """Convert accumulated Treasure EXP (or Lv floor if EXP==0) into fodder refund tuples."""
        tr_type = int(tm.get("typeID", 1401))
        cur_exp = int(tr.get("EXP", 0))
        cur_lv = int(tr.get("Lv", 0))
        if cur_exp <= 0 and cur_lv > 0:
            row = self.game_data.get("treasure_lv", {}).get(str(cur_lv), {})
            cur_exp = int(round(float(row.get("baseExpTotal", 0)) * float(tm.get("expR", 0.5))))
        if cur_exp <= 0:
            return []
        refund_tuples: list[tuple[int, int, int]] = []
        gold_fodder = 14021304 if tr_type == 1402 else 14011304
        silver_fodder = 14020803 if tr_type == 1402 else 14010803
        base_fodder = 14020501 if tr_type == 1402 else 14010501
        g_cnt = cur_exp // 40000
        rem = cur_exp % 40000
        s_cnt = rem // 10000
        b_cnt = (rem % 10000 + 999) // 1000
        if g_cnt > 0:
            refund_tuples.append((tr_type, gold_fodder, g_cnt))
        if s_cnt > 0:
            refund_tuples.append((tr_type, silver_fodder, s_cnt))
        if b_cnt > 0:
            refund_tuples.append((tr_type, base_fodder, b_cnt))
        return refund_tuples

    def _rpc_treasure_rebirth(self, data: Any) -> dict[str, Any]:
        """Reset unequipped Treasure back to Lv 0 Step 0 EXP 0 and refund EXP fodders + Step materials."""
        tr_id = self._rebirth_target_id(data)
        equipped_ids = {
            slot[k]["Id"]
            for slot in self.state.get("slots", [])
            for k in ("Book", "Horse")
            if isinstance(slot.get(k), dict) and slot[k].get("Id")
        }
        tr = next((t for t in self.state.get("treasures", []) if str(t.get("Id")) == tr_id), None)
        if not tr or tr_id in equipped_ids:
            self._last_rpc_context["status"] = -1
            return {}

        cur_lv = int(tr.get("Lv", 0))
        cur_step = int(tr.get("Step", 0))
        cur_exp = int(tr.get("EXP", 0))
        if cur_lv <= 0 and cur_step <= 0 and cur_exp <= 0:
            self._last_rpc_context["status"] = -1
            return {}

        tm = self.game_data.get("treasures", {}).get(str(tr["TreasureModelId"]), {})
        quality = str(int(tm.get("quality", 10)))
        rb_tbl = self.game_data.get("treasure_rebirth", {}).get(quality, {})
        dia_cost = int(rb_tbl.get(str(cur_step), {}).get("useDiamond", 0))
        if int(self.state["player"].get("Diamond", 0)) < dia_cost:
            self._last_rpc_context["status"] = -1
            return {}
        if dia_cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -dia_cost,
                source=f"treasure_rebirth:{tr['TreasureModelId']}",
            )

        tr_type = int(tm.get("typeID", 1401))
        refund_tuples = self._treasure_exp_refund_tuples(tm, tr) if cur_exp > 0 else []

        used_log = tr.pop("step_materials_used", None)
        if isinstance(used_log, list) and used_log:
            for item in used_log:
                if len(item) >= 3 and int(item[2]) > 0:
                    refund_tuples.append((int(item[0]), int(item[1]), int(item[2])))
        elif cur_step > 0:
            val_lv = int(tm.get("valueLv", 5))
            tr_step_tbl = self.game_data.get("treasure_step", {})
            for s_idx in range(cur_step):
                s_row = tr_step_tbl.get(str(val_lv * 1000 + s_idx))
                if not s_row:
                    continue
                refund_tuples.extend(_parse_resource_str(str(s_row.get("upUseExtraStr", ""))))
                cards_n = int(s_row.get("upUseBaseCardNum", 0))
                if cards_n > 0:
                    refund_tuples.append((tr_type, int(tr["TreasureModelId"]), cards_n))

        tr["Lv"] = 0
        tr["Step"] = 0
        tr["EXP"] = 0
        base_res = (
            self._grant_resources_from_tuples(
                refund_tuples,
                source=f"treasure_rebirth:{tr['TreasureModelId']}",
                tx_prefix=f"treasure_rebirth:{self.profile_name}:{tr_id}:{uuid.uuid4()}",
            )
            if refund_tuples
            else []
        )
        self._inc_stat("rebirth_count", 1)
        self.save()
        return {"TreasureInfo": copy.deepcopy(tr), "BaseGetGameResourceList": base_res}

    def _build_mystery_shop_items(self, shop_type: int) -> list[dict[str, Any]]:
        """Build 8 Mystery Shop entries from MysteryshopFixedRelation + MysteryshopOddsPseudoRelation."""
        lv = int(self.state["player"].get("Lv", 1))
        ms_cfg = self.game_data.get("mystery_shop_config", {})
        target_len = max(1, int(ms_cfg.get("refreshNum", 8)))
        fixed_rows = [
            r
            for r in sorted(self.game_data.get("mystery_shop_fixed", {}).values(), key=lambda x: int(x.get("ID", 0)))
            if int(r.get("shopType", 0)) == shop_type and lv >= int(r.get("needLv", 1))
        ]
        # Prefer the lowest needLv fixed slot first (ID=1: 50x 16050001 for 50 HeroCoin) so Lv24 Guide 7 step 211 succeeds
        odds_rows = list(self.game_data.get("mystery_shop_odds", {}).values())
        chosen_rows: list[dict[str, Any]] = []
        if fixed_rows:
            chosen_rows.append(fixed_rows[0])
        if odds_rows:
            pool = random.sample(odds_rows, min(len(odds_rows), max(0, target_len - len(chosen_rows))))
            chosen_rows.extend(pool)
        out: list[dict[str, Any]] = []
        for row in chosen_rows[:target_len]:
            sell_parts = _parse_resource_str(str(row.get("outResource", "")))
            buy_parts = _parse_resource_str(str(row.get("useResource", "")))
            if not sell_parts or not buy_parts:
                continue
            st, sm, sn = sell_parts[0]
            bt, bm, bn = buy_parts[0]
            if not self._is_valid_resource(st, sm):
                continue
            out.append(
                {
                    "Id": str(uuid.uuid4()),
                    "SellResourceTypeSub": st,
                    "SellGoodsModelId": sm,
                    "SellNum": sn,
                    "BuyResourceTypeSub": bt,
                    "BuyGoodsModelId": bm if bm > 0 and bt >= 1500 else 0,
                    "BuyNum": bn,
                    "IsSell": 0,  # Exchange.Enabled = 0 per MysticalStoreScene.lua:20
                }
            )
        return out

    def _mystery_shop_state(self, senior: bool = False) -> dict[str, Any]:
        vip_lv = int(self.state["player"].get("VIPLv", self.state["player"].get("Vip", 0)))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        free_max = max(1, int(vip_cfg.get("freeRefreshMysteryShopMaxNum", 2)))
        max_refresh = int(vip_cfg.get("refreshMysteryShopMaxNum", 10 + vip_lv * 5))
        ms = self.state.setdefault(
            "mystery_shop",
            {"normal": None, "senior": None, "free_date": "", "free_count": free_max, "gold_count": 0},
        )
        now = self.now_ts()
        today = self.clock.today_str(now)
        config = self.game_data["mystery_shop_config"]
        interval = int(config["freeRefreshCD"])
        # Use VN server-day boundaries. Store the most recent credited period so polling
        # and reopening the shop cannot award the same free refresh twice.
        midnight = self.clock.midnight_ts(now)
        normal_period = midnight + (now - midnight) // interval * interval
        changed = False
        if "free_period" not in ms:
            if not ms.get("free_date"):
                ms["free_count"] = free_max
            ms["free_date"] = today
            ms["free_period"] = normal_period
            changed = True
        elif normal_period > ms["free_period"]:
            elapsed = (normal_period - ms["free_period"]) // interval
            ms["free_count"] = min(free_max, ms["free_count"] + elapsed)
            ms["free_period"] = normal_period
            changed = True
        if today > ms.get("free_date", ""):
            ms["free_date"] = today
            ms["gold_count"] = 0
            changed = True

        normal_deadline = ms["free_period"] + interval
        senior_hours = [int(config[field] * 86400) for field in ("seniorRefreshTimeFirst", "seniorRefreshTimeSecond")]
        senior_deadline = next(
            (midnight + seconds for seconds in sorted(senior_hours) if midnight + seconds > now),
            midnight + 86400 + min(senior_hours),
        )
        deadlines = ms.setdefault("deadlines", {})
        # Attach deadlines to legacy stock before it can be rerolled, preserving sold entries.
        for shop, deadline in (("normal", normal_deadline), ("senior", senior_deadline)):
            if shop not in deadlines:
                deadlines[shop] = deadline
                changed = True
        key = "senior" if senior else "normal"
        if ms.get(key) is None or now >= deadlines[key]:
            ms[key] = self._build_mystery_shop_items(1 if senior else 0)
            deadlines[key] = senior_deadline if senior else normal_deadline
            changed = True
        if changed:
            self.save()
        return {
            "FreeCount": int(ms.get("free_count", free_max)),
            "GoldCount": int(ms.get("gold_count", 0)),
            "RefreshMysteryShopMaxNum": max_refresh,
            "MysteryShopGoodsList": ms[key],
            "LastFreshDate": deadlines[key],
        }

    def _rpc_mystery_shop_get_info(self, _data: Any) -> dict[str, Any]:
        return self._mystery_shop_state(senior=False)

    def _rpc_mystery_shop_senior_get_info(self, _data: Any) -> dict[str, Any]:
        return self._mystery_shop_state(senior=True)

    def _do_mystery_shop_refresh(self, refresh_type: int, senior: bool) -> dict[str, Any]:
        ms_state = self._mystery_shop_state(senior=senior)
        ms = self.state["mystery_shop"]
        ms_cfg = self.game_data.get("mystery_shop_config", {})
        if refresh_type not in (1, 2, 3):
            self._last_rpc_context["status"] = -48
            return {}
        if refresh_type == 1:
            if int(ms.get("free_count", 0)) <= 0:
                self._last_rpc_context["status"] = -2105
                return {}
            ms["free_count"] = int(ms["free_count"]) - 1
        elif refresh_type == 2:
            res_str = str(ms_cfg.get("seniorRefreshUseResource" if senior else "refreshUseResource", "1605,16050010,1"))
            _, model, count = _parse_resource_str(res_str)[0]
            if not self._consume_goods_qty(model, count):
                self._last_rpc_context["status"] = -1802
                return {}
            self._mark_goods_changed(model)
            ms["gold_count"] = int(ms.get("gold_count", 0)) + 1
        else:
            if int(ms.get("gold_count", 0)) >= int(ms_state["RefreshMysteryShopMaxNum"]):
                self._last_rpc_context["status"] = -2107
                return {}
            cost = int(ms_cfg.get("seniorRefreshUseDiamond" if senior else "refreshUseDiamond", 20))
            if int(self.state["player"].get("Diamond", 0)) < cost:
                self._last_rpc_context["status"] = -1105
                return {}
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                "Diamond",
                -cost,
                source=f"mystery_refresh:{'senior' if senior else 'normal'}",
            )
            ms["gold_count"] = int(ms.get("gold_count", 0)) + 1

        ms["senior" if senior else "normal"] = self._build_mystery_shop_items(1 if senior else 0)
        self._inc_stat("mystery_refresh", 1)
        self.save()
        return dict(ms_state, FreeCount=ms["free_count"], GoldCount=ms["gold_count"],
                    MysteryShopGoodsList=ms["senior" if senior else "normal"])

    def _rpc_mystery_shop_refresh(self, data: Any) -> dict[str, Any]:
        rtype = data[0] if isinstance(data, list) and len(data) == 1 and type(data[0]) is int else 0
        return self._do_mystery_shop_refresh(rtype, senior=False)

    def _rpc_mystery_shop_senior_refresh(self, data: Any) -> dict[str, Any]:
        rtype = data[0] if isinstance(data, list) and len(data) == 1 and type(data[0]) is int else 0
        return self._do_mystery_shop_refresh(rtype, senior=True)

    def _do_mystery_shop_buy(self, goods_id: str, senior: bool) -> dict[str, Any]:
        ms_state = self._mystery_shop_state(senior=senior)
        item = next((x for x in ms_state["MysteryShopGoodsList"] if str(x.get("Id")) == goods_id), None)
        if not item or int(item.get("IsSell", 0)) == 1:
            self._last_rpc_context["status"] = -1
            return {}
        bt = int(item["BuyResourceTypeSub"])
        bn = int(item["BuyNum"])
        attr_map = {1111: "Diamond", 1112: "Gold", 1116: "HeroCoin"}
        field = attr_map.get(bt, "HeroCoin")
        if int(self.state["player"].get(field, 0)) < bn:
            self._last_rpc_context["status"] = -1
            return {}
        if bn > 0:
            self.ledger.apply_player_delta(
                self.state["player"],
                self.profile_name,
                field,
                -bn,
                source=f"mystery_buy:{item['SellGoodsModelId']}",
                idempotency_key=f"mystery_cost:{self.profile_name}:{goods_id}",
            )
        item["IsSell"] = 1
        base_res = self._grant_resources_from_tuples(
            [(int(item["SellResourceTypeSub"]), int(item["SellGoodsModelId"]), int(item["SellNum"]))],
            source=f"mystery_buy:{item['SellGoodsModelId']}",
            tx_prefix=f"mystery_buy:{self.profile_name}:{goods_id}",
        )
        self._record_daily_task_progress(24, 1)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_mystery_shop_buy(self, data: Any) -> dict[str, Any]:
        gid = str(data[0]) if isinstance(data, list) and data else ""
        return self._do_mystery_shop_buy(gid, senior=False)

    def _rpc_mystery_shop_senior_buy(self, data: Any) -> dict[str, Any]:
        gid = str(data[0]) if isinstance(data, list) and data else ""
        return self._do_mystery_shop_buy(gid, senior=True)

    def _rpc_mystery_shop_reset_daily(self, data: Any = None) -> dict[str, Any]:
        """Reset daily Mystery Shop counters/free refreshes and reroll both normal and senior stock."""
        senior = bool(isinstance(data, list) and data and int(data[0]) == 1)
        vip_lv = int(self.state["player"].get("VIPLv", self.state["player"].get("Vip", 0)))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        free_max = max(1, int(vip_cfg.get("freeRefreshMysteryShopMaxNum", 2)))
        now = self.now_ts()
        today = self.clock.today_str(now)
        config = self.game_data["mystery_shop_config"]
        interval = int(config["freeRefreshCD"])
        midnight = self.clock.midnight_ts(now)
        normal_period = midnight + (now - midnight) // interval * interval
        normal_deadline = normal_period + interval
        senior_hours = [int(config[field] * 86400) for field in ("seniorRefreshTimeFirst", "seniorRefreshTimeSecond")]
        senior_deadline = next(
            (midnight + seconds for seconds in sorted(senior_hours) if midnight + seconds > now),
            midnight + 86400 + min(senior_hours),
        )
        ms = self.state.setdefault("mystery_shop", {})
        ms["free_count"] = free_max
        ms["gold_count"] = 0
        ms["free_date"] = today
        ms["free_period"] = normal_period
        ms["normal"] = self._build_mystery_shop_items(0)
        ms["senior"] = self._build_mystery_shop_items(1)
        ms["deadlines"] = {"normal": normal_deadline, "senior": senior_deadline}
        self.save()
        return self._mystery_shop_state(senior=senior)
