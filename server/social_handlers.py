"""Bạn Bè (`Friend`, `FriendMessage`, `Enemy`) & Hộp Thư (`PlayerEmail`) handlers for VN 5.0.4.98."""

from __future__ import annotations

import uuid
from typing import Any

EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"
FRIEND_STA_PER_DRAW = 2
FRIEND_STA_DRAW_DAILY_MAX = 20
FRIEND_NPC_COUNT = 24
FRIEND_MSG_MAX_LEN = 200

_FRIEND_NPC_NAMES: tuple[str, ...] = (
    "Khuyển Dạ Xoa",
    "Sát Sinh Hoàn",
    "A Ly",
    "Cát Cánh",
    "Di Lặc",
    "San Hô",
    "Thất Bảo",
    "Cương Nha",
    "Nại Lạc",
    "Thần Lạc",
    "Thần Vô",
    "Bạch Đồng Tử",
    "Hổ Phách",
    "Vân Mẫu",
    "Minh Gia",
    "Đao Đao Trai",
    "Long Cốt Tinh",
    "Man Cốt",
    "Xà Cốt",
    "Ngân Cốt",
    "Phong Dạ",
    "Lăng Nguyệt",
    "Tứ Đấu Thần",
    "KaguraVN",
)

_FRIEND_NPC_REPLIES: tuple[str, ...] = (
    "Chúc bạn đi ải thuận lợi, nhớ nhận Hoạt Lực mình tặng nhé!",
    "Hôm nay cùng tổ đội Phó Bản săn trang bị xịn nào!",
    "Đã nhận được tin nhắn của bạn, hẹn gặp lại ở Đấu Trường!",
    "Tứ Hồn Ngọc đang chờ chúng ta thu thập, cố lên nhé!",
)

_FALLBACK_HERO_POOL: tuple[int, ...] = (
    12011002,
    12011003,
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
    12013004,
    12013005,
)


def _det_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"inuyasha.revival.{seed}"))


class SocialHandlersMixin:
    """Offline server emulation for Friend, FriendMessage, Enemy, and PlayerEmail."""

    # -------------------- State & Daily Sync --------------------

    @staticmethod
    def _ensure_social_container(state: dict[str, Any]) -> dict[str, Any]:
        social = state.setdefault("social", {})
        social.setdefault("friends", [])
        social.setdefault("enemies", [])
        social.setdefault("sta_date", "")
        social.setdefault("sta_sent_today", [])
        social.setdefault("sta_draw_count", 0)
        social.setdefault("sta_inbox", [])
        social.setdefault("friend_messages", [])
        social.setdefault("emails", [])
        unread = social.setdefault("unread", {})
        unread.setdefault("system", False)
        unread.setdefault("battle", False)
        unread.setdefault("friend", False)
        social.setdefault("welcome_seeded", False)
        social.setdefault("recommend_seed", 0)
        return social

    def _sync_social_daily(self) -> bool:
        """Roll daily STA counters, seed NPC STA gifts, and ensure welcome email once."""
        social = self._ensure_social_container(self.state)
        changed = False
        now = self.now_ts()
        today = self.clock.today_str()

        if social.get("sta_date") != today:
            social["sta_date"] = today
            social["sta_sent_today"] = []
            social["sta_draw_count"] = 0
            inbox_pids = {str(item.get("PlayerId", "")) for item in social["sta_inbox"]}
            for fid in social["friends"]:
                fid_str = str(fid)
                if len(social["sta_inbox"]) >= FRIEND_STA_DRAW_DAILY_MAX:
                    break
                if self._social_npc_index(fid_str) is not None and fid_str not in inbox_pids:
                    social["sta_inbox"].append({"PlayerId": fid_str, "SendTime": now})
                    inbox_pids.add(fid_str)
            changed = True

        if not social.get("welcome_seeded"):
            social["welcome_seeded"] = True
            self._append_email_record(
                social,
                email_type=1,
                subject="Chào mừng đến với Khuyển Dạ Xoa",
                content=(
                    "Chào mừng Đại Hiệp đến với thế giới Khuyển Dạ Xoa VN!\n"
                    "Hãy kết bạn để tặng và nhận Hoạt Lực mỗi ngày, lập tổ đội chinh phục Phó Bản."
                ),
                send_player_id=EMPTY_ENTITY_ID,
                send_player_name="InuYasha VN",
                sub_module_id=0,
                head_image_id=0,
                fashion_model_id=0,
            )
            changed = True

        return changed

    def _social_state(self) -> dict[str, Any]:
        self._sync_social_daily()
        return self._ensure_social_container(self.state)

    def _friend_max_for_lv(self, lv: int) -> int:
        lv_tbl = self.game_data.get("player_lv", {})
        clamped = max(1, min(100, int(lv)))
        row = lv_tbl.get(str(clamped)) or {}
        return max(10, int(row.get("friendMax", 10)))

    # -------------------- Hero & NPC Profile Pool --------------------

    def _social_playable_heroes(self) -> list[int]:
        heroes_cfg = self.game_data.get("heroes", {})
        pool = [
            int(hid)
            for hid, row in sorted(heroes_cfg.items(), key=lambda x: int(x[0]))
            if int(hid) >= 12011000
            and int(row.get("specialType", 0)) != 255
            and int(row.get("quality", 0)) >= 10
            and str(row.get("largePic", "")).strip()
            and "boss" not in str(row.get("intro", "")).lower()
        ]
        return pool if pool else [h for h in _FALLBACK_HERO_POOL if str(h) in heroes_cfg] or [12011004]

    @staticmethod
    def _social_npc_index(player_id: str) -> int | None:
        pid = str(player_id)
        for idx in range(1, FRIEND_NPC_COUNT + 1):
            if _det_uuid(f"friend_npc:{idx}") == pid:
                return idx
        return None

    def _social_npc_profile(self, idx: int, base_lv: int | None = None) -> dict[str, Any]:
        player_lv = int(self.state.get("player", {}).get("Lv", 20)) if base_lv is None else int(base_lv)
        offsets = (-4, -2, -1, 0, 1, 2, 3, 5, -3, 4, 2, -5)
        npc_lv = max(5, min(80, player_lv + offsets[(idx - 1) % len(offsets)]))
        pool = self._social_playable_heroes()
        head_id = pool[(idx - 1) % len(pool)]

        chosen_models: list[int] = [head_id]
        for slot_offset in range(1, 10):
            cand = pool[(idx * 3 + slot_offset * 5) % len(pool)]
            if cand not in chosen_models:
                chosen_models.append(cand)
            if len(chosen_models) >= 6:
                break

        step_up = min(8, max(0, npc_lv // 10))
        eq_lv = max(1, npc_lv)
        eq_set = (13010503, 13020503, 13030503, 13040503) if npc_lv >= 30 else (13010404, 13020404, 13030404, 13040404)
        npc_pid = _det_uuid(f"friend_npc:{idx}")
        slots: list[dict[str, Any]] = []
        heroes_by_id: dict[str, dict[str, Any]] = {}
        embattle: dict[str, int] = {f"Formation{i}": 0 for i in range(1, 7)}
        total_fap = 0

        for s_idx in range(1, 7):
            if s_idx <= len(chosen_models):
                hm = chosen_models[s_idx - 1]
                h_id = _det_uuid(f"friend_npc_hero:{idx}:{s_idx}")
                h_inst = self._build_hero_instance(hm, lv=npc_lv, step=step_up, inst_id=h_id)
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
                        "Id": _det_uuid(f"friend_npc_eq:{idx}:{s_idx}:{ek}"),
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

        return {
            "PlayerId": npc_pid,
            "Lv": npc_lv,
            "Name": _FRIEND_NPC_NAMES[(idx - 1) % len(_FRIEND_NPC_NAMES)],
            "HeadImageId": head_id,
            "FashionModelId": 0,
            "FAP": total_fap,
            "Slots": slots,
            "Embattle": embattle,
            "HeroesById": heroes_by_id,
        }

    def _social_card_from_profile(self, prof: Any) -> dict[str, Any]:
        pp = prof.state.get("player", {})
        slots = prof.state.get("slots", [])
        head_id = self._valid_hero_head_id(int(pp.get("HeadImageId", 0)), slots)
        return {
            "PlayerId": str(pp.get("PlayerId", "")),
            "Name": str(pp.get("PlayerName", "Adventurer") or "Adventurer"),
            "Lv": int(pp.get("Lv", 1)),
            "FAP": int(pp.get("FAP", 0)),
            "HeadImageId": head_id,
            "FashionModelId": int(pp.get("FashionModelId", 0)),
        }

    def _social_card_from_bot(self, bot: dict[str, Any]) -> dict[str, Any]:
        slots = bot.get("Slots", [])
        head_id = int(bot.get("HeadImageId", 0)) or self._valid_hero_head_id(0, slots)
        return {
            "PlayerId": str(bot["PlayerId"]),
            "Name": str(bot["Name"]),
            "Lv": int(bot["Lv"]),
            "FAP": int(bot["FAP"]),
            "HeadImageId": head_id,
            "FashionModelId": int(bot.get("FashionModelId", 0)),
        }

    def _social_resolve_player(self, target_id: str) -> tuple[str, dict[str, Any], Any | None]:
        tid = str(target_id or "")
        if not tid or tid == EMPTY_ENTITY_ID:
            return "none", {}, None
        if tid == str(self.state["player"]["PlayerId"]):
            return "self", self._social_card_from_profile(self), self

        peer = self._find_peer_by_player_id(tid)
        if peer is not None:
            return "peer", self._social_card_from_profile(peer), peer

        npc_idx = self._social_npc_index(tid)
        if npc_idx is not None:
            npc = self._social_npc_profile(npc_idx)
            return "npc", self._social_card_from_bot(npc), npc

        # Fallback: Arena bot lookup for AddEnemy from Chat/Arena
        pvp = self.state.get("pvp", {})
        cur_step = self._pvp_step_for_lv(int(self.state["player"].get("Lv", 20)))
        probe_ranks = set(range(1, 31)) | set(range(50, 2001, 50))
        probe_ranks.update(self._candidate_arena_ranks(int(pvp.get("rank", 1500)), int(pvp.get("refresh_seed", 1))))
        for st in (cur_step, 1, 2, 3, 4, 5):
            for r in probe_ranks:
                if _det_uuid(f"arena_bot:{st}:{r}") == tid:
                    bot = self._arena_bot_profile(r, st)
                    return "arena_bot", self._social_card_from_bot(bot), bot
        return "none", {}, None

    def _social_npc_slot_formations(self, target_id: str) -> dict[str, Any] | None:
        idx = self._social_npc_index(target_id)
        if idx is None:
            return None
        return self._build_bot_formation_view(self._social_npc_profile(idx))

    def _social_npc_fight_objs(self, target_id: str, fight_add_pct: int = 0) -> list[dict[str, Any]] | None:
        idx = self._social_npc_index(target_id)
        if idx is None:
            return None
        units = self._arena_bot_fight_objs(self._social_npc_profile(idx))
        if fight_add_pct > 0:
            mult = 1.0 + fight_add_pct / 100.0
            for u in units:
                if not u:
                    continue
                for field in ("HP", "AP", "DEF"):
                    u[field] = max(1, int(u[field] * mult))
                u["TotalHp"] = u["HP"]
        return units

    # -------------------- Messaging, Email & Red-Dot Helpers --------------------

    def _append_email_record(
        self,
        social: dict[str, Any],
        *,
        email_type: int,
        subject: str,
        content: str,
        send_player_id: str = EMPTY_ENTITY_ID,
        send_player_name: str = "Hệ Thống",
        sub_module_id: int = 0,
        head_image_id: int = 0,
        fashion_model_id: int = 0,
    ) -> dict[str, Any]:
        now = self.now_ts()
        friend_set = {str(fid) for fid in social.get("friends", [])}
        record = {
            "Id": str(uuid.uuid4()),
            "HeadImageId": int(head_image_id),
            "HeroModelId": int(head_image_id),
            "FashionModelId": int(fashion_model_id),
            "SendPlayerId": str(send_player_id),
            "SendPlayerName": str(send_player_name),
            "Subject": str(subject),
            "Content": str(content),
            "Type": int(email_type),
            "SendTime": now,
            "SubModuleId": int(sub_module_id),
            "IsFriend": 1 if str(send_player_id) in friend_set else 0,
            "StartTime": now,
            "EndTime": now + 7 * 86400,
        }
        emails = social.setdefault("emails", [])
        emails.insert(0, record)
        if len(emails) > 100:
            del emails[100:]
        unread = social.setdefault("unread", {"system": False, "battle": False, "friend": False})
        if int(email_type) == 2:
            unread["battle"] = True
        else:
            unread["system"] = True
        return record

    def _push_player_email(
        self,
        email_type: int,
        subject: str,
        content: str,
        *,
        send_player_id: str = EMPTY_ENTITY_ID,
        send_player_name: str = "Hệ Thống",
        sub_module_id: int = 0,
        head_image_id: int = 0,
        fashion_model_id: int = 0,
    ) -> dict[str, Any]:
        social = self._social_state()
        return self._append_email_record(
            social,
            email_type=email_type,
            subject=subject,
            content=content,
            send_player_id=send_player_id,
            send_player_name=send_player_name,
            sub_module_id=sub_module_id,
            head_image_id=head_image_id,
            fashion_model_id=fashion_model_id,
        )

    def _push_friend_mail_message(
        self,
        social: dict[str, Any],
        *,
        msg_type: int,
        sender_card: dict[str, Any],
        content: str,
        now: int,
    ) -> None:
        msgs = social.setdefault("friend_messages", [])
        sid = str(sender_card["PlayerId"])
        if msg_type == 1:
            msgs[:] = [m for m in msgs if not (int(m.get("Type", 0)) == 1 and str(m.get("SendPlayerId", "")) == sid)]
        head_id = int(sender_card.get("HeadImageId", 12011004))
        subj = f"Lời mời kết bạn: {content}" if msg_type == 1 else str(content)
        msgs.insert(
            0,
            {
                "Id": str(uuid.uuid4()),
                "HeadImageId": head_id,
                "HeroModelId": head_id,
                "FashionModelId": int(sender_card.get("FashionModelId", 0)),
                "SendPlayerId": sid,
                "SendPlayerName": str(sender_card["Name"]),
                "SendPlayerLv": int(sender_card["Lv"]),
                "SendPlayerFAP": int(sender_card["FAP"]),
                "Type": int(msg_type),
                "Subject": subj,
                "Content": str(content),
                "SendTime": now,
            },
        )
        if len(msgs) > 100:
            del msgs[100:]
        if int(msg_type) != 1:
            social.setdefault("unread", {"system": False, "battle": False, "friend": False})["friend"] = True

    def _social_push_sta_gift(self, social: dict[str, Any], sender_id: str, now: int) -> None:
        inbox = social.setdefault("sta_inbox", [])
        if any(str(item.get("PlayerId", "")) == sender_id for item in inbox):
            return
        inbox.append({"PlayerId": sender_id, "SendTime": now})

    def _friend_sta_red_dot(self) -> int:
        lv = int(self.state.get("player", {}).get("Lv", 1))
        if lv < 2:
            return 0
        social = self._social_state()
        has_gifts = len(social.get("sta_inbox", [])) > 0
        left = max(0, FRIEND_STA_DRAW_DAILY_MAX - int(social.get("sta_draw_count", 0)))
        return 1 if (has_gifts and left > 0) else 0

    def _friend_red_dot(self) -> int:
        lv = int(self.state.get("player", {}).get("Lv", 1))
        if lv < 2:
            return 0
        social = self._social_state()
        has_apply = any(int(m.get("Type", 0)) == 1 for m in social.get("friend_messages", []))
        return 1 if (self._friend_sta_red_dot() == 1 or has_apply) else 0

    def _email_red_dots(self) -> dict[str, int]:
        social = self._social_state()
        unread = social.get("unread", {})
        has_apply = any(int(m.get("Type", 0)) == 1 for m in social.get("friend_messages", []))
        r1901 = 1 if bool(unread.get("battle")) else 0
        r1902 = 1 if (bool(unread.get("friend")) or has_apply) else 0
        r1903 = 1 if bool(unread.get("system")) else 0
        r1900 = 1 if (r1901 or r1902 or r1903) else 0
        return {"1900": r1900, "1901": r1901, "1902": r1902, "1903": r1903}

    def _social_reject(self, status: int) -> Any:
        self._last_rpc_context["status"] = int(status)
        return {}

    def _social_remove_friend_pair(self, social: dict[str, Any], target_id: str) -> bool:
        friends = [str(x) for x in social.get("friends", [])]
        existed = target_id in friends
        if existed:
            social["friends"] = [x for x in friends if x != target_id]
        peer = self._find_peer_by_player_id(target_id)
        if peer is not None:
            my_pid = str(self.state["player"]["PlayerId"])
            with peer._lock:
                ps = peer._social_state()
                if my_pid in ps["friends"]:
                    ps["friends"] = [x for x in ps["friends"] if str(x) != my_pid]
                    peer.save()
        return existed

    def _social_send_sta_one(
        self,
        social: dict[str, Any],
        target_id: str,
        my_pid: str,
        now: int,
    ) -> int:
        """Send 1 daily STA gift; returns 0 on success or negative error code."""
        if target_id not in {str(x) for x in social.get("friends", [])}:
            return -3007
        sent_today = social.setdefault("sta_sent_today", [])
        if target_id in sent_today:
            return -3001
        sent_today.append(target_id)
        self._inc_stat("friend_sta_sent", 1)
        self._record_daily_task_progress(11, 1)
        peer = self._find_peer_by_player_id(target_id)
        if peer is not None:
            with peer._lock:
                ps = peer._social_state()
                self._social_push_sta_gift(ps, my_pid, now)
                peer.save()
        return 0

    def _social_try_apply_one(self, social: dict[str, Any], target_id: str, message: str) -> int:
        """Send a friend request (auto-accepting Friend NPCs); returns 0 or negative error code."""
        p = self.state["player"]
        my_pid = str(p["PlayerId"])
        if target_id == my_pid:
            return -3006
        if len(message) > FRIEND_MSG_MAX_LEN:
            return -3002

        kind, target_card, target_obj = self._social_resolve_player(target_id)
        if kind not in ("peer", "npc"):
            return -3013
        if target_id in {str(x) for x in social.get("friends", [])}:
            return -3008

        my_max = self._friend_max_for_lv(int(p.get("Lv", 1)))
        if len(social["friends"]) >= my_max:
            return -3005

        # Reconciling removes target from local blacklist if previously blocked.
        social["enemies"] = [x for x in social["enemies"] if str(x) != target_id]
        now = self.now_ts()

        if kind == "npc":
            social["friends"].append(target_id)
            reply_idx = (self._social_npc_index(target_id) or 1) - 1
            self._push_friend_mail_message(
                social,
                msg_type=2,
                sender_card=target_card,
                content=_FRIEND_NPC_REPLIES[reply_idx % len(_FRIEND_NPC_REPLIES)],
                now=now,
            )
            self._social_push_sta_gift(social, target_id, now)
            return 0

        peer = target_obj
        with peer._lock:
            peer_lv = int(peer.state.get("player", {}).get("Lv", 1))
            if peer_lv < 2:
                return -3011
            ps = peer._social_state()
            peer_max = peer._friend_max_for_lv(peer_lv)
            if len(ps["friends"]) >= peer_max:
                return -3012
            if my_pid in {str(x) for x in ps["friends"]}:
                return -3008
            self._push_friend_mail_message(
                ps,
                msg_type=1,
                sender_card=self._social_card_from_profile(self),
                content=message or "Hãy kết bạn cùng phiêu lưu nhé!",
                now=now,
            )
            peer.save()
        return 0

    def _social_claim_sta_entry(
        self,
        social: dict[str, Any],
        sender_id: str,
        *,
        reciprocate: bool = False,
    ) -> int:
        """Claim one inbox STA gift; returns 0 or negative error code."""
        p = self.state["player"]
        draw_count = int(social.get("sta_draw_count", 0))
        if draw_count >= FRIEND_STA_DRAW_DAILY_MAX:
            return -3003
        sta_max = int(p.get("STAMaxNum", 40))
        if int(p.get("STA", 0)) >= sta_max:
            return -3010
        inbox = social.get("sta_inbox", [])
        match_idx = next((i for i, item in enumerate(inbox) if str(item.get("PlayerId", "")) == sender_id), -1)
        if match_idx < 0:
            return -3015

        inbox.pop(match_idx)
        social["sta_draw_count"] = draw_count + 1
        self.ledger.apply_player_delta(
            p,
            self.profile_name,
            "STA",
            FRIEND_STA_PER_DRAW,
            source=f"friend_sta:{sender_id}",
        )
        if reciprocate and sender_id in {str(x) for x in social.get("friends", [])}:
            self._social_send_sta_one(social, sender_id, str(p["PlayerId"]), self.now_ts())
        return 0

    # -------------------- Friend RPCs (5) --------------------

    def _rpc_friend_get_list(self, _data: Any) -> list[dict[str, Any]]:
        if int(self.state["player"].get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        social = self._social_state()
        sent_today = {str(x) for x in social.get("sta_sent_today", [])}
        out: list[dict[str, Any]] = []
        valid_ids: list[str] = []
        for fid in social["friends"]:
            fid_str = str(fid)
            kind, card, _ = self._social_resolve_player(fid_str)
            if kind not in ("peer", "npc"):
                continue
            valid_ids.append(fid_str)
            out.append({**card, "CanSendSTA": fid_str not in sent_today})
        social["friends"] = valid_ids
        self.save()
        return out

    def _rpc_friend_get_recommend(self, data: Any) -> list[dict[str, Any]]:
        if int(self.state["player"].get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        social = self._social_state()
        try:
            count = int(data[0]) if isinstance(data, list) and data and data[0] is not None else 10
        except (TypeError, ValueError):
            count = 10
        count = max(1, min(20, count))

        excluded = {str(x) for x in social["friends"]} | {str(x) for x in social["enemies"]}
        excluded.add(str(self.state["player"]["PlayerId"]))

        peers = [
            self._social_card_from_profile(peer)
            for peer in self._get_peer_s1_profiles()
            if str(peer.state["player"]["PlayerId"]) not in excluded
            and int(peer.state.get("player", {}).get("Lv", 1)) >= 2
        ]

        seed = int(social.get("recommend_seed", 0))
        social["recommend_seed"] = (seed + 1) % 1_000_000
        npc_cards: list[dict[str, Any]] = []
        for offset in range(FRIEND_NPC_COUNT):
            idx = ((offset + seed * 3) % FRIEND_NPC_COUNT) + 1
            npc_pid = _det_uuid(f"friend_npc:{idx}")
            if npc_pid in excluded:
                continue
            npc_cards.append(self._social_card_from_bot(self._social_npc_profile(idx)))

        out = (peers + npc_cards)[:count]
        self.save()
        return out

    def _rpc_friend_search(self, data: Any) -> list[dict[str, Any]]:
        if int(self.state["player"].get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        query = str(data[0]).strip().lower() if isinstance(data, list) and data and data[0] is not None else ""
        if not query:
            return []
        social = self._social_state()
        excluded = {str(x) for x in social["friends"]} | {str(x) for x in social["enemies"]}
        excluded.add(str(self.state["player"]["PlayerId"]))

        matches: list[dict[str, Any]] = []
        for peer in self._get_peer_s1_profiles():
            pid = str(peer.state["player"]["PlayerId"])
            if pid in excluded or int(peer.state.get("player", {}).get("Lv", 1)) < 2:
                continue
            card = self._social_card_from_profile(peer)
            if query in card["Name"].lower():
                matches.append(card)
        for idx in range(1, FRIEND_NPC_COUNT + 1):
            npc_pid = _det_uuid(f"friend_npc:{idx}")
            if npc_pid in excluded:
                continue
            npc_name = _FRIEND_NPC_NAMES[(idx - 1) % len(_FRIEND_NPC_NAMES)]
            if query in npc_name.lower():
                matches.append(self._social_card_from_bot(self._social_npc_profile(idx)))
        return matches[:20]

    def _rpc_friend_delete(self, data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        if not isinstance(data, list) or not data:
            return self._social_reject(-3019)
        target_id = str(data[0])
        social = self._social_state()
        if not self._social_remove_friend_pair(social, target_id):
            return self._social_reject(-3018)
        self.save()
        return {}

    def _rpc_friend_apply_response(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        if int(p.get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        if not isinstance(data, list) or len(data) < 2:
            return self._social_reject(-12)
        sender_id = str(data[0])
        is_agree = bool(data[1])
        social = self._social_state()
        msgs = social["friend_messages"]

        req_idx = next(
            (i for i, m in enumerate(msgs) if int(m.get("Type", 0)) == 1 and str(m.get("SendPlayerId", "")) == sender_id),
            -1,
        )
        if req_idx < 0:
            return self._social_reject(-12)
        msgs.pop(req_idx)

        if not is_agree:
            self.save()
            return {}

        my_pid = str(p["PlayerId"])
        if sender_id == my_pid:
            self.save()
            return self._social_reject(-3006)
        if sender_id in {str(x) for x in social["friends"]}:
            self.save()
            return self._social_reject(-3008)
        if len(social["friends"]) >= self._friend_max_for_lv(int(p.get("Lv", 1))):
            self.save()
            return self._social_reject(-3005)

        kind, _, target_obj = self._social_resolve_player(sender_id)
        if kind not in ("peer", "npc"):
            self.save()
            return self._social_reject(-3013)

        social["enemies"] = [x for x in social["enemies"] if str(x) != sender_id]
        if kind == "peer":
            peer = target_obj
            with peer._lock:
                ps = peer._social_state()
                peer_max = peer._friend_max_for_lv(int(peer.state.get("player", {}).get("Lv", 1)))
                if len(ps["friends"]) >= peer_max and my_pid not in {str(x) for x in ps["friends"]}:
                    self.save()
                    return self._social_reject(-3012)
                ps["enemies"] = [x for x in ps["enemies"] if str(x) != my_pid]
                if my_pid not in {str(x) for x in ps["friends"]}:
                    ps["friends"].append(my_pid)
                peer.save()

        social["friends"].append(sender_id)
        if kind == "npc":
            self._social_push_sta_gift(social, sender_id, self.now_ts())
        self.save()
        return {}

    # -------------------- FriendMessage RPCs (9) --------------------

    def _rpc_friend_send_sta(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        if int(p.get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        if not isinstance(data, list) or not data:
            return self._social_reject(-3007)
        social = self._social_state()
        err = self._social_send_sta_one(social, str(data[0]), str(p["PlayerId"]), self.now_ts())
        if err != 0:
            return self._social_reject(err)
        self.save()
        return {}

    def _rpc_friend_batch_send_sta(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        if int(p.get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        social = self._social_state()
        sent_set = {str(x) for x in social["sta_sent_today"]}
        eligible = [str(fid) for fid in social["friends"] if str(fid) not in sent_set]
        if not eligible:
            return self._social_reject(-3001)
        now = self.now_ts()
        my_pid = str(p["PlayerId"])
        sent_count = 0
        for fid in eligible:
            if self._social_send_sta_one(social, fid, my_pid, now) == 0:
                sent_count += 1
        self.save()
        return {"SentCount": sent_count}

    def _rpc_friend_get_sta_messages(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        social = self._social_state()
        now = self.now_ts()
        sta_data: list[dict[str, Any]] = []
        for item in social["sta_inbox"]:
            pid = str(item.get("PlayerId", ""))
            kind, card, _ = self._social_resolve_player(pid)
            if kind not in ("peer", "npc"):
                continue
            # Client FriendScene.lua:579 reads friend.PlayerName rather than friend.Name.
            sta_data.append(
                {
                    "PlayerId": pid,
                    "PlayerName": str(card["Name"]),
                    "Lv": int(card["Lv"]),
                    "FAP": int(card["FAP"]),
                    "HeadImageId": int(card["HeadImageId"]),
                    "FashionModelId": int(card.get("FashionModelId", 0)),
                    "SendTime": int(item.get("SendTime", now)),
                }
            )
        left = max(0, FRIEND_STA_DRAW_DAILY_MAX - int(social.get("sta_draw_count", 0)))
        self.save()
        return {"STAData": sta_data, "STADrawLeftCount": left}

    def _rpc_friend_receive_sta(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        if int(p.get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        if not isinstance(data, list) or not data:
            return self._social_reject(-3015)
        social = self._social_state()
        err = self._social_claim_sta_entry(social, str(data[0]), reciprocate=False)
        if err != 0:
            return self._social_reject(err)
        self._sync_player_recover_times(p)
        self.save()
        left = max(0, FRIEND_STA_DRAW_DAILY_MAX - int(social.get("sta_draw_count", 0)))
        return {"STADrawLeftCount": left, "STA": int(p["STA"])}

    def _rpc_friend_batch_receive_and_send_sta(self, _data: Any) -> dict[str, Any]:
        p = self.state["player"]
        if int(p.get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        social = self._social_state()
        if not social["sta_inbox"]:
            return self._social_reject(-3015)
        if int(social.get("sta_draw_count", 0)) >= FRIEND_STA_DRAW_DAILY_MAX:
            return self._social_reject(-3003)
        if int(p.get("STA", 0)) >= int(p.get("STAMaxNum", 40)):
            return self._social_reject(-3010)

        sent_before = len(social["sta_sent_today"])
        drawn = 0
        for sender_id in [str(item.get("PlayerId", "")) for item in social["sta_inbox"]]:
            if self._social_claim_sta_entry(social, sender_id, reciprocate=True) != 0:
                break
            drawn += 1
        sent_now = len(social["sta_sent_today"]) - sent_before
        self._sync_player_recover_times(p)
        self.save()
        left = max(0, FRIEND_STA_DRAW_DAILY_MAX - int(social.get("sta_draw_count", 0)))
        return {
            "DrawCount": drawn,
            "SendCount": sent_now,
            "STADrawLeftCount": left,
            "STA": int(p["STA"]),
        }

    def _rpc_friend_apply(self, data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        if not isinstance(data, list) or not data:
            return self._social_reject(-3013)
        target_id = str(data[0])
        message = str(data[1]) if len(data) > 1 and data[1] is not None else ""
        social = self._social_state()
        err = self._social_try_apply_one(social, target_id, message)
        if err != 0:
            return self._social_reject(err)
        self.save()
        return {}

    def _rpc_friend_batch_apply(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        if int(p.get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        id_list = data[0] if isinstance(data, list) and data and isinstance(data[0], list) else []
        social = self._social_state()
        my_max = self._friend_max_for_lv(int(p.get("Lv", 1)))
        applied = 0
        for raw_id in id_list:
            if len(social["friends"]) >= my_max:
                break
            if self._social_try_apply_one(social, str(raw_id), "Hãy kết bạn cùng phiêu lưu nhé!") == 0:
                applied += 1
        if applied == 0 and len(social["friends"]) >= my_max and id_list:
            return self._social_reject(-3005)
        self.save()
        return {"AppliedCount": applied}

    def _rpc_friend_send_message(self, data: Any) -> dict[str, Any]:
        p = self.state["player"]
        if int(p.get("Lv", 1)) < 2:
            return self._social_reject(-3011)
        if not isinstance(data, list) or len(data) < 2:
            return self._social_reject(-3017)
        target_id = str(data[0])
        content = str(data[1] if data[1] is not None else "").strip()
        if not content:
            return self._social_reject(-3017)
        if len(content) > FRIEND_MSG_MAX_LEN:
            return self._social_reject(-3002)

        social = self._social_state()
        if target_id not in {str(x) for x in social["friends"]}:
            return self._social_reject(-3014)
        kind, target_card, target_obj = self._social_resolve_player(target_id)
        if kind not in ("peer", "npc"):
            return self._social_reject(-3019)

        now = self.now_ts()
        if kind == "peer":
            peer = target_obj
            with peer._lock:
                ps = peer._social_state()
                self._push_friend_mail_message(
                    ps,
                    msg_type=2,
                    sender_card=self._social_card_from_profile(self),
                    content=content,
                    now=now,
                )
                peer.save()
        else:
            reply_idx = (len(content) + (self._social_npc_index(target_id) or 0)) % len(_FRIEND_NPC_REPLIES)
            self._push_friend_mail_message(
                social,
                msg_type=2,
                sender_card=target_card,
                content=_FRIEND_NPC_REPLIES[reply_idx],
                now=now,
            )
            self.save()
        return {}

    def _rpc_friend_get_messages_by_page(self, data: Any) -> list[dict[str, Any]]:
        social = self._social_state()
        try:
            page_idx = max(0, int(data[0])) if isinstance(data, list) and len(data) >= 1 and data[0] is not None else 0
            page_size = max(1, min(50, int(data[1]))) if isinstance(data, list) and len(data) >= 2 and data[1] is not None else 10
        except (TypeError, ValueError):
            page_idx, page_size = 0, 10
        social["unread"]["friend"] = False
        msgs = sorted(social["friend_messages"], key=lambda m: -int(m.get("SendTime", 0)))
        start = page_idx * page_size
        self.save()
        return list(msgs[start : start + page_size])

    # -------------------- Enemy Blacklist RPCs (3) --------------------

    def _rpc_enemy_get_list(self, _data: Any) -> list[dict[str, Any]]:
        social = self._social_state()
        out: list[dict[str, Any]] = []
        valid_ids: list[str] = []
        for eid in social["enemies"]:
            eid_str = str(eid)
            kind, card, _ = self._social_resolve_player(eid_str)
            if kind in ("peer", "npc", "arena_bot"):
                valid_ids.append(eid_str)
                out.append(card)
        social["enemies"] = valid_ids
        self.save()
        return out

    def _rpc_enemy_add(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            return self._social_reject(-3013)
        target_id = str(data[0])
        kind, card, _ = self._social_resolve_player(target_id)
        if kind == "self":
            return self._social_reject(-3006)
        if kind == "none":
            return self._social_reject(-3013)
        social = self._social_state()
        self._social_remove_friend_pair(social, target_id)
        if target_id not in {str(x) for x in social["enemies"]}:
            social["enemies"].append(target_id)
        self.save()
        return card

    def _rpc_enemy_delete(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            return self._social_reject(-3019)
        target_id = str(data[0])
        social = self._social_state()
        if target_id not in {str(x) for x in social["enemies"]}:
            return self._social_reject(-3019)
        social["enemies"] = [x for x in social["enemies"] if str(x) != target_id]
        self.save()
        return {}

    # -------------------- PlayerEmail RPCs (2) --------------------

    def _rpc_email_get_by_page(self, data: Any) -> list[dict[str, Any]]:
        social = self._social_state()
        try:
            email_type = int(data[0]) if isinstance(data, list) and len(data) >= 1 and data[0] is not None else 0
            page_idx = max(0, int(data[1])) if isinstance(data, list) and len(data) >= 2 and data[1] is not None else 0
            page_size = max(1, min(50, int(data[2]))) if isinstance(data, list) and len(data) >= 3 and data[2] is not None else 10
        except (TypeError, ValueError):
            return self._social_reject(-2703)
        if email_type not in (0, 1, 2):
            return self._social_reject(-2703)

        unread = social["unread"]
        if email_type in (0, 1):
            unread["system"] = False
        if email_type in (0, 2):
            unread["battle"] = False

        friend_set = {str(x) for x in social["friends"]}
        filtered = [
            {**e, "IsFriend": 1 if str(e.get("SendPlayerId", "")) in friend_set else 0}
            for e in social["emails"]
            if email_type == 0 or int(e.get("Type", 1)) == email_type
        ]
        filtered.sort(key=lambda e: -int(e.get("SendTime", 0)))
        start = page_idx * page_size
        self.save()
        return filtered[start : start + page_size]

    def _rpc_email_delete(self, data: Any) -> dict[str, Any]:
        social = self._social_state()
        if not isinstance(data, list) or not data:
            return self._social_reject(-2706)
        raw_ids = data[0] if isinstance(data[0], list) else [data[0]]
        target_ids = {str(x) for x in raw_ids if x}
        if not target_ids:
            return self._social_reject(-2706)
        before_ids = {str(e.get("Id", "")) for e in social["emails"]}
        matched = sorted(before_ids & target_ids)
        if not matched:
            return self._social_reject(-2706)
        social["emails"] = [e for e in social["emails"] if str(e.get("Id", "")) not in target_ids]
        self.save()
        return {"DeletedIds": matched}
