#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="${ROOT_DIR}/tools/install_prod.sh"
VERSION="0.0.0-smoke"
TRIPLET="linux-x64"
ASSET_NAME="archi-v${VERSION}-${TRIPLET}"
CHECKSUMS_NAME="archi-v${VERSION}-checksums.txt"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

RELEASE_DIR="${TMP_DIR}/release"
mkdir -p "${RELEASE_DIR}"
cat >"${RELEASE_DIR}/${ASSET_NAME}" <<'SH'
#!/usr/bin/env bash
echo "archi smoke"
SH
chmod +x "${RELEASE_DIR}/${ASSET_NAME}"
(
  cd "${RELEASE_DIR}"
  sha256sum "${ASSET_NAME}" >"${CHECKSUMS_NAME}"
)

run_installer() {
  local home_dir="$1"
  shift
  HOME="${home_dir}" \
    bash "${INSTALLER}" \
      --version "${VERSION}" \
      --base-url "file://${RELEASE_DIR}" \
      --install-base "${home_dir}/install" \
      --bin-dir "${home_dir}/bin" \
      --os linux \
      --arch x64 \
      "$@" >/dev/null
}

missing_home="${TMP_DIR}/missing-home"
run_installer "${missing_home}"
"${missing_home}/bin/archi" | grep -q "archi smoke"

starter_config="${missing_home}/.llmgateway/config.yaml"
if [[ ! -f "${starter_config}" ]]; then
  echo "starter llmgateway config was not created" >&2
  exit 1
fi

mode="$(python3 - "${starter_config}" <<'PY'
import os
import sys

print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])
PY
)"
if [[ "${mode}" != "600" ]]; then
  echo "starter llmgateway config mode is ${mode}, expected 600" >&2
  exit 1
fi

for needle in \
  "providers:" \
  "provider_type:" \
  "api_style:" \
  "base_url:" \
  "api_key:" \
  "headers:" \
  "model_map:" \
  "Optional fallback provider example" \
  "ARCHITEC_LLM_SECONDARY_BASE_URL" \
  "fallback_model:" \
  "strong_model:" \
  "weak_model:" \
  "strong_reasoning_effort:" \
  "weak_reasoning_effort:" \
  "max_concurrent:" \
  "retry_max:" \
  "transport_retries:" \
  "timeout:"; do
  if ! grep -q "${needle}" "${starter_config}"; then
    echo "starter llmgateway config missing ${needle}" >&2
    exit 1
  fi
done

existing_home="${TMP_DIR}/existing-home"
existing_config="${existing_home}/.llmgateway/config.yaml"
mkdir -p "$(dirname "${existing_config}")"
cat >"${existing_config}" <<'YAML'
sentinel: keep-this-file-byte-for-byte
provider:
  api_key: sentinel-not-a-real-secret
YAML
before_hash="$(sha256sum "${existing_config}" | awk '{print $1}')"

architec_llm_main_url="https://env.example.invalid" \
  architec_llm_main_api_key="env-value-must-not-overwrite" \
  run_installer "${existing_home}" --configure-llm

after_hash="$(sha256sum "${existing_config}" | awk '{print $1}')"
if [[ "${before_hash}" != "${after_hash}" ]]; then
  echo "existing llmgateway config changed" >&2
  exit 1
fi

PYTHONPATH="${ROOT_DIR}/src" python3 - "${starter_config}" <<'PY'
import sys
from pathlib import Path
import yaml

payload = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert isinstance(payload.get("providers"), list)
assert payload["providers"][0]["provider_type"] == "openai"
assert payload["settings"]["fallback_model"] == "gpt-5.4-mini"
assert payload["settings"]["transport_retries"] == 2
PY

echo "install_prod smoke passed"
