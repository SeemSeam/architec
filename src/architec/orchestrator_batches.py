from __future__ import annotations

from typing import Any

from .component_selection_policy import (
    is_infra_component,
    query_targets_infra,
    query_targets_tests,
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


def pick_focus_files(
    *,
    evidence_paths: list[str],
    hotspot_paths: list[str],
    descriptor: dict[str, Any],
) -> list[str]:
    descriptor_files = descriptor.get("files", []) if isinstance(descriptor, dict) else []
    ordered: list[str] = []
    for collection in (
        [path for path in evidence_paths if path in hotspot_paths],
        evidence_paths,
        [path for path in descriptor_files if path in hotspot_paths],
        descriptor_files,
    ):
        for path in collection[:12]:
            text = str(path or "")
            if text and text not in ordered:
                ordered.append(text)
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
    hotspots = history.get("hotspots", []) if isinstance(history.get("hotspots"), list) else []
    hotspot_paths = [h.get("path", "") for h in hotspots if isinstance(h, dict)]
    allow_infra = query_targets_infra(goal)
    allow_tests = query_targets_tests(goal)

    target_components = feature.get("target_components", [])
    target_components = [x for x in target_components if isinstance(x, dict)]
    risky_components = score.get("components", [])
    risky_components = [x for x in risky_components if isinstance(x, dict)]
    comp_to_score = {str(c.get("component", "")): c for c in risky_components}

    batches: list[dict[str, Any]] = []
    for idx, comp in enumerate(target_components[:3], start=1):
        cname = str(comp.get("component", ""))
        if not cname or cname == "unknown":
            continue
        if not allow_tests and cname.endswith(":tests"):
            continue
        if not allow_infra and is_infra_component(cname, descriptors.get(cname, {})):
            continue
        evid = comp.get("evidence_paths", []) if isinstance(comp.get("evidence_paths"), list) else []
        score_item = comp_to_score.get(cname, {})
        descriptor = descriptors.get(cname, {})
        focus = pick_focus_files(
            evidence_paths=evid,
            hotspot_paths=hotspot_paths,
            descriptor=descriptor,
        )
        priority = batch_priority(idx - 1, score_item, descriptor)
        batches.append(
            {
                "batch": f"B{idx}",
                "component": cname,
                "priority": priority,
                "focus_files": focus,
                "why": {
                    "feature_score": comp.get("score", 0),
                    "component_score": score_item.get("score", None),
                    "component_recommendation": score_item.get("recommendation", ""),
                    "layer_role": str(descriptor.get("layer_role", "") or ""),
                    "descriptor_confidence": float(descriptor.get("confidence", 0.0) or 0.0),
                    "neighbor_components": [
                        str(item.get("target_component", "") or "")
                        for item in descriptor.get("dependency_neighbors", [])[:4]
                        if isinstance(item, dict)
                    ],
                },
                "change_strategy": [
                    "Extract one responsibility at a time from hotspot function/module.",
                    "Keep public behavior stable via characterization tests before refactor.",
                    "Enforce boundary by introducing explicit interface or adapter.",
                ],
            }
        )

    if not batches:
        score_candidates = sorted(
            risky_components,
            key=lambda item: (
                0 if str(item.get("recommendation", "")) == "block" else 1,
                float(item.get("score", 100.0) or 100.0),
            ),
        )
        fallback_component = ""
        fallback_score: dict[str, Any] = {}
        if (
            qa_component
            and qa_component in descriptors
            and (allow_tests or not qa_component.endswith(":tests"))
            and (allow_infra or not is_infra_component(qa_component, descriptors.get(qa_component, {})))
        ):
            fallback_component = qa_component
            fallback_score = comp_to_score.get(qa_component, {})
        else:
            for item in score_candidates:
                candidate = str(item.get("component", "") or "")
                if not candidate or candidate == "unknown":
                    continue
                if not allow_tests and candidate.endswith(":tests"):
                    continue
                if not allow_infra and is_infra_component(candidate, descriptors.get(candidate, {})):
                    continue
                fallback_component = candidate
                fallback_score = item
                break
        if fallback_component:
            descriptor = descriptors.get(fallback_component, {})
            focus = pick_focus_files(
                evidence_paths=[
                    str(path or "")
                    for path in fallback_score.get("changed_files", [])[:6]
                    if str(path or "")
                ],
                hotspot_paths=hotspot_paths,
                descriptor=descriptor,
            )
            batches.append(
                {
                    "batch": "B1",
                    "component": fallback_component,
                    "priority": batch_priority(0, fallback_score, descriptor),
                    "focus_files": focus,
                    "why": {
                        "note": "fallback from scoring/qa when feature targets are empty",
                        "component_score": fallback_score.get("score", None),
                        "component_recommendation": fallback_score.get("recommendation", ""),
                        "layer_role": str(descriptor.get("layer_role", "") or ""),
                        "descriptor_confidence": float(descriptor.get("confidence", 0.0) or 0.0),
                    },
                    "change_strategy": [
                        "Stabilize the highest-risk component before broader refactors.",
                        "Use descriptor/test anchors to define the first safe refactor cut.",
                    ],
                }
            )

    if not batches:
        batches.append(
            {
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
        )
    return batches
