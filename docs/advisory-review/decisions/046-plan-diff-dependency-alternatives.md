# Plan Diff Dependency Alternatives

Date: 2026-05-14

## Context

Decision 040 added structured dependency import expectations for
`plan-diff-consistency`. That v1 treats each expected import as a separate
planned edge. Some plans intentionally allow one of several acceptable
boundaries, such as importing either a service facade or a compatibility facade.

The next narrow step is to let a structured dependency expectation express
acceptable alternatives without turning the plan into a complete import
allow-list.

## Decision

Extend structured dependency import expectations with dependency alternatives:

- `code-review --diff/--since --plan-review <plan.json>` can consume explicit
  structured dependency entries that include alternative acceptable modules.
- A dependency alternative group is satisfied when selected changed Python files
  matching the dependency source scope import any one listed module.
- If none of the listed modules is observed in the selected changed Python files
  for that source scope, emit an advisory `kind: "plan-diff-consistency"`
  observation such as
  `plan_diff_consistency.observation=planned_dependency_alternative_not_observed`.
- String or prose dependency entries remain plan context and are not treated as
  requirements.
- Existing single-module structured import expectations remain valid.
- The signal metrics should expose an alternative-group input count, separate
  from single import expectations.

V1 should stay explicit and conservative. A saved plan-review JSON may use object
entries such as:

```json
{
  "understood_plan": {
    "dependencies": [
      {
        "source": "src/api/**",
        "alternatives": [
          "app.service.facade",
          "app.compat.service_facade"
        ]
      }
    ]
  }
}
```

Equivalent object fields may be accepted for compatibility, but free-form prose
such as `"use the service layer"` is not a dependency alternative requirement.

The behavior is incremental-only:

- full review does not run this check;
- since bad-ref degraded results return before loading plan-review JSON or
  running the scanner;
- selected-scope and concern ranking semantics remain unchanged.

## Non-Goals

This does not:

- infer dependency alternatives from arbitrary prose;
- compare every import against an allow-list;
- report unexpected imports that are not mentioned in the plan;
- run in full review;
- inspect unchanged files outside the selected diff/since range;
- change architecture contract rules;
- add dedicated `fix-advice` behavior unless a separate implementation decision
  adds it;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Plans can express flexible boundary intent without forcing one exact module.
- `plan-diff-consistency` can distinguish missing all acceptable alternatives
  from choosing a different acceptable facade.
- Prose dependency notes remain safe context rather than accidental
  requirements.
- Existing path, single import, and expected-test observations remain unchanged.
