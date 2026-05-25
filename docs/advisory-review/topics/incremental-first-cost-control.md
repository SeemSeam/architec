# Incremental-First LLM Cost Control

Date: 2026-05-23

## Purpose

This topic records the next product shift for Architec: make short-term
incremental architecture review the default LLM-backed loop, and keep full
analysis as an explicit baseline operation.

The decision is recorded in
[Decision 068](../decisions/068-incremental-first-cost-control.md). Snapshot
freshness context is recorded in
[Decision 069](../decisions/069-incremental-snapshot-freshness-context.md), and
the command surface documentation cleanup is recorded in
[Decision 070](../decisions/070-command-surface-documentation-cleanup.md).

## Problem

Full project analysis is valuable but expensive. It can involve Hippo bundle
refresh, broad repository context, semantic cleanup judgment, full-project
signals, and full-project LLM narrative. That is the wrong cost profile for the
most common agent workflow: a small diff after one implementation step.

For that workflow, the useful question is narrower:

- Did the changed files add duplicate or shadow implementation?
- Did the changed files violate a declared architecture boundary?
- Did the diff drift from the reviewed plan?
- Did the diff omit expected tests, imports, migrations, or explicit intent
  touchpoints?
- Are the selected files already high-risk according to provided external
  risk context?

## Command Model

The common command model should stay simple:

| Command | Intended use | LLM use | Full Hippo refresh |
| --- | --- | --- | --- |
| `archi` | Day-to-day review of current selected changes | Yes, bounded incremental prompt | No by default |
| `archi --full` | Whole-project baseline and release-style review | Yes, full-project context | Explicit/allowed |

The internal implementation may keep `code-review --diff`, `--since`, or debug
flags, but the user-facing workflow should not require a budget matrix. The
normal skill and README surface should teach:

```bash
archi
archi --full
```

If there are no selected changes, `archi` should not silently perform a full
review. It should return a clear incremental empty-state result and point users
to `archi --full` when they want a baseline.

## Incremental Pipeline

V1 implementation status: bare `archi` now uses this incremental LLM path, and
`archi --full` remains the full-project path. Existing `code-review --diff` /
`--since` paths remain available for compatibility and advanced use.

The low-cost incremental path should:

1. Resolve selected files from git diff or since range.
2. Run deterministic selected-scope scanners only:
   near duplicate, shadow implementation, architecture contracts, plan/diff
   consistency, advisory discovery, and optional risk-context enrichment.
3. Build a compact LLM prompt from selected-scope evidence, changed-file
   summaries, relevant rules, and optional plan/risk inputs.
4. Avoid global cleanup/archive/hotspot/topology narrative unless the user runs
   `archi --full`.
5. Produce the same `CodeReviewResult` shape, with `summary.analysis_mode` or a
   nearby summary field making the incremental LLM path visible.
6. Record `cost_context` or equivalent signal metrics for selected file count,
   LLM call count, cache hits, and elapsed time.
7. Record `snapshot_context` metrics for Hippo bundle presence, unknown
   freshness, and selected-file freshness without refreshing Hippo on the
   normal incremental path.

## Cache And Reuse

Incremental review should prefer cheap reuse:

- Do not refresh Hippo by default for normal `archi` incremental review.
- Inspect Hippo bundle freshness as context only; missing or stale snapshots
  should not stop selected-scope review.
- Cache parsed AST/import/signature inputs by path plus content hash or mtime.
- Reuse selected-scope detector inputs across `near_duplicate`,
  `shadow_implementation`, plan/diff consistency, and architecture contracts
  where practical.
- Keep cache misses conservative: stale or unreadable cache entries should fall
  back to local parsing, not suppress observations.

## Tests And Dogfood

Implementation should add tests that prove:

- `archi` routes to incremental selected-scope review by default.
- `archi` uses the bounded incremental LLM path, not full-project analysis.
- Small diffs do not attempt full Hippo refresh.
- `archi --full` still routes to full-project LLM review.
- Existing plan-review, risk-context, architecture-contract, near-duplicate,
  and shadow selected-scope observations still appear.
- Summary metrics distinguish selected-scope generation from cost
  telemetry.

Dogfood should include:

- `architec` itself, especially small self-diffs.
- `/home/bfly/yunwei/ccb_source`, after refreshing Hippo explicitly when a full
  baseline is needed.
- `hippocampus`, to compare selected-scope results against prior full-review
  behavior.

## Remaining Calibration

The main unresolved calibration questions are:

- What exact selected-change source should bare `archi` use when both staged
  and unstaged changes exist?
- What prompt-size or stale-snapshot threshold should trigger a suggestion to
  run `archi --full` instead of expanding incremental context?
- How should cost telemetry be named so it is useful without becoming a
  scoring or gate concept?
- What cache invalidation evidence is enough for users to trust a cheap result?
- How should elapsed time and real cache hit counts be collected without
  slowing the selected-change path itself?
