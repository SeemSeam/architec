---
name: architect-g
description: Inject .hippocampus/architect-prompt.md as architecture-focused context. Use when user asks for architecture analysis, module boundary design, complexity reduction, or refactor planning.
---

# architect-g

Load the generated architect context artifact and inject it into conversation.

## Preconditions

The file `.hippocampus/architect-prompt.md` should exist.
If missing, generate with:

```bash
python3 architec/tools/collect_repo_metrics.py --root . --rubric architec/config/rubric.json
python3 architec/tools/build_architect_prompt.py --root .
```

## Execution

```bash
target="$PWD/.hippocampus/architect-prompt.md"
if [ ! -f "$target" ]; then
  echo "ERROR: $target not found. Run architec refresh first."
  exit 1
fi
echo "@$target"
```

## Output Rule

Only output the absolute file reference line (`@...`) so the host can inject content directly.
