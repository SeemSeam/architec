#!/usr/bin/env bash

set -euo pipefail

REPO="${ARCHITEC_RELEASE_REPO:-SeemSeam/architec}"
VERSION="${ARCHITEC_VERSION:-latest}"
BASE_URL="${ARCHITEC_DOWNLOAD_BASE_URL:-}"
INSTALL_BASE="${ARCHITEC_INSTALL_BASE:-$HOME/.local/architec}"
BIN_DIR="${ARCHITEC_BIN_DIR:-$HOME/.local/bin}"
VERIFY_CHECKSUMS="${ARCHITEC_VERIFY_CHECKSUMS:-1}"
RAW_OS_NAME="${ARCHITEC_TARGET_OS:-$(uname -s)}"
RAW_ARCH_NAME="${ARCHITEC_TARGET_ARCH:-$(uname -m)}"
ASSET_NAME="${ARCHITEC_ASSET_NAME:-}"
LOGIN_METHOD="${ARCHITEC_LOGIN_METHOD:-browser}"

USER_CONFIG_BASE="${ARCHITEC_USER_CONFIG_DIR:-$HOME/.architec}"
STATE_DIR="${USER_CONFIG_BASE}"
LLM_CONFIG_PATH="${ARCHITEC_LLM_CONFIG:-${STATE_DIR}/config.yaml}"
LLM_CONFIG_BASE="$(dirname "${LLM_CONFIG_PATH}")"

LLMGATEWAY_USER_CONFIG_BASE="${LLMGATEWAY_USER_CONFIG_DIR:-$HOME/.llmgateway}"
LLMGATEWAY_CONFIG_PATH="${LLMGATEWAY_CONFIG:-${LLMGATEWAY_USER_CONFIG_BASE}/config.yaml}"
LLMGATEWAY_CONFIG_BASE="$(dirname "${LLMGATEWAY_CONFIG_PATH}")"

HIPPOCAMPUS_USER_CONFIG_BASE="${HIPPOCAMPUS_USER_CONFIG_DIR:-$HOME/.hippocampus}"
HIPPOCAMPUS_LLM_CONFIG_PATH="${HIPPOCAMPUS_LLM_CONFIG:-${HIPPOCAMPUS_USER_CONFIG_BASE}/config.yaml}"
HIPPOCAMPUS_LLM_CONFIG_BASE="$(dirname "${HIPPOCAMPUS_LLM_CONFIG_PATH}")"

AUTH_STATE_DIR="${STATE_DIR}/auth"
AUTH_PREFERENCES_PATH="${AUTH_STATE_DIR}/preferences.json"

gateway_provider_type="${gateway_provider_type:-${architec_llm_provider_type:-openai}}"
gateway_api_style="${gateway_api_style:-${architec_llm_api_style:-openai_chat}}"
gateway_base_url="${gateway_base_url:-${architec_llm_main_url:-${ARCHITEC_LLM_MAIN_URL:-}}}"
gateway_api_key="${gateway_api_key:-${architec_llm_main_api_key:-${ARCHITEC_LLM_MAIN_API_KEY:-}}}"
gateway_max_concurrent="${gateway_max_concurrent:-${architec_llm_max_concurrent:-4}}"
gateway_retry_max="${gateway_retry_max:-2}"
gateway_timeout="${gateway_timeout:-120}"
architec_llm_strong_model="${architec_llm_strong_model:-gpt-5.4}"
architec_llm_weak_model="${architec_llm_weak_model:-gpt-5.4-mini}"
architec_llm_strong_reasoning_effort="${architec_llm_strong_reasoning_effort:-high}"
architec_llm_weak_reasoning_effort="${architec_llm_weak_reasoning_effort:-low}"

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

usage() {
  cat <<'EOF'
Usage: install_prod.sh [options]

Install the standalone Architec `archi` binary from GitHub Releases.

Options:
  --version <tag|latest>     Release tag or version to install. Default: latest
  --repo <owner/name>        Release repository. Default: SeemSeam/architec
  --base-url <url>           Direct release asset base URL
  --install-base <path>      Installation base directory. Default: ~/.local/architec
  --bin-dir <path>           Directory where the archi launcher is created. Default: ~/.local/bin
  --os <name>                Override detected operating system
  --arch <name>              Override detected architecture
  --asset-name <name>        Override release binary asset name
  --skip-checksum            Skip checksum verification
  --configure-llm            Accepted for compatibility; existing configs are never overwritten
  --skip-llm-config          Still creates a starter template when llmgateway config is missing
  --help                     Show this message

The installer never overwrites an existing ~/.llmgateway/config.yaml. If that
file is missing, it creates a 0600 starter template with primary and optional
fallback provider examples.
EOF
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

normalize_os() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    linux*) printf 'linux' ;;
    darwin*|macos*) printf 'darwin' ;;
    msys*|mingw*|cygwin*|windows*) printf 'win32' ;;
    *) die "Unsupported operating system: $1" ;;
  esac
}

normalize_arch() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    x86_64|amd64|x64) printf 'x64' ;;
    arm64|aarch64) printf 'arm64' ;;
    *) die "Unsupported CPU architecture: $1" ;;
  esac
}

platform_triplet() {
  local os_name="$1"
  local arch_name="$2"
  if [[ "${os_name}" == "win32" && "${arch_name}" != "x64" ]]; then
    die "Unsupported Windows architecture: ${arch_name}"
  fi
  printf '%s-%s' "${os_name}" "${arch_name}"
}

normalize_version() {
  local raw="$1"
  raw="${raw#v}"
  printf '%s' "${raw}"
}

asset_name_for() {
  local version="$1"
  local triplet="$2"
  local suffix=""
  if [[ "${triplet}" == win32-* ]]; then
    suffix=".exe"
  fi
  printf 'archi-v%s-%s%s' "${version}" "${triplet}" "${suffix}"
}

checksum_name_for() {
  printf 'archi-v%s-checksums.txt' "$1"
}

join_url() {
  local base="$1"
  local name="$2"
  printf '%s/%s' "${base%/}" "${name}"
}

resolve_latest_version() {
  local selector="$1"
  if [[ -n "${selector}" && "${selector}" != "latest" ]]; then
    normalize_version "${selector}"
    return 0
  fi

  local effective_url
  effective_url="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "https://github.com/${REPO}/releases/latest")" \
    || die "Unable to resolve latest GitHub Release for ${REPO}"
  local tag="${effective_url##*/}"
  tag="${tag#v}"
  [[ -n "${tag}" && "${tag}" != "latest" ]] || die "Latest GitHub Release redirect did not contain a version tag"
  printf '%s' "${tag}"
}

verify_checksum() {
  local binary_path="$1"
  local checksums_path="$2"
  local asset_name="$3"
  local expected=""
  expected="$(awk -v name="${asset_name}" '
    NF >= 2 && $1 !~ /^#/ {
      candidate = $NF
      sub(/^\*/, "", candidate)
      if (candidate == name) {
        print tolower($1)
        exit
      }
    }
  ' "${checksums_path}")"
  [[ -n "${expected}" ]] || die "Checksum entry not found for ${asset_name}"

  local actual=""
  if command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "${binary_path}" | awk '{print tolower($1)}')"
  elif command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "${binary_path}" | awk '{print tolower($1)}')"
  elif command -v openssl >/dev/null 2>&1; then
    actual="$(openssl dgst -sha256 "${binary_path}" | awk '{print tolower($NF)}')"
  else
    die "Missing checksum tool: install sha256sum, shasum, or openssl, or pass --skip-checksum"
  fi

  [[ "${actual}" == "${expected}" ]] || die "Checksum mismatch for ${asset_name}: expected ${expected}, got ${actual}"
}

yaml_quote() {
  local value="${1:-}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/}"
  printf '"%s"' "${value}"
}

positive_int_or_default() {
  local raw="${1:-}"
  local default="$2"
  if [[ "${raw}" =~ ^[0-9]+$ && "${raw}" -ge 1 ]]; then
    printf '%s' "${raw}"
  else
    printf '%s' "${default}"
  fi
}

nonnegative_int_or_default() {
  local raw="${1:-}"
  local default="$2"
  if [[ "${raw}" =~ ^[0-9]+$ ]]; then
    printf '%s' "${raw}"
  else
    printf '%s' "${default}"
  fi
}

number_or_default() {
  local raw="${1:-}"
  local default="$2"
  if [[ "${raw}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    printf '%s' "${raw}"
  else
    printf '%s' "${default}"
  fi
}

write_architec_config_if_missing() {
  [[ -f "${LLM_CONFIG_PATH}" ]] && return 0
  mkdir -p "${LLM_CONFIG_BASE}"
  cat >"${LLM_CONFIG_PATH}" <<'YAML'
version: 1
tasks:
  architect_history:
    tier: strong
  architect_feature:
    tier: strong
  architect_component_scoring:
    tier: weak
  architect_component_qa:
    tier: strong
  architect_folder_naming:
    tier: weak
  architect_topology_review:
    tier: weak
  architect_full_report_md:
    tier: strong
  architect_orchestrator:
    tier: strong
  architec_summary:
    tier: strong
YAML
  chmod 600 "${LLM_CONFIG_PATH}"
}

write_hippocampus_config_if_missing() {
  [[ -f "${HIPPOCAMPUS_LLM_CONFIG_PATH}" ]] && return 0
  mkdir -p "${HIPPOCAMPUS_LLM_CONFIG_BASE}"
  cat >"${HIPPOCAMPUS_LLM_CONFIG_PATH}" <<'YAML'
version: 1
tasks:
  phase_1:
    tier: weak
  phase_2a:
    tier: strong
  phase_2b:
    tier: weak
  phase_3a:
    tier: weak
  phase_3b:
    tier: strong
  architect:
    tier: strong
YAML
  chmod 600 "${HIPPOCAMPUS_LLM_CONFIG_PATH}"
}

write_gateway_config_if_missing() {
  if [[ -f "${LLMGATEWAY_CONFIG_PATH}" ]]; then
    say "Keeping existing llmgateway config at ${LLMGATEWAY_CONFIG_PATH}"
    return 0
  fi

  mkdir -p "${LLMGATEWAY_CONFIG_BASE}"
  local provider_type_q api_style_q base_url_q api_key_q strong_model_q weak_model_q strong_effort_q weak_effort_q
  local max_concurrent retry_max timeout fallback_model
  provider_type_q="$(yaml_quote "${gateway_provider_type:-openai}")"
  api_style_q="$(yaml_quote "${gateway_api_style:-openai_chat}")"
  base_url_q="$(yaml_quote "${gateway_base_url:-}")"
  api_key_q="$(yaml_quote "${gateway_api_key:-}")"
  architec_llm_strong_model="${architec_llm_strong_model:-gpt-5.4}"
  architec_llm_weak_model="${architec_llm_weak_model:-gpt-5.4-mini}"
  fallback_model="${architec_llm_weak_model:-${architec_llm_strong_model}}"
  strong_model_q="$(yaml_quote "${architec_llm_strong_model}")"
  weak_model_q="$(yaml_quote "${architec_llm_weak_model}")"
  strong_effort_q="$(yaml_quote "${architec_llm_strong_reasoning_effort:-high}")"
  weak_effort_q="$(yaml_quote "${architec_llm_weak_reasoning_effort:-low}")"
  max_concurrent="$(positive_int_or_default "${gateway_max_concurrent}" 4)"
  retry_max="$(nonnegative_int_or_default "${gateway_retry_max}" 2)"
  timeout="$(number_or_default "${gateway_timeout}" 120)"

  cat >"${LLMGATEWAY_CONFIG_PATH}" <<YAML
# llmgateway config for Architec
# Installer rule: this file is created only when missing. Existing provider
# credentials are never overwritten by install or update.
#
# Fill the primary provider base_url and api_key below, or replace values with
# env references such as \${MY_LLM_API_KEY}. llmgateway supports ordered
# provider fallback through providers.
version: 1

providers:
  # Primary provider. Common api_style values: openai_chat, responses, anthropic, litellm.
  - provider_type: ${provider_type_q}
    api_style: ${api_style_q}
    base_url: ${base_url_q}  # e.g. https://your-llm-endpoint/v1
    api_key: ${api_key_q}
    headers: {}
    # headers example, if your provider requires extra HTTP headers:
    # headers:
    #   anthropic-version: "2023-06-01"
    model_map: {}
    # model_map example, if provider model IDs differ from Architec names:
    # model_map:
    #   gpt-5.4: openai/gpt-5.4
    #   gpt-5.4-mini: openai/gpt-5.4-mini

  # Optional fallback provider example.
  # Uncomment and fill this block to let llmgateway try a secondary API
  # source after primary transport failures.
  # - provider_type: openai
  #   api_style: openai_chat
  #   base_url: \${ARCHITEC_LLM_SECONDARY_BASE_URL}
  #   api_key: \${ARCHITEC_LLM_SECONDARY_API_KEY}
  #   headers: {}
  #   model_map:
  #     gpt-5.4: secondary-provider-strong-model
  #     gpt-5.4-mini: secondary-provider-fast-model

settings:
  fallback_model: $(yaml_quote "${fallback_model}")
  strong_model: ${strong_model_q}
  weak_model: ${weak_model_q}
  strong_reasoning_effort: ${strong_effort_q}
  weak_reasoning_effort: ${weak_effort_q}
  max_concurrent: ${max_concurrent}
  retry_max: ${retry_max}
  transport_retries: 2
  timeout: ${timeout}
YAML
  chmod 600 "${LLMGATEWAY_CONFIG_PATH}"
  warn "Created a starter llmgateway config template at ${LLMGATEWAY_CONFIG_PATH}. Fill provider base_url and api_key before running archi."
}

write_auth_preferences() {
  mkdir -p "${AUTH_STATE_DIR}"
  case "${LOGIN_METHOD}" in
    browser|activation_code) ;;
    *) LOGIN_METHOD="browser" ;;
  esac
  cat >"${AUTH_PREFERENCES_PATH}" <<JSON
{
  "login_method": "${LOGIN_METHOD}"
}
JSON
  chmod 600 "${AUTH_PREFERENCES_PATH}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --install-base)
      INSTALL_BASE="${2:-}"
      shift 2
      ;;
    --bin-dir)
      BIN_DIR="${2:-}"
      shift 2
      ;;
    --os)
      RAW_OS_NAME="${2:-}"
      shift 2
      ;;
    --arch)
      RAW_ARCH_NAME="${2:-}"
      shift 2
      ;;
    --asset-name)
      ASSET_NAME="${2:-}"
      shift 2
      ;;
    --skip-checksum)
      VERIFY_CHECKSUMS="0"
      shift
      ;;
    --configure-llm|--skip-llm-config)
      shift
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

need_cmd curl

OS_NAME="$(normalize_os "${RAW_OS_NAME}")"
ARCH_NAME="$(normalize_arch "${RAW_ARCH_NAME}")"
TRIPLET="$(platform_triplet "${OS_NAME}" "${ARCH_NAME}")"

if [[ -z "${BASE_URL}" ]]; then
  VERSION="$(resolve_latest_version "${VERSION}")"
else
  VERSION="$(normalize_version "${VERSION}")"
  [[ -n "${VERSION}" && "${VERSION}" != "latest" ]] || die "--version is required when --base-url is used"
fi

if [[ -z "${ASSET_NAME}" ]]; then
  ASSET_NAME="$(asset_name_for "${VERSION}" "${TRIPLET}")"
fi
CHECKSUMS_NAME="$(checksum_name_for "${VERSION}")"

if [[ -z "${BASE_URL}" ]]; then
  BASE_URL="https://github.com/${REPO}/releases/download/v${VERSION}"
fi
BASE_URL="${BASE_URL%/}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

DOWNLOAD_PATH="${TMP_DIR}/${ASSET_NAME}"
CHECKSUMS_PATH="${TMP_DIR}/${CHECKSUMS_NAME}"
BINARY_NAME="archi"
if [[ "${OS_NAME}" == "win32" ]]; then
  BINARY_NAME="archi.exe"
fi

say "Installing Architec ${VERSION} from GitHub Release assets"
say "Target platform: ${TRIPLET}"
say "Downloading ${ASSET_NAME}"
curl -fL "$(join_url "${BASE_URL}" "${ASSET_NAME}")" -o "${DOWNLOAD_PATH}"

if [[ "${VERIFY_CHECKSUMS}" != "0" ]]; then
  say "Downloading ${CHECKSUMS_NAME}"
  curl -fL "$(join_url "${BASE_URL}" "${CHECKSUMS_NAME}")" -o "${CHECKSUMS_PATH}"
  verify_checksum "${DOWNLOAD_PATH}" "${CHECKSUMS_PATH}" "${ASSET_NAME}"
  say "Checksum verification passed"
else
  say "Checksum verification skipped"
fi

TARGET_DIR="${INSTALL_BASE}/${TRIPLET}"
rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}" "${BIN_DIR}"
cp "${DOWNLOAD_PATH}" "${TARGET_DIR}/${BINARY_NAME}"
chmod 755 "${TARGET_DIR}/${BINARY_NAME}"
if ! ln -sf "${TARGET_DIR}/${BINARY_NAME}" "${BIN_DIR}/archi" 2>/dev/null; then
  cp -f "${TARGET_DIR}/${BINARY_NAME}" "${BIN_DIR}/archi"
fi

write_architec_config_if_missing
write_hippocampus_config_if_missing
write_gateway_config_if_missing
write_auth_preferences

say "Installed Architec ${VERSION} to ${TARGET_DIR}"
say "Installed launcher ${BIN_DIR}/archi"
say "LLMGateway config: ${LLMGATEWAY_CONFIG_PATH}"
say "Project: https://github.com/${REPO}"
say "More info: https://github.com/${REPO}#readme"
say "Next step: archi --version"
