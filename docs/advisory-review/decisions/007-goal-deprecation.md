# Goal Deprecation Path

Date: 2026-05-12

## Context

`goal` was originally exposed as a planning-oriented entry point. The advisory-only product direction removes planning responsibility from `architec`: users or coding agents provide a plan, and `architec` reviews it through `plan-review`.

After the top-level full/diff routes move to `code-review`, `archi --goal ...` remains the main public path that still produces planning-era analysis. Removing it in one step would be a larger breaking change, so the retirement should be staged.

## Decision

Retire `--goal` in two implementation steps:

1. Mark `--goal` as deprecated in help text and emit a stderr warning when it is used, while keeping behavior unchanged.
2. In the next breaking step, keep the `--goal` argument visible but reject it with exit code 2 and a clear migration message pointing to `archi plan-review <plan.md>`.

The deprecation warning should point users to `archi plan-review <plan.md>`.

The second step uses a soft cut rather than removing the argparse option immediately. This keeps the migration message explicit instead of falling back to a generic "unrecognized arguments" parser error.

## Consequences

- Existing `--goal` users get an explicit migration signal before removal.
- The current implementation can keep using the legacy analysis path during the warning period.
- The breaking step remains user-readable: `--goal` will fail with a targeted message before the parser option is eventually removed.
- The public product direction remains clear: planning moves out of `architec`, and plan review becomes the replacement workflow.
