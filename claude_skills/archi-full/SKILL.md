---
name: archi-full
description: Run full-project architecture analysis with archi. Use when the user asks for an overall architecture score, full hotspot review, package topology diagnosis, or the main structural weaknesses of the current codebase.
---

# archi-full

Use `archi --full` for the public full-project architecture review workflow.

## Trigger

- Overall architecture analysis
- Overall architecture score
- Hotspot review for the full repo
- Package topology or folder-structure diagnosis
- "What are the main architecture problems?"

## Command

```bash
archi --full
```

Use Hippo refresh only when the user explicitly asks for a fresh rebuild:

```bash
archi --refresh-from-hippo --full
```

Save JSON only when the user asks for a file:

```bash
archi --full --out full-review.json
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`
- `.architec/architec-viz.html`

Read `architec-summary.md` first, then `architec-analysis.json` for exact `scores`, `hotspots`, `recommendations`, and `topology`.

## Output Rule

- Lead with the total score.
- Summarize the top 3-5 structural problems.
- Summarize the top 3-5 improvements.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill as a substitute for diff review when the question is specifically about active changes.
- Use it to describe existing architecture risks and modification opportunities.

## Example Prompts

- "Analyze this repo's overall architecture and tell me the main structural problems."
- "Run a full architecture review and summarize the score plus top improvements."
- "Give me the current architecture baseline for this codebase."

## Standard Output Template

Use this response shape:

```text
Score
- overall: <score>
- key reading: <one-line interpretation>

Problems
- <top structural problem 1>
- <top structural problem 2>
- <top structural problem 3>

Improvements
- <top improvement 1>
- <top improvement 2>
- <top improvement 3>
```
