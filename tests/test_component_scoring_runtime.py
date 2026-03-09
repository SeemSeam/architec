from __future__ import annotations

from pathlib import Path

from architec.component_scoring_runtime import (
    build_component_entries,
    llm_payload_from_components,
    update_component_registry,
)
from architec.io_utils import read_json


def test_build_component_entries_produces_sorted_scores() -> None:
    comp_stats = {
        "a:core": {
            "changed_files": ["a.py"],
            "added": 10,
            "deleted": 2,
            "critical": 1,
            "warning": 0,
            "info": 0,
            "hotspot_refs": [],
        },
        "b:core": {
            "changed_files": ["b.py"],
            "added": 2,
            "deleted": 0,
            "critical": 0,
            "warning": 0,
            "info": 0,
            "hotspot_refs": [],
        },
    }
    descriptors = {
        "a:core": {"layer_role": "orchestration", "confidence": 0.8, "dependency_neighbors": []},
        "b:core": {"layer_role": "domain", "confidence": 0.7, "dependency_neighbors": []},
    }
    entries = build_component_entries(comp_stats=comp_stats, descriptors=descriptors)
    assert len(entries) == 2
    assert entries[0]["component"] == "a:core"
    assert entries[0]["score"] <= entries[1]["score"]


def test_update_component_registry_writes_history(tmp_path: Path) -> None:
    registry_path = tmp_path / ".hippocampus" / "architect-component-registry.json"
    components = [
        {
            "component": "a:core",
            "score": 50.0,
            "grade": "D",
            "findings": {"critical": 1, "warning": 2},
            "churn": {"total": 12},
        }
    ]
    out = update_component_registry(
        registry_path=registry_path,
        components=components,
        registry={},
    )
    assert out[0]["trend"] == "flat"
    data = read_json(registry_path, default={})
    assert data["components"]["a:core"]["last_score"] == 50.0


def test_llm_payload_from_components_limit() -> None:
    components = [
        {"component": "a", "score": 1, "grade": "E", "recommendation": "block", "findings": {"critical": 1, "warning": 0}, "churn": {"total": 3}},
        {"component": "b", "score": 2, "grade": "E", "recommendation": "block", "findings": {"critical": 2, "warning": 0}, "churn": {"total": 4}},
    ]
    payload = llm_payload_from_components(components, limit=1)
    assert len(payload["components"]) == 1
    assert payload["components"][0]["component"] == "a"

