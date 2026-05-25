# Command Surface Documentation Cleanup

Date: 2026-05-24

## Context

Decision 068 changed the public command model to two common entry points:
`archi` for incremental LLM review and `archi --full` for full-project LLM
review. Some README and command notes still described historical aliases such
as `archi .` as the default full review path and `archi --diff .` as the main
diff workflow.

That mixed language makes the cost model harder to understand.

## Decision

User-facing documentation should teach the simple model first:

- `archi` runs incremental selected-change LLM architecture review.
- `archi --full` runs full-project LLM architecture review.

Historical top-level aliases such as `archi .` and `archi --diff .` may remain
documented only as compatibility or migration notes. Advanced `code-review`
subcommands may remain documented for explicit diff/since ranges, saved
plan-review JSON, risk context, and debugging.

## Consequences

The public workflow no longer asks users to choose from a budget matrix. It also
keeps the intended default cost profile visible: incremental first, full review
only when requested.

## Non-Goals

- Remove compatibility aliases in this decision.
- Remove advanced `code-review` subcommands.
- Change review semantics, result schema, or LLM usage.
- Add gate, verdict, automatic repair, patch, or apply semantics.
