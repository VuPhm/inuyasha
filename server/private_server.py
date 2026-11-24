#!/usr/bin/env python3
"""CLI entrypoint for hosting the InuYasha Private Server (LAN / Tunnel / Docker VPS)."""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import socket
import sys
import threading

SERVER_DIR = Path(__file__).resolve().parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from emulator import ENV_PRESETS, ThreadingEmulatorServer  # noqa: E402
from private_auth import PrivateServerConfig  # noqa: E402


def detect_lan_ip() -> str:
    """Best-effort detection of the host's LAN IPv4 address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip:
                return str(ip)
    except OSError:
        pass
    return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description="InuYasha: Seek Jade Private Server (R8.1)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind IP (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ENV_PRESETS["private"]["data_dir"],
        help="Persistent data directory (default: server/private_saves)",
    )
    parser.add_argument("--trace-path", type=Path, default=None, help="RPC trace log path")
    parser.add_argument("--server-name", default=None, help="Override server display name")
    parser.add_argument("--public-url", default=None, help="Explicit public URL (e.g. https://play.example.com)")
    parser.add_argument("--no-registration", action="store_true", help="Disable new account registration")
    parser.add_argument("--no-free-recharge", action="store_true", help="Disable in-game free recharge & month cards")
    parser.add_argument("--no-instant-1m", action="store_true", help="Hide & disable 1-tap 1M KC package")
    parser.add_argument("--max-free-recharge-per-day", type=int, default=None, help="Daily free recharge limit (0=unlimited)")
    parser.add_argument("--admin-token", default=None, help="Explicit X-Admin-Token for localhost GM API")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-request HTTP access logs")
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    trace_path = args.trace_path or (data_dir / "private_rpc_trace.log")

    cfg_path = data_dir / "private_server_config.json"
    cfg = PrivateServerConfig.load(cfg_path, persist=True)
    cfg_changed = False
    if args.server_name is not None:
        cfg.server_name = args.server_name
        cfg_changed = True
    if args.public_url is not None:
        cfg.public_base_url = args.public_url.rstrip("/")
        cfg_changed = True
    if args.no_registration:
        cfg.allow_registration = False
        cfg_changed = True
    if args.no_free_recharge:
        cfg.allow_free_recharge = False
        cfg_changed = True
    if args.no_instant_1m:
        cfg.allow_instant_1m_recharge = False
        cfg_changed = True
    if args.max_free_recharge_per_day is not None:
        cfg.max_free_recharge_per_day = max(0, int(args.max_free_recharge_per_day))
        cfg_changed = True
    if cfg_changed:
        cfg.save(cfg_path)

    srv = ThreadingEmulatorServer(
        (args.host, args.port),
        persist=True,
        quiet=args.quiet,
        env="private",
        data_dir=data_dir,
        trace_path=trace_path,
        admin_token=args.admin_token,
        private_mode=True,
        private_config=cfg,
    )
    lan_ip = detect_lan_ip()
    acct_cnt = len(srv.emu.auth.accounts) if srv.emu.auth else 0
    print("=" * 68)
    print(f"InuYasha Private Server [R8.1] — {cfg.server_name}")
    print(f"  Bind       : http://{args.host}:{args.port}")
    print(f"  LAN URL    : http://{lan_ip}:{args.port}   (dán vào ô Địa chỉ Server trong APK)")
    if cfg.public_base_url:
        print(f"  Public URL : {cfg.public_base_url}")
    print(f"  Info/Health: http://127.0.0.1:{args.port}/auth/info")
    print(f"  Data dir   : {data_dir}  (Tài khoản đã đăng ký: {acct_cnt})")
    print(f"  Config     : {cfg_path}")
    print(f"  Admin Token: {data_dir / '.admin_token'}")
    print(
        f"  Policy     : register={cfg.allow_registration} | free_recharge={cfg.allow_free_recharge} "
        f"| instant_1M={cfg.allow_instant_1m_recharge} | daily_cap={cfg.max_free_recharge_per_day or 'unlimited'}"
    )
    print(f"  Tunnel cmd : cloudflared tunnel --url http://127.0.0.1:{args.port}")
    print("=" * 68, flush=True)

    def _handle_sigterm(_signum: int, _frame: object) -> None:
        threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nĐang dừng InuYasha Private Server...")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
