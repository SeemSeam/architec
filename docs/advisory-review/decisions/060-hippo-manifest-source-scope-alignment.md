# Hippo Manifest Source Scope Alignment

Date: 2026-05-15

## Context

The multi-repo dogfood retest after Decisions 054/056/057/058/059 showed that
`packaging` and `itsdangerous` still degraded to static full review even though
backend LLM execution was available. Both fresh Hippo bundles were rejected as
stale because `file-manifest.json` marked `docs/conf.py` or `docs/Makefile` as
source, while Architec's local `path_kind()` classified those paths as docs.

That mismatch made a freshly generated bundle fail validation immediately:

```text
file-manifest.json does not match current source tree (added=0, removed=2)
```

## Decision

When validating a Hippo bundle, Architec treats manifest-declared source paths as
part of the current architecture source scope if the files still exist and are
not ignored by architecture rules.

The current source mtimes used for bundle validation now include paths that are:

- classified as `source` by Architec's local path policy; or
- present in the Hippo `file-manifest.json` architecture path set through
  `include_in_architecture=true`, `kind=source`, or the existing manifest
  fallback behavior.

This keeps validation aligned with the producer that created the bundle while
still detecting deleted manifest source files and ordinary local source-tree
changes.

## Non-Goals

This does not:

- change Hippo output generation;
- classify docs paths as source outside bundle validation;
- alter code-review concern schema, detector thresholds, ranking, discovery
  lane behavior, payload guard, or fix-advice behavior;
- make static full review equivalent to full Hippo/LLM-backed analysis;
- add patch, apply, pass, fail, block, verdict, or must-fix semantics.

## Consequences

- Fresh Hippo bundles that intentionally include docs-side source files no
  longer degrade to static full review only because Architec's local source
  classifier disagrees.
- Full review can proceed through the normal Hippo/LLM-backed path for
  repositories such as `packaging` and `itsdangerous`.
- Bundle validation remains conservative: if a manifest-declared source path is
  removed, stale detection still reports it.
