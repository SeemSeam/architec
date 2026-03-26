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

Validate end-to-end from a project that already has Hippo inputs:

```bash
archi --check .
archi --refresh-from-hippo --check .
```

The installer already runs backend LLM preflight without requiring `.hippocampus/`.

## Skills

Bundled skill source trees live in:

- `codex_skills/`
- `claude_skills/`

The website installer syncs them into:

- `~/.codex/skills`
- `~/.claude/skills`

Current skill map:

- `archi-full`: baseline full-repo architecture analysis via `archi .`
- `archi-diff`: change-scoped architecture review via `archi --diff .`
- `archi-goal`: goal-driven architecture placement and boundary analysis via `archi --goal "<goal>" .`
- `archi-advice`: concrete architecture improvement planning built on top of full analysis, then refined by goal or diff context when relevant

Recommended usage order:

1. Run `archi-full` to establish the structural baseline.
2. Add `archi-diff` when evaluating active changes.
3. Add `archi-goal` when the user has a concrete target or refactor objective.
4. Use `archi-advice` only after baseline context exists; it should synthesize full analysis first, then goal or diff results.

## Usage

Detailed manual:

- `docs/usage-manual.md`
- `docs/commercial-rollout-plan.md`
- `../architec-cloud/docs/local-auth-portal-mvp.md`
- `../architec-cloud/README.md`
- `../architec-release/docs/release-sop.md`

Real release-install regression:

```bash
bash ../architec-release/tools/release_install_smoke.sh
```

This starts the sibling `architec-cloud` portal, runs the website smoke, installs the public GitHub Release build, authorizes it through `/api/cli/authorize`, and verifies `archi login`, `archi whoami --json`, `archi status --json`, `archi devices --json`, and `archi logout`.

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

Full analysis:

```bash
archi .
archi --goal "analyze architecture stability" .
```

Diff analysis:

```bash
archi --diff .
archi --diff --base main --head HEAD .
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
- `.architec/cache/*`

Hippo remains the producer of input artifacts under `.hippocampus/`.

## Notes

- `--goal` is the only semantic analysis input.
- Default mode is full analysis.
- `--diff` switches to incremental analysis against the working tree or an explicit git range.
- `--refresh-from-hippo` refreshes Hippo inputs through stable local commands:
  `hippo init .`, `hippo sig-extract .`, `hippo tree .`, `hippo index --no-llm .`,
  `hippo structure-prompt --profile map --no-llm-enhance .`,
  then `architec/tools/collect_repo_metrics.py`.
- `architec` does not perform automatic repair loops.
