# Code Review Output Contract

Date: 2026-05-12

## Context

`code-review` now produces an advisory-only CodeReviewResult for full, diff, and since modes. Early implementation exposed three ambiguous fields:

- `concerns[].evidence` and top-level `evidence[]` could duplicate each other.
- `signals[]` had per-kind ad hoc fields.
- `summary.concern_total` counted only the displayed top concerns, not all generated concerns.

These ambiguities make downstream agent consumption and future `fix-advice` integration harder.

## Decision

Use the following contract:

- `concerns[]` is the canonical actionable list shown in the main result. It is capped to the top-N concerns by default.
- `concerns[].evidence` is the canonical per-concern fact list. It should contain facts only, not repair actions.
- Top-level `evidence[]` is a lightweight evidence index derived from the displayed concerns. Each item should include `evidence_id`, `concern_id`, `kind`, `location`, `confidence`, and `facts`. It intentionally duplicates a compact view for agent scanning; it is not the complete evidence store.
- `signals[]` uses one schema across signal kinds: `kind`, `summary`, and `metrics`.
- `summary.concern_total` means the number of generated concerns before top-N truncation.
- `summary.top_concern_total` means the number of concerns included in the main `concerns[]` list.
- `summary.concern_limit` records the active top-N cap.

## Consequences

- Consumers can distinguish "how many issues exist" from "how many are shown".
- `signals[]` can grow without inventing new top-level fields for each kind.
- `fix-advice` can reference `concern_id` and use `concerns[].evidence` as the detailed source of truth.
- Top-level `evidence[]` remains useful for quick scan and agent retrieval without becoming a second source of truth.
