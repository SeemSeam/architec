# Duplication Fix Advice Compatibility Intent

Date: 2026-05-14

## Context

The Hippocampus dogfood follow-up showed a duplication concern between
`legacy_project_prompts_dir` and `project_prompts_dir`. The finding was useful,
but the generic duplication advice leaned toward direct reuse. For legacy,
compatibility, shim, deprecation, or migration paths, intentional divergence may
be the right local boundary.

Duplication advice should keep reuse as one option while making compatibility
intent a first-class advisory option when the concern carries explicit
compatibility evidence.

## Decision

For `kind: "duplication"` concerns, `fix-advice` now detects conservative
legacy/compatibility intent from the duplicate location, reference location, or
evidence strings.

Recognized intent terms include `legacy`, `compat`, `compatibility`,
`backcompat`, `deprecated`, `deprecation`, `shim`, `migration`, and `migrate`.

When a normal `references[].role: "reference"` entry exists and compatibility
intent is detected, duplication advice adds an option to document the
compatibility intent and keep the compatibility wrapper or path separate from
the canonical implementation.

The structured duplication reference role remains `reference`.
`references[].role: "existing_implementation"` remains shadow-implementation
evidence and is not consumed by duplication advice.

Ordinary duplication advice remains unchanged when no compatibility intent is
present. If the concern lacks a duplication reference, advice remains generic
instead of inventing a compatibility direction from location text alone.

## Non-Goals

This does not:

- change `duplication` concern detection;
- change `near_duplicate` fingerprints, grouping, scope, or concern ids;
- change `ReviewConcern` or `FixAdviceResult` schema;
- make duplication consume `references[].role: "existing_implementation"`;
- decide whether compatibility code should merge or stay separate;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Compatibility-path duplication concerns produce advice that better matches
  legacy and migration boundaries.
- Plain duplication concerns still receive the existing compare/reuse/diverge
  options.
- The compatibility signal is intentionally token-based and conservative; implicit
  compatibility intent without explicit terms still receives ordinary duplication
  advice.
