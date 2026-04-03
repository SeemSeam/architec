from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .auth import auto_login, handle_auth_command, require_authorized_session
from .auth.guard import ArchitecAuthRequiredError
from .analysis.public import run_analysis
from .baseline.public import run_baseline
from .cleanup.public import run_cleanup
from .cleanup.autofix import run_autofix
from .gate.public import run_gate
from .integration.bundle_loader import inspect_bundle
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

    cleanup = result.get("cleanup", {}) if isinstance(result.get("cleanup"), dict) else {}
    if cleanup:
        candidate_total = int(cleanup.get("candidate_total", 0) or 0)
        review_required = int(cleanup.get("review_required_total", 0) or 0)
        lines.append(f"Cleanup: candidates={candidate_total} | review_required={review_required}")
        owner_total = int(cleanup.get("owner_total", 0) or 0)
        ttl_total = int(cleanup.get("ttl_total", 0) or 0)
        expires_total = int(cleanup.get("expires_total", 0) or 0)
        expired_total = int(cleanup.get("expired_total", 0) or 0)
        if owner_total or ttl_total or expires_total or expired_total:
            lines.append(
                "Cleanup metadata: "
                f"owner={owner_total} | ttl={ttl_total} | "
                f"expires_at={expires_total} | expired={expired_total}"
            )
        by_category = cleanup.get("by_category", {})
        if isinstance(by_category, dict) and by_category:
            rendered = ", ".join(f"{key}={value}" for key, value in sorted(by_category.items()))
            lines.append(f"Cleanup categories: {rendered}")
    archive_candidates = result.get("archive_candidates", {}) if isinstance(result.get("archive_candidates"), dict) else {}
    if archive_candidates:
        candidate_total = int(archive_candidates.get("candidate_total", 0) or 0)
        ready_total = int(archive_candidates.get("ready_total", 0) or 0)
        review_total = int(archive_candidates.get("review_total", 0) or 0)
        lines.append(f"Archive: candidates={candidate_total} | ready={ready_total} | review={review_total}")
    semantic_judge = result.get("semantic_judge", {}) if isinstance(result.get("semantic_judge"), dict) else {}
    if semantic_judge:
        status = str(semantic_judge.get("status", "") or "skipped").strip()
        if status == "ok":
            reviewed_total = int(semantic_judge.get("reviewed_total", 0) or 0)
            by_decision = semantic_judge.get("by_decision", {})
            rendered = (
                " | ".join(f"{key}={value}" for key, value in sorted(by_decision.items()))
                if isinstance(by_decision, dict) and by_decision
                else ""
            )
            line = f"Semantic judge: reviewed={reviewed_total}"
            if rendered:
                line += f" | {rendered}"
            lines.append(line)
        elif status != "skipped":
            lines.append(f"Semantic judge: status={status}")
    autofix = result.get("autofix", {}) if isinstance(result.get("autofix"), dict) else {}
    if autofix:
        line = (
            f"Autofix: status={str(autofix.get('status', '') or 'noop')} | "
            f"actions={int(autofix.get('action_total', 0) or 0)} | "
            f"applied={int(autofix.get('applied_total', 0) or 0)}"
        )
        blocked_total = int(autofix.get("blocked_total", 0) or 0)
        skipped_total = int(autofix.get("skipped_total", 0) or 0)
        if blocked_total > 0:
            line += f" | blocked={blocked_total}"
        if skipped_total > 0:
            line += f" | skipped={skipped_total}"
        lines.append(line)

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
    cleanup_inventory = str(artifacts.get("cleanup_inventory_json", "") or "").strip()
    cleanup_summary = str(artifacts.get("cleanup_summary_md", "") or "").strip()
    cleanup_ledger = str(artifacts.get("cleanup_ledger_json", "") or "").strip()
    archive_candidates_json = str(artifacts.get("archive_candidates_json", "") or "").strip()
    archive_summary = str(artifacts.get("archive_summary_md", "") or "").strip()
    semantic_judge_json = str(artifacts.get("semantic_judge_json", "") or "").strip()
    semantic_judge_summary = str(artifacts.get("semantic_judge_summary_md", "") or "").strip()
    autofix_plan_json = str(artifacts.get("autofix_plan_json", "") or "").strip()
    autofix_summary = str(artifacts.get("autofix_summary_md", "") or "").strip()
    baseline_json = str(artifacts.get("baseline_json", "") or "").strip()
    baseline_summary = str(artifacts.get("baseline_summary_md", "") or "").strip()
    gate_json = str(artifacts.get("gate_json", "") or "").strip()
    gate_summary = str(artifacts.get("gate_summary_md", "") or "").strip()
    if (
        summary_md
        or viz_html
        or analysis_json
        or cleanup_inventory
        or cleanup_ledger
        or cleanup_summary
        or archive_candidates_json
        or archive_summary
        or semantic_judge_json
        or semantic_judge_summary
        or autofix_plan_json
        or autofix_summary
        or baseline_json
        or baseline_summary
        or gate_json
        or gate_summary
    ):
        lines.append("Artifacts:")
        if summary_md:
            lines.append(f"- summary: {summary_md}")
        if viz_html:
            lines.append(f"- viz: {viz_html}")
        if analysis_json:
            lines.append(f"- json: {analysis_json}")
        if cleanup_inventory:
            lines.append(f"- cleanup inventory: {cleanup_inventory}")
        if cleanup_ledger:
            lines.append(f"- cleanup ledger: {cleanup_ledger}")
        if cleanup_summary:
            lines.append(f"- cleanup summary: {cleanup_summary}")
        if archive_candidates_json:
            lines.append(f"- archive candidates: {archive_candidates_json}")
        if archive_summary:
            lines.append(f"- archive summary: {archive_summary}")
        if semantic_judge_json:
            lines.append(f"- semantic judge: {semantic_judge_json}")
        if semantic_judge_summary:
            lines.append(f"- semantic judge summary: {semantic_judge_summary}")
        if autofix_plan_json:
            lines.append(f"- autofix plan: {autofix_plan_json}")
        if autofix_summary:
            lines.append(f"- autofix summary: {autofix_summary}")
        if baseline_json:
            lines.append(f"- baseline json: {baseline_json}")
        if baseline_summary:
            lines.append(f"- baseline summary: {baseline_summary}")
        if gate_json:
            lines.append(f"- gate json: {gate_json}")
        if gate_summary:
            lines.append(f"- gate summary: {gate_summary}")
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
    parser = argparse.ArgumentParser(
        prog='archi',
        description='Archi analysis CLI',
        epilog='Maintenance commands: `archi update` and `archi uninstall`.',
    )
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
        help='force-refresh Hippo bundle before analysis',
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


def build_cleanup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi cleanup', description='Archi cleanup CLI')
    _add_argument(
        parser,
        '--out',
        default='',
        help='optional output JSON path override',
    )
    _add_argument(parser, 'path', nargs='?', default='.', help='project root')
    return parser


def build_autofix_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi autofix', description='Archi autofix CLI')
    _add_argument(
        parser,
        '--out',
        default='',
        help='optional output JSON path override',
    )
    _add_argument(
        parser,
        '--apply',
        action='store_true',
        help='execute safe archive-move actions instead of dry-run only',
    )
    _add_argument(parser, 'path', nargs='?', default='.', help='project root')
    return parser


def build_baseline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi baseline', description='Archi baseline CLI')
    _add_argument(
        parser,
        '--out',
        default='',
        help='optional output JSON path override',
    )
    _add_argument(
        parser,
        '--refresh-from-hippo',
        action='store_true',
        help='force-refresh Hippo bundle before baseline capture',
    )
    _add_argument(
        parser,
        '--skip-auth',
        action='store_true',
        help='development-only bypass for local auth gate',
    )
    _add_argument(parser, 'path', nargs='?', default='.', help='project root')
    return parser


def build_gate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi gate', description='Archi gate CLI')
    _add_argument(
        parser,
        '--out',
        default='',
        help='optional output JSON path override',
    )
    _add_argument(
        parser,
        '--refresh-from-hippo',
        action='store_true',
        help='force-refresh Hippo bundle before gate evaluation',
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
    status = inspect_bundle(args.path)
    if status.missing_files:
        emit_progress("archi [1/3] Hippo bundle missing, refreshing via hippo")
        return refresh_bundle_from_hippo(args.path)
    if status.stale_reasons:
        emit_progress("archi [1/3] Hippo bundle stale, refreshing via hippo")
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


def _cleanup_result(args: argparse.Namespace) -> dict[str, Any]:
    emit_progress("archi cleanup [1/1] running cleanup scan")
    return run_cleanup(args.path, llm_enabled=True)


def _autofix_result(args: argparse.Namespace) -> dict[str, Any]:
    emit_progress("archi autofix [1/1] deriving autofix actions")
    return run_autofix(
        args.path,
        apply=bool(args.apply),
        llm_enabled=True,
    )


def _baseline_result(args: argparse.Namespace) -> dict[str, Any]:
    emit_progress("archi [3/3] capturing baseline snapshot")
    return run_baseline(
        args.path,
        progress=emit_progress,
    )


def _gate_result(args: argparse.Namespace) -> dict[str, Any]:
    emit_progress("archi [3/3] evaluating gate against baseline")
    return run_gate(
        args.path,
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
        argv = sys.argv[1:]
        self_manage_result = handle_self_manage_command(argv)
        if self_manage_result is not None:
            return self_manage_result
        auth_result = handle_auth_command(argv)
        if auth_result is not None:
            return auth_result
        if argv and argv[0] == 'cleanup':
            parser = build_cleanup_parser()
            args = parser.parse_args(argv[1:])
            result = _cleanup_result(args)
            _emit(
                result,
                args.out or None,
                output_format='all',
                check_mode=False,
            )
            return 0
        if argv and argv[0] == 'autofix':
            parser = build_autofix_parser()
            args = parser.parse_args(argv[1:])
            result = _autofix_result(args)
            _emit(
                result,
                args.out or None,
                output_format='all',
                check_mode=False,
            )
            return 0
        if argv and argv[0] == 'baseline':
            parser = build_baseline_parser()
            args = parser.parse_args(argv[1:])
            if not bool(args.skip_auth):
                _ensure_authorized_access()
            refresh_result = _ensure_bundle(args)
            checks = _required_llm_checks(diff=False, goal="")
            emit_progress("archi [2/3] checking backend LLM configuration")
            preflight_backend_llm(args.path, checks=checks)
            result = _baseline_result(args)
            result = _with_refresh_result(
                result,
                refresh_result=refresh_result,
                check_mode=False,
            )
            _emit(
                result,
                args.out or None,
                output_format='all',
                check_mode=False,
            )
            return 0
        if argv and argv[0] == 'gate':
            parser = build_gate_parser()
            args = parser.parse_args(argv[1:])
            if not bool(args.skip_auth):
                _ensure_authorized_access()
            refresh_result = _ensure_bundle(args)
            checks = _required_llm_checks(diff=False, goal="")
            emit_progress("archi [2/3] checking backend LLM configuration")
            preflight_backend_llm(args.path, checks=checks)
            result = _gate_result(args)
            result = _with_refresh_result(
                result,
                refresh_result=refresh_result,
                check_mode=False,
            )
            _emit(
                result,
                args.out or None,
                output_format='all',
                check_mode=False,
            )
            return 0
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
