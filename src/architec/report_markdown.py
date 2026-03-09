from __future__ import annotations

from typing import Any


def render_summary_markdown(report: dict[str, Any]) -> str:
    meta = report.get('meta', {}) if isinstance(report.get('meta'), dict) else {}
    scores = report.get('scores', {}) if isinstance(report.get('scores'), dict) else {}
    summary = report.get('summary', {}) if isinstance(report.get('summary'), dict) else {}
    hotspots = report.get('hotspots', []) if isinstance(report.get('hotspots'), list) else []
    components = report.get('components', []) if isinstance(report.get('components'), list) else []
    recommendations = report.get('recommendations', []) if isinstance(report.get('recommendations'), list) else []
    structure = scores.get('structure_dimensions', {}) if isinstance(scores.get('structure_dimensions'), dict) else {}

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
        f"- Overall: `{scores.get('overall', 0.0)}`",
        f"- Governance Overall: `{scores.get('governance_overall', scores.get('overall', 0.0))}`",
        f"- Structure: `{scores.get('structure', 0.0)}`",
        f"- Full: `{scores.get('full', 0.0)}`",
    ]
    if scores.get('incremental', None) is not None:
        lines.append(f"- Incremental: `{scores.get('incremental', 0.0)}`")
    lines.extend([
        '',
        '## Structure Signals',
    ])
    for key, value in structure.items():
        lines.append(f"- {key.replace('_', ' ').title()}: `{value}`")
    lines.extend(['', '## Top Hotspots'])
    for item in hotspots[:5]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('path', '')}` | impact=`{item.get('structure_impact', '')}` | {item.get('reason', '')}"
        )
    lines.extend(['', '## Risk Components'])
    for item in components[:5]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('component', '')}` | risk=`{item.get('risk_score', 0.0)}` | {', '.join(item.get('labels', [])[:3])}"
        )
    lines.extend(['', '## Recommendations'])
    for item in recommendations[:5]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('priority', 'P1')}` {item.get('title', '')}: {item.get('why', '')}"
        )
    return '\n'.join(lines).rstrip() + '\n'
