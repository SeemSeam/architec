# Code Review JSON Payload Budget

Date: 2026-05-13

## Context

The roadmap set a target that the main JSON output, excluding external artifact file contents, should stay under roughly 20KB for normal review output. As code-review gained more signals and richer concern evidence, that target needed an implementation guard instead of remaining only a documentation goal.

The main risk is unbounded growth in displayed `concerns[]`, `evidence[]`, and `signals[].metrics`. Artifact files can remain larger because they are explicitly out-of-band.

## Decision

Add a conservative payload guard to CodeReviewResult construction.

The 20KB target is advisory, not a gate. `code-review` still returns a result when the estimate is above target, and no merge or release decision is implied.

The guard:

- keeps the top-level CodeReviewResult schema compatible;
- preserves the existing top concern limit of 5;
- preserves `concern_id` values because ids are generated from original facts before display truncation;
- limits displayed per-concern `evidence` to 8 entries;
- limits displayed per-concern `blast_radius` to 8 entries;
- limits displayed per-concern `references` to 3 entries;
- limits oversized one-level `signals[].metrics` dictionaries to 12 entries;
- records truncation metadata in `artifacts.payload_truncation`;
- records a compact main-payload estimate in `summary.payload_bytes`.

The payload estimate is based on deterministic compact JSON encoding of the result without `artifacts`. It is meant to make growth observable and testable; it is not an exact transport-size promise.

## Non-Goals

This does not:

- change full, diff, or since review semantics;
- change detector behavior or thresholds;
- change ranking behavior;
- change `concern_total` semantics;
- change `concern_id`;
- introduce external JSON schema dependencies;
- move artifact file contents into the main JSON;
- enforce the 20KB target as a hard error.

## Consequences

- Large synthetic review payloads have a bounded display shape for concern facts and common signal metric maps.
- Consumers can detect display truncation through `artifacts.payload_truncation`.
- Consumers that need complete details should use artifact paths or future expanded-output modes rather than relying on the top-level JSON payload.
