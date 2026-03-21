#!/usr/bin/env bash

set -euo pipefail

base_url="${ARCHITEC_CLOUD_APP_URL:-http://127.0.0.1:3000}"
tmp_dir="$(mktemp -d)"
cookie_jar="${tmp_dir}/cookies.txt"
headers_file="${tmp_dir}/headers.txt"
email="smoke.$(date +%s).$RANDOM@example.com"
password="SmokePass123!"

cleanup() {
  rm -rf "${tmp_dir}"
}

trap cleanup EXIT

assert_redirect_contains() {
  local path="$1"
  local expected="$2"

  curl -sS -D "${headers_file}" -o /dev/null "${base_url}${path}"
  if ! tr -d '\r' < "${headers_file}" | grep -qi "^location: .*${expected}"; then
    echo "Expected redirect from ${path} to contain ${expected}" >&2
    cat "${headers_file}" >&2
    exit 1
  fi
}

assert_page_ok() {
  local path="$1"
  curl -fsS "${base_url}${path}" > /dev/null
}

echo "Checking public pages at ${base_url}"
assert_page_ok "/"
assert_page_ok "/support"
assert_page_ok "/status"
assert_page_ok "/legal/privacy"
assert_page_ok "/legal/terms"

echo "Checking protected redirect"
assert_redirect_contains "/account" "/login"

echo "Registering ${email}"
curl -fsS \
  -D "${headers_file}" \
  -c "${cookie_jar}" \
  -b "${cookie_jar}" \
  -o /dev/null \
  -X POST \
  -H "content-type: application/x-www-form-urlencoded" \
  --data-urlencode "email=${email}" \
  --data-urlencode "password=${password}" \
  "${base_url}/api/auth/register"

if ! tr -d '\r' < "${headers_file}" | grep -qi "^location: .*\/account"; then
  echo "Registration did not redirect to /account" >&2
  cat "${headers_file}" >&2
  exit 1
fi

account_html="$(curl -fsS -b "${cookie_jar}" "${base_url}/account")"
if ! printf "%s" "${account_html}" | grep -q "${email}"; then
  echo "Account page does not include the registered email" >&2
  exit 1
fi

echo "Logging out"
curl -fsS \
  -D "${headers_file}" \
  -c "${cookie_jar}" \
  -b "${cookie_jar}" \
  -o /dev/null \
  -X POST \
  "${base_url}/api/auth/logout"

if ! tr -d '\r' < "${headers_file}" | grep -Eqi "^location: (https?://[^[:space:]]+/|/)$"; then
  echo "Logout did not redirect to home" >&2
  cat "${headers_file}" >&2
  exit 1
fi

echo "Logging back in"
curl -fsS \
  -D "${headers_file}" \
  -c "${cookie_jar}" \
  -b "${cookie_jar}" \
  -o /dev/null \
  -X POST \
  -H "content-type: application/x-www-form-urlencoded" \
  --data-urlencode "email=${email}" \
  --data-urlencode "password=${password}" \
  "${base_url}/api/auth/login"

if ! tr -d '\r' < "${headers_file}" | grep -qi "^location: .*\/account"; then
  echo "Login did not redirect to /account" >&2
  cat "${headers_file}" >&2
  exit 1
fi

echo "Smoke checks passed"
