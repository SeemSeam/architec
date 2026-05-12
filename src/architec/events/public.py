from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EVENT_FILE = "review-events.jsonl"
DEFAULT_ROTATE_BYTES = 10 * 1024 * 1024


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _event_timestamp(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _top_concern_event(concern: dict[str, Any]) -> dict[str, Any]:
    return {
        "concern_id": str(concern.get("concern_id", "") or ""),
        "kind": str(concern.get("kind", "") or ""),
        "level": str(concern.get("level", "") or ""),
        "confidence": concern.get("confidence", 0.0),
        "location": _dict(concern.get("location")),
    }


def build_review_event(result: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    summary = _dict(result.get("summary"))
    concerns = [item for item in _list(result.get("concerns")) if isinstance(item, dict)]
    return {
        "generated_at": _event_timestamp(now),
        "mode": str(result.get("mode", "") or ""),
        "review_type": str(result.get("review_type", "") or ""),
        "scores": _dict(result.get("scores")),
        "concern_counts": {
            "total": int(summary.get("concern_total", len(concerns)) or 0),
            "top": int(summary.get("top_concern_total", len(concerns)) or 0),
            "limit": int(summary.get("concern_limit", len(concerns)) or 0),
        },
        "top_concerns": [_top_concern_event(concern) for concern in concerns],
        "artifacts": _dict(result.get("artifacts")),
    }


def _event_paths(project_root: str | Path, *, now: datetime | None = None) -> tuple[Path, Path]:
    root = Path(project_root)
    event_dir = root / ".architec"
    active = event_dir / DEFAULT_EVENT_FILE
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m")
    rotated = event_dir / f"review-events-{stamp}.jsonl"
    return active, rotated


def _event_dir(project_root: str | Path) -> Path:
    return Path(project_root) / ".architec"


def _append_file(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("ab") as handle:
        if target.exists() and target.stat().st_size > 0:
            handle.write(b"\n")
        handle.write(data.rstrip(b"\n"))


def _rotate_if_needed(active: Path, rotated: Path, *, rotate_bytes: int) -> None:
    if not active.exists() or active.stat().st_size < rotate_bytes:
        return
    data = active.read_bytes().rstrip(b"\n")
    if data:
        _append_file(rotated, data)
    active.unlink()


def append_review_event(
    project_root: str | Path,
    result: dict[str, Any],
    *,
    now: datetime | None = None,
    rotate_bytes: int = DEFAULT_ROTATE_BYTES,
) -> Path:
    active, rotated = _event_paths(project_root, now=now)
    active.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_needed(active, rotated, rotate_bytes=rotate_bytes)
    event = build_review_event(result, now=now)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8")
    _append_file(active, line)
    return active


def _review_event_files(project_root: str | Path) -> list[Path]:
    event_dir = _event_dir(project_root)
    if not event_dir.exists():
        return []
    rotated = sorted(event_dir.glob("review-events-*.jsonl"))
    active = event_dir / DEFAULT_EVENT_FILE
    files = [*rotated]
    if active.exists():
        files.append(active)
    return files


def read_review_events(project_root: str | Path, *, limit: int = 100) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in _review_event_files(project_root):
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(item)
    if limit > 0:
        return events[-limit:]
    return events


__all__ = ["append_review_event", "build_review_event", "read_review_events"]
