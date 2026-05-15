# Advisory Recall Discovery Lane

Date: 2026-05-15

## Context

Earlier AI-drift work optimized heavily for precision. That was useful for
making top concerns credible, but Architec is an advisory reviewer, not a merge
gate or auto-fixer. A coding agent or human still reviews the recommendation
before changing code.

That product boundary means some plausible but lower-confidence architecture
signals are still valuable. If Architec hides every uncertain duplicate,
shadow, parser, or intent-drift candidate, it can miss the early signs of
vibe-coding drift that the tool is meant to surface.

The dogfood runs showed both sides of the tradeoff:

- mature-library calibration should keep low-value noise out of top concerns;
- but `shadow_implementation` parser subdomain cases and module-level dry-run
  candidates can still be useful as "worth checking" signals when presented in
  the right lane.

## Decision

Introduce a two-lane review model for future code-review refinements:

1. **Primary concern lane**: `concerns[]`, `evidence[]`, and the default human
   summary remain concise and high-precision. Existing scope hygiene, payload
   guard, portfolio ranking, and suppression decisions still apply.
2. **Discovery lane**: plausible lower-confidence candidates may be retained in
   artifacts or clearly labelled signal metrics as advisory discovery
   observations. They are not default top concerns and do not imply that code is
   wrong.

Discovery candidates may include:

- low-confidence `shadow_implementation` candidates that are below the current
  concern threshold but still have strong local evidence;
- parser-subdomain candidates that should be reviewed as possible intent drift
  before being promoted or suppressed;
- module/file-level shadow dry-run candidates after source scope filtering;
- suppressed duplicate families where the suppressor is useful for explainable
  calibration counts;
- plan/diff semantic intent hints that are explicit but not strong enough to
  become a primary concern.

Promotion from discovery to a primary concern should require reinforcing
evidence, such as:

- changed-file scope in diff/since review;
- matching project architecture contract or saved plan-review expectation;
- external risk context such as high churn, low coverage, public API surface, or
  recurrence;
- repeated appearance across review events;
- manual or dogfood confirmation that the pattern is useful.

## Non-Goals

This does not:

- loosen default top-level `concerns[]` quality;
- turn discovery candidates into merge gates;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics;
- make Architec prove correctness;
- run LLM requirement inference over prose;
- make `fix-advice` act on discovery candidates by default;
- change existing concern ids for already emitted concerns.

## Consequences

- Architec can improve recall without flooding the primary review output.
- Dogfood can measure hidden candidate quality before changing public concern
  behavior.
- `status` and future calibration work can use discovery counts to explain
  whether signals are being suppressed, promoted, or recurring.
- The next implementation should start with an artifact-only or signal-metric
  discovery surface, then promote only patterns validated by dogfood or
  reinforcing project evidence.
