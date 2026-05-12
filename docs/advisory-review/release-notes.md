# Advisory Review Migration Notes

Date: 2026-05-12

## Summary

`architec` is moving the public CLI toward advisory-only review commands. It reviews plans and code, but does not plan work for the user, act as a gate, or automatically repair code.

## Top-Level Routing

The top-level full and diff commands now route through the code-review layer:

```bash
archi .
archi --diff .
```

These remain supported aliases, but their underlying result is now a CodeReviewResult:

- `archi .` maps to `archi code-review --full .`.
- `archi --diff .` maps to `archi code-review --diff .`.
- `archi --diff --base <base> --head <head> .` maps to diff code review with that range.

The human stdout summary still uses the existing top-level summary printer, so it may be shorter than the previous analysis summary.

## Output Shape Change

For top-level full and diff commands, `--out <path>` now writes CodeReviewResult JSON instead of the legacy analysis result shape.

The CodeReviewResult shape includes:

```json
{
  "mode": "code_review",
  "review_type": "full|diff|since",
  "scores": {},
  "summary": {},
  "findings": [],
  "signals": [],
  "evidence": [],
  "concerns": [],
  "artifacts": {}
}
```

Consumers that previously parsed legacy fields such as `meta`, `recommendations`, `cleanup`, `archive_candidates`, `change_analysis`, or `feature_analysis` from top-level `--out` should migrate to `concerns`, `signals`, `evidence`, and `artifacts`.

## Goal Parser Removal

The public `--goal` entry point has been removed from the parser:

```bash
archi --goal "..." .
```

It is no longer accepted by the CLI. Use a plan Markdown file instead:

```bash
archi plan-review <plan.md>
```

## Legacy Parser Removal

Legacy maintenance command parsers have been removed after the soft-cut migration period:

`archi cleanup` is no longer a supported command parser. Use `archi code-review --full .` and read cleanup/archive signals from CodeReviewResult.

`archi autofix` is no longer a supported command parser, including dry-run and `--apply` forms. Use `archi fix-advice --for <review.json>`.

`archi gate` is no longer a supported command parser. Use advisory `archi code-review --diff .` output; it is not a merge decision.

`archi baseline` is no longer a supported command parser. Use `archi status --snapshot`.

## Legacy Public API Migration

The cleanup subpackage wrapper APIs have been retired:

- `architec.cleanup.run_cleanup`
- `architec.cleanup.run_autofix`

Use `archi code-review --full .` for cleanup/archive advisory signals and `archi fix-advice --for <review.json>` for repair guidance. Lower-level cleanup inventory, archive, semantic judge, autofix plan, and artifact helpers remain available for internal compatibility.

The root legacy public APIs have also been retired:

- `architec.run_gate`
- `architec.run_baseline`
- `architec.gate.run_gate`
- `architec.baseline.run_baseline`

Use advisory `archi code-review --diff . --out review.json` instead of gate wrappers, and `archi status --snapshot` instead of baseline wrappers.

## CI Migration

For CI jobs that previously used legacy gate output, write advisory diff review JSON instead:

```bash
# old
archi gate --out gate.json .

# new
archi code-review --diff --out review.json .
```

The new JSON is advisory review output for humans or agents. It should not be treated as a merge decision.

For jobs that previously used standalone cleanup output, write full advisory review JSON and read cleanup/archive signals from the review result:

```bash
# old
archi cleanup --out cleanup.json .

# new
archi code-review --full --out review.json .
```

For CI jobs that previously captured a legacy baseline artifact, write an advisory status snapshot instead:

```bash
# old
archi baseline --out baseline.json .

# new
archi status --snapshot --out status.json .
```

## New Public Entrypoints

Use these advisory commands directly when possible:

```bash
archi plan-review <plan.md>
archi code-review --full .
archi code-review --diff .
archi code-review --since <ref> .
archi fix-advice --for <review.json>
```

`plan-review` reads a Markdown plan and reports understood intent, changed areas, dependencies, concerns, suggested adjustments, and a plan fingerprint.

`code-review` reviews current code structure in full, diff, or since-ref mode. It is advisory-only and does not emit merge decisions.

Successful code-review runs append a compact ReviewEvent to `.architec/review-events.jsonl`. The event stream is local generated data by default and rotates at 10MB into month-named JSONL files.

`archi status --trend` and `archi status --snapshot` are advisory project-health modes. Existing `archi status` and `archi status --json` remain auth/session status commands.

`fix-advice` reads a saved review JSON and returns independent repair-direction suggestions for its concerns. It does not output executable changes and does not provide an apply mode.

## Advisory-Only Boundary

The new review surface follows these boundaries:

- No planning: provide a plan to `plan-review`; `architec` reviews it.
- No gate: code review reports concerns and evidence, not merge decisions.
- No automatic repair: repair direction belongs in advisory output, not automatic patches.
