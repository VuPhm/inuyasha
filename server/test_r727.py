"""Delta coverage for R7.27 (TASK-N02B): Reborn System (8 RPCs), Reborn Stats/Cheer/Master, 11 UAID, & BDD Floor 27."""

from __future__ import annotations

from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from bdd_handlers import bdd_recommended_fap  # noqa: E402
from combat_effects import supports_talent_buff  # noqa: E402
from combat_sim import simulate_fight_info  # noqa: E402
from emulator import GameEmulatorState  # noqa: E402

UAID_HERO_MODELS: dict[int, int] = {
    12011002: 1003001,  # Inu no Taishou
    12011003: 1003002,  # Kikyo
    12011004: 1003003,  # InuYasha
    12012003: 1003004,  # Kanade Hime
    12012004: 1003005,  # Midoriko
    12012005: 1003006,  # Sesshomaru
    12013003: 1003007,  # Takemaru
    12013004: 1003008,  # Kaguya
    12013005: 1003009,  # Naraku
    12015022: 1003010,  # Tu Dau Than
    12015023: 1003011,  # Inu Kimi
}


class R727RebornAndBddFloor27Test(unittest.TestCase):
    def _new_emu(self, tmpdir: str) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
        emu.clock.set_fixed(1795176000)
        p = emu.profiles["normal"]
        return emu, p

    @staticmethod
    def _call(emu: GameEmulatorState, mod: str, fn: str, *args: Any) -> dict[str, Any]:
        return emu.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    def test_01_reborn_vn_configs_extracted_with_canonical_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, p = self._new_emu(tmp)
            gd = p.game_data
            self.assertEqual(gd["reborn_config"]["refreshNum"], 8)
            self.assertEqual(gd["reborn_config"]["freeRefreshCD"], 7200)
            self.assertEqual(gd["reborn_config"]["freeRefreshMax"], 2)
            self.assertEqual(len(gd["reborn_lv"]), 340)
            self.assertEqual(len(gd["reborn_lv_active"]), 9)
            self.assertEqual(len(gd["reborn_prtype"]), 34)
            self.assertEqual(len(gd["reborn_shop_odds"]), 61)
            self.assertEqual(len(gd["reborn_slots"]), 340)
            self.assertTrue(all(len(slots) == 4 for slots in gd["reborn_slots"].values()))
            self.assertEqual(len(gd["hero_reborn_cheer"]), 84)
            self.assertEqual(len(gd["reborn_goods"]), 28)

    def test_02_reborn_activate_compose_one_key_upgrade_refine_and_rebirth_refund(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.state["player"].update(Lv=75, Gold=50_000_000, Diamond=50_000)
            hero = p._build_hero_instance(12011004, lv=75, step=5)
            self.assertEqual(hero["RebornId"], 16000)
            self.assertEqual(len(hero["RebornStepInfo"]), 4)
            p.state["heroes"].append(hero)
            p.state["slots"][1].update(HeroId=hero["Id"], HeroModelId=12011004)
            p._recalc_all_slots_and_fap()
            base_fap = int(p.state["slots"][1]["FAP"])

            # 1. Activate fails cleanly without material, succeeds with 27010101
            self.assertEqual(self._call(emu, "RebornInfo", "Activate", hero["Id"], 1)["Status"], -1126)
            p._grant_resources_from_tuples([(2701, 27010101, 1)], "test", "seed_act_1")
            r_act = self._call(emu, "RebornInfo", "Activate", hero["Id"], 1)
            self.assertEqual(r_act["Status"], 0)
            self.assertEqual(r_act["Value"]["RebornStepInfo"][0]["Status"], 1)
            self.assertGreater(int(r_act["Avatar"]["SlotInfo"][1]["FAP"]), base_fap)
            self.assertEqual(r_act["Avatar"]["RebornGoodsList"]["27010101"], [])

            # 2. RebornGoodsCompose crafts 27010301 from compoundUse (27010101 x2 + 27010102 + 27010103)
            self.assertEqual(self._call(emu, "RebornInfo", "RebornGoodsCompose", 27010301)["Status"], -1126)
            p._grant_resources_from_tuples(
                [(2701, 27010101, 2), (2701, 27010102, 1), (2701, 27010103, 1)],
                "test",
                "seed_comp",
            )
            r_cmp = self._call(emu, "RebornInfo", "RebornGoodsCompose", 27010301)
            self.assertEqual(r_cmp["Status"], 0)
            self.assertEqual(p._reborn_goods_counts().get(27010301), 1)
            self.assertEqual(p._reborn_goods_counts().get(27010101, 0), 0)

            # 3. RebornGoodsRefine converts 27010301 -> RebornCoin (1128)
            coin_before = int(p.state["player"].get("RebornCoin", 0))
            r_ref = self._call(emu, "RebornInfo", "RebornGoodsRefine", 27010301, 1)
            self.assertEqual(r_ref["Status"], 0)
            self.assertEqual(int(p.state["player"]["RebornCoin"]) - coin_before, 19)
            self.assertEqual(p._reborn_goods_counts().get(27010301, 0), 0)

            # 4. ComposeAndActivateForOneKey uses recursive crafting from Tier-1 materials to finish slots 2..4
            p._grant_resources_from_tuples(
                [(2701, 27010102, 1), (2701, 27010103, 1), (2701, 27010104, 1)],
                "test",
                "seed_onekey",
            )
            r_ok = self._call(emu, "RebornInfo", "ComposeAndActivateForOneKey", hero["Id"])
            self.assertEqual(r_ok["Status"], 0)
            self.assertTrue(all(s["Status"] == 1 for s in hero["RebornStepInfo"]))

            # 5. Reborn advances 16000 -> 16001 using 16050065 stones & Gold, resets 4 slots to Status=0
            p._grant_resources_from_tuples([(1605, 16050065, 110)], "test", "seed_stones_0")
            r_up = self._call(emu, "RebornInfo", "Reborn", hero["Id"], [])
            self.assertEqual(r_up["Status"], 0)
            self.assertEqual(r_up["Value"]["RebornId"], 16001)
            self.assertTrue(all(s["Status"] == 0 for s in r_up["Value"]["RebornStepInfo"]))

            # Verify recursive OneKey crafting of higher-tier slot (16002 slot 3 uses 27010303!)
            hero["RebornId"] = 16009
            hero["RebornStepInfo"] = [{"Num": i, "Status": 1} for i in range(1, 5)]
            p._grant_resources_from_tuples([(1605, 16050065, 400)], "test", "seed_stones_9")
            # 16009 -> 16010 requires 1 duplicate InuYasha card (specialType != 255)
            self.assertEqual(self._call(emu, "RebornInfo", "Reborn", hero["Id"], [])["Status"], -1)
            dupe = p._build_hero_instance(12011004, lv=1, step=0)
            p.state["heroes"].append(dupe)
            r_up10 = self._call(emu, "RebornInfo", "Reborn", hero["Id"], [dupe["Id"]])
            self.assertEqual(r_up10["Status"], 0)
            self.assertEqual(hero["RebornId"], 16010)
            self.assertEqual(hero["RebornStep"], 1)
            self.assertNotIn(dupe["Id"], {h["Id"] for h in p.state["heroes"]})

            # Verify recursive crafting of 27010303 (needs 27010103x2 + 27010104 + 27010101)
            hero["RebornId"] = 16002
            hero["RebornStepInfo"] = [{"Num": i, "Status": 0} for i in range(1, 5)]
            p._grant_resources_from_tuples(
                [(2701, 27010101, 3), (2701, 27010102, 2), (2701, 27010103, 3), (2701, 27010104, 2)],
                "test",
                "seed_recursive",
            )
            r_rec = self._call(emu, "RebornInfo", "ComposeAndActivateForOneKey", hero["Id"])
            self.assertEqual(r_rec["Status"], 0)
            self.assertTrue(all(s["Status"] == 1 for s in hero["RebornStepInfo"]))

            # 6. Undeploy hero and call Hero.HeroRebirth -> refunds Reborn 2701 mats, stones, Gold, and resets RebornId
            p.state["slots"][1].update(HeroId="00000000-0000-0000-0000-000000000000", HeroModelId=0)
            stones_before = p._goods_qty(16050065)
            rb_rb = self._call(emu, "Hero", "HeroRebirth", hero["Id"])
            self.assertEqual(rb_rb["Status"], 0)
            self.assertEqual(hero["RebornId"], 16000)
            self.assertEqual(hero["RebornStep"], 0)
            self.assertTrue(all(s["Status"] == 0 for s in hero["RebornStepInfo"]))
            self.assertGreater(p._goods_qty(16050065), stones_before)
            self.assertGreater(sum(p._reborn_goods_counts().values()), 0)

    def test_03_reborn_shop_get_refresh_and_buy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.state["player"].update(Lv=60, Diamond=5000, RebornCoin=10_000, Gold=5_000_000)

            info = self._call(emu, "RebornShop", "GetInfo")
            self.assertEqual(info["Status"], 0)
            val = info["Value"]
            self.assertEqual(val["FreeCount"], 2)
            self.assertEqual(val["FreeRefreshMax"], 2)
            self.assertEqual(len(val["RebornShopGoodsData"]), 8)
            first_ids = [g["Id"] for g in val["RebornShopGoodsData"]]

            # Free refresh (type=1)
            r1 = self._call(emu, "RebornShop", "RefreshtGoodsList", 1)
            self.assertEqual(r1["Status"], 0)
            self.assertEqual(r1["Value"]["FreeCount"], 1)
            self.assertNotEqual([g["Id"] for g in r1["Value"]["RebornShopGoodsData"]], first_ids)

            # Advance clock 2h (7200s) -> free count recovers to 2
            emu.clock.set_fixed(1795176000 + 7200)
            r_rec = self._call(emu, "RebornShop", "GetInfo")
            self.assertEqual(r_rec["Value"]["FreeCount"], 2)

            # Token refresh (type=2, consumes 16050010)
            self.assertEqual(self._call(emu, "RebornShop", "RefreshtGoodsList", 2)["Status"], -1126)
            p._grant_resources_from_tuples([(1605, 16050010, 1)], "test", "seed_shop_tok")
            r2 = self._call(emu, "RebornShop", "RefreshtGoodsList", 2)
            self.assertEqual(r2["Status"], 0)
            self.assertEqual(p._goods_qty(16050010), 0)

            # Diamond refresh (type=3, costs 20 KC)
            dia_before = int(p.state["player"]["Diamond"])
            r3 = self._call(emu, "RebornShop", "RefreshtGoodsList", 3)
            self.assertEqual(r3["Status"], 0)
            self.assertEqual(dia_before - int(p.state["player"]["Diamond"]), 20)
            self.assertEqual(r3["Value"]["DiamondCount"], 1)

            # Low diamond fails with -1105
            p.state["player"]["Diamond"] = 5
            self.assertEqual(self._call(emu, "RebornShop", "RefreshtGoodsList", 3)["Status"], -1105)
            p.state["player"]["Diamond"] = 5000

            # Buy coin item & verify IsSell=1, double-buy blocked, resource granted
            goods_list = r3["Value"]["RebornShopGoodsData"]
            target = next(g for g in goods_list if int(g["BuyResourceTypeSub"]) == 1128)
            r_buy = self._call(emu, "RebornShop", "RebornShopBuyGoods", target["Id"])
            self.assertEqual(r_buy["Status"], 0)
            self.assertEqual(len(r_buy["Value"]["BaseGetGameResourceList"]), 1)
            self.assertEqual(self._call(emu, "RebornShop", "RebornShopBuyGoods", target["Id"])["Status"], -1)

    def test_04_reborn_stats_dashi_cheer_and_all_11_uaid_talents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.state["player"].update(Lv=80, StarId=350)

            # Verify all 11 UAID heroes keep RAID below RebornId=16090 and switch to UAID at >=16090
            # Note: includes Tu Dau Than (12015022 -> 1003010) and Inu Kimi (12015023 -> 1003011)
            for mid, expected_uaid in UAID_HERO_MODELS.items():
                cfg = p.game_data["heroes"][str(mid)]
                self.assertEqual(p._hero_reborn_class_id(cfg), 16, mid)
                fo_before = p._hero_fight_obj(cfg, lv=80, step=15, reborn_id=16089)
                fo_unlock = p._hero_fight_obj(cfg, lv=80, step=15, reborn_id=16090)
                fo_max = p._hero_fight_obj(cfg, lv=80, step=15, reborn_id=16099)
                self.assertEqual(fo_before["RAId"], int(cfg["RAID"]), mid)
                self.assertEqual(fo_unlock["RAId"], expected_uaid, mid)
                self.assertEqual(fo_max["RAId"], expected_uaid, mid)
                self.assertIn("10140400", fo_max["BuffList"], mid)
                self.assertIn("20190150", fo_max["BuffList"], mid)
                for req_buff in (b.strip() for b in str(p.game_data["attacks"][str(expected_uaid)].get("buffList", "")).split(",") if b.strip()):
                    self.assertTrue(supports_talent_buff(p.game_data["combat_buffs"][req_buff], p.game_data["combat_buffs"]), (mid, req_buff))

            # Verify MC 255099 gets Reborn Shield buff 20180600 and Reborn talents execute in combat
            mc_cfg = p.game_data["heroes"]["12010003"]
            fo_mc = p._hero_fight_obj(mc_cfg, lv=80, step=15, reborn_id=255099)
            self.assertIn("20180600", fo_mc["BuffList"])

            fo_midoriko = p._hero_fight_obj(p.game_data["heroes"]["12012004"], lv=80, step=15, reborn_id=16090)
            fo_midoriko.update(HP=500_000, TotalHp=500_000, RP=100, AP=50_000, DEF=10_000)
            fo_mc_sim = dict(fo_mc, HP=500_000, TotalHp=500_000, AP=10_000, DEF=10_000, RP=0)
            dummy = p._hero_fight_obj(p.game_data["heroes"]["12011005"], lv=1, step=0)
            dummy.update(HP=500_000, TotalHp=500_000, AP=20_000, DEF=0, RP=0, RAId=0, BuffList="")
            fight_payload = {
                "FightObjs": [
                    {
                        "Heros": [fo_midoriko, fo_mc_sim, {}, {}, {}, {}, dummy, {}, {}, {}, {}, {}],
                        "TeamData": [{"Fsp": 500, "Fap": 100}, {"Fsp": 500, "Fap": 10}],
                        "RandNum": 727,
                        "Pets": [],
                        "IsPVP": False,
                    }
                ]
            }
            sim_res = simulate_fight_info(fight_payload, p.game_data["attacks"], max_rounds=1, buffs_cfg=p.game_data["combat_buffs"])
            hp_by_pos = {row["PosId"]: row["HP"] for row in sim_res.verify_data["hp"][0]}
            # Midoriko's UAID (1003005, 455% factor) deals >150k damage; MC's 20180600 shield (240% DEF = 24k) absorbs dummy's hit completely
            self.assertLess(hp_by_pos[7], 350_000)
            self.assertEqual(hp_by_pos[2], 500_000)

            # Verify Team Reborn Master (RebornLvActiveModel) + HeroRebornCheer stat scaling
            team_mids = (12011002, 12011004, 12012004, 12012005, 12015022, 12015023)
            for idx, mid in enumerate(team_mids):
                h = p._build_hero_instance(mid, lv=80, step=15)
                h["RebornId"] = 16090
                h["RebornStep"] = 9
                p.state["heroes"].append(h)
                p.state["slots"][idx].update(HeroId=h["Id"], HeroModelId=mid)
            p._recalc_all_slots_and_fap()
            apr_master = int(p.state["slots"][0]["Property"]["APR1"])
            # 16090 self RebornPrtype (+3500) + RebornDashi Lv9 (+13000) + base 10000 >= 26500
            self.assertGreaterEqual(apr_master, 26500)

            # Drop one slot to RebornId=16000 -> Team Reborn Master drops from 9 -> 0 (-13000 APR)
            last_hero = next(h for h in p.state["heroes"] if h["Id"] == p.state["slots"][5]["HeroId"])
            last_hero["RebornId"] = 16000
            last_hero["RebornStep"] = 0
            p._recalc_all_slots_and_fap()
            self.assertEqual(apr_master - int(p.state["slots"][0]["Property"]["APR1"]), 13000)

            # Equip orange+ partner with RebornStep=9 -> HeroRebornCheer adds +AP2/+HP2/+DEF2
            ap_before_cheer = int(p.state["slots"][0]["Property"]["AP"])
            mate_h = p._build_hero_instance(12011003, lv=80, step=15)
            mate_h["RebornId"] = 16090
            mate_h["RebornStep"] = 9
            p.state["heroes"].append(mate_h)
            self.assertEqual(self._call(emu, "Slot", "MateinfoCombat", 1, mate_h["Id"])["Status"], 0)
            self.assertGreater(int(p.state["slots"][0]["Property"]["AP"]), ap_before_cheer)

    def test_05_bdd_floor_27_full_51_stage_route_and_uaid_combat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.state["player"].update(
                Lv=80, Vip=11, VIPLv=11, VipLv=11, IsNewPlayer=0, StarId=350,
                Diamond=1_000_000, Gold=500_000_000, Merit=0,
            )

            # 1. Catalogue exposes all 51/51 stages & Floor 27 preserves VN BddPointModel rows
            info_init = self._call(emu, "BddInfo", "Info")["Value"]
            self.assertEqual(info_init["PlayableCount"], 51)
            cfg = p.game_data["bdd"]
            for node in (2711, 2712, 2713):
                faps = []
                for mode in (1, 2, 3):
                    fight = p._bdd_encounter(node, mode, "cd270001")["FightObjs"][0]
                    point = cfg["points"][str(node * 100 + 10 + mode)]
                    faps.append(bdd_recommended_fap(point["proposeFAP"]))
                    self.assertLessEqual(abs(fight["TeamData"][1]["Fap"] - faps[-1]), 25)
                    self.assertEqual(point["nationalDrop"], f"1124,0,{10 * mode}")
                    self.assertEqual(bool(point["firstPassDrop"]), mode == 3)
                self.assertTrue(faps[0] < faps[1] < faps[2])

            # 2. Build legitimate Lv80 + Step15 + Reborn Lv9 (16099) + UAID + orange+ Reborn mates endgame team
            p.state["glory"] = {str(t): {"TypeId": t, "Lv": 100, "EXP": 0} for t in (1, 2, 3)}
            for fid in p.game_data["fashion_model"]:
                p.state["fashions"].append({"Id": f"f_{fid}", "FashionModelId": int(fid), "Step": 5, "IsDressed": int(fid) == 19010001})

            team_models = (12011002, 12011004, 12012004, 12012005, 12013005, 12015022)
            mate_models = (12011003, 12012003, 12013003, 12013004, 12015023, 12011005)
            for index, model in enumerate(team_models, 1):
                hero = p._build_hero_instance(model, lv=80, step=15)
                hero["RebornId"] = 16099
                hero["RebornStep"] = 9
                hero["RebornStepInfo"] = [{"Num": s, "Status": 1} for s in range(1, 5)]
                p.state["heroes"].append(hero)
                slot = p.state["slots"][index - 1]
                slot.update(HeroId=hero["Id"], HeroModelId=model)
                for equip_type, key in p.EQUIP_TYPE_TO_SLOT_KEY.items():
                    eq = p._build_equip_instance(equip_type * 10000 + 701)
                    eq.update(Lv=160, Step=10)
                    p.state["equips"].append(eq)
                    slot[key] = eq
                for kind, key, model_id in ((1401, "Book", 14011615), (1402, "Horse", 14021615)):
                    p._grant_resources_from_tuples([(kind, model_id, 1)], "fixture", f"tr27:{index}:{kind}")
                    tr = p.state["treasures"][-1]
                    tr.update(Lv=100, Step=10)
                    slot[key] = tr
                for gslot in range(1, 7):
                    gmod = next(int(k) for k, v in p.game_data["gem_model"].items() if v["limit"] == gslot and v["LV"] == 15)
                    p._grant_resources_from_tuples([(2000, gmod, 1)], "fixture", f"gem27:{index}:{gslot}")
                    self._call(emu, "Slot", "GemCombat", index, gslot, p.state["gems"][-1]["Id"])
            for idx, mm in enumerate(mate_models, 1):
                mh = p._build_hero_instance(mm, lv=80, step=15)
                mh["RebornId"] = 16099
                mh["RebornStep"] = 9
                p.state["heroes"].append(mh)
                self._call(emu, "Slot", "MateinfoCombat", idx, mh["Id"])
            p._recalc_all_slots_and_fap()
            p.save()

            # Confirm UAIDs are active in the team passed to combat simulator
            allies = p._bdd_allies()
            self.assertEqual([u["RAId"] for u in allies], [UAID_HERO_MODELS[m] for m in team_models])

            # 3. Clear ALL 51/51 stages (Floors 11..27), verifying 2711, 2712, 2713 each win cleanly!
            rng = random.Random(727)
            with patch("bdd_handlers.uuid", SimpleNamespace(uuid4=lambda: uuid.UUID(int=rng.getrandbits(128)))):
                for floor in range(11, 28):
                    difficulty = 3 if floor <= 23 else 1
                    for number in (11, 12, 13):
                        node = floor * 100 + number
                        res = None
                        for _ in range(3):
                            pending = self._call(emu, "BddInfo", "GetFightInfo", node, difficulty)["Value"]
                            tok = pending["FightToken"]
                            res = self._call(emu, "BddInfo", "Fight", node, difficulty, True, "", {}, tok)["Value"]
                            if res["IsSuccess"]:
                                break
                        self.assertTrue(res["IsSuccess"], (node, difficulty, res))
                    self.assertEqual(self._call(emu, "BddInfo", "RewardBox", floor, difficulty * 3)["Status"], 0)
                    if floor < 27:
                        info = self._call(emu, "BddInfo", "Info")["Value"]["Info"]
                        offers = [
                            o for o in self._call(emu, "BddInfo", "GetBuffs")["Value"]
                            if o["NeedStars"] <= info["CanUseStarCount"]
                        ]
                        def benefit(o: dict[str, Any]) -> tuple[bool, int]:
                            r = cfg["buffs"][str(o["Id"])]
                            return r["fightattrID"] in (401, 402, 410, 411), r["addValue"]
                        self.assertEqual(self._call(emu, "BddInfo", "SelectBuff", max(offers, key=benefit)["Id"])["Status"], 0)

                final_info = self._call(emu, "BddInfo", "Info")["Value"]["Info"]
                self.assertEqual(final_info["ClearedCount"], 51)
                self.assertTrue(final_info["NeedReset"])
                self.assertEqual(self._call(emu, "BddInfo", "Reset")["Status"], 0)


if __name__ == "__main__":
    unittest.main()
