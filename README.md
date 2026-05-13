# Architec

`architec` is an analysis-only architecture review tool.

The primary CLI command is `archi`.

It consumes Hippo bundle inputs from `.hippocampus/`, runs architecture analysis with backend LLM support, and writes its own outputs to `.architec/`.

## Install

For end users, use the production installer:

```bash
curl -fsSL https://www.architec.top/downloads/latest/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

This is the only recommended public install path. It installs the compiled Architec
build, pulls the bundled open-source dependency wheels when available, performs
basic environment checks, and leaves you with a working `archi` command.

The installer auto-detects the current OS and CPU architecture. End users should
normally use the same command on Linux and macOS. The only hard requirement is
that the selected release already contains the matching compiled asset, such as
`archi-linux-x86_64.tar.gz` or `archi-macos-arm64.tar.gz`.

The production installer supports explicit release selection and checksum
verification:

```bash
bash install_prod.sh --version v0.1.1
bash install_prod.sh --skip-checksum
```

Default behavior is to fetch `SHA256SUMS.txt` from the selected GitHub release and verify the downloaded archive before installation.

You can override the target directory with `ARCHITEC_USER_CONFIG_DIR`.

For compiled release packaging:

```bash
python3 ../architec-release/tools/build_release.py --with-nuitka
```

The production installer also ensures the open-source `hippocampus` and
`llmgateway` Python packages are installed from bundled release wheels when
available, then falls back to their public Git sources.

Minimal runtime config split:

```yaml
# ~/.llmgateway/config.yaml
version: 1
provider:
  provider_type: glm
  api_style: openai_responses
  base_url: https://your-llm-endpoint
  api_key: sk-...
settings:
  strong_model: gpt-5.4
  weak_model: gpt-5.4
```

```yaml
# ~/.architec/config.yaml
version: 1
tasks:
  architect_history:
    tier: strong
  architect_component_scoring:
    tier: weak
  architec_summary:
    tier: strong
```

Runtime config lookup now prefers:

1. provider route under `~/.llmgateway/`
2. project override under `.architec/`
3. user-global Architec config under `~/.architec/`
4. repo/package defaults under `config/`

Concrete model names are owned by `llmgateway`. `architec` only decides which
tasks use the `strong` or `weak` tier.
`architect_component_scoring` may remain configured for runtime scoring, but
advisory diff/since preflight does not require it.

Validate end-to-end from a project that already has Hippo inputs:

```bash
archi --check .
archi --refresh-from-hippo --check .
```

The installer already runs backend LLM preflight without requiring `.hippocampus/`.

For `archi --refresh-from-hippo`, the supported runtime sources are:

- published `hippo` on `PATH`
- installed `hippocampus` in the active Python environment

A sibling checkout such as `./hippocampus/src` is not a supported runtime fallback for end-user installs or release validation.

## Skills

Bundled skill source trees live in:

- `codex_skills/`
- `claude_skills/`

The website installer syncs them into:

- `~/.codex/skills`
- `~/.claude/skills`

Current skill map:

- `archi-full`: full-project advisory code review via `archi .` or `archi code-review --full .`
- `archi-diff`: change-scoped advisory code review via `archi --diff .` or `archi code-review --diff .`
- `archi-goal`: retired public workflow; write a plan Markdown file and run `archi plan-review <plan.md>` instead
- `archi-advice`: legacy planning-oriented workflow; advisory review output now uses `plan-review`, `code-review`, and `fix-advice`

Recommended usage order:

1. Run `archi-full` to establish the current structural review.
2. Add `archi-diff` when evaluating active changes.
3. When a concrete target or refactor objective exists, write it as a plan Markdown file and run `archi plan-review <plan.md>`.
4. Use code-review output as advisory input for human or agent follow-up; `architec` does not plan, gate, or automatically repair work.

## Usage

Detailed manual:

- `docs/usage-manual.md`
- `docs/advisory-review/release-notes.md`
- `docs/commercial-rollout-plan.md`
- `../architec-cloud/docs/local-auth-portal-mvp.md`
- `../architec-cloud/README.md`
- `../architec-release/docs/release-sop.md`

Real release-install regression:

```bash
bash ../architec-release/tools/release_install_smoke.sh
```

This starts the sibling `architec-cloud` portal, runs the website smoke, installs the public GitHub Release build, authorizes it through `/api/cli/authorize`, and verifies `archi login`, `archi whoami --json`, `archi status --json`, `archi devices --json`, and `archi logout`.

Live production browser-auth regression:

```bash
bash tools/prod_browser_auth_smoke.sh
```

This uses `https://www.architec.top` directly, installs from the public website script into an isolated run directory, completes the browser-authorization callback over local `127.0.0.1`, and verifies `archi whoami --json`, `archi status --json`, and `archi devices --json`.

Release cut helper:

```bash
bash ../architec-release/tools/cut_release.sh
```

This runs the core release checks across the sibling source, website, and release-management repos, creates the `v<version>` tag from the source repo `pyproject.toml`, and then uses the release-management tooling to publish into `bfly123/architec-releases`.

Local auth commands:

```bash
archi login
archi status --json
archi whoami --json
archi devices --json
archi logout
```

Version-gated auth behavior:

- `archi login` includes the local CLI version in the browser approval URL and in the code-exchange request.
- `archi status` and `archi whoami` include the current CLI version when querying the portal.
- lease refresh now also includes the current CLI version, so the portal can enforce a minimum supported build after rollout.
- if the portal returns an upgrade requirement, the CLI surfaces the GitHub Releases download URL instead of a generic auth failure.
- `archi status --json` and `archi whoami --json` now expose `action_required`, release links, and `recommended_upgrade_command` when the local build is too old.
- for automation, prefer the stable `upgrade` object in `archi status --json` and `archi whoami --json` instead of reading scattered top-level fields.

Advisory review:

```bash
archi .
archi code-review --full .
archi --diff .
archi code-review --diff .
archi code-review --since main .
```

`archi .` and `archi --diff .` are top-level aliases for code-review output. When `--out <path>` is used with those aliases, the JSON shape is CodeReviewResult rather than the legacy analysis result.

Diff and since reviews use the same base LLM preflight as full review. If a
`code-review --since <ref>` range cannot be resolved, the command returns a
structured CodeReviewResult explaining the unresolved range instead of falling
back to a full review.

Exact `near_duplicate` detection and conservative `shadow_implementation`
detection both support changed-file-scoped diff/since review: the primary
concern location is in the changed files, while structured references can point
to unchanged existing implementations.

Displayed top concerns use portfolio ranking: severity remains first, and
same-level concerns prefer a mix of kinds before filling remaining slots.

Generated `concern_id` values in current code-review output are fact-based identifiers, not display positions. `fix-advice` reports a CLI error for missing, invalid, or non-object review JSON; a valid review with no concerns still produces an empty suggestions list. `fix-advice` has dedicated advisory branches for duplication and shadow-implementation concerns when the review includes structured reference locations.

Plan review:

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
  - src/service/contracts.py
```
````

```bash
archi plan-review plan.md
```

The top-level `--goal` flag has been removed. Write the intent as a plan Markdown file and use `archi plan-review <plan.md>`.

Legacy maintenance command parsers have been removed. Use these replacement workflows instead:

- `archi cleanup .` -> `archi code-review --full .`
- `archi autofix .` -> `archi fix-advice --for <review.json>`
- `archi baseline .` -> `archi status --snapshot`
- `archi gate .` -> `archi code-review --diff . --out review.json`

`code-review --full` carries cleanup/archive observations as advisory signals and file-level concerns. `code-review --diff` output is advisory review data for humans or agents. Do not treat review output as a merge decision, and do not use automatic apply flows as part of the advisory-review workflow.

CLI self-maintenance:

```bash
archi update
archi uninstall
```

Diff analysis:

```bash
archi --diff .
archi --diff --base main --head HEAD .
archi code-review --diff .
```

Refresh Hippo bundle first:

```bash
archi --refresh-from-hippo .
```

## Outputs

Architec writes only to `.architec/`:

- `.architec/architec-analysis.json`
- `.architec/architec-summary.md`
- `.architec/architec-viz.html`
- `.architec/architec-cleanup-inventory.json`
- `.architec/architec-cleanup-ledger.json`
- `.architec/architec-cleanup-summary.md`
- `.architec/architec-archive-candidates.json`
- `.architec/architec-archive-summary.md`
- `.architec/architec-semantic-judge.json`
- `.architec/architec-semantic-judge-summary.md`
- `.architec/cache/*`

Historical legacy artifacts such as `.architec/architec-autofix-plan.json`, `.architec/architec-autofix-summary.md`, `.architec/architec-baseline.json`, `.architec/architec-baseline-summary.md`, `.architec/architec-gate.json`, and `.architec/architec-gate-summary.md` may exist from older runs. Cleanup, autofix, baseline, and gate wrapper public APIs and command parsers have been retired. Current advisory commands do not write these legacy-only artifacts.

Hippo remains the producer of input artifacts under `.hippocampus/`.

## Notes

- `--goal` has been removed from the parser; use `archi plan-review <plan.md>` for plan or intent review.
- Default top-level mode is full advisory code review.
- `--diff` switches the top-level alias to advisory diff code review against the working tree or an explicit git range.
- `archi cleanup` and `archi autofix` command parsers have been removed; use `archi code-review --full .` cleanup/archive signals and `archi fix-advice --for <review.json>`.
- `archi update` checks the latest public release when possible, then reruns the production installer; if the current version already matches, it simply reinstalls the latest build.
- `archi uninstall` is a deep uninstall by default: it removes the managed launcher, install tree, bundled skills, local config dirs, and attempts to uninstall `hippocampus` and `llmgateway` from the active Python environment. Use `--yes` only for non-interactive automation.
- repo-root `.architecture-rules.toml` can now annotate cleanup candidates via `[[shared.cleanup_metadata]]` or `[[archi.cleanup_metadata]]` with `owner`, `ttl_days`, and `expires_at`; those fields flow through cleanup/archive signals and legacy compatibility internals.
- `archi baseline` and `archi gate` command parsers have been removed; use `archi status --snapshot` and advisory `archi code-review --diff . --out review.json`.
- `--refresh-from-hippo` refreshes Hippo inputs through stable local commands:
  `hippo init .`, `hippo sig-extract .`, `hippo tree .`, `hippo index --no-llm .`,
  `hippo structure-prompt --profile map --no-llm-enhance .`,
  then `architec/tools/collect_repo_metrics.py`.
- `architec` does not perform automatic repair loops.
