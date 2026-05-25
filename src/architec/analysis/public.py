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
from ..cleanup.archive import (
    archive_report_view,
    build_archive_candidates,
    write_archive_artifacts,
)
from ..cleanup.inventory import build_cleanup_inventory, build_cleanup_ledger
from ..cleanup.report import cleanup_report_view, write_cleanup_artifacts
from ..cleanup.semantic_judge import (
    run_semantic_judge,
    semantic_judge_report_view,
    write_semantic_judge_artifacts,
)
from ..advice_feedback import apply_feedback_to_recommendations, load_advice_feedback
from .history_analyzer import analyze_history_and_iterate
from .hotspot_digest import build_hotspot_digest
from ..support.io_utils import ProgressFn
from .repo_topology import review_folder_topology
from ..scoring.public import evaluate_overall_score, load_scoring_policy


_llm_summary = llm_summary
_review_folder_topology = review_folder_topology
_run_semantic_judge = run_semantic_judge


def run_analysis(
    project_root: str | Path,
    *,
    goal: str = "",
    diff: bool = False,
    base: str = "",
    head: str = "",
    advice_feedback_path: str | Path | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    steps = 9 + (1 if diff else 0) + (1 if goal else 0)
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
    advance("building cleanup inventory and ledger")
    cleanup_inventory = build_cleanup_inventory(root)
    cleanup_ledger = build_cleanup_ledger(cleanup_inventory)
    cleanup = cleanup_report_view(cleanup_inventory, cleanup_ledger)
    archive_candidates = build_archive_candidates(cleanup_inventory)
    archive = archive_report_view(archive_candidates)
    advance("running semantic cleanup judge")
    semantic_judge_result = _run_semantic_judge(
        root,
        cleanup_inventory=cleanup_inventory,
        archive_candidates=archive_candidates,
        llm_enabled=True,
        fail_open=True,
    )
    semantic_judge = semantic_judge_report_view(semantic_judge_result)
    components = component_view(history)
    dimensions = build_structure_dimensions(
        history,
        topology=topology,
        hotspot_digest=hotspot_digest,
        components=components,
        cleanup=cleanup,
        archive_candidates=archive,
        semantic_judge=semantic_judge,
    )
    structure_score_value = build_structure_score(full_score, dimensions)
    snapshot_scores = score_snapshot(
        structure_score=structure_score_value,
        full_score=full_score,
        incremental_score=incremental_score,
        governance_overall=governance_overall,
        diff=diff,
    )
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
    advice_feedback = load_advice_feedback(advice_feedback_path) if advice_feedback_path else None
    recommendations_view, advice_feedback_summary = apply_feedback_to_recommendations(
        recommendations_view,
        advice_feedback,
    )

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
        cleanup=cleanup,
        archive_candidates=archive,
        semantic_judge=semantic_judge,
        cleanup_inventory=cleanup_inventory,
        graph_builder=build_component_graph,
    )
    if advice_feedback_summary:
        report.setdefault("artifacts", {})["advice_feedback"] = advice_feedback_summary
    advance("writing cleanup and semantic artifacts")
    report.setdefault("artifacts", {}).update(
        {
            **write_cleanup_artifacts(
                root,
                inventory=cleanup_inventory,
                ledger=cleanup_ledger,
            ),
            **write_archive_artifacts(
                root,
                archive_candidates=archive_candidates,
            ),
            **write_semantic_judge_artifacts(
                root,
                semantic_judge=semantic_judge_result,
            ),
        }
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
