---
name: archi-advice
description: Produce architecture advice by combining baseline analysis with goal or diff context. Use when the user wants a concrete architecture improvement plan, redesign direction, sequencing advice, or a practical refactor roadmap rather than only a score.
---

# archi-advice

This skill is the decision layer. It should synthesize full analysis plus goal or diff context before giving advice.

## Trigger

- Architecture improvement plan
- Refactor roadmap
- Redesign direction
- Prioritized next steps

## Preferred Workflow

1. Run baseline analysis:

```bash
archi .
```

2. Add goal context when relevant:

```bash
archi --goal "<goal>" .
```

3. Add diff context when relevant:

```bash
archi --diff .
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Use full analysis as the baseline. Use goal or diff results as modifiers.

## Output Rule

- Lead with the current architecture position and score.
- Give a phased improvement plan: immediate, next, later.
- Ground advice in full-analysis findings first.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill without a baseline full analysis.
- Do not produce a refactor roadmap from goal or diff context alone; use them only after `archi-full` establishes the structural baseline.

## Example Prompts

- Based on the current architecture, what should we improve next?
- Give me a concrete architecture refactor roadmap for this repo.
- Combine the baseline architecture review with the current goal and propose a phased plan.

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
