#!/usr/bin/env python3
"""Extract structured game config JSON from decrypted EN 5.1.1 Lua config tables."""

import json
import os
import re
from typing import Any

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "analysis",
    "decompiled",
    "EN_5.1.1",
    "src",
    "Config",
)
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


def main() -> None:
    heroes = parse_simple_lua_items(os.path.join(CONFIG_DIR, "HeroModel.lua"))
    attacks = parse_simple_lua_items(os.path.join(CONFIG_DIR, "AttackModel.lua"))
    chapters = parse_simple_lua_items(os.path.join(CONFIG_DIR, "BattleChapterModel.lua"))
    nodes = parse_simple_lua_items(os.path.join(CONFIG_DIR, "BattleNodeModel.lua"))

    player_config = parse_singleton_lua_item(os.path.join(CONFIG_DIR, "PlayerConfig.lua"))
    vit_config = parse_singleton_lua_item(os.path.join(CONFIG_DIR, "VitConfig.lua"))
    sta_config = parse_singleton_lua_item(os.path.join(CONFIG_DIR, "StaConfig.lua"))
    hero_config = parse_singleton_lua_item(os.path.join(CONFIG_DIR, "HeroConfig.lua"))
    callequip_config = parse_singleton_lua_item(os.path.join(CONFIG_DIR, "CallequipConfig.lua"))

    player_lv = parse_simple_lua_items(os.path.join(CONFIG_DIR, "PlayerLvRelation.lua"))
    hero_lv = parse_simple_lua_items(os.path.join(CONFIG_DIR, "HeroLvRelation.lua"))
    hero_step = parse_simple_lua_items(os.path.join(CONFIG_DIR, "HeroStepRelation.lua"))
    equips = parse_simple_lua_items(os.path.join(CONFIG_DIR, "EquipModel.lua"))
    equip_color = parse_simple_lua_items(os.path.join(CONFIG_DIR, "EquipColorRelation.lua"))
    equip_lv_up = parse_nested_lua_items(os.path.join(CONFIG_DIR, "EquipLvUpuseRelation.lua"))
    equip_group = parse_nested_lua_items(os.path.join(CONFIG_DIR, "EquipGroupActiveRelation.lua"))

    raw_node_drops = parse_simple_lua_items(os.path.join(CONFIG_DIR, "BattleNodeDropRelation.lua"))
    node_drops: dict[str, list[dict[str, Any]]] = {}
    for drop in raw_node_drops.values():
        nid = str(drop.get("nodeModelID", ""))
        if nid:
            node_drops.setdefault(nid, []).append(drop)

    road_boxes = parse_simple_lua_items(os.path.join(CONFIG_DIR, "BattleRoadBoxRelation.lua"))
    chapter_boxes = parse_simple_lua_items(os.path.join(CONFIG_DIR, "BattleChapterBoxRelation.lua"))
    module_subs = parse_simple_lua_items(os.path.join(CONFIG_DIR, "ModuleSubModel.lua"))
    hero_recruit = parse_simple_lua_items(os.path.join(CONFIG_DIR, "HeroRecruitModel.lua"))
    vip_model = parse_simple_lua_items(os.path.join(CONFIG_DIR, "VipModel.lua"))
    attrtree_slots = parse_simple_lua_items(os.path.join(CONFIG_DIR, "AttrtreeSlotRelation.lua"))

    data = {
        "source": "com.heitao.inuyasha.guge v5.1.1 (EN)",
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
            "road_boxes": len(road_boxes),
            "chapter_boxes": len(chapter_boxes),
            "module_subs": len(module_subs),
            "vip_model": len(vip_model),
        },
        "player_config": player_config,
        "vit_config": vit_config,
        "sta_config": sta_config,
        "hero_config": hero_config,
        "callequip_config": callequip_config,
        "player_lv": player_lv,
        "hero_lv": hero_lv,
        "hero_step": hero_step,
        "heroes": heroes,
        "attacks": attacks,
        "chapters": chapters,
        "nodes": nodes,
        "equips": equips,
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
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_PATH}: {data['counts']}")


if __name__ == "__main__":
    main()
