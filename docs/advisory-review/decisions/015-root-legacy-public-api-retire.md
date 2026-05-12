# Root Legacy Public API Retire

Date: 2026-05-12

## Context

The legacy CLI commands `archi gate` and `archi baseline` have already been soft-cut to migration errors. The cleanup subpackage wrapper APIs were retired in decision 014. The remaining legacy public API surface is now:

- root exports `architec.run_gate` and `architec.run_baseline`;
- subpackage wrapper exports `architec.gate.run_gate` and `architec.baseline.run_baseline`.

These wrappers preserve old gate and baseline workflows even though advisory-review no longer offers merge decisions or legacy baseline capture as live CLI workflows.

## Decision

Retire the root legacy public APIs and their wrapper exports:

- remove `architec.run_gate` and `architec.run_baseline` from the root package `__all__` and lazy `__getattr__`;
- remove `architec.gate.run_gate` and `architec.baseline.run_baseline` from subpackage exports;
- delete wrapper modules that only exist to call `run_analysis` and write legacy gate/baseline workflow artifacts.

This is a root public API breaking change.

## Migration

- Gate users should run `archi code-review --diff . --out review.json` and consume the advisory review output. This output is not a merge decision.
- Baseline users should run `archi status --snapshot` to capture advisory project status.

## Non-Goals

This decision does not remove or change:

- `run_analysis`;
- advisory commands or their JSON contracts;
- `status`, `code-review`, `fix-advice`, or `plan-review`;
- lower-level baseline and gate report helpers that remain useful for historical artifact parsing, rendering, or compatibility tests.

## Consequences

- CLI behavior is unchanged because `archi gate` and `archi baseline` already return exit code `2` with migration guidance.
- Direct Python callers of `architec.run_gate`, `architec.run_baseline`, `architec.gate.run_gate`, or `architec.baseline.run_baseline` must migrate.
- Wrapper-level tests move to lower-level report/value tests.
- Historical baseline and gate artifact helpers remain available, but no public wrapper API runs the old workflows end to end.
