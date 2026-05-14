# Near Duplicate Thin Wrapper Suppression

Date: 2026-05-14

## Context

Hippocampus dogfood produced a weak `near_duplicate` concern between
`build_tree` and `extract_signatures` in `src/hippocampus/api/__init__.py`.
Those functions are thin public API wrappers. They share the same wrapper shape,
but they delegate to different domain functions, so the duplicate wrapper
structure is low-value evidence.

This is a detector precision issue, not a reason to abandon exact duplicate
detection. Exact normalized AST fingerprinting remains useful for repeated
substantive logic and should stay the base signal for `near_duplicate`.

## Decision

Keep `near_duplicate` v1 based on exact normalized AST fingerprint matches, but
suppress thin wrapper/facade/delegator pairs when they delegate to different
dominant call targets.

In v1:

- exact normalized AST fingerprint matching remains the base detector;
- repeated substantive logic remains reportable;
- thin wrapper, facade, and delegator pairs with different dominant call targets
  are treated as noise and do not produce public `duplication` concerns;
- wrappers delegating to the same dominant target may remain reportable, because
  they can indicate redundant aliases or compatibility surfaces worth review;
- suppression happens before top concern ranking so wrapper boilerplate does not
  occupy default top concern slots;
- full, diff, and since scope semantics remain unchanged;
- `concern_id` generation remains fact-based and unchanged for concerns that are
  still emitted;
- `fix-advice` behavior remains unchanged.

Dominant call target means the main callee that the wrapper forwards to. The
implementation should stay conservative: if the detector cannot confidently
identify wrapper shape and different delegation targets, it should leave the
pair reportable rather than suppress substantive duplicated logic.

## Non-Goals

This does not:

- add fuzzy similarity;
- change normalized AST fingerprinting;
- change node-size thresholds for substantive duplicate detection;
- change `near_duplicate` diff/since changed-file scope;
- change `shadow_implementation` behavior;
- change `concern_id` semantics;
- change `fix-advice`, review events, status, or payload artifact behavior;
- decide that all public API wrappers are unimportant.

## Consequences

- `near_duplicate` keeps a high-precision exact-duplicate base.
- Low-value public facade boilerplate is less likely to occupy top concern
  slots.
- Repeated real implementation logic remains visible.
- The wrapper/delegator classifier only suppresses obvious thin wrappers with
  different delegated targets.
