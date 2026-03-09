from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .analysis_runner import run_analysis
from .bundle_loader import require_bundle
from .hippo_bridge import refresh_bundle_from_hippo
from .io_utils import emit_progress, write_json
from .llm_guard import ArchitectLLMUnavailableError
from .llm_preflight import preflight_backend_llm


def _emit(result: dict[str, Any], out: str | None) -> None:
    if out:
        write_json(Path(out).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _required_llm_checks(*, diff: bool, goal: str) -> list[tuple[str, str]]:
    checks: list[tuple[str, str]] = [
        ('architect_history', 'strong'),
        ('architec_summary', 'strong'),
    ]
    if diff:
        checks.append(('architect_component_scoring', 'small'))
    if goal:
        checks.append(('architect_feature', 'strong'))
    return checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Architec analysis CLI')
    parser.add_argument('--goal', default='', help='analysis goal / intent')
    parser.add_argument('--diff', action='store_true', help='run incremental git diff analysis')
    parser.add_argument('--base', default='', help='git base ref (only with --diff)')
    parser.add_argument('--head', default='', help='git head ref (only with --diff)')
    parser.add_argument('--component', default='', help='reserved component hint')
    parser.add_argument('--format', default='all', choices=['json', 'md', 'html', 'all'], help='preferred output format')
    parser.add_argument('--refresh-from-hippo', action='store_true', help='validate existing Hippo bundle; refresh hook reserved for follow-up')
    parser.add_argument('--open-browser', action='store_true', help='reserved flag; current implementation only generates HTML')
    parser.add_argument('--check', action='store_true', help='validate backend LLM config and exit')
    parser.add_argument('--out', default='', help='optional output JSON path override')
    parser.add_argument('path', nargs='?', default='.', help='project root')
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if (args.base or args.head) and not args.diff:
        print('--base/--head require --diff', file=sys.stderr)
        return 2
    try:
        refresh_result: dict[str, Any] | None = None
        if args.refresh_from_hippo:
            emit_progress("architec [1/3] refreshing Hippo bundle")
            refresh_result = refresh_bundle_from_hippo(args.path)
        else:
            emit_progress("architec [1/3] validating existing Hippo bundle")
            require_bundle(args.path)
        checks = _required_llm_checks(diff=bool(args.diff), goal=str(args.goal or ''))
        emit_progress("architec [2/3] checking backend LLM configuration")
        preflight_backend_llm(args.path, checks=checks)
        if args.check:
            emit_progress("architec [3/3] preflight complete")
            result = {
                'ok': True,
                'checked_path': str(Path(args.path).resolve()),
                'checks': [{'task': task, 'tier': tier} for task, tier in checks],
            }
            if refresh_result is not None:
                result['refresh'] = refresh_result
        else:
            emit_progress("architec [3/3] running analysis pipeline")
            result = run_analysis(
                args.path,
                goal=str(args.goal or '').strip(),
                diff=bool(args.diff),
                base=str(args.base or '').strip(),
                head=str(args.head or '').strip(),
                progress=emit_progress,
            )
            if refresh_result is not None:
                result['bundle_refresh'] = refresh_result
        _emit(result, args.out or None)
        return 0
    except ArchitectLLMUnavailableError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
