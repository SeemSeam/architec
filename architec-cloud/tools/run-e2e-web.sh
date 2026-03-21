#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"

rm -rf .data-e2e
mkdir -p .data-e2e

export ARCHITEC_CLOUD_APP_URL="${ARCHITEC_CLOUD_APP_URL:-http://127.0.0.1:3100}"
export ARCHITEC_CLOUD_DATA_DIR="${ARCHITEC_CLOUD_DATA_DIR:-.data-e2e}"
export ARCHITEC_CLOUD_SUPPORT_EMAIL="${ARCHITEC_CLOUD_SUPPORT_EMAIL:-support@example.com}"
export ARCHITEC_CLOUD_CLI_MIN_VERSION="${ARCHITEC_CLOUD_CLI_MIN_VERSION:-0.1.0}"
export ARCHITEC_CLOUD_GITHUB_REPO_URL="${ARCHITEC_CLOUD_GITHUB_REPO_URL:-https://github.com/bfly123/architec-releases}"
export ARCHITEC_CLOUD_GITHUB_RELEASES_URL="${ARCHITEC_CLOUD_GITHUB_RELEASES_URL:-https://github.com/bfly123/architec-releases/releases}"
export ARCHITEC_CLOUD_GITHUB_LATEST_RELEASE_URL="${ARCHITEC_CLOUD_GITHUB_LATEST_RELEASE_URL:-https://github.com/bfly123/architec-releases/releases/latest}"
export ARCHITEC_CLOUD_GITHUB_LATEST_LINUX_X64_URL="${ARCHITEC_CLOUD_GITHUB_LATEST_LINUX_X64_URL:-https://github.com/bfly123/architec-releases/releases/latest/download/archi-linux-x86_64.tar.gz}"
export ARCHITEC_CLOUD_GITHUB_LATEST_INSTALL_SCRIPT_URL="${ARCHITEC_CLOUD_GITHUB_LATEST_INSTALL_SCRIPT_URL:-https://github.com/bfly123/architec-releases/releases/latest/download/install_prod.sh}"
export ARCHITEC_CLOUD_GITHUB_LATEST_CHECKSUMS_URL="${ARCHITEC_CLOUD_GITHUB_LATEST_CHECKSUMS_URL:-https://github.com/bfly123/architec-releases/releases/latest/download/SHA256SUMS.txt}"
export ARCHITEC_CLOUD_RATE_LIMIT_REGISTER_IP="${ARCHITEC_CLOUD_RATE_LIMIT_REGISTER_IP:-200}"
export ARCHITEC_CLOUD_RATE_LIMIT_REGISTER_EMAIL="${ARCHITEC_CLOUD_RATE_LIMIT_REGISTER_EMAIL:-50}"
export ARCHITEC_CLOUD_RATE_LIMIT_LOGIN_IP="${ARCHITEC_CLOUD_RATE_LIMIT_LOGIN_IP:-200}"
export ARCHITEC_CLOUD_RATE_LIMIT_LOGIN_EMAIL="${ARCHITEC_CLOUD_RATE_LIMIT_LOGIN_EMAIL:-50}"

exec pnpm exec next start --hostname 127.0.0.1 --port 3100
