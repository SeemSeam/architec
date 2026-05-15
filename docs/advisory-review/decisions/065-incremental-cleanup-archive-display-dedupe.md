# Incremental Cleanup Archive Display Dedupe

Date: 2026-05-15

## Context

Decision 049 made full-review display calmer by ensuring cleanup and archive
observations for the same path/category do not both occupy top-level concern
slots. Decision 041 later separated diff/since selected-scope concerns from
global context, but it intentionally left selected-scope display ranking mostly
unchanged.

A follow-up dogfood run after Decisions 061-064 showed the remaining gap: when a
selected diff touches a file that appears in both cleanup and archive evidence,
`code-review --diff` can show both observations in the top concern portfolio.
Both observations remain useful raw context, but showing both by default spends
two incremental top-concern slots on one retention question.

## Decision

Apply the existing cleanup/archive display de-dupe to incremental selected-scope
concerns before ranking the displayed `concerns[]` portfolio.

For `code-review --diff` and `code-review --since`:

- generated concerns remain unchanged;
- selected-scope and global-context classification remains unchanged;
- `summary.scoped_concern_total` continues to count generated selected-scope
  concerns before display de-dupe;
- `summary.displayed_scoped_concern_total` counts the displayed portfolio after
  display de-dupe and ranking;
- cleanup/archive concerns sharing the same primary path and category occupy at
  most one displayed selected-scope top concern slot;
- the complete generated concerns artifact retains both cleanup and archive
  observations.

The representative selection uses the same display preference as full review:
keep the higher-confidence cleanup/archive observation for that path/category.

## Non-Goals

This does not:

- change cleanup or archive detectors;
- change diff/since scope hygiene from Decision 041;
- hide generated concerns from `.architec/code-review-concerns.json`;
- change `summary.concern_total` or `summary.scoped_concern_total` semantics;
- change concern ids, fix-advice behavior, discovery lane behavior, or payload
  guard limits;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Incremental top concerns spend fewer slots on duplicate retention context for
  one changed file.
- Consumers can still inspect complete cleanup/archive evidence through signals
  and generated concerns artifacts.
- Full and incremental display calibration now use the same same-path/category
  cleanup/archive display rule.
