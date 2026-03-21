from __future__ import annotations

from typing import Any


def grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def recommendation(score: float, critical: int) -> str:
    if critical >= 3 or score < 40:
        return "block"
    if critical > 0 or score < 70:
        return "needs_changes"
    return "approve"


def llm_payload_from_components(
    components: list[dict[str, Any]],
    limit: int = 10,
) -> dict[str, Any]:
    return {
        "components": [_llm_component_item(c) for c in components[: max(1, limit)]]
    }


def _llm_component_item(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "component": component.get("component", ""),
        "score": component.get("score", 0),
        "grade": component.get("grade", ""),
        "recommendation": component.get("recommendation", ""),
        "critical": component.get("findings", {}).get("critical", 0),
        "warning": component.get("findings", {}).get("warning", 0),
        "churn_total": component.get("churn", {}).get("total", 0),
    }
