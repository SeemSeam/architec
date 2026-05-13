---
name: archi-advice
description: Produce advisory architecture guidance by combining code-review output with plan-review, diff context, and fix-advice. Do not use the removed archi --goal flag.
---

# archi-advice

This skill synthesizes advisory review outputs. It should combine full code review plus plan-review, diff context, or fix-advice before giving architecture advice.

## Trigger

- Architecture improvement plan
- Refactor roadmap
- Redesign direction
- Prioritized next steps

## Preferred Workflow

1. Run full code review:

```bash
archi .
```

2. Add plan context when relevant:

```bash
archi plan-review <plan.md>
```

3. Add diff context when relevant:

```bash
archi --diff .
```

4. Generate repair-direction advice from a saved review when needed:

```bash
archi fix-advice --for <review.json>
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Use full code review as the baseline. Use plan-review, diff, or fix-advice results as advisory modifiers.

## Output Rule

- Lead with the current architecture position and score.
- Give a phased improvement plan: immediate, next, later.
- Ground advice in code-review findings first.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use removed `archi --goal`.
- Do not use this skill without a baseline full analysis.
- Do not produce a refactor roadmap from plan or diff context alone; use them only after `archi-full` establishes the structural baseline.

## Example Prompts

- Based on the current architecture, what should we improve next?
- Give me a concrete architecture refactor roadmap for this repo.
- Combine the baseline architecture review with the current plan and propose a phased plan.

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
