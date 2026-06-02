---
name: archi-diff
description: Run incremental architecture review with archi. Use when the user asks whether current changes introduce architecture risk or what the current selected changes affect.
---

# archi-diff

Use `archi` for the public incremental architecture review workflow.

## Trigger

- Architecture review for current git changes
- "Did these changes make the architecture worse?"
- Changed-file or changed-component risk review
- Incremental architecture concerns

## Command

```bash
archi
```

Save JSON only when the user asks for a file:

```bash
archi --out review.json
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`

Focus on:

- `recommendations`
- `concerns`
- `signals`
- `summary`

## Output Rule

- Lead with whether the current changes introduce architecture concerns.
- Summarize impacted components and main risks.
- End with the minimal set of improvements, if any.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill as the only architecture view when the user needs a repo-wide structural baseline; use `archi-full`.
- Do not infer long-term redesign direction from diff results alone.

## Example Prompts

- "Review the current git diff from an architecture perspective."
- "Tell me whether these changes are architecturally safe to merge."
- "Run incremental architecture analysis and summarize the main risks."

## Standard Output Template

Use this response shape:

```text
Verdict
- incremental status: <no concerns / caution / concern>

Impacted Areas
- <component or area 1>
- <component or area 2>
- <component or area 3>

Improvements
- <improvement 1>
- <improvement 2>
- <improvement 3>
```
