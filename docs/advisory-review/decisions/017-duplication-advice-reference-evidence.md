# Duplication Advice Reference Evidence

Date: 2026-05-13

## Context

`near_duplicate` v1 now reports Python function/method duplicates in full code review. The first implementation exposed the reference implementation only as an evidence string such as `near_duplicate.reference=path:line:symbol`.

That was enough for human reading, but it made `fix-advice` either ignore duplication concerns or infer the reference location from a string. Advisory repair suggestions need stable structured context without turning the review into an automatic merge or patch workflow.

## Decision

Add optional structured reference locations to duplication concerns.

For `kind: "duplication"` concerns, `code-review --full` may include:

```json
{
  "references": [
    {
      "role": "reference",
      "path": "src/a.py",
      "line": 10,
      "symbol": "first",
      "symbol_kind": "function"
    }
  ]
}
```

The duplicate implementation remains the primary `location`. The reference implementation is carried in `references[]`. Existing `evidence[]` strings remain for compatibility.

`fix-advice` uses structured references when available. For duplication concerns it gives advisory options such as:

- compare duplicate and reference behavior;
- consider reuse or routing through the reference implementation when behavior is intentionally shared;
- document intentional divergence when both implementations should remain.

## Non-Goals

This does not:

- generate patch output;
- add an `apply` mode;
- decide which implementation is correct;
- promise a merge direction or execution order;
- expand `near_duplicate` beyond the existing Python AST v1 scope.

## Consequences

- Old concerns without `references[]` remain valid.
- `fix-advice` can produce duplication-specific suggestions without parsing strings in the normal path.
- String parsing stays as a compatibility fallback for older reviews.
- Agents can cite both duplicate and reference locations directly from structured fields.
