from __future__ import annotations

from architec.orchestrator.orchestrator_batches import pick_change_batches, pick_focus_files


def test_pick_focus_files_prefers_hotspot_evidence_paths() -> None:
    focus = pick_focus_files(
        evidence_paths=["b.py", "a.py", "c.py"],
        hotspot_paths=["a.py", "x.py"],
        descriptor={"files": ["x.py", "y.py"]},
    )
    assert focus[:3] == ["a.py", "b.py", "c.py"]


def test_pick_change_batches_uses_feature_targets_first() -> None:
    batches = pick_change_batches(
        history={"hotspots": [{"path": "svc/core.py"}]},
        feature={
            "target_components": [
                {
                    "component": "svc:core",
                    "score": 12,
                    "evidence_paths": ["svc/core.py", "svc/extra.py"],
                }
            ]
        },
        score={"components": [{"component": "svc:core", "recommendation": "watch", "score": 62.0}]},
        descriptors={
            "svc:core": {
                "files": ["svc/core.py"],
                "layer_role": "domain",
                "confidence": 0.8,
                "dependency_neighbors": [{"target_component": "svc:api"}],
            }
        },
        goal="stabilize svc core",
    )
    assert batches[0]["component"] == "svc:core"
    assert batches[0]["focus_files"][0] == "svc/core.py"


def test_pick_change_batches_falls_back_to_qa_component() -> None:
    batches = pick_change_batches(
        history={"hotspots": [{"path": "svc/core.py"}]},
        feature={"target_components": []},
        score={"components": [{"component": "svc:core", "recommendation": "block", "score": 40.0}]},
        descriptors={
            "svc:core": {
                "files": ["svc/core.py"],
                "layer_role": "orchestration",
                "confidence": 0.7,
            }
        },
        qa_component="svc:core",
        goal="stabilize svc core",
    )
    assert batches[0]["component"] == "svc:core"
    assert batches[0]["priority"] == "high"
