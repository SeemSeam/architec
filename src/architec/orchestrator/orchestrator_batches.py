from __future__ import annotations

from typing import Any

from ..scoring.component_selection_policy import query_targets_infra, query_targets_tests
from .orchestrator_batch_helpers import (
    hotspot_paths as collect_hotspot_paths,
    normalized_components,
)
from .orchestrator_batch_builders import (
    fallback_batches,
    feature_target_batches,
    global_fallback_batch,
)


def batch_priority(feature_rank: int, score_item: dict[str, Any], descriptor: dict[str, Any]) -> str:
    recommendation = str(score_item.get("recommendation", "") or "")
    critical = int(score_item.get("findings", {}).get("critical", 0) or 0)
    layer_role = str(descriptor.get("layer_role", "") or "")
    if feature_rank == 0:
        return "high"
    if recommendation == "block" or critical > 0:
        return "high"
    if layer_role in {"orchestration", "interface_adapter"}:
        return "medium"
    return "medium" if feature_rank <= 2 else "low"


def _ordered_focus_candidates(
    *,
    evidence_paths: list[str],
    hotspot_paths: list[str],
    descriptor: dict[str, Any],
) -> list[list[str]]:
    descriptor_files = descriptor.get("files", []) if isinstance(descriptor, dict) else []
    return [
        [path for path in evidence_paths if path in hotspot_paths],
        evidence_paths,
        [path for path in descriptor_files if path in hotspot_paths],
        descriptor_files,
    ]


def _unique_non_empty(values: list[str], *, limit: int) -> list[str]:
    ordered: list[str] = []
    for value in values:
        text = str(value or "")
        if text and text not in ordered:
            ordered.append(text)
        if len(ordered) >= limit:
            break
    return ordered


def pick_focus_files(
    *,
    evidence_paths: list[str],
    hotspot_paths: list[str],
    descriptor: dict[str, Any],
) -> list[str]:
    ordered: list[str] = []
    for collection in _ordered_focus_candidates(
        evidence_paths=evidence_paths,
        hotspot_paths=hotspot_paths,
        descriptor=descriptor,
    ):
        ordered.extend(_unique_non_empty(collection[:12], limit=6))
        ordered = _unique_non_empty(ordered, limit=6)
        if len(ordered) >= 6:
            return ordered
    return ordered[:6]


def pick_change_batches(
    history: dict[str, Any],
    feature: dict[str, Any],
    score: dict[str, Any],
    *,
    descriptors: dict[str, dict[str, Any]],
    qa_component: str = "",
    goal: str = "",
) -> list[dict[str, Any]]:
    hotspot_paths = collect_hotspot_paths(history)
    allow_infra = query_targets_infra(goal)
    allow_tests = query_targets_tests(goal)

    target_components = normalized_components(feature, "target_components")
    risky_components = normalized_components(score, "components")
    comp_to_score = {str(item.get("component", "")): item for item in risky_components}

    batches = feature_target_batches(
        target_components=target_components,
        hotspot_paths=hotspot_paths,
        comp_to_score=comp_to_score,
        descriptors=descriptors,
        allow_infra=allow_infra,
        allow_tests=allow_tests,
        batch_priority_fn=batch_priority,
        pick_focus_files_fn=pick_focus_files,
    )
    if not batches:
        batches.extend(
            fallback_batches(
                risky_components=risky_components,
                comp_to_score=comp_to_score,
                qa_component=qa_component,
                hotspot_paths=hotspot_paths,
                descriptors=descriptors,
                allow_infra=allow_infra,
                allow_tests=allow_tests,
                batch_priority_fn=batch_priority,
                pick_focus_files_fn=pick_focus_files,
            )
        )

    if not batches:
        batches.append(global_fallback_batch(hotspot_paths))
    return batches
