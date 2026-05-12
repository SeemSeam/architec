# Legacy Public API Retention

Date: 2026-05-12

## Context

The public CLI entries `archi cleanup`, `archi autofix`, `archi gate`, and `archi baseline` have been soft-cut as part of the advisory-only migration. Their underlying functions still exist:

- `run_cleanup` is exported from `architec.cleanup`.
- `run_autofix` is exported from `architec.cleanup`.
- `run_gate` is exported from `architec.gate` and the root `architec` package.
- `run_baseline` is exported from `architec.baseline` and the root `architec` package.

Agent4's read-only scan found no remaining non-CLI business-code callers in `src/`, but tests and docs still treat these functions as executable public capabilities. `run_cleanup` and `run_autofix` are cleanup subpackage legacy compatibility APIs; `run_gate` and `run_baseline` are root package public APIs.

## Decision

At the CLI soft-cut phase, keep the underlying legacy public APIs. Do not delete `run_cleanup`, `run_autofix`, `run_gate`, or `run_baseline` in the same phase as CLI soft-cut.

Treat them as legacy compatibility APIs until a separate public API retirement decision is made. The next work should update user-facing docs so live CLI usage matches current behavior, while historical docs can remain if clearly marked as historical.

Decision 014 is the first follow-up retirement decision and narrows the retained set by retiring only the cleanup subpackage wrapper APIs. Decision 015 completes the wrapper retirement by removing the root gate/baseline legacy public APIs.

## Consequences

- CLI behavior is advisory-only and no longer exposes standalone cleanup, auto-apply, gate, or baseline workflows.
- Existing direct Python callers are not broken immediately by CLI soft-cut.
- Tests that directly exercise legacy public APIs can remain until a later API-retirement step.
- Any future deletion must be split into separate steps: docs, tests, exports, then implementation removal.
