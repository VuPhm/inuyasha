#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PORT="8080"
DATA_DIR="$REPO_ROOT/server/private_saves"
USE_TUNNEL="0"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="$2"
      shift 2
      ;;
    --tunnel)
      USE_TUNNEL="1"
      shift
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

mkdir -p "$DATA_DIR"

SERVER_PID=""
TUNNEL_PID=""

cleanup() {
  if [[ -n "$TUNNEL_PID" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
    kill "$TUNNEL_PID" 2>/dev/null || true
  fi
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ "$USE_TUNNEL" == "1" ]]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "Lỗi: không tìm thấy 'cloudflared' trong PATH." >&2
    exit 1
  fi
  python3 "$REPO_ROOT/server/private_server.py" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --data-dir "$DATA_DIR" \
    "${EXTRA_ARGS[@]}" &
  SERVER_PID=$!
  sleep 2
  echo "Đang mở Cloudflare Tunnel tới http://127.0.0.1:$PORT ..."
  cloudflared tunnel --url "http://127.0.0.1:$PORT" &
  TUNNEL_PID=$!
  wait "$SERVER_PID"
else
  exec python3 "$REPO_ROOT/server/private_server.py" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --data-dir "$DATA_DIR" \
    "${EXTRA_ARGS[@]}"
fi
