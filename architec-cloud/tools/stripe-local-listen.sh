#!/usr/bin/env bash
set -euo pipefail

APP_URL="${ARCHITEC_CLOUD_APP_URL:-http://127.0.0.1:3000}"
FORWARD_URL="${APP_URL%/}/api/webhooks/stripe"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_STRIPE="${ROOT_DIR}/tools/bin/stripe"

if [[ -x "${LOCAL_STRIPE}" ]]; then
  STRIPE_BIN="${LOCAL_STRIPE}"
elif command -v stripe >/dev/null 2>&1; then
  STRIPE_BIN="$(command -v stripe)"
else
  echo "stripe CLI is not installed."
  echo "Run ./tools/install-stripe-cli.sh or install it from https://docs.stripe.com/stripe-cli."
  exit 1
fi

cat <<EOF
Starting Stripe local listener.

Forward target:
  ${FORWARD_URL}

After the CLI prints a webhook signing secret, export it in another shell:

  export ARCHITEC_CLOUD_STRIPE_WEBHOOK_SECRET=whsec_...

Then restart the Next.js server so webhook verification uses the new secret.
EOF

"${STRIPE_BIN}" listen --forward-to "${FORWARD_URL}"
