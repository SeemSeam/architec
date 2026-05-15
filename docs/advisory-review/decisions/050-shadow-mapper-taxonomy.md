# Shadow Mapper Taxonomy

Date: 2026-05-14

## Context

The Hippocampus dogfood follow-up showed a weak `shadow-implementation`
candidate between `_module_color_map` and `module_rename_map`. Both functions
look like mappers at the coarse role-token level, but they serve different
mapping domains:

- `_module_color_map` maps module roles, tiers, or visualization state to color,
  palette, style, or display values.
- `module_rename_map` maps old module names to new module names for rename,
  move, diff, or migration workflows.

Decision 043 added negative taxonomy for broad renderer versus assembler/support
split roles. Mapper needs a narrower conservative subdomain split so unrelated
mapping responsibilities do not look like high-confidence shadow
implementations.

## Decision

Keep `shadow_implementation` function/class detection based on the current role,
AST, signature/class API, name-overlap, and no-reuse-edge evidence. Keep the
current concern schema and thresholds.

Add mapper subdomain suppression v1:

- when both candidates share the coarse `mapper` role, suppress clear
  visualization mapper versus migration/rename mapper pairs;
- visualization mapper tokens include color, palette, style, tier, role,
  rendering, visual, display, and theme-oriented mapping terms;
- migration/rename mapper tokens include rename, move, old, new, diff, migration,
  migrate, source, target, from, to, alias, and compatibility-oriented mapping
  terms;
- same-domain mapper pairs remain eligible;
- mapper pairs with ambiguous or mixed domain evidence remain eligible rather
  than being suppressed;
- parser-helper pairs remain eligible;
- same-role non-mapper candidates remain eligible;
- diff/since scope semantics remain unchanged.

This is a precision filter only. It should run before public concern emission
and should not change the shape of concerns that remain reportable.

## Non-Goals

This does not:

- change the `shadow-implementation` concern schema;
- change detection thresholds;
- change `references[].role: "existing_implementation"`;
- change `concern_id` semantics for emitted concerns;
- change diff/since selected changed-file scope;
- promote file/module-level shadow implementation to a public signal;
- change `fix-advice` schema or behavior;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Color/palette/style/tier/role visualization mappers are less likely to be
  conflated with rename/move/old/new/diff migration mappers.
- Useful same-domain mapper shadow signals remain reportable.
- Existing parser-helper and same-role shadow signals remain available.
- Existing consumers continue to read the same concern shape and reference role.
- File/module-level shadow remains a separate deferred product decision.
