from __future__ import annotations

from architec.reporting.architecture_report_compaction import (
    compact_batches,
    compact_descriptors,
    compact_hotspots,
    llm_report_payload,
)


def test_compact_hotspots_and_batches_basic() -> None:
    hotspots = compact_hotspots(
        {"items": [{"rank": 1, "path": "a.py", "critical": 1, "warning": 2, "hotspot_score": 9.5}]}
    )
    batches = compact_batches(
        [{"batch": "B1", "component": "x:y", "priority": "high", "focus_files": ["a.py", "b.py"]}]
    )
    assert hotspots[0]["path"] == "a.py"
    assert batches[0]["focus_files"] == ["a.py", "b.py"]


def test_compact_descriptors_fallback_when_missing_descriptor() -> None:
    out = compact_descriptors(
        {},
        batches=[{"component": "x:y", "why": {"layer_role": "orchestration", "descriptor_confidence": 0.8}}],
        feature={"target_components": []},
        qa={"component": ""},
    )
    assert out[0]["component"] == "x:y"
    assert out[0]["layer_role"] == "orchestration"


def test_llm_report_payload_contains_compacted_fields() -> None:
    payload = llm_report_payload(
        goal="g",
        question="q",
        governance={"full": 1},
        hotspot_digest={"items": [{"rank": 1, "path": "a.py"}]},
        batches=[{"batch": "B1", "component": "x:y", "focus_files": ["a.py"]}],
        feature={"target_components": [{"component": "x:y", "score": 10}]},
        qa={"component": "x:y"},
        descriptors=[{"component": "x:y"}],
    )
    assert payload["goal"] == "g"
    assert payload["hotspots"][0]["path"] == "a.py"
    assert payload["feature_targets"][0]["component"] == "x:y"

