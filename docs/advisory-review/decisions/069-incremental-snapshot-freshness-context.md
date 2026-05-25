# Incremental Snapshot Freshness Context

Date: 2026-05-24

## Context

Decision 068 moved the default `archi` workflow to incremental LLM review. That
keeps short feedback loops cheap because the selected-change path does not
refresh the full Hippo bundle by default.

The remaining trust problem is transparency: incremental review may still use
local selected-scope evidence while an existing Hippo structure snapshot is
missing or stale. Users should see that boundary without paying the cost of a
full refresh on every small diff.

## Decision

Default incremental review records a `snapshot_context` signal that describes
the selected-change relationship to the current Hippo bundle without refreshing
it.

The signal records whether the Hippo bundle is present, whether freshness could
be determined, whether stale reasons were observed for selected files, whether
refresh occurred, and a bounded list of stale reasons.
`hippo_refresh_performed` is `false` for the normal incremental path.

This context is also included in the compact incremental LLM payload so the LLM
can phrase advice with the right scope. Missing or stale Hippo input does not
turn incremental review into a full review and does not stop selected-scope
analysis.

## Consequences

Incremental review remains fast and LLM-backed, while users can see when the
selected files are newer than the available whole-project structure snapshot.
`archi --full` and explicit `--refresh-from-hippo` remain the paths for
refreshed whole-project analysis.

## Non-Goals

- Refresh Hippo automatically for bare `archi`.
- Treat stale Hippo input as an incremental review error.
- Make static or incremental review equivalent to refreshed full-project
  analysis.
- Add merge decisions, repair behavior, or gate semantics.
