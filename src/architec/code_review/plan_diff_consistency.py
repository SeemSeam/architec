from __future__ import annotations

import hashlib
import json
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any

from architec.support.io_utils import normalize_relpath


def _normal_path(path: object) -> str:
    text = normalize_relpath(str(path or ""))
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _planned_paths(plan_review: dict[str, Any]) -> list[str]:
    understood = plan_review.get("understood_plan")
    if not isinstance(understood, dict):
        return []
    raw_changes = understood.get("changes")
    if not isinstance(raw_changes, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_changes:
        path = ""
        if isinstance(item, dict):
            path = _normal_path(item.get("path", ""))
        else:
            path = _normal_path(item)
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _path_matches(path: str, pattern: str) -> bool:
    normalized = _normal_path(path)
    planned = _normal_path(pattern)
    if not normalized or not planned:
        return False
    if "*" in planned or "?" in planned or "[" in planned:
        return fnmatchcase(normalized, planned) or PurePosixPath(normalized).match(planned)
    return normalized == planned or normalized.startswith(f"{planned.rstrip('/')}/")


def _stable_concern_id(kind: str, *, path: str, plan_path: str, plan_fingerprint: str) -> str:
    payload = {
        "kind": kind,
        "path": path,
        "plan_path": plan_path,
        "plan_fingerprint": plan_fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:{kind}:{digest}"


def _unexpected_change_concern(
    *,
    path: str,
    planned_paths: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    evidence = [
        "plan_diff_consistency.observation=unexpected_changed_file",
        f"plan_diff_consistency.changed_file={path}",
        f"plan_diff_consistency.planned_path_total={len(planned_paths)}",
    ]
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    return {
        "concern_id": _stable_concern_id(
            "plan-diff-consistency",
            path=path,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "caution",
        "confidence": 0.8,
        "location": {
            "path": path,
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "Changed file is outside the saved plan-review touchpoints.",
        "evidence": evidence,
        "blast_radius": [path],
        "next_steps_hint": "Review whether the plan artifact should include this touchpoint or whether the change should be narrowed.",
    }


def _missing_planned_path_concern(
    *,
    path: str,
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    evidence = [
        "plan_diff_consistency.observation=planned_path_not_changed",
        f"plan_diff_consistency.planned_path={path}",
        f"plan_diff_consistency.changed_file_total={len(changed_files)}",
    ]
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    return {
        "concern_id": _stable_concern_id(
            "plan-diff-consistency",
            path=path,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "info",
        "confidence": 0.75,
        "location": {
            "path": path,
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "Saved plan-review touchpoint is not present in the selected diff.",
        "evidence": evidence,
        "blast_radius": [path],
        "next_steps_hint": "Review whether the plan is partially implemented or whether this touchpoint is no longer needed.",
    }


def load_plan_review(path: str | Path) -> dict[str, Any]:
    review_path = Path(path)
    try:
        loaded = json.loads(review_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Plan-review JSON not found: {review_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid plan-review JSON: {review_path}: {exc.msg}") from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to read plan-review JSON: {review_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Plan-review JSON must be an object: {review_path}")
    return loaded


def plan_diff_consistency_scan(
    plan_review: dict[str, Any],
    *,
    changed_files: list[str],
    limit: int = 20,
) -> dict[str, Any]:
    changed = [_normal_path(path) for path in changed_files]
    changed = [path for path in changed if path]
    planned = _planned_paths(plan_review)
    plan_fingerprint = str(plan_review.get("plan_fingerprint", "") or "")
    artifacts = plan_review.get("artifacts")
    plan_path = ""
    if isinstance(artifacts, dict):
        plan_path = _normal_path(artifacts.get("plan_path", ""))
    if not planned:
        return {
            "concerns": [],
            "changed_file_total": len(changed),
            "planned_path_total": len(planned),
            "scoped_to_changed_files": True,
        }

    concerns: list[dict[str, Any]] = []
    for path in changed:
        if not any(_path_matches(path, planned_path) for planned_path in planned):
            concerns.append(
                _unexpected_change_concern(
                    path=path,
                    planned_paths=planned,
                    plan_fingerprint=plan_fingerprint,
                    plan_path=plan_path,
                )
            )
    for path in planned:
        if not any(_path_matches(changed_path, path) for changed_path in changed):
            concerns.append(
                _missing_planned_path_concern(
                    path=path,
                    changed_files=changed,
                    plan_fingerprint=plan_fingerprint,
                    plan_path=plan_path,
                )
            )
    concerns.sort(
        key=lambda item: (
            str(item.get("level", "") or ""),
            str(item.get("location", {}).get("path", "") if isinstance(item.get("location"), dict) else ""),
            str(item.get("concern_id", "") or ""),
        )
    )
    return {
        "concerns": concerns[:limit],
        "changed_file_total": len(changed),
        "planned_path_total": len(planned),
        "concern_total_before_limit": len(concerns),
        "scoped_to_changed_files": True,
    }


__all__ = [
    "load_plan_review",
    "plan_diff_consistency_scan",
]
