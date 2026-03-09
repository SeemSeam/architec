from __future__ import annotations

from typing import Any


def compact_hotspots(hotspot_digest: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    items = hotspot_digest.get("items", []) if isinstance(hotspot_digest.get("items"), list) else []
    out: list[dict[str, Any]] = []
    for item in items[: max(1, limit)]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "rank": int(item.get("rank", 0) or 0),
                "path": str(item.get("path", "") or ""),
                "component": str(item.get("component", "") or ""),
                "critical": int(item.get("critical", 0) or 0),
                "warning": int(item.get("warning", 0) or 0),
                "hotspot_score": float(item.get("hotspot_score", 0.0) or 0.0),
            }
        )
    return out


def compact_batches(batches: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in batches[: max(1, limit)]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "batch": str(item.get("batch", "") or ""),
                "component": str(item.get("component", "") or ""),
                "priority": str(item.get("priority", "") or ""),
                "focus_files": [
                    str(p) for p in (item.get("focus_files", []) if isinstance(item.get("focus_files"), list) else [])[:6]
                ],
                "why": item.get("why", {}),
            }
        )
    return out


def _append_unique(components: list[str], value: str) -> None:
    if value and value not in components:
        components.append(value)


def _selected_components(
    *,
    batches: list[dict[str, Any]],
    feature: dict[str, Any],
    qa: dict[str, Any],
    limit: int,
) -> list[str]:
    selected: list[str] = []
    for item in batches:
        _append_unique(selected, str(item.get("component", "") or ""))

    targets = feature.get("target_components", []) if isinstance(feature.get("target_components"), list) else []
    for item in targets:
        if isinstance(item, dict):
            _append_unique(selected, str(item.get("component", "") or ""))

    _append_unique(selected, str(qa.get("component", "") or ""))
    return selected[: max(1, limit)]


def _fallback_descriptor(component: str, batches: list[dict[str, Any]]) -> dict[str, Any]:
    batch = next(
        (
            item
            for item in batches
            if isinstance(item, dict) and str(item.get("component", "") or "") == component
        ),
        {},
    )
    return {
        "layer_role": str(batch.get("why", {}).get("layer_role", "") or ""),
        "confidence": float(batch.get("why", {}).get("descriptor_confidence", 0.0) or 0.0),
        "responsibility_summary": "Fallback component context inferred from selected change batch.",
        "dependency_neighbors": [],
        "test_anchors": [],
    }


def _compact_descriptor_item(component: str, descriptor: dict[str, Any]) -> dict[str, Any]:
    return {
        "component": component,
        "layer_role": str(descriptor.get("layer_role", "") or ""),
        "confidence": float(descriptor.get("confidence", 0.0) or 0.0),
        "responsibility_summary": str(descriptor.get("responsibility_summary", "") or ""),
        "dependency_neighbors": [
            str(item.get("target_component", "") or "")
            for item in descriptor.get("dependency_neighbors", [])[:4]
            if isinstance(item, dict)
        ],
        "test_anchors": [
            str(path or "") for path in descriptor.get("test_anchors", [])[:4]
        ],
    }


def compact_descriptors(
    descriptors: dict[str, dict[str, Any]],
    *,
    batches: list[dict[str, Any]],
    feature: dict[str, Any],
    qa: dict[str, Any],
    limit: int = 6,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for component in _selected_components(
        batches=batches,
        feature=feature,
        qa=qa,
        limit=limit,
    ):
        descriptor = descriptors.get(component, {})
        if not isinstance(descriptor, dict) or not descriptor:
            descriptor = _fallback_descriptor(component, batches)
        out.append(_compact_descriptor_item(component, descriptor))
    return out


def llm_report_payload(
    *,
    goal: str,
    question: str,
    governance: dict[str, Any],
    hotspot_digest: dict[str, Any],
    batches: list[dict[str, Any]],
    feature: dict[str, Any],
    qa: dict[str, Any],
    descriptors: list[dict[str, Any]],
) -> dict[str, Any]:
    feature_targets = (
        feature.get("target_components", []) if isinstance(feature.get("target_components"), list) else []
    )
    return {
        "goal": goal,
        "question": question,
        "governance": governance,
        "hotspots": compact_hotspots(hotspot_digest, limit=10),
        "change_batches": compact_batches(batches, limit=6),
        "feature_targets": [
            {
                "component": str(item.get("component", "") or ""),
                "score": item.get("score", 0),
            }
            for item in feature_targets[:6]
            if isinstance(item, dict)
        ],
        "qa_component": str(qa.get("component", "") or ""),
        "component_descriptors": descriptors,
    }

