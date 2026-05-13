---
name: archi-goal
description: Review a concrete architecture objective by converting it to a plan and running archi plan-review. The legacy archi --goal flag has been removed; do not use it.
---

# archi-goal

Legacy note: `archi --goal` has been removed from the CLI parser. When the user has a concrete architectural objective, write or ask for a short Markdown plan and run `archi plan-review <plan.md>`.

## Trigger

- "Where should this feature go?"
- "How should this be refactored?"
- "How do we stabilize this boundary?"
- "What architecture changes support this goal?"

## Command

```bash
archi plan-review <plan.md>
```

The plan should include intent, expected changes, and dependencies when known.

Pair with code review when broader implementation context matters:

```bash
archi code-review --full .
archi code-review --diff .
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Focus on:

- `understood_plan`
- `concerns`
- `suggested_adjustments`
- `plan_fingerprint`

## Output Rule

- Restate the goal in architecture terms.
- Summarize the understood intent, change areas, and dependencies.
- Highlight likely boundary risks and placement advice.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use removed `archi --goal`.
- Do not treat plan-review as a full structural baseline; pair with `archi-full` or `archi code-review --full .` when broader architecture context matters.

## Example Prompts

- "Where should this new feature go architecturally?"
- "Use a plan for 'stabilize service boundaries' and tell me the best placement."
- "Analyze this refactor plan and identify the right target components."

## Standard Output Template

Use this response shape:

```text
Goal
- restated goal: <goal in architecture terms>

Recommended Placement
- <target component or area 1>
- <target component or area 2>

Risks
- <boundary or coupling risk 1>
- <boundary or coupling risk 2>

Next Moves
- <recommended action 1>
- <recommended action 2>
```
