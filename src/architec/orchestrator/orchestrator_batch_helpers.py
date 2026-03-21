from __future__ import annotations

from typing import Any

from ..scoring.component_selection_policy import is_infra_component


def allowed_component(
    component: str,
    *,
    allow_infra: bool,
    allow_tests: bool,
    descriptors: dict[str, dict[str, Any]],
) -> bool:
    if not component or component == "unknown":
        return False
    if not allow_tests and component.endswith(":tests"):
        return False
    if not allow_infra and is_infra_component(component, descriptors.get(component, {})):
        return False
    return True


def neighbor_components(descriptor: dict[str, Any]) -> list[str]:
    neighbors = descriptor.get("dependency_neighbors", []) if isinstance(descriptor, dict) else []
    if not isinstance(neighbors, list):
        return []
    return [
        str(item.get("target_component", "") or "")
        for item in neighbors[:4]
        if isinstance(item, dict)
    ]


def batch_why(
    *,
    component: dict[str, Any],
    score_item: dict[str, Any],
    descriptor: dict[str, Any],
) -> dict[str, Any]:
    return {
        "feature_score": component.get("score", 0),
        "component_score": score_item.get("score", None),
        "component_recommendation": score_item.get("recommendation", ""),
        "layer_role": str(descriptor.get("layer_role", "") or ""),
        "descriptor_confidence": float(descriptor.get("confidence", 0.0) or 0.0),
        "neighbor_components": neighbor_components(descriptor),
    }


def normalize_evidence_paths(raw: object, *, limit: int = 6) -> list[str]:
    if not isinstance(raw, list):
        return []
    ordered: list[str] = []
    for value in raw:
        text = str(value or "")
        if text and text not in ordered:
            ordered.append(text)
        if len(ordered) >= limit:
            break
    return ordered


def feature_target_context(
    component: dict[str, Any],
    *,
    comp_to_score: dict[str, dict[str, Any]],
    descriptors: dict[str, dict[str, Any]],
) -> tuple[str, list[str], dict[str, Any], dict[str, Any]]:
    cname = str(component.get("component", "") or "")
    evidence_paths = normalize_evidence_paths(component.get("evidence_paths", []))
    return (
        cname,
        evidence_paths,
        comp_to_score.get(cname, {}),
        descriptors.get(cname, {}),
    )


def select_fallback_component(
    *,
    score_candidates: list[dict[str, Any]],
    qa_component: str,
    allow_infra: bool,
    allow_tests: bool,
    descriptors: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    if allowed_component(
        qa_component,
        allow_infra=allow_infra,
        allow_tests=allow_tests,
        descriptors=descriptors,
    ) and qa_component in descriptors:
        return qa_component, {}
    for item in score_candidates:
        candidate = str(item.get("component", "") or "")
        if allowed_component(
            candidate,
            allow_infra=allow_infra,
            allow_tests=allow_tests,
            descriptors=descriptors,
        ):
            return candidate, item
    return "", {}


def hotspot_paths(history: dict[str, Any]) -> list[str]:
    hotspots = history.get("hotspots", []) if isinstance(history.get("hotspots"), list) else []
    ordered: list[str] = []
    for item in hotspots:
        if not isinstance(item, dict):
            continue
        text = str(item.get("path", "") or "")
        if text and text not in ordered:
            ordered.append(text)
        if len(ordered) >= 24:
            break
    return ordered


def normalized_components(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items = payload.get(key, [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def sorted_score_candidates(risky_components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        risky_components,
        key=lambda item: (
            0 if str(item.get("recommendation", "")) == "block" else 1,
            float(item.get("score", 100.0) or 100.0),
        ),
    )
