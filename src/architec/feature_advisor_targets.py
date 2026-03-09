from __future__ import annotations

from typing import Any

from .component_selection_policy import (
    is_infra_component,
    query_targets_infra,
    query_targets_tests,
)
from .contract_engine import aggregate_hotspots


def select_target_components(
    *,
    goal: str,
    comp_rank: dict[str, float],
    comp_evidence: dict[str, list[str]],
    descriptors: dict[str, dict[str, Any]],
    snapshot,
) -> list[dict[str, Any]]:
    allow_infra = query_targets_infra(goal)
    allow_tests = query_targets_tests(goal)
    target_components: list[dict[str, Any]] = []
    ranked_components = sorted(comp_rank.items(), key=lambda item: item[1], reverse=True)[:10]
    for comp, score in ranked_components:
        if not allow_tests and comp.endswith(":tests"):
            continue
        if not allow_infra and is_infra_component(comp, descriptors.get(comp, {})):
            continue
        if score < 8:
            continue
        target_components.append(
            {
                "component": comp,
                "score": round(float(score), 2),
                "evidence_paths": comp_evidence.get(comp, [])[:6],
            }
        )
        if len(target_components) >= 6:
            break
    if not target_components:
        for comp, score in ranked_components:
            if not allow_tests and comp.endswith(":tests"):
                continue
            if not allow_infra and is_infra_component(comp, descriptors.get(comp, {})):
                continue
            if score < 4:
                continue
            target_components.append(
                {
                    "component": comp,
                    "score": round(float(score), 2),
                    "evidence_paths": comp_evidence.get(comp, [])[:6],
                }
            )
            if len(target_components) >= 3:
                break
    if not target_components:
        for comp, score in ranked_components:
            if not allow_tests and comp.endswith(":tests"):
                continue
            if not allow_infra and is_infra_component(comp, descriptors.get(comp, {})):
                continue
            target_components.append(
                {
                    "component": comp,
                    "score": round(float(score), 2),
                    "evidence_paths": comp_evidence.get(comp, [])[:6],
                }
            )
            break
    if not target_components:
        picked: set[str] = set()
        hotspots = aggregate_hotspots(snapshot.first_party_findings(), top_n=30)
        for spot in hotspots:
            path = str(spot.get("path", "") or "")
            comp = snapshot.component_for_path(path)
            if not comp or comp in picked:
                continue
            if not allow_tests and comp.endswith(":tests"):
                continue
            if not allow_infra and is_infra_component(comp, descriptors.get(comp, {})):
                continue
            picked.add(comp)
            target_components.append(
                {
                    "component": comp,
                    "score": round(float(spot.get("score", 0.0) or 0.0), 2),
                    "evidence_paths": [path] if path else [],
                }
            )
            if len(target_components) >= 3:
                break
    return target_components


def collect_related_hotspots(
    *,
    snapshot,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hotspots = aggregate_hotspots(snapshot.first_party_findings(), top_n=30)
    hotspot_by_path = {x["path"]: x for x in hotspots}
    related_hotspots = []
    for c in candidates:
        path = str(c.get("path", ""))
        spot = hotspot_by_path.get(path)
        if not spot:
            continue
        related_hotspots.append(
            {
                "path": path,
                "critical": spot.get("critical", 0),
                "warning": spot.get("warning", 0),
                "score": spot.get("score", 0),
            }
        )
        if len(related_hotspots) >= 10:
            break
    return related_hotspots
