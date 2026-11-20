"""Mộ Thần Binh's VN catalogue and first two floors of offline encounters."""

from __future__ import annotations

import copy
import logging
import random
import uuid
from typing import Any, Callable

from combat_sim import CombatOutcome, simulate_fight_info
from economy_audit import ResourceLedger
from r79_event_handlers import _parse_res_tuples

PLAYABLE_FLOORS = (11, 12)


class BddHandlersMixin:
    def _bdd_reject(self, status: int) -> dict[str, Any]:
        self._last_rpc_context["status"] = status
        return {}

    def _bdd_is_open(self) -> bool:
        return int(self.state["player"]["Lv"]) >= int(self.game_data["module_subs"]["2507"]["openLv"])

    def _bdd_state(self) -> dict[str, Any]:
        return self.state.setdefault("bdd", {})

    def _bdd_nodes_for_floor(self, floor: int) -> list[dict[str, Any]]:
        return [row for row in self.game_data["bdd"]["nodes"].values() if row["floorModelID"] == floor]

    def _bdd_next_node(self) -> int | None:
        stars = self._bdd_state().get("stars", {})
        return next((row["ID"] for floor in PLAYABLE_FLOORS for row in self._bdd_nodes_for_floor(floor)
                     if not stars.get(str(row["ID"]))), None)

    def _bdd_floor_stars(self, floor: int) -> int:
        stars = self._bdd_state().get("stars", {})
        return sum(stars.get(str(row["ID"]), 0) for row in self._bdd_nodes_for_floor(floor))

    def _bdd_offer_buff(self, floor: int) -> list[dict[str, int]]:
        state = self._bdd_state()
        rng = random.Random(f"{self.state['player']['PlayerId']}:{state.get('run', 0)}:{floor}")
        buffs = self.game_data["bdd"]["buffs"].values()
        result = []
        for cost in (3, 6, 9):
            roll = rng.randint(1, 10000)
            row = next(row for row in buffs if row["needStars"] == cost and row["oddsMin"] <= roll <= row["oddsMax"])
            result.append({"Id": row["ID"], "NeedStars": cost})
        return result

    def _bdd_shop_info(self) -> list[dict[str, int]]:
        state = self._bdd_state()
        today = self.clock.today_str()
        return [
            {"ShopId": int(shop_id), "TodayBuyCount": row.get("days", {}).get(today, 0),
             "TotalBuyCount": row["total"]}
            for shop_id, row in state.get("shop", {}).items()
        ]

    def _bdd_payload(self) -> dict[str, Any]:
        state = self._bdd_state()
        next_node = self._bdd_next_node()
        floor = next_node // 100 if next_node is not None else max(PLAYABLE_FLOORS) + 1
        pending_reward = state.get("pending_reward")
        pending_buff = state.get("pending_buff")
        selection = state.get("buffs", {})
        stars = state.get("stars", {})
        totals = sum(stars.values())
        reset_count = state.get("daily_resets", {}).get(self.clock.today_str(), 0)
        catalogue = [
            {"Id": row["ID"], "Floor": row["floorModelID"], "StarCount": stars.get(str(row["ID"]), 0),
             "Locked": row["ID"] != next_node or bool(pending_reward or pending_buff),
             "Available": row["floorModelID"] in PLAYABLE_FLOORS}
            for row in self.game_data["bdd"]["nodes"].values()
        ]
        return {
            "Info": {
                "StarCount": totals, "MaxStarCount": state.get("max_stars", 0),
                "FAP": self._bdd_fap(self._bdd_allies()),
                "MaxThreeFloor": max(state.get("three_star_floors", []), default=0),
                "ResetCount": reset_count,
                "NeedReset": next_node is None and not pending_reward,
                "NeedDrawReward": bool(pending_reward), "NeedSelectBuff": bool(pending_buff),
                "BeforeFloorStarCount": self._bdd_floor_stars(pending_reward or pending_buff or floor - 1),
                "CanUseStarCount": totals - state.get("used_buff_stars", 0),
                "Feats": int(self.state["player"].get("Merit", 0)),
            },
            "NodeInfo": [{**item, "Passed": state.get("best", {}).get(str(item["Id"])) == 3}
                         for item in catalogue if item["Floor"] == floor],
            "BuffInfo": [{"FightattrId": int(attr), "AddValue": amount} for attr, amount in selection.items()],
            "BuyShopInfo": self._bdd_shop_info(),
            "Catalogue": catalogue,
            "Simulation": True,
            "PlayableCount": sum(item["Available"] for item in catalogue),
        }

    def _rpc_bdd_info(self, _data: Any) -> dict[str, Any]:
        return self._bdd_payload() if self._bdd_is_open() else self._bdd_reject(-1127)

    @staticmethod
    def _bdd_fap(heroes: list[dict[str, Any]]) -> int:
        return sum(hero["HP"] + 5 * (hero["AP"] + hero["DEF"]) for hero in heroes if hero)

    def _bdd_allies(self) -> list[dict[str, Any]]:
        allies = self._build_ally_fight_objs()
        buffs = self._bdd_state().get("buffs", {})
        for hero in allies:
            if not hero:
                continue
            for attr, field in (("401", "AP"), ("402", "HP")):
                hero[field] = hero[field] * (10000 + buffs.get(attr, 0)) // 10000
            hero["TotalHp"] = hero["HP"]
            for attr, field in (("301", "HIT"), ("302", "DOD"), ("303", "CRI"), ("305", "BLO"),
                                ("410", "DAMADDR"), ("411", "DAMCUTR")):
                hero[field] += buffs.get(attr, 0)
        return allies

    def _bdd_encounter(self, node: int, difficulty: int, token: str) -> dict[str, Any]:
        cfg = self.game_data["bdd"]
        floor = node // 100
        roster = self._bdd_nodes_for_floor(floor)
        # Approximation only. The selected VN boss leads the other two models from its floor.
        # Scale their VN base-stat proportions so the team matches the recommended FAP.
        roster.sort(key=lambda row: row["ID"] != node)
        foes = [self._hero_fight_obj(self.game_data["heroes"][str(row["pic"])], is_boss=index == 0)
                for index, row in enumerate(roster)]
        point = cfg["points"][str(node * 100 + 10 + difficulty)]
        target = int(point["proposeFAP"])
        current = self._bdd_fap(foes)
        for hero in foes:
            for key in ("HP", "AP", "DEF"):
                hero[key] = max(1, round(hero[key] * target / current))
            hero["TotalHp"] = hero["HP"]
        allies = self._bdd_allies()
        wave = {
            "Heros": allies + [foes[1], foes[0], foes[2], {}, {}, {}],
            "TeamData": [{"Fsp": sum(h.get("FSP", 0) for h in unit), "Fap": self._bdd_fap(unit)}
                         for unit in (allies, foes)],
            "Pets": [], "RandNum": 1 + int(token[:8], 16) % 2_000_000_000, "IsPVP": False,
        }
        return {"FightObjs": [wave]}

    @staticmethod
    def _bdd_cleared(rule: dict[str, Any], outcome: CombatOutcome) -> bool:
        kind, limit = rule["clearanceTypeID"], rule["clearanceCondition"]
        return outcome.won and (
            (kind == 2 and outcome.ally_hp_pct >= limit)
            or (kind == 3 and outcome.ally_alive >= limit)
            or (kind == 4 and outcome.total_rounds <= limit)
        )

    def _bdd_transaction(self, apply: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Commit the player and run state once, then emit audit entries."""
        before = copy.deepcopy(self.state)
        context = self._last_rpc_context.copy()
        ledger = self.ledger
        staged = ResourceLedger(vip_model=ledger.vip_model)
        self.ledger = staged
        try:
            result = apply()
            self.save()
        except Exception as exc:
            self.state.clear()
            self.state.update(before)
            self._last_rpc_context = context
            if not isinstance(exc, OSError):
                raise
            logging.exception("Could not save Mộ Thần Binh")
            return self._bdd_reject(-7)
        finally:
            self.ledger = ledger
        try:
            for entry in staged.list_transactions():
                ledger.record_grant_event(**{key: entry[key] for key in (
                    "account_id", "profile", "resource_type", "amount", "balance_after",
                    "source", "idempotency_key", "actor", "metadata",
                )})
        except OSError:
            logging.exception("Could not audit committed Mộ Thần Binh transaction")
        return result

    def _rpc_bdd_get_fight_info(self, data: Any) -> dict[str, Any]:
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        if not isinstance(data, list) or len(data) != 2 or any(type(v) is not int for v in data):
            return self._bdd_reject(-48)
        node, difficulty = data
        state = self._bdd_state()
        if node != self._bdd_next_node() or state.get("pending_reward") or state.get("pending_buff"):
            return self._bdd_reject(-1716)
        if difficulty not in (1, 2, 3) or not any(self._bdd_allies()):
            return self._bdd_reject(-1713)
        pending = state.get("pending_fight")
        if pending and (pending["node"], pending["difficulty"]) == (node, difficulty):
            return pending["payload"]
        token = uuid.uuid4().hex
        fight_info = self._bdd_encounter(node, difficulty, token)
        payload = {"FightInfo": fight_info, "FightToken": token, "Simulation": True}

        def prepare():
            state["pending_fight"] = {"node": node, "difficulty": difficulty, "payload": payload}
            return payload

        return self._bdd_transaction(prepare)

    def _bdd_record_win(self, node: int, difficulty: int) -> list[tuple[int, int, int]]:
        state = self._bdd_state()
        current = state.setdefault("stars", {})
        best = state.setdefault("best", {})
        old_best = best.get(str(node), 0)
        current[str(node)] = difficulty
        best[str(node)] = max(old_best, difficulty)
        state["max_stars"] = max(state.get("max_stars", 0), sum(current.values()))
        week = self.clock.week_str()
        weekly = state.setdefault("weekly_best", {})
        weekly[week] = max(weekly.get(week, 0), sum(current.values()))
        floor = node // 100
        rows = self._bdd_nodes_for_floor(floor)
        if all(str(row["ID"]) in current for row in rows):
            state["pending_reward"] = floor
            if all(current[str(row["ID"])] == 3 for row in rows):
                state["three_star_floors"] = sorted(set(state.get("three_star_floors", [])) | {floor})
        point = self.game_data["bdd"]["points"][str(node * 100 + 10 + difficulty)]
        drops = _parse_res_tuples(point["nationalDrop"])
        first = state.setdefault("first_rewards", [])
        fid = f"{node}:{difficulty}"
        if fid not in first:
            drops.extend(_parse_res_tuples(point["firstPassDrop"]))
            first.append(fid)
        self._record_daily_task_progress(21)
        self._inc_stat("bdd_Win")
        return drops

    def _rpc_bdd_fight(self, data: Any) -> dict[str, Any]:
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        if not isinstance(data, list) or len(data) != 6:
            return self._bdd_reject(-48)
        node, difficulty = data[:2]
        state = self._bdd_state()
        pending = state.get("pending_fight")
        if not pending or (pending["node"], pending["difficulty"], pending["payload"]["FightToken"]) != (node, difficulty, data[5]):
            return self._bdd_reject(-39)
        rule_id = self.game_data["bdd"]["nodes"][str(node)]["clearanceID"]
        rule = self.game_data["bdd"]["clearance"][str(rule_id)]
        outcome = simulate_fight_info(pending["payload"]["FightInfo"], self.game_data["attacks"])
        won = self._bdd_cleared(rule, outcome)

        def settle():
            state.pop("pending_fight")
            rewards = self._bdd_record_win(node, difficulty) if won else []
            output = self._grant_resources_from_tuples(rewards, "bdd_fight", f"bdd:{data[5]}") if rewards else []
            return {
                "IsSuccess": won, "StarCount": difficulty if won else 0,
                "BaseGetGameResourceList": output, "Simulation": True,
                "Turns": outcome.total_rounds, "AlliesAlive": outcome.ally_alive, "RemainingHPPercent": outcome.ally_hp_pct,
            }

        return self._bdd_transaction(settle)

    def _bdd_box(self, floor: int, stars: int) -> list[tuple[int, int, int]]:
        row = next(item for item in self.game_data["bdd"]["rewards"]
                   if item["floorModelID"] == floor and item["stars"] == stars)
        return _parse_res_tuples(row["reward"])

    def _rpc_bdd_reward_box(self, data: Any) -> dict[str, Any]:
        state = self._bdd_state()
        floor = state.get("pending_reward")
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        if floor is None or data != [floor, self._bdd_floor_stars(floor) // 3 * 3]:
            return self._bdd_reject(-39)

        def reward():
            state.pop("pending_reward")
            if self._bdd_next_node() is not None:
                state["pending_buff"] = floor
            return {"BaseGetGameResourceList": self._grant_resources_from_tuples(
                self._bdd_box(*data), "bdd_floor_box", f"bdd_box:{state.get('run', 0)}:{floor}",
            )}

        return self._bdd_transaction(reward)

    def _rpc_bdd_get_buffs(self, _data: Any) -> Any:
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        floor = self._bdd_state().get("pending_buff")
        if not floor:
            return self._bdd_reject(-39)
        return self._bdd_offer_buff(floor)

    def _rpc_bdd_select_buff(self, data: Any) -> dict[str, Any]:
        state = self._bdd_state()
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        floor = state.get("pending_buff")
        if not floor or not isinstance(data, list) or len(data) != 1:
            return self._bdd_reject(-39)
        offer = next((row for row in self._bdd_offer_buff(floor) if row["Id"] == data[0]), None)
        if not offer:
            return self._bdd_reject(-48)
        cost = offer["NeedStars"]
        used = state.get("used_buff_stars", 0)
        if sum(state["stars"].values()) - used < cost:
            return self._bdd_reject(-1732)

        def select():
            row = self.game_data["bdd"]["buffs"][str(offer["Id"])]
            buffs = state.setdefault("buffs", {})
            attr = str(row["fightattrID"])
            buffs[attr] = buffs.get(attr, 0) + row["addValue"]
            state["used_buff_stars"] = used + cost
            state.pop("pending_buff")
            return self._bdd_payload()

        return self._bdd_transaction(select)

    def _rpc_bdd_reset(self, _data: Any) -> dict[str, Any]:
        state = self._bdd_state()
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        if self._bdd_next_node() is not None or state.get("pending_reward"):
            return self._bdd_reject(-1716)
        today = self.clock.today_str()
        count = state.get("daily_resets", {}).get(today, 0)
        vip = self.game_data["vip_model"].get(str(self.state["player"].get("VIPLv", 0)), {})
        recipe = self.game_data["bdd"]["reset"].get(str(count + 1))
        if count >= vip.get("resetBDDNum", 0) or not recipe:
            return self._bdd_reject(-1736)
        cost = recipe["useDiamond"]
        player = self.state["player"]
        if int(player["Diamond"]) < cost:
            return self._bdd_reject(-1105)

        def reset():
            if cost:
                self.ledger.apply_player_delta(player, self.profile_name, "Diamond", -cost, source="bdd_reset")
                self._last_rpc_context["diamond_spent"] = cost
            for key in ("stars", "buffs", "used_buff_stars", "pending_fight", "pending_reward", "pending_buff"):
                state.pop(key, None)
            state["run"] = state.get("run", 0) + 1
            state["daily_resets"] = {today: count + 1}
            return self._bdd_payload()

        return self._bdd_transaction(reset)

    def _rpc_bdd_ranking(self, _data: Any) -> Any:
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        week = self.clock.week_str()
        rows = []
        for peer in self._s1_account_profiles():
            player = peer.state["player"]
            score = peer.state.get("bdd", {}).get("weekly_best", {}).get(week, 0)
            if score:
                rows.append({"PlayerId": player["PlayerId"], "HeadImageId": player["HeadImageId"], "Name": player["PlayerName"],
                             "FAP": player["FAP"], "Lv": player["Lv"], "WeekStarCount": score})
        return sorted(rows, key=lambda row: (-row["WeekStarCount"], -row["FAP"], row["PlayerId"]))

    def _rpc_bdd_buy_shop(self, data: Any) -> dict[str, Any]:
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        if not isinstance(data, list) or len(data) != 1:
            return self._bdd_reject(-48)
        row = self.game_data["bdd"]["merit_shop"].get(str(data[0]))
        if not row:
            return self._bdd_reject(-42)
        state = self._bdd_state()
        player = self.state["player"]
        shop_id = str(row["ID"])
        purchase = state.get("shop", {}).get(shop_id, {"total": 0, "days": {}})
        day = self.clock.today_str()
        today_count = purchase["days"].get(day, 0)
        if int(player.get("Merit", 0)) < row["needNum"]:
            return self._bdd_reject(-1602)
        if state.get("max_stars", 0) < row["needStarNum"]:
            return self._bdd_reject(-1732)
        if (row["perMaxNum"] and today_count >= row["perMaxNum"]) or (row["totalMaxNum"] and purchase["total"] >= row["totalMaxNum"]):
            return self._bdd_reject(-2104)
        resources = _parse_res_tuples(row["outResource"])
        if not resources or not all(self._is_valid_resource(kind, model) for kind, model, _ in resources):
            return self._bdd_reject(-1605)
        if not self._check_hero_capacity(sum(num for kind, _, num in resources if kind == 1201)):
            return {}

        def buy():
            self.ledger.apply_player_delta(player, self.profile_name, "Merit", -row["needNum"], source="bdd_shop")
            state.setdefault("shop", {})[shop_id] = {"total": purchase["total"] + 1, "days": {day: today_count + 1}}
            return {"BaseGetGameResourceList": self._grant_resources_from_tuples(
                resources, "bdd_shop", f"bdd_shop:{shop_id}:{purchase['total'] + 1}",
            ), "BuyShopInfo": self._bdd_shop_info(), "Feats": player["Merit"]}

        return self._bdd_transaction(buy)

    def _rpc_bdd_sweep(self, _data: Any) -> dict[str, Any]:
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        player = self.state["player"]
        rule = self.game_data["module_subs"]["2508"]
        if not (player["Lv"] >= rule["openLv"]
                or (player["Lv"] >= rule["VIPNeedLv"] and player.get("VIPLv", 0) >= rule["advancedOpenVIPLv"])):
            return self._bdd_reject(-1127)
        state = self._bdd_state()
        node = self._bdd_next_node()
        if node is None or state.get("pending_reward") or state.get("pending_buff") or state.get("pending_fight"):
            return self._bdd_reject(-1716)
        floor = node // 100
        if floor not in state.get("three_star_floors", []):
            return self._bdd_reject(-1717)

        def sweep():
            rewards = []
            for row in self._bdd_nodes_for_floor(floor):
                if not state.get("stars", {}).get(str(row["ID"])):
                    rewards.extend(self._bdd_record_win(row["ID"], 3))
            state.pop("pending_reward")
            if self._bdd_next_node() is not None:
                state["pending_buff"] = floor
            prefix = f"bdd_sweep:{state.get('run', 0)}:{floor}"
            base = self._grant_resources_from_tuples(rewards, "bdd_sweep", prefix)
            box = self._grant_resources_from_tuples(self._bdd_box(floor, self._bdd_floor_stars(floor) // 3 * 3),
                                                   "bdd_floor_box", prefix + ":box")
            return dict(self._bdd_payload(), BaseGetGameResourceList=base, BoxGetGameResourceList=box)

        return self._bdd_transaction(sweep)

    def _rpc_bdd_equip_shop_info(self, _data: Any) -> dict[str, Any]:
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        return {"EquipShopInfo": [{"Id": int(shop_id), "Num": count}
                                  for shop_id, count in self._bdd_state().get("equip_shop", {}).items()]}

    def _rpc_bdd_equip_shop_exchange(self, data: Any) -> dict[str, Any]:
        if not self._bdd_is_open():
            return self._bdd_reject(-1127)
        if not isinstance(data, list) or len(data) != 2 or not isinstance(data[1], list):
            return self._bdd_reject(-48)
        row = self.game_data["bdd"]["equip_shop"].get(str(data[0]))
        if not row:
            return self._bdd_reject(-42)
        state = self._bdd_state()
        player = self.state["player"]
        shop_id = str(row["ID"])
        used = state.get("equip_shop", {}).get(shop_id, 0)
        if used >= row["totalMaxNum"]:
            return self._bdd_reject(-2104)
        if int(player.get("Merit", 0)) < row["needNum"]:
            return self._bdd_reject(-1602)
        (_, model, count), = _parse_res_tuples(row["useEquip"])
        ids = data[1]
        if len(ids) != count or not all(isinstance(item, str) for item in ids) or len(set(ids)) != count:
            return self._bdd_reject(-1317)
        equips = {item["Id"]: item for item in self.state["equips"]}
        equipped = {slot.get(key, {}).get("Id") for slot in self.state["slots"]
                    for key in self.EQUIP_TYPE_TO_SLOT_KEY.values()}
        if set(ids) & equipped:
            return self._bdd_reject(-1304)
        if any(item not in equips or equips[item]["EquipModelId"] != model or equips[item].get("Step", 0) != row["equipStepNum"]
               for item in ids):
            return self._bdd_reject(-1317)
        resources = _parse_res_tuples(row["outResource"])
        if not resources or not all(self._is_valid_resource(kind, reward) for kind, reward, _ in resources):
            return self._bdd_reject(-1605)

        def exchange():
            self.ledger.apply_player_delta(player, self.profile_name, "Merit", -row["needNum"], source="bdd_equip_shop")
            self.state["equips"] = [item for item in self.state["equips"] if item["Id"] not in ids]
            state.setdefault("equip_shop", {})[shop_id] = used + 1
            output = self._grant_resources_from_tuples(resources, "bdd_equip_shop", f"bdd_equip_shop:{shop_id}:{used + 1}")
            return dict(self._rpc_bdd_equip_shop_info([]), Feats=player["Merit"], BaseGetGameResourceList=output)

        return self._bdd_transaction(exchange)
