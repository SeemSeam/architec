from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import read_json, write_json
from .paths import BACKEND_LLM_CACHE_PATH


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
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return digest


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
    path = _cache_path(project_root)
    data = read_json(path, default={})
    if not isinstance(data, dict):
        return None
    if int(data.get("version", 0) or 0) != _CACHE_VERSION:
        return None
    items = data.get("items", {}) if isinstance(data.get("items", {}), dict) else {}
    key = _cache_key(task, tier, prompt, provider_hint)
    entry = items.get(key, {}) if isinstance(items.get(key, {}), dict) else {}
    value = entry.get("value", {}) if isinstance(entry.get("value", {}), dict) else {}
    if not value:
        return None
    return dict(value)


def save_cached_result(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    provider_hint: str,
    value: dict[str, Any],
) -> None:
    if not _cache_enabled():
        return
    if not isinstance(value, dict) or not value:
        return
    path = _cache_path(project_root)
    data = read_json(path, default={})
    if not isinstance(data, dict) or int(data.get("version", 0) or 0) != _CACHE_VERSION:
        data = {"version": _CACHE_VERSION, "items": {}}

    items = data.get("items", {}) if isinstance(data.get("items", {}), dict) else {}
    key = _cache_key(task, tier, prompt, provider_hint)
    now = _utc_now_iso()
    items[key] = {
        "task": str(task or ""),
        "tier": str(tier or ""),
        "provider": str(provider_hint or ""),
        "prompt_sha256": hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest(),
        "updated_at": now,
        "value": value,
    }

    max_entries = _DEFAULT_MAX_ENTRIES
    raw_max = os.environ.get("ARCH_BACKEND_LLM_CACHE_MAX", "")
    if raw_max:
        try:
            max_entries = max(16, int(raw_max))
        except Exception:
            max_entries = _DEFAULT_MAX_ENTRIES

    if len(items) > max_entries:
        ordered = sorted(
            items.items(),
            key=lambda kv: str(
                kv[1].get("updated_at", "") if isinstance(kv[1], dict) else ""
            ),
        )
        overflow = len(items) - max_entries
        for stale_key, _ in ordered[:overflow]:
            items.pop(stale_key, None)

    data["items"] = items
    write_json(path, data)
