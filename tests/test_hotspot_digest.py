from __future__ import annotations

from pathlib import Path

from architec.analysis.hotspot_digest import HOTSPOT_DIGEST_PATH, build_hotspot_digest
from architec.support.io_utils import read_json


def test_build_hotspot_digest_writes_topk_file(tmp_path: Path) -> None:
    history = {
        "hotspots": [
            {"path": "a.py", "critical": 3, "warning": 2, "score": 20.0},
            {"path": "b.py", "critical": 1, "warning": 1, "score": 15.0},
            {"path": "c.py", "critical": 0, "warning": 4, "score": 12.0},
        ]
    }
    score = {
        "components": [
            {
                "component": "x:core",
                "score": 35.0,
                "hotspot_refs": [
                    {"path": "a.py", "score": 22.0, "critical": 3, "warning": 2},
                    {"path": "b.py", "score": 16.0, "critical": 1, "warning": 1},
                ],
            }
        ]
    }
    batches = [{"priority": "high", "component": "x:core", "focus_files": ["a.py"]}]

    out = build_hotspot_digest(
        tmp_path,
        history=history,
        score=score,
        batches=batches,
        governance={"full": 60.0, "incremental": 40.0, "overall": 52.0},
        topk=3,
    )
    assert out["topk"] == 3
    assert len(out["items"]) == 3
    assert out["items"][0]["path"] == "a.py"
    assert out["items"][2]["path"] == "c.py"
    assert out["items"][2]["component_score"] is None

    stored = read_json(tmp_path / HOTSPOT_DIGEST_PATH, default={})
    assert stored.get("topk") == 3
    assert len(stored.get("items", [])) == 3


def test_build_hotspot_digest_includes_rank_breakdown_and_metric_hint(
    tmp_path: Path,
) -> None:
    history = {
        "hotspots": [
            {
                "path": "src/big_module.py",
                "critical": 1,
                "warning": 2,
                "score": 18.0,
                "top_metrics": {"module_lines": 290.0, "cyclomatic_complexity": 22.0},
            }
        ]
    }
    out = build_hotspot_digest(
        tmp_path,
        history=history,
        score={"components": []},
        batches=[],
        governance={"full": 70.0, "incremental": 68.0, "overall": 69.0},
        topk=1,
    )
    item = out["items"][0]
    breakdown = item.get("rank_breakdown", {})
    assert isinstance(breakdown, dict)
    assert breakdown.get("base_signal") == 30.0
    assert breakdown.get("test_penalty") == 0.0
    assert item.get("dominant_metric") == "module_lines"
    assert "Split oversized module" in item.get("fix_hint", "")


def test_build_hotspot_digest_deweights_test_like_paths(tmp_path: Path) -> None:
    history = {
        "hotspots": [
            {"path": "tests/test_navigation.py", "critical": 2, "warning": 0, "score": 16.0},
            {"path": "src/navigation.py", "critical": 2, "warning": 0, "score": 16.0},
        ]
    }
    out = build_hotspot_digest(
        tmp_path,
        history=history,
        score={"components": []},
        batches=[],
        governance={"full": 70.0, "incremental": 70.0, "overall": 70.0},
        topk=2,
    )
    assert out["items"][0]["path"] == "src/navigation.py"
    assert out["items"][1]["path"] == "tests/test_navigation.py"
    assert out["items"][1]["rank_breakdown"]["test_penalty"] == 12.0
    assert "test file sprawl" in out["items"][1]["fix_hint"]


def test_build_hotspot_digest_deweights_javascript_spec_paths(tmp_path: Path) -> None:
    history = {
        "hotspots": [
            {"path": "src/navigation.ts", "critical": 2, "warning": 0, "score": 16.0},
            {"path": "src/navigation.spec.ts", "critical": 2, "warning": 0, "score": 16.0},
        ]
    }
    out = build_hotspot_digest(
        tmp_path,
        history=history,
        score={"components": []},
        batches=[],
        governance={"full": 70.0, "incremental": 70.0, "overall": 70.0},
        topk=2,
    )
    assert out["items"][0]["path"] == "src/navigation.ts"
    assert out["items"][1]["rank_breakdown"]["test_penalty"] == 12.0


def test_build_hotspot_digest_deweights_doc_like_paths(tmp_path: Path) -> None:
    history = {
        "hotspots": [
            {"path": "docs/architecture.md", "critical": 1, "warning": 1, "score": 14.0},
            {"path": "src/architecture_runtime.py", "critical": 1, "warning": 1, "score": 14.0},
        ]
    }
    out = build_hotspot_digest(
        tmp_path,
        history=history,
        score={"components": []},
        batches=[],
        governance={"full": 70.0, "incremental": 70.0, "overall": 70.0},
        topk=2,
    )
    assert out["items"][0]["path"] == "src/architecture_runtime.py"
    assert out["items"][1]["path"] == "docs/architecture.md"
    assert out["items"][1]["rank_breakdown"]["docs_penalty"] == 6.0
