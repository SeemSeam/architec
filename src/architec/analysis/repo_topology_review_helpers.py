from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..support.io_utils import normalize_relpath
from .repo_topology_findings import topology_findings


def root_role_for_path(
    path: str,
    *,
    root_keep_filenames: set[str],
    root_facade_stems: set[str],
) -> str:
    basename = Path(path).name
    stem = Path(path).stem
    if basename in root_keep_filenames:
        return "entrypoint"
    if stem in root_facade_stems:
        return "facade"
    return "implementation"


def _placement_entry(
    *,
    path: str,
    role: str,
    group: dict[str, Any] | None,
    folder: str,
    alternatives: list[str],
    confidence: float,
    import_signals: dict[str, Any],
) -> dict[str, Any]:
    return {
        "path": path,
        "root_role": role,
        "group_id": str(group.get("group_id", "") or "") if isinstance(group, dict) else "",
        "programmatic_folder": folder,
        "alternative_folders": alternatives[:3],
        "confidence": round(confidence, 2),
        "import_signals": import_signals,
    }


def _placement_decision(
    *,
    role: str,
    folder: str,
    confidence: float,
    import_signals: dict[str, Any],
) -> tuple[str, str]:
    confidence_gate = 0.76
    if import_signals.get("internal_import_total", 0) >= 6:
        confidence_gate = 0.84
    if role in {"entrypoint", "facade"}:
        return (
            "keep_root",
            "Explicit entrypoint or package-root facade may remain at the source root.",
        )
    if folder and confidence >= confidence_gate:
        return (
            "move",
            f"Implementation module does not belong at package root and aligns with `{folder}`.",
        )
    return (
        "review",
        "Implementation module is at package root but target folder confidence is not yet strong.",
    )


def _membership_issue(
    *,
    group_id: str,
    status: str,
    votes: dict[str, int],
) -> dict[str, Any]:
    sorted_votes = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    detail = (
        f"group `{group_id}` mixes files that vote for "
        + ", ".join(f"`{folder}` x{count}" for folder, count in sorted_votes[:4])
        if len(votes) >= 2 and sorted_votes
        else f"group `{group_id}` requires folder boundary review despite a single dominant folder vote."
    )
    return {
        "group_id": group_id,
        "severity": "warning" if len(votes) >= 2 else "info",
        "status": status,
        "folder_votes": votes,
        "detail": detail,
    }


def placement_review(
    *,
    project_root: Path,
    source_root: str,
    direct_files: list[str],
    groups: list[dict[str, Any]],
    path_to_descriptor: dict[str, dict[str, Any]],
    root_keep_filenames: set[str],
    root_facade_stems: set[str],
    file_folder_vote_fn: Callable[..., tuple[str, list[str], float]],
    module_import_signals_fn: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    group_by_file: dict[str, dict[str, Any]] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        for path in group.get("candidate_files", []):
            norm = normalize_relpath(str(path or ""))
            if norm:
                group_by_file[norm] = group

    placements: list[dict[str, Any]] = []
    allowed_root_files: list[dict[str, Any]] = []
    misplaced_root_files: list[dict[str, Any]] = []
    review_root_files: list[dict[str, Any]] = []
    by_path: dict[str, dict[str, Any]] = {}

    for path in direct_files:
        role = root_role_for_path(
            path,
            root_keep_filenames=root_keep_filenames,
            root_facade_stems=root_facade_stems,
        )
        group = group_by_file.get(path)
        folder, alternatives, confidence = file_folder_vote_fn(
            path,
            path_to_descriptor=path_to_descriptor,
        )
        import_signals = module_import_signals_fn(project_root, path, source_root)
        entry = _placement_entry(
            path=path,
            role=role,
            group=group,
            folder=folder,
            alternatives=alternatives,
            confidence=confidence,
            import_signals=import_signals,
        )
        entry["decision"], entry["reason"] = _placement_decision(
            role=role,
            folder=folder,
            confidence=confidence,
            import_signals=import_signals,
        )
        if entry["decision"] == "keep_root":
            allowed_root_files.append(entry)
        elif entry["decision"] == "move":
            misplaced_root_files.append(entry)
        else:
            review_root_files.append(entry)
        placements.append(entry)
        by_path[path] = entry

    return {
        "summary": (
            f"Keep {len(allowed_root_files)} root entrypoints/facades, "
            f"move {len(misplaced_root_files)} implementation files, "
            f"review {len(review_root_files)} uncertain root placements."
        ),
        "allowed_root_files": allowed_root_files,
        "misplaced_root_files": misplaced_root_files,
        "review_root_files": review_root_files,
        "placements": placements,
        "by_path": by_path,
    }


def folder_membership_review(
    groups: list[dict[str, Any]],
    *,
    path_to_descriptor: dict[str, dict[str, Any]],
    group_folder_votes_fn: Callable[..., dict[str, int]],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("group_id", "") or "")
        files = [
            normalize_relpath(str(path or ""))
            for path in group.get("candidate_files", [])
            if str(path or "").strip()
        ]
        votes = group_folder_votes_fn(files, path_to_descriptor=path_to_descriptor)
        if len(votes) <= 1 and str(group.get("status", "")) != "mixed":
            continue
        issues.append(
            _membership_issue(
                group_id=group_id,
                status=str(group.get("status", "") or ""),
                votes=votes,
            )
        )
    return {
        "summary": (
            f"Found {len(issues)} groups with mixed folder membership signals."
            if issues
            else "No group-level folder membership conflicts detected."
        ),
        "issues": issues,
    }
