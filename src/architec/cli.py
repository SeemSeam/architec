from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .advice_feedback import load_advice_feedback
from .auth import auto_login, handle_auth_command, require_authorized_session
from .auth.guard import ArchitecAuthRequiredError
from .code_review.public import (
    run_code_review_diff,
    run_code_review_full,
    run_code_review_incremental_llm,
    run_code_review_since,
    run_code_review_static_diff,
    run_code_review_static_full,
    run_code_review_static_since,
)
from .fix_advice.public import run_fix_advice
from .integration.bundle_loader import inspect_bundle
from .integration.hippo_bridge import refresh_bundle_from_hippo
from .plan_review.public import run_plan_review
from .project_status.public import run_status_snapshot, run_status_trend
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


def _code_review_count_line(summary: dict[str, Any]) -> str:
    parts: list[str] = []
    for label, key in (
        ("total", "concern_total"),
        ("shown", "top_concern_total"),
        ("limit", "concern_limit"),
    ):
        if key in summary:
            parts.append(f"{label}={summary.get(key)}")
    return " | ".join(parts)


def _format_concern_line(concern: dict[str, Any]) -> str:
    kind = str(concern.get("kind", "") or "concern").strip()
    level = str(concern.get("level", "") or "").strip()
    location = concern.get("location", {}) if isinstance(concern.get("location"), dict) else {}
    path = str(location.get("path", "") or "unknown path").strip()
    root_cause = str(concern.get("root_cause", "") or "").strip()
    prefix = f"{kind} [{level}]" if level else kind
    if root_cause:
        return f"- {prefix} {path}: {root_cause}"
    return f"- {prefix} {path}"


def _append_code_review_summary(lines: list[str], result: dict[str, Any], summary: dict[str, Any]) -> None:
    count_line = _code_review_count_line(summary)
    if count_line:
        lines.append(f"Concerns: {count_line}")

    signals = result.get("signals", [])
    if isinstance(signals, list) and signals:
        lines.append("Signals:")
        for signal in signals[:5]:
            if not isinstance(signal, dict):
                continue
            kind = str(signal.get("kind", "") or "").strip()
            text = str(signal.get("summary", "") or "").strip()
            if kind and text:
                lines.append(f"- {kind}: {text}")
            elif kind:
                lines.append(f"- {kind}")

    concerns = result.get("concerns", [])
    if isinstance(concerns, list) and concerns:
        lines.append("Top concerns:")
        for concern in concerns[:5]:
            if isinstance(concern, dict):
                lines.append(_format_concern_line(concern))


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

    if str(result.get("mode", "") or "") == "code_review":
        _append_code_review_summary(lines, result, summary)

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


def _emit_json(result: dict[str, Any], out: str | None) -> None:
    if out:
        write_json(Path(out).resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _required_llm_checks(*, diff: bool) -> list[tuple[str, str]]:
    del diff
    return [
        ('architect_history', 'strong'),
        ('architec_summary', 'strong'),
        ('architect_folder_naming', 'weak'),
        ('architect_topology_review', 'weak'),
    ]


def _incremental_llm_checks() -> list[tuple[str, str]]:
    return [('architec_summary', 'strong')]


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
    _add_argument(
        parser,
        '--full',
        action='store_true',
        help='run full project LLM architecture review',
    )
    _add_argument(
        parser,
        '--diff',
        action='store_true',
        help='compatibility alias for default incremental review',
    )
    _add_argument(parser, '--base', default='', help='git base ref (only with --diff)')
    _add_argument(parser, '--head', default='', help='git head ref (only with --diff)')
    _add_argument(
        parser,
        '--plan-review',
        default='',
        metavar='PLAN_JSON',
        help='optional plan-review JSON for diff consistency observations (only with --diff)',
    )
    _add_argument(
        parser,
        '--risk-context',
        default='',
        metavar='RISK_JSON',
        help='optional external risk context JSON for code-review concerns',
    )
    _add_argument(
        parser,
        '--advice-feedback',
        default='',
        metavar='FEEDBACK_JSON',
        help='optional reviewer feedback JSON for full-review recommendations',
    )
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

def build_plan_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi plan-review', description='Archi plan review CLI')
    _add_argument(
        parser,
        '--out',
        default='',
        help='optional output JSON path override',
    )
    _add_argument(
        parser,
        '--project-root',
        default='.',
        help='project root used for result context',
    )
    _add_argument(parser, 'plan', help='Markdown plan file')
    return parser


def build_code_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi code-review', description='Archi code review CLI')
    mode = parser.add_mutually_exclusive_group(required=True)
    _add_argument(
        mode,
        '--full',
        action='store_true',
        help='run full project code review',
    )
    _add_argument(
        mode,
        '--diff',
        action='store_true',
        help='run current diff code review',
    )
    _add_argument(
        mode,
        '--since',
        default='',
        metavar='REF',
        help='run code review for changes since ref',
    )
    _add_argument(parser, '--base', default='', help='git base ref (only with --diff)')
    _add_argument(parser, '--head', default='', help='git head ref (only with --diff)')
    _add_argument(
        parser,
        '--plan-review',
        default='',
        metavar='PLAN_JSON',
        help='optional plan-review JSON for diff/since consistency observations',
    )
    _add_argument(
        parser,
        '--risk-context',
        default='',
        metavar='RISK_JSON',
        help='optional external risk context JSON for code-review concerns',
    )
    _add_argument(
        parser,
        '--advice-feedback',
        default='',
        metavar='FEEDBACK_JSON',
        help='optional reviewer feedback JSON for full-review recommendations',
    )
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
        help='force-refresh Hippo bundle before code review',
    )
    _add_argument(
        parser,
        '--skip-auth',
        action='store_true',
        help='development-only bypass for local auth gate',
    )
    _add_argument(parser, 'path', nargs='?', default='.', help='project root')
    return parser

def build_status_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi status', description='Archi project status CLI')
    mode = parser.add_mutually_exclusive_group(required=True)
    _add_argument(mode, '--trend', action='store_true', help='show advisory project trend')
    _add_argument(mode, '--snapshot', action='store_true', help='write advisory project status snapshot')
    _add_argument(
        parser,
        '--out',
        default='',
        help='optional output JSON path override',
    )
    _add_argument(parser, 'path', nargs='?', default='.', help='project root')
    return parser


def build_fix_advice_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='archi fix-advice', description='Archi fix advice CLI')
    review_group = parser.add_mutually_exclusive_group(required=True)
    review_group.add_argument('--review', dest='review', help='review JSON file to read')
    review_group.add_argument('--for', dest='review', help='compatibility alias for --review')
    _add_argument(parser, '--focus-file', default='', help='only include concerns whose path contains this text')
    _add_argument(parser, '--focus-kind', default='', help='only include concerns of this kind')
    _add_argument(parser, '--concern-id', default='', help='only include one concern id')
    _add_argument(parser, '--advice-feedback', default='', metavar='FEEDBACK_JSON', help='optional reviewer feedback JSON')
    _add_argument(parser, '--out', default='', help='optional output JSON path override')
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


def _plan_review_result(args: argparse.Namespace) -> dict[str, Any]:
    emit_progress("archi plan-review [1/1] reading plan")
    return run_plan_review(
        args.plan,
        project_root=args.project_root,
    )


def _code_review_result(args: argparse.Namespace) -> dict[str, Any]:
    since_ref = str(args.since or "").strip()
    plan_review_path = str(getattr(args, "plan_review", "") or "").strip()
    risk_context_path = str(getattr(args, "risk_context", "") or "").strip()
    advice_feedback_path = str(getattr(args, "advice_feedback", "") or "").strip()
    if since_ref:
        emit_progress("archi code-review [3/3] running since code review")
        kwargs: dict[str, Any] = {"ref": since_ref, "progress": emit_progress}
        if plan_review_path:
            kwargs["plan_review_path"] = plan_review_path
        if risk_context_path:
            kwargs["risk_context_path"] = risk_context_path
        return run_code_review_since(
            args.path,
            **kwargs,
        )
    if bool(args.diff):
        emit_progress("archi code-review [3/3] running diff code review")
        kwargs = {
            "base": str(args.base or "").strip(),
            "head": str(args.head or "").strip(),
            "progress": emit_progress,
        }
        if plan_review_path:
            kwargs["plan_review_path"] = plan_review_path
        if risk_context_path:
            kwargs["risk_context_path"] = risk_context_path
        return run_code_review_diff(
            args.path,
            **kwargs,
        )
    emit_progress("archi code-review [3/3] running full code review")
    kwargs = {"progress": emit_progress}
    if risk_context_path:
        kwargs["risk_context_path"] = risk_context_path
    if advice_feedback_path:
        kwargs["advice_feedback_path"] = advice_feedback_path
    return run_code_review_full(args.path, **kwargs)


def _is_full_code_review_args(args: argparse.Namespace) -> bool:
    return (
        not bool(getattr(args, "check", False))
        and bool(getattr(args, "full", False))
        and not bool(getattr(args, "diff", False))
        and not str(getattr(args, "since", "") or "").strip()
    )


def _should_ensure_bundle(args: argparse.Namespace) -> bool:
    return (
        bool(getattr(args, "check", False))
        or bool(getattr(args, "full", False))
        or bool(getattr(args, "refresh_from_hippo", False))
    )


def _static_full_code_review_result(args: argparse.Namespace, reason: str) -> dict[str, Any]:
    emit_progress("archi code-review [3/3] running static full code review")
    kwargs: dict[str, Any] = {
        "reason": reason,
        "progress": emit_progress,
    }
    risk_context_path = str(getattr(args, "risk_context", "") or "").strip()
    if risk_context_path:
        kwargs["risk_context_path"] = risk_context_path
    advice_feedback_path = str(getattr(args, "advice_feedback", "") or "").strip()
    if advice_feedback_path:
        kwargs["advice_feedback_path"] = advice_feedback_path
    return run_code_review_static_full(args.path, **kwargs)


def _static_incremental_code_review_result(args: argparse.Namespace, reason: str) -> dict[str, Any]:
    since_ref = str(getattr(args, "since", "") or "").strip()
    if since_ref:
        emit_progress("archi code-review [3/3] running static since code review")
        kwargs: dict[str, Any] = {
            "ref": since_ref,
            "reason": reason,
            "progress": emit_progress,
        }
        plan_review_path = str(getattr(args, "plan_review", "") or "").strip()
        if plan_review_path:
            kwargs["plan_review_path"] = plan_review_path
        risk_context_path = str(getattr(args, "risk_context", "") or "").strip()
        if risk_context_path:
            kwargs["risk_context_path"] = risk_context_path
        return run_code_review_static_since(args.path, **kwargs)
    emit_progress("archi code-review [3/3] running static diff code review")
    kwargs = {
        "base": str(getattr(args, "base", "") or "").strip(),
        "head": str(getattr(args, "head", "") or "").strip(),
        "reason": reason,
        "progress": emit_progress,
    }
    plan_review_path = str(getattr(args, "plan_review", "") or "").strip()
    if plan_review_path:
        kwargs["plan_review_path"] = plan_review_path
    risk_context_path = str(getattr(args, "risk_context", "") or "").strip()
    if risk_context_path:
        kwargs["risk_context_path"] = risk_context_path
    return run_code_review_static_diff(args.path, **kwargs)


def _static_code_review_result(args: argparse.Namespace, reason: str) -> dict[str, Any]:
    if _is_full_code_review_args(args):
        return _static_full_code_review_result(args, reason)
    return _static_incremental_code_review_result(args, reason)


def _availability_reason(prefix: str, exc: Exception) -> str:
    detail = str(exc).strip()
    for source, replacement in (
        ("failed", "unavailable"),
        ("failure", "unavailable"),
        ("fail", "unavailable"),
    ):
        detail = detail.replace(source, replacement).replace(source.title(), replacement.title())
    return f"{prefix}: {detail}" if detail else prefix


def _status_result(args: argparse.Namespace) -> dict[str, Any]:
    if bool(args.snapshot):
        emit_progress("archi status [1/1] writing advisory status snapshot")
        return run_status_snapshot(args.path)
    emit_progress("archi status [1/1] reading advisory status trend")
    return run_status_trend(args.path)


def _fix_advice_result(args: argparse.Namespace) -> dict[str, Any]:
    emit_progress("archi fix-advice [1/1] reading review")
    return run_fix_advice(
        args.review,
        focus_file=str(args.focus_file or "").strip(),
        focus_kind=str(args.focus_kind or "").strip(),
        concern_id=str(args.concern_id or "").strip(),
        advice_feedback_path=str(getattr(args, "advice_feedback", "") or "").strip() or None,
    )


def _validate_args(args: argparse.Namespace) -> int | None:
    if bool(getattr(args, "full", False)) and bool(getattr(args, "diff", False)):
        print('--full and --diff are mutually exclusive', file=sys.stderr)
        return 2
    if (args.base or args.head) and not args.diff:
        print('--base/--head require --diff', file=sys.stderr)
        return 2
    if getattr(args, "plan_review", "") and bool(args.check):
        print('--plan-review cannot be used with --check', file=sys.stderr)
        return 2
    if getattr(args, "plan_review", "") and bool(getattr(args, "full", False)):
        print('--plan-review requires incremental review', file=sys.stderr)
        return 2
    if getattr(args, "risk_context", "") and bool(args.check):
        print('--risk-context cannot be used with --check', file=sys.stderr)
        return 2
    if getattr(args, "advice_feedback", "") and bool(args.check):
        print('--advice-feedback cannot be used with --check', file=sys.stderr)
        return 2
    if getattr(args, "advice_feedback", "") and not bool(getattr(args, "full", False)):
        print('--advice-feedback currently requires --full', file=sys.stderr)
        return 2
    return None


def _validate_code_review_args(args: argparse.Namespace) -> int | None:
    if (args.base or args.head) and not args.diff:
        print('--base/--head require --diff', file=sys.stderr)
        return 2
    if getattr(args, "plan_review", "") and bool(args.full):
        print('--plan-review requires --diff or --since', file=sys.stderr)
        return 2
    if getattr(args, "advice_feedback", "") and not bool(args.full):
        print('--advice-feedback currently requires --full', file=sys.stderr)
        return 2
    return None


def _validate_advice_feedback_arg(args: argparse.Namespace) -> None:
    path = str(getattr(args, "advice_feedback", "") or "").strip()
    if path:
        load_advice_feedback(path)


_REMOVED_LEGACY_COMMAND_REPLACEMENTS = {
    "cleanup": "archi code-review --full .",
    "autofix": "archi fix-advice --review <review.json>",
    "baseline": "archi status --snapshot",
    "gate": "archi code-review --diff . --out review.json",
}


def _reject_removed_legacy_token(argv: list[str]) -> int | None:
    if not argv:
        return None
    replacement = _REMOVED_LEGACY_COMMAND_REPLACEMENTS.get(argv[0])
    if replacement is None:
        return None
    print(
        f"archi {argv[0]} command parser has been removed; use `{replacement}`.",
        file=sys.stderr,
    )
    return 2


def _is_advisory_status_command(argv: list[str]) -> bool:
    return bool(argv and argv[0] == 'status' and any(arg in {'--trend', '--snapshot'} for arg in argv[1:]))


def _run_command(
    args: argparse.Namespace,
    checks: list[tuple[str, str]],
) -> dict[str, Any]:
    if args.check:
        return _checked_result(args, checks)
    if not bool(getattr(args, "full", False)):
        emit_progress("archi [3/3] running incremental LLM code review")
        kwargs: dict[str, Any] = {
            "base": str(args.base or "").strip(),
            "head": str(args.head or "").strip(),
            "progress": emit_progress,
        }
        plan_review_path = str(getattr(args, "plan_review", "") or "").strip()
        if plan_review_path:
            kwargs["plan_review_path"] = plan_review_path
        risk_context_path = str(getattr(args, "risk_context", "") or "").strip()
        if risk_context_path:
            kwargs["risk_context_path"] = risk_context_path
        return run_code_review_incremental_llm(args.path, **kwargs)
    emit_progress("archi [3/3] running full code review")
    kwargs = {"progress": emit_progress}
    risk_context_path = str(getattr(args, "risk_context", "") or "").strip()
    if risk_context_path:
        kwargs["risk_context_path"] = risk_context_path
    advice_feedback_path = str(getattr(args, "advice_feedback", "") or "").strip()
    if advice_feedback_path:
        kwargs["advice_feedback_path"] = advice_feedback_path
    return run_code_review_full(args.path, **kwargs)


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
        if _is_advisory_status_command(argv):
            parser = build_status_parser()
            args = parser.parse_args(argv[1:])
            result = _status_result(args)
            _emit_json(result, args.out or None)
            return 0
        if argv and argv[0] == 'fix-advice':
            parser = build_fix_advice_parser()
            args = parser.parse_args(argv[1:])
            _validate_advice_feedback_arg(args)
            result = _fix_advice_result(args)
            _emit_json(result, args.out or None)
            return 0
        auth_result = handle_auth_command(argv)
        if auth_result is not None:
            return auth_result
        removed_legacy_result = _reject_removed_legacy_token(argv)
        if removed_legacy_result is not None:
            return removed_legacy_result
        if argv and argv[0] == 'plan-review':
            parser = build_plan_review_parser()
            args = parser.parse_args(argv[1:])
            result = _plan_review_result(args)
            _emit_json(result, args.out or None)
            return 0
        if argv and argv[0] == 'code-review':
            parser = build_code_review_parser()
            args = parser.parse_args(argv[1:])
            invalid = _validate_code_review_args(args)
            if invalid is not None:
                return invalid
            _validate_advice_feedback_arg(args)
            if not bool(args.skip_auth):
                _ensure_authorized_access()
            try:
                refresh_result = _ensure_bundle(args)
            except (FileNotFoundError, RuntimeError) as exc:
                if not _is_full_code_review_args(args):
                    raise
                result = _static_full_code_review_result(
                    args,
                    _availability_reason("Hippo bundle unavailable", exc),
                )
                _emit_json(result, args.out or None)
                return 0
            checks = _required_llm_checks(diff=bool(args.diff or args.since))
            emit_progress("archi [2/3] checking backend LLM configuration")
            try:
                preflight_backend_llm(args.path, checks=checks)
            except ArchitectLLMUnavailableError as exc:
                if bool(getattr(args, "check", False)):
                    raise
                result = _static_code_review_result(
                    args,
                    _availability_reason("Backend LLM unavailable", exc),
                )
                result = _with_refresh_result(
                    result,
                    refresh_result=refresh_result,
                    check_mode=False,
                )
                _emit_json(result, args.out or None)
                return 0
            try:
                result = _code_review_result(args)
            except ArchitectLLMUnavailableError as exc:
                if bool(getattr(args, "check", False)):
                    raise
                result = _static_code_review_result(
                    args,
                    _availability_reason("Backend LLM unavailable", exc),
                )
                result = _with_refresh_result(
                    result,
                    refresh_result=refresh_result,
                    check_mode=False,
                )
            result = _with_refresh_result(
                result,
                refresh_result=refresh_result,
                check_mode=False,
            )
            _emit_json(result, args.out or None)
            return 0
        parser = build_parser()
        args = parser.parse_args()
        if bool(args.version):
            return print_version_status()
        invalid = _validate_args(args)
        if invalid is not None:
            return invalid
        _validate_advice_feedback_arg(args)
        if not bool(args.skip_auth):
            _ensure_authorized_access()
        refresh_result = None
        if _should_ensure_bundle(args):
            try:
                refresh_result = _ensure_bundle(args)
            except (FileNotFoundError, RuntimeError) as exc:
                if not _is_full_code_review_args(args):
                    raise
                result = _static_full_code_review_result(
                    args,
                    _availability_reason("Hippo bundle unavailable", exc),
                )
                _emit(
                    result,
                    args.out or None,
                    output_format=str(args.format or "all"),
                    check_mode=False,
                )
                return 0
        checks = (
            _required_llm_checks(diff=False)
            if bool(args.check) or bool(getattr(args, "full", False))
            else _incremental_llm_checks()
        )
        emit_progress("archi [2/3] checking backend LLM configuration")
        try:
            preflight_backend_llm(args.path, checks=checks)
        except ArchitectLLMUnavailableError as exc:
            if bool(getattr(args, "check", False)):
                raise
            result = _static_code_review_result(
                args,
                _availability_reason("Backend LLM unavailable", exc),
            )
            result = _with_refresh_result(
                result,
                refresh_result=refresh_result,
                check_mode=False,
            )
            _emit(
                result,
                args.out or None,
                output_format=str(args.format or "all"),
                check_mode=False,
            )
            return 0
        try:
            result = _run_command(args, checks)
        except ArchitectLLMUnavailableError as exc:
            if bool(getattr(args, "check", False)):
                raise
            result = _static_code_review_result(
                args,
                _availability_reason("Backend LLM unavailable", exc),
            )
            result = _with_refresh_result(
                result,
                refresh_result=refresh_result,
                check_mode=False,
            )
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
