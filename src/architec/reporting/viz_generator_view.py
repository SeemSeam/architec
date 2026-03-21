from __future__ import annotations

from html import escape
from typing import Any

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
