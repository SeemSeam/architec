# Advisory Empty State Wording

Date: 2026-05-14

## Context

Advisory commands return several legitimate empty or degraded states:

- diff/since code review can identify no new concerns in the selected change range;
- since code review can be unable to analyze an unresolved ref/range;
- status can have no review events or no full code-review event for scores;
- fix-advice can receive a valid review with no matching concerns.

These states should be understandable without implying a gate result.

## Decision

Use neutral empty-state wording:

- empty observations use "No ... were identified/recorded/generated";
- degraded inputs use "Unable to analyze/read ..." and include a `reason` where the schema already allows it;
- legal empty fix-advice output explains that the review has no matching concerns for the selected filters.

Do not describe empty states as pass, clean, safe, or any other verdict.

## Non-Goals

This does not:

- change JSON field names or top-level schemas;
- change CLI exit codes;
- change detector, ranking, payload guard, artifact, event, or fix-advice logic;
- introduce gate semantics.

## Consequences

- Users can distinguish neutral no-finding states from degraded input states.
- Empty advisory output remains machine-readable through existing result structures.
- Tests cover the public empty/degraded strings against verdict-like wording.
