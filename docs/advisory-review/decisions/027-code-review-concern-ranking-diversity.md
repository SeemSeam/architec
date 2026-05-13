# Code Review Concern Ranking Diversity

Date: 2026-05-13

## Context

`code-review` now emits several high-confidence concern kinds, including cleanup, boundary, hotspot, duplication, and shadow implementation. The previous top-N ranking sorted only by level, confidence, path presence, and path. That could let one abundant kind fill the default `concerns[]` display and hide other risk dimensions.

`concern_total` already records the full generated count before top-N display, so `concerns[]` is a display portfolio rather than the only review truth.

## Decision

Use portfolio ranking for `CodeReviewResult.concerns[]`.

The ranking still prioritizes severity level first. A lower-level concern must not move ahead of a higher-level concern only for diversity.

Within the same level:

- concerns are base-sorted by confidence, path presence, and path for deterministic output;
- each `kind` has a soft display cap of 2 in the first portfolio round;
- if other kinds are unavailable, remaining slots are filled by the same kind using the same base sort;
- the default top-N limit remains 5.

`summary.concern_total` continues to mean the generated concern count before top-N display. `summary.top_concern_total` remains the number displayed in `concerns[]`, and `summary.concern_limit` remains the configured display limit.

## Non-Goals

This does not:

- change detector confidence scores;
- change `concern_id`;
- change `concern_total` semantics;
- add gate, merge, or release decision semantics;
- make `concerns[]` the only source of review truth;
- change `fix-advice`, `status`, or review event semantics.

## Consequences

- Default output better represents different risk dimensions when multiple concern kinds are present.
- A single severe concern kind can still fill the display when no same-level alternatives exist, or when higher severity consumes the limit.
- Consumers that need the full set should use `summary.concern_total` and artifacts/expanded output rather than treating the displayed top-N as exhaustive.
