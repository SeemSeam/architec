# Semantic Review Display Reinforcement

Date: 2026-05-15

## Context

Decision 061 demotes stale-doc cleanup/archive observations when the semantic
cleanup judge marks the same path `keep_active`. The remaining full-review
display question is the opposite case: when the semantic judge explicitly says a
cleanup/archive path still needs `review`, the default display should preserve
that signal even if the original heuristic confidence is modest.

Because Architec is advisory and top concerns are reviewed before any code
changes, an explicit semantic `review` judgment is useful reinforcement for the
human or coding agent reading the portfolio.

## Decision

For full-review generated cleanup/archive concerns only, when
`semantic_judge.status` is `ok` and `semantic_judge.judgments[]` or
`semantic_judge.top_judgments[]` contains the same normalized path with
`decision: "review"`:

- append factual evidence `semantic_judge.decision=review`;
- raise the concern confidence to at least `0.76` for ranking/display purposes.

This applies only to cleanup/archive display concerns. It does not affect
hotspot, topology, duplicate, shadow, architecture-contract, plan-diff, or
discovery-lane candidates.

## Non-Goals

This does not:

- create new concerns from semantic judge output alone;
- override Decision 061 `keep_active` demotion;
- apply to semantic judge statuses other than `ok`;
- interpret prose beyond the normalized semantic judge decision field;
- change concern ids, concern kind, signal metrics, payload guard, discovery
  artifact schema, or fix-advice behavior;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics.

## Consequences

- Full-review top concerns can better reflect the LLM semantic cleanup judge
  when it reinforces heuristic cleanup/archive observations.
- The reinforcement is visible in concern evidence and complete artifacts.
- Raw cleanup/archive and semantic judge artifacts remain the source of detailed
  context; the primary lane still stays small and advisory.
