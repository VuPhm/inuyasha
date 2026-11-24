"""Delta coverage for R7.31 (REC-P2-04B): Bang Hội cục bộ S1 (Guild 30 + GuildBossInfo 6 + GuildReward 2 = 38 RPCs)."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import EMPTY_ENTITY_ID, GameEmulatorState  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R731GuildSystemTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
        # Tuesday 2026-11-17 12:00:00 UTC+7 — active window for GuildBoss, Teambattle, GGZJ & Gddh
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 17, 12, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(prof: any, mod: str, fn: str, *args: object) -> dict:
        return prof.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    @staticmethod
    def _count_goods(prof: any, model_id: int) -> int:
        return sum(int(g.get("Num", 0)) for g in prof.state.get("goods", []) if int(g.get("GoodsModelId", 0)) == model_id)

    def _prepare_hero_squad(self, prof: any, target_lv: int = 40, vip_lv: int = 4) -> dict:
        prof.admin_prepare_account(target_lv=target_lv, vip_lv=vip_lv, source="test_r731")
        prof.state["player"].update(Diamond=10_000, Gold=5_000_000, STA=60, HeroEXP=5_000_000)
        res = prof._grant_resources_from_tuples(
            [
                (1201, 12011004, 1),
                (1201, 12012005, 1),
                (1201, 12013004, 1),
                (1301, 13010602, 4),
                (1302, 13020602, 4),
                (1605, 16050016, 25),
            ],
            source="test_r731",
            tx_prefix="setup",
        )
        heroes = res[0]["Hero"]
        weapons = [e for e in res[0]["Equip"] if int(e["EquipModelId"]) == 13010602]
        helmets = [e for e in res[0]["Equip"] if int(e["EquipModelId"]) == 13020602]
        prof.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [prof.state["heroes"][0]["Id"], target_lv]})
        for idx, h in enumerate(heroes, start=2):
            prof.handle_rpc({"ModuleName": "Slot", "MethodName": "HeroCombat", "Data": [idx, h["Id"]]})
            prof.handle_rpc({"ModuleName": "Hero", "MethodName": "HeroLvUp", "Data": [h["Id"], target_lv]})
        for slot_idx in range(1, 5):
            prof.handle_rpc(
                {
                    "ModuleName": "Slot",
                    "MethodName": "OneKeyEquipCombat",
                    "Data": [slot_idx, weapons[slot_idx - 1]["Id"], helmets[slot_idx - 1]["Id"], "", "", "", ""],
                }
            )
        prof.save()
        return heroes[0]

    def test_01_guild_configs_npc_browse_apply_auto_join_and_exit(self) -> None:
        gd = json.loads((ROOT / "server" / "game_data.json").read_text(encoding="utf-8"))
        self.assertEqual(len(gd["guild_config"]), 17)
        self.assertEqual(len(gd["guild_lv"]), 30)
        self.assertEqual(len(gd["guild_posts"]), 4)
        self.assertEqual(len(gd["guild_build_types"]), 3)
        self.assertEqual(len(gd["guild_buildings"]), 9)
        self.assertEqual(len(gd["guild_building_lv"]), 5)
        self.assertEqual(sum(len(v) for v in gd["guild_building_lv"].values()), 150)
        self.assertEqual(len(gd["guild_shop"]), 22)
        self.assertEqual(len(gd["guild_bosses"]), 3)
        self.assertEqual(len(gd["guild_share"]), 1)
        self.assertEqual(len(gd["guild_donate"]), 2)
        for boss_id in ("12015019", "12015020", "12015021"):
            self.assertIn(boss_id, gd["heroes"])

        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=20, vip_lv=2, source="test_r731")
            p.state["player"].update(Diamond=2000, Gold=1_000_000)

            self.assertEqual(self._call(p, "Guild", "CreateGuild", "Sớm Quá", "")["Status"], -3449)
            self.assertEqual(self._call(p, "Guild", "GuildApply", "any")["Status"], -3449)

            self._prepare_hero_squad(p, target_lv=60, vip_lv=2)

            browse = self._call(p, "Guild", "GetApplyGuildInfo", 0)
            self.assertEqual(browse["Status"], 0)
            names = {g["Name"]: g["Id"] for g in browse["Value"]["GuildListInfo"]}
            self.assertTrue({"Tây Quốc", "Hội Trừ Yêu", "Bạch Linh Sơn"}.issubset(names.keys()))

            not_full = self._call(p, "Guild", "GetApplyGuildInfoForNotFull", 0)
            self.assertEqual(not_full["Status"], 0)
            self.assertGreaterEqual(len(not_full["Value"]["GuildListInfo"]), 3)

            queried = self._call(p, "Guild", "GuildQuery", "tây quốc")
            self.assertEqual(queried["Status"], 0)
            self.assertEqual(queried["Value"]["GuildListInfo"][0]["Name"], "Tây Quốc")

            wk_rank = self._call(p, "Guild", "GetGuildRankListForWeek", 0)
            self.assertEqual(wk_rank["Status"], 0)
            self.assertGreaterEqual(len(wk_rank["Value"]["GuildRankInfoForWeek"]), 3)

            tay_quoc_id = names["Tây Quốc"]
            joined = self._call(p, "Guild", "GuildApply", tay_quoc_id)
            self.assertEqual(joined["Status"], 0)
            self.assertEqual(joined["Value"]["GuildInfo"]["Name"], "Tây Quốc")
            # GuildBuildInfo[1] (1-based index 2 in Lua) must be GuildShop 34005000
            self.assertEqual(joined["Value"]["GuildBuildInfo"][1]["BuildingId"], 34005000)
            self.assertEqual(joined["Avatar"]["GuildId"], tay_quoc_id)
            self.assertEqual(joined["Avatar"]["GuildName"], "Tây Quốc")

            lb = self._call(p, "LeaderBoard", "RankList", 1)
            self.assertEqual(lb["Status"], 0)
            my_pid = p.state["player"]["PlayerId"]
            me_lb = next((r for r in lb["Value"]["RankList"] if r["Id"] == my_pid), None)
            self.assertIsNotNone(me_lb)
            self.assertEqual(me_lb["GuildName"], "Tây Quốc")

            # Cannot apply again while in a guild
            self.assertEqual(self._call(p, "Guild", "GuildApply", names["Hội Trừ Yêu"])["Status"], -3404)

            exited = self._call(p, "Guild", "ExitGuild")
            self.assertEqual(exited["Status"], 0)
            self.assertEqual(exited["Avatar"]["GuildId"], EMPTY_ENTITY_ID)
            self.assertEqual(exited["Avatar"]["GuildName"], "")

    def test_02_create_guild_apply_approval_roles_impeach_kick_dismiss_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            base_ts = _ts_vn(2026, 11, 17, 12, 0)
            emu.clock.set_fixed(base_ts)
            emu.ensure_s1_account_slots(3)
            a1, a2, a3 = emu.s1_accounts["acct_1"], emu.s1_accounts["acct_2"], emu.s1_accounts["acct_3"]
            for idx, acct in enumerate((a1, a2, a3), start=1):
                acct.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": [f"BangChu{idx}", idx % 2]})
                acct.handle_rpc({"ModuleName": "Player", "MethodName": "Login", "Data": []})
                acct.admin_prepare_account(target_lv=35, vip_lv=4, source="test_r731")
                acct.state["player"].update(Diamond=5000, Gold=2_000_000, FAP=50_000 + idx * 1000)
                acct.save()

            pid1 = str(a1.state["player"]["PlayerId"])
            pid2 = str(a2.state["player"]["PlayerId"])
            pid3 = str(a3.state["player"]["PlayerId"])

            created = self._call(a1, "Guild", "CreateGuild", "Ngọc Tứ Hồn", "Đoàn kết là sức mạnh")
            self.assertEqual(created["Status"], 0)
            gid = created["Value"]["GuildInfo"]["Id"]
            self.assertEqual(created["Value"]["PlayerGuildInfo"]["PostId"], 34001001)
            self.assertEqual(created["Avatar"]["Diamond"], 4900)
            self.assertEqual(created["Avatar"]["Gold"], 1_500_000)
            # Duplicate guild name rejected (-3421)
            self.assertEqual(self._call(a2, "Guild", "CreateGuild", "ngọc tứ hồn", "")["Status"], -3421)

            # Configure auto-apply OFF, FAP limit, notice & declaration (verify GuildAvatar piggyback)
            self.assertEqual(self._call(a1, "Guild", "AlterAutoApply", 0)["Status"], 0)
            self.assertEqual(self._call(a1, "Guild", "AlterFapLimit", 100)["Status"], 0)
            upd = self._call(a1, "Guild", "UpdateNotice", "Đi Boss lúc 12h")
            self.assertEqual(upd["Status"], 0)
            self.assertEqual(upd["GuildAvatar"]["Notice"], "Đi Boss lúc 12h")
            dec = self._call(a1, "Guild", "UpdateDeclaration", "Hoan nghênh thành viên")
            self.assertEqual(dec["GuildAvatar"]["Declaration"], "Hoan nghênh thành viên")

            # Apply -> Cancel -> Reapply by a2 & a3
            ap2 = self._call(a2, "Guild", "GuildApply", gid)
            self.assertEqual(ap2["Status"], 0)
            self.assertEqual(len(ap2["Value"]["ApplyGuildListInfo"]), 1)
            self.assertEqual(self._call(a2, "Guild", "GuildCancelApply", gid)["Status"], 0)
            self.assertEqual(self._call(a2, "Guild", "GuildCancelApply", gid)["Status"], -3412)
            self.assertEqual(self._call(a2, "Guild", "GuildApply", gid)["Status"], 0)
            self.assertEqual(self._call(a3, "Guild", "GuildApply", gid)["Status"], 0)

            ap_list = self._call(a1, "Guild", "GetApplyList")
            self.assertEqual(ap_list["Status"], 0)
            self.assertEqual(ap_list["Avatar"]["RedDotInfo"]["3400"], 1)
            self.assertEqual(len(ap_list["Value"]["ApplyListInfo"]), 2)
            self.assertEqual(self._call(a1, "Guild", "ManageApply", pid2, 1)["Status"], 0)
            self.assertEqual(self._call(a1, "Guild", "ManageApply", pid3, 1)["Status"], 0)

            members = self._call(a1, "Guild", "GetGuildMembers")
            self.assertEqual(members["Status"], 0)
            self.assertEqual(len(members["Value"]["GuildMembersInfo"]), 3)

            # Promote a2 -> Vice (34001002), swap Vice a2 <-> a3, transfer Leader a1 -> a2, kick a3
            self.assertEqual(self._call(a1, "Guild", "PostChange", pid2, 34001002)["Status"], 0)
            self.assertEqual(self._call(a1, "Guild", "PostAlter", 34001002, pid2, pid3)["Status"], 0)
            self.assertEqual(self._call(a1, "Guild", "PostAssignment", pid2)["Status"], 0)
            kick = self._call(a2, "Guild", "KickOutGuild", pid3)
            self.assertEqual(kick["Status"], 0)
            a3_info = self._call(a3, "Guild", "GetGuildInfo")
            self.assertEqual(a3_info["Status"], -3425)

            # Impeach fails before 168h, succeeds after +169h offline
            emu.clock.set_fixed(base_ts + 3600)
            self.assertEqual(self._call(a1, "Guild", "GuildImpeach")["Status"], -3415)
            emu.clock.set_fixed(base_ts + 169 * 3600)
            imp = self._call(a1, "Guild", "GuildImpeach")
            self.assertEqual(imp["Status"], 0)
            self.assertEqual(imp["GuildAvatar"]["PostId"], 34001001)
            self.assertEqual(imp["Avatar"]["Diamond"], 4800)

            # Reload from disk and verify s1_guilds.json persistence
            self.assertTrue((root / "s1_guilds.json").exists())
            reloaded = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc2.log")
            reloaded.clock.set_fixed(base_ts + 169 * 3600)
            ra1 = reloaded.s1_accounts["acct_1"]
            ra2 = reloaded.s1_accounts["acct_2"]
            info_after = self._call(ra1, "Guild", "GetGuildInfo")
            self.assertEqual(info_after["Status"], 0)
            self.assertEqual(info_after["Value"]["GuildInfo"]["Name"], "Ngọc Tứ Hồn")
            self.assertEqual(info_after["Value"]["PlayerGuildInfo"]["PostId"], 34001001)

            self.assertEqual(self._call(ra2, "Guild", "ExitGuild")["Status"], 0)
            dis = self._call(ra1, "Guild", "DismissGuild")
            self.assertEqual(dis["Status"], 0)
            self.assertEqual(dis["Avatar"]["GuildId"], EMPTY_ENTITY_ID)

    def test_03_contribute_building_upgrade_build_shop_and_daily_task_15(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=35, vip_lv=4, source="test_r731")
            p.state["player"].update(Diamond=5000, Gold=2_000_000)
            p._grant_resources_from_tuples([(1605, 16050018, 25)], source="test_r731", tx_prefix="tok")

            self.assertEqual(self._call(p, "Guild", "CreateGuild", "Đạo Trường", "")["Status"], 0)
            # GuildBuild blocked at Guild Lv 1 (buildNeedGuildLv=3 -> -3449)
            self.assertEqual(self._call(p, "Guild", "GuildBuild", 34004001)["Status"], -3449)

            # Donate 25 x 16050018 (1000 each -> +25,000 Fund & Contribution)
            don = self._call(p, "Guild", "GuildContribute", 16050018, 25)
            self.assertEqual(don["Status"], 0)
            self.assertEqual(don["Avatar"]["Contribution"], 25_000)
            self.assertEqual(don["GuildAvatar"]["Fund"], 25_000)

            # Upgrade Hall (34004000) 1->2 (7,000) & 2->3 (11,000) = 18,000 -> 7,000 Fund left
            up2 = self._call(p, "Guild", "GuildBuildingLvUp", 34004000)
            self.assertEqual(up2["Status"], 0)
            self.assertEqual(up2["Value"]["Lv"], 2)
            up3 = self._call(p, "Guild", "GuildBuildingLvUp", 34004000)
            self.assertEqual(up3["Status"], 0)
            self.assertEqual(up3["Value"]["Lv"], 3)
            self.assertEqual(up3["GuildAvatar"]["BuildLv"]["34004000"], 3)

            # Upgrade Shop (34005000) 1->2 (5,000) leaves 2,000 Fund; cannot exceed Hall Lv
            shop_up = self._call(p, "Guild", "GuildBuildingLvUp", 34005000)
            self.assertEqual(shop_up["Status"], 0)
            self.assertEqual(shop_up["Value"]["Lv"], 2)
            # Give extra fund to hit Hall Lv cap (-3419) on Shop 3->4
            p._grant_resources_from_tuples([(1605, 16050018, 20)], source="test_r731", tx_prefix="tok2")
            self._call(p, "Guild", "GuildContribute", 16050018, 20)
            self.assertEqual(self._call(p, "Guild", "GuildBuildingLvUp", 34005000)["Status"], 0)
            self.assertEqual(self._call(p, "Guild", "GuildBuildingLvUp", 34005000)["Status"], -3419)

            # At Guild Lv 3, GuildBuild 34004002 succeeds, updates DailyTask #15, logs entry, blocks duplicate same day
            dt_before = self._call(p, "DailyTaskInfo", "GetDaliyTaskInfo")["Value"]
            self.assertEqual(len(dt_before["TasksInfo"]), 25)
            bld = self._call(p, "Guild", "GuildBuild", 34004002)
            self.assertEqual(bld["Status"], 0)
            self.assertGreater(bld["Avatar"]["Contribution"], 45_000)
            self.assertEqual(self._call(p, "Guild", "GuildBuild", 34004001)["Status"], -3428)

            logs = self._call(p, "Guild", "GetGuildBuildLog")
            self.assertEqual(logs["Status"], 0)
            self.assertEqual(len(logs["Value"]["GlobalGuildBuildingLog"]), 1)

            dt_after = self._call(p, "DailyTaskInfo", "GetDaliyTaskInfo")["Value"]["TasksInfo"]
            t15 = next(t for t in dt_after if int(t["Id"]) == 15)
            self.assertEqual(int(t15["Num"]), 1)
            self.assertTrue(t15["CanDrawCredit"])
            self.assertEqual(self._call(p, "DailyTaskInfo", "GetCredit", 15)["Status"], 0)

            # GuildShopBuy: 22 items; ID=2 (needBuildingLV=2, needCoin=300, perMaxNum=1) succeeds once then -3420; ID=3 -> -3419
            slist = self._call(p, "Guild", "GetGuildShopBuyList")
            self.assertEqual(slist["Status"], 0)
            self.assertEqual(len(slist["Value"]["GuildShopInfo"]), 22)
            contrib_before = int(p.state["player"]["Contribution"])
            buy2 = self._call(p, "Guild", "GuildShopBuy", 2, 1)
            self.assertEqual(buy2["Status"], 0)
            self.assertEqual(buy2["Avatar"]["Contribution"], contrib_before - 300)
            self.assertEqual(self._call(p, "Guild", "GuildShopBuy", 2, 1)["Status"], -3420)
            self.assertEqual(self._call(p, "Guild", "GuildShopBuy", 3, 1)["Status"], -3419)

    def test_04_guild_share_daily_task_10_and_ggzj_hire_type_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu.clock.set_fixed(_ts_vn(2026, 11, 17, 12, 0))
            emu.ensure_s1_account_slots(2)
            a1, a2 = emu.s1_accounts["acct_1"], emu.s1_accounts["acct_2"]
            a1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["ChuLinh", 0]})
            a2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["NguoiThue", 1]})
            non_main = self._prepare_hero_squad(a1, target_lv=40, vip_lv=4)
            self._prepare_hero_squad(a2, target_lv=40, vip_lv=4)

            tay_quoc_id = self._call(a1, "Guild", "GetApplyGuildInfo", 0)["Value"]["GuildListInfo"][0]["Id"]
            self.assertEqual(self._call(a1, "Guild", "GuildApply", tay_quoc_id)["Status"], 0)
            self.assertEqual(self._call(a2, "Guild", "GuildApply", tay_quoc_id)["Status"], 0)

            # MainHero (Slot 1, specialType=255) cannot be shared -> -3424; Slot 2 succeeds & completes DailyTask #10
            self.assertEqual(self._call(a1, "Guild", "GuildShare", 1)["Status"], -3424)
            sh = self._call(a1, "Guild", "GuildShare", 2)
            self.assertEqual(sh["Status"], 0)
            self.assertTrue(sh["Value"]["ShareId"])
            self.assertEqual(self._call(a1, "Guild", "GuildShare", 3)["Status"], -3423)

            self.assertEqual(self._call(a1, "DailyTaskInfo", "GetCredit", 10)["Status"], 0)

            pid1 = str(a1.state["player"]["PlayerId"])
            hero_mid = int(non_main["HeroModelId"])
            share_list = self._call(a2, "Guild", "GetGuildShare")
            self.assertEqual(share_list["Status"], 0)
            self.assertTrue(any(s["PlayerId"] == pid1 and int(s["HeroModelId"]) == hero_mid for s in share_list["Value"]["GuildShareInfo"]))

            # Hire via GGZJ hire_type=1 -> consumes 3x 16050016, rewards owner +1 STA, usable in GGZJ fight
            sta_before = int(a1.state["player"]["STA"])
            tok_before = self._count_goods(a2, 16050016)
            hired = self._call(a2, "GGZJ", "Hire", 1, pid1, hero_mid)
            self.assertEqual(hired["Status"], 0)
            self.assertEqual(hired["Value"]["ShareType"], 1)
            self.assertEqual(hired["Value"]["HeroModelId"], hero_mid)
            self.assertEqual(self._count_goods(a2, 16050016), tok_before - 3)
            self.assertEqual(int(a1.state["player"]["STA"]), sta_before + 1)

            pre = self._call(a2, "GGZJ", "GetFightBeforeInfo")
            self.assertEqual(pre["Status"], 0)
            fight = self._call(a2, "GGZJ", "Fight", 0, 1)
            self.assertEqual(fight["Status"], 0)

            # Daily hire cap on same shared mercenary = 5 -> 6th rejects with -3426
            for _ in range(4):
                a2.state["ggzj"]["share_type"] = 0
                self.assertEqual(self._call(a2, "GGZJ", "Hire", 1, pid1, hero_mid)["Status"], 0)
            a2.state["ggzj"]["share_type"] = 0
            self.assertEqual(self._call(a2, "GGZJ", "Hire", 1, pid1, hero_mid)["Status"], -3426)

    def test_05_teambattle_guild_player_and_guild_boss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emu = GameEmulatorState(data_dir=root, env="dev", trace_path=root / "rpc.log")
            emu.clock.set_fixed(_ts_vn(2026, 11, 17, 12, 0))
            emu.ensure_s1_account_slots(2)
            a1, a2 = emu.s1_accounts["acct_1"], emu.s1_accounts["acct_2"]
            a1.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["TeamBang1", 0]})
            a2.handle_rpc({"ModuleName": "Player", "MethodName": "NewPlayer", "Data": ["TeamBang2", 1]})
            self._prepare_hero_squad(a1, target_lv=50, vip_lv=4)
            self._prepare_hero_squad(a2, target_lv=50, vip_lv=4)

            tay_quoc_id = self._call(a1, "Guild", "GetApplyGuildInfo", 0)["Value"]["GuildListInfo"][0]["Id"]
            self.assertEqual(self._call(a1, "Guild", "GuildApply", tay_quoc_id)["Status"], 0)
            self.assertEqual(self._call(a2, "Guild", "GuildApply", tay_quoc_id)["Status"], 0)

            # Teambattle GuildPlayer discovery, peer + guild_npc invite, and Fight execution
            self.assertEqual(self._call(a1, "TeambattleInfo", "CreatTeams", 1111)["Status"], 0)
            cands = self._call(a1, "TeambattleInfo", "GetFriendsOrGuildMembers")
            self.assertEqual(cands["Status"], 0)
            guild_pids = {g["PlayerId"]: g for g in cands["Value"]["GuildPlayer"]}
            pid2 = str(a2.state["player"]["PlayerId"])
            self.assertIn(pid2, guild_pids)
            npc_gm_id = next(pid for pid in guild_pids if pid != pid2)

            self.assertEqual(self._call(a1, "TeambattleInfo", "InviteFriends", 1111, pid2)["Status"], 0)
            inv2 = self._call(a1, "TeambattleInfo", "InviteFriends", 1111, npc_gm_id)
            self.assertEqual(inv2["Status"], 0)
            self.assertEqual(len(inv2["Value"]["TeamsInfo"]), 3)
            self.assertEqual(self._call(a1, "TeambattleInfo", "Fight")["Status"], 0)

            # GuildBoss: 23:40 truce -> -3447; 12:00 active -> Inspire +20% AP, Fight x2, RankList, RedDot 3403, Reset
            emu.clock.set_fixed(_ts_vn(2026, 11, 17, 23, 40))
            self.assertEqual(self._call(a1, "GuildBossInfo", "GetFightInfo")["Status"], -3447)

            emu.clock.set_fixed(_ts_vn(2026, 11, 17, 12, 0))
            gb = self._call(a1, "GuildBossInfo", "GetGuildBoss")
            self.assertEqual(gb["Status"], 0)
            self.assertIn(gb["Value"]["PlayerGuildBossInfo"]["BossModelId"], (12015019, 12015020, 12015021))
            self.assertEqual(gb["Avatar"]["RedDotInfo"]["3403"], 1)

            fi_base = self._call(a1, "GuildBossInfo", "GetFightInfo")
            self.assertEqual(fi_base["Status"], 0)
            base_ap = next(u["AP"] for u in fi_base["Value"]["FightInfo"]["FightObjs"][0]["Heros"][:6] if u)

            ins = self._call(a1, "GuildBossInfo", "Inspire")
            self.assertEqual(ins["Status"], 0)
            self.assertEqual(ins["Value"]["InspireBuffOpenState"], 1)
            self.assertEqual(self._call(a1, "GuildBossInfo", "Inspire")["Status"], -3438)

            fi_ins = self._call(a1, "GuildBossInfo", "GetFightInfo")
            self.assertEqual(fi_ins["Status"], 0)
            ins_ap = next(u["AP"] for u in fi_ins["Value"]["FightInfo"]["FightObjs"][0]["Heros"][:6] if u)
            self.assertGreater(ins_ap, base_ap)

            f1 = self._call(a1, "GuildBossInfo", "Fight", 1, 999999999)
            self.assertEqual(f1["Status"], 0)
            self.assertGreater(f1["Value"]["HurtValue"], 0)
            self.assertGreater(f1["Avatar"]["Contribution"], 0)

            self.assertEqual(self._call(a1, "GuildBossInfo", "GetFightInfo")["Status"], 0)
            f2 = self._call(a1, "GuildBossInfo", "Fight", 1, 1000)
            self.assertEqual(f2["Status"], 0)
            self.assertEqual(f2["Avatar"]["RedDotInfo"]["3403"], 0)
            self.assertEqual(self._call(a1, "GuildBossInfo", "GetFightInfo")["Status"], -3448)

            ranks = self._call(a1, "GuildBossInfo", "GetRankList")
            self.assertEqual(ranks["Status"], 0)
            self.assertGreater(ranks["Value"]["MyRank"]["Score"], 0)
            self.assertTrue(len(ranks["Value"]["Rank"]["GuildBossGuildRank"]) >= 1)
            self.assertTrue(len(ranks["Value"]["Rank"]["GuildBossPlayerRank"]) >= 1)

            rst = self._call(a1, "GuildBossInfo", "ResetFightCount")
            self.assertEqual(rst["Status"], 0)
            self.assertEqual(rst["Value"]["FightCount"], 0)
            self.assertEqual(rst["Avatar"]["RedDotInfo"]["3403"], 1)

    def test_06_guild_reward_and_gddh_season_settlement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            emu, p = self._new_emu(tmp, ts=_ts_vn(2026, 11, 17, 12, 0))
            self._prepare_hero_squad(p, target_lv=50, vip_lv=4)

            tay_quoc_id = self._call(p, "Guild", "GetApplyGuildInfo", 0)["Value"]["GuildListInfo"][0]["Id"]
            self.assertEqual(self._call(p, "Guild", "GuildApply", tay_quoc_id)["Status"], 0)

            self.assertEqual(self._call(p, "Gddh", "ApplyGroup", 1)["Status"], 0)

            # Advance past end_reward_date (Wed 2026-11-18 23:05 UTC+7) -> settles Gddh guild reward
            emu.clock.set_fixed(_ts_vn(2026, 11, 18, 23, 5))
            rew = self._call(p, "GuildReward", "Rewars")
            self.assertEqual(rew["Status"], 0)
            self.assertTrue(len(rew["Value"]) >= 1)
            self.assertEqual(rew["Avatar"]["RedDotInfo"]["3402"], 1)
            self.assertEqual(rew["Avatar"]["RedDotInfo"]["3400"], 1)
            first_rew = rew["Value"][0]
            self.assertTrue(len(first_rew["ResourceList"]) >= 1)
            for item in first_rew["ResourceList"]:
                self.assertIn("Count", item)
                self.assertNotIn("Num", item)

            gold_before = int(p.state["player"]["Gold"])
            drawn = self._call(p, "GuildReward", "DrawGiftBags", [first_rew["Id"]])
            self.assertEqual(drawn["Status"], 0)
            self.assertGreater(drawn["Avatar"]["Gold"], gold_before)
            self.assertEqual(drawn["Avatar"]["RedDotInfo"]["3402"], 0)
            self.assertEqual(self._call(p, "GuildReward", "Rewars")["Value"], [])
            # Repeat claim fails with -3452
            self.assertEqual(self._call(p, "GuildReward", "DrawGiftBags", [first_rew["Id"]])["Status"], -3452)


if __name__ == "__main__":
    unittest.main()
