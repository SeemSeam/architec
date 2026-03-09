from __future__ import annotations

import json
from typing import Any, Callable


def _values_from_parsed_scope(parsed: Any) -> list[str]:
    values: list[str] = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, str):
                values.append(item)
            elif isinstance(item, dict):
                values.append(str(item.get("path", "") or ""))
        return values
    if isinstance(parsed, dict):
        maybe_paths = parsed.get("paths", [])
        if isinstance(maybe_paths, list):
            return [item for item in maybe_paths if isinstance(item, str)]
    return values


def _parse_scope_values(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    values = _values_from_parsed_scope(parsed)
    if values:
        return values
    separator = "\n" if "\n" in raw else ","
    return [part.strip() for part in raw.split(separator) if part.strip()]


def changed_files_from_env_scope(
    raw: str,
    *,
    normalize_path: Callable[[str], str],
) -> list[dict[str, Any]]:
    values = _parse_scope_values(str(raw or "").strip())
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in values:
        path = normalize_path(item)
        if not path or path in seen:
            continue
        seen.add(path)
        out.append({"path": path, "added": 0, "deleted": 0})
    return out

