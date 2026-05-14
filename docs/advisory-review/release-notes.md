# Advisory Review Migration Notes

Date: 2026-05-12
Updated: 2026-05-14

## Summary

`architec` is moving the public CLI toward advisory-only review commands. It reviews plans and code, but does not plan work for the user, act as a gate, or automatically repair code.

## Top-Level Routing

The top-level full and diff commands now route through the code-review layer:

```bash
archi .
archi --diff .
```

These remain supported aliases, but their underlying result is now a CodeReviewResult:

- `archi .` maps to `archi code-review --full .`.
- `archi --diff .` maps to `archi code-review --diff .`.
- `archi --diff --base <base> --head <head> .` maps to diff code review with that range.

The human stdout summary now highlights CodeReviewResult concern counts, top concerns, and signal summaries while keeping the JSON output shape unchanged.

## Output Shape Change

For top-level full and diff commands, `--out <path>` now writes CodeReviewResult JSON instead of the legacy analysis result shape.

The CodeReviewResult shape includes:

```json
{
  "mode": "code_review",
  "review_type": "full|diff|since",
  "scores": {},
  "summary": {},
  "findings": [],
  "signals": [],
  "evidence": [],
  "concerns": [],
  "artifacts": {}
}
```

Consumers that previously parsed legacy fields such as `meta`, `recommendations`, `cleanup`, `archive_candidates`, `change_analysis`, or `feature_analysis` from top-level `--out` should migrate to `concerns`, `signals`, `evidence`, and `artifacts`.

Generated code-review `concern_id` values now use fact-based deterministic ids such as `code-review:cleanup:<hash>` instead of presentation positions. Older saved review JSON remains valid input to `fix-advice`.

## Final Breaking Changes Checklist

- `--goal` has been removed from the top-level parser. Use `archi plan-review <plan.md>`.
- Legacy command parsers have been removed: `archi cleanup`, `archi autofix`, `archi baseline`, and `archi gate`.
- Legacy public APIs have been retired:
  - cleanup subpackage wrappers: `architec.cleanup.run_cleanup`, `architec.cleanup.run_autofix`;
  - root and subpackage wrappers: `architec.run_gate`, `architec.run_baseline`, `architec.gate.run_gate`, `architec.baseline.run_baseline`.
- Top-level `archi .` now returns code-review-shaped output.
- Top-level `archi --diff .` now returns diff CodeReviewResult output.
- Top-level `--out <path>` writes CodeReviewResult JSON for full and diff review aliases.

Migration targets remain advisory-only: `plan-review`, `code-review`, `fix-advice`, and `status`. They report observations and suggestions; they do not plan work, make merge decisions, or apply repairs.

## Goal Parser Removal

The public `--goal` entry point has been removed from the parser:

```bash
archi --goal "..." .
```

It is no longer accepted by the CLI. Use a plan Markdown file instead:

```bash
archi plan-review <plan.md>
```

## Legacy Parser Removal

Legacy maintenance command parsers have been removed after the soft-cut migration period:

`archi cleanup` is no longer a supported command parser. Use `archi code-review --full .` and read cleanup/archive signals from CodeReviewResult.

`archi autofix` is no longer a supported command parser, including dry-run and `--apply` forms. Use `archi fix-advice --review <review.json>`.

`archi gate` is no longer a supported command parser. Use advisory `archi code-review --diff .` output; it is not a merge decision.

`archi baseline` is no longer a supported command parser. Use `archi status --snapshot`.

## Legacy Public API Migration

The cleanup subpackage wrapper APIs have been retired:

- `architec.cleanup.run_cleanup`
- `architec.cleanup.run_autofix`

Use `archi code-review --full .` for cleanup/archive advisory signals and `archi fix-advice --review <review.json>` for repair guidance. Lower-level cleanup inventory, archive, semantic judge, autofix plan, and artifact helpers remain available for internal compatibility.

The root legacy public APIs have also been retired:

- `architec.run_gate`
- `architec.run_baseline`
- `architec.gate.run_gate`
- `architec.baseline.run_baseline`

Use advisory `archi code-review --diff . --out review.json` instead of gate wrappers, and `archi status --snapshot` instead of baseline wrappers.

## CI Migration

For CI jobs that previously used legacy gate output, write advisory diff review JSON instead:

```bash
# old
archi gate --out gate.json .

# new
archi code-review --diff --out review.json .
```

The new JSON is advisory review output for humans or agents. It should not be treated as a merge decision.

For jobs that previously used standalone cleanup output, write full advisory review JSON and read cleanup/archive signals from the review result:

```bash
# old
archi cleanup --out cleanup.json .

# new
archi code-review --full --out review.json .
```

For CI jobs that previously captured a legacy baseline artifact, write an advisory status snapshot instead:

```bash
# old
archi baseline --out baseline.json .

# new
archi status --snapshot --out status.json .
```

## New Public Entrypoints

Use these advisory commands directly when possible:

```bash
archi plan-review <plan.md>
archi code-review --full .
archi code-review --diff .
archi code-review --since <ref> .
archi fix-advice --review <review.json>
```

`plan-review` reads a Markdown plan and reports understood intent, changed areas, dependencies, concerns, suggested adjustments, and a plan fingerprint.

`code-review` reviews current code structure in full, diff, or since-ref mode. It is advisory-only and does not emit merge decisions.

Successful code-review runs append a compact ReviewEvent to `.architec/review-events.jsonl`. The event stream is local generated data by default and rotates at 10MB into month-named JSONL files.

`archi status --trend` and `archi status --snapshot` are advisory project-health modes. Existing `archi status` and `archi status --json` remain auth/session status commands.

`fix-advice` reads a saved review JSON and returns independent repair-direction suggestions for its concerns. It does not output executable changes and does not provide an apply mode. `--review <review.json>` is the canonical flag; `--for <review.json>` remains a compatibility alias.

## Status And Review Events

Successful code-review runs write local review events on a fail-open basis. If event writing hits an `OSError`, the review still returns and records `artifacts.review_event_error`.

`status --trend` reads the latest 100 review events. Its `scores` field comes from the most recent full code-review event; diff and since events still contribute to trend counts and weakening component observations. `fix-advice` does not write review events.

## Final Advisory Checks

Diff and since code-review now use the same lightweight base LLM preflight as full code-review; `architect_component_scoring` is no longer a required preflight task for advisory diff feedback.

`code-review --since <ref>` returns a structured CodeReviewResult degradation when the git ref or range cannot be resolved. It does not fall back to full review or unrelated working-tree diff.

`code-review --full` now includes a conservative Python `shadow_implementation` signal for function-level and class-level candidates. It reports `shadow-implementation` concerns only when static evidence shows cross-file similarity, shared role, compatible function signature or class API shape, AST similarity, and no direct reuse edge.

`code-review --diff` and `code-review --since <ref>` now run `shadow_implementation` in changed-file-scoped mode. They only report concerns whose primary `location.path` is in the changed files; `references[]` may point at unchanged existing implementations.

`shadow_implementation` now applies role-taxonomy precision filtering for clear renderer versus assembler/support/budget/context split roles. Function/class shadow remains role, AST, signature, API, name-overlap, and reuse-edge based; same-role candidates and parser-helper pairs remain eligible.

`fix-advice` now has a dedicated advisory branch for `shadow-implementation` concerns. It consumes `references[].role: "existing_implementation"` to compare the suspected shadow implementation with the existing function or class, while keeping the output non-executable and neutral about which implementation is correct.

`code-review --diff` and `code-review --since <ref>` now also run exact `near_duplicate` detection in changed-file-scoped mode. They report duplication only when the primary `location.path` is changed; `references[]` may point at unchanged existing code.

File/module-level `shadow_implementation` remains dry-run calibration only. The internal helper can summarize module candidate pairs for noise analysis, but `code-review` does not expose module-level shadow signals or concerns.

Current repository sampling kept that boundary: root-scope dry-run candidates were dominated by `.ccb` provider-state and plugin copies, while `src/architec` had no reported module pairs. Public module-level shadow concerns remain deferred.

AI signal scanners now exclude local agent state and generated-state directories by default, including `.ccb`, release-flow-test installs, caches, virtual environments, dependency copies, fixtures, generated assets, and tests. This reduces noise for public `near_duplicate` and function/class `shadow_implementation` output without changing detector thresholds.

Advisory empty and degraded states now use standardized neutral wording. Diff/since no-finding headlines say no new architecture concerns were identified in the selected range, status reports no recorded events or no full score source without implying project health, and fix-advice explains legal empty suggestions as no matching concerns for the selected filters.

Architecture contracts v1 now lets projects declare changed-file-scoped dependency restrictions in `.architecture-rules.toml`. `code-review --diff` and `code-review --since <ref>` emit `architecture-contract` concerns when a changed Python file imports a restricted module; projects without contract config emit no contract signal.

Plan/diff consistency v1 connects saved plan-review JSON to incremental code review. `code-review --diff --plan-review <plan.json>` and `code-review --since <ref> --plan-review <plan.json>` compare `understood_plan.changes[].path` with the selected changed files and emit `plan-diff-consistency` observations for unexpected changed areas or planned paths not touched by the diff.

`fix-advice` now has a dedicated `architecture-contract` branch. It consumes the matched rule/import evidence and optional rule guidance to suggest boundary-oriented options without deciding whether the contract or the changed import is correct.

Risk context fusion v1 lets `code-review` read optional external coverage/churn/test-map JSON through `--risk-context <risk.json>`. Matching file facts are appended to existing concerns and summarized in a `risk_context` signal; `architec` does not execute tests or generate those reports.

Risk context enrichment accepts additional optional external facts for `complexity_by_file`, `public_api_files`, and `historical_recurrence_by_file`. These facts attach only to existing concerns and update `risk_context` input and `by_factor` counts; they do not create a new health score, concern kind, concern id scheme, or fix-advice schema.

Plan/diff consistency now also reads structured dependency import expectations from saved plan-review JSON. If selected changed Python files do not show an expected import edge, `code-review` emits a neutral `planned_import_not_observed` observation.

Plan/diff consistency expected tests v1 accepts explicit structured expected-test entries from saved plan-review JSON in diff/since review. Missing expected test touchpoints in the selected changed files emit advisory `plan-diff-consistency` observations. Free-form prose test notes remain context, not requirements; full review and since bad-ref degraded results do not run the check.

Plan/diff consistency dependency alternatives v1 lets explicit structured dependency entries list acceptable import alternatives. The selected changed Python files satisfy the expectation when any listed module is imported; missing all alternatives emits an advisory `plan-diff-consistency` observation. Free-form prose dependency notes remain context, not requirements.

Plan/diff consistency public API migrations v1 accepts explicit structured public API migration entries from saved plan-review JSON. Missing selected-diff migration touchpoints emit advisory `plan-diff-consistency` observations. String or prose migration notes remain context, not requirements, and there is no dedicated fix-advice behavior.

A follow-up Hippocampus dogfood run after Decisions 041-047 confirmed that diff/since scope hygiene is working: unrelated global cleanup/hotspot/topology context remains in signals/artifacts but does not fill selected-diff top concerns. The same run identified the next Architec product refinements: grouping intentional near-duplicate variant families, splitting broad mapper roles in `shadow_implementation`, and improving `fix-advice` wording for legacy/compat duplication concerns.

Decision 048 records the planned `near_duplicate` variant-family grouping v1. Exact normalized AST fingerprinting remains the base signal, but same-file phase/cache/prompt-builder families should be grouped into one advisory observation or display-limited so they do not flood top concerns. Cross-file duplicates and substantive non-family duplicates remain reportable.

A python-dotenv dogfood run tested Architec against a small mature Python library. The run produced a high overall score and no duplicate/shadow implementation findings, which is the desired behavior. It also exposed full-review calibration work: active changelogs can be over-classified as stale docs, cleanup/archive can duplicate attention on the same path, and low-pressure topology findings should remain context when `needs_folder_management=false`.

A Hippocampus dogfood audit recorded the next product priority for incremental review: diff/since top concerns need scope hygiene. Changed-file-scoped observations should be visually and structurally separated from global cleanup, hotspot, and topology context so incremental review does not look dominated by unrelated project-wide debt.

The implemented scope-hygiene behavior keeps full review unchanged. For diff/since review, top-level displayed concerns prioritize selected changed-file observations, while global cleanup/hotspot/topology context remains available through labelled context, signals, or artifacts. Summary metrics distinguish selected-scope counts from global-context counts via `scoped_concern_total`, `global_context_concern_total`, `displayed_scoped_concern_total`, and `displayed_global_context_concern_total`.

`near_duplicate` now suppresses exact duplicate pairs when both functions are thin wrapper/facade boilerplate and their delegated call targets differ. This keeps public API wrapper shapes such as `build_tree` / `extract_signatures` from occupying top concern slots while preserving substantive repeated logic and same-target wrapper duplicates.

`CodeReviewResult.concerns[]` now uses portfolio ranking for the displayed top concerns. Severity level remains the first ordering boundary, and same-level results prefer a mix of concern kinds before filling remaining slots with the same kind. `summary.concern_total` remains the pre-display total.

CodeReviewResult now records `summary.payload_bytes` as a compact main-payload estimate and applies a conservative display guard to oversized concern evidence, references, blast radius, and one-level signal metric maps. Truncation metadata is recorded in `artifacts.payload_truncation`.

Successful code-review runs now write `.architec/code-review-concerns.json` and expose it as `artifacts.code_review_concerns_json`. This artifact contains the complete generated concerns before top-level display truncation. Write failures are fail-open for `OSError` and are recorded as `artifacts.code_review_concerns_error`.

## Advisory-Only Boundary

The new review surface follows these boundaries:

- No planning: provide a plan to `plan-review`; `architec` reviews it.
- No gate: code review reports concerns and evidence, not merge decisions.
- No automatic repair: repair direction belongs in advisory output, not automatic patches.
