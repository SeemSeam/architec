# Hippocampus Dogfood Audit 2026-05-14

This note records a dogfood run of the current advisory-review workflow against `/home/bfly/workspace/hippocampus`. It is an Architec self-assessment and a product signal for Architec's own roadmap; it is not a Hippocampus audit and is not a request to modify Hippocampus.

## Commands

Run from `/home/bfly/workspace/hippocampus`:

```bash
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full . --out /tmp/hippocampus-code-review-full.json --skip-auth
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --diff . --out /tmp/hippocampus-code-review-diff.json --skip-auth
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec fix-advice --review /tmp/hippocampus-code-review-full.json
```

## Full Review Observations

The full review reported overall `88.33`, `summary.concern_total=43`, and `top_concern_total=5`. Signal kinds included cleanup, archive, semantic_judge, hotspot, topology, near_duplicate, and shadow_implementation.

Useful observations:

- `shadow-implementation`: `parse_json_block` in `src/hippocampus/tools/structure/structure_prompt_navigation.py` versus `_try_parse_json` in `src/hippocampus/llm/validators.py` looked plausibly actionable. Both appear to handle JSON-fence parsing; the advice could lead to a shared utility or an explicit contract difference.
- `duplication`: `_print_quiet_footer` versus `_echo_unless_quiet` looked low severity but reasonable. A shared CLI quiet-output helper may reduce small drift.
- `cleanup`: `tree_sitter_compat.py` looked like a reasonable retention/ownership observation, though not necessarily a code-review fix.

Weak or noisy observations:

- `duplication`: `build_tree` versus `extract_signatures` in `src/hippocampus/api/__init__.py` looked low value. Thin public API wrappers naturally share wrapper shape while routing to different domain functions. This Architec detector precision example is now covered by [decision 042](../decisions/042-near-duplicate-thin-wrapper-suppression.md): different-target thin wrapper/facade boilerplate is suppressed.
- `shadow-implementation`: `render_project_map` versus `append_project_map` looked dubious. Renderer and budget assembly helpers can share mapper tokens and AST shape while serving different roles. This Architec detector precision example is now covered by [decision 043](../decisions/043-shadow-implementation-role-taxonomy.md): clear renderer versus assembler/support/budget/context split-role pairs are suppressed while same-role and parser-helper candidates remain eligible.

## Diff Review Observations

The current Hippocampus changed files were:

- `tests/test_llm_transport.py`
- `tests/test_prompt_propagation.py`
- `opencode.json`

The diff review reported overall `89.95` and `concern_total=22`. `near_duplicate` and `shadow_implementation` were absent, which is the desired conservative behavior for scoped AI signals.

The top diff concerns, however, were global cleanup, hotspot, and topology observations unrelated to the changed files, including `tree_sitter_compat.py`, `docs/plans/fangan/repomix-structure-plan.md`, `cli/__init__.py`, `pipeline_command_builders.py`, and `architecture_rules.py`.

This weakens trust in incremental review. A diff review should still be allowed to show project-level context, but changed-file-scoped observations should dominate the displayed top concern portfolio. Global context should be labelled or separated so it does not look like a claim about the selected diff.

## Product Lessons

- Full review can surface useful duplicate and shadow implementation advice. Near-duplicate thin wrapper suppression is now covered by [decision 042](../decisions/042-near-duplicate-thin-wrapper-suppression.md); shadow role taxonomy precision is now covered by [decision 043](../decisions/043-shadow-implementation-role-taxonomy.md).
- Diff/since review scope hygiene is now covered by [decision 041](../decisions/041-diff-since-scope-hygiene.md). The top concern portfolio should not be occupied by unrelated global cleanup, hotspot, or topology concerns.
- Architecture contracts and plan/diff consistency are important, but they do not replace code-level duplicate and shadow signals. They cover declared intent and boundaries; duplicate/shadow detectors cover implementation drift and repeated wheel-building.
- Architec does not guarantee mainline correctness. It provides advisory feedback for drift, duplication, boundary adherence, risk context, and trend signals. Tests and project process remain responsible for behavior correctness.

## Follow-Up Priorities

1. Diff/since review scope hygiene:
   - covered by [decision 041](../decisions/041-diff-since-scope-hygiene.md);
   - changed-file-scoped concerns are separated from global context observations.
2. Near-duplicate precision:
   - covered by [decision 042](../decisions/042-near-duplicate-thin-wrapper-suppression.md);
   - different-target thin wrapper/facade boilerplate is suppressed while substantive duplicate logic remains reportable.
3. Shadow role taxonomy:
   - covered by [decision 043](../decisions/043-shadow-implementation-role-taxonomy.md);
   - clear renderer versus assembler/support/budget/context split roles are suppressed;
   - parser-helper and same-role candidates remain eligible.

## Re-Run After Decisions 041-047

To avoid writing generated `.architec/` artifacts into the Hippocampus working
tree, the follow-up dogfood run copied `/home/bfly/workspace/hippocampus` to
`/tmp/hippocampus-archi-dogfood` and ran Architec against the copy.

Commands:

```bash
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --full /tmp/hippocampus-archi-dogfood --out /tmp/hippocampus-archi-full-20260514.json --skip-auth
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec code-review --diff /tmp/hippocampus-archi-dogfood --out /tmp/hippocampus-archi-diff-20260514.json --skip-auth
PYTHONPATH=/home/bfly/workspace/architec/src python3 -m architec fix-advice --review /tmp/hippocampus-archi-full-20260514.json --out /tmp/hippocampus-fix-advice-20260514.json
```

Diff review result:

- `summary.headline`: `No new architecture concerns were identified in the selected diff.`
- `summary.concern_total=22`, `top_concern_total=0`.
- `scoped_concern_total=0`, `global_context_concern_total=22`.
- `displayed_scoped_concern_total=0`, `displayed_global_context_concern_total=0`.
- Signals still exposed cleanup/archive/semantic/hotspot/topology context, but
  top-level `concerns[]` and `evidence[]` stayed empty for the selected diff.

This confirms the Decision 041 scope hygiene fix: unrelated full-project
cleanup/hotspot/topology context no longer occupies incremental top concerns.
The `concern_total=22` versus `top_concern_total=0` split is acceptable because
summary now distinguishes selected-scope and global-context counts.

Full review result:

- overall score `88.31`.
- `summary.concern_total=40`, `top_concern_total=5`.
- Signals included cleanup, archive, semantic_judge, hotspot, topology,
  near_duplicate, and shadow_implementation.
- `near_duplicate` produced 16 concerns and `shadow_implementation` produced 2
  concerns.

Useful observations that remain credible:

- `shadow-implementation`: `parse_json_block` versus `_try_parse_json` remains
  a useful parser-helper drift signal.
- `duplication`: `_print_quiet_footer` versus `_echo_unless_quiet` remains a
  small but plausible helper consolidation signal.
- `cleanup`: `tree_sitter_compat.py` remains a reasonable ownership/retention
  question, not a direct code-change request.

Weak observations that should drive Architec roadmap refinement:

- `shadow-implementation`: `_module_color_map` versus `module_rename_map`
  looks like a role-taxonomy miss. Both are "mapper" functions, but one maps
  module roles/tiers to visualization colors while the other maps old module
  ids to new module ids. The current mapper role is too broad for this case.
  This is now captured by [decision 050](../decisions/050-shadow-mapper-taxonomy.md):
  visualization color/palette/style/tier/role mappers should be distinguished
  from rename/move/old/new/diff migration mappers while same-domain mapper pairs
  remain eligible.
- `near_duplicate`: phase-specific prompt builders and cache helpers
  (`build_phase_*_messages`, `save_phase*_cache`, `load_phase*_cache`) produce
  many exact normalized AST matches. These are often intentional variant
  families rather than independent wheel-building. They may still be useful as
  architecture context, but they should not flood top concerns as individual
  repeated findings. This is now captured by [decision 048](../decisions/048-near-duplicate-variant-family-grouping.md):
  same-file phase/cache/prompt-builder families should be grouped or
  display-limited while cross-file and substantive non-family duplicates remain
  reportable.
- `duplication`: `legacy_project_prompts_dir` versus `project_prompts_dir`
  highlights a compatibility-path variant. The advice should recognize legacy
  or compatibility intent instead of only suggesting direct reuse. This is now
  captured by [decision 051](../decisions/051-duplication-fix-advice-compat-intent.md):
  duplication fix-advice treats explicit legacy/compat evidence as a first-class
  option to document compatibility intent.

Follow-up plan adjustments:

1. Implement the [decision 048](../decisions/048-near-duplicate-variant-family-grouping.md)
   near-duplicate variant-family grouping/display-limit behavior for same-file
   phase/cache/prompt-builder families.
2. Re-run dogfood after the [decision 050](../decisions/050-shadow-mapper-taxonomy.md)
   mapper taxonomy split lands, confirming color/palette/style/tier/role mapping
   and rename/move/old/new/diff migration mapping no longer look like the same
   implementation role.
3. The duplication compatibility wording follow-up is covered by
   [decision 051](../decisions/051-duplication-fix-advice-compat-intent.md).
