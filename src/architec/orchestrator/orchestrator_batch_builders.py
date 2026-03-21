from __future__ import annotations

from typing import Any

from .orchestrator_batch_helpers import (
    allowed_component,
    batch_why,
    feature_target_context,
    normalize_evidence_paths,
    select_fallback_component,
    sorted_score_candidates,
)


def feature_target_batch(
    *,
    index: int,
    component: dict[str, Any],
    hotspot_paths: list[str],
    comp_to_score: dict[str, dict[str, Any]],
    descriptors: dict[str, dict[str, Any]],
    batch_priority_fn: Any,
    pick_focus_files_fn: Any,
) -> dict[str, Any]:
    cname, evidence_paths, score_item, descriptor = feature_target_context(
        component,
        comp_to_score=comp_to_score,
        descriptors=descriptors,
    )
    return {
        "batch": f"B{index}",
        "component": cname,
        "priority": batch_priority_fn(index - 1, score_item, descriptor),
        "focus_files": pick_focus_files_fn(
            evidence_paths=evidence_paths,
            hotspot_paths=hotspot_paths,
            descriptor=descriptor,
        ),
        "why": batch_why(
            component=component,
            score_item=score_item,
            descriptor=descriptor,
        ),
        "change_strategy": [
            "Extract one responsibility at a time from hotspot function/module.",
            "Keep public behavior stable via characterization tests before refactor.",
            "Enforce boundary by introducing explicit interface or adapter.",
        ],
    }


def fallback_batch(
    *,
    component: str,
    score_item: dict[str, Any],
    hotspot_paths: list[str],
    descriptors: dict[str, dict[str, Any]],
    batch_priority_fn: Any,
    pick_focus_files_fn: Any,
) -> dict[str, Any]:
    descriptor = descriptors.get(component, {})
    evidence_paths = normalize_evidence_paths(score_item.get("changed_files", []))
    return {
        "batch": "B1",
        "component": component,
        "priority": batch_priority_fn(0, score_item, descriptor),
        "focus_files": pick_focus_files_fn(
            evidence_paths=evidence_paths,
            hotspot_paths=hotspot_paths,
            descriptor=descriptor,
        ),
        "why": {
            "note": "fallback from scoring/qa when feature targets are empty",
            "component_score": score_item.get("score", None),
            "component_recommendation": score_item.get("recommendation", ""),
            "layer_role": str(descriptor.get("layer_role", "") or ""),
            "descriptor_confidence": float(descriptor.get("confidence", 0.0) or 0.0),
        },
        "change_strategy": [
            "Stabilize the highest-risk component before broader refactors.",
            "Use descriptor/test anchors to define the first safe refactor cut.",
        ],
    }


def global_fallback_batch(hotspot_paths: list[str]) -> dict[str, Any]:
    return {
        "batch": "B1",
        "component": "global",
        "priority": "medium",
        "focus_files": hotspot_paths[:6],
        "why": {"note": "fallback when no target component inferred"},
        "change_strategy": [
            "Start from top hotspot files.",
            "Do behavior-preserving decomposition first.",
        ],
    }


def feature_target_batches(
    *,
    target_components: list[dict[str, Any]],
    hotspot_paths: list[str],
    comp_to_score: dict[str, dict[str, Any]],
    descriptors: dict[str, dict[str, Any]],
    allow_infra: bool,
    allow_tests: bool,
    batch_priority_fn: Any,
    pick_focus_files_fn: Any,
) -> list[dict[str, Any]]:
    batches: list[dict[str, Any]] = []
    for idx, component in enumerate(target_components[:3], start=1):
        cname = str(component.get("component", "") or "")
        if not allowed_component(
            cname,
            allow_infra=allow_infra,
            allow_tests=allow_tests,
            descriptors=descriptors,
        ):
            continue
        batches.append(
            feature_target_batch(
                index=idx,
                component=component,
                hotspot_paths=hotspot_paths,
                comp_to_score=comp_to_score,
                descriptors=descriptors,
                batch_priority_fn=batch_priority_fn,
                pick_focus_files_fn=pick_focus_files_fn,
            )
        )
    return batches


def fallback_batches(
    *,
    risky_components: list[dict[str, Any]],
    comp_to_score: dict[str, dict[str, Any]],
    qa_component: str,
    hotspot_paths: list[str],
    descriptors: dict[str, dict[str, Any]],
    allow_infra: bool,
    allow_tests: bool,
    batch_priority_fn: Any,
    pick_focus_files_fn: Any,
) -> list[dict[str, Any]]:
    score_candidates = sorted_score_candidates(risky_components)
    fallback_component, fallback_score = select_fallback_component(
        score_candidates=score_candidates,
        qa_component=qa_component,
        allow_infra=allow_infra,
        allow_tests=allow_tests,
        descriptors=descriptors,
    )
    if fallback_component and not fallback_score:
        fallback_score = comp_to_score.get(fallback_component, {})
    if not fallback_component:
        return []
    return [
        fallback_batch(
            component=fallback_component,
            score_item=fallback_score,
            hotspot_paths=hotspot_paths,
            descriptors=descriptors,
            batch_priority_fn=batch_priority_fn,
            pick_focus_files_fn=pick_focus_files_fn,
        )
    ]
