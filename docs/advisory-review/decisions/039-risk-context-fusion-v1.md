# Risk Context Fusion V1

Date: 2026-05-14

## Context

Architecture concerns matter more when they appear in high-churn, under-tested, or low-coverage code. `architec` should use that context when users already have it, but it should not become a test runner, coverage collector, or churn mining tool.

## Decision

Add an optional external risk context input for code review:

- `archi code-review --full|--diff|--since ... --risk-context <risk.json>`;
- top-level `archi .` and `archi --diff .` also accept `--risk-context <risk.json>`;
- `--check` rejects `--risk-context`;
- Python APIs accept `risk_context_path`;
- no risk context input means no risk context signal and no risk context evidence.

The risk JSON v1 shape is intentionally small:

```json
{
  "coverage_by_file": {
    "src/service.py": {"line_rate": 0.42}
  },
  "churn_by_file": {
    "src/service.py": {"changes": 13}
  },
  "test_files_by_source": {
    "src/service.py": ["tests/test_service.py"]
  },
  "changed_tests": ["tests/test_service.py"]
}
```

Supported coverage values may be `0..1` ratios or `0..100` percentages. Churn values may be integers or objects with `changes`, `commit_count`, `count`, or `churn`.

When a concern location path matches risk context, code-review appends companion evidence facts such as:

- `risk_context.coverage=0.42`;
- `risk_context.coverage_level=low`;
- `risk_context.churn=13`;
- `risk_context.churn_level=high`;
- `risk_context.related_test_total=0`.

It also emits a `risk_context` signal with input and enrichment counts.

## Non-Goals

This does not:

- execute tests;
- generate coverage or churn reports;
- infer test ownership without an input report;
- change concern id generation;
- change detector thresholds, ranking, or confidence;
- create a separate health score;
- make any concern block review or CI.

## Consequences

- Existing structural concerns gain useful companion facts when teams provide coverage/churn/test mapping data.
- The feature is opt-in and silent by default, avoiding false precision for projects without external reports.
- Since bad-ref degraded results still return before reading risk context, preserving the existing range-error behavior.
