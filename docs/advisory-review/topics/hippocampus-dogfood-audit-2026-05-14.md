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
