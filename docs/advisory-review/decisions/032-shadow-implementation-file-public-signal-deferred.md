# Shadow Implementation File Public Signal Deferred

Date: 2026-05-13

## Context

Decision 031 added `shadow_implementation_file_dry_run(project_root, limit=20)` so module-level candidates could be sampled before becoming user-visible CodeReviewResult output.

The dry-run helper was run against the current repository root:

```bash
PYTHONPATH=src python3 - <<'PY'
import json
from pathlib import Path
from architec.code_review.shadow_implementation import shadow_implementation_file_dry_run
print(json.dumps(shadow_implementation_file_dry_run(Path("."), limit=20), indent=2, sort_keys=True))
PY
```

Root-scope sample result:

- `candidate_total`: 1395
- `pair_total`: 10139
- `reported_total`: 20
- `excluded_total`: 15133
- `by_exclusion`: `adapter_like=502`, `no_role=10203`, `parse_error=3`, `split_module_name=715`, `too_small=3710`

The top 20 reported candidates were all under `.ccb/agents/.../provider-state/...`, mostly duplicated skill/plugin scripts across agent workspaces or temporary plugin copies. Examples include repeated `plugin-creator/scripts/create_basic_plugin.py`, `atlassian-rovo/.../jql_builder.py`, `box_rest.py`, Hugging Face training scripts, and life-science plugin scripts.

An auxiliary source-only sample was also run against `src/architec` to understand project-source signal quality:

- `candidate_total`: 51
- `pair_total`: 0
- `reported_total`: 0
- `excluded_total`: 98
- `by_exclusion`: `adapter_like=5`, `no_role=28`, `split_module_name=31`, `too_small=34`

## Candidate Review

Manual review of the root-scope top 20:

- Repeated `create_basic_plugin.py` pairs: likely false positives for architec. They are duplicated generated/provider-state skill assets under `.ccb`, not maintained project source.
- Repeated `jql_builder.py`, `box_rest.py`, `cot-self-instruct.py`, `estimate_cost.py`, and `sparql_request.py` pairs: likely false positives for architec. They are external skill/plugin copies repeated across agent home directories.
- Life-science PheWAS script pairs with high API overlap: unclear as a general module-similarity signal, but still not suitable for architec CodeReviewResult because the files are `.ccb` provider-state assets rather than project source.

No top candidate was a clear true positive in `src/architec`.

## Decision

Do not promote file/module-level `shadow_implementation` to CodeReviewResult.

Keep the dry-run helper for calibration, but do not add:

- `signals[]` entries for module-level shadow implementation;
- `concerns[]` entries with `location.symbol_kind: "module"`;
- fix-advice behavior for module-level shadow implementation.

## Preconditions For Reconsideration

Revisit public signal exposure only after at least these are true:

- project-local generated and agent-state directories such as `.ccb` are excluded from module dry-run scanning, or callers can provide a source-root scope;
- real positive fixtures exist from maintained project source, not copied external plugin assets;
- role taxonomy distinguishes intentional provider/backend/plugin variants from shadow reimplementation;
- module public API extraction separates stable API surface from script utility functions;
- dry-run sampling across multiple repositories shows a low false-positive rate.

## Consequences

- Current public review output remains limited to function/class `shadow-implementation` concerns.
- The dry-run helper remains useful for offline calibration and detector research.
- The next useful implementation step is not CodeReviewResult integration; it is improving scan scoping and collecting real positive module-level examples.
