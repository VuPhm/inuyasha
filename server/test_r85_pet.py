#!/usr/bin/env python3
"""End-to-end R8.5 tests: Pet (7400-7600, 1414), PetOut (7500), and TimedExchange Pet rotation."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
import random
import sys
import tempfile
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import EMPTY_ENTITY_ID, GameEmulatorState  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R85PetTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 25, 12, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict[str, Any]:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    @staticmethod
    def _grant(prof: Any, tuples: list[tuple[int, int, int]]) -> list[dict[str, Any]]:
        return prof._grant_resources_from_tuples(
            tuples, source="test_seed", tx_prefix=f"test:{len(prof.state.get('pets', []))}:{random.randint(1, 999999)}"
        )

    def test_01_init_data_eggs_skill_chests_and_formula(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=50, vip_lv=5)

            init_res = self._call(prof, "Player", "GetInitData")
            self.assertEqual(init_res["Status"], 0)
            open_mods = {int(m["SubModuleId"]) for m in init_res["Value"]["ModulesInfo"] if int(m["IfOpen"]) == 1}
            for mid in (1414, 7400, 7401, 7402, 7403, 7404, 7405, 7406, 7500, 7600):
                self.assertIn(mid, open_mods)

            self._grant(prof, [(1602, 16021001, 1), (1602, 16021028, 1), (1602, 16021016, 1)])
            egg1 = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16021001)
            egg2 = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16021028)
            chest = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == 16021016)

            r1 = self._call(prof, "Goods", "GoodsUse", egg1["Id"], 16021001, 1)
            self.assertEqual(r1["Status"], 0)
            pet1 = r1["Value"]["BaseGetGameResourceList"][0]["Pet"][0]
            cfg1 = prof.game_data["pet_model"][str(pet1["ModelId"])]
            pc = prof.game_data["pet_config"]
            exp_ap = min(int(pc["APMax"]), int(float(cfg1["petGrow"]) / 10000.0 * pet1["PetAPQua"] * pc["petAPR"] * 1))
            exp_hp = min(int(pc["HPMax"]), int(float(cfg1["petGrow"]) / 10000.0 * pet1["PetHPQua"] * pc["petHPR"] * 1))
            self.assertEqual(pet1["PetAP"], exp_ap)
            self.assertEqual(pet1["PetHP"], exp_hp)

            r2 = self._call(prof, "Goods", "GoodsUse", egg2["Id"], 16021028, 1)
            self.assertEqual(r2["Status"], 0)
            pet2 = r2["Value"]["BaseGetGameResourceList"][0]["Pet"][0]
            self.assertEqual(int(prof.game_data["pet_model"][str(pet2["ModelId"])]["colorLV"]), 4)

            rc = self._call(prof, "Goods", "GoodsUse", chest["Id"], 16021016, 1)
            self.assertEqual(rc["Status"], 0)
            book = rc["Value"]["BaseGetGameResourceList"][0]["Goods"][0]
            self.assertEqual(int(book["GoodsModelId"]) // 10000, 1614)

            init2 = self._call(prof, "Player", "GetInitData")
            self.assertEqual(len(init2["Value"]["PetInfo"]), 2)

    def test_02_slot_pet_combat_and_shelter_bonuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=50, vip_lv=3)
            # Deploy a 2nd hero into slot 2 so we can verify CombatPet vs ShelterPet scope
            self._grant(prof, [(1201, 12011005, 1), (2401, 24011805, 1), (2401, 24011304, 1)])
            hero2 = next(h for h in prof.state["heroes"] if int(h["HeroModelId"]) == 12011005)
            self.assertEqual(self._call(prof, "Slot", "HeroCombat", 2, hero2["Id"])["Status"], 0)

            pet_a, pet_b = prof.state["pets"][0], prof.state["pets"][1]
            # Remove random initial passive skills to assert deterministic base contribution first
            pet_a["SkillIds"]["4"] = [{"SkillId": 40764107, "SkillIndex": 1, "SkillExp": 0}]  # 412|1000 RADAMADDR
            pet_b["SkillIds"]["4"] = [{"SkillId": 40774105, "SkillIndex": 1, "SkillExp": 0}]  # 414|800 RBDAMADDR
            prof._recalc_pet_attrs(pet_a)
            prof._recalc_pet_attrs(pet_b)

            base_s1 = dict(prof.state["slots"][0]["Property"])
            base_s2 = dict(prof.state["slots"][1]["Property"])
            base_fap = int(prof.state["player"]["FAP"])

            # 1) Slot 0 = CombatPet (boosts ALL deployed slots)
            res_c0 = self._call(prof, "Slot", "PetCombat", 0, pet_a["Id"])
            self.assertEqual(res_c0["Status"], 0)
            self.assertEqual(prof.state["player"]["CombatPet"], [pet_a["Id"]])
            self.assertEqual(prof.state["slots"][0]["Property"]["AP"], base_s1["AP"] + pet_a["PetAP"])
            self.assertEqual(prof.state["slots"][1]["Property"]["AP"], base_s2["AP"] + pet_a["PetAP"])
            self.assertEqual(prof.state["slots"][0]["Property"]["RADAMADDR"], base_s1["RADAMADDR"] + 1000)
            self.assertEqual(prof.state["slots"][1]["Property"]["RADAMADDR"], base_s2["RADAMADDR"] + 1000)
            self.assertGreater(int(prof.state["player"]["FAP"]), base_fap)

            # Inspect formation exposes full pet dict on CombatPet for PlayerFormationLayer
            fmt = self._call(prof, "Slot", "SlotFormations", prof.state["player"]["PlayerId"])
            self.assertEqual(fmt["Status"], 0)
            self.assertEqual(fmt["Value"]["CombatPet"]["Id"], pet_a["Id"])

            # 2) Slot 2 = Shelter Pet (boosts slot 2 ONLY)
            s1_before = dict(prof.state["slots"][0]["Property"])
            s2_before = dict(prof.state["slots"][1]["Property"])
            res_s2 = self._call(prof, "Slot", "PetCombat", 2, pet_b["Id"])
            self.assertEqual(res_s2["Status"], 0)
            self.assertEqual(prof.state["slots"][0]["Property"]["AP"], s1_before["AP"])
            self.assertEqual(prof.state["slots"][1]["Property"]["AP"], s2_before["AP"] + pet_b["PetAP"])
            self.assertEqual(prof.state["slots"][1]["Property"]["RBDAMADDR"], s2_before["RBDAMADDR"] + 800)

            # 3) Move pet_b to slot 1 -> automatically detaches from slot 2
            self.assertEqual(self._call(prof, "Slot", "PetCombat", 1, pet_b["Id"])["Status"], 0)
            self.assertEqual(prof.state["slots"][1]["Pet"], "")
            self.assertEqual(prof.state["slots"][0]["Pet"], pet_b["Id"])

            # 4) Unequip both -> stats return to baseline
            self.assertEqual(self._call(prof, "Slot", "PetCombat", 0, EMPTY_ENTITY_ID)["Status"], 0)
            self.assertEqual(self._call(prof, "Slot", "PetCombat", 1, EMPTY_ENTITY_ID)["Status"], 0)
            self.assertEqual(prof.state["slots"][0]["Property"]["AP"], base_s1["AP"])
            self.assertEqual(prof.state["slots"][1]["Property"]["AP"], base_s2["AP"])
            self.assertEqual(int(prof.state["player"]["FAP"]), base_fap)

    def test_03_lv_up_inherit_and_rebirth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=50, vip_lv=3)
            self._grant(prof, [(2401, 24011304, 1), (2401, 24012703, 1), (2401, 24010101, 1)])
            main_pet, exp_pet, eq_pet = prof.state["pets"][0], prof.state["pets"][1], prof.state["pets"][2]

            # Equip eq_pet so inherit/rebirth guards reject it
            self.assertEqual(self._call(prof, "Slot", "PetCombat", 1, eq_pet["Id"])["Status"], 0)

            # PetLvUp without enough PetSoul should reject (-1)
            prof.state["player"]["PetSoul"] = 0
            self.assertEqual(self._call(prof, "Pet", "PetLvUp", main_pet["Id"], 1)["Status"], -1)

            # Grant Gold & PetSoul, upgrade 1 lv then 5 lvs -> Value is direct Pet dict
            prof.state["player"]["Gold"] = 500_000
            prof.state["player"]["PetSoul"] = 200_000
            r1 = self._call(prof, "Pet", "PetLvUp", main_pet["Id"], 1)
            self.assertEqual(r1["Status"], 0)
            self.assertEqual(r1["Value"]["Lv"], 2)
            r5 = self._call(prof, "Pet", "PetLvUp", main_pet["Id"], 5)
            self.assertEqual(r5["Status"], 0)
            self.assertEqual(r5["Value"]["Lv"], 7)
            gold_after_lvup = int(prof.state["player"]["Gold"])
            soul_after_lvup = int(prof.state["player"]["PetSoul"])
            self.assertLess(gold_after_lvup, 500_000)
            self.assertLess(soul_after_lvup, 200_000)

            # Equipped pet cannot be devoured
            self.assertEqual(self._call(prof, "Pet", "PetInherit", main_pet["Id"], eq_pet["Id"])["Status"], -1)

            # Devour EXP pet -> InheritNum increments, Lv rises, fodder removed
            r_inh = self._call(prof, "Pet", "PetInherit", main_pet["Id"], exp_pet["Id"])
            self.assertEqual(r_inh["Status"], 0)
            self.assertEqual(r_inh["Value"]["InheritNum"], 1)
            self.assertGreater(r_inh["Value"]["Lv"], 7)
            self.assertIsNone(prof._find_pet(exp_pet["Id"]))

            # Unequip & test PetRebirth vs equipped rejection
            self.assertEqual(self._call(prof, "Pet", "PetRebirth", eq_pet["Id"])["Status"], -1)
            prof.state["player"]["Diamond"] = 1000
            r_rb = self._call(prof, "Pet", "PetRebirth", [main_pet["Id"]])
            self.assertEqual(r_rb["Status"], 0)
            self.assertEqual(r_rb["Value"]["PetInfo"]["Lv"], 1)
            self.assertEqual(r_rb["Value"]["PetInfo"]["InheritNum"], 0)
            self.assertEqual(prof.state["player"]["Gold"], 500_000)
            self.assertEqual(prof.state["player"]["PetSoul"], 200_000)

    def test_04_skill_books_order_and_colorup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, prof = self._new_emu(tmp)
            prof.admin_prepare_account(target_lv=50, vip_lv=3)
            # 24012307: 7★ pet with actSkillMax=4+, pasSkillMax=4+
            self._grant(prof, [(2401, 24012307, 1)])
            pet = prof.state["pets"][0]
            # Force clean skill slate so test is 100% deterministic
            base_act = int(prof.game_data["pet_model"][str(pet["ModelId"])]["baseSkillID"])
            pet["SkillIds"] = {"1": [], "3": [{"SkillId": base_act, "SkillIndex": 1, "SkillExp": 0}], "4": []}
            prof._recalc_pet_attrs(pet)

            # Find 2 active skill books + 2 passive skill books (for testing replace/commit)
            act_books = [
                int(gid)
                for gid, gm in prof.game_data["goods_model"].items()
                if int(gm.get("typeID", 0)) == 1614
                and int(prof.game_data["pet_skill"].get(str(gm.get("outputModelID", 0)), {}).get("actOrPas", 0)) == 1
                and int(prof.game_data["pet_skill"].get(str(gm.get("outputModelID", 0)), {}).get("colorLV", 0)) == 2
            ][:2]
            pas_books = [
                int(gid)
                for gid, gm in prof.game_data["goods_model"].items()
                if int(gm.get("typeID", 0)) == 1614
                and int(prof.game_data["pet_skill"].get(str(gm.get("outputModelID", 0)), {}).get("actOrPas", 0)) == 4
                and int(prof.game_data["pet_skill"].get(str(gm.get("outputModelID", 0)), {}).get("colorLV", 0)) == 2
            ][:6]
            self.assertGreaterEqual(len(act_books), 2)
            self.assertGreaterEqual(len(pas_books), 6)
            self._grant(prof, [(1614, bid, 1) for bid in act_books + pas_books])

            # Learn 2 active skills -> ExchangeSkillId=0
            for bid in act_books:
                b_ent = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == bid)
                res_l = self._call(prof, "Pet", "LearnPetBook", pet["Id"], b_ent["Id"])
                self.assertEqual(res_l["Status"], 0)
                self.assertEqual(res_l["Value"]["ExchangeSkillId"], 0)

            # Reorder active skills cleanly
            cur_act_ids = [int(s["SkillId"]) for s in prof._pet_active_skills(prof._find_pet(pet["Id"]))]
            rev_ids = list(reversed(cur_act_ids))
            r_ord = self._call(prof, "Pet", "OrderPetSkill", pet["Id"], rev_ids)
            self.assertEqual(r_ord["Status"], 0)
            after_ids = [int(s["SkillId"]) for s in prof._pet_active_skills(r_ord["Value"]["PetInfo"])]
            self.assertEqual(after_ids, rev_ids)

            # Fill all passive slots (pasSkillMax=5 for 24012307) then test full-slot replace cancel & commit
            pas_max = int(prof.game_data["pet_model"][str(pet["ModelId"])]["pasSkillMax"])
            for bid in pas_books[:pas_max]:
                b_ent = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == bid)
                res_p = self._call(prof, "Pet", "LearnPetBook", pet["Id"], b_ent["Id"])
                self.assertEqual(res_p["Status"], 0)
                self.assertEqual(res_p["Value"]["ExchangeSkillId"], 0)

            # Next passive book triggers ExchangeSkillId > 0
            extra_bid = pas_books[pas_max]
            extra_ent = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == extra_bid)
            res_prompt = self._call(prof, "Pet", "LearnPetBook", pet["Id"], extra_ent["Id"])
            self.assertEqual(res_prompt["Status"], 0)
            old_sid = int(res_prompt["Value"]["ExchangeSkillId"])
            new_sid = int(res_prompt["Value"]["GetedSkillId"])
            self.assertGreater(old_sid, 0)
            # Cancel keeps old skill
            res_cancel = self._call(prof, "Pet", "CommitLearnPetBook", pet["Id"], 0)
            self.assertEqual(res_cancel["Status"], 0)
            self.assertIn(old_sid, [int(s["SkillId"]) for s in res_cancel["Value"]["PetInfo"]["SkillIds"]["4"]])
            self.assertNotIn(new_sid, [int(s["SkillId"]) for s in res_cancel["Value"]["PetInfo"]["SkillIds"]["4"]])

            # Repeat with another copy & confirm replacement (commit=1)
            self._grant(prof, [(1614, extra_bid, 1)])
            extra_ent2 = next(g for g in prof.state["goods"] if int(g["GoodsModelId"]) == extra_bid)
            res_prompt2 = self._call(prof, "Pet", "LearnPetBook", pet["Id"], extra_ent2["Id"])
            self.assertGreater(int(res_prompt2["Value"]["ExchangeSkillId"]), 0)
            res_ok = self._call(prof, "Pet", "CommitLearnPetBook", pet["Id"], 1)
            self.assertEqual(res_ok["Status"], 0)
            self.assertIn(new_sid, [int(s["SkillId"]) for s in res_ok["Value"]["PetInfo"]["SkillIds"]["4"]])

            # Test PetColorup: 5 x 1★ -> 1 x 2★
            self._grant(prof, [(2401, 24010101, 5)])
            star1_pets = [p for p in prof.state["pets"] if int(p["ModelId"]) == 24010101]
            self.assertEqual(len(star1_pets), 5)
            # Reject if mixed stars or <5
            self.assertEqual(self._call(prof, "Pet", "PetColorup", [p["Id"] for p in star1_pets[:4]])["Status"], -1)
            self.assertEqual(self._call(prof, "Pet", "PetColorup", [p["Id"] for p in star1_pets[:4]] + [pet["Id"]])["Status"], -1)
            # Reject if InheritNum > 0
            star1_pets[0]["InheritNum"] = 1
            self.assertEqual(self._call(prof, "Pet", "PetColorup", [p["Id"] for p in star1_pets])["Status"], -1)
            star1_pets[0]["InheritNum"] = 0

            res_up = self._call(prof, "Pet", "PetColorup", [p["Id"] for p in star1_pets])
            self.assertEqual(res_up["Status"], 0)
            new_pet = res_up["Value"]["BaseGetGameResourceList"][0]["Pet"][0]
            self.assertEqual(int(prof.game_data["pet_model"][str(new_pet["ModelId"])]["colorLV"]), 2)
            for p in star1_pets:
                self.assertIsNone(prof._find_pet(p["Id"]))

    def test_05_petout_full_loop_rank_and_shop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, prof = self._new_emu(tmp)
            # Prepare strong squad able to clear stages 11..13 cleanly
            prof.admin_prepare_account(target_lv=60, vip_lv=5)
            prof.state["player"]["Diamond"] = 50_000
            prof.state["player"]["STA"] = 500
            for slot in prof.state["slots"]:
                if slot.get("HeroId") and slot["HeroId"] != EMPTY_ENTITY_ID:
                    slot["Property"]["HP"] = 5_000_000
                    slot["Property"]["AP"] = 1_500_000
                    slot["Property"]["DEF"] = 500_000
                    slot["Property"]["FAP"] = 25_000_000
            prof.state["player"]["FAP"] = 100_000_000

            info11 = self._call(prof, "PetOutInfo", "GetPetOutInfo")
            self.assertEqual(info11["Status"], 0)
            self.assertIn("PetOutInfo", info11["Value"])
            self.assertEqual(info11["Value"]["PetOutInfo"]["CurrentNodeId"], 11)
            targets11 = info11["Value"]["PetOutInfo"]["NodeInfo"]["TargetInfo"]
            self.assertEqual(len(targets11), 4)

            # Cannot skip uncleared node via NextNode
            self.assertEqual(self._call(prof, "PetOutInfo", "NextNode")["Status"], -1)

            # Inspect formation
            fmt = self._call(prof, "PetOutInfo", "Formation", targets11[0]["TargetId"])
            self.assertEqual(fmt["Status"], 0)
            self.assertGreater(len(fmt["Value"]["Formation"]["SlotFormationInfo"]), 0)

            # Test persistent HP on defeat with weak stats on 1st fight, then restore strong stats
            orig_ap = prof.state["slots"][0]["Property"]["AP"]
            orig_hp = prof.state["slots"][0]["Property"]["HP"]
            prof.state["slots"][0]["Property"]["AP"] = 50_000
            prof.state["slots"][0]["Property"]["HP"] = 50_000
            loss_try = self._call(prof, "PetOutInfo", "Fight", targets11[0]["TargetId"])
            self.assertEqual(loss_try["Status"], 0)
            self.assertFalse(loss_try["Value"]["IsWin"])
            prof.state["slots"][0]["Property"]["AP"] = orig_ap
            prof.state["slots"][0]["Property"]["HP"] = orig_hp

            # BuyStep to guarantee enough StepNum across stages 11..13 (4*3 = 12 fights + 1 loss)
            bs_res = self._call(prof, "PetOutInfo", "BuyStep", 5)
            self.assertEqual(bs_res["Status"], 0)
            self.assertGreaterEqual(bs_res["Value"]["PetOutInfo"]["StepNum"], 13)

            # Clear stages 11, 12, 13 -> verify Pet drops on stage clears & stage 14 enters Box mode!
            pets_before = len(prof.state.get("pets", []))
            for expected_node in (11, 12, 13):
                cur_info = self._call(prof, "PetOutInfo", "GetPetOutInfo")["Value"]["PetOutInfo"]
                self.assertEqual(cur_info["CurrentNodeId"], expected_node)
                for idx, t in enumerate(cur_info["NodeInfo"]["TargetInfo"]):
                    f_res = self._call(prof, "PetOutInfo", "Fight", t["TargetId"])
                    self.assertEqual(f_res["Status"], 0)
                    self.assertTrue(f_res["Value"]["IsWin"])
                    self.assertEqual(f_res["Value"]["FightInfo"]["FightObjs"][0]["Pets"], [])
                    if idx == 3:
                        self.assertIn("Pet", f_res["Value"]["BaseGetGameResourceList"][0])
            self.assertEqual(len(prof.state["pets"]), pets_before + 3)

            # Stage 14 (nodeType=2) MUST return flat top-level payload with NO PetOutInfo wrapper!
            box_info = self._call(prof, "PetOutInfo", "GetPetOutInfo")
            self.assertEqual(box_info["Status"], 0)
            self.assertNotIn("PetOutInfo", box_info["Value"])
            self.assertEqual(box_info["Value"]["CurrentNodeId"], 14)
            self.assertEqual(box_info["Value"]["BoxId"], 2)
            self.assertEqual(box_info["Value"]["FreeCount"], 1)
            self.assertEqual(box_info["Value"]["OpenBoxNum"], 0)

            # Open box: #1 free, #2 costs 500 Diamonds
            dia_before = int(prof.state["player"]["Diamond"])
            ob1 = self._call(prof, "PetOutInfo", "OpenBox")
            self.assertEqual(ob1["Status"], 0)
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia_before)
            ob2 = self._call(prof, "PetOutInfo", "OpenBox")
            self.assertEqual(ob2["Status"], 0)
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia_before - 500)

            # NextNode -> stage 15, then ResetNodeInfo -> stage 11
            n15 = self._call(prof, "PetOutInfo", "NextNode")
            self.assertEqual(n15["Status"], 0)
            self.assertEqual(n15["Value"]["PetOutInfo"]["CurrentNodeId"], 15)
            r11 = self._call(prof, "PetOutInfo", "ResetNodeInfo")
            self.assertEqual(r11["Status"], 0)
            self.assertEqual(r11["Value"]["PetOutInfo"]["CurrentNodeId"], 11)

            # Rank list
            ranks = self._call(prof, "PetOutInfo", "GetPetOutRankList")
            self.assertEqual(ranks["Status"], 0)
            self.assertGreater(len(ranks["Value"]["PetOutPlayerRankList"]), 0)
            self.assertGreater(len(ranks["Value"]["PetOutGuildRankList"]), 0)

            # PetShop: PetModudle key exact match, buy goods, refresh free -> token -> diamond
            shop1 = self._call(prof, "PetOutInfo", "GetPetShopList")
            self.assertEqual(shop1["Status"], 0)
            slots = shop1["Value"]["PetShopInfo"]
            self.assertEqual(sorted(slots.keys()), ["1", "2", "3", "4", "5", "6"])
            self.assertIn("PetModudle", slots["1"])
            prof.state["player"]["PetCoin"] = 5000
            buy1 = self._call(prof, "PetOutInfo", "PetOutBuyGoods", 1)
            self.assertEqual(buy1["Status"], 0)
            self.assertEqual(prof.state["pet_out"]["shop"]["slots"]["1"]["IsSell"], 1)

            # Free refresh (3 -> 2 -> 1 -> 0), then token 16050010, then 20 Diamonds
            self._grant(prof, [(1605, 16050010, 1)])
            for _ in range(3):
                rf = self._call(prof, "PetOutInfo", "PetShopRefresh")
                self.assertEqual(rf["Status"], 0)
            self.assertEqual(rf["Value"]["FreeCount"], 0)
            rf_tok = self._call(prof, "PetOutInfo", "PetShopRefresh")
            self.assertEqual(rf_tok["Status"], 0)
            dia_pre_ref = int(prof.state["player"]["Diamond"])
            rf_dia = self._call(prof, "PetOutInfo", "PetShopRefresh")
            self.assertEqual(rf_dia["Status"], 0)
            self.assertEqual(int(prof.state["player"]["Diamond"]), dia_pre_ref - 20)

    def test_06_timed_exchange_pet_rotation_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, prof = self._new_emu(tmp, ts=_ts_vn(2026, 11, 1, 12, 0))
            prof.admin_prepare_account(target_lv=50, vip_lv=5)
            prof.state["player"]["Diamond"] = 100_000

            seen_s26: set[tuple[int, int]] = set()
            seen_s27: set[int] = set()
            for day_offset in range(19):
                emu.clock.set_fixed(_ts_vn(2026, 11, 1 + day_offset, 12, 0))
                info = self._call(prof, "TimedLimitExchange", "GetInfo")["Value"]
                by_ser = {int(r["Serial"]): r for r in info["ActivityList"]}
                self.assertEqual(sorted(by_ser.keys()), list(range(1, 29)))
                g26 = by_ser[26]["ExchaneGameResourceList"][0]
                g27 = by_ser[27]["ExchaneGameResourceList"][0]
                seen_s26.add((int(g26["ResourceTypeSub"]), int(g26["ModelId"])))
                seen_s27.add(int(g27["ModelId"]))

            self.assertIn((2401, 24012601), seen_s26)
            self.assertIn((2401, 24012701), seen_s26)
            self.assertEqual(len(seen_s26), 19)
            self.assertGreaterEqual(len(seen_s27), 14)

            ex26 = self._call(prof, "TimedLimitExchange", "Exchange", 26, 1)
            ex27 = self._call(prof, "TimedLimitExchange", "Exchange", 27, 1)
            ex28 = self._call(prof, "TimedLimitExchange", "Exchange", 28, 1)
            self.assertEqual(ex26["Status"], 0)
            self.assertEqual(ex27["Status"], 0)
            self.assertEqual(ex28["Status"], 0)

            # Deploy & save, then reload from disk to verify persistence
            self._grant(prof, [(2401, 24010101, 1)])
            p_id = prof.state["pets"][-1]["Id"]
            self.assertEqual(self._call(prof, "Slot", "PetCombat", 0, p_id)["Status"], 0)
            self._call(prof, "PetOutInfo", "GetPetOutInfo")

            emu2 = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True, trace_path=Path(tmp) / "rpc.log")
            prof2 = emu2.profiles["normal"]
            self.assertEqual(prof2.state["player"]["CombatPet"], [p_id])
            self.assertIsNotNone(prof2._find_pet(p_id))
            self.assertGreaterEqual(int(prof2.state["player"]["PetSoul"]), 10000)
            self.assertGreaterEqual(int(prof2.state["player"]["PetCoin"]), 200)
            self.assertEqual(int(prof2.state["pet_out"]["current_node_id"]), 11)


if __name__ == "__main__":
    unittest.main()
