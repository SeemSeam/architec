#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BUILD_ROOT="${ARCHITEC_BUILD_ROOT:-$ROOT_DIR/build/nuitka}"
DIST_DIR="${ARCHITEC_DIST_DIR:-$ROOT_DIR/dist}"
ENTRYPOINT="${ROOT_DIR}/tools/archi_entry.py"
LLMGATEWAY_SRC="${ARCHITEC_LLMGATEWAY_SRC:-$ROOT_DIR/../llmgateway/src}"
VERSION="$("${PYTHON_BIN}" - <<'PY'
import tomllib
from pathlib import Path

payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(payload["project"]["version"])
PY
)"
RAW_OS_NAME="${ARCHITEC_TARGET_OS:-$(uname -s)}"
RAW_ARCH_NAME="${ARCHITEC_TARGET_ARCH:-$(uname -m)}"

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

OS_NAME="$(normalize_os "${RAW_OS_NAME}")"
ARCH_NAME="$(normalize_arch "${RAW_ARCH_NAME}")"
PACKAGE_NAME="archi-${OS_NAME}-${ARCH_NAME}"
if [[ "${OS_NAME}" == "windows" ]]; then
  ASSET_NAME="${PACKAGE_NAME}.zip"
else
  ASSET_NAME="${PACKAGE_NAME}.tar.gz"
fi

cd "${ROOT_DIR}"

if [[ -d "${LLMGATEWAY_SRC}/llmgateway" ]]; then
  export PYTHONPATH="${LLMGATEWAY_SRC}:${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"
fi

if ! "${PYTHON_BIN}" -m nuitka --version >/dev/null 2>&1; then
  echo "Nuitka is not installed in ${PYTHON_BIN}. Install it with:" >&2
  echo "  ${PYTHON_BIN} -m pip install nuitka ordered-set zstandard" >&2
  exit 1
fi

rm -rf "${BUILD_ROOT}"
mkdir -p "${BUILD_ROOT}" "${DIST_DIR}"

"${PYTHON_BIN}" -m nuitka \
  --standalone \
  --assume-yes-for-downloads \
  --follow-imports \
  --static-libpython=no \
  --nofollow-import-to=litellm \
  --nofollow-import-to=torch \
  --nofollow-import-to=matplotlib \
  --include-data-dir="${ROOT_DIR}/config=config" \
  --include-data-dir="${ROOT_DIR}/prompts=prompts" \
  --output-dir="${BUILD_ROOT}" \
  --output-filename=archi \
  "${ENTRYPOINT}"

DIST_BUNDLE_DIR="$(
  find "${BUILD_ROOT}" -maxdepth 1 -type d -name '*.dist' | head -n 1
)"
if [[ -z "${DIST_BUNDLE_DIR}" || ! -d "${DIST_BUNDLE_DIR}" ]]; then
  echo "Expected Nuitka output directory not found under: ${BUILD_ROOT}" >&2
  exit 1
fi

PACKAGE_ROOT="${BUILD_ROOT}/${PACKAGE_NAME}"
mkdir -p "${PACKAGE_ROOT}"
cp -R "${DIST_BUNDLE_DIR}/." "${PACKAGE_ROOT}/"

RUN_HINT="./archi"
if [[ "${OS_NAME}" == "windows" ]]; then
  RUN_HINT="./archi.exe"
fi

cat > "${PACKAGE_ROOT}/INSTALL.txt" <<EOF
Architec ${VERSION} compiled ${OS_NAME}/${ARCH_NAME} build

Install:
1. Extract this archive.
2. Copy the archi executable directory contents to a stable location.
3. Run ${RUN_HINT} --help to verify the binary starts.
4. Run ${RUN_HINT} login to bind the machine to your Architec account.

Notes:
- This build bundles Architec code as a compiled binary distribution.
- Runtime config still lives under ~/.architec and ~/.llmgateway unless overridden.
EOF

"${PYTHON_BIN}" - "${BUILD_ROOT}" "${PACKAGE_NAME}" "${DIST_DIR}/${ASSET_NAME}" "${OS_NAME}" <<'PY'
import shutil
import sys
from pathlib import Path

build_root = Path(sys.argv[1])
package_name = sys.argv[2]
asset_path = Path(sys.argv[3])
os_name = sys.argv[4]
package_dir = build_root / package_name

asset_path.parent.mkdir(parents=True, exist_ok=True)
if asset_path.exists():
    asset_path.unlink()

base_name = str(asset_path)
for suffix in (".tar.gz", ".zip"):
    if base_name.endswith(suffix):
        base_name = base_name[: -len(suffix)]
        break

archive_format = "zip" if os_name == "windows" else "gztar"
created = shutil.make_archive(base_name, archive_format, root_dir=build_root, base_dir=package_name)
print(created)
PY

echo "Built compiled artifact: ${DIST_DIR}/${ASSET_NAME}"
