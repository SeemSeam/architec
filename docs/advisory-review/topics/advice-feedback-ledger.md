# Advice Feedback Ledger

Architec supports the first step of a project-local feedback loop for advice
quality. Reviewers can provide an explicit feedback JSON file that marks advice
as accepted, rejected, deferred, superseded, or not applicable, then Architec
uses that feedback to reduce repeated wrong recommendations in later runs.

See [Decision 067](../decisions/067-advice-feedback-ledger.md).

## Problem

Advisory output can be broader than gate-style output because another review
step happens before changes land. That is useful for recall, but it creates a
different product problem: if a suggestion is reviewed and judged wrong for the
project, the next run should not present the same claim as if it were new.

Examples:

- a cleanup suggestion says a fallback module is obsolete, but maintainers mark
  it as active runtime behavior;
- a docs recommendation says a changelog is stale, but semantic review or human
  feedback says it is active surface;
- a duplication suggestion says two paths should share implementation, but the
  reviewer records an intentional compatibility split;
- a topology recommendation is technically true but repeatedly low value for a
  small mature library.

## Ledger Shape

The v1 ledger is read from `--advice-feedback <json>` for full review and
`fix-advice`. It is small and explicit:

```json
{
  "items": [
    {
      "advice_id": "archi-advice:cleanup:watch_fallback.py:fallback_branch",
      "concern_id": "code-review:cleanup:...",
      "kind": "cleanup",
      "path": "lib/cli/services/watch_fallback.py",
      "symbol": "",
      "status": "rejected",
      "scope": "same_path_kind",
      "reason": "This is active runtime fallback behavior, not obsolete.",
      "decided_at": "2026-05-18"
    }
  ]
}
```

Expected statuses:

- `accepted`: reviewer confirmed the advice is useful.
- `rejected`: reviewer judged the advice incorrect.
- `not_applicable`: advice may be generally valid but not relevant here.
- `deferred`: keep visible, but do not over-prioritize now.
- `superseded`: another decision or plan replaced this advice.

Expected scopes:

- `exact_advice`: affects only the same `advice_id` or `concern_id`.
- `same_path_kind`: affects future advice for the same path and kind.
- `pattern`: affects a named repeated pattern, such as active changelog or
  compatibility wrapper advice.

## Consumption Rules

The v1 implementation is conservative:

- read feedback after concerns and recommendations are generated;
- keep raw generated concerns and artifacts intact;
- suppress or demote only full-review recommendations and `fix-advice`
  suggestions;
- require explicit ids or path/kind matches;
- never infer a broad pattern from free-form prose alone.

Suggested behavior:

- `rejected` exact advice: hide from default recommendations unless new
  evidence is present.
- `not_applicable` same-path/kind advice: demote to artifact context.
- `deferred` advice: keep visible but lower priority.
- `accepted` advice: may reinforce similar advice when the same facts recur.
- `superseded` advice: point to the superseding plan or decision when present.

## Implementation Status

Implemented in v1:

- `archi --advice-feedback <json> .` and
  `archi code-review --full --advice-feedback <json> .` pass feedback into
  normal full-review recommendations.
- `archi fix-advice --review <review.json> --advice-feedback <json>` demotes
  matching suggestions.
- Raw generated concerns and complete artifacts remain intact.

Static fallback review remains deterministic and does not synthesize full
human-readable recommendations from feedback.

Later versions can add a helper command that writes `.architec/advice-feedback.json`
and can extend feedback effects to topology, discovery promotion, risk-context
reinforcement, and status trend summaries.

## Testing

Useful tests:

- a rejected exact advice item does not reappear in top recommendations;
- a rejected same-path/kind item remains in complete artifacts but is demoted
  from display;
- new semantic or risk evidence can reintroduce a previously rejected item with
  an explicit explanation;
- invalid ledger JSON returns a clear input error rather than silently changing
  advice;
- forbidden gate/verdict/pass/fail/block/must-fix/patch/apply terms remain
  absent from generated advice.
