from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.support.io_utils import utc_now_iso, write_json


def descriptor_view(descriptor: dict[str, Any]) -> dict[str, Any]:
    neighbors = descriptor.get("dependency_neighbors", [])
    anchors = descriptor.get("test_anchors", [])
    return {
        "layer_role": str(descriptor.get("layer_role", "") or ""),
        "confidence": float(descriptor.get("confidence", 0.0) or 0.0),
        "responsibility_summary": str(descriptor.get("responsibility_summary", "") or ""),
        "dependency_neighbors": _neighbor_targets(neighbors),
        "test_anchors": _anchor_paths(anchors),
    }


def _neighbor_targets(neighbors: object) -> list[str]:
    if not isinstance(neighbors, list):
        return []
    return [
        str(item.get("target_component", "") or "")
        for item in neighbors[:6]
        if isinstance(item, dict)
    ]


def _anchor_paths(anchors: object) -> list[str]:
    if not isinstance(anchors, list):
        return []
    return [str(path or "") for path in anchors[:6]]


def update_component_registry(
    *,
    registry_path: Path,
    components: list[dict[str, Any]],
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    data = (
        registry.get("components", {})
        if isinstance(registry.get("components"), dict)
        else {}
    )
    for component in components:
        _update_registry_component(data, component)

    write_json(
        registry_path,
        {
            "generated_at": utc_now_iso(),
            "components": data,
        },
    )
    return components


def _update_registry_component(data: dict[str, Any], component: dict[str, Any]) -> None:
    name = component["component"]
    existing = data.get(name, {}) if isinstance(data.get(name), dict) else {}
    history = existing.get("history", []) if isinstance(existing.get("history"), list) else []
    prev_score = float(existing.get("last_score", component["score"]))
    trend = _score_trend(component["score"], prev_score)

    history.append(
        {
            "ts": utc_now_iso(),
            "score": component["score"],
            "grade": component["grade"],
            "critical": component["findings"]["critical"],
            "warning": component["findings"]["warning"],
            "churn": component["churn"]["total"],
        }
    )
    data[name] = {
        "last_score": component["score"],
        "last_grade": component["grade"],
        "trend": trend,
        "history": history[-20:],
        "owner_hint": existing.get("owner_hint", ""),
    }
    component["trend"] = trend


def _score_trend(score: float, prev_score: float) -> str:
    if score > prev_score + 1.0:
        return "up"
    if score < prev_score - 1.0:
        return "down"
    return "flat"
