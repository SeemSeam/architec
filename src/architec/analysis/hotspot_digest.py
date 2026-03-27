from __future__ import annotations

import os
from typing import Any

from .hotspot_digest_rank import ranked_items, top_items
from .hotspot_digest_sources import apply_batch_refs, apply_component_refs, seed_hotspots
from ..support.path_policy import is_doc_like_path as shared_is_doc_like_path, is_test_like_path as shared_is_test_like_path
from ..support.io_utils import utc_now_iso, write_json
from ..integration.paths import HOTSPOT_DIGEST_PATH


def _topk_limit(default: int = 8) -> int:
    raw = str(os.environ.get("ARCH_HOTSPOT_TOPK", "") or "").strip()
    if not raw:
        return default
    try:
        return max(1, min(20, int(raw)))
    except Exception:
        return default


def _is_test_like_path(path: str) -> bool:
    return shared_is_test_like_path(path)


def _is_doc_like_path(path: str) -> bool:
    return shared_is_doc_like_path(path)


def build_hotspot_digest(
    root: Path,
    *,
    history: dict[str, Any],
    score: dict[str, Any],
    batches: list[dict[str, Any]],
    governance: dict[str, Any],
    topk: int | None = None,
) -> dict[str, Any]:
    limit = max(1, min(20, int(topk or _topk_limit())))
    by_path = seed_hotspots(history)
    apply_component_refs(by_path, score)
    apply_batch_refs(by_path, batches)
    top_hotspots = top_items(
        ranked_items(
            by_path,
            is_test_like_path=_is_test_like_path,
            is_doc_like_path=_is_doc_like_path,
        ),
        limit=limit,
        is_test_like_path=_is_test_like_path,
        is_doc_like_path=_is_doc_like_path,
    )

    payload = {
        "generated_at": utc_now_iso(),
        "topk": limit,
        "scores": governance,
        "items": top_hotspots,
    }
    write_json(root / HOTSPOT_DIGEST_PATH, payload)
    return payload
