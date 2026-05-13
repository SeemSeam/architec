# Fix Advice Review Flag

Date: 2026-05-13

## Context

`fix-advice` originally used `--for <review.json>` to identify the review JSON to consume. The flag works, but `for` is a Python reserved word and requires argparse destination handling in the CLI. It is also less explicit than the object it points to.

Existing scripts and documentation already use `--for`, so removing or warning on it would create unnecessary migration churn.

## Decision

Make `--review <review.json>` the canonical flag for `archi fix-advice`.

`--for <review.json>` remains a compatibility alias. It is not soft-cut and does not emit a warning.

The two flags are mutually exclusive, and one of them is required. Both write to the same CLI namespace field, `args.review`.

## Non-Goals

This does not:

- remove `--for`;
- add a deprecation warning;
- change `run_fix_advice()` public API;
- change FixAdviceResult schema;
- change fix-advice input error handling;
- change advisory-only semantics.

## Consequences

- New documentation can recommend `archi fix-advice --review <review.json>`.
- Existing `archi fix-advice --for <review.json>` scripts remain valid.
- CLI code no longer treats `--for` as the canonical user-facing name.
