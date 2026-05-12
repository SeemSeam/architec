# Legacy Command Migration Sequence

Date: 2026-05-12

## Context

The advisory-review product model keeps four public directions: `plan-review`, `code-review`, `fix-advice`, and `status`. Older commands still exist in the CLI: `cleanup`, `autofix`, `baseline`, and `gate`.

Removing them all at once would make migration noisy, but keeping them indefinitely would keep planning-era, gate-era, and auto-apply semantics visible in the product.

## Decision

Migrate legacy commands in staged order:

1. Protect the strongest product boundaries first.
   - `autofix --apply` should soft-cut to exit code 2, because advisory-review does not automatically modify code.
   - `gate` should emit a deprecation warning first, then soft-cut after one migration step, because advisory-review does not provide merge decisions.
2. Keep information-only legacy commands temporarily while their replacements are incomplete.
   - `cleanup` remains available with a deprecation warning until `code-review` signals cover the necessary cleanup/archive context.
   - `autofix` dry-run remains available with a deprecation warning until `fix-advice` exists.
   - `baseline` remains available with a deprecation warning until `status --snapshot` exists.
3. Do not remove parsers in the same step that first introduces warnings.
4. Each legacy command should follow the same ladder:
   - help text marks the command or flag as deprecated / removed.
   - runtime emits stderr migration guidance without polluting stdout.
   - soft-cut returns exit code 2 with a migration message.
   - parser removal happens only after the soft-cut step is stable.

## Consequences

- The most contradictory behavior (`autofix --apply`) is removed first.
- Existing users of read-only or report-only legacy commands get a clear migration signal before removal.
- `fix-advice` and `status` can be implemented before their legacy predecessors disappear.
- The codebase can repeat the tested `--goal` retirement pattern rather than inventing a new migration flow for each command.
