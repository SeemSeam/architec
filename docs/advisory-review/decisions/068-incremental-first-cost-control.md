# Incremental-First LLM Cost Control

Date: 2026-05-23

## Context

`archi code-review --full` is useful for baseline understanding, release checks,
and unfamiliar repositories, but it is too expensive as the default feedback
loop for short-lived coding changes. Agent-driven development usually needs a
fast answer to a narrower question: did this selected diff introduce structural
drift, duplicate implementation, boundary pressure, or a mismatch with an
accepted plan?

Earlier decisions already moved diff/since output toward selected-scope
observations and added static degradation when the backend LLM path is
unavailable. The remaining product gap is default cost shape and command
simplicity: normal incremental review should use an LLM, but it should not
behave like a full project analysis with a smaller display filter.

## Decision

Recenter the user-facing command surface around two modes:

- `archi` means incremental LLM-backed architecture review for the current
  selected changes.
- `archi --full` means full-project LLM-backed architecture review.

- Full review remains the explicit baseline path for whole-project structural
  narrative, release readiness, and scheduled health snapshots.
- Incremental review should run deterministic selected-scope scanners first,
  then send the compact selected-scope evidence to an LLM for interpretation.
  The deterministic pass uses git changed files, scoped near-duplicate and
  shadow implementation detectors, architecture contracts, plan/diff
  consistency, and optional risk-context facts.
- Incremental review should avoid automatic full Hippo refresh or full-project
  LLM prompts. Cost control comes from smaller context, bounded LLM calls, and
  reuse of selected-scope inputs, not from removing the LLM from normal review.
- Do not expose a broad public budget matrix for the common workflow. Advanced
  `code-review --diff/--since` flags can remain for compatibility or debugging,
  but normal documentation and skills should teach `archi` and `archi --full`.
- Diff/since should expose cost and scope metadata, such as selected file count,
  LLM-backed mode, LLM call count, cache hit count, and elapsed time where
  available.
- Cacheable selected-scope inputs should be reused by file hash or mtime where
  doing so does not hide changed-file evidence.

## Consequences

This makes the common review loop cheaper and more predictable without making
users choose between many command flags. It also makes the product boundary
clearer: `archi --full` answers "what is the repository's current architecture
shape?", while `archi` answers "what did this change do to the architecture
surface?".

The next implementation should focus on the incremental command path, compact
LLM prompt construction, metrics, and tests that assert small diffs use a
bounded incremental LLM path rather than full-project analysis. Exact escalation
thresholds remain calibration work and should be dogfooded before being treated
as stable defaults.

## Non-Goals

- Remove or weaken `code-review --full`.
- Remove LLM interpretation from normal incremental review.
- Expose many routine command parameters for cost tuning.
- Treat static degradation as equivalent to normal LLM-backed incremental
  review.
- Create merge decisions or automatic repair behavior.
- Infer requirements from prose with an LLM.
- Hide raw generated concerns, discovery artifacts, or explicit risk-context
  facts.
