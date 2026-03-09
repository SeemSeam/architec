#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_CONFIG_BASE="${ARCHITEC_USER_CONFIG_DIR:-$HOME/.architec}"
STATE_DIR="$USER_CONFIG_BASE"
LLM_CONFIG_PATH="$STATE_DIR/architec-llm.yaml"

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

write_project_llm_config() {
  local base_url="$1"
  local api_key="$2"

  mkdir -p "$STATE_DIR"

  python3 - "$LLM_CONFIG_PATH" "$base_url" "$api_key" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
base_url = sys.argv[2]
api_key = sys.argv[3]

payload = {
    "version": 1,
    "common_system_prompt": "",
    "task_prompt_prefixes": {},
    "failover": {
        "transport_failures_before_switch": 2,
        "parse_failures_before_switch": 1,
        "cooldown_sec": 180,
    },
    "providers": {
        "main": {
            "provider_type": "glm",
            "api_style": "openai_responses",
            "base_url": base_url,
            "api_key": api_key,
            "headers": {
                "anthropic-version": "2023-06-01",
            },
            "model_map": {
                "gpt-5.3-codex high": "gpt-5.3-codex",
                "gpt-5.3-codex-medium": "gpt-5.3-codex",
                "claude-sonnet-4-5-20250929": "gpt-5.3-codex",
                "claude-sonnet-4-20250514": "gpt-5.3-codex",
            },
        }
    },
    "tiers": {
        "strong": {
            "candidates": [
                {
                    "provider": "main",
                    "model": "gpt-5.3-codex high",
                }
            ]
        },
        "small": {
            "candidates": [
                {
                    "provider": "main",
                    "model": "gpt-5.3-codex-medium",
                }
            ]
        },
    },
    "tasks": {
        "architect_history": {"tier": "strong"},
        "architect_feature": {"tier": "strong"},
        "architect_component_scoring": {"tier": "small"},
        "architec_summary": {"tier": "strong"},
    },
}

config_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
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

from architec.llm_preflight import preflight_backend_llm

root = sys.argv[1]
checks = [
    ("architect_history", "strong"),
    ("architec_summary", "strong"),
    ("architect_component_scoring", "small"),
    ("architect_feature", "strong"),
]
preflight_backend_llm(root, checks=checks)
PY
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found on PATH." >&2
  exit 1
fi

cd "$ROOT_DIR"
python3 -m pip install -e .

architec_llm_main_url="${architec_llm_main_url:-}"
architec_llm_main_api_key="${architec_llm_main_api_key:-}"

prompt_required architec_llm_main_url "Architec backend URL: "
prompt_required architec_llm_main_api_key "Architec API key: " 1

seed_global_json_config "rubric.json"
seed_global_json_config "scoring-policy.json"
write_project_llm_config "$architec_llm_main_url" "$architec_llm_main_api_key"
validate_llm_config

echo "Saved global Architec LLM config to $LLM_CONFIG_PATH"
echo "Architec install and LLM preflight completed."
