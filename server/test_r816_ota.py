#!/usr/bin/env python3
"""Unit & HTTP integration tests for R8.16 In-Game OTA Update Manager."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
import zipfile

from emulator import EmulatorHandler, ThreadingEmulatorServer
from ota_updater import (
    OTA_RESTART_EXIT_CODE,
    OtaUpdateManager,
    format_base_patch_from_apk_name,
    parse_version_tuple,
)


def _make_zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for k, v in files.items():
            zf.writestr(k, v)
    return buf.getvalue()


class _FakeEmu:
    hybrid_sync = None


class R816OtaTest(unittest.TestCase):
    def test_01_version_parsing_and_update_classification(self) -> None:
        self.assertEqual(parse_version_tuple("r8.16.1"), (8, 16, 1))
        self.assertEqual(parse_version_tuple("5.0.4.98-r8.16-hybrid"), (8, 16, 0))
        self.assertEqual(format_base_patch_from_apk_name("5.0.4.98-r8.16-hybrid"), "r8.16.0")
        self.assertGreater(parse_version_tuple("r8.16.1"), parse_version_tuple("r8.16.0"))
        self.assertGreater(parse_version_tuple("r8.17.0"), parse_version_tuple("r8.16.9"))

        with tempfile.TemporaryDirectory() as td:
            mgr = OtaUpdateManager(
                Path(td),
                _FakeEmu(),
                persist=False,
                apk_version_code=875,
                apk_version_name="5.0.4.98-r8.16-hybrid",
            )
            self.assertEqual(mgr.compute_update_info(None)["update_kind"], "none")
            self.assertEqual(
                mgr.compute_update_info({
                    "patch_version": "r8.16.0",
                    "min_apk_code": 875,
                    "latest_apk_code": 875,
                    "patch_url": "/update/patch/r8.16.0",
                })["update_kind"],
                "none",
            )
            self.assertEqual(
                mgr.compute_update_info({
                    "patch_version": "r8.16.1",
                    "min_apk_code": 875,
                    "latest_apk_code": 875,
                    "patch_url": "/update/patch/r8.16.1",
                })["update_kind"],
                "hotfix",
            )
            self.assertEqual(
                mgr.compute_update_info({
                    "patch_version": "r8.17.0",
                    "min_apk_code": 876,
                    "latest_apk_code": 876,
                    "apk_url": "https://example.com/r817.apk",
                    "patch_url": "/update/patch/r8.17.0",
                })["update_kind"],
                "apk",
            )
            # Even with older min_apk_code, if latest_apk_code > current and no newer hotfix, notify APK
            self.assertEqual(
                mgr.compute_update_info({
                    "patch_version": "r8.16.0",
                    "min_apk_code": 875,
                    "latest_apk_code": 876,
                    "apk_url": "https://example.com/r817.apk",
                })["update_kind"],
                "apk",
            )

    def test_02_apk_upgrade_resets_installed_patch_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td) / "saves"
            data_dir.mkdir()
            (data_dir / "ota_state.json").write_text(
                json.dumps({"apk_version_code": 875, "installed_patch_version": "r8.16.3"}),
                encoding="utf-8",
            )
            mgr = OtaUpdateManager(
                data_dir,
                _FakeEmu(),
                persist=True,
                apk_version_code=876,
                apk_version_name="5.0.4.98-r8.17-hybrid",
            )
            self.assertEqual(mgr.state["apk_version_code"], 876)
            self.assertEqual(mgr.state["installed_patch_version"], "")
            self.assertEqual(mgr._effective_local_patch(), "r8.17.0")

    def test_03_apply_rejects_bad_sha_traversal_and_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "saves"
            srv_dir = root / "server"
            cli_dir = root / "Download"
            data_dir.mkdir()
            srv_dir.mkdir()
            (srv_dir / "gddh_handlers.py").write_text("X = 1\n", encoding="utf-8")

            # 3a. Bad SHA-256
            good_zip = _make_zip_bytes({"server/gddh_handlers.py": b"X = 2\n"})
            manifest = {
                "ok": True,
                "release": {
                    "channel": "hybrid",
                    "patch_version": "r8.16.1",
                    "min_apk_code": 875,
                    "latest_apk_code": 875,
                    "patch_url": "/update/patch/r8.16.1",
                    "patch_sha256": "0" * 64,
                    "patch_size": len(good_zip),
                },
            }

            def _get(url: str, _timeout: float, _cb) -> tuple[int, bytes, str]:
                if "/update/manifest" in url:
                    return 200, json.dumps(manifest).encode("utf-8"), ""
                return 200, good_zip, ""

            mgr = OtaUpdateManager(
                data_dir,
                _FakeEmu(),
                persist=True,
                http_get_fn=_get,
                server_dir=srv_dir,
                client_ota_dir=cli_dir,
                apk_version_code=875,
                apk_version_name="5.0.4.98-r8.16-hybrid",
            )
            self.assertEqual(mgr.check_now()["update_kind"], "hotfix")
            self.assertTrue(mgr.start_apply()["ok"])
            for _ in range(50):
                if not mgr.status()["busy"]:
                    break
                time.sleep(0.02)
            self.assertEqual(mgr.status()["progress"]["phase"], "error")
            self.assertIn("SHA-256", mgr.status()["progress"]["error"])
            self.assertEqual((srv_dir / "gddh_handlers.py").read_text(encoding="utf-8"), "X = 1\n")

            # 3b. Path traversal rejected
            trav_zip = _make_zip_bytes({"../evil.py": b"bad = 1\n"})
            manifest["release"]["patch_sha256"] = hashlib.sha256(trav_zip).hexdigest()
            manifest["release"]["patch_size"] = len(trav_zip)
            mgr._http_get_fn = lambda url, _t, _c: (
                (200, json.dumps(manifest).encode("utf-8"), "") if "/update/manifest" in url else (200, trav_zip, "")
            )
            self.assertTrue(mgr.start_apply()["ok"])
            for _ in range(50):
                if not mgr.status()["busy"]:
                    break
                time.sleep(0.02)
            self.assertEqual(mgr.status()["progress"]["phase"], "error")
            self.assertFalse((root / "evil.py").exists())

            # 3c. Broken Python syntax rejected BEFORE extracting client files too
            bad_py_zip = _make_zip_bytes({
                "server/gddh_handlers.py": b"def broken(:\n",
                "client/src/System/Test.luac": b"DATA",
            })
            manifest["release"]["patch_sha256"] = hashlib.sha256(bad_py_zip).hexdigest()
            manifest["release"]["patch_size"] = len(bad_py_zip)
            mgr._http_get_fn = lambda url, _t, _c: (
                (200, json.dumps(manifest).encode("utf-8"), "") if "/update/manifest" in url else (200, bad_py_zip, "")
            )
            self.assertTrue(mgr.start_apply()["ok"])
            for _ in range(50):
                if not mgr.status()["busy"]:
                    break
                time.sleep(0.02)
            self.assertEqual(mgr.status()["progress"]["phase"], "error")
            self.assertEqual((srv_dir / "gddh_handlers.py").read_text(encoding="utf-8"), "X = 1\n")
            self.assertFalse((cli_dir / "src" / "System" / "Test.luac").exists())

    def test_04_successful_apply_and_http_ota_routes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "saves"
            srv_dir = root / "server"
            cli_dir = root / "Download"
            data_dir.mkdir()
            srv_dir.mkdir()
            (srv_dir / "gddh_handlers.py").write_text("VAL = 1\n", encoding="utf-8")

            patch_zip = _make_zip_bytes({
                "server/gddh_handlers.py": b"VAL = 99\n",
                "client/src/System/NewPatch.luac": b"MQXXTEA_FAKE",
                "client/res/ui/new_icon.png": b"\x89PNG\r\n\x1a\n",
            })
            patch_sha = hashlib.sha256(patch_zip).hexdigest()
            manifest = {
                "ok": True,
                "release": {
                    "channel": "hybrid",
                    "patch_version": "r8.16.2",
                    "min_apk_code": 875,
                    "latest_apk_code": 875,
                    "patch_url": "/update/patch/r8.16.2",
                    "patch_sha256": patch_sha,
                    "patch_size": len(patch_zip),
                    "changelog": "Fix battle & add icon",
                },
            }

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]

            srv = ThreadingEmulatorServer(
                ("127.0.0.1", port),
                persist=False,
                quiet=True,
                data_dir=data_dir,
            )
            restarted = threading.Event()
            srv.emu.ota_updater = OtaUpdateManager(
                data_dir,
                srv.emu,
                persist=True,
                http_get_fn=lambda url, _t, _c: (
                    (200, json.dumps(manifest).encode("utf-8"), "") if "/update/manifest" in url else (200, patch_zip, "")
                ),
                restart_fn=restarted.set,
                server_dir=srv_dir,
                client_ota_dir=cli_dir,
                apk_version_code=875,
                apk_version_name="5.0.4.98-r8.16-hybrid",
            )
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                base = f"http://127.0.0.1:{port}"
                with urllib.request.urlopen(f"{base}/ota/status", timeout=3) as r:
                    st0 = json.loads(r.read().decode())
                self.assertTrue(st0["ok"])
                self.assertEqual(st0["update_kind"], "none")

                req_chk = urllib.request.Request(f"{base}/ota/check", data=b"{}", method="POST")
                with urllib.request.urlopen(req_chk, timeout=3) as r:
                    chk = json.loads(r.read().decode())
                self.assertEqual(chk["update_kind"], "hotfix")
                self.assertEqual(chk["release"]["patch_version"], "r8.16.2")

                req_app = urllib.request.Request(f"{base}/ota/apply", data=b"{}", method="POST")
                with urllib.request.urlopen(req_app, timeout=3) as r:
                    app = json.loads(r.read().decode())
                self.assertTrue(app["ok"])

                done_st = None
                for _ in range(50):
                    with urllib.request.urlopen(f"{base}/ota/status", timeout=3) as r:
                        cur = json.loads(r.read().decode())
                    if not cur["busy"] and cur["progress"]["phase"] == "done":
                        done_st = cur
                        break
                    time.sleep(0.02)

                self.assertIsNotNone(done_st)
                self.assertEqual(done_st["installed_patch_version"], "r8.16.2")
                self.assertEqual(done_st["update_kind"], "none")
                self.assertTrue(done_st["progress"]["needs_backend_restart"])
                self.assertTrue(done_st["progress"]["needs_client_reload"])
                self.assertEqual((srv_dir / "gddh_handlers.py").read_text(encoding="utf-8"), "VAL = 99\n")
                self.assertEqual((cli_dir / "src" / "System" / "NewPatch.luac").read_bytes(), b"MQXXTEA_FAKE")
                self.assertEqual((cli_dir / "res" / "ui" / "new_icon.png").read_bytes(), b"\x89PNG\r\n\x1a\n")

                req_rst = urllib.request.Request(f"{base}/ota/restart", data=b"{}", method="POST")
                with urllib.request.urlopen(req_rst, timeout=3) as r:
                    rst = json.loads(r.read().decode())
                self.assertTrue(rst["restarting"])
                self.assertEqual(rst["exit_code"], OTA_RESTART_EXIT_CODE)
                self.assertTrue(restarted.wait(timeout=2.0))
            finally:
                srv.shutdown()
                srv.server_close()

    def test_05_http_get_bytes_via_ip_follows_redirect(self) -> None:
        import http.server

        payload = b"PK_GITHUB_RELEASE_TEST_BYTES"

        class _RedirectHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:
                return

            def do_GET(self) -> None:
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/payload")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if self.path == "/payload":
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.send_response(404)
                self.end_headers()

        httpd = http.server.HTTPServer(("127.0.0.1", 0), _RedirectHandler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                mgr = OtaUpdateManager(Path(td), _FakeEmu(), persist=False)
                code, data, err = mgr._http_get_bytes_via_ip(
                    f"http://127.0.0.1:{port}/redirect",
                    "127.0.0.1",
                    timeout=3.0,
                )
                self.assertEqual(code, 200)
                self.assertEqual(err, "")
                self.assertEqual(data, payload)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
