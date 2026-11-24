"""Chiến Liên Server (`PVPinter` ModuleSub 6100 + `WhosTheGod` / `PVPinterTop` ModuleSub 6200) handlers."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from combat_sim import simulate_fight_info
from nightmare_handlers import scale_wave_to_target_fap
from r79_event_handlers import _parse_res_tuples

_CROSS_SERVERS: tuple[str, ...] = (
    "S2 - Tây Quốc",
    "S3 - Bạch Linh Sơn",
    "S4 - Minh Đạo",
    "S5 - Tứ Hồn",
)

_TIER_FAP_FACTORS: dict[int, float] = {
    1: 0.72,
    2: 0.78,
    3: 0.84,
    4: 0.90,
    5: 0.94,
    6: 0.98,
    7: 1.00,
    8: 1.02,
}


def _pack_bo3_is_win(rounds: tuple[int, int, int]) -> int:
    """Encode 3-round Bo3 result matching CSBSecondScene.lua `convertToByte`/`isWin` (`bit._d2b`)."""
    mask = 0
    for idx, res in enumerate(rounds):
        if int(res) > 0:
            mask |= 1 << (16 + idx)
    return mask | 0b111


class PVPinterHandlersMixin:
    """Offline emulator handlers for Chiến Liên Server (`PVPinter`, `PVPinterShopinfo`, `PVPinterTop`, `PvpinterTopWorshipInfo`)."""

    def _pvpinter_open_lv(self) -> int:
        return int(self.game_data.get("module_subs", {}).get("6100", {}).get("openLv", 42))

    def _ensure_pvpinter_state(self) -> dict[str, Any]:
        cfg = self.game_data.get("pvpinter_config", {})
        daily_times = int(cfg.get("dailyTimes", 10))
        st = self.state.setdefault("pvpinter", {})
        lv = max(1, min(8, int(st.get("lv", 1))))
        st["lv"] = lv
        st["history_max_lv"] = max(lv, min(8, int(st.get("history_max_lv", lv))))
        st["rate"] = max(0, int(st.get("rate", 0)))
        st.setdefault("fight_count", daily_times)
        st.setdefault("buy_count", 0)
        st.setdefault("win_count", 0)
        st.setdefault("total_fights", 0)
        st.setdefault("daily_wins", 0)
        st.setdefault("win_boxes_claimed", [])
        st.setdefault("uping", None)
        st.setdefault("fight_logs", [])
        st.setdefault("shop_bought", {})
        st.setdefault("top_bets", [])
        st.setdefault("worship_days_total", 0)
        st.setdefault("worship_groups_today", [])

        today = self.clock.today_str()
        if st.get("day") != today:
            st["day"] = today
            st["fight_count"] = daily_times
            st["buy_count"] = 0
            st["daily_wins"] = 0
            st["win_boxes_claimed"] = []
            st["worship_groups_today"] = []

        uping = st.get("uping")
        if isinstance(uping, dict) and self.now_ts() > int(uping.get("deadline", 0)):
            st["uping"] = None
        return st

    def _pvpinter_season_window(self) -> tuple[int, int]:
        cfg = self.game_data.get("pvpinter_config", {})
        season_days = max(1, int(cfg.get("season", 28)))
        sec_per_season = season_days * 86400
        now = self.now_ts()
        begin_ts = now - (now % sec_per_season)
        end_ts = begin_ts + sec_per_season
        if end_ts <= now:
            end_ts = now + sec_per_season
        return begin_ts, end_ts

    def _pvpinter_info_payload(self, st: dict[str, Any]) -> dict[str, Any]:
        return {
            "Lv": int(st["lv"]),
            "HistoryMaxLv": int(st["history_max_lv"]),
            "Rate": int(st["rate"]),
            "FightCount": int(st["fight_count"]),
            "BuyCount": int(st["buy_count"]),
            "WinCount": int(st["win_count"]),
            "TotalFights": int(st["total_fights"]),
            "DailyWins": int(st["daily_wins"]),
        }

    @staticmethod
    def _pvpinter_public_uping(uping: dict[str, Any] | None) -> list[dict[str, Any]] | None:
        if not isinstance(uping, dict) or not uping.get("targets"):
            return None
        return [
            {
                "TargetId": str(t["TargetId"]),
                "Name": str(t["Name"]),
                "Lv": int(t["Lv"]),
                "PVPInterLv": int(t["PVPInterLv"]),
                "HeadImageId": int(t["HeadImageId"]),
                "FashionModelId": int(t.get("FashionModelId", 0)),
                "FAP": int(t["FAP"]),
                "Zone": str(t["Zone"]),
                "Status": int(t.get("Status", 0)),
            }
            for t in uping["targets"]
        ]

    def _pvpinter_tier_need_bounds(self, lv: int) -> tuple[int, int, int]:
        lv_tbl = self.game_data.get("pvpinter_lv", {})
        row = lv_tbl.get(str(lv), lv_tbl.get("1", {}))
        prev_row = lv_tbl.get(str(lv - 1), {}) if lv > 1 else {}
        prev_need = int(prev_row.get("needRating", 0)) if lv > 1 else 0
        need_rating = int(row.get("needRating", 100))
        rating_k = int(row.get("ratingK", 40))
        return prev_need, need_rating, rating_k

    def _pvpinter_make_opponent(
        self, tier: int, seed_idx: int, *, fap_scale: float | None = None
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        player = self.state["player"]
        player_lv = max(42, int(player.get("Lv", 42)))
        player_fap = max(80_000, int(player.get("FAP", 100_000)))
        if tier <= 2:
            step = 2
            bot_rank = 950 + (seed_idx * 47) % 450
        elif tier <= 4:
            step = 3
            bot_rank = 500 + (seed_idx * 37) % 400
        elif tier <= 6:
            step = 4
            bot_rank = 180 + (seed_idx * 29) % 250
        else:
            step = 5
            bot_rank = max(1, 15 + (seed_idx * 17) % 140)
        bot = self._arena_bot_profile(bot_rank, step)
        factor = fap_scale if fap_scale is not None else _TIER_FAP_FACTORS.get(tier, 0.85)
        target_fap = max(45_000, int(player_fap * factor))
        enemies = self._arena_bot_fight_objs(bot)
        scale_wave_to_target_fap(enemies, target_fap)
        zone = _CROSS_SERVERS[(tier + seed_idx) % len(_CROSS_SERVERS)]
        head_id = self._valid_hero_head_id(0, bot["Slots"])
        opp = {
            "TargetId": f"cs-match:{tier}:{seed_idx}:{bot_rank}",
            "Name": str(bot["Name"]),
            "Lv": max(40, min(80, player_lv - 2 + (seed_idx % 5))),
            "PVPInterLv": max(1, min(8, tier)),
            "HeadImageId": int(head_id),
            "FashionModelId": int(bot.get("FashionModelId", 0)),
            "FAP": int(target_fap),
            "Zone": zone,
            "Status": 0,
            "_bot_step": step,
            "_bot_rank": bot_rank,
        }
        return opp, enemies

    def _pvpinter_enemies_from_target(self, target: dict[str, Any]) -> list[dict[str, Any]]:
        step = int(target.get("_bot_step", 4))
        bot_rank = int(target.get("_bot_rank", 100))
        target_fap = max(45_000, int(target.get("FAP", 100_000)))
        bot = self._arena_bot_profile(bot_rank, step)
        enemies = self._arena_bot_fight_objs(bot)
        scale_wave_to_target_fap(enemies, target_fap)
        return enemies

    def _pvpinter_run_pvp_battle(self, target_fap: int, enemies: list[dict[str, Any]]) -> tuple[dict[str, Any], bool]:
        player = self.state["player"]
        allies = self._build_ally_fight_objs()
        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        enemy_fsp = sum(int(u.get("FSP", 0)) for u in enemies if u)
        fight_info = {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": ally_fsp, "Fap": int(player.get("FAP", 0))},
                        {"Fsp": enemy_fsp, "Fap": int(target_fap)},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1, 999999),
                    "IsPVP": True,
                }
            ]
        }
        outcome = simulate_fight_info(
            fight_info,
            self.game_data["attacks"],
            buffs_cfg=self.game_data["combat_buffs"],
        )
        return fight_info, bool(outcome.won)

    def _pvpinter_collect_match_rewards(
        self, st: dict[str, Any], lv_for_reward: int, won: bool, *, first_promo_lv: int = 0
    ) -> list[dict[str, Any]]:
        lv_tbl = self.game_data.get("pvpinter_lv", {})
        row = lv_tbl.get(str(lv_for_reward), lv_tbl.get("1", {}))
        rew_str = str(row.get("victoryRewards" if won else "failedRewards", "1605,16050062,20" if won else "1605,16050062,10"))
        tuples = _parse_res_tuples(rew_str)

        if first_promo_lv > 1:
            promo_row = lv_tbl.get(str(first_promo_lv), {})
            promo_str = str(promo_row.get("lvUpRewardsFirst", "") or "")
            if promo_str:
                tuples.extend(_parse_res_tuples(promo_str))

        if won:
            box_tbl = self.game_data.get("pvpinter_win_box", {}).get(str(st["lv"]), {})
            claimed = st.setdefault("win_boxes_claimed", [])
            for win_req_s, brow in sorted(box_tbl.items(), key=lambda kv: int(kv[0])):
                win_req = int(win_req_s)
                if int(st["daily_wins"]) >= win_req and win_req not in claimed:
                    claimed.append(win_req)
                    tuples.extend(_parse_res_tuples(str(brow.get("reward", ""))))

        if not tuples:
            return []
        return self._grant_resources_from_tuples(
            tuples,
            source=f"pvpinter:{lv_for_reward}:{'win' if won else 'lose'}",
            tx_prefix=f"pvpinter:{self.profile_name}:{self.now_ts()}:{random.randint(100, 9999)}",
        )

    def _pvpinter_build_uping_targets(self, tier: int, seed_base: int) -> dict[str, Any]:
        targets = [
            self._pvpinter_make_opponent(
                tier,
                seed_base + i,
                fap_scale=max(0.65, _TIER_FAP_FACTORS.get(tier, 0.85) - 0.04 + 0.03 * i),
            )[0]
            for i in range(3)
        ]
        return {
            "target_lv": min(8, tier + 1),
            "deadline": self.now_ts() + 86400,
            "targets": targets,
        }

    def _pvpinter_append_log(
        self,
        st: dict[str, Any],
        target: dict[str, Any],
        won: bool,
        before_rate: int,
        before_lv: int,
        *,
        is_up: bool,
    ) -> dict[str, Any]:
        entry = {
            "Crdate": self.now_ts(),
            "IfWin": bool(won),
            "BeforeRate": int(before_rate),
            "BeforeLv": int(before_lv),
            "AfterRate": int(st["rate"]),
            "AfterLv": int(st["lv"]),
            "IsUp": bool(is_up),
            "IsTimeDown": False,
            "TimeDownDays": 0,
            "TargetHeadImageId": int(target["HeadImageId"]),
            "TargetFAP": int(target["FAP"]),
            "TargetName": str(target["Name"]),
        }
        logs = st.setdefault("fight_logs", [])
        logs.insert(0, entry)
        del logs[10:]
        return entry

    # -------------------- PVPinter (6100) RPCs --------------------

    def _rpc_pvpinter_get_info(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < self._pvpinter_open_lv():
            self._last_rpc_context["status"] = -1
            return {}
        st = self._ensure_pvpinter_state()
        self.state["player"]["PVPInterLv"] = int(st["lv"])
        begin_ts, end_ts = self._pvpinter_season_window()
        pid = str(self.state["player"].get("PlayerId", ""))
        top_entries = self._build_cross_server_rank_entries()
        my_rank = next((int(e["Rank"]) for e in top_entries if str(e.get("Id")) == pid), None)
        uping = st.get("uping")
        self.save()
        return {
            "IsOpen": True,
            "OpenDay": 0,
            "Rank": my_rank,
            "PVPinterInfo": self._pvpinter_info_payload(st),
            "PVPinterSeasonInfo": {"BeginDate": begin_ts, "EndDate": end_ts},
            "PVPinterUpingInfo": self._pvpinter_public_uping(uping),
            "PVPinterUpDefaultTime": int(uping.get("deadline", 0)) if isinstance(uping, dict) else 0,
        }

    def _rpc_pvpinter_get_fight_log(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < self._pvpinter_open_lv():
            self._last_rpc_context["status"] = -1
            return {}
        st = self._ensure_pvpinter_state()
        return {"PVPinterFightLog": list(st.get("fight_logs", [])[:10])}

    def _rpc_pvpinter_fight_match(self, _data: Any) -> dict[str, Any]:
        player = self.state["player"]
        if int(player.get("Lv", 1)) < self._pvpinter_open_lv():
            self._last_rpc_context["status"] = -1
            return {}
        st = self._ensure_pvpinter_state()
        if st.get("uping") or int(st["fight_count"]) < 1:
            self._last_rpc_context["status"] = -1
            return {}
        cfg = self.game_data.get("pvpinter_config", {})
        sta_cost = int(cfg.get("fightSTA", 2))
        if int(player.get("STA", 0)) < sta_cost:
            self._last_rpc_context["status"] = -1120
            return {}

        before_lv = int(st["lv"])
        before_rate = int(st["rate"])
        max_uping_lv = int(cfg.get("maxLv", 6))
        seed = int(st["total_fights"]) + 1
        target, enemies = self._pvpinter_make_opponent(before_lv, seed)

        self.ledger.apply_player_delta(
            player, self.profile_name, "STA", -sta_cost, source=f"pvpinter_match:{before_lv}"
        )
        st["fight_count"] = int(st["fight_count"]) - 1

        fight_info, won = self._pvpinter_run_pvp_battle(int(target["FAP"]), enemies)
        st["total_fights"] = int(st["total_fights"]) + 1
        if won:
            st["win_count"] = int(st["win_count"]) + 1
            st["daily_wins"] = int(st["daily_wins"]) + 1

        prev_need, need_rating, rating_k = self._pvpinter_tier_need_bounds(before_lv)
        first_promo_lv = 0
        if won:
            new_rate = before_rate + rating_k
            if before_lv < max_uping_lv and new_rate >= need_rating:
                st["rate"] = need_rating
                st["uping"] = self._pvpinter_build_uping_targets(before_lv, seed * 7)
            else:
                st["rate"] = new_rate
                if before_lv == 6 and new_rate >= 700:
                    st["lv"] = 7
                elif before_lv == 7 and new_rate >= 900:
                    st["lv"] = 8
                if st["lv"] > int(st["history_max_lv"]):
                    st["history_max_lv"] = st["lv"]
                    first_promo_lv = st["lv"]
        else:
            delta = max(10, rating_k // 2)
            new_rate = max(0, before_rate - delta)
            if 1 < before_lv <= max_uping_lv and new_rate < prev_need:
                st["lv"] = before_lv - 1
                st["rate"] = max(0, prev_need - 20)
            else:
                floor = prev_need if before_lv > 1 else 0
                st["rate"] = max(floor, new_rate)

        player["PVPInterLv"] = int(st["lv"])
        base_res = self._pvpinter_collect_match_rewards(st, before_lv, won, first_promo_lv=first_promo_lv)
        log_entry = self._pvpinter_append_log(st, target, won, before_rate, before_lv, is_up=False)
        self.save()

        return {
            "IsWinFight": 1 if won else 0,
            "FightInfo": fight_info,
            "TargetInfo": {k: v for k, v in target.items() if not str(k).startswith("_")},
            "PVPinterInfo": self._pvpinter_info_payload(st),
            "PVPinterUpingInfo": self._pvpinter_public_uping(st.get("uping")),
            "PVPinterFightLog": log_entry,
            "BaseGetGameResourceList": base_res,
        }

    def _rpc_pvpinter_fight_uping(self, data: Any) -> dict[str, Any]:
        player = self.state["player"]
        if int(player.get("Lv", 1)) < self._pvpinter_open_lv():
            self._last_rpc_context["status"] = -1
            return {}
        st = self._ensure_pvpinter_state()
        uping = st.get("uping")
        if not isinstance(uping, dict) or not uping.get("targets"):
            self._last_rpc_context["status"] = -1
            return {}
        target_id = str(data[0]) if isinstance(data, list) and data and data[0] is not None else ""
        target = next(
            (t for t in uping["targets"] if str(t.get("TargetId")) == target_id and int(t.get("Status", 0)) == 0),
            None,
        )
        if not target:
            self._last_rpc_context["status"] = -1
            return {}
        cfg = self.game_data.get("pvpinter_config", {})
        sta_cost = int(cfg.get("fightSTA", 2))
        if int(player.get("STA", 0)) < sta_cost:
            self._last_rpc_context["status"] = -1120
            return {}

        before_lv = int(st["lv"])
        before_rate = int(st["rate"])
        enemies = self._pvpinter_enemies_from_target(target)
        self.ledger.apply_player_delta(
            player, self.profile_name, "STA", -sta_cost, source=f"pvpinter_uping:{before_lv}"
        )

        fight_info, won = self._pvpinter_run_pvp_battle(int(target["FAP"]), enemies)
        st["total_fights"] = int(st["total_fights"]) + 1
        if won:
            st["win_count"] = int(st["win_count"]) + 1
            st["daily_wins"] = int(st["daily_wins"]) + 1
        target["Status"] = 2 if won else 1

        wins = sum(1 for t in uping["targets"] if int(t.get("Status", 0)) == 2)
        losses = sum(1 for t in uping["targets"] if int(t.get("Status", 0)) == 1)
        is_sucess = 0
        first_promo_lv = 0
        if wins >= 2:
            is_sucess = 2
            st["lv"] = min(8, int(uping.get("target_lv", before_lv + 1)))
            st["uping"] = None
            if st["lv"] > int(st["history_max_lv"]):
                st["history_max_lv"] = st["lv"]
                first_promo_lv = st["lv"]
        elif losses >= 2:
            is_sucess = 1
            st["rate"] = max(0, before_rate - 20)
            st["uping"] = None

        player["PVPInterLv"] = int(st["lv"])
        base_res = self._pvpinter_collect_match_rewards(st, before_lv, won, first_promo_lv=first_promo_lv)
        log_entry = self._pvpinter_append_log(st, target, won, before_rate, before_lv, is_up=True)
        self.save()

        return {
            "IsWinFight": 1 if won else 0,
            "IsSucess": is_sucess,
            "FightInfo": fight_info,
            "PVPinterInfo": self._pvpinter_info_payload(st),
            "PVPinterUpingInfo": self._pvpinter_public_uping(st.get("uping")),
            "PVPinterFightLog": log_entry,
            "BaseGetGameResourceList": base_res,
        }

    def _rpc_pvpinter_buy_fight_count(self, data: Any) -> dict[str, Any]:
        player = self.state["player"]
        if int(player.get("Lv", 1)) < self._pvpinter_open_lv():
            self._last_rpc_context["status"] = -1
            return {}
        count = int(data[0]) if isinstance(data, list) and data and data[0] is not None else 1
        if count < 1:
            self._last_rpc_context["status"] = -1
            return {}
        st = self._ensure_pvpinter_state()
        vip_lv = str(int(player.get("Vip", 0)))
        vip_limit = int(self.game_data.get("vip_model", {}).get(vip_lv, {}).get("buyKuafuNum", 0))
        cur_bought = int(st["buy_count"])
        if cur_bought + count > vip_limit:
            self._last_rpc_context["status"] = -1
            return {}

        buy_tbl = self.game_data.get("pvpinter_buynum", {})
        max_key = max((int(k) for k in buy_tbl if str(k).isdigit()), default=11)
        total_price = sum(
            int(buy_tbl.get(str(min(max_key, cur_bought + i)), {}).get("price", 50))
            for i in range(1, count + 1)
        )
        if int(player.get("Diamond", 0)) < total_price:
            self._last_rpc_context["status"] = -1105
            return {}
        if total_price > 0:
            self.ledger.apply_player_delta(
                player, self.profile_name, "Diamond", -total_price, source=f"pvpinter_buy:{count}"
            )
        st["buy_count"] = cur_bought + count
        st["fight_count"] = int(st["fight_count"]) + count
        self.save()
        return {"PVPinterInfo": self._pvpinter_info_payload(st)}

    # -------------------- PVPinterShopinfo RPCs --------------------

    def _rpc_pvpinter_shop_info(self, _data: Any) -> dict[str, Any]:
        st = self._ensure_pvpinter_state()
        bought = st.get("shop_bought", {})
        return {
            "BuyShopInfo": [
                {"ShopId": int(k), "TotalBuyCount": int(v)}
                for k, v in sorted(bought.items(), key=lambda kv: int(kv[0]))
            ]
        }

    def _rpc_pvpinter_shop_buy(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            shop_id = int(data[0])
            count = int(data[1]) if len(data) >= 2 and data[1] is not None else 1
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        if count < 1:
            self._last_rpc_context["status"] = -1
            return {}

        row = self.game_data.get("pvpinter_shop", {}).get(str(shop_id))
        if not row:
            self._last_rpc_context["status"] = -1
            return {}
        st = self._ensure_pvpinter_state()
        cur_lv = int(st["lv"])
        if cur_lv < int(row.get("needPVPInteLv", 1)):
            self._last_rpc_context["status"] = -1
            return {}
        max_total = int(row.get("maxTotalNum", 0))
        bought_map = st.setdefault("shop_bought", {})
        prev_bought = int(bought_map.get(str(shop_id), 0))
        if max_total > 0 and prev_bought + count > max_total:
            self._last_rpc_context["status"] = -1
            return {}

        uses = _parse_res_tuples(str(row.get("useResource", "1605,16050062,125")))
        if not uses:
            self._last_rpc_context["status"] = -1
            return {}
        _utype, medal_mid, raw_cost = uses[0]
        sale_str = str(self.game_data.get("pvpinter_lv", {}).get(str(cur_lv), {}).get("sale", "1"))
        sale_mult = float(sale_str) if int(row.get("isSale", 0)) == 1 else 1.0
        unit_cost = max(1, int(raw_cost * sale_mult))
        total_cost = unit_cost * count

        if not self._consume_goods_multi(medal_mid, total_cost):
            self._last_rpc_context["status"] = -1
            return {}

        outs = _parse_res_tuples(str(row.get("outResource", "")))
        scaled_outs = [(rt, rm, rn * count) for rt, rm, rn in outs if rn > 0]
        bought_map[str(shop_id)] = prev_bought + count
        base_res = self._grant_resources_from_tuples(
            scaled_outs,
            source=f"pvpinter_shop:{shop_id}x{count}",
            tx_prefix=f"pvpinter_shop:{self.profile_name}:{shop_id}:{self.now_ts()}:{random.randint(100, 9999)}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # -------------------- PVPinterTop (6200 WhosTheGod) Tournament & Worship --------------------

    def _pvpinter_top_roster(self, group_id: int) -> list[dict[str, Any]]:
        """Build 32 seeded contenders for group 1..4 (player placed at seed 0 in group 1)."""
        all_rank = self._build_cross_server_rank_entries()
        non_self = [r for r in all_rank if str(r.get("Id")) != str(self.state["player"].get("PlayerId", ""))]
        roster: list[dict[str, Any]] = []
        p = self.state["player"]
        if group_id == 1:
            roster.append(
                {
                    "Id": str(p.get("PlayerId", "200001")),
                    "Name": str(p.get("PlayerName", "Adventurer") or "Adventurer"),
                    "HeadImageId": self._valid_hero_head_id(int(p.get("HeadImageId", 0)), self.state.get("slots", [])),
                    "ServerId": 1,
                    "Zone": "S1 - Chiến Quốc",
                    "GuildName": str(p.get("GuildName", "") or ""),
                    "FashionModelId": int(p.get("FashionModelId", 0)),
                    "FAP": int(p.get("FAP", 100000)),
                    "_src": "self",
                }
            )
        offset = (group_id - 1) * 7
        idx = 0
        while len(roster) < 32:
            if non_self:
                entry = non_self[(offset + idx) % len(non_self)]
                roster.append(
                    {
                        "Id": str(entry["Id"]),
                        "Name": str(entry["Name"]),
                        "HeadImageId": int(entry["HeadImageId"]),
                        "ServerId": 1,
                        "Zone": str(entry.get("Zone", _CROSS_SERVERS[idx % len(_CROSS_SERVERS)])),
                        "GuildName": str(entry.get("GuildName", "")),
                        "FashionModelId": int(entry.get("FashionModelId", 0)),
                        "FAP": int(entry["FAP"]),
                        "_src": str(entry["Id"]),
                    }
                )
            else:
                bot = self._arena_bot_profile(10 + idx * 5, 5)
                roster.append(
                    {
                        "Id": f"cs-top:{group_id}:{idx}",
                        "Name": str(bot["Name"]),
                        "HeadImageId": self._valid_hero_head_id(0, bot["Slots"]),
                        "ServerId": 1,
                        "Zone": _CROSS_SERVERS[idx % len(_CROSS_SERVERS)],
                        "GuildName": str(bot.get("Guild", "")),
                        "FashionModelId": int(bot.get("FashionModelId", 0)),
                        "FAP": int(bot["FAP"]),
                        "_src": f"cs-bot:5:{10 + (idx % 10) * 3}",
                    }
                )
            idx += 1
        return roster

    def _pvpinter_top_bracket(self, group_id: int) -> dict[int, list[dict[str, Any]]]:
        """Generate deterministic Bo3 bracket matches for stages 32 -> 16 -> 8 -> 4 -> 2 -> 1."""
        contenders = self._pvpinter_top_roster(group_id)
        rounds_by_stage: dict[int, list[dict[str, Any]]] = {}
        current = contenders
        for stage in (32, 16, 8, 4, 2):
            matches: list[dict[str, Any]] = []
            winners: list[dict[str, Any]] = []
            for m_idx in range(0, len(current), 2):
                a = current[m_idx]
                b = current[m_idx + 1]
                # Deterministic winner favoring higher FAP (and player seed in ties / Group 1 opener)
                h_byte = hashlib.md5(f"top:{group_id}:{stage}:{a['Id']}:{b['Id']}".encode()).digest()[0]
                atk_wins = (int(a["FAP"]) > int(b["FAP"])) or (int(a["FAP"]) == int(b["FAP"]) and (h_byte % 2 == 0))
                if group_id == 1 and str(a["Id"]) == str(self.state["player"].get("PlayerId", "")) and stage >= 16:
                    atk_wins = True
                rounds = (1, 0, 1) if atk_wins else (0, 1, 0)
                win_obj = a if atk_wins else b
                winners.append(win_obj)
                m_num = m_idx // 2 + 1
                rep_ids = f"g{group_id}_s{stage}_m{m_num}_r1,g{group_id}_s{stage}_m{m_num}_r2,g{group_id}_s{stage}_m{m_num}_r3"
                matches.append(
                    {
                        "AttackerId": a["Id"],
                        "AttackerName": a["Name"],
                        "AttackerHeadImageId": int(a["HeadImageId"]),
                        "AttackerServerId": int(a["ServerId"]),
                        "AttackerZone": a["Zone"],
                        "AttackerGuildName": a["GuildName"],
                        "AttackerFashionModelId": int(a["FashionModelId"]),
                        "AttackerFAP": int(a["FAP"]),
                        "DefenderId": b["Id"],
                        "DefenderName": b["Name"],
                        "DefenderHeadImageId": int(b["HeadImageId"]),
                        "DefenderServerId": int(b["ServerId"]),
                        "DefenderZone": b["Zone"],
                        "DefenderGuildName": b["GuildName"],
                        "DefenderFashionModelId": int(b["FashionModelId"]),
                        "DefenderFAP": int(b["FAP"]),
                        "BattleReportId": rep_ids,
                        "IsWin": _pack_bo3_is_win(rounds),
                        "BattleTime": 0,
                        "Strong": stage,
                        "GroupId": group_id,
                        "_winner_id": win_obj["Id"],
                    }
                )
            rounds_by_stage[stage] = matches
            current = winners

        champ = current[0]
        rounds_by_stage[1] = [
            {
                "AttackerId": champ["Id"],
                "AttackerName": champ["Name"],
                "AttackerHeadImageId": int(champ["HeadImageId"]),
                "AttackerServerId": int(champ["ServerId"]),
                "AttackerZone": champ["Zone"],
                "AttackerGuildName": champ["GuildName"],
                "AttackerFashionModelId": int(champ["FashionModelId"]),
                "AttackerFAP": int(champ["FAP"]),
                "DefenderId": champ["Id"],
                "DefenderName": champ["Name"],
                "DefenderHeadImageId": int(champ["HeadImageId"]),
                "DefenderServerId": int(champ["ServerId"]),
                "DefenderZone": champ["Zone"],
                "DefenderGuildName": champ["GuildName"],
                "DefenderFashionModelId": int(champ["FashionModelId"]),
                "DefenderFAP": int(champ["FAP"]),
                "BattleReportId": f"g{group_id}_s1_m1_r1",
                "IsWin": _pack_bo3_is_win((1, 1, 1)),
                "BattleTime": 0,
                "Strong": 1,
                "GroupId": group_id,
                "_winner_id": champ["Id"],
            }
        ]
        return rounds_by_stage

    @staticmethod
    def _strip_match_internal(m: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in m.items() if not str(k).startswith("_")}

    def _pvpinter_top_fight_objs_for(self, fighter_id: str, fallback_fap: int) -> list[dict[str, Any]]:
        if fighter_id == str(self.state["player"].get("PlayerId", "")):
            return self._build_ally_fight_objs()
        for peer in self._get_peer_s1_profiles():
            if str(peer.state.get("player", {}).get("PlayerId", "")) == fighter_id:
                return peer._build_ally_fight_objs()
        step, rank = 5, 10
        if fighter_id.startswith("cs-bot:"):
            parts = fighter_id.split(":")
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                step, rank = int(parts[1]), int(parts[2])
        bot = self._arena_bot_profile(rank, step)
        objs = self._arena_bot_fight_objs(bot)
        if fallback_fap > 0:
            scale_wave_to_target_fap(objs, fallback_fap)
        return objs

    def _rpc_pvpinter_top_open(self, _data: Any) -> dict[str, Any]:
        return {"IsOpen": 1, "LastPvpinterTop": 1}

    def _rpc_pvpinter_top_get_own_info(self, _data: Any) -> dict[str, Any]:
        st = self._ensure_pvpinter_state()
        return {"PVPinterTopBetInfo": list(st.get("top_bets", []))}

    def _rpc_pvpinter_top_get_battle_report(self, data: Any) -> dict[str, Any]:
        group_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 and data[0] is not None else 1
        group_id = max(1, min(4, group_id))
        raw_stage = int(data[1]) if isinstance(data, list) and len(data) >= 2 and data[1] is not None else 1
        stage = raw_stage if raw_stage in (32, 16, 8, 4, 2, 1) else 1
        bracket = self._pvpinter_top_bracket(group_id)
        return {
            "Strong": stage,
            "BattleTime": 0,
            "BattleReport": [self._strip_match_internal(m) for m in bracket[stage]],
        }

    def _rpc_pvpinter_top_get_own_battle_report(self, _data: Any) -> dict[str, Any]:
        pid = str(self.state["player"].get("PlayerId", ""))
        bracket = self._pvpinter_top_bracket(1)
        own: list[dict[str, Any]] = []
        for stage in (32, 16, 8, 4, 2):
            for m in bracket[stage]:
                if str(m["AttackerId"]) == pid or str(m["DefenderId"]) == pid:
                    own.append(self._strip_match_internal(m))
        return {"BattleReport": own}

    def _rpc_pvpinter_top_get_battle_content(self, data: Any) -> dict[str, Any]:
        group_id = int(data[0]) if isinstance(data, list) and len(data) >= 1 and data[0] is not None else 1
        group_id = max(1, min(4, group_id))
        stage = int(data[1]) if isinstance(data, list) and len(data) >= 2 and data[1] is not None else 2
        if stage not in (32, 16, 8, 4, 2, 1):
            stage = 2
        rep_id = str(data[2]) if isinstance(data, list) and len(data) >= 3 and data[2] is not None else ""
        bracket = self._pvpinter_top_bracket(group_id)
        matches = bracket[stage]
        match = next((m for m in matches if rep_id and rep_id in str(m["BattleReportId"]).split(",")), matches[0])

        allies = self._pvpinter_top_fight_objs_for(str(match["AttackerId"]), int(match["AttackerFAP"]))
        enemies = self._pvpinter_top_fight_objs_for(str(match["DefenderId"]), int(match["DefenderFAP"]))
        fight_info = {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": sum(int(u.get("FSP", 0)) for u in allies if u), "Fap": int(match["AttackerFAP"])},
                        {"Fsp": sum(int(u.get("FSP", 0)) for u in enemies if u), "Fap": int(match["DefenderFAP"])},
                    ],
                    "Pets": [],
                    "RandNum": int(sum(ord(c) for c in (rep_id or "top")) % 90000 + 1000),
                    "IsPVP": True,
                }
            ]
        }
        return {"FightInfo": {"ClientRes": fight_info, **fight_info}}

    def _rpc_pvpinter_top_bet(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            bets_type = int(data[0])
            target_id = str(data[1])
            stage = int(data[2]) if len(data) >= 3 and data[2] is not None else 2
            group_id = int(data[3]) if len(data) >= 4 and data[3] is not None else 1
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        if bets_type not in (1, 2, 3) or stage not in (32, 16, 8, 4, 2) or group_id not in (1, 2, 3, 4):
            self._last_rpc_context["status"] = -1
            return {}

        st = self._ensure_pvpinter_state()
        bets = st.setdefault("top_bets", [])
        if any(int(b.get("Strong", 0)) == stage for b in bets):
            self._last_rpc_context["status"] = -1
            return {}

        gamble_row = self.game_data.get("pvpinter_top_gamble", {}).get(str(stage // 2), {}).get(str(bets_type))
        if not gamble_row:
            self._last_rpc_context["status"] = -1
            return {}
        costs = _parse_res_tuples(str(gamble_row.get("betsAmount", "1112,0,10000")))
        gold_cost = sum(qty for rtype, _rm, qty in costs if rtype == 1112)
        player = self.state["player"]
        if int(player.get("Gold", 0)) < gold_cost:
            self._last_rpc_context["status"] = -1118
            return {}
        if gold_cost > 0:
            self.ledger.apply_player_delta(
                player, self.profile_name, "Gold", -gold_cost, source=f"pvpinter_top_bet:{stage}:{bets_type}"
            )

        bracket = self._pvpinter_top_bracket(group_id)
        winners = {str(m["_winner_id"]) for m in bracket[stage]}
        is_win = 1 if target_id in winners else 0
        bet_entry = {
            "Strong": stage,
            "GroupId": group_id,
            "TargetId": target_id,
            "BetsType": bets_type,
            "IsWin": is_win,
            "IsReward": 0,
        }
        bets.append(bet_entry)
        self.save()
        return {"PVPinterTopBetInfo": bet_entry}

    def _rpc_pvpinter_top_bet_reward(self, _data: Any) -> dict[str, Any]:
        st = self._ensure_pvpinter_state()
        bets = st.setdefault("top_bets", [])
        claimable = [b for b in bets if int(b.get("IsWin", 0)) == 1 and int(b.get("IsReward", 0)) == 0]
        if not claimable:
            self._last_rpc_context["status"] = -1
            return {}
        gamble_tbl = self.game_data.get("pvpinter_top_gamble", {})
        tuples: list[tuple[int, int, int]] = []
        for b in claimable:
            g_row = gamble_tbl.get(str(int(b["Strong"]) // 2), {}).get(str(int(b["BetsType"])), {})
            tuples.extend(_parse_res_tuples(str(g_row.get("rewardAmount", "1112,0,100000"))))
            b["IsReward"] = 1
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="pvpinter_top_bet_reward",
            tx_prefix=f"pvpinter_bet_rew:{self.profile_name}:{self.now_ts()}:{random.randint(100, 9999)}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_pvpinter_top_worship(self, data: Any) -> dict[str, Any]:
        group_id = int(data[0]) if isinstance(data, list) and data and data[0] is not None else 1
        if group_id not in (1, 2, 3, 4):
            self._last_rpc_context["status"] = -1
            return {}
        st = self._ensure_pvpinter_state()
        w_today = st.setdefault("worship_groups_today", [])
        if group_id in w_today:
            self._last_rpc_context["status"] = -1
            return {}
        player = self.state["player"]
        cost = 50
        if int(player.get("Diamond", 0)) < cost:
            self._last_rpc_context["status"] = -1105
            return {}
        self.ledger.apply_player_delta(
            player, self.profile_name, "Diamond", -cost, source=f"pvpinter_worship:{group_id}"
        )
        w_today.append(group_id)
        days_total = int(st.get("worship_days_total", 0)) + 1
        st["worship_days_total"] = days_total

        worship_tbl = self.game_data.get("pvpinter_top_worship", {})
        max_day_key = max((int(k) for k in worship_tbl if str(k).isdigit()), default=6)
        day_key = str(((days_total - 1) % max_day_key) + 1)
        row = worship_tbl.get(day_key, worship_tbl.get("1", {}))
        tuples = _parse_res_tuples(str(row.get("rewards", "1605,16050072,1||1605,16050065,100||1111,0,100")))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"pvpinter_worship:{group_id}:{day_key}",
            tx_prefix=f"pvpinter_worship:{self.profile_name}:{group_id}:{self.now_ts()}:{random.randint(100, 9999)}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}
