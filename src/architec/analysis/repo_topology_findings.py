from __future__ import annotations

from typing import Any


def _base_findings(
    *,
    source_root: str,
    flat_file_total: int,
    subpackage_total: int,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if flat_file_total >= 20:
        findings.append(
            {
                "severity": "warning",
                "kind": "root_flatness",
                "scope": source_root,
                "detail": (
                    f"{source_root} contains {flat_file_total} direct Python modules, "
                    "which weakens package-level boundaries."
                ),
            }
        )
    if subpackage_total == 0 and flat_file_total >= 12:
        findings.append(
            {
                "severity": "warning",
                "kind": "missing_subpackages",
                "scope": source_root,
                "detail": "No functional subpackages detected under the primary source root.",
            }
        )
    return findings


def _root_placement_findings(
    *,
    source_root: str,
    placement_review: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    misplaced = (
        placement_review.get("misplaced_root_files", [])
        if isinstance(placement_review, dict)
        else []
    )
    review_root = (
        placement_review.get("review_root_files", [])
        if isinstance(placement_review, dict)
        else []
    )
    if isinstance(misplaced, list) and misplaced:
        findings.append(
            {
                "severity": "warning",
                "kind": "root_non_facade_file",
                "scope": source_root,
                "detail": (
                    f"{len(misplaced)} implementation modules appear to be misplaced at the package root "
                    "and should move into functional subpackages."
                ),
            }
        )
    if isinstance(review_root, list) and len(review_root) >= 3:
        findings.append(
            {
                "severity": "warning",
                "kind": "uncertain_root_placement",
                "scope": source_root,
                "detail": (
                    f"{len(review_root)} root modules still require manual placement review "
                    "after programmatic analysis."
                ),
            }
        )
    return findings


def _mixed_group_findings(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for group in groups[:6]:
        if str(group.get("status", "")) != "mixed":
            continue
        findings.append(
            {
                "severity": "warning",
                "kind": "mixed_domain_group",
                "scope": str(group.get("group_id", "") or ""),
                "detail": (
                    f"group {group.get('group_id', '')} mixes several secondary file families "
                    "and likely needs explicit subfolders."
                ),
            }
        )
    return findings


def _membership_conflict_findings(
    *,
    source_root: str,
    folder_membership_review: dict[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    issues = (
        folder_membership_review.get("issues", [])
        if isinstance(folder_membership_review, dict)
        else []
    )
    for issue in issues[:4]:
        if not isinstance(issue, dict):
            continue
        findings.append(
            {
                "severity": str(issue.get("severity", "info") or "info"),
                "kind": "folder_membership_conflict",
                "scope": str(issue.get("group_id", "") or source_root),
                "detail": str(issue.get("detail", "") or ""),
            }
        )
    return findings


def topology_findings(
    *,
    source_root: str,
    flat_file_total: int,
    subpackage_total: int,
    groups: list[dict[str, Any]],
    placement_review: dict[str, Any],
    folder_membership_review: dict[str, Any],
) -> list[dict[str, Any]]:
    findings = _base_findings(
        source_root=source_root,
        flat_file_total=flat_file_total,
        subpackage_total=subpackage_total,
    )
    findings.extend(
        _root_placement_findings(
            source_root=source_root,
            placement_review=placement_review,
        )
    )
    findings.extend(_mixed_group_findings(groups))
    findings.extend(
        _membership_conflict_findings(
            source_root=source_root,
            folder_membership_review=folder_membership_review,
        )
    )
    return findings
