"""Regression and integration tests for R7.22D (TASK-M04):
1. Slot.GemCombat (socket, swap, cross-slot transfer, unequip, validation)
2. Slot.GemOneKeyCombat (highest unbattle per limit, PlayerLvRelation.gemSlotMax gating)
3. Gem.GemCompose Mode B (bag compose + syntheticDoubleUse) and error handling
4. Gem.GemCompose Mode A (GemLevelUpLayer in-place upgrade of socketed gem)
5. Gem.GemOneKeyCompose (batch unbattle compose, excludes socketed gems/double stones) & reload persistence
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import emulator  # noqa: E402


class TestR722DGems(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.now = 1795262400
        self.reload()

    def reload(self):
        self.emu = emulator.GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(self.now)
        self.store = self.emu.profiles["normal"]

    def _rpc(self, module: str, method: str, data=None):
        return self.emu.handle_rpc(
            {"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(data or [])}
        )

    def _grant_gem(self, model_id: int, count: int = 1, source: str = "test_gem") -> list[dict]:
        res = self.store._grant_resources_from_tuples(
            [(2000, model_id, count)],
            source=source,
            tx_prefix=f"test:{model_id}:{len(self.store.state['gems'])}:{count}",
        )
        return res[0]["Gem"]

    def _grant_goods(self, model_id: int, count: int = 1) -> None:
        self.store._grant_resources_from_tuples(
            [(1605, model_id, count)],
            source="test_goods",
            tx_prefix=f"test_goods:{model_id}:{len(self.store.state['goods'])}:{count}",
        )

    def _set_player_lv(self, lv: int) -> None:
        self.store.state["player"]["Lv"] = lv
        self.store.state["heroes"][0]["Lv"] = lv
        self.store._recalc_all_slots_and_fap()

    def _deploy_second_hero(self, hero_model_id: int = 12011004) -> str:
        res = self.store._grant_resources_from_tuples(
            [(1201, hero_model_id, 1)],
            source="test_hero",
            tx_prefix=f"test_hero:{len(self.store.state['heroes'])}",
        )
        hid = res[0]["Hero"][0]["Id"]
        r = self._rpc("Slot", "HeroCombat", [2, hid])
        self.assertEqual(r["Status"], 0)
        return hid

    def test_gem_combat_socket_transfer_unequip_and_validation(self):
        self._set_player_lv(2)
        base_prop = dict(self.store.state["slots"][0]["Property"])

        gem_14 = self._grant_gem(20001014)[0]  # limit=1, attrStr="431|11000,303|4000,408|9000"
        gem_t2 = self._grant_gem(20002001)[0]  # limit=2
        gem_t3 = self._grant_gem(20003001)[0]  # limit=3

        # Wrong limit rejected without mutating slots
        r_wrong = self._rpc("Slot", "GemCombat", [1, 1, gem_t2["Id"]])
        self.assertEqual(r_wrong["Status"], -48)

        # Locked gem slot (Lv2 -> gemSlotMax=2, index 3 locked)
        r_locked = self._rpc("Slot", "GemCombat", [1, 3, gem_t3["Id"]])
        self.assertEqual(r_locked["Status"], -1127)

        # Raise to Lv6 and socket Lv14 Type-1 gem on slot 1 index 1
        self._set_player_lv(6)
        base_lv6 = dict(self.store.state["slots"][0]["Property"])
        r_ok = self._rpc("Slot", "GemCombat", [1, 1, gem_14["Id"]])
        self.assertEqual(r_ok["Status"], 0)
        slot1 = self.store.state["slots"][0]
        self.assertEqual(len(slot1["Gem"]), 6)
        self.assertEqual(slot1["Gem"][0], {"Id": gem_14["Id"], "ModelId": 20001014})
        self.assertEqual(slot1["Gem"][1:], [{}, {}, {}, {}, {}])
        self.assertIn("SlotInfo", r_ok["Avatar"])

        prop1 = slot1["Property"]
        self.assertEqual(prop1["AP"] - base_lv6["AP"], 11000)
        self.assertEqual(prop1["CRI"] - base_lv6["CRI"], 4000)
        self.assertEqual(prop1["DAMADD"] - base_lv6["DAMADD"], 9000)
        self.assertEqual(prop1["FAP"] - base_lv6["FAP"], 110000)

        # Verify FightInfo receives exact gem deltas in battle
        fi_resp = self._rpc("Battle", "GetFightInfo", [11, 1111, 1])
        self.assertEqual(fi_resp["Status"], 0)
        heros = fi_resp["Value"]["FightInfo"]["FightObjs"][0]["Heros"]
        fighter = heros[0]
        self.assertEqual(fighter["HeroModelId"], slot1["HeroModelId"])
        self.assertEqual(fighter["AP"], prop1["AP"])
        self.assertEqual(fighter["CRI"], prop1["CRI"])
        self.assertEqual(fighter["DAMADD"], prop1["DAMADD"])

        # Deploy slot 2 and transfer gem_14 from slot 1 to slot 2 (per GemSelectLayer.lua)
        self._deploy_second_hero()
        base_slot2 = dict(self.store.state["slots"][1]["Property"])
        r_xfer = self._rpc("Slot", "GemCombat", [2, 1, gem_14["Id"]])
        self.assertEqual(r_xfer["Status"], 0)
        self.assertEqual(self.store.state["slots"][0]["Gem"][0], {})
        self.assertEqual(self.store.state["slots"][1]["Gem"][0], {"Id": gem_14["Id"], "ModelId": 20001014})
        self.assertEqual(self.store.state["slots"][0]["Property"]["AP"], base_lv6["AP"])
        self.assertEqual(self.store.state["slots"][1]["Property"]["AP"] - base_slot2["AP"], 11000)

        # Unequip with "" then verify EMPTY_ENTITY_ID works as well
        r_un1 = self._rpc("Slot", "GemCombat", [2, 1, ""])
        self.assertEqual(r_un1["Status"], 0)
        self.assertEqual(self.store.state["slots"][1]["Gem"][0], {})
        self.assertEqual(self.store.state["slots"][1]["Property"]["AP"], base_slot2["AP"])

        self._rpc("Slot", "GemCombat", [1, 2, gem_t2["Id"]])
        self.assertEqual(self.store.state["slots"][0]["Gem"][1]["Id"], gem_t2["Id"])
        r_un2 = self._rpc("Slot", "GemCombat", [1, 2, emulator.EMPTY_ENTITY_ID])
        self.assertEqual(r_un2["Status"], 0)
        self.assertEqual(self.store.state["slots"][0]["Gem"][1], {})
        self.assertEqual(self.store.state["slots"][0]["Property"]["FAP"], base_lv6["FAP"])
        self.assertGreaterEqual(base_lv6["HP"], base_prop["HP"])

    def test_gem_one_key_combat_prefers_highest_unbattle_and_respects_open_lv(self):
        self._deploy_second_hero()
        self._set_player_lv(6)
        # Put a Lv5 type-1 gem on slot 2 so OneKey on slot 1 must not steal it
        s2_t1_lv5 = self._grant_gem(20001005)[0]
        self.assertEqual(self._rpc("Slot", "GemCombat", [2, 1, s2_t1_lv5["Id"]])["Status"], 0)

        # Unbattle gems across limits 1..6 with mixed levels
        g1_lv1 = self._grant_gem(20001001)[0]
        g1_lv3 = self._grant_gem(20001003)[0]
        g2_lv4 = self._grant_gem(20002004)[0]
        g3_lv2 = self._grant_gem(20003002)[0]
        g4_lv5 = self._grant_gem(20004005)[0]
        g5_lv2 = self._grant_gem(20005002)[0]
        g6_lv3 = self._grant_gem(20006003)[0]

        # Drop Lv to 3 -> only sockets 1..3 open
        self._set_player_lv(3)
        r1 = self._rpc("Slot", "GemOneKeyCombat", [1])
        self.assertEqual(r1["Status"], 0)
        s1_gems = self.store.state["slots"][0]["Gem"]
        self.assertEqual(s1_gems[0]["Id"], g1_lv3["Id"])
        self.assertEqual(s1_gems[1]["Id"], g2_lv4["Id"])
        self.assertEqual(s1_gems[2]["Id"], g3_lv2["Id"])
        self.assertEqual(s1_gems[3:], [{}, {}, {}])
        self.assertEqual(self.store.state["slots"][1]["Gem"][0]["Id"], s2_t1_lv5["Id"])

        # Add a strictly higher unbattle type-1 Lv4 gem + raise Lv to 6 -> fills 4..6 & upgrades socket 1
        g1_lv4 = self._grant_gem(20001004)[0]
        self._set_player_lv(6)
        r2 = self._rpc("Slot", "GemOneKeyCombat", [1])
        self.assertEqual(r2["Status"], 0)
        s1_gems = self.store.state["slots"][0]["Gem"]
        self.assertEqual(s1_gems[0]["Id"], g1_lv4["Id"])
        self.assertEqual(s1_gems[3]["Id"], g4_lv5["Id"])
        self.assertEqual(s1_gems[4]["Id"], g5_lv2["Id"])
        self.assertEqual(s1_gems[5]["Id"], g6_lv3["Id"])
        self.assertIn(g1_lv3["Id"], {g["Id"] for g in self.store.state["gems"]})
        self.assertIn(g1_lv1["Id"], {g["Id"] for g in self.store.state["gems"]})

    def test_gem_compose_bag_and_double_compose_and_errors(self):
        self.store.state["player"]["Gold"] = 50000
        g_list = self._grant_gem(20001001, count=4)
        g_ids = [g["Id"] for g in g_list]

        # Normal bag compose (4 Lv1 -> 1 Lv2, costs 1000 Gold)
        gold_before = self.store.state["player"]["Gold"]
        r = self._rpc("Gem", "GemCompose", [g_ids])
        self.assertEqual(r["Status"], 0)
        self.assertEqual(self.store.state["player"]["Gold"], gold_before - 1000)
        self.assertEqual(set(r["Value"]["ConsumeList"]), set(g_ids))
        created = r["Value"]["BaseGetGameResourceList"][0]["Gem"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["ModelId"], 20001002)
        self.store.validate_base_resource_list(r["Value"]["BaseGetGameResourceList"])
        owned_ids = {g["Id"] for g in self.store.state["gems"]}
        self.assertEqual(len(owned_ids), 1)
        self.assertIn(created[0]["Id"], owned_ids)

        # Bag compose with 16050041 (Đá Song Sinh Lv2) -> consumes 1 stone and produces 2 Lv2 gems
        self._grant_goods(16050041, 1)
        g_list2 = self._grant_gem(20001001, count=4)
        r_dbl = self._rpc("Gem", "GemCompose", [[g["Id"] for g in g_list2]])
        self.assertEqual(r_dbl["Status"], 0)
        created2 = r_dbl["Value"]["BaseGetGameResourceList"][0]["Gem"]
        self.assertEqual(len(created2), 2)
        self.assertEqual([c["ModelId"] for c in created2], [20001002, 20001002])
        self.assertEqual(r_dbl["Avatar"]["GoodsInfo"]["16050041"], [])
        self.assertEqual(sum(1 for g in self.store.state["gems"] if g["ModelId"] == 20001002), 3)

        # Validation error cases
        # Duplicate IDs -> -1320
        g_extra = self._grant_gem(20001001, count=3)
        self.assertEqual(self._rpc("Gem", "GemCompose", [[g_extra[0]["Id"]] * 4])["Status"], -1320)
        # Mismatched ModelId -> -1325
        g_other = self._grant_gem(20002001, count=1)[0]
        self.assertEqual(
            self._rpc("Gem", "GemCompose", [[g_extra[0]["Id"], g_extra[1]["Id"], g_extra[2]["Id"], g_other["Id"]]])["Status"],
            -1325,
        )
        # Max Lv 15 -> -1321
        g_max = self._grant_gem(20001015, count=4)
        self.assertEqual(self._rpc("Gem", "GemCompose", [[g["Id"] for g in g_max]])["Status"], -1321)
        # Insufficient Gold -> -1118
        g_more = self._grant_gem(20001001, count=1)[0]
        self.store.state["player"]["Gold"] = 500
        self.assertEqual(
            self._rpc("Gem", "GemCompose", [[g_extra[0]["Id"], g_extra[1]["Id"], g_extra[2]["Id"], g_more["Id"]]])["Status"],
            -1118,
        )
        # >1 socketed gem in compose batch -> -1304
        self._set_player_lv(6)
        self._deploy_second_hero()
        self.store.state["player"]["Gold"] = 50000
        lv2_gems = [g for g in self.store.state["gems"] if g["ModelId"] == 20001002]
        lv2_more = self._grant_gem(20001002, count=1)[0]
        self.assertEqual(self._rpc("Slot", "GemCombat", [1, 1, lv2_gems[0]["Id"]])["Status"], 0)
        self.assertEqual(self._rpc("Slot", "GemCombat", [2, 1, lv2_gems[1]["Id"]])["Status"], 0)
        self.assertEqual(
            self._rpc("Gem", "GemCompose", [[lv2_gems[0]["Id"], lv2_gems[1]["Id"], lv2_gems[2]["Id"], lv2_more["Id"]]])["Status"],
            -1304,
        )

    def test_gem_compose_in_place_socketed_upgrade(self):
        self._set_player_lv(6)
        self.store.state["player"]["Gold"] = 50000
        gems = self._grant_gem(20001001, count=4)
        socketed_id = gems[0]["Id"]
        mat_ids = [gems[1]["Id"], gems[2]["Id"], gems[3]["Id"]]

        self.assertEqual(self._rpc("Slot", "GemCombat", [1, 1, socketed_id])["Status"], 0)
        ap_before = self.store.state["slots"][0]["Property"]["AP"]
        fap_before = self.store.state["slots"][0]["Property"]["FAP"]

        # Exact GemLevelUpLayer.lua:266 payload {mat1, mat2, mat3, socketed_id}
        r = self._rpc("Gem", "GemCompose", [mat_ids + [socketed_id]])
        self.assertEqual(r["Status"], 0)
        self.assertEqual(self.store.state["player"]["Gold"], 49000)
        self.assertEqual(r["Value"]["Gem"]["Id"], socketed_id)
        self.assertEqual(r["Value"]["Gem"]["ModelId"], 20001002)
        self.assertNotIn("BaseGetGameResourceList", r["Value"])
        self.assertIn("SlotInfo", r["Avatar"])

        self.assertEqual(self.store.state["slots"][0]["Gem"][0], {"Id": socketed_id, "ModelId": 20001002})
        # 20001001 (431|60) -> 20001002 (431|90): +30 AP, +300 FAP
        self.assertEqual(self.store.state["slots"][0]["Property"]["AP"] - ap_before, 30)
        self.assertEqual(self.store.state["slots"][0]["Property"]["FAP"] - fap_before, 300)
        self.assertEqual([g["Id"] for g in self.store.state["gems"]], [socketed_id])

    def test_gem_one_key_compose_red_dot_and_persistence(self):
        self._set_player_lv(40)
        self.store.state["player"]["Gold"] = 50000
        # 1 socketed Lv1 type-1 + 9 unbattle Lv1 type-1 + 4 unbattle Lv1 type-2 + 1 double stone
        t1 = self._grant_gem(20001001, count=10)
        self._grant_gem(20002001, count=4)
        self._grant_goods(16050041, 1)
        self.assertEqual(self._rpc("Slot", "GemCombat", [1, 1, t1[0]["Id"]])["Status"], 0)

        # RedDot 1413 (eGemCompose) active before compose
        self.assertEqual(self.store._compute_red_dot_info()["1413"], 1)

        r = self._rpc("Gem", "GemOneKeyCompose", [])
        self.assertEqual(r["Status"], 0)
        # 2 batches of type-1 (8 gems) + 1 batch of type-2 (4 gems) = 12 consumed, 3 Lv2 created, 3000 Gold spent
        self.assertEqual(len(r["Value"]["ConsumeList"]), 12)
        created = r["Value"]["BaseGetGameResourceList"][0]["Gem"]
        self.assertEqual(len(created), 3)
        self.assertEqual(self.store.state["player"]["Gold"], 47000)
        # Socketed gem and double stone untouched
        self.assertEqual(self.store.state["slots"][0]["Gem"][0]["Id"], t1[0]["Id"])
        dbl_goods = [g for g in self.store.state["goods"] if g["GoodsModelId"] == 16050041]
        self.assertEqual(dbl_goods[0]["Num"], 1)
        self.assertEqual(self.store._compute_red_dot_info()["1413"], 0)

        # Save / reload persistence check + InitData GemInfo check
        saved_fap = self.store.state["slots"][0]["Property"]["FAP"]
        self.reload()
        self.assertEqual(len(self.store.state["slots"][0]["Gem"]), 6)
        self.assertEqual(self.store.state["slots"][0]["Gem"][0], {"Id": t1[0]["Id"], "ModelId": 20001001})
        self.assertEqual(self.store.state["slots"][0]["Property"]["FAP"], saved_fap)
        init_resp = self._rpc("Player", "GetInitData", [])
        self.assertEqual(len(init_resp["Value"]["GemInfo"]), len(self.store.state["gems"]))
        self.assertEqual(len(init_resp["Value"]["SlotInfo"][0]["Gem"]), 6)


if __name__ == "__main__":
    unittest.main()
