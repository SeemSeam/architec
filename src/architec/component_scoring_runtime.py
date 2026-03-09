from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .io_utils import clamp, normalize_relpath, safe_int, utc_now_iso, write_json


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
    if critical > 0 and neighbor_count >= 3:
        penalty += 2.0
    elif warning > 0 and neighbor_count >= 5:
        penalty += 1.0
    return penalty


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
        score = clamp(score, 0.0, 100.0)

        components.append(
            {
                "component": component,
                "score": round(score, 2),
                "grade": grade(score),
                "recommendation": recommendation(score, critical),
                "changed_file_count": len(stat["changed_files"]),
                "changed_files": sorted(set(stat["changed_files"])),
                "churn": {"added": int(stat["added"]), "deleted": int(stat["deleted"]), "total": churn},
                "findings": {"critical": critical, "warning": warning, "info": info},
                "hotspot_refs": stat["hotspot_refs"],
                "descriptor": {
                    "layer_role": str(descriptor.get("layer_role", "") or ""),
                    "confidence": float(descriptor.get("confidence", 0.0) or 0.0),
                    "responsibility_summary": str(
                        descriptor.get("responsibility_summary", "") or ""
                    ),
                    "dependency_neighbors": [
                        str(item.get("target_component", "") or "")
                        for item in descriptor.get("dependency_neighbors", [])[:6]
                        if isinstance(item, dict)
                    ],
                    "test_anchors": [
                        str(path or "") for path in descriptor.get("test_anchors", [])[:6]
                    ],
                },
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
    data = registry.get("components", {}) if isinstance(registry.get("components"), dict) else {}
    for component in components:
        name = component["component"]
        existing = data.get(name, {}) if isinstance(data.get(name), dict) else {}
        history = existing.get("history", []) if isinstance(existing.get("history"), list) else []
        prev_score = float(existing.get("last_score", component["score"]))

        trend = "flat"
        if component["score"] > prev_score + 1.0:
            trend = "up"
        elif component["score"] < prev_score - 1.0:
            trend = "down"

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

    write_json(
        registry_path,
        {
            "generated_at": utc_now_iso(),
            "components": data,
        },
    )
    return components


def llm_payload_from_components(components: list[dict[str, Any]], limit: int = 10) -> dict[str, Any]:
    return {
        "components": [
            {
                "component": c.get("component", ""),
                "score": c.get("score", 0),
                "grade": c.get("grade", ""),
                "recommendation": c.get("recommendation", ""),
                "critical": c.get("findings", {}).get("critical", 0),
                "warning": c.get("findings", {}).get("warning", 0),
                "churn_total": c.get("churn", {}).get("total", 0),
            }
            for c in components[: max(1, limit)]
        ]
    }

