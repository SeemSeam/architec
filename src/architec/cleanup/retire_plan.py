from __future__ import annotations

import re
from typing import Any

from architec.support.io_utils import normalize_relpath

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_TRANSIENT_TOKENS = {
    "compat",
    "deprecated",
    "fallback",
    "legacy",
    "migration",
    "old",
    "shim",
    "temp",
    "temporary",
}
_TEMPORARY_CATEGORIES = {
    "compat_layer",
    "fallback_branch",
    "legacy_impl",
    "obsolete_script",
    "stale_config",
    "stale_doc",
    "stale_prompt",
}


def _tokens(value: object) -> set[str]:
    text = normalize_relpath(str(value or "")).lower().replace(":", "/")
    return {token for token in _TOKEN_SPLIT_RE.split(text) if token}


def _top_level(path: str) -> str:
    normalized = normalize_relpath(path)
    if not normalized:
        return ""
    return normalized.split("/", 1)[0]


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in paths:
        path = normalize_relpath(raw)
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _focus_files_for_component(
    component: str,
    *,
    target_item: dict[str, Any],
    candidate_files: list[dict[str, Any]],
) -> list[str]:
    evidence = [
        str(path)
        for path in target_item.get("evidence_paths", [])
        if isinstance(path, str)
    ]
    candidate_paths = [
        str(item.get("path", "") or "")
        for item in candidate_files
        if isinstance(item, dict) and str(item.get("component", "") or "") == component
    ]
    return _dedupe_paths([*evidence, *candidate_paths])[:6]


def _goal_add_items(feature: dict[str, Any]) -> list[dict[str, Any]]:
    target_components = (
        feature.get("target_components", [])
        if isinstance(feature.get("target_components"), list)
        else []
    )
    candidate_files = (
        feature.get("candidate_files", [])
        if isinstance(feature.get("candidate_files"), list)
        else []
    )
    items: list[dict[str, Any]] = []
    for target in target_components[:5]:
        if not isinstance(target, dict):
            continue
        component = str(target.get("component", "") or "").strip()
        if not component:
            continue
        focus_files = _focus_files_for_component(
            component,
            target_item=target,
            candidate_files=candidate_files,
        )
        items.append(
            {
                "component": component,
                "focus_files": focus_files,
                "why": "goal_target_component",
            }
        )
    if items:
        return items
    fallback: list[dict[str, Any]] = []
    for candidate in candidate_files[:3]:
        if not isinstance(candidate, dict):
            continue
        path = normalize_relpath(str(candidate.get("path", "") or ""))
        if not path:
            continue
        fallback.append(
            {
                "component": str(candidate.get("component", "") or ""),
                "focus_files": [path],
                "why": "goal_candidate_file",
            }
        )
    return fallback


def _diff_add_items(score: dict[str, Any]) -> list[dict[str, Any]]:
    components = score.get("components", []) if isinstance(score.get("components"), list) else []
    items: list[dict[str, Any]] = []
    for component_entry in components[:10]:
        if not isinstance(component_entry, dict):
            continue
        component = str(component_entry.get("component", "") or "").strip()
        changed_files = [
            normalize_relpath(str(path))
            for path in component_entry.get("changed_files", [])
            if isinstance(path, str)
        ]
        transient_files = [path for path in changed_files if _tokens(path) & _TRANSIENT_TOKENS]
        if not transient_files and not (_tokens(component) & _TRANSIENT_TOKENS):
            continue
        signal_tokens = sorted(
            {
                token
                for value in [component, *changed_files]
                for token in (_tokens(value) & _TRANSIENT_TOKENS)
            }
        )
        items.append(
            {
                "component": component,
                "focus_files": transient_files[:6] or changed_files[:3],
                "signals": signal_tokens[:5],
                "why": "changed_temporary_structure",
            }
        )
        if len(items) >= 5:
            break
    return items


def _candidate_component(snapshot: Any, path: str) -> str:
    resolver = getattr(snapshot, "component_for_path", None)
    if not callable(resolver):
        return ""
    try:
        return str(resolver(path) or "")
    except Exception:
        return ""


def _cleanup_relevance(
    item: dict[str, Any],
    *,
    snapshot: Any,
    focus_components: set[str],
    focus_paths: list[str],
    query_tokens: set[str],
) -> float:
    path = normalize_relpath(str(item.get("path", "") or ""))
    if not path:
        return 0.0
    score = 0.0
    category = str(item.get("category", "") or "")
    confidence = float(item.get("confidence", 0.0) or 0.0)
    if category in _TEMPORARY_CATEGORIES:
        score += 1.2
    if str(item.get("replacement", "") or "").strip():
        score += 0.4
    if confidence > 0.0:
        score += min(1.0, confidence)

    candidate_component = _candidate_component(snapshot, path)
    if candidate_component and candidate_component in focus_components:
        score += 3.0

    top_levels = {_top_level(current) for current in focus_paths if _top_level(current)}
    if _top_level(path) and _top_level(path) in top_levels:
        score += 1.5

    path_tokens = _tokens(path)
    overlap = path_tokens & query_tokens
    if overlap:
        score += min(2.0, 0.5 * len(overlap))
    return score


def _retire_items(
    *,
    cleanup_inventory: dict[str, Any],
    snapshot: Any,
    focus_components: set[str],
    focus_paths: list[str],
    query_tokens: set[str],
) -> list[dict[str, Any]]:
    candidates = (
        cleanup_inventory.get("candidates", [])
        if isinstance(cleanup_inventory.get("candidates"), list)
        else []
    )
    ranked: list[tuple[float, dict[str, Any]]] = []
    fallback: list[dict[str, Any]] = []
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        item = {
            "path": normalize_relpath(str(raw.get("path", "") or "")),
            "kind": str(raw.get("kind", "") or ""),
            "category": str(raw.get("category", "") or ""),
            "replacement": str(raw.get("replacement", "") or ""),
            "confidence": round(float(raw.get("confidence", 0.0) or 0.0), 2),
            "evidence": raw.get("evidence", [])[:4] if isinstance(raw.get("evidence"), list) else [],
        }
        if item["path"]:
            fallback.append(item)
        relevance = _cleanup_relevance(
            raw,
            snapshot=snapshot,
            focus_components=focus_components,
            focus_paths=focus_paths,
            query_tokens=query_tokens,
        )
        if relevance <= 0.0:
            continue
        ranked.append((relevance, item))

    if ranked:
        ranked.sort(
            key=lambda pair: (
                -pair[0],
                -float(pair[1].get("confidence", 0.0) or 0.0),
                str(pair[1].get("path", "") or ""),
            )
        )
        return [item for _, item in ranked[:5]]
    return fallback[:3]


def _goal_validation(goal: str, add_items: list[dict[str, Any]], retire_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    targeted = ", ".join(
        item.get("component", "")
        for item in add_items[:3]
        if isinstance(item, dict) and str(item.get("component", "") or "")
    )
    retire_paths = ", ".join(
        item.get("path", "")
        for item in retire_items[:2]
        if isinstance(item, dict) and str(item.get("path", "") or "")
    )
    return [
        {
            "check": "ownership",
            "detail": (
                f"Keep goal work for `{goal}` inside the planned target scope"
                + (f": {targeted}." if targeted else ".")
            ),
        },
        {
            "check": "retirement",
            "detail": (
                "Retire matched legacy, compat, or fallback structures in the same implementation slice"
                + (f": {retire_paths}." if retire_paths else ".")
            ),
        },
        {
            "check": "verification",
            "detail": "Run focused tests for touched files and confirm no new critical findings in the affected paths.",
        },
    ]


def _diff_validation(score: dict[str, Any], add_items: list[dict[str, Any]], retire_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    changed_total = int(score.get("changed_file_total", 0) or 0)
    transient_total = len(add_items)
    retire_total = len(retire_items)
    return [
        {
            "check": "temporary_scope",
            "detail": f"Every temporary structure in this diff should have an exit condition. Flagged temporary entries: {transient_total}.",
        },
        {
            "check": "paired_retirement",
            "detail": f"Retire old structures in the same change when possible. Matched retirement candidates: {retire_total}.",
        },
        {
            "check": "verification",
            "detail": f"Run tests covering the changed scope and confirm no new critical findings across {changed_total} changed files.",
        },
    ]


def build_goal_retire_plan(
    feature: dict[str, Any],
    *,
    goal: str,
    snapshot: Any,
    cleanup_inventory: dict[str, Any],
) -> dict[str, Any]:
    add_items = _goal_add_items(feature)
    focus_components = {
        str(item.get("component", "") or "")
        for item in add_items
        if isinstance(item, dict) and str(item.get("component", "") or "")
    }
    focus_paths = [
        path
        for item in add_items
        if isinstance(item, dict)
        for path in item.get("focus_files", [])
        if isinstance(path, str)
    ]
    retire_items = _retire_items(
        cleanup_inventory=cleanup_inventory,
        snapshot=snapshot,
        focus_components=focus_components,
        focus_paths=focus_paths,
        query_tokens=_tokens(goal) | {token for component in focus_components for token in _tokens(component)},
    )
    return {
        "add": add_items,
        "retire": retire_items,
        "validation": _goal_validation(goal, add_items, retire_items),
    }


def build_diff_retire_plan(
    score: dict[str, Any],
    *,
    snapshot: Any,
    cleanup_inventory: dict[str, Any],
) -> dict[str, Any]:
    add_items = _diff_add_items(score)
    components = score.get("components", []) if isinstance(score.get("components"), list) else []
    focus_components = {
        str(item.get("component", "") or "")
        for item in components
        if isinstance(item, dict) and str(item.get("component", "") or "")
    }
    focus_paths = [
        normalize_relpath(str(path))
        for item in components
        if isinstance(item, dict)
        for path in item.get("changed_files", [])
        if isinstance(path, str)
    ]
    retire_items = _retire_items(
        cleanup_inventory=cleanup_inventory,
        snapshot=snapshot,
        focus_components=focus_components,
        focus_paths=focus_paths,
        query_tokens={token for component in focus_components for token in _tokens(component)}
        | {token for path in focus_paths for token in _tokens(path)},
    )
    return {
        "add": add_items,
        "retire": retire_items,
        "validation": _diff_validation(score, add_items, retire_items),
    }


__all__ = [
    "build_diff_retire_plan",
    "build_goal_retire_plan",
]
