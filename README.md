# Architec

Architec is an advisory architecture analysis CLI for codebases.

It helps answer a practical question:

> Will this change make the project harder to maintain?

Architec looks for architecture drift, repeated implementations, unclear
module boundaries, stale structure, hotspots, topology pressure, and other
signals that can accumulate into long-term maintenance risk.

The main command is:

```bash
archi
```

By default, `archi` reviews the current selected changes with compact LLM
context. Use `archi --full` when you want a whole-project architecture review.

Architec is analysis-only. It does not require login, does not make merge
decisions, and does not automatically edit code.

## Why Use Architec

LLM-assisted development can move fast, but it can also drift:

- a new implementation duplicates an existing one;
- a change bypasses a module boundary;
- a helper grows into an unowned subsystem;
- compatibility code becomes indistinguishable from the canonical path;
- stale docs and cleanup candidates keep accumulating;
- a small change lands in a high-churn or high-risk area.

Architec turns those signals into structured architecture review output. It is
meant to support human and agent review, not replace it.

## Install

Recommended public install:

```bash
curl -fsSL https://www.architec.top/downloads/latest/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

The installer provides the `archi` command and prepares the runtime dependencies
used by Architec, including Hippo and llmgateway when bundled wheels are
available.

Install a specific release:

```bash
bash install_prod.sh --version v0.2.10
```

For local development from this repository:

```bash
python3 -m pip install -e .
```

## Configure LLM Access

Architec gets LLM access through **llmgateway**.

Configure your provider and models in:

```text
~/.llmgateway/config.yaml
```

Example:

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

Architec does not own provider credentials or concrete model names. Those live
in llmgateway. Architec consumes the configured strong/weak model tiers.

Check the installation and LLM route:

```bash
archi --check .
```

## Quick Start

Run selected-change architecture review:

```bash
archi
```

This is the normal day-to-day command. It reads the current git changes, builds
compact architecture evidence, asks the LLM to interpret that selected-scope
context, and returns bounded advisory output.

Run whole-project architecture review:

```bash
archi --full
```

Use full review when you need a fresh baseline, broad hotspots, topology
diagnosis, cleanup/archive context, or repository-wide architecture direction.

Save JSON output:

```bash
archi --out review.json
archi --full --out full-review.json
```

Refresh Hippo inputs before a full review:

```bash
archi --refresh-from-hippo --full
```

Default `archi` does not refresh Hippo automatically. It reports whether the
available structural snapshot is present, stale, or unknown.

## Command Summary

| Command | Purpose |
| --- | --- |
| `archi` | Incremental LLM architecture review for current selected changes. |
| `archi --full` | Full-project LLM architecture review. |
| `archi --out review.json` | Save review JSON. |
| `archi --full --out full-review.json` | Save full-review JSON. |
| `archi --refresh-from-hippo --full` | Refresh Hippo inputs, then run full review. |
| `archi --check .` | Validate Hippo bundle state and LLM configuration. |

`archi --diff` is still accepted as a compatibility alias for the default
incremental review path, but new usage should prefer plain `archi`.

## What Architec Reports

Architec can report architecture concerns such as:

- duplicate logic;
- shadow implementations that look like a second copy of existing behavior;
- architecture-contract or import-boundary violations;
- cleanup/archive candidates;
- hotspots and topology pressure;
- stale or missing structural context;
- optional external risk facts attached to existing concerns.

The output is advisory. It is not a pass/fail result and it is not proof of
runtime correctness.

## Outputs

Architec writes generated files under `.architec/`:

- `.architec/architec-analysis.json`
- `.architec/architec-summary.md`
- `.architec/architec-viz.html`
- `.architec/code-review-concerns.json`
- `.architec/code-review-discovery.json`
- `.architec/review-events.jsonl`
- `.architec/cache/*`

Hippo produces structural input artifacts under `.hippocampus/`.

## No Login Required

Architecture analysis does not require `archi login`.

Account commands such as `archi login`, `archi whoami --json`, and
`archi devices --json` may exist for portal diagnostics or release smoke tests,
but they are not part of normal Architec analysis.

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

Maintenance commands:

```bash
archi update
archi uninstall
```

## More Documentation

- [Usage manual](docs/usage-manual.md)
- [Architecture stability notes](docs/advisory-review/topics/architecture-stability.md)
- [Evidence model](docs/advisory-review/topics/evidence-model.md)
