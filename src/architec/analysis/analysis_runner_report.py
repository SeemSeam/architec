from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.analysis.analysis_runner_report_views import (
    change_analysis,
    feature_analysis,
    llm_recommendations,
    report_meta,
    summary_payload,
    summary_view,
)
from architec.analysis.analysis_runner_report_support import (
    bundle_view,
    graph_view,
    report_evidence,
    write_report_artifacts,
)
from architec.integration.hippo_adapter import HippoSnapshot


def component_labels(item: dict[str, Any]) -> list[str]:
    labels = []
    if int(item.get('critical', 0) or 0) > 0:
        labels.append('critical_findings')
    if float(item.get('risk_score', 0.0) or 0.0) >= 8.0:
        labels.append('hotspot_concentration')
    if int(item.get('file_count', 0) or 0) >= 8:
        labels.append('wide_component')
    return labels or ['watch']


def component_entry(component: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        'component': component,
        'risk_score': round(float(item.get('risk_score', 0.0) or 0.0), 2),
        'critical': int(item.get('critical', 0) or 0),
        'warning': int(item.get('warning', 0) or 0),
        'file_count': int(item.get('file_count', 0) or 0),
        'labels': component_labels(item),
    }


def component_view(history: dict[str, Any]) -> list[dict[str, Any]]:
    risk_map = (
        history.get('component_risk', {})
        if isinstance(history.get('component_risk'), dict)
        else {}
    )
    out = [
        component_entry(component, item)
        for component, item in risk_map.items()
        if isinstance(item, dict)
    ]
    out.sort(key=lambda item: (-float(item.get('risk_score', 0.0)), item.get('component', '')))
    return out[:10]


def score_snapshot(
    *,
    structure_score: float,
    full_score: dict[str, Any],
    incremental_score: dict[str, Any],
    governance_overall: dict[str, Any],
    diff: bool,
) -> dict[str, Any]:
    detailed: dict[str, float | None] = {
        'structure': round(float(structure_score), 2),
        'full': round(float(full_score.get('score', 0.0) or 0.0), 2),
        'incremental': None,
    }
    values = [float(detailed['structure'] or 0.0), float(detailed['full'] or 0.0)]
    if diff:
        incremental_value = round(float(incremental_score.get('score', 0.0) or 0.0), 2)
        detailed['incremental'] = incremental_value
        values.append(incremental_value)
    total_average = round(sum(values) / max(1, len(values)), 2)
    return {
        'overall': total_average,
        'total_average': total_average,
        'governance_overall': round(float(governance_overall.get('score', 0.0) or 0.0), 2),
        'structure': detailed['structure'],
        'full': detailed['full'],
        'incremental': detailed['incremental'],
    }


def resolved_hotspots(snapshot: HippoSnapshot, hotspot_digest: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in hotspot_digest.get('items', []):
        if not isinstance(item, dict):
            continue
        resolved = dict(item)
        path = str(resolved.get('path', '') or '')
        if path and not str(resolved.get('component', '') or ''):
            resolved['component'] = snapshot.component_for_path(path)
        out.append(resolved)
    return out


def hotspot_view(hotspot_digest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            **item,
            'reason': str(item.get('fix_hint', '') or ''),
            'structure_impact': str(item.get('dominant_metric', '') or ''),
        }
        for item in hotspot_digest.get('items', [])[:8]
        if isinstance(item, dict)
    ]


def build_report(
    *,
    root: Path,
    snapshot: HippoSnapshot,
    history: dict[str, Any],
    score: dict[str, Any],
    feature: dict[str, Any],
    goal: str,
    diff: bool,
    base: str,
    head: str,
    dimensions: dict[str, float],
    score_snapshot: dict[str, Any],
    resolved_hotspots: list[dict[str, Any]],
    components: list[dict[str, Any]],
    summary: dict[str, Any],
    recommendations: list[dict[str, Any]],
    topology: dict[str, Any],
    cleanup: dict[str, Any],
    archive_candidates: dict[str, Any],
    semantic_judge: dict[str, Any],
    cleanup_inventory: dict[str, Any],
    graph_builder,
) -> dict[str, Any]:
    hotspots_payload = {'items': resolved_hotspots}
    return {
        'meta': report_meta(root=root, goal=goal, diff=diff, base=base, head=head),
        'bundle': bundle_view(root, snapshot),
        'summary': summary,
        'scores': {
            **score_snapshot,
            'structure_dimensions': dimensions,
        },
        'hotspots': hotspot_view(hotspots_payload),
        'components': components,
        'topology': topology,
        'change_analysis': change_analysis(
            score,
            diff=diff,
            snapshot=snapshot,
            cleanup_inventory=cleanup_inventory,
        ),
        'feature_analysis': feature_analysis(
            feature,
            goal=goal,
            snapshot=snapshot,
            cleanup_inventory=cleanup_inventory,
        ),
        'recommendations': recommendations,
        'cleanup': cleanup,
        'archive_candidates': archive_candidates,
        'semantic_judge': semantic_judge,
        'evidence': report_evidence(snapshot, history, hotspots_payload, components),
        'graph': graph_view(snapshot, resolved_hotspots, graph_builder=graph_builder),
        'artifacts': {},
    }
