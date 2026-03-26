---
name: archi-diff
description: Run diff-based architecture analysis with archi. Use when the user asks whether current changes are architecturally safe, what the current git diff impacts, or which changed components carry structural risk.
---

# archi-diff

Use `archi --diff` for change-scoped architecture review.

## Trigger

- Architecture review for current git changes
- "Did this diff make the architecture worse?"
- Changed-component risk review
- Incremental architecture score

## Commands

```bash
archi --diff .
```

When the user provides an explicit range:

```bash
archi --diff --base <base> --head <head> .
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Focus on:

- `scores.incremental`
- `change_analysis`
- `recommendations`
- `hotspots`

## Output Rule

- Lead with whether the current diff is architecturally safe.
- Summarize impacted components and main risks.
- End with the minimal set of improvements needed before merge.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill as the only architecture view when the user needs a repo-wide structural baseline; run `archi-full` first.
- Do not infer long-term redesign direction from diff results alone.

## Example Prompts

- "Review the current git diff from an architecture perspective."
- "Tell me whether these changes are architecturally safe to merge."
- "Run incremental architecture analysis and summarize the main risks."

## Standard Output Template

Use this response shape:

```text
Verdict
- diff status: <safe / caution / unsafe>
- incremental score: <score>

Impacted Areas
- <component or area 1>
- <component or area 2>
- <component or area 3>

Required Changes
- <required improvement 1>
- <required improvement 2>
- <required improvement 3>
```
