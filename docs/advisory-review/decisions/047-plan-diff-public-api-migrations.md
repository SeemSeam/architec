# Plan Diff Public API Migrations

Date: 2026-05-14

## Context

Decision 037 connected saved `plan-review` JSON to incremental code review using
planned path touchpoints. Decisions 040, 045, and 046 added structured import,
expected-test, and dependency-alternative expectations.

The remaining narrow plan/diff consistency gap is public API migration intent. A
plan may explicitly say that a public entry point, compatibility wrapper, or
consumer-facing migration file must be updated with the implementation. That is
useful context for incremental review, but it should stay an advisory
observation and should not infer migration obligations from prose.

## Decision

Add public API migration observations to `plan-diff-consistency` v1:

- `code-review --diff/--since --plan-review <plan.json>` can consume explicit
  structured public API migration entries from the saved `plan-review` JSON.
- V1 only treats structured public API migration entries as requirements.
  String or prose migration notes remain plan context and are not requirements.
- Public API migration entries may name one or more expected migration
  touchpoints such as public entry files, compatibility wrappers, docs, or
  consumer-facing migration notes.
- If an expected migration touchpoint is not present in selected changed files,
  emit an advisory `kind: "plan-diff-consistency"` observation such as
  `plan_diff_consistency.observation=planned_public_api_migration_not_observed`.
- The observation reports that a planned migration touchpoint was not observed
  in the selected diff/since range; it does not claim the API is broken or the
  implementation is incomplete.
- The signal metrics should expose public API migration input and missing counts
  separately from path, import, dependency-alternative, and expected-test counts.

V1 should stay explicit and conservative. A saved plan-review JSON may use object
entries such as:

```json
{
  "understood_plan": {
    "public_api_migrations": [
      {
        "path": "src/package/__init__.py",
        "note": "export the new public entry point"
      },
      {
        "path": "docs/migration.md"
      }
    ]
  }
}
```

Equivalent object fields may be accepted for compatibility, but free-form prose
such as `"update public API docs"` is not a migration requirement in v1.
Accepted path/glob keys are `path`, `api_path`, `public_api_path`, `glob`, and
`api_glob`. Optional `symbol`, `old_symbol`, `new_symbol`, `source`,
`source_glob`, and `from_path` fields are recorded as context facts, not used
for static API inference.

The behavior is incremental-only:

- full review does not run this check;
- since bad-ref degraded results return before loading plan-review JSON or
  running the scanner;
- selected-scope and concern ranking semantics remain unchanged.

## Non-Goals

This does not:

- infer public API migrations from arbitrary prose;
- inspect all exported symbols or public packages;
- decide whether a public API migration is behaviorally correct;
- create a new concern kind;
- run in full review;
- inspect unchanged files outside the selected diff/since range;
- add dedicated `fix-advice` behavior;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Plans can carry explicit public API migration intent into incremental review.
- Missing migration touchpoints are visible as advisory plan/diff consistency
  observations, not correctness claims.
- Prose migration notes remain safe context rather than accidental
  requirements.
- Existing path, import, dependency-alternative, and expected-test observations
  remain unchanged.
