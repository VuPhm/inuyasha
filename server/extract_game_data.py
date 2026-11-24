#!/usr/bin/env python3
"""Extract structured game config JSON from decrypted VN 5.0.4.98 (or EN 5.1.1) Lua config tables."""

import argparse
import json
import os
import re
from typing import Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VN_CONFIG_DIR = os.path.join(ROOT_DIR, "analysis", "vn", "decompiled_src", "Config")
EN_CONFIG_DIR = os.path.join(ROOT_DIR, "analysis", "decompiled", "EN_5.1.1", "src", "Config")
DEFAULT_CONFIG_DIR = VN_CONFIG_DIR if os.path.isdir(VN_CONFIG_DIR) else EN_CONFIG_DIR
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_data.json")


def _parse_lua_scalar(raw_v: str) -> Any:
    raw_v = raw_v.strip()
    if raw_v.startswith('"') and raw_v.endswith('"'):
        return raw_v[1:-1].replace('\\"', '"').replace("\\'", "'")
    if raw_v.startswith("{") and raw_v.endswith("}"):
        inner = raw_v[1:-1].strip()
        return [int(x.strip()) for x in inner.split(",") if x.strip().isdigit()] if inner else []
    if raw_v == "true":
        return True
    if raw_v == "false":
        return False
    try:
        return int(raw_v) if "." not in raw_v else float(raw_v)
    except ValueError:
        return raw_v


def _parse_fields(block: str, indent: int = 12) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    multiline_re = re.compile(
        rf"^\s{{{indent}}}([A-Za-z0-9_]+)\s*=\s*\{{\s*\n(.*?)^\s{{{indent}}}\}}(?:,\s*)?$",
        re.M | re.S,
    )
    for mm in multiline_re.finditer(block):
        obj[mm.group(1)] = [int(x) for x in re.findall(r"\d+", mm.group(2))]

    field_re = re.compile(rf"^\s{{{indent}}}([A-Za-z0-9_]+)\s*=\s*(.+?)(?:,\s*)?$", re.M)
    for fm in field_re.finditer(block):
        key = fm.group(1)
        if key in obj:
            continue
        obj[key] = _parse_lua_scalar(fm.group(2))
    return obj


def parse_simple_lua_items(path: str) -> dict[str, dict[str, Any]]:
    """Parse `ModelName = { ... items = { [id] = { k = v, ... } } }` Lua files."""
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\bitems\s*=\s*\{", text)
    if not m:
        return {}
    body = text[m.end() :]
    items: dict[str, dict[str, Any]] = {}
    block_re = re.compile(r"^\s{8}\[(\d+)\]\s*=\s*\{(.*?)^\s{8}\}", re.M | re.S)
    for bm in block_re.finditer(body):
        items[bm.group(1)] = _parse_fields(bm.group(2), indent=12)
    return items


def parse_singleton_lua_item(path: str) -> dict[str, Any]:
    """Parse `Config = { ... items = { { k = v, ... } } }` single-record Lua files."""
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\bitems\s*=\s*\{\s*\{(.*?)^\s{8}\}", text, re.M | re.S)
    if not m:
        return {}
    return _parse_fields(m.group(1), indent=12)


def parse_nested_lua_items(path: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Parse `Model = { ... items = { [k1] = { [k2] = { k = v, ... } } } }` Lua files."""
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\bitems\s*=\s*\{", text)
    if not m:
        return {}
    body = text[m.end() :]
    outer_re = re.compile(r"^\s{8}\[(\d+)\]\s*=\s*\{(.*?)^\s{8}\}", re.M | re.S)
    inner_re = re.compile(r"^\s{12}\[(\d+)\]\s*=\s*\{(.*?)^\s{12}\}", re.M | re.S)
    items: dict[str, dict[str, dict[str, Any]]] = {}
    for om in outer_re.finditer(body):
        inner_map: dict[str, dict[str, Any]] = {}
        for im in inner_re.finditer(om.group(2)):
            inner_map[im.group(1)] = _parse_fields(im.group(2), indent=16)
        items[om.group(1)] = inner_map
    return items


def parse_array_lua_items(path: str, id_key: str = "ID") -> dict[str, dict[str, Any]]:
    """Parse `Model = { ... items = { { k = v, ... }, ... } }` unindexed array Lua files."""
    if not os.path.exists(path):
        return {}
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\bitems\s*=\s*\{", text)
    if not m:
        return {}
    body = text[m.end() :]
    items: dict[str, dict[str, Any]] = {}
    block_re = re.compile(r"^\s{8}\{(.*?)^\s{8}\}", re.M | re.S)
    for idx, bm in enumerate(block_re.finditer(body)):
        fields = _parse_fields(bm.group(1), indent=12)
        key_val = fields.get(id_key, idx)
        items[str(key_val)] = fields
    return items


def parse_vip_buy_limit(path: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Parse `VipBuyLimitModel` 3-level nested `[LV][typeID][modelID]` into `{LV: {modelID: fields}}`."""
    if not os.path.exists(path):
        return {}
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\bitems\s*=\s*\{", text)
    if not m:
        return {}
    body = text[m.end() :]
    lv_re = re.compile(r"^\s{8}\[(\d+)\]\s*=\s*\{(.*?)^\s{8}\}", re.M | re.S)
    mod_re = re.compile(r"^\s{16}\[(\d+)\]\s*=\s*\{(.*?)^\s{16}\}", re.M | re.S)
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for lvm in lv_re.finditer(body):
        models: dict[str, dict[str, Any]] = {}
        for mm in mod_re.finditer(lvm.group(2)):
            models[mm.group(1)] = _parse_fields(mm.group(2), indent=20)
        out[lvm.group(1)] = models
    return out


def parse_warfare_lv(path: str) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    """Parse `WarfareLvRelation` 3-level nested `[warfareID][colorLV][LV]`."""
    if not os.path.exists(path):
        return {}
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\bitems\s*=\s*\{", text)
    if not m:
        return {}
    body = text[m.end() :]
    wf_re = re.compile(r"^\s{8}\[(\d+)\]\s*=\s*\{(.*?)^\s{8}\}", re.M | re.S)
    clv_re = re.compile(r"^\s{12}\[(\d+)\]\s*=\s*\{(.*?)^\s{12}\}", re.M | re.S)
    lv_re = re.compile(r"^\s{16}\[(\d+)\]\s*=\s*\{(.*?)^\s{16}\}", re.M | re.S)
    out: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for wfm in wf_re.finditer(body):
        clv_map: dict[str, dict[str, dict[str, Any]]] = {}
        for cm in clv_re.finditer(wfm.group(2)):
            lv_map: dict[str, dict[str, Any]] = {}
            for lm in lv_re.finditer(cm.group(2)):
                lv_map[lm.group(1)] = _parse_fields(lm.group(2), indent=20)
            clv_map[cm.group(1)] = lv_map
        out[wfm.group(1)] = clv_map
    return out


def extract_warfare_data(cfg_dir: str) -> dict[str, Any]:
    """Extract WarfareLvRelation (15x7x10) and WarfarecrestRefRelation (1575 rows)."""
    raw_ref = parse_simple_lua_items(os.path.join(cfg_dir, "WarfarecrestRefRelation.lua"))
    ref_by_crest: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(raw_ref.values(), key=lambda r: int(r.get("ID", 0))):
        cid = str(row.get("warfareCrestID", ""))
        if cid:
            ref_by_crest.setdefault(cid, []).append(row)
    return {
        "warfare_lv": parse_warfare_lv(os.path.join(cfg_dir, "WarfareLvRelation.lua")),
        "warfare_ref": ref_by_crest,
    }


def parse_array_lua_list(path: str) -> list[dict[str, Any]]:
    """Parse `Model = { ... items = { { k = v, ... }, ... } }` into a list preserving order."""
    if not os.path.exists(path):
        return []
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\bitems\s*=\s*\{", text)
    if not m:
        return []
    body = text[m.end() :]
    block_re = re.compile(r"^\s{8}\{(.*?)^\s{8}\}", re.M | re.S)
    return [_parse_fields(bm.group(1), indent=12) for bm in block_re.finditer(body)]


def extract_bdd_data(cfg_dir: str) -> dict[str, Any]:
    """Load the VN catalogue and reward tables. NPC lineups are supplied by the original server."""
    config = lambda name: os.path.join(cfg_dir, name + ".lua")
    return {
        "nodes": parse_simple_lua_items(config("BddNodeModel")),
        "points": parse_simple_lua_items(config("BddPointModel")),
        "clearance": parse_array_lua_items(config("BddClearanceModel"), "clearanceID"),
        "rewards": parse_array_lua_list(config("BddRewardStarsRelation")),
        "buffs": parse_array_lua_items(config("BddBuffShopRelation")),
        "reset": parse_simple_lua_items(config("BddResetUseRelation")),
        "merit_shop": parse_simple_lua_items(config("BddWraithShopRelation")),
        "equip_shop": parse_simple_lua_items(config("BddEquipShopRelation")),
    }


def extract_pet_data(cfg_dir: str) -> dict[str, Any]:
    """Extract PetoutTargetAttribute NPC teams grouped by targetId into a compact list."""
    raw_rows = parse_array_lua_list(os.path.join(cfg_dir, "PetoutTargetAttribute.lua"))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in raw_rows:
        tid = str(row.get("targetId", "")).strip()
        if tid:
            grouped.setdefault(tid, []).append(row)

    teams: list[dict[str, Any]] = []
    for tid, slots in grouped.items():
        slots_sorted = sorted(slots, key=lambda r: int(r.get("formation", 0)))
        total_fap = sum(int(s.get("FAP", 0)) for s in slots_sorted)
        leader = slots_sorted[0]
        compact_slots = [
            {
                "formation": int(s.get("formation", idx + 1)),
                "heroModelId": int(s.get("heroModelId", 12011001)),
                "step": int(s.get("step", 0)),
                "Lv": int(s.get("Lv", 1)),
                "HP": int(s.get("HP", 1000)),
                "AP": int(s.get("AP", 100)),
                "DEF": int(s.get("DEF", 50)),
                "FAP": int(s.get("FAP", 1000)),
                "FSP": int(s.get("FSP", 500)),
                "RP": int(s.get("RP", 50)),
                "HIT": int(s.get("HIT", 10000)),
                "DOD": int(s.get("DOD", 0)),
                "CRI": int(s.get("CRI", 0)),
                "TEN": int(s.get("TEN", 0)),
                "BLO": int(s.get("BLO", 0)),
                "BOG": int(s.get("BOG", 0)),
                "CRId": int(s.get("CRId", 0)),
                "TEND": int(s.get("TEND", 0)),
                "DAMADD": int(s.get("DAMADD", 0)),
                "DAMCUT": int(s.get("DAMCUT", 0)),
                "DAMADDR": int(s.get("DAMADDR", 0)),
                "DAMCUTR": int(s.get("DAMCUTR", 0)),
            }
            for idx, s in enumerate(slots_sorted)
        ]
        teams.append(
            {
                "targetId": tid,
                "total_fap": total_fap,
                "leader_hero_id": int(leader.get("heroModelId", 12011001)),
                "lv": max(int(s.get("Lv", 1)) for s in slots_sorted),
                "slots": compact_slots,
            }
        )
    teams.sort(key=lambda t: (t["total_fap"], t["targetId"]))
    return {"petout_targets": teams}


def parse_3level_lua_items(path: str, group_key: str) -> dict[str, list[dict[str, Any]]]:
    """Parse 3-level `[k1][k2][k3] = { ... }` tables grouped by `group_key`."""
    if not os.path.exists(path):
        return {}
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"\bitems\s*=\s*\{", text)
    if not m:
        return {}
    body = text[m.end() :]
    leaf_re = re.compile(r"^\s{16}\[\d+\]\s*=\s*\{(.*?)^\s{16}\}", re.M | re.S)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for lm in leaf_re.finditer(body):
        fields = _parse_fields(lm.group(1), indent=20)
        gk = fields.get(group_key)
        if gk is not None:
            grouped.setdefault(str(int(gk)), []).append(fields)
    return grouped


def parse_success_target_rewards(path: str) -> dict[str, list[dict[str, Any]]]:
    """Parse 3-level `SuccessTargetRewardRelation` `[targetID][sequence][appearDay]` into `{targetID: [rows...]}`."""
    by_target = parse_3level_lua_items(path, "targetID")
    for rows in by_target.values():
        rows.sort(key=lambda r: (int(r.get("appearDay", 0)), int(r.get("sequence", 0))))
    return by_target


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract InuYasha Lua config tables to game_data.json")
    parser.add_argument("--client", choices=["vn", "en"], default="vn", help="Source Lua config tree")
    args = parser.parse_args()
    cfg_dir = VN_CONFIG_DIR if args.client == "vn" and os.path.isdir(VN_CONFIG_DIR) else EN_CONFIG_DIR
    source_label = (
        "com.cmn.inuyasha v5.0.4.98 (VN)" if cfg_dir == VN_CONFIG_DIR else "com.heitao.inuyasha.guge v5.1.1 (EN)"
    )

    heroes = parse_simple_lua_items(os.path.join(cfg_dir, "HeroModel.lua"))
    attacks = parse_simple_lua_items(os.path.join(cfg_dir, "AttackModel.lua"))
    chapters = parse_simple_lua_items(os.path.join(cfg_dir, "BattleChapterModel.lua"))
    nodes = parse_simple_lua_items(os.path.join(cfg_dir, "BattleNodeModel.lua"))

    player_config = parse_singleton_lua_item(os.path.join(cfg_dir, "PlayerConfig.lua"))
    vit_config = parse_singleton_lua_item(os.path.join(cfg_dir, "VitConfig.lua"))
    sta_config = parse_singleton_lua_item(os.path.join(cfg_dir, "StaConfig.lua"))
    hero_config = parse_singleton_lua_item(os.path.join(cfg_dir, "HeroConfig.lua"))
    callequip_config = parse_singleton_lua_item(os.path.join(cfg_dir, "CallequipConfig.lua"))
    battle_config = parse_singleton_lua_item(os.path.join(cfg_dir, "BattleConfig.lua"))
    explore_config = parse_singleton_lua_item(os.path.join(cfg_dir, "ExploreConfig.lua"))

    player_lv = parse_simple_lua_items(os.path.join(cfg_dir, "PlayerLvRelation.lua"))
    hero_lv = parse_simple_lua_items(os.path.join(cfg_dir, "HeroLvRelation.lua"))
    hero_step = parse_simple_lua_items(os.path.join(cfg_dir, "HeroStepRelation.lua"))
    hero_talents = parse_nested_lua_items(os.path.join(cfg_dir, "HeroTalRelation.lua"))
    talent_models = parse_simple_lua_items(os.path.join(cfg_dir, "TalModel.lua"))
    combat_buffs = parse_simple_lua_items(os.path.join(cfg_dir, "BuffModel.lua"))
    equips = parse_simple_lua_items(os.path.join(cfg_dir, "EquipModel.lua"))
    equip_artifact = parse_simple_lua_items(os.path.join(cfg_dir, "EquipArtifactRelation.lua"))
    callequip_outodds = parse_simple_lua_items(os.path.join(cfg_dir, "CallequipOutoddsBRelation.lua"))
    equip_color = parse_simple_lua_items(os.path.join(cfg_dir, "EquipColorRelation.lua"))
    equip_lv_up = parse_nested_lua_items(os.path.join(cfg_dir, "EquipLvUpuseRelation.lua"))
    equip_group = parse_nested_lua_items(os.path.join(cfg_dir, "EquipGroupActiveRelation.lua"))

    raw_node_drops = parse_simple_lua_items(os.path.join(cfg_dir, "BattleNodeDropRelation.lua"))
    node_drops: dict[str, list[dict[str, Any]]] = {}
    for drop in raw_node_drops.values():
        nid = str(drop.get("nodeModelID", ""))
        if nid:
            node_drops.setdefault(nid, []).append(drop)
    battle_reset_use = parse_simple_lua_items(os.path.join(cfg_dir, "BattleResetUseRelation.lua"))
    attrtree_heromodel = parse_simple_lua_items(os.path.join(cfg_dir, "AttrtreeHeromodelRelation.lua"))

    raw_guide_npcs = parse_simple_lua_items(os.path.join(cfg_dir, "BattleNodeGuidenpcRelation.lua"))
    guide_npcs = {k: v for k, v in raw_guide_npcs.items() if int(v.get("heroModelID", 0)) > 0}

    road_boxes = parse_simple_lua_items(os.path.join(cfg_dir, "BattleRoadBoxRelation.lua"))
    chapter_boxes = parse_simple_lua_items(os.path.join(cfg_dir, "BattleChapterBoxRelation.lua"))
    module_subs = parse_simple_lua_items(os.path.join(cfg_dir, "ModuleSubModel.lua"))
    hero_recruit = parse_simple_lua_items(os.path.join(cfg_dir, "HeroRecruitModel.lua"))
    vip_model = parse_simple_lua_items(os.path.join(cfg_dir, "VipModel.lua"))
    attrtree_slots = parse_simple_lua_items(os.path.join(cfg_dir, "AttrtreeSlotRelation.lua"))
    attrtree = parse_array_lua_items(os.path.join(cfg_dir, "AttrtreeModel.lua"), id_key="ID")
    explore_base_awards = parse_simple_lua_items(os.path.join(cfg_dir, "ExploreBaseAwardsRelation.lua"))
    explore_reset_use = parse_simple_lua_items(os.path.join(cfg_dir, "ExploreResetUseRelation.lua"))
    explore_reward_model = parse_simple_lua_items(os.path.join(cfg_dir, "ExploreRewardModel.lua"))
    explore_reward_nums = parse_array_lua_items(os.path.join(cfg_dir, "ExploreRewardNumsRelation.lua"), id_key="ID")

    nightmare_chapters = parse_simple_lua_items(os.path.join(cfg_dir, "NightmareChapterModel.lua"))
    nightmare_nodes = parse_simple_lua_items(os.path.join(cfg_dir, "NightmareNodeModel.lua"))
    nightmare_config = parse_singleton_lua_item(os.path.join(cfg_dir, "NightmareConfig.lua"))
    nightmare_chapter_boxes = parse_simple_lua_items(os.path.join(cfg_dir, "NightmareChapterBoxRelation.lua"))
    raw_nightmare_drops = parse_simple_lua_items(os.path.join(cfg_dir, "NightmareNodeDropModel.lua"))
    nightmare_node_drops: dict[str, list[dict[str, Any]]] = {}
    for drop in raw_nightmare_drops.values():
        nid = str(drop.get("nodeModelID", ""))
        if nid:
            nightmare_node_drops.setdefault(nid, []).append(drop)
    nightmare_reset_use = parse_simple_lua_items(os.path.join(cfg_dir, "NightmareResetUseRelation.lua"))
    reborn_goods = parse_simple_lua_items(os.path.join(cfg_dir, "RebornGoodsModel.lua"))

    goods_model = parse_simple_lua_items(os.path.join(cfg_dir, "GoodsModel.lua"))
    shop_goods = parse_simple_lua_items(os.path.join(cfg_dir, "ShopGoodsModel.lua"))
    shop_goods_price = parse_nested_lua_items(os.path.join(cfg_dir, "ShopGoodsPriceRelation.lua"))
    vip_buy_limit = parse_vip_buy_limit(os.path.join(cfg_dir, "VipBuyLimitModel.lua"))
    treasures = parse_simple_lua_items(os.path.join(cfg_dir, "TreasureModel.lua"))
    treasure_debris = parse_simple_lua_items(os.path.join(cfg_dir, "TreasureDebrisModel.lua"))
    treasure_loot_config = parse_singleton_lua_item(os.path.join(cfg_dir, "TreasureLootConfig.lua"))
    elite_nodes = parse_simple_lua_items(os.path.join(cfg_dir, "ElitebattleNodeModel.lua"))
    elite_config = parse_singleton_lua_item(os.path.join(cfg_dir, "ElitebattleConfig.lua"))
    raw_elite_drops = parse_simple_lua_items(os.path.join(cfg_dir, "ElitebattleNodeDropRelation.lua"))
    elite_node_drops: dict[str, list[dict[str, Any]]] = {}
    for drop in raw_elite_drops.values():
        nid = str(drop.get("nodeModelID", ""))
        if nid:
            elite_node_drops.setdefault(nid, []).append(drop)

    luckboss_config = parse_singleton_lua_item(os.path.join(cfg_dir, "LuckbossConfig.lua"))
    luckboss_trigger = parse_singleton_lua_item(os.path.join(cfg_dir, "LuckbossTriggerRelation.lua"))
    luckboss_value_shop = parse_simple_lua_items(os.path.join(cfg_dir, "LuckbossValueShopModel.lua"))

    pvp_shop = parse_simple_lua_items(os.path.join(cfg_dir, "PvpShopModel.lua"))
    pvp_first_reward = parse_nested_lua_items(os.path.join(cfg_dir, "PvpRankFirstRewardRelation.lua"))
    pvp_rank_reward: dict[str, dict[str, dict[str, Any]]] = {}
    for step in range(1, 6):
        shard_path = os.path.join(cfg_dir, f"PvpRankRewardRelation_{step}.lua")
        if os.path.exists(shard_path):
            with open(shard_path, "r", encoding="utf-8") as sf:
                shard_txt = sf.read()
            step_rows: dict[str, dict[str, Any]] = {}
            for m in re.finditer(r"^ {4}\[(\d+)\] = \{\n(.*?)\n {4}\}", shard_txt, re.M | re.S):
                step_rows[m.group(1)] = _parse_fields(m.group(2), indent=8)
            pvp_rank_reward[str(step)] = step_rows

    daydayfund_model = parse_singleton_lua_item(os.path.join(cfg_dir, "DaydayfundModel.lua"))
    daydayfund_vip = parse_simple_lua_items(os.path.join(cfg_dir, "DaydayfundVipRelation.lua"))
    goods_output = parse_nested_lua_items(os.path.join(cfg_dir, "GoodsOutputRelation.lua"))
    fashion_model = parse_simple_lua_items(os.path.join(cfg_dir, "FashionModel.lua"))
    fashion_step = parse_nested_lua_items(os.path.join(cfg_dir, "FashionStepRelation.lua"))
    fashion_pr = parse_simple_lua_items(os.path.join(cfg_dir, "FashionPrRelation.lua"))
    hero_step_cheer = parse_simple_lua_items(os.path.join(cfg_dir, "HeroStepCheer.lua"))
    quality_model = parse_simple_lua_items(os.path.join(cfg_dir, "QualityModel.lua"))

    guide_relation = parse_nested_lua_items(os.path.join(cfg_dir, "GuideRelation.lua"))
    glory_type = parse_simple_lua_items(os.path.join(cfg_dir, "GloryTypeModel.lua"))
    glory_lv = parse_simple_lua_items(os.path.join(cfg_dir, "GloryLvRelation.lua"))
    gift_login = parse_simple_lua_items(os.path.join(cfg_dir, "GiftLoginRelation.lua"))
    gift_lv = parse_simple_lua_items(os.path.join(cfg_dir, "GiftLvRelation.lua"))
    mystery_shop_config = parse_singleton_lua_item(os.path.join(cfg_dir, "MysteryshopConfig.lua"))
    mystery_shop_fixed = parse_simple_lua_items(os.path.join(cfg_dir, "MysteryshopFixedRelation.lua"))
    mystery_shop_odds = parse_simple_lua_items(os.path.join(cfg_dir, "MysteryshopOddsPseudoRelation.lua"))

    shop_vip_gift = parse_simple_lua_items(os.path.join(cfg_dir, "ShopVipGiftModel.lua"))
    vip_slot_relation = parse_simple_lua_items(os.path.join(cfg_dir, "VipSlotRelation.lua"))
    charge_config = parse_array_lua_items(os.path.join(cfg_dir, "ChargeConfig.lua"), id_key="num")
    card_model = parse_simple_lua_items(os.path.join(cfg_dir, "CardModel.lua"))
    timed_recruit_model = parse_simple_lua_items(os.path.join(cfg_dir, "TimedRecruitModel.lua"))
    timed_recruit_credit = parse_simple_lua_items(os.path.join(cfg_dir, "TimedRecruitCreditrewardRelation.lua"))
    timed_recruit_rank = parse_3level_lua_items(os.path.join(cfg_dir, "TimedRecruitRankrewardModel.lua"), "activityEnumID")
    for rows in timed_recruit_rank.values():
        rows.sort(key=lambda r: int(r.get("rankMin", 0)))
    timed_recruit_bless = parse_simple_lua_items(os.path.join(cfg_dir, "TimedRecruitBlessoddsModel.lua"))
    timed_recruit_ratio = parse_simple_lua_items(os.path.join(cfg_dir, "TimedRecruitRatioOddsRelation.lua"))
    success_target_model = parse_simple_lua_items(os.path.join(cfg_dir, "SuccessTargetModel.lua"))
    success_target_reward = parse_success_target_rewards(os.path.join(cfg_dir, "SuccessTargetRewardRelation.lua"))
    success_time_model = parse_simple_lua_items(os.path.join(cfg_dir, "SuccessTimeModel.lua"))
    success_purchase_model = parse_nested_lua_items(os.path.join(cfg_dir, "SuccessPurchaseModel.lua"))

    dailytask_config = parse_singleton_lua_item(os.path.join(cfg_dir, "DailytaskConfig.lua"))
    dailytask_model = parse_simple_lua_items(os.path.join(cfg_dir, "DailytaskModel.lua"))
    dailytask_reward = parse_simple_lua_items(os.path.join(cfg_dir, "DailytaskRewardModel.lua"))
    dailytask_exp = parse_simple_lua_items(os.path.join(cfg_dir, "DailytaskExpRelation.lua"))

    xxbz_config = parse_singleton_lua_item(os.path.join(cfg_dir, "XxbzConfig.lua"))
    xxbz_model = parse_array_lua_items(os.path.join(cfg_dir, "XxbzModel.lua"), id_key="ID")
    xxbz_reward_base = parse_array_lua_list(os.path.join(cfg_dir, "XxbzRewardBaseRelation.lua"))
    xxbz_reward_cond = parse_array_lua_list(os.path.join(cfg_dir, "XxbzRewardConditionRelation.lua"))
    xxbz_del_cd = parse_simple_lua_items(os.path.join(cfg_dir, "XxbzDelCdRelation.lua"))

    zcsf_type = parse_simple_lua_items(os.path.join(cfg_dir, "ZcsfTypeModel.lua"))
    zcsf_use = parse_simple_lua_items(os.path.join(cfg_dir, "ZcsfUseRelation.lua"))
    limitthebounty = parse_simple_lua_items(os.path.join(cfg_dir, "LimitthebountyModel.lua"))
    timespike = parse_simple_lua_items(os.path.join(cfg_dir, "TimespikeModel.lua"))
    activeranking = parse_simple_lua_items(os.path.join(cfg_dir, "ActiverankingModel.lua"))
    opencontest_project = parse_simple_lua_items(os.path.join(cfg_dir, "OpencontestProject.lua"))
    opencontest_rank = parse_3level_lua_items(os.path.join(cfg_dir, "OpencontestRankingrewards.lua"), "days")
    shiwanyuanbao = parse_simple_lua_items(os.path.join(cfg_dir, "ShiwanyuanbaoRelation.lua"))
    share_config = parse_singleton_lua_item(os.path.join(cfg_dir, "ShareConfig.lua"))

    # Multi-Region (TW 1.4 -> VN 5.0.4.98 adapted) recovered Config tables
    xssb_model = parse_singleton_lua_item(os.path.join(cfg_dir, "XssbModel.lua"))
    critical_tasks_type = parse_simple_lua_items(os.path.join(cfg_dir, "CriticalTasksTypeRelation.lua"))
    earlytask_model = parse_simple_lua_items(os.path.join(cfg_dir, "EarlytaskModel.lua"))
    earlytask_reward = parse_nested_lua_items(os.path.join(cfg_dir, "EarlytaskRewardRelation.lua"))
    trader_config = parse_singleton_lua_item(os.path.join(cfg_dir, "TraderConfig.lua"))

    xhzw_config = parse_singleton_lua_item(os.path.join(cfg_dir, "XhzwConfig.lua"))
    xhzw_lip = parse_simple_lua_items(os.path.join(cfg_dir, "XhzwLipRelation.lua"))
    xhzw_reward = parse_simple_lua_items(os.path.join(cfg_dir, "XhzwRewardModel.lua"))
    xhzw_reward_refresh_price = parse_simple_lua_items(
        os.path.join(cfg_dir, "XhzwRewardRefreshPriceRelation.lua")
    )
    treasure_lv = parse_simple_lua_items(os.path.join(cfg_dir, "TreasureLvRelation.lua"))
    treasure_lv_active = parse_simple_lua_items(os.path.join(cfg_dir, "TreasureLvActiveRelation.lua"))
    treasure_step = parse_simple_lua_items(os.path.join(cfg_dir, "TreasureStepRelation.lua"))
    treasure_step_attr = parse_simple_lua_items(os.path.join(cfg_dir, "TreasureStepAttrRelation.lua"))
    hero_rebirth = parse_nested_lua_items(os.path.join(cfg_dir, "HeroRebirthRelation.lua"))
    equip_rebirth = parse_nested_lua_items(os.path.join(cfg_dir, "EquipRebirthRelation.lua"))
    treasure_rebirth = parse_nested_lua_items(os.path.join(cfg_dir, "TreasureRebirthRelation.lua"))
    treasure_color = parse_singleton_lua_item(os.path.join(cfg_dir, "TreasureColorModel.lua"))
    reborn_lv = parse_simple_lua_items(os.path.join(cfg_dir, "RebornLvModel.lua"))
    reborn_config = parse_singleton_lua_item(os.path.join(cfg_dir, "RebornConfig.lua"))
    reborn_lv_active = parse_simple_lua_items(os.path.join(cfg_dir, "RebornLvActiveModel.lua"))
    reborn_prtype = parse_simple_lua_items(os.path.join(cfg_dir, "RebornPrtypeRelation.lua"))
    reborn_shop_odds = parse_simple_lua_items(os.path.join(cfg_dir, "RebornShopOddsRelation.lua"))
    reborn_slots = parse_nested_lua_items(os.path.join(cfg_dir, "RebornSlotRelation.lua"))
    hero_reborn_cheer = parse_simple_lua_items(os.path.join(cfg_dir, "HeroRebornCheer.lua"))
    gem_model = parse_simple_lua_items(os.path.join(cfg_dir, "GemModel.lua"))
    leaderboard_config = parse_singleton_lua_item(os.path.join(cfg_dir, "LeaderboardConfig.lua"))
    goods_djq_model = parse_simple_lua_items(os.path.join(cfg_dir, "GoodsDjqModel.lua"))

    teambattle_config = parse_singleton_lua_item(os.path.join(cfg_dir, "TeambattleConfig.lua"))
    teambattle_nodes = parse_simple_lua_items(os.path.join(cfg_dir, "TeambattleNodeModel.lua"))
    teambattle_hold_drops = parse_simple_lua_items(os.path.join(cfg_dir, "TeambattleHoldDropoddsRelation.lua"))
    teambattle_hero_drops = parse_simple_lua_items(os.path.join(cfg_dir, "TeambattleNodeDropHeroRelation.lua"))
    teambattle_shop = parse_simple_lua_items(os.path.join(cfg_dir, "TeambattleShopModel.lua"))
    teambattle_player_npcs = parse_array_lua_list(os.path.join(cfg_dir, "TeambattlePlayerNpc.lua"))
    teambattle_hero_npcs = parse_array_lua_list(os.path.join(cfg_dir, "TeambattleHeroNpc.lua"))

    ggzj_config = parse_singleton_lua_item(os.path.join(cfg_dir, "GgzjConfig.lua"))
    ggzj_box_reward = parse_simple_lua_items(os.path.join(cfg_dir, "GgzjBoxRewardRelation.lua"))
    ggzj_reward_view = parse_simple_lua_items(os.path.join(cfg_dir, "GgzjRewardViewModel.lua"))
    ggzj_system_heroes = parse_nested_lua_items(os.path.join(cfg_dir, "GgzjSystemHeroRelation.lua"))

    gddh_config = parse_singleton_lua_item(os.path.join(cfg_dir, "GddhConfig.lua"))
    gddh_attack_reward = parse_simple_lua_items(os.path.join(cfg_dir, "GddhAttackRewardRelation.lua"))
    gddh_buynum = parse_simple_lua_items(os.path.join(cfg_dir, "GddhBuynumRelation.lua"))
    gddh_shop = parse_simple_lua_items(os.path.join(cfg_dir, "GddhShopModel.lua"))
    gddh_rank_reward = parse_3level_lua_items(os.path.join(cfg_dir, "GddhRankRewardRelation.lua"), "rewardsType")
    for rows in gddh_rank_reward.values():
        rows.sort(key=lambda r: int(r.get("rankMin", 0)))
    gddh_guild_reward = parse_3level_lua_items(os.path.join(cfg_dir, "GddhGuildrewardRelation.lua"), "rewardsType")
    for rows in gddh_guild_reward.values():
        rows.sort(key=lambda r: int(r.get("rankMin", 0)))

    guild_config = parse_singleton_lua_item(os.path.join(cfg_dir, "GuildConfig.lua"))
    guild_lv = parse_simple_lua_items(os.path.join(cfg_dir, "GuildLvRelation.lua"))
    guild_posts = parse_simple_lua_items(os.path.join(cfg_dir, "GuildPostModel.lua"))
    guild_build_types = parse_simple_lua_items(os.path.join(cfg_dir, "GuildBuildtypeModel.lua"))
    guild_buildings = parse_simple_lua_items(os.path.join(cfg_dir, "GuildBuildingModel.lua"))
    guild_building_lv = parse_nested_lua_items(os.path.join(cfg_dir, "GuildBuildingLvRelation.lua"))
    guild_shop = parse_simple_lua_items(os.path.join(cfg_dir, "GuildShopModel.lua"))
    guild_bosses = parse_simple_lua_items(os.path.join(cfg_dir, "GuildBossModel.lua"))
    guild_share = parse_simple_lua_items(os.path.join(cfg_dir, "GuildShareRelation.lua"))
    guild_donate = parse_simple_lua_items(os.path.join(cfg_dir, "GuildDonateRelation.lua"))

    lv_plan_config = parse_singleton_lua_item(os.path.join(cfg_dir, "LvPlanConfig.lua"))
    lv_plan_rewards = parse_simple_lua_items(os.path.join(cfg_dir, "LvPlanRewardModel.lua"))
    vip_welfare = parse_simple_lua_items(os.path.join(cfg_dir, "VipWelfareModel.lua"))
    bag_model = parse_simple_lua_items(os.path.join(cfg_dir, "BagModel.lua"))
    bag_expand_use = parse_simple_lua_items(os.path.join(cfg_dir, "BagExpandUseRelation.lua"))
    lianti_model = parse_simple_lua_items(os.path.join(cfg_dir, "LiantiModel.lua"))
    lianti_lv = parse_simple_lua_items(os.path.join(cfg_dir, "LiantiLvRelation.lua"))
    lianti_dashi = parse_simple_lua_items(os.path.join(cfg_dir, "LiantiDashiRelation.lua"))
    lianti_stone_exp = parse_simple_lua_items(os.path.join(cfg_dir, "LiantiLiantishiexpRelation.lua"))
    pvpinter_config = parse_singleton_lua_item(os.path.join(cfg_dir, "PvpinterConfig.lua"))
    pvpinter_lv = parse_simple_lua_items(os.path.join(cfg_dir, "PvpinterLvRelation.lua"))
    pvpinter_buynum = parse_simple_lua_items(os.path.join(cfg_dir, "PvpinterBuynumRelation.lua"))
    pvpinter_shop = parse_simple_lua_items(os.path.join(cfg_dir, "PvpinterShopModel.lua"))
    pvpinter_win_box = parse_nested_lua_items(os.path.join(cfg_dir, "PvpinterWinBoxModel.lua"))
    pvpinter_top_gamble = parse_nested_lua_items(os.path.join(cfg_dir, "PvpinterTopGamble.lua"))
    pvpinter_top_reward = parse_array_lua_list(os.path.join(cfg_dir, "PvpinterTopRewardRelation.lua"))
    pvpinter_top_worship = parse_simple_lua_items(os.path.join(cfg_dir, "PvpinterTopWorship.lua"))

    pet_config = parse_singleton_lua_item(os.path.join(cfg_dir, "PetConfig.lua"))
    pet_model = parse_simple_lua_items(os.path.join(cfg_dir, "PetModel.lua"))
    pet_lv = parse_nested_lua_items(os.path.join(cfg_dir, "PetLvRelation.lua"))
    pet_skill = parse_simple_lua_items(os.path.join(cfg_dir, "PetSkillModel.lua"))
    pet_new_skillrange = parse_simple_lua_items(os.path.join(cfg_dir, "PetNewSkillrangeModel.lua"))
    pet_rebirth = parse_nested_lua_items(os.path.join(cfg_dir, "PetRebirthRelation.lua"))
    petout_config = parse_singleton_lua_item(os.path.join(cfg_dir, "PetoutConfig.lua"))
    petout_nodes = parse_simple_lua_items(os.path.join(cfg_dir, "PetoutNodeModel.lua"))
    petout_boxes = parse_simple_lua_items(os.path.join(cfg_dir, "PetoutBoxModel.lua"))
    petout_buybox = parse_nested_lua_items(os.path.join(cfg_dir, "PetoutBuyboxRelation.lua"))
    petout_buystep = parse_simple_lua_items(os.path.join(cfg_dir, "PetoutBuystepUseRelation.lua"))
    petout_rank_per = parse_nested_lua_items(os.path.join(cfg_dir, "PetoutRankperRewardRelation.lua"))
    petout_rank_guild = parse_nested_lua_items(os.path.join(cfg_dir, "PetoutRankguildRewardRelation.lua"))
    petout_shop = parse_simple_lua_items(os.path.join(cfg_dir, "PetoutShopRelation.lua"))

    warfare_model = parse_simple_lua_items(os.path.join(cfg_dir, "WarfareModel.lua"))
    warfarespirit_model = parse_simple_lua_items(os.path.join(cfg_dir, "WarfarespiritModel.lua"))
    warfarespirit_lv = parse_nested_lua_items(os.path.join(cfg_dir, "WarfarespiritLvRelation.lua"))
    warfare_collocation = parse_nested_lua_items(os.path.join(cfg_dir, "WarfarecrestCollocation.lua"))
    warfare_droppreview = parse_simple_lua_items(os.path.join(cfg_dir, "WarfarecrestDroppreview.lua"))

    hero_bonds = {
        hero: [relations[order]["PRModelId"] for order in sorted(relations, key=int)]
        for hero, relations in parse_nested_lua_items(os.path.join(cfg_dir, "HeroPrRelation.lua")).items()
    }
    bonds = parse_simple_lua_items(os.path.join(cfg_dir, "PrModel.lua"))

    # R7.37: Canonical Red Book (14012001/02) & Red Mount (14022001/02) PrModel + Banner 84-86 UI assets
    if cfg_dir == VN_CONFIG_DIR:
        r737_red_bonds: list[tuple[int, int, int, int, str, int, int]] = [
            # (bond_id, hero_id, type_id, treasure_id, name, apr, hpr)
            (573, 12011002, 1401, 14012001, "Quyển Kami", 0, 2000),
            (574, 12011003, 1401, 14012002, "Quyển Tứ Hồn", 0, 2000),
            (575, 12011004, 1401, 14012001, "Quyển Kami", 0, 2000),
            (576, 12012003, 1401, 14012002, "Quyển Tứ Hồn", 0, 2000),
            (577, 12012004, 1401, 14012001, "Quyển Kami", 0, 2000),
            (578, 12012005, 1401, 14012002, "Quyển Tứ Hồn", 0, 2000),
            (579, 12013003, 1401, 14012001, "Quyển Kami", 0, 2000),
            (580, 12013004, 1401, 14012002, "Quyển Tứ Hồn", 0, 2000),
            (581, 12013005, 1401, 14012001, "Quyển Kami", 0, 2000),
            (582, 12015022, 1401, 14012002, "Quyển Tứ Hồn", 0, 2000),
            (583, 12015023, 1401, 14012001, "Quyển Kami", 0, 2000),
            (584, 12011002, 1402, 14022001, "Rồng Kami", 2000, 0),
            (585, 12011003, 1402, 14022002, "Phượng Hoàng Kami", 2000, 0),
            (586, 12011004, 1402, 14022001, "Rồng Kami", 2000, 0),
            (587, 12012003, 1402, 14022002, "Phượng Hoàng Kami", 2000, 0),
            (588, 12012004, 1402, 14022001, "Rồng Kami", 2000, 0),
            (589, 12012005, 1402, 14022002, "Phượng Hoàng Kami", 2000, 0),
            (590, 12013003, 1402, 14022001, "Rồng Kami", 2000, 0),
            (591, 12013004, 1402, 14022002, "Phượng Hoàng Kami", 2000, 0),
            (592, 12013005, 1402, 14022001, "Rồng Kami", 2000, 0),
            (593, 12015022, 1402, 14022001, "Rồng Kami", 2000, 0),
            (594, 12015023, 1402, 14022002, "Phượng Hoàng Kami", 2000, 0),
        ]
        for bond_id, hero_id, type_id, tr_id, tr_name, apr, hpr in r737_red_bonds:
            intro = f"Cùng {tr_name} ra trận,Công+20%" if apr else f"Cùng {tr_name} ra trận,HP+20%"
            bonds[str(bond_id)] = {
                "ID": bond_id,
                "name": tr_name,
                "intro": intro,
                "member": str(tr_id),
                "typeID": type_id,
                "APR": apr,
                "HPR": hpr,
                "DEFR": 0,
            }
            h_list = hero_bonds.setdefault(str(hero_id), [])
            if bond_id not in h_list:
                h_list.append(bond_id)

        red_pr_heroes = {
            "14012001": [12011002, 12011004, 12012004, 12013003, 12013005, 12015023],
            "14012002": [12011003, 12012003, 12012005, 12013004, 12015022],
            "14022001": [12011002, 12011004, 12012004, 12013003, 12013005, 12015022],
            "14022002": [12011003, 12012003, 12012005, 12013004, 12015023],
        }
        for tr_key, hero_list in red_pr_heroes.items():
            if tr_key in treasures:
                treasures[tr_key]["prHeroModelIds"] = hero_list

        for act_key, pic_name in (("84", "sy_157"), ("85", "sy_158"), ("86", "sy_159")):
            if act_key in timed_recruit_model:
                timed_recruit_model[act_key]["btnPic"] = pic_name

        b84_86_pics = {
            ("16060037", "1"): "xshd_101",
            ("16060037", "2"): "xshd_117",
            ("16060037", "3"): "xshd_100",
            ("16060038", "1"): "xshd_118",
            ("16060038", "2"): "xshd_103",
            ("16060038", "3"): "xshd_98",
            ("16060039", "1"): "xshd_102",
            ("16060039", "2"): "xshd_119",
            ("16060039", "3"): "xshd_99",
        }
        for (box_id, row_id), pic_name in b84_86_pics.items():
            if box_id in goods_output and row_id in goods_output[box_id]:
                goods_output[box_id][row_id]["pic"] = pic_name

        # R7.39: Enable Lianti (ModuleSub 5700) & expose canonical VN Lianti stones (16050035..16050038) in ShopGoods
        if "5700" in module_subs:
            module_subs["5700"]["ifOpen"] = 1
        # R8.5: Enable Pet & PetOut modules (1414, 7400..7406, 7500, 7600)
        for pet_mod in ("1414", "7400", "7401", "7402", "7403", "7404", "7405", "7406", "7500", "7600"):
            if pet_mod in module_subs:
                module_subs[pet_mod]["ifOpen"] = 1
        # R8.6: Enable Warfare & Warfarespirit modules (8101..8108)
        for wf_mod in ("8101", "8102", "8103", "8104", "8105", "8106", "8107", "8108"):
            if wf_mod in module_subs:
                module_subs[wf_mod]["ifOpen"] = 1
        r739_lianti_shop = [
            (7, 16050035, 10),
            (8, 16050036, 25),
            (9, 16050037, 60),
            (10, 16050038, 200),
        ]
        for sid, gid, price in r739_lianti_shop:
            if str(sid) not in shop_goods:
                shop_goods[str(sid)] = {
                    "ID": sid,
                    "serverGroupID": 0,
                    "goodsModelID": gid,
                    "sellTypeID": 1111,
                    "initPrice": price,
                    "currPrice": price,
                    "ifVipLimitBuy": False,
                    "ifOnceUse": False,
                    "ifDynamicPrice": False,
                    "needLV": 34,
                }

        # R7.40: VN VipModel.lua sets buyKuafuNum=0 for every VIP level; enable canonical vip+3 cap
        for v_key, v_row in vip_model.items():
            if int(v_row.get("buyKuafuNum", 0) or 0) <= 0:
                v_row["buyKuafuNum"] = int(v_key) + 3

    data = {
        "source": source_label,
        "counts": {
            "heroes": len(heroes),
            "attacks": len(attacks),
            "chapters": len(chapters),
            "nodes": len(nodes),
            "equips": len(equips),
            "equip_artifact": len(equip_artifact),
            "callequip_outodds": len(callequip_outodds),
            "player_lv": len(player_lv),
            "hero_lv": len(hero_lv),
            "hero_step": len(hero_step),
            "node_drops": sum(len(v) for v in node_drops.values()),
            "battle_reset_use": len(battle_reset_use),
            "attrtree_heromodel": len(attrtree_heromodel),
            "guide_npcs": len(guide_npcs),
            "road_boxes": len(road_boxes),
            "chapter_boxes": len(chapter_boxes),
            "module_subs": len(module_subs),
            "vip_model": len(vip_model),
            "attrtree": len(attrtree),
            "nightmare_chapters": len(nightmare_chapters),
            "nightmare_nodes": len(nightmare_nodes),
            "nightmare_chapter_boxes": len(nightmare_chapter_boxes),
            "nightmare_node_drops": sum(len(v) for v in nightmare_node_drops.values()),
            "nightmare_reset_use": len(nightmare_reset_use),
            "reborn_goods": len(reborn_goods),
            "goods_model": len(goods_model),
            "shop_goods": len(shop_goods),
            "treasures": len(treasures),
            "treasure_debris": len(treasure_debris),
            "elite_nodes": len(elite_nodes),
            "elite_node_drops": sum(len(v) for v in elite_node_drops.values()),
            "luckboss_value_shop": len(luckboss_value_shop),
            "pvp_shop": len(pvp_shop),
            "pvp_first_reward": sum(len(v) for v in pvp_first_reward.values()),
            "pvp_rank_reward": sum(len(v) for v in pvp_rank_reward.values()),
            "daydayfund_vip": len(daydayfund_vip),
            "goods_output": len(goods_output),
            "fashion_model": len(fashion_model),
            "fashion_pr": len(fashion_pr),
            "hero_step_cheer": len(hero_step_cheer),
            "quality_model": len(quality_model),
            "guide_relation": len(guide_relation),
            "glory_type": len(glory_type),
            "glory_lv": len(glory_lv),
            "gift_login": len(gift_login),
            "gift_lv": len(gift_lv),
            "mystery_shop_fixed": len(mystery_shop_fixed),
            "mystery_shop_odds": len(mystery_shop_odds),
            "shop_vip_gift": len(shop_vip_gift),
            "vip_slot_relation": len(vip_slot_relation),
            "charge_config": len(charge_config),
            "card_model": len(card_model),
            "timed_recruit_model": len(timed_recruit_model),
            "timed_recruit_credit": len(timed_recruit_credit),
            "timed_recruit_rank": sum(len(v) for v in timed_recruit_rank.values()),
            "timed_recruit_bless": len(timed_recruit_bless),
            "timed_recruit_ratio": len(timed_recruit_ratio),
            "success_target_model": len(success_target_model),
            "success_target_reward": sum(len(v) for v in success_target_reward.values()),
            "success_time_model": len(success_time_model),
            "success_purchase_model": sum(len(v) for v in success_purchase_model.values()),
            "dailytask_model": len(dailytask_model),
            "dailytask_reward": len(dailytask_reward),
            "dailytask_exp": len(dailytask_exp),
            "xxbz_model": len(xxbz_model),
            "xxbz_reward_base": len(xxbz_reward_base),
            "xxbz_reward_cond": len(xxbz_reward_cond),
            "xxbz_del_cd": len(xxbz_del_cd),
            "zcsf_type": len(zcsf_type),
            "zcsf_use": len(zcsf_use),
            "limitthebounty": len(limitthebounty),
            "timespike": len(timespike),
            "activeranking": len(activeranking),
            "opencontest_project": len(opencontest_project),
            "opencontest_rank": sum(len(v) for v in opencontest_rank.values()),
            "shiwanyuanbao": len(shiwanyuanbao),
            "xssb_model": 1 if xssb_model else 0,
            "critical_tasks_type": len(critical_tasks_type),
            "earlytask_model": len(earlytask_model),
            "earlytask_reward": sum(len(v) for v in earlytask_reward.values()),
            "trader_config": 1 if trader_config else 0,
            "xhzw_lip": len(xhzw_lip),
            "xhzw_reward": len(xhzw_reward),
            "xhzw_reward_refresh_price": len(xhzw_reward_refresh_price),
            "treasure_lv": len(treasure_lv),
            "treasure_lv_active": len(treasure_lv_active),
            "treasure_step": len(treasure_step),
            "treasure_step_attr": len(treasure_step_attr),
            "hero_rebirth": sum(len(v) for v in hero_rebirth.values()),
            "equip_rebirth": sum(len(v) for v in equip_rebirth.values()),
            "treasure_rebirth": sum(len(v) for v in treasure_rebirth.values()),
            "reborn_lv": len(reborn_lv),
            "reborn_lv_active": len(reborn_lv_active),
            "reborn_prtype": len(reborn_prtype),
            "reborn_shop_odds": len(reborn_shop_odds),
            "reborn_slots": len(reborn_slots),
            "hero_reborn_cheer": len(hero_reborn_cheer),
            "gem_model": len(gem_model),
            "goods_djq_model": len(goods_djq_model),
            "teambattle_nodes": len(teambattle_nodes),
            "teambattle_hold_drops": len(teambattle_hold_drops),
            "teambattle_hero_drops": len(teambattle_hero_drops),
            "teambattle_shop": len(teambattle_shop),
            "teambattle_player_npcs": len(teambattle_player_npcs),
            "teambattle_hero_npcs": len(teambattle_hero_npcs),
            "ggzj_box_reward": len(ggzj_box_reward),
            "ggzj_reward_view": len(ggzj_reward_view),
            "ggzj_system_heroes": sum(len(v) for v in ggzj_system_heroes.values()),
            "gddh_attack_reward": len(gddh_attack_reward),
            "gddh_buynum": len(gddh_buynum),
            "gddh_shop": len(gddh_shop),
            "gddh_rank_reward": sum(len(v) for v in gddh_rank_reward.values()),
            "gddh_guild_reward": sum(len(v) for v in gddh_guild_reward.values()),
            "guild_lv": len(guild_lv),
            "guild_posts": len(guild_posts),
            "guild_build_types": len(guild_build_types),
            "guild_buildings": len(guild_buildings),
            "guild_building_lv": sum(len(v) for v in guild_building_lv.values()),
            "guild_shop": len(guild_shop),
            "guild_bosses": len(guild_bosses),
            "guild_share": len(guild_share),
            "guild_donate": len(guild_donate),
            "lv_plan_rewards": len(lv_plan_rewards),
            "vip_welfare": len(vip_welfare),
            "bag_model": len(bag_model),
            "bag_expand_use": len(bag_expand_use),
            "lianti_model": len(lianti_model),
            "lianti_lv": len(lianti_lv),
            "lianti_dashi": len(lianti_dashi),
            "lianti_stone_exp": len(lianti_stone_exp),
            "pvpinter_lv": len(pvpinter_lv),
            "pvpinter_buynum": len(pvpinter_buynum),
            "pvpinter_shop": len(pvpinter_shop),
            "pvpinter_win_box": sum(len(v) for v in pvpinter_win_box.values()),
            "pvpinter_top_gamble": sum(len(v) for v in pvpinter_top_gamble.values()),
            "pvpinter_top_reward": len(pvpinter_top_reward),
            "pvpinter_top_worship": len(pvpinter_top_worship),
            "pet_model": len(pet_model),
            "pet_lv": len(pet_lv),
            "pet_skill": len(pet_skill),
            "pet_new_skillrange": len(pet_new_skillrange),
            "pet_rebirth": sum(len(v) for v in pet_rebirth.values()),
            "petout_nodes": len(petout_nodes),
            "petout_boxes": len(petout_boxes),
            "petout_buybox": sum(len(v) for v in petout_buybox.values()),
            "petout_buystep": len(petout_buystep),
            "petout_rank_per": len(petout_rank_per),
            "petout_rank_guild": len(petout_rank_guild),
            "petout_shop": len(petout_shop),
            "warfare_model": len(warfare_model),
            "warfarespirit_model": len(warfarespirit_model),
            "warfarespirit_lv": sum(len(v) for v in warfarespirit_lv.values()),
            "warfare_collocation": sum(len(v) for v in warfare_collocation.values()),
            "warfare_droppreview": len(warfare_droppreview),
        },
        "player_config": player_config,
        "vit_config": vit_config,
        "sta_config": sta_config,
        "hero_config": hero_config,
        "callequip_config": callequip_config,
        "battle_config": battle_config,
        "explore_config": explore_config,
        "treasure_loot_config": treasure_loot_config,
        "elite_config": elite_config,
        "luckboss_config": luckboss_config,
        "luckboss_trigger": luckboss_trigger,
        "luckboss_value_shop": luckboss_value_shop,
        "player_lv": player_lv,
        "hero_lv": hero_lv,
        "hero_step": hero_step,
        "hero_talents": hero_talents,
        "talent_models": talent_models,
        "combat_buffs": combat_buffs,
        "heroes": heroes,
        "hero_bonds": hero_bonds,
        "bonds": bonds,
        "attacks": attacks,
        "chapters": chapters,
        "nodes": nodes,
        "guide_npcs": guide_npcs,
        "equips": equips,
        "equip_artifact": equip_artifact,
        "callequip_outodds": callequip_outodds,
        "equip_steps": parse_nested_lua_items(os.path.join(cfg_dir, "EquipStepRelation.lua"))
        if os.path.exists(os.path.join(cfg_dir, "EquipStepRelation.lua")) else {},
        "equip_color": equip_color,
        "equip_lv_up": equip_lv_up,
        "equip_group": equip_group,
        "node_drops": node_drops,
        "road_boxes": road_boxes,
        "chapter_boxes": chapter_boxes,
        "module_subs": module_subs,
        "hero_recruit": hero_recruit,
        "vip_model": vip_model,
        "attrtree_slots": attrtree_slots,
        "attrtree": attrtree,
        "explore_base_awards": explore_base_awards,
        "explore_reset_use": explore_reset_use,
        "explore_reward_model": explore_reward_model,
        "explore_reward_nums": explore_reward_nums,
        "nightmare_chapters": nightmare_chapters,
        "nightmare_nodes": nightmare_nodes,
        "nightmare_config": nightmare_config,
        "nightmare_chapter_boxes": nightmare_chapter_boxes,
        "nightmare_node_drops": nightmare_node_drops,
        "nightmare_reset_use": nightmare_reset_use,
        "reborn_goods": reborn_goods,
        "goods_model": goods_model,
        "shop_goods": shop_goods,
        "shop_goods_price": shop_goods_price,
        "vip_buy_limit": vip_buy_limit,
        "treasures": treasures,
        "treasure_debris": treasure_debris,
        "elite_nodes": elite_nodes,
        "elite_node_drops": elite_node_drops,
        "battle_reset_use": battle_reset_use,
        "attrtree_heromodel": attrtree_heromodel,
        "pvp_shop": pvp_shop,
        "pvp_first_reward": pvp_first_reward,
        "pvp_rank_reward": pvp_rank_reward,
        "daydayfund_model": daydayfund_model,
        "daydayfund_vip": daydayfund_vip,
        "goods_output": goods_output,
        "fashion_model": fashion_model,
        "fashion_step": fashion_step,
        "fashion_pr": fashion_pr,
        "hero_step_cheer": hero_step_cheer,
        "quality_model": quality_model,
        "guide_relation": guide_relation,
        "glory_type": glory_type,
        "glory_lv": glory_lv,
        "gift_login": gift_login,
        "gift_lv": gift_lv,
        "mystery_shop_config": mystery_shop_config,
        "mystery_shop_fixed": mystery_shop_fixed,
        "mystery_shop_odds": mystery_shop_odds,
        "shop_vip_gift": shop_vip_gift,
        "vip_slot_relation": vip_slot_relation,
        "charge_config": charge_config,
        "card_model": card_model,
        "timed_recruit_model": timed_recruit_model,
        "timed_recruit_credit": timed_recruit_credit,
        "timed_recruit_rank": timed_recruit_rank,
        "timed_recruit_bless": timed_recruit_bless,
        "timed_recruit_ratio": timed_recruit_ratio,
        "success_target_model": success_target_model,
        "success_target_reward": success_target_reward,
        "success_time_model": success_time_model,
        "success_purchase_model": success_purchase_model,
        "dailytask_config": dailytask_config,
        "dailytask_model": dailytask_model,
        "dailytask_reward": dailytask_reward,
        "dailytask_exp": dailytask_exp,
        "xxbz_config": xxbz_config,
        "xxbz_model": xxbz_model,
        "xxbz_reward_base": xxbz_reward_base,
        "xxbz_reward_cond": xxbz_reward_cond,
        "xxbz_del_cd": xxbz_del_cd,
        "zcsf_type": zcsf_type,
        "zcsf_use": zcsf_use,
        "limitthebounty": limitthebounty,
        "timespike": timespike,
        "activeranking": activeranking,
        "opencontest_project": opencontest_project,
        "opencontest_rank": opencontest_rank,
        "shiwanyuanbao": shiwanyuanbao,
        "share_config": share_config,
        "xssb_model": xssb_model,
        "critical_tasks_type": critical_tasks_type,
        "earlytask_model": earlytask_model,
        "earlytask_reward": earlytask_reward,
        "trader_config": trader_config,
        "xhzw_config": xhzw_config,
        "xhzw_lip": xhzw_lip,
        "xhzw_reward": xhzw_reward,
        "xhzw_reward_refresh_price": xhzw_reward_refresh_price,
        "treasure_lv": treasure_lv,
        "treasure_lv_active": treasure_lv_active,
        "treasure_step": treasure_step,
        "treasure_step_attr": treasure_step_attr,
        "hero_rebirth": hero_rebirth,
        "equip_rebirth": equip_rebirth,
        "treasure_rebirth": treasure_rebirth,
        "treasure_color": treasure_color,
        "reborn_lv": reborn_lv,
        "reborn_config": reborn_config,
        "reborn_lv_active": reborn_lv_active,
        "reborn_prtype": reborn_prtype,
        "reborn_shop_odds": reborn_shop_odds,
        "reborn_slots": reborn_slots,
        "hero_reborn_cheer": hero_reborn_cheer,
        "gem_model": gem_model,
        "leaderboard_config": leaderboard_config,
        "goods_djq_model": goods_djq_model,
        "teambattle_config": teambattle_config,
        "teambattle_nodes": teambattle_nodes,
        "teambattle_hold_drops": teambattle_hold_drops,
        "teambattle_hero_drops": teambattle_hero_drops,
        "teambattle_shop": teambattle_shop,
        "teambattle_player_npcs": teambattle_player_npcs,
        "teambattle_hero_npcs": teambattle_hero_npcs,
        "ggzj_config": ggzj_config,
        "ggzj_box_reward": ggzj_box_reward,
        "ggzj_reward_view": ggzj_reward_view,
        "ggzj_system_heroes": ggzj_system_heroes,
        "gddh_config": gddh_config,
        "gddh_attack_reward": gddh_attack_reward,
        "gddh_buynum": gddh_buynum,
        "gddh_shop": gddh_shop,
        "gddh_rank_reward": gddh_rank_reward,
        "gddh_guild_reward": gddh_guild_reward,
        "guild_config": guild_config,
        "guild_lv": guild_lv,
        "guild_posts": guild_posts,
        "guild_build_types": guild_build_types,
        "guild_buildings": guild_buildings,
        "guild_building_lv": guild_building_lv,
        "guild_shop": guild_shop,
        "guild_bosses": guild_bosses,
        "guild_share": guild_share,
        "guild_donate": guild_donate,
        "lv_plan_config": lv_plan_config,
        "lv_plan_rewards": lv_plan_rewards,
        "vip_welfare": vip_welfare,
        "bag_model": bag_model,
        "bag_expand_use": bag_expand_use,
        "lianti_model": lianti_model,
        "lianti_lv": lianti_lv,
        "lianti_dashi": lianti_dashi,
        "lianti_stone_exp": lianti_stone_exp,
        "pvpinter_config": pvpinter_config,
        "pvpinter_lv": pvpinter_lv,
        "pvpinter_buynum": pvpinter_buynum,
        "pvpinter_shop": pvpinter_shop,
        "pvpinter_win_box": pvpinter_win_box,
        "pvpinter_top_gamble": pvpinter_top_gamble,
        "pvpinter_top_reward": pvpinter_top_reward,
        "pvpinter_top_worship": pvpinter_top_worship,
        "pet_config": pet_config,
        "pet_model": pet_model,
        "pet_lv": pet_lv,
        "pet_skill": pet_skill,
        "pet_new_skillrange": pet_new_skillrange,
        "pet_rebirth": pet_rebirth,
        "petout_config": petout_config,
        "petout_nodes": petout_nodes,
        "petout_boxes": petout_boxes,
        "petout_buybox": petout_buybox,
        "petout_buystep": petout_buystep,
        "petout_rank_per": petout_rank_per,
        "petout_rank_guild": petout_rank_guild,
        "petout_shop": petout_shop,
        "warfare_model": warfare_model,
        "warfarespirit_model": warfarespirit_model,
        "warfarespirit_lv": warfarespirit_lv,
        "warfare_collocation": warfare_collocation,
        "warfare_droppreview": warfare_droppreview,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_PATH}: {data['counts']}")
    with open(os.path.join(os.path.dirname(OUT_PATH), "bdd_data.json"), "w", encoding="utf-8") as f:
        json.dump(extract_bdd_data(cfg_dir), f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(os.path.dirname(OUT_PATH), "pet_data.json"), "w", encoding="utf-8") as f:
        json.dump(extract_pet_data(cfg_dir), f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(os.path.dirname(OUT_PATH), "warfare_data.json"), "w", encoding="utf-8") as f:
        json.dump(extract_warfare_data(cfg_dir), f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
