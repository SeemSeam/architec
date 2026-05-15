# Risk Context External Report Formats

Date: 2026-05-14

## Context

Decisions 039 and 044 made `--risk-context <risk.json>` useful when callers
provide first-class Architec-shaped fields such as `coverage_by_file`,
`churn_by_file`, `test_files_by_source`, `complexity_by_file`,
`public_api_files`, and `historical_recurrence_by_file`.

That shape is stable, but it requires callers to pre-normalize common tool
outputs. Teams often already have coverage.py JSON, radon-like complexity
reports, or simple churn summaries. Risk context should be able to read a
small set of common JSON shapes without becoming a coverage runner, complexity
collector, or history miner.

## Decision

Keep `--risk-context` as a single JSON input.

Within that JSON, accept first-class Architec fields and a conservative set of
derived report shapes. Supported derived shapes may include:

- coverage.py-style `files` maps where each file has
  `summary.percent_covered`;
- radon-like complexity maps or lists that can be normalized to a file-level
  numeric complexity value;
- simple churn aliases that can be normalized to `churn_by_file`, such as
  `changes`, `commit_count`, `count`, or `churn`.

Normalize supported derived report values into the existing `risk_context`
facts used by Decisions 039 and 044:

- `risk_context.coverage=<ratio>`;
- `risk_context.churn=<count>`;
- `risk_context.complexity=<value>`;
- existing companion level facts such as low coverage, high churn, or high
  complexity when thresholds apply.

When both a first-class field and a derived report shape provide a value for
the same file and factor, the first-class field wins. For example,
`coverage_by_file["src/a.py"]` overrides a coverage.py-derived
`files["src/a.py"].summary.percent_covered`, and `complexity_by_file` overrides
radon-like derived complexity for the same path.

Unsupported report shapes are ignored conservatively. They should not create
synthetic files, guesses, warnings, or concerns.

## Non-Goals

This does not:

- execute tests;
- generate coverage reports;
- run radon or any complexity tool;
- mine git history or generate churn reports;
- add a new concern kind;
- add a new health score;
- change concern ranking;
- change `concern_id` generation;
- change the `ReviewConcern` or `FixAdviceResult` schema;
- add fix-advice behavior.

## Consequences

- Users can pass more common tool JSON through the existing `--risk-context`
  input without an extra conversion step.
- Explicit Architec-shaped fields remain the most stable integration contract.
- Risk context continues to attach facts only to existing concerns and to
  summarize enrichment through the existing `risk_context` signal.
- Unknown or unsupported report shapes fail closed by omission instead of
  producing speculative risk evidence.
