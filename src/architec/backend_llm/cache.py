from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from architec.integration.paths import BACKEND_LLM_CACHE_PATH
from architec.support.io_utils import read_json, write_json


_CACHE_FILE = BACKEND_LLM_CACHE_PATH
_CACHE_VERSION = 1
_DEFAULT_MAX_ENTRIES = 256
_DISABLE_VALUES = {"0", "false", "off", "no"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_enabled() -> bool:
    raw = str(os.environ.get("ARCH_BACKEND_LLM_CACHE", "1") or "1").strip().lower()
    return raw not in _DISABLE_VALUES


def _cache_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / _CACHE_FILE


def _cache_key(task: str, tier: str, prompt: str, provider_hint: str) -> str:
    payload = {
        "task": str(task or ""),
        "tier": str(tier or ""),
        "provider": str(provider_hint or ""),
        "prompt": str(prompt or ""),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _cache_items(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("items", {}) if isinstance(data.get("items", {}), dict) else {}


def _read_cache_data(path: Path) -> dict[str, Any] | None:
    data = read_json(path, default={})
    if not isinstance(data, dict):
        return None
    if int(data.get("version", 0) or 0) != _CACHE_VERSION:
        return None
    return data


def _cache_entry(
    *,
    task: str,
    tier: str,
    provider_hint: str,
    prompt: str,
    value: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    return {
        "task": str(task or ""),
        "tier": str(tier or ""),
        "provider": str(provider_hint or ""),
        "prompt_sha256": hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest(),
        "updated_at": updated_at,
        "value": value,
    }


def _resolve_max_entries() -> int:
    raw_max = os.environ.get("ARCH_BACKEND_LLM_CACHE_MAX", "")
    if not raw_max:
        return _DEFAULT_MAX_ENTRIES
    try:
        return max(16, int(raw_max))
    except Exception:
        return _DEFAULT_MAX_ENTRIES


def _prune_items(items: dict[str, Any], *, max_entries: int) -> None:
    if len(items) <= max_entries:
        return
    ordered = sorted(
        items.items(),
        key=lambda kv: str(kv[1].get("updated_at", "") if isinstance(kv[1], dict) else ""),
    )
    for stale_key, _ in ordered[: len(items) - max_entries]:
        items.pop(stale_key, None)


def load_cached_result(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    provider_hint: str,
) -> dict[str, Any] | None:
    if not _cache_enabled():
        return None
    data = _read_cache_data(_cache_path(project_root))
    if data is None:
        return None
    entry = _cache_items(data).get(_cache_key(task, tier, prompt, provider_hint), {})
    value = entry.get("value", {}) if isinstance(entry, dict) else {}
    return dict(value) if isinstance(value, dict) and value else None


def save_cached_result(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    provider_hint: str,
    value: dict[str, Any],
) -> None:
    if not _cache_enabled() or not isinstance(value, dict) or not value:
        return
    path = _cache_path(project_root)
    data = _read_cache_data(path) or {"version": _CACHE_VERSION, "items": {}}
    items = _cache_items(data)
    items[_cache_key(task, tier, prompt, provider_hint)] = _cache_entry(
        task=task,
        tier=tier,
        provider_hint=provider_hint,
        prompt=prompt,
        value=value,
        updated_at=_utc_now_iso(),
    )
    _prune_items(items, max_entries=_resolve_max_entries())
    data["items"] = items
    write_json(path, data)


__all__ = ["load_cached_result", "save_cached_result"]
