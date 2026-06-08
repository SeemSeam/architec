# Incremental Static Degradation

Date: 2026-05-15

Superseded in part by Decision 071: backend LLM configuration preflight
failures are input errors and do not enter static degradation. The runtime LLM
degradation path described here still applies.

## Context

Post-Decision 065 dogfood against this repository showed that
`code-review --diff` can still stop before returning a CodeReviewResult when the
backend weak LLM channel is unavailable. Full review already has an explicit
static degradation path, but incremental review remained all-or-nothing even
though selected changed files can be obtained deterministically from git.

Because Architec is advisory, an incremental review should prefer a structured
degraded result when selected-file scope can still be established.

## Decision

Add a static incremental degradation path for backend LLM unavailability.

For `code-review --diff` and `code-review --since`, when backend LLM preflight
or runtime raises `ArchitectLLMUnavailableError`, the CLI returns a
CodeReviewResult built from deterministic selected-scope signals:

- changed files are read from the existing git numstat/status helper;
- `near_duplicate` and `shadow_implementation` run in changed-file scoped mode;
- architecture contracts and plan/diff consistency still run when their inputs
  are available;
- optional `--risk-context` enrichment still attaches to matching concerns.

The degraded result is explicit:

- `summary.analysis_mode` is `static`;
- `summary.headline` says diff or since analysis was unavailable and static
  code-review signals were generated;
- `summary.reason` records the backend availability reason;
- `artifacts.code_review_analysis_mode` is `static`;
- `artifacts.code_review_static_reason` records the same reason.

Since bad-ref and invalid git range handling remains unchanged: if git cannot
resolve the requested since range, the existing since-range degraded result is
returned and plan/risk inputs are not loaded.

Bundle validation errors still do not degrade diff/since review. The static
incremental path needs a readable project and git scope; it does not replace
bundle/source validation.

## Non-Goals

This does not:

- claim static incremental review is equivalent to full Hippo/LLM-backed diff
  analysis;
- run cleanup/archive/hotspot/topology global context in static incremental
  mode;
- change detector thresholds, concern schema, concern ids, ranking, payload
  guard, discovery artifact schema, or fix-advice behavior;
- change since bad-ref semantics;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics.

## Consequences

- Dogfood can continue to inspect deterministic selected-scope duplicate,
  shadow, contract, plan/diff, and risk-context signals when backend LLM
  infrastructure is temporarily unavailable.
- Static degraded incremental review is visibly marked so consumers do not
  mistake it for the full LLM-backed diff analysis path.
- Full review static degradation and incremental static degradation now share
  the same explicit `analysis_mode=static` marker family.
