"""Phó Bản Tổ Đội (Teambattle) handlers — 24 nodes, solo NPC teammates, garrison, and 18-item gem shop."""

from __future__ import annotations

import copy
import random
import uuid
from typing import Any

from combat_sim import simulate_fight_info
from r79_event_handlers import _parse_res_tuples

TEAMBATTLE_MODULE_ID = 2319
TEAMBATTLE_GEM_COIN_ID = 16050023


class TeambattleHandlersMixin:
    """Backend state & RPC engine for Phó Bản Tổ Đội (TeambattleInfo / Fightinfo / Holdinfo / Shopinfo)."""

    def _teambattle_reject(self, status: int) -> dict[str, Any]:
        self._last_rpc_context["status"] = status
        return {}

    def _teambattle_open_lv(self) -> int:
        ms = self.game_data.get("module_subs", {}).get(str(TEAMBATTLE_MODULE_ID), {})
        return int(ms.get("openLv", 40) or 40)

    def _teambattle_is_open(self) -> bool:
        return int(self.state["player"].get("Lv", 1)) >= self._teambattle_open_lv()

    def _teambattle_cfg(self) -> dict[str, Any]:
        return self.game_data.get("teambattle_config", {})

    def _teambattle_state(self) -> dict[str, Any]:
        tb = self.state.setdefault("teambattle", {})
        tb.setdefault("all_invite_flag", 0)
        tb.setdefault("nodes", {})
        tb.setdefault("shop", {})
        tb.setdefault("team", None)
        return tb

    def _teambattle_sync_holds(self) -> dict[str, Any]:
        tb = self._teambattle_state()
        now = self.now_ts()
        for nst in tb["nodes"].values():
            if (
                int(nst.get("hold_hero_id", 0)) > 0
                and not nst.get("hold_reward_pending")
                and nst.get("hold_drawn_date") != nst.get("hold_date")
                and now >= int(nst.get("hold_end_time", 0))
            ):
                nst["hold_reward_pending"] = True
        return tb

    def _teambattle_node_unlocked(self, node_id: int, tb: dict[str, Any]) -> bool:
        cfg = self.game_data.get("teambattle_nodes", {}).get(str(node_id))
        if not cfg:
            return False
        req = str(cfg.get("needNodeModelID", "")).strip()
        if not req:
            return True
        return int(tb["nodes"].get(req, {}).get("success_count", 0)) > 0

    def _teambattle_chapter_nodes(self, chapter_id: int) -> list[dict[str, Any]]:
        return sorted(
            (
                row
                for row in self.game_data.get("teambattle_nodes", {}).values()
                if int(row.get("chapterModelID", 0)) == chapter_id
            ),
            key=lambda r: int(r["ID"]),
        )

    def _teambattle_chapter_locked_today(self, chapter_id: int, tb: dict[str, Any], today: str, now: int) -> bool:
        for row in self._teambattle_chapter_nodes(chapter_id):
            nst = tb["nodes"].get(str(row["ID"]), {})
            if nst.get("last_clear_date") == today:
                return True
            if nst.get("hold_reward_pending"):
                return True
            if (
                int(nst.get("hold_hero_id", 0)) > 0
                and nst.get("hold_drawn_date") != nst.get("hold_date")
                and now < int(nst.get("hold_end_time", 0))
            ):
                return True
            if nst.get("hold_date") == today and nst.get("hold_drawn_date") == today:
                return True
        return False

    def _teambattle_active_hold_hero_ids(self, tb: dict[str, Any], today: str, now: int) -> list[int]:
        hero_ids: list[int] = []
        for nst in tb["nodes"].values():
            hid = int(nst.get("hold_hero_id", 0))
            if hid <= 0:
                continue
            unclaimed = bool(nst.get("hold_reward_pending")) or (
                nst.get("hold_drawn_date") != nst.get("hold_date") and now < int(nst.get("hold_end_time", 0))
            )
            if unclaimed or nst.get("hold_date") == today:
                if hid not in hero_ids:
                    hero_ids.append(hid)
        return hero_ids

    def _teambattle_node_status_entry(self, node_id: int, tb: dict[str, Any], today: str, now: int) -> dict[str, Any]:
        nst = tb["nodes"].get(str(node_id), {})
        team = tb.get("team")
        in_this_team = bool(team and int(team.get("node_id", 0)) == node_id)
        is_holding = (
            int(nst.get("hold_hero_id", 0)) > 0
            and not nst.get("hold_reward_pending")
            and nst.get("hold_drawn_date") != nst.get("hold_date")
            and now < int(nst.get("hold_end_time", 0))
        )
        hold_reward_can_draw = bool(nst.get("hold_reward_pending"))
        today_holded = bool(nst.get("hold_date") == today and nst.get("hold_drawn_date") == today)
        success_count = int(nst.get("success_count", 0))
        return {
            "NodeModelID": node_id,
            "SuccessFightCount": success_count,
            "TodayIsSuccess": nst.get("last_clear_date") == today,
            "TodayIsHolding": is_holding,
            "TodayIsHolded": today_holded,
            "HoldRewardIsCanDraw": hold_reward_can_draw,
            "IsCanDrawFirstReward": success_count > 0 and not bool(nst.get("first_drawn", False)),
            "HoldEndTime": int(nst.get("hold_end_time", 0)) if is_holding else 0,
            "IsInTeam": in_this_team and not bool(team.get("is_fighting")),
            "IsFight": in_this_team and bool(team.get("is_fighting")),
        }

    def _teambattle_validate_node_entry(self, node_id: int, tb: dict[str, Any]) -> int | None:
        cfg = self.game_data.get("teambattle_nodes", {}).get(str(node_id))
        if not cfg:
            return -48
        if not self._teambattle_node_unlocked(node_id, tb):
            return -7410
        if int(self.state["player"].get("Lv", 1)) < int(cfg.get("needLV", 40)):
            return -7403
        today = self.clock.today_str()
        now = self.now_ts()
        if self._teambattle_chapter_locked_today(int(cfg["chapterModelID"]), tb, today, now):
            return -7409
        return None

    def _teambattle_leader_member(self, node_id: int, fight_add: int = 0) -> dict[str, Any]:
        p = self.state["player"]
        return {
            "kind": "player",
            "PlayerId": str(p["PlayerId"]),
            "Name": str(p["PlayerName"]),
            "Lv": int(p["Lv"]),
            "FAP": int(p["FAP"]),
            "HeadImageId": int(p["HeadImageId"]),
            "FashionModelId": int(p.get("FashionModelId", 0)),
            "IsLeader": 1,
            "FightAdd": fight_add,
            "NodeModelId": node_id,
            "is_closer": False,
        }

    def _teambattle_npc_member(self, npc: dict[str, Any], node_id: int, *, is_closer: bool) -> dict[str, Any]:
        return {
            "kind": "npc",
            "PlayerId": str(npc["Id"]),
            "Name": str(npc["name"]),
            "Lv": int(npc["Lv"]),
            "FAP": int(npc["FAP"]),
            "HeadImageId": int(npc["headImageId"]),
            "FashionModelId": 0,
            "IsLeader": 0,
            "FightAdd": 0,
            "NodeModelId": node_id,
            "is_closer": is_closer,
        }

    def _teambattle_format_teams_info(self, team: dict[str, Any]) -> list[dict[str, Any]]:
        closer_bonus = int(self._teambattle_cfg().get("matchPlayerCloserFAPADD", 5))
        closer_cnt = sum(1 for m in team["members"] if m.get("is_closer") and m.get("IsLeader") != 1)
        fight_add = closer_bonus * closer_cnt
        out: list[dict[str, Any]] = []
        for m in team["members"]:
            out.append({
                "PlayerId": str(m["PlayerId"]),
                "Name": str(m["Name"]),
                "Lv": int(m["Lv"]),
                "FAP": int(m["FAP"]),
                "HeadImageId": int(m["HeadImageId"]),
                "FashionModelId": int(m.get("FashionModelId", 0)),
                "IsLeader": int(m["IsLeader"]),
                "FightAdd": fight_add if int(m["IsLeader"]) == 1 else 0,
                "NodeModelId": int(team["node_id"]),
            })
        return out

    def _teambattle_npcs_for_node(self, node_id: int) -> list[dict[str, Any]]:
        player_fap = int(self.state["player"].get("FAP", 0))
        candidates = [
            row for row in self.game_data.get("teambattle_player_npcs", []) if int(row.get("nodeModelID", 0)) == node_id
        ]
        candidates.sort(key=lambda r: (abs(int(r.get("FAP", 0)) - player_fap), str(r.get("Id", ""))))
        return candidates

    def _teambattle_fill_npc_teammates(self, team: dict[str, Any], *, is_closer: bool) -> None:
        existing_ids = {m["PlayerId"] for m in team["members"]}
        for npc in self._teambattle_npcs_for_node(int(team["node_id"])):
            if len(team["members"]) >= 3:
                break
            if str(npc["Id"]) in existing_ids:
                continue
            team["members"].append(self._teambattle_npc_member(npc, int(team["node_id"]), is_closer=is_closer))
            existing_ids.add(str(npc["Id"]))

    @staticmethod
    def _teambattle_raw_fap(units: list[dict[str, Any]]) -> int:
        return sum(int(u.get("HP", 0)) + 10 * (int(u.get("AP", 0)) + int(u.get("DEF", 0))) for u in units if u)

    def _teambattle_npc_fight_objs(self, npc_player_id: str, fight_add_pct: int = 0) -> list[dict[str, Any]]:
        heroes_cfg = self.game_data["heroes"]
        rows = [
            r for r in self.game_data.get("teambattle_hero_npcs", []) if str(r.get("playerId")) == npc_player_id
        ]
        allies: list[dict[str, Any]] = [{} for _ in range(6)]
        mult = 1.0 + max(0, fight_add_pct) / 100.0
        for row in rows:
            pos = int(row.get("formation", 0))
            if not (1 <= pos <= 6):
                continue
            cfg = heroes_cfg.get(str(row["heroModelId"]))
            if not cfg:
                continue
            stats = {
                "HP": int((int(row["HP"]) + int(row.get("HPAdd", 0))) * mult),
                "AP": int((int(row["AP"]) + int(row.get("APAdd", 0))) * mult),
                "DEF": int((int(row["DEF"]) + int(row.get("DEFAdd", 0))) * mult),
                "RP": int(row.get("RP", 50)),
                "FSP": int(row.get("FSP", 50)),
                "HIT": int(row.get("HIT", 10000)),
                "DOD": int(row.get("DOD", 0)),
                "CRI": int(row.get("CRI", 0)),
                "TEN": int(row.get("TEN", 0)),
                "BLO": int(row.get("BLO", 0)),
                "BOG": int(row.get("BOG", 0)),
                "CRId": int(row.get("CRID", row.get("CRId", 0))),
                "TEND": int(row.get("TEND", 0)),
                "CP": int(row.get("CP", 0)),
                "BCP": int(row.get("BCP", 0)),
                "CPR": int(row.get("CPR", 0)),
                "BCPR": int(row.get("BCPR", 0)),
                "DAMADD": int(row.get("DAMADD", 0)),
                "DAMCUT": int(row.get("DAMCUT", 0)),
                "DAMADDR": int(row.get("DAMADDR", 0)),
                "DAMCUTR": int(row.get("DAMCUTR", 0)),
            }
            allies[pos - 1] = self._hero_fight_obj(
                cfg,
                lv=int(row.get("Lv", 1)),
                is_boss=False,
                step=int(row.get("step", 0)),
                override_stats=stats,
            )
        return allies

    @staticmethod
    def _teambattle_scale_allies(allies: list[dict[str, Any]], fight_add_pct: int) -> list[dict[str, Any]]:
        if fight_add_pct > 0:
            mult = 1.0 + fight_add_pct / 100.0
            for u in allies:
                if not u:
                    continue
                for field in ("HP", "AP", "DEF"):
                    u[field] = max(1, int(u[field] * mult))
                u["TotalHp"] = u["HP"]
        return allies

    def _teambattle_member_fight_objs(self, member: dict[str, Any], fight_add_pct: int = 0) -> list[dict[str, Any]]:
        kind = member.get("kind")
        if kind == "npc":
            return self._teambattle_npc_fight_objs(str(member["PlayerId"]), fight_add_pct=fight_add_pct)
        if kind == "social_npc" and hasattr(self, "_social_npc_fight_objs"):
            units = self._social_npc_fight_objs(str(member["PlayerId"]), fight_add_pct=fight_add_pct)
            return units if units is not None else [{} for _ in range(6)]
        if kind == "guild_npc":
            hm = int(member.get("HeadImageId", 12011004))
            cfg = self.game_data.get("heroes", {}).get(str(hm)) or self.game_data.get("heroes", {}).get("12011004")
            if not cfg:
                return [{} for _ in range(6)]
            mlv = max(1, int(member.get("Lv", 35)))
            mfap = max(10000, int(member.get("FAP", 80000)))
            stats = {
                "HP": max(8000, int(mfap * 0.45)),
                "AP": max(1200, int(mfap * 0.03)),
                "DEF": max(600, int(mfap * 0.02)),
                "RP": 50,
                "FSP": 120,
                "HIT": 10000,
            }
            allies: list[dict[str, Any]] = [{} for _ in range(6)]
            allies[1] = self._hero_fight_obj(cfg, lv=mlv, is_boss=False, step=3, override_stats=stats)
            return self._teambattle_scale_allies(allies, fight_add_pct)
        if kind == "peer":
            peer = self._find_peer_by_player_id(str(member["PlayerId"]))
            if peer is None:
                return [{} for _ in range(6)]
            return self._teambattle_scale_allies(peer._build_ally_fight_objs(), fight_add_pct)
        return self._teambattle_scale_allies(self._build_ally_fight_objs(), fight_add_pct)

    def _teambattle_enemy_formation(self, node_id: int) -> list[dict[str, Any]]:
        """Build the 3 original chapter boss units calibrated against the node's TeambattleHeroNpc squad."""
        node_cfg = self.game_data["teambattle_nodes"][str(node_id)]
        chapter_idx = int(node_cfg["chapterModelID"]) - 10
        main_boss_id = int(node_cfg["heroModelID"])
        need_lv = int(node_cfg.get("needLV", 40))

        # Locate the 3 original chapter bosses (e.g. "百战域boss1") from HeroModel.
        tag = f"百战域boss{chapter_idx}"
        heroes_cfg = self.game_data["heroes"]
        boss_cfgs = sorted(
            (cfg for cfg in heroes_cfg.values() if cfg.get("intro") == tag),
            key=lambda c: (int(c["ID"]) != main_boss_id, int(c["ID"])),
        )
        if not boss_cfgs:
            boss_cfgs = [heroes_cfg[str(main_boss_id)]]

        # Derive per-unit boss baseline from this node's TeambattleHeroNpc rows so HP/AP/DEF/secondary
        # stats stay grounded in VN node difficulty without creating an impenetrable DEF wall.
        npcs = self._teambattle_npcs_for_node(node_id)
        pids = {str(n["Id"]) for n in npcs}
        hrows = [r for r in self.game_data.get("teambattle_hero_npcs", []) if str(r.get("playerId")) in pids]
        if hrows:
            n_rows = len(hrows)
            avg_hp = sum(int(r["HP"]) + int(r.get("HPAdd", 0)) for r in hrows) / n_rows
            avg_ap = sum(int(r["AP"]) + int(r.get("APAdd", 0)) for r in hrows) / n_rows
            avg_def = sum(int(r["DEF"]) + int(r.get("DEFAdd", 0)) for r in hrows) / n_rows
            sec_keys = (
                "HIT", "DOD", "CRI", "TEN", "BLO", "BOG", "CRId", "TEND",
                "CP", "BCP", "CPR", "BCPR", "DAMADD", "DAMCUT", "DAMADDR", "DAMCUTR",
            )
            avg_sec = {
                k: sum(int(r.get("CRID" if k == "CRId" else k, 0)) for r in hrows) // n_rows
                for k in sec_keys
            }
        else:
            propose = float(node_cfg.get("proposeFAP", 300000)) * 0.6
            avg_hp = max(3000.0, propose / 18.0)
            avg_ap = max(400.0, avg_hp / 8.0)
            avg_def = max(200.0, avg_ap * 0.45)
            avg_sec = {"HIT": 11000}

        # Chapter 3 ("Đội hình hàng sau chuyên Công") shields two bosses in the back row; scale slightly
        # lower so cleave-heavy and single-target formations both retain a clearable path.
        ch_factor = 0.85 if chapter_idx == 3 else 1.0
        base_objs = [self._hero_fight_obj(cfg, lv=need_lv, is_boss=(idx == 0)) for idx, cfg in enumerate(boss_cfgs)]
        enemies: list[dict[str, Any]] = [{} for _ in range(6)]
        if len(base_objs) == 1:
            slots_order = [1]
        elif chapter_idx == 3:
            slots_order = [1, 3, 5]
        else:
            slots_order = [1, 0, 2]

        for idx, u in enumerate(base_objs):
            w_hp = 1.4 if idx == 0 else 0.8
            w_ap = 1.15 if idx == 0 else 0.9
            u["HP"] = max(1, round(avg_hp * 5.8 * ch_factor * w_hp))
            u["TotalHp"] = u["HP"]
            u["AP"] = max(1, round(avg_ap * 1.48 * ch_factor * w_ap))
            u["DEF"] = max(1, round(avg_def * 1.0))
            u["RP"] = 50
            for k, val in avg_sec.items():
                u[k] = val
            enemies[slots_order[idx]] = u
        return enemies

    def _teambattle_simulate_battle(self, team: dict[str, Any], seed_token: str) -> tuple[dict[str, Any], bool]:
        node_id = int(team["node_id"])
        closer_bonus = int(self._teambattle_cfg().get("matchPlayerCloserFAPADD", 5))
        closer_cnt = sum(1 for m in team["members"] if m.get("is_closer") and m.get("IsLeader") != 1)
        fight_add = closer_bonus * closer_cnt

        base_enemies = self._teambattle_enemy_formation(node_id)
        enemy_hp: dict[int, int] = {idx + 7: int(u["HP"]) for idx, u in enumerate(base_enemies) if u}
        fight_objs: list[dict[str, Any]] = []
        team_info: list[dict[str, Any]] = []
        is_win = False
        base_seed = 1 + int(seed_token[:8], 16) % 2_000_000_000

        for wave_idx, member in enumerate(team["members"]):
            allies = self._teambattle_member_fight_objs(member, fight_add_pct=fight_add)
            if not any(allies):
                continue
            wave_enemies: list[dict[str, Any]] = [{} for _ in range(6)]
            for idx, tmpl in enumerate(base_enemies):
                pos = idx + 7
                if tmpl and enemy_hp.get(pos, 0) > 0:
                    eu = copy.deepcopy(tmpl)
                    eu["HP"] = enemy_hp[pos]
                    wave_enemies[idx] = eu

            wave_dict = {
                "Heros": allies + wave_enemies,
                "TeamData": [
                    {
                        "Fsp": sum(int(u.get("FSP", 0)) for u in unit if u),
                        "Fap": self._teambattle_raw_fap(unit),
                    }
                    for unit in (allies, wave_enemies)
                ],
                "Pets": [],
                "RandNum": base_seed + wave_idx,
                "IsPVP": False,
            }
            fight_objs.append(wave_dict)
            team_info.append({
                "PlayerId": str(member["PlayerId"]),
                "Name": str(member["Name"]),
                "HeadImageId": int(member["HeadImageId"]),
                "NodeModelId": node_id,
            })

            outcome = simulate_fight_info(
                {"FightObjs": [wave_dict]},
                self.game_data["attacks"],
                buffs_cfg=self.game_data["combat_buffs"],
            )
            for hp_row in outcome.verify_data["hp"][0]:
                pos = int(hp_row["PosId"])
                if pos >= 7:
                    enemy_hp[pos] = max(0, int(hp_row["HP"]))
            if outcome.won:
                is_win = True
                break

        fight_info = {
            "FightObjs": fight_objs,
            "TeamInfo": team_info,
            "IsWinFight": 1 if is_win else 0,
        }
        return fight_info, is_win

    def _teambattle_roll_hold_rewards(self, node_id: int, hero_model_id: int) -> list[tuple[int, int, int]]:
        cfg = self._teambattle_cfg()
        max_hold = int(cfg.get("maxHoldTime", 43200))
        cd = max(1, int(cfg.get("perHoldRewardCD", 1800)))
        ticks = max(1, max_hold // cd)
        drop_rows = sorted(
            (
                row
                for row in self.game_data.get("teambattle_hold_drops", {}).values()
                if int(row.get("nodeModelID", 0)) == node_id
            ),
            key=lambda r: int(r["ID"]),
        )
        merged: dict[tuple[int, int], int] = {}
        if drop_rows:
            max_odds = max(int(r.get("oddsMax", 10000)) for r in drop_rows)
            for _ in range(ticks):
                roll = random.randint(1, max_odds)
                chosen = next(
                    (r for r in drop_rows if int(r["oddsMin"]) <= roll <= int(r["oddsMax"])),
                    drop_rows[0],
                )
                for rtype, rmodel, rnum in _parse_res_tuples(str(chosen.get("dropResource", ""))):
                    merged[(rtype, rmodel)] = merged.get((rtype, rmodel), 0) + rnum

        hero_cfg = self.game_data.get("heroes", {}).get(str(hero_model_id), {})
        debris_ids = hero_cfg.get("debrisModelIds") or []
        if debris_ids:
            debris_mid = int(debris_ids[0])
            hq = int(hero_cfg.get("quality", 13))
            hero_drop_rows = list(self.game_data.get("teambattle_hero_drops", {}).values())
            matching = [r for r in hero_drop_rows if int(r.get("heroQuality", 0)) == hq]
            if not matching and hq >= 15:
                matching = [r for r in hero_drop_rows if int(r.get("heroQuality", 0)) == 15]
            if not matching:
                matching = hero_drop_rows
            if matching:
                weights = [max(1, int(r.get("odds", 1))) for r in matching]
                picked = random.choices(matching, weights=weights, k=1)[0]
                debris_total = int(picked.get("heroDebrisNums", 1)) * int(picked.get("debrisNumsSingle", 1))
                if debris_total > 0:
                    merged[(1501, debris_mid)] = merged.get((1501, debris_mid), 0) + debris_total

        return [(rtype, rmodel, rnum) for (rtype, rmodel), rnum in merged.items() if rnum > 0]

    # -------------------- RPC Handlers --------------------

    def _rpc_teambattle_get_info(self, _data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_sync_holds()
        today = self.clock.today_str()
        now = self.now_ts()
        fight_infos = []
        for nid_str in sorted(self.game_data.get("teambattle_nodes", {}), key=lambda k: int(k)):
            nid = int(nid_str)
            if self._teambattle_node_unlocked(nid, tb):
                fight_infos.append(self._teambattle_node_status_entry(nid, tb, today, now))
        return {
            "IsAllInviteFlg": int(tb.get("all_invite_flag", 0)),
            "NodeModelID": self._teambattle_active_hold_hero_ids(tb, today, now),
            "TeambattleFightinfo": fight_infos,
        }

    def _rpc_teambattle_draw_first_reward(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or not data:
            return self._teambattle_reject(-48)
        node_id = int(data[0])
        cfg = self.game_data.get("teambattle_nodes", {}).get(str(node_id))
        if not cfg:
            return self._teambattle_reject(-48)
        tb = self._teambattle_state()
        nst = tb["nodes"].get(str(node_id))
        if not nst or int(nst.get("success_count", 0)) <= 0 or nst.get("first_drawn"):
            return self._teambattle_reject(-7408)
        rewards = _parse_res_tuples(str(cfg.get("firstReward", "")))

        def claim() -> dict[str, Any]:
            nst["first_drawn"] = True
            base_res = self._grant_resources_from_tuples(
                rewards,
                source="teambattle_first",
                tx_prefix=f"tb_first:{self.profile_name}:{node_id}",
            )
            return {"BaseGetGameResourceList": base_res}

        return self._commit_resource_change(claim)

    def _rpc_teambattle_creat_teams(self, data: Any) -> Any:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or not data:
            return self._teambattle_reject(-48)
        node_id = int(data[0])
        tb = self._teambattle_sync_holds()
        err = self._teambattle_validate_node_entry(node_id, tb)
        if err is not None:
            return self._teambattle_reject(err)
        if tb.get("team") is not None:
            return self._teambattle_reject(-7414)

        team = {
            "team_id": str(uuid.uuid4()),
            "node_id": node_id,
            "leader_id": str(self.state["player"]["PlayerId"]),
            "is_fighting": False,
            "created_at": self.now_ts(),
            "members": [self._teambattle_leader_member(node_id)],
        }
        tb["team"] = team
        self.save()
        return self._teambattle_format_teams_info(team)

    def _rpc_teambattle_fight_for_match(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or not data:
            return self._teambattle_reject(-48)
        node_id = int(data[0])
        tb = self._teambattle_sync_holds()
        err = self._teambattle_validate_node_entry(node_id, tb)
        if err is not None:
            return self._teambattle_reject(err)
        if tb.get("team") is not None:
            return self._teambattle_reject(-7414)

        team = {
            "team_id": str(uuid.uuid4()),
            "node_id": node_id,
            "leader_id": str(self.state["player"]["PlayerId"]),
            "is_fighting": False,
            "created_at": self.now_ts(),
            "members": [self._teambattle_leader_member(node_id)],
        }
        self._teambattle_fill_npc_teammates(team, is_closer=False)
        tb["team"] = team
        self.save()
        return {"TeamsInfo": self._teambattle_format_teams_info(team)}

    def _rpc_teambattle_get_my_team_info(self, _data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_state()
        team = tb.get("team")
        if not team:
            return {"IsInTeam": 0}
        return {"IsInTeam": 1, "TeamsInfo": self._teambattle_format_teams_info(team)}

    def _rpc_teambattle_get_friends_or_guild(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_state()
        team = tb.get("team")
        node_id = int(data[0]) if isinstance(data, list) and data else (int(team["node_id"]) if team else 1111)
        in_team_ids = {m["PlayerId"] for m in team["members"]} if team else set()
        friend_list: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        if hasattr(self, "_social_state"):
            social = self._social_state()
            for fid in social.get("friends", []):
                fid_str = str(fid)
                if fid_str in in_team_ids or fid_str in seen_ids:
                    continue
                kind, card, _ = self._social_resolve_player(fid_str)
                if kind in ("peer", "npc"):
                    seen_ids.add(fid_str)
                    friend_list.append(
                        {
                            "PlayerId": fid_str,
                            "Name": str(card["Name"]),
                            "Lv": int(card["Lv"]),
                            "FAP": int(card["FAP"]),
                            "HeadImageId": int(card["HeadImageId"]),
                        }
                    )
        for npc in self._teambattle_npcs_for_node(node_id):
            pid = str(npc["Id"])
            if pid in in_team_ids or pid in seen_ids:
                continue
            seen_ids.add(pid)
            friend_list.append(
                {
                    "PlayerId": pid,
                    "Name": str(npc["name"]),
                    "Lv": int(npc["Lv"]),
                    "FAP": int(npc["FAP"]),
                    "HeadImageId": int(npc["headImageId"]),
                }
            )
        guild_list = (
            [g for g in self._guild_teammate_candidates(in_team_ids) if str(g["PlayerId"]) not in in_team_ids]
            if hasattr(self, "_guild_teammate_candidates")
            else []
        )
        return {"GuildPlayer": guild_list, "FriendPlayer": friend_list}

    def _rpc_teambattle_invite_friends(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or len(data) < 2:
            return self._teambattle_reject(-48)
        tb = self._teambattle_state()
        team = tb.get("team")
        if not team:
            return self._teambattle_reject(-7411)
        if len(team["members"]) >= 3:
            return self._teambattle_reject(-7420)
        target_pid = str(data[1])
        if any(m["PlayerId"] == target_pid for m in team["members"]):
            return self._teambattle_reject(-7414)
        node_id = int(team["node_id"])
        npc = next(
            (n for n in self._teambattle_npcs_for_node(node_id) if str(n["Id"]) == target_pid),
            None,
        )
        if npc is not None:
            team["members"].append(self._teambattle_npc_member(npc, node_id, is_closer=True))
        elif hasattr(self, "_social_state") and target_pid in {str(x) for x in self._social_state().get("friends", [])}:
            kind, card, _ = self._social_resolve_player(target_pid)
            if kind not in ("peer", "npc"):
                return self._teambattle_reject(-7413)
            team["members"].append(
                {
                    "kind": "peer" if kind == "peer" else "social_npc",
                    "PlayerId": target_pid,
                    "Name": str(card["Name"]),
                    "Lv": int(card["Lv"]),
                    "FAP": int(card["FAP"]),
                    "HeadImageId": int(card["HeadImageId"]),
                    "FashionModelId": int(card.get("FashionModelId", 0)),
                    "IsLeader": 0,
                    "FightAdd": 0,
                    "NodeModelId": node_id,
                    "is_closer": True,
                }
            )
        elif hasattr(self, "_guild_member_lookup") and self._guild_member_lookup(target_pid) is not None:
            gm = self._guild_member_lookup(target_pid)
            assert gm is not None
            peer = self._find_peer_by_player_id(target_pid)
            team["members"].append(
                {
                    "kind": "peer" if peer is not None else "guild_npc",
                    "PlayerId": target_pid,
                    "Name": str(gm.get("Name", "")),
                    "Lv": int(gm.get("Lv", 1)),
                    "FAP": int(gm.get("FAP", 0)),
                    "HeadImageId": int(gm.get("HeadImageId", 12011004)),
                    "FashionModelId": int(gm.get("FashionModelId", 0)),
                    "IsLeader": 0,
                    "FightAdd": 0,
                    "NodeModelId": node_id,
                    "is_closer": True,
                }
            )
        else:
            return self._teambattle_reject(-7413)
        self.save()
        return {"TeamsInfo": self._teambattle_format_teams_info(team)}

    def _rpc_teambattle_invite_one_key(self, _data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_state()
        team = tb.get("team")
        if not team:
            return self._teambattle_reject(-7411)
        self._teambattle_fill_npc_teammates(team, is_closer=True)
        self.save()
        return {"TeamsInfo": self._teambattle_format_teams_info(team)}

    def _rpc_teambattle_invite_all(self, _data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_state()
        team = tb.get("team")
        if not team:
            return self._teambattle_reject(-7411)
        self._teambattle_fill_npc_teammates(team, is_closer=False)
        self.save()
        return {"TeamsInfo": self._teambattle_format_teams_info(team)}

    def _rpc_teambattle_kick_out_team(self, data: Any) -> Any:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_state()
        team = tb.get("team")
        if not team:
            return self._teambattle_reject(-7411)
        target_pid = str(data[0]) if isinstance(data, list) and data else ""
        if not target_pid or target_pid == team["leader_id"]:
            return self._teambattle_reject(-7422)
        kept = [m for m in team["members"] if m["PlayerId"] != target_pid]
        if len(kept) == len(team["members"]):
            return self._teambattle_reject(-7422)
        team["members"] = kept
        self.save()
        return self._teambattle_format_teams_info(team)

    def _rpc_teambattle_dismiss_team(self, _data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_state()
        if tb.get("team") is None:
            return self._teambattle_reject(-7411)
        tb["team"] = None
        self.save()
        return {}

    def _rpc_teambattle_update_all_invite_flag(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        flag = 1 if (isinstance(data, list) and data and int(data[0])) else 0
        tb = self._teambattle_state()
        tb["all_invite_flag"] = flag
        self.save()
        return {"IsAllInviteFlg": flag}

    def _rpc_teambattle_get_invite_info(self, _data: Any) -> dict[str, Any]:
        return {"InviteInfo": []}

    def _rpc_teambattle_inter_team(self, _data: Any) -> dict[str, Any]:
        return self._teambattle_reject(-7417)

    def _rpc_teambattle_fight(self, _data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_sync_holds()
        team = tb.get("team")
        if not team:
            return self._teambattle_reject(-7411)
        if len(team.get("members", [])) < 3:
            return self._teambattle_reject(-7421)
        node_id = int(team["node_id"])
        err = self._teambattle_validate_node_entry(node_id, tb)
        if err is not None:
            return self._teambattle_reject(err)

        token = uuid.uuid4().hex
        fight_info, is_win = self._teambattle_simulate_battle(team, token)
        teams_info = self._teambattle_format_teams_info(team)
        node_cfg = self.game_data["teambattle_nodes"][str(node_id)]
        today = self.clock.today_str()

        def settle() -> dict[str, Any]:
            tb["team"] = None
            self._record_daily_task_progress(34, 1)
            base_res: list[dict[str, Any]] = []
            if is_win:
                nst = tb["nodes"].setdefault(str(node_id), {})
                nst["success_count"] = int(nst.get("success_count", 0)) + 1
                nst["last_clear_date"] = today
                rewards = _parse_res_tuples(str(node_cfg.get("fightRewards", "")))
                if rewards:
                    base_res = self._grant_resources_from_tuples(
                        rewards,
                        source="teambattle_fight",
                        tx_prefix=f"tb_fight:{self.profile_name}:{node_id}:{token}",
                    )
            return {
                "TeamsInfo": teams_info,
                "FightInfo": fight_info,
                "BaseGetGameResourceList": base_res,
            }

        return self._commit_resource_change(settle)

    def _rpc_teambattle_hero_hold(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or len(data) < 2:
            return self._teambattle_reject(-48)
        node_id, hero_model_id = int(data[0]), int(data[1])
        node_cfg = self.game_data.get("teambattle_nodes", {}).get(str(node_id))
        if not node_cfg:
            return self._teambattle_reject(-48)
        tb = self._teambattle_sync_holds()
        today = self.clock.today_str()
        now = self.now_ts()
        nst = tb["nodes"].setdefault(str(node_id), {})
        if nst.get("last_clear_date") != today:
            return self._teambattle_reject(-7402)
        if nst.get("hold_reward_pending"):
            return self._teambattle_reject(-7406)
        if int(nst.get("hold_hero_id", 0)) > 0 and nst.get("hold_drawn_date") != nst.get("hold_date"):
            return self._teambattle_reject(-7404)
        if nst.get("hold_date") == today and nst.get("hold_drawn_date") == today:
            return self._teambattle_reject(-7405)

        hero_cfg = self.game_data.get("heroes", {}).get(str(hero_model_id))
        owns_hero = any(int(h.get("HeroModelId", 0)) == hero_model_id for h in self.state.get("heroes", []))
        if not hero_cfg or not owns_hero or int(hero_cfg.get("starNum", 0)) != 5 or int(hero_cfg.get("specialType", 0)) == 255:
            return self._teambattle_reject(-7418)
        if hero_model_id in self._teambattle_active_hold_hero_ids(tb, today, now):
            return self._teambattle_reject(-7419)

        cfg = self._teambattle_cfg()
        need_vit = int(cfg.get("needVIT", 20))
        player = self.state["player"]
        if int(player.get("VIT", 0)) < need_vit:
            return self._teambattle_reject(-1119)
        max_hold = int(cfg.get("maxHoldTime", 43200))

        def start_hold() -> dict[str, Any]:
            self.ledger.apply_player_delta(player, self.profile_name, "VIT", -need_vit, source="teambattle_hold")
            nst["hold_hero_id"] = hero_model_id
            nst["hold_date"] = today
            nst["hold_end_time"] = now + max_hold
            nst["hold_reward_pending"] = False
            self._inc_stat("teambattle_count", 1)
            return {"HoldInfo": {"HeroModelID": hero_model_id, "HoldEndTime": nst["hold_end_time"]}}

        return self._commit_resource_change(start_hold)

    def _rpc_teambattle_get_hold_info(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or not data:
            return self._teambattle_reject(-48)
        node_id = int(data[0])
        tb = self._teambattle_sync_holds()
        nst = tb["nodes"].get(str(node_id), {})
        return {
            "HoldInfo": {
                "HeroModelID": int(nst.get("hold_hero_id", 0)),
                "HoldEndTime": int(nst.get("hold_end_time", 0)),
            }
        }

    def _rpc_teambattle_draw_hold_reward(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or not data:
            return self._teambattle_reject(-48)
        node_id = int(data[0])
        tb = self._teambattle_sync_holds()
        nst = tb["nodes"].get(str(node_id))
        if not nst or not nst.get("hold_reward_pending"):
            return self._teambattle_reject(-7407)
        hero_model_id = int(nst.get("hold_hero_id", 0))
        rewards = self._teambattle_roll_hold_rewards(node_id, hero_model_id)
        today = self.clock.today_str()

        def claim() -> dict[str, Any]:
            nst["hold_reward_pending"] = False
            nst["hold_drawn_date"] = nst.get("hold_date", today)
            nst["hold_end_time"] = 0
            base_res = self._grant_resources_from_tuples(
                rewards,
                source="teambattle_hold_reward",
                tx_prefix=f"tb_hold:{self.profile_name}:{node_id}:{uuid.uuid4()}",
            )
            return {"BaseGetGameResourceList": base_res}

        return self._commit_resource_change(claim)

    def _rpc_teambattle_quick_draw_hold_reward(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or not data:
            return self._teambattle_reject(-48)
        node_id = int(data[0])
        tb = self._teambattle_sync_holds()
        now = self.now_ts()
        today = self.clock.today_str()
        nst = tb["nodes"].get(str(node_id))
        if not nst or int(nst.get("hold_hero_id", 0)) <= 0 or nst.get("hold_drawn_date") == nst.get("hold_date"):
            return self._teambattle_reject(-7407)
        remaining = max(0, int(nst.get("hold_end_time", 0)) - now)
        if remaining <= 0:
            return self._rpc_teambattle_draw_hold_reward([node_id])
        cfg = self._teambattle_cfg()
        cost = int(cfg.get("holdTimeOver", 10)) * (remaining // 3600 + 1)
        player = self.state["player"]
        if int(player.get("Diamond", 0)) < cost:
            return self._teambattle_reject(-1105)
        rewards = self._teambattle_roll_hold_rewards(node_id, int(nst["hold_hero_id"]))

        def quick_claim() -> dict[str, Any]:
            if cost > 0:
                self.ledger.apply_player_delta(player, self.profile_name, "Diamond", -cost, source="teambattle_quick_hold")
                self._last_rpc_context["diamond_spent"] = cost
            nst["hold_reward_pending"] = False
            nst["hold_drawn_date"] = nst.get("hold_date", today)
            nst["hold_end_time"] = 0
            base_res = self._grant_resources_from_tuples(
                rewards,
                source="teambattle_quick_hold_reward",
                tx_prefix=f"tb_qhold:{self.profile_name}:{node_id}:{uuid.uuid4()}",
            )
            return {"BaseGetGameResourceList": base_res}

        return self._commit_resource_change(quick_claim)

    def _rpc_teambattle_shop_info(self, _data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        tb = self._teambattle_state()
        return {
            "BuyShopInfo": [
                {"Id": int(sid), "Num": int(cnt)}
                for sid, cnt in sorted(tb.get("shop", {}).items(), key=lambda kv: int(kv[0]))
            ]
        }

    def _rpc_teambattle_buy_shop(self, data: Any) -> dict[str, Any]:
        if not self._teambattle_is_open():
            return self._teambattle_reject(-1127)
        if not isinstance(data, list) or len(data) < 2:
            return self._teambattle_reject(-48)
        shop_id = int(data[0])
        count = int(data[1])
        if count <= 0:
            return self._teambattle_reject(-48)
        row = self.game_data.get("teambattle_shop", {}).get(str(shop_id))
        if not row:
            return self._teambattle_reject(-42)
        tb = self._teambattle_state()
        bought = int(tb["shop"].get(str(shop_id), 0))
        max_num = int(row.get("totalMaxNum", 0))
        if max_num > 0 and bought + count > max_num:
            return self._teambattle_reject(-2104)
        unit_price = int(row.get("needTeamBattleCoins", 0))
        total_cost = unit_price * count
        coin_item = next(
            (g for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == TEAMBATTLE_GEM_COIN_ID),
            None,
        )
        if not coin_item or int(coin_item.get("Num", 0)) < total_cost:
            return self._teambattle_reject(-1602)
        base_out = _parse_res_tuples(str(row.get("outResource", "")))
        rewards = [(rtype, rmodel, rnum * count) for rtype, rmodel, rnum in base_out]
        if not rewards or not all(self._is_valid_resource(rtype, rmodel) for rtype, rmodel, _ in rewards):
            return self._teambattle_reject(-1605)

        def purchase() -> dict[str, Any]:
            coin_item["Num"] = int(coin_item["Num"]) - total_cost
            if coin_item["Num"] <= 0:
                self.state["goods"] = [g for g in self.state["goods"] if g["Id"] != coin_item["Id"]]
            self.ledger.record_grant_event(
                account_id=str(self.state["player"]["PlayerId"]),
                profile=self.profile_name,
                resource_type=f"Goods:{TEAMBATTLE_GEM_COIN_ID}",
                amount=-total_cost,
                balance_after=max(0, int(coin_item.get("Num", 0))),
                source="teambattle_shop_cost",
                idempotency_key=f"tb_shop_cost:{self.profile_name}:{shop_id}:{uuid.uuid4()}",
            )
            self._mark_goods_changed(TEAMBATTLE_GEM_COIN_ID)
            tb["shop"][str(shop_id)] = bought + count
            base_res = self._grant_resources_from_tuples(
                rewards,
                source="teambattle_shop",
                tx_prefix=f"tb_shop:{self.profile_name}:{shop_id}:{uuid.uuid4()}",
            )
            return {
                "BaseGetGameResourceList": base_res,
                "BuyShopInfo": self._rpc_teambattle_shop_info([])["BuyShopInfo"],
            }

        return self._commit_resource_change(purchase)
