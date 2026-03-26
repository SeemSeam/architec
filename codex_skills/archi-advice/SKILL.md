---
name: archi-advice
description: Produce architecture advice by combining baseline analysis with goal or diff context. Use when the user wants a concrete architecture improvement plan, redesign direction, sequencing advice, or a practical refactor roadmap rather than only a score.
---

# archi-advice

This skill is the decision layer. It should synthesize full analysis plus current goal or diff context before giving architecture advice.

## Trigger

- Concrete architecture improvement plan
- Refactor roadmap
- Redesign direction
- Sequenced architecture recommendations
- "What should we do next?"

## Preferred Workflow

1. Run baseline analysis:

```bash
archi .
```

2. If the user has a concrete goal, also run:

```bash
archi --goal "<goal>" .
```

3. If the user is evaluating active changes, also run:

```bash
archi --diff .
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Use the baseline full analysis as the primary frame. Use goal or diff outputs as modifiers, not replacements.

## Output Rule

- Lead with the current architectural position and score.
- Give a prioritized improvement plan, not just observations.
- Prefer a phased plan: immediate, next, later.
- Advice should be grounded in full-analysis findings, then adjusted by goal or diff context.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill without a baseline full analysis.
- Do not produce a refactor roadmap from goal or diff context alone; use them only after `archi-full` establishes the structural baseline.

## Example Prompts

- "Based on the current architecture, what should we improve next?"
- "Give me a concrete architecture refactor roadmap for this repo."
- "Combine the baseline architecture review with the current goal and propose a phased plan."

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
