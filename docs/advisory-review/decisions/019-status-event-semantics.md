# Status Event Semantics

Date: 2026-05-13

## Context

`code-review` now appends compact local review events, and `status --trend` / `status --snapshot` consume those events. The initial implementation left three details under-specified:

- which event supplies current `StatusResult.scores`;
- how many events the default trend should read;
- whether consumer commands such as `fix-advice` should write events.

Without a clear rule, a recent diff or fix-advice run could overwrite full-project status scores or add noise to long-term trend observations.

## Decision

Review event semantics are:

- `code-review` is the current status event producer.
- `fix-advice` remains a pure consumer and does not write review events.
- `StatusResult.scores` comes from the most recent event where `mode == "code_review"` and `review_type == "full"`.
- Diff and since events participate in `trend` counts and weakening observations, but they are not score sources.
- If no full code-review event exists, `StatusResult.scores` is `{}` and `trend.score_source` is `"none"`.
- `status --trend` reads the latest 100 events by default; no time-window filtering is applied yet.
- `weakening_components` sorts deterministically by mention count descending, then path ascending.
- Code-review event writing remains fail-open for `OSError`; the review result records `artifacts.review_event_error` and still returns normally. Non-`OSError` implementation bugs are not swallowed.

## Consequences

- A lightweight diff review no longer replaces full-project score context in status output.
- `fix-advice` suggestions do not pollute project health trends.
- Status trend behavior is stable for tests and CI because ties sort by path.
- Future time-window semantics can be added as an explicit decision without changing the current latest-100 event contract.
