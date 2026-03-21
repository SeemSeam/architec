from __future__ import annotations

from pathlib import Path
from typing import Any

from ..descriptors.public import load_or_build_component_descriptors
from .feature_advisor_llm import llm_feature_enhancement
from .feature_advisor_ranking import rank_candidate_files
from .feature_advisor_targets import collect_related_hotspots, select_target_components
from .feature_query import aggregate_component_candidate_scores
from ..integration.hippo_adapter import HippoSnapshot
from ..support.io_utils import utc_now_iso, write_json
from ..support.llm_guard import guard_llm_result
from ..integration.paths import FEATURE_REPORT_PATH


def _rank_candidate_files(snapshot: HippoSnapshot, goal: str, top_n: int = 20) -> list[dict[str, Any]]:
    return rank_candidate_files(
        snapshot,
        goal,
        descriptor_loader=load_or_build_component_descriptors,
        top_n=top_n,
    )


def _llm_feature_enhancement(
    project_root: Path,
    *,
    goal: str,
    target_components: list[dict[str, Any]],
    candidate_files: list[dict[str, Any]],
    related_hotspots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    return llm_feature_enhancement(
        project_root,
        goal=goal,
        target_components=target_components,
        candidate_files=candidate_files,
        related_hotspots=related_hotspots,
    )


def suggest_feature_architecture(
    project_root: str | Path,
    goal: str,
    *,
    llm_enabled: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    snapshot = HippoSnapshot.load(root)
    descriptors = load_or_build_component_descriptors(root, snapshot=snapshot, persist=False)

    candidates = _rank_candidate_files(snapshot, goal, top_n=28)
    comp_rank, comp_evidence = aggregate_component_candidate_scores(candidates)
    target_components = select_target_components(
        goal=goal,
        comp_rank=comp_rank,
        comp_evidence=comp_evidence,
        descriptors=descriptors,
        snapshot=snapshot,
    )
    related_hotspots = collect_related_hotspots(
        snapshot=snapshot,
        candidates=candidates,
    )

    proposal = {
        "generated_at": utc_now_iso(),
        "goal": goal,
        "target_components": target_components,
        "candidate_files": candidates[:20],
        "related_hotspots": related_hotspots,
        "architecture_suggestion": {
            "principles": [
                "Keep feature entrypoint thin and push logic into focused modules.",
                "Respect existing component boundaries; avoid cross-layer shortcuts.",
                "Prefer additive interfaces over editing large hotspot files directly.",
            ],
            "phases": [
                {
                    "phase": "P0",
                    "goal": "Design boundary and contracts before coding",
                    "actions": [
                        "Define target component ownership and public interface.",
                        "List data flow between components and reject boundary-violating edges.",
                        "Write tests for interface contract before implementation.",
                    ],
                },
                {
                    "phase": "P1",
                    "goal": "Implement minimal vertical slice",
                    "actions": [
                        "Implement core path in one component with adapters at boundaries.",
                        "Avoid adding branches in existing hotspot functions when possible.",
                        "Keep PR small and observable.",
                    ],
                },
                {
                    "phase": "P2",
                    "goal": "Harden and reduce structural debt",
                    "actions": [
                        "Refactor duplicated logic into shared abstractions.",
                        "Add architecture contract checks and component-level score gate.",
                        "Document ownership and extension points.",
                    ],
                },
            ],
            "quality_gates": [
                "No new critical findings in touched files.",
                "No increase of hard-threshold complexity on touched functions.",
                "Changed components keep score >= 70 unless explicitly waived.",
            ],
        },
    }
    if llm_enabled:
        llm_part = guard_llm_result(
            root,
            task="architect_feature",
            runner=lambda: _llm_feature_enhancement(
                root,
                goal=goal,
                target_components=target_components,
                candidate_files=candidates[:20],
                related_hotspots=related_hotspots,
            ),
        )
        proposal["llm_enhancement"] = llm_part

    write_json(root / FEATURE_REPORT_PATH, proposal)
    return proposal
