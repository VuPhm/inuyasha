"""Bang Hội cục bộ S1 (`Guild` 30 RPC + `GuildBossInfo` 6 RPC + `GuildReward` 2 RPC = 38 RPC)."""

from __future__ import annotations

import copy
import json
import os
import random
import threading
import uuid
from pathlib import Path
from typing import Any

from combat_sim import simulate_fight_info
from r79_event_handlers import _parse_res_tuples

EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"
GUILD_POST_LEADER = 34001001
GUILD_POST_VICE = 34001002
GUILD_POST_ELITE = 34001003
GUILD_POST_MEMBER = 34001004
GUILD_HALL_ID = 34004000
GUILD_SHOP_ID = 34005000
GUILD_BOSS_ID = 34008000
GUILD_BUILDING_ORDER: tuple[int, ...] = (GUILD_HALL_ID, GUILD_SHOP_ID, GUILD_BOSS_ID)
GUILD_POST_CAPS: dict[int, int] = {
    GUILD_POST_VICE: 2,
    GUILD_POST_ELITE: 5,
}
GUILD_MERC_DAILY_HIRE_MAX = 5

_REGISTRY_LOCKS_GUARD = threading.Lock()
_REGISTRY_LOCKS: dict[str, threading.RLock] = {}
_MEM_REGISTRIES: dict[int, dict[str, Any]] = {}


def _det_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"inuyasha.revival.{seed}"))


def _registry_lock(key: str) -> threading.RLock:
    with _REGISTRY_LOCKS_GUARD:
        lock = _REGISTRY_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _REGISTRY_LOCKS[key] = lock
        return lock


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


class GuildHandlersMixin:
    """Offline S1 Guild, GuildBossInfo, and GuildReward RPC handlers."""

    # -------------------- State & Registry Storage --------------------

    @staticmethod
    def _ensure_player_guild_container(state: dict[str, Any]) -> dict[str, Any]:
        g = state.setdefault("guild", {})
        g.setdefault("guild_id", EMPTY_ENTITY_ID)
        g.setdefault("day", "")
        g.setdefault("built_today", False)
        g.setdefault("shared_today", False)
        g.setdefault("share_id", "")
        g.setdefault("share_time", 0)
        g.setdefault("fund_total", 0)
        g.setdefault("rejoin_cd_time", 0)
        g.setdefault("shop_daily", {})
        g.setdefault("shop_total", {})
        g.setdefault("boss_fight_count", 0)
        g.setdefault("rewards", [])
        return g

    def _guild_registry_target(self) -> tuple[str, Path | None]:
        acct_mgr = getattr(self, "account_manager", None)
        if getattr(self, "persist", False):
            if getattr(acct_mgr, "data_dir", None) is not None:
                path = Path(acct_mgr.data_dir) / "s1_guilds.json"
                return f"file:{path.resolve()}", path
            if getattr(self, "state_path", None) is not None:
                path = Path(self.state_path).parent / "s1_guilds.json"
                return f"file:{path.resolve()}", path
        host = acct_mgr or self
        return f"mem:{id(host)}", None

    def _guild_cfg(self) -> dict[str, Any]:
        return self.game_data.get("guild_config", {})

    def _guild_member_max(self, lv: int) -> int:
        lv_tbl = self.game_data.get("guild_lv", {})
        clamped = max(1, min(30, int(lv)))
        row = lv_tbl.get(str(clamped)) or {}
        return max(20, int(row.get("memberNumMax", 20)))

    def _guild_seed_npc_share(self, guild_id: str, owner_pid: str, owner_name: str, hero_model_id: int, lv: int, fap: int) -> dict[str, Any]:
        share_id = _det_uuid(f"npc_guild_share:{guild_id}:{owner_pid}")
        return {
            "ShareId": share_id,
            "PlayerId": owner_pid,
            "PlayerName": owner_name,
            "HeroModelId": int(hero_model_id),
            "Lv": int(lv),
            "Step": 4,
            "FAP": int(fap),
            "FSP": 120,
            "HP": max(8000, int(fap * 0.45)),
            "AP": max(1200, int(fap * 0.03)),
            "DEF": max(600, int(fap * 0.02)),
            "ShareTime": self.now_ts(),
            "HireCount": 0,
        }

    def _seed_default_guilds(self, reg: dict[str, Any], today: str, week_key: str) -> None:
        seeds = (
            ("npc_guild_1", "Tây Quốc", "Hội Tứ Quốc S1 hoan nghênh tân thủ và cao thủ cùng tham gia.", 3, 2, "Sát Sinh Hoàn", 12011005, 42, 165000),
            ("npc_guild_2", "Hội Trừ Yêu", "Cùng săn Yêu Vương, xây dựng công hội mỗi ngày.", 3, 2, "San Hô", 12011007, 40, 148000),
            ("npc_guild_3", "Bạch Linh Sơn", "Bang hội hòa đồng, mở lính thuê & boss bang hằng ngày.", 4, 3, "Nại Lạc", 12013004, 46, 192000),
        )
        guilds = reg.setdefault("guilds", {})
        now = self.now_ts()
        for key, name, decl, lv, boss_lv, leader_name, merc_hm, merc_lv, merc_fap in seeds:
            gid = _det_uuid(key)
            if gid in guilds:
                continue
            leader_pid = _det_uuid(f"{key}:leader")
            vice_pid = _det_uuid(f"{key}:vice")
            members = {
                leader_pid: {
                    "Id": leader_pid,
                    "Name": leader_name,
                    "Lv": merc_lv,
                    "FAP": merc_fap,
                    "PostId": GUILD_POST_LEADER,
                    "FundTotal": 12000 * lv,
                    "HeadImageId": merc_hm,
                    "FashionModelId": 0,
                    "LastActiveTime": now,
                    "JoinedAt": now - 86400 * 7,
                    "IsNpc": True,
                },
                vice_pid: {
                    "Id": vice_pid,
                    "Name": f"Phó {name}",
                    "Lv": max(30, merc_lv - 3),
                    "FAP": int(merc_fap * 0.85),
                    "PostId": GUILD_POST_VICE,
                    "FundTotal": 6000 * lv,
                    "HeadImageId": 12011004,
                    "FashionModelId": 0,
                    "LastActiveTime": now,
                    "JoinedAt": now - 86400 * 5,
                    "IsNpc": True,
                },
            }
            guilds[gid] = {
                "id": gid,
                "name": name,
                "lv": lv,
                "guild_fund": 20000 * lv,
                "guild_fund_total": 35000 * lv,
                "guild_fund_week": 8000 * lv,
                "notice": f"Chào mừng đến với {name}!",
                "declaration": decl,
                "is_auto_apply": 1,
                "fap_limit": 0,
                "day": today,
                "week": week_key,
                "build_count_today": 0,
                "buildings": {
                    str(GUILD_HALL_ID): lv,
                    str(GUILD_SHOP_ID): lv,
                    str(GUILD_BOSS_ID): boss_lv,
                },
                "members": members,
                "applies": [],
                "build_logs": [],
                "news": [],
                "shares": {
                    leader_pid: self._guild_seed_npc_share(gid, leader_pid, leader_name, merc_hm, merc_lv, merc_fap),
                },
                "boss_inspire_time": 0,
                "boss_total_score": 0,
                "boss_member_scores": {},
                "is_npc": True,
            }

    def _with_guild_registry(self, mutator: Any) -> Any:
        lock_key, path = self._guild_registry_target()
        lock = _registry_lock(lock_key)
        with lock:
            if path is not None:
                reg = _read_json_file(path)
            else:
                host_id = id(getattr(self, "account_manager", None) or self)
                reg = _MEM_REGISTRIES.setdefault(host_id, {})

            dt = self.clock.dt()
            today = self.clock.today_str()
            iso_y, iso_w, _ = dt.isocalendar()
            week_key = f"{iso_y}-W{iso_w:02d}"
            reg_changed = False
            if not reg.get("seeded"):
                self._seed_default_guilds(reg, today, week_key)
                reg["seeded"] = True
                reg_changed = True

            guilds = reg.setdefault("guilds", {})
            for g in guilds.values():
                if g.get("day") != today:
                    g["day"] = today
                    g["build_count_today"] = 0
                    g["boss_inspire_time"] = 0
                    g["boss_total_score"] = 0
                    g["boss_member_scores"] = {}
                    # Keep NPC shares fresh daily, clear human member daily shares.
                    new_shares: dict[str, Any] = {}
                    for pid, srow in list(g.get("shares", {}).items()):
                        m = g.get("members", {}).get(pid)
                        if m and m.get("IsNpc"):
                            refreshed = dict(srow)
                            refreshed["HireCount"] = 0
                            refreshed["ShareTime"] = self.now_ts()
                            new_shares[pid] = refreshed
                    g["shares"] = new_shares
                    reg_changed = True
                if g.get("week") != week_key:
                    g["week"] = week_key
                    g["guild_fund_week"] = 0
                    reg_changed = True

            dirty_hint: list[bool] = []
            result = mutator(reg, dirty_hint)
            if dirty_hint or reg_changed:
                if path is not None:
                    _write_json_atomic(path, reg)
            return result

    def _sync_guild_state(self) -> bool:
        """Roll daily player guild state and reconcile membership against registry."""
        pg = self._ensure_player_guild_container(self.state)
        p = self.state["player"]
        my_pid = str(p["PlayerId"])
        changed = False
        today = self.clock.today_str()

        if pg.get("day") != today:
            pg["day"] = today
            pg["built_today"] = False
            pg["shared_today"] = False
            pg["share_id"] = ""
            pg["share_time"] = 0
            pg["shop_daily"] = {}
            pg["boss_fight_count"] = 0
            changed = True

        gid = str(pg.get("guild_id") or p.get("GuildId") or EMPTY_ENTITY_ID)
        if gid and gid != EMPTY_ENTITY_ID:
            def _check_member(reg: dict[str, Any], dirty: list[bool]) -> tuple[bool, str, int, int]:
                g = reg["guilds"].get(gid)
                if not g or my_pid not in g.get("members", {}):
                    return False, "", GUILD_POST_MEMBER, 0
                m = g["members"][my_pid]
                now = self.now_ts()
                new_name = str(p.get("PlayerName", m.get("Name", "")))
                new_lv = int(p.get("Lv", 1))
                new_fap = int(p.get("FAP", 0))
                new_head = self._valid_hero_head_id(int(p.get("HeadImageId", 0)), self.state.get("slots", []))
                new_fashion = int(p.get("FashionModelId", 0))
                meta_changed = (
                    m.get("Name") != new_name
                    or int(m.get("Lv", 0)) != new_lv
                    or int(m.get("FAP", 0)) != new_fap
                    or int(m.get("HeadImageId", 0)) != new_head
                    or int(m.get("FashionModelId", 0)) != new_fashion
                )
                if meta_changed or (now - int(m.get("LastActiveTime", 0))) >= 60:
                    m["Name"] = new_name
                    m["Lv"] = new_lv
                    m["FAP"] = new_fap
                    m["HeadImageId"] = new_head
                    m["FashionModelId"] = new_fashion
                    m["LastActiveTime"] = now
                    dirty.append(True)
                return True, str(g["name"]), int(m.get("PostId", GUILD_POST_MEMBER)), int(m.get("FundTotal", 0))

            in_guild, gname, post_id, fund_tot = self._with_guild_registry(_check_member)
            if not in_guild:
                pg["guild_id"] = EMPTY_ENTITY_ID
                p["GuildId"] = EMPTY_ENTITY_ID
                p["GuildName"] = ""
                changed = True
            else:
                if pg.get("guild_id") != gid or p.get("GuildId") != gid or p.get("GuildName") != gname:
                    pg["guild_id"] = gid
                    p["GuildId"] = gid
                    p["GuildName"] = gname
                    changed = True
                if int(pg.get("fund_total", 0)) < fund_tot:
                    pg["fund_total"] = fund_tot
                    changed = True
        else:
            if p.get("GuildId") != EMPTY_ENTITY_ID or p.get("GuildName") != "":
                p["GuildId"] = EMPTY_ENTITY_ID
                p["GuildName"] = ""
                changed = True
        return changed

    # -------------------- Permissions, Ordering & Payloads --------------------

    def _guild_has_auth(self, post_id: int, auth_id: int) -> bool:
        row = self.game_data.get("guild_posts", {}).get(str(post_id), {})
        auth_raw = str(row.get("authIDList", ""))
        auths = {int(tok.strip()) for tok in auth_raw.split(",") if tok.strip().isdigit()}
        return auth_id in auths

    def _guild_rank_order(self, reg: dict[str, Any], guild_id: str) -> int:
        ordered = sorted(
            reg["guilds"].values(),
            key=lambda g: (-int(g.get("lv", 1)), -int(g.get("guild_fund_total", 0)), str(g["id"])),
        )
        for idx, g in enumerate(ordered, start=1):
            if g["id"] == guild_id:
                return idx
        return 1

    def _guild_card_dict(self, reg: dict[str, Any], g: dict[str, Any], rank_num: int | None = None) -> dict[str, Any]:
        leader = next((m for m in g.get("members", {}).values() if int(m.get("PostId", 0)) == GUILD_POST_LEADER), None)
        leader_name = str(leader["Name"]) if leader else ""
        return {
            "Id": str(g["id"]),
            "Name": str(g["name"]),
            "Lv": int(g.get("lv", 1)),
            "GuildFund": int(g.get("guild_fund", 0)),
            "GuildFundTotal": int(g.get("guild_fund_total", 0)),
            "GuildFundWeek": int(g.get("guild_fund_week", 0)),
            "Notice": str(g.get("notice", "")),
            "Declaration": str(g.get("declaration", "")),
            "GuildBuildCount": int(g.get("build_count_today", 0)),
            "LeaderName": leader_name,
            "MemberCount": len(g.get("members", {})),
            "RandNum": int(rank_num if rank_num is not None else self._guild_rank_order(reg, str(g["id"]))),
            "IsAutoApply": int(g.get("is_auto_apply", 0)),
            "FapLimit": int(g.get("fap_limit", 0)),
        }

    def _guild_ordered_buildings(self, g: dict[str, Any]) -> list[dict[str, int]]:
        bmap = g.get("buildings", {})
        # GuildShopLayer.lua indexes index 2 (1-based) for Shop -> keep (Hall, Shop, Boss) order.
        return [{"BuildingId": bid, "Lv": int(bmap.get(str(bid), 1))} for bid in GUILD_BUILDING_ORDER]

    def _guild_can_upgrade_any_building(self, g: dict[str, Any]) -> int:
        bmap = g.get("buildings", {})
        hall_lv = int(bmap.get(str(GUILD_HALL_ID), 1))
        fund = int(g.get("guild_fund", 0))
        lv_rel = self.game_data.get("guild_building_lv", {})
        for bid in GUILD_BUILDING_ORDER:
            cur_lv = int(bmap.get(str(bid), 1))
            if bid != GUILD_HALL_ID and cur_lv >= hall_lv:
                continue
            tbl = lv_rel.get(str(bid), {})
            cur_row = tbl.get(str(cur_lv))
            nxt_row = tbl.get(str(cur_lv + 1))
            if not cur_row or not nxt_row:
                continue
            cost = max(0, int(nxt_row.get("totalExp", 0)) - int(cur_row.get("totalExp", 0)))
            if fund >= cost:
                return 1
        return 0

    def _guild_post_lack(self, g: dict[str, Any]) -> int:
        vice_cnt = sum(1 for m in g.get("members", {}).values() if int(m.get("PostId", 0)) == GUILD_POST_VICE)
        return 1 if vice_cnt < GUILD_POST_CAPS[GUILD_POST_VICE] and len(g.get("members", {})) > 1 else 0

    def _guild_info_payload(self, reg: dict[str, Any], g: dict[str, Any], my_pid: str) -> dict[str, Any]:
        pg = self._ensure_player_guild_container(self.state)
        me = g.get("members", {}).get(my_pid, {})
        post_id = int(me.get("PostId", GUILD_POST_MEMBER))
        has_apply = 1 if g.get("applies") else 0
        can_bup = self._guild_can_upgrade_any_building(g)
        post_lack = self._guild_post_lack(g)
        return {
            "PlayerGuildInfo": {
                "FundTotal": int(pg.get("fund_total", me.get("FundTotal", 0))),
                "IfCanBuildTime": 0 if pg.get("built_today") else 1,
                "IfCanShare": 0 if pg.get("shared_today") else 1,
                "PostId": post_id,
            },
            "GuildInfo": self._guild_card_dict(reg, g),
            "GuildBuildInfo": self._guild_ordered_buildings(g),
            "GlobalGuildNewsInfo": list(g.get("news", [])[:20]),
            "GlobalGuildRedInfo": {
                "ApplyList": has_apply,
                "PostLack": post_lack,
                "BuildingLv": can_bup,
            },
        }

    def _emit_guild_avatar(self, g: dict[str, Any], my_pid: str, *, news_items: list[dict[str, Any]] | None = None) -> None:
        me = g.get("members", {}).get(my_pid, {})
        post_id = int(me.get("PostId", GUILD_POST_MEMBER))
        bmap = g.get("buildings", {})
        self._last_rpc_context["guild_avatar"] = {
            "Fund": int(g.get("guild_fund", 0)),
            "FundTotal": int(g.get("guild_fund_total", 0)),
            "MemberCount": len(g.get("members", {})),
            "GuildBuildCount": int(g.get("build_count_today", 0)),
            "PostId": post_id,
            "Notice": str(g.get("notice", "")),
            "Declaration": str(g.get("declaration", "")),
            "BuildLv": {str(bid): int(bmap.get(str(bid), 1)) for bid in GUILD_BUILDING_ORDER},
            "GuildNews": news_items or [],
            "IfApplyList": 1 if g.get("applies") else 0,
            "IfPostLack": self._guild_post_lack(g),
            "IfBuildingLv": self._guild_can_upgrade_any_building(g),
        }

    @staticmethod
    def _guild_append_news(g: dict[str, Any], content: str) -> dict[str, Any]:
        news = g.setdefault("news", [])
        next_id = max((int(n.get("Id", 0)) for n in news), default=0) + 1
        item = {"Id": next_id, "Content": str(content)}
        news.insert(0, item)
        if len(news) > 30:
            del news[30:]
        return item

    def _guild_reject(self, status: int) -> Any:
        self._last_rpc_context["status"] = int(status)
        return {}

    def _set_player_guild_link(self, guild_id: str, guild_name: str, *, set_cd: bool = False) -> None:
        pg = self._ensure_player_guild_container(self.state)
        pg["guild_id"] = str(guild_id)
        if set_cd:
            cd_sec = int(self._guild_cfg().get("reJoinGuildCD", 0))
            pg["rejoin_cd_time"] = (self.now_ts() + cd_sec) if cd_sec > 0 else 0
        self.state["player"]["GuildId"] = str(guild_id)
        self.state["player"]["GuildName"] = str(guild_name)

    def _clear_peer_guild_link(self, target_pid: str, *, set_cd: bool = False) -> None:
        peer = self._find_peer_by_player_id(target_pid)
        if peer is not None:
            with peer._lock:
                peer._set_player_guild_link(EMPTY_ENTITY_ID, "", set_cd=set_cd)
                peer.save()

    # -------------------- Cross-System & Red-Dot Helpers --------------------

    def _guild_red_dot(self) -> int:
        if int(self.state.get("player", {}).get("Lv", 1)) < 27:
            return 0
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        if not gid or gid == EMPTY_ENTITY_ID:
            return 0

        def _check(reg: dict[str, Any], _dirty: list[bool]) -> int:
            g = reg["guilds"].get(gid)
            if not g:
                return 0
            my_pid = str(self.state["player"]["PlayerId"])
            me = g.get("members", {}).get(my_pid)
            if not me:
                return 0
            post_id = int(me.get("PostId", GUILD_POST_MEMBER))
            need_build_lv = int(self._guild_cfg().get("buildNeedGuildLv", 3))
            can_build = not pg.get("built_today") and int(g.get("lv", 1)) >= need_build_lv
            can_share = not pg.get("shared_today") and int(self.state["player"].get("Lv", 1)) >= int(self._guild_cfg().get("shareNeedLV", 23))
            can_mgr = (self._guild_has_auth(post_id, 4) and len(g.get("applies", [])) > 0) or (
                self._guild_has_auth(post_id, 2) and self._guild_can_upgrade_any_building(g) == 1
            )
            return 1 if (can_build or can_share or can_mgr) else 0

        return int(self._with_guild_registry(_check))

    def _guild_reward_red_dot(self) -> int:
        if int(self.state.get("player", {}).get("Lv", 1)) < 27:
            return 0
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        if not gid or gid == EMPTY_ENTITY_ID:
            return 0
        return 1 if len(pg.get("rewards", [])) > 0 else 0

    def _guild_boss_red_dot(self) -> int:
        if int(self.state.get("player", {}).get("Lv", 1)) < 27:
            return 0
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        if not gid or gid == EMPTY_ENTITY_ID:
            return 0
        max_atk = int(self._guild_cfg().get("bossBattleNum", 2))
        if int(pg.get("boss_fight_count", 0)) >= max_atk:
            return 0
        return 1 if self._guild_boss_in_window() else 0

    def _guild_boss_in_window(self) -> bool:
        cfg = self._guild_cfg()
        start_f = float(cfg.get("bossStartTime", 0))
        end_f = float(cfg.get("bossEndTime", 0.979166666667))
        dt = self.clock.dt()
        frac = (dt.hour * 3600 + dt.minute * 60 + dt.second) / 86400.0
        return start_f <= frac <= end_f

    def _guild_get_shared_hero(self, owner_or_share_id: str, hero_model_id: int) -> dict[str, Any] | None:
        """Resolve an active Guild Mercenary matching owner PlayerId or ShareId + HeroModelId."""
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        if not gid or gid == EMPTY_ENTITY_ID:
            return None

        def _find(reg: dict[str, Any], _dirty: list[bool]) -> dict[str, Any] | None:
            g = reg["guilds"].get(gid)
            if not g:
                return None
            for s in g.get("shares", {}).values():
                if int(s.get("HeroModelId", 0)) != int(hero_model_id):
                    continue
                if str(s.get("PlayerId", "")) == str(owner_or_share_id) or str(s.get("ShareId", "")) == str(owner_or_share_id):
                    return copy.deepcopy(s)
            return None

        return self._with_guild_registry(_find)

    def _guild_record_merc_hired(self, owner_pid: str, hero_model_id: int) -> tuple[bool, int]:
        """Increment mercenary HireCount and grant owner GuildConfig.perMercenaryBeUseReward."""
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        if not gid or gid == EMPTY_ENTITY_ID:
            return False, -3425

        def _inc(reg: dict[str, Any], dirty: list[bool]) -> tuple[bool, int]:
            g = reg["guilds"].get(gid)
            if not g:
                return False, -3425
            s = g.get("shares", {}).get(str(owner_pid))
            if not s or int(s.get("HeroModelId", 0)) != int(hero_model_id):
                return False, -1
            if int(s.get("HireCount", 0)) >= GUILD_MERC_DAILY_HIRE_MAX:
                return False, -3426
            s["HireCount"] = int(s.get("HireCount", 0)) + 1
            dirty.append(True)
            return True, 0

        ok, err = self._with_guild_registry(_inc)
        if not ok:
            return False, err

        reward_raw = str(self._guild_cfg().get("perMercenaryBeUseReward", "1103,0,1"))
        tuples = _parse_res_tuples(reward_raw)
        if tuples:
            if str(owner_pid) == str(self.state["player"]["PlayerId"]):
                self._grant_resources_from_tuples(
                    tuples,
                    source=f"guild_merc_use:{hero_model_id}",
                    tx_prefix=f"merc_use:{self.profile_name}:{uuid.uuid4()}",
                )
            else:
                peer = self._find_peer_by_player_id(str(owner_pid))
                if peer is not None:
                    with peer._lock:
                        peer._grant_resources_from_tuples(
                            tuples,
                            source=f"guild_merc_use:{hero_model_id}",
                            tx_prefix=f"merc_use:{peer.profile_name}:{uuid.uuid4()}",
                        )
                        peer.save()
        return True, 0

    def _guild_teammate_candidates(self, in_team_ids: set[str]) -> list[dict[str, Any]]:
        """Return fellow Guild members eligible for TeambattleInfo GuildPlayer list."""
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        if not gid or gid == EMPTY_ENTITY_ID:
            return []
        my_pid = str(self.state["player"]["PlayerId"])

        def _list(reg: dict[str, Any], _dirty: list[bool]) -> list[dict[str, Any]]:
            g = reg["guilds"].get(gid)
            if not g:
                return []
            out: list[dict[str, Any]] = []
            for pid, m in g.get("members", {}).items():
                if pid == my_pid or pid in in_team_ids:
                    continue
                out.append(
                    {
                        "PlayerId": str(pid),
                        "Name": str(m.get("Name", "")),
                        "Lv": int(m.get("Lv", 1)),
                        "FAP": int(m.get("FAP", 0)),
                        "HeadImageId": int(m.get("HeadImageId", 12011004)),
                    }
                )
            return out

        return self._with_guild_registry(_list)

    def _guild_member_lookup(self, target_pid: str) -> dict[str, Any] | None:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        if not gid or gid == EMPTY_ENTITY_ID:
            return None

        def _find(reg: dict[str, Any], _dirty: list[bool]) -> dict[str, Any] | None:
            g = reg["guilds"].get(gid)
            if not g:
                return None
            m = g.get("members", {}).get(str(target_pid))
            return dict(m) if m else None

        return self._with_guild_registry(_find)

    def _push_guild_reward(self, title: str, res_tuples: list[tuple[int, int, int]], *, source_key: str = "") -> dict[str, Any]:
        pg = self._ensure_player_guild_container(self.state)
        rewards = pg.setdefault("rewards", [])
        if source_key and any(str(r.get("SourceKey", "")) == source_key for r in rewards):
            return {}
        entry = {
            "Id": str(uuid.uuid4()),
            "SourceKey": str(source_key),
            "Title": str(title),
            "CreateTime": self.now_ts(),
            # Note: GuildHomeScene.lua:1021 reads item.Count (not Num) on ResourceList entries!
            "ResourceList": [
                {"ResourceTypeSub": int(rt), "ModelId": int(rm), "Count": int(rn)}
                for rt, rm, rn in res_tuples
                if rn > 0
            ],
        }
        rewards.append(entry)
        return entry

    # -------------------- Guild Core & Membership RPCs --------------------

    def _rpc_guild_create(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if int(p.get("Lv", 1)) < 27:
            return self._guild_reject(-3449)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) != EMPTY_ENTITY_ID:
            return self._guild_reject(-3404)
        now = self.now_ts()
        if int(pg.get("rejoin_cd_time", 0)) > now:
            return self._guild_reject(-3405)

        name = str(data[0]).strip() if isinstance(data, list) and len(data) >= 1 and data[0] is not None else ""
        decl = str(data[1]).strip() if isinstance(data, list) and len(data) >= 2 and data[1] is not None else ""
        min_len = int(self.game_data.get("player_config", {}).get("playerNameMinLength", 2))
        max_len = int(self.game_data.get("player_config", {}).get("playerNameMaxLength", 32))
        if len(name) < min_len or len(name) > max_len:
            return self._guild_reject(-1)
        if not decl:
            decl = "Chiến đấu hết mình vì Công Hội!"

        costs = _parse_res_tuples(str(self._guild_cfg().get("createGuildUseResource", "1111,0,100||1112,0,500000")))
        dia_need = sum(rn for rt, _, rn in costs if rt == 1111)
        gold_need = sum(rn for rt, _, rn in costs if rt == 1112)
        if int(p.get("Diamond", 0)) < dia_need or int(p.get("Gold", 0)) < gold_need:
            return self._guild_reject(-1105)

        my_pid = str(p["PlayerId"])
        my_head = self._valid_hero_head_id(int(p.get("HeadImageId", 0)), self.state.get("slots", []))

        def _create_in_reg(reg: dict[str, Any], dirty: list[bool]) -> tuple[int, dict[str, Any] | None]:
            if any(str(g.get("name", "")).lower() == name.lower() for g in reg["guilds"].values()):
                return -3421, None
            gid = str(uuid.uuid4())
            today = self.clock.today_str()
            dt = self.clock.dt()
            iso_y, iso_w, _ = dt.isocalendar()
            week_key = f"{iso_y}-W{iso_w:02d}"
            g = {
                "id": gid,
                "name": name,
                "lv": 1,
                "guild_fund": 0,
                "guild_fund_total": 0,
                "guild_fund_week": 0,
                "notice": f"Chào mừng gia nhập {name}!",
                "declaration": decl[:80],
                "is_auto_apply": 0,
                "fap_limit": 0,
                "day": today,
                "week": week_key,
                "build_count_today": 0,
                "buildings": {str(GUILD_HALL_ID): 1, str(GUILD_SHOP_ID): 1, str(GUILD_BOSS_ID): 1},
                "members": {
                    my_pid: {
                        "Id": my_pid,
                        "Name": str(p.get("PlayerName", "Adventurer")),
                        "Lv": int(p.get("Lv", 1)),
                        "FAP": int(p.get("FAP", 0)),
                        "PostId": GUILD_POST_LEADER,
                        "FundTotal": 0,
                        "HeadImageId": my_head,
                        "FashionModelId": int(p.get("FashionModelId", 0)),
                        "LastActiveTime": now,
                        "JoinedAt": now,
                        "IsNpc": False,
                    }
                },
                "applies": [],
                "build_logs": [],
                "news": [{"Id": 1, "Content": f"{p.get('PlayerName', 'Tộc Trưởng')} đã thành lập Công Hội {name}!"}],
                "shares": {},
                "boss_inspire_time": 0,
                "boss_total_score": 0,
                "boss_member_scores": {},
                "is_npc": False,
            }
            reg["guilds"][gid] = g
            # Clear pending applies submitted elsewhere by this player
            for other in reg["guilds"].values():
                if other["id"] != gid and other.get("applies"):
                    other["applies"] = [a for a in other["applies"] if str(a.get("Id", "")) != my_pid]
            dirty.append(True)
            return 0, self._guild_info_payload(reg, g, my_pid)

        err, payload = self._with_guild_registry(_create_in_reg)
        if err != 0 or payload is None:
            return self._guild_reject(err)

        if dia_need > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -dia_need, source="guild_create")
        if gold_need > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Gold", -gold_need, source="guild_create")
        self._set_player_guild_link(payload["GuildInfo"]["Id"], payload["GuildInfo"]["Name"])
        pg["fund_total"] = 0
        self.save()
        return payload

    def _rpc_guild_get_info(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        if not gid or gid == EMPTY_ENTITY_ID:
            return self._guild_reject(-3425)
        my_pid = str(self.state["player"]["PlayerId"])

        def _fetch(reg: dict[str, Any], _dirty: list[bool]) -> dict[str, Any] | None:
            g = reg["guilds"].get(gid)
            if not g or my_pid not in g.get("members", {}):
                return None
            return self._guild_info_payload(reg, g, my_pid)

        payload = self._with_guild_registry(_fetch)
        if payload is None:
            return self._guild_reject(-3425)
        self.save()
        return payload

    def _browse_guilds_page(
        self,
        *,
        page_idx: int,
        ignore_full: bool = False,
        name_filter: str = "",
    ) -> dict[str, Any] | None:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) != EMPTY_ENTITY_ID:
            self._last_rpc_context["status"] = -3404
            return None
        my_pid = str(self.state["player"]["PlayerId"])
        page_size = 10

        def _list(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, dict[str, Any]]:
            all_ordered = sorted(
                reg["guilds"].values(),
                key=lambda g: (-int(g.get("lv", 1)), -int(g.get("guild_fund_total", 0)), str(g["id"])),
            )
            rank_map = {g["id"]: idx for idx, g in enumerate(all_ordered, start=1)}
            applied_cards = [
                self._guild_card_dict(reg, g, rank_map[g["id"]])
                for g in all_ordered
                if any(str(a.get("Id", "")) == my_pid for a in g.get("applies", []))
            ]
            filtered = []
            nf = name_filter.strip().lower()
            for g in all_ordered:
                if nf and nf not in str(g.get("name", "")).lower():
                    continue
                if ignore_full and len(g.get("members", {})) >= self._guild_member_max(int(g.get("lv", 1))):
                    continue
                filtered.append(self._guild_card_dict(reg, g, rank_map[g["id"]]))

            total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
            if page_idx < 0 or (filtered and page_idx >= total_pages) or (not filtered and page_idx > 0):
                return -3432, {}
            start = page_idx * page_size
            return 0, {
                "PlayerGuildInfo": {"ReJoinGuildCDTime": int(pg.get("rejoin_cd_time", 0))},
                "ApplyGuildListInfo": applied_cards,
                "GuildListInfo": filtered[start : start + page_size],
                "TotalPage": total_pages,
            }

        err, payload = self._with_guild_registry(_list)
        if err != 0:
            self._last_rpc_context["status"] = err
            return None
        return payload

    def _rpc_guild_get_apply_info(self, data: Any) -> dict[str, Any]:
        page_idx = int(data[0]) if isinstance(data, list) and len(data) >= 1 and data[0] is not None else 0
        ignore_full = bool(data[1]) if isinstance(data, list) and len(data) >= 2 else False
        out = self._browse_guilds_page(page_idx=page_idx, ignore_full=ignore_full)
        return out if out is not None else {}

    def _rpc_guild_get_apply_not_full(self, data: Any) -> dict[str, Any]:
        page_idx = int(data[0]) if isinstance(data, list) and len(data) >= 1 and data[0] is not None else 0
        out = self._browse_guilds_page(page_idx=page_idx, ignore_full=True)
        return out if out is not None else {}

    def _rpc_guild_query(self, data: Any) -> dict[str, Any]:
        query = str(data[0]) if isinstance(data, list) and len(data) >= 1 and data[0] is not None else ""
        page_idx = int(data[1]) if isinstance(data, list) and len(data) >= 2 and data[1] is not None else 0
        out = self._browse_guilds_page(page_idx=page_idx, name_filter=query)
        return out if out is not None else {}

    def _rpc_guild_get_rank_week(self, data: Any) -> dict[str, Any]:
        page_idx = int(data[0]) if isinstance(data, list) and len(data) >= 1 and data[0] is not None else 0
        page_size = 10

        def _rank(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, dict[str, Any]]:
            ordered = sorted(
                reg["guilds"].values(),
                key=lambda g: (-int(g.get("guild_fund_week", 0)), -int(g.get("guild_fund_total", 0)), -int(g.get("lv", 1)), str(g["id"])),
            )
            cards = [self._guild_card_dict(reg, g, idx) for idx, g in enumerate(ordered, start=1)]
            total_pages = max(1, (len(cards) + page_size - 1) // page_size)
            if page_idx < 0 or (cards and page_idx >= total_pages) or (not cards and page_idx > 0):
                return -3431, {}
            start = page_idx * page_size
            return 0, {"GuildRankInfoForWeek": cards[start : start + page_size], "TotalPage": total_pages}

        err, payload = self._with_guild_registry(_rank)
        if err != 0:
            return self._guild_reject(err)
        return payload

    def _rpc_guild_apply(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if int(p.get("Lv", 1)) < 27:
            return self._guild_reject(-3449)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) != EMPTY_ENTITY_ID:
            return self._guild_reject(-3404)
        now = self.now_ts()
        if int(pg.get("rejoin_cd_time", 0)) > now:
            return self._guild_reject(-3405)
        guild_id = str(data[0]) if isinstance(data, list) and data else ""
        if not guild_id:
            return self._guild_reject(-3401)

        my_pid = str(p["PlayerId"])
        my_fap = int(p.get("FAP", 0))
        apply_max = int(self._guild_cfg().get("applyNumMax", 3))
        my_head = self._valid_hero_head_id(int(p.get("HeadImageId", 0)), self.state.get("slots", []))

        def _apply(reg: dict[str, Any], dirty: list[bool]) -> tuple[int, dict[str, Any], str]:
            g = reg["guilds"].get(guild_id)
            if not g:
                return -3401, {}, ""
            if len(g.get("members", {})) >= self._guild_member_max(int(g.get("lv", 1))):
                return -3406, {}, ""
            if my_fap < int(g.get("fap_limit", 0)):
                return -3433, {}, ""
            if any(str(a.get("Id", "")) == my_pid for a in g.get("applies", [])):
                return -3410, {}, ""

            if int(g.get("is_auto_apply", 0)) == 1:
                g["members"][my_pid] = {
                    "Id": my_pid,
                    "Name": str(p.get("PlayerName", "Adventurer")),
                    "Lv": int(p.get("Lv", 1)),
                    "FAP": my_fap,
                    "PostId": GUILD_POST_MEMBER,
                    "FundTotal": 0,
                    "HeadImageId": my_head,
                    "FashionModelId": int(p.get("FashionModelId", 0)),
                    "LastActiveTime": now,
                    "JoinedAt": now,
                    "IsNpc": False,
                }
                self._guild_append_news(g, f"{p.get('PlayerName', 'Thành viên')} đã gia nhập Công Hội!")
                for other in reg["guilds"].values():
                    other["applies"] = [a for a in other.get("applies", []) if str(a.get("Id", "")) != my_pid]
                dirty.append(True)
                return 0, self._guild_info_payload(reg, g, my_pid), "joined"

            cur_applied = sum(1 for og in reg["guilds"].values() if any(str(a.get("Id", "")) == my_pid for a in og.get("applies", [])))
            if cur_applied >= apply_max:
                return -3407, {}, ""
            g.setdefault("applies", []).append(
                {
                    "Id": my_pid,
                    "PlayerId": my_pid,
                    "Name": str(p.get("PlayerName", "Adventurer")),
                    "Lv": int(p.get("Lv", 1)),
                    "FAP": my_fap,
                    "Vip": int(p.get("Vip", 0)),
                    "HeadImageId": my_head,
                    "FashionModelId": int(p.get("FashionModelId", 0)),
                    "Crdate": now,
                }
            )
            dirty.append(True)
            applied_cards = [
                self._guild_card_dict(reg, og)
                for og in reg["guilds"].values()
                if any(str(a.get("Id", "")) == my_pid for a in og.get("applies", []))
            ]
            return 0, {"ApplyGuildListInfo": applied_cards}, "pending"

        err, payload, mode = self._with_guild_registry(_apply)
        if err != 0:
            return self._guild_reject(err)
        if mode == "joined":
            self._set_player_guild_link(payload["GuildInfo"]["Id"], payload["GuildInfo"]["Name"])
            pg["fund_total"] = 0
            self.save()
        return payload

    def _rpc_guild_cancel_apply(self, data: Any) -> dict[str, Any]:
        guild_id = str(data[0]) if isinstance(data, list) and data else ""
        my_pid = str(self.state["player"]["PlayerId"])

        def _cancel(reg: dict[str, Any], dirty: list[bool]) -> int:
            g = reg["guilds"].get(guild_id)
            if not g:
                return -3401
            before = len(g.get("applies", []))
            g["applies"] = [a for a in g.get("applies", []) if str(a.get("Id", "")) != my_pid]
            if len(g["applies"]) == before:
                return -3412
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_cancel)
        return self._guild_reject(err) if err != 0 else {}

    def _require_my_guild_auth(self, reg: dict[str, Any], auth_id: int | None = None) -> tuple[int, dict[str, Any] | None, dict[str, Any] | None]:
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))
        my_pid = str(self.state["player"]["PlayerId"])
        g = reg["guilds"].get(gid)
        if not gid or gid == EMPTY_ENTITY_ID or not g or my_pid not in g.get("members", {}):
            return -3425, None, None
        me = g["members"][my_pid]
        if auth_id is not None and not self._guild_has_auth(int(me.get("PostId", GUILD_POST_MEMBER)), auth_id):
            return -3408, None, None
        return 0, g, me

    def _rpc_guild_get_apply_list(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()

        def _fetch(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, dict[str, Any]]:
            err, g, _ = self._require_my_guild_auth(reg, 4)
            if err != 0 or g is None:
                return err, {}
            applies = sorted(g.get("applies", []), key=lambda a: -int(a.get("Crdate", 0)))
            return 0, {"IsAutoApply": int(g.get("is_auto_apply", 0)), "ApplyListInfo": list(applies)}

        err, payload = self._with_guild_registry(_fetch)
        return self._guild_reject(err) if err != 0 else payload

    def _rpc_guild_manage_apply(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            return self._guild_reject(-3409)
        applicant_id = str(data[0])
        is_accept = int(data[1]) == 1
        my_pid = str(self.state["player"]["PlayerId"])
        now = self.now_ts()

        def _mgr(reg: dict[str, Any], dirty: list[bool]) -> tuple[int, str, str]:
            err, g, _ = self._require_my_guild_auth(reg, 4)
            if err != 0 or g is None:
                return err, "", ""
            applies = g.get("applies", [])
            idx = next((i for i, a in enumerate(applies) if str(a.get("Id", "")) == applicant_id), -1)
            if idx < 0:
                return -3409, "", ""
            app_entry = applies.pop(idx)
            dirty.append(True)
            if not is_accept:
                self._emit_guild_avatar(g, my_pid)
                return 0, "", ""
            if len(g.get("members", {})) >= self._guild_member_max(int(g.get("lv", 1))):
                return -3406, "", ""
            already_elsewhere = any(applicant_id in og.get("members", {}) for og in reg["guilds"].values())
            if already_elsewhere:
                return -3404, "", ""
            g["members"][applicant_id] = {
                "Id": applicant_id,
                "Name": str(app_entry.get("Name", "Thành viên")),
                "Lv": int(app_entry.get("Lv", 27)),
                "FAP": int(app_entry.get("FAP", 0)),
                "PostId": GUILD_POST_MEMBER,
                "FundTotal": 0,
                "HeadImageId": int(app_entry.get("HeadImageId", 12011004)),
                "FashionModelId": int(app_entry.get("FashionModelId", 0)),
                "LastActiveTime": now,
                "JoinedAt": now,
                "IsNpc": False,
            }
            news = self._guild_append_news(g, f"{app_entry.get('Name', 'Thành viên')} đã được duyệt vào Công Hội!")
            for other in reg["guilds"].values():
                other["applies"] = [a for a in other.get("applies", []) if str(a.get("Id", "")) != applicant_id]
            self._emit_guild_avatar(g, my_pid, news_items=[news])
            return 0, str(g["id"]), str(g["name"])

        err, joined_gid, joined_name = self._with_guild_registry(_mgr)
        if err != 0:
            return self._guild_reject(err)
        if joined_gid:
            peer = self._find_peer_by_player_id(applicant_id)
            if peer is not None:
                with peer._lock:
                    peer._set_player_guild_link(joined_gid, joined_name)
                    peer.state["guild"]["fund_total"] = 0
                    peer.save()
        return {}

    def _rpc_guild_alter_auto_apply(self, data: Any) -> int:
        val = 1 if (isinstance(data, list) and data and int(data[0]) == 1) else 0

        def _upd(reg: dict[str, Any], dirty: list[bool]) -> tuple[int, int]:
            err, g, _ = self._require_my_guild_auth(reg, 5)
            if err != 0 or g is None:
                return err, 0
            g["is_auto_apply"] = val
            dirty.append(True)
            return 0, val

        err, res = self._with_guild_registry(_upd)
        return self._guild_reject(err) if err != 0 else res

    def _rpc_guild_alter_fap_limit(self, data: Any) -> int:
        raw = str(data[0]).strip() if isinstance(data, list) and data and data[0] is not None else "0"
        fap_limit = max(0, int(raw)) if raw.isdigit() else 0

        def _upd(reg: dict[str, Any], dirty: list[bool]) -> tuple[int, int]:
            err, g, _ = self._require_my_guild_auth(reg, 5)
            if err != 0 or g is None:
                return err, 0
            g["fap_limit"] = fap_limit
            dirty.append(True)
            return 0, fap_limit

        err, res = self._with_guild_registry(_upd)
        return self._guild_reject(err) if err != 0 else res

    def _rpc_guild_update_notice(self, data: Any) -> dict[str, Any]:
        notice = str(data[0])[:120] if isinstance(data, list) and data and data[0] is not None else ""
        my_pid = str(self.state["player"]["PlayerId"])

        def _upd(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, _ = self._require_my_guild_auth(reg, 6)
            if err != 0 or g is None:
                return err
            g["notice"] = notice
            self._emit_guild_avatar(g, my_pid)
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_upd)
        return self._guild_reject(err) if err != 0 else {}

    def _rpc_guild_update_declaration(self, data: Any) -> dict[str, Any]:
        decl = str(data[0])[:120] if isinstance(data, list) and data and data[0] is not None else ""
        my_pid = str(self.state["player"]["PlayerId"])

        def _upd(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, _ = self._require_my_guild_auth(reg, 7)
            if err != 0 or g is None:
                return err
            g["declaration"] = decl
            self._emit_guild_avatar(g, my_pid)
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_upd)
        return self._guild_reject(err) if err != 0 else {}

    def _rpc_guild_get_members(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        now = self.now_ts()
        my_pid = str(self.state["player"]["PlayerId"])

        def _list(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, dict[str, Any]]:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err, {}
            rows: list[dict[str, Any]] = []
            for pid, m in g.get("members", {}).items():
                row = dict(m)
                peer = self._find_peer_by_player_id(pid)
                if peer is not None:
                    pp = peer.state.get("player", {})
                    row["Name"] = str(pp.get("PlayerName", row.get("Name", "")))
                    row["Lv"] = int(pp.get("Lv", row.get("Lv", 1)))
                    row["FAP"] = int(pp.get("FAP", row.get("FAP", 0)))
                last_act = int(row.get("LastActiveTime", now))
                out_time = max(0, now - last_act)
                is_active = pid == my_pid or bool(row.get("IsNpc")) or out_time < 300
                rows.append(
                    {
                        "Id": str(pid),
                        "Name": str(row.get("Name", "")),
                        "Lv": int(row.get("Lv", 1)),
                        "FAP": int(row.get("FAP", 0)),
                        "PostId": int(row.get("PostId", GUILD_POST_MEMBER)),
                        "FundTotal": int(row.get("FundTotal", 0)),
                        "HeadImageId": int(row.get("HeadImageId", 12011004)),
                        "FashionModelId": int(row.get("FashionModelId", 0)),
                        "IsActive": bool(is_active),
                        "OutTime": 0 if is_active else out_time,
                    }
                )
            rows.sort(key=lambda r: (int(r["PostId"]), -int(r["FAP"]), str(r["Id"])))
            return 0, {"GuildMembersInfo": rows}

        err, payload = self._with_guild_registry(_list)
        return self._guild_reject(err) if err != 0 else payload

    def _rpc_guild_post_change(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            return self._guild_reject(-3429)
        target_id = str(data[0])
        try:
            new_post_id = int(data[1])
        except (TypeError, ValueError):
            return self._guild_reject(-3429)
        if new_post_id not in (GUILD_POST_VICE, GUILD_POST_ELITE, GUILD_POST_MEMBER):
            return self._guild_reject(-3429)
        my_pid = str(self.state["player"]["PlayerId"])

        def _chg(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, me = self._require_my_guild_auth(reg, 1)
            if err != 0 or g is None or me is None:
                return err
            target = g.get("members", {}).get(target_id)
            if not target:
                return -3411
            cur_post = int(target.get("PostId", GUILD_POST_MEMBER))
            if cur_post == GUILD_POST_LEADER or cur_post <= int(me.get("PostId", GUILD_POST_MEMBER)):
                return -3403
            if cur_post == new_post_id:
                return -3430
            cap = GUILD_POST_CAPS.get(new_post_id)
            if cap is not None:
                cnt = sum(1 for m in g["members"].values() if int(m.get("PostId", 0)) == new_post_id)
                if cnt >= cap:
                    return -3414
            target["PostId"] = new_post_id
            news = self._guild_append_news(g, f"{target['Name']} được bổ nhiệm chức vụ mới.")
            self._emit_guild_avatar(g, my_pid, news_items=[news])
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_chg)
        return self._guild_reject(err) if err != 0 else {}

    def _rpc_guild_post_alter(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 3:
            return self._guild_reject(-3429)
        try:
            post_id = int(data[0])
        except (TypeError, ValueError):
            return self._guild_reject(-3429)
        old_id, new_id = str(data[1]), str(data[2])
        if post_id not in (GUILD_POST_VICE, GUILD_POST_ELITE):
            return self._guild_reject(-3429)
        my_pid = str(self.state["player"]["PlayerId"])

        def _alt(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, _ = self._require_my_guild_auth(reg, 1)
            if err != 0 or g is None:
                return err
            old_m = g["members"].get(old_id)
            new_m = g["members"].get(new_id)
            if not old_m or not new_m or int(old_m.get("PostId", 0)) != post_id:
                return -3429
            if int(new_m.get("PostId", 0)) == GUILD_POST_LEADER:
                return -3403
            old_m["PostId"] = GUILD_POST_MEMBER
            new_m["PostId"] = post_id
            self._emit_guild_avatar(g, my_pid)
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_alt)
        return self._guild_reject(err) if err != 0 else {}

    def _rpc_guild_post_assignment(self, data: Any) -> dict[str, Any]:
        target_id = str(data[0]) if isinstance(data, list) and data else ""
        my_pid = str(self.state["player"]["PlayerId"])

        def _xfer(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, me = self._require_my_guild_auth(reg)
            if err != 0 or g is None or me is None:
                return err
            if int(me.get("PostId", GUILD_POST_MEMBER)) != GUILD_POST_LEADER:
                return -3408
            target = g["members"].get(target_id)
            if not target or target_id == my_pid:
                return -3411
            me["PostId"] = GUILD_POST_MEMBER
            target["PostId"] = GUILD_POST_LEADER
            news = self._guild_append_news(g, f"{target['Name']} đã trở thành Tộc Trưởng mới!")
            self._emit_guild_avatar(g, my_pid, news_items=[news])
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_xfer)
        return self._guild_reject(err) if err != 0 else {}

    def _rpc_guild_kick_out(self, data: Any) -> dict[str, Any]:
        target_id = str(data[0]) if isinstance(data, list) and data else ""
        my_pid = str(self.state["player"]["PlayerId"])

        def _kick(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, me = self._require_my_guild_auth(reg, 3)
            if err != 0 or g is None or me is None:
                return err
            target = g["members"].get(target_id)
            if not target:
                return -3411
            if int(target.get("PostId", GUILD_POST_MEMBER)) <= int(me.get("PostId", GUILD_POST_MEMBER)):
                return -3403
            del g["members"][target_id]
            g.get("shares", {}).pop(target_id, None)
            news = self._guild_append_news(g, f"{target['Name']} đã rời Công Hội.")
            self._emit_guild_avatar(g, my_pid, news_items=[news])
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_kick)
        if err != 0:
            return self._guild_reject(err)
        self._clear_peer_guild_link(target_id, set_cd=True)
        return {}

    def _rpc_guild_exit(self, _data: Any) -> dict[str, Any]:
        my_pid = str(self.state["player"]["PlayerId"])

        def _exit(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, me = self._require_my_guild_auth(reg)
            if err != 0 or g is None or me is None:
                return err
            if int(me.get("PostId", GUILD_POST_MEMBER)) == GUILD_POST_LEADER:
                return -3413
            del g["members"][my_pid]
            g.get("shares", {}).pop(my_pid, None)
            self._guild_append_news(g, f"{me['Name']} đã thoát Công Hội.")
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_exit)
        if err != 0:
            return self._guild_reject(err)
        self._set_player_guild_link(EMPTY_ENTITY_ID, "", set_cd=True)
        self.save()
        return {}

    def _rpc_guild_dismiss(self, _data: Any) -> dict[str, Any]:
        max_dismiss_lv = int(self._guild_cfg().get("dismissGuildLVMax", 5))
        pg = self._ensure_player_guild_container(self.state)
        gid = str(pg.get("guild_id", EMPTY_ENTITY_ID))

        def _dismiss(reg: dict[str, Any], dirty: list[bool]) -> tuple[int, list[str]]:
            err, g, me = self._require_my_guild_auth(reg)
            if err != 0 or g is None or me is None:
                return err, []
            if int(me.get("PostId", GUILD_POST_MEMBER)) != GUILD_POST_LEADER:
                return -3408, []
            if int(g.get("lv", 1)) > max_dismiss_lv:
                return -3402, []
            member_ids = list(g.get("members", {}).keys())
            del reg["guilds"][gid]
            dirty.append(True)
            return 0, member_ids

        err, member_ids = self._with_guild_registry(_dismiss)
        if err != 0:
            return self._guild_reject(err)
        my_pid = str(self.state["player"]["PlayerId"])
        for mid in member_ids:
            if mid == my_pid:
                self._set_player_guild_link(EMPTY_ENTITY_ID, "", set_cd=True)
            else:
                self._clear_peer_guild_link(mid, set_cd=False)
        self.save()
        return {}

    def _rpc_guild_impeach(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        cfg = self._guild_cfg()
        need_dia = int(cfg.get("impeachUseDiamond", 100))
        min_offline_sec = int(cfg.get("impeachOfflineTimeMin", 168)) * 3600
        if int(p.get("Diamond", 0)) < need_dia:
            return self._guild_reject(-1105)
        now = self.now_ts()
        my_pid = str(p["PlayerId"])

        def _imp(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, me = self._require_my_guild_auth(reg)
            if err != 0 or g is None or me is None:
                return err
            if int(me.get("PostId", GUILD_POST_MEMBER)) == GUILD_POST_LEADER:
                return -3408
            leader = next((m for m in g["members"].values() if int(m.get("PostId", 0)) == GUILD_POST_LEADER), None)
            if leader is None:
                return -3401
            leader_last = int(leader.get("LastActiveTime", now))
            peer = self._find_peer_by_player_id(str(leader["Id"]))
            if peer is not None:
                leader_last = int(peer.state.get("player", {}).get("LastLoginTime", leader_last))
            if (now - leader_last) < min_offline_sec:
                return -3415
            leader["PostId"] = GUILD_POST_MEMBER
            me["PostId"] = GUILD_POST_LEADER
            me["LastActiveTime"] = now
            news = self._guild_append_news(g, f"{me['Name']} đã bãi nhiệm Tộc Trưởng cũ và lên nắm quyền.")
            self._emit_guild_avatar(g, my_pid, news_items=[news])
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_imp)
        if err != 0:
            return self._guild_reject(err)
        if need_dia > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -need_dia, source="guild_impeach")
        self.save()
        return {}

    # -------------------- Guild Construction, Donate, Upgrade, Shop, Mercenary --------------------

    def _rpc_guild_build(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        build_type_id = int(data[0]) if isinstance(data, list) and data and data[0] is not None else 0
        row = self.game_data.get("guild_build_types", {}).get(str(build_type_id))
        if not row:
            return self._guild_reject(-1)
        if pg.get("built_today"):
            return self._guild_reject(-3428)

        use_costs = _parse_res_tuples(str(row.get("useResource", "")))
        dia_cost = sum(rn for rt, _, rn in use_costs if rt == 1111)
        gold_cost = sum(rn for rt, _, rn in use_costs if rt == 1112)
        if int(p.get("Diamond", 0)) < dia_cost or int(p.get("Gold", 0)) < gold_cost:
            return self._guild_reject(-1105)

        need_guild_lv = int(self._guild_cfg().get("buildNeedGuildLv", 3))
        my_pid = str(p["PlayerId"])
        out_contrib = int(row.get("outputContribution", 0))
        out_fund = int(row.get("outputGuildFund", 0))

        def _build(reg: dict[str, Any], dirty: list[bool]) -> tuple[int, int]:
            err, g, me = self._require_my_guild_auth(reg)
            if err != 0 or g is None or me is None:
                return err, 1
            if int(g.get("lv", 1)) < need_guild_lv:
                return -3449, 1
            if int(g.get("build_count_today", 0)) >= self._guild_member_max(int(g.get("lv", 1))):
                return -3418, 1
            g["build_count_today"] = int(g.get("build_count_today", 0)) + 1
            g["guild_fund"] = int(g.get("guild_fund", 0)) + out_fund
            g["guild_fund_total"] = int(g.get("guild_fund_total", 0)) + out_fund
            g["guild_fund_week"] = int(g.get("guild_fund_week", 0)) + out_fund
            me["FundTotal"] = int(me.get("FundTotal", 0)) + out_contrib
            logs = g.setdefault("build_logs", [])
            next_id = max((int(l.get("Id", 0)) for l in logs), default=0) + 1
            logs.insert(0, {"Id": next_id, "BuildType": build_type_id, "PlayerName": str(p.get("PlayerName", ""))})
            if len(logs) > 50:
                del logs[50:]
            self._emit_guild_avatar(g, my_pid)
            dirty.append(True)
            return 0, self._guild_rank_order(reg, str(g["id"]))

        err, rank_num = self._with_guild_registry(_build)
        if err != 0:
            return self._guild_reject(err)

        if dia_cost > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -dia_cost, source=f"guild_build:{build_type_id}")
        if gold_cost > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Gold", -gold_cost, source=f"guild_build:{build_type_id}")

        tuples: list[tuple[int, int, int]] = []
        if out_contrib > 0:
            tuples.append((1113, 0, out_contrib))
        tuples.extend(_parse_res_tuples(str(row.get("outputResource", ""))))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"guild_build:{build_type_id}",
            tx_prefix=f"guild_build:{self.profile_name}:{pg['day']}:{build_type_id}",
        )
        pg["built_today"] = True
        pg["fund_total"] = int(pg.get("fund_total", 0)) + out_contrib
        self._inc_stat("guild_build_count", 1)
        self._record_daily_task_progress(15, 1)
        self.save()
        return {"BaseGetGameResourceList": base_res, "RandNum": rank_num}

    def _rpc_guild_get_build_log(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()

        def _logs(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, dict[str, Any]]:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err, {}
            return 0, {"GlobalGuildBuildingLog": list(g.get("build_logs", []))}

        err, payload = self._with_guild_registry(_logs)
        return self._guild_reject(err) if err != 0 else payload

    def _rpc_guild_contribute(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            return self._guild_reject(-1105)
        try:
            model_id = int(data[0])
            count = int(data[1])
        except (TypeError, ValueError):
            return self._guild_reject(-1105)
        row = self.game_data.get("guild_donate", {}).get(str(model_id))
        if not row or count <= 0:
            return self._guild_reject(-1)
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
            return self._guild_reject(-3425)
        have_goods = sum(int(g.get("Num", 0)) for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == model_id)
        if have_goods < count:
            return self._guild_reject(-1105)

        total_contrib = int(row.get("outputContribution", 0)) * count
        my_pid = str(self.state["player"]["PlayerId"])

        def _don(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, me = self._require_my_guild_auth(reg)
            if err != 0 or g is None or me is None:
                return err
            g["guild_fund"] = int(g.get("guild_fund", 0)) + total_contrib
            g["guild_fund_total"] = int(g.get("guild_fund_total", 0)) + total_contrib
            g["guild_fund_week"] = int(g.get("guild_fund_week", 0)) + total_contrib
            me["FundTotal"] = int(me.get("FundTotal", 0)) + total_contrib
            self._emit_guild_avatar(g, my_pid)
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_don)
        if err != 0:
            return self._guild_reject(err)
        self._consume_goods(model_id, count)
        base_res = self._grant_resources_from_tuples(
            [(1113, 0, total_contrib)],
            source=f"guild_contribute:{model_id}x{count}",
            tx_prefix=f"guild_contrib:{self.profile_name}:{uuid.uuid4()}",
        )
        pg["fund_total"] = int(pg.get("fund_total", 0)) + total_contrib
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_guild_building_lv_up(self, data: Any) -> dict[str, Any]:
        try:
            bid = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            return self._guild_reject(-1)
        if bid not in GUILD_BUILDING_ORDER:
            return self._guild_reject(-1)
        self._sync_guild_state()
        my_pid = str(self.state["player"]["PlayerId"])
        lv_rel = self.game_data.get("guild_building_lv", {}).get(str(bid), {})

        def _up(reg: dict[str, Any], dirty: list[bool]) -> tuple[int, dict[str, Any]]:
            err, g, _ = self._require_my_guild_auth(reg, 2)
            if err != 0 or g is None:
                return err, {}
            bmap = g.setdefault("buildings", {str(k): 1 for k in GUILD_BUILDING_ORDER})
            cur_lv = int(bmap.get(str(bid), 1))
            hall_lv = int(bmap.get(str(GUILD_HALL_ID), 1))
            if bid != GUILD_HALL_ID and cur_lv >= hall_lv:
                return -3419, {}
            cur_row = lv_rel.get(str(cur_lv))
            nxt_row = lv_rel.get(str(cur_lv + 1))
            if not cur_row or not nxt_row:
                return -3416, {}
            cost = max(0, int(nxt_row.get("totalExp", 0)) - int(cur_row.get("totalExp", 0)))
            if int(g.get("guild_fund", 0)) < cost:
                return -3417, {}
            g["guild_fund"] = int(g.get("guild_fund", 0)) - cost
            new_lv = cur_lv + 1
            bmap[str(bid)] = new_lv
            if bid == GUILD_HALL_ID:
                g["lv"] = new_lv
            bname = self.game_data.get("guild_buildings", {}).get(str(bid), {}).get("name", str(bid))
            news = self._guild_append_news(g, f"{bname} đã nâng lên Lv.{new_lv}!")
            self._emit_guild_avatar(g, my_pid, news_items=[news])
            dirty.append(True)
            return 0, {"BuildingId": bid, "Lv": new_lv, "GuildFund": int(g["guild_fund"])}

        err, payload = self._with_guild_registry(_up)
        return self._guild_reject(err) if err != 0 else payload

    def _rpc_guild_shop_buy_list(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
            return self._guild_reject(-3425)

        shop_cfg = self.game_data.get("guild_shop", {})
        daily_map = pg.get("shop_daily", {})
        total_map = pg.get("shop_total", {})
        items = []
        for row in sorted(shop_cfg.values(), key=lambda r: (int(r.get("order", 999)), int(r.get("ID", 0)))):
            sid = str(row["ID"])
            per_max = int(row.get("perMaxNum", 0))
            tot_max = int(row.get("totalMaxNum", 0))
            buy_num = int(total_map.get(sid, 0)) if tot_max > 0 else int(daily_map.get(sid, 0))
            items.append(
                {
                    "Id": int(row["ID"]),
                    "TypeId": int(row["typeID"]),
                    "ModelId": int(row["modelID"]),
                    "Num": int(row["num"]),
                    "NeedCoin": int(row["needCoin"]),
                    "PerMaxNum": per_max,
                    "TotalMaxNum": tot_max,
                    "NeedBuildingLv": int(row["needBuildingLV"]),
                    "BuyNum": buy_num,
                }
            )
        return {"GuildShopInfo": items}

    def _rpc_guild_shop_buy(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            return self._guild_reject(-1)
        try:
            shop_id = int(data[0])
            num = max(1, int(data[1]))
        except (TypeError, ValueError):
            return self._guild_reject(-1)
        row = self.game_data.get("guild_shop", {}).get(str(shop_id))
        if not row:
            return self._guild_reject(-1)
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)

        def _shop_lv(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, int]:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err, 0
            return 0, int(g.get("buildings", {}).get(str(GUILD_SHOP_ID), 1))

        err, shop_lv = self._with_guild_registry(_shop_lv)
        if err != 0:
            return self._guild_reject(err)
        if shop_lv < int(row.get("needBuildingLV", 1)):
            return self._guild_reject(-3419)

        sid = str(shop_id)
        per_max = int(row.get("perMaxNum", 0))
        tot_max = int(row.get("totalMaxNum", 0))
        daily_map = pg.setdefault("shop_daily", {})
        total_map = pg.setdefault("shop_total", {})
        if per_max > 0 and int(daily_map.get(sid, 0)) + num > per_max:
            return self._guild_reject(-3420)
        if tot_max > 0 and int(total_map.get(sid, 0)) + num > tot_max:
            return self._guild_reject(-3420)

        p = self.state["player"]
        cost = int(row.get("needCoin", 0)) * num
        if int(p.get("Contribution", 0)) < cost:
            return self._guild_reject(-1121)

        if cost > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Contribution", -cost, source=f"guild_shop:{shop_id}")
        daily_map[sid] = int(daily_map.get(sid, 0)) + num
        total_map[sid] = int(total_map.get(sid, 0)) + num
        base_res = self._grant_resources_from_tuples(
            [(int(row["typeID"]), int(row["modelID"]), int(row["num"]) * num)],
            source=f"guild_shop:{shop_id}x{num}",
            tx_prefix=f"guild_shop:{self.profile_name}:{pg['day']}:{shop_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_guild_shop_reset_daily(self, _data: Any = None) -> dict[str, Any]:
        """Reset daily Guild shop counts (perMaxNum) while preserving one-time totalMaxNum purchases."""
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
            return self._guild_reject(-3425)
        pg["shop_daily"] = {}
        self.save()
        return self._rpc_guild_shop_buy_list(None)

    def _rpc_guild_get_share(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        my_pid = str(self.state["player"]["PlayerId"])

        def _get(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, dict[str, Any]]:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err, {}
            share_list = sorted(g.get("shares", {}).values(), key=lambda s: -int(s.get("FAP", 0)))
            my_share = g.get("shares", {}).get(my_pid)
            return 0, {
                "ShareId": my_share["ShareId"] if my_share else None,
                "ShareTime": int(my_share["ShareTime"]) if my_share else 0,
                "GuildShareInfo": [copy.deepcopy(s) for s in share_list],
            }

        err, payload = self._with_guild_registry(_get)
        return self._guild_reject(err) if err != 0 else payload

    def _rpc_guild_share(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        need_lv = int(self._guild_cfg().get("shareNeedLV", 23))
        if int(p.get("Lv", 1)) < need_lv:
            return self._guild_reject(-3422)
        if pg.get("shared_today"):
            return self._guild_reject(-3423)

        try:
            slot_idx = int(data[0]) if isinstance(data, list) and data else 0
        except (TypeError, ValueError):
            return self._guild_reject(-1)
        slot = next((s for s in self.state.get("slots", []) if int(s.get("SlotId", 0)) == slot_idx), None)
        if not slot or not slot.get("HeroModelId") or str(slot.get("HeroId", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
            return self._guild_reject(-1)

        hero_model_id = int(slot["HeroModelId"])
        hero_cfg = self.game_data.get("heroes", {}).get(str(hero_model_id), {})
        if int(hero_cfg.get("specialType", 0)) == 255:
            return self._guild_reject(-3424)

        heroes_by_id = {str(h["Id"]): h for h in self.state.get("heroes", [])}
        hero_inst = heroes_by_id.get(str(slot["HeroId"]), {})
        prop = slot.get("Property", {})
        now = self.now_ts()
        my_pid = str(p["PlayerId"])
        share_id = str(uuid.uuid4())
        entry = {
            "ShareId": share_id,
            "PlayerId": my_pid,
            "PlayerName": str(p.get("PlayerName", "Adventurer")),
            "HeroModelId": hero_model_id,
            "Lv": int(hero_inst.get("Lv", p.get("Lv", 1))),
            "Step": int(hero_inst.get("Step", 0)),
            "RebornStep": int(hero_inst.get("RebornStep", 0)),
            "RebornId": int(hero_inst.get("RebornId", 0)),
            "FAP": int(prop.get("FAP", 0)),
            "FSP": int(prop.get("FSP", hero_cfg.get("FSP", 50))),
            "HP": int(prop.get("HP", 1000)),
            "AP": int(prop.get("AP", 200)),
            "DEF": int(prop.get("DEF", 100)),
            "Property": copy.deepcopy(prop),
            "ShareTime": now,
            "HireCount": 0,
        }

        def _put(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err
            g.setdefault("shares", {})[my_pid] = entry
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_put)
        if err != 0:
            return self._guild_reject(err)
        pg["shared_today"] = True
        pg["share_id"] = share_id
        pg["share_time"] = now
        self._inc_stat("guild_share_count", 1)
        self._record_daily_task_progress(10, 1)
        self.save()
        return {"ShareId": share_id, "ShareTime": now}

    # -------------------- GuildBossInfo RPCs (6) --------------------

    def _current_guild_boss_id(self) -> int:
        boss_keys = sorted(int(k) for k in self.game_data.get("guild_bosses", {}))
        if not boss_keys:
            return 12015019
        day_ord = self.clock.dt().date().toordinal()
        return boss_keys[day_ord % len(boss_keys)]

    def _guild_boss_inspire_active(self, g: dict[str, Any], now: int) -> tuple[int, int]:
        dur = int(self._guild_cfg().get("seconds", 1800))
        ts = int(g.get("boss_inspire_time", 0))
        if ts > 0 and (now - ts) < dur:
            return 1, ts
        return 0, 0

    def _rpc_guild_boss_get(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        need_lv = int(self._guild_cfg().get("needGuildLv", 1))
        now = self.now_ts()

        def _get(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, int, int]:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err, 0, 0
            if int(g.get("lv", 1)) < need_lv:
                return -3453, 0, 0
            st, ts = self._guild_boss_inspire_active(g, now)
            return 0, st, ts

        err, ins_st, ins_ts = self._with_guild_registry(_get)
        if err != 0:
            return self._guild_reject(err)
        self.save()
        return {
            "PlayerGuildBossInfo": {
                "BossModelId": self._current_guild_boss_id(),
                "FightCount": int(pg.get("boss_fight_count", 0)),
                "InspireBuffOpenState": ins_st,
                "InspireBuffOpenTime": ins_ts,
            }
        }

    def _rpc_guild_boss_rank_list(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        my_pid = str(self.state["player"]["PlayerId"])

        def _ranks(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, dict[str, Any]]:
            err, my_g, _ = self._require_my_guild_auth(reg)
            if err != 0 or my_g is None:
                return err, {}
            guild_rows: list[dict[str, Any]] = []
            player_rows: list[dict[str, Any]] = []
            for g in reg["guilds"].values():
                score = int(g.get("boss_total_score", 0))
                if score > 0 or g["id"] == my_g["id"]:
                    guild_rows.append(
                        {
                            "Lv": int(g.get("lv", 1)),
                            "GuildName": str(g["name"]),
                            "Score": score,
                        }
                    )
                for pid, m_score in g.get("boss_member_scores", {}).items():
                    m = g.get("members", {}).get(pid, {})
                    player_rows.append(
                        {
                            "PlayerId": str(pid),
                            "Lv": int(m.get("Lv", 1)),
                            "Name": str(m.get("Name", "")),
                            "GuildName": str(g["name"]),
                            "Score": int(m_score),
                        }
                    )
            guild_rows.sort(key=lambda r: (-int(r["Score"]), -int(r["Lv"]), r["GuildName"]))
            for idx, r in enumerate(guild_rows, start=1):
                r["Rank"] = idx
            player_rows.sort(key=lambda r: (-int(r["Score"]), -int(r["Lv"]), r["PlayerId"]))
            for idx, r in enumerate(player_rows, start=1):
                r["Rank"] = idx

            my_rank = next((r for r in player_rows if r["PlayerId"] == my_pid), None)
            if my_rank is None:
                p = self.state["player"]
                my_rank = {
                    "Rank": len(player_rows) + 1,
                    "Lv": int(p.get("Lv", 1)),
                    "Name": str(p.get("PlayerName", "")),
                    "GuildName": str(my_g["name"]),
                    "Score": 0,
                }
            return 0, {
                "Rank": {
                    "GuildBossGuildRank": guild_rows,
                    "GuildBossPlayerRank": player_rows,
                },
                "MyRank": my_rank,
            }

        err, payload = self._with_guild_registry(_ranks)
        return self._guild_reject(err) if err != 0 else payload

    def _rpc_guild_boss_inspire(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        self._sync_guild_state()
        cfg = self._guild_cfg()
        need_dia = int(cfg.get("buffUseDimonds", 200))
        if int(p.get("Diamond", 0)) < need_dia:
            return self._guild_reject(-1105)
        now = self.now_ts()

        def _ins(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err
            st, _ = self._guild_boss_inspire_active(g, now)
            if st == 1:
                return -3438
            g["boss_inspire_time"] = now
            dirty.append(True)
            return 0

        err = self._with_guild_registry(_ins)
        if err != 0:
            return self._guild_reject(err)
        if need_dia > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "Diamond", -need_dia, source="guild_boss_inspire")
        self.save()
        return {"InspireBuffOpenState": 1, "InspireBuffOpenTime": now}

    def _build_guild_boss_fight_info(self, *, inspired: bool) -> dict[str, Any]:
        p = self.state["player"]
        allies = self._build_ally_fight_objs()
        if inspired:
            add_r = int(self._guild_cfg().get("addAttack", 2000)) / 10000.0
            for u in allies:
                if u and "AP" in u:
                    u["AP"] = max(1, int(u["AP"] * (1.0 + add_r)))

        boss_mid = self._current_guild_boss_id()
        boss_row = self.game_data.get("guild_bosses", {}).get(str(boss_mid), {})
        hero_cfg = self.game_data.get("heroes", {}).get(str(boss_mid), {})
        if not boss_row or not hero_cfg:
            boss_mid = 12010050
            hero_cfg = self.game_data["heroes"][str(boss_mid)]

        boss_override = {
            "HP": int(boss_row.get("HP", 1_000_000_000)),
            "AP": int(boss_row.get("AP", 5000)),
            "DEF": int(boss_row.get("DEF", 0)),
            "RP": int(boss_row.get("RP", 0)),
            "HIT": int(boss_row.get("HIT", 50000)),
            "DOD": int(boss_row.get("DOD", 500)),
            "CRI": int(boss_row.get("CRI", 300)),
            "TEN": int(boss_row.get("TEN", 10000)),
            "BLO": int(boss_row.get("BLO", 300)),
            "BOG": int(boss_row.get("BOG", 10000)),
            "CRId": int(boss_row.get("CRID", 0)),
            "TEND": int(boss_row.get("TEND", 0)),
            "APR": int(boss_row.get("APR", 0)),
            "HPR": int(boss_row.get("HPR", 0)),
            "DEFR": int(boss_row.get("DEFR", 0)),
            "CP": int(boss_row.get("CP", 0)),
            "BCP": int(boss_row.get("BCP", 0)),
            "CPR": int(boss_row.get("CPR", 0)),
            "BCPR": int(boss_row.get("BCPR", 0)),
            "DAMADD": int(boss_row.get("DAMADD", 0)),
            "DAMCUT": int(boss_row.get("DAMCUT", 0)),
            "DAMADDR": int(boss_row.get("DAMADDR", 0)),
            "DAMCUTR": int(boss_row.get("DAMCUTR", 0)),
            "FSP": 100,
        }
        enemies: list[dict[str, Any]] = [{} for _ in range(6)]
        pos = max(1, min(6, int(boss_row.get("formation", 2)))) - 1
        enemies[pos] = self._hero_fight_obj(
            hero_cfg,
            lv=max(1, int(p.get("Lv", 27))),
            is_boss=True,
            step=int(boss_row.get("step", 5)),
            override_stats=boss_override,
        )
        return {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": sum(int(u.get("FSP", 0)) for u in allies if u), "Fap": int(p.get("FAP", 0))},
                        {"Fsp": 100, "Fap": int(boss_override["AP"]) * 100},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1000, 999999),
                    "IsPVP": False,
                }
            ]
        }

    def _rpc_guild_boss_get_fight_info(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        max_atk = int(self._guild_cfg().get("bossBattleNum", 2))
        if int(pg.get("boss_fight_count", 0)) >= max_atk:
            return self._guild_reject(-3448)
        if not self._guild_boss_in_window():
            return self._guild_reject(-3447)
        now = self.now_ts()

        def _prep(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, bool]:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err, False
            if int(g.get("lv", 1)) < int(self._guild_cfg().get("needGuildLv", 1)):
                return -3453, False
            st, _ = self._guild_boss_inspire_active(g, now)
            return 0, st == 1

        err, inspired = self._with_guild_registry(_prep)
        if err != 0:
            return self._guild_reject(err)
        fight_info = self._build_guild_boss_fight_info(inspired=inspired)
        pg["pending_boss_fight"] = {"fight_info": copy.deepcopy(fight_info), "inspired": inspired}
        self.save()
        return {"FightInfo": fight_info}

    def _rpc_guild_boss_fight(self, data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        max_atk = int(self._guild_cfg().get("bossBattleNum", 2))
        if int(pg.get("boss_fight_count", 0)) >= max_atk:
            return self._guild_reject(-3448)
        if not self._guild_boss_in_window():
            return self._guild_reject(-3447)

        now = self.now_ts()
        pending = pg.pop("pending_boss_fight", None)

        def _info(reg: dict[str, Any], _dirty: list[bool]) -> tuple[int, int, bool]:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err, 1, False
            boss_lv = int(g.get("buildings", {}).get(str(GUILD_BOSS_ID), 1))
            st, _ = self._guild_boss_inspire_active(g, now)
            return 0, boss_lv, st == 1

        err, boss_lv, inspired_now = self._with_guild_registry(_info)
        if err != 0:
            return self._guild_reject(err)

        fight_info = (
            pending["fight_info"]
            if isinstance(pending, dict) and pending.get("fight_info")
            else self._build_guild_boss_fight_info(inspired=inspired_now)
        )
        outcome = simulate_fight_info(
            fight_info,
            self.game_data.get("attacks", {}),
            buffs_cfg=self.game_data.get("combat_buffs", {}),
        )
        boss_pos = 6 + max(1, min(6, int(self.game_data.get("guild_bosses", {}).get(str(self._current_guild_boss_id()), {}).get("formation", 2))))
        boss_start_hp = int(self.game_data.get("guild_bosses", {}).get(str(self._current_guild_boss_id()), {}).get("HP", 1_000_000_000))
        last_wave = outcome.verify_data.get("hp", [[]])[-1]
        end_hp = next((int(u.get("HP", boss_start_hp)) for u in last_wave if int(u.get("PosId", 0)) == boss_pos), boss_start_hp)
        sim_hurt = max(1, boss_start_hp - end_hp)

        submitted_dmg = 0
        if isinstance(data, list) and len(data) >= 3 and data[2] is not None:
            try:
                submitted_dmg = int(float(data[2]))
            except (TypeError, ValueError):
                submitted_dmg = 0
        # Accept valid client damage within simulated sanity ceiling
        hurt = min(submitted_dmg, max(sim_hurt * 2, 1000)) if submitted_dmg > 0 else sim_hurt
        hurt = max(1, hurt)

        my_pid = str(self.state["player"]["PlayerId"])

        def _commit(reg: dict[str, Any], dirty: list[bool]) -> int:
            err, g, _ = self._require_my_guild_auth(reg)
            if err != 0 or g is None:
                return err
            g["boss_total_score"] = int(g.get("boss_total_score", 0)) + hurt
            mscores = g.setdefault("boss_member_scores", {})
            mscores[my_pid] = int(mscores.get(my_pid, 0)) + hurt
            dirty.append(True)
            return 0

        err2 = self._with_guild_registry(_commit)
        if err2 != 0:
            return self._guild_reject(err2)

        lv_row = self.game_data.get("guild_building_lv", {}).get(str(GUILD_BOSS_ID), {}).get(str(boss_lv), {})
        tuples = _parse_res_tuples(str(lv_row.get("battleRewardsEvery", "1111,0,100||1113,0,100")))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"guild_boss:{boss_lv}",
            tx_prefix=f"guild_boss:{self.profile_name}:{pg['day']}:{uuid.uuid4()}",
        )
        pg["boss_fight_count"] = int(pg.get("boss_fight_count", 0)) + 1
        self._inc_stat("guild_boss_fights", 1)
        self.save()
        return {"HurtValue": hurt, "BaseGetGameResourceList": base_res}

    def _rpc_guild_boss_reset_count(self, _data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
            return self._guild_reject(-3425)
        pg["boss_fight_count"] = 0
        self.save()
        return {"FightCount": 0}

    # -------------------- GuildReward RPCs (2) --------------------

    def _rpc_guild_reward_list(self, _data: Any) -> list[dict[str, Any]]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
            return self._guild_reject(-3425)
        return [
            {
                "Id": str(r["Id"]),
                "Title": str(r.get("Title", "Thưởng Công Hội")),
                "ResourceList": list(r.get("ResourceList", [])),
                "CreateTime": int(r.get("CreateTime", self.now_ts())),
            }
            for r in pg.get("rewards", [])
        ]

    def _rpc_guild_reward_draw(self, data: Any) -> dict[str, Any]:
        self._sync_guild_state()
        pg = self._ensure_player_guild_container(self.state)
        if str(pg.get("guild_id", EMPTY_ENTITY_ID)) == EMPTY_ENTITY_ID:
            return self._guild_reject(-3425)
        raw_ids = data[0] if isinstance(data, list) and data and isinstance(data[0], list) else (data if isinstance(data, list) else [])
        target_ids = {str(x) for x in raw_ids if x}
        rewards = pg.get("rewards", [])
        claimed = [r for r in rewards if str(r.get("Id", "")) in target_ids]
        if not claimed:
            return self._guild_reject(-3452)

        tuples: list[tuple[int, int, int]] = []
        for entry in claimed:
            for item in entry.get("ResourceList", []):
                rt = int(item.get("ResourceTypeSub", 0))
                rm = int(item.get("ModelId", 0))
                rn = int(item.get("Count", item.get("Num", 0)))
                if rt > 0 and rn > 0:
                    tuples.append((rt, rm, rn))

        pg["rewards"] = [r for r in rewards if str(r.get("Id", "")) not in target_ids]
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="guild_reward_draw",
            tx_prefix=f"guild_rew:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}
