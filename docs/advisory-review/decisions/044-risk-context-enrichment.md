# Risk Context Enrichment

Date: 2026-05-14

## Context

Decision 039 added optional external risk context for coverage, churn, source to
test mapping, and changed test files. That keeps `architec` advisory-only: it
reads facts users already have and attaches them to existing review concerns.

The next useful enrichment is to accept more external risk facts for complexity,
public API exposure, and historical recurrence. These facts make existing
concerns easier to prioritize, but they should not create a separate scoring
system or cause `code-review` to execute project tooling.

## Decision

Extend optional `--risk-context <risk.json>` with these accepted fields:

```json
{
  "complexity_by_file": {
    "src/service.py": {"score": 18}
  },
  "public_api_files": ["src/service.py"],
  "historical_recurrence_by_file": {
    "src/service.py": {"count": 3}
  }
}
```

These fields are optional and additive to the Decision 039 fields
`coverage_by_file`, `churn_by_file`, `test_files_by_source`, and
`changed_tests`.

Risk context enrichment follows the same rule as v1:

- facts attach only to existing concerns whose primary `location.path` matches
  the external report;
- no risk context input means no `risk_context` signal and no risk-context
  evidence;
- unmatched external file facts are counted as inputs but do not create
  concerns;
- `risk_context` signal metrics include input counts and `by_factor` enrichment
  counts so readers can see which fact classes affected existing concerns.

Expected evidence facts include, when supplied and matched:

- `risk_context.complexity=<value>`;
- `risk_context.complexity_level=high`;
- `risk_context.public_api=true`;
- `risk_context.recurrence=<value>`;
- `risk_context.recurrence_level=recurring`.

Expected input count metrics include `complexity_file_total`,
`public_api_file_total`, and `recurrence_file_total`. Expected `by_factor` keys
include `high_complexity`, `public_api`, and `recurring_history` when those facts
enrich existing concerns.

## Non-Goals

This does not:

- create a new health score;
- execute tests;
- generate coverage reports;
- compute complexity internally;
- mine git history or status events internally for recurrence;
- create a new concern kind;
- create concerns from risk context alone;
- change concern id generation;
- change detector thresholds, ranking, or confidence;
- change `fix-advice` schema or output contract.

## Consequences

- Teams can pass richer external risk facts without changing the code-review
  concern schema.
- High-churn, high-complexity, public API, repeated concerns become easier to
  triage because the facts live beside the existing concern evidence.
- `risk_context` remains opt-in and silent by default.
- Implementation should keep parsing conservative: unsupported shapes are
  ignored rather than treated as generated facts.
