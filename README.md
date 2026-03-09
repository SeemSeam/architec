# Architec

`architec` is an analysis-only architecture review tool.

It consumes Hippo bundle inputs from `.hippocampus/`, runs architecture analysis with backend LLM support, and writes its own outputs to `.architec/`.

## Install

```bash
./install.sh
```

`install.sh` will:

- install the package in editable mode
- require `architec_llm_main_url` and `architec_llm_main_api_key`
- prompt for them when running interactively
- seed `rubric.json` and `scoring-policy.json` into `~/.architec/`
- write a global user config to `~/.architec/architec-llm.yaml`
- run backend LLM preflight before finishing

You can override the target directory with `ARCHITEC_USER_CONFIG_DIR`.

For non-interactive installs, provide the values up front:

```bash
architec_llm_main_url=https://your-llm-endpoint \
architec_llm_main_api_key=your_api_key \
./install.sh
```

If you want to install with pip manually, you still need to create LLM config yourself:

```bash
python3 -m pip install -e .
```

Runtime config lookup now prefers:

1. project override under `.architec/`
2. user-global config under `~/.architec/`
3. repo/package defaults under `config/`

Validate end-to-end from a project that already has Hippo inputs:

```bash
architec --check .
architec --refresh-from-hippo --check .
```

The installer already runs backend LLM preflight without requiring `.hippocampus/`.

## Usage

Detailed manual:

- `docs/usage-manual.md`

Full analysis:

```bash
architec .
architec --goal "analyze architecture stability" .
```

Diff analysis:

```bash
architec --diff .
architec --diff --base main --head HEAD .
```

Refresh Hippo bundle first:

```bash
architec --refresh-from-hippo .
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
  `hippo init`, `hippo sig-extract`, `hippo index --no-llm`, `hippo structure-prompt --no-llm-enhance`,
  then `architec/tools/collect_repo_metrics.py`.
- `architec` does not perform automatic repair loops.
