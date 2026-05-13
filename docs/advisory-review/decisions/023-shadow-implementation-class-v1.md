# Shadow Implementation Class V1

Date: 2026-05-13

## Context

Decision 022 introduced function-level `shadow_implementation` detection for full code review. The next high-value extension is class-level detection, because AI-assisted changes often recreate service, policy, parser, or reporter classes with similar public methods instead of reusing an existing implementation.

Class-level matching has higher ambiguity than function matching. V1 should stay conservative and rely on concrete static facts.

## Decision

Extend `shadow_implementation` v1 to include Python class candidates:

- Keep the same concern kind: `shadow-implementation`.
- Enable class detection only in `code-review --full`.
- Do not use LLMs.
- Require cross-file class pairs; same-file candidates are out of scope.
- Keep file-level detection, diff/since range control, and fix-advice special handling out of this step.
- Exclude tests, fixtures, generated code, vendor code, build artifacts, virtual environments, and local generated architec data.
- Exclude adapter, wrapper, facade, compat, shim, bridge, proxy, and delegation-shaped names.
- Exclude exact normalized AST duplicates so exact structural duplication remains separate from shadow implementation.
- Require class total node count at least 90.
- Require shared role tokens, name token overlap, API/member shape similarity, AST feature similarity, and no direct call/import/attribute reuse edge.
- Emit `references[]` with `role: "existing_implementation"` for the existing class.
- Mark class concerns with `location.symbol_kind: "class"`.
- Include class-specific facts such as `shadow_implementation.scope=class`, `api_similarity`, `member_counts`, `ast_similarity`, `reuse_edge=false`, and `node_counts`.
- Keep stable ids in the `code-review:shadow-implementation:<hash>` form, with the hash input including symbol kind and class facts.

## Consequences

- Full code review can now surface both function-level and class-level shadow implementation concerns.
- The signal summary can break down candidates by symbol kind while keeping the existing `{kind, summary, metrics}` signal contract.
- V1 may miss valid classes with renamed APIs or indirect reuse. That is acceptable for this precision-first step.
- `fix-advice` continues to use generic fallback for this concern kind until a separate advisory-options decision.
