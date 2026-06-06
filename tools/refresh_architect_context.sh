#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
ROOT="$(cd "$ROOT" && pwd)"

python3 "$ROOT/architec/tools/collect_repo_metrics.py" \
  --root "$ROOT" \
  --rubric "$ROOT/architec/config/rubric.json"

python3 "$ROOT/architec/tools/build_architect_prompt.py" \
  --root "$ROOT"

echo "Architect context refreshed:"
echo "- $ROOT/.hippos/architect-metrics.json"
echo "- $ROOT/.hippos/architect-prompt.md"
