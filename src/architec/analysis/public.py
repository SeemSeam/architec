from __future__ import annotations

from pathlib import Path
from typing import Any

from .analysis_runner_flow import (
    incremental_score as resolve_incremental_score,
    llm_summary,
    recommendations,
    topology_recommendations,
    run_diff_analysis,
    run_goal_analysis,
    structure_dimensions as build_structure_dimensions,
    structure_score as build_structure_score,
)
from .analysis_runner_report import (
    build_report,
    component_view,
    llm_recommendations,
    resolved_hotspots,
    score_snapshot,
    summary_payload,
    summary_view,
    write_report_artifacts,
)
from ..descriptors.component_graph import build_component_graph
from ..scoring.component_scoring import score_changed_components
from ..feature.feature_advisor import suggest_feature_architecture
from ..integration.hippo_adapter import HippoSnapshot
from .history_analyzer import analyze_history_and_iterate
from .hotspot_digest import build_hotspot_digest
from ..support.io_utils import ProgressFn
from .repo_topology import review_folder_topology
from ..scoring.public import evaluate_overall_score, load_scoring_policy


_llm_summary = llm_summary
_review_folder_topology = review_folder_topology


def run_analysis(
    project_root: str | Path,
    *,
    goal: str = "",
    diff: bool = False,
    base: str = "",
    head: str = "",
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    steps = 6 + (1 if diff else 0) + (1 if goal else 0)
    step = 0

    def advance(label: str) -> None:
        nonlocal step
        step += 1
        if progress is not None:
            progress(f"analysis [{step}/{steps}] {label}")

    advance("loading Hippo snapshot")
    snapshot = HippoSnapshot.load(root)
    advance("running history analysis")
    history = analyze_history_and_iterate(root, llm_enabled=True)
    if diff:
        advance("running diff component scoring")
    score = run_diff_analysis(
        root,
        diff=diff,
        base=base,
        head=head,
        runner=score_changed_components,
    )
    if goal:
        advance("running goal-driven feature analysis")
    feature = run_goal_analysis(
        root,
        goal=goal,
        runner=suggest_feature_architecture,
    )

    full_score = history.get("full_score", {}) if isinstance(history.get("full_score"), dict) else {}
    incremental_score = resolve_incremental_score(score, diff=diff)
    governance_overall = evaluate_overall_score(
        full_score=full_score,
        incremental_score=incremental_score,
        policy=load_scoring_policy(root),
    )

    advance("building hotspot digest and structural scores")
    hotspot_digest = build_hotspot_digest(
        root,
        history=history,
        score=score if isinstance(score, dict) else {},
        batches=[],
        governance={
            "full": full_score.get("score", 0.0),
            "incremental": incremental_score.get("score", 0.0),
            "overall": governance_overall.get("score", 0.0),
        },
    )
    current_hotspots = resolved_hotspots(snapshot, hotspot_digest)
    advance("reviewing folder topology and naming")
    topology = _review_folder_topology(root, snapshot=snapshot, llm_enabled=True)
    dimensions = build_structure_dimensions(history, topology=topology)
    structure_score_value = build_structure_score(full_score, dimensions)
    snapshot_scores = score_snapshot(
        structure_score=structure_score_value,
        full_score=full_score,
        incremental_score=incremental_score,
        governance_overall=governance_overall,
        diff=diff,
    )
    components = component_view(history)
    recommendations_view = recommendations(hotspot_digest, components, goal)
    recommendations_view.extend(topology_recommendations(topology))
    payload = summary_payload(
        goal=goal,
        diff=diff,
        score_snapshot=snapshot_scores,
        hotspots=current_hotspots,
        components=components,
        feature=feature,
        topology=topology,
    )

    advance("requesting LLM executive summary")
    llm_summary_value = _llm_summary(root, payload=payload) or {}
    summary = summary_view(llm_summary_value)
    llm_recs = llm_recommendations(llm_summary_value)
    if llm_recs:
        recommendations_view = llm_recs

    report = build_report(
        root=root,
        snapshot=snapshot,
        history=history,
        score=score,
        feature=feature,
        goal=goal,
        diff=diff,
        base=base,
        head=head,
        dimensions=dimensions,
        score_snapshot=snapshot_scores,
        resolved_hotspots=current_hotspots,
        components=components,
        summary=summary,
        recommendations=recommendations_view,
        topology=topology,
        graph_builder=build_component_graph,
    )
    advance("writing JSON, Markdown, and HTML artifacts")
    write_report_artifacts(root, report)
    return report


__all__ = [
    "HippoSnapshot",
    "_llm_summary",
    "_review_folder_topology",
    "analyze_history_and_iterate",
    "build_component_graph",
    "build_hotspot_digest",
    "run_analysis",
    "score_changed_components",
    "suggest_feature_architecture",
]
