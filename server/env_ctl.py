#!/usr/bin/env python3
"""STABLE / DEV environment controller and smoke-check tool for InuYasha Revival."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
SAVES_DIR = SERVER_DIR / "saves"
DEV_SAVES_DIR = SERVER_DIR / "dev_saves"
BACKUPS_DIR = SERVER_DIR / "backups"
TRACE_PATH = SERVER_DIR / "rpc_trace.log"
DEV_TRACE_PATH = SERVER_DIR / "dev_rpc_trace.log"

SAVE_FILES = ["normal_profile.json", "debug_profile.json", "audit_ledger.jsonl"]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _summarize_dir(data_dir: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"dir": str(data_dir), "exists": data_dir.exists(), "profiles": {}}
    if not data_dir.exists():
        return out
    for fname, pname in [("normal_profile.json", "normal"), ("debug_profile.json", "debug")]:
        fp = data_dir / fname
        if fp.exists():
            d = json.loads(fp.read_text(encoding="utf-8"))
            p = d.get("player", {})
            b = d.get("battle", {})
            out["profiles"][pname] = {
                "PlayerId": p.get("PlayerId"),
                "PlayerName": p.get("PlayerName"),
                "Lv": p.get("Lv"),
                "Vip": p.get("Vip"),
                "Gold": p.get("Gold"),
                "Diamond": p.get("Diamond"),
                "MaxNodeId": b.get("MaxNodeId"),
                "StarCount": b.get("StarCount"),
            }
    return out


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def cmd_status(_args: argparse.Namespace) -> int:
    info = {
        "stable": {
            "port": 8080,
            "listening": _port_open("127.0.0.1", 8080),
            **_summarize_dir(SAVES_DIR),
            "trace_exists": TRACE_PATH.exists(),
        },
        "dev": {
            "port": 8082,
            "listening": _port_open("127.0.0.1", 8082),
            **_summarize_dir(DEV_SAVES_DIR),
            "trace_exists": DEV_TRACE_PATH.exists(),
        },
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def create_backup(tag: str | None = None, src_dir: Path = SAVES_DIR) -> Path:
    """Back up STABLE save files with SHA-256 manifest."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    folder_name = tag or f"stable_backup_{ts}"
    dest = BACKUPS_DIR / folder_name
    dest.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_dir": str(src_dir),
        "files": {},
    }
    for fname in SAVE_FILES:
        src = src_dir / fname
        if src.exists():
            dst = dest / fname
            shutil.copy2(src, dst)
            manifest["files"][fname] = {
                "size": dst.stat().st_size,
                "sha256": _sha256_file(dst),
            }
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dest


def cmd_backup(args: argparse.Namespace) -> int:
    dest = create_backup(tag=args.tag)
    print(json.dumps({"ok": True, "backup_dir": str(dest)}, indent=2))
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    bdir = Path(args.backup_dir)
    manifest_path = bdir / "MANIFEST.json"
    if not manifest_path.exists():
        print(json.dumps({"ok": False, "error": f"Missing MANIFEST.json in {bdir}"}), file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for fname, meta in manifest.get("files", {}).items():
        fp = bdir / fname
        if not fp.exists() or _sha256_file(fp) != meta["sha256"]:
            print(json.dumps({"ok": False, "error": f"Checksum mismatch for {fname}"}), file=sys.stderr)
            return 1
    pre_dir = create_backup(tag=f"pre_rollback_{time.strftime('%Y%m%d_%H%M%S')}")
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    for fname in manifest.get("files", {}):
        shutil.copy2(bdir / fname, SAVES_DIR / fname)
    print(json.dumps({"ok": True, "restored_from": str(bdir), "safety_backup": str(pre_dir)}, indent=2))
    return 0


def cmd_sync_to_dev(args: argparse.Namespace) -> int:
    DEV_SAVES_DIR.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(SERVER_DIR))
    from emulator import GameEmulatorState

    emu = GameEmulatorState(persist=True, env="dev", data_dir=DEV_SAVES_DIR, trace_path=DEV_TRACE_PATH)
    copied: list[str] = []
    if args.copy_normal and (SAVES_DIR / "normal_profile.json").exists():
        shutil.copy2(SAVES_DIR / "normal_profile.json", DEV_SAVES_DIR / "normal_profile.json")
        copied.append("normal_profile.json")
    if args.copy_debug and (SAVES_DIR / "debug_profile.json").exists():
        shutil.copy2(SAVES_DIR / "debug_profile.json", DEV_SAVES_DIR / "debug_profile.json")
        copied.append("debug_profile.json")
    print(
        json.dumps(
            {
                "ok": True,
                "dev_dir": str(DEV_SAVES_DIR),
                "copied_from_stable": copied,
                "normal_pid": emu.profiles["normal"].state["player"]["PlayerId"],
            },
            indent=2,
        )
    )
    return 0


def _http_json(url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    req_headers = {"X-Plain-Json": "1"}
    if headers:
        req_headers.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8") or "{}")


def cmd_smoke(args: argparse.Namespace) -> int:
    base = args.url.rstrip("/")
    checks: dict[str, Any] = {}
    st, health = _http_json(f"{base}/health")
    checks["health"] = {"status": st, "env": health.get("env"), "profiles": health.get("profiles")}
    assert st == 200 and health.get("ok") is True

    _, srv_list = _http_json(f"{base}/API/ServerList_Client.ashx", {})
    assert srv_list.get("Code") == 0 and len(srv_list["Data"]["Server"]) >= 2
    checks["server_list"] = {"Code": srv_list["Code"], "servers": len(srv_list["Data"]["Server"])}

    def rpc(mod: str, met: str, data: list[Any] | None = None, sid: int = 2) -> Any:
        code, body = _http_json(
            f"{base}/client.aspx",
            {"ModuleName": mod, "MethodName": met, "Data": data or [], "ServerId": sid, "TimeTick": int(time.time())},
        )
        assert code == 200 and body.get("Status") == 0, f"RPC {mod}.{met} failed: {body}"
        return body["Value"]

    sid = int(args.server_id)
    login_val = rpc("Player", "Login", [], sid=sid)
    init_val = rpc("Player", "GetInitData", [], sid=sid)
    pinfo = init_val["PlayerInfo"]
    assert isinstance(pinfo.get("VITNextRecoverTime"), int)
    assert isinstance(pinfo.get("STANextRecoverTime"), int)
    chapters = rpc("Battle", "AllChapterInfo", [], sid=sid)
    chapters_list = chapters if isinstance(chapters, list) else chapters.get("ChapterList", [])
    lv_plan = rpc("LvPlan", "GetLvPlanInfo", [], sid=sid)
    assert isinstance(lv_plan.get("CanRewardLvList"), list) and isinstance(lv_plan.get("RewardLvList"), list)
    vip_wel = rpc("VipWelfare", "GetVipWelfare", [], sid=sid)
    assert isinstance(vip_wel.get("CanDraw"), bool) and isinstance(vip_wel.get("ResourceList"), list)
    charge_list = rpc("PlayerCharge", "GetChargeList", [], sid=sid)
    assert isinstance(charge_list, list) and len(charge_list) >= 1
    checks["rpc_smoke"] = {
        "server_id": sid,
        "player_lv": login_val.get("Lv"),
        "VITNextRecoverTime": pinfo["VITNextRecoverTime"],
        "STANextRecoverTime": pinfo["STANextRecoverTime"],
        "chapters_count": len(chapters_list),
        "lv_plan_keys": sorted(lv_plan.keys()),
        "vip_welfare_items": len(vip_wel["ResourceList"]),
        "charge_tiers": len(charge_list),
    }

    unauth_code, _ = _http_json(f"{base}/admin/state?profile=debug")
    assert unauth_code == 401, f"Expected 401 unauthenticated admin request, got {unauth_code}"
    checks["admin_auth_guard"] = {"unauthenticated_status": unauth_code}

    token = args.admin_token or os.environ.get("INUYASHA_ADMIN_TOKEN")
    if token:
        adm_code, adm_state = _http_json(f"{base}/admin/state?profile=debug", headers={"X-Admin-Token": token})
        assert adm_code == 200 and adm_state.get("ok") is True
        checks["admin_authenticated"] = {"status": adm_code, "profile": adm_state.get("profile")}

    print(json.dumps({"ok": True, "url": base, "checks": checks}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage STABLE and DEV emulator environments")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Inspect STABLE and DEV ports and saves")

    p_bak = sub.add_parser("backup", help="Backup STABLE saves with SHA-256 manifest")
    p_bak.add_argument("--tag", default=None, help="Backup folder name under server/backups/")

    p_rb = sub.add_parser("rollback", help="Verify checksums and restore STABLE saves from backup")
    p_rb.add_argument("backup_dir", help="Path to backup directory containing MANIFEST.json")

    p_sync = sub.add_parser("sync-to-dev", help="Initialize isolated DEV save dir without affecting STABLE")
    p_sync.add_argument("--copy-normal", action="store_true", help="Copy STABLE normal_profile.json to DEV")
    p_sync.add_argument("--copy-debug", action="store_true", help="Copy STABLE debug_profile.json to DEV")

    p_smk = sub.add_parser("smoke", help="Run non-destructive HTTP smoke test against an emulator URL")
    p_smk.add_argument("--url", default="http://127.0.0.1:8080", help="Target emulator base URL")
    p_smk.add_argument("--server-id", type=int, default=2, help="Profile ServerId (default 2=debug to avoid touching normal)")
    p_smk.add_argument("--admin-token", default=None, help="Optional X-Admin-Token to verify authenticated admin endpoint")

    args = parser.parse_args()
    dispatch = {
        "status": cmd_status,
        "backup": cmd_backup,
        "rollback": cmd_rollback,
        "sync-to-dev": cmd_sync_to_dev,
        "smoke": cmd_smoke,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
