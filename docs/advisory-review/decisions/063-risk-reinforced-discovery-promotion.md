# Risk-Reinforced Discovery Promotion

Date: 2026-05-15

## Context

Decisions 055 and 056 established the advisory discovery lane: lower-confidence
or intentionally suppressed candidates are retained in artifacts and labelled
signals without inflating default `concerns[]`.

The next useful calibration step is not to promote all discovery candidates.
Some discovery reasons, such as explicit paired API variants, are usually
intentional public API symmetry. Others, especially different-target thin
wrappers, can become worth reviewing when external risk context says the file is
public API, high churn, low coverage, complex, recurring, or has no mapped
tests.

## Decision

Promote a narrow subset of discovery candidates into primary concerns only when
external `--risk-context` supplies reinforcing facts for the candidate's
location path.

V1 promotion applies to `near_duplicate` discovery candidates with reason:

- `thin_wrapper_different_target`
- `variant_family_thin_wrapper_different_target`

Promotion requires at least one risk-context reinforcement factor:

- `low_coverage`
- `high_churn`
- `high_complexity`
- `public_api`
- `recurring_history`
- `missing_related_tests`

Promoted candidates become low-severity `duplication` concerns with:

- `level: "info"`
- `confidence: 0.68`
- factual `advisory_discovery.reason=...` evidence
- factual `advisory_discovery.promoted_by=risk_context` evidence
- one `advisory_discovery.reinforcement=...` fact per reinforcing factor
- ordinary `references[].role: "reference"` when a reference location exists

The candidate remains in `.architec/code-review-discovery.json`, labelled with
promotion metadata. The `advisory_discovery` signal includes `promoted_total`.

## Non-Goals

This does not:

- promote paired API variants such as `post` / `dev` or
  `thousands_separator` / `decimal_separator`;
- promote module-level shadow dry-run candidates;
- promote discovery candidates without explicit external risk context;
- infer risk from prose or LLM output;
- change discovery artifact path, fix-advice schema, concern ids for existing
  concerns, or detector thresholds;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics.

## Consequences

- Discovery remains a safe calibration lane by default.
- Risk-reinforced wrapper/facade drift can reach the primary review lane when
  an external report says the file has higher maintenance impact.
- Mature-library paired API variants continue to stay out of primary concerns.
