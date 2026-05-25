from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

from architec.support.io_utils import read_json, write_json


T = TypeVar("T")


def _file_signature(path: Path) -> dict[str, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return {"mtime_ns": int(stat.st_mtime_ns), "size": int(stat.st_size)}


def _cache_version(cache: object) -> int:
    if not isinstance(cache, dict):
        return 0
    try:
        return int(cache.get("version", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _cache_files(cache: object, *, version: int) -> dict[str, Any]:
    if not isinstance(cache, dict) or _cache_version(cache) != version:
        return {}
    files = cache.get("files", {})
    return files if isinstance(files, dict) else {}


def _decode_cached_items(
    entry: object,
    *,
    signature: dict[str, int],
    decode_item: Callable[[object], T | None],
) -> list[T] | None:
    if not isinstance(entry, dict) or entry.get("signature") != signature:
        return None
    raw_items = entry.get("candidates", [])
    if not isinstance(raw_items, list):
        return None
    items: list[T] = []
    for raw_item in raw_items:
        item = decode_item(raw_item)
        if item is None:
            return None
        items.append(item)
    return items


def collect_file_scan_cache(
    root: Path,
    *,
    cache_path: Path,
    version: int,
    python_files: Iterable[Path],
    collect_file: Callable[[Path, Path], list[T]],
    encode_item: Callable[[T], dict[str, Any]],
    decode_item: Callable[[object], T | None],
) -> tuple[list[T], dict[str, int]]:
    resolved_cache_path = cache_path if cache_path.is_absolute() else root / cache_path
    cached_files = _cache_files(read_json(resolved_cache_path, default={}), version=version)

    out: list[T] = []
    next_files: dict[str, Any] = {}
    hit_total = 0
    miss_total = 0
    for path in python_files:
        try:
            relpath = path.relative_to(root).as_posix()
        except ValueError:
            relpath = path.as_posix()
        signature = _file_signature(path)
        if signature is None:
            continue
        items = _decode_cached_items(
            cached_files.get(relpath, {}),
            signature=signature,
            decode_item=decode_item,
        )
        if items is None:
            items = collect_file(path, root)
            miss_total += 1
        else:
            hit_total += 1
        out.extend(items)
        next_files[relpath] = {
            "signature": signature,
            "candidates": [encode_item(item) for item in items],
        }

    if miss_total or set(cached_files) != set(next_files):
        try:
            write_json(
                resolved_cache_path,
                {
                    "version": version,
                    "files": next_files,
                },
            )
        except Exception:
            pass
    return out, {
        "file_total": len(next_files),
        "file_cache_hit_total": hit_total,
        "file_cache_miss_total": miss_total,
    }
