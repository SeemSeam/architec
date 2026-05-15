# AI Drift Mature Library Calibration

Date: 2026-05-15

## Context

The multi-repo dogfood run against `packaging`, `itsdangerous`, and `humanize`
showed that deterministic AI drift scanners behave well on some compact mature
libraries, but still need mature-library calibration for low-value duplicate
signals.

The noisy cases were not evidence that those repositories should change code.
They were Architec product signals:

- benchmark functions under `benchmarks/` intentionally repeat timing shapes;
- same-file paired API variants such as `__and__` / `__or__`, `post` / `dev`,
  and `thousands_separator` / `decimal_separator` intentionally share shape
  because the public API is symmetric or parallel.

The source dogfood note is
[multi-repo-dogfood-audit-2026-05-14.md](../topics/multi-repo-dogfood-audit-2026-05-14.md).

## Decision

Calibrate AI drift scanners for mature-library support code and explicit paired
API variants.

Default source scanning should exclude `benchmark` and `benchmarks` path
segments for AI drift scanners, alongside existing tests, fixtures, generated
state, vendor, build, cache, and local agent-state exclusions.

For `near_duplicate`, suppress conservative same-file exact-fingerprint paired
API variants in v1:

- `__and__` / `__or__`;
- `post` / `dev` property or accessor pairs;
- `thousands_separator` / `decimal_separator` locale accessor pairs.

The paired API suppression is intentionally narrow. It only applies to
same-file exact-fingerprint pairs matching explicit known paired API names.

## Non-Goals

This does not:

- suppress paired variants across files;
- suppress broad semantic synonyms;
- change emitted concern schema;
- change `concern_id` semantics for emitted concerns;
- suppress substantive duplicates;
- change `shadow_implementation` public schema;
- solve Hippo bundle source-scope alignment;
- add backend LLM fallback behavior;
- add shadow parser subdomain taxonomy;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Mature-library benchmark suites are less likely to produce low-value AI drift
  scanner findings.
- Common intentional same-file API pairs no longer occupy `near_duplicate` top
  concern slots.
- Cross-file duplicates, non-paired same-file duplicates, and substantive
  repeated logic remain reportable.
- Shadow parser subdomain taxonomy and full-review dogfood reliability remain
  separate follow-up workstreams.
