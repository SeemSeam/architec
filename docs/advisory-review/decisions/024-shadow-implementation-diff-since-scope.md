# Shadow Implementation Diff/Since Scope

Date: 2026-05-13

## Context

`shadow_implementation` now detects function-level and class-level candidates during full code review. Diff and since review previously skipped the signal to avoid surfacing historical project debt in incremental output.

The high-value incremental case is narrower: a changed file introduces an implementation that appears similar to an existing implementation without a direct reuse edge.

## Decision

Enable `shadow_implementation` in `code-review --diff` and `code-review --since <ref>` as a changed-file-scoped signal:

- Build a project-wide candidate index so changed implementations can be compared against unchanged existing implementations.
- Report only concerns whose primary `location.path` is in the changed-file set.
- Allow `references[]` to point at unchanged files.
- Do not use `references[].path in changed_files` as a reporting condition.
- In scoped mode, force the changed candidate to be the concern `location`; do not let path sorting place it in `references[]`.
- Read changed files from the analysis report `change_analysis.changed_files`; do not call git a second time from code-review.
- If a since range cannot be resolved, keep returning the structured degraded CodeReviewResult and do not run the detector.
- Add scoped signal metrics: `scoped_to_changed_files`, `changed_file_total`, and `candidate_total_before_scope`.
- Do not add file-level detection or `fix-advice` shadow-specific options in this step.

## Consequences

- Incremental review can surface "this changed file appears to reimplement an existing implementation" without reporting unchanged historical pairs.
- The detector still parses the project to build references, but pair evaluation is scoped to changed-file primary candidates.
- If the analysis report lacks changed-file paths, scoped shadow detection does not run for that review.
- Changes to only the existing/reference implementation may be missed by incremental review; those remain full-review concerns.
