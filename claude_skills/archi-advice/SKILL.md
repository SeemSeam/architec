---
name: archi-advice
description: Produce architecture improvement advice from existing-code Archi analysis. Use when the user wants concrete modification suggestions, sequencing advice, or a practical refactor roadmap based on the current codebase rather than task-goal planning.
---

# archi-advice

This skill synthesizes existing-code Archi review outputs. It should combine
full analysis plus current diff context when relevant before giving
architecture modification advice.

## Trigger

- Architecture improvement plan
- Refactor roadmap
- Existing-code redesign direction
- Prioritized next steps

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

3. Add diff context when relevant. If help includes `--full`, use:

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

Use full code review as the baseline. Use diff results as advisory modifiers
when the user is asking about current changes.

## Output Rule

- Lead with the current architecture position and score.
- Give a phased improvement plan: immediate, next, later.
- Ground advice in code-review findings first.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill without a baseline full analysis.
- Do not produce a refactor roadmap from diff context alone; use it only after
  `archi-full` establishes the structural baseline.

## Example Prompts

- Based on the current architecture, what should we improve next?
- Give me a concrete architecture refactor roadmap for this repo.
- Turn the current Archi findings into a phased refactor plan.

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
