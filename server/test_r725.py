#!/usr/bin/env python3
"""Tests for TASK-M06 (R7.25): LeaderBoard, GoodsSell, AlterPlayerName/HeadId, TreasureCompose."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from emulator import EventClock, GAME_DATA_PATH, GameEmulatorState, ProfileStore, ResourceLedger


class R725GameplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.game_data = json.loads(GAME_DATA_PATH.read_text(encoding="utf-8"))

    def _new_store(self, tmpdir: str, name: str = "normal") -> ProfileStore:

        state_path = Path(tmpdir) / f"{name}_profile.json"
        audit_path = Path(tmpdir) / "audit_ledger.jsonl"
        ledger = ResourceLedger(audit_log_path=audit_path, vip_model=self.game_data.get("vip_model", {}))
        clock = EventClock()
        store = ProfileStore(
            name,
            self.game_data,
            ledger,
            state_path=state_path,
            persist=True,
            reset=True,
            clock=clock,
        )
        r = store.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["Tester", 0]})
        self.assertEqual(r["Status"], 0)
        return store

    def test_01_extracted_configs_present(self) -> None:
        """LeaderboardConfig, TreasureColorModel, and GoodsDjqModel must be extracted accurately from VN Lua."""
        lb_cfg = self.game_data.get("leaderboard_config", {})
        self.assertEqual(lb_cfg.get("likeReward"), "1112,0,10000")
        self.assertEqual(int(lb_cfg.get("rankNum", 0)), 50)
        self.assertEqual(int(lb_cfg.get("upNum", 0)), 10)

        tc_cfg = self.game_data.get("treasure_color", {})
        self.assertEqual(int(tc_cfg.get("needPurple", 0)), 5)
        self.assertEqual(int(tc_cfg.get("needGold", 0)), 100000)
        self.assertEqual(tc_cfg.get("outFinally"), "1605,16050020,1")

        djq = self.game_data.get("goods_djq_model", {})
        self.assertEqual(len(djq), 168)
        self.assertEqual(int(djq["16111001"]["sellTypeID"]), 1112)
        self.assertEqual(int(djq["16111001"]["sellNum"]), 5000)

    def test_02_leaderboard_rank_praise_formation_and_s1_peers(self) -> None:
        """LeaderBoard.RankList, Praise, and Formation must handle all 3 tabs, S1 peers, and daily reset."""
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, data_dir=Path(td))
            emu.ensure_s1_account_slots(2)
            acct1 = emu.s1_accounts["acct_1"]
            acct2 = emu.s1_accounts["acct_2"]
            acct1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["PlayerOne", 0]})
            acct2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["PeerTwo", 1]})
            acct1.admin_prepare_account(target_lv=25, vip_lv=2, source="test_lb")
            acct2.admin_prepare_account(target_lv=79, vip_lv=6, source="test_lb")
            granted = acct2._grant_resources_from_tuples(
                [(1201, 12011004, 1), (1201, 12012005, 1), (1117, 0, 5000000), (1112, 0, 5000000)],
                source="test_lb",
                tx_prefix="test_lb",
            )
            for idx, h in enumerate(granted[0]["Hero"], start=2):
                acct2.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
                acct2.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [h["Id"], 79]})
            acct2.save()

            acct2_pid = str(acct2.state["player"]["PlayerId"])
            acct2_fap = int(acct2.state["player"]["FAP"])

            # 1. All 3 supported tabs (1=FAP, 2=Lv, 4=Generals)
            for rtype in (1, 2, 4):
                res = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "RankList", "Data": [rtype]})
                self.assertEqual(res["Status"], 0)
                val = res["Value"]
                self.assertFalse(val["IsPraise"])
                entries = val["RankList"]
                self.assertEqual(len(entries), 50)
                for idx, e in enumerate(entries, start=1):
                    self.assertEqual(e["Rank"], idx)
                    self.assertIn(str(e["HeadImageId"]), self.game_data["heroes"])
                    self.assertIsInstance(e["GuildName"], str)
                    self.assertIsInstance(e["ServerName"], str)
                    self.assertTrue(len(e["ServerName"]) > 0)
                    self.assertNotIn("_source", e)
                if rtype == 2:
                    self.assertTrue(all(entries[i]["Lv"] >= entries[i + 1]["Lv"] for i in range(len(entries) - 1)))
                else:
                    self.assertTrue(all(entries[i]["FAP"] >= entries[i + 1]["FAP"] for i in range(len(entries) - 1)))

            # Verify Lv=79 peer appears near top of Lv leaderboard and Formation resolves cleanly
            lv_entries = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "RankList", "Data": [2]})["Value"]["RankList"]
            peer_entry = next((e for e in lv_entries if e["Id"] == acct2_pid), None)
            self.assertIsNotNone(peer_entry)
            self.assertEqual(peer_entry["Name"], "PeerTwo")
            self.assertEqual(peer_entry["Lv"], 79)

            fmt_peer = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "Formation", "Data": [2, peer_entry["Rank"]]})
            self.assertEqual(fmt_peer["Status"], 0)
            self.assertEqual(fmt_peer["Value"]["Formation"]["PlayerInfo"]["PlayerId"], acct2_pid)
            self.assertEqual(fmt_peer["Value"]["Formation"]["PlayerInfo"]["FAP"], acct2_fap)
            self.assertEqual(len(fmt_peer["Value"]["Formation"]["SlotInfos"]), 6)

            # Bot formation inspection (rank 1 on FAP tab or first bot rank)
            fap_entries = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "RankList", "Data": [1]})["Value"]["RankList"]
            bot_rank = next(e["Rank"] for e in fap_entries if e["Id"] not in {acct2_pid, str(acct1.state["player"]["PlayerId"])})
            fmt_bot = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "Formation", "Data": [1, bot_rank]})
            self.assertEqual(fmt_bot["Status"], 0)
            self.assertIn("PlayerInfo", fmt_bot["Value"]["Formation"])
            self.assertEqual(len(fmt_bot["Value"]["Formation"]["SlotInfos"]), 6)

            # 2. Praise peer on Lv tab -> +10000 Gold, PraiseNum +1 visible to both accounts
            gold_before = int(acct1.state["player"]["Gold"])
            praise_res = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "Praise", "Data": [2, peer_entry["Rank"]]})
            self.assertEqual(praise_res["Status"], 0)
            self.assertEqual(int(acct1.state["player"]["Gold"]), gold_before + 10000)
            self.assertTrue(len(praise_res["Value"]["BaseGetGameResourceList"]) > 0)

            lv_after = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "RankList", "Data": [2]})["Value"]
            self.assertTrue(lv_after["IsPraise"])
            self.assertEqual(lv_after["RankList"][peer_entry["Rank"] - 1]["PraiseNum"], 1)

            # Duplicate praise on same tab same day must fail cleanly without granting Gold
            dup = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "Praise", "Data": [2, peer_entry["Rank"]]})
            self.assertNotEqual(dup["Status"], 0)
            self.assertEqual(int(acct1.state["player"]["Gold"]), gold_before + 10000)

            # Different tab (FAP) is still praisable same day
            praise_fap = acct1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "Praise", "Data": [1, 1]})
            self.assertEqual(praise_fap["Status"], 0)
            self.assertEqual(int(acct1.state["player"]["Gold"]), gold_before + 20000)

            # Persistence across reload & rollover next virtual day
            emu2 = GameEmulatorState(persist=True, data_dir=Path(td))
            reloaded1 = emu2.s1_accounts["acct_1"]
            lv_rel = reloaded1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "RankList", "Data": [2]})["Value"]
            self.assertTrue(lv_rel["IsPraise"])
            self.assertEqual(lv_rel["RankList"][peer_entry["Rank"] - 1]["PraiseNum"], 1)

            emu2.clock.mode = "offset"
            emu2.clock.offset_sec += 86400
            lv_next = reloaded1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "RankList", "Data": [2]})["Value"]
            self.assertFalse(lv_next["IsPraise"])
            self.assertEqual(lv_next["RankList"][peer_entry["Rank"] - 1]["PraiseNum"], 1)

            # Error handling on invalid tab / rank
            self.assertNotEqual(reloaded1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "RankList", "Data": [3]})["Status"], 0)
            self.assertNotEqual(reloaded1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "Praise", "Data": [1, 999]})["Status"], 0)
            self.assertNotEqual(reloaded1.handle_rpc({"ModuleName": "LeaderBoard", "MethodName": "Formation", "Data": [4, 0]})["Status"], 0)

    def test_03_goods_sell_regular_voucher_and_errors(self) -> None:
        """Goods.GoodsSell must sell GoodsModel & GoodsDjqModel items, reject unsellable/invalid, and persist."""
        with tempfile.TemporaryDirectory() as td:
            store = self._new_store(td)
            store._grant_resources_from_tuples(
                [
                    (1605, 16050001, 10),   # Break Stone: sellType 1112, sellNum 100
                    (1611, 16111001, 1),    # Voucher 18k: sellType 1112, sellNum 5000 (GoodsDjqModel)
                    (1605, 16050020, 2),    # Essence Stone: sellNum 0 (not sellable)
                    (1614, 16140112, 1),    # Disabled Pet coin sellType 2404
                ],
                source="test_sell_setup",
                tx_prefix="test_sell_setup",
            )
            store.save()

            def find_good(mid: int) -> dict:
                return next(g for g in store.state["goods"] if int(g["GoodsModelId"]) == mid)

            stone = find_good(16050001)
            stone_before = int(stone["Num"])
            voucher = find_good(16111001)
            essence = find_good(16050020)
            pet_item = find_good(16140112)
            gold_before = int(store.state["player"]["Gold"])

            # Sell 5x 16050001 -> +500 Gold
            res1 = store.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsSell", "Data": [stone["Id"], 16050001, 5]})
            self.assertEqual(res1["Status"], 0)
            self.assertEqual(int(store.state["player"]["Gold"]), gold_before + 500)
            self.assertEqual(int(find_good(16050001)["Num"]), stone_before - 5)
            self.assertIn("16050001", res1["Avatar"]["GoodsInfo"])
            self.assertTrue(len(res1["Value"]["BaseGetGameResourceList"]) > 0)

            # Sell full stack 1x 16111001 voucher -> +5000 Gold, stack removed
            res2 = store.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsSell", "Data": [voucher["Id"], 16111001, 1]})
            self.assertEqual(res2["Status"], 0)
            self.assertEqual(int(store.state["player"]["Gold"]), gold_before + 5500)
            self.assertIsNone(next((g for g in store.state["goods"] if int(g["GoodsModelId"]) == 16111001), None))

            # Reject unsellable (sellNum=0), insufficient count, zero count, disabled currency 2404
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsSell", "Data": [essence["Id"], 16050020, 1]})["Status"], 0)
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsSell", "Data": [stone["Id"], 16050001, stone_before]})["Status"], 0)
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsSell", "Data": [stone["Id"], 16050001, 0]})["Status"], 0)
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Goods", "MethodName": "GoodsSell", "Data": [pet_item["Id"], 16140112, 1]})["Status"], 0)
            self.assertEqual(int(store.state["player"]["Gold"]), gold_before + 5500)

            # Reload check
            reloaded = ProfileStore(
                "normal",
                self.game_data,
                ResourceLedger(audit_log_path=Path(td) / "audit_ledger.jsonl", vip_model=self.game_data.get("vip_model", {})),
                state_path=Path(td) / "normal_profile.json",
                persist=True,
                clock=EventClock(),
            )
            self.assertEqual(int(reloaded.state["player"]["Gold"]), gold_before + 5500)
            self.assertEqual(int(next(g for g in reloaded.state["goods"] if int(g["GoodsModelId"]) == 16050001)["Num"]), stone_before - 5)

    def test_04_alter_player_head_id_and_name(self) -> None:
        """Player.AlterPlayerHeadId and AlterPlayerName must validate ownership, costs, and persistence."""
        with tempfile.TemporaryDirectory() as td:
            store = self._new_store(td)
            store._grant_resources_from_tuples(
                [(1201, 12011004, 1), (1605, 16050002, 1), (1111, 0, 150)],
                source="test_profile_alter",
                tx_prefix="test_profile_alter",
            )
            store.save()

            # AlterPlayerHeadId: reject unowned hero (12012005) and bad ID
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerHeadId", "Data": [12012005]})["Status"], 0)
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerHeadId", "Data": [99999999]})["Status"], 0)

            # Succeed for owned 12011004
            hres = store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerHeadId", "Data": [12011004]})
            self.assertEqual(hres["Status"], 0)
            self.assertEqual(int(store.state["player"]["HeadImageId"]), 12011004)
            self.assertEqual(int(hres["Avatar"]["HeadImageId"]), 12011004)

            # AlterPlayerName invalid names rejected without consuming card
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["A", 2]})["Status"], 0)
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["", 2]})["Status"], 0)
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["Tester", 2]})["Status"], 0)
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["TooLongName12345", 2]})["Status"], 0)

            # Consume_type=2: use Rename Card (16050002), Diamond stays 150
            dia_before = int(store.state["player"]["Diamond"])
            nres1 = store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["InuHero", 2]})
            self.assertEqual(nres1["Status"], 0)
            self.assertEqual(store.state["player"]["PlayerName"], "InuHero")
            self.assertEqual(nres1["Avatar"]["PlayerName"], "InuHero")
            self.assertEqual(int(store.state["player"]["Diamond"]), dia_before)
            self.assertIn("16050002", nres1["Avatar"]["GoodsInfo"])

            # Card is now gone -> consume_type=2 fails cleanly
            self.assertNotEqual(store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["AnotherName", 2]})["Status"], 0)

            # Consume_type=3: spend 100 Diamond
            nres2 = store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["KagomeVN", 3]})
            self.assertEqual(nres2["Status"], 0)
            self.assertEqual(store.state["player"]["PlayerName"], "KagomeVN")
            self.assertEqual(int(store.state["player"]["Diamond"]), dia_before - 100)

            # Now only 50 Diamond left -> reject -1105
            nres3 = store.handle_rpc({"ModuleName": "Player", "MethodName": "AlterPlayerName", "Data": ["BrokeName", 3]})
            self.assertEqual(nres3["Status"], -1105)
            self.assertEqual(store.state["player"]["PlayerName"], "KagomeVN")

    def test_05_treasure_compose_color_and_validation(self) -> None:
        """Treasure.TreasureCompose must consume 5 unequipped purple Step==0 treasures + 100k Gold for 16050020."""
        with tempfile.TemporaryDirectory() as td:
            store = self._new_store(td)
            store._grant_resources_from_tuples(
                [
                    (1112, 0, 200000),
                    (1401, 14011012, 6),   # Purple quality=10 books
                    (1401, 14010606, 1),   # Blue quality=6 book (colorLV=3)
                    (1401, 14010803, 1),   # Silver Book EXP fodder (quality=8, maxLV=0 -> excluded)
                ],
                source="test_tcompose_setup",
                tx_prefix="test_tcompose_setup",
            )
            store.save()

            purples = [t for t in store.state["treasures"] if int(t["TreasureModelId"]) == 14011012]
            blue = next(t for t in store.state["treasures"] if int(t["TreasureModelId"]) == 14010606)
            silver = next(t for t in store.state["treasures"] if int(t["TreasureModelId"]) == 14010803)

            # Put 1 purple as stepped and equip 1 on slot 0 to verify protection checks
            purples[5]["Step"] = 1
            store.state["slots"][0]["Book"] = purples[4]

            # Rejection checks (do not mutate gold or treasures)
            self.assertEqual(store.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureCompose", "Data": [[t["Id"] for t in purples[:4]]]})["Status"], -1317)
            self.assertEqual(store.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureCompose", "Data": [[purples[0]["Id"]] * 5]})["Status"], -1320)
            self.assertEqual(store.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureCompose", "Data": [[purples[0]["Id"], purples[1]["Id"], purples[2]["Id"], purples[3]["Id"], purples[4]["Id"]]]})["Status"], -1304)
            self.assertEqual(store.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureCompose", "Data": [[purples[0]["Id"], purples[1]["Id"], purples[2]["Id"], purples[3]["Id"], purples[5]["Id"]]]})["Status"], -1323)
            self.assertEqual(store.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureCompose", "Data": [[purples[0]["Id"], purples[1]["Id"], purples[2]["Id"], purples[3]["Id"], blue["Id"]]]})["Status"], -1325)
            self.assertEqual(store.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureCompose", "Data": [[purples[0]["Id"], purples[1]["Id"], purples[2]["Id"], purples[3]["Id"], silver["Id"]]]})["Status"], -1325)

            # Un-equip purples[4] and give purples[0] some Lv/EXP to test enhancement return cleanly
            store.state["slots"][0]["Book"] = None
            purples[0]["EXP"] = 12000
            purples[0]["Lv"] = store._treasure_lv_for_exp(14011012, 12000, 100)

            gold_before = int(store.state["player"]["Gold"])
            five_ids = [t["Id"] for t in purples[:5]]
            cres = store.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureCompose", "Data": [five_ids]})
            self.assertEqual(cres["Status"], 0)
            self.assertEqual(cres["Value"]["ConsumeList"], five_ids)
            self.assertEqual(int(store.state["player"]["Gold"]), gold_before - 100000)

            essence_stack = next((g for g in store.state["goods"] if int(g["GoodsModelId"]) == 16050020), None)
            self.assertIsNotNone(essence_stack)
            self.assertEqual(int(essence_stack["Num"]), 1)

            remaining_ids = {t["Id"] for t in store.state["treasures"]}
            for cid in five_ids:
                self.assertNotIn(cid, remaining_ids)

            # Should also have refunded EXP fodder treasures for purples[0]'s 12,000 EXP
            base_res = cres["Value"]["BaseGetGameResourceList"]
            self.assertTrue(any(14010803 == int(t.get("TreasureModelId", 0)) for b in base_res for t in b.get("Treasure", [])))

            # Insufficient Gold check (-1118)
            store.state["player"]["Gold"] = 50000
            extra_purples = []
            for _ in range(5):
                tid_b = store._grant_resources_from_tuples([(1401, 14011012, 1)], source="t2", tx_prefix="t2")
                extra_purples.append(tid_b[0]["Treasure"][0]["Id"])
            low_gold = store.handle_rpc({"ModuleName": "Treasure", "MethodName": "TreasureCompose", "Data": [extra_purples]})
            self.assertEqual(low_gold["Status"], -1118)


if __name__ == "__main__":
    unittest.main()
