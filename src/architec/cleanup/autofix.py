from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from architec.cleanup.metadata import cleanup_metadata_fields, cleanup_metadata_text
from architec.integration.paths import (
    AUTOFIX_PLAN_JSON_PATH,
    AUTOFIX_SUMMARY_MD_PATH,
)
from architec.support.io_utils import normalize_relpath, utc_now_iso, write_json


def _safe_project_relpath(path: object) -> str:
    text = normalize_relpath(str(path or ""))
    if not text:
        return ""
    parts = Path(text).parts
    if not parts:
        return ""
    if text.startswith("/"):
        return ""
    if any(part == ".." for part in parts):
        return ""
    return text


def _planned_archive_actions(semantic_judge: dict[str, Any]) -> list[dict[str, Any]]:
    judgments = (
        semantic_judge.get("judgments", [])
        if isinstance(semantic_judge.get("judgments"), list)
        else []
    )
    actions: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in judgments:
        if not isinstance(item, dict):
            continue
        decision = str(item.get("decision", "") or "").strip()
        if decision != "archive_first":
            continue
        kind = str(item.get("kind", "") or "").strip()
        if kind == "source":
            continue
        from_path = _safe_project_relpath(item.get("path"))
        to_path = _safe_project_relpath(item.get("archive_path_hint"))
        if not from_path or not to_path or not to_path.startswith("archive/"):
            continue
        key = (from_path, to_path)
        if key in seen:
            continue
        seen.add(key)
        actions.append(
            {
                "action": "archive_move",
                "decision_source": "semantic_judge",
                "decision": decision,
                "from_path": from_path,
                "to_path": to_path,
                "kind": kind,
                "category": str(item.get("category", "") or "").strip(),
                "confidence": round(float(item.get("confidence", 0.0) or 0.0), 2),
                "reason": str(item.get("reason", "") or "").strip(),
                "status": "planned",
                "note": "",
                **cleanup_metadata_fields(item),
            }
        )
    actions.sort(key=lambda item: (str(item.get("from_path", "") or ""), str(item.get("to_path", "") or "")))
    return actions


def build_autofix_plan(
    *,
    cleanup: dict[str, Any],
    archive_candidates: dict[str, Any],
    semantic_judge: dict[str, Any],
    apply: bool,
) -> dict[str, Any]:
    actions = _planned_archive_actions(semantic_judge)
    mode = "apply" if apply else "dry_run"
    status = "planned" if actions else "noop"
    return {
        "generated_at": utc_now_iso(),
        "mode": mode,
        "status": status,
        "cleanup_candidate_total": int(cleanup.get("candidate_total", 0) or 0),
        "archive_candidate_total": int(archive_candidates.get("candidate_total", 0) or 0),
        "semantic_judge_status": str(semantic_judge.get("status", "") or "skipped"),
        "action_total": len(actions),
        "applied_total": 0,
        "blocked_total": 0,
        "skipped_total": 0,
        "by_status": {"planned": len(actions)} if actions else {},
        "by_action": {"archive_move": len(actions)} if actions else {},
        "top_actions": actions[:8],
        "actions": actions,
    }


def _updated_counts(actions: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    by_status = Counter(str(item.get("status", "") or "") for item in actions if str(item.get("status", "") or ""))
    by_action = Counter(str(item.get("action", "") or "") for item in actions if str(item.get("action", "") or ""))
    return dict(sorted(by_status.items())), dict(sorted(by_action.items()))


def _apply_archive_move(root: Path, action: dict[str, Any]) -> dict[str, Any]:
    updated = dict(action)
    from_path = _safe_project_relpath(action.get("from_path"))
    to_path = _safe_project_relpath(action.get("to_path"))
    if not from_path or not to_path or not to_path.startswith("archive/"):
        updated["status"] = "blocked"
        updated["note"] = "unsafe archive target"
        return updated
    src = root / from_path
    dst = root / to_path
    if not src.exists() or not src.is_file():
        updated["status"] = "skipped"
        updated["note"] = "source file missing"
        return updated
    if dst.exists():
        updated["status"] = "blocked"
        updated["note"] = "archive target already exists"
        return updated
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    updated["status"] = "applied"
    updated["note"] = "moved to archive"
    return updated


def apply_autofix_plan(
    project_root: str | Path,
    *,
    plan: dict[str, Any],
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    actions = (
        plan.get("actions", [])
        if isinstance(plan.get("actions"), list)
        else []
    )
    updated_actions = [
        _apply_archive_move(root, action) if isinstance(action, dict) else action
        for action in actions
    ]
    applied_total = sum(1 for item in updated_actions if isinstance(item, dict) and str(item.get("status", "") or "") == "applied")
    blocked_total = sum(1 for item in updated_actions if isinstance(item, dict) and str(item.get("status", "") or "") == "blocked")
    skipped_total = sum(1 for item in updated_actions if isinstance(item, dict) and str(item.get("status", "") or "") == "skipped")
    by_status, by_action = _updated_counts([item for item in updated_actions if isinstance(item, dict)])
    status = "applied"
    if blocked_total > 0 and applied_total <= 0:
        status = "blocked"
    elif blocked_total > 0 or skipped_total > 0:
        status = "partial"
    elif applied_total <= 0:
        status = "noop"
    return {
        **plan,
        "generated_at": utc_now_iso(),
        "status": status,
        "action_total": len(updated_actions),
        "applied_total": applied_total,
        "blocked_total": blocked_total,
        "skipped_total": skipped_total,
        "by_status": by_status,
        "by_action": by_action,
        "top_actions": updated_actions[:8],
        "actions": updated_actions,
    }


def autofix_report_view(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": str(plan.get("mode", "") or "dry_run"),
        "status": str(plan.get("status", "") or "noop"),
        "action_total": int(plan.get("action_total", 0) or 0),
        "applied_total": int(plan.get("applied_total", 0) or 0),
        "blocked_total": int(plan.get("blocked_total", 0) or 0),
        "skipped_total": int(plan.get("skipped_total", 0) or 0),
        "by_status": plan.get("by_status", {}) if isinstance(plan.get("by_status"), dict) else {},
        "by_action": plan.get("by_action", {}) if isinstance(plan.get("by_action"), dict) else {},
        "top_actions": [
            item
            for item in (
                plan.get("top_actions", [])
                if isinstance(plan.get("top_actions"), list)
                else []
            )[:8]
            if isinstance(item, dict)
        ],
    }


def render_autofix_summary(plan: dict[str, Any]) -> str:
    lines = [
        "# Autofix Summary",
        "",
        f"Mode: {str(plan.get('mode', '') or 'dry_run')}",
        f"Status: {str(plan.get('status', '') or 'noop')}",
        f"Actions: {int(plan.get('action_total', 0) or 0)}",
        f"Applied: {int(plan.get('applied_total', 0) or 0)}",
        f"Blocked: {int(plan.get('blocked_total', 0) or 0)}",
        f"Skipped: {int(plan.get('skipped_total', 0) or 0)}",
    ]
    by_status = plan.get("by_status", {}) if isinstance(plan.get("by_status"), dict) else {}
    if by_status:
        lines.append("Statuses: " + ", ".join(f"{name}={value}" for name, value in by_status.items()))
    actions = plan.get("actions", []) if isinstance(plan.get("actions"), list) else []
    lines.extend(["", "## Planned Actions", ""])
    if not actions:
        lines.append("- No safe autofix actions were derived from the current semantic judge result.")
        return "\n".join(lines) + "\n"
    for item in actions[:12]:
        if not isinstance(item, dict):
            continue
        line = (
            f"- `{item.get('from_path', '')}` -> `{item.get('to_path', '')}` "
            f"[{item.get('status', '')}]"
        )
        reason = str(item.get("reason", "") or "").strip()
        if reason:
            line += f" | {reason}"
        note = str(item.get("note", "") or "").strip()
        if note:
            line += f" | {note}"
        metadata_text = cleanup_metadata_text(item)
        if metadata_text:
            line += f" | {metadata_text}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def write_autofix_artifacts(
    project_root: str | Path,
    *,
    plan: dict[str, Any],
) -> dict[str, str]:
    root = Path(project_root).resolve()
    json_path = root / AUTOFIX_PLAN_JSON_PATH
    summary_path = root / AUTOFIX_SUMMARY_MD_PATH
    write_json(json_path, plan)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_autofix_summary(plan), encoding="utf-8")
    return {
        "autofix_plan_json": str(json_path),
        "autofix_summary_md": str(summary_path),
    }


__all__ = [
    "apply_autofix_plan",
    "autofix_report_view",
    "build_autofix_plan",
    "render_autofix_summary",
    "write_autofix_artifacts",
]
