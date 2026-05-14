# Plan Diff Import Edge Expectations

Date: 2026-05-14

## Context

Decision 037 connected saved `plan-review` JSON to incremental `code-review` using
path touchpoints. That catches scope drift, but it cannot tell whether a planned
dependency edge was actually reflected in the selected diff.

For architecture stability, this is a useful next step: a plan may say that an
API change should route through a service facade, while the implementation either
does not add that import or uses a different boundary.

## Decision

Extend `plan-diff-consistency` with conservative import-edge expectations:

- `code-review --diff/--since --plan-review <plan.json>` continues to read the
  full saved `plan-review` JSON.
- In addition to `understood_plan.changes[].path`, it reads
  `understood_plan.dependencies[]` entries.
- Structured dependency entries may specify a source scope with `source`,
  `source_glob`, `path`, or `from_path`, and one or more expected import modules
  with `imports`, `modules`, `module`, `import`, `target`, or `dependency`.
- String dependency entries remain plan context and are not treated as import
  expectations in v1. This avoids treating old path-style dependency notes as
  missing imports.
- The scanner reads imports only from selected changed Python files.
- If no selected changed file in the dependency scope imports the expected
  module, it emits a `kind: "plan-diff-consistency"` concern with
  `plan_diff_consistency.observation=planned_import_not_observed`.
- The existing path-level observations remain unchanged.
- The signal metrics add `planned_import_total`.

The output remains advisory-only. It does not decide that the plan is correct or
that the implementation is wrong; it only records that a planned dependency edge
was not observed in the selected changed files.

## Non-Goals

This does not:

- infer dependency expectations from free-form prose;
- compare all imports against a complete allow-list;
- report unexpected imports that are not mentioned in the plan;
- run in full review;
- inspect unchanged files outside the selected diff/since range;
- change architecture contract rules or risk context fusion.

## Consequences

- Plan/diff consistency can now catch a second class of drift: expected boundary
  usage missing from the implementation.
- The behavior stays changed-file-scoped and deterministic.
- Plans that do not use structured dependency entries continue to get only the
  path-level v1 checks.
- More semantic checks, such as expected test coverage or public API migration
  notes, remain separate future decisions.
