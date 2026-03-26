---
name: archi-goal
description: Run goal-driven architecture analysis with archi. Use when the user wants architecture guidance for a specific objective, feature direction, refactor target, or boundary-stability goal.
---

# archi-goal

Use `archi --goal` when the user has a concrete architectural objective.

## Trigger

- Feature placement
- Refactor target analysis
- Boundary stabilization
- Goal-specific architecture advice

## Command

```bash
archi --goal "<goal>" .
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Focus on `feature_analysis`, `recommendations`, `topology`, and `scores`.

## Output Rule

- Restate the goal in architecture terms.
- Summarize target components, placement advice, and boundary risks.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill without a concrete goal string.
- Do not treat goal-driven placement advice as a full structural baseline; pair with `archi-full` when broader architecture context matters.

## Example Prompts

- Where should this new feature go architecturally?
- Use the goal "stabilize service boundaries" and tell me the best placement.
- Analyze this refactor goal and identify the right target components.

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
