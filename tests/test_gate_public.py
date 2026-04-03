from __future__ import annotations

import json

from architec.gate.public import run_gate
from architec.support.io_utils import write_json


def _report(*, overall: float, structure: float, full: float, cleanup_total: int, categories: dict[str, int]):
    return {
        "meta": {
            "generated_at": "2026-04-03T00:00:00+00:00",
            "path": "",
            "mode": "full",
            "goal": "",
        },
        "scores": {
            "overall": overall,
            "governance_overall": full,
            "structure": structure,
            "full": full,
            "incremental": None,
            "structure_dimensions": {},
        },
        "cleanup": {
            "candidate_total": cleanup_total,
            "review_required_total": cleanup_total,
            "by_category": categories,
            "by_kind": {"source": cleanup_total},
        },
        "artifacts": {
            "analysis_json": "/tmp/.architec/architec-analysis.json",
        },
    }


def test_run_gate_passes_when_current_snapshot_does_not_regress(tmp_path, monkeypatch) -> None:
    baseline = {
        "meta": {
            "generated_at": "2026-04-03T00:00:00+00:00",
            "path": str(tmp_path),
            "mode": "baseline",
            "source_mode": "full",
        },
        "scores": {
            "overall": 80.0,
            "structure": 82.0,
            "full": 78.0,
        },
        "cleanup": {
            "candidate_total": 4,
            "review_required_total": 4,
            "by_category": {"stale_doc": 4},
        },
    }
    write_json(tmp_path / ".architec" / "architec-baseline.json", baseline)
    monkeypatch.setattr(
        "architec.gate.public.run_analysis",
        lambda root, progress=None: _report(
            overall=82.0,
            structure=84.0,
            full=79.0,
            cleanup_total=3,
            categories={"stale_doc": 3},
        ),
    )

    result = run_gate(tmp_path)

    gate_path = tmp_path / ".architec" / "architec-gate.json"
    assert gate_path.exists()
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["gate"]["passed"] is True
    assert gate["gate"]["status"] == "pass"
    assert result["summary"]["headline"] == "Archi gate passed"
    assert result["artifacts"]["gate_json"].endswith("architec-gate.json")


def test_run_gate_warns_when_only_warn_cleanup_categories_regress(tmp_path, monkeypatch) -> None:
    baseline = {
        "meta": {
            "generated_at": "2026-04-03T00:00:00+00:00",
            "path": str(tmp_path),
            "mode": "baseline",
            "source_mode": "full",
        },
        "scores": {
            "overall": 80.0,
            "structure": 82.0,
            "full": 78.0,
        },
        "cleanup": {
            "candidate_total": 2,
            "review_required_total": 2,
            "by_category": {"stale_doc": 2},
        },
    }
    write_json(tmp_path / ".architec" / "architec-baseline.json", baseline)
    monkeypatch.setattr(
        "architec.gate.public.run_analysis",
        lambda root, progress=None: _report(
            overall=80.0,
            structure=82.0,
            full=78.0,
            cleanup_total=4,
            categories={"stale_doc": 3, "stale_config": 1},
        ),
    )

    result = run_gate(tmp_path)

    assert result["gate"]["passed"] is True
    assert result["gate"]["status"] == "warn"
    assert result["gate"]["failure_total"] == 0
    assert result["gate"]["warning_total"] >= 1
    assert result["summary"]["headline"] == "Archi gate warned"


def test_run_gate_fails_when_scores_or_blocking_cleanup_regress(tmp_path, monkeypatch) -> None:
    baseline = {
        "meta": {
            "generated_at": "2026-04-03T00:00:00+00:00",
            "path": str(tmp_path),
            "mode": "baseline",
            "source_mode": "full",
        },
        "scores": {
            "overall": 80.0,
            "structure": 82.0,
            "full": 78.0,
        },
        "cleanup": {
            "candidate_total": 2,
            "review_required_total": 2,
            "by_category": {"stale_doc": 2},
        },
    }
    write_json(tmp_path / ".architec" / "architec-baseline.json", baseline)
    monkeypatch.setattr(
        "architec.gate.public.run_analysis",
        lambda root, progress=None: _report(
            overall=79.0,
            structure=81.0,
            full=77.0,
            cleanup_total=4,
            categories={"stale_doc": 3, "fallback_branch": 1},
        ),
    )

    result = run_gate(tmp_path)

    assert result["gate"]["passed"] is False
    assert result["gate"]["status"] == "fail"
    assert result["gate"]["failure_total"] >= 1
    assert result["summary"]["headline"] == "Archi gate failed"
