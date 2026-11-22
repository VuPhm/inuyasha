"""Delta coverage for R7.30 (REC-P2-04A): Bạn Bè (Friend/FriendMessage/Enemy) & Hộp Thư (PlayerEmail)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import GameEmulatorState  # noqa: E402


class R730FriendAndEmailTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str) -> tuple[GameEmulatorState, any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
        emu.clock.set_fixed(1_763_370_000)
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(emu: GameEmulatorState, mod: str, fn: str, *args: object) -> dict:
        return emu.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    def test_01_recommend_search_npc_auto_accept_and_formation_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=10, vip_lv=2, source="test_r730")  # Lv 10 -> friendMax = 19

            rec1 = self._call(emu, "Friend", "GetRecommendFriendList", 10)
            self.assertEqual(rec1["Status"], 0)
            self.assertEqual(len(rec1["Value"]), 10)
            heroes_cfg = p.game_data["heroes"]
            for card in rec1["Value"]:
                self.assertIn(str(card["HeadImageId"]), heroes_cfg)
                self.assertGreater(card["FAP"], 0)

            rec2 = self._call(emu, "Friend", "GetRecommendFriendList", 10)
            self.assertEqual(rec2["Status"], 0)
            self.assertNotEqual([c["PlayerId"] for c in rec1["Value"]], [c["PlayerId"] for c in rec2["Value"]])

            search = self._call(emu, "Friend", "PlayerSearch", "khuyển")
            self.assertEqual(search["Status"], 0)
            self.assertTrue(any("Khuyển" in c["Name"] for c in search["Value"]))

            # NPC friend request auto-accepts and grants welcome reply + STA gift
            npc_id = rec1["Value"][0]["PlayerId"]
            ap1 = self._call(emu, "FriendMessage", "FriendApply", npc_id, "Kết bạn nhé!")
            self.assertEqual(ap1["Status"], 0)
            fl = self._call(emu, "Friend", "GetFriendList")
            self.assertEqual(fl["Status"], 0)
            self.assertEqual(len(fl["Value"]), 1)
            self.assertEqual(fl["Value"][0]["PlayerId"], npc_id)
            self.assertTrue(fl["Value"][0]["CanSendSTA"])

            # Slot.SlotFormations works for Friend NPC
            form = self._call(emu, "Slot", "SlotFormations", npc_id)
            self.assertEqual(form["Status"], 0)
            self.assertEqual(form["Value"]["PlayerInfo"]["PlayerId"], npc_id)
            self.assertEqual(len(form["Value"]["SlotInfo"]), 6)
            self.assertGreater(form["Value"]["PlayerInfo"]["FAP"], 0)

            # Duplicate apply rejected (-3008)
            self.assertEqual(self._call(emu, "FriendMessage", "FriendApply", npc_id, "Hi")["Status"], -3008)

            # Batch apply up to friendMax=19 then overflow fails (-3005)
            more = self._call(emu, "Friend", "GetRecommendFriendList", 20)["Value"]
            more_ids = [c["PlayerId"] for c in more]
            ba = self._call(emu, "FriendMessage", "BatchFriendApply", more_ids)
            self.assertEqual(ba["Status"], 0)
            fl_full = self._call(emu, "Friend", "GetFriendList")["Value"]
            self.assertEqual(len(fl_full), 19)

            remaining = self._call(emu, "Friend", "GetRecommendFriendList", 5)["Value"]
            self.assertTrue(len(remaining) >= 1)
            self.assertEqual(self._call(emu, "FriendMessage", "FriendApply", remaining[0]["PlayerId"], "")["Status"], -3005)

    def test_02_send_sta_daily_task_11_receive_sta_and_daily_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=25, vip_lv=2, source="test_r730")  # Lv 25 unlocks DailyTask 3000; friendMax = 34
            p.state["player"]["STA"] = 0
            p.save()

            recs = self._call(emu, "Friend", "GetRecommendFriendList", 12)["Value"]
            ba = self._call(emu, "FriendMessage", "BatchFriendApply", [c["PlayerId"] for c in recs])
            self.assertEqual(ba["Status"], 0)
            self.assertEqual(ba["Value"]["AppliedCount"], 12)

            # BatchSendFriendSTA updates DailyTask #11 (loopNum=10) & rejects duplicate (-3001)
            bs = self._call(emu, "FriendMessage", "BatchSendFriendSTA")
            self.assertEqual(bs["Status"], 0)
            self.assertEqual(bs["Value"]["SentCount"], 12)
            self.assertEqual(self._call(emu, "FriendMessage", "BatchSendFriendSTA")["Status"], -3001)

            fl = self._call(emu, "Friend", "GetFriendList")["Value"]
            self.assertTrue(all(item["CanSendSTA"] is False for item in fl))

            dt = self._call(emu, "DailyTaskInfo", "GetDaliyTaskInfo")["Value"]["TasksInfo"]
            t11 = next(t for t in dt if t["Id"] == 11)
            self.assertEqual(t11["Num"], 10)
            self.assertEqual(t11["Status"], 1)
            self.assertTrue(t11["CanDrawCredit"])
            gc = self._call(emu, "DailyTaskInfo", "GetCredit", 11)
            self.assertEqual(gc["Status"], 0)

            # STAData uses "PlayerName" (FriendScene.lua:579) and sets 1700/1701 red dots
            sta_msg = self._call(emu, "FriendMessage", "GetFriendSTAMessages")
            self.assertEqual(sta_msg["Status"], 0)
            self.assertEqual(sta_msg["Value"]["STADrawLeftCount"], 20)
            self.assertEqual(len(sta_msg["Value"]["STAData"]), 12)
            self.assertIn("PlayerName", sta_msg["Value"]["STAData"][0])
            self.assertEqual(sta_msg["Avatar"]["RedDotInfo"]["1700"], 1)
            self.assertEqual(sta_msg["Avatar"]["RedDotInfo"]["1701"], 1)

            # Claim single STA gift (+2 STA)
            first_sid = sta_msg["Value"]["STAData"][0]["PlayerId"]
            sta_before = int(p.state["player"]["STA"])
            rec1 = self._call(emu, "FriendMessage", "ReceiveFriendSTA", first_sid)
            self.assertEqual(rec1["Status"], 0)
            self.assertEqual(int(p.state["player"]["STA"]), sta_before + 2)
            self.assertEqual(rec1["Value"]["STADrawLeftCount"], 19)

            # BatchReceiveAndSendSTA claims until STAMaxNum (0->2->20 = 9 gifts), then empties rest cleanly
            batch_rec = self._call(emu, "FriendMessage", "BatchReceiveAndSendSTA")
            self.assertEqual(batch_rec["Status"], 0)
            self.assertEqual(batch_rec["Value"]["DrawCount"], 9)
            self.assertEqual(int(p.state["player"]["STA"]), int(p.state["player"]["STAMaxNum"]))
            self.assertEqual(self._call(emu, "Friend", "GetFriendList")["Avatar"]["RedDotInfo"]["1701"], 1)

            # Drain STA back to 0 and batch-claim the remaining 2 gifts
            p.state["player"]["STA"] = 0
            p.save()
            batch_rec2 = self._call(emu, "FriendMessage", "BatchReceiveAndSendSTA")
            self.assertEqual(batch_rec2["Status"], 0)
            self.assertEqual(batch_rec2["Value"]["DrawCount"], 2)
            self.assertEqual(batch_rec2["Value"]["STADrawLeftCount"], 8)
            self.assertEqual(self._call(emu, "Friend", "GetFriendList")["Avatar"]["RedDotInfo"]["1701"], 0)

            # When STA == STAMaxNum, claiming returns -3010
            p.state["player"]["STA"] = int(p.state["player"]["STAMaxNum"])
            extra_npc = self._call(emu, "Friend", "GetRecommendFriendList", 1)["Value"][0]["PlayerId"]
            self._call(emu, "FriendMessage", "FriendApply", extra_npc, "")
            self.assertEqual(self._call(emu, "FriendMessage", "ReceiveFriendSTA", extra_npc)["Status"], -3010)
            self.assertEqual(self._call(emu, "FriendMessage", "BatchReceiveAndSendSTA")["Status"], -3010)

            # Advance clock +1 day -> resets CanSendSTA=True, STADrawLeftCount=20, and seeds NPC STA gifts
            emu.clock.advance(86400)
            fl_next = self._call(emu, "Friend", "GetFriendList")["Value"]
            self.assertTrue(all(item["CanSendSTA"] is True for item in fl_next))
            sta_next = self._call(emu, "FriendMessage", "GetFriendSTAMessages")["Value"]
            self.assertEqual(sta_next["STADrawLeftCount"], 20)
            self.assertGreaterEqual(len(sta_next["STAData"]), 10)

    def test_03_two_way_s1_peer_friend_apply_message_and_sta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu.clock.set_fixed(1_763_370_000)
            emu.ensure_s1_account_slots(2)
            acct1 = emu.s1_accounts["acct_1"]
            acct2 = emu.s1_accounts["acct_2"]
            acct1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["PeerAlpha", 0]})
            acct2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["PeerBeta", 1]})
            acct1.admin_prepare_account(target_lv=20, vip_lv=2, source="test_r730")
            acct2.admin_prepare_account(target_lv=20, vip_lv=2, source="test_r730")
            acct2.state["player"]["STA"] = 10
            acct2.save()

            pid1 = str(acct1.state["player"]["PlayerId"])
            pid2 = str(acct2.state["player"]["PlayerId"])

            # acct1 searches & applies to acct2
            srch = acct1.handle_rpc({"ModuleName": "Friend", "MethodName": "PlayerSearch", "Data": ["PeerBeta"]})
            self.assertEqual(srch["Status"], 0)
            self.assertEqual(srch["Value"][0]["PlayerId"], pid2)

            ap = acct1.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "FriendApply", "Data": [pid2, "Kết bạn nha"]})
            self.assertEqual(ap["Status"], 0)

            # acct2 sees red dot 1902/1900 and pending apply in GetFriendMessageByPage
            init2 = acct2.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": []})
            self.assertEqual(init2["Avatar"]["RedDotInfo"]["1902"], 1)
            self.assertEqual(init2["Avatar"]["RedDotInfo"]["1900"], 1)
            self.assertEqual(init2["Avatar"]["RedDotInfo"]["1700"], 1)

            msgs2 = acct2.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "GetFriendMessageByPage", "Data": [0, 10]})
            self.assertEqual(msgs2["Status"], 0)
            self.assertEqual(len(msgs2["Value"]), 1)
            self.assertEqual(msgs2["Value"][0]["Type"], 1)
            self.assertEqual(msgs2["Value"][0]["SendPlayerId"], pid1)

            # Reject first -> still not friends
            rej = acct2.handle_rpc({"ModuleName": "Friend", "MethodName": "FriendApplyResponse", "Data": [pid1, False]})
            self.assertEqual(rej["Status"], 0)
            self.assertEqual(acct1.handle_rpc({"ModuleName": "Friend", "MethodName": "GetFriendList", "Data": []})["Value"], [])

            # Re-apply -> accept -> mutual friendship!
            self.assertEqual(acct1.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "FriendApply", "Data": [pid2, "Xin chào"]})["Status"], 0)
            acc = acct2.handle_rpc({"ModuleName": "Friend", "MethodName": "FriendApplyResponse", "Data": [pid1, True]})
            self.assertEqual(acc["Status"], 0)
            self.assertEqual(acc["Avatar"]["RedDotInfo"]["1902"], 0)

            fl1 = acct1.handle_rpc({"ModuleName": "Friend", "MethodName": "GetFriendList", "Data": []})["Value"]
            fl2 = acct2.handle_rpc({"ModuleName": "Friend", "MethodName": "GetFriendList", "Data": []})["Value"]
            self.assertEqual([x["PlayerId"] for x in fl1], [pid2])
            self.assertEqual([x["PlayerId"] for x in fl2], [pid1])

            # Two-way message & STA gift
            self.assertEqual(acct1.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "SendFriendMessage", "Data": [pid2, "Đi phó bản nào!"]})["Status"], 0)
            self.assertEqual(acct1.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "SendFriendSTA", "Data": [pid2]})["Status"], 0)

            page2 = acct2.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "GetFriendMessageByPage", "Data": [0, 10]})
            self.assertEqual(page2["Status"], 0)
            self.assertEqual(page2["Value"][0]["Type"], 2)
            self.assertEqual(page2["Value"][0]["Content"], "Đi phó bản nào!")
            self.assertEqual(page2["Avatar"]["RedDotInfo"]["1902"], 0)

            sta_list2 = acct2.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "GetFriendSTAMessages", "Data": []})["Value"]["STAData"]
            self.assertEqual(len(sta_list2), 1)
            self.assertEqual(sta_list2[0]["PlayerId"], pid1)
            claim2 = acct2.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "ReceiveFriendSTA", "Data": [pid1]})
            self.assertEqual(claim2["Status"], 0)
            self.assertEqual(int(acct2.state["player"]["STA"]), 12)

            # Mutual delete
            self.assertEqual(acct1.handle_rpc({"ModuleName": "Friend", "MethodName": "DeleteFriend", "Data": [pid2]})["Status"], 0)
            self.assertEqual(acct1.handle_rpc({"ModuleName": "Friend", "MethodName": "GetFriendList", "Data": []})["Value"], [])
            self.assertEqual(acct2.handle_rpc({"ModuleName": "Friend", "MethodName": "GetFriendList", "Data": []})["Value"], [])

    def test_04_enemy_blacklist_and_chat_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=10, vip_lv=1, source="test_r730")
            self.assertEqual(self._call(emu, "Enemy", "GetEnemyList")["Value"], [])

            rec = self._call(emu, "Friend", "GetRecommendFriendList", 3)["Value"]
            npc_id = rec[0]["PlayerId"]
            self._call(emu, "FriendMessage", "FriendApply", npc_id, "")
            self.assertEqual(len(self._call(emu, "Friend", "GetFriendList")["Value"]), 1)

            # Self blacklist rejected (-3006)
            self.assertEqual(self._call(emu, "Enemy", "AddEnemy", p.state["player"]["PlayerId"], "")["Status"], -3006)

            # AddEnemy returns single dict (ChatLayer.lua:1535) and removes from friends
            added = self._call(emu, "Enemy", "AddEnemy", npc_id, "Spam")
            self.assertEqual(added["Status"], 0)
            self.assertEqual(added["Value"]["PlayerId"], npc_id)
            self.assertEqual(self._call(emu, "Friend", "GetFriendList")["Value"], [])

            elist = self._call(emu, "Enemy", "GetEnemyList")["Value"]
            self.assertEqual(len(elist), 1)
            self.assertEqual(elist[0]["PlayerId"], npc_id)

            # DeleteEnemy removes target; second delete fails (-3019)
            self.assertEqual(self._call(emu, "Enemy", "DeleteEnemy", npc_id)["Status"], 0)
            self.assertEqual(self._call(emu, "Enemy", "GetEnemyList")["Value"], [])
            self.assertEqual(self._call(emu, "Enemy", "DeleteEnemy", npc_id)["Status"], -3019)

    def test_05_player_email_paging_filtering_red_dots_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu.clock.set_fixed(1_763_370_000)
            emu.ensure_s1_account_slots(2)
            acct1 = emu.s1_accounts["acct_1"]
            acct2 = emu.s1_accounts["acct_2"]
            acct1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["Challenger", 0]})
            acct2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["Defender", 1]})
            acct1.admin_prepare_account(target_lv=30, vip_lv=4, source="test_r730")
            acct2.admin_prepare_account(target_lv=30, vip_lv=2, source="test_r730")

            # Seeded VN welcome email (Type=1) triggers 1903 & 1900 red dots
            init1 = acct1.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": []})
            self.assertEqual(init1["Avatar"]["RedDotInfo"]["1903"], 1)
            self.assertEqual(init1["Avatar"]["RedDotInfo"]["1900"], 1)

            sys_page = acct1.handle_rpc({"ModuleName": "PlayerEmail", "MethodName": "GetEmailsByPage", "Data": [1, 0, 10]})
            self.assertEqual(sys_page["Status"], 0)
            self.assertEqual(len(sys_page["Value"]), 1)
            self.assertEqual(sys_page["Value"][0]["Type"], 1)
            self.assertEqual(sys_page["Avatar"]["RedDotInfo"]["1903"], 0)
            welcome_id = sys_page["Value"][0]["Id"]

            # Empower acct1 so PVP fight against acct2 (rank 1488 < 1500) succeeds & pushes Battle Email to acct2
            res1 = acct1._grant_resources_from_tuples(
                [(1201, 12011004, 1), (1201, 12012005, 1), (1301, 13010602, 2), (1117, 0, 5_000_000)],
                source="test_r730",
                tx_prefix="pvp",
            )
            for idx, h in enumerate(res1[0]["Hero"], start=2):
                acct1.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
                acct1.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [h["Id"], 30]})
            acct1.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [acct1.state["heroes"][0]["Id"], 30]})
            for s_idx, eq in enumerate(res1[0]["Equip"], start=1):
                acct1.handle_rpc({"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [s_idx, eq["Id"], "", "", "", "", ""]})
            acct1.save()

            pid2 = str(acct2.state["player"]["PlayerId"])
            pvp_res = acct1.handle_rpc({"ModuleName": "PVP", "MethodName": "PVPFight", "Data": [pid2, 1488]})
            self.assertEqual(pvp_res["Status"], 0)
            self.assertEqual(pvp_res["Value"]["IsWinFight"], 1)

            init2 = acct2.handle_rpc({"ModuleName": "Player", "MethodName": "GetInitData", "Data": []})
            self.assertEqual(init2["Avatar"]["RedDotInfo"]["1901"], 1)
            self.assertEqual(init2["Avatar"]["RedDotInfo"]["1900"], 1)

            bat2 = acct2.handle_rpc({"ModuleName": "PlayerEmail", "MethodName": "GetEmailsByPage", "Data": [2, 0, 10]})
            self.assertEqual(bat2["Status"], 0)
            self.assertEqual(len(bat2["Value"]), 1)
            self.assertEqual(bat2["Value"][0]["Type"], 2)
            self.assertEqual(bat2["Value"][0]["SubModuleId"], 2502)
            self.assertEqual(bat2["Avatar"]["RedDotInfo"]["1901"], 0)

            # BossBattle.FriendHelp pushes Boss Help system email (SubModuleId=2203, IsFriend=1) to S1 friend
            pid1 = str(acct1.state["player"]["PlayerId"])
            self.assertEqual(acct2.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "FriendApply", "Data": [pid1, "Hi"]})["Status"], 0)
            self.assertEqual(acct1.handle_rpc({"ModuleName": "Friend", "MethodName": "FriendApplyResponse", "Data": [pid2, True]})["Status"], 0)

            boss_id = acct2._maybe_trigger_luckboss(force=True)
            self.assertIsNotNone(boss_id)
            help_res = acct2.handle_rpc({"ModuleName": "BossBattle", "MethodName": "FriendHelp", "Data": [boss_id]})
            self.assertEqual(help_res["Status"], 0)

            all1 = acct1.handle_rpc({"ModuleName": "PlayerEmail", "MethodName": "GetEmailsByPage", "Data": [0, 0, 10]})
            self.assertEqual(all1["Status"], 0)
            self.assertTrue(any(e["SubModuleId"] == 2203 and e["IsFriend"] == 1 for e in all1["Value"]))

            # Invalid email type -> -2703; delete welcome email -> removes cleanly; repeat -> -2706
            self.assertEqual(acct1.handle_rpc({"ModuleName": "PlayerEmail", "MethodName": "GetEmailsByPage", "Data": [9, 0, 10]})["Status"], -2703)
            del_ok = acct1.handle_rpc({"ModuleName": "PlayerEmail", "MethodName": "DeleteEmail", "Data": [[welcome_id]]})
            self.assertEqual(del_ok["Status"], 0)
            self.assertEqual(del_ok["Value"]["DeletedIds"], [welcome_id])
            self.assertEqual(acct1.handle_rpc({"ModuleName": "PlayerEmail", "MethodName": "DeleteEmail", "Data": [[welcome_id]]})["Status"], -2706)

    def test_06_teambattle_friend_integration_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu.clock.set_fixed(1_763_370_000)
            emu.ensure_s1_account_slots(2)
            acct1 = emu.s1_accounts["acct_1"]
            acct2 = emu.s1_accounts["acct_2"]
            acct1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["TeamHost", 0]})
            acct2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["TeamBuddy", 1]})
            acct1.admin_prepare_account(target_lv=50, vip_lv=4, source="test_r730")
            acct2.admin_prepare_account(target_lv=50, vip_lv=4, source="test_r730")
            for acct in (acct1, acct2):
                res = acct._grant_resources_from_tuples(
                    [(1201, 12011004, 1), (1201, 12012005, 1), (1301, 13010602, 2), (1117, 0, 5_000_000)],
                    source="test_r730",
                    tx_prefix="tb",
                )
                for idx, h in enumerate(res[0]["Hero"], start=2):
                    acct.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
                    acct.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [h["Id"], 50]})
                acct.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [acct.state["heroes"][0]["Id"], 50]})
                for s_idx, eq in enumerate(res[0]["Equip"], start=1):
                    acct.handle_rpc({"ModuleName": "Slot", "MethodName": "OneKeyEquipCombat", "Data": [s_idx, eq["Id"], "", "", "", "", ""]})
                acct.save()

            pid1 = str(acct1.state["player"]["PlayerId"])
            pid2 = str(acct2.state["player"]["PlayerId"])
            self.assertEqual(acct1.handle_rpc({"ModuleName": "FriendMessage", "MethodName": "FriendApply", "Data": [pid2, "Tổ đội!"]})["Status"], 0)
            self.assertEqual(acct2.handle_rpc({"ModuleName": "Friend", "MethodName": "FriendApplyResponse", "Data": [pid1, True]})["Status"], 0)

            self.assertEqual(acct1.handle_rpc({"ModuleName": "TeambattleInfo", "MethodName": "CreatTeams", "Data": [1111]})["Status"], 0)
            mates = acct1.handle_rpc({"ModuleName": "TeambattleInfo", "MethodName": "GetFriendsOrGuildMembers", "Data": [1111]})["Value"]["FriendPlayer"]
            self.assertEqual(mates[0]["PlayerId"], pid2)

            inv = acct1.handle_rpc({"ModuleName": "TeambattleInfo", "MethodName": "InviteFriends", "Data": [1111, pid2]})
            self.assertEqual(inv["Status"], 0)
            self.assertEqual([m["PlayerId"] for m in inv["Value"]["TeamsInfo"]], [pid1, pid2])

            # Invite a 3rd teammate (node NPC / InviteOneKey) so full 3-member squad can Fight
            inv3 = acct1.handle_rpc({"ModuleName": "TeambattleInfo", "MethodName": "InviteFriendsForOneKey", "Data": []})
            self.assertEqual(inv3["Status"], 0)
            self.assertEqual(len(inv3["Value"]["TeamsInfo"]), 3)

            fight = acct1.handle_rpc({"ModuleName": "TeambattleInfo", "MethodName": "Fight", "Data": []})
            self.assertEqual(fight["Status"], 0)
            self.assertIn("FightInfo", fight["Value"])

            # Persistence across emulator reload
            emu2 = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu2.clock.set_fixed(1_763_370_000)
            fl_reloaded = emu2.profiles["normal"].handle_rpc({"ModuleName": "Friend", "MethodName": "GetFriendList", "Data": []})["Value"]
            self.assertEqual([x["PlayerId"] for x in fl_reloaded], [pid2])


if __name__ == "__main__":
    unittest.main()
