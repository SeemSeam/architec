# Legacy Parser Removal

Date: 2026-05-12

## Context

Legacy CLI commands have already gone through warning and soft-cut phases:

- `archi cleanup`
- `archi autofix`
- `archi baseline`
- `archi gate`

The planning-era `--goal` flag has also gone through deprecation and soft-cut. Their replacement workflows are now in place through `plan-review`, `code-review`, `fix-advice`, and `status`.

Keeping parser stubs after public APIs and wrapper workflows have been retired leaves dead CLI paths and migration-only helpers in the codebase.

## Decision

Remove the legacy parser stubs and final `--goal` flag:

- remove `cleanup`, `autofix`, `baseline`, and `gate` command-specific parsers and routing branches;
- remove the top-level `--goal` parser argument;
- remove command-level and flag-level soft-cut reject helpers;
- keep advisory commands and their output contracts unchanged.

Replacement workflows remain:

- cleanup/archive review: `archi code-review --full .`;
- repair direction: `archi fix-advice --for <review.json>`;
- advisory diff review: `archi code-review --diff . --out review.json`;
- status snapshot: `archi status --snapshot`;
- plan or intent review: `archi plan-review <plan.md>`.

## Non-Goals

This does not remove:

- `run_analysis`;
- lower-level cleanup, gate, baseline, archive, or report helper modules;
- current advisory commands;
- generated historical artifacts that may exist in user workspaces.

## Consequences

- Removed commands and `--goal` now fail through normal parser error behavior rather than targeted migration messages.
- CLI code no longer carries soft-cut routing branches for retired commands.
- User-facing live documentation should describe the commands as unavailable and point to replacement advisory workflows.
