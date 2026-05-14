# Near Duplicate Variant Family Grouping

Date: 2026-05-14

## Context

The Hippocampus dogfood follow-up after Decisions 041-047 showed that
diff/since scope hygiene is working, but full review can still over-represent
`near_duplicate` findings from intentional same-file variants. Phase-specific
prompt builders and cache helpers such as `build_phase_*_messages`,
`save_phase*_cache`, and `load_phase*_cache` can share an exact normalized AST
fingerprint while serving as parallel phase or cache variants.

These matches are not useless, but many individual concerns from one same-file
family can flood top concern slots and make the signal look more severe than it
is. This is a display and grouping precision issue, not a reason to weaken the
exact duplicate detector.

## Decision

Keep `near_duplicate` based on exact normalized AST fingerprint matches, and add
v1 grouping or display limiting for intentional same-file variant families.

In v1:

- exact normalized AST fingerprint matching remains the base detector;
- same-file intentional variant families may be grouped into one advisory
  duplication observation, or otherwise display-limited so one family does not
  occupy many top concern slots;
- target families include phase/cache/prompt-builder patterns observed in the
  Hippocampus dogfood run, especially `build_phase_*_messages`,
  `save_phase*_cache`, and `load_phase*_cache`-style naming;
- v1 variant tokens are intentionally narrow: explicit `phase`, `step`,
  `stage`, `part`, `v` markers and numeric suffixes such as `phase2`,
  `phase_2a`, or `cache3`;
- cross-file duplicates remain reportable;
- repeated substantive logic that is not confidently part of a variant family
  remains reportable;
- same-file duplicates with no clear phase/cache/prompt-builder family shape
  remain reportable;
- diff/since scope semantics remain unchanged: incremental concerns are still
  selected by primary `location.path`, and references may point at unchanged
  files;
- emitted duplication concerns keep the existing `kind: "duplication"` shape
  and `references[].role: "reference"` semantics;
- no `fix-advice` schema change is required unless implementation explicitly
  adds one later.

This should be conservative. If the detector cannot confidently identify a
same-file intentional variant family, it should leave the exact duplicate
reportable rather than hide substantive repeated logic.

## Non-Goals

This does not:

- add fuzzy duplicate detection;
- change normalized AST fingerprinting;
- change duplicate detector thresholds;
- suppress cross-file duplicates;
- suppress substantive same-file repeated logic outside clear variant families;
- change `near_duplicate` diff/since scope semantics;
- change `shadow_implementation` behavior;
- add a new concern kind;
- add dedicated `fix-advice` behavior or schema;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Full review top concerns should be less likely to be dominated by one
  same-file phase/cache/prompt-builder family.
- Exact duplicate evidence remains available for substantive duplicate logic.
- The dogfood-observed phase/cache/prompt-builder families become architecture
  context or a single grouped advisory observation rather than many independent
  top findings.
- Existing diff/since selected-scope behavior and advisory-only boundaries stay
  unchanged.
