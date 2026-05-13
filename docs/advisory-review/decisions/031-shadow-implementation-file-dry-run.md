# Shadow Implementation File Dry-Run

Date: 2026-05-13

## Context

Function-level and class-level `shadow_implementation` detection now produce advisory concerns in full, diff, and since review with changed-file scoping. File/module-level shadow implementation remains higher risk: modules can intentionally share roles because they are split by backend, provider, report view, adapter, or compatibility boundary.

The current plan needs data about candidate noise before promoting module-level findings into CodeReviewResult.

## Decision

Add an internal dry-run scan helper for file/module-level shadow implementation candidates.

The helper scans Python modules and returns calibration metrics only:

- `mode: "dry_run"`;
- candidate and pair totals;
- top candidate summaries with left/right paths, role, similarity metrics, and skip facts;
- exclusion counts for small, adapter-like, split-module, no-role, and parse-error cases.

The helper is not called by `code-review`, does not add `signals[]`, and does not add `concerns[]`.

## Scope

The dry-run collector is Python-only and compares modules using conservative static facts:

- top-level public function/class API tokens;
- public symbol shape;
- module AST feature cosine;
- import token similarity;
- shared role tokens;
- absence of direct module import/reuse edges.

It excludes likely adapters, wrappers, facades, compatibility shims, generated/vendor/test/build paths, and common intentional split-module names such as helpers, support, views, sections, runtime, payload, and registry.

## Non-Goals

This does not:

- add `location.symbol_kind: "module"` shadow concerns;
- change the public ReviewConcern schema;
- change function-level or class-level detector thresholds;
- change diff/since behavior;
- add fix-advice behavior;
- use an LLM or external dependency.

## Consequences

- Future work can sample module-level candidates without changing user-facing CLI output.
- `code-review` output stays limited to function/class `shadow-implementation` concerns.
- Whether file-level shadow implementation should become a public signal remains a deferred product decision.
