#!/usr/bin/env python3
"""
InuYasha: Seek Jade — In-Game OTA Update Engine (R8.16).

Supports:
  - Checking Cloudflare Sync Hub (/update/manifest?channel=hybrid) with the same
    DoH + IP-cache DNS resilience as HybridSyncManager.
  - Distinguishing seamless hotfix patches (Python server + Cocos2d-x Lua/assets)
    vs mandatory full-APK updates (AndroidManifest/Java/native .so changes).
  - Streaming download with live progress, SHA-256 verification, zip path-traversal
    guard, pre-extraction Python syntax compilation, atomic file replacement with
    backup rollback, and exit-code-42 backend respawn handoff.
"""

from __future__ import annotations

import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import threading
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from hybrid_sync import DEFAULT_SYNC_HUB_URL, HybridSyncManager, SYNC_USER_AGENT, _build_ssl_context

OTA_RESTART_EXIT_CODE = 42
DEFAULT_OTA_CHANNEL = "hybrid"
MAX_PATCH_BYTES = 25 * 1024 * 1024  # 25 MiB hard cap

_VER_R_RE = re.compile(r"r(\d+)(?:\.(\d+))?(?:\.(\d+))?", re.IGNORECASE)


def parse_version_tuple(raw: str) -> tuple[int, int, int]:
    """Parse 'r8.16.1' or '5.0.4.98-r8.16-hybrid' into normalized (major, minor, patch)."""
    s = str(raw or "").strip()
    if not s:
        return (0, 0, 0)
    m = _VER_R_RE.search(s)
    if m:
        return (
            int(m.group(1)),
            int(m.group(2) or 0),
            int(m.group(3) or 0),
        )
    nums = [int(tok) for tok in re.findall(r"\d+", s)[:3]]
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def format_base_patch_from_apk_name(name: str) -> str:
    """Derive base patch tag (e.g. 'r8.16.0') from apk_version_name."""
    maj, mino, pat = parse_version_tuple(name)
    if (maj, mino, pat) == (0, 0, 0):
        return "r0.0.0"
    return f"r{maj}.{mino}.{pat}"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _validate_archive_entry(raw_name: str) -> tuple[str, str] | None:
    """Validate zip entry path and map it into ('server'|'client_src'|'client_res', rel_path)."""
    if not raw_name or raw_name.endswith("/"):
        return None
    if raw_name.startswith("/") or "\\" in raw_name or ":" in raw_name:
        raise ValueError(f"Đường dẫn file cập nhật không hợp lệ: {raw_name}")
    parts = [p for p in raw_name.split("/") if p]
    if not parts or any(p in (".", "..") for p in parts):
        raise ValueError(f"Đường dẫn file cập nhật không an toàn: {raw_name}")
    if parts[0] == "server" and len(parts) >= 2:
        return "server", "/".join(parts[1:])
    if len(parts) >= 3 and parts[0] == "client" and parts[1] == "src":
        return "client_src", "/".join(parts[2:])
    if len(parts) >= 3 and parts[0] == "client" and parts[1] == "res":
        return "client_res", "/".join(parts[2:])
    raise ValueError(f"File ngoài vùng cho phép trong gói cập nhật: {raw_name}")


class OtaUpdateManager:
    """Manages OTA manifest checks, hotfix download/verify/extract, and APK update notices."""

    def __init__(
        self,
        data_dir: Path,
        emu: Any,
        *,
        persist: bool = True,
        http_get_fn: Callable[[str, float, Callable[[int, int], None] | None], tuple[int, bytes, str]] | None = None,
        restart_fn: Callable[[], None] | None = None,
        server_dir: Path | None = None,
        client_ota_dir: Path | None = None,
        apk_version_code: int | None = None,
        apk_version_name: str | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.emu = emu
        self.persist = persist
        self._http_get_fn = http_get_fn
        self._restart_fn = restart_fn or (lambda: os._exit(OTA_RESTART_EXIT_CODE))

        if apk_version_code is not None:
            self.apk_version_code = int(apk_version_code)
        else:
            try:
                self.apk_version_code = int(os.environ.get("INUYASHA_APK_VERSION_CODE", "0") or 0)
            except ValueError:
                self.apk_version_code = 0

        if apk_version_name is not None:
            self.apk_version_name = str(apk_version_name)
        else:
            self.apk_version_name = str(os.environ.get("INUYASHA_APK_VERSION_NAME", "") or "")

        env_srv = str(os.environ.get("INUYASHA_SERVER_DIR", "") or "").strip()
        self.server_dir = Path(server_dir) if server_dir is not None else (
            Path(env_srv) if env_srv else Path(__file__).resolve().parent
        )

        env_cli = str(os.environ.get("INUYASHA_CLIENT_OTA_DIR", "") or "").strip()
        self.client_ota_dir = Path(client_ota_dir) if client_ota_dir is not None else (
            Path(env_cli) if env_cli else (self.data_dir.parent / "moqikaka" / "Download")
        )

        self.state_path = self.data_dir / "ota_state.json"
        self._lock = threading.RLock()
        self._apply_in_flight = False
        self._ssl_ctx: ssl.SSLContext | None = None

        self.state: dict[str, Any] = {
            "channel": DEFAULT_OTA_CHANNEL,
            "apk_version_code": self.apk_version_code,
            "installed_patch_version": "",
            "last_check_at": 0,
            "last_applied_at": 0,
            "last_manifest": None,
            "last_error": "",
        }
        self._progress: dict[str, Any] = {
            "phase": "idle",
            "progress_pct": 0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "message": "",
            "needs_backend_restart": False,
            "needs_client_reload": False,
            "error": "",
        }
        self._load_state()

    def _load_state(self) -> None:
        if self.persist and self.state_path.exists():
            try:
                raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for k in self.state:
                        if k in raw:
                            self.state[k] = raw[k]
            except (ValueError, OSError):
                pass
        prev_code = int(self.state.get("apk_version_code") or 0)
        if self.apk_version_code > 0 and prev_code != self.apk_version_code:
            # Fresh APK upgrade supersedes any prior OTA patch
            self.state["apk_version_code"] = self.apk_version_code
            self.state["installed_patch_version"] = ""
            self.state["last_error"] = ""
            self._save_state()

    def _save_state(self) -> None:
        if not self.persist:
            return
        _write_json_atomic(self.state_path, self.state)

    def _server_url(self, override: str | None = None) -> str:
        raw = str(override or "").strip()
        if not raw:
            hs = getattr(self.emu, "hybrid_sync", None)
            if hs is not None and isinstance(getattr(hs, "cfg", None), dict):
                raw = str(hs.cfg.get("server_url") or "").strip()
        if not raw:
            raw = DEFAULT_SYNC_HUB_URL
        if not raw.startswith(("http://", "https://")):
            raw = "https://" + raw
        return raw.rstrip("/")

    def _get_ssl_context(self) -> ssl.SSLContext:
        hs = getattr(self.emu, "hybrid_sync", None)
        if hs is not None and getattr(hs, "_ssl_ctx", None) is not None:
            return hs._ssl_ctx
        if self._ssl_ctx is None:
            self._ssl_ctx = _build_ssl_context()
        return self._ssl_ctx

    def _http_get_bytes_via_ip(
        self,
        url: str,
        target_ip: str,
        timeout: float,
        on_progress: Callable[[int, int], None] | None = None,
        _redirects_left: int = 5,
    ) -> tuple[int, bytes, str]:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        headers = {"Host": parsed.netloc or host, "User-Agent": SYNC_USER_AGENT}

        if parsed.scheme == "https":
            ssl_ctx = self._get_ssl_context()

            class _SNIHTTPSConnection(http.client.HTTPSConnection):
                def connect(self_conn) -> None:
                    sock = socket.create_connection(
                        (target_ip, self_conn.port),
                        self_conn.timeout,
                        self_conn.source_address,
                    )
                    if getattr(self_conn, "_tunnel_host", None):
                        self_conn.sock = sock
                        self_conn._tunnel()
                    self_conn.sock = ssl_ctx.wrap_socket(sock, server_hostname=host)

            conn: http.client.HTTPConnection = _SNIHTTPSConnection(
                host, port=port, timeout=timeout, context=ssl_ctx
            )
        else:
            conn = http.client.HTTPConnection(target_ip, port=port, timeout=timeout)

        redirect_url: str | None = None
        try:
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            if resp.status in (301, 302, 303, 307, 308) and _redirects_left > 0:
                loc = resp.getheader("Location")
                if loc:
                    redirect_url = urllib.parse.urljoin(url, loc)
            if redirect_url is None:
                total = int(resp.getheader("Content-Length") or 0)
                if total > MAX_PATCH_BYTES:
                    raise ValueError("Gói cập nhật vượt quá giới hạn 25 MB")
                buf = io.BytesIO()
                downloaded = 0
                while True:
                    chunk = resp.read(32768)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_PATCH_BYTES:
                        raise ValueError("Gói cập nhật vượt quá giới hạn 25 MB")
                    buf.write(chunk)
                    if on_progress is not None:
                        on_progress(downloaded, total)
                return int(resp.status), buf.getvalue(), ""
        finally:
            conn.close()

        return self._http_get_bytes(
            redirect_url,
            timeout=timeout,
            on_progress=on_progress,
            _redirects_left=_redirects_left - 1,
        )

    def _http_get_bytes(
        self,
        url: str,
        *,
        timeout: float = 10.0,
        on_progress: Callable[[int, int], None] | None = None,
        _redirects_left: int = 5,
    ) -> tuple[int, bytes, str]:
        if callable(self._http_get_fn):
            return self._http_get_fn(url, timeout, on_progress)

        req = urllib.request.Request(
            url,
            headers={"User-Agent": SYNC_USER_AGENT, "Accept": "*/*"},
            method="GET",
        )
        ssl_ctx = self._get_ssl_context()
        host = urllib.parse.urlsplit(url).hostname or ""
        hs = getattr(self.emu, "hybrid_sync", None)

        try:
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=timeout) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                if total > MAX_PATCH_BYTES:
                    return 0, b"", "Gói cập nhật vượt quá giới hạn 25 MB"
                buf = io.BytesIO()
                downloaded = 0
                while True:
                    chunk = resp.read(32768)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_PATCH_BYTES:
                        return 0, b"", "Gói cập nhật vượt quá giới hạn 25 MB"
                    buf.write(chunk)
                    if on_progress is not None:
                        on_progress(downloaded, total)
                if hs is not None:
                    hs._cache_host_ip(host)
                return int(resp.status), buf.getvalue(), ""
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read(), f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if HybridSyncManager._is_dns_resolution_error(exc) and host and hs is not None:
                now = time.time()
                cached = hs._resolved_ip_cache.get(host)
                tried: set[str] = set()
                last_exc: BaseException = exc
                for cand_ip in (
                    cached[0] if (cached and (now - cached[1]) < 300.0) else None,
                    hs._resolve_host_via_doh(host, min(timeout, 4.0)),
                    cached[0] if cached else None,
                ):
                    if not cand_ip or cand_ip in tried:
                        continue
                    tried.add(cand_ip)
                    try:
                        st, data, err = self._http_get_bytes_via_ip(
                            url,
                            cand_ip,
                            timeout,
                            on_progress=on_progress,
                            _redirects_left=_redirects_left,
                        )
                        hs._resolved_ip_cache[host] = (cand_ip, time.time())
                        return st, data, err
                    except (OSError, TimeoutError, http.client.HTTPException) as ip_exc:
                        last_exc = ip_exc
                return 0, b"", HybridSyncManager._format_network_error(last_exc)
            return 0, b"", HybridSyncManager._format_network_error(exc)

    def _effective_local_patch(self) -> str:
        inst = str(self.state.get("installed_patch_version") or "").strip()
        if inst:
            return inst
        return format_base_patch_from_apk_name(self.apk_version_name)

    def compute_update_info(self, release: dict[str, Any] | None) -> dict[str, Any]:
        effective_local = self._effective_local_patch()
        if not isinstance(release, dict) or not release.get("patch_version"):
            return {
                "update_kind": "none",
                "effective_version": effective_local,
                "force_update": False,
            }

        min_apk = int(release.get("min_apk_code") or 0)
        latest_apk = int(release.get("latest_apk_code") or 0)
        apk_url = str(release.get("apk_url") or "").strip()
        patch_url = str(release.get("patch_url") or "").strip()
        patch_ver = str(release.get("patch_version") or "").strip()
        force = bool(release.get("force_update"))

        if self.apk_version_code > 0 and min_apk > self.apk_version_code:
            kind = "apk"
        elif patch_url and parse_version_tuple(patch_ver) > parse_version_tuple(effective_local):
            kind = "hotfix"
        elif self.apk_version_code > 0 and latest_apk > self.apk_version_code and apk_url:
            kind = "apk"
        else:
            kind = "none"

        return {
            "update_kind": kind,
            "effective_version": effective_local,
            "force_update": force,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            rel = copy.deepcopy(self.state.get("last_manifest"))
            info = self.compute_update_info(rel)
            return {
                "ok": True,
                "channel": str(self.state.get("channel") or DEFAULT_OTA_CHANNEL),
                "apk_version_code": self.apk_version_code,
                "apk_version_name": self.apk_version_name,
                "installed_patch_version": str(self.state.get("installed_patch_version") or ""),
                "effective_version": info["effective_version"],
                "server_url": self._server_url(),
                "last_check_at": int(self.state.get("last_check_at") or 0),
                "last_applied_at": int(self.state.get("last_applied_at") or 0),
                "last_error": str(self.state.get("last_error") or ""),
                "release": rel,
                "update_kind": info["update_kind"],
                "force_update": info["force_update"],
                "busy": bool(self._apply_in_flight),
                "progress": copy.deepcopy(self._progress),
            }

    def check_now(self, server_url: str | None = None) -> dict[str, Any]:
        base = self._server_url(server_url)
        with self._lock:
            channel = str(self.state.get("channel") or DEFAULT_OTA_CHANNEL)
            if not self._apply_in_flight:
                self._progress.update(
                    {
                        "phase": "checking",
                        "progress_pct": 0,
                        "message": "Đang kiểm tra bản cập nhật...",
                        "error": "",
                    }
                )
        url = f"{base}/update/manifest?channel={urllib.parse.quote(channel, safe='')}"
        code, raw, net_err = self._http_get_bytes(url, timeout=5.0)
        if code != 200:
            err_msg = net_err or f"Không kiểm tra được cập nhật (HTTP {code})"
            with self._lock:
                self.state["last_error"] = err_msg
                if not self._apply_in_flight:
                    self._progress.update({"phase": "error", "error": err_msg, "message": err_msg})
                self._save_state()
                st = self.status()
            st["check_ok"] = False
            st["error"] = err_msg
            return st

        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            err_msg = "Phản hồi manifest cập nhật không hợp lệ"
            with self._lock:
                self.state["last_error"] = err_msg
                if not self._apply_in_flight:
                    self._progress.update({"phase": "error", "error": err_msg, "message": err_msg})
                self._save_state()
                st = self.status()
            st["check_ok"] = False
            st["error"] = err_msg
            return st

        rel = body.get("release") if isinstance(body, dict) and isinstance(body.get("release"), dict) else None
        with self._lock:
            self.state["last_manifest"] = rel
            self.state["last_check_at"] = int(time.time())
            self.state["last_error"] = ""
            if not self._apply_in_flight:
                self._progress.update({"phase": "idle", "progress_pct": 0, "message": "", "error": ""})
            self._save_state()
            st = self.status()
        st["check_ok"] = True
        return st

    def start_apply(self, server_url: str | None = None) -> dict[str, Any]:
        with self._lock:
            if self._apply_in_flight:
                return {"ok": False, "busy": True, "error": "Đang tải bản cập nhật, vui lòng đợi..."}
            rel = copy.deepcopy(self.state.get("last_manifest"))

        if rel is None:
            chk = self.check_now(server_url=server_url)
            if not chk.get("check_ok"):
                return {"ok": False, "error": str(chk.get("error") or "Không kiểm tra được bản cập nhật")}
            rel = chk.get("release")

        with self._lock:
            info = self.compute_update_info(rel)
            if info["update_kind"] == "apk":
                return {"ok": False, "error": "Bản cập nhật này yêu cầu tải & cài đè APK mới."}
            if info["update_kind"] != "hotfix" or not isinstance(rel, dict):
                return {"ok": False, "error": "Bạn đang ở phiên bản mới nhất."}
            self._apply_in_flight = True
            self._progress = {
                "phase": "downloading",
                "progress_pct": 0,
                "downloaded_bytes": 0,
                "total_bytes": int(rel.get("patch_size") or 0),
                "message": f"Đang tải bản vá {rel.get('patch_version')}...",
                "needs_backend_restart": False,
                "needs_client_reload": False,
                "error": "",
            }

        t = threading.Thread(
            target=self._apply_worker,
            args=(rel, self._server_url(server_url)),
            name="ota-apply-worker",
            daemon=True,
        )
        t.start()
        return {"ok": True, "started": True, "status": self.status()}

    def _set_error(self, msg: str) -> None:
        with self._lock:
            self.state["last_error"] = msg
            self._progress.update({"phase": "error", "error": msg, "message": msg})
            self._save_state()

    def _apply_worker(self, release: dict[str, Any], base_url: str) -> None:
        tmp_dir = self.data_dir / ".ota_tmp"
        backup_dir = self.data_dir / ".ota_backup"
        try:
            raw_url = str(release.get("patch_url") or "").strip()
            dl_url = raw_url if raw_url.startswith(("http://", "https://")) else f"{base_url}{raw_url if raw_url.startswith('/') else '/' + raw_url}"
            expected_total = int(release.get("patch_size") or 0)

            def _on_prog(got: int, total_hdr: int) -> None:
                tot = total_hdr if total_hdr > 0 else expected_total
                pct = min(80, int((got * 80) / tot)) if tot > 0 else 40
                with self._lock:
                    self._progress["downloaded_bytes"] = got
                    self._progress["total_bytes"] = tot
                    self._progress["progress_pct"] = pct

            code, zip_bytes, net_err = self._http_get_bytes(dl_url, timeout=20.0, on_progress=_on_prog)
            if code != 200 or not zip_bytes:
                self._set_error(net_err or f"Tải gói cập nhật thất bại (HTTP {code})")
                return

            with self._lock:
                self._progress.update(
                    {
                        "phase": "verifying",
                        "progress_pct": 82,
                        "downloaded_bytes": len(zip_bytes),
                        "total_bytes": len(zip_bytes),
                        "message": "Đang kiểm tra toàn vẹn gói cập nhật...",
                    }
                )

            expected_sha = str(release.get("patch_sha256") or "").strip().lower()
            actual_sha = hashlib.sha256(zip_bytes).hexdigest().lower()
            if expected_sha and actual_sha != expected_sha:
                self._set_error("Gói cập nhật bị hỏng hoặc sai mã kiểm tra SHA-256")
                return

            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_zip = tmp_dir / "patch.zip"
            tmp_zip.write_bytes(zip_bytes)

            staged: list[tuple[Path, bytes]] = []
            server_count = 0
            client_count = 0
            with zipfile.ZipFile(tmp_zip, "r") as zf:
                for info in zf.infolist():
                    mapped = _validate_archive_entry(info.filename)
                    if mapped is None:
                        continue
                    kind, rel = mapped
                    raw = zf.read(info.filename)
                    if kind == "server":
                        if rel.endswith(".py"):
                            compile(raw.decode("utf-8"), rel, "exec")
                        dest = self.server_dir / rel
                        server_count += 1
                    elif kind == "client_src":
                        dest = self.client_ota_dir / "src" / rel
                        client_count += 1
                    else:
                        dest = self.client_ota_dir / "res" / rel
                        client_count += 1
                    staged.append((dest, raw))

            if not staged:
                self._set_error("Gói cập nhật trống, không có tệp nào để áp dụng")
                return

            with self._lock:
                self._progress.update(
                    {
                        "phase": "applying",
                        "progress_pct": 90,
                        "message": f"Đang cài đặt {len(staged)} tệp...",
                    }
                )

            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            backup_dir.mkdir(parents=True, exist_ok=True)

            backups: list[tuple[Path, Path | None]] = []
            try:
                for idx, (dest, raw) in enumerate(staged):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    bak_file: Path | None = None
                    if dest.exists():
                        bak_file = backup_dir / f"bak_{idx}.bin"
                        bak_file.write_bytes(dest.read_bytes())
                    backups.append((dest, bak_file))
                    tmp_out = dest.with_name(f".{dest.name}.ota_tmp.{os.getpid()}")
                    tmp_out.write_bytes(raw)
                    os.replace(tmp_out, dest)
            except Exception as write_exc:
                for dest, bak_file in reversed(backups):
                    try:
                        if bak_file is not None and bak_file.exists():
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(bak_file.read_bytes())
                        elif dest.exists():
                            dest.unlink()
                    except OSError:
                        pass
                raise write_exc

            with self._lock:
                self.state["installed_patch_version"] = str(release.get("patch_version") or "")
                self.state["last_applied_at"] = int(time.time())
                self.state["last_error"] = ""
                self._save_state()
                self._progress = {
                    "phase": "done",
                    "progress_pct": 100,
                    "downloaded_bytes": len(zip_bytes),
                    "total_bytes": len(zip_bytes),
                    "message": "Cập nhật hoàn tất! Đang áp dụng...",
                    "needs_backend_restart": server_count > 0,
                    "needs_client_reload": client_count > 0,
                    "error": "",
                }
        except (ValueError, UnicodeDecodeError, SyntaxError, zipfile.BadZipFile, OSError) as exc:
            self._set_error(f"Lỗi cài bản cập nhật: {exc}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            shutil.rmtree(backup_dir, ignore_errors=True)
            with self._lock:
                self._apply_in_flight = False

    def schedule_backend_restart(self, delay_sec: float = 0.25) -> dict[str, Any]:
        """Return HTTP response first, then exit(42) so Android supervisor respawns Python immediately."""
        def _do_restart() -> None:
            time.sleep(max(0.05, float(delay_sec)))
            self._restart_fn()

        t = threading.Thread(target=_do_restart, name="ota-restart-exit", daemon=True)
        t.start()
        return {"ok": True, "restarting": True, "exit_code": OTA_RESTART_EXIT_CODE}
