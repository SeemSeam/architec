# Diff Since Scope Hygiene

Date: 2026-05-14

## Context

Hippocampus dogfood showed a trust problem in incremental review. The selected
diff changed only:

- `tests/test_llm_transport.py`
- `tests/test_prompt_propagation.py`
- `opencode.json`

The displayed top concerns were dominated by global cleanup, hotspot, and
topology observations from unrelated files. Those observations may be useful as
project context, but when they occupy `code-review --diff` / `--since`
`concerns[]`, the result looks like Architec is blaming the selected diff for
unrelated repository-wide debt.

Full review has different semantics: it is supposed to show the current project
snapshot, including global cleanup, hotspot, topology, duplication, shadow, and
architecture stability signals. This decision only changes incremental display
scope hygiene.

## Decision

For `code-review --diff` and `code-review --since <ref>`, separate selected-scope
concerns from global context concerns.

Selected-scope concerns are concerns whose primary `location.path` belongs to
the selected changed files/range. Examples include changed-file-scoped
`near_duplicate`, `shadow-implementation`, `architecture-contract`,
`plan-diff-consistency`, and risk-context-augmented concerns.

Global context concerns are generated observations whose primary location is
outside the selected changed files/range, especially cleanup, archive, hotspot,
and topology observations. These may remain available as context, signals, or
artifacts, but they should not be presented as if they are selected-diff top
concerns.

The incremental CodeReviewResult should follow these rules:

- `code-review --full` remains unchanged.
- `code-review --diff` and `code-review --since` top-level displayed
  `concerns[]` prioritize selected-scope concerns.
- Global cleanup/hotspot/topology context may remain in `signals[]`, labelled
  context fields, or artifacts.
- Summary metrics should expose selected-scope and global-context counts. At
  minimum, summary should distinguish generated selected-scope concern count,
  generated global-context concern count, displayed selected-scope concern
  count, and displayed global-context concern count.
- The complete generated concerns artifact remains available for consumers that
  need all generated observations.
- Empty incremental selected-scope results should keep neutral no-finding
  wording and may still mention that global context is available separately.

This keeps incremental review centered on the selected change while preserving
project-wide context for users who want it.

## Non-Goals

This does not:

- change detector thresholds or precision rules;
- change `near_duplicate`, `shadow_implementation`, cleanup, hotspot, or
  topology detector logic;
- change `concern_id` generation or stability semantics;
- change `fix-advice` behavior;
- change review event or `status` semantics;
- change architecture contract or plan/diff consistency semantics;
- remove global cleanup/hotspot/topology signals from full review;
- claim the selected diff is behaviorally correct.

## Consequences

- Incremental review becomes easier to trust because top-level concerns are
  visibly tied to the selected diff/since range.
- Global repository context remains inspectable without being confused with
  selected-scope findings.
- Summary counts make truncation and scope separation explicit for agents and
  downstream consumers.
- Complete generated concern artifacts remain the source for all raw generated
  observations before display selection.
