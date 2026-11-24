#!/usr/bin/env python3
"""Unit tests for R8.3 pre-ship polish features:
1. Local S1 account deletion + explicit slot persistence (no resurrection)
2. Lucky Money Tree (4432) upgraded 1M Gold & 1000 Đá Đột Phá rewards
3. Treasure Hunt continuous loot (allow_continue=1) & multi-compose
4. Friend Sparring (Friend.FriendFight) for local S1 peers, Cloud synced peers & NPCs
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from emulator import GameEmulatorState  # noqa: E402
from hybrid_sync import HybridSyncManager  # noqa: E402
from test_r82_hybrid_sync import _MockCloudflareSyncHub, _prepare_player  # noqa: E402


class R83PreShipPolishTests(unittest.TestCase):
    def test_01_delete_s1_account_persists_and_blocks_last_account(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            emu = GameEmulatorState(persist=True, data_dir=d)
            listed = emu.list_s1_accounts(ensure_slots=3)
            self.assertEqual(len(listed["Accounts"]), 3)

            # Delete active acct_1 -> switches cleanly to remaining account and creates safety backup
            del_res = emu.delete_s1_account("acct_1")
            self.assertTrue(del_res["ok"])
            self.assertEqual(del_res["DeletedAccountId"], "acct_1")
            self.assertEqual(len(del_res["Accounts"]), 2)
            self.assertEqual(emu.active_account_id, "acct_2")
            self.assertTrue(Path(del_res["SafetyBackupPath"]).is_file())
            self.assertFalse((d / "normal_profile.json").exists())

            # Reloading from disk & calling list_s1_accounts(ensure_slots=3) must NOT resurrect acct_1!
            emu2 = GameEmulatorState(persist=True, data_dir=d)
            listed2 = emu2.list_s1_accounts(ensure_slots=3)
            ids2 = [a["account_id"] for a in listed2["Accounts"]]
            self.assertEqual(ids2, ["acct_2", "acct_3"])

            # Delete acct_3 -> only acct_2 remains; deleting last remaining account must fail safely
            del_res3 = emu2.delete_s1_account("acct_3")
            self.assertTrue(del_res3["ok"])
            self.assertEqual([a["account_id"] for a in del_res3["Accounts"]], ["acct_2"])

            last_del = emu2.delete_s1_account("acct_2")
            self.assertFalse(last_del["ok"])
            self.assertIn("duy nhất", last_del["error"])

    def test_02_lucky_money_tree_4432_upgraded_rewards(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=False, data_dir=Path(td))
            prof = emu.s1_accounts["acct_1"]
            prof.admin_prepare_account(target_lv=30, vip_lv=5)
            prof.state["player"]["Diamond"] = 50000

            info = prof.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "GetInfo", "Data": []})["Value"]
            show_gold = [r for s in info["ShowRewards"] for r in s["Reward"] if r["ResourceTypeSub"] == 1112]
            show_stones = [r for s in info["ShowRewards"] for r in s["Reward"] if r["ModelId"] == 16050001]
            self.assertTrue(any(r["Count"] >= 1_000_000 for r in show_gold))
            self.assertTrue(any(r["Count"] >= 1000 for r in show_stones))

            # Shake 10 times and verify milestone 5 grants >= 1M Gold & >= 1000 Đá Đột Phá
            gold_before = int(prof.state["player"]["Gold"])
            stones_before = next(
                (int(g["Num"]) for g in prof.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == 16050001),
                0,
            )
            shake = prof.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "ShakeTree", "Data": [10]})
            self.assertEqual(shake["Status"], 0)
            draw5 = prof.handle_rpc({"ModuleName": "TimedMoneyTree", "MethodName": "DrawReward", "Data": [5]})
            self.assertEqual(draw5["Status"], 0)

            gold_after = int(prof.state["player"]["Gold"])
            stones_after = next(
                (int(g["Num"]) for g in prof.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == 16050001),
                0,
            )
            self.assertGreaterEqual(gold_after - gold_before, 1_000_000)
            self.assertGreaterEqual(stones_after - stones_before, 1000)

    def test_03_treasure_continue_hunt_and_multi_compose(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=False, data_dir=Path(td))
            prof = emu.s1_accounts["acct_1"]
            prof.admin_prepare_account(target_lv=50, vip_lv=8)
            prof.state["player"]["STA"] = 100

            tid = 14010501  # 3-shard treasure: 15032101, 15032102, 15032103
            r1 = prof.handle_rpc({"ModuleName": "TreasureLoot", "MethodName": "TreasureLootForOneKey", "Data": [tid]})
            self.assertEqual(r1["Status"], 0)
            self.assertEqual(r1["Value"]["TotalLootCount"], 3)

            # Default 1-arg call still blocks with -2010 when all shards are owned (>=1)
            r_dup = prof.handle_rpc({"ModuleName": "TreasureLoot", "MethodName": "TreasureLootForOneKey", "Data": [tid]})
            self.assertEqual(r_dup["Status"], -2010)

            # With allow_continue=1, hunts a complete second set (min 1 -> 2 across all shards!)
            r2 = prof.handle_rpc({"ModuleName": "TreasureLoot", "MethodName": "TreasureLootForOneKey", "Data": [tid, 1]})
            self.assertEqual(r2["Status"], 0)
            self.assertGreaterEqual(r2["Value"]["TotalLootCount"], 3)
            self.assertEqual(set(r2["Value"]["LootInfo"].values()), {15032101, 15032102, 15032103})

            shard_counts = {
                int(d["TreasureDebrisModelId"]): int(d["Num"])
                for d in prof.state["treasure_debris"]
                if int(d["TreasureDebrisModelId"]) in (15032101, 15032102, 15032103)
            }
            self.assertEqual(shard_counts, {15032101: 2, 15032102: 2, 15032103: 2})

            # Multi-compose with req_count=0 composes all 2 sets at once!
            tr_before = sum(1 for t in prof.state.get("treasures", []) if int(t.get("TreasureModelId", 0)) == tid)
            comp = prof.handle_rpc({"ModuleName": "TreasureDebris", "MethodName": "TreasureDebrisCompose", "Data": [tid, 0]})
            self.assertEqual(comp["Status"], 0)
            self.assertEqual(comp["Value"]["ComposedCount"], 2)
            tr_after = sum(1 for t in prof.state.get("treasures", []) if int(t.get("TreasureModelId", 0)) == tid)
            self.assertEqual(tr_after - tr_before, 2)

    def test_04_friend_fight_local_peers_cloud_peers_and_npcs(self) -> None:
        # 1) Same-device S1 accounts sparring (0 STA, battle email delivered to acct_2)
        with tempfile.TemporaryDirectory() as td:
            emu = GameEmulatorState(persist=True, data_dir=Path(td))
            emu.list_s1_accounts(ensure_slots=2)
            p1 = emu.s1_accounts["acct_1"]
            p2 = emu.s1_accounts["acct_2"]
            p1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["LocalP1", 1]})
            p2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["LocalP2", 0]})
            p1.admin_prepare_account(target_lv=40, vip_lv=3)
            p2.admin_prepare_account(target_lv=20, vip_lv=1)
            p1.state["player"]["STA"] = 10
            p2_pid = str(p2.state["player"]["PlayerId"])

            duel_local = p1.handle_rpc({"ModuleName": "Friend", "MethodName": "FriendFight", "Data": [p2_pid]})
            self.assertEqual(duel_local["Status"], 0)
            self.assertEqual(duel_local["Value"]["TargetPlayerId"], p2_pid)
            self.assertEqual(duel_local["Value"]["TargetName"], "LocalP2")
            self.assertIn("FightObjs", duel_local["Value"]["FightInfo"])
            self.assertEqual(p1.state["player"]["STA"], 10)  # 0 STA cost
            self.assertTrue(
                any("Giao Hữu" in str(e.get("Subject", "")) for e in p2.state["social"].get("emails", []))
            )

            # Friend NPC sparring also works
            npc_list = p1.handle_rpc({"ModuleName": "Friend", "MethodName": "GetRecommendFriendList", "Data": [5]})["Value"]
            npc_pid = next(c["PlayerId"] for c in npc_list if c["PlayerId"] != p2_pid)
            duel_npc = p1.handle_rpc({"ModuleName": "Friend", "MethodName": "FriendFight", "Data": [npc_pid]})
            self.assertEqual(duel_npc["Status"], 0)
            self.assertIn("FightObjs", duel_npc["Value"]["FightInfo"])

        # 2) Cloud-synced peer sparring across devices via HybridSyncManager
        hub = _MockCloudflareSyncHub(invite_code="INU-999")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d1, d2 = root / "d1", root / "d2"
            d1.mkdir(); d2.mkdir()
            e1 = GameEmulatorState(persist=True, data_dir=d1)
            e2 = GameEmulatorState(persist=True, data_dir=d2)
            e1.hybrid_sync = HybridSyncManager(d1, e1, persist=True, default_url="https://m.w.dev", http_opener=hub.opener)
            e2.hybrid_sync = HybridSyncManager(d2, e2, persist=True, default_url="https://m.w.dev", http_opener=hub.opener)
            _prepare_player(e1, "CloudHero1", lv=50)
            _prepare_player(e2, "CloudHero2", lv=30)
            e1.hybrid_sync.register("ch1", "pw123", invite_code="INU-999")
            e2.hybrid_sync.register("ch2", "pw123", invite_code="INU-999")
            e1.hybrid_sync.sync_now(ignore_cooldown=True)

            p2_cloud_pid = e2.s1_accounts["acct_1"].state["player"]["PlayerId"]
            duel_cloud = e1.s1_accounts["acct_1"].handle_rpc(
                {"ModuleName": "Friend", "MethodName": "FriendFight", "Data": [p2_cloud_pid]}
            )
            self.assertEqual(duel_cloud["Status"], 0)
            self.assertEqual(duel_cloud["Value"]["IsWinFight"], 1)
            self.assertTrue(
                any(ev["event_type"] == "pvp_challenge_log" for ev in e1.hybrid_sync.cfg["outgoing_events"])
            )


if __name__ == "__main__":
    unittest.main()
