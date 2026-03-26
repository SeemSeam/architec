#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/run_archi_via_auth_tunnel.sh --identity /path/to/key.pem [archi args...]

What it does:
  - Opens an SSH local-forward tunnel to the remote auth API
  - Keeps browser login on https://www.architec.top
  - Sends CLI API calls through http://127.0.0.1:<local-port>

Options:
  --identity PATH      SSH private key used to connect to the server
  --target USER@HOST   SSH target (default: root@www.architec.top)
  --auth-url URL       Browser auth base URL (default: https://www.architec.top)
  --local-port PORT    Local forwarded port (default: 8788)
  --remote-port PORT   Remote app port on the server (default: 3000)
  --help               Show this message

Examples:
  bash tools/run_archi_via_auth_tunnel.sh --identity ~/Download/l3miyao.pem login
  bash tools/run_archi_via_auth_tunnel.sh --identity ~/Download/l3miyao.pem whoami --json
EOF
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

wait_for_tunnel() {
  local host="$1"
  local port="$2"
  python3 - "$host" "$port" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])

deadline = time.time() + 10.0
last_error = None
while time.time() < deadline:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        sock.connect((host, port))
    except OSError as exc:
        last_error = exc
        time.sleep(0.2)
    else:
        sock.close()
        raise SystemExit(0)
    finally:
        sock.close()
raise SystemExit(f"Tunnel did not become ready at {host}:{port}: {last_error}")
PY
}

IDENTITY=""
TARGET="${ARCHITEC_TUNNEL_TARGET:-root@www.architec.top}"
AUTH_URL="${ARCHITEC_TUNNEL_AUTH_URL:-https://www.architec.top}"
LOCAL_PORT="${ARCHITEC_TUNNEL_LOCAL_PORT:-8788}"
REMOTE_PORT="${ARCHITEC_TUNNEL_REMOTE_PORT:-3000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --identity)
      IDENTITY="${2:-}"
      shift 2
      ;;
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --auth-url)
      AUTH_URL="${2:-}"
      shift 2
      ;;
    --local-port)
      LOCAL_PORT="${2:-}"
      shift 2
      ;;
    --remote-port)
      REMOTE_PORT="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

if [[ -z "${IDENTITY}" ]]; then
  echo "--identity is required" >&2
  usage >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  set -- login
fi

need_cmd ssh
need_cmd python3
need_cmd archi

SSH_PID=""
cleanup() {
  if [[ -n "${SSH_PID}" ]] && kill -0 "${SSH_PID}" >/dev/null 2>&1; then
    kill "${SSH_PID}" >/dev/null 2>&1 || true
    wait "${SSH_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

ssh -i "${IDENTITY}" \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -N \
  -L "${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
  "${TARGET}" &
SSH_PID="$!"

wait_for_tunnel "127.0.0.1" "${LOCAL_PORT}"

ARCHITEC_AUTH_BASE_URL="${AUTH_URL}" \
ARCHITEC_AUTH_API_BASE_URL="http://127.0.0.1:${LOCAL_PORT}" \
archi "$@"
