# Repository Guidelines

## Project Structure & Module Organization

`architec` is a Python 3.11 CLI package under `src/architec/`. Keep core analysis, scoring, reporting, and LLM integration logic there. Tests live in `tests/` and follow the runtime module layout (`test_cli_main.py`, `test_backend_llm_json_paths.py`, etc.). User-facing docs are in `docs/`; update `README.md` for install or workflow changes. Default config templates live in `config/`, helper scripts in `tools/`, and prompt assets in `prompts/`.

## Build, Test, and Development Commands

- `python3 -m pip install -e .`: install the package in editable mode for local development only.
- `PYTHONPATH=src pytest -q`: run the full test suite.
- `PYTHONPATH=src pytest -q tests/test_cli_main.py`: run a focused test module.
- `PYTHONPATH=src python3 -m architec --check .`: validate bundle + LLM configuration.
- `PYTHONPATH=src python3 -m architec --refresh-from-hippo .`: refresh Hippo inputs and run a full analysis.

## Coding Style & Naming Conventions

Follow existing Python style: 4-space indentation, type hints on public functions, and small helper functions over long branch-heavy blocks. Use `snake_case` for modules, functions, and test names; use `PascalCase` for dataclasses and config objects. Prefer ASCII unless the file already uses non-ASCII. There is no enforced formatter in this repo today, so match surrounding style and keep changes minimal and readable.

## Testing Guidelines

Tests use `pytest`. Name files `test_*.py` and keep test names behavior-focused, for example `test_complete_json_reuses_cache_for_same_prompt`. Add or update targeted tests for any scoring, CLI, LLM config, or Hippo refresh change. Before opening a PR, run `PYTHONPATH=src pytest -q` and mention the result.

## Commit & Pull Request Guidelines

Use short imperative commit messages, capitalized like the existing history: `Refine architec scoring, config, and progress output`. Keep one logical change per commit when possible. PRs should include a brief summary, affected commands or config paths, test evidence, and any output artifact changes. Include screenshots only when changing generated HTML or visualization behavior.

## Security & Configuration Tips

Do not commit API keys or per-user config. Runtime config is expected under `~/.architec/` or a project-local `.architec/` override. Treat `.hippocampus/` as input data and `.architec/` as generated output; avoid checking generated files into commits unless the change specifically updates reference artifacts.
