from __future__ import annotations

from typing import Any

from architec.support.io_utils import normalize_relpath


def add_unique_paths(target: list[str], seen: set[str], paths: object) -> None:
    if not isinstance(paths, dict):
        return
    for path in paths.keys():
        normalized = normalize_relpath(str(path))
        if normalized and normalized not in seen:
            seen.add(normalized)
            target.append(normalized)


def signatures_from_file_map(files: object, path: str) -> list[dict[str, Any]]:
    if not isinstance(files, dict):
        return []
    item = files.get(path)
    if not isinstance(item, dict):
        return []
    raw = item.get("signatures", [])
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]
