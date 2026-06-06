#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNS_DIR="${ARCHITEC_SMOKE_RUNS_DIR:-${ROOT_DIR}/release-flow-test/runs}"
BASE_URL="${ARCHITEC_SMOKE_BASE_URL:-https://www.architec.top}"
INSTALL_SCRIPT_URL="${ARCHITEC_SMOKE_INSTALL_SCRIPT_URL:-https://github.com/SeemSeam/architec/releases/latest/download/install_prod.sh}"
LOGIN_TIMEOUT="${ARCHITEC_SMOKE_LOGIN_TIMEOUT:-180}"

EMAIL="${ARCHITEC_SMOKE_EMAIL:-}"
PASSWORD="${ARCHITEC_SMOKE_PASSWORD:-}"
AUTH_ACTION="register"
RUN_DIR=""
LOGIN_PID=""

usage() {
  cat <<'EOF'
Usage: bash tools/prod_browser_auth_smoke.sh [options]

Run the live Architec browser-authorization smoke against the production site:
1. Download the public install script
2. Install into an isolated run directory
3. Start `archi login --browser --no-browser`
4. Register or log into a website account
5. Approve the install through the website API
6. Send the callback back to the local CLI listener
7. Verify whoami/status/devices JSON outputs

Options:
  --base-url <url>            Override the website base URL. Default: https://www.architec.top
  --install-script-url <url>  Override the installer URL. Default: GitHub latest install_prod.sh
  --run-dir <path>            Use an explicit run directory instead of creating one under release-flow-test/runs
  --timeout <seconds>         Browser callback wait timeout for `archi login`. Default: 180
  --email <email>             Reuse an existing website account instead of auto-registering a temporary one
  --password <password>       Password for the existing website account
  --help                      Show this message

Examples:
  bash tools/prod_browser_auth_smoke.sh
  bash tools/prod_browser_auth_smoke.sh --email user@example.com --password 'secret'
  bash tools/prod_browser_auth_smoke.sh --base-url https://staging.example.com
EOF
}

say() {
  printf '%s\n' "$*"
}

warn() {
  printf 'Warning: %s\n' "$*" >&2
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    die "Missing required command: $1"
  fi
}

cleanup() {
  local status="$?"
  if [[ -n "${LOGIN_PID}" ]] && kill -0 "${LOGIN_PID}" >/dev/null 2>&1; then
    kill "${LOGIN_PID}" >/dev/null 2>&1 || true
    wait "${LOGIN_PID}" >/dev/null 2>&1 || true
  fi
  if [[ "${status}" -ne 0 && -n "${RUN_DIR}" ]]; then
    warn "Smoke failed. Inspect run directory: ${RUN_DIR}"
    if [[ -f "${RUN_DIR}/login.out" ]]; then
      warn "Recent login output:"
      tail -n 80 "${RUN_DIR}/login.out" >&2 || true
    fi
  fi
  exit "${status}"
}

trap cleanup EXIT INT TERM

header_location() {
  python3 - "$1" <<'PY'
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    for raw in handle:
        if raw.lower().startswith("location:"):
            print(raw.split(":", 1)[1].strip())
            raise SystemExit(0)
raise SystemExit("location header not found")
PY
}

assert_account_redirect() {
  local location="$1"
  case "${location}" in
    */account|*/account\?*|/account|/account\?*)
      ;;
    *)
      die "Expected redirect to /account, got: ${location}"
      ;;
  esac
}

wait_for_login_url() {
  local login_out="$1"
  local login_pid="$2"
  local attempt
  for attempt in $(seq 1 60); do
    if rg -q "Open this URL to authorize the CLI:" "${login_out}"; then
      return 0
    fi
    if ! kill -0 "${login_pid}" >/dev/null 2>&1; then
      return 1
    fi
    sleep 1
  done
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --install-script-url)
      INSTALL_SCRIPT_URL="$2"
      shift 2
      ;;
    --run-dir)
      RUN_DIR="$2"
      shift 2
      ;;
    --timeout)
      LOGIN_TIMEOUT="$2"
      shift 2
      ;;
    --email)
      EMAIL="$2"
      shift 2
      ;;
    --password)
      PASSWORD="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

need_cmd bash
need_cmd curl
need_cmd python3
need_cmd rg

if [[ -n "${EMAIL}" || -n "${PASSWORD}" ]]; then
  [[ -n "${EMAIL}" && -n "${PASSWORD}" ]] || die "--email and --password must be provided together"
  AUTH_ACTION="login"
fi

mkdir -p "${RUNS_DIR}"
if [[ -z "${RUN_DIR}" ]]; then
  RUN_STAMP="$(date +%Y%m%d-%H%M%S)"
  RUN_TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(3))
PY
)"
  RUN_DIR="${RUNS_DIR}/browser-auth-http-${RUN_STAMP}-${RUN_TOKEN}"
fi

HOME_DIR="${RUN_DIR}/home"
INSTALL_BASE="${RUN_DIR}/install"
BIN_DIR="${RUN_DIR}/bin"
PYTHON_USER_BASE="${RUN_DIR}/pyuser"
PYTHON_VENV_DIR="${RUN_DIR}/venv"
COOKIE_JAR="${RUN_DIR}/cookies.txt"
REGISTER_HEADERS="${RUN_DIR}/register.headers"
LOGIN_HEADERS="${RUN_DIR}/site-login.headers"
AUTHORIZE_HEADERS="${RUN_DIR}/authorize.headers"
INSTALL_LOG="${RUN_DIR}/install.log"
LOGIN_OUT="${RUN_DIR}/login.out"
WHOAMI_JSON="${RUN_DIR}/whoami.json"
STATUS_JSON="${RUN_DIR}/status.json"
DEVICES_JSON="${RUN_DIR}/devices.json"
SUMMARY_JSON="${RUN_DIR}/summary.json"
CALLBACK_HTML="${RUN_DIR}/callback.html"
INSTALL_SCRIPT_LOCAL="${RUN_DIR}/install_prod.sh"
LOGIN_PID_FILE="${RUN_DIR}/login.pid"

mkdir -p "${RUN_DIR}" "${HOME_DIR}" "${INSTALL_BASE}" "${BIN_DIR}" "${PYTHON_USER_BASE}"
python3 -m venv "${PYTHON_VENV_DIR}"

if [[ "${AUTH_ACTION}" == "register" ]]; then
  EMAIL="browser-smoke-$(date +%Y%m%d%H%M%S)-$RANDOM@example.com"
  PASSWORD="ArchiSmokePass123!"
fi

say "Run dir: ${RUN_DIR}"
say "Base URL: ${BASE_URL}"
say "Installer: ${INSTALL_SCRIPT_URL}"
say "Website auth action: ${AUTH_ACTION}"
say "Downloading install script"
curl -fsSL "${INSTALL_SCRIPT_URL}" -o "${INSTALL_SCRIPT_LOCAL}"

say "Installing Architec into isolated directories"
HOME="${HOME_DIR}" \
PYTHONUSERBASE="${PYTHON_USER_BASE}" \
ARCHITEC_INSTALL_BASE="${INSTALL_BASE}" \
ARCHITEC_BIN_DIR="${BIN_DIR}" \
ARCHITEC_LOGIN_METHOD=browser \
ARCHITEC_CONFIGURE_LLM=0 \
ARCHITEC_VERIFY_CHECKSUMS=0 \
PATH="${PYTHON_VENV_DIR}/bin:${PATH}" \
bash "${INSTALL_SCRIPT_LOCAL}" > "${INSTALL_LOG}" 2>&1

[[ -x "${BIN_DIR}/archi" ]] || die "Installed archi launcher not found at ${BIN_DIR}/archi"

say "Starting archi login"
(
  export HOME="${HOME_DIR}"
  export PYTHONUSERBASE="${PYTHON_USER_BASE}"
  export PATH="${BIN_DIR}:${PYTHON_VENV_DIR}/bin:${PYTHON_USER_BASE}/bin:${PATH}"
  export PYTHONUNBUFFERED=1
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -oL -eL archi login --browser --no-browser --timeout "${LOGIN_TIMEOUT}" > "${LOGIN_OUT}" 2>&1
  else
    archi login --browser --no-browser --timeout "${LOGIN_TIMEOUT}" > "${LOGIN_OUT}" 2>&1
  fi
) &
LOGIN_PID="$!"
printf '%s\n' "${LOGIN_PID}" > "${LOGIN_PID_FILE}"

if ! wait_for_login_url "${LOGIN_OUT}" "${LOGIN_PID}"; then
  die "archi login did not emit a browser authorization URL in time"
fi

LOGIN_URL="$(python3 - <<'PY' "${LOGIN_OUT}"
import re
import sys

text = open(sys.argv[1], "r", encoding="utf-8").read()
match = re.search(r"Open this URL to authorize the CLI:\n(https://[^\s]+)", text)
print(match.group(1) if match else "")
PY
)"

[[ -n "${LOGIN_URL}" ]] || die "Failed to parse the CLI login URL"
say "CLI login URL: ${LOGIN_URL}"

if [[ "${AUTH_ACTION}" == "register" ]]; then
  say "Registering temporary website account: ${EMAIL}"
  curl -fsS \
    -D "${REGISTER_HEADERS}" \
    -c "${COOKIE_JAR}" \
    -b "${COOKIE_JAR}" \
    -o /dev/null \
    -X POST \
    --data-urlencode "email=${EMAIL}" \
    --data-urlencode "password=${PASSWORD}" \
    "${BASE_URL}/api/auth/register"
  ACCOUNT_LOCATION="$(header_location "${REGISTER_HEADERS}")"
else
  say "Logging into existing website account: ${EMAIL}"
  curl -fsS \
    -D "${LOGIN_HEADERS}" \
    -c "${COOKIE_JAR}" \
    -b "${COOKIE_JAR}" \
    -o /dev/null \
    -X POST \
    --data-urlencode "email=${EMAIL}" \
    --data-urlencode "password=${PASSWORD}" \
    "${BASE_URL}/api/auth/login"
  ACCOUNT_LOCATION="$(header_location "${LOGIN_HEADERS}")"
fi

assert_account_redirect "${ACCOUNT_LOCATION}"

eval "$(
  python3 - <<'PY' "${LOGIN_URL}"
from urllib.parse import parse_qs, urlparse
import shlex
import sys

query = parse_qs(urlparse(sys.argv[1]).query)
for key in ("state", "install_id", "device_name", "redirect_uri", "app_version"):
    value = (query.get(key) or [""])[0]
    print(f"{key.upper()}={shlex.quote(value)}")
PY
)"

[[ -n "${STATE}" ]] || die "Missing state in CLI login URL"
[[ -n "${INSTALL_ID}" ]] || die "Missing install_id in CLI login URL"
[[ -n "${REDIRECT_URI}" ]] || die "Missing redirect_uri in CLI login URL"

say "Approving install ${INSTALL_ID} for device ${DEVICE_NAME}"
curl -fsS \
  -D "${AUTHORIZE_HEADERS}" \
  -c "${COOKIE_JAR}" \
  -b "${COOKIE_JAR}" \
  -o /dev/null \
  -X POST \
  -F "state=${STATE}" \
  -F "installId=${INSTALL_ID}" \
  -F "deviceName=${DEVICE_NAME}" \
  -F "redirectUri=${REDIRECT_URI}" \
  -F "appVersion=${APP_VERSION}" \
  "${BASE_URL}/api/cli/authorize"

AUTHORIZE_LOCATION="$(header_location "${AUTHORIZE_HEADERS}")"
CALLBACK_URL="$(python3 - <<'PY' "${AUTHORIZE_LOCATION}"
from urllib.parse import parse_qs, unquote, urlparse
import sys

query = parse_qs(urlparse(sys.argv[1]).query)
next_url = unquote((query.get("next") or [""])[0])
print(next_url)
PY
)"

[[ -n "${CALLBACK_URL}" ]] || die "Authorization redirect did not include the callback URL"
say "Sending callback to local listener"
curl -fsS "${CALLBACK_URL}" -o "${CALLBACK_HTML}"

wait "${LOGIN_PID}"
LOGIN_PID=""

say "Collecting CLI auth status"
HOME="${HOME_DIR}" \
PYTHONUSERBASE="${PYTHON_USER_BASE}" \
PATH="${BIN_DIR}:${PYTHON_VENV_DIR}/bin:${PYTHON_USER_BASE}/bin:${PATH}" \
archi whoami --json > "${WHOAMI_JSON}"

HOME="${HOME_DIR}" \
PYTHONUSERBASE="${PYTHON_USER_BASE}" \
PATH="${BIN_DIR}:${PYTHON_VENV_DIR}/bin:${PYTHON_USER_BASE}/bin:${PATH}" \
archi status --json > "${STATUS_JSON}"

HOME="${HOME_DIR}" \
PYTHONUSERBASE="${PYTHON_USER_BASE}" \
PATH="${BIN_DIR}:${PYTHON_VENV_DIR}/bin:${PYTHON_USER_BASE}/bin:${PATH}" \
archi devices --json > "${DEVICES_JSON}"

python3 - <<'PY' "${WHOAMI_JSON}" "${STATUS_JSON}" "${DEVICES_JSON}" "${SUMMARY_JSON}" "${RUN_DIR}" "${BASE_URL}" "${EMAIL}" "${AUTH_ACTION}"
import json
import sys

whoami_path, status_path, devices_path, summary_path, run_dir, base_url, email, auth_action = sys.argv[1:]
whoami = json.load(open(whoami_path, "r", encoding="utf-8"))
status = json.load(open(status_path, "r", encoding="utf-8"))
devices = json.load(open(devices_path, "r", encoding="utf-8"))

if not whoami.get("email"):
    raise SystemExit("whoami.json did not contain email")
if whoami.get("email") != email:
    raise SystemExit(f"whoami email mismatch: expected {email}, got {whoami.get('email')}")
if status.get("authenticated") is not True:
    raise SystemExit("status.json did not report authenticated=true")
if not isinstance(devices, list) or not devices:
    raise SystemExit("devices.json did not contain any active device")

summary = {
    "ok": True,
    "base_url": base_url,
    "auth_action": auth_action,
    "email": email,
    "run_dir": run_dir,
    "install_id": status.get("install_id") or whoami.get("install_id", ""),
    "device_name": status.get("device_name") or whoami.get("device_name", ""),
    "client_version": status.get("client_version") or whoami.get("client_version", ""),
    "whoami_path": whoami_path,
    "status_path": status_path,
    "devices_path": devices_path,
}
with open(summary_path, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, ensure_ascii=False)
PY

say "Production browser auth smoke passed"
say "Email: ${EMAIL}"
say "Run dir: ${RUN_DIR}"
say "Summary: ${SUMMARY_JSON}"
