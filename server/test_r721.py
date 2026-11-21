"""R7.21 acceptance & regression suite for Phó Bản Tổ Đội (Teambattle) & Gem (2000) persistence."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from emulator import GameEmulatorState


STAT_KEYS = (
    "HIT", "DOD", "CRI", "TEN", "BLO", "BOG", "CRId", "TEND",
    "CP", "BCP", "CPR", "BCPR", "DAMADD", "DAMCUT", "DAMADDR", "DAMCUTR",
)


class R721TeambattleTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.now = 1795176000  # 2026-11-20 14:00:00 UTC (21:00 UTC+7)
        self.reload()
        self.p.state["player"].update(Lv=100, Vip=9, VIPLv=9, IsNewPlayer=0, VIT=500, Diamond=5000)

    def reload(self):
        self.emu = GameEmulatorState(data_dir=self.root, env="dev", trace_path=self.root / "rpc.log")
        self.emu.clock.set_fixed(self.now)
        self.p = self.emu.profiles["normal"]

    def rpc(self, module, method, *args):
        return self.emu.handle_rpc({"ServerId": 1, "ModuleName": module, "MethodName": method, "Data": list(args)})

    def equip_strong_team(self, *, lv=80, step=15, equip_lv=160):
        self.p.state["player"]["StarId"] = 160
        self.p.state["heroes"] = []
        self.p.state["equips"] = []
        self.p.state["treasures"] = []
        for idx, model in enumerate((12011002, 12011004, 12012004, 12012005, 12013003, 12013005), 1):
            hero = self.p._build_hero_instance(model, lv=lv, step=step)
            self.p.state["heroes"].append(hero)
            slot = self.p.state["slots"][idx - 1]
            slot.update(HeroId=hero["Id"], HeroModelId=model)
            for equip_type, key in self.p.EQUIP_TYPE_TO_SLOT_KEY.items():
                eq = self.p._build_equip_instance(equip_type * 10000 + 701)
                eq.update(Lv=equip_lv, Step=min(10, step))
                self.p.state["equips"].append(eq)
                slot[key] = eq
            for kind, key, mid in ((1401, "Book", 14011615), (1402, "Horse", 14021615)):
                self.p._grant_resources_from_tuples([(kind, mid, 1)], "fixture", f"tb:{idx}:{kind}")
                tr = self.p.state["treasures"][-1]
                tr.update(Lv=equip_lv // 2, Step=min(10, step))
                slot[key] = tr
        self.p._recalc_all_slots_and_fap()
        self.p.save()

    def _sweep_member_objs(self, orig_fn, member: dict, fight_add_pct: int = 0):
        if member.get("IsLeader") == 1 and member.get("PlayerId") == str(self.p.state["player"]["PlayerId"]):
            node_id = int(self.p._teambattle_state()["team"]["node_id"])
            npcs = self.p._teambattle_npcs_for_node(node_id)
            return self.p._teambattle_npc_fight_objs(str(npcs[-1]["Id"]), fight_add_pct=fight_add_pct)
        return orig_fn(member, fight_add_pct=fight_add_pct)

    def test_extracted_config_counts_and_24_node_data_integrity(self):
        gd = self.p.game_data
        self.assertGreater(len(gd["gem_model"]), 0)
        self.assertEqual(gd["teambattle_config"].get("maxHoldTime"), 43200)
        self.assertEqual(gd["teambattle_config"].get("needVIT"), 20)
        self.assertEqual(len(gd["teambattle_nodes"]), 24)
        self.assertEqual(len(gd["teambattle_hold_drops"]), 144)
        self.assertEqual(len(gd["teambattle_hero_drops"]), 4)
        self.assertEqual(len(gd["teambattle_shop"]), 18)
        self.assertEqual(len(gd["teambattle_player_npcs"]), 72)
        self.assertEqual(len(gd["teambattle_hero_npcs"]), 432)

        # Every node must have >= 2 NPCs and valid enemy boss heroModelID
        for nid_str, node in gd["teambattle_nodes"].items():
            nid = int(nid_str)
            self.assertIn(str(node["heroModelID"]), gd["heroes"])
            self.assertGreaterEqual(len(self.p._teambattle_npcs_for_node(nid)), 2)
            enemies = self.p._teambattle_enemy_formation(nid)
            self.assertEqual(sum(1 for u in enemies if u), 3)

    def test_unlock_chain_all_24_nodes_combat_calibration_and_daily_reset(self):
        # Locked under Lv40
        self.p.state["player"]["Lv"] = 39
        self.assertEqual(self.rpc("TeambattleFightinfo", "GetInfo")["Status"], -1127)
        self.p.state["player"]["Lv"] = 100

        # Initially only nodes with empty needNodeModelID (1111..1611) are returned in GetInfo
        info = self.rpc("TeambattleFightinfo", "GetInfo")["Value"]
        returned_ids = {row["NodeModelID"] for row in info["TeambattleFightinfo"]}
        expected_initial = {
            int(k) for k, v in self.p.game_data["teambattle_nodes"].items() if not str(v.get("needNodeModelID", "")).strip()
        }
        self.assertEqual(returned_ids, expected_initial)

        # Locked node 1112 cannot be entered yet
        self.assertEqual(self.rpc("TeambattleInfo", "FightForMatch", 1112)["Status"], -7410)

        # Weak Lv1 player + 2 NPCs on 1111 loses; defeat keeps chapter unlocked & increments DailyTask #34
        self.p.state["heroes"] = [self.p._build_hero_instance(12010001, lv=1, step=0)]
        self.p.state["slots"][0].update(HeroId=self.p.state["heroes"][0]["Id"], HeroModelId=12010001)
        self.p._recalc_all_slots_and_fap()
        m_weak = self.rpc("TeambattleInfo", "FightForMatch", 1111)
        self.assertEqual(m_weak["Status"], 0)
        res_fail = self.rpc("TeambattleInfo", "Fight")
        self.assertEqual(res_fail["Status"], 0)
        self.assertEqual(res_fail["Value"]["FightInfo"]["IsWinFight"], 0)
        self.assertEqual(res_fail["Value"]["BaseGetGameResourceList"], [])
        self.assertIsNone(self.p._teambattle_state()["team"])
        tasks = self.rpc("DailyTaskInfo", "GetDaliyTaskInfo")["Value"]["TasksInfo"]
        t34 = next(t for t in tasks if t["Id"] == 34)
        self.assertEqual(t34["Num"], 1)

        # Still can retry immediately on same day after defeat with strong team
        self.equip_strong_team(lv=60, step=8, equip_lv=100)
        self.assertEqual(self.rpc("TeambattleInfo", "FightForMatch", 1111)["Status"], 0)
        res_win = self.rpc("TeambattleInfo", "Fight")
        self.assertEqual(res_win["Status"], 0)
        self.assertEqual(res_win["Value"]["FightInfo"]["IsWinFight"], 1)
        self.assertGreater(len(res_win["Value"]["BaseGetGameResourceList"]), 0)
        coins = self.p._get_goods_qty(16050023)
        self.assertEqual(coins, 10)

        # Claim first-clear reward once; duplicate rejected (-7408)
        first = self.rpc("TeambattleFightinfo", "DrawFirstReward", 1111)
        self.assertEqual(first["Status"], 0)
        self.assertEqual(self.p._get_goods_qty(16050023), 50)
        self.assertEqual(self.rpc("TeambattleFightinfo", "DrawFirstReward", 1111)["Status"], -7408)

        # Chapter 11 is now locked for the rest of today; cannot enter 1111 or newly unlocked 1112 today
        info2 = self.rpc("TeambattleFightinfo", "GetInfo")["Value"]
        ids2 = {row["NodeModelID"] for row in info2["TeambattleFightinfo"]}
        self.assertIn(1112, ids2)
        self.assertEqual(self.rpc("TeambattleInfo", "CreatTeams", 1112)["Status"], -7409)

        # Clear remaining 23 nodes across synthetic days using node-matched player power + 2 NPC teammates
        orig_objs_fn = self.p._teambattle_member_fight_objs
        self.p._teambattle_member_fight_objs = lambda m, fight_add_pct=0: self._sweep_member_objs(
            orig_objs_fn, m, fight_add_pct=fight_add_pct
        )
        cleared = {1111}
        ordered_nodes = sorted(int(k) for k in self.p.game_data["teambattle_nodes"])
        day_offset = 1
        try:
            while len(cleared) < 24:
                self.now += 86400
                self.emu.clock.set_fixed(self.now)
                chapters_used_today: set[int] = set()
                progressed = False
                for nid in ordered_nodes:
                    if nid in cleared:
                        continue
                    cfg = self.p.game_data["teambattle_nodes"][str(nid)]
                    ch = int(cfg["chapterModelID"])
                    if ch in chapters_used_today:
                        continue
                    tb = self.p._teambattle_state()
                    if not self.p._teambattle_node_unlocked(nid, tb):
                        continue
                    r_m = self.rpc("TeambattleInfo", "FightForMatch", nid)
                    self.assertEqual(r_m["Status"], 0, (nid, r_m))
                    r_f = self.rpc("TeambattleInfo", "Fight")
                    self.assertEqual(r_f["Status"], 0, (nid, r_f))
                    self.assertEqual(r_f["Value"]["FightInfo"]["IsWinFight"], 1, f"Matched team failed node {nid}")
                    self.assertEqual(self.rpc("TeambattleFightinfo", "DrawFirstReward", nid)["Status"], 0)
                    cleared.add(nid)
                    chapters_used_today.add(ch)
                    progressed = True
                day_offset += 1
                self.assertTrue(progressed, f"Stuck clearing nodes: {sorted(set(ordered_nodes) - cleared)}")
        finally:
            self.p._teambattle_member_fight_objs = orig_objs_fn
        self.assertEqual(len(cleared), 24)

    def test_manual_team_lobby_persistence_kick_dismiss_and_errors(self):
        # Empty team -> GetMyTeamInfo returns IsInTeam=0
        self.assertEqual(self.rpc("TeambattleInfo", "GetMyTeamInfo")["Value"], {"IsInTeam": 0})
        self.assertEqual(self.rpc("TeambattleInfo", "GetInviteInfo")["Value"], {"InviteInfo": []})
        self.assertEqual(self.rpc("TeambattleInfo", "UpdateAllInviteFlag", 1)["Value"], {"IsAllInviteFlg": 1})
        self.assertEqual(self.rpc("TeambattleInfo", "InterTeam", 1111)["Status"], -7417)

        # CreatTeams -> 1 member; Fight with <3 fails (-7421)
        ct = self.rpc("TeambattleInfo", "CreatTeams", 1111)
        self.assertEqual(ct["Status"], 0)
        self.assertEqual(len(ct["Value"]), 1)
        self.assertEqual(self.rpc("TeambattleInfo", "Fight")["Status"], -7421)

        # Reload mid-lobby preserves IsInTeam=1
        self.reload()
        my_team = self.rpc("TeambattleInfo", "GetMyTeamInfo")["Value"]
        self.assertEqual(my_team["IsInTeam"], 1)
        self.assertEqual(len(my_team["TeamsInfo"]), 1)

        # Cannot create a second team while already in team (-7414)
        self.assertEqual(self.rpc("TeambattleInfo", "CreatTeams", 1111)["Status"], -7414)

        # List friends -> invite one, kick one, then InviteAll fills to 3, DismissTeam clears
        friends = self.rpc("TeambattleInfo", "GetFriendsOrGuildMembers", 1111)["Value"]["FriendPlayer"]
        self.assertGreaterEqual(len(friends), 2)
        fid = friends[0]["PlayerId"]
        inv1 = self.rpc("TeambattleInfo", "InviteFriends", 1111, fid)
        self.assertEqual(inv1["Status"], 0)
        self.assertEqual(len(inv1["Value"]["TeamsInfo"]), 2)
        kicked = self.rpc("TeambattleInfo", "KickOutTeam", fid)
        self.assertEqual(kicked["Status"], 0)
        self.assertEqual(len(kicked["Value"]), 1)
        inv_all = self.rpc("TeambattleInfo", "InviteAll")
        self.assertEqual(inv_all["Status"], 0)
        self.assertEqual(len(inv_all["Value"]["TeamsInfo"]), 3)
        self.assertEqual(self.rpc("TeambattleInfo", "DismissTeam")["Status"], 0)
        self.assertEqual(self.rpc("TeambattleInfo", "GetMyTeamInfo")["Value"], {"IsInTeam": 0})

    def test_garrison_hold_12h_quick_draw_carryover_and_success_target_27(self):
        self.equip_strong_team(lv=60, step=8, equip_lv=100)
        # Clear 1111 first
        self.assertEqual(self.rpc("TeambattleInfo", "FightForMatch", 1111)["Status"], 0)
        res_f = self.rpc("TeambattleInfo", "Fight")
        self.assertEqual(res_f["Value"]["FightInfo"]["IsWinFight"], 1)

        # Non-owned or non-5-star hero cannot garrison (-7418); Jinenji (12011011 or valid 5*) check
        self.assertEqual(self.rpc("TeambattleHoldinfo", "HeroHold", 1111, 12011011)["Status"], -7418)

        # Grant an eligible 5-star hero (starNum==5, specialType!=255) for garrison
        valid_hero_mid = next(
            int(hid)
            for hid, hcfg in sorted(self.p.game_data["heroes"].items(), key=lambda kv: int(kv[0]))
            if int(hcfg.get("starNum", 0)) == 5 and int(hcfg.get("specialType", 0)) != 255
        )
        self.p._grant_resources_from_tuples([(1201, valid_hero_mid, 1)], "fixture", "hold_hero_5star")
        vit_before = self.p.state["player"]["VIT"]
        hold = self.rpc("TeambattleHoldinfo", "HeroHold", 1111, valid_hero_mid)
        self.assertEqual(hold["Status"], 0)
        self.assertEqual(self.p.state["player"]["VIT"], vit_before - 20)
        self.assertEqual(hold["Value"]["HoldInfo"]["HeroModelID"], valid_hero_mid)
        self.assertEqual(hold["Value"]["HoldInfo"]["HoldEndTime"], self.now + 43200)

        # SuccessTarget ID 27 reflects hold count (teambattle_count == 1)
        st_info = self.rpc("SuccessTargetInfo", "GetInfo")["Value"]
        t27 = next(row for row in st_info["TargetList"] if row["TargetId"] == 27)
        self.assertEqual(t27["ReachedNum"], 1)

        # Claim before 12h fails (-7407)
        self.assertEqual(self.rpc("TeambattleHoldinfo", "DrawHoldReward", 1111)["Status"], -7407)

        # Cross midnight into next day WITHOUT claiming yet: chapter 11 remains locked until claimed!
        self.now += 36000  # 10 hours later (07:00 next day, hold still has 2h remaining)
        self.emu.clock.set_fixed(self.now)
        self.assertEqual(self.rpc("TeambattleInfo", "CreatTeams", 1111)["Status"], -7409)

        # Advance past 12h -> DrawHoldReward succeeds & unlocks chapter 11 again next cycle
        self.now += 7205
        self.emu.clock.set_fixed(self.now)
        draw = self.rpc("TeambattleHoldinfo", "DrawHoldReward", 1111)
        self.assertEqual(draw["Status"], 0)
        self.assertGreater(len(draw["Value"]["BaseGetGameResourceList"]), 0)

        # QuickDrawHoldReward path on chapter 12 (node 1211) deducts Diamond and grants hold rewards early
        self.assertEqual(self.rpc("TeambattleInfo", "FightForMatch", 1211)["Status"], 0)
        self.assertEqual(self.rpc("TeambattleInfo", "Fight")["Value"]["FightInfo"]["IsWinFight"], 1)
        h2 = self.rpc("TeambattleHoldinfo", "HeroHold", 1211, valid_hero_mid)
        self.assertEqual(h2["Status"], 0)
        dia_before = self.p.state["player"]["Diamond"]
        qdraw = self.rpc("TeambattleHoldinfo", "QuickDrawHoldReward", 1211)
        self.assertEqual(qdraw["Status"], 0)
        self.assertLess(self.p.state["player"]["Diamond"], dia_before)
        self.assertGreater(len(qdraw["Value"]["BaseGetGameResourceList"]), 0)

    def test_shop_18_items_gem_persistence_and_gem_bags(self):
        # Verify all 18 TeambattleShopModel entries are purchasable, Gem (2000) persists in GetInitData, and shop limits enforce
        self.assertEqual(self.rpc("TeambattleShopinfo", "ShopInfo")["Value"], {"BuyShopInfo": []})
        self.p._grant_resources_from_tuples([(1605, 16050023, 50000)], "test", "tb_coins")
        self.p.save()

        # Insufficient coin guard (-1602) tested separately below; first buy 1 unit of every shop item (1..18)
        bought_gems_before = len(self.p.state["gems"])
        for sid in sorted(int(k) for k in self.p.game_data["teambattle_shop"]):
            res = self.rpc("TeambattleShopinfo", "BuyShop", sid, 1)
            self.assertEqual(res["Status"], 0, (sid, res))
            self.assertTrue(len(res["Value"]["BaseGetGameResourceList"]) > 0, (sid, res))

        self.assertGreater(len(self.p.state["gems"]), bought_gems_before)

        # Reload and verify GemInfo returned by Player.GetInitData
        self.reload()
        init_data = self.rpc("Player", "GetInitData")["Value"]
        self.assertEqual(len(init_data["GemInfo"]), len(self.p.state["gems"]))
        shop_after = self.rpc("TeambattleShopinfo", "ShopInfo")["Value"]["BuyShopInfo"]
        self.assertEqual(len(shop_after), 18)

        # Shop max-buy limit (-2104) & insufficient coin (-1602) checks
        lim_row = self.p.game_data["teambattle_shop"]["1"]
        orig_max = lim_row["totalMaxNum"]
        try:
            lim_row["totalMaxNum"] = 1
            self.assertEqual(self.rpc("TeambattleShopinfo", "BuyShop", 1, 1)["Status"], -2104)
        finally:
            lim_row["totalMaxNum"] = orig_max
        self.p.state["goods"] = [g for g in self.p.state["goods"] if int(g.get("GoodsModelId", 0)) != 16050023]
        self.assertEqual(self.rpc("TeambattleShopinfo", "BuyShop", 1, 1)["Status"], -1602)

        # Opening Gem bags (16020037, 16020040..46) persists real Gems
        gem_count_before = len(self.p.state["gems"])
        for gid in [16020037] + list(range(16020040, 16020047)):
            self.p._grant_resources_from_tuples([(1602, gid, 1)], "test", f"bag:{gid}")
            item = next(g for g in self.p.state["goods"] if g["GoodsModelId"] == gid)
            use_res = self.rpc("Goods", "GoodsUse", item["Id"], gid, 1)
            self.assertEqual(use_res["Status"], 0, (gid, use_res))
        self.assertEqual(len(self.p.state["gems"]), gem_count_before + 8)

    def test_no_regression_on_recruit_hero_bag_and_explore(self):
        self.p.state["player"]["Gold"] = 500000
        self.p.state["player"]["Diamond"] = 5000
        self.assertEqual(self.rpc("HeroRecruit", "Recruit", 1, 0)["Status"], 0)
        self.assertEqual(self.rpc("Explore", "ExploreInfo")["Status"], 0)


if __name__ == "__main__":
    unittest.main()
