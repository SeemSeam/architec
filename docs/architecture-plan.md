# Architect Role Boundary Plan

## Why a standalone folder

- Decouple Architect prompts/rules from navigation code paths.
- Make prompt and scoring iteration fast without touching runtime core.
- Allow independent versioning and experiment tracking.

## Boundary Definition

### Inputs
- `.hippocampus/structure-prompt.md` (project map)
- `.hippocampus/architect-metrics.json` (static metrics snapshot)
- optional `git diff`
- optional user intent text

### Outputs
- `.hippocampus/architect-prompt.md` (LLM-ready packed prompt)
- `architect report JSON` (from backend strong model)

### Non-goals
- No direct message rewriting.
- No direct context injection mutation.
- No provider routing decisions.

## Data Contracts

### Metrics snapshot (producer: collect_repo_metrics)
- `summary`
- `scores`
- `findings_stats`
- `findings[]`

### Architect response (consumer: lifecycle/gateway)
- `confidence`
- `scores`
- `critical_issues[]`
- `actions[]`
- `context_policy`

## Async Runtime Recommendation

1. Trigger architect worker only for architecture-heavy intent or low nav confidence.
2. Run off critical path; consume result on next turn with snapshot hash guard.
3. Fail-open: if worker errors or times out, skip architect intervention.
4. Apply only when `confidence >= threshold` and schema validates.

## Tool-call recommendation

If multi-turn tools are enabled for backend models:
- Tool allowlist:
  - `hippo_structure`
  - `hippo_search`
  - `git_diff_stat`
  - `read_file_excerpt`
- Max rounds per architect job: `3`
- Max tool calls per round: `3`
- Hard timeout per job: `8s`

This keeps Architect strong-model capability high while controlling token and latency drift.
