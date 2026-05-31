---
name: archi-advice
description: Produce architecture improvement advice from existing-code Archi analysis. Use when the user wants concrete modification suggestions, sequencing advice, or a practical refactor roadmap based on the current codebase rather than task-goal planning.
---

# archi-advice

This skill synthesizes existing-code Archi review outputs. It should combine
full analysis plus current diff context when relevant before giving
architecture modification advice.

## Trigger

- Concrete architecture improvement plan
- Refactor roadmap
- Existing-code redesign direction
- Sequenced architecture recommendations
- "What should we do next?"

## Preferred Workflow

1. Inspect the local command shape:

```bash
archi --help
```

2. Run baseline analysis. If help includes `--full`, use:

```bash
archi --full
```

If help lacks `--full`, use:

```bash
archi .
```

3. If the user is evaluating active changes, also run incremental review. If
help includes `--full`, use:

```bash
archi
```

If help lacks `--full` but includes `--diff`, use:

```bash
archi --diff .
```

4. Do not run goal, plan-review, or fix-advice commands. Synthesize advice from
the baseline output, incremental output, and the current codebase.

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Use the full code review as the primary frame. Use diff output as a modifier
when the user is asking about current changes.

## Output Rule

- Lead with the current architectural position and score.
- Give a prioritized improvement plan, not just observations.
- Prefer a phased plan: immediate, next, later.
- Advice should be grounded in code-review findings, then adjusted by diff
  context when relevant.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill without a baseline full analysis.
- Do not produce a refactor roadmap from diff context alone; use it only after
  `archi-full` establishes the structural baseline.

## Example Prompts

- "Based on the current architecture, what should we improve next?"
- "Give me a concrete architecture refactor roadmap for this repo."
- "Turn the current Archi findings into a phased refactor plan."

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
