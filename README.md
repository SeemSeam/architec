# Architec

Architec is an advisory architecture review CLI for codebases.

It answers a practical question: **will this change make the project harder to
maintain?** It looks for architecture drift, repeated implementations,
boundary pressure, stale structure, risky hotspots, and mismatches between a
plan and the selected code changes.

The command is:

```bash
archi
```

By default, `archi` reviews the current selected changes with bounded LLM
context. Use `archi --full` only when you want a whole-project architecture
baseline.

Architec is analysis-only. It does not require login, does not make merge
decisions, and does not automatically edit your code.

## Why Architec

Modern LLM-assisted coding can move quickly, but it can also create slow
architecture drift:

- duplicate implementations that should share a helper or facade;
- new code that bypasses the intended module boundary;
- compatibility shims that are not documented as compatibility shims;
- cleanup/archive concerns that keep accumulating;
- plans that say one thing while the diff touches another;
- changes in high-churn or weakly covered areas that deserve extra review.

Architec turns those signals into structured review output for humans and
agents. It is intentionally advisory: a reviewer still decides what to do.

## Install

Recommended public install:

```bash
curl -fsSL https://www.architec.top/downloads/latest/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

This installs the compiled `archi` command and prepares the open-source runtime
dependencies used by Architec, including Hippo and llmgateway when bundled
wheels are available.

Optional release selection:

```bash
bash install_prod.sh --version v0.2.10
```

The installer verifies release checksums by default when `SHA256SUMS.txt` is
available.

For local development from this repository:

```bash
python3 -m pip install -e .
```

## Configure an LLM

Architec uses llmgateway for provider routing. Put provider credentials in
`~/.llmgateway/config.yaml`:

```yaml
version: 1
provider:
  provider_type: openai
  api_style: openai_responses
  base_url: https://your-llm-endpoint/v1
  api_key: sk-...
settings:
  strong_model: your-strong-model
  weak_model: your-fast-model
```

Architec maps review tasks to model tiers in `~/.architec/config.yaml`:

```yaml
version: 1
tasks:
  architect_history:
    tier: strong
  architect_component_scoring:
    tier: weak
  architec_summary:
    tier: strong
```

Concrete model names belong in llmgateway. Architec only asks for `strong` or
`weak` task tiers.

Check the installation and LLM route:

```bash
archi --check .
```

## Quick Start

From a git repository:

```bash
archi
```

This runs selected-change architecture review. It reads the current git changes,
uses compact evidence, sends the selected-scope context to the LLM, and returns
bounded advisory output.

Run a full baseline when you need repository-wide context:

```bash
archi --full
```

Write JSON for automation or agent follow-up:

```bash
archi --out review.json
archi --full --out full-review.json
```

Refresh Hippo inputs first when you explicitly want a fresh structural snapshot:

```bash
archi --refresh-from-hippo --full
```

Default `archi` does **not** refresh Hippo automatically. It reports whether the
available snapshot is present, stale, or unknown as review context.

## Core Commands

| Command | Use it for |
| --- | --- |
| `archi` | Default incremental LLM architecture review for selected changes. |
| `archi --full` | Whole-project LLM architecture review and baseline artifacts. |
| `archi --check .` | Validate Hippo bundle state and LLM configuration. |
| `archi --out review.json` | Save the current review JSON. |
| `archi plan-review plan.md --out plan.json` | Convert a written plan into structured plan-review JSON. |
| `archi code-review --diff --plan-review plan.json .` | Compare selected changes against a saved plan. |
| `archi code-review --since main .` | Review changes since a git ref. |
| `archi fix-advice --review review.json` | Produce advisory follow-up options for a saved review. |
| `archi status --snapshot` | Record an advisory project status snapshot. |
| `archi status --trend` | Read recent advisory review trend data. |

`archi --diff` remains as a compatibility alias for the default incremental
review path.

## What Architec Looks For

Full and incremental reviews can surface:

- `duplication`: exact normalized Python function duplication, with conservative
  suppression for intentional wrappers and variant families;
- `shadow-implementation`: function/class implementations that look like a
  second copy of existing behavior without a reuse edge;
- `architecture-contract`: project-local import or ownership rules from
  `.architecture-rules.toml`;
- `plan-diff-consistency`: changed files, import expectations, tests, public API
  migrations, or explicit intent checks that do not line up with a saved plan;
- `cleanup` and `archive`: stale docs, compatibility layers, legacy paths, and
  cleanup candidates;
- `hotspot` and `topology`: full-review signals about concentration and package
  structure;
- `risk_context`: optional external facts such as coverage, churn, complexity,
  public API files, or recurrence attached to existing concerns.

These are review signals, not proof of correctness.

## Plan Review

For larger changes, write the intended touchpoints first:

````markdown
# Plan

## Intent
Stabilize service boundaries.

## Changes
```yaml
changes:
  - action: update
    path: src/service/boundary.py
    intent: clarify service ownership
dependencies:
  - source: src/api/**
    imports:
      - app.service.facade
expected_tests:
  - source: src/service/**
    test_glob: tests/service/**
```
````

Then run:

```bash
archi plan-review plan.md --out plan.json
archi code-review --diff --plan-review plan.json .
```

Architec only treats explicit structured plan entries as requirements. Prose
notes stay context.

## Risk Context

You can enrich existing concerns with external facts:

```bash
archi code-review --diff --risk-context risk.json .
```

Supported inputs include conservative coverage.py-style file maps,
radon-like complexity maps, churn maps, public API files, source-to-test maps,
and changed test files. Architec does not run tests, generate coverage, or mine
git history by itself.

## Outputs

Architec writes generated files under `.architec/`:

- `.architec/architec-analysis.json`
- `.architec/architec-summary.md`
- `.architec/architec-viz.html`
- `.architec/code-review-concerns.json`
- `.architec/code-review-discovery.json`
- `.architec/review-events.jsonl`
- `.architec/cache/*`

Hippo remains the producer of input artifacts under `.hippocampus/`.

Top-level review JSON is intentionally bounded. Full generated concerns are
kept in `.architec/code-review-concerns.json`.

## No Login Required

Architecture analysis commands do not require `archi login`.

These account commands still exist for portal diagnostics and release smoke
tests, but they are not part of normal review usage:

```bash
archi login
archi whoami --json
archi status --json
archi devices --json
archi logout
```

## Skills

The release can install helper skills for agent environments:

- `archi-full`: use `archi --full` for whole-project review;
- `archi-diff`: use `archi` for selected-change review;
- `archi-goal`: use plan Markdown plus `archi plan-review`;
- `archi-advice`: synthesize review output into a practical refactor roadmap.

Skill source trees live in `codex_skills/` and `claude_skills/`.

## Development

Run tests:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Run Architec from this checkout:

```bash
PYTHONPATH=src python3 -m architec
PYTHONPATH=src python3 -m architec --full
```

Build a compiled release from the sibling release repository:

```bash
python3 ../architec-release/tools/build_release.py --with-nuitka
```

Maintenance commands:

```bash
archi update
archi uninstall
```

## More Documentation

- [Usage manual](docs/usage-manual.md)
- [Advisory review release notes](docs/advisory-review/release-notes.md)
- [Architecture stability notes](docs/advisory-review/topics/architecture-stability.md)
- [Evidence model](docs/advisory-review/topics/evidence-model.md)
