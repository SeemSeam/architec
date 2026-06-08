# Full Code Review Static Degradation

Date: 2026-05-15

Superseded in part by Decision 071: backend LLM configuration preflight
failures are input errors and do not enter static degradation. The runtime LLM
and Hippo bundle degradation paths described here still apply.

## Context

Multi-repo dogfood showed that `code-review --full` can stop before returning a
review when Hippo bundle validation or backend LLM preflight is unavailable.
That makes external dogfood difficult even though the deterministic AI drift
scanners can still provide useful advisory signals.

Because Architec is advisory, a full review should prefer a structured degraded
result over a hard stop when the only blocked pieces are bundle/LLM-backed full
analysis steps.

## Decision

Add a static full-review degradation path.

For full code review only, when the CLI cannot validate or refresh the Hippo
bundle, or backend LLM preflight/runtime raises `ArchitectLLMUnavailableError`,
the command returns a CodeReviewResult built from deterministic code-review
signals:

- `near_duplicate` primary concerns and discovery candidates;
- `shadow_implementation` primary concerns;
- module-level `shadow_implementation` dry-run discovery candidates;
- optional `--risk-context` enrichment when it matches generated concerns.

The degraded result is explicit:

- `summary.headline` is `Full analysis was unavailable; static code-review
  signals were generated.`
- `summary.analysis_mode` is `static`.
- `summary.reason` records the bundle or backend LLM availability reason.
- `artifacts.code_review_analysis_mode` is `static`.
- `artifacts.code_review_static_reason` records the same reason.

Diff and since review remain strict: their selected-change semantics depend on
full diff analysis, so bundle or LLM unavailability still returns the existing
CLI error path.

## Non-Goals

This does not:

- claim static full review is equivalent to full Hippo/LLM-backed analysis;
- run plan/diff consistency without selected changed files;
- change detector thresholds, concern schema, concern ids, ranking, payload
  guard, discovery artifact schema, or fix-advice behavior;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics.

## Consequences

- Dogfood can continue to inspect deterministic duplicate/shadow/discovery
  signals when bundle scope or backend LLM infrastructure is unavailable.
- Static degraded full review is visibly marked so consumers do not mistake it
  for the full analysis path.
- The remaining dogfood follow-up is to repeat multi-repo runs and decide
  whether any discovery candidates deserve promotion rules.
