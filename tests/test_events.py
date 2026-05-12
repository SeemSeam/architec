from __future__ import annotations

import json
from datetime import datetime, timezone

from architec.events.public import append_review_event, build_review_event, read_review_events


def _review_result() -> dict[str, object]:
    return {
        "mode": "code_review",
        "review_type": "full",
        "scores": {"overall": 82.0},
        "summary": {
            "headline": "Full code review complete",
            "concern_total": 7,
            "top_concern_total": 5,
            "concern_limit": 5,
        },
        "concerns": [
            {
                "concern_id": "code-review:cleanup:1",
                "kind": "cleanup",
                "level": "caution",
                "confidence": 0.82,
                "location": {"path": "src/legacy.py", "line": 0, "symbol": "", "symbol_kind": "module"},
                "evidence": ["cleanup.category=legacy"],
            }
        ],
        "artifacts": {"analysis_json": "/tmp/.architec/architec-analysis.json"},
    }


def test_build_review_event_extracts_summary_and_top_concerns() -> None:
    now = datetime(2026, 5, 12, 3, 45, tzinfo=timezone.utc)

    event = build_review_event(_review_result(), now=now)

    assert event["generated_at"] == "2026-05-12T03:45:00Z"
    assert event["mode"] == "code_review"
    assert event["review_type"] == "full"
    assert event["scores"] == {"overall": 82.0}
    assert event["concern_counts"] == {"total": 7, "top": 5, "limit": 5}
    assert event["top_concerns"] == [
        {
            "concern_id": "code-review:cleanup:1",
            "kind": "cleanup",
            "level": "caution",
            "confidence": 0.82,
            "location": {"path": "src/legacy.py", "line": 0, "symbol": "", "symbol_kind": "module"},
        }
    ]
    assert event["artifacts"] == {"analysis_json": "/tmp/.architec/architec-analysis.json"}


def test_append_review_event_creates_local_jsonl(tmp_path) -> None:
    now = datetime(2026, 5, 12, 3, 45, tzinfo=timezone.utc)

    event_path = append_review_event(tmp_path, _review_result(), now=now)

    assert event_path == tmp_path / ".architec" / "review-events.jsonl"
    payload = json.loads(event_path.read_text(encoding="utf-8"))
    assert payload["generated_at"] == "2026-05-12T03:45:00Z"
    assert payload["concern_counts"] == {"total": 7, "top": 5, "limit": 5}


def test_append_review_event_rotates_active_file_when_size_limit_is_reached(tmp_path) -> None:
    now = datetime(2026, 5, 12, 3, 45, tzinfo=timezone.utc)
    event_dir = tmp_path / ".architec"
    event_dir.mkdir()
    active = event_dir / "review-events.jsonl"
    active.write_text('{"generated_at":"old"}\n', encoding="utf-8")

    event_path = append_review_event(tmp_path, _review_result(), now=now, rotate_bytes=1)

    rotated = event_dir / "review-events-202605.jsonl"
    assert event_path == active
    assert json.loads(rotated.read_text(encoding="utf-8")) == {"generated_at": "old"}
    assert json.loads(active.read_text(encoding="utf-8"))["generated_at"] == "2026-05-12T03:45:00Z"


def test_read_review_events_reads_rotated_then_active_and_skips_bad_lines(tmp_path) -> None:
    event_dir = tmp_path / ".architec"
    event_dir.mkdir()
    (event_dir / "review-events-202605.jsonl").write_text(
        '{"generated_at":"older","review_type":"full"}\nnot-json\n',
        encoding="utf-8",
    )
    (event_dir / "review-events.jsonl").write_text(
        '{"generated_at":"newer","review_type":"diff"}\n',
        encoding="utf-8",
    )

    events = read_review_events(tmp_path)

    assert [event["generated_at"] for event in events] == ["older", "newer"]
    assert [event["review_type"] for event in read_review_events(tmp_path, limit=1)] == ["diff"]
