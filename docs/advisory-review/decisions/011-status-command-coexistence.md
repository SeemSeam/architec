# Status Command Coexistence

Date: 2026-05-12

## Context

`archi status --json` already exists as an auth/session status command used by install and production smoke flows. The advisory-review plan also names `archi status --trend` and `archi status --snapshot` as the long-term project health command.

Removing or renaming the auth status command would break existing automation, but delaying advisory status would block trend and snapshot work.

## Decision

Keep one `status` command name with explicit mode separation:

- `archi status --json` and bare `archi status` remain auth/session status for compatibility.
- `archi status --trend` is advisory project status trend.
- `archi status --snapshot` is advisory project status snapshot.
- `--trend` and `--snapshot` are mutually exclusive advisory modes.
- Advisory status routing should happen before auth command dispatch only when one of the advisory mode flags is present.
- Without an advisory mode flag, existing auth status behavior wins.

## Consequences

- Existing auth automation keeps working.
- Advisory status can ship without inventing another public keyword.
- Documentation must be explicit that `status --trend` / `status --snapshot` are project health modes, while `status --json` is auth/session state.
- Future parser removal or renaming should treat auth status and advisory status as separate compatibility surfaces.
