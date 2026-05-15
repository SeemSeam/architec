# Semantic Archive Retire Display Reinforcement

Date: 2026-05-15

## Context

Decision 061 demotes stale-doc cleanup/archive display concerns when the
semantic cleanup judge explicitly marks the same path `keep_active`. Decision
062 reinforces cleanup/archive display concerns when the semantic judge marks
the same path `review`.

The remaining full-review display question is the stronger action case. When
the semantic judge successfully reviews a cleanup/archive path and says
`archive_first` or `retire_now`, the default display should not rely only on
the original cleanup/archive heuristic confidence. The semantic decision is
still advisory, but it is useful factual reinforcement for the human or coding
agent reading full-review top concerns.

## Decision

For full-review generated cleanup/archive display concerns only, when all of
the following are true:

- `semantic_judge.status` is `ok`;
- `semantic_judge.judgments[]` or `semantic_judge.top_judgments[]` contains the
  same normalized path;
- the matching semantic decision is `archive_first` or `retire_now`;

then the display layer may reinforce the matching cleanup/archive concern by:

- appending factual evidence such as
  `semantic_judge.decision=archive_first` or
  `semantic_judge.decision=retire_now`;
- raising the display confidence to a conservative floor for ranking/display
  purposes.

This is a display reinforcement only. It does not create a concern from semantic
judge output alone, and it does not decide that the file should actually be
archived or retired.

## Non-Goals

This does not:

- override Decision 061 `keep_active` demotion;
- change Decision 062 `review` reinforcement behavior;
- apply when `semantic_judge.status` is not `ok`;
- apply to hotspot, topology, duplicate, shadow, architecture-contract,
  plan-diff, or discovery-lane candidates;
- change cleanup/archive detectors;
- change signal schema;
- change discovery lane behavior;
- change concern schema, id, kind, or level;
- change fix-advice behavior;
- change payload guard behavior;
- change the generated-concerns artifact contract or raw detector outputs;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Full-review top concerns can better reflect semantic cleanup decisions when
  the semantic judge reinforces archive/retire action candidates.
- The reinforcement remains traceable as evidence on existing cleanup/archive
  concerns.
- Raw cleanup/archive signals, semantic judge artifacts, and the
  generated-concerns artifact contract remain available for auditing.
- The advisory boundary stays intact: Architec reports evidence and display
  emphasis, not an execution decision.
