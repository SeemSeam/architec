#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_CONFIG_BASE="${ARCHITEC_USER_CONFIG_DIR:-$HOME/.architec}"
STATE_DIR="$USER_CONFIG_BASE"
if [[ -n "${ARCHITEC_LLM_CONFIG:-}" ]]; then
  LLM_CONFIG_PATH="${ARCHITEC_LLM_CONFIG}"
else
  LLM_CONFIG_PATH="$STATE_DIR/config.yaml"
fi
LLM_CONFIG_BASE="$(dirname "$LLM_CONFIG_PATH")"

LLMGATEWAY_USER_CONFIG_BASE="${LLMGATEWAY_USER_CONFIG_DIR:-$HOME/.llmgateway}"
if [[ -n "${LLMGATEWAY_CONFIG:-}" ]]; then
  LLMGATEWAY_CONFIG_PATH="${LLMGATEWAY_CONFIG}"
else
  LLMGATEWAY_CONFIG_PATH="$LLMGATEWAY_USER_CONFIG_BASE/config.yaml"
fi
LLMGATEWAY_CONFIG_BASE="$(dirname "$LLMGATEWAY_CONFIG_PATH")"

LLMGATEWAY_LOCAL_PATH="${LLMGATEWAY_LOCAL_PATH:-$ROOT_DIR/../llmgateway}"
LLMGATEWAY_GIT_URL="${LLMGATEWAY_GIT_URL:-git+https://github.com/bfly123/llmgateway.git@main}"
CODEX_SKILLS_BASE="${CODEX_SKILLS_DIR:-$HOME/.codex/skills}"
CLAUDE_SKILLS_BASE="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

is_interactive() {
  [[ -t 0 && -t 1 ]]
}

prompt_required() {
  local var_name="$1"
  local prompt_text="$2"
  local secret="${3:-0}"
  local value="${!var_name:-}"

  if [[ -n "$value" ]]; then
    printf -v "$var_name" '%s' "$value"
    return 0
  fi

  if ! is_interactive; then
    echo "$var_name is required. Re-run install with $var_name set in the environment." >&2
    exit 1
  fi

  while [[ -z "$value" ]]; do
    if [[ "$secret" == "1" ]]; then
      read -r -s -p "$prompt_text" value
      echo
    else
      read -r -p "$prompt_text" value
    fi
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
  done

  printf -v "$var_name" '%s' "$value"
}

prompt_with_default() {
  local var_name="$1"
  local prompt_text="$2"
  local default_value="${3:-}"
  local value="${!var_name:-}"

  if [[ -n "$value" ]]; then
    printf -v "$var_name" '%s' "$value"
    return 0
  fi

  if ! is_interactive; then
    printf -v "$var_name" '%s' "$default_value"
    return 0
  fi

  read -r -p "$prompt_text" value
  if [[ -z "$value" ]]; then
    value="$default_value"
  fi
  printf -v "$var_name" '%s' "$value"
}

load_existing_gateway_config() {
  if [[ ! -f "$LLMGATEWAY_CONFIG_PATH" ]]; then
    return 0
  fi

  local loaded=""
  loaded="$(python3 - "$LLMGATEWAY_CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

from llmgateway.config import load_user_config, runtime_spec_from_dict

path = Path(sys.argv[1])
raw = load_user_config(path)
if not raw:
    print("\t\t\t\t\t\t\t\t\t\t")
    raise SystemExit(0)
runtime = runtime_spec_from_dict(raw)
print(
    "\t".join(
        [
            str(runtime.provider.provider_type or "").strip(),
            str(runtime.provider.api_style or "").strip(),
            str(runtime.provider.base_url or "").strip(),
            str(runtime.provider.api_key or "").strip(),
            str(runtime.max_concurrent or "").strip(),
            json.dumps(dict(runtime.provider.model_map or {}), ensure_ascii=True, sort_keys=True),
            str(runtime.retry_max or "").strip(),
            str(runtime.timeout or "").strip(),
            str(runtime.strong_model or "").strip(),
            str(runtime.weak_model or "").strip(),
            str(runtime.strong_reasoning_effort or "").strip().lower(),
            str(runtime.weak_reasoning_effort or "").strip().lower(),
        ]
    )
)
PY
)"

  local loaded_provider_type loaded_api_style loaded_url loaded_key loaded_max_concurrent loaded_model_map loaded_retry_max loaded_timeout loaded_strong_model loaded_weak_model loaded_strong_effort loaded_weak_effort
  IFS=$'\t' read -r loaded_provider_type loaded_api_style loaded_url loaded_key loaded_max_concurrent loaded_model_map loaded_retry_max loaded_timeout loaded_strong_model loaded_weak_model loaded_strong_effort loaded_weak_effort <<<"$loaded"
  if [[ -z "${gateway_provider_type:-}" && -n "$loaded_provider_type" ]]; then
    gateway_provider_type="$loaded_provider_type"
  fi
  if [[ -z "${gateway_api_style:-}" && -n "$loaded_api_style" ]]; then
    gateway_api_style="$loaded_api_style"
  fi
  if [[ -z "${gateway_base_url:-}" && -n "$loaded_url" ]]; then
    gateway_base_url="$loaded_url"
  fi
  if [[ -z "${gateway_api_key:-}" && -n "$loaded_key" ]]; then
    gateway_api_key="$loaded_key"
  fi
  if [[ -z "${gateway_max_concurrent:-}" && -n "$loaded_max_concurrent" ]]; then
    gateway_max_concurrent="$loaded_max_concurrent"
  fi
  if [[ -z "${gateway_model_map_json:-}" && -n "$loaded_model_map" ]]; then
    gateway_model_map_json="$loaded_model_map"
  fi
  if [[ -z "${gateway_retry_max:-}" && -n "$loaded_retry_max" ]]; then
    gateway_retry_max="$loaded_retry_max"
  fi
  if [[ -z "${gateway_timeout:-}" && -n "$loaded_timeout" ]]; then
    gateway_timeout="$loaded_timeout"
  fi
  if [[ -z "${architec_llm_strong_model:-}" && -n "$loaded_strong_model" ]]; then
    architec_llm_strong_model="$loaded_strong_model"
  fi
  if [[ -z "${architec_llm_weak_model:-}" && -n "$loaded_weak_model" ]]; then
    architec_llm_weak_model="$loaded_weak_model"
  fi
  if [[ -z "${architec_llm_strong_reasoning_effort:-}" && -n "$loaded_strong_effort" ]]; then
    architec_llm_strong_reasoning_effort="$loaded_strong_effort"
  fi
  if [[ -z "${architec_llm_weak_reasoning_effort:-}" && -n "$loaded_weak_effort" ]]; then
    architec_llm_weak_reasoning_effort="$loaded_weak_effort"
  fi
}

write_gateway_config() {
  mkdir -p "$LLMGATEWAY_CONFIG_BASE"
  python3 - "$LLMGATEWAY_CONFIG_PATH" "$gateway_provider_type" "$gateway_api_style" "$gateway_base_url" "$gateway_api_key" "$gateway_max_concurrent" "$gateway_model_map_json" "$gateway_retry_max" "$gateway_timeout" "$architec_llm_strong_model" "$architec_llm_weak_model" "$architec_llm_strong_reasoning_effort" "$architec_llm_weak_reasoning_effort" <<'PY'
import json
import sys
from pathlib import Path

from llmgateway.config import write_user_config

config_path = Path(sys.argv[1])
provider_type = str(sys.argv[2] or "").strip()
api_style = str(sys.argv[3] or "").strip()
base_url = str(sys.argv[4] or "").strip()
api_key = str(sys.argv[5] or "").strip()
max_concurrent = max(1, int(sys.argv[6] or 12))
model_map = json.loads(sys.argv[7]) if len(sys.argv) > 7 and sys.argv[7] else {}
if not isinstance(model_map, dict):
    model_map = {}
retry_max = max(0, int(sys.argv[8] or 3))
timeout = float(sys.argv[9] or 90)
strong_model = str(sys.argv[10] or "").strip()
weak_model = str(sys.argv[11] or "").strip()
strong_reasoning_effort = str(sys.argv[12] or "").strip().lower()
weak_reasoning_effort = str(sys.argv[13] or "").strip().lower()

write_user_config(
    {
        "version": 1,
        "provider": {
            "provider_type": provider_type,
            "api_style": api_style,
            "base_url": base_url,
            "api_key": api_key,
            "headers": {},
            "model_map": model_map,
        },
        "settings": {
            "strong_model": strong_model,
            "weak_model": weak_model,
            "strong_reasoning_effort": strong_reasoning_effort,
            "weak_reasoning_effort": weak_reasoning_effort,
            "max_concurrent": max_concurrent,
            "retry_max": retry_max,
            "timeout": timeout,
        },
    },
    config_path,
)
PY
  chmod 600 "$LLMGATEWAY_CONFIG_PATH"
}

write_architec_config() {
  mkdir -p "$LLM_CONFIG_BASE"
  python3 - "$LLM_CONFIG_PATH" <<'PY'
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
payload = {
    "version": 1,
    "tasks": {
        "architect_history": {"tier": "strong"},
        "architect_feature": {"tier": "strong"},
        "architect_component_scoring": {"tier": "weak"},
        "architect_component_qa": {"tier": "strong"},
        "architect_folder_naming": {"tier": "weak"},
        "architect_topology_review": {"tier": "weak"},
        "architect_full_report_md": {"tier": "strong"},
        "architect_orchestrator": {"tier": "strong"},
        "architec_summary": {"tier": "strong"},
    },
}
config_path.write_text(
    yaml.safe_dump(payload, default_flow_style=False, allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)
PY
  chmod 600 "$LLM_CONFIG_PATH"
}

seed_global_json_config() {
  local name="$1"
  local src="$ROOT_DIR/config/$name"
  local dest="$STATE_DIR/$name"

  if [[ ! -f "$src" ]]; then
    echo "Missing default config template: $src" >&2
    exit 1
  fi

  mkdir -p "$STATE_DIR"
  if [[ -f "$dest" ]]; then
    return 0
  fi

  cp "$src" "$dest"
  chmod 644 "$dest"
}

validate_llm_config() {
  python3 - "$ROOT_DIR" <<'PY'
import sys

from architec.support.llm_preflight import preflight_backend_llm

root = sys.argv[1]
preflight_backend_llm(
    root,
    checks=[
        ("architect_history", "strong"),
        ("architect_component_scoring", "weak"),
    ],
)
PY
}

has_llmgateway() {
  python3 - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

sys.exit(0 if importlib.util.find_spec("llmgateway") else 1)
PY
}

install_llmgateway() {
  if has_llmgateway; then
    return 0
  fi
  if [[ -f "$LLMGATEWAY_LOCAL_PATH/pyproject.toml" ]]; then
    echo "Installing llmgateway from local checkout: $LLMGATEWAY_LOCAL_PATH"
    python3 -m pip install -e "$LLMGATEWAY_LOCAL_PATH"
    return 0
  fi
  echo "Installing llmgateway from GitHub: $LLMGATEWAY_GIT_URL"
  python3 -m pip install "$LLMGATEWAY_GIT_URL"
}

install_skill_tree() {
  local src_root="$1"
  local dest_root="$2"
  local label="$3"

  if [[ ! -d "$src_root" ]]; then
    return 0
  fi

  mkdir -p "$dest_root"
  local installed=0
  while IFS= read -r -d '' src_dir; do
    local name
    name="$(basename "$src_dir")"
    rm -rf "$dest_root/$name"
    cp -R "$src_dir" "$dest_root/$name"
    installed=$((installed + 1))
  done < <(find "$src_root" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)

  if [[ "$installed" -gt 0 ]]; then
    echo "Installed $installed $label skill(s) to $dest_root"
  fi
}

remove_deprecated_skills() {
  local dest_root="$1"
  shift

  mkdir -p "$dest_root"
  local removed=0
  local skill_name
  for skill_name in "$@"; do
    if [[ -d "$dest_root/$skill_name" ]]; then
      rm -rf "$dest_root/$skill_name"
      removed=$((removed + 1))
    fi
  done

  if [[ "$removed" -gt 0 ]]; then
    echo "Removed $removed deprecated skill(s) from $dest_root"
  fi
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage: ./install.sh

Installs architec from the current source checkout into the active Python
environment as an editable package.
Also installs the llmgateway dependency, preferring ../llmgateway when present.
Writes ~/.llmgateway/config.yaml for provider/API/concurrency settings and
LLMGateway strong/weak model settings, plus ~/.architec/config.yaml for
Architec task-tier routing.
Also installs bundled Codex skills into ~/.codex/skills and Claude skills into
~/.claude/skills:
  archi-full, archi-diff, archi-goal, archi-advice
The installer reuses existing llmgateway or Architec configs when available and
runs backend LLM preflight before finishing.
EOF
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "install.sh takes no arguments." >&2
  exit 1
fi

python3 -m pip install --upgrade pip
install_llmgateway
python3 -m pip install -e .

gateway_provider_type="${gateway_provider_type:-${architec_llm_provider_type:-glm}}"
gateway_api_style="${gateway_api_style:-${architec_llm_api_style:-openai_responses}}"
gateway_base_url="${gateway_base_url:-${architec_llm_main_url:-}}"
gateway_api_key="${gateway_api_key:-${architec_llm_main_api_key:-}}"
gateway_max_concurrent="${gateway_max_concurrent:-${architec_llm_max_concurrent:-12}}"
gateway_model_map_json="${gateway_model_map_json:-}"
gateway_retry_max="${gateway_retry_max:-3}"
gateway_timeout="${gateway_timeout:-90}"

architec_llm_strong_model="${architec_llm_strong_model:-gpt-5.4}"
architec_llm_weak_model="${architec_llm_weak_model:-gpt-5.4}"
architec_llm_strong_reasoning_effort="${architec_llm_strong_reasoning_effort:-high}"
architec_llm_weak_reasoning_effort="${architec_llm_weak_reasoning_effort:-low}"

load_existing_gateway_config
prompt_with_default gateway_provider_type "LLMGateway provider type [$gateway_provider_type]: " "$gateway_provider_type"
prompt_with_default gateway_api_style "LLMGateway API style [$gateway_api_style]: " "$gateway_api_style"
prompt_required gateway_base_url "LLMGateway base URL: "
prompt_required gateway_api_key "LLMGateway API key: " 1
prompt_with_default gateway_max_concurrent "LLMGateway max concurrent [$gateway_max_concurrent]: " "$gateway_max_concurrent"
prompt_with_default gateway_retry_max "LLMGateway retry max [$gateway_retry_max]: " "$gateway_retry_max"
prompt_with_default gateway_timeout "LLMGateway timeout [$gateway_timeout]: " "$gateway_timeout"

prompt_with_default architec_llm_strong_model "LLMGateway strong model [$architec_llm_strong_model]: " "$architec_llm_strong_model"
prompt_with_default architec_llm_weak_model "LLMGateway weak model [$architec_llm_weak_model]: " "$architec_llm_weak_model"
prompt_with_default architec_llm_strong_reasoning_effort "LLMGateway strong reasoning effort [$architec_llm_strong_reasoning_effort]: " "$architec_llm_strong_reasoning_effort"
prompt_with_default architec_llm_weak_reasoning_effort "LLMGateway weak reasoning effort [$architec_llm_weak_reasoning_effort]: " "$architec_llm_weak_reasoning_effort"

seed_global_json_config "rubric.json"
seed_global_json_config "scoring-policy.json"
write_gateway_config
write_architec_config
install_skill_tree "$ROOT_DIR/codex_skills" "$CODEX_SKILLS_BASE" "Codex"
install_skill_tree "$ROOT_DIR/claude_skills" "$CLAUDE_SKILLS_BASE" "Claude"
remove_deprecated_skills \
  "$CODEX_SKILLS_BASE" \
  "archi-analysis" \
  "archi-full-analysis" \
  "archi-diff-analysis" \
  "archi-goal-analysis" \
  "archi-architecture-advice" \
  "architect-g"
remove_deprecated_skills \
  "$CLAUDE_SKILLS_BASE" \
  "archi-analysis" \
  "archi-full-analysis" \
  "archi-diff-analysis" \
  "archi-goal-analysis" \
  "archi-architecture-advice" \
  "architect-g"
validate_llm_config

echo "Saved LLMGateway config to $LLMGATEWAY_CONFIG_PATH"
echo "Saved Architec LLM config to $LLM_CONFIG_PATH"
