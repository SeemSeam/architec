from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from architec.events.public import read_review_events


SNAPSHOT_FILE = "status-snapshot.json"


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(event.get("review_type", "") or "unknown") for event in events)
    return dict(sorted(counts.items()))


def _weakening_components(events: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    kinds: dict[str, set[str]] = {}
    for event in events:
        for concern in _list(event.get("top_concerns")):
            if not isinstance(concern, dict):
                continue
            location = _dict(concern.get("location"))
            path = str(location.get("path", "") or "").strip()
            if not path:
                continue
            counts[path] += 1
            kinds.setdefault(path, set()).add(str(concern.get("kind", "") or "unknown"))
    return [
        {"path": path, "event_mentions": count, "kinds": sorted(kinds.get(path, set()))}
        for path, count in counts.most_common(limit)
    ]


def _status_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    latest = events[-1] if events else {}
    latest_counts = _dict(latest.get("concern_counts"))
    trend = {
        "event_total": len(events),
        "review_type_counts": _event_counts(events),
        "latest_generated_at": str(latest.get("generated_at", "") or ""),
        "latest_review_type": str(latest.get("review_type", "") or ""),
        "latest_concern_counts": latest_counts,
    }
    if not events:
        trend["summary"] = "No review events recorded yet."
    return {
        "mode": "status",
        "scores": _dict(latest.get("scores")),
        "snapshot": {},
        "trend": trend,
        "weakening_components": _weakening_components(events),
        "artifacts": {},
    }


def run_status_trend(project_root: str | Path) -> dict[str, Any]:
    events = read_review_events(project_root)
    result = _status_from_events(events)
    result["artifacts"]["review_event_jsonl"] = str(Path(project_root) / ".architec" / "review-events.jsonl")
    return result


def run_status_snapshot(project_root: str | Path) -> dict[str, Any]:
    result = run_status_trend(project_root)
    snapshot = {
        "created_at": _timestamp(),
        "scores": result["scores"],
        "trend": result["trend"],
        "weakening_components": result["weakening_components"],
    }
    path = Path(project_root) / ".architec" / SNAPSHOT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["snapshot"] = snapshot
    result["artifacts"]["status_snapshot_json"] = str(path)
    return result


__all__ = ["run_status_snapshot", "run_status_trend"]
