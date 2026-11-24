"""R8.5: Hệ Thống Thú Cưng (Pet 7400-7600, PetCompare 1414) & Động Phong Ấn (PetOut 7500)."""

from __future__ import annotations

import copy
import random
import uuid
from collections import Counter
from typing import Any

from combat_sim import simulate_fight_info
from r79_event_handlers import _parse_res_tuples

EMPTY_ENTITY_ID = "00000000-0000-0000-0000-000000000000"

# NPC rival names and guild fallbacks for Sealed Cave (PetOut) rank board & targets.
_PETOUT_NPC_NAMES = [
    "Lục Diệu Yêu",
    "Bạch Lang Vương",
    "Thanh Phong Kiếm",
    "Huyền Hỏa Hồ",
    "Xích Quỷ Tướng",
    "Tử Điện Mị",
    "Hắc Dạ Sát",
    "Ngọc Sương Nhi",
    "Huyết Nguyệt Ma",
    "Lôi Đình Sứ",
    "Phong Vân Khách",
    "Minh Vương Tử",
]
_PETOUT_NPC_GUILDS = [
    ("Tây Quốc", "S1", 260),
    ("Hội Trừ Yêu", "S1", 215),
    ("Bạch Linh Sơn", "S1", 180),
    ("Phong Hỏa Liên", "S2", 145),
    ("Thiên Không Thành", "S2", 110),
    ("Nguyệt Ảnh Đường", "S3", 80),
]

_PET_EXP_MODEL_LINEAGE = 240127
_PETOUT_MIN_NODE_ID = 11
_PETOUT_STEP_CAP = 10
_PETOUT_SHOP_MAX_REFRESH = 20
_PETOUT_FREE_REFRESH_DAILY = 3


def _pet_reject(store: Any, status: int = -1) -> dict[str, Any]:
    store._last_rpc_context["status"] = status
    return {}


class PetHandlersMixin:
    """Mixin implementing Pet progression (7400-7600 / 1414) and PetOut (7500)."""

    # ------------------------------------------------------------------
    # State Initialization & Shared Lookup Helpers
    # ------------------------------------------------------------------

    def _ensure_pet_state(self) -> None:
        player = self.state.setdefault("player", {})
        player.setdefault("PetCoin", 0)
        player.setdefault("PetSoul", 0)
        cp = player.get("CombatPet")
        if not isinstance(cp, list):
            player["CombatPet"] = [cp] if isinstance(cp, str) and cp and cp != EMPTY_ENTITY_ID else []
        for slot in self.state.get("slots", []):
            slot.setdefault("Pet", "")
        pets = self.state.setdefault("pets", [])
        for pet in pets:
            pet.setdefault("InheritNum", 0)
            pet.setdefault("InvestedGold", 0)
            pet.setdefault("InvestedPetSoul", 0)
            sids = pet.setdefault("SkillIds", {})
            sids.setdefault("1", [])
            sids.setdefault("3", [])
            sids.setdefault("4", [])
            self._recalc_pet_attrs(pet)
        self.state.setdefault("pet_pending_learn", {})

    def _find_pet(self, pet_id: Any) -> dict[str, Any] | None:
        pid = str(pet_id or "").strip()
        if not pid or pid == EMPTY_ENTITY_ID:
            return None
        for pet in self.state.get("pets", []):
            if str(pet.get("Id", "")) == pid:
                return pet
        return None

    def _deployed_pet_ids(self) -> set[str]:
        deployed: set[str] = set()
        for pid in self.state.get("player", {}).get("CombatPet") or []:
            spid = str(pid or "")
            if spid and spid != EMPTY_ENTITY_ID:
                deployed.add(spid)
        for slot in self.state.get("slots", []):
            spid = str(slot.get("Pet") or "")
            if spid and spid != EMPTY_ENTITY_ID:
                deployed.add(spid)
        return deployed

    @staticmethod
    def _pet_active_skills(pet: dict[str, Any]) -> list[dict[str, Any]]:
        sids = pet.get("SkillIds") or {}
        combined = list(sids.get("1") or []) + list(sids.get("3") or [])
        combined.sort(key=lambda s: int(s.get("SkillIndex", 0)))
        return combined

    @staticmethod
    def _pet_all_skill_entries(pet: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        sids = pet.get("SkillIds") or {}
        out: list[tuple[str, dict[str, Any]]] = []
        for bucket in ("1", "3", "4"):
            for entry in sids.get(bucket) or []:
                out.append((bucket, entry))
        return out

    # ------------------------------------------------------------------
    # Pet Attribute Formula & Slot Stat Contributions
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_pet_base_quas(base_attr_str: str) -> dict[int, int]:
        quas: dict[int, int] = {1011: 500, 1012: 350, 1013: 350, 1014: 350}
        for pair in str(base_attr_str or "").split(","):
            if "|" not in pair:
                continue
            k_s, v_s = pair.split("|", 1)
            if k_s.strip().isdigit():
                quas[int(k_s.strip())] = int(float(v_s.strip()))
        return quas

    def _recalc_pet_attrs(self, pet: dict[str, Any]) -> dict[str, Any]:
        """Match Common/ConfigFunc.lua:calcPetAttrValue + cap by PetConfig maxima."""
        cfg = self.game_data.get("pet_model", {}).get(str(pet.get("ModelId", 0)), {})
        pc = self.game_data.get("pet_config", {})
        grow_r = float(cfg.get("petGrow", 12))
        lv = max(1, int(pet.get("Lv", 1)))

        ap_qua = int(pet.get("PetAPQua", 500))
        hp_qua = int(pet.get("PetHPQua", 350))
        def_qua = int(pet.get("PetDEFQua", 350))
        fsp_qua = int(pet.get("PetFSPQua", 350))

        ap_r = float(pc.get("petAPR", 15))
        hp_r = float(pc.get("petHPR", 100))
        def_r = float(pc.get("petDEFR", 5))
        spd_r = float(pc.get("petSPDR", 1))

        pet_ap = min(int(pc.get("APMax", 15000)), int(grow_r / 10000.0 * ap_qua * ap_r * lv))
        pet_hp = min(int(pc.get("HPMax", 100000)), int(grow_r / 10000.0 * hp_qua * hp_r * lv))
        pet_def = min(int(pc.get("DEFMax", 5000)), int(grow_r / 10000.0 * def_qua * def_r * lv))
        pet_fsp = min(int(pc.get("SPDMax", 1000)), int(grow_r / 10000.0 * fsp_qua * spd_r * lv))

        skill_tbl = self.game_data.get("pet_skill", {})
        skill_fap = sum(
            int(skill_tbl.get(str(entry.get("SkillId", 0)), {}).get("skillFAP", 0))
            for _b, entry in self._pet_all_skill_entries(pet)
        )
        pet["PetAP"] = pet_ap
        pet["PetHP"] = pet_hp
        pet["PetDEF"] = pet_def
        pet["PetFSP"] = pet_fsp
        pet["Fap"] = max(1000, int(pet_hp + pet_ap * 10 + pet_def * 10 + skill_fap))
        return pet

    def _build_pet_instance(self, model_id: int, lv: int = 1, roll_initial_skills: bool = True) -> dict[str, Any]:
        cfg = self.game_data["pet_model"][str(int(model_id))]
        quas = self._parse_pet_base_quas(str(cfg.get("baseAttrStr", "")))
        base_skill_id = int(cfg.get("baseSkillID", 0))
        bucket3 = (
            [{"SkillId": base_skill_id, "SkillIndex": 1, "SkillExp": 0}]
            if base_skill_id > 0
            else []
        )
        pet: dict[str, Any] = {
            "Id": str(uuid.uuid4()),
            "ModelId": int(model_id),
            "Lv": max(1, int(lv)),
            "PetAPQua": quas[1011],
            "PetHPQua": quas[1012],
            "PetDEFQua": quas[1013],
            "PetFSPQua": quas[1014],
            "PetAP": 0,
            "PetHP": 0,
            "PetDEF": 0,
            "PetFSP": 0,
            "SkillIds": {
                "1": [],
                "3": bucket3,
                "4": [],
            },
            "InheritNum": 0,
            "InvestedGold": 0,
            "InvestedPetSoul": 0,
            "Fap": 1000,
        }
        if roll_initial_skills and (int(model_id) // 100) != _PET_EXP_MODEL_LINEAGE:
            self._roll_initial_pet_skills(pet, cfg)
        return self._recalc_pet_attrs(pet)

    def _roll_initial_pet_skills(self, pet: dict[str, Any], cfg: dict[str, Any]) -> None:
        clv = int(cfg.get("colorLV", 1))
        range_row = self.game_data.get("pet_new_skillrange", {}).get(str(clv))
        if not range_row:
            return
        n_min = int(range_row.get("newSkillsNumsMin", 0))
        n_max = int(range_row.get("newSkillsNumsMax", 0))
        if n_max <= 0:
            return
        target_extra = random.randint(max(0, n_min), n_max)
        if target_extra <= 0:
            return

        skill_range_id = max(1, int(range_row.get("skillsRangeID", 1)))
        skill_tbl = self.game_data.get("pet_skill", {})
        act_max = int(cfg.get("actSkillMax", 1))
        pas_max = int(cfg.get("pasSkillMax", 1))

        existing_types = {
            int(skill_tbl.get(str(e["SkillId"]), {}).get("skillTypeID", 0))
            for _b, e in self._pet_all_skill_entries(pet)
        }
        pool = [
            row
            for row in skill_tbl.values()
            if int(row.get("colorLV", 99)) == skill_range_id
            and int(row.get("actOrPas", 0)) in (1, 4)
            and int(row.get("skillTypeID", 0)) not in existing_types
        ]
        random.shuffle(pool)
        added = 0
        for row in pool:
            if added >= target_extra:
                break
            stype = int(row.get("skillTypeID", 0))
            if stype in existing_types:
                continue
            is_passive = int(row.get("actOrPas", 0)) == 4
            if is_passive:
                if len(pet["SkillIds"]["4"]) >= pas_max:
                    continue
                next_idx = len(pet["SkillIds"]["4"]) + 1
                pet["SkillIds"]["4"].append({"SkillId": int(row["skillID"]), "SkillIndex": next_idx, "SkillExp": 0})
            else:
                if len(pet["SkillIds"]["1"]) + len(pet["SkillIds"]["3"]) >= act_max:
                    continue
                next_idx = len(self._pet_active_skills(pet)) + 1
                pet["SkillIds"]["1"].append({"SkillId": int(row["skillID"]), "SkillIndex": next_idx, "SkillExp": 0})
            existing_types.add(stype)
            added += 1

    def _pet_attr_contribution(self, pet: dict[str, Any] | None, *, is_combat: bool) -> Counter[int]:
        totals: Counter[int] = Counter()
        if not pet:
            return totals
        pc = self.game_data.get("pet_config", {})
        ratio = float(pc.get("attAddAttackR" if is_combat else "attAddSheR", 10000)) / 10000.0
        totals[201] += int(int(pet.get("PetHP", 0)) * ratio)
        totals[202] += int(int(pet.get("PetAP", 0)) * ratio)
        totals[203] += int(int(pet.get("PetDEF", 0)) * ratio)
        totals[204] += int(int(pet.get("PetFSP", 0)) * ratio)

        skill_tbl = self.game_data.get("pet_skill", {})
        for entry in (pet.get("SkillIds") or {}).get("4") or []:
            sk = skill_tbl.get(str(entry.get("SkillId", 0)))
            if not sk or int(sk.get("actOrPas", 0)) != 4:
                continue
            for pair in str(sk.get("buffID", "") or "").split(","):
                if "|" not in pair:
                    continue
                k_s, v_s = pair.split("|", 1)
                if k_s.strip().isdigit():
                    totals[int(k_s.strip())] += int(float(v_s.strip()))
        return totals

    def _combat_pet_bonuses(self) -> Counter[int]:
        cp = self.state.get("player", {}).get("CombatPet") or []
        if not cp:
            return Counter()
        pet = self._find_pet(cp[0])
        return self._pet_attr_contribution(pet, is_combat=True)

    def _shelter_pet_bonuses(self, slot: dict[str, Any]) -> Counter[int]:
        pet = self._find_pet(slot.get("Pet"))
        return self._pet_attr_contribution(pet, is_combat=False)

    # ------------------------------------------------------------------
    # Pet & Slot RPCs
    # ------------------------------------------------------------------

    def _rpc_slot_pet_combat(self, data: Any) -> dict[str, Any]:
        """Slot.PetCombat [slotId, petId]: 0 = CombatPet (all heroes), 1..6 = hero shelter slot."""
        self._ensure_pet_state()
        if not isinstance(data, list) or len(data) < 2:
            return _pet_reject(self, -1)
        slot_id = int(data[0])
        pet_id = str(data[1] or "").strip()
        if slot_id < 0 or slot_id > 6:
            return _pet_reject(self, -1)

        slots = self.state.get("slots", [])
        player = self.state["player"]
        unequip = pet_id in ("", EMPTY_ENTITY_ID)

        if unequip:
            if slot_id == 0:
                player["CombatPet"] = []
            else:
                slots[slot_id - 1]["Pet"] = ""
        else:
            pet = self._find_pet(pet_id)
            if not pet:
                return _pet_reject(self, -1)
            if slot_id >= 1 and str(slots[slot_id - 1].get("HeroId", "")) in ("", EMPTY_ENTITY_ID):
                return _pet_reject(self, -1)
            # Detach from any previous slot / CombatPet first
            if player.get("CombatPet") and str(player["CombatPet"][0]) == pet_id:
                player["CombatPet"] = []
            for s in slots:
                if str(s.get("Pet", "")) == pet_id:
                    s["Pet"] = ""
            if slot_id == 0:
                player["CombatPet"] = [pet_id]
            else:
                slots[slot_id - 1]["Pet"] = pet_id

        self._recalc_all_slots_and_fap()
        self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"SlotInfo": slots, "CombatPet": list(player["CombatPet"])}

    def _pet_lv_cost_tuples(self, target_lv: int, color_lv: int) -> list[tuple[int, int, int]]:
        row = self.game_data.get("pet_lv", {}).get(str(target_lv), {}).get(str(color_lv), {})
        return _parse_res_tuples(str(row.get("use", "") or ""))

    def _pet_max_lv(self) -> int:
        lv_tbl = self.game_data.get("pet_lv", {})
        return max((int(k) for k in lv_tbl), default=100)

    def _rpc_pet_lv_up(self, data: Any) -> dict[str, Any]:
        """Pet.PetLvUp [petId, times]: level up pet by 1..times; returns pet dict as Value."""
        self._ensure_pet_state()
        if not isinstance(data, list) or not data:
            return _pet_reject(self, -1)
        pet = self._find_pet(data[0])
        if not pet:
            return _pet_reject(self, -1)
        times = max(1, min(100, int(data[1]) if len(data) >= 2 else 1))
        cfg = self.game_data.get("pet_model", {}).get(str(pet["ModelId"]), {})
        color_lv = int(cfg.get("colorLV", 1))
        max_lv = self._pet_max_lv()
        player = self.state["player"]

        gained = 0
        for _ in range(times):
            cur_lv = int(pet.get("Lv", 1))
            if cur_lv >= max_lv:
                break
            costs = self._pet_lv_cost_tuples(cur_lv + 1, color_lv)
            gold_cost = sum(amt for rt, _rm, amt in costs if rt == 1112)
            soul_cost = sum(amt for rt, _rm, amt in costs if rt == 2403)
            if int(player.get("Gold", 0)) < gold_cost or int(player.get("PetSoul", 0)) < soul_cost:
                break
            if gold_cost > 0:
                self.ledger.apply_player_delta(player, self.profile_name, "Gold", -gold_cost, source=f"pet_lv:{cur_lv+1}")
            if soul_cost > 0:
                self.ledger.apply_player_delta(player, self.profile_name, "PetSoul", -soul_cost, source=f"pet_lv:{cur_lv+1}")
            pet["InvestedGold"] = int(pet.get("InvestedGold", 0)) + gold_cost
            pet["InvestedPetSoul"] = int(pet.get("InvestedPetSoul", 0)) + soul_cost
            pet["Lv"] = cur_lv + 1
            gained += 1

        if gained == 0:
            return _pet_reject(self, -1)

        self._recalc_pet_attrs(pet)
        if str(pet["Id"]) in self._deployed_pet_ids():
            self._recalc_all_slots_and_fap()
            self._last_rpc_context["slots_changed"] = True
        self.save()
        return copy.deepcopy(pet)

    def _add_or_upgrade_pet_skill(
        self,
        pet: dict[str, Any],
        skill_id: int,
        *,
        exp_gain: int = 0,
        allow_upgrade_by_type: bool = True,
    ) -> str | None:
        """Try upgrading same skillTypeID in place or adding into a free slot.

        Returns bucket modified ('1','3','4') or None if slots full / not upgradeable.
        """
        skill_tbl = self.game_data.get("pet_skill", {})
        pet_cfg = self.game_data.get("pet_model", {}).get(str(pet["ModelId"]), {})
        sk = skill_tbl.get(str(skill_id))
        if not sk:
            return None
        stype = int(sk.get("skillTypeID", 0))
        is_passive = int(sk.get("actOrPas", 0)) == 4

        for bucket, entry in self._pet_all_skill_entries(pet):
            cur_sk = skill_tbl.get(str(entry["SkillId"]), {})
            if int(cur_sk.get("skillTypeID", -1)) == stype:
                if not allow_upgrade_by_type:
                    return None
                if exp_gain > 0:
                    entry["SkillExp"] = int(entry.get("SkillExp", 0)) + exp_gain
                    while True:
                        c_row = skill_tbl.get(str(entry["SkillId"]), {})
                        up_id = int(c_row.get("colorUpID", 0))
                        need_exp = int(c_row.get("needExp", 0))
                        if up_id > 0 and need_exp > 0 and entry["SkillExp"] >= need_exp and str(up_id) in skill_tbl:
                            entry["SkillExp"] -= need_exp
                            entry["SkillId"] = up_id
                        else:
                            break
                    return bucket
                # Direct learn book replaces lower colorLV same type
                if int(sk.get("colorLV", 0)) > int(cur_sk.get("colorLV", 0)):
                    entry["SkillId"] = int(skill_id)
                    entry["SkillExp"] = 0
                    return bucket
                return None

        if is_passive:
            pas_list = pet["SkillIds"].setdefault("4", [])
            if len(pas_list) < int(pet_cfg.get("pasSkillMax", 1)):
                pas_list.append({"SkillId": int(skill_id), "SkillIndex": len(pas_list) + 1, "SkillExp": 0})
                return "4"
        else:
            act_max = int(pet_cfg.get("actSkillMax", 1))
            if len(self._pet_active_skills(pet)) < act_max:
                act_list = pet["SkillIds"].setdefault("1", [])
                act_list.append(
                    {"SkillId": int(skill_id), "SkillIndex": len(self._pet_active_skills(pet)) + 1, "SkillExp": 0}
                )
                return "1"
        return None

    def _rpc_pet_inherit(self, data: Any) -> dict[str, Any]:
        """Pet.PetInherit [petId, devourPetId]: devour unequipped fodder into target pet; returns pet dict."""
        self._ensure_pet_state()
        if not isinstance(data, list) or len(data) < 2:
            return _pet_reject(self, -1)
        pet_id = str(data[0])
        fodder_id = str(data[1])
        if pet_id == fodder_id:
            return _pet_reject(self, -1)
        target = self._find_pet(pet_id)
        fodder = self._find_pet(fodder_id)
        if not target or not fodder or fodder_id in self._deployed_pet_ids():
            return _pet_reject(self, -1)

        pet_tbl = self.game_data.get("pet_model", {})
        lv_tbl = self.game_data.get("pet_lv", {})
        skill_tbl = self.game_data.get("pet_skill", {})
        pc = self.game_data.get("pet_config", {})

        t_clv = int(pet_tbl.get(str(target["ModelId"]), {}).get("colorLV", 1))
        f_clv = int(pet_tbl.get(str(fodder["ModelId"]), {}).get("colorLV", 1))
        f_lv = int(fodder.get("Lv", 1))
        t_lv = int(target.get("Lv", 1))

        cur_exp = int(lv_tbl.get(str(t_lv), {}).get(str(t_clv), {}).get("EXPTotal", 0))
        fodder_exp = int(lv_tbl.get(str(f_lv), {}).get(str(f_clv), {}).get("EXPTotal", 0))
        bonus_exp = (5000 if (int(fodder["ModelId"]) // 100) == _PET_EXP_MODEL_LINEAGE else 1000) * max(1, f_clv)
        new_exp_total = cur_exp + fodder_exp + bonus_exp
        max_lv = self._pet_max_lv()
        while t_lv < max_lv:
            req_total = int(lv_tbl.get(str(t_lv + 1), {}).get(str(t_clv), {}).get("EXPTotal", 10**12))
            if new_exp_total >= req_total:
                t_lv += 1
            else:
                break
        target["Lv"] = t_lv
        target["InheritNum"] = int(target.get("InheritNum", 0)) + 1
        target["InvestedGold"] = int(target.get("InvestedGold", 0)) + int(fodder.get("InvestedGold", 0))
        target["InvestedPetSoul"] = int(target.get("InvestedPetSoul", 0)) + int(fodder.get("InvestedPetSoul", 0))

        inherit_r = int(pc.get("inheritAndAddSkillR", 3000))
        target_types = {
            int(skill_tbl.get(str(e["SkillId"]), {}).get("skillTypeID", 0))
            for _b, e in self._pet_all_skill_entries(target)
        }
        for _b, f_entry in self._pet_all_skill_entries(fodder):
            fsid = int(f_entry["SkillId"])
            fsk = skill_tbl.get(str(fsid), {})
            fstype = int(fsk.get("skillTypeID", 0))
            if fstype in target_types:
                gmin = int(fsk.get("giveExpMin", 10))
                gmax = max(gmin, int(fsk.get("giveExpMax", gmin)))
                self._add_or_upgrade_pet_skill(target, fsid, exp_gain=random.randint(gmin, gmax))
            elif random.randint(1, 10000) <= inherit_r:
                if self._add_or_upgrade_pet_skill(target, fsid, allow_upgrade_by_type=False):
                    target_types.add(fstype)

        self.state["pets"] = [p for p in self.state["pets"] if str(p["Id"]) != fodder_id]
        self._recalc_pet_attrs(target)
        if pet_id in self._deployed_pet_ids():
            self._recalc_all_slots_and_fap()
            self._last_rpc_context["slots_changed"] = True
        self.save()
        return copy.deepcopy(target)

    def _find_pet_book_item(self, book_id_arg: Any) -> tuple[dict[str, Any] | None, int]:
        goods_tbl = self.game_data.get("goods_model", {})
        target = str(book_id_arg or "").strip()
        for g in self.state.get("goods", []):
            if int(g.get("Num", 0)) <= 0:
                continue
            gid = int(g.get("GoodsModelId", 0))
            if str(g.get("Id", "")) == target or (target.isdigit() and gid == int(target)):
                gm = goods_tbl.get(str(gid), {})
                if int(gm.get("typeID", 0)) == 1614:
                    return g, gid
        return None, 0

    def _rpc_pet_learn_book(self, data: Any) -> dict[str, Any]:
        """Pet.LearnPetBook [petId, bookEntityId]."""
        self._ensure_pet_state()
        if not isinstance(data, list) or len(data) < 2:
            return _pet_reject(self, -1)
        pet = self._find_pet(data[0])
        book_item, gid = self._find_pet_book_item(data[1])
        if not pet or not book_item:
            return _pet_reject(self, -1)

        skill_id = int(self.game_data.get("goods_model", {}).get(str(gid), {}).get("outputModelID", 0))
        skill_tbl = self.game_data.get("pet_skill", {})
        sk = skill_tbl.get(str(skill_id))
        if not sk:
            return _pet_reject(self, -1)

        stype = int(sk.get("skillTypeID", 0))
        new_clv = int(sk.get("colorLV", 1))
        for _b, entry in self._pet_all_skill_entries(pet):
            cur_sk = skill_tbl.get(str(entry["SkillId"]), {})
            if int(cur_sk.get("skillTypeID", -1)) == stype and int(cur_sk.get("colorLV", 0)) >= new_clv:
                return _pet_reject(self, -1)

        book_item["Num"] = int(book_item["Num"]) - 1
        if book_item["Num"] <= 0:
            self.state["goods"] = [g for g in self.state["goods"] if str(g.get("Id")) != str(book_item["Id"])]
        self._mark_goods_changed(gid)

        pending = self.state.setdefault("pet_pending_learn", {})
        pending.pop(str(pet["Id"]), None)

        modified_bucket = self._add_or_upgrade_pet_skill(pet, skill_id, exp_gain=0, allow_upgrade_by_type=True)
        if modified_bucket is not None:
            self._recalc_pet_attrs(pet)
            if str(pet["Id"]) in self._deployed_pet_ids():
                self._recalc_all_slots_and_fap()
                self._last_rpc_context["slots_changed"] = True
            self.save()
            return {"PetInfo": copy.deepcopy(pet), "ExchangeSkillId": 0, "GetedSkillId": skill_id}

        # Slots full: offer replacement prompt
        is_passive = int(sk.get("actOrPas", 0)) == 4
        if is_passive:
            candidates = [("4", e) for e in (pet["SkillIds"].get("4") or [])]
        else:
            b1 = [("1", e) for e in (pet["SkillIds"].get("1") or [])]
            b3 = [("3", e) for e in (pet["SkillIds"].get("3") or [])]
            candidates = b1 if b1 else b3
        if not candidates:
            self.save()
            return _pet_reject(self, -1)

        cand_bucket, cand_entry = random.choice(candidates)
        old_sid = int(cand_entry["SkillId"])
        pending[str(pet["Id"])] = {
            "bucket": cand_bucket,
            "old_skill_id": old_sid,
            "new_skill_id": skill_id,
        }
        self.save()
        return {"PetInfo": copy.deepcopy(pet), "ExchangeSkillId": old_sid, "GetedSkillId": skill_id}

    def _rpc_pet_commit_learn_book(self, data: Any) -> dict[str, Any]:
        """Pet.CommitLearnPetBook [petId, commitFlag]."""
        self._ensure_pet_state()
        if not isinstance(data, list) or len(data) < 2:
            return _pet_reject(self, -1)
        pet = self._find_pet(data[0])
        if not pet:
            return _pet_reject(self, -1)
        commit = int(data[1]) == 1
        pending = self.state.setdefault("pet_pending_learn", {}).pop(str(pet["Id"]), None)
        if commit and pending:
            bucket = str(pending["bucket"])
            old_sid = int(pending["old_skill_id"])
            new_sid = int(pending["new_skill_id"])
            for entry in pet["SkillIds"].get(bucket, []):
                if int(entry["SkillId"]) == old_sid:
                    entry["SkillId"] = new_sid
                    entry["SkillExp"] = 0
                    break
            self._recalc_pet_attrs(pet)
            if str(pet["Id"]) in self._deployed_pet_ids():
                self._recalc_all_slots_and_fap()
                self._last_rpc_context["slots_changed"] = True
        self.save()
        return {"PetInfo": copy.deepcopy(pet)}

    def _rpc_pet_order_skill(self, data: Any) -> dict[str, Any]:
        """Pet.OrderPetSkill [petId, sortedSkillIds]."""
        self._ensure_pet_state()
        if not isinstance(data, list) or len(data) < 2:
            return _pet_reject(self, -1)
        pet = self._find_pet(data[0])
        if not pet or not isinstance(data[1], list):
            return _pet_reject(self, -1)
        order_map = {int(sid): idx for idx, sid in enumerate(data[1], start=1)}
        for bucket in ("1", "3"):
            entries = pet["SkillIds"].get(bucket, [])
            for entry in entries:
                if int(entry["SkillId"]) in order_map:
                    entry["SkillIndex"] = order_map[int(entry["SkillId"])]
            entries.sort(key=lambda e: int(e.get("SkillIndex", 0)))
        self.save()
        return {"PetInfo": copy.deepcopy(pet)}

    def _rpc_pet_colorup(self, data: Any) -> dict[str, Any]:
        """Pet.PetColorup [petIdList]: synthesize 5 same-colorLV unequipped pets into +1 star pet."""
        self._ensure_pet_state()
        raw_ids = data[0] if isinstance(data, list) and data and isinstance(data[0], list) else data
        if not isinstance(raw_ids, list):
            return _pet_reject(self, -1)
        need_num = int(self.game_data.get("pet_config", {}).get("colorUpNeedNums", 5))
        pet_ids = [str(pid) for pid in raw_ids]
        if len(pet_ids) != need_num or len(set(pet_ids)) != need_num:
            return _pet_reject(self, -1)

        deployed = self._deployed_pet_ids()
        pet_tbl = self.game_data.get("pet_model", {})
        fodders: list[dict[str, Any]] = []
        color_lv: int | None = None
        for pid in pet_ids:
            if pid in deployed:
                return _pet_reject(self, -1)
            p = self._find_pet(pid)
            if not p or int(p.get("InheritNum", 0)) > 0:
                return _pet_reject(self, -1)
            clv = int(pet_tbl.get(str(p["ModelId"]), {}).get("colorLV", 0))
            if clv <= 0 or clv >= 7:
                return _pet_reject(self, -1)
            if color_lv is None:
                color_lv = clv
            elif clv != color_lv:
                return _pet_reject(self, -1)
            fodders.append(p)

        next_clv = int(color_lv or 1) + 1
        candidates = [
            int(row["petID"])
            for row in pet_tbl.values()
            if int(row.get("colorLV", 0)) == next_clv and (int(row["petID"]) // 100) != _PET_EXP_MODEL_LINEAGE
        ]
        if not candidates:
            return _pet_reject(self, -1)

        chosen_model = random.choice(candidates)
        del_set = set(pet_ids)
        self.state["pets"] = [p for p in self.state["pets"] if str(p["Id"]) not in del_set]
        pending = self.state.get("pet_pending_learn", {})
        for pid in del_set:
            pending.pop(pid, None)

        base_res = self._grant_resources_from_tuples(
            [(2401, chosen_model, 1)],
            source="pet_colorup",
            tx_prefix=f"pet_colorup:{self.profile_name}:{self.now_ts()}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _pet_rebirth_diamond_cost(self, color_lv: int, inherit_num: int) -> int:
        tbl = self.game_data.get("pet_rebirth", {}).get(str(color_lv), {})
        best_key = -1
        cost = 0
        for k_s, row in tbl.items():
            k = int(k_s)
            if inherit_num >= k and k >= best_key:
                best_key = k
                cost = int(row.get("useDiamond", 0))
        return cost

    def _rpc_pet_rebirth(self, data: Any) -> dict[str, Any]:
        """Pet.PetRebirth [petId]: refund 100% Gold & PetSoul, reset Lv=1 & InheritNum=0."""
        self._ensure_pet_state()
        if not isinstance(data, list) or not data:
            return _pet_reject(self, -1)
        arg = data[0]
        if isinstance(arg, list):
            if not arg:
                return _pet_reject(self, -1)
            pet_id = str(arg[0])
        else:
            pet_id = str(arg)

        if pet_id in self._deployed_pet_ids():
            return _pet_reject(self, -1)
        pet = self._find_pet(pet_id)
        if not pet:
            return _pet_reject(self, -1)
        old_lv = int(pet.get("Lv", 1))
        old_inherit = int(pet.get("InheritNum", 0))
        if old_lv <= 1 and old_inherit <= 0:
            return _pet_reject(self, -1)

        cfg = self.game_data.get("pet_model", {}).get(str(pet["ModelId"]), {})
        color_lv = int(cfg.get("colorLV", 1))
        dia_cost = self._pet_rebirth_diamond_cost(color_lv, old_inherit)
        player = self.state["player"]
        if dia_cost > 0:
            if int(player.get("Diamond", 0)) < dia_cost:
                return _pet_reject(self, -1104)
            self.ledger.apply_player_delta(
                player, self.profile_name, "Diamond", -dia_cost, source=f"pet_rebirth:{pet['ModelId']}"
            )

        has_tracked = "InvestedGold" in pet or "InvestedPetSoul" in pet
        if has_tracked:
            gold_refund = int(pet.get("InvestedGold", 0))
            soul_refund = int(pet.get("InvestedPetSoul", 0))
        elif old_inherit == 0:
            gold_refund = 0
            soul_refund = 0
            for lv_step in range(2, old_lv + 1):
                for rt, _rm, amt in self._pet_lv_cost_tuples(lv_step, color_lv):
                    if rt == 1112:
                        gold_refund += amt
                    elif rt == 2403:
                        soul_refund += amt
        else:
            gold_refund = 0
            soul_refund = 0

        refund_tuples: list[tuple[int, int, int]] = []
        if gold_refund > 0:
            refund_tuples.append((1112, 0, gold_refund))
        if soul_refund > 0:
            refund_tuples.append((2403, 0, soul_refund))

        pet["Lv"] = 1
        pet["InheritNum"] = 0
        pet["InvestedGold"] = 0
        pet["InvestedPetSoul"] = 0
        self._recalc_pet_attrs(pet)

        base_res = (
            self._grant_resources_from_tuples(
                refund_tuples,
                source=f"pet_rebirth:{pet['ModelId']}",
                tx_prefix=f"pet_rebirth:{self.profile_name}:{pet_id}:{self.now_ts()}",
            )
            if refund_tuples
            else []
        )
        self.save()
        return {"PetInfo": copy.deepcopy(pet), "BaseGetGameResourceList": base_res}

    def _rpc_pet_test_add(self, data: Any) -> dict[str, Any]:
        """Pet.TestAdd [petModelId, count]: debug-only helper."""
        if getattr(self, "is_normal_gameplay", True):
            return _pet_reject(self, -1)
        if not isinstance(data, list) or not data:
            return _pet_reject(self, -1)
        model_id = int(data[0])
        count = max(1, min(20, int(data[1]) if len(data) >= 2 else 1))
        if str(model_id) not in self.game_data.get("pet_model", {}):
            return _pet_reject(self, -1)
        base_res = self._grant_resources_from_tuples(
            [(2401, model_id, count)],
            source="debug_pet_add",
            tx_prefix=f"debug_pet_add:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_pet_test_add_res(self, data: Any) -> dict[str, Any]:
        """Pet.TestAddPetGameResource [resTypeSub, count]: debug-only helper."""
        if getattr(self, "is_normal_gameplay", True):
            return _pet_reject(self, -1)
        if not isinstance(data, list) or len(data) < 2:
            return _pet_reject(self, -1)
        rtype = int(data[0])
        count = max(1, int(data[1]))
        if rtype not in (2403, 2404):
            return _pet_reject(self, -1)
        base_res = self._grant_resources_from_tuples(
            [(rtype, 0, count)],
            source="debug_pet_res",
            tx_prefix=f"debug_pet_res:{self.profile_name}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    # ------------------------------------------------------------------
    # Sealed Cave (PetOut 7500) Internal Helpers & Timers
    # ------------------------------------------------------------------

    def _petout_open_lv(self) -> int:
        return int(self.game_data.get("module_subs", {}).get("7500", {}).get("openLv", 45))

    def _petout_node_cfg(self, node_id: int) -> dict[str, Any] | None:
        return self.game_data.get("petout_nodes", {}).get(str(int(node_id) * 100 + 11))

    def _ensure_petout_state(self) -> dict[str, Any]:
        self._ensure_pet_state()
        po = self.state.get("pet_out")
        now = self.now_ts()
        today = self.clock.today_str()
        if not isinstance(po, dict) or not po.get("shop"):
            po = {
                "current_node_id": _PETOUT_MIN_NODE_ID,
                "score": 0,
                "step_num": _PETOUT_STEP_CAP,
                "last_step_ts": now,
                "buy_step_count": 0,
                "buy_step_date": today,
                "open_box_num": 0,
                "node_targets": [],
                "shop": {
                    "slots": {},
                    "free_count": _PETOUT_FREE_REFRESH_DAILY,
                    "player_refresh_count": 0,
                    "next_refresh_time": 0,
                    "refresh_date": today,
                },
            }
            self.state["pet_out"] = po
        self._petout_sync_timers(po)
        node_cfg = self._petout_node_cfg(int(po.get("current_node_id", _PETOUT_MIN_NODE_ID)))
        if node_cfg and int(node_cfg.get("nodeType", 1)) == 1 and not po.get("node_targets"):
            self._petout_spawn_node_targets(po, int(po["current_node_id"]))
        return po

    def _petout_sync_timers(self, po: dict[str, Any]) -> None:
        now = self.now_ts()
        today = self.clock.today_str()
        if po.get("buy_step_date") != today:
            po["buy_step_date"] = today
            po["buy_step_count"] = 0

        pcfg = self.game_data.get("petout_config", {})
        step_sec = max(60, int(pcfg.get("stepNums", 30)) * 60)
        cur_step = int(po.get("step_num", _PETOUT_STEP_CAP))
        last_ts = int(po.get("last_step_ts", now))
        if cur_step < _PETOUT_STEP_CAP and now > last_ts:
            ticks = (now - last_ts) // step_sec
            if ticks > 0:
                cur_step = min(_PETOUT_STEP_CAP, cur_step + int(ticks))
                po["step_num"] = cur_step
                po["last_step_ts"] = now if cur_step >= _PETOUT_STEP_CAP else last_ts + int(ticks) * step_sec
        elif cur_step >= _PETOUT_STEP_CAP:
            po["last_step_ts"] = now

        shop = po.setdefault("shop", {})
        if shop.get("refresh_date") != today:
            shop["refresh_date"] = today
            shop["free_count"] = _PETOUT_FREE_REFRESH_DAILY
            shop["player_refresh_count"] = 0

        refresh_cd = max(60, int(pcfg.get("freeRefresh", 7200)))
        if not shop.get("slots") or now >= int(shop.get("next_refresh_time", 0)):
            shop["slots"] = self._petout_roll_shop_slots()
            shop["next_refresh_time"] = now + refresh_cd

    def _petout_roll_shop_slots(self) -> dict[str, dict[str, Any]]:
        rows = self.game_data.get("petout_shop", {}).values()
        by_loc: dict[int, list[dict[str, Any]]] = {i: [] for i in range(1, 7)}
        for r in rows:
            loc = int(r.get("locatin", 0))
            if 1 <= loc <= 6:
                by_loc[loc].append(r)

        out: dict[str, dict[str, Any]] = {}
        for loc in range(1, 7):
            pool = by_loc.get(loc) or []
            if not pool:
                continue
            max_roll = max((int(r.get("oddsMax", 0)) for r in pool), default=10000)
            roll = random.randint(1, max(1, max_roll))
            chosen = next((r for r in pool if int(r.get("oddsMin", 0)) <= roll <= int(r.get("oddsMax", 0))), pool[0])
            out_tuples = _parse_res_tuples(str(chosen.get("outResource", "2403,0,10000")))
            use_tuples = _parse_res_tuples(str(chosen.get("useResource", "2404,0,70")))
            otype, omodel, ocount = out_tuples[0]
            utype, _umodel, ucount = use_tuples[0]
            # Exact client typo 'PetModudle' required by PetShopLayer.lua:154,163
            out[str(loc)] = {
                "PetOutSourceType": otype,
                "PetModudle": omodel,
                "PetOutCount": ocount,
                "PetUseResourceTypeSub": utype,
                "PetUseCount": ucount,
                "IsSell": 0,
            }
        return out

    def _petout_spawn_node_targets(self, po: dict[str, Any], node_id: int) -> None:
        node_cfg = self._petout_node_cfg(node_id)
        if not node_cfg or int(node_cfg.get("nodeType", 1)) == 2:
            po["node_targets"] = []
            po["open_box_num"] = 0
            return

        teams = self.game_data.get("pet", {}).get("petout_targets", [])
        if not teams:
            po["node_targets"] = []
            return
        min_fap = int(node_cfg.get("minFAP", 425000))
        max_fap = int(node_cfg.get("maxFAP", 575000))
        mid_fap = (min_fap + max_fap) // 2
        need_count = int(self.game_data.get("petout_config", {}).get("enemyNums", 4))

        ranked = sorted(teams, key=lambda t: abs(int(t["total_fap"]) - mid_fap))
        pool = ranked[: max(need_count * 2, need_count)]
        chosen_teams = random.sample(pool, min(need_count, len(pool)))
        chosen_teams.sort(key=lambda t: int(t["total_fap"]))

        # Stage-appropriate pet preview (optional)
        pet_models = self.game_data.get("pet_model", {})
        stage_idx = node_id - 10
        star_bracket = min(7, 1 + (stage_idx // 8))
        star_pets = [int(r["petID"]) for r in pet_models.values() if int(r.get("colorLV", 1)) == star_bracket]

        spawned: list[dict[str, Any]] = []
        for idx, team in enumerate(chosen_teams):
            slots_copy: list[dict[str, Any]] = []
            for sl in team["slots"]:
                hp = max(1, int(sl["HP"]))
                slots_copy.append({
                    **sl,
                    "TotalHP": hp,
                    "CurrentHP": hp,
                    "HeroModelId": int(sl["heroModelId"]),
                })
            leader_id = int(team["leader_hero_id"])
            npc_name = _PETOUT_NPC_NAMES[(node_id * 4 + idx) % len(_PETOUT_NPC_NAMES)]
            spawned.append(
                {
                    "TargetId": f"{team['targetId']}:{node_id}:{idx}",
                    "HeroModelId": leader_id,
                    "FashionModelId": 0,
                    "Name": npc_name,
                    "FAP": int(team["total_fap"]),
                    "PVPInterLv": min(8, 1 + stage_idx // 6),
                    "ServerName": "S1",
                    "Lv": int(team["lv"]),
                    "PetId": random.choice(star_pets) if (idx == need_count - 1 and star_pets) else 0,
                    "Slots": slots_copy,
                }
            )
        po["node_targets"] = spawned
        po["open_box_num"] = 0

    def _petout_rank_lists(self, po: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
        my_score = int(po.get("score", 0))
        my_player = self.state["player"]
        my_pid = str(my_player.get("PlayerId", ""))

        # Player leaderboard (merge S1 peers if available + NPC rivals)
        entries: list[tuple[str, int, int, int, str, str, int]] = []
        seen_pids: set[str] = set()
        for prof in self._s1_account_profiles():
            p = prof.state.get("player", {})
            pid = str(p.get("PlayerId", ""))
            if not pid or pid in seen_pids:
                continue
            seen_pids.add(pid)
            p_po = prof.state.get("pet_out", {})
            sc = my_score if prof is self else int(p_po.get("score", 0))
            entries.append(
                (
                    pid,
                    int(p.get("HeadImageId", 12011004)),
                    int(p.get("FashionModelId", 0)),
                    int(p.get("PVPInterLv", 1)),
                    str(p.get("PlayerName", "Tân Thủ")),
                    "S1",
                    sc,
                )
            )
        for idx, npc_name in enumerate(_PETOUT_NPC_NAMES[:10]):
            npc_score = max(3, 45 - idx * 4)
            entries.append(
                (
                    f"npc_petout:{idx}",
                    12011004 + (idx % 6),
                    0,
                    max(1, 5 - idx // 2),
                    npc_name,
                    "S1",
                    npc_score,
                )
            )
        entries.sort(key=lambda r: (-r[6], r[0].startswith("npc_petout:"), r[0]))

        my_rank = 0
        player_ranks: list[dict[str, Any]] = []
        for rank_idx, row in enumerate(entries, start=1):
            if row[0] == my_pid:
                my_rank = rank_idx
            player_ranks.append(
                {
                    "Rank": rank_idx,
                    "HeadImageId": row[1],
                    "FashionModelId": row[2],
                    "PVPInterLv": row[3],
                    "Name": row[4],
                    "ServerName": row[5],
                    "Score": row[6],
                }
            )

        # Guild leaderboard
        guild_map: dict[str, tuple[str, str, int]] = {
            gname: (gname, srv, base_score) for gname, srv, base_score in _PETOUT_NPC_GUILDS
        }
        my_guild_name = ""
        g_info = self.state.get("guild", {})
        gid = str(g_info.get("guild_id", ""))
        if gid and gid != EMPTY_ENTITY_ID:
            gname = str(my_player.get("GuildName") or g_info.get("guild_name") or "Công Hội S1")
            my_guild_name = gname
            cur = guild_map.get(gname, (gname, "S1", 0))
            guild_map[gname] = (gname, "S1", max(cur[2], my_score))

        guild_rows = sorted(guild_map.values(), key=lambda x: (-x[2], x[0]))
        guild_ranks: list[dict[str, Any]] = []
        my_guild_rank = 0
        for rank_idx, (gname, srv, gscore) in enumerate(guild_rows, start=1):
            if my_guild_name and gname == my_guild_name:
                my_guild_rank = rank_idx
            guild_ranks.append(
                {
                    "Rank": rank_idx,
                    "GuildName": gname,
                    "ServerName": srv,
                    "Score": gscore,
                }
            )
        return player_ranks[:50], guild_ranks[:20], my_rank, my_guild_rank

    def _petout_payload(self, po: dict[str, Any]) -> dict[str, Any]:
        node_id = int(po.get("current_node_id", _PETOUT_MIN_NODE_ID))
        node_cfg = self._petout_node_cfg(node_id) or {"nodeType": 1, "payBoxID": 0}
        pcfg = self.game_data.get("petout_config", {})
        step_sec = max(60, int(pcfg.get("stepNums", 30)) * 60)
        now = self.now_ts()
        step_reset_ts = int(po.get("last_step_ts", now)) + step_sec
        node_reset_ts = now + 86400
        _, _, my_rank, guild_rank = self._petout_rank_lists(po)

        base_fields = {
            "CurrentNodeId": node_id,
            "Rank": my_rank,
            "GuildRank": guild_rank,
            "Score": int(po.get("score", 0)),
            "StepNum": int(po.get("step_num", _PETOUT_STEP_CAP)),
            "BuyStepCount": int(po.get("buy_step_count", 0)),
            "StepResetDate": step_reset_ts,
            "NodeResetDate": node_reset_ts,
        }
        if int(node_cfg.get("nodeType", 1)) == 2 and int(node_cfg.get("payBoxID", 0)) > 0:
            # Box stage MUST return flat top-level fields (no PetOutInfo wrapper) per PetChallengeScene.lua:75
            return {
                **base_fields,
                "BoxId": int(node_cfg["payBoxID"]),
                "FreeCount": int(pcfg.get("payBoxIDFreeNum", 1)),
                "OpenBoxNum": int(po.get("open_box_num", 0)),
            }

        target_summary = [
            {
                "TargetId": t["TargetId"],
                "HeroModelId": int(t["HeroModelId"]),
                "CurrentHP": sum(int(s["CurrentHP"]) for s in t["Slots"]),
                "TotalHP": max(1, sum(int(s["TotalHP"]) for s in t["Slots"])),
            }
            for t in po.get("node_targets", [])
        ]
        node_pet_info = [int(t["PetId"]) for t in po.get("node_targets", []) if int(t.get("PetId", 0)) > 0]
        return {
            "PetOutInfo": {
                **base_fields,
                "NodeInfo": {
                    "NodePetInfo": node_pet_info,
                    "TargetInfo": target_summary,
                },
            }
        }

    def _roll_petout_box_tuple(self, box_id: int) -> tuple[int, int, int] | None:
        rows = [
            row
            for row in self.game_data.get("petout_boxes", {}).values()
            if int(row.get("boxID", 0)) == int(box_id)
        ]
        if not rows:
            return None
        by_num_id: dict[int, list[dict[str, Any]]] = {}
        for r in rows:
            by_num_id.setdefault(int(r.get("numID", 1)), []).append(r)
        picked_group = random.choice(list(by_num_id.values()))
        max_roll = max((int(r.get("oddsMax", 0)) for r in picked_group), default=10000)
        roll = random.randint(1, max(1, max_roll))
        chosen = next(
            (r for r in picked_group if int(r.get("oddsMin", 0)) <= roll <= int(r.get("oddsMax", 0))),
            picked_group[0],
        )
        tuples = _parse_res_tuples(str(chosen.get("rewardResource", "")))
        return tuples[0] if tuples else None

    # ------------------------------------------------------------------
    # Sealed Cave (PetOutInfo) RPCs
    # ------------------------------------------------------------------

    def _rpc_petout_get_info(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        self.save()
        return self._petout_payload(po)

    def _rpc_petout_formation(self, data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        if not isinstance(data, list) or not data:
            return _pet_reject(self, -1)
        tid = str(data[0])
        target = next((t for t in po.get("node_targets", []) if t["TargetId"] == tid), None)
        if not target:
            return _pet_reject(self, -1)
        return {
            "Formation": {
                "SlotFormationInfo": [
                    {
                        "HeroModelId": int(s["HeroModelId"]),
                        "CurrentHP": int(s["CurrentHP"]),
                        "TotalHP": int(s["TotalHP"]),
                        "Step": int(s.get("step", 0)),
                        "Lv": int(s.get("Lv", 1)),
                    }
                    for s in target["Slots"]
                ],
                "FashionModelId": int(target.get("FashionModelId", 0)),
                "Name": target["Name"],
                "FAP": int(target["FAP"]),
                "PVPInterLv": int(target["PVPInterLv"]),
                "ServerName": target["ServerName"],
                "Lv": int(target["Lv"]),
                "HeroModelId": int(target["HeroModelId"]),
                "PetId": int(target.get("PetId", 0)),
            }
        }

    def _rpc_petout_fight(self, data: Any) -> dict[str, Any]:
        player = self.state["player"]
        if int(player.get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        node_id = int(po.get("current_node_id", _PETOUT_MIN_NODE_ID))
        node_cfg = self._petout_node_cfg(node_id)
        if not node_cfg or int(node_cfg.get("nodeType", 1)) != 1:
            return _pet_reject(self, -1)
        if not isinstance(data, list) or not data:
            return _pet_reject(self, -1)
        tid = str(data[0])
        target = next((t for t in po.get("node_targets", []) if t["TargetId"] == tid), None)
        if not target or sum(int(s["CurrentHP"]) for s in target["Slots"]) <= 0:
            return _pet_reject(self, -1)

        pcfg = self.game_data.get("petout_config", {})
        step_cost = int(pcfg.get("stepUse", 1))
        sta_cost = int(pcfg.get("needSTA", 2))
        if int(po.get("step_num", 0)) < step_cost:
            return _pet_reject(self, -1)
        if int(player.get("STA", 0)) < sta_cost:
            return _pet_reject(self, -1120)

        cur_step = int(po.get("step_num", 0))
        if cur_step >= _PETOUT_STEP_CAP:
            po["last_step_ts"] = self.now_ts()
        po["step_num"] = cur_step - step_cost
        self.ledger.apply_player_delta(player, self.profile_name, "STA", -sta_cost, source=f"petout_fight:{node_id}")

        allies = self._build_ally_fight_objs()
        heroes_cfg = self.game_data.get("heroes", {})
        enemies: list[dict[str, Any]] = [{} for _ in range(6)]
        pos_to_slot: dict[int, dict[str, Any]] = {}
        for idx, sl in enumerate(target["Slots"][:6]):
            if int(sl["CurrentHP"]) <= 0:
                continue
            cfg = heroes_cfg.get(str(sl["HeroModelId"]))
            if not cfg:
                continue
            override = {
                "HP": int(sl["TotalHP"]),
                "AP": int(sl["AP"]),
                "DEF": int(sl["DEF"]),
                "RP": int(sl.get("RP", 50)),
                "FSP": int(sl.get("FSP", 500)),
                "HIT": int(sl.get("HIT", 10000)),
                "DOD": int(sl.get("DOD", 0)),
                "CRI": int(sl.get("CRI", 0)),
                "TEN": int(sl.get("TEN", 0)),
                "BLO": int(sl.get("BLO", 0)),
                "BOG": int(sl.get("BOG", 0)),
                "CRId": int(sl.get("CRId", 0)),
                "TEND": int(sl.get("TEND", 0)),
                "DAMADD": int(sl.get("DAMADD", 0)),
                "DAMCUT": int(sl.get("DAMCUT", 0)),
                "DAMADDR": int(sl.get("DAMADDR", 0)),
                "DAMCUTR": int(sl.get("DAMCUTR", 0)),
            }
            unit = self._hero_fight_obj(
                cfg,
                lv=int(sl.get("Lv", 1)),
                step=int(sl.get("step", 0)),
                reborn_step=int(sl.get("rebornStep", 0)),
                override_stats=override,
            )
            unit["TotalHp"] = max(1, int(sl["TotalHP"]))
            unit["HP"] = max(1, int(sl["CurrentHP"]))
            fpos = int(sl.get("formation", idx + 1))
            fidx = fpos - 1 if 1 <= fpos <= 6 and not enemies[fpos - 1] else idx
            enemies[fidx] = unit
            pos_to_slot[7 + fidx] = sl

        ally_fsp = sum(int(u.get("FSP", 0)) for u in allies if u)
        enemy_fsp = sum(int(u.get("FSP", 0)) for u in enemies if u)
        fight_info = {
            "FightObjs": [
                {
                    "Heros": allies + enemies,
                    "TeamData": [
                        {"Fsp": ally_fsp, "Fap": int(player.get("FAP", 0))},
                        {"Fsp": enemy_fsp, "Fap": int(target["FAP"])},
                    ],
                    # Keep Pets empty to avoid missing .skel preload in BattleLoadingLayer.lua:269
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
        is_win = bool(outcome.won)

        if is_win:
            for sl in target["Slots"]:
                sl["CurrentHP"] = 0
        else:
            hp_rows = (outcome.verify_data.get("hp") or [[]])[0]
            hp_by_pos = {int(r["PosId"]): max(0, int(r["HP"])) for r in hp_rows}
            for pos_id, sl in pos_to_slot.items():
                if pos_id in hp_by_pos:
                    sl["CurrentHP"] = hp_by_pos[pos_id]

        target_dead = sum(int(s["CurrentHP"]) for s in target["Slots"]) <= 0
        if target_dead:
            is_win = True

        reward_tuples: list[tuple[int, int, int]] = []
        reward_tuples.extend(_parse_res_tuples(str(node_cfg.get("fightReward", "") or "")))
        if is_win:
            reward_tuples.extend(_parse_res_tuples(str(node_cfg.get("victoryReward", "") or "")))
            po["score"] = int(po.get("score", 0)) + int(node_cfg.get("score", 1))

            # If all 4 teams on this stage are now cleared, grant hatch Pet & advance node!
            all_cleared = all(sum(int(s["CurrentHP"]) for s in t["Slots"]) <= 0 for t in po.get("node_targets", []))
            if all_cleared:
                free_box_id = int(node_cfg.get("freeBoxID", 1))
                if free_box_id > 0:
                    pet_drop = self._roll_petout_box_tuple(free_box_id)
                    if pet_drop:
                        reward_tuples.append(pet_drop)
                if self._petout_node_cfg(node_id + 1) is not None:
                    po["current_node_id"] = node_id + 1
                    self._petout_spawn_node_targets(po, node_id + 1)

        base_res = (
            self._grant_resources_from_tuples(
                reward_tuples,
                source=f"petout_fight:{node_id}:{'win' if is_win else 'try'}",
                tx_prefix=f"petout_fight:{self.profile_name}:{node_id}:{self.now_ts()}:{uuid.uuid4()}",
            )
            if reward_tuples
            else []
        )
        self.save()
        return {
            "IsWin": is_win,
            "FightInfo": fight_info,
            "BaseGetGameResourceList": base_res or [{}],
        }

    def _rpc_petout_open_box(self, _data: Any) -> dict[str, Any]:
        player = self.state["player"]
        if int(player.get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        node_id = int(po.get("current_node_id", _PETOUT_MIN_NODE_ID))
        node_cfg = self._petout_node_cfg(node_id)
        if not node_cfg or int(node_cfg.get("nodeType", 1)) != 2:
            return _pet_reject(self, -1)
        box_id = int(node_cfg.get("payBoxID", 0))
        if box_id <= 0:
            return _pet_reject(self, -1)

        pcfg = self.game_data.get("petout_config", {})
        free_count = int(pcfg.get("payBoxIDFreeNum", 1))
        use_box_max = int(pcfg.get("useBoxNum", 10))
        open_num = int(po.get("open_box_num", 0))
        if open_num >= use_box_max:
            return _pet_reject(self, -1)

        if open_num >= free_count:
            paid_idx = open_num - free_count + 1
            buybox_tbl = self.game_data.get("petout_buybox", {}).get(str(box_id), {})
            max_k = max((int(k) for k in buybox_tbl), default=1)
            cost_row = buybox_tbl.get(str(min(paid_idx, max_k)), {})
            cost_tuples = _parse_res_tuples(str(cost_row.get("useResource", "1111,0,500")))
            dia_cost = sum(amt for rt, _rm, amt in cost_tuples if rt == 1111)
            if int(player.get("Diamond", 0)) < dia_cost:
                return _pet_reject(self, -1104)
            if dia_cost > 0:
                self.ledger.apply_player_delta(
                    player, self.profile_name, "Diamond", -dia_cost, source=f"petout_box:{box_id}:{paid_idx}"
                )

        reward_tuple = self._roll_petout_box_tuple(box_id)
        if not reward_tuple:
            return _pet_reject(self, -1)
        base_res = self._grant_resources_from_tuples(
            [reward_tuple],
            source=f"petout_open_box:{box_id}",
            tx_prefix=f"petout_box:{self.profile_name}:{node_id}:{open_num}:{uuid.uuid4()}",
        )
        po["open_box_num"] = open_num + 1
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_petout_next_node(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        cur_node = int(po.get("current_node_id", _PETOUT_MIN_NODE_ID))
        node_cfg = self._petout_node_cfg(cur_node)
        if not node_cfg:
            return _pet_reject(self, -1)
        all_cleared = all(sum(int(s["CurrentHP"]) for s in t["Slots"]) <= 0 for t in po.get("node_targets", []))
        if int(node_cfg.get("nodeType", 1)) != 2 and not all_cleared:
            return _pet_reject(self, -1)
        next_node = cur_node + 1
        if self._petout_node_cfg(next_node) is None:
            return _pet_reject(self, -1)
        po["current_node_id"] = next_node
        self._petout_spawn_node_targets(po, next_node)
        self.save()
        return self._petout_payload(po)

    def _rpc_petout_reset_node(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        po["current_node_id"] = _PETOUT_MIN_NODE_ID
        self._petout_spawn_node_targets(po, _PETOUT_MIN_NODE_ID)
        self.save()
        return self._petout_payload(po)

    def _rpc_petout_buy_step(self, data: Any) -> dict[str, Any]:
        player = self.state["player"]
        if int(player.get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        count = int(data[0]) if isinstance(data, list) and data else 1
        if count <= 0:
            return _pet_reject(self, -1)

        vip_lv = int(player.get("Vip", 0))
        vip_row = self.game_data.get("vip_model", {}).get(str(vip_lv), {})
        limit = int(vip_row.get("buyPetOutNum", vip_lv + 1))
        buyed = int(po.get("buy_step_count", 0))
        if buyed + count > limit:
            return _pet_reject(self, -1)

        use_tbl = self.game_data.get("petout_buystep", {})
        max_k = max((int(k) for k in use_tbl), default=14)
        total_dia = 0
        for i in range(1, count + 1):
            step_idx = min(buyed + i, max_k)
            row = use_tbl.get(str(step_idx), {})
            cost_tuples = _parse_res_tuples(str(row.get("useResource", "1111,0,100")))
            total_dia += sum(amt for rt, _rm, amt in cost_tuples if rt == 1111)

        if int(player.get("Diamond", 0)) < total_dia:
            return _pet_reject(self, -1104)
        if total_dia > 0:
            self.ledger.apply_player_delta(
                player, self.profile_name, "Diamond", -total_dia, source=f"petout_buy_step:{count}"
            )
        po["buy_step_count"] = buyed + count
        po["step_num"] = int(po.get("step_num", 0)) + count
        self.save()
        return self._petout_payload(po)

    def _rpc_petout_rank_list(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        player_ranks, guild_ranks, _r, _gr = self._petout_rank_lists(po)
        return {
            "PetOutPlayerRankList": player_ranks,
            "PetOutGuildRankList": guild_ranks,
        }

    def _petout_shop_payload(self, po: dict[str, Any]) -> dict[str, Any]:
        shop = po["shop"]
        return {
            "PetShopInfo": copy.deepcopy(shop["slots"]),
            "RefreshMysteryShopMaxNum": _PETOUT_SHOP_MAX_REFRESH,
            "FreeCount": int(shop.get("free_count", 0)),
            "PlayerRefreshCount": int(shop.get("player_refresh_count", 0)),
            "ShopNextRefreshTime": int(shop.get("next_refresh_time", self.now_ts() + 7200)),
        }

    def _rpc_petout_shop_list(self, _data: Any) -> dict[str, Any]:
        if int(self.state["player"].get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        self.save()
        return self._petout_shop_payload(po)

    def _rpc_petout_buy_goods(self, data: Any) -> dict[str, Any]:
        player = self.state["player"]
        if int(player.get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        if not isinstance(data, list) or not data:
            return _pet_reject(self, -1)
        slot_key = str(int(data[0]))
        entry = po["shop"].get("slots", {}).get(slot_key)
        if not entry or int(entry.get("IsSell", 0)) != 0:
            return _pet_reject(self, -1)

        utype = int(entry["PetUseResourceTypeSub"])
        ucost = int(entry["PetUseCount"])
        attr_field = {1111: "Diamond", 1112: "Gold", 2403: "PetSoul", 2404: "PetCoin"}.get(utype)
        if not attr_field or int(player.get(attr_field, 0)) < ucost:
            return _pet_reject(self, -1)
        self.ledger.apply_player_delta(
            player, self.profile_name, attr_field, -ucost, source=f"petout_shop:{slot_key}"
        )
        entry["IsSell"] = 1
        out_tuple = (
            int(entry["PetOutSourceType"]),
            int(entry["PetModudle"]),
            int(entry["PetOutCount"]),
        )
        base_res = self._grant_resources_from_tuples(
            [out_tuple],
            source=f"petout_shop:{slot_key}",
            tx_prefix=f"petout_shop:{self.profile_name}:{slot_key}:{self.now_ts()}:{uuid.uuid4()}",
        )
        self.save()
        return {"BaseGetGameResourceList": base_res}

    def _rpc_petout_shop_refresh(self, _data: Any) -> dict[str, Any]:
        player = self.state["player"]
        if int(player.get("Lv", 1)) < self._petout_open_lv():
            return _pet_reject(self, -1)
        po = self._ensure_petout_state()
        shop = po["shop"]
        refreshed = int(shop.get("player_refresh_count", 0))
        if refreshed >= _PETOUT_SHOP_MAX_REFRESH:
            return _pet_reject(self, -1)

        pcfg = self.game_data.get("petout_config", {})
        free_cnt = int(shop.get("free_count", 0))
        if free_cnt > 0:
            shop["free_count"] = free_cnt - 1
        else:
            token_tuples = _parse_res_tuples(str(pcfg.get("refreshUseResource", "1605,16050010,1")))
            token_gid = int(token_tuples[0][1]) if token_tuples else 16050010
            token_need = int(token_tuples[0][2]) if token_tuples else 1
            token_item = next(
                (g for g in self.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == token_gid and int(g.get("Num", 0)) >= token_need),
                None,
            )
            if token_item is not None:
                token_item["Num"] = int(token_item["Num"]) - token_need
                if token_item["Num"] <= 0:
                    self.state["goods"] = [g for g in self.state["goods"] if str(g.get("Id")) != str(token_item["Id"])]
                self._mark_goods_changed(token_gid)
            else:
                dia_cost = int(pcfg.get("refreshUseDiamond", 20))
                if int(player.get("Diamond", 0)) < dia_cost:
                    return _pet_reject(self, -1104)
                self.ledger.apply_player_delta(
                    player, self.profile_name, "Diamond", -dia_cost, source="petout_shop_refresh"
                )

        shop["player_refresh_count"] = refreshed + 1
        shop["slots"] = self._petout_roll_shop_slots()
        shop["next_refresh_time"] = self.now_ts() + max(60, int(pcfg.get("freeRefresh", 7200)))
        self.save()
        return self._petout_shop_payload(po)

    # ------------------------------------------------------------------
    # Red Dots
    # ------------------------------------------------------------------

    def _pet_red_dot(self) -> int:
        lv = int(self.state.get("player", {}).get("Lv", 1))
        open_lv = int(self.game_data.get("module_subs", {}).get("7400", {}).get("openLv", 45))
        if lv < open_lv:
            return 0
        pets = self.state.get("pets", [])
        if not pets:
            return 0
        deployed = self._deployed_pet_ids()
        if len(deployed) >= len(pets):
            return 0
        cp = self.state.get("player", {}).get("CombatPet") or []
        if not cp or str(cp[0]) == EMPTY_ENTITY_ID:
            return 1
        for slot in self.state.get("slots", []):
            hid = str(slot.get("HeroId", ""))
            pid = str(slot.get("Pet", ""))
            if hid and hid != EMPTY_ENTITY_ID and (not pid or pid == EMPTY_ENTITY_ID):
                return 1
        return 0

    def _pet_compare_red_dot(self) -> int:
        lv = int(self.state.get("player", {}).get("Lv", 1))
        open_lv = int(self.game_data.get("module_subs", {}).get("1414", {}).get("openLv", 42))
        if lv < open_lv:
            return 0
        need_num = int(self.game_data.get("pet_config", {}).get("colorUpNeedNums", 5))
        deployed = self._deployed_pet_ids()
        pet_tbl = self.game_data.get("pet_model", {})
        buckets: dict[int, int] = {}
        for p in self.state.get("pets", []):
            if str(p.get("Id", "")) in deployed or int(p.get("InheritNum", 0)) > 0:
                continue
            clv = int(pet_tbl.get(str(p.get("ModelId", 0)), {}).get("colorLV", 0))
            if 1 <= clv < 7:
                buckets[clv] = buckets.get(clv, 0) + 1
        return 1 if any(cnt >= need_num for cnt in buckets.values()) else 0

    def _petout_red_dot(self) -> int:
        if int(self.state.get("player", {}).get("Lv", 1)) < self._petout_open_lv():
            return 0
        po = self.state.get("pet_out")
        if not isinstance(po, dict):
            return 1
        return 1 if int(po.get("step_num", 0)) > 0 else 0
