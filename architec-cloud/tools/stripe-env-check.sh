#!/usr/bin/env bash
set -euo pipefail

missing=0
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_STRIPE="${ROOT_DIR}/tools/bin/stripe"

check_var() {
  local name="$1"
  local value="${!name:-}"
  if [[ -n "$value" ]]; then
    printf '[ok] %s is set\n' "$name"
  else
    printf '[missing] %s is not set\n' "$name"
    missing=1
  fi
}

echo "Stripe environment readiness"
echo

check_var ARCHITEC_CLOUD_STRIPE_SECRET_KEY
check_var ARCHITEC_CLOUD_STRIPE_PUBLISHABLE_KEY
check_var ARCHITEC_CLOUD_STRIPE_PRICE_ID_MONTHLY
check_var ARCHITEC_CLOUD_STRIPE_WEBHOOK_SECRET

echo
if [[ -x "${LOCAL_STRIPE}" ]]; then
  echo "[ok] stripe CLI is installed at ${LOCAL_STRIPE}"
elif command -v stripe >/dev/null 2>&1; then
  echo "[ok] stripe CLI is installed"
else
  echo "[missing] stripe CLI is not installed"
  missing=1
fi

echo
if [[ $missing -eq 0 ]]; then
  echo "Ready to test real Stripe checkout locally."
  exit 0
fi

echo "Stripe live testing is not fully configured yet."
exit 1
