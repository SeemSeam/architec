---
name: archi-advice
description: Produce advisory architecture guidance by combining code-review output with plan-review, diff context, and fix-advice. Do not use the removed archi --goal flag.
---

# archi-advice

This skill synthesizes advisory review outputs. It should combine full code review plus plan-review, diff context, or fix-advice before giving architecture advice.

## Trigger

- Concrete architecture improvement plan
- Refactor roadmap
- Redesign direction
- Sequenced architecture recommendations
- "What should we do next?"

## Preferred Workflow

1. Run full code review:

```bash
archi .
```

2. If the user has a concrete goal, write or ask for a Markdown plan and run:

```bash
archi plan-review <plan.md>
```

3. If the user is evaluating active changes, also run:

```bash
archi --diff .
```

4. If the user needs repair-direction options from a saved review, run:

```bash
archi fix-advice --for <review.json>
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Use the full code review as the primary frame. Use plan-review, diff, or fix-advice outputs as modifiers, not replacements.

## Output Rule

- Lead with the current architectural position and score.
- Give a prioritized improvement plan, not just observations.
- Prefer a phased plan: immediate, next, later.
- Advice should be grounded in code-review findings, then adjusted by plan-review, diff, or fix-advice context.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use removed `archi --goal`.
- Do not use this skill without a baseline full analysis.
- Do not produce a refactor roadmap from plan or diff context alone; use them only after `archi-full` establishes the structural baseline.

## Example Prompts

- "Based on the current architecture, what should we improve next?"
- "Give me a concrete architecture refactor roadmap for this repo."
- "Combine the baseline architecture review with the current plan and propose a phased plan."

## Standard Output Template

Use this response shape:

```text
Current Position
- baseline score: <score>
- current reading: <one-line interpretation>

Immediate
- <action 1>
- <action 2>

Next
- <action 1>
- <action 2>

Later
- <action 1>
- <action 2>
```
