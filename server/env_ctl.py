#!/usr/bin/env python3
"""STABLE / DEV environment controller and smoke-check tool for InuYasha Revival."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
SAVES_DIR = SERVER_DIR / "saves"
DEV_SAVES_DIR = SERVER_DIR / "dev_saves"
BACKUPS_DIR = SERVER_DIR / "backups"
RELEASES_DIR = SERVER_DIR / "releases"
VERSIONS_DIR = RELEASES_DIR / "versions"
STABLE_CURRENT_LINK = RELEASES_DIR / "stable"
STABLE_POINTER_PATH = RELEASES_DIR / "stable_release.json"
TRACE_PATH = SERVER_DIR / "rpc_trace.log"
DEV_TRACE_PATH = SERVER_DIR / "dev_rpc_trace.log"

ENV_DAEMON_CONFIG: dict[str, dict[str, Any]] = {
    "stable": {
        "host": "0.0.0.0",
        "port": 8080,
        "pid_file": SAVES_DIR / ".stable.pid",
        "log_file": SERVER_DIR / "stable_server.log",
    },
    "dev": {
        "host": "127.0.0.1",
        "port": 8082,
        "pid_file": DEV_SAVES_DIR / ".dev.pid",
        "log_file": SERVER_DIR / "dev_server.log",
    },
}

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


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _find_env_pids(env_name: str) -> list[int]:
    """Return active PIDs running emulator.py for the given environment preset."""
    pids: list[int] = []
    cfg = ENV_DAEMON_CONFIG[env_name]
    pid_file: Path = cfg["pid_file"]
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if _pid_alive(pid):
                pids.append(pid)
        except ValueError:
            pass
    res = subprocess.run(["pgrep", "-f", f"emulator\\.py.*--env {env_name}"], capture_output=True, text=True)
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                pid = int(line)
                if pid not in pids and _pid_alive(pid):
                    pids.append(pid)
    return pids


def _daemon_info(env_name: str, port_override: int | None = None) -> dict[str, Any]:
    cfg = ENV_DAEMON_CONFIG[env_name]
    port = int(port_override if port_override is not None else cfg["port"])
    pids = _find_env_pids(env_name)
    return {
        "env": env_name,
        "port": port,
        "listening": _port_open("127.0.0.1", port),
        "pids": pids,
        "pid_file": str(cfg["pid_file"]),
        "log_file": str(cfg["log_file"]),
    }


def _wait_for_port(port: int, want_open: bool, timeout_sec: float = 10.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _port_open("127.0.0.1", port) == want_open:
            return True
        time.sleep(0.2)
    return _port_open("127.0.0.1", port) == want_open


def stop_env_daemon(env_name: str, port_override: int | None = None) -> dict[str, Any]:
    cfg = ENV_DAEMON_CONFIG[env_name]
    port = int(port_override if port_override is not None else cfg["port"])
    pids = _find_env_pids(env_name)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 5.0
    while time.time() < deadline and any(_pid_alive(p) for p in pids):
        time.sleep(0.15)
    for pid in pids:
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    cfg["pid_file"].unlink(missing_ok=True)
    down = _wait_for_port(port, False, timeout_sec=5.0)
    return {"ok": down, "action": "stop", "stopped_pids": pids, **_daemon_info(env_name, port_override=port)}


def _safe_ref_name(ref: str) -> str:
    return ref.replace("/", "__").strip()


def _resolve_git_commit(ref: str, root_dir: Path = ROOT_DIR) -> str:
    res = subprocess.run(
        ["git", "rev-parse", f"{ref}^{{commit}}"],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def verify_release(release_dir: Path) -> tuple[bool, dict[str, Any]]:
    manifest_path = release_dir / "RELEASE.json"
    if not manifest_path.exists():
        return False, {"error": f"Missing RELEASE.json in {release_dir}"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel_path, expected_sha in manifest.get("files", {}).items():
        fp = release_dir / rel_path
        if not fp.exists() or _sha256_file(fp) != expected_sha:
            return False, {"error": f"Checksum mismatch for {rel_path}", "manifest": manifest}
    return True, manifest


def materialize_release(
    ref: str,
    releases_dir: Path = RELEASES_DIR,
    root_dir: Path = ROOT_DIR,
    force: bool = False,
) -> dict[str, Any]:
    """Materialize an immutable git checkpoint/ref into server/releases/versions/<ref>/."""
    commit = _resolve_git_commit(ref, root_dir=root_dir)
    safe_name = _safe_ref_name(ref)
    versions_dir = releases_dir / "versions"
    dest = versions_dir / safe_name

    if dest.exists() and not force:
        ok, manifest = verify_release(dest)
        if ok and manifest.get("commit") == commit:
            return {"ok": True, "reused": True, "release_dir": str(dest), "manifest": manifest}

    tmp_dest = versions_dir / f".tmp_{safe_name}_{int(time.time())}"
    versions_dir.mkdir(parents=True, exist_ok=True)
    archive_bytes = subprocess.check_output(
        ["git", "archive", "--format=tar", commit, "server"],
        cwd=str(root_dir),
    )
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as tf:
        for member in tf.getmembers():
            if member.name.startswith("/") or ".." in Path(member.name).parts:
                continue
            tf.extract(member, path=tmp_dest)

    # Link heavy asset/poc dirs without duplicating multi-GB binaries so R5.2..R6+ resolve natively
    for link_name in ("analysis", "poc"):
        target_path = (root_dir / link_name).resolve()
        link_path = tmp_dest / link_name
        if target_path.exists() and not link_path.exists():
            os.symlink(str(target_path), str(link_path))

    files_meta: dict[str, str] = {}
    srv_sub = tmp_dest / "server"
    for p in sorted(srv_sub.rglob("*")):
        if p.is_file():
            files_meta[str(p.relative_to(tmp_dest))] = _sha256_file(p)

    manifest = {
        "tag": ref,
        "commit": commit,
        "short_commit": commit[:7],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "files": files_meta,
    }
    (tmp_dest / "RELEASE.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if dest.exists():
        shutil.rmtree(dest)
    tmp_dest.rename(dest)
    return {"ok": True, "reused": False, "release_dir": str(dest), "manifest": manifest}


def _set_stable_release_pointer(
    ref: str,
    releases_dir: Path = RELEASES_DIR,
    root_dir: Path = ROOT_DIR,
) -> dict[str, Any]:
    mat = materialize_release(ref, releases_dir=releases_dir, root_dir=root_dir)
    release_dir = Path(mat["release_dir"])
    pointer_path = releases_dir / "stable_release.json"
    link_path = releases_dir / "stable"

    prev_release = None
    if pointer_path.exists():
        try:
            prev_release = json.loads(pointer_path.read_text(encoding="utf-8")).get("active_release")
        except Exception:
            prev_release = None
    if prev_release == ref:
        prev_release = json.loads(pointer_path.read_text(encoding="utf-8")).get("previous_release") if pointer_path.exists() else None

    tmp_link = releases_dir / f".tmp_stable_link_{int(time.time())}"
    if tmp_link.is_symlink() or tmp_link.exists():
        tmp_link.unlink()
    os.symlink(str(Path("versions") / release_dir.name), str(tmp_link))
    os.replace(str(tmp_link), str(link_path))

    ptr_data = {
        "active_release": ref,
        "previous_release": prev_release,
        "commit": mat["manifest"]["commit"],
        "short_commit": mat["manifest"]["short_commit"],
        "release_dir": str(release_dir),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    pointer_path.write_text(json.dumps(ptr_data, indent=2), encoding="utf-8")
    return ptr_data


def get_active_stable_release(releases_dir: Path = RELEASES_DIR) -> dict[str, Any]:
    pointer_path = releases_dir / "stable_release.json"
    link_path = releases_dir / "stable"
    if not pointer_path.exists() or not link_path.exists():
        return {"configured": False, "verified": False, "error": "STABLE release pointer not initialized"}
    ptr = json.loads(pointer_path.read_text(encoding="utf-8"))
    release_dir = link_path.resolve()
    ok, detail = verify_release(release_dir)
    emu_path = release_dir / "server" / "emulator.py"
    return {
        "configured": True,
        "verified": bool(ok and emu_path.exists()),
        "active_release": ptr.get("active_release"),
        "previous_release": ptr.get("previous_release"),
        "commit": ptr.get("commit"),
        "short_commit": ptr.get("short_commit"),
        "release_dir": str(release_dir),
        "emulator_path": str(emu_path),
        "isolated_from_dev": emu_path.resolve() != (SERVER_DIR / "emulator.py").resolve(),
        "verify_detail": None if ok else detail,
    }


def _dev_git_status_meta(root_dir: Path = ROOT_DIR) -> dict[str, Any]:
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root_dir, capture_output=True, text=True)
    desc = subprocess.run(["git", "describe", "--tags", "--exact-match", "HEAD"], cwd=root_dir, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "server/"], cwd=root_dir, capture_output=True, text=True)
    return {
        "head_commit": head.stdout.strip() if head.returncode == 0 else None,
        "exact_tag": desc.stdout.strip() if desc.returncode == 0 else None,
        "server_dirty": bool(dirty.stdout.strip()),
        "emulator_path": str(SERVER_DIR / "emulator.py"),
    }


def start_env_daemon(
    env_name: str,
    host_override: str | None = None,
    port_override: int | None = None,
    data_dir: Path | None = None,
    trace_path: Path | None = None,
    releases_dir: Path = RELEASES_DIR,
) -> dict[str, Any]:
    cfg = ENV_DAEMON_CONFIG[env_name]
    host = host_override or str(cfg["host"])
    port = int(port_override if port_override is not None else cfg["port"])
    if _port_open("127.0.0.1", port):
        return {"ok": True, "action": "start", "already_running": True, **_daemon_info(env_name, port_override=port)}
    pid_file: Path = (data_dir / f".{env_name}.pid") if data_dir else cfg["pid_file"]
    log_file: Path = cfg["log_file"]
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    run_env = os.environ.copy()
    if env_name == "stable":
        rel = get_active_stable_release(releases_dir=releases_dir)
        if not rel.get("configured") or not rel.get("verified") or not rel.get("isolated_from_dev"):
            raise RuntimeError(
                f"Refusing to start STABLE from DEV working tree; release isolation check failed: {rel}"
            )
        emu_script = Path(rel["emulator_path"])
        run_cwd = Path(rel["release_dir"])
        run_env["INUYASHA_ROOT_DIR"] = str(ROOT_DIR)
        eff_data_dir = data_dir or SAVES_DIR
        eff_trace_path = trace_path or TRACE_PATH
    else:
        emu_script = SERVER_DIR / "emulator.py"
        run_cwd = ROOT_DIR
        eff_data_dir = data_dir or DEV_SAVES_DIR
        eff_trace_path = trace_path or DEV_TRACE_PATH

    cmd = [
        sys.executable,
        str(emu_script),
        "--env",
        env_name,
        "--host",
        host,
        "--port",
        str(port),
        "--data-dir",
        str(eff_data_dir),
        "--trace-path",
        str(eff_trace_path),
    ]
    with open(log_file, "ab") as lf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(run_cwd),
            env=run_env,
            stdin=subprocess.DEVNULL,
            stdout=lf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    up = _wait_for_port(port, True, timeout_sec=10.0)
    return {
        "ok": up,
        "action": "start",
        "spawned_pid": proc.pid,
        "emulator_path": str(emu_script),
        **_daemon_info(env_name, port_override=port),
    }


def _probe_live_health(port: int) -> dict[str, Any] | None:
    if not _port_open("127.0.0.1", port):
        return None
    try:
        st, body = _http_json(f"http://127.0.0.1:{port}/health")
        return body if st == 200 and isinstance(body, dict) else None
    except Exception:
        return None


def cmd_status(_args: argparse.Namespace) -> int:
    stable_rel = get_active_stable_release()
    stable_health = _probe_live_health(8080)
    dev_health = _probe_live_health(8082)
    staged_versions = sorted(p.name for p in VERSIONS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")) if VERSIONS_DIR.exists() else []
    info = {
        "stable": {
            "port": 8080,
            "listening": _port_open("127.0.0.1", 8080),
            "daemon": _daemon_info("stable"),
            "release": stable_rel,
            "live_health_release": (stable_health or {}).get("release") if stable_health else None,
            **_summarize_dir(SAVES_DIR),
            "trace_exists": TRACE_PATH.exists(),
        },
        "dev": {
            "port": 8082,
            "listening": _port_open("127.0.0.1", 8082),
            "daemon": _daemon_info("dev"),
            "working_tree": _dev_git_status_meta(),
            "live_health_release": (dev_health or {}).get("release") if dev_health else None,
            **_summarize_dir(DEV_SAVES_DIR),
            "trace_exists": DEV_TRACE_PATH.exists(),
        },
        "staged_releases": staged_versions,
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    env_name = args.env
    action = args.action
    if action == "status":
        res = {"ok": True, "action": "status", **_daemon_info(env_name)}
        print(json.dumps(res, indent=2))
        return 0
    if action == "stop":
        res = stop_env_daemon(env_name)
        print(json.dumps(res, indent=2))
        return 0 if res["ok"] else 1
    if action == "start":
        res = start_env_daemon(env_name, host_override=args.host, port_override=args.port)
        print(json.dumps(res, indent=2))
        return 0 if res["ok"] else 1
    if action == "restart":
        stop_res = stop_env_daemon(env_name, port_override=args.port)
        start_res = start_env_daemon(env_name, host_override=args.host, port_override=args.port)
        out = {"ok": bool(stop_res["ok"] and start_res["ok"]), "action": "restart", "stop": stop_res, "start": start_res}
        print(json.dumps(out, indent=2))
        return 0 if out["ok"] else 1
    return 1


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


def cmd_release_stage(args: argparse.Namespace) -> int:
    res = materialize_release(args.ref, force=bool(args.force))
    print(json.dumps({"ok": True, "action": "release-stage", **res}, indent=2))
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    mat = materialize_release(args.ref, force=bool(args.force))
    cur = get_active_stable_release()
    if not args.confirm:
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "message": "Staged release verified. Pass --confirm (and optionally --restart) to update STABLE.",
                    "current_stable": cur,
                    "target_release": mat["manifest"],
                    "release_dir": mat["release_dir"],
                },
                indent=2,
            )
        )
        return 0

    bak_dir = create_backup(tag=f"pre_promote_{_safe_ref_name(args.ref)}_{time.strftime('%Y%m%d_%H%M%S')}")
    ptr = _set_stable_release_pointer(args.ref)
    out: dict[str, Any] = {
        "ok": True,
        "dry_run": False,
        "action": "promote",
        "backup_dir": str(bak_dir),
        "stable_pointer": ptr,
        "restarted": False,
    }
    if args.restart:
        stop_res = stop_env_daemon("stable")
        start_res = start_env_daemon("stable")
        out["restarted"] = True
        out["restart_detail"] = {"stop": stop_res, "start": start_res}
        out["ok"] = bool(stop_res.get("ok") and start_res.get("ok"))
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


def cmd_rollback_release(args: argparse.Namespace) -> int:
    cur = get_active_stable_release()
    target_ref = args.ref or cur.get("previous_release")
    if not target_ref:
        print(json.dumps({"ok": False, "error": "No previous_release recorded and no --ref specified"}), file=sys.stderr)
        return 1
    mat = materialize_release(target_ref)
    if not args.confirm:
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "message": "Dry-run release rollback plan. Pass --confirm (and --restart if needed) to apply.",
                    "current_stable": cur,
                    "target_release": mat["manifest"],
                    "backup_dir": args.backup_dir,
                },
                indent=2,
            )
        )
        return 0

    ptr = _set_stable_release_pointer(target_ref)
    restored_saves = None
    if args.backup_dir:
        rb_args = argparse.Namespace(backup_dir=args.backup_dir)
        if cmd_rollback(rb_args) != 0:
            return 1
        restored_saves = args.backup_dir
    out: dict[str, Any] = {
        "ok": True,
        "dry_run": False,
        "action": "rollback-release",
        "stable_pointer": ptr,
        "restored_saves": restored_saves,
        "restarted": False,
    }
    if args.restart:
        stop_res = stop_env_daemon("stable")
        start_res = start_env_daemon("stable")
        out["restarted"] = True
        out["restart_detail"] = {"stop": stop_res, "start": start_res}
        out["ok"] = bool(stop_res.get("ok") and start_res.get("ok"))
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


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

    p_dmn = sub.add_parser("daemon", help="Manage detached persistent emulator daemon (PID-tracked)")
    p_dmn.add_argument("action", choices=["start", "stop", "restart", "status"], help="Daemon action")
    p_dmn.add_argument("--env", choices=["stable", "dev"], default="stable", help="Target environment (default stable)")
    p_dmn.add_argument("--host", default=None, help="Override bind host")
    p_dmn.add_argument("--port", type=int, default=None, help="Override bind port")

    p_stage = sub.add_parser("release-stage", help="Materialize a git ref into isolated server/releases/versions/<ref>")
    p_stage.add_argument("--ref", required=True, help="Git tag or commit ref to materialize")
    p_stage.add_argument("--force", action="store_true", help="Rebuild release directory even if present")

    p_prom = sub.add_parser("promote", help="Promote a tested git ref to STABLE (dry-run without --confirm)")
    p_prom.add_argument("--ref", required=True, help="Git tag or commit ref to promote to STABLE")
    p_prom.add_argument("--force", action="store_true", help="Rebuild release directory even if present")
    p_prom.add_argument("--confirm", action="store_true", help="Actually update STABLE release pointer (backs up saves)")
    p_prom.add_argument("--restart", action="store_true", help="Also restart STABLE daemon after promoting")

    p_rrel = sub.add_parser("rollback-release", help="Roll STABLE release pointer back to previous or specified ref")
    p_rrel.add_argument("--ref", default=None, help="Target rollback git ref (default: recorded previous_release)")
    p_rrel.add_argument("--backup-dir", default=None, help="Optional save backup dir to restore simultaneously")
    p_rrel.add_argument("--confirm", action="store_true", help="Actually apply rollback")
    p_rrel.add_argument("--restart", action="store_true", help="Also restart STABLE daemon after rollback")

    args = parser.parse_args()
    dispatch = {
        "status": cmd_status,
        "backup": cmd_backup,
        "rollback": cmd_rollback,
        "sync-to-dev": cmd_sync_to_dev,
        "smoke": cmd_smoke,
        "daemon": cmd_daemon,
        "release-stage": cmd_release_stage,
        "promote": cmd_promote,
        "rollback-release": cmd_rollback_release,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
