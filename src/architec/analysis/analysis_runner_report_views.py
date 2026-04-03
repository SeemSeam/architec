from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.cleanup.retire_plan import (
    build_diff_retire_plan,
    build_goal_retire_plan,
)
from architec.support.io_utils import utc_now_iso


def summary_payload(
    *,
    goal: str,
    diff: bool,
    score_snapshot: dict[str, Any],
    hotspots: list[dict[str, Any]],
    components: list[dict[str, Any]],
    feature: dict[str, Any],
    topology: dict[str, Any],
) -> dict[str, Any]:
    topology_summary = _summary_topology(topology)
    feature_targets = feature.get('target_components', [])[:3] if isinstance(feature, dict) else []
    return {
        'goal': goal,
        'mode': 'diff' if diff else 'full',
        'scores': score_snapshot,
        'hotspots': hotspots[:5],
        'components': components[:5],
        'feature_targets': feature_targets,
        'topology': topology_summary,
    }


def _summary_topology_group(item: dict[str, Any]) -> dict[str, Any]:
    naming = item.get('naming_review', {}) if isinstance(item.get('naming_review'), dict) else {}
    return {
        'group_id': item.get('group_id', ''),
        'file_count': item.get('file_count', 0),
        'programmatic_name': item.get('programmatic_name', ''),
        'recommended_name': naming.get('recommended_name', ''),
    }


def _summary_topology(topology: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(topology, dict):
        return {}
    migration = topology.get('migration_plan', {})
    root_review = topology.get('root_placement_review', {})
    groups = topology.get('groups', [])
    return {
        'source_root': str(topology.get('source_root', '') or ''),
        'flat_file_total': int(topology.get('flat_file_total', 0) or 0),
        'needs_folder_management': bool(topology.get('needs_folder_management', False)),
        'migration_summary': (
            str(migration.get('summary', '') or '')
            if isinstance(migration, dict)
            else ''
        ),
        'groups': [
            _summary_topology_group(item)
            for item in groups[:5]
            if isinstance(item, dict)
        ] if isinstance(groups, list) else [],
        'migration_plan': _summary_migration_plan(migration),
        'root_placement_review': _summary_root_placement(root_review),
    }


def _summary_migration_plan(migration: object) -> dict[str, Any]:
    if not isinstance(migration, dict):
        return {}
    return {
        'folders_to_create': migration.get('folders_to_create', [])[:8],
        'file_move_total': len(migration.get('file_moves', [])),
        'review_file_total': len(migration.get('review_files', [])),
    }


def _summary_root_placement(root_review: object) -> dict[str, Any]:
    if not isinstance(root_review, dict):
        return {}
    return {
        'misplaced_root_total': len(root_review.get('misplaced_root_files', [])),
        'review_root_total': len(root_review.get('review_root_files', [])),
    }


def summary_view(llm_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        'headline': str(llm_summary.get('headline', '') or 'Project structure snapshot'),
        'executive_summary': str(
            llm_summary.get('executive_summary', '')
            or 'Structure score highlights where module boundaries and hotspot pressure need attention.'
        ),
        'top_takeaways': llm_summary.get('top_takeaways', []),
    }


def llm_recommendations(llm_summary: dict[str, Any]) -> list[dict[str, Any]]:
    raw = llm_summary.get('recommendations')
    if not isinstance(raw, list) or not raw:
        return []
    out = []
    for idx, item in enumerate(raw[:5]):
        if not isinstance(item, dict):
            continue
        out.append(
            {
                'priority': f'P{idx}',
                'title': str(item.get('title', '') or ''),
                'why': str(item.get('why', '') or ''),
                'scope': str(item.get('scope', '') or ''),
            }
        )
    return out


def change_analysis(
    score: dict[str, Any],
    *,
    diff: bool,
    snapshot: Any,
    cleanup_inventory: dict[str, Any],
) -> dict[str, Any]:
    if not diff:
        return {}
    return {
        'changed_file_total': int(score.get('changed_file_total', 0) or 0),
        'components': score.get('components', [])[:8] if isinstance(score, dict) else [],
        'retire_plan': build_diff_retire_plan(
            score,
            snapshot=snapshot,
            cleanup_inventory=cleanup_inventory,
        ),
    }


def feature_analysis(
    feature: dict[str, Any],
    *,
    goal: str,
    snapshot: Any,
    cleanup_inventory: dict[str, Any],
) -> dict[str, Any]:
    if not goal:
        return {}
    return {
        'goal': goal,
        'target_components': feature.get('target_components', [])[:8],
        'candidate_files': feature.get('candidate_files', [])[:10],
        'retire_plan': build_goal_retire_plan(
            feature,
            goal=goal,
            snapshot=snapshot,
            cleanup_inventory=cleanup_inventory,
        ),
    }


def report_meta(*, root: Path, goal: str, diff: bool, base: str, head: str) -> dict[str, Any]:
    if diff and (base or head):
        diff_scope = 'git_range'
    elif diff:
        diff_scope = 'working_tree'
    else:
        diff_scope = 'none'
    return {
        'generated_at': utc_now_iso(),
        'path': str(root),
        'mode': 'diff' if diff else 'full',
        'goal': goal,
        'base': base,
        'head': head,
        'diff_scope': diff_scope,
    }
