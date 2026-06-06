from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Sequence


INTERNAL_HIPPOS_COMMAND = "__architec_run_hippos"
INTERNAL_COLLECT_METRICS_COMMAND = "__architec_collect_repo_metrics"


def is_frozen_binary() -> bool:
    return bool(getattr(sys, "frozen", False))


def frozen_hippos_command() -> list[str]:
    return [sys.executable, INTERNAL_HIPPOS_COMMAND]


def frozen_collect_metrics_command() -> list[str]:
    return [sys.executable, INTERNAL_COLLECT_METRICS_COMMAND]


def _system_exit_code(exc: SystemExit) -> int:
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    print(exc.code, file=sys.stderr)
    return 1


def run_bundled_hippos(args: Sequence[str]) -> int:
    try:
        from hippos.cli import cli
    except Exception as exc:
        print(f"bundled Hippos runtime is unavailable: {exc}", file=sys.stderr)
        return 2

    try:
        cli(args=list(args), prog_name="hippos")
    except SystemExit as exc:
        return _system_exit_code(exc)
    return 0


def run_bundled_collect_metrics(args: Sequence[str]) -> int:
    from architec.integration.resource_paths import tool_script_path

    script_path = tool_script_path("collect_repo_metrics.py")
    tools_dir = str(script_path.parent)
    inserted = False
    old_argv = sys.argv[:]
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
        inserted = True
    sys.argv = [str(script_path), *list(args)]
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        return _system_exit_code(exc)
    finally:
        sys.argv = old_argv
        if inserted:
            try:
                sys.path.remove(tools_dir)
            except ValueError:
                pass
    return 0


def dispatch_internal_command(argv: Sequence[str]) -> int | None:
    if not argv:
        return None
    command = argv[0]
    if command == INTERNAL_HIPPOS_COMMAND:
        return run_bundled_hippos(argv[1:])
    if command == INTERNAL_COLLECT_METRICS_COMMAND:
        return run_bundled_collect_metrics(argv[1:])
    return None
