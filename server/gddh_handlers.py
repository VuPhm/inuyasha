"""Đấu Võ Đại Hội (`Gddh` 8 RPC + `GddhShop` 2 RPC = 10 RPC, ModuleSub 2503) handlers."""

from __future__ import annotations

import datetime as _dt
import random
import uuid
import zlib
from typing import Any

from combat_sim import simulate_fight_info
from r79_event_handlers import _parse_res_tuples

EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"
_UNAVAILABLE_RANK = 1_000_000

_GDDH_BOT_NAMES: tuple[str, ...] = (
    "SátSinhHoàn",
    "KhuyểnDạXoa",
    "Kikyo",
    "AQua",
    "Miroku",
    "SanGo",
    "NạiLạc",
    "ThầnLạc",
    "ThầnVô",
    "BạchĐồngTử",
    "HắcVuNữ",
    "NgânLang",
    "LuyệnCốt",
    "ManCốt",
    "XíchNguyệt",
    "HồĐiệp",
    "Kaguya",
    "TứĐấuThần",
    "InuKimi",
    "LăngNguyệt",
)

_GDDH_GUILDS: tuple[str, ...] = (
    "Tây Quốc",
    "Phong Chi Thương",
    "Hội Trừ Yêu",
    "Bạch Linh Sơn",
    "Chiến Quốc",
    "",
)

_GDDH_BOT_HEROS: tuple[int, ...] = (
    12011004,
    12011005,
    12011006,
    12011007,
    12011008,
    12011009,
    12011011,
    12011012,
    12011018,
    12011019,
    12011022,
    12012005,
    12013003,
    12013004,
    12013005,
)


def _det_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"inuyasha.revival.{seed}"))


class GddhHandlersMixin:
    """Offline server emulation for Đấu Võ Đại Hội (`Gddh` & `GddhShop`, 10 RPCs)."""

    def _gddh_season_window(self, ts: int | None = None) -> dict[str, Any]:
        cur_ts = self.now_ts() if ts is None else int(ts)
        dt = self.clock.dt(cur_ts)
        tz = self.clock.tz()
        wd = dt.isoweekday()  # 1=Mon .. 7=Sun
        today_date = dt.date()

        if wd in (2, 3):  # Tue-Wed (2-day season)
            start_date = today_date - _dt.timedelta(days=wd - 2)
            end_date = start_date + _dt.timedelta(days=1)
            rewards_type = 1
            iso_y, iso_w, _ = start_date.isocalendar()
            season_id = f"{iso_y}-W{iso_w:02d}-S1"
        elif wd in (4, 5):  # Thu-Fri (2-day season)
            start_date = today_date - _dt.timedelta(days=wd - 4)
            end_date = start_date + _dt.timedelta(days=1)
            rewards_type = 1
            iso_y, iso_w, _ = start_date.isocalendar()
            season_id = f"{iso_y}-W{iso_w:02d}-S2"
        else:  # Sat-Mon (3-day big-reward season)
            offset = {6: 0, 7: 1, 1: 2}[wd]
            start_date = today_date - _dt.timedelta(days=offset)
            end_date = start_date + _dt.timedelta(days=2)
            rewards_type = 0
            iso_y, iso_w, _ = start_date.isocalendar()
            season_id = f"{iso_y}-W{iso_w:02d}-S3"

        def _mid_ts(d: _dt.date) -> int:
            return int(_dt.datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz).timestamp())

        cfg = self.game_data.get("gddh_config", {})
        start_mid = _mid_ts(start_date)
        end_mid = _mid_ts(end_date)
        init_begin_date = start_mid - 60
        begin_date = start_mid - 30
        first_reward_date = start_mid + 23 * 3600
        end_reward_date = end_mid + 23 * 3600
        end_date_ts = end_reward_date + int(cfg.get("perRewardContinue", 1800))
        is_truce = 1 if cur_ts >= end_reward_date else 0

        return {
            "season_id": season_id,
            "rewards_type": rewards_type,
            "start_date_str": start_date.strftime("%Y-%m-%d"),
            "end_date_str": end_date.strftime("%Y-%m-%d"),
            "init_begin_date": init_begin_date,
            "begin_date": begin_date,
            "first_reward_date": first_reward_date,
            "end_reward_date": end_reward_date,
            "end_date": end_date_ts,
            "is_truce": is_truce,
        }

    def _gddh_ensure_state_dict(self) -> dict[str, Any]:
        gddh = self.state.setdefault("gddh", {})
        if not isinstance(gddh, dict):
            gddh = {}
            self.state["gddh"] = gddh
        cfg = self.game_data.get("gddh_config", {})
        init_val = int(cfg.get("initValue", 1000))
        max_atk = int(cfg.get("attckNumMax", 10))
        now = self.now_ts()
        today = self.clock.today_str(now)
        win = self._gddh_season_window(now)

        gddh.setdefault("season_id", win["season_id"])
        gddh.setdefault("season_rewards_type", win["rewards_type"])
        gddh.setdefault("season_end_date_str", win["end_date_str"])
        gddh.setdefault("is_apply", 0)
        gddh.setdefault("group_id", 1)
        gddh.setdefault("integral", init_val)
        gddh.setdefault("history_rank", _UNAVAILABLE_RANK)
        gddh.setdefault("rank_count", max_atk)
        gddh.setdefault("last_recover_time", now)
        gddh.setdefault("last_refresh_time", now)
        gddh.setdefault("refresh_seed", 0)
        gddh.setdefault("day", today)
        gddh.setdefault("buy_rank_count", 0)
        gddh.setdefault("per_rank_count", 0)
        gddh.setdefault("claimed_attack_rewards", [])
        gddh.setdefault("revive_list", [])
        gddh.setdefault("bot_integrals", {})
        gddh.setdefault("settled_seasons", [])
        gddh.setdefault("settled_daily_days", [])
        gddh.setdefault("shop_bought_daily", {"_date": today})
        gddh.setdefault("shop_bought_season", {"_season": gddh["season_id"]})
        gddh.setdefault("shop_bought_total", {})
        return gddh

    def _gddh_rank_reward_row(self, rewards_type: int, rank: int) -> dict[str, Any] | None:
        rows = self.game_data.get("gddh_rank_reward", {}).get(str(rewards_type), [])
        for row in rows:
            if int(row.get("rankMin", 0)) <= rank <= int(row.get("rankMax", 0)):
                return row
        return rows[-1] if rows else None

    def _gddh_sync_recover(self, gddh: dict[str, Any], now: int) -> bool:
        cfg = self.game_data.get("gddh_config", {})
        rec_cd = max(60, int(cfg.get("attckNumRecoverCD", 3600)))
        max_atk = int(cfg.get("attckNumMax", 10))
        cur_cnt = int(gddh.get("rank_count", max_atk))
        if cur_cnt >= max_atk:
            return False
        next_ts = int(gddh.get("last_recover_time", now))
        if now < next_ts:
            return False
        gained = 1 + (now - next_ts) // rec_cd
        new_cnt = min(max_atk, cur_cnt + gained)
        gddh["rank_count"] = new_cnt
        if new_cnt >= max_atk:
            gddh["last_recover_time"] = now
        else:
            gddh["last_recover_time"] = next_ts + gained * rec_cd
        return True

    def _gddh_push_daily_settlement(self, day_str: str, rewards_type: int, rank: int) -> bool:
        settled = self.state["gddh"].setdefault("settled_daily_days", [])
        if day_str in settled or rank <= 0:
            return False
        row = self._gddh_rank_reward_row(rewards_type, rank)
        if not row:
            return False
        lv = max(1, int(self.state["player"].get("Lv", 35)))
        gold = int(row.get("perRewardRawGold", 100)) * lv
        settled.append(day_str)
        if gold > 0:
            self._push_reward_center_entry(
                source_key=f"gddh_daily:{day_str}",
                title="Quà Ngày Đấu Võ Đại Hội",
                content=f"Thưởng xếp hạng ngày {day_str} (Hạng {rank} Đấu Võ Đại Hội).",
                res_tuples=[(1112, 0, gold)],
            )
            return True
        return False

    def _gddh_push_season_settlement(self, season_id: str, rewards_type: int, rank: int) -> bool:
        settled = self.state["gddh"].setdefault("settled_seasons", [])
        if season_id in settled or rank <= 0:
            return False
        row = self._gddh_rank_reward_row(rewards_type, rank)
        if not row:
            return False
        lv = max(1, int(self.state["player"].get("Lv", 35)))
        tuples: list[tuple[int, int, int]] = []
        gold = int(row.get("perRewardRawGold", 100)) * lv
        if gold > 0:
            tuples.append((1112, 0, gold))
        for rt, rm, rn in _parse_res_tuples(str(row.get("seasonReward", ""))):
            if rt == 2112:
                tuples.append((1112, 0, rn * lv))
            else:
                tuples.append((rt, rm, rn))
        settled.append(season_id)
        if tuples:
            self._push_reward_center_entry(
                source_key=f"gddh_season:{season_id}",
                title="Thưởng Mùa Giải Đấu Võ Đại Hội",
                content=f"Tổng kết mùa giải {season_id} (Hạng {rank} Đấu Võ Đại Hội).",
                res_tuples=tuples,
            )
            return True
        return False

    def _gddh_push_guild_season_settlement(
        self, season_id: str, rewards_type: int, groups: dict[str, Any],
    ) -> bool:
        if not hasattr(self, "_push_guild_reward"):
            return False
        settled_guild = self.state["gddh"].setdefault("settled_guild_seasons", [])
        if season_id in settled_guild:
            return False
        p = self.state["player"]
        if str(p.get("GuildId", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
            return False
        my_gname = str(p.get("GuildName", "") or "").strip()
        if not my_gname:
            return False
        guild_infos = groups.get("GuildInfo", []) if isinstance(groups, dict) else []
        g_entry = next(
            (g for g in guild_infos if g.get("IsSelfGuild") or str(g.get("GuildName", "")).strip() == my_gname),
            None,
        )
        if not g_entry:
            return False
        g_rank = int(g_entry.get("Rank", 0))
        if g_rank <= 0:
            return False
        rows = self.game_data.get("gddh_guild_reward", {}).get(str(rewards_type), [])
        row = next((r for r in rows if int(r.get("rankMin", 0)) <= g_rank <= int(r.get("rankMax", 0))), None)
        if not row:
            return False
        lv = max(1, int(p.get("Lv", 35)))
        tuples: list[tuple[int, int, int]] = []
        for rt, rm, rn in _parse_res_tuples(str(row.get("guildRewards", ""))):
            if rt == 2112:
                tuples.append((1112, 0, rn * lv))
            else:
                tuples.append((rt, rm, rn))
        settled_guild.append(season_id)
        if tuples:
            self._push_guild_reward(
                f"Thưởng Công Hội Đấu Võ Đại Hội ({season_id} - Hạng {g_rank})",
                tuples,
                source_key=f"gddh_guild:{season_id}",
            )
            return True
        return False

    def _sync_gddh_settlement(self) -> bool:
        """Settle Gddh daily (23:00 non-final) & season-end rewards to RewardCenter (2400)."""
        raw_gddh = self.state.get("gddh")
        if not isinstance(raw_gddh, dict) or not raw_gddh.get("season_id"):
            return False
        gddh = self._gddh_ensure_state_dict()
        changed = False
        now = self.now_ts()
        today = self.clock.today_str(now)
        win = self._gddh_season_window(now)
        old_season = str(gddh["season_id"])
        old_rtype = int(gddh.get("season_rewards_type", win["rewards_type"]))
        prev_day = str(gddh.get("day", today))
        lv = int(self.state["player"].get("Lv", 1))

        if int(gddh.get("is_apply", 0)) == 1 and lv >= 35:
            group_id = int(gddh.get("group_id", 1))
            # Determine player's current rank within old_season BEFORE any season reset
            groups = self._gddh_build_groups_for_season(gddh, old_season)
            group_key = ("One", "Two", "Three", "Four")[max(0, min(3, group_id - 1))]
            my_pid = str(self.state["player"]["PlayerId"])
            rank = next((int(e["Rank"]) for e in groups[group_key] if e["PlayerId"] == my_pid), 0)

            if old_season == win["season_id"]:
                # Same season: missed prior day daily reward
                if prev_day and prev_day != today:
                    if self._gddh_push_daily_settlement(prev_day, old_rtype, rank):
                        changed = True
                # Same season: current day >= 23:00
                today_23h = self.clock.midnight_ts(now) + 23 * 3600
                if today != win["end_date_str"]:
                    if now >= today_23h and self._gddh_push_daily_settlement(today, old_rtype, rank):
                        changed = True
                elif now >= int(win["end_reward_date"]):
                    if self._gddh_push_season_settlement(old_season, old_rtype, rank):
                        changed = True
                    if self._gddh_push_guild_season_settlement(old_season, old_rtype, groups):
                        changed = True
            else:
                # Season rolled over cleanly -> settle prev_day if non-final, then settle old season
                old_end_str = str(gddh.get("season_end_date_str", ""))
                if prev_day and prev_day != old_end_str:
                    if self._gddh_push_daily_settlement(prev_day, old_rtype, rank):
                        changed = True
                if self._gddh_push_season_settlement(old_season, old_rtype, rank):
                    changed = True
                if self._gddh_push_guild_season_settlement(old_season, old_rtype, groups):
                    changed = True

        # Rollover season state cleanly
        if old_season != win["season_id"]:
            cfg = self.game_data.get("gddh_config", {})
            gddh["season_id"] = win["season_id"]
            gddh["season_rewards_type"] = win["rewards_type"]
            gddh["season_end_date_str"] = win["end_date_str"]
            gddh["is_apply"] = 0
            gddh["integral"] = int(cfg.get("initValue", 1000))
            gddh["revive_list"] = []
            gddh["bot_integrals"] = {}
            gddh["shop_bought_season"] = {"_season": win["season_id"]}
            changed = True

        # Daily rollover
        if gddh.get("day") != today:
            gddh["day"] = today
            gddh["buy_rank_count"] = 0
            gddh["per_rank_count"] = 0
            gddh["claimed_attack_rewards"] = []
            gddh["shop_bought_daily"] = {"_date": today}
            changed = True

        if self._gddh_sync_recover(gddh, now):
            changed = True
        return changed

    def _gddh_state(self) -> dict[str, Any]:
        gddh = self._gddh_ensure_state_dict()
        if self._sync_gddh_settlement():
            self.save()
        return gddh

    def _gddh_bot_profile(self, season_id: str, group_id: int, bot_idx: int, base_lv: int) -> dict[str, Any]:
        heroes_cfg = self.game_data.get("heroes", {})
        pool = [hm for hm in _GDDH_BOT_HEROS if str(hm) in heroes_cfg]
        if not pool:
            pool = [int(k) for k in list(heroes_cfg.keys())[:15]]
        rng = random.Random(zlib.crc32(f"gddh:{season_id}:{group_id}:{bot_idx}".encode("utf-8")))
        bot_lv = max(35, min(80, base_lv - 5 + rng.randint(0, 12)))
        slot_count = 6 if bot_idx < 10 else 5
        step_up = max(1, min(8, 2 + (19 - bot_idx) // 4))
        rng.shuffle(pool)
        chosen = pool[:slot_count]
        eq_set = (13010503, 13020503, 13030503, 13040503) if bot_idx < 10 else (13010404, 13020404, 13030404, 13040404)
        eq_lv = max(20, bot_lv)

        bot_pid = _det_uuid(f"gddh_bot:{season_id}:{group_id}:{bot_idx}")
        slots: list[dict[str, Any]] = []
        heroes_by_id: dict[str, dict[str, Any]] = {}
        embattle: dict[str, int] = {f"Formation{i}": 0 for i in range(1, 7)}
        total_fap = 0
        for s_idx in range(1, 7):
            if s_idx <= len(chosen):
                hm = chosen[s_idx - 1]
                h_id = _det_uuid(f"gddh_hero:{season_id}:{group_id}:{bot_idx}:{s_idx}")
                h_inst = self._build_hero_instance(hm, lv=bot_lv, step=step_up, inst_id=h_id)
                heroes_by_id[h_id] = h_inst
                slot: dict[str, Any] = {
                    "SlotId": s_idx,
                    "HeroId": h_id,
                    "HeroModelId": hm,
                    "GemId": EMPTY_ENTITY_ID,
                    "NewWraithId": EMPTY_ENTITY_ID,
                    "StarId": 0,
                    "Book": None,
                    "Horse": None,
                    "Hero": h_inst,
                }
                for ek, em_id in zip(("Weapon", "Helmet", "Clothes", "Necklace"), eq_set):
                    slot[ek] = {
                        "Id": _det_uuid(f"gddh_eq:{season_id}:{group_id}:{bot_idx}:{s_idx}:{ek}"),
                        "EquipModelId": em_id,
                        "Lv": eq_lv,
                        "Step": 0,
                        "Gold": 0,
                        "ExtraCount": 0,
                        "APExtra": 0,
                        "HPExtra": 0,
                        "DEFExtra": 0,
                        "DAMADDExtra": 0,
                        "DAMCUTExtra": 0,
                    }
                prop = self._compute_slot_property(slot, heroes_by_id, include_player_star=False)
                slot["Property"] = prop
                total_fap += int(prop["FAP"])
                embattle[f"Formation{s_idx}"] = s_idx
            else:
                slot = {
                    "SlotId": s_idx,
                    "HeroId": EMPTY_ENTITY_ID,
                    "HeroModelId": 0,
                    "Weapon": None,
                    "Helmet": None,
                    "Clothes": None,
                    "Necklace": None,
                    "Book": None,
                    "Horse": None,
                    "GemId": EMPTY_ENTITY_ID,
                    "NewWraithId": EMPTY_ENTITY_ID,
                    "StarId": 0,
                    "Property": self._compute_slot_property({"HeroId": EMPTY_ENTITY_ID}, {}),
                }
            slots.append(slot)

        base_integral = 2150 - bot_idx * 70  # spans 2150 down to 820
        name = f"{_GDDH_BOT_NAMES[bot_idx % len(_GDDH_BOT_NAMES)]}{group_id}{bot_idx + 1}"
        return {
            "PlayerId": bot_pid,
            "Lv": bot_lv,
            "Name": name,
            "HeadImageId": chosen[0],
            "FashionModelId": 0,
            "Guild": _GDDH_GUILDS[(group_id + bot_idx) % len(_GDDH_GUILDS)],
            "GroupId": group_id,
            "FAP": total_fap,
            "DefaultIntegral": base_integral,
            "Slots": slots,
            "Embattle": embattle,
            "HeroesById": heroes_by_id,
        }

    def _gddh_bot_slot_formations(self, target_id: str) -> dict[str, Any] | None:
        gddh = self._gddh_ensure_state_dict()
        season_id = str(gddh.get("season_id", self._gddh_season_window()["season_id"]))
        base_lv = max(35, int(self.state["player"].get("Lv", 35)))
        for gid in range(1, 5):
            for idx in range(20):
                if _det_uuid(f"gddh_bot:{season_id}:{gid}:{idx}") == target_id:
                    return self._build_bot_formation_view(self._gddh_bot_profile(season_id, gid, idx, base_lv))
        return None

    def _gddh_build_groups_for_season(self, gddh: dict[str, Any], season_id: str) -> dict[str, Any]:
        p = self.state["player"]
        base_lv = max(35, int(p.get("Lv", 35)))
        overrides = gddh.get("bot_integrals", {})
        group_names = ("One", "Two", "Three", "Four")
        groups: dict[str, list[dict[str, Any]]] = {k: [] for k in group_names}
        guild_totals: dict[str, dict[str, Any]] = {}

        for gid_idx, gname in enumerate(group_names, start=1):
            entries: list[dict[str, Any]] = []
            for idx in range(20):
                bot = self._gddh_bot_profile(season_id, gid_idx, idx, base_lv)
                integ = int(overrides.get(bot["PlayerId"], bot["DefaultIntegral"]))
                entries.append(
                    {
                        "PlayerId": bot["PlayerId"],
                        "HeadImageId": int(bot["HeadImageId"]),
                        "FashionModelId": 0,
                        "Lv": int(bot["Lv"]),
                        "Name": bot["Name"],
                        "Guild": bot["Guild"],
                        "Integral": integ,
                        "FAP": int(bot["FAP"]),
                        "GroupId": gid_idx,
                    }
                )

            # Real S1 self & peers joined in this season
            if int(gddh.get("is_apply", 0)) == 1 and int(gddh.get("group_id", 1)) == gid_idx and str(gddh.get("season_id")) == season_id:
                entries.append(
                    {
                        "PlayerId": str(p["PlayerId"]),
                        "HeadImageId": int(p.get("HeadImageId", 12011004)),
                        "FashionModelId": int(p.get("FashionModelId", 0)),
                        "Lv": int(p.get("Lv", 35)),
                        "Name": str(p.get("PlayerName", "Adventurer")),
                        "Guild": str(p.get("GuildName", "") or ""),
                        "Integral": int(gddh.get("integral", 1000)),
                        "FAP": int(p.get("FAP", 0)),
                        "GroupId": gid_idx,
                    }
                )
            for peer in self._get_peer_s1_profiles():
                pg = peer.state.get("gddh", {})
                if isinstance(pg, dict) and pg.get("season_id") == season_id and int(pg.get("is_apply", 0)) == 1 and int(pg.get("group_id", 1)) == gid_idx:
                    pp = peer.state["player"]
                    entries.append(
                        {
                            "PlayerId": str(pp["PlayerId"]),
                            "HeadImageId": int(pp.get("HeadImageId", 12011004)),
                            "FashionModelId": int(pp.get("FashionModelId", 0)),
                            "Lv": int(pp.get("Lv", 35)),
                            "Name": str(pp.get("PlayerName", "Peer")),
                            "Guild": str(pp.get("GuildName", "") or ""),
                            "Integral": int(pg.get("integral", 1000)),
                            "FAP": int(pp.get("FAP", 0)),
                            "GroupId": gid_idx,
                        }
                    )

            entries.sort(key=lambda e: (-int(e["Integral"]), str(e["PlayerId"])))
            for rank_num, e in enumerate(entries, start=1):
                e["Rank"] = rank_num
                g_name = str(e.get("Guild", "") or "").strip()
                if g_name:
                    rec = guild_totals.setdefault(g_name, {"GuildName": g_name, "Integral": 0, "LV": 1, "IsSelfGuild": False})
                    rec["Integral"] += int(e["Integral"])
                    rec["LV"] = max(rec["LV"], min(10, int(e["Lv"]) // 8))
                    if g_name == str(p.get("GuildName", "") or ""):
                        rec["IsSelfGuild"] = True
            groups[gname] = entries

        guild_list = sorted(guild_totals.values(), key=lambda g: (-int(g["Integral"]), str(g["GuildName"])))
        for idx, gr in enumerate(guild_list, start=1):
            gr["Rank"] = idx
        return {
            "One": groups["One"],
            "Two": groups["Two"],
            "Three": groups["Three"],
            "Four": groups["Four"],
            "GuildInfo": guild_list,
        }

    def _gddh_build_targets(self, gddh: dict[str, Any], rank_list: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = self.game_data.get("gddh_config", {})
        high_min = int(cfg.get("highValueMin", 70))
        value_add_r = int(cfg.get("valueAddR", 500))
        my_pid = str(self.state["player"]["PlayerId"])

        all_candidates = [
            dict(entry)
            for key in ("One", "Two", "Three", "Four")
            for entry in rank_list.get(key, [])
            if entry["PlayerId"] != my_pid
        ]
        all_candidates.sort(key=lambda e: (-int(e["Integral"]), str(e["PlayerId"])))

        high_pool = [e for e in all_candidates if int(e["Integral"]) * value_add_r >= high_min * 10000]
        normal_pool = [e for e in all_candidates if e not in high_pool]
        rng = random.Random(zlib.crc32(f"{gddh['season_id']}:{gddh.get('refresh_seed', 0)}".encode("utf-8")))

        picked: list[dict[str, Any]] = []
        if high_pool:
            t1 = dict(rng.choice(high_pool[: max(1, len(high_pool) // 2)]))
            t1["HighValueMin"] = 1
            picked.append(t1)
        elif all_candidates:
            t1 = dict(all_candidates[0])
            t1["HighValueMin"] = 1
            picked.append(t1)

        rem = [e for e in (normal_pool or all_candidates) if e["PlayerId"] not in {x["PlayerId"] for x in picked}]
        rng.shuffle(rem)
        for cand in rem[: max(0, 3 - len(picked))]:
            c_copy = dict(cand)
            c_copy["HighValueMin"] = 0
            picked.append(c_copy)
        while len(picked) < 3 and all_candidates:
            fallback = next((e for e in all_candidates if e["PlayerId"] not in {x["PlayerId"] for x in picked}), all_candidates[0])
            fc = dict(fallback)
            fc["HighValueMin"] = 0
            picked.append(fc)
        return picked[:3]

    def _gddh_find_target(
        self, gddh: dict[str, Any], target_id: str,
    ) -> tuple[str, int, str, int, int, int, list[dict[str, Any]], Any]:
        """Resolve Gddh target (S1 peer or deterministic bot across 4 groups)."""
        peer = self._find_peer_by_player_id(target_id)
        if peer is not None:
            pg = peer.state.get("gddh", {})
            pp = peer.state["player"]
            return (
                str(pp["PlayerId"]),
                int(pp.get("Lv", 35)),
                str(pp.get("PlayerName", "Peer")),
                int(pp.get("FAP", 0)),
                int(pg.get("integral", 1000)) if isinstance(pg, dict) else 1000,
                int(pp.get("HeadImageId", 12011004)),
                peer._build_ally_fight_objs(),
                peer,
            )

        season_id = str(gddh["season_id"])
        base_lv = max(35, int(self.state["player"].get("Lv", 35)))
        overrides = gddh.get("bot_integrals", {})
        for gid in range(1, 5):
            for idx in range(20):
                if _det_uuid(f"gddh_bot:{season_id}:{gid}:{idx}") == target_id:
                    bot = self._gddh_bot_profile(season_id, gid, idx, base_lv)
                    integ = int(overrides.get(target_id, bot["DefaultIntegral"]))
                    return (
                        target_id,
                        int(bot["Lv"]),
                        str(bot["Name"]),
                        int(bot["FAP"]),
                        integ,
                        int(bot["HeadImageId"]),
                        self._arena_bot_fight_objs(bot),
                        None,
                    )
        return ("", 0, "", 0, 0, 0, [], None)

    def _gddh_welfare_mult(self) -> int:
        return self._timed_welfare_mult(4414)

    def _gddh_red_dot(self) -> int:
        if int(self.state.get("player", {}).get("Lv", 1)) < 35:
            return 0
        now = self.now_ts()
        win = self._gddh_season_window(now)
        if win["is_truce"] == 1:
            return 0
        gddh = self._gddh_state()
        if int(gddh.get("is_apply", 0)) == 0:
            return 1
        if int(gddh.get("rank_count", 0)) > 0:
            return 1
        per_cnt = int(gddh.get("per_rank_count", 0))
        claimed = set(int(x) for x in gddh.get("claimed_attack_rewards", []))
        return 1 if any(per_cnt >= int(k) and int(k) not in claimed for k in self.game_data.get("gddh_attack_reward", {})) else 0

    def _gddh_receive_ids(self, gddh: dict[str, Any]) -> list[int]:
        per_cnt = int(gddh.get("per_rank_count", 0))
        claimed = set(int(x) for x in gddh.get("claimed_attack_rewards", []))
        return [
            int(k)
            for k in sorted(self.game_data.get("gddh_attack_reward", {}), key=int)
            if per_cnt >= int(k) and int(k) not in claimed
        ]

    # -------------------- 8 Gddh RPCs --------------------

    def _rpc_gddh_signup_info(self, _data: Any) -> dict[str, Any]:
        gddh = self._gddh_state()
        win = self._gddh_season_window()
        return {
            "IsFirst": 0,
            "IsJoin": int(gddh.get("is_apply", 0)),
            "InitBeginDate": int(win["init_begin_date"]),
            "BeginDate": int(win["begin_date"]),
            "FirstRewardDate": int(win["first_reward_date"]),
            "EndRewardDate": int(win["end_reward_date"]),
            "EndDate": int(win["end_date"]),
        }

    def _rpc_gddh_apply_group(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        win = self._gddh_season_window()
        if int(p.get("Lv", 1)) < 35 or win["is_truce"] == 1:
            self._last_rpc_context["status"] = -1
            return {}
        gddh = self._gddh_state()
        if int(gddh.get("is_apply", 0)) == 1:
            return {"GroupId": int(gddh["group_id"])}
        cfg = self.game_data.get("gddh_config", {})
        max_atk = int(cfg.get("attckNumMax", 10))
        init_val = int(cfg.get("initValue", 1000))
        now = self.now_ts()
        gid = (zlib.crc32(f"{win['season_id']}:{p['PlayerId']}".encode("utf-8")) % 4) + 1
        gddh["is_apply"] = 1
        gddh["group_id"] = gid
        gddh["integral"] = init_val
        gddh["rank_count"] = max_atk
        gddh["last_recover_time"] = now

        rank_list = self._gddh_build_groups_for_season(gddh, win["season_id"])
        gname = ("One", "Two", "Three", "Four")[gid - 1]
        my_rank = next((int(e["Rank"]) for e in rank_list[gname] if e["PlayerId"] == str(p["PlayerId"])), _UNAVAILABLE_RANK)
        if my_rank < int(gddh.get("history_rank", _UNAVAILABLE_RANK)):
            gddh["history_rank"] = my_rank
        self.save()
        return {"GroupId": gid}

    def _rpc_gddh_get_info(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        gddh = self._gddh_state()
        now = self.now_ts()
        win = self._gddh_season_window(now)
        rank_list = self._gddh_build_groups_for_season(gddh, win["season_id"])
        targets = self._gddh_build_targets(gddh, rank_list)
        gid = int(gddh.get("group_id", 1))
        is_apply = int(gddh.get("is_apply", 0))
        gname = ("One", "Two", "Three", "Four")[max(0, min(3, gid - 1))]
        rank = (
            next((int(e["Rank"]) for e in rank_list[gname] if e["PlayerId"] == str(p["PlayerId"])), 0)
            if is_apply == 1
            else 0
        )
        max_atk = int(self.game_data.get("gddh_config", {}).get("attckNumMax", 10))
        rec_ts = now if int(gddh.get("rank_count", max_atk)) >= max_atk else max(now, int(gddh.get("last_recover_time", now)))
        ref_ts = max(now, int(gddh.get("last_refresh_time", now)))
        self.save()
        return {
            "IsApply": is_apply,
            "IsInTruce": int(win["is_truce"]),
            "BuyRankCount": int(gddh.get("buy_rank_count", 0)),
            "LastRecoveTime": rec_ts,
            "LastRefreshTime": ref_ts,
            "GDDHCoin": int(p.get("GDDHCoin", 0)),
            "RankCount": int(gddh.get("rank_count", max_atk)),
            "Rank": rank,
            "GroupId": gid,
            "Integral": int(gddh.get("integral", 1000)) if is_apply == 1 else 0,
            "HistortRank": int(gddh.get("history_rank", _UNAVAILABLE_RANK)),
            "PerRankCount": int(gddh.get("per_rank_count", 0)),
            "ReceiveIdList": self._gddh_receive_ids(gddh),
            "GddhRankList": rank_list,
            "GddhRankTargetList": targets,
        }

    def _rpc_gddh_refresh_rank_list(self, _data: Any) -> dict[str, Any]:
        win = self._gddh_season_window()
        gddh = self._gddh_state()
        now = self.now_ts()
        if int(self.state["player"].get("Lv", 1)) < 35 or int(gddh.get("is_apply", 0)) != 1 or win["is_truce"] == 1:
            self._last_rpc_context["status"] = -1
            return {}
        if now < int(gddh.get("last_refresh_time", 0)):
            self._last_rpc_context["status"] = -1
            return {}
        cd = int(self.game_data.get("gddh_config", {}).get("refreshCD", 10))
        gddh["last_refresh_time"] = now + cd
        gddh["refresh_seed"] = int(gddh.get("refresh_seed", 0)) + 1
        rank_list = self._gddh_build_groups_for_season(gddh, win["season_id"])
        targets = self._gddh_build_targets(gddh, rank_list)
        self.save()
        return {
            "GddhRankTargetList": targets,
            "LastRefreshTime": int(gddh["last_refresh_time"]),
        }

    def _rpc_gddh_rank_fight(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        win = self._gddh_season_window()
        gddh = self._gddh_state()
        lv = int(p.get("Lv", 1))
        if lv < 35 or int(gddh.get("is_apply", 0)) != 1 or win["is_truce"] == 1:
            self._last_rpc_context["status"] = -1
            return {}
        if not isinstance(data, list) or not data:
            self._last_rpc_context["status"] = -1
            return {}
        target_id = str(data[0])
        is_revenge = int(data[1]) if len(data) > 1 and data[1] is not None else 0

        sta_cost = int(self.game_data.get("sta_config", {}).get("perUseNum", 2))
        if int(p.get("STA", 0)) < sta_cost or int(gddh.get("rank_count", 0)) < 1:
            self._last_rpc_context["status"] = -1
            return {}

        t_pid, t_lv, t_name, t_fap, t_integ, t_head, enemies, peer = self._gddh_find_target(gddh, target_id)
        if not t_pid or t_pid == str(p["PlayerId"]):
            self._last_rpc_context["status"] = -1
            return {}

        allies = self._build_ally_fight_objs()
        fight_info = {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": sum(int(u.get("FSP", 0)) for u in allies if u), "Fap": int(p.get("FAP", 0))},
                        {"Fsp": sum(int(u.get("FSP", 0)) for u in enemies if u), "Fap": t_fap},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1, 999999),
                    "IsPVP": True,
                }
            ]
        }

        now = self.now_ts()
        cfg = self.game_data.get("gddh_config", {})
        max_atk = int(cfg.get("attckNumMax", 10))
        rec_cd = max(60, int(cfg.get("attckNumRecoverCD", 3600)))

        self.ledger.apply_player_delta(p, self.profile_name, "STA", -sta_cost, source=f"gddh_sta:{t_pid}")
        if int(gddh.get("rank_count", max_atk)) >= max_atk:
            gddh["last_recover_time"] = now + rec_cd
        gddh["rank_count"] = max(0, int(gddh.get("rank_count", max_atk)) - 1)
        gddh["per_rank_count"] = int(gddh.get("per_rank_count", 0)) + 1

        outcome = simulate_fight_info(fight_info, self.game_data["attacks"], buffs_cfg=self.game_data["combat_buffs"])
        is_win = 1 if outcome.won else 0
        self._inc_stat("gddh_fights", 1)
        self._record_daily_task_progress(6, 1)

        welfare_mult = self._gddh_welfare_mult()
        per_exp_pct = int(self.game_data.get("sta_config", {}).get("perGetEXPR", 20000))
        exp_gain = int(sta_cost * lv * (per_exp_pct / 10000.0))
        add_integral = 0
        tuples: list[tuple[int, int, int]] = [(1101, 0, exp_gain)]
        choice_cards: list[dict[str, Any]] = []
        revive_list = gddh.setdefault("revive_list", [])

        if is_win:
            self._inc_stat("gddh_wins", 1)
            add_r = int(cfg.get("valueAddR", 500))
            cut_r = int(cfg.get("valueCutR", 200))
            add_integral = max(20, int(round(t_integ * add_r / 10000.0)))
            cut_integral = max(10, int(round(t_integ * cut_r / 10000.0)))
            gddh["integral"] = int(gddh.get("integral", 1000)) + add_integral

            if peer is not None:
                with peer._lock:
                    pg = peer._gddh_ensure_state_dict()
                    pg["integral"] = max(0, int(pg.get("integral", 1000)) - cut_integral)
                    peer_rev = [r for r in pg.setdefault("revive_list", []) if r.get("RankPlayerId") != str(p["PlayerId"])]
                    peer_rev.insert(
                        0,
                        {
                            "RankPlayerId": str(p["PlayerId"]),
                            "RankHeadImageId": int(p.get("HeadImageId", 12011004)),
                            "FashionModelId": int(p.get("FashionModelId", 0)),
                            "RankLv": lv,
                            "RankName": str(p.get("PlayerName", "Adventurer")),
                            "RankFAP": int(p.get("FAP", 0)),
                        },
                    )
                    pg["revive_list"] = peer_rev[:20]
                    if hasattr(peer, "_push_player_email"):
                        peer._push_player_email(
                            2,
                            "Chiến báo Đấu Võ Đại Hội",
                            f"{p.get('PlayerName', 'Đối thủ')} đã đánh bại bạn tại Đấu Võ Đại Hội (-{cut_integral} điểm).",
                            send_player_id=str(p["PlayerId"]),
                            send_player_name=str(p.get("PlayerName", "Đối thủ")),
                            sub_module_id=2503,
                            head_image_id=0,
                            fashion_model_id=0,
                        )
                    peer.save()
            else:
                gddh.setdefault("bot_integrals", {})[t_pid] = max(0, t_integ - cut_integral)

            coin_gain = int(cfg.get("GDDHCoinAdd", 2)) * welfare_mult
            gold_gain = (2000 + lv * 60) * welfare_mult
            tuples.extend([(1112, 0, gold_gain), (1119, 0, coin_gain), (1605, 16050001, 5)])
            choice_cards = [
                {"ResourceTypeSub": 1605, "ModelId": 16050001, "Num": 5, "IsDrop": 1},
                {"ResourceTypeSub": 1112, "ModelId": 0, "Num": 8000, "IsDrop": 0},
                {"ResourceTypeSub": 1119, "ModelId": 0, "Num": coin_gain, "IsDrop": 0},
            ]
            if is_revenge == 1:
                gddh["revive_list"] = [r for r in revive_list if r.get("RankPlayerId") != t_pid]
        else:
            gold_gain = (800 + lv * 25) * welfare_mult
            tuples.append((1112, 0, gold_gain))
            rev_entry = {
                "RankPlayerId": t_pid,
                "RankHeadImageId": t_head,
                "FashionModelId": 0,
                "RankLv": t_lv,
                "RankName": t_name,
                "RankFAP": t_fap,
            }
            new_rev = [r for r in revive_list if r.get("RankPlayerId") != t_pid]
            new_rev.insert(0, rev_entry)
            gddh["revive_list"] = new_rev[:20]

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"gddh_fight:{t_pid}:{'win' if is_win else 'lose'}",
            tx_prefix=f"gddh:{self.profile_name}:{t_pid}:{uuid.uuid4()}",
        )
        old_lv2, new_lv2 = self._sync_level_from_exp()
        if new_lv2 != old_lv2:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True

        if is_revenge == 0:
            gddh["refresh_seed"] = int(gddh.get("refresh_seed", 0)) + 1

        rank_list = self._gddh_build_groups_for_season(gddh, win["season_id"])
        gid = int(gddh.get("group_id", 1))
        gname = ("One", "Two", "Three", "Four")[max(0, min(3, gid - 1))]
        new_rank = next((int(e["Rank"]) for e in rank_list[gname] if e["PlayerId"] == str(p["PlayerId"])), 0)
        if 0 < new_rank < int(gddh.get("history_rank", _UNAVAILABLE_RANK)):
            gddh["history_rank"] = new_rank

        rec_ts = now if int(gddh["rank_count"]) >= max_atk else max(now, int(gddh.get("last_recover_time", now)))
        self.save()
        out: dict[str, Any] = {
            "IsWinFight": is_win,
            "AddIntegral": add_integral,
            "Integral": int(gddh.get("integral", 1000)),
            "Rank": new_rank,
            "HistortRank": int(gddh.get("history_rank", _UNAVAILABLE_RANK)),
            "RankCount": int(gddh["rank_count"]),
            "PerRankCount": int(gddh["per_rank_count"]),
            "LastRecoveTime": rec_ts,
            "GDDHCoin": int(p.get("GDDHCoin", 0)),
            "FightInfo": fight_info,
            "BaseGetGameResourceList": base_res,
            "ChoiceGetGameResource": choice_cards,
            "GddhReviveList": list(gddh.get("revive_list", [])),
            "GddhRankList": rank_list,
        }
        if is_revenge == 0:
            out["GddhRankTargetList"] = self._gddh_build_targets(gddh, rank_list)
        return out

    def _rpc_gddh_buy_rank_count(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        win = self._gddh_season_window()
        gddh = self._gddh_state()
        if int(p.get("Lv", 1)) < 35 or int(gddh.get("is_apply", 0)) != 1 or win["is_truce"] == 1:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            count = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}
        if count < 1 or count > 99:
            self._last_rpc_context["status"] = -1
            return {}

        buy_tbl = self.game_data.get("gddh_buynum", {})
        max_key = max((int(k) for k in buy_tbl), default=30)
        prev_bought = int(gddh.get("buy_rank_count", 0))
        cost = 0
        for step in range(1, count + 1):
            idx = min(max_key, prev_bought + step)
            cost += int(buy_tbl.get(str(idx), {"price": 30}).get("price", 30))

        if int(p.get("Diamond", 0)) < cost:
            self._last_rpc_context["status"] = -1105
            return {}
        if cost > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -cost, source=f"gddh_buy_count:{count}")

        now = self.now_ts()
        cfg = self.game_data.get("gddh_config", {})
        max_atk = int(cfg.get("attckNumMax", 10))
        gddh["buy_rank_count"] = prev_bought + count
        gddh["rank_count"] = int(gddh.get("rank_count", 0)) + count
        if int(gddh["rank_count"]) >= max_atk:
            gddh["last_recover_time"] = now
        self.save()
        return {
            "BuyRankCount": int(gddh["buy_rank_count"]),
            "RankCount": int(gddh["rank_count"]),
            "LastRecoveTime": max(now, int(gddh.get("last_recover_time", now))),
        }

    def _rpc_gddh_receive_reward(self, data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < 35:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            milestone = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}

        row = self.game_data.get("gddh_attack_reward", {}).get(str(milestone))
        if not row:
            self._last_rpc_context["status"] = -1
            return {}
        gddh = self._gddh_state()
        claimed = gddh.setdefault("claimed_attack_rewards", [])
        if int(gddh.get("per_rank_count", 0)) < milestone or milestone in claimed:
            self._last_rpc_context["status"] = -1
            return {}

        tuples = _parse_res_tuples(str(row.get("reward", "")))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"gddh_attack_reward:{milestone}",
            tx_prefix=f"gddhatk:{self.profile_name}:{gddh['day']}:{milestone}",
        )
        claimed.append(milestone)
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_gddh_get_revive_list(self, _data: Any) -> list[dict[str, Any]]:
        win = self._gddh_season_window()
        if int(self.state["player"].get("Lv", 1)) < 35 or win["is_truce"] == 1:
            return []
        gddh = self._gddh_state()
        return list(gddh.get("revive_list", []))

    # -------------------- 2 GddhShop RPCs --------------------

    def _gddh_shop_sync_maps(self, gddh: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
        today = self.clock.today_str()
        daily_map = gddh.setdefault("shop_bought_daily", {})
        if daily_map.get("_date") != today:
            daily_map.clear()
            daily_map["_date"] = today
        season_id = str(gddh.get("season_id", self._gddh_season_window()["season_id"]))
        season_map = gddh.setdefault("shop_bought_season", {})
        if season_map.get("_season") != season_id:
            season_map.clear()
            season_map["_season"] = season_id
        total_map = gddh.setdefault("shop_bought_total", {})
        return daily_map, season_map, total_map

    def _rpc_gddh_shop_info(self, _data: Any) -> list[dict[str, Any]]:
        gddh = self._gddh_state()
        daily_map, season_map, total_map = self._gddh_shop_sync_maps(gddh)
        rows = sorted(self.game_data.get("gddh_shop", {}).values(), key=lambda x: int(x["ID"]))
        out: list[dict[str, Any]] = []
        for row in rows:
            sid = int(row["ID"])
            out.append(
                {
                    "ShopId": sid,
                    "TypeId": int(row["typeID"]),
                    "ModelId": int(row["modelID"]),
                    "Num": int(row["num"]),
                    "NeedGDDHCoin": int(row["needGDDHCoin"]),
                    "NeedLv": int(row.get("needLV", 1)),
                    "PerMaxNum": int(row.get("perMaxNum", 0)),
                    "SeasonMaxNum": int(row.get("seasonMaxNum", 0)),
                    "TotalMaxNum": int(row.get("totalMaxNum", 0)),
                    "BuyNum": int(daily_map.get(str(sid), 0)),
                    "BuySeasonNum": int(season_map.get(str(sid), 0)),
                    "BuyTotalNum": int(total_map.get(str(sid), 0)),
                }
            )
        return out

    def _rpc_gddh_shop_buy(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        try:
            shop_id = int(data[0])
            num = max(1, int(data[1]))
        except (TypeError, ValueError):
            self._last_rpc_context["status"] = -1
            return {}

        row = self.game_data.get("gddh_shop", {}).get(str(shop_id))
        if not row:
            self._last_rpc_context["status"] = -1
            return {}

        p = self.state["player"]
        gddh = self._gddh_state()
        lv = int(p.get("Lv", 1))
        need_lv = int(row.get("needLV", 1))
        need_rank = int(row.get("needRank", 0))
        hist_rank = int(gddh.get("history_rank", _UNAVAILABLE_RANK))
        if lv < need_lv or (need_rank > 0 and (hist_rank <= 0 or hist_rank > need_rank)):
            self._last_rpc_context["status"] = -1
            return {}

        daily_map, season_map, total_map = self._gddh_shop_sync_maps(gddh)
        cur_daily = int(daily_map.get(str(shop_id), 0))
        cur_season = int(season_map.get(str(shop_id), 0))
        cur_total = int(total_map.get(str(shop_id), 0))
        per_max = int(row.get("perMaxNum", 0))
        season_max = int(row.get("seasonMaxNum", 0))
        tot_max = int(row.get("totalMaxNum", 0))
        if per_max > 0 and cur_daily + num > per_max:
            self._last_rpc_context["status"] = -1
            return {}
        if season_max > 0 and cur_season + num > season_max:
            self._last_rpc_context["status"] = -1
            return {}
        if tot_max > 0 and cur_total + num > tot_max:
            self._last_rpc_context["status"] = -1
            return {}

        cost = int(row.get("needGDDHCoin", 0)) * num
        if int(p.get("GDDHCoin", 0)) < cost:
            self._last_rpc_context["status"] = -1
            return {}
        if cost > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "GDDHCoin", -cost, source=f"gddh_shop:{shop_id}")

        daily_map[str(shop_id)] = cur_daily + num
        season_map[str(shop_id)] = cur_season + num
        total_map[str(shop_id)] = cur_total + num

        base_res = self._grant_resources_from_tuples(
            [(int(row["typeID"]), int(row["modelID"]), int(row["num"]) * num)],
            source=f"gddh_shop_buy:{shop_id}",
            tx_prefix=f"gddh_shop:{self.profile_name}:{shop_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}
