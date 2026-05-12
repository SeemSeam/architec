# Top-level Code Review Routing

Date: 2026-05-12

## Context

`code-review --full`, `--diff`, and `--since` now have advisory-only JSON result shapes. The legacy top-level commands `archi .` and `archi --diff .` still route through the older analysis result, which keeps planning-era fields such as recommendations and legacy cleanup/archive summaries.

To make advisory-only positioning visible in normal use, the top-level full and diff aliases need to route through the new code-review layer. This affects stdout summary richness and `--out` JSON shape.

## Decision

Top-level `archi .` and `archi --diff .` should internally route to `run_code_review_full` and `run_code_review_diff` when no goal is provided.

This transition accepts three constraints:

- The top-level human summary may become shorter because CodeReviewResult intentionally omits planning-era recommendations and legacy cleanup/archive top-level fields.
- `--out` should write the CodeReviewResult shape rather than the legacy analysis result shape.
- `archi --goal ...` temporarily remains on the legacy analysis path until a dedicated goal-retirement step removes or redirects it.

This routing step should not introduce `_emit_json` for the top-level alias. It should continue using the existing top-level emit path while the underlying result changes.

## Consequences

- This is a breaking output-shape change for users parsing top-level `--out`.
- Human stdout becomes more advisory-only and less planning-oriented, but may lose some legacy detail until the new summary layer is improved.
- Goal retirement remains an explicit follow-up, not an accidental side effect of routing.
- Existing subcommands such as cleanup, autofix, baseline, gate, and plan-review are not part of this routing step.
