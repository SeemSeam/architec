# Plan Diff Consistency V1

Date: 2026-05-14

## Context

`plan-review` can parse a Markdown plan into structured touchpoints and a fingerprint, while `code-review --diff` and `code-review --since <ref>` can inspect the actual changed files. Before this decision, those outputs were separate: a coding agent could drift away from a reviewed plan without `code-review` surfacing that mismatch.

The first implementation should connect the two artifacts without reintroducing goal-style planning behavior.

## Decision

Add a conservative plan/diff consistency v1:

- `code-review --diff` and `code-review --since <ref>` accept an optional `--plan-review <plan.json>` argument.
- The argument points to a saved `plan-review` JSON result, normally produced with `archi plan-review <plan.md> --out plan.json`.
- `code-review` reads the full plan-review JSON, not only the fingerprint.
- It compares `understood_plan.changes[].path` with `change_analysis.changed_files`.
- It emits `kind: "plan-diff-consistency"` concerns for:
  - changed files outside the saved plan touchpoints;
  - planned paths not present in the selected diff.
- It emits a `plan_diff_consistency` signal when planned paths are available.
- The scan is changed-file-scoped and only runs for diff/since review types.
- Top-level `archi --diff` also accepts `--plan-review` for parity with `archi code-review --diff`.

The output remains advisory-only. It reports mismatch observations and plan metadata as evidence; it does not decide that the implementation is wrong or that the plan is correct.

## Non-Goals

This does not:

- generate or rewrite plans;
- infer plan intent beyond `understood_plan.changes[].path`;
- run in full review;
- compare import edges, tests, coverage, churn, or runtime data;
- add fix-advice special handling for `plan-diff-consistency`;
- fail the review when the plan and diff diverge.

## Consequences

- Coding-agent changes can be compared with a previously reviewed plan without using the removed `--goal` workflow.
- The first signal is intentionally path-based. It can miss semantic drift inside an expected file and can flag intentional scope changes as observations.
- More detailed plan/diff checks, such as import-edge expectations or test/churn fusion, remain separate follow-up decisions.
