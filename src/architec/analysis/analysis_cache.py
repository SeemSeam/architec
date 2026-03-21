from __future__ import annotations

import hashlib
import json
from typing import Any

from architec.support.io_utils import read_json, utc_now_iso, write_json
from architec.integration.paths import ANALYSIS_CACHE_DIR


CACHE_DIR = ANALYSIS_CACHE_DIR


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def fingerprint_payload(payload: object) -> str:
    return hashlib.sha256(_stable_json(payload).encode('utf-8')).hexdigest()


def _cache_path(root: Path, namespace: str) -> Path:
    safe = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in namespace)
    return root / CACHE_DIR / f'{safe}.json'


def load_cached_analysis(root: Path, *, namespace: str, payload: object) -> dict[str, Any] | None:
    path = _cache_path(root, namespace)
    data = read_json(path, default={})
    if not isinstance(data, dict):
        return None
    if str(data.get('fingerprint', '') or '') != fingerprint_payload(payload):
        return None
    result = data.get('result')
    if not isinstance(result, dict):
        return None
    cached = dict(result)
    cached['_cache_hit'] = True
    cached['_cache_namespace'] = namespace
    return cached


def save_cached_analysis(
    root: Path,
    *,
    namespace: str,
    payload: object,
    result: dict[str, Any],
) -> None:
    path = _cache_path(root, namespace)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        path,
        {
            'generated_at': utc_now_iso(),
            'namespace': namespace,
            'fingerprint': fingerprint_payload(payload),
            'result': result,
        },
    )


def run_cached_analysis(
    root: Path,
    *,
    namespace: str,
    payload: object,
    runner,
) -> tuple[dict[str, Any] | None, bool]:
    cached = load_cached_analysis(root, namespace=namespace, payload=payload)
    if cached is not None:
        return cached, True
    result = runner()
    if isinstance(result, dict):
        save_cached_analysis(root, namespace=namespace, payload=payload, result=result)
    return result, False
