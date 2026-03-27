from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from architec.descriptors.component_descriptors_semantics import (
    build_responsibility_summary,
    descriptor_confidence,
    descriptor_terms,
    infer_layer_role,
)
from architec.descriptors.component_descriptors_symbols import (
    collect_component_symbols,
    findings_by_severity,
)
from architec.descriptors.component_graph import build_component_graph, component_neighbors
from architec.scoring.contract_engine import aggregate_hotspots
from architec.integration.hippo_adapter import HippoSnapshot
from architec.support.io_utils import utc_now_iso, write_json
from architec.integration.paths import COMPONENT_DESCRIPTOR_PATH


def build_component_descriptors(snapshot: HippoSnapshot) -> dict[str, dict[str, Any]]:
    findings = snapshot.first_party_findings()
    hotspots = aggregate_hotspots(findings, top_n=200)
    hotspot_by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
    findings_by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in findings:
        component = snapshot.component_for_path(str(item.get("path", "") or ""))
        if component:
            findings_by_component[component].append(item)
    for item in hotspots:
        component = snapshot.component_for_path(str(item.get("path", "") or ""))
        if component:
            hotspot_by_component[component].append(item)

    graph = build_component_graph(snapshot)
    component_files = snapshot.component_files()
    out: dict[str, dict[str, Any]] = {}
    for component, files in component_files.items():
        symbols = collect_component_symbols(snapshot, files)
        neighbors = component_neighbors(graph, component, limit=8)
        findings_bucket = findings_by_component.get(component, [])
        hotspots_bucket = hotspot_by_component.get(component, [])[:6]
        layer_role = infer_layer_role(component, files)
        descriptor = {
            "component": component,
            "file_count": len(files),
            "files": files[:24],
            "primary_symbols": symbols[:12],
            "findings_by_severity": findings_by_severity(findings_bucket),
            "top_hotspots": hotspots_bucket,
            "dependency_neighbors": neighbors,
            "test_anchors": _find_test_anchors(snapshot, component),
            "layer_role": layer_role,
            "responsibility_summary": build_responsibility_summary(
                component=component,
                files=files,
                symbols=symbols,
                neighbors=neighbors,
                layer_role=layer_role,
                hotspots=hotspots_bucket,
            ),
        }
        descriptor["descriptor_terms"] = descriptor_terms(descriptor)
        descriptor["confidence"] = descriptor_confidence(descriptor)
        out[component] = descriptor
    return out


def load_or_build_component_descriptors(
    project_root: str | Path,
    *,
    snapshot: HippoSnapshot | None = None,
    persist: bool = True,
) -> dict[str, dict[str, Any]]:
    root = Path(project_root).resolve()
    snap = snapshot or HippoSnapshot.load(root)
    descriptors = build_component_descriptors(snap)
    if persist:
        write_json(
            root / COMPONENT_DESCRIPTOR_PATH,
            {
                "generated_at": utc_now_iso(),
                "component_count": len(descriptors),
                "components": descriptors,
            },
        )
    return descriptors


def _find_test_anchors(snapshot: HippoSnapshot, component: str) -> list[str]:
    component_parts = [part for part in component.lower().replace(":", "/").split("/") if len(part) >= 4]
    anchors: list[str] = []
    test_paths_fn = getattr(snapshot, "test_support_paths", None)
    test_paths = test_paths_fn() if callable(test_paths_fn) else snapshot.first_party_paths()
    for path in test_paths:
        low = path.lower()
        if any(token in low for token in component_parts):
            anchors.append(path)
        if len(anchors) >= 8:
            break
    return anchors
