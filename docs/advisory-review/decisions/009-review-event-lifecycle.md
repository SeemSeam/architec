# Review Event Lifecycle

Date: 2026-05-12

## Context

`status --trend` and future continuity hints need a durable review history. The plan already names `.architec/review-events.jsonl`, but the lifecycle was unresolved: how large the file can grow, whether it should be versioned, and how status should read older events.

The repository already treats `.architec/` as generated local data through `.gitignore`.

## Decision

Review events are local generated artifacts by default:

- Append review summaries to `.architec/review-events.jsonl`.
- Do not require committing review events to version control.
- Rely on the existing `.architec/` ignore rule for the default local workflow.
- Rotate the active event file when it reaches 10 MB.
- Use month-based rotated names, for example `.architec/review-events-202605.jsonl`.
- `status --trend` should read the active event file plus recent rotated files in its configured window.
- Long-term archived event files are optional inputs for offline trend analysis, not part of the normal command path.

## Consequences

- Event history starts useful immediately without adding database or service dependencies.
- Teams can opt into sharing events by changing their own ignore rules, but architec does not treat shared events as required project facts.
- Rotation keeps local files bounded while preserving enough recent data for trend views.
- Future status implementation can stay simple: JSONL append, size check, and bounded read window.
