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
    field_re = re.compile(rf"^\s{{{indent}}}([A-Za-z0-9_]+)\s*=\s*(.+?)(?:,\s*)?$", re.M)
    obj: dict[str, Any] = {}
    for fm in field_re.finditer(block):
        obj[fm.group(1)] = _parse_lua_scalar(fm.group(2))
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
    equip_color = parse_simple_lua_items(os.path.join(cfg_dir, "EquipColorRelation.lua"))
    equip_lv_up = parse_nested_lua_items(os.path.join(cfg_dir, "EquipLvUpuseRelation.lua"))
    equip_group = parse_nested_lua_items(os.path.join(cfg_dir, "EquipGroupActiveRelation.lua"))

    raw_node_drops = parse_simple_lua_items(os.path.join(cfg_dir, "BattleNodeDropRelation.lua"))
    node_drops: dict[str, list[dict[str, Any]]] = {}
    for drop in raw_node_drops.values():
        nid = str(drop.get("nodeModelID", ""))
        if nid:
            node_drops.setdefault(nid, []).append(drop)

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

    goods_model = parse_simple_lua_items(os.path.join(cfg_dir, "GoodsModel.lua"))
    shop_goods = parse_simple_lua_items(os.path.join(cfg_dir, "ShopGoodsModel.lua"))
    shop_goods_price = parse_nested_lua_items(os.path.join(cfg_dir, "ShopGoodsPriceRelation.lua"))
    vip_buy_limit = parse_vip_buy_limit(os.path.join(cfg_dir, "VipBuyLimitModel.lua"))
    treasures = parse_simple_lua_items(os.path.join(cfg_dir, "TreasureModel.lua"))
    treasure_debris = parse_simple_lua_items(os.path.join(cfg_dir, "TreasureDebrisModel.lua"))
    treasure_loot_config = parse_singleton_lua_item(os.path.join(cfg_dir, "TreasureLootConfig.lua"))
    elite_nodes = parse_simple_lua_items(os.path.join(cfg_dir, "ElitebattleNodeModel.lua"))
    elite_config = parse_singleton_lua_item(os.path.join(cfg_dir, "ElitebattleConfig.lua"))

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
    reborn_lv = parse_simple_lua_items(os.path.join(cfg_dir, "RebornLvModel.lua"))

    data = {
        "source": source_label,
        "counts": {
            "heroes": len(heroes),
            "attacks": len(attacks),
            "chapters": len(chapters),
            "nodes": len(nodes),
            "equips": len(equips),
            "player_lv": len(player_lv),
            "hero_lv": len(hero_lv),
            "hero_step": len(hero_step),
            "node_drops": sum(len(v) for v in node_drops.values()),
            "guide_npcs": len(guide_npcs),
            "road_boxes": len(road_boxes),
            "chapter_boxes": len(chapter_boxes),
            "module_subs": len(module_subs),
            "vip_model": len(vip_model),
            "attrtree": len(attrtree),
            "nightmare_chapters": len(nightmare_chapters),
            "nightmare_nodes": len(nightmare_nodes),
            "goods_model": len(goods_model),
            "shop_goods": len(shop_goods),
            "treasures": len(treasures),
            "treasure_debris": len(treasure_debris),
            "elite_nodes": len(elite_nodes),
            "luckboss_value_shop": len(luckboss_value_shop),
            "pvp_shop": len(pvp_shop),
            "pvp_first_reward": sum(len(v) for v in pvp_first_reward.values()),
            "pvp_rank_reward": sum(len(v) for v in pvp_rank_reward.values()),
            "daydayfund_vip": len(daydayfund_vip),
            "goods_output": len(goods_output),
            "fashion_model": len(fashion_model),
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
        "hero_bonds": {
            hero: [relations[order]["PRModelId"] for order in sorted(relations, key=int)]
            for hero, relations in parse_nested_lua_items(os.path.join(cfg_dir, "HeroPrRelation.lua")).items()
        },
        "bonds": parse_simple_lua_items(os.path.join(cfg_dir, "PrModel.lua")),
        "attacks": attacks,
        "chapters": chapters,
        "nodes": nodes,
        "guide_npcs": guide_npcs,
        "equips": equips,
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
        "goods_model": goods_model,
        "shop_goods": shop_goods,
        "shop_goods_price": shop_goods_price,
        "vip_buy_limit": vip_buy_limit,
        "treasures": treasures,
        "treasure_debris": treasure_debris,
        "elite_nodes": elite_nodes,
        "pvp_shop": pvp_shop,
        "pvp_first_reward": pvp_first_reward,
        "pvp_rank_reward": pvp_rank_reward,
        "daydayfund_model": daydayfund_model,
        "daydayfund_vip": daydayfund_vip,
        "goods_output": goods_output,
        "fashion_model": fashion_model,
        "fashion_step": fashion_step,
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
        "reborn_lv": reborn_lv,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_PATH}: {data['counts']}")
    with open(os.path.join(os.path.dirname(OUT_PATH), "bdd_data.json"), "w", encoding="utf-8") as f:
        json.dump(extract_bdd_data(cfg_dir), f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
