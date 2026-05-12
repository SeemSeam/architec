from __future__ import annotations

import json

import architec
import architec.gate as gate_pkg
import pytest
from architec.gate.report import (
    build_gate_result,
    load_baseline_snapshot,
    write_gate_artifacts,
)
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


def _baseline(tmp_path, *, cleanup_total: int, categories: dict[str, int]) -> dict[str, object]:
    return {
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
            "candidate_total": cleanup_total,
            "review_required_total": cleanup_total,
            "by_category": categories,
        },
    }


def test_gate_wrapper_exports_are_retired() -> None:
    assert "run_gate" not in architec.__all__
    assert "run_gate" not in gate_pkg.__all__
    assert not hasattr(architec, "run_gate")
    assert not hasattr(gate_pkg, "run_gate")


def test_load_baseline_snapshot_missing_points_to_status_snapshot(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="archi status --snapshot"):
        load_baseline_snapshot(tmp_path)


def test_load_baseline_snapshot_reads_existing_legacy_snapshot(tmp_path) -> None:
    baseline = _baseline(tmp_path, cleanup_total=4, categories={"stale_doc": 4})
    write_json(tmp_path / ".architec" / "architec-baseline.json", baseline)

    assert load_baseline_snapshot(tmp_path) == baseline


def test_build_gate_result_passes_when_current_snapshot_does_not_regress() -> None:
    result = build_gate_result(
        current_report=_report(
            overall=82.0,
            structure=84.0,
            full=79.0,
            cleanup_total=3,
            categories={"stale_doc": 3},
        ),
        baseline={
            "meta": {"generated_at": "2026-04-03T00:00:00+00:00", "source_mode": "full"},
            "scores": {"overall": 80.0, "structure": 82.0, "full": 78.0},
            "cleanup": {
                "candidate_total": 4,
                "review_required_total": 4,
                "by_category": {"stale_doc": 4},
            },
        },
    )

    assert result["passed"] is True
    assert result["status"] == "pass"
    assert result["failure_total"] == 0
    assert result["warning_total"] == 0


def test_build_gate_result_warns_when_only_warn_cleanup_categories_regress(tmp_path) -> None:
    result = build_gate_result(
        current_report=_report(
            overall=80.0,
            structure=82.0,
            full=78.0,
            cleanup_total=4,
            categories={"stale_doc": 3, "stale_config": 1},
        ),
        baseline=_baseline(tmp_path, cleanup_total=2, categories={"stale_doc": 2}),
    )

    assert result["passed"] is True
    assert result["status"] == "warn"
    assert result["failure_total"] == 0
    assert result["warning_total"] >= 1


def test_build_gate_result_fails_when_scores_or_blocking_cleanup_regress(tmp_path) -> None:
    result = build_gate_result(
        current_report=_report(
            overall=79.0,
            structure=81.0,
            full=77.0,
            cleanup_total=4,
            categories={"stale_doc": 3, "fallback_branch": 1},
        ),
        baseline=_baseline(tmp_path, cleanup_total=2, categories={"stale_doc": 2}),
    )

    assert result["passed"] is False
    assert result["status"] == "fail"
    assert result["failure_total"] >= 1


def test_write_gate_artifacts_emits_legacy_report_files(tmp_path) -> None:
    result = {
        "meta": {"generated_at": "2026-04-03T00:00:00+00:00"},
        "scores": {"overall": 82.0, "structure": 84.0, "full": 79.0},
        "cleanup": {"candidate_total": 3, "review_required_total": 3},
        "gate": build_gate_result(
            current_report=_report(
                overall=82.0,
                structure=84.0,
                full=79.0,
                cleanup_total=3,
                categories={"stale_doc": 3},
            ),
            baseline=_baseline(tmp_path, cleanup_total=4, categories={"stale_doc": 4}),
        ),
    }

    artifacts = write_gate_artifacts(tmp_path, result)

    gate_path = tmp_path / ".architec" / "architec-gate.json"
    summary_path = tmp_path / ".architec" / "architec-gate-summary.md"
    assert artifacts["gate_json"] == str(gate_path)
    assert artifacts["gate_summary_md"] == str(summary_path)
    assert json.loads(gate_path.read_text(encoding="utf-8"))["gate"]["status"] == "pass"
    assert "# Architec Gate" in summary_path.read_text(encoding="utf-8")
