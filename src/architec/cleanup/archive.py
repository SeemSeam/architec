from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from architec.integration.paths import (
    ARCHIVE_CANDIDATES_PATH,
    ARCHIVE_SUMMARY_MD_PATH,
)
from architec.cleanup.metadata import cleanup_metadata_fields, cleanup_metadata_text
from architec.support.io_utils import normalize_relpath, utc_now_iso, write_json

_ARCHIVE_CATEGORY_RULES = {
    "obsolete_script": {
        "tier": "review",
        "reason": "legacy or one-off script can be archived after verifying no operational hooks remain.",
    },
    "stale_doc": {
        "tier": "ready",
        "reason": "stale documentation is low-risk to archive outside the active project surface.",
    },
    "stale_config": {
        "tier": "review",
        "reason": "stale configuration should be archived only after confirming no live runtime or case references remain.",
    },
    "stale_prompt": {
        "tier": "ready",
        "reason": "stale prompt assets are typically safe to archive once superseded.",
    },
}
_ARCHIVE_ALLOWED_KINDS = frozenset({"doc", "config", "prompt", "script"})


def _archive_path_hint(path: str) -> str:
    return normalize_relpath(Path("archive") / Path(normalize_relpath(path)))


def _archive_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    kind = str(item.get("kind", "") or "").strip()
    category = str(item.get("category", "") or "").strip()
    if kind not in _ARCHIVE_ALLOWED_KINDS:
        return None
    rule = _ARCHIVE_CATEGORY_RULES.get(category)
    if rule is None:
        return None
    path = normalize_relpath(str(item.get("path", "") or ""))
    if not path:
        return None
    return {
        "path": path,
        "kind": kind,
        "category": category,
        "confidence": float(item.get("confidence", 0.0) or 0.0),
        "evidence": list(item.get("evidence", [])) if isinstance(item.get("evidence"), list) else [],
        "replacement": str(item.get("replacement", "") or "").strip(),
        "review_required": bool(item.get("review_required", False)),
        "archive_tier": str(rule["tier"]),
        "archive_reason": str(rule["reason"]),
        "archive_path_hint": _archive_path_hint(path),
        **cleanup_metadata_fields(item),
    }


def build_archive_candidates(cleanup_inventory: dict[str, Any]) -> dict[str, Any]:
    raw_items = (
        cleanup_inventory.get("candidates", [])
        if isinstance(cleanup_inventory.get("candidates"), list)
        else []
    )
    items = [
        candidate
        for item in raw_items
        if isinstance(item, dict)
        if (candidate := _archive_candidate(item)) is not None
    ]
    items.sort(
        key=lambda item: (
            str(item.get("archive_tier", "") or "") != "ready",
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("path", "") or ""),
        )
    )
    by_kind = Counter(str(item.get("kind", "") or "") for item in items)
    by_category = Counter(str(item.get("category", "") or "") for item in items)
    by_tier = Counter(str(item.get("archive_tier", "") or "") for item in items)
    return {
        "generated_at": utc_now_iso(),
        "candidate_total": len(items),
        "ready_total": int(by_tier.get("ready", 0)),
        "review_total": int(by_tier.get("review", 0)),
        "by_kind": dict(sorted(by_kind.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_tier": dict(sorted(by_tier.items())),
        "candidates": items,
    }


def archive_report_view(archive_candidates: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_total": int(archive_candidates.get("candidate_total", 0) or 0),
        "ready_total": int(archive_candidates.get("ready_total", 0) or 0),
        "review_total": int(archive_candidates.get("review_total", 0) or 0),
        "by_kind": (
            archive_candidates.get("by_kind", {})
            if isinstance(archive_candidates.get("by_kind"), dict)
            else {}
        ),
        "by_category": (
            archive_candidates.get("by_category", {})
            if isinstance(archive_candidates.get("by_category"), dict)
            else {}
        ),
        "by_tier": (
            archive_candidates.get("by_tier", {})
            if isinstance(archive_candidates.get("by_tier"), dict)
            else {}
        ),
        "top_candidates": [
            item
            for item in (
                archive_candidates.get("candidates", [])
                if isinstance(archive_candidates.get("candidates"), list)
                else []
            )[:8]
            if isinstance(item, dict)
        ],
    }


def render_archive_summary(archive_candidates: dict[str, Any]) -> str:
    by_category = (
        archive_candidates.get("by_category", {})
        if isinstance(archive_candidates.get("by_category"), dict)
        else {}
    )
    by_tier = (
        archive_candidates.get("by_tier", {})
        if isinstance(archive_candidates.get("by_tier"), dict)
        else {}
    )
    lines = [
        "# Archive Candidate Summary",
        "",
        f"Candidates: {int(archive_candidates.get('candidate_total', 0) or 0)}",
        f"Ready: {int(archive_candidates.get('ready_total', 0) or 0)}",
        f"Review: {int(archive_candidates.get('review_total', 0) or 0)}",
    ]
    if by_tier:
        lines.append(
            "Tiers: " + ", ".join(f"{name}={value}" for name, value in by_tier.items())
        )
    if by_category:
        lines.append(
            "Categories: " + ", ".join(f"{name}={value}" for name, value in by_category.items())
        )
    items = (
        archive_candidates.get("candidates", [])
        if isinstance(archive_candidates.get("candidates"), list)
        else []
    )
    lines.extend(["", "## Top Archive Candidates", ""])
    if not items:
        lines.append("- No archive candidates detected from the current cleanup inventory.")
        return "\n".join(lines) + "\n"
    for item in items[:12]:
        if not isinstance(item, dict):
            continue
        line = (
            f"- `{item.get('path', '')}` [{item.get('kind', '')}] -> "
            f"{item.get('category', '')} | tier={item.get('archive_tier', '')}"
        )
        archive_path_hint = str(item.get("archive_path_hint", "") or "").strip()
        if archive_path_hint:
            line += f" | archive as `{archive_path_hint}`"
        metadata_text = cleanup_metadata_text(item)
        if metadata_text:
            line += f" | {metadata_text}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def write_archive_artifacts(
    project_root: str | Path,
    *,
    archive_candidates: dict[str, Any],
) -> dict[str, str]:
    root = Path(project_root).resolve()
    candidates_path = root / ARCHIVE_CANDIDATES_PATH
    summary_path = root / ARCHIVE_SUMMARY_MD_PATH
    write_json(candidates_path, archive_candidates)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_archive_summary(archive_candidates), encoding="utf-8")
    return {
        "archive_candidates_json": str(candidates_path),
        "archive_summary_md": str(summary_path),
    }


__all__ = [
    "archive_report_view",
    "build_archive_candidates",
    "render_archive_summary",
    "write_archive_artifacts",
]
