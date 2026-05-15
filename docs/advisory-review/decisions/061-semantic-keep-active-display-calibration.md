# Semantic Keep-Active Display Calibration

Date: 2026-05-15

## Context

The multi-repo dogfood retest after Decision 060 confirmed that `packaging`,
`itsdangerous`, and `humanize` can now reach normal full review when backend LLM
analysis is available. It also showed a remaining full-review display issue:
cleanup/archive stale-doc observations for changelogs or docs-side build files
can still enter top-level `concerns[]` even when the semantic cleanup judge
explicitly classifies the same path as `keep_active`.

Because `concerns[]` is the default display portfolio, it should not continue to
highlight a stale-doc/archive observation after the semantic judge has already
found active-retention evidence for that path. The raw cleanup/archive signals
and artifacts should remain available for auditing.

## Decision

For full review display only, demote cleanup/archive concerns when all of the
following are true:

- the generated concern is a cleanup/archive display concern with
  `stale_doc` category;
- `semantic_judge.status` is `ok`;
- `semantic_judge.judgments[]` or `semantic_judge.top_judgments[]` contains the
  same normalized path with `decision: "keep_active"`.

The concern remains in the complete generated-concerns artifact and the
cleanup/archive/semantic-judge signals remain unchanged. The calibration only
affects the displayed `concerns[]`, derived `evidence[]`, and
`summary.top_concern_total`.

## Non-Goals

This does not:

- remove cleanup/archive detector output or semantic judge artifacts;
- demote non-`stale_doc` cleanup categories such as fallback or legacy source
  observations;
- hide stale-doc observations when the semantic judge says `review`,
  `archive_first`, `retire_now`, `skipped`, or `unavailable`;
- change concern ids, concern schema, signal metrics, payload guard, discovery
  lane behavior, or fix-advice behavior;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics.

## Consequences

- Active changelog, release-note, and docs-infrastructure files are less likely
  to occupy default top concern slots after semantic review already explains why
  they should remain active.
- Full generated concerns still preserve the original heuristic output for
  traceability.
- Future calibration can decide whether semantic judge `review` decisions
  should receive stronger top-concern treatment, but this step only demotes
  clear `keep_active` stale-doc conflicts.
