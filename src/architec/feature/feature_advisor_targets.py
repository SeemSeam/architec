from __future__ import annotations

from typing import Any

from ..scoring.component_selection_policy import (
    is_infra_component,
    query_targets_infra,
    query_targets_tests,
)
from ..scoring.contract_engine import aggregate_hotspots


def _component_entry(
    component: str,
    score: float,
    comp_evidence: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        "component": component,
        "score": round(float(score), 2),
        "evidence_paths": comp_evidence.get(component, [])[:6],
    }


def _component_allowed(
    component: str,
    *,
    allow_infra: bool,
    allow_tests: bool,
    descriptors: dict[str, dict[str, Any]],
) -> bool:
    if not allow_tests and component.endswith(":tests"):
        return False
    if allow_infra:
        return True
    return not is_infra_component(component, descriptors.get(component, {}))


def _ranked_candidates(
    ranked_components: list[tuple[str, float]],
    *,
    comp_evidence: dict[str, list[str]],
    descriptors: dict[str, dict[str, Any]],
    allow_infra: bool,
    allow_tests: bool,
    min_score: float | None,
    limit: int,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for component, score in ranked_components:
        if not _component_allowed(
            component,
            allow_infra=allow_infra,
            allow_tests=allow_tests,
            descriptors=descriptors,
        ):
            continue
        if min_score is not None and score < min_score:
            continue
        targets.append(_component_entry(component, score, comp_evidence))
        if len(targets) >= limit:
            break
    return targets


def _hotspot_fallback_candidates(
    *,
    snapshot,
    descriptors: dict[str, dict[str, Any]],
    allow_infra: bool,
    allow_tests: bool,
) -> list[dict[str, Any]]:
    picked: set[str] = set()
    targets: list[dict[str, Any]] = []
    hotspots = aggregate_hotspots(snapshot.first_party_findings(), top_n=30)
    for spot in hotspots:
        path = str(spot.get("path", "") or "")
        component = snapshot.component_for_path(path)
        if not component or component in picked:
            continue
        if not _component_allowed(
            component,
            allow_infra=allow_infra,
            allow_tests=allow_tests,
            descriptors=descriptors,
        ):
            continue
        picked.add(component)
        targets.append(
            {
                "component": component,
                "score": round(float(spot.get("score", 0.0) or 0.0), 2),
                "evidence_paths": [path] if path else [],
            }
        )
        if len(targets) >= 3:
            break
    return targets


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
    ranked_components = sorted(
        comp_rank.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:10]
    for min_score, limit in ((8.0, 6), (4.0, 3), (None, 1)):
        target_components = _ranked_candidates(
            ranked_components,
            comp_evidence=comp_evidence,
            descriptors=descriptors,
            allow_infra=allow_infra,
            allow_tests=allow_tests,
            min_score=min_score,
            limit=limit,
        )
        if target_components:
            return target_components
    return _hotspot_fallback_candidates(
        snapshot=snapshot,
        descriptors=descriptors,
        allow_infra=allow_infra,
        allow_tests=allow_tests,
    )


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
