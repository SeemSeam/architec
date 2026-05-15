# Near Duplicate Member Variant Families

Date: 2026-05-15

## Context

The multi-repo dogfood run after Decisions 054/056/057/058 showed that mature
libraries can still produce several `near_duplicate` primary concerns for
intentional same-file API families. Examples from `packaging` included
`Version.major` / `Version.minor` / `Version.micro`, `PackageWheel` /
`PackageSdist` members, `Specifier` class-family methods, and bound comparison
helpers.

These are still useful architectural observations, but repeated one-concern-per
member output can make mature public API variants look like accidental drift.

## Decision

Extend `near_duplicate` variant-family grouping for same-file class/member
families.

The grouping remains conservative:

- candidates must still share an exact normalized AST fingerprint;
- candidates must be in the same file;
- grouped candidates must share a normalized member-family key, such as:
  - release segment accessors (`major`, `minor`, `micro`) under the same parent;
  - class variant members where parent tokens normalize by dropping narrow
    variant modifiers such as `base`, `set`, `wheel`, `sdist`, `lower`, or
    `upper`;
  - the same member name on a normalized class-family parent.

Grouped output stays in the existing `duplication` concern schema. It adds
factual `near_duplicate.variant_family` and
`near_duplicate.variant_member_total` evidence, just like the existing phase /
cache / prompt-builder family grouping.

Also extend paired API suppression to prefixed explicit variants such as
`_validate_dev` / `_validate_post`: if same-file same-parent functions differ
by exactly one token and that token pair is on the explicit paired-API allowlist,
they are suppressed from primary concerns and retained in discovery.

## Non-Goals

This does not:

- group cross-file duplicates;
- infer semantic equivalence from prose or LLMs;
- suppress substantive non-family duplicates;
- change concern schema, `references[].role`, concern ids, fix-advice, payload
  guard, or discovery artifact schema;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics.

## Consequences

- Mature public API families produce fewer repeated top-level duplication
  concerns while preserving a primary advisory observation.
- Explicit prefixed paired variants move to the discovery lane, where they can
  be inspected during dogfood without occupying primary concern slots.
- Remaining cross-file helper duplicates, such as credible shared parsing or
  validation helpers, remain reportable.
