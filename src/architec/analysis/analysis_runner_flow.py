from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.analysis.analysis_runner_llm import (
    llm_summary,
    run_diff_analysis,
    run_goal_analysis,
)
from architec.analysis.governance_dimensions import governance_dimensions
from architec.analysis.analysis_runner_recommendations import (
    recommendations,
    topology_recommendations,
)
from architec.support.io_utils import clamp


def score_from_keywords(
    source: dict[str, Any],
    keywords: tuple[str, ...],
    factor: float,
) -> float:
    total = 0.0
    for key, value in source.items():
        if any(word in str(key).lower() for word in keywords):
            total += float(value or 0.0)
    return total * factor


def _count(source: dict[str, Any], key: str) -> float:
    return float(source.get(key, 0.0) or 0.0)


def _excess_penalty(
    count: float,
    *,
    grace: float,
    factor: float,
    cap: float,
) -> float:
    if count <= grace:
        return 0.0
    return min(cap, (count - grace) * factor)


def _file_modularity_penalty(by_metric: dict[str, Any]) -> float:
    return (
        _excess_penalty(_count(by_metric, 'module_lines'), grace=10.0, factor=1.4, cap=24.0)
        + _excess_penalty(
            _count(by_metric, 'class_public_methods'),
            grace=4.0,
            factor=1.2,
            cap=8.0,
        )
        + _excess_penalty(
            _count(by_metric, 'class_instance_attributes'),
            grace=4.0,
            factor=1.0,
            cap=6.0,
        )
    )


def _maintainability_penalty(
    by_metric: dict[str, Any],
    by_severity: dict[str, Any],
) -> float:
    complexity = _excess_penalty(
        _count(by_metric, 'cyclomatic_complexity'),
        grace=32.0,
        factor=0.45,
        cap=18.0,
    )
    line_soft = _excess_penalty(
        _count(by_metric, 'line_length_soft_hits'),
        grace=55.0,
        factor=0.06,
        cap=6.0,
    )
    line_hard = _excess_penalty(
        _count(by_metric, 'line_length_hard_hits'),
        grace=16.0,
        factor=0.22,
        cap=8.0,
    )
    critical = _excess_penalty(
        _count(by_severity, 'critical'),
        grace=6.0,
        factor=0.55,
        cap=10.0,
    )
    return complexity + line_soft + line_hard + critical


def _topology_dimension(topology: dict[str, Any]) -> float:
    if not isinstance(topology, dict) or not topology:
        return 70.0

    flat_file_total = int(topology.get('flat_file_total', 0) or 0)
    subpackage_total = int(topology.get('subpackage_total', 0) or 0)
    compat_wrapper_total = int(topology.get('compat_wrapper_total', 0) or 0)
    placement_review = (
        topology.get('root_placement_review', {})
        if isinstance(topology.get('root_placement_review', {}), dict)
        else {}
    )
    misplaced_root_total = len(placement_review.get('misplaced_root_files', []))
    review_root_total = len(placement_review.get('review_root_files', []))
    retained_root_total = len(placement_review.get('allowed_root_files', []))

    score = 100.0
    if flat_file_total > 8:
        score -= min(34.0, (flat_file_total - 8) * 1.25)
    if misplaced_root_total:
        score -= min(26.0, misplaced_root_total * 1.15)
    if review_root_total:
        score -= min(12.0, review_root_total * 1.4)
    if retained_root_total > 8:
        score -= min(8.0, (retained_root_total - 8) * 1.6)

    if subpackage_total >= 6:
        score += 8.0
    elif subpackage_total >= 3:
        score += 5.0
    elif subpackage_total > 0:
        score += 2.5

    if (
        not bool(topology.get('needs_folder_management', False))
        and flat_file_total <= 28
        and misplaced_root_total <= 18
    ):
        score += 4.0
    if compat_wrapper_total and misplaced_root_total == 0:
        score += min(4.0, compat_wrapper_total * 0.8)

    return round(clamp(score, 0.0, 100.0), 2)


def structure_dimensions(
    history: dict[str, Any],
    topology: dict[str, Any] | None = None,
    *,
    hotspot_digest: dict[str, Any] | None = None,
    components: list[dict[str, Any]] | None = None,
    cleanup: dict[str, Any] | None = None,
    archive_candidates: dict[str, Any] | None = None,
    semantic_judge: dict[str, Any] | None = None,
) -> dict[str, float]:
    summary = history.get('summary', {}) if isinstance(history.get('summary'), dict) else {}
    by_metric = summary.get('by_metric', {}) if isinstance(summary.get('by_metric'), dict) else {}
    by_dimension = (
        summary.get('by_dimension', {})
        if isinstance(summary.get('by_dimension'), dict)
        else {}
    )
    by_severity = (
        summary.get('by_severity', {})
        if isinstance(summary.get('by_severity'), dict)
        else {}
    )

    file_modularity = 100.0 - min(36.0, _file_modularity_penalty(by_metric))
    boundary_clarity = 100.0 - min(
        40.0,
        score_from_keywords(by_dimension, ('boundary', 'layer', 'ownership', 'component'), 2.0),
    )
    coupling = 100.0 - min(
        35.0,
        score_from_keywords(by_dimension, ('coupling', 'dependency'), 2.4),
    )
    maintainability = 100.0 - min(
        36.0,
        _maintainability_penalty(by_metric, by_severity),
    )
    dimensions = {
        'file_modularity': round(max(0.0, file_modularity), 2),
        'boundary_clarity': round(max(0.0, boundary_clarity), 2),
        'coupling_control': round(max(0.0, coupling), 2),
        'maintainability': round(max(0.0, maintainability), 2),
    }
    if topology is not None:
        dimensions['package_topology'] = _topology_dimension(topology)
    dimensions.update(
        governance_dimensions(
            hotspot_digest=hotspot_digest,
            components=components,
            cleanup=cleanup,
            archive_candidates=archive_candidates,
            semantic_judge=semantic_judge,
        )
    )
    return dimensions


def structure_score(full_score: dict[str, Any], dimensions: dict[str, float]) -> float:
    base = float(full_score.get('score', 0.0) or 0.0)
    if not dimensions:
        return round(base, 2)
    avg = sum(float(v or 0.0) for v in dimensions.values()) / max(1, len(dimensions))
    return round((base * 0.3) + (avg * 0.7), 2)


def incremental_score(score: dict[str, Any], *, diff: bool) -> dict[str, Any]:
    if diff and isinstance(score.get('incremental_score'), dict):
        return score['incremental_score']
    return {'mode': 'not_applicable', 'score': 0.0, 'recommendation': 'n/a', 'signals': {}}
