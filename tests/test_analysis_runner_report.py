from __future__ import annotations

from architec.analysis.analysis_runner_report import score_snapshot


def test_score_snapshot_uses_governance_overall_for_overall_score() -> None:
    snapshot = score_snapshot(
        structure_score=84.0,
        full_score={"score": 70.0},
        incremental_score={"score": 40.0},
        governance_overall={"score": 58.6},
        diff=True,
    )

    assert snapshot["overall"] == 71.3
    assert snapshot["total_average"] == 71.3
    assert snapshot["structure"] == 84.0
    assert snapshot["full"] == 70.0
    assert snapshot["incremental"] == 40.0
    assert snapshot["governance_overall"] == 58.6
