from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEMOTE_STATUSES = {"rejected", "not_applicable", "superseded"}
KNOWN_STATUSES = DEMOTE_STATUSES | {"accepted", "deferred"}
KNOWN_SCOPES = {"exact_advice", "same_path_kind", "pattern"}


class AdviceFeedbackInputError(RuntimeError):
    """Raised when advice feedback JSON cannot be read or used."""


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean(value: object) -> str:
    return str(value or "").strip()


def _norm_token(value: object) -> str:
    return _clean(value).lower().replace("-", "_").replace(" ", "_")


def _norm_path(value: object) -> str:
    return _clean(value).replace("\\", "/").lstrip("./")


def _stable_advice_id(prefix: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:12]}"


def _feedback_items(feedback: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(feedback, dict):
        return []
    out: list[dict[str, Any]] = []
    for item in _list(feedback.get("items")):
        if not isinstance(item, dict):
            continue
        status = _norm_token(item.get("status"))
        if status not in KNOWN_STATUSES:
            continue
        scope = _norm_token(item.get("scope"))
        if scope not in KNOWN_SCOPES:
            if _clean(item.get("advice_id")) or _clean(item.get("concern_id")):
                scope = "exact_advice"
            elif _clean(item.get("path")):
                scope = "same_path_kind"
            elif _clean(item.get("pattern")):
                scope = "pattern"
            else:
                continue
        out.append(
            {
                "advice_id": _clean(item.get("advice_id")),
                "concern_id": _clean(item.get("concern_id")),
                "kind": _norm_token(item.get("kind")),
                "path": _norm_path(item.get("path")),
                "symbol": _clean(item.get("symbol")),
                "status": status,
                "scope": scope,
                "pattern": _clean(item.get("pattern")).lower(),
                "reason": _clean(item.get("reason")),
            }
        )
    return out


def load_advice_feedback(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise AdviceFeedbackInputError(f"Advice feedback JSON not found: {source}") from exc
    except OSError as exc:
        raise AdviceFeedbackInputError(f"Unable to read advice feedback JSON: {source}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdviceFeedbackInputError(f"Invalid advice feedback JSON: {source}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise AdviceFeedbackInputError(f"Advice feedback JSON must be an object: {source}")
    items = data.get("items")
    if items is not None and not isinstance(items, list):
        raise AdviceFeedbackInputError(f"Advice feedback items must be a list: {source}")
    data = dict(data)
    data["_source_path"] = str(source)
    return data


def recommendation_target(item: dict[str, Any]) -> dict[str, Any]:
    title = _clean(item.get("title"))
    scope = _clean(item.get("scope"))
    why = _clean(item.get("why"))
    priority = _clean(item.get("priority"))
    kind = _norm_token(item.get("kind")) or "recommendation"
    advice_id = _clean(item.get("advice_id")) or _stable_advice_id(
        "archi-advice:recommendation",
        {
            "kind": kind,
            "priority": priority,
            "title": title,
            "scope": scope,
            "why": why,
        },
    )
    return {
        "advice_id": advice_id,
        "kind": kind,
        "path": _norm_path(item.get("path")) or _norm_path(title) or _norm_path(scope),
        "title": title,
        "scope": scope,
        "why": why,
        "text": " ".join([advice_id, kind, title, scope, why]).lower(),
    }


def concern_target(concern: dict[str, Any]) -> dict[str, Any]:
    location = _dict(concern.get("location"))
    concern_id = _clean(concern.get("concern_id"))
    kind = _norm_token(concern.get("kind"))
    path = _norm_path(location.get("path"))
    symbol = _clean(location.get("symbol"))
    return {
        "advice_id": "",
        "concern_id": concern_id,
        "kind": kind,
        "path": path,
        "symbol": symbol,
        "title": "",
        "scope": path,
        "why": "",
        "text": " ".join([concern_id, kind, path, symbol]).lower(),
    }


def _path_matches(entry_path: str, target: dict[str, Any]) -> bool:
    if not entry_path:
        return False
    target_path = _norm_path(target.get("path"))
    if target_path == entry_path:
        return True
    haystack = " ".join(
        [
            _norm_path(target.get("path")),
            _clean(target.get("title")),
            _clean(target.get("scope")),
            _clean(target.get("text")),
        ]
    ).lower()
    return entry_path.lower() in haystack


def _kind_matches(entry_kind: str, target: dict[str, Any]) -> bool:
    if not entry_kind:
        return True
    target_kind = _norm_token(target.get("kind"))
    if target_kind == entry_kind:
        return True
    return entry_kind in _clean(target.get("text")).lower()


def demoting_feedback_for_target(
    target: dict[str, Any],
    feedback: dict[str, Any] | None,
) -> dict[str, Any]:
    target_advice_id = _clean(target.get("advice_id"))
    target_concern_id = _clean(target.get("concern_id"))
    target_text = _clean(target.get("text")).lower()
    for item in _feedback_items(feedback):
        if item["status"] not in DEMOTE_STATUSES:
            continue
        if item["scope"] == "exact_advice":
            if item["advice_id"] and item["advice_id"] == target_advice_id:
                return item
            if item["concern_id"] and item["concern_id"] == target_concern_id:
                return item
            continue
        if item["scope"] == "same_path_kind":
            if _path_matches(item["path"], target) and _kind_matches(item["kind"], target):
                return item
            continue
        if item["scope"] == "pattern":
            pattern = item["pattern"]
            if pattern and pattern in target_text and _kind_matches(item["kind"], target):
                return item
    return {}


def apply_feedback_to_recommendations(
    recommendations: list[dict[str, Any]],
    feedback: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items = _feedback_items(feedback)
    if not items:
        return recommendations, {}
    kept: list[dict[str, Any]] = []
    demoted: list[dict[str, Any]] = []
    for index, item in enumerate(recommendations):
        if not isinstance(item, dict):
            continue
        target = recommendation_target(item)
        enriched = dict(item)
        enriched.setdefault("advice_id", target["advice_id"])
        match = demoting_feedback_for_target(target, feedback)
        if match:
            demoted.append(
                {
                    "advice_id": target["advice_id"],
                    "kind": target["kind"],
                    "title": target["title"],
                    "scope": target["scope"],
                    "status": match["status"],
                    "feedback_scope": match["scope"],
                    "reason": match["reason"],
                    "position": index,
                }
            )
            continue
        kept.append(enriched)
    return kept, {
        "input_path": _clean(_dict(feedback).get("_source_path")),
        "item_total": len(items),
        "demoted_recommendation_total": len(demoted),
        "demoted_recommendations": demoted,
    }


def feedback_summary_for_concern(
    concern: dict[str, Any],
    feedback: dict[str, Any] | None,
) -> dict[str, Any]:
    target = concern_target(concern)
    match = demoting_feedback_for_target(target, feedback)
    if not match:
        return {}
    return {
        "concern_id": target["concern_id"],
        "kind": target["kind"],
        "path": target["path"],
        "symbol": target["symbol"],
        "status": match["status"],
        "feedback_scope": match["scope"],
        "reason": match["reason"],
    }


__all__ = [
    "AdviceFeedbackInputError",
    "apply_feedback_to_recommendations",
    "feedback_summary_for_concern",
    "load_advice_feedback",
]
