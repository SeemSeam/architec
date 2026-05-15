# Advisory Recall Calibration

Architec is an advisory architecture reviewer. Its output is inspected by a
human or coding agent before any code is changed, so every useful observation
does not need to meet the same precision bar as a top-level concern.

The product goal is to avoid two failure modes:

- **Over-reporting**: low-value observations fill `concerns[]` and make reviews
  feel noisy.
- **Over-suppression**: plausible early drift signals disappear because they are
  not yet strong enough for a primary concern.

[Decision 055](../decisions/055-advisory-recall-discovery-lane.md) defines the
next direction: keep the primary concern lane precise, and add a discovery lane
for lower-confidence "worth checking" observations.

Discovery lane v1 is recorded in
[Decision 056](../decisions/056-advisory-discovery-lane-v1.md). It writes
`.architec/code-review-discovery.json` and an `advisory_discovery` signal when
suppressed `near_duplicate` candidates or module-level shadow dry-run candidates
exist. It does not promote those candidates into primary concerns.

## Review Lanes

Primary lane:

- visible in top-level `concerns[]` and `evidence[]`;
- should stay high-confidence, scoped, and actionable;
- should continue to respect diff/since scope hygiene and full-review display
  calibration;
- should remain small enough for coding agents to read first.

Discovery lane:

- may live in artifacts or clearly labelled signal metrics;
- can include lower-confidence or intentionally suppressed candidates;
- should explain why the candidate was not promoted;
- should be queryable for dogfood and calibration;
- should not change `summary.concern_total` until a candidate is promoted.

## Candidate Sources

Good first candidates for discovery are signals that already exist internally
but are not safe enough for default top concerns:

- `shadow_implementation` parser subdomain matches in protocol/version parsing
  libraries;
- file/module-level `shadow_implementation` dry-run pairs after source scope
  filtering;
- near-duplicate candidates suppressed as variant families or paired APIs, with
  counts for calibration rather than individual concerns;
- plan/diff semantic intent checks that are explicit but weakly scoped;
- concerns that become more interesting only when risk context says the file is
  high churn, low coverage, public API, or recurring.

## Promotion Rules

Discovery should not be a dumping ground. A candidate should become a primary
concern only when at least one reinforcing condition exists:

- it is scoped to the selected changed files in diff/since review;
- it matches an architecture contract or saved plan-review expectation;
- external risk context raises the maintenance impact;
- it recurs across review events;
- dogfood confirms the pattern is useful on real projects.

If no reinforcing condition exists, the candidate can stay in artifact context
or remain only as a metric.

## Testing Plan

The next implementation should be tested on both synthetic fixtures and real
repositories:

- Architec itself, to ensure existing high-value concerns do not disappear.
- Hippocampus, to ensure diff/since top concerns stay scoped.
- `packaging`, to inspect parser-subdomain and paired-API discovery quality.
- `humanize`, to ensure intentional paired accessors stay out of primary
  concerns.
- `itsdangerous`, to ensure compact mature libraries still produce little or no
  discovery noise.

Useful acceptance checks:

- `concerns[]` does not grow just because discovery candidates exist;
- complete artifacts contain labelled discovery data when available;
- summary or signal metrics distinguish promoted concerns from discovery
  candidates;
- forbidden gate/verdict/pass/fail/block/must-fix/patch/apply terms remain
  absent from user-facing output;
- dogfood notes record whether a discovery candidate would have been useful.
