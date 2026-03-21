from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


ProgressFn = Callable[[str], None]


def emit_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def normalize_relpath(path: str) -> str:
    return str(path or "").strip().replace("\\", "/")
