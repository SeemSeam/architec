# Plan Diff Semantic Intent Matching

Date: 2026-05-14

## Context

Plan/diff consistency already compares saved plan-review JSON with selected
diff/since files for paths, import expectations, dependency alternatives,
expected tests, and public API migration touchpoints. The remaining roadmap
question is whether a reviewed plan can carry a small amount of semantic intent
into incremental review without reintroducing goal-style planning or LLM/NLP
inference.

V1 should stay deterministic. It should only check explicit structured terms
that the saved plan-review JSON provides, and it should report observations
about selected changed files rather than proving requirement correctness.

## Decision

Add semantic intent checks to `plan-diff-consistency` v1 for incremental review.

`code-review --diff/--since --plan-review <plan.json>` may consume explicit
structured semantic intent checks from saved plan-review JSON:

- `understood_plan.intent_checks[]`;
- `understood_plan.semantic_intents[]`.

Only dict/object entries are requirements. String or prose intent notes remain
context and are not scanned as requirements.

Each structured check may define:

- a source or path scope that selects changed files within the selected
  diff/since range;
- required all terms, meaning every listed term must appear in the scoped
  changed text;
- required any terms, meaning at least one listed term must appear;
- forbidden terms, meaning listed terms should not appear in the scoped changed
  text.

The matching is deterministic text-term matching. It is not LLM or NLP
reasoning. The scanner does not read `understood_plan.intent`,
`changes[].intent`, or other natural-language prose to infer requirements.

If required terms are missing from the scoped selected changed text, emit an
advisory `kind: "plan-diff-consistency"` observation with
`plan_diff_consistency.observation=planned_intent_terms_not_observed`.

If forbidden terms are observed in the scoped selected changed text, emit an
advisory `kind: "plan-diff-consistency"` observation with
`plan_diff_consistency.observation=planned_intent_conflict_observed`.

If a source/path scope has no checkable selected changed text file in v1, do
not emit a missing concern. Metrics may still count the input check so callers
can see that the plan provided semantic intent checks.

Signal metrics should include:

- `semantic_intent_total`;
- `observed_semantic_intent_total`;
- `missing_semantic_intent_total`;
- `conflicting_semantic_intent_total`.

## Non-Goals

This does not:

- run in full review;
- load plan-review JSON or run the scanner for since bad-ref degraded results;
- infer requirements from `understood_plan.intent`, `changes[].intent`, or
  arbitrary prose;
- perform LLM/NLP semantic matching;
- prove that implementation intent is correct;
- prove tests are sufficient;
- guarantee mainline correctness;
- create a new concern kind;
- change concern id schema;
- change `fix-advice` behavior;
- add gate, verdict, pass, fail, block, must-fix, patch, or apply semantics.

## Consequences

- Reviewed plans can carry explicit term-level intent checks into incremental
  review.
- String/prose plan notes stay safe as context rather than hidden requirements.
- A scoped missing-file case is neutral in v1: it is visible in metrics but does
  not create a missing-intent concern without changed text to inspect.
- The check can catch simple implementation drift signals, but it remains an
  advisory observation and not proof of requirement satisfaction.
