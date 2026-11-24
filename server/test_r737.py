"""Delta coverage for R7.37: Mount/Treasure multi-line debris & Red Bonds + TimedExchange + Banners 84/85/86."""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
import sys
import tempfile
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from emulator import GameEmulatorState  # noqa: E402
from event_runtime import EventRuntime  # noqa: E402

VN_TZ = _dt.timezone(_dt.timedelta(hours=7))


def _ts_vn(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(_dt.datetime(year, month, day, hour, minute, 0, tzinfo=VN_TZ).timestamp())


class R737MountBondsAndFactionBannersTest(unittest.TestCase):
    def _new_emu(self, tmpdir: str, ts: int | None = None) -> tuple[GameEmulatorState, Any]:
        root = Path(tmpdir)
        emu = GameEmulatorState(data_dir=root, env="dev", persist=True, trace_path=root / "rpc.log")
        emu.clock.set_fixed(ts if ts is not None else _ts_vn(2026, 11, 24, 12, 0))
        return emu, emu.profiles["normal"]

    @staticmethod
    def _call(target: Any, mod: str, fn: str, *args: object) -> dict:
        return target.handle_rpc({"ServerId": 1, "ModuleName": mod, "MethodName": fn, "Data": list(args)})

    def test_01_game_data_integrity_and_red_treasure_bonds(self) -> None:
        gd = json.loads((ROOT / "server" / "game_data.json").read_text(encoding="utf-8"))

        # Zero truncated "{" scalars anywhere in game_data.json
        def _has_open_brace(obj: Any) -> bool:
            if isinstance(obj, dict):
                return any(_has_open_brace(v) for v in obj.values())
            if isinstance(obj, list):
                return any(_has_open_brace(v) for v in obj)
            return obj == "{"

        self.assertFalse(_has_open_brace(gd))

        treasures = gd["treasures"]
        self.assertEqual(len(treasures), 46)
        for tid, row in treasures.items():
            self.assertIsInstance(row.get("debrisModelIds"), list, msg=f"treasure {tid} debrisModelIds")
            self.assertIsInstance(row.get("prHeroModelIds"), list, msg=f"treasure {tid} prHeroModelIds")

        # Purple/Orange/Red mounts have complete 5-6 piece debrisModelIds
        self.assertEqual(len(treasures["14021014"]["debrisModelIds"]), 5)
        self.assertEqual(len(treasures["14021615"]["debrisModelIds"]), 6)
        self.assertEqual(len(treasures["14022001"]["debrisModelIds"]), 6)
        self.assertEqual(len(treasures["14022002"]["debrisModelIds"]), 6)
        self.assertEqual(
            treasures["14022001"]["prHeroModelIds"],
            [12011002, 12011004, 12012004, 12013003, 12013005, 12015022],
        )
        self.assertEqual(
            treasures["14022002"]["prHeroModelIds"],
            [12011003, 12012003, 12012005, 12013004, 12015023],
        )

        # Canonical PrModel 573..594 & HeroPrRelation for all 11 UR heroes
        self.assertEqual(len(gd["bonds"]), 594)
        for bid in range(573, 584):
            self.assertEqual(gd["bonds"][str(bid)]["typeID"], 1401)
            self.assertEqual(gd["bonds"][str(bid)]["HPR"], 2000)
        for bid in range(584, 595):
            self.assertEqual(gd["bonds"][str(bid)]["typeID"], 1402)
            self.assertEqual(gd["bonds"][str(bid)]["APR"], 2000)

        ur_heroes = [
            12011002, 12011003, 12011004,
            12012003, 12012004, 12012005,
            12013003, 12013004, 12013005,
            12015022, 12015023,
        ]
        for hid in ur_heroes:
            hb = gd["hero_bonds"][str(hid)]
            self.assertTrue(any(573 <= int(b) <= 583 for b in hb), msg=f"hero {hid} missing red book bond")
            self.assertTrue(any(584 <= int(b) <= 594 for b in hb), msg=f"hero {hid} missing red mount bond")

        # Banner 84/85/86 art metadata
        for act_key, pic in (("84", "sy_157"), ("85", "sy_158"), ("86", "sy_159")):
            self.assertEqual(gd["timed_recruit_model"][act_key]["btnPic"], pic)
        for box_id in ("16060037", "16060038", "16060039"):
            rows = gd["goods_output"][box_id]
            self.assertEqual(len(rows), 3)
            for row in rows.values():
                self.assertTrue(str(row.get("pic", "")).startswith("xshd_"))

    def test_02_treasure_loot_one_key_and_compose_orange_and_red_mounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=50, vip_lv=4, source="test_r737")
            p.state["player"]["STA"] = 300

            # Seed 1 initial debris for 14021615 (Rồng Hai Đầu) -> OneKey loot remaining 5 & Compose
            p._grant_resources_from_tuples([(1504, 15041501, 1)], source="test_r737", tx_prefix="r737:deb:15041501")
            ok_loot = self._call(p, "TreasureLoot", "TreasureLootForOneKey", 14021615)
            self.assertEqual(ok_loot["Status"], 0)
            self.assertTrue(ok_loot["Value"]["TotalLootCount"] >= 5)

            comp_orange = self._call(p, "TreasureDebris", "TreasureDebrisCompose", 14021615)
            self.assertEqual(comp_orange["Status"], 0)
            self.assertTrue(any(int(t["TreasureModelId"]) == 14021615 for t in p.state["treasures"]))

            # Grant all 6 debris for Red Mount 14022001 (Rồng Kami) & compose directly
            red_debris = [(1504, did, 1) for did in range(15044701, 15044707)]
            p._grant_resources_from_tuples(red_debris, source="test_r737", tx_prefix="r737:reddeb")
            comp_red = self._call(p, "TreasureDebris", "TreasureDebrisCompose", 14022001)
            self.assertEqual(comp_red["Status"], 0)
            self.assertTrue(any(int(t["TreasureModelId"]) == 14022001 for t in p.state["treasures"]))

    def test_03_equipping_red_mounts_and_books_activates_bonds_and_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=60, vip_lv=5, source="test_r737")

            cases = [
                # (hero_id, slot_id, book_id, expected_book_pr, mount_id, expected_mount_pr)
                (12011002, 2, 14012001, 573, 14022001, 584),  # Inu no Taishou
                (12012005, 3, 14012002, 578, 14022002, 589),  # Sesshomaru
                (12011004, 4, 14012001, 575, 14022001, 586),  # InuYasha
                (12015022, 5, 14012002, 582, 14022001, 593),  # Tứ Đấu Thần
                (12015023, 6, 14012001, 583, 14022002, 594),  # Inu Kimi
            ]
            for hid, sid, book_id, pr_book, mount_id, pr_mount in cases:
                h_res = p._grant_resources_from_tuples([(1201, hid, 1)], source="test_r737", tx_prefix=f"r737:hero:{hid}")
                h_inst = h_res[0]["Hero"][0]["Id"]
                self.assertEqual(self._call(p, "Slot", "HeroCombat", sid, h_inst)["Status"], 0)
                slot = p.state["slots"][sid - 1]
                base_ap_rate = int(slot["Property"]["APR1"])
                base_hp_rate = int(slot["Property"]["HPR1"])
                base_fap = int(slot["Property"]["FAP"])

                tr_res = p._grant_resources_from_tuples(
                    [(1401, book_id, 1), (1402, mount_id, 1)],
                    source="test_r737",
                    tx_prefix=f"r737:tr:{hid}",
                )
                tr_list = tr_res[0]["Treasure"]
                b_inst = next(t["Id"] for t in tr_list if int(t["TreasureModelId"]) == book_id)
                m_inst = next(t["Id"] for t in tr_list if int(t["TreasureModelId"]) == mount_id)

                eq = self._call(p, "Slot", "OneKeyEquipCombat", sid, "", "", "", "", b_inst, m_inst)
                self.assertEqual(eq["Status"], 0)
                prop = p.state["slots"][sid - 1]["Property"]
                self.assertIn(pr_book, prop["ActivePrIds"])
                self.assertIn(pr_mount, prop["ActivePrIds"])
                self.assertGreaterEqual(int(prop["APR1"]), base_ap_rate + 2000)
                self.assertGreaterEqual(int(prop["HPR1"]), base_hp_rate + 2000)
                self.assertGreater(int(prop["FAP"]), base_fap)

    def test_04_timed_exchange_grants_orange_nvc_and_red_treasures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=40, vip_lv=2, source="test_r737")
            p.state["player"]["Diamond"] = 20000

            info = self._call(p, "TimedLimitExchange", "GetInfo")
            self.assertEqual(info["Status"], 0)
            serials = [int(row["Serial"]) for row in info["Value"]["ActivityList"]]
            self.assertEqual(serials, list(range(1, 31)))

            # Serial 5 -> 16060003 (800 dia), Serial 7 -> 16060036 (800 dia),
            # Serial 8 -> 14022001 (1500 dia), Serial 10 -> 14012001 (1500 dia)
            for ser, cost, check_fn in (
                (5, 800, lambda s: any(int(g["GoodsModelId"]) == 16060003 for g in s["goods"])),
                (7, 800, lambda s: any(int(g["GoodsModelId"]) == 16060036 for g in s["goods"])),
                (8, 1500, lambda s: any(int(t["TreasureModelId"]) == 14022001 for t in s["treasures"])),
                (10, 1500, lambda s: any(int(t["TreasureModelId"]) == 14012001 for t in s["treasures"])),
            ):
                before_dia = int(p.state["player"]["Diamond"])
                ex = self._call(p, "TimedLimitExchange", "Exchange", 4406, ser, 1)
                self.assertEqual(ex["Status"], 0)
                self.assertEqual(int(p.state["player"]["Diamond"]), before_dia - cost)
                self.assertTrue(check_fn(p.state), msg=f"Exchange Serial {ser} missing expected item")

    def test_05_faction_banners_84_85_86_open_pull_and_draw_gold_hero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _emu, p = self._new_emu(tmp)
            p.admin_prepare_account(target_lv=40, vip_lv=5, source="test_r737")
            p.state["player"]["Diamond"] = 50000

            for act_id in (84, 85, 86):
                self.assertIn(f"timed_recruit:{act_id}", EventRuntime.DEFAULT_CONCURRENT_EVENTS)

            init_r = self._call(p, "Player", "GetInitData")
            self.assertEqual(init_r["Status"], 0)
            tr_open_ids = [
                int(row["ActivityId"])
                for row in init_r["Avatar"]["TimedActivityOpenInfo"]["9300"]
            ]
            self.assertEqual(tr_open_ids, [81, 82, 83, 84, 85, 86])

            banner_picks = [
                (84, 12011003),  # Kikyo
                (85, 12012003),  # Kanade Hime
                (86, 12013004),  # Kaguya
            ]
            for act_id, ur_hid in banner_picks:
                sel = self._call(p, "TimedRecruitInfo", "SelectBanner", act_id)
                self.assertEqual(sel["Status"], 0)
                self.assertEqual(int(sel["Value"]["ActivityEnumId"]), act_id)
                self.assertEqual(sel["Value"]["AvailableBanners"], [81, 82, 83, 84, 85, 86])

                pull = self._call(p, "TimedRecruitInfo", "Recruit", 30, act_id)
                self.assertEqual(pull["Status"], 0)
                self.assertEqual(int(pull["Value"]["RecruitInfo"]["ActivityEnumId"]), act_id)
                self.assertEqual(int(pull["Value"]["RecruitInfo"]["MyCredit"]), 100)

                # Unlock pending UR choice box on this banner instance and claim faction UR hero
                prog = p._ensure_timed_recruit_prog(act_id, sel["Value"]["EventInstanceId"])
                prog["pending_gold_hero"] = True
                draw = self._call(
                    p,
                    "TimedRecruitInfo",
                    "DrawGoldHero",
                    ur_hid,
                    act_id,
                    sel["Value"]["EventInstanceId"],
                )
                self.assertEqual(draw["Status"], 0)
                self.assertTrue(any(int(h["HeroModelId"]) == ur_hid for h in p.state["heroes"]))

            # Verify pre-R7.37 save migration (no r737_migrated, only 81/82/83) upgrades cleanly
            ac = p.state["event_runtime"]["archive_config"]
            ac["concurrent_events"] = [
                x for x in ac["concurrent_events"]
                if x not in ("timed_recruit:84", "timed_recruit:85", "timed_recruit:86")
            ]
            ac["rotation_pool"] = ["timed_recruit:81", "timed_recruit:82", "timed_recruit:83"]
            ac.pop("r737_migrated", None)
            p.save()

            reloaded = GameEmulatorState(data_dir=Path(tmp), env="dev", persist=True, trace_path=Path(tmp) / "rpc2.log")
            reloaded.clock.set_fixed(_ts_vn(2026, 11, 24, 12, 0))
            rp = reloaded.profiles["normal"]
            b84_rel = self._call(rp, "TimedRecruitInfo", "GetTimedRecruitInfo", 84)
            self.assertEqual(b84_rel["Status"], 0)
            self.assertEqual(b84_rel["Value"]["AvailableBanners"], [81, 82, 83, 84, 85, 86])
            self.assertEqual(b84_rel["Value"]["MyCredit"], 100)


if __name__ == "__main__":
    unittest.main()
