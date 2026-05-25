# Advice Feedback Ledger

Date: 2026-05-18

## Context

Architec is intentionally advisory. Its recommendations can be broader than a
merge gate because a human or coding agent reviews the advice before code is
changed.

That also means some suggestions will be wrong for a specific project. If a
reviewer rejects a suggestion as incorrect or not applicable, the same weak
claim should not keep reappearing in later reviews just because the LLM or
heuristic scanner sees the same surface evidence again.

This should be handled as project-local evidence, not as provider memory. The
feedback must be auditable, deterministic, and visible to future Architec runs.

## Decision

Add an advice feedback ledger.

The ledger records reviewer decisions about Architec advice items. It is a
project-local generated/configurable input. V1 consumes it through explicit
`--advice-feedback <json>` on full review and `fix-advice`; a future helper may
write `.architec/advice-feedback.json`.

Each feedback entry should identify the advice item and the scope of the
decision:

- stable `advice_id` or `concern_id` when available;
- `kind`, `path`, optional `symbol`, and optional source signal;
- reviewer status such as `accepted`, `rejected`, `not_applicable`,
  `deferred`, or `superseded`;
- a short reviewer reason;
- scope such as `exact_advice`, `same_path_kind`, or `pattern`.

Reviews should consume the ledger before final display:

- exact rejected advice should not re-enter default top recommendations;
- same path/kind feedback should reduce display strength unless new evidence is
  present;
- pattern-level feedback may move similar future candidates to artifact or
  discovery context;
- if a previously rejected item appears again because new evidence exists, the
  output should say which new evidence changed the recommendation.

V1 affects human-readable full-review recommendations and `fix-advice`
suggestions. Later versions may extend to broader display calibration. The
ledger must not erase raw scanner output or generated artifacts.

## Non-Goals

This does not:

- make Architec remember private conversation state outside the project;
- make rejected advice disappear from complete artifacts;
- change detector thresholds by default;
- make reviewer feedback a merge gate or correctness proof;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics;
- require LLM natural-language inference over arbitrary feedback prose.

## Consequences

- Architec can be intentionally broad while still learning from project-specific
  review outcomes.
- Incorrect advice becomes structured calibration input instead of repeated
  noise.
- The first implementation stays narrow: explicit feedback input, full-review
  recommendations, and `fix-advice`; later versions can expand to helper
  commands, duplicate/shadow/topology observations, and status summaries.
