"""Delta coverage for R7.28 (REC-P2-02): EquipArtifact (1408, 1104 tiers) & Callequip (3802, 2 RPCs + 4416/4419)."""

from __future__ import annotations

from pathlib import Path
import random
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import EMPTY_ENTITY_ID, GameEmulatorState  # noqa: E402


class R728EquipArtifactAndCallequipTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str) -> tuple[GameEmulatorState, any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
        emu.clock.set_fixed(1795262400)
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(emu: GameEmulatorState, mod: str, fn: str, *args: object) -> dict:
        return emu.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    def test_01_vn_configs_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, p = self._new_emu(tmp)
            gd = p.game_data
            self.assertEqual(len(gd["equip_artifact"]), 1104)
            by_aid = {}
            for row in gd["equip_artifact"].values():
                by_aid[row["artifactModelID"]] = by_aid.get(row["artifactModelID"], 0) + 1
            self.assertEqual(by_aid, {1: 276, 2: 276, 3: 276, 4: 276})
            self.assertEqual(len(gd["callequip_outodds"]), 36)
            self.assertEqual({r["colorLV"] for r in gd["callequip_outodds"].values()}, {3, 4, 5})
            self.assertEqual(gd["callequip_config"]["perPrice"], 200)
            self.assertEqual(gd["callequip_config"]["tenTimesPrice"], 1800)

    def test_02_equip_artifact_resonance_stats_and_avatar_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.state["player"].update(Lv=70, Diamond=50_000, Gold=50_000_000)

            # Empty formation has 0 artifact tier
            init_0 = self._call(emu, "Player", "GetInitData", *([1] * 20))
            self.assertEqual(init_0["Avatar"]["EquipArtifactInfo"]["1"]["Id"], 0)

            p._recalc_all_slots_and_fap()
            base_prop = dict(p.state["slots"][0]["Property"])

            # Grant & equip 1 Red Weapon (13010701: itemLv=15000) + 1 Red Helmet (13020701: itemLv=15000)
            w1 = p._build_equip_instance(13010701)
            h1 = p._build_equip_instance(13020701)
            p.state["equips"].extend([w1, h1])
            r_eq = self._call(emu, "Slot", "OneKeyEquipCombat", 1, w1["Id"], h1["Id"], "", "", "", "")
            self.assertEqual(r_eq["Status"], 0)

            # EquipModel[13010701].itemLv = 15000 -> highest Lv with needEquipNum=1 & needItemLv<=15000:
            # Verify against game_data directly
            exp_w = max(
                (
                    r for r in p.game_data["equip_artifact"].values()
                    if r["artifactModelID"] == 1 and r["needEquipNum"] <= 1 and r["needItemLv"] <= 15000
                ),
                key=lambda r: (r["Lv"], r["needEquipNum"]),
            )
            exp_h = max(
                (
                    r for r in p.game_data["equip_artifact"].values()
                    if r["artifactModelID"] == 2 and r["needEquipNum"] <= 1 and r["needItemLv"] <= 15000
                ),
                key=lambda r: (r["Lv"], r["needEquipNum"]),
            )
            art_av = r_eq["Avatar"]["EquipArtifactInfo"]
            self.assertEqual(art_av["1"]["Id"], exp_w["ID"])
            self.assertEqual(art_av["1"]["Lv"], exp_w["Lv"])
            self.assertEqual(art_av["1"]["OldLv"], 0)
            self.assertEqual(art_av["2"]["Id"], exp_h["ID"])

            # Calling unrelated RPC with no artifact change omits EquipArtifactInfo from Avatar
            r_sync = self._call(emu, "Player", "SyncAvatarInfo")
            self.assertNotIn("EquipArtifactInfo", r_sync["Avatar"])

            # Deploy 2nd hero wearing 2nd Red Weapon (13010701) -> advances artifact 1 to needEquipNum=2!
            hero2 = p._build_hero_instance(12011004, lv=70, step=0)
            w2 = p._build_equip_instance(13010701)
            p.state["heroes"].append(hero2)
            p.state["equips"].append(w2)
            self._call(emu, "Slot", "HeroCombat", 2, hero2["Id"])
            r_eq2 = self._call(emu, "Slot", "OneKeyEquipCombat", 2, w2["Id"], "", "", "", "", "")
            exp_w2 = max(
                (
                    r for r in p.game_data["equip_artifact"].values()
                    if r["artifactModelID"] == 1 and r["needEquipNum"] <= 2 and r["needItemLv"] <= 15000
                ),
                key=lambda r: (r["Lv"], r["needEquipNum"]),
            )
            self.assertEqual(r_eq2["Avatar"]["EquipArtifactInfo"]["1"]["Id"], exp_w2["ID"])
            self.assertEqual(r_eq2["Avatar"]["EquipArtifactInfo"]["1"]["OldLv"], exp_w["Lv"])

            # Verify EquipStepUp pushes itemLv (15000 + 2500 = 17500) on fodder-stepped 13010701? Check real EquipStepRelation
            # Step 13010701 using spare 13010701 copy -> verify Prop & FightInfo include EquipArtifact bonuses
            fight_h0 = p._build_ally_fight_objs()[0]
            self.assertEqual(fight_h0["AP"], p.state["slots"][0]["Property"]["AP"])
            self.assertEqual(fight_h0["HP"], p.state["slots"][0]["Property"]["HP"])
            self.assertGreater(p.state["slots"][0]["Property"]["AP"], base_prop["AP"])

            # Remove Slot 2 weapon -> resets artifact 1 back cleanly to needEquipNum=1
            r_un = self._call(emu, "Slot", "OneKeyEquipCombat", 2, EMPTY_ENTITY_ID, "", "", "", "", "")
            self.assertEqual(r_un["Avatar"]["EquipArtifactInfo"]["1"]["Id"], exp_w["ID"])

    def test_03_success_target_37_to_41_and_12_wired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.state["player"].update(Lv=70, Diamond=50_000, Gold=50_000_000)
            p.state["success_target"] = {"start_ts": emu.clock.now() - 6 * 86400, "drawn": {}, "drawn_days": [], "if_draw": 0, "exchange_counts": {}}

            # Equip Gold Weapon (13010801: itemLv=75000 -> Artifact Lv 33) + Gold Helmet/Clothes/Necklace
            slot0_ids = []
            for tid_eq in (13010801, 13020801, 13030801, 13040801):
                eq = p._build_equip_instance(tid_eq)
                p.state["equips"].append(eq)
                slot0_ids.append(eq["Id"])
            self._call(emu, "Slot", "OneKeyEquipCombat", 1, *slot0_ids, "", "")

            info = self._call(emu, "SuccessTargetInfo", "GetInfo")["Value"]
            by_tid = {r["TargetId"]: r for r in info["TargetList"]}
            for tid_eq in (37, 38, 39, 40, 41):
                self.assertGreaterEqual(by_tid[tid_eq]["ReachedNum"], 33)
            self.assertTrue(by_tid[37]["Claimable"]["1"])

            # Claim SuccessTarget #37 seq=1 (Lv >= 2 achieved legitimately by real EquipArtifact!)
            claim37 = self._call(emu, "SuccessTargetInfo", "DrawReward", 37, 1)
            self.assertEqual(claim37["Status"], 0)
            self.assertGreater(len(claim37["Value"]["BaseGetGameResourceList"]), 0)

            # Pull Callequip once and confirm SuccessTarget #12 scalar updates
            self._call(emu, "Callequip", "CallEquip", 1, 3)
            scalars = p._success_target_metrics(7)[0]
            self.assertEqual(scalars[12], 1)

    def test_04_callequip_get_data_free_cd_first_orange_pity_and_10x(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.state["player"].update(Lv=30, Diamond=10_000)
            # Test baseline Callequip prices without active 4416 discount (covered in test_05)
            p.event_runtime.configure_archive_mode("scheduled", scheduled_windows={})

            gd_resp = self._call(emu, "Callequip", "GetCallEquipData")
            self.assertEqual(gd_resp["Status"], 0)
            ce0 = gd_resp["Value"]
            self.assertEqual((ce0["IsFrist"], ce0["CallCount"], ce0["ColorLv"]), (1, 9, 4))
            self.assertEqual(ce0["LastFreeCallTime"], emu.clock.now() + 90 * 60)

            # Early free pull before 90m CD rejected
            self.assertEqual(self._call(emu, "Callequip", "CallEquip", 1, 1)["Status"], -1)

            # Advance clock 90 minutes -> free 1x succeeds without Diamond spend
            emu.clock.set_fixed(emu.clock.now() + 90 * 60)
            dia_before = p.state["player"]["Diamond"]
            free_resp = self._call(emu, "Callequip", "CallEquip", 1, 1)
            self.assertEqual(free_resp["Status"], 0)
            self.assertEqual(p.state["player"]["Diamond"], dia_before)
            self.assertEqual(free_resp["Value"]["CallEquipInfo"]["IsFrist"], 1)  # Only Diamond pull consumes IsFrist
            self.assertEqual(free_resp["Value"]["CallEquipInfo"]["LastFreeCallTime"], emu.clock.now() + 4260 * 60)

            # First Diamond 1x guarantees Orange (colorLV == 5) & clears IsFrist=0
            r_first = self._call(emu, "Callequip", "CallEquip", 1, 3)
            self.assertEqual(r_first["Status"], 0)
            self.assertEqual(p.state["player"]["Diamond"], dia_before - 200)
            self.assertEqual(r_first["Value"]["CallEquipInfo"]["IsFrist"], 0)
            first_eq_mid = str(r_first["Value"]["BaseGetGameResourceList"][0]["Equip"][0]["EquipModelId"])
            self.assertEqual(p.game_data["equips"][first_eq_mid]["colorLV"], 5)

            # Reset CallCount=0 to verify pity hit toggles ColorLv 4 -> 5
            p.state["callequip"]["call_count"] = 0
            p.state["callequip"]["color_lv"] = 4
            r_pity = self._call(emu, "Callequip", "CallEquip", 1, 3)
            self.assertEqual(r_pity["Status"], 0)
            pity_mid = str(r_pity["Value"]["BaseGetGameResourceList"][0]["Equip"][0]["EquipModelId"])
            self.assertGreaterEqual(p.game_data["equips"][pity_mid]["colorLV"], 4)
            self.assertEqual(r_pity["Value"]["CallEquipInfo"]["ColorLv"], 5)
            self.assertEqual(r_pity["Value"]["CallEquipInfo"]["CallCount"], 9)

            # 10x Diamond pull grants 10 equips and spends 1800 Diamond (4416 inactive)
            dia_pre10 = p.state["player"]["Diamond"]
            r_10 = self._call(emu, "Callequip", "CallEquip", 10, 3)
            self.assertEqual(r_10["Status"], 0)
            self.assertEqual(dia_pre10 - p.state["player"]["Diamond"], 1800)
            self.assertEqual(len(r_10["Value"]["BaseGetGameResourceList"][0]["Equip"]), 10)

            # Low Diamond -> -1105
            p.state["player"]["Diamond"] = 10
            self.assertEqual(self._call(emu, "Callequip", "CallEquip", 10, 3)["Status"], -1105)

    def test_05_callequip_welfare_4416_discount_and_4419_crit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.state["player"].update(Lv=30, Diamond=10_000)

            # Default concurrent archive already enables 4416 (80% price): 200->160, 1800->1440
            dia0 = p.state["player"]["Diamond"]
            r1 = self._call(emu, "Callequip", "CallEquip", 1, 3)
            self.assertEqual(r1["Status"], 0)
            self.assertEqual(dia0 - p.state["player"]["Diamond"], 160)

            dia1 = p.state["player"]["Diamond"]
            r10 = self._call(emu, "Callequip", "CallEquip", 10, 3)
            self.assertEqual(r10["Status"], 0)
            self.assertEqual(dia1 - p.state["player"]["Diamond"], 1440)
            self.assertEqual(len(r10["Value"]["BaseGetGameResourceList"][0]["Equip"]), 10)

            # Enable 4419 (eTimedWelfareEquipCallCrid) -> doubles equip drops!
            p.event_runtime.activate_manual_event("timed_welfare_equip_crit", duration_sec=3600)
            r_crit = self._call(emu, "Callequip", "CallEquip", 10, 3)
            self.assertEqual(r_crit["Status"], 0)
            self.assertEqual(len(r_crit["Value"]["BaseGetGameResourceList"][0]["Equip"]), 20)


if __name__ == "__main__":
    unittest.main()
