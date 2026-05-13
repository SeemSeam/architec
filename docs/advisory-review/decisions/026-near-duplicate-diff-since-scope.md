# Near Duplicate Diff Since Scope

Date: 2026-05-13

## Context

`near_duplicate` started as a full-review-only signal. It reports Python functions and methods with the same normalized AST fingerprint and intentionally avoids fuzzy similarity.

Diff and since reviews now support changed-file-scoped `shadow_implementation`, but exact near duplicates in changed files were still invisible in incremental review. This missed a high-precision case: newly changed code exactly duplicates an existing implementation.

## Decision

Enable `near_duplicate` in `code-review --diff` and `code-review --since <ref>` with changed-file scope.

The detector still:

- scans Python only;
- uses exact normalized AST fingerprint matching;
- reports function/method-level concerns only;
- keeps `kind: "duplication"` and `references[].role: "reference"`.

In incremental review:

- the detector may scan the whole repository to build the fingerprint index;
- a concern is emitted only when the primary `location.path` is in `change_analysis.changed_files`;
- `references[].path` may point to an unchanged existing implementation;
- a changed reference path alone is not enough to report historical duplicates;
- if `change_analysis.changed_files` is missing or empty, no near-duplicate signal is emitted;
- if a since range is degraded because the ref/range cannot be resolved, the detector is not run.

When the changed file sorts before the existing implementation, incremental review still makes the changed function the primary `location` and chooses a stable other function as `reference`.

## Non-Goals

This does not:

- add fuzzy similarity;
- add class, module, or file-level near-duplicate detection;
- change `shadow_implementation` behavior;
- change `fix-advice` behavior;
- treat changed `references[].path` as scope for historical issues;
- re-run git helpers from the detector layer.

## Consequences

- Incremental review can surface exact duplicated functions introduced or touched by the current change.
- Full review behavior remains compatible: the first sorted implementation in a fingerprint group is the reference, and later implementations become duplication concerns.
- Incremental concern ids may differ from full concern ids for the same fingerprint group when the changed-file scope forces a different primary duplicate/reference pair. This is intentional because the id describes the reported primary/reference fact pair, not a global fingerprint group.
- Signal metrics in scoped mode include `scoped_to_changed_files`, `changed_file_total`, and `candidate_total_before_scope`.
