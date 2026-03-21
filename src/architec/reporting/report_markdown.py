from __future__ import annotations

from typing import Any


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


def render_summary_markdown(report: dict[str, Any]) -> str:
    meta = _report_section(report, 'meta', dict)
    scores = _report_section(report, 'scores', dict)
    summary = _report_section(report, 'summary', dict)
    hotspots = _report_section(report, 'hotspots', list)
    components = _report_section(report, 'components', list)
    recommendations = _report_section(report, 'recommendations', list)
    topology = _report_section(report, 'topology', dict)
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
    if topology:
        lines.extend(_topology_lines(topology))
    lines.extend(['', '## Recommendations', *_item_lines(recommendations, kind='recommendations')])
    return '\n'.join(lines).rstrip() + '\n'
