# Shadow Implementation V1 Scope

Date: 2026-05-13

Superseded in part by [023-shadow-implementation-class-v1.md](023-shadow-implementation-class-v1.md) for class-level detection.

## Context

`near_duplicate` catches exact normalized AST repetition, but AI-assisted code can also produce a second implementation that is structurally and semantically close to an existing one without being an exact duplicate.

This signal has higher noise risk than `near_duplicate`. V1 needs to favor high precision, concrete evidence, and advisory language over broad fuzzy matching.

## Decision

Implement `shadow_implementation` v1 as a conservative Python-only full-review signal:

- Add a distinct concern kind: `shadow-implementation`.
- Detect function-level candidates only; class-level and file-level variants remain future work.
- Enable the detector only in `code-review --full`.
- Do not use LLMs for detection.
- Require cross-file evidence. Same-file nested helpers are out of scope.
- Exclude exact normalized AST duplicates so `near_duplicate` remains the owner for that case.
- Require a combined static evidence threshold:
  - function node count at least 45;
  - shared role tokens such as parser, report, mapper, status, cleanup, review, scoring, component, filter, selection, or policy;
  - name token overlap at least 0.45 after stopword removal;
  - signature similarity at least 0.6;
  - AST feature cosine similarity at least 0.82;
  - no direct call, import, or attribute reuse edge between the two functions;
  - final confidence at least 0.78.
- Emit `references[]` with `role: "existing_implementation"` for the existing implementation location.
- Emit factual evidence strings for overlap, signature similarity, AST similarity, role, reuse edge, and node counts.

V1 does not add a `fix-advice` special branch. Unknown-kind fallback remains acceptable until a separate decision defines shadow-specific repair guidance.

## Consequences

- `code-review --full` can now report AI-style "similar implementation without reuse" drift beyond exact AST duplication.
- Diff and since review remain scoped to their current concerns and do not surface historical shadow implementation debt.
- The signal may miss valid cases where names diverge heavily or where reuse is indirect; that is intentional for V1.
- The new reference role is additive and backward compatible with existing consumers that ignore unknown `references[].role` values.
