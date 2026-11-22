"""Delta coverage for R7.24 (TASK-N01): Combat buffs Slice 1B + BDD floors 24-26 (48/51 stages)."""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
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
from combat_effects import BattleEffects, buff_ids, supports_talent_buff  # noqa: E402
from combat_sim import CreateRandom, simulate_fight_info  # noqa: E402
from emulator import GameEmulatorState  # noqa: E402


@lru_cache(maxsize=1)
def game():
    return GameEmulatorState(persist=False).game_data


def unit(model, hp=100_000, ap=1000, def_=0, rp=0, buffs="", na=1001015, ra=0, hit=10000, cri=0, blo=0):
    row = game()["heroes"][str(model)]
    return {
        "HeroModelId": model,
        "HP": hp,
        "TotalHp": hp,
        "OpeningHP": hp,
        "AP": ap,
        "OriginalAP": ap,
        "DEF": def_,
        "OriginalDEF": def_,
        "RP": rp,
        "NAId": row["NAID"] if na is None else na,
        "RAId": row["RAID"] if ra is None else ra,
        "BuffList": buffs,
        "HIT": hit,
        "CRI": cri,
        "BLO": blo,
        "FSP": 500,
    }


def wave(allies, enemies, seed=4, *, npc_first=False):
    h = [{} for _ in range(12)]
    for pos, u in allies.items():
        h[pos - 1] = u
    for pos, u in enemies.items():
        h[pos - 1] = u
    return {
        "Heros": h,
        "TeamData": [dict(Fsp=500, Fap=10), dict(Fsp=500, Fap=11 if npc_first else 9)],
        "RandNum": seed,
        "Pets": [],
        "IsPVP": False,
    }


class R724Slice1BAndBddTest(unittest.TestCase):
    def sim(self, allies, enemies, *, max_rounds=1, seed=4, npc_first=False):
        data = {"FightObjs": [wave(allies, enemies, seed=seed, npc_first=npc_first)]}
        res = simulate_fight_info(data, game()["attacks"], max_rounds=max_rounds, buffs_cfg=game()["combat_buffs"])
        return res, {row["PosId"]: row for row in res.verify_data["hp"][0]}

    def test_100_percent_vn_talent_and_attack_buff_coverage(self):
        gd = game()
        buffs, tals, attacks = gd["combat_buffs"], gd["talent_models"], gd["attacks"]

        tal_full = tal_total = 0
        missing_tal = []
        for hid, rows in gd["hero_talents"].items():
            for row in rows.values():
                tal_total += 1
                t = tals.get(str(row["TALModelID"]), {})
                bids = buff_ids(t.get("buffList"))
                if all(bid in buffs and supports_talent_buff(buffs[bid], buffs) for bid in bids):
                    tal_full += 1
                else:
                    missing_tal.append((hid, row["step"], bids))
        self.assertEqual((tal_full, tal_total, missing_tal), (1699, 1699, []))

        atk_ok = atk_total = 0
        missing_atk = []
        for aid, a in attacks.items():
            for bid in buff_ids(a.get("buffList")):
                atk_total += 1
                if bid in buffs and supports_talent_buff(buffs[bid], buffs):
                    atk_ok += 1
                else:
                    missing_atk.append((aid, bid))
        self.assertEqual((atk_ok, atk_total, missing_atk), (133, 133, []))

        for extra_bid in ("20180600", "20661001", "20080101", "20080151"):
            self.assertTrue(supports_talent_buff(buffs[extra_bid], buffs), extra_bid)

    def test_continuous_attack_kill_chain_double_attack_and_block_counter(self):
        # 1. Midoriko 20060000 (9002 kill-chain): 1001015 has factor=125% -> 1250 dmg; kills 7 & 8, hits 9
        midoriko = unit(12012004, hp=50_000, ap=1000, rp=0, buffs="20060000", na=1001015, ra=0)
        e1 = unit(12011005, hp=500, ap=0, na=0, ra=0)
        e2 = unit(12011005, hp=500, ap=0, na=0, ra=0)
        e3 = unit(12011005, hp=5000, ap=0, na=0, ra=0)
        _, after_chain = self.sim({1: midoriko}, {7: e1, 8: e2, 9: e3}, max_rounds=1)
        self.assertEqual((after_chain[7]["HP"], after_chain[8]["HP"], after_chain[9]["HP"]), (0, 0, 3750))
        self.assertEqual(after_chain[1]["RP"], 125)  # 3 normal hits (+75) + 2 kills (+50)

        # 2. Hoshiyomi 20040601 (9003 on crit) fires ONCE (no infinite loop when follow-up also crits via exclude_types={5})
        hoshiyomi = unit(12012005, hp=50_000, ap=1000, cri=10000, rp=0, buffs="20040601", na=1001015, ra=0)
        dummy = unit(12011005, hp=10_000, ap=0, na=0, ra=0)
        with patch.object(CreateRandom, "randrange", return_value=0):
            _, after_crit = self.sim({1: hoshiyomi}, {7: dummy}, max_rounds=1)
        self.assertEqual(after_crit[7]["HP"], 6250)  # 1875 primary crit + 1875 follow-up crit = 3750 dmg
        self.assertEqual(after_crit[1]["RP"], 50)  # both primary and follow-up NAs grant +25 RP

        # 3. Sesshomaru RA 1002016 (20530600, 9003 on RA): consumes RP -> 0, triggers 1 follow-up NA granting +25 RP
        sessh = unit(12012005, hp=50_000, ap=1000, rp=100, buffs="", na=1001015, ra=1002016)
        dummy2 = unit(12011005, hp=50_000, ap=0, na=0, ra=0)
        with patch.object(CreateRandom, "randrange", return_value=0):
            _, after_sessh = self.sim({1: sessh}, {7: dummy2}, max_rounds=1)
        self.assertLess(after_sessh[7]["HP"], 50_000)
        self.assertEqual(after_sessh[1]["RP"], 25)  # RA spent RP=0; follow-up NA granted +25 RP

        # 4. Inu no Taishou 20050600 (9005 block counter): 75% dmg counter, dont_add_rp=True, exclude_types=0..9
        # Attach 10660400 (type=2 NA c1=2 c2=5 +20% AP heal) to prove counterattack suppresses ALL type 0..9 buffs!
        tank = unit(12011002, hp=50_000, ap=1000, blo=10000, rp=0, buffs="20050600,10660400", na=1001015, ra=0)
        tank["TotalHp"] = 100_000
        attacker = unit(12011005, hp=50_000, ap=100, rp=0, na=1001015, ra=0)
        # Round 1: pos 1 hits pos 7 (blocked 125->63) -> counter deals 937 (0 RP, no +200 heal);
        # then pos 7 regular turn hits pos 1 for 1250 (+25 RP, +200 heal from regular NA).
        _, after_ctr = self.sim({7: tank}, {1: attacker}, max_rounds=1, npc_first=False)
        self.assertEqual(after_ctr[1]["HP"], 47_813)  # 50000 - 937 (counter) - 1250 (regular NA)
        self.assertEqual(after_ctr[7]["RP"], 25)  # +0 from counterattack, +25 from regular NA
        self.assertEqual(after_ctr[7]["HP"], 50_137)  # 50000 - 63 + 200 (10660400 ran once on regular NA, suppressed on counter)

    def test_sputtering_reflect_immune_thorn_loss_addition_shield_and_immune_die(self):
        # 1. InuYasha 20590600 (9004 splash): middle slot 8 takes 1250, splashes 60% (-750) to 7 and 9, NOT back-row 10
        iny = unit(12011004, hp=50_000, ap=1000, rp=0, buffs="20590600", na=1001015, ra=0)
        e7 = unit(12011005, hp=10_000, ap=0, na=0, ra=0)
        e8 = unit(12011005, hp=10_000, ap=0, na=0, ra=0)
        e9 = unit(12011005, hp=10_000, ap=0, na=0, ra=0)
        e10 = unit(12011005, hp=10_000, ap=0, na=0, ra=0)
        _, after_mid = self.sim({2: iny}, {7: e7, 8: e8, 9: e9, 10: e10}, max_rounds=1)
        self.assertEqual((after_mid[7]["HP"], after_mid[8]["HP"], after_mid[9]["HP"], after_mid[10]["HP"]),
                         (9250, 8750, 9250, 10_000))

        # Corner slot 7 only splashes 8 (not 10); single-target RA (1002033, factor=315%) never splashes
        e7b, e8b, e10b = unit(12011005, hp=10_000, ap=0, na=0, ra=0), unit(12011005, hp=10_000, ap=0, na=0, ra=0), unit(12011005, hp=10_000, ap=0, na=0, ra=0)
        _, after_corner = self.sim({1: dict(iny)}, {7: e7b, 8: e8b, 10: e10b}, max_rounds=1)
        self.assertEqual((after_corner[7]["HP"], after_corner[8]["HP"], after_corner[10]["HP"]), (8750, 9250, 10_000))

        ra_only = unit(12011004, hp=50_000, ap=1000, rp=100, buffs="20590600", na=0, ra=1002033)
        e7r, e8r = unit(12011005, hp=10_000, ap=0, na=0, ra=0), unit(12011005, hp=10_000, ap=0, na=0, ra=0)
        _, after_ra = self.sim({1: ra_only}, {7: e7r, 8: e8r}, max_rounds=1)
        self.assertEqual((after_ra[7]["HP"], after_ra[8]["HP"]), (6850, 10_000))

        # 2. Takemaru 20070600 (9006 18% reflect) & 10070000 (707 IMMUNE_THORN)
        atk = unit(12011005, hp=10_000, ap=1000, buffs="", na=1001015, ra=0)
        ref_def = unit(12013003, hp=10_000, ap=0, buffs="20070600", na=0, ra=0)
        _, after_ref = self.sim({1: atk}, {9: ref_def}, max_rounds=1)
        self.assertEqual(after_ref[1]["HP"], 9775)  # floor(-1250 * 0.18) = -225

        imm_atk = unit(12011005, hp=10_000, ap=1000, buffs="10070000", na=1001015, ra=0)
        _, after_imm = self.sim({1: imm_atk}, {9: dict(ref_def)}, max_rounds=1)
        self.assertEqual(after_imm[1]["HP"], 10_000)

        # 3. 10110600 (type=0): +6% DAMADDR (600) per 10% HP lost
        loss_u = unit(12011005, hp=6500, ap=1000, buffs="10110600")
        loss_u["TotalHp"] = 10_000
        loss_u["OpeningHP"] = 10_000
        fx_loss = BattleEffects({1: loss_u, 9: unit(12011005)}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        mods = defaultdict(Counter)
        fx_loss.apply(1, 1, None, [9], (1, 2), (1,), mods)
        self.assertEqual(mods[1]["DAMADDR"], 1800)  # floor((10000 - 6500) / 1000) * 600 = 3 * 600

        # 4. 20180600 -> 14110000 (c1=7 Shield): ceil(1000 * 2.4) = 2400 capacity; blocks damage & reflect until broken
        shield_def = unit(12013003, hp=10_000, ap=0, def_=1000, buffs="20180600,20070600", na=0, ra=0)
        shield_def["DEF"] = 1000
        shield_def["OriginalDEF"] = 1000
        # ap=2200 vs def=1000 -> hurt_strength=1200, *1.25 = 1500 dmg/hit: Hit 1 absorbed (shield 2400->900), Hit 2 loses 600 HP & -108 reflect
        atk_sh = unit(12011005, hp=10_000, ap=2200, na=1001015, ra=0)
        _, after_r1 = self.sim({1: dict(atk_sh)}, {9: dict(shield_def)}, max_rounds=1)
        self.assertEqual((after_r1[9]["HP"], after_r1[1]["HP"]), (10_000, 10_000))
        _, after_r2 = self.sim({1: dict(atk_sh)}, {9: dict(shield_def)}, max_rounds=2)
        self.assertEqual((after_r2[9]["HP"], after_r2[1]["HP"]), (9400, 9892))

        # 5. 20080101 (9007 immune fatal blow): blocks one lethal blow (0 dmg) then clears
        imm_die = unit(12011005, hp=500, ap=0, buffs="20080101", na=0, ra=0)
        slayer = unit(12011005, hp=10_000, ap=1000, na=1001015, ra=0)
        with patch.object(CreateRandom, "randrange", return_value=0):
            _, after_1 = self.sim({1: dict(slayer)}, {9: dict(imm_die)}, max_rounds=1)
            self.assertEqual(after_1[9]["HP"], 500)
            _, after_2 = self.sim({1: dict(slayer)}, {9: dict(imm_die)}, max_rounds=2)
            self.assertEqual(after_2[9]["HP"], 0)

    def test_reborn_immortal_on_death_triggers_and_boss_enrage(self):
        # 1. Inu no Taishou 10290000 Reborn: revives once at 1.5*AP, attacker still gets +25 kill RP, second lethal kills
        reborn = unit(12011002, hp=500, ap=1000, rp=0, buffs="10290000", na=0, ra=0)
        reborn["TotalHp"] = 10_000
        killer = unit(12011005, hp=10_000, ap=2000, rp=0, na=1001015, ra=0)
        _, r1 = self.sim({1: dict(killer)}, {9: dict(reborn)}, max_rounds=1)
        self.assertEqual(r1[9]["HP"], 1500)
        self.assertEqual(r1[1]["RP"], 50)  # +25 NA +25 kill even when victim revives
        _, r2 = self.sim({1: dict(killer)}, {9: dict(reborn)}, max_rounds=2)
        self.assertEqual(r2[9]["HP"], 0)

        # LOCK_HEALING (505) blocks Reborn
        fx_lock = BattleEffects({1: dict(killer), 9: dict(reborn)}, game()["attacks"], game()["combat_buffs"], CreateRandom(1))
        fx_lock._add(9, {
            "ID": 999505, "typeEnum": 2, "targetCampEnum": 3, "triggerCondition2": 1,
            "addAttrEnum": 505, "maxTime": -1, "maxNum": -1, "overlayNum": -1, "isDebuff": True,
        }, 4)
        fx_lock.units[9]["HP"] = 0
        fx_lock.apply(9, 1, 1, [1], (4, 5), (5,), defaultdict(Counter))
        self.assertEqual(fx_lock.units[9]["HP"], 0)

        # 2. Hitomiko 20470808 -> 14060000: 1-turn immortality keeps restoring 1 HP until caster's next turn ends
        # Put Hitomiko at pos 1 (acts 1st) so her RA attaches 14060000 to Ally (pos 2) BEFORE E8 (pos 8) hits pos 2!
        hito = unit(12012009, hp=10_000, ap=10, rp=100, buffs="20470808", na=1001015, ra=1002020)
        ally = unit(12011005, hp=500, ap=0, rp=0, na=0, ra=0)
        ally["TotalHp"] = 10_000
        e8 = unit(12011005, hp=50_000, ap=5000, na=1001015, ra=0)
        with patch.object(CreateRandom, "randrange", return_value=0):
            _, h_r1 = self.sim({1: dict(hito), 2: dict(ally)}, {8: dict(e8)}, max_rounds=1)
            self.assertEqual(h_r1[2]["HP"], 1)
            _, h_r2 = self.sim({1: dict(hito), 2: dict(ally)}, {8: dict(e8)}, max_rounds=2)
            self.assertEqual(h_r2[2]["HP"], 0)

        # 3. On-death triggers: 10300600 (-25 RP to enemy), 10310800 (-80% AP dmg to enemy), 10320400 (+100% AP to most-injured ally), 10330600 (+45% AP to all allies)
        martyr = unit(12011005, hp=100, ap=1000, buffs="10300600,10310800,10320400,10330600", na=0, ra=0)
        injured_ally = unit(12011005, hp=1000, ap=0, na=0, ra=0)
        injured_ally["TotalHp"] = 5000
        full_ally = unit(12011005, hp=5000, ap=0, na=0, ra=0)
        slayer_o = unit(12011005, hp=10_000, ap=1000, rp=50, na=1001015, ra=0)
        # Note: order is friend 1->7. Put enemy slayer at pos 1 vs martyr at pos 7, allies at pos 8 (injured), pos 9 (full)
        with patch.object(CreateRandom, "randrange", return_value=0):
            _, od = self.sim({1: dict(slayer_o)}, {7: dict(martyr), 8: dict(injured_ally), 9: dict(full_ally)}, max_rounds=1)
        self.assertEqual(od[7]["HP"], 0)
        self.assertEqual(od[1]["RP"], 75)  # 50 + 25 NA + 25 kill - 25 (10300600)
        self.assertEqual(od[1]["HP"], 9200)  # -80% of 1000 AP (10310800)
        self.assertEqual(od[8]["HP"], 2450)  # 1000 + 1000 (10320400) + 450 (10330600)
        self.assertEqual(od[9]["HP"], 5000)  # capped at TotalHp

        # 4. Boss enrage 10090000 (type=9 refAttr=205 >= 50 RP -> +9,999,000 DAMADD)
        foe_low_rp = unit(12011005, hp=20_000_000, ap=0, na=0, ra=0)
        boss49 = unit(12011005, hp=50_000, ap=1000, rp=49, na=1001001, ra=0)
        boss50 = unit(12011005, hp=50_000, ap=1000, rp=50, na=1001001, ra=0)
        _, res49 = self.sim({1: boss49}, {7: dict(foe_low_rp)}, max_rounds=1)
        _, res50 = self.sim({1: boss50}, {7: dict(foe_low_rp)}, max_rounds=1)
        self.assertLess(20_000_000 - res49[7]["HP"], 10_000)
        self.assertGreaterEqual(20_000_000 - res50[7]["HP"], 9_999_000)

    @patch("bdd_handlers.PLAYABLE_FLOORS", range(11, 27))
    def test_bdd_floors_24_to_26_upgrade_samples_and_full_48_stage_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu.clock.set_fixed(1795176000)
            p = emu.profiles["normal"]
            call = lambda mod, fn, *args: emu.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

            p.state["player"].update(Lv=80, Vip=11, VIPLv=11, VipLv=11, IsNewPlayer=0, StarId=350, Diamond=1_000_000, Gold=500_000_000)

            # 1. Verify upgrade from R7.18-R7.23 floor-23 terminal save offers floor 23 buff once before 2411
            keys_39 = [str(100 * f + n) for f in range(11, 24) for n in (11, 12, 13)]
            p.state["bdd"] = {
                "stars": dict.fromkeys(keys_39, 3),
                "best": dict.fromkeys(keys_39, 3),
                "max_stars": 117,
                "last_buff_floor": 22,
                "three_star_floors": list(range(11, 24)),
            }
            p.save()
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu.clock.set_fixed(1795176000)
            p = emu.profiles["normal"]

            val = call("BddInfo", "Info")["Value"]
            self.assertEqual((val["PlayableCount"], val["Info"]["ClearedCount"]), (48, 39))
            self.assertTrue(val["Info"]["NeedSelectBuff"])
            self.assertFalse(val["Info"]["NeedReset"])
            self.assertEqual(val["Info"]["BeforeFloorStarCount"], 9)
            self.assertEqual(call("BddInfo", "RewardBox", 23, 9)["Status"], -39)
            self.assertEqual(call("BddInfo", "GetFightInfo", 2411, 1)["Status"], -1716)
            offer = call("BddInfo", "GetBuffs")["Value"][0]
            self.assertEqual(call("BddInfo", "SelectBuff", offer["Id"])["Status"], 0)
            info = call("BddInfo", "Info")["Value"]["Info"]
            self.assertFalse(info["NeedSelectBuff"])
            self.assertEqual(call("BddInfo", "GetFightInfo", 2411, 1)["Status"], 0)
            self.assertEqual(call("BddInfo", "GetFightInfo", 2711, 1)["Status"], -1716)

            # 2. Verify all 27 VN difficulty rows across floors 24-26 preserve FAP & canonical pic/drops
            cfg = p.game_data["bdd"]
            rows_24_26 = [r for r in cfg["nodes"].values() if 24 <= r["floorModelID"] <= 26]
            self.assertEqual(len(rows_24_26), 9)
            for row in rows_24_26:
                node = row["ID"]
                faps = []
                for mode in (1, 2, 3):
                    fight = p._bdd_encounter(node, mode, "cd987654")["FightObjs"][0]
                    point = cfg["points"][str(node * 100 + 10 + mode)]
                    faps.append(bdd_recommended_fap(point["proposeFAP"]))
                    self.assertLessEqual(abs(fight["TeamData"][1]["Fap"] - faps[-1]), 25)
                    self.assertEqual(fight["Heros"][7]["HeroModelId"], int(row["pic"]))
                    self.assertEqual(point["nationalDrop"], f"1124,0,{10 * mode}")
                    self.assertEqual(bool(point["firstPassDrop"]), mode == 3)
                self.assertTrue(faps[0] < faps[1] < faps[2])

            # 3. Reset clean & build legitimate Lv80 endgame team, clear all 48 stages (floors 11-26) via real simulator
            p.state["bdd"] = {}
            p.state["player"]["Merit"] = 0
            p.state["glory"] = {"1": 100, "2": 100, "3": 100}
            for fid in p.game_data["fashion_model"]:
                p.state["fashions"].append({"Id": f"f_{fid}", "FashionModelId": int(fid), "Step": 5, "IsDressed": int(fid) == 19010001})
            team_models = (12011002, 12011004, 12012004, 12012005, 12013003, 12013005)
            mate_models = (12011003, 12012003, 12013004, 12015022, 12015023, 12011005)
            for index, model in enumerate(team_models, 1):
                hero = p._build_hero_instance(model, lv=80, step=15)
                p.state["heroes"].append(hero)
                slot = p.state["slots"][index - 1]
                slot.update(HeroId=hero["Id"], HeroModelId=model)
                for equip_type, key in p.EQUIP_TYPE_TO_SLOT_KEY.items():
                    eq = p._build_equip_instance(equip_type * 10000 + 701)
                    eq.update(Lv=160, Step=10)
                    p.state["equips"].append(eq)
                    slot[key] = eq
                for kind, key, model_id in ((1401, "Book", 14011615), (1402, "Horse", 14021615)):
                    p._grant_resources_from_tuples([(kind, model_id, 1)], "fixture", f"tr:{index}:{kind}")
                    tr = p.state["treasures"][-1]
                    tr.update(Lv=100, Step=10)
                    slot[key] = tr
                for gslot in range(1, 7):
                    gmod = next(int(k) for k, v in p.game_data["gem_model"].items() if v["limit"] == gslot and v["LV"] == 15)
                    p._grant_resources_from_tuples([(2000, gmod, 1)], "fixture", f"gem:{index}:{gslot}")
                    call("Slot", "GemCombat", index, gslot, p.state["gems"][-1]["Id"])
            for idx, mm in enumerate(mate_models, 1):
                mh = p._build_hero_instance(mm, lv=80, step=15)
                p.state["heroes"].append(mh)
                call("Slot", "MateinfoCombat", idx, mh["Id"])
            p._recalc_all_slots_and_fap()
            p.save()

            rng = random.Random(724)
            with patch("bdd_handlers.uuid", SimpleNamespace(uuid4=lambda: uuid.UUID(int=rng.getrandbits(128)))):
                for floor in range(11, 27):
                    difficulty = 3 if floor <= 22 else 1
                    for number in (11, 12, 13):
                        node = floor * 100 + number
                        res = None
                        for _ in range(4):
                            pending = call("BddInfo", "GetFightInfo", node, difficulty)["Value"]
                            tok = pending["FightToken"]
                            res = call("BddInfo", "Fight", node, difficulty, True, "", {}, tok)["Value"]
                            if res["IsSuccess"]:
                                break
                        self.assertTrue(res["IsSuccess"], (node, res))
                    self.assertEqual(call("BddInfo", "RewardBox", floor, difficulty * 3)["Status"], 0)
                    if floor < 26:
                        info = call("BddInfo", "Info")["Value"]["Info"]
                        offers = [o for o in call("BddInfo", "GetBuffs")["Value"] if o["NeedStars"] <= info["CanUseStarCount"]]
                        def benefit(o):
                            r = cfg["buffs"][str(o["Id"])]
                            return r["fightattrID"] in (401, 402, 410, 411), r["addValue"]
                        self.assertEqual(call("BddInfo", "SelectBuff", max(offers, key=benefit)["Id"])["Status"], 0)

                info = call("BddInfo", "Info")["Value"]["Info"]
                self.assertEqual(info["ClearedCount"], 48)
                self.assertTrue(info["NeedReset"])
                self.assertGreater(info["Feats"], 0)
                self.assertEqual(call("BddInfo", "Ranking")["Value"][0]["WeekStarCount"], info["StarCount"])
                self.assertEqual(call("BddInfo", "Reset")["Status"], 0)
                sweep = call("BddInfo", "OneKeyThreeStar")["Value"]
                self.assertEqual((sweep["SweepStarCount"], sweep["Info"]["ClearedCount"]), (9, 3))


if __name__ == "__main__":
    unittest.main()
