#!/usr/bin/env python3
"""
InuYasha: Seek Jade — OTA Hotfix & APK Release Publisher (R8.16).

Packages validated server Python/JSON files and/or client Lua/assets into a
patch zip, chunks it into D1-safe payloads (240 KiB raw per chunk), uploads via
/admin/ota/chunk, publishes the release manifest via /admin/ota/publish, and
verifies the live download SHA-256 against Cloudflare Sync Hub.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile

ROOT_DIR = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT_DIR / "server"
SECRETS_PATH = ROOT_DIR / "deploy" / "cloudflare_sync" / ".secrets.local"
DEFAULT_HUB_URL = "https://inuyasha-sync-hub.vuphamletruong.workers.dev"
DEFAULT_GITHUB_REPO = "VuPhm/inuyasha"
CHUNK_RAW_BYTES = 240 * 1024

sys.path.insert(0, str(ROOT_DIR / "poc"))
from patch_vn_apk import XXTEA_KEY, XXTEA_SIGN, xxtea_encrypt  # noqa: E402

ALL_SERVER_BUNDLE_FILES = (
    "emulator.py",
    "emulator_common.py",
    "event_handlers.py",
    "r79_event_handlers.py",
    "event_runtime.py",
    "combat_effects.py",
    "combat_sim.py",
    "economy_audit.py",
    "game_data.json",
    "bdd_handlers.py",
    "bdd_data.json",
    "teambattle_handlers.py",
    "nightmare_handlers.py",
    "reborn_handlers.py",
    "ggzj_handlers.py",
    "gddh_handlers.py",
    "social_handlers.py",
    "guild_handlers.py",
    "pvpinter_handlers.py",
    "pvp_boss_handlers.py",
    "treasure_rebirth_handlers.py",
    "progression_handlers.py",
    "pet_handlers.py",
    "pet_data.json",
    "warfare_handlers.py",
    "warfare_data.json",
    "private_auth.py",
    "hybrid_sync.py",
    "ota_updater.py",
    "sync_ca_bundle.pem",
)


def _load_admin_secret(explicit: str) -> str:
    if explicit.strip():
        return explicit.strip()
    if SECRETS_PATH.exists():
        for line in SECRETS_PATH.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "=" in s:
                k, v = s.split("=", 1)
                if k.strip() == "ADMIN_TOKEN":
                    return v.strip().strip('"').strip("'")
            else:
                return s
    raise RuntimeError("Missing --admin-secret and deploy/cloudflare_sync/.secrets.local")


def _http_json(method: str, url: str, payload: dict | None = None, admin_token: str = "") -> dict:
    headers = {"Accept": "application/json", "User-Agent": "InuYashaOtaPublisher/1.0"}
    if admin_token:
        headers["X-Admin-Token"] = admin_token
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed HTTP {exc.code}: {body}") from exc


def build_patch_zip(
    out_zip: Path,
    *,
    server_files: list[str],
    all_server: bool,
    client_src_dir: Path | None,
    client_res_dir: Path | None,
    client_files: list[str],
) -> tuple[bytes, str, int]:
    entries: list[tuple[str, bytes]] = []
    srv_list = list(ALL_SERVER_BUNDLE_FILES) if all_server else []
    for item in server_files:
        for tok in item.split(","):
            tok = tok.strip()
            if tok and tok not in srv_list:
                srv_list.append(tok)

    for rel in srv_list:
        p = (SERVER_DIR / rel).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Missing server file: {p}")
        raw = p.read_bytes()
        if p.suffix == ".py":
            if len(raw) >= 450 * 1024:
                raise RuntimeError(f"Refusing to pack {p.name}: exceeds 450 KiB limit")
            compile(raw.decode("utf-8"), p.name, "exec")
        entries.append((f"server/{Path(rel).as_posix()}", raw))

    def _add_client_src_file(src_file: Path, rel_name: str) -> None:
        raw = src_file.read_bytes()
        rel_posix = Path(rel_name).as_posix()
        if src_file.suffix == ".lua":
            raw = XXTEA_SIGN + xxtea_encrypt(raw)
            rel_posix = rel_posix[:-4] + ".luac"
        entries.append((f"client/src/{rel_posix}", raw))

    if client_src_dir is not None:
        if not client_src_dir.is_dir():
            raise FileNotFoundError(f"Missing client-src-dir: {client_src_dir}")
        for f in sorted(client_src_dir.rglob("*")):
            if f.is_file():
                _add_client_src_file(f, str(f.relative_to(client_src_dir)))

    if client_res_dir is not None:
        if not client_res_dir.is_dir():
            raise FileNotFoundError(f"Missing client-res-dir: {client_res_dir}")
        for f in sorted(client_res_dir.rglob("*")):
            if f.is_file():
                entries.append((f"client/res/{f.relative_to(client_res_dir).as_posix()}", f.read_bytes()))

    for spec in client_files:
        for tok in spec.split(","):
            tok = tok.strip()
            if not tok:
                continue
            if "=" in tok:
                arc, src_str = tok.split("=", 1)
                src_p = Path(src_str).resolve()
                arc = arc.strip().lstrip("/")
                raw = src_p.read_bytes()
                if src_p.suffix == ".lua" and arc.startswith("src/") and arc.endswith(".luac"):
                    raw = XXTEA_SIGN + xxtea_encrypt(raw)
                entries.append((f"client/{arc}", raw))
            else:
                src_p = Path(tok).resolve()
                _add_client_src_file(src_p, src_p.name)

    if not entries:
        return b"", "", 0

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for arcname, raw in entries:
            zf.writestr(arcname, raw)

    zip_bytes = out_zip.read_bytes()
    sha = hashlib.sha256(zip_bytes).hexdigest()
    return zip_bytes, sha, len(entries)


def _upload_github_release(
    repo: str,
    tag: str,
    assets: list[Path],
    *,
    title: str,
    notes: str,
) -> None:
    if not assets:
        return
    view = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo],
        capture_output=True,
        text=True,
    )
    asset_args = [str(p) for p in assets]
    if view.returncode == 0:
        subprocess.run(
            ["gh", "release", "upload", tag, *asset_args, "--repo", repo, "--clobber"],
            check=True,
        )
    else:
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                *asset_args,
                "--repo",
                repo,
                "--title",
                title,
                "--notes",
                notes or f"InuYasha Hybrid OTA {tag}",
            ],
            check=True,
        )


def main() -> None:
    p = argparse.ArgumentParser(description="Publish OTA hotfix or APK update to GitHub Releases + InuYasha Sync Hub")
    p.add_argument("--patch-version", required=True, help="Release patch version (e.g. r8.16.1)")
    p.add_argument("--channel", default="hybrid", help="OTA release channel (default: hybrid)")
    p.add_argument("--storage", choices=("github", "d1"), default="github", help="Where to host binary files (default: github)")
    p.add_argument("--repo", default=DEFAULT_GITHUB_REPO, help="GitHub owner/repo for --storage github")
    p.add_argument("--release-tag", default="", help="GitHub Release tag (defaults to --patch-version)")
    p.add_argument("--min-apk-code", type=int, default=875, help="Minimum APK versionCode supporting this patch")
    p.add_argument("--latest-apk-code", type=int, default=875, help="Latest APK versionCode")
    p.add_argument("--latest-apk-name", default="", help="Latest APK versionName")
    p.add_argument("--apk-file", default="", help="Optional APK path to attach to GitHub Release (auto-sets --apk-url)")
    p.add_argument("--apk-url", default="", help="Download URL when APK reinstall is required")
    p.add_argument("--changelog", default="", help="Human-readable Vietnamese changelog")
    p.add_argument("--force", action="store_true", help="Require update before playing")
    p.add_argument("--server-files", action="append", default=[], help="Server relative path(s), comma-separated")
    p.add_argument("--all-server", action="store_true", help="Bundle all core server files")
    p.add_argument("--client-src-dir", default="", help="Directory of Lua/.luac files mapped into client/src/")
    p.add_argument("--client-res-dir", default="", help="Directory of assets mapped into client/res/")
    p.add_argument("--client-files", action="append", default=[], help="src/Path.luac=/abs/file or /abs/file.lua")
    p.add_argument("--hub-url", default=DEFAULT_HUB_URL, help="Cloudflare Sync Hub base URL")
    p.add_argument("--admin-secret", default="", help="X-Admin-Token (defaults to .secrets.local)")
    p.add_argument("--out-zip", default="", help="Optional output zip path")
    p.add_argument("--dry-run", action="store_true", help="Build & print manifest without uploading")
    args = p.parse_args()

    hub = args.hub_url.rstrip("/")
    release_tag = (args.release_tag or args.patch_version).strip()
    out_zip = (
        Path(args.out_zip)
        if args.out_zip
        else (ROOT_DIR / "analysis" / "vn" / "patched" / f"ota_{args.patch_version}.zip")
    )
    zip_bytes, sha, file_cnt = build_patch_zip(
        out_zip,
        server_files=args.server_files,
        all_server=args.all_server,
        client_src_dir=Path(args.client_src_dir) if args.client_src_dir else None,
        client_res_dir=Path(args.client_res_dir) if args.client_res_dir else None,
        client_files=args.client_files,
    )

    apk_path = Path(args.apk_file).resolve() if args.apk_file else None
    if apk_path is not None and not apk_path.is_file():
        raise FileNotFoundError(f"Missing --apk-file: {apk_path}")

    apk_url = args.apk_url.strip()
    if args.storage == "github":
        patch_url = (
            f"https://github.com/{args.repo}/releases/download/{release_tag}/{out_zip.name}"
            if zip_bytes
            else ""
        )
        if apk_path is not None and not apk_url:
            apk_url = f"https://github.com/{args.repo}/releases/download/{release_tag}/{apk_path.name}"
    else:
        patch_url = f"/update/patch/{args.patch_version}" if zip_bytes else ""

    print(
        f"Prepared OTA release {args.patch_version} (storage={args.storage}): "
        f"files={file_cnt}, bytes={len(zip_bytes)}, sha256={sha or '-'}"
    )
    if args.dry_run:
        print(json.dumps({
            "channel": args.channel,
            "patch_version": args.patch_version,
            "min_apk_code": args.min_apk_code,
            "latest_apk_code": args.latest_apk_code,
            "latest_apk_name": args.latest_apk_name,
            "apk_url": apk_url,
            "patch_url": patch_url,
            "patch_sha256": sha,
            "patch_size": len(zip_bytes),
            "changelog": args.changelog,
            "force_update": args.force,
        }, ensure_ascii=False, indent=2))
        return

    if args.storage == "github":
        gh_assets: list[Path] = []
        if zip_bytes:
            gh_assets.append(out_zip)
        if apk_path is not None:
            gh_assets.append(apk_path)
        _upload_github_release(
            args.repo,
            release_tag,
            gh_assets,
            title=f"InuYasha Hybrid {release_tag}",
            notes=args.changelog or f"Release {args.patch_version}",
        )
    elif zip_bytes:
        secret = _load_admin_secret(args.admin_secret)
        chunks = [zip_bytes[i : i + CHUNK_RAW_BYTES] for i in range(0, len(zip_bytes), CHUNK_RAW_BYTES)]
        for idx, chunk in enumerate(chunks):
            _http_json(
                "POST",
                f"{hub}/admin/ota/chunk",
                {
                    "patch_version": args.patch_version,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "data_b64": base64.b64encode(chunk).decode("ascii"),
                },
                admin_token=secret,
            )
            print(f"Uploaded chunk {idx + 1}/{len(chunks)} ({len(chunk)} bytes)")

    secret = _load_admin_secret(args.admin_secret)
    pub = _http_json(
        "POST",
        f"{hub}/admin/ota/publish",
        {
            "channel": args.channel,
            "patch_version": args.patch_version,
            "min_apk_code": args.min_apk_code,
            "latest_apk_code": args.latest_apk_code,
            "latest_apk_name": args.latest_apk_name,
            "apk_url": apk_url,
            "patch_url": patch_url,
            "patch_sha256": sha,
            "patch_size": len(zip_bytes),
            "changelog": args.changelog,
            "force_update": bool(args.force),
        },
        admin_token=secret,
    )
    print("Published manifest:", json.dumps(pub.get("release"), ensure_ascii=False))

    # Verify live manifest + binary checksum
    man = _http_json("GET", f"{hub}/update/manifest?channel={args.channel}")
    assert man.get("release", {}).get("patch_version") == args.patch_version
    if zip_bytes:
        dl_full = patch_url if patch_url.startswith(("http://", "https://")) else f"{hub}{patch_url}"
        req = urllib.request.Request(dl_full, headers={"User-Agent": "InuYashaOtaPublisher/1.0"})
        with urllib.request.urlopen(req, timeout=20.0) as resp:
            got = resp.read()
        got_sha = hashlib.sha256(got).hexdigest()
        if got_sha != sha:
            raise RuntimeError(f"Live verification SHA mismatch: {got_sha} != {sha}")
        print(f"Verified live download: {len(got)} bytes, sha256={got_sha}")


if __name__ == "__main__":
    main()
