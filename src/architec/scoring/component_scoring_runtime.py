from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from architec.scoring.component_scoring_payload import (
    grade,
    llm_payload_from_components as llm_payload_from_components_impl,
    recommendation,
)
from architec.scoring.component_scoring_registry import (
    descriptor_view as descriptor_view_impl,
    update_component_registry as update_component_registry_impl,
)
from architec.support.io_utils import clamp, normalize_relpath, safe_int


def structural_penalty(
    *,
    descriptor: dict[str, Any],
    critical: int,
    warning: int,
) -> float:
    if not isinstance(descriptor, dict):
        return 0.0
    layer_role = str(descriptor.get("layer_role", "") or "")
    neighbor_count = len(descriptor.get("dependency_neighbors", []) or [])
    penalty = 0.0
    if critical > 0 and layer_role in {"orchestration", "interface_adapter"}:
        penalty += 4.0
    penalty += _neighbor_penalty(
        critical=critical,
        warning=warning,
        neighbor_count=neighbor_count,
    )
    return penalty


def _neighbor_penalty(*, critical: int, warning: int, neighbor_count: int) -> float:
    if critical > 0 and neighbor_count >= 3:
        return 2.0
    if warning > 0 and neighbor_count >= 5:
        return 1.0
    return 0.0
def index_findings_by_path(findings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    findings_by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in findings:
        path = normalize_relpath(str(finding.get("path", "")))
        if path:
            findings_by_path[path].append(finding)
    return findings_by_path


def aggregate_component_stats(
    *,
    snapshot: Any,
    changed_rows: list[dict[str, Any]],
    findings_by_path: dict[str, list[dict[str, Any]]],
    hotspots_by_path: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    comp_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "changed_files": [],
            "added": 0,
            "deleted": 0,
            "critical": 0,
            "warning": 0,
            "info": 0,
            "hotspot_refs": [],
        }
    )

    for row in changed_rows:
        path = normalize_relpath(str(row.get("path", "")))
        if not path:
            continue
        component = snapshot.component_for_path(path)
        item = comp_stats[component]
        item["changed_files"].append(path)
        item["added"] += safe_int(row.get("added"), 0)
        item["deleted"] += safe_int(row.get("deleted"), 0)

        for finding in findings_by_path.get(path, []):
            sev = str(finding.get("severity", "info")).lower()
            item[sev] = int(item.get(sev, 0)) + 1

        hotspot = hotspots_by_path.get(path)
        if hotspot and len(item["hotspot_refs"]) < 8:
            item["hotspot_refs"].append(
                {
                    "path": path,
                    "score": hotspot.get("score", 0),
                    "critical": hotspot.get("critical", 0),
                    "warning": hotspot.get("warning", 0),
                }
    )
    return comp_stats


def _component_score(
    *,
    critical: int,
    warning: int,
    info: int,
    churn: int,
    descriptor: dict[str, Any],
) -> float:
    score = 100.0
    score -= min(60.0, critical * 18.0)
    score -= min(24.0, warning * 4.0)
    score -= min(10.0, info * 1.0)
    score -= min(20.0, churn * 0.04)
    score -= structural_penalty(
        descriptor=descriptor,
        critical=critical,
        warning=warning,
    )
    return clamp(score, 0.0, 100.0)


def _descriptor_view(descriptor: dict[str, Any]) -> dict[str, Any]:
    return descriptor_view_impl(descriptor)


def build_component_entries(
    *,
    comp_stats: dict[str, dict[str, Any]],
    descriptors: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    for component, stat in comp_stats.items():
        churn = int(stat["added"]) + int(stat["deleted"])
        critical = int(stat["critical"])
        warning = int(stat["warning"])
        info = int(stat["info"])
        descriptor = descriptors.get(component, {})
        score = _component_score(
            critical=critical,
            warning=warning,
            info=info,
            churn=churn,
            descriptor=descriptor,
        )
        components.append(
            {
                "component": component,
                "score": round(score, 2),
                "grade": grade(score),
                "recommendation": recommendation(score, critical),
                "changed_file_count": len(stat["changed_files"]),
                "changed_files": sorted(set(stat["changed_files"])),
                "churn": {
                    "added": int(stat["added"]),
                    "deleted": int(stat["deleted"]),
                    "total": churn,
                },
                "findings": {"critical": critical, "warning": warning, "info": info},
                "hotspot_refs": stat["hotspot_refs"],
                "descriptor": _descriptor_view(descriptor),
            }
        )
    components.sort(key=lambda x: (x["score"], -x["findings"]["critical"], x["component"]))
    return components


def update_component_registry(
    *,
    registry_path: Path,
    components: list[dict[str, Any]],
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    return update_component_registry_impl(
        registry_path=registry_path,
        components=components,
        registry=registry,
    )
def llm_payload_from_components(
    components: list[dict[str, Any]],
    limit: int = 10,
) -> dict[str, Any]:
    return llm_payload_from_components_impl(components, limit=limit)
