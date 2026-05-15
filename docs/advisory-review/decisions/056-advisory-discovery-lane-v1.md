# Advisory Discovery Lane V1

Date: 2026-05-15

## Context

[Decision 055](055-advisory-recall-discovery-lane.md) defined a two-lane model:
primary `concerns[]` stays high-precision, while lower-confidence candidates can
be retained in a labelled discovery lane.

The first implementation should be small and measurable. It should expose
already available static candidates without changing default review behavior.

## Decision

Add an `advisory_discovery` signal and a generated discovery artifact:

- `.architec/code-review-discovery.json`
- `artifacts.code_review_discovery_json`
- `artifacts.code_review_discovery_error` for fail-open `OSError`

The v1 discovery lane includes:

- `near_duplicate` candidates suppressed before concern construction, such as
  different-target thin wrappers, explicit paired API variants, or variant
  families whose representative pair is itself suppressed;
- file/module-level `shadow_implementation` dry-run candidates from
  `shadow_implementation_file_dry_run`.

The artifact contains labelled candidates with source and reason fields. The
signal exposes only aggregate metrics:

- `candidate_total`
- `reported_total`
- `by_source`
- `by_reason`

The primary review lane is unchanged:

- discovery candidates do not enter `concerns[]`;
- discovery candidates do not enter derived `evidence[]`;
- discovery candidates do not increment `summary.concern_total`;
- discovery candidates are not inputs to `fix-advice`;
- existing concern ids are unchanged.

## Non-Goals

This does not:

- promote parser subdomain candidates into primary concerns;
- change `shadow_implementation` thresholds or public schema;
- change `near_duplicate` emitted concern schema;
- add LLM/prose requirement inference;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics.

## Consequences

- Dogfood can inspect what Architec suppressed or kept in dry-run without making
  the default review noisy.
- Future work can decide which discovery sources deserve promotion rules.
- Consumers that only read `concerns[]` see no behavior change.
