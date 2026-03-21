from __future__ import annotations

from typing import Any


def _hotspot_recommendation(spot: dict[str, Any]) -> dict[str, Any]:
    return {
        "priority": f"P{min(2, int(spot.get('rank', 1)) - 1)}",
        "title": str(spot.get("path", "") or ""),
        "why": str(spot.get("fix_hint", "") or ""),
        "scope": str(spot.get("component", "") or ""),
    }


def _component_recommendation(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "priority": "P1",
        "title": f"Stabilize {component.get('component', '')}",
        "why": (
            f"Component risk score {component.get('risk_score', 0.0)} "
            f"with labels {', '.join(component.get('labels', [])[:3])}."
        ),
        "scope": str(component.get("component", "") or ""),
    }


def _goal_recommendation(goal: str) -> dict[str, Any]:
    return {
        "priority": "P0",
        "title": "Keep goal-driven changes inside existing ownership boundaries",
        "why": f"Goal context: {goal}",
        "scope": "goal",
    }


def recommendations(
    hotspot_digest: dict[str, Any],
    components: list[dict[str, Any]],
    goal: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for spot in hotspot_digest.get("items", [])[:3]:
        if not isinstance(spot, dict):
            continue
        items.append(_hotspot_recommendation(spot))
    for component in components[:2]:
        if not isinstance(component, dict):
            continue
        items.append(_component_recommendation(component))
    if goal:
        items.insert(0, _goal_recommendation(goal))
    return items[:5]


def _root_topology_recommendation(topology: dict[str, Any]) -> dict[str, Any]:
    source_root = str(topology.get("source_root", "") or "")
    flat_total = int(topology.get("flat_file_total", 0) or 0)
    return {
        "priority": "P0",
        "title": f"Introduce functional subpackages under {source_root or 'source root'}",
        "why": (
            f"{source_root or 'source root'} currently has {flat_total} direct Python modules, "
            "which leaves package boundaries implicit and makes new file placement unpredictable."
        ),
        "scope": source_root or "source_root",
    }


def _group_topology_recommendation(group: dict[str, Any]) -> dict[str, Any] | None:
    naming = (
        group.get("naming_review", {})
        if isinstance(group.get("naming_review"), dict)
        else {}
    )
    name = str(naming.get("recommended_name", "") or "") or str(
        group.get("programmatic_name", "") or ""
    )
    if not name:
        return None
    return {
        "priority": "P1",
        "title": f"Create `{name}` folder for `{group.get('group_id', '')}` family",
        "why": (
            str(naming.get("reason", "") or "")
            or f"{group.get('file_count', 0)} related modules already share the same implicit domain."
        ),
        "scope": ", ".join(group.get("candidate_files", [])[:4]),
    }


def topology_recommendations(topology: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(topology, dict):
        return []
    items: list[dict[str, Any]] = []
    if bool(topology.get("needs_folder_management", False)):
        items.append(_root_topology_recommendation(topology))
    groups = topology.get("groups", []) if isinstance(topology.get("groups"), list) else []
    for group in groups[:2]:
        if not isinstance(group, dict):
            continue
        item = _group_topology_recommendation(group)
        if item is not None:
            items.append(item)
    return items[:3]
