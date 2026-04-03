from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.cleanup.inventory import build_cleanup_inventory, build_cleanup_ledger
from architec.cleanup.metadata import cleanup_metadata_text
from architec.integration.paths import (
    CLEANUP_INVENTORY_PATH,
    CLEANUP_LEDGER_PATH,
    CLEANUP_SUMMARY_MD_PATH,
)
from architec.support.io_utils import write_json


def cleanup_report_view(
    inventory: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    counts = ledger.get("counts", {}) if isinstance(ledger.get("counts"), dict) else {}
    return {
        "candidate_total": int(counts.get("candidate_total", 0) or 0),
        "review_required_total": int(counts.get("review_required_total", 0) or 0),
        "owner_total": int(counts.get("owner_total", 0) or 0),
        "ttl_total": int(counts.get("ttl_total", 0) or 0),
        "expires_total": int(counts.get("expires_total", 0) or 0),
        "expired_total": int(counts.get("expired_total", 0) or 0),
        "by_kind": counts.get("by_kind", {}) if isinstance(counts.get("by_kind"), dict) else {},
        "by_category": counts.get("by_category", {}) if isinstance(counts.get("by_category"), dict) else {},
        "by_owner": counts.get("by_owner", {}) if isinstance(counts.get("by_owner"), dict) else {},
        "top_candidates": [
            item
            for item in (inventory.get("candidates", []) if isinstance(inventory.get("candidates"), list) else [])[:8]
            if isinstance(item, dict)
        ],
    }


def render_cleanup_summary(
    inventory: dict[str, Any],
    ledger: dict[str, Any],
) -> str:
    counts = ledger.get("counts", {}) if isinstance(ledger.get("counts"), dict) else {}
    by_category = counts.get("by_category", {}) if isinstance(counts.get("by_category"), dict) else {}
    lines = [
        "# Cleanup Summary",
        "",
        f"Candidates: {int(counts.get('candidate_total', 0) or 0)}",
        f"Review required: {int(counts.get('review_required_total', 0) or 0)}",
    ]
    owner_total = int(counts.get("owner_total", 0) or 0)
    ttl_total = int(counts.get("ttl_total", 0) or 0)
    expires_total = int(counts.get("expires_total", 0) or 0)
    expired_total = int(counts.get("expired_total", 0) or 0)
    if owner_total or ttl_total or expires_total or expired_total:
        lines.append(
            "Metadata: "
            f"owner={owner_total}, ttl={ttl_total}, expires_at={expires_total}, expired={expired_total}"
        )
    if by_category:
        rendered = ", ".join(f"{name}={value}" for name, value in by_category.items())
        lines.append(f"Categories: {rendered}")
    top_items = inventory.get("candidates", []) if isinstance(inventory.get("candidates"), list) else []
    lines.append("")
    lines.append("## Top Candidates")
    if not top_items:
        lines.append("")
        lines.append("- No cleanup candidates detected by the current heuristic pass.")
        return "\n".join(lines) + "\n"
    lines.append("")
    for item in top_items[:12]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "").strip()
        kind = str(item.get("kind", "") or "").strip()
        category = str(item.get("category", "") or "").strip()
        confidence = float(item.get("confidence", 0.0) or 0.0)
        evidence = item.get("evidence", [])
        evidence_text = ", ".join(str(part) for part in evidence[:3]) if isinstance(evidence, list) else ""
        line = f"- `{path}` [{kind}] -> {category} ({confidence:.2f})"
        if evidence_text:
            line += f" | {evidence_text}"
        metadata_text = cleanup_metadata_text(item)
        if metadata_text:
            line += f" | {metadata_text}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def write_cleanup_artifacts(
    project_root: str | Path,
    *,
    inventory: dict[str, Any] | None = None,
    ledger: dict[str, Any] | None = None,
) -> dict[str, str]:
    root = Path(project_root).resolve()
    if inventory is None:
        inventory = build_cleanup_inventory(root)
    if ledger is None:
        ledger = build_cleanup_ledger(inventory)
    inventory_path = root / CLEANUP_INVENTORY_PATH
    ledger_path = root / CLEANUP_LEDGER_PATH
    summary_path = root / CLEANUP_SUMMARY_MD_PATH
    write_json(inventory_path, inventory)
    write_json(ledger_path, ledger)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_cleanup_summary(inventory, ledger), encoding="utf-8")
    return {
        "cleanup_inventory_json": str(inventory_path),
        "cleanup_ledger_json": str(ledger_path),
        "cleanup_summary_md": str(summary_path),
    }


__all__ = [
    "cleanup_report_view",
    "render_cleanup_summary",
    "write_cleanup_artifacts",
]
