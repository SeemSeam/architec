from __future__ import annotations

from pathlib import Path
from typing import Any

from .analysis_cache import run_cached_analysis
from .backend_llm import complete_json
from .component_graph import build_component_graph
from .component_scoring import score_changed_components
from .contract_engine import summarize_findings
from .feature_advisor import suggest_feature_architecture
from .hippo_adapter import HippoSnapshot
from .history_analyzer import analyze_history_and_iterate
from .hotspot_digest import build_hotspot_digest
from .io_utils import ProgressFn, utc_now_iso, write_json
from .llm_guard import guard_llm_result
from .paths import ANALYSIS_JSON_PATH, SUMMARY_MD_PATH, VIZ_HTML_PATH
from .report_markdown import render_summary_markdown
from .scoring_policy import evaluate_overall_score, load_scoring_policy
from .viz_generator import render_viz_html


def _score_from_keywords(source: dict[str, Any], keywords: tuple[str, ...], factor: float) -> float:
    total = 0.0
    for key, value in source.items():
        if any(word in str(key).lower() for word in keywords):
            total += float(value or 0.0)
    return total * factor


def _structure_dimensions(history: dict[str, Any]) -> dict[str, float]:
    summary = history.get('summary', {}) if isinstance(history.get('summary'), dict) else {}
    by_metric = summary.get('by_metric', {}) if isinstance(summary.get('by_metric'), dict) else {}
    by_dimension = summary.get('by_dimension', {}) if isinstance(summary.get('by_dimension'), dict) else {}
    by_severity = summary.get('by_severity', {}) if isinstance(summary.get('by_severity'), dict) else {}

    file_modularity = 100.0 - min(
        45.0,
        _score_from_keywords(by_metric, ('module_lines', 'class_public_methods', 'class_instance_attributes'), 1.6),
    )
    boundary_clarity = 100.0 - min(
        40.0,
        _score_from_keywords(by_dimension, ('boundary', 'layer', 'ownership', 'component'), 2.0),
    )
    coupling = 100.0 - min(
        35.0,
        _score_from_keywords(by_dimension, ('coupling', 'dependency'), 2.4),
    )
    maintainability = 100.0 - min(
        45.0,
        _score_from_keywords(by_metric, ('cyclomatic', 'complexity', 'line_length'), 1.2)
        + _score_from_keywords(by_severity, ('critical',), 3.0),
    )
    return {
        'file_modularity': round(max(0.0, file_modularity), 2),
        'boundary_clarity': round(max(0.0, boundary_clarity), 2),
        'coupling_control': round(max(0.0, coupling), 2),
        'maintainability': round(max(0.0, maintainability), 2),
    }


def _structure_score(full_score: dict[str, Any], dimensions: dict[str, float]) -> float:
    base = float(full_score.get('score', 0.0) or 0.0)
    if not dimensions:
        return round(base, 2)
    avg = sum(float(v or 0.0) for v in dimensions.values()) / max(1, len(dimensions))
    return round((base * 0.45) + (avg * 0.55), 2)


def _recommendations(hotspot_digest: dict[str, Any], components: list[dict[str, Any]], goal: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for spot in hotspot_digest.get('items', [])[:3]:
        if not isinstance(spot, dict):
            continue
        items.append(
            {
                'priority': f"P{min(2, int(spot.get('rank', 1)) - 1)}",
                'title': str(spot.get('path', '') or ''),
                'why': str(spot.get('fix_hint', '') or ''),
                'scope': str(spot.get('component', '') or ''),
            }
        )
    for component in components[:2]:
        if not isinstance(component, dict):
            continue
        items.append(
            {
                'priority': 'P1',
                'title': f"Stabilize {component.get('component', '')}",
                'why': f"Component risk score {component.get('risk_score', 0.0)} with labels {', '.join(component.get('labels', [])[:3])}.",
                'scope': str(component.get('component', '') or ''),
            }
        )
    if goal:
        items.insert(
            0,
            {
                'priority': 'P0',
                'title': 'Keep goal-driven changes inside existing ownership boundaries',
                'why': f'Goal context: {goal}',
                'scope': 'goal',
            },
        )
    return items[:5]


def _llm_summary(root: Path, *, payload: dict[str, Any]) -> dict[str, Any] | None:
    prompt = (
        'You are Architec, an architecture analyst.\n'
        'Only make claims that are directly supported by the input payload.\n'
        'Do not infer duplication, shared abstractions, or causal relationships unless they are explicit in the input.\n'
        'Return strict JSON only with schema:\n'
        '{\n'
        '  "headline":"string",\n'
        '  "executive_summary":"string",\n'
        '  "top_takeaways":["string"],\n'
        '  "recommendations":[{"title":"string","why":"string","scope":"string"}]\n'
        '}\n\n'
        f'Input:\n{payload}'
    )
    result, _ = run_cached_analysis(
        root,
        namespace='architec_summary',
        payload=payload,
        runner=lambda: guard_llm_result(
            root,
            task='architec_summary',
            runner=lambda: complete_json(
                root,
                task='architec_summary',
                tier='strong',
                prompt=prompt,
                timeout_sec=30.0,
                max_tokens=900,
                required=True,
            ),
        ),
    )
    return result if isinstance(result, dict) else None


def _component_view(history: dict[str, Any]) -> list[dict[str, Any]]:
    risk_map = history.get('component_risk', {}) if isinstance(history.get('component_risk'), dict) else {}
    out: list[dict[str, Any]] = []
    for component, item in risk_map.items():
        if not isinstance(item, dict):
            continue
        labels = []
        if int(item.get('critical', 0) or 0) > 0:
            labels.append('critical_findings')
        if float(item.get('risk_score', 0.0) or 0.0) >= 8.0:
            labels.append('hotspot_concentration')
        if int(item.get('file_count', 0) or 0) >= 8:
            labels.append('wide_component')
        out.append(
            {
                'component': component,
                'risk_score': round(float(item.get('risk_score', 0.0) or 0.0), 2),
                'critical': int(item.get('critical', 0) or 0),
                'warning': int(item.get('warning', 0) or 0),
                'file_count': int(item.get('file_count', 0) or 0),
                'labels': labels or ['watch'],
            }
        )
    out.sort(key=lambda item: (-float(item.get('risk_score', 0.0)), item.get('component', '')))
    return out[:10]


def _score_snapshot(
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


def _graph_view(snapshot: HippoSnapshot, hotspots: list[dict[str, Any]]) -> dict[str, Any]:
    graph = build_component_graph(snapshot)
    hotspot_components = {
        str(item.get('component', '') or '')
        for item in hotspots[:5]
        if isinstance(item, dict) and str(item.get('component', '') or '')
    }
    nodes = [{'id': comp, 'label': comp} for comp in sorted(hotspot_components)]
    edges: list[dict[str, Any]] = []
    for source in sorted(hotspot_components):
        for edge in graph.get(source, [])[:8]:
            if not isinstance(edge, dict):
                continue
            target = str(edge.get('target_component', '') or '')
            if target and target in hotspot_components and target != source:
                edges.append({'source': source, 'target': target, 'weight': int(edge.get('weight', 0) or 0)})
    return {'nodes': nodes, 'edges': edges}


def run_analysis(
    project_root: str | Path,
    *,
    goal: str = '',
    diff: bool = False,
    base: str = '',
    head: str = '',
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    steps = 5 + (1 if diff else 0) + (1 if goal else 0)
    step = 0

    def advance(label: str) -> None:
        nonlocal step
        step += 1
        if progress is not None:
            progress(f"analysis [{step}/{steps}] {label}")

    advance('loading Hippo snapshot')
    snapshot = HippoSnapshot.load(root)
    advance('running history analysis')
    history = analyze_history_and_iterate(root, llm_enabled=True)
    if diff:
        advance('running diff component scoring')
        score = score_changed_components(root, base=base or None, head=head or None, llm_enabled=True)
    else:
        score = {}
    if goal:
        advance('running goal-driven feature analysis')
        feature = suggest_feature_architecture(root, goal=goal, llm_enabled=True)
    else:
        feature = {}
    full_score = history.get('full_score', {}) if isinstance(history.get('full_score'), dict) else {}
    incremental_score = (
        score.get('incremental_score', {})
        if diff and isinstance(score.get('incremental_score'), dict)
        else {'mode': 'not_applicable', 'score': 0.0, 'recommendation': 'n/a', 'signals': {}}
    )
    governance_overall = evaluate_overall_score(
        full_score=full_score,
        incremental_score=incremental_score,
        policy=load_scoring_policy(root),
    )
    advance('building hotspot digest and structural scores')
    hotspot_digest = build_hotspot_digest(
        root,
        history=history,
        score=score if isinstance(score, dict) else {},
        batches=[],
        governance={
            'full': full_score.get('score', 0.0),
            'incremental': incremental_score.get('score', 0.0),
            'overall': governance_overall.get('score', 0.0),
        },
    )
    dimensions = _structure_dimensions(history)
    structure_score = _structure_score(full_score, dimensions)
    score_snapshot = _score_snapshot(
        structure_score=structure_score,
        full_score=full_score,
        incremental_score=incremental_score,
        governance_overall=governance_overall,
        diff=diff,
    )
    components = _component_view(history)
    recommendations = _recommendations(hotspot_digest, components, goal)
    summary_payload = {
        'goal': goal,
        'mode': 'diff' if diff else 'full',
        'scores': score_snapshot,
        'hotspots': hotspot_digest.get('items', [])[:5],
        'components': components[:5],
        'feature_targets': feature.get('target_components', [])[:3] if isinstance(feature, dict) else [],
    }
    advance('requesting LLM executive summary')
    llm_summary = _llm_summary(root, payload=summary_payload) or {}
    summary = {
        'headline': str(llm_summary.get('headline', '') or 'Project structure snapshot'),
        'executive_summary': str(llm_summary.get('executive_summary', '') or 'Structure score highlights where module boundaries and hotspot pressure need attention.'),
        'top_takeaways': llm_summary.get('top_takeaways', []),
    }
    if isinstance(llm_summary.get('recommendations'), list) and llm_summary['recommendations']:
        llm_recs = []
        for idx, item in enumerate(llm_summary['recommendations'][:5]):
            if not isinstance(item, dict):
                continue
            llm_recs.append(
                {
                    'priority': f'P{idx}',
                    'title': str(item.get('title', '') or ''),
                    'why': str(item.get('why', '') or ''),
                    'scope': str(item.get('scope', '') or ''),
                }
            )
        if llm_recs:
            recommendations = llm_recs

    report = {
        'meta': {
            'generated_at': utc_now_iso(),
            'path': str(root),
            'mode': 'diff' if diff else 'full',
            'goal': goal,
            'base': base,
            'head': head,
            'diff_scope': 'git_range' if diff and (base or head) else ('working_tree' if diff else 'none'),
        },
        'bundle': {
            'source_dir': str(root / '.hippocampus'),
            'metrics_loaded': bool(snapshot.metrics),
            'index_loaded': bool(snapshot.index),
            'signatures_loaded': bool(snapshot.signatures),
            'first_party_file_total': len(snapshot.first_party_paths()),
            'finding_total': len(snapshot.first_party_findings()),
        },
        'summary': summary,
        'scores': {
            **score_snapshot,
            'structure_dimensions': dimensions,
        },
        'hotspots': [
            {
                **item,
                'reason': str(item.get('fix_hint', '') or ''),
                'structure_impact': str(item.get('dominant_metric', '') or ''),
            }
            for item in hotspot_digest.get('items', [])[:8]
            if isinstance(item, dict)
        ],
        'components': components,
        'change_analysis': {
            'changed_file_total': int(score.get('changed_file_total', 0) or 0),
            'components': score.get('components', [])[:8] if isinstance(score, dict) else [],
        } if diff else {},
        'feature_analysis': {
            'goal': goal,
            'target_components': feature.get('target_components', [])[:8],
            'candidate_files': feature.get('candidate_files', [])[:10],
        } if goal else {},
        'recommendations': recommendations,
        'evidence': {
            'history_summary': history.get('summary', {}),
            'top_hotspots': hotspot_digest.get('items', [])[:5],
            'components': components[:5],
            'metrics_summary': summarize_findings(snapshot.first_party_findings()),
        },
        'graph': _graph_view(snapshot, hotspot_digest.get('items', [])),
        'artifacts': {},
    }
    advance('writing JSON, Markdown, and HTML artifacts')
    analysis_path = root / ANALYSIS_JSON_PATH
    summary_path = root / SUMMARY_MD_PATH
    viz_path = root / VIZ_HTML_PATH
    write_json(analysis_path, report)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_summary_markdown(report), encoding='utf-8')
    viz_path.parent.mkdir(parents=True, exist_ok=True)
    viz_path.write_text(render_viz_html(report), encoding='utf-8')
    report['artifacts'] = {
        'analysis_json': str(analysis_path),
        'summary_md': str(summary_path),
        'viz_html': str(viz_path),
    }
    write_json(analysis_path, report)
    return report
