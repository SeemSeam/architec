# Since Range Error Semantics

Date: 2026-05-13

## Context

`code-review --since <ref>` depends on a git range. If `<ref>` cannot be resolved, returning an empty diff is misleading because it makes an input problem look like a clean advisory observation.

Earlier public code handled recognizable `run_analysis` exceptions, but the lower git helper could swallow failed explicit ranges and fall back to the working tree.

## Decision

Treat explicit since range failures as structured advisory degradation:

- `code-review --since <ref>` calls analysis with `diff=True`, `base=<ref>`, `head="HEAD"`.
- If the explicit git range cannot be resolved, the public result is a CodeReviewResult skeleton with `review_type: "since"`, empty `concerns` and `findings`, and a summary explaining that the since range could not be analyzed.
- The command does not fall back to full review or to an unrelated working-tree diff.
- Known git range errors are caught; unrelated programming/runtime errors still propagate.

The git changed-files helper now raises `RuntimeError` for failed explicit `base...head` ranges and returns an empty list for valid explicit ranges with no changed files.

## Consequences

- Bad refs are visible to users and agents as input problems.
- Valid empty since ranges still produce the normal empty-concern since result.
- CLI output remains advisory-only and avoids gate-style wording.
- Future structured error schemas can extend `summary.reason` without changing the top-level CodeReviewResult contract.
