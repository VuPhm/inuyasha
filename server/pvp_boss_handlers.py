"""Boss (`LuckBoss`), Arena (`PVP` / `PVPShop`), Daydayfund & StartWork handlers extracted from emulator.py."""

from __future__ import annotations

import copy
import json
import math
import random
import time
from typing import Any
import uuid

from combat_sim import simulate_fight_info
from emulator_common import (
    EMPTY_ENTITY_ID,
    _det_uuid,
    _parse_resource_str,
    _zero_slot_property,
)


class PvpBossHandlersMixin:
    """Mixin hosting Boss, Arena PVP, Daydayfund, and StartWork RPC handlers."""

    def _sync_boss_battle_state(self) -> dict[str, Any]:
        """Recover LuckBoss attack charges over time and prune defeated/expired bosses."""
        now = int(time.time())
        lb_cfg = self.game_data.get("luckboss_config", {})
        rec_cd = max(60, int(lb_cfg.get("attackNumRecoverTime", 1800)))
        vip_lv = int(self.state["player"].get("VIPLv", 0))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        max_atk = max(10, int(vip_cfg.get("attackLuckBossMaxNum", 10)))

        bs = self.state["boss_battle"]
        bs["bosses"] = [
            b for b in bs.get("bosses", []) if int(b.get("CurHP", 0)) > 0 and int(b.get("AwayTime", 0)) > now
        ]
        for b in bs["bosses"]:
            self._sanitize_boss_drop(b)
        atk_num = int(bs.get("attack_num", 10))
        rec_time = int(bs.get("recover_time", now + rec_cd))
        if atk_num < max_atk:
            if rec_time <= now:
                gained = 1 + (now - rec_time) // rec_cd
                atk_num = min(max_atk, atk_num + gained)
                bs["attack_num"] = atk_num
                bs["recover_time"] = (now + rec_cd) if atk_num < max_atk else now
            elif rec_time > now + rec_cd:
                bs["recover_time"] = now + rec_cd
        else:
            bs["recover_time"] = now
        bs["jifen"] = int(self.state["player"].get("BossCoin", bs.get("jifen", 0)))
        if "battle" in self.state:
            self.state["battle"]["HasBoss"] = "True" if bs["bosses"] else "False"
        return bs

    def _luckboss_is_double_jifen(self) -> bool:
        """Check LuckbossConfig double-point window (default 18:00-20:00 local time)."""
        lb_cfg = self.game_data.get("luckboss_config", {})
        begin_frac = float(lb_cfg.get("valueDoubleBeginTime1", 0.75))
        end_frac = float(lb_cfg.get("valueDoubleEndTime2", 0.833333333333))
        lt = time.localtime()
        frac = (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec) / 86400.0
        return begin_frac <= frac <= end_frac

    def _boss_info_payload(self, bs: dict[str, Any]) -> dict[str, Any]:
        return {
            "AttackNum": int(bs.get("attack_num", 0)),
            "RecoverTime": int(bs.get("recover_time", int(time.time()) + 1800)),
            "BuyCount": int(bs.get("buy_count", 0)),
            "JiFen": int(bs.get("jifen", 0)),
            "NextBoss": {
                "NCount": int(bs.get("next_boss_count", 10)),
                "BossModelId": int(bs.get("next_boss_model_id", 12010055)),
            },
        }

    def _maybe_trigger_luckboss(self, force: bool = False) -> str | None:
        """Spawn a LuckBoss on Lv>=18 battle victory (strictly inactive below Lv 18)."""
        lv = int(self.state["player"].get("Lv", 1))
        if lv < 18:
            return None
        bs = self._sync_boss_battle_state()
        bs["clear_counter"] = int(bs.get("clear_counter", 0)) + 1
        if len(bs["bosses"]) >= 3 and not force:
            return None

        ncount = int(bs.get("next_boss_count", 10))
        should_spawn = force or bs["clear_counter"] == 1 or ncount <= 1 or random.randint(1, 100) <= 35
        if not should_spawn:
            bs["next_boss_count"] = max(1, ncount - 1)
            return None

        if ncount <= 1 or bs["clear_counter"] % 5 == 0:
            model_id = int(bs.get("next_boss_model_id", 12010055))
            bs["next_boss_count"] = 10
            bs["next_boss_model_id"] = 12010055 if model_id == 12010054 else 12010054
        else:
            bs["next_boss_count"] = max(1, ncount - 1)
            tier_pool = [12010050, 12010051, 12010052] if lv < 25 else [12010051, 12010052, 12010053, 12010054]
            model_id = random.choice(tier_pool)

        tier_idx = max(0, model_id - 12010050)
        boss_lv = max(18, lv + min(3, tier_idx))
        hero_cfg = self.game_data["heroes"].get(str(model_id), self.game_data["heroes"]["12010050"])
        hp_mult = 18.0 + tier_idx * 6.0
        boss_obj = self._hero_fight_obj(
            hero_cfg,
            lv=boss_lv,
            is_boss=True,
            hp_mult=hp_mult,
            ap_mult=1.2 + tier_idx * 0.2,
            def_mult=1.1 + tier_idx * 0.15,
        )
        drop_res = self._boss_drop_for_model(model_id)
        now = int(time.time())
        boss_entry = {
            "Id": str(uuid.uuid4()),
            "PlayerId": str(self.state["player"]["PlayerId"]),
            "PlayerName": str(self.state["player"]["PlayerName"]),
            "BossModelId": model_id,
            "Name": f"Yêu Vương Bậc {tier_idx + 1}",
            "Lv": boss_lv,
            "CurHP": int(boss_obj["TotalHp"]),
            "TotalHP": int(boss_obj["TotalHp"]),
            "AwayTime": now + 7200,
            "CanHelpTime": 0,
            "DropResource": drop_res,
        }
        bs["bosses"].append(boss_entry)
        if "battle" in self.state:
            self.state["battle"]["HasBoss"] = "True"
        return boss_entry["Id"]

    def _build_boss_fight_info(self, boss: dict[str, Any], is_full: bool) -> dict[str, Any]:
        allies = self._build_ally_fight_objs()
        if is_full:
            up_r = float(self.game_data.get("luckboss_config", {}).get("alloutAttackAttrUpR", 30000)) / 10000.0
            for unit in allies:
                if unit:
                    unit["AP"] = max(1, int(unit.get("AP", 1) * up_r))
                    unit["RP"] = 100
        model_id = int(boss.get("BossModelId", 12010050))
        tier_idx = max(0, model_id - 12010050)
        cfg = self.game_data["heroes"].get(str(model_id), self.game_data["heroes"]["12010050"])
        boss_unit = self._hero_fight_obj(
            cfg,
            lv=int(boss.get("Lv", 18)),
            is_boss=True,
            hp_mult=18.0 + tier_idx * 6.0,
            ap_mult=1.2 + tier_idx * 0.2,
            def_mult=1.1 + tier_idx * 0.15,
        )
        boss_unit["TotalHp"] = int(boss["TotalHP"])
        boss_unit["HP"] = int(boss["CurHP"])
        enemies: list[dict[str, Any]] = [{}, boss_unit, {}, {}, {}, {}]
        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        enemy_fsp = int(boss_unit.get("FSP", 500))
        return {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": ally_fsp, "Fap": int(self.state["player"].get("FAP", 0))},
                        {"Fsp": enemy_fsp, "Fap": int(boss_unit["TotalHp"] + boss_unit["AP"] * 10 + boss_unit.get("DEF", 0) * 10)},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1, 999999),
                    "IsPVP": False,
                }
            ]
        }

    def _rpc_boss_get_boss_list(self, _data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        self.save()
        return {"BattleInfo": self._boss_info_payload(bs), "BossList": copy.deepcopy(bs["bosses"])}

    def _rpc_boss_get_boss_info(self, data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        boss_id = str(data[0]) if isinstance(data, list) and data else ""
        boss = next((b for b in bs["bosses"] if str(b["Id"]) == boss_id), None)
        if not boss:
            self._last_rpc_context["status"] = -1
            return {}
        return {"BattleInfo": self._boss_info_payload(bs), "BossInfo": copy.deepcopy(boss)}

    def _rpc_boss_get_fight_info(self, data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        boss_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        is_full = bool(int(data[1])) if isinstance(data, list) and len(data) >= 2 else False
        boss = next((b for b in bs["bosses"] if str(b["Id"]) == boss_id and int(b.get("CurHP", 0)) > 0), None)
        need_atk = 3 if is_full else 1
        need_vit = 15 if is_full else 5
        if not boss or int(bs["attack_num"]) < need_atk or int(self.state["player"].get("VIT", 0)) < need_vit:
            self._last_rpc_context["status"] = -1
            return {}
        fight_info = self._build_boss_fight_info(boss, is_full)
        bs["pending_fight"] = {"boss_id": boss["Id"], "is_full": is_full, "fight_info": fight_info}
        self.save()
        return {"FightInfo": fight_info}

    def _rpc_boss_fight(self, data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        boss_id = str(data[0]) if isinstance(data, list) and len(data) >= 1 else ""
        is_full = bool(int(data[1])) if isinstance(data, list) and len(data) >= 2 else False
        verify_raw = data[3] if isinstance(data, list) and len(data) >= 4 else None

        boss = next((b for b in bs["bosses"] if str(b["Id"]) == boss_id and int(b.get("CurHP", 0)) > 0), None)
        need_atk = 3 if is_full else 1
        need_vit = 15 if is_full else 5
        if not boss or int(bs["attack_num"]) < need_atk or int(self.state["player"].get("VIT", 0)) < need_vit:
            self._last_rpc_context["status"] = -1
            return {}

        bs["attack_num"] = int(bs["attack_num"]) - need_atk
        self._sync_boss_battle_state()
        self.ledger.apply_player_delta(
            self.state["player"], self.profile_name, "VIT", -need_vit, source=f"boss_vit:{boss_id}"
        )

        old_hp = int(boss["CurHP"])
        sim_boss_hp: int | None = None
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
                            sim_boss_hp = int(unit_hp.get("HP", old_hp))
                            break
        if sim_boss_hp is None:
            pending = bs.pop("pending_fight", None)
            if isinstance(pending, dict) and pending.get("boss_id") == boss_id and bool(pending.get("is_full")) == is_full:
                fight_info = pending["fight_info"]
            else:
                fight_info = self._build_boss_fight_info(boss, is_full)
            outcome = simulate_fight_info(fight_info, self.game_data["attacks"], buffs_cfg=self.game_data["combat_buffs"])
            last_wave = outcome.verify_data.get("hp", [[]])[-1]
            sim_boss_hp = next((int(u["HP"]) for u in last_wave if int(u.get("PosId", 0)) == 8), old_hp)
        else:
            bs.pop("pending_fight", None)

        new_hp = max(0, min(old_hp, int(sim_boss_hp)))
        hurt = old_hp - new_hp
        boss["CurHP"] = new_hp
        boss_exist = new_hp > 0
        if not boss_exist:
            bs["bosses"] = [b for b in bs["bosses"] if str(b["Id"]) != boss_id]

        jifen_gain = max(15, hurt // 150) + (120 if not boss_exist else 0)
        if self._luckboss_is_double_jifen():
            jifen_gain *= 2

        old_lv = int(self.state["player"]["Lv"])
        per_exp_pct = int(self.game_data.get("vit_config", {}).get("perGetEXPR", 20000))
        exp_gain = int(need_vit * old_lv * (per_exp_pct / 10000.0))
        tuples: list[tuple[int, int, int]] = [
            (1101, 0, exp_gain),
            (1112, 0, 1200 * need_atk),
            (1117, 0, 600 * need_atk),
            (1120, 0, jifen_gain),
        ]
        if not boss_exist and isinstance(boss.get("DropResource"), dict):
            dr = self._sanitize_boss_drop(boss)
            tuples.append((int(dr["TypeId"]), int(dr["ModelId"]), int(dr.get("Num", 1))))

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"boss_fight:{boss['BossModelId']}",
            tx_prefix=f"boss:{self.profile_name}:{boss_id}:{uuid.uuid4()}",
        )
        self.validate_base_resource_list(base_res, context="BossBattle.Fight")
        old_lv2, new_lv2 = self._sync_level_from_exp()
        if new_lv2 != old_lv2:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True

        self._inc_stat("boss_fights", need_atk)
        self._record_daily_task_progress(7, need_atk)
        self.save()
        return {
            "HurtValue": hurt,
            "SingleJiFen": jifen_gain,
            "BossExist": boss_exist,
            "BaseGetGameResourceList": base_res,
        }

    def _rpc_boss_box_list(self, _data: Any) -> list[dict[str, Any]]:
        bs = self._sync_boss_battle_state()
        drawn = set(int(x) for x in bs.get("drawn_boxes", []))
        rows = sorted(self.game_data.get("luckboss_value_shop", {}).values(), key=lambda r: int(r["needValue"]))
        return [
            {"NeedValue": int(row["needValue"]), "IsDraw": "True" if int(row["needValue"]) in drawn else "False"}
            for row in rows
        ]

    def _rpc_boss_draw_box(self, data: Any) -> dict[str, Any]:
        need_val = int(data[0]) if isinstance(data, list) and data else 0
        bs = self._sync_boss_battle_state()
        drawn = bs.setdefault("drawn_boxes", [])
        row = next(
            (r for r in self.game_data.get("luckboss_value_shop", {}).values() if int(r["needValue"]) == need_val),
            None,
        )
        if not row or need_val in drawn or int(bs.get("jifen", 0)) < need_val:
            self._last_rpc_context["status"] = -1
            return {}
        drawn.append(need_val)
        base_res = self._grant_resources_from_tuples(
            [(int(row["typeID"]), int(row["modelID"]), int(row["num"]))],
            source=f"boss_box:{need_val}",
            tx_prefix=f"boss_box:{self.profile_name}:{need_val}:{uuid.uuid4()}",
        )
        self.validate_base_resource_list(base_res, context="BossBattle.DrawBox")
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_boss_one_key_draw_box(self, _data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        jifen = int(bs.get("jifen", 0))
        drawn = bs.setdefault("drawn_boxes", [])
        rows = sorted(self.game_data.get("luckboss_value_shop", {}).values(), key=lambda r: int(r["needValue"]))
        tuples: list[tuple[int, int, int]] = []
        for row in rows:
            nv = int(row["needValue"])
            if nv <= jifen and nv not in drawn:
                drawn.append(nv)
                tuples.append((int(row["typeID"]), int(row["modelID"]), int(row["num"])))
        if not tuples:
            self._last_rpc_context["status"] = -1
            return {}
        base_res = self._grant_resources_from_tuples(
            tuples,
            source="boss_one_key_box",
            tx_prefix=f"boss_box_all:{self.profile_name}:{uuid.uuid4()}",
        )
        self.validate_base_resource_list(base_res, context="BossBattle.OneKeyDrawBox")
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_boss_buy_count(self, data: Any) -> dict[str, Any]:
        count = max(1, min(20, int(data[0]) if isinstance(data, list) and data else 1))
        bs = self._sync_boss_battle_state()
        vip_lv = int(self.state["player"].get("VIPLv", 0))
        vip_cfg = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        allow_buy = int(vip_cfg.get("allowBuyLuckBossFightNum", 10))
        cur_buy = int(bs.get("buy_count", 0))
        if cur_buy + count > allow_buy:
            self._last_rpc_context["status"] = -1
            return {}
        base_price = int(self.game_data.get("luckboss_config", {}).get("buyAttackNumBaseUseNum", 10))
        cost = sum(math.ceil((cur_buy + step) / 2) * base_price for step in range(1, count + 1))
        if int(self.state["player"].get("Diamond", 0)) < cost:
            self._last_rpc_context["status"] = -1
            return {}
        if cost > 0:
            self.ledger.apply_player_delta(
                self.state["player"], self.profile_name, "Diamond", -cost, source=f"boss_buy_count:{count}"
            )
        bs["buy_count"] = cur_buy + count
        bs["attack_num"] = int(bs.get("attack_num", 0)) + count
        self._sync_boss_battle_state()
        self.save()
        return {"BuyCount": int(bs["buy_count"]), "AttackNum": int(bs["attack_num"])}

    def _rpc_boss_friend_help(self, data: Any) -> dict[str, Any]:
        bs = self._sync_boss_battle_state()
        boss_id = str(data[0]) if isinstance(data, list) and data else ""
        boss = next((b for b in bs["bosses"] if str(b["Id"]) == boss_id), None)
        if not boss:
            self._last_rpc_context["status"] = -1
            return {}
        now = int(time.time())
        boss["CanHelpTime"] = now + 60
        social = self._social_state()
        for fid in social.get("friends", []):
            peer = self._find_peer_by_player_id(str(fid))
            if peer is not None:
                p_info = self.state["player"]
                with peer._lock:
                    peer._push_player_email(
                        1,
                        "Hỗ trợ Yêu Vương",
                        f"{p_info.get('PlayerName', 'Bạn bè')} kêu gọi hỗ trợ đánh Yêu Vương!",
                        send_player_id=str(p_info["PlayerId"]),
                        send_player_name=str(p_info.get("PlayerName", "Bạn bè")),
                        sub_module_id=2203,
                        head_image_id=0,
                        fashion_model_id=0,
                    )
                    peer.save()
        self.save()
        return {"CanHelpTime": int(boss["CanHelpTime"])}

    def _rpc_boss_jifen_ranking(self, _data: Any) -> list[dict[str, Any]]:
        bs = self._sync_boss_battle_state()
        p = self.state["player"]
        rows = [
            {
                "PlayerId": str(p["PlayerId"]),
                "Name": str(p["PlayerName"]),
                "Lv": int(p["Lv"]),
                "FAP": int(p.get("FAP", 0)),
                "JiFen": int(bs.get("jifen", 0)),
                "HeadImageId": int(p.get("HeadImageId", 12011004)),
            }
        ]
        npc_jifens = [3600, 2900, 2350, 1800, 1400, 950, 620, 380, 210]
        step = self._pvp_step_for_lv(int(p.get("Lv", 18)))
        for idx, score in enumerate(npc_jifens, start=1):
            bot = self._arena_bot_profile(idx * 50, step)
            rows.append(
                {
                    "PlayerId": bot["PlayerId"],
                    "Name": bot["Name"],
                    "Lv": bot["Lv"],
                    "FAP": bot["FAP"],
                    "JiFen": score,
                    "HeadImageId": bot["Slots"][0]["HeroModelId"],
                }
            )
        rows.sort(key=lambda r: (-int(r["JiFen"]), -int(r["FAP"])))
        for rank_idx, r in enumerate(rows, start=1):
            r["Id"] = rank_idx
        return rows

    @staticmethod
    def _pvp_step_for_lv(lv: int) -> int:
        if lv <= 30:
            return 1
        if lv <= 40:
            return 2
        if lv <= 50:
            return 3
        if lv <= 60:
            return 4
        return 5

    @staticmethod
    def _pvp_reward_window() -> tuple[int, int]:
        now_dt = time.localtime()
        midnight = int(time.time()) - (now_dt.tm_hour * 3600 + now_dt.tm_min * 60 + now_dt.tm_sec)
        start = midnight + 22 * 3600
        end = start + 300
        now = int(time.time())
        if now >= start:
            start += 86400
            end += 86400
        return start, end

    def _arena_bot_profile(self, rank: int, step: int) -> dict[str, Any]:
        """Deterministically construct a realistic Arena bot built from real heroes & equips."""
        rank = max(1, min(2000, int(rank)))
        step = max(1, min(5, int(step)))
        names = [
            "PhongKhuyển", "BạchSát", "TửVu", "HắcCửu", "KhuyểnDạXoa",
            "NgọcTứHồn", "PhongChiThủ", "MinhĐạoTàn", "ThiếtToáiNha", "ThiênSinhNha",
            "BấtYêuVương", "LamNgọc", "XíchNguyệt", "ĐoạnKiếm", "LôiThú",
            "HồĐiệpẢo", "VôẢnhNhẫn", "DạMaLâm", "BăngTinh", "ThanhLongẨn",
            "CổTỉnh", "PhongHuyệt", "TửTâm", "NgânLang", "HồngLiên",
            "TuyếtNữ", "ThầnLạc", "CànThú", "HoàngTuyền", "KỳLânẨn",
        ]
        guilds = ["Chiến Quốc", "Tây Quốc", "Hội Trừ Yêu", "Làng Phong", ""]
        base_lv_min = {1: 18, 2: 31, 3: 41, 4: 51, 5: 61}[step]
        base_lv_max = {1: 30, 2: 40, 3: 50, 4: 60, 5: 75}[step]
        # Stronger bots sit at lower numeric rank (rank 1 = strongest, rank 1500+ = entry Lv)
        ratio = max(0.0, min(1.0, (1600 - rank) / 1599.0))
        bot_lv = min(80, max(16, int(round(base_lv_min + (base_lv_max - base_lv_min) * (ratio ** 1.35)))))

        if rank <= 20:
            slot_count = 6
            step_up = 3 + step
            eq_tier = min(7, 5 + (step >= 3))
            hero_pool = [12011004, 12012005, 12011002, 12011003, 12011005, 12011007, 12011008, 12011020]
        elif rank <= 200:
            slot_count = 5
            step_up = 2 + step
            eq_tier = 5
            hero_pool = [12011004, 12011005, 12011006, 12011007, 12011008, 12011011, 12011019, 12011022]
        elif rank <= 900:
            slot_count = 5 if bot_lv >= 22 else 4
            step_up = 1 + step
            eq_tier = 4
            hero_pool = [12011005, 12011006, 12011007, 12011009, 12011012, 12011014, 12011016, 12011018]
        elif rank <= 1350:
            slot_count = 4
            step_up = 1
            eq_tier = 3
            hero_pool = [12011009, 12011012, 12011013, 12011023, 12011024, 12011026, 12011028, 12011030]
        else:
            slot_count = 3 if rank >= 1480 else 4
            step_up = 0 if rank >= 1460 else 1
            eq_tier = 2 if rank >= 1460 else 3
            hero_pool = [12011023, 12011025, 12011027, 12011033, 12011034, 12011035, 12011036, 12011037]

        equip_by_color = {
            1: (13010130, 13020130, 13030130, 13040130),
            2: (13010215, 13020215, 13030215, 13040215),
            3: (13010314, 13020314, 13030314, 13040314),
            4: (13010404, 13020404, 13030404, 13040404),
            5: (13010503, 13020503, 13030503, 13040503),
            6: (13010602, 13020602, 13030602, 13040602),
            7: (13010701, 13020701, 13030701, 13040701),
        }
        eq_set = equip_by_color.get(eq_tier, equip_by_color[3])
        eq_lv = max(1, int(bot_lv * (1.5 if rank <= 200 else 1.0 if rank <= 1350 else 0.5)))

        rng = random.Random(step * 10000 + rank)
        chosen_models = [hero_pool[(rank + i * 3 + rng.randint(0, 2)) % len(hero_pool)] for i in range(slot_count)]
        # Deduplicate while keeping order
        seen_m: set[int] = set()
        unique_models: list[int] = []
        for hm in chosen_models + hero_pool:
            if hm not in seen_m and str(hm) in self.game_data["heroes"]:
                seen_m.add(hm)
                unique_models.append(hm)
            if len(unique_models) >= slot_count:
                break

        bot_player_id = _det_uuid(f"arena_bot:{step}:{rank}")
        slots: list[dict[str, Any]] = []
        heroes_by_id: dict[str, dict[str, Any]] = {}
        embattle: dict[str, int] = {f"Formation{i}": 0 for i in range(1, 7)}
        total_fap = 0
        for s_idx in range(1, 7):
            if s_idx <= len(unique_models):
                hm = unique_models[s_idx - 1]
                h_id = _det_uuid(f"bot_hero:{step}:{rank}:{s_idx}")
                h_inst = self._build_hero_instance(hm, lv=bot_lv, step=step_up, inst_id=h_id)
                heroes_by_id[h_id] = h_inst
                eq_keys = ("Weapon", "Helmet", "Clothes", "Necklace")
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
                for ek_idx, ek in enumerate(eq_keys):
                    em_id = eq_set[ek_idx]
                    slot[ek] = {
                        "Id": _det_uuid(f"bot_eq:{step}:{rank}:{s_idx}:{ek}"),
                        "EquipModelId": em_id,
                        "Lv": eq_lv,
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
                    "Property": _zero_slot_property(),
                }
            slots.append(slot)

        base_name = names[(rank + step * 7) % len(names)]
        bot_name = base_name if rank <= 30 else f"{base_name}{rank}"
        return {
            "PlayerId": bot_player_id,
            "Lv": bot_lv,
            "Name": bot_name,
            "FAP": total_fap,
            "Rank": rank,
            "Step": step,
            "Guild": guilds[(rank + step) % len(guilds)],
            "FashionModelId": 0,
            "Slots": slots,
            "Embattle": embattle,
            "HeroesById": heroes_by_id,
        }

    def _build_bot_formation_view(self, bot: dict[str, Any]) -> dict[str, Any]:
        return {
            "PlayerInfo": {
                "PlayerId": bot["PlayerId"],
                "Name": bot["Name"],
                "Lv": bot["Lv"],
                "StarId": 0,
                "FashionModelId": int(bot.get("FashionModelId", 0)),
                "FAP": bot["FAP"],
            },
            "SlotInfo": bot["Slots"],
            "SlotInfos": bot["Slots"],
            "MateInfos": [],
            "SlotFormationInfo": bot["Embattle"],
            "SkillInfos": [],
            "CombatPet": None,
        }

    def _bot_slot_formations(self, target_id: str) -> dict[str, Any] | None:
        p = self.state["player"]
        cur_step = self._pvp_step_for_lv(int(p.get("Lv", 20)))
        for st in (cur_step, 1, 2, 3, 4, 5):
            # Probe current rank list candidates & top 50 quickly
            pvp = self.state.get("pvp", {})
            probe_ranks = list(range(1, 31)) + list(range(50, 2001, 50))
            pr = int(pvp.get("rank", 1500))
            probe_ranks.extend(self._candidate_arena_ranks(pr, int(pvp.get("refresh_seed", 1))))
            for r in set(probe_ranks):
                if _det_uuid(f"arena_bot:{st}:{r}") == target_id:
                    return self._build_bot_formation_view(self._arena_bot_profile(r, st))
        return self._gddh_bot_slot_formations(target_id) or self._social_npc_slot_formations(target_id)

    def _arena_bot_fight_objs(self, bot: dict[str, Any]) -> list[dict[str, Any]]:
        enemies: list[dict[str, Any]] = [{} for _ in range(6)]
        slots_by_id = {int(s["SlotId"]): s for s in bot["Slots"]}
        emb = bot["Embattle"]
        heroes_by_id = bot["HeroesById"]
        for f_idx in range(1, 7):
            s_id = int(emb.get(f"Formation{f_idx}", f_idx))
            slot = slots_by_id.get(s_id)
            if slot and slot.get("HeroModelId"):
                hm = int(slot["HeroModelId"])
                cfg = self.game_data["heroes"][str(hm)]
                inst = heroes_by_id.get(str(slot["HeroId"]), {})
                enemies[f_idx - 1] = self._hero_fight_obj(
                    cfg,
                    is_boss=False,
                    step=int(inst.get("Step", 0)),
                    reborn_step=int(inst.get("RebornStep", 0)),
                    reborn_id=int(inst.get("RebornId", 0)),
                    override_stats=slot["Property"],
                    fashion_model_id=int(bot.get("FashionModelId", 0)),
                )
        return enemies

    def _candidate_arena_ranks(self, player_rank: int, refresh_seed: int) -> list[int]:
        if player_rank <= 1:
            return [1, 2, 3, 4, 5, 6]
        ranks: set[int] = {1, 2, 3, player_rank}
        rng = random.Random(player_rank * 97 + refresh_seed)
        if player_rank <= 15:
            for r in range(1, min(21, player_rank + 4)):
                ranks.add(r)
        else:
            step_spans = [320, 210, 140, 90, 55, 32, 18, 8, 1]
            prev = player_rank
            for idx, delta in enumerate(step_spans):
                jitter = rng.randint(0, max(0, delta // 4)) if idx < len(step_spans) - 1 else 0
                cand = max(4, min(prev - 1, player_rank - delta + jitter))
                ranks.add(cand)
                prev = cand
            ranks.add(min(2000, player_rank + 1))
            ranks.add(min(2000, player_rank + 2))
        return sorted(r for r in ranks if 1 <= r <= 2000)

    def _self_arena_entry(self, rank: int) -> dict[str, Any]:
        p = self.state["player"]
        slot_heroes = [
            {"Id": int(s["SlotId"]), "HeroModelId": int(s["HeroModelId"])}
            for s in self.state["slots"]
            if int(s.get("HeroModelId", 0)) > 0
        ]
        return {
            "PlayerId": str(p["PlayerId"]),
            "Lv": int(p["Lv"]),
            "Name": str(p["PlayerName"]),
            "FAP": int(p.get("FAP", 0)),
            "Rank": rank,
            "Guild": "",
            "FashionModelId": int(p.get("FashionModelId", 0)),
            "IfAllowRank": 0,
            "SlotHeroModelIdList": slot_heroes,
        }

    def _build_arena_rank_list(self, step: int, player_rank: int, refresh_seed: int) -> list[dict[str, Any]]:
        ranks_set = set(self._candidate_arena_ranks(player_rank, refresh_seed))
        for peer in self._get_peer_s1_profiles():
            pr = int(peer.state.get("pvp", {}).get("rank", 1500))
            if 1 <= pr <= 2000:
                ranks_set.add(pr)
        ranks = sorted(ranks_set)
        out: list[dict[str, Any]] = []
        for r in ranks:
            if r == player_rank:
                out.append(self._self_arena_entry(r))
            else:
                allow = 1 if (r < player_rank and (r >= 4 or player_rank <= 20)) else 0
                peer = self._find_peer_by_arena_rank(r)
                if peer is not None:
                    entry = peer._self_arena_entry(r)
                    entry["IfAllowRank"] = allow
                    out.append(entry)
                else:
                    bot = self._arena_bot_profile(r, step)
                    out.append(
                        {
                            "PlayerId": bot["PlayerId"],
                            "Lv": bot["Lv"],
                            "Name": bot["Name"],
                            "FAP": bot["FAP"],
                            "Rank": r,
                            "Guild": bot["Guild"],
                            "FashionModelId": bot["FashionModelId"],
                            "IfAllowRank": allow,
                            "SlotHeroModelIdList": [
                                {"Id": int(s["SlotId"]), "HeroModelId": int(s["HeroModelId"])}
                                for s in bot["Slots"]
                                if int(s.get("HeroModelId", 0)) > 0
                            ],
                        }
                    )
        out.sort(key=lambda item: int(item["Rank"]))
        return out

    def _pvp_current_reward(self, step: int, rank: int) -> list[dict[str, int]]:
        step_tbl = self.game_data.get("pvp_rank_reward", {}).get(str(step), {})
        row = step_tbl.get(str(min(2000, max(1, rank))), {"PVPCoin": 100, "rawGold": 500})
        return [
            {"ResourceTypeSub": 1115, "ModelId": 0, "Num": int(row.get("PVPCoin", 100))},
            {"ResourceTypeSub": 1112, "ModelId": 0, "Num": int(row.get("rawGold", 500))},
        ]

    def _pvp_shop_list_payload(self) -> list[dict[str, Any]]:
        pvp = self.state["pvp"]
        today = self.clock.today_str()
        daily_map = pvp.setdefault("shop_bought_daily", {})
        if daily_map.get("_date") != today:
            daily_map.clear()
            daily_map["_date"] = today
        total_map = pvp.setdefault("shop_bought_total", {})
        items = sorted(self.game_data.get("pvp_shop", {}).values(), key=lambda x: int(x["ID"]))
        out: list[dict[str, Any]] = []
        for row in items:
            sid = int(row["ID"])
            out.append(
                {
                    "ShopId": sid,
                    "TypeId": int(row["typeID"]),
                    "ModelId": int(row["modelID"]),
                    "Num": int(row["num"]),
                    "NeedStep": int(row["needStep"]),
                    "NeedRank": int(row["needRank"]),
                    "NeedPVPCoin": int(row["needPVPCoin"]),
                    "PerMaxNum": int(row["perMaxNum"]),
                    "TotalMaxNum": int(row["totalMaxNum"]),
                    "BuyNum": int(daily_map.get(str(sid), 0)),
                    "BuyTotalNum": int(total_map.get(str(sid), 0)),
                }
            )
        return out

    def _calc_upgrade_rank_diamonds(self, old_rank: int, old_step: int, new_rank: int) -> int:
        if new_rank >= old_rank:
            return 0
        first_tbl = self.game_data.get("pvp_first_reward", {})

        def _reward_at(step: int, rank: int) -> int:
            rec = first_tbl.get(str(step), {}).get(str(rank))
            if not rec and step > 1:
                rec = first_tbl.get(str(step - 1), {}).get("1")
            if not rec:
                return 0
            total = 0
            for rt, _rm, cnt in _parse_resource_str(str(rec.get("firstReward", ""))):
                if rt == 1111:
                    total += cnt
            return total

        return max(0, _reward_at(old_step, new_rank) - _reward_at(old_step, old_rank))

    def _rpc_pvp_get_info(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        pvp = self.state["pvp"]
        step = self._pvp_step_for_lv(int(p.get("Lv", 20)))
        if step > int(pvp.get("history_max_step", 1)):
            pvp["history_max_step"] = step
        rank = int(pvp.get("rank", 1500))
        r_start, r_end = self._pvp_reward_window()
        self.save()
        return {
            "RefreshDate": int(pvp.get("refresh_date", 0)),
            "PVPCoin": int(p.get("PVPCoin", 0)),
            "RewardTimeStart": r_start,
            "RewardTimeEnd": r_end,
            "Rank": rank,
            "HistoryMaxStep": int(pvp.get("history_max_step", step)),
            "HistoryMaxRank": int(pvp.get("history_max_rank", rank)),
            "CurrentReward": self._pvp_current_reward(step, rank),
            "RankList": self._build_arena_rank_list(step, rank, int(pvp.get("refresh_seed", 1))),
            "PVPShopInfo": self._pvp_shop_list_payload(),
        }

    def _rpc_pvp_refresh(self, _data: Any) -> dict[str, Any]:
        pvp = self.state["pvp"]
        now = int(time.time())
        if now < int(pvp.get("refresh_date", 0)):
            self._last_rpc_context["status"] = -1
            return {}
        pvp["refresh_seed"] = int(pvp.get("refresh_seed", 1)) + 1
        pvp["refresh_date"] = now + 5
        step = self._pvp_step_for_lv(int(self.state["player"].get("Lv", 20)))
        rank = int(pvp.get("rank", 1500))
        self.save()
        return {
            "RefreshDate": int(pvp["refresh_date"]),
            "RankList": self._build_arena_rank_list(step, rank, int(pvp["refresh_seed"])),
        }

    def _rpc_pvp_fight(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        pvp = self.state["pvp"]
        lv = int(p.get("Lv", 1))
        if lv < 20 or not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        target_id = str(data[0])
        target_rank = int(data[1])
        sta_cost = int(self.game_data.get("sta_config", {}).get("perUseNum", 2))
        if int(p.get("STA", 0)) < sta_cost:
            self._last_rpc_context["status"] = -1
            return {}

        step = self._pvp_step_for_lv(lv)
        peer = self._find_peer_by_player_id(target_id) or self._find_peer_by_arena_rank(target_rank)
        if peer is not None:
            target_rank = int(peer.state.get("pvp", {}).get("rank", target_rank))
            target_pid = str(peer.state["player"]["PlayerId"])
            target_name = str(peer.state["player"].get("PlayerName", "Peer"))
            target_fap = int(peer.state["player"].get("FAP", 0))
            enemies = peer._build_ally_fight_objs()
        else:
            bot = self._arena_bot_profile(target_rank, step)
            if bot["PlayerId"] != target_id:
                # Resolve matching bot rank if client sent slightly stale rank
                for probe in self._candidate_arena_ranks(int(pvp.get("rank", 1500)), int(pvp.get("refresh_seed", 1))):
                    cand = self._arena_bot_profile(probe, step)
                    if cand["PlayerId"] == target_id:
                        bot = cand
                        target_rank = probe
                        break
            target_pid = str(bot["PlayerId"])
            target_name = str(bot["Name"])
            target_fap = int(bot["FAP"])
            enemies = self._arena_bot_fight_objs(bot)

        allies = self._build_ally_fight_objs()
        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        enemy_fsp = sum(int(u.get("FSP", 0)) for u in enemies if u)
        fight_info = {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": ally_fsp, "Fap": int(p.get("FAP", 0))},
                        {"Fsp": enemy_fsp, "Fap": target_fap},
                    ],
                    "Pets": [],
                    "RandNum": random.randint(1, 999999),
                    "IsPVP": True,
                }
            ]
        }

        self.ledger.apply_player_delta(p, self.profile_name, "STA", -sta_cost, source=f"pvp_sta:{target_rank}")
        outcome = simulate_fight_info(fight_info, self.game_data["attacks"], buffs_cfg=self.game_data["combat_buffs"])
        is_win = 1 if outcome.won else 0
        self._inc_stat("pvp_fights", 1)
        self._record_daily_task_progress(5, 1)
        if is_win:
            self._inc_stat("pvp_wins", 1)

        old_rank = int(pvp.get("rank", 1500))
        old_max_rank = int(pvp.get("history_max_rank", old_rank))
        new_rank = min(old_rank, target_rank) if is_win else old_rank
        pvp["rank"] = new_rank
        if is_win and peer is not None:
            if getattr(peer, "is_remote_peer", False):
                pvp["arena_score"] = int(pvp.get("arena_score", 1000)) + 15
                self._enqueue_hybrid_event(
                    target_pid,
                    "pvp_challenge_log",
                    {
                        "attacker_name": str(p.get("PlayerName", "Đối thủ")),
                        "attacker_fap": int(p.get("FAP", 0)),
                        "old_rank": old_rank,
                        "new_rank": new_rank,
                        "won": True,
                    },
                )
            elif target_rank < old_rank:
                with peer._lock:
                    peer_pvp = peer.state.setdefault("pvp", {})
                    peer_pvp["rank"] = old_rank
                    peer._push_player_email(
                        2,
                        "Chiến báo Đấu Trường",
                        f"{p.get('PlayerName', 'Đối thủ')} đã đánh bại bạn tại Đấu Trường (Hạng {target_rank} → {old_rank}).",
                        send_player_id=str(p["PlayerId"]),
                        send_player_name=str(p.get("PlayerName", "Đối thủ")),
                        sub_module_id=2502,
                        head_image_id=0,
                        fashion_model_id=0,
                    )
                    peer.save()

        breakthrough_diamond = 0
        if is_win and new_rank < old_max_rank:
            breakthrough_diamond = self._calc_upgrade_rank_diamonds(old_max_rank, step, new_rank)
            pvp["history_max_rank"] = new_rank
        if step > int(pvp.get("history_max_step", 1)):
            pvp["history_max_step"] = step

        per_exp_pct = int(self.game_data.get("sta_config", {}).get("perGetEXPR", 20000))
        exp_gain = int(sta_cost * lv * (per_exp_pct / 10000.0))
        arena_mult = self._timed_welfare_mult(4413, default=1)
        pvp_coin_gain = ((40 + max(0, (1600 - target_rank) // 100)) if is_win else 15) * arena_mult
        gold_gain = (1500 + lv * 50) if is_win else 500
        tuples: list[tuple[int, int, int]] = [
            (1101, 0, exp_gain),
            (1115, 0, pvp_coin_gain),
            (1112, 0, gold_gain),
        ]
        if breakthrough_diamond > 0:
            tuples.append((1111, 0, breakthrough_diamond))

        choice_cards: list[dict[str, Any]] = []
        if is_win:
            tuples.append((1605, 16050001, 5))
            choice_cards = [
                {"ResourceTypeSub": 1605, "ModelId": 16050001, "Num": 5, "IsDrop": 1},
                {"ResourceTypeSub": 1112, "ModelId": 0, "Num": 5000, "IsDrop": 0},
                {"ResourceTypeSub": 1115, "ModelId": 0, "Num": 30, "IsDrop": 0},
            ]

        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"pvp_fight:{target_rank}:{'win' if is_win else 'lose'}",
            tx_prefix=f"pvp:{self.profile_name}:{target_rank}:{uuid.uuid4()}",
        )
        old_lv2, new_lv2 = self._sync_level_from_exp()
        if new_lv2 != old_lv2:
            self._last_rpc_context["lv_changed"] = True
            self._last_rpc_context["slots_changed"] = True

        history = pvp.setdefault("history", [])
        history.append(
            {
                "Timestamp": int(time.time()),
                "TargetPlayerId": target_pid,
                "TargetName": target_name,
                "TargetRank": target_rank,
                "OldRank": old_rank,
                "NewRank": new_rank,
                "IsWin": is_win,
                "DiamondBonus": breakthrough_diamond,
            }
        )
        if len(history) > 30:
            pvp["history"] = history[-30:]

        self.save()
        return {
            "Rank": new_rank,
            "HistoryMaxRank": int(pvp["history_max_rank"]),
            "HistoryMaxStep": int(pvp["history_max_step"]),
            "PVPCoin": int(p.get("PVPCoin", 0)),
            "IsWinFight": is_win,
            "RankList": self._build_arena_rank_list(step, new_rank, int(pvp.get("refresh_seed", 1))),
            "CurrentReward": self._pvp_current_reward(step, new_rank),
            "BaseGetGameResourceList": base_res,
            "ChoiceGetGameResource": choice_cards,
            "FightInfo": fight_info,
        }

    def _rpc_pvp_top_rank_list(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        pvp = self.state["pvp"]
        my_step = self._pvp_step_for_lv(int(p.get("Lv", 20)))
        my_rank = int(pvp.get("rank", 1500))
        top_steps: list[dict[str, Any]] = []
        for st in range(1, 6):
            rank_entries: list[dict[str, Any]] = []
            for r in range(1, 21):
                if st == my_step and r == my_rank:
                    rank_entries.append(self._self_arena_entry(r))
                else:
                    peer = self._find_peer_by_arena_rank(r) if st == my_step else None
                    if peer is not None:
                        rank_entries.append(peer._self_arena_entry(r))
                    else:
                        bot = self._arena_bot_profile(r, st)
                        rank_entries.append(
                            {
                                "PlayerId": bot["PlayerId"],
                                "Lv": bot["Lv"],
                                "Name": bot["Name"],
                                "FAP": bot["FAP"],
                                "Rank": r,
                                "Guild": bot["Guild"],
                                "FashionModelId": 0,
                                "IfAllowRank": 0,
                                "SlotHeroModelIdList": [
                                    {"Id": int(s["SlotId"]), "HeroModelId": int(s["HeroModelId"])}
                                    for s in bot["Slots"]
                                    if int(s.get("HeroModelId", 0)) > 0
                                ],
                            }
                        )
            top_steps.append({"RankList": rank_entries})
        return {"TopRankList": top_steps}

    def _rpc_pvp_shop_buy(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or len(data) < 2:
            self._last_rpc_context["status"] = -1
            return {}
        shop_id = int(data[0])
        num = max(1, int(data[1]))
        row = self.game_data.get("pvp_shop", {}).get(str(shop_id))
        if not row:
            self._last_rpc_context["status"] = -1
            return {}

        p = self.state["player"]
        pvp = self.state["pvp"]
        step = self._pvp_step_for_lv(int(p.get("Lv", 20)))
        need_step = int(row.get("needStep", 1))
        need_rank = int(row.get("needRank", 0))
        if step < need_step or (step == need_step and need_rank > 0 and int(pvp.get("history_max_rank", 1500)) > need_rank):
            self._last_rpc_context["status"] = -1
            return {}

        today = self.clock.today_str()
        daily_map = pvp.setdefault("shop_bought_daily", {})
        if daily_map.get("_date") != today:
            daily_map.clear()
            daily_map["_date"] = today
        total_map = pvp.setdefault("shop_bought_total", {})
        cur_daily = int(daily_map.get(str(shop_id), 0))
        cur_total = int(total_map.get(str(shop_id), 0))
        per_max = int(row.get("perMaxNum", 0))
        tot_max = int(row.get("totalMaxNum", 0))
        if per_max > 0 and cur_daily + num > per_max:
            self._last_rpc_context["status"] = -1
            return {}
        if tot_max > 0 and cur_total + num > tot_max:
            self._last_rpc_context["status"] = -1
            return {}

        cost = int(row.get("needPVPCoin", 0)) * num
        if int(p.get("PVPCoin", 0)) < cost:
            self._last_rpc_context["status"] = -1
            return {}
        if cost > 0:
            self.ledger.apply_player_delta(p, self.profile_name, "PVPCoin", -cost, source=f"pvp_shop:{shop_id}")
        daily_map[str(shop_id)] = cur_daily + num
        total_map[str(shop_id)] = cur_total + num

        base_res = self._grant_resources_from_tuples(
            [(int(row["typeID"]), int(row["modelID"]), int(row["num"]) * num)],
            source=f"pvp_shop_buy:{shop_id}",
            tx_prefix=f"pvp_shop:{self.profile_name}:{shop_id}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_pvp_shop_reset_daily(self, _data: Any = None) -> dict[str, Any]:
        """Reset daily Arena shop limits (perMaxNum) while preserving one-time totalMaxNum purchases."""
        pvp = self.state.setdefault("pvp", {})
        pvp["shop_bought_daily"] = {"_date": self.clock.today_str()}
        self.save()
        return {"PVPShopList": self._pvp_shop_list_payload()}

    def _rpc_daydayfund_get_info(self, _data: Any) -> dict[str, Any]:
        df = self.state["daydayfund"]
        return {
            "Multiple": int(df.get("last_multiple", 0)),
            "CooledTime": int(df.get("cooled_time", 0)),
            "IfDraw": bool(df.get("if_draw", True)),
            "HarvestList": list(df.get("harvest_list", []))[-10:],
        }

    def _rpc_daydayfund_invest(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        lv = int(p.get("Lv", 1))
        df = self.state["daydayfund"]
        if lv < 19 or not bool(df.get("if_draw", True)):
            self._last_rpc_context["status"] = -1
            return {}
        dm = self.game_data.get("daydayfund_model", {})
        base_fund = int(dm.get("baseFund", 100))
        if int(p.get("Gold", 0)) < base_fund:
            self._last_rpc_context["status"] = -1
            return {}
        self.ledger.apply_player_delta(p, self.profile_name, "Gold", -base_fund, source="daydayfund_invest")
        m_min = int(dm.get("multipleMin", 30)) * lv
        m_max = int(dm.get("multipleMax", 60)) * lv
        mult = random.randint(m_min, max(m_min, m_max))
        df["last_multiple"] = mult
        df["cooled_time"] = 0
        df["if_draw"] = False
        self._inc_stat("daydayfund_count", 1)
        self.save()
        return {
            "Multiple": mult,
            "CooledTime": 0,
            "IfDraw": False,
            "HarvestList": list(df.get("harvest_list", []))[-10:],
        }

    def _rpc_daydayfund_harvest(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        df = self.state["daydayfund"]
        now = int(time.time())
        if bool(df.get("if_draw", True)) or now < int(df.get("cooled_time", 0)):
            self._last_rpc_context["status"] = -1
            return {}
        dm = self.game_data.get("daydayfund_model", {})
        base_fund = int(dm.get("baseFund", 100))
        mult = max(1, int(df.get("last_multiple", 30)))
        vip_lv = int(p.get("VIPLv", 0))
        vip_row = self.game_data.get("daydayfund_vip", {}).get(str(vip_lv), {})
        vip_pct = int(vip_row.get("mutipleR", 100)) / 100.0
        gold_gain = int(base_fund * mult * vip_pct)
        tuples: list[tuple[int, int, int]] = [(1112, 0, gold_gain)]
        if mult % 10 == 8:
            tuples.extend(_parse_resource_str(str(dm.get("specialReward", "1111,0,50"))))
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"daydayfund_harvest:{mult}",
            tx_prefix=f"daydayfund:{self.profile_name}:{uuid.uuid4()}",
        )
        h_list = df.setdefault("harvest_list", [])
        h_list.append({"PlayerName": str(p["PlayerName"]), "Multiple": mult})
        if len(h_list) > 20:
            df["harvest_list"] = h_list[-20:]
        df["if_draw"] = True
        df["last_multiple"] = 0
        df["cooled_time"] = 0
        self.save()
        return {
            "Multiple": mult,
            "CooledTime": 0,
            "IfDraw": True,
            "HarvestList": list(df["harvest_list"])[-10:],
            "BaseGetGameResourceList": base_res,
        }

    def _startwork_schedule(self) -> dict[str, dict[str, Any]]:
        return {
            str(d): {
                "Diamond": 50 * d,
                "Multiple": 2 if d == 1 else 1,
                "Resource": [{"ResourceTypeSub": 1112, "ModelId": 0, "Count": 10000 * d}],
            }
            for d in (1, 2, 3, 4)
        }

    def _rpc_startwork_get_info(self, _data: Any) -> dict[str, Any]:
        return {"StartWorkReward": [self._startwork_schedule()]}

    def _rpc_startwork_get_reward(self, _data: Any) -> dict[str, Any]:
        sw = self.state["startwork"]
        today = self.clock.today_str()
        claimed = sw.setdefault("claimed_days", [])
        if today in claimed:
            self._last_rpc_context["status"] = -1
            return {}
        wday = self.clock.weekday()  # 1=Mon .. 7=Sun
        sched = self._startwork_schedule()
        entry = sched.get(str(wday if 1 <= wday <= 4 else 1))
        tuples = [(1111, 0, int(entry["Diamond"]) * int(entry["Multiple"]))]
        for r in entry["Resource"]:
            tuples.append((int(r["ResourceTypeSub"]), int(r["ModelId"]), int(r["Count"])))
        claimed.append(today)
        base_res = self._grant_resources_from_tuples(
            tuples,
            source=f"startwork:{today}",
            tx_prefix=f"startwork:{self.profile_name}:{today}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}
