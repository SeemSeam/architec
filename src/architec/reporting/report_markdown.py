from __future__ import annotations

from typing import Any

from architec.cleanup.metadata import cleanup_metadata_text


def _report_section(report: dict[str, Any], key: str, expected_type: type) -> Any:
    value = report.get(key, expected_type())
    return value if isinstance(value, expected_type) else expected_type()


def _score_lines(scores: dict[str, Any]) -> list[str]:
    lines = [
        f"- Overall: `{scores.get('overall', 0.0)}`",
        f"- Governance Overall: `{scores.get('governance_overall', scores.get('overall', 0.0))}`",
        f"- Structure: `{scores.get('structure', 0.0)}`",
        f"- Full: `{scores.get('full', 0.0)}`",
    ]
    if scores.get('incremental', None) is not None:
        lines.append(f"- Incremental: `{scores.get('incremental', 0.0)}`")
    return lines


def _item_lines(items: list[dict[str, Any]], *, kind: str) -> list[str]:
    lines: list[str] = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        if kind == 'hotspots':
            lines.append(
                f"- `{item.get('path', '')}` | impact=`{item.get('structure_impact', '')}` | "
                f"{item.get('reason', '')}"
            )
        elif kind == 'components':
            labels = ', '.join(item.get('labels', [])[:3])
            lines.append(
                f"- `{item.get('component', '')}` | risk=`{item.get('risk_score', 0.0)}` | {labels}"
            )
        else:
            lines.append(
                f"- `{item.get('priority', 'P1')}` {item.get('title', '')}: {item.get('why', '')}"
            )
    return lines


def _topology_lines(topology: dict[str, Any]) -> list[str]:
    lines: list[str] = ['', '## Folder Management']
    lines.append(
        f"- Source Root: `{topology.get('source_root', '')}` | flat modules=`{topology.get('flat_file_total', 0)}` | "
        f"subpackage count=`{topology.get('subpackage_total', 0)}` | flatness score=`{topology.get('flatness_score', 0.0)}`"
    )
    migration = (
        topology.get('migration_plan', {})
        if isinstance(topology.get('migration_plan', {}), dict)
        else {}
    )
    if migration:
        lines.append(f"- Migration Plan: {migration.get('summary', '')}")
    placement = (
        topology.get('root_placement_review', {})
        if isinstance(topology.get('root_placement_review', {}), dict)
        else {}
    )
    if placement:
        lines.append(
            f"- Root Placement: misplaced=`{len(placement.get('misplaced_root_files', []))}` | "
            f"review=`{len(placement.get('review_root_files', []))}`"
        )
    lines.extend(_topology_finding_lines(topology))
    lines.extend(_topology_group_lines(topology))
    lines.extend(_topology_move_lines(migration))
    return lines


def _topology_finding_lines(topology: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for finding in topology.get('findings', [])[:3]:
        if not isinstance(finding, dict):
            continue
        lines.append(
            f"- `{finding.get('severity', 'info')}` `{finding.get('kind', '')}`: {finding.get('detail', '')}"
        )
    return lines


def _topology_group_lines(topology: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for group in topology.get('groups', [])[:4]:
        if not isinstance(group, dict):
            continue
        naming = (
            group.get('naming_review', {})
            if isinstance(group.get('naming_review'), dict)
            else {}
        )
        target = str(
            naming.get('recommended_name', '')
            or group.get('programmatic_name', '')
            or ''
        )
        lines.append(
            f"- Group `{group.get('group_id', '')}` -> folder `{target}` | files=`{group.get('file_count', 0)}` | "
            f"status=`{group.get('status', '')}`"
        )
    return lines


def _topology_move_lines(migration: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for move in migration.get('file_moves', [])[:4]:
        if not isinstance(move, dict):
            continue
        lines.append(f"- Move `{move.get('from', '')}` -> `{move.get('to', '')}`")
    return lines


def _cleanup_lines(cleanup: dict[str, Any]) -> list[str]:
    total = int(cleanup.get('candidate_total', 0) or 0)
    review_required = int(cleanup.get('review_required_total', 0) or 0)
    by_category = (
        cleanup.get('by_category', {})
        if isinstance(cleanup.get('by_category'), dict)
        else {}
    )
    top_candidates = (
        cleanup.get('top_candidates', [])
        if isinstance(cleanup.get('top_candidates'), list)
        else []
    )
    lines = ['', '## Cleanup Candidates']
    lines.append(f"- Candidate Total: `{total}` | review required=`{review_required}`")
    owner_total = int(cleanup.get('owner_total', 0) or 0)
    ttl_total = int(cleanup.get('ttl_total', 0) or 0)
    expires_total = int(cleanup.get('expires_total', 0) or 0)
    expired_total = int(cleanup.get('expired_total', 0) or 0)
    if owner_total or ttl_total or expires_total or expired_total:
        lines.append(
            f"- Metadata: owner=`{owner_total}` | ttl=`{ttl_total}` | "
            f"expires_at=`{expires_total}` | expired=`{expired_total}`"
        )
    if by_category:
        rendered = ', '.join(f"{key}={value}" for key, value in by_category.items())
        lines.append(f"- Categories: {rendered}")
    if not top_candidates:
        lines.append("- No cleanup candidates detected in the current heuristic pass.")
        return lines
    for item in top_candidates[:5]:
        if not isinstance(item, dict):
            continue
        evidence = item.get('evidence', [])
        evidence_text = ', '.join(str(part) for part in evidence[:3]) if isinstance(evidence, list) else ''
        line = (
            f"- `{item.get('path', '')}` [{item.get('kind', '')}] -> "
            f"`{item.get('category', '')}` confidence=`{item.get('confidence', 0.0)}`"
        )
        if evidence_text:
            line += f" | {evidence_text}"
        metadata_text = cleanup_metadata_text(item)
        if metadata_text:
            line += f" | {metadata_text}"
        lines.append(line)
    return lines


def _archive_lines(archive_candidates: dict[str, Any]) -> list[str]:
    total = int(archive_candidates.get('candidate_total', 0) or 0)
    ready_total = int(archive_candidates.get('ready_total', 0) or 0)
    review_total = int(archive_candidates.get('review_total', 0) or 0)
    by_category = (
        archive_candidates.get('by_category', {})
        if isinstance(archive_candidates.get('by_category'), dict)
        else {}
    )
    top_candidates = (
        archive_candidates.get('top_candidates', [])
        if isinstance(archive_candidates.get('top_candidates'), list)
        else []
    )
    lines = ['', '## Archive Candidates']
    lines.append(f"- Candidate Total: `{total}` | ready=`{ready_total}` | review=`{review_total}`")
    if by_category:
        rendered = ', '.join(f"{key}={value}" for key, value in by_category.items())
        lines.append(f"- Categories: {rendered}")
    if not top_candidates:
        lines.append("- No archive candidates derived from the current cleanup inventory.")
        return lines
    for item in top_candidates[:5]:
        if not isinstance(item, dict):
            continue
        line = (
            f"- `{item.get('path', '')}` [{item.get('kind', '')}] -> "
            f"`{item.get('category', '')}` tier=`{item.get('archive_tier', '')}`"
        )
        archive_path_hint = str(item.get('archive_path_hint', '') or '').strip()
        if archive_path_hint:
            line += f" | archive as `{archive_path_hint}`"
        metadata_text = cleanup_metadata_text(item)
        if metadata_text:
            line += f" | {metadata_text}"
        lines.append(line)
    return lines


def _semantic_judge_lines(semantic_judge: dict[str, Any]) -> list[str]:
    status = str(semantic_judge.get('status', '') or 'skipped')
    summary = str(semantic_judge.get('summary', '') or '').strip()
    lines = ['', '## Semantic Judge']
    if status != 'ok':
        lines.append(f"- Status: `{status}`")
        if summary:
            lines.append(f"- Summary: {summary}")
        error = str(semantic_judge.get('error', '') or '').strip()
        if error:
            lines.append(f"- Error: {error}")
        return lines
    reviewed_total = int(semantic_judge.get('reviewed_total', 0) or 0)
    candidate_pool_total = int(semantic_judge.get('candidate_pool_total', 0) or 0)
    by_decision = (
        semantic_judge.get('by_decision', {})
        if isinstance(semantic_judge.get('by_decision'), dict)
        else {}
    )
    top_judgments = (
        semantic_judge.get('top_judgments', [])
        if isinstance(semantic_judge.get('top_judgments'), list)
        else []
    )
    lines.append(
        f"- Status: `ok` | reviewed=`{reviewed_total}` / candidate pool=`{candidate_pool_total}`"
    )
    if by_decision:
        rendered = ', '.join(f"{key}={value}" for key, value in by_decision.items())
        lines.append(f"- Decisions: {rendered}")
    if summary:
        lines.append(f"- Summary: {summary}")
    if not top_judgments:
        lines.append("- No semantic judgments returned.")
        return lines
    for item in top_judgments[:5]:
        if not isinstance(item, dict):
            continue
        line = (
            f"- `{item.get('path', '')}` -> `{item.get('decision', '')}` "
            f"confidence=`{item.get('confidence', 0.0)}`"
        )
        reason = str(item.get('reason', '') or '').strip()
        if reason:
            line += f" | {reason}"
        replacement = str(item.get('replacement', '') or '').strip()
        if replacement:
            line += f" | replace with `{replacement}`"
        archive_path_hint = str(item.get('archive_path_hint', '') or '').strip()
        if archive_path_hint:
            line += f" | archive as `{archive_path_hint}`"
        metadata_text = cleanup_metadata_text(item)
        if metadata_text:
            line += f" | {metadata_text}"
        lines.append(line)
    return lines


def _retire_plan_lines(title: str, analysis: dict[str, Any]) -> list[str]:
    retire_plan = (
        analysis.get('retire_plan', {})
        if isinstance(analysis.get('retire_plan'), dict)
        else {}
    )
    add_items = retire_plan.get('add', []) if isinstance(retire_plan.get('add'), list) else []
    retire_items = retire_plan.get('retire', []) if isinstance(retire_plan.get('retire'), list) else []
    validations = (
        retire_plan.get('validation', [])
        if isinstance(retire_plan.get('validation'), list)
        else []
    )
    if not retire_plan:
        return []
    lines = ['', f'## {title}']
    lines.append(f"- Planned Adds: `{len(add_items)}` | Planned Retirements: `{len(retire_items)}`")
    for item in add_items[:4]:
        if not isinstance(item, dict):
            continue
        component = str(item.get('component', '') or '').strip()
        focus_files = item.get('focus_files', [])
        focus_text = ', '.join(str(path) for path in focus_files[:3]) if isinstance(focus_files, list) else ''
        line = f"- Add `{component or item.get('why', '')}`"
        if focus_text:
            line += f" | focus: {focus_text}"
        lines.append(line)
    for item in retire_items[:4]:
        if not isinstance(item, dict):
            continue
        line = (
            f"- Retire `{item.get('path', '')}` [{item.get('kind', '')}] -> "
            f"`{item.get('category', '')}`"
        )
        replacement = str(item.get('replacement', '') or '').strip()
        if replacement:
            line += f" | replace with `{replacement}`"
        lines.append(line)
    for item in validations[:3]:
        if isinstance(item, dict):
            lines.append(f"- Validate `{item.get('check', '')}`: {item.get('detail', '')}")
        elif isinstance(item, str):
            lines.append(f"- Validate: {item}")
    return lines


def render_summary_markdown(report: dict[str, Any]) -> str:
    meta = _report_section(report, 'meta', dict)
    scores = _report_section(report, 'scores', dict)
    summary = _report_section(report, 'summary', dict)
    hotspots = _report_section(report, 'hotspots', list)
    components = _report_section(report, 'components', list)
    recommendations = _report_section(report, 'recommendations', list)
    topology = _report_section(report, 'topology', dict)
    cleanup = _report_section(report, 'cleanup', dict)
    archive_candidates = _report_section(report, 'archive_candidates', dict)
    semantic_judge = _report_section(report, 'semantic_judge', dict)
    change = _report_section(report, 'change_analysis', dict)
    feature = _report_section(report, 'feature_analysis', dict)
    structure = (
        scores.get('structure_dimensions', {})
        if isinstance(scores.get('structure_dimensions'), dict)
        else {}
    )

    lines = [
        '# Architec Summary',
        '',
        f"- Generated At: `{meta.get('generated_at', '')}`",
        f"- Path: `{meta.get('path', '')}`",
        f"- Mode: `{meta.get('mode', 'full')}`",
        f"- Goal: `{meta.get('goal', '')}`",
        '',
        '## Executive Summary',
        str(summary.get('executive_summary', '') or 'No summary generated.'),
        '',
        '## Score Snapshot',
    ]
    lines.extend(_score_lines(scores))
    lines.extend(['', '## Structure Signals'])
    for key, value in structure.items():
        lines.append(f"- {key.replace('_', ' ').title()}: `{value}`")
    lines.extend(['', '## Top Hotspots', *_item_lines(hotspots, kind='hotspots')])
    lines.extend(['', '## Risk Components', *_item_lines(components, kind='components')])
    if cleanup:
        lines.extend(_cleanup_lines(cleanup))
    if archive_candidates:
        lines.extend(_archive_lines(archive_candidates))
    if semantic_judge:
        lines.extend(_semantic_judge_lines(semantic_judge))
    if feature:
        lines.extend(_retire_plan_lines('Goal Retire Plan', feature))
    if change:
        lines.extend(_retire_plan_lines('Diff Retire Plan', change))
    if topology:
        lines.extend(_topology_lines(topology))
    lines.extend(['', '## Recommendations', *_item_lines(recommendations, kind='recommendations')])
    return '\n'.join(lines).rstrip() + '\n'
