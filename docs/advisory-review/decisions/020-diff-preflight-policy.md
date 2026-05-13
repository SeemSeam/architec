# Diff Preflight Policy

Date: 2026-05-13

## Context

`code-review --diff` and top-level `archi --diff .` are meant to be lightweight advisory feedback loops. Earlier routing reused an extra weak LLM preflight check for `architect_component_scoring`, which made diff review depend on a task that is optional for the current advisory output path.

The full/check paths still need the base LLM health checks used by the advisory review surface.

## Decision

Use the same base preflight checks for full, diff, and since code-review:

- `architect_history` strong
- `architec_summary` strong
- `architect_folder_naming` weak
- `architect_topology_review` weak

Do not add `architect_component_scoring` as a required diff/since preflight check for advisory code-review.

This changes only CLI preflight gating. The underlying analysis code can still call component scoring when it needs incremental score data; that runtime behavior remains guarded by the normal analysis path and tests.

## Consequences

- `archi --diff .` and `archi code-review --diff .` start with fewer required LLM task checks.
- `archi code-review --since <ref> .` follows the same lightweight preflight policy.
- `archi --check .` still validates the base advisory-review LLM configuration.
- Future component-scoring LLM improvements can remain optional unless a later decision promotes them back into required preflight.
