# Cleanup Subpackage API Retire

Date: 2026-05-12

## Context

The legacy CLI entries `archi cleanup` and `archi autofix` have been soft-cut. Their live replacements are advisory outputs:

- cleanup and archive observations are emitted from `archi code-review --full .`.
- repair direction is emitted from `archi fix-advice --for <review.json>`.

The remaining cleanup subpackage wrapper exports, `architec.cleanup.run_cleanup` and `architec.cleanup.run_autofix`, duplicate retired CLI workflows and keep standalone cleanup/autofix semantics visible as public API.

## Decision

Retire the cleanup subpackage wrapper public APIs:

- remove `architec.cleanup.run_cleanup` from package exports;
- remove `architec.cleanup.run_autofix` from package exports;
- remove the wrapper implementations that only exist to run retired standalone workflows.

This decision does not include:

- `run_gate` or `run_baseline`, which remain root package public APIs until a separate decision;
- lower-level cleanup inventory, archive, semantic judge, autofix plan, artifact, and report helpers;
- advisory commands such as `code-review`, `fix-advice`, `plan-review`, or `status`.

## Test Strategy

Wrapper-level public tests should move to lower-level helper coverage or code-review signal coverage. The auto-apply wrapper test should not keep the wrapper alive; if lower-level move behavior remains valuable, test `apply_autofix_plan` directly.

CLI soft-cut tests remain in place. They protect that legacy commands parse retained arguments, return exit code `2`, leave stdout empty, and do not trigger auth, bundle, LLM, or runtime work.

## Consequences

- This is a cleanup subpackage API breaking change, but not a root package breaking change.
- Existing CLI behavior is unchanged because the CLI already soft-cuts `cleanup` and `autofix`.
- `run_gate` and `run_baseline` remain retained compatibility APIs for now. Decision 015 later retires them.
- Cleanup/archive evidence continues through `code-review --full` signals and file-level concerns.
