#!/usr/bin/env bash

set -euo pipefail

REPO="${ARCHITEC_RELEASE_REPO:-bfly123/architec-releases}"
VERSION="${ARCHITEC_VERSION:-latest}"
INSTALL_BASE="${ARCHITEC_INSTALL_BASE:-$HOME/.local/architec}"
BIN_DIR="${ARCHITEC_BIN_DIR:-$HOME/.local/bin}"
VERIFY_CHECKSUMS="${ARCHITEC_VERIFY_CHECKSUMS:-1}"
RAW_OS_NAME="${ARCHITEC_TARGET_OS:-$(uname -s)}"
RAW_ARCH_NAME="${ARCHITEC_TARGET_ARCH:-$(uname -m)}"
OS_NAME=""
ARCH_NAME=""
ASSET_NAME="${ARCHITEC_ASSET_NAME:-}"

usage() {
  cat <<'EOF'
Usage: install_prod.sh [options]

Install the compiled Architec release artifact from GitHub Releases.

Options:
  --version <tag|latest>     Release tag to install. Default: latest
  --repo <owner/name>        Release repository. Default: bfly123/architec-releases
  --install-base <path>      Installation base directory. Default: ~/.local/architec
  --bin-dir <path>           Directory where the archi symlink is created. Default: ~/.local/bin
  --os <name>                Override detected operating system
  --arch <name>              Override detected architecture
  --asset-name <name>        Override the release asset name
  --skip-checksum            Skip SHA256SUMS verification
  --help                     Show this message

Environment overrides:
  ARCHITEC_RELEASE_REPO
  ARCHITEC_VERSION
  ARCHITEC_INSTALL_BASE
  ARCHITEC_BIN_DIR
  ARCHITEC_TARGET_OS
  ARCHITEC_TARGET_ARCH
  ARCHITEC_ASSET_NAME
  ARCHITEC_VERIFY_CHECKSUMS=0
EOF
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

normalize_os() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    linux)
      printf 'linux'
      ;;
    darwin|macos|macosx|osx)
      printf 'macos'
      ;;
    mingw*|msys*|cygwin*|windows|win32|win64)
      printf 'windows'
      ;;
    *)
      printf '%s' "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
      ;;
  esac
}

normalize_arch() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    x86_64|amd64)
      printf 'x86_64'
      ;;
    arm64|aarch64)
      printf 'arm64'
      ;;
    *)
      printf '%s' "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
      ;;
  esac
}

default_asset_name() {
  if [[ "$1" == "windows" ]]; then
    printf 'archi-%s-%s.zip' "$1" "$2"
  else
    printf 'archi-%s-%s.tar.gz' "$1" "$2"
  fi
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
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

OS_NAME="$(normalize_os "${RAW_OS_NAME}")"
ARCH_NAME="$(normalize_arch "${RAW_ARCH_NAME}")"
if [[ -z "${ASSET_NAME}" ]]; then
  ASSET_NAME="$(default_asset_name "${OS_NAME}" "${ARCH_NAME}")"
fi

if [[ -z "${VERSION}" || -z "${REPO}" || -z "${INSTALL_BASE}" || -z "${BIN_DIR}" || -z "${ASSET_NAME}" ]]; then
  echo "Version, repo, install base, bin dir, and asset name must be non-empty." >&2
  exit 2
fi

need_cmd curl
need_cmd python3
if [[ "${ASSET_NAME}" == *.tar.gz ]]; then
  need_cmd tar
fi

if [[ "${VERSION}" == "latest" ]]; then
  API_URL="https://api.github.com/repos/${REPO}/releases/latest"
else
  API_URL="https://api.github.com/repos/${REPO}/releases/tags/${VERSION}"
fi

echo "Resolving Architec release metadata from ${REPO} (${VERSION})"
RELEASE_JSON="$(curl -fsSL "${API_URL}")"

read -r RELEASE_TAG DOWNLOAD_URL CHECKSUMS_URL < <(
  RELEASE_JSON="${RELEASE_JSON}" python3 - "${ASSET_NAME}" <<'PY'
import json
import os
import sys

asset_name = sys.argv[1]
payload = json.loads(os.environ["RELEASE_JSON"])
tag_name = str(payload.get("tag_name", "") or "").strip()
download_url = ""
checksums_url = ""

for item in payload.get("assets", []):
    name = str(item.get("name", "") or "").strip()
    url = str(item.get("browser_download_url", "") or "").strip()
    if name == asset_name:
        download_url = url
    elif name == "SHA256SUMS.txt":
        checksums_url = url

if not tag_name:
    raise SystemExit("release tag missing from GitHub API response")
if not download_url:
    raise SystemExit(f"release asset not found: {asset_name}")

print(tag_name, download_url, checksums_url)
PY
)

if [[ -z "${RELEASE_TAG}" || -z "${DOWNLOAD_URL}" ]]; then
  echo "Failed to resolve release tag or download URL." >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

mkdir -p "${INSTALL_BASE}" "${BIN_DIR}"
ARCHIVE_PATH="${TMP_DIR}/${ASSET_NAME}"
CHECKSUMS_PATH="${TMP_DIR}/SHA256SUMS.txt"

echo "Downloading ${ASSET_NAME} from ${RELEASE_TAG}"
curl -fL "${DOWNLOAD_URL}" -o "${ARCHIVE_PATH}"

if [[ "${VERIFY_CHECKSUMS}" != "0" ]]; then
  if [[ -z "${CHECKSUMS_URL}" ]]; then
    echo "SHA256SUMS.txt not found on release ${RELEASE_TAG}; refusing to continue." >&2
    echo "Use --skip-checksum only if you intentionally want to bypass verification." >&2
    exit 1
  fi
  echo "Downloading SHA256SUMS.txt for verification"
  curl -fL "${CHECKSUMS_URL}" -o "${CHECKSUMS_PATH}"
  python3 - "${ARCHIVE_PATH}" "${CHECKSUMS_PATH}" "${ASSET_NAME}" <<'PY'
import hashlib
import sys
from pathlib import Path

archive_path = Path(sys.argv[1])
checksums_path = Path(sys.argv[2])
asset_name = sys.argv[3]

expected = ""
for raw in checksums_path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    parts = line.split()
    if len(parts) >= 2 and parts[-1] == asset_name:
        expected = parts[0].strip()
        break

if not expected:
    raise SystemExit(f"checksum entry not found for {asset_name}")

digest = hashlib.sha256()
with archive_path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)

actual = digest.hexdigest()
if actual != expected:
    raise SystemExit(
        f"checksum mismatch for {asset_name}: expected {expected}, got {actual}"
    )
PY
  echo "Checksum verification passed"
else
  echo "Checksum verification skipped"
fi

if [[ "${ASSET_NAME}" == *.zip ]]; then
  python3 - "${ARCHIVE_PATH}" "${TMP_DIR}" <<'PY'
from pathlib import Path
import sys
import zipfile

archive_path = Path(sys.argv[1])
target_dir = Path(sys.argv[2])

with zipfile.ZipFile(archive_path) as archive:
    archive.extractall(target_dir)
PY
else
  tar -xzf "${ARCHIVE_PATH}" -C "${TMP_DIR}"
fi

PACKAGE_DIR="${TMP_DIR}/archi-${OS_NAME}-${ARCH_NAME}"
if [[ ! -d "${PACKAGE_DIR}" ]]; then
  echo "Extracted package not found: ${PACKAGE_DIR}" >&2
  exit 1
fi

BINARY_NAME="archi"
if [[ "${OS_NAME}" == "windows" ]]; then
  BINARY_NAME="archi.exe"
fi

TARGET_DIR="${INSTALL_BASE}/${OS_NAME}-${ARCH_NAME}"
rm -rf "${TARGET_DIR}"
mkdir -p "${INSTALL_BASE}"
mv "${PACKAGE_DIR}" "${TARGET_DIR}"
if [[ ! -f "${TARGET_DIR}/${BINARY_NAME}" ]]; then
  echo "Installed binary is missing: ${TARGET_DIR}/${BINARY_NAME}" >&2
  exit 1
fi
if ! ln -sf "${TARGET_DIR}/${BINARY_NAME}" "${BIN_DIR}/archi" 2>/dev/null; then
  cp -f "${TARGET_DIR}/${BINARY_NAME}" "${BIN_DIR}/archi"
fi

echo "Installed Architec ${RELEASE_TAG} to ${TARGET_DIR}"
echo "Installed launcher ${BIN_DIR}/archi"
echo "Binary: ${TARGET_DIR}/${BINARY_NAME}"
echo "Next step: archi login"
