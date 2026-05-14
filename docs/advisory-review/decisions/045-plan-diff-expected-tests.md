# Plan Diff Expected Tests

Date: 2026-05-14

## Context

Decision 037 connected saved `plan-review` JSON to incremental code review using
planned path touchpoints. Decision 040 added structured import-edge
expectations. The next narrow plan/diff consistency step is explicit expected
test coverage from the saved plan.

The goal is to make reviewed plans more useful during agent implementation
without turning `architec` into a test runner or a merge gate.

## Decision

Add expected-test observations to `plan-diff-consistency` v1:

- `code-review --diff/--since --plan-review <plan.json>` can consume explicit
  structured expected-test entries from the saved `plan-review` JSON.
- V1 only treats structured expected-test entries as requirements. Arbitrary
  string or prose test/dependency entries remain plan context and are not
  requirements.
- Expected-test entries may name planned source or change scope and one or more
  expected test files.
- The scanner compares those expected test files with the selected changed
  files in the diff/since range.
- If a planned expected test is not present in selected changed files, emit an
  advisory `kind: "plan-diff-consistency"` observation such as
  `plan_diff_consistency.observation=planned_test_not_observed`.
- The observation reports missing expected test coverage for the selected
  implementation range; it does not claim the code is incorrect or untested.
- The signal metrics should expose an expected-test input count, separate from
  path and import expectation counts.

The behavior is incremental-only:

- full review does not run this check;
- since bad-ref degraded results return before loading plan-review JSON or
  running the scanner;
- selected-scope and concern ranking semantics remain unchanged.

## Structured Entry Shape

V1 accepts only explicit structured entries. The exact parser can stay
conservative, but the saved plan-review JSON should provide object entries such
as:

```json
{
  "understood_plan": {
    "tests": [
      {
        "source": "src/api/service.py",
        "test_path": "tests/test_service.py"
      }
    ]
  }
}
```

Equivalent object fields may be accepted for compatibility, but free-form
strings such as `"add tests"` or prose dependency notes are not treated as
expected-test requirements in v1.

## Non-Goals

This does not:

- infer test requirements from arbitrary prose;
- run tests;
- generate coverage;
- inspect unchanged test files outside the selected diff/since range;
- run in full review;
- load plan-review JSON for since bad-ref degraded results;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics;
- add dedicated `fix-advice` behavior unless a separate implementation decision
  adds it.

## Consequences

- Plans can carry explicit expected-test intent into incremental code review.
- Missing expected tests are visible as advisory plan/diff consistency
  observations, not correctness claims.
- Existing path and import-edge checks remain unchanged.
- Projects that only provide prose test notes continue to get context but no
  expected-test observations.
