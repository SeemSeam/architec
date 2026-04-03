from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from architec.cleanup.metadata import cleanup_metadata_fields
from architec.cleanup.scope import iter_cleanup_scope
from architec.support.architecture_rules import cleanup_metadata_for_candidate, load_archi_rules
from architec.support.io_utils import clamp, normalize_relpath, safe_int, utc_now_iso

_PATH_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_TEXT_SIGNAL_LIMIT = 24000


@dataclass(frozen=True)
class CleanupRule:
    category: str
    kinds: tuple[str, ...]
    path_signals: tuple[str, ...]
    content_signals: tuple[str, ...]


_CLEANUP_RULES = (
    CleanupRule(
        category="fallback_branch",
        kinds=("source",),
        path_signals=("fallback", "degraded", "degrade"),
        content_signals=("fallback", "degraded mode", "fallback path", "temporary fallback"),
    ),
    CleanupRule(
        category="compat_layer",
        kinds=("source", "script"),
        path_signals=("compat", "shim"),
        content_signals=("backward compatible", "compatibility layer", "compat shim"),
    ),
    CleanupRule(
        category="legacy_impl",
        kinds=("source",),
        path_signals=("legacy", "deprecated", "obsolete", "old"),
        content_signals=("deprecated", "legacy implementation", "obsolete", "remove after migration"),
    ),
    CleanupRule(
        category="obsolete_script",
        kinds=("script",),
        path_signals=("legacy", "deprecated", "obsolete", "old", "migration", "oneoff"),
        content_signals=("deprecated", "one-off", "temporary script", "remove after migration", "obsolete"),
    ),
    CleanupRule(
        category="stale_doc",
        kinds=("doc",),
        path_signals=("legacy", "deprecated", "obsolete", "old", "migration"),
        content_signals=("deprecated", "old flow", "legacy", "obsolete", "remove after migration"),
    ),
    CleanupRule(
        category="stale_config",
        kinds=("config",),
        path_signals=("legacy", "deprecated", "obsolete", "old", "migration"),
        content_signals=("deprecated", "legacy", "obsolete", "temporary override", "remove after migration"),
    ),
    CleanupRule(
        category="stale_prompt",
        kinds=("prompt",),
        path_signals=("legacy", "deprecated", "obsolete", "old", "migration"),
        content_signals=("deprecated", "legacy prompt", "obsolete", "remove after migration"),
    ),
)


def _safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:_TEXT_SIGNAL_LIMIT]
    except Exception:
        return ""


def _path_tokens(path: str) -> set[str]:
    lowered = normalize_relpath(path).lower().replace(".", "/")
    return {token for token in _PATH_TOKEN_SPLIT_RE.split(lowered) if token}


def _matched_path_signals(path: str, signals: tuple[str, ...]) -> list[str]:
    tokens = _path_tokens(path)
    return [signal for signal in signals if signal in tokens]


def _matched_content_signals(text: str, signals: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [signal for signal in signals if signal in lowered]


def _replacement_hint(root: Path, path: str) -> str:
    normalized = normalize_relpath(path)
    candidates: list[str] = []
    if "/legacy/" in normalized:
        candidates.append(normalized.replace("/legacy/", "/", 1))
    if "/deprecated/" in normalized:
        candidates.append(normalized.replace("/deprecated/", "/", 1))
    name = Path(normalized).name
    parent = Path(normalized).parent
    stem = Path(name).stem
    suffix = Path(name).suffix
    for prefix in ("legacy_", "deprecated_", "old_", "compat_"):
        if stem.startswith(prefix):
            candidates.append(normalize_relpath(parent / f"{stem[len(prefix):]}{suffix}"))
    for suffix_token in ("_legacy", "_deprecated", "_compat", "_old"):
        if stem.endswith(suffix_token):
            candidates.append(normalize_relpath(parent / f"{stem[: -len(suffix_token)]}{suffix}"))
    for candidate in candidates:
        if candidate and (root / candidate).exists():
            return candidate
    return ""


def _candidate_from_rule(
    *,
    root: Path,
    path: str,
    kind: str,
    text: str,
    rule: CleanupRule,
) -> dict[str, Any] | None:
    if kind not in rule.kinds:
        return None
    path_matches = _matched_path_signals(path, rule.path_signals)
    content_matches = _matched_content_signals(text, rule.content_signals)
    if not path_matches and not content_matches:
        return None
    confidence = 0.55 + (0.12 * len(path_matches)) + (0.18 * len(content_matches))
    evidence = [f"path:{signal}" for signal in path_matches]
    evidence.extend(f"content:{signal}" for signal in content_matches)
    return {
        "path": path,
        "kind": kind,
        "category": rule.category,
        "confidence": round(clamp(confidence, 0.55, 0.95), 2),
        "evidence": evidence,
        "replacement": _replacement_hint(root, path),
        "review_required": True,
    }


def build_cleanup_inventory(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    rules = load_archi_rules(root)
    candidates: list[dict[str, Any]] = []
    for entry in iter_cleanup_scope(root, rules=rules):
        text = _safe_text(root / entry.path)
        matched = [
            candidate
            for rule in _CLEANUP_RULES
            if (candidate := _candidate_from_rule(root=root, path=entry.path, kind=entry.kind, text=text, rule=rule))
        ]
        if not matched:
            continue
        matched.sort(
            key=lambda item: (
                -float(item.get("confidence", 0.0) or 0.0),
                len(item.get("replacement", "") or ""),
                str(item.get("category", "") or ""),
            )
        )
        candidate = dict(matched[0])
        candidate.update(
            cleanup_metadata_for_candidate(
                candidate.get("path", ""),
                rules=rules,
                kind=str(candidate.get("kind", "") or ""),
                category=str(candidate.get("category", "") or ""),
            )
        )
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("path", "") or ""),
        )
    )
    return {
        "generated_at": utc_now_iso(),
        "candidate_total": len(candidates),
        "candidates": candidates,
    }


def build_cleanup_ledger(inventory: dict[str, Any]) -> dict[str, Any]:
    candidates = inventory.get("candidates", [])
    items = [item for item in candidates if isinstance(item, dict)]
    by_kind = Counter(str(item.get("kind", "") or "") for item in items)
    by_category = Counter(str(item.get("category", "") or "") for item in items)
    by_owner = Counter(str(item.get("owner", "") or "") for item in items if str(item.get("owner", "") or ""))
    review_required_total = sum(1 for item in items if bool(item.get("review_required", False)))
    owner_total = sum(1 for item in items if str(item.get("owner", "") or "").strip())
    ttl_total = sum(1 for item in items if safe_int(item.get("ttl_days", 0) or 0) > 0)
    expires_total = sum(1 for item in items if str(item.get("expires_at", "") or "").strip())
    expired_total = sum(1 for item in items if bool(item.get("expired", False)))
    return {
        "generated_at": utc_now_iso(),
        "counts": {
            "candidate_total": len(items),
            "review_required_total": review_required_total,
            "owner_total": owner_total,
            "ttl_total": ttl_total,
            "expires_total": expires_total,
            "expired_total": expired_total,
            "by_kind": dict(sorted(by_kind.items())),
            "by_category": dict(sorted(by_category.items())),
            "by_owner": dict(sorted(by_owner.items())),
        },
        "items_by_path": {
            str(item.get("path", "") or ""): {
                "kind": str(item.get("kind", "") or ""),
                "category": str(item.get("category", "") or ""),
                "confidence": float(item.get("confidence", 0.0) or 0.0),
                **cleanup_metadata_fields(item),
            }
            for item in items
            if str(item.get("path", "") or "")
        },
    }


__all__ = [
    "build_cleanup_inventory",
    "build_cleanup_ledger",
]
