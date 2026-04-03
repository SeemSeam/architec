from __future__ import annotations

from html import escape
from typing import Any

from architec.cleanup.metadata import cleanup_metadata_text

from architec.reporting.viz_generator_cards import (
    graph_block,
    item_cards,
    label_text,
    structure_bars,
)


def viz_content(report: dict[str, Any]) -> dict[str, str]:
    scores = _report_section(report, 'scores', dict)
    hotspots = _report_section(report, 'hotspots', list)
    components = _report_section(report, 'components', list)
    recommendations = _report_section(report, 'recommendations', list)
    cleanup = _report_section(report, 'cleanup', dict)
    archive_candidates = _report_section(report, 'archive_candidates', dict)
    semantic_judge = _report_section(report, 'semantic_judge', dict)
    feature = _report_section(report, 'feature_analysis', dict)
    change = _report_section(report, 'change_analysis', dict)
    topology = _report_section(report, 'topology', dict)
    graph = _report_section(report, 'graph', dict)

    structure_dimensions = (
        scores.get('structure_dimensions', {})
        if isinstance(scores.get('structure_dimensions'), dict)
        else {}
    )
    graph_nodes = graph.get('nodes', []) if isinstance(graph.get('nodes'), list) else []
    graph_edges = graph.get('edges', []) if isinstance(graph.get('edges'), list) else []
    migration = (
        topology.get('migration_plan', {})
        if isinstance(topology.get('migration_plan', {}), dict)
        else {}
    )
    placement = (
        topology.get('root_placement_review', {})
        if isinstance(topology.get('root_placement_review'), dict)
        else {}
    )

    return {
        'structure_bar_markup': structure_bars(structure_dimensions),
        'hotspot_cards': _hotspot_cards(hotspots),
        'component_cards': _component_cards(components),
        'recommendation_cards': _recommendation_cards(recommendations),
        'cleanup_cards': _cleanup_cards(cleanup),
        'cleanup_summary': _cleanup_summary(cleanup),
        'archive_cards': _archive_cards(archive_candidates),
        'archive_summary': _archive_summary(archive_candidates),
        'semantic_cards': _semantic_cards(semantic_judge),
        'semantic_summary': _semantic_summary(semantic_judge),
        'goal_retire_cards': _retire_plan_cards(feature),
        'goal_retire_summary': _retire_plan_summary(feature, mode='goal'),
        'diff_retire_cards': _retire_plan_cards(change),
        'diff_retire_summary': _retire_plan_summary(change, mode='diff'),
        'topology_cards': _topology_cards(topology),
        'migration_cards': _migration_cards(migration),
        'graph_markup': graph_block(graph_nodes, graph_edges),
        'root_placement_summary': (
            f"Root placement: move {len(placement.get('misplaced_root_files', []))} files, "
            f"review {len(placement.get('review_root_files', []))} files."
        ),
        'topology_summary': escape(str(topology.get('summary', '') or 'No folder review.')),
        'migration_summary': escape(str(migration.get('summary', '') or 'No migration plan.')),
    }


def _report_section(report: dict[str, Any], key: str, expected_type: type) -> Any:
    value = report.get(key, expected_type())
    return value if isinstance(value, expected_type) else expected_type()


def _hotspot_cards(hotspots: list[dict[str, Any]]) -> str:
    return item_cards(
        hotspots,
        title_key='path',
        body_text=lambda item: escape(str(item.get('reason', ''))),
        small_text=lambda item: item.get('structure_impact', ''),
    )


def _component_cards(components: list[dict[str, Any]]) -> str:
    return item_cards(
        components,
        title_key='component',
        body_text=lambda item: label_text(item.get('labels')),
        small_text=lambda item: f"risk={item.get('risk_score', 0.0)}",
    )


def _recommendation_cards(recommendations: list[dict[str, Any]]) -> str:
    return item_cards(
        recommendations,
        title_key='title',
        body_text=lambda item: escape(str(item.get('why', ''))),
        small_text=lambda item: item.get('scope', ''),
    )


def _cleanup_cards(cleanup: dict[str, Any]) -> str:
    items = cleanup.get('top_candidates', []) if isinstance(cleanup.get('top_candidates'), list) else []
    return item_cards(
        items,
        title_key='path',
        body_text=lambda item: escape(
            str(item.get('category', ''))
            + (f" | {cleanup_metadata_text(item)}" if cleanup_metadata_text(item) else "")
        ),
        small_text=lambda item: f"{item.get('kind', '')} · {item.get('confidence', 0.0)}",
    )


def _cleanup_summary(cleanup: dict[str, Any]) -> str:
    total = int(cleanup.get('candidate_total', 0) or 0)
    review_required = int(cleanup.get('review_required_total', 0) or 0)
    owner_total = int(cleanup.get('owner_total', 0) or 0)
    ttl_total = int(cleanup.get('ttl_total', 0) or 0)
    expires_total = int(cleanup.get('expires_total', 0) or 0)
    expired_total = int(cleanup.get('expired_total', 0) or 0)
    text = f"Candidates: {total}. Review required: {review_required}."
    if owner_total or ttl_total or expires_total or expired_total:
        text += (
            f" Metadata owner={owner_total}, ttl={ttl_total}, "
            f"expires_at={expires_total}, expired={expired_total}."
        )
    return escape(text)


def _archive_cards(archive_candidates: dict[str, Any]) -> str:
    items = (
        archive_candidates.get('top_candidates', [])
        if isinstance(archive_candidates.get('top_candidates'), list)
        else []
    )
    return item_cards(
        items,
        title_key='path',
        body_text=lambda item: escape(
            str(item.get('archive_reason', ''))
            + (f" | {cleanup_metadata_text(item)}" if cleanup_metadata_text(item) else "")
        ),
        small_text=lambda item: (
            f"{item.get('archive_tier', '')} · {item.get('archive_path_hint', '')}"
        ),
    )


def _archive_summary(archive_candidates: dict[str, Any]) -> str:
    total = int(archive_candidates.get('candidate_total', 0) or 0)
    ready_total = int(archive_candidates.get('ready_total', 0) or 0)
    review_total = int(archive_candidates.get('review_total', 0) or 0)
    return escape(f"Candidates: {total}. Ready: {ready_total}. Review: {review_total}.")


def _semantic_cards(semantic_judge: dict[str, Any]) -> str:
    items = (
        semantic_judge.get('top_judgments', [])
        if isinstance(semantic_judge.get('top_judgments'), list)
        else []
    )
    return item_cards(
        items,
        title_key='path',
        body_text=lambda item: escape(
            str(item.get('reason', '') or item.get('decision', ''))
            + (f" | {cleanup_metadata_text(item)}" if cleanup_metadata_text(item) else "")
        ),
        small_text=lambda item: (
            f"{item.get('decision', '')} · {item.get('confidence', 0.0)}"
        ),
    )


def _semantic_summary(semantic_judge: dict[str, Any]) -> str:
    status = str(semantic_judge.get('status', '') or 'skipped')
    if status != 'ok':
        summary = str(semantic_judge.get('summary', '') or '').strip()
        return escape(summary or f"Semantic judge status: {status}.")
    reviewed_total = int(semantic_judge.get('reviewed_total', 0) or 0)
    by_decision = (
        semantic_judge.get('by_decision', {})
        if isinstance(semantic_judge.get('by_decision'), dict)
        else {}
    )
    rendered = ", ".join(f"{key}={value}" for key, value in sorted(by_decision.items()))
    return escape(
        f"Reviewed {reviewed_total} candidates." + (f" Decisions: {rendered}." if rendered else "")
    )


def _retire_plan_cards(analysis: dict[str, Any]) -> str:
    retire_plan = (
        analysis.get('retire_plan', {})
        if isinstance(analysis.get('retire_plan'), dict)
        else {}
    )
    add_items = retire_plan.get('add', []) if isinstance(retire_plan.get('add'), list) else []
    retire_items = retire_plan.get('retire', []) if isinstance(retire_plan.get('retire'), list) else []
    cards: list[dict[str, Any]] = []
    for item in add_items[:3]:
        if not isinstance(item, dict):
            continue
        cards.append(
            {
                'title': item.get('component', '') or item.get('why', ''),
                'body': 'add',
                'small': ', '.join(str(path) for path in item.get('focus_files', [])[:2]),
            }
        )
    for item in retire_items[:3]:
        if not isinstance(item, dict):
            continue
        cards.append(
            {
                'title': item.get('path', ''),
                'body': item.get('category', ''),
                'small': item.get('replacement', '') or item.get('kind', ''),
            }
        )
    return item_cards(
        cards,
        title_key='title',
        body_text=lambda item: escape(str(item.get('body', ''))),
        small_text=lambda item: item.get('small', ''),
    )


def _retire_plan_summary(analysis: dict[str, Any], *, mode: str) -> str:
    retire_plan = (
        analysis.get('retire_plan', {})
        if isinstance(analysis.get('retire_plan'), dict)
        else {}
    )
    if not retire_plan:
        return escape(f"No {mode} retire plan.")
    add_total = len(retire_plan.get('add', []) if isinstance(retire_plan.get('add'), list) else [])
    retire_total = len(retire_plan.get('retire', []) if isinstance(retire_plan.get('retire'), list) else [])
    validation_total = len(
        retire_plan.get('validation', [])
        if isinstance(retire_plan.get('validation'), list)
        else []
    )
    return escape(
        f"Adds: {add_total}. Retirements: {retire_total}. Validation checks: {validation_total}."
    )


def _topology_cards(topology: dict[str, Any]) -> str:
    groups = topology.get('groups', []) if isinstance(topology.get('groups'), list) else []
    return item_cards(
        groups,
        title_key='group_id',
        body_text=lambda item: escape(
            str(
                (
                    item.get('naming_review', {}).get('reason', '')
                    if isinstance(item.get('naming_review'), dict)
                    else ''
                )
                or f"recommended folder: {item.get('programmatic_name', '')}"
            )
        ),
        small_text=lambda item: (
            item.get('naming_review', {}).get('recommended_name', '')
            if isinstance(item.get('naming_review'), dict)
            else item.get('programmatic_name', '')
        ),
    )


def _migration_cards(migration: dict[str, Any]) -> str:
    moves = (
        migration.get('file_moves', [])
        if isinstance(migration.get('file_moves'), list)
        else []
    )
    return item_cards(
        moves,
        title_key='from',
        body_text=lambda item: escape(str(item.get('reason', '') or '')),
        small_text=lambda item: item.get('to', ''),
    )
