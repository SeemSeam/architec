# Code Review Full Concerns Artifact

Date: 2026-05-13

## Context

CodeReviewResult now guards the top-level JSON payload by showing a small portfolio of top concerns and truncating oversized displayed fields. That keeps the main payload readable, but it also means the top-level `concerns[]` cannot be treated as the complete review detail.

The review needs an out-of-band place for the complete generated concerns before display truncation.

## Decision

Write a complete generated concerns artifact for successful code-review runs.

The artifact path is:

```text
.architec/code-review-concerns.json
```

The top-level result records the path as `artifacts.code_review_concerns_json`.

The artifact contains:

- `mode`
- `review_type`
- `concern_total`
- `concern_limit`
- `top_concern_total`
- lightweight `scores`
- lightweight `summary`
- `concerns` with the complete generated concern list

The artifact concern list is the generated concern list before top-level payload guard truncation. It is not limited to the displayed top 5 and does not truncate per-concern `evidence`, `references`, or `blast_radius`.

The artifact is local generated data under `.architec/`; it is not intended to be committed by default.

Artifact writing is fail-open for `OSError`. If writing fails, code-review still returns and records `artifacts.code_review_concerns_error`. Non-`OSError` implementation bugs are not swallowed.

## Non-Goals

This does not:

- change detector behavior or thresholds;
- change top concerns ranking;
- change `concern_id`;
- change review event or status semantics;
- change payload guard limits;
- put artifact file contents into the top-level JSON;
- write artifacts for degraded since-range results that do not run review analysis.

## Consequences

- The top-level `concerns[]` remains a display portfolio.
- Consumers that need full concern details can read `artifacts.code_review_concerns_json`.
- Payload guard can stay conservative without losing generated review detail.
- The latest run overwrites the same concerns artifact path, matching current local generated-data behavior.
