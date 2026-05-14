# Shadow Implementation Role Taxonomy

Date: 2026-05-14

## Context

Hippocampus dogfood produced a dubious `shadow-implementation` concern between
`render_project_map` and `append_project_map`. Renderer and assembly/support
helpers can share mapper tokens and similar AST shape while intentionally
serving different roles.

The useful signal should remain available for cases such as parser helper versus
parser helper, policy helper versus policy helper, or same-role implementations
that appear to reimplement an existing capability without reuse. The detector
needs a negative taxonomy for obvious intentional split roles so those pairs do
not occupy high-confidence concern slots.

## Decision

Keep function/class `shadow_implementation` based on role overlap, AST
similarity, signature or class API similarity, name overlap, and no direct reuse
edge.

Add a negative role taxonomy for intentional split-role pairs:

- renderer/rendering roles versus assembler, append, support, budget, or context
  assembly helpers are noise when that split role is clear;
- parser helper versus parser helper remains eligible;
- same-role candidates remain eligible;
- negative taxonomy filtering suppresses only clear split-role conflicts and
  does not replace the existing role, AST, signature, API, and reuse-edge
  evidence checks.

The existing review contracts stay unchanged:

- full/diff/since scope semantics stay unchanged;
- `shadow-implementation` concern schema stays unchanged;
- `references[].role: "existing_implementation"` stays unchanged;
- `concern_id` generation stays fact-based and unchanged for emitted concerns;
- `fix-advice` behavior stays unchanged;
- file/module-level shadow public signal remains deferred.

## Non-Goals

This does not:

- add file-level public shadow concerns;
- change concern schema, reference roles, review events, status, or payload
  artifacts;
- change `fix-advice` output;
- change full/diff/since selected-scope semantics;
- change `concern_id` semantics;
- broaden `shadow_implementation` into a fuzzy semantic detector;
- declare renderer/assembler splits unimportant architecture concerns in
  general.

## Consequences

- Useful function/class shadow signals remain available for same-role and
  parser-helper pairs.
- Renderer versus assembler/support/budget/context split-role helpers are less
  likely to be reported as high-confidence shadow implementations.
- Scope hygiene, reference evidence, fix advice, and generated concern artifacts
  continue to work without schema migration.
- File/module-level shadow remains a separate deferred product decision.
