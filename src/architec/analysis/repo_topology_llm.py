from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _group_payload_items(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in groups[:10]:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "group_id": item.get("group_id", ""),
                "candidate_files": item.get("candidate_files", []),
                "evidence_terms": item.get("evidence_terms", []),
                "responsibility_summary": item.get("responsibility_summary", ""),
                "primary_symbols": item.get("primary_symbols", []),
                "current_candidate": item.get("programmatic_name", ""),
                "alternative_names": item.get("alternative_names", []),
                "folder_votes": item.get("folder_votes", {}),
                "status": item.get("status", ""),
                "cohesion": item.get("cohesion", 0.0),
                "folder_share": item.get("folder_share", 0.0),
            }
        )
    return items


def _root_file_payload_items(placement_review: dict[str, Any]) -> list[dict[str, Any]]:
    rows = placement_review.get("misplaced_root_files", []) + placement_review.get("review_root_files", [])
    items: list[dict[str, Any]] = []
    for item in rows[:16]:
        if not isinstance(item, dict):
            continue
        import_signals = item.get("import_signals", {}) if isinstance(item.get("import_signals"), dict) else {}
        items.append(
            {
                "path": item.get("path", ""),
                "root_role": item.get("root_role", ""),
                "programmatic_folder": item.get("programmatic_folder", ""),
                "alternative_folders": item.get("alternative_folders", []),
                "decision": item.get("decision", ""),
                "reason": item.get("reason", ""),
                "internal_import_total": import_signals.get("internal_import_total", 0),
                "internal_targets": import_signals.get("internal_targets", []),
            }
        )
    return items


def _folder_membership_payload_items(review: dict[str, Any]) -> list[dict[str, Any]]:
    folder_review = review.get("folder_membership_review", {})
    if not isinstance(folder_review, dict):
        return []
    items: list[dict[str, Any]] = []
    for item in folder_review.get("issues", [])[:6]:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "group_id": item.get("group_id", ""),
                "folder_votes": item.get("folder_votes", {}),
                "detail": item.get("detail", ""),
            }
        )
    return items


def topology_payload(review: dict[str, Any]) -> dict[str, Any]:
    groups = review.get("groups", []) if isinstance(review.get("groups"), list) else []
    placement_review = (
        review.get("root_placement_review", {})
        if isinstance(review.get("root_placement_review", {}), dict)
        else {}
    )
    return {
        "source_root": review.get("source_root", ""),
        "flat_file_total": review.get("flat_file_total", 0),
        "subpackage_total": review.get("subpackage_total", 0),
        "peer_directories": review.get("peer_directories", []),
        "groups": _group_payload_items(groups),
        "root_files": _root_file_payload_items(placement_review),
        "folder_membership_issues": _folder_membership_payload_items(review),
    }


def llm_topology_review(
    project_root: Path,
    review: dict[str, Any],
    *,
    run_cached_analysis_fn: Callable[..., Any],
    guard_llm_result_fn: Callable[..., Any],
    complete_json_fn: Callable[..., Any],
) -> dict[str, Any] | None:
    payload = topology_payload(review)
    prompt = f"Input:\n{payload}"
    result, _ = run_cached_analysis_fn(
        project_root,
        namespace="architect_topology_review",
        payload=payload,
        runner=lambda: guard_llm_result_fn(
            project_root,
            task="architect_topology_review",
            runner=lambda: complete_json_fn(
                project_root,
                task="architect_topology_review",
                tier="weak",
                prompt=prompt,
                timeout_sec=20.0,
                max_tokens=2200,
            ),
        ),
    )
    return result if isinstance(result, dict) else None


def _raw_group_reviews(llm_part: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(llm_part, dict):
        return []
    if isinstance(llm_part.get("group_reviews"), list):
        return [item for item in llm_part.get("group_reviews", []) if isinstance(item, dict)]
    if isinstance(llm_part.get("reviews"), list):
        return [item for item in llm_part.get("reviews", []) if isinstance(item, dict)]
    if str(llm_part.get("group_id", "") or ""):
        return [llm_part]
    return []


def _name_list(item: dict[str, Any], key: str, *, limit: int) -> list[str]:
    raw = item.get(key, [])
    if not isinstance(raw, list):
        return []
    return [str(name or "") for name in raw[:limit] if str(name or "").strip()]


def _recommended_folder(item: dict[str, Any], group: dict[str, Any]) -> str:
    return str(
        item.get("recommended_folder", "")
        or item.get("recommended_name", "")
        or group.get("programmatic_name", "")
    )


def _topology_review_entry(item: dict[str, Any], recommended: str) -> dict[str, Any]:
    review = {
        "decision": str(item.get("decision", "") or "review"),
        "recommended_folder": recommended,
        "alternatives": _name_list(item, "alternatives", limit=3),
        "reason": str(item.get("reason", "") or ""),
        "style_fit": item.get("style_fit", {}) if isinstance(item.get("style_fit"), dict) else {},
        "confidence": float(item.get("confidence", 0.0) or 0.0),
        "human_review_note": str(item.get("human_review_note", "") or ""),
    }
    split_suggestion = _name_list(item, "split_suggestion", limit=4)
    if split_suggestion:
        review["split_suggestion"] = split_suggestion
    return review


def _naming_review_entry(item: dict[str, Any], topology_review: dict[str, Any], recommended: str) -> dict[str, Any]:
    return {
        "decision": topology_review["decision"],
        "recommended_name": recommended,
        "alternatives": topology_review["alternatives"],
        "rejected_names": _name_list(item, "rejected_names", limit=4),
        "reason": topology_review["reason"],
        "style_fit": topology_review["style_fit"],
        "confidence": topology_review["confidence"],
        "human_review_note": topology_review["human_review_note"],
    }


def apply_llm_reviews(review: dict[str, Any], llm_part: dict[str, Any] | None) -> None:
    groups = review.get("groups", [])
    if not isinstance(groups, list) or not groups:
        return
    by_group = {
        str(item.get("group_id", "") or ""): item
        for item in _raw_group_reviews(llm_part)
        if str(item.get("group_id", "") or "")
    }
    for group in groups:
        if not isinstance(group, dict):
            continue
        item = by_group.get(str(group.get("group_id", "") or ""))
        if not item:
            continue
        recommended = _recommended_folder(item, group)
        topology_review = _topology_review_entry(item, recommended)
        group["topology_review"] = topology_review
        group["naming_review"] = _naming_review_entry(item, topology_review, recommended)
