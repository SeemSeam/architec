from __future__ import annotations

import json

from architec.events.public import append_review_event
from architec.project_status.public import run_status_snapshot, run_status_trend


def _review_result(
    path: str = "src/legacy.py",
    *,
    review_type: str = "full",
    scores: dict[str, float] | None = None,
) -> dict[str, object]:
    return {
        "mode": "code_review",
        "review_type": review_type,
        "scores": scores if scores is not None else {"overall": 82.0},
        "summary": {"concern_total": 2, "top_concern_total": 1, "concern_limit": 5},
        "concerns": [
            {
                "concern_id": "code-review:cleanup:1",
                "kind": "cleanup",
                "level": "caution",
                "confidence": 0.82,
                "location": {"path": path, "line": 0, "symbol": "", "symbol_kind": "module"},
            }
        ],
        "artifacts": {},
    }


def test_status_trend_returns_empty_trend_without_events(tmp_path) -> None:
    result = run_status_trend(tmp_path)

    assert result["mode"] == "status"
    assert result["scores"] == {}
    assert result["snapshot"] == {}
    assert result["trend"]["event_total"] == 0
    assert result["trend"]["event_limit"] == 100
    assert result["trend"]["score_source"] == "none"
    assert result["trend"]["summary"] == "No review events recorded yet."
    assert result["weakening_components"] == []
    assert result["artifacts"]["review_event_jsonl"] == str(tmp_path / ".architec" / "review-events.jsonl")


def test_status_trend_reads_review_events(tmp_path) -> None:
    append_review_event(tmp_path, _review_result("src/a.py"))
    append_review_event(tmp_path, _review_result("src/a.py", review_type="diff", scores={"incremental": 70.0}))
    append_review_event(tmp_path, _review_result("src/b.py"))

    result = run_status_trend(tmp_path)

    assert result["scores"] == {"overall": 82.0}
    assert result["trend"]["event_total"] == 3
    assert result["trend"]["event_limit"] == 100
    assert result["trend"]["mode_counts"] == {"code_review": 3}
    assert result["trend"]["review_type_counts"] == {"diff": 1, "full": 2}
    assert result["trend"]["latest_review_type"] == "full"
    assert result["trend"]["score_source"] == "latest_full"
    assert result["trend"]["score_source_review_type"] == "full"
    assert result["trend"]["score_source_generated_at"]
    assert result["trend"]["latest_concern_counts"] == {"total": 2, "top": 1, "limit": 5}
    assert result["weakening_components"][0] == {
        "path": "src/a.py",
        "event_mentions": 2,
        "kinds": ["cleanup"],
    }


def test_status_scores_use_latest_full_event_not_latest_diff(tmp_path) -> None:
    append_review_event(tmp_path, _review_result("src/a.py", scores={"overall": 75.0}))
    append_review_event(tmp_path, _review_result("src/b.py", review_type="diff", scores={"incremental": 92.0}))

    result = run_status_trend(tmp_path)

    assert result["scores"] == {"overall": 75.0}
    assert result["trend"]["latest_review_type"] == "diff"
    assert result["trend"]["score_source"] == "latest_full"
    assert result["trend"]["score_source_review_type"] == "full"


def test_status_scores_empty_without_full_event(tmp_path) -> None:
    append_review_event(tmp_path, _review_result("src/a.py", review_type="diff", scores={"incremental": 92.0}))
    append_review_event(tmp_path, _review_result("src/b.py", review_type="since", scores={"incremental": 88.0}))

    result = run_status_trend(tmp_path)

    assert result["scores"] == {}
    assert result["trend"]["score_source"] == "none"
    assert result["trend"]["score_source_review_type"] == ""
    assert result["trend"]["summary"] == "No full code-review event is available for status scores."


def test_status_weakening_components_sort_by_count_desc_then_path(tmp_path) -> None:
    append_review_event(tmp_path, _review_result("src/b.py"))
    append_review_event(tmp_path, _review_result("src/a.py"))
    append_review_event(tmp_path, _review_result("src/c.py"))
    append_review_event(tmp_path, _review_result("src/c.py"))

    result = run_status_trend(tmp_path)

    assert [item["path"] for item in result["weakening_components"]] == [
        "src/c.py",
        "src/a.py",
        "src/b.py",
    ]


def test_status_trend_reads_latest_100_events(tmp_path) -> None:
    for index in range(105):
        append_review_event(
            tmp_path,
            _review_result(
                f"src/{index:03d}.py",
                scores={"overall": float(index)},
            ),
        )

    result = run_status_trend(tmp_path)

    assert result["trend"]["event_total"] == 100
    assert result["trend"]["event_limit"] == 100
    assert result["scores"] == {"overall": 104.0}
    assert all(item["path"] != "src/000.py" for item in result["weakening_components"])


def test_status_trend_counts_fix_advice_events_without_using_scores(tmp_path) -> None:
    append_review_event(tmp_path, _review_result("src/a.py", scores={"overall": 77.0}))
    append_review_event(
        tmp_path,
        {
            "mode": "fix_advice",
            "review_type": "",
            "scores": {"overall": 1.0},
            "summary": {"concern_total": 0, "top_concern_total": 0, "concern_limit": 0},
            "concerns": [],
            "artifacts": {},
        },
    )

    result = run_status_trend(tmp_path)

    assert result["scores"] == {"overall": 77.0}
    assert result["trend"]["mode_counts"] == {"code_review": 1, "fix_advice": 1}
    assert result["trend"]["review_type_counts"] == {"full": 1, "unknown": 1}


def test_status_snapshot_writes_snapshot_artifact(tmp_path) -> None:
    append_review_event(tmp_path, _review_result("src/a.py"))

    result = run_status_snapshot(tmp_path)

    path = tmp_path / ".architec" / "status-snapshot.json"
    assert result["artifacts"]["status_snapshot_json"] == str(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["scores"] == {"overall": 82.0}
    assert payload["trend"]["event_total"] == 1
    assert result["snapshot"]["scores"] == {"overall": 82.0}
