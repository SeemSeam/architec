from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.scoring.contract_engine import summarize_findings
from architec.integration.hippo_adapter import HippoSnapshot
from architec.integration.bundle_loader import bundle_dir
from architec.support.io_utils import write_json
from architec.integration.paths import (
    ANALYSIS_JSON_PATH,
    SUMMARY_MD_PATH,
    TOPOLOGY_REVIEW_PATH,
    VIZ_HTML_PATH,
)
from architec.reporting.report_markdown import render_summary_markdown
from architec.reporting.viz_generator import render_viz_html


def _hotspot_components(hotspots: list[dict[str, Any]]) -> set[str]:
    return {
        str(item.get('component', '') or '')
        for item in hotspots[:5]
        if isinstance(item, dict) and str(item.get('component', '') or '')
    }


def graph_edges(
    graph: dict[str, list[dict[str, Any]]],
    hotspot_components: set[str],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for source in sorted(hotspot_components):
        for edge in graph.get(source, [])[:8]:
            if not isinstance(edge, dict):
                continue
            target = str(edge.get('target_component', '') or '')
            if target and target in hotspot_components and target != source:
                edges.append(
                    {
                        'source': source,
                        'target': target,
                        'weight': int(edge.get('weight', 0) or 0),
                    }
                )
    return edges


def graph_view(
    snapshot: HippoSnapshot,
    hotspots: list[dict[str, Any]],
    *,
    graph_builder,
) -> dict[str, Any]:
    hotspot_components = _hotspot_components(hotspots)
    return {
        'nodes': [{'id': comp, 'label': comp} for comp in sorted(hotspot_components)],
        'edges': graph_edges(graph_builder(snapshot), hotspot_components),
    }


def bundle_view(root: Path, snapshot: HippoSnapshot) -> dict[str, Any]:
    return {
        'source_dir': str(bundle_dir(root)),
        'metrics_loaded': bool(snapshot.metrics),
        'index_loaded': bool(snapshot.index),
        'signatures_loaded': bool(snapshot.signatures),
        'first_party_file_total': len(snapshot.first_party_paths()),
        'finding_total': len(snapshot.first_party_findings()),
    }


def report_evidence(
    snapshot: HippoSnapshot,
    history: dict[str, Any],
    hotspot_digest: dict[str, Any],
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        'history_summary': history.get('summary', {}),
        'top_hotspots': hotspot_digest.get('items', [])[:5],
        'components': components[:5],
        'metrics_summary': summarize_findings(snapshot.first_party_findings()),
    }


def write_report_artifacts(root: Path, report: dict[str, Any]) -> None:
    analysis_path = root / ANALYSIS_JSON_PATH
    summary_path = root / SUMMARY_MD_PATH
    viz_path = root / VIZ_HTML_PATH
    write_json(analysis_path, report)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_summary_markdown(report), encoding='utf-8')
    viz_path.parent.mkdir(parents=True, exist_ok=True)
    viz_path.write_text(render_viz_html(report), encoding='utf-8')
    existing_artifacts = report.get('artifacts', {}) if isinstance(report.get('artifacts'), dict) else {}
    report['artifacts'] = {
        **existing_artifacts,
        'analysis_json': str(analysis_path),
        'summary_md': str(summary_path),
        'viz_html': str(viz_path),
        'topology_json': str(root / TOPOLOGY_REVIEW_PATH),
    }
    write_json(analysis_path, report)
