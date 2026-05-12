# Near Duplicate V1 Scope

Date: 2026-05-12

## Context

`near_duplicate` is the first AI/vibe-coding-specific signal planned for code-review. The risk is false positives: broad similarity matching can quickly create noisy advice, and advisory-only output only stays useful if evidence is concrete.

## Decision

Implement `near_duplicate` v1 as a conservative Python-only full-review signal:

- Detect duplicated Python functions and methods by normalized AST fingerprints.
- Normalize identifiers and literal values, but keep structure and operation shape.
- Ignore very small functions to avoid boilerplate noise.
- Emit `duplication` concerns with file, line, symbol, reference symbol, and fingerprint evidence.
- Emit a `near_duplicate` signal summary when duplicate concerns are present.
- Only enable this in `code-review --full` initially.
- Do not enable it in `--diff` / `--since` until changed-file scoping is available, because increment modes must not report historical duplicate debt.

## Consequences

- The first version prioritizes high-confidence evidence over recall.
- Shadow implementation and fuzzy similarity remain future work.
- The signal can immediately help full-project review find AI-style "new function instead of reuse" drift without turning code-review into a broad style linter.
