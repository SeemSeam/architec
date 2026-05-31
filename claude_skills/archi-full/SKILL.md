---
name: archi-full
description: Run full-project architecture analysis with archi. Use when the user asks for an overall architecture score, full hotspot review, package topology diagnosis, or the main structural weaknesses of the current codebase.
---

# archi-full

Use the locally supported full-review Archi command for the baseline
architecture pass.

## Trigger

- Overall architecture analysis
- Overall architecture score
- Hotspot review for the full repo
- Package topology or folder-structure diagnosis
- Main architecture problems

## Command

```bash
archi --help
```

If help includes `--full`, use:

```bash
archi --full
```

If help lacks `--full`, use the legacy full-review entrypoint:

```bash
archi .
```

Use Hippo refresh only when the user explicitly asks for a fresh rebuild:

```bash
archi --refresh-from-hippo --full
```

If the local help lacks `--full`, use:

```bash
archi --refresh-from-hippo .
```

## Read Outputs

- `.architec/architec-summary.md`
- `.architec/architec-analysis.json`
- `.architec/architec-viz.html`

Read `architec-summary.md` first, then `architec-analysis.json` for exact `scores`, `hotspots`, `recommendations`, and `topology`.

## Output Rule

- Lead with the total score.
- Summarize the top structural problems and top improvements.
- Do not paste raw JSON.

## Avoid Misuse

- Do not use this skill as a substitute for diff review when the question is specifically about active changes.
- Do not turn full review into task-goal planning. Use it to describe existing
  architecture risks and modification opportunities.

## Example Prompts

- Analyze this repo's overall architecture and summarize the main structural problems.
- Run a full architecture review and give me the score plus top improvements.
- Give me the current architecture baseline for this codebase.

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
