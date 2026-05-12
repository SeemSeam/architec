from __future__ import annotations

import json

from architec.events.public import append_review_event
from architec.project_status.public import run_status_snapshot, run_status_trend


def _review_result(path: str = "src/legacy.py") -> dict[str, object]:
    return {
        "mode": "code_review",
        "review_type": "full",
        "scores": {"overall": 82.0},
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
    assert result["trend"]["summary"] == "No review events recorded yet."
    assert result["weakening_components"] == []
    assert result["artifacts"]["review_event_jsonl"] == str(tmp_path / ".architec" / "review-events.jsonl")


def test_status_trend_reads_review_events(tmp_path) -> None:
    append_review_event(tmp_path, _review_result("src/a.py"))
    append_review_event(tmp_path, {**_review_result("src/a.py"), "review_type": "diff"})
    append_review_event(tmp_path, _review_result("src/b.py"))

    result = run_status_trend(tmp_path)

    assert result["scores"] == {"overall": 82.0}
    assert result["trend"]["event_total"] == 3
    assert result["trend"]["review_type_counts"] == {"diff": 1, "full": 2}
    assert result["trend"]["latest_review_type"] == "full"
    assert result["trend"]["latest_concern_counts"] == {"total": 2, "top": 1, "limit": 5}
    assert result["weakening_components"][0] == {
        "path": "src/a.py",
        "event_mentions": 2,
        "kinds": ["cleanup"],
    }


def test_status_snapshot_writes_snapshot_artifact(tmp_path) -> None:
    append_review_event(tmp_path, _review_result("src/a.py"))

    result = run_status_snapshot(tmp_path)

    path = tmp_path / ".architec" / "status-snapshot.json"
    assert result["artifacts"]["status_snapshot_json"] == str(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["scores"] == {"overall": 82.0}
    assert payload["trend"]["event_total"] == 1
    assert result["snapshot"]["scores"] == {"overall": 82.0}
