#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${ROOT_DIR}/tools/bin"
TARGET="${BIN_DIR}/stripe"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

mkdir -p "${BIN_DIR}"

ARCH="$(uname -m)"
case "${ARCH}" in
  x86_64|amd64)
    CLI_ARCH="linux_x86_64"
    ;;
  aarch64|arm64)
    CLI_ARCH="linux_arm64"
    ;;
  *)
    echo "Unsupported architecture: ${ARCH}"
    exit 1
    ;;
esac

LATEST_JSON="$(curl -fsSL https://api.github.com/repos/stripe/stripe-cli/releases/latest)"
DOWNLOAD_URL="$(printf '%s' "${LATEST_JSON}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
tag = data.get("tag_name", "")
version = tag[1:] if tag.startswith("v") else tag
want = f"stripe_{version}_{sys.argv[1]}.tar.gz"
for asset in data.get("assets", []):
    if asset.get("name") == want:
        print(asset["browser_download_url"])
        break
else:
    raise SystemExit(f"Stripe CLI release asset not found for {want}")
' "${CLI_ARCH}")"

echo "Downloading Stripe CLI for ${CLI_ARCH}"
curl -fsSL "${DOWNLOAD_URL}" -o "${TMP_DIR}/stripe.tar.gz"
tar -xzf "${TMP_DIR}/stripe.tar.gz" -C "${TMP_DIR}"

if [[ ! -x "${TMP_DIR}/stripe" ]]; then
  echo "Stripe CLI binary was not found in the downloaded archive."
  exit 1
fi

mv "${TMP_DIR}/stripe" "${TARGET}"
chmod +x "${TARGET}"

echo "Installed Stripe CLI to ${TARGET}"
"${TARGET}" version
