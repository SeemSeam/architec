# Shadow Implementation Fix Advice

Date: 2026-05-13

## Context

`shadow_implementation` now reports Python function-level and class-level concerns in code review. The concern `location` points at the suspected shadow implementation, while `references[]` can include an `existing_implementation` location for the implementation it resembles.

Before this decision, `fix-advice` treated `kind: "shadow-implementation"` as an unknown concern. That kept the output advisory-only, but it missed structured context that code review already exposes.

## Decision

`fix-advice` consumes `shadow-implementation` concerns with `references[].role: "existing_implementation"` and emits a dedicated advisory suggestion.

For function-level shadow concerns, advice compares the changed function with the existing implementation and presents options such as:

- route through or reuse the existing implementation when behavior should be shared;
- keep implementations separate when the roles only appear similar;
- document intentional divergence when both implementations remain.

For class-level shadow concerns, advice compares the changed class with the existing class and presents options such as:

- reuse the existing class when it already owns the behavior;
- extract shared behavior when both classes have a stable common core;
- document intentional divergence when lifecycle, context, or configuration differs.

If the concern lacks a structured `existing_implementation` reference, `fix-advice` stays conservative and explains that reference evidence is insufficient. Compatibility parsing of legacy evidence strings can be used only as a fallback.

## Non-Goals

This does not:

- generate patches or executable edits;
- add an apply mode;
- decide whether the existing or changed implementation is correct;
- choose a merge direction;
- add file-level shadow detection;
- change detector thresholds or shadow concern generation;
- change duplication `references[].role: "reference"` semantics.

## Consequences

- Saved reviews with structured shadow references now produce more specific repair-direction options.
- Reviews without structured references remain valid and produce conservative output.
- `duplication` and `shadow-implementation` keep distinct reference roles: `reference` for near duplicates, `existing_implementation` for shadow implementation.
- The advisory boundary stays unchanged: code review reports evidence, and fix-advice suggests options without applying changes.
