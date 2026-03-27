from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .auth import auto_login, handle_auth_command, require_authorized_session
from .auth.guard import ArchitecAuthRequiredError
from .analysis.public import run_analysis
from .integration.bundle_loader import require_bundle
from .integration.hippo_bridge import refresh_bundle_from_hippo
from .self_manage import handle_self_manage_command, print_version_status
from .support.io_utils import emit_progress, write_json
from .support.llm_guard import ArchitectLLMUnavailableError
from .support.llm_preflight import preflight_backend_llm


def _score_line(scores: dict[str, Any]) -> str:
    parts: list[str] = []
    for label, key in (
        ("overall", "overall"),
        ("governance", "governance_overall"),
        ("structure", "structure"),
        ("full", "full"),
        ("incremental", "incremental"),
    ):
        value = scores.get(key)
        if value is None:
            continue
        parts.append(f"{label}={value}")
    return " | ".join(parts)


def _summary_lines(result: dict[str, Any], *, check_mode: bool) -> list[str]:
    lines: list[str] = []
    if check_mode:
        lines.append("Archi preflight OK")
        checked_path = str(result.get("checked_path", "") or "").strip()
        if checked_path:
            lines.append(f"Path: {checked_path}")
        checks = result.get("checks", [])
        if isinstance(checks, list) and checks:
            rendered = []
            for item in checks:
                if not isinstance(item, dict):
                    continue
                task = str(item.get("task", "") or "").strip()
                tier = str(item.get("tier", "") or "").strip()
                if task and tier:
                    rendered.append(f"{task}({tier})")
                elif task:
                    rendered.append(task)
            if rendered:
                lines.append(f"LLM checks: {', '.join(rendered)}")
        refresh = result.get("refresh")
        if isinstance(refresh, dict) and refresh:
            lines.append("Hippo bundle: refreshed")
        return lines

    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    scores = result.get("scores", {}) if isinstance(result.get("scores"), dict) else {}
    recommendations = result.get("recommendations", [])
    artifacts = result.get("artifacts", {}) if isinstance(result.get("artifacts"), dict) else {}

    headline = str(summary.get("headline", "") or "").strip() or "Archi analysis complete"
    lines.append(headline)

    score_line = _score_line(scores)
    if score_line:
        lines.append(f"Scores: {score_line}")

    executive_summary = str(summary.get("executive_summary", "") or "").strip()
    if executive_summary:
        lines.append(f"Summary: {executive_summary}")

    takeaways = summary.get("top_takeaways", [])
    if isinstance(takeaways, list):
        for item in takeaways[:3]:
            text = str(item or "").strip()
            if text:
                lines.append(f"- {text}")

    if isinstance(recommendations, list) and recommendations:
        lines.append("Top improvements:")
        for item in recommendations[:5]:
            if not isinstance(item, dict):
                continue
            priority = str(item.get("priority", "") or "").strip()
            title = str(item.get("title", "") or "").strip()
            why = str(item.get("why", "") or "").strip()
            prefix = f"{priority} " if priority else ""
            if title and why:
                lines.append(f"- {prefix}{title}: {why}")
            elif title:
                lines.append(f"- {prefix}{title}")

    summary_md = str(artifacts.get("summary_md", "") or "").strip()
    viz_html = str(artifacts.get("viz_html", "") or "").strip()
    analysis_json = str(artifacts.get("analysis_json", "") or "").strip()
    if summary_md or viz_html or analysis_json:
        lines.append("Artifacts:")
        if summary_md:
            lines.append(f"- summary: {summary_md}")
        if viz_html:
            lines.append(f"- viz: {viz_html}")
        if analysis_json:
            lines.append(f"- json: {analysis_json}")
    return lines


def _emit(
    result: dict[str, Any],
    out: str | None,
    *,
    output_format: str,
    check_mode: bool,
) -> None:
    del output_format
    if out:
        write_json(Path(out).resolve(), result)
    print("\n".join(_summary_lines(result, check_mode=check_mode)))


def _required_llm_checks(*, diff: bool, goal: str) -> list[tuple[str, str]]:
    checks: list[tuple[str, str]] = [
        ('architect_history', 'strong'),
        ('architec_summary', 'strong'),
        ('architect_folder_naming', 'weak'),
        ('architect_topology_review', 'weak'),
    ]
    if diff:
        checks.append(('architect_component_scoring', 'weak'))
    if goal:
        checks.append(('architect_feature', 'strong'))
    return checks


def _add_argument(parser: argparse.ArgumentParser, *args: str, **kwargs: Any) -> None:
    parser.add_argument(*args, **kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi', description='Archi analysis CLI')
    _add_argument(
        parser,
        '--version',
        action='store_true',
        help='show current CLI version and latest release status',
    )
    _add_argument(parser, '--goal', default='', help='analysis goal / intent')
    _add_argument(
        parser,
        '--diff',
        action='store_true',
        help='run incremental git diff analysis',
    )
    _add_argument(parser, '--base', default='', help='git base ref (only with --diff)')
    _add_argument(parser, '--head', default='', help='git head ref (only with --diff)')
    _add_argument(parser, '--component', default='', help='reserved component hint')
    _add_argument(
        parser,
        '--format',
        default='all',
        choices=['json', 'md', 'html', 'all'],
        help='preferred output format',
    )
    _add_argument(
        parser,
        '--refresh-from-hippo',
        action='store_true',
        help='validate existing Hippo bundle; refresh hook reserved for follow-up',
    )
    _add_argument(
        parser,
        '--open-browser',
        action='store_true',
        help='reserved flag; current implementation only generates HTML',
    )
    _add_argument(
        parser,
        '--check',
        action='store_true',
        help='validate backend LLM config and exit',
    )
    _add_argument(
        parser,
        '--out',
        default='',
        help='optional output JSON path override',
    )
    _add_argument(
        parser,
        '--skip-auth',
        action='store_true',
        help='development-only bypass for local auth gate',
    )
    _add_argument(parser, 'path', nargs='?', default='.', help='project root')
    return parser


def _preflight_result(path: str, checks: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        'ok': True,
        'checked_path': str(Path(path).resolve()),
        'checks': [{'task': task, 'tier': tier} for task, tier in checks],
    }


def _ensure_bundle(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.refresh_from_hippo:
        emit_progress("archi [1/3] refreshing Hippo bundle")
        return refresh_bundle_from_hippo(args.path)
    emit_progress("archi [1/3] validating existing Hippo bundle")
    try:
        require_bundle(args.path)
    except FileNotFoundError:
        emit_progress("archi [1/3] Hippo bundle missing, refreshing via hippo")
        return refresh_bundle_from_hippo(args.path)
    return None


def _checked_result(args: argparse.Namespace, checks: list[tuple[str, str]]) -> dict[str, Any]:
    emit_progress("archi [3/3] preflight complete")
    return _preflight_result(args.path, checks)


def _analysis_result(args: argparse.Namespace) -> dict[str, Any]:
    emit_progress("archi [3/3] running analysis pipeline")
    return run_analysis(
        args.path,
        goal=str(args.goal or '').strip(),
        diff=bool(args.diff),
        base=str(args.base or '').strip(),
        head=str(args.head or '').strip(),
        progress=emit_progress,
    )


def _validate_args(args: argparse.Namespace) -> int | None:
    if (args.base or args.head) and not args.diff:
        print('--base/--head require --diff', file=sys.stderr)
        return 2
    return None


def _run_command(
    args: argparse.Namespace,
    checks: list[tuple[str, str]],
) -> dict[str, Any]:
    return _checked_result(args, checks) if args.check else _analysis_result(args)


def _interactive_terminal() -> bool:
    streams = (sys.stdin, sys.stdout, sys.stderr)
    return all(getattr(stream, "isatty", lambda: False)() for stream in streams)


def _ensure_authorized_access() -> None:
    try:
        require_authorized_session()
        return
    except ArchitecAuthRequiredError as exc:
        if not _interactive_terminal():
            raise
        print(str(exc), file=sys.stderr)
        print("Authorizing this install in the browser...", file=sys.stderr)
    login_status = auto_login()
    if login_status != 0:
        raise ArchitecAuthRequiredError("Browser authorization did not complete.")
    require_authorized_session()


def _with_refresh_result(
    result: dict[str, Any],
    *,
    refresh_result: dict[str, Any] | None,
    check_mode: bool,
) -> dict[str, Any]:
    if refresh_result is None:
        return result
    key = 'refresh' if check_mode else 'bundle_refresh'
    result[key] = refresh_result
    return result


def main() -> int:
    try:
        self_manage_result = handle_self_manage_command(sys.argv[1:])
        if self_manage_result is not None:
            return self_manage_result
        auth_result = handle_auth_command(sys.argv[1:])
        if auth_result is not None:
            return auth_result
        parser = build_parser()
        args = parser.parse_args()
        if bool(args.version):
            return print_version_status()
        invalid = _validate_args(args)
        if invalid is not None:
            return invalid
        if not bool(args.skip_auth):
            _ensure_authorized_access()
        refresh_result = _ensure_bundle(args)
        checks = _required_llm_checks(diff=bool(args.diff), goal=str(args.goal or ''))
        emit_progress("archi [2/3] checking backend LLM configuration")
        preflight_backend_llm(args.path, checks=checks)
        result = _run_command(args, checks)
        result = _with_refresh_result(
            result,
            refresh_result=refresh_result,
            check_mode=bool(args.check),
        )
        _emit(
            result,
            args.out or None,
            output_format=str(args.format or "all"),
            check_mode=bool(args.check),
        )
        return 0
    except ArchitecAuthRequiredError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ArchitectLLMUnavailableError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
