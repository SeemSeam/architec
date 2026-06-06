# Architec

**Incremental architecture review for AI-assisted codebases.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![CLI](https://img.shields.io/badge/CLI-archi-222222)](#quick-start)
[![Login](https://img.shields.io/badge/login-not_required-green)](#no-login-required)

[English](README.md) | [中文](README.zh-CN.md)

Architec is an advisory architecture analysis CLI. It helps answer one
practical question:

> Will this change make the codebase harder to maintain?

It reviews current changes by default, asks an LLM to interpret compact
selected-scope evidence, and reports architecture risks such as duplicated
logic, shadow implementations, unclear boundaries, stale structure, topology
pressure, and risky hotspots.

Architec does not make merge decisions and does not edit code. It gives
structured advice for humans and coding agents to review.

## Why Architec

LLM-assisted development can move quickly, but architecture can drift quietly.
Architec is designed to catch the kinds of issues that accumulate over time:

- repeated implementations and "same idea twice" code;
- compatibility paths that blur into canonical implementations;
- changed files crossing intended module boundaries;
- stale cleanup/archive candidates;
- high-risk work landing in churn-heavy areas;
- full-project topology pressure that is easy to miss during local edits.

The default workflow is incremental-first:

```bash
archi
```

Use full review when you want the whole-project baseline:

```bash
archi --full
```

## How It Fits Together

Architec is the review layer. It uses two companion components:

| Component | Command / package | Role |
| --- | --- | --- |
| **Architec** | `archi` / `architec` | Runs architecture review, calls the LLM through llmgateway, writes advisory results under `.architec/`. |
| **Hippos** | `hippos` / `seemseam-hippos` | Builds structural project snapshots under `.hippos/`: file manifests, code signatures, repository indexes, structure prompts, and metrics. |
| **llmgateway** | `llmgateway` | Owns provider credentials, base URLs, API style, model names, and strong/weak model routing. |

```text
source tree + git changes
        |
        v
Hippos structural snapshot  ->  .hippos/
        |
        v
Architec evidence builder  ->  selected-scope or full-project context
        |
        v
llmgateway LLM call        ->  strong / weak model tiers
        |
        v
Architec review output     ->  .architec/
```

Day-to-day `archi` runs still use the LLM, but they avoid refreshing the whole
Hippos snapshot unless requested. `archi --full` uses the Hippos snapshot more
heavily, and `archi --refresh-from-hippos --full` refreshes it before review.

## How It Works

Architec combines deterministic code signals with LLM interpretation. The
deterministic layer keeps the review grounded in concrete evidence; the LLM
layer turns that evidence into readable architecture advice.

1. **Select scope**
   - `archi` reads the current git changes and focuses on changed files.
   - `archi --full` reviews the whole project.

2. **Read structural context**
   - Hippos produces `.hippos/` snapshots: file manifests, code signatures,
     repository indexes, metrics, and structure prompts.
   - Architec checks whether that snapshot is present, stale, or unknown.

3. **Build architecture evidence**
   - Architec runs static scanners for duplicated logic, shadow
     implementations, import-boundary pressure, cleanup/archive candidates,
     hotspots, topology pressure, and snapshot freshness.
   - Incremental review keeps selected-change concerns separate from broader
     project context so small diffs are not drowned by global noise.

4. **Ask the LLM for interpretation**
   - Architec sends compact evidence to llmgateway.
   - llmgateway chooses the configured strong or weak model tier and owns all
     provider credentials.

5. **Write advisory output**
   - Architec ranks concerns, keeps raw artifacts for inspection, and writes
     human-readable plus machine-readable output under `.architec/`.
   - The result is advice, not an automatic merge decision or proof of runtime
     correctness.

## Install

Architec requires Python 3.11+.

Recommended install from PyPI:

```bash
python3 -m pip install --user architec
```

This installs:

- `archi`, the Architec CLI;
- `seemseam-llmgateway`, the package that provides the LLM provider gateway;
- `seemseam-hippos`, the package that provides Hippos structural snapshots.

The runtime imports remain `llmgateway` and `hippos`; no separate package index
setup is required.

Standalone GitHub installer:

```bash
curl -fsSL https://github.com/SeemSeam/architec/releases/latest/download/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

The installer downloads the matching standalone `archi` binary from
`SeemSeam/architec` GitHub Releases and verifies it against the release
checksum file. It creates `~/.llmgateway/config.yaml` only when the file is
missing and never overwrites existing provider credentials.

Optional npm binary dispatcher install:

```bash
npm install -g @seemseam/archi
```

The npm package exposes only the `archi` command. Its standalone binary bundles
Hippos for Architec refreshes and uses llmgateway as a library dependency, so
normal npm users do not need separate `hippos` or `llmgateway` commands. Install
`seemseam-hippos` separately only if you want to run the Hippos CLI directly.
During npm install and on first `archi` startup, the dispatcher creates
`~/.llmgateway/config.yaml` when it is missing and never overwrites an existing
provider config.

The historical `@seemseam/architec` npm package is kept only as a compatibility
shim for existing users.

## Output Language

Architec prints English by default, and automatically switches CLI status,
error, and maintenance output to Chinese when the system locale is Chinese
(`LC_ALL`, `LC_MESSAGES`, `LANGUAGE`, or `LANG` starts with `zh`).

You can force a language for scripts or tests:

```bash
ARCHITEC_LANG=zh archi --version
ARCHITEC_LANG=en archi --check .
```

Local development from this repository:

```bash
python3 -m pip install -e .
```

## Configure LLM Access

Architec gets all LLM access through **llmgateway**. Configure provider
credentials and model tiers in:

```text
~/.llmgateway/config.yaml
```

The public installer creates this file only when it is missing. It never
overwrites an existing `~/.llmgateway/config.yaml`, including provider
credentials. The starter template includes primary provider fields, model tier
settings, and commented fallback-provider examples. Fallback behavior depends on
the installed llmgateway schema; current llmgateway supports an ordered
`providers` chain.

Use `archi --check .` to validate provider credentials before analysis. Regular
analysis commands now fail when the required backend LLM is unavailable. Pass
`--allow-static` only when you intentionally want Architec to return static
code-review signals instead of LLM-backed results.

Minimal example:

```yaml
version: 1
providers:
  - provider_type: openai
    api_style: openai_chat
    base_url: https://your-llm-endpoint/v1
    api_key: sk-...
    headers: {}
    model_map: {}
settings:
  fallback_model: your-fast-model
  strong_model: your-strong-model
  weak_model: your-fast-model
  strong_reasoning_effort: high
  weak_reasoning_effort: low
```

Architec consumes the configured `strong_model` and `weak_model` tiers. It does
not store model-provider credentials itself.

Check the installation and LLM route:

```bash
archi --check .
```

If the check reports missing LLM configuration, update
`~/.llmgateway/config.yaml`.

## Quick Start

Review the current selected changes:

```bash
archi
```

Run whole-project architecture review:

```bash
archi --full
```

Save JSON output:

```bash
archi --out review.json
archi --full --out full-review.json
```

Refresh Hippos inputs before full review:

```bash
archi --refresh-from-hippos --full
```

## Command Summary

| Command | Purpose |
| --- | --- |
| `archi` | Incremental LLM architecture review for current selected changes. |
| `archi --full` | Full-project LLM architecture review. |
| `archi --out review.json` | Save incremental review JSON. |
| `archi --full --out full-review.json` | Save full-review JSON. |
| `archi --refresh-from-hippos --full` | Refresh Hippos structural inputs, then run full review. |
| `archi --check .` | Validate Hippos bundle state and llmgateway configuration. |

Advanced compatibility flags and older subcommands may still be accepted for
existing automation, but new usage should prefer the commands above.

## What Architec Reports

Architec reports advisory concerns and signals, including:

- **Duplication**: repeated logic and suspicious near-duplicates.
- **Shadow implementations**: second implementations of similar behavior.
- **Architecture contracts**: import-boundary or dependency-direction pressure.
- **Cleanup/archive candidates**: stale or legacy-looking code and docs.
- **Hotspots**: churn-heavy or structurally risky areas.
- **Topology pressure**: flat or confusing project structure.
- **Snapshot freshness**: missing, stale, or unknown Hippos context.
- **Risk context**: optional external facts attached to existing concerns.

The output is advisory. It is not a pass/fail result and is not proof of
runtime correctness.

## Outputs

Architec writes generated files under `.architec/`:

```text
.architec/
  architec-analysis.json
  architec-summary.md
  architec-viz.html
  code-review-concerns.json
  code-review-discovery.json
  review-events.jsonl
  cache/
```

Hippos writes structural inputs under `.hippos/`.

Start with `.architec/architec-summary.md` for the human-readable report, then
open `.architec/architec-analysis.json` for exact scores, concerns, signals,
and artifact paths.

## Agent Command Compatibility

The commands above describe the current public workflow. Some older installed
`archi` binaries may still show the previous command shape, where full review
is `archi .` and incremental review is `archi --diff .`.

Agents and automation should inspect the local binary before choosing commands:

```bash
archi --help
```

| Help output | Incremental review | Full review |
| --- | --- | --- |
| Includes `--full` | `archi` | `archi --full` |
| Lacks `--full` but includes `--diff` | `archi --diff .` | `archi .` |

## No Login Required

Architecture analysis does not require `archi login`.

Account commands such as `archi login`, `archi whoami --json`, and
`archi devices --json` may exist for diagnostics, but they are not part of
normal Architec analysis.

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

## More Documentation

- [Usage manual](docs/usage-manual.md)
- [Architecture stability notes](docs/advisory-review/topics/architecture-stability.md)
- [Evidence model](docs/advisory-review/topics/evidence-model.md)
